# Minimales Datenmodell fuer Managed Energy Ops und MeterIQ-artige Delivery

Dieses Dokument definiert ein kleines, kanonisches Datenmodell, das von OpenEMS inspiriert ist, aber bewusst deutlich einfacher bleibt.

Ziel ist nicht, ein komplettes EMS zu modellieren.
Ziel ist, spaetere Analyse-, Reporting- und Opportunity-Workflows mit stabilen Begriffen und Beziehungen zu unterlegen.

## Designprinzipien

- `service-first`: Das Modell muss Reporting und Opportunity Discovery zuerst unterstuetzen.
- `produktisierbar`: Begriffe sollen spaeter in Software ueberfuehrbar sein.
- `nicht an OpenEMS gekoppelt`: Das Modell uebernimmt Denkstrukturen, nicht die Runtime.
- `channel-first`: Standardisierte Mess- und Zustandswerte sind wichtiger als fruehe Detailtiefe.
- `read before control`: Fuer die fruehe Phase steht Analyse vor Steuerung.

## Kernentitaeten

### Site

Ein Standort, fuer den Einsparpotenziale, Reports und Massnahmen bewertet werden.

Beispielfelder:

- `site_id`
- `name`
- `customer_name`
- `country`
- `timezone`
- `industry`
- `operating_hours`
- `status`

### Building

Ein Gebaeude oder klar abgegrenzter Teil eines Standorts.

Beispielfelder:

- `building_id`
- `site_id`
- `name`
- `type`
- `gross_floor_area_m2`
- `notes`

### Asset

Ein physisches oder logisches Systemelement am Standort.

Beispiele:

- main meter
- sub meter
- PV inverter
- battery
- EV charger
- heat pump
- tariff source

Beispielfelder:

- `asset_id`
- `site_id`
- `building_id`
- `asset_type`
- `vendor`
- `model`
- `serial_number`
- `commissioned_at`
- `connectivity_status`

### Meter

Spezialisierte Asset-Sicht fuer Messpunkte.

Beispielfelder:

- `meter_id`
- `asset_id`
- `meter_role`
- `measurement_scope`
- `phase_type`
- `unit_system`

`meter_role` Beispiele:

- `grid_import_export`
- `submeter_process`
- `submeter_hvac`
- `pv_generation`
- `ev_charging`

### Channel

Ein standardisierter Mess- oder Zustandswert fuer ein Asset oder eine logische Komponente.

Beispielfelder:

- `channel_id`
- `asset_id`
- `key`
- `display_name`
- `value_type`
- `unit`
- `direction`
- `aggregation_hint`
- `quality_flag`

Beispiel-Keys:

- `active_power_kw`
- `energy_import_kwh`
- `energy_export_kwh`
- `voltage_v`
- `current_a`
- `state_of_charge_pct`
- `availability_state`
- `price_eur_per_kwh`

## Zeitreihen und Ereignisse

### TimeSeriesPoint

Ein einzelner Zeitreihenwert fuer einen Channel.

Beispielfelder:

- `site_id`
- `channel_id`
- `timestamp`
- `value`
- `quality`
- `source`

### PeakEvent

Ein identifiziertes Leistungs- oder Lastspitzenereignis.

Beispielfelder:

- `peak_event_id`
- `site_id`
- `start_ts`
- `end_ts`
- `peak_kw`
- `cost_impact_eur`
- `likely_driver`
- `confidence`

### Alert

Ein diagnostischer oder wirtschaftlich relevanter Hinweis.

Beispielfelder:

- `alert_id`
- `site_id`
- `severity`
- `category`
- `title`
- `description`
- `detected_at`
- `status`

## Analyse- und Entscheidungsentitaeten

### Recommendation

Eine priorisierte Handlungsempfehlung.

Beispielfelder:

- `recommendation_id`
- `site_id`
- `category`
- `title`
- `summary`
- `evidence`
- `expected_savings_eur_month`
- `expected_savings_kwh_month`
- `confidence`
- `implementation_effort`
- `status`

`category` Beispiele:

- `peak_shaving`
- `load_shift`
- `tariff_optimization`
- `controls_tuning`
- `metering_gap`
- `operational_change`

### Measure

Eine konkretisierte Massnahme, die aus einer Recommendation hervorgeht.

Beispielfelder:

- `measure_id`
- `recommendation_id`
- `owner`
- `planned_start_date`
- `planned_end_date`
- `implementation_cost_eur`
- `expected_payback_months`
- `state`

### SavingsEstimate

Eine strukturierte Einsparannahme fuer eine Recommendation oder Measure.

Beispielfelder:

- `savings_estimate_id`
- `reference_type`
- `reference_id`
- `period`
- `estimated_energy_savings_kwh`
- `estimated_cost_savings_eur`
- `assumptions`
- `method`

## Reporting-Entitaeten

### Report

Ein erzeugter Kundenreport oder internes Entscheidungsdokument.

Beispielfelder:

- `report_id`
- `site_id`
- `report_type`
- `reporting_period_start`
- `reporting_period_end`
- `generated_at`
- `generated_by`
- `status`

`report_type` Beispiele:

- `monthly_ops_report`
- `opportunity_scan`
- `peak_analysis`
- `pre_sales_assessment`

### ReportSection

Eine klar strukturierte Sektion innerhalb eines Reports.

Beispielfelder:

- `report_section_id`
- `report_id`
- `section_type`
- `title`
- `content_payload`
- `sort_order`

## Minimale Beziehungen

Die Kernbeziehungen fuer die erste Phase sind:

- `Site` 1:n `Building`
- `Site` 1:n `Asset`
- `Asset` 1:n `Channel`
- `Channel` 1:n `TimeSeriesPoint`
- `Site` 1:n `PeakEvent`
- `Site` 1:n `Alert`
- `Site` 1:n `Recommendation`
- `Recommendation` 1:n `Measure`
- `Recommendation` 1:n `SavingsEstimate`
- `Site` 1:n `Report`
- `Report` 1:n `ReportSection`

## Was bewusst fehlt

Dieses Modell enthaelt bewusst nicht:

- vollstaendige Geraetekonfiguration
- Steuerbefehle und Control Runtime
- Benutzer- und Rollenmodell auf Produktionsniveau
- OSGi-Komponentenlebenszyklus
- Hersteller- oder protokollspezifische Tiefe

Diese Dinge werden erst spaeter relevant, wenn du wirklich in Integrations- oder Steuerungstiefe gehst.

## Mapping von OpenEMS-Denkstruktur auf deinen Stack

Nutze OpenEMS als Referenz auf dieser Ebene:

- `OpenEMS Component` -> `Asset` oder logische Pipeline-Komponente
- `Channel` -> standardisierter Mess- oder Zustandswert
- `Timedata` -> Zeitreihen- und Historienlayer
- `Metadata` -> spaeteres Rechte- und Zuordnungsmodell
- `Controller` -> spaeteres Recommendation- oder Control-Modul
- `UI` -> spaetere Report- oder Ops-Oberflaeche

Nicht direkt uebernehmen:

- die komplette Runtime
- die Modulgranularitaet
- die Herstellerbreite

## Kernworkflows, die dieses Modell sofort tragen soll

### 1. Opportunity Discovery

Input:

- Zeitreihen aus relevanten Channels
- Asset-Inventar
- Tarifdaten

Output:

- `PeakEvent`
- `Recommendation`
- `SavingsEstimate`

### 2. Reporting and Decision Support

Input:

- Site
- TimeSeriesPoint
- Alert
- Recommendation

Output:

- `Report`
- `ReportSection`

### 3. Pre-Sales Assessment

Input:

- Basisdaten zum Standort
- vorhandene Meter und Assets
- erste Lastgangdaten

Output:

- Opportunity-Scan
- Datenluecken
- naechste Mess- oder Integrationsschritte

## Praktische Einfuehrungsregel

Wenn du unsicher bist, ob etwas in das Modell gehoert, stelle nur diese Frage:

> Hilft diese Entitaet in den naechsten 6-18 Monaten direkt bei Analyse, Reporting, Opportunity Discovery oder Savings-Kommunikation?

Wenn nein, bleibt sie vorerst draussen.

## Fazit

Dieses Modell ist absichtlich klein.

Es soll dir helfen:

- konsistent ueber Standorte, Assets und Daten zu sprechen
- wiederholbare Reporting- und Analyse-Workflows zu bauen
- OpenEMS als Referenz zu nutzen, ohne dessen Komplexitaet zu uebernehmen
- spaeter sauber in Richtung tieferer Integration oder Steuerung zu erweitern
