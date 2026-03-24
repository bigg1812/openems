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
    ChannelRegistry,
    GRID_LOCKOUT_CHANNEL,
    SPOTMARKET_LOCKOUT_CHANNEL,
)
from mini_ems_poc.mini_ems_runtime.config import (
    ControllersConfig,
    GridLockoutConfig,
    LoggingConfig,
    MiniEmsConfig,
    NetworkConfig,
    PointsConfig,
    SafetyConfig,
    SpotMarketLockoutConfig,
    TimingConfig,
)
from mini_ems_poc.mini_ems_runtime.cycle import CycleRunner
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

    def extend(self, responses):
        self.responses.extend(responses)


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
                spot_price_start_hour_instance=1001,
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

        value = adapter.read_float(self.registry.get("tariff.price_hour_00"))

        self.assertEqual(value, 4.25)
        self.assertEqual(len(fake_socket.sent_packets), 1)

    def test_read_timeout_raises(self) -> None:
        fake_socket = FakeSocket([socket.timeout()])
        adapter = BacnetAdapter(self.network, self.logger, sock=fake_socket)

        with self.assertRaises(BacnetCommunicationError):
            adapter.read_float(self.registry.get("tariff.price_hour_00"))

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
                spot_price_start_hour_instance=1001,
                grid_lockout_bv=400,
                spotmarket_lockout_bv=401,
            ),
            timing=TimingConfig(
                cycle_seconds=1,
                inter_read_delay_seconds=0.0,
            ),
            controllers=ControllersConfig(
                grid_lockout=GridLockoutConfig(
                    threshold_kw=5.0,
                    clear_threshold_kw=5.5,
                    below_threshold_cycles_required=3,
                ),
                spotmarket_lockout=SpotMarketLockoutConfig(
                    negative_hours_min_consecutive=4,
                    min_valid_hours=24,
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
                state_file="state.json",
                health_file="health.json",
                level="INFO",
                stdout=False,
            ),
        )
        self.registry = ChannelRegistry.from_points_config(self.config.points)

    def test_write_failure_does_not_confirm_true_state(self) -> None:
        responses = [make_read_response(3.0)]
        responses.extend(make_read_response(10.0) for _ in range(24))
        responses.append(socket.timeout())
        responses.append(make_ack_response())
        responses.append(make_ack_response())
        fake_socket = FakeSocket(responses)

        runner = self._build_runner(fake_socket)
        runner.state.grid_lockout.below_threshold_counter = 2
        snapshot = runner.run_cycle()

        self.assertEqual(snapshot["status"], "safe_mode")
        self.assertTrue(runner.state.health.safe_mode_active)
        self.assertFalse(runner.state.outputs[GRID_LOCKOUT_CHANNEL].value)
        self.assertTrue(runner.state.outputs[GRID_LOCKOUT_CHANNEL].is_confirmed)
        self.assertIn("write_failure", runner.state.health.safe_mode_reason)

    def test_safe_mode_recovers_after_communication_returns(self) -> None:
        fake_socket = FakeSocket([socket.timeout()])
        runner = self._build_runner(fake_socket)

        first = runner.run_cycle()
        self.assertEqual(first["status"], "safe_mode")
        self.assertTrue(runner.state.health.safe_mode_active)

        fake_socket.extend([make_read_response(50.0)])
        fake_socket.extend(make_read_response(5.0) for _ in range(24))
        fake_socket.extend([make_ack_response(), make_ack_response()])

        second = runner.run_cycle()
        self.assertEqual(second["status"], "healthy")
        self.assertFalse(runner.state.health.safe_mode_active)
        self.assertEqual(runner.state.health.consecutive_comm_errors, 0)

    def _build_runner(self, fake_socket: FakeSocket) -> CycleRunner:
        adapter = BacnetAdapter(self.config.network, self.logger, sock=fake_socket)
        state_store = StateStore(self.config.state_path, self.registry.output_channel_ids())
        return CycleRunner(
            config=self.config,
            registry=self.registry,
            adapter=adapter,
            state_store=state_store,
            logger=self.logger,
        )


if __name__ == "__main__":
    unittest.main()
