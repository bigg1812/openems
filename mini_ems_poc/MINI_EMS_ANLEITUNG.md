# Mini EMS PoC - Architektur, Betrieb und aktueller Stand

## Ziel

Dieses PoC ist eine kleine Python-Edge auf dem IPC. Sie uebernimmt vier Aufgaben:

- Spotmarktpreise von SMARD holen
- BACnet-Werte lesen
- BACnet-Werte schreiben
- Laufzeitdaten fuer Betrieb, API und Reports persistieren

Der aktuelle fachliche Scope ist:

- BACnet Read auf `AV:300` als `grid.active_power_kw`
- BACnet Read auf `AI:1801` des zweiten Controllers als `site.outdoor_temperature_c`
- BACnet Write auf:
  - `AV:1000` fuer den aktuellen Viertelstundenpreis
  - `BV:400` fuer Grid-Lockout
  - `BV:401` fuer Spotmarket-Lockout
- SQLite-Historie fuer Zyklen, Kanalwerte, Preis-Slots, Spotmarktfenster und BACnet-Ereignisse
- lokale Read-only-HTTP-API plus einfaches Dashboard

## Architektur

### Kernmodule

`mini_ems.py`
- CLI-Entrypoint
- startet `--once` oder `--loop`

`config.json`
- zentrale Parametrierung
- enthaelt Netzwerk, BACnet-Punkte, Timing, Safety, DB- und API-Pfade

`mini_ems_runtime/app.py`
- setzt Runtime, API, Datenbank und Zyklus zusammen

`mini_ems_runtime/bacnet.py`
- BACnet/IP Transport
- UDP-Socket, Read/Write, ACK- und Readback-Behandlung

`mini_ems_runtime/simulation.py`
- lokaler Simulationsmodus für Laptop-Entwicklung
- ersetzt BACnet-Reads durch Werte aus `sim/sample_values.json`
- bestätigt Writes als simulierte Writes, ohne echte BACnet-Schreibbefehle zu senden
- erzeugt simulierte Spotmarktpreise aus `sim/sample_prices.json`

`mini_ems_runtime/channels.py`
- baut den Kanalraum fuer Standardpunkte und zusaetzliche Inputs auf

`mini_ems_runtime/controllers.py`
- fachliche Logik fuer Grid- und Spotmarket-Lockout

`mini_ems_runtime/cycle.py`
- orchestriert den Zyklus
- liest Inputs, aktualisiert Preise, berechnet Sollwerte, schreibt BACnet, persistiert Snapshot und Historie

`mini_ems_runtime/price_provider_smard.py`
- holt Day-Ahead-Preise von SMARD

`mini_ems_runtime/price_cache.py`
- verwaltet den lokalen Spotmarkt-Cache mit `today` und `tomorrow`

`mini_ems_runtime/spotmarket_plan.py`
- erkennt negative Preisfenster
- verarbeitet auch manuelle Override-Fenster

`mini_ems_runtime/read_diagnostics.py`
- liefert wiederholbare Diagnose-Reads fuer BACnet-Inputs

`mini_ems_runtime/runtime_db.py`
- verwaltet die SQLite-Datenbank
- schreibt Rohdaten und Rollups

`mini_ems_runtime/http_api.py`
- lokale Read-only-API
- liefert Status, Historie, Reports und Diagnose-Reads

`mini_ems_runtime/state_store.py`
- schreibt `runtime/state.json` und `runtime/health.json`

## Aktuelle Ordnerstruktur

Die folgende Struktur zeigt die IPC-Pfade aus `config.json`. Der lokale Simulationsbetrieb mit
`config.local.json` schreibt in eigene Unterordner (`data/local/`, `logs/local/`, `runtime/local/`) -
siehe Abschnitt "Konfiguration" und "Wichtige Laufzeitdateien" fuer die genauen lokalen Pfade.

```text
mini_ems_poc/
|-- config.json
|-- config.local.json
|-- mini_ems.py
|-- MINI_EMS_ANLEITUNG.md
|-- run_mini_ems.cmd
|-- dashboard/
|   |-- dashboard.css
|   |-- dashboard.js
|   `-- index.html
|-- data/
|   |-- runtime/
|   |   `-- mini_ems.sqlite
|   |-- local/
|   |   |-- mini_ems.local.sqlite
|   |   |-- spotmarket_price_cache.json
|   |   |-- spotmarket_tomorrow_windows.json
|   |   `-- spotmarket_manual_override.json
|   `-- spotmarket/
|       |-- spotmarket_manual_override.json
|       |-- spotmarket_manual_override.example.json
|       |-- spotmarket_price_cache.json
|       `-- spotmarket_tomorrow_windows.json
|-- logs/
|   |-- mini_ems.log
|   |-- mini_ems_stdout.log
|   `-- local/
|       `-- mini_ems.local.log
|-- mini_ems_runtime/
|   |-- app.py
|   |-- bacnet.py
|   |-- channels.py
|   |-- config.py
|   |-- controllers.py
|   |-- cycle.py
|   |-- http_api.py
|   |-- logging_utils.py
|   |-- operator_status.py
|   |-- price_cache.py
|   |-- price_provider_smard.py
|   |-- read_diagnostics.py
|   |-- runtime_db.py
|   |-- spotmarket_plan.py
|   `-- state_store.py
|-- runtime/
|   |-- health.json
|   |-- state.json
|   `-- local/
|       |-- health.json
|       `-- state.json
|-- sim/
|   |-- sample_prices.json
|   `-- sample_values.json
|-- tests/
`-- windows/
    `-- install_task.ps1
```

## Laptop-Entwicklung mit Simulation

Die Grundregel ist:

- `config.json` bleibt die IPC-Konfiguration für die echte Anlage.
- `config.local.json` ist die Laptop-Konfiguration für ungefährliche Entwicklung.

Im lokalen Modus wird nicht versucht, die komplette Anlage physikalisch nachzubauen.
Es werden nur die Eingangswerte simuliert, die Mini EMS gerade braucht.

Technischer Ablauf:

1. `mini_ems.py` lädt `config.local.json`.
2. `runtime.bacnet_mode` steht auf `simulated`.
3. Die App verwendet `SimulatedBacnetAdapter` statt `BacnetAdapter`.
4. BACnet-Reads kommen aus `sim/sample_values.json`.
5. BACnet-Writes werden nur intern gespeichert und als `simulation.bacnet_write` geloggt.
6. Spotmarktpreise kommen aus `sim/sample_prices.json`.
7. Datenbank, Logs, State und Health werden getrennt unter lokalen Pfaden geschrieben.

Start aus dem Ordner `mini_ems_poc`:

```bash
python mini_ems.py --config config.local.json --once
python mini_ems.py --config config.local.json --loop
```

`--once` führt genau einen Zyklus aus.
`--loop` startet den dauerhaften Betrieb mit wiederholten Zyklen und lokaler API.

Die lokale API läuft mit `config.local.json` auf:

```text
http://127.0.0.1:8090
```

Der Sicherheitsmechanismus ist bewusst hart:

- `environment=local` darf nur mit `bacnet_mode=simulated` starten.
- `bacnet_mode=simulated` verlangt `real_writes_enabled=false`.
- `real_writes_enabled=false` ist mit echtem BACnet nicht erlaubt, damit keine Scheinsicherheit entsteht.

## Konfiguration

### Netzwerk

```json
"network": {
  "controller_ip": "192.168.244.30",
  "controller_port": 47808,
  "local_ip": "192.168.244.10",
  "local_port": 47809,
  "response_timeout_seconds": 5.0,
  "retries": 1
}
```

Bedeutung:

- `controller_ip`: Default-Zielgeraet fuer BACnet
- `controller_port`: meist `47808`
- `local_ip`: echte IP des IPC
- `local_port`: lokaler UDP-Port des IPC

### Standardpunkte

```json
"points": {
  "grid_active_power_kw": 300,
  "current_price_av": 1000,
  "grid_lockout_bv": 400,
  "spotmarket_lockout_bv": 401
}
```

### Zusaetzliche Inputs

Aktuell ist ein zusaetzlicher Read-only-Sensor konfiguriert:

```json
"additional_inputs": [
  {
    "channel_id": "site.outdoor_temperature_c",
    "object_type": "ai",
    "instance": 1801,
    "controller_ip": "192.168.244.40",
    "controller_port": 47808,
    "description": "Outdoor air temperature in degC",
    "plausible_min": -50.0,
    "plausible_max": 60.0,
    "include_in_health": true
  }
]
```

Damit liest Mini-EMS vom zweiten Controller die Aussentemperatur als eigenen Kanal.

### Timing

```json
"timing": {
  "cycle_seconds": 60,
  "inter_read_delay_seconds": 0.05
}
```

Das System prueft jede Minute. `inter_read_delay_seconds` ist nur die kleine Pause zwischen einzelnen BACnet-Leseoperationen im selben Zyklus.

### Preisquelle

```json
"price_source": {
  "provider": "smard",
  "region": "DE-LU",
  "filter": 4169,
  "resolution": "quarterhour",
  "timeout_seconds": 30,
  "price_factor": 0.1
}
```

Wichtig:

- SMARD liefert hier Day-Ahead-Preise in `EUR/MWh`
- `price_factor = 0.1` wandelt in `ct/kWh`
- gearbeitet wird durchgehend mit 96 Viertelstundenwerten pro Tag

### Regler

```json
"controllers": {
  "grid_lockout": {
    "threshold_kw": 5.0,
    "clear_threshold_kw": 5.5,
    "below_threshold_cycles_required": 3
  },
  "spotmarket_lockout": {
    "negative_quarters_min_consecutive": 8,
    "min_valid_quarters": 96,
    "invalid_price_sentinel": null
  }
}
```

Aktuelle Spotmarket-Regel:

- `8` Viertelstunden hintereinander mit Preis `<= 0`
- das entspricht `2` Stunden am Stueck

### Output-Bestaetigung

```json
"outputs": {
  "current_price": {
    "confirmation_mode": "ack_or_readback",
    "criticality": "noncritical"
  },
  "grid_lockout": {
    "confirmation_mode": "ack_only",
    "criticality": "critical"
  },
  "spotmarket_lockout": {
    "confirmation_mode": "ack_only",
    "criticality": "critical"
  }
}
```

Das bedeutet:

- `AV:1000` gilt als bestaetigt, wenn `SimpleACK` kommt oder ein passender Readback den Wert bestaetigt
- `BV:400` und `BV:401` bleiben streng `ack_only`
- nicht-kritische Fehler fuehren zu `degraded`
- kritische Fehler fuehren zu `safe_mode`

### Datenbank und API

IPC (`config.json`):

```json
"database": {
  "sqlite_file": "data/runtime/mini_ems.sqlite"
},
"api": {
  "enabled": true,
  "host": "192.168.244.10",
  "port": 8090,
  "history_default_limit": 96
}
```

Lokal (`config.local.json`):

```json
"database": {
  "sqlite_file": "data/local/mini_ems.local.sqlite"
},
"api": {
  "enabled": true,
  "host": "127.0.0.1",
  "port": 8090,
  "history_default_limit": 96
}
```

## Laufzeitverhalten

### Inputs

Der Zyklus liest aktuell:

- `grid.active_power_kw` aus `AV:300`
- `site.outdoor_temperature_c` aus `AI:1801` auf `192.168.244.40`

`grid.active_power_kw` ist fachlich kritisch. Ein Read-Fehler kann den Status auf `safe_mode` bringen. Zusaetzliche Inputs wie die Aussentemperatur sind nicht-kritisch und werden getrennt behandelt.

### Preisuebergabe auf AV1000

Das System:

1. holt Day-Ahead-Daten von SMARD
2. speichert `today` und `tomorrow` lokal
3. bestimmt den aktuellen Viertelstunden-Slot
4. schreibt den passenden Preis auf `AV:1000`
5. bestaetigt den Write ueber `ACK` oder passenden Readback

Wichtig:

- geschrieben wird bei Sollwertwechsel oder wenn eine neue Bestaetigung erforderlich ist
- der aktuelle Preisstand wird in `health.json` und in der Historie sichtbar

### Spotmarket-Lockout

`BV:401` kann aus zwei Quellen kommen:

1. automatisch aus negativen Preisfenstern
2. manuell aus der Override-Datei

Die manuelle Testdatei ist:

- IPC (`config.json`): [spotmarket_manual_override.json](C:/dev/openems/mini_ems_poc/data/spotmarket/spotmarket_manual_override.json)
- Lokal (`config.local.json`): `data/local/spotmarket_manual_override.json`

Beispiel:

```json
{
  "enabled": true,
  "date": "2026-04-02",
  "note": "Manueller Test fuer BV401",
  "windows": [
    {
      "start_label": "11:00",
      "end_label_exclusive": "11:30"
    }
  ]
}
```

Wichtig:

- nur Viertelstunden sind erlaubt: `:00`, `:15`, `:30`, `:45`
- die Datei wird im Loop immer wieder neu gelesen
- fuer Aenderungen ist kein Task-Neustart noetig

### Grid-Lockout

`BV:400` ist fachlich vorgesehen und im aktiven Output-Schema vorhanden. Die Logik nutzt weiterhin Schwellwert, Clear-Threshold und Zyklus-Hysterese. Dieser Kanal bleibt sicherheitskritisch und verlangt eine echte Write-Bestaetigung.

## Wichtige Laufzeitdateien

### `runtime/health.json`

IPC (`config.json`): [health.json](C:/dev/openems/mini_ems_poc/runtime/health.json)
Lokal (`config.local.json`): `runtime/local/health.json`

Diese Datei ist der kompakte Operator-Snapshot. Sie zeigt nur den aktuellen Zustand und keine vollstaendige Historie.

Wichtige Felder:

- `status`
  - `healthy`
  - `degraded`
  - `safe_mode`
- `timestamp`
- `current_slot_label`
- `current_price_ct_kwh`
- `grid_active_power_kw`
- `grid_read_status`
- `grid_lockout_active`
- `spotmarket_active_now`
- `spotmarket_next_window`
- `last_price_handoff_at`
- `last_price_handoff_slot_label`
- `last_price_handoff_value_ct_kwh`
- `operator_message`
- `write_status`
- `additional_inputs`

Beispiel fuer zusaetzliche Inputs:

```json
"additional_inputs": {
  "site.outdoor_temperature_c": {
    "status": "ok",
    "value": 15.0269,
    "error": null
  }
}
```

Beispiel fuer Output-Status:

```json
"write_status": {
  "current_price": {
    "confirmed": true,
    "desired_value": 4.709,
    "last_confirmation_mode": "ack",
    "last_confirmed_at": "2026-04-09T08:30:44.320758Z",
    "last_confirmed_value": 4.709,
    "last_error": null,
    "last_readback_value": null
  }
}
```

### `runtime/state.json`

IPC (`config.json`): [state.json](C:/dev/openems/mini_ems_poc/runtime/state.json)
Lokal (`config.local.json`): `runtime/local/state.json`

Diese Datei ist der technische Persistenzzustand der Runtime. Sie ist fuer Debugging und Neustart-Wiederaufnahme wichtig, aber nicht als schlanke Bedienoberflaeche gedacht.

### `logs/mini_ems.log`

IPC (`config.json`): [mini_ems.log](C:/dev/openems/mini_ems_poc/logs/mini_ems.log)
Lokal (`config.local.json`): `logs/local/mini_ems.local.log`

Diese Datei ist die technische Referenzdatei. Sie ist bei Zeit-, Schalt- und Kommunikationsfragen wichtiger als GUI oder Excel, weil dort die echten App-Zeitstempel und Fehlerdetails stehen.

## Spotmarkt-Dateien

### `data/spotmarket/spotmarket_price_cache.json` (IPC) / `data/local/spotmarket_price_cache.json` (lokal)

Enthaelt:

- `today`
- `tomorrow`
- pro Tag 96 Slots
- `slots_by_label` fuer lesbare Uhrzeiten

### `data/spotmarket/spotmarket_tomorrow_windows.json` (IPC) / `data/local/spotmarket_tomorrow_windows.json` (lokal)

Enthaelt die erkannten negativen Preisfenster fuer `today` und `tomorrow`, jeweils mit Start, Ende, Laenge und Preisbereich. Diese Datei wird sowohl fuer Betrieb als auch fuer API und Dashboard genutzt.

## Datenbank

Die Laufzeitdatenbank ist:

- IPC (`config.json`): [mini_ems.sqlite](C:/dev/openems/mini_ems_poc/data/runtime/mini_ems.sqlite)
- Lokal (`config.local.json`): `data/local/mini_ems.local.sqlite`

Sie ist eine lokale SQLite-Datei. Mini-EMS schreibt dort bei jedem Zyklus Rohdaten hinein und erzeugt zusaetzlich Rollups fuer spaetere Reports.

### Wichtige Tabellen

- `cycle_runs`
  - ein Datensatz pro Zyklus
  - enthaelt Status, Slot, Preis, Grid-Power und den kompletten Snapshot als JSON
- `channel_samples`
  - Rohwerte pro Kanal und Zyklus
  - fuer Inputs und Outputs
- `price_slots`
  - Preis-Slots aus dem Cache
- `spotmarket_windows`
  - erkannte negative Fenster
- `bacnet_events`
  - Read- und Write-Fehler bzw. Kommunikationsereignisse
- `channel_rollups_5m`
- `channel_rollups_1h`
- `channel_rollups_1d`

Die Rollups werden aus den Rohdaten neu berechnet. Damit sind Wochen- und Tagesreports moeglich, ohne nur auf Minutenwerte zu schauen.

### Typischer Einsatz

- Live und Diagnose: `channel_samples`
- Wochenreport Temperatur: `channel_rollups_5m` oder `channel_rollups_1h`
- Tagesreport Betrieb: `cycle_runs`, `price_slots`, `spotmarket_windows`, `bacnet_events`

### Datenbank ansehen

Moegliche Wege:

- `DB Browser for SQLite`
- VS Code mit SQLite-Extension
- die lokale API unter `/api/history` und `/api/report/daily`

## HTTP-API und Dashboard

Wenn `api.enabled = true`, startet die Runtime einen HTTP-Server auf der in `api.host` konfigurierten Adresse.

Für reinen Lokalbetrieb bleibt `127.0.0.1` die sichere Wahl. Wenn Secomea oder ein anderes Remote-Tool zugreifen soll, binde die API an die konkrete EMS-LAN-IP, zum Beispiel `192.168.244.10`. Das ist sauberer und sicherer als `0.0.0.0`, weil der Dienst nur auf dem vorgesehenen Interface erreichbar ist.

Wer, welche Rolle und welcher Netzzugang UI, Konfiguration, Logs und Betriebsdaten sehen darf, sowie die Minimalvariante für ein erstes read-only Online-Hosting (Secomea/VPN vs. externer Hosting-Punkt, freizugebende und zu sperrende Endpunkte, Leitplanken) sind in [HOSTING_SICHERHEIT.md](./HOSTING_SICHERHEIT.md) beschrieben.

Wichtige Endpunkte:

- `/`
- `/dashboard`
  - einfaches Dashboard
- `/api/status`
  - `health.json`, `state.json`, Spotmarktplan und letzte Zyklen
- `/api/spotmarket/windows`
  - aktueller Spotmarktplan
- `/api/history?channel_id=site.outdoor_temperature_c`
  - Rohhistorie
- `/api/history?channel_id=site.outdoor_temperature_c&granularity=5m`
  - 5-Minuten-Rollup
- `/api/history?channel_id=site.outdoor_temperature_c&granularity=1h`
  - 1-Stunden-Rollup
- `/api/cycles?limit=20`
  - letzte Zyklen
- `/api/report/daily?date=2026-04-09`
  - Tagesreport als JSON
- `/api/report/daily.csv?date=2026-04-09`
  - Tagesreport als CSV
- `/api/diagnostics/read?channel_id=grid.active_power_kw&samples=3`
  - wiederholter Diagnose-Read

## Betrieb auf Windows

### Lokaler Einmallauf

```powershell
cd C:\dev\openems\mini_ems_poc
python mini_ems.py --once
```

### Lokaler Loop

```powershell
cd C:\dev\openems\mini_ems_poc
python mini_ems.py --loop
```

### Automatischer Hintergrundbetrieb

Der produktive Start erfolgt ueber die Aufgabenplanung, nicht ueber einen nativen Windows-Dienst.

Verwende dazu:

- [windows/install_task.ps1](C:/dev/openems/mini_ems_poc/windows/install_task.ps1)
- [run_mini_ems.cmd](C:/dev/openems/mini_ems_poc/run_mini_ems.cmd)

Wichtig:

- den Installer in einer PowerShell als Administrator ausfuehren
- der Task startet beim Systemstart
- `run_mini_ems.cmd` nutzt bevorzugt die projektlokale `.venv`
- wenn der Python-Prozess mit Fehlercode endet, startet der Wrapper ihn nach kurzer Pause neu

### Neustart nach Codeaenderungen

Codeaenderungen werden nicht automatisch in den laufenden Python-Prozess geladen. Nach Runtime-Aenderungen muss Mini-EMS neu gestartet werden, damit neuer Code, neue API-Endpunkte oder neue Konfigurationsfelder aktiv werden.

## Verhalten bei IPC-Ausfall

Wenn der IPC komplett aus geht:

- Mini-EMS stoppt sofort
- es gibt keine neuen Reads, Writes oder DB-Eintraege mehr
- die Controller laufen mit ihrer eigenen Logik weiter
- die zuletzt von Mini-EMS geschriebenen BACnet-Werte bleiben zunaechst auf dem letzten Stand

Wenn der IPC wieder hochfaehrt:

- der Scheduled Task startet Mini-EMS automatisch wieder
- der Runtime-Zustand wird aus `runtime/state.json` geladen
- der erste Zyklus bestaetigt die Outputs erneut

Wichtig:

- ein Preiswechsel waehrend des IPC-Ausfalls wird nicht geschrieben
- das System ist aktuell automatisch wiederanlaufend, aber nicht autonom weiterlaufend

## Aktueller Projektstand

### Funktioniert

1. SMARD-Abruf fuer Viertelstundenpreise
2. lokaler Cache fuer `today` und `tomorrow`
3. Preisuebergabe auf `AV:1000` mit `ack_or_readback`
4. BACnet-Read auf `AV:300`
5. BACnet-Read auf `AI:1801` des zweiten Controllers
6. Hintergrundbetrieb ueber Scheduled Task
7. lokale SQLite-Historie
8. lokale Read-only-API plus Dashboard
9. Spotmarktfenster aus echten Preisreihen
10. manueller Override fuer `BV:401`

### Beobachtungshinweise

Fuer den Betrieb sind diese drei Sichtweisen am wichtigsten (IPC-Pfade aus `config.json`;
lokal mit `config.local.json` liegen die gleichen Dateien unter `runtime/local/`, `logs/local/` und `data/local/`):

1. [health.json](C:/dev/openems/mini_ems_poc/runtime/health.json)
2. [mini_ems.log](C:/dev/openems/mini_ems_poc/logs/mini_ems.log)
3. [mini_ems.sqlite](C:/dev/openems/mini_ems_poc/data/runtime/mini_ems.sqlite)

### Offene Punkte

1. `BV:400` weiter fachlich verifizieren
2. Controller- und GUI-Zeitbasis sauber im Feld nachhalten
3. Watchdog fuer echten Betriebsalarm bei haengender Runtime: umgesetzt. Ist der letzte Zyklus- bzw.
   Healthy-Zeitstempel aelter als `watchdog.max_cycle_age_seconds`, meldet `health.json` den Status
   `stale_runtime` (Felder `stale_runtime`, `runtime_status`). Ohne konfigurierten Schwellwert bleibt der
   Watchdog rein beobachtend; der Watchdog meldet nur "kein Zyklus mehr" und loest keine Safe-Mode-/Steuerlogik aus.
4. UI spaeter weiter in Richtung OpenEMS-inspirierte Bedienoberflaeche ausbauen

## Meine aktuelle Empfehlung

Weiter in dieser Reihenfolge:

1. Runtime stabil betreiben und beobachten
2. Reports auf Basis der SQLite-Historie nutzen
3. `BV:400` im echten Betrieb absichern
4. danach UI und Betriebsoberflaeche ausbauen
