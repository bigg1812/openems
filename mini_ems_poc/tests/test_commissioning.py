import json
import logging
import tempfile
import unittest
from pathlib import Path

from mini_ems_poc.mini_ems_runtime.commissioning import CommissioningService, CommissioningStore
from mini_ems_poc.mini_ems_runtime.config import validate_raw_config
from mini_ems_poc.mini_ems_runtime.identity import IdentityStore, IdentityUser
from mini_ems_poc.mini_ems_runtime.protocol import WriteConfirmation
from mini_ems_poc.tests.test_config_api import make_raw_config


class FakeAdapter:
    def __init__(self, readback=None, write_confirmed=True):
        self.readback = readback
        self.write_confirmed = write_confirmed
        self.writes = []
        self.relinquishes = []

    def write_with_confirmation(self, point, desired_value, confirmation_mode):
        self.writes.append((point, desired_value, confirmation_mode))
        return WriteConfirmation(
            channel_id=point.channel_id,
            confirmed=self.write_confirmed,
            ack_received=self.write_confirmed,
            confirmation_mode=confirmation_mode,
            confirmation_source="ack" if self.write_confirmed else None,
            desired_value=desired_value,
            attempts=1,
            error=None if self.write_confirmed else "no ack",
        )

    def read_float(self, point):
        if self.readback is None:
            raise RuntimeError("no readback")
        return float(self.readback)

    def relinquish_with_confirmation(self, point, confirmation_mode):
        self.relinquishes.append((point, confirmation_mode))
        return WriteConfirmation(
            channel_id=point.channel_id,
            confirmed=True,
            ack_received=True,
            confirmation_mode=confirmation_mode,
            confirmation_source="ack",
            desired_value=None,
            attempts=1,
        )

    def close(self):
        pass


class FakeTimer:
    created = []

    def __init__(self, seconds, callback):
        self.seconds = seconds
        self.callback = callback
        self.daemon = False
        self.cancelled = False
        self.__class__.created.append(self)

    def start(self):
        pass

    def cancel(self):
        self.cancelled = True


class CommissioningTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.base_dir = Path(self.tmpdir.name)
        self.identity = IdentityStore(self.base_dir)
        self.store = CommissioningStore(self.identity.path)
        self.admin = IdentityUser("admin-id", "admin", "Admin", "admin", True, 0)
        self.viewer = IdentityUser("viewer-id", "viewer", "Viewer", "viewer", True, 0)
        self.raw = make_raw_config()
        self.raw["api"]["read_only"] = False
        self.config = validate_raw_config(self.raw, base_dir=self.base_dir)
        self.logger = logging.getLogger("mini_ems.runtime.test.commissioning")
        FakeTimer.created = []

    def service(self, adapter=None, config=None):
        return CommissioningService(
            store=self.store,
            identity_store=self.identity,
            adapter=adapter or FakeAdapter(),
            config=config or self.config,
            logger=self.logger,
            timer_factory=FakeTimer,
        )

    def approve(self, service):
        return service.approve(
            {
                "name": "EMS_TEST_AUSSENTEMPERATUR",
                "controller_ip": "192.168.244.10",
                "controller_port": 47808,
                "object_type": "bv",
                "instance": 200,
                "write_priority": 14,
            },
            self.admin,
        )["point"]

    def test_only_admin_can_approve_ems_named_safe_priority(self) -> None:
        service = self.service()
        with self.assertRaises(PermissionError):
            service.approve({"name": "EMS_TEST", "controller_ip": "10.0.0.1", "object_type": "bv", "instance": 1}, self.viewer)
        with self.assertRaisesRegex(ValueError, "EMS_"):
            service.approve({"name": "TEST", "controller_ip": "10.0.0.1", "object_type": "bv", "instance": 1}, self.admin)
        with self.assertRaisesRegex(ValueError, "Schutzfunktionen"):
            service.approve({"name": "EMS_TEST", "controller_ip": "10.0.0.1", "object_type": "bv", "instance": 1, "write_priority": 5}, self.admin)

        point = self.approve(service)

        self.assertTrue(point["enabled"])
        self.assertEqual(point["write_priority"], 14)

        with self.assertRaisesRegex(ValueError, "bereits"):
            service.approve(
                {
                    "name": "EMS_TEST_AUSSENTEMPERATUR",
                    "controller_ip": "192.168.244.10",
                    "object_type": "bv",
                    "instance": 201,
                },
                self.admin,
            )

    def test_runtime_owned_output_cannot_be_approved_twice(self) -> None:
        service = self.service()

        with self.assertRaisesRegex(ValueError, "laufenden Mini-EMS-Regelung"):
            service.approve(
                {
                    "name": "EMS_BESTEHENDER_AUSGANG",
                    "controller_ip": self.config.network.controller_ip,
                    "controller_port": self.config.network.controller_port,
                    "object_type": "bv",
                    "instance": self.config.points.spotmarket_lockout_bv,
                    "write_priority": 14,
                },
                self.admin,
            )

    def test_bv_test_writes_reads_back_and_automatically_relinquishes(self) -> None:
        adapter = FakeAdapter(readback=0)
        service = self.service(adapter)
        point = self.approve(service)

        result = service.start_test({"point_id": point["id"], "value": False}, self.admin)

        self.assertTrue(result["started"])
        self.assertTrue(result["effective"])
        self.assertEqual(result["lease"]["status"], "active")
        self.assertEqual(adapter.writes[0][0].write_priority, 14)
        self.assertEqual(FakeTimer.created[0].seconds, 10)

        FakeTimer.created[0].callback()

        lease = self.store.latest_lease(point["id"])
        self.assertEqual(lease["status"], "released")
        self.assertEqual(len(adapter.relinquishes), 1)

    def test_mismatching_readback_reports_higher_priority(self) -> None:
        adapter = FakeAdapter(readback=1)
        service = self.service(adapter)
        point = self.approve(service)

        result = service.start_test({"point_id": point["id"], "value": False}, self.admin)

        self.assertFalse(result["effective"])
        self.assertIn("höhere BACnet-Priorität", result["message"])

    def test_read_only_mode_blocks_start_but_not_approval(self) -> None:
        raw = make_raw_config()
        raw["api"]["read_only"] = True
        config = validate_raw_config(raw, base_dir=self.base_dir)
        service = self.service(config=config)
        point = self.approve(service)

        with self.assertRaisesRegex(PermissionError, "Anlagenaktionen sind gesperrt"):
            service.start_test({"point_id": point["id"], "value": False}, self.admin)

    def test_unfinished_write_is_released_after_restart(self) -> None:
        first_adapter = FakeAdapter(readback=0)
        first = self.service(first_adapter)
        point = self.approve(first)
        first.start_test({"point_id": point["id"], "value": False}, self.admin)
        restart_adapter = FakeAdapter()
        restarted = self.service(restart_adapter)

        restarted.recover_unfinished()

        self.assertEqual(self.store.latest_lease(point["id"])["status"], "released")
        self.assertEqual(len(restart_adapter.relinquishes), 1)

    def test_failed_ack_triggers_best_effort_relinquish(self) -> None:
        adapter = FakeAdapter(write_confirmed=False)
        service = self.service(adapter)
        point = self.approve(service)

        with self.assertRaisesRegex(RuntimeError, "no ack"):
            service.start_test({"point_id": point["id"], "value": False}, self.admin)

        self.assertEqual(self.store.latest_lease(point["id"])["status"], "failed")
        self.assertEqual(len(adapter.relinquishes), 1)


if __name__ == "__main__":
    unittest.main()
