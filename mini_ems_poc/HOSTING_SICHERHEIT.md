# Mini EMS – Hosting und Sicherheitsgrenze

Diese Datei erledigt zwei Dinge:

- **Teil 1 (H1 aus `ROADMAP.md`)** legt das Zielbild und die Sicherheitsgrenze fest: wer UI, Runtime-Dateien,
  Standortkonfiguration, Logs und Betriebsdaten sehen bzw. ändern darf.
- **Teil 2 (Konzept zu To-do 3 aus `ROADMAP.md`)** ist die Entscheidungsvorlage für das erste sichere
  Online-Hosting: zwei konkrete Pfade, eine Empfehlung und eine Checkliste für den Piloten.

Grundsatz wie im `EDGE_INTEGRATION_CONTRACT.md`: **Der Code ist die Wahrheit.** Die Endpunkt-Listen und
Aussagen zu Lese-/Schreibpfaden sind aus `mini_ems_runtime/http_api.py`, `config.json` und dem
Rollenmodell in `PRODUCT_UX_KONZEPT.md` (Abschnitt 3) abgeleitet. Weicht diese Datei vom Code ab, gilt
der Code, und diese Datei ist zu korrigieren.

Das Rollenmodell (Viewer / Operator / Admin) ist fachlich in `PRODUCT_UX_KONZEPT.md` Abschnitt 3 definiert.
Diese Datei setzt es auf die konkreten Dateien, Netzwerkgrenzen und Endpunkte um; sie erfindet keine neue
Rollenlogik.

---

## Teil 1 – Zielbild und Sicherheitsgrenze (H1)

### 1.1 Festlegung

Mini EMS läuft auf **kundeneigener IPC-Hardware** und bleibt der lokale Anlagen-Gateway. Es wird aber
nicht als frei einsehbarer Entwicklerordner ausgeliefert, und die Anlagen-API wird nicht offen ins Netz
gestellt. Konkret gilt:

- Der Betriebspfad ist die **IPC vor Ort**. `config.json` bleibt der reale IPC-/Anlagenpfad,
  `config.local.json` bleibt ausschließlich der Laptop-/Simulationspfad. Beide werden nie vermischt.
- Der Zugriff auf **UI und API** bleibt auf **Kundennetz, VPN oder Secomea** beschränkt. Es gibt keine
  direkte Erreichbarkeit der Anlagen-API aus dem offenen Internet.
- Die API bindet heute laut `config.json` an `192.168.244.10:8090` (die EMS-LAN-IP des IPC), lokal an
  `127.0.0.1:8090`. Beides ist bewusst kein `0.0.0.0` und keine Internet-Adresse.
- Das ausgelieferte Zielformat ist ein **versioniertes Release-Paket** statt eines Git-Checkouts
  (Detailschritt: H2 in `ROADMAP.md`, hier noch offen). Ziel ist, dass ein normaler Windows-Nutzer nicht
  beiläufig den gesamten Python-Quellcode lesen kann.

### 1.2 Sichtbarkeits- und Änderungsmatrix

Vier Zugriffsklassen. Die Rollen **Viewer / Operator / Admin** entsprechen dem UX-Rollenmodell
(`PRODUCT_UX_KONZEPT.md`, Abschnitt 3); "normaler Windows-Nutzer" ist die Person, die nur am
Windows-Rechner sitzt, ohne Mini-EMS-Rolle.

| Ressource | Normaler Windows-Nutzer (kein Mini-EMS-Zugang) | Viewer (Betreiber/Gast, read-only Netz) | Operator (Betreiber vor Ort) | Admin (wir / interner Betrieb) |
|---|---|---|---|---|
| **UI – Dashboard, Analyse, Berichte, Systemzustand** | nur, wenn im Kundennetz/VPN und Zugangsdaten vorhanden (sonst gar nicht) | sehen | sehen | sehen |
| **UI – Diagnose (Preisprüfung, technische Details)** | nein | nein | sehen + ausführen | sehen + ausführen |
| **UI – Einstellung Preissteuerung (Mindestdauer Preisfenster)** | nein | nein | ändern | ändern |
| **Standortkonfiguration `config.json` (Grenzwerte, Datenpunkte, `api.host`)** | nein (Dateirechte, Ziel H3) | nein | nein | lesen + ändern (lokal/administrativ) |
| **Runtime-Dateien (`runtime/state.json`, `runtime/health.json`)** | nein direkt; `health.json`-Inhalte nur mittelbar über das UI | Inhalte über UI in Betreiber-Sprache | Inhalte über UI + Diagnose | Dateien direkt |
| **Logs (`logs/mini_ems.log`)** | nein | nein | nein (nur aufbereitete Kommunikationshinweise im UI) | lesen |
| **Betriebsdaten SQLite (`data/runtime/mini_ems.sqlite`)** | nein direkt | Auswertungen über Historie/Reports im UI | Auswertungen über UI | Datei direkt |
| **Schreibfreigaben an der Anlage / Safety-Flags (`runtime.real_writes_enabled`, `outputs.*`)** | nein | nein | nein | nur lokal/administrativ auf der IPC, nie über Netzwerkzugriff |

Kurzfassung der Grenzen:

- **Normale Windows-Nutzer** sollen das UI nur über den freigegebenen Netzzugang öffnen können und keine
  Runtime-Dateien, Konfiguration oder Logs direkt durchsuchen oder ändern (Umsetzung der Dateirechte:
  H3). Sie sehen keinen Quellcode-Ordner.
- **Viewer** sehen echte Betriebsdaten, Historie und Berichte, aber keine Diagnose, keine Einstellungen,
  keine Systemdateien. Der erste geschützte Netzwerkzugriff (H5) ist genau diese Rolle.
- **Operator** darf zusätzlich die Preisprüfung ausführen (aktiver Lesezugriff auf die Anlage) und die
  Mindestdauer der Preisfenster einstellen – beides bleibt zunächst dem lokalen bzw. ausdrücklich
  freigegebenen Zugriff vorbehalten, nicht dem read-only Online-Pfad.
- **Admin** sieht und ändert Standortkonfiguration, Logs, Datenbank und Safety-Flags – ausschließlich
  lokal/administrativ auf der IPC, nie über den Netzwerkzugriff.

### 1.3 Ehrliche Abgrenzung (Risiko-Leitplanke aus H1)

Diese Festlegung beschreibt **professionellen Betrieb ohne offenen Source-Checkout und ohne öffentlich
erreichbare Anlagen-API**. Sie ist ausdrücklich **kein** Versprechen von Geheimhaltung gegenüber einer
Person mit Administrator-Rechten auf der kundeneigenen IPC.

- Wer lokalen Administrator-Zugriff auf die IPC hat, kann prinzipiell Prozesse, Dateien und Datenbank
  einsehen. Das ist bei kundeneigener Hardware nicht verhinderbar und wird hier auch nicht behauptet.
- Ein Release-Paket (H2) und Dateirechte (H3) senken die **beiläufige** Einsicht durch normale Nutzer.
  Sie sind **kein** DRM und **kein** Schutz gegen entschlossene Extraktion. PyInstaller-Artefakte sind
  extrahierbar; Nuitka erschwert das, verhindert es aber nicht.
- Die Sicherheitsgrenze ist eine **Netzwerk- und Zugriffsgrenze** (Kundennetz/VPN/Secomea, read-only
  zuerst, Login später), keine kryptografische Uneinsehbarkeit auf dem Zielgerät.
- Es werden keine Zusagen formuliert, die auf kundeneigener Hardware mit Admin-Zugriff nicht haltbar
  sind. Wo Schutz an Windows-Dateirechten oder an einem Reverse Proxy hängt, wird das als solches benannt
  (Detailschritte H3, H4, H6 in `ROADMAP.md`).

---

## Teil 2 – Erstes sicheres Online-Hosting (Konzept zu To-do 3)

Ziel von To-do 3: Echte IPC-Daten sollen von einem **zweiten Rechner** aus sichtbar werden, ohne die
Anlagen-API öffentlich freizugeben und ohne Schreibfunktionen online zu stellen. Diese Datei liefert das
geforderte **dokumentierte Minimalkonzept** als Entscheidungsvorlage; der reale Nachweis auf einem
zweiten Rechner am Standort ist bewusst noch offen (siehe `ROADMAP.md`, To-do 3).

### 2.1 Endpunkt-Einstufung (Basis für beide Pfade)

Abgeleitet aus `mini_ems_runtime/http_api.py`. Nur die als **read-only** eingestuften Endpunkte dürfen im
Online-Pfad erreichbar sein. Die als **sperren** markierten bleiben lokal/administrativ bzw. auf die
Operator-Rolle beschränkt.

**Read-only (freigebbar, reine Anzeige/Datenabruf):**

| Endpunkt | Zweck | Wirkung |
|---|---|---|
| `GET /`, `/dashboard`, `/index.html` | Dashboard-Seite | statische Auslieferung |
| `GET /dashboard.css`, `/dashboard.js`, `/vendor/*` | UI-Assets | statische Auslieferung |
| `GET /api/status` | Anlagenzustand (`health.json`, `state.json`, Preis-Cache, Plan, letzte Zyklen) | liest nur Dateien/DB |
| `GET /api/spotmarket/windows` | aktueller Preisfenster-Plan | liest Datei |
| `GET /api/config/spotmarket-lockout` | aktuelle Einstellung der Preissteuerung (nur Anzeige) | liest Einstellung, schreibt nichts |
| `GET /api/config/site` | Standortkonfiguration als geschützte Anzeige (Admin-Token wird ausgeblendet) | liest `config.json`, schreibt nichts |
| `GET /api/history` | Messwert-Historie inkl. Rollups | liest DB |
| `GET /api/cycles` | letzte Zyklen | liest DB |
| `GET /api/report/daily`, `/api/report/daily.csv` | Tagesbericht JSON/CSV | liest DB |
| `GET /api/report/studio` | Report-Studio-Kennzahlen | liest DB |
| `GET /api/report/html`, `/api/report/pdf` | konfigurierbarer Bericht HTML/PDF | liest DB, rendert |
| `GET /api/weather` | Wetter-Kachel (Open-Meteo-Cache) | liest Cache; ruft nur Wetterdienst, nie die Anlage |

**Zu sperren (nicht in den Online-Pfad):**

| Endpunkt | Warum gesperrt |
|---|---|
| `GET /api/diagnostics/read` | löst einen **aktiven Live-Lesezugriff auf die Anlage** aus (BACnet-Read über `read_diagnostics`); im Rollenmodell Operator, nicht Viewer – im read-only Modus (H5) von außen nicht erreichbar |
| `POST /api/config/spotmarket-lockout` | **schreibt in `config.json`** (`_persist_min_consecutive_quarters`) und ändert das Planungsverhalten; Operator/Admin, kein Online-Viewer |
| `POST /api/config/site/validate` | Validierung eines Konfigurations-Entwurfs (S5/H9); zwar nur prüfend, aber ein POST-Schreibpfad-Muster und Teil des Konfigurationsflusses; nicht in den Online-Pfad |
| `POST /api/config/site/save` | **speichert die Standortkonfiguration** (Admin-Token, Backup, Neustartbedarf); rein administrativ, nie über den Netzwerkzugriff |
| `POST /api/config/mapping/preview` | Vorschau/Validierung eines Mapping-Entwurfs (S5); POST-Konfigurationspfad, nicht für den read-only Viewer |
| `POST /api/report/preview` | zwar nur DB-Lesen, aber ein POST-Schreibpfad-Muster; für den read-only Pilot nicht nötig und bewusst außerhalb gehalten |

Hinweis zur Robustheit: Die Sperre ist **positiv/deny-by-default** umgesetzt (nur GET-Methoden werden
grundsätzlich durchgelassen; `POST`/`PUT`/`DELETE` sind generell gesperrt), nicht als Blocklist einzelner
Pfade. So bleiben auch später neu hinzukommende Schreib-Endpunkte standardmäßig draußen. Die einzige
zusätzliche Ausnahme ist der aktive Anlagen-Read `GET /api/diagnostics/read`, der trotz GET explizit
gesperrt wird.

**Serverseitiger Read-only-Modus (`api.read_only`, umgesetzt für H5).** Die Endpunkt-Einstufung dieses
Abschnitts wird jetzt direkt in der HTTP-API durchgesetzt und hängt nicht mehr allein an einem vorgelagerten
Reverse Proxy. Der Schlüssel `api.read_only` (Boolean, Default `false`) steht im `api`-Block der
Konfiguration. Ist er `true`, lehnt die API an **einer zentralen Stelle im Request-Handling** alle nicht-GET-
Methoden sowie `GET /api/diagnostics/read` mit `HTTP 403` und einem kurzen deutschen JSON-Hinweis ab
(`{"error": "read_only_mode", "message": "Diese Funktion ist über den Netzwerkzugriff nicht verfügbar. …"}`).
Alle read-only Endpunkte oben bleiben erreichbar. Zusätzlich meldet `GET /api/status` das Feld
`api_read_only: true`, damit das UI den Modus erkennen kann. Default `false` lässt das bisherige Verhalten
unverändert; `config.json`/`config.local.json` werden dafür nicht geändert – der Schlüssel wird nur dort
gesetzt, wo der read-only Netzbetrieb (Pilot-Pfad a) gewünscht ist.

Aktivierung für den Pilot-Pfad (a): Im `api`-Block der auf der IPC verwendeten `config.json` ergänzen:

```json
"api": {
  "host": "192.168.244.10",
  "port": 8090,
  "read_only": true
}
```

Anschließend Mini EMS neu starten (der Schlüssel wird beim Start geladen). Danach greift die read-only
Grenze serverseitig, unabhängig davon, ob zusätzlich ein Reverse Proxy davorsteht.

### 2.2 Pfad (a) – Secomea/VPN-Zugriff auf das bestehende Dashboard

**Architekturskizze (Text):**

```text
Zweiter Rechner (Betreiber/Gast)
  -> Secomea-Client / VPN-Tunnel ins Kundennetz
  -> IPC im Kundennetz, Mini-EMS-API an 192.168.244.10:8090 (unverändert)
  -> bestehendes Dashboard + read-only Endpunkte
```

Die Daten verlassen die IPC nicht dauerhaft; der zweite Rechner klinkt sich per gesichertem Tunnel in das
Kundennetz ein und öffnet dasselbe Dashboard wie vor Ort.

**IPC-Konfiguration / Firewall:**

- `api.host` bleibt auf der EMS-LAN-IP `192.168.244.10` (nicht `0.0.0.0`, nicht Internet). Keine
  Portweiterleitung von `8090` an ein WAN-Interface.
- Windows-Firewall: Port `8090` nur aus dem Kundennetz/VPN-Bereich erreichbar, nicht aus dem Internet.
- Secomea-Freigabe auf genau den einen Dienst (`192.168.244.10:8090`) begrenzen; kein pauschaler
  Netzzugang, wo nicht nötig.
- Die Anlagen-Controller (`192.168.244.30/.40:47808`, BACnet) werden **nicht** in den Fernzugriff
  aufgenommen. Fernzugriff endet an der Mini-EMS-API.

**Freigegebene Endpunkte:** die read-only-Liste aus 2.1. Da hier das **komplette** Dashboard erreichbar
ist, ist zusätzlich sicherzustellen, dass Diagnose-/Einstell-Aktionen für Nur-Viewer nicht ausgelöst
werden können (siehe Grenzen).

**Aufwand:** gering (S). Secomea/VPN ist bereits vorhanden; im Kern nur Firewall-/Freigaberegeln prüfen
und den Zugriff dokumentieren. Keine Codeänderung.

**Risiken / Grenzen:**

- Mit `api.read_only: true` (siehe 2.1) sind die schreibenden/aktiven Endpunkte serverseitig gesperrt und
  liefern über denselben Port `HTTP 403`. Ohne diesen Schalter reicht der Pfad den **kompletten** Dienst
  durch: die schreibenden/aktiven Endpunkte (`/api/diagnostics/read`, `POST /api/config/spotmarket-lockout`,
  die `POST /api/config/site/*`- und `POST /api/config/mapping/preview`-Konfigurationspfade,
  `POST /api/report/preview`) sind dann technisch erreichbar, und nur die **organisatorische** Vergabe des
  VPN-Zugangs trennt Viewer von Operator. Für den Pilot-Pfad (a) wird deshalb `api.read_only: true` gesetzt;
  eine echte Rollen-/Login-Trennung bleibt H6 vorbehalten.
- Jeder mit VPN-Zugang sieht das Dashboard so, wie es ist; es gibt heute keine UI-seitige Rollentrennung.
- Kein zusätzlicher Login vor dem Dashboard, solange H6 nicht umgesetzt ist – der Schutz ist der
  VPN-/Secomea-Zugang selbst.

### 2.3 Pfad (b) – Read-only Export an einen kleinen externen Hosting-Punkt mit Login

**Architekturskizze (Text):**

```text
IPC (Mini EMS, Anlagen-Gateway)
  -> kleiner Export/Push nur der freigegebenen read-only Daten (Status, Historie, Reports)
  -> ausgehende Verbindung (IPC -> Hosting), keine eingehende Freigabe auf der IPC
  -> kleiner externer Hosting-Punkt mit HTTPS + Login
  -> Zweiter Rechner (Betreiber/Gast) über Internet, aber hinter Login
```

Entscheidend: Die IPC **veröffentlicht** ausgewählte read-only Daten nach außen (Push/Export), statt
ihren Port erreichbar zu machen. Der Hosting-Punkt bekommt nie Zugriff auf die Anlagen-API oder BACnet.

**IPC-Konfiguration / Firewall:**

- `api.host` bleibt lokal (`192.168.244.10` bzw. `127.0.0.1`); es wird **keine** eingehende Freigabe
  eingerichtet. Nur eine **ausgehende** Verbindung von der IPC zum Hosting-Punkt.
- Der Export nutzt ausschließlich die read-only-Datenquellen (`/api/status`, `/api/history`,
  `/api/report/*` bzw. direkt `health.json`/SQLite-Rollups). Schreib-/Diagnose-Endpunkte werden gar
  nicht erst exportiert.
- Kein Durchreichen von `/api/diagnostics/read` und keinerlei `POST`-Pfad nach außen.

**Freigegebene Endpunkte / Daten:** nur die read-only-Liste aus 2.1, und davon nur die Dateninhalte, die
für Monitoring nötig sind (Status, Historie, Berichte, Wetter). Der externe Punkt bietet **keine**
Konfigurations- oder Diagnosefunktion an.

**Aufwand:** mittel (M). Es braucht einen kleinen Exporter oder Reverse-/Push-Mechanismus, den externen
Hosting-Punkt, HTTPS-Zertifikat und einen Login. Mehr bewegliche Teile als Pfad (a), dafür eine echte
Trennung zwischen "was die Anlage kann" und "was online sichtbar ist".

**Risiken / Grenzen:**

- Datenhaltung außerhalb des Kundennetzes: Es muss geklärt werden, welche Daten das Kundennetz verlassen
  dürfen (Betreiberfreigabe, Datenschutz). Für reine Betriebs-/Messdaten meist unkritisch, aber zu
  dokumentieren.
- HTTPS und Login müssen sauber betrieben werden (Zertifikat, Passwort-Rotation) – sonst verschiebt man
  das Risiko nur nach außen.
- Der Exporter darf keine Rückkanäle zur Anlage öffnen; er ist strikt einseitig (IPC -> Hosting).
- Aktualität: Exportierte Daten sind so frisch wie der Push-Takt; das ist bei Monitoring akzeptabel, aber
  kein Live-Regelbild.

### 2.4 Empfehlung

**Zuerst Pfad (a): Secomea/VPN-Zugriff auf das bestehende Dashboard.** Begründung:

- Der Fernzugriff (Secomea/VPN) ist bereits vorhanden; der Pilot ist mit reiner Firewall-/Freigabe-Prüfung
  und Dokumentation erreichbar, **ohne Codeänderung** und ohne Daten aus dem Kundennetz zu exportieren.
- Er erfüllt die Definition of Done von To-do 3 am direktesten: echte IPC-Daten auf einem zweiten Rechner,
  ohne die Anlagen-API öffentlich freizugeben, mit Schreibfunktionen außerhalb des vorgesehenen Nutzens.
- Er hält die Sicherheitsgrenze ein: keine Internet-Portfreigabe von `8090`, keine Vermischung von
  Simulations- und IPC-Pfad, keine Änderung an `runtime.real_writes_enabled`.

Pfad (b) ist die **zweite Ausbaustufe**, sobald echtes Hosting außerhalb des Kundennetzes gewünscht ist
oder mehreren externen Zuschauern ohne VPN-Client Zugriff gegeben werden soll. Er setzt die
read-only-Trennung technisch sauberer um, kostet aber mehr Aufwand und wirft die Frage der
Datenauslagerung auf.

### 2.5 Schritt-für-Schritt-Checkliste für den Piloten (Pfad a)

1. Bestätigen, dass `api.host` in `config.json` auf `192.168.244.10` steht (nicht `0.0.0.0`, nicht
   Internet) – **nur lesen**, nicht ändern.
2. Windows-Firewall prüfen: Port `8090` nur aus Kundennetz/VPN erreichbar, keine WAN-Weiterleitung.
3. Secomea-/VPN-Freigabe auf genau `192.168.244.10:8090` begrenzen; BACnet-Ports (`47808`) nicht
   freigeben.
4. Vom zweiten Rechner über VPN/Secomea das Dashboard öffnen und prüfen, dass echte IPC-Daten erscheinen
   (Status, Historie, Berichte).
5. `api.read_only: true` im `api`-Block der `config.json` setzen und Mini EMS neu starten. Danach prüfen,
   dass `GET /api/diagnostics/read` und die `POST`-Endpunkte (`/api/config/spotmarket-lockout`,
   `/api/config/site/validate`, `/api/config/site/save`, `/api/config/mapping/preview`,
   `/api/report/preview`) über diesen Pfad `HTTP 403` liefern und `GET /api/status` `api_read_only: true`
   meldet. Solange keine Rollenschicht (H6) existiert, den VPN-Zugang zusätzlich nur an
   vertrauenswürdige Personen vergeben.
6. Zugriff und Freigabe im Betriebslog/Zugriffskonzept festhalten (Vorbereitung H8).
7. **Definition-of-Done-Nachweis (durch den Betreiber/Nutzer vor Ort):** Ein zweiter Rechner am Standort
   zeigt echte IPC-Daten; Schalt-/Konfigurationsaktionen sind über diesen Pfad nicht vorgesehen. Dieser
   Nachweis kann nur am realen Standort erbracht werden und bleibt in `ROADMAP.md` (To-do 3) offen.

### 2.6 Verbleibende offene Entscheidungen des Betreibers/Nutzers

Diese Punkte bleiben bewusst offen und sind in `ROADMAP.md` als eigene Schritte geführt:

- **HTTPS/Login-Verfahren** vor dem Dashboard (Reverse Proxy, Zertifikat, Erstpasswort und Rotation) –
  Querverweis **H4** (API intern binden, UI über geschützten Zugriff) und **H6** (Login und Rollenlogik).
- **Echte read-only Erzwingung im Netz** (Allowlist der Endpunkte, Sperre schreibender Pfade auf
  Proxy-Ebene) – Querverweis **H5** (Read-only Netzwerkmodus zuerst).
- **Rollen viewer/operator/admin** als technische Umsetzung des UX-Rollenmodells – Querverweis **H6**;
  fachliche Vorlage: `PRODUCT_UX_KONZEPT.md` Abschnitt 3.
- **Bei Pfad (b) zusätzlich:** welche Daten das Kundennetz verlassen dürfen und wo der Hosting-Punkt
  betrieben wird.

### 2.7 Harte Leitplanken (gelten für beide Pfade)

- **Keine Internet-Portfreigabe von `8090`** und keine Portweiterleitung der Anlagen-API ins offene Netz.
- **Keine Vermischung von Simulationspfad und echter IPC:** `config.local.json` bleibt Laptop/Simulation,
  `config.json` bleibt IPC/Anlage.
- **Schreibfunktionen bleiben außerhalb des Online-Pfads:** die aktiven/schreibenden Endpunkte aus 2.1
  werden online nicht angeboten.
- **Keine Änderung an `runtime.real_writes_enabled`** und keinen anderen Safety-Flags durch das
  Online-Hosting. Der Schreibpfad zur Anlage bleibt lokaler Admin-Betrieb auf der IPC.

---

## Querverweise

- `ROADMAP.md` – strategische To-do-Linie "Geschütztes Kundenhosting" (H1–H9) und To-do 3
- `PRODUCT_UX_KONZEPT.md`, Abschnitt 3 – fachliches Rollenmodell Viewer/Operator/Admin
- `EDGE_INTEGRATION_CONTRACT.md` – Lese-/Schreibrechte, Safety-Flags, Ausfallverhalten
- `MINI_EMS_ANLEITUNG.md` – Betrieb, `api.host`-Bindung, Endpunktübersicht
- `mini_ems_runtime/http_api.py` – tatsächliche Endpunkte (Quelle der Einstufung in 2.1)
- `UPDATE_WARTUNG.md` – Update-, Healthcheck- und Rollback-Ablauf (H7), Verantwortlichkeiten remote
  (Secomea/VPN) vs. vor Ort, konsistent zur Sichtbarkeits-/Änderungsmatrix in Teil 1
