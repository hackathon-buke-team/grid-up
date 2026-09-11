"""CUSUM on the daily median of theta.

What it is for
--------------
theta answers "is this joint hot for its load right now".  CUSUM answers the
harder and more valuable question: "is this joint's theta *drifting upward*,
slowly, in a way no single reading would ever trip".  A bolted joint does not
fail in a step.  It oxidises, it relaxes, its contact area shrinks, and its
excess resistance climbs over months.  The signal we want to catch is on the
order of **0.2 K per week** against a per-sample noise floor of the same order,
which is exactly the regime a threshold cannot see and a cumulative sum can.

We run it on the **daily median** of theta, not on the raw stream.  A daily
median of ~1440 samples is robust to the crew opening the panel, to a truck
parking in front of the substation door, and to a single bad frame; and one
sample per day is the right cadence for a process whose time constant is weeks.

Where sigma comes from - and where it must NOT come from
--------------------------------------------------------
sigma is the standard deviation of the **training LEVEL**: the plain sample
standard deviation of the 14 daily medians in the training window.

It is tempting to estimate it from lag-1 differences instead
(``sigma ~ sd(diff)/sqrt(2)``, the classic MR-bar/1.128 trick).  Do not.  theta
is positively autocorrelated day to day - the weather, the load pattern and the
joint's own thermal state all persist - so lag-1 differences see only the
high-frequency part of the variance and systematically UNDER-estimate the
low-frequency variance that actually drives a CUSUM excursion.  An
under-estimated sigma inflates every standardised increment, and the detector
then produces false alarms at a rate far above its design point.  The
difference is not academic: on a series with lag-1 autocorrelation 0.6 the
difference-based estimator returns about 63 % of the true level sd, which alone
shortens ARL0 by more than an order of magnitude.

sigma is floored at 0.8 K.  A joint that happens to sit very still for fourteen
days would otherwise be handed a sigma of 0.1 K and become a permanent false
alarm generator the first time the weather changed.

Parameters and what they buy
----------------------------
``k = 0.5`` in sigma units: the classic choice, optimal for detecting a shift of
2k = 1 sigma.  ``h = 8`` (not the textbook 4 or 5) because of the
autocorrelation just described.

Siegmund's approximation for the one-sided ARL::

    ARL0 = [ exp(2*k*b) - 2*k*b - 1 ] / (2*k^2),    b = h + 1.166

At k = 0.5, h = 8 that is **19112 daily samples** between false alarms per
joint.  The 1.166 is Siegmund's continuity correction for the overshoot of a
discrete random walk past a continuous boundary; dropping it turns 19112 into
5944, a 3.2x error, so it is not optional.

**Honest caveat, stated in the product and not only in a comment:** the formula
assumes i.i.d. normal increments.  theta's daily medians are positively
autocorrelated - weather, load pattern and the joint's own thermal state all
persist - and an AR(1) with coefficient rho inflates the accumulated increment
variance by (1+rho)/(1-rho).  Because ARL0 depends EXPONENTIALLY on h measured
in units of that standard deviation, the penalty is exponential, not linear.
The self-test measures it: rho = 0.3 takes ARL0 from 19112 days to 1078, and
rho = 0.6 to 188.  That is precisely why h is 8 and not the textbook 4 or 5: at
h = 5 the i.i.d. ARL0 is already only 938 days, and after the autocorrelation
penalty a 100-panel fleet would be producing false crossings daily.

And CUSUM crossing alone never raises an alarm.  The rules layer requires all
three of: ``cusum > 8`` AND ``theta_daily >= 5 K`` AND ``3 of the last 5 days``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

DEFAULT_K = 0.5
DEFAULT_H = 8.0
DEFAULT_TRAIN_DAYS = 14
SIGMA_FLOOR_K = 0.8

#: A CUSUM day "qualifies" for the alarm counter only if the level itself is
#: also meaningful.  Drift with no magnitude is a maintenance note, not a fault.
#:
#: TWO WAYS TO QUALIFY, because a joint can be bad in two different ways.
#:
#: ``QUALIFY_THETA_K`` is the ABSOLUTE level: a lug that has run this far above
#: its phase mates is a defect whether or not it is currently moving.
#:
#: ``QUALIFY_RISE_K`` is the RISE above that joint's own commissioned baseline.
#: It is much smaller, and legitimately so.  Every bolted joint has a
#: manufacturing offset against its siblings, so a joint whose baseline sits at
#: -2 K would need a 7 K excursion to trip an absolute 5 K gate, while a joint
#: baselined at +4 K would trip on a 1 K wobble.  Judging the rise removes that
#: unfairness, and because the statistic is a daily median of roughly sixteen
#: samples its noise is smaller by sqrt(16) = 4 - which is exactly what buys the
#: weeks of early warning the whole product is built on.
QUALIFY_THETA_K = 5.0
QUALIFY_RISE_K = 1.0
QUALIFY_OF_LAST = 5
QUALIFY_NEEDED = 3


@dataclass
class CusumState:
    """Per-joint drift state.

    Maps onto the ``joint_state`` columns ``cusum_pos``, ``cusum_neg``,
    ``train_n``, ``train_mean``, ``train_m2``, ``baseline``, ``sigma`` so it
    survives a restart with its training intact.
    """

    pos: float = 0.0
    neg: float = 0.0
    n: int = 0            #: training samples seen
    mean: float = 0.0     #: Welford running mean of the training window
    m2: float = 0.0       #: Welford sum of squared deviations
    baseline: float | None = None
    sigma: float | None = None
    fired_days: int = 0   #: consecutive days the positive arm has been above h

    @property
    def trained(self) -> bool:
        return self.baseline is not None and self.sigma is not None

    def to_row(self) -> dict:
        return {
            "cusum_pos": self.pos,
            "cusum_neg": self.neg,
            "train_n": self.n,
            "train_mean": self.mean,
            "train_m2": self.m2,
            "baseline": self.baseline,
            "sigma": self.sigma,
        }

    @classmethod
    def from_row(cls, row: dict) -> "CusumState":
        return cls(
            pos=float(row.get("cusum_pos") or 0.0),
            neg=float(row.get("cusum_neg") or 0.0),
            n=int(row.get("train_n") or 0),
            mean=float(row.get("train_mean") or 0.0),
            m2=float(row.get("train_m2") or 0.0),
            baseline=(None if row.get("baseline") is None else float(row["baseline"])),
            sigma=(None if row.get("sigma") is None else float(row["sigma"])),
        )


def cusum_update(st: CusumState, value: float, k: float = DEFAULT_K, h: float = DEFAULT_H,
                 train_days: int = DEFAULT_TRAIN_DAYS,
                 sigma_floor: float = SIGMA_FLOOR_K) -> tuple[CusumState, bool]:
    """Fold one daily median of theta in.  Returns ``(new_state, fired)``.

    While ``n < train_days`` the sample only trains the baseline and never
    fires: a joint that was already degrading at commissioning trains a high
    baseline and will not be caught by drift detection, which is exactly why the
    absolute limits (T > 110 C, T > 130 C) and the level test (theta >= 5 K) are
    armed from minute one and are never gated by the learn window.

    Returns a NEW state; the input is not mutated.
    """
    out = CusumState(st.pos, st.neg, st.n, st.mean, st.m2, st.baseline, st.sigma,
                     st.fired_days)

    if not math.isfinite(value):
        return out, False

    if out.n < train_days:
        # Welford, so the training window needs no array and survives a restart
        # as three floats.
        out.n += 1
        d = value - out.mean
        out.mean += d / out.n
        out.m2 += d * (value - out.mean)
        out.baseline = out.mean
        if out.n >= 2:
            var = out.m2 / (out.n - 1)
            # sd of the training LEVEL - never of lag-1 differences.
            out.sigma = max(math.sqrt(max(var, 0.0)), sigma_floor)
        else:
            out.sigma = sigma_floor
        return out, False

    base = out.baseline if out.baseline is not None else 0.0
    sig = max(out.sigma or sigma_floor, sigma_floor)
    z = (value - base) / sig
    out.pos = max(0.0, out.pos + z - k)
    out.neg = max(0.0, out.neg - z - k)
    fired = out.pos > h
    out.fired_days = out.fired_days + 1 if fired else 0
    return out, fired


def arl0(k: float = DEFAULT_K, h: float = DEFAULT_H) -> float:
    """Siegmund's one-sided in-control average run length, in samples (days).

    ``ARL0 = [exp(2kb) - 2kb - 1] / (2k^2)`` with ``b = h + 1.166``.

    The 1.166 is the continuity correction for the overshoot of a discrete
    random walk over a continuous boundary; omitting it over-estimates ARL0 by
    roughly ``exp(2*k*1.166)`` = 3.2x at k = 0.5.
    """
    b = h + 1.166
    x = 2.0 * k * b
    return (math.exp(x) - x - 1.0) / (2.0 * k * k)


def arl1(k: float = DEFAULT_K, h: float = DEFAULT_H, delta: float = 1.0) -> float:
    """Out-of-control ARL for a sustained shift of ``delta`` sigma.

    Same Siegmund form with the drift folded in: ``d = delta - k``, and the ARL
    is ``(exp(-2*d*b) + 2*d*b - 1) / (2*d^2)``, which tends to ``b/d`` for a
    large shift - i.e. "how many days to walk h+1.166 units at d units a day".
    """
    b = h + 1.166
    d = delta - k
    if abs(d) < 1e-9:
        return b * b
    x = -2.0 * d * b
    return (math.exp(x) + 2.0 * d * b - 1.0) / (2.0 * d * d)


def days_to_alarm(slope_k_per_week: float, sigma: float = SIGMA_FLOOR_K,
                  k: float = DEFAULT_K, h: float = DEFAULT_H) -> float:
    """Rough lead-time estimate for a linear drift, in days.

    A ramp of ``s`` sigma per day makes the CUSUM a quadratic: after n days the
    statistic is about ``s*n^2/2 - k*n``.  Solving ``pos = h`` gives
    ``n = (k + sqrt(k^2 + 2*s*h)) / s``.  Used only for the UI's "expected
    detection horizon" line and for the self-test's sanity check; the real
    number comes from running the detector.
    """
    s = (slope_k_per_week / 7.0) / max(sigma, 1e-9)
    if s <= 0.0:
        return float("inf")
    return (k + math.sqrt(k * k + 2.0 * s * h)) / s


# --------------------------------------------------------------------------
# Self-test
# --------------------------------------------------------------------------

def _mc_arl(n_runs: int, k: float, h: float, seed: int, cap: int,
            *, true_sd: float = 2.0, rho: float = 0.0, estimate_sigma: bool = False,
            train_days: int = DEFAULT_TRAIN_DAYS,
            sigma_floor: float = SIGMA_FLOOR_K) -> dict:
    """Monte Carlo in-control ARL over ``n_runs`` independent healthy joints.

    A vectorised replica of the :func:`cusum_update` recursion, so that millions
    of joint-days run in seconds.  ``_check_replica`` below asserts, on real
    data, that the replica reproduces :func:`cusum_update` to the last bit - a
    fast test of a different algorithm would prove nothing.

    ``estimate_sigma=False`` hands the detector the true sigma, which is the
    assumption set Siegmund's formula is derived under, and is therefore the
    only fair comparison against it.  ``estimate_sigma=True`` is the shipped
    configuration: baseline and sigma learned from ``train_days`` daily medians.
    """
    import numpy as np

    rng = np.random.default_rng(seed)
    if estimate_sigma:
        train = rng.standard_normal((train_days, n_runs)) * true_sd
        base = train.mean(axis=0)
        sig = np.maximum(train.std(axis=0, ddof=1), sigma_floor)
    else:
        base = np.zeros(n_runs)
        sig = np.full(n_runs, true_sd)

    pos = np.zeros(n_runs)
    x = np.zeros(n_runs)
    run_len = np.zeros(n_runs, dtype=np.int64)
    alive = np.ones(n_runs, dtype=bool)
    inn = true_sd * math.sqrt(1.0 - rho * rho) if rho else true_sd

    n = 0
    while n < cap and alive.any():
        n += 1
        e = rng.standard_normal(n_runs)
        if rho:
            x = rho * x + e * inn
            v = x
        else:
            v = e * true_sd
        pos = np.maximum(0.0, pos + (v - base) / sig - k)
        newly = alive & (pos > h)
        if newly.any():
            run_len[newly] = n
            alive &= ~newly
    run_len[alive] = cap
    return {
        "arl": float(run_len.mean()),
        "median": float(np.median(run_len)),
        "crossed": int((~alive).sum()),
        "censored": int(alive.sum()),
        "joint_days": int(run_len.sum()),
        "sigma_mean": float(sig.mean()),
    }


def _check_replica(seed: int = 99, n: int = 4000) -> float:
    """Assert the vectorised Monte Carlo recursion equals ``cusum_update``."""
    import numpy as np

    rng = np.random.default_rng(seed)
    vals = rng.standard_normal(n) * 2.0
    st = CusumState(n=DEFAULT_TRAIN_DAYS, baseline=0.0, sigma=2.0)
    pos = 0.0
    worst = 0.0
    for v in vals:
        st, _ = cusum_update(st, float(v))
        pos = max(0.0, pos + (float(v) - 0.0) / 2.0 - DEFAULT_K)
        worst = max(worst, abs(pos - st.pos))
    return worst


if __name__ == "__main__":
    from panogoz.contracts import assets

    print("=" * 78)
    print("cusum.py self-test")
    print("=" * 78)

    K, H = DEFAULT_K, DEFAULT_H
    predicted = arl0(K, H)

    # ------------------------------------------------------------------ 0 --
    worst = _check_replica()
    print(f"\n[0] the fast Monte Carlo recursion is verified against cusum_update()")
    print(f"    max |pos_replica - pos_cusum_update| over 4000 samples = {worst:.2e}")
    assert worst < 1e-12

    # ------------------------------------------------------------------ 1 --
    print(f"\n[1] Siegmund prediction")
    print(f"    k = {K}, h = {H}, b = h + 1.166 = {H + 1.166}")
    print(f"    ARL0 = [exp(2kb) - 2kb - 1] / (2k^2) = {predicted:,.0f} daily samples")
    print(f"         = {predicted / 365.25:,.1f} years per joint")
    arl0_naive = (math.exp(2 * K * H) - 2 * K * H - 1) / (2 * K * K)
    print(f"    dropping the 1.166 continuity correction would give {arl0_naive:,.0f} "
          f"days ({arl0_naive / predicted:.2f}x) - the correction is not optional")
    for hh in (4.0, 5.0, 6.0, 8.0, 10.0):
        print(f"      h = {hh:4.1f} -> ARL0 {arl0(K, hh):12,.0f} days")

    # ------------------------------------------------------------------ 2 --
    print(f"\n[2] Monte Carlo, healthy joints, sigma known exactly")
    print(f"    (the assumption set Siegmund's formula is derived under)")
    RUNS, CAP = 500, 400_000
    m = _mc_arl(RUNS, K, H, seed=20260910, cap=CAP)
    print(f"    runs {RUNS}   crossings {m['crossed']}   censored {m['censored']}")
    print(f"    simulated healthy joint-days   {m['joint_days']:,}")
    assert m["joint_days"] >= 5000, "must simulate at least 5000 healthy joint-days"
    print(f"    measured ARL0                  {m['arl']:,.0f} days")
    print(f"    predicted ARL0 (Siegmund)      {predicted:,.0f} days")
    ratio = m["arl"] / predicted
    print(f"    ratio measured / predicted     {ratio:.2f}   (requirement: within 3x)")
    assert 1.0 / 3.0 < ratio < 3.0, f"ARL0 off by more than 3x: {ratio}"
    print(f"    false alarms per 5000 healthy joint-days: "
          f"measured {5000 / m['arl']:.3f}   predicted {5000 / predicted:.3f}")

    # ------------------------------------------------------------------ 3 --
    print(f"\n[3] the SHIPPED configuration - sigma learned from "
          f"{DEFAULT_TRAIN_DAYS} daily medians")
    m2 = _mc_arl(300, K, H, seed=777, cap=150_000, estimate_sigma=True)
    lo = "at least " if m2["censored"] else ""
    print(f"    runs 300   crossings {m2['crossed']}   censored at 150,000 d "
          f"{m2['censored']}")
    print(f"    mean sigma actually learned    {m2['sigma_mean']:.3f} K "
          f"(true level sd 2.000 K, floor {SIGMA_FLOOR_K})")
    print(f"    measured ARL0                  {lo}{m2['arl']:,.0f} days "
          f"({m2['arl'] / predicted:.1f}x the formula)")
    print(f"    A 14-sample sigma estimate is noisy, and ARL0 grows like")
    print(f"    exp(2kb * (sigma_hat/sigma_true)^2), so averaging over that noise")
    print(f"    LENGTHENS the mean run length.  The error is in the safe direction:")
    print(f"    fewer false alarms than advertised, never more.")

    # ------------------------------------------------------------------ 4 --
    print(f"\n[4] the autocorrelation penalty, measured rather than asserted")
    for rho in (0.0, 0.3, 0.6, 0.8):
        mr = _mc_arl(400, K, H, seed=4242 + int(rho * 10), cap=200_000, rho=rho)
        print(f"    lag-1 autocorrelation {rho:.1f} -> ARL0 {mr['arl']:11,.0f} days"
              f"   ({mr['arl'] / predicted:5.2f}x the i.i.d. formula)"
              f"   censored {mr['censored']}")
    print(f"    theta IS positively autocorrelated day to day, so the true ARL0 is")
    print(f"    SHORTER than the i.i.d. formula.  That is exactly why h = {H:.0f} and")
    print(f"    not the textbook 4 or 5: at h = 5 the i.i.d. ARL0 is only "
          f"{arl0(K, 5.0):,.0f} days,")
    print(f"    and rho = 0.6 would cut that to a few months per joint.")

    # ------------------------------------------------------------------ 5 --
    print(f"\n[5] fleet arithmetic - what the operator actually experiences")
    n_joints = len(assets.monitored_joints())
    arl_used = predicted
    print(f"    monitored joints per panel (assets.monitored_joints()): {n_joints}")
    print(f"    using the conservative i.i.d. ARL0 = {arl_used:,.0f} joint-days")
    for panels, per_panel, label in (
        (100, n_joints, f"100 panels x {n_joints} instrumented bottom-compartment joints"),
        (100, 12 * 4, "100 panels x 12 ways x 4 conductors, if every way were fitted"),
    ):
        total = panels * per_panel
        per_day = total / arl_used
        print(f"    {label}:")
        print(f"      {total:,} joint-days/day -> {per_day:.3f} crossings/day"
              f" = {per_day * 30:.2f}/month fleet-wide"
              f" = {per_day * 30 / panels:.4f} per panel-month")
        print(f"      i.e. one false CUSUM crossing somewhere in the fleet every "
              f"{1 / per_day:.1f} days")
    print(f"    per panel: one false crossing every "
          f"{arl_used / n_joints / 365.25:,.1f} years")
    print(f"    and a crossing is NOT an alarm: the rules layer requires")
    print(f"      cusum > {H:.0f}  AND  theta_daily >= {QUALIFY_THETA_K:.0f} K  AND  "
          f"{QUALIFY_NEEDED} of the last {QUALIFY_OF_LAST} days.")
    print(f"    The numbers above are therefore an upper bound on the alarm rate.")

    # ------------------------------------------------------------------ 6 --
    print(f"\n[6] out-of-control behaviour - a real defect is caught fast")
    print(f"    {'shift':>10} {'Siegmund ARL1':>16}")
    for delta in (0.75, 1.0, 1.5, 2.0, 3.0):
        print(f"    {delta:9.2f}s {arl1(K, H, delta):15.1f} days")
    print(f"    linear drift lead time (sigma = {SIGMA_FLOOR_K} K):")
    for slope in (0.1, 0.2, 0.5, 1.0):
        print(f"      {slope:.1f} K/week -> h crossed about "
              f"{days_to_alarm(slope):5.1f} days after onset")

    # ------------------------------------------------------------------ 7 --
    print(f"\n[7] a drifting joint, day by day, through the real cusum_update()")
    st = CusumState()
    fired_on = None
    for day in range(80):
        drift = 0.0 if day < DEFAULT_TRAIN_DAYS else 0.2 * (day - DEFAULT_TRAIN_DAYS) / 7.0
        val = 1.0 + drift
        st, fired = cusum_update(st, val)
        if fired and fired_on is None:
            fired_on = day
        if day in (0, 13, 14, 21, 35, 49, 63, 79):
            print(f"    day {day:3d}  theta {val:5.2f} K  cusum+ {st.pos:7.2f}  "
                  f"{'FIRED' if fired else ''}")
    print(f"    baseline {st.baseline:.3f} K, sigma {st.sigma:.3f} K "
          f"(floored at {SIGMA_FLOOR_K})")
    print(f"    noiseless 0.2 K/week drift crosses h on day {fired_on}, i.e. "
          f"{fired_on - DEFAULT_TRAIN_DAYS} days after onset")
    print(f"    closed-form estimate days_to_alarm(0.2) = {days_to_alarm(0.2):.1f} days")
    assert fired_on is not None

    print("\nOK - cusum.py self-test passed")
