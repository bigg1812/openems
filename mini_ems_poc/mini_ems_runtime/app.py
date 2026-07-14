import argparse
import json
import logging
import os
import secrets
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

from .bacnet import BacnetAdapter, BacnetCommunicationError
from .channels import ChannelRegistry
from .commissioning import CommissioningService, CommissioningStore
from .config import (
    PROTOCOL_BACNET,
    PROTOCOL_MODBUS_TCP,
    build_default_site_config,
    validate_raw_config,
)
from .cycle import CycleRunner
from .http_api import MiniEmsApiServer
from .identity import IdentityStore
from .logging_utils import log_event, setup_logging
from .modbus import ModbusTcpAdapter
from .price_cache import SpotmarketPriceCacheService
from .price_provider_smard import SmardPriceProvider
from .protocol import ProtocolRoutingAdapter
from .read_diagnostics import ChannelReadDiagnosticsService
from .resources import is_frozen, read_app_version, resource_base_dir
from .runtime_db import RuntimeDatabase
from .simulation import SimulatedBacnetAdapter, SimulatedModbusAdapter, SimulatedSpotmarketPriceService
from .spotmarket_plan import SpotmarketManualOverrideStore, SpotmarketPlanWriter
from .state_store import StateStore
from .site_store import SiteConfigStore


def main() -> int:
    args = _parse_args()
    site_dir = _site_dir_from_args(args)
    site_store = SiteConfigStore(site_dir)
    identity_store = IdentityStore(site_dir)
    raw, startup_message = _load_or_initialize_site(site_store, args.import_config)
    if args.reset_admin_code:
        if identity_store.is_initialized():
            temporary_password = secrets.token_urlsafe(15)
            admin = identity_store.reset_first_admin_password(temporary_password)
            print("Temporäres Mini-EMS-Passwort für {0}: {1}".format(admin.username, temporary_password))
            print("Nach der Anmeldung bitte unter Konten und Rollen ein eigenes Passwort setzen.")
            return 0
        token = secrets.token_urlsafe(9)
        api = raw.setdefault("api", {})
        if not isinstance(api, dict):
            raise ValueError("Die gespeicherte API-Konfiguration ist ungültig.")
        api["config_admin_token"] = token
        validate_raw_config(raw, base_dir=site_dir)
        site_store.save_revision(
            raw,
            action="admin_code.reset",
            actor="local_cli",
            details={"restart_required": True},
        )
        print("Neuer Mini-EMS-Freigabecode: {0}".format(token))
        return 0
    if startup_message:
        print(startup_message, file=sys.stderr)
    config = validate_raw_config(raw, base_dir=site_dir)
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
    commissioning = CommissioningService(
        store=CommissioningStore(identity_store.path),
        identity_store=identity_store,
        adapter=adapter,
        config=config,
        logger=logger,
    )
    commissioning.recover_unfinished()

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
        site_store=site_store,
        spotmarket_plan_writer=spotmarket_plan_writer,
        price_source_resolution=config.price_source.resolution,
        app_version=app_version,
        identity_store=identity_store,
        secure_cookies=config.runtime.environment == "ipc",
        commissioning_service=commissioning,
    )

    log_event(
        logger,
        logging.INFO,
        "app.started",
        site_dir=str(site_dir),
        site_revision=site_store.active_revision(),
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
        commissioning.shutdown()
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
    parser = argparse.ArgumentParser(description="Mini EMS proof-of-concept runtime")
    parser.add_argument(
        "--site-dir",
        default=None,
        help="Operational site directory containing site.sqlite and runtime data.",
    )
    parser.add_argument(
        "--import-config",
        default=None,
        help="One-time migration source for an existing JSON configuration.",
    )
    parser.add_argument(
        "--reset-admin-code",
        "--reset-admin-password",
        dest="reset_admin_code",
        action="store_true",
        help="Reset the initial approval code or an existing Admin password and exit.",
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


def _site_dir_from_args(args: argparse.Namespace) -> Path:
    if args.site_dir:
        return Path(args.site_dir).expanduser().resolve()
    configured = os.environ.get("MINI_EMS_SITE_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    if is_frozen():
        program_data = os.environ.get("PROGRAMDATA", r"C:\ProgramData")
        return (Path(program_data) / "MiniEMS").resolve()
    return (Path(__file__).resolve().parents[1] / "runtime" / "local" / "site").resolve()


def _load_or_initialize_site(
    store: SiteConfigStore,
    import_config: str | None,
) -> tuple[dict[str, object], str | None]:
    if store.has_active_config():
        return store.active_config(), None

    explicit_source = Path(import_config).expanduser().resolve() if import_config else None
    legacy_source = store.site_dir / "config.json"
    source = explicit_source or (legacy_source if legacy_source.exists() else None)
    if source is not None:
        raw = json.loads(source.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("Die Importkonfiguration muss ein JSON-Objekt sein.")
        validate_raw_config(raw, base_dir=store.site_dir)
        revision = store.save_revision(
            raw,
            action="legacy_config.import",
            actor="system",
            details={"source_name": source.name, "restart_required": False},
        )
        migration_warning = ""
        if explicit_source is None:
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            try:
                source.replace(store.site_dir / "config.json.migrated.{0}.bak".format(timestamp))
            except OSError as error:
                migration_warning = " Die alte Datei konnte nicht umbenannt werden und wird ignoriert: {0}".format(error)
        return raw, "Bestehende Standortkonfiguration in site.sqlite migriert (Revision {0}).{1}".format(
            revision,
            migration_warning,
        )

    token = secrets.token_urlsafe(9)
    raw = build_default_site_config(token)
    validate_raw_config(raw, base_dir=store.site_dir)
    store.save_revision(
        raw,
        action="site.bootstrap",
        actor="system",
        details={"restart_required": False, "setup_required": True},
    )
    return raw, (
        "Neuer Standort-Speicher angelegt. Einmaliger Freigabecode für die UI: {0} "
        "(bei Verlust: --reset-admin-code).".format(token)
    )
