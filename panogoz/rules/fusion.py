"""Evidence fusion: many weak channels -> seven failure-mode risks -> one number.

Why this shape
--------------

A thermal monitoring system fails in the field in one of two ways.  Either it
alarms on everything, and is switched off in month three; or it alarms on
nothing, and is switched off in month twelve.  Both failures come from the same
root cause: a single channel crossing a single threshold decides the outcome.

So PANO GOZ never lets a channel decide.  Every observation enters as a
**capped log-likelihood ratio**::

    l = clamp( per_unit * (value - pivot), -2.2, +2.2 )

The cap is the whole point.  With a per-mode prior of roughly 2 %, a prior
logit of about -3.9, one channel pinned at its maximum can move a mode's risk
only to ``sigmoid(-3.9 + 2.2) = 0.16``.  A stuck sensor reading 200 C, an IR
array that has lost its aim, a CUSUM that has run away because somebody
re-torqued a joint - none of them can, alone, produce a KRITIK.  Two independent
channels can.  That is the two-channel dispatch rule, expressed in arithmetic
rather than in a policy document.

Modes are combined naive-Bayes: ``L_m = logit(prior_m) + sum_i c_i * l_i`` and
``r_m = sigmoid(L_m)``, where ``c_i`` is the coupling of evidence ``i`` to mode
``m``.  Naive Bayes over-counts correlated evidence, which is exactly why the
per-term cap and the modest priors exist, and why the *dispatch* decision is
gated on independent sensor families rather than on term count.

Health index
------------

::

    HI = 100 * prod_m (1 - r_m) ^ w_m

with the ``w_m`` from ``contracts.channels.FAILURE_MODES`` summing to 1.  Taking
logs, ``ln(HI/100) = sum_m w_m ln(1 - r_m)``: the deficit decomposes with no
attribution heuristic at all.  The waterfall reported to the UI uses the exact
telescoping partial products, so the ``delta_hi`` column sums to ``HI - 100``
to floating-point precision.  The self-test asserts that and prints the
residual.

Independent sensor families
---------------------------

Two agreeing channels means two *different measurement principles*, not two
statistics derived from the same thermometer:

===== ============================================================
TC    the clip's TMP117 on the cable core: theta, its CUSUM, its slope
IR    the MLX90640 array looking up at the lug row: absolute lug temperature
RF    HFCT / TEV / ultrasonic on the PE stud
ELEC  Entes MPR-53CS currents, THD, neutral
ARC   ABB TVOC-2 registers
ENV   SHT41 humidity, dewpoint, compartment air
===== ============================================================

theta and its CUSUM share a sensor, so they are one family.  A hot lug seen by
both the clip and the array is two.  This is why the day-1 kit deliberately
overlaps: six clips and one array both watch feeders 6 and 7.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Iterable

from panogoz.contracts import assets
from panogoz.contracts.channels import (
    FAILURE_MODES,
    MODES_BY_KEY,
    SEVERITIES,
    SEVERITY_RANK,
)
from panogoz.contracts.live import JointView, PanelLive
from panogoz.detector import engine as _det   # severity thresholds, one source of truth

# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------

#: No single observation may contribute more than this to a mode's log-odds.
#: With the priors below, one capped channel reaches r ~ 0.16 - visible on the
#: dashboard, nowhere near a dispatch.
LLR_CAP = 2.2

#: Per-mode prior probability that the mode is present on a randomly chosen
#: panel-day.  Deliberately small: most panels, most days, are fine.
PRIORS: dict[str, float] = {
    "loose_connection": 0.020,
    "overload": 0.030,
    "arc_integrity": 0.020,
    "thermal_runaway": 0.020,
    "harmonic_neutral": 0.030,
    "moisture": 0.020,
    "insulation": 0.015,
}

#: Sensor families.  Two agreeing FAMILIES are a dispatch; two agreeing terms
#: from one family are one opinion stated twice.
FAMILIES = ("TC", "IR", "RF", "ELEC", "ARC", "ENV")

FAMILY_LABELS_TR = {
    "TC": "Isıl kelepçe (TMP117)",
    "IR": "Termal dizi (MLX90640)",
    "RF": "RF / HFCT-TEV",
    "ELEC": "Enerji analizörü",
    "ARC": "Ark rölesi (TVOC-2)",
    "ENV": "Ortam (SHT41)",
}

#: A term must reach this much positive log-odds before its family counts as
#: "agreeing".  Stops a marginally-positive channel from unlocking a dispatch.
FAMILY_AGREE_LLR = 0.50

#: theta raise thresholds, kelvin at reference current.  Clearing happens at
#: ``HYSTERESIS`` times these (see ``rules.alarms``).
# Absolute-theta raise thresholds.  SOURCED FROM THE DETECTOR so the alarm
# console and the panel screen cannot grade the same joint differently -- two
# tables of numbers for one decision is how a monitoring system ends up arguing
# with itself in front of an operator.
#
# theta is delta-T OVER A SIMILAR COMPONENT, so the anchor is the thermography
# band set for that quantity (1-3 / 4-15 / >15 K), not the coarser 10/20/40 K
# set, which grades delta-T over AMBIENT.
THETA_RAISE: dict[str, float] = {
    "IZLE": _det.THETA_ABS_IZLE_K,
    "UYARI": _det.THETA_ABS_UYARI_K,
    "KRITIK": _det.THETA_ABS_KRITIK_K,
    "ACIL": _det.THETA_ABS_ACIL_K,
}

#: Absolute conductor-surface limits.  These are safety facts, not statistics:
#: they stay armed during the learn week and are exempt from the two-channel
#: cap, because a 130 C lug is a 130 C lug whether or not a second sensor agrees.
TEMP_RAISE: dict[str, float] = {"UYARI": 90.0, "KRITIK": 110.0, "ACIL": 130.0}

#: 40 % dead band: an alarm clears at 0.6x the level that raised it.
HYSTERESIS = 0.60

#: Health index -> severity.  Explicit, monotone, testable.
HI_SEVERITY: tuple[tuple[float, str], ...] = (
    (90.0, "BILGI"),
    (75.0, "IZLE"),
    (55.0, "UYARI"),
    (35.0, "KRITIK"),
    (0.0, "ACIL"),
)

#: Where a private, non-dataclass annotation is parked on a PanelLive.  These
#: are attributes, not fields, so ``asdict`` and the ICD encoder never see them.
DETAIL_ATTR = "_panogoz_fusion_detail"
NEG_ATTR = "_panogoz_negative_evidence"
SUPPRESSED_JOINTS_ATTR = "_panogoz_suppressed_joints"


def sigmoid(x: float) -> float:
    if x >= 0.0:
        return 1.0 / (1.0 + math.exp(-min(x, 700.0)))
    e = math.exp(max(x, -700.0))
    return e / (1.0 + e)


def logit(p: float) -> float:
    p = min(max(p, 1e-12), 1.0 - 1e-12)
    return math.log(p / (1.0 - p))


# --------------------------------------------------------------------------
# Evidence registry
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Evidence:
    """One observable turned into log-odds.

    ``pivot`` is the value at which the observation is neutral; ``per_unit`` is
    the log-odds gained per engineering unit above it.  ``monotone`` is -1 for
    observations where *less* is worse (condensation margin).  ``floor`` lets a
    corroborating channel say "I see nothing" without that becoming a strong
    argument for health - absence of evidence is weak evidence of absence.
    """

    name: str
    label_tr: str
    unit: str
    family: str
    pivot: float
    per_unit: float
    modes: tuple[tuple[str, float], ...]
    monotone: int = 1
    floor: float = -LLR_CAP
    ceil: float = LLR_CAP
    note: str = ""


def _e(*args: Any, **kw: Any) -> Evidence:
    ev = Evidence(*args, **kw)
    assert ev.family in FAMILIES, f"{ev.name}: unknown family {ev.family}"
    assert -LLR_CAP <= ev.floor <= 0.0 <= ev.ceil <= LLR_CAP, f"{ev.name}: bad clip"
    for mode, coupling in ev.modes:
        assert mode in MODES_BY_KEY, f"{ev.name}: unknown mode {mode}"
        assert 0.0 < coupling <= 1.0, f"{ev.name}: coupling out of range"
    return ev


EVIDENCE_LIST: tuple[Evidence, ...] = (
    # ---- TC family: the sibling-differential temperature and its drift ------
    _e("theta_k", "θ · anma akımında sıcaklık fazlası", "K", "TC",
       pivot=1.5, per_unit=0.32,
       modes=(("loose_connection", 1.0), ("thermal_runaway", 0.25)),
       note="[T - kardeş medyanı] / (I/I_ref)²; yükten ve ortamdan bağımsız"),
    _e("theta_cusum", "θ CUSUM istatistiği", "-", "TC",
       pivot=4.0, per_unit=0.35, modes=(("loose_connection", 0.85),),
       note="k=0.5 h=8, günlük medyan üzerinde"),
    _e("theta_slope", "θ eğimi", "K/hafta", "TC",
       pivot=0.15, per_unit=3.00, modes=(("loose_connection", 0.75),),
       note="Pozitif eğim bozulmanın sürdüğünü gösterir"),
    # ---- IR family: the independent look at the same lug --------------------
    _e("lug_temp_c", "Pabuç mutlak sıcaklığı", "°C", "IR",
       pivot=75.0, per_unit=0.060, floor=-1.20,
       modes=(("loose_connection", 0.45), ("thermal_runaway", 0.70), ("overload", 0.35)),
       note="MLX90640 dizisi; kalaylı baraya DEĞİL, pabuç ve kablo kılıfına bakar"),
    _e("lug_theta_ir_k", "Termal diziden θ", "K", "IR",
       pivot=2.5, per_unit=0.28, modes=(("loose_connection", 0.90),),
       note="Aynı pabuğun ikinci, bağımsız ölçümü; σ_m = 0.8 K"),
    # ---- RF family ----------------------------------------------------------
    _e("pd_qmax_db", "RF tepe genliği", "dB", "RF",
       pivot=25.0, per_unit=0.070, floor=-0.80,
       modes=(("insulation", 0.90), ("loose_connection", 0.35)),
       note="pC eşdeğeri, IEC 60270 izlenebilir DEĞİL"),
    _e("pd_rate_per_s", "RF darbe hızı", "1/s", "RF",
       pivot=200.0, per_unit=0.0040, floor=-0.60, modes=(("insulation", 0.60),)),
    _e("pd_trend_db_30d", "RF 30 günlük eğilim", "dB", "RF",
       pivot=3.0, per_unit=0.25, floor=-0.60, modes=(("insulation", 0.70),)),
    _e("tev_db", "TEV seviyesi", "dB", "RF",
       pivot=20.0, per_unit=0.060, floor=-0.60, modes=(("insulation", 0.55),)),
    _e("pd_yuzen_db", "Yüzen elektrot imzası", "dB", "RF",
       pivot=18.0, per_unit=0.060, floor=-0.40,
       modes=(("loose_connection", 0.60), ("insulation", 0.40)),
       note="Akım sıfır geçişlerinde kümelenen darbeler = seri ark"),
    _e("pd_surface_db", "Yüzey kaçağı imzası", "dB", "RF",
       pivot=15.0, per_unit=0.080, floor=-0.40,
       modes=(("moisture", 0.70), ("insulation", 0.45))),
    # ---- ELEC family --------------------------------------------------------
    _e("load_factor", "Yük faktörü", "-", "ELEC",
       pivot=0.85, per_unit=6.00, modes=(("overload", 1.0),)),
    _e("feeder_load_ratio", "En yüklü fider / anma", "-", "ELEC",
       pivot=0.90, per_unit=5.00, modes=(("overload", 0.85),)),
    _e("thd_i_max_pct", "En yüksek akım THD", "%", "ELEC",
       pivot=12.0, per_unit=0.090, floor=-0.80,
       modes=(("harmonic_neutral", 0.85),),
       note="I > CT anmasının %10'u değilse hiç değerlendirilmez (register %99.9'da doyar)"),
    _e("neutral_ratio", "I_N / faz ortalaması", "-", "ELEC",
       pivot=0.35, per_unit=3.00, modes=(("harmonic_neutral", 1.0),),
       note="Üçün katı harmonikler sıfır bileşendir, aritmetik toplanır: I_N = 3·h3·I1"),
    _e("k_n_slope", "K_N eğilimi", "µK/A²/hafta", "ELEC",
       pivot=0.0, per_unit=1.20, floor=-0.40,
       modes=(("loose_connection", 0.60), ("harmonic_neutral", 0.40)),
       note="K_N = ΔT_N / I_N². Kendi eğilimine göre yükseliyorsa nötr bağlantısı bozuluyor"),
    # ---- ARC family ---------------------------------------------------------
    _e("arc_detectors_missing", "Arızalı dedektör", "adet", "ARC",
       pivot=0.5, per_unit=1.20, modes=(("arc_integrity", 1.0),),
       note="TVOC-2 reg 222/223 bit sayımı; yalnız FW >= 03.00.00"),
    _e("arc_comms_lost", "Ark rölesi haberleşmesi yok", "-", "ARC",
       pivot=0.5, per_unit=3.00, modes=(("arc_integrity", 1.0),),
       note="Cihazın kendisi bunu bildiremez; bunu biz üretiriz"),
    _e("arc_active_error", "Aktif TVOC-2 hatası", "-", "ARC",
       pivot=0.5, per_unit=4.40, modes=(("arc_integrity", 1.0),),
       note="reg 1300 bit1 ile kapılanır; 200-212 tek başına 0 okuyabilir"),
    _e("arc_active_trip", "Aktif ark açması", "-", "ARC",
       pivot=0.5, per_unit=4.40, modes=(("arc_integrity", 1.0),),
       note="reg 1300 bit0. Bu bir çıkarım değil, SIL-2 bir cihazın açtığını "
            "bildirmesidir; iki kanal kuralından muaftır (absolute_breach)"),
    _e("arc_selftest_days", "Son otokontrolden beri", "gün", "ARC",
       pivot=180.0, per_unit=0.0080, floor=-0.80, modes=(("arc_integrity", 0.70),)),
    _e("arc_ambient_warn", "Ortam ışığı uyarısı", "adet", "ARC",
       pivot=0.5, per_unit=1.00, modes=(("arc_integrity", 0.60),),
       note="3000 Lux üzerinde dedektör körleşir"),
    _e("arc_not_fitted", "Ark rölesi takılı değil", "-", "ARC",
       pivot=0.5, per_unit=1.60, modes=(("arc_integrity", 0.80),)),
    # ---- ENV family ---------------------------------------------------------
    _e("air_temp_c", "Bölme havası", "°C", "ENV",
       pivot=45.0, per_unit=0.100, floor=-1.00,
       modes=(("thermal_runaway", 0.90), ("overload", 0.30)),
       note="Tablo 1 dahili: ortam max 40 °C, 24 saat ortalaması max 35 °C"),
    _e("air_rise_k", "Bölme havası - dış ortam", "K", "ENV",
       pivot=12.0, per_unit=0.120, floor=-0.80, modes=(("thermal_runaway", 0.80),)),
    _e("condensation_margin_k", "Yoğuşma payı", "K", "ENV",
       pivot=5.0, per_unit=0.30, monotone=-1, modes=(("moisture", 1.0),),
       note="En SOĞUK yüzeye göre; duvar sıcaklığı ortamın 90 dk'lık gecikmesi"),
    _e("rh_pct", "Bağıl nem", "%", "ENV",
       pivot=75.0, per_unit=0.050, floor=-0.80, modes=(("moisture", 0.60),)),
)

EVIDENCE: dict[str, Evidence] = {e.name: e for e in EVIDENCE_LIST}


def evidence_llr(name: str, value: float | None, **kw: Any) -> float:
    """Turn one observation into capped log-odds.

    ``pivot`` and ``per_unit`` may be overridden per call (a 250 A feeder and a
    400 A feeder do not share a pivot for absolute temperature).  ``gate=False``
    zeroes the term, which is how the current-THD registers are silenced below
    10 % of CT rating instead of being believed at their saturated 99.9 %.
    """
    ev = EVIDENCE.get(name)
    if ev is None:  # pragma: no cover - programmer error
        raise KeyError(f"unknown evidence {name!r}; add it to rules.fusion.EVIDENCE")
    if value is None or not kw.get("gate", True):
        return 0.0
    try:
        v = float(value)
    except (TypeError, ValueError):
        return 0.0
    if v != v:  # NaN
        return 0.0
    pivot = float(kw.get("pivot", ev.pivot))
    per_unit = float(kw.get("per_unit", ev.per_unit))
    raw = ev.monotone * per_unit * (v - pivot)
    out = max(ev.floor, min(ev.ceil, raw))
    assert abs(out) <= LLR_CAP + 1e-12
    return out


# --------------------------------------------------------------------------
# Suppression hand-off
# --------------------------------------------------------------------------

def negative_evidence(live: PanelLive) -> dict[str, float]:
    """Log-odds pushed in by ``rules.suppression``, per failure mode.

    Suppression runs FIRST in the pipeline precisely so that this dictionary
    exists before any risk is computed.  A grid-side disturbance that lights up
    all three phases together arrives here as -1.5 on every in-panel mode.
    """
    return dict(getattr(live, NEG_ATTR, None) or {})


def set_negative_evidence(live: PanelLive, neg: dict[str, float]) -> None:
    setattr(live, NEG_ATTR, dict(neg))


def detail(live: PanelLive) -> dict[str, Any]:
    """Per-term breakdown left behind by ``fuse``.  Read by ``rules.alarms``."""
    return dict(getattr(live, DETAIL_ATTR, None) or {})


# --------------------------------------------------------------------------
# Observation extraction
# --------------------------------------------------------------------------

def suppressed_joints(live: PanelLive) -> set[str]:
    """Joints whose thermal evidence ``rules.suppression`` has taken off the
    table for this cycle - a clip that has fallen off its cable, an array that
    has lost its aim, a sensor that is drifting.  Their readings are still
    stored and still shown; they simply do not get to raise a panel risk."""
    return set(getattr(live, SUPPRESSED_JOINTS_ATTR, None) or ())


def set_suppressed_joints(live: PanelLive, keys: Iterable[str]) -> None:
    setattr(live, SUPPRESSED_JOINTS_ATTR, set(keys))


def _monitored(live: PanelLive) -> list[JointView]:
    skip = suppressed_joints(live)
    return [j for j in live.joints if j.monitored and j.key not in skip]


def _worst_joint(live: PanelLive) -> JointView | None:
    cands = [j for j in _monitored(live) if j.theta_k is not None]
    if not cands:
        cands = [j for j in _monitored(live) if j.temp_c is not None]
    if not cands:
        return None
    return max(cands, key=lambda j: (j.theta_k if j.theta_k is not None else -1e9,
                                     j.temp_c if j.temp_c is not None else -1e9))


def observations(live: PanelLive) -> dict[str, float | None]:
    """Pull every evidence input out of the live image.

    Panel-level channels are taken as they are; joint-level channels are taken
    at their worst monitored joint, because the panel's risk is set by its worst
    connection and not by the average of forty healthy ones.
    """
    o: dict[str, float | None] = {k: None for k in EVIDENCE}
    js = _monitored(live)

    thetas = [j.theta_k for j in js if j.theta_k is not None]
    if thetas:
        o["theta_k"] = max(thetas)
    cus = [j.cusum for j in js if j.cusum]
    if cus:
        o["theta_cusum"] = max(cus)
    sl = [j.slope_k_per_week for j in js if j.slope_k_per_week]
    if sl:
        o["theta_slope"] = max(sl)
    temps = [j.temp_c for j in js if j.temp_c is not None]
    if temps:
        o["lug_temp_c"] = max(temps)

    cur = [(j.current_a, j.rated_a) for j in js if j.current_a is not None and j.rated_a]
    if cur:
        o["feeder_load_ratio"] = max(c / r for c, r in cur)

    an = live.analyser or {}
    env = live.env or {}
    pd = live.pd
    arc = live.arc

    if live.load_factor:
        o["load_factor"] = live.load_factor

    phases = [an.get(f"mpr.i_l{p}_a") for p in (1, 2, 3)]
    phases = [p for p in phases if p is not None]
    i_max = max(phases) if phases else 0.0
    # The UI reports mean busbar loading; overload evidence must also see an
    # overloaded phase even when the other two phases keep that mean low.
    if phases:
        o["load_factor"] = max(live.load_factor, i_max / assets.MAIN_BUSBAR_RATED_A)
    # Current-THD registers saturate at 99.9 %.  At light load the value is
    # meaningless, so the term is gated out entirely rather than believed.
    thd_gate = i_max >= 0.10 * assets.MAIN_CT_PRIMARY_A
    thd_i = [an.get(f"mpr.thd_i_l{p}_pct") for p in (1, 2, 3)]
    thd_i = [t for t in thd_i if t is not None]
    if thd_i and thd_gate:
        o["thd_i_max_pct"] = max(thd_i)
    i_n = an.get("mpr.i_n_a")
    if i_n is not None and phases and sum(phases) > 0:
        o["neutral_ratio"] = i_n / (sum(phases) / len(phases))

    if arc.fitted:
        if arc.detectors_total:
            o["arc_detectors_missing"] = float(max(0, arc.detectors_total - arc.detectors_ok))
        o["arc_comms_lost"] = 0.0 if arc.online else 1.0
        o["arc_active_error"] = 1.0 if arc.active_error else 0.0
        # The trip itself.  It also travels the absolute_breach path, which is
        # what actually forces ACIL; this term exists so the risk figure and the
        # evidence list an operator reads agree with the badge above them.
        o["arc_active_trip"] = 1.0 if arc.active_trip else 0.0
        o["arc_selftest_days"] = float(min(arc.last_selftest_days, 3650))
        o["arc_ambient_warn"] = float(arc.ambient_warn)
        o["arc_not_fitted"] = 0.0
    else:
        o["arc_not_fitted"] = 1.0

    if env.get("env.air_c") is not None:
        o["air_temp_c"] = env["env.air_c"]
    if env.get("env.air_c") is not None and env.get("env.ambient_c") is not None:
        o["air_rise_k"] = env["env.air_c"] - env["env.ambient_c"]
    if env.get("env.condensation_margin_k") is not None:
        o["condensation_margin_k"] = env["env.condensation_margin_k"]
    if env.get("env.rh_pct") is not None:
        o["rh_pct"] = env["env.rh_pct"]

    if pd.qmax_db:
        o["pd_qmax_db"] = pd.qmax_db
    if pd.rate_per_s:
        o["pd_rate_per_s"] = pd.rate_per_s
    if pd.trend_db_30d:
        o["pd_trend_db_30d"] = pd.trend_db_30d
    if pd.tev_db:
        o["tev_db"] = pd.tev_db
    if pd.klass == "YUZEN" and pd.qmax_db:
        o["pd_yuzen_db"] = pd.qmax_db
    if pd.klass == "YUZEY" and pd.qmax_db:
        o["pd_surface_db"] = pd.qmax_db

    # Optional second-opinion channels that the detector may have filled in.
    extra = getattr(live, "_panogoz_extra_obs", None) or {}
    for k, v in extra.items():
        if k in o:
            o[k] = v
    return o


def set_extra_observations(live: PanelLive, obs: dict[str, float]) -> None:
    """Inject observations the live image has no field for (IR second opinion,
    K_N trend).  Used by the detector and by the tests."""
    cur = dict(getattr(live, "_panogoz_extra_obs", None) or {})
    cur.update(obs)
    setattr(live, "_panogoz_extra_obs", cur)


# --------------------------------------------------------------------------
# Fusion
# --------------------------------------------------------------------------

def fuse(live: PanelLive) -> dict[str, float]:
    """Seven failure-mode risks in 0..1.

    Leaves a full per-term breakdown on the live image (see ``detail``) so the
    alarm layer can show its work rather than assert a conclusion.
    """
    obs = observations(live)
    neg = negative_evidence(live)

    terms: dict[str, dict[str, Any]] = {}
    for name, ev in EVIDENCE.items():
        value = obs.get(name)
        if value is None:
            continue
        l = evidence_llr(name, value)
        terms[name] = {
            "value": value,
            "llr": l,
            "family": ev.family,
            "label_tr": ev.label_tr,
            "unit": ev.unit,
            "modes": {m: c for m, c in ev.modes},
        }

    per_mode: dict[str, dict[str, Any]] = {}
    risks: dict[str, float] = {}
    for m in FAILURE_MODES:
        L = logit(PRIORS.get(m.key, 0.02))
        contribs: list[dict[str, Any]] = []
        for name, t in terms.items():
            c = t["modes"].get(m.key)
            if not c:
                continue
            add = c * t["llr"]
            contribs.append({
                "evidence": name,
                "label_tr": t["label_tr"],
                "family": t["family"],
                "value": t["value"],
                "unit": t["unit"],
                "llr": t["llr"],
                "coupling": c,
                "delta_logodds": add,
            })
            L += add
        supp = float(neg.get(m.key, 0.0))
        if supp:
            L += supp
            contribs.append({
                "evidence": "suppression",
                "label_tr": "Bastırma (şebeke/geçici olay)",
                "family": "ELEC",
                "value": None,
                "unit": "-",
                "llr": supp,
                "coupling": 1.0,
                "delta_logodds": supp,
            })
        contribs.sort(key=lambda d: -abs(d["delta_logodds"]))
        r = sigmoid(L)
        risks[m.key] = r
        per_mode[m.key] = {
            "label_tr": m.label_tr,
            "prior": PRIORS.get(m.key, 0.02),
            "log_odds": L,
            "risk": r,
            "terms": contribs,
            "families": sorted({
                c["family"] for c in contribs if c["delta_logodds"] >= FAMILY_AGREE_LLR
            }),
        }

    setattr(live, DETAIL_ATTR, {
        "observations": {k: v for k, v in obs.items() if v is not None},
        "terms": terms,
        "modes": per_mode,
        "families": agreeing_families(per_mode),
        "negative_evidence": neg,
    })
    return risks


def agreeing_families(per_mode: dict[str, dict[str, Any]]) -> list[str]:
    """Distinct sensor families that positively support at least one mode."""
    fams: set[str] = set()
    for info in per_mode.values():
        fams.update(info.get("families", ()))
    return [f for f in FAMILIES if f in fams]


def health_index(risks: dict[str, float]) -> tuple[float, list[dict]]:
    """``HI = 100 * prod (1-r)^w`` plus its exact waterfall.

    ``delta_hi`` uses the telescoping partial products, so the column sums to
    ``HI - 100`` exactly - no attribution heuristic, no normalisation fudge.
    ``contribution`` is the additive log-space share, ``w_m * ln(1-r_m)``, which
    is what you want when comparing modes on a log axis.
    """
    prod = 1.0
    waterfall: list[dict] = []
    for m in FAILURE_MODES:
        r = float(risks.get(m.key, 0.0))
        r = min(max(r, 0.0), 1.0 - 1e-9)
        prev = prod
        prod *= (1.0 - r) ** m.weight
        waterfall.append({
            "mode": m.key,
            "label_tr": m.label_tr,
            "risk": r,
            "weight": m.weight,
            "contribution": m.weight * math.log(1.0 - r),
            "delta_hi": 100.0 * (prod - prev),
        })
    return 100.0 * prod, waterfall


# --------------------------------------------------------------------------
# Severity
# --------------------------------------------------------------------------

def severity_from_hi(hi: float) -> str:
    for floor_hi, sev in HI_SEVERITY:
        if hi >= floor_hi:
            return sev
    return "ACIL"


def joint_severity(j: JointView) -> str:
    """Severity of one joint.

    ONE SOURCE OF TRUTH.  The detector already graded this joint, weighing two
    things this module cannot see: the daily median rather than the live sample,
    and the rise above the joint's own commissioned baseline.  Both matter --
    every bolted joint carries a manufacturing offset against its siblings, so a
    lug baselined at -2 K would need a 7 K excursion to trip an absolute 5 K gate
    while one baselined at +4 K would trip on a 1 K wobble.

    Recomputing severity here from absolute theta alone used to silently
    override that judgement, which meant the alarm console and the panel screen
    could disagree about the same joint.  So we trust ``j.severity`` and only
    fall back to a local computation when the detector left it unset.

    Absolute temperature limits are re-applied on top regardless, because they
    are a safety floor that no differential statistic may lower.
    """
    sev = j.severity if j.severity in SEVERITY_RANK else "BILGI"

    # Only a snapshot with no detector decision uses the instantaneous theta
    # fallback. Explicit BILGI/KRITIK decisions include context absent here.
    if j.severity not in SEVERITY_RANK and j.theta_k is not None:
        detectable = j.theta_min_k is None or j.theta_k >= j.theta_min_k
        if detectable:
            for name in ("ACIL", "KRITIK", "UYARI", "IZLE"):
                if j.theta_k >= THETA_RAISE[name]:
                    if SEVERITY_RANK[name] > SEVERITY_RANK[sev]:
                        sev = name
                    break

    if j.temp_c is not None:
        for name in ("ACIL", "KRITIK", "UYARI"):
            if j.temp_c >= TEMP_RAISE[name]:
                if SEVERITY_RANK[name] > SEVERITY_RANK[sev]:
                    sev = name
                break
    return sev


def absolute_breach(live: PanelLive) -> str | None:
    """Highest severity justified by a FACT rather than by an inference.

    Everything else in this module is statistics: capped evidence, naive-Bayes
    fusion, a two-channel dispatch rule.  That machinery exists so that no
    single noisy channel can raise an alarm on its own, and it is the right
    default for a differential quantity like theta.

    Two things are not statistics, and must not be filtered through it:

    * **An absolute conductor temperature.**  A 130 C lug is a 130 C lug whether
      or not a second sensor agrees, and the limit stays armed through the learn
      week.
    * **An active arc trip.**  Register 1300 bit 0 is a SIL-2 certified device
      reporting that it has already fired its trip contacts.  Demanding a second
      opinion before telling anyone would be absurd - and on this panel it
      matters more than usual, because there is no LV incoming breaker, so the
      fault was cleared from the MV side and the substation is now dark.

    theta is never an absolute limit: it is a differential statistic and it
    needs corroboration.
    """
    worst: str | None = None

    arc = live.arc
    if arc.fitted and arc.active_trip:
        worst = "ACIL"
    elif arc.fitted and arc.active_error:
        worst = "UYARI"

    temps = [j.temp_c for j in _monitored(live) if j.temp_c is not None]
    if temps:
        t = max(temps)
        for name in ("ACIL", "KRITIK", "UYARI"):
            if t >= TEMP_RAISE[name]:
                if worst is None or SEVERITY_RANK[name] > SEVERITY_RANK[worst]:
                    worst = name
                break
    return worst


def panel_severity(live: PanelLive, hi: float, risks: dict[str, float]) -> tuple[str, dict]:
    """Panel severity, with the two-channel cap applied and explained.

    The mapping, stated once so it can be tested:

    1. ``severity_from_hi(HI)`` gives a baseline from the fused risk.
    2. The worst monitored joint's own grade can raise it.
    3. Panel state flags (DE_ENERGISED, SENSITIVITY_LOW, LEARN_MODE, STALE)
       cap the result at IZLE - we are blind, not calm.
    4. Fewer than two agreeing sensor families caps the result at UYARI.
       One channel is a WATCH, two are a DISPATCH.
    5. An absolute temperature breach overrides 3 and 4 upward.  A 130 C lug
       does not wait for a second opinion.
    """
    d = detail(live)
    fams = d.get("families", [])
    base = severity_from_hi(hi)
    worst = "BILGI"
    for j in _monitored(live):
        s = joint_severity(j)
        if SEVERITY_RANK[s] > SEVERITY_RANK[worst]:
            worst = s
    sev = base if SEVERITY_RANK[base] >= SEVERITY_RANK[worst] else worst

    reasons: list[str] = []
    blind = {"DE_ENERGISED", "SENSITIVITY_LOW", "LEARN_MODE", "STALE"} & set(live.status_flags)
    if blind and SEVERITY_RANK[sev] > SEVERITY_RANK["IZLE"]:
        sev = "IZLE"
        reasons.append("Modül durumu (" + ", ".join(sorted(blind)) + ") nedeniyle IZLE ile sınırlandı")
    if len(fams) < 2 and SEVERITY_RANK[sev] > SEVERITY_RANK["UYARI"]:
        sev = "UYARI"
        reasons.append(
            "Tek kanal teyidi (" + (", ".join(fams) or "yok") + ") — iki bağımsız kanal "
            "olmadan ekip yönlendirilmez"
        )
    ab = absolute_breach(live)
    if ab and SEVERITY_RANK[ab] > SEVERITY_RANK[sev]:
        sev = ab
        reasons.append(f"Mutlak sıcaklık limiti aşıldı → {ab} (öğrenme haftasında da aktiftir)")
    return sev, {
        "hi_severity": base,
        "worst_joint_severity": worst,
        "families": fams,
        "absolute_breach": ab,
        "caps": reasons,
    }


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------

def apply(live: PanelLive) -> PanelLive:
    """Fill ``risks``, ``hi_waterfall``, ``health_index`` and ``severity``."""
    risks = fuse(live)
    hi, waterfall = health_index(risks)
    skip = suppressed_joints(live)
    for j in live.joints:
        if not j.monitored:
            continue
        if j.key in skip:
            # Graded BILGI, not "healthy": the suppression table carries the
            # reason and the device work order carries the fix.
            j.severity = "BILGI"
            continue
        j.severity = joint_severity(j)
    sev, why = panel_severity(live, hi, risks)

    live.risks = risks
    live.hi_waterfall = waterfall
    live.health_index = round(hi, 2)
    live.severity = sev
    d = detail(live)
    d["severity"] = why
    d["health_index"] = hi
    setattr(live, DETAIL_ATTR, d)
    return live


# --------------------------------------------------------------------------
# Self-test
# --------------------------------------------------------------------------

def _demo_live(**kw: Any) -> PanelLive:
    from panogoz.contracts.live import ArcView, PdView

    js: list[JointView] = []
    for j in assets.monitored_joints():
        js.append(JointView(
            key=j.key, label=j.label, zone=j.zone, conductor=j.conductor,
            feeder_index=j.feeder_index, rated_a=j.rated_a, monitored=True,
            temp_c=42.0, sibling_median_c=41.5, current_a=180.0, load_factor=0.45,
            theta_k=0.4, theta_min_k=1.5, sensitivity_pct=70.0,
        ))
    live = PanelLive(
        panel_key="SOKE-14", panel_index=14, site="Soke", name="Soke-14", dso="ADM",
        joints=js,
        env={"env.air_c": 33.0, "env.ambient_c": 27.0, "env.rh_pct": 55.0,
             "env.condensation_margin_k": 9.0},
        analyser={"mpr.i_l1_a": 900.0, "mpr.i_l2_a": 1020.0, "mpr.i_l3_a": 830.0,
                  "mpr.i_n_a": 180.0, "mpr.thd_i_l1_pct": 8.0, "mpr.thd_i_l2_pct": 9.0,
                  "mpr.thd_i_l3_pct": 7.5, "mpr.thd_v_l1_pct": 2.1,
                  "mpr.thd_v_l2_pct": 2.0, "mpr.thd_v_l3_pct": 2.2,
                  "mpr.freq_hz": 50.01},
        load_factor=0.40,
        arc=ArcView(fitted=True, online=True, detectors_ok=10, detectors_total=10,
                    last_selftest_days=30, selftest_enabled=False),
        pd=PdView(rate_per_s=40.0, qmax_db=14.0, tev_db=11.0, klass="GURULTU",
                  klass_label="Gürültü"),
    )
    for k, v in kw.items():
        setattr(live, k, v)
    return live


if __name__ == "__main__":  # pragma: no cover
    import json

    print("=" * 78)
    print("PANO GOZ · fusion self-test")
    print("=" * 78)

    print(f"\n{len(EVIDENCE)} evidence definitions over {len(FAMILIES)} sensor families")
    print(f"LLR cap = {LLR_CAP};  one capped channel reaches risk "
          f"{sigmoid(logit(0.02) + LLR_CAP):.4f} against a 2 % prior")

    # -- 1. healthy panel --------------------------------------------------
    live = _demo_live()
    apply(live)
    print(f"\n[healthy]  HI = {live.health_index:.2f}  severity = {live.severity}")
    for w in live.hi_waterfall:
        print(f"    {w['mode']:<18} r={w['risk']:.4f} w={w['weight']:.2f} "
              f"ln-share={w['contribution']:+.5f} ΔHI={w['delta_hi']:+.4f}")

    # -- 2. waterfall closes exactly --------------------------------------
    risks = {m.key: 0.05 + 0.11 * i for i, m in enumerate(FAILURE_MODES)}
    hi, wf = health_index(risks)
    total = sum(w["delta_hi"] for w in wf)
    residual = total - (hi - 100.0)
    ln_total = sum(w["contribution"] for w in wf)
    ln_residual = ln_total - math.log(hi / 100.0)
    print(f"\n[waterfall]  HI = {hi:.6f}   sum(ΔHI) = {total:.6f}   "
          f"HI-100 = {hi - 100.0:.6f}")
    print(f"             residual = {residual:.3e}   ln-residual = {ln_residual:.3e}")
    assert abs(residual) < 1e-9, residual
    assert abs(ln_residual) < 1e-9, ln_residual
    print("             ASSERT OK: waterfall sums exactly to the deficit")

    # -- 3. one channel at maximum evidence -------------------------------
    solo = _demo_live()
    for j in solo.joints:
        j.temp_c = None            # no IR opinion
        j.sibling_median_c = None
        j.theta_k = 0.4
    solo.joints[7].theta_k = 400.0  # absurd, pinned at the cap
    solo.pd.qmax_db = 0.0
    solo.pd.tev_db = 0.0
    solo.pd.rate_per_s = 0.0
    apply(solo)
    d = detail(solo)
    print(f"\n[single channel at max]  families = {d['families']}")
    print(f"    risk(loose_connection) = {solo.risks['loose_connection']:.4f}")
    print(f"    HI = {solo.health_index:.2f}   severity = {solo.severity}")
    print(f"    caps: {d['severity']['caps']}")
    assert SEVERITY_RANK[solo.severity] <= SEVERITY_RANK["UYARI"], solo.severity
    print("             ASSERT OK: one channel cannot reach KRITIK")

    # -- 4. two agreeing families ------------------------------------------
    two = _demo_live()
    two.joints[7].theta_k = 14.0
    two.joints[7].temp_c = 96.0
    two.joints[7].cusum = 19.0
    two.joints[7].slope_k_per_week = 0.9
    apply(two)
    d2 = detail(two)
    print(f"\n[two families]  families = {d2['families']}")
    print(f"    risk(loose_connection) = {two.risks['loose_connection']:.4f}")
    print(f"    HI = {two.health_index:.2f}   severity = {two.severity}")
    assert SEVERITY_RANK[two.severity] >= SEVERITY_RANK["KRITIK"], two.severity
    print("             ASSERT OK: two independent families reach dispatch grade")

    print("\n[top terms for loose_connection]")
    for t in d2["modes"]["loose_connection"]["terms"][:6]:
        v = "-" if t["value"] is None else f"{t['value']:.2f}"
        print(f"    {t['family']:<5} {t['evidence']:<22} {v:>8} {t['unit']:<5} "
              f"llr={t['llr']:+.3f} x{t['coupling']:.2f} = {t['delta_logodds']:+.3f}")

    print("\n[severity mapping]")
    for hi_v in (99, 92, 88, 80, 70, 60, 50, 40, 30, 10):
        print(f"    HI {hi_v:>3} -> {severity_from_hi(float(hi_v))}")

    print("\nOK")
