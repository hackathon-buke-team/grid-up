"""K4 4.4: ek dedektörler (aşırı yük, çiy noktası, nötr, PD, ark), ölü bant/debounce, ısıl tau tahmini."""
import math
import random

import pytest

from panogoz.contracts.channels import Phase
from panogoz.detector.arc import arc_integrity_scores, arc_trip_scores
from panogoz.detector.common import lowpass, rolling_median, rolling_rms
from panogoz.detector.condensation import (
    condensation_scores,
    dew_margin_c,
    dew_point_c,
    humidity_scores,
)
from panogoz.detector.overload import overload_scores
from panogoz.detector.pd import pd_scores
from panogoz.detector.theta import compute_theta_series
from panogoz.detector.thermal_tau import estimate_tau_s
from panogoz.rules.engine import Severity, debounce_severity, severity_with_deadband
from panogoz.sim.synthetic import ThermalSample

THETA_THR = {Severity.WARNING: 15.0, Severity.ALARM: 30.0, Severity.CRITICAL: 60.0}


def test_dew_point_matches_standard_table_values():
    assert dew_point_c(20.0, 50.0) == pytest.approx(9.3, abs=0.15)
    assert dew_point_c(30.0, 100.0) == pytest.approx(30.0, abs=0.01)
    assert dew_point_c(25.0, 60.0) == pytest.approx(16.7, abs=0.2)


def test_dew_margin_negative_when_wall_colder_than_dew_point():
    assert dew_margin_c(25.0, 90.0, wall_temp_c=20.0) < 0
    assert dew_margin_c(25.0, 40.0, wall_temp_c=20.0) > 0


def test_condensation_score_rises_as_margin_shrinks_and_masks_invalid():
    valid = [True, True, False]
    scored = condensation_scores([25.0, 25.0, 25.0], [40.0, 95.0, 95.0], [22.0, 22.0, 22.0], valid)
    assert scored.values[0] == 0.0  # geniş marj -> risk yok
    assert scored.values[1] > 5.0  # duvar çiy noktasının altında
    assert scored.values[2] is None and scored.reasons[2] == "STALE"


def test_humidity_score_is_median_not_mean():
    rh = [50.0, 50.0, 50.0, 99.0, 50.0, 50.0]
    scored = humidity_scores(rh, [True] * 6)
    assert scored.values[-1] == 50.0  # tek örneklik sıçrama medyanı bozmaz


def test_rolling_rms_and_median_require_full_window():
    assert rolling_rms([3.0, 4.0], 2) == [None, pytest.approx(math.sqrt(12.5))]
    assert rolling_rms([3.0, None, 4.0], 2) == [None, None, None]
    assert rolling_median([1.0, 9.0, 2.0], 3) == [None, None, 2.0]


def test_lowpass_first_order_response():
    out = lowpass([0.0, 10.0, 10.0, 10.0], alpha=0.5)
    assert out == pytest.approx([0.0, 5.0, 7.5, 8.75])


def test_overload_uses_worst_phase_rolling_rms_over_rated():
    n = 8
    cur = {Phase.L1: [100.0] * n, Phase.L2: [300.0] * n, Phase.L3: [100.0] * n}
    scored = overload_scores(cur, rated_current_a=250.0, valid=[True] * n, window=4)
    assert scored.values[2] is None and scored.reasons[2] == "WARMUP"
    assert scored.values[-1] == pytest.approx(300.0 / 250.0)


def test_overload_ignores_single_spike_but_not_sustained_load():
    n = 12
    base = {p: [100.0] * n for p in Phase}
    spike = {p: list(v) for p, v in base.items()}
    spike[Phase.L1][6] = 600.0
    one = overload_scores(spike, 250.0, [True] * n, window=4)
    sustained = {p: [300.0] * n for p in Phase}
    many = overload_scores(sustained, 250.0, [True] * n, window=4)
    assert max(v for v in one.values if v is not None) < 1.25  # 2,4x'lik tek sıçrama ALARM eşiğini aşmaz
    assert many.values[-1] == pytest.approx(1.2)


def test_pd_median_suppresses_single_burst():
    pd = [4.0] * 20
    pd[10] = 90.0
    scored = pd_scores(pd, [True] * 20)
    assert max(v for v in scored.values if v is not None) < 10.0


def test_arc_trip_is_immediate_and_integrity_flags_sensor_fault():
    trip = arc_trip_scores([0, 1, 0], [True] * 3)
    assert trip.values == [0.0, 2.0, 0.0]
    integrity = arc_integrity_scores([1, 0], [True, True])
    assert integrity.values == [0.0, 1.0]


def test_deadband_holds_level_until_score_falls_below_exit_threshold():
    scores = [0.0, 16.0, 12.0, 10.0, 8.0]  # WARNING eşiği 15, çıkış 9
    out = severity_with_deadband(scores, THETA_THR, deadband=0.40)
    assert out == [Severity.NORMAL, Severity.WARNING, Severity.WARNING, Severity.WARNING, Severity.NORMAL]


def test_deadband_steps_down_one_level_at_a_time():
    out = severity_with_deadband([31.0, 20.0, 17.0, 5.0], THETA_THR, deadband=0.40)
    assert out == [Severity.ALARM, Severity.ALARM, Severity.WARNING, Severity.NORMAL]


def test_deadband_resets_on_masked_sample():
    out = severity_with_deadband([40.0, None, 12.0], THETA_THR, deadband=0.40)
    assert out == [Severity.ALARM, Severity.NORMAL, Severity.NORMAL]  # 12 < 15: taşınan seviye yok


def test_debounce_requires_three_of_five():
    raw = [Severity.NORMAL, Severity.ALARM, Severity.NORMAL, Severity.ALARM, Severity.NORMAL, Severity.ALARM]
    out = debounce_severity(raw)
    assert out[3] == Severity.NORMAL  # 5 pencerede 2 isabet
    assert out[5] == Severity.ALARM  # son 5'te 3 isabet


def test_debounce_one_of_one_passes_events_immediately():
    out = debounce_severity([Severity.NORMAL, Severity.CRITICAL], window=1, min_hits=1)
    assert out[1] == Severity.CRITICAL


def _first_order_series(load_a: list[float], k_by_phase: dict[Phase, float], tau_s: float, dt: float = 900.0, amb: float = 30.0):
    alpha = min(dt / tau_s, 1.0)
    temps = {p: amb + k_by_phase[p] * load_a[0] ** 2 * (1.1 if p is Phase.L2 else 0.92 if p is Phase.L3 else 1.0) ** 2 for p in Phase}
    scale = {Phase.L1: 1.0, Phase.L2: 1.1, Phase.L3: 0.92}
    out = {p: [] for p in Phase}
    for i, base in enumerate(load_a):
        for p in Phase:
            cur = base * scale[p]
            temps[p] += alpha * (amb + k_by_phase[p] * cur**2 - temps[p])
            out[p].append(ThermalSample(t_s=i * dt, phase=p, current_a=cur, surface_temp_c=temps[p]))
    return out


def test_theta_lag_compensation_cancels_transient_false_theta():
    # %10 dengesiz ama SAĞLAM bağlantı, yük 250 A <-> 110 A sıçrıyor
    load = ([250.0] * 12 + [110.0] * 12) * 4
    series = _first_order_series(load, {p: 0.0006 for p in Phase}, tau_s=1800.0)
    instant = compute_theta_series(series, rated_current_a=250.0)
    lagged = compute_theta_series(series, rated_current_a=250.0, lag_tau_s=1800.0)
    worst_instant = max(abs(s.theta) for s in instant[Phase.L2] if s.theta is not None)
    worst_lagged = max(abs(s.theta) for s in lagged[Phase.L2][12:] if s.theta is not None)
    assert worst_instant > 15.0  # gecikme telafisiz: sahte UYARI seviyesi
    assert worst_lagged < 8.0  # telafili: yalnız gerçek dengesizlik payı (~6,5 K)


def test_theta_default_behaviour_unchanged_without_lag_parameter():
    series = _first_order_series([250.0] * 5, {p: 0.0006 for p in Phase}, tau_s=1800.0)
    a = compute_theta_series(series, rated_current_a=250.0)
    b = compute_theta_series(series, rated_current_a=250.0, lag_tau_s=None)
    assert [s.theta for s in a[Phase.L2]] == [s.theta for s in b[Phase.L2]]


@pytest.mark.parametrize("true_tau", [900.0, 1800.0, 5400.0])
def test_estimate_tau_recovers_true_time_constant_from_baseline(true_tau):
    rng = random.Random(7)
    dt, n = 900.0, 14 * 96
    load, level = [], 200.0
    for i in range(n):
        if i % 6 == 0:
            level = rng.uniform(120.0, 320.0)
        load.append(level)
    ambient = [30.0 + 5.0 * math.sin(2 * math.pi * i * dt / 86400.0) for i in range(n)]
    alpha = dt / true_tau
    temp, t = [], ambient[0] + 0.0006 * load[0] ** 2
    for i in range(n):
        t += alpha * (ambient[i] + 0.0006 * load[i] ** 2 - t)
        temp.append(t + 0.3)  # sabit sensör ofseti
    est = estimate_tau_s([(temp, ambient, [x * x for x in load])], [True] * n, gate=(0.4 * 250.0) ** 2, period_s=dt, count=n)
    assert est == pytest.approx(true_tau, rel=0.08)
