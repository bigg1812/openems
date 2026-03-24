import argparse
import logging
import time
from pathlib import Path

from .bacnet import BacnetAdapter, BacnetCommunicationError
from .channels import ChannelRegistry
from .config import load_config
from .cycle import CycleRunner
from .logging_utils import log_event, setup_logging
from .state_store import StateStore


def main() -> int:
    args = _parse_args()
    config = load_config(Path(args.config).resolve())
    logger = setup_logging(config)
    registry = ChannelRegistry.from_points_config(config.points)
    state_store = StateStore(config.state_path, registry.output_channel_ids())

    try:
        adapter = BacnetAdapter(config.network, logger)
    except BacnetCommunicationError as error:
        log_event(logger, logging.ERROR, "app.start_failed", error=str(error))
        return 1

    runner = CycleRunner(
        config=config,
        registry=registry,
        adapter=adapter,
        state_store=state_store,
        logger=logger,
    )

    log_event(
        logger,
        logging.INFO,
        "app.started",
        config_path=str(Path(args.config).resolve()),
        mode="once" if args.once else "loop",
        cycle_seconds=config.timing.cycle_seconds,
    )

    try:
        if args.once:
            runner.run_cycle()
            return 0

        while True:
            runner.run_cycle()
            time.sleep(config.timing.cycle_seconds)
    except KeyboardInterrupt:
        log_event(logger, logging.INFO, "app.stopped", reason="keyboard_interrupt")
        return 0
    finally:
        adapter.close()


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
