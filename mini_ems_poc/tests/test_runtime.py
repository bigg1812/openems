import json
import logging
import socket
import struct
import tempfile
import unittest
from pathlib import Path

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
    ControllersConfig,
    GridLockoutConfig,
    LoggingConfig,
    MiniEmsConfig,
    NetworkConfig,
    PointsConfig,
    PriceSourceConfig,
    SafetyConfig,
    SpotMarketLockoutConfig,
    TimingConfig,
)
from mini_ems_poc.mini_ems_runtime.cycle import CycleRunner
from mini_ems_poc.mini_ems_runtime.price_cache import CachedDay, PriceCacheFile, PublishedPriceSnapshot, SpotmarketPriceCacheService
from mini_ems_poc.mini_ems_runtime.price_provider_smard import PriceProviderError, RecentSlotMapScanResult, berlin_now
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


def make_read_response(value: float):
    payload = b"\x00\x3E\x44" + struct.pack(">f", value) + b"\x3F\x00"
    return payload, ("192.168.1.100", 47808)


def make_ack_response():
    payload = bytes([0, 0, 0, 0, 0, 0, 0x20, 0x00, 0x0F])
    return payload, ("192.168.1.100", 47808)


def make_wrong_sender_response(value: float):
    payload = b"\x00\x3E\x44" + struct.pack(">f", value) + b"\x3F\x00"
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
                make_read_response(4.25),
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
        self.registry = ChannelRegistry.from_points_config(self.config.points)

    def test_successful_cycle_writes_current_price(self) -> None:
        fake_socket = FakeSocket([make_ack_response(), make_ack_response()])
        runner = self._build_runner(fake_socket)

        snapshot = runner.run_cycle()

        self.assertEqual(snapshot["status"], "healthy")
        self.assertTrue(snapshot["tomorrow_prices_available"])
        self.assertEqual(runner.state.outputs[CURRENT_PRICE_CHANNEL].value, -0.25)
        self.assertFalse(runner.state.outputs["ems.lockout_spotmarket"].value)

    def test_write_failure_triggers_safe_mode(self) -> None:
        fake_socket = FakeSocket([socket.timeout()])
        runner = self._build_runner(fake_socket)

        snapshot = runner.run_cycle()

        self.assertEqual(snapshot["status"], "safe_mode")
        self.assertIn("write_failure", snapshot["safe_mode_reason"])

    def test_price_service_failure_triggers_safe_mode(self) -> None:
        fake_socket = FakeSocket([])
        runner = self._build_runner(
            fake_socket,
            price_service=FakePriceService(error=PriceProviderError("api down")),
        )

        snapshot = runner.run_cycle()

        self.assertEqual(snapshot["status"], "safe_mode")
        self.assertIn("api down", snapshot["safe_mode_reason"])

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
        fake_socket = FakeSocket([make_ack_response(), make_ack_response()])
        runner = self._build_runner(fake_socket)

        snapshot = runner.run_cycle()

        self.assertEqual(snapshot["spotmarket_source"], "manual_override")
        self.assertTrue(snapshot["spotmarket_active_now"])
        self.assertTrue(runner.state.outputs["ems.lockout_spotmarket"].value)

    def _build_runner(self, fake_socket: FakeSocket, price_service=None) -> CycleRunner:
        adapter = BacnetAdapter(self.config.network, self.logger, sock=fake_socket)
        state_store = StateStore(self.config.state_path, self.registry.output_channel_ids())
        return CycleRunner(
            config=self.config,
            registry=self.registry,
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
        )

    def _price_snapshot(self):
        return PublishedPriceSnapshot(
            current_price_ct_kwh=-0.25,
            current_slot_index=46,
            current_slot_label="11:30",
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
