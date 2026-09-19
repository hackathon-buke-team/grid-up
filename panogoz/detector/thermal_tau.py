"""Isıl zaman sabiti (tau) tahmini: kurulum taban çizgisinden sistem tanılama.

Birinci derece ısıl model: T' = (T_ortam + k I^2 - T)/tau. Çözümü
    T - LP_tau(T_ortam) = k * LP_tau(I^2) + b      (b = sensör ofseti)
Ortam sıcaklığı da iletkenle AYNI gecikmeyle süzülmelidir: ortamı anlık çıkarmak,
gün içi ortam salınımının (±6 K) gecikmesini sahte artık olarak bırakır (ölçüldü:
tau=7200 s'de ~3 K, K_N oranında yanlış alarm). tau bilinmeden LP kurulamaz; yanlış
tau regresörü gürültülü yapar (eğim zayıflar, geçici rejimler artık olarak kalır). Bu modül, taban çizgisi
penceresinde rezidü kareler ortalamasını (MSE) en küçük yapan tau'yu log-üçlü
aramayla bulur. Birden çok iletken (üç faz) AYNI kabinin ısıl kütlesini paylaşır
varsayımıyla ortak bir tau için MSE'leri toplanır.

Varsayım: taban çizgisi penceresi sağlıklıdır (cusum.py ve nötr K_N ile aynı).
"""
from __future__ import annotations

import math
from typing import Sequence

from panogoz.detector.common import lowpass

MIN_BASELINE_POINTS = 200
TAU_SEARCH_RANGE_S = (300.0, 14400.0)


def least_squares(xs: list[float], ys: list[float]) -> tuple[float, float]:
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx <= 0:
        raise ValueError("taban çizgisinde yük çeşitliliği yok, eğim tahmin edilemez")
    k = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    return k, my - k * mx


def fit_baseline(
    temp: list[float],
    ambient: list[float],
    current_sq: list[float],
    valid: list[bool],
    gate: float,
    alpha: float,
    count: int,
) -> tuple[float, float, float, int] | None:
    """(k, b, mse, nokta_sayısı) veya taban çizgisi yetersizse None."""
    lp = lowpass(current_sq[:count], alpha)
    lp_amb = lowpass(ambient[:count], alpha)
    pts = [(lp[i], temp[i] - lp_amb[i]) for i in range(count) if valid[i] and lp[i] >= gate]
    if len(pts) < MIN_BASELINE_POINTS:
        return None
    xs = [x for x, _ in pts]
    ys = [y for _, y in pts]
    try:
        k, b = least_squares(xs, ys)
    except ValueError:
        return None
    mse = sum((y - (k * x + b)) ** 2 for x, y in pts) / len(pts)
    return k, b, mse, len(pts)


def estimate_tau_s(
    series: Sequence[tuple[list[float], list[float], list[float]]],
    valid: list[bool],
    gate: float,
    period_s: float,
    count: int,
) -> float | None:
    """`series`: (sıcaklık, ortam, akım_karesi) üçlüleri. Ortak tau; başarısızsa None."""
    lo, hi = math.log(TAU_SEARCH_RANGE_S[0]), math.log(TAU_SEARCH_RANGE_S[1])

    def cost(log_tau: float) -> float:
        alpha = min(period_s / math.exp(log_tau), 1.0)
        total = 0.0
        for temp, ambient, current_sq in series:
            fit = fit_baseline(temp, ambient, current_sq, valid, gate, alpha, count)
            if fit is None:
                return math.inf
            total += fit[2]
        return total

    for _ in range(24):
        m1, m2 = lo + (hi - lo) / 3.0, hi - (hi - lo) / 3.0
        if cost(m1) < cost(m2):
            hi = m2
        else:
            lo = m1
    best = math.exp((lo + hi) / 2.0)
    return best if math.isfinite(cost(math.log(best))) else None
