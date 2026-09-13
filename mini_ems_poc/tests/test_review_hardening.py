"""Regression cases from the September 2026 runtime review; no plant access."""

import json
import logging
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock

from mini_ems_poc.mini_ems_runtime.channels import ChannelRegistry, PointConfig
from mini_ems_poc.mini_ems_runtime.config import ApiConfig
from mini_ems_poc.mini_ems_runtime.http_api import MiniEmsApiServer
from mini_ems_poc.mini_ems_runtime.read_diagnostics import ChannelReadDiagnosticsService


class MeasurementQualityTest(unittest.TestCase):
    def test_implausible_and_nonfinite_values_are_bad(self):
        registry = ChannelRegistry({"temperature": PointConfig("temperature", 0, 1, "read", "Temperatur")})
        adapter = Mock()
        service = ChannelReadDiagnosticsService(registry, adapter, logging.getLogger("review.quality"))
        for value in (999.0, float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value):
                adapter.read_float.return_value = value
                result = service.read_float_channel("temperature", plausible_min=-30, plausible_max=60)
                self.assertEqual(result.quality, "bad")
                self.assertNotEqual(result.status, "ok")
                # Nonfinite values must not leak into API JSON or persistence.
                json.dumps(result.to_dict(), allow_nan=False)

    def test_valid_value_stays_good_but_partial_failure_is_bad(self):
        registry = ChannelRegistry({"temperature": PointConfig("temperature", 0, 1, "read", "Temperatur")})
        adapter = Mock()
        service = ChannelReadDiagnosticsService(registry, adapter, logging.getLogger("review.quality"))
        adapter.read_float.return_value = 12.5
        good = service.read_float_channel("temperature", plausible_min=-30, plausible_max=60)
        self.assertEqual((good.status, good.quality, good.value), ("ok", "good", 12.5))
        adapter.read_float.side_effect = [12.5, float("nan")]
        partial = service.read_float_channel("temperature", samples=2)
        self.assertEqual(partial.quality, "bad")
        self.assertEqual(partial.successful_sample_count, 1)
        json.dumps(partial.to_dict(), allow_nan=False)


class HealthFreshnessTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name)
        self.db = Mock()
        self.db.get_recent_cycles.return_value = []
        self.server = MiniEmsApiServer(
            api_config=ApiConfig(True, "127.0.0.1", 0, 96), runtime_db=self.db,
            health_path=self.path / "health.json", state_path=self.path / "state.json",
            price_cache_path=self.path / "prices.json", spotmarket_plan_path=self.path / "plan.json",
            dashboard_dir=self.path / "dashboard", logger=logging.getLogger("review.health"),
            read_diagnostics=None,
        )

    def write_health(self, **overrides):
        payload = {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat(),
                   "max_cycle_age_seconds": 120}
        payload.update(overrides)
        self.server.health_path.write_text(json.dumps(payload), encoding="utf-8")

    def test_hour_source_does_not_change_quarterhour_window_settings(self):
        self.server.price_source_resolution = "hour"
        self.assertEqual(self.server._parse_min_consecutive_quarters({"min_consecutive_hours": 2}), 8)
        settings = self.server._spotmarket_settings_payload(8)
        self.assertEqual(settings["min_consecutive_hours"], 2)
        self.assertEqual(settings["resolution"], "quarterhour")
        self.assertEqual(settings["source_resolution"], "hour")

    def test_old_snapshot_is_reassessed_on_both_api_paths_without_cycle(self):
        self.write_health(timestamp=(datetime.now(timezone.utc) - timedelta(seconds=180)).isoformat())
        original = self.server.health_path.read_bytes()
        self.assertEqual(self.server.health_payload()["status"], "stale_runtime")
        health = self.server._get_status_payload()["health"]
        self.assertTrue(health["stale_runtime"])
        self.assertEqual(health["cycle_status"], "healthy")
        self.assertEqual(self.server.health_path.read_bytes(), original)

    def test_missing_invalid_or_future_timestamp_is_not_healthy(self):
        for timestamp in (None, "invalid", "2026-01-01T00:00:00", "2099-01-01T00:00:00Z"):
            with self.subTest(timestamp=timestamp):
                self.write_health(timestamp=timestamp)
                self.assertEqual(self.server.health_payload()["status"], "unknown")
                self.assertTrue(self.server._get_status_payload()["health"]["stale_runtime"])

    def test_fresh_safe_mode_is_alive_but_keeps_its_operational_error(self):
        self.write_health(status="safe_mode", stale_runtime=True, runtime_status="stale_runtime",
                          last_healthy_at="2020-01-01T00:00:00Z")
        health = self.server._get_status_payload()["health"]
        self.assertEqual(health["status"], "safe_mode")
        self.assertEqual(health["runtime_status"], "live")
        self.assertFalse(health["stale_runtime"])

    def test_legacy_snapshot_uses_five_minute_fallback(self):
        self.write_health(max_cycle_age_seconds=None,
                          timestamp=(datetime.now(timezone.utc) - timedelta(seconds=360)).isoformat())
        self.assertEqual(self.server.health_payload()["status"], "stale_runtime")
