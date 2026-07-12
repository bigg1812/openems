# Mini EMS PoC - Technische Roadmap

## Kontext / Ist-Zustand

Aktiver Fokus liegt auf dem lokalen Python-Prototyp `mini_ems_poc/`; neue Funktionen werden auf Feature-Branches
entwickelt und nach Prüfung in `develop` zusammengeführt. Der aktuelle Stand enthält den ProtocolAdapter-Kontrakt,
eine Plausibilitaets-Single-Source in `PointConfig`, einen Freshness/Quality-Gate (`max_age_seconds`) und den
UI-eigenen Standort-Speicher `site.sqlite`. Die aktuelle Python-Testsuite ist unter Python 3.12 grün
(`OK`), schlagen aber unter dem Standard-`python3` (3.9) dieses Rechners wegen PEP-604-Syntax (`X | None`) fehl.
Es gibt praktisch keine TODO/FIXME-Marker im Python-Code; offene Punkte stehen in `MINI_EMS_ANLEITUNG.md`
("Offene Punkte") und ergeben sich aus dem Code-Ist-Zustand.

Diese Datei behandelt bewusst die technische Betriebs-, Architektur- und Sicherheitsseite. Produktwirkung,
Reporting-UX, Bedienbarkeit und visuelles UI-Design werden separat in `PRODUCT_UX_ROADMAP.md` geführt.

Arbeitsregel für neue Architekturimpulse: Wenn aus Analyse, Wiki-Recherche oder Systemarchitektur-Gesprächen
ein sinnvoller späterer Ausbaupunkt entsteht, wird er hier oder in `PRODUCT_UX_ROADMAP.md` festgehalten. Dabei
gilt: als Zukunftsoption mit Nutzen, Einordnung und Risiken dokumentieren, aber nicht automatisch als nächster
Implementierungsschritt behandeln.

## Nächster Release-Pfad: standortunabhängige UI-Konfiguration (2026-07-12)

- Der Runtime-Start verwendet nur noch `--site-dir`; eine aktive `config.json` existiert nicht mehr.
- `site.sqlite` ist die einzige Quelle der Wahrheit für Standortparameter, Mapping-Entwürfe und Revisionen.
- Neue Standorte starten loopback-only, simuliert und ohne reale Writes. Der einmalige Freigabecode wird lokal
  ausgegeben; anschließend erfolgt die vollständige Einrichtung über die UI.
- Eine vorhandene Pilot-`config.json` wird beim ersten Start einmalig validiert, nach `site.sqlite` migriert und
  als `.migrated.*.bak` aus dem aktiven Pfad genommen.
- Release-Launcher und Windows-Task starten `mini_ems.exe --site-dir C:\ProgramData\MiniEMS --loop`.
- Mapping-/Standortänderungen erzeugen transaktionale SQLite-Revisionen; `.bak`, `mapping_drafts/` und
  `config_audit.jsonl` werden nicht mehr als getrennte Wahrheiten geführt.

## Historischer IPC-Stand vor diesem Release (2026-07-08)

Der echte IPC ist nicht mehr im alten Git-Checkout-Betrieb. Der belegte Standortzustand ist:

- Mini EMS läuft als Release-Paket unter `C:\Program Files\MiniEMS` mit externer
  `C:\ProgramData\MiniEMS\config.json`.
- Der geplante Task `MiniEmsPoCRelease` startet `mini_ems.exe --config
  "C:\ProgramData\MiniEMS\config.json" --loop`; Alt-Autostarts sind entschärft.
- `C:\ProgramData\MiniEMS` ist per ACL gehärtet; normale Windows-Benutzer haben keinen direkten Zugriff auf
  Standortdaten, Logs oder Runtime-Dateien.
- H4/H5 sind auf der IPC lokal umgeschaltet: Mini EMS bindet auf `127.0.0.1:8090`, Caddy lauscht auf
  `192.168.244.10:443` und proxyt auf `127.0.0.1:8090`, `api.read_only` ist aktiv.
- Lokal auf der IPC ist verifiziert: `/api/status` meldet `api_read_only: true`, direkte Zugriffe auf
  `192.168.244.10:8090` sind nicht mehr erreichbar, HTTPS über Caddy liefert `HTTP 200`, aktive/schreibende
  Endpunkte liefern `HTTP 403`.

Damit sind H2 und H3 erledigt; H4/H5 sind IPC-seitig umgeschaltet. Offen bleibt der reale Nachweis von einem
zweiten Rechner im freigegebenen Kundennetz/VPN/Secomea.

## Strategische Ergänzung (2026-07-01)

Die Erkenntnis aus der Architektur- und Marktbetrachtung ist: Mini EMS sollte nicht über den aktuellen
Windows-IPC definiert werden, sondern über seinen Integrationsvertrag zur Anlage. Der Windows-IPC bleibt der
praktische Pilot- und Kundenpfad. Das Zielmodell soll aber hardware- und betriebssystemneutral bleiben, damit
derselbe Kern später auch auf Linux-IPC, Industrial-IoT-Gateway, Embedded-Edge-Plattform oder containerisiertem
Edge-Device laufen kann.

Der nächste Reifegrad ist deshalb kein sofortiger Wechsel auf Linux, Container, balenaOS oder K3s, sondern ein
sauberer Edge-Integrationskern:

```text
BACnet / Modbus / HTTP / MQTT / GLT- oder Plattform-API
-> ProtocolAdapter
-> RawPoint / DeviceConfig / PointConfig
-> Canonical Channel / SemanticChannel
-> Time Series + Health + Quality
-> Controller
-> Safe Write Path
-> Northbound API / Export
```

Leitentscheidungen:

- Windows-IPC bleibt für den aktuellen PoC und erste Kundenpiloten gültig.
- `site.sqlite` ist der reale IPC-Pfad; lokale Simulation verwendet einen getrennten `--site-dir`.
- Deployment-Flotte, Container und OTA kommen erst nach sauberem Integrationsmodell, Datenqualität und Schreibsicherheit.
- Reads und Writes werden als unterschiedliche Risikoklassen behandelt.
- Die Regelung soll langfristig nur noch kanonische Kanäle lesen, nicht BACnet-Objekte, Modbus-Register oder API-Felder.

## Strategische Ergänzung (2026-07-02): Konfiguration als Mapping-Prozess

Die Konfiguration soll nicht als JSON-Editor oder lange technische Formularseite wachsen. Ziel ist ein leichter
Inbetriebnahmeprozess: Der Kunde bzw. Konfigurator richtet einen Standort ein, legt Geräte/Datenquellen an,
erfasst oder importiert Rohpunkte, ordnet sie fachlichen Mini-EMS-Kanälen zu, testet die Werte und aktiviert erst
danach die daraus erzeugte Runtime-Konfiguration.

Die verständliche Zwischenebene ist inzwischen zugleich die dauerhafte Quelle der Wahrheit:

```text
Mapping-Entwurf
-> Validierung und Preview
-> geprüfter Standortstand
-> transaktionale Revision in site.sqlite
-> Aktivierung nach Neustart
```

Der erste technische Kern ist `mini_ems_runtime/mapping_config.py` mit dem Preview-Endpunkt
`POST /api/config/mapping/preview`. Die UI erzeugt einen fachlichen Entwurf aus `devices`, `raw_points` und
`mappings`; der Generator übersetzt ihn in die geprüften Runtime-Bereiche (`network`, `points`,
`additional_inputs`) der nächsten Standortrevision.

Leitentscheidungen:

- Einstieg ist "Standort einrichten", nicht "Konfiguration bearbeiten".
- Fachliche Kanäle stehen vor Protokolldetails: z. B. "Netzleistung" vor "BACnet AV 300".
- Technische Details bleiben sichtbar, aber einklappbar und sekundär.
- Preview, Validierung, vorherige Revision und Audit-Metadaten bleiben Pflicht.
- Version 1 bleibt bewusst klein: manuelles BACnet-Mapping plus Preview; Scan, Import, Templates und Live-Test folgen danach.

## Strategische To-do-Linie: Edge-Integrationskern

- [x] **S1. Edge Integration Contract dokumentieren**
  - **Was:** Eine kurze Architekturdatei anlegen, z. B. `EDGE_INTEGRATION_CONTRACT.md`, die Gerät, Rohpunkt,
    kanonischen Kanal, Semantik, Qualität, Historie, Schreibpfad, Fallback und Audit Trail definiert.
  - **Nutzen:** Verhindert, dass Mini EMS nur ein größerer PoC-Baukasten wird. Der Vertrag macht klar, was die Edge
    gegenüber MSR, Betreiber, Dashboard, Cloud und späterem Business-System garantiert.
  - **Betroffen:** neue Doku-Datei unter `mini_ems_poc/`; querverwiesen aus `README.md`, `EMS-Mapping.md` oder
    `MINI_EMS_ANLEITUNG.md`, wenn sinnvoll.
  - **Aufwand:** S
  - **Risiken:** Doku darf nicht zu abstrakt werden; sie muss am bestehenden BACnet-Pfad und den realen Safety-Regeln
    hängen bleiben.
  - **Definition of Done:** Der Contract beantwortet: Was ist ein gültiger Messwert? Wann ist ein Wert stale/bad?
    Was darf gelesen werden? Was darf geschrieben werden? Was wird geloggt? Was passiert bei Netzwerk-, Controller-
    oder Cloud-Ausfall?

- [x] **S2. Bestehendes BACnet-Mapping auf das Zielmodell abbilden**
  - **Was:** Die vorhandenen BACnet-Punkte als Referenzmodell beschreiben: `source_id`, `protocol`, `raw_address`,
    `channel_id`, `equipment_id`, `role`, `unit`, `access`, Plausibilität, Aktualität und Schreibrecht.
  - **Nutzen:** Der bestehende PoC wird zur belastbaren Vorlage für spätere Modbus-, HTTP-, MQTT- oder GLT-Anbindungen.
  - **Betroffen:** zuerst Doku/Mapping; spätere Code-Folgen in `config.py`, `channels.py`, `protocol.py`, `cycle.py`.
  - **Aufwand:** M
  - **Risiken:** Nicht zu früh ein großes Semantik-Framework einbauen. Das Ziel ist ein kleines internes Modell, kein
    sofortiger Haystack-/Brick-Runtime-Stack.
  - **Definition of Done:** Die Regelung kann fachlich als Nutzer kanonischer Kanäle beschrieben werden; das darunterliegende
    Protokoll bleibt austauschbar.

- [x] **S3. Erstes wiederverwendbares Geräte-Template vorbereiten**
  - **Was:** Eine Geräteklasse als Template denken, bevorzugt Hauptzähler / Netzanschlusspunkt, weil daran Lastspitzen,
    Eigenverbrauch, Speicher, Spotmarkt, Flexibilität und §14a hängen.
  - **Nutzen:** Mini EMS entwickelt sich von projektbezogenen Einzelpunkten zu wiederholbaren Geräte- und Anlagenklassen.
  - **Betroffen:** zunächst Doku und Config-Struktur; später Tests und Adapter.
  - **Aufwand:** M
  - **Risiken:** Nicht zu viele Geräteklassen parallel anfangen.
  - **Definition of Done:** Es gibt eine klare Vorlage, welche Rohpunkte, Einheiten, Rollen, Plausibilitätsgrenzen,
    Aktualitätsregeln und optionalen Schreibrechte ein Hauptzähler braucht.

- [x] **S4. Danach Modbus TCP read-only als erster neuer Adapter**
  - **Was:** Erst nach S1-S3 einen read-only Modbus-TCP-Adapter für ein Leistungsmessgerät ergänzen.
  - **Nutzen:** Beweist, dass das Modell wirklich protokollneutral ist, ohne sofort neue Schreibrisiken einzubauen.
  - **Betroffen:** `protocol.py`, neuer Adapter, Config, Tests, Simulation.
  - **Aufwand:** M/L
  - **Risiken:** Registerlisten, Skalierung, Byte-/Word-Order und Vorzeichen müssen sauber geprüft werden.
  - **Definition of Done:** Ein kanonischer Kanal wie `meter.grid.active_power_kw` kann wahlweise aus BACnet oder Modbus
    stammen, ohne dass die Regelungslogik das Protokoll kennen muss.

- [x] **S5. Mapping-Entwurfsmodell als Konfigurationskern ausbauen**
  - **Was:** Das vorhandene Preview-Modell (`devices`, `raw_points`, `mappings`) zur zentralen Grundlage der
    Konfigurations-UI machen. Ein Mapping-Entwurf beschreibt Geräte/Datenquellen, gefundene oder manuell
    angelegte Rohpunkte und deren Zuordnung zu kanonischen Mini-EMS-Kanälen. Die Runtime arbeitet weiter mit
    der generierten Config, nicht direkt mit UI-Formularfeldern.
  - **Nutzen:** Die UI kann leicht und fachlich bleiben, während die Runtime stabil und sicher bleibt. Konfiguratoren
    mappen "Netzleistung", "Außentemperatur" oder "Puffer oben" auf Rohpunkte, statt eine komplette technische
    JSON-Struktur verstehen zu müssen.
  - **Betroffen:** `mapping_config.py`, HTTP-API, spätere Dashboard-Konfigurationsseite, Tests, `EMS-Mapping.md`,
    `MINI_EMS_ANLEITUNG.md`.
  - **Aufwand:** M
  - **Risiken:** Das Modell darf nicht zu früh zur generischen Plattform anwachsen. Für Version 1 nur BACnet,
    manuelle Rohpunkte und einfache Preview/Validierung; Modbus-Rohpunkte kommen über den in S4 ergänzten
    Modbus-Adapter hinzu, nicht als eigenes Mapping-Protokoll.
  - **Definition of Done:** Ein Mapping-Entwurf kann Geräte, Rohpunkte und fachliche Zuordnungen aufnehmen;
    `POST /api/config/mapping/preview` liefert einen validierten Runtime-Config-Patch; Fehler/Warnungen sind
    UI-tauglich; bestehende Runtime-Tests bleiben grün.
  - **Erledigt (2026-07-11):** `mapping_config.py` validiert Geräte, Rohpunkte und fachliche Zuordnungen als
    gemeinsamen Entwurf und erzeugt daraus ausschließlich einen geprüften Runtime-Config-Patch. Die
    Inbetriebnahme-UI baut genau dieses Modell aus aktiver Konfiguration, Punktlisten-Import oder Discovery auf;
    Validierungsfehler erscheinen in verständlichem Deutsch und interne IDs bleiben in der technischen Vorschau.

- [x] **S6. Mapping-Aktivierung mit Backup und Audit ergänzen**
  - **Was:** Nach der Preview einen kontrollierten Aktivierungspfad bauen: Mapping-Entwurf speichern, erzeugten
    Config-Patch prüfen, aktive Config sichern, Änderung mit Admin-Recht übernehmen und Neustartbedarf sichtbar
    markieren. Der Entwurf selbst bleibt als nachvollziehbares Inbetriebnahme-Artefakt erhalten.
  - **Nutzen:** Aus dem einfachen UI-Prozess wird ein sicherer Betriebsprozess. Kunden sehen nicht nur "gespeichert",
    sondern welche Zuordnung aktiv ist, wer sie freigegeben hat und ob ein Neustart erforderlich ist.
  - **Betroffen:** Config-API, Backup-/Audit-Ablage, künftige Auth-/Token-Schicht, UI-Freigabeseite, Betriebsdoku.
  - **Aufwand:** M/L
  - **Risiken:** Aktivieren darf nie über einen read-only Viewer-Pfad möglich sein. Secrets, Freigabecode und
    Anlagen-Schreibfreigaben dürfen nicht im Mapping-Entwurf landen.
  - **Definition of Done:** Ungültige Entwürfe können nicht aktiviert werden; jede Aktivierung erzeugt Backup und
    Audit-Eintrag; UI zeigt aktiven Stand, Entwurf, Validierungsstatus und Neustartbedarf getrennt.
  - **Erledigt (2026-07-11):** Schritt 5 heißt in der UI bewusst „Abschließen“: Ein Klick prüft den Entwurf erneut,
    verlangt den lokalen Freigabecode und aktiviert erst danach. Der bisherige Stand wird automatisch gesichert,
    der Mapping-Entwurf unter `mapping_drafts/` erhalten und die Freigabe in `config_audit.jsonl` protokolliert.
    Aktiver Stand, offener Entwurf und ausstehender Neustart bleiben auch nach einem Browser-Neuladen unterscheidbar;
    nach einem Runtime-Neustart verschwindet der Neustarthinweis automatisch.

## Strategische To-do-Linie: Professioneller Protokoll- und Cloud-Ausbau

Diese Linie sammelt sinnvolle Ausbauspuren für den professionellen Rollout. S5/S6 und der lokale sichere
Betriebspfad bilden inzwischen die stabile Grundlage; als nächster kleiner Ausbau ist deshalb S9 read-only gesetzt.
Die übrigen Protokoll- und Cloud-Themen bleiben geparkt, damit das Produkt kein unübersichtlicher Baukasten wird.

- [x] **S7. BACnet-Profi-Stack evaluieren: BACpypes3 und BAC0**
  - **Was:** Prüfen, ob der eigene kleine BACnet-Adapter für größere Standorte durch `BACpypes3` oder den Wrapper
    `BAC0` ergänzt werden sollte. Fokus: viele dynamische BACnet-Punkte, Discovery, Punktlisten-Import,
    `Who-Is`/`I-Am`, `ReadPropertyMultiple`, BBMD/BACnet-Routing und perspektivisch BACnet/SC.
  - **Nutzen:** Der aktuelle Adapter ist gut für wenige bekannte Punkte. Für wiederholbare Inbetriebnahme, dynamische
    Punktlisten und größere GA-Netze kann ein etablierter BACnet-Stack Aufwand und Protokollrisiko senken.
  - **Betroffen:** neuer Discovery-/Importpfad, Mapping-Preview, Tests mit simulierten BACnet-Geräten; der aktuelle
    Produktionsadapter bleibt zunächst stabil.
  - **Aufwand:** M/L
  - **Risiken:** BAC0 erleichtert Routineaufgaben, kann aber weniger granular sein als direkter BACpypes3-Zugriff.
    `ReadPropertyMultiple` darf nicht blind für "alles auf einmal" genutzt werden; MS/TP, Segmentierung und Geräte-
    Grenzen müssen Last und Timeouts begrenzen. Discovery erzeugt nur Rohpunkt-Kandidaten, keine automatisch
    freigegebenen EMS-Kanäle.
  - **Definition of Done:** Es gibt eine kurze technische Entscheidung: eigener Adapter weiterführen, BACpypes3 direkt
    nutzen oder BAC0 für Discovery/Import einsetzen; inklusive Teststrategie und klarer Grenze zu Schreibpfaden.
  - **Stand (2026-07-07):** Entscheidung bestätigt. Produktiver Lese-/Schreibpfad bleibt beim eigenen Adapter
    (`bacnet.py`); für die Discovery-/Import-Vorstufe (S8) wird `BACpypes3` **direkt** als getrennter,
    **read-only** Werkzeugpfad genutzt (MIT, eine Abhängigkeit, direkte Broadcast-/RPM-Lastkontrolle) statt `BAC0`
    (LGPL-3.0, zwei Abhängigkeiten, verdeckte Last). Fremd-Stack erzeugt nur Rohpunkt-**Kandidaten** für den
    Mapping-Entwurf (S5), niemals Kanäle oder Writes. Ist-Analyse, Optionsvergleich, RPM-/Broadcast-Lastregeln und
    Teststrategie in `BACNET_STACK_EVAL.md`.

- [x] **S8. BACnet-Discovery und Punktlisten-Import als Mapping-Vorstufe bauen**
  - **Was:** Einen späteren Importpfad entwerfen: erreichbare Controller finden, BACnet-Objekte/Punktlisten einlesen,
    Kandidaten mit Name, Objekt, Instanz, Einheit und aktueller Probe darstellen und daraus einen Mapping-Entwurf
    erzeugen. Zweiter gleichwertiger Einstieg: vorhandene Datenpunktlisten als Excel-/CSV-Datei hochladen,
    relevante Spalten erkennen (Name, Objekt-/Instanzkennung, Einheit, Kommentar, Zugriff/Schreibpunkt-Hinweis),
    daraus Rohpunkt-Kandidaten erzeugen und diese im selben Mapping-Flow sortieren, filtern, zuordnen und testen.
  - **Nutzen:** Inbetriebnahme wird schneller und weniger fehleranfällig, ohne dass die Runtime selbst automatisch
    fremde Punkte übernimmt.
  - **Betroffen:** Mapping-UI, `mapping_config.py`, neue Diagnose-/Discovery-API, Excel-/CSV-Import,
    `BACpypes3` als getrennter read-only Discovery-Pfad.
  - **Aufwand:** L
  - **Risiken:** Broadcasts und Objektlisten können GA-Netze belasten. Discovery muss read-only bleiben und darf keine
    Schreibpunkte aktivieren. Gefundene Punkte sind nur Kandidaten; fachliche Zuordnung, Plausibilität und
    Betreiberfreigabe bleiben Pflicht.
  - **Definition of Done:** Discovery-Lauf oder Excel-/CSV-Upload erzeugt nur einen Entwurf mit Rohpunkten;
    Aktivierung läuft weiterhin über S5/S6 mit Validierung, Backup und Audit.
  - **Stand (2026-07-07):** Erledigt als erster sicherer Import-/Discovery-Schnitt. `pointlist_import.py`
    importiert CSV/TSV/XLSX-Datenpunktlisten in Rohpunkt-Kandidaten und Mapping-Entwürfe; `bacnet_discovery.py`
    kapselt den optionalen BACpypes3-Pfad als read-only Preview mit Fake-testbarer Anwendungsschnittstelle. Neue
    API-Endpunkte: `POST /api/config/pointlist/import` und `POST /api/config/discovery/bacnet/preview`.
    Aktivierung bleibt ausschließlich über `POST /api/config/mapping/preview|activate` mit Validierung, Backup und
    Audit. Ein echter Standort-Discovery-Lauf braucht weiterhin MSR-/Betreiberfreigabe und optional installierten
    BACpypes3-Werkzeugpfad.

- [ ] **S9. Northbound Outbox und MQTT/Cloud-Export read-only vorbereiten**
  - **Was:** Einen Exportpfad definieren, der normalisierte Mini-EMS-Werte aus Zeitreihe/Health in eine lokale Outbox
    schreibt und später per MQTT oder HTTP an einen Cloud-/Business-Dienst sendet. Start read-only: keine Cloud-
    Commands, keine Remote-Writes.
  - **Nutzen:** Mini EMS kann echte Standortdaten für Portfolioanalyse, Reports, Monitoring oder Business OS liefern,
    ohne die lokale Anlagensteuerung von der Cloud abhängig zu machen.
  - **Betroffen:** Runtime-Datenmodell, lokale Outbox, Exporter-Prozess, Zertifikate/Secrets, Betriebsdoku,
    später Cloud-Broker oder API.
  - **Aufwand:** M/L
  - **Risiken:** Keine direkte Freigabe der Anlagen-API ins Internet. TLS/mTLS, Zertifikatsrotation, Retry/Backoff,
    Offline-Pufferung, Duplikatvermeidung und Datenminimierung müssen geplant werden. Der Export darf keine
    Geheimnisse, Freigabecodes oder unnötigen personenbezogenen Daten enthalten.
  - **Definition of Done:** Ein read-only Exportmodell beschreibt Payload, Topic/API, Authentifizierung, Offline-
    Verhalten und Replay-Regeln; lokale Steuerung läuft bei Cloud-Ausfall unverändert weiter.

- [ ] **S10. M-Bus und Wireless M-Bus als langsame Zähler-Integrationen prüfen**
  - **Was:** Für Wärme-, Wasser-, Gas- oder Stromzähler einen M-Bus-/wM-Bus-Pfad prüfen, z. B. über `libmbus`,
    `wmbusmeters` oder einen separaten Gateway-/MQTT-Wrapper.
  - **Nutzen:** Viele Energie- und Wärmeberichte brauchen Zählerwerte, die nicht über BACnet/Modbus vorliegen.
    M-Bus ist dafür nützlich, aber eher für Monitoring und Bilanzierung als für schnelle Regelung.
  - **Betroffen:** Mapping-Vorlagen, Import-/Adapterkonzept, Zeitreihe, Reports.
  - **Aufwand:** M
  - **Risiken:** M-Bus-Datensätze sind gerätespezifisch; Record-Position, Einheit, Skalierung und Zählerstand müssen
    immer gegen reale Ausgaben geprüft werden. Keine Abhängigkeit schneller Steuerlogik von langsamen Zählerzyklen.
  - **Definition of Done:** Es gibt eine Entscheidung, ob Mini EMS direkt liest oder einen externen M-Bus-zu-MQTT/HTTP-
    Gateway-Pfad nutzt; inklusive Beispiel-Mapping und Qualitätsregeln.

- [ ] **S11. Haystack-/Brick-/REC-kompatiblen Semantik-Export vorbereiten**
  - **Was:** Das interne Modell (`Canonical Channel`, `equipment_id`, `role`, `unit`, `tags`, Standortbezug) so
    formulieren, dass später ein Export nach Project Haystack, Brick Schema oder RealEstateCore möglich ist.
  - **Nutzen:** Semantik wird anschlussfähig für größere Gebäudeportfolios, Partnerplattformen, Wissensgraphen und
    wiederverwendbare Algorithmen.
  - **Betroffen:** Mapping-Modell, Gerätetemplates, Dokumentation, spätere Northbound API.
  - **Aufwand:** M
  - **Risiken:** Haystack/Brick/REC nicht als sofortige Runtime-Abhängigkeit einführen. Für den aktuellen
    Mini-EMS-Stand reicht ein kleines internes Modell; externe Ontologien bleiben Export-/Integrationsziel.
  - **Definition of Done:** Für die wichtigsten Kanal- und Gerätetypen gibt es eine Mapping-Tabelle von Mini-EMS-
    Feldern zu Haystack-Tags, Brick-Klassen/Beziehungen und REC-Entitäten/Relationen, ohne die Runtime umzubauen.

- [ ] **S12. Remote-Command-Pfad erst nach read-only Export separat bewerten**
  - **Was:** Erst nach stabilem read-only Export prüfen, ob Cloud- oder Business-Systeme Befehle, Fahrpläne oder
    Optimierungsvorschläge an Mini EMS senden dürfen.
  - **Nutzen:** Hält die klare Sicherheitsgrenze: Datenexport ist nicht automatisch Fernsteuerung.
  - **Betroffen:** Safe Write Path, Rollen/Rechte, Betreiberfreigabe, Audit, Fallback, Kommunikationssicherheit.
  - **Aufwand:** L
  - **Risiken:** Remote-Commands sind eine andere Risikoklasse als Monitoring. Jeder Befehl braucht Authentifizierung,
    Autorisierung, Plausibilisierung, lokale Freigabe, Audit, Fallback und ggf. manuelle Betreiberabnahme.
  - **Definition of Done:** Vor Code gibt es ein Sicherheits- und Betriebsdokument, das Remote-Commands entweder
    explizit ausschließt oder mit klaren Grenzen, Tests und Betreiberfreigaben erlaubt.

## Strategische To-do-Linie: Cloud Data Pipeline und semantisches Mapping

Diese Linie beschreibt die spätere Cloud-Seite hinter dem read-only Export aus S9. Für Mini EMS bleibt zuerst
wichtig: stabile Edge-Daten, klare Payloads, lokale Outbox und semantisch saubere Kanäle. MQTT-Broker, Kafka,
Schema Registry oder Portfolio-Semantik werden erst relevant, wenn mehrere Standorte zuverlässig Daten liefern
und diese Daten von Reporting, Analyse, Regeln oder ML-Jobs parallel genutzt werden.

- [ ] **C1. Northbound Payload-Vertrag versionieren**
  - **Was:** Ein stabiles Exportformat definieren, bevor ein Cloud-Broker ausgewählt wird: `edge_device_id`,
    Standort-/Anlagenbezug, `channel_id`, `equipment_id`, Zeitstempel, Wert, Einheit, Qualität, Quelle,
    Sequenznummer, Mapping-Version und Payload-Schema-Version.
  - **Nutzen:** Cloud-Ingestion, Historie, Semantik und spätere Replays bleiben nutzbar, auch wenn sich
    Protokolladapter oder Mapping-Details ändern.
  - **Betroffen:** Outbox aus S9, `EDGE_INTEGRATION_CONTRACT.md`, spätere Cloud-API/MQTT-Topics, Tests.
  - **Aufwand:** M
  - **Risiken:** Payload darf nicht rohe MSR-Kryptik nach oben durchreichen. Rohadresse kann im technischen Anhang
    enthalten sein, aber die primäre Bedeutung muss über kanonische Kanäle und Semantik kommen.
  - **Definition of Done:** Es gibt ein versioniertes JSON-Schema oder vergleichbares Datenvertragsdokument mit
    Beispielpayloads für Messwert, Health/Event und Mapping-Änderung.

- [ ] **C2. MQTT-Broker-Schicht nach Skalierungspfad bewerten**
  - **Was:** Für erste Piloten reicht ein einfacher read-only Export oder ein kleiner Broker. Für Flottenbetrieb
    müssen Enterprise-Broker wie EMQX oder HiveMQ gegen Mosquitto, Managed IoT-Plattformen und Betriebsaufwand
    bewertet werden.
  - **Nutzen:** Mini EMS springt nicht zu früh in Enterprise-Infrastruktur, hat aber eine klare Spur für TLS,
    MQTT v5, Sessions, Topics, Zertifikate, Clustering und horizontale Skalierung.
  - **Betroffen:** Cloud-Architektur, Zertifikats-/Device-Identity-Konzept, Topic-Namensraum, Betriebskosten.
  - **Aufwand:** M
  - **Risiken:** Brokerwahl löst keine Semantik- oder Datenqualitätsprobleme. EMQX/HiveMQ sind für größere IoT-
    Flotten plausibel; für einen einzelnen Standort wäre das Overengineering. Mosquitto bleibt als simpler
    Test-/Pilotbroker denkbar, aber nicht als HA-Flottenziel.
  - **Definition of Done:** Entscheidungsmatrix mit Pilot-, Portfolio- und Enterprise-Pfad; inklusive TLS/mTLS,
    Zertifikatsrotation, QoS, Retained Messages, Session Expiry und Betriebsmodell.

- [ ] **C3. Kafka/Event-Log erst für Replay- und Multi-Consumer-Bedarf einplanen**
  - **Was:** Kafka oder ein vergleichbarer Event-Streaming-Layer wird erst bewertet, wenn mehrere unabhängige
    Konsumenten dieselben Gebäudedaten brauchen: Zeitreihenspeicher, Reporting, Rule Engine, ML-Training,
    Alerting und Abrechnung.
  - **Nutzen:** Entkoppelt Ingestion-Rate von Verarbeitung, erlaubt Replays historischer Datenströme und macht
    spätere Algorithmus-Iterationen reproduzierbarer.
  - **Betroffen:** Cloud-Ingestion, Speicherstrategie, Schema Registry, Consumer-Gruppen, Retention, Reprocessing.
  - **Aufwand:** L
  - **Risiken:** Kafka ist kein Ersatz für Zeitreihendatenbank, Semantik oder Data Quality. Falsche Partitionierung,
    fehlende Schemas oder ungeklärte Retention machen Replay später wertlos.
  - **Definition of Done:** Vor Umsetzung gibt es einen Datenflussplan: MQTT/Broker → Ingestion → Event Log →
    Zeitreihe/Semantik/Analytics, inklusive Topic-/Partition-Key, Retention, Schema-Evolution und Reprocessing-Regeln.

- [ ] **C4. Semantische Cloud-Klassifikation als eigenen Dienst denken**
  - **Was:** Cloud-seitig einen Mapping-/Semantikdienst vorbereiten, der Edge-Kanäle, Rohpunkte, Equipment,
    Standortstruktur, Einheiten, Qualität und Rollen zusammenführt. Haystack, Brick und RealEstateCore bleiben
    mögliche Export- oder Integrationsformate, nicht zwingend die Edge-Runtime.
  - **Nutzen:** Kryptische MSR-Namen werden portfoliofähig. Reports, Regeln und ML-Jobs arbeiten auf
    `meter.grid.active_power_kw`, `heat.buffer.top_temperature_c` oder Equipment-Rollen statt auf `AV:300`.
  - **Betroffen:** Mapping-Modell, `S11`, Cloud-Datenmodell, Portfolio-/Mandantenstruktur, spätere Admin-UI.
  - **Aufwand:** L
  - **Risiken:** Automatische Klassifikation darf keine ungeprüfte Wahrheit erzeugen. Semantik braucht Versionierung,
    Prüfstatus, Quelle und Betreiber-/Konfiguratorfreigabe.
  - **Definition of Done:** Es gibt ein Cloud-Semantikmodell mit Status je Kanal: importiert, vorgeschlagen,
    geprüft, aktiv, veraltet; Änderungen sind versioniert und auf Zeitreihendaten zurückverfolgbar.

- [ ] **C5. Zeitreihen- und Speicherstrategie getrennt vom Event-Log wählen**
  - **Was:** Festlegen, welche Daten im Event Log, in einer Zeitreihendatenbank, in Objekt-/Parquet-Speicher und
    in relationalen Metadaten liegen. Edge-SQLite bleibt lokale Betriebs- und Diagnosehistorie, nicht das
    Portfolio-Backend.
  - **Nutzen:** Große Datenmengen bleiben abfragbar, kosteneffizient und auditierbar. Trainingsdaten, Reports und
    Betreiberansichten bekommen jeweils passende Speicherformen.
  - **Betroffen:** Cloud-Backend, Retention, Downsampling/Rollups, Datenschutz, Exportformate.
  - **Aufwand:** L
  - **Risiken:** Alles in Kafka oder alles in einer Datenbank zu halten, vermischt Zwecke. Zeitreihen brauchen
    andere Abfrage- und Retention-Regeln als Semantik, Audit oder ML-Rohdaten.
  - **Definition of Done:** Speicherklassen sind definiert: Raw events, normalisierte Zeitreihen, Rollups,
    semantische Metadaten, Audit und ML-Trainingssnapshots.

- [ ] **C6. TSDB-Auswahl für Portfolio-Zeitreihen evaluieren**
  - **Was:** Für die Cloud-/Portfolio-Schicht TimescaleDB, VictoriaMetrics und InfluxDB 3 anhand echter Mini-EMS-
    Workloads bewerten: Ingestion-Rate, Kardinalität, Abfragemuster, Retention, Downsampling, Kosten, Betriebsmodell
    und SQL-/Analytics-Ökosystem.
  - **Nutzen:** Verhindert eine frühe Datenbankentscheidung nach Marketingclaims. Die richtige TSDB hängt davon ab,
    ob wir eher SQL-nahe Reports, massive Sensor-Metriken, analytische Parquet-/Arrow-Abfragen oder ML-Replays
    priorisieren.
  - **Betroffen:** Cloud-Backend, Zeitreihenmodell, Reporting, Portfolioanalyse, ML-/Forecast-Pipeline,
    DevOps/Betriebskosten.
  - **Aufwand:** M/L
  - **Risiken:** TimescaleDB ist attraktiv, wenn PostgreSQL/SQL, relationale Metadaten und Reportabfragen zentral sind;
    bei sehr hoher Serienkardinalität und Metrik-Workloads können VictoriaMetrics oder InfluxDB 3 besser passen.
    Benchmark-Ergebnisse müssen mit Mini-EMS-ähnlichen Daten entstehen: viele Standorte, viele Kanäle, gemischte
    Abfragen, Quality-Felder, Rollups und Semantik-Joins.
  - **Definition of Done:** Es gibt eine Entscheidungsmatrix und einen kleinen reproduzierbaren Benchmark mit
    mindestens drei Workloads: aktueller Standortreport, Portfolio-Dashboard und Langzeitabfrage über verdichtete Daten.

- [ ] **C7. Retention- und Downsampling-Policy fachlich definieren**
  - **Was:** Festlegen, wie lange Rohwerte, 1-Minuten-/5-Minuten-/15-Minuten-/Stunden-Rollups, Tageswerte,
    Ereignisse und Audit-Daten aufbewahrt werden. Dabei muss fachlich geklärt werden, welche Aggregationen
    zulässig sind: Durchschnitt, Min/Max, letzter Wert, Delta bei Zählerständen, Qualitätsanteil und Anzahl Samples.
  - **Nutzen:** Speicher bleibt bezahlbar, ohne Reports, Abrechnung, Anlagenanalyse oder ML-Training wertlos zu
    machen. Downsampling wird nicht nur technische Datendünnung, sondern fachlich korrekte Verdichtung.
  - **Betroffen:** lokale Rollups, Cloud-TSDB, Report-API, Datenexport, Datenschutz/Retention, ML-Snapshots.
  - **Aufwand:** M
  - **Risiken:** Einfache Downsampling-Strategien wie "erster Wert pro Intervall" können für Temperaturen oder
    Zustände brauchbar sein, aber für Energiezähler, Leistungsspitzen, Sperrzeiten oder Qualitätsmetriken falsch.
    Zähler brauchen Delta-/Reset-Logik; Peak-Shaving braucht Min/Max bzw. Spitzenwerte; Data Quality muss in
    Rollups erhalten bleiben.
  - **Definition of Done:** Pro Kanaltyp ist definiert, welche Verdichtung erlaubt ist und welche Rohdaten wie lange
    bleiben. Die Policy enthält Beispiele für Temperatur, Leistung, Energiezähler, Status/Lockout und Events.

- [ ] **C8. Semantik-Speicherform entscheiden: RDF/Graph vs. relationale Projektion**
  - **Was:** Für die Cloud-/Portfolio-Schicht entscheiden, ob der semantische Gebäudemodell-Teil als echter
    RDF-/Property-Graph, als relationale Tabellenstruktur, als JSONB-Metadaten an Zeitreihen oder als hybride
    Projektion betrieben wird.
  - **Nutzen:** Brick/REC beschreiben Beziehungen wie Equipment, Location, Point, `hasPoint`, `feeds` oder
    `locatedIn` sauber als Graph. Reports, Dashboards und Zeitreihenabfragen brauchen aber oft schnelle Joins
    gegen Standort-, Equipment- und Kanalmetadaten. Die Speicherform muss beide Welten bewusst verbinden.
  - **Betroffen:** Cloud-Semantikdienst, TSDB-Auswahl aus C6, Mapping-Versionierung, Portfolio-Queries,
    Partner-API, Datenexport.
  - **Aufwand:** M/L
  - **Risiken:** Ein reiner Graph kann für Standardreports unnötig komplex werden; reine JSONB-Metadaten verlieren
    schnell Beziehungslogik, Validierung und Ontologie-Kompatibilität. Die erste Umsetzung sollte deshalb eine
    kleine interne Modellquelle mit exportierbaren Brick-/REC-Projektionen bevorzugen.
  - **Definition of Done:** Es gibt eine Architekturentscheidung mit Beispielqueries: "alle Punkte eines Geräts",
    "alle Vorlauftemperaturen eines Heizkreises", "alle Kanäle eines Raums/Geschosses" und "alle Zeitreihen für
    einen Portfolio-Report"; inklusive Entscheidung, welche Daten in Graph, SQL/JSONB und TSDB liegen.

- [ ] **C9. Auto-Mapping als Assistenzsystem mit Human-in-the-loop vorbereiten**
  - **Was:** Einen späteren Auto-Mapping-Prozess entwerfen, der Rohpunktnamen, BACnet-Objekttypen, Units,
    Read/Write-Properties, Zeitreihenmuster, Standortstruktur und bestehende Templates zu semantischen Kandidaten
    verdichtet. NLP/LLM-/Transformer-Modelle dürfen Vorschläge machen, aktivieren aber keine EMS-Kanäle allein.
  - **Nutzen:** Tausende kryptische MSR-Punkte werden schneller onboardingfähig, ohne fachliche Prüfung zu ersetzen.
    Auto-Mapping hilft besonders bei wiederkehrenden Namensmustern, Geräteklassen und Standort-Templates.
  - **Betroffen:** Discovery/Import aus S8, Mapping-Entwurfsmodell aus S5, Semantikdienst aus C4, UX22,
    Trainings-/Evaluationsdaten, Audit.
  - **Aufwand:** L
  - **Risiken:** Hohe F1-Werte aus einzelnen Studien oder Vendor-Demos sind nicht automatisch auf unsere Gebäude,
    Namenskonventionen und Gewerke übertragbar. Schreibpunkte, Safety-relevante Kanäle und Abrechnungs-/Nachweiswerte
    brauchen strengere Freigabe als reine Monitoringpunkte.
  - **Definition of Done:** Auto-Mapping liefert pro Kandidat Klasse, Equipment/Location-Bezug, Konfidenz,
    Begründungsmerkmale und Prüfstatus. Aktivierung erfolgt nur über S6 mit Audit; unklare oder sicherheitsrelevante
    Punkte bleiben blockiert, bis ein Mensch sie freigibt.

## Strategische To-do-Linie: Professioneller Write-Back und Anlagen-Safety

Der Mini-EMS-Schreibpfad ist bewusst eng: wenige BACnet-Ausgänge, validierte BACnet-Priorität, ACK/Readback,
Criticality, Safe Mode und keine echten Writes in der lokalen Simulation. Für prädiktive Regelung, Cloud-Commands
oder größere Eingriffe reicht das langfristig nicht. Dann muss Write-Back als eigener Sicherheitsvertrag mit der
MSR/DDC verstanden werden, nicht nur als `WriteProperty` aus dem Edge-Code.

- [x] **S13. BACnet-Priority-Array-Strategie pro Schreibpunkt definieren**
  - **Was:** Die aktuell feste BACnet-Schreibpriorität `14` durch eine explizite, validierte Schreibpunkt-Strategie
    ersetzen oder zumindest dokumentiert bestätigen. Pro Ausgangspunkt wird festgelegt: genutzte Priorität,
    Bedeutung, zulässiger Wertebereich, bestätigte Schutzprioritäten darüber und Betreiberfreigabe.
  - **Nutzen:** Mini EMS kann lokale Sicherheitsketten nicht aus Versehen übersteuern. Die MSR behält Vorrang für
    Frostschutz, Rauch-/Brandfall, Mindestlaufzeiten, lokale Verriegelungen und DDC-interne Schutzlogik.
  - **Betroffen:** `bacnet.py` (`WRITE_PRIORITY`), `config.py`, `EDGE_INTEGRATION_CONTRACT.md`, Tests,
    Inbetriebnahme-/MSR-Abnahme.
  - **Aufwand:** M
  - **Risiken:** Priorität `8` ("Manual Operator") ist in vielen BACnet-Konzepten plausibel, aber nicht automatisch
    richtig für jeden Standort. Prioritäten `1`, `2` und andere hardwarenahe Schutzebenen müssen tabu bleiben.
    Die Wahl muss mit der MSR-Programmierung abgestimmt werden, nicht nur im EMS-Code.
  - **Definition of Done:** Jeder beschreibbare BACnet-Punkt hat eine dokumentierte Priorität; reservierte
    Schutzprioritäten werden durch Config-Validierung verhindert; Tests prüfen die erzeugten BACnet-Pakete und
    die Dokumentation beschreibt, welche lokale Logik Mini EMS niemals übersteuert.
  - **Stand (2026-07-09): Softwareseitig umgesetzt.** `outputs.*.write_priority` wird geladen, Default bleibt
    kompatibel `14`, reservierte Schutzprioritäten `1`, `2`, `5` und `6` werden validiert abgelehnt, und
    `BacnetAdapter` erzeugt die Write-Pakete mit der punktbezogenen Priorität. Tests prüfen Config-Validierung
    und erzeugte BACnet-Pakete.

- [x] **S14. Relinquish/Null-Schreibpfad für BACnet-Prioritäten entwerfen**
  - **Was:** Einen sicheren Weg definieren, wie Mini EMS seine eigene BACnet-Priorität wieder freigibt, also auf
    derselben Prioritätsstufe `NULL` schreibt und damit auf den nächsten aktiven Wert oder `Relinquish_Default`
    zurückfallen lässt.
  - **Nutzen:** Ein EMS-Eingriff bleibt nicht dauerhaft im Priority Array hängen, wenn die Prognose endet, ein
    Operator zurück auf lokale Regelung will oder eine Fallback-Situation sauber aufgelöst werden soll.
  - **Betroffen:** BACnet-Write-Encoder, Output-State, Safe-Mode-/Shutdown-Verhalten, Audit-Log, MSR-Abnahmetest.
  - **Aufwand:** M/L
  - **Risiken:** Relinquish ist selbst ein Write und darf nur auf der eigenen, freigegebenen Priorität passieren.
    Ein falscher Null-Write kann gewünschte lokale Betriebszustände ändern. Vor Umsetzung muss klar sein, welche
    DDC-Punkte überhaupt Priority Array und `Relinquish_Default` korrekt nutzen.
  - **Definition of Done:** Für konfigurierte Schreibpunkte kann Mini EMS seine eigene Priorität kontrolliert
    freigeben; Freigabe wird bestätigt, geloggt und getestet; Punkte ohne geprüften Relinquish-Mechanismus bleiben
    ausgeschlossen.
  - **Stand (2026-07-09): Softwarepfad umgesetzt, operativer Einsatz bleibt explizit.**
    `relinquish_with_confirmation()` schreibt BACnet `NULL` auf der eigenen `write_priority`; Simulation und
    Modbus spiegeln die Schutzgrenze. Ohne `relinquish_enabled=true` wird der Freigabepfad abgelehnt. Die
    automatische Safe-Mode-/Shutdown-Nutzung ist bewusst noch nicht aktiviert und muss pro MSR-Freigabe entschieden
    werden.

- [ ] **S15. Edge-DDC-Heartbeat mit DDC-seitigem Fallback prüfen**
  - **Was:** Einen dedizierten BACnet-Heartbeat-Punkt und eine dazugehörige DDC-Watchdog-Logik entwerfen: Mini EMS
    aktualisiert zyklisch einen Counter/Timestamp; die DDC erkennt Timeout und fällt lokal auf Notlauf, lokale
    Heizkurven oder Basis-Sollwerte zurück.
  - **Nutzen:** Der Anlagen-Fallback hängt nicht vom Edge-Prozess ab. Wenn IPC, Netzwerk, VPN oder Cloud ausfallen,
    kann die DDC autark entscheiden und Mini-EMS-Einflüsse zurücknehmen.
  - **Betroffen:** zusätzlicher BACnet-Schreibpunkt, DDC-/GLT-Programmierung, Betriebskonzept, Tests am Standort,
    `MINI_EMS_ANLEITUNG.md`.
  - **Aufwand:** L
  - **Risiken:** Das ist kein reines Python-Feature. Es braucht MSR-Zugriff, Betreiberfreigabe und einen echten
    Abnahmetest. Der Heartbeat darf nicht mit Cloud-Erreichbarkeit verwechselt werden: lokale Edge kann gesund sein,
    auch wenn Cloud/Internet ausfällt.
  - **Definition of Done:** DDC-Timeout wird in Simulation bzw. Testanlage nachgewiesen; bei ausbleibendem Heartbeat
    entfernt die lokale Steuerung Mini-EMS-Einfluss oder ignoriert ihn und läuft auf definierten lokalen Fallbacks.
  - **Stand (2026-07-09): Software-Vorstufe umgesetzt, Standortabnahme offen.** Optionales
    `ddc_heartbeat.enabled` ergänzt einen `system.edge_heartbeat`-AV-Counter als Ausgangskanal. Mini EMS schreibt
    diesen Counter am Zyklusanfang vor Preis-/Cloud-Logik; ein unbestätigter Heartbeat stoppt den restlichen
    Anlagen-Schreibpfad im selben Zyklus. Unit-Tests decken Reihenfolge und Fehlerverhalten ab. Offen bleibt der
    echte MSR-/DDC-Test: Timeout erkennen und lokalen Fallback an der Anlage nachweisen.

- [ ] **S16. Zeitlich begrenzte Write-Back-Leases für prädiktive Regelung einführen**
  - **Was:** Jeder prädiktive Eingriff bekommt eine Laufzeit, Gültigkeitsbedingung und Rückfallregel. Beispiel:
    "Sollwertverschiebung gültig bis 15:30, nur wenn Messwerte frisch sind, nur innerhalb Komfort-/Anlagengrenzen,
    danach Relinquish oder lokaler Basiswert."
  - **Nutzen:** Prognosefehler, alte Daten oder Kommunikationsabbrüche hinterlassen keine unbegrenzten Eingriffe in
    der Anlage. Write-Back wird von einem Zustand zu einem befristeten, prüfbaren Auftrag.
  - **Betroffen:** Controller-Logik, Output-State, Audit, UI-Status, Safe Write Path, ggf. Northbound Commands.
  - **Aufwand:** L
  - **Risiken:** Leases dürfen nicht nur in der Cloud liegen; die lokale Edge muss sie durchsetzen können. Für echte
    Anlagen braucht jeder Lease-Typ klare Grenzen, Abbruchbedingungen und Betreiberfreigabe.
  - **Definition of Done:** Schreibende Optimierungen laufen nur als befristete, lokal prüfbare Aufträge; abgelaufene
    oder ungültige Aufträge werden nicht weitergeschrieben und erzeugen einen nachvollziehbaren Fallback-Status.

## Strategische To-do-Linie: Geschütztes Kundenhosting

- [x] **H1. Zielbild und Sicherheitsgrenze festlegen**
  - **Was:** Festlegen, dass Mini EMS auf kundeneigener IPC-Hardware laufen kann, aber nicht als frei einsehbarer
    Entwicklerordner ausgeliefert wird. Zugriff auf UI und API bleibt auf Kundennetz, VPN oder Secomea beschränkt.
  - **Nutzen:** Klärt die Erwartung: Es geht nicht um absolute Geheimhaltung gegen Administratoren, sondern um professionellen
    Betrieb ohne offenen Source-Code-Checkout und ohne öffentlich erreichbare Anlagen-API.
  - **Betroffen:** `README.md`, `MINI_EMS_ANLEITUNG.md`, spätere Installations-/Betriebsdoku.
  - **Aufwand:** S
  - **Risiken:** Keine Sicherheitsversprechen formulieren, die auf einer kundeneigenen IPC mit Admin-Zugriff nicht haltbar sind.
  - **Definition of Done:** Es ist dokumentiert, wer UI, Runtime-Dateien, Standortkonfiguration, Logs und Betriebsdaten sehen darf.
  - **Erledigt:** Zielbild, Sichtbarkeits-/Änderungsmatrix (normaler Windows-Nutzer, Viewer, Operator, Admin – konsistent
    zum UX-Rollenmodell) und die ehrliche Risiko-Abgrenzung stehen in `HOSTING_SICHERHEIT.md`, Teil 1; querverwiesen aus
    `README.md` und `MINI_EMS_ANLEITUNG.md`.

- [x] **H2. Mini EMS als Release-Paket statt Git-Checkout ausliefern**
  - **Was:** Die Kunden-IPC bekommt kein vollständiges Repository mehr, sondern ein versioniertes Release-Paket, z. B.
    `mini_ems.exe`, `dashboard/`, Release-Launcher, Checksums und Versionsdatei; `site.sqlite` bleibt als externe
    Standortdatenbank außerhalb des Pakets erhalten.
  - **Nutzen:** Normale Nutzer können nicht einfach den gesamten Python-Code lesen. Updates werden kontrollierter und
    professioneller als ein manueller Git-Ordner auf der IPC.
  - **Betroffen:** Packaging-Konzept, `run_mini_ems_release.cmd`, `windows/install_task.ps1`, Release-Artefakt,
    Standortkonfiguration.
  - **Aufwand:** M
  - **Risiken:** PyInstaller ist einfacher, aber leichter extrahierbar; Nuitka ist für weniger beiläufige Code-Einsicht
    geeigneter, aber aufwendiger. Standortdaten dürfen nie in ein hart kodiertes Paket verschwinden.
  - **Definition of Done:** Eine Test-IPC kann Mini EMS ohne Git-Repo mit externem `--site-dir` und geplantem
    Windows-Task starten.
  - **Entscheidung (Nutzer, wörtlich):** *"Release-Paket, initial PyInstaller, später Nuitka-kompatibel"*.
    Umsetzung: One-Dir-Release (ausführbares Artefakt + `run_mini_ems_release.cmd` + `dashboard/` +
    `mini_ems_runtime/templates/`, optional `sim/`, plus `VERSION`, `SHA256SUMS`, `RELEASE_HINWEISE.md`) über `packaging/`
    (`mini_ems.spec`, `build_release.ps1` für Windows/IPC, `build_release.sh` für lokale Verifikation).
    Standortdaten und Betriebsdaten sind nie Teil des Pakets; der Betriebspfad verwendet den externen
    Standortordner mit `site.sqlite` plus geplantem Windows-Task. Die Frozen-Pfadauflösung ist bewusst generisch gehalten (Ressourcen neben
    dem Executable, kein `sys._MEIPASS` im Runtime-Code), damit sie ohne Umbau auch für Nuitka trägt.
  - **Stand:** Packaging-Tooling, Release-Launcher (`run_mini_ems_release.cmd`), `install_task.ps1 -Mode release`
    und die minimale Frozen-Pfadauflösung (`mini_ems_runtime/resources.py`, eine Zeile in `app.py`) liegen vor; der
    lokale Build-Nachweis auf macOS ist erbracht (PyInstaller-Build, `--once`-Zyklus schreibt `health.json`,
    `--loop` liefert `/api/status` und `/dashboard`, alle Mini-EMS-Tests grün). Details: `packaging/README.md`;
    aufgelöste Betriebsschritte: `UPDATE_WARTUNG.md`.
  - **Nachweis auf der realen Pilot-IPC erbracht (2026-07-07):** Der Windows-Build (PyInstaller, `version=2026.07`,
    `build_date=2026-07-07T08:57:37Z`) liegt unter `C:\Program Files\MiniEMS` und ist per `SHA256SUMS` verifiziert
    (40/40 Dateien unverändert). Der Listener auf `192.168.244.10:8090` ist
    `C:\Program Files\MiniEMS\mini_ems.exe --config C:\ProgramData\MiniEMS\config.json --loop`, gestartet über den
    geplanten Task `MiniEmsPoCRelease` (SYSTEM, Trigger Systemstart) – kein Python, kein Git-Checkout als
    Laufzeitbasis. Betriebsdaten (`health.json` status=healthy/live, `mini_ems.log`, SQLite) werden laufend unter
    `C:\ProgramData\MiniEMS` fortgeschrieben; die alten Runtime-Dateien im Checkout sind seit dem Umschalten
    eingefroren. `/dashboard` und `/api/status` antworten mit HTTP 200 und frischen Daten. Damit ist der DoD (Start
    ohne Git-Repo, Betriebspfad `config.json` + geplanter Task) auf der realen IPC erfüllt. Der konkurrierende
    Alt-Autostart wurde entschärft (siehe „Autostart-Bereinigung" unten). **Restpunkte (Betriebs-Hygiene, keine
    H2-Lücken):** (1) das laufende Release ist ein dirty-Build (`git_commit=be4d81b8ad4d+dirty`) – nächster Build aus
    committetem Stand für ein reproduzierbares Release; (2) die API hat keinen Versions-Endpunkt, Version nur über die
    `VERSION`-Datei belegbar (optionales Follow-up).
  - **Stand (2026-07-09): Version zur Laufzeit sichtbar, Release-Ablauf reproduzierbar.** Der Restpunkt (2) ist
    aufgelöst: Die Runtime liest die `VERSION`-Datei beim Start (`mini_ems_runtime/resources.py`,
    `read_app_version`) und stellt sie additiv unter `/api/status` als `app_version`
    (`version`/`git_commit`/`build_date`) bereit – kein neuer Endpunkt. Die Systemstatus-Seite des Dashboards
    zeigt eine dezente Zeile "Softwareversion"; im Git-Betrieb erscheint `dev`. Die Build-Skripte verlangen die
    Version jetzt als Pflicht-Parameter (Schema `JJJJ.MM.n`), es gibt eine `CHANGELOG.md` (Repo-Pflege) mit
    Build-Schnappschuss ins Paket; der präzise "Release erstellen"-Ablauf steht in `packaging/README.md`.
  - **Autostart-Bereinigung (2026-07-07):** Auf der IPC existierten noch drei konkurrierende Alt-Autostarts. Der alte
    Dev-Task `MiniEmsPoC` (Boot-Trigger auf den Git-Checkout) wäre beim Reboot mit dem Release-Task um Port 8090
    kollidiert; er ist jetzt **deaktiviert** (nicht gelöscht). Der Legacy-Dienst `MiniEmsPoC` (Autostart, nie
    lauffähig, Fehler 1053) steht auf **Manual**. Der überholte Task `MiniEmsDashboardProxy` (zeigte auf
    `dashboard_proxy.py` im Checkout) ist **deaktiviert**. Reboot-Prognose: Es startet genau ein Pfad –
    `MiniEmsPoCRelease`. Alle Änderungen reversibel; Rollback-Kommandos im Bericht `agent_b/ALTLASTEN_BERICHT.md`.

- [x] **H3. Runtime-Dateien und Konfiguration sauber schützen**
  - **Was:** Installation z. B. unter `C:\Program Files\MiniEMS` oder `C:\ProgramData\MiniEMS`, mit Windows-Rechten nur
    für Administratoren und einen definierten Mini-EMS-Task-/Service-Benutzer. Logs, Datenbank und Standortkonfiguration
    werden getrennt abgelegt.
  - **Nutzen:** Verhindert zufälliges Bearbeiten, Kopieren oder Lesen durch normale Windows-Benutzer.
  - **Betroffen:** Installationspfade, Dateirechte, Log-/DB-Pfade, Update-Anleitung.
  - **Aufwand:** M
  - **Risiken:** Zu strenge Rechte dürfen den geplanten Task, Logs und Reports nicht blockieren.
  - **Definition of Done:** Normale Benutzer können das UI öffnen, aber Runtime-Dateien, Konfiguration und Logs nicht direkt
    durchsuchen oder ändern.
  - **Stand (2026-07-06):** Konzept liegt vor in `HOSTING_SICHERHEIT.md`, Teil 3: Ziel-Installationslayout
    (App-Dateien `C:\Program Files\MiniEMS`, Standortdaten `C:\ProgramData\MiniEMS`, konsistent zur
    App-/Standortdaten-Liste aus `UPDATE_WARTUNG.md` und zur config-relativen Pfadauflösung in `config.py`
    `resolve_path`/`base_dir`), Rechtemodell als Tabelle (SYSTEM/Administratoren/Task-Benutzer/normale
    Benutzer je Ordner), kopierbare `icacls`-Kommandos mit Prüfkommandos, Betriebsrisiken-Abschnitt
    (Mindestrechte des Task-Benutzers, typische Symptome bei zu strengen Rechten, Funktionstest) und
    Migrationsreihenfolge vom heutigen Git-Checkout zum Ziel-Layout. Details: `HOSTING_SICHERHEIT.md`, Teil 3.
  - **Stand (2026-07-07): Auf der realen Pilot-IPC angewandt und plant-stabil verifiziert.** Die ACLs aus
    `HOSTING_SICHERHEIT.md` 3.3 sind auf `C:\ProgramData\MiniEMS` gesetzt: Vererbung gekappt (`inheritance:r`),
    Wurzel nur noch `BUILTIN\Administratoren:(OI)(CI)F` und `SYSTEM:(OI)(CI)F`, `config.json` `SYSTEM:(R)`,
    `data`/`logs`/`runtime` `SYSTEM:(OI)(CI)M`; die rekursive Prüfung bestätigt **keinen** `Benutzer`-/`Users`-/
    `Everyone`-Eintrag mehr im gesamten Baum. Damit ist der DoD strukturell erfüllt: Ohne jede Users-/Everyone-ACE
    und mit gekappter Vererbung hat **kein** normaler Benutzer Lese-/Schreibzugriff (ein nicht-elevated Zugriff auf
    den Ordner liefert „Zugriff verweigert"). Der Funktionstest nach 3.4 ist bestanden: Die Anlage lief unter den
    gehärteten Rechten stabil weiter (health status=healthy/live, Zyklen laufen, SQLite/Log wachsen, keine
    `PermissionError` nach der Härtung). Ein Rollback-Anker (`icacls /save`) liegt im Nachweis-Ordner
    (`agent_c/acl_backup.txt`). **Betriebs-Lehre aus dem Lauf (wichtig für spätere IPCs):** Ein erster
    Härtungsversuch, der `inheritance:r` **vor** den SYSTEM-Grants auf den Unterordnern ausführte, entzog SYSTEM
    kurzzeitig den Schreibzugriff auf `data\spotmarket` und verursachte einen ~5-minütigen Zyklus-Ausfall
    (`PermissionError` auf `spotmarket_price_cache.json`, `app.cycle_failed`). Die Reparatur (Besitzübernahme,
    ACL-Restore, Erholung abwarten, dann Neuhärtung in korrigierter Reihenfolge – **Grants zuerst, dann
    `inheritance:r`**) stellte den Betrieb wieder her; der Ausfall heilte vollständig selbst. Konsequenz für 3.3:
    Reihenfolge „Grants auf Wurzel/Unterordner setzen, danach Vererbung kappen" ist verbindlich, und `data\spotmarket`
    muss das SYSTEM-Schreibrecht via `(OI)(CI)` von `data` erben. **Restpunkt:** ein Klick-Test unter einem echten,
    dedizierten Nicht-Admin-Windows-Konto bei laufendem Task ist die Gürtel-und-Hosenträger-Bestätigung; die
    ACL-Struktur (keine Users-/Everyone-ACE) garantiert das Ergebnis bereits kategorisch. Nachweisprotokoll:
    `agent_c/H3_ACL_BERICHT.md` bzw. `agent_c/verify_stable_log.txt`.

- [ ] **H4. API intern binden, UI über geschützten Zugriff bereitstellen**
  - **Was:** Die Mini-EMS-API nur an `127.0.0.1` oder eine definierte IPC-Netzwerkadresse binden. Davor optional einen
    lokalen Reverse Proxy setzen, der HTTPS, Login und Zugriffsbeschränkung übernimmt.
  - **Nutzen:** Die technische API wird nicht direkt im Netzwerk ausgestellt. Das UI wird kontrolliert erreichbar.
  - **Betroffen:** `config.json` `api.host`, Windows-Firewall, Reverse-Proxy-Konzept, Secomea/VPN-Regeln.
  - **Aufwand:** M
  - **Risiken:** Keine direkte Internet-Portfreigabe auf `8090`; keine Vermischung von lokalem Simulationspfad und echter IPC.
  - **Definition of Done:** Zugriff funktioniert nur aus freigegebenem Kundennetz/VPN; die bestehende Anlagen-API ist nicht
    öffentlich erreichbar.
  - **Stand (2026-07-07):** Umsetzungsreifes Feinkonzept liegt vor in `HOSTING_SICHERHEIT.md`, Teil 4, plus
    kopierfertige Vorlagen unter `proxy/`. Enthalten: Bindungs-Matrix (wann `127.0.0.1` = nur lokal + Proxy
    davor, wann konkrete EMS-LAN-IP `192.168.244.10` = Secomea-Pfad heute, warum nie `0.0.0.0`, Zusammenspiel
    mit `api.read_only` je Szenario), Reverse-Proxy-Empfehlung **Caddy** (eine Binary, automatisches internes
    HTTPS via `tls internal`, `sc.exe`-Dienst; vs. nginx/IIS begründet), kommentierte `proxy/Caddyfile`
    (`bind` auf EMS-LAN-IP, `reverse_proxy 127.0.0.1:8090`, auskommentierter `basic_auth`-Block als
    H6-Vorbereitung, keine Credentials im Repo), `proxy/firewall_rules.ps1` (`8090` nur lokal, Proxy-Port nur
    Kundennetz/VPN), `proxy/README.md` (Dienst-Installation, Client-Zertifikat, Prüfschritte, Update-
    Zusammenspiel) sowie Sicherheits-Ehrlichkeit (kein Login bis H6, Schutzgrenze beim Kunden-Admin,
    Abgrenzung zum Secomea-Pfad a). Checkbox bleibt **offen**: Die DoD (Zugriff nur aus freigegebenem
    Kundennetz/VPN, Anlagen-API nicht öffentlich) ist erst am Standort nachweisbar – sie setzt den in H2
    offenen Windows-Build, das Umstellen von `config.json` auf `api.host: 127.0.0.1` + `api.read_only: true`
    und die Installation von Caddy/Firewall auf der realen IPC voraus. Offene Standort-Schritte und
    Verifikations-Checkliste: `HOSTING_SICHERHEIT.md`, Teil 4, Abschnitt 4.6.
  - **Stand (2026-07-07): Caddy-Proxy auf der IPC installiert und im Parallelbetrieb nachgewiesen.**
    `caddy.exe v2.11.4` liegt unter `C:\Program Files\Caddy`, die produktive `Caddyfile` unter
    `C:\ProgramData\MiniEMS\proxy\Caddyfile` (bind `192.168.244.10:443`, `tls internal`, `skip_install_trust`,
    upstream aktuell `192.168.244.10:8090` für den Parallelbetrieb). Der Proxy läuft als geplanter Task
    `MiniEmsDashboardCaddy` (SYSTEM, Trigger Systemstart, Crash-Restart) – **nicht** als `sc.exe`-Dienst: Caddy `run`
    ist ein Konsolenprozess ohne Windows-Service-Handler, der als nativer Dienst nach ~30 s START_PENDING vom SCM
    beendet wird (dieselbe Ursache wie beim Legacy-`MiniEmsPoC`-Dienst, Fehler 1053). Der Task-Weg entspricht dem
    `MiniEmsPoCRelease`-Muster. **Zweite Stolperstelle, im Repo-Template behoben:** Auto-HTTPS wollte zusätzlich
    einen HTTP→HTTPS-Redirect-Listener auf **Port 80** binden; Port 80 ist auf dieser IPC durch `http.sys` belegt,
    was den gesamten Config-Load scheitern ließ. Fix: globale Option `auto_https disable_redirects` (HTTPS auf 443
    bleibt aktiv, kein Port-80-Listener) – jetzt Teil von `proxy/Caddyfile`. Nachweis Parallelbetrieb: direkt
    `http://192.168.244.10:8090/dashboard` und `/api/status` = HTTP 200 (unverändert), gleichzeitig über den Proxy
    `https://192.168.244.10/dashboard` und `/api/status` = HTTP 200 (`curl -k`, internes Zertifikat); Plant blieb
    durchgehend healthy. Additive Firewall-Allow-Regel für 443 (`192.168.244.0/24`) gesetzt; die 8090-Block-Regel
    bewusst **nicht** (gehört zur Umschaltung). Die eigentliche H4-Umschaltung (API auf `127.0.0.1`,
    `api.read_only: true`, Caddyfile-Upstream auf `127.0.0.1:8090`, 8090 aus dem Netz sperren) ist als geprüftes,
    **nicht ausgeführtes** Skriptpaket vorbereitet (`agent_d/umschaltung/` mit `umschalten.ps1`, `rollback.ps1`,
    `README_UMSCHALTUNG.md`). Checkbox bleibt **offen**: Der DoD (Zugriff nur aus Kundennetz/VPN, Anlagen-API nicht
    öffentlich) verlangt die Umschaltung und den Nachweis vom zweiten Rechner am Standort – Achtung
    Secomea-Erreichbarkeit, siehe Risiko-Abschnitt im Umschalt-README. Bericht: `agent_d/H4_PROXY_BERICHT.md`.
  - **Stand (2026-07-08): IPC-seitige H4-Umschaltung ausgeführt und lokal verifiziert.**
    `C:\ProgramData\MiniEMS\config.json` bindet die API jetzt an `127.0.0.1:8090` und setzt
    `api.read_only: true`; die produktive `Caddyfile` proxyt auf `127.0.0.1:8090`. Mini EMS wurde über
    `MiniEmsPoCRelease` neu gestartet, Caddy reloadet. Verifikation auf der IPC: `GET /api/status` auf
    `http://127.0.0.1:8090` liefert `api_read_only: true` und `runtime_status: live`;
    `http://192.168.244.10:8090/api/status` ist nicht mehr erreichbar; `https://192.168.244.10/api/status`
    und `/dashboard` liefern über den Proxy HTTP 200; `netstat` zeigt `8090` nur auf `127.0.0.1` und
    `443` auf `192.168.244.10`; Firewall-Regeln `MiniEMS Proxy HTTPS (nur Kundennetz)` und
    `MiniEMS API 8090 (nur lokal, Netz blockiert)` sind aktiv. Backups liegen auf der IPC unter
    `C:\ProgramData\MiniEMS\backups\h4_h5_20260708_185158`. Checkbox bleibt offen bis zum
    zweiten-Rechner-/Secomea-Nachweis aus dem freigegebenen Kundennetz/VPN.

- [ ] **H5. Read-only Netzwerkmodus zuerst**
  - **Was:** Für den ersten geschützten Netzwerkzugriff nur Dashboard, Status, Historie und Reports freigeben. Schreibende
    Endpunkte werden blockiert oder bleiben ausschließlich lokal/administrativ.
  - **Nutzen:** Echte Daten sind sichtbar, aber Anlagensteuerung bleibt geschützt.
  - **Betroffen:** HTTP-API, Dashboard, Reverse Proxy oder API-Gateway-Regeln, Doku zu erlaubten Endpunkten.
  - **Aufwand:** M
  - **Risiken:** UI darf keine verdeckten Konfigurations- oder Schreibfunktionen über denselben Zugriffspfad anbieten.
  - **Definition of Done:** Ein zweiter Rechner sieht echte IPC-Daten im UI; Schalt- und Konfigurationsaktionen sind über
    diesen Pfad nicht möglich.
  - **Stand (2026-07-06):** Die technische Grundlage ist umgesetzt: ein konfigurierbarer, serverseitiger Read-only-Modus
    der HTTP-API (`api.read_only`, Boolean, Default `false`) in `mini_ems_runtime/config.py` und `http_api.py`. Die Sperre
    sitzt an **einer zentralen Stelle** im Request-Handling (`Handler._deny_in_read_only`, aufgerufen am Anfang von
    `do_GET`/`do_POST`): deny-by-default für alle nicht-GET-Methoden plus explizite Zusatzsperre für den aktiven
    Anlagen-Read `GET /api/diagnostics/read`. So bleiben auch künftig neu hinzukommende Endpunkte standardmäßig sicher.
    Blockierte Aufrufe liefern `HTTP 403` mit deutschem JSON-Hinweis (`read_only_mode`); `GET /api/status` meldet additiv
    `api_read_only`. Die read-only Freigabeliste aus `HOSTING_SICHERHEIT.md` 2.1 (Dashboard, `/api/status`, Historie,
    Zyklen, Reports, Wetter, Spotmarkt-/Config-GETs) bleibt erreichbar; die 2.1-Liste wurde gegen den aktuellen
    Endpunktbestand abgeglichen (neu erfasst: `GET /api/config/site`, `POST /api/config/site/validate|save`,
    `POST /api/config/mapping/preview`). Doku ergänzt in `HOSTING_SICHERHEIT.md` (2.1/2.2/2.5) und
    `MINI_EMS_ANLEITUNG.md`; parametrisierte Tests in `tests/test_read_only_api.py` (Default off unverändert;
    read_only=true sperrt jeden blockierten Endpunkt mit 403; Freigabeliste bleibt erreichbar; Status-Feld vorhanden).
    Checkbox bleibt **offen**: Die DoD verlangt den Nachweis von einem zweiten Rechner am Standort – das kann nur der
    Nutzer/Betreiber vor Ort erbringen (Pilot-Checkliste in `HOSTING_SICHERHEIT.md` 2.5, jetzt inkl. `api.read_only`-Schritt).
  - **Stand (2026-07-08): Auf der Pilot-IPC aktiviert und lokal verifiziert.** `GET /api/status` meldet
    `api_read_only: true`; `GET /api/diagnostics/read` liefert HTTP 403; `POST
    /api/config/spotmarket-lockout` liefert HTTP 403 mit `read_only_mode`. Dashboard und Status bleiben über
    `https://192.168.244.10` erreichbar. Offen bleibt auch hier nur der zweite-Rechner-Nachweis aus dem
    Kundennetz/VPN.

- [ ] **H6. UI-Zugriff mit Login und einfacher Rollenlogik absichern**
  - **Was:** Mindestens Passwortschutz für das UI; später Rollen wie `viewer`, `operator`, `admin`. Für den ersten Schritt
    reicht ein kleiner, sauber dokumentierter Zugriffsschutz vor dem Dashboard.
  - **Nutzen:** Das UI ist nicht nur weniger sichtbar, sondern tatsächlich zugangsbeschränkt.
  - **Betroffen:** Reverse Proxy oder kleine Auth-Schicht, Nutzer-/Passwortverwaltung, Betreiberfreigabe.
  - **Aufwand:** M
  - **Risiken:** Passwörter dürfen nicht in Git oder im ausgelieferten Standardpaket landen; Erstpasswort/Rotation klären.
  - **Definition of Done:** Ohne Zugangsdaten ist das UI nicht erreichbar; Viewer können nur lesen.

- [x] **H7. Update- und Wartungsprozess definieren**
  - **Was:** Updates laufen über versionierte Pakete, Checksums und ein kurzes Install-/Rollback-Verfahren. Keine manuellen
    Codeänderungen auf der Kunden-IPC.
  - **Nutzen:** Macht Mini EMS wartbar und reduziert Risiko durch lokale Änderungen.
  - **Betroffen:** Release-Prozess, Paketablage, Backup, Healthcheck, Rollback-Anleitung.
  - **Aufwand:** M
  - **Risiken:** Standortkonfiguration und Betriebsdaten dürfen bei Updates nicht überschrieben werden.
  - **Definition of Done:** Es gibt einen dokumentierten Ablauf: stoppen, Backup, Paket ersetzen, starten, Healthcheck prüfen,
    Rollback falls nötig.
  - **Erledigt:** Der vollständige Ablauf (Grundsätze, Standard-Update-Checkliste, Rollback, Wartungsroutine,
    Versionierung, Verantwortlichkeiten) steht in `UPDATE_WARTUNG.md`, paketformneutral formuliert mit explizit
    markierten H2-abhängigen Stellen; querverwiesen aus `HOSTING_SICHERHEIT.md` und `MINI_EMS_ANLEITUNG.md`.
  - **Stand (2026-07-09): Ablauf als Skripte automatisiert.** `windows/update_release.ps1` setzt den
    H7-Standardablauf um (SHA256SUMS prüfen → Task stoppen + Prozess-Ende verifizieren → App-Ordner nach
    `<AppDir>_vorher_<version>` umbenennen als Rollback-Kandidat → neues Paket kopieren → Task starten →
    Smoketest); `-Rollback` schiebt den vorherigen Stand zurück. `windows/smoketest_release.ps1` prüft frische
    `health.json`, `/api/status` inkl. erwarteter `app_version`/`api_read_only` und das Log auf neue
    ERROR-Zeilen (Exit-Code 0/1). Standortdaten (`SiteDir`) werden nie angefasst. `UPDATE_WARTUNG.md` ist auf
    Skript-first umgestellt, die manuellen Schritte bleiben als Fallback-Referenz.
  - **IPC-Abnahme (2026-07-12, Betreiberbestätigung):** Das neue Release wurde auf der realen IPC installiert
    und läuft fehlerfrei. Die bestehende Standortkonfiguration blieb erhalten, der Freigabecode funktionierte
    und es traten keine Fehlermeldungen auf. Damit ist der reale H7-Updatepfad einschließlich Erhalt der
    Standortdaten und anschließendem Anwendungsstart bestätigt. Konsolenausgaben wurden auf Wunsch nicht ins
    Repository übernommen; der Nachweis ist ausdrücklich als Betreiberbestätigung dokumentiert.

- [x] **H8. Audit, Nachvollziehbarkeit und Betreiberfreigabe**
  - **Was:** UI-Zugriffe, Runtime-Starts, Konfigurationsänderungen und spätere Schreibaktionen nachvollziehbar loggen.
    Kundenseitig klären, wer Zugriff bekommt.
  - **Nutzen:** Professioneller Betrieb statt versteckter Ordner auf Windows.
  - **Betroffen:** Logging, Betriebsdoku, Rollen-/Rechtekonzept, spätere Schreibfreigaben.
  - **Aufwand:** M
  - **Risiken:** Audit-Logs dürfen keine Geheimnisse oder unnötigen personenbezogenen Daten enthalten.
  - **Definition of Done:** Betriebslog und Zugriffskonzept sind für einen Pilotkunden erklärbar.
  - **Erledigt (2026-07-11):** Das bestehende strukturierte Betriebslog dokumentiert Runtime-Starts,
    Dashboard-Aufrufe ohne IP-/Personenbezug sowie bestätigte und fehlgeschlagene Anlagenübergaben.
    Der Revisionsverlauf in `site.sqlite` erfasst Mapping-Aktivierungen, direkte Standortänderungen und Bedienänderungen der
    Preissteuerung. `GET /api/config/changes` liefert daraus nur einen bereinigten Verlauf ohne Token, Dateipfade
    oder personenbezogene Daten; die UI zeigt die letzten Änderungen direkt beim Abschluss. Das Zugriffskonzept
    Viewer/Operator/Admin steht in `HOSTING_SICHERHEIT.md`; echte Benutzeridentitäten und Rollen bleiben H6.

- [x] **H9. Konfigurations-UI als geschützten Entwurfs- und Speicherpfad bauen**
  - **Was:** Die UI schreibt nicht direkt aus einem Formular in die aktive Standortrevision. Umgesetzt ist ein
    kontrollierter Ablauf: aktive Konfiguration lesen, erlaubte Felder als
    Entwurf bearbeiten, denselben fachlichen und technischen Regeln wie beim Runtime-Start validieren, Entwurf
    als neue unveränderliche Revision speichern, Änderung mit Freigabecode übernehmen und
    den Vorgang auditierbar protokollieren. Änderungen, die nur beim Start geladen werden, bleiben bis zum
    geplanten Mini-EMS-Neustart als "Neustart erforderlich" markiert.
  - **Nutzen:** Betreiber bekommen eine verständliche Konfigurationsoberfläche, ohne die Schutzwirkung der
    getrennten IPC-/Laptop-Konfiguration, Validierung und geplanten Betriebsfreigabe zu verlieren.
  - **Betroffen:** HTTP-API, künftige Auth-/Token-Schicht, Config-Validierung, Backup-/Rollback-Ablage,
    Revisionsverlauf, `MINI_EMS_ANLEITUNG.md`, Windows-Task-Neustartprozess.
  - **Aufwand:** M/L
  - **Risiken:** Der Netzwerkzugriff bleibt anlagenbezogen read-only. Ausschließlich passive Entwurfs-/Vorschaupfade
    und token-geschützte Standortaktivierungen sind über Caddy erreichbar; Bedienaktionen und aktive Anlagenzugriffe
    bleiben gesperrt. Der lokale Simulationspfad (`runtime.bacnet_mode=simulated`,
    `runtime.real_writes_enabled=false`) darf keinen Weg bekommen, echte
    BACnet-Writes auszulösen. Safety-Flags und Anlagen-Schreibfreigaben bleiben lokale Admin-/IPC-Arbeit.
  - **Definition of Done:** Ungültige Entwürfe können die aktive Konfiguration nicht überschreiben; jede
    Übernahme erzeugt eine unveränderliche Revision ohne Geheimnisse; Freigabecode-Prüfung ist dokumentiert;
    der geschützte Netzwerkbetrieb blockiert Bedienaktionen und aktive Anlagenzugriffe; Neustartbedarf und Rollback-Pfad sind in Betrieb
    und UI sichtbar.

## Priorisierte To-do-Liste

- [x] **1. Freshness-Gate scharf schalten (Config statt totem Code)**
  - **Was:** In `config.json` und `config.local.json` fuer die Temperatur-/Zaehler-Inputs sinnvolle
    `max_age_seconds`-Werte setzen (aktuell 0 von 17 `additional_inputs` gesetzt -> Gate ist implementiert, aber inaktiv).
  - **Nutzen:** Der bereits gebaute Quality-Gate (`stale`/`bad`) wirkt erst, wenn `max_age_seconds` konfiguriert ist.
    Ohne Werte bleibt jeder Wert dauerhaft `good`, auch wenn der Controller eingefroren ist. Hoher Betriebsnutzen.
  - **Betroffen:** `config.json`, `config.local.json` (Schema/Logik unveraendert: `config.py`, `channels.py`,
    `read_diagnostics.py`, `cycle.py`).
  - **Aufwand:** S
  - **Risiken:** Zu strenge Werte loesen unnoetige `warning`/`stale`-Meldungen aus; Werte am realen Lese-Intervall
    (`read_interval_cycles` x Zykluszeit) ausrichten. KEINE Aenderung an `runtime.*`-Safety-Flags.
  - **Definition of Done:** `config.local.json` (und konsistent `config.json`) setzen `max_age_seconds` fuer alle
    relevanten `additional_inputs`; `config.py`-Validierung (`> 0`) bleibt erfuellt; Tests bleiben gruen
    (`python3.12 -m unittest discover -s mini_ems_poc/tests -v`).

- [x] **2. Quality/Freshness im Dashboard sichtbar machen**
  - **Was:** Im Dashboard die `quality`/`age_seconds`/`status`-Flags der Inputs anzeigen (z. B. dezenter Stale-/Bad-Badge
    an der jeweiligen Kachel). Daten liegen in `health.json` (`additional_inputs`) und in `/api/status` bereits vor.
  - **Nutzen:** Der Operator sieht heute keinen Hinweis auf veraltete Messwerte; `dashboard.js` rendert weder
    `quality` noch `age_seconds`. Schliesst die Luecke zwischen vorhandenen Backend-Flags und Bedienoberflaeche.
  - **Betroffen:** `dashboard/dashboard.js`, `dashboard/dashboard.css`; lesend `mini_ems_runtime/http_api.py` (`/api/status`).
  - **Aufwand:** M
  - **Risiken:** Nur Frontend, keine Steuerlogik. Kundensprache beachten (`AGENTS.md` Abschnitt "German UI Language"):
    keine internen IDs/Protokollbegriffe,
    echte Umlaute. Backend-Vertrag (`build_health_additional_inputs`) nicht aufweichen.
  - **Definition of Done:** Bei `quality == "stale"`/`"bad"` zeigt die betroffene Kachel sichtbar einen Hinweis in klarer
    deutscher Geschaeftssprache; "good" bleibt unauffaellig; lokaler Smoke-Test gegen `config.local.json` zeigt das Verhalten.

- [ ] **3. Erstes sicheres Online-Hosting für Mini EMS vorbereiten**
  - **Was:** Einen ersten Hosting-Pfad für das Mini-EMS-UI definieren und prototypisch umsetzen, damit echte IPC-Daten
    von einem zweiten Rechner aus sichtbar werden, ohne die aktuelle Anlagen-API öffentlich freizugeben.
  - **Nutzen:** Erlaubt echtes Monitoring außerhalb der lokalen Simulation und macht Mini EMS als bedienbares Produkt
    greifbarer. Gleichzeitig bleibt die klare Sicherheitsgrenze erhalten: Die IPC bleibt Anlagen-Gateway, das Online-UI
    ist zunächst read-only und bekommt nur freigegebene Betriebsdaten.
  - **Betroffen:** Architektur-/Betriebsdoku, `MINI_EMS_ANLEITUNG.md`, Dashboard/API-Schnitt, optional kleiner Exporter
    oder Reverse-Proxy-Konzept; keine Änderung an BACnet-Writes oder `runtime.real_writes_enabled`.
  - **Aufwand:** M
  - **Risiken:** Keine Portfreigabe des bestehenden `192.168.244.10:8090`-Dienstes ins Internet. Vor produktiver Nutzung
    braucht es HTTPS, Login, Rollen, klare Trennung read-only vs. write, Firewall/VPN-Regeln und ein nachvollziehbares
    Datenmodell für die veröffentlichten Kanäle.
  - **Definition of Done:** Es gibt eine dokumentierte Minimalvariante für das erste Online-Hosting, z. B. Secomea/VPN-Zugriff
    auf das bestehende Dashboard oder ein read-only Cloud-Export mit Login; der Pfad zeigt echte IPC-Daten auf einem zweiten
    Rechner; Schreibfunktionen bleiben gesperrt oder explizit außerhalb des Online-UI.
  - **Stand:** Das dokumentierte Minimalkonzept (beide Pfade, freizugebende read-only und zu sperrende Endpunkte,
    Empfehlung Secomea/VPN zuerst, Pilot-Checkliste, Leitplanken) liegt in `HOSTING_SICHERHEIT.md`, Teil 2, vor.
    Offen bleibt der reale Nachweis auf einem zweiten Rechner am Standort – das kann nur der Betreiber/Nutzer vor Ort
    erbringen; deshalb bleibt dieses To-do offen.

- [x] **4. Runtime-Watchdog mit echtem Alarm (Offene Punkte #3)**
  - **Was:** Aus dem reinen Beobachtungs-Snapshot (`_watchdog_snapshot`, `last_healthy_at`) eine echte Liveness-Bewertung
    machen: bei zu altem `last_cycle_at`/`last_healthy_at` einen klaren `stale_runtime`-Status in `health.json` ausgeben.
  - **Nutzen:** Heute wird die Watchdog-Info nur protokolliert, aber nie ausgewertet; eine haengende Runtime faellt nicht auf.
    Direkt aus ANLEITUNG "Offene Punkte" #3.
  - **Betroffen:** `mini_ems_runtime/cycle.py` (`_watchdog_snapshot`/`_build_health_payload`), evtl. neues Feld in
    `state_store.py`/`config.py` (z. B. `watchdog.max_cycle_age_seconds`); Tests in `tests/test_runtime.py`.
  - **Aufwand:** M
  - **Risiken:** Abgrenzung zu `safe_mode` sauber halten (Watchdog erkennt "kein Zyklus mehr", nicht "Zyklus fehlerhaft").
    Schwellwert konfigurierbar machen, nicht hart kodieren.
  - **Definition of Done:** Neuer Unit-Test reproduziert einen veralteten Heartbeat und erwartet ein Stale-/Alarm-Feld in der
    Health-Payload; alle Tests gruen; Standardverhalten ohne Konfiguration unveraendert.

- [x] **5. Python-Versions-Footgun entschaerfen (Toolchain/Doku)**
  - **Was:** Sicherstellen, dass die dokumentierten Befehle nur mit Python >= 3.10 laufen: in `README.md`/`AGENTS.md` den
    Versions-Hinweis prominenter machen bzw. einen `python_requires`/Versions-Check ergaenzen (z. B. fruehe Pruefung in `mini_ems.py`).
  - **Nutzen:** `python3 -m unittest ...` schlaegt auf Maschinen mit `python3` = 3.9 hart fehl (PEP-604 `X | None`),
    obwohl der Code korrekt ist. Senkt Onboarding-Reibung und falsche "Tests rot"-Schluesse.
  - **Betroffen:** `mini_ems.py` (optionaler Versions-Guard), `README.md`, `AGENTS.md`, `mini_ems_poc/AGENTS.md`.
  - **Aufwand:** S
  - **Risiken:** Sehr gering; rein additiv. Keine Verhaltensaenderung der Runtime.
  - **Definition of Done:** Ein Aufruf mit Python < 3.10 liefert eine klare Fehlermeldung statt eines `TypeError` tief im Import;
    Doku nennt den exakten Interpreter (z. B. `python3.12`); Tests unter 3.10+ bleiben gruen.

- [x] **6. Doku-Pfade an Ist-Konfiguration angleichen**
  - **Was:** In `MINI_EMS_ANLEITUNG.md` die Pfade fuer SQLite/Log konsistent machen: Doku nennt `data/runtime/mini_ems.sqlite`
    und `logs/mini_ems.log`, die lokale Konfiguration nutzt `data/local/...` bzw. `data/runtime/...` je nach Umgebung.
  - **Nutzen:** Vermeidet falsche Pfadannahmen bei Betrieb/Debugging; rein redaktionell, kein Code-Risiko.
  - **Betroffen:** `MINI_EMS_ANLEITUNG.md` (lesend `config.json`, `config.local.json`).
  - **Aufwand:** S
  - **Risiken:** Keine (Doku-only). Echte Umlaute verwenden (`AGENTS.md` Abschnitt "German UI Language").
  - **Definition of Done:** Jede in der Anleitung genannte Datei-/DB-Pfadangabe entspricht den tatsaechlichen Werten in
    `config.json`/`config.local.json` (getrennt nach IPC und lokal).

## Empfohlener nächster Schritt

**Mapping- und Freigabekern abgeschlossen; nächste Laptop-Linie ist S9 Edge-to-Cloud read-only.** S1-S4 haben
den Edge-Integrationskern und ein erstes Modbus-Referenzmodell etabliert, S7/S8 den sicheren Import-/Discovery-
Pfad. UX14-16 und S5/S6 bilden nun einen einzigen Ablauf: Standort → Geräte → Datenpunkte → Testen →
Abschließen, mit erneutem Preview, lokalem Freigabecode, automatischem Backup, erhaltenem Entwurf,
Audit-Verlauf und eindeutigem Neustartstatus. H8 macht denselben Vorgang für den Betreiber nachvollziehbar.
Damit ist die fachliche Zuordnung stabil genug, um als Nächstes S9 als transportneutralen read-only
Outbox-/Cloud-Export aufzubauen. Der IPC bleibt dabei Edge-Gateway; der erste Cloud-Schritt enthält keine
Remote-Befehle und keinen direkten Anlagenzugriff.

**Standort-Schritte als Block: H4/H5-Zweitrechner-Nachweis + To-do 3, danach H6.** Auf der Pilot-IPC am
2026-07-07 deutlich vorangebracht und am 2026-07-08 für H4/H5 IPC-seitig umgeschaltet.
**H2: erledigt** – Release-Paket (`mini_ems.exe`) läuft über Task `MiniEmsPoCRelease`, per `SHA256SUMS` verifiziert,
Alt-Autostarts entschärft; Version ist zusätzlich zur Laufzeit sichtbar (Stand 2026-07-09). **H3: erledigt** –
`icacls`-Härtung auf `C:\ProgramData\MiniEMS` angewandt (keine Users-/Everyone-ACE, Vererbung gekappt), Anlage
unter den Rechten stabil; Rest ist ein formaler Klick-Test unter einem Nicht-Admin-Konto. **H4: IPC-seitig
umgeschaltet** – API bindet nur noch auf `127.0.0.1:8090`, Caddy läuft als Task `MiniEmsDashboardCaddy` auf
`https://192.168.244.10`, 8090 ist aus dem LAN nicht mehr erreichbar und die H4-Firewallregeln sind aktiv.
**H5:** `api.read_only` ist auf der Pilot-IPC aktiv; Diagnose-Read und POST-Konfigurationspfade liefern HTTP 403.
Offen bleibt bei H4 und H5 derselbe reale Nachweis von einem zweiten Rechner am Standort über
Kundennetz/VPN/Secomea. **To-do 3:** Minimalkonzept (Secomea/VPN bzw. Export mit Login) liegt in
`HOSTING_SICHERHEIT.md`, Teil 2, vor; der zweite-Rechner-Nachweis fehlt noch (identischer Standort-Schritt
wie bei H4/H5). **H6 (Login/Rollen): Auswahlentscheidung offen.** Es ist noch nicht festgelegt, ob der
erste Zugriffsschutz über den vorbereiteten `basic_auth`-Block in `proxy/Caddyfile` läuft oder über eine
eigene Login-Schicht; das folgt nach dem Zweitrechner-Nachweis. H8 ist abgeschlossen; H9 bleibt für die
spätere rollenbasierte Erweiterung der gesamten Konfigurationsoberfläche offen.

**Danach: S9 klein beginnen; S10-S12, S16 und die große Cloud-Data-Pipeline bleiben geparkt.** S9 startet nur
mit stabiler Payload, lokaler Outbox und einem simulierten read-only Empfänger. Broker-, TSDB-, Mandanten-,
Semantik- und Retention-Entscheidungen aus C1-C9 folgen erst anhand dieses kleinen Ende-zu-Ende-Pfads.
Remote-Commands und Write-Back-Leases bleiben ausdrücklich später; S15 braucht zuvor die reale
MSR-/Standortabnahme des DDC-Fallbacks.
