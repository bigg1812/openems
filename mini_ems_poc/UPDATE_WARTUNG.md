# Mini EMS – Update- und Wartungsprozess (H7)

Diese Datei erledigt **H7** aus `ROADMAP.md` (strategische To-do-Linie "Geschütztes Kundenhosting"):
einen dokumentierten Ablauf für Update, Healthcheck und Rollback auf der Kunden-IPC.

Grundsatz wie in `HOSTING_SICHERHEIT.md` und `EDGE_INTEGRATION_CONTRACT.md`: **Der Code ist die
Wahrheit.** Pfade, Felder und Endpunkte hier sind aus `config.json`, `mini_ems_runtime/state_store.py`,
`mini_ems_runtime/cycle.py`, `mini_ems_runtime/http_api.py`, `run_mini_ems_release.cmd`,
`windows/install_task.ps1`, `windows/update_release.ps1` und `windows/smoketest_release.ps1` abgeleitet.
Weicht diese Datei vom Code ab, gilt der Code.

**H2-Entscheidung getroffen:** `H2. Mini EMS als Release-Paket statt Git-Checkout ausliefern`
ist entschieden. Die Festlegung des Nutzers lautet wörtlich: *"Release-Paket, initial PyInstaller, später
Nuitka-kompatibel"*. Das konkrete Paketformat ist damit ein **One-Dir-Release** (ausführbares Artefakt
`mini_ems`/`mini_ems.exe` + `run_mini_ems_release.cmd`, `dashboard/`, `mini_ems_runtime/templates/`,
optional `sim/`, `VERSION`, `SHA256SUMS`, `RELEASE_HINWEISE.md`), gebaut über `packaging/build_release.ps1` (Windows/IPC) bzw.
`packaging/build_release.sh` (lokale Verifikation). Details: `packaging/README.md`. Der Prozess bleibt im
Kern gleich; die zuvor als **[H2-abhängig]** markierten Stellen sind unten jetzt konkret auf dieses
Paketformat aufgelöst. Die Trennung App-Dateien vs. Standortdaten (Abschnitt 1) ändert sich dadurch nicht:
`config.json` und Betriebsdaten sind niemals Teil des Pakets.

---

## Standardweg: Update per Skript (empfohlen)

Der reguläre Update- und Rollback-Ablauf läuft über zwei PowerShell-Skripte im
Ordner `windows/`. Die nummerierten Abschnitte 2 und 3 unten bleiben als
**Fallback- und Referenzbeschreibung** erhalten: Sie beschreiben genau die
Schritte, die die Skripte automatisieren, und dienen als manueller Weg, falls
ein Skript nicht nutzbar ist.

- **`windows/update_release.ps1`** – ein Update fahren:

  ```powershell
  .\windows\update_release.ps1 -PackagePath <Ordner-des-neuen-Release-Pakets>
  # Defaults: -AppDir "C:\Program Files\MiniEMS", -SiteDir "C:\ProgramData\MiniEMS",
  #           -TaskName "MiniEmsPoCRelease"
  ```

  Ablauf: `SHA256SUMS` des Pakets prüfen → Task stoppen und Prozess-Ende
  verifizieren → bisherigen App-Ordner nach `<AppDir>_vorher_<version>`
  umbenennen (Rollback-Kandidat) → neues Paket nach `AppDir` kopieren → Task
  starten → Smoketest. Standortdaten in `SiteDir` (`config.json`, `data\`, `logs\`, `runtime\`,
  `config_audit.jsonl`, `mapping_drafts\`, `config.json.*.bak`) werden **nie** angefasst. Für einen Trockenlauf `-WhatIf`
  anhängen.

- **Rollback** bei fehlgeschlagenem Smoketest:

  ```powershell
  .\windows\update_release.ps1 -Rollback
  ```

  Schiebt den jüngsten `<AppDir>_vorher_*`-Ordner zurück und startet den Task
  wieder.

- **`windows/smoketest_release.ps1`** – Smoketest solo (wird vom Update-Skript
  automatisch aufgerufen):

  ```powershell
  .\windows\smoketest_release.ps1 -ExpectedVersion 2026.07.1
  ```

  Prüft frische `runtime\health.json` (`last_cycle_at` neu, `runtime_status`
  `live`, `status` `healthy`), `/api/status` inkl. erwarteter `app_version` und
  `api_read_only` wie in `config.json` konfiguriert, sowie das Log auf neue
  `ERROR`-Zeilen. Exit-Code `0` = bestanden, `1` = nicht bestanden.

Der Grundsatz "Kein zweiter Blindversuch" (Abschnitt 1) gilt auch hier: Nach
einem fehlgeschlagenen Smoketest folgen Rollback und Ursachenklärung, keine
sofortige zweite Installation.

**Hinweis (Stand 2026-07-09):** Beide Skripte sind auf dem Laptop entwickelt und
sorgfältig reviewt, aber noch nicht auf der realen IPC gelaufen (auf dem
Build-Laptop ist kein PowerShell verfügbar). Beim ersten IPC-Einsatz zuerst mit
`-WhatIf` prüfen, dann scharf fahren.

---

## 1. Grundsätze

1. **Updates laufen ausschließlich über versionierte Release-Pakete mit Prüfsumme.** Es gibt keine
   manuellen Codeänderungen auf der Kunden-IPC – kein Editieren einzelner `.py`-Dateien, kein
   `git pull` auf der Produktivmaschine, kein Ad-hoc-Patch "nur für jetzt". Jede Änderung am Standort
   kommt über ein neues, vollständiges Release-Paket (siehe Abschnitt 5).
2. **Standortkonfiguration und Betriebsdaten werden bei einem Update NIE überschrieben.** Das ist die
   explizite Risiko-Leitplanke aus H7 (`ROADMAP.md`: *"Standortkonfiguration und Betriebsdaten dürfen bei
   Updates nicht überschrieben werden"*). Konkret bleiben bei jedem Update unverändert bzw. werden vor
   dem Update gesichert, nie aus dem Paket überschrieben:
   - `config.json` (Standortkonfiguration: Netzwerk, Punkte, Regler, Safety-Flags, `api.host`)
   - `data/runtime/mini_ems.sqlite` (Betriebsdaten-Historie)
   - `logs/mini_ems.log`, `logs/mini_ems_stdout.log` (Logs)
   - `runtime/state.json`, `runtime/health.json` (Laufzeit-/Health-Zustand)
   - `config_audit.jsonl`, `mapping_drafts/`, `config.json.*.bak` (H8-Verlauf, freigegebene Mapping-Entwürfe
     und automatische Konfigurationssicherungen)
   - `data/spotmarket/spotmarket_manual_override.json` (aktive manuelle Override-Einstellung, falls
     genutzt)
   Ein Update ersetzt **nur** die Anwendungsdateien (Code, Dashboard-Assets, Startskripte, mitgelieferte
   Beispieldateien), nie die oben genannten standortspezifischen Dateien.
3. **App-Dateien vs. Standortdaten – klare Trennung.** Jedes Release-Paket-Format muss diese Trennung
   einhalten, unabhängig davon, wie es technisch gebaut ist:
   - **App-Dateien** (kommen aus dem Release-Paket, werden bei jedem Update ersetzt): Anwendungscode
     bzw. ausführbares Artefakt, `dashboard/` (Assets), `run_mini_ems_release.cmd`,
     mitgelieferte Beispiel-/Vorlagedateien wie `sim/` (nur für lokale Simulation relevant, nicht
     IPC-Betriebsdaten). `windows/install_task.ps1` bleibt das Repository-Werkzeug zum Registrieren des Tasks,
     ist aber kein laufend zu editierender Standortdatenbestandteil.
   - **Standortdaten** (bleiben unangetastet, werden vor dem Update gesichert): `config.json`,
     `data/runtime/`, `data/spotmarket/spotmarket_manual_override.json` (falls aktiv gesetzt),
     `logs/`, `runtime/`, `config_audit.jsonl`, `mapping_drafts/`, `config.json.*.bak`.
4. **Kein zweiter Blindversuch.** Schlägt ein Update fehl oder besteht der Healthcheck nicht, folgt
   Rollback (Abschnitt 3) statt eines zweiten Installationsversuchs ohne Ursachenklärung.
5. **Keine Sicherheitsversprechen über das hinaus, was auf kundeneigener Hardware haltbar ist.** Wie in
   `HOSTING_SICHERHEIT.md` Teil 1 festgehalten: Ein Release-Paket senkt beiläufige Einsicht/Änderung durch
   normale Nutzer, ist aber kein Schutz gegen einen Administrator mit lokalem Zugriff auf die IPC. Dieser
   Update-Prozess schützt vor unkontrollierten manuellen Änderungen und vor dem Überschreiben von
   Standortdaten – nicht vor jemandem mit Admin-Rechten, der bewusst etwas anderes tut.

---

## 2. Standard-Update-Ablauf

*Fallback-/Referenzweg. Der empfohlene Weg ist das Skript
`windows/update_release.ps1` (siehe "Standardweg" oben); diese Checkliste
beschreibt die Schritte, die das Skript automatisiert, und den manuellen Ablauf,
falls das Skript nicht nutzbar ist.*

Nummerierte Checkliste für ein reguläres Update auf der Kunden-IPC. Schritte, die schon heute mit dem
bestehenden Code (`run_mini_ems.cmd`, `windows/install_task.ps1`, `config.json`) ausführbar sind, sind
mit konkreten Kommandos/Prüfpunkten hinterlegt. Die früher als **[H2-abhängig]** markierten Schritte sind
jetzt auf das entschiedene Paketformat (One-Dir-PyInstaller-Release, siehe `packaging/README.md`) konkret
aufgelöst. "Release-Paket ersetzen" bedeutet damit: den installierten Release-Ordner austauschen.

Durchführung remote via Secomea/VPN auf die IPC, wie in `HOSTING_SICHERHEIT.md` Teil 2 beschrieben
(siehe Verantwortlichkeiten, Abschnitt 6).

### 2.1 Vorbereitung

1. Release-Paket und Prüfsumme bereitstellen und **vor** dem Kopieren auf die IPC verifizieren
   (z. B. `CertUtil -hashfile mini_ems_release_<version>.zip SHA256` unter Windows) gegen die
   veröffentlichte Prüfsumme des Pakets. Kein Update mit abweichender Prüfsumme fortsetzen.
2. Laufende Version auf der IPC feststellen, bevor etwas verändert wird (siehe Abschnitt 5,
   "Version auf der IPC feststellen"). Notieren, damit im Rollback-Fall bekannt ist, wohin
   zurückgesetzt wird.
3. `health.json` vor dem Update einmal ansehen (Pfad: `runtime/health.json`, siehe
   `MINI_EMS_ANLEITUNG.md`, Abschnitt "Wichtige Laufzeitdateien") und den aktuellen `status` sowie
   `runtime_status` notieren. Das ist der Vergleichswert für den Healthcheck nach dem Update
   (Abschnitt 2.4).

### 2.2 Stoppen

4. Geplanten Task stoppen:
   ```powershell
   Stop-ScheduledTask -TaskName "MiniEmsPoCRelease"
   ```
5. Prozess-Ende verifizieren, bevor Dateien angefasst werden:
   ```powershell
   Get-ScheduledTask -TaskName "MiniEmsPoCRelease" | Get-ScheduledTaskInfo
   Get-Process mini_ems -ErrorAction SilentlyContinue
   ```
   Erwartung: `LastTaskResult` zeigt keinen laufenden Task mehr an, und es läuft kein
   `mini_ems.exe`-Prozess mehr. Falls doch, Prozess sauber beenden
   (nicht `taskkill /F` als ersten Reflex, sondern kurz abwarten – der Zykluscode reagiert nicht auf
   Kill-Signale, ein hängender Prozess deutet eher auf Task Scheduler-Wiederanlauf hin, siehe
   `run_mini_ems_release.cmd`-Restart-Schleife) und erneut prüfen.

### 2.3 Backup

6. Backup-Ordner mit Zeitstempel anlegen und die Standortdaten aus Abschnitt 1.2 sichern, **nicht**
   die App-Dateien (die liegen im alten Release-Paket und sind ohnehin vor dem Ersetzen vorhanden):
   ```powershell
   $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
   $backupDir = "C:\ProgramData\MiniEMS\backup\$stamp"
   New-Item -ItemType Directory -Path $backupDir -Force
   Copy-Item "config.json" "$backupDir\config.json"
   Copy-Item "data\runtime" "$backupDir\data_runtime" -Recurse
   Copy-Item "data\spotmarket\spotmarket_manual_override.json" "$backupDir\" -ErrorAction SilentlyContinue
   Copy-Item "runtime\state.json" "$backupDir\"
   Copy-Item "runtime\health.json" "$backupDir\"
   Copy-Item "logs\mini_ems.log" "$backupDir\" -ErrorAction SilentlyContinue
   Copy-Item "config_audit.jsonl" "$backupDir\" -ErrorAction SilentlyContinue
   Copy-Item "mapping_drafts" "$backupDir\mapping_drafts" -Recurse -ErrorAction SilentlyContinue
   Copy-Item "config.json.*.bak" "$backupDir\" -ErrorAction SilentlyContinue
   ```
   (Pfad `C:\ProgramData\MiniEMS\...` ist die vorgesehene Zielstruktur aus H3 – Konzept liegt jetzt vor in
   `HOSTING_SICHERHEIT.md` Teil 3, Anwendung auf der realen IPC steht noch aus. Solange das Ziel-Layout
   nicht auf der IPC angewendet ist, Backup-Ordner unterhalb des heutigen Projektordners ablegen, z. B.
   `<ProjectDir>\backup\<stamp>\`.)
7. Zusätzlich den kompletten bisherigen Release-Ordner als Rollback-Kandidat aufheben. Beim entschiedenen
   One-Dir-Format ist das der Ordner mit `mini_ems.exe`, `dashboard/`, `mini_ems_runtime/templates/`,
   `VERSION` und `SHA256SUMS`. Konkret: den bisherigen Installationsordner umbenennen (z. B. auf
   `MiniEMS_vorher`) **oder** das vorherige Release-Archiv aufbewahren, aus dem er installiert wurde. Die
   unter Punkt 6 gesicherten Standortdaten (`config.json`, `data/runtime/`, `runtime/`, `logs/`,
   `config_audit.jsonl`, `mapping_drafts/`, `config.json.*.bak`) sind hier
   nicht erneut zu kopieren; sie gehören nicht zum Release-Ordner.
8. Backup-Vollständigkeit stichprobenartig prüfen: Größe von `config.json` und der SQLite-Datei im
   Backup mit dem Original vergleichen (`Get-Item <pfad> | Select Length`).

### 2.4 Release-Ordner tauschen

9. Neuen Release-Ordner an die Installationsstelle entpacken/kopieren, ohne die unter Punkt 6 gesicherten
   Standortdaten-Dateien zu überschreiben. Beim entschiedenen One-Dir-Format heißt das konkret: den
   bisherigen Release-Ordner (aus Punkt 7 als `MiniEMS_vorher` beiseitegelegt) durch den neuen ersetzen.
   Der neue Ordner enthält `mini_ems.exe`, `run_mini_ems_release.cmd`, `_internal/`-Laufzeitdateien bei
   aktivierter `_internal`-Struktur bzw. die flach danebenliegenden Laufzeitdateien, `dashboard/`,
   `mini_ems_runtime/templates/`, optional `sim/`, `VERSION`, `SHA256SUMS` und `RELEASE_HINWEISE.md`.
   Die Zielaussage bleibt: Code/Assets/Vorlagen werden ersetzt; `config.json`, `data/runtime/`, `runtime/`,
   `logs/`, `config_audit.jsonl`, `mapping_drafts/` und `config.json.*.bak` liegen außerhalb des Release-Ordners
   und bleiben unverändert. Der Start erfolgt über den
   geplanten Windows-Task (`windows/install_task.ps1 -Mode release`) mit externem `--config <pfad>\config.json`.
10. Nach dem Ersetzen erneut Prüfsumme kontrollieren: Die mitgelieferte `SHA256SUMS` gegen die tatsächlichen
    Dateien im installierten Ordner prüfen (nicht nur vor dem Kopieren, auch am Zielort, um
    Übertragungsfehler auszuschließen). Unter Windows z. B. je Datei
    `Get-FileHash <datei> -Algorithm SHA256` bzw. den Hash gegen die passende Zeile in `SHA256SUMS`
    vergleichen.
11. Versionsdatei `VERSION` im installierten Ordner gegen die erwartete Zielversion prüfen
    (`Get-Content .\VERSION`, siehe Abschnitt 5).
12. `config.json` unverändert lassen. Falls das neue Release neue, optionale Konfigurationsfelder
    einführt, werden diese in einem separaten, dokumentierten Schritt manuell ergänzt (nicht durch
    Überschreiben der Datei) – das bleibt Admin-Arbeit lokal auf der IPC (siehe
    `HOSTING_SICHERHEIT.md`, Sichtbarkeits-/Änderungsmatrix).

### 2.5 Starten

13. Geplanten Task wieder starten:
    ```powershell
    Start-ScheduledTask -TaskName "MiniEmsPoCRelease"
    ```
14. Kurz warten (mindestens ein Zyklus, siehe `timing.cycle_seconds` in `config.json`, aktuell `60`
    Sekunden) und danach `Get-ScheduledTaskInfo -TaskName "MiniEmsPoCRelease"` prüfen: `LastTaskResult` soll
    `0` sein bzw. der Task soll im Zustand "Running" stehen.

### 2.6 Healthcheck

15. `runtime/health.json` öffnen und konkret prüfen:
    - `status` ist `healthy` (nicht `degraded`, nicht `safe_mode`).
    - `runtime_status` ist `live` (nicht `stale_runtime`) – das Watchdog-Feld aus
      `mini_ems_runtime/cycle.py` (`_watchdog_liveness`).
    - `last_cycle_at` bzw. `watchdog.last_cycle_at` liegt nach dem Neustart-Zeitpunkt und ist nicht
      älter als ein bis zwei Zykluslängen.
    - `write_status` zeigt für die konfigurierten Outputs (`current_price`, `grid_lockout`,
      `spotmarket_lockout`) keine neuen `last_error`-Einträge seit dem Update.
16. `/api/status` von einem Rechner mit Netzzugriff (Kundennetz/VPN/Secomea, siehe
    `HOSTING_SICHERHEIT.md` Teil 2) erreichen und prüfen, dass die Antwort aktuelle Daten liefert
    (nicht nur HTTP 200, sondern `health`-Feld mit frischem `timestamp`):
    ```text
    GET http://192.168.244.10:8090/api/status
    ```
    Ist die H4-Stufe aktiv (Reverse Proxy, siehe unten und `HOSTING_SICHERHEIT.md` Teil 4) – wie
    aktuell auf der Pilot-IPC – bindet die API nur noch lokal auf `127.0.0.1:8090`; der äquivalente
    Aufruf läuft dann über den Proxy: `GET https://192.168.244.10/api/status`, während
    `http://192.168.244.10:8090/api/status` nicht mehr erreichbar sein darf.
17. Dashboard (`/dashboard`) im Browser öffnen und stichprobenartig prüfen, dass aktuelle Werte
    (Netzleistung, Außentemperatur, Preis) angezeigt werden und keine dauerhaften Stale-/Bad-Badges
    zu sehen sind.
18. `logs/mini_ems.log` auf Fehler seit dem Neustart durchsuchen:
    ```powershell
    Select-String -Path "logs\mini_ems.log" -Pattern "ERROR","Traceback" | Select-Object -Last 20
    ```
    Erwartung: keine neuen `ERROR`/`Traceback`-Einträge nach dem Start-Zeitstempel aus Schritt 13.
19. Mindestens einen vollständigen Zyklus lang beobachten (Faustregel: 3–5 Zyklen, siehe
    `timing.cycle_seconds`), bevor das Update als abgeschlossen gilt.
20. Ergebnis (bestanden/nicht bestanden) und Zeitpunkt als Teil des H8-Betriebsnachweises im
    Betriebslog/Zugriffskonzept festhalten.

Besteht der Healthcheck alle Punkte 15–19 → Update abgeschlossen, Backup-Ordner aus Schritt 6/7 gemäß
Aufbewahrungsregel (siehe Abschnitt 4) behalten. Besteht er nicht → Rollback (Abschnitt 3).

---

## 3. Rollback-Ablauf

*Fallback-/Referenzweg. Der empfohlene Weg ist `windows/update_release.ps1
-Rollback` (siehe "Standardweg" oben).*

### 3.1 Wann zurückrollen

Rollback auslösen, wenn nach dem Update **mindestens einer** dieser Healthcheck-Befunde auftritt:

- `health.json`-`status` bleibt nach mehreren Zyklen `degraded` oder `safe_mode`, ohne dass eine
  bekannte externe Ursache vorliegt (z. B. echter Controller-Ausfall, der auch vor dem Update bestand).
- `runtime_status` zeigt `stale_runtime` – der Prozess läuft nicht erkennbar weiter, obwohl der Task
  gestartet wurde.
- Der geplante Task startet nicht oder bricht wiederholt ab (`LastTaskResult` ungleich `0` über mehrere
  Wiederanlaufversuche der `run_mini_ems.cmd`-Restart-Schleife hinweg).
- `/api/status` ist über den freigegebenen Netzzugriff nicht erreichbar oder liefert dauerhaft
  Fehler/Timeout.
- `logs/mini_ems.log` zeigt neue, wiederkehrende `ERROR`/`Traceback`-Einträge nach dem Neustart, die vor
  dem Update nicht auftraten.
- Prüfsumme des installierten Release-Pakets stimmt nicht mit der veröffentlichten überein (Abschnitt
  2.4, Schritt 10) – in diesem Fall sofort zurückrollen, ohne überhaupt zu starten.

### 3.2 Wie zurückrollen

1. Task stoppen (wie Abschnitt 2.2).
2. Prozess-Ende erneut verifizieren.
3. Neuen Release-Ordner entfernen und den unter Abschnitt 2.3 Schritt 7 aufgehobenen vorherigen Stand
   wiederherstellen. Beim entschiedenen One-Dir-Format konkret: den fehlgeschlagenen Release-Ordner löschen
   und den beiseitegelegten `MiniEMS_vorher`-Ordner (oder das vorherige Release-Archiv) wieder an die
   Installationsstelle bringen.
4. Standortdaten aus dem in Abschnitt 2.3 Schritt 6 angelegten Backup zurückspielen: `config.json`,
   `data/runtime/`, `runtime/state.json`, `runtime/health.json`, `config_audit.jsonl`, `mapping_drafts/`,
   `config.json.*.bak`,
   `data/spotmarket/spotmarket_manual_override.json` (falls gesichert). Nur zurückspielen, falls das
   fehlgeschlagene Update diese Dateien tatsächlich verändert hat – im Normalfall (Grundsatz 2) hat es
   das nicht, dann bleibt dieser Schritt eine Kontrolle statt einer Wiederherstellung.
5. Task wieder starten (wie Abschnitt 2.5).
6. Healthcheck erneut durchführen (Abschnitt 2.6, Schritte 15–19) gegen den vorherigen, bekannten guten
   Stand.

### 3.3 Was danach

7. **Meldung:** Rollback-Vorfall mit Zeitpunkt, betroffener Zielversion, beobachtetem Healthcheck-Befund
   und Rollback-Ergebnis als Teil des H8-Betriebsnachweises im Betriebslog/Zugriffskonzept festhalten.
8. **Ursachenanalyse:** Vor jedem erneuten Update-Versuch klären, woran das fehlgeschlagene Update lag
   (Paketfehler, Prüfsumme, Konfigurationslücke, Umgebungsunterschied Test- vs. Kunden-IPC). Das gehört
   in die Vorbereitung des nächsten Versuchs, nicht in eine sofortige zweite Installation.
9. **Kein zweiter Blindversuch:** Ohne geklärte Ursache wird nicht erneut derselbe Release-Stand
   installiert. Ein zweiter Versuch erfolgt erst mit einem korrigierten Paket oder einer geklärten
   Vorbedingung.

---

## 4. Wartungsroutine

Kleine, wiederkehrende Checkliste unabhängig von konkreten Updates (z. B. monatlich, oder wenn
Secomea-Fernzugriff ohnehin stattfindet):

- **Log-Größe:** Größe von `logs/mini_ems.log` und `logs/mini_ems_stdout.log` prüfen
  (`Get-Item logs\mini_ems.log | Select Length`). Bei ungewöhnlichem Wachstum Logdatei sichern und
  leeren bzw. rotieren (aktuell keine automatische Rotation im Code vorgesehen).
- **SQLite-Größe:** Größe von `data/runtime/mini_ems.sqlite` prüfen. Starkes Wachstum kann auf sehr
  viele Rohwerte/Rollups hindeuten (siehe `MINI_EMS_ANLEITUNG.md`, Abschnitt "Datenbank") – das ist
  heute erwartetes Verhalten, aber die absolute Größe im Blick behalten, bevor Speicherplatz auf der
  IPC knapp wird.
- **Backup-Alter:** Prüfen, dass der jüngste Backup-Ordner aus Abschnitt 2.3 nicht älter als das letzte
  durchgeführte Update ist. Alte Backups nach einer angemessenen Aufbewahrungszeit (z. B. die letzten
  2–3 Stände) löschen, damit Backups nicht unbegrenzt Platz belegen; den jeweils letzten guten Stand
  aber immer behalten.
- **Anstehende Windows-Updates der IPC:** Prüfen, ob Windows-Updates für die IPC anstehen bzw.
  geplant sind, und ob ein Neustart der IPC bevorsteht. Ein Windows-Neustart startet den geplanten Task
  automatisch neu (`New-ScheduledTaskTrigger -AtStartup` in `windows/install_task.ps1`); nach einem
  IPC-Neustart trotzdem einen Healthcheck (Abschnitt 2.6) durchführen.
- **Secomea-Erreichbarkeit:** Regelmäßig prüfen, dass der Secomea-/VPN-Fernzugriff tatsächlich
  funktioniert (nicht erst, wenn ein Update ansteht) – siehe `HOSTING_SICHERHEIT.md`, Teil 2, Abschnitt
  2.5, Schritt 4. Ohne H4-Proxy ist das der direkte Zugriff auf `192.168.244.10:8090`; ist H4 aktiv (wie
  aktuell auf der Pilot-IPC), prüfen statt dessen `https://192.168.244.10`, siehe die nächste Zeile.
- **Reverse Proxy (falls eingerichtet, H4):** Ist die optionale H4-Stufe aktiv (Reverse Proxy vor der
  intern gebundenen API, siehe `HOSTING_SICHERHEIT.md`, Teil 4 und `proxy/README.md`), muss der Proxy für
  ein Mini-EMS-Update **nicht** gestoppt werden. Er ist ein eigener Dienst; während Mini EMS in
  Abschnitt 2.2/2.5 stoppt und wieder startet, liefert der Proxy kurz `502` und erholt sich automatisch,
  sobald `127.0.0.1:8090` wieder antwortet. Neu geladen (`caddy reload`) werden muss der Proxy nur, wenn
  sich die `Caddyfile` oder die `caddy.exe` selbst ändert – nicht bei einem reinen Mini-EMS-Update.

---

## 5. Versionierung

- **Schema:** Jeder Release-Ordner enthält eine Datei `VERSION` direkt im Installationsordner (neben
  `mini_ems.exe`). Format (vom Build-Skript erzeugt, `packaging/build_release.ps1` bzw. `.sh`): eine
  einfache `key=value`-Liste mit
  - `version=` – Semver-artige Kennung, z. B. `2026.07.0`,
  - `build_date=` – UTC-Zeitstempel des Builds (`YYYY-MM-DDTHH:MM:SSZ`),
  - `git_commit=` – Git-Commit-Hash des Quellstands (mit `+dirty`, falls aus einem unsauberen Arbeitsbaum
    gebaut),
  - `platform=` – Zielplattform (z. B. `Windows-AMD64`).

  Beispiel:

  ```text
  version=2026.07.0
  build_date=2026-07-05T08:21:49Z
  git_commit=3de16bd4eedf
  platform=Windows-AMD64
  ```

  Zusätzlich liegt `SHA256SUMS` (Prüfsummen über alle Paketdateien) im selben Ordner. Damit ist die
  Anforderung erfüllt: **eine lesbare, versionierte Kennung liegt am Installationsort.**
- **Version zur Laufzeit sichtbar:** Die Runtime liest die `VERSION`-Datei beim Start und stellt sie
  additiv unter `/api/status` als `app_version` (`version`, `git_commit`, `build_date`) bereit; die
  Systemstatus-Seite des Dashboards zeigt sie als dezente Zeile "Softwareversion". Der Smoketest nutzt
  dieses Feld, um nach dem Update die erwartete Version zu bestätigen. Im Git-Betrieb ohne `VERSION`
  erscheint `dev`.
- **Changelog im Paket:** Neben `VERSION` liegt eine `CHANGELOG.md` als Schnappschuss des
  `[Unreleased]`-Standes unter der gewählten Versionsüberschrift (erzeugt vom Build, siehe
  `packaging/README.md`, Abschnitt "Release erstellen").
- **Laufende Version auf der IPC feststellen:** `VERSION` im Installationsordner öffnen:

  ```powershell
  Get-Content .\VERSION
  ```

  Die Zeilen `version=` und `git_commit=` sind die maßgebliche Kennung; ein Rückgriff auf
  Ordnerzeitstempel oder Git-Stand ist nicht mehr nötig.
- **Jede Änderung am Standort kommt über einen neuen Release-Ordner.** Es gibt keinen Zwischenzustand
  "halb aktualisiert" oder "einzelne Datei von Hand ersetzt". Ein neuer Release-Ordner erhöht die
  Versionsnummer und wird komplett über den Ablauf in Abschnitt 2 eingespielt, auch wenn nur eine
  einzelne Datei fachlich betroffen ist.

---

## 6. Verantwortlichkeiten

Konsistent zur Sichtbarkeits- und Änderungsmatrix in `HOSTING_SICHERHEIT.md`, Teil 1, Abschnitt 1.2:

- **Wir (Admin-Rolle, interner Betrieb) führen Updates remote über Secomea/VPN durch.** Ersetzen des
  Release-Pakets, Bearbeiten von `config.json`, direkter Zugriff auf `data/runtime/`, `runtime/`, `logs/`,
  `config_audit.jsonl` und `mapping_drafts/` bleibt Admin-Arbeit – genau die Ressourcen, die laut Sichtbarkeitsmatrix nur der Admin lesen
  und ändern darf. Das ist der Standardweg für den Update-Ablauf in Abschnitt 2.
- **Der Kunde/Betreiber vor Ort führt keine eigenständigen Updates durch.** Operator und Viewer haben
  laut Sichtbarkeitsmatrix keinen Lese- oder Änderungszugriff auf Standortkonfiguration, Runtime-Dateien
  oder Logs; ein Update-Vorgang, der diese Dateien anfasst, gehört damit nicht in ihre Rolle.
- **Vor-Ort-Handlungen, die der Kunde übernehmen kann**, falls Secomea/VPN ausfällt oder ein Vor-Ort-
  Eingriff nötig ist: rein mechanische Schritte nach genauer Anweisung (z. B. Task in der
  Aufgabenplanung neu starten, IPC neu starten), **nicht** das Ersetzen von Paketdateien oder das
  Bearbeiten von `config.json`. Ein vollständiges Update mit Backup/Rollback bleibt Admin-Aufgabe.
- Diese Aufteilung ist keine reine Präferenz, sondern folgt derselben Risikoabgrenzung wie in
  `HOSTING_SICHERHEIT.md` Teil 1.3: Schreibfreigaben, Konfiguration und Safety-relevante Änderungen
  bleiben lokal/administrativ, nie über einen breiteren Zugriffspfad.

---

## Querverweise

- `ROADMAP.md` – strategische To-do-Linie "Geschütztes Kundenhosting" (H1–H9), insbesondere H2
  (Release-Paketform, entschieden: PyInstaller-One-Dir), H3 (Installationspfad/Dateirechte) und H7
  (diese Datei)
- `packaging/README.md` – Build-Tooling, Release-Layout, Version-/Prüfsummen-Erzeugung, "Später Nuitka"
- `HOSTING_SICHERHEIT.md` – Sichtbarkeits-/Änderungsmatrix (Teil 1), Netzwerkgrenzen, Secomea/VPN-Zugriff
  (Teil 2), Installationslayout und Windows-Dateirechte (Teil 3, H3), API-Bindung und Reverse Proxy
  (Teil 4, H4) – Grundlage für die Backup-Zielpfade in Abschnitt 2.3 dieser Datei
- `proxy/README.md`, `proxy/Caddyfile`, `proxy/firewall_rules.ps1` – optionaler Reverse Proxy (H4); für ein
  Mini-EMS-Update nicht zu stoppen (siehe Wartungsroutine, Abschnitt 4)
- `EDGE_INTEGRATION_CONTRACT.md` – Lese-/Schreibrechte, Safety-Flags, Ausfallverhalten
- `MINI_EMS_ANLEITUNG.md` – Betrieb, Pfade IPC vs. lokal, `health.json`-Felder, Windows-Task
- `windows/update_release.ps1`, `windows/smoketest_release.ps1` – Skript-Umsetzung des Standard-Update-,
  Rollback- und Smoketest-Ablaufs (Standardweg, siehe oben)
- `CHANGELOG.md` – Änderungen pro Release; der Build legt einen versionierten Schnappschuss ins Paket
- `windows/install_task.ps1`, `run_mini_ems_release.cmd` – Produktions-Startpfad; `run_mini_ems.cmd`
  bleibt Checkout-/Fallback-Pfad (nur lesend referenziert, hier nicht verändert)
- `config.json` – Quelle der Pfade für Backup/Healthcheck (Datenbank, Logging, API)
