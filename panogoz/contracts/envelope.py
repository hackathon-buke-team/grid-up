"""Uç düğümden gelen tek ölçüm mesajının zarfı ve cihaz sözleşmesi."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Envelope:
    device_id: str
    channel_id: str
    ts: float
    seq: int
    value: float
    unit: str


@dataclass(frozen=True)
class DeviceContract:
    """dev.period_s: cihazın ilan ettiği yayın kadansı; tazelik pencereleri buradan türer."""

    device_id: str
    period_s: int
    stale_factor: float = 2.5
