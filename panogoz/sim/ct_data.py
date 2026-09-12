"""Gerçek CT verisine (İstenen Veriler.xlsx / Akım Sensörü) dayalı yük profili."""
from __future__ import annotations

import csv
import math
import os
from itertools import cycle

_DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "ct_l1_real.csv")
STEP_S = 900


def load_real_l1_profile() -> list[float]:
    """15 dk aralıklı gerçek L1 birincil akım serisi (A) - ~1.5 gün, 152 nokta."""
    values = []
    with open(_DATA_PATH, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            values.append(float(row["primer_A"]))
    return values


_REAL_PROFILE = load_real_l1_profile()
_REAL_PEAK_A = max(_REAL_PROFILE)


def real_profile_cycle(n_steps: int, scale: float = 1.0) -> list[float]:
    """Gerçek profili istenen adım sayısına döngüleyip ölçekler (0-1 arası yük oranı × scale)."""
    it = cycle(_REAL_PROFILE)
    return [(next(it) / _REAL_PEAK_A) * scale for _ in range(n_steps)]


def ambient_temp_c(step: int, *, base_c: float = 22.0, daily_swing_c: float = 8.0) -> float:
    hours = (step * STEP_S) / 3600.0
    return base_c + daily_swing_c * math.sin(2 * math.pi * (hours - 9) / 24.0)
