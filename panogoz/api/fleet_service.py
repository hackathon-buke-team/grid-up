"""Filo servisi: çok kanallı senaryo panoları + alarm motoru + eskalasyon + simülasyon saati.

Konsolun (K3 3.1/3.4/3.5) tek gerçek kaynağı. Her pano bir senaryo örneğidir
(panogoz/sim/scenarios.py); analiz (bastırma→onay→füzyon) bir kez önceden hesaplanır,
alarm motoru ise simülasyon saati ilerledikçe örnek örnek beslenir. Böylece onay/kapatma/
sessize alma gibi operatör eylemleri kalıcı durumdur ve saat ileri akar (geri sarma yok;
`reset()` başa döner).

Bildirim varsayılan olarak BELLEKTE "telefon" gösterimidir (dış sisteme bağlanmaz).
Gerçek Telegram yalnız `PANOGOZ_LIVE_NOTIFY=1` + `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID`
birlikte ayarlıysa, yalnızca 1. kademe nöbetçiye gider.
"""
from __future__ import annotations

import math
import os
import threading
import time
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Callable

from panogoz.contracts.channels import Phase
from panogoz.detector.condensation import dew_margin_c
from panogoz.notify.escalation import (
    ConsoleDispatcher,
    EscalationManager,
    EscalationPolicy,
    OnCallSchedule,
    Recipient,
    RoutedDispatcher,
    Shift,
    telegram_route,
)
from panogoz.rules.alarms import Alarm, AlarmEngine, AlarmState, EventType, tracks_now
from panogoz.rules.engine import Severity
from panogoz.rules.pipeline import SPECS, Analysis, Family, analyze
from panogoz.rules.workorders import work_order
from panogoz.sim.scenarios import SCENARIOS, Scenario, ScenarioData, generate, shift_scenario

DAY_S = 86400.0
PERIOD_S = 900.0
STORM_WINDOW_S = 3600.0
STORM_LIMIT = 5
DEFAULT_START_DAY = 30.0
SEVERITY_LABELS = {"NORMAL": "NORMAL", "WARNING": "UYARI", "ALARM": "ALARM", "CRITICAL": "KRİTİK"}


@dataclass(frozen=True)
class PanelSpec:
    id: str
    name: str
    location: str
    scenario_key: str
    onset_day: float | None = None  # None: senaryonun kendi başlangıcı


def default_fleet_specs() -> list[PanelSpec]:
    """22 senaryonun her biri bir pano. Arıza başlangıçları 34–46. güne YAYILIR:
    gerçek bir filoda arızalar aynı dakikada başlamaz (ve fırtına demosu ayrı, kasıtlıdır)."""
    specs: list[PanelSpec] = []
    fault_i = 0
    for i, (key, sc) in enumerate(SCENARIOS.items()):
        onset = None
        if sc.expect.value in ("detect", "advisory"):
            onset = 34.0 + 1.1 * fault_i
            fault_i += 1
        tm, slot = i // 4 + 1, i % 4 + 1
        specs.append(
            PanelSpec(
                id=f"P{i + 1:02d}",
                name=f"Örnek TM-{tm} · Pano {slot}",
                location=f"Örnek TM-{tm} · AG Pano-{slot} (1600 kVA) · alt bölüm, kablo/bara boşluğu",
                scenario_key=key,
                onset_day=onset,
            )
        )
    return specs


@lru_cache(maxsize=128)
def _scenario_run(scenario_key: str, onset_day: float | None, seed: int):
    """Üretim + analiz salt-okunur sonuçtur (motor durumu Panel'de tutulur), bu yüzden
    paylaşılabilir: `reset()`, tekrarlanan enjeksiyon ve testler yeniden hesaplamaz."""
    scenario = SCENARIOS[scenario_key]
    if onset_day is not None:
        scenario = shift_scenario(scenario, onset_day)
    data = generate(scenario, seed=seed)
    return scenario, data, analyze(data)


class SimClock:
    """Simülasyon saati: duvar saatinden `speed` (sim-sn / gerçek-sn) ile ilerler."""

    def __init__(self, start_t_s: float, speed: float = 3600.0, running: bool = False, wall: Callable[[], float] = time.monotonic):
        self._wall = wall
        self._t0 = start_t_s
        self._ref = wall()
        self.speed = speed
        self.running = running

    def now(self) -> float:
        return self._t0 + (self._wall() - self._ref) * self.speed if self.running else self._t0

    def set(self, *, speed: float | None = None, running: bool | None = None, jump_to: float | None = None) -> None:
        current = self.now()
        self._t0 = current if jump_to is None else jump_to
        self._ref = self._wall()
        if speed is not None:
            self.speed = speed
        if running is not None:
            self.running = running


class MemoryDispatcher(ConsoleDispatcher):
    """Bellekte 'telefon' gösterimi; dış sisteme bağlanmaz."""


@dataclass
class Panel:
    spec: PanelSpec
    index: int
    scenario: Scenario
    seed: int
    data: ScenarioData
    analysis: Analysis
    engine: AlarmEngine
    revision: int = 0
    injected_scenario: str | None = None
    reason_counts: dict[str, int] = field(default_factory=dict)  # bastırma gerekçesi -> örnek sayısı (WARMUP hariç)
    capped_count: int = 0  # füzyonda UYARI'ya tavanlanan (PD) örnek sayısı
    past: list["Panel"] = field(default_factory=list)  # enjeksiyonla değiştirilmeden önceki sürümler (alarm geçmişi = denetim kaydı)


@dataclass
class RosterConfig:
    tiers_day: tuple[tuple[Recipient, ...], ...]
    tiers_night: tuple[tuple[Recipient, ...], ...]


def default_roster(live_chat_id: str | None = None) -> RosterConfig:
    def r(name, role, n):
        return Recipient(name, role, "console", f"555-00{n}")

    first = Recipient("Saha nöbetçisi (Ayşe Y.)", "saha nöbetçisi", "telegram" if live_chat_id else "console", live_chat_id or "555-001")
    first_night = Recipient("Gece nöbetçisi (Kemal D.)", "saha nöbetçisi (gece)", "telegram" if live_chat_id else "console", live_chat_id or "555-004")
    return RosterConfig(
        tiers_day=((first,), (r("Bölge sorumlusu (Mehmet K.)", "bölge sorumlusu", 2),), (r("Operasyon müdürü (Zeynep A.)", "operasyon müdürü", 3),)),
        tiers_night=((first_night,), (r("Gece bölge sorumlusu (Nur T.)", "bölge sorumlusu (gece)", 5),), (r("Operasyon müdürü (Zeynep A.)", "operasyon müdürü", 3),)),
    )


class FleetService:
    def __init__(
        self,
        specs: list[PanelSpec] | None = None,
        *,
        seed: int = 1,
        start_t_s: float = DEFAULT_START_DAY * DAY_S,
        speed: float = 3600.0,
        wall: Callable[[], float] = time.monotonic,
        dispatcher=None,
        roster: RosterConfig | None = None,
        policy: EscalationPolicy | None = None,
    ) -> None:
        self._lock = threading.RLock()
        self.specs = specs if specs is not None else default_fleet_specs()
        self.seed = seed
        self.start_t_s = start_t_s
        self._speed0 = speed
        self._wall = wall
        self._dispatcher_arg = dispatcher
        self._roster = roster
        self._policy = policy
        self._build()

    # ------------------------------------------------------------- kurulum
    def _build(self) -> None:
        self.clock = SimClock(self.start_t_s, self._speed0, running=False, wall=self._wall)
        self.memory = MemoryDispatcher()
        live = os.environ.get("PANOGOZ_LIVE_NOTIFY") == "1" and os.environ.get("TELEGRAM_BOT_TOKEN") and os.environ.get("TELEGRAM_CHAT_ID")
        roster = self._roster or default_roster(os.environ.get("TELEGRAM_CHAT_ID") if live else None)
        self.live_notify = bool(live) and self._roster is None
        if self._dispatcher_arg is not None:
            dispatcher = self._dispatcher_arg
        elif self.live_notify:
            dispatcher = RoutedDispatcher({"telegram": telegram_route(os.environ["TELEGRAM_BOT_TOKEN"]), "console": self.memory.deliver})
        else:
            dispatcher = self.memory
        self.schedule = OnCallSchedule([Shift(8, 20, roster.tiers_day), Shift(20, 8, roster.tiers_night)])
        self.manager = EscalationManager(self.schedule, dispatcher, self._policy)
        self.panels: dict[str, Panel] = {}
        for idx, spec in enumerate(self.specs):
            self.panels[spec.id] = self._make_panel(spec, idx, spec.scenario_key, spec.onset_day, revision=0)
        self.cursor = 0  # sıradaki işlenecek örnek indeksi
        self.storm_limit = STORM_LIMIT
        self.advance_to(self.start_t_s)

    def _make_panel(self, spec: PanelSpec, idx: int, scenario_key: str, onset_day: float | None, *, revision: int) -> Panel:
        seed = self.seed + idx
        scenario, data, analysis = _scenario_run(scenario_key, onset_day, seed)
        prefix = spec.id if revision == 0 else f"{spec.id}r{revision}"
        engine = AlarmEngine(spec.name, id_prefix=prefix, seed=seed)
        return Panel(spec, idx, scenario, seed, data, analysis, engine, revision, scenario_key if revision else None)

    def reset(self) -> None:
        with self._lock:
            self._build()

    # ------------------------------------------------------------- zaman
    @property
    def n_samples(self) -> int:
        return len(next(iter(self.panels.values())).data.t_s)

    @property
    def end_t_s(self) -> float:
        return (self.n_samples - 1) * PERIOD_S

    def sync(self) -> float:
        with self._lock:
            return self.advance_to(min(self.clock.now(), self.end_t_s))

    def advance_to(self, t_s: float) -> float:
        """Filoyu `t_s` anına kadar işler (geri gitmez). Tüm panolar aynı zaman ızgarasını
        paylaşır; her adımda önce her panonun motoru, sonra ortak eskalasyon tick'i işlenir."""
        with self._lock:
            target = min(int(t_s // PERIOD_S), self.n_samples - 1)
            while self.cursor <= target:
                i = self.cursor
                t = i * PERIOD_S
                active: list[Alarm] = []
                for panel in self.panels.values():
                    for ev in panel.engine.step(t, tracks_now(panel.analysis, i)):
                        self.manager.on_event(ev, panel.engine.alarms[ev.alarm_id])
                    for tr in panel.analysis.tracks:
                        reason = tr.reasons[i]
                        if reason and reason != "WARMUP":
                            panel.reason_counts[reason] = panel.reason_counts.get(reason, 0) + 1
                        if tr.capped[i]:
                            panel.capped_count += 1
                    active.extend(a for a in panel.engine.alarms.values() if a.state in (AlarmState.OPEN, AlarmState.ACKED))
                self.manager.tick(t, active)
                self.cursor += 1
            return self.now_t_s

    @property
    def now_t_s(self) -> float:
        return (self.cursor - 1) * PERIOD_S

    @property
    def now_index(self) -> int:
        return max(0, self.cursor - 1)

    def set_clock(self, *, speed: float | None = None, running: bool | None = None, jump_to_day: float | None = None) -> dict:
        with self._lock:
            if speed is not None and speed <= 0:
                raise ValueError("hız pozitif olmalı")
            jump = None
            if jump_to_day is not None:
                jump = max(jump_to_day * DAY_S, self.now_t_s)  # geri sarma yok
            self.clock.set(speed=speed, running=running, jump_to=jump)
            self.sync()
            return self.clock_state()

    def clock_state(self) -> dict:
        return {
            "now_t_s": self.now_t_s,
            "day": self.now_t_s / DAY_S,
            "running": self.clock.running and self.now_t_s < self.end_t_s,
            "speed": self.clock.speed,
            "end_day": self.end_t_s / DAY_S,
        }

    # ------------------------------------------------------------- alarmlar
    def _versions(self):
        """Her panonun mevcut ve geçmiş sürümleri (geçmiş alarm kayıtları silinmez)."""
        for p in self.panels.values():
            yield from p.past
            yield p

    def _panel_of(self, alarm_id: str) -> Panel:
        for cand in self._versions():
            if alarm_id in cand.engine.alarms:
                return cand
        raise KeyError(f"alarm bulunamadı: {alarm_id}")

    def _all_alarms(self) -> list[tuple[Panel, Alarm]]:
        return [(cand, a) for cand in self._versions() for a in cand.engine.alarms.values()]

    def alarm_row(self, panel: Panel, a: Alarm) -> dict:
        d = a.to_dict()
        d.update(
            {
                "panel_id": panel.spec.id,
                "panel_name": panel.spec.name,
                "severity_label": SEVERITY_LABELS[a.severity.name],
                "peak_label": SEVERITY_LABELS[a.peak.name],
                "category": "sistem" if a.family == Family.SYSTEM.value else "süreç",
                "advisory": SPECS[a.kind].advisory,
                "unit": SPECS[a.kind].unit,
                "notified_count": sum(1 for m in self.manager.log if m.alarm_id == a.id and m.status == "sent" and m.kind in ("first", "reminder", "escalation", "escalated_severity", "handover")),
                "age_s": max(0.0, self.now_t_s - a.opened_t_s),
            }
        )
        return d

    def alarms(
        self,
        *,
        state: str | None = None,
        min_severity: str | None = None,
        family: str | None = None,
        panel_id: str | None = None,
        kind: str | None = None,
        sort: str = "priority",
    ) -> list[dict]:
        with self._lock:
            self.sync()
            rows = []
            if min_severity and min_severity not in Severity.__members__:
                raise ValueError(f"geçersiz şiddet: {min_severity!r} (NORMAL/WARNING/ALARM/CRITICAL)")
            floor = Severity[min_severity] if min_severity else Severity.NORMAL
            for panel, a in self._all_alarms():
                if state == "active" and not a.is_active and a.state is not AlarmState.CLEARED:
                    continue
                if state in ("open", "acked", "cleared", "closed") and a.state.value != state:
                    continue
                if a.severity < floor and a.peak < floor:
                    continue
                if family and a.family != family:
                    continue
                if panel_id and panel.spec.id != panel_id:
                    continue
                if kind and a.kind != kind:
                    continue
                rows.append((panel, a))
            key_fns = {
                "priority": lambda pa: (pa[1].state is AlarmState.CLOSED, -int(pa[1].severity), -pa[1].opened_t_s),
                "opened": lambda pa: -pa[1].opened_t_s,
                "severity": lambda pa: (-int(pa[1].severity), -pa[1].opened_t_s),
                "panel": lambda pa: (pa[0].spec.id, -pa[1].opened_t_s),
                "state": lambda pa: (pa[1].state.value, -int(pa[1].severity)),
            }
            rows.sort(key=key_fns.get(sort, key_fns["priority"]))
            return [self.alarm_row(p, a) for p, a in rows]

    def ack(self, alarm_id: str, token: str, by: str) -> dict:
        with self._lock:
            self.sync()
            panel = self._panel_of(alarm_id)
            alarm = panel.engine.ack(alarm_id, token, by, self.now_t_s)
            self.manager.on_event(panel.engine.events[-1], alarm)
            return self.alarm_row(panel, alarm)

    def close(self, alarm_id: str, reason: str, by: str) -> dict:
        with self._lock:
            self.sync()
            panel = self._panel_of(alarm_id)
            alarm = panel.engine.close(alarm_id, reason, by, self.now_t_s)
            self.manager.on_event(panel.engine.events[-1], alarm)
            return self.alarm_row(panel, alarm)

    def mute(self, panel_id: str, scope: str, minutes: float, by: str, reason: str) -> dict:
        with self._lock:
            self.sync()
            panel = self.panels[panel_id]
            m = panel.engine.mute(scope, until_t_s=self.now_t_s + minutes * 60.0, by=by, reason=reason)
            return {"panel_id": panel_id, "scope": m.scope, "until_t_s": m.until_t_s, "by": m.by, "reason": m.reason}

    def silence(self, name: str, minutes: float, by: str) -> dict:
        with self._lock:
            self.sync()
            self.manager.silence(name, until_t_s=self.now_t_s + minutes * 60.0, by=by)
            return {"name": name, "until_t_s": self.now_t_s + minutes * 60.0, "by": by}

    def alarm_detail(self, alarm_id: str) -> dict:
        with self._lock:
            self.sync()
            panel = self._panel_of(alarm_id)
            a = panel.engine.alarms[alarm_id]
            row = self.alarm_row(panel, a)
            tr = panel.analysis.track(a.track_key)
            i_now = self.now_index
            start_i = max(0, int((a.opened_t_s - 2 * DAY_S) // PERIOD_S))
            idx = range(start_i, i_now + 1, 4)
            reasons: dict[str, int] = {}
            for j in range(start_i, i_now + 1):
                if tr.reasons[j]:
                    reasons[tr.reasons[j]] = reasons.get(tr.reasons[j], 0) + 1
            spec = tr.spec
            thresholds = {k.name: v for k, v in spec.thresholds.items() if v < 1e9}
            evidence = {
                "track_key": tr.key,
                "unit": spec.unit,
                "thresholds": thresholds,
                "deadband": spec.deadband,
                "advisory": spec.advisory,
                "max_severity": spec.max_severity.name,
                "t_s": [panel.data.t_s[j] for j in idx],
                "score": [tr.scores[j] for j in idx],
                "severity": [int(tr.fused[j]) for j in idx],
                "suppressed_reasons": reasons,
                "advisory_capped_samples": sum(1 for j in range(start_i, i_now + 1) if tr.capped[j]),
                "window_start_t_s": panel.data.t_s[start_i],
            }
            wo = work_order(a.kind, a.severity, connection_id=panel.spec.name, location=panel.spec.location, phase=a.phase)
            messages = [
                {"t_s": m.t_s, "to": m.recipient, "role": m.role, "route": m.route, "kind": m.kind, "status": m.status, "text": m.text}
                for m in self.manager.log
                if m.alarm_id == a.id
            ]
            return {"alarm": row, "evidence": evidence, "work_order": wo, "messages": messages}

    # ------------------------------------------------------------- panolar
    def panel_state(self, panel: Panel) -> dict:
        i = self.now_index
        process = [t for t in panel.analysis.tracks if t.spec.family is not Family.SYSTEM]
        sev = max((t.fused[i] for t in process), default=Severity.NORMAL)
        # olay tipi (latching) alarm sinyal dönse de onaylanana kadar panonun şiddetinde görünür
        sev = max([sev, *[a.severity for a in panel.engine.alarms.values() if a.latching and a.is_active]])
        system = next((t for t in panel.analysis.tracks if t.spec.kind == "comms_lost"), None)
        stale = bool(system and system.fused[i] >= Severity.WARNING)
        d = panel.data
        active_alarms = [a for a in panel.engine.alarms.values() if a.is_active or a.state is AlarmState.CLEARED]
        de_energised = any(t.reasons[i] == "DE_ENERGISED" for t in panel.analysis.tracks if t.spec.kind == "loose_bolt")
        return {
            "id": panel.spec.id,
            "name": panel.spec.name,
            "location": panel.spec.location,
            "scenario_key": panel.spec.scenario_key if panel.revision == 0 else panel.injected_scenario,
            "scenario_title": panel.scenario.title,
            "revision": panel.revision,
            "severity": sev.name,
            "severity_label": SEVERITY_LABELS[sev.name],
            "stale": stale,
            "de_energised": de_energised,
            "open_alarms": sum(1 for a in active_alarms if a.state is AlarmState.OPEN),
            "active_alarms": len(active_alarms),
            "current_a": max(d.current_a[p][i] for p in Phase),
            "joint_temp_c": max(d.joint_temp_c[p][i] for p in Phase),
            "ambient_c": d.ambient_c[i],
            "humidity_rh": d.humidity_rh[i],
        }

    def panels_summary(self) -> list[dict]:
        with self._lock:
            self.sync()
            return [self.panel_state(p) for p in self.panels.values()]

    def panel_series(self, panel_id: str, days: float = 14.0) -> dict:
        with self._lock:
            self.sync()
            panel = self.panels[panel_id]
            d = panel.data
            i_now = self.now_index
            start = max(0, i_now - int(days * 96))
            idx = list(range(start, i_now + 1, 4))
            tracks = {}
            for tr in panel.analysis.tracks:
                tracks[tr.key] = {
                    "kind": tr.spec.kind,
                    "label": tr.spec.label,
                    "family": tr.spec.family.value,
                    "unit": tr.spec.unit,
                    "advisory": tr.spec.advisory,
                    "thresholds": {k.name: v for k, v in tr.spec.thresholds.items() if v < 1e9},
                    "score": [tr.scores[j] for j in idx],
                    "severity": [int(tr.fused[j]) for j in idx],
                    "reasons": [tr.reasons[j] for j in idx],
                }
            return {
                "panel": self.panel_state(panel),
                "t_s": [d.t_s[j] for j in idx],
                "current_a": {p.value: [d.current_a[p][j] for j in idx] for p in Phase},
                "joint_temp_c": {p.value: [d.joint_temp_c[p][j] for j in idx] for p in Phase},
                "neutral_current_a": [d.neutral_current_a[j] for j in idx],
                "neutral_temp_c": [d.neutral_temp_c[j] for j in idx],
                "ambient_c": [d.ambient_c[j] for j in idx],
                "wall_temp_c": [d.wall_temp_c[j] for j in idx],
                "humidity_rh": [d.humidity_rh[j] for j in idx],
                "dew_margin_c": [dew_margin_c(d.ambient_c[j], d.humidity_rh[j], d.wall_temp_c[j]) for j in idx],
                "pd_index": [d.pd_index[j] for j in idx],
                "arc_trip": [d.arc_trip[j] for j in idx],
                "tracks": tracks,
                "theta_tau_s": panel.analysis.theta_tau_s,
                "rated_current_a": d.rated_current_a,
            }

    def suppression_summary(self, panel_id: str | None = None) -> list[dict]:
        """Bastırma ekranı: her panoda hangi gerekçeyle kaç örnek puansız bırakıldı, kaç
        PD örneği füzyonda UYARI'ya tavanlandı (şu ana kadar; adım adım biriktirilir)."""
        with self._lock:
            self.sync()
            return [
                {
                    "panel_id": p.spec.id,
                    "name": p.spec.name,
                    "reasons": dict(p.reason_counts),
                    "advisory_capped": p.capped_count,
                    "muted_events": len(p.engine.suppressed),
                    "mutes": [m.scope for m in p.engine.mutes if m.until_t_s > self.now_t_s],
                }
                for p in self.panels.values()
                if not panel_id or p.spec.id == panel_id
            ]

    # ------------------------------------------------------------- bildirim
    def notifications(self, limit: int = 100) -> list[dict]:
        with self._lock:
            self.sync()
            msgs = self.manager.log[-limit:]
            return [
                {"t_s": m.t_s, "alarm_id": m.alarm_id, "to": m.recipient, "role": m.role, "route": m.route, "kind": m.kind,
                 "status": m.status, "tier": m.tier, "text": m.text}
                for m in reversed(msgs)
            ]

    def storms(self) -> dict:
        """Filo düzeyi alarm fırtınası: 1 saatlik pencerede `storm_limit`+ alarm açılışı (UYARI dahil)."""
        with self._lock:
            self.sync()
            opens = sorted(
                (ev.t_s, p.spec.id)
                for p in self._versions()
                for ev in p.engine.events
                if ev.type in (EventType.OPENED, EventType.REOPENED) and ev.severity >= Severity.WARNING
            )
            episodes: list[dict] = []
            j = 0
            for i in range(len(opens)):
                while opens[i][0] - opens[j][0] > STORM_WINDOW_S:
                    j += 1
                window = opens[j : i + 1]
                if len(window) >= self.storm_limit:
                    start, end = window[0][0], window[-1][0]
                    if episodes and start <= episodes[-1]["end_t_s"] + STORM_WINDOW_S:
                        episodes[-1]["end_t_s"] = end
                        episodes[-1]["count"] = max(episodes[-1]["count"], len(window))
                        episodes[-1]["panels"] = sorted(set(episodes[-1]["panels"]) | {p for _, p in window})
                    else:
                        episodes.append({"start_t_s": start, "end_t_s": end, "count": len(window), "panels": sorted({p for _, p in window})})
            active = bool(episodes) and self.now_t_s - episodes[-1]["end_t_s"] <= STORM_WINDOW_S
            return {"limit": self.storm_limit, "window_s": STORM_WINDOW_S, "active": active, "episodes": episodes}

    def kpis(self) -> dict:
        with self._lock:
            self.sync()
            rows = [(p, a) for p, a in self._all_alarms()]
            process_active = [a for p, a in rows if (a.is_active or a.state is AlarmState.CLEARED) and a.family != Family.SYSTEM.value]
            by_sev = {s.name: 0 for s in (Severity.WARNING, Severity.ALARM, Severity.CRITICAL)}
            for a in process_active:
                if a.state is not AlarmState.CLEARED:
                    by_sev[a.severity.name] += 1
            awaiting = sum(1 for p, a in rows if a.state is AlarmState.OPEN and a.severity >= Severity.ALARM)
            hour_ago = self.now_t_s - 3600.0
            recent = [m for m in self.manager.log if m.t_s >= hour_ago]
            return {
                "active_by_severity": by_sev,
                "awaiting_ack": awaiting,
                "cleared_pending": sum(1 for _, a in rows if a.state is AlarmState.CLEARED),
                "system_alerts": sum(1 for _, a in rows if a.is_active and a.family == Family.SYSTEM.value),
                "messages_last_hour": sum(1 for m in recent if m.status == "sent"),
                "rate_limited_last_hour": sum(1 for m in recent if m.status == "rate_limited"),
                "failed_last_hour": sum(1 for m in recent if m.status == "failed"),
                "storm_active": self.storms()["active"],
                "panels_total": len(self.panels),
                "panels_alarming": sum(1 for p in self.panels.values() if self.panel_state(p)["severity"] in ("ALARM", "CRITICAL")),
                "live_notify": self.live_notify,
            }

    # ------------------------------------------------------------- demo kontrol
    def inject(self, panel_id: str, scenario_key: str, *, onset_in_s: float = 3600.0) -> dict:
        """Panoya 'şimdi + onset_in_s' anında başlayan bir senaryo enjekte eder (arıza
        verisi baştan üretilir; geçmiş aynı tohumla sağlıklı kalır)."""
        with self._lock:
            self.sync()
            if scenario_key not in SCENARIOS:
                raise KeyError(f"bilinmeyen senaryo: {scenario_key}")
            panel = self.panels[panel_id]
            t_now = self.now_t_s
            onset_day = math.ceil((t_now + onset_in_s) / PERIOD_S) * PERIOD_S / DAY_S
            if onset_day > 56.0:
                raise ValueError("simülasyon penceresinin sonuna çok yakın; enjeksiyon için sıfırla")
            if onset_day < 16.0:
                raise ValueError("taban çizgisi öğrenimi için en az 16. günden sonra enjekte edilebilir")
            for a in list(panel.engine.alarms.values()):
                if a.state is not AlarmState.CLOSED:
                    panel.engine.close(a.id, "diger", "sistem (senaryo değiştirildi)", t_now)
                    self.manager.on_event(panel.engine.events[-1], a)
            new = self._make_panel(panel.spec, panel.index, scenario_key, onset_day, revision=panel.revision + 1)
            new.past = [*panel.past, panel]
            self.panels[panel_id] = new
            return self.panel_state(new)

    def clear(self, panel_id: str) -> dict:
        return self.inject(panel_id, "healthy_baseline", onset_in_s=900.0)

    def inject_storm(self, panel_ids: list[str] | None = None, *, scenario_key: str = "arc_integrity_fault") -> list[str]:
        """Fırtına demosu: birden çok panoda AYNI ANDA ortak nedenli olay (varsayılan: ark koruma
        tanılama hatası, ör. hatalı bir ürün yazılımı güncellemesi). Beklenen sonuç: konsolda
        fırtına görünümü, alıcıda fırtına sınırı + tek özet mesajı."""
        with self._lock:
            targets = panel_ids or list(self.panels)[:8]
            for pid in targets:
                self.inject(pid, scenario_key, onset_in_s=900.0)
            return targets
