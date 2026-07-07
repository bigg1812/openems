# Mini EMS – Release-Paket

Diese Datei liegt dem gebauten Release-Paket bei und erklärt kurz, **was zum
Paket gehört** und **was Standortdaten sind**. Ausführlicher Update-, Healthcheck-
und Rollback-Ablauf: siehe `UPDATE_WARTUNG.md` im Repository.

## Was zum Paket gehört (wird bei einem Update ersetzt)

- `mini_ems` bzw. `mini_ems.exe` – das ausführbare Artefakt.
- `run_mini_ems_release.cmd` – Windows-Launcher für den geplanten Task. Startet
  `mini_ems.exe --config <externe config.json> --loop` und schreibt die
  Konsolenausgabe nach `<Standortdaten>\logs\mini_ems_stdout.log`.
- `_internal/` – von PyInstaller mitgelieferte Laufzeitbibliotheken (nicht von
  Hand bearbeiten).
- `dashboard/` – UI-Assets (inklusive `vendor/`). Liegen als Dateien neben dem
  Binary, nicht nur eingefroren, und können bei Bedarf eingesehen werden.
- `mini_ems_runtime/templates/` – Report-Vorlage `report.html.j2`.
- `sim/` – Beispiel-Simulationsdaten, nur für einen optionalen Testlauf auf der
  IPC (`--config <test-config> --once`), nicht für den Produktivbetrieb nötig.
- `VERSION` – lesbare Versionskennung (Semver + Build-Datum + Git-Commit-Hash).
- `SHA256SUMS` – Prüfsummen über alle Paketdateien.
- `RELEASE_HINWEISE.md` – diese Datei.

## Was NICHT zum Paket gehört (Standortdaten, bleiben unangetastet)

Diese Dateien werden **nie** aus dem Paket geliefert oder überschrieben. Der
Betriebspfad bleibt: **externes `config.json` + geplanter Windows-Task**.

- `config.json` – Standortkonfiguration (Netzwerk, Punkte, Regler, Safety-Flags,
  `api.host`). Liegt außerhalb des Pakets und wird beim Start per
  `--config <pfad>` übergeben.
- `data/` – Betriebsdaten (SQLite-Historie, Spotmarkt-Cache).
- `logs/` – Logdateien.
- `runtime/` – Laufzeit-/Health-Zustand (`state.json`, `health.json`).

## Version feststellen

Auf der IPC die Datei `VERSION` im Installationsordner öffnen, z. B.:

```powershell
Get-Content .\VERSION
```

## Prüfsumme kontrollieren

```powershell
# Beispiel für eine einzelne Datei; SHA256SUMS listet alle Paketdateien.
Get-FileHash .\mini_ems.exe -Algorithm SHA256
```
