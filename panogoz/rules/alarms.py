"""Alarm yaşam döngüsü: aç -> yükselt -> temizlen -> onayla -> kapat (CLAUDE.md §2 "alarm").

`pipeline.py` her iz için örnek başına *füzyon sonrası* şiddet üretir; bu motor o
şiddetleri kalıcı, onaylanabilir alarm kayıtlarına çevirir:

- UYARI ve üstü bir alarm AÇAR (konsolda görünür); yalnız ALARM ve üstü bildirim
  gerektirir (bkz. panogoz/notify/escalation.py).
- Şiddet artarsa aynı alarm YÜKSELİR ve önceki onayı geçersiz kılar (daha kötü bir
  duruma verilmiş onay eski durum için verilmişti).
- İz normale dönünce ALARM+ bir alarm TEMİZLENİR ama otomatik kapanmaz: biri onaylayana
  kadar "onay bekliyor" kalır; onay gelirse anında, gelmezse 7 gün sonra KAPANIR
  ("kendiliğinden kapanma"). Hiç ALARM'a çıkmamış (yalnız UYARI) kayıt kimseye sevk
  edilmediğinden normale dönünce onay beklemeden kapanır.
- Olay tipi (latching) alarmlar (ark TRIP) sinyal dönse de temizlenmez; onayla kapanır.
- Bir izin temizlendikten `reopen_within_s` içinde yeniden yükselmesi yeni alarm
  değil aynı alarmın yeniden açılmasıdır (sınırda gezinme = flapping tek kayıt).
- Onay **kimliklendirilmiş**dir: 4 haneli belirteç bildirimle birlikte gider; belirteç
  ve isim olmadan onay reddedilir. Kapatma gerekçesiz reddedilir.
- SESSİZE ALMA yalnız KRİTİK-altı alarmları bastırır; KRİTİK her zaman geçer.

Zaman motora `t_s` olarak DIŞARIDAN verilir (simülasyon saati veya duvar saati);
motor hiç saate bakmaz, bu yüzden deterministik ve test edilebilirdir.
"""
from __future__ import annotations

import hmac
import random
from dataclasses import dataclass, field
from enum import Enum

from panogoz.contracts.channels import Phase
from panogoz.rules.engine import Severity
from panogoz.rules.pipeline import Analysis, Family, TrackSpec

DAY_S = 86400.0
AUTO_CLOSE_S = 7 * DAY_S
REOPEN_WITHIN_S = 6 * 3600.0

# Aynı kök nedeni anlatan daha zayıf bir iz, güçlüsü açılınca ona birleştirilir
# (θ alarmı açılınca aynı fazın CUSUM "trend" uyarısı ayrı kayıt olarak kalmaz).
SUPERSEDES = {"loose_bolt": "loose_bolt_trend"}

CLOSE_REASONS = (
    "sahada_giderildi",
    "yanlis_alarm",
    "planli_bakim",
    "bilinen_sorun_izleniyor",
    "diger",
)


class AlarmState(str, Enum):
    OPEN = "open"  # aktif ve onay bekliyor
    ACKED = "acked"  # aktif, onaylandı, ekip ilgileniyor
    CLEARED = "cleared"  # sinyal normale döndü, onay bekliyor
    CLOSED = "closed"


class AckError(ValueError):
    pass


@dataclass
class TrackNow:
    """Bir izin bu andaki durumu (motorun girdisi)."""

    spec: TrackSpec
    phase: Phase | None
    severity: Severity
    score: float | None = None
    reason: str | None = None
    capped: bool = False

    @property
    def key(self) -> str:
        return f"{self.spec.kind}:{self.phase.value}" if self.phase else self.spec.kind


@dataclass
class Alarm:
    id: str
    connection_id: str
    track_key: str
    kind: str
    family: str
    phase: str | None
    label: str
    latching: bool
    opened_t_s: float
    severity: Severity
    peak: Severity
    state: AlarmState
    ack_token: str
    peak_score: float | None = None
    acked_severity: Severity | None = None
    acked_by: str | None = None
    acked_t_s: float | None = None
    ack_note: str | None = None
    cleared_t_s: float | None = None
    closed_t_s: float | None = None
    close_reason: str | None = None
    closed_by: str | None = None
    flaps: int = 0
    history: list[tuple[float, str, str]] = field(default_factory=list)

    @property
    def is_active(self) -> bool:
        return self.state in (AlarmState.OPEN, AlarmState.ACKED)

    @property
    def needs_notification(self) -> bool:
        """ALARM+ ve süreç alarmı. Sistem alarmları (cihaz susuyor) bakım biletidir,
        nöbetçiyi aramaz; konsolda ve KPI'da görünür."""
        return self.severity >= Severity.ALARM and self.family != "system"

    def to_dict(self, *, include_token: bool = False) -> dict:
        data = {
            "id": self.id,
            "connection_id": self.connection_id,
            "track_key": self.track_key,
            "kind": self.kind,
            "family": self.family,
            "phase": self.phase,
            "label": self.label,
            "latching": self.latching,
            "opened_t_s": self.opened_t_s,
            "severity": self.severity.name,
            "peak": self.peak.name,
            "state": self.state.value,
            "peak_score": self.peak_score,
            "acked_by": self.acked_by,
            "acked_t_s": self.acked_t_s,
            "ack_note": self.ack_note,
            "cleared_t_s": self.cleared_t_s,
            "closed_t_s": self.closed_t_s,
            "close_reason": self.close_reason,
            "closed_by": self.closed_by,
            "flaps": self.flaps,
            "history": [{"t_s": t, "event": e, "detail": d} for t, e, d in self.history],
        }
        if include_token:
            data["ack_token"] = self.ack_token
        return data


class EventType(str, Enum):
    OPENED = "opened"
    REOPENED = "reopened"
    ESCALATED = "escalated"
    DEESCALATED = "deescalated"
    CLEARED = "cleared"
    ACKED = "acked"
    CLOSED = "closed"
    MUTED = "muted"  # sessize alma nedeniyle açılmayan/yükseltilmeyen


@dataclass(frozen=True)
class AlarmEvent:
    t_s: float
    type: EventType
    alarm_id: str
    severity: Severity
    detail: str = ""


@dataclass
class Mute:
    scope: str  # bir iz anahtarı ("loose_bolt:L2") veya tür ("condensation")
    until_t_s: float
    by: str
    reason: str

    def covers(self, track_key: str, kind: str, t_s: float) -> bool:
        return t_s < self.until_t_s and self.scope in (track_key, kind)


class AlarmEngine:
    """Tek bir bağlantının alarm kayıtlarını yönetir."""

    def __init__(
        self,
        connection_id: str,
        *,
        id_prefix: str | None = None,
        auto_close_s: float = AUTO_CLOSE_S,
        reopen_within_s: float = REOPEN_WITHIN_S,
        seed: int = 0,
    ) -> None:
        self.connection_id = connection_id
        self.id_prefix = id_prefix or connection_id
        self.auto_close_s = auto_close_s
        self.reopen_within_s = reopen_within_s
        self._seed = seed
        self.alarms: dict[str, Alarm] = {}
        self.events: list[AlarmEvent] = []
        self.mutes: list[Mute] = []
        self.suppressed: list[AlarmEvent] = []
        self._seq = 0
        self._by_track: dict[str, str] = {}  # iz -> son alarm id

    # ------------------------------------------------------------ sessize alma
    def mute(self, scope: str, *, until_t_s: float, by: str, reason: str) -> Mute:
        if not by.strip() or not reason.strip():
            raise ValueError("sessize alma için kişi ve gerekçe zorunlu")
        m = Mute(scope, until_t_s, by.strip(), reason.strip())
        self.mutes.append(m)
        return m

    def _muted(self, track_key: str, kind: str, t_s: float) -> Mute | None:
        return next((m for m in self.mutes if m.covers(track_key, kind, t_s)), None)

    # ------------------------------------------------------------------ adım
    def step(self, t_s: float, tracks: dict[str, TrackNow] | list[TrackNow]) -> list[AlarmEvent]:
        now = list(tracks.values()) if isinstance(tracks, dict) else tracks
        out: list[AlarmEvent] = []
        for tn in now:
            out.extend(self._step_track(t_s, tn))
        out.extend(self._auto_close(t_s))
        self.events.extend(out)
        return out

    def _new_alarm(self, t_s: float, tn: TrackNow) -> Alarm:
        self._seq += 1
        alarm_id = f"{self.id_prefix}-{self._seq:04d}"
        token = f"{random.Random(f'{self._seed}:{alarm_id}').randrange(10000):04d}"
        alarm = Alarm(
            id=alarm_id,
            connection_id=self.connection_id,
            track_key=tn.key,
            kind=tn.spec.kind,
            family=tn.spec.family.value,
            phase=tn.phase.value if tn.phase else None,
            label=tn.spec.label,
            latching=tn.spec.latching,
            opened_t_s=t_s,
            severity=tn.severity,
            peak=tn.severity,
            state=AlarmState.OPEN,
            ack_token=token,
            peak_score=tn.score,
        )
        self.alarms[alarm_id] = alarm
        self._by_track[tn.key] = alarm_id
        return alarm

    def _step_track(self, t_s: float, tn: TrackNow) -> list[AlarmEvent]:
        out: list[AlarmEvent] = []
        alarm = self.alarms.get(self._by_track.get(tn.key, ""))
        if alarm is not None and alarm.state is AlarmState.CLOSED:
            alarm = None
        sev = tn.severity

        if alarm is not None and tn.score is not None and (alarm.peak_score is None or tn.score > alarm.peak_score):
            alarm.peak_score = tn.score

        # -- yeni açılış / yeniden açılış
        if alarm is None or alarm.state is AlarmState.CLEARED:
            if sev < Severity.WARNING:
                return out
            mute = self._muted(tn.key, tn.spec.kind, t_s)
            if mute is not None and sev < Severity.CRITICAL:
                ev = AlarmEvent(t_s, EventType.MUTED, alarm.id if alarm else f"{self.id_prefix}-muted", sev, f"{mute.by}: {mute.reason}")
                self.suppressed.append(ev)
                return out
            if alarm is not None and alarm.cleared_t_s is not None and t_s - alarm.cleared_t_s <= self.reopen_within_s:
                alarm.state = AlarmState.OPEN if alarm.acked_t_s is None else AlarmState.ACKED
                alarm.cleared_t_s = None
                alarm.flaps += 1
                alarm.severity = sev
                alarm.peak = max(alarm.peak, sev)
                alarm.history.append((t_s, EventType.REOPENED.value, sev.name))
                out.append(AlarmEvent(t_s, EventType.REOPENED, alarm.id, sev))
                return out
            alarm = self._new_alarm(t_s, tn)
            alarm.history.append((t_s, EventType.OPENED.value, sev.name))
            out.append(AlarmEvent(t_s, EventType.OPENED, alarm.id, sev))
            out.extend(self._absorb_weaker(alarm, tn, t_s))
            return out

        # -- aktif alarm (OPEN / ACKED)
        if sev > alarm.severity:
            alarm.severity = sev
            alarm.peak = max(alarm.peak, sev)
            if alarm.state is AlarmState.ACKED and (alarm.acked_severity is None or sev > alarm.acked_severity):
                alarm.state = AlarmState.OPEN  # daha kötü durum: eski onay geçersiz
                alarm.history.append((t_s, "ack_invalidated", sev.name))
            alarm.history.append((t_s, EventType.ESCALATED.value, sev.name))
            out.append(AlarmEvent(t_s, EventType.ESCALATED, alarm.id, sev))
        elif Severity.WARNING <= sev < alarm.severity:
            alarm.severity = sev
            alarm.history.append((t_s, EventType.DEESCALATED.value, sev.name))
            out.append(AlarmEvent(t_s, EventType.DEESCALATED, alarm.id, sev))
        elif sev < Severity.WARNING and not alarm.latching:
            if alarm.state is AlarmState.ACKED:
                self._close(alarm, t_s, "sahada_giderildi", "sistem (onaylı alarm normale döndü)")
                out.append(AlarmEvent(t_s, EventType.CLOSED, alarm.id, alarm.severity, "cleared_after_ack"))
            elif alarm.peak < Severity.ALARM:
                # UYARI seviyesinde kalmış alarm kimseye sevk edilmedi: onay beklemeden kapanır
                self._close(alarm, t_s, "diger", "sistem (uyarı normale döndü)")
                out.append(AlarmEvent(t_s, EventType.CLOSED, alarm.id, alarm.severity, "warning_cleared"))
            else:
                alarm.state = AlarmState.CLEARED
                alarm.cleared_t_s = t_s
                alarm.history.append((t_s, EventType.CLEARED.value, ""))
                out.append(AlarmEvent(t_s, EventType.CLEARED, alarm.id, alarm.severity))
        return out

    def _absorb_weaker(self, new: Alarm, tn: TrackNow, t_s: float) -> list[AlarmEvent]:
        weaker_kind = SUPERSEDES.get(tn.spec.kind)
        if weaker_kind is None:
            return []
        weaker_key = f"{weaker_kind}:{tn.phase.value}" if tn.phase else weaker_kind
        old = self.alarms.get(self._by_track.get(weaker_key, ""))
        if old is None or old.state is AlarmState.CLOSED:
            return []
        self._close(old, t_s, "diger", f"sistem (birleştirildi: {new.id})")
        return [AlarmEvent(t_s, EventType.CLOSED, old.id, old.severity, f"merged_into:{new.id}")]

    def _auto_close(self, t_s: float) -> list[AlarmEvent]:
        out = []
        for alarm in self.alarms.values():
            if alarm.state is AlarmState.CLEARED and alarm.cleared_t_s is not None and t_s - alarm.cleared_t_s >= self.auto_close_s:
                self._close(alarm, t_s, "diger", "sistem (7 gün onaylanmadı, kendiliğinden kapandı)")
                out.append(AlarmEvent(t_s, EventType.CLOSED, alarm.id, alarm.severity, "auto_7d"))
        return out

    def _close(self, alarm: Alarm, t_s: float, reason: str, by: str) -> None:
        alarm.state = AlarmState.CLOSED
        alarm.closed_t_s = t_s
        alarm.close_reason = reason
        alarm.closed_by = by
        alarm.history.append((t_s, EventType.CLOSED.value, reason))

    # -------------------------------------------------------------- operatör
    def ack(self, alarm_id: str, token: str, by: str, t_s: float, note: str = "") -> Alarm:
        alarm = self._get(alarm_id)
        if not by or not by.strip():
            raise AckError("onay için kimlik (isim) zorunlu")
        if not hmac.compare_digest(str(token).strip(), alarm.ack_token):
            raise AckError("onay belirteci hatalı")
        if alarm.state is AlarmState.CLOSED:
            raise AckError("alarm zaten kapalı")
        if alarm.state is AlarmState.ACKED:
            raise AckError("alarm zaten onaylı")
        alarm.acked_by, alarm.acked_t_s, alarm.ack_note = by.strip(), t_s, note or None
        alarm.acked_severity = alarm.severity
        alarm.history.append((t_s, EventType.ACKED.value, by.strip()))
        if alarm.state is AlarmState.CLEARED or (alarm.latching and alarm.severity >= Severity.WARNING and self._signal_gone(alarm)):
            self._close(alarm, t_s, "sahada_giderildi", by.strip())
        else:
            alarm.state = AlarmState.ACKED
        self.events.append(AlarmEvent(t_s, EventType.ACKED, alarm.id, alarm.severity, by.strip()))
        return alarm

    def _signal_gone(self, alarm: Alarm) -> bool:
        return alarm.latching  # olay tipi: sinyal darbeydi, onay = kapanış

    def close(self, alarm_id: str, reason: str, by: str, t_s: float) -> Alarm:
        alarm = self._get(alarm_id)
        if reason not in CLOSE_REASONS:
            raise ValueError(f"kapatma gerekçesi geçersiz: {reason!r} (geçerli: {', '.join(CLOSE_REASONS)})")
        if not by or not by.strip():
            raise ValueError("kapatma için kimlik zorunlu")
        if alarm.state is AlarmState.CLOSED:
            raise ValueError("alarm zaten kapalı")
        self._close(alarm, t_s, reason, by.strip())
        self.events.append(AlarmEvent(t_s, EventType.CLOSED, alarm.id, alarm.severity, f"manual:{reason}"))
        return alarm

    def _get(self, alarm_id: str) -> Alarm:
        try:
            return self.alarms[alarm_id]
        except KeyError:
            raise KeyError(f"alarm bulunamadı: {alarm_id}") from None


def tracks_now(analysis: Analysis, i: int) -> list[TrackNow]:
    return [
        TrackNow(tr.spec, tr.phase, tr.fused[i], tr.scores[i], tr.reasons[i], tr.capped[i])
        for tr in analysis.tracks
    ]


def build_alarm_log(
    connection_id: str, analysis: Analysis, *, id_prefix: str | None = None, until_t_s: float | None = None, seed: int = 0
) -> AlarmEngine:
    """Tüm analizi baştan sona motordan geçirir (`until_t_s` verilirse o ana kadar)."""
    engine = AlarmEngine(connection_id, id_prefix=id_prefix, seed=seed)
    for i, t in enumerate(analysis.data.t_s):
        if until_t_s is not None and t > until_t_s:
            break
        engine.step(t, tracks_now(analysis, i))
    return engine


PROCESS_FAMILIES = frozenset(f.value for f in Family if f is not Family.SYSTEM)
