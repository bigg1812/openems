"""Tests for the read-only Modbus TCP adapter (Roadmap S4).

All network tests run against an in-process fake Modbus TCP server on
127.0.0.1 with an ephemeral port: deterministic, offline, and fast (the
only waiting test is the timeout case, bounded by a 50 ms client timeout).
"""

import json
import logging
import socket
import struct
import tempfile
import threading
import unittest
from pathlib import Path
from typing import Dict, List

from mini_ems_poc.mini_ems_runtime.channels import ChannelRegistry, PointConfig
from mini_ems_poc.mini_ems_runtime.config import (
    PROTOCOL_BACNET,
    PROTOCOL_MODBUS_TCP,
    AdditionalInputConfig,
    ModbusPointConfig,
    PointsConfig,
    validate_raw_config,
)
from mini_ems_poc.mini_ems_runtime.modbus import (
    ModbusCommunicationError,
    ModbusError,
    ModbusPermissionError,
    ModbusTcpAdapter,
)
from mini_ems_poc.mini_ems_runtime.protocol import ProtocolRoutingAdapter
from mini_ems_poc.mini_ems_runtime.read_diagnostics import (
    QUALITY_BAD,
    QUALITY_GOOD,
    ChannelReadDiagnosticsService,
)
from mini_ems_poc.mini_ems_runtime.simulation import SimulatedBacnetAdapter

METER_CHANNEL = "meter.grid.active_power_kw"

_ENCODING_FORMATS = {
    "int16": ">h",
    "uint16": ">H",
    "int32": ">i",
    "uint32": ">I",
    "float32": ">f",
}


def _make_logger() -> logging.Logger:
    logger = logging.getLogger("mini_ems.runtime.test.modbus")
    logger.handlers.clear()
    logger.addHandler(logging.NullHandler())
    return logger


def _encode_registers(value, encoding: str, word_order: str = "big") -> List[int]:
    """Encode a value into 16-bit registers exactly like a real device would."""
    raw = struct.pack(_ENCODING_FORMATS[encoding], value)
    words = [word for (word,) in struct.iter_unpack(">H", raw)]
    if word_order == "little":
        words.reverse()
    return words


def _recv_exact(connection: socket.socket, byte_count: int) -> bytes:
    chunks = []
    remaining = byte_count
    while remaining > 0:
        chunk = connection.recv(remaining)
        if not chunk:
            raise ConnectionError("client closed connection")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


class FakeModbusServer:
    """Minimal in-process Modbus TCP server for adapter tests.

    Serves a register map for function codes 3 and 4. ``mode`` selects the
    misbehaviour under test: ``"ok"`` (normal), ``"exception"`` (Modbus
    exception response), ``"wrong_transaction_id"`` (response with a foreign
    transaction id) and ``"no_response"`` (accepts the request but never
    answers, so the client runs into its timeout).
    """

    def __init__(self, registers=None, mode: str = "ok", exception_code: int = 2):
        self.registers: Dict[int, int] = dict(registers or {})
        self.mode = mode
        self.exception_code = exception_code
        self.requests: List[Dict[str, int]] = []
        self._listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._listener.bind(("127.0.0.1", 0))
        self._listener.listen(5)
        self.host, self.port = self._listener.getsockname()
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._listener.close()
        self._thread.join(timeout=1.0)

    def set_registers(self, register: int, words: List[int]) -> None:
        self.registers.clear()
        for offset, word in enumerate(words):
            self.registers[register + offset] = word

    def _serve(self) -> None:
        while True:
            try:
                connection, _sender = self._listener.accept()
            except OSError:
                return
            with connection:
                try:
                    self._handle(connection)
                except (ConnectionError, OSError):
                    continue

    def _handle(self, connection: socket.socket) -> None:
        header = _recv_exact(connection, 7)
        transaction_id, protocol_id, length, unit_id = struct.unpack(">HHHB", header)
        pdu = _recv_exact(connection, length - 1)
        function_code, register, count = struct.unpack(">BHH", pdu)
        self.requests.append({
            "transaction_id": transaction_id,
            "protocol_id": protocol_id,
            "unit_id": unit_id,
            "function_code": function_code,
            "register": register,
            "count": count,
        })

        if self.mode == "no_response":
            # Hold the connection open without answering; the client's timeout
            # fires and closes the socket, which unblocks this recv.
            try:
                connection.recv(1)
            except OSError:
                pass
            return

        response_transaction_id = transaction_id
        if self.mode == "wrong_transaction_id":
            response_transaction_id = (transaction_id + 1) % 0x10000

        if self.mode == "exception":
            payload = struct.pack(">BB", function_code | 0x80, self.exception_code)
        else:
            words = [self.registers.get(register + offset, 0) for offset in range(count)]
            payload = struct.pack(">BB", function_code, 2 * count)
            payload += b"".join(struct.pack(">H", word) for word in words)
        mbap = struct.pack(">HHHB", response_transaction_id, 0, len(payload) + 1, unit_id)
        connection.sendall(mbap + payload)


def _modbus_point(
    server: FakeModbusServer,
    register: int = 19026,
    unit_id: int = 1,
    function_code: int = 3,
    encoding: str = "float32",
    word_order: str = "big",
    scale: float = 1.0,
    channel_id: str = METER_CHANNEL,
) -> PointConfig:
    return PointConfig(
        channel_id=channel_id,
        object_type=None,
        instance=None,
        access="read",
        description="Modbus test point",
        protocol=PROTOCOL_MODBUS_TCP,
        modbus=ModbusPointConfig(
            host=server.host,
            register=register,
            port=server.port,
            unit_id=unit_id,
            function_code=function_code,
            encoding=encoding,
            word_order=word_order,
            scale=scale,
        ),
    )


class ModbusFramingAndDecodingTest(unittest.TestCase):
    def setUp(self) -> None:
        self.logger = _make_logger()
        self.server = FakeModbusServer()
        self.addCleanup(self.server.stop)
        self.adapter = ModbusTcpAdapter(self.logger, response_timeout_seconds=0.5, retries=0)

    def test_read_float32_holding_register_with_scale(self) -> None:
        # float32 over two registers via FC3, scaled to kW like Variante B.
        self.server.set_registers(19026, _encode_registers(123400.0, "float32"))
        point = _modbus_point(self.server, register=19026, unit_id=7, scale=0.001)

        value = self.adapter.read_float(point)

        self.assertAlmostEqual(value, 123.4, places=4)
        request = self.server.requests[0]
        self.assertEqual(request["protocol_id"], 0)
        self.assertEqual(request["unit_id"], 7)
        self.assertEqual(request["function_code"], 3)
        self.assertEqual(request["register"], 19026)
        self.assertEqual(request["count"], 2)

    def test_read_input_register_uses_function_code_4(self) -> None:
        self.server.set_registers(100, _encode_registers(4210, "uint16"))
        point = _modbus_point(self.server, register=100, function_code=4, encoding="uint16")

        value = self.adapter.read_float(point)

        self.assertEqual(value, 4210.0)
        self.assertEqual(self.server.requests[0]["function_code"], 4)
        self.assertEqual(self.server.requests[0]["count"], 1)

    def test_decoding_covers_sign_word_order_and_scale(self) -> None:
        # (encoding, word_order, raw value, scale, expected float)
        cases = [
            ("int16", "big", -123, 1.0, -123.0),
            ("int16", "big", -123, 0.1, -12.3),
            ("uint16", "big", 65535, 1.0, 65535.0),
            ("int32", "big", -8_000_000, 1.0, -8000000.0),
            ("int32", "little", -8_000_000, 1.0, -8000000.0),
            ("uint32", "little", 3_000_000_000, 1.0, 3000000000.0),
            ("float32", "big", 12.5, 1.0, 12.5),
            ("float32", "little", 12.5, 1.0, 12.5),
        ]
        for encoding, word_order, raw_value, scale, expected in cases:
            with self.subTest(encoding=encoding, word_order=word_order, scale=scale):
                self.server.set_registers(200, _encode_registers(raw_value, encoding, word_order))
                point = _modbus_point(
                    self.server,
                    register=200,
                    encoding=encoding,
                    word_order=word_order,
                    scale=scale,
                )
                self.assertAlmostEqual(self.adapter.read_float(point), expected, places=4)


class ModbusErrorHandlingTest(unittest.TestCase):
    def setUp(self) -> None:
        self.logger = _make_logger()
        self.adapter = ModbusTcpAdapter(self.logger, response_timeout_seconds=0.05, retries=0)

    def test_timeout_raises_communication_error(self) -> None:
        server = FakeModbusServer(mode="no_response")
        self.addCleanup(server.stop)
        point = _modbus_point(server)

        with self.assertRaises(ModbusCommunicationError):
            self.adapter.read_float(point)

    def test_exception_response_raises_with_code(self) -> None:
        server = FakeModbusServer(mode="exception", exception_code=2)
        self.addCleanup(server.stop)
        point = _modbus_point(server)

        with self.assertRaises(ModbusError) as context:
            self.adapter.read_float(point)
        self.assertIn("exception", str(context.exception))
        self.assertIn("illegal data address", str(context.exception))

    def test_wrong_transaction_id_raises(self) -> None:
        server = FakeModbusServer(mode="wrong_transaction_id")
        self.addCleanup(server.stop)
        server.set_registers(19026, _encode_registers(1.0, "float32"))
        point = _modbus_point(server)

        with self.assertRaises(ModbusError) as context:
            self.adapter.read_float(point)
        self.assertIn("Transaction id mismatch", str(context.exception))

    def test_write_with_confirmation_is_refused(self) -> None:
        server = FakeModbusServer()
        self.addCleanup(server.stop)
        point = _modbus_point(server)

        with self.assertRaises(ModbusPermissionError) as context:
            self.adapter.write_with_confirmation(point, 1.0, "ack_only")
        self.assertIn("read-only", str(context.exception))
        # The refusal happens before any I/O: no request reached the server.
        self.assertEqual(server.requests, [])

    def test_read_failure_is_classified_as_quality_bad(self) -> None:
        # The diagnostics service must treat a Modbus failure exactly like a
        # BACnet failure — via the neutral AdapterError base, quality="bad".
        server = FakeModbusServer(mode="exception")
        self.addCleanup(server.stop)
        registry = _registry_with_input(_meter_input_modbus(server))
        service = ChannelReadDiagnosticsService(
            registry=registry,
            adapter=ProtocolRoutingAdapter({PROTOCOL_MODBUS_TCP: self.adapter}),
            logger=self.logger,
        )

        diagnostic = service.read_float_channel(METER_CHANNEL)

        self.assertEqual(diagnostic.status, "error")
        self.assertEqual(diagnostic.quality, QUALITY_BAD)
        self.assertIsNone(diagnostic.value)


def _registry_with_input(input_config: AdditionalInputConfig) -> ChannelRegistry:
    return ChannelRegistry.from_points_config(
        PointsConfig(
            grid_active_power_kw=300,
            current_price_av=1000,
            grid_lockout_bv=400,
            spotmarket_lockout_bv=401,
        ),
        additional_inputs={input_config.channel_id: input_config},
    )


def _meter_input_modbus(server: FakeModbusServer) -> AdditionalInputConfig:
    return AdditionalInputConfig(
        channel_id=METER_CHANNEL,
        object_type=None,
        instance=None,
        description="Hauptzähler Wirkleistung Netzanschluss",
        plausible_min=-750.0,
        plausible_max=750.0,
        protocol=PROTOCOL_MODBUS_TCP,
        modbus=ModbusPointConfig(
            host=server.host,
            register=19026,
            port=server.port,
            encoding="float32",
            scale=0.001,
        ),
    )


def _meter_input_bacnet() -> AdditionalInputConfig:
    return AdditionalInputConfig(
        channel_id=METER_CHANNEL,
        object_type=2,
        instance=310,
        description="Hauptzähler Wirkleistung Netzanschluss",
        plausible_min=-750.0,
        plausible_max=750.0,
    )


class CanonicalChannelAcrossProtocolsTest(unittest.TestCase):
    """S4 Definition of Done: the same canonical channel can come from BACnet
    or Modbus without any change to control or diagnostics logic — only the
    per-point config and the routed adapter differ."""

    def setUp(self) -> None:
        self.logger = _make_logger()
        self._temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp_dir.cleanup)
        self.values_path = Path(self._temp_dir.name) / "sample_values.json"
        self.values_path.write_text(
            json.dumps({"channels": {METER_CHANNEL: 123.4}}),
            encoding="utf-8",
        )

    def _read_channel(self, registry: ChannelRegistry, adapter) -> "object":
        # Identical diagnostics call for both protocols: nothing here knows
        # whether the value comes from BACnet or Modbus.
        point = registry.get(METER_CHANNEL)
        service = ChannelReadDiagnosticsService(
            registry=registry,
            adapter=adapter,
            logger=self.logger,
        )
        return service.read_float_channel(
            METER_CHANNEL,
            plausible_min=point.plausible_min,
            plausible_max=point.plausible_max,
            max_age_seconds=point.max_age_seconds,
        )

    def test_same_channel_reads_from_bacnet_and_modbus(self) -> None:
        # Path A: canonical channel served by the simulated BACnet adapter.
        bacnet_registry = _registry_with_input(_meter_input_bacnet())
        bacnet_adapter = ProtocolRoutingAdapter({
            PROTOCOL_BACNET: SimulatedBacnetAdapter(self.values_path, self.logger),
        })
        bacnet_diagnostic = self._read_channel(bacnet_registry, bacnet_adapter)

        # Path B: same canonical channel served by the Modbus TCP adapter.
        server = FakeModbusServer()
        self.addCleanup(server.stop)
        server.set_registers(19026, _encode_registers(123400.0, "float32"))
        modbus_registry = _registry_with_input(_meter_input_modbus(server))
        modbus_adapter = ProtocolRoutingAdapter({
            PROTOCOL_MODBUS_TCP: ModbusTcpAdapter(
                self.logger,
                response_timeout_seconds=0.5,
                retries=0,
            ),
        })
        modbus_diagnostic = self._read_channel(modbus_registry, modbus_adapter)

        for label, diagnostic in (("bacnet", bacnet_diagnostic), ("modbus", modbus_diagnostic)):
            with self.subTest(protocol=label):
                self.assertEqual(diagnostic.channel_id, METER_CHANNEL)
                self.assertEqual(diagnostic.status, "ok")
                self.assertEqual(diagnostic.quality, QUALITY_GOOD)
                self.assertTrue(diagnostic.plausible)
        self.assertAlmostEqual(bacnet_diagnostic.value, modbus_diagnostic.value, places=4)


class ModbusConfigTest(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp_dir.cleanup)

    def _load(self, additional_inputs: List[dict]):
        raw = {
            "network": {
                "controller_ip": "127.0.0.1",
                "controller_port": 47808,
                "local_ip": "127.0.0.1",
                "local_port": 47809,
                "response_timeout_seconds": 1.0,
                "retries": 0,
            },
            "points": {
                "grid_active_power_kw": 300,
                "current_price_av": 1000,
                "grid_lockout_bv": 400,
                "spotmarket_lockout_bv": 401,
            },
            "additional_inputs": additional_inputs,
            "timing": {"cycle_seconds": 60, "inter_read_delay_seconds": 0.0},
            "price_source": {
                "provider": "smard",
                "region": "DE-LU",
                "filter": 4169,
                "resolution": "quarterhour",
                "timeout_seconds": 30,
                "price_factor": 0.1,
            },
            "controllers": {
                "grid_lockout": {
                    "enabled": False,
                    "threshold_kw": 5.0,
                    "clear_threshold_kw": 5.5,
                    "below_threshold_cycles_required": 3,
                },
                "spotmarket_lockout": {
                    "negative_quarters_min_consecutive": 8,
                    "min_valid_quarters": 96,
                    "invalid_price_sentinel": None,
                },
            },
            "safety": {"fail_safe_output": False, "comm_error_safe_mode_threshold": 2},
            "logging": {
                "directory": "logs",
                "log_file": "mini_ems.log",
                "state_file": "runtime/state.json",
                "health_file": "runtime/health.json",
                "price_cache_file": "data/spotmarket_price_cache.json",
                "level": "INFO",
                "stdout": False,
            },
        }
        return validate_raw_config(raw, base_dir=Path(self._temp_dir.name))

    def _modbus_entry(self, **overrides) -> dict:
        modbus = {
            "host": "192.168.244.60",
            "port": 1502,
            "unit_id": 7,
            "register": 19026,
            "function_code": 4,
            "encoding": "int32",
            "word_order": "little",
            "scale": 0.01,
        }
        modbus.update(overrides.pop("modbus", {}))
        entry = {
            "channel_id": METER_CHANNEL,
            "protocol": "modbus_tcp",
            "description": "Hauptzähler Wirkleistung",
            "modbus": modbus,
            "plausible_min": -750.0,
            "plausible_max": 750.0,
            "max_age_seconds": 120,
        }
        entry.update(overrides)
        return entry

    def test_modbus_additional_input_is_parsed(self) -> None:
        config = self._load([self._modbus_entry()])
        input_config = config.additional_inputs[METER_CHANNEL]
        self.assertEqual(input_config.protocol, PROTOCOL_MODBUS_TCP)
        self.assertIsNone(input_config.object_type)
        self.assertIsNone(input_config.instance)
        modbus = input_config.modbus
        self.assertEqual(modbus.host, "192.168.244.60")
        self.assertEqual(modbus.port, 1502)
        self.assertEqual(modbus.unit_id, 7)
        self.assertEqual(modbus.register, 19026)
        self.assertEqual(modbus.function_code, 4)
        self.assertEqual(modbus.encoding, "int32")
        self.assertEqual(modbus.word_order, "little")
        self.assertEqual(modbus.scale, 0.01)
        self.assertEqual(modbus.register_count, 2)

    def test_modbus_defaults_apply(self) -> None:
        entry = self._modbus_entry()
        entry["modbus"] = {"host": "192.168.244.60", "register": 19026}
        config = self._load([entry])
        modbus = config.additional_inputs[METER_CHANNEL].modbus
        self.assertEqual(modbus.port, 502)
        self.assertEqual(modbus.unit_id, 1)
        self.assertEqual(modbus.function_code, 3)
        self.assertEqual(modbus.encoding, "float32")
        self.assertEqual(modbus.word_order, "big")
        self.assertEqual(modbus.scale, 1.0)

    def test_entry_without_protocol_field_stays_bacnet(self) -> None:
        # Backwards compatibility: existing configs behave exactly as before.
        config = self._load([
            {
                "channel_id": "site.outdoor_temperature_c",
                "object_type": "ai",
                "instance": 1801,
                "description": "Outdoor air temperature",
            }
        ])
        input_config = config.additional_inputs["site.outdoor_temperature_c"]
        self.assertEqual(input_config.protocol, PROTOCOL_BACNET)
        self.assertIsNone(input_config.modbus)
        self.assertEqual(input_config.object_type, 0)
        self.assertEqual(input_config.instance, 1801)

    def test_unknown_protocol_is_rejected(self) -> None:
        entry = self._modbus_entry(protocol="mqtt")
        with self.assertRaises(ValueError):
            self._load([entry])

    def test_modbus_entry_without_address_block_is_rejected(self) -> None:
        entry = self._modbus_entry()
        del entry["modbus"]
        with self.assertRaises(ValueError):
            self._load([entry])

    def test_invalid_function_code_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self._load([self._modbus_entry(modbus={"function_code": 6})])

    def test_invalid_encoding_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self._load([self._modbus_entry(modbus={"encoding": "float64"})])

    def test_invalid_word_order_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self._load([self._modbus_entry(modbus={"word_order": "swapped"})])


if __name__ == "__main__":
    unittest.main()
