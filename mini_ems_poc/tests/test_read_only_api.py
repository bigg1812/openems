"""Tests fuer den read-only Netzwerkmodus der HTTP-API (Roadmap H5).

Setzt die Endpunkt-Einstufung aus HOSTING_SICHERHEIT.md Abschnitt 2.1 durch:

- api.read_only Default False -> Verhalten unveraendert (Bestandssuite deckt das ab;
  hier zusaetzlich explizit geprueft, dass POST- und diagnostics/read-Pfade nicht 403 sind).
- api.read_only True -> alle nicht-GET-Methoden und GET /api/diagnostics/read
  liefern 403 mit deutschem JSON-Fehlerkoerper; die read-only Freigabeliste bleibt erreichbar.

Die Tests laufen gegen einen echten HTTP-Server auf 127.0.0.1 mit ephemerem Port,
damit die zentrale Sperre im Request-Handling (do_GET/do_POST) real durchlaufen wird.
"""

import http.client
import json
import logging
import socket
import tempfile
import unittest
from pathlib import Path


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]

from mini_ems_poc.mini_ems_runtime.config import validate_raw_config
from mini_ems_poc.mini_ems_runtime.http_api import MiniEmsApiServer
from mini_ems_poc.mini_ems_runtime.runtime_db import RuntimeDatabase
from mini_ems_poc.tests.test_config_api import make_raw_config


# Vollstaendiges Endpunkt-Inventar (Methode, Pfad) aus http_api.py, abgeglichen
# gegen HOSTING_SICHERHEIT.md 2.1. blocked=True bedeutet: im read-only Modus 403.
API_ENDPOINTS = [
    # Read-only Freigabeliste (2.1)
    ("GET", "/", False),
    ("GET", "/dashboard", False),
    ("GET", "/index.html", False),
    ("GET", "/dashboard.css", False),
    ("GET", "/dashboard.js", False),
    ("GET", "/api/status", False),
    ("GET", "/api/config/spotmarket-lockout", False),
    ("GET", "/api/config/site", False),
    ("GET", "/api/spotmarket/windows", False),
    ("GET", "/api/history", False),
    ("GET", "/api/cycles", False),
    ("GET", "/api/report/daily", False),
    ("GET", "/api/report/daily.csv", False),
    ("GET", "/api/report/studio", False),
    ("GET", "/api/report/html", False),
    ("GET", "/api/report/pdf", False),
    ("GET", "/api/weather", False),
    # Aktiver Anlagen-Read: trotz GET gesperrt (2.1)
    ("GET", "/api/diagnostics/read", True),
    # Alle POST-Endpunkte: deny-by-default gesperrt
    ("POST", "/api/config/spotmarket-lockout", True),
    ("POST", "/api/config/site/validate", True),
    ("POST", "/api/config/site/save", True),
    ("POST", "/api/config/mapping/preview", True),
    ("POST", "/api/report/preview", True),
]

BLOCKED_ENDPOINTS = [(m, p) for (m, p, blocked) in API_ENDPOINTS if blocked]
# Endpunkte mit ausgehendem Netzzugriff bzw. optionaler Fremd-Abhaengigkeit
# (Wetterdienst / PDF-Renderer); fuer die offline/deterministische Erreichbarkeits-
# Stichprobe ausgenommen. Ihre Read-only-Einstufung (Freigabe) aendert sich dadurch nicht.
_LIVE_DEPENDENT_PATHS = frozenset({"/api/weather", "/api/report/pdf"})
NON_BLOCKED_ENDPOINTS = [
    (m, p)
    for (m, p, blocked) in API_ENDPOINTS
    if not blocked and p not in _LIVE_DEPENDENT_PATHS
]


class ReadOnlyApiTestBase(unittest.TestCase):
    read_only = False

    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.base_dir = Path(self.tmpdir.name)
        self.config_path = self.base_dir / "config.json"
        self.logger = logging.getLogger("mini_ems.runtime.test.read_only_api")
        self.logger.handlers.clear()
        self.logger.addHandler(logging.NullHandler())

        raw = make_raw_config()
        raw["api"]["read_only"] = self.read_only
        # Freier Port: damit aufeinanderfolgende Testserver nicht auf 8090 kollidieren.
        raw["api"]["port"] = _free_port()
        self.config_path.write_text(json.dumps(raw, indent=2), encoding="utf-8")
        config = validate_raw_config(raw, base_dir=self.base_dir)

        # Minimaler Dashboard-Ordner + Zustandsdateien, damit die Freigabeliste
        # echte Antworten statt 404 liefert.
        dashboard_dir = self.base_dir / "dashboard"
        dashboard_dir.mkdir(parents=True, exist_ok=True)
        (dashboard_dir / "index.html").write_text("<html>ok</html>", encoding="utf-8")
        (dashboard_dir / "dashboard.css").write_text("/* ok */", encoding="utf-8")
        (dashboard_dir / "dashboard.js").write_text("// ok", encoding="utf-8")
        for path, payload in (
            (config.health_path, {"status": "healthy", "today_date": "2026-04-01"}),
            (config.state_path, {"safe_mode_active": False}),
            (config.price_cache_path, {}),
            (config.spotmarket_plan_path, {"min_consecutive_quarters": 8}),
        ):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(payload), encoding="utf-8")

        self.server = MiniEmsApiServer(
            api_config=config.api,
            runtime_db=RuntimeDatabase(config.database_path),
            health_path=config.health_path,
            state_path=config.state_path,
            price_cache_path=config.price_cache_path,
            spotmarket_plan_path=config.spotmarket_plan_path,
            dashboard_dir=dashboard_dir,
            logger=self.logger,
            read_diagnostics=None,
            config_path=self.config_path,
        )
        self.server.start()
        self.addCleanup(self.server.stop)
        self.host = self.server._server.server_address[0]
        self.port = self.server._server.server_address[1]

    def _request(self, method: str, path: str):
        connection = http.client.HTTPConnection(self.host, self.port, timeout=5)
        try:
            body = "{}" if method == "POST" else None
            headers = {"Content-Type": "application/json"} if method == "POST" else {}
            connection.request(method, path, body=body, headers=headers)
            response = connection.getresponse()
            raw = response.read()
            return response.status, raw
        finally:
            connection.close()


class ReadOnlyDefaultOffTest(ReadOnlyApiTestBase):
    read_only = False

    def test_status_field_defaults_to_false(self) -> None:
        status, raw = self._request("GET", "/api/status")
        self.assertEqual(status, 200)
        payload = json.loads(raw.decode("utf-8"))
        self.assertIn("api_read_only", payload)
        self.assertFalse(payload["api_read_only"])

    def test_gate_never_fires_when_read_only_off(self) -> None:
        # Standard-Verhalten unveraendert: bei Default off darf die zentrale
        # Read-only-Sperre auf keinem der im read-only Modus gesperrten Pfade
        # ausloesen. Ein Endpunkt kann aus anderen Gruenden 403 liefern (z. B.
        # site/save ohne Admin-Token) - entscheidend ist, dass es nicht der
        # read_only_mode-Fehler ist.
        for method, path in BLOCKED_ENDPOINTS:
            with self.subTest(method=method, path=path):
                status, raw = self._request(method, path)
                error = None
                if raw:
                    try:
                        error = json.loads(raw.decode("utf-8")).get("error")
                    except (ValueError, UnicodeDecodeError):
                        error = None
                self.assertNotEqual(
                    error,
                    "read_only_mode",
                    "{0} {1} must not hit the read-only gate when off".format(method, path),
                )


class ReadOnlyEnabledTest(ReadOnlyApiTestBase):
    read_only = True

    def test_status_field_true_and_endpoint_reachable(self) -> None:
        status, raw = self._request("GET", "/api/status")
        self.assertEqual(status, 200)
        payload = json.loads(raw.decode("utf-8"))
        self.assertTrue(payload["api_read_only"])

    def test_blocked_endpoints_return_forbidden_with_german_body(self) -> None:
        for method, path in BLOCKED_ENDPOINTS:
            with self.subTest(method=method, path=path):
                status, raw = self._request(method, path)
                self.assertEqual(status, 403, "{0} {1} should be 403".format(method, path))
                payload = json.loads(raw.decode("utf-8"))
                self.assertEqual(payload["error"], "read_only_mode")
                self.assertIn("über den Netzwerkzugriff nicht", payload["message"])

    def test_allowlisted_endpoints_stay_reachable(self) -> None:
        # Stichproben aus der Freigabeliste 2.1 (plus die volle nicht-blockierte
        # Liste), die im read-only Modus weiter funktionieren muessen.
        for method, path in NON_BLOCKED_ENDPOINTS:
            with self.subTest(method=method, path=path):
                status, _ = self._request(method, path)
                self.assertNotEqual(status, 403, "{0} {1} must stay reachable".format(method, path))

    def test_sample_allowlist_endpoints_ok(self) -> None:
        for path in ("/api/status", "/api/report/daily", "/dashboard"):
            with self.subTest(path=path):
                status, _ = self._request("GET", path)
                self.assertEqual(status, 200)


if __name__ == "__main__":
    unittest.main()
