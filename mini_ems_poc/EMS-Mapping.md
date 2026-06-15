# EMS-Mapping

Zweck dieser Datei: Sie hält fest, wie OpenEMS Messgeräte und Protokolle grundsätzlich auf EMS-Kanäle abbildet, wie unser `mini_ems_poc` aktuell BACnet nutzt, und wie spätere Protokoll-Zubauten sauber erweitert werden sollen.

Wichtig: Das ist eine technische Arbeitskarte für das POC. Jede reale Aufschaltung an elektrischen Anlagen braucht Elektrofachkraft, Betreiberfreigabe, saubere OT-Netztrennung und zuerst einen reinen Lesebetrieb. Schreiben auf Anlagen oder Controller bleibt Human-Review-pflichtig.

## Kurzfazit

Ja, im großen OpenEMS-Projekt gibt es bereits viele Ordner und Programme, die genau die Aufgaben erfüllen, die wir für echte EMS-Messgeräte brauchen:

| Aufgabe | OpenEMS-Vorbild | Bedeutung für Mini EMS |
|---|---|---|
| Einheitliche Zählerkanäle | `io.openems.edge.meter.api/ElectricityMeter.java` | Definiert kanonische Kanäle wie Wirkleistung, Blindleistung, Spannung, Strom, Energie |
| Modbus TCP/RTU lesen und schreiben | `io.openems.edge.bridge.modbus/` | Wichtigstes Muster für Leistungsmessgeräte mit Registerliste |
| Modbus-Register auf EMS-Kanäle mappen | `AbstractOpenemsModbusComponent`, `ModbusProtocol`, `FC3ReadRegistersTask`, `FC4ReadInputRegistersTask` | Vorlage für `protocol -> raw value -> channel` |
| M-Bus-Zähler lesen | `io.openems.edge.bridge.mbus/`, `io.openems.edge.meter.abb/` | Vorlage für Zähler mit Primäradresse und Datensatz-Positionen |
| HTTP/REST-Geräte lesen | `io.openems.common.bridge.http/`, `io.openems.edge.io.shelly/`, `io.openems.edge.meter.discovergy/` | Vorlage für Shelly, Cloud/API-Zähler oder REST-Gateways |
| MQTT-Verbindung | `io.openems.edge.bridge.mqtt/` | Vorlage für spätere Broker-/Topic-basierte Geräte |
| BACnet ähnlich unserem POC | Kein fertiges Edge-BACnet-Bundle im Code gefunden | Unser POC ist hier aktuell die eigene BACnet-Implementierung |

## Grundmuster in OpenEMS

OpenEMS trennt drei Dinge sauber:

| Schicht | Was sie macht | Beispiel |
|---|---|---|
| Bridge | Stellt die technische Verbindung bereit | `Bridge.Modbus.Tcp`, `Bridge.Modbus.Serial`, `Bridge.Mbus`, `Bridge.Mqtt`, HTTP-Bridge |
| Geräte-Komponente | Kennt Register, API-Felder, Datenmodell und Skalierung eines konkreten Geräts | `Meter.Janitza.UMG96RME`, `Meter.Microcare.SDM630`, `IO.Shelly.Pro3EM` |
| Nature / kanonische Kanäle | Vereinheitlicht die Werte für Controller und Auswertung | `ElectricityMeter.ChannelId.ACTIVE_POWER`, `VOLTAGE_L1`, `CURRENT_L1` |

Das wichtigste Muster lautet:

```text
physisches Messgerät
-> Protokoll-Bridge
-> gerätespezifische Mapping-Komponente
-> kanonischer EMS-Kanal
-> Controller / Zeitreihe / UI / Report
```

Für Mini EMS sollten wir dieses Muster übernehmen:

```text
Wandlerspulen + Spannungsabgriff
-> Leistungsmessgerät
-> Protokolladapter im Mini EMS
-> interner Channel
-> CycleRunner / SQLite / Dashboard / Business OS
```

Die Wandlerspule selbst ist dabei kein Datenpunkt. Sie liefert dem Leistungsmessgerät ein Stromsignal. Erst das Messgerät berechnet daraus zusammen mit den Spannungen Werte wie `kW`, `kvar`, `V`, `A`, `kWh`.

## OpenEMS: Meter-API als Zielmodell

Die zentrale OpenEMS-Datei ist:

```text
io.openems.edge.meter.api/src/io/openems/edge/meter/api/ElectricityMeter.java
```

Relevante Kanäle:

| OpenEMS-Kanal | Einheit | Bedeutung |
|---|---:|---|
| `ACTIVE_POWER` | W | Wirkleistung gesamt |
| `ACTIVE_POWER_L1/L2/L3` | W | Wirkleistung je Phase |
| `REACTIVE_POWER` | var | Blindleistung gesamt |
| `REACTIVE_POWER_L1/L2/L3` | var | Blindleistung je Phase |
| `VOLTAGE`, `VOLTAGE_L1/L2/L3` | mV | Spannung |
| `CURRENT`, `CURRENT_L1/L2/L3` | mA | Strom |
| `FREQUENCY` | mHz | Frequenz |
| `ACTIVE_PRODUCTION_ENERGY` | Wh kumuliert | Erzeugungsenergie |
| `ACTIVE_CONSUMPTION_ENERGY` | Wh kumuliert | Verbrauchsenergie |

Wichtig ist die Vorzeichenlogik über `MeterType`:

| MeterType | Positive Wirkleistung | Negative Wirkleistung |
|---|---|---|
| `GRID` | Netzbezug | Einspeisung |
| `PRODUCTION` | Erzeugung | undefiniert |
| `PRODUCTION_AND_CONSUMPTION` | Erzeugung | Verbrauch |
| `CONSUMPTION_METERED` | Verbrauch | undefiniert |

Für Mini EMS heißt das: Wir sollten früh ein eigenes kanonisches Kanalmodell pflegen und Vorzeichen nicht pro Auswertung neu interpretieren.

Empfohlene Mini-EMS-Kanäle:

| Mini-EMS-Kanal | Einheit | Bedeutung |
|---|---:|---|
| `meter.grid.active_power_kw` | kW | Netzbezug positiv, Einspeisung negativ |
| `meter.grid.active_power_l1_kw` | kW | L1 |
| `meter.grid.active_power_l2_kw` | kW | L2 |
| `meter.grid.active_power_l3_kw` | kW | L3 |
| `meter.grid.reactive_power_kvar` | kvar | Blindleistung gesamt |
| `meter.grid.voltage_l1_v` | V | Spannung L1 |
| `meter.grid.current_l1_a` | A | Strom L1 |
| `meter.grid.consumed_energy_kwh` | kWh | Bezug kumuliert |
| `meter.grid.exported_energy_kwh` | kWh | Einspeisung kumuliert |

Der bestehende Kanal `grid.active_power_kw` kann bleiben. Neue Protokolle sollten aber Richtung `meter.grid.*` erweitert werden, damit später Hauptzähler, Unterzähler, PV, BHKW, Speicher und Verbraucher sauber unterscheidbar sind.

## OpenEMS: Modbus-Muster

Relevante Ordner:

```text
io.openems.edge.bridge.modbus/
io.openems.edge.meter.janitza/
io.openems.edge.meter.socomec/
io.openems.edge.meter.eastron/
io.openems.edge.meter.phoenixcontact/
io.openems.edge.meter.pqplus/
io.openems.edge.meter.carlo.gavazzi/
io.openems.edge.meter.siemens/
```

Die Modbus-Bridge gibt es in zwei Varianten:

| Bridge | Factory-ID | Typische Konfiguration |
|---|---|---|
| Modbus TCP | `Bridge.Modbus.Tcp` | IP-Adresse, Port |
| Modbus RTU Serial | `Bridge.Modbus.Serial` | serieller Port, Baudrate, Datenbits, Stopbits, Parität |

Eine konkrete Meter-Komponente bekommt zusätzlich:

| Feld | Bedeutung |
|---|---|
| `modbus.id` | ID der Bridge, z. B. `modbus0` |
| `modbusUnitId` | Unit-ID / Slave-ID des Messgeräts |
| `type` | Zählerrolle, z. B. `GRID` |
| `invert` | Vorzeichen drehen, wenn Einbaurichtung oder Messrichtung anders ist |

Technisches Mapping in OpenEMS:

```text
ModbusProtocol
-> FC3ReadRegistersTask oder FC4ReadInputRegistersTask
-> ModbusElement, z. B. FloatDoublewordElement / SignedDoublewordElement
-> ElementToChannelConverter, z. B. Skalierung oder Invertierung
-> ElectricityMeter.ChannelId
```

Beispiel Janitza UMG96RM-E:

```text
io.openems.edge.meter.janitza/.../MeterJanitzaUmg96rmeImpl.java
```

Das Gerät liest per `FC3ReadRegistersTask` ab Registerbereich `19000`. Auszüge:

| Register | OpenEMS-Kanal | Typ |
|---:|---|---|
| `19000` | `VOLTAGE_L1` | `FloatDoublewordElement` |
| `19012` | `CURRENT_L1` | `FloatDoublewordElement` |
| `19020` | `ACTIVE_POWER_L1` | `FloatDoublewordElement` |
| `19026` | `ACTIVE_POWER` | `FloatDoublewordElement` |
| `19036` | `REACTIVE_POWER_L1` | `FloatDoublewordElement` |
| `19042` | `REACTIVE_POWER` | `FloatDoublewordElement` |
| `19050` | `FREQUENCY` | `FloatDoublewordElement` |

Beispiel Eastron SDM630:

```text
io.openems.edge.meter.eastron/.../MeterEastronSdm630Impl.java
```

Das Gerät liest per `FC4ReadInputRegistersTask`, nutzt `FloatDoublewordElement`, setzt Byte-/Word-Order und kann Phasenrotation abbilden. Das ist wichtig, weil echte Zähler oft nicht einfach "Register lesen = richtiger Wert" sind. Man braucht:

| Thema | Warum wichtig |
|---|---|
| Function Code | Holding Register (`FC3`) oder Input Register (`FC4`) |
| Registeradresse | Herstellerangabe kann 0-basiert oder 1-basiert sein |
| Datentyp | `float32`, `int32`, `uint32`, `word`, Bits |
| Byte-/Word-Order | MSW/LSW, Big/Little Endian |
| Skalierung | z. B. W zu kW, mV zu V, A zu mA |
| Invertierung | Einbaurichtung / Bezug-Einspeisung |
| Phasenrotation | L1/L2/L3 können vertauscht sein |

Beispiel Socomec:

```text
io.openems.edge.meter.socomec/
```

Socomec zeigt ein zweites wichtiges Muster: Das System liest zuerst Kennungsregister, erkennt das konkrete Modell und fügt danach passende Register-Tasks hinzu. Das ist für Gerätefamilien nützlich, bei denen mehrere Modelle ähnlich, aber nicht identisch sind.

## OpenEMS: M-Bus-Muster

Relevante Ordner:

```text
io.openems.edge.bridge.mbus/
io.openems.edge.meter.abb/
```

M-Bus ist anders als Modbus. Es geht weniger um feste Registeradressen und mehr um Datensätze eines Zählers.

OpenEMS-Muster:

```text
Bridge.Mbus
-> serieller Port, Baudrate
-> Meter-Komponente mit PrimaryAddress
-> ChannelRecord-Liste
-> Datensatzposition oder Datentyp
-> OpenEMS-Kanal
```

Beispiel ABB B23:

```text
io.openems.edge.meter.abb/.../MeterAbbB23Impl.java
```

Die Komponente nutzt:

| Element | Bedeutung |
|---|---|
| `BridgeMbus` | M-Bus-Verbindung |
| `primaryAddress` | M-Bus-Adresse des Geräts |
| `MbusTask` | zyklische Abfrage |
| `ChannelRecord` | Zuordnung M-Bus-Datensatz zu OpenEMS-Kanal |

Hinweis: In `MeterAbbB23Impl.java` steht ein TODO, dass ein Teil des Mappings vermutlich falsch ist. Als Architekturvorbild ist die Datei trotzdem nützlich; konkrete Register-/Record-Zuordnung muss bei M-Bus immer gegen die reale Zählerausgabe geprüft werden.

## OpenEMS: HTTP-/REST-Muster

Relevante Ordner:

```text
io.openems.common.bridge.http/
io.openems.edge.bridge.http/
io.openems.edge.io.shelly/
io.openems.edge.meter.discovergy/
```

Beispiel Shelly Pro 3EM:

```text
io.openems.edge.io.shelly/.../IoShellyPro3EmImpl.java
```

Das Gerät wird per HTTP abgefragt:

```text
http://<ip>/rpc/EM.GetStatus?id=0
```

Dann werden JSON-Felder auf OpenEMS-Kanäle gesetzt:

| JSON-Feld | OpenEMS-Kanal |
|---|---|
| `total_act_power` | `ACTIVE_POWER` |
| `a_act_power` | `ACTIVE_POWER_L1` |
| `b_act_power` | `ACTIVE_POWER_L2` |
| `c_act_power` | `ACTIVE_POWER_L3` |
| `a_voltage` | `VOLTAGE_L1` |
| `a_current` | `CURRENT_L1` |

Beispiel Discovergy:

```text
io.openems.edge.meter.discovergy/
```

Discovergy ist API-/Cloud-orientiert. Der Worker ruft letzte Messwerte ab, prüft, ob die Messung zu alt ist, und mappt Felder wie `POWER`, `POWER1`, `VOLTAGE1`, `ENERGY` auf `ElectricityMeter`-Kanäle.

Für Mini EMS heißt das: HTTP/REST-Geräte brauchen keinen Register-Parser, sondern:

```text
URL
-> JSON-Feldpfad
-> Plausibilität / Aktualität
-> kanonischer Channel
```

## OpenEMS: MQTT-Muster

Relevanter Ordner:

```text
io.openems.edge.bridge.mqtt/
```

OpenEMS hat eine MQTT-Bridge:

| Element | Aufgabe |
|---|---|
| `Bridge.Mqtt` | Verbindung zum MQTT-Broker |
| `publish(...)` | Werte senden |
| `subscribe(...)` | Topics abonnieren |
| `MqttComponent` | Marker für Komponenten mit MQTT-Kommunikation |

Für Mini EMS wäre MQTT sinnvoll, wenn ein Gateway oder Datenlogger Werte als Topics bereitstellt, z. B.:

```text
site/main_meter/active_power_w
site/main_meter/voltage_l1_v
site/main_meter/current_l1_a
```

Dann braucht der POC eine Topic-zu-Channel-Tabelle.

## BACnet in unserem Mini EMS

OpenEMS selbst hat in diesem Checkout keine fertige native BACnet-Edge-Bridge wie `Bridge.Modbus.Tcp` oder `Bridge.Mbus`. Unser POC implementiert BACnet daher selbst.

Relevante POC-Dateien:

```text
mini_ems_poc/config.json
mini_ems_poc/config.local.json
mini_ems_poc/mini_ems_runtime/config.py
mini_ems_poc/mini_ems_runtime/channels.py
mini_ems_poc/mini_ems_runtime/bacnet.py
mini_ems_poc/mini_ems_runtime/simulation.py
mini_ems_poc/mini_ems_runtime/cycle.py
```

Aktuelle BACnet-Kette:

```text
config.json
-> PointsConfig / AdditionalInputConfig
-> ChannelRegistry
-> PointConfig
-> BacnetAdapter
-> CycleRunner
-> StateStore + RuntimeDatabase + Dashboard
```

Aktuelle Kernpunkte:

| Mini-EMS-Kanal | BACnet-Objekt | Instanz | Zugriff | Bedeutung |
|---|---|---:|---|---|
| `grid.active_power_kw` | `AV` | `300` | read | Netzleistung in kW |
| `tariff.current_price_ct_kwh` | `AV` | `1000` | readwrite | aktueller Spotpreis in ct/kWh |
| `ems.lockout_grid` | `BV` | `400` | write | Lastsperre wegen Netzleistung |
| `ems.lockout_spotmarket` | `BV` | `401` | write | Sperre/Freigabe wegen Spotmarktfenster |

Aktuelle zusätzliche Eingänge aus `additional_inputs`:

| Beispiel-Kanal | BACnet-Objekt | Instanz | Bemerkung |
|---|---|---:|---|
| `site.outdoor_temperature_c` | `AI` | `1801` | kann auf anderem Controller liegen |
| `site.buffer_1_top_temperature_c` | `AI` | `1101` | Puffer oben |
| `site.chp_electric_energy_kwh` | `AV` | `48` | BHKW elektrische Energie |
| `site.gas_thermal_energy_kwh` | `AV` | `51` | Gaskessel thermische Energie |

Was der `BacnetAdapter` technisch macht:

| Funktion | Umsetzung |
|---|---|
| Lesen | `ReadProperty` auf `presentValue` |
| Schreiben AV | `WriteProperty` auf `presentValue`, Float, Priorität `14` |
| Schreiben BV | `WriteProperty` auf `presentValue`, Boolean, Priorität `14` |
| Zielgerät | pro Punkt `controller_ip/controller_port` oder Default aus `network` |
| Absicherung | `can_read()`, `can_write()`, ACK-Prüfung, optional Readback |
| Simulation | `SimulatedBacnetAdapter` liest aus `sim/sample_values.json` und speichert Writes nur intern |

Wichtiges Sicherheitsmuster:

| Umgebung | BACnet-Modus | echte Writes |
|---|---|---|
| `local` | `simulated` | nein |
| `ipc` | `real` | ja, nur mit realer IPC-Konfiguration |

Diese Regel steht in `mini_ems_runtime/config.py`: Lokale Entwicklung darf nicht mit echtem BACnet starten.

## Vergleich: OpenEMS vs. Mini EMS

| Thema | OpenEMS | Mini EMS aktuell | Ziel für Mini EMS |
|---|---|---|---|
| Datenpunktmodell | `Component-ID/Channel-ID` | freie `channel_id` Strings | beibehalten, aber stärker standardisieren |
| Geräteabstraktion | Component + Nature | `PointConfig` + Adapter | `DeviceConfig` + `PointConfig` + Adapter |
| Protokoll | Bridge-Bundles | nur BACnet real/simuliert | BACnet + Modbus + HTTP/MQTT schrittweise |
| Zählermodell | `ElectricityMeter` | `grid.active_power_kw` plus Zusatzpunkte | eigenes `meter.*` Modell nahe an `ElectricityMeter` |
| Mapping | Register/API-Feld -> Channel | BACnet-Objekt -> Channel | generisches Mapping je Protokoll |
| Simulation | Dummy-/Testkomponenten | `SimulatedBacnetAdapter` | pro Protokoll Simulation oder ein gemeinsamer SimAdapter |

## Erweiterungsmuster für neue Protokolle

Neue Protokolle sollten nicht direkt in `CycleRunner` eingebaut werden. Besser:

```text
config
-> DeviceConfig
-> PointConfig
-> passender ProtocolAdapter
-> gleicher CycleRunner
```

Minimaler Adapter-Vertrag:

```text
read_float(point) -> float
write_with_confirmation(point, desired_value, confirmation_mode) -> WriteConfirmation
close()
```

Für reine Messgeräte reicht zuerst nur:

```text
read_float(point) -> float
close()
```

Die bestehende Klasse heißt noch `BacnetAdapter`. Für den nächsten Zubau wäre sinnvoll:

| Schritt | Änderung |
|---|---|
| 1 | Adapter-Vertrag sprachlich neutralisieren: `BacnetWriteConfirmation` später zu `WriteConfirmation` |
| 2 | `PointConfig` um `protocol`, `device_id`, `address`, `data_type`, `scale`, `offset`, `invert`, `unit` erweitern |
| 3 | `BacnetAdapter` als ein konkreter Adapter behalten |
| 4 | `ModbusAdapter` ergänzen, zuerst read-only |
| 5 | `CycleRunner` nur gegen den neutralen Adapter-Vertrag laufen lassen |

## Mapping-Vorlage: BACnet

```json
{
  "channel_id": "grid.active_power_kw",
  "protocol": "bacnet",
  "device_id": "ebcon_1",
  "object_type": "av",
  "instance": 300,
  "property": "presentValue",
  "access": "read",
  "unit": "kW",
  "scale": 1.0,
  "plausible_min": -1000000.0,
  "plausible_max": 1000000.0
}
```

Für Schreibpunkte zusätzlich:

```json
{
  "channel_id": "ems.lockout_spotmarket",
  "protocol": "bacnet",
  "device_id": "ebcon_1",
  "object_type": "bv",
  "instance": 401,
  "property": "presentValue",
  "access": "write",
  "write_priority": 14,
  "confirmation_mode": "ack_only",
  "criticality": "critical"
}
```

## Mapping-Vorlage: Modbus-Leistungsmessgerät

```json
{
  "channel_id": "meter.grid.active_power_kw",
  "protocol": "modbus_tcp",
  "device_id": "main_meter",
  "function_code": 3,
  "register": 19026,
  "data_type": "float32",
  "word_order": "msw_lsw",
  "byte_order": "big_endian",
  "scale": 0.001,
  "offset": 0.0,
  "invert": false,
  "access": "read",
  "unit": "kW",
  "meter_type": "grid",
  "plausible_min": -10000.0,
  "plausible_max": 10000.0
}
```

Für ein Modbus-Gerät braucht die Geräte-Konfiguration:

```json
{
  "device_id": "main_meter",
  "protocol": "modbus_tcp",
  "ip": "192.168.244.60",
  "port": 502,
  "unit_id": 1,
  "timeout_seconds": 2.0,
  "retries": 1
}
```

Für Modbus RTU:

```json
{
  "device_id": "main_meter",
  "protocol": "modbus_rtu",
  "port_name": "/dev/ttyUSB0",
  "baudrate": 9600,
  "databits": 8,
  "parity": "none",
  "stopbits": 1,
  "unit_id": 1
}
```

## Mapping-Vorlage: M-Bus-Zähler

```json
{
  "channel_id": "meter.submeter.consumed_energy_kwh",
  "protocol": "mbus",
  "device_id": "heat_or_energy_meter_1",
  "primary_address": 12,
  "record_index": 0,
  "data_type": "energy",
  "scale": 1.0,
  "access": "read",
  "unit": "kWh"
}
```

Geräte-Konfiguration:

```json
{
  "device_id": "heat_or_energy_meter_1",
  "protocol": "mbus",
  "port_name": "/dev/ttyUSB0",
  "baudrate": 2400,
  "primary_address": 12
}
```

## Mapping-Vorlage: HTTP/REST-Gerät

```json
{
  "channel_id": "meter.grid.active_power_kw",
  "protocol": "http_json",
  "device_id": "shelly_pro_3em",
  "url": "http://192.168.244.61/rpc/EM.GetStatus?id=0",
  "json_path": "total_act_power",
  "scale": 0.001,
  "invert": false,
  "access": "read",
  "unit": "kW",
  "max_age_seconds": 30
}
```

## Mapping-Vorlage: MQTT

```json
{
  "channel_id": "meter.grid.active_power_kw",
  "protocol": "mqtt",
  "device_id": "main_meter_gateway",
  "topic": "site/main_meter/active_power_w",
  "payload_type": "number",
  "scale": 0.001,
  "invert": false,
  "access": "read",
  "unit": "kW",
  "max_age_seconds": 30
}
```

MQTT-Geräte-Konfiguration:

```json
{
  "device_id": "main_meter_gateway",
  "protocol": "mqtt",
  "host": "192.168.244.70",
  "port": 1883,
  "client_id": "mini-ems",
  "use_tls": false
}
```

## Was man für eine reale Aufschaltung braucht

| Bereich | Benötigt |
|---|---|
| Elektro | Einbauort, Stromwandlerverhältnis, Spannungsabgriff, Absicherung, Phasenlage, Messrichtung |
| Messgerät | Hersteller, Modell, Genauigkeit, CT/VT-Konfiguration, Register-/Objektliste |
| Kommunikation | Modbus TCP/RTU, BACnet, M-Bus, HTTP oder MQTT; IP/Port oder serieller Bus |
| Datenmodell | Kanalname, Einheit, Skalierung, Datentyp, Vorzeichen, Plausibilitätsgrenzen |
| Betrieb | Aktualitätsprüfung, Heartbeat, Fehlerzustand, Logging, Zeitreihe |
| Sicherheit | Read-only Start, getrenntes Netz, keine Schreibrechte ohne Freigabe |
| Abnahme | Messwert gegen Display, Zähler, Rechnung oder Lastgang plausibilisieren |

## Zubau-Checkliste

Vor jedem neuen Protokoll oder Messgerät:

1. Gerätetyp klären: Hauptzähler, Unterzähler, PV, BHKW, Speicher, Ladepunkt, HVAC.
2. Physische Messung klären: Direktmessung oder Stromwandler, CT-Verhältnis, Spannungspfad.
3. Protokoll klären: BACnet, Modbus TCP, Modbus RTU, M-Bus, HTTP, MQTT.
4. Herstellerdaten holen: Registerliste, BACnet-Objektliste, API-Felder oder Topic-Liste.
5. Mapping-Tabelle schreiben, bevor Code geschrieben wird.
6. Nur read-only implementieren.
7. Simulation ergänzen.
8. Einen Test mit Fake-Antwort oder Beispieldaten schreiben.
9. Eine Plausibilitätsprüfung definieren.
10. Erst danach überlegen, ob ein Schreibpfad überhaupt nötig ist.

## Entscheidungsregel für Mini EMS

| Situation | Empfehlung |
|---|---|
| Werte liegen schon sauber im Delta/eBCON als BACnet-Punkte | BACnet weiter nutzen |
| Neues Leistungsmessgerät mit Modbus TCP verfügbar | Modbus-TCP-Adapter bauen, read-only starten |
| Serielles Schaltschrankgerät mit RS-485 | Modbus RTU über USB/RS-485 oder Gateway |
| Klassischer Zähler mit M-Bus | M-Bus nur für Energie-/Zählerwerte, nicht für schnelle Regelung |
| Shelly/IoT-Gerät | HTTP/REST oder MQTT, eher Monitoring als kritische Steuerung |
| Cloud-Zähler/API | Nur Reporting/Monitoring, nicht für schnelle lokale Steuerung |

## Konkreter nächster sinnvoller POC-Schritt

Der nächste technische Schritt sollte ein read-only Modbus-Meter-Adapter sein:

```text
Modbus TCP Leistungsmessgerät
-> register_map in JSON
-> ModbusAdapter.read_float()
-> meter.grid.active_power_kw
-> SQLite / Dashboard / Business OS
```

Kein Schreibpfad. Kein aktives Lastmanagement. Erst echte Messwerte stabil lesen, plausibilisieren und historisieren.

Beste OpenEMS-Vorbilder dafür:

| Zweck | Datei |
|---|---|
| Modbus-Bridges | `io.openems.edge.bridge.modbus/src/io/openems/edge/bridge/modbus/BridgeModbusTcpImpl.java` und `BridgeModbusSerialImpl.java` |
| Register-zu-Channel-Mapping | `io.openems.edge.bridge.modbus/src/io/openems/edge/bridge/modbus/api/AbstractOpenemsModbusComponent.java` |
| Modbus-Aufgaben | `io.openems.edge.bridge.modbus/src/io/openems/edge/bridge/modbus/api/task/FC3ReadRegistersTask.java` und `FC4ReadInputRegistersTask.java` |
| Janitza-Beispiel | `io.openems.edge.meter.janitza/src/io/openems/edge/meter/janitza/umg96rme/MeterJanitzaUmg96rmeImpl.java` |
| Eastron-Beispiel | `io.openems.edge.meter.eastron/src/io/openems/edge/meter/eastron/sdm630/MeterEastronSdm630Impl.java` |
| Shelly-HTTP-Beispiel | `io.openems.edge.io.shelly/src/io/openems/edge/io/shelly/shellypro3em/IoShellyPro3EmImpl.java` |
| M-Bus-Beispiel | `io.openems.edge.bridge.mbus/` und `io.openems.edge.meter.abb/` |

## Merksatz

Ein neues Protokoll darf im Mini EMS nicht als Spezialfall in die Regelung wandern. Es soll immer nur Rohkommunikation in saubere Kanäle übersetzen. Die Regelung liest danach nur noch Kanäle.
