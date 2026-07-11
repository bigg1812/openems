from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .channels import (
    CURRENT_PRICE_CHANNEL,
    GRID_ACTIVE_POWER_CHANNEL,
    GRID_LOCKOUT_CHANNEL,
    SPOTMARKET_LOCKOUT_CHANNEL,
)


@dataclass(frozen=True)
class MappingDevice:
    id: str
    name: str
    protocol: str
    host: str
    port: int


@dataclass(frozen=True)
class RawPoint:
    id: str
    device_id: str
    object_type: str
    instance: int
    name: str
    unit: str


@dataclass(frozen=True)
class ChannelMapping:
    channel_id: str
    source_point_id: str
    label: str
    access: str
    scale: float
    offset: float
    invert: bool
    plausible_min: Optional[float]
    plausible_max: Optional[float]
    max_age_seconds: Optional[float]
    read_interval_cycles: int
    include_in_health: bool


CORE_CHANNELS = {
    GRID_ACTIVE_POWER_CHANNEL,
    CURRENT_PRICE_CHANNEL,
    GRID_LOCKOUT_CHANNEL,
    SPOTMARKET_LOCKOUT_CHANNEL,
}

CORE_CHANNEL_POINT_KEYS = {
    GRID_ACTIVE_POWER_CHANNEL: "grid_active_power_kw",
    CURRENT_PRICE_CHANNEL: "current_price_av",
    GRID_LOCKOUT_CHANNEL: "grid_lockout_bv",
    SPOTMARKET_LOCKOUT_CHANNEL: "spotmarket_lockout_bv",
}

CORE_CHANNEL_OBJECT_TYPES = {
    GRID_ACTIVE_POWER_CHANNEL: "av",
    CURRENT_PRICE_CHANNEL: "av",
    GRID_LOCKOUT_CHANNEL: "bv",
    SPOTMARKET_LOCKOUT_CHANNEL: "bv",
}


def build_mapping_config_patch(payload: Dict[str, object]) -> Dict[str, object]:
    """Validate a human-oriented mapping draft and build a runtime config patch."""
    try:
        draft, errors, warnings = _parse_mapping_draft(payload)
    except (TypeError, ValueError) as error:
        return _result(False, [str(error)], [], {})
    if errors:
        return _result(False, errors, warnings, {})

    devices, raw_points, mappings = draft
    patch_errors, patch_warnings, patch = _build_patch(devices, raw_points, mappings)
    return _result(not patch_errors, patch_errors, warnings + patch_warnings, patch)


def _parse_mapping_draft(
    payload: Dict[str, object],
) -> Tuple[
    Optional[Tuple[Dict[str, MappingDevice], Dict[str, RawPoint], List[ChannelMapping]]],
    List[str],
    List[str],
]:
    if not isinstance(payload, dict):
        return None, ["Der Zuordnungsentwurf ist ungültig."], []

    errors: List[str] = []
    warnings: List[str] = []
    devices = _parse_devices(payload.get("devices"), errors)
    raw_points = _parse_raw_points(payload.get("raw_points"), devices, errors)
    mappings = _parse_mappings(payload.get("mappings"), raw_points, errors, warnings)
    if errors:
        return None, errors, warnings
    return (devices, raw_points, mappings), errors, warnings


def _parse_devices(raw: object, errors: List[str]) -> Dict[str, MappingDevice]:
    if not isinstance(raw, list) or not raw:
        errors.append("Bitte mindestens ein Gerät angeben.")
        return {}

    devices: Dict[str, MappingDevice] = {}
    for index, entry in enumerate(raw):
        if not isinstance(entry, dict):
            errors.append("Gerät {0} ist unvollständig.".format(index + 1))
            continue
        device_id = _required_text(entry, "id", "Gerät {0}".format(index + 1), errors)
        if not device_id:
            continue
        if device_id in devices:
            errors.append("Das Gerät „{0}“ ist doppelt vorhanden.".format(device_id))
            continue
        protocol = _text(entry.get("protocol"), "bacnet").lower()
        if protocol != "bacnet":
            errors.append("Das Gerät „{0}“ nutzt ein noch nicht unterstütztes Protokoll: {1}.".format(device_id, protocol))
        host = _required_text(entry, "host", "Gerät „{0}“".format(device_id), errors)
        port = _integer(entry.get("port"), 47808)
        if port <= 0 or port > 65535:
            errors.append("Beim Gerät „{0}“ muss der Port zwischen 1 und 65535 liegen.".format(device_id))
        devices[device_id] = MappingDevice(
            id=device_id,
            name=_text(entry.get("name"), device_id),
            protocol=protocol,
            host=host,
            port=port,
        )
    return devices


def _parse_raw_points(
    raw: object,
    devices: Dict[str, MappingDevice],
    errors: List[str],
) -> Dict[str, RawPoint]:
    if not isinstance(raw, list) or not raw:
        errors.append("Bitte mindestens einen Datenpunkt angeben.")
        return {}

    raw_points: Dict[str, RawPoint] = {}
    for index, entry in enumerate(raw):
        if not isinstance(entry, dict):
            errors.append("Datenpunkt {0} ist unvollständig.".format(index + 1))
            continue
        point_id = _required_text(entry, "id", "Datenpunkt {0}".format(index + 1), errors)
        if not point_id:
            continue
        if point_id in raw_points:
            errors.append("Der Datenpunkt „{0}“ ist doppelt vorhanden.".format(point_id))
            continue
        device_id = _required_text(entry, "device_id", "Datenpunkt „{0}“".format(point_id), errors)
        if device_id and device_id not in devices:
            errors.append("Der Datenpunkt „{0}“ verweist auf ein unbekanntes Gerät: {1}.".format(point_id, device_id))
        object_type = _bacnet_object_type(entry.get("object_type"))
        if object_type is None:
            errors.append("Beim Datenpunkt „{0}“ wird der BACnet-Objekttyp noch nicht unterstützt.".format(point_id))
            object_type = "ai"
        instance = _integer(entry.get("instance"), -1)
        if instance < 0:
            errors.append("Beim Datenpunkt „{0}“ fehlt eine gültige BACnet-Instanz.".format(point_id))
        raw_points[point_id] = RawPoint(
            id=point_id,
            device_id=device_id,
            object_type=object_type,
            instance=instance,
            name=_text(entry.get("name"), point_id),
            unit=_text(entry.get("unit"), ""),
        )
    return raw_points


def _parse_mappings(
    raw: object,
    raw_points: Dict[str, RawPoint],
    errors: List[str],
    warnings: List[str],
) -> List[ChannelMapping]:
    if not isinstance(raw, list) or not raw:
        errors.append("Bitte mindestens einen Datenpunkt fachlich zuordnen.")
        return []

    mappings: List[ChannelMapping] = []
    channel_ids: set[str] = set()
    source_ids: set[str] = set()
    for index, entry in enumerate(raw):
        if not isinstance(entry, dict):
            errors.append("Zuordnung {0} ist unvollständig.".format(index + 1))
            continue
        channel_id = _required_text(entry, "channel_id", "Zuordnung {0}".format(index + 1), errors)
        if not channel_id:
            continue
        label = _text(entry.get("label"), channel_id)
        if channel_id in channel_ids:
            errors.append("Die Bedeutung „{0}“ ist mehrfach zugeordnet. Bitte nur einen Datenpunkt auswählen.".format(label))
            continue
        channel_ids.add(channel_id)
        source_point_id = _required_text(entry, "source_point_id", "Zuordnung „{0}“".format(label), errors)
        if source_point_id and source_point_id not in raw_points:
            errors.append("Für „{0}“ wurde ein unbekannter Datenpunkt gewählt: {1}.".format(label, source_point_id))
        if source_point_id in source_ids:
            warnings.append("Der Datenpunkt „{0}“ wird mehrfach verwendet.".format(source_point_id))
        source_ids.add(source_point_id)
        access = _text(entry.get("access"), "read").lower()
        if access not in ("read", "write", "readwrite"):
            errors.append("Bei „{0}“ ist die Zugriffsart ungültig.".format(label))
        plausible_min = _optional_float(entry.get("plausible_min"))
        plausible_max = _optional_float(entry.get("plausible_max"))
        if plausible_min is not None and plausible_max is not None and plausible_min > plausible_max:
            errors.append("Bei „{0}“ ist der kleinste plausible Wert größer als der größte.".format(label))
        max_age_seconds = _optional_float(entry.get("max_age_seconds"))
        if max_age_seconds is not None and max_age_seconds <= 0:
            errors.append("Bei „{0}“ muss das maximale Alter größer als 0 Sekunden sein.".format(label))
        read_interval_cycles = _integer(entry.get("read_interval_cycles"), 1)
        if read_interval_cycles <= 0:
            errors.append("Bei „{0}“ muss das Abfrageintervall größer als 0 sein.".format(label))
        mappings.append(ChannelMapping(
            channel_id=channel_id,
            source_point_id=source_point_id,
            label=label,
            access=access,
            scale=_float(entry.get("scale"), 1.0),
            offset=_float(entry.get("offset"), 0.0),
            invert=bool(entry.get("invert", False)),
            plausible_min=plausible_min,
            plausible_max=plausible_max,
            max_age_seconds=max_age_seconds,
            read_interval_cycles=read_interval_cycles,
            include_in_health=bool(entry.get("include_in_health", False)),
        ))
    return mappings


def _build_patch(
    devices: Dict[str, MappingDevice],
    raw_points: Dict[str, RawPoint],
    mappings: List[ChannelMapping],
) -> Tuple[List[str], List[str], Dict[str, object]]:
    errors: List[str] = []
    warnings: List[str] = []
    patch: Dict[str, object] = {}
    points: Dict[str, int] = {}
    additional_inputs: List[Dict[str, object]] = []
    core_device_key: Optional[Tuple[str, int]] = None
    core_device: Optional[MappingDevice] = None

    for mapping in mappings:
        raw_point = raw_points[mapping.source_point_id]
        device = devices[raw_point.device_id]
        if mapping.channel_id in CORE_CHANNELS:
            expected_type = CORE_CHANNEL_OBJECT_TYPES[mapping.channel_id]
            if raw_point.object_type != expected_type:
                errors.append(
                    "„{0}“ benötigt einen BACnet-{1}-Datenpunkt.".format(mapping.label, expected_type.upper())
                )
                continue
            next_core_key = (device.host, device.port)
            if core_device_key is None:
                core_device_key = next_core_key
                core_device = device
            elif core_device_key != next_core_key:
                errors.append("Die vier Mini-EMS-Kernpunkte müssen aktuell auf demselben BACnet-Gerät liegen.")
                continue
            points[CORE_CHANNEL_POINT_KEYS[mapping.channel_id]] = raw_point.instance
            if mapping.scale != 1.0 or mapping.offset != 0.0 or mapping.invert:
                warnings.append("Die Umrechnung für „{0}“ wird von der aktuellen Runtime noch nicht angewendet.".format(mapping.label))
            continue

        if mapping.access != "read":
            errors.append("Der zusätzliche Datenpunkt „{0}“ kann aktuell nur gelesen werden.".format(mapping.label))
            continue
        additional_inputs.append(_additional_input_entry(mapping, raw_point, device))

    if points:
        patch["points"] = points
    if core_device is not None:
        patch["network"] = {
            "controller_ip": core_device.host,
            "controller_port": core_device.port,
        }
    if additional_inputs:
        patch["additional_inputs"] = additional_inputs
    if not points and not additional_inputs and not errors:
        errors.append("Aus der Zuordnung konnten keine nutzbaren Datenpunkte erzeugt werden.")
    return errors, warnings, patch


def _additional_input_entry(
    mapping: ChannelMapping,
    raw_point: RawPoint,
    device: MappingDevice,
) -> Dict[str, object]:
    entry: Dict[str, object] = {
        "channel_id": mapping.channel_id,
        "protocol": device.protocol,
        "object_type": raw_point.object_type,
        "instance": raw_point.instance,
        "description": mapping.label or raw_point.name,
        "controller_ip": device.host,
        "controller_port": device.port,
        "include_in_health": mapping.include_in_health,
        "read_interval_cycles": mapping.read_interval_cycles,
    }
    if mapping.plausible_min is not None:
        entry["plausible_min"] = mapping.plausible_min
    if mapping.plausible_max is not None:
        entry["plausible_max"] = mapping.plausible_max
    if mapping.max_age_seconds is not None:
        entry["max_age_seconds"] = mapping.max_age_seconds
    return entry


def _result(valid: bool, errors: List[str], warnings: List[str], patch: Dict[str, object]) -> Dict[str, object]:
    return {
        "valid": valid,
        "errors": errors,
        "warnings": warnings,
        "patch": patch,
    }


def _required_text(raw: Dict[str, object], key: str, context: str, errors: List[str]) -> str:
    value = _text(raw.get(key), "")
    if not value:
        labels = {
            "id": "eine Kennung",
            "host": "eine Geräteadresse",
            "device_id": "ein Gerät",
            "channel_id": "eine fachliche Bedeutung",
            "source_point_id": "einen Datenpunkt",
        }
        errors.append("{0} benötigt {1}.".format(context, labels.get(key, key)))
    return value


def _text(value: object, fallback: str) -> str:
    if value is None:
        return fallback
    return str(value).strip() or fallback


def _integer(value: object, fallback: int) -> int:
    if value is None or value == "":
        return fallback
    return int(value)


def _float(value: object, fallback: float) -> float:
    if value is None or value == "":
        return fallback
    return float(value)


def _optional_float(value: object) -> Optional[float]:
    if value is None or value == "":
        return None
    return float(value)


def _bacnet_object_type(value: object) -> Optional[str]:
    normalized = str(value or "").strip().lower()
    mapping = {
        "ai": "ai",
        "analog_input": "ai",
        "analog-input": "ai",
        "analog input": "ai",
        "av": "av",
        "analog_value": "av",
        "analog-value": "av",
        "analog value": "av",
        "bv": "bv",
        "binary_value": "bv",
        "binary-value": "bv",
        "binary value": "bv",
    }
    return mapping.get(normalized)
