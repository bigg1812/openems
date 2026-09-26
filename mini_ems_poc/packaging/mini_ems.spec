# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for the Mini EMS release package (H2).
#
# Design goals (see packaging/README.md):
#   * One-dir build: executable, runtime and resources share one directory.
#   * Bundled *resources* (dashboard/, mini_ems_runtime/templates/, sim/) are
#     shipped as DATA next to the executable, not only frozen inside it, so the
#     operator can inspect/replace UI assets and the report template without a
#     rebuild. The runtime resolves them next to the executable via
#     mini_ems_runtime/resources.py (frozen-aware, PyInstaller *and* Nuitka).
#   * site.sqlite and all operational data are NEVER part of the build.
#
# SPECPATH is the directory of this spec (packaging/); the project root is its
# parent. The build/dist working dirs live under packaging/ (see build scripts).

import os
from PyInstaller.utils.hooks import collect_data_files

PROJECT_DIR = os.path.abspath(os.path.join(SPECPATH, os.pardir))

# Resource files that ship next to the executable. Destinations are relative to
# the one-dir output root, mirroring the Git layout so dashboard_dir.parent
# lookups (report template, weather cache) work unchanged when frozen.
datas = [
    (os.path.join(PROJECT_DIR, "dashboard"), "dashboard"),
    # sim/ is optional and only needed for a simulated test run on the IPC.
    (os.path.join(PROJECT_DIR, "sim"), "sim"),
] + collect_data_files("tzdata")

a = Analysis(
    [os.path.join(PROJECT_DIR, "mini_ems.py")],
    pathex=[PROJECT_DIR],
    binaries=[],
    datas=datas,
    hiddenimports=["tzdata"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Fixed lean profile, independent of optional packages on the build host.
    # Reports use the stdlib HTML renderer and browser print/PDF.
    excludes=["weasyprint", "jinja2", "bacpypes3", "tkinter"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="mini_ems",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # Flatten the one-dir layout: keep resources (dashboard/, mini_ems_runtime/
    # templates/, sim/) directly beside the executable instead of inside the
    # default _internal/ folder. This is what resources.py expects (data next to
    # sys.executable) and keeps the resolution generic for Nuitka.
    contents_directory=".",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="mini_ems",
)
