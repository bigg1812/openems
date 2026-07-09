"""Resolve where bundled application resources live.

Application resources are the read-only files that ship *with* the code:
``dashboard/`` (UI assets), ``mini_ems_runtime/templates/`` (report template)
and ``data/weather/`` (weather cache). They must not be confused with
site/operational data (``config.json``, SQLite history, logs, runtime state),
which stay next to the external ``config.json`` on the IPC.

In a normal Git/development checkout the config file sits next to those
resource directories, so the resource base is simply ``config.base_dir`` and
behaviour is unchanged. When the app runs as a packaged, frozen artifact
(PyInstaller today, Nuitka later), ``config.json`` lives in a separate
operational directory, so the resources are resolved next to the executable
instead. Both packagers set ``sys.frozen``, so this resolution is generic and
carries no PyInstaller-only mechanics into the runtime (H2 / Nuitka
compatibility).
"""

import subprocess
import sys
from pathlib import Path
from typing import Dict, Optional


def is_frozen() -> bool:
    """True when running from a packaged executable (PyInstaller/Nuitka)."""
    return bool(getattr(sys, "frozen", False))


def read_app_version(resource_base: Path) -> Dict[str, Optional[str]]:
    """Read the ``VERSION`` file that ships next to the executable in a release.

    Returns a small, additive dict with ``version``, ``git_commit`` and
    ``build_date`` for the ``/api/status`` payload and the Systemstatus page.

    - **Release** (``VERSION`` present, built by ``packaging/build_release.*``):
      the parsed ``key=value`` fields.
    - **Git/development** (no ``VERSION`` file): ``version="dev"`` plus the short
      Git commit if it can be determined, otherwise just ``"dev"``.
    - **Defective** ``VERSION`` (unreadable or without a ``version=`` line):
      ``version="unbekannt"`` so the UI never shows a blank or misleading value.
    """
    version_file = Path(resource_base) / "VERSION"
    if not version_file.exists():
        return _dev_version(resource_base)
    try:
        text = version_file.read_text(encoding="utf-8")
    except OSError:
        return _unknown_version()

    fields: Dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or "=" not in line:
            continue
        key, value = line.split("=", 1)
        fields[key.strip()] = value.strip()

    version = fields.get("version")
    if not version:
        return _unknown_version()
    return {
        "version": version,
        "git_commit": fields.get("git_commit") or None,
        "build_date": fields.get("build_date") or None,
    }


def _dev_version(resource_base: Path) -> Dict[str, Optional[str]]:
    return {
        "version": "dev",
        "git_commit": _git_short_commit(resource_base),
        "build_date": None,
    }


def _unknown_version() -> Dict[str, Optional[str]]:
    return {"version": "unbekannt", "git_commit": None, "build_date": None}


def _git_short_commit(resource_base: Path) -> Optional[str]:
    """Short Git commit for the dev build, or ``None`` when not determinable."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(resource_base),
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    commit = result.stdout.strip()
    return commit or None


def resource_base_dir(config_base_dir: Path) -> Path:
    """Directory that contains ``dashboard/``, ``mini_ems_runtime/templates/`` etc.

    - Development/Git checkout (not frozen): the config directory, exactly as
      before – existing behaviour is preserved bit for bit.
    - Frozen artifact: the directory next to the executable, where the build
      places ``dashboard/`` and ``mini_ems_runtime/templates/`` as data beside
      the binary (not only embedded).
    """
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(config_base_dir)
