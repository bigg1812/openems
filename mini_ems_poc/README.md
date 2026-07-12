# Mini EMS PoC

Mini EMS PoC ist ein schlanker Prototyp für ein lokales Energie-Management-System auf einem IPC.
Der Fokus liegt nicht auf technischer Vollstaendigkeit, sondern darauf, den MVP sofort zu verstehen:
Welche Signale kommen rein, was wird daraus entschieden, und welche Werte werden wieder nach aussen geschrieben?

## Vision

Die Idee hinter dem Projekt ist ein einfaches, robustes und nachvollziehbares Energiesystem für den Standort.
Es soll in kurzer Form zeigen, wie man aus Live-Daten nutzbare Betriebslogik macht:

- Spotmarktpreise holen und in lokale Entscheidungen übersetzen
- BACnet-Werte lesen und schreiben
- Betriebszustand transparent machen
- Historie und Reports für Analyse und Betrieb bereitstellen

Langfristig ist das Projekt ein Baustein für ein spaeteres Produkt rund um Energy Ops, Monitoring und automatisierte Empfehlungen.
Der PoC beweist vor allem die Kernfrage: Kann ein kleiner lokaler Stack in Echtzeit brauchbare Energieentscheidungen treffen?

## Was der MVP kann

Der Kern ist standortunabhängig; welche Geräte und BACnet-/Modbus-Punkte verwendet werden, wird über
**Konfiguration → Standort einrichten** zugeordnet. Das bisherige Pilotprofil kann unter anderem:

- liest `site.outdoor_temperature_c` von `AI:1801` am zweiten Controller
- liest ausgewaehlte reale Waerme-, Puffer- und Energiezaehlerpunkte für Reports
- schreibt den aktuellen Viertelstundenpreis auf `AV:1000`
- schreibt `spotmarket_lockout` auf `BV:401`
- speichert Zyklen, Kanalwerte, Preisfenster und BACnet-Ereignisse lokal in SQLite
- stellt einen lokalen Read-only-HTTP-API-Zugang und ein einfaches Dashboard bereit

## Laptop-Entwicklung

Konfiguration, Mapping-Entwürfe und Revisionen liegen in `site.sqlite` im gewählten Standortordner. Es gibt
keine aktive `config.json` mehr. Ein neuer Standort startet sicher in Simulation und wird anschließend über die UI
eingerichtet. Beispielwerte kommen aus `sim/sample_values.json`, Beispielpreise aus `sim/sample_prices.json`.

**Python-Version:** Mini EMS benötigt Python >= 3.10 (PEP-604-Syntax wie `X | None`). Der System-`python3`
auf macOS-Laptops ist häufig 3.9 und scheitert dann tief im Import mit einem `TypeError` statt einer klaren Meldung.
`mini_ems.py` prüft die Version deshalb selbst und bricht bei < 3.10 sofort mit einer verständlichen deutschen
Fehlermeldung ab. Nutze den exakten Interpreter: `python3.12` bzw. die Projekt-`.venv`
(`/Users/gabriel/dev/openems/.venv/bin/python`).

Start im Projektordner:

```bash
python3.12 mini_ems.py --site-dir runtime/local/site --once
python3.12 mini_ems.py --site-dir runtime/local/site --loop
```

Im lokalen Modus werden Schreibbefehle nicht an die echte Anlage gesendet. Sie werden nur als simulierte Writes bestätigt
und in Log, State, Datenbank und Dashboard sichtbar gemacht.

## Wie es grob funktioniert

Der Ablauf ist bewusst simpel:

1. Preise werden aus SMARD geladen und lokal gecacht.
2. BACnet-Daten werden aus den relevanten Quellen gelesen.
3. Die Logik bewertet Grid- und Spotmarket-Situationen.
4. Sollwerte werden auf BACnet geschrieben.
5. Der komplette Lauf wird für Diagnose und Reporting gespeichert.

Damit ist das System klein genug für schnelle Iteration, aber schon real genug, um Betrieb und Logik sauber zu testen.
Konkrete Instanzen wie AV300 oder AV48 bis AV51 gehören zum migrierten Pilotstandort und nicht mehr zu den
Produktvorgaben. Neue Standorte beginnen ohne solche Zusatzkanäle.

## Kernbausteine

- `mini_ems.py` startet den Prozess im Single-Run- oder Loop-Modus
- `mini_ems_runtime/site_store.py` speichert UI-Konfiguration, Mapping und Revisionen in `site.sqlite`
- `mini_ems_runtime/app.py` verbindet Runtime, API und Datenhaltung
- `mini_ems_runtime/bacnet.py` kuemmert sich um BACnet/IP
- `mini_ems_runtime/channels.py` definiert den Kanalraum
- `mini_ems_runtime/controllers.py` enthaelt die fachliche Schaltlogik
- `mini_ems_runtime/cycle.py` orchestriert den Zyklus
- `mini_ems_runtime/price_provider_smard.py` holt die Day-Ahead-Preise
- `mini_ems_runtime/runtime_db.py` schreibt die SQLite-Historie
- `mini_ems_runtime/http_api.py` stellt Status und Daten read-only bereit

## Projektgrenzen

Mini EMS PoC ist absichtlich kein vollwertiges Multi-Site-EMS. Der Edge-Kern ist für unterschiedliche Standorte
konfigurierbar, läuft aber jeweils als eine lokale Instanz pro Standort. Der Fokus bleibt auf einem klaren MVP mit
nachvollziehbarer Logik und realem Betriebskontext.
Innerhalb des großen OpenEMS-Repos wird `mini_ems_poc/` wie ein eigenständiges Teilprojekt geführt.
OpenEMS bleibt Referenz für professionelle Struktur, Begriffe und Muster; produktive Änderungen sollen aber eng auf Mini EMS begrenzt bleiben.

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

Diese README ist der Einstieg für das schnelle Gesamtverständnis. Für alles Weitere gilt: Der Code ist die
Wahrheit, die folgenden Dokumente vertiefen jeweils einen Teilaspekt.

| Dokument | Zweck |
| --- | --- |
| [MINI_EMS_ANLEITUNG.md](./MINI_EMS_ANLEITUNG.md) | Technische Anleitung: Architektur, Konfiguration und Betrieb im Detail. |
| [ROADMAP.md](./ROADMAP.md) | Technische Roadmap: Betriebs-, Architektur-, Sicherheits- und Deployment-Schritte. |
| [PRODUCT_UX_ROADMAP.md](./PRODUCT_UX_ROADMAP.md) | Product & UX Roadmap: Reporting, Bedienbarkeit, moderne UI-Richtung, Sprache und Demo-Fähigkeit. |
| [PRODUCT_UX_KONZEPT.md](./PRODUCT_UX_KONZEPT.md) | Ausgearbeitetes Konzept zu Reporting-Zielbild, Wording-Set und Rollenmodell (UX1/UX10/UX11). |
| [EDGE_INTEGRATION_CONTRACT.md](./EDGE_INTEGRATION_CONTRACT.md) | Verbindlicher Integrationsvertrag: gültige Messwerte, Qualität, Lese-/Schreibrechte, Ausfallverhalten. |
| [HOSTING_SICHERHEIT.md](./HOSTING_SICHERHEIT.md) | Sicherheitsgrenze und Sichtbarkeitsmatrix fürs Kundenhosting plus Minimalkonzept für erstes read-only Online-Hosting. |
| [CHANGELOG.md](./CHANGELOG.md) | Änderungen pro Release (Keep-a-Changelog, `JJJJ.MM.n`); Build übernimmt den `[Unreleased]`-Stand ins Paket. |
| [UPDATE_WARTUNG.md](./UPDATE_WARTUNG.md) | Update-, Healthcheck- und Rollback-Ablauf für die Kunden-IPC (H7), Skript-first plus manueller Fallback. |
| [packaging/README.md](./packaging/README.md) | Release-Paket bauen und ausliefern; Betriebspfad ist Standortordner mit `site.sqlite` plus Windows-Task. |
| [UI_STYLEGUIDE.md](./UI_STYLEGUIDE.md) | Verbindliche Design-Referenz: Farben, Typografie, Abstände, Komponenten-Tokens aus `dashboard.css`. |
| [PILOT_DEMO.md](./PILOT_DEMO.md) | 5-Minuten-Demoablauf für einen bezahlten Pilotkunden (UX13). |
| [EMS-Mapping.md](./EMS-Mapping.md) | Arbeitskarte, wie OpenEMS-Vorbilder Messgeräte/Protokolle auf EMS-Kanäle abbilden und wie mini_ems_poc BACnet nutzt. |
| [BACNET_STACK_EVAL.md](./BACNET_STACK_EVAL.md) | Entscheidungsvorlage S7: eigener BACnet-Adapter vs. BACpypes3 vs. BAC0 für Discovery/Import. |
| [RELEASE_WORKFLOW.md](./RELEASE_WORKFLOW.md) | Zielablauf für eine neue Mini-EMS-Installation auf einem IPC: Release-Paket bauen, Betriebsordner anlegen, Release-Task registrieren und starten. |

## Ordnerstruktur

```text
mini_ems_poc/
|-- AGENTS.md
|-- EMS-Mapping.md
|-- README.md
|-- MINI_EMS_ANLEITUNG.md
|-- ROADMAP.md
|-- PRODUCT_UX_ROADMAP.md
|-- CHANGELOG.md
|-- mini_ems.py
|-- dashboard_proxy.py
|-- run_mini_ems.cmd
|-- run_mini_ems_release.cmd
|-- mini_ems_runtime/
|-- dashboard/
|-- data/
|-- logs/
|-- runtime/
|-- sim/
|-- tests/
|-- packaging/
|-- proxy/
`-- windows/
    |-- install_task.ps1
    |-- update_release.ps1
    `-- smoketest_release.ps1
```

## Wenn du nur drei Dinge verstehen willst

1. Mini EMS PoC ist ein lokaler Prototyp für Energie-Logik auf einem IPC.
2. Die Kernidee ist: messen, bewerten, schreiben, speichern.
3. README, technische Roadmap und Product & UX Roadmap trennen Zweck, Betriebstechnik und Nutzererlebnis bewusst.
