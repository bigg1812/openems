# Mini EMS – Hosting und Sicherheitsgrenze

Diese Datei erledigt vier Dinge:

- **Teil 1 (H1 aus `ROADMAP.md`)** legt das Zielbild und die Sicherheitsgrenze fest: wer UI, Runtime-Dateien,
  Standortkonfiguration, Logs und Betriebsdaten sehen bzw. ändern darf.
- **Teil 2 (Konzept zu To-do 3 aus `ROADMAP.md`)** ist die Entscheidungsvorlage für das erste sichere
  Online-Hosting: zwei konkrete Pfade, eine Empfehlung und eine Checkliste für den Piloten.
- **Teil 3 (H3 aus `ROADMAP.md`)** setzt die Sichtbarkeits-/Änderungsmatrix aus Teil 1 in ein konkretes
  Installationslayout und Windows-Dateirechte um: wo App-Dateien und Standortdaten auf der Kunden-IPC
  liegen, wer welche Rechte auf welchen Ordner bekommt, und mit welchen `icacls`-Kommandos das umgesetzt
  wird.
- **Teil 4 (H4 aus `ROADMAP.md`)** bindet die API intern und stellt das UI über einen geschützten Zugriff
  bereit: eine Bindungs-Matrix (wann `127.0.0.1`, wann EMS-LAN-IP, warum nie `0.0.0.0`), eine
  Reverse-Proxy-Empfehlung (Caddy) mit kopierfertigen Vorlagen unter `proxy/` und eine
  Verifikations-Checkliste für den Standort.

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

*Stand: 2026-07-07 – abgeglichen mit `mini_ems_runtime/http_api.py` inkl. Commit `e5417edd2`
(Pointlist-Import-Flow) und der Mapping-Aktivierung; Testabdeckung in `tests/test_read_only_api.py`.*

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
| `POST /api/config/pointlist/import` | parst eine hochgeladene BACnet-Punkteliste (CSV/TSV/XLSX) zu Mapping-Kandidaten; schreibt zwar nicht in `config.json`, ist aber Teil des Konfigurations-Editors (S5/S6) und kein Viewer-Endpunkt |
| `POST /api/config/discovery/bacnet/preview` | löst optional eine **echte BACnet-Discovery** (`who_is`/`read_property`) gegen die Anlage aus, sobald BACpypes3 installiert ist – aktiver Anlagenzugriff wie `GET /api/diagnostics/read`, deshalb gesperrt |
| `POST /api/config/mapping/activate` | **sicherheitskritischster Endpunkt:** aktiviert einen Mapping-Patch, schreibt `config.json`, legt Backup/Draft/Audit-Log an und lädt die Konfiguration neu; nur mit Admin-Token, nie über den Netzwerkzugriff |

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
  `POST /api/report/preview`, die Config-Editor-Pipeline `POST /api/config/pointlist/import` und
  `POST /api/config/discovery/bacnet/preview` sowie insbesondere `POST /api/config/mapping/activate`)
  sind dann technisch erreichbar, und nur die **organisatorische** Vergabe des
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

## Teil 3 – Dateischutz und Installationslayout auf der IPC (H3)

Ziel von H3: Die Sichtbarkeits-/Änderungsmatrix aus Teil 1.2 ist heute nur eine fachliche Festlegung.
Dieser Teil übersetzt sie in ein konkretes Installationsverzeichnis-Layout und Windows-`icacls`-Rechte,
konsistent mit dem in H2 entschiedenen Release-Paket (One-Dir-PyInstaller, siehe `packaging/README.md`)
und dem Update-Ablauf in `UPDATE_WARTUNG.md`. Die reale Anwendung auf der Kunden-IPC ist damit noch nicht
erbracht (siehe Migrationshinweis 3.5 und `ROADMAP.md`, H3-Stand); dieser Abschnitt ist das umsetzungsreife
Konzept dafür.

### 3.1 Ziel-Installationslayout

Grundprinzip: **App-Dateien** (aus dem Release-Paket, bei jedem Update ersetzt) und **Standortdaten**
(bleiben über Updates hinweg bestehen) liegen in getrennten Windows-Wurzelverzeichnissen mit
unterschiedlichem Schreibschutz – nicht nur in getrennten Unterordnern desselben Projektbaums wie heute.

```text
C:\Program Files\MiniEMS\                     <- App-Dateien (nur Administratoren schreibbar)
|-- mini_ems.exe
|-- _internal\                                 (PyInstaller-Laufzeit)
|-- dashboard\                                  (UI-Assets, inkl. vendor\)
|-- mini_ems_runtime\templates\report.html.j2
|-- sim\                                        (optional, nur Testlauf)
|-- VERSION
|-- SHA256SUMS
`-- RELEASE_HINWEISE.md

C:\ProgramData\MiniEMS\                        <- Standortdaten (Task-Benutzer schreibt, normale Nutzer lesen/schreiben nicht)
|-- config.json                                 (Standortkonfiguration, Admin-Arbeit)
|-- data\
|   |-- runtime\mini_ems.sqlite                 (Betriebsdaten-Historie)
|   `-- spotmarket\
|       |-- spotmarket_manual_override.json
|       |-- spotmarket_price_cache.json
|       `-- spotmarket_tomorrow_windows.json
|-- logs\
|   |-- mini_ems.log
|   `-- mini_ems_stdout.log
|-- runtime\
|   |-- state.json
|   `-- health.json
`-- backup\<zeitstempel>\                       (Backups aus UPDATE_WARTUNG.md Abschnitt 2.3)
```

**Begründung der Trennung:**

- `C:\Program Files\MiniEMS` ist unter Windows standardmäßig nur für Administratoren beschreibbar;
  normale Benutzer haben dort Lese-, aber kein Schreibrecht. Das passt genau zur App-Dateien-Rolle: Sie
  werden nur bei einem kontrollierten Update (Admin-Vorgang, siehe `UPDATE_WARTUNG.md` Abschnitt 2)
  ersetzt, nie im Betrieb verändert.
- `C:\ProgramData\MiniEMS` ist der vorgesehene Windows-Ort für maschinenweite Anwendungsdaten, die kein
  Benutzerprofil sind. Das passt zur Standortdaten-Rolle: Der laufende Task schreibt hier laufend
  (Logs, DB, `runtime/state.json`, `runtime/health.json`, Spotmarkt-Dateien), Admin liest/ändert hier
  gezielt (`config.json`), normale Benutzer brauchen hierauf keinen Zugriff.
- Diese Trennung ist **identisch** zur App-Dateien-/Standortdaten-Liste aus `UPDATE_WARTUNG.md`
  Abschnitt 1.3: Was dort als "App-Dateien (werden bei jedem Update ersetzt)" gilt, liegt im
  Ziel-Layout unter `C:\Program Files\MiniEMS`; was dort als "Standortdaten (bleiben unangetastet)" gilt
  (`config.json`, `data/runtime/`, `data/spotmarket/spotmarket_manual_override.json`, `logs/`, `runtime/`),
  liegt unter `C:\ProgramData\MiniEMS`. Das Ziel-Layout erfindet keine neue Einteilung, es gibt der
  bestehenden Einteilung nur zwei physisch getrennte, unterschiedlich berechtigte Wurzelverzeichnisse.
- Ausnahme `sim/`: laut `UPDATE_WARTUNG.md` 1.3 ist `sim/` App-seitig (mitgelieferte Beispieldaten,
  "nur für lokale Simulation relevant, nicht IPC-Betriebsdaten") und bleibt deshalb unter
  `C:\Program Files\MiniEMS\sim`, nicht unter `ProgramData`.

**Wie die Runtime das findet:** Der Betriebspfad bleibt unverändert das, was H2 und `UPDATE_WARTUNG.md`
bereits festlegen: `config.json` liegt außerhalb des Release-Pakets und wird als **Argument beim Start**
übergeben (`--config <pfad>\config.json`), heute über `run_mini_ems.cmd` bzw. den davon gestarteten
Python-/Executable-Aufruf. Im Ziel-Layout wäre das Argument `--config C:\ProgramData\MiniEMS\config.json`.

Alle übrigen Datenpfade sind **config-relativ**, nicht fest verdrahtet auf einen bestimmten
Windows-Ordner. Das ist an `mini_ems_runtime/config.py` nachvollziehbar:

```python
def resolve_path(self, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return self.base_dir / path
```

`base_dir` wird beim Laden gesetzt als `config_path.resolve().parent` (`load_config`, `config.py`) –
also der Ordner, in dem `config.json` liegt. `config.json` selbst enthält für Logs, Datenbank, State,
Health und Spotmarkt-Dateien relative Pfade (`"sqlite_file": "data/runtime/mini_ems.sqlite"`,
`"state_file": "runtime/state.json"`, `"health_file": "runtime/health.json"`, `logging.directory: "logs"`,
`"spotmarket_plan_file": "data/spotmarket/..."` usw., siehe `config.json`). Daraus folgt für das
Ziel-Layout: Wenn `config.json` unter `C:\ProgramData\MiniEMS\config.json` liegt und die relativen Pfade
unverändert bleiben, landen `data\`, `logs\` und `runtime\` automatisch als Unterordner von
`C:\ProgramData\MiniEMS` – exakt wie oben skizziert, **ohne Code- oder Config-Feld-Änderung**, nur durch
die Wahl des Installationsorts von `config.json`. App-Ressourcen (`dashboard/`, Templates) löst die
Runtime separat über `mini_ems_runtime/resources.py` neben dem Executable auf (`sys.frozen`-Fall, siehe
`packaging/README.md`), landen also unabhängig davon korrekt unter `C:\Program Files\MiniEMS`.

### 3.2 Rechtemodell

Vier Konten-/Rollentypen, konsistent zur Sichtbarkeitsmatrix aus Teil 1.2: **normale Windows-Benutzer**
öffnen das UI ausschließlich über HTTP (Kundennetz/VPN, siehe Teil 2) und brauchen dafür **keine**
Dateisystemrechte auf Runtime-Dateien, Konfiguration oder Logs – die Matrix aus Teil 1.2 verlangt das
bereits fachlich, dieser Abschnitt setzt es als Dateirecht um.

| Ordner | SYSTEM | Administratoren | Task-/Dienst-Benutzer (`MiniEmsSvc`) | Normale Benutzer |
|---|---|---|---|---|
| `C:\Program Files\MiniEMS` (App-Dateien) | Lesen + Ausführen | Vollzugriff | Lesen + Ausführen | Lesen + Ausführen (Standard-Vererbung von `Program Files`) |
| `C:\ProgramData\MiniEMS` (Wurzel) | Vollzugriff | Vollzugriff | Lesen + Ausführen | kein Zugriff |
| `C:\ProgramData\MiniEMS\config.json` | Lesen | Ändern | Lesen | kein Zugriff |
| `C:\ProgramData\MiniEMS\data\` | Vollzugriff | Vollzugriff | Ändern (Lesen/Schreiben) | kein Zugriff |
| `C:\ProgramData\MiniEMS\logs\` | Vollzugriff | Vollzugriff | Ändern (Lesen/Schreiben) | kein Zugriff |
| `C:\ProgramData\MiniEMS\runtime\` | Vollzugriff | Vollzugriff | Ändern (Lesen/Schreiben) | kein Zugriff |
| `C:\ProgramData\MiniEMS\backup\` | Vollzugriff | Vollzugriff | kein Zugriff (Backups sind Admin-Arbeit, siehe `UPDATE_WARTUNG.md` 2.3) | kein Zugriff |

Begründung je Konto:

- **SYSTEM** braucht Zugriff, weil der geplante Task laut heutigem `windows/install_task.ps1` mit
  `-UserId "NT AUTHORITY\SYSTEM"` läuft (nur lesend referenziert; an dieser Datei arbeitet parallel eine
  andere Session). Falls künftig auf einen dedizierten Dienstkonto-Ansatz umgestellt wird (Spalte
  "Task-/Dienst-Benutzer"), gilt dieselbe Rechtezuteilung für dieses Konto statt für SYSTEM – das
  Rechtemodell ist bewusst so aufgebaut, dass beide Betriebsarten (SYSTEM-Task heute, dedizierter
  Dienstbenutzer später) ohne Änderung der Ordnerstruktur funktionieren.
- **Administratoren** brauchen Vollzugriff auf `ProgramData\MiniEMS`, weil Config-Änderungen, Backups,
  Log-Einsicht und Datenbankzugriff laut Teil 1.2 ausschließlich Admin-Aufgaben sind ("Admin sieht und
  ändert Standortkonfiguration, Logs, Datenbank und Safety-Flags – ausschließlich lokal/administrativ").
- **Task-/Dienst-Benutzer** braucht **Lesen** auf `config.json` (Startparameter, Netzwerk-/Punktkonfiguration
  lesen) und **Schreiben** auf `data\`, `logs\`, `runtime\` (dort entstehen SQLite-Journal-Dateien,
  Log-Zeilen, `state.json`/`health.json` bei jedem Zyklus). Kein Schreibrecht auf `config.json` selbst
  (Config-Änderung ist Admin-Vorgang, siehe H9) und kein Zugriff auf `backup\` (Backups sind Teil des
  Admin-gesteuerten Update-Ablaufs, nicht der laufenden Runtime).
- **Normale Benutzer** bekommen laut Teil 1.2 ausdrücklich **keinen** direkten Zugriff auf Runtime-Dateien,
  Konfiguration oder Logs. Sie sehen `health.json`-Inhalte nur mittelbar über das UI (`/api/status`), nie
  die Datei selbst. Deshalb: kein Eintrag, keine vererbte ACL auf `ProgramData\MiniEMS` – Vererbung von
  `ProgramData` wird bewusst gekappt (siehe 3.3), sonst würde die Standard-Windows-ACL von `ProgramData`
  (die "Benutzer"-Gruppe hat dort im Regelfall Lesezugriff) genau das Gegenteil bewirken.

### 3.3 Konkrete PowerShell-/`icacls`-Kommandos

Diese Kommandos sind als Kopiervorlage für die reale IPC gedacht; sie ändern **keine** Datei in diesem
Repository und sind unabhängig von `windows/install_task.ps1`. Auszuführen als Administrator auf der
Kunden-IPC, nach dem Kopieren des Release-Pakets und vor dem ersten Start des Tasks.

**1. Ordner anlegen**

```powershell
New-Item -ItemType Directory -Path "C:\Program Files\MiniEMS" -Force
New-Item -ItemType Directory -Path "C:\ProgramData\MiniEMS\data\runtime" -Force
New-Item -ItemType Directory -Path "C:\ProgramData\MiniEMS\data\spotmarket" -Force
New-Item -ItemType Directory -Path "C:\ProgramData\MiniEMS\logs" -Force
New-Item -ItemType Directory -Path "C:\ProgramData\MiniEMS\runtime" -Force
New-Item -ItemType Directory -Path "C:\ProgramData\MiniEMS\backup" -Force
```

**2. Vererbung kappen (nur auf `ProgramData\MiniEMS`)**

`C:\Program Files` braucht keine Sonderbehandlung – die Windows-Standard-ACL dort (Administratoren
Vollzugriff, normale Benutzer nur Lesen/Ausführen) entspricht bereits dem Zielbild aus 3.2. Auf
`C:\ProgramData\MiniEMS` muss die Vererbung von `ProgramData` (dort haben "Benutzer" im Regelfall
Lesezugriff) dagegen gekappt werden, damit normale Benutzer keinen Zugriff erben:

```powershell
icacls "C:\ProgramData\MiniEMS" /inheritance:r
```

**3. ACLs setzen**

```powershell
# SYSTEM und Administratoren: Vollzugriff auf die gesamte Standortdaten-Wurzel
icacls "C:\ProgramData\MiniEMS" /grant "SYSTEM:(OI)(CI)F"
icacls "C:\ProgramData\MiniEMS" /grant "BUILTIN\Administrators:(OI)(CI)F"

# config.json: Task-Benutzer nur lesen (Admin aendert, siehe H9/UPDATE_WARTUNG.md)
icacls "C:\ProgramData\MiniEMS\config.json" /grant "SYSTEM:(R)"

# Daten-/Log-/Runtime-Ordner: Task-Benutzer aendern (lesen+schreiben), rekursiv fuer neue Dateien im Betrieb
icacls "C:\ProgramData\MiniEMS\data" /grant "SYSTEM:(OI)(CI)M"
icacls "C:\ProgramData\MiniEMS\logs" /grant "SYSTEM:(OI)(CI)M"
icacls "C:\ProgramData\MiniEMS\runtime" /grant "SYSTEM:(OI)(CI)M"

# backup\: bewusst kein Grant fuer den Task-Benutzer - nur SYSTEM/Administratoren (aus Schritt 3a) haben Zugriff
```

Hinweis: Die Beispiele nutzen `SYSTEM`, weil der heutige `windows/install_task.ps1` den Task als
`NT AUTHORITY\SYSTEM` registriert (nur lesend referenziert). Wird künftig ein dedizierter
Dienst-/Task-Benutzer eingeführt (z. B. `IPC\MiniEmsSvc`), ersetzt dessen Kontoname in denselben
Kommandos `SYSTEM` 1:1 – Rechteart und betroffene Ordner ändern sich nicht.

Falls kein dedizierter Task-Benutzer, sondern weiterhin `SYSTEM` verwendet wird: Der `/grant`-Aufruf auf
`SYSTEM` in Schritt 3 ist dann bereits ausreichend, ein zusätzlicher Benutzer-Grant entfällt.

**4. Normale Benutzer explizit ausschließen (Kontrolle, kein Zusatzrecht nötig)**

Nach Schritt 2 (`inheritance:r`) haben normale Benutzer bereits keinen Zugriff mehr, weil keine
Vererbung mehr greift und kein expliziter Grant für "Benutzer" oder "Jeder" gesetzt wurde. Ein
zusätzliches explizites `/deny` ist nicht nötig und wird nicht empfohlen (`/deny`-Einträge erschweren
spätere Rechtekorrekturen und können sich mit Administratorrechten überschneiden). Zur Kontrolle:

```powershell
icacls "C:\ProgramData\MiniEMS"
```

Erwartete Ausgabe: nur `NT AUTHORITY\SYSTEM` und `BUILTIN\Administrators` (bzw. der dedizierte
Task-Benutzer) als Einträge, kein `BUILTIN\Users`, kein `Jeder`/`Everyone`.

**5. Prüfkommandos**

```powershell
# ACL-Ausgabe je Ordner pruefen (erwartet: kein BUILTIN\Users, kein Everyone)
icacls "C:\ProgramData\MiniEMS"
icacls "C:\ProgramData\MiniEMS\config.json"
icacls "C:\ProgramData\MiniEMS\data"
icacls "C:\ProgramData\MiniEMS\logs"
icacls "C:\ProgramData\MiniEMS\runtime"

# Test als normaler Benutzer (in einer Sitzung/Remote-Desktop-Session eines Nicht-Admin-Kontos ausfuehren):
Get-Content "C:\ProgramData\MiniEMS\config.json"          # erwartet: Zugriff verweigert
Get-ChildItem "C:\ProgramData\MiniEMS\logs"                # erwartet: Zugriff verweigert
Test-Path "C:\ProgramData\MiniEMS\runtime\health.json"     # Pfad kann als vorhanden gemeldet werden,
                                                            # ein anschliessendes Get-Content muss aber scheitern
```

Der eigentliche DoD-Nachweis ("normale Benutzer können Runtime-Dateien nicht lesen/ändern") ist erst mit
diesem dritten Prüfschritt – ausgeführt unter einem echten Nicht-Admin-Windows-Konto auf der realen
IPC – tatsächlich erbracht, nicht schon mit dem Setzen der ACLs allein.

### 3.4 Betriebsrisiken

Die H3-Leitplanke aus `ROADMAP.md` lautet wörtlich: *"Zu strenge Rechte dürfen den geplanten Task, Logs
und Reports nicht blockieren."* Konkret heißt das:

**Mindestrechte, die der Task-/Dienst-Benutzer braucht:**

- **Lesen:** `C:\Program Files\MiniEMS` (Executable, `dashboard/`, Templates) und
  `C:\ProgramData\MiniEMS\config.json`.
- **Schreiben (Lesen+Ändern):** `C:\ProgramData\MiniEMS\data\` (SQLite-Datei inkl. WAL-/Journal-Dateien,
  Spotmarkt-Cache/-Plan/-Override), `C:\ProgramData\MiniEMS\logs\` (laufendes Anhängen an `mini_ems.log`
  und `mini_ems_stdout.log`), `C:\ProgramData\MiniEMS\runtime\` (`state.json`, `health.json` werden laut
  `MINI_EMS_ANLEITUNG.md` bei jedem Zyklus neu geschrieben).

**Was bei zu strengen Rechten typischerweise bricht** (jeweils mit Symptom, damit es im Betrieb
wiedererkennbar ist):

- **Fehlendes Schreibrecht auf `logs\`:** Der Task startet, aber `mini_ems_stdout.log` bzw.
  `mini_ems.log` wachsen nicht mehr; im schlimmsten Fall bricht der Prozess beim ersten Log-Write ab und
  die `run_mini_ems.cmd`-Restart-Schleife (siehe `UPDATE_WARTUNG.md` 2.2) startet ihn endlos neu, ohne
  dass ein Fehler sichtbar wird, weil genau das Log fehlt, das den Fehler zeigen würde.
- **Fehlendes Schreibrecht auf `data\runtime\`:** SQLite kann keine Journal-/WAL-Datei neben der
  `.sqlite`-Datei anlegen. Typisches Symptom: `sqlite3.OperationalError: attempt to write a readonly
  database` oder `disk I/O error` in den Logs, Historie/Reports bleiben leer oder brechen ab
  (`/api/history`, `/api/report/*` liefern keine neuen Daten).
  **Wichtig:** Das Schreibrecht muss auch für **neu erzeugte** Dateien in diesem Ordner gelten (SQLite
  legt `-wal`/`-shm`-Dateien zur Laufzeit an) – deshalb in Schritt 3 die Vererbungsflags `(OI)(CI)`
  (Object Inherit/Container Inherit), nicht nur ein Recht auf die heute schon vorhandenen Dateien.
- **Fehlendes Schreibrecht auf `runtime\`:** `state.json`/`health.json` können nicht aktualisiert werden.
  Der Healthcheck aus `UPDATE_WARTUNG.md` 2.6 zeigt dann entweder eine veraltete `health.json`
  (`last_cycle_at` bleibt stehen) oder der Prozess wirft beim Schreibversuch eine Exception und der
  Watchdog/`runtime_status` kippt auf `stale_runtime`.
- **Fehlendes Leserecht auf `config.json`:** Der Prozess kann gar nicht starten (`load_config` schlägt
  schon beim `read_text` fehl); sichtbar als sofortiger Absturz direkt nach Taskstart, `LastTaskResult`
  ungleich `0`.
- **Zu strenge Rechte auf `data\spotmarket\`:** Der Spotmarkt-Override (`spotmarket_manual_override.json`)
  kann nicht gelesen/geschrieben werden; die Preisplanung fällt auf Default-Verhalten zurück oder eine
  manuell gesetzte Override-Einstellung wird beim nächsten Zyklus nicht übernommen.
- **Report-PDF/HTML (`/api/report/pdf`, `/api/report/html`):** Diese Endpunkte lesen aus der SQLite-DB
  (`data\runtime\`) und rendern serverseitig; sie brauchen kein zusätzliches Schreibrecht über die oben
  genannten Ordner hinaus, sind aber indirekt betroffen, wenn `data\runtime\` nicht beschreibbar ist und
  deshalb keine aktuellen Daten in der DB stehen.

**Kurzer Funktionstest nach dem Setzen der Rechte** (Verweis auf `UPDATE_WARTUNG.md` Abschnitt 2.6,
hier auf das Rechte-Setzen zugeschnitten statt auf ein volles Update):

1. Task starten (`Start-ScheduledTask -TaskName "MiniEmsPoC"`) und mindestens einen Zyklus abwarten
   (`timing.cycle_seconds`, siehe `config.json`).
2. `runtime\health.json` öffnen: `status` muss `healthy` sein, `runtime_status` muss `live` sein,
   `last_cycle_at` muss aktuell sein – identische Prüfpunkte wie in `UPDATE_WARTUNG.md` 2.6, Punkt 15.
3. `logs\mini_ems.log` auf neue `ERROR`/`Traceback`-Einträge seit dem Start prüfen
   (`Select-String -Path "logs\mini_ems.log" -Pattern "ERROR","Traceback" | Select-Object -Last 20`).
4. `data\runtime\mini_ems.sqlite` Dateigröße/Änderungszeitpunkt prüfen (`Get-Item ... | Select
   Length,LastWriteTime`) – sie muss sich nach einem Zyklus geändert haben.
5. `/api/status` von einem Rechner mit Netzzugriff abrufen und ein frisches `timestamp`-Feld im
   `health`-Abschnitt prüfen (identisch zu `UPDATE_WARTUNG.md` 2.6, Punkt 16).

Schlägt einer dieser Punkte fehl, ist das erste Verdachtsmoment ein zu enges Dateirecht auf genau dem
Ordner, der zum jeweiligen Symptom passt (siehe Liste oben) – nicht zwingend ein Code- oder
Konfigurationsfehler.

### 3.5 Migrationshinweis: vom heutigen Zustand zum Ziel-Layout

**Heutiger Zustand:** Git-Checkout unter `C:\dev\openems\mini_ems_poc` (siehe `MINI_EMS_ANLEITUNG.md`,
Ordnerstruktur), Task läuft über `windows/install_task.ps1` als `SYSTEM`, `run_mini_ems.cmd` startet
`python.exe mini_ems.py --config "%PROJECT_DIR%\config.json" --loop` mit `WorkingDirectory` = Projektordner.
Alle Standortdaten liegen als Unterordner desselben Checkouts. Es gibt keine Windows-ACL-Sonderbehandlung
gegenüber dem Standard-Benutzerordner.

**Reihenfolge der Migration** (kann erst nach dem in H2 vorausgesetzten Windows-Build erfolgen, siehe
unten):

1. **Voraussetzung, bereits an anderer Stelle offen:** Windows-Build des Release-Pakets auf/für die IPC
   (`packaging\build_release.ps1`), siehe `ROADMAP.md` H2-Stand. Ohne dieses Paket gibt es keine
   App-Dateien-Menge, die nach `C:\Program Files\MiniEMS` kopiert werden könnte.
2. Zielordner anlegen und Rechte setzen wie in 3.3 beschrieben (kann vorbereitend erfolgen, sobald die
   Zielverzeichnisse feststehen, unabhängig vom fertigen Release-Build).
3. Aktuelle Standortdaten aus dem bestehenden Checkout **kopieren, nicht verschieben** (Originale bleiben
   bis zum bestätigten Funktionstest erhalten): `config.json`, `data\runtime\`, `data\spotmarket\
   spotmarket_manual_override.json` (falls gesetzt), `logs\`, `runtime\state.json`,
   `runtime\health.json` nach `C:\ProgramData\MiniEMS\...` in identischer Unterstruktur – dieselbe
   Dateiliste wie beim Backup-Schritt in `UPDATE_WARTUNG.md` 2.3.
4. Release-Paket nach `C:\Program Files\MiniEMS` entpacken (identisch zum "Release-Ordner tauschen" aus
   `UPDATE_WARTUNG.md` 2.4, nur mit neuem Zielpfad statt In-Place-Ersetzung im Checkout-Ordner).
5. Geplanten Task auf den neuen Installationsort umstellen: `windows/install_task.ps1 -Mode release`
   registriert einen separaten Release-Task, der `C:\Program Files\MiniEMS\run_mini_ems_release.cmd`
   mit `C:\ProgramData\MiniEMS\config.json` startet. Der Launcher ruft `mini_ems.exe --config
   C:\ProgramData\MiniEMS\config.json --loop` auf; Arbeitsverzeichnis ist `C:\Program Files\MiniEMS`.
6. Funktionstest wie in 3.4 durchführen, bevor der alte Checkout-Ordner entfernt wird.
7. Erst nach bestandenem Funktionstest den alten Task deregistrieren/alten Checkout-Ordner archivieren
   oder löschen – nicht vorher, damit im Fehlerfall der bekannte funktionierende Zustand sofort wieder
   verfügbar ist (gleiches Rollback-Prinzip wie in `UPDATE_WARTUNG.md` Abschnitt 3).

**Was erst nach dem H2-Windows-Build auf der realen IPC passieren kann** (nicht vorwegnehmbar in diesem
Dokument):

- Das tatsächliche Kopieren der Standortdaten und das Entpacken des Release-Pakets in die Zielordner.
- Das Setzen und Prüfen der `icacls`-ACLs auf der realen Windows-Installation (die Kommandos in 3.3 sind
  kopierbereit, aber ungetestet gegen die reale IPC-Umgebung, reale Kontonamen und reale
  Windows-Version).
- Der DoD-Nachweis selbst: ein Test als echter normaler Windows-Benutzer, dass Runtime-Dateien nicht
  lesbar/änderbar sind, bei laufendem Task und funktionierendem UI-Zugriff.
- Die Umstellung auf einen dedizierten Task-/Dienst-Benutzer statt `SYSTEM` bleibt eine spätere
  Betriebsentscheidung. Der Release-Task-Pfad selbst ist über `windows/install_task.ps1 -Mode release`
  und `run_mini_ems_release.cmd` vorbereitet.

---

## Teil 4 – API-Bindung und Reverse Proxy (H4)

Ziel von H4: Die technische Mini-EMS-API wird **nicht direkt im Netz ausgestellt**, sondern intern
gebunden; der UI-Zugriff läuft kontrolliert über einen davor gesetzten Reverse Proxy mit HTTPS. Dieser
Teil liefert das umsetzungsreife Feinkonzept: die Bindungs-Matrix, die Proxy-Empfehlung mit Begründung,
die Verweise auf die kopierfertigen Vorlagen unter `proxy/`, die ehrliche Schutzabgrenzung und eine
Verifikations-Checkliste für den Standort. Die Vorlagen selbst (`proxy/Caddyfile`,
`proxy/firewall_rules.ps1`, `proxy/README.md`) ändern **nichts** an Mini EMS, an `config.json` oder an
`windows/*.ps1`.

**Abgrenzung vorweg:** Diese Stufe ist die **Vorstufe** vor dem Login (H6). Sie nimmt die API aus dem Netz,
bringt TLS und kanalisiert den Zugriff über genau einen Einstiegspunkt – sie bringt **keinen** Login und
**keine** Rollen. Der Schutz endet außerdem beim Kunden-Administrator der IPC (Grenze aus Teil 1.3).

### 4.1 Bindungs-Matrix

Die Bindung entscheidet, **welches Netzwerk-Interface** die API überhaupt annimmt. Sie ist die erste und
wichtigste Grenze – noch vor Firewall, read-only Modus und Proxy.

| # | Szenario | `api.host` (Bindung) | `api.read_only` | Reverse Proxy | Wer kommt an die API |
|---|---|---|---|---|---|
| 1 | Laptop / Simulation (`config.local.json`) | `127.0.0.1` | `false` (Default) | nein | nur der lokale Benutzer auf dem Laptop |
| 2 | Secomea-/VPN-Pfad heute (Teil 2, Pfad a) | `192.168.244.10` (EMS-LAN-IP) | `true` | nein (optional) | Personen mit Secomea-/VPN-Zugang, **direkt** auf `8090` (ohne TLS/Login) |
| 3 | **H4-Zielstufe: API lokal, Proxy davor** | `127.0.0.1` | `true` | **ja** (Caddy) | Kundennetz/VPN **nur über den HTTPS-Proxy**; `8090` ist im Netz unsichtbar |
| 4 | (Anti-Muster, nie verwenden) | `0.0.0.0` | egal | egal | **alle Interfaces**, inkl. jedem versehentlich gerouteten Netz |

**Wann `127.0.0.1`:** immer, wenn ein Proxy davorsteht (Szenario 3) oder reiner Lokalbetrieb vorliegt
(Szenario 1). Die API hört dann nur auf Loopback und ist von keinem anderen Rechner direkt erreichbar –
weder aus dem Kundennetz noch aus dem Internet. Der Proxy ist der einzige Sprecher zur API.

**Wann die konkrete EMS-LAN-IP `192.168.244.10`:** im heutigen Secomea-Pfad (Szenario 2), solange **kein**
Proxy eingerichtet ist. Dann muss die API auf dem LAN-Interface lauschen, damit der VPN-/Secomea-Client sie
erreicht. Diese Bindung ist die **bestehende** Betriebsart aus Teil 2 – der Proxy ersetzt sie nicht,
sondern tritt in Szenario 3 optional davor (siehe 4.5).

**Warum nie `0.0.0.0`:** `0.0.0.0` bindet an **alle** Netzwerk-Interfaces gleichzeitig. Auf einer IPC mit
mehreren Interfaces (EMS-LAN, ggf. weiteres Management-/WAN-Interface, VPN-Adapter) würde die API damit auch
auf Interfaces lauschen, die nie dafür gedacht waren – im ungünstigsten Fall auf einem Interface mit
Internet-Route. Eine konkrete Bindung (`127.0.0.1` oder `192.168.244.10`) stellt sicher, dass der Dienst nur
auf dem einen vorgesehenen Weg annimmt. Das ist genau die Festlegung aus Teil 1.1 und
`MINI_EMS_ANLEITUNG.md` ("sauberer und sicherer als `0.0.0.0`").

**Zusammenspiel mit `api.read_only`:** Die Bindung sagt, *wer* die API erreicht; `api.read_only` sagt, *was*
er dann darf. Beides ist unabhängig und wirkt additiv (defense in depth). In Szenario 3 gilt bewusst beides:
`127.0.0.1` nimmt die API aus dem Netz, `read_only: true` sperrt zusätzlich serverseitig alle Schreib-/
Aktiv-Endpunkte (siehe 2.1) – selbst wenn der Proxy einmal fehlkonfiguriert wäre, bliebe die API read-only.

### 4.2 Reverse-Proxy-Empfehlung: Caddy

Verglichen für die Windows-IPC:

- **Caddy (Empfehlung).** Eine einzige Binary (`caddy.exe`), kein Installer, kein Runtime-Unterbau.
  Automatisches, intern vertrauenswürdiges HTTPS über die eingebaute lokale CA (`tls internal`) – ohne
  Internet-CA, was für eine IPC ohne öffentliche Erreichbarkeit passt. Die "eine Binary neben einer Konfig"-
  Philosophie deckt sich mit dem Release-Paket-Ansatz aus `packaging/`.
- **nginx für Windows.** Funktioniert, aber HTTPS-Zertifikate müssen manuell erzeugt und erneuert werden,
  und der Windows-Build gilt als zweitrangig gepflegt. Mehr Handarbeit für denselben Zweck.
- **IIS mit URL-Rewrite/ARR.** Bereits im Windows-Ökosystem, aber schwergewichtig: Rollen/Features
  aktivieren, ARR- und URL-Rewrite-Module nachinstallieren, Zertifikate über den Windows-Zertifikatspeicher
  verwalten. Deutlich mehr bewegliche Teile als eine einzelne Binary.

**Empfehlung: Caddy** – eine Binary, automatisches internes HTTPS, einfache Integration als
`sc.exe`-Windows-Dienst. Das hält die Betriebsschritte minimal und passt zur Release-Paket-Philosophie.
Details und Installationsschritte: `proxy/README.md`.

### 4.3 Konkrete Vorlagen unter `proxy/`

Analog zu `packaging/` liegen die kopierfertigen Vorlagen in einem eigenen Verzeichnis:

| Datei | Inhalt |
|---|---|
| `proxy/Caddyfile` | Reverse Proxy auf `127.0.0.1:8090`, `tls internal` (internes Zertifikat), `bind` auf die EMS-LAN-IP, auskommentierter `basic_auth`-Block als H6-Vorbereitung (kein Credential im Repo) |
| `proxy/firewall_rules.ps1` | `New-NetFirewallRule`-Kommandos: Proxy-Port nur aus dem Kundennetz/VPN, `8090` eingehend aus dem Netz blockiert |
| `proxy/README.md` | Installation als `sc.exe`-Dienst, Firewall, Client-Zertifikat, Prüfschritte, Update-Zusammenspiel, H6-Ausblick |

Kernpunkte der `Caddyfile` (verifiziert gegen die aktuelle Caddy-v2-Dokumentation):

- `bind 192.168.244.10` – der Proxy lauscht nur auf der EMS-LAN-IP, nicht auf allen Interfaces. Der `bind`-
  Wert enthält bewusst keinen Port; der Port kommt aus der Site-Adresse.
- `tls internal` – Caddy nutzt seine lokale, intern vertrauenswürdige CA und braucht keine Internet-CA.
- `reverse_proxy 127.0.0.1:8090` – Weiterleitung an die lokal gebundene Mini-EMS-API.
- `basic_auth { … }` – **auskommentiert**, Andockstelle für H6. Passwort-Hashes werden mit
  `caddy hash-password` erzeugt und **außerhalb** des Repos gehalten (Caddy akzeptiert keine
  Klartext-Passwörter). `basic_auth` ist die aktuelle Direktiven-Schreibweise (vor Caddy v2.8: `basicauth`).

### 4.4 Was diese Stufe leistet – und was nicht

**Leistet (H4):**

- Die technische API ist **nicht mehr direkt im Netz**: Sie hört nur auf `127.0.0.1`, der einzige
  Netzwerk-Sprecher ist der Proxy.
- **TLS** für den UI-Zugriff über ein intern vertrauenswürdiges Zertifikat, ohne Internet-CA.
- Der Zugriff ist auf **genau einen Einstiegspunkt kanalisiert** (der Proxy), zusätzlich per Firewall auf
  das Kundennetz/VPN begrenzt.
- Zusammen mit `api.read_only: true` bleiben Schreib-/Aktiv-Endpunkte serverseitig gesperrt (siehe 2.1).

**Leistet NICHT (bewusst nicht Teil von H4):**

- **Kein Login und keine Rollen.** Wer den Proxy im Kundennetz/VPN erreicht, sieht das Dashboard ohne
  Passwort. Der `basic_auth`-Block ist vorbereitet, aber inaktiv – Login/Rollen (`viewer`/`operator`/
  `admin`) kommen mit **H6** (`PRODUCT_UX_KONZEPT.md`, Abschnitt 3).
- **Keine Uneinsehbarkeit gegenüber dem Kunden-Administrator.** Der Schutz ist eine Netzwerk- und
  Zugriffsgrenze, keine kryptografische Uneinsehbarkeit auf der IPC. Wer lokalen Admin-Zugriff hat, kann
  den Proxy umgehen und `127.0.0.1:8090` direkt ansprechen – das ist die Grenze aus **Teil 1.3** und wird
  hier nicht anders behauptet.
- **Kein Ersatz für die read-only Grenze.** Der Proxy ist kein Rollenfilter; die read-only Trennung bleibt
  serverseitig über `api.read_only` (H5) verantwortlich, nicht über Proxy-Regeln.

### 4.5 Abgrenzung zum Secomea-Pfad (Teil 2, Pfad a)

Der heutige Pfad a bindet die API an die EMS-LAN-IP `192.168.244.10:8090` und erreicht sie über Secomea/VPN
**direkt**, ohne Proxy und ohne TLS (Szenario 2 der Matrix). Der Reverse Proxy ist eine **optionale Stufe
davor**, kein Ersatz:

- Er verschiebt die API-Bindung auf `127.0.0.1` (Szenario 3), macht `8090` im Netz unsichtbar und stellt
  denselben VPN-Zugriff über HTTPS und einen einzigen Einstiegspunkt bereit.
- Solange der Proxy **nicht** eingerichtet ist, bleibt Pfad a unverändert gültig und betriebsfähig – die
  H4-Stufe ist additiv, nicht erzwingend.
- Die BACnet-Controller (`192.168.244.30/.40:47808`) bleiben in **beiden** Fällen außerhalb jedes
  Fernzugriffs; daran ändert der Proxy nichts.

### 4.6 Verifikations-Checkliste für den Standort

Ausführbar erst auf der realen IPC (Windows-Build, echte Netze). Erwartete Ergebnisse jeweils dahinter:

1. **API lokal erreichbar:** auf der IPC `curl http://127.0.0.1:8090/api/status` → `HTTP 200` mit
   Statusdaten.
2. **API nicht mehr im Netz:** vom zweiten Rechner (Kundennetz/VPN)
   `curl http://192.168.244.10:8090/api/status` → Verbindung abgelehnt/Timeout (weil `api.host=127.0.0.1`).
3. **Proxy lokal:** auf der IPC `curl -k https://<hostname>/api/status` → `HTTP 200` (Proxy erreicht die
   lokale API).
4. **Proxy vom zweiten Rechner:** aus dem Kundennetz/VPN `curl -k https://<hostname>/api/status` →
   `HTTP 200`; das Dashboard `https://<hostname>/` lädt.
5. **read-only greift über den Proxy:** `curl -k -X POST https://<hostname>/api/config/spotmarket-lockout`
   → `HTTP 403` (`read_only_mode`); `curl -k https://<hostname>/api/diagnostics/read` → `HTTP 403`;
   `curl -k https://<hostname>/api/status` meldet `api_read_only: true`.
6. **TLS aktiv:** der Proxy antwortet auf `https://`, nicht auf `http://`; das Zertifikat stammt aus Caddys
   interner CA (bei `-k` akzeptiert; für vertrauenswürdige Anzeige die Root-CA auf dem Client importieren,
   siehe `proxy/README.md`).
7. **Firewall:** `Get-NetFirewallRule -DisplayName "MiniEMS*"` zeigt die Allow-Regel für den Proxy-Port und
   die Block-Regel für `8090`; ein Zugriff auf den Proxy-Port **von außerhalb** des Kundennetzes schlägt
   fehl.

**Stand Pilot-IPC 2026-07-08:** Die IPC-seitige Umschaltung ist ausgeführt. `config.json` setzt
`api.host: 127.0.0.1` und `api.read_only: true`, die produktive Caddyfile proxyt auf `127.0.0.1:8090`,
Mini EMS läuft nach Neustart über `MiniEmsPoCRelease`, und Caddy wurde reloadet. Lokal auf der IPC verifiziert:
`127.0.0.1:8090/api/status` meldet `api_read_only: true`, `192.168.244.10:8090` ist nicht mehr erreichbar,
`https://192.168.244.10/api/status` und `/dashboard` liefern HTTP 200, `GET /api/diagnostics/read` und
`POST /api/config/spotmarket-lockout` liefern HTTP 403, und die H4-Firewallregeln sind aktiv.

**Offene Standort-Schritte (nur am realen Standort nachweisbar, deshalb bleibt die H4-Checkbox offen):**

- Vom zweiten Rechner im freigegebenen Kundennetz/VPN/Secomea prüfen: `https://192.168.244.10/api/status`
  und Dashboard laden, `http://192.168.244.10:8090/api/status` darf nicht mehr erreichbar sein.
- Von außerhalb des Kundennetz-/VPN-Bereichs prüfen, dass der Proxy-Port nicht erreichbar ist.
- **DoD-Nachweis:** Zugriff funktioniert nur aus dem freigegebenen Kundennetz/VPN, und die Anlagen-API ist
  nicht öffentlich erreichbar (Prüfschritte 2, 4, 7 gegen die reale Netztopologie). Dieser Nachweis kann nur
  am Standort erbracht werden.

---

## Querverweise

- `ROADMAP.md` – strategische To-do-Linie "Geschütztes Kundenhosting" (H1–H9) und To-do 3
- `PRODUCT_UX_KONZEPT.md`, Abschnitt 3 – fachliches Rollenmodell Viewer/Operator/Admin
- `EDGE_INTEGRATION_CONTRACT.md` – Lese-/Schreibrechte, Safety-Flags, Ausfallverhalten
- `MINI_EMS_ANLEITUNG.md` – Betrieb, `api.host`-Bindung, Endpunktübersicht, heutige Ordnerstruktur
- `mini_ems_runtime/http_api.py` – tatsächliche Endpunkte (Quelle der Einstufung in 2.1)
- `mini_ems_runtime/config.py` – `resolve_path`/`base_dir`, Quelle der config-relativen Pfadauflösung in Teil 3.1
- `packaging/README.md`, `packaging/RELEASE_HINWEISE.md` – Release-Layout, Frozen-Pfadauflösung (H2),
  Grundlage für das App-Dateien-Layout in Teil 3.1
- `proxy/Caddyfile`, `proxy/firewall_rules.ps1`, `proxy/README.md` – kopierfertige Reverse-Proxy- und
  Firewall-Vorlagen für Teil 4 (H4): API intern binden, HTTPS-Proxy davor, Zugriff kanalisieren
- `UPDATE_WARTUNG.md` – Update-, Healthcheck- und Rollback-Ablauf (H7), App-Dateien-/Standortdaten-Liste
  (Abschnitt 1.3, Basis für Teil 3.1), Backup-Dateiliste (Abschnitt 2.3, Basis für Migrationshinweis 3.5),
  Verantwortlichkeiten remote (Secomea/VPN) vs. vor Ort, konsistent zur Sichtbarkeits-/Änderungsmatrix in
  Teil 1
- `windows/install_task.ps1` – Task-Mechanismus für heutigen Checkout-Betrieb (`-Mode checkout`) und
  Release-Ziel-Layout (`-Mode release` mit `run_mini_ems_release.cmd`)
