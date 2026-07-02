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

- [ ] **UX4. Betreiber-Startseite neu strukturieren**
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

## Strategische To-do-Linie: Modernes minimalistisches UI

- [ ] **UX7. Visuelle Designrichtung festlegen**
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

- [ ] **UX12. Ersten Demo-Flow für bezahlten Pilot bauen**
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
