import json
import logging
import socket
import struct
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from mini_ems_poc.mini_ems_runtime.bacnet import (
    BacnetAdapter,
    BacnetCommunicationError,
)
from mini_ems_poc.mini_ems_runtime.channels import (
    CURRENT_PRICE_CHANNEL,
    ChannelRegistry,
    GRID_ACTIVE_POWER_CHANNEL,
    GRID_LOCKOUT_CHANNEL,
)
from mini_ems_poc.mini_ems_runtime.config import (
    AdditionalInputConfig,
    ApiConfig,
    ControllersConfig,
    DatabaseConfig,
    GridLockoutConfig,
    LoggingConfig,
    MiniEmsConfig,
    NetworkConfig,
    PointsConfig,
    PriceSourceConfig,
    SafetyConfig,
    SpotMarketLockoutConfig,
    TimingConfig,
    WatchdogConfig,
)
from mini_ems_poc.mini_ems_runtime.cycle import CycleRunner
from mini_ems_poc.mini_ems_runtime.http_api import MiniEmsApiServer
from mini_ems_poc.mini_ems_runtime.objectlist_import import import_objectlist_snapshot
from mini_ems_poc.mini_ems_runtime.price_cache import CachedDay, PriceCacheFile, PublishedPriceSnapshot, SpotmarketPriceCacheService
from mini_ems_poc.mini_ems_runtime.price_provider_smard import PriceProviderError, RecentSlotMapScanResult, SmardPriceProvider, berlin_now
from mini_ems_poc.mini_ems_runtime.read_diagnostics import (
    QUALITY_BAD,
    QUALITY_GOOD,
    QUALITY_STALE,
    ChannelReadDiagnosticsService,
)
from mini_ems_poc.mini_ems_runtime.runtime_db import RuntimeDatabase
from mini_ems_poc.mini_ems_runtime.simulation import SimulatedBacnetAdapter, SimulatedSpotmarketPriceService
from mini_ems_poc.mini_ems_runtime.spotmarket_plan import SpotmarketManualOverrideStore, SpotmarketPlanWriter
from mini_ems_poc.mini_ems_runtime.state_store import StateStore


class FakeSocket:
    def __init__(self, responses=None):
        self.responses = list(responses or [])
        self.sent_packets = []
        self.bound = None
        self.timeout = None
        self.closed = False

    def setsockopt(self, *_args):
        return None

    def bind(self, address):
        self.bound = address

    def settimeout(self, value):
        self.timeout = value

    def sendto(self, data, address):
        self.sent_packets.append((data, address))

    def recvfrom(self, _bufsize):
        if not self.responses:
            raise socket.timeout()
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    def close(self):
        self.closed = True


class FakePriceService:
    def __init__(self, snapshots=None, error=None):
        self.snapshots = list(snapshots or [])
        self.error = error

    def refresh(self):
        if self.error is not None:
            raise self.error
        if not self.snapshots:
            raise AssertionError("No fake price snapshot configured")
        return self.snapshots.pop(0)


class ScriptedClock:
    """Injectable UTC clock returning successive moments from a queue.

    The diagnostics service calls now() once per captured sample and once more
    when computing age, so a script of two timestamps lets a test simulate a
    valid value that is already older than max_age_seconds at evaluation time.
    """

    def __init__(self, moments):
        self._moments = list(moments)
        self._last = self._moments[-1] if self._moments else datetime.now(timezone.utc)

    def __call__(self):
        if self._moments:
            self._last = self._moments.pop(0)
        return self._last


class FakeHTTPHeaders:
    def __init__(self, charset="utf-8"):
        self._charset = charset

    def get_content_charset(self):
        return self._charset


class FakeHTTPResponse:
    def __init__(self, payload, charset="utf-8"):
        self._payload = json.dumps(payload).encode(charset)
        self.headers = FakeHTTPHeaders(charset)

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def make_read_response(value: float):
    return make_read_response_for_point(value, invoke_id=1, instance=300)


def make_read_response_for_point(
    value: float,
    *,
    invoke_id: int,
    instance: int,
    object_type: int = 2,
    sender_ip: str = "192.168.1.100",
    sender_port: int = 47808,
):
    object_id = struct.pack(">I", (object_type << 22) | instance)
    apdu = bytes([0x30, invoke_id, 0x0C, 0x0C]) + object_id + bytes([0x19, 0x55, 0x3E, 0x44]) + struct.pack(">f", value) + bytes([0x3F])
    npdu = bytes([0x01, 0x04])
    payload = bytes([0x81, 0x0A]) + struct.pack(">H", 4 + len(npdu) + len(apdu)) + npdu + apdu
    return payload, (sender_ip, sender_port)


def make_ack_response(*, invoke_id: int, service_choice: int = 0x0F):
    npdu = bytes([0x01, 0x04])
    apdu = bytes([0x20, invoke_id, service_choice])
    payload = bytes([0x81, 0x0A]) + struct.pack(">H", 4 + len(npdu) + len(apdu)) + npdu + apdu
    return payload, ("192.168.1.100", 47808)


def make_wrong_sender_response(value: float):
    payload, _sender = make_read_response_for_point(value, invoke_id=1, instance=300)
    return payload, ("10.0.0.5", 47808)


class BacnetAdapterTest(unittest.TestCase):
    def setUp(self) -> None:
        self.logger = logging.getLogger("mini_ems.runtime.test.adapter")
        self.logger.handlers.clear()
        self.logger.addHandler(logging.NullHandler())
        self.network = NetworkConfig(
            controller_ip="192.168.1.100",
            controller_port=47808,
            local_ip="192.168.1.50",
            local_port=47809,
            response_timeout_seconds=0.1,
            retries=0,
        )
        self.registry = ChannelRegistry.from_points_config(
            PointsConfig(
                grid_active_power_kw=300,
                current_price_av=1000,
                grid_lockout_bv=400,
                spotmarket_lockout_bv=401,
            )
        )

    def test_wrong_sender_is_ignored(self) -> None:
        fake_socket = FakeSocket(
            [
                make_wrong_sender_response(7.5),
                make_read_response_for_point(4.25, invoke_id=1, instance=300),
            ]
        )
        adapter = BacnetAdapter(self.network, self.logger, sock=fake_socket)

        value = adapter.read_float(self.registry.get(GRID_ACTIVE_POWER_CHANNEL))

        self.assertEqual(value, 4.25)
        self.assertEqual(len(fake_socket.sent_packets), 1)

    def test_read_timeout_raises(self) -> None:
        fake_socket = FakeSocket([socket.timeout()])
        adapter = BacnetAdapter(self.network, self.logger, sock=fake_socket)

        with self.assertRaises(BacnetCommunicationError):
            adapter.read_float(self.registry.get(GRID_ACTIVE_POWER_CHANNEL))

    def test_missing_ack_raises(self) -> None:
        fake_socket = FakeSocket([socket.timeout()])
        adapter = BacnetAdapter(self.network, self.logger, sock=fake_socket)

        with self.assertRaises(BacnetCommunicationError):
            adapter.write_bool(self.registry.get(GRID_LOCKOUT_CHANNEL), True)

    def test_read_ignores_stale_simple_ack_before_value_response(self) -> None:
        fake_socket = FakeSocket(
            [
                make_ack_response(invoke_id=99),
                make_read_response_for_point(3.5, invoke_id=1, instance=300),
            ]
        )
        adapter = BacnetAdapter(self.network, self.logger, sock=fake_socket)

        value = adapter.read_float(self.registry.get(GRID_ACTIVE_POWER_CHANNEL))

        self.assertEqual(value, 3.5)

    def test_read_ignores_response_for_wrong_object_instance(self) -> None:
        fake_socket = FakeSocket(
            [
                make_read_response_for_point(0.0, invoke_id=1, instance=300),
                make_read_response_for_point(13.58, invoke_id=1, instance=1000),
            ]
        )
        adapter = BacnetAdapter(self.network, self.logger, sock=fake_socket)

        value = adapter.read_float(self.registry.get(CURRENT_PRICE_CHANNEL))

        self.assertEqual(value, 13.58)

    def test_read_accepts_point_specific_controller_sender(self) -> None:
        registry = ChannelRegistry.from_points_config(
            PointsConfig(
                grid_active_power_kw=300,
                current_price_av=1000,
                grid_lockout_bv=400,
                spotmarket_lockout_bv=401,
            ),
            additional_inputs={
                "site.outdoor_temperature_c": AdditionalInputConfig(
                    channel_id="site.outdoor_temperature_c",
                    object_type=0,
                    instance=1801,
                    description="Outdoor temperature",
                    controller_ip="192.168.1.200",
                    controller_port=47808,
                )
            },
        )
        fake_socket = FakeSocket(
            [
                make_read_response_for_point(
                    22.5,
                    invoke_id=1,
                    instance=1801,
                    object_type=0,
                    sender_ip="192.168.1.200",
                ),
            ]
        )
        adapter = BacnetAdapter(self.network, self.logger, sock=fake_socket)

        value = adapter.read_float(registry.get("site.outdoor_temperature_c"))

        self.assertEqual(value, 22.5)
        self.assertEqual(fake_socket.sent_packets[0][1], ("192.168.1.200", 47808))


class SimulationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.logger = logging.getLogger("mini_ems.runtime.test.simulation")
        self.logger.handlers.clear()
        self.logger.addHandler(logging.NullHandler())
        self.registry = ChannelRegistry.from_points_config(
            PointsConfig(
                grid_active_power_kw=300,
                current_price_av=1000,
                grid_lockout_bv=400,
                spotmarket_lockout_bv=401,
            )
        )

    def test_simulated_bacnet_reads_values_and_confirms_writes_without_ack(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            values_path = Path(temp_dir) / "sample_values.json"
            values_path.write_text(
                json.dumps(
                    {
                        "channels": {
                            GRID_ACTIVE_POWER_CHANNEL: 4.2,
                            CURRENT_PRICE_CHANNEL: 1.0,
                        }
                    }
                ),
                encoding="utf-8",
            )
            adapter = SimulatedBacnetAdapter(values_path, self.logger)

            value = adapter.read_float(self.registry.get(GRID_ACTIVE_POWER_CHANNEL))
            confirmation = adapter.write_with_confirmation(
                self.registry.get(CURRENT_PRICE_CHANNEL),
                -0.25,
                "ack_or_readback",
            )

            self.assertEqual(value, 4.2)
            self.assertTrue(confirmation.confirmed)
            self.assertFalse(confirmation.ack_received)
            self.assertEqual(confirmation.confirmation_source, "simulated")
            self.assertEqual(adapter.read_float(self.registry.get(CURRENT_PRICE_CHANNEL)), -0.25)

    def test_simulated_price_service_writes_dashboard_cache(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            prices_path = temp_path / "sample_prices.json"
            cache_path = temp_path / "spotmarket_price_cache.json"
            prices_path.write_text(
                json.dumps(
                    {
                        "default_today_ct_kwh": 12.0,
                        "default_tomorrow_ct_kwh": 10.5,
                        "today_windows": [
                            {"start_slot": 44, "length": 8, "price_ct_kwh": -0.25}
                        ],
                    }
                ),
                encoding="utf-8",
            )
            service = SimulatedSpotmarketPriceService(
                cache_path=cache_path,
                prices_path=prices_path,
                resolution="quarterhour",
                logger=self.logger,
            )

            snapshot = service.refresh()
            cache = json.loads(cache_path.read_text(encoding="utf-8"))

            self.assertEqual(snapshot.price_source_status["provider"], "simulated")
            self.assertEqual(len(snapshot.today_slots), 96)
            self.assertEqual(snapshot.today_slots[44], -0.25)
            self.assertEqual(cache["price_source_status"]["provider"], "simulated")


class SmardPriceProviderTest(unittest.TestCase):
    def test_get_json_uses_stdlib_http(self) -> None:
        provider = SmardPriceProvider(
            PriceSourceConfig(
                provider="smard",
                region="DE-LU",
                filter=4169,
                resolution="quarterhour",
                timeout_seconds=1.0,
                price_factor=0.1,
            )
        )

        with patch("urllib.request.urlopen", return_value=FakeHTTPResponse({"timestamps": [1, 2, 3]})) as urlopen:
            payload = provider._get_json("https://example.test")

        self.assertEqual(payload["timestamps"], [1, 2, 3])
        urlopen.assert_called_once()


class CycleRunnerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.base_dir = Path(self.tmpdir.name)
        self.logger = logging.getLogger("mini_ems.runtime.test.cycle")
        self.logger.handlers.clear()
        self.logger.addHandler(logging.NullHandler())
        self.config = MiniEmsConfig(
            base_dir=self.base_dir,
            network=NetworkConfig(
                controller_ip="192.168.1.100",
                controller_port=47808,
                local_ip="192.168.1.50",
                local_port=47809,
                response_timeout_seconds=0.1,
                retries=0,
            ),
            points=PointsConfig(
                grid_active_power_kw=300,
                current_price_av=1000,
                grid_lockout_bv=400,
                spotmarket_lockout_bv=401,
            ),
            timing=TimingConfig(
                cycle_seconds=1,
                inter_read_delay_seconds=0.0,
            ),
            price_source=PriceSourceConfig(
                provider="smard",
                region="DE-LU",
                filter=4169,
                resolution="quarterhour",
                timeout_seconds=5.0,
                price_factor=0.1,
            ),
            controllers=ControllersConfig(
                grid_lockout=GridLockoutConfig(
                    threshold_kw=5.0,
                    clear_threshold_kw=5.5,
                    below_threshold_cycles_required=3,
                ),
                spotmarket_lockout=SpotMarketLockoutConfig(
                    negative_quarters_min_consecutive=8,
                    min_valid_quarters=96,
                    invalid_price_sentinel=None,
                ),
            ),
            safety=SafetyConfig(
                fail_safe_output=False,
                comm_error_safe_mode_threshold=2,
            ),
            logging=LoggingConfig(
                directory="logs",
                log_file="mini_ems.log",
                state_file="runtime/state.json",
                health_file="runtime/health.json",
                price_cache_file="data/spotmarket/spotmarket_price_cache.json",
                spotmarket_plan_file="data/spotmarket/spotmarket_tomorrow_windows.json",
                spotmarket_override_file="data/spotmarket/spotmarket_manual_override.json",
                level="INFO",
                stdout=False,
            ),
        )
        self.registry = ChannelRegistry.from_points_config(self.config.points, self.config.additional_inputs)

    def test_successful_cycle_writes_current_price(self) -> None:
        fake_socket = FakeSocket(
            [
                make_read_response_for_point(7.2, invoke_id=1, instance=300),
                make_ack_response(invoke_id=2),
                make_ack_response(invoke_id=3),
                make_ack_response(invoke_id=4),
            ]
        )
        runner = self._build_runner(fake_socket)

        snapshot = runner.run_cycle()

        self.assertEqual(snapshot["status"], "healthy")
        self.assertTrue(snapshot["tomorrow_prices_available"])
        self.assertEqual(runner.state.outputs[CURRENT_PRICE_CHANNEL].value, -0.25)
        self.assertFalse(runner.state.outputs["ems.lockout_spotmarket"].value)
        self.assertEqual(snapshot["grid_active_power_kw"], 7.2)
        self.assertFalse(runner.state.outputs[GRID_LOCKOUT_CHANNEL].value)

    def test_current_price_is_rewritten_for_each_new_slot_even_if_value_matches(self) -> None:
        first_snapshot = self._price_snapshot()
        second_snapshot = self._price_snapshot(current_slot_index=47, current_slot_label="11:45")
        fake_socket = FakeSocket(
            [
                make_read_response_for_point(7.2, invoke_id=1, instance=300),
                make_ack_response(invoke_id=2),
                make_ack_response(invoke_id=3),
                make_ack_response(invoke_id=4),
                make_read_response_for_point(7.3, invoke_id=5, instance=300),
                make_ack_response(invoke_id=6),
            ]
        )
        runner = self._build_runner(
            fake_socket,
            price_service=FakePriceService([first_snapshot, second_snapshot]),
        )

        runner.run_cycle()
        snapshot = runner.run_cycle()

        self.assertTrue(snapshot["write_results"][CURRENT_PRICE_CHANNEL]["changed"])
        self.assertEqual(snapshot["watchdog"]["last_price_handoff_key"], "2026-04-01/11:45")
        self.assertEqual(runner.state.health.last_price_handoff_value_ct_kwh, -0.25)

    def test_write_failure_triggers_safe_mode(self) -> None:
        fake_socket = FakeSocket(
            [
                make_read_response_for_point(7.2, invoke_id=1, instance=300),
                socket.timeout(),
            ]
        )
        runner = self._build_runner(fake_socket)

        snapshot = runner.run_cycle()

        self.assertEqual(snapshot["status"], "safe_mode")
        self.assertIn("write_failure", snapshot["safe_mode_reason"])
        self.assertIn("ems.lockout_grid", snapshot["desired_outputs"])

    def test_implausible_grid_read_triggers_safe_mode_via_point_bounds(self) -> None:
        grid_point = self.registry.get(GRID_ACTIVE_POWER_CHANNEL)
        self.assertIsNotNone(grid_point.plausible_max)
        out_of_range = grid_point.plausible_max + 1.0
        fake_socket = FakeSocket(
            [
                make_read_response_for_point(out_of_range, invoke_id=1, instance=300),
            ]
        )
        runner = self._build_runner(fake_socket)

        snapshot = runner.run_cycle()

        self.assertEqual(snapshot["status"], "safe_mode")
        self.assertIn("grid_read", snapshot["safe_mode_reason"])
        self.assertEqual(
            snapshot["input_reads"][GRID_ACTIVE_POWER_CHANNEL]["status"], "warning"
        )
        self.assertFalse(snapshot["input_reads"][GRID_ACTIVE_POWER_CHANNEL]["plausible"])

    def test_spotmarket_bv_is_written_even_if_price_write_fails(self) -> None:
        override_path = self.config.spotmarket_override_path
        override_path.parent.mkdir(parents=True, exist_ok=True)
        override_path.write_text(
            json.dumps(
                {
                    "enabled": True,
                    "date": "2026-04-01",
                    "windows": [
                        {
                            "start_label": "11:30",
                            "end_label_exclusive": "11:45",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        fake_socket = FakeSocket(
            [
                make_read_response_for_point(7.2, invoke_id=1, instance=300),
                make_ack_response(invoke_id=2),
                make_ack_response(invoke_id=3),
                socket.timeout(),
                make_read_response_for_point(999.0, invoke_id=5, instance=1000),
            ]
        )
        runner = self._build_runner(fake_socket)

        snapshot = runner.run_cycle()

        self.assertEqual(snapshot["status"], "degraded")
        self.assertTrue(runner.state.outputs["ems.lockout_spotmarket"].value)
        self.assertTrue(snapshot["desired_outputs"]["ems.lockout_spotmarket"])
        self.assertEqual(
            snapshot["write_results"]["ems.lockout_spotmarket"]["confirmed_value"],
            True,
        )
        self.assertIn("Failed to confirm tariff.current_price_ct_kwh", snapshot["degraded_reason"])

    def test_price_service_failure_triggers_safe_mode(self) -> None:
        fake_socket = FakeSocket([])
        runner = self._build_runner(
            fake_socket,
            price_service=FakePriceService(error=PriceProviderError("api down")),
        )

        snapshot = runner.run_cycle()

        self.assertEqual(snapshot["status"], "safe_mode")
        self.assertIn("api down", snapshot["safe_mode_reason"])

    def test_price_cache_falls_back_to_cached_current_slot_when_smard_is_unavailable(self) -> None:
        today = berlin_now().date()
        tomorrow = today.fromordinal(today.toordinal() + 1)

        class ProviderStub:
            def __init__(self):
                self.config = type("Config", (), {"resolution": "quarterhour", "provider": "smard"})()

            def current_slot_index(self, _now_local):
                return 12

            def slot_label(self, slot_index):
                hour = slot_index // 4
                minute = (slot_index % 4) * 15
                return f"{hour:02d}:{minute:02d}"

            def scan_recent_slot_maps(self, _target_dates):
                raise PriceProviderError("vpn offline")

        cache_path = self.base_dir / "spotmarket_price_cache.json"
        cache = PriceCacheFile(
            last_update_at="2026-04-01T14:05:31+02:00",
            today=CachedDay(date_iso=today.isoformat(), slots=[10.0] * 96),
            tomorrow=CachedDay(date_iso=tomorrow.isoformat(), slots=[11.0] * 96),
        )
        cache_path.write_text(json.dumps(cache.to_dict(), indent=2), encoding="utf-8")

        service = SpotmarketPriceCacheService(cache_path, ProviderStub())
        snapshot = service.refresh()

        self.assertEqual(snapshot.current_price_ct_kwh, 10.0)
        self.assertTrue(snapshot.price_source_status["stale"])
        self.assertEqual(snapshot.price_source_status["fallback"], "cache")

    def test_price_cache_promotes_cached_tomorrow_after_midnight_when_smard_is_unavailable(self) -> None:
        today = berlin_now().date()
        yesterday = today.fromordinal(today.toordinal() - 1)

        class ProviderStub:
            def __init__(self):
                self.config = type("Config", (), {"resolution": "quarterhour", "provider": "smard"})()

            def current_slot_index(self, _now_local):
                return 43

            def slot_label(self, slot_index):
                hour = slot_index // 4
                minute = (slot_index % 4) * 15
                return f"{hour:02d}:{minute:02d}"

            def scan_recent_slot_maps(self, _target_dates):
                raise PriceProviderError("vpn offline")

        cache_path = self.base_dir / "spotmarket_price_cache.json"
        cache = PriceCacheFile(
            last_update_at="2026-04-01T23:55:31+02:00",
            today=CachedDay(date_iso=yesterday.isoformat(), slots=[10.0] * 96),
            tomorrow=CachedDay(date_iso=today.isoformat(), slots=[12.5] * 96),
        )
        cache_path.write_text(json.dumps(cache.to_dict(), indent=2), encoding="utf-8")

        service = SpotmarketPriceCacheService(cache_path, ProviderStub())
        snapshot = service.refresh()

        self.assertEqual(snapshot.today_date_iso, today.isoformat())
        self.assertEqual(snapshot.current_slot_label, "10:45")
        self.assertEqual(snapshot.current_price_ct_kwh, 12.5)
        self.assertTrue(snapshot.price_source_status["stale"])
        self.assertEqual(snapshot.price_source_status["fallback"], "cache")

    def test_cache_file_name_is_operator_readable(self) -> None:
        self.assertEqual(self.config.price_cache_path.name, "spotmarket_price_cache.json")
        self.assertEqual(self.config.spotmarket_plan_path.name, "spotmarket_tomorrow_windows.json")

    def test_tomorrow_is_not_marked_available_when_all_slots_are_empty(self) -> None:
        today = berlin_now().date()
        tomorrow = today.fromordinal(today.toordinal() + 1)

        class ProviderStub:
            def __init__(self):
                self.config = type("Config", (), {"resolution": "quarterhour", "provider": "smard"})()

            def current_slot_index(self, _now_local):
                return 56

            def slot_label(self, slot_index):
                hour = slot_index // 4
                minute = (slot_index % 4) * 15
                return f"{hour:02d}:{minute:02d}"

            def scan_recent_slot_maps(self, _target_dates):
                return RecentSlotMapScanResult(
                    slot_maps_by_date={
                        today.isoformat(): {},
                        tomorrow.isoformat(): {},
                    },
                    raw_slot_counts_by_date={today.isoformat(): 96},
                    first_local_timestamp=f"{today.isoformat()}T00:00:00+02:00",
                    last_local_timestamp=f"{today.isoformat()}T23:45:00+02:00",
                    scanned_block_timestamps=[1, 2, 3],
                )

        cache_path = self.base_dir / "spotmarket_price_cache.json"
        cache = PriceCacheFile(
            last_update_at="2026-04-01T14:05:31+02:00",
            today=CachedDay(date_iso=today.isoformat(), slots=[1.0] * 96),
            tomorrow=CachedDay(date_iso=tomorrow.isoformat(), slots=[None] * 96),
        )
        cache_path.write_text(json.dumps(cache.to_dict(), indent=2), encoding="utf-8")

        service = SpotmarketPriceCacheService(cache_path, ProviderStub())
        snapshot = service.refresh()

        self.assertFalse(snapshot.tomorrow_prices_available)
        self.assertEqual(snapshot.tomorrow_available_slot_count, 0)
        self.assertEqual(snapshot.price_source_status["provider"], "smard")
        self.assertEqual(snapshot.price_source_status["today_slots_found"], 0)
        self.assertEqual(snapshot.price_source_status["tomorrow_slots_found"], 0)

    def test_manual_override_switches_spotmarket_bv_on(self) -> None:
        override_path = self.config.spotmarket_override_path
        override_path.parent.mkdir(parents=True, exist_ok=True)
        override_path.write_text(
            json.dumps(
                {
                    "enabled": True,
                    "date": "2026-04-01",
                    "windows": [
                        {
                            "start_label": "11:30",
                            "end_label_exclusive": "11:45",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        fake_socket = FakeSocket(
            [
                make_read_response_for_point(7.2, invoke_id=1, instance=300),
                make_ack_response(invoke_id=2),
                make_ack_response(invoke_id=3),
                make_ack_response(invoke_id=4),
            ]
        )
        runner = self._build_runner(fake_socket)

        snapshot = runner.run_cycle()

        self.assertEqual(snapshot["spotmarket_source"], "manual_override")
        self.assertTrue(snapshot["spotmarket_active_now"])
        self.assertTrue(runner.state.outputs["ems.lockout_spotmarket"].value)

    def test_current_price_readback_confirmation_keeps_cycle_healthy(self) -> None:
        fake_socket = FakeSocket(
            [
                make_read_response_for_point(7.2, invoke_id=1, instance=300),
                make_ack_response(invoke_id=2),
                make_ack_response(invoke_id=3),
                socket.timeout(),
                make_read_response_for_point(-0.25, invoke_id=5, instance=1000),
            ]
        )
        runner = self._build_runner(fake_socket)

        snapshot = runner.run_cycle()

        self.assertEqual(snapshot["status"], "healthy")
        self.assertEqual(
            snapshot["write_results"][CURRENT_PRICE_CHANNEL]["confirmation_source"],
            "readback",
        )
        self.assertEqual(
            snapshot["watchdog"]["last_price_handoff_value_ct_kwh"],
            -0.25,
        )

    def test_current_price_confirmation_failure_marks_cycle_degraded(self) -> None:
        fake_socket = FakeSocket(
            [
                make_read_response_for_point(7.2, invoke_id=1, instance=300),
                make_ack_response(invoke_id=2),
                make_ack_response(invoke_id=3),
                socket.timeout(),
                make_read_response_for_point(4.0, invoke_id=5, instance=1000),
            ]
        )
        runner = self._build_runner(fake_socket)

        snapshot = runner.run_cycle()

        self.assertEqual(snapshot["status"], "degraded")
        self.assertFalse(snapshot["safe_mode_active"])
        self.assertIn("readback mismatch", snapshot["degraded_reason"])

    def test_grid_lockout_reactivates_after_stable_av300_reads(self) -> None:
        fake_socket = FakeSocket(
            [
                make_read_response_for_point(4.9, invoke_id=1, instance=300),
                make_ack_response(invoke_id=2),
                make_ack_response(invoke_id=3),
                make_ack_response(invoke_id=4),
                make_read_response_for_point(4.8, invoke_id=5, instance=300),
                make_read_response_for_point(4.7, invoke_id=6, instance=300),
                make_ack_response(invoke_id=7),
            ]
        )
        runner = self._build_runner(
            fake_socket,
            price_service=FakePriceService(
                [
                    self._price_snapshot(),
                    self._price_snapshot(),
                    self._price_snapshot(),
                ]
            ),
        )

        runner.run_cycle()
        runner.run_cycle()
        snapshot = runner.run_cycle()

        self.assertEqual(snapshot["status"], "healthy")
        self.assertTrue(snapshot["desired_outputs"][GRID_LOCKOUT_CHANNEL])
        self.assertTrue(runner.state.outputs[GRID_LOCKOUT_CHANNEL].value)
        self.assertEqual(snapshot["controller_outcomes"]["grid_lockout"]["state_name"], "lockout_active")

    def test_runtime_database_contains_cycle_history(self) -> None:
        fake_socket = FakeSocket(
            [
                make_read_response_for_point(7.2, invoke_id=1, instance=300),
                make_ack_response(invoke_id=2),
                make_ack_response(invoke_id=3),
                make_ack_response(invoke_id=4),
            ]
        )
        runner = self._build_runner(fake_socket)

        snapshot = runner.run_cycle()
        db = RuntimeDatabase(self.config.database_path)
        report = db.get_daily_report(snapshot["today_date"])

        self.assertGreaterEqual(report["cycle_count"], 1)
        self.assertIn("healthy", report["status_counts"])
        self.assertGreaterEqual(report["price_ct_kwh"]["slot_count"], 1)

    def test_output_channels_are_available_as_rollups_for_reports(self) -> None:
        fake_socket = FakeSocket(
            [
                make_read_response_for_point(7.2, invoke_id=1, instance=300),
                make_ack_response(invoke_id=2),
                make_ack_response(invoke_id=3),
                make_ack_response(invoke_id=4),
            ]
        )
        runner = self._build_runner(fake_socket)

        runner.run_cycle()
        db = RuntimeDatabase(self.config.database_path)
        history = db.get_channel_history(CURRENT_PRICE_CHANNEL, limit=1, granularity="5m")

        self.assertEqual(history[0]["channel_id"], CURRENT_PRICE_CHANNEL)
        self.assertEqual(history[0]["sample_count"], 1)
        self.assertEqual(history[0]["last_value"], -0.25)

    def test_objectlist_import_records_selected_report_points(self) -> None:
        csv_path = self.base_dir / "objectlist.csv"
        csv_path.write_text(
            "\n".join(
                [
                    '"Object Reference",Alarm,Manual,Commissioned,Name,Value,Status,Description',
                    '//Engie_Stuttgart_EM/3000.AI1101,,,1,NLS02_PUF_01_T_oben_IW,"79.2 C",,"Puffer 1 Temperatur oben"',
                    '//Engie_Stuttgart_EM/3000.AV300,,,1,EMS_Netzleistung,"12.5 kW",out-of-service,""',
                ]
            ),
            encoding="utf-8",
        )
        db = RuntimeDatabase(self.config.database_path)

        count = import_objectlist_snapshot(
            db,
            csv_path,
            timestamp="2026-04-01T10:00:00Z",
            cycle_id="objectlist-test",
        )
        history = db.get_channel_history("site.buffer_1_top_temperature_c", limit=1)
        grid_history = db.get_channel_history("grid.active_power_kw", limit=1)

        self.assertEqual(count, 1)
        self.assertEqual(history[0]["value"], 79.2)
        self.assertEqual(grid_history, [])

    def test_energy_counters_are_reported_as_period_delta(self) -> None:
        db = RuntimeDatabase(self.config.database_path)
        db.record_external_channel_samples(
            [
                {"channel_id": "site.chp_electric_energy_kwh", "value": 1000.0},
                {"channel_id": "site.chp_thermal_energy_kwh", "value": 2000.0},
                {"channel_id": "site.pellet_thermal_energy_kwh", "value": 3000.0},
                {"channel_id": "site.gas_thermal_energy_kwh", "value": 4000.0},
            ],
            cycle_id="energy-start",
            timestamp="2026-04-01T00:00:00Z",
        )
        db.record_external_channel_samples(
            [
                {"channel_id": "site.chp_electric_energy_kwh", "value": 1012.5},
                {"channel_id": "site.chp_thermal_energy_kwh", "value": 2025.0},
                {"channel_id": "site.pellet_thermal_energy_kwh", "value": 3030.0},
                {"channel_id": "site.gas_thermal_energy_kwh", "value": 4040.0},
            ],
            cycle_id="energy-end",
            timestamp="2026-04-01T12:00:00Z",
        )

        report = db.build_configurable_report(
            {
                "start": "2026-04-01T00:00:00Z",
                "end": "2026-04-02T00:00:00Z",
                "channels": ["site.chp_electric_energy_kwh", "site.gas_thermal_energy_kwh"],
                "sections": [{"component": "summary"}],
            }
        )
        cards = {card["channel_id"]: card for card in report["sections"][0]["cards"]}

        self.assertEqual(cards["site.chp_electric_energy_kwh"]["display_label"], "Erzeugung im Zeitraum")
        self.assertEqual(cards["site.chp_electric_energy_kwh"]["delta"], 12.5)
        self.assertEqual(cards["site.gas_thermal_energy_kwh"]["delta"], 40.0)

    def test_report_html_uses_customer_language(self) -> None:
        db = RuntimeDatabase(self.config.database_path)
        db.record_external_channel_samples(
            [
                {"channel_id": CURRENT_PRICE_CHANNEL, "value": -0.25},
                {"channel_id": "ems.lockout_spotmarket", "value": 1.0},
            ],
            cycle_id="customer-language",
            timestamp="2026-04-01T12:00:00Z",
        )

        html = db.render_report_html(
            {
                "title": "Mini EMS Betriebsbericht",
                "start": "2026-04-01T00:00:00Z",
                "end": "2026-04-02T00:00:00Z",
                "channels": [CURRENT_PRICE_CHANNEL, "ems.lockout_spotmarket"],
                "sections": [{"component": "summary"}, {"component": "table"}],
            }
        )

        self.assertIn("Strompreis", html)
        self.assertIn("Preissteuerung", html)
        self.assertIn("Messpunkte", html)
        self.assertNotIn("Samples", html)
        self.assertNotIn("Spotpreis", html)
        self.assertNotIn("ems.lockout", html)

    def test_health_file_is_compact_operator_snapshot(self) -> None:
        fake_socket = FakeSocket(
            [
                make_read_response_for_point(7.2, invoke_id=1, instance=300),
                make_ack_response(invoke_id=2),
                make_ack_response(invoke_id=3),
                make_ack_response(invoke_id=4),
            ]
        )
        runner = self._build_runner(fake_socket)

        runner.run_cycle()
        health = json.loads(self.config.health_path.read_text(encoding="utf-8"))

        self.assertEqual(health["status"], "healthy")
        self.assertEqual(health["current_price_ct_kwh"], -0.25)
        self.assertEqual(health["grid_read_status"], "ok")
        self.assertNotIn("input_reads", health)
        self.assertNotIn("controller_outcomes", health)
        self.assertNotIn("outputs", health)
        self.assertIn("write_status", health)
        self.assertTrue(health["write_status"]["current_price"]["confirmed"])

    def test_api_status_payload_exposes_price_cache_for_dashboard(self) -> None:
        self.config.health_path.parent.mkdir(parents=True, exist_ok=True)
        self.config.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.config.price_cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.config.spotmarket_plan_path.parent.mkdir(parents=True, exist_ok=True)

        self.config.health_path.write_text(json.dumps({"status": "healthy"}), encoding="utf-8")
        self.config.state_path.write_text(json.dumps({"safe_mode_active": False}), encoding="utf-8")
        self.config.price_cache_path.write_text(
            json.dumps(
                {
                    "last_update_at": "2026-04-01T11:30:00+02:00",
                    "today": {
                        "date": "2026-04-01",
                        "slots": [1.0] * 96,
                    },
                    "tomorrow": {
                        "date": "2026-04-02",
                        "slots": [2.0] * 96,
                    },
                }
            ),
            encoding="utf-8",
        )
        self.config.spotmarket_plan_path.write_text(
            json.dumps({"min_consecutive_quarters": 8, "today": {"date": "2026-04-01", "windows": []}}),
            encoding="utf-8",
        )

        api_server = MiniEmsApiServer(
            api_config=self.config.api,
            runtime_db=RuntimeDatabase(self.config.database_path),
            health_path=self.config.health_path,
            state_path=self.config.state_path,
            price_cache_path=self.config.price_cache_path,
            spotmarket_plan_path=self.config.spotmarket_plan_path,
            dashboard_dir=self.base_dir / "dashboard",
            logger=self.logger,
            read_diagnostics=None,
        )

        payload = api_server._get_status_payload()

        self.assertEqual(payload["health"]["status"], "healthy")
        self.assertEqual(payload["price_cache"]["today"]["date"], "2026-04-01")
        self.assertEqual(len(payload["price_cache"]["tomorrow"]["slots"]), 96)
        self.assertEqual(payload["spotmarket_settings"]["min_consecutive_quarters"], 8)

    def test_api_updates_spotmarket_duration_and_persists_config(self) -> None:
        config_path = self.base_dir / "config.json"
        config_path.write_text(
            json.dumps(
                {
                    "controllers": {
                        "spotmarket_lockout": {
                            "negative_quarters_min_consecutive": 8,
                            "min_valid_quarters": 96,
                        }
                    }
                }
            ),
            encoding="utf-8",
        )
        writer = SpotmarketPlanWriter(
            self.config.spotmarket_plan_path,
            negative_threshold_ct_kwh=0.0,
            min_consecutive_quarters=8,
        )
        api_server = MiniEmsApiServer(
            api_config=self.config.api,
            runtime_db=RuntimeDatabase(self.config.database_path),
            health_path=self.config.health_path,
            state_path=self.config.state_path,
            price_cache_path=self.config.price_cache_path,
            spotmarket_plan_path=self.config.spotmarket_plan_path,
            dashboard_dir=self.base_dir / "dashboard",
            logger=self.logger,
            read_diagnostics=None,
            config_path=config_path,
            spotmarket_plan_writer=writer,
            price_source_resolution="quarterhour",
        )

        payload = api_server.update_spotmarket_lockout_settings({"min_consecutive_hours": 2.5})
        persisted = json.loads(config_path.read_text(encoding="utf-8"))

        self.assertEqual(payload["min_consecutive_quarters"], 10)
        self.assertEqual(writer.min_consecutive_quarters, 10)
        self.assertEqual(
            persisted["controllers"]["spotmarket_lockout"]["negative_quarters_min_consecutive"],
            10,
        )

    def test_additional_input_from_second_controller_is_logged_and_exposed(self) -> None:
        self.config.additional_inputs["site.outdoor_temperature_c"] = AdditionalInputConfig(
            channel_id="site.outdoor_temperature_c",
            object_type=0,
            instance=1801,
            description="Outdoor temperature",
            controller_ip="192.168.1.200",
            controller_port=47808,
            plausible_min=-50.0,
            plausible_max=60.0,
            include_in_health=True,
        )
        fake_socket = FakeSocket(
            [
                make_read_response_for_point(7.2, invoke_id=1, instance=300),
                make_read_response_for_point(
                    14.5,
                    invoke_id=2,
                    instance=1801,
                    object_type=0,
                    sender_ip="192.168.1.200",
                ),
                make_ack_response(invoke_id=3),
                make_ack_response(invoke_id=4),
                make_ack_response(invoke_id=5),
            ]
        )
        runner = self._build_runner(fake_socket)

        snapshot = runner.run_cycle()
        health = json.loads(self.config.health_path.read_text(encoding="utf-8"))
        db = RuntimeDatabase(self.config.database_path)
        history = db.get_channel_history("site.outdoor_temperature_c", limit=1)
        rollup_history = db.get_channel_history("site.outdoor_temperature_c", limit=1, granularity="5m")

        self.assertEqual(snapshot["status"], "healthy")
        self.assertEqual(snapshot["input_reads"]["site.outdoor_temperature_c"]["value"], 14.5)
        self.assertEqual(health["additional_inputs"]["site.outdoor_temperature_c"]["value"], 14.5)
        self.assertEqual(health["additional_inputs"]["site.outdoor_temperature_c"]["status"], "ok")
        self.assertEqual(history[0]["channel_id"], "site.outdoor_temperature_c")
        self.assertEqual(history[0]["value"], 14.5)
        self.assertEqual(rollup_history[0]["channel_id"], "site.outdoor_temperature_c")
        self.assertEqual(rollup_history[0]["sample_count"], 1)
        self.assertEqual(rollup_history[0]["average_value"], 14.5)
        self.assertEqual(rollup_history[0]["last_value"], 14.5)

    def test_value_past_max_age_seconds_is_flagged_stale(self) -> None:
        # A valid read whose timestamp is older than max_age_seconds must become
        # quality=stale and lose its "ok" status (demoted to "warning").
        registry = ChannelRegistry.from_points_config(self.config.points, self.config.additional_inputs)
        fake_socket = FakeSocket(
            [make_read_response_for_point(7.2, invoke_id=1, instance=300)]
        )
        adapter = BacnetAdapter(self.config.network, self.logger, sock=fake_socket)
        captured_at = datetime(2026, 4, 1, 9, 30, 0, tzinfo=timezone.utc)
        # Sample captured at 09:30:00, evaluated 120s later -> older than max_age=60.
        clock = ScriptedClock([captured_at, captured_at + timedelta(seconds=120)])
        service = ChannelReadDiagnosticsService(
            registry=registry,
            adapter=adapter,
            logger=self.logger,
            now=clock,
        )

        diagnostic = service.read_float_channel(
            GRID_ACTIVE_POWER_CHANNEL,
            samples=1,
            max_age_seconds=60.0,
        )

        self.assertEqual(diagnostic.quality, QUALITY_STALE)
        self.assertEqual(diagnostic.status, "warning")
        self.assertEqual(diagnostic.value, 7.2)
        self.assertAlmostEqual(diagnostic.age_seconds, 120.0)
        self.assertEqual(diagnostic.max_age_seconds, 60.0)
        self.assertEqual(diagnostic.to_dict()["quality"], QUALITY_STALE)

    def test_fresh_value_within_max_age_seconds_is_good(self) -> None:
        registry = ChannelRegistry.from_points_config(self.config.points, self.config.additional_inputs)
        fake_socket = FakeSocket(
            [make_read_response_for_point(7.2, invoke_id=1, instance=300)]
        )
        adapter = BacnetAdapter(self.config.network, self.logger, sock=fake_socket)
        captured_at = datetime(2026, 4, 1, 9, 30, 0, tzinfo=timezone.utc)
        clock = ScriptedClock([captured_at, captured_at + timedelta(seconds=5)])
        service = ChannelReadDiagnosticsService(
            registry=registry,
            adapter=adapter,
            logger=self.logger,
            now=clock,
        )

        diagnostic = service.read_float_channel(
            GRID_ACTIVE_POWER_CHANNEL,
            samples=1,
            max_age_seconds=60.0,
        )

        self.assertEqual(diagnostic.quality, QUALITY_GOOD)
        self.assertEqual(diagnostic.status, "ok")

    def test_failed_read_quality_is_bad(self) -> None:
        registry = ChannelRegistry.from_points_config(self.config.points, self.config.additional_inputs)
        fake_socket = FakeSocket([socket.timeout()])
        adapter = BacnetAdapter(self.config.network, self.logger, sock=fake_socket)
        service = ChannelReadDiagnosticsService(
            registry=registry,
            adapter=adapter,
            logger=self.logger,
        )

        diagnostic = service.read_float_channel(
            GRID_ACTIVE_POWER_CHANNEL,
            samples=1,
            max_age_seconds=60.0,
        )

        self.assertEqual(diagnostic.quality, QUALITY_BAD)
        self.assertEqual(diagnostic.status, "error")
        self.assertIsNone(diagnostic.age_seconds)

    def test_stale_additional_input_is_warned_but_not_safe_mode(self) -> None:
        # Documented policy: a stale ADDITIONAL input surfaces as quality=stale in
        # health/input_reads but does NOT escalate the cycle to safe_mode.
        self.config.additional_inputs["site.outdoor_temperature_c"] = AdditionalInputConfig(
            channel_id="site.outdoor_temperature_c",
            object_type=0,
            instance=1801,
            description="Outdoor temperature",
            controller_ip="192.168.1.200",
            controller_port=47808,
            plausible_min=-50.0,
            plausible_max=60.0,
            include_in_health=True,
            max_age_seconds=30.0,
        )
        fake_socket = FakeSocket(
            [
                make_read_response_for_point(7.2, invoke_id=1, instance=300),
                make_read_response_for_point(
                    14.5,
                    invoke_id=2,
                    instance=1801,
                    object_type=0,
                    sender_ip="192.168.1.200",
                ),
                make_ack_response(invoke_id=3),
                make_ack_response(invoke_id=4),
                make_ack_response(invoke_id=5),
            ]
        )
        base = datetime(2026, 4, 1, 9, 30, 0, tzinfo=timezone.utc)
        # The clock advances by 90s on every call; the additional input is read
        # second, so by the time its age is evaluated it is well past max_age=30.
        clock = ScriptedClock([base + timedelta(seconds=90 * i) for i in range(8)])
        runner = self._build_runner(fake_socket, now=clock)

        snapshot = runner.run_cycle()
        health = json.loads(self.config.health_path.read_text(encoding="utf-8"))
        additional = health["additional_inputs"]["site.outdoor_temperature_c"]

        # Not escalated to safe_mode (additional input policy).
        self.assertNotEqual(snapshot["status"], "safe_mode")
        # But observably stale in both the snapshot input_reads and health payload.
        self.assertEqual(
            snapshot["input_reads"]["site.outdoor_temperature_c"]["quality"],
            QUALITY_STALE,
        )
        self.assertEqual(additional["quality"], QUALITY_STALE)
        self.assertEqual(additional["max_age_seconds"], 30.0)
        self.assertEqual(additional["status"], "warning")

    def test_stale_heartbeat_flags_stale_runtime_when_watchdog_configured(self) -> None:
        # A configured watchdog turns an old heartbeat into an explicit stale_runtime
        # alarm in the health payload, without touching safe_mode/control logic.
        self.config = replace(
            self.config,
            watchdog=WatchdogConfig(max_cycle_age_seconds=120.0),
        )
        fake_socket = FakeSocket([])
        runner = self._build_runner(fake_socket)
        # Baseline: runtime is not in safe_mode. The watchdog must not change this.
        runner.state.health.safe_mode_active = False
        runner.state.health.safe_mode_reason = None
        # Simulate a hung runtime: the persisted heartbeat is far older than "now".
        runner.state.health.last_cycle_at = "2026-04-01T09:30:00Z"
        runner.state.health.last_healthy_at = "2026-04-01T09:30:00Z"
        # Evaluate 5 minutes later -> well past the 120s liveness threshold.
        runner.read_diagnostics._now = lambda: datetime(2026, 4, 1, 9, 35, 0, tzinfo=timezone.utc)

        watchdog = runner._watchdog_snapshot()
        health = runner._build_health_payload({"watchdog": watchdog})

        self.assertTrue(watchdog["stale_runtime"])
        self.assertEqual(watchdog["runtime_status"], "stale_runtime")
        self.assertAlmostEqual(watchdog["last_cycle_age_seconds"], 300.0)
        self.assertEqual(health["runtime_status"], "stale_runtime")
        self.assertTrue(health["stale_runtime"])
        self.assertEqual(health["max_cycle_age_seconds"], 120.0)
        # The watchdog only reports; it must not flip the runtime into safe_mode.
        self.assertFalse(runner.state.health.safe_mode_active)

    def test_stale_heartbeat_without_watchdog_config_does_not_alarm(self) -> None:
        # Default behaviour is unchanged: without max_cycle_age_seconds the watchdog
        # stays observational and never emits a stale_runtime alarm, even if old.
        fake_socket = FakeSocket([])
        runner = self._build_runner(fake_socket)
        self.assertIsNone(self.config.watchdog.max_cycle_age_seconds)
        runner.state.health.last_cycle_at = "2026-04-01T09:30:00Z"
        runner.state.health.last_healthy_at = "2026-04-01T09:30:00Z"
        runner.read_diagnostics._now = lambda: datetime(2026, 4, 1, 10, 30, 0, tzinfo=timezone.utc)

        watchdog = runner._watchdog_snapshot()
        health = runner._build_health_payload({"watchdog": watchdog})

        self.assertFalse(watchdog["stale_runtime"])
        self.assertEqual(watchdog["runtime_status"], "live")
        self.assertFalse(health["stale_runtime"])
        self.assertEqual(health["runtime_status"], "live")

    def _build_runner(self, fake_socket: FakeSocket, price_service=None, now=None) -> CycleRunner:
        registry = ChannelRegistry.from_points_config(self.config.points, self.config.additional_inputs)
        adapter = BacnetAdapter(self.config.network, self.logger, sock=fake_socket)
        state_store = StateStore(self.config.state_path, registry.output_channel_ids())
        return CycleRunner(
            config=self.config,
            registry=registry,
            adapter=adapter,
            state_store=state_store,
            logger=self.logger,
            price_service=price_service or FakePriceService([self._price_snapshot()]),
            spotmarket_plan_writer=SpotmarketPlanWriter(
                self.config.spotmarket_plan_path,
                negative_threshold_ct_kwh=0.0,
                min_consecutive_quarters=self.config.controllers.spotmarket_lockout.negative_quarters_min_consecutive,
            ),
            spotmarket_override_store=SpotmarketManualOverrideStore(
                self.config.spotmarket_override_path,
            ),
            read_diagnostics=ChannelReadDiagnosticsService(
                registry=registry,
                adapter=adapter,
                logger=self.logger,
                now=now,
            ),
            runtime_db=RuntimeDatabase(self.config.database_path),
        )

    def _price_snapshot(self, current_slot_index=46, current_slot_label="11:30"):
        return PublishedPriceSnapshot(
            current_price_ct_kwh=-0.25,
            current_slot_index=current_slot_index,
            current_slot_label=current_slot_label,
            today_date_iso="2026-04-01",
            today_available_slot_count=96,
            today_slots=[1.0] * 96,
            tomorrow_date_iso="2026-04-02",
            tomorrow_prices_available=True,
            tomorrow_available_slot_count=96,
            tomorrow_slots=[1.0] * 96,
            cache_path=str(self.base_dir / "spotmarket_price_cache.json"),
            last_update_at="2026-04-01T11:30:00+02:00",
            price_source_status={
                "provider": "smard",
                "resolution": "quarterhour",
                "today_date": "2026-04-01",
                "today_slots_found": 96,
                "today_complete": True,
                "tomorrow_date": "2026-04-02",
                "tomorrow_slots_found": 96,
                "tomorrow_complete": True,
                "first_local_timestamp": "2026-04-01T00:00:00+02:00",
                "last_local_timestamp": "2026-04-02T23:45:00+02:00",
                "scanned_block_count": 10,
            },
        )


if __name__ == "__main__":
    unittest.main()
