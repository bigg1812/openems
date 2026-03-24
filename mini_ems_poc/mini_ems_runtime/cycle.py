import logging
import time
from typing import Dict, List, Optional

from .bacnet import BacnetAdapter, BacnetCommunicationError, BacnetError
from .channels import (
    GRID_ACTIVE_POWER_CHANNEL,
    GRID_LOCKOUT_CHANNEL,
    SPOTMARKET_LOCKOUT_CHANNEL,
    ChannelRegistry,
)
from .config import MiniEmsConfig
from .controllers import GridLockoutController, SpotMarketLockoutController
from .logging_utils import log_event, utcnow_iso
from .state_store import StateStore, write_json_atomic


class CycleRunner:
    def __init__(
        self,
        config: MiniEmsConfig,
        registry: ChannelRegistry,
        adapter: BacnetAdapter,
        state_store: StateStore,
        logger: logging.Logger,
    ):
        self.config = config
        self.registry = registry
        self.adapter = adapter
        self.state_store = state_store
        self.logger = logger
        self.state = state_store.load()
        self.grid_controller = GridLockoutController(config.controllers.grid_lockout)
        self.spotmarket_controller = SpotMarketLockoutController(config.controllers.spotmarket_lockout)
        if not self.state.health.safe_mode_active:
            self.state.health.safe_mode_active = True
            self.state.health.safe_mode_reason = "startup_validation"

    def run_cycle(self) -> Dict[str, object]:
        cycle_id = self._next_cycle_id()
        timestamp = utcnow_iso()
        self.state.health.last_cycle_id = cycle_id
        self.state.health.last_cycle_at = timestamp

        log_event(
            self.logger,
            logging.INFO,
            "cycle.start",
            cycle_id=cycle_id,
            safe_mode_active=self.state.health.safe_mode_active,
            safe_mode_reason=self.state.health.safe_mode_reason,
        )

        readings, read_errors = self._read_inputs(cycle_id)
        if read_errors:
            self.state.health.consecutive_comm_errors += 1
        else:
            self.state.health.consecutive_comm_errors = 0

        grid_outcome = self.grid_controller.evaluate(
            readings.get(GRID_ACTIVE_POWER_CHANNEL),
            self.state.grid_lockout,
        )
        prices = [readings.get(channel_id) for channel_id in self.registry.price_channel_ids()]
        spot_outcome = self.spotmarket_controller.evaluate(prices, self.state.spotmarket_lockout)

        controller_outcomes = {
            "grid_lockout": grid_outcome.to_dict(),
            "spotmarket_lockout": spot_outcome.to_dict(),
        }

        unhealthy_reasons = list(read_errors)
        if (
            read_errors
            and self.state.health.consecutive_comm_errors >= self.config.safety.comm_error_safe_mode_threshold
        ):
            unhealthy_reasons.append(
                "comm_error_threshold_reached:{0}".format(self.state.health.consecutive_comm_errors)
            )
        for outcome in (grid_outcome, spot_outcome):
            if not outcome.valid or outcome.safe_mode_required:
                unhealthy_reasons.append(outcome.reason)

        if unhealthy_reasons:
            snapshot = self._handle_unhealthy_cycle(
                cycle_id=cycle_id,
                timestamp=timestamp,
                reason="; ".join(unhealthy_reasons),
                controller_outcomes=controller_outcomes,
                read_errors=read_errors,
            )
            self._persist(snapshot)
            return snapshot

        desired_outputs = {
            GRID_LOCKOUT_CHANNEL: bool(grid_outcome.desired_value),
            SPOTMARKET_LOCKOUT_CHANNEL: bool(spot_outcome.desired_value),
        }

        try:
            write_results = self._apply_outputs(desired_outputs, cycle_id, timestamp)
        except BacnetError as error:
            self.state.health.consecutive_comm_errors += 1
            reason = "write_failure: {0}".format(error)
            if self.state.health.consecutive_comm_errors >= self.config.safety.comm_error_safe_mode_threshold:
                reason = "{0}; comm_error_threshold_reached:{1}".format(
                    reason,
                    self.state.health.consecutive_comm_errors,
                )
            snapshot = self._handle_unhealthy_cycle(
                cycle_id=cycle_id,
                timestamp=timestamp,
                reason=reason,
                controller_outcomes=controller_outcomes,
                read_errors=read_errors,
            )
            self._persist(snapshot)
            return snapshot

        self.state.health.safe_mode_active = False
        self.state.health.safe_mode_reason = None
        self.state.health.safe_outputs_confirmed = False
        self.state.health.last_healthy_cycle_id = cycle_id
        self.state.health.last_healthy_at = timestamp

        snapshot = {
            "timestamp": timestamp,
            "cycle_id": cycle_id,
            "status": "healthy",
            "safe_mode_active": self.state.health.safe_mode_active,
            "safe_mode_reason": self.state.health.safe_mode_reason,
            "consecutive_comm_errors": self.state.health.consecutive_comm_errors,
            "read_errors": read_errors,
            "controller_outcomes": controller_outcomes,
            "desired_outputs": desired_outputs,
            "write_results": write_results,
            "outputs": self._outputs_snapshot(),
        }
        log_event(
            self.logger,
            logging.INFO,
            "cycle.healthy",
            cycle_id=cycle_id,
            desired_outputs=desired_outputs,
            write_results=write_results,
        )
        self._persist(snapshot)
        return snapshot

    def _read_inputs(self, cycle_id: str) -> (Dict[str, Optional[float]], List[str]):
        readings: Dict[str, Optional[float]] = {}
        errors: List[str] = []

        for channel_id in [GRID_ACTIVE_POWER_CHANNEL] + self.registry.price_channel_ids():
            point = self.registry.get(channel_id)
            try:
                readings[channel_id] = self.adapter.read_float(point)
            except BacnetCommunicationError as error:
                readings[channel_id] = None
                message = "{0}: {1}".format(channel_id, error)
                errors.append(message)
                log_event(
                    self.logger,
                    logging.ERROR,
                    "cycle.read_failed",
                    cycle_id=cycle_id,
                    channel_id=channel_id,
                    error=str(error),
                )
            if channel_id != self.registry.price_channel_ids()[-1] and self.config.timing.inter_read_delay_seconds > 0:
                time.sleep(self.config.timing.inter_read_delay_seconds)
        return readings, errors

    def _apply_outputs(self, desired_outputs: Dict[str, bool], cycle_id: str, timestamp: str) -> Dict[str, object]:
        results: Dict[str, object] = {}
        for channel_id, desired_value in desired_outputs.items():
            output_state = self.state.outputs[channel_id]
            needs_write = (not output_state.is_confirmed) or output_state.value != desired_value
            if not needs_write:
                results[channel_id] = {
                    "changed": False,
                    "confirmed_value": output_state.value,
                    "last_confirmed_at": output_state.last_confirmed_at,
                }
                continue

            point = self.registry.get(channel_id)
            self.adapter.write_bool(point, desired_value)
            output_state.value = desired_value
            output_state.is_confirmed = True
            output_state.last_confirmed_at = timestamp
            output_state.last_error = None
            results[channel_id] = {
                "changed": True,
                "confirmed_value": desired_value,
                "last_confirmed_at": timestamp,
            }
            log_event(
                self.logger,
                logging.INFO,
                "cycle.output_confirmed",
                cycle_id=cycle_id,
                channel_id=channel_id,
                confirmed_value=desired_value,
            )
        return results

    def _handle_unhealthy_cycle(
        self,
        cycle_id: str,
        timestamp: str,
        reason: str,
        controller_outcomes: Dict[str, object],
        read_errors: List[str],
    ) -> Dict[str, object]:
        self.state.health.safe_mode_active = True
        self.state.health.safe_mode_reason = reason

        safe_write_results = self._enforce_safe_outputs(cycle_id, timestamp)
        snapshot = {
            "timestamp": timestamp,
            "cycle_id": cycle_id,
            "status": "safe_mode",
            "safe_mode_active": self.state.health.safe_mode_active,
            "safe_mode_reason": self.state.health.safe_mode_reason,
            "consecutive_comm_errors": self.state.health.consecutive_comm_errors,
            "read_errors": read_errors,
            "controller_outcomes": controller_outcomes,
            "desired_outputs": {
                GRID_LOCKOUT_CHANNEL: self.config.safety.fail_safe_output,
                SPOTMARKET_LOCKOUT_CHANNEL: self.config.safety.fail_safe_output,
            },
            "write_results": safe_write_results,
            "outputs": self._outputs_snapshot(),
        }
        log_event(
            self.logger,
            logging.ERROR,
            "cycle.safe_mode",
            cycle_id=cycle_id,
            reason=reason,
            safe_write_results=safe_write_results,
        )
        return snapshot

    def _enforce_safe_outputs(self, cycle_id: str, timestamp: str) -> Dict[str, object]:
        safe_value = bool(self.config.safety.fail_safe_output)
        results: Dict[str, object] = {}
        all_confirmed = True

        for channel_id in self.registry.output_channel_ids():
            output_state = self.state.outputs[channel_id]
            needs_write = (not output_state.is_confirmed) or output_state.value != safe_value
            if not needs_write:
                results[channel_id] = {
                    "changed": False,
                    "confirmed_value": output_state.value,
                    "last_confirmed_at": output_state.last_confirmed_at,
                }
                continue
            try:
                self.adapter.write_bool(self.registry.get(channel_id), safe_value)
                output_state.value = safe_value
                output_state.is_confirmed = True
                output_state.last_confirmed_at = timestamp
                output_state.last_error = None
                results[channel_id] = {
                    "changed": True,
                    "confirmed_value": safe_value,
                    "last_confirmed_at": timestamp,
                }
            except BacnetError as error:
                all_confirmed = False
                output_state.last_error = str(error)
                results[channel_id] = {
                    "changed": True,
                    "error": str(error),
                }
                log_event(
                    self.logger,
                    logging.ERROR,
                    "cycle.safe_output_failed",
                    cycle_id=cycle_id,
                    channel_id=channel_id,
                    error=str(error),
                )
        self.state.health.safe_outputs_confirmed = all_confirmed and all(
            output.value == safe_value and output.is_confirmed
            for output in self.state.outputs.values()
        )
        return results

    def _outputs_snapshot(self) -> Dict[str, object]:
        return {
            channel_id: output_state.to_dict()
            for channel_id, output_state in self.state.outputs.items()
        }

    def _persist(self, snapshot: Dict[str, object]) -> None:
        self.state_store.save(self.state)
        write_json_atomic(self.config.health_path, snapshot)

    def _next_cycle_id(self) -> str:
        self.state.health.cycle_counter += 1
        return "cycle-{0:06d}".format(self.state.health.cycle_counter)
