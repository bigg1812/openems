import argparse
import logging
import time
import traceback
from pathlib import Path

from .bacnet import BacnetAdapter, BacnetCommunicationError
from .channels import ChannelRegistry
from .config import PROTOCOL_BACNET, PROTOCOL_MODBUS_TCP, load_config
from .cycle import CycleRunner
from .http_api import MiniEmsApiServer
from .logging_utils import log_event, setup_logging
from .modbus import ModbusTcpAdapter
from .price_cache import SpotmarketPriceCacheService
from .price_provider_smard import SmardPriceProvider
from .protocol import ProtocolRoutingAdapter
from .read_diagnostics import ChannelReadDiagnosticsService
from .resources import read_app_version, resource_base_dir
from .runtime_db import RuntimeDatabase
from .simulation import SimulatedBacnetAdapter, SimulatedModbusAdapter, SimulatedSpotmarketPriceService
from .spotmarket_plan import SpotmarketManualOverrideStore, SpotmarketPlanWriter
from .state_store import StateStore


def main() -> int:
    args = _parse_args()
    config_path = Path(args.config).resolve()
    config = load_config(config_path)
    logger = setup_logging(config)
    registry = ChannelRegistry.from_points_config(
        config.points,
        config.additional_inputs,
        config.output_policies,
        config.ddc_heartbeat,
    )
    resource_base = resource_base_dir(config.base_dir)
    app_version = read_app_version(resource_base)
    state_store = StateStore(config.state_path, registry.output_channel_ids())
    runtime_db = RuntimeDatabase(config.database_path)

    try:
        adapter = _build_protocol_adapter(config, logger)
    except BacnetCommunicationError as error:
        log_event(logger, logging.ERROR, "app.start_failed", error=str(error))
        return 1

    read_diagnostics = ChannelReadDiagnosticsService(
        registry=registry,
        adapter=adapter,
        logger=logger,
    )

    spotmarket_plan_writer = SpotmarketPlanWriter(
        config.spotmarket_plan_path,
        negative_threshold_ct_kwh=0.0,
        min_consecutive_quarters=config.controllers.spotmarket_lockout.negative_quarters_min_consecutive,
    )
    runner = CycleRunner(
        config=config,
        registry=registry,
        adapter=adapter,
        state_store=state_store,
        logger=logger,
        price_service=_build_price_service(config, logger),
        spotmarket_plan_writer=spotmarket_plan_writer,
        spotmarket_override_store=SpotmarketManualOverrideStore(
            config.spotmarket_override_path,
        ),
        read_diagnostics=read_diagnostics,
        runtime_db=runtime_db,
    )
    api_server = MiniEmsApiServer(
        api_config=config.api,
        runtime_db=runtime_db,
        health_path=config.health_path,
        state_path=config.state_path,
        price_cache_path=config.price_cache_path,
        spotmarket_plan_path=config.spotmarket_plan_path,
        # dashboard/, mini_ems_runtime/templates/ and data/weather/ are bundled
        # resources: next to the config in a Git checkout, next to the executable
        # when frozen (H2). Everything downstream derives from dashboard_dir(.parent).
        dashboard_dir=resource_base / "dashboard",
        logger=logger,
        read_diagnostics=read_diagnostics,
        config_path=config_path,
        spotmarket_plan_writer=spotmarket_plan_writer,
        price_source_resolution=config.price_source.resolution,
        app_version=app_version,
    )

    log_event(
        logger,
        logging.INFO,
        "app.started",
        config_path=str(config_path),
        mode="once" if args.once else "loop",
        environment=config.runtime.environment,
        bacnet_mode=config.runtime.bacnet_mode,
        real_writes_enabled=config.runtime.real_writes_enabled,
        cycle_seconds=config.timing.cycle_seconds,
    )

    try:
        if args.once:
            runner.run_cycle()
            return 0

        api_server.start()
        while True:
            try:
                runner.run_cycle()
            except KeyboardInterrupt:
                raise
            except Exception as error:
                log_event(
                    logger,
                    logging.ERROR,
                    "app.cycle_failed",
                    error_type=error.__class__.__name__,
                    error=str(error),
                    traceback=traceback.format_exc(),
                )
                time.sleep(max(5, config.timing.cycle_seconds))
                continue

            time.sleep(config.timing.cycle_seconds)
    except KeyboardInterrupt:
        log_event(logger, logging.INFO, "app.stopped", reason="keyboard_interrupt")
        return 0
    finally:
        api_server.stop()
        adapter.close()


def _build_protocol_adapter(config, logger):
    # One routing adapter in front of the concrete adapters keeps cycle and
    # diagnostics protocol-agnostic; each point selects its adapter via the
    # protocol field (default "bacnet", so existing configs are unchanged).
    if config.runtime.bacnet_mode == "simulated":
        log_event(
            logger,
            logging.INFO,
            "app.simulation_enabled",
            values_file=str(config.simulation_values_path),
            real_writes_enabled=config.runtime.real_writes_enabled,
        )
        return ProtocolRoutingAdapter({
            PROTOCOL_BACNET: SimulatedBacnetAdapter(config.simulation_values_path, logger),
            PROTOCOL_MODBUS_TCP: SimulatedModbusAdapter(config.simulation_values_path, logger),
        })
    return ProtocolRoutingAdapter({
        PROTOCOL_BACNET: BacnetAdapter(config.network, logger),
        PROTOCOL_MODBUS_TCP: ModbusTcpAdapter(
            logger,
            response_timeout_seconds=config.network.response_timeout_seconds,
            retries=config.network.retries,
        ),
    })


def _build_price_service(config, logger):
    if config.runtime.bacnet_mode == "simulated":
        return SimulatedSpotmarketPriceService(
            cache_path=config.price_cache_path,
            prices_path=config.simulation_prices_path,
            resolution=config.price_source.resolution,
            logger=logger,
        )
    return SpotmarketPriceCacheService(
        config.price_cache_path,
        SmardPriceProvider(config.price_source),
    )


def _parse_args() -> argparse.Namespace:
    default_config = Path(__file__).resolve().parents[1] / "config.json"
    parser = argparse.ArgumentParser(description="Mini EMS proof-of-concept runtime")
    parser.add_argument(
        "--config",
        default=str(default_config),
        help="Path to the JSON configuration file.",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--once",
        action="store_true",
        help="Run a single control cycle and exit.",
    )
    mode.add_argument(
        "--loop",
        action="store_true",
        help="Run continuously with the configured cycle time.",
    )
    args = parser.parse_args()
    if not args.once and not args.loop:
        args.once = True
    return args
