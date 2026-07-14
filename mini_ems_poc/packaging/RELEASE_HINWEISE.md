# Mini EMS – Release-Paket

Das Paket enthält die Anwendung, das Dashboard, Vorlagen, Simulationsressourcen, `VERSION`,
`CHANGELOG.md` und `SHA256SUMS`. `run_mini_ems_release.cmd` startet:

```text
mini_ems.exe --site-dir C:\ProgramData\MiniEMS --loop
```

Standortdaten gehören nicht zum Paket und werden bei Updates nicht überschrieben:

- `site.sqlite` – aktive UI-Konfiguration, Mapping-Entwürfe und Revisionen;
- `identity.sqlite` – lokale Viewer-/Admin-Konten, Sitzungen, Audit und BACnet-Schreibfreigaben;
- `data/` – Historie und Spotmarkt-Cache;
- `logs/` – Laufzeit- und Startprotokolle;
- `runtime/` – Zustand und Health-Dateien.

Ein neuer Standort startet sicher in Simulation und wird über **Konfiguration → Standort einrichten**
konfiguriert. Der einmalige Freigabecode steht nach dem ersten Start in
`C:\ProgramData\MiniEMS\logs\mini_ems_stdout.log` und legt genau einmal das erste Admin-Konto an.

Eine vorhandene `config.json` wird beim ersten Start einmalig nach `site.sqlite` migriert und danach nur
noch als `config.json.migrated.<Zeitstempel>.bak` aufbewahrt. Sie ist kein Runtime-Eingang mehr.

Version prüfen:

```powershell
Get-Content .\VERSION
Get-FileHash .\mini_ems.exe -Algorithm SHA256
```
