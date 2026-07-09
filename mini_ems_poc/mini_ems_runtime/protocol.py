"""Protocol-neutral adapter contract.

This module defines the abstractions that decouple the control runtime
(``CycleRunner``, ``ChannelReadDiagnosticsService``) from any concrete
fieldbus protocol. Today the only real implementation is the BACnet
adapter, but the contract is deliberately protocol-agnostic so that a
second protocol (e.g. Modbus) can be added without touching the runtime.

It is the first of the wiki's three pillars:
``ProtocolAdapter + MappingConfig + SemanticChannel``.

Placement rationale: this module imports only ``PointConfig`` from
``channels`` (for type hints). ``channels`` imports only ``config``, so
there is no import cycle. Both ``bacnet`` and ``simulation`` import the
neutral ``WriteConfirmation`` from here, and ``cycle`` / ``read_diagnostics``
depend on ``ProtocolAdapter`` here rather than on the concrete adapter.
"""

from dataclasses import dataclass
from typing import Dict, Optional, Protocol, runtime_checkable

from .channels import PointConfig


class AdapterError(Exception):
    """Protocol-neutral base class for adapter errors.

    Every concrete adapter derives its error hierarchy from this class
    (``BacnetError``, ``ModbusError``), so the runtime — most importantly
    ``ChannelReadDiagnosticsService`` — can classify any failed read as a
    read error (``quality="bad"``) without knowing the protocol.
    """


@dataclass(frozen=True)
class WriteConfirmation:
    """Protocol-neutral result of a confirmed write to an output point.

    The field set mirrors what the runtime persists and reports; it is not
    tied to BACnet semantics. ``confirmation_source`` records *how* the
    write was confirmed (e.g. ``"ack"``, ``"readback"``, ``"simulated"``).
    """

    channel_id: str
    confirmed: bool
    ack_received: bool
    confirmation_mode: str
    confirmation_source: Optional[str]
    desired_value: object
    attempts: int
    readback_value: Optional[float] = None
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "channel_id": self.channel_id,
            "confirmed": self.confirmed,
            "ack_received": self.ack_received,
            "confirmation_mode": self.confirmation_mode,
            "confirmation_source": self.confirmation_source,
            "desired_value": self.desired_value,
            "attempts": self.attempts,
            "readback_value": self.readback_value,
            "error": self.error,
        }


@runtime_checkable
class ProtocolAdapter(Protocol):
    """Minimal contract the control runtime needs from any protocol adapter.

    Concrete adapters (``BacnetAdapter``, ``SimulatedBacnetAdapter``, a
    future Modbus adapter) satisfy this structurally — no explicit
    inheritance is required. Only the methods actually used by the runtime
    are part of the contract.
    """

    def read_float(self, point: PointConfig) -> float:
        ...

    def write_with_confirmation(
        self,
        point: PointConfig,
        desired_value: object,
        confirmation_mode: str,
    ) -> WriteConfirmation:
        ...

    def relinquish_with_confirmation(
        self,
        point: PointConfig,
        confirmation_mode: str,
    ) -> WriteConfirmation:
        ...

    def close(self) -> None:
        ...


class ProtocolRoutingAdapter:
    """Per-point dispatcher: delegates each call to the adapter of ``point.protocol``.

    Itself satisfies ``ProtocolAdapter``, so ``CycleRunner`` and
    ``ChannelReadDiagnosticsService`` stay protocol-agnostic: they keep
    talking to a single adapter while each point declares its protocol in
    the config (default ``"bacnet"``, so existing configs behave exactly
    as before).
    """

    def __init__(self, adapters: Dict[str, "ProtocolAdapter"]):
        if not adapters:
            raise ValueError("ProtocolRoutingAdapter requires at least one adapter")
        self._adapters = dict(adapters)

    def read_float(self, point: PointConfig) -> float:
        return self._adapter_for(point).read_float(point)

    def write_with_confirmation(
        self,
        point: PointConfig,
        desired_value: object,
        confirmation_mode: str,
    ) -> WriteConfirmation:
        return self._adapter_for(point).write_with_confirmation(
            point,
            desired_value,
            confirmation_mode,
        )

    def relinquish_with_confirmation(
        self,
        point: PointConfig,
        confirmation_mode: str,
    ) -> WriteConfirmation:
        return self._adapter_for(point).relinquish_with_confirmation(
            point,
            confirmation_mode,
        )

    def close(self) -> None:
        # Adapters may be registered under several protocol names (e.g. one
        # simulated adapter serving both); close each instance only once.
        seen_ids = set()
        for adapter in self._adapters.values():
            if id(adapter) in seen_ids:
                continue
            seen_ids.add(id(adapter))
            adapter.close()

    def _adapter_for(self, point: PointConfig) -> "ProtocolAdapter":
        adapter = self._adapters.get(point.protocol)
        if adapter is None:
            # AdapterError so a routed read on a misconfigured point is
            # classified as a read error (quality="bad") like any other failure.
            raise AdapterError(
                "No adapter registered for protocol {0} (channel {1})".format(
                    point.protocol,
                    point.channel_id,
                )
            )
        return adapter
