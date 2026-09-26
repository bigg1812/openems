# Changelog

Alle nennenswerten Änderungen an Mini EMS PoC. Format angelehnt an
[Keep a Changelog](https://keepachangelog.com/de/1.1.0/); Versionsschema
`JJJJ.MM.n` (Jahr.Monat.laufende Nummer im Monat), passend zu den
`version=`-Kennungen der Release-Pakete (`packaging/build_release.*`, `VERSION`).

Pflege-Regel: Änderungen werden während der Arbeit unter `[Unreleased]`
gesammelt. Beim Release-Build wird der `[Unreleased]`-Stand als versionierter
**Schnappschuss** in die `CHANGELOG.md` **im Release-Paket** übernommen; diese
Repo-Datei wird vom Build nicht umgeschrieben, sondern bleibt manuelle Pflege
(siehe `packaging/README.md`, Abschnitt "Paket und Version").

## [Unreleased]

### Stabilisiert und vereinfacht – lokaler Prüfstand 22.09.2026

- Unabhängiger Prozesswächter (`--supervise`) erkennt Stillstand/Absturz anhand Run-ID und Zyklusfortschritt.
  Maximal drei Startversuche einschließlich Erststart in 15 Minuten; das Budget bleibt über Neustarts erhalten.
  OS-Dateisperren verhindern parallele Runtime-/Supervisor-Instanzen desselben Standorts.
- Speicherfehler erscheinen in Health/API und Oberfläche; ein fortschreitender gestörter Zyklus wird nicht
  blind neu gestartet. Zyklus-IDs bleiben auch bei verlorenem Zustand über Neustarts eindeutig.
- Runtime-/Supervisor-Logs rotieren bei 5 MiB mit je drei Sicherungen. Windows-Launcher nutzt den Wächter;
  Task-Wiederholungen sind begrenzt. Update übernimmt die Task-Einstellungen, prüft das vollständige Manifest
  und verlangt den Smoketest. Windows-Ausführung und Task-Abnahme bleiben offen.
- Standardübersicht auf Zustand und wenige Kennzahlen reduziert; Preise/Details bleiben eingeklappt.
  Analyse zeigt nur historisierte bekannte Kanäle. Vier unwirksame Regler-/Fallback-Felder aus dem Formular
  entfernt; Altwerte bleiben für Kompatibilität erhalten. Wetter verwendet optionale Standortkoordinaten,
  schreibt in den SiteDir und lädt erst bei Bedarf, unabhängig von der Hauptaktualisierung.
- Ungenutzten alten Spotmarkt-Regler samt drei exklusiven Tests entfernt; Zustandskompatibilität erhalten.
  HTML-Darstellung aus `runtime_db.py` nach `reporting.py` verschoben. Bericht-CSS wird gezielt per CSP-Hash
  erlaubt. Stunden-/Tagesaggregate behandeln die Zeitumstellung eindeutig; Altaggregate werden nicht rückwirkend geändert.
- Festes schlankes Paketprofil mit gepinnten Build-Werkzeugen und Zeitzonen; keine optionalen PDF-/Discovery-
  Bibliotheken oder Legacy-Service-Helfer im Paket. Binary-Test prüft Crash-Recovery, Rollen, Restore und Prüfsummen.
- Lokaler Nachweis: `docs/VALIDIERUNG_2026-09-22.md`. Keine Produktivinstallation, kein echter Anlagenzugriff.

### Hinzugefügt – lokale Beobachtung 20.09.2026

- Expliziter Beobachtungsmodus ohne reguläre Ausgaben, Heartbeat, Schreibtests oder Relinquish.
  Offene Rückgaben bleiben gespeichert und sichtbar. Bestehende Standorte bleiben im Steuerungsmodus.
- Messwerterfassung und Historie laufen bei fehlenden Preisen weiter; SMARD-Abrufe laufen außerhalb des Zyklus.
  Der Cache wird je aktuellem UTC-Intervall ausgewertet; nutzbarer Cache und gestörte Preisquelle bleiben getrennt.
- Empfangszeit, letzter erfolgreicher Read und optionale Quellzeit in Diagnose/API/Rohhistorie; tatsächliches
  Alter zwischen Reads, keine doppelten Historienwerte aus dem Lesecache. Ohne Quellzeit keine Frischebehauptung.
- Additive SQLite-Migration; frühere Werte erhalten keinen erfundenen Qualitätsnachweis. Dashboard und Berichte
  erklären Beobachtungsmodus, fehlende Preise und Datenqualität; gestörte Werte gehen nicht als gültig in Diagramme ein.
- Lokal mit Fake-Geräten, Simulation und macOS-Paket geprüft; keine Installation auf IPC oder Windows-Abnahme.
  Details: `docs/VALIDIERUNG_2026-09-20.md`.

### Hinzugefügt

- Stabilisierungsrunde vom 12.09.2026 (lokal, noch nicht auf IPC ausgeliefert): Regressionen für
  unplausible/nichtendliche Messwerte, alte Health-Dateien und fehlgeschlagene BACnet-Rückgaben.
- Eigenständiger Mini-EMS-CI-Workflow für Python 3.12 und Dashboard-Logik unter Linux/Windows;
  erster GitHub-Lauf und Windows-Paketprüfung stehen aus.

### Korrigiert – lokale Stabilisierungsrunde 12.09.2026

- Unplausible oder teilweise fehlgeschlagene Messreihen sind `quality=bad`; NaN/Infinity gelangen nicht in
  Messwert-Snapshots. Empfangsfrische ist weiterhin kein Nachweis für eine aktuelle Messung im Controller.
- Health- und Status-API bewerten das Snapshot-Alter bei jeder Anfrage. Alte Zyklen werden `stale_runtime`,
  fehlende/ungültige Zeitstempel `unknown`; ohne gültigen Watchdog-Schwellwert gilt ein 300-Sekunden-Fallback.
- Fehlgeschlagene Relinquish-Versuche bleiben offen, sperren Folgetests und Änderungen der Punktfreigabe
  und werden beim Neustart erneut versucht. Transportausnahmen werden gespeichert; die manuelle API
  und Oberfläche melden Erfolg nur bei bestätigter Rückgabe.
- Schreibtests zeigen angeforderten Wert, ACK, einmaligen Readback und Rückgabe dauerhaft getrennt.
  Eine fehlende Rücklesung wird nicht als belegte Wirksamkeit dargestellt (UX24, lokale Umsetzung).

### Korrigiert und vereinfacht – Fortsetzung 13.09.2026

- Fehlendes Write-ACK und Write-Ausnahmen hinterlassen einen getrennten Schreibfehler und denselben
  persistenten Rückgabeablauf wie Timer/Neustart. Originalziel und Priorität werden vor dem Write gesichert.
  Rückgabeversuche werden vor dem I/O angelegt; bei Abbruch bleibt das Ergebnis ausdrücklich unbekannt.
- Ungeklärte historische Fehlversuche blockieren neue Tests; keine automatisch geratene Zielpriorität.
  Der Timer berücksichtigt bereits vergangene I/O-Zeit. Irreführende UI-Rückgabeversprechen entfernt.
- Preisintervalle durchgängig auf UTC-Viertelstunden umgestellt, einschließlich 92/100-Intervall-Tagen,
  Stundenquellen, Cache, Korrekturen, Plan, manuellen Fenstern, Preisübergabe, Historie und Diagramm.
  Mehrdeutige alte Cachetage werden verworfen; alte Historie bleibt gekennzeichnet erhalten.
- Ungenutzten alternativen SMARD-Snapshot-/Stundenaggregationsweg und stillen Best-effort-Relinquish entfernt.
- Release-Builds markieren auch unversionierte Dateien als `+dirty`; lokale macOS-Paketprüfung durchgeführt.
  Windows-Build, GitHub-CI und IPC-Abnahme sind damit noch nicht nachgewiesen.

### Frühere, noch nicht vollständig versionierte Änderungen

- Persönliche lokale Viewer-/Admin-Konten mit scrypt-Passworthashes, serverseitigen Sitzungen, Login-Schutz,
  Kontenverwaltung und getrenntem Security-Audit in `identity.sqlite`. Viewer lesen Betrieb, Historie und
  Berichte; Admins konfigurieren. Der lokale Recovery-Befehl setzt bei bestehenden Konten ein temporäres
  Admin-Passwort und widerruft alte Sitzungen.
- Explizite BACnet-Inbetriebnahmefreigaben für eindeutig benannte `EMS_`-BV/AV-Punkte. Admin-Schreibtests
  laufen zehn Sekunden auf Priorität 14, zeigen den wirksamen Wert und relinquishen automatisch; unfertige
  Leases werden nach Neustart bereinigt. Modbus bleibt read-only.
- Standortunabhängiger UI-Konfigurationspfad: `site.sqlite` speichert die aktive Standortkonfiguration,
  Mapping-Entwürfe, Audit-Metadaten und unveränderliche Revisionen transaktional. Neue Standorte starten sicher
  in Simulation; `--site-dir` ersetzt den produktiven `--config`-Startparameter.
- Einmalige Migration bestehender Pilotkonfigurationen: Eine vorhandene `config.json` wird validiert, nach
  `site.sqlite` übernommen und anschließend als `.migrated.*.bak` aus dem aktiven Startpfad genommen.
- Die erweiterte UI speichert nun auch Standortmetadaten, Netzwerk-Timeouts, Netzwerkmodus, Fail-safe,
  DDC-Heartbeat sowie BACnet-Schreibprioritäten und Rückgaberechte.
- Konfigurationsseite als geführtes "Standort einrichten" (UX14-16, S5/S6): Standort → Geräte → Datenpunkte →
  Testen → Schreibzugriffe → Abschließen mit Fortschrittskarten, Punktlisten-Upload (CSV/TSV/XLSX) und optionaler
  BACnet-Discovery-Vorschau als Einstieg in "Datenpunkte", einer fachlichen Mapping-Tabelle (Bedeutung,
  Quelle, Live-Wert, Status statt technischer Rohpunkte) und "Alle Punkte testen" für einen sequenziellen
  Live-Check aller Zuordnungen in Inbetriebnahme-Sprache. „Einrichtung abschließen“ prüft erneut und übernimmt
  nur in einer Admin-Sitzung über `POST /api/config/mapping/activate`; Backup, gespeicherter Entwurf,
  Audit-Eintrag und Neustarthinweis entstehen automatisch. Aktiver Stand, offener Entwurf und Neustartbedarf
  bleiben getrennt sichtbar. Das bisherige Konfigurationsformular bleibt als „Erweiterte Direktbearbeitung“
  vollständig erhalten.
- Nachvollziehbarer Pilotbetrieb (H8): Das Betriebslog erfasst Runtime-Starts, datensparsame Dashboard-Aufrufe
  und Anlagenübergaben. Der Revisionsverlauf in `site.sqlite` erfasst Mapping-, Standort- und Preissteuerungsänderungen;
  `GET /api/config/changes` und die Inbetriebnahme-UI zeigen daraus einen bereinigten Verlauf ohne Token,
  interne Dateipfade oder personenbezogene Daten.
- Softwareversion sichtbar: Die Runtime liest beim Start die `VERSION`-Datei des
  Release-Pakets und stellt sie additiv unter `/api/status` als `app_version`
  (`version`, `git_commit`, `build_date`) bereit. Im Git-Betrieb ohne
  `VERSION`-Datei erscheint `dev` (mit kurzem Git-Hash, falls ermittelbar). Die
  Systemstatus-Seite des Dashboards zeigt eine dezente Zeile "Softwareversion".
- `CHANGELOG.md` eingeführt (diese Datei). Die Build-Skripte übernehmen den
  `[Unreleased]`-Stand als versionierten Schnappschuss ins Release-Paket.
- Update-Automatisierung für die IPC: `windows/update_release.ps1` setzt den
  bisher manuellen H7-Ablauf (Prüfsumme, Task stoppen, App-Ordner umbenennen als
  Rollback-Kandidat, neues Paket kopieren, Task starten, Smoketest) als Skript
  um; `-Rollback` schiebt den vorherigen App-Ordner zurück. Standortdaten
  (`SiteDir`) werden nie angefasst.
- Smoketest nach dem Update: `windows/smoketest_release.ps1` prüft frische
  `health.json` (`timestamp`, `runtime_status`), die minimale `/api/health`-Antwort inkl.
  erwarteter `app_version` und `api_read_only`, sowie das Log auf neue
  `ERROR`-Zeilen. Exit-Code 0/1 mit deutschen Meldungen.
- Reale IPC-Abnahme des Release-Wechsels am 12.07.2026 durch den Betreiber bestätigt:
  neue Version fehlerfrei, Standortkonfiguration erhalten, Freigabecode erfolgreich
  und keine Fehlermeldungen. Die Bestätigung ist ohne gespeicherte Konsolenausgaben dokumentiert.

### Geändert

- Die Build-Skripte (`packaging/build_release.ps1` und `.sh`) verlangen die
  Version jetzt als expliziten Pflicht-Parameter (`-Version` bzw.
  `MINI_EMS_VERSION`) statt eines still veraltenden Vorgabewerts – reproduzierbar
  und ohne versehentlich falsche Versionskennung.
- Der Windows-Smoketest prüft den tatsächlichen Zeitstempel `timestamp` der kompakten
  `health.json`; ältere Pakete mit `last_cycle_at` bleiben kompatibel.

## [2026.07.0] - 2026-07-08

Erster versionierter Release-Paket-Betrieb auf der IPC. Davor lief Mini EMS als
Git-Checkout ohne Versionsnummern; dieser Eintrag fasst den Stand bis zum
Umzug auf das Release-Paket ehrlich zusammen (abgeleitet aus den Wellen-Merges
und IPC-Meilensteinen im Git-Log), er erfindet keine feinere Zwischenhistorie.

### Hinzugefügt

- Release-Paketierung (H2): PyInstaller-One-Dir-Build mit `mini_ems(.exe)`,
  Dashboard-/Template-/Sim-Ressourcen als Daten neben dem Executable,
  `VERSION`, `SHA256SUMS` und `RELEASE_HINWEISE.md`; frozen-fähige
  Pfadauflösung (`mini_ems_runtime/resources.py`).
- Read-only-Netzwerkmodus der HTTP-API (H5): `api.read_only` sperrt alle
  schreibenden/aktiven Endpunkte serverseitig (deny-by-default) mit deutschem
  Fehlerkörper; struktureller Wächter-Test gegen Testlücken.
- Zweiter Protokoll-Adapter: Modbus TCP read-only (S4) über denselben
  ProtocolAdapter-Kontrakt wie BACnet.
- Konfigurations-/Mapping-UI-Grundlagen: Mapping-Entwurf mit Preview
  (`POST /api/config/mapping/preview`), Punktlisten-Import (CSV/TSV/XLSX) und
  read-only BACnet-Discovery-Vorstufe (S8).
- Reporting- und UX-Ausbau: kundentauglicher Tagesbericht (UX2),
  Berichte-Standardweg und lesbare Diagramme (UX3/UX8), Operator-Startseite mit
  klarer Hauptmeldung (UX4), verständliche Zustandsmeldungen (UX5/UX6),
  Responsive-/Tablet-Bedienbarkeit (UX9), Freshness-/Plausibilitätshinweise an
  den Dashboard-Kacheln.

### Sicherheit / Betrieb

- Geschütztes Kundenhosting: Sicherheitsgrenze und Sichtbarkeitsmatrix (H1),
  Installationslayout und Windows-Dateirechte (H3), API-Bindung hinter
  Reverse-Proxy (H4). IPC-Stand (2026-07-08): Release-Paket unter
  `C:\Program Files\MiniEMS`, externe `C:\ProgramData\MiniEMS\config.json`,
  gehärtete ACLs, Caddy auf `192.168.244.10:443` vor lokal gebundener API
  (`127.0.0.1:8090`), `api.read_only` aktiv.
- Dokumentierter Update-, Healthcheck- und Rollback-Ablauf (H7,
  `UPDATE_WARTUNG.md`).

### Dokumentation

- Architektur- und Integrationsdoku: `EDGE_INTEGRATION_CONTRACT.md`,
  `EMS-Mapping.md` (S1–S3), BACnet-Stack-Evaluierung (`BACNET_STACK_EVAL.md`,
  S7), `HOSTING_SICHERHEIT.md`, `UI_STYLEGUIDE.md`, `PILOT_DEMO.md`.
