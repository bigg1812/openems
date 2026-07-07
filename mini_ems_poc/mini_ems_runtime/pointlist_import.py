import base64
import binascii
import csv
import io
import re
import zipfile
from typing import Dict, List, Optional, Tuple
from xml.etree import ElementTree


OBJECT_REFERENCE_RE = re.compile(
    r"(?:(?P<device>\d+)[./])?(?P<object_type>AI|AO|AV|BI|BO|BV|MSI|MSO|MSV|MI|MO|MV)\s*-?\s*(?P<instance>\d+)",
    re.IGNORECASE,
)
NUMBER_RE = re.compile(r"[-+]?\d+(?:[.,]\d+)?")

HEADER_ALIASES = {
    "object_reference": {
        "object reference",
        "object",
        "object id",
        "object identifier",
        "object_reference",
        "bacnet object",
        "bacnet-objekt",
        "bacnet objekt",
        "datenpunkt",
        "referenz",
    },
    "device": {"device", "device id", "gerät", "geraet", "controller", "source", "quelle"},
    "name": {"name", "object name", "object-name", "bezeichnung", "beschreibung", "description", "text"},
    "unit": {"unit", "units", "einheit", "engineering units", "eng units"},
    "value": {"value", "wert", "present value", "present-value", "istwert"},
    "access": {"access", "zugriff", "richtung", "read write", "r/w", "rw"},
    "channel_id": {"channel", "channel_id", "kanal", "ems kanal", "ems channel", "mini ems kanal"},
    "comment": {"comment", "kommentar", "notes", "notiz", "remark", "bemerkung"},
}

BACNET_OBJECT_TYPES = {
    "ai": "ai",
    "analog-input": "ai",
    "analog input": "ai",
    "analog_input": "ai",
    "ao": "ao",
    "analog-output": "ao",
    "analog output": "ao",
    "analog_output": "ao",
    "av": "av",
    "analog-value": "av",
    "analog value": "av",
    "analog_value": "av",
    "bi": "bi",
    "binary-input": "bi",
    "binary input": "bi",
    "binary_input": "bi",
    "bo": "bo",
    "binary-output": "bo",
    "binary output": "bo",
    "binary_output": "bo",
    "bv": "bv",
    "binary-value": "bv",
    "binary value": "bv",
    "binary_value": "bv",
    "msi": "msi",
    "multi-state-input": "msi",
    "mso": "mso",
    "multi-state-output": "mso",
    "msv": "msv",
    "multi-state-value": "msv",
}

MAPPING_SUPPORTED_TYPES = {"ai", "av", "bv"}
DEFAULT_DEVICE_ID = "imported_bacnet_device"


def import_pointlist_payload(payload: Dict[str, object]) -> Dict[str, object]:
    filename = _text(payload.get("filename"), "pointlist.csv")
    try:
        raw_content = _decode_content(payload)
        rows = _read_rows(filename, raw_content)
        default_device = _device_payload(payload.get("default_device"))
        return build_pointlist_import_draft(rows, filename=filename, default_device=default_device)
    except ValueError as error:
        return {
            "valid": False,
            "errors": [str(error)],
            "warnings": [],
            "devices": [],
            "raw_points": [],
            "suggested_mappings": [],
            "candidates": [],
        }


def build_pointlist_import_draft(
    rows: List[Dict[str, object]],
    *,
    filename: str,
    default_device: Optional[Dict[str, object]] = None,
) -> Dict[str, object]:
    if not rows:
        return _result(False, ["Punktliste enthält keine Datenzeilen"], [], [], [], [])

    default_device = _device_payload(default_device)
    devices_by_id: Dict[str, Dict[str, object]] = {}
    candidates: List[Dict[str, object]] = []
    raw_points: List[Dict[str, object]] = []
    suggested_mappings: List[Dict[str, object]] = []
    warnings: List[str] = []
    errors: List[str] = []
    seen_point_ids: set[str] = set()

    for row_index, row in enumerate(rows, start=2):
        normalized = _normalized_row(row)
        object_ref = _text(normalized.get("object_reference"), "")
        parsed = _parse_object_reference(object_ref)
        if parsed is None:
            fallback = "{0}{1}".format(_text(normalized.get("object_type"), ""), _text(normalized.get("instance"), ""))
            parsed = _parse_object_reference(fallback)
        if parsed is None:
            warnings.append("Zeile {0}: keine BACnet-Objektkennung erkannt".format(row_index))
            continue

        device_suffix, object_type, instance = parsed
        explicit_device = _slug(_text(normalized.get("device"), ""))
        if explicit_device:
            device_id = explicit_device
        elif device_suffix:
            device_id = "device_{0}".format(device_suffix)
        else:
            device_id = _text(default_device.get("id"), DEFAULT_DEVICE_ID)

        devices_by_id.setdefault(
            device_id,
            {
                "id": device_id,
                "name": _text(normalized.get("device"), "") or _text(default_device.get("name"), device_id),
                "protocol": "bacnet",
                "host": _text(default_device.get("host"), ""),
                "port": _integer(default_device.get("port"), 47808),
            },
        )

        point_id = "bacnet:{0}:{1}:{2}".format(device_id, object_type, instance)
        if point_id in seen_point_ids:
            warnings.append("Zeile {0}: doppelter Rohpunkt {1} ignoriert".format(row_index, point_id))
            continue
        seen_point_ids.add(point_id)

        name = _text(normalized.get("name"), object_ref or point_id)
        unit = _text(normalized.get("unit"), "")
        value = _optional_float(normalized.get("value"))
        access = _access_from_row(normalized, object_type)
        candidate = {
            "id": point_id,
            "device_id": device_id,
            "object_type": object_type,
            "instance": instance,
            "name": name,
            "unit": unit,
            "access": access,
            "value": value,
            "source": {
                "kind": "pointlist",
                "filename": filename,
                "row": row_index,
                "object_reference": object_ref,
                "comment": _text(normalized.get("comment"), ""),
            },
            "status": "candidate",
        }
        candidates.append(candidate)

        if object_type not in MAPPING_SUPPORTED_TYPES:
            warnings.append(
                "Zeile {0}: {1} wird als Kandidat importiert, ist aber noch kein aktivierbarer Mini-EMS-Rohpunkt".format(
                    row_index,
                    object_type.upper(),
                )
            )
            continue

        raw_points.append(
            {
                "id": point_id,
                "device_id": device_id,
                "object_type": object_type,
                "instance": instance,
                "name": name,
                "unit": unit,
            }
        )
        channel_id = _text(normalized.get("channel_id"), "")
        if channel_id:
            suggested_mappings.append(
                {
                    "channel_id": channel_id,
                    "source_point_id": point_id,
                    "label": name,
                    "access": "read" if access == "write" else access,
                }
            )

    if not candidates:
        errors.append("Keine verwertbaren BACnet-Rohpunkte erkannt")
    return _result(not errors, errors, warnings, list(devices_by_id.values()), raw_points, suggested_mappings, candidates)


def _decode_content(payload: Dict[str, object]) -> bytes:
    if "content_base64" in payload:
        try:
            return base64.b64decode(str(payload["content_base64"]), validate=True)
        except (binascii.Error, ValueError) as error:
            raise ValueError("content_base64 ist kein gültiges Base64") from error
    if "content" in payload:
        return str(payload["content"]).encode("utf-8")
    raise ValueError("filename und content_base64 oder content sind erforderlich")


def _read_rows(filename: str, content: bytes) -> List[Dict[str, object]]:
    suffix = filename.lower().rsplit(".", 1)[-1] if "." in filename else "csv"
    if suffix in ("csv", "txt"):
        return _read_csv_rows(content, delimiter=None)
    if suffix == "tsv":
        return _read_csv_rows(content, delimiter="\t")
    if suffix == "xlsx":
        return _read_xlsx_rows(content)
    raise ValueError("Dateityp wird noch nicht unterstützt: {0}".format(filename))


def _read_csv_rows(content: bytes, delimiter: Optional[str]) -> List[Dict[str, object]]:
    text = content.decode("utf-8-sig")
    sample = text[:2048]
    if delimiter is None:
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
            delimiter = dialect.delimiter
        except csv.Error:
            delimiter = ";"
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    return [dict(row) for row in reader]


def _read_xlsx_rows(content: bytes) -> List[Dict[str, object]]:
    with zipfile.ZipFile(io.BytesIO(content)) as workbook:
        sheet_name = _first_sheet_path(workbook)
        shared_strings = _read_shared_strings(workbook)
        raw_rows = _read_sheet_rows(workbook, sheet_name, shared_strings)
    rows = [[_text(cell, "") for cell in row] for row in raw_rows if any(_text(cell, "") for cell in row)]
    if not rows:
        return []
    headers = rows[0]
    data_rows: List[Dict[str, object]] = []
    for row in rows[1:]:
        data_rows.append({headers[index]: row[index] if index < len(row) else "" for index in range(len(headers))})
    return data_rows


def _first_sheet_path(workbook: zipfile.ZipFile) -> str:
    names = set(workbook.namelist())
    if "xl/worksheets/sheet1.xml" in names:
        return "xl/worksheets/sheet1.xml"
    for name in sorted(names):
        if name.startswith("xl/worksheets/sheet") and name.endswith(".xml"):
            return name
    raise ValueError("XLSX enthält kein lesbares Arbeitsblatt")


def _read_shared_strings(workbook: zipfile.ZipFile) -> List[str]:
    if "xl/sharedStrings.xml" not in workbook.namelist():
        return []
    root = ElementTree.fromstring(workbook.read("xl/sharedStrings.xml"))
    values: List[str] = []
    for item in root.findall(".//{*}si"):
        values.append("".join(text.text or "" for text in item.findall(".//{*}t")))
    return values


def _read_sheet_rows(workbook: zipfile.ZipFile, sheet_name: str, shared_strings: List[str]) -> List[List[str]]:
    root = ElementTree.fromstring(workbook.read(sheet_name))
    output: List[List[str]] = []
    for row in root.findall(".//{*}row"):
        values: List[str] = []
        for cell in row.findall("{*}c"):
            column_index = _column_index(cell.attrib.get("r", ""))
            while len(values) < column_index:
                values.append("")
            values.append(_cell_value(cell, shared_strings))
        output.append(values)
    return output


def _cell_value(cell: ElementTree.Element, shared_strings: List[str]) -> str:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        return "".join(text.text or "" for text in cell.findall(".//{*}t"))
    value = cell.find("{*}v")
    if value is None or value.text is None:
        return ""
    if cell_type == "s":
        index = int(value.text)
        return shared_strings[index] if index < len(shared_strings) else ""
    return value.text


def _column_index(reference: str) -> int:
    letters = "".join(ch for ch in reference if ch.isalpha()).upper()
    if not letters:
        return 0
    index = 0
    for letter in letters:
        index = index * 26 + (ord(letter) - ord("A") + 1)
    return index - 1


def _normalized_row(row: Dict[str, object]) -> Dict[str, object]:
    normalized: Dict[str, object] = {}
    for header, value in row.items():
        key = _normalize_header(header)
        normalized[key] = value
    return normalized


def _normalize_header(header: object) -> str:
    text = _text(header, "").lower().replace("_", " ").replace("-", " ")
    text = " ".join(text.split())
    for canonical, aliases in HEADER_ALIASES.items():
        if text in aliases:
            return canonical
    if text in {"object type", "objekttyp", "type", "typ"}:
        return "object_type"
    if text in {"instance", "instanz", "object instance"}:
        return "instance"
    return text.replace(" ", "_")


def _parse_object_reference(reference: str) -> Optional[Tuple[Optional[str], str, int]]:
    match = OBJECT_REFERENCE_RE.search(reference.strip())
    if not match:
        return None
    object_type = BACNET_OBJECT_TYPES.get(match.group("object_type").lower())
    if object_type is None:
        return None
    return match.group("device"), object_type, int(match.group("instance"))


def _access_from_row(row: Dict[str, object], object_type: str) -> str:
    raw = _text(row.get("access"), "").lower()
    if any(token in raw for token in ("readwrite", "read/write", "rw", "r/w", "lesen/schreiben")):
        return "readwrite"
    if any(token in raw for token in ("write", "schreib", "writable", "ausgang", "output")):
        return "write"
    if any(token in raw for token in ("read", "les", "input")):
        return "read"
    if object_type in {"ao", "bo"}:
        return "write"
    return "read"


def _device_payload(raw: object) -> Dict[str, object]:
    if not isinstance(raw, dict):
        return {"id": DEFAULT_DEVICE_ID, "name": "Importiertes BACnet-Gerät", "host": "", "port": 47808}
    return {
        "id": _slug(_text(raw.get("id"), DEFAULT_DEVICE_ID)) or DEFAULT_DEVICE_ID,
        "name": _text(raw.get("name"), "Importiertes BACnet-Gerät"),
        "host": _text(raw.get("host"), ""),
        "port": _integer(raw.get("port"), 47808),
    }


def _result(
    valid: bool,
    errors: List[str],
    warnings: List[str],
    devices: List[Dict[str, object]],
    raw_points: List[Dict[str, object]],
    suggested_mappings: List[Dict[str, object]],
    candidates: Optional[List[Dict[str, object]]] = None,
) -> Dict[str, object]:
    return {
        "valid": valid,
        "errors": errors,
        "warnings": warnings,
        "devices": devices,
        "raw_points": raw_points,
        "suggested_mappings": suggested_mappings,
        "candidates": list(candidates if candidates is not None else raw_points),
        "mapping_draft": {
            "devices": devices,
            "raw_points": raw_points,
            "mappings": suggested_mappings,
        },
    }


def _text(value: object, fallback: str) -> str:
    if value is None:
        return fallback
    return str(value).strip() or fallback


def _integer(value: object, fallback: int) -> int:
    if value is None or value == "":
        return fallback
    return int(value)


def _optional_float(value: object) -> Optional[float]:
    text = _text(value, "")
    if not text:
        return None
    match = NUMBER_RE.search(text)
    if not match:
        return None
    return float(match.group(0).replace(",", "."))


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_]+", "_", value.strip().lower()).strip("_")
    return slug
