import json
import math
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Dict, List, Optional, Tuple
from urllib import error, request

from .config import PriceSourceConfig

from .price_time import berlin_now, slot_index, to_berlin


class PriceProviderError(Exception):
    """Raised when SMARD price data cannot be fetched or normalized."""


@dataclass(frozen=True)
class RecentSlotMapScanResult:
    slot_maps_by_date: Dict[str, Dict[int, float]]
    raw_slot_counts_by_date: Dict[str, int]
    first_local_timestamp: Optional[str]
    last_local_timestamp: Optional[str]
    scanned_block_timestamps: List[int]

    def to_dict(self) -> Dict[str, object]:
        target_slot_counts_by_date = {
            date_iso: len(slot_map)
            for date_iso, slot_map in self.slot_maps_by_date.items()
        }
        return {
            "raw_slot_counts_by_date": dict(sorted(self.raw_slot_counts_by_date.items())),
            "target_slot_counts_by_date": dict(sorted(target_slot_counts_by_date.items())),
            "first_local_timestamp": self.first_local_timestamp,
            "last_local_timestamp": self.last_local_timestamp,
            "scanned_block_count": len(self.scanned_block_timestamps),
            "scanned_block_timestamps": list(self.scanned_block_timestamps),
        }


class SmardPriceProvider:
    def __init__(self, config: PriceSourceConfig):
        self.config = config
        self.base_url = "https://www.smard.de/app/chart_data"

    def current_slot_index(self, now_local: datetime | None = None) -> int:
        return slot_index(now_local or berlin_now())

    def scan_recent_slot_maps(self, target_dates: List[date], blocks_to_scan: int = 10) -> RecentSlotMapScanResult:
        timestamps = self._fetch_index()
        target_date_isos = {item.isoformat() for item in target_dates}
        slot_maps_by_date: Dict[str, Dict[int, float]] = {
            date_iso: {}
            for date_iso in target_date_isos
        }
        raw_slots_by_date: Dict[str, set[int]] = {}
        scanned_block_timestamps = list(reversed(timestamps[-blocks_to_scan:]))
        first_local_dt: Optional[datetime] = None
        last_local_dt: Optional[datetime] = None

        for block_ts in scanned_block_timestamps:
            for ts_ms, price_eur_mwh in self._fetch_series(block_ts):
                dt_local = to_berlin(datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc))
                index = slot_index(dt_local)
                date_iso = dt_local.date().isoformat()

                slots_for_date = raw_slots_by_date.setdefault(date_iso, set())
                slots_for_date.update(range(index, index + (4 if self.config.resolution == "hour" else 1)))

                if first_local_dt is None or dt_local < first_local_dt:
                    first_local_dt = dt_local
                if last_local_dt is None or dt_local > last_local_dt:
                    last_local_dt = dt_local

                if date_iso not in target_date_isos:
                    continue
                price = round(price_eur_mwh * self.config.price_factor, 4)
                if not math.isfinite(price):
                    continue
                # Source hours cover four consecutive UTC quarters, including DST days.
                for quarter in range(index, index + (4 if self.config.resolution == "hour" else 1)):
                    slot_maps_by_date[date_iso].setdefault(quarter, price)

        return RecentSlotMapScanResult(
            slot_maps_by_date=slot_maps_by_date,
            raw_slot_counts_by_date={
                date_iso: len(slot_indexes)
                for date_iso, slot_indexes in raw_slots_by_date.items()
            },
            first_local_timestamp=first_local_dt.isoformat() if first_local_dt is not None else None,
            last_local_timestamp=last_local_dt.isoformat() if last_local_dt is not None else None,
            scanned_block_timestamps=scanned_block_timestamps,
        )

    def _fetch_index(self) -> List[int]:
        url = "{0}/{1}/{2}/index_{3}.json".format(
            self.base_url,
            self.config.filter,
            self.config.region,
            self.config.resolution,
        )
        payload = self._get_json(url)
        timestamps = payload.get("timestamps")
        if not isinstance(timestamps, list) or not timestamps:
            raise PriceProviderError("SMARD index returned no timestamps")
        return [int(item) for item in timestamps]

    def _fetch_series(self, block_ts_ms: int) -> List[Tuple[int, float]]:
        url = "{0}/{1}/{2}/{1}_{2}_{3}_{4}.json".format(
            self.base_url,
            self.config.filter,
            self.config.region,
            self.config.resolution,
            block_ts_ms,
        )
        payload = self._get_json(url)
        series = payload.get("series")
        if not isinstance(series, list):
            raise PriceProviderError("SMARD series payload is invalid")

        rows: List[Tuple[int, float]] = []
        for item in series:
            if not isinstance(item, list) or len(item) < 2 or item[1] is None:
                continue
            rows.append((int(item[0]), float(item[1])))
        return rows

    def _get_json(self, url: str) -> Dict[str, object]:
        try:
            http_request = request.Request(url, headers={"User-Agent": "MiniEmsPoC/1.0"})
            with request.urlopen(http_request, timeout=self.config.timeout_seconds) as response:
                raw_payload = response.read()
                charset = response.headers.get_content_charset() or "utf-8"
        except error.HTTPError as exc:
            raise PriceProviderError("SMARD request failed with HTTP {0}".format(exc.code)) from exc
        except (error.URLError, TimeoutError, OSError) as exc:
            raise PriceProviderError(str(exc)) from exc

        try:
            payload = json.loads(raw_payload.decode(charset))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise PriceProviderError("SMARD JSON payload has unexpected structure") from exc

        if not isinstance(payload, dict):
            raise PriceProviderError("SMARD JSON payload has unexpected structure")
        return payload
