# Mini EMS – Update und Wartung

Diese Anleitung beschreibt den normalen Release-Wechsel auf der Windows-IPC. Der Ablauf ist bewusst kurz:
Das geprüfte Paket wird mit einem Skript installiert, automatisch getestet und kann mit einem Skript
zurückgerollt werden.

## Was beim Update getrennt bleibt

```text
C:\Program Files\MiniEMS\       Anwendung und Dashboard; wird ersetzt
C:\ProgramData\MiniEMS\         Standortdaten; bleibt erhalten
```

Der Standortordner enthält insbesondere:

- `site.sqlite`: aktive Konfiguration, Mapping und Revisionsverlauf
- `data\`: Betriebsdaten und Preiszustände
- `logs\`: Runtime- und Startprotokolle
- `runtime\`: aktueller Zustand und `health.json`

Eine aktive `config.json` gibt es nach der einmaligen Migration nicht mehr. Das Release-Paket darf keine
Standortdaten enthalten.

## Voraussetzungen

- PowerShell als Administrator geöffnet
- neues Release vollständig entpackt, zum Beispiel nach `C:\Temp\MiniEMS-Release-2026.07.2`
- im Paketordner liegen mindestens `mini_ems.exe`, `VERSION`, `SHA256SUMS` und `windows\`
- produktiver Task heißt standardmäßig `MiniEmsPoCRelease`

Der Paketordner ist die Quelle des Updates. `C:\Program Files\MiniEMS` ist dagegen die bereits installierte
Anwendung und darf nicht als `-PackagePath` verwendet werden.

## Reguläres Update

### 1. In den neuen Paketordner wechseln

```powershell
cd "C:\Temp\MiniEMS-Release-2026.07.2"
```

### 2. Trockenlauf ausführen

```powershell
.\windows\update_release.ps1 `
  -PackagePath "C:\Temp\MiniEMS-Release-2026.07.2" `
  -WhatIf
```

Der Trockenlauf prüft Paketpfad, Pflichtdateien und Prüfsummen und zeigt die geplanten Änderungen. Er stoppt
keinen Task und kopiert keine Dateien.

### 3. Update ausführen

```powershell
.\windows\update_release.ps1 `
  -PackagePath "C:\Temp\MiniEMS-Release-2026.07.2"
```

Das Skript erledigt automatisch:

1. Paket-Prüfsummen kontrollieren.
2. Task stoppen und Prozess-Ende abwarten.
3. Den ruhenden Standortordner als `C:\ProgramData\MiniEMS_backup_<Zeit>` sichern.
4. Die bisherige App als `C:\Program Files\MiniEMS_vorher_<Version>` behalten.
5. Das neue Paket nach `C:\Program Files\MiniEMS` kopieren.
6. Den Task starten.
7. Health, Version und neue Fehler im Log prüfen.

Bei Erfolg endet das Skript mit `UPDATE BESTANDEN`. Kein weiterer Installationsbefehl ist erforderlich.

## Prüfung nach dem Update

Der automatische Smoketest reicht für die technische Freigabe. Zusätzlich kurz den echten Zugriffsweg prüfen:

```powershell
Get-ScheduledTask -TaskName MiniEmsPoCRelease
Invoke-RestMethod http://127.0.0.1:8090/api/status
Get-Item "C:\ProgramData\MiniEMS\site.sqlite"
```

Danach im Browser über Caddy öffnen:

```text
https://192.168.244.10/dashboard
```

Erwartet:

- Übersicht lädt und zeigt aktuelle Daten.
- `/api/status` meldet die neue `app_version.version`.
- `api_read_only` ist auf der produktiven IPC `true`.
- „Verwaltung öffnen“ akzeptiert den Freigabecode über denselben HTTPS-Link.
- Standortdaten und bisherige Revisionen sind weiterhin vorhanden.

Der Smoketest kann bei Bedarf einzeln wiederholt werden:

```powershell
.\windows\smoketest_release.ps1 `
  -ExpectedVersion 2026.07.2 `
  -SiteDir "C:\ProgramData\MiniEMS" `
  -ExpectReadOnly $true
```

## Rollback der Anwendung

Wenn der automatische Smoketest fehlschlägt, keinen zweiten Blindversuch starten:

```powershell
.\windows\update_release.ps1 -Rollback
```

Das Skript legt den fehlgeschlagenen App-Stand beiseite, stellt den jüngsten
`MiniEMS_vorher_*`-Ordner wieder her, startet den Task und prüft die alte Version.

Der Standortordner wird dabei absichtlich nicht zurückgesetzt. So gehen keine seit dem Update entstandenen
Betriebsdaten verloren.

## Rollback über die erste site.sqlite-Migration

Beim ersten Wechsel von einer alten `config.json`-Version auf `site.sqlite` ist auch das Standortformat neu.
Soll genau dieser Wechsel zurückgerollt werden, App und Standort gemeinsam wiederherstellen:

```powershell
.\windows\update_release.ps1 -Rollback -RestoreSiteBackup
```

Der aktuelle Standortordner wird nicht gelöscht, sondern als `MiniEMS_fehlgeschlagen_<Zeit>` beiseitegelegt.
Danach wird die jüngste `MiniEMS_backup_*`-Sicherung zurückbenannt. Diese Option nur verwenden, wenn wirklich
auf eine alte `config.json`-Version zurückgegangen wird oder eine Standortmigration nachweislich beschädigt ist.

## Freigabecode erneuern

Bei Verlust des Freigabecodes lokal auf der IPC:

```powershell
Stop-ScheduledTask -TaskName MiniEmsPoCRelease

& "C:\Program Files\MiniEMS\mini_ems.exe" `
  --site-dir "C:\ProgramData\MiniEMS" `
  --reset-admin-code

Start-ScheduledTask -TaskName MiniEmsPoCRelease
```

Der neue Code wird einmal in der PowerShell ausgegeben. Er wird nicht in Dashboard, Log oder API-Antwort
offengelegt.

## Aufräumen nach erfolgreicher Abnahme

Rollback-Stände nicht sofort löschen. Nach einigen stabilen Betriebstagen genügt normalerweise:

- ein zuletzt funktionierender `MiniEMS_vorher_*`-App-Ordner
- eine passende `MiniEMS_backup_*`-Standortsicherung

Ältere Sicherungen erst nach dokumentierter Abnahme manuell entfernen. `C:\ProgramData\MiniEMS` selbst niemals
als Aufräummaßnahme löschen oder durch Dateien aus dem Release-Paket ersetzen.

## Zugehörige Dokumente

- `RELEASE_WORKFLOW.md`: Erstinstallation und einmalige Migration
- `packaging/README.md`: Release bauen
- `HOSTING_SICHERHEIT.md`: Caddy, Netzwerkgrenzen und Rollen
