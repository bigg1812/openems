import argparse
import json
import sqlite3
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


class DashboardProxyServer:
    def __init__(self, host: str, port: int, upstream_base: str, project_dir: Path):
        self.host = host
        self.port = port
        self.upstream_base = upstream_base.rstrip("/")
        self.project_dir = Path(project_dir)
        self.dashboard_dir = self.project_dir / "dashboard"
        self.price_cache_path = self.project_dir / "data" / "spotmarket" / "spotmarket_price_cache.json"
        self.runtime_db_path = self.project_dir / "data" / "runtime" / "mini_ems.sqlite"
        self.weather_cache_path = self.project_dir / "data" / "weather" / "open_meteo_weather_cache.json"

    def serve_forever(self) -> None:
        server = ThreadingHTTPServer((self.host, self.port), self._build_handler())
        try:
            print(f"Dashboard proxy listening on http://{self.host}:{self.port} -> {self.upstream_base}")
            server.serve_forever()
        finally:
            server.server_close()

    def _build_handler(self):
        proxy = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                parsed = urlparse(self.path)
                if parsed.path in ("/", "/dashboard", "/index.html"):
                    self._send_file(proxy.dashboard_dir / "index.html", "text/html; charset=utf-8")
                    return
                if parsed.path == "/dashboard.css":
                    self._send_file(proxy.dashboard_dir / "dashboard.css", "text/css; charset=utf-8")
                    return
                if parsed.path == "/dashboard.js":
                    self._send_file(proxy.dashboard_dir / "dashboard.js", "application/javascript; charset=utf-8")
                    return
                if parsed.path == "/api/status":
                    self._send_patched_status()
                    return
                if parsed.path == "/api/report/studio":
                    self._send_report_studio()
                    return
                if parsed.path == "/api/weather":
                    self._send_weather()
                    return
                if parsed.path.startswith("/api/"):
                    self._proxy_upstream()
                    return
                self._send_json({"error": "not_found", "path": parsed.path}, status=HTTPStatus.NOT_FOUND)

            def do_POST(self) -> None:
                parsed = urlparse(self.path)
                if parsed.path.startswith("/api/"):
                    self._proxy_upstream()
                    return
                self._send_json({"error": "not_found", "path": parsed.path}, status=HTTPStatus.NOT_FOUND)

            def log_message(self, _format: str, *_args) -> None:
                return None

            def _proxy_upstream(self) -> None:
                target = proxy.upstream_base + self.path
                try:
                    request = self._build_upstream_request(target)
                    with urlopen(request) as response:
                        payload = response.read()
                        content_type = response.headers.get("Content-Type", "application/octet-stream")
                        self.send_response(response.status)
                        self.send_header("Content-Type", content_type)
                        self.send_header("Cache-Control", "no-store")
                        self.send_header("Content-Length", str(len(payload)))
                        self.end_headers()
                        self.wfile.write(payload)
                except HTTPError as error:
                    payload = error.read()
                    content_type = error.headers.get("Content-Type", "application/json; charset=utf-8")
                    self.send_response(error.code)
                    self.send_header("Content-Type", content_type)
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                except URLError as error:
                    self._send_json(
                        {"error": "upstream_unreachable", "message": str(error.reason)},
                        status=HTTPStatus.BAD_GATEWAY,
                    )

            def _build_upstream_request(self, target: str):
                if self.command == "GET":
                    return target
                content_length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(content_length) if content_length > 0 else None
                headers = {}
                content_type = self.headers.get("Content-Type")
                if content_type:
                    headers["Content-Type"] = content_type
                return Request(target, data=body, headers=headers, method=self.command)

            def _send_patched_status(self) -> None:
                target = proxy.upstream_base + self.path
                try:
                    with urlopen(target) as response:
                        payload = json.loads(response.read().decode("utf-8"))
                except HTTPError as error:
                    raw = error.read().decode("utf-8", errors="replace")
                    self._send_json(
                        {"error": "upstream_http_error", "status": error.code, "message": raw},
                        status=HTTPStatus.BAD_GATEWAY,
                    )
                    return
                except URLError as error:
                    self._send_json(
                        {"error": "upstream_unreachable", "message": str(error.reason)},
                        status=HTTPStatus.BAD_GATEWAY,
                    )
                    return

                if not isinstance(payload, dict):
                    payload = {}
                payload["price_cache"] = proxy._load_json(proxy.price_cache_path)
                self._send_json(payload)

            def _send_report_studio(self) -> None:
                date_iso = proxy._default_report_date()
                report = proxy._daily_report_summary(date_iso)
                self._send_json(
                    {
                        "date": date_iso,
                        "selected_window": "day",
                        "available_windows": [
                            {"id": "day", "label": "Tag", "ready": True},
                            {"id": "week", "label": "Woche", "ready": False},
                            {"id": "month", "label": "Monat", "ready": False},
                            {"id": "custom", "label": "Frei", "ready": False},
                        ],
                        "exports": [
                            {"label": "Tagesreport CSV", "href": f"/api/report/daily.csv?date={date_iso}"},
                            {"label": "Tagesreport JSON", "href": f"/api/report/daily?date={date_iso}"},
                        ],
                        "metrics": [
                            {"id": "grid", "label": "Netz Bilanz", "value": report.get("grid_average_kw"), "unit": "kW"},
                            {"id": "price", "label": "Preis Niveau", "value": report.get("price_average_ct_kwh"), "unit": "ct/kWh"},
                            {"id": "events", "label": "BACnet Events", "value": report.get("bacnet_event_count"), "unit": ""},
                            {"id": "windows", "label": "Preisfenster", "value": report.get("window_count"), "unit": ""},
                        ],
                    }
                )

            def _send_weather(self) -> None:
                cached = proxy._load_json(proxy.weather_cache_path)
                cached_at = _parse_epoch_seconds(cached.get("fetched_at"))
                now = datetime.now(timezone.utc)
                if cached and cached_at is not None and now.timestamp() - cached_at < 900:
                    self._send_json(cached)
                    return
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
                        self._send_json(cached)
                        return
                    self._send_json({"status": "unavailable", "error": str(error), "site": "Stuttgart"})
                    return
                payload = _normalize_weather_payload(raw)
                payload["fetched_at"] = now.isoformat().replace("+00:00", "Z")
                _write_json(proxy.weather_cache_path, payload)
                self._send_json(payload)

            def _send_json(self, payload, status: HTTPStatus = HTTPStatus.OK) -> None:
                raw = json.dumps(payload, ensure_ascii=True, sort_keys=True).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def _send_file(self, path: Path, content_type: str) -> None:
                if not path.exists():
                    self._send_json({"error": "not_found", "path": str(path)}, status=HTTPStatus.NOT_FOUND)
                    return
                payload = path.read_bytes()
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", content_type)
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

        return Handler

    @staticmethod
    def _load_json(path: Path):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return raw if isinstance(raw, dict) else {}

    def _default_report_date(self) -> str:
        health = self._load_json(self.project_dir / "runtime" / "health.json")
        today_date = health.get("today_date")
        if isinstance(today_date, str) and today_date:
            return today_date
        return datetime.now().date().isoformat()

    def _daily_report_summary(self, date_iso: str):
        if not self.runtime_db_path.exists():
            return {"grid_average_kw": None, "price_average_ct_kwh": None, "bacnet_event_count": 0, "window_count": 0}
        with sqlite3.connect(str(self.runtime_db_path)) as connection:
            connection.row_factory = sqlite3.Row
            grid = connection.execute(
                """
                SELECT AVG(value) AS average_value
                FROM channel_samples
                WHERE channel_id = 'grid.active_power_kw'
                  AND direction = 'input'
                  AND cycle_id IN (SELECT cycle_id FROM cycle_runs WHERE today_date = ?)
                """,
                (date_iso,),
            ).fetchone()
            price = connection.execute(
                "SELECT AVG(price_ct_kwh) AS average_price_ct_kwh FROM price_slots WHERE date_iso = ?",
                (date_iso,),
            ).fetchone()
            events = connection.execute(
                "SELECT COUNT(*) FROM bacnet_events WHERE cycle_id IN (SELECT cycle_id FROM cycle_runs WHERE today_date = ?)",
                (date_iso,),
            ).fetchone()[0]
            windows = connection.execute(
                "SELECT COUNT(*) FROM spotmarket_windows WHERE date_iso = ?",
                (date_iso,),
            ).fetchone()[0]
        return {
            "grid_average_kw": grid["average_value"] if grid else None,
            "price_average_ct_kwh": price["average_price_ct_kwh"] if price else None,
            "bacnet_event_count": events,
            "window_count": windows,
        }


def _normalize_weather_payload(raw):
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


def _list_value(values, index: int):
    if not isinstance(values, list) or index >= len(values):
        return None
    return values[index]


def _weather_label(code) -> str:
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


def _parse_epoch_seconds(value) -> float | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    temp_path.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Mini EMS dashboard proxy")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8091, type=int)
    parser.add_argument("--upstream", default="http://127.0.0.1:8090")
    parser.add_argument("--project-dir", default=str(Path(__file__).resolve().parent))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    server = DashboardProxyServer(
        host=args.host,
        port=args.port,
        upstream_base=args.upstream,
        project_dir=Path(args.project_dir).resolve(),
    )
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
