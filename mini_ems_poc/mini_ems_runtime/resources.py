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

import sys
from pathlib import Path


def is_frozen() -> bool:
    """True when running from a packaged executable (PyInstaller/Nuitka)."""
    return bool(getattr(sys, "frozen", False))


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
