# Mini EMS Release-Workflow fuer ein neues Projekt

Diese Anleitung beschreibt den Zielablauf fuer eine neue Mini-EMS-Installation auf einem IPC.
Sie geht davon aus, dass noch kein alter Mini-EMS-Prozess laeuft.

Stand 2026-07-09: Die Pilot-IPC ist bereits einen Schritt weiter gehaertet (Release-Task hinter Caddy,
API nur lokal, `api.read_only`). Diese Datei beschreibt den frischen Erstaufbau bis zur lauffaehigen
Release-Installation; danach folgen die Haertungsschritte aus `HOSTING_SICHERHEIT.md` und laufende Updates
aus `UPDATE_WARTUNG.md`.

## Grundidee

Mini EMS besteht aus zwei getrennten Teilen:

1. Die App
   - liegt in `C:\Program Files\MiniEMS`
   - enthaelt `mini_ems.exe`, Dashboard, Runtime-Dateien und DLLs
   - wird bei Updates ersetzt

2. Die Projektdaten
   - liegen in `C:\ProgramData\MiniEMS`
   - enthalten `config.json`, `data`, `logs` und `runtime`
   - bleiben bei Updates erhalten

Dadurch kann ein Update die App ersetzen, ohne die Standortkonfiguration oder Betriebsdaten zu
ueberschreiben.

## 1. Release-Paket bauen

Im Git-/Entwicklungsordner:

```powershell
cd C:\dev\openems\mini_ems_poc
C:\dev\openems\mini_ems_poc\.venv\Scripts\python.exe -m pip install pyinstaller
powershell -ExecutionPolicy Bypass -File packaging\build_release.ps1 -Version 2026.07 -Python C:\dev\openems\mini_ems_poc\.venv\Scripts\python.exe
```

Ergebnis:

```text
C:\dev\openems\mini_ems_poc\packaging\dist\mini_ems
```

## 2. Betriebsordner anlegen

In einer PowerShell als Administrator:

```powershell
New-Item -ItemType Directory -Force "C:\Program Files\MiniEMS"
New-Item -ItemType Directory -Force "C:\ProgramData\MiniEMS"
```

## 3. Release-App kopieren

```powershell
Copy-Item -Path "C:\dev\openems\mini_ems_poc\packaging\dist\mini_ems\*" `
  -Destination "C:\Program Files\MiniEMS" `
  -Recurse `
  -Force
```

Pruefen:

```powershell
Get-ChildItem "C:\Program Files\MiniEMS"
```

Wichtig sind mindestens:

- `mini_ems.exe`
- `run_mini_ems_release.cmd`
- `VERSION`
- `SHA256SUMS`

## 4. Start-Konfiguration anlegen

Mini EMS braucht zum ersten Start eine gueltige `config.json`.
Die UI kann die Konfiguration erst bearbeiten, wenn Mini EMS bereits laeuft.

Beispiel:

```powershell
Copy-Item -Path "C:\dev\openems\mini_ems_poc\config.json" `
  -Destination "C:\ProgramData\MiniEMS\config.json" `
  -Force
```

Falls die Datei mit Windows PowerShell geschrieben oder bearbeitet wurde, sicherstellen, dass sie
als UTF-8 ohne BOM gespeichert ist. Ein BOM fuehrt beim aktuellen Release zu:

```text
json.decoder.JSONDecodeError: Unexpected UTF-8 BOM
```

## 5. Admin-Token fuer die UI setzen

Damit die Konfigurationsseite speichern darf, braucht `api.config_admin_token` einen Wert.
Der Token gehoert in:

```text
C:\ProgramData\MiniEMS\config.json
```

Beispiel im `api`-Block:

```json
"api": {
  "enabled": true,
  "host": "192.168.244.10",
  "port": 8090,
  "history_default_limit": 96,
  "config_admin_token": "HIER_EIN_LANGER_ZUFAELLIGER_TOKEN"
}
```

## 6. Release-Task registrieren

In einer PowerShell als Administrator:

```powershell
cd C:\dev\openems\mini_ems_poc

powershell -ExecutionPolicy Bypass -Command "& '.\windows\install_task.ps1' -Mode release -TaskName MiniEmsPoCRelease -AppDir 'C:\Program Files\MiniEMS' -ConfigPath 'C:\ProgramData\MiniEMS\config.json' -StartNow:`$false"
```

Der Task wird angelegt, aber noch nicht gestartet.

Pruefen:

```powershell
Get-ScheduledTask -TaskName MiniEmsPoCRelease | Format-List TaskName,State
(Get-ScheduledTask -TaskName MiniEmsPoCRelease).Actions | Format-List *
```

Die Arguments-Zeile sollte wegen `Program Files` doppelt gequotet sein:

```text
/c ""C:\Program Files\MiniEMS\run_mini_ems_release.cmd" "C:\ProgramData\MiniEMS\config.json""
```

## 7. Release-Task starten

```powershell
Start-ScheduledTask -TaskName MiniEmsPoCRelease
```

Pruefen:

```powershell
Get-NetTCPConnection -LocalPort 8090 | Select-Object LocalAddress,LocalPort,State,OwningProcess
Invoke-RestMethod -Uri http://192.168.244.10:8090/api/status
```

Erwartung:

- Port `8090` lauscht auf `192.168.244.10`
- `/api/status` antwortet
- `health.status` ist `healthy` oder ein fachlich erklaerbarer Zustand

Wenn die H4/H5-Haertung bereits angewandt ist, ist diese Direktpruefung bewusst nicht mehr gueltig: dann
lauscht `8090` nur auf `127.0.0.1`, und der Netz-/Secomea-Zugriff laeuft ueber Caddy auf
`https://192.168.244.10`.

## 8. Prozesspfad pruefen

Die Prozessnummer aus `OwningProcess` einsetzen:

```powershell
Get-CimInstance Win32_Process -Filter "ProcessId = <PID>" | Format-List ProcessId,Name,CommandLine
```

Ziel:

- Es laeuft `mini_ems.exe`
- nicht mehr `C:\dev\openems\mini_ems_poc\mini_ems.py`

## 9. Dashboard und UI-Konfiguration nutzen

Dashboard:

```text
http://192.168.244.10:8090/dashboard
```

Ab diesem Punkt kann die Konfigurationsseite genutzt werden.

Wichtig:

- Aenderungen an Start-/Runtime-Feldern werden oft erst nach Neustart aktiv.
- Vor dem Speichern erstellt die Runtime ein Backup der aktiven Config.
- Die aktive Config bleibt in `C:\ProgramData\MiniEMS\config.json`.

## 10. Update einer bestehenden Installation

Codeaenderungen im Git-Ordner aktualisieren die Release-Version nicht automatisch.

Fuer ein Update:

1. Im Git-Ordner Code aendern.
2. Tests ausfuehren.
3. Neues Release-Paket bauen.
4. Task stoppen.
5. Neue Paketdateien nach `C:\Program Files\MiniEMS` kopieren.
6. `C:\ProgramData\MiniEMS` nicht loeschen und nicht ueberschreiben.
7. Task wieder starten.
8. Healthcheck ausfuehren.

Die Standortdaten bleiben dabei erhalten.

## Sonderfall: alter Mini EMS laeuft noch

Wenn bereits ein alter Mini EMS aus dem Git-Checkout laeuft, ist der Ablauf komplizierter.
Dann blockiert der alte Prozess Port `8090`.

Pruefen:

```powershell
Get-NetTCPConnection -LocalPort 8090 | Select-Object LocalAddress,LocalPort,State,OwningProcess
```

Prozess anzeigen:

```powershell
Get-CimInstance Win32_Process -Filter "ProcessId = <PID>" | Format-List ProcessId,Name,CommandLine,ParentProcessId
```

Wenn dort `C:\dev\openems\mini_ems_poc\mini_ems.py` steht, laeuft noch der alte Checkout-Betrieb.
Dann muss der alte Prozessbaum bewusst gestoppt werden, bevor der Release-Task starten kann.

Das war der Grund, warum die Umstellung beim ersten IPC-Test deutlich komplizierter war als eine
frische Installation.

## Danach: Haertung und Update-Ablauf

Dieser Ablauf endet mit einer direkt im Netz erreichbaren API (`192.168.244.10:8090`, ohne TLS, ohne
`api.read_only`). Das ist der Ausgangszustand fuer ein neues Projekt, nicht der empfohlene Dauerzustand.
Fuer die weiteren Haertungsschritte (API intern auf `127.0.0.1` binden, Caddy-Reverse-Proxy mit HTTPS
davor, `api.read_only` aktivieren, Windows-Dateirechte) siehe `HOSTING_SICHERHEIT.md`, Teile 3 und 4.
Laufende Updates nach diesem Erstaufbau laufen ueber `UPDATE_WARTUNG.md` (Skript-first:
`windows/update_release.ps1`).
