# Mini EMS PoC

Mini EMS PoC ist ein schlanker Prototyp fuer ein lokales Energie-Management-System auf einem IPC.
Der Fokus liegt nicht auf technischer Vollstaendigkeit, sondern darauf, den MVP sofort zu verstehen:
Welche Signale kommen rein, was wird daraus entschieden, und welche Werte werden wieder nach aussen geschrieben?

## Vision

Die Idee hinter dem Projekt ist ein einfaches, robustes und nachvollziehbares Energiesystem fuer den Standort.
Es soll in kurzer Form zeigen, wie man aus Live-Daten nutzbare Betriebslogik macht:

- Spotmarktpreise holen und in lokale Entscheidungen uebersetzen
- BACnet-Werte lesen und schreiben
- Betriebszustand transparent machen
- Historie und Reports fuer Analyse und Betrieb bereitstellen

Langfristig ist das Projekt ein Baustein fuer ein spaeteres Produkt rund um Energy Ops, Monitoring und automatisierte Empfehlungen.
Der PoC beweist vor allem die Kernfrage: Kann ein kleiner lokaler Stack in Echtzeit brauchbare Energieentscheidungen treffen?

## Was der MVP kann

Aktuell macht Mini EMS PoC genau diese Dinge:

- liest `grid.active_power_kw` von `AV:300`
- liest `site.outdoor_temperature_c` von `AI:1801` am zweiten Controller
- schreibt den aktuellen Viertelstundenpreis auf `AV:1000`
- schreibt `grid_lockout` auf `BV:400`
- schreibt `spotmarket_lockout` auf `BV:401`
- speichert Zyklen, Kanalwerte, Preisfenster und BACnet-Ereignisse lokal in SQLite
- stellt einen lokalen Read-only-HTTP-API-Zugang und ein einfaches Dashboard bereit

## Wie es grob funktioniert

Der Ablauf ist bewusst simpel:

1. Preise werden aus SMARD geladen und lokal gecacht.
2. BACnet-Daten werden aus den relevanten Quellen gelesen.
3. Die Logik bewertet Grid- und Spotmarket-Situationen.
4. Sollwerte werden auf BACnet geschrieben.
5. Der komplette Lauf wird fuer Diagnose und Reporting gespeichert.

Damit ist das System klein genug fuer schnelle Iteration, aber schon real genug, um Betrieb und Logik sauber zu testen.

## Kernbausteine

- `mini_ems.py` startet den Prozess im Single-Run- oder Loop-Modus
- `config.json` enthaelt die zentrale Konfiguration
- `mini_ems_runtime/app.py` verbindet Runtime, API und Datenhaltung
- `mini_ems_runtime/bacnet.py` kuemmert sich um BACnet/IP
- `mini_ems_runtime/channels.py` definiert den Kanalraum
- `mini_ems_runtime/controllers.py` enthaelt die fachliche Schaltlogik
- `mini_ems_runtime/cycle.py` orchestriert den Zyklus
- `mini_ems_runtime/price_provider_smard.py` holt die Day-Ahead-Preise
- `mini_ems_runtime/runtime_db.py` schreibt die SQLite-Historie
- `mini_ems_runtime/http_api.py` stellt Status und Daten read-only bereit

## Projektgrenzen

Mini EMS PoC ist absichtlich kein vollwertiges EMS.
Es ist auch nicht gedacht als generische Plattform fuer beliebige Standorte.
Der Fokus liegt auf einem klaren, kleinen MVP mit nachvollziehbarer Logik und realem Betriebskontext.

Das Projekt will zeigen:

- wie ein lokaler Steuerungs-Stack im Kleinen aussieht
- wie Preis, Messwert und Aktion zusammenhaengen
- wie man Betriebslogik beobachtbar macht

Es will nicht sofort alles abdecken:

- keine breite Herstellerlandschaft
- keine komplexe Multi-Site-Architektur
- kein grosses Produkt-Frontend
- keine unnötige Abstraktion vor dem ersten echten Nutzen

## Dokumentation

- [Technische Anleitung](./MINI_EMS_ANLEITUNG.md)

Die Anleitung ist bewusst tiefer und beschreibt Architektur, Konfiguration und Betrieb im Detail.
Diese README ist der Einstieg fuer das schnelle Gesamtverstaendnis.

## Ordnerstruktur

```text
mini_ems_poc/
|-- README.md
|-- MINI_EMS_ANLEITUNG.md
|-- config.json
|-- mini_ems.py
|-- mini_ems_runtime/
|-- dashboard/
|-- data/
|-- logs/
|-- runtime/
|-- tests/
`-- windows/
```

## Wenn du nur drei Dinge verstehen willst

1. Mini EMS PoC ist ein lokaler Prototyp fuer Energie-Logik auf einem IPC.
2. Die Kernidee ist: messen, bewerten, schreiben, speichern.
3. Die Anleitung beschreibt die Technik, diese README beschreibt Zweck und Vision.
