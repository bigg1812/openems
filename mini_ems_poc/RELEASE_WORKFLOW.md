# Mini EMS – Release bauen und starten

Diese Anleitung ist der kurze Standardablauf für neue Mini-EMS-Releases auf dem Windows-IPC.

```text
C:\Program Files\MiniEMS\       installierte Anwendung; wird beim Update ersetzt
C:\ProgramData\MiniEMS\         Standortdaten; bleiben beim Update erhalten
```

`C:\ProgramData\MiniEMS` wird beim Release-Wechsel nicht überschrieben. Dort bleiben insbesondere
`site.sqlite`, `identity.sqlite`, Betriebsdaten und Logs erhalten.

## Normalfall: neue Version bauen und installieren

### 1. Bauen – normale PowerShell

Eine normale PowerShell öffnen, **nicht als Administrator**. Diesen Block vollständig einfügen:

```powershell
$ErrorActionPreference = "Stop"
Set-Location "C:\dev\openems\mini_ems_poc"

Get-Content "C:\Program Files\MiniEMS\VERSION"
$Version = Read-Host "Neue höhere Version eingeben (JJJJ.MM.n, zum Beispiel 2026.07.3)"

& ".\.venv\Scripts\python.exe" -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw "Tests fehlgeschlagen. Release wird nicht gebaut." }

& powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File ".\packaging\build_release.ps1" `
  -Version $Version `
  -Python ".\.venv\Scripts\python.exe"
if ($LASTEXITCODE -ne 0) { throw "Release-Build fehlgeschlagen." }

Get-Content ".\packaging\dist\mini_ems\VERSION"
```

Erwartung: Alle Tests enden mit `OK`, der Build endet mit `[build] done` und die ausgegebene Version ist
höher als die bisher installierte Version.

### 2. Installieren und starten – PowerShell als Administrator

Jetzt eine PowerShell mit **Als Administrator ausführen** öffnen. Diesen Block vollständig einfügen:

```powershell
$ErrorActionPreference = "Stop"
$Package = "C:\dev\openems\mini_ems_poc\packaging\dist\mini_ems"

& powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File "$Package\windows\update_release.ps1" `
  -PackagePath $Package
if ($LASTEXITCODE -ne 0) { throw "Update fehlgeschlagen. Siehe UPDATE_WARTUNG.md unter Rollback." }
```

Das Skript erledigt automatisch:

1. Paket prüfen.
2. Mini EMS stoppen.
3. Standortdaten und alte Anwendung sichern.
4. Neue Anwendung installieren.
5. Mini EMS starten.
6. Version und Health prüfen.

Fertig ist das Update erst bei:

```text
[update] UPDATE BESTANDEN
```

Nicht zusätzlich mit `Copy-Item` nach `C:\Program Files\MiniEMS` kopieren. Eine laufende Mini-EMS-Version hält
DLL-Dateien geöffnet; das Update-Skript stoppt sie kontrolliert.

### 3. Kurz prüfen

In derselben Administrator-PowerShell:

```powershell
Get-Content "C:\Program Files\MiniEMS\VERSION"
Invoke-RestMethod "http://127.0.0.1:8090/api/health"
Get-ScheduledTask -TaskName MiniEmsPoCRelease
```

Danach das Dashboard öffnen:

```text
https://192.168.244.10/dashboard
```

## Wenn das Update fehlschlägt

Keinen zweiten blinden Kopierversuch starten. In einer PowerShell als Administrator zurückrollen:

```powershell
$Package = "C:\dev\openems\mini_ems_poc\packaging\dist\mini_ems"

& powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File "$Package\windows\update_release.ps1" `
  -Rollback
```

Weitere Diagnose- und Wartungshinweise stehen in `UPDATE_WARTUNG.md`.

## Nur für eine komplett neue Erstinstallation

Zuerst das Release wie oben in Schritt 1 bauen. Danach eine PowerShell als Administrator öffnen:

```powershell
$ErrorActionPreference = "Stop"
$Project = "C:\dev\openems\mini_ems_poc"
$Package = "$Project\packaging\dist\mini_ems"

if (-not (Test-Path "$Package\mini_ems.exe")) {
    throw "Release-Paket fehlt. Zuerst Schritt 1 ausführen."
}
if (Test-Path "C:\Program Files\MiniEMS\mini_ems.exe") {
    throw "Mini EMS ist bereits installiert. Den normalen Update-Ablauf verwenden."
}

New-Item -ItemType Directory -Force "C:\Program Files\MiniEMS" | Out-Null
New-Item -ItemType Directory -Force "C:\ProgramData\MiniEMS" | Out-Null
Copy-Item "$Package\*" "C:\Program Files\MiniEMS" -Recurse -Force

& powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File "$Project\windows\install_task.ps1" `
  -Mode release `
  -TaskName MiniEmsPoCRelease `
  -AppDir "C:\Program Files\MiniEMS" `
  -SiteDir "C:\ProgramData\MiniEMS" `
  -StartNow:`$true
if ($LASTEXITCODE -ne 0) { throw "Erstinstallation fehlgeschlagen." }
```

Beim ersten Start erzeugt Mini EMS einen sicheren Einrichtungsstand in `site.sqlite`. Der einmalige Code für
das erste Admin-Konto wird in der Startkonsole ausgegeben. Danach den Standort im Dashboard unter
**Konfiguration → Standort einrichten** konfigurieren.

Eine vorhandene alte `C:\ProgramData\MiniEMS\config.json` wird beim ersten Start einmalig nach `site.sqlite`
migriert und anschließend nicht mehr als aktive Konfiguration verwendet.
