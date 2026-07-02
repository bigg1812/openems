import json
import logging
from datetime import timedelta
from pathlib import Path
from typing import Dict, List, Optional

from .bacnet import (
    BacnetCommunicationError,
    BacnetPermissionError,
)
from .channels import BACNET_AV, BACNET_BV, PointConfig
from .logging_utils import log_event
from .modbus import ModbusPermissionError
from .protocol import WriteConfirmation
from .price_cache import CachedDay, PriceCacheFile, PublishedPriceSnapshot
from .price_provider_smard import PriceProviderError, berlin_now
from .state_store import write_json_atomic


class SimulatedBacnetAdapter:
    def __init__(self, values_path: Path, logger: logging.Logger):
        self.values_path = Path(values_path)
        self.logger = logger
        self._written_values: Dict[str, object] = {}

    def close(self) -> None:
        return None

    def read_float(self, point: PointConfig) -> float:
        if not point.can_read():
            raise BacnetPermissionError("Read access denied for channel {0}".format(point.channel_id))

        if point.channel_id in self._written_values:
            return float(self._written_values[point.channel_id])

        values = self._load_values()
        if point.channel_id not in values:
            raise BacnetCommunicationError(
                "No simulated value configured for channel {0}".format(point.channel_id)
            )
        value = float(values[point.channel_id])
        log_event(
            self.logger,
            logging.INFO,
            "simulation.bacnet_read",
            channel_id=point.channel_id,
            value=value,
            values_file=str(self.values_path),
        )
        return value

    def write_bool(self, point: PointConfig, value: bool) -> None:
        self._store_write(point, bool(value))

    def write_float(self, point: PointConfig, value: float) -> None:
        self._store_write(point, float(value))

    def write_with_confirmation(
        self,
        point: PointConfig,
        desired_value: object,
        confirmation_mode: str,
    ) -> WriteConfirmation:
        normalized_value = self._normalize_write_value(point, desired_value)
        self._store_write(point, normalized_value)
        return WriteConfirmation(
            channel_id=point.channel_id,
            confirmed=True,
            ack_received=False,
            confirmation_mode=confirmation_mode,
            confirmation_source="simulated",
            desired_value=normalized_value,
            attempts=1,
            readback_value=float(normalized_value) if point.object_type == BACNET_AV else None,
        )

    def _store_write(self, point: PointConfig, value: object) -> None:
        if not point.can_write():
            raise BacnetPermissionError("Write access denied for channel {0}".format(point.channel_id))
        self._written_values[point.channel_id] = value
        log_event(
            self.logger,
            logging.INFO,
            "simulation.bacnet_write",
            channel_id=point.channel_id,
            value=value,
            real_write=False,
        )

    def _normalize_write_value(self, point: PointConfig, desired_value: object) -> object:
        if point.object_type == BACNET_BV:
            return bool(desired_value)
        if point.object_type == BACNET_AV:
            return float(desired_value)
        raise BacnetPermissionError(
            "Unsupported simulated BACnet object type for channel {0}".format(point.channel_id)
        )

    def _load_values(self) -> Dict[str, object]:
        try:
            raw = json.loads(self.values_path.read_text(encoding="utf-8"))
        except FileNotFoundError as error:
            raise BacnetCommunicationError(
                "Simulation values file not found: {0}".format(self.values_path)
            ) from error
        except json.JSONDecodeError as error:
            raise BacnetCommunicationError(
                "Simulation values file is invalid JSON: {0}".format(self.values_path)
            ) from error

        if not isinstance(raw, dict):
            raise BacnetCommunicationError("Simulation values must be a JSON object")
        values = raw.get("channels", raw)
        if not isinstance(values, dict):
            raise BacnetCommunicationError("Simulation values must contain a 'channels' object")
        return values


class SimulatedModbusAdapter(SimulatedBacnetAdapter):
    """Simulated counterpart of the read-only ``ModbusTcpAdapter``.

    Reads come from the same channel-keyed values file as the simulated
    BACnet adapter (the raw Modbus address is irrelevant locally), but the
    write refusal of the real Modbus adapter is mirrored exactly so that
    simulation and IPC behave identically on the write path.
    """

    def write_bool(self, point: PointConfig, value: bool) -> None:
        raise ModbusPermissionError(
            "Modbus adapter is read-only: write denied for channel {0}".format(point.channel_id)
        )

    def write_float(self, point: PointConfig, value: float) -> None:
        raise ModbusPermissionError(
            "Modbus adapter is read-only: write denied for channel {0}".format(point.channel_id)
        )

    def write_with_confirmation(
        self,
        point: PointConfig,
        desired_value: object,
        confirmation_mode: str,
    ) -> WriteConfirmation:
        raise ModbusPermissionError(
            "Modbus adapter is read-only: write denied for channel {0}".format(point.channel_id)
        )


class SimulatedSpotmarketPriceService:
    def __init__(
        self,
        cache_path: Path,
        prices_path: Path,
        resolution: str,
        logger: logging.Logger,
    ):
        self.cache_path = Path(cache_path)
        self.prices_path = Path(prices_path)
        self.resolution = resolution
        self.logger = logger

    def refresh(self) -> PublishedPriceSnapshot:
        now_local = berlin_now()
        today = now_local.date()
        tomorrow = today + timedelta(days=1)
        raw = self._load_price_config()
        today_slots = self._build_slots(raw, "today")
        tomorrow_slots = self._build_slots(raw, "tomorrow")
        slot_index = self._current_slot_index(now_local)
        current_value = today_slots[slot_index]
        if current_value is None:
            raise PriceProviderError("Simulated current price slot is empty")

        last_update_at = now_local.isoformat()
        price_source_status = {
            "provider": "simulated",
            "resolution": self.resolution,
            "today_date": today.isoformat(),
            "today_slots_found": len([value for value in today_slots if value is not None]),
            "today_complete": all(value is not None for value in today_slots),
            "tomorrow_date": tomorrow.isoformat(),
            "tomorrow_slots_found": len([value for value in tomorrow_slots if value is not None]),
            "tomorrow_complete": all(value is not None for value in tomorrow_slots),
            "prices_file": str(self.prices_path),
        }
        cache = PriceCacheFile(
            last_update_at=last_update_at,
            today=CachedDay(date_iso=today.isoformat(), slots=today_slots),
            tomorrow=CachedDay(date_iso=tomorrow.isoformat(), slots=tomorrow_slots),
            price_source_status=price_source_status,
        )
        write_json_atomic(self.cache_path, cache.to_dict())
        log_event(
            self.logger,
            logging.INFO,
            "simulation.price_snapshot",
            current_slot_label=self._slot_label(slot_index),
            current_price_ct_kwh=current_value,
            prices_file=str(self.prices_path),
        )
        return PublishedPriceSnapshot(
            current_price_ct_kwh=float(current_value),
            current_slot_index=slot_index,
            current_slot_label=self._slot_label(slot_index),
            today_date_iso=today.isoformat(),
            today_available_slot_count=price_source_status["today_slots_found"],
            today_slots=today_slots,
            tomorrow_date_iso=tomorrow.isoformat(),
            tomorrow_prices_available=price_source_status["tomorrow_slots_found"] > 0,
            tomorrow_available_slot_count=price_source_status["tomorrow_slots_found"],
            tomorrow_slots=tomorrow_slots,
            cache_path=str(self.cache_path),
            last_update_at=last_update_at,
            price_source_status=price_source_status,
        )

    def _load_price_config(self) -> dict:
        try:
            raw = json.loads(self.prices_path.read_text(encoding="utf-8"))
        except FileNotFoundError as error:
            raise PriceProviderError(
                "Simulation prices file not found: {0}".format(self.prices_path)
            ) from error
        except json.JSONDecodeError as error:
            raise PriceProviderError(
                "Simulation prices file is invalid JSON: {0}".format(self.prices_path)
            ) from error
        if not isinstance(raw, dict):
            raise PriceProviderError("Simulation prices must be a JSON object")
        return raw

    def _build_slots(self, raw: dict, day_key: str) -> List[Optional[float]]:
        expected_slots = 96 if self.resolution == "quarterhour" else 24
        explicit_slots = raw.get("{0}_slots_ct_kwh".format(day_key))
        if isinstance(explicit_slots, list):
            if len(explicit_slots) != expected_slots:
                raise PriceProviderError(
                    "{0}_slots_ct_kwh must contain {1} slots".format(day_key, expected_slots)
                )
            return [None if value is None else float(value) for value in explicit_slots]

        default_value = float(raw.get("default_{0}_ct_kwh".format(day_key), raw.get("default_ct_kwh", 10.0)))
        slots: List[Optional[float]] = [default_value] * expected_slots
        windows = raw.get("{0}_windows".format(day_key), [])
        if not isinstance(windows, list):
            raise PriceProviderError("{0}_windows must be a list".format(day_key))
        for window in windows:
            if not isinstance(window, dict):
                raise PriceProviderError("each simulated price window must be an object")
            start_slot = int(window["start_slot"])
            length = int(window["length"])
            price = float(window["price_ct_kwh"])
            for slot_index in range(start_slot, min(start_slot + length, expected_slots)):
                slots[slot_index] = price
        return slots

    def _current_slot_index(self, now_local) -> int:
        if self.resolution == "quarterhour":
            return now_local.hour * 4 + now_local.minute // 15
        return now_local.hour

    def _slot_label(self, slot_index: int) -> str:
        if self.resolution == "quarterhour":
            hour = slot_index // 4
            minute = (slot_index % 4) * 15
        else:
            hour = slot_index
            minute = 0
        return "{0:02d}:{1:02d}".format(hour, minute)
