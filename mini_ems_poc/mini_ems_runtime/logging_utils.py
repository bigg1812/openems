import json
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime, timezone

from .config import MiniEmsConfig


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def setup_logging(config: MiniEmsConfig, *, supervisor: bool = False) -> logging.Logger:
    config.log_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("mini_ems.supervisor" if supervisor else "mini_ems")
    logger.setLevel(_parse_level(config.logging.level))
    for handler in logger.handlers[:]:
        handler.close()
        logger.removeHandler(handler)
    logger.propagate = False

    formatter = logging.Formatter("%(message)s")

    log_path = config.log_dir / "supervisor.log" if supervisor else config.log_path
    file_handler = RotatingFileHandler(log_path, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    if config.logging.stdout:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

    return logger


def log_event(logger: logging.Logger, level: int, event: str, **fields) -> None:
    payload = {
        "timestamp": utcnow_iso(),
        "level": logging.getLevelName(level),
        "event": event,
    }
    payload.update(fields)
    logger.log(level, json.dumps(payload, ensure_ascii=True, sort_keys=True))


def _parse_level(value: str) -> int:
    level = getattr(logging, value.upper(), None)
    if isinstance(level, int):
        return level
    return logging.INFO
