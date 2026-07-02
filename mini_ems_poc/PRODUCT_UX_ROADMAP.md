# Mini EMS - Product & UX Roadmap

## Zweck

Diese Roadmap ergänzt die technische `ROADMAP.md`. Sie beschreibt nicht primär Adapter, Watchdogs,
Deployment oder Sicherheit, sondern die Frage, wie Mini EMS für Betreiber, Kunden und interne Nutzer
verständlich, vertrauenswürdig und angenehm bedienbar wird.

Die technische Roadmap beantwortet: Läuft das System sicher und robust?
Diese Roadmap beantwortet: Versteht der Nutzer sofort, was passiert, warum es wichtig ist und was er tun kann?

## Leitbild

Mini EMS soll sich nicht wie ein technisches Diagnosefenster anfühlen, sondern wie ein ruhiger, moderner
Energie-Leitstand für Standortbetreiber. Die Oberfläche soll wenig erklären müssen, klare Prioritäten zeigen
und Fachbegriffe nur dort verwenden, wo sie wirklich gebraucht werden.

Leitentscheidungen:

- Betreiber sehen zuerst Zustand, Relevanz und Handlungsbedarf, nicht interne Kanalnamen.
- Reports werden kundentauglich, exportierbar und optisch sauber.
- Warnungen werden in Alltagssprache erklärt.
- Das Design wird modern, minimalistisch und ruhig, ohne unnötige Dekoration.
- Technische Details bleiben erreichbar, aber nicht im Weg.
- Konfiguration fühlt sich wie "Standort einrichten" an, nicht wie technische JSON-Pflege.

## Strategische To-do-Linie: Reporting und Auswertung

- [x] **UX1. Reporting-Zielbild definieren** — erledigt, siehe `PRODUCT_UX_KONZEPT.md`, Abschnitt 1.
  - **Was:** Festlegen, welche Reports Mini EMS für einen ersten Kunden wirklich braucht: Tagesbericht,
    Wochenübersicht, Anlagenstatus, Auffälligkeiten, Einsparpotenzial und Betriebsnotizen.
  - **Nutzen:** Reporting wird nicht nur Datenexport, sondern ein sichtbarer Kundennutzen.
  - **Betroffen:** Berichte-Ansicht, PDF/HTML-Report, Tagesreport-API, spätere Templates.
  - **Aufwand:** S
  - **Risiken:** Nicht zu viele Reporttypen parallel anfangen.
  - **Definition of Done:** Es gibt eine priorisierte Liste der ersten 2-3 Reports mit Zielgruppe, Inhalt und Ausgabeformat.

- [x] **UX2. Schönere Report-Templates bauen** — erledigt, siehe `report.html.j2` und
  `runtime_db.py` (`build_report_overview`, `_render_report_html_fallback`).
  - **Was:** HTML/PDF-Templates visuell überarbeiten: klare Titelseite, Standort-/Zeitraum-Kopf, Kennzahlen,
    Diagramme, Auffälligkeiten, kurze Interpretation und technischer Anhang.
  - **Nutzen:** Reports werden präsentierbar für Kunden, Betreiber und interne Abstimmungen.
  - **Betroffen:** Report-Templates, `runtime_db.py` Report-Daten, Dashboard-Links.
  - **Aufwand:** M
  - **Risiken:** Optik darf die fachliche Nachvollziehbarkeit nicht verdecken.
  - **Definition of Done:** Ein Tagesreport kann ohne Nachbearbeitung als Kunden-PDF gezeigt werden.
  - **Umsetzung:** Tagesbericht-Kopf (Titel, Standort, Zeitraum, Erstellzeitpunkt), datengetriebene
    Hauptbotschaft, Betriebszusammenfassung mit Ampellogik, Strompreis-/Netzleistungs-Kennzahlen,
    Kommunikationshinweise und Verlaufsdiagramme (Inline-SVG, keine JS-Chart-Lib) vor einem dezent
    abgesetzten technischen Anhang; A4-`@page`-Setup mit Seitenumbruch-Regeln, System-Font-Stack ohne
    Webfonts. `render_report_html` baut die Kopfdaten read-only aus den bestehenden Tagesreport-Feldern
    (`get_daily_report`); JSON-/CSV-Endpunkte bleiben unverändert (siehe Byte-Vergleich im Abschlussbericht
    des Umsetzungs-Threads). `/api/report/html`/`/api/report/pdf` akzeptieren optional `?date=`, um ohne
    manuelle Zeitraumwahl den vollen Berichtstag zu rendern; ohne WeasyPrint liefert `/api/report/pdf`
    dieselbe kundentaugliche HTML-Ansicht als Fallback.

- [ ] **UX3. Report-Konfigurator vereinfachen**
  - **Was:** Der Nutzer kann Zeitraum, Reporttyp und optionale Bausteine einfach auswählen, ohne technische Felder
    oder interne IDs zu sehen.
  - **Nutzen:** Reports werden bedienbar, nicht nur generierbar.
  - **Betroffen:** Berichte-Ansicht im Dashboard, Report-Preview, PDF-/HTML-Download.
  - **Aufwand:** M
  - **Risiken:** Zu viele Optionen machen das Tool wieder kompliziert.
  - **Definition of Done:** Ein nicht-technischer Nutzer kann einen sinnvollen Report in weniger als einer Minute erzeugen.

## Strategische To-do-Linie: Einfachere Bedienung

- [x] **UX4. Betreiber-Startseite neu strukturieren** — erledigt: Startseite mit einer Hauptbotschaft,
  priorisierten Kennzahlen und Hinweisliste („Heute wichtig"); technische Details auf der Systemseite.
  - **Was:** Die erste Dashboard-Ansicht auf wenige Fragen zuspitzen: Läuft die Anlage? Gibt es Handlungsbedarf?
    Was ist heute wirtschaftlich oder energetisch auffällig?
  - **Nutzen:** Der Nutzer muss nicht interpretieren, sondern bekommt sofort Orientierung.
  - **Betroffen:** Dashboard-Startseite, KPI-Reihenfolge, Statusmeldung, Warnhinweise.
  - **Aufwand:** M
  - **Risiken:** Wichtige technische Details dürfen nicht verschwinden, sondern müssen in Diagnose-/Systemansichten wandern.
  - **Definition of Done:** Die Startseite zeigt maximal eine klare Hauptbotschaft, die wichtigsten Kennzahlen und konkrete Hinweise.

- [ ] **UX5. Nutzerführung für normale Bediener vereinfachen**
  - **Was:** Navigation und Begriffe so überarbeiten, dass ein Betreiber ohne Projekthintergrund versteht, was er sieht:
    Übersicht, Analyse, Berichte, Systemstatus.
  - **Nutzen:** Weniger Erklärbedarf bei Pilotkunden und weniger Risiko durch Fehlbedienung.
  - **Betroffen:** Navigation, Seitentitel, Buttontexte, leere Zustände, Hilfetexte.
  - **Aufwand:** S/M
  - **Risiken:** Keine sichtbaren internen IDs, BACnet-Begriffe oder Implementierungsdetails in normalen Nutzeransichten.
  - **Definition of Done:** Ein neuer Nutzer versteht die Hauptnavigation ohne Einweisung.

- [ ] **UX6. Zustände und Warnungen verständlich machen**
  - **Was:** Ladezustände, veraltete Daten, Kommunikationsprobleme, sichere Sperren und fehlende Werte in klarer
    Geschäftssprache anzeigen.
  - **Nutzen:** Vertrauen steigt, weil Probleme sichtbar und erklärbar werden.
  - **Betroffen:** Dashboard, Systemansicht, Quality-/Freshness-Anzeigen, Health-Status.
  - **Aufwand:** M
  - **Risiken:** Warnungen dürfen nicht dramatisieren, aber auch nicht zu harmlos wirken.
  - **Definition of Done:** Jeder kritische Zustand hat eine sichtbare, verständliche Meldung mit nächstem sinnvollen Schritt.

## Strategische To-do-Linie: Standort einrichten und Mapping

- [ ] **UX14. Konfigurationsbereich als "Standort einrichten" neu denken**
  - **Was:** Die Konfigurations-UI soll nicht mit technischen Feldern starten, sondern mit einem geführten
    Inbetriebnahmeprozess:
    ```text
    Standort
    -> Geräte
    -> Datenpunkte
    -> Testen
    -> Aktivieren
    ```
    Der Nutzer soll sofort sehen: Wie viele Schritte sind erledigt? Wie viele Datenpunkte sind gefunden,
    zugeordnet oder noch zu prüfen? Die Hauptfrage lautet nicht "Ist die JSON vollständig?", sondern
    "Ist dieser Standort bereit, sauber und sicher vom Mini EMS gelesen und geregelt zu werden?"
  - **Nutzen:** Der Kunde bekommt den gewünschten "endlich einfach und übersichtlich"-Moment. Er richtet fachlich
    einen Standort ein, statt eine technische Runtime-Struktur zu pflegen.
  - **Betroffen:** Konfigurationsnavigation, Admin-/Konfigurator-Ansicht, Mapping-Preview, Status- und
    Freigabeseite; technische Grundlage siehe `ROADMAP.md` S4/S5.
  - **Aufwand:** M/L
  - **Risiken:** Der Flow darf nicht zu spielerisch wirken. Es bleibt Inbetriebnahme an realer Anlagentechnik;
    technische Details, Schreibrechte und Safety-Grenzen müssen erreichbar und verständlich bleiben.
  - **Definition of Done:** Ein neuer Konfigurator versteht ohne Erklärung, welche Schritte bis zur Aktivierung
    fehlen; die Seite zeigt Fortschritt, offene Prüfungen und nächsten sinnvollen Schritt.

- [ ] **UX15. Fachliche Mapping-Tabelle statt technische Punktliste bauen**
  - **Was:** Die zentrale Ansicht soll fachliche Mini-EMS-Kanäle in den Vordergrund stellen. Beispiel:
    ```text
    Netzleistung              EBCON · AV 300 · 42,3 kW       geprüft
    Außentemperatur           EBCON · AI 1801 · 8,4 °C       geprüft
    Puffer 1 oben             EBCON · AI 1101 · 62,1 °C      geprüft
    BHKW elektrische Energie  EBCON · AV 48 · 18.420 kWh     prüfen
    Preissteuerung Sperre     EBCON · BV 401                 Schreibpunkt
    ```
    Pro Zeile ist die fachliche Bedeutung sichtbar. BACnet-Objekttyp, Instanz, Property, Plausibilitätsgrenzen,
    `max_age_seconds` und ähnliche Details liegen in einem einklappbaren Technikbereich.
  - **Nutzen:** Kunden und Konfiguratoren sehen zuerst, was der Punkt im EMS bedeutet. Techniker können trotzdem
    sauber nachvollziehen, welches BACnet-Objekt dahinterliegt.
  - **Betroffen:** Mapping-UI, Datenpunkt-Komponenten, technische Detailansicht, Wording.
  - **Aufwand:** M
  - **Risiken:** Fachliche Namen dürfen nicht unpräzise werden. Die technische Zuordnung muss jederzeit prüfbar sein.
  - **Definition of Done:** Eine Mapping-Zeile beantwortet auf einen Blick: Was ist der Punkt? Woher kommt er?
    Welcher Wert kommt aktuell an? Ist er geprüft?

- [ ] **UX16. "Alle Punkte testen" als zentralen Wow-Moment gestalten**
  - **Was:** Der Konfigurator soll alle Zuordnungen mit einem klaren Button prüfen können:
    ```text
    Alle Punkte testen
    ```
    Die Rückmeldung soll verständlich sein:
    - "Netzleistung: Wert kommt an und liegt im erwarteten Bereich."
    - "Außentemperatur: Wert kommt an."
    - "BHKW Energie: Wert kommt an, aber Einheit bitte prüfen."
    - "Preissteuerung: Schreibpunkt erkannt. Freigabe erforderlich."
  - **Nutzen:** Der Nutzer bekommt Vertrauen, weil die UI nicht nur `valid=true` sagt, sondern echte Inbetriebnahme-
    Aussagen liefert. Das ist der Moment, in dem Mini EMS professionell und leicht wirkt.
  - **Betroffen:** Mapping-UI, Test-/Diagnose-API, Ergebnisdarstellung, Wording, spätere Schreibpunkt-Freigabe.
  - **Aufwand:** M/L
  - **Risiken:** Testen darf bei Schreibpunkten niemals unkontrolliert schreiben. Schreibpunkte brauchen getrennte
    Freigabe, Warnung und ggf. simulierten Test.
  - **Definition of Done:** Der Nutzer kann die Mapping-Qualität ohne Rohlogs bewerten; jede Zeile zeigt Wert,
    Plausibilität, Aktualität und Freigabestatus in Alltagssprache.

## Strategische To-do-Linie: Modernes minimalistisches UI

- [x] **UX7. Visuelle Designrichtung festlegen** — erledigt, siehe `UI_STYLEGUIDE.md` (verbindliche
  Token-Referenz aus `dashboard.css`) und die überarbeitete Startseite im neuen Stil.
  - **Was:** Eine ruhige, moderne und minimalistische Designsprache definieren: Farben, Typografie, Abstände,
    Karten, Tabellen, Diagramme, Statusfarben und Interaktionszustände.
  - **Nutzen:** Mini EMS wirkt weniger wie ein Prototyp und mehr wie ein professionelles Betreiberprodukt.
  - **Betroffen:** `dashboard.css`, Dashboard-Komponenten, Report-Templates.
  - **Aufwand:** M
  - **Risiken:** Design darf nicht dekorativ werden; Scannbarkeit und Betriebssicherheit sind wichtiger als Show.
  - **Definition of Done:** Es gibt einen kleinen UI-Styleguide und eine überarbeitete Startseite im neuen Stil.

- [ ] **UX8. Diagramme und Kennzahlen lesbarer machen**
  - **Was:** Diagramme klarer beschriften, sinnvolle Einheiten zeigen, relevante Zeiträume vorauswählen und
    Ausreißer/Preisfenster verständlicher markieren.
  - **Nutzen:** Nutzer erkennen schneller, was passiert ist und warum es relevant ist.
  - **Betroffen:** Preisdiagramm, frei konfigurierbare Dashboard-Charts, Analyse-Ansicht, Reports.
  - **Aufwand:** M
  - **Risiken:** Zu viele Linien oder Farben machen die Ansicht schwer lesbar.
  - **Definition of Done:** Die wichtigsten Diagramme sind ohne technische Erklärung interpretierbar.

- [ ] **UX9. Responsive und Vor-Ort-taugliche Ansicht prüfen**
  - **Was:** UI auf Laptop, großem Monitor und Tablet prüfen; wichtige Bedienflächen, Tabellen und Diagramme
    für typische Vor-Ort-Nutzung stabil machen.
  - **Nutzen:** Mini EMS kann in der Niederlassung, im Büro und bei Inbetriebnahme sinnvoll genutzt werden.
  - **Betroffen:** Dashboard-Layout, Navigation, Tabellen, Modale, Report-Ansicht.
  - **Aufwand:** S/M
  - **Risiken:** Mobile Optimierung darf die Desktop-Bedienung nicht verschlechtern.
  - **Definition of Done:** Dashboard, Analyse und Berichte sind auf Desktop und Tablet ohne Überlappungen bedienbar.

## Strategische To-do-Linie: Produktwirkung und Vertrauen

- [x] **UX10. Kundentaugliche Sprache und Begriffe festlegen** — erledigt, siehe `PRODUCT_UX_KONZEPT.md`, Abschnitt 2.
  - **Was:** Ein kleines Wording-Set erstellen: Statusbegriffe, Warnungen, Reporttitel, KPI-Namen und Erklärtexte.
  - **Nutzen:** Die Oberfläche klingt konsistent und verständlich, nicht wie ein interner Technikmonitor.
  - **Betroffen:** Dashboard, Reports, Fehlermeldungen, README-/Pilotdoku.
  - **Aufwand:** S
  - **Risiken:** Begriffe müssen fachlich korrekt bleiben.
  - **Definition of Done:** Die wichtigsten UI-Texte sind in klarer deutscher Betreiber-Sprache formuliert.

- [x] **UX11. Rollenbasierte Ansichten vorbereiten** — erledigt, siehe `PRODUCT_UX_KONZEPT.md`, Abschnitt 3.
  - **Was:** Fachlich definieren, was Viewer, Operator und Admin jeweils sehen oder tun dürfen.
  - **Nutzen:** Die spätere Login-/Hosting-Logik bekommt ein klares Bedienmodell.
  - **Betroffen:** UI-Struktur, geschütztes Hosting, read-only Netzwerkmodus, Admin-/Systemansicht.
  - **Aufwand:** S/M
  - **Risiken:** Rollen nicht zu früh technisch überbauen; zuerst UX- und Sicherheitsgrenzen klären.
  - **Definition of Done:** Für jede Rolle ist dokumentiert, welche Seiten, Aktionen und Daten sichtbar sind.

- [ ] **UX12. Rollenbasierte Konfigurationsseite als Freigabeprozess gestalten**
  - **Was:** Eine spätere Konfigurationsseite nicht als freien JSON-Editor denken, sondern als geführten
    Entwurfs-, Prüf- und Freigabeprozess:
    - **Viewer:** sieht nur freigegebene, aktive Konfigurationszusammenfassungen, letzte Änderung, Status und
      Hinweise auf ausstehende Neustarts; keine Bearbeitung, keine Geheimnisse, keine Rohdateien.
    - **Operator:** darf betriebliche Einstellungen als Entwurf vorbereiten oder prüfen, z. B. Anzeige- und
      Planungsparameter; er speichert aber keine aktive Standortkonfiguration und ändert keine Safety-Flags.
    - **Konfigurator/Admin:** darf validierte Entwürfe freigeben und speichern, nachdem Rechte bzw. Token geprüft
      wurden; er sieht Validierungsfehler, Backup-Status, Audit-Hinweise und Neustartbedarf.
  - **Nutzen:** Konfiguration wird bedienbar und nachvollziehbar, ohne die harte Grenze zwischen Anzeige,
    Bedienung und Anlagen-/Systemadministration aufzuweichen.
  - **Betroffen:** Admin-/Systemansicht, Rollenmodell, Formularzustände, Validierungs- und Freigabetexte;
    technische API-, Backup- und Token-Regeln bleiben in `ROADMAP.md`.
  - **Aufwand:** M
  - **Risiken:** Die UI darf keine Scheinsicherheit erzeugen. Was im Netzwerk nur read-only erreichbar sein soll,
    darf dort auch nicht über eine versteckte Konfigurationsaktion möglich werden.
  - **Definition of Done:** Für jede Rolle ist klar sichtbar, ob sie nur liest, einen Entwurf vorbereitet oder eine
    geprüfte Konfiguration aktiv speichert; aktive Konfiguration, Entwurf, Validierungsfehler, Backup und
    Neustartbedarf sind fachlich unterscheidbar.

- [ ] **UX13. Ersten Demo-Flow für bezahlten Pilot bauen**
  - **Was:** Einen klaren Vorführpfad definieren: Dashboard öffnen, Zustand verstehen, Tagesreport erzeugen,
    Auffälligkeit erklären, Systemstatus prüfen.
  - **Nutzen:** Mini EMS wird leichter verkaufbar, weil der Nutzen in wenigen Minuten sichtbar wird.
  - **Betroffen:** Dashboard, Berichte, Beispielreport, Pilotunterlagen.
  - **Aufwand:** M
  - **Risiken:** Demo darf keine simulierten Versprechen machen, die der reale Standort noch nicht erfüllt.
  - **Definition of Done:** Es gibt einen 5-Minuten-Demoablauf mit echten oder realistischen Pilotdaten.

## Empfohlener nächster Schritt

**Zuerst UX1, UX4 und UX7 bearbeiten.** Damit werden Reporting-Zielbild, Betreiber-Startseite und visuelle Richtung
parallel geklärt. Danach kann UX2 als erster sichtbarer Kundennutzen umgesetzt werden: ein schönerer, präsentabler
Report, der aus echten Mini-EMS-Daten entsteht.
