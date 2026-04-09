from dataclasses import dataclass
from typing import Dict, Iterable, List

from .config import PointsConfig

BACNET_AV = 2
BACNET_BV = 5

GRID_ACTIVE_POWER_CHANNEL = "grid.active_power_kw"
CURRENT_PRICE_CHANNEL = "tariff.current_price_ct_kwh"
GRID_LOCKOUT_CHANNEL = "ems.lockout_grid"
SPOTMARKET_LOCKOUT_CHANNEL = "ems.lockout_spotmarket"
HEALTH_CHANNEL = "system.health"


@dataclass(frozen=True)
class PointConfig:
    channel_id: str
    object_type: int
    instance: int
    access: str
    description: str

    def can_read(self) -> bool:
        return self.access in ("read", "readwrite")

    def can_write(self) -> bool:
        return self.access in ("write", "readwrite")


class ChannelRegistry:
    def __init__(self, points_by_id: Dict[str, PointConfig]):
        self._points_by_id = dict(points_by_id)

    @classmethod
    def from_points_config(cls, points: PointsConfig) -> "ChannelRegistry":
        registry = {
            GRID_ACTIVE_POWER_CHANNEL: PointConfig(
                channel_id=GRID_ACTIVE_POWER_CHANNEL,
                object_type=BACNET_AV,
                instance=points.grid_active_power_kw,
                access="read",
                description="Grid active power in kW",
            ),
            CURRENT_PRICE_CHANNEL: PointConfig(
                channel_id=CURRENT_PRICE_CHANNEL,
                object_type=BACNET_AV,
                instance=points.current_price_av,
                access="write",
                description="Current spot price in ct/kWh",
            ),
            GRID_LOCKOUT_CHANNEL: PointConfig(
                channel_id=GRID_LOCKOUT_CHANNEL,
                object_type=BACNET_BV,
                instance=points.grid_lockout_bv,
                access="write",
                description="Fail-safe grid lockout output",
            ),
            SPOTMARKET_LOCKOUT_CHANNEL: PointConfig(
                channel_id=SPOTMARKET_LOCKOUT_CHANNEL,
                object_type=BACNET_BV,
                instance=points.spotmarket_lockout_bv,
                access="write",
                description="Fail-safe spot market lockout output",
            ),
        }
        return cls(registry)

    def get(self, channel_id: str) -> PointConfig:
        if channel_id not in self._points_by_id:
            raise KeyError("Unknown channel_id: {0}".format(channel_id))
        return self._points_by_id[channel_id]

    def all_points(self) -> Iterable[PointConfig]:
        return self._points_by_id.values()

    def input_channel_ids(self) -> List[str]:
        return [point.channel_id for point in self._points_by_id.values() if point.can_read()]

    def output_channel_ids(self) -> List[str]:
        return [CURRENT_PRICE_CHANNEL, GRID_LOCKOUT_CHANNEL, SPOTMARKET_LOCKOUT_CHANNEL]

    def internal_channels(self) -> List[str]:
        return [HEALTH_CHANNEL]
