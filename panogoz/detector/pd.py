"""Kısmi deşarj (PD) dedektörü.

HFCT çıkışından türetilen PD indeksinin 1,5 saatlik medyanı. Medyan, anahtarlama
gürültüsünün tek örneklik patlamalarını (yalancı PD) bastırır. AG'de PD tek başına
ekip yönlendirmez -- bu yüzden kural motoru (panogoz/rules/pipeline.py) PD'yi
"tavsiye" işaretler ve ikinci bir kanal ailesi (ısı/nem) desteklemedikçe UYARI'da
tutar (füzyon).
"""
from __future__ import annotations

from panogoz.detector.common import Scored, gap_reasons, rolling_median

PD_WINDOW_SAMPLES = 6


def pd_scores(pd_index: list[float], valid: list[bool]) -> Scored:
    masked = [v if ok else None for v, ok in zip(pd_index, valid)]
    return Scored(rolling_median(masked, PD_WINDOW_SAMPLES), gap_reasons(valid, PD_WINDOW_SAMPLES))
