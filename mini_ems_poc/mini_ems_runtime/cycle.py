import logging
from typing import Dict

from .bacnet import BacnetAdapter, BacnetError
from .channels import BACNET_BV, CURRENT_PRICE_CHANNEL, SPOTMARKET_LOCKOUT_CHANNEL, ChannelRegistry
from .config import MiniEmsConfig
from .logging_utils import log_event, utcnow_iso
from .operator_status import build_operator_message
from .price_cache import PublishedPriceSnapshot, SpotmarketPriceCacheService
from .price_provider_smard import PriceProviderError
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
    ):
        self.config = config
        self.registry = registry
        self.adapter = adapter
        self.state_store = state_store
        self.logger = logger
        self.price_service = price_service
        self.spotmarket_plan_writer = spotmarket_plan_writer
        self.spotmarket_override_store = spotmarket_override_store
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

        try:
            price_snapshot = self.price_service.refresh()
        except PriceProviderError as error:
            self.state.health.consecutive_comm_errors += 1
            snapshot = self._handle_unhealthy_cycle(
                cycle_id=cycle_id,
                timestamp=timestamp,
                reason="price_provider: {0}".format(error),
                price_snapshot=None,
                desired_outputs={},
                write_results={},
            )
            self._persist(snapshot)
            return snapshot

        spotmarket_plan = self.spotmarket_plan_writer.write_plan(
            generated_at=price_snapshot.last_update_at,
            today_date_iso=price_snapshot.today_date_iso,
            today_slots=price_snapshot.today_slots,
            tomorrow_date_iso=price_snapshot.tomorrow_date_iso,
            tomorrow_slots=price_snapshot.tomorrow_slots,
            current_slot_index=price_snapshot.current_slot_index,
        )
        manual_override = self.spotmarket_override_store.load_for_date(price_snapshot.today_date_iso)
        spotmarket_active_now = manual_override.active_now(price_snapshot.current_slot_index) if manual_override.enabled else bool(spotmarket_plan["active_today_now"])
        spotmarket_next_window = (
            manual_override.next_window(price_snapshot.current_slot_index).to_dict()
            if manual_override.enabled and manual_override.next_window(price_snapshot.current_slot_index) is not None
            else spotmarket_plan["next_today_window"]
        )
        spotmarket_source = "manual_override" if manual_override.enabled else "computed_plan"

        desired_outputs = {
            CURRENT_PRICE_CHANNEL: float(price_snapshot.current_price_ct_kwh),
            SPOTMARKET_LOCKOUT_CHANNEL: bool(spotmarket_active_now),
        }

        try:
            write_results = self._apply_outputs(desired_outputs, cycle_id, timestamp)
        except BacnetError as error:
            self.state.health.consecutive_comm_errors += 1
            snapshot = self._handle_unhealthy_cycle(
                cycle_id=cycle_id,
                timestamp=timestamp,
                reason="write_failure: {0}".format(error),
                price_snapshot=price_snapshot,
                desired_outputs=desired_outputs,
                write_results={
                    CURRENT_PRICE_CHANNEL: {
                        "changed": True,
                        "confirmed_value": None,
                        "error": str(error),
                        "desired_value": desired_outputs[CURRENT_PRICE_CHANNEL],
                    }
                },
            )
            self._persist(snapshot)
            return snapshot

        self.state.health.consecutive_comm_errors = 0
        self.state.health.safe_mode_active = False
        self.state.health.safe_mode_reason = None
        self.state.health.safe_outputs_confirmed = True
        self.state.health.last_healthy_cycle_id = cycle_id
        self.state.health.last_healthy_at = timestamp

        snapshot = {
            "timestamp": timestamp,
            "cycle_id": cycle_id,
            "status": "healthy",
            "safe_mode_active": False,
            "safe_mode_reason": None,
            "consecutive_comm_errors": self.state.health.consecutive_comm_errors,
            "desired_outputs": desired_outputs,
            "write_results": write_results,
            "outputs": self._outputs_snapshot(),
            "price_cache_path": price_snapshot.cache_path,
            "price_cache_last_update_at": price_snapshot.last_update_at,
            "spotmarket_plan_path": str(self.spotmarket_plan_writer.path),
            "spotmarket_override_path": str(self.spotmarket_override_store.path),
            "spotmarket_active_now": spotmarket_active_now,
            "spotmarket_source": spotmarket_source,
            "spotmarket_today_window_count": spotmarket_plan["today"]["window_count"],
            "spotmarket_tomorrow_window_count": spotmarket_plan["tomorrow"]["window_count"],
            "spotmarket_next_window": spotmarket_next_window,
            "spotmarket_override": manual_override.to_dict(),
            "spotmarket_summary": spotmarket_plan["operator_summary"],
            "price_source_status": price_snapshot.price_source_status,
            "today_date": price_snapshot.today_date_iso,
            "today_available_slot_count": price_snapshot.today_available_slot_count,
            "tomorrow_date": price_snapshot.tomorrow_date_iso,
            "tomorrow_prices_available": price_snapshot.tomorrow_prices_available,
            "tomorrow_available_slot_count": price_snapshot.tomorrow_available_slot_count,
            "current_slot_index": price_snapshot.current_slot_index,
            "current_slot_label": price_snapshot.current_slot_label,
            "current_price_ct_kwh": price_snapshot.current_price_ct_kwh,
            "operator_message": build_operator_message(
                price_snapshot.current_price_ct_kwh,
                price_snapshot.current_slot_label,
                price_snapshot.today_date_iso,
                price_snapshot.tomorrow_prices_available,
                False,
                None,
            ),
        }
        log_event(
            self.logger,
            logging.INFO,
            "cycle.healthy",
            cycle_id=cycle_id,
            desired_outputs=desired_outputs,
            write_results=write_results,
            today_date=price_snapshot.today_date_iso,
            today_available_slot_count=price_snapshot.today_available_slot_count,
            tomorrow_prices_available=price_snapshot.tomorrow_prices_available,
            tomorrow_available_slot_count=price_snapshot.tomorrow_available_slot_count,
            spotmarket_active_now=spotmarket_active_now,
            spotmarket_source=spotmarket_source,
            spotmarket_today_window_count=spotmarket_plan["today"]["window_count"],
            spotmarket_tomorrow_window_count=spotmarket_plan["tomorrow"]["window_count"],
            price_source_status=price_snapshot.price_source_status,
            current_slot_label=price_snapshot.current_slot_label,
        )
        self._persist(snapshot)
        return snapshot

    def _apply_outputs(self, desired_outputs: Dict[str, object], cycle_id: str, timestamp: str) -> Dict[str, object]:
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
            if point.object_type == BACNET_BV:
                self.adapter.write_bool(point, bool(desired_value))
            else:
                self.adapter.write_float(point, float(desired_value))
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
        price_snapshot: PublishedPriceSnapshot | None,
        desired_outputs: Dict[str, object],
        write_results: Dict[str, object],
    ) -> Dict[str, object]:
        self.state.health.safe_mode_active = True
        self.state.health.safe_mode_reason = reason
        self.state.health.safe_outputs_confirmed = False

        current_price = price_snapshot.current_price_ct_kwh if price_snapshot is not None else 0.0
        current_slot_label = price_snapshot.current_slot_label if price_snapshot is not None else "--:--"
        today_date = price_snapshot.today_date_iso if price_snapshot is not None else "unknown"
        tomorrow_prices_available = price_snapshot.tomorrow_prices_available if price_snapshot is not None else False

        snapshot = {
            "timestamp": timestamp,
            "cycle_id": cycle_id,
            "status": "safe_mode",
            "safe_mode_active": True,
            "safe_mode_reason": reason,
            "consecutive_comm_errors": self.state.health.consecutive_comm_errors,
            "desired_outputs": desired_outputs,
            "write_results": write_results,
            "outputs": self._outputs_snapshot(),
            "price_cache_path": price_snapshot.cache_path if price_snapshot is not None else None,
            "price_cache_last_update_at": price_snapshot.last_update_at if price_snapshot is not None else None,
            "spotmarket_plan_path": str(self.spotmarket_plan_writer.path),
            "spotmarket_override_path": str(self.spotmarket_override_store.path),
            "price_source_status": price_snapshot.price_source_status if price_snapshot is not None else {},
            "today_date": today_date,
            "today_available_slot_count": price_snapshot.today_available_slot_count if price_snapshot is not None else 0,
            "tomorrow_date": price_snapshot.tomorrow_date_iso if price_snapshot is not None else None,
            "tomorrow_prices_available": tomorrow_prices_available,
            "tomorrow_available_slot_count": price_snapshot.tomorrow_available_slot_count if price_snapshot is not None else 0,
            "current_slot_index": price_snapshot.current_slot_index if price_snapshot is not None else None,
            "current_slot_label": current_slot_label,
            "current_price_ct_kwh": current_price,
            "spotmarket_active_now": None,
            "spotmarket_source": None,
            "spotmarket_today_window_count": None,
            "spotmarket_tomorrow_window_count": None,
            "spotmarket_next_window": None,
            "spotmarket_override": None,
            "spotmarket_summary": None,
            "operator_message": build_operator_message(
                current_price,
                current_slot_label,
                today_date,
                tomorrow_prices_available,
                True,
                reason,
            ),
        }
        log_event(
            self.logger,
            logging.ERROR,
            "cycle.safe_mode",
            cycle_id=cycle_id,
            reason=reason,
        )
        return snapshot

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
