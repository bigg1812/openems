from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from .config import PriceSourceConfig

def _berlin_zone():
    try:
        return ZoneInfo("Europe/Berlin")
    except Exception:
        return None


BERLIN = _berlin_zone()


def berlin_now() -> datetime:
    if BERLIN is not None:
        return datetime.now(BERLIN)
    return datetime.now(_berlin_fallback_tz())


def _berlin_fallback_tz(reference_utc: datetime | None = None):
    reference_utc = reference_utc or datetime.now(timezone.utc)
    year = reference_utc.year
    dst_start = _last_sunday_utc(year, 3)
    dst_end = _last_sunday_utc(year, 10)
    if dst_start <= reference_utc < dst_end:
        return timezone(timedelta(hours=2))
    return timezone(timedelta(hours=1))


def _last_sunday_utc(year: int, month: int) -> datetime:
    if month == 12:
        next_month = datetime(year + 1, 1, 1, 1, tzinfo=timezone.utc)
    else:
        next_month = datetime(year, month + 1, 1, 1, tzinfo=timezone.utc)
    last_day = next_month - timedelta(days=1)
    while last_day.weekday() != 6:
        last_day -= timedelta(days=1)
    return datetime(year, month, last_day.day, 1, tzinfo=timezone.utc)


class PriceProviderError(Exception):
    """Raised when SMARD price data cannot be fetched or normalized."""


@dataclass(frozen=True)
class PriceSnapshot:
    current_price_ct_kwh: float
    current_slot_start_utc: datetime
    tomorrow_hourly_ct_kwh: List[float]
    source_resolution: str


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

    def fetch_snapshot(self) -> PriceSnapshot:
        timestamps = self._fetch_index()
        current_price, current_slot_start = self._fetch_current_price(timestamps)
        tomorrow_prices = self._fetch_tomorrow_prices(timestamps)
        return PriceSnapshot(
            current_price_ct_kwh=current_price,
            current_slot_start_utc=current_slot_start,
            tomorrow_hourly_ct_kwh=tomorrow_prices,
            source_resolution=self.config.resolution,
        )

    def current_slot_index(self, now_local: datetime | None = None) -> int:
        now_local = now_local or berlin_now()
        slots_per_hour = 4 if self.config.resolution == "quarterhour" else 1
        minutes_per_slot = 15 if self.config.resolution == "quarterhour" else 60
        return now_local.hour * slots_per_hour + (now_local.minute // minutes_per_slot)

    def slot_label(self, slot_index: int) -> str:
        if self.config.resolution == "quarterhour":
            hour = slot_index // 4
            minute = (slot_index % 4) * 15
        else:
            hour = slot_index
            minute = 0
        return "{0:02d}:{1:02d}".format(hour, minute)

    def fetch_day_slots(self, target_date: date) -> List[float]:
        slots_by_index = self.fetch_day_slot_map(target_date)
        expected_slots = 24 if self.config.resolution == "hour" else 96
        slots: List[float] = []
        for slot_index in range(expected_slots):
            value = slots_by_index.get(slot_index)
            if value is None:
                raise PriceProviderError(
                    "Missing {0} price for {1} at slot {2}".format(
                        self.config.resolution,
                        target_date.isoformat(),
                        self.slot_label(slot_index),
                    )
                )
            slots.append(value)
        return slots

    def fetch_day_slot_map(self, target_date: date) -> Dict[int, float]:
        result = self.scan_recent_slot_maps([target_date])
        return dict(result.slot_maps_by_date.get(target_date.isoformat(), {}))

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
                dt_local = self._to_berlin_datetime(ts_ms).replace(second=0, microsecond=0)
                slot_index = self._slot_index_for_datetime(dt_local)
                date_iso = dt_local.date().isoformat()

                slots_for_date = raw_slots_by_date.setdefault(date_iso, set())
                slots_for_date.add(slot_index)

                if first_local_dt is None or dt_local < first_local_dt:
                    first_local_dt = dt_local
                if last_local_dt is None or dt_local > last_local_dt:
                    last_local_dt = dt_local

                if date_iso not in target_date_isos:
                    continue
                slot_maps_by_date[date_iso][slot_index] = round(price_eur_mwh * self.config.price_factor, 4)

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

    def _fetch_current_price(self, timestamps: List[int]) -> Tuple[float, datetime]:
        slot_ms = 900_000 if self.config.resolution == "quarterhour" else 3_600_000
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

        for block_ts in reversed(timestamps[-3:]):
            for ts_ms, price_eur_mwh in self._fetch_series(block_ts):
                if price_eur_mwh is not None and ts_ms <= now_ms < ts_ms + slot_ms:
                    return (
                        round(price_eur_mwh * self.config.price_factor, 4),
                        datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc),
                    )
        raise PriceProviderError("No current SMARD price available for the active slot")

    def _fetch_tomorrow_prices(self, timestamps: List[int]) -> List[float]:
        tomorrow = (berlin_now() + timedelta(days=1)).date()
        prices_by_ts: Dict[datetime, float] = {}

        for block_ts in reversed(timestamps[-10:]):
            for ts_ms, price_eur_mwh in self._fetch_series(block_ts):
                if price_eur_mwh is None:
                    continue
                dt_local = self._to_berlin_datetime(ts_ms)
                if dt_local.date() != tomorrow:
                    continue
                normalized_dt = dt_local.replace(second=0, microsecond=0)
                prices_by_ts[normalized_dt] = round(price_eur_mwh * self.config.price_factor, 4)

        if self.config.resolution == "hour":
            return self._extract_hourly_series(tomorrow, prices_by_ts)
        return self._aggregate_quarterhours_to_hours(tomorrow, prices_by_ts)

    def _build_slot_list(self, target_date: date, prices_by_ts: Dict[datetime, float]) -> List[float]:
        slots: List[float] = []
        if self.config.resolution == "hour":
            for hour in range(24):
                dt_local = datetime(
                    target_date.year,
                    target_date.month,
                    target_date.day,
                    hour,
                    0,
                    tzinfo=BERLIN,
                )
                value = prices_by_ts.get(dt_local)
                if value is None:
                    raise PriceProviderError("Missing hourly price for {0}".format(dt_local.isoformat()))
                slots.append(value)
            return slots

        for hour in range(24):
            for minute in (0, 15, 30, 45):
                dt_local = datetime(
                    target_date.year,
                    target_date.month,
                    target_date.day,
                    hour,
                    minute,
                    tzinfo=BERLIN,
                )
                value = prices_by_ts.get(dt_local)
                if value is None:
                    raise PriceProviderError("Missing quarter-hour price for {0}".format(dt_local.isoformat()))
                slots.append(value)
        return slots

    def _extract_hourly_series(self, target_date: date, prices_by_ts: Dict[datetime, float]) -> List[float]:
        hours: List[float] = []
        for hour in range(24):
            dt_local = datetime(
                target_date.year,
                target_date.month,
                target_date.day,
                hour,
                0,
                tzinfo=BERLIN,
            )
            if dt_local not in prices_by_ts:
                raise PriceProviderError("Missing hourly price for {0}".format(dt_local.isoformat()))
            hours.append(prices_by_ts[dt_local])
        return hours

    def _aggregate_quarterhours_to_hours(self, target_date: date, prices_by_ts: Dict[datetime, float]) -> List[float]:
        hours: List[float] = []
        for hour in range(24):
            samples: List[float] = []
            for minute in (0, 15, 30, 45):
                dt_local = datetime(
                    target_date.year,
                    target_date.month,
                    target_date.day,
                    hour,
                    minute,
                    tzinfo=BERLIN,
                )
                value = prices_by_ts.get(dt_local)
                if value is None:
                    raise PriceProviderError("Missing quarter-hour price for {0}".format(dt_local.isoformat()))
                samples.append(value)
            hours.append(round(sum(samples) / 4.0, 4))
        return hours

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
            import requests
        except ModuleNotFoundError as error:
            raise PriceProviderError("requests package is not installed") from error
        try:
            response = requests.get(url, timeout=self.config.timeout_seconds)
            response.raise_for_status()
        except requests.RequestException as error:
            raise PriceProviderError(str(error)) from error
        payload = response.json()
        if not isinstance(payload, dict):
            raise PriceProviderError("SMARD JSON payload has unexpected structure")
        return payload

    def _to_berlin_datetime(self, ts_ms: int) -> datetime:
        dt_utc = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
        if BERLIN is not None:
            return dt_utc.astimezone(BERLIN)
        return dt_utc.astimezone(_berlin_fallback_tz(dt_utc))

    def _slot_index_for_datetime(self, dt_local: datetime) -> int:
        if self.config.resolution == "hour":
            return dt_local.hour
        return dt_local.hour * 4 + (dt_local.minute // 15)
