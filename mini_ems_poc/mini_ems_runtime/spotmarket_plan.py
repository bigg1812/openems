import json
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from .state_store import write_json_atomic


@dataclass(frozen=True)
class SpotmarketWindow:
    start_slot: int
    end_slot_exclusive: int
    start_label: str
    end_label_exclusive: str
    length_quarters: int
    min_price_ct_kwh: float
    max_price_ct_kwh: float

    def to_dict(self) -> Dict[str, object]:
        return {
            "start_slot": self.start_slot,
            "end_slot_exclusive": self.end_slot_exclusive,
            "start_label": self.start_label,
            "end_label_exclusive": self.end_label_exclusive,
            "length_quarters": self.length_quarters,
            "min_price_ct_kwh": self.min_price_ct_kwh,
            "max_price_ct_kwh": self.max_price_ct_kwh,
        }


@dataclass(frozen=True)
class SpotmarketManualOverride:
    enabled: bool
    date_iso: Optional[str]
    windows: List[SpotmarketWindow]
    note: Optional[str] = None

    def active_now(self, current_slot_index: int) -> bool:
        if not self.enabled:
            return False
        for window in self.windows:
            if window.start_slot <= current_slot_index < window.end_slot_exclusive:
                return True
        return False

    def next_window(self, current_slot_index: int) -> Optional[SpotmarketWindow]:
        for window in self.windows:
            if current_slot_index < window.end_slot_exclusive:
                return window
        return None

    def to_dict(self) -> Dict[str, object]:
        return {
            "enabled": self.enabled,
            "date": self.date_iso,
            "note": self.note,
            "window_count": len(self.windows),
            "windows": [window.to_dict() for window in self.windows],
        }


class SpotmarketManualOverrideStore:
    def __init__(self, path: Path):
        self.path = Path(path)

    def load_for_date(self, date_iso: str) -> SpotmarketManualOverride:
        if not self.path.exists():
            return SpotmarketManualOverride(enabled=False, date_iso=date_iso, windows=[], note=None)
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return SpotmarketManualOverride(enabled=False, date_iso=date_iso, windows=[], note="invalid_override_file")
        if not isinstance(raw, dict):
            return SpotmarketManualOverride(enabled=False, date_iso=date_iso, windows=[], note="invalid_override_payload")

        enabled = bool(raw.get("enabled", False))
        override_date_iso = str(raw.get("date")) if raw.get("date") is not None else None
        if not enabled or override_date_iso != date_iso:
            return SpotmarketManualOverride(enabled=False, date_iso=date_iso, windows=[], note=raw.get("note"))

        windows: List[SpotmarketWindow] = []
        raw_windows = raw.get("windows")
        if isinstance(raw_windows, list):
            for item in raw_windows:
                window = _parse_override_window(item)
                if window is not None:
                    windows.append(window)

        return SpotmarketManualOverride(
            enabled=True,
            date_iso=override_date_iso,
            windows=windows,
            note=str(raw.get("note")) if raw.get("note") is not None else None,
        )


class SpotmarketPlanWriter:
    def __init__(self, path: Path, negative_threshold_ct_kwh: float, min_consecutive_quarters: int):
        self.path = Path(path)
        self.negative_threshold_ct_kwh = float(negative_threshold_ct_kwh)
        self._lock = threading.RLock()
        self.min_consecutive_quarters = self._validate_min_consecutive_quarters(min_consecutive_quarters)

    def set_min_consecutive_quarters(self, value: int) -> None:
        with self._lock:
            self.min_consecutive_quarters = self._validate_min_consecutive_quarters(value)

    def settings_payload(self) -> Dict[str, object]:
        with self._lock:
            return {
                "min_consecutive_quarters": self.min_consecutive_quarters,
                "min_consecutive_hours": self.min_consecutive_quarters / 4.0,
            }

    def write_plan(
        self,
        generated_at: str,
        today_date_iso: Optional[str],
        today_slots: Sequence[Optional[float]],
        tomorrow_date_iso: Optional[str],
        tomorrow_slots: Sequence[Optional[float]],
        current_slot_index: int,
    ) -> Dict[str, object]:
        with self._lock:
            today_windows = self._find_windows(today_slots)
            tomorrow_windows = self._find_windows(tomorrow_slots)
            active_today = self.is_slot_active(current_slot_index, today_windows)
            next_today_window = self._next_window(current_slot_index, today_windows)

            payload = {
                "generated_at": generated_at,
                "plan_type": "spotmarket_windows",
                "source_resolution": "quarterhour",
                "negative_threshold_ct_kwh": self.negative_threshold_ct_kwh,
                "min_consecutive_quarters": self.min_consecutive_quarters,
                "active_today_now": active_today,
                "next_today_window": next_today_window.to_dict() if next_today_window is not None else None,
                "today": self._day_payload(today_date_iso, today_slots, today_windows),
                "tomorrow": self._day_payload(tomorrow_date_iso, tomorrow_slots, tomorrow_windows),
                "operator_summary": self._build_operator_summary(
                    today_date_iso,
                    today_windows,
                    tomorrow_date_iso,
                    tomorrow_windows,
                    active_today,
                ),
            }
            write_json_atomic(self.path, payload)
            return payload

    def is_slot_active(self, slot_index: int, windows: Sequence[SpotmarketWindow]) -> bool:
        for window in windows:
            if window.start_slot <= slot_index < window.end_slot_exclusive:
                return True
        return False

    def _next_window(self, current_slot_index: int, windows: Sequence[SpotmarketWindow]) -> Optional[SpotmarketWindow]:
        for window in windows:
            if current_slot_index < window.end_slot_exclusive:
                return window
        return None

    def _day_payload(
        self,
        date_iso: Optional[str],
        slots: Sequence[Optional[float]],
        windows: Sequence[SpotmarketWindow],
    ) -> Dict[str, object]:
        return {
            "date": date_iso,
            "available_slot_count": sum(1 for value in slots if value is not None),
            "window_count": len(windows),
            "has_negative_windows": len(windows) > 0,
            "windows": [window.to_dict() for window in windows],
        }

    def _find_windows(self, slots: Sequence[Optional[float]]) -> List[SpotmarketWindow]:
        windows: List[SpotmarketWindow] = []
        current_start: Optional[int] = None
        current_values: List[float] = []

        for slot_index, raw_value in enumerate(slots):
            value = None if raw_value is None else float(raw_value)
            if value is not None and value <= self.negative_threshold_ct_kwh:
                if current_start is None:
                    current_start = slot_index
                    current_values = []
                current_values.append(value)
                continue

            if current_start is not None:
                maybe_window = self._build_window(current_start, slot_index, current_values)
                if maybe_window is not None:
                    windows.append(maybe_window)
                current_start = None
                current_values = []

        if current_start is not None:
            maybe_window = self._build_window(current_start, len(slots), current_values)
            if maybe_window is not None:
                windows.append(maybe_window)

        return windows

    def _build_window(
        self,
        start_slot: int,
        end_slot_exclusive: int,
        values: Sequence[float],
    ) -> Optional[SpotmarketWindow]:
        length = end_slot_exclusive - start_slot
        if length < self.min_consecutive_quarters:
            return None
        return SpotmarketWindow(
            start_slot=start_slot,
            end_slot_exclusive=end_slot_exclusive,
            start_label=_slot_label(start_slot),
            end_label_exclusive=_slot_label(end_slot_exclusive),
            length_quarters=length,
            min_price_ct_kwh=round(min(values), 4),
            max_price_ct_kwh=round(max(values), 4),
        )

    def _build_operator_summary(
        self,
        today_date_iso: Optional[str],
        today_windows: Sequence[SpotmarketWindow],
        tomorrow_date_iso: Optional[str],
        tomorrow_windows: Sequence[SpotmarketWindow],
        active_today: bool,
    ) -> str:
        today_text = self._windows_text(today_date_iso, today_windows)
        tomorrow_text = self._windows_text(tomorrow_date_iso, tomorrow_windows)
        active_text = "Spotmarket lockout is active now." if active_today else "Spotmarket lockout is not active now."
        return "{0} {1} {2}".format(active_text, today_text, tomorrow_text).strip()

    def _windows_text(self, date_iso: Optional[str], windows: Sequence[SpotmarketWindow]) -> str:
        if not date_iso:
            return "No date available."
        if not windows:
            return "No negative windows for {0}.".format(date_iso)
        return "Negative windows for {0}: {1}.".format(
            date_iso,
            ", ".join("{0}-{1}".format(window.start_label, window.end_label_exclusive) for window in windows),
        )

    @staticmethod
    def _validate_min_consecutive_quarters(value: int) -> int:
        parsed = int(value)
        if parsed <= 0:
            raise ValueError("min_consecutive_quarters must be > 0")
        return parsed


def _slot_label(slot_index: int) -> str:
    wrapped_index = slot_index % 96
    hour = wrapped_index // 4
    minute = (wrapped_index % 4) * 15
    return "{0:02d}:{1:02d}".format(hour, minute)


def _parse_override_window(raw: object) -> Optional[SpotmarketWindow]:
    if not isinstance(raw, dict):
        return None
    start_label = raw.get("start_label")
    end_label_exclusive = raw.get("end_label_exclusive")
    if not isinstance(start_label, str) or not isinstance(end_label_exclusive, str):
        return None
    start_slot = _label_to_slot(start_label)
    end_slot_exclusive = _label_to_slot(end_label_exclusive)
    if start_slot is None or end_slot_exclusive is None or end_slot_exclusive <= start_slot:
        return None
    return SpotmarketWindow(
        start_slot=start_slot,
        end_slot_exclusive=end_slot_exclusive,
        start_label=start_label,
        end_label_exclusive=end_label_exclusive,
        length_quarters=end_slot_exclusive - start_slot,
        min_price_ct_kwh=0.0,
        max_price_ct_kwh=0.0,
    )


def _label_to_slot(label: str) -> Optional[int]:
    parts = label.split(":")
    if len(parts) != 2:
        return None
    try:
        hour = int(parts[0])
        minute = int(parts[1])
    except ValueError:
        return None
    if hour < 0 or hour > 23 or minute not in (0, 15, 30, 45):
        return None
    return hour * 4 + (minute // 15)
