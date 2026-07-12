# Changelog

Alle nennenswerten Änderungen an Mini EMS PoC. Format angelehnt an
[Keep a Changelog](https://keepachangelog.com/de/1.1.0/); Versionsschema
`JJJJ.MM.n` (Jahr.Monat.laufende Nummer im Monat), passend zu den
`version=`-Kennungen der Release-Pakete (`packaging/build_release.*`, `VERSION`).

Pflege-Regel: Änderungen werden während der Arbeit unter `[Unreleased]`
gesammelt. Beim Release-Build wird der `[Unreleased]`-Stand als versionierter
**Schnappschuss** in die `CHANGELOG.md` **im Release-Paket** übernommen; diese
Repo-Datei wird vom Build nicht umgeschrieben, sondern bleibt manuelle Pflege
(siehe `packaging/README.md`, Abschnitt "Release erstellen").

## [Unreleased]

### Hinzugefügt

- Standortunabhängiger UI-Konfigurationspfad: `site.sqlite` speichert die aktive Standortkonfiguration,
  Mapping-Entwürfe, Audit-Metadaten und unveränderliche Revisionen transaktional. Neue Standorte starten sicher
  in Simulation; `--site-dir` ersetzt den produktiven `--config`-Startparameter.
- Einmalige Migration bestehender Pilotkonfigurationen: Eine vorhandene `config.json` wird validiert, nach
  `site.sqlite` übernommen und anschließend als `.migrated.*.bak` aus dem aktiven Startpfad genommen.
- Die erweiterte UI speichert nun auch Standortmetadaten, Netzwerk-Timeouts, Netzwerkmodus, Fail-safe,
  DDC-Heartbeat sowie BACnet-Schreibprioritäten und Rückgaberechte.
- Konfigurationsseite als geführtes "Standort einrichten" (UX14-16, S5/S6): Standort → Geräte → Datenpunkte →
  Testen → Abschließen mit Fortschrittskarten, Punktlisten-Upload (CSV/TSV/XLSX) und optionaler
  BACnet-Discovery-Vorschau als Einstieg in "Datenpunkte", einer fachlichen Mapping-Tabelle (Bedeutung,
  Quelle, Live-Wert, Status statt technischer Rohpunkte) und "Alle Punkte testen" für einen sequenziellen
  Live-Check aller Zuordnungen in Inbetriebnahme-Sprache. „Einrichtung abschließen“ prüft erneut und übernimmt
  nur mit lokalem Freigabecode über `POST /api/config/mapping/activate`; Backup, gespeicherter Entwurf,
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
  `health.json` (`timestamp`, `runtime_status`), `/api/status` inkl.
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
