# Mini EMS Plattform-Zielbild: Operational Context Layer

**Status:** Strategische Leitplanke, kein unmittelbarer Implementierungsauftrag  
**Stand:** 2026-07-12

## Entscheidung in einem Satz

Mini EMS startet mit Energiemanagement als erstem realen Anwendungsfall, entwickelt seinen Kern aber als
anpassbare Edge-to-Cloud-Plattform: Operative Ereignisse aus Branchensoftware und technische Gebäudedaten werden
in sichere, lokal begrenzte Betriebsentscheidungen und messbare Ergebnisse übersetzt.

Der Kern soll deshalb nicht dauerhaft von Begriffen wie Strompreis, BHKW oder Kessel abhängen. Solche Begriffe
gehören in ein Energie-Vertikalpaket. Standort, Asset, Kanal, Ereignis, Kontext, Regel, Aktion, Qualität und Audit
bilden den wiederverwendbaren Plattformkern.

## Produktthese

Die Plattform verbindet zwei bisher oft getrennte Welten:

```text
Branchensoftware und operative Planung
-> Operational Context
-> Bedarfsübersetzung und Policy
-> sichere Edge-Ausführung
-> Gebäudeautomation und technische Anlagen
-> Nachweis von Wirkung und Betriebsqualität
```

Beispiele für operative Zukunftsdaten sind Buchungen, Belegung, Touren, LKW-Ankünfte, Abfahrtszeiten,
Produktionschargen, Wetterprognosen oder Wachstumsphasen. Ihr Wert entsteht erst, wenn sie mit Standort, Zeit,
Asset, Priorität und Betriebsgrenze verbunden werden.

Mini EMS ersetzt dabei keine DDC, SPS, lokale Sicherheitskette oder schnelle Regelung. Die Plattform liefert
Betriebsmodi, Zeitfenster, Sollwertkorridore, Leistungsgrenzen, Empfehlungen oder freigegebene Aktionen. Die
lokale Automation bleibt für Safety, Verriegelungen und schnelle Regelkreise führend.

## Warum Energie der erste Einstieg bleibt

Energiemanagement ist der richtige erste Vertikalpfad, weil bereits reale Anlagenkommunikation, Zeitreihen,
Qualitätsbewertung, Simulation, Reporting, sichere BACnet-Schreibpfade und ein Pilot-IPC vorhanden sind. Damit
lässt sich der Plattformkern an einem echten Problem beweisen.

Der erste Markteintritt soll trotzdem nicht als generisches „EMS für alle“ erfolgen. Die Produktdisziplin lautet:

```text
1 Branchensystem
+ 1 Gebäudetyp
+ 1 technischer Use Case
+ 1 messbarer KPI
+ 3 bis 5 vergleichbare Pilotstandorte
```

Erst wiederholbare Vertikalen rechtfertigen eine breitere Plattformpositionierung.

## Schichten der Zielarchitektur

| Schicht | Verantwortung | Beispiele |
| --- | --- | --- |
| Vertikalpaket | Sprache, Prozesse, Templates und KPIs einer Nische | Energie, Depot, Hotel, Food/Filiale, Gewächshaus |
| Operational Context | Operative Ereignisse mit Ort, Zeit, Ressource, Deadline und Priorität verbinden | Buchung, Tour, Ankunft, Charge, Wachstumsphase |
| Policy und Bedarfsübersetzung | Kontext in Demand, Grenzen, Empfehlungen oder freigegebene Betriebsmodi übersetzen | Ladebedarf, Vorkonditionierung, Temperaturkorridor |
| Edge Runtime | Offline-Betrieb, Mapping, Datenqualität, lokale Regeln, Simulation, Audit und Safe Write | Mini-EMS-Runtime auf IPC/Gateway |
| Southbound Adapter | Technische Anlagen und Sensorquellen anbinden | BACnet, Modbus, M-Bus, MQTT, HTTP |
| Northbound Cloud | Flottenbetrieb, Benutzer, APIs, Zeitreihen, Events, Analyse und Rollout | Outbox, Broker/API, Mandanten, Portfolio |

### Kleines kanonisches Kernmodell

| Entität | Zweck |
| --- | --- |
| `Site` | Standort, Zeitzone, Betriebsumgebung und Mandant |
| `Location` | Gebäude, Bereich, Raum, Zone oder Außenfläche |
| `Asset` | Technische oder operative Ressource, z. B. RLT, Ladesäule, Kühlraum, Gewächshauszone |
| `Channel` | Kanonischer Mess-, Status- oder Schreibpunkt mit Einheit, Qualität und Quelle |
| `Event` | Beobachtetes oder geplantes Ereignis mit Zeit und Herkunft |
| `Context` | Fachliche Einordnung eines Events für Standort, Asset und Prozess |
| `Demand` | Abgeleiteter technischer Bedarf mit Deadline, Priorität und Unsicherheit |
| `Policy` | Zulässige Reaktion, Grenzen, Fallback und Zielkonflikte |
| `Action` | Empfehlung oder freigegebener Edge-Befehl mit Laufzeit und Ablaufzeit |
| `Evidence` | Messbarer Nachweis, Audit, Ergebnis und Abweichung |

Externe Ontologien wie Haystack, Brick oder RealEstateCore bleiben zunächst Export- und Integrationsziele. Der
Edge-Kern verwendet ein kleines eigenes Modell, das später verlustarm projiziert werden kann.

## Protokollstrategie

| Protokoll/Quelle | Rolle in der Plattform | Leitplanke |
| --- | --- | --- |
| BACnet | Gebäudeautomation lesen und kontrolliert schreiben | Prioritäten, Readback, lokale Verriegelungen und Betreiberfreigabe |
| Modbus | Geräte, Zähler und technische Anlagen anbinden | zunächst read-only; Datentyp, Endianness und Skalierung explizit |
| M-Bus/wM-Bus | Langsame Energie-, Wärme-, Wasser- und Gaszähler | Monitoring und Bilanzierung, nicht schnelle Regelung |
| MQTT | Sensor-/Gateway-Ingress und später Northbound-Export | Topic- und Payload-Vertrag versionieren; Broker ist nicht die Semantik |
| HTTP/REST/Webhooks | Branchensoftware, Wetter, Buchung, TMS, PMS, MES und Partner-APIs | Authentifizierung, Rate Limits, Schema und Idempotenz |
| LoRaWAN | Sparse Telemetrie über externen Network/Application Server | Mini EMS wird kein LoRaWAN Network Server; Ingress per MQTT/HTTP |

Protokolladapter liefern Rohwerte und technische Metadaten. Erst Mapping und Kontext machen daraus fachlich
nutzbare Kanäle. Kein Adapter darf durch Discovery automatisch aktive Schreibpunkte erzeugen.

## Simulation als Plattformfunktion

Simulation soll nicht nur ein Entwickler-Mock bleiben, sondern ein wiederholbarer Produktbestandteil werden.
Vier Ebenen sind sinnvoll:

1. **Protokollsimulation:** BACnet-, Modbus-, M-Bus-, MQTT- und HTTP-Quellen reproduzierbar nachbilden.
2. **Anlagenszenarien:** normale Werte, Kommunikationsausfall, Stale Data, Grenzwertverletzung und Write-Failure.
3. **Vertikalszenarien:** operative Ereignisse und erwartete Gebäudereaktion gemeinsam abspielen.
4. **Policy-Vergleich:** Baseline und neue Regel mit Energie-, Komfort-, Prozess- und Sicherheits-KPIs vergleichen.

Ein Szenario besteht mindestens aus Eingangsereignissen, Anlagenwerten, erwarteter Entscheidung, erlaubten
Aktionen und Assertions. Ein vollständiger physikalischer Digital Twin ist dafür nicht immer nötig. Für sensible
Vertikalen wie Gewächshaus, Reinraum oder Kühlkette kann später ein genaueres Domänenmodell ergänzt werden.

Beispielszenarien:

| Vertikale | Operativer Kontext | Sichere Reaktion | Nachweis |
| --- | --- | --- | --- |
| Energie | Preis, Last, Wetter, Anlagenzustand | Speicher-/Sperrmodus oder Empfehlung | Kosten, Peak, Übergabequalität |
| Logistikdepot | LKW-Ankunft, Abfahrt, Fahrzeug-SOC, Priorität | Ladefenster und Leistungsgrenze vorbereiten | Fahrbereitschaft, Peak, manuelle Eingriffe |
| Hotel | Buchung, Check-in/-out, Zimmerstatus | Vorkonditionierung und Setback-Modus | Komfort, Laufzeit, Beschwerden |
| Gewächshaus | Wachstumsphase, Wetter, Licht, Feuchte, CO2 | Sollwertkorridor und Betriebsplan vorschlagen | Ertrag/Qualität, Energie, Grenzverletzungen |
| Food/Filiale | Anlieferung, Öffnungszeit, Kühlraumstatus, Produktion | Alarm, Vorkühlung oder Peak-Empfehlung | Kühlkette, Warenrisiko, Energie |

## Authentifizierung und Identitäten

Cloud- und Benutzeridentitäten müssen getrennt betrachtet werden:

| Identität | Mindestanforderung |
| --- | --- |
| Edge-Gerät | eindeutige Device-ID, Zertifikat oder vergleichbare starke Identität, Rotation und Sperrbarkeit |
| Benutzer | Login, Mandantenzuordnung, Session-Schutz und nachvollziehbare Rollen |
| Dienst/API | eigener Client, begrenzte Scopes, rotierbares Secret oder Zertifikat |
| Remote-Aktion | Autor, Rolle, Ziel, Payload, Ablaufzeit, Idempotenzschlüssel, Policy-Prüfung und Audit |

Erste Rollen bleiben überschaubar: `Viewer`, `Operator`, `Configurator` und `Admin`. Eine Cloud-Verbindung ist
niemals automatisch eine Schreibfreigabe. Read-only Export und Remote-Commands bleiben getrennte Produktebenen.

## Sicherheitsvertrag

Diese Regeln gelten für jede Vertikale:

- Lokale Safety und schnelle Regelung bleiben unabhängig von Cloud und Internet.
- Lesen kommt vor Schreiben; Empfehlungen kommen vor automatisierten Aktionen.
- Cloud schreibt keine rohen Ventilstellungen, Pumpendrehzahlen oder unbefristeten Sollwerte.
- Jede Aktion besitzt Ziel, Wertebereich, Priorität, Gültigkeitsdauer, Fallback und Bestätigung.
- Kommunikationsausfall darf den lokalen Betrieb nicht stoppen.
- Mapping, Policy und Aktionen sind versioniert und auditierbar.
- Simulation und Test dürfen niemals einen Pfad zu realen Anlagenwrites öffnen.
- Personen- und Betriebsdaten werden minimiert; Mandanten und Standorte bleiben logisch getrennt.

## Auswahl einer profitablen Nische

Die Plattformidee allein ist kein Markt. Jede Vertikale wird vor Umsetzung nach denselben Fragen bewertet:

| Kriterium | Leitfrage |
| --- | --- |
| Operativer Schmerz | Welcher teure oder häufige Fehler wird verhindert? |
| Zukunftsdaten | Welche Information ist früher verfügbar als die physikalische Reaktion? |
| Technischer Hebel | Welche sichere Gebäude-/Anlagenreaktion folgt daraus? |
| Datenzugang | Gibt es API, Export oder wiederholbaren Connector? |
| Wiederholbarkeit | Sind Anlagen und Prozesse über mehrere Standorte ähnlich? |
| Nachweis | Welcher KPI zeigt innerhalb weniger Wochen einen Wert? |
| Käufer | Wer besitzt Budget und Verantwortung für das Problem? |
| Risiko | Welche Safety-, Komfort-, Hygiene- oder Prozessgrenze ist tabu? |

Die LLM-Wiki priorisiert aktuell Fitness/Wellness und Bäckerei/Food Production als gut startbare Vertikalen.
Depots besitzen einen großen Energie- und Prozesshebel, sind aber integrations- und vertriebsseitig komplexer.
Hotel ist technisch plausibel, jedoch bereits stärker besetzt. Landwirtschaft und Gewächshaus sind fachlich
interessant, bilden aber einen eigenen Käufer- und Produktmarkt und dürfen den ersten Pilot nicht verwässern.

## OpenEMS-Audit vor der Repository-Trennung

Vor der Isolierung von Mini EMS wird OpenEMS einmal systematisch als Referenzarchitektur untersucht. Nicht jede
Datei wird gleich tief gelesen. Der Audit folgt den fachlichen Verantwortungen und endet pro Thema mit
`übernehmen`, `vereinfacht adaptieren`, `später` oder `nicht übernehmen`.

| Auditfeld | Zu untersuchende Idee | Ergebnisartefakt |
| --- | --- | --- |
| Edge-Komponenten und Channels | Lifecycle, Nature/Interfaces, Channel-Metadaten und Fehlerzustände | Vergleich mit `Asset`/`Channel`-Kernmodell |
| Scheduler und Controller | Reihenfolge, Prioritäten, Abhängigkeiten, Konflikte und deterministische Zyklen | kleine Policy-/Controller-Verträge |
| Protokoll-Bridges | BACnet, Modbus, M-Bus und MQTT; Reconnect, Timeouts und Mapping | Adapter-Entscheidung je Protokoll |
| Simulation und Tests | Dummy-Komponenten, Simulatoren, Testhilfen und Szenarien | Simulations-Roadmap und Szenarioformat |
| Edge-Backend-Kommunikation | Verbindung, Offline-Verhalten, Queueing, JSON-RPC und Events | S9/C1-Outbox- und Payload-Vertrag |
| Benutzer und Rollen | Authentifizierung, Autorisierung, Mandanten- und Zugriffsmuster | H6-/Cloud-Identity-Entscheidung |
| Zeitreihen und Persistenz | Edge-Timedata, Backend-Timedata, Aggregation und Retention | Speicher- und Replay-Entscheidung |
| Betrieb und Sicherheit | Config-Lifecycle, Health, Audit, Updates und Fehlerdiagnose | Hardening- und Betriebs-Checkliste |

OpenEMS wird als Referenz genutzt, nicht als Blaupause. OSGi-, Java- und Enterprise-Komplexität wird nur
übernommen, wenn sie ein konkretes Mini-EMS-Problem löst. Vor jeder tatsächlichen Codeübernahme werden Herkunft,
Lizenz und notwendige Hinweise dokumentiert.

## Tor vor der Repository-Isolierung

Mini EMS wird erst aus dem großen OpenEMS-Repository gelöst, wenn:

1. Release `2026.07.1` auf der Pilot-IPC installiert und abgenommen ist.
2. Der OpenEMS-Architektur-Audit abgeschlossen und als Entscheidungsmatrix dokumentiert ist.
3. Abhängigkeiten auf Dateien außerhalb `mini_ems_poc/` entfernt oder bewusst übernommen sind.
4. Lizenz- und Herkunftsinventar für übernommene Bestandteile vorliegt.
5. Plattformkern und Energie-Vertikalpaket im Zielbild fachlich trennbar sind.
6. Build, Tests, Release und Git-Historie in das neue Repository übertragbar sind.

Die eigentliche Extraktion erfolgt mit erhaltener Git-Historie, nicht als unnachvollziehbare Ordnerkopie.

## Nicht-Ziele

- Kein generischer Low-Code-Baukasten für jedes IoT-Projekt.
- Kein Ersatz für BMS, DDC, SPS, Safety-Systeme oder LoRaWAN Network Server.
- Keine Cloud-Direktsteuerung ohne lokalen Policy- und Freigabepfad.
- Kein vollständiger Digital Twin, bevor ein Vertikal-Use-Case ihn wirtschaftlich rechtfertigt.
- Keine Protokollsammlung ohne konkreten Standort- und Produktbedarf.
- Keine Plattformbreite, bevor ein vertikaler Einstieg wiederholbar verkauft und betrieben werden kann.

## Begleitende Wissensbasis

Die fachliche Herleitung liegt im separaten Repository `llm-wiki-starter`:

- `wiki/analyses/operational-context-layer-gebaeudeautomation-nischen.md`
- `wiki/analyses/lorawan-iot-anwendungsfaelle-context-layer-nischen.md`
- `wiki/concepts/gebaeudearten-und-energietechnische-lastprofile.md`
- `wiki/concepts/ems-integrationsarchitektur-proptech-energytech.md`
- `wiki/concepts/building-energy-management.md`
- `wiki/concepts/ot-cloud-sicherheitsmuster-gebaeudeautomation.md`

Diese Seiten dienen der Markt-, Architektur- und Nischenforschung. Dieses Dokument ist dagegen die verbindliche
Produktleitplanke für Mini EMS.
