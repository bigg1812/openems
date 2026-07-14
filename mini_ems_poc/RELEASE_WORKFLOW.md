# Mini EMS Release-Workflow für einen neuen Standort

Diese Anleitung beschreibt den Erstaufbau eines standortunabhängigen Mini-EMS-Release auf einem Windows-IPC.
Die Standortkonfiguration wird vollständig über die UI gepflegt und liegt revisionssicher in
`C:\ProgramData\MiniEMS\site.sqlite`. Eine `config.json` ist nicht erforderlich.

## Zielaufbau

```text
C:\Program Files\MiniEMS\       App und Dashboard; wird bei Updates ersetzt
C:\ProgramData\MiniEMS\         site.sqlite, Daten, Logs und Runtime-Zustand
```

## 1. Release bauen und kopieren

```powershell
cd C:\dev\openems\mini_ems_poc
powershell -ExecutionPolicy Bypass -File packaging\build_release.ps1 `
  -Version 2026.07.1 `
  -Python C:\dev\openems\.venv\Scripts\python.exe

New-Item -ItemType Directory -Force "C:\Program Files\MiniEMS"
New-Item -ItemType Directory -Force "C:\ProgramData\MiniEMS"
Copy-Item -Path "packaging\dist\mini_ems\*" `
  -Destination "C:\Program Files\MiniEMS" -Recurse -Force
```

## 2. Release-Task registrieren

```powershell
powershell -ExecutionPolicy Bypass -File windows\install_task.ps1 `
  -Mode release `
  -TaskName MiniEmsPoCRelease `
  -AppDir "C:\Program Files\MiniEMS" `
  -SiteDir "C:\ProgramData\MiniEMS" `
  -StartNow:$true
```

Der Task startet:

```text
mini_ems.exe --site-dir C:\ProgramData\MiniEMS --loop
```

Beim ersten Start erzeugt Mini EMS einen sicheren, lokalen Einrichtungsstand in `site.sqlite` und schreibt
den einmaligen Freigabecode nach `C:\ProgramData\MiniEMS\logs\mini_ems_stdout.log`. Dieser Code legt im Browser
genau einmal das erste Admin-Konto an. Konten und Sitzungen liegen danach getrennt in `identity.sqlite`.

```powershell
& "C:\Program Files\MiniEMS\mini_ems.exe" `
  --site-dir "C:\ProgramData\MiniEMS" `
  --reset-admin-code
```

## 3. Standort über die UI einrichten

Dashboard öffnen und **Konfiguration → Standort einrichten** ausführen:

1. Standortname und Betriebsumgebung festlegen.
2. Geräte eintragen oder per Punktliste/Discovery erfassen.
3. Datenpunkte fachlichen Kanälen zuordnen.
4. Lesbare Punkte testen.
5. Optional einen eindeutig benannten `EMS_`-BACnet-Punkt freigeben; Schreiben bleibt bei aktivem API-Schutz aus.
6. Als Admin aktivieren.
7. Den geplanten Task einmal neu starten.

Die Aktivierung schreibt keine Konfigurationsdatei. Sie erzeugt eine neue unveränderliche Revision in
`site.sqlite`; die vorherige Revision bleibt als Rollback-Stand erhalten.

## 4. Bestehende Pilotinstallation migrieren

Liegt beim ersten Start noch `C:\ProgramData\MiniEMS\config.json` vor, wird sie einmalig validiert und in
`site.sqlite` importiert. Danach benennt Mini EMS sie in `config.json.migrated.<Zeitstempel>.bak` um und nutzt
sie nicht mehr. Alternativ kann eine Datei explizit einmalig importiert werden:

Der Release-Launcher erkennt außerdem das alte Task-Argument mit einem `.json`-Pfad und verwendet automatisch
dessen Elternordner als `--site-dir`. Dadurch kann das neue Paket einmal starten, bevor der Task mit `-SiteDir`
neu registriert wird.

```powershell
& "C:\Program Files\MiniEMS\mini_ems.exe" `
  --site-dir "C:\ProgramData\MiniEMS" `
  --import-config "D:\Migration\config.json" `
  --once
```

## 5. Prüfung

```powershell
Get-ScheduledTask -TaskName MiniEmsPoCRelease
Invoke-RestMethod -Uri http://127.0.0.1:8090/api/health
Get-ChildItem "C:\ProgramData\MiniEMS"
```

Erwartet werden `site.sqlite`, nach der ersten Kontoeinrichtung `identity.sqlite`, Betriebsdaten und Logs, aber
keine aktive `config.json`.

Updates ersetzen ausschließlich `C:\Program Files\MiniEMS`. Der gesamte Standortordner unter
`C:\ProgramData\MiniEMS` bleibt erhalten; Details stehen in `UPDATE_WARTUNG.md`.
