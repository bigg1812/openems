# Mini EMS – Architektur und Betrieb

Stand: 22.09.2026. Diese Anleitung beschreibt den lokalen Prüfkandidaten, keine bereits ausgerollte
IPC-Version. Aufgaben und Freigaben: [ROADMAP.md](ROADMAP.md). Aktuelle Nachweise:
[Validierung](docs/VALIDIERUNG_2026-09-22.md). Frühere Pilotadressen und JSON-Startpfade sind in der
Git-Historie erhalten und gelten nicht als aktuelle Betriebsanweisung.

## Architektur

```text
site.sqlite → validierte Standortkonfiguration
                   ↓
Supervisor → Anlagenzyklus → Protokolladapter → simulierte oder freigegebene Geräte
                   ↓
          Zustand + SQLite-Historie + Health
                   ↓
          lokale HTTP-API → Dashboard / Bericht

Preisabruf im Hintergrund → lokaler Preis-Cache → Anlagenzyklus
```

Der Supervisor beobachtet Fortschritt und Prozessende. Er trifft keine Regelentscheidung.
`app.py` setzt die Komponenten zusammen; `cycle.py` führt den Anlagenzyklus aus.
BACnet und Modbus bleiben hinter dem Protokollrouter. Regeln arbeiten mit Kanälen statt Geräteadressen.
`runtime_db.py` verwaltet Historie und Auswertungen; `reporting.py` rendert HTML und deutsche Beschriftungen.
Die Oberfläche besteht aus lokal ausgeliefertem HTML, CSS und JavaScript mit uPlot.
Python und SQLite bleiben Grundlage; ein zusätzlicher Datenbankserver ist nicht erforderlich.

## Standortdaten und Start

| Ort | Inhalt |
|---|---|
| `C:\Program Files\MiniEMS` | Austauschbares Windows-Programmpaket |
| `C:\ProgramData\MiniEMS\site.sqlite` | Aktive Konfiguration, Mapping-Entwürfe und Revisionen |
| `C:\ProgramData\MiniEMS\identity.sqlite` | Konten, Sitzungen, Audit, Schreibfreigaben und offene Rückgaben |
| `data/` im Standortordner | Historie, Preisdateien, optionaler Wettercache |
| `runtime/` im Standortordner | Zustand, Health und Supervisor-Nachweis |
| `logs/` im Standortordner | Laufzeit-, Supervisor- und Startprotokolle |

`site.sqlite` ist die einzige aktive Konfigurationsquelle. Die UI speichert Änderungen als neue Revision;
Laufzeitänderungen gelten nach einem geplanten Neustart. Eine vorhandene `config.json` kann beim ersten
Start migriert werden; danach ist sie ausschließlich Altbestand. Standortdaten werden nicht per Git verteilt.

Lokale Entwicklung verwendet Python ≥ 3.10, hier ausdrücklich `python3.12`, und einen eigenen Standort:

```bash
cd mini_ems_poc
python3.12 mini_ems.py --site-dir runtime/local/site --once
python3.12 mini_ems.py --site-dir runtime/local/site --supervise
```

Ein neuer Standort startet mit simulierten Geräten, Loopback-Zugriff und gesperrten realen Writes.
`--once` prüft einen Zyklus; bei erkanntem Speicherfehler endet er mit Fehlercode 1.
`--loop` bleibt der direkte Entwicklungsstart ohne externen Prozesswächter.
`--supervise` startet den überwachten Dauerbetrieb. Betriebssystem-Sperren verhindern parallele
Runtime-Prozesse für denselben Standort. Keine realen BACnet-Schreibpfade aus `environment=local`.

Für Windows sind [Release bauen und installieren](RELEASE_WORKFLOW.md) und
[Update, Rollback und Wartung](UPDATE_WARTUNG.md) maßgeblich. Der Release-Launcher verwendet `--supervise`.
Der geplante Task heißt standardmäßig `MiniEmsPoCRelease`. Der veraltete Windows-Service und der alte
Python-Dashboard-Proxy gehören nicht zum unterstützten Release-Paket.

## Beobachten und Steuern

| Betriebsart | Verhalten |
|---|---|
| `monitoring` | Messwerte und Historie erfassen; keine regulären Ausgaben, Heartbeats, Schreibtests oder Rückgaben |
| `control` | Bestehenden Regelpfad und ausdrücklich freigegebene Inbetriebnahmeaktionen ausführen |

Die Betriebsart wird unter „Standort einrichten“ eingestellt. Bestehende Standorte bleiben ohne Änderung
in `control`. Beobachtung verlangt `real_writes_enabled=false`; echte Reads sind nur für den IPC vorgesehen.
`api.read_only` ist zusätzlich eine API-Zugriffsgrenze und ersetzt die Betriebsart nicht.

**Vor einem Wechsel in Beobachtung offene Rückgaben klären.** Frühere BACnet-Prioritäten können weiter
wirken. Offene Leases bleiben in `identity.sqlite` erhalten und sichtbar. Der Beobachtungsmodus gibt sie
nicht automatisch zurück. Im freigegebenen Steuerungsbetrieb versuchen Neustart und geordnetes Beenden
nur die Rückgabe, niemals die Wiederholung eines früheren Test-Writes.

Ein bestätigtes ACK oder Relinquish belegt die Protokollantwort. Die tatsächliche Anlagenreaktion,
Prioritätskonflikte und der IPC-unabhängige DDC-Fallback benötigen eine Feldabnahme.

## Messwerte, Preise und Speicherung

Erlaubte Reads laufen bei fehlenden oder langsamen Strompreisen weiter. Der reale SMARD-Abruf läuft
außerhalb des Zyklus mit höchstens einem laufenden Abruf. Der Zyklus liest den Cache für das aktuelle
UTC-Intervall. Ohne gültigen Preis pausieren preisabhängige Ausgaben; es wird kein Preis von null erfunden.
Der bisherige Heartbeat im Steuerungsbetrieb bleibt preisunabhängig.

Messwerte enthalten Empfangszeit, letzten erfolgreichen Read, Alter und Qualität. Ausgelassene Reads
altern weiter und erzeugen keine zusätzlichen Rohmessungen. Unplausible oder fehlgeschlagene Reads
werden nicht als gültige Werte in Diagramme und Statistik aufgenommen. Ohne Controller-Quellzeit bleibt
die tatsächliche Aktualität im Gerät unbekannt. Vertragsdetails: [EDGE_INTEGRATION_CONTRACT.md](EDGE_INTEGRATION_CONTRACT.md).

Preisintervalle verwenden UTC-Schlüssel; ein deutscher Markttag hat 92, 96 oder 100 Viertelstunden.
Auch Stundenaggregate unterscheiden die doppelte Herbststunde. Tagesaggregate folgen dem Berliner Kalendertag.
Bereits vorhandene alte Aggregate werden durch diese Änderung nicht rückwirkend neu berechnet.

Speicherfehler in Zustandsdatei oder Historie werden als `storage_status=error` in Health und Oberfläche
sichtbar. Erfassung kann weiterlaufen, die betroffenen Daten fehlen aber im Nachweis. Scheitert auch die
Health-Datei, bleibt der alte Nachweis stehen und wird veraltet. Zykluskennungen enthalten eine eindeutige
Laufkennung: Ein Neustart mit fehlender Zustandsdatei überschreibt keine früheren Zyklen.

## Prozessüberwachung und Alarmzustände

Der Supervisor nutzt ausschließlich frische Health-Daten mit passender Laufkennung und fortschreitender
Zykluskennung. Alte Dateien eines früheren Prozesses gelten nicht als neuer Fortschritt.

- Maximal drei Startversuche einschließlich Erststart innerhalb von 15 Minuten; vor jedem Start dauerhaft erfasst.
- Bei Absturz oder fehlendem Fortschritt: geordnetes Stoppsignal, nötigenfalls Beendigung, begrenzter Neustart.
- Ein fortschreitender Zyklus mit Preis-, Geräte- oder Speicherstörung wird nicht allein deshalb neu gestartet.
- Nach ausgeschöpftem Budget: `restart_blocked`, Fehlercode 3. Ursache prüfen; kein Löschen des Nachweises als Standardmaßnahme.
- `runtime/supervisor.json` und `logs/supervisor.log` liefern den unabhängigen lokalen Nachweis.
- Ein verlorener Supervisor bei weiterlaufender Runtime wird in API und Dashboard als Störung sichtbar.

`watchdog.max_cycle_age_seconds` muss endlich und größer als die Zykluspause sein. Es muss zusätzlich
langsame erlaubte Reads, Timeouts und Retries abdecken. Ohne Konfiguration gelten 300 Sekunden; die
Anlaufzeit beträgt mindestens 30 Sekunden. Vor Ort sind diese Zeiten gegen die DDC-Reaktion abzugleichen.
Der Windows-Task erhält ebenfalls begrenzte Neustarts; das Update registriert bestehende Task-Einstellungen neu.

`/api/health` bewertet den gespeicherten Nachweis bei jedem Aufruf: `stale_runtime` bei Überschreitung,
`unknown` bei fehlendem, ungültigem oder zukünftigem Zeitpunkt. HTTP 200 allein bedeutet keine fehlerfreie Anlage.
Ein externer Benachrichtigungsdienst ist nicht Bestandteil dieses Pakets. Bei ausgeschaltetem IPC braucht
es einen außerhalb des IPC liegenden Alarmweg; dessen Anbindung gehört zur Standortabnahme.

## Bedienung und Rollen

Die Übersicht zeigt eine Hauptaussage, ausgewählte Kennzahlen und relevante Hinweise. Strompreise und
Planung sowie weitere Anzeigen sind zunächst eingeklappt. Die Analyse bietet vorhandene Messreihen an;
unbenutzte Pilotkanäle werden nicht als zusätzliche Auswahl dargestellt.

Viewer sehen Betrieb, Analyse und Berichte. Admins erhalten Standortkonfiguration, Kontenverwaltung und
freigegebene technische Funktionen. Ausgeblendete Bedienelemente ersetzen keine API-Rechteprüfung.
Die API bindet am IPC auf Loopback; für den geschützten Zugang gilt [HOSTING_SICHERHEIT.md](HOSTING_SICHERHEIT.md).

Das Paket verwendet den eingebauten HTML-Bericht. Zum PDF-Export die Druckfunktion des Browsers verwenden.
Jinja-Vorlagen, serverseitiges WeasyPrint-PDF und BACpypes3-Discovery sind optionale Quellcode-Erweiterungen
und nicht Teil des schlanken Prüfprofils. BACnet- und Modbus-Laufzeitadapter bleiben enthalten.

Wetter ist optional. Ohne Breiten-/Längengrad gibt es keinen externen Abruf. Ein Admin kann die Koordinaten
unter „Standort und Zugriff → Wetterstandort“ speichern; sie werden an Open-Meteo übermittelt. Der Cache
liegt ausschließlich im Standortordner und wird bei geänderter Ortszuordnung nicht wiederverwendet.
Die Wetterabfrage läuft unabhängig vom Laden des Betriebszustands und erst bei Bedarf.

## Aufbewahrung und nächster Nachweis

Laufzeit- und Supervisor-Log rotieren jeweils bei 5 MiB mit drei Sicherungen: ungefähr 20 MiB je Logfamilie.
Das Startprotokoll enthält nur Start-/Abbruchmeldungen und gegebenenfalls den Einrichtungs-Code; nach
Einrichtung gemäß Standortverfahren sichern und bereinigen. Zugriff auf den Standortordner bleibt geschützt.

Die Historie wird nicht automatisch gelöscht. Der lokale Lasttest mit zehn Messpunkten und 30-Sekunden-Raster
ergab etwa 137 MiB pro simulierter Woche. Das ist eine Messung dieses Profils, keine allgemeine Speicherzusage.
Für den ersten begrenzten Standortlauf Speicherbudget und Endzeit vorher festlegen, vor/nach dem Lauf
freien Platz prüfen und die komplette ruhende Standortkopie sichern. Dauerhafte Aufbewahrungsfristen und
Archivierung sind vor unbeaufsichtigtem Langzeitbetrieb zu entscheiden.

Als Nächstes: Windows-Paket auf einem getrennten Simulationsstandort prüfen, installierten IPC-Stand und
Zugriff aufnehmen, dann einen freigegebenen Beobachtungslauf durchführen. Schreibtests und DDC-Ausfalltests
bleiben separate, ausdrücklich vereinbarte Prüfungen. Der vollständige Ablauf steht in der Roadmap.
