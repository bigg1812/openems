# Mini EMS – Produkt- und UX-Konzept: Reporting, Wording, Rollen

Dieses Dokument erledigt die Aufgaben **UX1 (Reporting-Zielbild)**, **UX10 (Wording-Set)** und
**UX11 (Rollenmodell)** aus `PRODUCT_UX_ROADMAP.md`. Es ist bewusst am Ist-Zustand verankert:
an den heute vorhandenen Daten, Endpunkten und Dashboard-Seiten. Was noch fehlt, ist als
**Fehlt noch** markiert und erfindet keine Funktionen, für die es keine Daten gibt.

Leitbild (aus der UX-Roadmap): ruhiger, moderner Energie-Leitstand in deutscher Betreiber-Sprache –
kein Technikmonitor, keine internen IDs, keine Protokollbegriffe in normalen Nutzeransichten.

**Praxisbefund vom 12.07.2026:** Die erste Release-Abnahme auf der IPC hat gezeigt, dass verständliche
Begriffe allein nicht reichen. Zu viele gleichgewichtete Seiten, alle fünf Einrichtungsschritte auf einmal
und mehrere Freigabecode-Felder haben die Software trotz funktionierender Technik unnötig schwer bedienbar
gemacht. Seitdem gilt zusätzlich: Betrieb ist die Standardoberfläche, Verwaltung wird bewusst geöffnet,
und ein geführter Ablauf zeigt immer nur den aktuellen Schritt.

---

## 1. Reporting-Zielbild (UX1)

### 1.1 Datenbasis heute

Reports können nur zeigen, was die Runtime tatsächlich erfasst. Stand heute liegen vor
(SQLite `runtime_db.py`, API `http_api.py`):

| Datenbestand | Quelle / Endpunkt | Inhalt |
| --- | --- | --- |
| Tagesreport | `GET /api/report/daily` (JSON), `/api/report/daily.csv` | Anzahl Läufe, Status-Verteilung (Normalbetrieb / eingeschränkt / sicherer Modus), Netzleistung (Min/Max/Mittel), Strompreis (Min/Max/Mittel), geplante Preisfenster, Kommunikationshinweise |
| Konfigurierbarer Bericht | `GET /api/report/html`, `/api/report/pdf`, `POST /api/report/preview` | Frei wählbarer Zeitraum, Zeitraster (Einzelwerte/5m/1h/1d), Datenpunkte; Bausteine: Kennzahlen, Liniendiagramm, Säulendiagramm, Heatmap, Datentabelle, Textbaustein, Kommunikationshinweise |
| Messwert-Historie | `GET /api/history` | Alle kanonischen Datenpunkte (Preise, Temperaturen, Zähler, Netzleistung) mit Rollups 5 Minuten / 1 Stunde / 1 Tag |
| Anlagenzustand | `GET /api/status` | Health (Status, sicherer Modus, Preisübergabe), letzte Läufe, Preis-Cache, Preisfenster-Plan |
| Report-Studio | `GET /api/report/studio` | Tages-Kennzahlen; Zeitfenster Woche/Monat/Frei sind angelegt, aber noch als „nicht bereit" markiert |

**Hinweis PDF:** `/api/report/pdf` liefert nur dann echtes PDF, wenn WeasyPrint installiert ist;
sonst fällt es auf HTML zurück. Für den Kundeneinsatz muss der PDF-Pfad auf der IPC verlässlich sein.

### 1.2 Priorisierte Reports (die ersten drei)

#### Prio 1: Tagesbericht

- **Zielgruppe:** Standortbetreiber und Betriebsverantwortliche; sekundär interne Abstimmung.
- **Inhalt:**
  1. Kopf: Standort, Datum, Erstellzeitpunkt.
  2. Betriebszusammenfassung: Läufe gesamt, davon Normalbetrieb / eingeschränkt / sicherer Modus;
     eine kurze Hauptbotschaft in einem Satz (z. B. „Die Anlage lief heute durchgehend im Normalbetrieb.").
  3. Strompreis: Tagesmittel, günstigster und höchster Preis, genutzte bzw. geplante Preisfenster.
  4. Netzleistung: Min/Max/Mittel des Tages.
  5. Kommunikationshinweise: Anzahl und die letzten relevanten Meldungen in Betreiber-Sprache.
  6. Optional: eigener Textbaustein des Betreibers (Bewertung, Maßnahmen).
- **Ausgabeformat:** HTML-Ansicht im Dashboard, PDF-Download; CSV/JSON als Datenexport für Weiterverarbeitung.
- **Heute schon möglich:** Alle Kennzahlen und die Rohausgabe existieren (`/api/report/daily`,
  konfigurierbarer HTML/PDF-Bericht, Berichte-Seite im Dashboard).
- **Fehlt noch:** Kundentaugliches Template mit Titelkopf und Interpretationssatz (→ UX2),
  Energie-Kennzahlen je Erzeuger (BHKW, Pellet, Gas) als feste Tagesbausteine statt manueller
  Datenpunktauswahl, verlässlicher PDF-Pfad auf der IPC.

#### Prio 2: Anlagenstatus-Bericht

- **Zielgruppe:** Betreiber vor Ort und Servicetechnik; auch als Gesprächsgrundlage bei Störungen.
- **Inhalt:**
  1. Aktueller Gesamtzustand in einem Satz (Normalbetrieb / eingeschränkter Betrieb / sicherer Modus mit Grund).
  2. Datenqualität: Welche Messwerte sind aktuell, welche veraltet oder gestört.
  3. Preisübergabe an die Anlage: bestätigt / wartend / gestört, mit Zeitpunkt.
  4. Letzte Läufe mit Status und Zeitstempel.
  5. Nächster sinnvoller Schritt als Handlungsempfehlung (z. B. „Verbindung zur Anlage prüfen").
- **Ausgabeformat:** Zuerst als Live-Ansicht (Systemseite im Dashboard); Export als PDF-Abschnitt
  oder Anhang des Tagesberichts in einem zweiten Schritt.
- **Heute schon möglich:** Systemseite mit Signalen, letzten Läufen und Preisprüfung;
  alle Daten liegen in `/api/status` vor.
- **Fehlt noch:** Exportierbare Momentaufnahme („Statusbericht als PDF"), Erkennung einer
  eingefrorenen Runtime (Watchdog, technische Roadmap To-do 4) und deren verständliche Meldung.

#### Prio 3: Wochenübersicht

- **Zielgruppe:** Betreiber und Management; Blick auf Trends statt Einzeltage.
- **Inhalt:**
  1. Wochenverlauf Strompreis (Tagesmittel, Spannweite) und genutzte Preisfenster je Tag.
  2. Energiezähler-Differenzen je Erzeuger über die Woche (BHKW elektrisch/thermisch, Pellet, Gas).
  3. Betriebsqualität: Anteil Normalbetrieb, Anzahl Tage mit Einschränkungen oder sicherem Modus.
  4. Auffälligkeiten der Woche als kurze Liste.
- **Ausgabeformat:** HTML/PDF; kein separater CSV-Export nötig (Tages-CSV reicht als Rohdatenpfad).
- **Heute schon möglich:** Die Datenbasis existiert (1-Tages-Rollups, frei wählbarer Zeitraum im
  konfigurierbaren Bericht) – eine Wochenauswertung ist damit manuell bereits erzeugbar.
- **Fehlt noch:** Wochen-Preset im Report-Studio (dort bereits angelegt, aber als „nicht bereit"
  markiert), Vergleich zur Vorwoche, automatische wöchentliche Erzeugung.

### 1.3 Bewusst zurückgestellt (keine Datenbasis)

- **Einsparpotenzial in Euro:** Es gibt keine Referenzlast und keine Tarif-Gegenrechnung; ohne
  belastbare Baseline wäre jede Euro-Zahl ein Versprechen ohne Grundlage.
- **Betriebsnotizen / Logbuch:** Es gibt keinen Speicher für Nutzereinträge; der Textbaustein im
  konfigurierbaren Bericht deckt den ersten Bedarf ab.
- **CO₂-Bilanz:** Keine Emissionsfaktoren im System.

Diese Punkte bleiben Kandidaten für später, sind aber ausdrücklich nicht Teil der ersten drei Reports.

---

## 2. Wording-Set (UX10)

### 2.1 Grundregeln

1. Deutsch mit echten Umlauten, kurze Hauptsätze, keine Abkürzungen ohne Einführung.
2. Keine internen IDs (`ems.lockout_spotmarket`), keine Protokollbegriffe (BACnet, Objekt, Register)
   und keine englischen Zustandswörter (`stale`, `safe_mode`) in normalen Nutzeransichten.
   Ausnahme: die Preisprüfung auf der Systemseite ist ausdrücklich technische Diagnose.
3. Jede Warnung nennt den Zustand **und** den nächsten sinnvollen Schritt.
4. Nicht dramatisieren, nicht verharmlosen: „veraltet" heißt veraltet, nicht „Störung" und nicht „alles gut".

### 2.2 Systemzustand

| Interner Begriff / Zustand | UI-Text | Erklärtext |
| --- | --- | --- |
| `healthy` (Zyklusstatus) | Normalbetrieb | Die Anlage läuft normal. Alle Werte werden regelmäßig gelesen und übergeben. |
| `degraded` (Zyklusstatus) | Eingeschränkter Betrieb | Die Anlage läuft weiter, aber einzelne Werte konnten nicht übertragen werden. Details stehen im Systemzustand. |
| `safe_mode` (Zyklusstatus) | Sicherer Modus | Die Steuerung wurde vorsorglich angehalten. Die Anlage läuft eigenständig weiter. Bitte den Systemzustand prüfen. |
| `safe_mode_reason: startup_validation` | Anlaufprüfung aktiv | Nach dem Start prüft das System zuerst alle Verbindungen und Werte, bevor es eingreift. |
| `safe_mode_reason: price_provider…` | Preisdaten nicht verfügbar | Die aktuellen Strompreise konnten nicht abgerufen werden. Die Steuerung pausiert, bis wieder Preise vorliegen. |
| `safe_mode_reason: grid_read…` | Netzleistung nicht lesbar | Der Messwert der Netzleistung kommt nicht an. Bitte die Verbindung zur Anlage prüfen. |
| `safe_mode_reason: write_failure…` | Übergabe an die Anlage gestört | Werte konnten nicht an die Anlage übergeben werden. Bitte die Verbindung zur Anlage prüfen. |
| Veraltete Runtime (geplant, Watchdog) | Keine aktuellen Daten vom System | Das System hat sich seit einiger Zeit nicht gemeldet. Die angezeigten Werte können veraltet sein. Bitte den Betrieb der Steuerung prüfen. |
| Kein API-Zugriff (Frontend-Fehler) | Verbindung unterbrochen | Die Daten konnten nicht geladen werden. Bitte die Verbindung zur lokalen Anlage prüfen. |

### 2.3 Datenqualität einzelner Messwerte

| Interner Begriff / Zustand | UI-Text | Erklärtext |
| --- | --- | --- |
| `quality: good` | aktuell | Der Messwert ist frisch und plausibel. (Im UI unauffällig, kein Badge nötig.) |
| `quality: stale` | veraltet | Der Wert wurde zuletzt vor längerer Zeit aktualisiert. Er wird angezeigt, aber nicht mehr für Entscheidungen genutzt. |
| `quality: bad` | gestört | Für diesen Messpunkt liegt kein gültiger Wert vor. Bitte die Verbindung zur Anlage prüfen. |
| Fehlender Wert (`value: null`, `-`) | kein Messwert | Für diesen Punkt liegt aktuell kein Wert vor. |
| `status: warning` (Diagnose) | mit Einschränkung | Die Prüfung war erfolgreich, aber nicht alle Einzelmessungen kamen an. |
| `value_out_of_range` | Wert außerhalb des erwarteten Bereichs | Der gemessene Wert ist unplausibel und wird nicht verwendet. |
| Zeitüberschreitung (`timeout`) | Anlage antwortet nicht rechtzeitig | Die Anlage hat auf die Anfrage nicht rechtzeitig geantwortet. Bitte später erneut prüfen. |
| BACnet-Ereignisse (`bacnet_events`) | Kommunikationshinweise | Meldungen aus dem Datenaustausch mit der Anlage, z. B. verzögerte oder fehlgeschlagene Übertragungen. |

### 2.4 Steuerung und Betrieb

| Interner Begriff / Zustand | UI-Text | Erklärtext |
| --- | --- | --- |
| `ems.lockout_spotmarket` | Preissteuerung | Sperrt die Wärmepumpe in teuren Stunden und gibt sie in günstigen Preisfenstern frei. |
| `ems.lockout_grid` | Netzschutz | Begrenzt den Betrieb, wenn die Netzleistung zu hoch wird. |
| `spotmarket_active_now: true` | Preissteuerung aktiv | Die Anlage befindet sich gerade in einem geplanten Preisfenster. |
| Lockout-Zustand `disabled` | deaktiviert | Diese Funktion ist derzeit ausgeschaltet und greift nicht ein. |
| Lockout-Zustand `monitoring` | beobachtet | Die Funktion misst mit, greift aber nicht in den Betrieb ein. |
| Lockout-Zustand `active` | aktiv | Die Funktion greift derzeit aktiv in den Betrieb ein. |
| `confirmed: false` (Write-Status) | wartet auf Bestätigung | Der Wert wurde gesendet; die Rückmeldung der Anlage steht noch aus. |
| `last_error` (Write-Status) | Übergabe gestört | Der letzte Übertragungsversuch ist fehlgeschlagen. Details stehen im Systemzustand. |

### 2.5 KPI-Namen (Dashboard)

| Interner Kanal / Wert | KPI-Name | Erklärtext (Untertitel/Tooltip) |
| --- | --- | --- |
| `tariff.current_price_ct_kwh` | Aktueller Strompreis | Börsenstrompreis für das laufende Zeitfenster, in ct/kWh. |
| Tagesminimum Preis | Günstigster Preis heute | Niedrigster Viertelstundenpreis des Tages. |
| Tagesmaximum Preis | Höchster Preis heute | Höchster Viertelstundenpreis des Tages. |
| `tomorrow_prices_available` | Preise morgen | Zeigt, ob die Strompreise für morgen bereits vorliegen. |
| `grid.active_power_kw` | Netzleistung | Aktuelle Leistung am Netzanschluss, in kW. |
| `site.outdoor_temperature_c` | Außentemperatur | Gemessene Außentemperatur am Standort. |
| `site.buffer_*_temperature_c` | Puffer 1/2 oben/unten | Temperatur im Wärmespeicher, oben und unten gemessen. |
| `site.chp_*` | BHKW Vorlauf / Rücklauf / elektrisch / thermisch | Werte des Blockheizkraftwerks. |
| `site.boiler_1_*` / `site.boiler_2_*` | Gaskessel / Pelletkessel Vorlauf/Rücklauf | Temperaturen der Kessel. |
| `site.*_thermal_energy_kwh` | Wärmemenge (BHKW/Pellet/Gas) | Zählerstand der erzeugten Wärme, in kWh. |

### 2.6 Reporttitel und Bausteine

| Intern | UI-Text | Erklärtext |
| --- | --- | --- |
| daily report | Tagesbericht | Zusammenfassung eines Betriebstags: Zustand, Preise, Preisfenster, Hinweise. |
| status report | Anlagenstatus | Momentaufnahme des Systemzustands mit Datenqualität und letzten Läufen. |
| weekly report | Wochenübersicht | Trends der Woche: Preise, Wärmemengen, Betriebsqualität. |
| `summary` | Kennzahlen | Min-, Max- und Mittelwerte der gewählten Datenpunkte. |
| `line_chart` / `bar_chart` | Liniendiagramm / Säulendiagramm | Verlauf der gewählten Datenpunkte im Berichtszeitraum. |
| `heatmap` | Heatmap | Werteverteilung über Tage und Uhrzeiten. |
| `table` | Datentabelle | Einzelwerte des Berichtszeitraums als Tabelle. |
| `text` | Textbaustein | Eigener Kommentar des Betreibers zum Berichtszeitraum. |
| `events` | Kommunikationshinweise | Meldungen aus dem Datenaustausch mit der Anlage im Berichtszeitraum. |

---

## 3. Rollenmodell (UX11)

Fachliche Definition der Rollen **Viewer**, **Operator** und **Admin**. Der Pilot setzt davon bereits zwei
Oberflächenstufen um: Viewer/Operator sehen zuerst den Betrieb; Admin öffnet die Verwaltung einmalig mit
dem vorhandenen Freigabecode. Der Code wird serverseitig geprüft und nur im Arbeitsspeicher der geöffneten
Browserseite gehalten. Persönliche Konten, Rechte pro Benutzer und eine eigenständige Operator-Anmeldung
bleiben Teil der späteren Login-/Hosting-Logik (technische Roadmap H6).

### 3.1 Prinzipien

1. **Read-only zuerst (konsistent mit H5):** Der erste Netzwerkzugriff von außerhalb der IPC ist
   die Viewer-Rolle. Alles, was in den Betrieb eingreift oder die Anlage aktiv anspricht, gehört
   mindestens zur Operator-Rolle und bleibt zunächst dem lokalen bzw. ausdrücklich freigegebenen
   Zugriff vorbehalten.
2. **Sehen ist nicht Steuern:** Auch Viewer sehen ehrliche Zustände inklusive Warnungen – Vertrauen
   entsteht durch Sichtbarkeit, nicht durch Ausblenden. Nur Eingriffe sind rollenbeschränkt.
3. **Technische Details wandern nach oben:** Interne IDs, Rohdiagnosen, Konfigurationsdateien und
   Logs erscheinen erst ab Operator (Diagnose) bzw. Admin (Systemdateien).
4. **Keine verdeckten Schreibpfade:** Eine Ansicht darf keiner Rolle Aktionen anbieten, die ihr
   nicht erlaubt sind – Buttons werden ausgeblendet, nicht nur deaktiviert (H5-Risikohinweis).

### 3.2 Rollen im Überblick

| Rolle | Typische Person | Kernfrage |
| --- | --- | --- |
| Viewer | Kundenseitige Ansprechperson, Management, Gast per VPN/Secomea | „Läuft die Anlage, und was hat sie geleistet?" |
| Operator | Betreiber/Hausmeister vor Ort, Energieverantwortlicher | „Muss ich etwas tun, und darf ich Einstellungen anpassen?" |
| Admin | Interner Betrieb / Inbetriebnahme / Service | „Ist das System richtig konfiguriert und wartbar?" |

### 3.3 Seiten je Rolle

| Seite | Viewer | Operator | Admin |
| --- | --- | --- | --- |
| Dashboard (Übersicht, KPIs, Preisdiagramm, Wetter, Preisfenster) | sichtbar | sichtbar | sichtbar |
| Analyse (Datenpunkte, Historie, gespeicherte Ansichten) | sichtbar | sichtbar | sichtbar |
| Berichte (Vorschau, HTML/PDF/CSV-Abruf) | sichtbar | sichtbar | sichtbar |
| Technik und Status (Signale, Diagnose, letzte Läufe) | nicht in der Standardnavigation | geplant | sichtbar |
| System – Diagnose (Preisprüfung, technische Details) | nicht sichtbar | sichtbar | sichtbar |
| Standort einrichten / technische Einstellungen | nicht sichtbar | nicht sichtbar | sichtbar nach Freigabecode |

### 3.4 Aktionen je Rolle

| Aktion (heutiger Pfad) | Viewer | Operator | Admin |
| --- | --- | --- | --- |
| Daten ansehen, Zeitraum/Zeitraster wählen, Diagramme lesen | ja | ja | ja |
| Berichte erzeugen und herunterladen (HTML/PDF/CSV) | ja | ja | ja |
| Eigene Dashboard-/Analyse-Ansichten speichern (nur im eigenen Browser) | ja | ja | ja |
| Preisprüfung ausführen (`/api/diagnostics/read`, aktiver Lesezugriff auf die Anlage) | nein | ja | ja |
| Preissteuerung einstellen (Mindestdauer der Preisfenster, `POST /api/config/spotmarket-lockout`) | nein | ja | ja |
| Standortkonfiguration ändern (`config.json`, Grenzwerte, Datenpunkte) | nein | nein | ja |
| Runtime starten/stoppen, Updates, Logs und Datenbank einsehen | nein | nein | ja |
| Schreibfreigaben an der Anlage ändern (Safety-Flags) | nein | nein | ja (nur lokal/administrativ, nie über den Netzwerkzugriff) |

Begründung der beiden Grenzfälle:

- **Preisprüfung ist Operator, nicht Viewer:** Sie löst echte Lesezugriffe auf die Anlage aus und
  ist damit keine reine Anzeige – im read-only Netzwerkmodus (H5) darf dieser Endpunkt von außen
  nicht erreichbar sein.
- **Preissteuerungs-Einstellung ist Operator, nicht Admin:** Sie ändert nur das Planungsverhalten
  (Mindestdauer der Preisfenster), keine Sicherheits- oder Schreibfreigaben. Das ist eine
  betriebliche Entscheidung des Betreibers, keine Systemadministration.

### 3.5 Daten je Rolle

| Datenbereich | Viewer | Operator | Admin |
| --- | --- | --- | --- |
| Kennzahlen, Messwerte, Historie, Preise, Wetter, Preisfenster | ja | ja | ja |
| Zustands- und Qualitätsmeldungen in Betreiber-Sprache (inkl. sicherer Modus) | ja | ja | ja |
| Berichte (Tagesbericht, künftige Wochenübersicht) | ja | ja | ja |
| Technische Diagnosedetails (interne Kanal-IDs, Rohfehlermeldungen, Einzelmessungen) | nein | ja | ja |
| Konfigurationsdateien, Logdateien, Datenbankdateien, Zugangsdaten | nein | nein | ja |

### 3.6 Abgleich mit der Sicherheitslinie (ROADMAP.md)

- **H5 (geschützter Netzwerkmodus):** Viewer sehen Dashboard, Analyse und Berichte ohne aktive
  Anlagenzugriffe. Ein Admin kann denselben HTTPS-Zugang nach serverseitiger Prüfung des Freigabecodes
  für Konfigurations-Import, Vorschau und Aktivierung nutzen. Aktive Discovery, Live-Diagnose und
  betriebliche Anlagenaktionen bleiben gesperrt.
- **H6 (Login und Rollenlogik):** Dieses Rollenmodell ist die fachliche Vorlage für H6;
  persönliche Konten, Operator-Rechte und Sitzungsverwaltung bleiben dort.
- **H1/H3 (Sichtbarkeitsgrenze):** Nur Admin sieht Runtime-Dateien, Standortkonfiguration und Logs –
  passend zur Festlegung, dass normale Benutzer das UI öffnen, aber keine Systemdateien durchsuchen.
- **Schreibpfad zur Anlage:** Echte Anlagen-Schreibvorgänge und Safety-Flags bleiben außerhalb
  jeder Netzwerk-Rolle; sie sind lokaler Admin-Betrieb auf der IPC.
