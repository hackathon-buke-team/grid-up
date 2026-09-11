"""Acceptance tests for the PANO GOZ physics simulator.

Two jobs, and the second one is the interesting one.

**Job one:** pin the load generator to criteria a Turkish DSO would recognise, so
it cannot silently regress into noise.  Every bound below is asserted on 30-day
15-minute series across seasons and across panels.

**Job two:** apply the *same* criteria to the data supplied with the hackathon
and watch it fail all of them.  The "Akim Sensoru" sheet is 152 rows at 15-minute
intervals of ``=RANDBETWEEN(15;90)``.  The lag-1 autocorrelation of a real
quarter-hourly LV feeder is above +0.97, because a neighbourhood cannot change
its consumption by an independent random amount every fifteen minutes.  The
sheet's is +0.0003.  ``var(diff)/var(series)`` is 2.0023 - the exact white-noise
value of 2.  Excess kurtosis is -1.2129, the signature of a discrete uniform.
Day-over-day shape correlation at identical clock time is +0.0596 where a real
feeder gives above +0.85.

This is not a complaint about the organisers.  It is the reason the whole system
is built to be **history-free on day one**: theta compares three sibling phases
that already exist inside the panel, so it needs no training set, and no
training set was available.

How wide the guarantee is
-------------------------

The named tests below assert the criteria on four load characters across four
seasons.  The generator was also swept over **1416 independent 30-day series**
(112 fleet panels plus 6 hand-built characters, x 12 monthly windows).  Eight of
the nine criteria are met by **100 %** of those series.  The ninth, the 30-day
load factor, is met by 99.79 % - three series land at 0.543 or 0.705 against a
0.55-0.70 band.

That last figure is reported rather than tuned away.  A monthly mean/max of 0.54
is a real thing a real feeder-month does; squeezing the generator until no window
could ever produce one would mean deleting the weather, and a load model with no
weather is a worse model, not a better one.

Run it either way::

    pytest tests/test_sim_acceptance.py
    python -m tests.test_sim_acceptance
"""

from __future__ import annotations

import datetime as dt
import math
import random

from panogoz.contracts import assets, channels
from panogoz.sim import faults as fx
from panogoz.sim import load as ld
from panogoz.sim import thermal as th
from panogoz.sim.fleet import FleetSim, NO_ANALYSER_FRACTION, NO_ARC_RELAY_FRACTION
from panogoz.sim.load import (LoadModel, acf, cv, mean_abs_step_pct, profile_stats,
                              sample_series, turning_point_fraction, var_ratio)
from panogoz.sim.panel import PanelSim, backfill

# --------------------------------------------------------------------------
# The acceptance criteria
# --------------------------------------------------------------------------

#: ``key -> (low, high)``; ``None`` means unbounded on that side.
CRITERIA: dict[str, tuple[float | None, float | None]] = {
    "acf_1": (0.97, None),        # 15 min
    "acf_4": (0.85, None),        # 1 h
    "acf_96": (0.60, None),       # 24 h
    "var_ratio": (None, 0.05),    # white noise gives exactly 2.0
    "step_pct": (1.5, 4.0),       # mean |15 min step| as % of mean
    "turning_pct": (0.15, 0.30),  # white noise gives 2/3
    "cv": (0.20, 0.30),
    "load_factor": (0.55, 0.70),  # mean / max
    "min_over_max": (0.25, 0.45),
}

CRITERIA_LABEL = {
    "acf_1": "ACF lag-1 (15 dk)",
    "acf_4": "ACF lag-4 (1 sa)",
    "acf_96": "ACF lag-96 (24 sa)",
    "var_ratio": "var(fark)/var(seri)",
    "step_pct": "ort |15 dk adim| %",
    "turning_pct": "donus noktasi orani",
    "cv": "degisim katsayisi",
    "load_factor": "yuk faktoru ort/maks",
    "min_over_max": "min/maks",
}


def _ts(iso: str) -> float:
    return dt.datetime.fromisoformat(iso).replace(tzinfo=dt.timezone.utc).timestamp()


#: Windows chosen to cover the two very different Turkish load shapes: the
#: winter evening peak and the summer air-conditioning plateau, plus a shoulder.
WINDOWS: tuple[tuple[str, str], ...] = (
    ("kis", "2026-01-05"),
    ("ilkbahar", "2026-04-15"),
    ("yaz", "2026-07-10"),
    ("sonbahar", "2026-10-01"),
)

#: A deliberately awkward spread: a tidy suburban feeder, a badly unbalanced
#: rural one, a big industrial one, and a small heavily nonlinear one.
MODELS: tuple[tuple[str, dict], ...] = (
    ("dengeli",       dict(seed=1, base_a=1100.0, unbalance=0.06)),
    ("dengesiz %30",  dict(seed=7, base_a=900.0, unbalance=0.30, nonlinear=1.8)),
    ("agir yuklu",    dict(seed=11, base_a=1300.0, unbalance=0.10, nonlinear=0.8)),
    ("dogrusal disi", dict(seed=41, base_a=980.0, unbalance=0.20, nonlinear=2.0)),
)

DEMO_TS = _ts("2026-06-15")

#: Result of the wide sweep described in the module docstring: 118 load
#: characters x 12 monthly windows = 1416 series of 2880 samples each.
#: ``key -> (min, p05, median, p95, max, fraction_outside)``
FLEET_SWEEP: dict[str, tuple[float, float, float, float, float, float]] = {
    "acf_1":        (0.9932, 0.9937, 0.9948, 0.9955, 0.9959, 0.0000),
    "acf_4":        (0.9218, 0.9268, 0.9458, 0.9528, 0.9574, 0.0000),
    "acf_96":       (0.8501, 0.8734, 0.8944, 0.9126, 0.9303, 0.0000),
    "var_ratio":    (0.0067, 0.0076, 0.0087, 0.0111, 0.0118, 0.0000),
    "step_pct":     (1.7585, 1.8003, 1.8808, 2.0312, 2.0739, 0.0000),
    "turning_pct":  (0.1782, 0.1939, 0.2210, 0.2391, 0.2568, 0.0000),
    "cv":           (0.2363, 0.2417, 0.2507, 0.2629, 0.2754, 0.0000),
    "load_factor":  (0.5433, 0.5821, 0.6281, 0.6811, 0.7045, 0.0021),
    "min_over_max": (0.2819, 0.3097, 0.3396, 0.3724, 0.4029, 0.0000),
}
FLEET_SWEEP_N = 1416


def _check(stats: dict[str, float]) -> list[str]:
    bad = []
    for key, (lo, hi) in CRITERIA.items():
        v = stats[key]
        if v != v:
            bad.append(f"{key}=NaN")
        elif lo is not None and v < lo:
            bad.append(f"{key}={v:.4f} < {lo}")
        elif hi is not None and v > hi:
            bad.append(f"{key}={v:.4f} > {hi}")
    return bad


# --------------------------------------------------------------------------
# The supplied hackathon sheet
# --------------------------------------------------------------------------

#: The documented statistics of the supplied "Akim Sensoru" sheet, measured from
#: the file itself.  A generator that reproduces them is a generator that
#: reproduces uniform random noise.
SUPPLIED = ld.SUPPLIED_SHEET_STATS


def supplied_like_series(seed: int = 20260910) -> list[float]:
    """152 draws of ``=RANDBETWEEN(15;90)``, scaled to primary amps.

    The sheet's own header describes a 5 A -> 125 mA interposing CT cascaded with
    the TEDAS 2500/5, which is 20 000:1 or 20.0 A per mA.  Its formula applies
    600000/100 = 6000, or 6.0 A per mA.  The two disagree by a factor of 3.33,
    and 125 mA x 6.0 is 750 A, not the 600 A the sheet calls full scale.  We use
    the formula's 6.0 because that is what the numbers in the file actually did.
    """
    rng = random.Random(seed)
    return [rng.randint(15, 90) * 6.0 for _ in range(152)]


def excess_kurtosis(x: list[float]) -> float:
    n = len(x)
    m = sum(x) / n
    m2 = sum((a - m) ** 2 for a in x) / n
    m4 = sum((a - m) ** 4 for a in x) / n
    return m4 / (m2 * m2) - 3.0


def supplied_stats() -> dict[str, float]:
    """Acceptance statistics for the supplied sheet.

    ``acf_96`` and ``load_factor``-style shape measures need more than 152
    samples to be meaningful, so where the sheet is too short we substitute the
    figure measured on the file itself.  ``acf_1`` and ``var_ratio`` are the two
    that settle the argument on their own and both come straight from the file.
    """
    s = supplied_like_series()
    out = {
        "acf_1": SUPPLIED["acf_1"],
        "acf_4": acf(s, 4),
        "acf_96": acf(s, 96),
        "var_ratio": SUPPLIED["var_ratio"],
        "step_pct": mean_abs_step_pct(s),
        "turning_pct": turning_point_fraction(s),
        "cv": SUPPLIED["ma_cv"],
        "load_factor": SUPPLIED["a_mean"] / SUPPLIED["a_max"],
        "min_over_max": SUPPLIED["a_min"] / SUPPLIED["a_max"],
        "excess_kurtosis": excess_kurtosis(s),
    }
    return out


# ==========================================================================
# Tests - load
# ==========================================================================

def test_load_meets_every_acceptance_criterion():
    """Every model, every season, a 30-day 15-minute series."""
    failures: list[str] = []
    for mname, kw in MODELS:
        m = LoadModel(**kw)
        for wname, iso in WINDOWS:
            st = profile_stats(sample_series(m, _ts(iso), 30))
            bad = _check(st)
            if bad:
                failures.append(f"{mname}/{wname}: {', '.join(bad)}")
    assert not failures, "load generator failed acceptance:\n  " + "\n  ".join(failures)


def test_load_criteria_hold_across_a_sample_of_the_real_fleet():
    """A spot check on the fleet itself, not just hand-built characters.

    Eleven panels x four seasons.  Every criterion except the load factor must
    hold on every series; the load factor is allowed one stray window in the
    sample, for the reason set out in the module docstring.
    """
    f = FleetSim(112, seed=42, start_ts=DEMO_TS)
    panels = f.panels()[::10]
    strays = 0
    total = 0
    for p in panels:
        for wname, iso in WINDOWS:
            st = profile_stats(sample_series(p.load, _ts(iso), 30))
            total += 1
            for key, (lo, hi) in CRITERIA.items():
                v = st[key]
                inside = ((lo is None or v >= lo) and (hi is None or v <= hi))
                if inside:
                    continue
                if key == "load_factor":
                    strays += 1
                    assert 0.52 <= v <= 0.72, f"{p.panel_key}/{wname}: {key}={v:.4f}"
                else:
                    raise AssertionError(f"{p.panel_key}/{wname}: {key}={v:.4f}")
    assert strays <= max(1, total // 20), f"{strays} load-factor strays in {total}"


def test_recorded_fleet_sweep_matches_the_live_generator():
    """The sweep numbers quoted in the docstring must still describe this code.

    Recomputing 1416 series in a unit test would be indulgent, so a small
    stratified sample is checked against the recorded percentiles instead.  If
    the generator drifts, the medians move and this catches it.
    """
    f = FleetSim(112, seed=42, start_ts=DEMO_TS)
    got: dict[str, list[float]] = {k: [] for k in CRITERIA}
    for p in f.panels()[::14]:
        for iso in ("2026-01-05", "2026-07-10"):
            st = profile_stats(sample_series(p.load, _ts(iso), 30))
            for k in CRITERIA:
                got[k].append(st[k])
    for k, rec in FLEET_SWEEP.items():
        v = sorted(got[k])
        med = v[len(v) // 2]
        lo, p05, rec_med, p95, hi, _ = rec
        assert lo * 0.9 <= med <= hi * 1.1, (k, med, rec)
        assert abs(med - rec_med) < 0.25 * max(abs(rec_med), 0.05), (k, med, rec_med)


def test_load_criteria_hold_on_individual_phases_too():
    """The criteria are asserted on the three-phase mean; L1 alone must pass too.

    Unbalance adds a slow multiplicative wander on top of each phase.  If it were
    large or fast enough to break the autocorrelation structure, the per-phase
    series a real analyser reports would not look like a feeder.
    """
    m = LoadModel(seed=7, base_a=1000.0, unbalance=0.30)
    t0 = _ts("2026-07-10")
    s = [m.currents(t0 + i * 900)[0] for i in range(2880)]
    st = profile_stats(s)
    assert not _check(st), f"L1 alone failed: {_check(st)}"


def test_supplied_hackathon_data_fails_the_same_criteria():
    """The contrast that justifies building our own generator."""
    st = supplied_stats()
    assert st["acf_1"] < 0.05, "supplied sheet should have no autocorrelation"
    assert st["var_ratio"] > 1.9, "supplied sheet should sit at the white-noise value of 2"
    assert st["turning_pct"] > 0.55, "supplied sheet should sit near the 2/3 of white noise"
    assert st["excess_kurtosis"] < -0.9, "supplied sheet should show the uniform signature"
    bad = _check(st)
    # It must fail at least the four structural criteria, not scrape through.
    for key in ("acf_1", "acf_4", "var_ratio", "turning_pct"):
        assert any(b.startswith(key) for b in bad), f"{key} unexpectedly passed on noise"


def test_supplied_like_series_reproduces_the_documented_moments():
    """Our reconstruction of RANDBETWEEN(15;90) matches the file's own moments,
    which is what licenses using it as a stand-in for the missing sheet."""
    s = supplied_like_series()
    ma = [v / 6.0 for v in s]
    assert len(s) == int(SUPPLIED["n"])
    assert 15.0 <= min(ma) <= 20.0 and 85.0 <= max(ma) <= 90.0
    mean = sum(ma) / len(ma)
    assert abs(mean - SUPPLIED["ma_mean"]) < 4.0, mean
    sd = math.sqrt(sum((v - mean) ** 2 for v in ma) / (len(ma) - 1))
    assert abs(sd - SUPPLIED["ma_sd"]) < 3.0, sd


def test_absolute_current_levels_match_a_1600_kva_panel():
    m = LoadModel(seed=1, base_a=1100.0)
    year = [m.avg_current(_ts("2026-01-01") + i * 3600.0) for i in range(8760)]
    mean = sum(year) / len(year)
    assert 900.0 <= mean <= 1300.0, mean
    assert 1700.0 <= max(year) <= 2100.0, max(year)
    assert 500.0 <= min(year) <= 700.0, min(year)
    # and never above the 2312 A of Tablo 3a on a healthy panel
    assert max(year) < assets.MAIN_BUSBAR_RATED_A


def test_neutral_current_behaviour():
    t0 = _ts("2026-02-01")
    normal = LoadModel(seed=3, unbalance=0.06, nonlinear=1.0)
    heavy = LoadModel(seed=3, unbalance=0.06, nonlinear=2.8)
    for model, lo, hi in ((normal, 10.0, 25.0), (heavy, 40.0, 70.0)):
        pct = []
        for i in range(96 * 7):
            i1, i2, i3, i_n = model.currents(t0 + i * 900)
            pct.append(100.0 * i_n / ((i1 + i2 + i3) / 3.0))
        mean = sum(pct) / len(pct)
        assert lo * 0.75 <= mean <= hi * 1.05, (mean, lo, hi)
        assert max(pct) <= hi * 1.05, max(pct)


def test_triplen_harmonics_add_arithmetically():
    """I_N,h = 3 * h3 * I1.  Zero sequence, so the three phases add, not cancel."""
    m = LoadModel(seed=5)
    i = 500.0
    fund = LoadModel.neutral_fundamental(i, i, i)
    assert fund < 1e-9, "a perfectly balanced fundamental leaves no neutral current"
    i_n = m.neutral_current(0.0, i, i, i, h3=0.10)
    assert abs(i_n - 3.0 * 0.10 * i) < 1e-6, i_n


def test_dewpoint_uses_alduchov_eskridge():
    assert abs(ld.dewpoint_c(20.0, 50.0) - 9.26) < 0.01
    assert ld.MAGNUS_A == 17.62 and ld.MAGNUS_B == 243.12
    # round trip
    for t, rh in ((5.0, 90.0), (35.0, 30.0), (-2.0, 75.0)):
        td = ld.dewpoint_c(t, rh)
        assert abs(ld.rh_from_dewpoint(t, td) - rh) < 0.05


def test_condensation_events_per_year():
    """15-40 mornings a year where the wall reaches the dewpoint, weighted to the
    wet half of the year."""
    days: set[int] = set()
    winter = 0
    t0 = _ts("2026-01-01")
    for i in range(365 * 24):
        t = t0 + i * 3600.0
        if ld.condensation_margin_k(t, 37.9, 5) <= 0.0:
            d = ld.local_day_index(t)
            days.add(d)
            if ld._doy(t) < 105 or ld._doy(t) > 274:  # Oct-Apr
                winter += 1
    assert 15 <= len(days) <= 40, len(days)
    assert winter >= 1, "condensation should not be a summer-only phenomenon"


def test_ambient_respects_the_service_envelope_shape():
    t0 = _ts("2026-01-01")
    year = [ld.ambient_c(t0 + i * 3600.0, 37.9, 5) for i in range(365 * 24)]
    assert -8.0 < min(year) < 4.0, min(year)
    assert 36.0 < max(year) < 45.0, max(year)
    mean = sum(year) / len(year)
    assert 14.0 < mean < 22.0, mean


# ==========================================================================
# Tests - thermal physics
# ==========================================================================

def test_busbar_thermal_resistance_is_the_fin_value_not_3_44():
    lo, hi = th.BUSBAR_R_TH_LO_K_PER_W, th.BUSBAR_R_TH_HI_K_PER_W
    assert 0.23 <= lo <= 0.26, lo
    assert 0.36 <= hi <= 0.39, hi
    # The wrong figure would predict a physically impossible rise.
    assert 267.0 * 3.44 > 900.0
    assert 267.0 * hi < 120.0, "the fin value keeps a 50 uohm busbar joint physical"


def test_lug_case_inverts_back_to_the_injected_resistance():
    p = 400.0 ** 2 * 50e-6
    assert abs(p - 8.0) < 0.01, p
    theta = th.joint_rise_k(p, th.R_TH_LUG_NOM_K_PER_W, n=1.0)
    lo, hi = th.excess_r_interval_uohm(theta, 400.0)
    assert lo < 50.0 < hi, (lo, hi)
    assert lo / hi == th.R_TH_LUG_LO_K_PER_W / th.R_TH_LUG_HI_K_PER_W


def test_healthy_joint_power_matches_the_brief():
    for r_uohm, want_w in ((3.0, 16.0), (5.0, 27.0), (50.0, 267.0)):
        p = assets.MAIN_BUSBAR_RATED_A ** 2 * r_uohm * 1e-6
        assert abs(p - want_w) / want_w < 0.06, (r_uohm, p, want_w)


def test_fuse_links_dominate_the_in_panel_heat_budget():
    """The busbar is about 200 W; the thirty NH poles are two to three times that."""
    for lf in (0.4, 0.55, 0.7):
        fuse = th.fuse_loss_w(lf)
        bus = th.BUSBAR_LOSS_AT_RATED_W * lf * lf
        assert fuse > 2.0 * bus, (lf, fuse, bus)
        per_pole = fuse / 30.0
        assert 2.0 <= per_pole <= 15.0, (lf, per_pole)
    assert 150.0 <= th.fuse_loss_w(0.5) <= 500.0


def test_air_rise_is_20_k_at_rated():
    tm = th.ThermalModel(rated_a=400.0)
    assert abs(tm.steady_air_rise_k(1.0) - 20.0) < 0.01
    assert tm.steady_air_rise_k(0.5) > 20.0 * 0.25, "P^0.8 must beat a pure square law"


def test_theta_min_table_matches_the_brief():
    for f, want in ((0.85, 0.83), (0.60, 1.67), (0.40, 3.75), (0.20, 15.0)):
        assert abs(th.theta_min_k(f, 0.2) - want) < 0.02, (f, want)
    for f, want in ((0.85, 3.32), (0.20, 60.0)):
        assert abs(th.theta_min_k(f, 0.8) - want) < 0.05, (f, want)
    assert th.SENSITIVITY_FLOOR_F == 0.35


def test_sibling_pair_noise_is_the_design_sigma():
    n = 4000
    d = [th.mount_micro_k(7, 11, i * 60.0) - th.mount_micro_k(7, 23, i * 60.0)
         for i in range(n)]
    m = sum(d) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in d) / (n - 1))
    assert 0.13 <= sd <= 0.28, sd  # design target 0.2 K for a contact pair
    d_ir = [th.mlx90640_read(40.0, 7, 1, i) - th.mlx90640_read(40.0, 7, 2, i)
            for i in range(n)]
    m = sum(d_ir) / n
    sd_ir = math.sqrt(sum((x - m) ** 2 for x in d_ir) / (n - 1))
    assert 0.7 <= sd_ir <= 0.9, sd_ir  # design target 0.8 K for an IR pixel pair


def test_tmp117_is_quantised_to_one_128th_of_a_kelvin():
    v = th.tmp117_read(37.312345, 1, 1, 100.0)
    assert abs(v * 128.0 - round(v * 128.0)) < 1e-9, v
    assert abs(v - 37.312345) < 0.25


# ==========================================================================
# Tests - panel simulator
# ==========================================================================

def _panel(**kw) -> PanelSim:
    base = dict(panel_key="SOKE-14", panel_index=14, site="Soke", name="Soke 14",
                dso="ADM", lat=37.75, lon=27.41, seed=14, start_ts=DEMO_TS)
    base.update(kw)
    return PanelSim(**base)


def test_panel_only_emits_channels_from_the_registry():
    sim = _panel()
    sim.step(DEMO_TS)
    o = sim.step(DEMO_TS + 60)
    for name in o.channel_names():
        assert name in channels.BY_NAME, f"invented channel {name!r}"
    for src in (o.panel, *o.joints.values(), *o.devices.values()):
        for name, value in src.items():
            assert channels.validate(name, value), f"{name}={value} out of range"


def test_panel_geometry_comes_from_the_asset_model():
    sim = _panel()
    sim.step(DEMO_TS)
    o = sim.step(DEMO_TS + 60)
    assert set(o.joints) <= {j.key for j in assets.monitored_joints()}
    assert len(o.joints) == 40
    assert set(o.devices) == {d.key for d in assets.DEVICES}
    assert len(o.devices) == assets.DEVICES_PER_PANEL == 9


def test_only_the_six_clip_conductors_report_a_current():
    """No outgoing way has a utility CT.  We do not invent one for the other 34."""
    sim = _panel()
    sim.step(DEMO_TS)
    o = sim.step(DEMO_TS + 60)
    with_current = {k for k, v in o.joints.items() if "tc.current_a" in v}
    assert len(with_current) == 6
    assert with_current == set(sim.clip_of.values())
    assert all("ir.lug_temp_c" in v for v in o.joints.values())


def test_no_analyser_emits_no_mpr_channels_at_all():
    sim = _panel(has_analyser=False, has_arc_relay=False)
    sim.step(DEMO_TS)
    o = sim.step(DEMO_TS + 60)
    assert not [c for c in o.panel if c.startswith("mpr.")]
    assert not [c for c in o.panel if c.startswith("tvoc.")]
    # but the clips still carry their own CTs, so theta still works
    assert any("tc.current_a" in v for v in o.joints.values())
    assert "env.air_c" in o.panel


def test_determinism():
    a, b = _panel(), _panel()
    for i in range(20):
        oa, ob = a.step(DEMO_TS + i * 300), b.step(DEMO_TS + i * 300)
    assert oa.panel == ob.panel
    assert oa.joints == ob.joints


def test_backfill_produces_history_and_primes_the_thermal_nodes():
    sim = _panel()
    out = list(backfill(sim, 3, 3600))
    assert len(out) == 3 * 24 + 1
    assert out[0].ts == DEMO_TS - 3 * 86400
    assert out[-1].ts == DEMO_TS
    first = out[0].truth["joints"]["C07-L2-PABUC"]
    # primed at steady state, so no warm-up transient in the first hours
    assert abs(first["dt_excess_k"] - first["dt_excess_ss_k"]) < 0.05


# ---- scenario behaviour ---------------------------------------------------

def _paired(scenario: str, days: float, step_s: int, **kw):
    clean, dirty = _panel(), _panel()
    dirty.inject(scenario, at_ts=DEMO_TS, **kw)
    n = int(days * 86400 / step_s)
    rows = []
    for i in range(n + 1):
        t = DEMO_TS + i * step_s
        rows.append((t, clean.step(t), dirty.step(t)))
    return rows, clean, dirty


def _day_median(rows, which: str, joint: str, fld: str) -> dict[int, float]:
    b: dict[int, list[float]] = {}
    for t, oc, od in rows:
        o = od if which == "dirty" else oc
        b.setdefault(int((t - DEMO_TS) // 86400), []).append(o.truth["joints"][joint][fld])
    return {d: sorted(v)[len(v) // 2] for d, v in b.items()}


def _window_median(daily: dict[int, float], days: range) -> float:
    v = sorted(daily[d] for d in days if d in daily)
    return v[len(v) // 2]


def _drift_k_per_week(rows, joint: str, span_days: int, win: int = 7) -> float:
    """Slope of the clean-to-faulted theta gap, estimated from week-long medians.

    Two single days would be a terrible estimator here: the day-to-day residual
    on a healthy joint is a kelvin or more, which is the whole reason the
    detector runs CUSUM on daily medians instead of thresholding a sample.  A
    test that used two days would be measuring that noise, not the drift.
    """
    mc = _day_median(rows, "clean", joint, "theta_k")
    md = _day_median(rows, "dirty", joint, "theta_k")
    gap = {d: md[d] - mc[d] for d in md if d in mc}
    early = _window_median(gap, range(0, win))
    late = _window_median(gap, range(span_days - win, span_days))
    weeks = (span_days - win) / 7.0
    return (late - early) / weeks


JT = "C07-L2-PABUC"
NJ = "C07-N-PABUC"


def test_scenario_registry_is_complete_and_consistent():
    required = {
        "gevsek_baglanti", "hizli_gevseme", "notr_gevsek", "harmonik_yuk",
        "asiri_yuk", "havalandirma_tikali", "yogusma", "pd_yuzen", "ark_olayi",
        "dedektor_arizasi", "sensor_takildi", "sensor_kaydi", "dugum_sessiz",
        "sicak_hava_dalgasi", "sebeke_olayi", "trafo_devreye_alma", "pano_enerjisiz",
    }
    assert required <= set(fx.SCENARIOS)
    for name, spec in fx.SCENARIOS.items():
        assert spec["label_tr"] and spec["description_tr"]
        assert isinstance(spec["expect_alarm"], bool)
        assert isinstance(spec["default_kw"], dict)
    for name in ("sicak_hava_dalgasi", "sebeke_olayi", "trafo_devreye_alma",
                 "pano_enerjisiz", "sensor_takildi", "sensor_kaydi", "dugum_sessiz"):
        assert fx.SCENARIOS[name]["expect_alarm"] is False, name
    assert fx.SCENARIOS["havalandirma_tikali"]["expect_mode"] == "thermal_runaway"
    assert "loose_connection" in fx.SCENARIOS["havalandirma_tikali"]["forbid_modes"]


def test_every_scenario_runs_without_producing_invalid_data():
    for name in sorted(fx.SCENARIOS):
        sim = _panel()
        sim.step(DEMO_TS)
        sim.inject(name, at_ts=DEMO_TS)
        for i in range(1, 8):
            o = sim.step(DEMO_TS + i * 1800)
        for src in (o.panel, *o.joints.values(), *o.devices.values()):
            for ch, v in src.items():
                assert channels.validate(ch, v), f"{name}: {ch}={v}"
        assert sim.active_faults and sim.active_faults[0]["scenario"] == name
        sim.clear_faults()
        assert sim.active_faults == []


def test_loose_connection_drifts_theta_at_the_injected_rate():
    rows, clean, dirty = _paired("gevsek_baglanti", 56, 3600, joint_key=JT)
    rate = _drift_k_per_week(rows, JT, 56)
    # 0.2 K/week at the reference current, amplified by the f^(2(n-1)) convection
    # bias because the feeder does not sit at its own rating.
    assert 0.15 <= rate <= 0.50, rate
    mc = _day_median(rows, "clean", JT, "theta_k")
    md = _day_median(rows, "dirty", JT, "theta_k")
    gap = {d: md[d] - mc[d] for d in md if d in mc}
    assert _window_median(gap, range(49, 56)) > 1.0


def test_fast_loosening_is_ten_times_faster():
    slow_rows, _, _ = _paired("gevsek_baglanti", 28, 3600, joint_key=JT)
    fast_rows, _, _ = _paired("hizli_gevseme", 28, 3600, joint_key=JT)
    slow = _drift_k_per_week(slow_rows, JT, 28)
    fast = _drift_k_per_week(fast_rows, JT, 28)
    assert fast > 5.0 * slow, (slow, fast)
    mc = _day_median(fast_rows, "clean", JT, "theta_k")
    md = _day_median(fast_rows, "dirty", JT, "theta_k")
    gap = {d: md[d] - mc[d] for d in md if d in mc}
    assert _window_median(gap, range(21, 28)) > 5.0, "must clear the 5 K alarm gate"


def test_heat_wave_moves_every_temperature_and_leaves_theta_untouched():
    """The single scenario that separates PANO GOZ from a thermometer."""
    rows, clean, dirty = _paired("sicak_hava_dalgasi", 4, 1800)
    t, oc, od = rows[-1]
    assert od.truth["ambient_c"] - oc.truth["ambient_c"] > 10.0
    assert od.panel["env.air_c"] - oc.panel["env.air_c"] > 10.0
    for k, cj in oc.truth["joints"].items():
        dj = od.truth["joints"][k]
        assert dj["t_joint_c"] - cj["t_joint_c"] > 9.0, k
        assert abs(dj["theta_k"] - cj["theta_k"]) < 1e-6, k


def test_blocked_ventilation_warms_all_joints_together():
    """Absolute temperature climbs everywhere; the sibling differences barely
    move.  The mode is thermal_runaway, and it must never be loose_connection."""
    rows, clean, dirty = _paired("havalandirma_tikali", 4, 1800)
    t, oc, od = rows[-1]
    rises = [od.truth["joints"][k]["t_joint_c"] - oc.truth["joints"][k]["t_joint_c"]
             for k in oc.truth["joints"]]
    assert min(rises) > 2.0, min(rises)
    assert max(rises) - min(rises) < 0.4 * (sum(rises) / len(rises)), "must rise together"
    clip = sorted(clean.clip_of.values())
    for k in clip:
        dth = abs(od.truth["joints"][k]["theta_k"] - oc.truth["joints"][k]["theta_k"])
        rise = od.truth["joints"][k]["t_joint_c"] - oc.truth["joints"][k]["t_joint_c"]
        assert dth < rise, (k, dth, rise)


def test_harmonic_loading_raises_i_n_but_not_k_n():
    rows, clean, dirty = _paired("harmonik_yuk", 14, 1800)
    ic = _day_median(rows, "clean", NJ, "current_a")
    idd = _day_median(rows, "dirty", NJ, "current_a")
    kc = _day_median(rows, "clean", NJ, "k_n_ss_k_per_a2")
    kd = _day_median(rows, "dirty", NJ, "k_n_ss_k_per_a2")
    d = 13
    assert idd[d] / ic[d] > 1.4, "neutral current must climb"
    assert 0.6 <= kd[d] / kc[d] <= 1.15, f"K_N must stay flat, got {kd[d]/kc[d]:.2f}"


def test_bad_neutral_joint_raises_k_n_but_not_i_n():
    rows, clean, dirty = _paired("notr_gevsek", 14, 1800, joint_key=NJ)
    ic = _day_median(rows, "clean", NJ, "current_a")
    idd = _day_median(rows, "dirty", NJ, "current_a")
    kc = _day_median(rows, "clean", NJ, "k_n_ss_k_per_a2")
    kd = _day_median(rows, "dirty", NJ, "k_n_ss_k_per_a2")
    d = 13
    assert abs(idd[d] / ic[d] - 1.0) < 0.02, "neutral current must not move"
    assert kd[d] / kc[d] > 2.0, f"K_N must climb, got {kd[d]/kc[d]:.2f}"


def test_overload_raises_current_not_theta():
    rows, clean, dirty = _paired("asiri_yuk", 2, 1800, feeder_index=7)
    t, oc, od = rows[-1]
    ic = oc.truth["feeder_currents"][7]["L2"]
    idd = od.truth["feeder_currents"][7]["L2"]
    assert idd / ic > 2.0, (ic, idd)
    dth = abs(od.truth["joints"][JT]["theta_k"] - oc.truth["joints"][JT]["theta_k"])
    assert dth < 3.0, dth


def test_de_energised_zeroes_every_electrical_quantity():
    sim = _panel()
    sim.step(DEMO_TS)
    sim.inject("pano_enerjisiz", at_ts=DEMO_TS, at_s=0.0)
    o = sim.step(DEMO_TS + 300)
    assert o.truth["de_energised"]
    assert "DE_ENERGISED" in o.truth["flags"]
    assert o.truth["i_l1"] == 0.0 and o.truth["i_n"] == 0.0
    # The analyser is fed from the panel's own measurement circuit, so it is
    # unpowered.  It must publish that it is gone, not a set of zeros: zeros
    # would be a measurement nobody made.
    assert o.panel["mpr.online"] == 0.0
    assert [c for c in o.panel if c.startswith("mpr.")] == ["mpr.online"]
    for j in o.truth["joints"].values():
        assert j["current_a"] == 0.0
        assert j["p_joint_w"] == 0.0
    # the battery-powered clips keep reporting, which is how we know the busbar
    # is dead rather than the RS-485 link broken
    assert any("tc.current_a" in v for v in o.joints.values())
    assert all(v.get("tc.current_a", 0.0) < 1.0 for v in o.joints.values())


def test_transformer_inrush_is_brief_and_carries_no_energy():
    f = fx.make_fault("trafo_devreye_alma", 0.0)
    assert f.panel_current_scale(1800.0) >= 6.5
    assert f.panel_current_scale(1800.0 + 2.0) < 1.3
    assert f.panel_current_scale(1800.0 + 5.0) == 1.0
    assert f.voltage_scale(1800.0) < 0.85


def test_grid_event_raises_thd_v_on_all_three_phases_equally():
    sim = _panel()
    sim.step(DEMO_TS)
    o0 = sim.step(DEMO_TS + 60)
    sim.inject("sebeke_olayi", at_ts=DEMO_TS + 60)
    o1 = sim.step(DEMO_TS + 120)
    d = [o1.panel[f"mpr.thd_v_l{p}_pct"] - o0.panel[f"mpr.thd_v_l{p}_pct"] for p in (1, 2, 3)]
    assert min(d) > 3.0, d
    assert max(d) - min(d) < 0.6, "all three move together -> upstream, not us"


def test_sensor_drift_moves_the_clip_and_not_the_array():
    clean, dirty = _panel(), _panel()
    dirty.inject("sensor_kaydi", at_ts=DEMO_TS, device_key="TC-05", k_per_day=0.35)
    for i in range(int(6 * 86400 / 1800)):
        t = DEMO_TS + i * 1800
        oc, od = clean.step(t), dirty.step(t)
    d_clip = od.joints[JT]["tc.temp_c"] - oc.joints[JT]["tc.temp_c"]
    d_ir = od.joints[JT]["ir.lug_temp_c"] - oc.joints[JT]["ir.lug_temp_c"]
    assert 1.5 < d_clip < 2.5, d_clip
    assert abs(d_ir) < 1e-9, "the array sees the same lug and must not move"
    assert od.truth["joints"][JT]["r_joint_uohm"] == oc.truth["joints"][JT]["r_joint_uohm"]


def test_stuck_sensor_stops_moving_while_its_siblings_do_not():
    clean, dirty = _panel(), _panel()
    dirty.inject("sensor_takildi", at_ts=DEMO_TS, device_key="TC-05", at_s=0.0)
    vals, sib = [], []
    for i in range(48):
        t = DEMO_TS + i * 1800
        clean.step(t)
        od = dirty.step(t)
        vals.append(od.joints[JT]["tc.temp_c"])
        sib.append(od.joints["C07-L1-PABUC"]["tc.temp_c"])
    assert len(set(vals)) == 1, "a stuck sensor must not move at all"
    assert len(set(sib)) > 10, "its siblings must keep breathing"


def test_silent_node_stops_reporting_entirely():
    sim = _panel()
    sim.step(DEMO_TS)
    sim.inject("dugum_sessiz", at_ts=DEMO_TS, device_key="TC-03", at_s=300.0)
    o = sim.step(DEMO_TS + 600)
    assert "TC-03" not in o.devices
    assert "tc.temp_c" not in o.joints["C06-L3-PABUC"]
    assert "ir.lug_temp_c" in o.joints["C06-L3-PABUC"], "the array still sees the lug"
    assert any(e["type"] == "node_silent" for e in o.events)


def test_condensation_uses_the_wall_not_the_air():
    clean, dirty = _panel(), _panel()
    dirty.inject("yogusma", at_ts=DEMO_TS)
    worst = 99.0
    for i in range(int(2 * 86400 / 600)):
        t = DEMO_TS + i * 600
        clean.step(t)
        od = dirty.step(t)
        worst = min(worst, od.panel["env.condensation_margin_k"])
        # the air itself is never supersaturated
        assert od.panel["env.dewpoint_c"] <= od.truth["ambient_c"] + 1e-6
    assert worst <= 0.0, worst


# ---- arc protection -------------------------------------------------------

def test_arc_trip_names_the_detector_and_the_relay():
    sim = _panel()
    sim.step(DEMO_TS)
    sim.inject("ark_olayi", at_ts=DEMO_TS + 60, at_s=0.0, detector="X2:4", relay="K5")
    o = sim.step(DEMO_TS + 120)
    ev = [e for e in o.events if e["type"] == "arc_trip"]
    assert len(ev) == 1
    assert ev[0]["detector"] == "X2:4" and ev[0]["relay"] == "K5"
    assert ev[0]["trip_time_ms"] == 1.0
    lo, hi = ev[0]["notify_latency_s"]
    assert (lo, hi) == (4.0, 13.0), "latency is a range, never a single number"
    r = sim.tvoc_registers(DEMO_TS + 120)
    assert r[1300] & 1, "reg 1300 bit0 = active trip"
    assert r[210] == 1 << 13, "X2:4 is bit 13 of the LOW detector word"
    assert r[211] == 0
    assert r[212] == 1 << 1, "K5 is bit1 of the relay word"
    assert r[149] == 1
    assert o.truth["de_energised"], "no LV incoming breaker: the trip is on the MV side"


def test_tvoc_detector_bit_maps():
    assert fx.detector_bits("X1:1") == (1 << 0, 0)
    assert fx.detector_bits("X1:10") == (1 << 9, 0)
    assert fx.detector_bits("X2:1") == (1 << 10, 0)
    assert fx.detector_bits("X2:5") == (1 << 14, 0)
    assert fx.detector_bits("X2:6") == (0, 1 << 0)
    assert fx.detector_bits("X2:10") == (0, 1 << 4)
    assert fx.detector_bits("X3:1") == (0, 1 << 5)
    assert fx.detector_bits("X3:10") == (0, 1 << 14)


def test_tvoc_4_4_2_zero_means_not_populated():
    """Manual 4.4.2: registers 200-212 and 222-225 read 0x0000 when there is no
    active error or trip.  A zero in reg 222 does NOT mean all ten detectors
    failed.  Gate on reg 1300."""
    sim = _panel()
    sim.step(DEMO_TS)
    r = sim.tvoc_registers(DEMO_TS)
    assert r[1300] == 0
    assert r[222] == r[223] == r[224] == r[225] == 0
    for a in range(200, 213):
        assert r[a] == 0
    assert 213 not in r, "reg 213 is write-only; reading it raises exception 02"
    o = sim.step(DEMO_TS + 60)
    assert o.panel["tvoc.detectors_ok"] == o.panel["tvoc.detectors_total"] == 20

    sim.inject("dedektor_arizasi", at_ts=DEMO_TS + 60, at_s=0.0,
               detector="X2:7", ambient_detector="X2:9")
    o = sim.step(DEMO_TS + 120)
    r = sim.tvoc_registers(DEMO_TS + 120)
    assert r[1300] & 2, "reg 1300 bit1 = active error"
    assert r[222] != 0, "now the block is populated"
    assert not (r[222] >> 6) & 1, "X2:7 is bit6 of reg 222 and must read 0 = Error"
    assert not (r[224] >> 8) & 1, "X2:9 is bit8 of reg 224 and must read 0 = Warning"
    assert o.panel["tvoc.detectors_ok"] == 19
    assert o.panel["tvoc.ambient_warn"] == 1


def test_no_arc_relay_is_not_the_same_as_a_silent_one():
    sim = _panel(has_arc_relay=False)
    sim.step(DEMO_TS)
    o = sim.step(DEMO_TS + 60)
    assert not [c for c in o.panel if c.startswith("tvoc.")]
    assert sim.tvoc_registers(DEMO_TS + 60) == {}


def test_tvoc_date_encoding_is_binary_not_bcd():
    sim = _panel()
    sim._arc["last_selftest_ts"] = _ts("2026-03-04") + 14 * 3600 + 37 * 60
    sim.step(DEMO_TS)
    r = sim.tvoc_registers(DEMO_TS)
    assert r[220] == int(_ts("2026-03-04") // 86400), "unsigned days since 1970-01-01"
    assert r[221] == (14 << 8) | 37, "HHMM: hour in the MSB, minute in the LSB, binary"


# ---- RF channel -----------------------------------------------------------

def test_pd_class_walks_to_floating_electrode_and_clusters_at_current_zero():
    sim = _panel()
    sim.step(DEMO_TS)
    sim.inject("pd_yuzen", at_ts=DEMO_TS, ramp_days=12.0)
    seen = []
    for d in (0.5, 4.0, 9.0, 14.0):
        o = sim.step(DEMO_TS + d * 86400)
        seen.append(channels.PRPD_CLASSES[int(o.panel["pd.class"])])
    assert seen[0] == "GURULTU"
    assert seen[-1] == "YUZEN"
    f = fx.make_fault("pd_yuzen", DEMO_TS)
    o = f.pd_override(DEMO_TS + 12 * 86400, {"rate_per_s": 6.0, "qmax_db": 11.0,
                                             "nqn": 18.0, "tev_db": 8.0,
                                             "ultrasonic_db": 5.0, "klass": "GURULTU"})
    assert o["phase_clusters_deg"] == [0.0, 180.0], (
        "a series arc restrikes near CURRENT ZERO, not at the current peaks")


# ==========================================================================
# Tests - fleet
# ==========================================================================

def test_fleet_is_mixed_the_way_a_real_one_is():
    f = FleetSim(112, seed=42, start_ts=DEMO_TS)
    s = f.summary()
    assert s["panels"] == 112
    assert s["devices_total"] == 112 * 9
    assert s["joints_monitored"] == 112 * 40
    assert abs(s["no_analyser_pct"] - 100 * NO_ANALYSER_FRACTION) < 1.0
    assert abs(s["no_arc_relay_pct"] - 100 * NO_ARC_RELAY_FRACTION) < 1.0
    assert s["adm"] > 0 and s["gdz"] > 0


def test_fleet_panels_are_seeded_from_their_index():
    big = FleetSim(112, seed=42, start_ts=DEMO_TS)
    small = FleetSim(20, seed=42, start_ts=DEMO_TS)
    assert small.panels()[13].seed == big.panels()[13].seed
    a = FleetSim(8, seed=42, start_ts=DEMO_TS)
    b = FleetSim(8, seed=42, start_ts=DEMO_TS)
    assert a.panels()[0].step(DEMO_TS).panel == b.panels()[0].step(DEMO_TS).panel


def test_fleet_shares_weather_within_a_district():
    f = FleetSim(112, seed=42, start_ts=DEMO_TS)
    by_site: dict[str, list] = {}
    for p in f.panels():
        by_site.setdefault(p.site, []).append(p)
    for site, ps in by_site.items():
        assert len({p.weather_seed for p in ps}) == 1, site


def test_fleet_get_and_keys():
    f = FleetSim(20, seed=42, start_ts=DEMO_TS)
    k = f.keys()[3]
    assert f.get(k).panel_key == k
    try:
        f.get("YOK-99")
    except KeyError:
        pass
    else:  # pragma: no cover
        raise AssertionError("unknown panel must raise")


# ==========================================================================
# Report
# ==========================================================================

def _fmt(key: str, v: float) -> str:
    return f"{v:.4f}" if abs(v) < 100 else f"{v:.1f}"


def _verdict(key: str, v: float) -> str:
    lo, hi = CRITERIA[key]
    if v != v:
        return "kaldi"
    if lo is not None and v < lo:
        return "kaldi"
    if hi is not None and v > hi:
        return "kaldi"
    return "gecti"


def print_comparison() -> None:
    print("PANO GOZ · yuk profili kabul olcutleri")
    print("=" * 104)
    print("Ayni olcutler, iki veri kaynagi. Solda uretecimiz, sagda hackathon ile")
    print("verilen 'Akim Sensoru' sayfasi (152 satir, 15 dk, =RANDBETWEEN(15;90)).")
    print()

    series = {}
    for mname, kw in MODELS:
        m = LoadModel(**kw)
        for wname, iso in WINDOWS:
            series[(mname, wname)] = profile_stats(sample_series(m, _ts(iso), 30))
    sup = supplied_stats()

    hdr = f"{'olcut':<22}{'aralik':<16}"
    for wname, _ in WINDOWS:
        hdr += f"{wname:>11}"
    hdr += f"{'VERILEN':>12}{'bizim':>8}{'verilen':>9}"
    print(hdr)
    print("-" * 104)
    for key in CRITERIA:
        lo, hi = CRITERIA[key]
        rng = (f">= {lo}" if hi is None else
               f"<= {hi}" if lo is None else f"{lo} - {hi}")
        row = f"{CRITERIA_LABEL[key]:<22}{rng:<16}"
        worst_ok = True
        for wname, _ in WINDOWS:
            vals = [series[(m, wname)][key] for m, _ in MODELS]
            v = min(vals) if (lo is not None) else max(vals)
            worst_ok &= _verdict(key, v) == "gecti"
            row += f"{v:>11.4f}"
        row += f"{sup[key]:>12.4f}"
        row += f"{'GECTI' if worst_ok else 'KALDI':>8}"
        row += f"{_verdict(key, sup[key]).upper():>9}"
        print(row)
    print("-" * 104)
    print(f"{'fazla basiklik':<22}{'~0 (normal)':<16}"
          + " " * (11 * len(WINDOWS))
          + f"{sup['excess_kurtosis']:>12.4f}"
          + f"{'-':>8}{'KALDI':>9}")
    nfail = sum(1 for k in CRITERIA if _verdict(k, sup[k]) != "gecti")
    print(f"  -> verilen sayfa 9 olcutten {nfail}'inde kaliyor; kalanlar 152 satirda")
    print("     zaten ayirt edici degil. Yapisal olanlar (ACF, var orani, donus")
    print("     noktasi) tek basina kesin sonucu veriyor.")
    print("-" * 104)
    print()
    print("Verilen sayfanin dosyadan olculen kanitlari:")
    print(f"  lag-1 otokorelasyon  {SUPPLIED['acf_1']:+.4f}   (gercek 15 dk fider > +0.97)")
    print(f"  var(fark)/var(seri)  {SUPPLIED['var_ratio']:.4f}   (beyaz gurultunun tam degeri 2)")
    print(f"  fazla basiklik       {SUPPLIED['excess_kurtosis']:+.4f}   (kesikli duzgun dagilim imzasi)")
    print(f"  KS D={SUPPLIED['ks_d']:.4f} < kritik {SUPPLIED['ks_crit']:.4f} -> U(14.5, 90.5) reddedilemiyor")
    print(f"  ki-kare {SUPPLIED['chi2']:.2f}, sd {SUPPLIED['chi2_df']:.0f}, p={SUPPLIED['chi2_p']:.3f}"
          f" -> 76 tamsayi uzerinde duzgun")
    print(f"  ayni saatte gun-gune sekil korelasyonu {SUPPLIED['day_shape_r']:+.4f}"
          f"   (gercek fider > +0.85)")
    print(f"  saate gore ANOVA F(23,128)={SUPPLIED['anova_f']:.3f}, p={SUPPLIED['anova_p']:.3f}"
          f" -> gunun saati hicbir sey aciklamiyor")
    print(f"  olcek celiskisi: sayfanin basligi 40:1 ara CT ile 2500/5 kaskadi tarif eder")
    print(f"    (20000:1 = 20.0 A/mA) ama formulu 600000/100 = 6.0 A/mA uygular; 3.33 kat fark.")
    print(f"    Ayrica 125 mA x 6.0 = 750 A, sayfanin yazdigi 600 A tam skala degil.")
    print(f"  tum veri panonun anmasinin %3.9 - %23.4 araliginda: asiri yuk yok, tepe yok,")
    print(f"    anomali yok. Bu bir yuk profili degil, 152 rastgele sayidir.")
    print()
    print(f"Ureteci genis tarama: {FLEET_SWEEP_N} bagimsiz 30 gunluk seri")
    print("(112 filo panosu + 6 elle kurulmus karakter, x 12 aylik pencere)")
    print(f"  {'olcut':<22}{'min':>10}{'p05':>10}{'medyan':>10}{'p95':>10}{'maks':>10}{'disarda':>10}")
    for k, (mn, p05, med, p95, mx, out) in FLEET_SWEEP.items():
        print(f"  {CRITERIA_LABEL[k]:<22}{mn:>10.4f}{p05:>10.4f}{med:>10.4f}"
              f"{p95:>10.4f}{mx:>10.4f}{100*out:>9.2f}%")
    print("  Dokuz olcutten sekizi serilerin %100'unde saglaniyor. Dokuzuncusu,")
    print("  30 gunluk yuk faktoru, %99.79'unda. Bu ucu gizlenmiyor: aylik yuk")
    print("  faktoru gercekten de 0.54'e dusebilir; havayi silmeden bunu")
    print("  engelleyemeyiz ve havasiz bir yuk modeli daha kotu bir modeldir.")
    print()
    print("Sonuc: verilen veri ile egitim yapilamaz. Bu yuzden theta tarih gerektirmez -")
    print("panonun icindeki uc kardes faz zaten devreye alma gununde gecerli bir referanstir.")


def print_physics() -> None:
    print()
    print("PANO GOZ · fizik dogrulamalari")
    print("=" * 104)
    print(f"  bara iki tarafli kanat R_th        {th.BUSBAR_R_TH_LO_K_PER_W:.2f}"
          f" - {th.BUSBAR_R_TH_HI_K_PER_W:.2f} K/W   (3.44 K/W ~10 kat yanlis)")
    print(f"  240 mm2 kablo pabucu R_th          {th.R_TH_LUG_LO_K_PER_W:.1f}"
          f" - {th.R_TH_LUG_HI_K_PER_W:.1f} K/W")
    p50 = 400.0 ** 2 * 50e-6
    lo, hi = th.excess_r_interval_uohm(p50 * th.R_TH_LUG_NOM_K_PER_W, 400.0)
    print(f"  400 A pabuc @ 50 uohm              {p50:.1f} W ->"
          f" {p50*th.R_TH_LUG_LO_K_PER_W:.0f}-{p50*th.R_TH_LUG_HI_K_PER_W:.0f} K"
          f"  -> ters cozum {lo:.0f}-{hi:.0f} uohm")
    print(f"  2312 A bara eklemi @ 50 uohm       {2312.0**2*50e-6:.0f} W ->"
          f" {2312.0**2*50e-6*th.BUSBAR_R_TH_LO_K_PER_W:.0f}"
          f"-{2312.0**2*50e-6*th.BUSBAR_R_TH_HI_K_PER_W:.0f} K   (919 K DEGIL)")
    print(f"  pano kayip butcesi @ %55 yuk       bara {th.BUSBAR_LOSS_AT_RATED_W*0.55**2:.0f} W"
          f" + NH sigortalar {th.fuse_loss_w(0.55):.0f} W"
          f" (%{100*th.fuse_loss_w(0.55)/th.panel_loss_w(0.55):.0f} sigorta)")
    print(f"  kabin havasi anma akiminda         +{th.ThermalModel().steady_air_rise_k(1.0):.1f} K")
    print(f"  cig noktasi 20 C / %50 RH          {ld.dewpoint_c(20.0, 50.0):.2f} C (beklenen 9.26)")
    print(f"  {'f':>6}{'theta_min TC':>15}{'theta_min IR':>15}   durum")
    for f in (0.85, 0.60, 0.40, 0.35, 0.20):
        state = "gorunur" if f >= th.SENSITIVITY_FLOOR_F else "SENSITIVITY_LOW"
        print(f"  {f:>6.2f}{th.theta_min_k(f, 0.2):>15.2f}{th.theta_min_k(f, 0.8):>15.2f}   {state}")


def main() -> int:
    print_comparison()
    print_physics()
    print()
    print("PANO GOZ · kabul testleri")
    print("=" * 104)
    tests = [(n, o) for n, o in sorted(globals().items())
             if n.startswith("test_") and callable(o)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
        except AssertionError as exc:
            failed += 1
            print(f"  FAIL  {name}\n        {exc}")
        except Exception as exc:  # pragma: no cover
            failed += 1
            print(f"  ERROR {name}\n        {type(exc).__name__}: {exc}")
        else:
            print(f"  ok    {name}")
    print("-" * 104)
    print(f"  {len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
