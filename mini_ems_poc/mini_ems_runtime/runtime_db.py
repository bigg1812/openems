import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path
from typing import Any, Iterator
from typing import Dict, List, Optional, Sequence
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def _load_site_timezone():
    try:
        return ZoneInfo("Europe/Berlin")
    except ZoneInfoNotFoundError:
        return timezone.utc


SITE_TIMEZONE = _load_site_timezone()
ROLLUP_GRANULARITIES = {
    "5m": timedelta(minutes=5),
    "1h": timedelta(hours=1),
    "1d": timedelta(days=1),
}
ROLLUP_TABLES = {
    "5m": "channel_rollups_5m",
    "1h": "channel_rollups_1h",
    "1d": "channel_rollups_1d",
}
REPORT_CHANNELS = {
    "tariff.current_price_ct_kwh": {"label": "Strompreis", "unit": "ct/kWh", "group": "Markt", "kind": "average"},
    "grid.active_power_kw": {"label": "Netzleistung", "unit": "kW", "group": "Netz", "kind": "average"},
    "site.outdoor_temperature_c": {"label": "Außentemperatur", "unit": "C", "group": "Wetter", "kind": "average"},
    "site.buffer_1_top_temperature_c": {"label": "Puffer 1 oben", "unit": "C", "group": "Puffer", "kind": "average"},
    "site.buffer_1_bottom_temperature_c": {"label": "Puffer 1 unten", "unit": "C", "group": "Puffer", "kind": "average"},
    "site.buffer_2_top_temperature_c": {"label": "Puffer 2 oben", "unit": "C", "group": "Puffer", "kind": "average"},
    "site.buffer_2_bottom_temperature_c": {"label": "Puffer 2 unten", "unit": "C", "group": "Puffer", "kind": "average"},
    "site.heat_generation_flow_temperature_c": {"label": "Wärmeerzeugung Vorlauf", "unit": "C", "group": "Wärme", "kind": "average"},
    "site.heat_generation_return_temperature_c": {"label": "Wärmeerzeugung Rücklauf", "unit": "C", "group": "Wärme", "kind": "average"},
    "site.boiler_1_flow_temperature_c": {"label": "Gaskessel Vorlauf", "unit": "C", "group": "Gaskessel", "kind": "average"},
    "site.boiler_1_return_temperature_c": {"label": "Gaskessel Rücklauf", "unit": "C", "group": "Gaskessel", "kind": "average"},
    "site.boiler_2_flow_temperature_c": {"label": "Pelletkessel Vorlauf", "unit": "C", "group": "Pellet", "kind": "average"},
    "site.boiler_2_return_temperature_c": {"label": "Pelletkessel Rücklauf", "unit": "C", "group": "Pellet", "kind": "average"},
    "site.chp_flow_temperature_c": {"label": "BHKW Vorlauf", "unit": "C", "group": "BHKW", "kind": "average"},
    "site.chp_return_temperature_c": {"label": "BHKW Rücklauf", "unit": "C", "group": "BHKW", "kind": "average"},
    "site.chp_electric_energy_kwh": {"label": "BHKW elektrisch", "unit": "kWh", "group": "Energie", "kind": "energy_counter"},
    "site.chp_thermal_energy_kwh": {"label": "BHKW thermisch", "unit": "kWh", "group": "Energie", "kind": "energy_counter"},
    "site.pellet_thermal_energy_kwh": {"label": "Pellet thermisch", "unit": "kWh", "group": "Energie", "kind": "energy_counter"},
    "site.gas_thermal_energy_kwh": {"label": "Gas thermisch", "unit": "kWh", "group": "Energie", "kind": "energy_counter"},
    "ems.lockout_spotmarket": {"label": "Preissteuerung", "unit": "", "group": "Betrieb", "kind": "state"},
    "ems.lockout_grid": {"label": "Netzschutz", "unit": "", "group": "Betrieb", "kind": "state"},
}
REPORT_COMPONENTS = {
    "summary": "Kennzahlen",
    "line_chart": "Liniendiagramm",
    "table": "Datentabelle",
    "events": "Kommunikationshinweise",
}
REPORT_GRANULARITIES = ("raw", "5m", "1h", "1d")

# Betreiber-Sprache fuer Betriebszustaende (UX10, PRODUCT_UX_KONZEPT.md Abschnitt 2.2).
REPORT_STATUS_WORDING = {
    "healthy": "Normalbetrieb",
    "degraded": "Eingeschränkter Betrieb",
    "safe_mode": "Sicherer Modus",
}
# Reihenfolge fuer die Betriebszusammenfassung: guenstigster Zustand zuerst.
REPORT_STATUS_ORDER = ("healthy", "degraded", "safe_mode")
# Grund fuer den sicheren Modus in Betreiber-Sprache (UX10 Abschnitt 2.2).
REPORT_SAFE_MODE_REASON_WORDING = {
    "startup_validation": "Anlaufprüfung nach dem Start",
    "price_provider": "Strompreise nicht verfügbar",
    "grid_read": "Netzleistung nicht lesbar",
    "write_failure": "Übergabe an die Anlage gestört",
}
# Kommunikationshinweise: interne Schweregrade in Betreiber-Sprache (UX10 Abschnitt 2.3).
REPORT_SEVERITY_WORDING = {
    "info": "Hinweis",
    "warning": "mit Einschränkung",
    "error": "gestört",
    "critical": "gestört",
}


class RuntimeDatabase:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def record_cycle_bundle(
        self,
        snapshot: Dict[str, object],
        input_reads: Optional[Dict[str, Dict[str, object]]] = None,
        output_policies: Optional[Dict[str, Dict[str, str]]] = None,
        price_days: Optional[Sequence[Dict[str, object]]] = None,
        spotmarket_plan: Optional[Dict[str, object]] = None,
    ) -> None:
        cycle_id = str(snapshot.get("cycle_id"))
        timestamp = str(snapshot.get("timestamp"))
        with self._connection() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO cycle_runs (
                    cycle_id,
                    timestamp,
                    status,
                    safe_mode_reason,
                    degraded_reason,
                    current_slot_label,
                    current_price_ct_kwh,
                    today_date,
                    tomorrow_date,
                    spotmarket_active_now,
                    spotmarket_source,
                    grid_active_power_kw,
                    operator_message,
                    snapshot_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    cycle_id,
                    timestamp,
                    str(snapshot.get("status")),
                    _optional_text(snapshot.get("safe_mode_reason")),
                    _optional_text(snapshot.get("degraded_reason")),
                    _optional_text(snapshot.get("current_slot_label")),
                    _optional_float(snapshot.get("current_price_ct_kwh")),
                    _optional_text(snapshot.get("today_date")),
                    _optional_text(snapshot.get("tomorrow_date")),
                    _optional_bool(snapshot.get("spotmarket_active_now")),
                    _optional_text(snapshot.get("spotmarket_source")),
                    _extract_grid_power(input_reads),
                    _optional_text(snapshot.get("operator_message")),
                    json.dumps(snapshot, ensure_ascii=True, sort_keys=True),
                ),
            )
            connection.execute("DELETE FROM channel_samples WHERE cycle_id = ?", (cycle_id,))
            connection.execute("DELETE FROM bacnet_events WHERE cycle_id = ?", (cycle_id,))

            for channel_id, diagnostic in (input_reads or {}).items():
                self._insert_channel_sample(
                    connection,
                    cycle_id=cycle_id,
                    timestamp=timestamp,
                    channel_id=channel_id,
                    direction="input",
                    value=diagnostic.get("value"),
                    desired_value=None,
                    is_confirmed=True if diagnostic.get("status") == "ok" else False,
                    confirmation_mode="read",
                    criticality="critical" if channel_id == "grid.active_power_kw" else "noncritical",
                    source="bacnet_read",
                    error=diagnostic.get("error"),
                    readback_value=None,
                )
                if diagnostic.get("status") == "ok" and diagnostic.get("value") is not None:
                    self._refresh_rollups_for_sample(
                        connection,
                        channel_id=channel_id,
                        timestamp=timestamp,
                    )
                if diagnostic.get("status") != "ok":
                    self._insert_bacnet_event(
                        connection,
                        timestamp=timestamp,
                        cycle_id=cycle_id,
                        channel_id=channel_id,
                        event_type="read_failure",
                        severity="warning",
                        message=str(diagnostic.get("error") or "read warning"),
                        details=diagnostic,
                    )

            outputs = snapshot.get("outputs")
            write_results = snapshot.get("write_results")
            desired_outputs = snapshot.get("desired_outputs")
            if isinstance(outputs, dict):
                for channel_id, output_state in outputs.items():
                    state = output_state if isinstance(output_state, dict) else {}
                    result = write_results.get(channel_id, {}) if isinstance(write_results, dict) else {}
                    policy = output_policies.get(channel_id, {}) if isinstance(output_policies, dict) else {}
                    self._insert_channel_sample(
                        connection,
                        cycle_id=cycle_id,
                        timestamp=timestamp,
                        channel_id=channel_id,
                        direction="output",
                        value=state.get("value"),
                        desired_value=desired_outputs.get(channel_id) if isinstance(desired_outputs, dict) else None,
                        is_confirmed=state.get("is_confirmed"),
                        confirmation_mode=result.get("confirmation_source") or policy.get("confirmation_mode"),
                        criticality=policy.get("criticality"),
                        source=result.get("confirmation_source") or "state",
                        error=result.get("error") or state.get("last_error"),
                        readback_value=result.get("readback_value"),
                    )
                    if result.get("error"):
                        self._insert_bacnet_event(
                            connection,
                            timestamp=timestamp,
                            cycle_id=cycle_id,
                            channel_id=channel_id,
                            event_type="write_failure",
                            severity="critical" if policy.get("criticality") == "critical" else "warning",
                            message=str(result.get("error")),
                            details=result,
                        )
                    elif state.get("value") is not None:
                        self._refresh_rollups_for_sample(
                            connection,
                            channel_id=channel_id,
                            timestamp=timestamp,
                        )

            if price_days:
                for day_payload in price_days:
                    self._upsert_price_day(connection, day_payload)

            if spotmarket_plan:
                self._upsert_spotmarket_plan(connection, spotmarket_plan)

    def get_channel_history(
        self,
        channel_id: str,
        limit: int,
        granularity: str = "raw",
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> List[Dict[str, object]]:
        granularity = str(granularity or "raw").lower()
        with self._connection() as connection:
            if granularity == "raw":
                query = """
                    SELECT timestamp, channel_id, direction, value, desired_value, is_confirmed,
                           confirmation_mode, criticality, source, error, readback_value
                    FROM channel_samples
                    WHERE channel_id = ?
                """
                params: List[object] = [channel_id]
                if start:
                    query += " AND timestamp >= ?"
                    params.append(start)
                if end:
                    query += " AND timestamp < ?"
                    params.append(end)
                query += " ORDER BY timestamp DESC, id DESC LIMIT ?"
                params.append(int(limit))
                rows = connection.execute(query, params).fetchall()
            else:
                table_name = _rollup_table_name(granularity)
                query = """
                    SELECT
                        bucket_start AS timestamp,
                        bucket_end,
                        channel_id,
                        sample_count,
                        min_value,
                        max_value,
                        average_value,
                        last_value,
                        last_sample_timestamp
                    FROM {table_name}
                    WHERE channel_id = ?
                """.format(table_name=table_name)
                params = [channel_id]
                if start:
                    query += " AND bucket_start >= ?"
                    params.append(start)
                if end:
                    query += " AND bucket_start < ?"
                    params.append(end)
                query += " ORDER BY bucket_start DESC LIMIT ?"
                params.append(int(limit))
                rows = connection.execute(query, params).fetchall()
                if not rows:
                    rows = self.get_channel_history(
                        channel_id,
                        limit=limit,
                        granularity="raw",
                        start=start,
                        end=end,
                    )
        return [dict(row) for row in rows]

    def record_external_channel_samples(
        self,
        samples: Sequence[Dict[str, object]],
        *,
        cycle_id: str,
        timestamp: str,
        source: str = "external",
    ) -> None:
        with self._connection() as connection:
            for sample in samples:
                channel_id = _optional_text(sample.get("channel_id"))
                if not channel_id:
                    continue
                self._insert_channel_sample(
                    connection,
                    cycle_id=cycle_id,
                    timestamp=timestamp,
                    channel_id=channel_id,
                    direction="input",
                    value=sample.get("value"),
                    desired_value=None,
                    is_confirmed=sample.get("is_confirmed", True),
                    confirmation_mode="import",
                    criticality="noncritical",
                    source=source,
                    error=sample.get("error"),
                    readback_value=None,
                )
                if sample.get("error") is None and sample.get("value") is not None:
                    self._refresh_rollups_for_sample(
                        connection,
                        channel_id=channel_id,
                        timestamp=timestamp,
                    )

    def get_recent_cycles(self, limit: int = 20) -> List[Dict[str, object]]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT cycle_id, timestamp, status, safe_mode_reason, degraded_reason,
                       current_slot_label, current_price_ct_kwh, today_date, spotmarket_active_now,
                       spotmarket_source, grid_active_power_kw
                FROM cycle_runs
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (int(limit),),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_daily_report(self, date_iso: str) -> Dict[str, object]:
        with self._connection() as connection:
            cycle_count = connection.execute(
                "SELECT COUNT(*) FROM cycle_runs WHERE today_date = ?",
                (date_iso,),
            ).fetchone()[0]
            status_rows = connection.execute(
                """
                SELECT status, COUNT(*) AS count
                FROM cycle_runs
                WHERE today_date = ?
                GROUP BY status
                ORDER BY status
                """,
                (date_iso,),
            ).fetchall()
            grid_row = connection.execute(
                """
                SELECT
                    COUNT(*) AS sample_count,
                    MIN(value) AS min_value,
                    MAX(value) AS max_value,
                    AVG(value) AS average_value
                FROM channel_samples
                WHERE channel_id = 'grid.active_power_kw'
                  AND direction = 'input'
                  AND cycle_id IN (SELECT cycle_id FROM cycle_runs WHERE today_date = ?)
                """,
                (date_iso,),
            ).fetchone()
            price_row = connection.execute(
                """
                SELECT
                    COUNT(*) AS slot_count,
                    MIN(price_ct_kwh) AS min_price_ct_kwh,
                    MAX(price_ct_kwh) AS max_price_ct_kwh,
                    AVG(price_ct_kwh) AS average_price_ct_kwh
                FROM price_slots
                WHERE date_iso = ?
                """,
                (date_iso,),
            ).fetchone()
            windows = connection.execute(
                """
                SELECT date_iso, start_slot, end_slot_exclusive, start_label, end_label_exclusive,
                       length_quarters, min_price_ct_kwh, max_price_ct_kwh, source_day_kind, generated_at
                FROM spotmarket_windows
                WHERE date_iso = ?
                ORDER BY start_slot
                """,
                (date_iso,),
            ).fetchall()
            bacnet_event_count = connection.execute(
                """
                SELECT COUNT(*)
                FROM bacnet_events
                WHERE cycle_id IN (SELECT cycle_id FROM cycle_runs WHERE today_date = ?)
                """,
                (date_iso,),
            ).fetchone()[0]
            recent_events = connection.execute(
                """
                SELECT timestamp, channel_id, event_type, severity, message
                FROM bacnet_events
                WHERE cycle_id IN (SELECT cycle_id FROM cycle_runs WHERE today_date = ?)
                ORDER BY timestamp DESC, id DESC
                LIMIT 20
                """,
                (date_iso,),
            ).fetchall()

        return {
            "date": date_iso,
            "cycle_count": cycle_count,
            "status_counts": {row["status"]: row["count"] for row in status_rows},
            "grid_active_power_kw": {
                "sample_count": grid_row["sample_count"],
                "min": _optional_float(grid_row["min_value"]),
                "max": _optional_float(grid_row["max_value"]),
                "average": _optional_float(grid_row["average_value"]),
            },
            "price_ct_kwh": {
                "slot_count": price_row["slot_count"],
                "min": _optional_float(price_row["min_price_ct_kwh"]),
                "max": _optional_float(price_row["max_price_ct_kwh"]),
                "average": _optional_float(price_row["average_price_ct_kwh"]),
            },
            "spotmarket_windows": [dict(row) for row in windows],
            "bacnet_event_count": bacnet_event_count,
            "recent_bacnet_events": [dict(row) for row in recent_events],
        }

    def get_report_studio_payload(self, date_iso: str) -> Dict[str, object]:
        report = self.get_daily_report(date_iso)
        return {
            "date": date_iso,
            "selected_window": "day",
            "available_windows": [
                {"id": "day", "label": "Tag", "ready": True},
                {"id": "week", "label": "Woche", "ready": False},
                {"id": "month", "label": "Monat", "ready": False},
                {"id": "custom", "label": "Frei", "ready": False},
            ],
            "exports": [
                {"label": "Tagesbericht CSV", "href": "/api/report/daily.csv?date={0}".format(date_iso)},
                {"label": "Tagesbericht JSON", "href": "/api/report/daily?date={0}".format(date_iso)},
            ],
            "metrics": [
                {"id": "price", "label": "Preisniveau", "value": report["price_ct_kwh"].get("average"), "unit": "ct/kWh"},
                {"id": "energy", "label": "Energiezähler", "value": self._energy_counter_total("{0}T00:00:00Z".format(date_iso), "{0}T23:59:59Z".format(date_iso)), "unit": "kWh"},
                {"id": "events", "label": "Kommunikationshinweise", "value": report.get("bacnet_event_count"), "unit": ""},
                {"id": "windows", "label": "Preisfenster", "value": len(report.get("spotmarket_windows", [])), "unit": ""},
            ],
            "next_steps": [
                "Energiezähler BHKW, Pellet und Gas als Standardbericht prüfen",
                "PDF-Layout mit Betreiberlogo und Monatsvergleich erweitern",
                "Automatischen Wochenbericht terminieren",
            ],
            "config": _normalize_report_config({"start": "{0}T00:00:00Z".format(date_iso), "end": "{0}T23:59:59Z".format(date_iso)}),
        }

    def build_configurable_report(self, config: Dict[str, object]) -> Dict[str, object]:
        normalized = _normalize_report_config(config)
        sections = []
        for section_config in normalized["sections"]:
            component = section_config["component"]
            if component == "summary":
                sections.append(self._build_report_summary_section(normalized, section_config))
            elif component == "line_chart":
                sections.append(self._build_report_chart_section(normalized, section_config))
            elif component == "table":
                sections.append(self._build_report_table_section(normalized, section_config))
            elif component == "events":
                sections.append(self._build_report_events_section(normalized, section_config))
        return {
            "config": normalized,
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "title": normalized["title"],
            "subtitle": "{0} bis {1}, Zeitraster {2}".format(
                normalized["start"],
                normalized["end"],
                normalized["granularity"],
            ),
            "sections": sections,
            "export_pipeline": ["Daten", "Python-Aufbereitung", "HTML-Template", "PDF-Export"],
        }

    def render_report_html(self, config: Dict[str, object], template_path: Optional[Path] = None) -> str:
        report = self.build_configurable_report(config)
        overview = self.build_report_overview(report["config"])
        if template_path is not None:
            try:
                from jinja2 import Environment, FileSystemLoader, select_autoescape

                environment = Environment(
                    loader=FileSystemLoader(str(template_path.parent)),
                    autoescape=select_autoescape(["html", "xml"]),
                )
                template = environment.get_template(template_path.name)
                return template.render(report=report, overview=overview)
            except ImportError:
                pass
        return _render_report_html_fallback(report, overview)

    def build_report_overview(self, normalized: Dict[str, object]) -> Dict[str, object]:
        """Leitet aus dem Berichtszeitraum eine kundentaugliche Tagesbericht-Kopfzeile ab.

        Rein lesend/aufbereitend: nutzt dieselben Tagesreport-Daten wie
        ``get_daily_report`` und formatiert sie in Betreiber-Sprache (UX1/UX10).
        Aendert kein Schema und keinen bestehenden API-Vertrag.
        """
        start = str(normalized.get("start") or "")
        end = str(normalized.get("end") or "")
        date_iso = start[:10] if len(start) >= 10 else datetime.now(SITE_TIMEZONE).date().isoformat()
        daily = self.get_daily_report(date_iso)

        status_counts = daily.get("status_counts", {}) or {}
        cycle_count = int(daily.get("cycle_count") or 0)
        status_lines = []
        for status_key in REPORT_STATUS_ORDER:
            count = int(status_counts.get(status_key, 0) or 0)
            if count:
                status_lines.append({"label": REPORT_STATUS_WORDING[status_key], "count": count})
        # Unbekannte Zustaende ehrlich, aber ohne interne Rohbegriffe ergaenzen.
        for status_key, count in sorted(status_counts.items()):
            if status_key in REPORT_STATUS_WORDING:
                continue
            status_lines.append({"label": "Sonstiger Zustand", "count": int(count or 0)})

        price = daily.get("price_ct_kwh", {}) or {}
        grid = daily.get("grid_active_power_kw", {}) or {}
        windows = daily.get("spotmarket_windows", []) or []
        window_labels = [
            "{0}-{1}".format(window.get("start_label", "?"), window.get("end_label_exclusive", "?"))
            for window in windows
        ]

        events = daily.get("recent_bacnet_events", []) or []
        event_lines = []
        for event in events[:5]:
            message = _optional_text(event.get("message"))
            severity = str(event.get("severity") or "").lower()
            event_lines.append(
                {
                    "time": _format_time_de(event.get("timestamp")),
                    "severity": REPORT_SEVERITY_WORDING.get(severity, "Hinweis"),
                    "message": message or "Meldung aus dem Datenaustausch mit der Anlage",
                }
            )

        return {
            "title": "Tagesbericht",
            "location": _report_location_name(normalized),
            "date_label": _format_date_de(date_iso),
            "period_label": _format_period_de(start, end),
            "generated_label": _format_datetime_de(
                datetime.now(SITE_TIMEZONE).isoformat()
            ),
            "cycle_count": cycle_count,
            "status_lines": status_lines,
            "main_message": _report_main_message(cycle_count, status_counts, daily.get("bacnet_event_count") or 0),
            "price": {
                "average": _optional_float(price.get("average")),
                "min": _optional_float(price.get("min")),
                "max": _optional_float(price.get("max")),
                "slot_count": int(price.get("slot_count") or 0),
            },
            "grid": self._overview_grid_stats(grid, date_iso),
            "windows": window_labels,
            "event_count": int(daily.get("bacnet_event_count") or 0),
            "events": event_lines,
        }

    def _overview_grid_stats(self, grid: Dict[str, object], date_iso: str) -> Dict[str, object]:
        """Netzleistung fuer den Tagesbericht-Kopf, rein lesend.

        Bevorzugt die Kanal-Messwerte aus dem Tagesreport; liegen dort keine
        Einzelmesswerte vor (z. B. weil die Netzleistung nur je Lauf im
        Zyklusprotokoll steht), werden ersatzweise die Werte der Laeufe des
        Tages aggregiert. Der bestehende JSON-/CSV-Vertrag bleibt unberuehrt.
        """
        sample_count = int(grid.get("sample_count") or 0)
        if sample_count > 0:
            return {
                "average": _optional_float(grid.get("average")),
                "min": _optional_float(grid.get("min")),
                "max": _optional_float(grid.get("max")),
                "sample_count": sample_count,
            }
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT
                    COUNT(grid_active_power_kw) AS sample_count,
                    MIN(grid_active_power_kw) AS min_value,
                    MAX(grid_active_power_kw) AS max_value,
                    AVG(grid_active_power_kw) AS average_value
                FROM cycle_runs
                WHERE today_date = ? AND grid_active_power_kw IS NOT NULL
                """,
                (date_iso,),
            ).fetchone()
        return {
            "average": _optional_float(row["average_value"]),
            "min": _optional_float(row["min_value"]),
            "max": _optional_float(row["max_value"]),
            "sample_count": int(row["sample_count"] or 0),
        }

    def render_daily_report_csv(self, date_iso: str) -> str:
        report = self.get_daily_report(date_iso)
        lines = [
            "section,key,value",
            "summary,date,{0}".format(report["date"]),
            "summary,cycle_count,{0}".format(report["cycle_count"]),
            "summary,bacnet_event_count,{0}".format(report["bacnet_event_count"]),
        ]
        for status, count in sorted(report["status_counts"].items()):
            lines.append("status_counts,{0},{1}".format(status, count))
        price = report["price_ct_kwh"]
        for key in ("slot_count", "min", "max", "average"):
            lines.append("price_ct_kwh,{0},{1}".format(key, price.get(key)))
        for index, window in enumerate(report["spotmarket_windows"], start=1):
            lines.append(
                "spotmarket_window_{0},range,{1}-{2}".format(
                    index,
                    window["start_label"],
                    window["end_label_exclusive"],
                )
            )
        return "\n".join(lines) + "\n"

    def _build_report_summary_section(self, normalized: Dict[str, Any], section_config: Dict[str, str]) -> Dict[str, object]:
        cards = []
        for channel_id in normalized["channels"]:
            stats = self._channel_stats(channel_id, normalized["start"], normalized["end"])
            meta = REPORT_CHANNELS.get(channel_id, {"label": "Datenpunkt", "unit": ""})
            display = _summary_display_value(stats, meta)
            cards.append(
                {
                    "channel_id": channel_id,
                    "label": meta["label"],
                    "unit": meta["unit"],
                    "group": meta.get("group", "EMS"),
                    "kind": meta.get("kind", "average"),
                    "sample_count": stats["sample_count"],
                    "min": _optional_float(stats["min_value"]),
                    "max": _optional_float(stats["max_value"]),
                    "average": _optional_float(stats["average_value"]),
                    "first": _optional_float(stats["first_value"]),
                    "last": _optional_float(stats["last_value"]),
                    "delta": display["delta"],
                    "display_value": display["value"],
                    "display_label": display["label"],
                    "detail": display["detail"],
                }
            )
        return {"id": section_config["id"], "component": "summary", "title": section_config["title"], "cards": cards}

    def _build_report_chart_section(self, normalized: Dict[str, Any], section_config: Dict[str, str]) -> Dict[str, object]:
        series = []
        for channel_id in normalized["channels"]:
            rows = self.get_channel_history(
                channel_id,
                limit=normalized["limit"],
                granularity=normalized["granularity"],
                start=normalized["start"],
                end=normalized["end"],
            )
            meta = REPORT_CHANNELS.get(channel_id, {"label": "Datenpunkt", "unit": ""})
            series.append(
                {
                    "channel_id": channel_id,
                    "label": meta["label"],
                    "unit": meta["unit"],
                    "points": [
                        {"timestamp": row["timestamp"], "value": _optional_float(_history_row_value(row))}
                        for row in reversed(rows)
                    ],
                }
            )
        return {"id": section_config["id"], "component": "line_chart", "title": section_config["title"], "series": series}

    def _build_report_table_section(self, normalized: Dict[str, Any], section_config: Dict[str, str]) -> Dict[str, object]:
        rows = []
        for channel_id in normalized["channels"]:
            meta = REPORT_CHANNELS.get(channel_id, {"label": "Datenpunkt", "unit": ""})
            for row in self.get_channel_history(
                channel_id,
                limit=min(normalized["limit"], 200),
                granularity=normalized["granularity"],
                start=normalized["start"],
                end=normalized["end"],
            ):
                rows.append(
                    {
                        "timestamp": row["timestamp"],
                        "channel_id": channel_id,
                        "label": meta["label"],
                        "value": _optional_float(_history_row_value(row)),
                        "unit": meta["unit"],
                    }
                )
        rows.sort(key=lambda row: str(row["timestamp"]), reverse=True)
        return {"id": section_config["id"], "component": "table", "title": section_config["title"], "rows": rows[:200]}

    def _build_report_events_section(self, normalized: Dict[str, Any], section_config: Dict[str, str]) -> Dict[str, object]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT timestamp, channel_id, event_type, severity, message
                FROM bacnet_events
                WHERE timestamp >= ? AND timestamp < ?
                ORDER BY timestamp DESC, id DESC
                LIMIT 50
                """,
                (normalized["start"], normalized["end"]),
            ).fetchall()
        return {"id": section_config["id"], "component": "events", "title": section_config["title"], "rows": [dict(row) for row in rows]}

    def _channel_stats(self, channel_id: str, start: str, end: str) -> sqlite3.Row:
        with self._connection() as connection:
            return connection.execute(
                """
                SELECT
                    COUNT(*) AS sample_count,
                    MIN(value) AS min_value,
                    MAX(value) AS max_value,
                    AVG(value) AS average_value,
                    (
                        SELECT value
                        FROM channel_samples first
                        WHERE first.channel_id = ?
                          AND first.error IS NULL
                          AND first.value IS NOT NULL
                          AND first.timestamp >= ?
                          AND first.timestamp < ?
                        ORDER BY first.timestamp ASC, first.id ASC
                        LIMIT 1
                    ) AS first_value,
                    (
                        SELECT value
                        FROM channel_samples latest
                        WHERE latest.channel_id = ?
                          AND latest.error IS NULL
                          AND latest.value IS NOT NULL
                          AND latest.timestamp >= ?
                          AND latest.timestamp < ?
                        ORDER BY latest.timestamp DESC, latest.id DESC
                        LIMIT 1
                    ) AS last_value
                FROM channel_samples
                WHERE channel_id = ?
                  AND error IS NULL
                  AND value IS NOT NULL
                  AND timestamp >= ?
                  AND timestamp < ?
                """,
                (channel_id, start, end, channel_id, start, end, channel_id, start, end),
            ).fetchone()

    def _energy_counter_total(self, start: str, end: str) -> Optional[float]:
        total = 0.0
        has_value = False
        for channel_id, metadata in REPORT_CHANNELS.items():
            if metadata.get("kind") != "energy_counter":
                continue
            stats = self._channel_stats(channel_id, start, end)
            display = _summary_display_value(stats, metadata)
            if display["delta"] is not None:
                total += float(display["delta"])
                has_value = True
        return total if has_value else None

    def _ensure_schema(self) -> None:
        with self._connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS cycle_runs (
                    cycle_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    status TEXT NOT NULL,
                    safe_mode_reason TEXT,
                    degraded_reason TEXT,
                    current_slot_label TEXT,
                    current_price_ct_kwh REAL,
                    today_date TEXT,
                    tomorrow_date TEXT,
                    spotmarket_active_now INTEGER,
                    spotmarket_source TEXT,
                    grid_active_power_kw REAL,
                    operator_message TEXT,
                    snapshot_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS channel_samples (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cycle_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    channel_id TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    value REAL,
                    desired_value REAL,
                    is_confirmed INTEGER,
                    confirmation_mode TEXT,
                    criticality TEXT,
                    source TEXT,
                    error TEXT,
                    readback_value REAL
                );
                CREATE INDEX IF NOT EXISTS idx_channel_samples_channel_timestamp
                    ON channel_samples (channel_id, timestamp DESC);

                CREATE TABLE IF NOT EXISTS price_slots (
                    date_iso TEXT NOT NULL,
                    slot_index INTEGER NOT NULL,
                    slot_label TEXT NOT NULL,
                    price_ct_kwh REAL,
                    source_day_kind TEXT NOT NULL,
                    captured_at TEXT NOT NULL,
                    PRIMARY KEY (date_iso, slot_index)
                );

                CREATE TABLE IF NOT EXISTS spotmarket_windows (
                    date_iso TEXT NOT NULL,
                    start_slot INTEGER NOT NULL,
                    end_slot_exclusive INTEGER NOT NULL,
                    start_label TEXT NOT NULL,
                    end_label_exclusive TEXT NOT NULL,
                    length_quarters INTEGER NOT NULL,
                    min_price_ct_kwh REAL,
                    max_price_ct_kwh REAL,
                    source_day_kind TEXT NOT NULL,
                    generated_at TEXT NOT NULL,
                    PRIMARY KEY (date_iso, start_slot, end_slot_exclusive)
                );

                CREATE TABLE IF NOT EXISTS bacnet_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    cycle_id TEXT,
                    channel_id TEXT,
                    event_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    message TEXT NOT NULL,
                    details_json TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_bacnet_events_cycle
                    ON bacnet_events (cycle_id, timestamp DESC);

                CREATE TABLE IF NOT EXISTS channel_rollups_5m (
                    channel_id TEXT NOT NULL,
                    bucket_start TEXT NOT NULL,
                    bucket_end TEXT NOT NULL,
                    sample_count INTEGER NOT NULL,
                    min_value REAL,
                    max_value REAL,
                    average_value REAL,
                    last_value REAL,
                    last_sample_timestamp TEXT,
                    PRIMARY KEY (channel_id, bucket_start)
                );
                CREATE INDEX IF NOT EXISTS idx_channel_rollups_5m_channel_bucket
                    ON channel_rollups_5m (channel_id, bucket_start DESC);

                CREATE TABLE IF NOT EXISTS channel_rollups_1h (
                    channel_id TEXT NOT NULL,
                    bucket_start TEXT NOT NULL,
                    bucket_end TEXT NOT NULL,
                    sample_count INTEGER NOT NULL,
                    min_value REAL,
                    max_value REAL,
                    average_value REAL,
                    last_value REAL,
                    last_sample_timestamp TEXT,
                    PRIMARY KEY (channel_id, bucket_start)
                );
                CREATE INDEX IF NOT EXISTS idx_channel_rollups_1h_channel_bucket
                    ON channel_rollups_1h (channel_id, bucket_start DESC);

                CREATE TABLE IF NOT EXISTS channel_rollups_1d (
                    channel_id TEXT NOT NULL,
                    bucket_start TEXT NOT NULL,
                    bucket_end TEXT NOT NULL,
                    sample_count INTEGER NOT NULL,
                    min_value REAL,
                    max_value REAL,
                    average_value REAL,
                    last_value REAL,
                    last_sample_timestamp TEXT,
                    PRIMARY KEY (channel_id, bucket_start)
                );
                CREATE INDEX IF NOT EXISTS idx_channel_rollups_1d_channel_bucket
                    ON channel_rollups_1d (channel_id, bucket_start DESC);
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.path))
        connection.row_factory = sqlite3.Row
        return connection

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _insert_channel_sample(
        self,
        connection: sqlite3.Connection,
        *,
        cycle_id: str,
        timestamp: str,
        channel_id: str,
        direction: str,
        value: object,
        desired_value: object,
        is_confirmed: object,
        confirmation_mode: Optional[str],
        criticality: Optional[str],
        source: Optional[str],
        error: object,
        readback_value: object,
    ) -> None:
        connection.execute(
            """
            INSERT INTO channel_samples (
                cycle_id,
                timestamp,
                channel_id,
                direction,
                value,
                desired_value,
                is_confirmed,
                confirmation_mode,
                criticality,
                source,
                error,
                readback_value
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                cycle_id,
                timestamp,
                channel_id,
                direction,
                _normalize_numeric_value(value),
                _normalize_numeric_value(desired_value),
                _optional_bool(is_confirmed),
                confirmation_mode,
                criticality,
                source,
                _optional_text(error),
                _optional_float(readback_value),
            ),
        )

    def _insert_bacnet_event(
        self,
        connection: sqlite3.Connection,
        *,
        timestamp: str,
        cycle_id: Optional[str],
        channel_id: Optional[str],
        event_type: str,
        severity: str,
        message: str,
        details: Optional[Dict[str, object]] = None,
    ) -> None:
        connection.execute(
            """
            INSERT INTO bacnet_events (
                timestamp,
                cycle_id,
                channel_id,
                event_type,
                severity,
                message,
                details_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                timestamp,
                cycle_id,
                channel_id,
                event_type,
                severity,
                message,
                json.dumps(details, ensure_ascii=True, sort_keys=True) if details is not None else None,
            ),
        )

    def _upsert_price_day(self, connection: sqlite3.Connection, day_payload: Dict[str, object]) -> None:
        date_iso = _optional_text(day_payload.get("date"))
        if not date_iso:
            return
        slots = day_payload.get("slots")
        captured_at = _optional_text(day_payload.get("captured_at")) or ""
        source_day_kind = _optional_text(day_payload.get("day_kind")) or "unknown"
        if not isinstance(slots, list):
            return
        for slot_index, value in enumerate(slots):
            connection.execute(
                """
                INSERT OR REPLACE INTO price_slots (
                    date_iso,
                    slot_index,
                    slot_label,
                    price_ct_kwh,
                    source_day_kind,
                    captured_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    date_iso,
                    slot_index,
                    _slot_label(slot_index),
                    _optional_float(value),
                    source_day_kind,
                    captured_at,
                ),
            )

    def _upsert_spotmarket_plan(self, connection: sqlite3.Connection, plan_payload: Dict[str, object]) -> None:
        generated_at = _optional_text(plan_payload.get("generated_at")) or ""
        for day_kind in ("today", "tomorrow"):
            day_payload = plan_payload.get(day_kind)
            if not isinstance(day_payload, dict):
                continue
            date_iso = _optional_text(day_payload.get("date"))
            if not date_iso:
                continue
            connection.execute(
                "DELETE FROM spotmarket_windows WHERE date_iso = ?",
                (date_iso,),
            )
            for window in day_payload.get("windows", []):
                if not isinstance(window, dict):
                    continue
                connection.execute(
                    """
                    INSERT OR REPLACE INTO spotmarket_windows (
                        date_iso,
                        start_slot,
                        end_slot_exclusive,
                        start_label,
                        end_label_exclusive,
                        length_quarters,
                        min_price_ct_kwh,
                        max_price_ct_kwh,
                        source_day_kind,
                        generated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        date_iso,
                        int(window["start_slot"]),
                        int(window["end_slot_exclusive"]),
                        str(window["start_label"]),
                        str(window["end_label_exclusive"]),
                        int(window["length_quarters"]),
                        _optional_float(window.get("min_price_ct_kwh")),
                        _optional_float(window.get("max_price_ct_kwh")),
                        day_kind,
                        generated_at,
                    ),
                )

    def _refresh_rollups_for_sample(
        self,
        connection: sqlite3.Connection,
        *,
        channel_id: str,
        timestamp: str,
    ) -> None:
        sample_dt_utc = _parse_iso_datetime_utc(timestamp)
        for granularity in ROLLUP_GRANULARITIES:
            bucket_start_utc, bucket_end_utc = _bucket_bounds_utc(sample_dt_utc, granularity)
            bucket_start_iso = _utc_iso(bucket_start_utc)
            bucket_end_iso = _utc_iso(bucket_end_utc)
            aggregate = connection.execute(
                """
                SELECT
                    COUNT(*) AS sample_count,
                    MIN(value) AS min_value,
                    MAX(value) AS max_value,
                    AVG(value) AS average_value
                FROM channel_samples
                WHERE channel_id = ?
                  AND error IS NULL
                  AND value IS NOT NULL
                  AND timestamp >= ?
                  AND timestamp < ?
                """,
                (channel_id, bucket_start_iso, bucket_end_iso),
            ).fetchone()
            sample_count = int(aggregate["sample_count"] or 0)
            table_name = _rollup_table_name(granularity)
            if sample_count == 0:
                connection.execute(
                    "DELETE FROM {0} WHERE channel_id = ? AND bucket_start = ?".format(table_name),
                    (channel_id, bucket_start_iso),
                )
                continue

            latest_sample = connection.execute(
                """
                SELECT timestamp, value
                FROM channel_samples
                WHERE channel_id = ?
                  AND error IS NULL
                  AND value IS NOT NULL
                  AND timestamp >= ?
                  AND timestamp < ?
                ORDER BY timestamp DESC, id DESC
                LIMIT 1
                """,
                (channel_id, bucket_start_iso, bucket_end_iso),
            ).fetchone()
            connection.execute(
                """
                INSERT OR REPLACE INTO {table_name} (
                    channel_id,
                    bucket_start,
                    bucket_end,
                    sample_count,
                    min_value,
                    max_value,
                    average_value,
                    last_value,
                    last_sample_timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """.format(table_name=table_name),
                (
                    channel_id,
                    bucket_start_iso,
                    bucket_end_iso,
                    sample_count,
                    _optional_float(aggregate["min_value"]),
                    _optional_float(aggregate["max_value"]),
                    _optional_float(aggregate["average_value"]),
                    _optional_float(latest_sample["value"]) if latest_sample is not None else None,
                    latest_sample["timestamp"] if latest_sample is not None else None,
                ),
            )


def _extract_grid_power(input_reads: Optional[Dict[str, Dict[str, object]]]) -> Optional[float]:
    if not isinstance(input_reads, dict):
        return None
    grid = input_reads.get("grid.active_power_kw")
    if not isinstance(grid, dict):
        return None
    return _optional_float(grid.get("value"))


def _summary_display_value(stats: sqlite3.Row, meta: Dict[str, object]) -> Dict[str, object]:
    sample_count = int(stats["sample_count"] or 0)
    first = _optional_float(stats["first_value"])
    last = _optional_float(stats["last_value"])
    average = _optional_float(stats["average_value"])
    minimum = _optional_float(stats["min_value"])
    maximum = _optional_float(stats["max_value"])
    kind = str(meta.get("kind") or "average")

    if kind == "energy_counter":
        delta = None
        if first is not None and last is not None and sample_count > 1:
            raw_delta = last - first
            delta = raw_delta if raw_delta >= 0 else None
        if delta is not None:
            return {
                "value": delta,
                "delta": delta,
                "label": "Erzeugung im Zeitraum",
                "detail": "Zähler {0} -> {1}".format(_format_report_number(first), _format_report_number(last)),
            }
        return {
            "value": last,
            "delta": None,
            "label": "Zählerstand",
            "detail": "{0} Messpunkte".format(sample_count),
        }

    if kind == "state":
        return {
            "value": last,
            "delta": None,
            "label": "Letzter Zustand",
            "detail": "{0} Messpunkte".format(sample_count),
        }

    return {
        "value": average,
        "delta": None,
        "label": "Mittelwert",
        "detail": "Min {0} / Max {1}".format(_format_report_number(minimum), _format_report_number(maximum)),
    }


def _normalize_report_config(config: Dict[str, object]) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    default_end = now.isoformat().replace("+00:00", "Z")
    default_start = (now - timedelta(days=1)).isoformat().replace("+00:00", "Z")
    start = _optional_text(config.get("start")) or default_start
    end = _optional_text(config.get("end")) or default_end
    granularity = (_optional_text(config.get("granularity")) or "5m").lower()
    if granularity not in REPORT_GRANULARITIES:
        granularity = "5m"
    channels = config.get("channels")
    if not isinstance(channels, list) or not channels:
        channels = [
            "site.chp_electric_energy_kwh",
            "site.chp_thermal_energy_kwh",
            "site.pellet_thermal_energy_kwh",
            "site.gas_thermal_energy_kwh",
            "tariff.current_price_ct_kwh",
            "site.outdoor_temperature_c",
            "site.buffer_1_top_temperature_c",
            "site.buffer_1_bottom_temperature_c",
        ]
    normalized_channels = [
        str(channel_id)
        for channel_id in channels
        if str(channel_id) in REPORT_CHANNELS
    ]
    if not normalized_channels:
        normalized_channels = ["tariff.current_price_ct_kwh"]

    raw_sections = config.get("sections")
    if not isinstance(raw_sections, list) or not raw_sections:
        raw_sections = [
            {"component": "summary", "title": "Kennzahlen"},
            {"component": "line_chart", "title": "Zeitverlauf"},
            {"component": "table", "title": "Messwerte"},
            {"component": "events", "title": "Kommunikationshinweise"},
        ]
    sections = []
    for index, section in enumerate(raw_sections, start=1):
        section = section if isinstance(section, dict) else {}
        component = str(section.get("component", "summary"))
        if component not in REPORT_COMPONENTS:
            continue
        sections.append(
            {
                "id": str(section.get("id") or "section-{0}".format(index)),
                "component": component,
                "title": str(section.get("title") or REPORT_COMPONENTS[component]),
            }
        )
    if not sections:
        sections = [{"id": "section-1", "component": "summary", "title": "Kennzahlen"}]

    try:
        limit = int(config.get("limit", 500))
    except (TypeError, ValueError):
        limit = 500
    return {
        "title": _optional_text(config.get("title")) or "Mini EMS Betriebsbericht",
        "start": start,
        "end": end,
        "granularity": granularity,
        "channels": normalized_channels,
        "sections": sections,
        "limit": max(1, min(limit, 5000)),
        "available_channels": [
            {"id": channel_id, **metadata}
            for channel_id, metadata in REPORT_CHANNELS.items()
        ],
        "available_components": [
            {"id": component, "label": label}
            for component, label in REPORT_COMPONENTS.items()
        ],
        "available_granularities": list(REPORT_GRANULARITIES),
    }


def _history_row_value(row: Dict[str, object]) -> object:
    for key in ("average_value", "last_value", "value"):
        if key in row:
            return row[key]
    return None


_REPORT_STYLES = """
    :root {
      --ink: #1c2530;
      --muted: #667485;
      --line: #dce3ea;
      --line-soft: #e8edf2;
      --panel: #ffffff;
      --soft: #f7f9fb;
      --accent: #3b6ea5;
      --good: #3f7a5f;
      --warn: #b07a1e;
      --bad: #b0463c;
    }
    * { box-sizing: border-box; }
    html, body { margin: 0; padding: 0; }
    body {
      background: #eef2f6;
      color: var(--ink);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      font-size: 12px;
      line-height: 1.5;
    }
    .report {
      width: min(820px, 100%);
      margin: 0 auto;
      padding: 24px;
    }
    .eyebrow {
      display: block;
      color: var(--muted);
      font-size: 10px;
      font-weight: 700;
      letter-spacing: 0.09em;
      text-transform: uppercase;
    }
    h1 { margin: 6px 0 0; font-size: 26px; font-weight: 650; letter-spacing: -0.01em; }
    h2 { margin: 0 0 12px; font-size: 15px; font-weight: 650; }
    h3 { margin: 0 0 8px; font-size: 12px; font-weight: 650; color: var(--muted); }
    p { margin: 0; }
    .muted { color: var(--muted); }
    .cover {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 24px;
      padding: 22px 24px;
      border: 1px solid var(--line);
      border-radius: 10px;
      background: var(--panel);
    }
    .cover-sub { margin-top: 4px; color: var(--muted); font-size: 13px; }
    .cover-meta {
      display: flex;
      flex-wrap: wrap;
      gap: 20px 32px;
      margin: 18px 0 0;
    }
    .cover-meta div { min-width: 120px; }
    .cover-meta dt {
      margin: 0;
      color: var(--muted);
      font-size: 10px;
      font-weight: 700;
      letter-spacing: 0.06em;
      text-transform: uppercase;
    }
    .cover-meta dd { margin: 3px 0 0; font-weight: 600; }
    .cover-status {
      flex: 0 0 auto;
      display: flex;
      flex-direction: column;
      align-items: flex-start;
      gap: 4px;
      padding: 14px 16px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--soft);
      min-width: 150px;
    }
    .status-dot {
      width: 10px; height: 10px; border-radius: 50%;
      background: var(--muted);
    }
    .status-good .status-dot { background: var(--good); }
    .status-warn .status-dot { background: var(--warn); }
    .status-bad .status-dot { background: var(--bad); }
    .status-label { font-size: 14px; font-weight: 650; }
    .status-good .status-label { color: var(--good); }
    .status-warn .status-label { color: var(--warn); }
    .status-bad .status-label { color: var(--bad); }
    .status-hint { color: var(--muted); font-size: 10px; }
    .message {
      margin-top: 14px;
      padding: 16px 20px;
      border: 1px solid var(--line);
      border-left: 3px solid var(--accent);
      border-radius: 8px;
      background: var(--panel);
    }
    .message-text { margin-top: 5px; font-size: 15px; font-weight: 550; }
    .block {
      margin-top: 14px;
      padding: 18px 20px;
      border: 1px solid var(--line);
      border-radius: 10px;
      background: var(--panel);
      page-break-inside: avoid;
      break-inside: avoid;
    }
    .kpi-row {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
    }
    .kpi {
      padding: 12px 14px;
      border: 1px solid var(--line-soft);
      border-radius: 8px;
      background: var(--soft);
    }
    .kpi-label {
      display: block;
      color: var(--muted);
      font-size: 10px;
      font-weight: 700;
      letter-spacing: 0.05em;
      text-transform: uppercase;
    }
    .kpi-value { display: block; margin-top: 8px; font-size: 20px; font-weight: 650; line-height: 1.1; }
    .kpi-note { display: block; margin-top: 5px; color: var(--muted); font-size: 11px; }
    .status-list { list-style: none; margin: 14px 0 0; padding: 0; }
    .status-list li {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 7px 0;
      border-top: 1px solid var(--line-soft);
      font-weight: 550;
    }
    .status-list .count { margin-left: auto; font-weight: 650; }
    .dot { width: 9px; height: 9px; border-radius: 50%; background: var(--muted); }
    .dot-good { background: var(--good); }
    .dot-warn { background: var(--warn); }
    .dot-bad { background: var(--bad); }
    .block-note { margin-top: 12px; color: var(--muted); font-size: 11px; }
    .chips { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px; }
    .chip {
      padding: 4px 10px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: var(--soft);
      font-variant-numeric: tabular-nums;
      font-size: 11px;
    }
    table { width: 100%; border-collapse: collapse; }
    table.events { margin-top: 12px; }
    th, td {
      border-bottom: 1px solid var(--line-soft);
      padding: 7px 6px;
      text-align: left;
      font-size: 11px;
      vertical-align: top;
    }
    th {
      color: var(--muted);
      font-size: 10px;
      font-weight: 700;
      letter-spacing: 0.06em;
      text-transform: uppercase;
    }
    td.time, td.sev { white-space: nowrap; color: var(--muted); }
    td.value { text-align: right; font-weight: 600; white-space: nowrap; }
    .chart-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }
    .chart-card {
      padding: 12px 14px;
      border: 1px solid var(--line-soft);
      border-radius: 8px;
      background: var(--panel);
      page-break-inside: avoid;
      break-inside: avoid;
    }
    .chart-head {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 8px;
      color: var(--muted);
      font-size: 11px;
    }
    .chart {
      width: 100%;
      height: 130px;
      border: 1px solid var(--line-soft);
      background: var(--soft);
    }
    .empty {
      padding: 16px;
      border: 1px dashed var(--line);
      border-radius: 6px;
      color: var(--muted);
    }
    .appendix {
      margin-top: 20px;
      padding: 18px 20px;
      border: 1px solid var(--line-soft);
      border-radius: 10px;
      background: var(--soft);
      page-break-before: auto;
    }
    .appendix-label {
      display: block;
      color: var(--muted);
      font-size: 10px;
      font-weight: 700;
      letter-spacing: 0.09em;
      text-transform: uppercase;
    }
    .appendix-note { margin: 6px 0 4px; color: var(--muted); font-size: 11px; }
    .appendix-part { margin-top: 16px; page-break-inside: avoid; break-inside: avoid; }
    .cards {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 10px;
    }
    .card {
      padding: 12px;
      border: 1px solid var(--line-soft);
      border-radius: 8px;
      background: var(--panel);
      page-break-inside: avoid;
      break-inside: avoid;
    }
    .card-group {
      display: block;
      color: var(--muted);
      font-size: 9px;
      font-weight: 700;
      letter-spacing: 0.06em;
      text-transform: uppercase;
    }
    .card-title { display: block; margin-top: 6px; font-weight: 650; }
    .card-metric { display: block; margin-top: 8px; font-size: 18px; font-weight: 650; line-height: 1; }
    .card-metric small { color: var(--muted); font-size: 11px; font-weight: 500; }
    .card-meta { margin-top: 7px; color: var(--muted); font-size: 10px; }
    table.data { margin-top: 6px; }
    .report-footer {
      display: flex;
      justify-content: space-between;
      gap: 16px;
      margin-top: 22px;
      padding-top: 12px;
      border-top: 1px solid var(--line);
      color: var(--muted);
      font-size: 10px;
    }
    @page { size: A4; margin: 16mm 14mm; }
    @media print {
      body { background: #ffffff; }
      .report { width: 100%; padding: 0; }
      .cover, .block, .appendix, .message { break-inside: avoid; }
      .appendix { page-break-before: always; }
      .report-footer { page-break-inside: avoid; }
    }
    @media (max-width: 760px) {
      .cover { flex-direction: column; }
      .kpi-row, .chart-grid, .cards { grid-template-columns: 1fr; }
      .report-footer { flex-direction: column; gap: 4px; }
    }
"""


def _render_report_html_fallback(report: Dict[str, object], overview: Optional[Dict[str, object]] = None) -> str:
    overview = overview or {}
    cover = _render_report_cover(overview)
    message = _render_report_main_message(overview)
    summary_block = _render_report_operations_summary(overview)
    price_block = _render_report_price_block(overview)
    grid_block = _render_report_grid_block(overview)
    events_block = _render_report_events_block(overview)
    charts_block = _render_report_charts(report)
    appendix = "\n".join(_render_report_section_fallback(section) for section in report.get("sections", []))
    title = escape(str(overview.get("title") or report.get("title") or "Tagesbericht"))
    return """<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
{styles}
  </style>
</head>
<body>
  <main class="report">
    {cover}
    {message}
    {summary}
    {price}
    {grid}
    {events}
    {charts}
    <section class="appendix">
      <span class="appendix-label">Technischer Anhang</span>
      <p class="appendix-note">Dieser Abschnitt enthält die zugrunde liegenden Messwerte für die technische Nachvollziehbarkeit.</p>
      {appendix}
    </section>
    <footer class="report-footer">
      <span>Mini EMS Betriebsbericht</span>
      <span>Bei fehlendem PDF-Renderer kann diese Ansicht im Browser über Drucken / Als PDF speichern exportiert werden.</span>
    </footer>
  </main>
</body>
</html>
""".format(
        title=title,
        styles=_REPORT_STYLES,
        cover=cover,
        message=message,
        summary=summary_block,
        price=price_block,
        grid=grid_block,
        events=events_block,
        charts=charts_block,
        appendix=appendix or "<p class='muted'>Keine Detaildaten für diese Auswahl.</p>",
    )


def _render_report_cover(overview: Dict[str, object]) -> str:
    # Ampellogik nur funktional: aus den Zustandszeilen des Tages ableiten.
    status_lines = overview.get("status_lines", []) or []
    labels = {str(line.get("label")): int(line.get("count") or 0) for line in status_lines}
    if labels.get("Sicherer Modus"):
        tone = "bad"
    elif labels.get("Eingeschränkter Betrieb"):
        tone = "warn"
    else:
        tone = "good"
    tone_label = {"good": "Normalbetrieb", "warn": "Eingeschränkter Betrieb", "bad": "Sicherer Modus"}[tone]
    return (
        "<header class='cover'>"
        "<div class='cover-main'>"
        "<span class='eyebrow'>Mini EMS &middot; Betriebsbericht</span>"
        "<h1>{title}</h1>"
        "<p class='cover-sub'>{location}</p>"
        "<dl class='cover-meta'>"
        "<div><dt>Berichtstag</dt><dd>{date}</dd></div>"
        "<div><dt>Zeitraum</dt><dd>{period}</dd></div>"
        "<div><dt>Erstellt</dt><dd>{generated}</dd></div>"
        "</dl>"
        "</div>"
        "<div class='cover-status status-{tone}'>"
        "<span class='status-dot'></span>"
        "<span class='status-label'>{tone_label}</span>"
        "<span class='status-hint'>Betriebsstatus des Tages</span>"
        "</div>"
        "</header>"
    ).format(
        title=escape(str(overview.get("title") or "Tagesbericht")),
        location=escape(str(overview.get("location") or "")),
        date=escape(str(overview.get("date_label") or "kein Datum")),
        period=escape(str(overview.get("period_label") or "")),
        generated=escape(str(overview.get("generated_label") or "")),
        tone=tone,
        tone_label=escape(tone_label),
    )


def _render_report_main_message(overview: Dict[str, object]) -> str:
    message = overview.get("main_message")
    if not message:
        return ""
    return (
        "<section class='message'>"
        "<span class='eyebrow'>Hauptbotschaft</span>"
        "<p class='message-text'>{0}</p>"
        "</section>"
    ).format(escape(str(message)))


def _render_report_kpi(label: str, value: str, note: str) -> str:
    return (
        "<article class='kpi'>"
        "<span class='kpi-label'>{0}</span>"
        "<strong class='kpi-value'>{1}</strong>"
        "<span class='kpi-note'>{2}</span>"
        "</article>"
    ).format(escape(label), escape(value), escape(note))


def _render_report_operations_summary(overview: Dict[str, object]) -> str:
    cycle_count = int(overview.get("cycle_count") or 0)
    status_lines = overview.get("status_lines", []) or []
    if status_lines:
        rows = "".join(
            "<li><span class='dot dot-{tone}'></span>{label}<span class='count'>{count}</span></li>".format(
                tone=_status_line_tone(str(line.get("label"))),
                label=escape(str(line.get("label"))),
                count=int(line.get("count") or 0),
            )
            for line in status_lines
        )
        breakdown = "<ul class='status-list'>{0}</ul>".format(rows)
    else:
        breakdown = "<p class='muted'>Für diesen Tag liegen noch keine Läufe vor.</p>"
    return (
        "<section class='block'>"
        "<h2>Betriebszusammenfassung</h2>"
        "<div class='kpi-row'>{kpi}</div>"
        "{breakdown}"
        "</section>"
    ).format(
        kpi=_render_report_kpi("Läufe heute", str(cycle_count), "Ausgeführte Steuerungszyklen"),
        breakdown=breakdown,
    )


def _status_line_tone(label: str) -> str:
    if label == "Sicherer Modus":
        return "bad"
    if label == "Eingeschränkter Betrieb":
        return "warn"
    if label == "Normalbetrieb":
        return "good"
    return "warn"


def _render_report_price_block(overview: Dict[str, object]) -> str:
    price = overview.get("price", {}) or {}
    windows = overview.get("windows", []) or []
    kpis = (
        _render_report_kpi("Tagesmittel", _format_price(price.get("average")), "Mittlerer Börsenstrompreis")
        + _render_report_kpi("Günstigster Preis", _format_price(price.get("min")), "Niedrigster Viertelstundenpreis")
        + _render_report_kpi("Höchster Preis", _format_price(price.get("max")), "Höchster Viertelstundenpreis")
    )
    if windows:
        window_html = "<div class='chips'>{0}</div>".format(
            "".join("<span class='chip'>{0}</span>".format(escape(str(window))) for window in windows)
        )
        window_block = "<p class='block-note'>Geplante Preisfenster ({0}):</p>{1}".format(len(windows), window_html)
    else:
        window_block = "<p class='block-note'>Für diesen Tag wurden keine Preisfenster geplant.</p>"
    return (
        "<section class='block'>"
        "<h2>Strompreis</h2>"
        "<div class='kpi-row'>{kpis}</div>"
        "{windows}"
        "</section>"
    ).format(kpis=kpis, windows=window_block)


def _render_report_grid_block(overview: Dict[str, object]) -> str:
    grid = overview.get("grid", {}) or {}
    kpis = (
        _render_report_kpi("Mittlere Leistung", _format_power(grid.get("average")), "Durchschnitt am Netzanschluss")
        + _render_report_kpi("Niedrigste Leistung", _format_power(grid.get("min")), "Minimum des Tages")
        + _render_report_kpi("Höchste Leistung", _format_power(grid.get("max")), "Maximum des Tages")
    )
    return (
        "<section class='block'>"
        "<h2>Netzleistung</h2>"
        "<div class='kpi-row'>{kpis}</div>"
        "</section>"
    ).format(kpis=kpis)


def _render_report_events_block(overview: Dict[str, object]) -> str:
    count = int(overview.get("event_count") or 0)
    events = overview.get("events", []) or []
    if count == 0:
        body = "<p class='muted'>Keine Kommunikationshinweise an diesem Tag.</p>"
    else:
        rows = "".join(
            "<tr><td class='time'>{time}</td><td class='sev'>{sev}</td><td>{msg}</td></tr>".format(
                time=escape(str(event.get("time") or "--:--")),
                sev=escape(str(event.get("severity") or "Hinweis")),
                msg=escape(str(event.get("message") or "")),
            )
            for event in events
        )
        note = "" if count <= len(events) else "<p class='block-note'>Angezeigt werden die letzten {0} von {1} Meldungen.</p>".format(len(events), count)
        body = "<table class='events'><thead><tr><th>Zeit</th><th>Status</th><th>Meldung</th></tr></thead><tbody>{0}</tbody></table>{1}".format(rows, note)
    return (
        "<section class='block'>"
        "<h2>Kommunikationshinweise</h2>"
        "<p class='block-note'>Meldungen aus dem Datenaustausch mit der Anlage: {count}.</p>"
        "{body}"
        "</section>"
    ).format(count=count, body=body)


def _render_report_charts(report: Dict[str, object]) -> str:
    cards = []
    for section in report.get("sections", []):
        if section.get("component") != "line_chart":
            continue
        for serie in section.get("series", []):
            cards.append(_render_report_series_card(serie))
    if not cards:
        return ""
    return (
        "<section class='block charts'>"
        "<h2>Verlaufsdiagramme</h2>"
        "<div class='chart-grid'>{0}</div>"
        "</section>"
    ).format("".join(cards))


def _render_report_section_fallback(section: Dict[str, object]) -> str:
    title = escape(str(section.get("title", "")))
    component = section.get("component")
    if component == "summary":
        cards = "".join(
            "<article class='card {0}'><span class='card-group'>{1}</span><span class='card-title'>{2}</span><strong class='card-metric'>{3} <small>{4}</small></strong><p class='card-meta'>{5}; {6}</p><p class='card-meta'>{7} Messpunkte</p></article>".format(
                "energy" if card.get("kind") == "energy_counter" else "",
                escape(str(card.get("group") or "EMS")),
                escape(str(card["label"])),
                _format_report_number(card.get("display_value")),
                escape(str(card.get("unit") or "")),
                escape(str(card.get("display_label") or "")),
                escape(str(card.get("detail") or "")),
                escape(str(card.get("sample_count") or 0)),
            )
            for card in section.get("cards", [])
        )
        return "<div class='appendix-part'><h3>{0}</h3><div class='cards'>{1}</div></div>".format(title, cards)
    if component == "line_chart":
        charts = "".join(_render_report_series_card(serie) for serie in section.get("series", []))
        if not charts:
            charts = "<div class='empty'>Keine Diagrammdaten für diese Auswahl.</div>"
        return "<div class='appendix-part'><h3>{0}</h3><div class='chart-grid'>{1}</div></div>".format(title, charts)
    rows = section.get("rows", [])
    header = "<tr><th>Zeit</th><th>Datenpunkt</th><th>Wert</th><th>Details</th></tr>"
    body = "".join(
        "<tr><td>{0}</td><td>{1}</td><td class='value'>{2}</td><td>{3}</td></tr>".format(
            escape(str(row.get("timestamp", ""))),
            escape(str(row.get("label") or "Anlage")),
            escape(_format_report_number(row.get("value"))),
            escape(str(row.get("message") or row.get("event_type") or row.get("unit") or "")),
        )
        for row in rows
    )
    if not body:
        body = "<tr><td colspan='4' class='muted'>Keine Einträge im gewählten Zeitraum.</td></tr>"
    return "<div class='appendix-part'><h3>{0}</h3><table class='data'>{1}{2}</table></div>".format(title, header, body)


def _render_report_series_card(serie: Dict[str, object]) -> str:
    points = [point for point in serie.get("points", []) if point.get("value") is not None]
    label = escape(str(serie.get("label") or "Datenpunkt"))
    unit = escape(str(serie.get("unit") or ""))
    if not points:
        chart = "<div class='empty'>Kein Messwert im gewählten Zeitraum.</div>"
        meta = ""
    else:
        width = 520
        height = 150
        values = [float(point["value"]) for point in points]
        min_value = min(values)
        max_value = max(values)
        span = max(max_value - min_value, 1e-9)
        step = width / max(len(points) - 1, 1)
        polyline = " ".join(
            "{0:.1f},{1:.1f}".format(
                point_index * step,
                132 - (((float(point["value"]) - min_value) / span) * 112),
            )
            for point_index, point in enumerate(points)
        )
        stroke = "#3f7a5f" if str(serie.get("unit") or "") == "kWh" else "#3b6ea5"
        chart = "<svg class='chart' viewBox='0 0 {0} {1}' preserveAspectRatio='none' role='img'><line x1='0' y1='132' x2='{0}' y2='132' stroke='#d7ddE4'></line><polyline fill='none' stroke='{2}' stroke-width='2' points='{3}'></polyline></svg>".format(width, height, stroke, polyline)
        meta = "<p class='card-meta'>Min {0} / Max {1}</p>".format(_format_report_number(min_value), _format_report_number(max_value))
    return "<article class='chart-card'><div class='chart-head'><strong>{0}</strong><span>{1}</span></div>{2}{3}</article>".format(label, unit, chart, meta)


def _format_report_number(value: object) -> str:
    if value is None:
        return "-"
    try:
        return "{0:.2f}".format(float(value))
    except (TypeError, ValueError):
        return str(value)


_MONTHS_DE = (
    "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
)


def _parse_report_timestamp(value: object) -> Optional[datetime]:
    if not value:
        return None
    text = str(value).strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(SITE_TIMEZONE)


def _format_date_de(date_iso: object) -> str:
    parsed = _parse_report_timestamp("{0}T00:00:00Z".format(str(date_iso)[:10]))
    if parsed is None:
        return str(date_iso or "kein Datum")
    return "{0}. {1} {2}".format(parsed.day, _MONTHS_DE[parsed.month - 1], parsed.year)


def _format_datetime_de(value: object) -> str:
    parsed = _parse_report_timestamp(value)
    if parsed is None:
        return "kein Zeitpunkt"
    return "{0}. {1} {2}, {3:02d}:{4:02d} Uhr".format(
        parsed.day, _MONTHS_DE[parsed.month - 1], parsed.year, parsed.hour, parsed.minute
    )


def _format_time_de(value: object) -> str:
    parsed = _parse_report_timestamp(value)
    if parsed is None:
        return "--:--"
    return "{0:02d}:{1:02d} Uhr".format(parsed.hour, parsed.minute)


def _format_period_de(start: object, end: object) -> str:
    start_parsed = _parse_report_timestamp(start)
    end_parsed = _parse_report_timestamp(end)
    if start_parsed is None or end_parsed is None:
        return "Zeitraum nicht bekannt"
    total_seconds = (end_parsed - start_parsed).total_seconds()
    # Ganztags-Bericht: rund ein Tag zwischen Tagesgrenzen -> ohne verwirrende Uhrzeit.
    spans_full_day = 23 * 3600 <= total_seconds <= 24 * 3600 + 3600
    same_clock = (start_parsed.hour, start_parsed.minute) == (end_parsed.hour, end_parsed.minute)
    if spans_full_day and same_clock:
        return "{0}, ganztägig".format(_format_date_de(start_parsed.date().isoformat()))
    if start_parsed.date() == end_parsed.date():
        return "{0}, {1:02d}:{2:02d}-{3:02d}:{4:02d} Uhr".format(
            _format_date_de(start_parsed.date().isoformat()),
            start_parsed.hour,
            start_parsed.minute,
            end_parsed.hour,
            end_parsed.minute,
        )
    return "{0} bis {1}".format(
        _format_datetime_de(start_parsed.isoformat()),
        _format_datetime_de(end_parsed.isoformat()),
    )


def _format_price(value: object) -> str:
    if value is None:
        return "kein Messwert"
    try:
        return "{0:.2f} ct/kWh".format(float(value))
    except (TypeError, ValueError):
        return "kein Messwert"


def _format_power(value: object) -> str:
    if value is None:
        return "kein Messwert"
    try:
        return "{0:.1f} kW".format(float(value))
    except (TypeError, ValueError):
        return "kein Messwert"


def _report_location_name(normalized: Dict[str, object]) -> str:
    location = _optional_text(normalized.get("location")) or _optional_text(normalized.get("site"))
    return location or "Standort Mini EMS"


def _report_main_message(cycle_count: int, status_counts: Dict[str, object], event_count: object) -> str:
    """Eine datengetriebene Hauptbotschaft in einem Satz (UX1, Prio 1)."""
    if cycle_count <= 0:
        return "Für diesen Tag liegen noch keine Betriebsdaten vor."
    healthy = int(status_counts.get("healthy", 0) or 0)
    degraded = int(status_counts.get("degraded", 0) or 0)
    safe_mode = int(status_counts.get("safe_mode", 0) or 0)
    try:
        events = int(event_count or 0)
    except (TypeError, ValueError):
        events = 0

    if safe_mode > 0:
        return (
            "Die Steuerung war heute zeitweise im sicheren Modus; bitte den Systemzustand prüfen."
        )
    if degraded > 0:
        return (
            "Die Anlage lief heute überwiegend im Normalbetrieb, zeitweise mit Einschränkungen "
            "bei der Datenübertragung."
        )
    if healthy == cycle_count:
        base = "Die Anlage lief heute durchgehend im Normalbetrieb."
    else:
        base = "Die Anlage lief heute im Normalbetrieb."
    if events > 0:
        return base + " Es gab einzelne Kommunikationshinweise."
    return base


def _normalize_numeric_value(value: object) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    return float(value)


def _optional_float(value: object) -> Optional[float]:
    if value is None:
        return None
    return float(value)


def _optional_bool(value: object) -> Optional[int]:
    if value is None:
        return None
    return 1 if bool(value) else 0


def _optional_text(value: object) -> Optional[str]:
    if value is None:
        return None
    return str(value)


def _slot_label(slot_index: int) -> str:
    hour = slot_index // 4
    minute = (slot_index % 4) * 15
    return "{0:02d}:{1:02d}".format(hour, minute)


def _rollup_table_name(granularity: str) -> str:
    table_name = ROLLUP_TABLES.get(granularity)
    if table_name is None:
        raise ValueError("Unsupported history granularity: {0}".format(granularity))
    return table_name


def _parse_iso_datetime_utc(value: str) -> datetime:
    normalized = str(value).replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _bucket_bounds_utc(value_utc: datetime, granularity: str) -> tuple[datetime, datetime]:
    value_local = value_utc.astimezone(SITE_TIMEZONE)
    if granularity == "5m":
        bucket_start_local = value_local.replace(
            minute=(value_local.minute // 5) * 5,
            second=0,
            microsecond=0,
        )
    elif granularity == "1h":
        bucket_start_local = value_local.replace(
            minute=0,
            second=0,
            microsecond=0,
        )
    elif granularity == "1d":
        bucket_start_local = value_local.replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
    else:
        raise ValueError("Unsupported rollup granularity: {0}".format(granularity))
    bucket_end_local = bucket_start_local + ROLLUP_GRANULARITIES[granularity]
    return (
        bucket_start_local.astimezone(timezone.utc),
        bucket_end_local.astimezone(timezone.utc),
    )


def _utc_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
