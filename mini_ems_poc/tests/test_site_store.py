import json
import tempfile
import unittest
from pathlib import Path

from mini_ems_poc.mini_ems_runtime.config import validate_raw_config
from mini_ems_poc.mini_ems_runtime.site_store import SiteConfigStore
from mini_ems_poc.mini_ems_runtime.app import _load_or_initialize_site
from mini_ems_poc.tests.test_config_api import make_raw_config


class SiteConfigStoreTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.site_dir = Path(self.tmpdir.name)
        self.store = SiteConfigStore(self.site_dir)

    def test_revision_is_active_and_persisted_without_config_file(self) -> None:
        revision = self.store.save_revision(
            {"site": {"name": "Standort Nord"}, "network": {"controller_ip": "10.0.0.4"}},
            action="site.bootstrap",
            actor="system",
        )

        reopened = SiteConfigStore(self.site_dir)

        self.assertEqual(reopened.active_revision(), revision)
        self.assertEqual(reopened.active_config()["site"]["name"], "Standort Nord")
        self.assertTrue((self.site_dir / "site.sqlite").exists())
        self.assertFalse((self.site_dir / "config.json").exists())

    def test_mapping_revision_keeps_previous_revision_and_draft(self) -> None:
        previous = self.store.save_revision(
            {"network": {"controller_ip": "10.0.0.4"}},
            action="site.bootstrap",
            actor="system",
        )
        current = self.store.save_revision(
            {"network": {"controller_ip": "10.0.0.9"}},
            action="mapping.activate",
            actor="local_admin",
            mapping_draft={"devices": [{"id": "anlage"}]},
            details={"mapping_count": 1},
        )

        self.assertNotEqual(previous, current)
        self.assertEqual(self.store.revision(previous).config["network"]["controller_ip"], "10.0.0.4")
        saved = self.store.revision(current)
        self.assertEqual(saved.mapping_draft["devices"][0]["id"], "anlage")
        self.assertEqual(saved.details["mapping_count"], 1)

    def test_fingerprint_changes_only_with_active_content(self) -> None:
        self.store.save_revision({"value": 1}, action="site.bootstrap", actor="system")
        first = self.store.active_fingerprint()
        self.store.save_revision({"value": 2}, action="site_config.save", actor="local_admin")

        self.assertNotEqual(first, self.store.active_fingerprint())

    def test_empty_site_bootstraps_safe_ui_configuration(self) -> None:
        raw, message = _load_or_initialize_site(self.store, import_config=None)
        config = validate_raw_config(raw, base_dir=self.site_dir)

        self.assertEqual(raw["site"]["name"], "Neuer Standort")
        self.assertEqual(raw["runtime"]["bacnet_mode"], "simulated")
        self.assertFalse(raw["runtime"]["real_writes_enabled"])
        self.assertTrue(raw["api"]["read_only"])
        self.assertTrue(config.simulation_values_path.is_file())
        self.assertTrue(config.simulation_prices_path.is_file())
        self.assertIn("Freigabecode", message)
        self.assertFalse((self.site_dir / "config.json").exists())

    def test_existing_config_is_migrated_once_and_no_longer_active_file(self) -> None:
        legacy_path = self.site_dir / "config.json"
        legacy_path.write_text(json.dumps(make_raw_config("legacy-token")), encoding="utf-8")

        raw, message = _load_or_initialize_site(self.store, import_config=None)

        self.assertEqual(raw["api"]["config_admin_token"], "legacy-token")
        self.assertIn("migriert", message)
        self.assertFalse(legacy_path.exists())
        self.assertEqual(len(list(self.site_dir.glob("config.json.migrated.*.bak"))), 1)


if __name__ == "__main__":
    unittest.main()
