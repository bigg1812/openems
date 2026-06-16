import logging
from typing import Dict, List, Optional, Sequence, Tuple

from .bacnet import BacnetAdapter
from .channels import (
    CURRENT_PRICE_CHANNEL,
    GRID_ACTIVE_POWER_CHANNEL,
    GRID_LOCKOUT_CHANNEL,
    SPOTMARKET_LOCKOUT_CHANNEL,
    ChannelRegistry,
)
from .config import MiniEmsConfig, OutputPolicyConfig
from .controllers import ControllerOutcome, GridLockoutController
from .logging_utils import log_event, utcnow_iso
from .operator_status import build_operator_message
from .price_cache import PublishedPriceSnapshot, SpotmarketPriceCacheService
from .price_provider_smard import PriceProviderError
from .read_diagnostics import ChannelReadDiagnostic, ChannelReadDiagnosticsService
from .runtime_db import RuntimeDatabase
from .spotmarket_plan import SpotmarketManualOverrideStore, SpotmarketPlanWriter
from .state_store import StateStore, write_json_atomic


class CycleRunner:
    def __init__(
        self,
        config: MiniEmsConfig,
        registry: ChannelRegistry,
        adapter: BacnetAdapter,
        state_store: StateStore,
        logger: logging.Logger,
        price_service: SpotmarketPriceCacheService,
        spotmarket_plan_writer: SpotmarketPlanWriter,
        spotmarket_override_store: SpotmarketManualOverrideStore,
        read_diagnostics: ChannelReadDiagnosticsService,
        runtime_db: RuntimeDatabase,
    ):
        self.config = config
        self.registry = registry
        self.adapter = adapter
        self.state_store = state_store
        self.logger = logger
        self.price_service = price_service
        self.spotmarket_plan_writer = spotmarket_plan_writer
        self.spotmarket_override_store = spotmarket_override_store
        self.read_diagnostics = read_diagnostics
        self.runtime_db = runtime_db
        self.grid_controller = GridLockoutController(config.controllers.grid_lockout)
        self.state = state_store.load()
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

        force_confirmation = self.state.health.safe_mode_reason == "startup_validation"
        input_reads: Dict[str, Dict[str, object]] = {}
        controller_outcomes: Dict[str, object] = {}

        try:
            price_snapshot = self.price_service.refresh()
        except PriceProviderError as error:
            self.state.health.consecutive_comm_errors += 1
            snapshot = self._handle_safe_mode(
                cycle_id=cycle_id,
                timestamp=timestamp,
                reason="price_provider: {0}".format(error),
                price_snapshot=None,
                input_reads=input_reads,
                controller_outcomes=controller_outcomes,
                desired_outputs={},
                write_results={},
                spotmarket_plan=None,
                spotmarket_active_now=None,
                spotmarket_source=None,
                spotmarket_next_window=None,
                spotmarket_override=None,
                degraded_reason=None,
            )
            self._persist(snapshot, input_reads=input_reads, price_snapshot=None, spotmarket_plan=None)
            return snapshot

        if self.config.controllers.grid_lockout.enabled:
            grid_point = self.registry.get(GRID_ACTIVE_POWER_CHANNEL)
            grid_read = self.read_diagnostics.read_float_channel(
                GRID_ACTIVE_POWER_CHANNEL,
                samples=1,
                delay_seconds=self.config.timing.inter_read_delay_seconds,
                plausible_min=grid_point.plausible_min,
                plausible_max=grid_point.plausible_max,
            )
            input_reads[GRID_ACTIVE_POWER_CHANNEL] = grid_read.to_dict()
            if grid_read.status != "ok" or grid_read.value is None:
                self.state.health.consecutive_comm_errors += 1
                snapshot = self._handle_safe_mode(
                    cycle_id=cycle_id,
                    timestamp=timestamp,
                    reason="grid_read: {0}".format(grid_read.error or "grid active power unavailable"),
                    price_snapshot=price_snapshot,
                    input_reads=input_reads,
                    controller_outcomes=controller_outcomes,
                    desired_outputs={},
                    write_results={},
                    spotmarket_plan=None,
                    spotmarket_active_now=None,
                    spotmarket_source=None,
                    spotmarket_next_window=None,
                    spotmarket_override=None,
                    degraded_reason=None,
                )
                self._persist(snapshot, input_reads=input_reads, price_snapshot=price_snapshot, spotmarket_plan=None)
                return snapshot

            grid_outcome = self.grid_controller.evaluate(grid_read.value, self.state.grid_lockout)
            controller_outcomes["grid_lockout"] = grid_outcome.to_dict()
            if not grid_outcome.valid or grid_outcome.safe_mode_required:
                self.state.health.consecutive_comm_errors += 1
                snapshot = self._handle_safe_mode(
                    cycle_id=cycle_id,
                    timestamp=timestamp,
                    reason="grid_lockout: {0}".format(grid_outcome.reason),
                    price_snapshot=price_snapshot,
                    input_reads=input_reads,
                    controller_outcomes=controller_outcomes,
                    desired_outputs={},
                    write_results={},
                    spotmarket_plan=None,
                    spotmarket_active_now=None,
                    spotmarket_source=None,
                    spotmarket_next_window=None,
                    spotmarket_override=None,
                    degraded_reason=None,
                )
                self._persist(snapshot, input_reads=input_reads, price_snapshot=price_snapshot, spotmarket_plan=None)
                return snapshot
        else:
            grid_outcome = ControllerOutcome(
                name="grid_lockout",
                valid=True,
                desired_value=False,
                reason="Grid lockout disabled; AV300 is not used for control",
                state_name="disabled",
                metrics={},
                safe_mode_required=False,
            )
            controller_outcomes["grid_lockout"] = grid_outcome.to_dict()

        for channel_id in self.registry.additional_input_channel_ids():
            point = self.registry.get(channel_id)
            if not self._should_read_additional_input(point, force_confirmation=force_confirmation):
                continue
            diagnostic = self.read_diagnostics.read_float_channel(
                channel_id,
                samples=1,
                delay_seconds=self.config.timing.inter_read_delay_seconds,
                plausible_min=point.plausible_min,
                plausible_max=point.plausible_max,
            )
            input_reads[channel_id] = diagnostic.to_dict()
            if diagnostic.status != "ok":
                log_event(
                    self.logger,
                    logging.WARNING,
                    "cycle.input_warning",
                    cycle_id=cycle_id,
                    channel_id=channel_id,
                    status=diagnostic.status,
                    error=diagnostic.error,
                )

        spotmarket_plan = self.spotmarket_plan_writer.write_plan(
            generated_at=price_snapshot.last_update_at,
            today_date_iso=price_snapshot.today_date_iso,
            today_slots=price_snapshot.today_slots,
            tomorrow_date_iso=price_snapshot.tomorrow_date_iso,
            tomorrow_slots=price_snapshot.tomorrow_slots,
            current_slot_index=price_snapshot.current_slot_index,
        )
        manual_override = self.spotmarket_override_store.load_for_date(price_snapshot.today_date_iso)
        spotmarket_active_now = (
            manual_override.active_now(price_snapshot.current_slot_index)
            if manual_override.enabled
            else bool(spotmarket_plan["active_today_now"])
        )
        spotmarket_next_window = (
            manual_override.next_window(price_snapshot.current_slot_index).to_dict()
            if manual_override.enabled and manual_override.next_window(price_snapshot.current_slot_index) is not None
            else spotmarket_plan["next_today_window"]
        )
        spotmarket_source = "manual_override" if manual_override.enabled else "computed_plan"
        controller_outcomes["spotmarket_lockout"] = {
            "name": "spotmarket_lockout",
            "source": spotmarket_source,
            "desired_value": spotmarket_active_now,
            "today_window_count": spotmarket_plan["today"]["window_count"],
            "tomorrow_window_count": spotmarket_plan["tomorrow"]["window_count"],
        }

        desired_outputs = {}
        if self.config.controllers.grid_lockout.enabled:
            desired_outputs[GRID_LOCKOUT_CHANNEL] = bool(grid_outcome.desired_value)
        desired_outputs[SPOTMARKET_LOCKOUT_CHANNEL] = bool(spotmarket_active_now)
        desired_outputs[CURRENT_PRICE_CHANNEL] = float(price_snapshot.current_price_ct_kwh)

        write_results, critical_errors, noncritical_errors = self._apply_outputs(
            desired_outputs=desired_outputs,
            cycle_id=cycle_id,
            timestamp=timestamp,
            force_confirmation=force_confirmation,
            current_price_handoff_key=_price_handoff_key(price_snapshot),
            current_slot_label=price_snapshot.current_slot_label,
            current_price_ct_kwh=price_snapshot.current_price_ct_kwh,
        )

        if critical_errors:
            self.state.health.consecutive_comm_errors += 1
            snapshot = self._handle_safe_mode(
                cycle_id=cycle_id,
                timestamp=timestamp,
                reason="write_failure: {0}".format("; ".join(critical_errors)),
                price_snapshot=price_snapshot,
                input_reads=input_reads,
                controller_outcomes=controller_outcomes,
                desired_outputs=desired_outputs,
                write_results=write_results,
                spotmarket_plan=spotmarket_plan,
                spotmarket_active_now=spotmarket_active_now,
                spotmarket_source=spotmarket_source,
                spotmarket_next_window=spotmarket_next_window,
                spotmarket_override=manual_override.to_dict(),
                degraded_reason=None,
            )
            self._persist(snapshot, input_reads=input_reads, price_snapshot=price_snapshot, spotmarket_plan=spotmarket_plan)
            return snapshot

        if noncritical_errors:
            self.state.health.consecutive_comm_errors = 0
            degraded_reason = "; ".join(noncritical_errors)
            self.state.health.safe_mode_active = False
            self.state.health.safe_mode_reason = None
            self.state.health.safe_outputs_confirmed = False
            self.state.health.last_successful_cycle_id = cycle_id
            self.state.health.last_successful_at = timestamp
            self.state.health.last_degraded_cycle_id = cycle_id
            self.state.health.last_degraded_at = timestamp
            self.state.health.last_degraded_reason = degraded_reason
            snapshot = self._build_snapshot(
                timestamp=timestamp,
                cycle_id=cycle_id,
                status="degraded",
                degraded_reason=degraded_reason,
                price_snapshot=price_snapshot,
                input_reads=input_reads,
                controller_outcomes=controller_outcomes,
                desired_outputs=desired_outputs,
                write_results=write_results,
                spotmarket_plan=spotmarket_plan,
                spotmarket_active_now=spotmarket_active_now,
                spotmarket_source=spotmarket_source,
                spotmarket_next_window=spotmarket_next_window,
                spotmarket_override=manual_override.to_dict(),
            )
            log_event(
                self.logger,
                logging.WARNING,
                "cycle.degraded",
                cycle_id=cycle_id,
                degraded_reason=degraded_reason,
                write_results=write_results,
                current_slot_label=price_snapshot.current_slot_label,
                desired_price_ct_kwh=price_snapshot.current_price_ct_kwh,
            )
            self._persist(snapshot, input_reads=input_reads, price_snapshot=price_snapshot, spotmarket_plan=spotmarket_plan)
            return snapshot

        self.state.health.consecutive_comm_errors = 0
        self.state.health.safe_mode_active = False
        self.state.health.safe_mode_reason = None
        self.state.health.safe_outputs_confirmed = True
        self.state.health.last_successful_cycle_id = cycle_id
        self.state.health.last_successful_at = timestamp
        self.state.health.last_healthy_cycle_id = cycle_id
        self.state.health.last_healthy_at = timestamp

        snapshot = self._build_snapshot(
            timestamp=timestamp,
            cycle_id=cycle_id,
            status="healthy",
            degraded_reason=None,
            price_snapshot=price_snapshot,
            input_reads=input_reads,
            controller_outcomes=controller_outcomes,
            desired_outputs=desired_outputs,
            write_results=write_results,
            spotmarket_plan=spotmarket_plan,
            spotmarket_active_now=spotmarket_active_now,
            spotmarket_source=spotmarket_source,
            spotmarket_next_window=spotmarket_next_window,
            spotmarket_override=manual_override.to_dict(),
        )
        log_event(
            self.logger,
            logging.INFO,
            "cycle.healthy",
            cycle_id=cycle_id,
            desired_outputs=desired_outputs,
            write_results=write_results,
            current_slot_label=price_snapshot.current_slot_label,
            desired_price_ct_kwh=price_snapshot.current_price_ct_kwh,
            grid_active_power_kw=snapshot.get("grid_active_power_kw"),
            today_date=price_snapshot.today_date_iso,
            tomorrow_prices_available=price_snapshot.tomorrow_prices_available,
        )
        self._persist(snapshot, input_reads=input_reads, price_snapshot=price_snapshot, spotmarket_plan=spotmarket_plan)
        return snapshot

    def _apply_outputs(
        self,
        *,
        desired_outputs: Dict[str, object],
        cycle_id: str,
        timestamp: str,
        force_confirmation: bool,
        current_price_handoff_key: str,
        current_slot_label: str,
        current_price_ct_kwh: float,
    ) -> Tuple[Dict[str, object], List[str], List[str]]:
        results: Dict[str, object] = {}
        critical_errors: List[str] = []
        noncritical_errors: List[str] = []

        for channel_id, desired_value in desired_outputs.items():
            output_state = self.state.outputs[channel_id]
            policy = self.config.output_policies.for_channel(channel_id)
            previous_value = output_state.value
            needs_write = (
                force_confirmation
                or (not output_state.is_confirmed)
                or output_state.value != desired_value
                or (
                    channel_id == CURRENT_PRICE_CHANNEL
                    and self.state.health.last_price_handoff_key != current_price_handoff_key
                )
            )
            if not needs_write:
                results[channel_id] = {
                    "changed": False,
                    "confirmed_value": output_state.value,
                    "last_confirmed_at": output_state.last_confirmed_at,
                    "confirmation_mode": policy.confirmation_mode,
                    "confirmation_source": output_state.last_confirmation_mode,
                    "criticality": policy.criticality,
                    "readback_value": output_state.last_readback_value,
                    "ack_received": output_state.last_confirmation_mode == "ack",
                    "handoff_key": current_price_handoff_key if channel_id == CURRENT_PRICE_CHANNEL else None,
                }
                continue

            point = self.registry.get(channel_id)
            confirmation = self.adapter.write_with_confirmation(
                point=point,
                desired_value=desired_value,
                confirmation_mode=policy.confirmation_mode,
            )

            if not confirmation.confirmed:
                output_state.is_confirmed = False
                output_state.last_error = confirmation.error
                output_state.last_confirmation_mode = confirmation.confirmation_source or confirmation.confirmation_mode
                output_state.last_readback_value = confirmation.readback_value
                result = {
                    "changed": True,
                    "confirmed_value": None,
                    "desired_value": desired_value,
                    "error": confirmation.error,
                    "confirmation_mode": confirmation.confirmation_mode,
                    "confirmation_source": confirmation.confirmation_source,
                    "criticality": policy.criticality,
                    "readback_value": confirmation.readback_value,
                    "ack_received": confirmation.ack_received,
                    "attempts": confirmation.attempts,
                }
                results[channel_id] = result
                message = "Failed to confirm {0}: {1}".format(channel_id, confirmation.error)
                if policy.criticality == "critical":
                    critical_errors.append(message)
                else:
                    noncritical_errors.append(message)
                log_event(
                    self.logger,
                    logging.ERROR if policy.criticality == "critical" else logging.WARNING,
                    "cycle.output_not_confirmed",
                    cycle_id=cycle_id,
                    channel_id=channel_id,
                    desired_value=desired_value,
                    confirmation_mode=confirmation.confirmation_mode,
                    confirmation_source=confirmation.confirmation_source,
                    readback_value=confirmation.readback_value,
                    ack_received=confirmation.ack_received,
                    error=confirmation.error,
                    criticality=policy.criticality,
                    desired_slot=current_slot_label if channel_id == CURRENT_PRICE_CHANNEL else None,
                    desired_price_ct_kwh=current_price_ct_kwh if channel_id == CURRENT_PRICE_CHANNEL else None,
                )
                continue

            output_state.value = desired_value
            output_state.is_confirmed = True
            output_state.last_confirmed_at = timestamp
            output_state.last_error = None
            output_state.last_confirmation_mode = confirmation.confirmation_source or confirmation.confirmation_mode
            output_state.last_readback_value = confirmation.readback_value
            results[channel_id] = {
                "changed": True,
                "confirmed_value": desired_value,
                "last_confirmed_at": timestamp,
                "confirmation_mode": confirmation.confirmation_mode,
                "confirmation_source": confirmation.confirmation_source,
                "criticality": policy.criticality,
                "readback_value": confirmation.readback_value,
                "ack_received": confirmation.ack_received,
                "attempts": confirmation.attempts,
                "handoff_key": current_price_handoff_key if channel_id == CURRENT_PRICE_CHANNEL else None,
            }
            log_event(
                self.logger,
                logging.INFO,
                "cycle.output_confirmed",
                cycle_id=cycle_id,
                channel_id=channel_id,
                confirmed_value=desired_value,
                confirmation_mode=confirmation.confirmation_mode,
                confirmation_source=confirmation.confirmation_source,
                readback_value=confirmation.readback_value,
                ack_received=confirmation.ack_received,
                desired_slot=current_slot_label if channel_id == CURRENT_PRICE_CHANNEL else None,
                desired_price_ct_kwh=current_price_ct_kwh if channel_id == CURRENT_PRICE_CHANNEL else None,
            )
            if channel_id == CURRENT_PRICE_CHANNEL and (force_confirmation or previous_value != desired_value):
                self.state.health.last_price_handoff_at = timestamp
                self.state.health.last_price_handoff_slot_label = current_slot_label
                self.state.health.last_price_handoff_key = current_price_handoff_key
                self.state.health.last_price_handoff_value_ct_kwh = float(desired_value)
            elif channel_id == CURRENT_PRICE_CHANNEL and self.state.health.last_price_handoff_key != current_price_handoff_key:
                self.state.health.last_price_handoff_at = timestamp
                self.state.health.last_price_handoff_slot_label = current_slot_label
                self.state.health.last_price_handoff_key = current_price_handoff_key
                self.state.health.last_price_handoff_value_ct_kwh = float(desired_value)

        return results, critical_errors, noncritical_errors

    def _should_read_additional_input(self, point, *, force_confirmation: bool) -> bool:
        interval = max(1, int(point.read_interval_cycles))
        return force_confirmation or interval == 1 or self.state.health.cycle_counter % interval == 0

    def _handle_safe_mode(
        self,
        *,
        cycle_id: str,
        timestamp: str,
        reason: str,
        price_snapshot: PublishedPriceSnapshot | None,
        input_reads: Dict[str, Dict[str, object]],
        controller_outcomes: Dict[str, object],
        desired_outputs: Dict[str, object],
        write_results: Dict[str, object],
        spotmarket_plan: Dict[str, object] | None,
        spotmarket_active_now: bool | None,
        spotmarket_source: str | None,
        spotmarket_next_window: Dict[str, object] | None,
        spotmarket_override: Dict[str, object] | None,
        degraded_reason: Optional[str],
    ) -> Dict[str, object]:
        self.state.health.safe_mode_active = True
        self.state.health.safe_mode_reason = reason
        self.state.health.safe_outputs_confirmed = False

        snapshot = self._build_snapshot(
            timestamp=timestamp,
            cycle_id=cycle_id,
            status="safe_mode",
            degraded_reason=degraded_reason,
            price_snapshot=price_snapshot,
            input_reads=input_reads,
            controller_outcomes=controller_outcomes,
            desired_outputs=desired_outputs,
            write_results=write_results,
            spotmarket_plan=spotmarket_plan,
            spotmarket_active_now=spotmarket_active_now,
            spotmarket_source=spotmarket_source,
            spotmarket_next_window=spotmarket_next_window,
            spotmarket_override=spotmarket_override,
            safe_mode_reason=reason,
        )
        log_event(
            self.logger,
            logging.ERROR,
            "cycle.safe_mode",
            cycle_id=cycle_id,
            reason=reason,
        )
        return snapshot

    def _build_snapshot(
        self,
        *,
        timestamp: str,
        cycle_id: str,
        status: str,
        degraded_reason: Optional[str],
        price_snapshot: PublishedPriceSnapshot | None,
        input_reads: Dict[str, Dict[str, object]],
        controller_outcomes: Dict[str, object],
        desired_outputs: Dict[str, object],
        write_results: Dict[str, object],
        spotmarket_plan: Dict[str, object] | None,
        spotmarket_active_now: bool | None,
        spotmarket_source: str | None,
        spotmarket_next_window: Dict[str, object] | None,
        spotmarket_override: Dict[str, object] | None,
        safe_mode_reason: Optional[str] = None,
    ) -> Dict[str, object]:
        current_price = price_snapshot.current_price_ct_kwh if price_snapshot is not None else 0.0
        current_slot_label = price_snapshot.current_slot_label if price_snapshot is not None else "--:--"
        current_slot_index = price_snapshot.current_slot_index if price_snapshot is not None else None
        today_date = price_snapshot.today_date_iso if price_snapshot is not None else "unknown"
        tomorrow_date = price_snapshot.tomorrow_date_iso if price_snapshot is not None else None
        tomorrow_prices_available = price_snapshot.tomorrow_prices_available if price_snapshot is not None else False
        today_available_slot_count = price_snapshot.today_available_slot_count if price_snapshot is not None else 0
        tomorrow_available_slot_count = price_snapshot.tomorrow_available_slot_count if price_snapshot is not None else 0
        price_source_status = price_snapshot.price_source_status if price_snapshot is not None else {}
        grid_read = input_reads.get(GRID_ACTIVE_POWER_CHANNEL, {})
        watchdog = self._watchdog_snapshot()

        return {
            "timestamp": timestamp,
            "cycle_id": cycle_id,
            "status": status,
            "safe_mode_active": status == "safe_mode",
            "safe_mode_reason": safe_mode_reason if status == "safe_mode" else None,
            "degraded_reason": degraded_reason,
            "consecutive_comm_errors": self.state.health.consecutive_comm_errors,
            "desired_outputs": desired_outputs,
            "write_results": write_results,
            "outputs": self._outputs_snapshot(),
            "input_reads": input_reads,
            "controller_outcomes": controller_outcomes,
            "grid_active_power_kw": grid_read.get("value"),
            "price_cache_path": price_snapshot.cache_path if price_snapshot is not None else None,
            "price_cache_last_update_at": price_snapshot.last_update_at if price_snapshot is not None else None,
            "spotmarket_plan_path": str(self.spotmarket_plan_writer.path),
            "spotmarket_override_path": str(self.spotmarket_override_store.path),
            "spotmarket_active_now": spotmarket_active_now,
            "spotmarket_source": spotmarket_source,
            "spotmarket_today_window_count": spotmarket_plan["today"]["window_count"] if spotmarket_plan is not None else None,
            "spotmarket_tomorrow_window_count": spotmarket_plan["tomorrow"]["window_count"] if spotmarket_plan is not None else None,
            "spotmarket_next_window": spotmarket_next_window,
            "spotmarket_override": spotmarket_override,
            "spotmarket_summary": spotmarket_plan["operator_summary"] if spotmarket_plan is not None else None,
            "price_source_status": price_source_status,
            "today_date": today_date,
            "today_available_slot_count": today_available_slot_count,
            "tomorrow_date": tomorrow_date,
            "tomorrow_prices_available": tomorrow_prices_available,
            "tomorrow_available_slot_count": tomorrow_available_slot_count,
            "current_slot_index": current_slot_index,
            "current_slot_label": current_slot_label,
            "current_price_ct_kwh": current_price,
            "watchdog": watchdog,
            "operator_message": build_operator_message(
                current_price,
                current_slot_label,
                today_date,
                tomorrow_prices_available,
                status == "safe_mode",
                safe_mode_reason,
                degraded_reason=degraded_reason,
            ),
        }

    def _outputs_snapshot(self) -> Dict[str, object]:
        return {
            channel_id: output_state.to_dict()
            for channel_id, output_state in self.state.outputs.items()
        }

    def _persist(
        self,
        snapshot: Dict[str, object],
        *,
        input_reads: Dict[str, Dict[str, object]],
        price_snapshot: PublishedPriceSnapshot | None,
        spotmarket_plan: Dict[str, object] | None,
    ) -> None:
        self.state_store.save(self.state)
        write_json_atomic(self.config.health_path, self._build_health_payload(snapshot))
        try:
            self.runtime_db.record_cycle_bundle(
                snapshot=snapshot,
                input_reads=input_reads,
                output_policies={
                    channel_id: {
                        "confirmation_mode": self.config.output_policies.for_channel(channel_id).confirmation_mode,
                        "criticality": self.config.output_policies.for_channel(channel_id).criticality,
                    }
                    for channel_id in self.state.outputs.keys()
                },
                price_days=self._price_days(price_snapshot),
                spotmarket_plan=spotmarket_plan,
            )
        except Exception as error:
            log_event(
                self.logger,
                logging.ERROR,
                "runtime_db.write_failed",
                cycle_id=snapshot.get("cycle_id"),
                error=str(error),
            )

    def _build_health_payload(self, snapshot: Dict[str, object]) -> Dict[str, object]:
        desired_outputs = snapshot.get("desired_outputs")
        outputs = snapshot.get("outputs")
        input_reads = snapshot.get("input_reads")
        controller_outcomes = snapshot.get("controller_outcomes")
        watchdog = snapshot.get("watchdog")

        desired_outputs = desired_outputs if isinstance(desired_outputs, dict) else {}
        outputs = outputs if isinstance(outputs, dict) else {}
        input_reads = input_reads if isinstance(input_reads, dict) else {}
        controller_outcomes = controller_outcomes if isinstance(controller_outcomes, dict) else {}
        watchdog = watchdog if isinstance(watchdog, dict) else {}

        grid_read = input_reads.get(GRID_ACTIVE_POWER_CHANNEL)
        grid_outcome = controller_outcomes.get("grid_lockout")
        grid_read = grid_read if isinstance(grid_read, dict) else {}
        grid_outcome = grid_outcome if isinstance(grid_outcome, dict) else {}

        payload = {
            "timestamp": snapshot.get("timestamp"),
            "cycle_id": snapshot.get("cycle_id"),
            "status": snapshot.get("status"),
            "safe_mode_reason": snapshot.get("safe_mode_reason"),
            "degraded_reason": snapshot.get("degraded_reason"),
            "operator_message": snapshot.get("operator_message"),
            "today_date": snapshot.get("today_date"),
            "tomorrow_date": snapshot.get("tomorrow_date"),
            "tomorrow_prices_available": snapshot.get("tomorrow_prices_available"),
            "current_slot_label": snapshot.get("current_slot_label"),
            "current_price_ct_kwh": snapshot.get("current_price_ct_kwh"),
            "grid_active_power_kw": snapshot.get("grid_active_power_kw"),
            "grid_read_status": grid_read.get("status"),
            "grid_lockout_state": grid_outcome.get("state_name"),
            "grid_lockout_active": desired_outputs.get(GRID_LOCKOUT_CHANNEL),
            "spotmarket_active_now": snapshot.get("spotmarket_active_now"),
            "spotmarket_source": snapshot.get("spotmarket_source"),
            "spotmarket_summary": snapshot.get("spotmarket_summary"),
            "spotmarket_next_window": snapshot.get("spotmarket_next_window"),
            "last_healthy_at": watchdog.get("last_healthy_at"),
            "last_price_handoff_at": watchdog.get("last_price_handoff_at"),
            "last_price_handoff_slot_label": watchdog.get("last_price_handoff_slot_label"),
            "last_price_handoff_value_ct_kwh": watchdog.get("last_price_handoff_value_ct_kwh"),
            "write_status": {
                "current_price": self._build_health_channel_status(
                    channel_id=CURRENT_PRICE_CHANNEL,
                    desired_value=desired_outputs.get(CURRENT_PRICE_CHANNEL),
                    outputs=outputs,
                ),
                "grid_lockout": self._build_health_channel_status(
                    channel_id=GRID_LOCKOUT_CHANNEL,
                    desired_value=desired_outputs.get(GRID_LOCKOUT_CHANNEL),
                    outputs=outputs,
                ),
                "spotmarket_lockout": self._build_health_channel_status(
                    channel_id=SPOTMARKET_LOCKOUT_CHANNEL,
                    desired_value=desired_outputs.get(SPOTMARKET_LOCKOUT_CHANNEL),
                    outputs=outputs,
                ),
            },
        }
        additional_inputs = self._build_health_additional_inputs(input_reads)
        if additional_inputs:
            payload["additional_inputs"] = additional_inputs
        return payload

    def _build_health_channel_status(
        self,
        *,
        channel_id: str,
        desired_value: object,
        outputs: Dict[str, object],
    ) -> Dict[str, object]:
        output_state = outputs.get(channel_id)
        output_state = output_state if isinstance(output_state, dict) else {}
        return {
            "desired_value": desired_value,
            "confirmed": output_state.get("is_confirmed"),
            "last_confirmed_at": output_state.get("last_confirmed_at"),
            "last_confirmed_value": output_state.get("value"),
            "last_confirmation_mode": output_state.get("last_confirmation_mode"),
            "last_readback_value": output_state.get("last_readback_value"),
            "last_error": output_state.get("last_error"),
        }

    def _build_health_additional_inputs(
        self,
        input_reads: Dict[str, object],
    ) -> Dict[str, object]:
        additional_inputs: Dict[str, object] = {}
        for channel_id in self.registry.additional_input_channel_ids():
            point = self.registry.get(channel_id)
            if not point.include_in_health:
                continue
            diagnostic = input_reads.get(channel_id)
            diagnostic = diagnostic if isinstance(diagnostic, dict) else {}
            additional_inputs[channel_id] = {
                "value": diagnostic.get("value"),
                "status": diagnostic.get("status"),
                "error": diagnostic.get("error"),
            }
        return additional_inputs

    def _price_days(self, price_snapshot: PublishedPriceSnapshot | None) -> List[Dict[str, object]]:
        if price_snapshot is None:
            return []
        days: List[Dict[str, object]] = [
            {
                "day_kind": "today",
                "date": price_snapshot.today_date_iso,
                "slots": list(price_snapshot.today_slots),
                "captured_at": price_snapshot.last_update_at,
            }
        ]
        if price_snapshot.tomorrow_date_iso:
            days.append(
                {
                    "day_kind": "tomorrow",
                    "date": price_snapshot.tomorrow_date_iso,
                    "slots": list(price_snapshot.tomorrow_slots),
                    "captured_at": price_snapshot.last_update_at,
                }
            )
        return days

    def _watchdog_snapshot(self) -> Dict[str, object]:
        return {
            "last_cycle_id": self.state.health.last_cycle_id,
            "last_cycle_at": self.state.health.last_cycle_at,
            "last_successful_cycle_id": self.state.health.last_successful_cycle_id,
            "last_successful_at": self.state.health.last_successful_at,
            "last_healthy_cycle_id": self.state.health.last_healthy_cycle_id,
            "last_healthy_at": self.state.health.last_healthy_at,
            "last_degraded_cycle_id": self.state.health.last_degraded_cycle_id,
            "last_degraded_at": self.state.health.last_degraded_at,
            "last_degraded_reason": self.state.health.last_degraded_reason,
            "last_price_handoff_at": self.state.health.last_price_handoff_at,
            "last_price_handoff_slot_label": self.state.health.last_price_handoff_slot_label,
            "last_price_handoff_key": self.state.health.last_price_handoff_key,
            "last_price_handoff_value_ct_kwh": self.state.health.last_price_handoff_value_ct_kwh,
        }

    def _next_cycle_id(self) -> str:
        self.state.health.cycle_counter += 1
        return "cycle-{0:06d}".format(self.state.health.cycle_counter)


def _price_handoff_key(price_snapshot: PublishedPriceSnapshot) -> str:
    return "{0}/{1}".format(price_snapshot.today_date_iso, price_snapshot.current_slot_label)
