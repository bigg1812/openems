# OpenEMS als Referenzsystem fuer einen service-first Einstieg

Dieses Dokument fasst OpenEMS als Lern- und Architektur-Asset fuer einen spaeteren Einstieg in `Managed Energy Ops` oder ein `MeterIQ`-aehnliches Produkt zusammen.

Die zentrale Einordnung ist:

- OpenEMS ist ein ernsthaftes Open-Source-Energiemanagementsystem.
- OpenEMS ist hilfreich, um echte Energie- und Anlagenlogik zu verstehen.
- OpenEMS ist unpassend als fruehes Startprodukt fuer einen schlanken service-first Einstieg.
- Die beste Nutzung in deiner Phase ist: `Referenzsystem`, `Denkmodell`, `Vokabular`, nicht `Produktbasis`.

## Warum dieses Repo wertvoll ist

OpenEMS zeigt in realem Code, wie ein produktionsnahes Energiesystem getrennt wird in:

- lokale Laufzeit am Standort (`Edge`)
- serverseitige Koordination fuer mehrere Standorte (`Backend`)
- Nutzeroberflaeche (`UI`)
- standardisierte Datenpunkte (`Channels`)
- Komponenten mit klarer Verantwortung (`Components`)
- zyklische Steuerlogik (`Scheduler` und `Controller`)
- historische Datenhaltung (`Timedata`)
- Rechte, Nutzer und Edge-Zuordnung (`Metadata`)

Fuer deine spaetere Firma ist das wertvoll, weil es dir ein belastbares mentales Modell fuer technische Tiefe gibt, ohne dass du diese Tiefe jetzt sofort selbst bauen musst.

## Warum OpenEMS nicht dein fruehes Startprodukt sein sollte

Fuer deinen aktuellen Zeithorizont von `6-18 Monaten` ist OpenEMS zu schwergewichtig als operative Basis.

Die Hauptgruende:

- hohe Runtime-Komplexitaet durch OSGi/Bnd und viele Module
- breite Geraete- und Herstellerlandschaft statt engem Start-Use-Case
- Fokus auf Steuerung und Systembetrieb statt auf schnelle Delivery und Reporting
- separates Edge-, Backend- und UI-Betriebsmodell
- Lizenzsplit zwischen Edge/Backend und UI

Fuer einen fruehen service-first Einstieg brauchst du eher:

- schnelle Datenerfassung
- einfache Opportunity-Analysen
- wiederholbare Reports
- Savings-Logik
- Angebots- und Delivery-Workflows

OpenEMS hilft dir dabei indirekt, aber es ist dafuer nicht die richtige unmittelbare Basis.

## Repo-Tour entlang eines einzigen Flows

Lies das Repo entlang dieses Pfads:

1. [README.md](../../../README.md)
2. [doc/modules/ROOT/pages/coreconcepts.adoc](../../modules/ROOT/pages/coreconcepts.adoc)
3. [doc/modules/ROOT/pages/gettingstarted.adoc](../../modules/ROOT/pages/gettingstarted.adoc)
4. [io.openems.edge.core/src/io/openems/edge/core/cycle/CycleWorker.java](../../../io.openems.edge.core/src/io/openems/edge/core/cycle/CycleWorker.java)
5. [io.openems.backend.core/src/io/openems/backend/core/jsonrpcrequesthandler/CoreJsonRpcRequestHandlerImpl.java](../../../io.openems.backend.core/src/io/openems/backend/core/jsonrpcrequesthandler/CoreJsonRpcRequestHandlerImpl.java)
6. [ui/README.md](../../../ui/README.md)

Wenn du nur diesen Flow verstehst, verstehst du bereits einen grossen Teil des praktischen Systems.

## Das Laufzeitmodell in einfachen Worten

### 1. Edge

`OpenEMS Edge` laeuft lokal am Standort und spricht mit realen Geraeten und Services.

Technisch heisst das:

- Komponenten repraesentieren Meter, Wechselrichter, Batterien, EV Charger, Tarife oder Controller.
- Jede Komponente hat `Channels`.
- Ein Channel ist ein standardisierter Mess- oder Zustandswert wie `meter0/ActivePower` oder `ess0/Soc`.
- Die Edge-Runtime arbeitet zyklisch.

Der relevante Codeanker ist [CycleWorker.java](../../../io.openems.edge.core/src/io/openems/edge/core/cycle/CycleWorker.java).

Die Zykluslogik ist grob:

1. neue Messwerte in die naechste Prozessabbildung uebernehmen
2. Summen und Systemzustaende aktualisieren
3. Controller in definierter Reihenfolge ausfuehren
4. Writes an Geraete ausloesen

Das Wichtigste daran ist nicht das konkrete Java-Pattern, sondern die Produktidee dahinter:

> Ein ernsthaftes Energiesystem trennt Messung, Zustand, Entscheidung und Aktion.

### 2. Backend

`OpenEMS Backend` sitzt serverseitig zwischen UI und vielen Edge-Instanzen.

Es kuemmert sich um:

- Edge-Verbindungen
- Nutzer und Berechtigungen
- Weiterleitung von Requests an einzelne Edges
- historische Datenabfragen
- aggregierte Sicht auf mehrere Standorte

Der relevante Codeanker ist [CoreJsonRpcRequestHandlerImpl.java](../../../io.openems.backend.core/src/io/openems/backend/core/jsonrpcrequesthandler/CoreJsonRpcRequestHandlerImpl.java).

In einfachen Worten:

- UI oder externe Clients schicken JSON-RPC Requests
- das Backend prueft Rechte
- das Backend beantwortet eigene Requests direkt
- oder reicht Requests an eine bestimmte Edge weiter

### 3. UI

`OpenEMS UI` ist ein Angular/Ionic-Frontend, das entweder direkt mit Edge oder ueber das Backend kommuniziert.

Fuer deinen aktuellen Zweck ist das UI vor allem relevant, um zu sehen:

- welche Sichten Nutzer wirklich brauchen
- wie Realtime und Historic Data getrennt werden
- wie stark ein richtiges EMS am Ende doch UI-, Rechte- und Betriebslogik braucht

## Die wichtigsten Abstraktionen, die du uebernehmen solltest

Nicht die volle OpenEMS-Architektur uebernehmen, sondern die folgenden Denkbausteine:

### Channel

Ein `Channel` ist die wichtigste uebernehmbare Abstraktion.

Fuer deine spaetere Firma bedeutet das:

- jeder standardisierte Messwert oder Zustand bekommt einen klaren Namen
- Werte werden nicht lose in Reports oder Prompts behandelt
- Daten werden ueber feste Adressen oder Schluessel referenziert

Beispiele fuer spaetere eigene Channels:

- `main_meter/active_power_kw`
- `site/peak_demand_kw`
- `tariff/current_energy_price_eur_per_kwh`
- `battery/state_of_charge_pct`
- `recommendation/estimated_monthly_savings_eur`

### Component

Eine `Component` ist die zweitwichtigste uebernehmbare Abstraktion.

Fuer deinen spaeteren Stack koennte das sein:

- Meter
- PV inverter
- battery
- EV charger
- tariff source
- building
- recommendation engine
- reporting pipeline

### Trennung von Verantwortungen

Das Repo ist stark, weil es sauber trennt zwischen:

- `Realtime`
- `Configuration`
- `Historical Data`
- `Permissions`
- `Recommendations/Control`

Diese Trennung solltest du frueh in deinem eigenen Daten- und Workflow-Modell beruecksichtigen, auch wenn dein erster Stack technisch viel einfacher ist.

## Konkreter Transfer in deine Firmenrichtung

Fuer `Managed Energy Ops` und ein spaeteres `MeterIQ`-aehnliches Modul ist OpenEMS besonders hilfreich in drei Punkten:

### 1. Vokabular fuer dein eigenes Datenmodell

OpenEMS zwingt zu klaren Entitaeten und Datenpunkten. Genau das brauchst du spaeter auch fuer Reports, Savings-Logik und Opportunity Discovery.

### 2. Produktintuition fuer spaetere technische Tiefe

Das Repo zeigt, wie komplex echte Steuerung, Rechte, Zustandsmodelle und historische Datenhaltung werden. Das hilft dir, kurzfristigen Delivery-Stack und langfristigen Moat sauber zu trennen.

### 3. Markt- und Integrationslandkarte

Schon die Modulstruktur zeigt, welche Kategorien in der Praxis wichtig sind:

- Meter
- Batterie
- Wechselrichter
- EV Charging
- Tarife
- Wetter
- Timedata
- APIs

Das ist eine gute Problem- und Integrationslandkarte fuer spaetere Feldarbeit.

## Was du explizit nicht uebernehmen solltest

In deiner aktuellen Phase solltest du nicht versuchen, aus OpenEMS direkt zu uebernehmen:

- OSGi/Bnd-Workspace-Struktur
- komplette Edge/Backend/UI-Laufzeit
- breite Herstellerabdeckung
- Steuerungslogik fuer reale Geraete
- volles UI als fruehes Produkt

Wenn du das doch tust, steigt die Wahrscheinlichkeit, dass du statt eines schlanken Delivery- und Reporting-Stacks versehentlich ein volles EMS zu bauen beginnst.

## Entscheidungsregel fuer die naechsten Monate

Nutze OpenEMS als Referenz, wenn du eine dieser Fragen beantworten willst:

- Wie ist ein reales EMS logisch aufgebaut?
- Welche Entitaeten und Datenpunkte sind spaeter wichtig?
- Wie sehen Realtime-, Config-, Permission- und Historic-Layer aus?
- Welche Geraete- und Steuerungskategorien sind in der Praxis relevant?

Nutze OpenEMS nicht als unmittelbare Basis, wenn du eine dieser Aufgaben loesen willst:

- ersten Reporting-Workflow bauen
- erste Opportunity-Analyse standardisieren
- einen schlanken Kundenreport erzeugen
- schnelle Delivery fuer einen engen ICP aufsetzen

## Fazit

OpenEMS ist fuer dich aktuell kein Startprodukt.

OpenEMS ist ein sehr gutes Lern- und Architektur-Asset, weil es dir zeigt, wie ein ernsthaftes Energiesystem technisch und logisch aufgebaut ist.

Der richtige strategische Einsatz ist:

- jetzt: verstehen, extrahieren, abstrahieren
- spaeter: bei Bedarf als Referenz fuer Integrations- und Steuerungstiefe wieder aufgreifen
- nicht jetzt: darauf dein erstes operatives Produkt aufbauen
