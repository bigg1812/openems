# Mini EMS – Update, Rollback und Wartung

Der normale Ablauf zum **Bauen und Installieren** eines neuen Releases steht kurz und vollständig in
`RELEASE_WORKFLOW.md`. Diese Datei wird nur benötigt, wenn ein Update fehlschlägt oder alte Sicherungen
aufgeräumt werden sollen.

## Was beim Update erhalten bleibt

```text
C:\Program Files\MiniEMS\       Anwendung; wird ersetzt
C:\ProgramData\MiniEMS\         Standortdaten; bleiben erhalten
```

Zu den Standortdaten gehören `site.sqlite`, `identity.sqlite`, Betriebsdaten, Logs und Runtime-Zustand.
`C:\ProgramData\MiniEMS` niemals durch Dateien aus dem Release-Paket ersetzen.

## Was das Update-Skript automatisch macht

`windows\update_release.ps1`:

1. prüft Paket und Prüfsummen,
2. stoppt Task und Prozess,
3. sichert Standortdaten und bisherige Anwendung,
4. installiert das neue Paket,
5. startet Mini EMS,
6. prüft Version und Health.

Bei Erfolg erscheint:

```text
[update] UPDATE BESTANDEN
```

## Rollback nach einem fehlgeschlagenen Update

Eine PowerShell mit **Als Administrator ausführen** öffnen:

```powershell
$Package = "C:\dev\openems\mini_ems_poc\packaging\dist\mini_ems"

& powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File "$Package\windows\update_release.ps1" `
  -Rollback
```

Das Skript stellt die zuletzt funktionierende Anwendung wieder her, startet den Task und prüft die alte
Version. Die aktuellen Standortdaten bleiben dabei erhalten.

Nur wenn ausdrücklich eine fehlerhafte Standortdaten-Migration zurückgenommen werden muss:

```powershell
$Package = "C:\dev\openems\mini_ems_poc\packaging\dist\mini_ems"

& powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File "$Package\windows\update_release.ps1" `
  -Rollback `
  -RestoreSiteBackup
```

`-RestoreSiteBackup` nicht bei einem normalen App-Rollback verwenden, weil sonst neuere Betriebsdaten durch
die Sicherung ersetzt werden.

## Zustand prüfen

```powershell
Get-Content "C:\Program Files\MiniEMS\VERSION"
Get-ScheduledTask -TaskName MiniEmsPoCRelease
Invoke-RestMethod "http://127.0.0.1:8090/api/health"
Get-Item "C:\ProgramData\MiniEMS\site.sqlite"
```

Dashboard:

```text
https://192.168.244.10/dashboard
```

Erwartet werden eine laufende Release-Version, HTTP `200`, `api_read_only: true` und die unveränderte
`site.sqlite`.

## Admin-Zugang lokal zurücksetzen

Eine PowerShell als Administrator öffnen:

```powershell
Stop-ScheduledTask -TaskName MiniEmsPoCRelease

& "C:\Program Files\MiniEMS\mini_ems.exe" `
  --site-dir "C:\ProgramData\MiniEMS" `
  --reset-admin-code

Start-ScheduledTask -TaskName MiniEmsPoCRelease
```

Bei einem neuen Standort wird ein neuer einmaliger Freigabecode ausgegeben. Wenn bereits Konten existieren,
wird für das erste aktive Admin-Konto ein temporäres Passwort erzeugt. Danach sofort ein eigenes Passwort
setzen.

## Alte Sicherungen aufräumen

Das Update-Skript lässt Sicherungen bewusst liegen:

```text
C:\Program Files\MiniEMS_vorher_<Version>
C:\ProgramData\MiniEMS_backup_<Zeit>
```

Erst nach einigen stabilen Betriebstagen aufräumen. Mindestens den letzten funktionierenden App-Stand und
eine passende Standort-Sicherung behalten. `C:\ProgramData\MiniEMS` selbst niemals löschen.
