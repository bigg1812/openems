"""Read-only Modbus TCP adapter (Roadmap S4).

Second concrete implementation of the neutral ``ProtocolAdapter`` contract
next to ``BacnetAdapter``: pure stdlib (socket + struct), no external
dependencies. Deliberately read-only — ``write_with_confirmation()`` always
refuses, so adding Modbus introduces no new write risk.

Scope: MBAP framing over TCP, function codes 3 (holding registers) and
4 (input registers), encodings int16/uint16/int32/uint32/float32 with
configurable word order (``"big"`` = most significant word first,
``"little"`` = word-swapped) and scale factor. Each read opens a fresh TCP
connection; at the configured cycle times (>= 60 s per point) the connect
overhead is negligible and avoids stale-connection handling.

The error hierarchy mirrors the BACnet one and derives from the neutral
``AdapterError``, so ``ChannelReadDiagnosticsService`` classifies any Modbus
read failure as ``quality="bad"`` without knowing the protocol.
"""

import logging
import socket
import struct
from typing import Sequence, Tuple

from .channels import PointConfig
from .config import PROTOCOL_MODBUS_TCP, ModbusPointConfig
from .logging_utils import log_event
from .protocol import AdapterError, WriteConfirmation

MBAP_HEADER_LENGTH = 7
MBAP_PROTOCOL_ID = 0

# struct format per encoding for the register payload after word ordering;
# the register count per encoding lives in config.MODBUS_REGISTER_COUNTS.
_ENCODING_FORMATS = {
    "int16": ">h",
    "uint16": ">H",
    "int32": ">i",
    "uint32": ">I",
    "float32": ">f",
}

# Standard Modbus exception codes, for readable error messages.
_EXCEPTION_CODE_NAMES = {
    1: "illegal function",
    2: "illegal data address",
    3: "illegal data value",
    4: "slave device failure",
}


class ModbusError(AdapterError):
    """Base class for Modbus adapter errors."""


class ModbusPermissionError(ModbusError):
    """Raised when a point is accessed outside the allowlist or written."""


class ModbusCommunicationError(ModbusError):
    """Raised when communication with the Modbus device fails."""


class ModbusProtocolError(ModbusError):
    """Raised when the device returns an unexpected Modbus frame."""


class ModbusTcpAdapter:
    """Read-only Modbus TCP implementation of the ``ProtocolAdapter`` contract."""

    def __init__(
        self,
        logger: logging.Logger,
        response_timeout_seconds: float = 2.0,
        retries: int = 1,
    ):
        self.logger = logger
        self.response_timeout_seconds = response_timeout_seconds
        self.retries = retries
        self._transaction_id = 0

    def close(self) -> None:
        # Connections are opened and closed per read; nothing is kept open.
        return None

    def read_float(self, point: PointConfig) -> float:
        if not point.can_read():
            raise ModbusPermissionError("Read access denied for channel {0}".format(point.channel_id))
        address = self._modbus_address(point)

        last_error = None
        for attempt in range(1, self.retries + 2):
            transaction_id = self._next_transaction_id()
            try:
                registers = self._read_registers(address, transaction_id, point.channel_id)
                raw_value = _decode_registers(registers, address.encoding, address.word_order)
                return round(raw_value * address.scale, 4)
            except (OSError, ModbusError) as error:
                last_error = error
                log_event(
                    self.logger,
                    logging.WARNING,
                    "modbus.read_retry",
                    channel_id=point.channel_id,
                    attempt=attempt,
                    error=str(error),
                )
        raise ModbusCommunicationError(
            "Failed to read {0}: {1}".format(point.channel_id, last_error)
        )

    def write_with_confirmation(
        self,
        point: PointConfig,
        desired_value: object,
        confirmation_mode: str,
    ) -> WriteConfirmation:
        # Deliberate S4 restriction: the Modbus adapter never writes, so no
        # new write risk is introduced. Refuse before any permission check.
        raise ModbusPermissionError(
            "Modbus adapter is read-only: write denied for channel {0}".format(point.channel_id)
        )

    def relinquish_with_confirmation(
        self,
        point: PointConfig,
        confirmation_mode: str,
    ) -> WriteConfirmation:
        raise ModbusPermissionError(
            "Modbus adapter is read-only: relinquish denied for channel {0}".format(point.channel_id)
        )

    def _modbus_address(self, point: PointConfig) -> ModbusPointConfig:
        if point.protocol != PROTOCOL_MODBUS_TCP or point.modbus is None:
            raise ModbusPermissionError(
                "Channel {0} has no Modbus address configured".format(point.channel_id)
            )
        return point.modbus

    def _read_registers(
        self,
        address: ModbusPointConfig,
        transaction_id: int,
        channel_id: str,
    ) -> Tuple[int, ...]:
        request = _build_read_request(address, transaction_id)
        sock = socket.create_connection(
            (address.host, address.port),
            timeout=self.response_timeout_seconds,
        )
        try:
            sock.settimeout(self.response_timeout_seconds)
            sock.sendall(request)
            header = _recv_exact(sock, MBAP_HEADER_LENGTH)
            response_transaction_id, protocol_id, length, unit_id = struct.unpack(">HHHB", header)
            if response_transaction_id != transaction_id:
                raise ModbusProtocolError(
                    "Transaction id mismatch for channel {0}: expected {1}, got {2}".format(
                        channel_id,
                        transaction_id,
                        response_transaction_id,
                    )
                )
            if protocol_id != MBAP_PROTOCOL_ID:
                raise ModbusProtocolError(
                    "Unexpected MBAP protocol id {0} for channel {1}".format(protocol_id, channel_id)
                )
            if unit_id != address.unit_id:
                raise ModbusProtocolError(
                    "Unit id mismatch for channel {0}: expected {1}, got {2}".format(
                        channel_id,
                        address.unit_id,
                        unit_id,
                    )
                )
            if length < 2:
                raise ModbusProtocolError(
                    "MBAP length field too small ({0}) for channel {1}".format(length, channel_id)
                )
            pdu = _recv_exact(sock, length - 1)
        finally:
            sock.close()
        return _parse_read_response_pdu(pdu, address, channel_id)

    def _next_transaction_id(self) -> int:
        self._transaction_id = (self._transaction_id % 0xFFFF) + 1
        return self._transaction_id


def _build_read_request(address: ModbusPointConfig, transaction_id: int) -> bytes:
    pdu = struct.pack(">BHH", address.function_code, address.register, address.register_count)
    mbap = struct.pack(">HHHB", transaction_id, MBAP_PROTOCOL_ID, len(pdu) + 1, address.unit_id)
    return mbap + pdu


def _parse_read_response_pdu(
    pdu: bytes,
    address: ModbusPointConfig,
    channel_id: str,
) -> Tuple[int, ...]:
    if not pdu:
        raise ModbusProtocolError("Empty Modbus response PDU for channel {0}".format(channel_id))
    function_code = pdu[0]
    if function_code == address.function_code | 0x80:
        exception_code = pdu[1] if len(pdu) > 1 else None
        raise ModbusProtocolError(
            "Modbus exception response for channel {0}: code {1} ({2})".format(
                channel_id,
                exception_code,
                _EXCEPTION_CODE_NAMES.get(exception_code, "unknown"),
            )
        )
    if function_code != address.function_code:
        raise ModbusProtocolError(
            "Unexpected function code {0} for channel {1}".format(function_code, channel_id)
        )
    expected_byte_count = 2 * address.register_count
    if len(pdu) < 2 or pdu[1] != expected_byte_count or len(pdu) != 2 + expected_byte_count:
        raise ModbusProtocolError(
            "Unexpected register payload length for channel {0}".format(channel_id)
        )
    return struct.unpack(">{0}H".format(address.register_count), pdu[2:])


def _decode_registers(registers: Sequence[int], encoding: str, word_order: str) -> float:
    format_spec = _ENCODING_FORMATS.get(encoding)
    if format_spec is None:
        raise ModbusProtocolError("Unsupported Modbus encoding: {0}".format(encoding))
    ordered = list(registers) if word_order == "big" else list(reversed(registers))
    raw = b"".join(struct.pack(">H", register) for register in ordered)
    return float(struct.unpack(format_spec, raw)[0])


def _recv_exact(sock: socket.socket, byte_count: int) -> bytes:
    chunks = []
    remaining = byte_count
    while remaining > 0:
        chunk = sock.recv(remaining)
        if not chunk:
            raise ModbusCommunicationError("Connection closed while waiting for response")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)
