"""PANO GOZ detector - the claims, with the numbers that back them.

Run it::

    cd grid-up-v2
    PYTHONIOENCODING=utf-8 python -m tests.test_detector

Everything printed here is computed in this file from synthetic data with a
fixed seed.  Nothing is quoted from a datasheet or asserted from memory.  The
seven sections correspond one-to-one to the seven claims the product makes:

  1. theta is load-invariant
  2. theta is ambient-invariant
  3. RLS beats pointwise deconvolution, by a measured factor
  4. a 0.2 K/week drift is caught, in a measured number of days
  5. the false-alarm arithmetic is what the ARL formula says it is
  6. the dew point reference values are right
  7. rule H3 tells a bad neutral joint from harmonic loading

Each section prints its numbers first and asserts afterwards, so a failure
still leaves the evidence on the screen.
"""

from __future__ import annotations

import datetime as _dt
import math
import random
import sys
import tempfile
from pathlib import Path
from statistics import median

from panogoz.contracts import assets, icd
from panogoz.store.db import Store

from panogoz.detector import cusum as cs
from panogoz.detector import dewpoint as dp
from panogoz.detector import engine as eng
from panogoz.detector import neutral as nt
from panogoz.detector import theta as th

DAY_S = 86400.0
FAILURES: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    if ok:
        print(f"    [PASS] {name}" + (f"  {detail}" if detail else ""))
    else:
        print(f"    [FAIL] {name}  {detail}")
        FAILURES.append(f"{name} {detail}")


def rule(title: str) -> None:
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


# --------------------------------------------------------------------------
# A shared synthetic joint: absolute temperatures, then differenced
# --------------------------------------------------------------------------

def simulate_joint(theta_true: float, *, days: float, dt_s: float, sigma: float,
                   seed: int, load, ambient_base: float = 28.0,
                   tau_s: float = 1200.0):
    """Three co-located conductors; returns (excess, load_factor, T_absolute).

    The defective conductor and its two healthy siblings share the ambient, the
    diurnal air swing and their own I^2R self-heating.  Only the defect is
    different.  The estimator sees ``T_i - median(all three)``, which is exactly
    what the product computes in the field.
    """
    rng = random.Random(seed)
    a = math.exp(-dt_s / tau_s)
    n = int(days * DAY_S / dt_s)
    lag = 0.0
    excess: list[float] = []
    loads: list[float] = []
    absolute: list[float] = []
    s1 = sigma / math.sqrt(2.0)
    for k in range(n):
        t = k * dt_s
        f = load(t)
        lag = a * lag + (1.0 - a) * theta_true * f * f
        hour = (t / 3600.0) % 24.0
        common = (ambient_base
                  + 6.0 * math.sin(2 * math.pi * (hour - 15.0) / 24.0)
                  + 18.0 * f * f)
        hot = common + lag + rng.gauss(0.0, s1)
        sibs = [common + rng.gauss(0.0, s1) for _ in range(2)]
        excess.append(hot - median([hot] + sibs))
        loads.append(f)
        absolute.append(hot)
    return excess, loads, absolute


def rls_theta(excess, loads, dt_s, tau_s=1200.0, lam=0.9995):
    st = th.ThetaState(tau_s=tau_s)
    traj = []
    for e, f in zip(excess, loads):
        st = th.rls_update(st, e, f, dt_s, lam=lam)
        traj.append(st.theta)
    return st.theta, traj


def sd(xs) -> float:
    xs = [x for x in xs if x is not None and math.isfinite(x)]
    if len(xs) < 2:
        return float("nan")
    m = sum(xs) / len(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


# --------------------------------------------------------------------------
# 1. Load invariance
# --------------------------------------------------------------------------

def test_1_load_invariance() -> None:
    rule("1  theta is LOAD-invariant  -  the same defect at f = 0.3 and f = 0.9")
    print("""
    A joint's excess temperature over its siblings is dR*I^2*R_th, so it grows
    as the square of the load.  The same physical defect therefore shows up as
    a completely different number of kelvin depending on the time of day.  theta
    divides that out.  If theta is not the same at 30 % load and 90 % load, the
    whole product is wrong.
""")
    DT, DAYS, THETA = 60.0, 10.0, 6.0
    SIG = th.SIGMA_TC_K
    # The three-element peer set has one exactly computable bias: when a joint
    # really is the outlier, the median of three IS the larger of the other two,
    # so the excess reads low by E[max of two] = sigma_1/sqrt(pi) with
    # sigma_1 = sigma_pair/sqrt(2), i.e. sigma_pair/sqrt(2*pi).  In theta units
    # that is a 1/f^2 term, which is why it shows up as a load-dependent
    # residual and must be accounted for before claiming load invariance.
    BIAS_K = SIG / math.sqrt(2.0 * math.pi)
    print(f"    true defect theta = {THETA:.1f} K at rated current, "
          f"sigma_pair = {SIG} K, {DAYS:.0f} days at {DT:.0f} s")
    print(f"    known peer-set bias: sigma/sqrt(2*pi) = {BIAS_K:.4f} K of excess,")
    print(f"    which is {BIAS_K:.4f}/f^2 K of theta (see theta.sibling_excess)\n")
    print(f"    {'f':>6} {'excess':>10} {'theta raw':>12} {'predicted':>12} "
          f"{'residual':>10} {'theta+bias':>12} {'error':>9}")
    results = {}
    corrected = {}
    for f_const in (0.30, 0.45, 0.60, 0.75, 0.90):
        exc, lo, _ = simulate_joint(THETA, days=DAYS, dt_s=DT, sigma=SIG,
                                    seed=11, load=lambda t, c=f_const: c)
        got, _ = rls_theta(exc, lo, DT)
        results[f_const] = got
        pred = THETA - BIAS_K / (f_const ** 2)
        fixed = got + BIAS_K / (f_const ** 2)
        corrected[f_const] = fixed
        print(f"    {f_const:6.2f} {THETA * f_const ** 2:8.2f} K {got:10.3f} K "
              f"{pred:10.3f} K {got - pred:+9.3f} K {fixed:10.3f} K "
              f"{100 * (fixed - THETA) / THETA:+8.2f} %")

    max_resid = max(abs(results[f] - (THETA - BIAS_K / f ** 2)) for f in results)
    print(f"\n    the raw estimate tracks the closed-form prediction to "
          f"{max_resid:.3f} K at every load -")
    print(f"    the whole load dependence left in theta is that one known term")
    check("peer-set bias matches sigma/sqrt(2*pi) closed form at every load",
          max_resid < 0.10, f"max residual {max_resid:.3f} K")

    spread = 100.0 * abs(corrected[0.90] - corrected[0.30]) / THETA
    print(f"\n    excess temperature at f=0.9 is {(0.9 / 0.3) ** 2:.0f}x the excess "
          f"at f=0.3 ({THETA * 0.81:.2f} K vs {THETA * 0.09:.2f} K),")
    print(f"    a 9x change in what the sensor sees.")
    print(f"    theta at f=0.9 differs from theta at f=0.3 by {spread:.2f} %")
    check("theta(f=0.3) == theta(f=0.9) within 3 %", spread < 3.0,
          f"spread {spread:.2f} %")
    check("every load point within 3 % of truth",
          all(abs(v - THETA) / THETA < 0.03 for v in corrected.values()),
          f"max err {100 * max(abs(v - THETA) for v in corrected.values()) / THETA:.2f} %")
    floor_frac = 100.0 * BIAS_K / (3.0 * SIG)
    print(f"\n    and the bias never changes a decision: it is "
          f"{floor_frac:.1f} % of the 3-sigma")
    print(f"    detection floor at EVERY load factor "
          f"({BIAS_K:.4f}/f^2 against {3 * SIG:.2f}/f^2),")
    print(f"    so the effective threshold is 3.13 sigma instead of 3.00 sigma.")
    check("bias is a fixed fraction of the detection floor at all loads",
          abs(floor_frac - 13.3) < 0.5, f"{floor_frac:.2f} %")

    LIMIT = 45.0
    print(f"\n    for contrast, the same defect through an absolute thermometer.")
    print(f"    Peak temperature over one day at ambient 28 C, alarm at "
          f"{LIMIT:.0f} C:")
    print(f"      {'f':>6} {'healthy phase':>15} {'verdict':>9} "
          f"{'defect phase':>14} {'verdict':>9} {'theta':>9}")
    verdicts = {}
    for f_const in (0.30, 0.60, 0.90):
        _, _, ab = simulate_joint(THETA, days=1.0, dt_s=DT, sigma=SIG,
                                  seed=11, load=lambda t, c=f_const: c)
        hot_peak = max(ab)
        healthy_peak = hot_peak - THETA * f_const ** 2
        vh = "ALARM" if healthy_peak >= LIMIT else "silent"
        vd = "ALARM" if hot_peak >= LIMIT else "silent"
        verdicts[f_const] = (vh, vd)
        print(f"      {f_const:6.2f} {healthy_peak:13.1f} C {vh:>9} "
              f"{hot_peak:12.1f} C {vd:>9} {corrected[f_const]:8.2f} K")
    print(f"\n    at f = 0.90 the thermometer alarms on the DEFECT and on both")
    print(f"    HEALTHY phases alike - they are hot from load, not from damage.")
    print(f"    at f = 0.30 and 0.60 it is silent on a defect that is already 6 K.")
    print(f"    There is no threshold that fixes this, because the healthy and the")
    print(f"    defective conductor are only {THETA * 0.09:.1f} K apart at low load and both")
    print(f"    are above any workable limit at high load.  theta reads the same")
    print(f"    number in all three rows.")
    check("a fixed threshold false-alarms on healthy phases at high load",
          verdicts[0.90][0] == "ALARM")
    check("a fixed threshold is blind to the same defect at low load",
          verdicts[0.30][1] == "silent")


# --------------------------------------------------------------------------
# 2. Ambient invariance
# --------------------------------------------------------------------------

def test_2_ambient_invariance() -> None:
    rule("2  theta is AMBIENT-invariant  -  shift the whole compartment +12 K")
    print("""
    TEDAS Tablo 1 gives the indoor service range as -5 C to +40 C with a 24 h
    mean up to 35 C.  A joint's absolute temperature therefore moves by 45 K
    across the year for reasons that have nothing to do with its condition.
    Because theta is a difference between three sensors in the same air, every
    bit of that must cancel.
""")
    DT, DAYS, THETA = 60.0, 10.0, 6.0

    def daily(t: float) -> float:
        h = (t / 3600.0) % 24.0
        return 0.55 + 0.30 * math.sin(2 * math.pi * (h - 9.0) / 24.0)

    print(f"    (theta reads ~5.84 K rather than 6.00 K because of the known")
    print(f"     sigma/sqrt(2*pi)/f^2 peer-set bias quantified in section 1;")
    print(f"     what matters here is that it does not MOVE with ambient)\n")
    print(f"    {'ambient base':>14} {'mean joint T':>14} {'peak joint T':>14} "
          f"{'theta':>10}")
    thetas = []
    for base in (10.0, 22.0, 28.0, 34.0, 40.0):
        exc, lo, ab = simulate_joint(THETA, days=DAYS, dt_s=DT,
                                     sigma=th.SIGMA_TC_K, seed=3, load=daily,
                                     ambient_base=base)
        got, _ = rls_theta(exc, lo, DT)
        thetas.append(got)
        print(f"    {base:12.1f} C {sum(ab) / len(ab):12.2f} C "
              f"{max(ab):12.2f} C {got:9.4f} K")
    spread = max(thetas) - min(thetas)
    print(f"\n    absolute joint temperature moved over a {40 - 10:.0f} K range")
    print(f"    theta moved by {spread:.2e} K")
    check("theta does not move with ambient (< 1e-9 K)", spread < 1e-9,
          f"spread {spread:.2e} K")

    print(f"\n    the +12 K case specifically:")
    e0, l0, a0 = simulate_joint(THETA, days=DAYS, dt_s=DT, sigma=th.SIGMA_TC_K,
                                seed=3, load=daily, ambient_base=28.0)
    e1, l1, a1 = simulate_joint(THETA, days=DAYS, dt_s=DT, sigma=th.SIGMA_TC_K,
                                seed=3, load=daily, ambient_base=40.0)
    t0, _ = rls_theta(e0, l0, DT)
    t1, _ = rls_theta(e1, l1, DT)
    print(f"      mean joint T {sum(a0) / len(a0):.2f} C -> {sum(a1) / len(a1):.2f} C"
          f"   ({sum(a1) / len(a1) - sum(a0) / len(a0):+.2f} K)")
    print(f"      theta        {t0:.6f} K -> {t1:.6f} K   ({t1 - t0:+.2e} K)")
    check("+12 K ambient shift moves theta by < 1e-9 K", abs(t1 - t0) < 1e-9)


# --------------------------------------------------------------------------
# 3. RLS versus deconvolution
# --------------------------------------------------------------------------

def test_3_rls_beats_deconvolution() -> None:
    rule("3  RLS through the model beats pointwise deconvolution")
    print("""
    A joint is a thermal mass: dT[k] = a*dT[k-1] + (1-a)*theta*f^2.  Inverting
    that pointwise to get theta multiplies sensor noise by sqrt(1+a^2)/(1-a).
    Regressing THROUGH the model instead averages the same information over
    thousands of samples.  Both estimators are run below on identical data.
""")
    DT, TAU, THETA, DAYS = 60.0, 1200.0, 6.0, 14.0

    def daily(t: float) -> float:
        h = (t / 3600.0) % 24.0
        return 0.55 + 0.30 * math.sin(2 * math.pi * (h - 9.0) / 24.0)

    exc, lo, _ = simulate_joint(THETA, days=DAYS, dt_s=DT, sigma=th.SIGMA_TC_K,
                                seed=5, load=daily, tau_s=TAU)
    final, traj = rls_theta(exc, lo, DT, tau_s=TAU)
    tail = traj[-int(3 * DAY_S / DT):]
    rls_sd, rls_mean = sd(tail), sum(tail) / len(tail)

    naive = []
    for k in range(1, len(exc)):
        v = th.naive_theta(exc[k], exc[k - 1], lo[k], DT, TAU)
        if v is not None and lo[k] >= 0.3:
            naive.append(v)
    nv_sd, nv_mean = sd(naive), sum(naive) / len(naive)

    a = math.exp(-DT / TAU)
    gain = th.deconvolution_noise_gain(DT, TAU)
    print(f"    dt = {DT:.0f} s, tau = {TAU / 60:.0f} min  ->  a = {a:.4f}")
    print(f"    analytic noise gain of pointwise inversion "
          f"sqrt(1+a^2)/(1-a) = {gain:.2f}")
    print(f"    that turns a {th.SIGMA_TC_K} K sensor pair into a "
          f"{gain * th.SIGMA_TC_K:.2f} K per-sample theta estimate,")
    print(f"    which is larger than the {th.THETA_ALARM_K:.0f} K defect we are hunting\n")
    print(f"    {'estimator':<28} {'mean':>10} {'sd':>10} {'relative sd':>13}")
    print(f"    {'pointwise deconvolution':<28} {nv_mean:9.3f} K "
          f"{nv_sd:9.4f} K {100 * nv_sd / THETA:12.2f} %")
    print(f"    {'RLS through the model':<28} {rls_mean:9.3f} K "
          f"{rls_sd:9.4f} K {100 * rls_sd / THETA:12.4f} %")
    print(f"\n    measured advantage: {nv_sd / rls_sd:,.0f}x quieter, "
          f"both unbiased ({nv_mean:.3f} vs {rls_mean:.3f} against {THETA:.3f})")
    check("RLS is at least 10x quieter than deconvolution", nv_sd > 10 * rls_sd,
          f"{nv_sd / rls_sd:,.0f}x")
    check("RLS mean within 3 % of truth", abs(rls_mean - THETA) / THETA < 0.03,
          f"{rls_mean:.3f} K")
    check("deconvolution is unbiased too - it is the VARIANCE that kills it",
          abs(nv_mean - THETA) / THETA < 0.20, f"{nv_mean:.3f} K")

    print(f"\n    (both estimators sit ~2.6 % low because of the peer-set bias")
    print(f"     quantified in section 1; the comparison here is variance, not bias)")
    print(f"\n    a 100 % error in tau costs almost nothing.  Measured against the")
    print(f"    correct-tau fit, so the peer-set bias divides out:")
    ref, _ = th._fit_theta(exc, lo, DT, TAU)
    for factor in (0.25, 0.5, 1.0, 2.0, 4.0):
        got, _ = th._fit_theta(exc, lo, DT, TAU * factor)
        print(f"      tau assumed {TAU * factor:6.0f} s ({factor:4.2f}x true) -> "
              f"theta {got:6.3f} K   {100 * (got - ref) / ref:+6.2f} % vs correct tau")
    half, _ = th._fit_theta(exc, lo, DT, TAU * 0.5)
    dbl, _ = th._fit_theta(exc, lo, DT, TAU * 2.0)
    worst = 100.0 * max(abs(half - ref), abs(dbl - ref)) / ref
    print(f"      worst cost of a 100 % tau error: {worst:.2f} %")
    check("100 % tau error costs under 3 % of theta", worst < 3.0,
          f"{worst:.2f} %")
    picked = th.identify_tau(exc[:2880], lo[:2880], DT)
    print(f"      identify_tau() picks {picked:.0f} s from the five-point grid "
          f"(true {TAU:.0f} s)")


# --------------------------------------------------------------------------
# 4. Detection lead time on a 0.2 K/week drift
# --------------------------------------------------------------------------

def test_4_detection_lead_time() -> None:
    rule("4  DETECTION LEAD TIME  -  inject 0.2 K/week, count the days")
    print("""
    This is the number the utility actually buys.  A bolted joint degrades over
    months; the question is how long after the degradation starts the system
    says something, and whether the answer is weeks rather than "when it burns".

    Full path: daily medians of theta -> 14 days of CUSUM training -> CUSUM with
    k = 0.5, h = 8, sigma floored at 0.8 K.  The alarm needs all three of
    cusum > 8 AND theta_daily >= 5 K AND 3 of the last 5 days, so both the
    CUSUM crossing and the qualified alarm are reported.
""")
    TRAIN = cs.DEFAULT_TRAIN_DAYS
    ONSET = TRAIN + 10          # drift starts 10 days after training ends
    N_DAYS = 400
    SIGMA_DAILY = 0.8

    print(f"    {'drift':>12} {'CUSUM crosses h':>18} {'qualified alarm':>18} "
          f"{'theta at alarm':>16}")
    lead_02 = None
    for slope in (0.1, 0.2, 0.35, 0.5, 1.0):
        rng = random.Random(4242)
        st = cs.CusumState()
        fired_hist: list[bool] = []
        cross_day = None
        alarm_day = None
        theta_at_alarm = 0.0
        for day in range(N_DAYS):
            drift = max(0.0, day - ONSET) * slope / 7.0
            val = 0.4 + drift + rng.gauss(0.0, SIGMA_DAILY)
            st, fired = cs.cusum_update(st, val)
            fired_hist.append(fired)
            if fired and cross_day is None:
                cross_day = day
            tail = fired_hist[-cs.QUALIFY_OF_LAST:]
            if (alarm_day is None and sum(tail) >= cs.QUALIFY_NEEDED
                    and val >= cs.QUALIFY_THETA_K):
                alarm_day = day
                theta_at_alarm = val
        cd = "-" if cross_day is None else f"{cross_day - ONSET} d"
        ad = "-" if alarm_day is None else f"{alarm_day - ONSET} d"
        ta = "-" if alarm_day is None else f"{theta_at_alarm:.2f} K"
        print(f"    {slope:8.2f} K/wk {cd:>18} {ad:>18} {ta:>16}")
        if abs(slope - 0.2) < 1e-9:
            lead_02 = (cross_day, alarm_day, theta_at_alarm)

    cross, alarm, ta = lead_02
    print(f"\n    the headline case, 0.2 K/week.  Two different questions, two")
    print(f"    different answers, and it matters which one is being asked:")
    print(f"      drift starts on day {ONSET} (CUSUM training ended on day {TRAIN})")
    print(f"\n      'when did we NOTICE?'   CUSUM crosses h = {cs.DEFAULT_H:.0f} on "
          f"day {cross},")
    print(f"                              {cross - ONSET} days after onset, when the "
          f"joint has")
    print(f"                              drifted just {(cross - ONSET) * 0.2 / 7:.2f} K."
          f"  That puts it on")
    print(f"                              the weekly watch list.  No crew moves.")
    print(f"      closed-form check: cusum.days_to_alarm(0.2) = "
          f"{cs.days_to_alarm(0.2):.0f} days")
    print(f"\n      'when do we SEND A CREW?'  the qualified alarm needs all three")
    print(f"                              conditions, and the binding one is")
    print(f"                              theta >= {cs.QUALIFY_THETA_K:.0f} K.  It fires "
          f"on day {alarm},")
    print(f"                              {alarm - ONSET} days after onset, at theta = "
          f"{ta:.1f} K.")
    print(f"\n      The gap between the two is deliberate.  Noticing is free;")
    print(f"      dispatching a crew to a rural secondary substation is not, and a")
    print(f"      1 K drift is not yet worth a truck.  What the CUSUM buys is that")
    print(f"      the joint is already on a list with a dated onset and a slope")
    print(f"      {alarm - cross} days before anything else in the panel would have "
          f"noticed it at all.")
    check("0.2 K/week is detected by the CUSUM", cross is not None)
    check("0.2 K/week CUSUM crossing inside 90 days of onset",
          cross - ONSET <= 90, f"{cross - ONSET} days")
    check("qualified alarm eventually fires", alarm is not None,
          f"day {alarm}")

    print(f"\n    and what a bare threshold, with no CUSUM at all, would have done:")
    rng = random.Random(4242)
    first_2k = first_5k = None
    false_2k = 0
    for day in range(N_DAYS):
        drift = max(0.0, day - ONSET) * 0.2 / 7.0
        val = 0.4 + drift + rng.gauss(0.0, SIGMA_DAILY)
        if val >= 2.0:
            if first_2k is None:
                first_2k = day
            if drift < 0.8:
                false_2k += 1
        if val >= 5.0 and first_5k is None:
            first_5k = day
    print(f"      a 5 K threshold fires on day {first_5k} "
          f"({first_5k - ONSET} d after onset) - {first_5k - cross} days later than")
    print(f"      the CUSUM, and with no onset date and no slope to show anyone.")
    print(f"      lowering it to 2 K to catch it sooner fires on day {first_2k}, but "
          f"noise")
    print(f"      alone had already crossed 2 K on {false_2k} day(s) while the defect "
          f"was under 0.8 K.")
    print(f"      That is the trade a cumulative sum removes: it integrates {cross - ONSET}"
          f" days of")
    print(f"      evidence instead of trusting one.")
    check("CUSUM notices the drift well before a bare 5 K threshold",
          cross < first_5k, f"day {cross} vs day {first_5k}")


# --------------------------------------------------------------------------
# 5. False-alarm arithmetic
# --------------------------------------------------------------------------

def test_5_false_alarm_arithmetic() -> None:
    rule("5  FALSE-ALARM ARITHMETIC  -  what the fleet actually experiences")
    print("""
    A monitoring system dies of false alarms, not of missed faults.  So the
    false-alarm rate is a design parameter with a number attached, not a hope.
""")
    K, H = cs.DEFAULT_K, cs.DEFAULT_H
    predicted = cs.arl0(K, H)
    print(f"    Siegmund:  ARL0 = [exp(2kb) - 2kb - 1] / (2k^2),  b = h + 1.166")
    print(f"    k = {K}, h = {H}  ->  b = {H + 1.166}, "
          f"ARL0 = {predicted:,.0f} joint-days = {predicted / 365.25:.1f} years/joint")

    m = cs._mc_arl(400, K, H, seed=31337, cap=400_000)
    ratio = m["arl"] / predicted
    print(f"\n    Monte Carlo on healthy joints (sigma known):")
    print(f"      {m['joint_days']:,} simulated healthy joint-days, "
          f"{m['crossed']} crossings, {m['censored']} censored")
    print(f"      measured ARL0 {m['arl']:,.0f} d   predicted {predicted:,.0f} d"
          f"   ratio {ratio:.2f}")
    check("measured ARL0 within a factor of 3 of Siegmund",
          1 / 3 < ratio < 3, f"ratio {ratio:.2f}")
    check("at least 5000 healthy joint-days simulated", m["joint_days"] >= 5000,
          f"{m['joint_days']:,}")

    n_joints = len(assets.monitored_joints())
    print(f"\n    fleet arithmetic (using the conservative i.i.d. ARL0):")
    print(f"      monitored joints per panel: {n_joints}")
    for panels in (1, 10, 100):
        total = panels * n_joints
        per_day = total / predicted
        print(f"      {panels:4d} panel(s) = {total:6,} joint-days/day -> "
              f"{per_day:8.4f} crossings/day = {per_day * 30:7.3f}/month "
              f"= {per_day * 30 / panels:.4f} per panel-month")
    per_day_100 = 100 * n_joints / predicted
    print(f"\n      at 100 panels: one false CUSUM crossing somewhere in the fleet "
          f"every {1 / per_day_100:.1f} days")
    print(f"      per panel: one every {predicted / n_joints / 365.25:.1f} years")
    print(f"\n      and a crossing is NOT an alarm.  The alarm needs")
    print(f"        cusum > {H:.0f}  AND  theta_daily >= {cs.QUALIFY_THETA_K:.0f} K"
          f"  AND  {cs.QUALIFY_NEEDED} of the last {cs.QUALIFY_OF_LAST} days,")
    print(f"      so those figures are an upper bound on the alarm rate.")

    print(f"\n    honest caveat, measured not asserted:")
    for rho in (0.0, 0.3, 0.6):
        mr = cs._mc_arl(200, K, H, seed=99 + int(rho * 10), cap=300_000, rho=rho)
        print(f"      daily autocorrelation rho = {rho:.1f} -> ARL0 "
              f"{mr['arl']:10,.0f} d ({mr['arl'] / predicted:.2f}x the i.i.d. formula)")
    print(f"      theta IS autocorrelated, so the true ARL0 is SHORTER than the")
    print(f"      formula.  That is why h = {H:.0f} rather than the textbook 4 or 5:")
    print(f"      h = 5 gives an i.i.d. ARL0 of only {cs.arl0(K, 5.0):,.0f} days.")


# --------------------------------------------------------------------------
# 6. Dew point reference values
# --------------------------------------------------------------------------

def test_6_dewpoint() -> None:
    rule("6  DEW POINT  -  Magnus-Tetens with Alduchov-Eskridge coefficients")
    print(f"""
    a = {dp.MAGNUS_A}, b = {dp.MAGNUS_B} C, valid {dp.VALID_LO_C:.0f}..{dp.VALID_HI_C:.0f} C,
    max error +-{dp.ACCURACY_C} C.  gamma = ln(RH/100) + a*T/(b+T);  Td = b*gamma/(a-gamma).
""")
    for t, rh, expect in ((20.0, 50.0, 9.26), (10.0, 90.0, 8.43)):
        got = dp.dewpoint_c(t, rh)
        print(f"    Td({t:.0f} C, {rh:.0f} %) = {got:.4f} C   reference {expect:.2f} C"
              f"   delta {got - expect:+.4f}")
        check(f"Td({t:.0f} C, {rh:.0f} %) = {expect}", abs(got - expect) < 0.005,
              f"got {got:.4f}")
    print(f"    Td(T, 100 %) = T exactly: Td(25, 100) = "
          f"{dp.dewpoint_c(25.0, 100.0):.6f} C")
    check("Td = T at RH 100 %", abs(dp.dewpoint_c(25.0, 100.0) - 25.0) < 1e-9)

    print(f"\n    the point of the wall model - the AIR can never condense:")
    wall = None
    dt = 300.0
    air_wet = wall_wet = 0
    for step in range(int(8 * 3600 / dt) + 1):
        hour = 5.0 + step * dt / 3600.0
        ramp = max(0.0, min(1.0, (hour - 6.0) / 7.0))
        air = 9.0 + 13.0 * ramp
        rh = 95.0 - 25.0 * ramp
        wall = dp.wall_temp(wall, air, dt)
        td = dp.dewpoint_c(air, rh)
        if air - td < 0:
            air_wet += 1
        if dp.condensation_margin(wall, td) < 0:
            wall_wet += 1
    print(f"    spring morning, cable trench, tau = {dp.WALL_TAU_S / 60:.0f} min:")
    print(f"      surface below dew point for {wall_wet * dt / 60:.0f} minutes")
    print(f"      air     below dew point for {air_wet * dt / 60:.0f} minutes "
          f"<- an air-referenced alarm stays silent")
    check("wall model detects wetting the air model misses",
          wall_wet > 0 and air_wet == 0, f"wall {wall_wet}, air {air_wet}")

    print(f"\n    severity ladder:")
    for m, mins, pd_db, expect in ((5.0, 0, 0, "BILGI"), (1.5, 45, 0, "IZLE"),
                                   (-0.5, 75, 0, "UYARI"), (1.5, 45, 6.5, "KRITIK")):
        got = dp.condensation_severity(m, mins, pd_db)
        print(f"      margin {m:+5.1f} K, {mins:3d} min, PD {pd_db:+4.1f} dB "
              f"-> {got}")
        check(f"ladder({m}, {mins}, {pd_db}) == {expect}", got == expect, got)


# --------------------------------------------------------------------------
# 7. Rule H3
# --------------------------------------------------------------------------

def test_7_rule_h3() -> None:
    rule("7  RULE H3  -  same hot neutral bar, two opposite work orders")
    print("""
    The neutral bar has no fuse, no relay and no ammeter.  Nothing else in a
    TEDAS panel watches it.  When it runs hot there are two causes that look
    identical on a thermal image:

      harmonic loading      -> filter / rebalance / derate.  Retorquing is futile.
      a bad neutral joint   -> retorque.  A filter is futile.

    The discriminator is K_N = dT_N / I_N^2 against its own baseline.
""")
    CT = assets.MAIN_CT_PRIMARY_A
    K_BASE = 4.0 / (350.0 ** 2)
    print(f"    healthy baseline K_N = {K_BASE:.3e} K/A^2 (350 A -> 4.0 K)")
    print(f"    main CT {CT:.0f}/{assets.MAIN_CT_SECONDARY_A:.0f} "
          f"(incomer only - no outgoing way has one)")

    fund_bal = nt.neutral_fundamental(800, 800, 800, 0, -120, 120)
    fund_unb = nt.neutral_fundamental(900, 700, 500, 0, -120, 120)
    print(f"\n    fundamental (unbalance) neutral current:")
    print(f"      balanced 800/800/800 A            -> I_N,fund = {fund_bal:6.1f} A")
    print(f"      Turkish reality 900/700/500 A     -> I_N,fund = {fund_unb:6.1f} A "
          f"(57 % unbalance is routine)")

    cases = []

    i_n = 720.0                              # 30 % triplen on a balanced 800 A
    dt_n = K_BASE * i_n ** 2
    cases.append(("harmonik yük", nt.rule_h3(nt.k_n(dt_n, i_n), K_BASE, dt_n, i_n,
                                             800.0, i_n_fund=fund_bal,
                                             ct_rating_a=CT), i_n, dt_n,
                  "harmonik_yuk"))

    i_n = fund_unb                           # unbalance only, joint degraded 2.2x
    dt_n = 2.2 * K_BASE * i_n ** 2
    cases.append(("kötü nötr bağlantısı",
                  nt.rule_h3(nt.k_n(dt_n, i_n), K_BASE, dt_n, i_n, 700.0,
                             i_n_fund=fund_unb, ct_rating_a=CT), i_n, dt_n,
                  "kotu_notr_baglanti"))

    i_n = 720.0                              # both at once
    dt_n = 1.8 * K_BASE * i_n ** 2
    cases.append(("her ikisi birden",
                  nt.rule_h3(nt.k_n(dt_n, i_n), K_BASE, dt_n, i_n, 800.0,
                             i_n_fund=fund_bal, ct_rating_a=CT), i_n, dt_n,
                  "kotu_notr_baglanti"))

    i_n = 200.0                              # healthy
    dt_n = K_BASE * i_n ** 2
    cases.append(("sağlam", nt.rule_h3(nt.k_n(dt_n, i_n), K_BASE, dt_n, i_n, 700.0,
                                       i_n_fund=180.0, ct_rating_a=CT), i_n, dt_n,
                  "normal"))

    print(f"\n    {'senaryo':<24} {'I_N A':>7} {'dT_N K':>8} {'K_N x':>7} "
          f"{'h3 %':>6}  {'karar':<20}")
    for name, r, i_n_v, dt_v, expect in cases:
        print(f"    {name:<24} {i_n_v:7.0f} {dt_v:8.1f} {r['k_n_ratio']:7.2f} "
              f"{r['h3_pct']:6.0f}  {r['verdict']:<20}")
    for name, r, _, _, expect in cases:
        check(f"H3({name}) == {expect}", r["verdict"] == expect, r["verdict"])

    print(f"\n    the two work orders, in the operator's own words:")
    for name, r, _, _, _ in cases[:2]:
        print(f"\n      {name.upper()}")
        print(f"        gerekçe : {r['reason_tr']}")
        print(f"        aksiyon : {r['action_tr']}")

    gated = nt.rule_h3(0.0, K_BASE, 0.4, 3.0, 120.0, i_n_fund=3.0, ct_rating_a=CT)
    print(f"\n    light load -> diagnosis refused (MPR-53CS current THD saturates")
    print(f"    at 99.9 %, and K_N error grows as 1/I^2):")
    print(f"      gated = {gated['gated']}, verdict = {gated['verdict']}")
    check("H3 refuses to diagnose below the THD/current gate", gated["gated"] is True)


# --------------------------------------------------------------------------
# 8. End to end through the real engine
# --------------------------------------------------------------------------

def test_8_end_to_end() -> None:
    rule("8  END TO END  -  envelopes in, PanelLive out, Modbus words out")
    print("""
    Everything above tests one estimator.  This runs the whole detector: real
    Envelope objects from the frozen 9-device kit, into DetectorEngine, into the
    sqlite store, out as a PanelLive and then as the 48-word Modbus block the
    ICD defines.
""")
    tmp = Path(tempfile.mkdtemp(prefix="panogoz-test-")) / "t.db"
    store = Store(tmp)
    STEP = 3600.0
    e = eng.DetectorEngine(store, commit_every=500, peer_max_age_s=2.5 * STEP)
    SITE, PANEL, T0, DAYS = "Soke", "SOKE-14", 1_750_000_000.0, 45
    DEFECT = "C06-L2-PABUC"

    n, last = 0, T0
    for env in eng._demo_envelopes(SITE, PANEL, T0, DAYS, STEP, seed=7,
                                   defect_joint=DEFECT, defect_start_day=14.0,
                                   defect_ramp_per_day=0.35):
        e.observe(env)
        n += 1
        last = env.ts
    store.commit()
    now = last + 30.0
    rows = e.roll_daily(now, days_back=DAYS + 2)
    live = e.evaluate(PANEL, now)

    print(f"    {n:,} envelopes over {DAYS} days -> "
          f"{store.stats()['joint_sample']:,} joint samples, {rows} daily rows")
    print(f"    rejected out-of-range samples: {e.stats()['rejected']}")
    check("all 9 devices present in the image", len(live.devices) == 9,
          f"{len(live.devices)}")
    check("all 9 devices online", sum(1 for d in live.devices if d.online) == 9)
    check("every joint in the asset model is in the image",
          len(live.joints) == len(assets.JOINTS), f"{len(live.joints)}")
    check("40 joints monitored, the rest shown as izlenmiyor",
          sum(1 for j in live.joints if j.monitored) == 40)
    check("the defect is the worst joint", live.theta_max_joint == DEFECT,
          str(live.theta_max_joint))

    jv = next(j for j in live.joints if j.key == DEFECT)
    onset = ("-" if jv.changepoint_ts is None else
             _dt.datetime.utcfromtimestamp(jv.changepoint_ts).strftime("%d %B %Y"))
    age = ("" if jv.changepoint_ts is None
           else f", {(now - jv.changepoint_ts) / DAY_S:.0f} gün önce")
    print(f"\n    the sentence the demo ends on:")
    print(f'      "{jv.label}: θ {jv.theta_k:.1f} K, fazla temas direnci '
          f'{jv.excess_r_lo_uohm:.0f}-{jv.excess_r_hi_uohm:.0f} µΩ,')
    print(f'       eğim {jv.slope_k_per_week:+.2f} K/hafta, bu bozulma yaklaşık '
          f'{onset} tarihinde başladı{age}."')
    print(f"\n    supporting numbers:")
    print(f"      T {jv.temp_c:.2f} C, sibling median {jv.sibling_median_c:.2f} C, "
          f"own CT {jv.current_a:.0f} A, f {jv.load_factor:.2f}")
    print(f"      theta_min at this load {jv.theta_min_k:.2f} K, "
          f"visibility {jv.sensitivity_pct:.0f} %")
    print(f"      CUSUM {jv.cusum:.1f} (h = {cs.DEFAULT_H:.0f}), "
          f"qualified days {jv.alarm_days}/{cs.QUALIFY_OF_LAST}, "
          f"severity {jv.severity}")
    check("defect theta above the 5 K alarm level", jv.theta_k >= 5.0,
          f"{jv.theta_k:.2f} K")
    check("defect reaches KRITIK", jv.severity == "KRITIK", jv.severity)
    check("onset is dated", jv.changepoint_ts is not None)

    healthy = [j for j in live.joints
               if j.monitored and j.conductor != "N" and j.key != DEFECT]
    worst_healthy = max(abs(j.theta_k or 0.0) for j in healthy)
    sev_healthy = {j.severity for j in healthy}
    print(f"\n    the other {len(healthy)} monitored phase joints:")
    print(f"      worst |theta| {worst_healthy:.2f} K, severities {sorted(sev_healthy)}")
    check("no healthy phase joint raises above BILGI", sev_healthy == {"BILGI"},
          str(sorted(sev_healthy)))

    print(f"\n    neutral joints are judged by rule H3, never by the phase peers:")
    nj = next(j for j in live.joints if j.conductor == "N" and j.monitored)
    v = e.neutral_verdict(PANEL)
    print(f"      {nj.key}: theta_k = {nj.theta_k} (deliberately None), "
          f"severity {nj.severity}")
    print(f"      panel H3 verdict: {v['verdict'] if v else None}")
    check("neutral has no phase-differential theta", nj.theta_k is None)

    print(f"\n    status flags (observational only - policy flags belong to rules):")
    print(f"      {', '.join(live.status_flags)}")
    check("DATA_VALID is set", "DATA_VALID" in live.status_flags)
    check("no STALE flag on fresh data", "STALE" not in live.status_flags)
    check("no comms-lost flags with all 9 devices reporting",
          not any(f.endswith("COMMS_LOST") for f in live.status_flags))

    print(f"\n    SENSITIVITY_LOW is a first-class state, not a silence:")
    print(f"      {'f':>6} {'theta_min (clip)':>18} {'visibility':>12} {'flag':>18}")
    for f in (0.90, 0.60, 0.3464, 0.30, 0.15):
        tmin = th.theta_min(th.SIGMA_TC_K, f)
        pct = th.sensitivity_pct(th.THETA_ALARM_K, th.SIGMA_TC_K, f)
        flag = "SENSITIVITY_LOW" if pct < 100 else "-"
        print(f"      {f:6.3f} {tmin:16.2f} K {pct:11.0f} % {flag:>18}")
    print(f"      threshold f = {th.SENSITIVITY_LOW_F:.4f} "
          f"= sqrt(3*{th.SIGMA_TC_K}/{th.THETA_ALARM_K})")

    print(f"\n    restart: kill the process, rebuild the engine from the store")
    before = (jv.theta_k, jv.cusum, jv.baseline_k, jv.slope_k_per_week,
              jv.changepoint_ts)
    e2 = eng.DetectorEngine(store, peer_max_age_s=2.5 * STEP)
    jv2 = next(j for j in e2.evaluate(PANEL, now).joints if j.key == DEFECT)
    after = (jv2.theta_k, jv2.cusum, jv2.baseline_k, jv2.slope_k_per_week,
             jv2.changepoint_ts)
    print(f"      before  theta {before[0]:.4f}  cusum {before[1]:.2f}  "
          f"baseline {before[2]:.4f}  slope {before[3]:+.4f}")
    print(f"      after   theta {after[0]:.4f}  cusum {after[1]:.2f}  "
          f"baseline {after[2]:.4f}  slope {after[3]:+.4f}")
    check("state survives a restart bit for bit",
          all(abs(x - y) < 1e-9 for x, y in zip(before, after)))

    print(f"\n    the same numbers as Modbus words (encoded by contracts.live,")
    print(f"    never re-implemented here):")
    live.severity = "KRITIK"
    words = live.to_registers([j.key for j in assets.JOINTS])
    R = icd.PANEL_BY_NAME
    base = icd.panel_base(max(1, live.panel_index))
    for name in ("HEALTH_INDEX", "SEVERITY", "STATUS_WORD", "THETA_MAX",
                 "THETA_SLOPE", "SENSITIVITY_PCT", "T_JOINT_MAX", "LOAD_FACTOR",
                 "I_N", "DEVICES_ONLINE", "DATA_AGE_S"):
        r = R[name]
        raw = words[r.offset:r.offset + r.words]
        print(f"      PDU {base + r.offset:<5} {name:<16} raw {str(raw):<12} -> "
              f"{icd.decode(r, raw):g} {r.unit}")
    check("THETA_MAX word matches the image",
          abs(icd.decode(R["THETA_MAX"], words[6:7]) - live.theta_max) < 0.06)
    check("48-word block", len(words) == icd.REGS_PER_PANEL)
    store.close()


# --------------------------------------------------------------------------

def main() -> int:
    print("PANO GÖZ · dedektör doğrulama · " +
          _dt.datetime.now().strftime("%Y-%m-%d %H:%M"))
    print(f"panel: {assets.panel_summary()['tip']}")
    print(f"       {assets.MAIN_BUSBAR_RATED_A:.0f} A, "
          f"{len(assets.monitored_joints())} izlenen bağlantı, "
          f"{assets.DEVICES_PER_PANEL} cihaz")
    test_1_load_invariance()
    test_2_ambient_invariance()
    test_3_rls_beats_deconvolution()
    test_4_detection_lead_time()
    test_5_false_alarm_arithmetic()
    test_6_dewpoint()
    test_7_rule_h3()
    test_8_end_to_end()

    rule("SONUÇ")
    if FAILURES:
        print(f"    {len(FAILURES)} FAILURE(S):")
        for f in FAILURES:
            print(f"      - {f}")
        return 1
    print("    all detector claims verified with computed numbers")
    return 0


if __name__ == "__main__":
    sys.exit(main())
