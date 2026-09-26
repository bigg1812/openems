# Mini EMS – Update, Rollback und Wartung

Der normale Ablauf zum **Bauen und Installieren** eines neuen Releases steht kurz und vollständig in
`RELEASE_WORKFLOW.md`. Diese Datei ergänzt die fachliche Abnahme, Fehlerbehebung und Wartung einschließlich alter Sicherungen.

## Quellcode, GitHub und installierte Version unterscheiden

Der normale Weg lautet: lokale Änderungen → Commit → Push nach GitHub → geprüfter Windows-Build aus
diesem Commit → Paketinstallation → Vergleich von `VERSION`, Commit und laufender Health-Antwort.
`git pull` aktualisiert nur einen Checkout. Der produktive Release-Task startet die kopierte `mini_ems.exe`
in `C:\Program Files\MiniEMS`; diese Datei wird durch einen Pull nicht ersetzt.

Für eine Freigabe muss der Build auf einem sauberen, bekannten Commit beruhen. `+dirty` kennzeichnet einen
Prüfstand mit lokalen oder unversionierten Änderungen; derselbe Basis-Commit beweist dann keine gleichen
Programmdateien. Paketdateien werden zusätzlich anhand von `SHA256SUMS` geprüft. Laptop und IPC dürfen
absichtlich verschiedene Stände haben, bis ein neuer Stand abgenommen ist. Ihre Standortdaten werden nie
per Git synchronisiert: lokale Simulation und reale Anlage behalten getrennte Datenbanken.

## Nächste gemeinsame Abnahme nach der Stabilisierungsrunde

Die lokalen Nachweise stehen in [Validierung 22.09.2026](docs/VALIDIERUNG_2026-09-22.md), der Aufgabenstatus
in [ROADMAP.md](ROADMAP.md). Der nächste Schritt ist die Windows-/VPN-Prüfung:

1. Windows-/Linux-CI bestätigen und ein Windows-Paket aus dem geprüften Commit bauen. Zuerst
   `packaging/verify_release.py` mit temporären Simulationen ausführen. Danach Task/SYSTEM, Update/Rollback,
   Preiszeitmodell und Berichtdruck mit eigenen Testordnern, Tasknamen und Loopback-Port prüfen.
2. Über freigegebenen VPN-Zugang zuerst nur den bestehenden IPC-Stand aufnehmen: installierte `VERSION`,
   App-Commit, Task/Prozesse, SiteDir, Standortrevision und Zugriffsweg. Backup/Restore vorbereiten;
   `identity.sqlite` und offene Rückgaben gehören zum Standortnachweis.
3. Offene/historische Test-Leases vor Update und Moduswechsel feststellen. Alte `failed`-Leases ohne
   Zielpriorität vor Ort klären. Beobachtungsmodus gibt bestehende Prioritäten nicht automatisch zurück.
4. Nach freigegebenem Update Version/Commit, frische Health und Supervisor-Nachweis, Rollen, Caddy/HTTPS,
   gesperrte Anlagenaktionen und erhaltene Standortrevision prüfen. Im Beobachtungsmodus beginnen.
5. Wenige vorab vereinbarte Lesepunkte über ein begrenztes Zeitfenster beobachten (R8c). Punktliste,
   Leseintervalle, Datenalter, Speicherbudget und verantwortliche Person festhalten. Ausfälle nur in Simulation
   erzeugen; am Standort Datenlücken, Wiederanlauf und Bedienbarkeit auswerten.
6. Erst für späteren Steuerungsbetrieb: DDC-Heartbeat/Fallback, IPC-/Kommunikationsverlust und
   Ersatzbetrieb mit Betreiber/MSR fachlich klären (R6). Aktiven Test auf ungefährlichem Punkt separat
   freigeben: Wert, ACK, Readback, Prioritätskonflikt und bestätigte Rückgabe (R3c).

Ein Paket-Smoketest ersetzt diese fachliche Abnahme nicht. Testergebnisse stets mit Datum, Paket-Commit,
Standort und Nachweisart festhalten. Aus der lokalen Entwicklungsumgebung erfolgen keine realen Writes.

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
4. installiert das neue Paket und aktualisiert den Release-Task mit begrenzten Wiederholungen,
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

Erwartet werden die passende Release-Version, `status: healthy`, `storage_status: ok`, im überwachten
Betrieb `supervision_status: ok`, `api_read_only: true` und die erhaltene Standortrevision. HTTP `200` allein
beweist nur die erreichbare API. Offene Rückgaben und Speicherfehler dürfen nicht als gesund gelten.

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

## Aufbewahrung im begrenzten Pilot

Runtime- und Supervisor-Log rotieren bei je 5 MiB mit drei Sicherungen. Das Launcher-Stdout-Log enthält
Start-/Fehlermeldungen und den Erstzugang, aber im überwachten Betrieb keine doppelten Zykluslogs;
es wird nicht automatisch rotiert und gehört zur Wartung.

Die Historie wird noch nicht automatisch gelöscht. Der lokale Lasttest mit zehn Punkten im 30-Sekunden-Takt
benötigte für sieben simulierte Tage rund 137 MiB; das ist eine Größenordnung für genau dieses Testprofil,
keine allgemeine Kapazitätszusage. Vor dem Beobachtungslauf freien Speicher prüfen, Laufzeit begrenzen und
Größe regelmäßig kontrollieren. Für unbeaufsichtigten Dauerbetrieb sind ein extern erreichbarer Alarmweg,
Speicherbudget und eine vereinbarte Aufbewahrungs-/Löschregel noch erforderlich.

Für ein vollständiges dateibasiertes Standortbackup Runtime und Supervisor stoppen und ihr Ende prüfen;
dann den gesamten SiteDir kopieren. Einzelne aktive SQLite-Dateien nicht blind kopieren. Bei
Wiederherstellung eine getrennte Kopie verwenden und Integrität, Revision, Konten und Historie prüfen.
Automatische Löschjobs sind nicht Bestandteil dieses Kandidaten.

## Alte Sicherungen aufräumen

Das Update-Skript lässt Sicherungen bewusst liegen:

```text
C:\Program Files\MiniEMS_vorher_<Version>
C:\ProgramData\MiniEMS_backup_<Zeit>
```

Erst nach einigen stabilen Betriebstagen aufräumen. Mindestens den letzten funktionierenden App-Stand und
eine passende Standort-Sicherung behalten. `C:\ProgramData\MiniEMS` selbst niemals löschen.
