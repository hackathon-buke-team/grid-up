"""Dedektörlerin ortak yapı taşları: puan (score) + bastırma gerekçesi, kayan pencere yardımcıları."""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass
from statistics import median
from typing import Sequence

REASON_STALE = "STALE"
REASON_DE_ENERGISED = "DE_ENERGISED"
REASON_LOW_LOAD = "LOW_LOAD"
REASON_WARMUP = "WARMUP"


@dataclass(frozen=True)
class Scored:
    """Bir dedektörün örnek başına çıktısı.

    `values[i]` None ise o örnek değerlendirilemedi; `reasons[i]` nedenini söyler
    (STALE: veri yok, DE_ENERGISED: enerjisiz, LOW_LOAD: normalize etmek için yük
    çok düşük, WARMUP: pencere/taban çizgisi henüz dolmadı). Nedeni olan örnek
    "bastırılmış" sayılır -- sessizce NORMAL yazılmaz, kanıt ekranı gösterebilsin diye.
    """

    values: list[float | None]
    reasons: list[str | None]


def rolling_rms(values: Sequence[float | None], window: int) -> list[float | None]:
    out: list[float | None] = []
    buf: deque[float | None] = deque()
    sum_sq = 0.0
    missing = 0
    for v in values:
        buf.append(v)
        if v is None:
            missing += 1
        else:
            sum_sq += v * v
        if len(buf) > window:
            old = buf.popleft()
            if old is None:
                missing -= 1
            else:
                sum_sq -= old * old
        out.append(None if len(buf) < window or missing else math.sqrt(max(sum_sq, 0.0) / window))
    return out


def rolling_median(values: Sequence[float | None], window: int) -> list[float | None]:
    out: list[float | None] = []
    buf: deque[float | None] = deque(maxlen=window)
    for v in values:
        buf.append(v)
        if len(buf) < window or any(x is None for x in buf):
            out.append(None)
        else:
            out.append(median(x for x in buf if x is not None))
    return out


def lowpass(values: Sequence[float], alpha: float) -> list[float]:
    """Birinci derece gecikme (ısıl model ile aynı biçim): y += alpha*(x - y)."""
    out: list[float] = []
    y: float | None = None
    for x in values:
        y = x if y is None else y + alpha * (x - y)
        out.append(y)
    return out


def gap_reasons(valid: Sequence[bool], window: int = 1) -> list[str | None]:
    """Geçersiz (haberleşme kaybı) örnekleri STALE olarak işaretler; ilk `window-1`
    örnek pencere dolmadığı için WARMUP'tır."""
    reasons: list[str | None] = []
    for i, ok in enumerate(valid):
        if not ok:
            reasons.append(REASON_STALE)
        elif i < window - 1:
            reasons.append(REASON_WARMUP)
        else:
            reasons.append(None)
    return reasons
