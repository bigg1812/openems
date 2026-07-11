# Mini EMS – Demo-Flow für den bezahlten Pilot (UX13)

Dieses Dokument erledigt **UX13** aus `PRODUCT_UX_ROADMAP.md`: einen klaren, in fünf Minuten
durchführbaren Vorführpfad für einen Standortbetreiber oder Entscheider, der über einen
bezahlten Pilotbetrieb entscheidet. Es nutzt bewusst nur Ansichten und Endpunkte, die heute
wirklich existieren (siehe `PRODUCT_UX_KONZEPT.md`, `HOSTING_SICHERHEIT.md`, `UI_STYLEGUIDE.md`).
Wording folgt durchgehend `PRODUCT_UX_KONZEPT.md`, Abschnitt 2 – keine internen IDs oder
Protokollbegriffe im eigentlichen Vorführtext.

---

## 1. Ziel und Zielgruppe

- **Ziel:** In fünf Minuten zeigen, dass Mini EMS den Standort verständlich, ehrlich und
  professionell überwacht – als Entscheidungsgrundlage für einen bezahlten Pilotbetrieb.
- **Zielgruppe:** Standortbetreiber, Betriebsverantwortliche oder wirtschaftliche
  Entscheider – **nicht** Techniker. Es wird in Betreiber-Sprache vorgeführt, ohne BACnet-
  oder Protokollbegriffe.
- **Dauer:** 5 Minuten Vorführung, plus Puffer für 1–2 Rückfragen. Nicht länger machen –
  das ist der Kern des Leitbilds ("wenig erklären müssen").
- **Vorbereitung:**
  - Eine laufende Mini-EMS-Runtime mit Daten (lokal simuliert reicht für die Demo völlig aus;
    siehe Abschnitt 5.1). Mehrere Zyklen sollten bereits gelaufen sein, damit Verlaufsdiagramme
    und der Tagesbericht nicht leer wirken.
  - Ein Browser mit geöffnetem Dashboard (`http://127.0.0.1:8090` lokal, bzw. die
    EMS-LAN-Adresse des IPC im Kundennetz).
  - Falls die Vorführung von einem zweiten Rechner aus erfolgt: Secomea-Client oder VPN-Zugang
    ins Kundennetz gemäß `HOSTING_SICHERHEIT.md`, Teil 2, Pfad (a). Es wird **kein** eigener
    Zugang ins offene Internet benötigt und keiner freigeschaltet.
  - Kein Zugriff auf Konfigurationsdateien, Logs oder die Datenbank nötig – die gesamte
    Vorführung läuft über das UI.

---

## 2. Ablauf in 5 Schritten

### Schritt 1 – Dashboard öffnen (0:00–0:45)

- **Was wird gezeigt:** Startseite (`#/dashboard`), direkt nach dem Laden. Kurz auf die
  Hauptbotschaft (`status-hero`) oben zeigen.
- **Kernbotschaft:** „Das ist die Startseite für den Betreiber – sie zeigt auf einen Blick,
  ob die Anlage läuft und ob heute etwas zu tun ist."
- **Was der Kunde sehen soll:** Genau eine Hauptbotschaft oben (z. B. „Die Anlage lief heute
  durchgehend im Normalbetrieb."), darunter die wichtigsten Kennzahlen (Kennzahlenkarten) und
  den Hinweisbereich „Heute wichtig".
- **Worauf man NICHT abschweift:** Keine Diskussion von Datenpunkten, Reglern oder
  Konfiguration. Nicht auf „Konfiguration" oder „Systemstatus" klicken.

### Schritt 2 – Zustand verstehen (0:45–1:45)

- **Was wird gezeigt:** Kennzahlenkarten und den Hinweisbereich „Heute wichtig" auf derselben
  Startseite; kurz auf Preisdiagramm und „Geplante Preisfenster" zeigen.
- **Kernbotschaft:** „Mini EMS übersetzt Rohdaten automatisch in verständliche Hinweise – zum
  Beispiel, wann der Strompreis günstig ist oder wann ein Wert genauer geprüft werden sollte."
- **Was der Kunde sehen soll:** Aktueller Strompreis, ob die Preissteuerung gerade aktiv ist,
  und mindestens einen Hinweis im „Heute wichtig"-Bereich in normaler Alltagssprache.
- **Worauf man NICHT abschweift:** Keine Erklärung der Berechnungslogik (Viertelstunden-Regel,
  Schwellwerte). Es reicht: „Das System erkennt automatisch günstige Zeitfenster."

### Schritt 3 – Tagesreport erzeugen (1:45–3:00)

- **Was wird gezeigt:** Navigation zu „Berichte". Dort steht ganz oben die Karte „Tagesbericht":
  Berichtstag „Heute" ist bereits ausgewählt, ein Klick auf den Primärbutton „Bericht anzeigen"
  öffnet den fertigen Tagesbericht (`/api/report/html`) in einem neuen Tab.
- **Kernbotschaft:** „Ein Klick genügt: Der fertige, kundentaugliche Bericht steht sofort da –
  ganz ohne Zeitraum einstellen oder technische Felder ausfüllen. Er kann direkt gezeigt,
  gedruckt oder heruntergeladen werden."
- **Was der Kunde sehen soll:** Berichtskopf mit Standort und Datum, die Hauptbotschaft des
  Tages, Betriebszusammenfassung, Strompreis-Kennzahlen mit genutztem Preisfenster,
  Verlaufsdiagramme und den Hinweis auf den technischen Anhang weiter unten. Zurück auf der
  Berichte-Seite kurz auf die beiden Sekundärbuttons direkt neben „Bericht anzeigen" zeigen:
  „PDF herunterladen" und „Daten als CSV" – ein Bericht, drei Ausgabeformen, ohne weitere Klicks.
- **Worauf man NICHT abschweift:** Nicht in den technischen Anhang scrollen und dort Rohwerte
  erklären. Nicht den einklappbaren Bereich „Erweiterte Einstellungen" unterhalb der Karte
  aufklappen – das ist der vollständige Report-Baukasten (freier Zeitraum, Zeitraster,
  Bausteine, Datenpunkte) für Konfiguratoren, nicht Teil des Kundenpfads. Beim Button „PDF
  herunterladen": Ist auf dem Vorführrechner kein PDF-Renderer installiert, öffnet der Klick
  bewusst dieselbe HTML-Ansicht im neuen Tab statt eine `.pdf`-Datei herunterzuladen – das ist
  kein Fehler, sondern der dokumentierte Normalfall (siehe Abschnitt 3).

### Schritt 4 – Auffälligkeit erklären (3:00–4:00)

- **Was wird gezeigt:** Zurück zum Dashboard, Preisdiagramm bzw. „Geplante Preisfenster".
- **Kernbotschaft:** „Hier sieht man ein Beispiel: Gerade ist ein günstiges Preisfenster aktiv
  – die Anlage nutzt das automatisch, ohne dass jemand eingreifen muss." (Alternative, falls
  gerade kein Preisfenster aktiv ist: den nächsten geplanten Zeitraum zeigen: „Das nächste
  günstige Preisfenster ist um HH:MM – das plant das System schon jetzt ein.")
- **Was der Kunde sehen soll:** Eine konkrete, im Diagramm sichtbare Auffälligkeit – ein
  aktives oder bevorstehendes Preisfenster, oder alternativ einen „veraltet"-Hinweis
  (Quality-Badge) an einer Kennzahl.
- **Reproduktion, falls nichts natürlich auftritt:**
  - **Bevorzugt (Preisfenster):** Die mitgelieferten Beispielpreise (`sim/sample_prices.json`)
    enthalten in der lokalen Simulation regelmäßig negative bzw. sehr günstige Viertelstunden;
    ein aktives oder in Kürze startendes Preisfenster ist damit in aller Regel ohne weiteres
    Zutun zu sehen. Vor der Demo kurz `/api/status` prüfen (Feld `spotmarket_active_now` bzw.
    `spotmarket_next_window`) und den Zeitpunkt der Vorführung passend legen.
  - **Alternative (veralteter Messwert):** Wenn stattdessen ein „Wert veraltet"-Badge gezeigt
    werden soll, die laufende Runtime für gut zwei Minuten pausieren (Prozess kurz anhalten,
    ohne die Konfiguration zu ändern) und danach das Dashboard neu laden. Da einzelne
    Messwerte nach `max_age_seconds` (in der Simulation 120 Sekunden) als veraltet gelten,
    erscheint dann automatisch der Hinweis „Wert veraltet: … Diese Werte werden angezeigt,
    aber nicht mehr für Entscheidungen genutzt." Anschließend die Runtime wieder starten,
    damit der Wert nach dem nächsten Zyklus wieder als aktuell markiert wird.
- **Worauf man NICHT abschweift:** Nicht andeuten, dass „veraltet" gleich „Störung" ist. Nicht
  in Diagnosedetails (Preisprüfung, technische Systemseite) wechseln – das bleibt Schritt 5
  vorbehalten.

### Schritt 5 – Systemstatus prüfen (4:00–5:00)

- **Was wird gezeigt:** Navigation zu „Systemstatus", dort die Kachel „Signale" und die Tabelle
  „Letzte Läufe".
- **Kernbotschaft:** „Auf der Systemseite sieht man jederzeit, ob die Anlage zuverlässig läuft
  – inklusive der letzten Durchläufe. Das ist die Grundlage für Vertrauen im laufenden
  Betrieb."
- **Was der Kunde sehen soll:** Den aktuellen Gesamtzustand (z. B. „Normalbetrieb"), die Liste
  der letzten Läufe mit Zeitstempel, und dass Datenqualität sowie Preisübergabe sichtbar
  gemacht werden.
- **Worauf man NICHT abschweift:** Den Button „Preis prüfen" (aktiver Lesezugriff auf die
  Anlage) nicht live auslösen und nicht als Kernfunktion der Demo behandeln – das ist eine
  Operator-Diagnosefunktion, kein Teil des Betreiber-Vorführpfads. Nicht in Konfigurationsfelder
  oder Logdateien wechseln.

---

## 3. Ehrlichkeit und Grenzen der Demo

Diese Demo darf keine Versprechen machen, die der reale Standort noch nicht einlöst
(Roadmap-Risikohinweis zu UX13). Konkret gilt:

- **Die Demo zeigt echte oder realistische Simulationsdaten, keine geschönten Fantasiewerte.**
  Im lokalen Modus stammen die Werte aus `sim/sample_values.json` und
  `sim/sample_prices.json` – das wird auf Nachfrage offen benannt, nicht verschleiert.
- **Schreibzugriffe auf die Anlage sind in der Demo nie live.** Im lokalen Modus ist
  `real_writes_enabled=false` erzwungen; auf der IPC bleiben Schreibfreigaben ausschließlich
  lokal-administrativer Betrieb (siehe `HOSTING_SICHERHEIT.md`, 1.2).
- **Der Netzwerkzugriff bleibt read-only und auf Kundennetz/VPN/Secomea beschränkt.** Es gibt
  keine offene Portfreigabe ins Internet und keine Vermischung von Simulations- und
  IPC-Pfad (`config.local.json` vs. `config.json`).
- **Login und Rollentrennung sind Konzept, noch keine technische Umsetzung.** Das
  Rollenmodell (Viewer/Operator/Admin) ist fachlich in `PRODUCT_UX_KONZEPT.md`, Abschnitt 3
  festgelegt, aber es gibt heute noch keine echte Login-Schicht vor dem Dashboard (siehe
  `ROADMAP.md`, H6). In der Demo wird das offen so benannt, falls danach gefragt wird –
  nicht als „schon fertig" dargestellt.
- **Die Mapping-/Inbetriebnahme-Ansicht („Standort einrichten") ist gebaut, aber nicht Teil der
  5-Minuten-Demo.** Die Konfigurationsseite führt inzwischen als geführter Ablauf Standort → Geräte →
  Datenpunkte → Testen → Abschließen mit fachlicher Mapping-Tabelle und „Alle Punkte testen"
  (`PRODUCT_UX_ROADMAP.md`, UX14–UX16, erledigt). Das bleibt trotzdem außerhalb der eigentlichen
  Betreiber-Vorführung: Die Demo zeigt Betrieb und Reporting, nicht die Inbetriebnahme-Strecke, weil
  sich Standort einrichten an Konfiguratoren richtet, nicht an den Standortbetreiber. UX17
  (Punktlisten-Import/Discovery als vollständig geführter Prüfprozess) bleibt offen – siehe der
  optionale Abschnitt 6 für Konfiguratoren, der jetzt sowohl den UI- als auch den API-Weg nennt.
- **Netzleistung („Grid") kann in der Simulation ohne Wert bleiben.** Die Kennzahlenkarte zeigt
  dann „-", der Tagesbericht „kein Messwert". Der Grid-Lockout-Kanal ist in der mitgelieferten
  Laptop-Simulation bewusst deaktiviert (`controllers.grid_lockout.enabled = false`, siehe
  `config.local.json`); auf der echten IPC ist der Netzleistungs-Messwert aktiv. Falls
  Netzleistung in der Demo leer bleibt, wird das ehrlich als Simulationslücke benannt, nicht
  kaschiert.
- **Der PDF-Export ist optional und fällt kontrolliert auf HTML zurück.** Der Button „PDF
  herunterladen" auf der Berichte-Seite ruft `/api/report/pdf` auf. Ist auf dem Zielrechner
  kein PDF-Renderer (WeasyPrint) installiert, liefert dieser Aufruf dieselbe kundentaugliche
  HTML-Ansicht statt eines echten PDF – dokumentiertes Verhalten, kein Fehler. Für den echten
  Pilotbetrieb muss der PDF-Pfad auf der Ziel-IPC noch verlässlich eingerichtet werden (offener
  Punkt aus `PRODUCT_UX_KONZEPT.md`, Abschnitt 1.2).

---

## 4. Troubleshooting: die wahrscheinlichsten Pannen

| Problem | Woran erkennbar | Sofortmaßnahme |
| --- | --- | --- |
| Runtime läuft nicht / Dashboard lädt nicht | Browser zeigt „Verbindung unterbrochen" oder die Seite lädt dauerhaft „Anlagenstatus wird geladen." | Prüfen, ob der Mini-EMS-Prozess läuft (lokal: `python3.12 mini_ems.py --config config.local.json --loop`); danach Seite neu laden. Nicht live neu starten, während der Kunde zusieht – vorher testen. |
| Keine Preisdaten / leeres Preisdiagramm | Kennzahl „Aktueller Strompreis" zeigt „-", Preisdiagramm ist leer | Vorab mit `GET /api/status` prüfen, ob `price_cache.today` gefüllt ist. Im lokalen Modus notfalls die Runtime einmal neu starten, damit die Beispielpreise aus `sim/sample_prices.json` neu geladen werden. |
| Leerer oder wirkender „falscher" Tagesbericht | `/api/report/html` zeigt „Für diesen Tag liegen noch keine Betriebsdaten vor." | Kein Fehler, sondern korrektes Verhalten für Tage ohne Zyklen. Vor der Demo sicherstellen, dass der Bericht ohne `?date=`-Parameter (oder mit dem heutigen Datum) geöffnet wird, und dass vorher mindestens ein paar Zyklen gelaufen sind. |
| Netzleistung dauerhaft ohne Wert | Kennzahlenkarte „Netzleistung" zeigt „-", im Tagesbericht steht „kein Messwert" | In der Laptop-Simulation ist das erwartetes Verhalten (Grid-Kanal deaktiviert, siehe Abschnitt 3). Auf der echten IPC stattdessen prüfen, ob `grid_active_power_kw`/`grid_lockout` in `config.json` aktiv und die BACnet-Verbindung zum Controller erreichbar ist. |

---

## 5. Anhang: Vorbereitungs-Kommandos und Prüf-URLs

Dieser Abschnitt ist technischer Anhang für die vorführende Person, nicht Teil des
Kundengesprächs.

### 5.1 Lokale Simulation starten (Laptop-Vorbereitung)

```bash
cd /Users/gabriel/dev/openems/mini_ems_poc
/Users/gabriel/dev/openems/.venv/bin/python3.12 mini_ems.py --config config.local.json --loop
```

Hinweise:

- Python-Version muss >= 3.10 sein; die Projekt-`.venv` (`python3.12`) ist der geprüfte Pfad.
- `config.local.json` bindet die API lokal auf `http://127.0.0.1:8090` und erzwingt
  `bacnet_mode=simulated` sowie `real_writes_enabled=false` – sicher für eine Vorführung ohne
  echte Anlage.
- Vor der Demo mindestens 3–5 Minuten laufen lassen, damit mehrere Zyklen und ein sichtbarer
  Verlauf im Diagramm entstehen. Für den Tagesbericht reicht bereits ein Zyklus, wirkt aber
  überzeugender mit mehreren.
- Auf der echten IPC läuft die Runtime bereits über den Scheduled Task (siehe
  `MINI_EMS_ANLEITUNG.md`, „Automatischer Hintergrundbetrieb"); dort ist kein manueller Start
  nötig, nur die Erreichbarkeit über Secomea/VPN gemäß `HOSTING_SICHERHEIT.md` zu prüfen.

### 5.2 Prüf-URLs vor der Vorführung

```text
GET /                          -> Dashboard lädt (HTTP 200)
GET /api/status                -> health.status = "healthy", price_cache gefüllt
GET /api/spotmarket/windows     -> mindestens ein Preisfenster heute oder morgen
GET /api/report/html            -> Tagesbericht mit mindestens einem Zyklus
GET /api/history?channel_id=site.outdoor_temperature_c&granularity=5m
                                 -> Verlaufsdaten für das Diagramm
```

Kurzcheck per `curl` (lokal):

```bash
curl -s http://127.0.0.1:8090/api/status | python3 -m json.tool | head -30
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8090/api/report/html
curl -s -o /dev/null -w "%{http_code}\n" "http://127.0.0.1:8090/api/report/html?date=$(date +%Y-%m-%d)"
```

### 5.3 Zugriff über einen zweiten Rechner (Kundenstandort)

Siehe `HOSTING_SICHERHEIT.md`, Abschnitt 2.5 („Schritt-für-Schritt-Checkliste für den
Piloten, Pfad a"): `api.host` bleibt auf der EMS-LAN-IP, Firewall/Secomea-Freigabe nur auf
`<ipc-ip>:8090`, keine Freigabe von BACnet-Port `47808`. Nur lesen, nicht ändern.

---

## 6. Ausblick Inbetriebnahme: Standort einrichten und Punktlisten-Import (optional, nur für Konfiguratoren)

Dieser Baustein ist **kein Teil der 5-Minuten-Kundendemo** und richtet sich nicht an den
Standortbetreiber, sondern an die Person, die einen neuen Standort technisch einrichtet
(Konfigurator/Inbetriebnahme, siehe `ROADMAP.md`, S8). Nur zeigen, wenn im Anschluss an die
eigentliche Vorführung ausdrücklich danach gefragt wird, z. B. „Wie kommen die Datenpunkte
eigentlich rein?" – nicht als Teil des Betreiber-Gesprächs.

- **Was heute existiert:** Die Konfigurationsseite führt als „Standort einrichten" geführt durch
  Standort → Geräte → Datenpunkte → Testen → Abschließen (`PRODUCT_UX_ROADMAP.md`, UX14–UX16,
  erledigt). Einstieg in „Datenpunkte" ist ein Punktlisten-Upload (CSV/TSV/XLSX) im UI, der intern
  `POST /api/config/pointlist/import` aufruft und daraus Rohpunkt-Kandidaten sowie einen
  Mapping-Entwurf erzeugt (`mini_ems_runtime/pointlist_import.py`); eine BACnet-Discovery-Vorschau
  ist als sekundärer Weg im UI verfügbar und nutzt `POST /api/config/discovery/bacnet/preview` über
  einen getrennten, read-only `BACpypes3`-Werkzeugpfad (`mini_ems_runtime/bacnet_discovery.py`;
  Entscheidung siehe `BACNET_STACK_EVAL.md`). Die zentrale Mapping-Tabelle zeigt fachliche Bedeutung,
  Quelle und Live-Wert statt technischer Rohpunkte; „Alle Punkte testen" prüft alle Zuordnungen
  nacheinander in Inbetriebnahme-Sprache.
- **Was es (noch) nicht ist:** Der vollständig geführte Prüfprozess für Import und Discovery
  (Quelle wählen, Spalten erkennen, Kandidaten gruppieren, Schreibpunkte separat freigeben) ist
  weiterhin offen – das ist `PRODUCT_UX_ROADMAP.md`, UX17. Ohne lokalen Freigabecode bleibt
  „Einrichtung abschließen" im UI sichtbar, aber als gesperrt erklärt.
- **Was daraus wird:** Import und Discovery erzeugen ausschließlich Kandidaten für einen
  Mapping-Entwurf, nie aktive Mini-EMS-Kanäle. Aktivierung bleibt an den bestehenden,
  validierten Pfad `POST /api/config/mapping/preview` bzw. `activate` gebunden (Backup, Audit,
  Freigabe – siehe `ROADMAP.md`, S5/S6, erledigt). Aktiver Stand, offener Entwurf und ausstehender
  Neustart werden getrennt angezeigt; der bereinigte H8-Änderungsverlauf steht direkt darunter.
- **Kurzbeispiel für den API-Weg (technischer Anhang, kein Vorführtext):** Der Import ist auch
  direkt über die HTTP-API nutzbar, ohne die UI, z. B. für Skripte oder Tests.

  ```bash
  curl -s -X POST http://127.0.0.1:8090/api/config/pointlist/import \
    -H "Content-Type: application/json" \
    -d '{"filename":"datenpunkte.csv","content":"Object Reference;Name;Unit;Value;Mini EMS Kanal\n/100.AV300;Netzleistung;kW;42,3;grid.active_power_kw\n"}'
  ```

  Die Antwort enthält `devices`, `candidates`, `raw_points` und einen `mapping_draft` – noch
  keine aktive Konfiguration.
