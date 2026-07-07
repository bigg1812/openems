# Mini EMS – Packaging (H2)

Dieses Verzeichnis liefert das Tooling, um Mini EMS als **versioniertes
Release-Paket** statt als Git-Checkout auszuliefern (`ROADMAP.md`, H2).

**Entscheidung (Nutzer, wörtlich):** *"Release-Paket, initial PyInstaller, später
Nuitka-kompatibel"*.

Der Betriebspfad bleibt unverändert: **externes `config.json` + geplanter
Windows-Task** (`windows/install_task.ps1`, hier nur referenziert). `config.json`
und alle Betriebsdaten sind **niemals** Teil des Pakets.

## Inhalt

| Datei | Zweck |
|---|---|
| `mini_ems.spec` | PyInstaller-Spec (eine Quelle für beide Plattformen) |
| `build_release.sh` | Build für macOS/Linux – lokale Verifikation |
| `build_release.ps1` | Build für Windows – IPC-Release-Erstellung |
| `RELEASE_HINWEISE.md` | wird ins Paket kopiert: Paket vs. Standortdaten |
| `../run_mini_ems_release.cmd` | wird ins Paket kopiert: Launcher für `mini_ems.exe --config <ProgramData>\config.json --loop` |
| `.gitignore` | ignoriert die Arbeitsverzeichnisse `build/` und `dist/` |

Die PyInstaller-Arbeitsverzeichnisse (`packaging/build/`, `packaging/dist/`)
liegen bewusst unterhalb von `packaging/` und sind git-ignoriert. Das repo-eigene
`build/` (unrelated Tooling) wird nicht angefasst.

## Release-Layout

Der Build erzeugt ein One-Dir-Paket unter `packaging/dist/mini_ems/`:

```text
mini_ems/
|-- mini_ems(.exe)                     # ausführbares Artefakt
|-- run_mini_ems_release.cmd           # Windows-Launcher für den geplanten Task
|-- _internal/                         # PyInstaller-Laufzeit (nicht editieren)
|-- dashboard/                         # UI-Assets als DATEN neben dem Binary
|   `-- vendor/
|-- mini_ems_runtime/
|   `-- templates/report.html.j2       # Report-Vorlage als DATEN
|-- sim/                               # optional, nur für Testbetrieb
|-- VERSION                            # semver + Build-Datum + Git-Commit-Hash
|-- SHA256SUMS                         # Prüfsummen über alle Paketdateien
`-- RELEASE_HINWEISE.md                # Paket vs. Standortdaten
```

`dashboard/`, `mini_ems_runtime/templates/` und (für den Testlauf) `data/weather/`
sind **Ressourcen neben dem Executable**, nicht nur eingefroren. Die Runtime löst
sie über `mini_ems_runtime/resources.py` auf: im Git-Betrieb neben `config.json`,
im gepackten Betrieb neben dem Executable.

## Build ausführen

### macOS/Linux (lokale Verifikation)

```bash
python3.12 -m pip install pyinstaller
packaging/build_release.sh
# optional: MINI_EMS_VERSION=2026.07.1 PYTHON=python3.12 packaging/build_release.sh
```

### Windows (IPC-Release)

```powershell
python -m pip install pyinstaller
powershell -ExecutionPolicy Bypass -File packaging\build_release.ps1 -Version 2026.07.0
```

## Testlauf des gepackten Artefakts

```bash
# Einzelzyklus gegen eine Test-Config (schreibt health.json):
packaging/dist/mini_ems/mini_ems --config <pfad>/config.local.json --once

# Kurzer Loop auf einem freien Port zum Prüfen von /api/status und /dashboard:
packaging/dist/mini_ems/mini_ems --config <pfad>/config.local.json --loop
```

`config.json`/`config.local.json` bleiben **außerhalb** des Pakets und werden per
`--config` übergeben. Betriebsdaten (SQLite, Logs, `runtime/`) entstehen relativ
zur Config, nicht im Paket.

## Geplanten Task auf Release-Paket registrieren

Nach dem Kopieren des Release-Ordners nach `C:\Program Files\MiniEMS` und der Standortdaten nach
`C:\ProgramData\MiniEMS`:

```powershell
powershell -ExecutionPolicy Bypass -File windows\install_task.ps1 `
  -Mode release `
  -TaskName MiniEmsPoCRelease `
  -AppDir "C:\Program Files\MiniEMS" `
  -ConfigPath "C:\ProgramData\MiniEMS\config.json" `
  -StartNow:$false
```

Der alte Checkout-Task bleibt damit als Rollback erhalten. Cutover: alten Task stoppen, neuen Task starten,
Healthcheck fahren; bei Problemen den neuen Task stoppen und den alten wieder starten.

## Frozen-Pfadauflösung (Code)

Die einzige Runtime-Änderung für das Packaging ist `mini_ems_runtime/resources.py`
plus eine Zeile in `mini_ems_runtime/app.py`:

- **Git/Entwicklung** (nicht frozen): Ressourcen liegen neben `config.json`
  (`config.base_dir`) – Verhalten exakt wie bisher, alle 85 Tests unverändert grün.
- **Frozen** (`sys.frozen` gesetzt): Ressourcen liegen neben dem Executable
  (`Path(sys.executable).parent`).

Report-Vorlage und Wetter-Cache leiten sich in `http_api.py` aus
`dashboard_dir.parent` ab und folgen der Auflösung automatisch – es gibt keine
zweite Sonderbehandlung.

## Später Nuitka

Die Pfadauflösung ist bewusst **generisch** ("Datenverzeichnisse neben dem
Executable") und enthält keine PyInstaller-only-Mechanik (`sys._MEIPASS` wird
nicht verwendet). `sys.frozen` setzen sowohl PyInstaller als auch Nuitka
(`--standalone`), daher trägt der Runtime-Code bereits beide Fälle.

Wenn später auf Nuitka gewechselt oder ergänzt wird, sind zu tun:

1. **Build-Kommando** ergänzen (die `.spec` ist PyInstaller-spezifisch, der
   Runtime-Code nicht), z. B.:
   `python -m nuitka --standalone --include-data-dir=dashboard=dashboard
   --include-data-dir=mini_ems_runtime/templates=mini_ems_runtime/templates
   --include-data-dir=sim=sim mini_ems.py`.
2. **Ressourcen weiterhin als Daten neben dem Executable** ausliefern
   (`--include-data-dir`), damit `resources.py` sie wie gehabt neben
   `sys.executable` findet – nicht nur ins Binary einbetten.
3. **VERSION-/SHA256SUMS-/RELEASE_HINWEISE-Schritte** aus den Build-Skripten
   wiederverwenden (identisch, unabhängig vom Packager).
4. **Prüfen**, dass `getattr(sys, "frozen", False)` unter der gewählten
   Nuitka-Variante gesetzt ist (bei `--standalone` der Fall); andernfalls in
   `resources.py` die Nuitka-Erkennung (`"__compiled__" in globals()`) ergänzen.
5. Gleiche Verifikation fahren: `--once`-Zyklus (health.json), `--loop` mit
   `/api/status` und `/dashboard`, danach volle Testsuite.

Nuitka erschwert beiläufige Code-Einsicht stärker als PyInstaller (siehe
`HOSTING_SICHERHEIT.md`, Teil 1.3), verhindert entschlossene Extraktion aber
nicht – das ist eine bewusste Abgrenzung, kein DRM-Versprechen.
