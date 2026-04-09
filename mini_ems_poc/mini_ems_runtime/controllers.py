from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from .config import GridLockoutConfig, SpotMarketLockoutConfig


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


class SpotMarketLockoutController:
    def __init__(self, config: SpotMarketLockoutConfig):
        self.config = config

    def evaluate(self, prices: Sequence[Optional[float]], state: SpotMarketLockoutState) -> ControllerOutcome:
        if len(prices) != 96:
            return ControllerOutcome(
                name="spotmarket_lockout",
                valid=False,
                desired_value=False,
                reason="Expected 96 quarter-hour prices, got {0}".format(len(prices)),
                state_name=state.mode,
                safe_mode_required=True,
            )

        invalid_quarters: List[int] = []
        valid_prices: List[float] = []
        longest_block = 0
        current_block = 0
        negative_quarters: List[int] = []

        for quarter_index, price in enumerate(prices):
            if price is None or self._is_invalid_sentinel(price):
                invalid_quarters.append(quarter_index)
                current_block = 0
                continue
            valid_prices.append(price)
            if price <= 0:
                negative_quarters.append(quarter_index)
                current_block += 1
                if current_block > longest_block:
                    longest_block = current_block
            else:
                current_block = 0

        state.longest_negative_block_quarters = longest_block

        if len(valid_prices) < self.config.min_valid_quarters:
            state.mode = "invalid_input"
            return ControllerOutcome(
                name="spotmarket_lockout",
                valid=False,
                desired_value=False,
                reason="Only {0}/96 valid quarter-hour prices available".format(len(valid_prices)),
                state_name=state.mode,
                metrics={
                    "valid_quarters": len(valid_prices),
                    "invalid_quarters": invalid_quarters,
                },
                safe_mode_required=True,
            )

        desired_value = longest_block >= self.config.negative_quarters_min_consecutive
        state.mode = "lockout_active" if desired_value else "normal"
        return ControllerOutcome(
            name="spotmarket_lockout",
            valid=True,
            desired_value=desired_value,
            reason=(
                "Negative price block reached threshold"
                if desired_value
                else "Negative price block below threshold"
            ),
            state_name=state.mode,
            metrics={
                "valid_quarters": len(valid_prices),
                "invalid_quarters": invalid_quarters,
                "negative_quarters": negative_quarters,
                "longest_negative_block_quarters": longest_block,
            },
        )

    def _is_invalid_sentinel(self, value: float) -> bool:
        sentinel = self.config.invalid_price_sentinel
        if sentinel is None:
            return False
        return abs(value - sentinel) < 1e-9
