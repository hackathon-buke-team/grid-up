"""Şiddet akışını izleyip yalnızca yükseliş anında (edge-triggered) bildirim gönderir.

Her örnekte aynı şiddeti tekrar bildirmek spam olur; bu yüzden yalnızca önceki
en yüksek bildirilen şiddeti aşan geçişlerde mesaj gönderilir. Şiddet NORMAL'e
dönünce takip sıfırlanır, böylece bir sonraki yükseliş yeniden bildirilir.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from panogoz.rules.engine import Severity, SeverityEvent

SEVERITY_LABELS = {
    Severity.WARNING: "UYARI",
    Severity.ALARM: "ALARM",
    Severity.CRITICAL: "KRİTİK",
}


@dataclass
class AlarmNotifier:
    channel: object
    connection_id: str
    _last_notified: Severity = field(default=Severity.NORMAL, init=False)

    def process(self, event: SeverityEvent, theta: float | None = None) -> bool:
        if event.severity == Severity.NORMAL:
            self._last_notified = Severity.NORMAL
            return False
        if event.severity <= self._last_notified:
            return False
        label = SEVERITY_LABELS[event.severity]
        theta_part = f", θ={theta:.1f}" if theta is not None else ""
        self.channel.send(f"[{label}] {self.connection_id}{theta_part}")
        self._last_notified = event.severity
        return True
