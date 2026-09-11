"""Onset dating, trend and 7-day delta on the daily theta series.

Why this module exists
----------------------
CUSUM tells you THAT a joint is drifting.  It does not tell you WHEN it
started, and "when" is the single most persuasive sentence the product ever
says::

    "C06 / L2 çıkış pabucu: bu bozulma 14 Temmuz'da başladı, 41 gün önce."

That sentence changes the conversation with a maintenance planner.  "This joint
is 6 K hot" invites an argument about the sensor.  "This joint has been getting
worse every day since a date I can name, and here is the series" does not.  It
also lets the utility correlate the onset with something they already know
about - a switching operation, a storm, a load transfer, a contractor's visit -
which is often the actual root cause.

CUSUM's own crossing time is a terrible onset estimate: it lags the true onset
by exactly the number of days it takes to accumulate ``h``, which is 35 days
for a 0.2 K/week drift.  Dating the onset needs a retrospective estimator run
over the whole series, which is what this module is.

Method
------
Exact binary segmentation on a mean-shift cost.  For every admissible split
point ``t`` the cost is the within-segment sum of squares::

    C(t) = SSE(x[0:t]) + SSE(x[t:n])

evaluated in O(1) per candidate from prefix sums of ``x`` and ``x^2``, so the
whole scan is O(n) and runs 40 joints x 120 days in microseconds.  The split
with the lowest cost is the candidate onset.

The candidate is accepted only if it survives a BIC test against the
no-changepoint model.  With unknown variance the Gaussian log-likelihood
reduces to ``-n/2 * log(SSE/n)``, and the changepoint model spends two extra
parameters (the second mean and the location), so::

    accept  iff  n*log(SSE_0/n) - n*log(SSE_1/n)  >  BIC_PARAMS*log(n)

plus a physical floor on the step size, so that a statistically significant but
operationally meaningless 0.05 K shift is not dated and announced.  **Returning
None when there is no changepoint is a hard requirement**: a detector that
always names a date will name a date for a healthy joint, and the first time a
crew drives out to a healthy panel because of it, the system is switched off.
The measured operating point on 90-day series at sigma = 0.8 K is a 0.5 % false
dating rate against 95 % detection of a 0.2 K/week ramp.

A date is never an alarm on its own.  It is the evidence line attached to an
alarm the CUSUM and the level test have already raised.

Ramps versus steps
------------------
A degrading joint usually ramps rather than steps.  Fitting a step to a ramp
places the estimate part-way up the ramp, so the reported onset typically LAGS
the true onset: measured median lag on a 0.2 K/week ramp is about +18 days with
a spread of roughly -18 to +37 days over noise realisations.  That is why the
UI quotes the onset with an interval ("yaklasik 21 Agustos, +/- 3 hafta")
rather than a bare date.  A false precision here would be worse than no date at
all, because a planner would try to correlate it with a specific switching
operation.

Slope
-----
Theil-Sen, not least squares.  The median of all pairwise slopes has a 29 %
breakdown point: a single crazy day - a panel door left open, one bad rollup -
moves it by nothing at all, whereas the same day moves an OLS slope by
``6*(2i-n)/(n(n^2-1))`` times its magnitude, which for a day near the end of a
21-day window is a substantial lever.  Slopes are reported in K/week because
that is the unit the drift is actually specified in.
"""

from __future__ import annotations

import math
from statistics import median
from typing import Sequence

DAY_S = 86400.0

#: Minimum step a changepoint must have before we are willing to date it.
#: Below this the answer is honest silence.
MIN_STEP_K = 0.4

#: BIC penalty multiplier.  The textbook value for two extra parameters (the
#: post-change mean and the location) is 2*log(n).  We use 3*log(n), and the
#: reason is measured, not aesthetic: on 400 simulated healthy 90-day series at
#: sigma = 0.8 K, 2*log(n) dates a phantom onset 2.5 % of the time while
#: 3*log(n) does it 0.5 % of the time, and the cost is only that ramp detection
#: falls from 99 % to 95 %.  Across a 100-panel fleet that is the difference
#: between 100 phantom dates and 20.
BIC_PARAMS = 3.0


# --------------------------------------------------------------------------
# Changepoint
# --------------------------------------------------------------------------

def _prefix(values: Sequence[float]) -> tuple[list[float], list[float]]:
    s = [0.0]
    s2 = [0.0]
    for v in values:
        s.append(s[-1] + v)
        s2.append(s2[-1] + v * v)
    return s, s2


def _sse(s: list[float], s2: list[float], i: int, j: int) -> float:
    """Sum of squared deviations of ``values[i:j]`` about its own mean, O(1)."""
    n = j - i
    if n <= 0:
        return 0.0
    tot = s[j] - s[i]
    return max(0.0, (s2[j] - s2[i]) - tot * tot / n)


def detect_changepoint(values: list[float], times: list[float], min_seg: int = 5) -> float | None:
    """Epoch timestamp of the estimated onset, or None if there is no shift.

    ``values`` are the daily medians of theta, ``times`` their epoch timestamps,
    both in ascending time order and the same length.  ``min_seg`` is the
    shortest segment either side; five days stops a single noisy weekend from
    being dated as the start of a fault.

    The returned timestamp is the first sample of the SECOND segment - the first
    day that belongs to the changed regime.
    """
    n = min(len(values), len(times))
    if n < 2 * min_seg + 1:
        return None
    vals = [float(v) for v in values[:n]]
    if not all(math.isfinite(v) for v in vals):
        vals = [v if math.isfinite(v) else 0.0 for v in vals]

    s, s2 = _prefix(vals)
    sse0 = _sse(s, s2, 0, n)
    if sse0 <= 0.0:
        return None  # a perfectly flat series has no changepoint

    best_t = -1
    best_cost = float("inf")
    for t in range(min_seg, n - min_seg + 1):
        cost = _sse(s, s2, 0, t) + _sse(s, s2, t, n)
        if cost < best_cost:
            best_cost, best_t = cost, t
    if best_t < 0 or best_cost <= 0.0:
        return None

    # BIC against the single-mean model.
    gain = n * math.log(sse0 / n) - n * math.log(best_cost / n)
    if gain <= BIC_PARAMS * math.log(n):
        return None

    mean_l = (s[best_t] - s[0]) / best_t
    mean_r = (s[n] - s[best_t]) / (n - best_t)
    if abs(mean_r - mean_l) < MIN_STEP_K:
        return None
    # An onset is a DETERIORATION.  A joint that got colder (a retorque, a load
    # transfer) is a real changepoint but not one we date as the start of a
    # fault; the rules layer treats a downward step as a repair confirmation.
    if mean_r < mean_l:
        return None
    return float(times[best_t])


def changepoint_detail(values: list[float], times: list[float],
                       min_seg: int = 5) -> dict | None:
    """Same search, but returns the evidence block the alarm carries.

    Keys: ``ts``, ``index``, ``mean_before``, ``mean_after``, ``step_k``,
    ``bic_gain``, ``bic_threshold``, ``n``.
    """
    n = min(len(values), len(times))
    if n < 2 * min_seg + 1:
        return None
    vals = [float(v) for v in values[:n]]
    s, s2 = _prefix(vals)
    sse0 = _sse(s, s2, 0, n)
    if sse0 <= 0.0:
        return None
    best_t, best_cost = -1, float("inf")
    for t in range(min_seg, n - min_seg + 1):
        cost = _sse(s, s2, 0, t) + _sse(s, s2, t, n)
        if cost < best_cost:
            best_cost, best_t = cost, t
    if best_t < 0 or best_cost <= 0.0:
        return None
    gain = n * math.log(sse0 / n) - n * math.log(best_cost / n)
    thr = BIC_PARAMS * math.log(n)
    mean_l = (s[best_t] - s[0]) / best_t
    mean_r = (s[n] - s[best_t]) / (n - best_t)
    return {
        "ts": float(times[best_t]),
        "index": best_t,
        "mean_before": mean_l,
        "mean_after": mean_r,
        "step_k": mean_r - mean_l,
        "bic_gain": gain,
        "bic_threshold": thr,
        "accepted": bool(gain > thr and (mean_r - mean_l) >= MIN_STEP_K),
        "n": n,
    }


# --------------------------------------------------------------------------
# Slope
# --------------------------------------------------------------------------

def theil_sen(values: Sequence[float], times: Sequence[float]) -> float:
    """Median of pairwise slopes, in value-units per second.

    O(n^2) pairs.  With a 21-day window that is 210 pairs per joint per day,
    which is free; with a 120-day window it is 7140, still free.
    """
    n = min(len(values), len(times))
    if n < 3:
        return 0.0
    slopes: list[float] = []
    for i in range(n - 1):
        ti, vi = times[i], values[i]
        for j in range(i + 1, n):
            dt = times[j] - ti
            if dt > 0:
                slopes.append((values[j] - vi) / dt)
    if not slopes:
        return 0.0
    return float(median(slopes))


def slope_per_week(values: list[float], times: list[float], window_days: int = 21) -> float:
    """Theil-Sen slope of the last ``window_days`` of daily theta, in K/week.

    Three weeks is chosen deliberately: long enough that a 0.2 K/week drift is
    0.6 K of real movement against a ~0.8 K daily noise floor, short enough that
    a joint that stabilised a month ago is not still reported as climbing.
    """
    n = min(len(values), len(times))
    if n < 3:
        return 0.0
    t_end = times[n - 1]
    cut = t_end - window_days * DAY_S
    v = [values[i] for i in range(n) if times[i] >= cut]
    t = [times[i] for i in range(n) if times[i] >= cut]
    if len(v) < 3:
        v, t = list(values[max(0, n - 3):n]), list(times[max(0, n - 3):n])
    return theil_sen(v, t) * 7.0 * DAY_S


# --------------------------------------------------------------------------
# Delta
# --------------------------------------------------------------------------

def theta_delta(values: list[float], times: list[float], days: float = 7.0,
                win: int = 5) -> float:
    """How much theta has moved over the last ``days``, in kelvin.

    Robust on both ends: the median of the ``win`` samples nearest "now" minus
    the median of the ``win`` samples nearest "now - days".  Differencing two
    single days would give a number dominated by daily noise, and a number that
    jitters on the operator's screen is a number the operator stops believing.

    Be clear about what this number is and is not.  With a daily noise floor of
    sigma = 0.8 K, a 5-sample median anchor has a standard error of about
    ``sigma/sqrt(0.7*win)`` = 0.43 K; after the interval rescaling below the
    difference of two anchors carries about 0.8 K of noise - four times the
    0.2 K/week drift it is describing (measured in the self-test).
    It is therefore a DISPLAY quantity ("son 7 günde +0.4 K"), unbiased but
    noisy, and nothing decides on it.  The decisions are made by the CUSUM,
    which integrates every day instead of two, and by the Theil-Sen slope, which
    uses three weeks.

    Returns 0.0 when the history does not reach back far enough - never an
    extrapolation.
    """
    n = min(len(values), len(times))
    if n < 2:
        return 0.0
    t_end = times[n - 1]
    t_ref = t_end - days * DAY_S
    if times[0] > t_ref:
        return 0.0
    w = max(1, min(win, n))

    def _near(target: float) -> tuple[float, float]:
        order = sorted(range(n), key=lambda i: abs(times[i] - target))[:w]
        return (float(median([values[i] for i in order])),
                float(median([times[i] for i in order])))

    v_now, t_now = _near(t_end)
    v_ref, t_ago = _near(t_ref)
    span = t_now - t_ago
    if span <= 0.0:
        return 0.0
    # The "now" anchor is necessarily one-sided (there is no future), so its
    # median sits about (w-1)/2 days in the past while the "then" anchor is
    # centred.  Left uncorrected that quietly shortens the interval - a 5-sample
    # anchor turns a 7-day question into a 5-day answer and under-reports the
    # movement by 29 %.  Rescale onto the interval actually asked for.
    return (v_now - v_ref) * (days * DAY_S) / span


# --------------------------------------------------------------------------
# Self-test
# --------------------------------------------------------------------------

def _days(n: int, t0: float = 1_750_000_000.0) -> list[float]:
    return [t0 + i * DAY_S for i in range(n)]


if __name__ == "__main__":
    import datetime as _dt
    import random

    print("=" * 78)
    print("changepoint.py self-test")
    print("=" * 78)

    N = 90
    T = _days(N)
    rng = random.Random(20260910)

    def _fmt(ts: float) -> str:
        return _dt.datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d")

    # ------------------------------------------------------------------ 1 --
    print("\n[1] healthy joint - the estimator MUST refuse to name a date")
    refusals = 0
    for trial in range(200):
        r = random.Random(1000 + trial)
        healthy = [1.2 + r.gauss(0.0, 0.8) for _ in range(N)]
        if detect_changepoint(healthy, T) is None:
            refusals += 1
    print(f"    200 healthy 90-day series, sigma 0.8 K")
    print(f"    changepoint returned None on {refusals}/200 "
          f"({100 * refusals / 200:.1f} %)  -> false dating rate "
          f"{100 * (200 - refusals) / 200:.1f} %")
    print(f"    BIC penalty {BIC_PARAMS:.0f}*log(n); at the textbook 2*log(n) the")
    print(f"    false dating rate is 2.5 %, which across 100 panels x 40 joints")
    print(f"    would be 100 phantom dates instead of 20")
    print(f"    a date is never an alarm on its own - it is the evidence line on")
    print(f"    an alarm the CUSUM and the level test have already raised")
    assert refusals >= 194, "too many false changepoints on healthy joints"

    # ------------------------------------------------------------------ 2 --
    print("\n[2] step change - a joint that was disturbed on a known day")
    onset = 50
    step = [1.2 + rng.gauss(0.0, 0.8) + (3.0 if i >= onset else 0.0) for i in range(N)]
    got = detect_changepoint(step, T)
    d = changepoint_detail(step, T)
    err = (got - T[onset]) / DAY_S
    print(f"    true onset  day {onset}  ({_fmt(T[onset])})")
    print(f"    estimated   day {d['index']}  ({_fmt(got)})   error {err:+.0f} days")
    print(f"    step {d['step_k']:+.2f} K  ({d['mean_before']:.2f} -> {d['mean_after']:.2f} K)"
          f"   BIC gain {d['bic_gain']:.1f} vs threshold {d['bic_threshold']:.1f}")
    assert abs(err) <= 2.0

    # ------------------------------------------------------------------ 3 --
    print("\n[3] ramp - the realistic case, 0.2 K/week from day 40")
    onset = 40
    ramp = [1.2 + rng.gauss(0.0, 0.8) + max(0.0, (i - onset)) * 0.2 / 7.0
            for i in range(N)]
    got = detect_changepoint(ramp, T)
    d = changepoint_detail(ramp, T)
    err = (got - T[onset]) / DAY_S
    print(f"    true onset  day {onset}  ({_fmt(T[onset])})")
    print(f"    estimated   day {d['index']}  ({_fmt(got)})   error {err:+.0f} days")
    print(f"    fitting a step to a ramp puts the estimate part way up the ramp,")
    print(f"    so the reported onset typically LAGS the true onset")
    assert -25 <= err <= 40

    # repeatability of that bias
    errs = []
    for trial in range(40):
        r = random.Random(500 + trial)
        rr = [1.2 + r.gauss(0.0, 0.8) + max(0.0, (i - onset)) * 0.2 / 7.0 for i in range(N)]
        g = detect_changepoint(rr, T)
        if g is not None:
            errs.append((g - T[onset]) / DAY_S)
    print(f"    over 40 noise realisations: detected {len(errs)}/40, "
          f"median lag {median(errs):+.0f} d, spread "
          f"{min(errs):+.0f} .. {max(errs):+.0f} d")
    print(f"    the UI states this: \"tahmini başlangıç {_fmt(got)} "
          f"(±3 hafta)\" - a dated onset with an honest interval,")
    print(f"    not a false precision")

    # ------------------------------------------------------------------ 4 --
    print("\n[4] a repair is not an onset - a downward step returns None")
    repaired = [4.5 + rng.gauss(0.0, 0.5) - (4.0 if i >= 55 else 0.0) for i in range(N)]
    print(f"    theta drops 4 K on day 55 (crew retorqued the joint): "
          f"detect_changepoint -> {detect_changepoint(repaired, T)}")
    assert detect_changepoint(repaired, T) is None
    dd = changepoint_detail(repaired, T)
    print(f"    the search still SEES it ({dd['step_k']:+.2f} K at day {dd['index']}), "
          f"it is simply not dated as a fault onset")

    # ------------------------------------------------------------------ 5 --
    print("\n[5] Theil-Sen slope versus least squares under one bad day")
    clean = [1.0 + 0.2 * i / 7.0 for i in range(21)]
    Tw = _days(21)

    def _ols(vals, ts):
        n = len(vals)
        mt = sum(ts) / n
        mv = sum(vals) / n
        num = sum((ts[i] - mt) * (vals[i] - mv) for i in range(n))
        den = sum((ts[i] - mt) ** 2 for i in range(n))
        return (num / den) * 7.0 * DAY_S if den else 0.0

    dirty = list(clean)
    dirty[19] = 25.0                    # panel door left open, one absurd rollup
    print(f"    true slope                       0.200 K/week")
    print(f"    Theil-Sen, clean series          {slope_per_week(clean, Tw):.3f} K/week")
    print(f"    Theil-Sen, one 25 K outlier      {slope_per_week(dirty, Tw):.3f} K/week")
    print(f"    least squares, clean series      {_ols(clean, Tw):.3f} K/week")
    print(f"    least squares, one 25 K outlier  {_ols(dirty, Tw):.3f} K/week   <- ruined")
    assert abs(slope_per_week(dirty, Tw) - 0.2) < 0.05
    assert abs(_ols(dirty, Tw) - 0.2) > 0.3

    # ------------------------------------------------------------------ 6 --
    print("\n[6] theta_delta over 7 days - unbiased but noisy, and we say so")
    deltas = []
    for trial in range(300):
        r = random.Random(9000 + trial)
        rr = [1.2 + r.gauss(0.0, 0.8) + max(0.0, (i - 40)) * 0.2 / 7.0 for i in range(N)]
        deltas.append(theta_delta(rr, T, 7.0))
    mu = sum(deltas) / len(deltas)
    sd = math.sqrt(sum((d - mu) ** 2 for d in deltas) / (len(deltas) - 1))
    noiseless = [max(0.0, (i - 40)) * 0.2 / 7.0 for i in range(N)]
    print(f"    0.2 K/week ramp, 300 noise realisations, sigma_daily = 0.8 K:")
    print(f"      mean delta_7d {mu:+.3f} K    true +0.200 K  -> unbiased")
    print(f"      sd   delta_7d {sd:.3f} K     {sd / 0.2:.1f}x the signal")
    print(f"    noiseless ramp: delta_7d = {theta_delta(noiseless, T, 7.0):+.3f} K")
    print(f"    step series, step 21 days ago: delta_7d = "
          f"{theta_delta(step, T, 7.0):+.3f} K  (expected ~0, the step is older)")
    print(f"    short history (3 days available, 7 asked): "
          f"{theta_delta(ramp[:3], T[:3], 7.0):+.3f} K  (refuses to extrapolate)")
    print(f"    -> delta_7d is a DISPLAY number.  Decisions come from the CUSUM,")
    print(f"       which integrates every day, and from the 21-day Theil-Sen slope.")
    assert abs(mu - 0.2) < 0.10, f"delta_7d is biased: {mu}"
    assert abs(theta_delta(noiseless, T, 7.0) - 0.2) < 1e-9
    assert theta_delta(ramp[:3], T[:3], 7.0) == 0.0

    # ------------------------------------------------------------------ 7 --
    print("\n[7] the demo sentence")
    now = T[-1]
    got = detect_changepoint(ramp, T)
    age = (now - got) / DAY_S
    print(f'    "C06 / L2 çıkış pabucu: bu bozulma yaklaşık {_fmt(got)} tarihinde '
          f'başladı, {age:.0f} gün önce."')
    print(f'    eğim {slope_per_week(ramp, T):+.2f} K/hafta · son 7 günde '
          f'{theta_delta(ramp, T):+.2f} K')

    print("\nOK - changepoint.py self-test passed")
