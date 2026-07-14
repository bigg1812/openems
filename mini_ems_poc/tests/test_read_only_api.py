"""Tests fuer den read-only Netzwerkmodus der HTTP-API (Roadmap H5).

Setzt die Endpunkt-Einstufung aus HOSTING_SICHERHEIT.md Abschnitt 2.1 durch:

- api.read_only Default False -> Verhalten unveraendert (Bestandssuite deckt das ab;
  hier zusaetzlich explizit geprueft, dass POST- und diagnostics/read-Pfade nicht 403 sind).
- api.read_only True -> Anlagenaktionen und GET /api/diagnostics/read liefern
  403. Der UI-Konfigurationspfad bleibt für eine Admin-Sitzung erreichbar.
- Anmeldung, Rollenverwaltung und BACnet-Inbetriebnahme sind vollständig
  inventarisiert. Admin-Sitzungen ersetzen den früheren Freigabecode-Header.
- ReadOnlyGuardStructuralTest scannt do_POST in http_api.py und stellt sicher,
  dass jeder dort verdrahtete POST-Pfad in dieser Testliste vorkommt, damit
  kuenftige neue Endpunkte nicht unbemerkt an der Sperre vorbeirutschen.

Die Tests laufen gegen einen echten HTTP-Server auf 127.0.0.1 mit ephemerem Port,
damit die zentrale Sperre im Request-Handling (do_GET/do_POST) real durchlaufen wird.
"""

import http.client
import json
import logging
import re
import socket
import tempfile
import unittest
from pathlib import Path
from typing import Dict, Optional


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]

from mini_ems_poc.mini_ems_runtime import http_api as http_api_module
from mini_ems_poc.mini_ems_runtime.config import validate_raw_config
from mini_ems_poc.mini_ems_runtime.http_api import MiniEmsApiServer
from mini_ems_poc.mini_ems_runtime.identity import IdentityStore
from mini_ems_poc.mini_ems_runtime.runtime_db import RuntimeDatabase
from mini_ems_poc.mini_ems_runtime.site_store import SiteConfigStore
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
    ("GET", "/theme-init.js", False),
    ("GET", "/api/auth/status", False),
    ("GET", "/api/health", False),
    ("GET", "/api/auth/users", False),
    ("GET", "/api/auth/events", False),
    ("GET", "/api/bacnet/write-points", False),
    ("GET", "/api/status", False),
    ("GET", "/api/config/spotmarket-lockout", False),
    ("GET", "/api/config/site", False),
    ("GET", "/api/config/changes", False),
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
    # Anlagen-/Bedienaktionen bleiben gesperrt
    ("POST", "/api/config/spotmarket-lockout", True),
    # Anmeldung, Verwaltung und Konfigurationsfluss bleiben erreichbar.
    ("POST", "/api/auth/bootstrap", False),
    ("POST", "/api/auth/login", False),
    ("POST", "/api/auth/logout", False),
    ("POST", "/api/auth/users/create", False),
    ("POST", "/api/auth/users/update", False),
    ("POST", "/api/bacnet/write-points/approve", False),
    ("POST", "/api/bacnet/write-points/revoke", False),
    ("POST", "/api/bacnet/write-test/start", True),
    ("POST", "/api/bacnet/write-test/release", False),
    ("POST", "/api/config/site/validate", False),
    ("POST", "/api/config/site/save", False),
    ("POST", "/api/config/mapping/preview", False),
    ("POST", "/api/report/preview", True),
    # Config-Editor-Pipeline (S5/S6, seit Commit e5417edd2 hinzugekommen):
    ("POST", "/api/config/pointlist/import", False),
    ("POST", "/api/config/discovery/bacnet/preview", True),
    ("POST", "/api/config/mapping/activate", False),
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
        self.site_store = SiteConfigStore(self.base_dir)
        self.logger = logging.getLogger("mini_ems.runtime.test.read_only_api")
        self.logger.handlers.clear()
        self.logger.addHandler(logging.NullHandler())

        self.bootstrap_code = "test-bootstrap-code-for-read-only"
        raw = make_raw_config(config_admin_token=self.bootstrap_code)
        raw["api"]["read_only"] = self.read_only
        # Freier Port: damit aufeinanderfolgende Testserver nicht auf 8090 kollidieren.
        raw["api"]["port"] = _free_port()
        self.site_store.save_revision(raw, action="site.bootstrap", actor="test")
        config = validate_raw_config(raw, base_dir=self.base_dir)
        self.identity_store = IdentityStore(self.base_dir)
        session = self.identity_store.bootstrap_admin(
            bootstrap_code=self.bootstrap_code,
            expected_code=self.bootstrap_code,
            username="admin",
            display_name="Test Admin",
            password="sicheres-testpasswort",
        )
        self.admin_cookie = "mini_ems_session={0}".format(session.token)

        # Minimaler Dashboard-Ordner + Zustandsdateien, damit die Freigabeliste
        # echte Antworten statt 404 liefert.
        dashboard_dir = self.base_dir / "dashboard"
        dashboard_dir.mkdir(parents=True, exist_ok=True)
        (dashboard_dir / "index.html").write_text("<html>ok</html>", encoding="utf-8")
        (dashboard_dir / "dashboard.css").write_text("/* ok */", encoding="utf-8")
        (dashboard_dir / "dashboard.js").write_text("// ok", encoding="utf-8")
        (dashboard_dir / "theme-init.js").write_text("// ok", encoding="utf-8")
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
            site_store=self.site_store,
            identity_store=self.identity_store,
        )
        self.server.start()
        self.addCleanup(self.server.stop)
        self.host = self.server._server.server_address[0]
        self.port = self.server._server.server_address[1]

    def _request(
        self,
        method: str,
        path: str,
        headers: Optional[Dict[str, str]] = None,
        payload: Optional[Dict[str, object]] = None,
        authenticated: bool = True,
    ):
        connection = http.client.HTTPConnection(self.host, self.port, timeout=5)
        try:
            body = json.dumps(payload or {}) if method == "POST" else None
            request_headers = {"Content-Type": "application/json"} if method == "POST" else {}
            if authenticated:
                request_headers["Cookie"] = self.admin_cookie
            if headers:
                request_headers.update(headers)
            connection.request(method, path, body=body, headers=request_headers)
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

    def test_status_exposes_app_version(self) -> None:
        # Additives Softwareversion-Feld (H2): im Testbetrieb ohne VERSION-Datei
        # liefert der Server die dev-Variante mit den erwarteten Schluesseln.
        status, raw = self._request("GET", "/api/status")
        self.assertEqual(status, 200)
        payload = json.loads(raw.decode("utf-8"))
        self.assertIn("app_version", payload)
        self.assertEqual(payload["app_version"]["version"], "dev")
        self.assertIn("git_commit", payload["app_version"])
        self.assertIn("build_date", payload["app_version"])

    def test_gate_never_fires_when_read_only_off(self) -> None:
        # Standard-Verhalten unveraendert: bei Default off darf die zentrale
        # Read-only-Sperre auf keinem der im read-only Modus gesperrten Pfade
        # ausloesen. Ein Endpunkt kann aus anderen Gruenden 403 liefern (z. B.
        # fehlende/ungültige Nutzdaten) - entscheidend ist, dass es nicht der
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
                _status, raw = self._request(method, path)
                payload = {}
                try:
                    payload = json.loads(raw.decode("utf-8"))
                except (UnicodeDecodeError, ValueError):
                    pass
                self.assertNotEqual(
                    payload.get("error"),
                    "read_only_mode",
                    "{0} {1} must not hit the read-only gate".format(method, path),
                )

    def test_sample_allowlist_endpoints_ok(self) -> None:
        for path in ("/api/status", "/api/health", "/api/report/daily", "/dashboard"):
            with self.subTest(path=path):
                status, _ = self._request("GET", path)
                self.assertEqual(status, 200)

    def test_dashboard_access_is_logged_without_personal_client_data(self) -> None:
        with self.assertLogs(self.logger, level=logging.INFO) as captured:
            status, _ = self._request("GET", "/dashboard")

        self.assertEqual(status, 200)
        event = json.loads(captured.output[-1].split(":", 2)[-1])
        self.assertEqual(event["event"], "ui.accessed")
        self.assertEqual(event["access_mode"], "read_only")
        self.assertNotIn("client_ip", event)
        self.assertNotIn("user", event)


class ReadOnlyAllowsAuthenticatedUiConfigurationTest(ReadOnlyApiTestBase):
    """Der UI-Konfigurationspfad bleibt mit einer Admin-Sitzung erreichbar."""

    read_only = True

    def _assert_reaches_admin_handler(self, path: str) -> None:
        status, raw = self._request("POST", path)
        self.assertEqual(status, 200, "{0} should reach its authenticated handler".format(path))
        payload = json.loads(raw.decode("utf-8"))
        self.assertNotEqual(payload.get("error"), "read_only_mode")

    def test_auth_status_accepts_session_cookie(self) -> None:
        status, raw = self._request("GET", "/api/auth/status")
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(raw.decode("utf-8"))["authenticated"])

    def test_auth_status_rejects_missing_session(self) -> None:
        status, raw = self._request("GET", "/api/auth/status", authenticated=False)
        self.assertEqual(status, 200)
        self.assertFalse(json.loads(raw.decode("utf-8"))["authenticated"])

    def test_mapping_activate_reaches_handler_with_admin_session(self) -> None:
        self._assert_reaches_admin_handler("/api/config/mapping/activate")

    def test_site_save_reaches_handler_with_admin_session(self) -> None:
        self._assert_reaches_admin_handler("/api/config/site/save")


class ReadOnlyGuardStructuralTest(unittest.TestCase):
    """Struktureller Waechter gegen kuenftige Testluecken.

    Scannt den do_POST-Quelltext in http_api.py nach 'parsed.path == "..."'
    und stellt sicher, dass jeder dort gefundene POST-Pfad in der read-only
    Testliste (BLOCKED_ENDPOINTS oben) vorkommt. Legt jemand einen neuen
    schreibenden/aktiven POST-Endpunkt an, ohne die Read-only-Testliste (und
    HOSTING_SICHERHEIT.md Abschnitt 2.1) zu pflegen, schlaegt dieser Test fehl
    - unabhaengig davon, dass die deny-by-default Sperre den Endpunkt zur
    Laufzeit ohnehin schon sperrt.
    """

    def test_every_do_post_path_is_covered_by_read_only_test_list(self) -> None:
        source = Path(http_api_module.__file__).read_text(encoding="utf-8")
        post_start = source.index("def do_POST")
        post_end = source.index("def log_message", post_start)
        post_body = source[post_start:post_end]

        found_paths = set(re.findall(r'parsed\.path == "([^"]+)"', post_body))
        self.assertTrue(
            found_paths,
            "Regex fand keine POST-Pfade in do_POST - Struktur von http_api.py hat "
            "sich veraendert, Waechter-Regex in test_read_only_api.py anpassen.",
        )

        covered_paths = {path for (method, path, _blocked) in API_ENDPOINTS if method == "POST"}
        missing = found_paths - covered_paths
        self.assertFalse(
            missing,
            "Neue(r) POST-Endpunkt(e) ohne Read-only-Testabdeckung: {0}. Bitte in "
            "API_ENDPOINTS (test_read_only_api.py) und HOSTING_SICHERHEIT.md "
            "Abschnitt 2.1 ergaenzen.".format(sorted(missing)),
        )


if __name__ == "__main__":
    unittest.main()
