import json
from dataclasses import dataclass, field
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
class AdditionalInputConfig:
    channel_id: str
    object_type: int
    instance: int
    description: str
    controller_ip: Optional[str] = None
    controller_port: Optional[int] = None
    plausible_min: Optional[float] = None
    plausible_max: Optional[float] = None
    include_in_health: bool = False
    read_interval_cycles: int = 1


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
    enabled: bool = True


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
class OutputPolicyConfig:
    confirmation_mode: str
    criticality: str


@dataclass(frozen=True)
class OutputPoliciesConfig:
    current_price: OutputPolicyConfig
    grid_lockout: OutputPolicyConfig
    spotmarket_lockout: OutputPolicyConfig

    def for_channel(self, channel_id: str) -> OutputPolicyConfig:
        mapping = {
            "tariff.current_price_ct_kwh": self.current_price,
            "ems.lockout_grid": self.grid_lockout,
            "ems.lockout_spotmarket": self.spotmarket_lockout,
        }
        policy = mapping.get(channel_id)
        if policy is None:
            raise KeyError("Missing output policy for channel: {0}".format(channel_id))
        return policy


@dataclass(frozen=True)
class RuntimeConfig:
    environment: str = "ipc"
    bacnet_mode: str = "real"
    real_writes_enabled: bool = True


@dataclass(frozen=True)
class SimulationConfig:
    values_file: str = "sim/sample_values.json"
    prices_file: str = "sim/sample_prices.json"


@dataclass(frozen=True)
class DatabaseConfig:
    sqlite_file: str


@dataclass(frozen=True)
class ApiConfig:
    enabled: bool
    host: str
    port: int
    history_default_limit: int


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
    additional_inputs: Dict[str, AdditionalInputConfig] = field(default_factory=dict)
    output_policies: OutputPoliciesConfig = field(default_factory=lambda: OutputPoliciesConfig(
        current_price=OutputPolicyConfig(
            confirmation_mode="ack_or_readback",
            criticality="noncritical",
        ),
        grid_lockout=OutputPolicyConfig(
            confirmation_mode="ack_only",
            criticality="critical",
        ),
        spotmarket_lockout=OutputPolicyConfig(
            confirmation_mode="ack_only",
            criticality="critical",
        ),
    ))
    database: DatabaseConfig = field(default_factory=lambda: DatabaseConfig(sqlite_file="data/runtime/mini_ems.sqlite"))
    api: ApiConfig = field(default_factory=lambda: ApiConfig(
        enabled=True,
        host="127.0.0.1",
        port=8090,
        history_default_limit=96,
    ))
    runtime: RuntimeConfig = field(default_factory=RuntimeConfig)
    simulation: SimulationConfig = field(default_factory=SimulationConfig)

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

    @property
    def database_path(self) -> Path:
        return self.resolve_path(self.database.sqlite_file)

    @property
    def simulation_values_path(self) -> Path:
        return self.resolve_path(self.simulation.values_file)

    @property
    def simulation_prices_path(self) -> Path:
        return self.resolve_path(self.simulation.prices_file)


def load_config(path: Path) -> MiniEmsConfig:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))

    network = _require_dict(raw, "network")
    points = _require_dict(raw, "points")
    additional_inputs_raw = raw.get("additional_inputs")
    timing = _require_dict(raw, "timing")
    price_source = _require_dict(raw, "price_source")
    controllers = _require_dict(raw, "controllers")
    grid_lockout = _require_dict(controllers, "grid_lockout")
    spotmarket_lockout = _require_dict(controllers, "spotmarket_lockout")
    safety = _require_dict(raw, "safety")
    outputs = _optional_dict(raw.get("outputs"))
    database = _optional_dict(raw.get("database"))
    api = _optional_dict(raw.get("api"))
    runtime = _optional_dict(raw.get("runtime"))
    simulation = _optional_dict(raw.get("simulation"))
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
        additional_inputs=_load_additional_inputs(
            additional_inputs_raw,
            default_controller_port=int(network["controller_port"]),
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
                    enabled=bool(grid_lockout.get("enabled", True)),
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
        output_policies=OutputPoliciesConfig(
            current_price=_load_output_policy(
                outputs.get("current_price"),
                default_confirmation_mode="ack_or_readback",
                default_criticality="noncritical",
            ),
            grid_lockout=_load_output_policy(
                outputs.get("grid_lockout"),
                default_confirmation_mode="ack_only",
                default_criticality="critical",
            ),
            spotmarket_lockout=_load_output_policy(
                outputs.get("spotmarket_lockout"),
                default_confirmation_mode="ack_only",
                default_criticality="critical",
            ),
        ),
        database=DatabaseConfig(
            sqlite_file=str(database.get("sqlite_file", "data/runtime/mini_ems.sqlite")),
        ),
        api=ApiConfig(
            enabled=bool(api.get("enabled", True)),
            host=str(api.get("host", "127.0.0.1")),
            port=int(api.get("port", 8090)),
            history_default_limit=int(api.get("history_default_limit", 96)),
        ),
        runtime=RuntimeConfig(
            environment=str(runtime.get("environment", "ipc")).lower(),
            bacnet_mode=str(runtime.get("bacnet_mode", "real")).lower(),
            real_writes_enabled=bool(runtime.get("real_writes_enabled", runtime.get("writes_enabled", True))),
        ),
        simulation=SimulationConfig(
            values_file=str(simulation.get("values_file", "sim/sample_values.json")),
            prices_file=str(simulation.get("prices_file", "sim/sample_prices.json")),
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


def _optional_dict(value: object) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _load_output_policy(
    raw: object,
    default_confirmation_mode: str,
    default_criticality: str,
) -> OutputPolicyConfig:
    raw = raw if isinstance(raw, dict) else {}
    return OutputPolicyConfig(
        confirmation_mode=str(raw.get("confirmation_mode", default_confirmation_mode)).lower(),
        criticality=str(raw.get("criticality", default_criticality)).lower(),
    )


def _load_additional_inputs(
    raw: object,
    *,
    default_controller_port: int,
) -> Dict[str, AdditionalInputConfig]:
    if raw is None:
        return {}
    if not isinstance(raw, list):
        raise ValueError("additional_inputs must be a list")

    additional_inputs: Dict[str, AdditionalInputConfig] = {}
    for entry in raw:
        if not isinstance(entry, dict):
            raise ValueError("each additional_inputs entry must be an object")
        channel_id = str(entry["channel_id"])
        additional_inputs[channel_id] = AdditionalInputConfig(
            channel_id=channel_id,
            object_type=_parse_object_type(entry["object_type"]),
            instance=int(entry["instance"]),
            description=str(entry.get("description", channel_id)),
            controller_ip=_optional_text(entry.get("controller_ip")),
            controller_port=int(entry.get("controller_port", default_controller_port)),
            plausible_min=_optional_float(entry.get("plausible_min")),
            plausible_max=_optional_float(entry.get("plausible_max")),
            include_in_health=bool(entry.get("include_in_health", False)),
            read_interval_cycles=int(entry.get("read_interval_cycles", 1)),
        )
    return additional_inputs


def _parse_object_type(value: object) -> int:
    if isinstance(value, int):
        return value
    normalized = str(value).strip().lower()
    mapping = {
        "ai": 0,
        "analog_input": 0,
        "analog-input": 0,
        "av": 2,
        "analog_value": 2,
        "analog-value": 2,
        "bv": 5,
        "binary_value": 5,
        "binary-value": 5,
    }
    if normalized not in mapping:
        raise ValueError("Unsupported BACnet object_type: {0}".format(value))
    return mapping[normalized]


def _optional_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    return float(value)


def _optional_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    return str(value)


def _validate_config(config: MiniEmsConfig) -> None:
    if config.runtime.environment not in ("ipc", "local", "test"):
        raise ValueError("runtime.environment must be one of ['ipc', 'local', 'test']")
    if config.runtime.bacnet_mode not in ("real", "simulated"):
        raise ValueError("runtime.bacnet_mode must be one of ['real', 'simulated']")
    if config.runtime.environment == "local" and config.runtime.bacnet_mode != "simulated":
        raise ValueError("local environment must use simulated BACnet mode")
    if config.runtime.bacnet_mode == "simulated" and config.runtime.real_writes_enabled:
        raise ValueError("simulated BACnet mode requires real_writes_enabled=false")
    if config.runtime.bacnet_mode == "real" and not config.runtime.real_writes_enabled:
        raise ValueError("real_writes_enabled=false is only supported with simulated BACnet mode")
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
    allowed_confirmation_modes = {"ack_only", "ack_or_readback"}
    allowed_criticalities = {"critical", "noncritical"}
    for channel_id in (
        "tariff.current_price_ct_kwh",
        "ems.lockout_grid",
        "ems.lockout_spotmarket",
    ):
        policy = config.output_policies.for_channel(channel_id)
        if policy.confirmation_mode not in allowed_confirmation_modes:
            raise ValueError(
                "confirmation_mode for {0} must be one of {1}".format(
                    channel_id,
                    sorted(allowed_confirmation_modes),
                )
            )
        if policy.criticality not in allowed_criticalities:
            raise ValueError(
                "criticality for {0} must be one of {1}".format(
                    channel_id,
                    sorted(allowed_criticalities),
                )
            )
    if config.api.port <= 0 or config.api.port > 65535:
        raise ValueError("api.port must be between 1 and 65535")
    if config.api.history_default_limit <= 0:
        raise ValueError("api.history_default_limit must be > 0")
    core_channels = {
        "grid.active_power_kw",
        "tariff.current_price_ct_kwh",
        "ems.lockout_grid",
        "ems.lockout_spotmarket",
    }
    from .channels import ChannelRegistry, GRID_ACTIVE_POWER_CHANNEL

    grid_point = ChannelRegistry.from_points_config(config.points).get(GRID_ACTIVE_POWER_CHANNEL)
    if (
        grid_point.plausible_min is not None
        and grid_point.plausible_max is not None
        and grid_point.plausible_min > grid_point.plausible_max
    ):
        raise ValueError(
            "core channel plausible_min must be <= plausible_max for {0}".format(GRID_ACTIVE_POWER_CHANNEL)
        )
    for channel_id, input_config in config.additional_inputs.items():
        if channel_id in core_channels:
            raise ValueError("additional_inputs channel_id duplicates a core channel: {0}".format(channel_id))
        if input_config.controller_port is None:
            continue
        if input_config.controller_port <= 0 or input_config.controller_port > 65535:
            raise ValueError(
                "additional_inputs controller_port must be between 1 and 65535 for {0}".format(channel_id)
            )
        if (
            input_config.plausible_min is not None
            and input_config.plausible_max is not None
            and input_config.plausible_min > input_config.plausible_max
        ):
            raise ValueError(
                "additional_inputs plausible_min must be <= plausible_max for {0}".format(channel_id)
            )
        if input_config.read_interval_cycles <= 0:
            raise ValueError(
                "additional_inputs read_interval_cycles must be > 0 for {0}".format(channel_id)
            )
