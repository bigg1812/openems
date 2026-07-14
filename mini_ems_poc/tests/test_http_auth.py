import http.client
import json
import logging
import socket
import tempfile
import unittest
from pathlib import Path
from typing import Dict, Optional

from mini_ems_poc.mini_ems_runtime.config import validate_raw_config
from mini_ems_poc.mini_ems_runtime.commissioning import CommissioningService, CommissioningStore
from mini_ems_poc.mini_ems_runtime.http_api import MiniEmsApiServer
from mini_ems_poc.mini_ems_runtime.identity import IdentityStore
from mini_ems_poc.mini_ems_runtime.runtime_db import RuntimeDatabase
from mini_ems_poc.mini_ems_runtime.site_store import SiteConfigStore
from mini_ems_poc.tests.test_config_api import make_raw_config
from mini_ems_poc.tests.test_commissioning import FakeAdapter, FakeTimer


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


class HttpAuthTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.base_dir = Path(self.tmpdir.name)
        self.site_store = SiteConfigStore(self.base_dir)
        raw = make_raw_config(config_admin_token="release-bootstrap-code")
        raw["api"]["port"] = _free_port()
        raw["api"]["read_only"] = False
        self.site_store.save_revision(raw, action="site.bootstrap", actor="test")
        config = validate_raw_config(raw, base_dir=self.base_dir)
        dashboard_dir = self.base_dir / "dashboard"
        dashboard_dir.mkdir()
        (dashboard_dir / "index.html").write_text("<html>ok</html>", encoding="utf-8")
        (dashboard_dir / "dashboard.css").write_text("", encoding="utf-8")
        (dashboard_dir / "dashboard.js").write_text("", encoding="utf-8")
        for path, payload in (
            (config.health_path, {"status": "healthy", "today_date": "2026-07-14"}),
            (config.state_path, {}),
            (config.price_cache_path, {}),
            (config.spotmarket_plan_path, {"min_consecutive_quarters": 8}),
        ):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(payload), encoding="utf-8")
        identity_store = IdentityStore(self.base_dir)
        self.commissioning = CommissioningService(
            store=CommissioningStore(identity_store.path),
            identity_store=identity_store,
            adapter=FakeAdapter(readback=0),
            config=config,
            logger=logging.getLogger("mini_ems.runtime.test.http_auth.commissioning"),
            timer_factory=FakeTimer,
        )
        self.addCleanup(self.commissioning.shutdown)
        self.server = MiniEmsApiServer(
            api_config=config.api,
            runtime_db=RuntimeDatabase(config.database_path),
            health_path=config.health_path,
            state_path=config.state_path,
            price_cache_path=config.price_cache_path,
            spotmarket_plan_path=config.spotmarket_plan_path,
            dashboard_dir=dashboard_dir,
            logger=logging.getLogger("mini_ems.runtime.test.http_auth"),
            read_diagnostics=None,
            site_store=self.site_store,
            identity_store=identity_store,
            commissioning_service=self.commissioning,
        )
        self.server.start()
        self.addCleanup(self.server.stop)
        self.host, self.port = self.server._server.server_address

    def request(
        self,
        method: str,
        path: str,
        payload: Optional[Dict[str, object]] = None,
        cookie: Optional[str] = None,
    ):
        connection = http.client.HTTPConnection(self.host, self.port, timeout=10)
        headers = {}
        body = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            body = json.dumps(payload)
        if cookie:
            headers["Cookie"] = cookie
        try:
            connection.request(method, path, body=body, headers=headers)
            response = connection.getresponse()
            raw = response.read()
            parsed = json.loads(raw.decode("utf-8")) if raw else {}
            return response.status, parsed, dict(response.getheaders())
        finally:
            connection.close()

    def bootstrap_admin(self) -> str:
        status, payload, headers = self.request(
            "POST",
            "/api/auth/bootstrap",
            {
                "bootstrap_code": "release-bootstrap-code",
                "username": "admin",
                "display_name": "Anlagenadmin",
                "password": "admin-passwort-2026",
            },
        )
        self.assertEqual(status, 200)
        self.assertTrue(payload["authenticated"])
        return headers["Set-Cookie"].split(";", 1)[0]

    def test_first_admin_bootstrap_sets_server_side_session_cookie(self) -> None:
        status, before, _ = self.request("GET", "/api/auth/status")
        self.assertEqual(status, 200)
        self.assertFalse(before["initialized"])

        status, payload, headers = self.request(
            "POST",
            "/api/auth/bootstrap",
            {
                "bootstrap_code": "release-bootstrap-code",
                "username": "admin",
                "display_name": "Anlagenadmin",
                "password": "admin-passwort-2026",
            },
        )

        self.assertEqual(status, 200)
        self.assertEqual(payload["user"]["role"], "admin")
        cookie = headers["Set-Cookie"]
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Strict", cookie)
        self.assertNotIn("admin-passwort-2026", cookie)

    def test_public_health_is_minimal_and_sends_security_headers(self) -> None:
        status, payload, headers = self.request("GET", "/api/health")

        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "healthy")
        self.assertEqual(payload["api_read_only"], False)
        self.assertIn("app_version", payload)
        self.assertNotIn("today_date", payload)
        self.assertNotIn("state", payload)
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(headers["X-Frame-Options"], "DENY")
        self.assertIn("default-src 'self'", headers["Content-Security-Policy"])

    def test_data_requires_login_and_viewer_cannot_configure(self) -> None:
        status, payload, _ = self.request("GET", "/api/status")
        self.assertEqual(status, 401)
        self.assertEqual(payload["error"], "authentication_required")
        admin_cookie = self.bootstrap_admin()

        status, created, _ = self.request(
            "POST",
            "/api/auth/users/create",
            {
                "username": "viewer",
                "display_name": "Leitwarte",
                "role": "viewer",
                "password": "viewer-passwort-2026",
            },
            admin_cookie,
        )
        self.assertEqual(status, 200)
        self.assertEqual(created["user"]["role"], "viewer")

        status, login, headers = self.request(
            "POST",
            "/api/auth/login",
            {"username": "viewer", "password": "viewer-passwort-2026"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(login["user"]["role"], "viewer")
        viewer_cookie = headers["Set-Cookie"].split(";", 1)[0]

        self.assertEqual(self.request("GET", "/api/status", cookie=viewer_cookie)[0], 200)
        status, payload, _ = self.request("GET", "/api/config/site", cookie=viewer_cookie)
        self.assertEqual(status, 403)
        self.assertEqual(payload["error"], "forbidden")
        status, payload, _ = self.request(
            "POST",
            "/api/config/site/validate",
            {"patch": {"timing": {"cycle_seconds": 60}}},
            viewer_cookie,
        )
        self.assertEqual(status, 403)
        self.assertEqual(payload["error"], "forbidden")

    def test_logout_revokes_session(self) -> None:
        cookie = self.bootstrap_admin()

        status, payload, headers = self.request("POST", "/api/auth/logout", {}, cookie)

        self.assertEqual(status, 200)
        self.assertFalse(payload["authenticated"])
        self.assertIn("Max-Age=0", headers["Set-Cookie"])
        self.assertEqual(self.request("GET", "/api/status", cookie=cookie)[0], 401)

    def test_admin_can_approve_and_run_bounded_bacnet_test(self) -> None:
        cookie = self.bootstrap_admin()
        status, approved, _ = self.request(
            "POST",
            "/api/bacnet/write-points/approve",
            {
                "name": "EMS_TEST_BV",
                "controller_ip": "192.168.244.10",
                "controller_port": 47808,
                "object_type": "bv",
                "instance": 200,
                "write_priority": 14,
            },
            cookie,
        )
        self.assertEqual(status, 200)
        point_id = approved["point"]["id"]

        status, started, _ = self.request(
            "POST",
            "/api/bacnet/write-test/start",
            {"point_id": point_id, "value": False},
            cookie,
        )

        self.assertEqual(status, 200)
        self.assertTrue(started["effective"])
        self.assertEqual(started["lease"]["status"], "active")
        status, listed, _ = self.request("GET", "/api/bacnet/write-points", cookie=cookie)
        self.assertEqual(status, 200)
        self.assertEqual(listed["points"][0]["last_test"]["status"], "active")

        status, released, _ = self.request(
            "POST",
            "/api/bacnet/write-test/release",
            {"lease_id": started["lease"]["id"]},
            cookie,
        )
        self.assertEqual(status, 200)
        self.assertEqual(released["lease"]["status"], "released")


if __name__ == "__main__":
    unittest.main()
