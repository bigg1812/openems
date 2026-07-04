# Mini EMS - Product & UX Roadmap

## Zweck

Diese Roadmap ergänzt die technische `ROADMAP.md`. Sie beschreibt nicht primär Adapter, Watchdogs,
Deployment oder Sicherheit, sondern die Frage, wie Mini EMS für Betreiber, Kunden und interne Nutzer
verständlich, vertrauenswürdig und angenehm bedienbar wird.

Die technische Roadmap beantwortet: Läuft das System sicher und robust?
Diese Roadmap beantwortet: Versteht der Nutzer sofort, was passiert, warum es wichtig ist und was er tun kann?

Arbeitsregel für neue Architekturimpulse: Wenn technische Zukunftsthemen aus `ROADMAP.md` später eine sichtbare
Bedien-, Einrichtungs- oder Vertrauenswirkung haben, wird hier der passende UX-Punkt ergänzt. Die UI soll solche
Themen nicht als Rohtechnik ausstellen, sondern in verständliche Betreiber- und Konfiguratorabläufe übersetzen.

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

- [x] **UX5. Nutzerführung für normale Bediener vereinfachen** — erledigt: Navigation auf Betreiber-Sprache
  geschärft, leere Zustände durchgängig mit nächstem Schritt versehen, keine internen IDs/Protokollbegriffe
  in normalen Ansichten.
  - **Was:** Navigation und Begriffe so überarbeiten, dass ein Betreiber ohne Projekthintergrund versteht, was er sieht:
    Übersicht, Analyse, Berichte, Systemstatus.
  - **Nutzen:** Weniger Erklärbedarf bei Pilotkunden und weniger Risiko durch Fehlbedienung.
  - **Betroffen:** Navigation, Seitentitel, Buttontexte, leere Zustände, Hilfetexte.
  - **Aufwand:** S/M
  - **Risiken:** Keine sichtbaren internen IDs, BACnet-Begriffe oder Implementierungsdetails in normalen Nutzeransichten.
  - **Definition of Done:** Ein neuer Nutzer versteht die Hauptnavigation ohne Einweisung.
  - **Umsetzung:** Navigationslabel „Dashboard" → „Übersicht" und „System" → „Systemstatus" konsistent in
    `index.html`, `PAGES`-Mapping und `page-title` (Analyse/Berichte/Konfiguration unverändert, hoher
    Wiedererkennungswert). Startseiten-Kicker auf „Startseite" (vermeidet Dopplung mit „Übersicht"), Button und
    Modal „Dashboard anpassen" → „Ansicht anpassen"/„Übersicht anpassen". Leere Zustände mit nächstem Schritt
    nachgerüstet: Kennzahlen ohne Auswahl, Tagesbericht ohne Betriebsdaten, Wetter nicht verfügbar (ohne
    Rohfehlertext), leere Diagramme (Zeitraum erweitern), keine Läufe. Keine internen IDs, BACnet- oder
    englischen Zustandswörter in normalen Ansichten (Technikdetails bleiben in der einklappbaren
    Konfigurations-/Diagnoseansicht).

- [x] **UX6. Zustände und Warnungen verständlich machen** — erledigt: jeder kritische Zustand erscheint als
  verständliche Meldung mit nächstem Schritt; dezenter Ladehinweis beim ersten Laden und beim Aktualisieren.
  - **Was:** Ladezustände, veraltete Daten, Kommunikationsprobleme, sichere Sperren und fehlende Werte in klarer
    Geschäftssprache anzeigen.
  - **Nutzen:** Vertrauen steigt, weil Probleme sichtbar und erklärbar werden.
  - **Betroffen:** Dashboard, Systemansicht, Quality-/Freshness-Anzeigen, Health-Status.
  - **Aufwand:** M
  - **Risiken:** Warnungen dürfen nicht dramatisieren, aber auch nicht zu harmlos wirken.
  - **Definition of Done:** Jeder kritische Zustand hat eine sichtbare, verständliche Meldung mit nächstem sinnvollen Schritt.
  - **Umsetzung:** Bestehende Hauptbotschaft (`buildMainMessage`) deckt Ladeanlauf, sicherer Modus (alle Gründe),
    eingeschränkter Betrieb, stale_runtime, fehlende Werte und Verbindungsabbruch ab. Ergänzt: dezenter
    Ladehinweis (`load-indicator`, pulsierender Punkt, kein Spinner) plus „Lädt …"-Button-Zustand für Erst- und
    Folgeladung; Signalkarte „Sicherer Betriebszustand" nennt jetzt Grund und nächsten Schritt
    (`safeModeSignalText`); Signal „Preisdaten" ohne Werte mit Handlungsempfehlung statt „-"; Wetter-Ausfall und
    Verlaufsfehler in Betreiber-Sprache mit nächstem Schritt. Neue Texte im Ton des UX10-Wording-Sets formuliert
    (siehe Abschlussbericht des Umsetzungs-Threads).

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

- [ ] **UX17. Punktlisten-Import und Discovery als geführten Prüfprozess gestalten**
  - **Was:** Wenn später BACnet-Discovery, BAC0/BACpypes3, Modbus-Registerlisten oder M-Bus-/MQTT-Importe hinzukommen,
    darf die UI nicht einfach eine lange technische Rohpunktliste zeigen. Der Nutzer sieht einen geführten Ablauf:
    Quelle auswählen, Punkte importieren, Kandidaten gruppieren, fachliche Bedeutung zuordnen, Werte testen,
    Schreibpunkte separat freigeben.
  - **Nutzen:** Professionelle Protokolltiefe wird bedienbar. Discovery spart Inbetriebnahmezeit, ohne dass Nutzer
    glauben, automatisch gefundene Punkte seien automatisch richtige EMS-Kanäle.
  - **Betroffen:** Standort-einrichten-Flow, Mapping-Tabelle, Import-Preview, Test-Ergebnisse, Warntexte; technische
    Grundlage siehe `ROADMAP.md` S7/S8/S10.
  - **Aufwand:** M/L
  - **Risiken:** Discovery darf keine Scheinsicherheit erzeugen. "Gefunden" ist nicht "geprüft". Schreibpunkte müssen
    deutlich getrennt, gewarnt und aktiv freigegeben werden.
  - **Definition of Done:** Importierte Punkte erscheinen als Kandidaten mit verständlichem Status: gefunden, zugeordnet,
    geprüft, unklar, Schreibpunkt/Freigabe nötig. Kein Rohpunkt wird ohne Prüfung aktiv.

- [ ] **UX18. Cloud-/Northbound-Export verständlich und vertrauensbildend anzeigen**
  - **Was:** Wenn später ein read-only MQTT-/Cloud-Export entsteht, soll die UI klar zeigen, welche Daten wohin
    exportiert werden, ob der Export aktuell online ist, ob Werte gepuffert sind und dass keine Fernsteuerung aktiv ist.
  - **Nutzen:** Betreiber verstehen den Unterschied zwischen Monitoring-Datenexport und Anlagensteuerung. Das stärkt
    Vertrauen bei Pilotkunden und reduziert Sicherheitsbedenken.
  - **Betroffen:** Systemstatus, Rollenmodell, Export-/Hosting-Status, Wording, spätere Admin-Ansicht; technische
    Grundlage siehe `ROADMAP.md` S9/S12.
  - **Aufwand:** M
  - **Risiken:** Keine Cloud-Begriffe ohne Erklärung. Die UI darf nicht suggerieren, dass Cloud-Ausfall die lokale
    Regelung stoppt, wenn die lokale Edge weiterlaufen soll.
  - **Definition of Done:** Ein Betreiber sieht in Alltagssprache: Export aktiv/inaktiv, letzter erfolgreicher Sync,
    gepufferte Werte, freigegebene Datenklassen und klarer Hinweis "keine Fernsteuerung aktiv" bzw. spätere
    Remote-Command-Freigabe nur mit Admin-/Betreiberfreigabe.

- [ ] **UX20. Semantik- und Datenqualitätsabdeckung sichtbar machen**
  - **Was:** Wenn Mini EMS Daten in eine Cloud-/Portfolio-Pipeline exportiert, soll die UI zeigen, welche Kanäle
    fachlich geprüft sind, welche nur importiert wurden, welche Einheiten/Equipment-Zuordnung noch offen sind und
    welche Datenqualität für Reports oder Optimierung ausreicht.
  - **Nutzen:** Nutzer und Konfiguratoren verstehen, warum manche Daten sofort für Reports nutzbar sind, andere aber
    noch nicht für Regeln, ML oder Write-Back. Semantik wird damit kein unsichtbares Backend-Thema.
  - **Betroffen:** Standort-einrichten-Flow, Mapping-Tabelle, Systemstatus, spätere Portfolio-/Cloud-Ansicht;
    technische Grundlage siehe `ROADMAP.md` C1-C5 und S11.
  - **Aufwand:** M
  - **Risiken:** Keine Prozentanzeige ohne Bedeutung. "80 % gemappt" ist wertlos, wenn kritische Kanäle wie
    Netzleistung, Preis, Wärme-/Kältezähler oder Schreibfreigaben fehlen.
  - **Definition of Done:** Die UI unterscheidet klar: gefunden, semantisch vorgeschlagen, fachlich geprüft,
    exportiert, reportfähig, optimierungsfähig und schreibfähig.

- [ ] **UX22. Auto-Mapping-Vorschläge prüfbar und erklärbar machen**
  - **Was:** Wenn später NLP-/ML-gestütztes Auto-Mapping entsteht, soll die UI keine automatische Wahrheit anzeigen,
    sondern prüfbare Vorschläge: fachlicher Name, vermutete Klasse, Equipment-/Raumbezug, Konfidenz, genutzte
    Merkmale und klare Aktion "übernehmen", "ändern", "ablehnen" oder "später prüfen".
  - **Nutzen:** Konfiguratoren sparen Zeit, behalten aber Kontrolle. Ein kryptischer Punkt wie `L3_R12_VL_T` wird
    nicht blind aktiviert, sondern als verständlicher Kandidat mit Begründung und Prüfstatus behandelt.
  - **Betroffen:** Punktlisten-Import, Mapping-Tabelle, Semantikstatus, Review-Flow, Audit; technische Grundlage siehe
    `ROADMAP.md` C8/C9.
  - **Aufwand:** M/L
  - **Risiken:** Prozentwerte oder "KI sicher" erzeugen falsches Vertrauen. Schreibpunkte, sicherheitsnahe Punkte und
    abrechnungs-/nachweisrelevante Werte brauchen strengere Darstellung und dürfen nie automatisch aktiv werden.
  - **Definition of Done:** Jeder Auto-Mapping-Vorschlag zeigt Quelle, Konfidenz, Begründung und nächsten Prüfschritt.
    Aktivierte Vorschläge sind auditierbar; abgelehnte Vorschläge verbessern später Templates oder Trainingsdaten.

- [ ] **UX19. Schreibende Eingriffe und lokalen Fallback verständlich anzeigen**
  - **Was:** Sobald Mini EMS stärker schreibend eingreift, soll die UI nicht nur technische Write-Status zeigen.
    Betreiber sehen in klarer Sprache: Mini EMS greift aktuell ein / lokale Regelung führt / Fallback aktiv /
    Eingriff endet um ... / letzte Bestätigung / Freigabe erforderlich.
  - **Nutzen:** Write-Back wird vertrauenswürdig. Der Nutzer versteht, dass lokale Schutzfunktionen Vorrang haben
    und dass ein EMS-Eingriff begrenzt, bestätigt und rücknehmbar ist.
  - **Betroffen:** Startseite, Systemstatus, Admin-/Operator-Ansicht, Audit-/Ereignisliste; technische Grundlage
    siehe `ROADMAP.md` S13-S16.
  - **Aufwand:** M
  - **Risiken:** Keine Darstellung, die Sicherheit nur behauptet. Die UI muss ehrlich zwischen "bestätigt",
    "wartet auf Bestätigung", "Fallback aktiv" und "unbekannt/gestört" unterscheiden.
  - **Definition of Done:** Ein Betreiber kann ohne BACnet-Wissen erkennen, ob Mini EMS gerade einen Anlagenwert
    beeinflusst, wann der Eingriff endet, ob lokale Schutzlogik Vorrang hat und welche Aktion als nächstes sinnvoll ist.

- [ ] **UX21. Datenauflösung, Historie und Verdichtung nachvollziehbar machen**
  - **Was:** Für Reports, Diagramme und spätere Portfolio-Ansichten klar anzeigen, ob Werte als Rohdaten, 5-Minuten-/
    15-Minuten-/Stunden-Rollup oder Tageswert dargestellt werden, wie vollständig der Zeitraum ist und ob ältere
    Rohdaten bereits gelöscht oder nur noch verdichtet verfügbar sind.
  - **Nutzen:** Nutzer interpretieren historische Kurven, Einsparnachweise und Anlagenvergleiche richtig. Verdichtete
    Daten wirken nicht wie vermeintlich exakte Rohmessungen, und fehlende Datenqualität bleibt sichtbar.
  - **Betroffen:** Diagramme, Report-Templates, Portfolio-Dashboard, Exportstatus, Datenqualitätsanzeigen; technische
    Grundlage siehe `ROADMAP.md` C6/C7.
  - **Aufwand:** M
  - **Risiken:** Zu viel Datenbankvokabular überfordert Betreiber. Die UI soll nicht "TimescaleDB" oder "Downsampling"
    erklären, sondern fachlich zeigen: Auflösung, Zeitraum, Vollständigkeit, Aggregationsart und Datenqualität.
  - **Definition of Done:** Jede historische Ansicht kann anzeigen, welche Auflösung und Aggregationslogik genutzt wird
    und ob Rohdaten, Rollups oder lückenhafte Daten die Aussage begrenzen.

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

- [x] **UX13. Ersten Demo-Flow für bezahlten Pilot bauen** — erledigt, siehe `PILOT_DEMO.md`.
  - **Was:** Einen klaren Vorführpfad definieren: Dashboard öffnen, Zustand verstehen, Tagesreport erzeugen,
    Auffälligkeit erklären, Systemstatus prüfen.
  - **Nutzen:** Mini EMS wird leichter verkaufbar, weil der Nutzen in wenigen Minuten sichtbar wird.
  - **Betroffen:** Dashboard, Berichte, Beispielreport, Pilotunterlagen.
  - **Aufwand:** M
  - **Risiken:** Demo darf keine simulierten Versprechen machen, die der reale Standort noch nicht erfüllt.
  - **Definition of Done:** Es gibt einen 5-Minuten-Demoablauf mit echten oder realistischen Pilotdaten.
  - **Umsetzung:** `PILOT_DEMO.md` beschreibt Ziel/Zielgruppe, den 5-Minuten-Ablauf in 5 Schritten
    (Dashboard öffnen, Zustand verstehen, Tagesreport erzeugen, Auffälligkeit erklären, Systemstatus
    prüfen) mit Kernbotschaft je Schritt, einen Abschnitt „Ehrlichkeit und Grenzen" (keine Versprechen zu
    Schreibzugriffen, Login/Rollen, Standort-Einrichtung, PDF-Fallback), eine Troubleshooting-Liste und
    einen technischen Anhang mit Vorbereitungs-Kommandos und Prüf-URLs. Der Ablauf wurde gegen die lokal
    laufende Simulation (`config.local.json`, `/api/status`, `/api/report/html`, `/api/history`) geprüft.

## Empfohlener nächster Schritt

**Zuerst UX1, UX4 und UX7 bearbeiten.** Damit werden Reporting-Zielbild, Betreiber-Startseite und visuelle Richtung
parallel geklärt. Danach kann UX2 als erster sichtbarer Kundennutzen umgesetzt werden: ein schönerer, präsentabler
Report, der aus echten Mini-EMS-Daten entsteht.
