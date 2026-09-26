"""Reassess receipt age without presenting a cached value as a new measurement."""

from datetime import datetime, timezone
from typing import Optional


def timestamp_age(timestamp: Optional[str], now: datetime) -> Optional[float]:
    if not timestamp:
        return None
    try:
        moment = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
        if moment.tzinfo is None:
            return None
        seconds = (now.astimezone(timezone.utc) - moment).total_seconds()
        return round(seconds, 3) if seconds >= 0 else None
    except (ValueError, TypeError, OverflowError):
        return None


def age_diagnostic(diagnostic: dict, now: datetime) -> dict:
    result = dict(diagnostic)
    # Legacy snapshots without the explicit receipt timestamp remain unchanged.
    if "received_at" not in result:
        return result
    age = timestamp_age(result.get("received_at"), now)
    source_age = timestamp_age(result.get("source_timestamp"), now)
    result.update(age_seconds=age, source_age_seconds=source_age,
                  source_freshness="unknown" if source_age is None else "known")
    if result.get("quality") == "bad":
        return result
    if age is None:
        result.update(quality="bad", status="warning", error="receipt_time_unknown")
    elif result.get("max_age_seconds") is not None and age > float(result["max_age_seconds"]):
        result.update(quality="stale", status="warning", error="value_stale")
    return result
