"""Aşırı yük dedektörü: en yüklü fazın 1 saatlik RMS akımı / anma akımı.

Anlık tepe değil kayan RMS kullanılır: bağlantının ısınması akımın karesinin
zaman ortalamasıyla (I^2 x tau) belirlenir; gerçek CT serisindeki kısa
sıçramalar (90 A -> 540 A) tek başına arıza değildir. Eşikler
panogoz/rules/pipeline.py'de tanımlıdır.
"""
from __future__ import annotations

from panogoz.contracts.channels import Phase
from panogoz.detector.common import REASON_WARMUP, Scored, gap_reasons, rolling_rms

WINDOW_SAMPLES = 4  # 4 x 15 dk = 1 saat


def overload_scores(
    current_a: dict[Phase, list[float]],
    rated_current_a: float,
    valid: list[bool],
    *,
    window: int = WINDOW_SAMPLES,
) -> Scored:
    n = len(valid)
    peak = [max(current_a[p][i] for p in Phase) if valid[i] else None for i in range(n)]
    rms = rolling_rms(peak, window)
    values = [None if r is None else r / rated_current_a for r in rms]
    reasons = gap_reasons(valid, window)
    for i, v in enumerate(values):
        if v is None and reasons[i] is None:
            reasons[i] = REASON_WARMUP
    return Scored(values, reasons)
