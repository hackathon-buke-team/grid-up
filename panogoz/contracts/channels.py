"""Bir bağlantı (fider ucu) için izlenen kanal kataloğu.

Yarışma brifinin "Dikkate Alınabilecek Veriler" listesindeki kanalları temsil
eder: akım, yüzey/kablo sıcaklığı, nem, kısmi deşarj (PD), ark flaş.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Phase(str, Enum):
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"


class ChannelKind(str, Enum):
    CURRENT = "current"
    SURFACE_TEMP = "surface_temp"
    AMBIENT_TEMP = "ambient_temp"
    HUMIDITY = "humidity"
    PD_INDEX = "pd_index"
    ARC_TRIP = "arc_trip"


@dataclass(frozen=True)
class Reading:
    t_s: float
    connection_id: str
    kind: ChannelKind
    value: float
    phase: Phase | None = None
