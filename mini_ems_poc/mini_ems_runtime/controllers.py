from dataclasses import dataclass, field
from typing import Dict, Optional

from .config import GridLockoutConfig


@dataclass
class ControllerOutcome:
    name: str
    valid: bool
    desired_value: bool
    reason: str
    state_name: str
    metrics: Dict[str, object] = field(default_factory=dict)
    safe_mode_required: bool = False

    def to_dict(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "valid": self.valid,
            "desired_value": self.desired_value,
            "reason": self.reason,
            "state_name": self.state_name,
            "metrics": dict(self.metrics),
            "safe_mode_required": self.safe_mode_required,
        }


@dataclass
class GridLockoutState:
    mode: str = "monitoring"
    below_threshold_counter: int = 0

    def to_dict(self) -> Dict[str, object]:
        return {
            "mode": self.mode,
            "below_threshold_counter": self.below_threshold_counter,
        }

    @classmethod
    def from_dict(cls, raw: Optional[Dict[str, object]]) -> "GridLockoutState":
        raw = raw or {}
        return cls(
            mode=str(raw.get("mode", "monitoring")),
            below_threshold_counter=int(raw.get("below_threshold_counter", 0)),
        )


@dataclass
class SpotMarketLockoutState:
    # Legacy state.json round-trip only; current control uses SpotmarketPlanWriter.
    mode: str = "normal"
    longest_negative_block_quarters: int = 0

    def to_dict(self) -> Dict[str, object]:
        return {
            "mode": self.mode,
            "longest_negative_block_quarters": self.longest_negative_block_quarters,
        }

    @classmethod
    def from_dict(cls, raw: Optional[Dict[str, object]]) -> "SpotMarketLockoutState":
        raw = raw or {}
        return cls(
            mode=str(raw.get("mode", "normal")),
            longest_negative_block_quarters=int(
                raw.get(
                    "longest_negative_block_quarters",
                    raw.get("longest_negative_block", 0),
                )
            ),
        )


class GridLockoutController:
    def __init__(self, config: GridLockoutConfig):
        self.config = config

    def evaluate(self, active_power_kw: Optional[float], state: GridLockoutState) -> ControllerOutcome:
        if active_power_kw is None:
            return ControllerOutcome(
                name="grid_lockout",
                valid=False,
                desired_value=False,
                reason="Grid active power is missing",
                state_name=state.mode,
                safe_mode_required=True,
            )

        if state.mode == "lockout_active":
            if active_power_kw >= self.config.clear_threshold_kw:
                state.mode = "monitoring"
                state.below_threshold_counter = 0
                return ControllerOutcome(
                    name="grid_lockout",
                    valid=True,
                    desired_value=False,
                    reason="Active power recovered above clear threshold",
                    state_name=state.mode,
                    metrics={
                        "active_power_kw": active_power_kw,
                        "below_threshold_counter": state.below_threshold_counter,
                    },
                )
            return ControllerOutcome(
                name="grid_lockout",
                valid=True,
                desired_value=True,
                reason="Lockout stays active until clear threshold is reached",
                state_name=state.mode,
                metrics={
                    "active_power_kw": active_power_kw,
                    "below_threshold_counter": state.below_threshold_counter,
                },
            )

        if active_power_kw < self.config.threshold_kw:
            state.below_threshold_counter += 1
            if state.below_threshold_counter >= self.config.below_threshold_cycles_required:
                state.mode = "lockout_active"
                return ControllerOutcome(
                    name="grid_lockout",
                    valid=True,
                    desired_value=True,
                    reason="Active power stayed below threshold for required cycles",
                    state_name=state.mode,
                    metrics={
                        "active_power_kw": active_power_kw,
                        "below_threshold_counter": state.below_threshold_counter,
                    },
                )
            state.mode = "below_threshold_pending"
            return ControllerOutcome(
                name="grid_lockout",
                valid=True,
                desired_value=False,
                reason="Waiting for additional below-threshold cycles",
                state_name=state.mode,
                metrics={
                    "active_power_kw": active_power_kw,
                    "below_threshold_counter": state.below_threshold_counter,
                },
            )

        state.mode = "monitoring"
        state.below_threshold_counter = 0
        return ControllerOutcome(
            name="grid_lockout",
            valid=True,
            desired_value=False,
            reason="Active power is inside normal operating range",
            state_name=state.mode,
            metrics={
                "active_power_kw": active_power_kw,
                "below_threshold_counter": state.below_threshold_counter,
            },
        )
