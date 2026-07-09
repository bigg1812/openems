"""Tests fuer das Lesen der Softwareversion (H2).

`mini_ems_runtime/resources.py:read_app_version` liest die `VERSION`-Datei, die
im Release-Paket neben dem Executable liegt. Geprueft werden die drei relevanten
Faelle:

- VERSION vorhanden -> version/git_commit/build_date stammen aus der Datei.
- VERSION fehlt (Git-Betrieb) -> version "dev"; git_commit ist entweder ein
  kurzer Hash (falls ermittelbar) oder None, nie ein Fehler.
- VERSION defekt (unlesbar/ohne version=-Zeile) -> version "unbekannt".
"""

import tempfile
import unittest
from pathlib import Path

from mini_ems_poc.mini_ems_runtime.resources import read_app_version


class ReadAppVersionTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _write_version(self, text: str) -> None:
        (self.base / "VERSION").write_text(text, encoding="utf-8")

    def test_version_file_present_is_parsed(self) -> None:
        self._write_version(
            "version=2026.07.1\n"
            "build_date=2026-07-08T08:21:49Z\n"
            "git_commit=3de16bd4eedf\n"
            "platform=Windows-AMD64\n"
        )
        result = read_app_version(self.base)
        self.assertEqual(result["version"], "2026.07.1")
        self.assertEqual(result["git_commit"], "3de16bd4eedf")
        self.assertEqual(result["build_date"], "2026-07-08T08:21:49Z")

    def test_version_file_missing_is_dev(self) -> None:
        result = read_app_version(self.base)
        self.assertEqual(result["version"], "dev")
        self.assertIsNone(result["build_date"])
        # git_commit ist ein kurzer Hash oder None, aber nie ein Fehler.
        self.assertTrue(result["git_commit"] is None or isinstance(result["git_commit"], str))

    def test_version_file_defective_is_unknown(self) -> None:
        # Datei vorhanden, aber ohne verwertbare version=-Zeile.
        self._write_version("kaputt\nnur muell ohne gleichheitszeichen semantik\n")
        result = read_app_version(self.base)
        self.assertEqual(result["version"], "unbekannt")
        self.assertIsNone(result["git_commit"])
        self.assertIsNone(result["build_date"])

    def test_version_file_empty_is_unknown(self) -> None:
        self._write_version("")
        result = read_app_version(self.base)
        self.assertEqual(result["version"], "unbekannt")


if __name__ == "__main__":
    unittest.main()
