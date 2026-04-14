import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, Optional

from .controllers import GridLockoutState, SpotMarketLockoutState


@dataclass
class OutputState:
    value: object = False
    is_confirmed: bool = False
    last_confirmed_at: Optional[str] = None
    last_error: Optional[str] = None
    last_confirmation_mode: Optional[str] = None
    last_readback_value: Optional[float] = None

    def to_dict(self) -> Dict[str, object]:
        return {
            "value": self.value,
            "is_confirmed": self.is_confirmed,
            "last_confirmed_at": self.last_confirmed_at,
            "last_error": self.last_error,
            "last_confirmation_mode": self.last_confirmation_mode,
            "last_readback_value": self.last_readback_value,
        }

    @classmethod
    def from_dict(cls, raw: Optional[Dict[str, object]]) -> "OutputState":
        raw = raw or {}
        return cls(
            value=raw.get("value", False),
            is_confirmed=bool(raw.get("is_confirmed", False)),
            last_confirmed_at=_optional_string(raw.get("last_confirmed_at")),
            last_error=_optional_string(raw.get("last_error")),
            last_confirmation_mode=_optional_string(raw.get("last_confirmation_mode")),
            last_readback_value=_optional_float(raw.get("last_readback_value")),
        )


@dataclass
class HealthState:
    safe_mode_active: bool = False
    safe_mode_reason: Optional[str] = None
    safe_outputs_confirmed: bool = False
    consecutive_comm_errors: int = 0
    last_successful_cycle_id: Optional[str] = None
    last_successful_at: Optional[str] = None
    last_healthy_cycle_id: Optional[str] = None
    last_healthy_at: Optional[str] = None
    last_degraded_cycle_id: Optional[str] = None
    last_degraded_at: Optional[str] = None
    last_degraded_reason: Optional[str] = None
    last_cycle_id: Optional[str] = None
    last_cycle_at: Optional[str] = None
    last_price_handoff_at: Optional[str] = None
    last_price_handoff_slot_label: Optional[str] = None
    last_price_handoff_value_ct_kwh: Optional[float] = None
    cycle_counter: int = 0

    def to_dict(self) -> Dict[str, object]:
        return {
            "safe_mode_active": self.safe_mode_active,
            "safe_mode_reason": self.safe_mode_reason,
            "safe_outputs_confirmed": self.safe_outputs_confirmed,
            "consecutive_comm_errors": self.consecutive_comm_errors,
            "last_successful_cycle_id": self.last_successful_cycle_id,
            "last_successful_at": self.last_successful_at,
            "last_healthy_cycle_id": self.last_healthy_cycle_id,
            "last_healthy_at": self.last_healthy_at,
            "last_degraded_cycle_id": self.last_degraded_cycle_id,
            "last_degraded_at": self.last_degraded_at,
            "last_degraded_reason": self.last_degraded_reason,
            "last_cycle_id": self.last_cycle_id,
            "last_cycle_at": self.last_cycle_at,
            "last_price_handoff_at": self.last_price_handoff_at,
            "last_price_handoff_slot_label": self.last_price_handoff_slot_label,
            "last_price_handoff_value_ct_kwh": self.last_price_handoff_value_ct_kwh,
            "cycle_counter": self.cycle_counter,
        }

    @classmethod
    def from_dict(cls, raw: Optional[Dict[str, object]]) -> "HealthState":
        raw = raw or {}
        return cls(
            safe_mode_active=bool(raw.get("safe_mode_active", False)),
            safe_mode_reason=_optional_string(raw.get("safe_mode_reason")),
            safe_outputs_confirmed=bool(raw.get("safe_outputs_confirmed", False)),
            consecutive_comm_errors=int(raw.get("consecutive_comm_errors", 0)),
            last_successful_cycle_id=_optional_string(raw.get("last_successful_cycle_id")),
            last_successful_at=_optional_string(raw.get("last_successful_at")),
            last_healthy_cycle_id=_optional_string(raw.get("last_healthy_cycle_id")),
            last_healthy_at=_optional_string(raw.get("last_healthy_at")),
            last_degraded_cycle_id=_optional_string(raw.get("last_degraded_cycle_id")),
            last_degraded_at=_optional_string(raw.get("last_degraded_at")),
            last_degraded_reason=_optional_string(raw.get("last_degraded_reason")),
            last_cycle_id=_optional_string(raw.get("last_cycle_id")),
            last_cycle_at=_optional_string(raw.get("last_cycle_at")),
            last_price_handoff_at=_optional_string(raw.get("last_price_handoff_at")),
            last_price_handoff_slot_label=_optional_string(raw.get("last_price_handoff_slot_label")),
            last_price_handoff_value_ct_kwh=_optional_float(raw.get("last_price_handoff_value_ct_kwh")),
            cycle_counter=int(raw.get("cycle_counter", 0)),
        )


@dataclass
class RuntimeState:
    version: int = 2
    grid_lockout: GridLockoutState = field(default_factory=GridLockoutState)
    spotmarket_lockout: SpotMarketLockoutState = field(default_factory=SpotMarketLockoutState)
    outputs: Dict[str, OutputState] = field(default_factory=dict)
    health: HealthState = field(default_factory=HealthState)

    def to_dict(self) -> Dict[str, object]:
        return {
            "version": self.version,
            "grid_lockout": self.grid_lockout.to_dict(),
            "spotmarket_lockout": self.spotmarket_lockout.to_dict(),
            "outputs": {channel_id: state.to_dict() for channel_id, state in self.outputs.items()},
            "health": self.health.to_dict(),
        }

    @classmethod
    def create_default(cls, output_channel_ids: Iterable[str]) -> "RuntimeState":
        return cls(outputs={channel_id: OutputState() for channel_id in output_channel_ids})

    @classmethod
    def from_dict(cls, raw: Dict[str, object], output_channel_ids: Iterable[str]) -> "RuntimeState":
        outputs = {}
        raw_outputs = raw.get("outputs", {})
        if not isinstance(raw_outputs, dict):
            raw_outputs = {}
        for channel_id in output_channel_ids:
            outputs[channel_id] = OutputState.from_dict(raw_outputs.get(channel_id))
        raw_version = raw.get("version", 2)
        try:
            version = int(raw_version)
        except (TypeError, ValueError):
            version = 2
        return cls(
            version=max(2, version),
            grid_lockout=GridLockoutState.from_dict(raw.get("grid_lockout")),
            spotmarket_lockout=SpotMarketLockoutState.from_dict(raw.get("spotmarket_lockout")),
            outputs=outputs,
            health=HealthState.from_dict(raw.get("health")),
        )


class StateStore:
    def __init__(self, path: Path, output_channel_ids: Iterable[str]):
        self.path = Path(path)
        self.output_channel_ids = list(output_channel_ids)

    def load(self) -> RuntimeState:
        if not self.path.exists():
            return RuntimeState.create_default(self.output_channel_ids)
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            state = RuntimeState.create_default(self.output_channel_ids)
            state.health.safe_mode_active = True
            state.health.safe_mode_reason = "state_file_invalid"
            return state
        return RuntimeState.from_dict(raw, self.output_channel_ids)

    def save(self, state: RuntimeState) -> None:
        write_json_atomic(self.path, state.to_dict())


def write_json_atomic(path: Path, payload: Dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(temp_path, path)


def _optional_string(value: object) -> Optional[str]:
    if value is None:
        return None
    return str(value)


def _optional_float(value: object) -> Optional[float]:
    if value is None:
        return None
    return float(value)
