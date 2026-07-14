# Mini EMS – Hosting und Sicherheitsgrenze

> **Aktueller Release-Pfad (2026-07-14):** Standortparameter und Revisionen liegen in
> `C:\ProgramData\MiniEMS\site.sqlite`; persönliche Konten, Sitzungen und BACnet-Schreibfreigaben in
> `C:\ProgramData\MiniEMS\identity.sqlite`. Die Runtime startet ausschließlich mit `--site-dir`.
> Eine `config.json` ist nur noch einmalige Migrationsquelle. Viewer lesen nach Anmeldung, Admins verwalten
> Standort und Konten. BACnet-Schreibtests benötigen zusätzlich eine explizite `EMS_`-Punktfreigabe und enden
> nach zehn Sekunden automatisch mit Relinquish. `api.read_only=true` blockiert den Test unabhängig von der Rolle.

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
Aussagen zu Lese-/Schreibpfaden sind aus `mini_ems_runtime/http_api.py`, `mini_ems_runtime/site_store.py` und dem
Rollenmodell in `PRODUCT_UX_KONZEPT.md` (Abschnitt 3) abgeleitet. Weicht diese Datei vom Code ab, gilt
der Code, und diese Datei ist zu korrigieren.

Im ersten Release sind genau zwei Rollen technisch umgesetzt: **Viewer** und **Admin**. Eine spätere
Operator-Rolle bleibt eine Produkterweiterung und ist keine aktuell vergebbare Berechtigung.

---

## Teil 1 – Zielbild und Sicherheitsgrenze (H1)

### 1.1 Festlegung

Mini EMS läuft auf **kundeneigener IPC-Hardware** und bleibt der lokale Anlagen-Gateway. Es wird aber
nicht als frei einsehbarer Entwicklerordner ausgeliefert, und die Anlagen-API wird nicht offen ins Netz
gestellt. Konkret gilt:

- Der Betriebspfad ist die **IPC vor Ort**. Ihre aktive Standortkonfiguration liegt revisionssicher in
  `C:\ProgramData\MiniEMS\site.sqlite`; lokale Entwicklung verwendet einen getrennten temporären `--site-dir`.
- Der Zugriff auf **UI und API** bleibt auf **Kundennetz, VPN oder Secomea** beschränkt. Es gibt keine
  direkte Erreichbarkeit der Anlagen-API aus dem offenen Internet.
- Die Runtime bindet auf der IPC an `127.0.0.1:8090`; Caddy stellt das Dashboard geschützt auf der
  EMS-LAN-IP bereit. Beides ist bewusst kein offener Internet-Zugang.
- Das ausgelieferte Zielformat ist ein **versioniertes Release-Paket** statt eines Git-Checkouts
  (H2 in `ROADMAP.md`, umgesetzt). Ziel ist, dass ein normaler Windows-Nutzer nicht
  beiläufig den gesamten Python-Quellcode lesen kann.

### 1.2 Sichtbarkeits- und Änderungsmatrix

| Ressource | Ohne Anmeldung | Viewer | Admin |
|---|---|---|---|
| **UI-Assets und `/api/health`** | erreichbar | erreichbar | erreichbar |
| **Übersicht, Analyse, Berichte und Betriebsdaten-API** | nein (`HTTP 401`) | lesen | lesen |
| **Systemdiagnose und Standortkonfiguration** | nein | nein (`HTTP 403`) | lesen und validiert speichern |
| **Konten und Rollen** | nein | nein | Konten anlegen, Rolle ändern, deaktivieren, Passwort setzen |
| **BACnet-Schreibpunkt freigeben** | nein | nein | nur BV/AV, eindeutiger `EMS_`-Name, sichere Priorität |
| **BACnet-Schreibtest** | nein | nein | nur bei aufgehobenem API-Schreibschutz; zehn Sekunden, dann Relinquish |
| **Dateien, Logs und SQLite direkt** | Windows-Rechte maßgeblich | nein | nur lokale IPC-Administration |

Passwörter werden mit scrypt und individuellem Salt in `identity.sqlite` gespeichert. Der Browser erhält nur
ein `HttpOnly`-/`SameSite=Strict`-Sitzungscookie; in der IPC-Umgebung zusätzlich `Secure`. Sitzungen enden nach
30 Minuten Inaktivität oder spätestens nach zwölf Stunden. `api.read_only` bleibt eine zweite, rollenunabhängige
Schutzschicht: Ein Admin darf dann konfigurieren und Freigaben vorbereiten, aber keine Anlagenaktion starten.

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

### 1.4 Nachvollziehbarkeit im Pilotbetrieb (H8)

Der Pilot trennt technisches Betriebslog und dauerhaften Konfigurationsverlauf:

- `logs/mini_ems.log` enthält Runtime-Starts (`app.started`), Dashboard-Aufrufe (`ui.accessed`) und bestätigte
  bzw. fehlgeschlagene Anlagenübergaben (`cycle.output_confirmed`/`cycle.output_not_confirmed`).
- `site.sqlite` enthält den unveränderlichen Standort-Revisionsverlauf. `identity.sqlite` enthält getrennt davon
  Sicherheitsereignisse für Anmeldung, Kontenverwaltung, Punktfreigaben und Schreibtests; Passwörter und
  Sitzungstoken erscheinen in keinem Audit-Eintrag.
- `GET /api/config/changes` liefert nur Titel, Zeitpunkt, verständliche Zusammenfassung und Neustarthinweis.
  Interne Backup-/Entwurfspfade bleiben lokal und werden nicht an Viewer ausgegeben.
- Administrative Änderungen werden dem angemeldeten Konto zugeordnet. Ein lokaler Recovery-Aufruf wird als
  Systemereignis ohne erfundene Benutzeridentität protokolliert.

---

## Teil 2 – Erstes sicheres Online-Hosting (Konzept zu To-do 3)

Ziel von To-do 3: Echte IPC-Daten sollen von einem **zweiten Rechner** aus sichtbar werden, ohne die
Anlagen-API öffentlich freizugeben und ohne Schreibfunktionen online zu stellen. Diese Datei liefert das
geforderte **dokumentierte Minimalkonzept** als Entscheidungsvorlage; der reale Nachweis auf einem
zweiten Rechner am Standort ist bewusst noch offen (siehe `ROADMAP.md`, To-do 3).

**Stand (2026-07-08):** Die IPC-seitige H4-Umschaltung (Teil 4) ist inzwischen ausgeführt: Die API
bindet nicht mehr auf der EMS-LAN-IP direkt, sondern nur noch auf `127.0.0.1:8090`; der Zugriff läuft
über den Caddy-Proxy auf `https://192.168.244.10`. Pfad (a) unten beschreibt weiterhin das gültige
Grundkonzept (Secomea/VPN statt Datenexport nach außen) und bleibt als Entscheidungsvorlage stehen; die
konkreten Adress-/Port-Angaben in 2.1-2.5 (direkt `192.168.244.10:8090`) entsprechen dem Stand **vor**
der H4-Umschaltung. Für den aktuellen Zugriffsweg auf der Pilot-IPC gilt Teil 4, Abschnitt 4.6.

### 2.1 Endpunkt-Einstufung (Basis für beide Pfade)

*Stand: 2026-07-14 – abgeglichen mit `mini_ems_runtime/http_api.py`, `identity.py` und
`commissioning.py`; Testabdeckung in `tests/test_http_auth.py` und `tests/test_read_only_api.py`.*

**Ohne Anmeldung:** Nur UI-Assets, `GET /api/auth/status` und der minimale Maschinen-Endpunkt
`GET /api/health` sind öffentlich. `/api/health` liefert Health, Version und `api_read_only`, aber keine
Anlagenwerte. Alle übrigen Datenendpunkte verlangen eine gültige Sitzung.

**Viewer:** `GET /api/status`, Historie, Zyklen, Spotmarktplan, Wetter und Reports sowie
`POST /api/report/preview`. Viewer sehen keine Standortkonfiguration, Diagnose, Benutzer oder
BACnet-Freigaben.

**Admin:** Zusätzlich `GET /api/config/site|changes`, `GET /api/diagnostics/read`, Konten-/Audit-Endpunkte,
Mapping und Standortkonfiguration. Kontoaktionen und passive BACnet-Punktfreigaben sind auch bei
`api.read_only=true` möglich.

**Rollenunabhängiger Read-only-Schutz:** Bei `api.read_only=true` bleiben aktive Diagnose/Discovery,
Preissteuerungsänderungen, Report-POST und `POST /api/bacnet/write-test/start` mit `HTTP 403
read_only_mode` gesperrt. Punktfreigabe, Widerruf und eine sicherheitsgerichtete vorzeitige Rückgabe bleiben
erreichbar. Der Wächtertest inventarisiert jeden POST-Endpunkt; neue POST-Routen sind dadurch automatisch
gesperrt, bis sie bewusst eingestuft werden.

**BACnet-Schreibtest:** Ein Admin muss den Zielpunkt vorher separat freigeben. Zugelassen sind nur BV/AV,
eine eindeutige Bezeichnung `EMS_...`, IPv4-Ziel, Instanz 0 bis 4194303 und eine nicht reservierte Priorität;
die UI verwendet Priorität 14. Bereits von der Mini-EMS-Regelung belegte Ausgänge sind ausgeschlossen.
Ein Test läuft genau zehn Sekunden, prüft nach Möglichkeit den wirksamen Wert und schreibt anschließend
`NULL` auf derselben Priorität. Unfertige Leases werden auch nach Neustart bzw. beim Shutdown zurückgegeben.

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

- Mit `api.read_only: true` (siehe 2.1) bleiben aktive Anlagenzugriffe und Bedienaktionen serverseitig
  gesperrt. Der Konfigurationspfad ist bewusst erreichbar, verlangt aber eine Admin-Sitzung.
- VPN-/Secomea-Zugang allein reicht nicht: Betriebsdaten verlangen mindestens Viewer, Standort-Einrichtung und
  Technik Admin. Login-Throttling und serverseitige Sitzungen sind H6-Bestandteil.

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

1. Als Admin in **Standort einrichten → Technische Einstellungen** bestätigen, dass `api.host` für
   diesen Direktpfad auf `192.168.244.10` steht (nicht `0.0.0.0`, nicht Internet). Die aktive Revision
   liegt in `site.sqlite`; **nur prüfen**, nicht im Test ändern.
2. Windows-Firewall prüfen: Port `8090` nur aus Kundennetz/VPN erreichbar, keine WAN-Weiterleitung.
3. Secomea-/VPN-Freigabe auf genau `192.168.244.10:8090` begrenzen; BACnet-Ports (`47808`) nicht
   freigeben.
4. Vom zweiten Rechner über VPN/Secomea das Dashboard öffnen und prüfen, dass echte IPC-Daten erscheinen
   (Status, Historie, Berichte).
5. `api.read_only: true` setzen und Mini EMS neu starten. Danach prüfen: `GET /api/diagnostics/read`,
   `POST /api/config/spotmarket-lockout`, `POST /api/report/preview` und
   `POST /api/config/discovery/bacnet/preview` liefern `HTTP 403`; `GET /api/health` meldet
   `api_read_only: true`. Die Verwaltung lässt sich als Admin öffnen; Import, Vorschau,
   Speichern und Aktivieren laufen über denselben HTTPS-Link.
6. Nach dem Test im Betriebslog und im H8-/Security-Verlauf prüfen, dass Zugriff und Freigabe dem Admin-Konto
   nachvollziehbar zugeordnet wurden.
7. **Definition-of-Done-Nachweis:** Eine fachfremde Person sieht Betriebsdaten ohne Techniknavigation,
   meldet sich als Admin an und kann einen Mapping-Entwurf über denselben Link bis zur
   Aktivierung führen. Aktive Anlagenaktionen bleiben gesperrt. Dieser Nachweis bleibt auf der realen IPC offen.

### 2.6 Verbleibende offene Entscheidungen des Betreibers/Nutzers

Diese Punkte bleiben bewusst offen und sind in `ROADMAP.md` als eigene Schritte geführt:

- **HTTPS/Login-Verfahren** vor dem Dashboard (Reverse Proxy, Zertifikat, Erstpasswort und Rotation) –
  Querverweis **H4** (API intern binden, UI über geschützten Zugriff) und **H6** (Login und Rollenlogik).
- **Echte read-only Erzwingung im Netz** (Allowlist der Endpunkte, Sperre schreibender Pfade auf
  Proxy-Ebene) – Querverweis **H5** (Read-only Netzwerkmodus zuerst).
- **Rollen Viewer/Admin** sind mit H6 umgesetzt; eine Operator-Zwischenrolle bleibt bewusst eine spätere
  Produkterweiterung. Fachliche Vorlage: `PRODUCT_UX_KONZEPT.md` Abschnitt 3.
- **Bei Pfad (b) zusätzlich:** welche Daten das Kundennetz verlassen dürfen und wo der Hosting-Punkt
  betrieben wird.

### 2.7 Harte Leitplanken (gelten für beide Pfade)

- **Keine Internet-Portfreigabe von `8090`** und keine Portweiterleitung der Anlagen-API ins offene Netz.
- **Keine Vermischung von Simulationspfad und echter IPC:** Laptop und IPC verwenden getrennte
  `--site-dir`-Verzeichnisse mit eigener `site.sqlite`; eine alte `config.json` ist nur Migrationseingang.
- **Schreibfunktionen bleiben außerhalb des Online-Pfads:** die aktiven/schreibenden Endpunkte aus 2.1
  werden online nicht angeboten.
- **Keine Änderung an `runtime.real_writes_enabled`** und keinen anderen Safety-Flags durch das
  Online-Hosting. Der Schreibpfad zur Anlage bleibt lokaler Admin-Betrieb auf der IPC.

---

## Teil 3 – Dateischutz und Installationslayout auf der IPC (H3)

H3 ist auf der Pilot-IPC umgesetzt: Das Release liegt getrennt von den dauerhaft
erhaltenen Standortdaten. Der geplante Task läuft als `SYSTEM`; normale
Windows-Benutzer benötigen keinen Dateizugriff, weil Viewer und Admin ausschließlich
über die HTTPS-Oberfläche arbeiten.

### 3.1 Aktuelles Installationslayout

```text
C:\Program Files\MiniEMS\                     <- austauschbares Release-Paket
|-- mini_ems.exe
|-- _internal\
|-- dashboard\
|-- mini_ems_runtime\templates\
|-- VERSION
|-- CHANGELOG.md
|-- SHA256SUMS
`-- RELEASE_HINWEISE.md

C:\ProgramData\MiniEMS\                        <- dauerhafte Standortdaten
|-- site.sqlite                                 (Konfiguration, Mapping, Revisionen)
|-- identity.sqlite                             (Konten, Sitzungen, Audit, BACnet-Freigaben)
|-- data\                                       (Historie und externe Daten-Caches)
|-- logs\                                       (Runtime- und Startprotokolle)
|-- runtime\                                    (Health, State und Controller-Zustand)
|-- proxy\Caddyfile                             (standortspezifische Proxy-Konfiguration)
`-- backup\                                    (administrative Sicherungen)
```

`site.sqlite` und `identity.sqlite` gehören nie in das Release-Paket. Das
Update ersetzt nur `C:\Program Files\MiniEMS` und erhält
`C:\ProgramData\MiniEMS` vollständig. Eine alte `config.json` wird beim
ersten Start einmalig importiert und danach als datierte
`config.json.migrated.*.bak` abgelegt; sie ist kein aktiver Runtime-Eingang.

### 3.2 Rechtemodell

| Bereich | SYSTEM / Mini-EMS-Task | Administratoren | Normale Windows-Benutzer |
|---|---|---|---|
| `C:\Program Files\MiniEMS` | Lesen/Ausführen, für Updates über den administrativen Task-Stopp | Vollzugriff | kein notwendiger Zugriff |
| `site.sqlite`, `identity.sqlite` | Lesen/Schreiben | Vollzugriff für Wartung/Recovery | kein Zugriff |
| `data\`, `logs\`, `runtime\` | Lesen/Schreiben | Vollzugriff | kein Zugriff |
| `proxy\Caddyfile` | Caddy/SYSTEM liest | Vollzugriff | kein Zugriff |
| Browser-Oberfläche | über App-Rolle | über App-Rolle | nur mit Viewer-/Admin-Konto |

Die App-Rolle ersetzt keine Windows-Rechte: Ein Windows-Administrator kann die
IPC und die SQLite-Dateien technisch verändern. Die Produktgrenze schützt vor
unbeabsichtigtem oder unberechtigtem Netzwerkzugriff, nicht vor dem Eigentümer
der Kunden-IPC.

### 3.3 ACLs auf der IPC

Die folgenden Befehle werden in einer administrativen PowerShell ausgeführt. Vor
einer Änderung zuerst die aktuelle ACL sichern und einen Wartungspunkt festlegen.

```powershell
$AppDir  = 'C:\Program Files\MiniEMS'
$SiteDir = 'C:\ProgramData\MiniEMS'

icacls $AppDir  /save C:\Windows\Temp\MiniEMS-App.acl  /t /c
icacls $SiteDir /save C:\Windows\Temp\MiniEMS-Site.acl /t /c

icacls $AppDir /inheritance:r
icacls $AppDir /grant:r 'SYSTEM:(OI)(CI)F' 'BUILTIN\Administrators:(OI)(CI)F' /t /c

icacls $SiteDir /inheritance:r
icacls $SiteDir /grant:r 'SYSTEM:(OI)(CI)F' 'BUILTIN\Administrators:(OI)(CI)F' /t /c
```

Auf einer nicht deutsch lokalisierten Windows-Installation können lokalisierte
Gruppennamen abweichen; `SYSTEM` und die Administratoren-SID müssen zur realen
IPC passen. Keine `Everyone`-/`Users`-Grants ergänzen. Falls der geplante Task
später von `SYSTEM` auf ein eigenes Dienstkonto wechselt, erhält dieses Konto
nur die dafür nötigen Rechte; das ist eine separate Betriebsänderung.

Prüfung:

```powershell
icacls 'C:\Program Files\MiniEMS'
icacls 'C:\ProgramData\MiniEMS'
Get-ScheduledTask -TaskName 'MiniEmsPoCRelease'
Get-ScheduledTask -TaskName 'MiniEmsDashboardCaddy'
```

Danach als normaler Windows-Benutzer bestätigen, dass die Standortdaten nicht
direkt lesbar sind. Anschließend über Caddy anmelden und als Viewer sowie Admin
prüfen; Dateirechte dürfen die Web-Rollen nicht ersetzen oder umgehen.

### 3.4 Betriebs- und Update-Regeln

- `windows/update_release.ps1` als Administrator ausführen. Das Skript stoppt
  den Release-Task, tauscht den App-Ordner, startet neu und prüft `/api/health`.
- `C:\ProgramData\MiniEMS` wird nie als Teil eines normalen App-Updates
  gelöscht oder überschrieben.
- Vor ACL-, SQLite- oder Migrationsarbeiten Standortdaten sichern. Währenddessen
  Mini EMS und gegebenenfalls Caddy stoppen.
- Der lokale Recovery-Befehl
  `mini_ems.exe --site-dir C:\ProgramData\MiniEMS --reset-admin-password`
  setzt ein temporäres Admin-Passwort und widerruft bestehende Sitzungen.
- Logs dürfen keine Passwörter oder Sitzungstoken enthalten. Der einmalige
  Bootstrap-Code ist nur für das erste Admin-Konto bestimmt.
- SQLite-WAL-Dateien gehören bei einer Dateisicherung zum konsistenten
  Datenbestand; bevorzugt wird eine Sicherung bei gestopptem Task.

### 3.5 Migration vom Checkout zum Release

1. Release-Paket nach `C:\Program Files\MiniEMS` installieren.
2. Bestehende Standortdaten nach `C:\ProgramData\MiniEMS` übernehmen.
3. Falls nur eine alte `config.json` vorhanden ist, Mini EMS genau einmal mit
   diesem `--site-dir` starten und den erfolgreichen Import im Log prüfen.
4. Release-Task mit `windows/install_task.ps1` auf
   `run_mini_ems_release.cmd` registrieren.
5. Caddy auf `127.0.0.1:8090` konfigurieren und als geplanten Task starten.
6. `/api/health`, Login, Viewer/Admin-Trennung, Konfigurationserhalt und
   Rollback-Pfad prüfen.
7. Den alten Checkout-Task erst entfernen, wenn das Release nachweislich stabil
   läuft.

## Teil 4 – API-Bindung und Reverse Proxy (H4)

Ziel von H4: Die technische Mini-EMS-API wird **nicht direkt im Netz ausgestellt**, sondern intern
gebunden; der UI-Zugriff läuft kontrolliert über einen davor gesetzten Reverse Proxy mit HTTPS. Dieser
Teil liefert das umsetzungsreife Feinkonzept: die Bindungs-Matrix, die Proxy-Empfehlung mit Begründung,
die Verweise auf die kopierfertigen Vorlagen unter `proxy/`, die ehrliche Schutzabgrenzung und eine
Verifikations-Checkliste für den Standort. Die Vorlagen selbst (`proxy/Caddyfile`,
`proxy/firewall_rules.ps1`, `proxy/README.md`) ändern **nichts** an Mini EMS, am Standort-Speicher oder an
`windows/*.ps1`.

**Abgrenzung:** H4 beschreibt die Transportgrenze: API nur auf Loopback, TLS und genau ein Proxy-Einstieg.
H6 ergänzt heute den App-Login mit Viewer/Admin; Caddy selbst verwaltet keine Mini-EMS-Rollen. Der Schutz endet
außerdem beim Kunden-Administrator der IPC (Grenze aus Teil 1.3).

### 4.1 Bindungs-Matrix

Die Bindung entscheidet, **welches Netzwerk-Interface** die API überhaupt annimmt. Sie ist die erste und
wichtigste Grenze – noch vor Firewall, read-only Modus und Proxy.

| # | Szenario | `api.host` (Bindung) | `api.read_only` | Reverse Proxy | Wer kommt an die API |
|---|---|---|---|---|---|
| 1 | Laptop / Simulation (eigener `--site-dir`) | `127.0.0.1` | `false` (Default) | nein | nur der lokale Benutzer auf dem Laptop; App-Login bleibt aktiv |
| 2 | Historischer direkter Secomea-/VPN-Pfad | `192.168.244.10` (EMS-LAN-IP) | `true` | nein | Personen mit Secomea-/VPN-Zugang und App-Konto, **direkt** auf `8090` (ohne TLS) |
| 3 | **H4-Zielstufe: API lokal, Proxy davor** | `127.0.0.1` | `true` | **ja** (Caddy) | Kundennetz/VPN **nur über den HTTPS-Proxy**; `8090` ist im Netz unsichtbar |
| 4 | (Anti-Muster, nie verwenden) | `0.0.0.0` | egal | egal | **alle Interfaces**, inkl. jedem versehentlich gerouteten Netz |

**Wann `127.0.0.1`:** immer, wenn ein Proxy davorsteht (Szenario 3) oder reiner Lokalbetrieb vorliegt
(Szenario 1). Die API hört dann nur auf Loopback und ist von keinem anderen Rechner direkt erreichbar –
weder aus dem Kundennetz noch aus dem Internet. Der Proxy ist der einzige Sprecher zur API.

**Wann die konkrete EMS-LAN-IP `192.168.244.10`:** im direkten Secomea-Fallback (Szenario 2), solange **kein**
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
`127.0.0.1` nimmt die API aus dem Netz, `read_only: true` sperrt zusätzlich serverseitig alle nicht
freigegebenen Bedien-/Aktiv-Endpunkte (siehe 2.1). Konfigurationsaktivierungen verlangen zusätzlich eine
gültige Admin-Sitzung.

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
geplanter Windows-Task. Das hält die Betriebsschritte minimal und passt zur Release-Paket-Philosophie.
Details und Installationsschritte: `proxy/README.md`.

### 4.3 Konkrete Vorlagen unter `proxy/`

Analog zu `packaging/` liegen die kopierfertigen Vorlagen in einem eigenen Verzeichnis:

| Datei | Inhalt |
|---|---|
| `proxy/Caddyfile` | Reverse Proxy auf `127.0.0.1:8090`, `tls internal` (internes Zertifikat), `bind` auf die EMS-LAN-IP; Login/Rollen bleiben in Mini EMS |
| `proxy/firewall_rules.ps1` | `New-NetFirewallRule`-Kommandos: Proxy-Port nur aus dem Kundennetz/VPN, `8090` eingehend aus dem Netz blockiert |
| `proxy/README.md` | Installation als geplanter Task, Firewall, Client-Zertifikat, Prüfschritte und Update-Zusammenspiel |

Kernpunkte der `Caddyfile` (verifiziert gegen die aktuelle Caddy-v2-Dokumentation):

- `bind 192.168.244.10` – der Proxy lauscht nur auf der EMS-LAN-IP, nicht auf allen Interfaces. Der `bind`-
  Wert enthält bewusst keinen Port; der Port kommt aus der Site-Adresse.
- `tls internal` – Caddy nutzt seine lokale, intern vertrauenswürdige CA und braucht keine Internet-CA.
- `reverse_proxy 127.0.0.1:8090` – Weiterleitung an die lokal gebundene Mini-EMS-API.
- Login und Rollen werden von Mini EMS geprüft. Caddy erhält bewusst keine zweite Benutzerverwaltung.

### 4.4 Was diese Stufe leistet – und was nicht

**Leistet (H4):**

- Die technische API ist **nicht mehr direkt im Netz**: Sie hört nur auf `127.0.0.1`, der einzige
  Netzwerk-Sprecher ist der Proxy.
- **TLS** für den UI-Zugriff über ein intern vertrauenswürdiges Zertifikat, ohne Internet-CA.
- Der Zugriff ist auf **genau einen Einstiegspunkt kanalisiert** (der Proxy), zusätzlich per Firewall auf
  das Kundennetz/VPN begrenzt.
- Persönliche Viewer-/Admin-Konten schützen Daten und Verwaltungsfunktionen hinter demselben HTTPS-Einstieg.
- Zusammen mit `api.read_only: true` bleiben Anlagenaktionen auch für Admins gesperrt (siehe 2.1).

**Leistet NICHT (bewusst nicht Teil von H4):**

- **Kein öffentliches Cloud-IAM.** Konten gelten lokal für genau diesen Standort. Zentrale Benutzerverwaltung,
  SSO und mandantenfähige Cloud-Rollen sind damit noch nicht gelöst.
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

1. **API lokal erreichbar:** auf der IPC `curl http://127.0.0.1:8090/api/health` → `HTTP 200` mit
   Health und Version; `curl http://127.0.0.1:8090/api/status` ohne Sitzung → `HTTP 401`.
2. **API nicht mehr im Netz:** vom zweiten Rechner (Kundennetz/VPN)
   `curl http://192.168.244.10:8090/api/health` → Verbindung abgelehnt/Timeout (weil `api.host=127.0.0.1`).
3. **Proxy lokal:** auf der IPC `curl -k https://<hostname>/api/health` → `HTTP 200` (Proxy erreicht die
   lokale API).
4. **Proxy vom zweiten Rechner:** aus dem Kundennetz/VPN `curl -k https://<hostname>/api/health` →
   `HTTP 200`; das Dashboard `https://<hostname>/` lädt und verlangt eine Anmeldung.
5. **read-only greift über den Proxy:** `curl -k -X POST https://<hostname>/api/config/spotmarket-lockout`
   → `HTTP 403` (`read_only_mode`); `curl -k https://<hostname>/api/diagnostics/read` → `HTTP 403`;
   `curl -k https://<hostname>/api/health` meldet `api_read_only: true`.
6. **TLS aktiv:** der Proxy antwortet auf `https://`, nicht auf `http://`; das Zertifikat stammt aus Caddys
   interner CA (bei `-k` akzeptiert; für vertrauenswürdige Anzeige die Root-CA auf dem Client importieren,
   siehe `proxy/README.md`).
7. **Firewall:** `Get-NetFirewallRule -DisplayName "MiniEMS*"` zeigt die Allow-Regel für den Proxy-Port und
   die Block-Regel für `8090`; ein Zugriff auf den Proxy-Port **von außerhalb** des Kundennetzes schlägt
   fehl.

**Historischer Nachweis Pilot-IPC 2026-07-08, vor H6:** Die IPC-seitige Umschaltung wurde ausgeführt. Die damalige
Standortkonfiguration setzte
`api.host: 127.0.0.1` und `api.read_only: true`, die produktive Caddyfile proxyt auf `127.0.0.1:8090`,
Mini EMS läuft nach Neustart über `MiniEmsPoCRelease`, und Caddy wurde reloadet. Lokal auf der IPC verifiziert:
`127.0.0.1:8090/api/status` meldet `api_read_only: true`, `192.168.244.10:8090` ist nicht mehr erreichbar,
`https://192.168.244.10/api/status` und `/dashboard` liefern HTTP 200, `GET /api/diagnostics/read` und
`POST /api/config/spotmarket-lockout` liefern HTTP 403, und die H4-Firewallregeln sind aktiv.

**Offene Standort-Schritte (nur am realen Standort nachweisbar, deshalb bleibt die H4-Checkbox offen):**

- Vom zweiten Rechner im freigegebenen Kundennetz/VPN/Secomea prüfen: `https://192.168.244.10/api/health`
  und Dashboard mit Anmeldung laden; `http://192.168.244.10:8090/api/health` darf nicht erreichbar sein.
- Von außerhalb des Kundennetz-/VPN-Bereichs prüfen, dass der Proxy-Port nicht erreichbar ist.
- **DoD-Nachweis:** Zugriff funktioniert nur aus dem freigegebenen Kundennetz/VPN, und die Anlagen-API ist
  nicht öffentlich erreichbar (Prüfschritte 2, 4, 7 gegen die reale Netztopologie). Dieser Nachweis kann nur
  am Standort erbracht werden.

---

## Querverweise

- `ROADMAP.md` – strategische To-do-Linie "Geschütztes Kundenhosting" (H1–H9) und To-do 3
- `PRODUCT_UX_KONZEPT.md`, Abschnitt 3 – aktuelles Rollenmodell Viewer/Admin und spätere Operator-Option
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
