import argparse
import csv
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .runtime_db import RuntimeDatabase


OBJECT_REFERENCE_RE = re.compile(r"/(?P<device>\d+)\.(?P<object_type>[A-Z]+)(?P<instance>\d+)$")
NUMBER_RE = re.compile(r"[-+]?\d+(?:[.,]\d+)?")


@dataclass(frozen=True)
class ObjectListReportPoint:
    channel_id: str
    object_type: str
    instance: int
    label: str
    unit: str
    plausible_min: Optional[float] = None
    plausible_max: Optional[float] = None

    def to_additional_input_config(self, *, read_interval_cycles: int = 5) -> Dict[str, object]:
        return {
            "channel_id": self.channel_id,
            "object_type": self.object_type.lower(),
            "instance": self.instance,
            "description": self.label,
            "plausible_min": self.plausible_min,
            "plausible_max": self.plausible_max,
            "include_in_health": False,
            "read_interval_cycles": read_interval_cycles,
        }


SELECTED_REPORT_POINTS: Dict[str, ObjectListReportPoint] = {
    "AI1101": ObjectListReportPoint("site.buffer_1_top_temperature_c", "AI", 1101, "Puffer 1 oben", "C", -20.0, 120.0),
    "AI1102": ObjectListReportPoint("site.buffer_1_bottom_temperature_c", "AI", 1102, "Puffer 1 unten", "C", -20.0, 120.0),
    "AI1103": ObjectListReportPoint("site.buffer_2_top_temperature_c", "AI", 1103, "Puffer 2 oben", "C", -20.0, 120.0),
    "AI1104": ObjectListReportPoint("site.buffer_2_bottom_temperature_c", "AI", 1104, "Puffer 2 unten", "C", -20.0, 120.0),
    "AI1107": ObjectListReportPoint("site.heat_generation_flow_temperature_c", "AI", 1107, "Waermeerzeugung Vorlauf", "C", -20.0, 120.0),
    "AI1108": ObjectListReportPoint("site.heat_generation_return_temperature_c", "AI", 1108, "Waermeerzeugung Ruecklauf", "C", -20.0, 120.0),
    "AI1201": ObjectListReportPoint("site.boiler_1_return_temperature_c", "AI", 1201, "Gaskessel Ruecklauf", "C", -20.0, 120.0),
    "AI1202": ObjectListReportPoint("site.boiler_2_return_temperature_c", "AI", 1202, "Pelletkessel Ruecklauf", "C", -20.0, 120.0),
    "AI1203": ObjectListReportPoint("site.chp_flow_temperature_c", "AI", 1203, "BHKW Vorlauf", "C", -20.0, 120.0),
    "AI1204": ObjectListReportPoint("site.chp_return_temperature_c", "AI", 1204, "BHKW Ruecklauf", "C", -20.0, 120.0),
    "AI2101": ObjectListReportPoint("site.boiler_1_flow_temperature_c", "AI", 2101, "Gaskessel Vorlauf", "C", -20.0, 120.0),
    "AI2102": ObjectListReportPoint("site.boiler_2_flow_temperature_c", "AI", 2102, "Pelletkessel Vorlauf", "C", -20.0, 120.0),
}


def selected_additional_input_configs(*, read_interval_cycles: int = 5) -> List[Dict[str, object]]:
    return [
        point.to_additional_input_config(read_interval_cycles=read_interval_cycles)
        for point in SELECTED_REPORT_POINTS.values()
    ]


def build_samples_from_objectlist_csv(path: Path) -> List[Dict[str, object]]:
    samples: List[Dict[str, object]] = []
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            reference = str(row.get("Object Reference") or "")
            point_key = _point_key(reference)
            if point_key is None or point_key not in SELECTED_REPORT_POINTS:
                continue
            status = str(row.get("Status") or "").lower()
            if "fault" in status or "not-commissioned" in status or "out-of-service" in status:
                continue
            value = _parse_numeric_value(row.get("Value"))
            if value is None:
                continue
            point = SELECTED_REPORT_POINTS[point_key]
            samples.append(
                {
                    "channel_id": point.channel_id,
                    "value": value,
                    "unit": point.unit,
                    "label": point.label,
                    "source_reference": reference,
                }
            )
    return samples


def import_objectlist_snapshot(
    runtime_db: RuntimeDatabase,
    csv_path: Path,
    *,
    timestamp: Optional[str] = None,
    cycle_id: Optional[str] = None,
) -> int:
    timestamp = timestamp or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    cycle_id = cycle_id or "objectlist-{0}".format(timestamp.replace(":", "").replace("-", ""))
    samples = build_samples_from_objectlist_csv(csv_path)
    runtime_db.record_external_channel_samples(
        samples,
        cycle_id=cycle_id,
        timestamp=timestamp,
        source="objectlist_csv",
    )
    return len(samples)


def _point_key(reference: str) -> Optional[str]:
    match = OBJECT_REFERENCE_RE.search(reference.strip())
    if not match:
        return None
    return "{0}{1}".format(match.group("object_type"), match.group("instance"))


def _parse_numeric_value(raw_value: object) -> Optional[float]:
    text = str(raw_value or "").strip().replace("'", "")
    match = NUMBER_RE.search(text)
    if not match:
        return None
    return float(match.group(0).replace(",", "."))


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Import selected BACnet objectlist values into the Mini EMS report DB.")
    parser.add_argument("--csv", required=True, help="Path to objectlist.csv")
    parser.add_argument("--db", default="data/runtime/mini_ems.sqlite", help="Path to mini_ems.sqlite")
    args = parser.parse_args(list(argv) if argv is not None else None)

    count = import_objectlist_snapshot(RuntimeDatabase(Path(args.db)), Path(args.csv))
    print("imported {0} selected report samples".format(count))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
