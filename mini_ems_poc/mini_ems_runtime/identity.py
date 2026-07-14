"""Local users, roles and server-side sessions for one Mini EMS site."""

import hashlib
import hmac
import json
import re
import secrets
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Iterator, List, Optional


ROLE_VIEWER = "viewer"
ROLE_ADMIN = "admin"
ROLES = frozenset({ROLE_VIEWER, ROLE_ADMIN})

SESSION_ABSOLUTE_SECONDS = 12 * 60 * 60
SESSION_IDLE_SECONDS = 30 * 60
LOGIN_FAILURE_LIMIT = 5
LOGIN_LOCK_SECONDS = 5 * 60

_SCRYPT_N = 2**15
_SCRYPT_R = 8
_SCRYPT_P = 3
_SCRYPT_MAXMEM = 128 * 1024 * 1024
_USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9._-]{3,40}$")


@dataclass(frozen=True)
class IdentityUser:
    user_id: str
    username: str
    display_name: str
    role: str
    enabled: bool
    created_at: int

    def to_public_dict(self) -> Dict[str, object]:
        return {
            "id": self.user_id,
            "username": self.username,
            "display_name": self.display_name,
            "role": self.role,
            "enabled": self.enabled,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class AuthSession:
    token: str
    user: IdentityUser
    expires_at: int


class IdentityStore:
    """SQLite-backed identities kept outside immutable site config revisions."""

    def __init__(self, site_dir: Path, now: Callable[[], float] = time.time):
        self.site_dir = Path(site_dir).resolve()
        self.site_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.site_dir / "identity.sqlite"
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
                PRAGMA foreign_keys=ON;
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    username TEXT NOT NULL,
                    username_key TEXT NOT NULL UNIQUE,
                    display_name TEXT NOT NULL,
                    role TEXT NOT NULL CHECK (role IN ('viewer', 'admin')),
                    password_hash BLOB NOT NULL,
                    password_salt BLOB NOT NULL,
                    scrypt_n INTEGER NOT NULL,
                    scrypt_r INTEGER NOT NULL,
                    scrypt_p INTEGER NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    token_hash BLOB PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
                    created_at INTEGER NOT NULL,
                    last_seen_at INTEGER NOT NULL,
                    expires_at INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS sessions_user_id ON sessions(user_id);
                CREATE TABLE IF NOT EXISTS security_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp INTEGER NOT NULL,
                    actor_user_id TEXT,
                    action TEXT NOT NULL,
                    details_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS login_failures (
                    username_key TEXT PRIMARY KEY,
                    failed_count INTEGER NOT NULL,
                    window_started INTEGER NOT NULL,
                    locked_until INTEGER NOT NULL
                );
                """
            )

    def is_initialized(self) -> bool:
        with self._connect() as connection:
            row = connection.execute("SELECT COUNT(*) AS count FROM users").fetchone()
        return bool(row and int(row["count"]) > 0)

    def bootstrap_admin(
        self,
        *,
        bootstrap_code: str,
        expected_code: str,
        username: str,
        display_name: str,
        password: str,
    ) -> AuthSession:
        if self.is_initialized():
            raise PermissionError("Der Verwaltungszugang ist bereits eingerichtet.")
        if not expected_code or not hmac.compare_digest(str(bootstrap_code), str(expected_code)):
            raise PermissionError("Der Freigabecode ist nicht gültig.")
        user = self._insert_user(username, display_name, ROLE_ADMIN, password)
        self.record_event("identity.bootstrap", actor_user_id=user.user_id)
        return self.create_session(user)

    def authenticate(self, username: str, password: str) -> AuthSession:
        try:
            _validate_password(password)
        except ValueError:
            _derive_password("ungueltiger-login-versuch", b"\0" * 16, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P)
            raise PermissionError("Benutzername oder Passwort ist nicht richtig.")
        try:
            username_key = _normalize_username(username)
        except ValueError:
            _derive_password(password, b"\0" * 16, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P)
            raise PermissionError("Benutzername oder Passwort ist nicht richtig.")
        self._check_login_lock(username_key)
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM users WHERE username_key = ?",
                (username_key,),
            ).fetchone()
        if row is None or not bool(row["enabled"]):
            _derive_password(password, b"\0" * 16, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P)
            self._record_login_failure(username_key)
            raise PermissionError("Benutzername oder Passwort ist nicht richtig.")
        candidate = _derive_password(
            password,
            bytes(row["password_salt"]),
            n=int(row["scrypt_n"]),
            r=int(row["scrypt_r"]),
            p=int(row["scrypt_p"]),
        )
        if not hmac.compare_digest(candidate, bytes(row["password_hash"])):
            self._record_login_failure(username_key)
            raise PermissionError("Benutzername oder Passwort ist nicht richtig.")
        self._clear_login_failures(username_key)
        user = _user_from_row(row)
        self.record_event("identity.login", actor_user_id=user.user_id)
        return self.create_session(user)

    def _check_login_lock(self, username_key: str) -> None:
        now = int(self._now())
        with self._connect() as connection:
            row = connection.execute(
                "SELECT locked_until FROM login_failures WHERE username_key = ?",
                (username_key,),
            ).fetchone()
        if row is not None and int(row["locked_until"]) > now:
            raise PermissionError("Zu viele Anmeldeversuche. Bitte in einigen Minuten erneut versuchen.")

    def _record_login_failure(self, username_key: str) -> None:
        now = int(self._now())
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM login_failures WHERE username_key = ?",
                (username_key,),
            ).fetchone()
            if row is None or int(row["window_started"]) + LOGIN_LOCK_SECONDS <= now:
                count = 1
                window_started = now
            else:
                count = int(row["failed_count"]) + 1
                window_started = int(row["window_started"])
            locked_until = now + LOGIN_LOCK_SECONDS if count >= LOGIN_FAILURE_LIMIT else 0
            connection.execute(
                """
                INSERT INTO login_failures (username_key, failed_count, window_started, locked_until)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(username_key) DO UPDATE SET
                    failed_count = excluded.failed_count,
                    window_started = excluded.window_started,
                    locked_until = excluded.locked_until
                """,
                (username_key, count, window_started, locked_until),
            )

    def _clear_login_failures(self, username_key: str) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM login_failures WHERE username_key = ?", (username_key,))

    def create_session(self, user: IdentityUser) -> AuthSession:
        now = int(self._now())
        expires_at = now + SESSION_ABSOLUTE_SECONDS
        token = secrets.token_urlsafe(32)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO sessions (token_hash, user_id, created_at, last_seen_at, expires_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (_token_hash(token), user.user_id, now, now, expires_at),
            )
        return AuthSession(token=token, user=user, expires_at=expires_at)

    def session_user(self, token: Optional[str]) -> Optional[IdentityUser]:
        if not token:
            return None
        now = int(self._now())
        token_hash = _token_hash(token)
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT s.last_seen_at, s.expires_at, u.*
                FROM sessions s JOIN users u ON u.user_id = s.user_id
                WHERE s.token_hash = ?
                """,
                (token_hash,),
            ).fetchone()
            if row is None:
                return None
            expired = int(row["expires_at"]) <= now
            idle = int(row["last_seen_at"]) + SESSION_IDLE_SECONDS <= now
            if expired or idle or not bool(row["enabled"]):
                connection.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))
                return None
            if int(row["last_seen_at"]) + 60 <= now:
                connection.execute(
                    "UPDATE sessions SET last_seen_at = ? WHERE token_hash = ?",
                    (now, token_hash),
                )
        return _user_from_row(row)

    def revoke_session(self, token: Optional[str]) -> None:
        if not token:
            return
        with self._connect() as connection:
            row = connection.execute(
                "SELECT user_id FROM sessions WHERE token_hash = ?",
                (_token_hash(token),),
            ).fetchone()
            connection.execute("DELETE FROM sessions WHERE token_hash = ?", (_token_hash(token),))
        if row is not None:
            self.record_event("identity.logout", actor_user_id=str(row["user_id"]))

    def list_users(self) -> List[IdentityUser]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM users ORDER BY role DESC, display_name COLLATE NOCASE, username_key"
            ).fetchall()
        return [_user_from_row(row) for row in rows]

    def create_user(
        self,
        *,
        username: str,
        display_name: str,
        role: str,
        password: str,
        actor_user_id: str,
    ) -> IdentityUser:
        user = self._insert_user(username, display_name, role, password)
        self.record_event(
            "identity.user_created",
            actor_user_id=actor_user_id,
            details={"target_user_id": user.user_id, "role": user.role},
        )
        return user

    def update_user(
        self,
        *,
        user_id: str,
        role: Optional[str],
        enabled: Optional[bool],
        password: Optional[str],
        actor_user_id: str,
    ) -> IdentityUser:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
            if row is None:
                raise ValueError("Das Benutzerkonto wurde nicht gefunden.")
            next_role = _validate_role(role) if role is not None else str(row["role"])
            next_enabled = bool(enabled) if enabled is not None else bool(row["enabled"])
            if str(row["role"]) == ROLE_ADMIN and bool(row["enabled"]) and (
                next_role != ROLE_ADMIN or not next_enabled
            ):
                count = connection.execute(
                    "SELECT COUNT(*) AS count FROM users WHERE role = 'admin' AND enabled = 1"
                ).fetchone()
                if count is not None and int(count["count"]) <= 1:
                    raise ValueError("Mindestens ein aktiver Admin muss erhalten bleiben.")
            updates = ["role = ?", "enabled = ?", "updated_at = ?"]
            values: List[object] = [next_role, int(next_enabled), int(self._now())]
            if password:
                salt, password_hash = _hash_password(password)
                updates.extend(
                    [
                        "password_hash = ?",
                        "password_salt = ?",
                        "scrypt_n = ?",
                        "scrypt_r = ?",
                        "scrypt_p = ?",
                    ]
                )
                values.extend([password_hash, salt, _SCRYPT_N, _SCRYPT_R, _SCRYPT_P])
            values.append(user_id)
            connection.execute(
                "UPDATE users SET {0} WHERE user_id = ?".format(", ".join(updates)),
                values,
            )
            if not next_enabled or password:
                connection.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
            updated = connection.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        self.record_event(
            "identity.user_updated",
            actor_user_id=actor_user_id,
            details={
                "target_user_id": user_id,
                "role": next_role,
                "enabled": next_enabled,
                "password_changed": bool(password),
            },
        )
        return _user_from_row(updated)

    def reset_first_admin_password(self, password: str) -> IdentityUser:
        """Local IPC recovery path; never exposed through the network API."""
        salt, password_hash = _hash_password(password)
        now = int(self._now())
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM users
                WHERE role = 'admin' AND enabled = 1
                ORDER BY created_at, username_key LIMIT 1
                """
            ).fetchone()
            if row is None:
                raise ValueError("Es ist kein aktives Admin-Konto vorhanden.")
            connection.execute(
                """
                UPDATE users SET
                    password_hash = ?, password_salt = ?, scrypt_n = ?, scrypt_r = ?,
                    scrypt_p = ?, updated_at = ?
                WHERE user_id = ?
                """,
                (
                    password_hash,
                    salt,
                    _SCRYPT_N,
                    _SCRYPT_R,
                    _SCRYPT_P,
                    now,
                    str(row["user_id"]),
                ),
            )
            connection.execute("DELETE FROM sessions WHERE user_id = ?", (str(row["user_id"]),))
            updated = connection.execute("SELECT * FROM users WHERE user_id = ?", (str(row["user_id"]),)).fetchone()
        user = _user_from_row(updated)
        self.record_event(
            "identity.admin_password_recovered",
            details={"target_user_id": user.user_id, "username": user.username},
        )
        return user

    def record_event(
        self,
        action: str,
        *,
        actor_user_id: Optional[str] = None,
        details: Optional[Dict[str, object]] = None,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO security_events (timestamp, actor_user_id, action, details_json)
                VALUES (?, ?, ?, ?)
                """,
                (
                    int(self._now()),
                    actor_user_id,
                    str(action),
                    json.dumps(details or {}, ensure_ascii=False, separators=(",", ":"), sort_keys=True),
                ),
            )

    def recent_events(self, limit: int = 20) -> List[Dict[str, object]]:
        safe_limit = min(max(int(limit), 1), 100)
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT e.*, u.display_name AS actor_name
                FROM security_events e LEFT JOIN users u ON u.user_id = e.actor_user_id
                ORDER BY event_id DESC LIMIT ?
                """,
                (safe_limit,),
            ).fetchall()
        return [
            {
                "timestamp": int(row["timestamp"]),
                "action": str(row["action"]),
                "actor": str(row["actor_name"]) if row["actor_name"] is not None else None,
                "details": json.loads(str(row["details_json"])),
            }
            for row in rows
        ]

    def _insert_user(self, username: str, display_name: str, role: str, password: str) -> IdentityUser:
        clean_username = _validate_username(username)
        clean_display_name = _validate_display_name(display_name, clean_username)
        clean_role = _validate_role(role)
        salt, password_hash = _hash_password(password)
        now = int(self._now())
        user_id = secrets.token_urlsafe(12)
        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO users (
                        user_id, username, username_key, display_name, role,
                        password_hash, password_salt, scrypt_n, scrypt_r, scrypt_p,
                        enabled, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                    """,
                    (
                        user_id,
                        clean_username,
                        clean_username.casefold(),
                        clean_display_name,
                        clean_role,
                        password_hash,
                        salt,
                        _SCRYPT_N,
                        _SCRYPT_R,
                        _SCRYPT_P,
                        now,
                        now,
                    ),
                )
        except sqlite3.IntegrityError as error:
            raise ValueError("Dieser Benutzername ist bereits vergeben.") from error
        return IdentityUser(
            user_id=user_id,
            username=clean_username,
            display_name=clean_display_name,
            role=clean_role,
            enabled=True,
            created_at=now,
        )


def _validate_username(value: str) -> str:
    username = str(value or "").strip()
    if not _USERNAME_PATTERN.fullmatch(username):
        raise ValueError("Der Benutzername muss 3 bis 40 Zeichen lang sein und darf Buchstaben, Zahlen, Punkt, Bindestrich und Unterstrich enthalten.")
    return username


def _normalize_username(value: str) -> str:
    return _validate_username(value).casefold()


def _validate_display_name(value: str, fallback: str) -> str:
    display_name = str(value or "").strip() or fallback
    if len(display_name) > 80:
        raise ValueError("Der Anzeigename darf höchstens 80 Zeichen lang sein.")
    return display_name


def _validate_role(value: str) -> str:
    role = str(value or "").strip().lower()
    if role not in ROLES:
        raise ValueError("Die Rolle muss Viewer oder Admin sein.")
    return role


def _validate_password(password: str) -> bytes:
    raw = str(password or "").encode("utf-8")
    if len(str(password or "")) < 12:
        raise ValueError("Das Passwort muss mindestens 12 Zeichen lang sein.")
    if len(raw) > 1024:
        raise ValueError("Das Passwort ist zu lang.")
    return raw


def _hash_password(password: str) -> tuple[bytes, bytes]:
    salt = secrets.token_bytes(16)
    return salt, _derive_password(password, salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P)


def _derive_password(password: str, salt: bytes, *, n: int, r: int, p: int) -> bytes:
    return hashlib.scrypt(
        _validate_password(password),
        salt=salt,
        n=n,
        r=r,
        p=p,
        maxmem=_SCRYPT_MAXMEM,
        dklen=32,
    )


def _token_hash(token: str) -> bytes:
    return hashlib.sha256(str(token).encode("utf-8")).digest()


def _user_from_row(row: sqlite3.Row) -> IdentityUser:
    return IdentityUser(
        user_id=str(row["user_id"]),
        username=str(row["username"]),
        display_name=str(row["display_name"]),
        role=str(row["role"]),
        enabled=bool(row["enabled"]),
        created_at=int(row["created_at"]),
    )
