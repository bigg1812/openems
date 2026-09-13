# Mini EMS – Technische Roadmap

**Stand: 12.09.2026.** Maßgebliche Aufgabenliste für den lokalen Entwicklungsstand.
Die [Produkt-/UX-Roadmap](PRODUCT_UX_ROADMAP.md) führt die Bedienaufgaben;
[das Archiv](docs/archive/ROADMAP_vor_2026-09-12.md) bewahrt die frühere Planung mit S-/H-/C-IDs.
Neue Prioritäten hier ersetzen die dortigen Empfehlungen. Ein älteres Häkchen ist kein Release- oder Feldnachweis.

## Ziel der nächsten Version

**Einen Standort zuverlässig einrichten, seinen Zustand korrekt erklären und freigegebene Eingriffe
einschließlich ihrer Rückgabe lückenlos nachweisen.**

Die nächste Version ist eine Stabilisierungsrunde. Cloud, zusätzliche Protokollfamilien und ein allgemeiner
Plattformkern folgen erst nach einem verlässlich abgenommenen Standortablauf.

## Geprüfter Stand und Nachweisgrenzen

- Eigene Python-Laufzeit mit BACnet, Modbus TCP read-only, Preis-Cache, Historie, Reports und Browseroberfläche.
- `site.sqlite` ist die einzige aktive Standortkonfiguration; `--site-dir` trennt Anlage und Simulation.
- Viewer/Admin, getrennte `identity.sqlite`, Mapping-Revisionen und BACnet-Testfreigaben sind implementiert.
- Der Mapping-Assistent unterstützt BACnet; Modbus ist noch nicht durchgängig im geführten Ablauf angekommen.
- Release-Paket, Windows-Task, Caddy, Backup-/Update-/Rollback-Werkzeuge sind vorhanden.
- Review-Basis: Commit `1bd2d3986`; 151 Python-Tests und 78 Dashboard-Prüfungen bestanden am 12.09.2026.
  Zusätzliche Fehlersimulationen zeigten dennoch Qualitäts-, Health-, Rückgabe- und Zeitmodelllücken.
- Die unten als lokal umgesetzt bezeichneten Änderungen sind noch kein ausgeliefertes Windows-Release.
- **Prüfung 12./13.09.2026:** Lokale Regressionen, HTTP-Integration, Dashboard-Harness und macOS-Paketbau.
  Der gebaute Prozess wurde im Browser mit getrenntem Simulationsstandort geprüft. Details und Grenzen:
  [Validierungsnachweis](docs/VALIDIERUNG_2026-09-13.md). Kein Windows-Release installiert, keine Live-Anlagenzugriffe.
- IPC-Update vom 12.07.2026: Betreiberbestätigung vorhanden, keine Konsolennachweise im Repo.
- UX24 enthält die lokale Notiz über reale BV-/AV-Tests vom 14.07.2026. Das ist zusätzliche Felderfahrung,
  keine vollständige Rollen-/Release-/Zweitrechner-Abnahme. Installierte Version am 12.09.2026 nicht live geprüft.
- `design_prototype/` ist ein statischer Entwurf ohne Anlagen-/API-Verbindung.

## Reihenfolge und Statusregeln

1. R1–R4: Datenqualität, Betriebszustand, Schreibnachweis und Zeitmodell.
2. R5–R7: Version/Abnahme, DDC-Fallback und reproduzierbare Prüfung/Auslieferung.
3. R8–R11: Beobachtungsmodus, Dokumentation, Codegrenzen und Standortannahmen.
4. UX23 und R12: fachfremder Bedienversuch und konkreter weiterer Gerätetyp.
5. Erst dann S9/C1: kleiner read-only Export.

**Status:** `lokal geprüft` bedeutet implementiert und lokal getestet; `vorbereitet` bedeutet noch nicht in der
Zielumgebung nachgewiesen; `offen` ist unerledigte Arbeit. Feldabnahmen bleiben ausdrücklich separat offen.

## P1 – Verlässliche Zustände und Eingriffe

### R1. Messwertqualität eindeutig machen

- [x] **R1a – lokal geprüft:** Unplausible Werte tragen `quality=bad`; NaN/Infinity werden vor Speicherung
  und API-Ausgabe verworfen. Teilweise fehlgeschlagene Messreihen sind nicht mehr `good`.
- **Nachweis:** Regressionen in `tests/test_review_hardening.py` sowie bestehende Runtime-/Adaptertests.
- [ ] **R1b – offen:** Zeitmodell der Messwerte vervollständigen. Empfangszeit, letzter erfolgreicher Read und
  gegebenenfalls Quellzeit unterscheiden; Alter zwischen Lesezyklen weiterführen. Ein erneut gelesener
  eingefrorener Controllerwert wird durch einen neuen Empfangszeitstempel allein nicht frisch.
- **Abnahme R1b:** Bei ausgelassenen Reads steigt das Alter; Kommunikationsausfall und unplausible Werte bleiben
  sichtbar; Messwertalter und Quellenalter werden nicht verwechselt. Alte Freshness-Häkchen gelten nur für die Grundlage.

### R2. Health unabhängig vom Zyklus bewerten

- [x] **R2a – lokal geprüft:** `/api/health` und `/api/status` bewerten bei jeder Anfrage das Alter des gespeicherten
  Zyklus. Ein alter Snapshot wird `stale_runtime`; fehlende, ungültige, zeitzonenlose oder zukünftige Zeitstempel
  werden `unknown`. Der gespeicherte Zyklusstatus bleibt in `/api/status` als `cycle_status` erhalten.
- **Grenze:** Gültiger `max_cycle_age_seconds` aus dem Snapshot, sonst 300 Sekunden API-Fallback.
  Dies verändert weder Anlagenwerte noch die gespeicherte Health-Datei. HTTP 200 bedeutet erreichbare API;
  der Payload-Status bewertet den Zyklus. Frischer `safe_mode` bleibt ein fachlicher Fehler bei lebender Runtime.
- **Nachweis:** Direkte API-Regressionen und HTTP-Test mit laufendem Testserver und altem Snapshot.
- [ ] **R2b – offen:** Prozessüberwachung, Alarmweg und Wiederanlauf unabhängig von Runtime/API festlegen;
  zyklusinterne Watchdog-Semantik und API-Bewertung vollständig vereinheitlichen.
- **Abnahme R2b:** Hängender Zyklus, abgestürzter Prozess und fachlich gestörter, aber laufender Zyklus sind
  unterscheidbar; Alarm und Wiederanlauf am Windows-Paket nachgewiesen.

### R3. BACnet-Rückgabe als offene Verpflichtung behandeln

- [x] **R3a – lokal geprüft:** `release_failed` bleibt in Recovery und Sperre für neue Tests enthalten.
  Transportausnahmen beim Relinquish werden gespeichert. Erneute Punktfreigabe/Prioritätsänderung ist bei
  offener Lease gesperrt. Manuelle API-Rückgabe meldet Erfolg nur bei bestätigter Rückgabe.
- **Nachweis:** Fake-Adapter testet fehlendes ACK, Transportausnahme, gesperrten Folgetest, unveränderte Priorität
  und erfolgreiche Wiederaufnahme. UI bietet für offene Rückgaben weiterhin die Rückgabeaktion an.
- **Grenze:** Kein unbegrenzter Hintergrund-Retry. Erneuter Versuch durch Admin, beim Neustart oder beim geordneten
  Beenden; eine bestätigte Rückgabe ist ein Protokollnachweis, keine Messung eines sicheren Anlagenzustands.
- [x] **R3b – lokal geprüft:** Auch fehlendes Write-ACK und Write-Ausnahmen führen in denselben gespeicherten
  Rückgabeablauf. Ziel und Priorität werden vor dem Write festgehalten; der ursprüngliche Schreibfehler bleibt
  getrennt vom Rückgabeergebnis erhalten. Jeder Rückgabeversuch wird vor dem I/O protokolliert und danach ergänzt.
  Ein Prozessabbruch hinterlässt einen Versuch ohne Ergebnis, keinen erfundenen Erfolg. Neustart versucht nur
  Rückgabe, keinen erneuten Test-Write. Langsames I/O verlängert den Timer nicht um weitere zehn Sekunden.
- **Altbestände:** Historische `failed`-Leases ohne gesicherte Zielpriorität blockieren neue Tests und erneute
  Freigabe. Sie werden nicht automatisch auf einer geratenen Priorität zurückgegeben; Prüfung vor Ort erforderlich.
- [ ] **R3c – Feldabnahme offen:** Auf freigegebenem ungefährlichem Punkt Write, Readback, Prioritätskonflikt,
  Rückgabe und Kommunikationsfehler prüfen. Timer sind keine IPC-unabhängige Safety-Garantie; siehe R6.
- **UX-Verweis:** UX24 führt ausschließlich die dauerhafte und eindeutige Ergebnisdarstellung.

### R4. Preisintervalle über UTC eindeutig identifizieren

- [x] **Lokal geprüft:** Provider, Cache, Preisübergabe, Plan, Simulation, Historie und Diagramm verwenden
  chronologische UTC-Viertelstunden. Ein Berliner Markttag hat 92, 96 oder 100 Intervalle; Stundenquellen werden
  in vier gleiche Viertelstunden aufgelöst. Wiederholte Uhrzeiten erhalten einen Offset in der Beschriftung.
- [x] Gleich große Preiskorrekturen aktualisieren den Cache; neuere Quellblöcke gewinnen. Fehlende Intervalle
  bleiben fehlend, verfügbare Cachewerte können einspringen; ein fehlender aktueller Preis stoppt den Regelpfad.
- [x] Normale alte Cachetage werden migriert; alte Zeitumstellungstage werden wegen Mehrdeutigkeit verworfen.
  Historische `price_slots` bleiben erhalten. Neue `price_intervals` haben UTC-Schlüssel; Berichte verwenden je Tag
  die neue Serie oder den ausdrücklich als `legacy_clock_slots` markierten Altbestand, ohne beide zu vermischen.
- [x] Manuelle Fenster benötigen eindeutige Ortszeiten oder `start_utc`/`end_utc`; mehrdeutige/nicht existierende
  Uhrzeiten führen vor regulären Ausgaben in `safe_mode`. Das beweist keinen physisch sicheren Zustand der DDC.
- **Nachweis:** `tests/test_price_intervals.py`, Zyklusregression und Dashboard-Harness auch mit amerikanischer
  Prozesszeitzone. Zeitmodell und Migrationsregeln stehen im [Integrationsvertrag](EDGE_INTEGRATION_CONTRACT.md).
- [ ] Windows-Lauf und Paket-/IPC-Vergleich der Preisübergabe im Rahmen von R5/R7 abnehmen.

## P2 – Freigabe und wiederholbarer Betrieb

### R5. Tatsächliche IPC-Version und Abnahmen konsolidieren

- [ ] Installierte `VERSION` und Commit, Starttask, Site-Store und Änderungen seit der letzten Abnahme feststellen.
- [ ] H4/H5/Hosting-To-do 3 als **einen** Zweitrechner-Nachweis führen: HTTPS über freigegebenes Kundennetz/VPN/Secomea,
  keine direkte LAN-Erreichbarkeit von 8090, Rollen und gesperrte Anlagenaktionen prüfen.
- [ ] H6/UX12: Erst-Admin, Viewer, Rollenwechsel, Recovery und Konfiguration mit aktuellem Release abnehmen.
- **Abnahme:** Eine datierte Version-/Prüfmatrix mit Ergebnis und Nachweisart; keine Übertragung alter Häkchen auf neue Builds.
- **Benötigte Betreiberangaben erst hierfür:** installierte Version, freigegebener Zugriffsweg, Testzeitfenster und Testpunkt.

### R6. Anlagenfallback fachlich abnehmen (S15 / frühere BV400-Prüfung)

- [ ] Netzleistungsabhängige Sperre, Vorzeichen, Grenzwerte und Reaktion der realen DDC klären.
- [ ] DDC-Heartbeat/Fallback bei IPC-Ausfall und Kommunikationsverlust nachweisen; Wirkung bestehender Prioritäten prüfen.
- [ ] `fail_safe_output` und `comm_error_safe_mode_threshold` fachlich entscheiden: implementieren oder aus dem aktiven
  Einstellmodell entfernen. Aktuell werden sie eingelesen/angezeigt, aber nicht entsprechend im Zyklus ausgewertet.
- **Abnahme:** Betreiber/MSR bestätigen Reaktion, Timeout, Ersatzbetrieb und Wiederanlauf am Standort.
  `safe_mode` allein beweist keinen sicheren physischen Anlagenzustand.

### R7. Tests und Release reproduzierbar ausführen

- [x] **Vorbereitet:** `.github/workflows/mini-ems.yml` führt Python-3.12-Tests und Dashboard-Logik unter Linux/Windows aus.
  Workflow-Datei angelegt; GitHub-Ausführung steht aus. Lokale Prüfungen ersetzen den Windows-Nachweis nicht.
- [ ] Ersten CI-Lauf auf beiden Betriebssystemen bestätigen.
- [ ] Abhängigkeiten und optionale Funktionen festschreiben: insbesondere BACpypes3, Template/PDF und Build-Werkzeuge.
- [x] Lokales macOS-Paket mit PyInstaller gebaut; Simulation, Login, Preisdiagramm, Schreibtest und persistentes Ergebnis geprüft. Buildkennzeichen berücksichtigt jetzt auch unversionierte Dateien.
- [ ] Windows-Release automatisiert bauen und mit frischem Standort, Login, Health und Update/Restore testen.
- [ ] Aufbewahrungsregeln, Datenbankwachstum und Wiederherstellung mit realistischem Datenvolumen prüfen.
- **Abnahme:** Gleiches Paketverhalten auf sauberem Rechner; Version/Commit und Prüfergebnisse sind zuordenbar.

## P3 – Produkt vereinfachen und Standortbindung lösen

### R8. Reale Anlage ohne zyklische Writes beobachten

- [ ] Eigenen Anlagen-Monitoringmodus implementieren. Aktuell verbietet die Validierung
  `bacnet_mode=real` mit `real_writes_enabled=false`; `api.read_only` ersetzt diesen Modus nicht.
- **Abnahme:** Echte Reads erlaubt, alle regulären Writes unterbunden; Übergang zur Steuerung explizit freigegeben.
  Lokale Entwicklung bleibt ausschließlich Simulation. Umgang mit bereits offenen Rückgaben ist separat definiert.

### R9. Aktive Dokumentation konsolidieren

- [x] Aktuelle Prioritäten und Review-Befunde hier zusammengeführt, frühere technische Planung vollständig archiviert.
- [x] Produktroadmap, README, Betriebsanleitungs-Einstieg/-Empfehlung und Integrationsvertrag an die erste Runde angeglichen.
- [ ] Betriebsanleitung vollständig auf `--site-dir` und externe Standortdaten umstellen; Pilot-/JSON-Historie auslagern.
- [ ] Release-/Update-/Packaging-/Proxy-Anleitungen entdoppeln: ein maßgeblicher Ort je Anleitung, andere Stellen verlinken.
- [ ] BACnet-Evaluierung und lange OpenEMS-Vergleiche als datierte Entscheidungen/Referenzen führen.
- [ ] Changelog-Releasegrenzen und UX-Status anhand R5 nachziehen; Pilot-Demo kürzen und Viewer/Admin trennen.
- **Abnahme:** Keine konkurrierenden Startanweisungen; aktuelle Aufgaben stehen nur hier bzw. in der UX-Roadmap.

### R10. Altcode entfernen und große Dateien fachlich aufteilen

- [ ] Nutzung prüfen, dann alten `SpotMarketLockoutController` samt verwaisten Zustands-/Testresten entfernen.
- [x] Unbenutzten zweiten SMARD-Snapshot-/Stundenaggregationsweg samt ausschließlich dort verwendeten Helfern entfernt; der Runtime-Pfad ist `scan_recent_slot_maps`.
- [ ] Alten `dashboard_proxy.py` und `windows/install_service.ps1` aus unterstützten Auslieferungspfaden entfernen;
  verbleibende Nutzer/Migrationsbedürfnisse vorher prüfen.
- [ ] Festen Pilotimport `objectlist_import.py` aus dem allgemeinen Laufzeitkern herausnehmen.
- [ ] Einen verbindlichen Report-Renderer wählen; `runtime_db.py` von Reportdarstellung trennen.
- [ ] `http_api.py`, `dashboard.js` und `cycle.py` entlang vorhandener Aufgaben aufteilen; externe Preisabfragen
  zeitlich vom Anlagenzyklus entkoppeln. Kein Frameworkwechsel allein wegen Dateigröße.
- **Abnahme:** Verhalten bleibt durch passende Tests belegt; keine zweite aktive Konfigurationsquelle;
  Entfernung erst nach Referenz-/Kompatibilitätsprüfung.

### R11. Standortannahmen beseitigen

- [ ] Wetterkoordinaten/-name aus Standortdaten beziehen und Wettercache in den SiteDir verlegen.
- [ ] Feste Energiekanäle und Pilotmetadaten als Energie-Fachmodell kenntlich machen; gemeinsame Kanalmetadaten verbessern.
- **Abnahme:** Zwei unterschiedlich konfigurierte Simulationsstandorte mischen weder Namen noch Dateien oder Werte.

### R12. Konkreten zweiten Gerätetyp durchgängig einrichten

- [ ] Modbus read-only in den geführten Mapping-/Test-/Aktivierungspfad aufnehmen (UX17).
- [ ] Optionalen BACpypes3-Discovery-Pfad mit installierter Abhängigkeit und freigegebenem Standort tatsächlich prüfen.
- **Abnahme:** Ein konkretes Gerät wird nachvollziehbar importiert, zugeordnet und getestet; Discovery erzeugt nur Kandidaten.

## Nach der Stabilisierung: begrenzter Export und Repository-Trennung

- [ ] **S9/C1:** Versionierte read-only Payload, lokale Outbox und simulierter Empfänger. Nach Unterbrechung
  nachvollziehbar weiterliefern; Dublettenbehandlung und Qualitätskennzeichen prüfen. Keine Remote-Befehle.
- [ ] **Repository-Isolierung:** Begrenzte OpenEMS-Entscheidungsmatrix, externe Dateireferenzen, Herkunftsinventar,
  Build und Historienübernahme prüfen; Voraussetzungen aus `PLATTFORM_ZIELBILD.md` beachten.
- [ ] **Produktnachweis:** Einen konkreten Nutzen samt Baseline, Messdauer und Betreuungsaufwand belegen.
  Tagesberichte allein sind kein Nachweis eingesparter Energie oder Kosten.

**Geparkt bis konkreter Bedarf besteht:** S10 M-Bus/wM-Bus; S11 Semantikexport; S12 Remote Commands;
S16 prädiktive Leases; C2 Brokerwahl, C3 Kafka, C4 semantischer Dienst, C5/C6 Cloud-Zeitreihenspeicher,
C7 Cloud-Retention, C8 Graph/RDF, C9 Auto-Mapping. Lokale Aufbewahrung gehört bereits zu R7.
Die ursprünglichen Kriterien bleiben im Archiv erhalten. UX18–UX22 folgen erst ihren technischen Grundlagen.

## Container: bewusste spätere Deployment-Option

Aktuell bleibt das native Windows-Release der unterstützte Pfad. Es bündelt den Python-Interpreter bereits.
Containerisierung wird neu bewertet, wenn mehrere gleichartige IPCs, ein Linux-Ziel oder mehrere getrennt
zu betreibende Dienste den Zusatzaufwand rechtfertigen. Voraussetzung: BACnet-Netzwerkpfad, persistenter
SiteDir, Autostart, Health, Update und Rollback nachgewiesen. Container ersetzen weder Git-Versionsführung
noch die lokale Anlagenrückgabe. Kein Containerumbau in dieser Runde.

## Nächster Arbeitsblock

R3b/R4 sind lokal umgesetzt. Als Nächstes: geprüften Quellstand versionieren, ersten Windows-/Linux-CI-Lauf
bestätigen, daraus Windows-Paket bauen und mit getrenntem Simulationsstandort prüfen (R7). Dann gemeinsame
IPC-Abnahme R5/R3c und fachlicher DDC-Fallback R6 gemäß [Update und Wartung](UPDATE_WARTUNG.md).
R1b/R2b/R8 sowie die übrigen offenen Punkte bleiben eigenständige Aufgaben; sie sind durch diese Runde
nicht erledigt. UX23 benötigt weiterhin eine fachfremde Testperson.
