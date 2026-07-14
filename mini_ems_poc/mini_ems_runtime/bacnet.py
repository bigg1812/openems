import logging
import socket
import struct
import time
from typing import Optional

from .channels import BACNET_AV, BACNET_BV, PointConfig
from .config import DEFAULT_BACNET_WRITE_PRIORITY, NetworkConfig
from .logging_utils import log_event
from .protocol import AdapterError, WriteConfirmation

# Backwards-compatible alias: the confirmation type is now protocol-neutral.
BacnetWriteConfirmation = WriteConfirmation

PROP_PRESENT_VALUE = 85
WRITE_PRIORITY = DEFAULT_BACNET_WRITE_PRIORITY
READ_PROPERTY_SERVICE_CHOICE = 0x0C
WRITE_PROPERTY_SERVICE_CHOICE = 0x0F


class BacnetError(AdapterError):
    """Base class for BACnet adapter errors."""


class BacnetPermissionError(BacnetError):
    """Raised when a point is accessed outside the allowlist."""


class BacnetCommunicationError(BacnetError):
    """Raised when communication with the controller fails."""


class BacnetProtocolError(BacnetError):
    """Raised when the controller returns an unexpected BACnet frame."""


class BacnetAdapter:
    def __init__(self, network: NetworkConfig, logger: logging.Logger, sock: Optional[socket.socket] = None):
        self.network = network
        self.logger = logger
        self._owns_socket = sock is None
        self.sock = sock or self._open_socket()
        self._invoke_id = 0

    def close(self) -> None:
        if self._owns_socket and self.sock:
            self.sock.close()

    def read_float(self, point: PointConfig) -> float:
        if not point.can_read():
            raise BacnetPermissionError("Read access denied for channel {0}".format(point.channel_id))

        last_error = None
        invoke_id = self._next_invoke_id()
        payload = _build_read_packet(point.object_type, point.instance, invoke_id)
        target_ip, target_port = self._target_address(point)
        for attempt in range(1, self.network.retries + 2):
            try:
                self.sock.sendto(payload, (target_ip, target_port))
                response = self._receive_matching(
                    matcher=lambda data: _is_read_property_ack(
                        data,
                        invoke_id=invoke_id,
                        object_type=point.object_type,
                        instance=point.instance,
                    ),
                    channel_id=point.channel_id,
                    expected_description="ReadPropertyACK",
                    expected_ip=target_ip,
                    expected_port=target_port,
                )
                value = _parse_read_property_ack_float(
                    response,
                    object_type=point.object_type,
                    instance=point.instance,
                )
                if value is None:
                    log_event(
                        self.logger,
                        logging.WARNING,
                        "bacnet.read_parse_failed",
                        channel_id=point.channel_id,
                        raw_hex=response.hex(),
                    )
                    raise BacnetProtocolError(
                        "No float present value in response for channel {0}".format(point.channel_id)
                    )
                return value
            except (OSError, BacnetError) as error:
                last_error = error
                log_event(
                    self.logger,
                    logging.WARNING,
                    "bacnet.read_retry",
                    channel_id=point.channel_id,
                    attempt=attempt,
                    error=str(error),
                )
        raise BacnetCommunicationError(
            "Failed to read {0}: {1}".format(point.channel_id, last_error)
        )

    def write_bool(self, point: PointConfig, value: bool) -> None:
        if not point.can_write():
            raise BacnetPermissionError("Write access denied for channel {0}".format(point.channel_id))
        if point.object_type != BACNET_BV:
            raise BacnetPermissionError("Write target is not a Binary Value: {0}".format(point.channel_id))
        invoke_id = self._next_invoke_id()
        self._write_with_ack(
            point.channel_id,
            value,
            _build_write_packet_bool(point.instance, value, invoke_id, point.write_priority),
            invoke_id,
            point,
        )

    def write_float(self, point: PointConfig, value: float) -> None:
        if not point.can_write():
            raise BacnetPermissionError("Write access denied for channel {0}".format(point.channel_id))
        if point.object_type != BACNET_AV:
            raise BacnetPermissionError("Write target is not an Analog Value: {0}".format(point.channel_id))
        invoke_id = self._next_invoke_id()
        self._write_with_ack(
            point.channel_id,
            value,
            _build_write_packet_float(point.instance, value, invoke_id, point.write_priority),
            invoke_id,
            point,
        )

    def write_with_confirmation(
        self,
        point: PointConfig,
        desired_value: object,
        confirmation_mode: str,
    ) -> WriteConfirmation:
        if not point.can_write():
            raise BacnetPermissionError("Write access denied for channel {0}".format(point.channel_id))

        invoke_id = self._next_invoke_id()
        if point.object_type == BACNET_BV:
            payload = _build_write_packet_bool(point.instance, bool(desired_value), invoke_id, point.write_priority)
        elif point.object_type == BACNET_AV:
            payload = _build_write_packet_float(point.instance, float(desired_value), invoke_id, point.write_priority)
        else:
            raise BacnetPermissionError(
                "Unsupported BACnet object type for channel {0}".format(point.channel_id)
            )

        try:
            attempts = self._write_with_ack(point.channel_id, desired_value, payload, invoke_id, point)
            return WriteConfirmation(
                channel_id=point.channel_id,
                confirmed=True,
                ack_received=True,
                confirmation_mode=confirmation_mode,
                confirmation_source="ack",
                desired_value=desired_value,
                attempts=attempts,
            )
        except BacnetError as ack_error:
            if confirmation_mode == "ack_or_readback" and point.object_type == BACNET_AV:
                try:
                    readback_value = self.read_float(point)
                except BacnetError as readback_error:
                    return WriteConfirmation(
                        channel_id=point.channel_id,
                        confirmed=False,
                        ack_received=False,
                        confirmation_mode=confirmation_mode,
                        confirmation_source=None,
                        desired_value=desired_value,
                        attempts=self.network.retries + 1,
                        error="{0}; readback failed: {1}".format(ack_error, readback_error),
                    )

                if _float_values_match(float(desired_value), readback_value):
                    return WriteConfirmation(
                        channel_id=point.channel_id,
                        confirmed=True,
                        ack_received=False,
                        confirmation_mode=confirmation_mode,
                        confirmation_source="readback",
                        desired_value=desired_value,
                        attempts=self.network.retries + 1,
                        readback_value=readback_value,
                    )

                return WriteConfirmation(
                    channel_id=point.channel_id,
                    confirmed=False,
                    ack_received=False,
                    confirmation_mode=confirmation_mode,
                    confirmation_source=None,
                    desired_value=desired_value,
                    attempts=self.network.retries + 1,
                    readback_value=readback_value,
                    error=(
                        "{0}; readback mismatch: expected {1}, got {2}".format(
                            ack_error,
                            desired_value,
                            readback_value,
                        )
                    ),
                )

            return WriteConfirmation(
                channel_id=point.channel_id,
                confirmed=False,
                ack_received=False,
                confirmation_mode=confirmation_mode,
                confirmation_source=None,
                desired_value=desired_value,
                attempts=self.network.retries + 1,
                error=str(ack_error),
            )

    def relinquish_with_confirmation(
        self,
        point: PointConfig,
        confirmation_mode: str,
    ) -> WriteConfirmation:
        if not point.can_write():
            raise BacnetPermissionError("Write access denied for channel {0}".format(point.channel_id))
        if not point.relinquish_enabled:
            raise BacnetPermissionError("Relinquish is not enabled for channel {0}".format(point.channel_id))
        if point.object_type not in (BACNET_AV, BACNET_BV):
            raise BacnetPermissionError(
                "Unsupported BACnet object type for channel {0}".format(point.channel_id)
            )

        invoke_id = self._next_invoke_id()
        payload = _build_write_packet_null(
            point.object_type,
            point.instance,
            invoke_id,
            point.write_priority,
        )
        try:
            attempts = self._write_with_ack(point.channel_id, None, payload, invoke_id, point)
            return WriteConfirmation(
                channel_id=point.channel_id,
                confirmed=True,
                ack_received=True,
                confirmation_mode=confirmation_mode,
                confirmation_source="ack",
                desired_value=None,
                attempts=attempts,
            )
        except BacnetError as ack_error:
            return WriteConfirmation(
                channel_id=point.channel_id,
                confirmed=False,
                ack_received=False,
                confirmation_mode=confirmation_mode,
                confirmation_source=None,
                desired_value=None,
                attempts=self.network.retries + 1,
                error=str(ack_error),
            )

    def _write_with_ack(
        self,
        channel_id: str,
        desired_value: object,
        payload: bytes,
        invoke_id: int,
        point: PointConfig,
    ) -> int:
        last_error = None
        target_ip, target_port = self._target_address(point)
        for attempt in range(1, self.network.retries + 2):
            try:
                self.sock.sendto(payload, (target_ip, target_port))
                self._receive_matching(
                    matcher=lambda data: _is_simple_ack(
                        data,
                        invoke_id=invoke_id,
                        service_choice=WRITE_PROPERTY_SERVICE_CHOICE,
                    ),
                    channel_id=channel_id,
                    expected_description="SimpleACK",
                    expected_ip=target_ip,
                    expected_port=target_port,
                )
                return attempt
            except (OSError, BacnetError) as error:
                last_error = error
                log_event(
                    self.logger,
                    logging.WARNING,
                    "bacnet.write_retry",
                    channel_id=channel_id,
                    attempt=attempt,
                    desired_value=desired_value,
                    error=str(error),
                )
        raise BacnetCommunicationError(
            "Failed to write {0}: {1}".format(channel_id, last_error)
        )

    def _open_socket(self) -> socket.socket:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((self.network.local_ip, self.network.local_port))
        except OSError as error:
            sock.close()
            raise BacnetCommunicationError(
                "Unable to bind UDP socket to {0}:{1}: {2}".format(
                    self.network.local_ip,
                    self.network.local_port,
                    error,
                )
            )
        return sock

    def _receive_matching(
        self,
        matcher,
        channel_id: str,
        expected_description: str,
        expected_ip: str,
        expected_port: int,
    ) -> bytes:
        deadline = time.monotonic() + self.network.response_timeout_seconds
        last_error = None
        while time.monotonic() < deadline:
            timeout = max(0.0, deadline - time.monotonic())
            self.sock.settimeout(timeout)
            try:
                data, sender = self.sock.recvfrom(1500)
            except socket.timeout as error:
                last_error = error
                break
            except OSError as error:
                raise BacnetCommunicationError(str(error))

            if sender[0] != expected_ip or sender[1] != expected_port:
                log_event(
                    self.logger,
                    logging.WARNING,
                    "bacnet.unexpected_sender",
                    sender_ip=sender[0],
                    sender_port=sender[1],
                    expected_ip=expected_ip,
                    expected_port=expected_port,
                )
                continue
            if not matcher(data):
                log_event(
                    self.logger,
                    logging.INFO,
                    "bacnet.discarded_response",
                    channel_id=channel_id,
                    expected=expected_description,
                    raw_hex=data.hex(),
                )
                continue
            return data
        raise BacnetCommunicationError(
            "Timed out waiting for {0}:{1}: {2}".format(
                expected_ip,
                expected_port,
                last_error or "no response",
            )
        )

    def _next_invoke_id(self) -> int:
        self._invoke_id = (self._invoke_id % 255) + 1
        return self._invoke_id

    def _target_address(self, point: PointConfig) -> tuple[str, int]:
        return (
            point.controller_ip or self.network.controller_ip,
            point.controller_port or self.network.controller_port,
        )


def _build_read_packet(object_type: int, instance: int, invoke_id: int) -> bytes:
    apdu = bytearray([0x00, 0x04, invoke_id, READ_PROPERTY_SERVICE_CHOICE])
    apdu.append(0x0C)
    apdu.extend(struct.pack(">I", (object_type << 22) | instance))
    apdu.extend([0x19, PROP_PRESENT_VALUE])
    npdu = bytes([0x01, 0x04])
    bvlc = bytes([0x81, 0x0A]) + struct.pack(">H", 4 + len(npdu) + len(apdu))
    return bvlc + npdu + bytes(apdu)


def _build_write_packet_float(instance: int, value: float, invoke_id: int, write_priority: int) -> bytes:
    apdu = bytearray([0x00, 0x04, invoke_id, WRITE_PROPERTY_SERVICE_CHOICE])
    apdu.append(0x0C)
    apdu.extend(struct.pack(">I", (BACNET_AV << 22) | instance))
    apdu.extend([0x19, PROP_PRESENT_VALUE])
    apdu.extend([0x3E, 0x44])
    apdu.extend(struct.pack(">f", value))
    apdu.extend([0x3F, 0x49, write_priority])
    npdu = bytes([0x01, 0x04])
    bvlc = bytes([0x81, 0x0A]) + struct.pack(">H", 4 + len(npdu) + len(apdu))
    return bvlc + npdu + bytes(apdu)


def _build_write_packet_bool(instance: int, value: bool, invoke_id: int, write_priority: int) -> bytes:
    apdu = bytearray([0x00, 0x04, invoke_id, WRITE_PROPERTY_SERVICE_CHOICE])
    apdu.append(0x0C)
    apdu.extend(struct.pack(">I", (BACNET_BV << 22) | instance))
    apdu.extend([0x19, PROP_PRESENT_VALUE])
    apdu.append(0x3E)
    apdu.extend([0x91, 0x01 if value else 0x00])
    apdu.extend([0x3F, 0x49, write_priority])
    npdu = bytes([0x01, 0x04])
    bvlc = bytes([0x81, 0x0A]) + struct.pack(">H", 4 + len(npdu) + len(apdu))
    return bvlc + npdu + bytes(apdu)


def _build_write_packet_null(object_type: int, instance: int, invoke_id: int, write_priority: int) -> bytes:
    apdu = bytearray([0x00, 0x04, invoke_id, WRITE_PROPERTY_SERVICE_CHOICE])
    apdu.append(0x0C)
    apdu.extend(struct.pack(">I", (object_type << 22) | instance))
    apdu.extend([0x19, PROP_PRESENT_VALUE])
    apdu.extend([0x3E, 0x00, 0x3F, 0x49, write_priority])
    npdu = bytes([0x01, 0x04])
    bvlc = bytes([0x81, 0x0A]) + struct.pack(">H", 4 + len(npdu) + len(apdu))
    return bvlc + npdu + bytes(apdu)


def _parse_read_property_ack_float(data: bytes, object_type: int, instance: int) -> Optional[float]:
    value_section = _read_property_value_section(data, object_type, instance)
    if value_section is None:
        return None
    real_value = _scan_real_value(value_section)
    if real_value is not None:
        return real_value
    if object_type == BACNET_BV:
        enumerated_value = _scan_enumerated_value(value_section)
        return float(enumerated_value) if enumerated_value is not None else None
    return None


def _is_simple_ack(data: bytes, invoke_id: int, service_choice: int) -> bool:
    return _matches_apdu_header(
        data,
        pdu_type=2,
        invoke_id=invoke_id,
        service_choice=service_choice,
    )


def _is_read_property_ack(data: bytes, invoke_id: int, object_type: int, instance: int) -> bool:
    if not _matches_apdu_header(
        data,
        pdu_type=3,
        invoke_id=invoke_id,
        service_choice=READ_PROPERTY_SERVICE_CHOICE,
    ):
        return False
    return _read_property_value_section(data, object_type, instance) is not None


def _matches_apdu_header(data: bytes, pdu_type: int, invoke_id: int, service_choice: int) -> bool:
    return bool(
        data
        and len(data) >= 9
        and (data[6] >> 4) == pdu_type
        and data[7] == invoke_id
        and data[8] == service_choice
    )


def _read_property_value_section(data: bytes, object_type: int, instance: int) -> Optional[bytes]:
    if len(data) < 9:
        return None
    payload = data[9:]
    object_marker = bytes([0x0C]) + struct.pack(">I", (object_type << 22) | instance)
    property_marker = bytes([0x19, PROP_PRESENT_VALUE])
    object_index = payload.find(object_marker)
    if object_index == -1:
        return None
    property_index = payload.find(property_marker, object_index + len(object_marker))
    if property_index == -1:
        return None
    return payload[property_index + len(property_marker):]


def _scan_real_value(data: bytes) -> Optional[float]:
    if not data:
        return None
    for index in range(len(data) - 4):
        if data[index] == 0x3C:
            return round(struct.unpack(">f", data[index + 1:index + 5])[0], 4)
    for index in range(len(data) - 6):
        if data[index] == 0x3E and data[index + 1] == 0x44 and data[index + 6] == 0x3F:
            return round(struct.unpack(">f", data[index + 2:index + 6])[0], 4)
    for index in range(len(data) - 4):
        if data[index] == 0x44:
            return round(struct.unpack(">f", data[index + 1:index + 5])[0], 4)
    return None


def _scan_enumerated_value(data: bytes) -> Optional[int]:
    for index, tag in enumerate(data):
        if tag >> 4 != 9 or tag & 0x08:
            continue
        length = tag & 0x07
        if length < 1 or length > 4 or index + 1 + length > len(data):
            continue
        return int.from_bytes(data[index + 1:index + 1 + length], "big")
    return None


def _float_values_match(expected: float, actual: float, tolerance: float = 0.001) -> bool:
    return abs(expected - actual) <= tolerance
