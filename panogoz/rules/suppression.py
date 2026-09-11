"""Suppression: the reasons we deliberately do not tell you something.

The single hardest problem in fleet condition monitoring is not detection.  It
is the fact that one operator cannot read a hundred panels' worth of true-but-
useless alarms.  Every rule in this module exists to answer one question:

    Is this reading about the panel, or about the grid, the weather, the load,
    or our own instrument?

If it is about anything other than the panel, it must not become a panel fault.
It must instead become a row in the ``suppression`` table with a Turkish reason
an operator can read.  That table is a shipped product feature with its own
screen.  It is what an operator opens when they ask *"why didn't you tell me
about that 78 degree reading?"* - and the answer, in their own language, is
"because the feeder went from 90 A to 620 A eleven minutes ago and the joint is
still on its thermal ramp; theta is held until 3*tau has elapsed."

The headline discriminator
--------------------------

Voltage THD rising on **all three phases together** is a grid-side event.  A
defect inside one panel cannot lift the voltage distortion of all three phases
in step; the panel is a load, not a source, and its own busbar impedance is
microohms.  Recognising this one pattern is what makes a hundred panels
manageable, because a regional event otherwise produces a hundred simultaneous
"anomalies" from a hundred honest detectors.

The learn week
--------------

The first seven days after commissioning accumulate baseline only.  But the
window is never blind: the absolute temperature limits in ``rules.fusion``
(90 / 110 / 130 C) stay armed throughout, because a lug that is at 130 C on day
two of commissioning is at 130 C regardless of how much history we have.

The ``history`` dictionary
--------------------------

``evaluate`` is pure with respect to the live image and takes all of its context
from ``history``.  Recognised keys, all optional::

    history["load_factor"]      [(ts, load_factor), ...]  ascending, >= 15 min deep
    history["thd_v_baseline"]   {"L1": pct, "L2": pct, "L3": pct}
    history["commissioned"]     epoch seconds; falls back to live.learn_until
    history["device_residual"]  {device_key: {"stuck_s": s, "drift_k_per_day": K}}
    history["maintenance"]      True while an operator has muted the panel
    history["now"]              epoch seconds; falls back to live.ts

``evaluate`` also writes bookkeeping keys prefixed with ``_`` back into
``history`` (grid-window and load-hold expiry instants), so the caller can keep
one dictionary per panel and hand it back each cycle.  Nothing else is mutated.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Iterable

from panogoz.contracts import assets
from panogoz.contracts.live import PanelLive, SuppressionView
from panogoz.rules import fusion

# --------------------------------------------------------------------------
# Tunables, all stated as named constants so the ICD document can print them
# --------------------------------------------------------------------------

#: Voltage THD above this, on all three phases at once, is a grid-side event.
#: EN 50160 allows 8 % total voltage THD on LV networks, so 5 % is comfortably
#: inside "distorted but legal" and is where the discriminator starts to earn.
THD_V_GRID_PCT = 5.0
#: ...and each phase must be at least this far above its own quiet baseline, so
#: a permanently distorted feeder does not suppress itself forever.
THD_V_RISE_PCT = 1.5
#: Default quiet baseline when the caller supplies no history.
THD_V_BASELINE_PCT = 2.5

#: Grid frequency acceptance window.  Outside it, nothing thermal is trusted
#: for GRID_WINDOW_S, because the whole region is doing something unusual.
FREQ_LO_HZ = 49.5
FREQ_HI_HZ = 50.5
GRID_WINDOW_S = 600.0

#: A load step larger than this within LOAD_STEP_WINDOW_S puts theta on hold.
#: theta divides out the *steady state* I^2 dependence; it says nothing about
#: the transient, and a joint's thermal time constant is tau ~ 20 min.
LOAD_STEP_FRACTION = 0.30
LOAD_STEP_WINDOW_S = 900.0
JOINT_TAU_S = 1200.0
LOAD_HOLD_S = 3.0 * JOINT_TAU_S  # 3600 s, about 60 minutes

#: Transformer energisation inrush: current goes from essentially nothing to a
#: large fraction of rating in one sample, with heavy even-harmonic distortion.
#: TEDAS EK-I/11 Not 5 already forbids the thermal relay from mis-tripping on
#: inrush; we inherit the rule rather than inventing a new one.
INRUSH_QUIET_LOAD = 0.05
INRUSH_STEP_LOAD = 0.35
INRUSH_THD_I_PCT = 15.0

#: Current-THD gate.  The MPR-53CS THD registers saturate at 99.9 % and light
#: load routinely exceeds that, so below this fraction of CT rating the current
#: THD channel is not merely noisy - it is meaningless.
THD_I_GATE_FRACTION = 0.10

#: Below this load factor theta's detectability floor (3*sigma/f^2) has grown
#: past anything worth calling a defect.  f = 0.35 -> theta_min = 4.9 K.
SENSITIVITY_LOAD_FLOOR = 0.35
#: Below this, there is no current at all and no thermal statement is possible.
DE_ENERGISED_LOAD = 0.02

#: Learn week, seconds.
LEARN_WINDOW_S = 7.0 * 86400.0

#: How stale a live image may be before we stop believing it.
STALE_AFTER_S = 90.0

#: Sensor self-diagnosis limits.
STUCK_S = 3600.0
DRIFT_K_PER_DAY = 0.30

#: The log-odds pushed into a mode when its evidence has been explained away.
#: Chosen at -1.5 so it cancels a strong single channel but cannot on its own
#: drive a risk to zero: suppression argues, it does not decree.
GRID_LLR = -1.5
HOLD_LLR = -1.2
BLIND_LLR = -1.0

#: The push for evidence that is CONSISTENT with a grid event but does not
#: establish one.
#:
#: Three-phase voltage THD is the case that matters.  The panel is a load and
#: cannot lift three phases on its own, but the non-linear loads it FEEDS can: a
#: VFD bank, a UPS or a rectifier downstream of this busbar injects harmonic
#: current into all three phases, and that current develops a voltage distortion
#: across the shared upstream impedance.  At the analyser the two look identical,
#: and nothing in this panel can tell them apart.
#:
#: A third of the full push is enough to demote a finding that rests on the
#: distortion itself, and too little to argue away a thermal finding that has its
#: own independent evidence - which is the case that matters, because a
#: disturbance is exactly when a marginal joint is most likely to let go.
GRID_CANDIDATE_LLR = -0.5

#: Modes a grid-side or transient event can masquerade as.  ``arc_integrity``
#: is excluded on purpose: it is the TVOC-2 reporting on itself, and a grid
#: disturbance is no reason to disbelieve a detector fault.  ``moisture`` is
#: excluded because dewpoint physics does not care what the grid is doing.
IN_PANEL_MODES: tuple[str, ...] = (
    "loose_connection", "overload", "thermal_runaway", "harmonic_neutral", "insulation",
)

#: Modes that depend on a thermal reading and therefore go quiet when the
#: thermal reading is not trustworthy.
THERMAL_MODES: tuple[str, ...] = ("loose_connection", "thermal_runaway", "overload")

#: Modes whose EVIDENCE IS the harmonic measurement.  When the distortion is
#: explained by something outside this panel, so is the finding, and the full
#: push applies whether the source is the grid or a neighbouring load.
THD_ATTRIBUTABLE_MODES: tuple[str, ...] = ("harmonic_neutral", "insulation")

#: Modes that rest on a temperature, measured by a different sensor through a
#: different physical mechanism.  A voltage-distortion measurement is at most
#: circumstantial for these, so it only ever demotes them to a candidate.
THD_CANDIDATE_MODES: tuple[str, ...] = tuple(
    m for m in IN_PANEL_MODES if m not in THD_ATTRIBUTABLE_MODES
)

# --------------------------------------------------------------------------
# Reason catalogue - reason code -> Turkish sentence template
# --------------------------------------------------------------------------

REASONS_TR: dict[str, str] = {
    "GRID_THD_3PH":
        "Üç fazın gerilim THD'si birlikte yükseldi (%{l1:.1f} / %{l2:.1f} / %{l3:.1f}). "
        "Bu bulgunun kanıtı harmoniğin kendisidir ve harmoniğin kaynağı bu panonun "
        "dışındadır; pano bir yüktür, üç fazın gerilim bozunumunu kendi üretemez. "
        "Kaynak şebeke ya da tesis içindeki doğrusal olmayan bir yük olabilir; her "
        "iki durumda da bu pano için tork iş emri açılmaz.",
    "GRID_THD_3PH_CANDIDATE":
        "Üç fazın gerilim THD'si birlikte yükseldi (%{l1:.1f} / %{l2:.1f} / %{l3:.1f}). "
        "Bu, ŞEBEKE OLAYI ADAYIDIR, kanıtlanmış bir şebeke olayı değildir: aynı "
        "ölçümü tesis içindeki büyük bir doğrusal olmayan yük (sürücü, UPS, "
        "redresör) de üretir ve analizör ikisini ayırt edemez. Isıl bulgu kendi "
        "bağımsız kanıtına dayandığı için silinmez, yalnızca bir kademe geriletilir. "
        "Şebeke atfının kesinleşmesi için EK KANIT gerekir (frekans penceresi, "
        "inrush sınıflandırması ya da filo genelinde eşzamanlılık).",
    "INRUSH":
        "Trafo devreye alma (inrush) sınıflandırıldı: yük %{f0:.0f} → %{f1:.0f}, akım THD "
        "%{thd:.0f}. TEDAŞ EK-I/11 Not 5 termik rölenin inrush'ta açmasını zaten "
        "yasaklar; aynı kuralı biz de uygularız. Alarm üretilmez, olay kaydedilir.",
    "GRID_FREQUENCY":
        "Şebeke frekansı {f:.2f} Hz, {lo}-{hi} Hz penceresinin dışında. Bölgesel bir "
        "olay sürüyor; ısıl göstergeler {mins:.0f} dakika boyunca askıya alındı.",
    "LOAD_STEP":
        "Son {win:.0f} dakikada yük %{step:.0f} değişti (%{f0:.0f} → %{f1:.0f}). "
        "θ kararlı hâl için tanımlıdır; bağlantının ısıl zaman sabiti τ≈{tau:.0f} dk "
        "olduğundan 3τ = {hold:.0f} dk boyunca θ askıya alındı.",
    "SENSITIVITY_LOW":
        "Yük faktörü %{f:.0f}. Görülebilir en küçük θ, 3σ/f² = {tmin:.1f} K'e çıktı. "
        "Bu bir pano arızası değil, bir görünürlük durumudur: şu anda küçük bir "
        "kusuru göremiyoruz ve bunu saklamıyoruz.",
    "DE_ENERGISED":
        "Panoda akım yok ({i:.0f} A). Hiçbir ısıl gösterge anlamlı değildir. "
        "Bu bir modül durumudur, pano arızası değildir.",
    "STALE":
        "Veri yaşı {age:.0f} s (> {limit:.0f} s). Bayat görüntü üzerinden alarm "
        "üretilmez; son iyi değeri sessizce tekrar yayınlamak da yapılmaz.",
    "LEARN_WEEK":
        "Devreye alma sonrası öğrenme haftası ({days:.1f}/7 gün). Bu pencerede yalnız "
        "temel çizgi toplanır. Mutlak sıcaklık limitleri (90/110/130 °C) bu süre "
        "boyunca da aktiftir; pencere hiçbir zaman kör değildir.",
    "MAINTENANCE":
        "Operatör panoyu bakım moduna aldı. Bastırma gerekçesi ve süresi kayıtlıdır.",
    "THD_I_UNGATED":
        "Akım THD'si değerlendirilmedi: en yüksek faz akımı {i:.0f} A, CT anmasının "
        "%{gate:.0f}'i olan {need:.0f} A'in altında. Register %99.9'da doyar ve "
        "düşük yükte okunan değer fizikî olarak anlamsızdır.",
    "DEVICE_MOUNT_LOST":
        "{dev} kelepçesi kabloyla temasını kaybetti (MOUNT_LOST). Okuduğu sıcaklık "
        "artık bağlantının değil, havanın sıcaklığıdır. Bu bir CİHAZ iş emridir: "
        "kelepçeyi yerine oturtun. Bağlantıyı yeniden sıkmayın.",
    "DEVICE_AIM_SHIFTED":
        "{dev} termal dizisinin nişanı kaydı (AIM_SHIFTED): üç sabit referans noktası "
        "eşleşmiyor. Pikseller artık aynı pabuçlara bakmıyor. CİHAZ iş emri: diziyi "
        "yeniden hizalayın.",
    "DEVICE_CELL_LOW":
        "{dev} pili zayıf (CELL_LOW). Ölçüm sürüyor ancak güvenilirliği düşüyor. "
        "CİHAZ iş emri: Li-SOCl2 hücreyi değiştirin.",
    "DEVICE_STUCK":
        "{dev} {stuck:.0f} saniyedir aynı değeri veriyor. Takılı bir sensör, kusursuz "
        "bir bağlantı gibi de görünebilir, korkunç bir bağlantı gibi de. CİHAZ iş "
        "emri: sensörü doğrulayın.",
    "DEVICE_DRIFT":
        "{dev} günde {drift:+.2f} K sapıyor. Sapan bir sensör CİHAZ iş emri üretir, "
        "tork iş emri DEĞİL. Bağlantıya gitmeden önce sensörü kalibre edin.",
    "OFFLINE":
        "{dev} çevrimdışı. Kapsadığı bağlantılar için ısıl gösterge yoktur; "
        "'veri yok' ile 'sorun yok' aynı şey değildir.",
}


def reason_text(code: str, **kw: Any) -> str:
    tmpl = REASONS_TR.get(code)
    if tmpl is None:  # pragma: no cover - programmer error
        return code
    try:
        return tmpl.format(**kw)
    except (KeyError, IndexError, ValueError):  # pragma: no cover
        return tmpl


# --------------------------------------------------------------------------
# Result
# --------------------------------------------------------------------------

@dataclass
class SuppressionResult:
    flags: set[str] = field(default_factory=set)
    suppressed: list[dict] = field(default_factory=list)
    negative_evidence: dict[str, float] = field(default_factory=dict)
    #: Joints whose thermal evidence is attributed to a device rather than to
    #: the panel.  ``fusion`` skips these entirely.
    joints_out: set[str] = field(default_factory=set)
    #: Device work orders raised instead of joint work orders.
    device_orders: list[dict] = field(default_factory=list)

    def add(self, reason: str, reason_tr: str, mode: str | None = None,
            joint_key: str | None = None, detail: dict | None = None) -> None:
        self.suppressed.append({
            "reason": reason,
            "reason_tr": reason_tr,
            "mode": mode,
            "joint_key": joint_key,
            "detail": detail or {},
        })

    def push(self, llr: float, modes: Iterable[str]) -> None:
        for m in modes:
            self.negative_evidence[m] = self.negative_evidence.get(m, 0.0) + llr

    def to_dict(self) -> dict:
        return {
            "flags": sorted(self.flags),
            "suppressed": self.suppressed,
            "negative_evidence": self.negative_evidence,
            "joints_out": sorted(self.joints_out),
            "device_orders": self.device_orders,
        }


# --------------------------------------------------------------------------
# Individual discriminators
# --------------------------------------------------------------------------

def _thd_v(live: PanelLive) -> tuple[float | None, float | None, float | None]:
    an = live.analyser or {}
    return (an.get("mpr.thd_v_l1_pct"), an.get("mpr.thd_v_l2_pct"), an.get("mpr.thd_v_l3_pct"))


def three_phase_thd_event(live: PanelLive, history: dict) -> dict | None:
    """All three voltage THDs high AND all three lifted off their own baseline.

    Both halves matter.  "All three high" alone would suppress a feeder that is
    permanently distorted by a nearby converter.  "All three risen" alone would
    fire on measurement noise.  Together they describe a grid event and nothing
    else in this panel can produce them.
    """
    l1, l2, l3 = _thd_v(live)
    if l1 is None or l2 is None or l3 is None:
        return None
    base = dict(history.get("thd_v_baseline") or {})
    b1 = float(base.get("L1", THD_V_BASELINE_PCT))
    b2 = float(base.get("L2", THD_V_BASELINE_PCT))
    b3 = float(base.get("L3", THD_V_BASELINE_PCT))
    high = l1 >= THD_V_GRID_PCT and l2 >= THD_V_GRID_PCT and l3 >= THD_V_GRID_PCT
    risen = (l1 - b1) >= THD_V_RISE_PCT and (l2 - b2) >= THD_V_RISE_PCT and (l3 - b3) >= THD_V_RISE_PCT
    if not (high and risen):
        return None
    return {"l1": l1, "l2": l2, "l3": l3, "baseline": [b1, b2, b3],
            "rise": [l1 - b1, l2 - b2, l3 - b3]}


def load_step(history: dict, now: float) -> dict | None:
    """Largest relative load change inside the last ``LOAD_STEP_WINDOW_S``."""
    series = list(history.get("load_factor") or [])
    if len(series) < 2:
        return None
    window = [(t, f) for t, f in series if now - t <= LOAD_STEP_WINDOW_S]
    if len(window) < 2:
        return None
    f_now = window[-1][1]
    f_ref = window[0][1]
    denom = max(f_ref, 0.02)
    step = abs(f_now - f_ref) / denom
    if step < LOAD_STEP_FRACTION:
        return None
    return {"f0": f_ref, "f1": f_now, "step": step, "t0": window[0][0], "t1": window[-1][0]}


def inrush(live: PanelLive, history: dict, now: float) -> dict | None:
    """Transformer energisation, classified and never alarmed."""
    step = load_step(history, now)
    if step is None:
        return None
    if not (step["f0"] <= INRUSH_QUIET_LOAD and step["f1"] >= INRUSH_STEP_LOAD):
        return None
    an = live.analyser or {}
    thd = [an.get(f"mpr.thd_i_l{p}_pct") for p in (1, 2, 3)]
    thd = [t for t in thd if t is not None]
    thd_max = max(thd) if thd else 0.0
    if thd_max < INRUSH_THD_I_PCT:
        return None
    return {"f0": step["f0"], "f1": step["f1"], "thd": thd_max}


def _device_faults(live: PanelLive, history: dict) -> list[dict]:
    """Turn device state into device work orders, never joint work orders."""
    resid = dict(history.get("device_residual") or {})
    out: list[dict] = []
    for d in live.devices:
        spec = assets.DEVICES_BY_KEY.get(d.key)
        covers = tuple(spec.covers) if spec else ()
        flags = set(d.faults or ())
        r = dict(resid.get(d.key) or {})
        if "MOUNT_LOST" in flags:
            out.append({"code": "DEVICE_MOUNT_LOST", "device": d.key, "covers": covers,
                        "kw": {"dev": d.key}})
        if "AIM_SHIFTED" in flags:
            out.append({"code": "DEVICE_AIM_SHIFTED", "device": d.key, "covers": covers,
                        "kw": {"dev": d.key}})
        if "CELL_LOW" in flags or (d.battery_pct is not None and d.battery_pct < 10):
            out.append({"code": "DEVICE_CELL_LOW", "device": d.key, "covers": (),
                        "kw": {"dev": d.key}})
        stuck = float(r.get("stuck_s", 0.0) or 0.0)
        if stuck >= STUCK_S:
            out.append({"code": "DEVICE_STUCK", "device": d.key, "covers": covers,
                        "kw": {"dev": d.key, "stuck": stuck}})
        drift = float(r.get("drift_k_per_day", 0.0) or 0.0)
        if abs(drift) >= DRIFT_K_PER_DAY:
            out.append({"code": "DEVICE_DRIFT", "device": d.key, "covers": covers,
                        "kw": {"dev": d.key, "drift": drift}})
        if not d.online and d.key != "GW-01":
            out.append({"code": "OFFLINE", "device": d.key, "covers": covers,
                        "kw": {"dev": d.key}})
    return out


# --------------------------------------------------------------------------
# evaluate
# --------------------------------------------------------------------------

def evaluate(live: PanelLive, history: dict) -> SuppressionResult:
    """Decide, for this cycle, what must not become a panel fault."""
    res = SuppressionResult()
    now = float(history.get("now") or live.ts or time.time())
    an = live.analyser or {}

    # ---- 1. grid-side voltage distortion --------------------------------
    ev = three_phase_thd_event(live, history)
    if ev is not None:
        # TWO VERDICTS, BECAUSE THE MEASUREMENT SUPPORTS TWO DIFFERENT CLAIMS.
        #
        # For a finding whose evidence is the distortion itself, the source being
        # outside this panel settles it.  For a finding that rests on a lug's
        # temperature, the same measurement is circumstantial: an in-facility
        # rectifier produces it just as well as a regional event, and suppressing
        # a hot bolt on that basis would delete the one incident that mattered.
        res.flags.add("GRID_DISTURBANCE_CANDIDATE")
        txt = reason_text("GRID_THD_3PH", l1=ev["l1"], l2=ev["l2"], l3=ev["l3"])
        for m in THD_ATTRIBUTABLE_MODES:
            res.add("GRID_THD_3PH", txt, mode=m, detail=ev)
        res.push(GRID_LLR, THD_ATTRIBUTABLE_MODES)

        cand = reason_text("GRID_THD_3PH_CANDIDATE", l1=ev["l1"], l2=ev["l2"],
                           l3=ev["l3"])
        for m in THD_CANDIDATE_MODES:
            res.add("GRID_THD_3PH_CANDIDATE", cand, mode=m,
                    detail={**ev, "confirmed": False})
        res.push(GRID_CANDIDATE_LLR, THD_CANDIDATE_MODES)

    # ---- 2. transformer energisation inrush ------------------------------
    ir = inrush(live, history, now)
    if ir is not None:
        res.flags.add("INRUSH")
        txt = reason_text("INRUSH", f0=100.0 * ir["f0"], f1=100.0 * ir["f1"], thd=ir["thd"])
        for m in ("overload", "harmonic_neutral", "loose_connection"):
            res.add("INRUSH", txt, mode=m, detail=ir)
        res.push(GRID_LLR, ("overload", "harmonic_neutral", "loose_connection"))

    # ---- 3. frequency window ---------------------------------------------
    f = an.get("mpr.freq_hz")
    if f is not None and not (FREQ_LO_HZ <= f <= FREQ_HI_HZ):
        history["_freq_window_until"] = now + GRID_WINDOW_S
    until = float(history.get("_freq_window_until") or 0.0)
    if now < until:
        res.flags.add("GRID_WINDOW")
        txt = reason_text("GRID_FREQUENCY", f=(f if f is not None else float("nan")),
                          lo=FREQ_LO_HZ, hi=FREQ_HI_HZ, mins=(until - now) / 60.0)
        for m in IN_PANEL_MODES:
            res.add("GRID_FREQUENCY", txt, mode=m,
                    detail={"freq_hz": f, "until": until, "window_s": GRID_WINDOW_S})
        res.push(GRID_LLR, IN_PANEL_MODES)

    # ---- 3b. promotion: candidate -> confirmed grid event -----------------
    #
    # Nothing downstream of an LV busbar moves the system frequency, and an
    # inrush is a classified transient with its own signature.  Either of them
    # agreeing with the distortion is corroboration this panel cannot
    # manufacture, and only then does the attribution stop being a candidate.
    # ``GRID_DISTURBANCE`` blocks crew dispatch outright (see
    # ``alarms.NO_DISPATCH_FLAGS``), which is why it has to be earned.
    if "GRID_DISTURBANCE_CANDIDATE" in res.flags and (
            "GRID_WINDOW" in res.flags or "INRUSH" in res.flags):
        res.flags.add("GRID_DISTURBANCE")

    # ---- 4. load step: theta held for 3*tau -------------------------------
    st = load_step(history, now)
    if st is not None and ir is None:
        history["_load_hold_until"] = now + LOAD_HOLD_S
    hold_until = float(history.get("_load_hold_until") or 0.0)
    if now < hold_until:
        res.flags.add("LOAD_HOLD")
        d = st or {"f0": 0.0, "f1": live.load_factor, "step": LOAD_STEP_FRACTION}
        txt = reason_text("LOAD_STEP", win=LOAD_STEP_WINDOW_S / 60.0,
                          step=100.0 * d["step"], f0=100.0 * d["f0"], f1=100.0 * d["f1"],
                          tau=JOINT_TAU_S / 60.0, hold=LOAD_HOLD_S / 60.0)
        for m in THERMAL_MODES:
            res.add("LOAD_STEP", txt, mode=m, detail={**d, "until": hold_until})
        res.push(HOLD_LLR, THERMAL_MODES)

    # ---- 5. module states: we are blind, not calm -------------------------
    lf = live.load_factor or 0.0
    i_phases = [an.get(f"mpr.i_l{p}_a") for p in (1, 2, 3)]
    i_phases = [v for v in i_phases if v is not None]
    i_max = max(i_phases) if i_phases else 0.0
    if lf <= DE_ENERGISED_LOAD:
        res.flags.add("DE_ENERGISED")
        txt = reason_text("DE_ENERGISED", i=i_max)
        for m in THERMAL_MODES:
            res.add("DE_ENERGISED", txt, mode=m, detail={"load_factor": lf, "i_max_a": i_max})
        res.push(BLIND_LLR, THERMAL_MODES)
    elif lf < SENSITIVITY_LOAD_FLOOR:
        res.flags.add("SENSITIVITY_LOW")
        tmin = 3.0 * 0.2 / max(lf, 1e-6) ** 2
        txt = reason_text("SENSITIVITY_LOW", f=100.0 * lf, tmin=tmin)
        for m in THERMAL_MODES:
            res.add("SENSITIVITY_LOW", txt, mode=m,
                    detail={"load_factor": lf, "theta_min_k": round(tmin, 2)})
        res.push(BLIND_LLR, THERMAL_MODES)

    if live.data_age_s and live.data_age_s > STALE_AFTER_S:
        res.flags.add("STALE")
        res.add("STALE", reason_text("STALE", age=live.data_age_s, limit=STALE_AFTER_S),
                detail={"data_age_s": live.data_age_s})
        res.push(BLIND_LLR, IN_PANEL_MODES)

    # ---- 6. device attribution -------------------------------------------
    for order in _device_faults(live, history):
        txt = reason_text(order["code"], **order["kw"])
        res.device_orders.append({
            "device": order["device"],
            "reason": order["code"],
            "reason_tr": txt,
            "action_tr": "Cihaz iş emri — bağlantıya müdahale etmeyin",
        })
        for jk in order["covers"]:
            res.joints_out.add(jk)
            res.add(order["code"], txt, mode="loose_connection", joint_key=jk,
                    detail={"device": order["device"]})
        if not order["covers"]:
            res.add(order["code"], txt, detail={"device": order["device"]})
        res.flags.add(order["code"] if order["code"] in
                      ("DEVICE_MOUNT_LOST", "DEVICE_AIM_SHIFTED", "DEVICE_CELL_LOW")
                      else "DEVICE_FAULT")

    # ---- 7. current-THD gate ---------------------------------------------
    need = THD_I_GATE_FRACTION * assets.MAIN_CT_PRIMARY_A
    thd_i = [an.get(f"mpr.thd_i_l{p}_pct") for p in (1, 2, 3)]
    thd_i = [t for t in thd_i if t is not None]
    if thd_i and i_max < need:
        res.flags.add("THD_I_UNGATED")
        res.add("THD_I_UNGATED",
                reason_text("THD_I_UNGATED", i=i_max, gate=THD_I_GATE_FRACTION * 100.0,
                            need=need),
                mode="harmonic_neutral",
                detail={"i_max_a": i_max, "gate_a": need, "thd_i_pct": max(thd_i)})

    # ---- 8. learn week ----------------------------------------------------
    commissioned = history.get("commissioned")
    learn_until = live.learn_until
    if commissioned is not None and learn_until is None:
        learn_until = float(commissioned) + LEARN_WINDOW_S
    if learn_until is not None and now < float(learn_until):
        res.flags.add("LEARN_MODE")
        started = float(learn_until) - LEARN_WINDOW_S
        days = max(0.0, (now - started) / 86400.0)
        txt = reason_text("LEARN_WEEK", days=days)
        for m in IN_PANEL_MODES:
            res.add("LEARN_WEEK", txt, mode=m,
                    detail={"learn_until": learn_until, "day": round(days, 2),
                            "absolute_limits_armed": True})
        res.push(GRID_LLR, IN_PANEL_MODES)

    # ---- 9. operator maintenance mode -------------------------------------
    if history.get("maintenance"):
        res.flags.add("MAINTENANCE")
        txt = reason_text("MAINTENANCE")
        for m in IN_PANEL_MODES:
            res.add("MAINTENANCE", txt, mode=m, detail={})
        res.push(GRID_LLR, IN_PANEL_MODES)

    if res.suppressed:
        res.flags.add("SUPPRESSED")
    return res


# --------------------------------------------------------------------------
# apply
# --------------------------------------------------------------------------

def apply(live: PanelLive, store, history: dict) -> PanelLive:
    """Evaluate, persist every suppression with its reason, and annotate.

    Persistence is not optional and not a debug switch.  A suppression that is
    not written down is indistinguishable from a detection we never made.
    """
    res = evaluate(live, history)
    now = float(history.get("now") or live.ts or time.time())

    for s in res.suppressed:
        if store is not None:
            store.add_suppression(
                panel_key=live.panel_key,
                reason=s["reason_tr"],
                joint_key=s["joint_key"],
                mode=s["mode"],
                detail={"code": s["reason"], **(s["detail"] or {})},
            )
        live.suppressed.append(SuppressionView(
            ts=now, panel_key=live.panel_key, joint_key=s["joint_key"],
            mode=s["mode"], reason=s["reason_tr"],
            detail={"code": s["reason"], **(s["detail"] or {})},
        ))
    if store is not None and res.suppressed:
        store.commit()

    for f in sorted(res.flags):
        if f not in live.status_flags:
            live.status_flags.append(f)
    if res.flags & {"LEARN_MODE"}:
        live.learn_mode = True

    fusion.set_negative_evidence(live, res.negative_evidence)
    fusion.set_suppressed_joints(live, res.joints_out)
    setattr(live, "_panogoz_device_orders", res.device_orders)
    setattr(live, "_panogoz_suppression", res)
    return live


def device_orders(live: PanelLive) -> list[dict]:
    """Device work orders raised this cycle.  A drifting sensor produces one of
    these, never a retorque order."""
    return list(getattr(live, "_panogoz_device_orders", None) or [])


def result(live: PanelLive) -> SuppressionResult | None:
    return getattr(live, "_panogoz_suppression", None)


# --------------------------------------------------------------------------
# Self-test
# --------------------------------------------------------------------------

if __name__ == "__main__":  # pragma: no cover
    from panogoz.rules.fusion import _demo_live
    from panogoz.store.db import Store

    import tempfile
    import os

    print("=" * 78)
    print("PANO GOZ · suppression self-test")
    print("=" * 78)

    tmp = os.path.join(tempfile.mkdtemp(prefix="panogoz-supp-"), "t.db")
    store = Store(tmp)

    def show(tag: str, live: PanelLive, hist: dict) -> SuppressionResult:
        r = evaluate(live, hist)
        print(f"\n[{tag}]  flags = {sorted(r.flags)}")
        print(f"          negative evidence = "
              f"{ {k: round(v, 2) for k, v in r.negative_evidence.items()} }")
        seen: set[str] = set()
        for s in r.suppressed:
            if s["reason"] in seen:
                continue
            seen.add(s["reason"])
            print(f"          · {s['reason']}: {s['reason_tr'][:150]}")
        return r

    # 1. three-phase voltage THD
    live = _demo_live()
    live.analyser.update({"mpr.thd_v_l1_pct": 6.4, "mpr.thd_v_l2_pct": 6.1,
                          "mpr.thd_v_l3_pct": 6.9})
    live.joints[7].theta_k = 9.0
    live.joints[7].temp_c = 92.0
    hist: dict = {"now": 1_760_000_000.0}
    r = show("3-faz gerilim THD", live, hist)
    assert "GRID_DISTURBANCE" in r.flags
    assert r.negative_evidence["loose_connection"] == GRID_LLR

    # 2. inrush
    live2 = _demo_live()
    live2.analyser.update({"mpr.thd_i_l1_pct": 42.0})
    hist2 = {"now": 1_760_000_000.0,
             "load_factor": [(1_759_999_700.0, 0.01), (1_760_000_000.0, 0.62)]}
    r2 = show("trafo inrush", live2, hist2)
    assert "INRUSH" in r2.flags

    # 3. frequency
    live3 = _demo_live()
    live3.analyser["mpr.freq_hz"] = 49.12
    hist3 = {"now": 1_760_000_000.0}
    r3 = show("frekans penceresi", live3, hist3)
    assert "GRID_WINDOW" in r3.flags
    hist3["now"] = 1_760_000_000.0 + 300
    r3b = evaluate(live3, hist3)
    print(f"          +5 dk sonra hâlâ bastırılmış: {'GRID_WINDOW' in r3b.flags}")

    # 4. load step
    live4 = _demo_live()
    hist4 = {"now": 1_760_000_000.0,
             "load_factor": [(1_759_999_400.0, 0.40), (1_760_000_000.0, 0.78)]}
    r4 = show("yük sıçraması", live4, hist4)
    assert "LOAD_HOLD" in r4.flags

    # 5. sensitivity / de-energised
    live5 = _demo_live()
    live5.load_factor = 0.18
    r5 = show("görünürlük düşük", live5, {"now": 1_760_000_000.0})
    assert "SENSITIVITY_LOW" in r5.flags
    live5b = _demo_live()
    live5b.load_factor = 0.0
    live5b.analyser.update({"mpr.i_l1_a": 0.0, "mpr.i_l2_a": 0.0, "mpr.i_l3_a": 0.0})
    r5b = show("enerjisiz", live5b, {"now": 1_760_000_000.0})
    assert "DE_ENERGISED" in r5b.flags

    # 6. drifting sensor -> device work order, not a retorque order
    from panogoz.contracts.live import DeviceView
    live6 = _demo_live()
    live6.devices = [DeviceView(key=d.key, kind=d.kind, label=d.label, online=True)
                     for d in assets.DEVICES]
    live6.devices[1].faults = ["MOUNT_LOST"]
    hist6 = {"now": 1_760_000_000.0,
             "device_residual": {"TC-03": {"drift_k_per_day": 0.62}}}
    r6 = show("cihaz atfı", live6, hist6)
    print(f"          cihaz iş emirleri: "
          f"{[(o['device'], o['reason']) for o in r6.device_orders]}")
    print(f"          devre dışı bırakılan bağlantılar: {sorted(r6.joints_out)}")
    assert r6.joints_out, "device fault must take its joints out of the panel risk"
    assert all("tork" not in o["action_tr"].lower() or "etmeyin" in o["action_tr"]
               for o in r6.device_orders)

    # 7. THD-I gate
    live7 = _demo_live()
    for p in (1, 2, 3):
        live7.analyser[f"mpr.i_l{p}_a"] = 120.0
        live7.analyser[f"mpr.thd_i_l{p}_pct"] = 99.9
    r7 = show("akım THD kapısı", live7, {"now": 1_760_000_000.0})
    assert "THD_I_UNGATED" in r7.flags

    # 8. learn week, absolute limits still armed
    live8 = _demo_live()
    live8.learn_until = 1_760_100_000.0
    live8.joints[7].temp_c = 134.0
    live8.joints[7].theta_k = 20.0
    apply(live8, store, {"now": 1_760_000_000.0})
    fusion.apply(live8)
    print(f"\n[öğrenme haftası]  flags = {sorted(live8.status_flags)}")
    print(f"          HI = {live8.health_index:.1f}  severity = {live8.severity}")
    print(f"          mutlak limit ihlali = {fusion.absolute_breach(live8)}")
    assert live8.severity == "ACIL", live8.severity
    print("          ASSERT OK: öğrenme haftasında bile mutlak limit alarm üretir")

    rows = store.suppressions(since=0)
    print(f"\n[store]  {len(rows)} suppression rows written with their reasons")
    for row in rows[:3]:
        print(f"    · {row['mode']} / {row['joint_key']} :: {row['reason'][:110]}")

    print("\nOK")
