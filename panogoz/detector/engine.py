"""DetectorEngine - the orchestrator.

What this module is responsible for
-----------------------------------
Turn a stream of :class:`panogoz.contracts.envelope.Envelope` messages into a
fully populated :class:`panogoz.contracts.live.PanelLive` image, and persist
enough state that a process restart loses nothing.

It fills everything in ``PanelLive`` EXCEPT ``risks``, ``hi_waterfall``,
``health_index``, ``severity`` and ``alarms``.  Those are fusion and policy, and
they belong to the rules layer.  The split is deliberate: this module answers
"what is measurably true about this panel", the rules layer answers "what should
we do about it".  Keeping the two apart is what makes it possible to change an
alarm policy without touching a physics estimator, and what makes the physics
testable on its own.

Absolute safety limits are armed FROM MINUTE ONE
------------------------------------------------
``T_joint > 110 C -> KRITIK`` and ``T_joint > 130 C -> ACIL`` are evaluated on
every sample, on every joint, regardless of the learn window, regardless of the
CUSUM training state, and regardless of whether theta is available at all.

This matters because the learn window is otherwise a genuine hole in the
argument.  A joint that was ALREADY degrading on commissioning day trains a
high baseline, and drift detection will never flag it - it is not drifting, it
is already bad.  theta catches most of those on day one (a degraded joint is
hot relative to its healthy siblings from the first reading), but a feeder with
two bad phases would even defeat that.  The absolute limits are the backstop,
and they cost nothing.

110 C is chosen against the insulation, not against the copper: the panel is
wired with 1 kV XLPE-class cable whose continuous conductor limit is 90 C, and
the lug is the hottest point of that cable.  130 C is where solder-tinned
surfaces and cable insulation start to be damaged in minutes rather than years.

Where load factor comes from, and where we admit we are estimating
------------------------------------------------------------------
No outgoing way in a TEDAS panel has a utility CT - the 2500/5 measures the
incomer only.  So:

* the six thermal clips on feeders 6 and 7 carry their **own split-core CT** and
  their load factor is measured directly, ``f = I_clip / feeder_rating``;
* every other bottom-compartment lug is seen only by the IR array, and its
  current is genuinely unknown.  For those we use the panel's per-phase current
  divided by the total rated current of all non-spare ways, which is the
  proportional-share assumption ``I_joint = I_phase * rated_j / sum(rated)``.
  It is an estimate, it is labelled as an estimate in the joint's ``note``, and
  the two definitions agree exactly when the panel is loaded proportionally.

A judge who asks "how do you know the current in lug C03/L2" gets the honest
answer: we do not, we know the phase current and the way's rating, and the six
clips exist precisely so that at least two feeders are measured directly and can
validate the assumption.

Restart behaviour
-----------------
Per-joint RLS state (theta, covariance, lag state, tau) and per-joint CUSUM
state (baseline, sigma, training moments, arms) are written to ``joint_state``
and read back in ``__init__``.  The drift statistics - CUSUM, slope, changepoint,
alarm-day counter - are additionally RECOMPUTED from scratch from the
``joint_daily`` rollup on every :meth:`roll_daily`.  That is a deliberate
belt-and-braces choice: an incremental statistic that has been running for eight
months is impossible to audit, whereas one recomputed from a table anybody can
SELECT is reproducible on demand, and 40 joints x 180 days is microseconds.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from statistics import median
from typing import Any, Sequence

from panogoz.contracts import assets, channels, icd
from panogoz.contracts.envelope import Envelope, SeqTracker, is_stale
from panogoz.contracts.live import (ArcView, DeviceView, EtaView, JointView,
                                    PanelLive, PdView)

from panogoz.detector import changepoint as cp
from panogoz.detector import cusum as cs
from panogoz.detector import dewpoint as dp
from panogoz.detector import horizon as hz
from panogoz.detector import neutral as nt
from panogoz.detector import theta as th

DAY_S = 86400.0

# --------------------------------------------------------------------------
# Thresholds that are policy-free enough to live here
# --------------------------------------------------------------------------

#: Absolute joint temperature limits.  Never gated by the learn window.
T_JOINT_KRITIK_C = 110.0
T_JOINT_ACIL_C = 130.0

#: theta levels for the observational per-joint severity.
THETA_UYARI_K = th.THETA_ALARM_K      # 5.0
THETA_IZLE_K = 2.0

# --------------------------------------------------------------------------
# Two ladders, because theta answers two different questions
# --------------------------------------------------------------------------
#
# ABSOLUTE theta is delta-T OVER A SIMILAR COMPONENT at rated current, so the
# right thermography anchor is the "over similar component" band set
# (1-3 / 4-15 / >15 K), NOT the coarser 10/20/40 K set - that one grades delta-T
# over AMBIENT and applying it here would under-report by roughly a factor of
# three.  Getting that distinction wrong in front of a thermography-qualified
# engineer would cost more credibility than the whole metric earns.
#
# Note honestly that IEC 61439-1 sets NO numeric limit for a busbar joint - it
# defers to its Cizelge 8 table, which was not in the supplied documents.  These
# bands are established practice, not a standard we can cite chapter and verse.
# The one hard material limit is tin plating melting at 232 C.
# The bands are 1-3 K "possible deficiency", 4-15 K "probable deficiency, repair
# as time permits", >15 K "major discrepancy, repair immediately".  The ladder
# below sits inside them rather than on their edges: a fleet of 112 panels holds
# roughly 4 500 joints, so raising a watch at the bottom of the "possible" band
# would put a permanent queue in front of an operator and the system would be
# switched off by month three.  We start watching at the top of that band.
THETA_ABS_IZLE_K = 2.0       # top of "possible deficiency"
THETA_ABS_UYARI_K = 5.0      # inside "probable deficiency"
THETA_ABS_KRITIK_K = 12.0    # upper "probable deficiency"
THETA_ABS_ACIL_K = 25.0      # well into "major discrepancy"

#: Mutlak theta merdiveni, ufuk projeksiyonunun hedef sectigi sira.
#:
#: Dort sabitten TUREIR, onlari tekrar etmez: bir esigi degistiren kisi tek
#: yerde degistirir.  horizon.project() bunu PARAMETRE olarak alir; engine'i
#: import etmez, cunku engine zaten changepoint'i import ediyor ve ters yon
#: dongu kurardi.
THETA_ABS_LADDER: tuple[tuple[str, float], ...] = (
    ("IZLE", THETA_ABS_IZLE_K),
    ("UYARI", THETA_ABS_UYARI_K),
    ("KRITIK", THETA_ABS_KRITIK_K),
    ("ACIL", THETA_ABS_ACIL_K),
)

# The RISE above a joint's own commissioned baseline is judged on daily medians
# with a CUSUM confirmation.  Its thresholds are far lower, and legitimately so:
# the daily median of ~16 samples cuts the measurement noise by sqrt(16) = 4, and
# the CUSUM supplies the statistical confidence that a single sample cannot.
# This is the path that gives weeks of warning, and it is why the system does not
# need the defect to clear the instantaneous detectability floor.
THETA_RISE_IZLE_K = 1.0
THETA_RISE_UYARI_K = 5.0
THETA_RISE_KRITIK_K = 15.0

#: A confirmed drift this fast escalates one level.
#:
#: Level alone is not the whole story.  A joint sitting at +10 K that has sat
#: there since commissioning is a manufacturing defect to schedule; the same
#: +10 K climbing at 2.5 K per week reaches the "major discrepancy" band inside
#: a fortnight, and treating the two identically wastes the entire point of
#: measuring a trend.  So a CUSUM-confirmed drift steeper than this promotes the
#: verdict by one step - never past KRITIK, because ACIL is reserved for facts
#: (an absolute temperature, an arc trip) rather than for extrapolations.
SLOPE_ESCALATE_K_PER_WEEK = 0.5

#: A sibling reading older than this is not a sibling any more.  Five minutes
#: at the shipped 1/min cadence, i.e. five samples.  It is a constructor
#: argument because the cadence is configurable, and a peer window shorter than
#: two sample intervals would silently disable the whole sibling comparison.
PEER_MAX_AGE_S = 300.0

#: Forgetting expressed as a TIME, not a sample count.  ``lam = exp(-dt/tau)``
#: gives lam = 0.9995 at the shipped 60 s cadence (an effective window of 2000
#: samples = 33 h) and stays correct when the cadence changes or a device
#: reports irregularly.  A fixed lam would make the memory of the estimator
#: depend on how often the radio happened to get through, which is not a
#: property anybody would choose on purpose.
FORGET_TAU_S = 120_000.0

#: Freshness FLOORS.
#:
#: These are the shortest windows the server will ever use.  They are floors and
#: not fixed thresholds, because the interval a device publishes at is a
#: property of the device, not of the server: the shipped node sleeps 900 s in
#: its idle cadence, 60 s when theta is elevated and 10 s in a burst, and a
#: fixed 180 s window would declare a perfectly healthy idle node dead three
#: minutes into a fifteen-minute sleep.  A device that advertises ``dev.period_s``
#: gets a window scaled to its own cadence; one that does not - a legacy feed, a
#: manual snapshot - keeps exactly these numbers.
DEVICE_OFFLINE_S = 180.0
ANALYSER_OFFLINE_S = 180.0
ARC_OFFLINE_S = 180.0

#: How many consecutive publications a device may miss before it is offline.
#:
#: Three, because one lost frame is a normal LoRa outcome at the edge of a
#: substation and two in a row is not rare; three in a row is a node that has
#: stopped, and waiting longer than that costs an operator real time.
DEVICE_MISS_BUDGET = 3

#: How many publish intervals apart two sibling readings may be and still be
#: subtracted from one another.
#:
#: One interval plus jitter is the smallest honest answer: below that, two
#: devices on independent wake schedules can NEVER both be inside the window,
#: and the differential detector - the whole product - is silently disabled at
#: the cadence the node is designed to run at.  It is not free: theta is load
#: normalised (θ = ΔT/f²) and the lug's thermal time constant is about 900 s, so
#: at the idle cadence two sibling readings are a time constant apart and the
#: common-mode cancellation is weaker than it is in a burst.  That is a real
#: limit of running a battery node at 15-minute cadence, and it is stated here
#: rather than hidden inside a constant.
PEER_PERIOD_BUDGET = 2.0

#: A device clock this far from the panel's newest observation is unsynced.
CLOCK_SKEW_S = 300.0

#: Battery percentage below which CELL_LOW is raised.
CELL_LOW_PCT = 15.0

#: Below this the panel is de-energised rather than merely lightly loaded.
DE_ENERGISED_F = 0.01

#: Per-joint RLS/CUSUM state is flushed at most this often.
STATE_SAVE_S = 300.0

#: Total rated current of all non-spare outgoing ways, per phase.  5x250 + 5x400
#: = 3250 A against a 2312 A busbar rating - the usual diversity allowance.
SUM_FEEDER_RATED_A = float(sum(f.rated_a for f in assets.FEEDERS if not f.spare))

#: The device that polls the MPR-63 over RS-485 and republishes ``mpr.*``.
#: It is the mains-powered gateway, so its cadence is independent of every
#: battery node's, and analyser freshness is judged against ITS period.
ANALYSER_DEVICE = "GW-01"

#: Channels that carry a joint temperature, in order of preference.
TEMP_CHANNELS = ("tc.temp_c", "ir.lug_temp_c")
CURRENT_CHANNELS = ("tc.current_a",)


def _sibling_group(j: assets.Joint) -> str:
    """``Joint.sibling_group`` with a guard for the four incoming stubs.

    ``GIRIS-L1..N`` have ``feeder_index = None`` and the contract's property
    formats that index unconditionally, so it raises for them.  We do not own
    ``contracts/assets.py`` and will not edit it; the four roof joints are not
    monitored on day 1 in any case, so we only need a stable label to store.
    Their peer set is genuinely the other three incoming stubs.
    """
    try:
        return j.sibling_group
    except TypeError:
        return f"{j.zone}:{'N' if j.conductor == 'N' else 'GIRIS'}"


# --------------------------------------------------------------------------
# In-memory panel state
# --------------------------------------------------------------------------

def lift_panel_eta(joints: Sequence[JointView]) -> EtaView:
    """Panonun projeksiyonu: hedefi en agir, esitlikte gunu en yakin baglanti.

    Sadece min(gun) almak yanlis olurdu: IZLE'ye 3 gun kalan bir baglanti,
    KRITIK'e 18 gun kalanin onune gecer ve kontrol odasi yanlis panoya bakar.
    ``theta_delta_7d`` EN KOTU baglantidan yukseltilir; bu FARKLI bir anahtarla
    yukseltilir ve ikisi ayni sey degildir.
    """
    ranked = [j.eta for j in joints if j.eta.days is not None and j.eta.target]
    if ranked:
        return max(ranked, key=lambda e: (channels.SEVERITY_RANK.get(e.target, 0),
                                          -(e.days or 0.0)))
    # Hicbir baglanti sayi vermiyor.  Bos donmek gerekceyi kaybettirir ve filo
    # tablosunda operator sebebi sorulamayan bir "—" gorur; gerekce sayinin
    # YERINE yazilan seydir, o yuzden pano duzeyine tasinmak zorunda.
    #
    # Kapilardan EN ILERI gidebilmis baglantinin gerekcesi secilir: bir panoda
    # bir baglanti yalnizca "egim yok" diye susuyorsa panonun dogru cumlesi
    # "burada tirmanan bir baglanti yok"tur, "yetersiz gecmis" degil.
    silent = [j.eta for j in joints if j.eta.reason]
    if not silent:
        return EtaView()
    return max(silent, key=lambda e: hz.GATE_ORDER.get(e.reason, 0))


@dataclass
class _JointRuntime:
    theta: th.ThetaState = field(default_factory=th.ThetaState)
    cusum: cs.CusumState = field(default_factory=cs.CusumState)
    last_theta_ts: float = 0.0
    last_save_ts: float = 0.0
    slope: float = 0.0
    changepoint: float | None = None
    alarm_days: int = 0
    theta_daily: float | None = None
    delta_7d: float = 0.0
    excess_r_uohm: float | None = None
    eta: EtaView = field(default_factory=EtaView)
    note: str = ""


@dataclass
class _PanelRuntime:
    panel_key: str
    last_ts: float = 0.0
    ch: dict[str, tuple[float, float]] = field(default_factory=dict)
    joint_temp: dict[str, dict[str, tuple[float, float]]] = field(default_factory=dict)
    joint_cur: dict[str, tuple[float, float]] = field(default_factory=dict)
    joints: dict[str, _JointRuntime] = field(default_factory=dict)
    devices: dict[str, dict] = field(default_factory=dict)
    wall_c: float | None = None
    wall_ts: float = 0.0
    minutes_below_2: float = 0.0
    minutes_below_0: float = 0.0
    clock_unsynced: bool = False
    h3: dict | None = None
    registered: bool = False
    #: Longest publish interval any device on this panel currently advertises.
    #: 0.0 means nobody has told us, and the fixed floors apply.
    max_period_s: float = 0.0

    def jr(self, key: str) -> _JointRuntime:
        r = self.joints.get(key)
        if r is None:
            r = _JointRuntime()
            self.joints[key] = r
        return r


# --------------------------------------------------------------------------
# The engine
# --------------------------------------------------------------------------


def _decode_detector_map(lo: int, hi: int) -> list[str]:
    """TVOC-2 registers 210/211 -> detector names.

    bit0-9 of the low word are X1:1..X1:10 and bit10-14 are X2:1..X2:5;
    bit0-4 of the high word are X2:6..X2:10 and bit5-14 are X3:1..X3:10.
    Thirty detectors is the documented maximum for one Arc Monitor.
    """
    out: list[str] = []
    for b in range(10):
        if lo & (1 << b):
            out.append(f"X1:{b + 1}")
    for b in range(10, 15):
        if lo & (1 << b):
            out.append(f"X2:{b - 9}")
    for b in range(5):
        if hi & (1 << b):
            out.append(f"X2:{b + 6}")
    for b in range(5, 15):
        if hi & (1 << b):
            out.append(f"X3:{b - 4}")
    return out

class DetectorEngine:
    """Stateful detector for a fleet of panels.

    ``sigma_tc`` and ``sigma_ir`` are the sibling-differential measurement noise
    of a thermal-clip pair and of an IR pixel pair.  They set the detectability
    floor ``theta_min = 3*sigma/f^2`` and therefore the sensitivity percentage,
    so they are constructor arguments rather than constants: a site that
    qualifies its own sensors can put its own measured numbers in.
    """

    def __init__(self, store, *, sigma_tc: float = th.SIGMA_TC_K,
                 sigma_ir: float = th.SIGMA_IR_K,
                 theta_ref_k: float = th.THETA_ALARM_K,
                 peer_max_age_s: float = PEER_MAX_AGE_S,
                 forget_tau_s: float = FORGET_TAU_S,
                 commit_every: int = 1, persist_samples: bool = True) -> None:
        self.store = store
        self.sigma_tc = float(sigma_tc)
        self.sigma_ir = float(sigma_ir)
        self.theta_ref_k = float(theta_ref_k)
        self.peer_max_age_s = float(peer_max_age_s)
        self.forget_tau_s = float(forget_tau_s)
        self.commit_every = max(1, int(commit_every))
        self.persist_samples = bool(persist_samples)

        self.seq = SeqTracker()
        self.observed = 0
        self.rejected = 0            #: samples failing channels.validate()
        self._pending = 0
        self._panels: dict[str, _PanelRuntime] = {}
        self._device_kind = {d.key: d.kind for d in assets.DEVICES}
        self._tc_joints = {
            j for d in assets.DEVICES if d.kind == "TC" for j in d.covers
        }
        self._load_states()

    # ------------------------------------------------------------ state ---

    def _load_states(self) -> None:
        """Restore RLS and CUSUM state for every joint the store knows about."""
        for row in self.store.joint_states():
            pk = row["panel_key"]
            pr = self._panels.get(pk)
            if pr is None:
                pr = _PanelRuntime(panel_key=pk)
                pr.registered = True
                self._panels[pk] = pr
            jr = pr.jr(row["joint_key"])
            jr.theta = th.ThetaState.from_row(row)
            jr.cusum = cs.CusumState.from_row(row)
            jr.slope = float(row.get("slope") or 0.0)
            jr.changepoint = row.get("changepoint")
            jr.alarm_days = int(row.get("alarm_days") or 0)
            jr.excess_r_uohm = row.get("excess_r_uohm")

    def _pr(self, panel_key: str) -> _PanelRuntime:
        pr = self._panels.get(panel_key)
        if pr is None:
            pr = _PanelRuntime(panel_key=panel_key)
            self._panels[panel_key] = pr
        return pr

    def _save_joint_state(self, panel_key: str, joint_key: str, jr: _JointRuntime) -> None:
        row: dict[str, Any] = {}
        row.update(jr.theta.to_row())
        row.update(jr.cusum.to_row())
        # ``train_n`` is owned by the CUSUM (it is the training-day counter);
        # the RLS sample counter would collide, so it is not persisted.  The RLS
        # only needs n > 0 to know it is past its cold start, which is implied by
        # a non-zero covariance history.
        row["train_n"] = jr.cusum.n
        row["slope"] = jr.slope
        row["changepoint"] = jr.changepoint
        row["alarm_days"] = jr.alarm_days
        row["excess_r_uohm"] = jr.excess_r_uohm
        self.store.save_joint_state(panel_key, joint_key, row)

    # ---------------------------------------------------------- register --

    def _register_panel(self, env: Envelope) -> None:
        pk = env.panel_key
        pr = self._pr(pk)
        if pr.registered:
            return
        pr.registered = True
        if self.store.panel(pk) is None:
            existing = self.store.panels()
            index = max((int(p["panel_index"]) for p in existing), default=0) + 1
            dso, lat, lon = "", 0.0, 0.0
            for site, d, la, lo in assets.FLEET_SITES:
                if site.lower() == env.site.lower():
                    dso, lat, lon = d, la, lo
                    break
            self.store.upsert_panel(
                panel_key=pk, panel_index=index, site=env.site, name=pk,
                dso=dso, lat=lat, lon=lon, rated_kva=assets.RATED_KVA,
                commissioned=env.ts, learn_until=env.ts + 7 * DAY_S,
                has_analyser=1, has_arc_relay=1, arc_detectors=10,
            )
        for j in assets.JOINTS:
            self.store.upsert_joint(
                panel_key=pk, joint_key=j.key, label=j.label, zone=j.zone,
                conductor=j.conductor, feeder_index=j.feeder_index,
                rated_a=j.rated_a, sibling_group=_sibling_group(j),
                monitored=1 if j.zone in assets.MONITORED_ZONES else 0,
                x_mm=j.x_mm, y_mm=j.y_mm,
            )
        for d in assets.DEVICES:
            self.store.upsert_device(panel_key=pk, device_key=d.key, kind=d.kind,
                                     label=d.label)
        self.store.commit()

    # ------------------------------------------------------------ ingest --

    def observe(self, env: Envelope) -> None:
        """Ingest one envelope: persist it, update state, advance theta."""
        pk = env.panel_key
        self._register_panel(env)
        pr = self._pr(pk)
        if is_stale(self.seq.check(env)):
            # A redelivered or replayed envelope.  Everything it carries has
            # already been folded into the live image, the RLS and the freshness
            # clocks once.  Applying it a second time would walk the live value
            # backwards to whatever the panel was doing at the older instant,
            # double-count one physical sample in the estimator, and - worst -
            # make a stale reading look fresh.  It is counted, not applied.
            return
        self.observed += 1

        # A device whose clock disagrees with the rest of the panel is a real
        # field failure (the RTC backup cell dies long before the primary does)
        # and it silently corrupts every time-based statistic, so it is a flag.
        if pr.last_ts and (pr.last_ts - env.ts) > CLOCK_SKEW_S:
            pr.clock_unsynced = True
        pr.last_ts = max(pr.last_ts, env.ts)

        dev = pr.devices.setdefault(env.device, {"faults": []})
        dev["last_seen"] = env.ts
        dev["boot"] = env.boot
        dev["seq"] = env.seq
        if env.fw:
            dev["fw"] = env.fw
        if env.kind == "birth":
            dev["metrics"] = list(env.metrics)
            dev["faults"] = []
        elif env.kind == "death":
            dev["last_seen"] = env.ts
            dev["offline"] = True
            return
        if env.kind != "death":
            dev["offline"] = False
        faults = env.event.get("faults")
        if isinstance(faults, list):
            dev["faults"] = [str(f) for f in faults]
        if env.event.get("clock_unsynced"):
            pr.clock_unsynced = True

        # ---- panel-level channels ---------------------------------------
        rows: list[tuple[float, str, str, float]] = []
        for name, value in env.values.items():
            try:
                v = float(value)
            except (TypeError, ValueError):
                self.rejected += 1
                continue
            if not channels.validate(name, v):
                # Out-of-range at the edge, not silently absorbed into a
                # baseline.  A stuck or garbage sensor is caught here.
                self.rejected += 1
                continue
            pr.ch[name] = (env.ts, v)
            if name in ("dev.rssi_dbm", "dev.battery_v", "dev.battery_pct",
                        "dev.temp_mcu_c", "dev.uptime_s", "dev.period_s"):
                dev[name] = v
                if name == "dev.period_s":
                    pr.max_period_s = max(
                        (float(s["dev.period_s"]) for s in pr.devices.values()
                         if s.get("dev.period_s")), default=0.0)
            rows.append((env.ts, pk, name, v))
        if rows and self.persist_samples:
            self.store.add_samples(rows)

        # ---- environment: wall temperature and condensation dwell --------
        self._update_environment(pr, env.ts)

        # ---- per-joint channels ------------------------------------------
        jrows: list[tuple[float, str, str, str, float]] = []
        touched: list[str] = []
        for jkey, vals in env.joints.items():
            if jkey not in assets.JOINTS_BY_KEY:
                self.rejected += 1
                continue
            for name, value in vals.items():
                try:
                    v = float(value)
                except (TypeError, ValueError):
                    self.rejected += 1
                    continue
                if not channels.validate(name, v):
                    self.rejected += 1
                    continue
                jrows.append((env.ts, pk, jkey, name, v))
                if name in TEMP_CHANNELS:
                    pr.joint_temp.setdefault(jkey, {})[name] = (env.ts, v)
                    if name == self._drives(jkey):
                        touched.append(jkey)
                elif name in CURRENT_CHANNELS:
                    pr.joint_cur[jkey] = (env.ts, v)
        if jrows and self.persist_samples:
            self.store.add_joint_samples(jrows)

        for jkey in touched:
            self._advance_theta(pr, jkey, env.ts, jrows)

        self._pending += 1
        if self._pending >= self.commit_every:
            self.store.commit()
            self._pending = 0

    # ------------------------------------------------------------- theta --

    # ------------------------------------------------------- freshness ----

    def _device_period(self, pr: _PanelRuntime, device_key: str) -> float | None:
        """What interval this device says it publishes at, or None if it never said."""
        p = (pr.devices.get(device_key) or {}).get("dev.period_s")
        return float(p) if p else None

    def _online_window(self, pr: _PanelRuntime, device_key: str) -> float:
        """How long silence from this device is still normal."""
        p = self._device_period(pr, device_key)
        if p is None:
            return DEVICE_OFFLINE_S
        return max(DEVICE_OFFLINE_S, DEVICE_MISS_BUDGET * p)

    def _analyser_window(self, pr: _PanelRuntime) -> float:
        """Freshness window for ``mpr.*``.

        The analyser is read over RS-485 by the mains-powered gateway, so its
        cadence is the GATEWAY's, not a battery node's, and it is a separate
        question from whether any given clip is awake.
        """
        p = self._device_period(pr, ANALYSER_DEVICE)
        if p is None:
            return ANALYSER_OFFLINE_S
        return max(ANALYSER_OFFLINE_S, DEVICE_MISS_BUDGET * p)

    def _peer_window(self, pr: _PanelRuntime) -> float:
        """How far apart two sibling readings may be and still be subtracted."""
        if pr.max_period_s <= 0.0:
            return self.peer_max_age_s
        return max(self.peer_max_age_s, PEER_PERIOD_BUDGET * pr.max_period_s)

    def _drives(self, joint_key: str) -> str:
        """Which channel is allowed to advance theta for this joint.

        A clip-covered joint is seen by two sensors, and letting both drive the
        estimator would fold the same physical instant in twice with a zero time
        step.  The better sensor wins: the clip for the six joints that have one,
        the IR array for the other thirty-four.
        """
        return "tc.temp_c" if joint_key in self._tc_joints else "ir.lug_temp_c"

    def _sigma_for(self, joint_key: str) -> float:
        """Which measurement noise applies to this joint.

        A joint covered by a thermal clip is measured by a TMP117 pair
        (sigma 0.2 K); everything else is an MLX90640 pixel pair (0.8 K).  Using
        the right one per joint is what makes the sensitivity number honest -
        quoting the clip figure for an IR-only lug would overstate coverage by a
        factor of four in theta_min.
        """
        return self.sigma_tc if joint_key in self._tc_joints else self.sigma_ir

    def _load_factor(self, pr: _PanelRuntime, joint: assets.Joint,
                     ts: float) -> tuple[float, bool]:
        """``(f, measured)`` - load factor and whether it came from a real CT."""
        cur = pr.joint_cur.get(joint.key)
        if cur is not None and ts - cur[0] <= self._peer_window(pr) and joint.rated_a > 0:
            return (cur[1] / joint.rated_a, True)
        chan = {
            "L1": "mpr.i_l1_a", "L2": "mpr.i_l2_a", "L3": "mpr.i_l3_a",
            "N": "mpr.i_n_a",
        }.get(joint.conductor)
        got = pr.ch.get(chan) if chan else None
        if got is None or ts - got[0] > max(self._analyser_window(pr),
                                            self._peer_window(pr)):
            return (0.0, False)
        return (got[1] / SUM_FEEDER_RATED_A, False)

    def _advance_theta(self, pr: _PanelRuntime, jkey: str, ts: float,
                       jrows: list) -> None:
        joint = assets.JOINTS_BY_KEY[jkey]
        if joint.zone not in assets.MONITORED_ZONES:
            return
        jr = pr.jr(jkey)
        dt_s = ts - jr.last_theta_ts if jr.last_theta_ts else 0.0
        jr.last_theta_ts = ts
        f, measured = self._load_factor(pr, joint, ts)

        if joint.conductor == "N":
            excess = self._neutral_excess(pr, jkey, ts)
            jr.note = ("nötr: kardeş karşılaştırması geçersiz, "
                       "kural H3 ile değerlendirilir")
        else:
            got = self._sibling_excess(pr, jkey, ts)
            if got is None:
                return
            excess = got[0]
            jr.note = "" if measured else "akım fider bazında ölçülmüyor; pano faz akımından oransal tahmin"
        if excess is None:
            return

        step = dt_s if dt_s > 0.0 else 60.0
        jr.theta = th.rls_update(jr.theta, excess, f, step,
                                 lam=math.exp(-step / self.forget_tau_s))

        sigma = self._sigma_for(jkey)
        tmin = th.theta_min(sigma, f)
        lo, mid, hi = th.excess_resistance_uohm(jr.theta.theta, joint.rated_a)
        jr.excess_r_uohm = mid
        if self.persist_samples:
            self.store.add_joint_samples([
                (ts, pr.panel_key, jkey, "det.theta_k", jr.theta.theta),
                (ts, pr.panel_key, jkey, "det.theta_min_k",
                 min(tmin, 1000.0) if math.isfinite(tmin) else 1000.0),
                (ts, pr.panel_key, jkey, "det.sensitivity_pct",
                 th.sensitivity_pct(self.theta_ref_k, sigma, f)),
            ])
        if ts - jr.last_save_ts >= STATE_SAVE_S:
            jr.last_save_ts = ts
            self._save_joint_state(pr.panel_key, jkey, jr)

    def _temp(self, pr: _PanelRuntime, jkey: str, ts: float) -> float | None:
        """Effective temperature of one joint: the freshest of its two sensors.

        A joint covered by a thermal clip has two independent readings - the
        clip's TMP117 and the IR array's pixel.  We take whichever is fresher,
        breaking a tie towards the clip because it is the better sensor
        (0.2 K against 0.8 K on the pair difference).  Taking the freshest
        rather than always preferring the clip matters: it keeps every sibling
        comparison between readings taken at the SAME instant, and that
        simultaneity is exactly what the common-mode cancellation depends on.
        """
        got = pr.joint_temp.get(jkey)
        if not got:
            return None
        best = None
        for name in TEMP_CHANNELS:
            v = got.get(name)
            if v is None or ts - v[0] > self._peer_window(pr):
                continue
            if best is None or v[0] > best[0]:
                best = v
        return best[1] if best is not None else None

    def _sibling_excess(self, pr: _PanelRuntime, jkey: str,
                        ts: float) -> tuple[float, float] | None:
        temps: dict[str, float] = {}
        for k in pr.joint_temp:
            v = self._temp(pr, k, ts)
            if v is not None:
                temps[k] = v
        return th.sibling_excess(temps, jkey)

    def _neutral_excess(self, pr: _PanelRuntime, jkey: str, ts: float) -> float | None:
        """Neutral rise, referenced to the compartment air.

        The neutral has no valid sibling: the three phases carry a different
        current, and the other nine neutrals carry unknown per-feeder currents.
        So this one measurement is NOT ambient-cancelling, and we do not pretend
        it is.  That is precisely why rule H3 compares K_N against the neutral's
        OWN baseline as a RATIO - a slow ambient bias moves the numerator and
        the baseline together and divides out, whereas an absolute threshold on
        dT_N would drift with the season.
        """
        t = self._temp(pr, jkey, ts)
        if t is None:
            return None
        air = pr.ch.get("env.air_c") or pr.ch.get("ir.air_top_c")
        if air is None or ts - air[0] > max(self._analyser_window(pr),
                                            self._peer_window(pr)):
            return None
        return t - air[1]

    # ------------------------------------------------------- environment --

    def _update_environment(self, pr: _PanelRuntime, ts: float) -> None:
        air = pr.ch.get("env.air_c")
        rh = pr.ch.get("env.rh_pct")
        if air is None or rh is None:
            return
        dt_s = ts - pr.wall_ts if pr.wall_ts else 0.0
        pr.wall_c = dp.wall_temp(pr.wall_c, air[1], dt_s)
        pr.wall_ts = ts
        td = dp.dewpoint_c(air[1], rh[1])
        margin = dp.condensation_margin(pr.wall_c, td)
        pr.ch["env.dewpoint_c"] = (ts, td)
        pr.ch["env.wall_c"] = (ts, pr.wall_c)
        pr.ch["env.condensation_margin_k"] = (ts, margin)
        mins = dt_s / 60.0 if 0.0 < dt_s <= 3600.0 else 0.0
        pr.minutes_below_2 = pr.minutes_below_2 + mins if margin < dp.MARGIN_WATCH_K else 0.0
        pr.minutes_below_0 = pr.minutes_below_0 + mins if margin < 0.0 else 0.0

    # ---------------------------------------------------------- rollup ----

    def roll_daily(self, now: float, *, days_back: int = 3,
                   panel_key: str | None = None) -> int:
        """Write ``joint_daily`` medians and recompute the drift statistics.

        Returns the number of ``joint_daily`` rows written.  Idempotent: running
        it twice over the same window produces the same table.

        ``days_back`` covers the current day plus enough history to repair a gap
        left by a restart; the demo and the tests pass a larger number to build
        a whole history in one call.
        """
        written = 0
        keys = [panel_key] if panel_key else [p["panel_key"] for p in self.store.panels()]
        day_now = int(now // DAY_S)
        since = (day_now - days_back + 1) * DAY_S
        for pk in keys:
            rows = self.store.query(
                "SELECT ts, joint_key, channel, value FROM joint_sample "
                "WHERE panel_key=? AND ts>=? AND channel IN "
                "('det.theta_k','det.theta_min_k','det.sensitivity_pct') ORDER BY ts",
                (pk, since),
            )
            buckets: dict[tuple[int, str], dict[str, list[float]]] = {}
            for r in rows:
                key = (int(r["ts"] // DAY_S), r["joint_key"])
                buckets.setdefault(key, {}).setdefault(r["channel"], []).append(r["value"])
            for (day, jkey), chans in sorted(buckets.items()):
                thetas = chans.get("det.theta_k") or []
                if not thetas:
                    continue
                s = sorted(thetas)
                n = len(s)
                p90 = s[min(n - 1, int(0.9 * (n - 1) + 0.5))]
                sens = chans.get("det.sensitivity_pct") or []
                tmins = chans.get("det.theta_min_k") or []
                sigma = self._sigma_for(jkey)
                # theta_min = 3*sigma/f^2 inverts exactly to f, so the daily mean
                # load factor needs no extra stored channel.
                loads = [math.sqrt(3.0 * sigma / t) for t in tmins if t > 0]
                self.store.upsert_joint_daily(
                    day, pk, jkey,
                    theta_med=float(median(s)), theta_p90=float(p90), n=n,
                    load_mean=float(median(loads)) if loads else 0.0,
                    sens_pct=float(median(sens)) if sens else 0.0,
                    # Gorulebilirlik tabaninin KENDISI.  Sema bu kolonu bastan
                    # tanimliyordu ama rollup onu atliyordu: tmins yalniz
                    # load_mean'i turetmek icin okunuyordu.  Ufuk projeksiyonu
                    # "bu esik bu yukte gorunur mu" sorusunu bu kolona soruyor,
                    # yuzdeye degil.
                    theta_min=float(median(tmins)) if tmins else None,
                )
                written += 1
            self._refresh_stats(pk, now)
        self.store.commit()
        return written

    def _refresh_stats(self, panel_key: str, now: float, history_days: int = 180) -> None:
        """Recompute CUSUM, slope, changepoint and the alarm-day counter.

        Recomputed from ``joint_daily`` rather than carried incrementally, so
        the whole drift argument for any joint can be reproduced from a table
        the operator can SELECT.  An eight-month-old incremental statistic that
        nobody can re-derive is not evidence.
        """
        pr = self._pr(panel_key)
        for j in assets.monitored_joints():
            rows = self.store.joint_daily(panel_key, j.key, history_days)
            if not rows:
                continue
            rows = sorted(rows, key=lambda r: r["day"])
            days = [float(r["day"]) * DAY_S for r in rows]
            vals = [float(r["theta_med"] or 0.0) for r in rows]
            jr = pr.jr(j.key)
            if j.conductor == "N":
                # The neutral's series is K_N in kelvin-at-rating units.  A CUSUM
                # on it would be meaningless: I_N does not track I_phase, so the
                # series moves with the load mix rather than with the joint, and
                # a sigma-floored CUSUM would fire on the first load transfer.
                # What rule H3 needs from history is a ROBUST BASELINE, so that
                # is all we keep.
                train = vals[:cs.DEFAULT_TRAIN_DAYS] or vals
                jr.cusum = cs.CusumState(n=len(train),
                                         baseline=float(median(train)))
                jr.theta_daily = vals[-1]
                jr.slope = cp.slope_per_week(vals, days)
                jr.changepoint = None
                jr.alarm_days = 0
                jr.delta_7d = cp.theta_delta(vals, days, 7.0)
                jr.eta = hz.project([], [], [], THETA_ABS_LADDER,
                                    conductor="N")
                self._save_joint_state(panel_key, j.key, jr)
                continue
            st = cs.CusumState()
            fired_flags: list[bool] = []
            cusum_trail: list[float] = []
            for v in vals:
                st, fired = cs.cusum_update(st, v)
                fired_flags.append(fired)
                cusum_trail.append(st.pos)
            jr.cusum = st
            # Write the CUSUM back onto each day so the evidence screen can plot
            # the statistic over the whole retained history, not just over the
            # window where raw samples still exist.
            for day_i, day_ts in enumerate(days):
                self.store.upsert_joint_daily(
                    int(day_ts // DAY_S), panel_key, j.key,
                    cusum=cusum_trail[day_i],
                    baseline=st.baseline,
                )
            jr.theta_daily = vals[-1]
            jr.slope = cp.slope_per_week(vals, days)
            jr.changepoint = cp.detect_changepoint(vals, days)
            jr.delta_7d = cp.theta_delta(vals, days, 7.0)
            # Qualify on the RISE above this joint's own baseline, or on an
            # absolute level high enough to stand on its own.  See the note on
            # QUALIFY_RISE_K: judging only the absolute level lets a joint's
            # manufacturing offset decide how sick it has to get before anyone
            # is told, which is not a property we want the product to have.
            base = st.baseline if st.baseline is not None else 0.0
            tail = list(zip(fired_flags, vals))[-cs.QUALIFY_OF_LAST:]
            jr.alarm_days = sum(
                1 for f, v in tail
                if f and (v - base >= cs.QUALIFY_RISE_K or v >= cs.QUALIFY_THETA_K)
            )
            # Ufuk, gunluk tablonun GECERLI satirlarindan hesaplanir.  ``vals``
            # yukarida None'lari 0.0'a cevirdigi icin yeniden kullanilamaz: bos
            # bir gunu 0 K olarak okumak, olmayan bir gunu olculmus saymaktir.
            #
            # theta_min bilinmiyorsa ``inf`` gecilir, yani kapi "gorunurluk
            # dusuk" tarafina duser.  Bilmedigimiz bir tabanla esigin gorunur
            # oldugunu IDDIA ETMEYIZ.
            ok = [r for r in rows
                  if (r.get("n") or 0) > 0 and r.get("theta_med") is not None]
            jr.eta = hz.project(
                [float(r["theta_med"]) for r in ok],
                [float(r["day"]) * DAY_S for r in ok],
                [float(r["theta_min"]) if r.get("theta_min") is not None
                 else float("inf") for r in ok],
                THETA_ABS_LADDER,
                conductor=j.conductor,
            )
            self._save_joint_state(panel_key, j.key, jr)

    # ------------------------------------------------------------ evaluate -

    def evaluate_all(self, now: float) -> list[PanelLive]:
        return [self.evaluate(p["panel_key"], now) for p in self.store.panels()]

    def evaluate(self, panel_key: str, now: float) -> PanelLive:
        """Build the live image.  Everything except fusion, policy and alarms."""
        row = self.store.panel(panel_key) or {}
        pr = self._pr(panel_key)

        live = PanelLive(
            panel_key=panel_key,
            panel_index=int(row.get("panel_index") or 0),
            site=str(row.get("site") or ""),
            name=str(row.get("name") or panel_key),
            dso=str(row.get("dso") or ""),
            lat=float(row.get("lat") or 0.0),
            lon=float(row.get("lon") or 0.0),
            ts=now,
        )
        live.data_age_s = max(0.0, now - pr.last_ts) if pr.last_ts else 1e9

        learn_until = row.get("learn_until")
        live.learn_until = float(learn_until) if learn_until is not None else None
        live.learn_mode = bool(live.learn_until and now < live.learn_until)

        # ---- analyser ----------------------------------------------------
        live.analyser_fitted = bool(int(row.get("has_analyser", 1) or 0))
        an: dict[str, float] = {}
        an_fresh = False
        for c in channels.CHANNELS:
            if not c.name.startswith("mpr."):
                continue
            got = pr.ch.get(c.name)
            if got is None:
                continue
            an[c.name] = got[1]
            if now - got[0] <= self._analyser_window(pr):
                an_fresh = True
        live.analyser = an
        online_flag = pr.ch.get("mpr.online")
        live.analyser_online = bool(
            an_fresh and (online_flag is None or online_flag[1] >= 0.5)
        )

        phases = [an.get(f"mpr.i_l{p}_a", 0.0) for p in (1, 2, 3)]
        i_mean = sum(phases) / 3.0 if phases else 0.0
        live.load_factor = i_mean / assets.MAIN_BUSBAR_RATED_A
        live.feeder_load_factor = i_mean / SUM_FEEDER_RATED_A if SUM_FEEDER_RATED_A else 0.0

        # ---- environment -------------------------------------------------
        env_out: dict[str, float] = {}
        for name in ("env.air_c", "env.rh_pct", "env.dewpoint_c", "env.wall_c",
                     "env.condensation_margin_k", "ir.air_top_c"):
            got = pr.ch.get(name)
            if got is not None:
                env_out[name] = got[1]
        live.env = env_out

        # ---- neutral rule H3 (before the joint loop: the neutral views
        #      carry its verdict, and the neutral has no theta of its own) ---
        pr.h3 = self._run_h3(pr, live, now)

        # ---- joints ------------------------------------------------------
        views: list[JointView] = []
        theta_max, theta_max_joint = 0.0, None
        for j in assets.JOINTS:
            monitored = j.zone in assets.MONITORED_ZONES
            jv = JointView(
                key=j.key, label=j.label, zone=j.zone, conductor=j.conductor,
                feeder_index=j.feeder_index, rated_a=j.rated_a,
                monitored=monitored, x_mm=j.x_mm, y_mm=j.y_mm, severity="BILGI",
            )
            if not monitored:
                jv.note = "izlenmiyor · canlı bara bölmesi, gün 1 kapsamı dışında"
                # Susmanin her zaman bir kodu vardir.  Bos bir EtaView "reason
                # bossa sayi gecerlidir" sozlesmesini bozardi.
                jv.eta = EtaView(reason=hz.REASON_UNMONITORED)
                views.append(jv)
                continue

            jr = pr.jr(j.key)
            t = self._temp(pr, j.key, now)
            if t is not None:
                jv.temp_c = t
            cur = pr.joint_cur.get(j.key)
            if cur is not None:
                jv.current_a = cur[1]
            f, measured = self._load_factor(pr, j, now)
            jv.load_factor = f
            sigma = self._sigma_for(j.key)
            jv.theta_min_k = th.theta_min(sigma, f)
            jv.sensitivity_pct = th.sensitivity_pct(self.theta_ref_k, sigma, f)

            if j.conductor == "N":
                # The neutral has NO phase-differential theta and we do not
                # invent one.  Its excess is measured against the compartment
                # air, which is a different quantity on a different scale (it
                # contains the conductor's own I^2R, not just the joint's), and
                # putting that number in ``theta_k`` would make the panel's
                # worst-theta line meaningless.  What the neutral has instead is
                # K_N = dT/I^2 judged against its own baseline - rule H3.
                jv.slope_k_per_week = jr.slope
                jv.baseline_k = jr.cusum.baseline
                jv.eta = jr.eta
                jv.severity, jv.note = self._neutral_severity(jv, pr.h3)
                views.append(jv)
                continue

            if jr.theta.n > 0:
                jv.theta_k = jr.theta.theta
                lo, mid, hi = th.excess_resistance_uohm(jr.theta.theta, j.rated_a)
                jv.excess_r_lo_uohm, jv.excess_r_uohm, jv.excess_r_hi_uohm = lo, mid, hi
            if t is not None:
                got = self._sibling_excess(pr, j.key, now)
                if got is not None:
                    jv.sibling_median_c = got[1]
            jv.cusum = jr.cusum.pos
            jv.baseline_k = jr.cusum.baseline
            if jv.theta_k is not None and jr.cusum.baseline is not None:
                jv.theta_rise_k = jv.theta_k - jr.cusum.baseline
            jv.slope_k_per_week = jr.slope
            jv.changepoint_ts = jr.changepoint
            jv.alarm_days = jr.alarm_days
            jv.eta = jr.eta
            jv.note = jr.note
            jv.severity = self._joint_severity(jv, jr, live.learn_mode)
            views.append(jv)
        live.joints = views
        live.eta = lift_panel_eta(views)

        # THE WORST JOINT IS NOT SIMPLY THE LARGEST THETA.
        #
        # An uninstrumented lug watched only by the IR array has sibling noise
        # of 0.8 K, so at a load factor of 0.3 its detectability floor is
        # 3*0.8/0.09 = 27 K.  A 5 K reading there is noise, not a finding, and
        # ranking on raw theta lets that noise outrank a real, confirmed 1.5 K
        # drift on a clip-instrumented joint.  A judge who clicks the panel's
        # "worst" joint and lands on a feeder we do not even measure the current
        # of has found a hole in the product, not a bug in a chart.
        #
        # So rank on evidence: severity first, then confirmed drift, then how
        # many detectability units the absolute reading actually clears.
        def rank_key(v: JointView) -> tuple:
            jrv = pr.jr(v.key)
            # Same rule as the severity ladder: rank on the daily median, which
            # has already averaged the sibling noise down, not on the live
            # sample that produced it.
            theta = jrv.theta_daily
            if theta is None:
                theta = v.theta_k if v.theta_k is not None else 0.0
            tmin = v.theta_min_k if v.theta_min_k else float("inf")
            visible = theta / tmin if tmin and tmin != float("inf") else 0.0
            confirmed_rise = v.theta_rise_k if (v.theta_rise_k and v.cusum > cs.DEFAULT_H) else 0.0
            return (channels.SEVERITY_RANK.get(v.severity, 0),
                    confirmed_rise, visible, theta)

        worst = max(views, key=rank_key, default=None)
        # A joint only becomes "the worst joint" on EVIDENCE: either it earned a
        # severity above BILGI (its daily median cleared the detectability
        # floor), or its drift is CUSUM-confirmed.  Merely being the largest of
        # forty noisy numbers is not evidence of anything.
        if worst is not None and (rank_key(worst)[0] > 0 or rank_key(worst)[1] > 0):
            live.theta_max = worst.theta_k or 0.0
            live.theta_max_joint = worst.key
            live.theta_delta_7d = pr.jr(worst.key).delta_7d
        else:
            # NOTHING CLEARS A FLOOR OR A CUSUM ANYWHERE ON THIS PANEL.
            #
            # Reporting the largest raw reading here would be actively
            # misleading.  On a lightly loaded panel the IR-only lugs sit
            # around 19 K of pure sibling noise against a 28 K floor, and a
            # fleet screen showing "theta_max 19 K" next to a health index of
            # 98 invites exactly the question we would then have to explain
            # away.  The honest answer is that there is no visible finding,
            # and SENSITIVITY_LOW already carries the reason why.
            live.theta_max = 0.0
            live.theta_max_joint = None
            live.theta_delta_7d = 0.0

        # Panel sensitivity is the CLIP figure at the estimated feeder load: it is
        # the best coverage we have anywhere in the panel, and the per-joint
        # numbers above say where it is worse.
        live.sensitivity_pct = th.sensitivity_pct(
            self.theta_ref_k, self.sigma_tc, live.feeder_load_factor
        )

        # ---- devices -----------------------------------------------------
        live.devices = self._device_views(pr, panel_key, now)

        # ---- arc and PD --------------------------------------------------
        live.arc = self._arc_view(pr, row, now)
        live.pd = self._pd_view(pr, panel_key, now)

        # ---- observational status flags ---------------------------------
        live.status_flags = self._status_flags(pr, live, now)

        return live

    # --------------------------------------------------------- severity ---

    def _joint_severity(self, jv: JointView, jr: _JointRuntime,
                        learn_mode: bool) -> str:
        """Per-joint observational severity.

        The absolute temperature limits come first and are NEVER gated by the
        learn window or by the CUSUM training state.  Everything below them is
        a theta judgement and is capped at IZLE while the panel is still
        learning, because a baseline built from fourteen days of an unknown
        joint is not yet evidence.
        """
        if jv.temp_c is not None:
            if jv.temp_c >= T_JOINT_ACIL_C:
                return "ACIL"
            if jv.temp_c >= T_JOINT_KRITIK_C:
                return "KRITIK"

        theta = jv.theta_k
        if theta is None:
            return "BILGI"

        rank = channels.SEVERITY_RANK

        # --- path 1: absolute theta, graded on IR thermography practice -----
        # JUDGE THE DAILY MEDIAN, NOT THE LIVE SAMPLE.
        #
        # A fleet of 112 panels carries about 4 500 monitored joints.  A single
        # instantaneous reading three sigma from its siblings therefore happens
        # somewhere every few minutes by construction, and on an IR-only lug at
        # half load that noise is worth roughly 10 K of theta.  Grading the live
        # sample would mean the fleet screen was permanently decorated with
        # findings that evaporate on the next poll.
        #
        # The daily median of ~16 samples cuts that noise by sqrt(16) = 4, which
        # is precisely why every drift statistic in this system runs on it.  The
        # live theta stays on the operator's screen because it is what the
        # sensor actually says; the daily median is what gets a severity.
        # THE ABSOLUTE PATH IS FOR CLIP-INSTRUMENTED JOINTS ONLY.
        #
        # A clip measures its own conductor with a TMP117 and its own current
        # with its own split-core CT, giving 0.2 K of sibling-differential
        # noise.  The IR array measures a lug cluster from 0.4 m away and is
        # differenced against its own neighbours, giving 0.8 K - and theta
        # divides by the square of the load factor, so on a feeder running at
        # 27 % of its DSYA rating that 0.8 K becomes 11 K of theta per sigma.
        # There is no absolute theta threshold that is both above that floor and
        # below a real defect, so grading IR-only joints on absolute theta would
        # mean decorating healthy panels with 20 K findings that no physics
        # supports: a genuine 3 microohm spread between healthy joints is worth
        # about 1.4 K at rated current, not twenty.
        #
        # The array still earns its place, on the DRIFT path, where the joint's
        # own baseline absorbs the offset and the daily median averages the
        # noise down.  That is what "the array is used only differentially"
        # means in code.
        sev_abs = "BILGI"
        robust = jr.theta_daily if jr.theta_daily is not None else theta
        tmin = jv.theta_min_k if jv.theta_min_k is not None else float("inf")
        if jv.key in self._tc_joints and robust > tmin:
            theta = robust
            if theta >= THETA_ABS_ACIL_K:
                sev_abs = "ACIL"
            elif theta >= THETA_ABS_KRITIK_K:
                sev_abs = "KRITIK"
            elif theta >= THETA_ABS_UYARI_K:
                sev_abs = "UYARI"
            elif theta >= THETA_ABS_IZLE_K:
                sev_abs = "IZLE"

        # --- path 2: drift above this joint's own baseline -------------------
        # No instantaneous floor applies here.  The statistic is the daily
        # median, whose noise is smaller by sqrt(n), and the CUSUM supplies the
        # confidence.  This is the path that buys weeks of warning, and it is
        # deliberately able to fire on a defect that no single sample could see.
        sev_drift = "BILGI"
        rise = jv.theta_rise_k
        confirmed = (jr.cusum.pos > cs.DEFAULT_H
                     and jr.alarm_days >= cs.QUALIFY_NEEDED)
        if rise is not None and confirmed:
            if rise >= THETA_RISE_KRITIK_K:
                sev_drift = "KRITIK"
            elif rise >= THETA_RISE_UYARI_K:
                sev_drift = "UYARI"
            elif rise >= THETA_RISE_IZLE_K:
                sev_drift = "IZLE"

        sev = sev_abs if rank[sev_abs] >= rank[sev_drift] else sev_drift

        # A confirmed, fast drift promotes the verdict one step. Capped at
        # KRITIK: ACIL belongs to facts, not to extrapolations.
        if (confirmed and rank[sev] >= rank["IZLE"]
                and jv.slope_k_per_week >= SLOPE_ESCALATE_K_PER_WEEK
                and rank[sev] < rank["KRITIK"]):
            sev = channels.SEVERITIES[rank[sev] + 1]

        if learn_mode and rank[sev] > rank["IZLE"]:
            sev = "IZLE"
        return sev

    def _neutral_severity(self, jv: JointView, h3: dict | None) -> tuple[str, str]:
        """Severity and note for a neutral lug.

        Absolute limits first, as everywhere.  Below them the verdict comes from
        rule H3, never from the phase-peer path.  A bad neutral joint is UYARI
        (it gets worse on its own and nothing else in the panel is watching it);
        harmonic loading is IZLE (real, but a planning item, not a failure).
        """
        if jv.temp_c is not None:
            if jv.temp_c >= T_JOINT_ACIL_C:
                return "ACIL", "Mutlak sıcaklık sınırı aşıldı."
            if jv.temp_c >= T_JOINT_KRITIK_C:
                return "KRITIK", "Mutlak sıcaklık sınırı aşıldı."
        if not h3 or h3.get("joint_key") != jv.key:
            return "BILGI", ("nötr: kardeş karşılaştırması geçersiz, "
                             "kural H3 ile değerlendirilir")
        verdict = h3.get("verdict")
        if verdict == "kotu_notr_baglanti":
            return "UYARI", h3["reason_tr"]
        if verdict == "harmonik_yuk":
            return "IZLE", h3["reason_tr"]
        return "BILGI", h3.get("reason_tr") or (
            "nötr: kardeş karşılaştırması geçersiz, kural H3 ile değerlendirilir")

    # --------------------------------------------------------------- H3 ---

    def _run_h3(self, pr: _PanelRuntime, live: PanelLive, now: float) -> dict | None:
        an = live.analyser
        i_n = an.get("mpr.i_n_a")
        if i_n is None:
            return None
        phases = [an.get(f"mpr.i_l{p}_a", 0.0) for p in (1, 2, 3)]
        # The MPR-53CS does report current angles (registers 66/68/70,
        # multiplier 1 = degrees), but the frozen channel registry has no place
        # for them, so we fall back to nominal 120 degree spacing.  That
        # UNDER-estimates I_N,fund whenever the phases differ in power factor,
        # which OVER-estimates the harmonic excess and therefore biases the
        # verdict towards "harmonic loading" - the cheaper work order.  A bad
        # joint is never hidden by this approximation, only occasionally
        # mistaken for load, and rule H3 catches that through K_N regardless.
        angs = [an.get(f"mpr.i_angle_l{p}_deg", d)
                for p, d in zip((1, 2, 3), (0.0, -120.0, 120.0))]
        fund = nt.neutral_fundamental(phases[0], phases[1], phases[2],
                                      angs[0], angs[1], angs[2])
        air = live.env.get("env.air_c")
        best: tuple[float, str] | None = None
        for j in assets.monitored_joints():
            if j.conductor != "N":
                continue
            t = self._temp(pr, j.key, now)
            if t is None or air is None:
                continue
            dt_n = t - air
            if best is None or dt_n > best[0]:
                best = (dt_n, j.key)
        if best is None:
            return None
        dt_n, jkey = best
        joint = assets.JOINTS_BY_KEY[jkey]
        k_now = nt.k_n(dt_n, i_n)
        jr = pr.jr(jkey)
        base_theta = jr.cusum.baseline
        k_base = (base_theta / (joint.rated_a ** 2)) if base_theta else 0.0
        out = nt.rule_h3(k_now, k_base, dt_n, i_n, sum(phases) / 3.0,
                         i_n_fund=fund, ct_rating_a=assets.MAIN_CT_PRIMARY_A)
        out["joint_key"] = jkey
        return out

    def neutral_verdict(self, panel_key: str) -> dict | None:
        """Latest rule H3 result for the panel, for the rules layer."""
        return self._pr(panel_key).h3

    # ----------------------------------------------------------- devices ---

    def _device_views(self, pr: _PanelRuntime, panel_key: str,
                      now: float) -> list[DeviceView]:
        out: list[DeviceView] = []
        for d in assets.DEVICES:
            st = pr.devices.get(d.key, {})
            last = st.get("last_seen")
            online = bool(last and (now - last) <= self._online_window(pr, d.key)
                          and not st.get("offline"))
            out.append(DeviceView(
                key=d.key, kind=d.kind, label=d.label, mount=d.mount,
                online=online, last_seen=last,
                period_s=self._device_period(pr, d.key),
                rssi_dbm=st.get("dev.rssi_dbm"),
                battery_pct=st.get("dev.battery_pct"),
                battery_v=st.get("dev.battery_v"),
                fw=str(st.get("fw", "")),
                faults=list(st.get("faults", [])),
                x_mm=d.x_mm, y_mm=d.y_mm,
            ))
        return out

    # --------------------------------------------------------------- arc ---

    def _arc_view(self, pr: _PanelRuntime, row: dict, now: float) -> ArcView:
        fitted = bool(int(row.get("has_arc_relay", 1) or 0))
        a = ArcView(fitted=fitted)
        if not fitted:
            return a
        got = pr.ch.get("tvoc.online")
        state = pr.ch.get("tvoc.system_state")
        fresh = state is not None and (now - state[0]) <= ARC_OFFLINE_S
        a.online = bool(fresh and (got is None or got[1] >= 0.5))

        word = int(state[1]) if state is not None else 0
        # reg 1300: bit0 active trip, bit1 active error, bit2 start sequence,
        # bit3 diagnostics running.  Every other TVOC-2 status register is only
        # meaningful when this word says something is active - registers 200-212
        # and 222-225 read 0x0000 when there is NO active error or trip, so a
        # zero there must never be read as "all detectors failed" (manual 4.4.2).
        a.active_trip = bool(word & 0x1)
        a.active_error = bool(word & 0x2)
        a.start_sequence = bool(word & 0x4)
        a.diagnostics_running = bool(word & 0x8)

        total = pr.ch.get("tvoc.detectors_total")
        okc = pr.ch.get("tvoc.detectors_ok")
        a.detectors_total = int(total[1]) if total else int(row.get("arc_detectors") or 0)
        a.detectors_ok = int(okc[1]) if okc else a.detectors_total
        warn = pr.ch.get("tvoc.ambient_warn")
        a.ambient_warn = int(warn[1]) if warn else 0
        sd = pr.ch.get("tvoc.last_selftest_days")
        a.last_selftest_days = int(sd[1]) if sd else 9999

        # The 30-bit detector location map and the trip relay, gated on 1300
        # exactly as the manual requires.  This is what lets an alarm say
        # "detector X2:3, relay K5" instead of "somewhere in this panel".
        if a.active_trip or a.active_error:
            lo = pr.ch.get("tvoc.detector_map_lo")
            hi = pr.ch.get("tvoc.detector_map_hi")
            rel = pr.ch.get("tvoc.trip_relay")
            a.detector_map_lo = int(lo[1]) if lo else 0
            a.detector_map_hi = int(hi[1]) if hi else 0
            relay_word = int(rel[1]) if rel else 0
            names = [n for b, n in ((0, "K4"), (1, "K5"), (2, "K6")) if relay_word & (1 << b)]
            a.last_trip = {
                "ts": state[0] if state is not None else now,
                "detector_map_lo": a.detector_map_lo,
                "detector_map_hi": a.detector_map_hi,
                "relay_word": relay_word,
                "relays": names,
                "detectors": _decode_detector_map(a.detector_map_lo, a.detector_map_hi),
            }
        a.firmware = str(pr.devices.get("GW-01", {}).get("fw", ""))
        return a

    # ---------------------------------------------------------------- PD ---

    def pd_trend_db(self, panel_key: str, hours: float, now: float) -> float:
        """Change in PD Qmax over the last ``hours``, in dB.

        Median of the newest sixth of the window minus the median of the oldest
        sixth, so one loud switching transient does not become a trend.
        """
        since = now - hours * 3600.0
        pts = self.store.series(panel_key, "pd.qmax_db", since, now)
        if len(pts) < 6:
            return 0.0
        k = max(1, len(pts) // 6)
        old = median([v for _, v in pts[:k]])
        new = median([v for _, v in pts[-k:]])
        return float(new - old)

    def _pd_view(self, pr: _PanelRuntime, panel_key: str, now: float) -> PdView:
        p = PdView()
        for name, attr in (("pd.rate_per_s", "rate_per_s"), ("pd.qmax_db", "qmax_db"),
                           ("pd.nqn", "nqn"), ("pd.tev_db", "tev_db"),
                           ("pd.ultrasonic_db", "ultrasonic_db")):
            got = pr.ch.get(name)
            if got is not None:
                setattr(p, attr, got[1])
        kl = pr.ch.get("pd.class")
        idx = int(kl[1]) if kl else 0
        if 0 <= idx < len(channels.PRPD_CLASSES):
            p.klass = channels.PRPD_CLASSES[idx]
            p.klass_label = channels.PRPD_LABELS_TR[p.klass]
        p.trend_db_30d = self.pd_trend_db(panel_key, 24 * 30, now)
        p.features = {"trend_48h_db": self.pd_trend_db(panel_key, 48.0, now)}
        return p

    # ------------------------------------------------------------- flags ---

    def _status_flags(self, pr: _PanelRuntime, live: PanelLive, now: float) -> list[str]:
        """Only the OBSERVATIONAL flags.

        SUPPRESSED, MAINTENANCE, CONFIG_MISMATCH and SELFTEST_DUE are policy and
        belong to the rules layer; setting them here would let a physics module
        silently decide what an operator is allowed to see.
        """
        flags: list[str] = []
        if pr.last_ts:
            flags.append("DATA_VALID")
        if live.data_age_s > icd.STALE_AFTER_S:
            flags.append("STALE")

        # DE_ENERGISED before SENSITIVITY_LOW: a dark panel is not a panel we
        # cannot see well, it is a panel where no thermal indicator means
        # anything at all, and the two must not be confused on the screen.
        de = live.analyser_online and live.load_factor < DE_ENERGISED_F
        if de:
            flags.append("DE_ENERGISED")
        elif live.sensitivity_pct < 100.0:
            flags.append("SENSITIVITY_LOW")

        if live.learn_mode:
            flags.append("LEARN_MODE")

        devs = {d.key: d for d in live.devices}
        if any(d.battery_pct is not None and d.battery_pct < CELL_LOW_PCT
               for d in live.devices):
            flags.append("CELL_LOW")
        if any("MOUNT_LOST" in d.faults for d in live.devices):
            flags.append("MOUNT_LOST")
        aim = pr.ch.get("ir.aim_ok")
        if (aim is not None and aim[1] < 0.5) or any(
                "AIM_SHIFTED" in d.faults for d in live.devices):
            flags.append("AIM_SHIFTED")
        if pr.clock_unsynced:
            flags.append("CLOCK_UNSYNCED")

        if live.analyser_fitted and not live.analyser_online:
            flags.append("ANALYSER_COMMS_LOST")
        if live.arc.fitted and not live.arc.online:
            flags.append("ARC_RELAY_COMMS_LOST")
        gw = devs.get("GW-01")
        if gw is None or not gw.online:
            flags.append("GATEWAY_COMMS_LOST")
        return flags

    # -------------------------------------------------------------- info ---

    def stats(self) -> dict:
        return {
            "observed": self.observed,
            "rejected": self.rejected,
            "panels": len(self._panels),
            "seq_gaps": self.seq.gaps,
            "seq_lost": self.seq.lost,
            "duplicates": self.seq.duplicates,
            "reboots": self.seq.reboots,
        }


# --------------------------------------------------------------------------
# Self-test
# --------------------------------------------------------------------------

def _demo_envelopes(site: str, panel: str, t0: float, days: float, step_s: float,
                    seed: int, defect_joint: str | None = None,
                    defect_theta: float = 0.0, defect_start_day: float = 0.0,
                    defect_ramp_per_day: float = 0.0):
    """A deterministic synthetic panel.

    Six thermal clips on feeders 6 and 7 with their own CTs, one IR array
    covering all 40 bottom joints, one RF/environment node, one gateway - the
    frozen 9-device kit and nothing else.
    """
    import random

    rng = random.Random(seed)
    tau = 1200.0
    a = math.exp(-step_s / tau)
    lag: dict[str, float] = {}
    n = int(days * DAY_S / step_s)
    monitored = assets.monitored_joints()

    for k in range(n):
        ts = t0 + k * step_s
        hour = (ts / 3600.0) % 24.0
        f = 0.53 + 0.30 * math.sin(2 * math.pi * (hour - 9.0) / 24.0)
        air = 26.0 + 5.0 * math.sin(2 * math.pi * (hour - 15.0) / 24.0)
        rh = 55.0 - 10.0 * math.sin(2 * math.pi * (hour - 15.0) / 24.0)
        i_phase = f * SUM_FEEDER_RATED_A
        day = (ts - t0) / DAY_S

        temps: dict[str, float] = {}
        for j in monitored:
            base = air + 16.0 * f * f + rng.gauss(0.0, 0.10)
            theta_true = 0.0
            if defect_joint and j.key == defect_joint:
                theta_true = defect_theta
                if defect_ramp_per_day and day >= defect_start_day:
                    theta_true += defect_ramp_per_day * (day - defect_start_day)
            prev = lag.get(j.key, 0.0)
            cur = a * prev + (1.0 - a) * theta_true * f * f
            lag[j.key] = cur
            temps[j.key] = base + cur

        # --- gateway: analyser + arc relay mirror -------------------------
        #     published first: theta needs a current and rule H3 needs an air
        #     temperature from the SAME instant as the thermal payload.
        yield Envelope(
            kind="data", site=site, panel=panel, device="GW-01", ts=ts,
            seq=k, boot=1, fw="2.1.0",
            values={
                "mpr.v_l1_v": 231.0, "mpr.v_l2_v": 230.2, "mpr.v_l3_v": 232.1,
                "mpr.i_l1_a": round(i_phase * 1.08, 1),
                "mpr.i_l2_a": round(i_phase * 0.96, 1),
                "mpr.i_l3_a": round(i_phase * 0.96, 1),
                "mpr.i_n_a": round(i_phase * 0.18, 1),
                "mpr.freq_hz": 50.0, "mpr.online": 1,
                "mpr.thd_v_l1_pct": 2.4, "mpr.thd_i_l1_pct": 8.1,
                "tvoc.system_state": 0, "tvoc.online": 1,
                "tvoc.detectors_total": 10, "tvoc.detectors_ok": 10,
                "tvoc.ambient_warn": 0, "tvoc.last_selftest_days": 12,
            },
        )

        # --- RF / environment node ---------------------------------------
        yield Envelope(
            kind="data", site=site, panel=panel, device="PD-01", ts=ts,
            seq=k, boot=1, fw="1.0.0",
            values={"env.air_c": round(air, 2), "env.rh_pct": round(rh, 1),
                    "pd.rate_per_s": 12.0, "pd.qmax_db": 31.0, "pd.nqn": 40.0,
                    "pd.class": 0, "pd.tev_db": 12.0, "pd.ultrasonic_db": 8.0,
                    "dev.battery_pct": 89.0},
        )

        # --- IR array: every bottom joint, one envelope -------------------
        yield Envelope(
            kind="data", site=site, panel=panel, device="TN-IR", ts=ts,
            seq=k, boot=1, fw="1.0.0",
            values={"ir.air_top_c": round(air + 1.0, 2), "ir.aim_ok": 1,
                    "dev.battery_pct": 96.0, "dev.rssi_dbm": -78},
            joints={j.key: {"ir.lug_temp_c": round(temps[j.key], 2)}
                    for j in monitored},
        )

        # --- six thermal clips, each with its own split-core CT ------------
        for d in assets.DEVICES:
            if d.kind != "TC":
                continue
            jk = d.covers[0]
            joint = assets.JOINTS_BY_KEY[jk]
            yield Envelope(
                kind="data", site=site, panel=panel, device=d.key, ts=ts,
                seq=k, boot=1, fw="1.0.0",
                values={"dev.battery_pct": 93.0, "dev.rssi_dbm": -81},
                joints={jk: {"tc.temp_c": round(temps[jk], 2),
                             "tc.current_a": round(f * joint.rated_a, 1)}},
            )


if __name__ == "__main__":
    import tempfile
    from pathlib import Path

    from panogoz.store.db import Store

    print("=" * 78)
    print("engine.py self-test")
    print("=" * 78)

    tmp = Path(tempfile.mkdtemp(prefix="panogoz-engine-")) / "t.db"
    store = Store(tmp)
    STEP_S = 3600.0
    eng = DetectorEngine(store, commit_every=400, peer_max_age_s=2.5 * STEP_S)

    SITE, PANEL = "Soke", "SOKE-14"
    T0 = 1_750_000_000.0
    STEP = STEP_S            # 1 h, so the whole run is quick but the RLS is real
    DAYS = 45
    DEFECT = "C06-L2-PABUC"

    print(f"\n[1] ingesting {DAYS} days of a synthetic panel at "
          f"{STEP / 60:.0f} min cadence")
    print(f"    9 devices, {len(assets.monitored_joints())} monitored joints, "
          f"defect on {DEFECT} ramping 0.35 K/day from day 14")
    n_env = 0
    last_ts = T0
    for env in _demo_envelopes(SITE, PANEL, T0, DAYS, STEP, seed=7,
                               defect_joint=DEFECT, defect_theta=0.0,
                               defect_start_day=14.0, defect_ramp_per_day=0.35):
        eng.observe(env)
        n_env += 1
        last_ts = env.ts
    store.commit()
    NOW = last_ts + 30.0
    print(f"    {n_env:,} envelopes, {eng.stats()['rejected']} rejected samples")
    print(f"    store: {store.stats()['joint_sample']:,} joint samples, "
          f"{store.stats()['sample']:,} panel samples")

    print(f"\n[2] daily rollup and drift statistics")
    written = eng.roll_daily(NOW, days_back=DAYS + 2)
    print(f"    joint_daily rows written: {written}")

    live = eng.evaluate(PANEL, NOW)
    print(f"\n[3] the live image")
    print(f"    panel {live.panel_key} ({live.site}, {live.dso})  "
          f"index {live.panel_index}")
    print(f"    joints in image {len(live.joints)} "
          f"({sum(1 for j in live.joints if j.monitored)} monitored, "
          f"{sum(1 for j in live.joints if not j.monitored)} shown as izlenmiyor)")
    print(f"    devices {len(live.devices)} "
          f"({sum(1 for d in live.devices if d.online)} online)")
    assert len(live.devices) == 9, "the device kit is frozen at 9"
    assert len(live.joints) == len(assets.JOINTS)
    print(f"    load factor {100 * live.load_factor:.1f} %   "
          f"sensitivity {live.sensitivity_pct:.0f} %   "
          f"data age {live.data_age_s:.0f} s")
    print(f"    status flags: {', '.join(live.status_flags)}")
    print(f"    analyser online {live.analyser_online} · arc fitted "
          f"{live.arc.fitted} online {live.arc.online} "
          f"({live.arc.detectors_ok}/{live.arc.detectors_total} dedektör)")
    print(f"    env: hava {live.env.get('env.air_c'):.1f} °C  "
          f"nem {live.env.get('env.rh_pct'):.0f} %  "
          f"çiy {live.env.get('env.dewpoint_c'):.2f} °C  "
          f"yüzey {live.env.get('env.wall_c'):.2f} °C  "
          f"pay {live.env.get('env.condensation_margin_k'):.2f} K")

    print(f"\n[4] the worst joint")
    print(f"    theta_max {live.theta_max:.2f} K on {live.theta_max_joint}")
    assert live.theta_max_joint == DEFECT, live.theta_max_joint
    jv = next(j for j in live.joints if j.key == DEFECT)
    import datetime as _dt
    cpt = ("-" if jv.changepoint_ts is None
           else _dt.datetime.utcfromtimestamp(jv.changepoint_ts).strftime("%Y-%m-%d"))
    print(f"    {jv.label}")
    print(f"      T {jv.temp_c:.2f} °C   kardeş medyanı {jv.sibling_median_c:.2f} °C"
          f"   akım {jv.current_a:.0f} A   f {jv.load_factor:.2f}")
    print(f"      θ {jv.theta_k:.2f} K   görülebilir en küçük θ "
          f"{jv.theta_min_k:.2f} K   görünürlük {jv.sensitivity_pct:.0f} %")
    print(f"      fazla direnç {jv.excess_r_lo_uohm:.1f} .. "
          f"{jv.excess_r_hi_uohm:.1f} µΩ  (R_th 2-4 K/W varsayımıyla)")
    print(f"      ufuk: hedef {jv.eta.target or '—'} · "
          f"{'—' if jv.eta.days is None else format(jv.eta.days, '.0f') + ' g'}"
          f" · gerekçe {jv.eta.reason or '(yok)'} · "
          f"geçerli gün {jv.eta.valid_days}")
    print(f"      CUSUM {jv.cusum:.1f}   taban {jv.baseline_k:.2f} K   "
          f"eğim {jv.slope_k_per_week:+.2f} K/hafta")
    print(f"      başlangıç {cpt}   nitelikli gün {jv.alarm_days}/5   "
          f"seviye {jv.severity}")
    assert jv.theta_k > 5.0
    assert jv.severity in ("UYARI", "KRITIK"), jv.severity

    healthy = next(j for j in live.joints if j.key == "C06-L1-PABUC")
    print(f"    healthy sibling C06-L1-PABUC: θ {healthy.theta_k:+.2f} K, "
          f"CUSUM {healthy.cusum:.1f}, seviye {healthy.severity}")
    assert healthy.severity == "BILGI"

    print(f"\n[5] absolute limits are armed from minute one")
    # Use a REAL clip-instrumented joint key: the absolute-theta path is open
    # only to joints that carry their own TMP117 and their own CT, so a
    # made-up key would silently exercise the wrong branch.
    _clip_key = sorted(eng._tc_joints)[0]
    hot = JointView(key=_clip_key, label=_clip_key, zone="bottom", conductor="L1",
                    feeder_index=6, rated_a=400.0, monitored=True, temp_c=118.0)
    jr0 = _JointRuntime()
    print(f"    118 °C, no theta, learn_mode ON  -> "
          f"{eng._joint_severity(hot, jr0, True)}")
    assert eng._joint_severity(hot, jr0, True) == "KRITIK"
    hot.temp_c = 134.0
    print(f"    134 °C, no theta, learn_mode ON  -> "
          f"{eng._joint_severity(hot, jr0, True)}")
    assert eng._joint_severity(hot, jr0, True) == "ACIL"
    hot.temp_c = 60.0
    hot.theta_k, hot.theta_min_k = 7.0, 1.0
    print(f"    60 °C, θ 7 K, learn_mode ON      -> "
          f"{eng._joint_severity(hot, jr0, True)}   (theta capped while learning)")
    assert eng._joint_severity(hot, jr0, True) == "IZLE"
    print(f"    60 °C, θ 7 K, learn_mode OFF     -> "
          f"{eng._joint_severity(hot, jr0, False)}")
    assert eng._joint_severity(hot, jr0, False) == "UYARI"

    print(f"\n[6] restart - the detector must not lose its baselines")
    before = (jv.theta_k, jv.cusum, jv.baseline_k, jv.slope_k_per_week)
    eng2 = DetectorEngine(store, commit_every=1, peer_max_age_s=2.5 * STEP_S)
    live2 = eng2.evaluate(PANEL, NOW)
    jv2 = next(j for j in live2.joints if j.key == DEFECT)
    after = (jv2.theta_k, jv2.cusum, jv2.baseline_k, jv2.slope_k_per_week)
    print(f"    before restart  θ {before[0]:.4f}  CUSUM {before[1]:.3f}  "
          f"taban {before[2]:.4f}  eğim {before[3]:+.4f}")
    print(f"    after  restart  θ {after[0]:.4f}  CUSUM {after[1]:.3f}  "
          f"taban {after[2]:.4f}  eğim {after[3]:+.4f}")
    for x, y in zip(before, after):
        assert abs(x - y) < 1e-9, f"{x} != {y}"
    print(f"    identical - state came back from the joint_state table")

    # The RLS cold start is the trap here.  ``train_n`` in the schema belongs to
    # the CUSUM, so a restored ThetaState would report n = 0 and the next sample
    # would RE-SEED theta from a single reading, throwing away everything that
    # was just reloaded.  Feed one more envelope and prove it does not.
    more = list(_demo_envelopes(SITE, PANEL, NOW + STEP, 1.0 / 24.0, STEP, seed=7,
                                defect_joint=DEFECT, defect_theta=10.5))
    for env in more:
        eng2.observe(env)
    jv3 = next(j for j in eng2.evaluate(PANEL, more[-1].ts + 30.0).joints
               if j.key == DEFECT)
    row = [r for r in store.joint_states(PANEL) if r["joint_key"] == DEFECT][0]
    restored = th.ThetaState.from_row(row)
    print(f"    restored ThetaState: n={restored.n} (must be > 0), "
          f"p={restored.p:.3e}, dt_excess={restored.dt_excess:.3f} K")
    print(f"    stored train_n = {row['train_n']} - that column belongs to the CUSUM,")
    print(f"    so the RLS infers 'past cold start' from its covariance instead")
    print(f"    (theta.py self-test [8] proves the train_n = 0 case)")
    print(f"    one more sample after the restart: θ {after[0]:.4f} -> "
          f"{jv3.theta_k:.4f} K  (moved {abs(jv3.theta_k - after[0]):.4f} K, i.e.")
    print(f"    it kept estimating instead of restarting)")
    assert restored.n > 0, "restored RLS state must not look like a cold start"
    assert abs(jv3.theta_k - after[0]) < 0.5, "restart re-seeded the estimator"

    print(f"\n[7] Modbus encoding through the ICD (nothing duplicated here)")
    order = [j.key for j in assets.JOINTS]
    live.severity = "UYARI"
    words = live.to_registers(order)
    print(f"    {len(words)} words at PDU {icd.panel_base(max(1, live.panel_index))}"
          f" (panel {live.panel_index})")
    R = icd.PANEL_BY_NAME
    for name in ("THETA_MAX", "THETA_MAX_JOINT", "SENSITIVITY_PCT", "LOAD_FACTOR",
                 "T_JOINT_MAX", "DEWPOINT_MARGIN", "STATUS_WORD", "DEVICES_ONLINE"):
        r = R[name]
        raw = words[r.offset:r.offset + r.words]
        print(f"      +{r.offset:<3} {name:<20} raw {raw} -> "
              f"{icd.decode(r, raw):g} {r.unit}")
    sw = words[R["STATUS_WORD"].offset]
    print(f"      STATUS_WORD bits: {', '.join(icd.unpack_bits(icd.STATUS_BITS, sw))}")
    assert abs(icd.decode(R["THETA_MAX"], words[6:7]) - round(live.theta_max, 1)) < 0.06

    print(f"\n[8] engine counters")
    for k, v in eng.stats().items():
        print(f"    {k:<10} {v}")

    store.close()
    print("\nOK - engine.py self-test passed")
