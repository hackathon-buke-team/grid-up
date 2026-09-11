"""Condensation risk inside the cable compartment.

The problem, stated properly
----------------------------
Water does not condense out of the air.  It condenses on a SURFACE whose
temperature has fallen below the dew point of the air touching it.  Almost every
"dew point alarm" shipped in switchgear compares the dew point against the
measured AIR temperature, which is the one temperature that can never
condense - and it therefore alarms late, or never.

The TEDAS panel makes this worse in a very specific way.  Madde 2.2.8.6 Not:2
leaves the panel bottom **fully open** onto the cable trench, and the trench is
the wettest, coldest volume in the substation.  On a spring morning the air in
the compartment warms with the building while the steel gland plate, the lug
bolts and the incoming cable armour lag hours behind, sitting at trench
temperature.  Warm humid air meets cold metal and the surface wets.  Nothing in
the panel measures that surface.

So we estimate it.  The coldest surface is modelled as a first-order lag on the
compartment air::

    T_wall[k] = a*T_wall[k-1] + (1-a)*T_air[k],   a = exp(-dt/tau)

with ``tau ~ 90 minutes``.  That constant is not a guess pulled from nowhere:
it is the lumped time constant of a few kilograms of steel and copper with
natural convection on one side, and it is the number that reproduces the
morning lag actually seen in cable trenches.  It is a model, we say it is a
model, and the margin it produces is reported as an estimate.

Why margin, not a boolean
-------------------------
``margin = T_wall - T_dew``.  Positive is dry, zero is the onset of wetting,
negative means the surface is already wet.  A margin has a gradient, so an
operator can see the risk building over a week of nights; a boolean only tells
them after it is too late to plan anything.

Why this matters electrically
-----------------------------
At 400 V a wet surface does not flash over.  What it does is start **surface
tracking**: the moisture film carries leakage current, dries into carbonised
paths, and those paths grow.  That is a months-to-years process ending in a
phase-to-earth fault inside a panel with no LV incoming breaker, where clearing
means the MV side and a whole secondary substation goes dark.  So condensation
is not itself an emergency; it is a leading indicator, and the only way to
confirm it is doing damage is to see the RF channel respond.  Hence the
severity ladder: on its own, condensation is IZLE or UYARI.  Combined with a
rising PD Qmax it becomes KRITIK, because now two independent physical channels
agree.

Formula
-------
Magnus-Tetens with the Alduchov-Eskridge (1996) coefficients::

    a = 17.62,  b = 243.12 C
    gamma = ln(RH/100) + a*T/(b+T)
    Td    = b*gamma / (a - gamma)

Valid -45..+60 C with a maximum error of 0.35 C, which comfortably spans the
TEDAS Tablo 1 indoor service range (-5 to +40 C).  The older Magnus constants
(17.27 / 237.7) are about 0.4 C worse near freezing; at a 2 K alarm margin that
is 20 % of the decision, so the choice of coefficients is not cosmetic.
"""

from __future__ import annotations

import math

#: Alduchov-Eskridge (1996) coefficients.
MAGNUS_A = 17.62
MAGNUS_B = 243.12
VALID_LO_C = -45.0
VALID_HI_C = 60.0
ACCURACY_C = 0.35

#: Wall/surface thermal lag.  90 minutes: a few kg of steel and copper with
#: natural convection, which is what the gland plate and the lug bolts are.
WALL_TAU_S = 5400.0

#: Severity ladder thresholds.
MARGIN_WATCH_K = 2.0          #: within 2 K of the dew point
WATCH_MINUTES = 30.0
WARN_MINUTES = 60.0
PD_CONFIRM_DB = 6.0           #: Qmax rise over 48 h that confirms tracking

SEVERITY_TR = {
    "BILGI": "Yoğuşma riski yok",
    "IZLE": "Yüzey çiy noktasına yaklaştı",
    "UYARI": "Yüzeyde yoğuşma var",
    "KRITIK": "Yoğuşma + RF artışı: yüzey kaçağı doğrulandı",
}

REASON_TR = {
    "BILGI": "Tahmini yüzey sıcaklığı çiy noktasının güvenli üzerinde.",
    "IZLE": (
        "Tahmini en soğuk yüzey {margin:.1f} K içinde çiy noktasına yaklaştı ve "
        "{minutes:.0f} dakikadır bu seviyede. Pano tabanı kablo kanalına açıktır "
        "(Madde 2.2.8.6 Not:2)."
    ),
    "UYARI": (
        "Tahmini en soğuk yüzey {minutes:.0f} dakikadır çiy noktasının altında "
        "({margin:.1f} K). Yüzeyde nem filmi bekleniyor."
    ),
    "KRITIK": (
        "Yoğuşma payı {margin:.1f} K ve son 48 saatte RF tepe genliği "
        "{pd:.1f} dB arttı. İki bağımsız kanal aynı şeyi söylüyor: yüzey kaçağı "
        "başlamış durumda."
    ),
}

ACTION_TR = {
    "BILGI": "Aksiyon yok.",
    "IZLE": "Kablo kanalı sızdırmazlığını ve varsa kabin ısıtıcısını kontrol edin.",
    "UYARI": (
        "Kablo kanalı drenajını ve kabin ısıtıcı/termostat devresini kontrol edin; "
        "pabuç bölmesinde nem izi arayın."
    ),
    "KRITIK": (
        "Planlı kesintide pabuç bölmesini temizleyip kurutun, yüzey kaçağı izlerini "
        "ve yalıtım bariyerlerini inceleyin. AG'de tek başına ekip yönlendirmez, "
        "ısıl bulguyla birlikte değerlendirilir."
    ),
}


# --------------------------------------------------------------------------
# Psychrometrics
# --------------------------------------------------------------------------

def dewpoint_c(t_c: float, rh_pct: float) -> float:
    """Dew point in Celsius from dry-bulb temperature and relative humidity.

    Magnus-Tetens with Alduchov-Eskridge coefficients, +-0.35 C over
    -45..+60 C.  Reference values the self-test checks:
    20 C / 50 % -> 9.26 C, and 10 C / 90 % -> 8.43 C.

    RH is clamped to (0.01, 100] rather than allowed to produce ``log(0)``: a
    sensor reporting 0 % is broken, and the honest response is to return an
    absurdly low dew point that the margin logic will treat as "no risk", not
    to raise ``ValueError`` inside a detector loop.
    """
    rh = min(max(float(rh_pct), 0.01), 100.0)
    t = float(t_c)
    gamma = math.log(rh / 100.0) + MAGNUS_A * t / (MAGNUS_B + t)
    return MAGNUS_B * gamma / (MAGNUS_A - gamma)


def rh_from_dewpoint(t_c: float, td_c: float) -> float:
    """Inverse of :func:`dewpoint_c`; used only to check the implementation."""
    t, td = float(t_c), float(td_c)
    gamma = MAGNUS_A * td / (MAGNUS_B + td)
    return 100.0 * math.exp(gamma - MAGNUS_A * t / (MAGNUS_B + t))


def in_valid_range(t_c: float) -> bool:
    return VALID_LO_C <= t_c <= VALID_HI_C


# --------------------------------------------------------------------------
# Surface temperature model
# --------------------------------------------------------------------------

def wall_temp(prev_wall_c: float | None, ambient_c: float, dt_s: float,
              tau_s: float = WALL_TAU_S) -> float:
    """First-order lag estimate of the coldest surface in the compartment.

    ``prev_wall_c is None`` means we are starting cold: return the ambient
    rather than inventing a lag we have no state for.  That is deliberately
    optimistic for one sample and honest about it - the estimate converges
    within about 3 tau (4.5 hours), and the panel's status carries no
    condensation claim before then.

    A gap in the data (``dt_s`` much larger than tau) collapses ``a`` towards
    zero and the estimate simply re-anchors on the ambient, which is the correct
    behaviour: after a six-hour outage we genuinely do not know the surface
    history and must not pretend we do.
    """
    if prev_wall_c is None or not math.isfinite(prev_wall_c):
        return float(ambient_c)
    if dt_s <= 0.0:
        return float(prev_wall_c)
    a = math.exp(-float(dt_s) / max(tau_s, 1.0))
    return a * float(prev_wall_c) + (1.0 - a) * float(ambient_c)


def condensation_margin(wall_c: float, dew_c: float) -> float:
    """Kelvin of headroom on the coldest surface.  Negative means wet."""
    return float(wall_c) - float(dew_c)


# --------------------------------------------------------------------------
# Severity
# --------------------------------------------------------------------------

def condensation_severity(margin_k: float, minutes_below: float,
                          pd_trend_db: float) -> str:
    """Severity for the moisture failure mode.  One of BILGI/IZLE/UYARI/KRITIK.

    The ladder, in the order it is evaluated:

    * ``margin < 2 K`` and PD Qmax up by >= 6 dB in 48 h -> **KRITIK**.
      Two independent physical channels agreeing is what turns a modelled
      surface temperature into a confirmed surface-tracking finding.  6 dB is a
      factor of two in amplitude, which is well outside the AD8318 log
      detector's drift and outside the day-to-day variation of a healthy panel.
    * ``margin < 0`` sustained 60 minutes -> **UYARI**.  The surface is wet.
    * ``margin < 2 K`` sustained 30 minutes -> **IZLE**.  Getting close.
    * otherwise **BILGI**.

    ``minutes_below`` is the dwell time in the CURRENT condition, supplied by
    the caller, because a five-minute dip as the morning sun hits the substation
    roof is not a condensation event and a detector that alarms on it will be
    switched off by August.

    Note this never returns ACIL.  Condensation at 400 V is a months-to-years
    degradation mechanism, not an emergency, and claiming otherwise would be the
    kind of overreach that destroys trust in every other alarm the system sends.
    """
    m = float(margin_k)
    mins = float(minutes_below)
    pd = float(pd_trend_db)

    if m < MARGIN_WATCH_K and pd >= PD_CONFIRM_DB:
        return "KRITIK"
    if m < 0.0 and mins >= WARN_MINUTES:
        return "UYARI"
    if m < MARGIN_WATCH_K and mins >= WATCH_MINUTES:
        return "IZLE"
    return "BILGI"


def condensation_report(margin_k: float, minutes_below: float,
                        pd_trend_db: float) -> dict:
    """Severity plus the Turkish reason and action the operator reads."""
    sev = condensation_severity(margin_k, minutes_below, pd_trend_db)
    return {
        "severity": sev,
        "title_tr": SEVERITY_TR[sev],
        "reason_tr": REASON_TR[sev].format(margin=margin_k, minutes=minutes_below,
                                           pd=pd_trend_db),
        "action_tr": ACTION_TR[sev],
        "margin_k": margin_k,
        "minutes_below": minutes_below,
        "pd_trend_db": pd_trend_db,
    }


# --------------------------------------------------------------------------
# Self-test
# --------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 78)
    print("dewpoint.py self-test")
    print("=" * 78)

    # ------------------------------------------------------------------ 1 --
    print("\n[1] reference values")
    checks = [
        (20.0, 50.0, 9.26),
        (10.0, 90.0, 8.43),
    ]
    for t, rh, expect in checks:
        got = dewpoint_c(t, rh)
        print(f"    T = {t:5.1f} °C, RH = {rh:5.1f} %  ->  Td = {got:7.4f} °C   "
              f"(reference {expect:.2f} °C, delta {got - expect:+.4f})")
        assert abs(got - expect) < 0.005, f"dewpoint {got} != {expect}"

    print("\n    table across the TEDAS Tablo 1 indoor service range:")
    print(f"    {'T °C':>7}", end="")
    for rh in (30, 50, 70, 80, 90, 95):
        print(f"{'RH ' + str(rh) + '%':>10}", end="")
    print()
    for t in (-5.0, 0.0, 10.0, 20.0, 25.0, 30.0, 35.0, 40.0):
        print(f"    {t:7.1f}", end="")
        for rh in (30, 50, 70, 80, 90, 95):
            print(f"{dewpoint_c(t, rh):10.2f}", end="")
        print()
    print(f"    TEDAŞ Tablo 1 dahili: 40 °C'de %50 bağıl nem -> çiy noktası "
          f"{dewpoint_c(40.0, 50.0):.2f} °C")

    # ------------------------------------------------------------------ 2 --
    print("\n[2] round trip through the inverse")
    worst = 0.0
    for t in range(-40, 60, 7):
        for rh in (5, 20, 40, 60, 80, 99):
            td = dewpoint_c(t, rh)
            back = rh_from_dewpoint(t, td)
            worst = max(worst, abs(back - rh))
    print(f"    max |RH - RH(Td(RH))| over -40..+60 °C, 5..99 % = {worst:.2e} %")
    assert worst < 1e-9
    print(f"    Td <= T always (Td = T exactly at RH = 100 %): "
          f"Td(25, 100) = {dewpoint_c(25.0, 100.0):.6f} °C")
    assert abs(dewpoint_c(25.0, 100.0) - 25.0) < 1e-9

    # ------------------------------------------------------------------ 3 --
    print("\n[3] wall lag - a spring morning in the cable trench")
    print(f"    tau = {WALL_TAU_S:.0f} s = {WALL_TAU_S / 60:.0f} min")
    wall = None
    dt = 300.0
    rows = []
    for step in range(int(8 * 3600 / dt) + 1):
        hour = 5.0 + step * dt / 3600.0
        # Air warms from 9 to 22 C over the morning; the trench keeps the RH up.
        air = 9.0 + 13.0 * max(0.0, min(1.0, (hour - 6.0) / 7.0))
        rh = 95.0 - 25.0 * max(0.0, min(1.0, (hour - 6.0) / 7.0))
        wall = wall_temp(wall, air, dt)
        td = dewpoint_c(air, rh)
        rows.append((hour, air, rh, wall, td, condensation_margin(wall, td)))
    print(f"    {'saat':>6} {'hava °C':>9} {'RH %':>7} {'yüzey °C':>10} "
          f"{'çiy °C':>9} {'pay K':>8}")
    for r in rows[::12]:
        flag = "  <- YOĞUŞMA" if r[5] < 0 else ""
        print(f"    {r[0]:6.1f} {r[1]:9.2f} {r[2]:7.1f} {r[3]:10.2f} "
              f"{r[4]:9.2f} {r[5]:8.2f}{flag}")
    wet = [r for r in rows if r[5] < 0.0]
    print(f"    surface below dew point for {len(wet) * dt / 60:.0f} minutes")
    print(f"    if we had compared the AIR to the dew point instead, "
          f"{sum(1 for r in rows if r[1] - r[4] < 0) * dt / 60:.0f} minutes "
          f"would have been flagged - the classic silent failure")
    assert len(wet) > 0, "the morning trench case must produce wetting"
    assert all(r[1] - r[4] >= 0 for r in rows), "air-based test must stay blind here"

    # ------------------------------------------------------------------ 4 --
    print("\n[4] wall model behaviour")
    print(f"    cold start (no previous state) returns ambient: "
          f"{wall_temp(None, 17.0, 60.0):.2f} °C")
    w = 10.0
    for _ in range(int(3 * WALL_TAU_S / 60)):
        w = wall_temp(w, 20.0, 60.0)
    print(f"    step 10 -> 20 °C, after 3 tau ({3 * WALL_TAU_S / 3600:.1f} h): "
          f"{w:.3f} °C  (expect 20 - 10*e^-3 = {20 - 10 * math.exp(-3):.3f})")
    assert abs(w - (20 - 10 * math.exp(-3))) < 0.01
    print(f"    after a 6 h data gap the estimate re-anchors on ambient: "
          f"{wall_temp(10.0, 20.0, 6 * 3600.0):.3f} °C  (we do not invent history)")

    # ------------------------------------------------------------------ 5 --
    print("\n[5] severity ladder")
    cases = [
        (5.0, 0.0, 0.0, "BILGI", "dry"),
        (1.5, 10.0, 0.0, "BILGI", "close, but only 10 min"),
        (1.5, 45.0, 0.0, "IZLE", "within 2 K for 45 min"),
        (-0.5, 45.0, 0.0, "IZLE", "wet, but under an hour"),
        (-0.5, 75.0, 0.0, "UYARI", "wet for 75 min"),
        (-2.0, 600.0, 3.0, "UYARI", "wet all night, PD flat"),
        (1.5, 45.0, 6.5, "KRITIK", "close AND PD up 6.5 dB in 48 h"),
        (-1.0, 90.0, 9.0, "KRITIK", "wet AND PD up 9 dB"),
        (4.0, 600.0, 12.0, "BILGI", "PD rising but the surface is dry - not moisture"),
    ]
    print(f"    {'pay K':>7} {'dk':>6} {'PD dB':>7}  {'beklenen':<8} {'sonuç':<8}")
    for m, mins, pd, expect, why in cases:
        got = condensation_severity(m, mins, pd)
        ok = "OK" if got == expect else "FAIL"
        print(f"    {m:7.1f} {mins:6.0f} {pd:7.1f}  {expect:<8} {got:<8} {ok}  {why}")
        assert got == expect, f"{m},{mins},{pd}: got {got} expected {expect}"
    print("    the ladder never returns ACIL: at 400 V condensation is a")
    print("    months-to-years tracking mechanism, not an emergency")

    # ------------------------------------------------------------------ 6 --
    print("\n[6] the operator's card")
    rep = condensation_report(1.4, 55.0, 7.2)
    print(f"    seviye  : {rep['severity']} · {rep['title_tr']}")
    print(f"    gerekçe : {rep['reason_tr']}")
    print(f"    aksiyon : {rep['action_tr']}")

    print("\nOK - dewpoint.py self-test passed")
