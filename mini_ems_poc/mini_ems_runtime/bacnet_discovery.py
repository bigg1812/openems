import asyncio
from typing import Dict, List, Optional

from .pointlist_import import build_pointlist_import_draft


SUPPORTED_DISCOVERY_TYPES = {"analog-input", "analog-value", "binary-value", "ai", "av", "bv"}


def preview_bacnet_discovery_payload(payload: Dict[str, object], *, application=None) -> Dict[str, object]:
    """Run or simulate a read-only BACnet discovery and return mapping candidates.

    The real path uses BACpypes3 when it is installed. Tests inject an
    application with the tiny async surface we need (`who_is`, `read_property`,
    `close`) so the contract stays verifiable without touching a real plant.
    """
    if application is None:
        try:
            application = _build_bacpypes3_application(payload)
        except ImportError:
            return {
                "valid": False,
                "errors": ["BACpypes3 ist nicht installiert; Discovery ist nur als optionales Werkzeug verfügbar"],
                "warnings": [],
                "devices": [],
                "raw_points": [],
                "suggested_mappings": [],
                "candidates": [],
                "mapping_draft": {"devices": [], "raw_points": [], "mappings": []},
            }
    return asyncio.run(_discover(payload, application))


async def _discover(payload: Dict[str, object], application) -> Dict[str, object]:
    low_limit = _integer(payload.get("low_limit"), 0)
    high_limit = _integer(payload.get("high_limit"), low_limit)
    max_objects = _integer(payload.get("max_objects_per_device"), 64)
    rows: List[Dict[str, object]] = []
    warnings: List[str] = []

    try:
        i_ams = await application.who_is(low_limit, high_limit)
        for i_am in i_ams:
            device_identifier = i_am.iAmDeviceIdentifier
            device_instance = _object_instance(device_identifier)
            device_address = i_am.pduSource
            object_list = await _read_object_list(application, device_address, device_identifier, warnings)
            for object_identifier in object_list[:max_objects]:
                object_type = _object_type(object_identifier)
                if object_type not in SUPPORTED_DISCOVERY_TYPES:
                    continue
                instance = _object_instance(object_identifier)
                name = await _safe_read(application, device_address, object_identifier, "object-name")
                description = await _safe_read(application, device_address, object_identifier, "description")
                unit = await _safe_read(application, device_address, object_identifier, "units")
                value = await _safe_read(application, device_address, object_identifier, "present-value")
                rows.append(
                    {
                        "Object Reference": "{0}.{1}{2}".format(
                            device_instance,
                            _short_object_type(object_type),
                            instance,
                        ),
                        "Device": "device_{0}".format(device_instance),
                        "Name": str(name or description or object_identifier),
                        "Unit": str(unit or ""),
                        "Value": "" if value is None else str(value),
                        "Access": "read",
                        "Comment": "BACpypes3 read-only discovery",
                    }
                )
    finally:
        close = getattr(application, "close", None)
        if close is not None:
            close()

    result = build_pointlist_import_draft(
        rows,
        filename="bacpypes3-discovery",
        default_device={
            "id": "bacnet_discovery",
            "name": "BACpypes3 Discovery",
            "host": str(payload.get("target_host") or ""),
            "port": _integer(payload.get("target_port"), 47808),
        },
    )
    result["warnings"] = warnings + list(result.get("warnings", []))
    result["source"] = {
        "kind": "bacpypes3_discovery",
        "low_limit": low_limit,
        "high_limit": high_limit,
        "read_only": True,
    }
    return result


async def _read_object_list(application, address, device_identifier, warnings: List[str]) -> List[object]:
    try:
        object_list = await application.read_property(address, device_identifier, "object-list")
        return list(object_list or [])
    except Exception as error:
        warnings.append("object-list konnte nicht als Liste gelesen werden: {0}".format(error))
    try:
        length = await application.read_property(address, device_identifier, "object-list", array_index=0)
        objects = []
        for index in range(int(length)):
            objects.append(await application.read_property(address, device_identifier, "object-list", array_index=index + 1))
        return objects
    except Exception as error:
        warnings.append("object-list konnte nicht einzeln gelesen werden: {0}".format(error))
        return []


async def _safe_read(application, address, object_identifier, property_identifier: str) -> Optional[object]:
    try:
        return await application.read_property(address, object_identifier, property_identifier)
    except Exception:
        return None


def _build_bacpypes3_application(payload: Dict[str, object]):
    from argparse import Namespace

    from bacpypes3.app import Application

    args = Namespace(
        address=str(payload.get("local_address") or payload.get("local_ip") or "0.0.0.0"),
        debug=[],
        color=False,
        route_aware=False,
        name="Mini EMS Discovery",
        instance=_integer(payload.get("local_device_instance"), 59999),
        vendoridentifier=_integer(payload.get("vendor_identifier"), 999),
    )
    return Application.from_args(args)


def _object_type(identifier: object) -> str:
    if isinstance(identifier, (tuple, list)) and identifier:
        return str(identifier[0]).lower()
    text = str(identifier).strip().lower()
    if "," in text:
        text = text.split(",", 1)[0].strip("() ")
    return text


def _object_instance(identifier: object) -> int:
    if isinstance(identifier, (tuple, list)) and len(identifier) > 1:
        return int(identifier[1])
    digits = "".join(ch for ch in str(identifier) if ch.isdigit())
    return int(digits or "0")


def _short_object_type(object_type: str) -> str:
    mapping = {
        "analog-input": "AI",
        "analog-value": "AV",
        "binary-value": "BV",
        "ai": "AI",
        "av": "AV",
        "bv": "BV",
    }
    return mapping.get(object_type, object_type.upper())


def _integer(value: object, fallback: int) -> int:
    if value is None or value == "":
        return fallback
    return int(value)
