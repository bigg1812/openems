# Mini EMS PoC – Mini-Edge-Architektur, Inbetriebnahme und Testprotokoll

## Ziel

Dieses PoC baut **kein OpenEMS nach**.
Es uebernimmt aber die wichtigsten OpenEMS-Prinzipien in einer kleinen Python-Edge:

- klare `Channels`
- getrennte `Controller`
- zyklischer Ablauf `read -> validate -> decide -> write`
- persistenter Runtime-State
- Health- und Log-Artefakte
- konservatives Fail-safe-Verhalten

Der fachliche Scope bleibt absichtlich klein:

- ein Delta Controls Controller
- BACnet Read auf Netzleistung und 24 Stundenpreise
- BACnet Write nur auf `BV:400` und `BV:401`

Damit beweist das System zweierlei:

1. Ein uebergeordnetes BEMS kann auf dem IPC laufen.
2. Es kann in einer echten Liegenschaft sicher begrenzt Daten aus dem GA-Controller lesen und wieder hineinschreiben.

## Architektur

### Komponenten

`mini_ems.py`
- duennes CLI-Entrypoint
- startet einen Zyklus oder Dauerbetrieb

`config.json`
- einzige Stelle fuer IPs, AV/BV-Mapping, Zykluszeit, Schwellenwerte und Safety-Defaults

`mini_ems_runtime/channels.py`
- feste interne Channel-IDs
- Mapping von Channel-ID auf BACnet-Objekt

`mini_ems_runtime/bacnet.py`
- einziger BACnet-Layer
- UDP-Socket, Allowlist, Timeout, Retry, ACK-Pruefung, Absenderpruefung

`mini_ems_runtime/controllers.py`
- reine Entscheidungslogik
- keine direkte BACnet-Kommunikation

`mini_ems_runtime/cycle.py`
- orchestriert den festen Ablauf eines Zyklus
- erzwingt Fail-safe-Modus

`mini_ems_runtime/state_store.py`
- persistiert `state.json`
- schreibt `health.json`

`tests/`
- Unit-Tests fuer Controller
- Runtime-Tests mit Fake-BACnet-Socket

### Wichtige interne Channels

- `grid.active_power_kw`
- `tariff.price_hour_00` bis `tariff.price_hour_23`
- `ems.lockout_grid`
- `ems.lockout_spotmarket`
- `system.health`

### OpenEMS-Bezug

Die Naehe zu OpenEMS liegt im Denkmodell:

- BACnet-Objekte werden intern als standardisierte Channels behandelt
- Entscheidungen liegen in separaten Controllern
- der Zyklus ist deterministisch
- lokaler Zustand wird persistiert
- Outputs gelten erst nach bestaetigtem Write als bestaetigt

Nicht uebernommen werden:

- OSGi
- Backend/UI
- allgemeine Herstellerabdeckung
- breites Komponentenmodell

## Dateistruktur

```text
mini_ems_poc/
├── config.json
├── mini_ems.py
├── MINI_EMS_ANLEITUNG.md
├── mini_ems_runtime/
│   ├── app.py
│   ├── bacnet.py
│   ├── channels.py
│   ├── config.py
│   ├── controllers.py
│   ├── cycle.py
│   ├── logging_utils.py
│   └── state_store.py
├── tests/
│   ├── test_controllers.py
│   └── test_runtime.py
└── windows/
    └── install_service.ps1
```

## Konfiguration

Passe zuerst `config.json` an.

### Netzwerk

```json
"network": {
  "controller_ip": "192.168.1.100",
  "controller_port": 47808,
  "local_ip": "192.168.1.50",
  "local_port": 47809,
  "response_timeout_seconds": 2.0,
  "retries": 1
}
```

### BACnet-Punkte

```json
"points": {
  "grid_active_power_kw": 300,
  "spot_price_start_hour_instance": 1001,
  "grid_lockout_bv": 400,
  "spotmarket_lockout_bv": 401
}
```

### Regler

```json
"controllers": {
  "grid_lockout": {
    "threshold_kw": 5.0,
    "clear_threshold_kw": 5.5,
    "below_threshold_cycles_required": 3
  },
  "spotmarket_lockout": {
    "negative_hours_min_consecutive": 4,
    "min_valid_hours": 24,
    "invalid_price_sentinel": null
  }
}
```

Wichtig:

- Preise werden als **24 Stundenwerte** behandelt.
- `negative_hours_min_consecutive = 4` bedeutet vier zusammenhaengende negative Stunden.
- `-0.2` gilt als echter negativer Preis.
- Nur wenn dein Controller einen echten Fehlerwert wie `-1.0` liefert, setzt du `invalid_price_sentinel` explizit darauf.

## Laufzeitverhalten

Jeder Zyklus laeuft in fester Reihenfolge:

1. `read`
2. `validate`
3. `decide`
4. `write`
5. `persist`
6. `heartbeat`

### Grid-Lockout

- liest `grid.active_power_kw`
- zaehlt Zyklen unterhalb `threshold_kw`
- aktiviert Sperre erst nach `below_threshold_cycles_required`
- hebt aktive Sperre erst oberhalb `clear_threshold_kw` wieder auf

### Spotmarket-Lockout

- liest 24 Stundenpreise
- validiert die Reihe
- sucht den laengsten negativen Block
- setzt Sperre nur, wenn der Block lang genug ist

### Safety Gate

In den Safe-Mode geht das System bei:

- fehlenden Inputs
- unvollstaendiger Preisreihe
- BACnet-ACK-Fehlern
- Kommunikationsstoerungen

Im Safe-Mode:

- werden nur die zwei erlaubten Outputs geschrieben
- wird aktiv `OFF/OFF` angefahren
- bleiben Ausgaenge lokal unbestaetigt, wenn der Safe-Write fehlschlaegt
- bleibt das System im Safe-Mode, bis wieder ein gesunder Zyklus erfolgreich war

## Artefakte

### `logs/mini_ems.log`

- JSON-Logzeilen
- pro Zyklus Status, Entscheidungen und Write-Ergebnisse

### `state.json`

- persistierter Controller- und Output-State
- ueberlebt Neustarts

### `health.json`

- aktueller Health-Snapshot fuer Betrieb und BA-Nachweis
- enthaelt Safe-Mode-Status, letzte erfolgreiche Zyklen und Output-Status

## Lokaler Start

Einmaliger Testlauf:

```cmd
cd C:\mini-ems
python mini_ems.py --once
```

Dauerbetrieb:

```cmd
cd C:\mini-ems
python mini_ems.py --loop
```

## Windows-Dienst

Das Skript `windows/install_service.ps1` richtet einen einfachen Windows-Dienst ein:

- Autostart
- Neustart bei Crash
- Dienstkonto `LocalService`
- Firewall-Regeln nur fuer den BACnet-Pfad IPC <-> Controller

Beispiel:

```powershell
cd C:\mini-ems\windows
PowerShell -ExecutionPolicy Bypass -File .\install_service.ps1 `
  -ServiceName MiniEmsPoC `
  -PythonPath C:\Python39\python.exe `
  -ProjectDir C:\mini-ems
```

Danach:

```powershell
Start-Service MiniEmsPoC
Get-Service MiniEmsPoC
```

## Testprotokoll fuer die Bachelorarbeit

### A. Normalstart

- `python mini_ems.py --once`
- pruefen, dass `health.json` geschrieben wird
- pruefen, dass keine fremden BVs geschrieben werden

### B. Grid-Lockout

Voraussetzung:

- `AV:300` ist ein Testwert
- `BV:400` ist angelegt

Test:

1. `AV:300` auf `3.0` setzen
2. `python mini_ems.py --once` drei Mal ausfuehren
3. nach dem dritten Lauf muss `BV:400 = Active` sein
4. `AV:300` auf `6.0` setzen
5. `python mini_ems.py --once`
6. `BV:400` muss wieder `Inactive` sein

Wichtig:

- der Zaehler lebt jetzt nicht mehr nur im RAM
- er wird in `state.json` persistiert

### C. Spotmarket-Lockout

Voraussetzung:

- `BV:401` ist angelegt

Test:

1. `AV:1001` bis `AV:1004` auf negative Werte setzen, z. B. `-0.2`, `-0.5`, `-1.1`, `-0.3`
2. `python mini_ems.py --once`
3. `BV:401` muss `Active` sein

### D. Kommunikationsfehler

Test:

1. Controller-IP in `config.json` absichtlich falsch setzen oder Controller kurz trennen
2. `python mini_ems.py --once`
3. `health.json` muss `safe_mode_active = true` zeigen
4. beide Outputs muessen auf `OFF/OFF` fallen oder als nicht bestaetigt markiert bleiben, wenn Safe-Write selbst scheitert

### E. Prozessneustart

Test:

1. zwei Grid-Zyklen unter Schwelle fahren
2. Prozess beenden
3. erneut starten
4. dritter Zyklus muss den persistierten Zaehler weiterverwenden

## Erwarteter Nachweis

Wenn die Tests erfolgreich sind, ist gezeigt:

1. Python auf dem IPC kann BACnet-Objekte lesen.
2. Die Entscheidungslogik ist getrennt von der Kommunikation.
3. Das System schreibt nur die zwei explizit erlaubten Outputs.
4. Outputs gelten erst nach bestaetigtem Write als lokal bestaetigt.
5. Kommunikationsfehler fuehren in einen konservativen Safe-Mode.
6. Das PoC ist technisch naeher an einer OpenEMS-artigen Edge-Logik als ein einzelnes Skript.
