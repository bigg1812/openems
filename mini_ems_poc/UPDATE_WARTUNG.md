# Mini EMS – Update und Wartung

Diese Anleitung beschreibt den normalen Release-Wechsel auf der Windows-IPC. Der Ablauf ist bewusst kurz:
Das geprüfte Paket wird mit einem Skript installiert, automatisch getestet und kann mit einem Skript
zurückgerollt werden.

> **Realer Nachweis vom 12.07.2026:** Der Betreiber hat den Release-Wechsel auf der Pilot-IPC erfolgreich
> durchgeführt. Die neue Version lief fehlerfrei, die bestehende Konfiguration blieb erhalten, der
> Freigabecode funktionierte und es gab keine Fehlermeldungen. Dieser Nachweis beruht auf der ausdrücklichen
> Betreiberbestätigung; Konsolenausgaben wurden nicht ins Repository übernommen.

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

Die lokalen Nachweise stehen in [Validierung 13.09.2026](docs/VALIDIERUNG_2026-09-13.md), der Aufgabenstatus
in [ROADMAP.md](ROADMAP.md). Vor Produktivfreigabe:

1. Windows-/Linux-CI bestätigen und ein Windows-Paket aus dem geprüften Commit bauen. Zuerst in einem
   separaten Simulations-SiteDir auf Windows starten; Python-Laufzeit, Migration, Preiszeitmodell und Login prüfen.
2. Am IPC installierte `VERSION`, App-Commit, Task/Prozess, SiteDir und echten Zugriffsweg aufnehmen.
   Backup/Restore gemäß dieser Anleitung vorbereiten. `identity.sqlite` gehört zum Standortbackup.
3. Offene/historische Test-Leases vor dem Update feststellen. Alte `failed`-Leases ohne gespeicherte
   Zielpriorität vor Ort klären; diese neue Version gibt sie nicht anhand einer geratenen Priorität zurück.
4. Nach Update Version/Commit, frische Health, Rollen, Caddy/HTTPS, Schutzstatus und erhaltene Standortrevision prüfen.
5. Nur im vereinbarten Testfenster auf einem freigegebenen ungefährlichen Punkt testen: gewünschter Wert,
   Protokollbestätigung, Readback, höhere Priorität, Rückgabe und Kommunikationsfehler. Danach Rückgabe nachweisen.
6. DDC-Heartbeat, IPC-Ausfall, Kommunikationsverlust und Wiederanlauf mit Betreiber/MSR fachlich abnehmen (R6).
   Einen Ausfallversuch erst durchführen, wenn seine sichere Anlagenreaktion und Verantwortlichen feststehen.

Ein Paket-Smoketest ersetzt diese fachliche Abnahme nicht. Testergebnisse stets mit Datum, Paket-Commit,
Standort und Nachweisart festhalten. Aus der lokalen Entwicklungsumgebung erfolgen keine realen Writes.

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

Der automatische Smoketest prüft Start und technische Erreichbarkeit. Zusätzlich den echten Zugriffsweg
und die oben aufgeführten Abnahmekriterien prüfen:

```powershell
Get-ScheduledTask -TaskName MiniEmsPoCRelease
Invoke-RestMethod http://127.0.0.1:8090/api/health
Get-Item "C:\ProgramData\MiniEMS\site.sqlite"
```

Danach im Browser über Caddy öffnen:

```text
https://192.168.244.10/dashboard
```

Erwartet:

- Dashboard verlangt eine Anmeldung; nach Login lädt die Übersicht aktuelle Daten.
- `/api/health` meldet die neue `app_version.version`.
- `api_read_only` ist auf der produktiven IPC `true`.
- Beim ersten H6-Update legt der bisherige Freigabecode einmalig das erste Admin-Konto an; danach funktioniert
  die persönliche Anmeldung über denselben HTTPS-Link.
- Standortdaten, `identity.sqlite` und bisherige Revisionen bleiben bei späteren Updates erhalten.

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

## Admin-Zugang lokal wiederherstellen

Bei einem noch nicht eingerichteten Standort erzeugt der Befehl einen neuen einmaligen Freigabecode. Sobald
Konten existieren, setzt derselbe Befehl lokal ein temporäres Passwort für das erste aktive Admin-Konto und
beendet dessen bestehende Sitzungen:

```powershell
Stop-ScheduledTask -TaskName MiniEmsPoCRelease

& "C:\Program Files\MiniEMS\mini_ems.exe" `
  --site-dir "C:\ProgramData\MiniEMS" `
  --reset-admin-code

Start-ScheduledTask -TaskName MiniEmsPoCRelease
```

Code bzw. temporäres Passwort werden einmal in PowerShell ausgegeben. Nach der Anmeldung unter „Konten und
Rollen“ sofort ein eigenes Passwort setzen. Der Wert wird nicht über Dashboard, Log oder API offengelegt.

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
