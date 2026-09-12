"""Bastırma katmanı: 3/5 günlük debounce, ölü bant, iki kanal ailesi şartı."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

DEBOUNCE_WINDOW = 5
DEBOUNCE_REQUIRED = 3
DEAD_BAND = 0.40
MIN_LOAD_RATIO_FOR_CORROBORATION = 0.05


@dataclass
class DebounceTracker:
    window: deque = field(default_factory=lambda: deque(maxlen=DEBOUNCE_WINDOW))

    def push(self, exceeded: bool) -> bool:
        self.window.append(exceeded)
        return sum(self.window) >= DEBOUNCE_REQUIRED


def still_active(value: float, threshold: float) -> bool:
    """Ölü bant: kapanmak için değer eşik * (1 - DEAD_BAND) altına inmeli."""
    return value > threshold * (1 - DEAD_BAND)


def current_family_corroborates(current_ratio_avg: float, flags: set[str]) -> bool:
    """İki kanal ailesi şartı: termal bulgu, devrenin gerçekten enerjili olduğunu doğrulayan akım ailesiyle desteklenmeli."""
    return current_ratio_avg > MIN_LOAD_RATIO_FOR_CORROBORATION and "DE_ENERGISED" not in flags
