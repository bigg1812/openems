# BACnet-Stack-Evaluierung (Roadmap S7)

Diese Datei ist die technische Entscheidungsvorlage zu `ROADMAP.md` **S7 — "BACnet-Profi-Stack
evaluieren: BACpypes3 und BAC0"**. Sie beantwortet die geforderte Kernfrage: eigenen Adapter
weiterführen, `BACpypes3` direkt nutzen oder `BAC0` als Komfortschicht für Discovery/Import einsetzen —
inklusive Teststrategie und klarer Grenze zu den Schreibpfaden.

Grundsatz wie im `EDGE_INTEGRATION_CONTRACT.md`: **Der Code ist die Wahrheit.** Jede Aussage über den
eigenen Adapter ist am Repo verifiziert (Datei/Zeile genannt), jede Aussage über eine Fremdbibliothek
mit aktueller Quelle belegt (Stand der Recherche: 2026-07-05).

Status: **Evaluierung, keine Umsetzung.** Diese Datei installiert keine Abhängigkeit und ändert keinen
Laufzeitcode. Die S7-Checkbox bleibt offen; die finale Wahl trifft der Nutzer.

---

## 1. Ist-Analyse: der eigene BACnet-Adapter heute

Der eigene Adapter ist `mini_ems_runtime/bacnet.py`. Er ist bewusst klein, stdlib-only (nur `socket`,
`struct`, `time`, `logging`) und implementiert BACnet/IP von Hand auf UDP-Ebene.

### Was er kann (verifiziert am Code)

| Fähigkeit | Beleg im Code |
|---|---|
| BACnet/IP über UDP (BVLC `0x81 0x0A` = Original-Unicast-NPDU) | `_build_read_packet`/`_build_write_packet_*` in `bacnet.py:336-369` |
| `ReadProperty` auf `presentValue` (Property-ID 85) | `PROP_PRESENT_VALUE = 85`, `READ_PROPERTY_SERVICE_CHOICE = 0x0C`, `read_float()` `bacnet.py:15,17,49-101` |
| `WriteProperty` auf `presentValue`, feste Priorität 14 | `WRITE_PRIORITY = 14`, `write_float`/`write_bool` `bacnet.py:16,103-129,346-369` |
| Objekttypen **nur** AI (0), AV (2), BV (5) | `channels.py:6-8`; Config-Parser `config.py:514-531` erlaubt ausschließlich `ai`/`av`/`bv` |
| Datentyp beim Lesen: **nur Real/Float** (BACnet Application Tag `0x44`/`0x3C`) | `_scan_real_value()` `bacnet.py:424-436` |
| Schreiben: Float (`AV`) und Boolean (`BV`) | `_build_write_packet_float`/`_bool` `bacnet.py:346-369` |
| Write mit Bestätigung: `SimpleACK`, optional Readback (nur `AV`, Toleranz 0,001) | `write_with_confirmation()` `bacnet.py:131-216`, `_float_values_match()` `bacnet.py:439-440` |
| Retries + Timeout pro Zugriff | `network.retries`/`response_timeout_seconds`, `_receive_matching()` `bacnet.py:274-323` |
| Absender-Filterung (verwirft Pakete fremder IP/Port) | `bacnet.py:295-305`, Log-Event `bacnet.unexpected_sender` |
| Invoke-ID-Matching (Antwort muss zur Anfrage passen) | `_next_invoke_id()`/`_matches_apdu_header()` `bacnet.py:325-327,399-406` |
| Ziel je Punkt überschreibbar (`controller_ip`/`controller_port`) | `_target_address()` `bacnet.py:329-333` |
| Neutraler Vertrag: erfüllt `ProtocolAdapter` aus `protocol.py` | `read_float`/`write_with_confirmation`/`close` |

Ergänzend liefert `mini_ems_runtime/objectlist_import.py` heute die **Antwort auf Punktlisten**: Es
liest eine bereits vom GLT-/MSR-Werkzeug exportierte `objectlist.csv` (Spalte `Object Reference` im
Muster `/<device>.<TYPE><instance>`), filtert auf eine **fest kodierte Allowlist** von 12 bekannten
Report-Punkten (`SELECTED_REPORT_POINTS`, `objectlist_import.py:39-52`) und schreibt daraus Snapshots
in die Report-DB. Das ist ein **statischer Import aus einer fremden Datei**, kein Netz-Discovery: Es
gibt keinen Live-Scan, kein `Who-Is`, keine dynamische Objektliste vom Gerät.

### Harte Grenzen für größere Standorte (jede Aussage am Code verifiziert)

- **Kein `Who-Is`/`I-Am`.** Kein Discovery-Broadcast, keine Geräteerkennung. `grep -rin "who.is|i-am"
  mini_ems_runtime/` liefert nichts; das gesamte BVLC-Framing ist Unicast (`0x81 0x0A`). Punkte müssen
  in `config.json` bekannt und von Hand gepflegt sein.
- **Kein `ReadPropertyMultiple` (RPM).** Nur Einzel-`ReadProperty` je Punkt
  (`READ_PROPERTY_SERVICE_CHOICE = 0x0C`). Bei vielen Punkten entsteht ein Request/Response pro Punkt
  pro Zyklus — für die heutigen ~21 Punkte tragbar, für hunderte Punkte ineffizient.
- **Keine dynamische Objektlisten-Abfrage.** Der Adapter kann das `object-list`-Property eines Device-
  Objekts nicht lesen (nur `presentValue`). Punktlisten kommen ausschließlich aus der CSV-Vorstufe.
- **Kein BBMD / kein Foreign-Device-Registrierung / kein Routing.** Kein `Register-Foreign-Device`,
  keine BVLC-Broadcast-Distribution. Kommunikation nur direkt zu erreichbaren IP-Zielen im selben
  Subnetz (bzw. per Punkt gesetzter IP). Standorte mit BBMD/mehreren BACnet-Netzen sind so nicht
  vollständig erreichbar.
- **Keine Segmentierung.** `_receive_matching()` liest ein einzelnes Datagramm mit `recvfrom(1500)`
  (`bacnet.py:288`); es gibt keine Segment-ACK-Logik. Antworten, die nicht in eine APDU/ein UDP-Paket
  passen (große Objektlisten, RPM über viele Properties), werden nicht zusammengesetzt.
- **Begrenzte Objekttypen und Datentypen.** Nur AI/AV/BV und nur Real/Boolean. Kein MSV/MSI, kein BI/BO,
  kein AO, keine Enumerated/Unsigned/CharacterString-Werte. Der Value-Scanner sucht ausschließlich nach
  Real-Tags (`_scan_real_value`), Binär wird nur beim Schreiben erzeugt.
- **Keine COV-Subscription, kein Trend/Event-Log-Zugriff.** Nur zyklisches Polling.

### Einordnung

Für den **produktiven Lese-/Schreibpfad weniger, bekannter Punkte** ist der Adapter angemessen,
auditierbar und ohne Fremdrisiko — genau das, was der Contract in "Was darf geschrieben werden?"
(`EDGE_INTEGRATION_CONTRACT.md`) eng absichert. Die Grenzen treffen ausschließlich den **Inbetriebnahme-/
Onboarding-Fall** großer Netze: Geräte finden, Objektlisten einlesen, viele Punkte effizient
probelesen. Genau das ist Ziel von **S8** (Discovery/Import als Mapping-Vorstufe).

---

## 2. Kandidaten-Analyse

### 2.1 BACpypes3

| Merkmal | Stand (Quelle) |
|---|---|
| Aktuelle Version | **0.0.106**, veröffentlicht **17.03.2026** (PyPI) |
| Lizenz | **MIT** (PyPI-Metadaten, "License Expression") |
| Python-Support | Classifier **3.8 bis 3.14**, inkl. 3.12/3.13; `Requires: Python >=3.8` (PyPI) |
| Async-Modell | vollständig `asyncio` / `async`/`await`; Neuentwicklung gegenüber dem alten `bacpypes` |
| Discovery / RPM / BBMD | Kern-BACnet-Stack mit `Who-Is`/`I-Am`, `ReadPropertyMultiple`, IPv4/IPv6- und BBMD-/Foreign-Device-Fähigkeit (Applikations- + Netzwerkschicht, siehe Doku/Samples) |
| BACnet/SC | über Extra `websockets`; laut offizieller Setup-Doku **"required for BACnet/SC communications (still being developed)"** — also vorhanden, aber nicht ausgereift |
| Optionale Extras | `websockets` (SC), `ifaddr` (Interface-Auflösung), `pyyaml` (YAML-Config), `rdflib` (RDF/Semantik), `pcap`/`ifaddr` je nach Plattform (Setup-Doku) |
| Wartung | aktiv; Versionscadence bis 03/2026, Autor Joel Bender (Original-BACpypes-Maintainer) |
| Reifegrad | Versionsschema noch `0.0.x` — API nicht als stabil deklariert; Kern jedoch der De-facto-Python-BACnet-Stack |

**Was BACpypes3 für die S8-Ziele bietet:** genau die vier fehlenden Bausteine — `Who-Is`/`I-Am`
(Discovery), dynamische Objektlisten (`object-list` lesen), `ReadPropertyMultiple` (effizientes
Probelesen vieler Punkte) und BBMD/Foreign-Device (Erreichbarkeit über Router). BACnet/SC ist
perspektivisch abgedeckt, aber noch in Entwicklung.

**Was es kostet:**
- **Dependency-Fußabdruck:** erste Nicht-stdlib-Laufzeitabhängigkeit im bisher **stdlib-only** Projekt
  (verifiziert: `grep` über `mini_ems_runtime/` zeigt nur Standardbibliothek — `socket`, `struct`,
  `urllib`, `sqlite3`, `hmac` …; keine `requirements.txt`/`pyproject.toml` mit Fremd-Deps vorhanden).
  Für Discovery bleibt der Kern reines `asyncio`; SC/Semantik-Extras nur bei Bedarf.
- **Deployment auf der Windows-IPC:** relevant im Zusammenhang mit dem frisch entschiedenen
  **PyInstaller-Release-Paket** (Roadmap H2). Ein `asyncio`-Netzwerkstack lässt sich mit PyInstaller
  bündeln, vergrößert aber das Artefakt und die Angriffs-/Fehlerfläche. Da BACpypes3 im **0.0.x**-Band
  liegt, muss die Version im Release fixiert und bei Updates bewusst nachgezogen werden.
- **Betriebsrisiko:** ein zweiter Netz-Stack, der Broadcasts (`Who-Is`) und RPM erzeugt. Ohne Regeln
  kann Discovery ein GA-Netz belasten (siehe S8-Risiken). API-Stabilität `0.0.x` bedeutet Pflege.

### 2.2 BAC0

| Merkmal | Stand (Quelle) |
|---|---|
| Aktuelle Version | **2025.9.15**, veröffentlicht **19.09.2025** (PyPI) |
| Lizenz | **LGPL-3.0** (PyPI) |
| Python-Support | **"3.10 and over"** — laut Projekt (PyPI/GitHub); **schließt 3.9 aus** |
| Abhängigkeit | baut **auf BACpypes3 auf** ("Library depending on BACpypes3", GitHub/PyPI); zieht BACpypes3 transitiv mit |
| Rolle | Komfort-/Skript-Schicht: einfache Befehle für Netz-Browsing, Read/Write, Point-Discovery, Trends |
| Wartung | laut Snyk-Health "Healthy", regelmäßige Releases |
| Reifegrad | höheres, aber datumsbasiertes Versionsschema; erbt die Reifegrenzen von BACpypes3 |

**Verhältnis der beiden (aktuell geprüft):** BAC0 ist **kein Konkurrent, sondern ein Wrapper** über
BACpypes3. Frühere BAC0-Versionen nutzten das alte `bacpypes`; die aktuelle Linie (2025.x) setzt auf
`BACpypes3`. Wer BAC0 nimmt, bekommt BACpypes3 **plus** eine Komfortschicht **plus** eine zweite
Wartungs-/Kompatibilitätsstelle und die **LGPL-3.0**-Lizenz obendrauf.

**Was BAC0 für die S8-Ziele bietet:** dieselben Fähigkeiten wie BACpypes3, aber mit weniger Boilerplate
(z. B. `bacnet.discover()`, Objekt-Browsing, `read`/`readMultiple` mit einfachen Strings). Ideal für
schnelle Inbetriebnahme-Skripte.

**Was es kostet:**
- **Dependency-Fußabdruck:** BACpypes3 **plus** BAC0 selbst — zwei Fremdpakete statt einem.
- **Lizenz:** LGPL-3.0 statt MIT. Für ein intern betriebenes, nicht weiterverteiltes
  Inbetriebnahme-Werkzeug meist unkritisch (dynamisches Linken), aber im Kontext des ausgelieferten
  PyInstaller-Release-Pakets (H2) juristisch bewusst zu behandeln (LGPL-Weitergabepflichten). Ein
  **read-only Werkzeugpfad, der nicht Teil des Kundenpakets ist**, umgeht dieses Thema am saubersten.
- **Python-Minimum 3.10:** die Tests laufen ohnehin unter 3.12 (`.venv`, py3.12); der System-`python3`
  (3.9) dieses Rechners scheidet für BAC0 aus — konsistent mit dem bereits bestehenden PEP-604-Problem.
- **Betriebsrisiko:** Komfort verdeckt Details. Genau der in S7 genannte Punkt: BAC0 kann `readMultiple`
  "alles auf einmal" anbieten und damit Last/Timeouts schlechter kontrollierbar machen als direkter
  BACpypes3-Zugriff.

---

## 3. Drei Optionen im Vergleich

**(a) Eigener Adapter + gezielte Eigenerweiterung** — Discovery/RPM selbst in `bacnet.py` nachbauen.
**(b) BACpypes3 direkt** — als **getrennter, read-only Werkzeugpfad** nur für Discovery/Import.
**(c) BAC0** — dasselbe wie (b), aber über die Komfortschicht.

| Kriterium | (a) Eigenerweiterung | (b) BACpypes3 direkt | (c) BAC0 |
|---|---|---|---|
| Betriebsrisiko am Standort (Produktivpfad) | keins zusätzlich; Produktivpfad unverändert | keins, **wenn** strikt read-only/getrennt | keins, **wenn** strikt read-only/getrennt |
| Aufwand bis S8 | **hoch** (Who-Is, RPM, Objektliste, BBMD, Segmentierung von Hand — genau das, was reife Stacks gelöst haben) | **mittel** (Stack vorhanden; Integrationsarbeit + Lastregeln) | **niedrig-mittel** (fertige Discovery-Befehle) |
| Testbarkeit | volle Kontrolle, aber viel eigener Protokollcode zu testen | gut: BACpypes3 bringt eigene Testserver/Samples zum Simulieren von Geräten | gut, aber eine Abstraktionsebene weiter weg vom Draht |
| Deployment (Windows-IPC, PyInstaller H2) | **null Fremd-Deps**, kleinstes Artefakt | +1 Fremd-Dep; als getrenntes Werkzeug nicht zwingend im Kundenpaket | +2 Fremd-Deps + LGPL; als getrenntes Werkzeug nicht im Kundenpaket |
| Lock-in | keiner | moderat (De-facto-Standardstack, MIT) | höher (BAC0-API **über** BACpypes3, LGPL) |
| Lizenz | — | **MIT** | **LGPL-3.0** |
| API-Stabilität | selbst bestimmt | `0.0.x` (nicht stabil deklariert) | datumsbasiert, erbt BACpypes3-Reife |

**Kernabwägung:** Option (a) reproduziert Jahre gelöster Protokollarbeit (Segmentierung, BBMD,
RPM-Fehlerfälle) und ist für einen kleinen EMS unwirtschaftlich und riskant. Option (c) spart etwas
Skriptaufwand, zahlt dafür mit einer zweiten Abhängigkeit, LGPL und weniger Lastkontrolle — der in S7
ausdrücklich benannte Nachteil. Option (b) trifft die Mitte: reifer Stack, MIT, direkter Zugriff auf
Lastparameter (RPM-Batchgröße, Timeouts, gezieltes `Who-Is`).

---

## 4. Empfehlung und harte Grenze

### Empfehlung

**Der produktive Lese-/Schreibpfad bleibt beim eigenen Adapter (`bacnet.py`).** Für die
Inbetriebnahme-/Discovery-Vorstufe (S8) wird **BACpypes3 direkt** empfohlen (Option b), **nicht** BAC0:
gleicher Funktionsumfang für unsere Ziele, aber MIT-Lizenz, direkte Kontrolle über Broadcast-/RPM-Last
und nur **eine** Fremdabhängigkeit. BAC0 bleibt als optionale Skript-Bequemlichkeit denkbar, ist aber
für den Betriebspfad nicht nötig und bringt LGPL + zweite Abhängigkeit.

Begründung in drei Punkten: (1) Der eigene Adapter deckt den engen, auditierten Produktivpfad sicher ab
und darf keine Discovery-Komplexität übernehmen. (2) Die vier fehlenden Bausteine (Who-Is, RPM,
Objektliste, BBMD) sind reine Inbetriebnahme-Funktionen und in BACpypes3 fertig und gepflegt. (3) MIT +
ein Paket + direkter Lastzugriff ist gegenüber BAC0 (LGPL + zwei Pakete + verdeckte Last) das kleinere
Betriebs- und Lizenzrisiko.

### Harte Grenze (aus dem Roadmap-Eintrag zwingend)

1. **Kein Fremd-Stack im Produktivpfad.** BACpypes3 läuft **ausschließlich als read-only
   Discovery-/Import-Werkzeug** im Inbetriebnahme-Kontext. Der reale Lese-/Schreibpfad (Regelung,
   `cycle.py`, Outputs) benutzt **weiterhin nur** `BacnetAdapter`/`ProtocolRoutingAdapter`.
2. **Niemals Writes.** Das Werkzeug ruft **keine** `WriteProperty`-, `WritePropertyMultiple`- oder
   Command-Dienste auf. Es kennt nur `Who-Is`/`I-Am`, `ReadProperty(object-list)` und begrenztes
   `ReadPropertyMultiple`. Der Schreibpfad bleibt zu 100 % beim eigenen Adapter mit fester Priorität 14,
   ACK/Readback und den Safety-Flags aus `EDGE_INTEGRATION_CONTRACT.md` ("Was darf geschrieben werden?").
3. **Nur Kandidaten, keine Kanäle.** Ein Discovery-Lauf erzeugt ausschließlich **Rohpunkt-KANDIDATEN**
   (Name, Objekttyp, Instanz, Einheit, aktuelle Probe) als Eingabe für den **Mapping-Entwurf (S5,
   `mapping_config.py`)**. Es entstehen **keine** aktivierten Kanäle, keine `additional_inputs`, kein
   `points`-Eintrag. Aktivierung läuft unverändert über den validierten Preview-/Freigabepfad (S5/S6)
   mit Backup und Audit.
4. **Getrenntes Artefakt.** Das Werkzeug ist ein separater Prozess/CLI-Pfad, nicht Teil des Regel-
   Prozesses und — wegen LGPL-Vermeidung und kleinerem Kundenpaket — nicht zwingend Teil des
   ausgelieferten PyInstaller-Release-Pakets (H2). Discovery ist Konfigurator-Werkzeug, kein
   Laufzeitdienst auf der Kunden-IPC.

### RPM-/Broadcast-Lastgrenzen als konkrete Regeln

- **`Who-Is` nur gezielt.** Bevorzugt gerichtete/rangebeschränkte `Who-Is` (Instanzbereich) oder
  Unicast an bekannte Controller-IPs statt globalem Broadcast. Ein globaler `Who-Is` höchstens einmal
  pro Discovery-Lauf, mit Mindestpause; keine periodischen Broadcasts.
- **RPM in kleinen Batches.** `ReadPropertyMultiple` **nie** "alles auf einmal". Feste Obergrenze pro
  Request (Richtwert: **max. 8–16 Properties/Objekte je RPM**, standort-/geräteabhängig nach unten
  korrigieren), damit Antworten in eine APDU passen und Segmentierung vermieden wird. Bei Timeout oder
  Segment-Bedarf automatisch auf Einzel-`ReadProperty` zurückfallen.
- **Ratenbegrenzung.** Serielle, gedrosselte Abfrage pro Gerät (analog zu `timing.inter_read_delay_seconds`
  im Produktivpfad), keine parallelen Bursts gegen ein Gerät; explizite Timeouts + begrenzte Retries.
- **Read-only-Guard.** Der Werkzeugpfad exportiert keine Write-Funktion nach außen; jeder Schreibdienst
  ist im Werkzeug technisch nicht aufrufbar (analog zum `ModbusPermissionError`-Muster im
  read-only Modbus-Adapter, `EDGE_INTEGRATION_CONTRACT.md`, "Modbus TCP als zweites Protokoll").
- **Netz-Etikette.** Vor Discovery an einem realen Standort: Betreiber-/MSR-Freigabe, Zeitfenster,
  Beobachtung der GA-Netzlast; keine Discovery gegen produktive DDC ohne Absprache.

---

## 5. Teststrategie

Ziel: den empfohlenen Pfad (BACpypes3 als read-only Discovery-Werkzeug) vollständig testbar machen,
**ohne echte Anlagen zu gefährden** — konsistent mit dem bestehenden Testmuster (In-Process-Fake-Server
auf `127.0.0.1`, wie bei Modbus in `tests/test_modbus_adapter.py`).

1. **Simulierte BACnet-Geräte lokal.** BACpypes3 bringt eigene **Beispiel-/Testserver** (Sample-Apps für
   IPv4/IPv6/SC-Link-Layer) mit, die als virtuelle BACnet-Geräte auf `127.0.0.1` oder einem
   isolierten Test-Subnetz laufen. Damit lassen sich `Who-Is`/`I-Am`, `object-list` und RPM gegen
   definierte Objektlisten testen, ohne physische Controller. Alternativ ein kleiner selbstgebauter
   Fake-Responder analog zum Modbus-Fake.
2. **Contract-Tests gegen den bestehenden Vertrag.** Der Discovery-Output ist **nur Kandidatenliste**.
   Ein Test prüft, dass die erzeugten Kandidaten ausschließlich in einen **Mapping-Entwurf** (`RawPoint`/
   `MappingDevice` in `mapping_config.py`) fließen und `build_mapping_config_patch()` weiterhin über den
   validierten Pfad läuft — es darf **kein** Weg vom Discovery-Lauf direkt in `config.json`, `points`
   oder `additional_inputs` existieren. Zusätzlich: der Produktivpfad (`ProtocolAdapter`,
   `BacnetAdapter`) bleibt in allen bestehenden Tests unverändert grün.
3. **Read-only-/Write-Verbot-Test.** Ein Test stellt sicher, dass der Werkzeugpfad keinerlei
   Write-Dienst aufruft bzw. exponiert (kein `WriteProperty`), analog zum `ModbusPermissionError`-Test.
4. **Lastregel-Tests.** RPM-Batchgröße respektiert die Obergrenze; bei simuliertem Timeout/Segment-Bedarf
   erfolgt der Fallback auf Einzel-`ReadProperty`; `Who-Is` wird gedrosselt/gerichtet abgesetzt (Zähler
   der Broadcasts im Test verifizieren).
5. **Netz-Lastregeln vor Feldeinsatz.** Erster realer Lauf nur in Test-/Abnahmefenster, gegen ein
   einzelnes freigegebenes Gerät, mit kleinen RPM-Batches und beobachteter Netzlast; Ausweitung erst
   nach Freigabe. Keine automatisierten CI-Tests gegen reale Anlagen.
6. **Isolation vom Release.** Werkzeug-Tests laufen in derselben `.venv` (py3.12), aber die
   Discovery-Abhängigkeit ist als optionale/getrennte Test-/Werkzeug-Dependency zu führen, damit der
   stdlib-only Produktivkern und das PyInstaller-Paket (H2) davon unberührt bleiben.

---

## Quellen (Recherche 2026-07-05)

- BACpypes3 auf PyPI — Version 0.0.106 (17.03.2026), Lizenz MIT, Python 3.8–3.14:
  https://pypi.org/project/bacpypes3/
- BACpypes3 GitHub (Joel Bender): https://github.com/JoelBender/BACpypes3
- BACpypes3 Setup-Doku (Extras; `websockets` "required for BACnet/SC communications (still being
  developed)"): https://bacpypes3.readthedocs.io/en/latest/gettingstarted/setup.html
- BAC0 auf PyPI — Version 2025.9.15 (19.09.2025), Lizenz LGPL-3.0, Python 3.10+:
  https://pypi.org/project/BAC0/
- BAC0 GitHub ("Library depending on BACpypes3"): https://github.com/ChristianTremblay/BAC0

---

## Bezug zur Roadmap

- **S7 (diese Datei):** Entscheidung liegt vor; Checkbox bleibt offen bis zur Nutzerbestätigung.
- **S8:** setzt diese Entscheidung um — Discovery/Import als Mapping-Vorstufe, read-only, nur Kandidaten.
- **S5/S6:** bleiben der einzige Aktivierungspfad (Preview, Validierung, Backup, Audit).
- **EDGE_INTEGRATION_CONTRACT.md:** Schreibpfad-Regeln bleiben unangetastet; Fremd-Stack niemals schreibend.
