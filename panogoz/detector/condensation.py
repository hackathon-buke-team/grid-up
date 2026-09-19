"""Yoğuşma (çiy noktası) ve nem dedektörleri.

Yoğuşma, bir yüzeyin sıcaklığı komşu havanın çiy noktasının altına indiğinde
başlar. Kabinin en soğuk yüzeyi (kapı/yan sac) dış havayı izler; iç hava ise
yük nedeniyle daha sıcaktır. Bu yüzden risk, iç hava sıcaklığı+RH'tan
hesaplanan çiy noktası ile *duvar (soğuk nokta) sıcaklığı* arasındaki marjdır.

Puan = max(0, REF_MARGIN_K - marj): marj küçüldükçe artar, böylece eşik
mantığı (yüksek = kötü) diğer dedektörlerle aynıdır.
"""
from __future__ import annotations

import math

from panogoz.detector.common import Scored, gap_reasons, rolling_median

REF_MARGIN_K = 6.0
HUMIDITY_WINDOW_SAMPLES = 6  # 1,5 saatlik medyan


def dew_point_c(temp_c: float, rh_percent: float) -> float:
    """Magnus yaklaşımı (a=17,62; b=243,12 °C)."""
    a, b = 17.62, 243.12
    gamma = math.log(max(rh_percent, 1.0) / 100.0) + a * temp_c / (b + temp_c)
    return b * gamma / (a - gamma)


def dew_margin_c(air_temp_c: float, rh_percent: float, wall_temp_c: float) -> float:
    return wall_temp_c - dew_point_c(air_temp_c, rh_percent)


def condensation_scores(
    air_temp_c: list[float], humidity_rh: list[float], wall_temp_c: list[float], valid: list[bool]
) -> Scored:
    values: list[float | None] = []
    for ok, t, rh, w in zip(valid, air_temp_c, humidity_rh, wall_temp_c):
        values.append(max(0.0, REF_MARGIN_K - dew_margin_c(t, rh, w)) if ok else None)
    return Scored(values, gap_reasons(valid))


def humidity_scores(humidity_rh: list[float], valid: list[bool]) -> Scored:
    masked = [rh if ok else None for rh, ok in zip(humidity_rh, valid)]
    values = rolling_median(masked, HUMIDITY_WINDOW_SAMPLES)
    return Scored(values, gap_reasons(valid, HUMIDITY_WINDOW_SAMPLES))
