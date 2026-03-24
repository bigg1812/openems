from dataclasses import dataclass
from typing import Dict, Iterable, List

from .config import PointsConfig

BACNET_AV = 2
BACNET_BV = 5

GRID_ACTIVE_POWER_CHANNEL = "grid.active_power_kw"
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
        for hour in range(24):
            channel_id = "tariff.price_hour_{0:02d}".format(hour)
            registry[channel_id] = PointConfig(
                channel_id=channel_id,
                object_type=BACNET_AV,
                instance=points.spot_price_start_hour_instance + hour,
                access="read",
                description="Spot price for hour {0:02d}:00".format(hour),
            )
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
        return [GRID_LOCKOUT_CHANNEL, SPOTMARKET_LOCKOUT_CHANNEL]

    def price_channel_ids(self) -> List[str]:
        return ["tariff.price_hour_{0:02d}".format(hour) for hour in range(24)]

    def internal_channels(self) -> List[str]:
        return [HEALTH_CHANNEL]
