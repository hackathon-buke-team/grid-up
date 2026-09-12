"""Eskalasyon merdiveni: rota, onay token'ı, tekrar aralığı, fırtına sınırı, sessize alma (K4 §4.2)."""
from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from enum import Enum


class AlarmState(str, Enum):
    OPEN = "OPEN"
    ACKED = "ACKED"
    CLOSED = "CLOSED"
    SNOOZED = "SNOOZED"


@dataclass
class Alarm:
    alarm_id: str
    connection_id: str
    severity: str
    families: set
    opened_at: float
    approval_token: str
    state: AlarmState = AlarmState.OPEN
    last_notified_at: float | None = None
    notify_count: int = 0
    acknowledged_by: str | None = None
    snoozed_until: float | None = None


REPEAT_INTERVAL_S = {"ALARM": 30 * 60, "CRITICAL": 15 * 60, "EMERGENCY": 5 * 60}
STORM_LIMIT_PER_HOUR = 5


def generate_approval_token() -> str:
    """Tahmin edilemeyen 4 haneli onay token'ı — kimliklendirilmiş onay için."""
    return f"{random.randint(0, 9999):04d}"


@dataclass
class EscalationLadder:
    channel: object
    notified_timestamps: list = field(default_factory=list)
    open_alarms: dict = field(default_factory=dict)
    storm_digest: list = field(default_factory=list)

    def _storm_active(self, now: float) -> bool:
        self.notified_timestamps = [t for t in self.notified_timestamps if now - t < 3600]
        return len(self.notified_timestamps) >= STORM_LIMIT_PER_HOUR

    def open_alarm(self, *, connection_id: str, severity: str, families: set, now: float | None = None) -> Alarm:
        now = time.time() if now is None else now
        alarm = Alarm(
            alarm_id=f"{connection_id}-{int(now * 1000)}",
            connection_id=connection_id,
            severity=severity,
            families=set(families),
            opened_at=now,
            approval_token=generate_approval_token(),
        )
        self.open_alarms[alarm.alarm_id] = alarm
        self._notify(alarm, now)
        return alarm

    def _notify(self, alarm: Alarm, now: float) -> bool:
        if self._storm_active(now):
            self.storm_digest.append(alarm.alarm_id)
            return False
        text = (
            f"[{alarm.severity}] {alarm.connection_id} - kanallar: {', '.join(sorted(alarm.families))}\n"
            f"Onay token'i: {alarm.approval_token}"
        )
        self.channel.send(text)
        alarm.last_notified_at = now
        alarm.notify_count += 1
        self.notified_timestamps.append(now)
        return True

    def tick(self, now: float | None = None) -> None:
        """Onaylanmamış açık alarmları tekrar aralığına göre yeniden bildirir."""
        now = time.time() if now is None else now
        for alarm in self.open_alarms.values():
            if alarm.state != AlarmState.OPEN:
                continue
            interval = REPEAT_INTERVAL_S.get(alarm.severity, 30 * 60)
            if alarm.last_notified_at is not None and now - alarm.last_notified_at >= interval:
                self._notify(alarm, now)

    def acknowledge(self, alarm_id: str, *, token: str, person: str) -> bool:
        alarm = self.open_alarms.get(alarm_id)
        if alarm is None or alarm.approval_token != token:
            return False
        alarm.state = AlarmState.ACKED
        alarm.acknowledged_by = person
        return True

    def snooze(self, alarm_id: str, *, until: float, person: str) -> bool:
        alarm = self.open_alarms.get(alarm_id)
        if alarm is None:
            return False
        alarm.state = AlarmState.SNOOZED
        alarm.snoozed_until = until
        alarm.acknowledged_by = person
        return True

    def close(self, alarm_id: str) -> bool:
        alarm = self.open_alarms.pop(alarm_id, None)
        if alarm is None:
            return False
        alarm.state = AlarmState.CLOSED
        return True

    def shift_handover_summary(self) -> str:
        lines = [f"Açık alarm sayısı: {len(self.open_alarms)}"]
        for alarm in self.open_alarms.values():
            lines.append(
                f"- {alarm.alarm_id} [{alarm.severity}] {alarm.state.value} "
                f"(bildirim: {alarm.notify_count}, onaylayan: {alarm.acknowledged_by or '-'})"
            )
        return "\n".join(lines)
