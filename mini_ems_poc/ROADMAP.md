# Mini EMS – Technische Roadmap

**Planungsstand: 22.09.2026.** Maßgebliche Aufgabenliste für den lokalen Entwicklungsstand.
Lokal geprüfte Umsetzung und ausstehende Windows-/Feldnachweise werden getrennt geführt.
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
- **Prüfung 20.09.2026:** R8a/R8b/R1b mit 196 Python-Tests, 116 Dashboard-Prüfungen in zwei Zeitzonen,
  macOS-Testpaket sowie Browser-/Neustartprüfung lokal nachgewiesen.
  [Validierungsnachweis](docs/VALIDIERUNG_2026-09-20.md); Windows-/Standortabnahme bleibt offen.
- **Prüfung 22.09.2026:** Prozesswächter, Speicherfehler, minimierte UI, Standortwetter und schlankes Paketprofil;
  211 Python-Tests, 121 Dashboard-Prüfungen je Zeitzone, 201.600 Messwerte im beschleunigten Historientest.
  [Validierungsnachweis](docs/VALIDIERUNG_2026-09-22.md) einschließlich Browser- und Paketprüfung.
- IPC-Update vom 12.07.2026: Betreiberbestätigung vorhanden, keine Konsolennachweise im Repo.
- UX24 enthält die lokale Notiz über reale BV-/AV-Tests vom 14.07.2026. Das ist zusätzliche Felderfahrung,
  keine vollständige Rollen-/Release-/Zweitrechner-Abnahme. Installierte Version am 12.09.2026 nicht live geprüft.
- `design_prototype/` ist ein statischer Entwurf ohne Anlagen-/API-Verbindung.

## Reihenfolge und Statusregeln

1. R8a/R8b und R1b sind lokal geprüft: preisunabhängige Erfassung, Beobachtungsmodus und Messwertalter.
   Nachweis und Grenzen: [Validierung 20.09.2026](docs/VALIDIERUNG_2026-09-20.md).
2. R2b/R7 sind lokal geprüft. Jetzt CI bestätigen und Windows-Paket, Task sowie Update/Rollback in Simulation abnehmen.
3. R5 und R8c: installierten Stand/Zugriff prüfen und einen begrenzten Beobachtungslauf am Standort auswerten.
4. Vor Steuerungsbetrieb: offene Feldabnahme R3c und DDC-Fallback R6 abschließen; R4 am Windows-Paket bestätigen.
5. R9–R11 begleitend im betroffenen Umfang; danach UX23, ein erster Diagnosefall R13 und bei konkretem Bedarf R12.
6. Erst nach der Stabilisierung S9/C1: kleiner read-only Export.

**Status:** `lokal geprüft` bedeutet implementiert und lokal getestet; `vorbereitet` bedeutet noch nicht in der
Zielumgebung nachgewiesen; `offen` ist unerledigte Arbeit. Feldabnahmen bleiben ausdrücklich separat offen.

## P1 – Verlässliche Zustände und Eingriffe

### R1. Messwertqualität eindeutig machen

- [x] **R1a – lokal geprüft:** Unplausible Werte tragen `quality=bad`; NaN/Infinity werden vor Speicherung
  und API-Ausgabe verworfen. Teilweise fehlgeschlagene Messreihen sind nicht mehr `good`.
- **Nachweis:** Regressionen in `tests/test_review_hardening.py` sowie bestehende Runtime-/Adaptertests.
- [x] **R1b – lokal geprüft:** Empfangszeit und letzter erfolgreicher Read sind in Diagnose, API und Rohhistorie
  enthalten. Ausgelassene Reads altern weiter, erzeugen aber keine neuen Messungen. Nach Neustart wird neu
  gelesen; ein fehlgeschlagener Read übernimmt keinen alten Wert als gültig. API-Anfragen bewerten das Alter erneut.
- **Grenze:** Die aktuellen Adapter liefern keine Quellzeit. `source_timestamp=null` und
  `source_freshness=unknown` machen dies ausdrücklich sichtbar. Ein erneut gelesener eingefrorener
  Controllerwert ist damit nicht als aktuelle Messung nachgewiesen; dessen Erkennung bleibt gerätespezifisch.
- **Nachweis:** `tests/test_monitoring.py`, Dashboard-Harness und additive Migration bestehender SQLite-Historie.

### R2. Health unabhängig vom Zyklus bewerten

- [x] **R2a – lokal geprüft:** `/api/health` und `/api/status` bewerten bei jeder Anfrage das Alter des gespeicherten
  Zyklus. Ein alter Snapshot wird `stale_runtime`; fehlende, ungültige, zeitzonenlose oder zukünftige Zeitstempel
  werden `unknown`. Der gespeicherte Zyklusstatus bleibt in `/api/status` als `cycle_status` erhalten.
- **Grenze:** Gültiger `max_cycle_age_seconds` aus dem Snapshot, sonst 300 Sekunden API-Fallback.
  Dies verändert weder Anlagenwerte noch die gespeicherte Health-Datei. HTTP 200 bedeutet erreichbare API;
  der Payload-Status bewertet den Zyklus. Frischer `safe_mode` bleibt ein fachlicher Fehler bei lebender Runtime.
- **Nachweis:** Direkte API-Regressionen und HTTP-Test mit laufendem Testserver und altem Snapshot.
- [x] **R2b – lokaler Teil geprüft:** Separater Supervisor erkennt Stillstand und Prozessabbruch, überwacht
  nur passende Run-IDs und begrenzt Neustarts persistent auf drei Startversuche in 15 Minuten.
  Lebende gestörte Zyklen bleiben sichtbar; fehlende Supervisor-Lebendigkeit wird separat in der API erkannt.
- [x] State-/Datenbankfehler werden vor dem Health-Nachweis bewertet; fehlgeschlagene Health-Schreibvorgänge
  bleiben als ausbleibender Fortschritt erkennbar. Regressionsfälle in `tests/test_operational_readiness.py`.
- [ ] **Zielumgebung offen:** Windows-Task/SYSTEM, Wiederanlauf und Störmeldung am nativen Paket prüfen.
  Lokale Supervisor-Datei/Log/API sind vorhanden; ein externer Alarmempfänger ist noch nicht eingerichtet.
- **Abnahme:** Hänger, Absturz und fachlicher Fehler bleiben unterscheidbar. Für unbeaufsichtigten Betrieb
  muss eine benannte Person Ausfallmeldungen auch bei nicht erreichbarer Runtime erhalten.

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
  Einstellmodell entfernen. Sie bleiben nur als Altwerte lesbar; die wirkungslosen UI-Einstellungen wurden entfernt. Eine entsprechende Zykluswirkung ist nicht implementiert.
- **Abnahme:** Betreiber/MSR bestätigen Reaktion, Timeout, Ersatzbetrieb und Wiederanlauf am Standort.
  `safe_mode` allein beweist keinen sicheren physischen Anlagenzustand.

### R7. Tests und Release reproduzierbar ausführen

- [x] **Vorbereitet:** CI führt Tests, PowerShell-Syntaxprüfung, Paketbau und Binary-Prüfung unter Linux/Windows
  aus; Artefakte werden nur nach Erfolg aufbewahrt. Erster tatsächlicher GitHub-Lauf bleibt offen.
- [x] Build-Abhängigkeiten festgeschrieben; `BUILD_REQUIREMENTS.txt` protokolliert das Build-Environment.
  Verbindliches Profil: eingebauter HTML-Renderer, Browserdruck für PDF, keine optionalen Jinja2/WeasyPrint/BACpypes3-Pakete.
- [x] Lokales macOS-Paket: Erststart, Rollen, Health, erzwungener Child-Absturz, Wiederanlauf, Site-Restore,
  SQLite-Integrität und unveränderte Paketprüfsummen automatisiert geprüft.
- [x] Beschleunigte Historienlast: sieben Tage mit 30-Sekunden-Takt und zehn Punkten, 20.160 Zyklen,
  201.600 Messwerte, rund 137 MiB. Tagesbericht-Abfrage 0,34 Sekunden; Backup/Restore intakt.
- [x] Aufbewahrung für den begrenzten Pilot festgelegt: rotierte Runtime-/Supervisor-Logs, vollständiges
  Standortbackup bei gestoppter Runtime; Historie bleibt erhalten. Keine automatische Datenlöschung implementiert.
- [ ] Windows-Paket auf sauberem Rechner sowie Task/SYSTEM, Update und Rollback mit getrenntem SiteDir prüfen.
- [ ] Vor dauerhaft unbeaufsichtigtem Betrieb: externe Alarmierung, Speicherbudget und automatische
  Aufbewahrung mit dem Betreiber festlegen. Der Lasttest ist kein siebentägiger Echtzeit-Dauertest.
- **Abnahme:** Paket, Commit, Betriebssystem und Prüfergebnisse sind eindeutig zuordenbar.

## P3 – Produkt vereinfachen und Standortbindung lösen

### R8. Reale Anlage ohne zyklische Writes beobachten

- [x] **R8a – lokal geprüft:** Erlaubte Reads und Historie laufen auch ohne nutzbaren aktuellen Preis weiter.
  SMARD aktualisiert im Hintergrund mit höchstens einem laufenden Abruf; der Zyklus liest nur den lokalen Cache
  und wählt das aktuelle UTC-Intervall neu. Preisfehler und gesperrte preisabhängige Entscheidungen bleiben sichtbar.
  Im Steuerungsmodus bleibt der bisherige Heartbeat-Pfad erhalten; er ist nicht preisabhängig.
- [x] **R8b – lokal geprüft:** `runtime.operation_mode=monitoring` und `real_writes_enabled=false` erlauben
  ausdrücklich reinen Lesebetrieb, auf IPC auch mit `bacnet_mode=real`. Der lokale Modus bleibt simuliert.
  Reguläre Ausgaben, Heartbeat, Schreibtests und Relinquish sind im Beobachtungsmodus gesperrt; zusätzlich
  schützt der Protokollrouter vor versehentlichen Schreibaufrufen. Bestehende Konfigurationen bleiben `control`.
  Offene Leases bleiben gespeichert und werden als Störung angezeigt. Klärung vor Ort oder Rückgabe im
  ausdrücklich freigegebenen Steuerungsbetrieb; keine automatische Erledigung durch Moduswechsel.
- **Lokal nachgewiesene Fälle R8a/R8b:** Preisquelle langsam/ausgefallen ohne nutzbaren Cache, einzelner Controller
  nicht erreichbar und Prozessneustart reproduzierbar geprüft. Verfügbare Messpunkte werden weiterhin
  erfasst; Ausfälle bleiben in Historie, Oberfläche und Bericht erkennbar. Messwertalter folgt R1b.
  Siehe [Validierung 20.09.2026](docs/VALIDIERUNG_2026-09-20.md); Standortnachweis weiterhin offen.
  Keine regulären Writes, auch keine zyklischen Preis-, Sperr- oder Heartbeat-Ausgaben; Schreibtests bleiben gesperrt.
  Vor dem Moduswechsel offene Rückgaben sichtbar machen und ihren Umgang ausdrücklich festlegen;
  bestehende Rückgabeverpflichtungen dürfen weder verschwinden noch stillschweigend als erledigt gelten.
- [ ] **R8c – Begrenzter Standortnachweis:** Nach R5/R7 wenige freigegebene Lesepunkte über einen vorab
  festgelegten Zeitraum beobachten, als Startvorschlag sieben Tage. Version, Punktliste, Leseintervalle,
  zulässiges Datenalter, erwartete Datenabdeckung und Auswertungsverantwortung vor Beginn festhalten.
  Datenlücken, Wiederanlauf, verständliche Zustände und Einrichtungs-/Betreuungsaufwand dokumentieren.
  Fehler gezielt in Simulation prüfen; keine ungeplanten Störungen an der Kundenanlage erzeugen.
- **Grenze:** Lokale Entwicklung bleibt ausschließlich Simulation. Ein bestandener Beobachtungslauf belegt
  weder Steuerungsfreigabe noch Energieeinsparung; für Steuerungsbetrieb bleiben R3c/R6 erforderlich.

### R9. Aktive Dokumentation konsolidieren

- [x] Aktuelle Prioritäten und Review-Befunde hier zusammengeführt, frühere technische Planung vollständig archiviert.
- [x] Produktroadmap, README, Betriebsanleitungs-Einstieg/-Empfehlung und Integrationsvertrag an die erste Runde angeglichen.
- [x] Betriebsanleitung auf `--site-dir` und externe Standortdaten gekürzt; alte Pilot-/JSON-Anweisungen bleiben in der Git-Historie.
- [x] Paketbau zentral unter `packaging/README.md`, Installation unter `RELEASE_WORKFLOW.md`, Abnahme/Wartung unter `UPDATE_WARTUNG.md`; README verlinkt den Build.
- [ ] BACnet-Evaluierung und lange OpenEMS-Vergleiche als datierte Entscheidungen/Referenzen führen.
- [ ] Changelog-Releasegrenzen und UX-Status anhand R5 nachziehen; Pilot-Demo kürzen und Viewer/Admin trennen.
- **Abnahme:** Keine konkurrierenden Startanweisungen; aktuelle Aufgaben stehen nur hier bzw. in der UX-Roadmap.

### R10. Altcode entfernen und große Dateien fachlich aufteilen

- [x] Ungenutzten `SpotMarketLockoutController` und drei ausschließlich dafür bestehende Tests entfernt; altes Zustandsformat bleibt für Rückwärtskompatibilität lesbar.
- [x] Unbenutzten zweiten SMARD-Snapshot-/Stundenaggregationsweg samt ausschließlich dort verwendeten Helfern entfernt; der Runtime-Pfad ist `scan_recent_slot_maps`.
- [x] Legacy-Service-/Proxy-Helfer werden nicht mit ausgeliefert. Historische Quellcodehilfen bleiben bis zur Klärung früherer Installationen erhalten.
- [ ] Festen Pilotimport `objectlist_import.py` aus dem allgemeinen Laufzeitkern herausnehmen.
- [x] Paket nutzt den eingebauten HTML-Renderer. Darstellung/Formatierung liegen in `reporting.py`; Datenabfragen bleiben in `runtime_db.py`.
- [ ] `http_api.py`, `dashboard.js` und `cycle.py` entlang vorhandener Aufgaben aufteilen; externe Preisabfragen
  im Rahmen von R8a vom Anlagenzyklus entkoppeln. Zunächst nur die für den Arbeitsblock nötigen Grenzen schaffen;
  kein Frameworkwechsel allein wegen Dateigröße. Python und SQLite bleiben Grundlage dieses Arbeitsblocks.
- **Abnahme:** Verhalten bleibt durch passende Tests belegt; keine zweite aktive Konfigurationsquelle;
  Entfernung erst nach Referenz-/Kompatibilitätsprüfung.

### R11. Standortannahmen beseitigen

- [x] Wetter verwendet validierte optionale Standortkoordinaten/-namen und Cache im SiteDir. Ohne Koordinaten kein externer Abruf; Standortwechsel invalidiert alte Wetterdaten.
- [x] Analyse bietet nur bekannte Kanäle mit tatsächlich gespeicherten Messungen an; keine unkonfigurierten Pilotpunkte im Standardangebot.
- [ ] Metadatenkatalog für beliebige neue semantische Kanäle erweitern; das bestehende Energie-Fachmodell bleibt eine bewusste Grenze.
- **Abnahme:** Zwei unterschiedlich konfigurierte Simulationsstandorte mischen weder Namen noch Dateien oder Werte.

### R12. Konkreten zweiten Gerätetyp durchgängig einrichten

- [ ] Modbus read-only in den geführten Mapping-/Test-/Aktivierungspfad aufnehmen (UX17).
- [ ] Optionalen BACpypes3-Discovery-Pfad mit installierter Abhängigkeit und freigegebenem Standort tatsächlich prüfen.
- **Abnahme:** Ein konkretes Gerät wird nachvollziehbar importiert, zugeordnet und getestet; Discovery erzeugt nur Kandidaten.

### R13. Ersten beobachtenden Diagnosefall fachlich prüfen

- [ ] Nach belastbarem Beobachtungslauf genau einen zum Standort passenden Befund auswählen, zum Beispiel
  „Betrieb außerhalb der Nutzungszeit“, sofern Betriebsrückmeldung, Zeitprogramm und Sonderfreigaben verfügbar sind.
- [ ] Eine Regelbeschreibung mit benötigten Punkten, gültigen Betriebszuständen, Datenqualität, Dauer/Grenzwerten,
  Rücksetzbedingung, Testfällen und konkreter Prüfempfehlung erstellen. Fehlende Voraussetzungen ergeben
  „nicht auswertbar“, keinen Normalzustand und keinen erfundenen Fehlerbefund.
- **Abnahme:** Normalbetrieb, echte Abweichung, zulässige Ausnahme und fehlende/veraltete Daten reproduzierbar
  prüfen; Befunde mit Standortverantwortlichen auf Verständlichkeit und Fehlalarme bewerten. Keine automatischen Eingriffe.
- **Lernquelle:** [open-control-library](https://github.com/jscott3201/open-control-library) als Vorlage für
  Regelbeschreibungen und Testvektoren. Übernommene Logik braucht eigene fachliche Prüfung am Anwendungsfall.

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

**Lokale Vorbereitung abgeschlossen:** R1b/R8a/R8b, lokaler Teil von R2b/R7 sowie die dafür nötige
Bereinigung von UI, Reports, Paket und Dokumentation. [Prüfnachweis](docs/VALIDIERUNG_2026-09-22.md).

**Jetzt sinnvoll: Windows-/VPN-Abnahme vorbereiten.** Zuerst den geprüften Quellstand versionieren,
Windows-/Linux-CI bestätigen und das Windows-Paket in einem separaten Simulationsstandort prüfen.
Task/SYSTEM, Update/Rollback, Berichtdruck und Windows-Zeitmodell gehören dazu. Ein macOS-Paket ist kein Windows-Paket.

Danach über den freigegebenen VPN-Zugang den bestehenden IPC-Stand zunächst nur lesen (R5): Version,
Prozesse/Task, Standortrevision, offene Rückgaben, Backup und Zugriffspfad. Erst anschließend den begrenzten
Beobachtungslauf mit wenigen vereinbarten Lesepunkten starten (R8c). Für spätere aktive Eingriffe bleiben
R3c/R6 und eine ausdrückliche Betreiberfreigabe erforderlich. Ein VPN ersetzt diese Grenzen nicht.

Nach dem Beobachtungsnachweis folgen ein Bedienversuch mit fachfremder Testperson (UX23) und genau ein
passender Diagnosefall (R13). Neue Protokolle, Cloud und ein Stackwechsel sind keine Voraussetzung hierfür.
