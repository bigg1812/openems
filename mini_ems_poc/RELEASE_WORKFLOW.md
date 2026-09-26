# Mini EMS – Release bauen und starten

Diese Anleitung ist der kurze Standardablauf für neue Mini-EMS-Releases auf dem Windows-IPC.

```text
C:\Program Files\MiniEMS\       installierte Anwendung; wird beim Update ersetzt
C:\ProgramData\MiniEMS\         Standortdaten; bleiben beim Update erhalten
```

`C:\ProgramData\MiniEMS` wird beim Release-Wechsel nicht überschrieben. Dort bleiben insbesondere
`site.sqlite`, `identity.sqlite`, Betriebsdaten und Logs erhalten.

## Einfacher Ablauf auf dem IPC

1. Das **Windows-Paket** aus dem erfolgreichen GitHub-Actions-Lauf herunterladen und das ZIP vollständig
   in einen eigenen Ordner entpacken. Auf dem IPC ist weder Git noch Python dafür nötig.
2. `MiniEMS-Paket.cmd` doppelt anklicken und **1 – Paket ohne Anlagenzugriff prüfen** wählen.
   Das prüft Prüfsummen und einen einmaligen Zyklus in einem temporären Simulationsstandort. Der
   installierte Task und `C:\ProgramData\MiniEMS` bleiben unberührt. Es ist noch kein Feldtest.
3. Wenn die Prüfung bestanden ist und der geplante Wartungszeitpunkt erreicht ist, dieselbe Datei erneut
   öffnen und **2 – Version auf diesem IPC installieren** wählen. Windows fragt nach Administratorrechten;
   eine abschließende Ja-Eingabe startet das Update. Das Programm sichert Standortdaten und Vorversion,
   installiert das Paket und prüft danach Version und Gesundheit. Erfolg steht ausdrücklich als
   `UPDATE BESTANDEN` im Fenster.

Bei einem fehlgeschlagenen Update keine Dateien von Hand kopieren. Im selben Menü stellt **3 – Vorherige
Version wiederherstellen** die alte Anwendungsversion zurück. Der Standort-Sicherungsstand wird dabei
bewusst nicht automatisch zurückgespielt. Den Fehlerbefund vor weiteren Versuchen sichern.

Der Menütest vor der Installation zeigt nur, dass das Paket in Simulation startet. Die Prüfung des
Windows-Tasks unter SYSTEM, die Bedienung im Dashboard und die Anlagenabnahme erfolgen erst auf dem IPC.

## Manueller Wartungspfad: neue Version bauen und installieren

### 1. Bauen – normale PowerShell

Build-Profil, saubere Python-Umgebung und Build-Befehle stehen verbindlich in
[packaging/README.md](packaging/README.md). Aus dem Repository-Stamm die Tests ausführen:

```powershell
Set-Location "C:\dev\openems"
& ".\mini_ems_poc\.venv\Scripts\python.exe" -m unittest discover -s mini_ems_poc/tests -v
if ($LASTEXITCODE -ne 0) { throw "Tests fehlgeschlagen." }
node mini_ems_poc/tests/dashboard_logic_harness.mjs
if ($LASTEXITCODE -ne 0) { throw "Dashboard-Prüfungen fehlgeschlagen." }
```

Dann mit einer bewusst gewählten höheren Version bauen und `packaging/verify_release.py` ausführen,
wie im Paketbau beschrieben. Es startet ausschließlich temporäre Simulationen, einschließlich
Prozessabbruch und Restore. Erwartung: Tests `OK`, Paketprüfung `result: passed`, bekannter sauberer Commit.

**Kandidat 26.09.2026:** Das Windows-Paket wurde in GitHub Actions gebaut und mit temporärem
Simulationsstandort geprüft. Vor dem folgenden Produktivablauf Task/SYSTEM, Update/Rollback und Berichtdruck in getrennten
Simulationsordnern prüfen. Dafür eigene Tasknamen und einen freien Loopback-Port verwenden; den bestehenden
Produktivtask und `C:\ProgramData\MiniEMS` nicht für den Versuch verwenden. Danach gilt die
[gemeinsame Abnahme](UPDATE_WARTUNG.md#nächste-gemeinsame-abnahme-nach-der-stabilisierungsrunde).

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
4. Neue Anwendung installieren und begrenzte Task-Wiederholungen übernehmen.
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
