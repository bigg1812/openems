import logging
import socket
import struct
import time
from typing import Optional

from .channels import BACNET_AV, BACNET_BV, PointConfig
from .config import NetworkConfig
from .logging_utils import log_event

PROP_PRESENT_VALUE = 85
WRITE_PRIORITY = 14


class BacnetError(Exception):
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

    def close(self) -> None:
        if self._owns_socket and self.sock:
            self.sock.close()

    def read_float(self, point: PointConfig) -> float:
        if not point.can_read():
            raise BacnetPermissionError("Read access denied for channel {0}".format(point.channel_id))

        last_error = None
        for attempt in range(1, self.network.retries + 2):
            try:
                payload = _build_read_packet(point.object_type, point.instance)
                self.sock.sendto(payload, (self.network.controller_ip, self.network.controller_port))
                response = self._receive_expected()
                value = _parse_float_response(response)
                if value is None:
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
        self._write_with_ack(point.channel_id, value, _build_write_packet_bool(point.instance, value))

    def write_float(self, point: PointConfig, value: float) -> None:
        if not point.can_write():
            raise BacnetPermissionError("Write access denied for channel {0}".format(point.channel_id))
        if point.object_type != BACNET_AV:
            raise BacnetPermissionError("Write target is not an Analog Value: {0}".format(point.channel_id))
        self._write_with_ack(point.channel_id, value, _build_write_packet_float(point.instance, value))

    def _write_with_ack(self, channel_id: str, desired_value: object, payload: bytes) -> None:
        last_error = None
        for attempt in range(1, self.network.retries + 2):
            try:
                self.sock.sendto(payload, (self.network.controller_ip, self.network.controller_port))
                response = self._receive_expected()
                if not _is_simple_ack(response):
                    raise BacnetProtocolError(
                        "No BACnet SimpleACK returned for channel {0}".format(channel_id)
                    )
                return
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

    def _receive_expected(self) -> bytes:
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

            if sender[0] != self.network.controller_ip or sender[1] != self.network.controller_port:
                log_event(
                    self.logger,
                    logging.WARNING,
                    "bacnet.unexpected_sender",
                    sender_ip=sender[0],
                    sender_port=sender[1],
                    expected_ip=self.network.controller_ip,
                    expected_port=self.network.controller_port,
                )
                continue
            return data
        raise BacnetCommunicationError(
            "Timed out waiting for {0}:{1}: {2}".format(
                self.network.controller_ip,
                self.network.controller_port,
                last_error or "no response",
            )
        )


def _build_read_packet(object_type: int, instance: int) -> bytes:
    apdu = bytearray([0x00, 0x04, 0x01, 0x0C])
    apdu.append(0x0C)
    apdu.extend(struct.pack(">I", (object_type << 22) | instance))
    apdu.extend([0x19, PROP_PRESENT_VALUE])
    npdu = bytes([0x01, 0x04])
    bvlc = bytes([0x81, 0x0A]) + struct.pack(">H", 4 + len(npdu) + len(apdu))
    return bvlc + npdu + bytes(apdu)


def _build_write_packet_float(instance: int, value: float) -> bytes:
    apdu = bytearray([0x00, 0x04, 0x02, 0x0F])
    apdu.append(0x0C)
    apdu.extend(struct.pack(">I", (BACNET_AV << 22) | instance))
    apdu.extend([0x19, PROP_PRESENT_VALUE])
    apdu.extend([0x3E, 0x44])
    apdu.extend(struct.pack(">f", value))
    apdu.extend([0x3F, 0x49, WRITE_PRIORITY])
    npdu = bytes([0x01, 0x04])
    bvlc = bytes([0x81, 0x0A]) + struct.pack(">H", 4 + len(npdu) + len(apdu))
    return bvlc + npdu + bytes(apdu)


def _build_write_packet_bool(instance: int, value: bool) -> bytes:
    apdu = bytearray([0x00, 0x04, 0x02, 0x0F])
    apdu.append(0x0C)
    apdu.extend(struct.pack(">I", (BACNET_BV << 22) | instance))
    apdu.extend([0x19, PROP_PRESENT_VALUE])
    apdu.append(0x3E)
    apdu.extend([0x91, 0x01 if value else 0x00])
    apdu.extend([0x3F, 0x49, WRITE_PRIORITY])
    npdu = bytes([0x01, 0x04])
    bvlc = bytes([0x81, 0x0A]) + struct.pack(">H", 4 + len(npdu) + len(apdu))
    return bvlc + npdu + bytes(apdu)


def _parse_float_response(data: bytes) -> Optional[float]:
    if not data:
        return None
    for index in range(len(data) - 6):
        if data[index] == 0x3E and data[index + 1] == 0x44 and data[index + 6] == 0x3F:
            return round(struct.unpack(">f", data[index + 2:index + 6])[0], 4)
    return None


def _is_simple_ack(data: bytes) -> bool:
    return bool(data and len(data) >= 9 and (data[6] >> 4) == 2 and data[8] == 0x0F)
