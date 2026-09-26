"""Storage and process failures, using disposable sites and simulated devices."""

import json
import logging
import os
import subprocess
import sys
import tempfile
import time
import unittest
from dataclasses import replace
from pathlib import Path
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from mini_ems_poc.tests import test_monitoring as fixtures
from mini_ems_poc.mini_ems_runtime.logging_utils import setup_logging
from mini_ems_poc.mini_ems_runtime.http_api import MiniEmsApiServer
from mini_ems_poc.mini_ems_runtime.state_store import write_json_atomic
from mini_ems_poc.mini_ems_runtime.supervisor import site_lock, supervise_runtime


class StorageHealthTest(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.MonitoringTest()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.runner = self.fixture.runner()

    def test_atomic_json_write_retries_a_transient_reader_lock(self):
        path = self.fixture.config.base_dir / "lock-test.json"
        original_replace = os.replace
        calls = 0

        def replace_after_lock(source, target):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise PermissionError("temporary Windows reader lock")
            return original_replace(source, target)

        with patch("mini_ems_poc.mini_ems_runtime.state_store.os.replace", side_effect=replace_after_lock):
            write_json_atomic(path, {"status": "healthy"})
        self.assertEqual(calls, 2)
        self.assertEqual(json.loads(path.read_text()), {"status": "healthy"})

    def test_database_failure_is_visible_and_recovers_without_inventing_history(self):
        original = self.runner.runtime_db.path
        self.runner.runtime_db.path = Path(original).parent  # A directory is not a SQLite database.
        failed = self.runner.run_cycle()
        self.assertEqual(failed["status"], "degraded")
        self.assertEqual(failed["acquisition_status"], "healthy")
        health = json.loads(self.fixture.config.health_path.read_text())
        self.assertEqual(health["storage_status"], "error")
        self.assertIn("history", health["storage_errors"])
        self.runner.runtime_db.path = original
        recovered = self.runner.run_cycle()
        self.assertEqual(recovered["storage_status"], "ok")
        self.assertEqual(recovered["storage_errors"], {})
        self.assertEqual(recovered["status"], "healthy")
        rows = self.runner.runtime_db.get_recent_cycles(10)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["cycle_id"], recovered["cycle_id"])
        channels = self.runner.runtime_db.get_report_studio_payload(recovered["today_date"])["config"]["available_channels"]
        self.assertIn("grid.active_power_kw", [item["id"] for item in channels])
        self.assertNotIn("site.chp_electric_energy_kwh", [item["id"] for item in channels])

    def test_state_failure_does_not_hide_still_available_history(self):
        self.fixture.config.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.runner.state_store.path = self.fixture.config.state_path.parent
        failed = self.runner.run_cycle()
        self.assertEqual(failed["storage_status"], "error")
        self.assertIn("state", failed["storage_errors"])
        self.assertEqual(len(self.runner.runtime_db.get_recent_cycles(10)), 1)
        self.assertEqual(json.loads(self.fixture.config.health_path.read_text())["status"], "degraded")

    def test_health_write_failure_cannot_leave_fresh_healthy_evidence(self):
        self.runner.run_cycle()
        before = self.fixture.config.health_path.read_bytes()
        # Block the atomic temporary file, leaving the last snapshot as evidence.
        temporary = self.fixture.config.health_path.with_suffix(".json.tmp")
        temporary.mkdir()
        with self.assertRaises(OSError):
            self.runner.run_cycle()
        self.assertEqual(self.fixture.config.health_path.read_bytes(), before)

    def test_restart_after_failed_state_save_preserves_previous_history(self):
        state_path = self.runner.state_store.path
        state_path.parent.mkdir(parents=True, exist_ok=True)
        self.runner.state_store.path = state_path.parent
        failed = self.runner.run_cycle()
        restarted = self.fixture.runner().run_cycle()
        self.assertNotEqual(failed["cycle_id"], restarted["cycle_id"])
        self.assertEqual(len(self.runner.runtime_db.get_recent_cycles(10)), 2)

    def test_live_runtime_with_lost_supervisor_is_degraded_without_altering_evidence(self):
        # This test checks supervisor liveness; keep the short-lived sensor fixture
        # fresh even on slow Windows CI workers.
        self.fixture.config = replace(self.fixture.config, additional_inputs={
            key: replace(input_config, max_age_seconds=300)
            for key, input_config in self.fixture.config.additional_inputs.items()
        })
        self.runner = self.fixture.runner()
        self.runner.run_id = "test-supervised-run"
        self.runner.run_cycle()
        config = self.fixture.config
        before = config.health_path.read_bytes()
        server = MiniEmsApiServer(config.api, self.runner.runtime_db, config.health_path,
                                 config.state_path, config.price_cache_path, config.spotmarket_plan_path,
                                 config.base_dir / "dashboard", self.runner.logger, self.runner.read_diagnostics)
        self.assertEqual(server.health_payload()["supervision_status"], "unavailable")
        self.assertEqual(server.health_payload()["status"], "degraded")
        config.health_path.with_name("supervisor.json").write_text(json.dumps({
            "run_id": self.runner.run_id, "status": "running", "timestamp": datetime.now(timezone.utc).isoformat(),
        }))
        self.assertEqual(server.health_payload()["status"], "healthy")
        self.assertEqual(server.health_payload()["supervision_status"], "ok")
        self.assertEqual(config.health_path.read_bytes(), before)

    def test_log_rotation_is_bounded_and_supervisor_has_its_own_log(self):
        runtime = setup_logging(self.fixture.config)
        supervisor = setup_logging(self.fixture.config, supervisor=True)
        for logger in (runtime, supervisor):
            for handler in logger.handlers:
                self.addCleanup(handler.close)
                self.addCleanup(logger.removeHandler, handler)
                if hasattr(handler, "maxBytes"):
                    self.assertEqual(handler.maxBytes, 5 * 1024 * 1024)
                    handler.maxBytes = 100  # Exercise real rotation with small disposable files.
            for index in range(12):
                logger.warning("%s %s", index, "x" * 80)
        for name in ("mini_ems.log", "supervisor.log"):
            files = list(self.fixture.config.log_dir.glob(name + "*"))
            self.assertEqual(len(files), 4)
            self.assertIn("11 ", (self.fixture.config.log_dir / name).read_text())


class SupervisorTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.config = SimpleNamespace(
            health_path=self.directory / "health.json",
            watchdog=SimpleNamespace(max_cycle_age_seconds=0.15),
        )
        self.logger = logging.getLogger("supervisor-test")
        self.status_path = self.directory / "supervisor.json"

    def supervise(self, script, **kwargs):
        return supervise_runtime(
            self.config, self.logger, [sys.executable, "-c", script, str(self.config.health_path)],
            poll_seconds=0.01, restart_delay_seconds=0.01, startup_seconds=1, **kwargs,
        )

    def test_crashes_exhaust_persisted_budget_and_do_not_restart_forever(self):
        with self.assertLogs(self.logger, level="INFO"):
            self.assertEqual(self.supervise("raise SystemExit(8)"), 3)
        status = json.loads(self.status_path.read_text())
        self.assertEqual(status["status"], "restart_blocked")
        self.assertEqual(len(status["start_timestamps"]), 3)
        with patch("mini_ems_poc.mini_ems_runtime.supervisor.subprocess.Popen") as spawn:
            with self.assertLogs(self.logger, level="ERROR"):
                self.assertEqual(self.supervise("raise SystemExit(8)"), 3)
            spawn.assert_not_called()

    def test_hung_child_is_stopped_and_old_health_cannot_prove_new_process_alive(self):
        script = self.child_script("time.sleep(20)")
        with self.assertLogs(self.logger, level="INFO") as events:
            self.assertEqual(self.supervise(script, max_starts=2), 3)
        records = [json.loads(item.split(":", 2)[2]) for item in events.output]
        runs = [item["run_id"] for item in records if item["event"] == "supervisor.running"]
        self.assertEqual(len(set(runs)), 2)
        self.assertEqual(sum(item.get("reason") == "cycle_stalled" for item in records), 2)

    def test_storage_or_domain_failure_with_advancing_cycles_is_not_restarted(self):
        script = self.child_script("time.sleep(0.025)", cycles=12, storage_status="error")
        with self.assertLogs(self.logger, level="INFO") as events:
            self.assertEqual(self.supervise(script, max_starts=1), 3)
        joined = "\n".join(events.output)
        self.assertIn("storage_error", joined)
        self.assertIn("process_exited:0", joined)
        self.assertNotIn("cycle_stalled", joined)
        self.assertEqual(len(json.loads(self.status_path.read_text())["start_timestamps"]), 1)

    def test_shutdown_stops_child_and_releases_site_lock(self):
        original_sleep = time.sleep
        interrupted = False
        def stop_after_first_cycle(seconds):
            nonlocal interrupted
            original_sleep(seconds)
            if not interrupted and self.config.health_path.exists():
                interrupted = True
                raise KeyboardInterrupt
        with patch("mini_ems_poc.mini_ems_runtime.supervisor.time.sleep", side_effect=stop_after_first_cycle):
            with self.assertLogs(self.logger, level="INFO"):
                self.assertEqual(self.supervise(self.child_script("time.sleep(20)")), 0)
        status = json.loads(self.status_path.read_text())
        self.assertEqual(status["status"], "stopped")
        with site_lock(self.status_path.with_suffix(".lock")):
            pass

    def test_site_lock_excludes_second_process_and_is_released_after_crash(self):
        lock_path = self.directory / "runtime.lock"
        script = (
            "from pathlib import Path; import sys, time; "
            "from mini_ems_poc.mini_ems_runtime.supervisor import site_lock; "
            "lock = site_lock(Path(sys.argv[1])); lock.__enter__(); "
            "print('locked', flush=True); time.sleep(20)"
        )
        child = subprocess.Popen(
            [sys.executable, "-c", script, str(lock_path)],
            cwd=Path(__file__).resolve().parents[2], stdout=subprocess.PIPE, text=True,
        )
        self.addCleanup(child.stdout.close)
        try:
            self.assertEqual(child.stdout.readline().strip(), "locked")
            with self.assertRaisesRegex(RuntimeError, "bereits ein Prozess"):
                with site_lock(lock_path):
                    self.fail("Second runtime must not acquire the site lock")
        finally:
            child.kill()
            child.wait(timeout=5)
        with site_lock(lock_path):
            pass

    def test_invalid_budget_fails_closed_before_spawning(self):
        for invalid in ([], {"start_timestamps": [float("nan")]}, {"start_timestamps": "bad"}):
            self.status_path.write_text(json.dumps(invalid))
            with self.assertRaises(ValueError):
                self.supervise("raise SystemExit(0)")

    @staticmethod
    def child_script(after_publish, *, cycles=1, storage_status="ok"):
        return f"""
import os, sys, time
from datetime import datetime, timezone
from pathlib import Path
from mini_ems_poc.mini_ems_runtime.state_store import write_json_atomic
path = Path(sys.argv[1])
for index in range({cycles}):
    payload = {{"run_id": os.environ["MINI_EMS_RUN_ID"], "cycle_id": str(index),
               "timestamp": datetime.now(timezone.utc).isoformat(),
               "status": "degraded", "storage_status": "{storage_status}"}}
    write_json_atomic(path, payload)
    {after_publish}
"""
