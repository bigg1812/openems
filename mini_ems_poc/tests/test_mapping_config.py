import unittest

from mini_ems_poc.mini_ems_runtime.mapping_config import build_mapping_config_patch


def sample_mapping_draft():
    return {
        "devices": [
            {
                "id": "ebcon_1",
                "name": "EBCON Heizzentrale",
                "protocol": "bacnet",
                "host": "192.168.1.20",
                "port": 47808,
            }
        ],
        "raw_points": [
            {
                "id": "bacnet:ebcon_1:av:300",
                "device_id": "ebcon_1",
                "object_type": "analog-value",
                "instance": 300,
                "name": "Main Meter Power",
                "unit": "kW",
            },
            {
                "id": "bacnet:ebcon_1:ai:1801",
                "device_id": "ebcon_1",
                "object_type": "ai",
                "instance": 1801,
                "name": "Outdoor temperature",
                "unit": "C",
            },
        ],
        "mappings": [
            {
                "channel_id": "grid.active_power_kw",
                "source_point_id": "bacnet:ebcon_1:av:300",
                "label": "Netzleistung",
                "access": "read",
                "plausible_min": -1000.0,
                "plausible_max": 1000.0,
                "max_age_seconds": 120,
            },
            {
                "channel_id": "site.outdoor_temperature_c",
                "source_point_id": "bacnet:ebcon_1:ai:1801",
                "label": "Außentemperatur",
                "access": "read",
                "plausible_min": -30.0,
                "plausible_max": 60.0,
                "max_age_seconds": 120,
                "include_in_health": True,
            },
        ],
    }


class MappingConfigTest(unittest.TestCase):
    def test_builds_runtime_patch_from_mapping_draft(self) -> None:
        result = build_mapping_config_patch(sample_mapping_draft())

        self.assertTrue(result["valid"])
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["patch"]["network"]["controller_ip"], "192.168.1.20")
        self.assertEqual(result["patch"]["points"]["grid_active_power_kw"], 300)
        additional = result["patch"]["additional_inputs"][0]
        self.assertEqual(additional["channel_id"], "site.outdoor_temperature_c")
        self.assertEqual(additional["protocol"], "bacnet")
        self.assertEqual(additional["object_type"], "ai")
        self.assertEqual(additional["instance"], 1801)
        self.assertEqual(additional["description"], "Außentemperatur")
        self.assertTrue(additional["include_in_health"])

    def test_rejects_core_channel_with_wrong_object_type(self) -> None:
        draft = sample_mapping_draft()
        draft["raw_points"][0]["object_type"] = "ai"

        result = build_mapping_config_patch(draft)

        self.assertFalse(result["valid"])
        self.assertIn("Netzleistung", " / ".join(result["errors"]))
        self.assertIn("BACnet-AV-Datenpunkt", " / ".join(result["errors"]))

    def test_rejects_unsupported_protocol_before_runtime_config_generation(self) -> None:
        draft = sample_mapping_draft()
        draft["devices"][0]["protocol"] = "modbus_tcp"

        result = build_mapping_config_patch(draft)

        self.assertFalse(result["valid"])
        self.assertIn("noch nicht unterstütztes Protokoll", " / ".join(result["errors"]))

    def test_warns_when_core_channel_transform_cannot_be_applied_yet(self) -> None:
        draft = sample_mapping_draft()
        draft["mappings"][0]["scale"] = 0.001

        result = build_mapping_config_patch(draft)

        self.assertTrue(result["valid"])
        self.assertIn("Umrechnung", " / ".join(result["warnings"]))
        self.assertIn("noch nicht angewendet", " / ".join(result["warnings"]))

    def test_rejects_duplicate_channel_mapping(self) -> None:
        draft = sample_mapping_draft()
        draft["mappings"].append(dict(draft["mappings"][1]))

        result = build_mapping_config_patch(draft)

        self.assertFalse(result["valid"])
        self.assertIn("mehrfach zugeordnet", " / ".join(result["errors"]))


if __name__ == "__main__":
    unittest.main()
