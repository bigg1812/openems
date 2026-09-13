import json
import math
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from .price_provider_smard import PriceProviderError, RecentSlotMapScanResult, SmardPriceProvider, berlin_now
from .price_time import TIME_MODEL, slot_count, slot_label, slot_starts
from .state_store import write_json_atomic


@dataclass(frozen=True)
class CachedDay:
    date_iso: str
    slots: List[Optional[float]]

    def to_dict(self) -> dict:
        return {
            "date": self.date_iso,
            "slot_count": len(self.slots),
            "available_slot_count": sum(1 for value in self.slots if value is not None),
            "slot_minutes": 15,
            "time_model": TIME_MODEL,
            "slot_starts_utc": slot_starts(self.date_iso),
            "slots": list(self.slots),
            "slots_by_label": {
                slot_label(self.date_iso, index): value
                for index, value in enumerate(self.slots)
            },
        }

    @classmethod
    def from_dict(cls, raw: object) -> Optional["CachedDay"]:
        if not isinstance(raw, dict):
            return None
        date_iso = raw.get("date")
        slots = raw.get("slots")
        if not isinstance(date_iso, str) or not isinstance(slots, list):
            return None
        try:
            expected = slot_count(date_iso)
            if raw.get("time_model") != TIME_MODEL:
                # Old clock-indexed transition days cannot be reconstructed reliably.
                if expected != 96 or raw.get("time_model") is not None:
                    return None
                if len(slots) == 24:
                    slots = [value for value in slots for _ in range(4)]
            if len(slots) != expected:
                return None
            normalized = [None if value is None else float(value) for value in slots]
            if any(value is not None and not math.isfinite(value) for value in normalized):
                return None
            return cls(date_iso=date_iso, slots=normalized)
        except (ValueError, TypeError, OverflowError):
            return None



@dataclass(frozen=True)
class PublishedPriceSnapshot:
    current_price_ct_kwh: float
    current_slot_index: int
    current_slot_label: str
    today_date_iso: str
    today_available_slot_count: int
    tomorrow_date_iso: Optional[str]
    tomorrow_prices_available: bool
    tomorrow_available_slot_count: int
    cache_path: str
    last_update_at: str
    today_slots: List[Optional[float]] = field(default_factory=list)
    tomorrow_slots: List[Optional[float]] = field(default_factory=list)
    price_source_status: Dict[str, object] = field(default_factory=dict)


class SpotmarketPriceCacheService:
    def __init__(self, path: Path, provider: SmardPriceProvider):
        self.path = Path(path)
        self.provider = provider

    def refresh(self) -> PublishedPriceSnapshot:
        now_local = berlin_now()
        today = now_local.date()
        tomorrow = today + timedelta(days=1)
        cache = self._load_cache()
        try:
            scan_result = self.provider.scan_recent_slot_maps([today, tomorrow])
        except PriceProviderError as error:
            cached_snapshot = self._snapshot_from_cache(
                cache,
                now_local=now_local,
                today=today,
                tomorrow=tomorrow,
                error=error,
            )
            if cached_snapshot is not None:
                return cached_snapshot
            raise
        today_slot_map = scan_result.slot_maps_by_date.get(today.isoformat(), {})
        tomorrow_slot_map = scan_result.slot_maps_by_date.get(tomorrow.isoformat(), {})

        def merged_day(day: date, fresh: Dict[int, float]) -> CachedDay:
            date_iso = day.isoformat()
            previous = next((entry for entry in (cache.today, cache.tomorrow)
                             if entry is not None and entry.date_iso == date_iso), None)
            slots = list(previous.slots) if previous else [None] * slot_count(date_iso)
            # Merge corrections even when the published interval count is unchanged.
            for index, value in fresh.items():
                if 0 <= index < len(slots) and math.isfinite(value):
                    slots[index] = float(value)
            return CachedDay(date_iso=date_iso, slots=slots)

        today_entry = merged_day(today, today_slot_map)
        tomorrow_entry = merged_day(tomorrow, tomorrow_slot_map)

        slot_index = self.provider.current_slot_index(now_local)
        if slot_index >= len(today_entry.slots):
            raise PriceProviderError(
                "Current slot index {0} is outside cached day length {1}".format(
                    slot_index,
                    len(today_entry.slots),
                )
            )
        current_value = today_entry.slots[slot_index]
        if current_value is None:
            raise PriceProviderError(
                "Current slot {0} for {1} is not available in the published price set".format(
                    slot_label(today_entry.date_iso, slot_index),
                    today_entry.date_iso,
                )
            )

        cache = PriceCacheFile(
            last_update_at=now_local.isoformat(),
            today=today_entry,
            tomorrow=tomorrow_entry,
            price_source_status=self._build_price_source_status(scan_result, today, tomorrow),
        )
        self._save_cache(cache)

        tomorrow_available_slot_count = sum(1 for value in tomorrow_entry.slots if value is not None) if tomorrow_entry is not None else 0
        return PublishedPriceSnapshot(
            current_price_ct_kwh=float(current_value),
            current_slot_index=slot_index,
            current_slot_label=slot_label(today_entry.date_iso, slot_index),
            today_date_iso=today_entry.date_iso,
            today_available_slot_count=sum(1 for value in today_entry.slots if value is not None),
            today_slots=list(today_entry.slots),
            tomorrow_date_iso=tomorrow_entry.date_iso if tomorrow_entry is not None else None,
            tomorrow_prices_available=tomorrow_available_slot_count > 0,
            tomorrow_available_slot_count=tomorrow_available_slot_count,
            tomorrow_slots=list(tomorrow_entry.slots) if tomorrow_entry is not None else [],
            cache_path=str(self.path),
            last_update_at=now_local.isoformat(),
            price_source_status=cache.price_source_status or {},
        )

    def _snapshot_from_cache(
        self,
        cache: "PriceCacheFile",
        *,
        now_local: datetime,
        today: date,
        tomorrow: date,
        error: PriceProviderError,
    ) -> Optional[PublishedPriceSnapshot]:
        today_entry = cache.today
        if today_entry is None or today_entry.date_iso != today.isoformat():
            if cache.tomorrow is not None and cache.tomorrow.date_iso == today.isoformat():
                today_entry = cache.tomorrow
            else:
                return None

        if today_entry.date_iso != today.isoformat():
            return None

        slot_index = self.provider.current_slot_index(now_local)
        if slot_index >= len(today_entry.slots):
            return None

        current_value = today_entry.slots[slot_index]
        if current_value is None:
            return None

        tomorrow_entry = cache.tomorrow if cache.tomorrow is not None and cache.tomorrow.date_iso == tomorrow.isoformat() else None
        tomorrow_slots = list(tomorrow_entry.slots) if tomorrow_entry is not None else []
        tomorrow_available_slot_count = sum(1 for value in tomorrow_slots if value is not None)
        today_available_slot_count = sum(1 for value in today_entry.slots if value is not None)
        expected_slots = slot_count(today.isoformat())
        source_status = {
            "provider": self.provider.config.provider,
            "resolution": self.provider.config.resolution,
            "stale": True,
            "fallback": "cache",
            "error": str(error),
            "today_date": today.isoformat(),
            "today_slots_found": today_available_slot_count,
            "today_complete": today_available_slot_count == expected_slots,
            "tomorrow_date": tomorrow.isoformat(),
            "tomorrow_slots_found": tomorrow_available_slot_count,
            "tomorrow_complete": tomorrow_available_slot_count == slot_count(tomorrow.isoformat()),
            "last_successful_update_at": cache.last_update_at,
        }
        return PublishedPriceSnapshot(
            current_price_ct_kwh=float(current_value),
            current_slot_index=slot_index,
            current_slot_label=slot_label(today_entry.date_iso, slot_index),
            today_date_iso=today_entry.date_iso,
            today_available_slot_count=today_available_slot_count,
            today_slots=list(today_entry.slots),
            tomorrow_date_iso=tomorrow_entry.date_iso if tomorrow_entry is not None else tomorrow.isoformat(),
            tomorrow_prices_available=tomorrow_available_slot_count > 0,
            tomorrow_available_slot_count=tomorrow_available_slot_count,
            tomorrow_slots=tomorrow_slots,
            cache_path=str(self.path),
            last_update_at=now_local.isoformat(),
            price_source_status=source_status,
        )

    def _load_cache(self) -> "PriceCacheFile":
        if not self.path.exists():
            return PriceCacheFile(last_update_at=None, today=None, tomorrow=None)
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return PriceCacheFile(last_update_at=None, today=None, tomorrow=None)
        if not isinstance(raw, dict):
            return PriceCacheFile(last_update_at=None, today=None, tomorrow=None)
        return PriceCacheFile(
            last_update_at=str(raw.get("last_update_at")) if raw.get("last_update_at") is not None else None,
            today=CachedDay.from_dict(raw.get("today")),
            tomorrow=CachedDay.from_dict(raw.get("tomorrow")),
            price_source_status=(
                raw.get("price_source_status")
                if isinstance(raw.get("price_source_status"), dict)
                else raw.get("smard_diagnostics")
                if isinstance(raw.get("smard_diagnostics"), dict)
                else None
            ),
        )

    def _save_cache(self, cache: "PriceCacheFile") -> None:
        write_json_atomic(self.path, cache.to_dict())

    def _build_price_source_status(
        self,
        scan_result: RecentSlotMapScanResult,
        today: date,
        tomorrow: date,
    ) -> Dict[str, object]:
        today_slots_found = len(scan_result.slot_maps_by_date.get(today.isoformat(), {}))
        tomorrow_slots_found = len(scan_result.slot_maps_by_date.get(tomorrow.isoformat(), {}))
        expected_slots = slot_count(today.isoformat())
        return {
            "provider": self.provider.config.provider,
            "resolution": self.provider.config.resolution,
            "today_date": today.isoformat(),
            "today_slots_found": today_slots_found,
            "today_complete": today_slots_found == expected_slots,
            "tomorrow_date": tomorrow.isoformat(),
            "tomorrow_slots_found": tomorrow_slots_found,
            "tomorrow_complete": tomorrow_slots_found == slot_count(tomorrow.isoformat()),
            "first_local_timestamp": scan_result.first_local_timestamp,
            "last_local_timestamp": scan_result.last_local_timestamp,
            "scanned_block_count": len(scan_result.scanned_block_timestamps),
        }


@dataclass(frozen=True)
class PriceCacheFile:
    last_update_at: Optional[str]
    today: Optional[CachedDay]
    tomorrow: Optional[CachedDay]
    price_source_status: Optional[Dict[str, object]] = None

    def to_dict(self) -> dict:
        return {
            "last_update_at": self.last_update_at,
            "last_update_slot_label": _slot_label_from_timestamp(self.last_update_at),
            "today": self.today.to_dict() if self.today is not None else None,
            "tomorrow": self.tomorrow.to_dict() if self.tomorrow is not None else None,
            "price_source_status": self.price_source_status,
        }


def _slot_label_from_timestamp(timestamp: Optional[str]) -> Optional[str]:
    if timestamp is None:
        return None
    try:
        current = datetime.fromisoformat(timestamp)
    except ValueError:
        return None
    return "{0:02d}:{1:02d}".format(current.hour, (current.minute // 15) * 15)
