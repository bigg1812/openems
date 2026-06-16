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
from typing import Optional, Protocol, runtime_checkable

from .channels import PointConfig


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

    def close(self) -> None:
        ...
