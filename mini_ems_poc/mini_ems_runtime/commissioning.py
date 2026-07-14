"""Explicitly approved, time-limited BACnet commissioning writes."""

import ipaddress
import json
import math
import re
import secrets
import sqlite3
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Iterator, List, Optional

from .channels import BACNET_AV, BACNET_BV, PointConfig
from .config import MiniEmsConfig, RESERVED_BACNET_WRITE_PRIORITIES
from .identity import IdentityStore, IdentityUser, ROLE_ADMIN
from .logging_utils import log_event
from .protocol import ProtocolAdapter, WriteConfirmation


WRITE_TEST_SECONDS = 10
_EMS_NAME_PATTERN = re.compile(r"^EMS_[A-Za-z0-9_.-]{1,76}$")


@dataclass(frozen=True)
class ApprovedWritePoint:
    point_id: str
    name: str
    controller_ip: str
    controller_port: int
    object_type: str
    instance: int
    write_priority: int
    enabled: bool
    approved_by: str
    approved_at: int

    def to_public_dict(self) -> Dict[str, object]:
        return {
            "id": self.point_id,
            "name": self.name,
            "controller_ip": self.controller_ip,
            "controller_port": self.controller_port,
            "object_type": self.object_type,
            "instance": self.instance,
            "write_priority": self.write_priority,
            "enabled": self.enabled,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at,
        }


class CommissioningStore:
    def __init__(self, identity_path: Path, now: Callable[[], float] = time.time):
        self.path = Path(identity_path).resolve()
        self._now = now
        self._initialize_schema()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(str(self.path), timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize_schema(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS bacnet_write_points (
                    point_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    controller_ip TEXT NOT NULL,
                    controller_port INTEGER NOT NULL,
                    object_type TEXT NOT NULL CHECK (object_type IN ('bv', 'av')),
                    instance INTEGER NOT NULL,
                    write_priority INTEGER NOT NULL,
                    enabled INTEGER NOT NULL,
                    approved_by TEXT NOT NULL,
                    approved_at INTEGER NOT NULL,
                    UNIQUE(controller_ip, controller_port, object_type, instance)
                );
                CREATE UNIQUE INDEX IF NOT EXISTS bacnet_write_points_name
                ON bacnet_write_points(name COLLATE NOCASE);
                CREATE TABLE IF NOT EXISTS bacnet_write_leases (
                    lease_id TEXT PRIMARY KEY,
                    point_id TEXT NOT NULL REFERENCES bacnet_write_points(point_id),
                    desired_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    started_at INTEGER NOT NULL,
                    expires_at INTEGER NOT NULL,
                    actor_user_id TEXT NOT NULL,
                    write_confirmation_json TEXT,
                    effective_value_json TEXT,
                    release_confirmation_json TEXT,
                    error TEXT
                );
                CREATE INDEX IF NOT EXISTS bacnet_write_leases_point
                ON bacnet_write_leases(point_id, started_at DESC);
                """
            )

    def approve(self, payload: Dict[str, object], actor: IdentityUser) -> ApprovedWritePoint:
        _require_admin(actor)
        name = _validate_ems_name(payload.get("name"))
        controller_ip = _validate_controller_ip(payload.get("controller_ip"))
        controller_port = _bounded_int(payload.get("controller_port", 47808), 1, 65535, "Kommunikationsport")
        object_type = str(payload.get("object_type") or "").strip().lower()
        if object_type not in {"bv", "av"}:
            raise ValueError("Für Schreibtests sind nur BACnet BV und AV erlaubt.")
        instance = _bounded_int(payload.get("instance"), 0, 4_194_303, "BACnet-Instanz")
        priority = _bounded_int(payload.get("write_priority", 14), 3, 16, "BACnet-Priorität")
        if priority in RESERVED_BACNET_WRITE_PRIORITIES:
            raise ValueError("Die BACnet-Prioritäten 1, 2, 5 und 6 bleiben für Schutzfunktionen reserviert.")
        now = int(self._now())
        with self._connect() as connection:
            existing = connection.execute(
                """
                SELECT point_id FROM bacnet_write_points
                WHERE controller_ip = ? AND controller_port = ? AND object_type = ? AND instance = ?
                """,
                (controller_ip, controller_port, object_type, instance),
            ).fetchone()
            point_id = str(existing["point_id"]) if existing is not None else secrets.token_urlsafe(10)
            try:
                connection.execute(
                    """
                    INSERT INTO bacnet_write_points (
                        point_id, name, controller_ip, controller_port, object_type,
                        instance, write_priority, enabled, approved_by, approved_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                    ON CONFLICT(point_id) DO UPDATE SET
                        name = excluded.name,
                        write_priority = excluded.write_priority,
                        enabled = 1,
                        approved_by = excluded.approved_by,
                        approved_at = excluded.approved_at
                    """,
                    (
                        point_id,
                        name,
                        controller_ip,
                        controller_port,
                        object_type,
                        instance,
                        priority,
                        actor.username,
                        now,
                    ),
                )
            except sqlite3.IntegrityError as error:
                raise ValueError("Diese EMS_-Bezeichnung ist bereits für einen anderen BACnet-Punkt vergeben.") from error
        return self.get_point(point_id)

    def get_point(self, point_id: str) -> ApprovedWritePoint:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM bacnet_write_points WHERE point_id = ?",
                (str(point_id),),
            ).fetchone()
        if row is None:
            raise ValueError("Der freigegebene BACnet-Punkt wurde nicht gefunden.")
        return _point_from_row(row)

    def list_points(self) -> List[Dict[str, object]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM bacnet_write_points ORDER BY enabled DESC, approved_at DESC, name"
            ).fetchall()
        result = []
        for row in rows:
            point = _point_from_row(row)
            entry = point.to_public_dict()
            entry["last_test"] = self.latest_lease(point.point_id)
            result.append(entry)
        return result

    def disable(self, point_id: str) -> ApprovedWritePoint:
        with self._connect() as connection:
            connection.execute(
                "UPDATE bacnet_write_points SET enabled = 0 WHERE point_id = ?",
                (str(point_id),),
            )
            if connection.total_changes != 1:
                raise ValueError("Der freigegebene BACnet-Punkt wurde nicht gefunden.")
        return self.get_point(point_id)

    def create_lease(self, point_id: str, desired_value: object, actor_user_id: str) -> Dict[str, object]:
        if self.active_lease(point_id) is not None:
            raise ValueError("Für diesen Punkt läuft bereits ein Schreibtest.")
        now = int(self._now())
        lease_id = secrets.token_urlsafe(12)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO bacnet_write_leases (
                    lease_id, point_id, desired_json, status, started_at, expires_at, actor_user_id
                ) VALUES (?, ?, ?, 'writing', ?, ?, ?)
                """,
                (
                    lease_id,
                    point_id,
                    json.dumps(desired_value),
                    now,
                    now + WRITE_TEST_SECONDS,
                    actor_user_id,
                ),
            )
        return self.get_lease(lease_id)

    def mark_active(
        self,
        lease_id: str,
        confirmation: WriteConfirmation,
        effective_value: Optional[object],
    ) -> Dict[str, object]:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE bacnet_write_leases
                SET status = 'active', write_confirmation_json = ?, effective_value_json = ?
                WHERE lease_id = ?
                """,
                (
                    json.dumps(confirmation.to_dict(), ensure_ascii=False),
                    json.dumps(effective_value),
                    lease_id,
                ),
            )
        return self.get_lease(lease_id)

    def mark_released(self, lease_id: str, confirmation: WriteConfirmation) -> Dict[str, object]:
        status = "released" if confirmation.confirmed else "release_failed"
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE bacnet_write_leases
                SET status = ?, release_confirmation_json = ?, error = ?
                WHERE lease_id = ?
                """,
                (
                    status,
                    json.dumps(confirmation.to_dict(), ensure_ascii=False),
                    confirmation.error,
                    lease_id,
                ),
            )
        return self.get_lease(lease_id)

    def mark_failed(self, lease_id: str, error: str) -> Dict[str, object]:
        with self._connect() as connection:
            connection.execute(
                "UPDATE bacnet_write_leases SET status = 'failed', error = ? WHERE lease_id = ?",
                (str(error), lease_id),
            )
        return self.get_lease(lease_id)

    def get_lease(self, lease_id: str) -> Dict[str, object]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM bacnet_write_leases WHERE lease_id = ?",
                (str(lease_id),),
            ).fetchone()
        if row is None:
            raise ValueError("Der Schreibtest wurde nicht gefunden.")
        return _lease_from_row(row)

    def latest_lease(self, point_id: str) -> Optional[Dict[str, object]]:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM bacnet_write_leases
                WHERE point_id = ? ORDER BY started_at DESC, rowid DESC LIMIT 1
                """,
                (str(point_id),),
            ).fetchone()
        return _lease_from_row(row) if row is not None else None

    def active_lease(self, point_id: str) -> Optional[Dict[str, object]]:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM bacnet_write_leases
                WHERE point_id = ? AND status IN ('writing', 'active')
                ORDER BY started_at DESC, rowid DESC LIMIT 1
                """,
                (str(point_id),),
            ).fetchone()
        return _lease_from_row(row) if row is not None else None

    def unfinished_leases(self) -> List[Dict[str, object]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM bacnet_write_leases WHERE status IN ('writing', 'active')"
            ).fetchall()
        return [_lease_from_row(row) for row in rows]


class CommissioningService:
    def __init__(
        self,
        *,
        store: CommissioningStore,
        identity_store: IdentityStore,
        adapter: ProtocolAdapter,
        config: MiniEmsConfig,
        logger,
        timer_factory=threading.Timer,
    ):
        self.store = store
        self.identity_store = identity_store
        self.adapter = adapter
        self.config = config
        self.logger = logger
        self.timer_factory = timer_factory
        self._timers: Dict[str, object] = {}
        self._lock = threading.RLock()

    def points_payload(self) -> Dict[str, object]:
        return {
            "points": self.store.list_points(),
            "write_test_seconds": WRITE_TEST_SECONDS,
            "write_tests_available": not self.config.api.read_only,
            "mode": "simulation" if self.config.runtime.bacnet_mode == "simulated" else "anlage",
        }

    def approve(self, payload: Dict[str, object], actor: IdentityUser) -> Dict[str, object]:
        _require_admin(actor)
        target = _target_from_payload(payload)
        if target in _runtime_owned_targets(self.config):
            raise ValueError(
                "Dieses BACnet-Objekt wird bereits von der laufenden Mini-EMS-Regelung verwendet und kann nicht als separater Testpunkt freigegeben werden."
            )
        point = self.store.approve(payload, actor)
        self.identity_store.record_event(
            "bacnet.point_approved",
            actor_user_id=actor.user_id,
            details={
                "point_id": point.point_id,
                "name": point.name,
                "object_type": point.object_type,
                "instance": point.instance,
                "write_priority": point.write_priority,
            },
        )
        return {"approved": True, "point": point.to_public_dict()}

    def revoke(self, point_id: str, actor: IdentityUser) -> Dict[str, object]:
        _require_admin(actor)
        with self._lock:
            active = self.store.active_lease(point_id)
            if active is not None:
                self._release(active["id"], actor_user_id=actor.user_id)
            point = self.store.disable(point_id)
        self.identity_store.record_event(
            "bacnet.point_revoked",
            actor_user_id=actor.user_id,
            details={"point_id": point.point_id, "name": point.name},
        )
        return {"revoked": True, "point": point.to_public_dict()}

    def start_test(self, payload: Dict[str, object], actor: IdentityUser) -> Dict[str, object]:
        _require_admin(actor)
        if self.config.api.read_only:
            raise PermissionError("Anlagenaktionen sind gesperrt. Bitte den Schreibschutz zuerst bewusst aufheben.")
        if self.config.runtime.bacnet_mode == "real":
            if self.config.runtime.environment == "local":
                raise PermissionError("Aus der lokalen Entwicklung sind echte BACnet-Schreibzugriffe gesperrt.")
            if not self.config.runtime.real_writes_enabled:
                raise PermissionError("Echte BACnet-Schreibzugriffe sind in der Runtime nicht freigegeben.")
        point = self.store.get_point(str(payload.get("point_id") or ""))
        if not point.enabled:
            raise PermissionError("Dieser BACnet-Punkt ist nicht freigegeben.")
        desired_value = _normalize_desired_value(point, payload.get("value"))
        point_config = _point_config(point)
        with self._lock:
            lease = self.store.create_lease(point.point_id, desired_value, actor.user_id)
            try:
                confirmation = self.adapter.write_with_confirmation(
                    point_config,
                    desired_value,
                    "ack_only",
                )
                if not confirmation.confirmed:
                    self._best_effort_release(point_config)
                    raise RuntimeError(confirmation.error or "Der BACnet-Write wurde nicht bestätigt.")
                effective_value = self._read_effective_value(point_config)
                lease = self.store.mark_active(lease["id"], confirmation, effective_value)
                timer = self.timer_factory(
                    WRITE_TEST_SECONDS,
                    lambda: self._release(lease["id"], actor_user_id=None),
                )
                timer.daemon = True
                self._timers[lease["id"]] = timer
                timer.start()
            except Exception as error:
                self.store.mark_failed(lease["id"], str(error))
                self.identity_store.record_event(
                    "bacnet.write_test_failed",
                    actor_user_id=actor.user_id,
                    details={"point_id": point.point_id, "error": str(error)},
                )
                raise
        desired_matches = _values_match(desired_value, lease.get("effective_value"))
        self.identity_store.record_event(
            "bacnet.write_test_started",
            actor_user_id=actor.user_id,
            details={
                "point_id": point.point_id,
                "desired_value": desired_value,
                "effective": desired_matches,
                "expires_at": lease["expires_at"],
            },
        )
        return {
            "started": True,
            "lease": lease,
            "effective": desired_matches,
            "message": _write_result_message(lease, desired_matches),
        }

    def release_test(self, lease_id: str, actor: IdentityUser) -> Dict[str, object]:
        _require_admin(actor)
        return {"released": True, "lease": self._release(lease_id, actor_user_id=actor.user_id)}

    def recover_unfinished(self) -> None:
        for lease in self.store.unfinished_leases():
            try:
                self._release(lease["id"], actor_user_id=None)
            except Exception as error:
                log_event(
                    self.logger,
                    40,
                    "commissioning.recovery_failed",
                    lease_id=lease["id"],
                    point_id=lease["point_id"],
                    error=str(error),
                )

    def shutdown(self) -> None:
        for timer in list(self._timers.values()):
            timer.cancel()
        for lease in self.store.unfinished_leases():
            try:
                self._release(lease["id"], actor_user_id=None)
            except Exception:
                pass

    def _release(self, lease_id: str, actor_user_id: Optional[str]) -> Dict[str, object]:
        with self._lock:
            lease = self.store.get_lease(lease_id)
            if lease["status"] == "released":
                return lease
            point = self.store.get_point(lease["point_id"])
            confirmation = self.adapter.relinquish_with_confirmation(
                _point_config(point),
                "ack_only",
            )
            released = self.store.mark_released(lease_id, confirmation)
            timer = self._timers.pop(lease_id, None)
            if timer is not None and threading.current_thread() is not timer:
                timer.cancel()
        self.identity_store.record_event(
            "bacnet.write_test_released" if confirmation.confirmed else "bacnet.write_test_release_failed",
            actor_user_id=actor_user_id,
            details={"point_id": point.point_id, "lease_id": lease_id, "confirmed": confirmation.confirmed},
        )
        return released

    def _read_effective_value(self, point: PointConfig) -> Optional[object]:
        try:
            value = self.adapter.read_float(point)
        except Exception as error:
            log_event(
                self.logger,
                30,
                "commissioning.readback_unavailable",
                channel_id=point.channel_id,
                error=str(error),
            )
            return None
        return bool(round(value)) if point.object_type == BACNET_BV else float(value)

    def _best_effort_release(self, point: PointConfig) -> None:
        try:
            self.adapter.relinquish_with_confirmation(point, "ack_only")
        except Exception:
            pass


def _require_admin(actor: IdentityUser) -> None:
    if actor.role != ROLE_ADMIN or not actor.enabled:
        raise PermissionError("Diese Funktion ist nur für Administratoren verfügbar.")


def _validate_ems_name(value: object) -> str:
    name = str(value or "").strip()
    if not _EMS_NAME_PATTERN.fullmatch(name):
        raise ValueError("Freigegebene Schreibpunkte müssen eindeutig mit EMS_ beginnen.")
    return name


def _validate_controller_ip(value: object) -> str:
    text = str(value or "").strip()
    try:
        return str(ipaddress.IPv4Address(text))
    except ipaddress.AddressValueError as error:
        raise ValueError("Bitte eine gültige IPv4-Adresse des BACnet-Controllers eingeben.") from error


def _target_from_payload(payload: Dict[str, object]) -> tuple[str, int, str, int]:
    controller_ip = _validate_controller_ip(payload.get("controller_ip"))
    controller_port = _bounded_int(payload.get("controller_port", 47808), 1, 65535, "Kommunikationsport")
    object_type = str(payload.get("object_type") or "").strip().lower()
    if object_type not in {"bv", "av"}:
        raise ValueError("Für Schreibtests sind nur BACnet BV und AV erlaubt.")
    instance = _bounded_int(payload.get("instance"), 0, 4_194_303, "BACnet-Instanz")
    return controller_ip, controller_port, object_type, instance


def _runtime_owned_targets(config: MiniEmsConfig) -> set[tuple[str, int, str, int]]:
    default = (config.network.controller_ip, config.network.controller_port)
    targets = {
        (*default, "av", config.points.current_price_av),
        (*default, "bv", config.points.grid_lockout_bv),
        (*default, "bv", config.points.spotmarket_lockout_bv),
    }
    heartbeat = config.ddc_heartbeat
    if heartbeat.enabled and heartbeat.instance is not None:
        targets.add(
            (
                heartbeat.controller_ip or config.network.controller_ip,
                heartbeat.controller_port or config.network.controller_port,
                "av",
                heartbeat.instance,
            )
        )
    return targets


def _bounded_int(value: object, minimum: int, maximum: int, label: str) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError("{0} muss eine ganze Zahl sein.".format(label)) from error
    if number < minimum or number > maximum:
        raise ValueError("{0} muss zwischen {1} und {2} liegen.".format(label, minimum, maximum))
    return number


def _point_from_row(row: sqlite3.Row) -> ApprovedWritePoint:
    return ApprovedWritePoint(
        point_id=str(row["point_id"]),
        name=str(row["name"]),
        controller_ip=str(row["controller_ip"]),
        controller_port=int(row["controller_port"]),
        object_type=str(row["object_type"]),
        instance=int(row["instance"]),
        write_priority=int(row["write_priority"]),
        enabled=bool(row["enabled"]),
        approved_by=str(row["approved_by"]),
        approved_at=int(row["approved_at"]),
    )


def _lease_from_row(row: sqlite3.Row) -> Dict[str, object]:
    return {
        "id": str(row["lease_id"]),
        "point_id": str(row["point_id"]),
        "desired_value": json.loads(str(row["desired_json"])),
        "status": str(row["status"]),
        "started_at": int(row["started_at"]),
        "expires_at": int(row["expires_at"]),
        "write_confirmation": json.loads(str(row["write_confirmation_json"])) if row["write_confirmation_json"] else None,
        "effective_value": json.loads(str(row["effective_value_json"])) if row["effective_value_json"] else None,
        "release_confirmation": json.loads(str(row["release_confirmation_json"])) if row["release_confirmation_json"] else None,
        "error": str(row["error"]) if row["error"] is not None else None,
    }


def _point_config(point: ApprovedWritePoint) -> PointConfig:
    return PointConfig(
        channel_id="commissioning.{0}".format(point.point_id),
        object_type=BACNET_BV if point.object_type == "bv" else BACNET_AV,
        instance=point.instance,
        access="readwrite",
        description="Approved commissioning point {0}".format(point.name),
        controller_ip=point.controller_ip,
        controller_port=point.controller_port,
        write_priority=point.write_priority,
        relinquish_enabled=True,
    )


def _normalize_desired_value(point: ApprovedWritePoint, value: object) -> object:
    if point.object_type == "bv":
        if not isinstance(value, bool):
            raise ValueError("Für einen BV muss Ein oder Aus gewählt werden.")
        return value
    if isinstance(value, bool):
        raise ValueError("Für einen AV muss ein Zahlenwert eingegeben werden.")
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError("Für einen AV muss ein Zahlenwert eingegeben werden.") from error
    if not math.isfinite(number):
        raise ValueError("Der AV-Testwert muss eine endliche Zahl sein.")
    return number


def _values_match(expected: object, actual: Optional[object]) -> Optional[bool]:
    if actual is None:
        return None
    if isinstance(expected, bool):
        return bool(expected) == bool(actual)
    return abs(float(expected) - float(actual)) <= 0.001


def _write_result_message(lease: Dict[str, object], effective: Optional[bool]) -> str:
    if effective is True:
        return "Der Testwert wurde angenommen und ist am BACnet-Objekt wirksam."
    if effective is False:
        return "Der Write wurde angenommen, aber am Objekt wirkt eine höhere BACnet-Priorität."
    return "Der Write wurde bestätigt. Der wirksame Objektwert konnte nicht zusätzlich gelesen werden."
