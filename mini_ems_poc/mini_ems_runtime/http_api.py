import copy
import json
import logging
import math
import os
import threading
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Dict, Optional
from urllib.error import URLError
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

from .bacnet_discovery import preview_bacnet_discovery_payload
from .commissioning import CommissioningService
from .config import ApiConfig, validate_raw_config
from .identity import IdentityStore, IdentityUser, ROLE_ADMIN
from .logging_utils import log_event
from .mapping_config import build_mapping_config_patch
from .pointlist_import import import_pointlist_payload
from .read_diagnostics import ChannelReadDiagnosticsService
from .runtime_db import RuntimeDatabase
from .spotmarket_plan import SpotmarketPlanWriter
from .site_store import SiteConfigStore, SiteRevision


class MiniEmsApiServer:
    def __init__(
        self,
        api_config: ApiConfig,
        runtime_db: RuntimeDatabase,
        health_path: Path,
        state_path: Path,
        price_cache_path: Path,
        spotmarket_plan_path: Path,
        dashboard_dir: Path,
        logger,
        read_diagnostics: ChannelReadDiagnosticsService,
        site_store: Optional[SiteConfigStore] = None,
        spotmarket_plan_writer: Optional[SpotmarketPlanWriter] = None,
        price_source_resolution: str = "quarterhour",
        app_version: Optional[Dict[str, object]] = None,
        identity_store: Optional[IdentityStore] = None,
        secure_cookies: bool = False,
        commissioning_service: Optional[CommissioningService] = None,
    ):
        self.api_config = api_config
        self.runtime_db = runtime_db
        self.health_path = Path(health_path)
        self.state_path = Path(state_path)
        self.price_cache_path = Path(price_cache_path)
        self.spotmarket_plan_path = Path(spotmarket_plan_path)
        self.dashboard_dir = Path(dashboard_dir)
        self.logger = logger
        self.read_diagnostics = read_diagnostics
        self.site_store = site_store
        self.identity_store = identity_store or (
            IdentityStore(site_store.site_dir) if site_store is not None else None
        )
        self.secure_cookies = bool(secure_cookies)
        self.commissioning_service = commissioning_service
        self._runtime_config_fingerprint = self._config_fingerprint()
        self.spotmarket_plan_writer = spotmarket_plan_writer
        self.price_source_resolution = str(price_source_resolution).lower()
        # Additive Softwareversion fuer /api/status und die Systemstatus-Seite.
        # Direkt konstruierte Server (Tests) ohne VERSION liefern die dev-Variante.
        self.app_version = app_version or {"version": "dev", "git_commit": None, "build_date": None}
        self._server: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if not self.api_config.enabled or self._server is not None:
            return
        self._server = ThreadingHTTPServer(
            (self.api_config.host, self.api_config.port),
            self._build_handler(),
        )
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name="mini-ems-http-api",
            daemon=True,
        )
        self._thread.start()
        log_event(
            self.logger,
            20,
            "api.started",
            host=self.api_config.host,
            port=self.api_config.port,
        )

    def stop(self) -> None:
        if self._server is None:
            return
        self._server.shutdown()
        self._server.server_close()
        self._server = None
        self._thread = None
        log_event(self.logger, 20, "api.stopped")

    def _build_handler(self) -> type[BaseHTTPRequestHandler]:
        api_server = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                parsed = urlparse(self.path)
                query = parse_qs(parsed.query)
                try:
                    if parsed.path in ("/", "/dashboard", "/index.html"):
                        api_server._record_ui_access(parsed.path)
                        self._send_file(api_server.dashboard_dir / "index.html", "text/html; charset=utf-8")
                        return
                    if parsed.path == "/dashboard.css":
                        self._send_file(api_server.dashboard_dir / "dashboard.css", "text/css; charset=utf-8")
                        return
                    if parsed.path == "/dashboard.js":
                        self._send_file(api_server.dashboard_dir / "dashboard.js", "application/javascript; charset=utf-8")
                        return
                    if parsed.path == "/theme-init.js":
                        self._send_file(api_server.dashboard_dir / "theme-init.js", "application/javascript; charset=utf-8")
                        return
                    if parsed.path.startswith("/vendor/"):
                        self._send_vendor_asset(parsed.path[len("/vendor/"):])
                        return
                    if parsed.path == "/api/auth/status":
                        self._send_json(api_server.auth_status_payload(self._session_token()))
                        return
                    if parsed.path == "/api/health":
                        self._send_json(api_server.health_payload())
                        return
                    user = self._require_authenticated()
                    if user is None:
                        return
                    if parsed.path in _ADMIN_GET_PATHS and user.role != ROLE_ADMIN:
                        self._send_forbidden("Diese Funktion ist nur für Administratoren verfügbar.")
                        return
                    if self._deny_in_read_only("GET", parsed.path):
                        return
                    if parsed.path == "/api/auth/users":
                        self._send_json(api_server.users_payload())
                        return
                    if parsed.path == "/api/auth/events":
                        self._send_json(api_server.security_events_payload())
                        return
                    if parsed.path == "/api/bacnet/write-points":
                        self._send_json(api_server._require_commissioning_service().points_payload())
                        return
                    if parsed.path == "/api/status":
                        self._send_json(api_server._get_status_payload())
                        return
                    if parsed.path == "/api/config/spotmarket-lockout":
                        self._send_json(api_server._get_spotmarket_lockout_settings())
                        return
                    if parsed.path == "/api/config/site":
                        self._send_json(api_server.get_site_config())
                        return
                    if parsed.path == "/api/config/changes":
                        limit = int(_single_value(query, "limit", "10"))
                        self._send_json(api_server.get_config_changes_payload(limit=limit))
                        return
                    if parsed.path == "/api/spotmarket/windows":
                        self._send_json(api_server._load_json(api_server.spotmarket_plan_path, {}))
                        return
                    if parsed.path == "/api/history":
                        channel_id = _single_value(query, "channel_id", "tariff.current_price_ct_kwh")
                        limit = int(_single_value(query, "limit", str(api_server.api_config.history_default_limit)))
                        granularity = _single_value(query, "granularity", "raw")
                        start = _optional_single_value(query, "start")
                        end = _optional_single_value(query, "end")
                        self._send_json(
                            {
                                "channel_id": channel_id,
                                "granularity": granularity,
                                "rows": api_server.runtime_db.get_channel_history(
                                    channel_id,
                                    limit=limit,
                                    granularity=granularity,
                                    start=start,
                                    end=end,
                                ),
                            }
                        )
                        return
                    if parsed.path == "/api/cycles":
                        limit = int(_single_value(query, "limit", "20"))
                        self._send_json({"rows": api_server.runtime_db.get_recent_cycles(limit=limit)})
                        return
                    if parsed.path == "/api/report/daily":
                        date_iso = _single_value(query, "date", api_server._default_report_date())
                        self._send_json(api_server.runtime_db.get_daily_report(date_iso))
                        return
                    if parsed.path == "/api/report/daily.csv":
                        date_iso = _single_value(query, "date", api_server._default_report_date())
                        self._send_text(
                            api_server.runtime_db.render_daily_report_csv(date_iso),
                            "text/csv; charset=utf-8",
                        )
                        return
                    if parsed.path == "/api/report/studio":
                        date_iso = _single_value(query, "date", api_server._default_report_date())
                        self._send_json(api_server.runtime_db.get_report_studio_payload(date_iso))
                        return
                    if parsed.path == "/api/report/html":
                        config = api_server._report_config_from_query(query)
                        self._send_text(
                            api_server.runtime_db.render_report_html(config, api_server._report_template_path()),
                            "text/html; charset=utf-8",
                        )
                        return
                    if parsed.path == "/api/report/pdf":
                        config = api_server._report_config_from_query(query)
                        self._send_report_pdf(config)
                        return
                    if parsed.path == "/api/weather":
                        self._send_json(api_server._get_weather_payload())
                        return
                    if parsed.path == "/api/diagnostics/read":
                        channel_id = _single_value(query, "channel_id", "tariff.current_price_ct_kwh")
                        samples = int(_single_value(query, "samples", "3"))
                        diagnostic = api_server.read_diagnostics.read_float_channel(
                            channel_id=channel_id,
                            samples=samples,
                            delay_seconds=0.05,
                            plausible_min=-1_000_000.0,
                            plausible_max=1_000_000.0,
                        )
                        self._send_json(diagnostic.to_dict())
                        return
                except Exception as error:
                    self._send_json(
                        {"error": error.__class__.__name__, "message": str(error)},
                        status=HTTPStatus.INTERNAL_SERVER_ERROR,
                    )
                    return

                self._send_json(
                    {"error": "not_found", "path": parsed.path},
                    status=HTTPStatus.NOT_FOUND,
                )

            def do_POST(self) -> None:
                parsed = urlparse(self.path)
                try:
                    if parsed.path == "/api/auth/bootstrap":
                        payload = self._read_json_body()
                        try:
                            session = api_server.bootstrap_identity(payload)
                            self._send_authenticated(session)
                        except PermissionError as error:
                            self._send_json(
                                {"authenticated": False, "message": str(error)},
                                status=HTTPStatus.FORBIDDEN,
                            )
                        return
                    if parsed.path == "/api/auth/login":
                        payload = self._read_json_body()
                        try:
                            session = api_server.login(payload)
                            self._send_authenticated(session)
                        except PermissionError as error:
                            self._send_json(
                                {"authenticated": False, "message": str(error)},
                                status=HTTPStatus.UNAUTHORIZED,
                            )
                        return
                    if parsed.path == "/api/auth/logout":
                        api_server.logout(self._session_token())
                        self._send_json(
                            {"authenticated": False},
                            headers={"Set-Cookie": self._expired_session_cookie()},
                        )
                        return

                    user = self._require_authenticated()
                    if user is None:
                        return
                    if parsed.path not in _VIEWER_POST_PATHS and user.role != ROLE_ADMIN:
                        self._send_forbidden("Diese Funktion ist nur für Administratoren verfügbar.")
                        return
                    if self._deny_in_read_only("POST", parsed.path):
                        return
                    if parsed.path == "/api/auth/users/create":
                        payload = self._read_json_body()
                        self._send_json(api_server.create_user_payload(payload, user))
                        return
                    if parsed.path == "/api/auth/users/update":
                        payload = self._read_json_body()
                        self._send_json(api_server.update_user_payload(payload, user))
                        return
                    if parsed.path == "/api/bacnet/write-points/approve":
                        payload = self._read_json_body()
                        self._send_json(api_server._require_commissioning_service().approve(payload, user))
                        return
                    if parsed.path == "/api/bacnet/write-points/revoke":
                        payload = self._read_json_body()
                        self._send_json(
                            api_server._require_commissioning_service().revoke(
                                str(payload.get("point_id") or ""),
                                user,
                            )
                        )
                        return
                    if parsed.path == "/api/bacnet/write-test/start":
                        payload = self._read_json_body()
                        self._send_json(api_server._require_commissioning_service().start_test(payload, user))
                        return
                    if parsed.path == "/api/bacnet/write-test/release":
                        payload = self._read_json_body()
                        self._send_json(
                            api_server._require_commissioning_service().release_test(
                                str(payload.get("lease_id") or ""),
                                user,
                            )
                        )
                        return
                    if parsed.path == "/api/config/spotmarket-lockout":
                        payload = self._read_json_body()
                        self._send_json(api_server.update_spotmarket_lockout_settings(payload))
                        return
                    if parsed.path == "/api/config/site/validate":
                        payload = self._read_json_body()
                        self._send_json(api_server.validate_site_config_payload(payload))
                        return
                    if parsed.path == "/api/config/site/save":
                        payload = self._read_json_body()
                        self._send_json(api_server.save_site_config_payload(payload, user))
                        return
                    if parsed.path == "/api/config/mapping/preview":
                        payload = self._read_json_body()
                        self._send_json(api_server.preview_mapping_config_payload(payload))
                        return
                    if parsed.path == "/api/config/pointlist/import":
                        payload = self._read_json_body()
                        self._send_json(api_server.import_pointlist_payload(payload))
                        return
                    if parsed.path == "/api/config/discovery/bacnet/preview":
                        payload = self._read_json_body()
                        self._send_json(api_server.preview_bacnet_discovery_payload(payload))
                        return
                    if parsed.path == "/api/config/mapping/activate":
                        payload = self._read_json_body()
                        self._send_json(api_server.activate_mapping_config_payload(payload, user))
                        return
                    if parsed.path == "/api/report/preview":
                        payload = self._read_json_body()
                        self._send_json(api_server.runtime_db.build_configurable_report(payload))
                        return
                except ValueError as error:
                    self._send_json(
                        {"error": "invalid_request", "message": str(error)},
                        status=HTTPStatus.BAD_REQUEST,
                    )
                    return
                except PermissionError as error:
                    self._send_json(
                        {"error": "forbidden", "message": str(error)},
                        status=HTTPStatus.FORBIDDEN,
                    )
                    return
                except Exception as error:
                    self._send_json(
                        {"error": error.__class__.__name__, "message": str(error)},
                        status=HTTPStatus.INTERNAL_SERVER_ERROR,
                    )
                    return

                self._send_json(
                    {"error": "not_found", "path": parsed.path},
                    status=HTTPStatus.NOT_FOUND,
                )

            def log_message(self, _format: str, *_args) -> None:
                return None

            def _deny_in_read_only(self, method: str, path: str) -> bool:
                """Zentrale Read-only-Sperre (H5) fuer das Request-Handling.

                Deny-by-default: Im read-only Netzwerkmodus werden nicht freigegebene
                POST-Methoden abgelehnt. Der UI-Konfigurationspfad bleibt verfügbar;
                seine aktivierenden Endpunkte erzwingen weiterhin die Admin-Rolle.
                Zusaetzlich wird der aktive
                Anlagen-Read GET /api/diagnostics/read explizit gesperrt (er loest
                trotz GET einen Live-Lesezugriff aus, siehe HOSTING_SICHERHEIT.md
                Abschnitt 2.1). Rueckgabe True bedeutet: Antwort wurde gesendet,
                der Aufrufer muss abbrechen.
                """
                if not api_server.api_config.read_only:
                    return False
                if method == "POST" and path in _READ_ONLY_CONFIG_POST_PATHS:
                    return False
                if method != "GET" or path in _READ_ONLY_BLOCKED_GET_PATHS:
                    self._send_json(
                        {
                            "error": "read_only_mode",
                            "message": (
                                "Diese Funktion ist über den Netzwerkzugriff nicht "
                                "verfügbar. Änderungen und aktive Anlagenabfragen sind "
                                "nur über den lokalen bzw. administrativen Zugriff auf "
                                "der Anlage möglich."
                            ),
                        },
                        status=HTTPStatus.FORBIDDEN,
                    )
                    return True
                return False

            def _read_json_body(self) -> Dict[str, object]:
                content_type = str(self.headers.get("Content-Type", "")).split(";", 1)[0].strip().lower()
                if content_type != "application/json":
                    raise ValueError("Content-Type muss application/json sein.")
                try:
                    content_length = int(self.headers.get("Content-Length", "0"))
                except ValueError as error:
                    raise ValueError("Invalid Content-Length") from error
                if content_length <= 0:
                    raise ValueError("Request body must not be empty")
                if content_length > _MAX_JSON_BODY_BYTES:
                    raise ValueError("Request body is too large")
                raw = self.rfile.read(content_length)
                try:
                    payload = json.loads(raw.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as error:
                    raise ValueError("Request body must be valid JSON") from error
                if not isinstance(payload, dict):
                    raise ValueError("Request body must be a JSON object")
                return payload

            def _session_token(self) -> Optional[str]:
                raw_cookie = self.headers.get("Cookie", "")
                if not raw_cookie:
                    return None
                cookie = SimpleCookie()
                try:
                    cookie.load(raw_cookie)
                except Exception:
                    return None
                morsel = cookie.get(_SESSION_COOKIE_NAME)
                return morsel.value if morsel is not None else None

            def _require_authenticated(self) -> Optional[IdentityUser]:
                store = api_server.identity_store
                user = store.session_user(self._session_token()) if store is not None else None
                if user is None:
                    self._send_json(
                        {
                            "error": "authentication_required",
                            "message": "Bitte anmelden, um Mini EMS zu verwenden.",
                        },
                        status=HTTPStatus.UNAUTHORIZED,
                    )
                    return None
                return user

            def _send_forbidden(self, message: str) -> None:
                self._send_json(
                    {"error": "forbidden", "message": message},
                    status=HTTPStatus.FORBIDDEN,
                )

            def _send_authenticated(self, session) -> None:
                self._send_json(
                    api_server.auth_status_payload(session.token),
                    headers={"Set-Cookie": self._session_cookie(session.token)},
                )

            def _session_cookie(self, token: str) -> str:
                parts = [
                    "{0}={1}".format(_SESSION_COOKIE_NAME, token),
                    "Path=/",
                    "HttpOnly",
                    "SameSite=Strict",
                    "Max-Age=43200",
                ]
                if api_server.secure_cookies:
                    parts.append("Secure")
                return "; ".join(parts)

            def _expired_session_cookie(self) -> str:
                parts = [
                    "{0}=".format(_SESSION_COOKIE_NAME),
                    "Path=/",
                    "HttpOnly",
                    "SameSite=Strict",
                    "Max-Age=0",
                ]
                if api_server.secure_cookies:
                    parts.append("Secure")
                return "; ".join(parts)

            def _send_json(
                self,
                payload: Dict[str, object],
                status: HTTPStatus = HTTPStatus.OK,
                headers: Optional[Dict[str, str]] = None,
            ) -> None:
                raw = json.dumps(payload, ensure_ascii=True, sort_keys=True).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self._send_security_headers()
                for name, value in (headers or {}).items():
                    self.send_header(name, value)
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def _send_text(self, payload: str, content_type: str, status: HTTPStatus = HTTPStatus.OK) -> None:
                raw = payload.encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Cache-Control", "no-store")
                self._send_security_headers()
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def _send_report_pdf(self, config: Dict[str, object]) -> None:
                html = api_server.runtime_db.render_report_html(config, api_server._report_template_path())
                try:
                    from weasyprint import HTML
                except ImportError:
                    self._send_text(
                        html,
                        "text/html; charset=utf-8",
                    )
                    return
                raw = HTML(string=html, base_url=str(api_server.dashboard_dir.parent)).write_pdf()
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "application/pdf")
                self.send_header("Cache-Control", "no-store")
                self._send_security_headers()
                self.send_header("Content-Disposition", 'attachment; filename="mini-ems-report.pdf"')
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def _send_vendor_asset(self, relative: str) -> None:
                content_types = {
                    ".js": "application/javascript; charset=utf-8",
                    ".css": "text/css; charset=utf-8",
                    ".woff2": "font/woff2",
                }
                vendor_root = (api_server.dashboard_dir / "vendor").resolve()
                target = (vendor_root / relative).resolve()
                if vendor_root not in target.parents or target.suffix not in content_types:
                    self._send_json({"error": "not_found", "path": relative}, status=HTTPStatus.NOT_FOUND)
                    return
                self._send_file(target, content_types[target.suffix])

            def _send_file(self, path: Path, content_type: str) -> None:
                if not path.exists():
                    self._send_json({"error": "not_found", "path": str(path)}, status=HTTPStatus.NOT_FOUND)
                    return
                raw = path.read_bytes()
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", content_type)
                self.send_header("Cache-Control", "no-store")
                self._send_security_headers()
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def _send_security_headers(self) -> None:
                self.send_header("Content-Security-Policy", _CONTENT_SECURITY_POLICY)
                self.send_header("Referrer-Policy", "no-referrer")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("X-Frame-Options", "DENY")

        return Handler

    def _report_template_path(self) -> Path:
        return self.dashboard_dir.parent / "mini_ems_runtime" / "templates" / "report.html.j2"

    def _report_config_from_query(self, query: Dict[str, list[str]]) -> Dict[str, object]:
        start = _optional_single_value(query, "start")
        end = _optional_single_value(query, "end")
        if start is None and end is None:
            # Tagesbericht (UX2): ohne expliziten Zeitraum wird der volle
            # Berichtstag verwendet - per ?date=YYYY-MM-DD oder als Standard
            # der aktuelle Betriebstag aus health.json.
            day_range = _report_day_range(_single_value(query, "date", self._default_report_date()))
            if day_range is not None:
                start, end = day_range
        return {
            "title": _single_value(query, "title", "Tagesbericht"),
            "start": start,
            "end": end,
            "granularity": _single_value(query, "granularity", "5m"),
            "channels": _multi_value(query, "channels", ["tariff.current_price_ct_kwh", "site.outdoor_temperature_c"]),
            "sections": [
                {"component": component}
                for component in _multi_value(query, "sections", ["summary", "line_chart", "table", "events"])
            ],
        }

    def _default_report_date(self) -> str:
        health = self._load_json(self.health_path, {})
        today_date = health.get("today_date")
        if isinstance(today_date, str) and today_date:
            return today_date
        return ""

    def auth_status_payload(self, session_token: Optional[str]) -> Dict[str, object]:
        store = self.identity_store
        initialized = bool(store and store.is_initialized())
        user = store.session_user(session_token) if store is not None else None
        return {
            "initialized": initialized,
            "authenticated": user is not None,
            "user": user.to_public_dict() if user is not None else None,
            "permissions": _permissions_for(user),
        }

    def health_payload(self) -> Dict[str, object]:
        health = self._load_json(self.health_path, {})
        return {
            "status": str(health.get("status") or "unknown"),
            "timestamp": health.get("timestamp"),
            "app_version": self.app_version,
            "api_read_only": bool(self.api_config.read_only),
        }

    def bootstrap_identity(self, payload: Dict[str, object]):
        store = self._require_identity_store()
        return store.bootstrap_admin(
            bootstrap_code=str(payload.get("bootstrap_code") or ""),
            expected_code=str(self.api_config.config_admin_token or ""),
            username=str(payload.get("username") or "admin"),
            display_name=str(payload.get("display_name") or "Administrator"),
            password=str(payload.get("password") or ""),
        )

    def login(self, payload: Dict[str, object]):
        return self._require_identity_store().authenticate(
            str(payload.get("username") or ""),
            str(payload.get("password") or ""),
        )

    def logout(self, session_token: Optional[str]) -> None:
        self._require_identity_store().revoke_session(session_token)

    def users_payload(self) -> Dict[str, object]:
        return {
            "users": [user.to_public_dict() for user in self._require_identity_store().list_users()]
        }

    def create_user_payload(
        self,
        payload: Dict[str, object],
        actor: IdentityUser,
    ) -> Dict[str, object]:
        user = self._require_identity_store().create_user(
            username=str(payload.get("username") or ""),
            display_name=str(payload.get("display_name") or ""),
            role=str(payload.get("role") or "viewer"),
            password=str(payload.get("password") or ""),
            actor_user_id=actor.user_id,
        )
        return {"created": True, "user": user.to_public_dict()}

    def update_user_payload(
        self,
        payload: Dict[str, object],
        actor: IdentityUser,
    ) -> Dict[str, object]:
        enabled_value = payload.get("enabled")
        if enabled_value is not None and not isinstance(enabled_value, bool):
            raise ValueError("enabled muss true oder false sein.")
        user = self._require_identity_store().update_user(
            user_id=str(payload.get("user_id") or ""),
            role=str(payload["role"]) if payload.get("role") is not None else None,
            enabled=enabled_value,
            password=str(payload["password"]) if payload.get("password") else None,
            actor_user_id=actor.user_id,
        )
        return {"updated": True, "user": user.to_public_dict()}

    def security_events_payload(self) -> Dict[str, object]:
        return {"events": self._require_identity_store().recent_events(30)}

    def _get_status_payload(self) -> Dict[str, object]:
        health = self._load_json(self.health_path, {})
        state = self._load_json(self.state_path, {})
        price_cache = self._load_json(self.price_cache_path, {})
        spotmarket_plan = self._load_json(self.spotmarket_plan_path, {})
        return {
            "health": health,
            "state": state,
            "price_cache": price_cache,
            "spotmarket_plan": spotmarket_plan,
            "spotmarket_settings": self._get_spotmarket_lockout_settings(spotmarket_plan),
            "recent_cycles": self.runtime_db.get_recent_cycles(limit=12),
            # Additiver Modus-Hinweis fuer das UI (H5): read-only Netzwerkmodus aktiv?
            "api_read_only": bool(self.api_config.read_only),
            # Additive Softwareversion (H2): version/git_commit/build_date aus der
            # VERSION-Datei des Release-Pakets bzw. dev im Git-Betrieb.
            "app_version": self.app_version,
        }

    def _get_weather_payload(self) -> Dict[str, object]:
        cache_path = self.dashboard_dir.parent / "data" / "weather" / "open_meteo_weather_cache.json"
        cached = self._load_json(cache_path, {})
        cached_at = _parse_epoch_seconds(cached.get("fetched_at"))
        now = datetime.now(timezone.utc)
        if cached and cached_at is not None and now.timestamp() - cached_at < 900:
            return cached

        url = (
            "https://api.open-meteo.com/v1/forecast"
            "?latitude=48.7758&longitude=9.1829"
            "&current=temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m"
            "&hourly=temperature_2m,precipitation_probability,cloud_cover"
            "&forecast_days=1&timezone=Europe%2FBerlin"
        )
        try:
            request = Request(url, headers={"User-Agent": "MiniEmsPoC/1.0"})
            with urlopen(request, timeout=8) as response:
                raw = json.loads(response.read().decode("utf-8"))
        except (OSError, URLError, json.JSONDecodeError) as error:
            if cached:
                cached["stale"] = True
                cached["error"] = str(error)
                return cached
            return {"status": "unavailable", "error": str(error), "site": "Stuttgart"}

        payload = _normalize_weather_payload(raw)
        payload["fetched_at"] = now.isoformat().replace("+00:00", "Z")
        _write_json_preserve_order(cache_path, payload)
        return payload

    def get_site_config(self) -> Dict[str, object]:
        raw = self._read_site_config()
        config = validate_raw_config(raw, base_dir=self._config_base_dir())
        restart_required = self._config_restart_required()
        mapping_status = self._mapping_status(restart_required)
        return {
            "config": _safe_site_config_view(raw, config),
            "editable_sections": list(_SITE_CONFIG_EDITABLE_SECTIONS),
            "save_enabled": bool(self.identity_store and self.identity_store.is_initialized()),
            "restart_required_on_save": True,
            "restart_required": restart_required,
            "setup_required": not mapping_status["active"],
            "mapping_status": mapping_status,
        }

    def get_config_changes_payload(self, limit: int = 10) -> Dict[str, object]:
        safe_limit = min(max(int(limit), 1), 50)
        entries = [
            entry
            for entry in self._site_history(200)
            if entry.get("action") in {
                "mapping.activate",
                "site_config.save",
                "spotmarket.settings.update",
                "admin_code.reset",
            }
        ][:safe_limit]
        return {
            "changes": [self._public_config_change(entry) for entry in entries],
        }

    def validate_site_config_payload(self, payload: Dict[str, object]) -> Dict[str, object]:
        try:
            raw = self._candidate_config_from_payload(payload)
            validate_raw_config(raw, base_dir=self._config_base_dir())
        except Exception as error:
            return {"valid": False, "message": str(error)}
        return {"valid": True}

    def preview_mapping_config_payload(self, payload: Dict[str, object]) -> Dict[str, object]:
        result = build_mapping_config_patch(payload)
        if not result.get("valid"):
            return result
        try:
            raw = _deep_merge_dicts(self._read_site_config(), result["patch"])
            validate_raw_config(raw, base_dir=self._config_base_dir())
        except Exception as error:
            errors = list(result.get("errors", []))
            errors.append(str(error))
            return {
                **result,
                "valid": False,
                "errors": errors,
            }
        return result

    def import_pointlist_payload(self, payload: Dict[str, object]) -> Dict[str, object]:
        return import_pointlist_payload(payload)

    def preview_bacnet_discovery_payload(self, payload: Dict[str, object]) -> Dict[str, object]:
        return preview_bacnet_discovery_payload(payload)

    def save_site_config_payload(
        self,
        payload: Dict[str, object],
        actor: Optional[IdentityUser],
    ) -> Dict[str, object]:
        actor = _require_admin_actor(actor)
        previous = self._read_site_config()
        try:
            raw = self._candidate_config_from_payload(payload)
            validate_raw_config(raw, base_dir=self._config_base_dir())
        except Exception as error:
            return {"saved": False, "valid": False, "message": str(error)}

        changed_sections = _changed_top_level_sections(previous, raw)
        store = self._require_site_store()
        previous_revision = store.active_revision()
        revision = store.save_revision(
            raw,
            action="site_config.save",
            actor=actor.username,
            details={
                "restart_required": True,
                "changed_sections": changed_sections,
            },
        )
        log_event(
            self.logger,
            logging.INFO,
            "config.site_saved",
            changed_sections=changed_sections,
            restart_required=True,
        )
        return {
            "saved": True,
            "valid": True,
            "restart_required": True,
            "previous_revision": previous_revision,
            "revision": revision,
        }

    def activate_mapping_config_payload(
        self,
        payload: Dict[str, object],
        actor: Optional[IdentityUser],
    ) -> Dict[str, object]:
        actor = _require_admin_actor(actor)
        preview = self.preview_mapping_config_payload(payload)
        if not preview.get("valid"):
            return {
                "activated": False,
                "valid": False,
                "errors": list(preview.get("errors", [])),
                "warnings": list(preview.get("warnings", [])),
            }

        store = self._require_site_store()
        raw = _deep_merge_dicts(self._read_site_config(), preview["patch"])
        validate_raw_config(raw, base_dir=self._config_base_dir())
        previous_revision = store.active_revision()
        revision = store.save_revision(
            raw,
            action="mapping.activate",
            actor=actor.username,
            mapping_draft=payload,
            details={
                "restart_required": True,
                "patch_sections": sorted(str(key) for key in preview["patch"].keys()),
                "device_count": len(payload.get("devices", [])),
                "mapping_count": len(payload.get("mappings", [])),
            },
        )
        log_event(
            self.logger,
            logging.INFO,
            "config.mapping_activated",
            revision=revision,
            device_count=len(payload.get("devices", [])),
            mapping_count=len(payload.get("mappings", [])),
            restart_required=True,
        )
        return {
            "activated": True,
            "valid": True,
            "restart_required": True,
            "previous_revision": previous_revision,
            "revision": revision,
            "warnings": list(preview.get("warnings", [])),
        }

    def update_spotmarket_lockout_settings(self, payload: Dict[str, object]) -> Dict[str, object]:
        min_consecutive_quarters = self._parse_min_consecutive_quarters(payload)
        if self.site_store is not None:
            restart_was_required = self._config_restart_required()
            self._persist_min_consecutive_quarters(min_consecutive_quarters)
            if not restart_was_required:
                # Diese Einstellung wird unten direkt in die laufende Runtime
                # übernommen und benötigt für sich allein keinen Neustart.
                self._runtime_config_fingerprint = self._config_fingerprint()
            # _persist_min_consecutive_quarters already wrote the immutable
            # revision; no separate audit file exists anymore.
        if self.spotmarket_plan_writer is not None:
            self.spotmarket_plan_writer.set_min_consecutive_quarters(min_consecutive_quarters)
        log_event(
            self.logger,
            20,
            "api.spotmarket_settings_updated",
            min_consecutive_quarters=min_consecutive_quarters,
        )
        return self._spotmarket_settings_payload(min_consecutive_quarters)

    def _get_spotmarket_lockout_settings(self, spotmarket_plan: Optional[Dict[str, object]] = None) -> Dict[str, object]:
        if self.spotmarket_plan_writer is not None:
            writer_payload = self.spotmarket_plan_writer.settings_payload()
            return self._spotmarket_settings_payload(int(writer_payload["min_consecutive_quarters"]))
        if spotmarket_plan is None:
            spotmarket_plan = self._load_json(self.spotmarket_plan_path, {})
        raw_quarters = spotmarket_plan.get("min_consecutive_quarters", 0)
        try:
            min_consecutive_quarters = int(raw_quarters)
        except (TypeError, ValueError):
            min_consecutive_quarters = 0
        return self._spotmarket_settings_payload(min_consecutive_quarters)

    def _parse_min_consecutive_quarters(self, payload: Dict[str, object]) -> int:
        slots_per_hour = self._slots_per_hour()
        if "min_consecutive_quarters" in payload:
            try:
                quarters = int(payload["min_consecutive_quarters"])
            except (TypeError, ValueError) as error:
                raise ValueError("min_consecutive_quarters must be an integer") from error
        elif "min_consecutive_hours" in payload:
            try:
                hours = float(payload["min_consecutive_hours"])
            except (TypeError, ValueError) as error:
                raise ValueError("min_consecutive_hours must be a number") from error
            quarters = int(math.ceil(hours * slots_per_hour))
        else:
            raise ValueError("Missing min_consecutive_hours or min_consecutive_quarters")

        max_slots = 24 * slots_per_hour
        if quarters <= 0 or quarters > max_slots:
            raise ValueError("min_consecutive_quarters must be between 1 and {0}".format(max_slots))
        return quarters

    def _persist_min_consecutive_quarters(self, min_consecutive_quarters: int) -> None:
        if self.site_store is None:
            return
        raw = self._read_site_config()
        controllers = raw.setdefault("controllers", {})
        if not isinstance(controllers, dict):
            raise ValueError("Config section controllers must be a JSON object")
        spotmarket_lockout = controllers.setdefault("spotmarket_lockout", {})
        if not isinstance(spotmarket_lockout, dict):
            raise ValueError("Config section controllers.spotmarket_lockout must be a JSON object")
        spotmarket_lockout["negative_quarters_min_consecutive"] = min_consecutive_quarters
        validate_raw_config(raw, base_dir=self._config_base_dir())
        self.site_store.save_revision(
            raw,
            action="spotmarket.settings.update",
            actor="operator",
            details={
                "restart_required": False,
                "min_consecutive_quarters": min_consecutive_quarters,
            },
        )

    def _spotmarket_settings_payload(self, min_consecutive_quarters: int) -> Dict[str, object]:
        slots_per_hour = self._slots_per_hour()
        return {
            "resolution": self.price_source_resolution,
            "slots_per_hour": slots_per_hour,
            "min_consecutive_quarters": min_consecutive_quarters,
            "min_consecutive_hours": min_consecutive_quarters / slots_per_hour if slots_per_hour else 0,
        }

    def _slots_per_hour(self) -> int:
        return 1 if self.price_source_resolution == "hour" else 4

    def _load_json(self, path: Path, default: Dict[str, object]) -> Dict[str, object]:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return dict(default)
        if not isinstance(raw, dict):
            return dict(default)
        return raw

    def _candidate_config_from_payload(self, payload: Dict[str, object]) -> Dict[str, object]:
        if "config" in payload:
            config_payload = payload["config"]
            if not isinstance(config_payload, dict):
                raise ValueError("config must be a JSON object")
            if _looks_like_full_config(config_payload):
                return copy.deepcopy(config_payload)
            return _deep_merge_dicts(self._read_site_config(), config_payload)
        if "patch" in payload:
            patch = payload["patch"]
            if not isinstance(patch, dict):
                raise ValueError("patch must be a JSON object")
            return _deep_merge_dicts(self._read_site_config(), patch)
        if _looks_like_full_config(payload):
            return copy.deepcopy(payload)
        return _deep_merge_dicts(self._read_site_config(), payload)

    def _read_site_config(self) -> Dict[str, object]:
        return self._require_site_store().active_config()

    def _config_base_dir(self) -> Path:
        return self._require_site_store().site_dir

    def _require_site_store(self) -> SiteConfigStore:
        if self.site_store is None:
            raise ValueError("Der Standort-Speicher ist nicht verfügbar.")
        return self.site_store

    def _require_identity_store(self) -> IdentityStore:
        if self.identity_store is None:
            raise ValueError("Der Benutzer-Speicher ist nicht verfügbar.")
        return self.identity_store

    def _require_commissioning_service(self) -> CommissioningService:
        if self.commissioning_service is None:
            raise ValueError("Die BACnet-Inbetriebnahme ist nicht verfügbar.")
        return self.commissioning_service

    def _config_fingerprint(self) -> Optional[str]:
        return self.site_store.active_fingerprint() if self.site_store is not None else None

    def _config_restart_required(self) -> bool:
        current = self._config_fingerprint()
        return current is not None and current != self._runtime_config_fingerprint

    def _mapping_status(self, restart_required: bool) -> Dict[str, object]:
        if self.site_store is not None:
            revision = self.site_store.latest_for_action("mapping.activate")
        else:
            revision = None
        if revision is not None:
            entry = self._revision_entry(revision)
            return {
                "active": True,
                "revision": str(entry.get("revision") or ""),
                "activated_at": _normalize_audit_timestamp(entry.get("timestamp")),
                "device_count": _safe_nonnegative_int(entry.get("device_count")),
                "mapping_count": _safe_nonnegative_int(entry.get("mapping_count")),
                "restart_required": restart_required,
            }
        if self.site_store is not None:
            imported = self.site_store.latest_for_action("legacy_config.import")
        else:
            imported = None
        if imported is not None:
            return {
                "active": True,
                "revision": imported.revision,
                "activated_at": _normalize_audit_timestamp(imported.timestamp),
                "device_count": 0,
                "mapping_count": 0,
                "restart_required": restart_required,
            }
        return {
            "active": False,
            "revision": None,
            "activated_at": None,
            "device_count": 0,
            "mapping_count": 0,
            "restart_required": restart_required,
        }

    def _site_history(self, limit: int) -> list[Dict[str, object]]:
        if self.site_store is None:
            return []
        return [self._revision_entry(revision) for revision in self.site_store.history(limit)]

    @staticmethod
    def _revision_entry(revision: SiteRevision) -> Dict[str, object]:
        return {
            "timestamp": revision.timestamp,
            "revision": revision.revision,
            "action": revision.action,
            "actor": revision.actor,
            **revision.details,
        }

    def _public_config_change(self, entry: Dict[str, object]) -> Dict[str, object]:
        action = str(entry.get("action") or "")
        if action == "mapping.activate":
            count = _safe_nonnegative_int(entry.get("mapping_count"))
            title = "Datenpunkte aktiviert"
            detail = (
                "{0} {1} übernommen; Sicherung automatisch erstellt.".format(
                    count,
                    "Zuordnung" if count == 1 else "Zuordnungen",
                )
                if count
                else "Zuordnung übernommen; Sicherung automatisch erstellt."
            )
        elif action == "site_config.save":
            title = "Betriebseinstellungen gespeichert"
            detail = "Geprüfte Einstellungen übernommen; Sicherung automatisch erstellt."
        elif action == "spotmarket.settings.update":
            title = "Preissteuerung angepasst"
            quarters = _safe_nonnegative_int(entry.get("min_consecutive_quarters"))
            detail = "Mindestdauer auf {0} Viertelstunden gesetzt.".format(quarters)
        elif action == "legacy_config.import":
            title = "Bestehenden Standort übernommen"
            detail = "Die bisherige Standortkonfiguration wurde einmalig in den Standort-Speicher migriert."
        elif action == "site.bootstrap":
            title = "Standort angelegt"
            detail = "Ein sicherer Einrichtungsstand wurde erzeugt."
        elif action == "admin_code.reset":
            title = "Freigabecode erneuert"
            detail = "Der lokale Freigabecode wurde erneuert."
        else:
            title = "Änderung protokolliert"
            detail = "Eine administrative Änderung wurde erfasst."
        return {
            "timestamp": _normalize_audit_timestamp(entry.get("timestamp")),
            "title": title,
            "detail": detail,
            "restart_required": bool(entry.get("restart_required", False)),
        }

    def _record_ui_access(self, path: str) -> None:
        log_event(
            self.logger,
            logging.INFO,
            "ui.accessed",
            path=path,
            access_mode="read_only" if self.api_config.read_only else "administrative",
        )

# GET-Endpunkte, die trotz GET im read-only Netzwerkmodus (H5) gesperrt bleiben,
# weil sie einen aktiven Lesezugriff auf die Anlage ausloesen (HOSTING_SICHERHEIT.md
# Abschnitt 2.1). Alle nicht-GET-Methoden werden ohnehin deny-by-default gesperrt.
_SESSION_COOKIE_NAME = "mini_ems_session"
_MAX_JSON_BODY_BYTES = 10 * 1024 * 1024
_CONTENT_SECURITY_POLICY = (
    "default-src 'self'; script-src 'self'; style-src 'self'; font-src 'self'; "
    "img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; "
    "frame-ancestors 'none'; form-action 'self'"
)

_ADMIN_GET_PATHS = frozenset({
    "/api/auth/users",
    "/api/auth/events",
    "/api/bacnet/write-points",
    "/api/config/site",
    "/api/config/changes",
    "/api/diagnostics/read",
})

_VIEWER_POST_PATHS = frozenset({
    "/api/auth/logout",
    "/api/report/preview",
})

_READ_ONLY_BLOCKED_GET_PATHS = frozenset({"/api/diagnostics/read"})

# UI-Konfiguration bleibt auch im geschuetzten Netzwerkmodus nutzbar. Nur die
# persistierenden Pfade speichern Zustand und verlangen im Handler zusätzlich
# eine authentifizierte Admin-Rolle. Discovery bleibt als aktiver Anlagenread
# gesperrt; Punktlisten-Import und Vorschau arbeiten nur auf dem Request-Inhalt.
_READ_ONLY_CONFIG_POST_PATHS = frozenset({
    "/api/auth/bootstrap",
    "/api/auth/login",
    "/api/auth/logout",
    "/api/auth/users/create",
    "/api/auth/users/update",
    "/api/bacnet/write-points/approve",
    "/api/bacnet/write-points/revoke",
    "/api/bacnet/write-test/release",
    "/api/config/site/validate",
    "/api/config/site/save",
    "/api/config/mapping/preview",
    "/api/config/pointlist/import",
    "/api/config/mapping/activate",
})


def _permissions_for(user: Optional[IdentityUser]) -> list[str]:
    if user is None:
        return []
    permissions = ["dashboard.read", "history.read", "reports.read"]
    if user.role == ROLE_ADMIN:
        permissions.extend(
            [
                "site.configure",
                "mapping.configure",
                "diagnostics.read",
                "users.manage",
                "bacnet.approve",
                "bacnet.write_test",
            ]
        )
    return permissions


def _require_admin_actor(actor: Optional[IdentityUser]) -> IdentityUser:
    if actor is None or not actor.enabled or actor.role != ROLE_ADMIN:
        raise PermissionError("Diese Änderung ist nur für Administratoren verfügbar.")
    return actor


_SITE_CONFIG_EDITABLE_SECTIONS = (
    "site",
    "runtime",
    "network",
    "api",
    "timing",
    "watchdog",
    "price_source",
    "controllers",
    "safety",
    "ddc_heartbeat",
    "outputs",
    "additional_inputs",
)
# Anzeige-Sektionen der Site-Konfiguration: zusaetzlich zu den editierbaren
# Sektionen auch "points", damit die Inbetriebnahme-UI (UX14/UX15) die aktiven
# Kernadressen (Netzleistung, Preis, Sperren) ehrlich anzeigen kann.
_SITE_CONFIG_VIEW_SECTIONS = _SITE_CONFIG_EDITABLE_SECTIONS + ("points",)
_FULL_CONFIG_REQUIRED_SECTIONS = {
    "network",
    "points",
    "timing",
    "price_source",
    "controllers",
    "safety",
    "logging",
}


def _safe_site_config_view(raw: Dict[str, object], config) -> Dict[str, object]:
    view: Dict[str, object] = {}
    for section in _SITE_CONFIG_VIEW_SECTIONS:
        value = raw.get(section)
        if value is None:
            continue
        view[section] = copy.deepcopy(value)
    view.setdefault(
        "runtime",
        {
            "environment": config.runtime.environment,
            "bacnet_mode": config.runtime.bacnet_mode,
            "real_writes_enabled": config.runtime.real_writes_enabled,
        },
    )
    api = dict(view.get("api") if isinstance(view.get("api"), dict) else {})
    api.update(
        {
            "enabled": config.api.enabled,
            "host": config.api.host,
            "port": config.api.port,
            "history_default_limit": config.api.history_default_limit,
        }
    )
    api.pop("config_admin_token", None)
    view["api"] = api
    view.setdefault(
        "watchdog",
        {"max_cycle_age_seconds": config.watchdog.max_cycle_age_seconds},
    )
    view.setdefault(
        "safety",
        {
            "fail_safe_output": config.safety.fail_safe_output,
            "comm_error_safe_mode_threshold": config.safety.comm_error_safe_mode_threshold,
        },
    )
    return view


def _looks_like_full_config(payload: Dict[str, object]) -> bool:
    return _FULL_CONFIG_REQUIRED_SECTIONS.issubset(payload.keys())


def _deep_merge_dicts(base: Dict[str, object], patch: Dict[str, object]) -> Dict[str, object]:
    result = copy.deepcopy(base)
    for key, value in patch.items():
        current = result.get(key)
        if isinstance(current, dict) and isinstance(value, dict):
            result[key] = _deep_merge_dicts(current, value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def _changed_top_level_sections(before: Dict[str, object], after: Dict[str, object]) -> list[str]:
    keys = set(before) | set(after)
    return sorted(str(key) for key in keys if before.get(key) != after.get(key))


def _normalize_audit_timestamp(value: object) -> Optional[str]:
    text = str(value or "").strip()
    if not text:
        return None
    if "-" in text and ":" in text:
        return text
    try:
        parsed = datetime.strptime(text, "%Y%m%dT%H%M%S%fZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return text
    return parsed.isoformat().replace("+00:00", "Z")


def _safe_nonnegative_int(value: object) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _write_json_preserve_order(path: Path, payload: Dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    os.replace(temp_path, path)


def _normalize_weather_payload(raw: Dict[str, object]) -> Dict[str, object]:
    current = raw.get("current") if isinstance(raw.get("current"), dict) else {}
    hourly = raw.get("hourly") if isinstance(raw.get("hourly"), dict) else {}
    next_hours = []
    times = hourly.get("time") if isinstance(hourly.get("time"), list) else []
    temperatures = hourly.get("temperature_2m") if isinstance(hourly.get("temperature_2m"), list) else []
    precipitation = hourly.get("precipitation_probability") if isinstance(hourly.get("precipitation_probability"), list) else []
    clouds = hourly.get("cloud_cover") if isinstance(hourly.get("cloud_cover"), list) else []
    for index, time_value in enumerate(times[:8]):
        next_hours.append(
            {
                "time": time_value,
                "temperature_c": _list_value(temperatures, index),
                "precipitation_probability_percent": _list_value(precipitation, index),
                "cloud_cover_percent": _list_value(clouds, index),
            }
        )
    code = current.get("weather_code")
    return {
        "status": "ok",
        "site": "Stuttgart",
        "source": "Open-Meteo",
        "current": {
            "time": current.get("time"),
            "temperature_c": current.get("temperature_2m"),
            "apparent_temperature_c": current.get("apparent_temperature"),
            "humidity_percent": current.get("relative_humidity_2m"),
            "precipitation_mm": current.get("precipitation"),
            "wind_speed_kmh": current.get("wind_speed_10m"),
            "weather_code": code,
            "weather_label": _weather_label(code),
        },
        "next_hours": next_hours,
    }


def _list_value(values: object, index: int) -> object:
    if not isinstance(values, list) or index >= len(values):
        return None
    return values[index]


def _weather_label(code: object) -> str:
    labels = {
        0: "klar",
        1: "überwiegend klar",
        2: "teilweise bewölkt",
        3: "bewölkt",
        45: "Nebel",
        48: "Reifnebel",
        51: "leichter Niesel",
        53: "Niesel",
        55: "starker Niesel",
        61: "leichter Regen",
        63: "Regen",
        65: "starker Regen",
        71: "leichter Schnee",
        73: "Schnee",
        75: "starker Schnee",
        80: "leichter Schauer",
        81: "Schauer",
        82: "starker Schauer",
        95: "Gewitter",
    }
    try:
        return labels.get(int(code), "wetterdaten")
    except (TypeError, ValueError):
        return "wetterdaten"


def _parse_epoch_seconds(value: object) -> Optional[float]:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _report_day_range(date_iso: str) -> Optional[tuple[str, str]]:
    """Voller Berichtstag [00:00, 24:00) als UTC-Zeitstempel, sonst None."""
    try:
        day = datetime.strptime(str(date_iso), "%Y-%m-%d")
    except (TypeError, ValueError):
        return None
    next_day = day + timedelta(days=1)
    return (
        day.strftime("%Y-%m-%dT00:00:00Z"),
        next_day.strftime("%Y-%m-%dT00:00:00Z"),
    )


def _single_value(query: Dict[str, list[str]], key: str, default: str) -> str:
    values = query.get(key)
    if not values:
        return default
    return values[0]


def _optional_single_value(query: Dict[str, list[str]], key: str) -> Optional[str]:
    values = query.get(key)
    if not values:
        return None
    return values[0]


def _multi_value(query: Dict[str, list[str]], key: str, default: list[str]) -> list[str]:
    values = query.get(key)
    if not values:
        return list(default)
    result = []
    for value in values:
        result.extend(part for part in str(value).split(",") if part)
    return result or list(default)
