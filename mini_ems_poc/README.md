# Mini EMS PoC

Mini EMS PoC ist ein kleiner lokaler Energy-Edge-Stack für einen IPC. Er verbindet
Messwerte, Strompreise, einfache Betriebslogik, Historie und Dashboard in einem
überschaubaren System.

Der Einstiegspunkt ist bewusst standortunabhängig: Ein reales Projekt bekommt seine
Punkte, Geräte und Freigaben über die Inbetriebnahme-UI. Alte Pilot-Objekte aus
frühen Tests sind nicht mehr die Definition des Produkts.

## Was Mini EMS macht

Mini EMS übernimmt im Kern diese Aufgaben:

- Energie- und Anlagenwerte über Protokolladapter lesen, aktuell vor allem BACnet.
- Day-Ahead-Spotmarktpreise von SMARD laden und lokal cachen.
- einfache Steuerlogik aus Messwerten, Preisfenstern und Sicherheitsregeln ableiten.
- freigegebene Ausgänge schreiben, bestätigen und im Fehlerfall sichtbar machen.
- Zyklen, Kanalwerte, Preise, Betriebsereignisse und Reports lokal in SQLite speichern.
- Dashboard, Status-API, Reports, Diagnose und Konfigurationsansichten bereitstellen.

Das Ziel ist kein schweres Voll-EMS, sondern ein nachvollziehbarer lokaler Stack:
messen, bewerten, handeln, speichern und erklären.

## Aktueller Betriebsweg

Der produktive Betrieb läuft über ein versioniertes Release-Paket, nicht über einen
laufenden Git-Checkout.

```text
C:\Program Files\MiniEMS\      App-Dateien aus dem Release-Paket
C:\ProgramData\MiniEMS\        Standortdaten, Konfiguration, Logs, Runtime, Datenbank
```

Die App wird als One-Dir-Paket gebaut und enthält unter anderem:

- `mini_ems.exe`
- `run_mini_ems_release.cmd`
- `dashboard/`
- `mini_ems_runtime/templates/`
- `VERSION`
- `SHA256SUMS`
- `CHANGELOG.md`

Gestartet wird sie über den geplanten Windows-Task `MiniEmsPoCRelease`. In der
gehärteten Zielvariante läuft die API nur intern auf `127.0.0.1:8090`; Zugriff aus
Kundennetz, VPN oder Secomea läuft über den Caddy-Proxy.

Wichtig: Änderungen im Repo unter `C:\dev\openems\mini_ems_poc` aktualisieren die
installierte IPC-Version nicht automatisch. Ein Update bedeutet immer: testen, neues
Release-Paket bauen, Paket einspielen, Healthcheck ausführen.

## Konfiguration und Mapping

Die normale Inbetriebnahme läuft nicht mehr über manuelles Bearbeiten einer
Punktliste in `config.json`.

Der gewünschte Weg ist:

```text
Standort -> Geräte -> Datenpunkte -> Testen -> Abschließen
```

Die UI importiert eine Datenpunktliste oder später eine read-only Discovery, erzeugt
daraus einen Mapping-Entwurf, validiert ihn und übernimmt ihn erst nach Freigabe.
Vor der Übernahme werden Backup, gespeicherter Entwurf und Audit-Eintrag angelegt.

`config.json` bleibt trotzdem wichtig: Es ist die aktive Runtime-Konfiguration der
Installation. Für den ersten Start braucht Mini EMS eine gültige Startkonfiguration,
weil die UI erst erreichbar ist, wenn die Runtime läuft. Danach soll die laufende
Konfiguration über die UI und den Freigabecode gepflegt werden, nicht per
Alltags-Handedit.

Für lokale Entwicklung gibt es `config.local.json`. Sie nutzt Simulation und darf
keine echten BACnet-Writes senden.

## Lokale Entwicklung

Mini EMS benötigt Python >= 3.10. Auf dieser Maschine sollte für Mini EMS die
Projekt-`.venv` oder ein explizites Python 3.12 verwendet werden.

Ein sicherer lokaler Einzelzyklus:

```powershell
cd C:\dev\openems\mini_ems_poc
.\.venv\Scripts\python.exe mini_ems.py --config config.local.json --once
```

Lokaler Loop mit Dashboard/API:

```powershell
cd C:\dev\openems\mini_ems_poc
.\.venv\Scripts\python.exe mini_ems.py --config config.local.json --loop
```

Die lokale API läuft mit `config.local.json` auf:

```text
http://127.0.0.1:8090
```

Im lokalen Modus gilt:

- `environment=local`
- `runtime.bacnet_mode=simulated`
- `runtime.real_writes_enabled=false`
- Eingänge kommen aus `sim/sample_values.json`.
- Beispielpreise kommen aus `sim/sample_prices.json`.
- Daten, Logs und Health-Dateien landen in lokalen Unterordnern.

## Release bauen und aktualisieren

Release-Build und Update sind getrennte Schritte.

Build auf Windows:

```powershell
cd C:\dev\openems\mini_ems_poc
.\.venv\Scripts\python.exe -m pip install pyinstaller
powershell -ExecutionPolicy Bypass -File packaging\build_release.ps1 -Version 2026.07.1 -Python C:\dev\openems\mini_ems_poc\.venv\Scripts\python.exe
```

Das Paket entsteht unter:

```text
mini_ems_poc\packaging\dist\mini_ems
```

Ein bestehender IPC-Stand wird bevorzugt per Skript aktualisiert:

```powershell
cd C:\dev\openems\mini_ems_poc
.\windows\update_release.ps1 -PackagePath <Ordner-des-neuen-Release-Pakets>
```

Das Update-Skript ersetzt die App-Dateien und lässt Standortdaten wie `config.json`,
SQLite-Datenbank, Logs, Runtime-Dateien, Mapping-Entwürfe und Audit-Log unangetastet.
Rollback läuft über:

```powershell
.\windows\update_release.ps1 -Rollback
```

## Wichtige Dateien und Ordner

| Pfad | Bedeutung |
| --- | --- |
| `mini_ems.py` | CLI-Einstieg für Einzelzyklus und Loop im Checkout-Betrieb. |
| `mini_ems_runtime/` | Runtime-Code für Config, Adapter, Zyklus, API, Persistenz und Reports. |
| `dashboard/` | Browser-UI für Dashboard, Einrichtung, Diagnose und Systemstatus. |
| `config.local.json` | Sichere lokale Simulationskonfiguration. |
| `config.json` | Beispiel bzw. IPC-Startkonfiguration; im produktiven Betrieb liegt die aktive Datei unter `C:\ProgramData\MiniEMS`. |
| `sim/` | Beispielwerte und Beispielpreise für lokale Simulation. |
| `tests/` | Python-`unittest`-Tests. |
| `packaging/` | Build-Tooling für versionierte Release-Pakete. |
| `windows/` | Windows-Task, Update- und Smoketest-Skripte. |
| `proxy/` | Caddy-Reverse-Proxy-Konzept für gehärteten Netzwerkzugriff. |

## Dokumentation

| Dokument | Zweck |
| --- | --- |
| [MINI_EMS_ANLEITUNG.md](./MINI_EMS_ANLEITUNG.md) | Technische Anleitung zu Architektur, Runtime, API, UI-Konfiguration und Betrieb. |
| [RELEASE_WORKFLOW.md](./RELEASE_WORKFLOW.md) | Erstinstallation auf einem neuen IPC: Paket bauen, Ordner anlegen, Task registrieren, starten. |
| [UPDATE_WARTUNG.md](./UPDATE_WARTUNG.md) | Update, Healthcheck, Rollback, Wartungsroutine und Versionierung. |
| [packaging/README.md](./packaging/README.md) | Release-Paket bauen, Layout, `VERSION`, `SHA256SUMS`, späterer Nuitka-Pfad. |
| [HOSTING_SICHERHEIT.md](./HOSTING_SICHERHEIT.md) | Sicherheitsgrenze, Rollen, Netzwerkzugriff, Program-Files/ProgramData-Trennung und Proxy. |
| [EMS-Mapping.md](./EMS-Mapping.md) | Protokoll- und Kanal-Mapping, OpenEMS-Vorbilder, Mapping-Vorlagen und Freigabeweg. |
| [EDGE_INTEGRATION_CONTRACT.md](./EDGE_INTEGRATION_CONTRACT.md) | Verbindlicher Integrationsvertrag für Messwertqualität, Rechte, Ausfallverhalten und Mapping. |
| [ROADMAP.md](./ROADMAP.md) | Technische Roadmap für Architektur, Betrieb, Sicherheit und Plattformausbau. |
| [PRODUCT_UX_ROADMAP.md](./PRODUCT_UX_ROADMAP.md) | Product- und UX-Roadmap für Bedienbarkeit, Reporting, Rollen und Demo-Reife. |
| [PRODUCT_UX_KONZEPT.md](./PRODUCT_UX_KONZEPT.md) | Produktkonzept zu Reporting, Wording und Rollenmodell. |
| [UI_STYLEGUIDE.md](./UI_STYLEGUIDE.md) | UI-Designreferenz für Farben, Typografie, Abstände und Komponenten. |
| [PILOT_DEMO.md](./PILOT_DEMO.md) | Kurzer Demoablauf für Pilotkunden. |
| [CHANGELOG.md](./CHANGELOG.md) | Änderungen pro Release; der Build übernimmt den Release-Schnappschuss ins Paket. |
| [BACNET_STACK_EVAL.md](./BACNET_STACK_EVAL.md) | Entscheidungsvorlage für BACnet-Discovery und Import-Werkzeuge. |

## Wenn du nur drei Dinge behalten willst

1. Mini EMS läuft produktiv als Release-Paket auf dem IPC, nicht als Git-Checkout.
2. Standort-Mapping wird über UI, Entwurf, Test und Freigabe gepflegt; `config.json` ist Runtime- und Bootstrap-Datei, nicht die normale Bedienoberfläche.
3. App-Dateien und Standortdaten bleiben strikt getrennt, damit Updates die Anlage nicht versehentlich überschreiben.
