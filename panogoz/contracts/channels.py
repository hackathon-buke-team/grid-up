"""Kanal kataloğu — tek doğruluk kaynağı.

Görev dağılımı belgesindeki "57 kanal" iddiası kod seviyesinde doğrulanmadı.
Burada gerçek pano donanımına (12 fider, 74 cıvatalı bağlantıdan 40'ı izleniyor,
MPR-53CS akım/gerilim analizörü, ABB TVOC-2 ark koruma, HFCT30 PD sensörü,
2500/5 ana CT oranı, 250/400 A fider anma akımı) dayanan somut bir katalog
üretiliyor; sayı ne çıkarsa odur.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Family(str, Enum):
    THERMAL = "thermal"
    CURRENT = "current"
    NEUTRAL = "neutral"
    HUMIDITY = "humidity"
    PD = "pd"
    ARC = "arc"


@dataclass(frozen=True)
class Channel:
    channel_id: str
    family: Family
    unit: str
    feeder_id: str | None
    nominal_current_a: float | None


FEEDERS = [f"F{idx:02d}" for idx in range(1, 13)]
FEEDER_RATED_A = {f: (400.0 if (i % 3 == 0) else 250.0) for i, f in enumerate(FEEDERS)}
MONITORED_NEUTRAL_FEEDERS = FEEDERS[:4]


def _build_thermal_channels() -> list[Channel]:
    channels: list[Channel] = []
    for feeder in FEEDERS:
        rated = FEEDER_RATED_A[feeder]
        for phase in ("L1", "L2", "L3"):
            channels.append(Channel(f"T_{feeder}_{phase}", Family.THERMAL, "degC", feeder, rated))
    for feeder in MONITORED_NEUTRAL_FEEDERS:
        channels.append(Channel(f"T_{feeder}_N", Family.NEUTRAL, "degC", feeder, FEEDER_RATED_A[feeder]))
    return channels


THERMAL_CHANNELS = _build_thermal_channels()

CURRENT_CHANNELS = [
    Channel("I_MAIN_L1", Family.CURRENT, "A", None, 2500.0),
    Channel("I_MAIN_L2", Family.CURRENT, "A", None, 2500.0),
    Channel("I_MAIN_L3", Family.CURRENT, "A", None, 2500.0),
    Channel("I_MAIN_N", Family.NEUTRAL, "A", None, 2500.0),
]

ENCLOSURE_CHANNELS = [
    Channel("RH_PANO", Family.HUMIDITY, "%RH", None, None),
    Channel("T_DUVAR", Family.HUMIDITY, "degC", None, None),
]

PD_CHANNELS = [Channel(f"PD_{phase}", Family.PD, "score", None, None) for phase in ("L1", "L2", "L3")]

ARC_CHANNELS = [
    Channel("ARC_DETECTOR_HEALTH", Family.ARC, "bool", None, None),
    Channel("ARC_SENSOR_STATUS", Family.ARC, "bitfield", None, None),
    Channel("ARC_TRIP_COUNT", Family.ARC, "count", None, None),
]

ALL_CHANNELS = THERMAL_CHANNELS + CURRENT_CHANNELS + ENCLOSURE_CHANNELS + PD_CHANNELS + ARC_CHANNELS
CHANNELS_BY_ID = {c.channel_id: c for c in ALL_CHANNELS}


def siblings_of(channel_id: str) -> list[str]:
    """Aynı fiderdeki diğer faz sıcaklık kanalları — theta kardeş grubu."""
    ch = CHANNELS_BY_ID[channel_id]
    if ch.family != Family.THERMAL:
        return []
    return [
        c.channel_id
        for c in THERMAL_CHANNELS
        if c.feeder_id == ch.feeder_id and c.channel_id != channel_id and c.family == Family.THERMAL
    ]
