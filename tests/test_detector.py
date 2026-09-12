from panogoz.detector.engine import (
    CusumDetector,
    ThermalRLS,
    absolute_severity,
    compute_expect_flags,
    condensation_margin_c,
    dew_point_c,
    neutral_k,
    theta_raw,
)


def test_theta_raw_zero_when_no_deviation():
    assert theta_raw(60.0, [60.0, 60.0], 250.0) == 0.0


def test_theta_raw_normalizes_by_nominal_current():
    small = theta_raw(70.0, [60.0, 60.0], 400.0)
    large = theta_raw(70.0, [60.0, 60.0], 250.0)
    assert large > small > 0


def test_theta_raw_handles_empty_siblings():
    assert theta_raw(90.0, [], 250.0) == 0.0


def test_thermal_rls_isolates_load_independent_offset():
    rls = ThermalRLS()
    residual = None
    for _ in range(50):
        residual = rls.update(0.05, 0.0)
    assert residual is not None and abs(residual - 0.05) < 1e-6


def test_thermal_rls_learns_pure_load_driven_relationship():
    rls = ThermalRLS()
    residual = None
    for i in range(200):
        delta_i_sq = 0.1 * ((i % 7) - 3)
        theta = 2.0 * delta_i_sq
        residual = rls.update(theta, delta_i_sq)
    assert abs(residual) < 0.05


def test_cusum_detects_sustained_drift():
    cusum = CusumDetector(k=0.01, h=0.05)
    triggered_days = [cusum.update_daily(0.0) for _ in range(3)]
    assert not any(triggered_days)
    triggered_later = [cusum.update_daily(0.05) for _ in range(10)]
    assert any(triggered_later)
    assert cusum.changepoint_day is not None


def test_neutral_k_scales_with_delta_t_over_i_squared():
    assert neutral_k(8.0, 2.0) == 2.0
    assert neutral_k(8.0, 0.0) == 0.0


def test_dew_point_below_air_temp_at_partial_humidity():
    assert dew_point_c(22.0, 55.0) < 22.0


def test_condensation_margin_negative_at_high_humidity():
    margin = condensation_margin_c(t_wall_c=17.5, t_air_c=22.0, rh_pct=92.0)
    assert margin < 0


def test_absolute_severity_thresholds():
    assert absolute_severity(100.0) is None
    assert absolute_severity(110.0) == "CRITICAL"
    assert absolute_severity(130.0) == "EMERGENCY"


def test_compute_expect_flags_stale_when_gap_exceeds_period():
    flags = compute_expect_flags(now_ts=10_000, last_ts=0, period_s=900, current_a=100.0, drift_score=None)
    assert "STALE" in flags


def test_compute_expect_flags_de_energised_below_threshold():
    flags = compute_expect_flags(now_ts=1000, last_ts=1000, period_s=900, current_a=1.0, drift_score=None)
    assert "DE_ENERGISED" in flags


def test_compute_expect_flags_sensor_drift_above_threshold():
    flags = compute_expect_flags(now_ts=1000, last_ts=1000, period_s=900, current_a=100.0, drift_score=5.0)
    assert "SENSOR_DRIFT" in flags


def test_compute_expect_flags_clean_reading_has_no_flags():
    flags = compute_expect_flags(now_ts=1000, last_ts=900, period_s=900, current_a=100.0, drift_score=0.1)
    assert flags == set()
