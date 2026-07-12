import json
import logging
import tempfile
import unittest
from pathlib import Path

from mini_ems_poc.mini_ems_runtime.config import validate_raw_config
from mini_ems_poc.mini_ems_runtime.http_api import MiniEmsApiServer
from mini_ems_poc.mini_ems_runtime.site_store import SiteConfigStore
from mini_ems_poc.tests.test_mapping_config import sample_mapping_draft


def make_raw_config(config_admin_token=None):
    raw = {
        "runtime": {
            "environment": "local",
            "bacnet_mode": "simulated",
            "real_writes_enabled": False,
        },
        "network": {
            "controller_ip": "192.168.1.100",
            "controller_port": 47808,
            "local_ip": "127.0.0.1",
            "local_port": 47809,
            "response_timeout_seconds": 0.1,
            "retries": 0,
        },
        "points": {
            "grid_active_power_kw": 300,
            "current_price_av": 1000,
            "grid_lockout_bv": 400,
            "spotmarket_lockout_bv": 401,
        },
        "additional_inputs": [
            {
                "channel_id": "site.outdoor_temperature_c",
                "object_type": "ai",
                "instance": 1801,
                "description": "Outdoor temperature",
                "plausible_min": -30.0,
                "plausible_max": 60.0,
            }
        ],
        "timing": {
            "cycle_seconds": 30,
            "inter_read_delay_seconds": 0.0,
        },
        "price_source": {
            "provider": "smard",
            "region": "DE-LU",
            "filter": 4169,
            "resolution": "quarterhour",
            "timeout_seconds": 5.0,
            "price_factor": 0.1,
        },
        "controllers": {
            "grid_lockout": {
                "threshold_kw": 5.0,
                "clear_threshold_kw": 5.5,
                "below_threshold_cycles_required": 3,
                "enabled": True,
            },
            "spotmarket_lockout": {
                "negative_quarters_min_consecutive": 8,
                "min_valid_quarters": 96,
                "invalid_price_sentinel": None,
            },
        },
        "safety": {
            "fail_safe_output": True,
            "comm_error_safe_mode_threshold": 3,
        },
        "database": {
            "sqlite_file": "data/local/mini_ems.local.sqlite",
        },
        "api": {
            "enabled": True,
            "host": "127.0.0.1",
            "port": 8090,
            "history_default_limit": 96,
        },
        "logging": {
            "directory": "logs/local",
            "log_file": "mini_ems.local.log",
            "state_file": "runtime/local/state.json",
            "health_file": "runtime/local/health.json",
            "price_cache_file": "data/local/spotmarket_price_cache.json",
            "spotmarket_plan_file": "data/local/spotmarket_tomorrow_windows.json",
            "spotmarket_override_file": "data/local/spotmarket_manual_override.json",
            "level": "INFO",
            "stdout": True,
        },
    }
    if config_admin_token is not None:
        raw["api"]["config_admin_token"] = config_admin_token
    return raw


class ConfigApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.base_dir = Path(self.tmpdir.name)
        self.site_store = SiteConfigStore(self.base_dir)
        self.logger = logging.getLogger("mini_ems.runtime.test.config_api")
        self.logger.handlers.clear()
        self.logger.addHandler(logging.NullHandler())

    def _build_server(self, raw):
        if self.site_store.has_active_config():
            self.site_store.save_revision(raw, action="test.reset", actor="test")
        else:
            self.site_store.save_revision(raw, action="site.bootstrap", actor="test")
        return self._build_server_from_existing_store()

    def _build_server_from_existing_store(self):
        raw = self.site_store.active_config()
        config = validate_raw_config(raw, base_dir=self.base_dir)
        return MiniEmsApiServer(
            api_config=config.api,
            runtime_db=None,
            health_path=config.health_path,
            state_path=config.state_path,
            price_cache_path=config.price_cache_path,
            spotmarket_plan_path=config.spotmarket_plan_path,
            dashboard_dir=self.base_dir / "dashboard",
            logger=self.logger,
            read_diagnostics=None,
            site_store=self.site_store,
        )

    def test_validate_accepts_safe_patch_without_saving(self) -> None:
        server = self._build_server(make_raw_config())

        payload = server.validate_site_config_payload({"patch": {"timing": {"cycle_seconds": 60}}})
        persisted = self.site_store.active_config()

        self.assertEqual(payload, {"valid": True})
        self.assertEqual(persisted["timing"]["cycle_seconds"], 30)

    def test_validate_rejects_real_writes_in_local_simulation(self) -> None:
        server = self._build_server(make_raw_config())

        payload = server.validate_site_config_payload({"patch": {"runtime": {"real_writes_enabled": True}}})

        self.assertFalse(payload["valid"])
        self.assertIn("simulated BACnet mode requires real_writes_enabled=false", payload["message"])

    def test_output_policy_accepts_safe_write_priority_and_relinquish_flag(self) -> None:
        raw = make_raw_config()
        raw["outputs"] = {
            "grid_lockout": {
                "confirmation_mode": "ack_only",
                "criticality": "critical",
                "write_priority": 14,
                "relinquish_enabled": True,
            }
        }

        config = validate_raw_config(raw, base_dir=self.base_dir)

        policy = config.output_policies.grid_lockout
        self.assertEqual(policy.write_priority, 14)
        self.assertTrue(policy.relinquish_enabled)

    def test_output_policy_rejects_reserved_write_priority(self) -> None:
        raw = make_raw_config()
        raw["outputs"] = {
            "spotmarket_lockout": {
                "confirmation_mode": "ack_only",
                "criticality": "critical",
                "write_priority": 1,
            }
        }

        with self.assertRaises(ValueError) as context:
            validate_raw_config(raw, base_dir=self.base_dir)

        self.assertIn("reserved protection priorities", str(context.exception))

    def test_ddc_heartbeat_requires_output_policy_when_enabled(self) -> None:
        raw = make_raw_config()
        raw["ddc_heartbeat"] = {
            "enabled": True,
            "object_type": "av",
            "instance": 1200,
            "fallback_timeout_seconds": 180,
        }

        with self.assertRaises(ValueError) as context:
            validate_raw_config(raw, base_dir=self.base_dir)

        self.assertIn("outputs.edge_heartbeat is required", str(context.exception))

    def test_ddc_heartbeat_accepts_counter_point_and_policy(self) -> None:
        raw = make_raw_config()
        raw["ddc_heartbeat"] = {
            "enabled": True,
            "object_type": "av",
            "instance": 1200,
            "fallback_timeout_seconds": 180,
        }
        raw["outputs"] = {
            "edge_heartbeat": {
                "confirmation_mode": "ack_only",
                "criticality": "critical",
                "write_priority": 14,
            }
        }

        config = validate_raw_config(raw, base_dir=self.base_dir)

        self.assertTrue(config.ddc_heartbeat.enabled)
        self.assertEqual(config.ddc_heartbeat.instance, 1200)
        self.assertEqual(config.output_policies.edge_heartbeat.write_priority, 14)

    def test_validate_accepts_additional_input_protocol_and_target_fields(self) -> None:
        server = self._build_server(make_raw_config())

        payload = server.validate_site_config_payload(
            {
                "patch": {
                    "additional_inputs": [
                        {
                            "channel_id": "site.outdoor_temperature_c",
                            "protocol": "bacnet",
                            "object_type": "ai",
                            "instance": 1801,
                            "description": "Outdoor temperature",
                            "controller_ip": "192.168.1.200",
                            "controller_port": 47810,
                            "plausible_min": -30.0,
                            "plausible_max": 60.0,
                            "read_interval_cycles": 2,
                            "max_age_seconds": 180,
                        }
                    ]
                }
            }
        )

        self.assertEqual(payload, {"valid": True})

    def test_validate_still_checks_plausibility_when_point_target_uses_default(self) -> None:
        server = self._build_server(make_raw_config())

        payload = server.validate_site_config_payload(
            {
                "patch": {
                    "additional_inputs": [
                        {
                            "channel_id": "site.outdoor_temperature_c",
                            "protocol": "bacnet",
                            "object_type": "ai",
                            "instance": 1801,
                            "description": "Outdoor temperature",
                            "controller_ip": None,
                            "controller_port": None,
                            "plausible_min": 80.0,
                            "plausible_max": 60.0,
                        }
                    ]
                }
            }
        )

        self.assertFalse(payload["valid"])
        self.assertIn("plausible_min must be <= plausible_max", payload["message"])

    def test_validate_rejects_unsupported_additional_input_protocol(self) -> None:
        server = self._build_server(make_raw_config())

        payload = server.validate_site_config_payload(
            {
                "patch": {
                    "additional_inputs": [
                        {
                            "channel_id": "site.outdoor_temperature_c",
                            "protocol": "mqtt",
                            "object_type": "ai",
                            "instance": 1801,
                            "description": "Outdoor temperature",
                        }
                    ]
                }
            }
        )

        self.assertFalse(payload["valid"])
        self.assertIn("protocol must be one of", payload["message"])

    def test_validate_rejects_modbus_additional_input_without_address_block(self) -> None:
        # protocol=modbus_tcp is supported (S4), but still requires the modbus
        # address block; a bare BACnet-shaped entry must fail clearly.
        server = self._build_server(make_raw_config())

        payload = server.validate_site_config_payload(
            {
                "patch": {
                    "additional_inputs": [
                        {
                            "channel_id": "site.outdoor_temperature_c",
                            "protocol": "modbus_tcp",
                            "object_type": "ai",
                            "instance": 1801,
                            "description": "Outdoor temperature",
                        }
                    ]
                }
            }
        )

        self.assertFalse(payload["valid"])
        self.assertIn("requires a modbus object", payload["message"])

    def test_validate_accepts_modbus_additional_input_with_address_block(self) -> None:
        # S4: protocol=modbus_tcp with a complete modbus block is a valid,
        # read-only alternative to the BACnet path for the same channel shape.
        server = self._build_server(make_raw_config())

        payload = server.validate_site_config_payload(
            {
                "patch": {
                    "additional_inputs": [
                        {
                            "channel_id": "meter.grid.active_power_kw",
                            "protocol": "modbus_tcp",
                            "description": "Hauptzaehler Wirkleistung",
                            "modbus": {
                                "host": "192.168.244.60",
                                "port": 502,
                                "unit_id": 1,
                                "function_code": 3,
                                "register": 19026,
                                "encoding": "float32",
                                "word_order": "big",
                                "scale": 0.001,
                            },
                            "plausible_min": -750.0,
                            "plausible_max": 750.0,
                            "max_age_seconds": 120,
                        }
                    ]
                }
            }
        )

        self.assertEqual(payload, {"valid": True})

    def test_mapping_preview_returns_valid_runtime_config_patch(self) -> None:
        server = self._build_server(make_raw_config())

        payload = server.preview_mapping_config_payload(sample_mapping_draft())

        self.assertTrue(payload["valid"])
        self.assertEqual(payload["errors"], [])
        self.assertEqual(payload["patch"]["network"]["controller_ip"], "192.168.1.20")
        self.assertEqual(payload["patch"]["points"]["grid_active_power_kw"], 300)
        self.assertEqual(
            payload["patch"]["additional_inputs"][0]["channel_id"],
            "site.outdoor_temperature_c",
        )

    def test_pointlist_import_endpoint_builds_mapping_draft(self) -> None:
        server = self._build_server(make_raw_config())

        payload = server.import_pointlist_payload(
            {
                "filename": "datenpunkte.csv",
                "content": "Object Reference;Name;Mini EMS Kanal\n/100.AV300;Netzleistung;grid.active_power_kw\n",
                "default_device": {"host": "192.168.244.10"},
            }
        )

        self.assertTrue(payload["valid"])
        self.assertEqual(payload["mapping_draft"]["raw_points"][0]["id"], "bacnet:device_100:av:300")
        self.assertEqual(payload["mapping_draft"]["mappings"][0]["channel_id"], "grid.active_power_kw")

    def test_mapping_activate_rejects_missing_admin_token(self) -> None:
        server = self._build_server(make_raw_config(config_admin_token="secret-token"))

        with self.assertRaisesRegex(PermissionError, "Freigabecode ist nicht gültig"):
            server.activate_mapping_config_payload(sample_mapping_draft(), admin_token=None)

    def test_mapping_activate_persists_patch_draft_audit_and_previous_revision(self) -> None:
        server = self._build_server(make_raw_config(config_admin_token="secret-token"))

        payload = server.activate_mapping_config_payload(
            sample_mapping_draft(),
            admin_token="secret-token",
        )
        persisted = self.site_store.active_config()
        revision = self.site_store.revision(payload["revision"])

        self.assertTrue(payload["activated"])
        self.assertTrue(payload["valid"])
        self.assertTrue(payload["restart_required"])
        self.assertIsNotNone(payload["previous_revision"])
        self.assertEqual(persisted["network"]["controller_ip"], "192.168.1.20")
        self.assertEqual(persisted["points"]["grid_active_power_kw"], 300)
        self.assertEqual(
            persisted["additional_inputs"][0]["channel_id"],
            "site.outdoor_temperature_c",
        )
        self.assertEqual(revision.mapping_draft, sample_mapping_draft())
        self.assertEqual(revision.action, "mapping.activate")
        self.assertEqual(revision.actor, "local_admin")
        self.assertEqual(revision.details["patch_sections"], ["additional_inputs", "network", "points"])
        self.assertEqual(revision.details["device_count"], 1)
        self.assertEqual(revision.details["mapping_count"], 2)
        validate_raw_config(persisted, base_dir=self.base_dir)

        site = server.get_site_config()
        self.assertTrue(site["restart_required"])
        self.assertTrue(site["mapping_status"]["active"])
        self.assertEqual(site["mapping_status"]["mapping_count"], 2)

    def test_restart_requirement_clears_when_runtime_restarts_with_current_config(self) -> None:
        server = self._build_server(make_raw_config(config_admin_token="secret-token"))
        server.activate_mapping_config_payload(sample_mapping_draft(), admin_token="secret-token")

        restarted_server = self._build_server_from_existing_store()
        site = restarted_server.get_site_config()

        self.assertFalse(site["restart_required"])
        self.assertTrue(site["mapping_status"]["active"])
        self.assertFalse(site["mapping_status"]["restart_required"])

    def test_mapping_activate_does_not_persist_invalid_draft(self) -> None:
        server = self._build_server(make_raw_config(config_admin_token="secret-token"))
        draft = sample_mapping_draft()
        draft["raw_points"][0]["object_type"] = "ai"

        payload = server.activate_mapping_config_payload(draft, admin_token="secret-token")
        persisted = self.site_store.active_config()

        self.assertFalse(payload["activated"])
        self.assertFalse(payload["valid"])
        self.assertIn("BACnet-AV-Datenpunkt", " / ".join(payload["errors"]))
        self.assertEqual(persisted["network"]["controller_ip"], "192.168.1.100")
        self.assertEqual(len(self.site_store.history()), 1)

    def test_site_config_view_strips_admin_token_and_keeps_editable_sections(self) -> None:
        server = self._build_server(make_raw_config(config_admin_token="secret-token"))

        payload = server.get_site_config()

        self.assertTrue(payload["save_enabled"])
        self.assertNotIn("config_admin_token", payload["config"]["api"])
        self.assertIn("runtime", payload["config"])
        self.assertIn("safety", payload["config"])
        self.assertIn("watchdog", payload["config"])
        self.assertIn("additional_inputs", payload["config"])
        self.assertIn("site", payload["editable_sections"])
        self.assertIn("outputs", payload["editable_sections"])
        # Inbetriebnahme-UI (UX14/UX15): aktive Kernadressen sind sichtbar.
        self.assertEqual(payload["config"]["points"]["grid_active_power_kw"], 300)

    def test_site_metadata_is_saved_from_ui_patch(self) -> None:
        server = self._build_server(make_raw_config(config_admin_token="secret-token"))

        response = server.save_site_config_payload(
            {"patch": {"site": {"name": "Werk Nord", "access_status": "restricted", "operator_note": "Pilot"}}},
            admin_token="secret-token",
        )

        self.assertTrue(response["saved"])
        self.assertEqual(self.site_store.active_config()["site"]["name"], "Werk Nord")

    def test_save_is_disabled_without_configured_admin_token(self) -> None:
        server = self._build_server(make_raw_config())

        with self.assertRaisesRegex(PermissionError, "kein Freigabecode eingerichtet"):
            server.save_site_config_payload({"patch": {"timing": {"cycle_seconds": 60}}}, admin_token=None)

    def test_save_rejects_wrong_admin_token(self) -> None:
        server = self._build_server(make_raw_config(config_admin_token="secret-token"))

        with self.assertRaisesRegex(PermissionError, "Freigabecode ist nicht gültig"):
            server.save_site_config_payload(
                {"patch": {"timing": {"cycle_seconds": 60}}},
                admin_token="wrong-token",
            )

    def test_save_with_admin_token_persists_patch_and_keeps_previous_revision(self) -> None:
        server = self._build_server(make_raw_config(config_admin_token="secret-token"))

        payload = server.save_site_config_payload(
            {"patch": {"timing": {"cycle_seconds": 60}}},
            admin_token="secret-token",
        )
        persisted = self.site_store.active_config()
        revision = self.site_store.revision(payload["revision"])
        previous = self.site_store.revision(payload["previous_revision"])

        self.assertTrue(payload["saved"])
        self.assertTrue(payload["valid"])
        self.assertTrue(payload["restart_required"])
        self.assertEqual(persisted["timing"]["cycle_seconds"], 60)
        self.assertEqual(persisted["api"]["config_admin_token"], "secret-token")
        self.assertEqual(persisted["logging"]["state_file"], "runtime/local/state.json")
        self.assertEqual(previous.config["timing"]["cycle_seconds"], 30)
        self.assertEqual(revision.action, "site_config.save")
        self.assertEqual(revision.details["changed_sections"], ["timing"])
        validate_raw_config(persisted, base_dir=self.base_dir)

    def test_change_history_is_latest_first_and_hides_internal_file_names(self) -> None:
        server = self._build_server(make_raw_config(config_admin_token="secret-token"))
        server.activate_mapping_config_payload(sample_mapping_draft(), admin_token="secret-token")
        server.save_site_config_payload(
            {"patch": {"timing": {"cycle_seconds": 60}}},
            admin_token="secret-token",
        )

        payload = server.get_config_changes_payload(limit=10)

        self.assertEqual(len(payload["changes"]), 2)
        self.assertEqual(payload["changes"][0]["title"], "Betriebseinstellungen gespeichert")
        self.assertEqual(payload["changes"][1]["title"], "Datenpunkte aktiviert")
        self.assertIn("2 Zuordnungen", payload["changes"][1]["detail"])
        self.assertEqual(
            set(payload["changes"][0]),
            {"timestamp", "title", "detail", "restart_required"},
        )
        self.assertNotIn("backup_file", payload["changes"][0])
        self.assertNotIn("draft_file", payload["changes"][1])
        self.assertNotIn("action", payload["changes"][0])
        self.assertNotIn("actor", payload["changes"][1])
        self.assertNotIn("revision", payload["changes"][1])

    def test_operator_setting_change_is_added_to_change_history(self) -> None:
        server = self._build_server(make_raw_config())

        server.update_spotmarket_lockout_settings({"min_consecutive_quarters": 6})
        changes = server.get_config_changes_payload()["changes"]

        self.assertEqual(changes[0]["title"], "Preissteuerung angepasst")
        self.assertIn("6 Viertelstunden", changes[0]["detail"])
        self.assertFalse(server.get_site_config()["restart_required"])

    def test_live_operator_setting_does_not_clear_existing_restart_requirement(self) -> None:
        server = self._build_server(make_raw_config(config_admin_token="secret-token"))
        server.activate_mapping_config_payload(sample_mapping_draft(), admin_token="secret-token")

        server.update_spotmarket_lockout_settings({"min_consecutive_quarters": 6})

        self.assertTrue(server.get_site_config()["restart_required"])


if __name__ == "__main__":
    unittest.main()
