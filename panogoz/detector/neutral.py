"""Nötr iletkeni için iki ayrı dedektör.

1. Yüklenme (`neutral_loading_scores`): nötr akımının 1 saatlik RMS'i / nötr anma
   akımı. 3. harmonik (ve tüm üçlü harmonikler) fazlarda birbirini götürmez,
   nötrde ARİTMETİK toplanır; nötr baranın kesiti fazdan küçük olduğundan
   dengeli bir yükte bile nötr aşırı yüklenebilir.

2. Bağlantı (`neutral_joint_scores`): K_N = dT / I^2 (CLAUDE.md §2). Nötr akımı
   hızlı değiştiği için ham dT/I^2 ısıl gecikmeyle sahte sıçramalar üretir
   (akım düşer, sıcaklık henüz düşmemiştir). Bu yüzden I^2, iletkenin ısıl
   modeliyle AYNI birinci derece süzgeçten geçirilir ve kurulumdan sonraki ilk
   `baseline_samples` örnekte
   T - LP(T_ortam) = k0 * LP(I^2) + b0 doğrusu en küçük kareler ile öğrenilir
   (b0 sensör ofsetini yakalar; ortam da aynı süzgeçten geçer, bkz. thermal_tau.py). Sonraki her örnek için artık (rezidü) hesaplanır ve
   K_efektif / k0 oranı puan olur.

   tau varsayılmaz, aynı taban çizgisinden tahmin edilir (thermal_tau.estimate_tau_s): tau'yu
   yanlış varsaymak regresörü gürültülü yapıp eğimi zayıflatır (ölçüldü: %17 hatalı
   tau, taban çizgisinin dışındaki yüksek akım rejiminde K_N oranında sistematik
   +%23 sapma verdi ve sahte UYARI üretti). Baz alınan sistem tanılama: tau,
   rezidü kareler ortalamasını en küçük yapan değerdir (logaritmik üçlü arama).

   Kısıt: taban çizgisi penceresinde zaten arızalı bir bağlantı "normal" öğrenilir
   (ilk kurulum sonrası ilk 14 günün sağlıklı olduğu varsayımı, cusum.py ile aynı).
"""
from __future__ import annotations

from panogoz.detector.common import (
    REASON_LOW_LOAD,
    REASON_STALE,
    REASON_WARMUP,
    Scored,
    gap_reasons,
    lowpass,
    rolling_rms,
)
from panogoz.detector.thermal_tau import estimate_tau_s, fit_baseline

LOADING_WINDOW_SAMPLES = 4
MIN_LOAD_FRACTION = 0.40
DEFAULT_BASELINE_SAMPLES = 14 * 96


def neutral_loading_scores(
    neutral_current_a: list[float], neutral_rated_a: float, valid: list[bool], *, window: int = LOADING_WINDOW_SAMPLES
) -> Scored:
    masked = [i if ok else None for i, ok in zip(neutral_current_a, valid)]
    rms = rolling_rms(masked, window)
    return Scored([None if r is None else r / neutral_rated_a for r in rms], gap_reasons(valid, window))


def neutral_joint_scores(
    neutral_temp_c: list[float],
    ambient_c: list[float],
    neutral_current_a: list[float],
    neutral_rated_a: float,
    valid: list[bool],
    *,
    period_s: float,
    tau_estimate_s: float | None = None,
    baseline_samples: int = DEFAULT_BASELINE_SAMPLES,
    min_load_fraction: float = MIN_LOAD_FRACTION,
) -> Scored:
    """`tau_estimate_s=None` ise tau taban çizgisinden tahmin edilir; bir sayı
    verilirse o değer sabit kullanılır (testler/duyarlılık analizi için)."""
    n = len(valid)
    current_sq = [i * i for i in neutral_current_a]
    gate = (min_load_fraction * neutral_rated_a) ** 2
    count = min(baseline_samples, n)

    tau = tau_estimate_s
    if tau is None:
        tau = estimate_tau_s([(neutral_temp_c, ambient_c, current_sq)], valid, gate, period_s, count)
    fit = (
        None
        if tau is None
        else fit_baseline(neutral_temp_c, ambient_c, current_sq, valid, gate, min(period_s / tau, 1.0), count)
    )
    if fit is None:
        return Scored([None] * n, [REASON_STALE if not ok else REASON_WARMUP for ok in valid])
    k0, b0, _, _ = fit
    alpha = min(period_s / tau, 1.0)
    lp = lowpass(current_sq, alpha)
    lp_ambient = lowpass(ambient_c, alpha)

    values: list[float | None] = []
    reasons: list[str | None] = []
    for i in range(n):
        if not valid[i]:
            values.append(None)
            reasons.append(REASON_STALE)
        elif i < baseline_samples:
            values.append(None)
            reasons.append(REASON_WARMUP)
        elif lp[i] < gate:
            values.append(None)
            reasons.append(REASON_LOW_LOAD)
        else:
            excess = (neutral_temp_c[i] - lp_ambient[i]) - (k0 * lp[i] + b0)
            values.append(1.0 + excess / (k0 * lp[i]))
            reasons.append(None)
    return Scored(values, reasons)
