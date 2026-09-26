"""Observation, failure recovery and price isolation; only fake devices/providers."""

import json
import logging
import sqlite3
import tempfile
import threading
import unittest
from contextlib import closing
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

from mini_ems_poc.mini_ems_runtime.app import _build_protocol_adapter, _build_price_service
from mini_ems_poc.mini_ems_runtime.background_prices import BackgroundPriceService
from mini_ems_poc.mini_ems_runtime.channels import GRID_ACTIVE_POWER_CHANNEL, PointConfig
from mini_ems_poc.mini_ems_runtime.config import (
    AdditionalInputConfig, DdcHeartbeatConfig, OutputPolicyConfig, build_default_site_config, validate_raw_config,
)
from mini_ems_poc.mini_ems_runtime.http_api import MiniEmsApiServer
from mini_ems_poc.mini_ems_runtime.price_cache import CachedDay, PriceCacheFile, SpotmarketPriceCacheService
from mini_ems_poc.mini_ems_runtime.price_provider_smard import PriceProviderError
from mini_ems_poc.mini_ems_runtime.protocol import AdapterError, ProtocolRoutingAdapter
from mini_ems_poc.mini_ems_runtime.read_diagnostics import ChannelReadDiagnosticsService
from mini_ems_poc.mini_ems_runtime.runtime_db import RuntimeDatabase
from mini_ems_poc.tests import test_runtime as fixtures
from mini_ems_poc.tests import test_commissioning as commissioning_fixtures


class MonitoringTest(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.CycleRunnerTest()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.config = replace(
            self.fixture.config,
            runtime=replace(self.fixture.config.runtime, environment="local", bacnet_mode="simulated",
                            real_writes_enabled=False, operation_mode="monitoring"),
            additional_inputs={"temperature": AdditionalInputConfig(
                "temperature", 0, 100, "Temperatur", read_interval_cycles=3, max_age_seconds=5,
                include_in_health=True, plausible_min=-30, plausible_max=60,
            )},
            ddc_heartbeat=DdcHeartbeatConfig(enabled=True, instance=1200, fallback_timeout_seconds=180),
            output_policies=replace(self.fixture.config.output_policies,
                                   edge_heartbeat=OutputPolicyConfig("ack_only", "critical")),
        )
        self.adapter = Mock()
        self.adapter.read_float.side_effect = lambda point: 12.5
        self.now = datetime.now(timezone.utc)

    def runner(self, price_service=None):
        self.fixture.config = self.config
        runner = self.fixture._build_runner(
            fixtures.FakeSocket(), price_service=price_service or fixtures.FakePriceService(error=PriceProviderError("offline")),
        )
        runner.adapter = self.adapter
        runner.read_diagnostics = ChannelReadDiagnosticsService(
            runner.registry, self.adapter, self.fixture.logger, now=lambda: self.now,
        )
        return runner

    def test_monitoring_collects_without_price_or_any_output_and_persists(self):
        runner = self.runner()
        snapshot = runner.run_cycle()
        self.assertEqual(snapshot["status"], "healthy")
        self.assertEqual(snapshot["operation_mode"], "monitoring")
        self.assertEqual(snapshot["price_control_status"], "disabled")
        self.assertEqual(snapshot["acquisition_status"], "healthy")
        self.assertIsNone(snapshot["current_price_ct_kwh"])
        self.assertFalse(snapshot["price_source_status"]["current_price_available"])
        self.assertEqual(snapshot["outputs"], {})
        self.assertEqual(snapshot["write_results"], {})
        self.adapter.write_with_confirmation.assert_not_called()
        self.adapter.relinquish_with_confirmation.assert_not_called()
        row = runner.runtime_db.get_channel_history("temperature", 10)[0]
        self.assertEqual(row["quality"], "good")
        self.assertEqual(row["received_at"], self.now.isoformat().replace("+00:00", "Z"))
        self.assertIsNone(row["source_timestamp"])
        report = runner.runtime_db.get_daily_report(snapshot["today_date"])
        self.assertEqual(report["cycle_count"], 1)
        self.assertEqual(report["sample_quality_counts"], {"good": 2})
        json.dumps(snapshot, allow_nan=False)

    def test_grid_failure_does_not_skip_other_controller_or_invent_normal_values(self):
        def read(point):
            if point.channel_id == GRID_ACTIVE_POWER_CHANNEL:
                raise AdapterError("controller offline")
            return 18.0
        self.adapter.read_float.side_effect = read
        runner = self.runner()
        snapshot = runner.run_cycle()
        self.assertEqual(snapshot["status"], "degraded")
        self.assertEqual(snapshot["input_reads"]["temperature"]["value"], 18)
        self.assertIsNone(snapshot["grid_active_power_kw"])
        self.assertEqual(runner.runtime_db.get_daily_report(snapshot["today_date"])["grid_active_power_kw"]["sample_count"], 0)

    def test_control_mode_keeps_collecting_on_price_failure_but_does_not_decide(self):
        self.config = replace(self.config, runtime=replace(self.config.runtime, operation_mode="control"),
                              ddc_heartbeat=DdcHeartbeatConfig())
        runner = self.runner()
        snapshot = runner.run_cycle()
        self.assertEqual(snapshot["status"], "safe_mode")
        self.assertEqual(snapshot["price_control_status"], "blocked")
        self.assertEqual(snapshot["input_reads"]["temperature"]["value"], 12.5)
        self.assertEqual(len(runner.runtime_db.get_channel_history("temperature", 10)), 1)
        self.adapter.write_with_confirmation.assert_not_called()

    def test_skipped_reads_age_without_duplicate_measurements_and_refresh_recovers(self):
        runner = self.runner()
        first = runner.run_cycle()["input_reads"]["temperature"]
        self.now += timedelta(seconds=10)
        second = runner.run_cycle()["input_reads"]["temperature"]
        self.assertEqual(second["received_at"], first["received_at"])
        self.assertEqual(second["age_seconds"], 10)
        self.assertEqual(second["quality"], "stale")
        self.assertFalse(second["read_attempted"])
        self.assertEqual(len(runner.runtime_db.get_channel_history("temperature", 10)), 1)
        self.now += timedelta(seconds=1)
        third = runner.run_cycle()["input_reads"]["temperature"]
        self.assertEqual(third["quality"], "good")
        self.assertNotEqual(third["received_at"], first["received_at"])
        self.assertEqual(third["source_freshness"], "unknown")  # Identical value is not proof of source freshness.
        self.assertEqual(len(runner.runtime_db.get_channel_history("temperature", 10)), 2)

    def test_restart_does_not_relabel_old_sample_as_new_or_repeat_outputs(self):
        first = self.runner().run_cycle()
        self.now += timedelta(seconds=10)
        self.adapter.read_float.side_effect = AdapterError("offline after restart")
        restarted = self.runner()
        second = restarted.run_cycle()
        self.assertNotEqual(second["cycle_id"], first["cycle_id"])
        self.assertIsNone(second["input_reads"]["temperature"]["value"])
        self.assertEqual(second["input_reads"]["temperature"]["quality"], "bad")
        self.assertEqual(len(restarted.runtime_db.get_channel_history("temperature", 10)), 2)
        self.adapter.write_with_confirmation.assert_not_called()

    def test_manual_diagnostic_cannot_replace_acquisition_cache_or_limits(self):
        runner = self.runner()
        first = runner.run_cycle()["input_reads"]["temperature"]
        self.now += timedelta(seconds=10)
        self.adapter.read_float.return_value = 999
        self.adapter.read_float.side_effect = None
        diagnostic = runner.read_diagnostics.read_float_channel(
            "temperature", plausible_min=-1_000_000, plausible_max=1_000_000,
        )
        self.assertEqual(diagnostic.quality, "good")  # Deliberately broad manual diagnostics.
        cached = runner.run_cycle()["input_reads"]["temperature"]
        self.assertEqual(cached["value"], 12.5)
        self.assertEqual(cached["received_at"], first["received_at"])
        self.assertEqual(cached["max_age_seconds"], 5)
        self.assertEqual(cached["quality"], "stale")
        self.assertEqual(len(runner.runtime_db.get_channel_history("temperature", 10)), 1)

    def test_failed_read_retains_last_receipt_but_does_not_return_last_value_as_valid(self):
        runner = self.runner()
        service = runner.read_diagnostics
        first = service.read_float_channel("temperature")
        self.now += timedelta(seconds=8)
        self.adapter.read_float.side_effect = AdapterError("offline")
        failed = service.read_float_channel("temperature")
        self.assertIsNone(failed.value)
        self.assertEqual(failed.last_successful_read_at, first.last_successful_read_at)
        self.assertEqual(failed.age_seconds, 8)
        self.assertEqual(failed.quality, "bad")

    def test_api_ages_measurements_without_rewriting_evidence(self):
        self.now -= timedelta(seconds=30)
        runner = self.runner()
        runner.run_cycle()
        before = self.config.health_path.read_bytes()
        self.config.spotmarket_plan_path.parent.mkdir(parents=True, exist_ok=True)
        old_plan = '{"today": {"windows": [{"start_label": "10:00"}]}}'
        self.config.spotmarket_plan_path.write_text(old_plan)
        server = MiniEmsApiServer(
            api_config=self.config.api, runtime_db=runner.runtime_db,
            health_path=self.config.health_path, state_path=self.config.state_path,
            price_cache_path=self.config.price_cache_path, spotmarket_plan_path=self.config.spotmarket_plan_path,
            dashboard_dir=self.fixture.base_dir, logger=self.fixture.logger, read_diagnostics=runner.read_diagnostics,
        )
        payload = server._get_status_payload()
        health = payload["health"]
        self.assertEqual(payload["spotmarket_plan"], {})
        self.assertEqual(self.config.spotmarket_plan_path.read_text(), old_plan)
        self.assertEqual(health["measurements"]["temperature"]["quality"], "stale")
        self.assertEqual(health["acquisition_status"], "degraded")
        self.assertEqual(health["status"], "degraded")
        self.assertEqual(health["cycle_status"], "healthy")
        self.assertEqual(before, self.config.health_path.read_bytes())

    def test_collection_continues_while_price_refresh_is_blocked_without_cache(self):
        started, release = threading.Event(), threading.Event()
        service = Mock()
        def blocked():
            started.set()
            release.wait(timeout=5)
        service.refresh.side_effect = blocked
        service.read_cached_snapshot.side_effect = PriceProviderError("no cache")
        background = BackgroundPriceService(service)
        try:
            runner = self.runner(price_service=background)
            first = runner.run_cycle()
            self.assertTrue(started.wait(timeout=1))
            second = runner.run_cycle()
            self.assertNotEqual(first["cycle_id"], second["cycle_id"])
            self.assertEqual(second["status"], "healthy")
            self.assertEqual(len(runner.runtime_db.get_channel_history(GRID_ACTIVE_POWER_CHANNEL, 10)), 2)
            self.assertEqual(service.refresh.call_count, 1)
            self.adapter.write_with_confirmation.assert_not_called()
        finally:
            release.set()
            background.close()

    def test_pending_releases_are_reported_as_unresolved(self):
        runner = self.runner()
        runner.pending_releases = lambda: 1
        snapshot = runner.run_cycle()
        self.assertEqual(snapshot["status"], "degraded")
        self.assertEqual(snapshot["pending_release_count"], 1)
        self.assertIn("Rückgaben", snapshot["operator_message"])


class MonitoringBoundaryTest(unittest.TestCase):
    def test_existing_database_migrates_without_inventing_historical_quality(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "history.sqlite"
            # Schema shipped before receipt/quality metadata was persisted.
            with closing(sqlite3.connect(path)) as connection:
                connection.execute("""CREATE TABLE channel_samples (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, cycle_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL, channel_id TEXT NOT NULL, direction TEXT NOT NULL,
                    value REAL, desired_value REAL, is_confirmed INTEGER, confirmation_mode TEXT,
                    criticality TEXT, source TEXT, error TEXT, readback_value REAL
                )""")
                connection.execute("""INSERT INTO channel_samples
                    (cycle_id, timestamp, channel_id, direction, value, source)
                    VALUES ('old', '2026-09-19T10:00:00Z', 'temperature', 'input', 18, 'bacnet_read')""")
                connection.commit()
            for _ in range(2):  # Restart must also be safe after the additive migration.
                row = RuntimeDatabase(path).get_channel_history("temperature", 10)[0]
                self.assertEqual(row["value"], 18)
                self.assertIsNone(row["quality"])
                self.assertIsNone(row["received_at"])
                self.assertIsNone(row["source_timestamp"])

    def test_configuration_requires_explicit_mode_and_retains_local_simulation_boundary(self):
        raw = build_default_site_config("test-token")
        self.assertEqual(validate_raw_config(raw, base_dir=Path("/tmp")).runtime.operation_mode, "control")
        raw["runtime"].update(environment="ipc", bacnet_mode="real", real_writes_enabled=False)
        with self.assertRaises(ValueError):
            validate_raw_config(raw, base_dir=Path("/tmp"))
        raw["runtime"]["operation_mode"] = "monitoring"
        self.assertEqual(validate_raw_config(raw, base_dir=Path("/tmp")).runtime.operation_mode, "monitoring")
        raw["runtime"]["real_writes_enabled"] = True
        with self.assertRaises(ValueError):
            validate_raw_config(raw, base_dir=Path("/tmp"))
        raw["runtime"].update(environment="local", real_writes_enabled=False)
        with self.assertRaises(ValueError):
            validate_raw_config(raw, base_dir=Path("/tmp"))

    def test_adapter_blocks_write_and_relinquish_even_when_called_directly(self):
        driver = Mock()
        driver.read_float.return_value = 5.0
        adapter = ProtocolRoutingAdapter({"bacnet": driver}, allow_writes=False)
        point = PointConfig("test", 2, 1, "readwrite", "Test")
        self.assertEqual(adapter.read_float(point), 5.0)
        with self.assertRaises(PermissionError):
            adapter.write_with_confirmation(point, 1, "ack_only")
        with self.assertRaises(PermissionError):
            adapter.relinquish_with_confirmation(point, "ack_only")
        driver.write_with_confirmation.assert_not_called()
        driver.relinquish_with_confirmation.assert_not_called()

    def test_application_builds_guarded_simulation_and_background_real_price_service(self):
        with tempfile.TemporaryDirectory() as temporary:
            raw = build_default_site_config("test-token")
            raw["runtime"]["operation_mode"] = "monitoring"
            config = validate_raw_config(raw, base_dir=Path(temporary))
            adapter = _build_protocol_adapter(config, logging.getLogger("monitoring"))
            try:
                with self.assertRaises(PermissionError):
                    adapter.write_with_confirmation(PointConfig("test", 2, 1, "write", "Test"), 1, "ack_only")
            finally:
                adapter.close()
            config = replace(config, runtime=replace(config.runtime, environment="ipc", bacnet_mode="real"))
            prices = _build_price_service(config, logging.getLogger("monitoring"))
            self.assertIsInstance(prices, BackgroundPriceService)
            prices.close()  # Construction does not start network traffic.

    def test_monitoring_preserves_unfinished_lease_across_recovery_and_shutdown(self):
        fixture = commissioning_fixtures.CommissioningTest()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        adapter = commissioning_fixtures.FakeAdapter(readback=True)
        control = fixture.service(adapter=adapter)
        point = fixture.approve(control)
        lease = control.start_test({"point_id": point["id"], "value": True}, fixture.admin)["lease"]
        config = replace(fixture.config, runtime=replace(fixture.config.runtime, operation_mode="monitoring", real_writes_enabled=False))
        monitor = fixture.service(adapter=adapter, config=config)
        monitor.recover_unfinished()
        monitor.shutdown()
        self.assertEqual(monitor.points_payload()["pending_release_count"], 1)
        self.assertFalse(monitor.points_payload()["write_tests_available"])
        with self.assertRaises(PermissionError):
            monitor.start_test({"point_id": point["id"], "value": False}, fixture.admin)
        with self.assertRaises(PermissionError):
            monitor.release_test(lease["id"], fixture.admin)
        self.assertEqual(adapter.relinquishes, [])
        self.assertEqual(len(adapter.writes), 1)
        control.recover_unfinished()  # Explicitly returning to control can complete the original obligation.
        self.assertEqual(len(adapter.relinquishes), 1)
        self.assertEqual(monitor.points_payload()["pending_release_count"], 0)


class BackgroundPriceTest(unittest.TestCase):
    def test_cached_fallback_keeps_source_failure_visible_until_success(self):
        service = Mock()
        service.refresh.return_value = Mock(price_source_status={"stale": True, "error": "provider offline"})
        background = BackgroundPriceService(service, refresh_seconds=3600)
        try:
            background.refresh()
            background._worker.join(timeout=1)
            background.refresh()
            service.read_cached_snapshot.assert_called_with(error="provider offline", refreshing=False)
            service.refresh.return_value = Mock(price_source_status={})
            background._next_refresh = 0
            background.refresh()
            background._worker.join(timeout=1)
            background.refresh()
            service.read_cached_snapshot.assert_called_with(error=None, refreshing=False)
        finally:
            background.close()

    def test_blocked_source_does_not_block_cache_reads_or_spawn_multiple_workers(self):
        started, release = threading.Event(), threading.Event()
        service = Mock()
        def blocked():
            started.set()
            release.wait(timeout=5)
        service.refresh.side_effect = blocked
        service.read_cached_snapshot.side_effect = PriceProviderError("no cache")
        background = BackgroundPriceService(service)
        try:
            for _ in range(5):
                with self.assertRaises(PriceProviderError):
                    background.refresh()
            self.assertTrue(started.wait(timeout=1))
            self.assertEqual(service.refresh.call_count, 1)
            self.assertFalse(release.is_set())
        finally:
            release.set()
            background.close()

    def test_cached_price_tracks_current_interval_and_missing_interval_blocks(self):
        with tempfile.TemporaryDirectory() as temporary:
            provider = Mock()
            provider.config.provider = "smard"
            provider.config.resolution = "quarterhour"
            provider.current_slot_index.side_effect = lambda now: now.hour * 4 + now.minute // 15
            service = SpotmarketPriceCacheService(Path(temporary) / "prices.json", provider)
            slots = [None] * 96
            slots[0], slots[1] = 1.0, 9.0
            service._save_cache(PriceCacheFile("2026-09-20T00:00:00+02:00", CachedDay("2026-09-20", slots), None))
            for minute, expected in ((0, 1.0), (15, 9.0)):
                with patch("mini_ems_poc.mini_ems_runtime.price_cache.berlin_now", return_value=datetime.fromisoformat(f"2026-09-20T00:{minute:02}:00+02:00")):
                    self.assertEqual(service.read_cached_snapshot(error="offline", refreshing=True).current_price_ct_kwh, expected)
            with patch("mini_ems_poc.mini_ems_runtime.price_cache.berlin_now", return_value=datetime.fromisoformat("2026-09-20T00:30:00+02:00")):
                with self.assertRaises(PriceProviderError):
                    service.read_cached_snapshot(error="offline", refreshing=False)


if __name__ == "__main__":
    unittest.main()
