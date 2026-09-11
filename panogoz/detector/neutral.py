"""Rule H3 - the neutral bar, which nothing else in the panel watches.

Why the neutral is the blind spot
---------------------------------
Go through a TEDAS 1600 kVA panel conductor by conductor.  Every phase has a
DSYA fuse, a busbar, and - on the incomer - a 2500/5 CT feeding an analyser.
The neutral has **no fuse, no relay, no ammeter and no protection of any kind**.
It is a bar of the same 2x(100x10) mm2 tinned copper as the phases, carrying a
current nobody looks at, through bolted joints nobody torques on a schedule.
The Entes MPR-53CS does measure I_N (register 12), but no device in the panel
does anything with it.

That is a genuine gap, and it is where a large share of real LV distribution
failures live: Turkish secondary feeders are heavily single-phase loaded, 20-40 %
phase unbalance is routine, and the loads are increasingly non-linear.

Two completely different faults, one symptom
--------------------------------------------
A hot neutral bar has two causes that look identical on a thermal image and
require opposite work orders:

1. **Harmonic loading.**  Triplen harmonics (3rd, 9th, 15th) are zero sequence:
   they are in phase in all three conductors and therefore ADD arithmetically in
   the neutral instead of cancelling.  ``I_N,harmonic = 3 * h3 * I_1``.  With
   30 % third harmonic the neutral carries 90 % of a phase current even with
   perfectly balanced loads.  The bar is hot because it is genuinely loaded.
   The work order is *filter, rebalance or derate*.  Retorquing the joints
   achieves nothing.

2. **A bad neutral joint.**  Excess contact resistance at a bolted neutral
   connection.  The bar is hot because the joint is bad.  The work order is
   *retorque*.  Installing a filter achieves nothing.

The discriminator
-----------------
Normalise the neutral's temperature rise by its own current::

    K_N = dT_N / I_N^2      [K/A^2]

``K_N`` is the neutral's thermal transfer coefficient.  It does not care how
much current is flowing - that is the whole point of dividing by ``I^2`` - so:

* **K_N normal, dT_N high**  ->  the bar is hot because there is a lot of
  current in it.  *HARMONIC LOADING.*
* **K_N rising against its own trend**  ->  the same current is producing more
  heat than it used to.  *BAD NEUTRAL JOINT.*

The comparison is against the neutral's OWN history, not against the phases,
because the neutral has no valid sibling: it carries a different current, so
the phase-peer test in :mod:`panogoz.detector.theta` does not apply to it.
That is why :func:`panogoz.contracts.assets.Joint.sibling_group` puts all ten
neutrals in ``bottom:N`` and this module judges them.

Decomposition
-------------
The fundamental part of the neutral current is the zero-sequence sum of the
three phase phasors, which the MPR-53CS gives us directly (currents at
registers 6/8/10, current angles at 66/68/70, angle multiplier 1 = degrees)::

    I_N,fund = |I_L1 + I_L2 + I_L3| = 3*|I_0|

and everything the neutral carries beyond that is harmonic::

    E = sqrt( max(0, I_N,meas^2 - I_N,fund^2) )

which is exact for orthogonal frequency components.  From E::

    h3 = E / (3 * I_phase_mean)

This is attributed entirely to the third harmonic, which is an over-estimate of
h3 whenever the 9th and 15th are present.  We say so rather than pretending the
split is resolvable: the MPR-53CS reports total current THD (registers 78/80/82)
but not the individual harmonic orders, so h3 from this route is an upper bound
on the third and a correct measure of the total triplen content.

One more instrument caveat that has to be respected: the MPR-53CS THD registers
saturate at 99.9 % (range 0-999 x 0.1), and light-load current THD routinely
exceeds that.  Every current-THD rule must therefore be gated on
``I > 10 % of CT rating``, and :func:`rule_h3` refuses to reach a verdict below
that gate rather than reporting a saturated number as if it were a measurement.
"""

from __future__ import annotations

import math

DEG = math.pi / 180.0

#: Gate below which neutral diagnosis is refused.  Two independent reasons:
#: the MPR-53CS current THD registers saturate at light load, and K_N = dT/I^2
#: has a 1/I^2 error amplification that makes it meaningless at low current.
MIN_I_N_A = 5.0
MIN_I_PHASE_FRACTION = 0.10      #: of CT rating, per the THD saturation note

#: K_N ratio against its own baseline that indicates a degrading joint.
K_N_RATIO_BAD = 1.5
#: Temperature rise below which there is nothing to diagnose either way.
DT_N_MIN_K = 2.0
#: Temperature rise that counts as "hot" for the harmonic-loading verdict.
DT_N_HOT_K = 5.0
#: Triplen content that makes the harmonic explanation credible.
H3_NOTABLE_PCT = 15.0


# --------------------------------------------------------------------------
# Decomposition
# --------------------------------------------------------------------------

def neutral_fundamental(i_l1: float, i_l2: float, i_l3: float,
                        ang_l1: float, ang_l2: float, ang_l3: float) -> float:
    """``3*|I_0|`` - the fundamental (unbalance) part of the neutral current, A.

    Angles are in degrees, as the MPR-53CS reports them (registers 66/68/70,
    multiplier 1).  A balanced three-phase set at 0 / -120 / +120 sums to zero,
    so this returns 0 for a balanced load no matter how large the phase
    currents are.
    """
    re = (i_l1 * math.cos(ang_l1 * DEG) + i_l2 * math.cos(ang_l2 * DEG)
          + i_l3 * math.cos(ang_l3 * DEG))
    im = (i_l1 * math.sin(ang_l1 * DEG) + i_l2 * math.sin(ang_l2 * DEG)
          + i_l3 * math.sin(ang_l3 * DEG))
    return math.hypot(re, im)


def neutral_decompose(i_l1: float, i_l2: float, i_l3: float,
                      ang1: float, ang2: float, ang3: float,
                      i_n_meas: float) -> dict:
    """Split the measured neutral current into unbalance and harmonic parts.

    Returns ``i_n_meas_a``, ``i_n_fund_a``, ``harmonic_excess_a``,
    ``i_phase_mean_a``, ``h3_pct``, ``unbalance_pct`` and ``harmonic_share``.

    ``harmonic_excess_a`` uses ``sqrt(I_N^2 - I_N,fund^2)`` and is clamped at
    zero.  A measured I_N slightly BELOW the computed fundamental is not an
    error to hide: it means the phasor sum and the RMS reading disagree, which
    happens with CT phase error and rounding, so the excess is simply zero and
    ``consistent`` is set False so the caller can see it happened.
    """
    fund = neutral_fundamental(i_l1, i_l2, i_l3, ang1, ang2, ang3)
    meas = max(0.0, float(i_n_meas))
    excess2 = meas * meas - fund * fund
    excess = math.sqrt(excess2) if excess2 > 0.0 else 0.0
    phases = [abs(i_l1), abs(i_l2), abs(i_l3)]
    i_mean = sum(phases) / 3.0
    i_max, i_min = max(phases), min(phases)
    unbalance = 100.0 * (i_max - i_min) / i_mean if i_mean > 0 else 0.0
    return {
        "i_n_meas_a": meas,
        "i_n_fund_a": fund,
        "harmonic_excess_a": excess,
        "i_phase_mean_a": i_mean,
        "h3_pct": h3_estimate(excess, i_mean),
        "unbalance_pct": unbalance,
        "harmonic_share": (excess / meas) if meas > 0 else 0.0,
        "consistent": excess2 >= -1e-6 * max(1.0, meas * meas),
    }


def h3_estimate(i_n_harmonic: float, i_phase_mean: float) -> float:
    """Triplen content as a percentage of the fundamental phase current.

    Inverts ``I_N,harmonic = 3 * h3 * I_1``.  Attributed entirely to the third
    harmonic, so it is an UPPER bound on h3 when the 9th and 15th are also
    present, and a correct measure of the total zero-sequence harmonic content.
    The MPR-53CS does not report individual harmonic orders, so this is the
    honest limit of what the installed instrument can say.
    """
    if i_phase_mean <= 0.0:
        return 0.0
    return 100.0 * i_n_harmonic / (3.0 * i_phase_mean)


def k_n(dt_n: float, i_n: float) -> float:
    """``dT_N / I_N^2`` in K/A^2.  Zero when there is no current to normalise by."""
    if i_n <= 0.0:
        return 0.0
    return float(dt_n) / (float(i_n) * float(i_n))


# --------------------------------------------------------------------------
# The rule
# --------------------------------------------------------------------------

def rule_h3(k_n: float, k_n_baseline: float, dt_n: float, i_n: float,
            i_phase: float, *, i_n_fund: float = 0.0,
            ct_rating_a: float | None = None) -> dict:
    """Decide which of the two neutral faults this is.

    Parameters
    ----------
    k_n, k_n_baseline
        The neutral's thermal coefficient now, and its own established value.
        Compared as a ratio, never as a difference: K_N carries an ``I^-2`` and
        its absolute magnitude depends on the bar geometry.
    dt_n
        Neutral bar temperature rise over the compartment air, K.
    i_n, i_phase
        Measured neutral current and mean phase current, A.
    i_n_fund
        ``3*|I_0|`` from :func:`neutral_fundamental`.  Keyword-only with a
        default of 0.0, which is the conservative fallback "assume the phases
        are balanced, so all of I_N is harmonic" - conservative because it
        maximises the apparent harmonic content and therefore biases towards the
        cheaper work order.  The engine always passes the real value.
    ct_rating_a
        Used only for the THD-saturation gate.

    Returns a dict with ``verdict`` in ``{"harmonik_yuk",
    "kotu_notr_baglanti", "normal"}`` plus ``reason_tr``, ``action_tr``,
    ``h3_pct`` and ``harmonic_excess_a``.
    """
    excess2 = float(i_n) ** 2 - float(i_n_fund) ** 2
    excess = math.sqrt(excess2) if excess2 > 0.0 else 0.0
    h3 = h3_estimate(excess, float(i_phase))
    ratio = (k_n / k_n_baseline) if k_n_baseline and k_n_baseline > 0.0 else 0.0

    out = {
        "verdict": "normal",
        "reason_tr": "",
        "action_tr": "",
        "h3_pct": h3,
        "harmonic_excess_a": excess,
        "i_n_fund_a": float(i_n_fund),
        "k_n": float(k_n),
        "k_n_baseline": float(k_n_baseline),
        "k_n_ratio": ratio,
        "dt_n_k": float(dt_n),
        "i_n_a": float(i_n),
        "gated": False,
    }

    # ---- gates ----------------------------------------------------------
    gate_a = ct_rating_a * MIN_I_PHASE_FRACTION if ct_rating_a else 0.0
    if i_n < MIN_I_N_A or (gate_a and i_phase < gate_a):
        out["gated"] = True
        out["reason_tr"] = (
            f"Nötr akımı {i_n:.0f} A / faz akımı {i_phase:.0f} A. Bu seviyede "
            f"MPR-53CS akım THD kayıtları doyuma gidiyor ve K_N = ΔT/I² hatası "
            f"1/I² ile büyüyor; nötr teşhisi yapılmıyor."
        )
        out["action_tr"] = "Yük arttığında yeniden değerlendirilir."
        return out

    if dt_n < DT_N_MIN_K and ratio < K_N_RATIO_BAD:
        out["reason_tr"] = (
            f"Nötr barası {dt_n:.1f} K yükseldi, K_N kendi geçmişiyle uyumlu "
            f"(x{ratio:.2f}). Üçlü harmonik içeriği %{h3:.0f}."
        )
        out["action_tr"] = "Aksiyon yok, izlemeye devam."
        return out

    # ---- bad joint first: it is the one that gets worse on its own -------
    if ratio >= K_N_RATIO_BAD and dt_n >= DT_N_MIN_K:
        out["verdict"] = "kotu_notr_baglanti"
        out["reason_tr"] = (
            f"Nötr barası {dt_n:.1f} K yükseldi ve K_N = ΔT/I² kendi taban "
            f"değerinin {ratio:.2f} katına çıktı ({k_n:.3e} / {k_n_baseline:.3e} "
            f"K/A²). Aynı akım eskisinden daha fazla ısı üretiyor: bu bir yük "
            f"sorunu değil, temas direnci sorunudur. Üçlü harmonik içeriği "
            f"%{h3:.0f} ve bu tek başına ısınmayı açıklamıyor."
        )
        out["action_tr"] = (
            "Nötr bara civatalı bağlantılarını tork anahtarı ile yeniden sıkın, "
            "temas yüzeylerini ve rondelaları kontrol edin. Nötr barasında sigorta, "
            "röle veya ampermetre yoktur; bu bağlantıyı izleyen başka bir cihaz "
            "bulunmuyor."
        )
        return out

    # ---- otherwise: is it simply carrying a lot of triplen current? -----
    if dt_n >= DT_N_HOT_K:
        out["verdict"] = "harmonik_yuk"
        out["reason_tr"] = (
            f"Nötr barası {dt_n:.1f} K yükseldi ancak K_N = ΔT/I² kendi taban "
            f"değeriyle uyumlu (x{ratio:.2f}). Bağlantı bozulmamış; bara "
            f"gerçekten yüklü. Ölçülen nötr akımı {i_n:.0f} A, bunun "
            f"{out['harmonic_excess_a']:.0f} A'i sıfır bileşen harmoniği "
            f"(üçlü harmonik ≈ %{h3:.0f}). Üçlü harmonikler üç iletkende aynı "
            f"fazdadır ve nötrde aritmetik toplanır: I_N = 3·h3·I₁."
        )
        out["action_tr"] = (
            "Harmonik ölçümü yapın; yük dengeleme, harmonik filtre veya nötr "
            "kesitinin yeniden değerlendirilmesi (derating) planlayın. Civata "
            "sıkmak bu sorunu çözmez."
        )
        return out

    out["reason_tr"] = (
        f"Nötr barası {dt_n:.1f} K, K_N x{ratio:.2f}, üçlü harmonik %{h3:.0f}. "
        f"Eşiklerin altında."
    )
    out["action_tr"] = "Aksiyon yok, izlemeye devam."
    return out


# --------------------------------------------------------------------------
# Self-test
# --------------------------------------------------------------------------

if __name__ == "__main__":
    from panogoz.contracts import assets

    print("=" * 78)
    print("neutral.py self-test")
    print("=" * 78)

    CT = assets.MAIN_CT_PRIMARY_A          # 2500 A
    print(f"\n    ana ölçü akım trafosu {assets.MAIN_CT_PRIMARY_A:.0f}/"
          f"{assets.MAIN_CT_SECONDARY_A:.0f} (oran {assets.MAIN_CT_RATIO:.0f})")
    print(f"    nötr kesiti = faz kesiti = "
          f"{assets.BUSBAR_BARS_PER_PHASE}x({assets.BUSBAR_BAR_W_MM:.0f}x"
          f"{assets.BUSBAR_BAR_T_MM:.0f}) mm² kalaylı bakır")
    print(f"    nötr barasında sigorta yok, röle yok, ampermetre yok")

    # ------------------------------------------------------------------ 1 --
    print("\n[1] fundamental decomposition")
    cases = [
        ("balanced 800 A, no harmonics", 800, 800, 800, 0, -120, 120, 0.0),
        ("balanced 800 A, 30 % triplen", 800, 800, 800, 0, -120, 120, 720.0),
        ("Turkish reality: 40 % unbalance", 900, 700, 500, 0, -120, 120, 0.0),
        ("unbalanced AND harmonic", 900, 700, 500, 0, -120, 120, 400.0),
    ]
    print(f"    {'case':<34} {'I_N ölç':>9} {'I_N tem':>9} {'harm':>8} {'h3 %':>7} "
          f"{'dengesiz %':>11}")
    for name, a, b, c, p1, p2, p3, extra_harm in cases:
        fund = neutral_fundamental(a, b, c, p1, p2, p3)
        meas = math.sqrt(fund * fund + extra_harm * extra_harm)
        d = neutral_decompose(a, b, c, p1, p2, p3, meas)
        print(f"    {name:<34} {d['i_n_meas_a']:9.1f} {d['i_n_fund_a']:9.1f} "
              f"{d['harmonic_excess_a']:8.1f} {d['h3_pct']:7.1f} "
              f"{d['unbalance_pct']:11.1f}")
    bal = neutral_decompose(800, 800, 800, 0, -120, 120, 0.0)
    assert bal["i_n_fund_a"] < 1e-9, "a balanced set must sum to zero"
    h30 = neutral_decompose(800, 800, 800, 0, -120, 120, 720.0)
    assert abs(h30["h3_pct"] - 30.0) < 0.01, "30 % triplen must read back as 30 %"
    print(f"    check: 30 % triplen on a balanced 800 A load puts "
          f"{h30['i_n_meas_a']:.0f} A in the neutral = "
          f"{100 * h30['i_n_meas_a'] / 800:.0f} % of a phase current,")
    print(f"    with perfectly balanced loads.  I_N = 3·h3·I₁.")

    unb = neutral_decompose(900, 700, 500, 0, -120, 120, 346.4)
    print(f"    check: 900/700/500 A unbalance alone gives "
          f"I_N,fund = {unb['i_n_fund_a']:.1f} A")

    # ------------------------------------------------------------------ 2 --
    print("\n[2] rule H3 - the discriminator")
    # A healthy neutral joint: dT = K_N * I_N^2.  Pick a plausible K_N so that
    # 350 A gives 4 K:  K_N = 4 / 350^2 = 3.27e-5 K/A^2.
    K_BASE = 4.0 / (350.0 ** 2)
    print(f"    taban K_N = {K_BASE:.3e} K/A² (sağlam bağlantı: 350 A -> 4.0 K)")

    print("\n    --- CASE A: harmonic loading -----------------------------------")
    # Balanced 800 A phases, 30 % triplen -> 720 A neutral, SAME joint quality.
    i_n_a = 720.0
    dt_a = K_BASE * i_n_a ** 2
    fund_a = neutral_fundamental(800, 800, 800, 0, -120, 120)
    ra = rule_h3(k_n(dt_a, i_n_a), K_BASE, dt_a, i_n_a, 800.0,
                 i_n_fund=fund_a, ct_rating_a=CT)
    print(f"    I_N {i_n_a:.0f} A (temel {fund_a:.0f} A), ΔT_N {dt_a:.1f} K, "
          f"K_N x{ra['k_n_ratio']:.2f}")
    print(f"    verdict : {ra['verdict']}")
    print(f"    gerekçe : {ra['reason_tr']}")
    print(f"    aksiyon : {ra['action_tr']}")
    assert ra["verdict"] == "harmonik_yuk", ra["verdict"]

    print("\n    --- CASE B: bad neutral joint ----------------------------------")
    # Same modest 350 A neutral from unbalance only, but the joint degraded 2.2x.
    fund_b = neutral_fundamental(900, 700, 500, 0, -120, 120)
    i_n_b = fund_b
    dt_b = 2.2 * K_BASE * i_n_b ** 2
    rb = rule_h3(k_n(dt_b, i_n_b), K_BASE, dt_b, i_n_b, 700.0,
                 i_n_fund=fund_b, ct_rating_a=CT)
    print(f"    I_N {i_n_b:.0f} A (temel {fund_b:.0f} A, harmonik yok), "
          f"ΔT_N {dt_b:.1f} K, K_N x{rb['k_n_ratio']:.2f}")
    print(f"    verdict : {rb['verdict']}")
    print(f"    gerekçe : {rb['reason_tr']}")
    print(f"    aksiyon : {rb['action_tr']}")
    assert rb["verdict"] == "kotu_notr_baglanti", rb["verdict"]

    print("\n    --- CASE C: both at once ---------------------------------------")
    i_n_c = 720.0
    dt_c = 1.8 * K_BASE * i_n_c ** 2
    rc = rule_h3(k_n(dt_c, i_n_c), K_BASE, dt_c, i_n_c, 800.0,
                 i_n_fund=fund_a, ct_rating_a=CT)
    print(f"    I_N {i_n_c:.0f} A, ΔT_N {dt_c:.1f} K, K_N x{rc['k_n_ratio']:.2f}, "
          f"h3 %{rc['h3_pct']:.0f}")
    print(f"    verdict : {rc['verdict']}  (the joint wins: it is the one that")
    print(f"              gets worse on its own and the one that can start a fire)")
    assert rc["verdict"] == "kotu_notr_baglanti"

    print("\n    --- CASE D: healthy ---------------------------------------------")
    i_n_d = 200.0
    dt_d = K_BASE * i_n_d ** 2
    rd = rule_h3(k_n(dt_d, i_n_d), K_BASE, dt_d, i_n_d, 700.0,
                 i_n_fund=180.0, ct_rating_a=CT)
    print(f"    I_N {i_n_d:.0f} A, ΔT_N {dt_d:.2f} K, K_N x{rd['k_n_ratio']:.2f} "
          f"-> {rd['verdict']}")
    assert rd["verdict"] == "normal"

    print("\n    --- CASE E: light load, diagnosis refused ------------------------")
    re_ = rule_h3(0.0, K_BASE, 0.4, 3.0, 120.0, i_n_fund=3.0, ct_rating_a=CT)
    print(f"    verdict : {re_['verdict']}  gated {re_['gated']}")
    print(f"    gerekçe : {re_['reason_tr']}")
    assert re_["gated"] is True

    # ------------------------------------------------------------------ 3 --
    print("\n[3] the separation, as a table - same hot bar, different work order")
    print(f"    {'senaryo':<26} {'I_N A':>7} {'ΔT_N K':>8} {'K_N x':>7} {'h3 %':>6}  "
          f"{'karar':<20} iş emri")
    rows = [
        ("harmonik yük", ra, i_n_a, dt_a, "filtre / dengeleme / derating"),
        ("kötü nötr bağlantısı", rb, i_n_b, dt_b, "tork ile yeniden sıkma"),
        ("her ikisi", rc, i_n_c, dt_c, "tork ile yeniden sıkma"),
        ("sağlam", rd, i_n_d, dt_d, "yok"),
    ]
    for name, r, i_n_v, dt_v, order in rows:
        print(f"    {name:<26} {i_n_v:7.0f} {dt_v:8.1f} {r['k_n_ratio']:7.2f} "
              f"{r['h3_pct']:6.0f}  {r['verdict']:<20} {order}")

    # ------------------------------------------------------------------ 4 --
    print("\n[4] K_N really is load-independent for a healthy joint")
    print(f"    {'I_N A':>8} {'ΔT_N K':>9} {'K_N K/A²':>12}")
    for i in (150.0, 350.0, 600.0, 900.0):
        dt = K_BASE * i * i
        print(f"    {i:8.0f} {dt:9.2f} {k_n(dt, i):12.3e}")
    vals = [k_n(K_BASE * i * i, i) for i in (150.0, 350.0, 600.0, 900.0)]
    assert max(vals) - min(vals) < 1e-12
    print(f"    identical to 1e-12 across a 6x current range - which is exactly")
    print(f"    why a change in K_N can only be the joint, never the load")

    print("\nOK - neutral.py self-test passed")
