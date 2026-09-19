"""Bildirim eskalasyonu: rota, onay belirteci, tekrar aralığı, fırtına sınırı, sessize alma, nöbet devri.

`panogoz/rules/alarms.py` alarm olaylarını üretir; bu modül onları insanlara ulaştırır
ve ulaştığından emin olur. Tasarım ilkeleri:

- **Rota şiddete göre:** UYARI yalnız konsolda (bildirim yok); ALARM birinci kademeye
  (saha nöbetçisi); KRİTİK aynı anda ilk iki kademeye. Onaylanmayan ALARM/KRİTİK,
  `ack_timeout` sonra bir üst kademeye YÜKSELİR.
- **Onay belirteci:** her mesaj `ONAY <alarm> <4 haneli belirteç>` talimatı taşır;
  belirteçsiz veya kimliksiz onay alarm motorunda reddedilir.
- **Tekrar aralığı:** onaylanana kadar `repeat` aralığıyla hatırlatma (üst sınırlı).
- **Fırtına sınırı:** alıcı başına saatte en fazla `rate_limit_per_hour` mesaj; fazlası
  tek bir "N bildirim bastırıldı" özetine dönüşür. KRİTİK ilk bildirimler sınırı aşar.
- **Sessize alma:** kişi bazlı; KRİTİK alarm sessizdeki kişiyi de arar. Sessizdeki
  kişi atlanır, kademe boş kalırsa bir üst kademeye geçilir.
- **Nöbet devri:** vardiya takvimi + açık devir kaydı; alarm sürerken nöbet değişirse
  hatırlatma YENİ nöbetçiye "NÖBET DEVRİ" öneki ve devir notuyla gider.
- **Teslimat hatası sessiz yutulmaz:** bir kanal hata verirse mesaj "başarısız" kaydedilir
  ve aynı anda bir üst kademe aranır.

Mesaj yalnız bağlantı kimliği, şiddet, alarm türü ve puanı taşır -- ham sensör verisi
üçüncü tarafa (Telegram/SMS operatörü) gitmez (docs/12-BILDIRIM-ESKALASYON.md §3).

Zaman dışarıdan verilir (`t_s`), motor saate bakmaz: simülasyon ve testte deterministik.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Iterable, Protocol

from panogoz.rules.alarms import Alarm, AlarmEvent, AlarmState, EventType
from panogoz.rules.engine import Severity
from panogoz.rules.pipeline import SPECS

HOUR_S = 3600.0
DAY_S = 86400.0

SEVERITY_LABELS = {Severity.WARNING: "UYARI", Severity.ALARM: "ALARM", Severity.CRITICAL: "KRİTİK"}
_ACK_RE = re.compile(r"^\s*/?onay\s+(\S+)\s+(\d{4})\s*$", re.IGNORECASE)


@dataclass(frozen=True)
class Recipient:
    name: str
    role: str
    route: str  # "telegram" | "sms" | "console"
    address: str  # chat_id / telefon; günlüğe maskeli yazılır


@dataclass(frozen=True)
class Shift:
    start_hour: float
    end_hour: float  # start > end ise gece yarısını aşar (ör. 20 -> 08)
    tiers: tuple[tuple[Recipient, ...], ...]

    def covers(self, hour: float) -> bool:
        if self.start_hour <= self.end_hour:
            return self.start_hour <= hour < self.end_hour
        return hour >= self.start_hour or hour < self.end_hour


@dataclass(frozen=True)
class Handover:
    at_t_s: float
    tiers: tuple[tuple[Recipient, ...], ...]
    note: str


class OnCallSchedule:
    """Vardiya takvimi + açık devirler. `t_s` saniye; yerel saat = (t_s + tz_offset_s) mod 24 sa."""

    def __init__(self, shifts: list[Shift], *, tz_offset_s: float = 0.0) -> None:
        if not shifts:
            raise ValueError("en az bir vardiya gerekli")
        self.shifts = shifts
        self.tz_offset_s = tz_offset_s
        self.handovers: list[Handover] = []

    def handover(self, at_t_s: float, tiers: tuple[tuple[Recipient, ...], ...], note: str) -> Handover:
        h = Handover(at_t_s, tiers, note)
        self.handovers.append(h)
        self.handovers.sort(key=lambda x: x.at_t_s)
        return h

    def _shift(self, t_s: float) -> Shift:
        hour = ((t_s + self.tz_offset_s) % DAY_S) / HOUR_S
        for shift in self.shifts:
            if shift.covers(hour):
                return shift
        return self.shifts[0]

    def tiers_at(self, t_s: float) -> tuple[tuple[Recipient, ...], ...]:
        override = None
        for h in self.handovers:
            if h.at_t_s <= t_s:
                override = h
        return override.tiers if override else self._shift(t_s).tiers

    def handover_note(self, t_s: float) -> str | None:
        note = None
        for h in self.handovers:
            if h.at_t_s <= t_s:
                note = h.note
        return note


@dataclass(frozen=True)
class EscalationPolicy:
    ack_timeout_s: dict[Severity, float] = field(default_factory=lambda: {Severity.ALARM: 30 * 60.0, Severity.CRITICAL: 10 * 60.0})
    repeat_s: dict[Severity, float] = field(default_factory=lambda: {Severity.ALARM: 15 * 60.0, Severity.CRITICAL: 5 * 60.0})
    initial_tiers: dict[Severity, int] = field(default_factory=lambda: {Severity.ALARM: 1, Severity.CRITICAL: 2})
    max_repeats: int = 6
    rate_limit_per_hour: int = 6


class Dispatcher(Protocol):
    def deliver(self, recipient: Recipient, text: str) -> None: ...


class ConsoleDispatcher:
    """Test/demo: mesajları belleğe yazar."""

    def __init__(self) -> None:
        self.delivered: list[tuple[Recipient, str]] = []
        self.fail_for: set[str] = set()  # adı burada olan alıcıya teslimat başarısız olur (test)

    def deliver(self, recipient: Recipient, text: str) -> None:
        if recipient.name in self.fail_for:
            raise ConnectionError("kanal erişilemiyor")
        self.delivered.append((recipient, text))


class RoutedDispatcher:
    """`route` alanına göre alt dispatcher/kanal seçer."""

    def __init__(self, routes: dict[str, Callable[[Recipient, str], None]]) -> None:
        self.routes = routes

    def deliver(self, recipient: Recipient, text: str) -> None:
        try:
            handler = self.routes[recipient.route]
        except KeyError:
            raise ValueError(f"bilinmeyen rota: {recipient.route}") from None
        handler(recipient, text)


def telegram_route(bot_token: str) -> Callable[[Recipient, str], None]:
    from panogoz.notify.telegram_channel import TelegramChannel

    def send(recipient: Recipient, text: str) -> None:
        TelegramChannel(bot_token=bot_token, chat_id=recipient.address).send(text)

    return send


@dataclass(frozen=True)
class SentMessage:
    t_s: float
    alarm_id: str
    recipient: str
    role: str
    route: str
    kind: str  # first | reminder | escalation | handover | escalated_severity | ack | closed | cleared | digest
    status: str  # sent | failed | rate_limited | silenced
    tier: int
    text: str
    error: str | None = None


@dataclass
class _Track:
    tiers_notified: int = 0
    last_sent_t: float = 0.0
    last_escalation_t: float = 0.0
    repeats: int = 0
    notified: dict[str, Recipient] = field(default_factory=dict)  # ad -> alıcı
    last_holders: frozenset[str] = frozenset()


def parse_ack(text: str) -> tuple[str, str] | None:
    """'ONAY F02-0001 4271' -> ('F02-0001', '4271')."""
    m = _ACK_RE.match(text or "")
    return (m.group(1), m.group(2)) if m else None


def _mask(address: str) -> str:
    return address if len(address) <= 4 else f"…{address[-3:]}"


class EscalationManager:
    def __init__(
        self,
        schedule: OnCallSchedule,
        dispatcher: Dispatcher,
        policy: EscalationPolicy | None = None,
    ) -> None:
        self.schedule = schedule
        self.dispatcher = dispatcher
        self.policy = policy or EscalationPolicy()
        self.log: list[SentMessage] = []
        self._tracks: dict[str, _Track] = {}
        self._window: dict[str, list[float]] = {}  # alıcı -> son 1 saatteki gönderim zamanları
        self._suppressed: dict[str, int] = {}  # alıcı -> fırtına sınırı yüzünden bastırılan sayısı
        self._silenced: dict[str, tuple[float, str]] = {}

    # ---------------------------------------------------------- sessize alma
    def silence(self, name: str, *, until_t_s: float, by: str) -> None:
        if not by.strip():
            raise ValueError("sessize alma için kişi zorunlu")
        self._silenced[name] = (until_t_s, by.strip())

    def _is_silenced(self, name: str, t_s: float) -> bool:
        entry = self._silenced.get(name)
        return entry is not None and t_s < entry[0]

    # ------------------------------------------------------------- olaylar
    def on_event(self, ev: AlarmEvent, alarm: Alarm) -> None:
        t = ev.t_s
        if ev.type in (EventType.OPENED, EventType.REOPENED):
            if alarm.severity >= Severity.ALARM:
                tr = self._tracks.setdefault(alarm.id, _Track())
                tr.last_escalation_t = t
                self._notify_tiers(alarm, t, upto=self.policy.initial_tiers[alarm.severity], kind="first", track=tr)
        elif ev.type is EventType.ESCALATED:
            if alarm.severity >= Severity.ALARM:
                tr = self._tracks.setdefault(alarm.id, _Track())
                want = self.policy.initial_tiers[alarm.severity]
                tr.last_escalation_t = t
                self._notify_tiers(
                    alarm, t, upto=max(want, tr.tiers_notified), kind="escalated_severity", track=tr, force_all=True
                )
        elif ev.type is EventType.ACKED:
            tr = self._tracks.pop(alarm.id, None)
            if tr:
                self._broadcast(alarm, t, tr, "ack", f"[ONAYLANDI] {alarm.connection_id} · {alarm.id} — {alarm.acked_by} üstlendi.")
        elif ev.type is EventType.CLOSED:
            tr = self._tracks.pop(alarm.id, None)
            if tr:
                self._broadcast(alarm, t, tr, "closed", f"[KAPANDI] {alarm.connection_id} · {alarm.id} — {alarm.close_reason or ''}.")
        elif ev.type is EventType.CLEARED:
            tr = self._tracks.get(alarm.id)
            if tr:
                self._broadcast(
                    alarm, t, tr, "cleared",
                    f"[NORMALE DÖNDÜ] {alarm.connection_id} · {alarm.id} — onay bekliyor: ONAY {alarm.id} <belirteç>.",
                )
                self._tracks.pop(alarm.id, None)

    def tick(self, t_s: float, alarms: Iterable[Alarm]) -> None:
        """Zamana bağlı işler: onaylanmayan alarm için hatırlatma / üst kademe / nöbet devri."""
        for alarm in alarms:
            tr = self._tracks.get(alarm.id)
            if tr is None:
                continue
            if alarm.state is not AlarmState.OPEN or alarm.severity < Severity.ALARM:
                continue
            tiers = self.schedule.tiers_at(t_s)
            holders_now = frozenset(r.name for tier in tiers[: tr.tiers_notified] for r in tier)
            if tr.last_holders and holders_now != tr.last_holders:
                # nöbet devri: sıradaki hatırlatmayı beklemeden YENİ nöbetçi hemen aranır
                self._notify_tiers(alarm, t_s, upto=tr.tiers_notified, kind="handover", track=tr, force_all=True)
                continue
            timeout = self.policy.ack_timeout_s[alarm.severity]
            if tr.tiers_notified < len(tiers) and t_s - tr.last_escalation_t >= timeout:
                tr.last_escalation_t = t_s
                self._notify_tiers(alarm, t_s, upto=tr.tiers_notified + 1, kind="escalation", track=tr)
            elif t_s - tr.last_sent_t >= self.policy.repeat_s[alarm.severity] and tr.repeats < self.policy.max_repeats:
                tr.repeats += 1
                self._notify_tiers(alarm, t_s, upto=tr.tiers_notified, kind="reminder", track=tr, force_all=True)
        self._flush_digests(t_s)

    # ------------------------------------------------------------ gönderim
    def _notify_tiers(
        self, alarm: Alarm, t: float, *, upto: int, kind: str, track: _Track, force_all: bool = False
    ) -> None:
        tiers = self.schedule.tiers_at(t)
        upto = min(upto, len(tiers))
        holders_now = frozenset(r.name for tier in tiers[:upto] for r in tier)
        start = 0 if force_all else track.tiers_notified
        idx = start
        while idx < upto:
            reached = self._send_tier(alarm, t, tiers[idx], idx, kind, track)
            if not reached and upto < len(tiers):
                upto += 1  # bu kademeden kimseye ulaşılamadı (hata/sessiz): bir üst kademeyi de ara
            idx += 1
        track.tiers_notified = max(track.tiers_notified, upto)
        track.last_sent_t = t
        track.last_holders = holders_now

    def _send_tier(self, alarm: Alarm, t: float, tier: tuple[Recipient, ...], tier_idx: int, kind: str, track: _Track) -> bool:
        """Kademeye ulaşıldı mı? Teslim edilen VEYA fırtına sınırıyla kasıtlı bastırılan
        mesaj "ulaşıldı" sayılır (bastırma eskalasyon nedeni değildir); yalnız hata veya
        sessize alma yüzünden kimseye gidilemediyse False."""
        reached = False
        for r in tier:
            if self._is_silenced(r.name, t) and alarm.severity < Severity.CRITICAL:
                self._record(t, alarm, r, kind, "silenced", tier_idx, "", None)
                continue
            text = self._compose(alarm, t, kind, tier_idx, track)
            critical_first = alarm.severity is Severity.CRITICAL and kind in ("first", "escalated_severity", "escalation")
            if not critical_first and not self._allow(r, t):
                self._suppressed[r.name] = self._suppressed.get(r.name, 0) + 1
                self._record(t, alarm, r, kind, "rate_limited", tier_idx, text, None)
                reached = True
                continue
            try:
                self.dispatcher.deliver(r, text)
            except Exception as exc:  # noqa: BLE001 -- teslimat hatası kaydedilir, üst kademe aranır
                self._record(t, alarm, r, kind, "failed", tier_idx, text, str(exc)[:120])
                continue
            self._window.setdefault(r.name, []).append(t)
            self._record(t, alarm, r, kind, "sent", tier_idx, text, None)
            track.notified[r.name] = r
            reached = True
        return reached

    def _broadcast(self, alarm: Alarm, t: float, track: _Track, kind: str, text: str) -> None:
        for r in list(track.notified.values()):
            if self._is_silenced(r.name, t) and alarm.severity < Severity.CRITICAL:
                continue
            try:
                self.dispatcher.deliver(r, text)
                self._record(t, alarm, r, kind, "sent", 0, text, None)
            except Exception as exc:  # noqa: BLE001
                self._record(t, alarm, r, kind, "failed", 0, text, str(exc)[:120])

    def _allow(self, r: Recipient, t: float) -> bool:
        window = [x for x in self._window.get(r.name, []) if t - x < HOUR_S]
        self._window[r.name] = window
        return len(window) < self.policy.rate_limit_per_hour

    def _flush_digests(self, t: float) -> None:
        for name, count in list(self._suppressed.items()):
            if count <= 0:
                continue
            recipient = self._recipient_by_name(name, t)
            if recipient is None or not self._allow(recipient, t):
                continue
            text = f"[ÖZET] Fırtına sınırı nedeniyle {count} bildirim bastırıldı; ayrıntı için konsola bakın."
            try:
                self.dispatcher.deliver(recipient, text)
            except Exception:  # noqa: BLE001
                continue
            self._window.setdefault(name, []).append(t)
            self._suppressed[name] = 0
            self.log.append(SentMessage(t, "-", name, recipient.role, recipient.route, "digest", "sent", 0, text))

    def _recipient_by_name(self, name: str, t: float) -> Recipient | None:
        for tier in self.schedule.tiers_at(t):
            for r in tier:
                if r.name == name:
                    return r
        return None

    def _record(self, t: float, alarm: Alarm, r: Recipient, kind: str, status: str, tier: int, text: str, error: str | None) -> None:
        self.log.append(SentMessage(t, alarm.id, r.name, r.role, r.route, kind, status, tier, text, error))

    # --------------------------------------------------------------- metin
    def _compose(self, alarm: Alarm, t: float, kind: str, tier_idx: int, track: _Track) -> str:
        label = SEVERITY_LABELS.get(alarm.severity, alarm.severity.name)
        unit = SPECS[alarm.kind].unit if alarm.kind in SPECS else ""
        score = f" · {alarm.peak_score:.1f} {unit}".rstrip() if alarm.peak_score is not None else ""
        where = f"{alarm.connection_id}" + (f" faz {alarm.phase}" if alarm.phase else "")
        prefix = {
            "first": "",
            "reminder": f"HATIRLATMA {track.repeats}/{self.policy.max_repeats} · ",
            "escalation": "ESKALASYON (onaylanmadı, üst kademe) · ",
            "escalated_severity": "ŞİDDET YÜKSELDİ · ",
            "handover": "NÖBET DEVRİ · ",
        }.get(kind, "")
        lines = [f"{prefix}[{label}] {where} — {alarm.label}{score}"]
        if kind == "handover":
            note = self.schedule.handover_note(t)
            if note:
                lines.append(f"Devir notu: {note}")
        lines.append(f"Onay: ONAY {alarm.id} {alarm.ack_token}")
        lines.append(f"Kademe {tier_idx + 1}")
        return "\n".join(lines)

    # ---------------------------------------------------------------- özet
    def sent(self, *, status: str = "sent") -> list[SentMessage]:
        return [m for m in self.log if m.status == status]

    def masked_log(self) -> list[dict]:
        return [
            {"t_s": m.t_s, "alarm": m.alarm_id, "to": m.recipient, "route": m.route, "kind": m.kind, "status": m.status, "tier": m.tier}
            for m in self.log
        ]


class TelegramAckPoller:
    """Telegram `getUpdates` ile 'ONAY <alarm> <belirteç>' yanıtlarını okur ve alarm
    motoruna iletir. Yalnız izinli sohbetlerden (`allowed_chat_ids`) gelen mesajlar
    işlenir; kimlik Telegram'ın kendi `from` alanından alınır (uydurulamaz).

    `http_get(url, params)` -> dict enjekte edilir (testte sahte, gerçekte requests)."""

    def __init__(self, bot_token: str, allowed_chat_ids: set[str], http_get: Callable[[str, dict], dict] | None = None) -> None:
        self.bot_token = bot_token
        self.allowed = {str(c) for c in allowed_chat_ids}
        self._get = http_get or self._default_get
        self._offset = 0

    @staticmethod
    def _default_get(url: str, params: dict) -> dict:
        import requests

        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()

    def poll(self, apply_ack: Callable[[str, str, str], object]) -> list[str]:
        """`apply_ack(alarm_id, token, by)`; işlenen alarm kimliklerini döner."""
        url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates"
        data = self._get(url, {"offset": self._offset, "timeout": 0})
        done: list[str] = []
        for upd in data.get("result", []):
            self._offset = max(self._offset, upd["update_id"] + 1)
            msg = upd.get("message") or {}
            chat_id = str((msg.get("chat") or {}).get("id", ""))
            if chat_id not in self.allowed:
                continue
            parsed = parse_ack(msg.get("text", ""))
            if not parsed:
                continue
            sender = msg.get("from") or {}
            by = " ".join(x for x in (sender.get("first_name"), sender.get("last_name")) if x) or sender.get("username", "")
            try:
                apply_ack(parsed[0], parsed[1], by)
                done.append(parsed[0])
            except Exception:  # noqa: BLE001 -- geçersiz belirteç vb.: sessizce yoksay, alarm açık kalır
                continue
        return done
