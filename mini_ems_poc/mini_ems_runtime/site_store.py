"""Persistent UI-owned site configuration.

The runtime deliberately does not read a ``config.json`` file.  Every accepted
UI change creates an immutable revision in ``site.sqlite`` and moves the active
revision pointer in the same SQLite transaction.  This gives mapping drafts,
rollback evidence and audit metadata one durable home without exposing a
second, manually editable configuration source.
"""

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterator, List, Optional


def _utc_revision() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


@dataclass(frozen=True)
class SiteRevision:
    revision: str
    timestamp: str
    action: str
    actor: str
    config: Dict[str, object]
    mapping_draft: Optional[Dict[str, object]]
    details: Dict[str, object]


class SiteConfigStore:
    """SQLite-backed source of truth for one edge site's UI configuration."""

    def __init__(self, site_dir: Path):
        self.site_dir = Path(site_dir).resolve()
        self.site_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.site_dir / "site.sqlite"
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
                PRAGMA foreign_keys=ON;
                CREATE TABLE IF NOT EXISTS site_revisions (
                    revision TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    action TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    config_json TEXT NOT NULL,
                    mapping_json TEXT,
                    details_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS site_state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """
            )

    def has_active_config(self) -> bool:
        return self.active_revision() is not None

    def active_revision(self) -> Optional[str]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT value FROM site_state WHERE key = 'active_revision'"
            ).fetchone()
        return str(row["value"]) if row is not None else None

    def active_config(self) -> Dict[str, object]:
        revision = self.active_revision()
        if revision is None:
            raise ValueError("Der Standort ist noch nicht initialisiert.")
        with self._connect() as connection:
            row = connection.execute(
                "SELECT config_json FROM site_revisions WHERE revision = ?",
                (revision,),
            ).fetchone()
        if row is None:
            raise ValueError("Die aktive Standortrevision ist nicht vorhanden.")
        raw = json.loads(str(row["config_json"]))
        if not isinstance(raw, dict):
            raise ValueError("Die aktive Standortkonfiguration ist ungültig.")
        return raw

    def active_fingerprint(self) -> Optional[str]:
        if not self.has_active_config():
            return None
        payload = _canonical_json(self.active_config()).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def save_revision(
        self,
        config: Dict[str, object],
        *,
        action: str,
        actor: str,
        mapping_draft: Optional[Dict[str, object]] = None,
        details: Optional[Dict[str, object]] = None,
        revision: Optional[str] = None,
    ) -> str:
        if not isinstance(config, dict):
            raise ValueError("Die Standortkonfiguration muss ein Objekt sein.")
        timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        revision = revision or _utc_revision()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                INSERT INTO site_revisions (
                    revision, timestamp, action, actor, config_json, mapping_json, details_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    revision,
                    timestamp,
                    action,
                    actor,
                    _canonical_json(config),
                    _canonical_json(mapping_draft) if mapping_draft is not None else None,
                    _canonical_json(details or {}),
                ),
            )
            connection.execute(
                """
                INSERT INTO site_state (key, value) VALUES ('active_revision', ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (revision,),
            )
        return revision

    def revision(self, revision: str) -> SiteRevision:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM site_revisions WHERE revision = ?",
                (revision,),
            ).fetchone()
        if row is None:
            raise KeyError(revision)
        mapping = json.loads(str(row["mapping_json"])) if row["mapping_json"] is not None else None
        return SiteRevision(
            revision=str(row["revision"]),
            timestamp=str(row["timestamp"]),
            action=str(row["action"]),
            actor=str(row["actor"]),
            config=json.loads(str(row["config_json"])),
            mapping_draft=mapping,
            details=json.loads(str(row["details_json"])),
        )

    def history(self, limit: int = 50) -> List[SiteRevision]:
        safe_limit = min(max(int(limit), 1), 200)
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT revision FROM site_revisions ORDER BY timestamp DESC, revision DESC LIMIT ?",
                (safe_limit,),
            ).fetchall()
        return [self.revision(str(row["revision"])) for row in rows]

    def latest_for_action(self, action: str) -> Optional[SiteRevision]:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT revision FROM site_revisions
                WHERE action = ? ORDER BY timestamp DESC, revision DESC LIMIT 1
                """,
                (action,),
            ).fetchone()
        return self.revision(str(row["revision"])) if row is not None else None
