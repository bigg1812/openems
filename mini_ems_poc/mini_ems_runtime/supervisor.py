"""Bounded process supervision. Never makes protocol or control decisions."""

import json
import logging
import math
import os
import signal
import subprocess
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .logging_utils import log_event, utcnow_iso
from .measurement_quality import timestamp_age
from .state_store import write_json_atomic


@contextmanager
def site_lock(path: Path):
    """OS-held lock: a crash releases it without trusting a stale PID file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as handle:
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise RuntimeError("Für diesen Standort läuft bereits ein Prozess: {0}".format(path.name)) from error
        yield


def stop_child(process, *, grace_seconds=10):
    if process.poll() is not None:
        return
    try:
        process.send_signal(signal.CTRL_BREAK_EVENT if os.name == "nt" else signal.SIGTERM)
    except OSError:
        process.terminate()
    try:
        process.wait(timeout=grace_seconds)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def supervise_runtime(config, logger, command, *, poll_seconds=1, restart_delay_seconds=5,
                      max_starts=3, restart_window_seconds=900, startup_seconds=None):
    """Restart only dead/stalled children; domain/storage errors remain visible.

    At most three starts (including the first) per 15 minutes, persisted before
    spawning. Timestamps survive a supervisor restart. After exhaustion an operator
    must investigate; the supervisor exits without launching another child.
    """
    status_path = config.health_path.with_name("supervisor.json")
    max_age = config.watchdog.max_cycle_age_seconds or 300
    startup_seconds = startup_seconds if startup_seconds is not None else max(30, max_age)
    with site_lock(status_path.with_suffix(".lock")):
        previous = json.loads(status_path.read_text()) if status_path.exists() else {}
        attempts = previous.get("start_timestamps", []) if isinstance(previous, dict) else None
        if not isinstance(attempts, list) or any(
            type(item) not in (int, float) or not math.isfinite(item) or item < 0 for item in attempts
        ):
            raise ValueError("Neustartnachweis ist ungültig; bitte supervisor.json prüfen.")
        process = None
        run_id = None
        cycle_id = None
        last_published = None

        def publish(status, reason=None, cycle_status=None):
            nonlocal last_published
            signature = (status, reason, cycle_status, cycle_id, run_id, len(attempts))
            if signature == last_published:
                return
            payload = {
                "timestamp": utcnow_iso(), "status": status, "reason": reason,
                "cycle_status": cycle_status, "cycle_id": cycle_id, "run_id": run_id,
                "process_id": process.pid if process else None,
                "start_timestamps": attempts, "max_starts": max_starts,
                "restart_window_seconds": restart_window_seconds,
                "max_cycle_age_seconds": max_age,
            }
            write_json_atomic(status_path, payload)
            if last_published is None or signature[:3] != last_published[:3]:
                log_event(logger, logging.ERROR if reason else logging.INFO,
                          "supervisor." + status, reason=reason,
                          cycle_status=cycle_status, run_id=run_id)
            last_published = signature

        try:
            while True:
                now = time.time()
                attempts[:] = [item for item in attempts if now - item < restart_window_seconds]
                if len(attempts) >= max_starts:
                    publish("restart_blocked", "restart_budget_exhausted")
                    return 3
                run_id, cycle_id = uuid.uuid4().hex, None
                process = None
                attempts.append(now)
                publish("starting")
                env = {**os.environ, "MINI_EMS_RUN_ID": run_id}
                options = ({"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt"
                           else {"start_new_session": True})
                process = subprocess.Popen(command, env=env, **options)
                last_progress = time.monotonic()
                seen_cycle = False
                while True:
                    exit_code = process.poll()
                    if exit_code is not None:
                        reason = "process_exited:{0}".format(exit_code)
                        break
                    try:
                        health = json.loads(config.health_path.read_text())
                    except (OSError, ValueError):
                        health = {}
                    if isinstance(health, dict) and health.get("run_id") == run_id:
                        age = timestamp_age(health.get("timestamp"), datetime.now(timezone.utc))
                        if age is not None and age <= max_age and health.get("cycle_id"):
                            if health["cycle_id"] != cycle_id:
                                cycle_id = health["cycle_id"]
                                last_progress = time.monotonic()
                                seen_cycle = True
                            alarm = "storage_error" if health.get("storage_status") == "error" else None
                            publish("running", alarm, health.get("status"))
                    if time.monotonic() - last_progress > (max_age if seen_cycle else startup_seconds):
                        reason = "cycle_stalled" if seen_cycle else "startup_timeout"
                        break
                    time.sleep(poll_seconds)
                publish("restarting", reason)
                stop_child(process)
                time.sleep(restart_delay_seconds)
        except KeyboardInterrupt:
            return 0
        except Exception as error:
            publish("failed", str(error))
            raise
        finally:
            if process is not None:
                stop_child(process)
            if last_published is None or last_published[0] not in ("restart_blocked", "failed"):
                publish("stopped")
