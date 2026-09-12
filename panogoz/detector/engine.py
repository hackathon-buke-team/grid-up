"""theta/RLS/CUSUM dedektör çekirdeği ve expect_flags hesaplaması (K4 §4.3)."""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass

CRITICAL_TEMP_C = 110.0
EMERGENCY_TEMP_C = 130.0


def theta_raw(t_channel: float, t_siblings: list[float], nominal_current_a: float) -> float:
    """theta = (kanal - kardeş medyanı) / anma akımı."""
    if not t_siblings or nominal_current_a <= 0:
        return 0.0
    return (t_channel - statistics.median(t_siblings)) / nominal_current_a


@dataclass
class ThermalRLS:
    """theta_raw'ı ΔI² üzerine çevrimiçi regresyona sokup yük-bağımsız kalıntıyı çıkarır."""

    forgetting: float = 0.98
    p: float = 1e4
    a: float = 0.0

    def update(self, theta: float, delta_i_sq: float) -> float:
        denom = self.forgetting + delta_i_sq * self.p * delta_i_sq
        gain = (self.p * delta_i_sq) / denom if denom else 0.0
        error = theta - self.a * delta_i_sq
        self.a = self.a + gain * error
        self.p = (self.p - gain * delta_i_sq * self.p) / self.forgetting
        return error


@dataclass
class CusumDetector:
    """Günlük medyanlar üzerinde CUSUM değişim noktası tespiti."""

    k: float = 0.5
    h: float = 5.0
    baseline: float | None = None
    s_pos: float = 0.0
    s_neg: float = 0.0
    changepoint_day: int | None = None
    _day_idx: int = 0

    def update_daily(self, daily_median: float) -> bool:
        if self.baseline is None:
            self.baseline = daily_median
            self._day_idx += 1
            return False
        deviation = daily_median - self.baseline
        self.s_pos = max(0.0, self.s_pos + deviation - self.k)
        self.s_neg = min(0.0, self.s_neg + deviation + self.k)
        triggered = self.s_pos > self.h or abs(self.s_neg) > self.h
        if triggered and self.changepoint_day is None:
            self.changepoint_day = self._day_idx
        self._day_idx += 1
        return triggered


def neutral_k(delta_t_neutral: float, i_neutral: float) -> float:
    """K_N = ΔT/I² — nötr harmonik yüklenmeyi gevşek nötr bağlantısından ayırır."""
    if i_neutral <= 0:
        return 0.0
    return delta_t_neutral / (i_neutral ** 2)


def dew_point_c(t_air_c: float, rh_pct: float) -> float:
    a, b = 17.62, 243.12
    gamma = (a * t_air_c) / (b + t_air_c) + math.log(max(rh_pct, 1e-3) / 100.0)
    return (b * gamma) / (a - gamma)


def condensation_margin_c(t_wall_c: float, t_air_c: float, rh_pct: float) -> float:
    """Duvar sıcaklığı - çiy noktası; negatifse yoğuşma riski var."""
    return t_wall_c - dew_point_c(t_air_c, rh_pct)


def absolute_severity(temp_c: float) -> str | None:
    if temp_c >= EMERGENCY_TEMP_C:
        return "EMERGENCY"
    if temp_c >= CRITICAL_TEMP_C:
        return "CRITICAL"
    return None


def compute_expect_flags(
    *,
    now_ts: float,
    last_ts: float | None,
    period_s: int,
    current_a: float | None,
    drift_score: float | None,
    stale_factor: float = 2.5,
    drift_threshold: float = 3.0,
    de_energised_current_a: float = 2.0,
) -> set[str]:
    """Cihaz düzeyinde ilan edilmesi gereken üç bayrak: STALE, DE_ENERGISED, SENSOR_DRIFT."""
    flags: set[str] = set()
    if last_ts is None or (now_ts - last_ts) > period_s * stale_factor:
        flags.add("STALE")
    if current_a is not None and current_a < de_energised_current_a:
        flags.add("DE_ENERGISED")
    if drift_score is not None and abs(drift_score) > drift_threshold:
        flags.add("SENSOR_DRIFT")
    return flags
