# Mini EMS PoC - Technische Roadmap

## Kontext / Ist-Zustand

Aktiver Fokus liegt auf dem lokalen Python-Prototyp `mini_ems_poc/` (Branch `develop`, working tree clean).
Die juengsten Commits haben den ProtocolAdapter-Kontrakt, eine Plausibilitaets-Single-Source in `PointConfig` und
einen Freshness/Quality-Gate (`max_age_seconds`) eingebaut. Die 48 Python-Tests sind unter Python 3.12 alle gruen
(`OK`), schlagen aber unter dem Standard-`python3` (3.9) dieses Rechners wegen PEP-604-Syntax (`X | None`) fehl.
Es gibt praktisch keine TODO/FIXME-Marker im Python-Code; offene Punkte stehen in `MINI_EMS_ANLEITUNG.md`
("Offene Punkte") und ergeben sich aus dem Code-Ist-Zustand.

Diese Datei behandelt bewusst die technische Betriebs-, Architektur- und Sicherheitsseite. Produktwirkung,
Reporting-UX, Bedienbarkeit und visuelles UI-Design werden separat in `PRODUCT_UX_ROADMAP.md` geführt.

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
- `config.json` bleibt der reale IPC-Pfad; `config.local.json` bleibt Laptop-/Simulationspfad.
- Deployment-Flotte, Container und OTA kommen erst nach sauberem Integrationsmodell, Datenqualität und Schreibsicherheit.
- Reads und Writes werden als unterschiedliche Risikoklassen behandelt.
- Die Regelung soll langfristig nur noch kanonische Kanäle lesen, nicht BACnet-Objekte, Modbus-Register oder API-Felder.

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

- [ ] **S4. Danach Modbus TCP read-only als erster neuer Adapter**
  - **Was:** Erst nach S1-S3 einen read-only Modbus-TCP-Adapter für ein Leistungsmessgerät ergänzen.
  - **Nutzen:** Beweist, dass das Modell wirklich protokollneutral ist, ohne sofort neue Schreibrisiken einzubauen.
  - **Betroffen:** `protocol.py`, neuer Adapter, Config, Tests, Simulation.
  - **Aufwand:** M/L
  - **Risiken:** Registerlisten, Skalierung, Byte-/Word-Order und Vorzeichen müssen sauber geprüft werden.
  - **Definition of Done:** Ein kanonischer Kanal wie `meter.grid.active_power_kw` kann wahlweise aus BACnet oder Modbus
    stammen, ohne dass die Regelungslogik das Protokoll kennen muss.

## Strategische To-do-Linie: Geschütztes Kundenhosting

- [ ] **H1. Zielbild und Sicherheitsgrenze festlegen**
  - **Was:** Festlegen, dass Mini EMS auf kundeneigener IPC-Hardware laufen kann, aber nicht als frei einsehbarer
    Entwicklerordner ausgeliefert wird. Zugriff auf UI und API bleibt auf Kundennetz, VPN oder Secomea beschränkt.
  - **Nutzen:** Klärt die Erwartung: Es geht nicht um absolute Geheimhaltung gegen Administratoren, sondern um professionellen
    Betrieb ohne offenen Source-Code-Checkout und ohne öffentlich erreichbare Anlagen-API.
  - **Betroffen:** `README.md`, `MINI_EMS_ANLEITUNG.md`, spätere Installations-/Betriebsdoku.
  - **Aufwand:** S
  - **Risiken:** Keine Sicherheitsversprechen formulieren, die auf einer kundeneigenen IPC mit Admin-Zugriff nicht haltbar sind.
  - **Definition of Done:** Es ist dokumentiert, wer UI, Runtime-Dateien, Standortkonfiguration, Logs und Betriebsdaten sehen darf.

- [ ] **H2. Mini EMS als Release-Paket statt Git-Checkout ausliefern**
  - **Was:** Die Kunden-IPC bekommt kein vollständiges Repository mehr, sondern ein versioniertes Release-Paket, z. B.
    `mini_ems.exe`, `dashboard/`, `config.json`, Startskripte, Checksums und Versionsdatei.
  - **Nutzen:** Normale Nutzer können nicht einfach den gesamten Python-Code lesen. Updates werden kontrollierter und
    professioneller als ein manueller Git-Ordner auf der IPC.
  - **Betroffen:** Packaging-Konzept, `run_mini_ems.cmd`, `windows/install_task.ps1`, Release-Artefakt, Standortkonfiguration.
  - **Aufwand:** M
  - **Risiken:** PyInstaller ist einfacher, aber leichter extrahierbar; Nuitka ist für weniger beiläufige Code-Einsicht
    geeigneter, aber aufwendiger. `config.json` darf nicht in ein hart kodiertes Paket verschwinden.
  - **Definition of Done:** Eine Test-IPC kann Mini EMS ohne Git-Repo starten; der Betriebspfad bleibt `config.json` plus
    geplanter Windows-Task.

- [ ] **H3. Runtime-Dateien und Konfiguration sauber schützen**
  - **Was:** Installation z. B. unter `C:\Program Files\MiniEMS` oder `C:\ProgramData\MiniEMS`, mit Windows-Rechten nur
    für Administratoren und einen definierten Mini-EMS-Task-/Service-Benutzer. Logs, Datenbank und Standortkonfiguration
    werden getrennt abgelegt.
  - **Nutzen:** Verhindert zufälliges Bearbeiten, Kopieren oder Lesen durch normale Windows-Benutzer.
  - **Betroffen:** Installationspfade, Dateirechte, Log-/DB-Pfade, Update-Anleitung.
  - **Aufwand:** M
  - **Risiken:** Zu strenge Rechte dürfen den geplanten Task, Logs und Reports nicht blockieren.
  - **Definition of Done:** Normale Benutzer können das UI öffnen, aber Runtime-Dateien, Konfiguration und Logs nicht direkt
    durchsuchen oder ändern.

- [ ] **H4. API intern binden, UI über geschützten Zugriff bereitstellen**
  - **Was:** Die Mini-EMS-API nur an `127.0.0.1` oder eine definierte IPC-Netzwerkadresse binden. Davor optional einen
    lokalen Reverse Proxy setzen, der HTTPS, Login und Zugriffsbeschränkung übernimmt.
  - **Nutzen:** Die technische API wird nicht direkt im Netzwerk ausgestellt. Das UI wird kontrolliert erreichbar.
  - **Betroffen:** `config.json` `api.host`, Windows-Firewall, Reverse-Proxy-Konzept, Secomea/VPN-Regeln.
  - **Aufwand:** M
  - **Risiken:** Keine direkte Internet-Portfreigabe auf `8090`; keine Vermischung von lokalem Simulationspfad und echter IPC.
  - **Definition of Done:** Zugriff funktioniert nur aus freigegebenem Kundennetz/VPN; die bestehende Anlagen-API ist nicht
    öffentlich erreichbar.

- [ ] **H5. Read-only Netzwerkmodus zuerst**
  - **Was:** Für den ersten geschützten Netzwerkzugriff nur Dashboard, Status, Historie und Reports freigeben. Schreibende
    Endpunkte werden blockiert oder bleiben ausschließlich lokal/administrativ.
  - **Nutzen:** Echte Daten sind sichtbar, aber Anlagensteuerung bleibt geschützt.
  - **Betroffen:** HTTP-API, Dashboard, Reverse Proxy oder API-Gateway-Regeln, Doku zu erlaubten Endpunkten.
  - **Aufwand:** M
  - **Risiken:** UI darf keine verdeckten Konfigurations- oder Schreibfunktionen über denselben Zugriffspfad anbieten.
  - **Definition of Done:** Ein zweiter Rechner sieht echte IPC-Daten im UI; Schalt- und Konfigurationsaktionen sind über
    diesen Pfad nicht möglich.

- [ ] **H6. UI-Zugriff mit Login und einfacher Rollenlogik absichern**
  - **Was:** Mindestens Passwortschutz für das UI; später Rollen wie `viewer`, `operator`, `admin`. Für den ersten Schritt
    reicht ein kleiner, sauber dokumentierter Zugriffsschutz vor dem Dashboard.
  - **Nutzen:** Das UI ist nicht nur weniger sichtbar, sondern tatsächlich zugangsbeschränkt.
  - **Betroffen:** Reverse Proxy oder kleine Auth-Schicht, Nutzer-/Passwortverwaltung, Betreiberfreigabe.
  - **Aufwand:** M
  - **Risiken:** Passwörter dürfen nicht in Git oder im ausgelieferten Standardpaket landen; Erstpasswort/Rotation klären.
  - **Definition of Done:** Ohne Zugangsdaten ist das UI nicht erreichbar; Viewer können nur lesen.

- [ ] **H7. Update- und Wartungsprozess definieren**
  - **Was:** Updates laufen über versionierte Pakete, Checksums und ein kurzes Install-/Rollback-Verfahren. Keine manuellen
    Codeänderungen auf der Kunden-IPC.
  - **Nutzen:** Macht Mini EMS wartbar und reduziert Risiko durch lokale Änderungen.
  - **Betroffen:** Release-Prozess, Paketablage, Backup, Healthcheck, Rollback-Anleitung.
  - **Aufwand:** M
  - **Risiken:** Standortkonfiguration und Betriebsdaten dürfen bei Updates nicht überschrieben werden.
  - **Definition of Done:** Es gibt einen dokumentierten Ablauf: stoppen, Backup, Paket ersetzen, starten, Healthcheck prüfen,
    Rollback falls nötig.

- [ ] **H8. Audit, Nachvollziehbarkeit und Betreiberfreigabe**
  - **Was:** UI-Zugriffe, Runtime-Starts, Konfigurationsänderungen und spätere Schreibaktionen nachvollziehbar loggen.
    Kundenseitig klären, wer Zugriff bekommt.
  - **Nutzen:** Professioneller Betrieb statt versteckter Ordner auf Windows.
  - **Betroffen:** Logging, Betriebsdoku, Rollen-/Rechtekonzept, spätere Schreibfreigaben.
  - **Aufwand:** M
  - **Risiken:** Audit-Logs dürfen keine Geheimnisse oder unnötigen personenbezogenen Daten enthalten.
  - **Definition of Done:** Betriebslog und Zugriffskonzept sind für einen Pilotkunden erklärbar.

## Priorisierte To-do-Liste

- [ ] **1. Freshness-Gate scharf schalten (Config statt totem Code)**
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

- [ ] **2. Quality/Freshness im Dashboard sichtbar machen**
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

- [ ] **4. Runtime-Watchdog mit echtem Alarm (Offene Punkte #3)**
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

- [ ] **5. Python-Versions-Footgun entschaerfen (Toolchain/Doku)**
  - **Was:** Sicherstellen, dass die dokumentierten Befehle nur mit Python >= 3.10 laufen: in `README.md`/`AGENTS.md` den
    Versions-Hinweis prominenter machen bzw. einen `python_requires`/Versions-Check ergaenzen (z. B. fruehe Pruefung in `mini_ems.py`).
  - **Nutzen:** `python3 -m unittest ...` schlaegt auf Maschinen mit `python3` = 3.9 hart fehl (PEP-604 `X | None`),
    obwohl der Code korrekt ist. Senkt Onboarding-Reibung und falsche "Tests rot"-Schluesse.
  - **Betroffen:** `mini_ems.py` (optionaler Versions-Guard), `README.md`, `AGENTS.md`, `mini_ems_poc/AGENTS.md`.
  - **Aufwand:** S
  - **Risiken:** Sehr gering; rein additiv. Keine Verhaltensaenderung der Runtime.
  - **Definition of Done:** Ein Aufruf mit Python < 3.10 liefert eine klare Fehlermeldung statt eines `TypeError` tief im Import;
    Doku nennt den exakten Interpreter (z. B. `python3.12`); Tests unter 3.10+ bleiben gruen.

- [ ] **6. Doku-Pfade an Ist-Konfiguration angleichen**
  - **Was:** In `MINI_EMS_ANLEITUNG.md` die Pfade fuer SQLite/Log konsistent machen: Doku nennt `data/runtime/mini_ems.sqlite`
    und `logs/mini_ems.log`, die lokale Konfiguration nutzt `data/local/...` bzw. `data/runtime/...` je nach Umgebung.
  - **Nutzen:** Vermeidet falsche Pfadannahmen bei Betrieb/Debugging; rein redaktionell, kein Code-Risiko.
  - **Betroffen:** `MINI_EMS_ANLEITUNG.md` (lesend `config.json`, `config.local.json`).
  - **Aufwand:** S
  - **Risiken:** Keine (Doku-only). Echte Umlaute verwenden (`AGENTS.md` Abschnitt "German UI Language").
  - **Definition of Done:** Jede in der Anleitung genannte Datei-/DB-Pfadangabe entspricht den tatsaechlichen Werten in
    `config.json`/`config.local.json` (getrennt nach IPC und lokal).

## Empfohlener nächster Schritt

**Strategisch zuerst: S1 Edge Integration Contract dokumentieren.** Damit wird die Richtung vom PoC zum portablen
Edge-Integrationskern festgehalten, ohne den aktuellen Windows-IPC-Pilot infrage zu stellen.

**Operativ direkt danach: To-do 1 Freshness-Gate scharf schalten.** Höchstes Nutzen-x-Umsetzbarkeit-Verhältnis im
bestehenden Code: Der Quality-Gate ist bereits vollständig implementiert und getestet, aber durch fehlende
`max_age_seconds`-Werte in beiden Configs faktisch inaktiv. Mit reiner, risikoarmer Konfiguration (kein Logikeingriff,
keine Safety-Flags) wird ein zentrales Betriebs-Feature sofort wirksam. Anschließend logisch gefolgt von To-do 2
(Sichtbarmachung im Dashboard).

**Parallel als Betriebs-/Kundenpfad: H1, H2 und H4 vorbereiten.** Erst Sicherheitsgrenze und Auslieferungsmodell
festlegen, dann Release-Paket und geschützten UI-Zugriff im Kundennetz sauber beschreiben. Das schafft die Grundlage,
um echtes Monitoring außerhalb der lokalen Simulation zu zeigen, ohne die Anlagen-API oder den Quellcode unnötig
offenzulegen.
