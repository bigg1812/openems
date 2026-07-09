from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

from .config import (
    DEFAULT_BACNET_WRITE_PRIORITY,
    PROTOCOL_BACNET,
    AdditionalInputConfig,
    DdcHeartbeatConfig,
    ModbusPointConfig,
    OutputPoliciesConfig,
    PointsConfig,
)

BACNET_AI = 0
BACNET_AV = 2
BACNET_BV = 5

GRID_ACTIVE_POWER_CHANNEL = "grid.active_power_kw"
CURRENT_PRICE_CHANNEL = "tariff.current_price_ct_kwh"
GRID_LOCKOUT_CHANNEL = "ems.lockout_grid"
SPOTMARKET_LOCKOUT_CHANNEL = "ems.lockout_spotmarket"
HEALTH_CHANNEL = "system.health"
EDGE_HEARTBEAT_CHANNEL = "system.edge_heartbeat"


@dataclass(frozen=True)
class PointConfig:
    channel_id: str
    # BACnet raw address; None for points read via another protocol (S4).
    object_type: Optional[int]
    instance: Optional[int]
    access: str
    description: str
    controller_ip: Optional[str] = None
    controller_port: Optional[int] = None
    plausible_min: Optional[float] = None
    plausible_max: Optional[float] = None
    include_in_health: bool = False
    read_interval_cycles: int = 1
    max_age_seconds: Optional[float] = None
    # Protocol routing (S4): the runtime picks the adapter per point via
    # ProtocolRoutingAdapter; "bacnet" keeps the existing behaviour.
    protocol: str = PROTOCOL_BACNET
    modbus: Optional[ModbusPointConfig] = None
    write_priority: int = DEFAULT_BACNET_WRITE_PRIORITY
    relinquish_enabled: bool = False

    def can_read(self) -> bool:
        return self.access in ("read", "readwrite")

    def can_write(self) -> bool:
        return self.access in ("write", "readwrite")


class ChannelRegistry:
    def __init__(
        self,
        points_by_id: Dict[str, PointConfig],
        additional_input_channel_ids: Optional[List[str]] = None,
        output_channel_ids: Optional[List[str]] = None,
    ):
        self._points_by_id = dict(points_by_id)
        self._additional_input_channel_ids = list(additional_input_channel_ids or [])
        self._output_channel_ids = list(output_channel_ids or [
            CURRENT_PRICE_CHANNEL,
            GRID_LOCKOUT_CHANNEL,
            SPOTMARKET_LOCKOUT_CHANNEL,
        ])

    @classmethod
    def from_points_config(
        cls,
        points: PointsConfig,
        additional_inputs: Optional[Dict[str, AdditionalInputConfig]] = None,
        output_policies: Optional[OutputPoliciesConfig] = None,
        ddc_heartbeat: Optional[DdcHeartbeatConfig] = None,
    ) -> "ChannelRegistry":
        def output_point_policy(channel_id: str) -> tuple[int, bool]:
            if output_policies is None:
                return DEFAULT_BACNET_WRITE_PRIORITY, False
            policy = output_policies.for_channel(channel_id)
            return policy.write_priority, policy.relinquish_enabled

        current_price_priority, current_price_relinquish = output_point_policy(CURRENT_PRICE_CHANNEL)
        grid_lockout_priority, grid_lockout_relinquish = output_point_policy(GRID_LOCKOUT_CHANNEL)
        spotmarket_priority, spotmarket_relinquish = output_point_policy(SPOTMARKET_LOCKOUT_CHANNEL)
        output_channel_ids = [
            CURRENT_PRICE_CHANNEL,
            GRID_LOCKOUT_CHANNEL,
            SPOTMARKET_LOCKOUT_CHANNEL,
        ]
        registry = {
            GRID_ACTIVE_POWER_CHANNEL: PointConfig(
                channel_id=GRID_ACTIVE_POWER_CHANNEL,
                object_type=BACNET_AV,
                instance=points.grid_active_power_kw,
                access="read",
                description="Grid active power in kW",
                plausible_min=-1_000_000.0,
                plausible_max=1_000_000.0,
            ),
            CURRENT_PRICE_CHANNEL: PointConfig(
                channel_id=CURRENT_PRICE_CHANNEL,
                object_type=BACNET_AV,
                instance=points.current_price_av,
                access="readwrite",
                description="Current spot price in ct/kWh",
                write_priority=current_price_priority,
                relinquish_enabled=current_price_relinquish,
            ),
            GRID_LOCKOUT_CHANNEL: PointConfig(
                channel_id=GRID_LOCKOUT_CHANNEL,
                object_type=BACNET_BV,
                instance=points.grid_lockout_bv,
                access="write",
                description="Fail-safe grid lockout output",
                write_priority=grid_lockout_priority,
                relinquish_enabled=grid_lockout_relinquish,
            ),
            SPOTMARKET_LOCKOUT_CHANNEL: PointConfig(
                channel_id=SPOTMARKET_LOCKOUT_CHANNEL,
                object_type=BACNET_BV,
                instance=points.spotmarket_lockout_bv,
                access="write",
                description="Fail-safe spot market lockout output",
                write_priority=spotmarket_priority,
                relinquish_enabled=spotmarket_relinquish,
            ),
        }
        additional_input_channel_ids: List[str] = []
        for channel_id, input_config in (additional_inputs or {}).items():
            registry[channel_id] = PointConfig(
                channel_id=channel_id,
                object_type=input_config.object_type,
                instance=input_config.instance,
                access="read",
                description=input_config.description,
                controller_ip=input_config.controller_ip,
                controller_port=input_config.controller_port,
                plausible_min=input_config.plausible_min,
                plausible_max=input_config.plausible_max,
                include_in_health=input_config.include_in_health,
                read_interval_cycles=input_config.read_interval_cycles,
                max_age_seconds=input_config.max_age_seconds,
                protocol=input_config.protocol,
                modbus=input_config.modbus,
            )
            additional_input_channel_ids.append(channel_id)
        if ddc_heartbeat is not None and ddc_heartbeat.enabled:
            heartbeat_priority, heartbeat_relinquish = output_point_policy(EDGE_HEARTBEAT_CHANNEL)
            registry[EDGE_HEARTBEAT_CHANNEL] = PointConfig(
                channel_id=EDGE_HEARTBEAT_CHANNEL,
                object_type=ddc_heartbeat.object_type,
                instance=ddc_heartbeat.instance,
                access="write",
                description="Mini EMS edge-to-DDC heartbeat counter",
                controller_ip=ddc_heartbeat.controller_ip,
                controller_port=ddc_heartbeat.controller_port,
                write_priority=heartbeat_priority,
                relinquish_enabled=heartbeat_relinquish,
            )
            output_channel_ids.append(EDGE_HEARTBEAT_CHANNEL)
        return cls(
            registry,
            additional_input_channel_ids=additional_input_channel_ids,
            output_channel_ids=output_channel_ids,
        )

    def get(self, channel_id: str) -> PointConfig:
        if channel_id not in self._points_by_id:
            raise KeyError("Unknown channel_id: {0}".format(channel_id))
        return self._points_by_id[channel_id]

    def all_points(self) -> Iterable[PointConfig]:
        return self._points_by_id.values()

    def input_channel_ids(self) -> List[str]:
        return [point.channel_id for point in self._points_by_id.values() if point.can_read()]

    def output_channel_ids(self) -> List[str]:
        return list(self._output_channel_ids)

    def internal_channels(self) -> List[str]:
        return [HEALTH_CHANNEL]

    def additional_input_channel_ids(self) -> List[str]:
        return list(self._additional_input_channel_ids)
