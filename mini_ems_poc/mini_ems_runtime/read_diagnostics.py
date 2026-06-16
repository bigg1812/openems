import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional

from .bacnet import BacnetAdapter, BacnetError
from .channels import ChannelRegistry
from .logging_utils import log_event

# Quality flags carried by every read; surfaced into health.json / SQLite / dashboard.
QUALITY_GOOD = "good"
QUALITY_STALE = "stale"
QUALITY_BAD = "bad"


def _real_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_iso(moment: datetime) -> str:
    # Mirror logging_utils.utcnow_iso() formatting so existing payloads are unchanged.
    return moment.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class ChannelReadSample:
    timestamp: str
    value: float

    def to_dict(self) -> Dict[str, object]:
        return {
            "timestamp": self.timestamp,
            "value": self.value,
        }


@dataclass(frozen=True)
class ChannelReadDiagnostic:
    channel_id: str
    status: str
    value: Optional[float]
    sample_count: int
    successful_sample_count: int
    samples: List[ChannelReadSample] = field(default_factory=list)
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    average_value: Optional[float] = None
    plausible: bool = True
    error: Optional[str] = None
    sender_validation: str = "controller_only"
    quality: str = QUALITY_GOOD
    age_seconds: Optional[float] = None
    max_age_seconds: Optional[float] = None

    def to_dict(self) -> Dict[str, object]:
        return {
            "channel_id": self.channel_id,
            "status": self.status,
            "value": self.value,
            "sample_count": self.sample_count,
            "successful_sample_count": self.successful_sample_count,
            "samples": [sample.to_dict() for sample in self.samples],
            "min_value": self.min_value,
            "max_value": self.max_value,
            "average_value": self.average_value,
            "plausible": self.plausible,
            "error": self.error,
            "sender_validation": self.sender_validation,
            "quality": self.quality,
            "age_seconds": self.age_seconds,
            "max_age_seconds": self.max_age_seconds,
        }


class ChannelReadDiagnosticsService:
    def __init__(
        self,
        registry: ChannelRegistry,
        adapter: BacnetAdapter,
        logger: logging.Logger,
        now: Optional[Callable[[], datetime]] = None,
    ):
        self.registry = registry
        self.adapter = adapter
        self.logger = logger
        # Injectable clock (aware UTC datetime) so freshness logic is testable
        # without monkeypatching; defaults to the real wall clock.
        self._now = now or _real_now

    def read_float_channel(
        self,
        channel_id: str,
        samples: int = 1,
        delay_seconds: float = 0.0,
        plausible_min: Optional[float] = None,
        plausible_max: Optional[float] = None,
        max_age_seconds: Optional[float] = None,
    ) -> ChannelReadDiagnostic:
        point = self.registry.get(channel_id)
        collected_samples: List[ChannelReadSample] = []
        sample_moments: List[datetime] = []
        errors: List[str] = []

        for sample_index in range(max(1, int(samples))):
            try:
                value = self.adapter.read_float(point)
                moment = self._now()
                sample_moments.append(moment)
                collected_samples.append(
                    ChannelReadSample(timestamp=_to_iso(moment), value=float(value))
                )
            except BacnetError as error:
                errors.append(str(error))
                break

            if sample_index < max(1, int(samples)) - 1 and delay_seconds > 0:
                time.sleep(delay_seconds)

        values = [sample.value for sample in collected_samples]
        plausible = _is_plausible(values, plausible_min, plausible_max)
        average_value = round(sum(values) / len(values), 4) if values else None
        min_value = round(min(values), 4) if values else None
        max_value = round(max(values), 4) if values else None
        current_value = collected_samples[-1].value if collected_samples else None
        status = "ok" if values and not errors and plausible else "error" if not values else "warning"
        error = "; ".join(errors) if errors else None

        # Age of the freshest valid sample, measured at evaluation time against
        # the same injectable clock. None when there is no valid sample.
        age_seconds: Optional[float] = None
        if sample_moments:
            age_seconds = max(0.0, round((self._now() - sample_moments[-1]).total_seconds(), 3))

        quality = _classify_quality(
            has_value=bool(values),
            status=status,
            age_seconds=age_seconds,
            max_age_seconds=max_age_seconds,
        )
        # A fresh-but-stale value must not be silently accepted as "ok": demote it
        # to "warning" so existing status-based handling reacts, and annotate error.
        if quality == QUALITY_STALE and status == "ok":
            status = "warning"
            if error is None:
                error = "value_stale"

        diagnostic = ChannelReadDiagnostic(
            channel_id=channel_id,
            status=status,
            value=current_value,
            sample_count=max(1, int(samples)),
            successful_sample_count=len(collected_samples),
            samples=collected_samples,
            min_value=min_value,
            max_value=max_value,
            average_value=average_value,
            plausible=plausible,
            error=error if error is not None else None if plausible else "value_out_of_range",
            quality=quality,
            age_seconds=age_seconds,
            max_age_seconds=max_age_seconds,
        )
        log_event(
            self.logger,
            logging.INFO if diagnostic.status == "ok" else logging.WARNING,
            "bacnet.read_diagnostic",
            channel_id=channel_id,
            status=diagnostic.status,
            value=diagnostic.value,
            sample_count=diagnostic.sample_count,
            successful_sample_count=diagnostic.successful_sample_count,
            min_value=diagnostic.min_value,
            max_value=diagnostic.max_value,
            average_value=diagnostic.average_value,
            plausible=diagnostic.plausible,
            error=diagnostic.error,
            quality=diagnostic.quality,
            age_seconds=diagnostic.age_seconds,
            max_age_seconds=diagnostic.max_age_seconds,
        )
        return diagnostic


def _classify_quality(
    *,
    has_value: bool,
    status: str,
    age_seconds: Optional[float],
    max_age_seconds: Optional[float],
) -> str:
    # No usable value (failed read or implausible) -> bad.
    if not has_value or status == "error":
        return QUALITY_BAD
    # No freshness requirement configured -> preserve current behavior (always good).
    if max_age_seconds is None or age_seconds is None:
        return QUALITY_GOOD
    if age_seconds > max_age_seconds:
        return QUALITY_STALE
    return QUALITY_GOOD


def _is_plausible(values: List[float], plausible_min: Optional[float], plausible_max: Optional[float]) -> bool:
    if not values:
        return False
    for value in values:
        if plausible_min is not None and value < plausible_min:
            return False
        if plausible_max is not None and value > plausible_max:
            return False
    return True
