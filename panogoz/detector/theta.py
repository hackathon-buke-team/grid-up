"""theta - the load-corrected, sibling-differential temperature excess.

The whole product rests on one number::

    theta_i = [ T_i - median(T_siblings) ] / (I / I_ref)^2      [K at I_ref]

Read it as "how many kelvin hotter than its own two sibling phases this joint
would be if it were carrying its rated current".

Why this and not a thermometer with a threshold
-----------------------------------------------
A joint's absolute temperature is dominated by load and by season, not by its
condition.  A 62 C lug at 09:00 in February is a defect; the same 62 C at 15:00
in August at full load is normal.  Any fixed threshold therefore has to be set
high enough to survive August, which makes it blind in February.

theta removes both confounders by construction:

* **Load** divides out.  Joule heating at a bolted joint is ``dR * I^2``, so the
  steady excess over an identical sibling is proportional to ``I^2``.  Dividing
  by ``(I/I_ref)^2`` leaves a quantity that does not move with load.
* **Ambient, season, solar gain and cabinet convection** subtract out.  The
  siblings are three co-located conductors in the same air, 20 mm apart, on the
  same busbar, of the same age.  Whatever the air does, it does to all three.
* **Emissivity** cancels for the IR array: the three lugs present identical
  surfaces to the same pixel array at the same angle.

And it needs **no history**.  Three identical phases on one busbar are a valid
baseline on installation day, which is why PANO GOZ is useful in week one
instead of after a year of "learning".  theta is not a new invention: it is the
load-corrected "delta-T over a similar component under similar load" that IR
thermography practice (NETA / IEC TS 62271-37-082 style acceptance criteria)
has always prescribed, computed continuously instead of once a year by a
contractor with a camera.

Estimating theta: regress THROUGH the model, never deconvolve
-------------------------------------------------------------
A joint is not a resistor with a thermometer glued to it; it is a thermal mass.
The measured excess follows the load with a first-order lag::

    dT_excess[k] = a * dT_excess[k-1] + (1 - a) * theta * f[k]^2
    a = exp(-dt / tau),    f = I / I_ref

The tempting move is to invert that pointwise::

    theta_hat[k] = ( dT[k] - a*dT[k-1] ) / ( (1 - a) * f[k]^2 )       # DO NOT

That is a deconvolution, and it multiplies the sensor noise by

    G = sqrt(1 + a^2) / (1 - a)

At dt = 60 s and tau = 20 min, ``a = 0.9512`` and ``G = 28.3``.  A TMP117 pair
with sigma_m = 0.2 K therefore produces a per-sample theta estimate with a
standard deviation of 5.7 K - larger than the 5 K defect we are hunting.  The
self-test at the bottom of this file measures both estimators on the same
synthetic data and prints the two relative standard deviations, so the factor
is a number we computed, not a number we asserted.

The right move is the opposite one: keep the forward model and regress through
it.  Write the model as a linear regression in theta::

    y[k] = dT[k] - a*dT[k-1]          (target)
    x[k] = (1 - a) * f[k]^2           (regressor)
    y[k] = theta * x[k] + noise

and run a one-parameter recursive least squares with a forgetting factor.  RLS
averages the same information over thousands of samples instead of one, so its
noise is smaller by roughly the square root of the effective window length.
It is also cheap: five floats of state and about ten flops per joint per
sample, which is what lets the whole thing run on the gateway.

Two engineering details that matter in the field:

* **Covariance windup.**  When the panel is lightly loaded ``x`` is tiny and the
  sample carries no information about theta.  A naive forgetting factor keeps
  inflating ``P`` through those samples, and the first informative sample after
  a quiet night then produces an enormous jump.  We simply do not forget on
  uninformative samples, and we cap ``P``.
* **tau does not have to be right.**  Under quasi-static load the least-squares
  solution is exactly invariant to the assumed ``a``: substituting the true
  model into the normal equations gives
  ``theta_hat = theta * [(a - a') + (1 - a)] / (1 - a') = theta``.
  Only genuinely fast load steps leak error, and the leakage is second order.
  A 100 % error in tau costs a couple of percent of bias, which is why
  :func:`identify_tau` searches a five-point logarithmic grid and stops.

Reporting excess resistance
---------------------------
Given theta the excess contact resistance follows from ``theta = dR * I_ref^2 *
R_th``, so ``dR = theta / (R_th * I_ref^2)``.  ``R_th,local`` is only known to a
factor, so dR is ALWAYS reported as an interval with the assumed R_th range
attached, never as a single number.

For a localised source on a busbar behaving as a two-sided fin,
``R_th = 1 / (2*sqrt(h*P*k*A))``; with k = 400 W/mK, A = 2e-3 m2, P = 0.44 m and
h = 5..12 W/m2K that is 0.24..0.38 K/W.  A lug on a 240 mm2 cable tail, where
the heat has only the cable to run into, is 2..4 K/W.  A real feeder lug sits
between the two depending on which side of the joint dominates the heat path,
which is exactly why the answer is an interval.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import median
from typing import Sequence

from panogoz.contracts import assets

# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------

#: Thermal resistance of a localised source, K/W.  Busbar-side: two-sided fin
#: on 2x(100x10) mm2 tinned copper.  Lug-side: 240 mm2 cable tail.
R_TH_BUSBAR_LO = 0.24
R_TH_BUSBAR_HI = 0.38
R_TH_LUG_LO = 2.0
R_TH_LUG_HI = 4.0

#: Sibling-differential measurement noise, 1 sigma, kelvin.
#: TC pair: two TMP117 on the same clip family, systematic offset cancels.
#: IR pixel pair: MLX90640 pixel-to-pixel noise dominates.
SIGMA_TC_K = 0.2
SIGMA_IR_K = 0.8

#: The defect size the product promises to see.  A 400 A lug degraded from a
#: healthy 2-5 microohm to 50 microohm dissipates 8.0 W; on the busbar-side fin
#: that is about 2.4 K, and it keeps growing.  5 K is where we commit to an
#: alarm, which is why sensitivity is quoted against it.
THETA_ALARM_K = 5.0

#: Below this load factor a 5 K defect is no longer 3 sigma above the noise for
#: a TC pair, so the panel is honestly declared SENSITIVITY_LOW.
#: f_low = sqrt(3*sigma/theta_ref) = sqrt(3*0.2/5.0) = 0.3464
SENSITIVITY_LOW_F = math.sqrt(3.0 * SIGMA_TC_K / THETA_ALARM_K)

#: RLS guards.  ``X_MIN`` is the regressor below which a sample carries no
#: information about theta (f^2 under ~2 % of rating).  ``P_MAX`` caps the
#: covariance so a long de-energised spell cannot produce a jump on return.
X_MIN = 1e-5
P_MAX = 1.0e4


# --------------------------------------------------------------------------
# State
# --------------------------------------------------------------------------

@dataclass
class ThetaState:
    """Per-joint estimator state.  Five floats plus a counter.

    Maps one-to-one onto the ``joint_state`` columns ``theta``, ``theta_p``,
    ``dt_excess``, ``tau_s`` and ``resid_ewma`` so it survives a restart.
    """

    theta: float = 0.0          #: kelvin at reference current
    p: float = 100.0            #: RLS covariance
    dt_excess: float = 0.0      #: last measured excess over siblings, K
    tau_s: float = 1200.0       #: thermal time constant, s
    resid_ewma: float = 0.0     #: EWMA of |innovation|, a model-fit health metric
    n: int = 0                  #: samples folded in

    def to_row(self) -> dict:
        """Column names as they appear in ``store/schema.sql``."""
        return {
            "theta": self.theta,
            "theta_p": self.p,
            "dt_excess": self.dt_excess,
            "tau_s": self.tau_s,
            "resid_ewma": self.resid_ewma,
            "train_n": self.n,
        }

    @classmethod
    def from_row(cls, row: dict) -> "ThetaState":
        """Restore from a ``joint_state`` row.

        ``train_n`` in the schema is the CUSUM's training-day counter, not the
        RLS sample counter - there is only one integer column and the CUSUM
        needs it.  The RLS only ever asks one question of ``n``: "am I past my
        cold start?", because ``n == 0`` triggers a re-seed that would throw the
        restored theta away.  A persisted row whose covariance or lag state has
        moved off its defaults answers that question by itself, so we infer it
        rather than store it.  Getting this wrong would mean every process
        restart silently reset the estimator it had just carefully reloaded.
        """
        theta = float(row.get("theta") or 0.0)
        p = float(row.get("theta_p") or 100.0)
        dt_excess = float(row.get("dt_excess") or 0.0)
        n = int(row.get("train_n") or 0)
        if n == 0 and (abs(p - 100.0) > 1e-12 or dt_excess != 0.0 or theta != 0.0):
            n = 1
        return cls(
            theta=theta,
            p=p,
            dt_excess=dt_excess,
            tau_s=float(row.get("tau_s") or 1200.0),
            resid_ewma=float(row.get("resid_ewma") or 0.0),
            n=n,
        )


# --------------------------------------------------------------------------
# The estimator
# --------------------------------------------------------------------------

def rls_update(st: ThetaState, dt_excess_meas: float, load_factor: float, dt_s: float,
               lam: float = 0.9995, r: float = 1.0) -> ThetaState:
    """Fold one sample into the recursive least squares estimate of theta.

    ``dt_excess_meas`` is ``T_joint - median(T_siblings)`` in kelvin, straight
    from the sensors with no filtering.  ``load_factor`` is ``I / I_ref`` for
    THIS joint at THIS instant, from the clip's own split-core CT (no outgoing
    way in a TEDAS panel has a utility CT, which is why every clip carries one).

    The regression is through the forward model, never its inverse::

        y = dT[k] - a*dT[k-1]        x = (1-a)*f^2        y = theta*x + noise

    with ``a = exp(-dt/tau)``.  Returns a NEW state; the input is not mutated,
    so a caller can evaluate a hypothesis without disturbing the live estimate.

    ``lam`` is the forgetting factor.  0.9995 at a 60 s cadence is an effective
    window of 1/(1-lam) = 2000 samples = 33 hours, long enough to average the
    noise down by ~45x and short enough to follow a joint that is degrading
    over weeks.
    """
    out = ThetaState(st.theta, st.p, st.dt_excess, st.tau_s, st.resid_ewma, st.n)

    if dt_s <= 0.0 or not math.isfinite(dt_excess_meas) or not math.isfinite(load_factor):
        return out

    f2 = max(0.0, load_factor) ** 2

    # Cold start.  The ARX form needs a previous sample to build y, so the very
    # first observation is used to seed the lag state and - when the panel is
    # loaded enough for the quasi-static approximation to hold - to seed theta
    # itself.  Seeding beats letting a P=100 prior take a 4x step on sample one.
    if out.n == 0:
        out.dt_excess = dt_excess_meas
        if f2 >= 0.04:  # f >= 0.2
            out.theta = dt_excess_meas / f2
        out.n = 1
        return out

    a = math.exp(-dt_s / max(out.tau_s, 1.0))
    x = (1.0 - a) * f2
    y = dt_excess_meas - a * out.dt_excess
    out.dt_excess = dt_excess_meas
    out.n += 1

    if x < X_MIN:
        # Uninformative sample (panel dark or nearly so).  Do NOT forget, or the
        # covariance winds up and the first loaded sample of the morning throws
        # theta across the room.
        return out

    denom = lam * r + x * x * out.p
    if denom <= 0.0:
        return out
    gain = out.p * x / denom
    err = y - x * out.theta
    out.theta += gain * err
    out.p = min((out.p - gain * x * out.p) / lam, P_MAX)
    out.resid_ewma = 0.98 * out.resid_ewma + 0.02 * abs(err)
    return out


def naive_theta(dt_now: float, dt_prev: float, load_factor: float, dt_s: float,
                tau_s: float = 1200.0) -> float | None:
    """Pointwise deconvolution.  Present ONLY so the self-test can measure how
    bad it is; nothing in the product calls it.

    Noise gain ``sqrt(1+a^2)/(1-a)``, which is 28.3 at dt = 60 s, tau = 20 min.
    """
    f2 = max(0.0, load_factor) ** 2
    a = math.exp(-dt_s / max(tau_s, 1.0))
    x = (1.0 - a) * f2
    if x < X_MIN:
        return None
    return (dt_now - a * dt_prev) / x


def deconvolution_noise_gain(dt_s: float, tau_s: float) -> float:
    """``sqrt(1+a^2)/(1-a)`` - the factor by which pointwise inversion
    multiplies sensor noise."""
    a = math.exp(-dt_s / max(tau_s, 1.0))
    return math.sqrt(1.0 + a * a) / max(1.0 - a, 1e-12)


# --------------------------------------------------------------------------
# Detectability
# --------------------------------------------------------------------------

def theta_min(sigma_m: float, load_factor: float, k_sigma: float = 3.0) -> float:
    """Smallest theta that is ``k_sigma`` above the sibling-differential noise.

    At load factor f a defect of size theta produces only ``theta * f^2`` of
    actual measured excess, so the detectable floor grows as ``1/f^2``::

        theta_min(f) = k_sigma * sigma_m / f^2

    With sigma_m = 0.2 K (TC pair) and k_sigma = 3:
    f = 0.85 -> 0.83 K, f = 0.60 -> 1.67 K, f = 0.40 -> 3.75 K, f = 0.20 -> 15 K.

    Saying this out loud is a feature.  A system that reports "all normal" at
    03:00 on a 12 % loaded feeder is lying; PANO GOZ reports SENSITIVITY_LOW.
    """
    f2 = max(0.0, load_factor) ** 2
    if f2 <= 0.0:
        return float("inf")
    return k_sigma * sigma_m / f2


def sensitivity_pct(theta_ref: float, sigma_m: float, load_factor: float) -> float:
    """Visibility, 0..100 %: can we currently see a defect of size ``theta_ref``?

    100 % means ``theta_ref`` is at or above the 3-sigma floor right now.  The
    number falls as the square of the load factor, which is exactly the honest
    shape: at 20 % load a 5 K defect is a third of the way to visible.
    """
    if theta_ref <= 0.0:
        return 0.0
    tmin = theta_min(sigma_m, load_factor)
    if not math.isfinite(tmin) or tmin <= 0.0:
        return 0.0
    return 100.0 * min(1.0, theta_ref / tmin)


def sensitivity_low(load_factor: float, sigma_m: float = SIGMA_TC_K,
                    theta_ref: float = THETA_ALARM_K) -> bool:
    """True when the panel must declare SENSITIVITY_LOW."""
    return sensitivity_pct(theta_ref, sigma_m, load_factor) < 100.0


# --------------------------------------------------------------------------
# tau identification
# --------------------------------------------------------------------------

def _fit_theta(dt_excess: Sequence[float], load_factor: Sequence[float],
               dt_s: float, tau: float) -> tuple[float, float]:
    """Batch least squares for one assumed tau.  Returns (theta, normalised SSE).

    The SSE is divided by ``1 + a^2`` because that is the variance of the target
    ``y = dT[k] - a*dT[k-1]`` under white sensor noise.  Without that
    normalisation the criterion would trivially prefer the largest ``a``, which
    shrinks the residual by shrinking the signal.  This is the profiled
    Gaussian likelihood, not a fudge.
    """
    n = min(len(dt_excess), len(load_factor))
    if n < 3:
        return 0.0, float("inf")
    a = math.exp(-dt_s / max(tau, 1.0))
    sxx = sxy = 0.0
    for k in range(1, n):
        f = max(0.0, load_factor[k])
        x = (1.0 - a) * f * f
        y = dt_excess[k] - a * dt_excess[k - 1]
        sxx += x * x
        sxy += x * y
    if sxx <= 0.0:
        return 0.0, float("inf")
    th = sxy / sxx
    sse = 0.0
    for k in range(1, n):
        f = max(0.0, load_factor[k])
        x = (1.0 - a) * f * f
        y = dt_excess[k] - a * dt_excess[k - 1]
        e = y - th * x
        sse += e * e
    return th, sse / (1.0 + a * a)


def identify_tau(dt_excess: list[float], load_factor: list[float], dt_s: float,
                 grid=(300, 600, 1200, 2400, 3600)) -> float:
    """Pick the thermal time constant from a coarse logarithmic grid.

    Five points spanning 5 minutes to 1 hour is enough, and that is a provable
    claim rather than a convenient one: under quasi-static load the least
    squares estimate of theta is exactly invariant to the assumed ``a`` (see the
    module docstring), so the grid only has to be fine enough to keep the
    transient leakage small.  The self-test measures the residual bias at
    tau/2 and 2*tau and prints it.
    """
    best_tau = float(grid[len(grid) // 2])
    best_sse = float("inf")
    for tau in grid:
        _, sse = _fit_theta(dt_excess, load_factor, dt_s, float(tau))
        if sse < best_sse:
            best_sse, best_tau = sse, float(tau)
    return best_tau


# --------------------------------------------------------------------------
# Excess resistance
# --------------------------------------------------------------------------

def excess_resistance_uohm(theta_k: float, i_ref_a: float,
                           r_th_lo: float = R_TH_LUG_LO,
                           r_th_hi: float = R_TH_LUG_HI) -> tuple[float, float, float]:
    """Excess contact resistance implied by theta, in microohms, as an INTERVAL.

    ``dR = theta / (R_th * I_ref^2)``.  A larger R_th means the same temperature
    rise is produced by less power, hence less resistance, so ``r_th_hi``
    produces the LOW end of the interval.  The middle value uses the geometric
    mean of the R_th bounds, because R_th is known to a multiplicative factor,
    not to an additive one.

    Returns ``(lo, mid, hi)`` in microohms, always ascending.  Never quote the
    middle number on its own: the honest sentence is "38 to 76 microohm of
    excess, assuming R_th,local = 2 to 4 K/W for a 240 mm2 lug".

    Reference points for a sanity check: a healthy tinned bolted joint is
    2-5 microohm; at the panel's 2312 A rating that is about 27 W.  The same
    joint degraded to 50 microohm dissipates 267 W.  A 400 A feeder lug at
    50 microohm dissipates 8.0 W.
    """
    if i_ref_a <= 0.0 or not math.isfinite(theta_k):
        return (0.0, 0.0, 0.0)
    lo_r, hi_r = min(r_th_lo, r_th_hi), max(r_th_lo, r_th_hi)
    if lo_r <= 0.0:
        return (0.0, 0.0, 0.0)
    mid_r = math.sqrt(lo_r * hi_r)
    scale = 1e6 / (i_ref_a * i_ref_a)
    return (theta_k * scale / hi_r, theta_k * scale / mid_r, theta_k * scale / lo_r)


def power_w(excess_r_uohm: float, current_a: float) -> float:
    """``I^2 * dR`` in watts - the number a maintenance engineer actually feels."""
    return current_a * current_a * excess_r_uohm * 1e-6


# --------------------------------------------------------------------------
# Sibling handling
# --------------------------------------------------------------------------

def sibling_excess(temps: dict[str, float], key: str) -> tuple[float, float] | None:
    """``(excess_k, sibling_median_c)`` for one joint, or None if not comparable.

    Peers come from :func:`panogoz.contracts.assets.sibling_groups`: the three
    phases of one feeder, in the same air, on the same bar, of the same age,
    presenting the same surface.  The neutral is deliberately NOT a peer of the
    phases - it carries the unbalance plus the triplens, so it is its own group
    and is judged by rule H3 in :mod:`panogoz.detector.neutral`.

    The reference is the median of the WHOLE group, the joint under test
    included - not the median of the other two.  With a three-element peer set
    those two choices behave very differently, and the difference matters::

        T = [45.8, 35.8, 35.8]      one hot phase, 10 K excess

        median of the OTHER two ->  L1 +10.0,  L2 -5.0,  L3 -5.0
        median of ALL three     ->  L1 +10.0,  L2  0.0,  L3  0.0

    Excluding self makes the reference itself move with the defect and smears
    a single fault across all three phases, so the operator sees a whole feeder
    lit up instead of one lug.  Including self gives the median a breakdown
    point of 1/3: one bad element cannot move it at all.

    That robustness has a small, exactly computable price, and it is worth
    stating because it is the kind of thing an auditor finds later.  When one
    member really is the outlier, the median of three IS the LARGER of the other
    two, not their midpoint.  For two independent readings with per-sensor noise
    ``sigma_1``, ``E[max] = sigma_1/sqrt(pi)``, and since a pair difference of
    ``sigma_m`` comes from ``sigma_1 = sigma_m/sqrt(2)``, the outlier's excess is
    biased LOW by::

        bias = sigma_m / sqrt(2*pi) = 0.3989 * sigma_m

    which is 0.08 K for a clip pair and 0.32 K for an IR pixel pair.  In theta
    units that is ``0.3989*sigma_m/f^2`` - exactly 13.3 % of the ``3*sigma_m/f^2``
    detection floor, at EVERY load factor.  So the effective detection threshold
    is 3.13 sigma rather than 3 sigma, and the bias can never change a decision.
    We do not correct for it: the correction is only valid when the joint under
    test really is the outlier, and applying it to a healthy joint would
    manufacture a positive offset out of nothing.  The self-test in
    ``tests/test_detector.py`` measures this bias and checks it against the
    closed form.

    The honest limit of a three-element set: if TWO of the three phases are
    equally bad, the median IS a bad phase and the healthy one reads negative.
    That is why a large NEGATIVE theta is itself reported (the rules layer
    treats it as a peer-set-integrity finding) rather than being clipped to zero
    and forgotten.

    Requires at least three group members with finite readings.  With two, the
    median is the midpoint of a pair and a fault in either is indistinguishable
    from a fault in the other; refusing to answer beats answering wrongly.
    """
    joint = assets.JOINTS_BY_KEY.get(key)
    if joint is None or key not in temps:
        return None
    group = joint.sibling_group
    vals = [
        v for k, v in temps.items()
        if k in assets.JOINTS_BY_KEY
        and assets.JOINTS_BY_KEY[k].sibling_group == group
        and math.isfinite(v)
    ]
    if len(vals) < 3:
        return None
    med = float(median(vals))
    return (float(temps[key]) - med, med)


def robust_z(value: float, peers: list[float]) -> float:
    """MAD-based robust z score of ``value`` against its peer set.

    Median and MAD instead of mean and standard deviation because with three
    phases a single bad sensor is 33 % of the sample and would drag a mean
    estimator straight past the defect it is supposed to reveal.
    ``sigma = 1.4826 * MAD`` (the normal-consistency constant), floored at 2 %
    of the median so that a set of identical readings does not produce an
    infinite score on a rounding difference.
    """
    vals = [p for p in peers if math.isfinite(p)]
    if not vals:
        return 0.0
    med = float(median(vals))
    mad = float(median([abs(p - med) for p in vals]))
    sigma = 1.4826 * mad
    floor = max(0.02 * abs(med), 1e-6)
    sigma = max(sigma, floor)
    return (value - med) / sigma


# --------------------------------------------------------------------------
# Self-test
# --------------------------------------------------------------------------

def _simulate(theta_true: float, tau_s: float, dt_s: float, n: int, sigma: float,
              seed: int, f_of_k, ambient_shift: float = 0.0):
    """Forward thermal model through ABSOLUTE temperatures, then differenced.

    Three co-located conductors are simulated: the defective one and two healthy
    siblings.  All three see the same ambient, the same diurnal air swing and the
    same self-heating, so ``ambient_shift`` is applied to all three.  What the
    estimator receives is what the product actually computes,
    ``T_joint - median(T_siblings)``, so the ambient cancellation is exercised
    rather than assumed.  Deterministic in ``seed``.
    """
    import random

    rng = random.Random(seed)
    a = math.exp(-dt_s / tau_s)
    dt_true = 0.0
    meas: list[float] = []
    loads: list[float] = []
    abs_temps: list[float] = []
    for k in range(n):
        f = f_of_k(k)
        dt_true = a * dt_true + (1.0 - a) * theta_true * f * f
        h = (k * dt_s / 3600.0) % 24.0
        # Common mode: ambient base, diurnal air swing, and the I^2R self-heating
        # of the healthy conductors.  None of it is a defect; all of it is what
        # wrecks an absolute-threshold thermometer.
        common = (28.0 + ambient_shift
                  + 6.0 * math.sin(2 * math.pi * (h - 15.0) / 24.0)
                  + 18.0 * f * f)
        sigma1 = sigma / math.sqrt(2.0)   # per-sensor, so the pair difference is sigma
        t_hot = common + dt_true + rng.gauss(0.0, sigma1)
        sibs = [common + rng.gauss(0.0, sigma1) for _ in range(2)]
        meas.append(t_hot - median(sibs))
        abs_temps.append(t_hot)
        loads.append(f)
    _simulate.last_abs = abs_temps  # type: ignore[attr-defined]
    return meas, loads


def _rls_run(meas, loads, dt_s, tau_s, lam=0.9995):
    st = ThetaState(tau_s=tau_s)
    traj = []
    for m, f in zip(meas, loads):
        st = rls_update(st, m, f, dt_s, lam=lam)
        traj.append(st.theta)
    return st, traj


def _sd(xs) -> float:
    xs = [x for x in xs if x is not None and math.isfinite(x)]
    if len(xs) < 2:
        return float("nan")
    m = sum(xs) / len(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


if __name__ == "__main__":
    import math as _m

    print("=" * 78)
    print("theta.py self-test")
    print("=" * 78)

    DT = 60.0
    TAU = 1200.0
    SIG = SIGMA_TC_K
    THETA = 6.0
    DAYS = 14
    N = int(DAYS * 86400 / DT)

    def daily_load(k: int) -> float:
        """Realistic Turkish LV feeder shape: 0.25 at night, 0.90 at the peak."""
        h = (k * DT / 3600.0) % 24.0
        return 0.575 + 0.325 * _m.sin(2 * _m.pi * (h - 9.0) / 24.0)

    # ---------------------------------------------------------------- 1 ----
    print("\n[1] RLS versus pointwise deconvolution, same data, same noise")
    meas, loads = _simulate(THETA, TAU, DT, N, SIG, seed=1, f_of_k=daily_load)
    st, traj = _rls_run(meas, loads, DT, TAU)
    tail = traj[-int(3 * 86400 / DT):]                       # last 3 days
    rls_sd = _sd(tail)
    rls_mean = sum(tail) / len(tail)

    naive = []
    for k in range(1, N):
        v = naive_theta(meas[k], meas[k - 1], loads[k], DT, TAU)
        if v is not None and loads[k] >= 0.3:
            naive.append(v)
    naive_sd = _sd(naive)
    naive_mean = sum(naive) / len(naive)

    print(f"    true theta                       {THETA:8.3f} K")
    print(f"    RLS estimate                     {rls_mean:8.3f} K   "
          f"rel sd {100 * rls_sd / THETA:6.2f} %   (sd {rls_sd:.4f} K)")
    print(f"    pointwise deconvolution          {naive_mean:8.3f} K   "
          f"rel sd {100 * naive_sd / THETA:6.2f} %   (sd {naive_sd:.4f} K)")
    print(f"    measured noise advantage of RLS  {naive_sd / rls_sd:8.1f} x")
    print(f"    analytic deconvolution gain      {deconvolution_noise_gain(DT, TAU):8.2f} x"
          f"  -> per-sample sd {deconvolution_noise_gain(DT, TAU) * SIG:.2f} K"
          f" on a {THETA:.0f} K defect")
    assert abs(rls_mean - THETA) < 0.25 * THETA, "RLS estimate off"
    assert naive_sd > 10.0 * rls_sd, "RLS should be an order of magnitude quieter"

    # ---------------------------------------------------------------- 2 ----
    print("\n[2] load invariance - same defect, two very different load factors")
    for f_const in (0.30, 0.60, 0.90):
        m2, l2 = _simulate(THETA, TAU, DT, N, SIG, seed=7,
                           f_of_k=lambda k, c=f_const: c)
        s2, t2 = _rls_run(m2, l2, DT, TAU)
        err = 100.0 * (s2.theta - THETA) / THETA
        print(f"    f = {f_const:.2f}   measured excess {THETA * f_const ** 2:5.2f} K"
              f"   theta = {s2.theta:6.3f} K   error {err:+5.2f} %")
        assert abs(err) < 5.0

    # ---------------------------------------------------------------- 3 ----
    print("\n[3] ambient invariance - shift the whole compartment by +12 K")
    print("    absolute temperatures are simulated and then differenced, so the")
    print("    cancellation is exercised, not assumed")
    m3a, l3a = _simulate(THETA, TAU, DT, N, SIG, seed=1, f_of_k=daily_load,
                         ambient_shift=0.0)
    abs0 = list(_simulate.last_abs)  # type: ignore[attr-defined]
    s3a, _ = _rls_run(m3a, l3a, DT, TAU)
    m3, l3 = _simulate(THETA, TAU, DT, N, SIG, seed=1, f_of_k=daily_load,
                       ambient_shift=12.0)
    abs1 = list(_simulate.last_abs)  # type: ignore[attr-defined]
    s3, _ = _rls_run(m3, l3, DT, TAU)
    print(f"    mean absolute joint temperature {sum(abs0) / len(abs0):.2f} °C "
          f"-> {sum(abs1) / len(abs1):.2f} °C  "
          f"({sum(abs1) / len(abs1) - sum(abs0) / len(abs0):+.2f} K), "
          f"peak {max(abs1):.1f} °C")
    print(f"    theta at 28 °C base {s3a.theta:.4f} K   at 40 °C base "
          f"{s3.theta:.4f} K   delta {s3.theta - s3a.theta:+.6f} K")
    assert abs(s3.theta - s3a.theta) < 1e-9, "ambient must cancel exactly"

    # ---------------------------------------------------------------- 4 ----
    print("\n[4] tau identification and the cost of getting tau wrong")
    sub_m, sub_l = meas[:2880], loads[:2880]                 # two days
    got = identify_tau(sub_m, sub_l, DT)
    print(f"    true tau {TAU:.0f} s   grid search picks {got:.0f} s")
    base, _ = _fit_theta(sub_m, sub_l, DT, TAU)
    for factor in (0.25, 0.5, 1.0, 2.0, 4.0):
        th, sse = _fit_theta(sub_m, sub_l, DT, TAU * factor)
        print(f"    tau assumed {TAU * factor:7.0f} s ({factor:4.2f}x true) "
              f"-> theta {th:6.3f} K   bias vs true {100 * (th - THETA) / THETA:+5.2f} %")
    th_half, _ = _fit_theta(sub_m, sub_l, DT, TAU * 0.5)
    th_dbl, _ = _fit_theta(sub_m, sub_l, DT, TAU * 2.0)
    worst = max(abs(th_half - THETA), abs(th_dbl - THETA)) / THETA * 100.0
    print(f"    worst bias for a 100 % tau error: {worst:.2f} %  "
          f"-> a five-point grid is sufficient")
    assert worst < 6.0

    # ---------------------------------------------------------------- 5 ----
    print("\n[5] detectability floor  theta_min(f) = 3*sigma/f^2")
    print(f"    {'f':>6} {'TC pair 0.2 K':>16} {'IR pair 0.8 K':>16} {'visibility %':>14}")
    for f in (0.90, 0.85, 0.60, 0.40, 0.35, 0.20, 0.10):
        print(f"    {f:6.2f} {theta_min(SIGMA_TC_K, f):14.2f} K "
              f"{theta_min(SIGMA_IR_K, f):14.2f} K "
              f"{sensitivity_pct(THETA_ALARM_K, SIGMA_TC_K, f):13.0f} %")
    assert abs(theta_min(0.2, 0.85) - 0.830) < 0.005
    assert abs(theta_min(0.2, 0.60) - 1.667) < 0.005
    assert abs(theta_min(0.2, 0.40) - 3.750) < 0.005
    assert abs(theta_min(0.2, 0.20) - 15.00) < 0.01
    print(f"    SENSITIVITY_LOW below f = {SENSITIVITY_LOW_F:.4f} "
          f"(= sqrt(3*{SIGMA_TC_K}/{THETA_ALARM_K}))")

    # ---------------------------------------------------------------- 6 ----
    print("\n[6] excess resistance, always an interval")
    for name, iref, rlo, rhi in (
        ("400 A lug   (cable tail 2-4 K/W)", 400.0, R_TH_LUG_LO, R_TH_LUG_HI),
        ("400 A lug   (on the bar 0.24-0.38 K/W)", 400.0, R_TH_BUSBAR_LO, R_TH_BUSBAR_HI),
        ("2312 A incomer (on the bar)", assets.MAIN_BUSBAR_RATED_A, R_TH_BUSBAR_LO, R_TH_BUSBAR_HI),
    ):
        lo, mid, hi = excess_resistance_uohm(THETA, iref, rlo, rhi)
        print(f"    theta {THETA:.1f} K @ {name:<40} -> {lo:7.2f} .. {hi:7.2f} µΩ "
              f"(orta {mid:6.2f})")
    lo, mid, hi = excess_resistance_uohm(2.4, 400.0, R_TH_BUSBAR_LO, R_TH_BUSBAR_HI)
    print(f"    cross-check: the documented 8.0 W / 2.4 K case gives "
          f"{lo:.1f} .. {hi:.1f} µΩ; 50 µΩ at 400 A = {power_w(50.0, 400.0):.1f} W")
    assert lo < 50.0 < hi, "the 50 microohm reference case must fall inside the interval"

    # ---------------------------------------------------------------- 7 ----
    print("\n[7] sibling handling on the real asset model")
    group = assets.sibling_groups()["bottom:F06"]
    temps = {j.key: 41.0 for j in assets.monitored_joints()}
    hot = group[0].key
    temps[hot] = 47.5
    exc = sibling_excess(temps, hot)
    peers = [temps[j.key] for j in group if j.key != hot]
    print(f"    group bottom:F06 = {', '.join(j.key for j in group)}")
    print(f"    {hot} at {temps[hot]:.1f} °C, siblings {peers}")
    print(f"    excess {exc[0]:+.2f} K over sibling median {exc[1]:.2f} °C   "
          f"robust z {robust_z(temps[hot], peers + [temps[hot]]):+.1f}")
    assert exc is not None and abs(exc[0] - 6.5) < 1e-9

    print("    choice of reference, on a three-element peer set:")
    trio = {j.key: temps[j.key] for j in group}
    print(f"    {'joint':<16} {'T °C':>7} {'excl. self':>12} {'incl. self (used)':>19}")
    for j in group:
        others = [trio[o.key] for o in group if o.key != j.key]
        excl = trio[j.key] - median(others)
        incl = sibling_excess(temps, j.key)[0]
        print(f"    {j.key:<16} {trio[j.key]:7.1f} {excl:+12.2f} {incl:+19.2f}")
    print("    excluding self lets the defect move its own reference and smears")
    print("    one bad lug across all three phases; including it does not")
    healthy_incl = sibling_excess(temps, group[1].key)[0]
    assert abs(healthy_incl) < 1e-9

    n_kg = sibling_excess(temps, "C01-N-PABUC")
    print(f"    neutral group has {len(assets.sibling_groups()['bottom:N'])} members "
          f"and is judged by rule H3, not by the phase peer test")
    assert sibling_excess(temps, "C01-L1-BARA") is None, "busbar joints are not monitored"

    # ---------------------------------------------------------------- 8 ----
    print("\n[8] restart safety - a restored estimator must not look cold")
    print("    ``train_n`` in joint_state belongs to the CUSUM, so a joint that")
    print("    restarts inside its first 14 days has train_n = 0 while the RLS")
    print("    has been running for a week.  If from_row() believed that column,")
    print("    every restart would re-seed theta from a single lagged reading.")
    row = {"theta": 6.40, "theta_p": 0.21, "dt_excess": 2.00, "tau_s": 1200.0,
           "resid_ewma": 0.03, "train_n": 0}
    restored = ThetaState.from_row(row)
    naive_state = ThetaState(theta=6.40, p=0.21, dt_excess=2.00, n=0)
    MEAS, F = 2.00, 0.40
    good = rls_update(restored, MEAS, F, 60.0)
    bad = rls_update(naive_state, MEAS, F, 60.0)
    print(f"    persisted row: theta 6.40 K, p 0.21, dt_excess 2.00 K, train_n 0")
    print(f"    from_row() infers n = {restored.n} from the covariance being "
          f"{row['theta_p']}, not 100")
    print(f"    next sample (excess {MEAS:.2f} K at f = {F:.2f}):")
    print(f"      restored correctly -> theta {good.theta:6.3f} K   (kept estimating)")
    print(f"      believing train_n  -> theta {bad.theta:6.3f} K   "
          f"(re-seeded to {MEAS:.1f}/{F:.1f}^2 - the estimator was thrown away)")
    assert restored.n > 0
    assert abs(good.theta - 6.40) < 0.2
    assert bad.theta > 10.0

    print("\nOK - theta.py self-test passed")
