import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator
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
        return [dict(row) for row in rows]

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
                {"label": "Tagesreport CSV", "href": "/api/report/daily.csv?date={0}".format(date_iso)},
                {"label": "Tagesreport JSON", "href": "/api/report/daily?date={0}".format(date_iso)},
            ],
            "metrics": [
                {"id": "grid", "label": "Netz Bilanz", "value": report["grid_active_power_kw"].get("average"), "unit": "kW"},
                {"id": "price", "label": "Preis Niveau", "value": report["price_ct_kwh"].get("average"), "unit": "ct/kWh"},
                {"id": "events", "label": "BACnet Events", "value": report.get("bacnet_event_count"), "unit": ""},
                {"id": "windows", "label": "Preisfenster", "value": len(report.get("spotmarket_windows", [])), "unit": ""},
            ],
            "next_steps": [
                "Zeitfenster als Query-Parameter stabilisieren",
                "Energie aus Leistung integrieren",
                "Vorlagen fuer Betreiber, Technik und Finance trennen",
            ],
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
        grid = report["grid_active_power_kw"]
        for key in ("sample_count", "min", "max", "average"):
            lines.append("grid_active_power_kw,{0},{1}".format(key, grid.get(key)))
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
                  AND direction = 'input'
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
                  AND direction = 'input'
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
