"""Protocol-neutral ProtocolAdapter contract test.

Runs the same assertions against every concrete adapter so that any
adapter (BACnet today, Modbus tomorrow) honours the same behavioural
contract. Deterministic and offline:

- The simulated adapter is the primary subject (no I/O at all).
- The real ``BacnetAdapter`` is exercised only on paths that need no
  network round-trip (permission/normalization checks), and even then it
  is constructed with an injected dummy socket so its ``__init__`` never
  opens a real UDP socket.
"""

import json
import logging
import tempfile
import unittest
from pathlib import Path

from mini_ems_poc.mini_ems_runtime.bacnet import BacnetAdapter, BacnetPermissionError
from mini_ems_poc.mini_ems_runtime.channels import (
    CURRENT_PRICE_CHANNEL,
    GRID_ACTIVE_POWER_CHANNEL,
    GRID_LOCKOUT_CHANNEL,
    SPOTMARKET_LOCKOUT_CHANNEL,
    ChannelRegistry,
)
from mini_ems_poc.mini_ems_runtime.config import NetworkConfig, PointsConfig
from mini_ems_poc.mini_ems_runtime.protocol import ProtocolAdapter, WriteConfirmation
from mini_ems_poc.mini_ems_runtime.simulation import SimulatedBacnetAdapter


class DummySocket:
    """Socket stand-in: satisfies BacnetAdapter.__init__ without real I/O.

    Only methods that could be touched before any actual send are provided;
    the contract cases that use the real adapter never reach ``sendto`` /
    ``recvfrom``, so leaving those unimplemented keeps the test honest about
    not performing network I/O.
    """

    def setsockopt(self, *_args):
        return None

    def settimeout(self, _value):
        return None

    def close(self):
        return None


def _make_registry() -> ChannelRegistry:
    return ChannelRegistry.from_points_config(
        PointsConfig(
            grid_active_power_kw=300,
            current_price_av=1000,
            grid_lockout_bv=400,
            spotmarket_lockout_bv=401,
        )
    )


def _make_logger() -> logging.Logger:
    logger = logging.getLogger("mini_ems.runtime.test.contract")
    logger.handlers.clear()
    logger.addHandler(logging.NullHandler())
    return logger


_CONFIRMATION_FIELDS = (
    "confirmed",
    "ack_received",
    "confirmation_mode",
    "confirmation_source",
    "desired_value",
    "attempts",
    "readback_value",
    "error",
)


class AdapterContractTest(unittest.TestCase):
    """Parametrized contract: every adapter must satisfy the same assertions."""

    def setUp(self) -> None:
        self.logger = _make_logger()
        self.registry = _make_registry()
        self._temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp_dir.cleanup)
        values_path = Path(self._temp_dir.name) / "sample_values.json"
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
        self._values_path = values_path

    # -- adapter factories ------------------------------------------------

    def _simulated_adapter(self) -> SimulatedBacnetAdapter:
        return SimulatedBacnetAdapter(self._values_path, self.logger)

    def _real_adapter(self) -> BacnetAdapter:
        network = NetworkConfig(
            controller_ip="192.168.1.100",
            controller_port=47808,
            local_ip="192.168.1.50",
            local_port=47809,
            response_timeout_seconds=0.1,
            retries=0,
        )
        return BacnetAdapter(network, self.logger, sock=DummySocket())

    def _all_adapters(self):
        # (label, factory, exercises_io) — io adapters skip network paths.
        yield "simulated", self._simulated_adapter, True
        yield "bacnet", self._real_adapter, False

    # -- structural conformance ------------------------------------------

    def test_adapters_satisfy_protocol(self) -> None:
        for label, factory, _io in self._all_adapters():
            with self.subTest(adapter=label):
                adapter = factory()
                self.assertIsInstance(adapter, ProtocolAdapter)
                for method in ("read_float", "write_with_confirmation", "close"):
                    self.assertTrue(
                        callable(getattr(adapter, method, None)),
                        "{0} missing {1}".format(label, method),
                    )

    # -- read-permission enforcement -------------------------------------

    def test_read_denied_on_write_only_point(self) -> None:
        # ems.lockout_grid is access="write" — reading it must be denied.
        point = self.registry.get(GRID_LOCKOUT_CHANNEL)
        for label, factory, _io in self._all_adapters():
            with self.subTest(adapter=label):
                adapter = factory()
                with self.assertRaises(BacnetPermissionError):
                    adapter.read_float(point)

    # -- write-permission enforcement ------------------------------------

    def test_write_denied_on_read_only_point(self) -> None:
        # grid.active_power_kw is access="read" — writing it must be denied.
        point = self.registry.get(GRID_ACTIVE_POWER_CHANNEL)
        for label, factory, _io in self._all_adapters():
            with self.subTest(adapter=label):
                adapter = factory()
                with self.assertRaises(BacnetPermissionError):
                    adapter.write_with_confirmation(
                        point=point,
                        desired_value=1.0,
                        confirmation_mode="ack",
                    )

    # -- normalization: AV -> float, BV -> bool --------------------------

    def test_av_write_normalizes_to_float(self) -> None:
        # Only the simulated adapter can confirm a write without network I/O.
        adapter = self._simulated_adapter()
        confirmation = adapter.write_with_confirmation(
            point=self.registry.get(CURRENT_PRICE_CHANNEL),
            desired_value=7,  # int -> must normalize to float
            confirmation_mode="ack_or_readback",
        )
        self.assertTrue(confirmation.confirmed)
        self.assertIsInstance(confirmation.desired_value, float)
        self.assertEqual(confirmation.desired_value, 7.0)
        self.assertEqual(confirmation.readback_value, 7.0)

    def test_bv_write_normalizes_to_bool(self) -> None:
        adapter = self._simulated_adapter()
        confirmation = adapter.write_with_confirmation(
            point=self.registry.get(SPOTMARKET_LOCKOUT_CHANNEL),
            desired_value=1,  # truthy int -> must normalize to bool True
            confirmation_mode="ack",
        )
        self.assertTrue(confirmation.confirmed)
        self.assertIsInstance(confirmation.desired_value, bool)
        self.assertIs(confirmation.desired_value, True)
        # BV has no analog readback.
        self.assertIsNone(confirmation.readback_value)

    # -- confirmation object shape ---------------------------------------

    def test_confirmation_exposes_contract_fields(self) -> None:
        adapter = self._simulated_adapter()
        confirmation = adapter.write_with_confirmation(
            point=self.registry.get(CURRENT_PRICE_CHANNEL),
            desired_value=-0.25,
            confirmation_mode="ack_or_readback",
        )
        self.assertIsInstance(confirmation, WriteConfirmation)
        for field in _CONFIRMATION_FIELDS:
            self.assertTrue(
                hasattr(confirmation, field),
                "confirmation missing attribute {0}".format(field),
            )

        payload = confirmation.to_dict()
        self.assertIsInstance(payload, dict)
        for field in _CONFIRMATION_FIELDS:
            self.assertIn(field, payload)
        self.assertEqual(payload["confirmed"], confirmation.confirmed)
        self.assertEqual(payload["confirmation_mode"], "ack_or_readback")
        self.assertEqual(confirmation.confirmation_source, "simulated")


if __name__ == "__main__":
    unittest.main()
