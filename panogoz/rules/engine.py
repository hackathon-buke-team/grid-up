"""θ serisinden alarm şiddeti üreten kural motoru: eşik + debounce.

Tek örneklik bir gürültü sıçraması alarm üretmemeli — bu yüzden şiddet, son
DEBOUNCE_WINDOW örnekten en az DEBOUNCE_MIN_HITS'inin eşiği aşmasını şart
koşan klasik "M/N" alarm hijyeni deseniyle onaylanır.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from panogoz.detector.theta import ThetaSample


class Severity(IntEnum):
    NORMAL = 0
    WARNING = 1
    ALARM = 2
    CRITICAL = 3


THETA_THRESHOLDS = {
    Severity.WARNING: 15.0,
    Severity.ALARM: 30.0,
    Severity.CRITICAL: 60.0,
}

DEBOUNCE_WINDOW = 5
DEBOUNCE_MIN_HITS = 3


def _raw_severity(theta: float | None) -> Severity:
    if theta is None:
        return Severity.NORMAL
    magnitude = abs(theta)
    if magnitude >= THETA_THRESHOLDS[Severity.CRITICAL]:
        return Severity.CRITICAL
    if magnitude >= THETA_THRESHOLDS[Severity.ALARM]:
        return Severity.ALARM
    if magnitude >= THETA_THRESHOLDS[Severity.WARNING]:
        return Severity.WARNING
    return Severity.NORMAL


@dataclass(frozen=True)
class SeverityEvent:
    t_s: float
    severity: Severity


DEADBAND_FRACTION = 0.40  # CLAUDE.md §2: %40 ölü bant

_LEVELS_DESC = (Severity.CRITICAL, Severity.ALARM, Severity.WARNING)


def debounce_severity(
    raw: list[Severity], *, window: int = DEBOUNCE_WINDOW, min_hits: int = DEBOUNCE_MIN_HITS
) -> list[Severity]:
    """Klasik M/N onayı: son `window` örnekte en az `min_hits` kez bir seviyeye
    (veya üstüne) ulaşılmadıysa o seviye onaylanmaz."""
    confirmed_series: list[Severity] = []
    for i in range(len(raw)):
        recent = raw[max(0, i - window + 1) : i + 1]
        confirmed = Severity.NORMAL
        if len(recent) >= min_hits:
            for severity in _LEVELS_DESC:
                if sum(1 for s in recent if s >= severity) >= min_hits:
                    confirmed = severity
                    break
        confirmed_series.append(confirmed)
    return confirmed_series


def severity_with_deadband(
    scores: list[float | None],
    thresholds: dict[Severity, float],
    *,
    deadband: float = DEADBAND_FRACTION,
) -> list[Severity]:
    """Histerezisli ham şiddet: bir seviyeye eşiği aşınca girilir, ancak puan o
    seviyenin eşiğinin `(1 - deadband)` katının altına inince çıkılır. Sınırda
    dolaşan bir puanın alarmı açıp kapatıp durmasını (flapping) önler.
    Puan None (bastırılmış örnek: düşük yük, veri yok, enerjisiz) ise durum TUTULUR:
    "bilgi yok" "normal" demek değildir. Aksi halde yalnız yüksek yükte görünen bir
    arıza (düşük-yük senaryosu) her gece maskelenince "temizlenir", her gün yeniden
    açılır ve tek arıza için onlarca alarm/bildirim üretir (ölçüldü: 6,4 günde 179
    mesaj). Durum, ilk geçerli örnekte güncellenir."""
    state = Severity.NORMAL
    result: list[Severity] = []
    for score in scores:
        if score is None:
            result.append(state)
            continue
        entry = Severity.NORMAL
        hold = Severity.NORMAL
        for level in _LEVELS_DESC:
            if entry == Severity.NORMAL and score >= thresholds[level]:
                entry = level
            if hold == Severity.NORMAL and level <= state and score >= thresholds[level] * (1.0 - deadband):
                hold = level
        state = max(entry, hold)
        result.append(state)
    return result


def evaluate_severity_series(theta_samples: list[ThetaSample]) -> list[SeverityEvent]:
    """Her örnek için debounce uygulanmış şiddeti döner."""
    raw = [_raw_severity(s.theta) for s in theta_samples]
    confirmed = debounce_severity(raw)
    return [SeverityEvent(t_s=sample.t_s, severity=sev) for sample, sev in zip(theta_samples, confirmed)]
