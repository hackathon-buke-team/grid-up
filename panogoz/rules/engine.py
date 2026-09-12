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


def evaluate_severity_series(theta_samples: list[ThetaSample]) -> list[SeverityEvent]:
    """Her örnek için debounce uygulanmış şiddeti döner."""
    raw = [_raw_severity(s.theta) for s in theta_samples]
    result: list[SeverityEvent] = []
    for i, sample in enumerate(theta_samples):
        window = raw[max(0, i - DEBOUNCE_WINDOW + 1) : i + 1]
        confirmed = Severity.NORMAL
        if len(window) >= DEBOUNCE_MIN_HITS:
            for severity in (Severity.CRITICAL, Severity.ALARM, Severity.WARNING):
                hits = sum(1 for s in window if s >= severity)
                if hits >= DEBOUNCE_MIN_HITS:
                    confirmed = severity
                    break
        result.append(SeverityEvent(t_s=sample.t_s, severity=confirmed))
    return result
