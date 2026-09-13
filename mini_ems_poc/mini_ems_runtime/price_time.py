"""Chronological quarter-hour intervals for the German price market.

UTC identifies intervals; Berlin time is only their calendar and display basis.
"""
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from zoneinfo import ZoneInfo

TIME_MODEL = "utc_quarterhours_v1"

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



def to_berlin(moment: datetime) -> datetime:
    if moment.tzinfo is None:
        raise ValueError("Price timestamps require a timezone")
    utc = moment.astimezone(timezone.utc)
    return utc.astimezone(BERLIN or _berlin_fallback_tz(utc))


@lru_cache(maxsize=32)
def day_bounds(date_iso: str) -> tuple[datetime, datetime]:
    day = date.fromisoformat(date_iso)
    bounds = []
    for current in (day, day + timedelta(days=1)):
        # At local midnight the offset matches 00:00 UTC, including transition days.
        reference = datetime.combine(current, datetime.min.time(), timezone.utc)
        zone = BERLIN or _berlin_fallback_tz(reference)
        bounds.append(datetime.combine(current, datetime.min.time(), zone).astimezone(timezone.utc))
    return bounds[0], bounds[1]


def slot_count(date_iso: str) -> int:
    start, end = day_bounds(date_iso)
    return int((end - start).total_seconds() // 900)


def slot_index(moment: datetime) -> int:
    local = to_berlin(moment)
    start, _ = day_bounds(local.date().isoformat())
    return int((moment.astimezone(timezone.utc) - start).total_seconds() // 900)


def slot_start(date_iso: str, index: int) -> datetime:
    if not 0 <= index <= slot_count(date_iso):
        raise ValueError("Price interval outside its market day")
    return day_bounds(date_iso)[0] + timedelta(minutes=15 * index)


def slot_starts(date_iso: str) -> list[str]:
    start, _ = day_bounds(date_iso)
    return [(start + timedelta(minutes=15 * index)).isoformat() for index in range(slot_count(date_iso))]


def slot_label(date_iso: str, index: int) -> str:
    local = to_berlin(slot_start(date_iso, index))
    # Include the offset on both transition days, so repeated labels remain distinct.
    return local.strftime("%H:%M %z" if slot_count(date_iso) != 96 else "%H:%M")
