# Edge Integration Contract

Diese Datei ist der Integrationsvertrag zwischen Mini EMS und der Anlage. Sie definiert, was die Edge
gegenüber MSR, Betreiber, Dashboard, Cloud und späterem Business-System garantiert: was ein gültiger
Messwert ist, wann ein Wert `stale` oder `bad` ist, was gelesen und geschrieben werden darf, was geloggt
wird und was bei Netzwerk-, Controller- oder Cloud-Ausfall passiert.

Grundsatz: **Der Code ist die Wahrheit.** Jede Regel in dieser Datei ist aus dem realen BACnet-Pfad
abgeleitet (`mini_ems_runtime/config.py`, `channels.py`, `protocol.py`, `bacnet.py`,
`read_diagnostics.py`, `cycle.py`) und zitiert die echten Config-Schlüssel aus `config.json`
(IPC/Anlage) bzw. `config.local.json` (Laptop/Simulation). Weicht diese Datei vom Code ab, gilt der
Code, und diese Datei ist zu korrigieren.

Der Vertrag ist bewusst hardware- und betriebssystemneutral formuliert. Der Windows-IPC bleibt der
aktuelle Pilot- und Kundenpfad; das Modell selbst muss später auch auf Linux-IPC, Gateway oder
Container laufen können (siehe `ROADMAP.md`, Abschnitt "Strategische Ergänzung").

## Begriffsmodell

| Begriff | Bedeutung im Zielmodell | Heutige Umsetzung im Code |
|---|---|---|
| Gerät | physisches/logisches Quellsystem (MSR-Controller, Zähler, Gateway) | Default-Zielgerät aus `network.controller_ip`/`network.controller_port`; je Punkt überschreibbar über `controller_ip`/`controller_port` (`AdditionalInputConfig`, `PointConfig`) |
| Rohpunkt | protokollspezifische Adresse eines Werts | BACnet-Objekt aus `object_type` + `instance`, Property `presentValue` (`PROP_PRESENT_VALUE = 85` in `bacnet.py`) |
| Kanonischer Kanal | protokollneutraler Name, den Regelung, Historie und UI benutzen | `channel_id` in `ChannelRegistry`/`PointConfig` (`channels.py`), z. B. `grid.active_power_kw` |
| Semantik | Rolle, Einheit, Vorzeichen eines Kanals | heute implizit über Namenskonvention (`*_kw`, `*_c`, `*_kwh`) und `description`; Referenztabellen siehe unten |
| Qualität | Bewertung jedes gelesenen Werts | `status` (`ok`/`warning`/`error`), `plausible`, `quality` (`good`/`stale`/`bad`), `age_seconds` (`read_diagnostics.py`) |
| Historie | persistierte Zeitreihe und Zyklusdaten | SQLite über `runtime_db.py` (`cycle_runs`, `channel_samples`, Rollups) |
| Schreibpfad | kontrollierter, bestätigter Weg zurück zur Anlage | `ProtocolAdapter.write_with_confirmation()` mit `confirmation_mode` und `criticality` aus `outputs.*` |
| Fallback | definiertes Verhalten im Fehlerfall | `safe_mode`/`degraded`-Logik in `cycle.py`, Preis-Cache-Fallback in `price_cache.py` |
| Audit Trail | Nachvollziehbarkeit jedes Lese-/Schreibereignisses | strukturierte Log-Events (`log_event`), `runtime/health.json`, `runtime/state.json`, SQLite `bacnet_events` |

Der reale Datenfluss (heute nur BACnet, Vertrag aber protokollneutral):

```text
config.json
-> PointsConfig / AdditionalInputConfig        (config.py)
-> ChannelRegistry / PointConfig               (channels.py)
-> ProtocolAdapter                             (protocol.py; real: BacnetAdapter, lokal: SimulatedBacnetAdapter)
-> ChannelReadDiagnosticsService               (read_diagnostics.py: Plausibilität + Freshness/Quality)
-> CycleRunner                                 (cycle.py: Regelung, Safe Write Path, safe_mode/degraded)
-> StateStore + health.json + RuntimeDatabase  (state_store.py, runtime_db.py)
-> HTTP-API / Dashboard                        (http_api.py, read-only)
```

## Was ist ein gültiger Messwert?

Ein Messwert gilt als gültig, wenn alle folgenden Bedingungen erfüllt sind
(`ChannelReadDiagnosticsService.read_float_channel()`):

1. **Der Kanal ist lesbar konfiguriert.** `PointConfig.can_read()` verlangt `access` `read` oder
   `readwrite`; sonst wirft der Adapter `BacnetPermissionError`.
2. **Die Antwort kommt vom erwarteten Gerät.** `BacnetAdapter._receive_matching()` verwirft Pakete,
   deren Absender-IP/-Port nicht dem konfigurierten Controller entsprechen
   (Log-Event `bacnet.unexpected_sender`).
3. **Die Antwort ist ein parsebarer Float.** Ein nicht parsebares `ReadPropertyACK` führt zu
   `bacnet.read_parse_failed` und zählt als Lesefehler.
4. **Der Wert liegt in den Plausibilitätsgrenzen.** `plausible_min`/`plausible_max` stammen pro Punkt
   aus `PointConfig` (für `additional_inputs` direkt aus der Config, für `grid.active_power_kw` als
   Code-Default ±1.000.000 in `channels.py`). Ein Wert außerhalb setzt `plausible=false` und
   `error="value_out_of_range"`.
5. **Der Wert ist frisch genug.** Wenn `max_age_seconds` für den Punkt gesetzt ist, muss
   `age_seconds <= max_age_seconds` gelten (siehe nächster Abschnitt).

Nur wenn 1-5 erfüllt sind, ist `status = "ok"` und `quality = "good"`. Jeder Read wird mit
Zeitstempel, Wert, Status, Qualität und Alter geloggt und persistiert.

## Wann ist ein Wert stale oder bad?

Die Einstufung macht `_classify_quality()` in `read_diagnostics.py`:

| Qualität | Bedingung (Code) | Bedeutung |
|---|---|---|
| `bad` | kein Wert lesbar (Kommunikations-/Parse-Fehler, `status = "error"`) | Wert ist unbrauchbar |
| `stale` | Wert vorhanden, aber `age_seconds > max_age_seconds` | Wert ist zu alt für eine Entscheidung |
| `good` | Wert vorhanden, frisch genug oder kein `max_age_seconds` konfiguriert | Wert ist nutzbar |

Wichtige Detailregeln aus dem Code:

- Ohne konfiguriertes `max_age_seconds` bleibt ein Punkt dauerhaft `good` (Gate inaktiv). Deshalb
  setzen `config.json` und `config.local.json` für alle 17 `additional_inputs` Werte
  (IPC: `600` s, lokal: `120` s).
- Ein frischer, aber unplausibler Wert wird nicht `bad`, sondern `status = "warning"` mit
  `plausible=false` und `error="value_out_of_range"`; er darf nicht als Messwert weiterverwendet werden.
- Ein `stale`-Wert wird nie stillschweigend akzeptiert: `status` wird von `ok` auf `warning`
  herabgestuft und `error="value_stale"` gesetzt.
- Konsequenz je Risikoklasse (`cycle.py`): Für den regelungskritischen Kanal `grid.active_power_kw`
  wird jeder Nicht-`ok`-Read (also auch `stale`) wie ein Lesefehler behandelt und führt in den
  `safe_mode`. Für `additional_inputs` gibt es nur eine Warnung (`cycle.input_warning`), keinen
  `safe_mode`; die Werte bleiben mit `quality`/`age_seconds` in `health.json` und Historie sichtbar.

## Was darf gelesen werden?

Es gilt eine Allowlist: Nur Kanäle, die in `config.json` konfiguriert sind (Abschnitte `points` und
`additional_inputs`), existieren in der `ChannelRegistry`. Alles andere wird vom Adapter mit
`BacnetPermissionError` abgelehnt.

- Lesbar sind alle Punkte mit `access` `read` oder `readwrite` (`PointConfig.can_read()`).
- Alle `additional_inputs` sind hart `access="read"` (gesetzt in `ChannelRegistry.from_points_config()`);
  ein Schreibrecht auf Messwerte ist im Modell nicht vorgesehen.
- Der Lesetakt ist konfiguriert: `timing.cycle_seconds` (60 s) pro Zyklus, `read_interval_cycles`
  pro Zusatzpunkt (aktuell `5`, also alle 300 s), `timing.inter_read_delay_seconds` als Pause zwischen
  Reads im selben Zyklus.
- Gelesen wird ausschließlich `presentValue` per BACnet `ReadProperty`; andere Properties oder
  Objekttypen als `AI`/`AV`/`BV` sind nicht implementiert (`_parse_object_type()` in `config.py`).

## Was darf geschrieben werden?

Der Schreibpfad ist die höhere Risikoklasse und maximal eingeschränkt:

- **Nur drei Ausgangskanäle** existieren (`ChannelRegistry.output_channel_ids()`):
  `tariff.current_price_ct_kwh` (`AV:1000`, `access="readwrite"`), `ems.lockout_grid` (`BV:400`,
  `access="write"`) und `ems.lockout_spotmarket` (`BV:401`, `access="write"`). Jeder andere
  Schreibversuch scheitert an `PointConfig.can_write()` mit `BacnetPermissionError`.
- **Jeder Write ist bestätigungspflichtig** (`write_with_confirmation()` in `bacnet.py`):
  BACnet `WriteProperty` auf `presentValue` mit fester Priorität `14` (`WRITE_PRIORITY`).
  Bestätigung per `SimpleACK`; bei `confirmation_mode="ack_or_readback"` (nur `AV`) ersatzweise per
  Readback mit Toleranz `0.001` (`_float_values_match()`).
- **Die Schreibpolitik steht in der Config** (`outputs.*` in `config.json`):
  `current_price` = `ack_or_readback`/`noncritical`, `grid_lockout` und `spotmarket_lockout` =
  `ack_only`/`critical`. Ein unbestätigter kritischer Write führt in den `safe_mode`, ein
  unbestätigter nicht-kritischer Write in den Status `degraded`.
- **Geschrieben wird nur bei Bedarf** (`CycleRunner._apply_outputs()`): bei Sollwertwechsel, fehlender
  Bestätigung oder neuem Preis-Slot (`handoff_key`). Nach jedem Runtime-Start erzwingt
  `safe_mode_reason="startup_validation"` eine Neubestätigung aller Outputs.
- **`ems.lockout_grid` ist aktuell deaktiviert:** `controllers.grid_lockout.enabled=false` in
  `config.json`; der Kanal wird dann weder gelesen noch geschrieben.
- **Safety-Flags trennen Simulation und Anlage** (`_validate_config()` in `config.py`):
  `runtime.environment="local"` erzwingt `runtime.bacnet_mode="simulated"`, simulierter Modus erzwingt
  `runtime.real_writes_enabled=false`, und `real_writes_enabled=false` ist mit echtem BACnet nicht
  startbar. Simulierte Writes werden nur intern gespeichert (`confirmation_source="simulated"`,
  Log-Event `simulation.bacnet_write`) und erreichen die Anlage nie.

## Was wird geloggt? (Audit Trail und Historie)

Jedes Lese- und Schreibereignis ist auf drei Ebenen nachvollziehbar:

1. **Strukturierte Log-Events** in `logs/mini_ems.log` (`log_event()` in `logging_utils.py`), u. a.:
   `bacnet.read_diagnostic` (jeder Read mit `status`, `quality`, `age_seconds`, `max_age_seconds`),
   `bacnet.read_retry` / `bacnet.write_retry`, `bacnet.unexpected_sender`, `bacnet.discarded_response`,
   `cycle.start`, `cycle.healthy`, `cycle.degraded`, `cycle.safe_mode`, `cycle.input_warning`,
   `cycle.output_confirmed` / `cycle.output_not_confirmed`, `simulation.bacnet_write`,
   `runtime_db.write_failed`.
2. **Operator-Snapshot** `runtime/health.json` (`_build_health_payload()` in `cycle.py`): Status,
   `safe_mode_reason`/`degraded_reason`, `write_status` je Ausgang (Sollwert, Bestätigung, Readback,
   letzter Fehler) sowie `additional_inputs` mit `value`, `status`, `error`, `quality`,
   `age_seconds`, `max_age_seconds` für Punkte mit `include_in_health=true`. Der technische
   Persistenzzustand liegt in `runtime/state.json`.
3. **SQLite-Historie** (`data/runtime/mini_ems.sqlite`, `runtime_db.py`): `cycle_runs` (kompletter
   Snapshot je Zyklus), `channel_samples` (jeder Input- und Output-Wert mit Bestätigungsstatus),
   `price_slots`, `spotmarket_windows`, `bacnet_events` (Read-/Write-Fehler und
   Kommunikationsereignisse) sowie `channel_rollups_5m`/`_1h`/`_1d` für Reports.

Damit ist für jeden Zyklus rekonstruierbar: welcher Rohwert gelesen wurde, wie er bewertet wurde,
welcher Sollwert warum geschrieben wurde und ob die Anlage ihn bestätigt hat.

## Was passiert bei Netzwerk-, Controller- oder Cloud-Ausfall?

| Ausfall | Verhalten (Code) |
|---|---|
| BACnet-Netzwerk/Controller antwortet nicht | Retries pro Zugriff (`network.retries`, Timeout `network.response_timeout_seconds`), dann `BacnetCommunicationError`. Grid-Read-Fehler oder unbestätigter kritischer Write → sofort `safe_mode` im selben Zyklus; Fehler bei `additional_inputs` → nur `warning` + `quality="bad"`. `consecutive_comm_errors` wird gezählt und in `state.json`/Snapshot ausgewiesen. Hinweis: `safety.comm_error_safe_mode_threshold` wird validiert (`> 0`), aber aktuell nicht als Schaltschwelle ausgewertet — der `safe_mode` greift bereits beim ersten kritischen Fehler. |
| Cloud-Ausfall (SMARD nicht erreichbar) | `SpotmarketPriceCacheService.refresh()` fällt auf den lokalen Cache (`data/spotmarket/spotmarket_price_cache.json`) zurück, solange dieser den aktuellen Tag und Slot abdeckt; der Zustand wird als `price_source_status.fallback="cache"` markiert. Erst wenn auch der Cache den aktuellen Slot nicht liefert, führt `PriceProviderError` in den `safe_mode`. |
| Nicht-kritischer Write scheitert (Preis auf `AV:1000`) | Status `degraded`, Betrieb läuft weiter, Grund in `degraded_reason`; im nächsten Zyklus wird erneut geschrieben. |
| `safe_mode` aktiv | Keine weiteren Sollwert-Schreibvorgänge im Zyklus; Grund steht in `safe_mode_reason` (`health.json`, Log, SQLite). Die MSR-Controller regeln autark weiter; zuletzt geschriebene BACnet-Werte bleiben auf der Anlage stehen. |
| IPC-/Runtime-Ausfall | Mini EMS stoppt; keine neuen Reads/Writes/DB-Einträge. Nach Neustart (Scheduled Task) wird der Zustand aus `runtime/state.json` geladen und der erste Zyklus bestätigt alle Outputs neu (`startup_validation`). Ein Preiswechsel während des Ausfalls wird nicht nachträglich geschrieben. Details: `MINI_EMS_ANLEITUNG.md`, Abschnitt "Verhalten bei IPC-Ausfall". |

## Referenzmodell: das bestehende BACnet-Mapping (S2)

Dieses Kapitel bildet die real konfigurierten Punkte aus `config.json` auf das Zielmodell ab. Es ist
die Vorlage für spätere Modbus-, HTTP-, MQTT- oder GLT-Anbindungen (Protokoll-Muster und
Mapping-Vorlagen: `EMS-Mapping.md`).

### Geräte

| Gerät (`source_device`) | Protokoll | Adresse | Beschreibung |
|---|---|---|---|
| `msr1` | `bacnet_ip` | `192.168.244.30:47808` (Default aus `network.controller_ip`/`controller_port`) | MSR-Controller Heizzentrale; Ziel aller Punkte ohne eigenes `controller_ip` |
| `msr2` | `bacnet_ip` | `192.168.244.40:47808` (per Punkt gesetzt über `controller_ip`) | zweiter MSR-Controller (Außentemperatur) |

### Punkte: Identität und Zugriff

`raw_address` ist immer `Objekttyp:Instanz` auf Property `presentValue`. Rollen: `measurement`
(Messwert, nur lesen), `setpoint` (Sollwert mit Readback), `command` (Schaltbefehl).

| `source_id` | `protocol` | `raw_address` | `channel_id` | `equipment_id` | `role` | `unit` | `access` |
|---|---|---|---|---|---|---|---|
| `msr1.av300` | `bacnet_ip` | `AV:300` | `grid.active_power_kw` | `netzanschluss` | `measurement` | kW | `read` |
| `msr1.av1000` | `bacnet_ip` | `AV:1000` | `tariff.current_price_ct_kwh` | `ems_uebergabe` | `setpoint` | ct/kWh | `readwrite` |
| `msr1.bv400` | `bacnet_ip` | `BV:400` | `ems.lockout_grid` | `heizzentrale` | `command` | bool | `write` |
| `msr1.bv401` | `bacnet_ip` | `BV:401` | `ems.lockout_spotmarket` | `heizzentrale` | `command` | bool | `write` |
| `msr2.ai1801` | `bacnet_ip` | `AI:1801` | `site.outdoor_temperature_c` | `aussenbereich` | `measurement` | °C | `read` |
| `msr1.ai1101` | `bacnet_ip` | `AI:1101` | `site.buffer_1_top_temperature_c` | `puffer_1` | `measurement` | °C | `read` |
| `msr1.ai1102` | `bacnet_ip` | `AI:1102` | `site.buffer_1_bottom_temperature_c` | `puffer_1` | `measurement` | °C | `read` |
| `msr1.ai1103` | `bacnet_ip` | `AI:1103` | `site.buffer_2_top_temperature_c` | `puffer_2` | `measurement` | °C | `read` |
| `msr1.ai1104` | `bacnet_ip` | `AI:1104` | `site.buffer_2_bottom_temperature_c` | `puffer_2` | `measurement` | °C | `read` |
| `msr1.ai1107` | `bacnet_ip` | `AI:1107` | `site.heat_generation_flow_temperature_c` | `waermeerzeugung` | `measurement` | °C | `read` |
| `msr1.ai1108` | `bacnet_ip` | `AI:1108` | `site.heat_generation_return_temperature_c` | `waermeerzeugung` | `measurement` | °C | `read` |
| `msr1.ai2101` | `bacnet_ip` | `AI:2101` | `site.boiler_1_flow_temperature_c` | `kessel_gas` | `measurement` | °C | `read` |
| `msr1.ai1201` | `bacnet_ip` | `AI:1201` | `site.boiler_1_return_temperature_c` | `kessel_gas` | `measurement` | °C | `read` |
| `msr1.ai2102` | `bacnet_ip` | `AI:2102` | `site.boiler_2_flow_temperature_c` | `kessel_pellet` | `measurement` | °C | `read` |
| `msr1.ai1202` | `bacnet_ip` | `AI:1202` | `site.boiler_2_return_temperature_c` | `kessel_pellet` | `measurement` | °C | `read` |
| `msr1.ai1203` | `bacnet_ip` | `AI:1203` | `site.chp_flow_temperature_c` | `bhkw` | `measurement` | °C | `read` |
| `msr1.ai1204` | `bacnet_ip` | `AI:1204` | `site.chp_return_temperature_c` | `bhkw` | `measurement` | °C | `read` |
| `msr1.av48` | `bacnet_ip` | `AV:48` | `site.chp_electric_energy_kwh` | `bhkw` | `measurement` | kWh | `read` |
| `msr1.av49` | `bacnet_ip` | `AV:49` | `site.chp_thermal_energy_kwh` | `bhkw` | `measurement` | kWh | `read` |
| `msr1.av50` | `bacnet_ip` | `AV:50` | `site.pellet_thermal_energy_kwh` | `kessel_pellet` | `measurement` | kWh | `read` |
| `msr1.av51` | `bacnet_ip` | `AV:51` | `site.gas_thermal_energy_kwh` | `kessel_gas` | `measurement` | kWh | `read` |

### Punkte: Plausibilität, Aktualität und Schreibrecht

Leseabstand für `additional_inputs`: `read_interval_cycles=5` × `timing.cycle_seconds=60` = 300 s.
`max_age_seconds` gilt je Umgebung: `config.json` (IPC) / `config.local.json` (lokal).

| Kanal bzw. Gruppe | `plausible_min` | `plausible_max` | `max_age_seconds` (IPC / lokal) | Schreibrecht |
|---|---:|---:|---|---|
| `grid.active_power_kw` | -1.000.000 | 1.000.000 (Code-Default in `channels.py`) | nicht gesetzt; Absicherung über `safe_mode` bei jedem Nicht-`ok`-Read | nein; wird nur bei `controllers.grid_lockout.enabled=true` überhaupt gelesen |
| `tariff.current_price_ct_kwh` | – | – | – (Readback dient nur der Write-Bestätigung) | ja: `ack_or_readback`, `noncritical`, BACnet-Priorität 14 |
| `ems.lockout_grid` | – | – | – | ja: `ack_only`, `critical`, Priorität 14; aktuell nicht geschrieben (`controllers.grid_lockout.enabled=false`) |
| `ems.lockout_spotmarket` | – | – | – | ja: `ack_only`, `critical`, Priorität 14 |
| `site.outdoor_temperature_c` | -50 | 60 | 600 s / 120 s | nein (`include_in_health=true`) |
| übrige `site.*_temperature_c` (12 Punkte) | -20 | 120 | 600 s / 120 s | nein |
| `site.*_energy_kwh` (4 Punkte) | 0 | 1.000.000.000 | 600 s / 120 s | nein |

### Die Regelung als Nutzerin kanonischer Kanäle

Fachlich lässt sich die Regelung vollständig ohne Protokollbegriffe beschreiben:

- `GridLockoutController` liest `grid.active_power_kw` und entscheidet über `ems.lockout_grid`.
- Die Spotmarkt-Logik (`spotmarket_plan.py` + Override) entscheidet über `ems.lockout_spotmarket`
  und den Sollwert `tariff.current_price_ct_kwh`.
- `CycleRunner` kennt nur `channel_id`s und den neutralen Adapter-Vertrag aus `protocol.py`
  (`read_float(point)`, `write_with_confirmation(point, desired_value, confirmation_mode)`, `close()`).

Dass darunter BACnet liegt, ist austauschbar: heute erfüllen `BacnetAdapter` (real) und
`SimulatedBacnetAdapter` (lokal) denselben Vertrag; ein Modbus-Adapter (Roadmap S4) käme als dritte
Implementierung hinzu, ohne dass Regelung, Historie oder API sich ändern.

## Geräte-Template: Hauptzähler / Netzanschlusspunkt (S3)

Erste wiederverwendbare Geräteklasse ist der Hauptzähler am Netzanschlusspunkt, weil daran
Lastspitzen, Eigenverbrauch, Speicher, Spotmarkt, Flexibilität und §14a hängen. Das Template ist
reine Doku- und Config-Vorlage; es ändert keinen Code und keine aktive Konfiguration.

### Rohpunkte und Kanäle

Kanalnamen folgen dem `meter.grid.*`-Schema aus `EMS-Mapping.md` (nahe an OpenEMS
`ElectricityMeter`). Vorzeichenregel wie `MeterType.GRID`: Netzbezug positiv, Einspeisung negativ.

| Kanal | Rolle | Einheit | Pflicht | Bedeutung |
|---|---|---|---|---|
| `meter.grid.active_power_kw` | `measurement` | kW | ja | Wirkleistung gesamt am Netzanschluss |
| `meter.grid.active_power_l1_kw` / `_l2_` / `_l3_` | `measurement` | kW | optional | Wirkleistung je Phase (Schieflast) |
| `meter.grid.reactive_power_kvar` | `measurement` | kvar | optional | Blindleistung gesamt |
| `meter.grid.voltage_l1_v` (analog L2/L3) | `measurement` | V | optional | Spannung je Phase |
| `meter.grid.current_l1_a` (analog L2/L3) | `measurement` | A | optional | Strom je Phase |
| `meter.grid.frequency_hz` | `measurement` | Hz | optional | Netzfrequenz |
| `meter.grid.consumed_energy_kwh` | `measurement` | kWh | ja | Bezug kumuliert (Zählerstand) |
| `meter.grid.exported_energy_kwh` | `measurement` | kWh | optional | Einspeisung kumuliert |

### Plausibilitätsgrenzen

Grenzen sind Anlagenwerte, keine Messbereiche; sie werden pro Standort aus der Anschlussleistung
`P_max` (bzw. dem Stromwandlerverhältnis) abgeleitet:

| Kanal | `plausible_min` | `plausible_max` | Herleitung |
|---|---:|---:|---|
| `meter.grid.active_power_kw` | -1,5 × P_max | 1,5 × P_max | Reserve für kurzzeitige Spitzen und Einspeisung |
| `meter.grid.active_power_l*_kw` | -0,6 × P_max | 0,6 × P_max | einzelne Phase |
| `meter.grid.voltage_l*_v` | 180 | 260 | Niederspannung 230 V ±Toleranz |
| `meter.grid.current_l*_a` | 0 | 1,2 × I_CT | Wandler-Nennstrom mit Reserve |
| `meter.grid.frequency_hz` | 45 | 55 | alles außerhalb ist ein Messfehler |
| `meter.grid.*_energy_kwh` | 0 | 1.000.000.000 | wie die bestehenden `site.*_energy_kwh`-Punkte; Zählerstände sind monoton steigend |

### Aktualitätsregeln

Regel aus dem Bestandsmuster: `max_age_seconds >= 2 × Leseabstand`, wobei
Leseabstand = `read_interval_cycles` × `timing.cycle_seconds` (so sind die 17 Bestandspunkte
konfiguriert: 300 s Leseabstand, 600 s `max_age_seconds`).

| Kanalgruppe | `read_interval_cycles` (bei 60-s-Zyklus) | `max_age_seconds` |
|---|---:|---:|
| Leistung (`active_power*`, `reactive_power*`) | 1 (jeden Zyklus) | 120 |
| Spannung, Strom, Frequenz | 1 | 120 |
| Energie/Zählerstände (`*_energy_kwh`) | 5 | 600 |

Ein Hauptzähler mit `quality="stale"` auf `meter.grid.active_power_kw` darf nicht für
Lastmanagement-Entscheidungen genutzt werden (gleiche konservative Regel wie heute für
`grid.active_power_kw`: Nicht-`ok` → `safe_mode`).

### Schreibrechte

Standard: **keine**. Ein Hauptzähler ist ein reines Messgerät; alle Punkte sind `access="read"`.
Optional und erst nach Betreiberfreigabe kommt ein getrennter Befehls-Kanal in Richtung MSR hinzu
(z. B. `ems.limit_grid_power_kw` für §14a-Dimmen) — als eigener `command`-Punkt nach dem Muster von
`ems.lockout_spotmarket`: `access="write"`, `confirmation_mode="ack_only"`, `criticality="critical"`.
Der Befehl gehört zur EMS-Übergabe, nie zum Zähler selbst.

### Beispielhafte Config-Struktur

Variante A — sofort umsetzbar im heutigen Schema (`additional_inputs`, BACnet, read-only), falls die
GLT die Zählerwerte als BACnet-Objekte bereitstellt:

```json
{
  "channel_id": "meter.grid.active_power_kw",
  "object_type": "av",
  "instance": 310,
  "description": "Hauptzähler Wirkleistung Netzanschluss",
  "plausible_min": -750.0,
  "plausible_max": 750.0,
  "include_in_health": true,
  "read_interval_cycles": 1,
  "max_age_seconds": 120
},
{
  "channel_id": "meter.grid.consumed_energy_kwh",
  "object_type": "av",
  "instance": 311,
  "description": "Hauptzähler Bezugsenergie kumuliert",
  "plausible_min": 0.0,
  "plausible_max": 1000000000.0,
  "include_in_health": false,
  "read_interval_cycles": 5,
  "max_age_seconds": 600
}
```

Variante B — protokollneutrale Zielstruktur für den direkten Zähleranschluss (z. B. Modbus TCP,
Roadmap S4); Feldnamen wie in den Mapping-Vorlagen in `EMS-Mapping.md`:

```json
{
  "device_id": "main_meter",
  "protocol": "modbus_tcp",
  "equipment_id": "netzanschluss",
  "device_class": "grid_meter",
  "points": [
    {
      "channel_id": "meter.grid.active_power_kw",
      "role": "measurement",
      "register": 19026,
      "data_type": "float32",
      "scale": 0.001,
      "invert": false,
      "access": "read",
      "unit": "kW",
      "plausible_min": -750.0,
      "plausible_max": 750.0,
      "max_age_seconds": 120
    },
    {
      "channel_id": "meter.grid.consumed_energy_kwh",
      "role": "measurement",
      "register": 19062,
      "data_type": "float32",
      "scale": 0.001,
      "invert": false,
      "access": "read",
      "unit": "kWh",
      "plausible_min": 0.0,
      "plausible_max": 1000000000.0,
      "max_age_seconds": 600
    }
  ]
}
```

Beide Varianten erfüllen denselben Vertrag: gleiche Kanalnamen, gleiche Qualitätsregeln, gleiche
Historie — nur der `ProtocolAdapter` darunter unterscheidet sich.

## Querverweise

- `EMS-Mapping.md` — Protokoll-Muster (Modbus, M-Bus, HTTP, MQTT) und Mapping-Vorlagen
- `MINI_EMS_ANLEITUNG.md` — Betrieb, Konfiguration, API, IPC-Ausfallverhalten
- `ROADMAP.md` — strategische To-do-Linie Edge-Integrationskern (S1-S4)
