# Mini EMS – Release-Paket

Das Paket enthält die Anwendung, das Dashboard, Simulationsressourcen, Zeitzonen, `VERSION`,
`BUILD_REQUIREMENTS.txt`, `CHANGELOG.md` und `SHA256SUMS`. `run_mini_ems_release.cmd` startet:

```text
mini_ems.exe --site-dir C:\ProgramData\MiniEMS --supervise
```

Für die Bedienung auf dem IPC `MiniEMS-Paket.cmd` doppelt anklicken: Menüpunkt 1 prüft das Paket nur
in Simulation, Menüpunkt 2 führt das gesicherte Update aus, Menüpunkt 3 stellt die vorherige
Anwendungsversion wieder her. Git und Python werden dafür auf dem IPC nicht benötigt.

Standortdaten gehören nicht zum Paket und werden bei Updates nicht überschrieben:

- `site.sqlite` – aktive UI-Konfiguration, Mapping-Entwürfe und Revisionen;
- `identity.sqlite` – lokale Viewer-/Admin-Konten, Sitzungen, Audit und BACnet-Schreibfreigaben;
- `data/` – Historie und Spotmarkt-Cache;
- `logs/` – Laufzeit- und Startprotokolle;
- `runtime/` – Zustand, Health und persistenten Supervisor-Neustartnachweis.

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

Das feste Paketprofil verwendet den eingebauten HTML-Bericht; PDF wird über die Browser-Druckfunktion
exportiert. Optionale Jinja2-/WeasyPrint-/BACpypes3-Erweiterungen gehören nicht zum Paket.

Der Supervisor startet einen `--loop`-Kindprozess, erkennt Stillstand/Absturz und erlaubt höchstens drei
Startversuche einschließlich Erststart pro 15 Minuten. Speicherfehler bleiben in Status und Logs sichtbar.
Das ist keine Anlagenfallback-Garantie und kein externer Alarmempfänger.

`+dirty` in `VERSION` kennzeichnet einen lokalen Prüfstand. Ein macOS-/Linux-Paket darf nicht als
Windows-Release installiert werden. Vor Produktiveinsatz sind nativer Windows-Build, Task/SYSTEM,
Update/Rollback und die vereinbarte Standortabnahme erforderlich.
