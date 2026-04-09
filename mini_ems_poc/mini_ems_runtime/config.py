import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class NetworkConfig:
    controller_ip: str
    controller_port: int
    local_ip: str
    local_port: int
    response_timeout_seconds: float
    retries: int


@dataclass(frozen=True)
class PointsConfig:
    grid_active_power_kw: int
    current_price_av: int
    grid_lockout_bv: int
    spotmarket_lockout_bv: int


@dataclass(frozen=True)
class TimingConfig:
    cycle_seconds: int
    inter_read_delay_seconds: float


@dataclass(frozen=True)
class PriceSourceConfig:
    provider: str
    region: str
    filter: int
    resolution: str
    timeout_seconds: float
    price_factor: float


@dataclass(frozen=True)
class GridLockoutConfig:
    threshold_kw: float
    clear_threshold_kw: float
    below_threshold_cycles_required: int


@dataclass(frozen=True)
class SpotMarketLockoutConfig:
    negative_quarters_min_consecutive: int
    min_valid_quarters: int
    invalid_price_sentinel: Optional[float]


@dataclass(frozen=True)
class ControllersConfig:
    grid_lockout: GridLockoutConfig
    spotmarket_lockout: SpotMarketLockoutConfig


@dataclass(frozen=True)
class SafetyConfig:
    fail_safe_output: bool
    comm_error_safe_mode_threshold: int


@dataclass(frozen=True)
class LoggingConfig:
    directory: str
    log_file: str
    state_file: str
    health_file: str
    price_cache_file: str
    spotmarket_plan_file: str
    spotmarket_override_file: str
    level: str
    stdout: bool


@dataclass(frozen=True)
class MiniEmsConfig:
    base_dir: Path
    network: NetworkConfig
    points: PointsConfig
    timing: TimingConfig
    price_source: PriceSourceConfig
    controllers: ControllersConfig
    safety: SafetyConfig
    logging: LoggingConfig

    def resolve_path(self, value: str) -> Path:
        path = Path(value)
        if path.is_absolute():
            return path
        return self.base_dir / path

    @property
    def log_dir(self) -> Path:
        return self.resolve_path(self.logging.directory)

    @property
    def log_path(self) -> Path:
        return self.log_dir / self.logging.log_file

    @property
    def state_path(self) -> Path:
        return self.resolve_path(self.logging.state_file)

    @property
    def health_path(self) -> Path:
        return self.resolve_path(self.logging.health_file)

    @property
    def price_cache_path(self) -> Path:
        return self.resolve_path(self.logging.price_cache_file)

    @property
    def spotmarket_plan_path(self) -> Path:
        return self.resolve_path(self.logging.spotmarket_plan_file)

    @property
    def spotmarket_override_path(self) -> Path:
        return self.resolve_path(self.logging.spotmarket_override_file)


def load_config(path: Path) -> MiniEmsConfig:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))

    network = _require_dict(raw, "network")
    points = _require_dict(raw, "points")
    timing = _require_dict(raw, "timing")
    price_source = _require_dict(raw, "price_source")
    controllers = _require_dict(raw, "controllers")
    grid_lockout = _require_dict(controllers, "grid_lockout")
    spotmarket_lockout = _require_dict(controllers, "spotmarket_lockout")
    safety = _require_dict(raw, "safety")
    logging = _require_dict(raw, "logging")

    config = MiniEmsConfig(
        base_dir=Path(path).resolve().parent,
        network=NetworkConfig(
            controller_ip=str(network["controller_ip"]),
            controller_port=int(network["controller_port"]),
            local_ip=str(network["local_ip"]),
            local_port=int(network["local_port"]),
            response_timeout_seconds=float(network["response_timeout_seconds"]),
            retries=int(network["retries"]),
        ),
        points=PointsConfig(
            grid_active_power_kw=int(points["grid_active_power_kw"]),
            current_price_av=int(points["current_price_av"]),
            grid_lockout_bv=int(points["grid_lockout_bv"]),
            spotmarket_lockout_bv=int(points["spotmarket_lockout_bv"]),
        ),
        timing=TimingConfig(
            cycle_seconds=int(timing["cycle_seconds"]),
            inter_read_delay_seconds=float(timing["inter_read_delay_seconds"]),
        ),
        price_source=PriceSourceConfig(
            provider=str(price_source["provider"]).lower(),
            region=str(price_source["region"]),
            filter=int(price_source["filter"]),
            resolution=str(price_source["resolution"]).lower(),
            timeout_seconds=float(price_source["timeout_seconds"]),
            price_factor=float(price_source["price_factor"]),
        ),
            controllers=ControllersConfig(
                grid_lockout=GridLockoutConfig(
                    threshold_kw=float(grid_lockout["threshold_kw"]),
                    clear_threshold_kw=float(grid_lockout["clear_threshold_kw"]),
                    below_threshold_cycles_required=int(grid_lockout["below_threshold_cycles_required"]),
                ),
                spotmarket_lockout=SpotMarketLockoutConfig(
                    negative_quarters_min_consecutive=int(
                        spotmarket_lockout.get(
                            "negative_quarters_min_consecutive",
                            spotmarket_lockout.get("negative_hours_min_consecutive"),
                        )
                    ),
                    min_valid_quarters=int(
                        spotmarket_lockout.get(
                            "min_valid_quarters",
                            spotmarket_lockout.get("min_valid_hours"),
                        )
                    ),
                    invalid_price_sentinel=_optional_float(spotmarket_lockout.get("invalid_price_sentinel")),
                ),
            ),
        safety=SafetyConfig(
            fail_safe_output=bool(safety["fail_safe_output"]),
            comm_error_safe_mode_threshold=int(safety["comm_error_safe_mode_threshold"]),
        ),
        logging=LoggingConfig(
            directory=str(logging["directory"]),
            log_file=str(logging["log_file"]),
            state_file=str(logging["state_file"]),
            health_file=str(logging["health_file"]),
            price_cache_file=str(logging["price_cache_file"]),
            spotmarket_plan_file=str(logging.get("spotmarket_plan_file", "data/spotmarket/spotmarket_tomorrow_windows.json")),
            spotmarket_override_file=str(logging.get("spotmarket_override_file", "data/spotmarket/spotmarket_manual_override.json")),
            level=str(logging["level"]).upper(),
            stdout=bool(logging["stdout"]),
        ),
    )
    _validate_config(config)
    return config


def _require_dict(raw: Dict[str, Any], key: str) -> Dict[str, Any]:
    value = raw.get(key)
    if not isinstance(value, dict):
        raise ValueError("Missing or invalid config section: {0}".format(key))
    return value


def _optional_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    return float(value)


def _validate_config(config: MiniEmsConfig) -> None:
    if config.network.controller_port <= 0 or config.network.controller_port > 65535:
        raise ValueError("controller_port must be between 1 and 65535")
    if config.network.local_port <= 0 or config.network.local_port > 65535:
        raise ValueError("local_port must be between 1 and 65535")
    if config.network.response_timeout_seconds <= 0:
        raise ValueError("response_timeout_seconds must be > 0")
    if config.network.retries < 0:
        raise ValueError("retries must be >= 0")
    if config.timing.cycle_seconds <= 0:
        raise ValueError("cycle_seconds must be > 0")
    if config.timing.inter_read_delay_seconds < 0:
        raise ValueError("inter_read_delay_seconds must be >= 0")
    if config.price_source.provider != "smard":
        raise ValueError("provider must be 'smard'")
    if config.price_source.resolution not in ("hour", "quarterhour"):
        raise ValueError("resolution must be 'hour' or 'quarterhour'")
    if config.price_source.timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be > 0")
    if config.price_source.price_factor <= 0:
        raise ValueError("price_factor must be > 0")
    if config.controllers.grid_lockout.threshold_kw <= 0:
        raise ValueError("threshold_kw must be > 0")
    if config.controllers.grid_lockout.clear_threshold_kw < config.controllers.grid_lockout.threshold_kw:
        raise ValueError("clear_threshold_kw must be >= threshold_kw")
    if config.controllers.grid_lockout.below_threshold_cycles_required <= 0:
        raise ValueError("below_threshold_cycles_required must be > 0")
    if config.controllers.spotmarket_lockout.negative_quarters_min_consecutive <= 0:
        raise ValueError("negative_quarters_min_consecutive must be > 0")
    if config.controllers.spotmarket_lockout.min_valid_quarters <= 0:
        raise ValueError("min_valid_quarters must be > 0")
    if config.price_source.resolution == "quarterhour":
        if config.controllers.spotmarket_lockout.min_valid_quarters > 96:
            raise ValueError("min_valid_quarters must be <= 96 for quarterhour resolution")
    elif config.controllers.spotmarket_lockout.min_valid_quarters > 24:
        raise ValueError("min_valid_quarters must be <= 24 for hourly resolution")
    if config.safety.comm_error_safe_mode_threshold <= 0:
        raise ValueError("comm_error_safe_mode_threshold must be > 0")
