from __future__ import annotations

from panogoz.detector.flags import (
    DE_ENERGISED_MAX_LOAD_FRACTION,
    Flag,
    flags_for_connection,
    is_de_energised,
    is_stale,
)
from panogoz.detector.theta import MIN_LOAD_FRACTION

RATED_A = 250.0


def test_stale_true_when_gap_exceeds_factor():
    assert is_stale(last_sample_t_s=0, now_t_s=1000, period_s=100, factor=3.0) is True


def test_stale_false_within_period():
    assert is_stale(last_sample_t_s=0, now_t_s=250, period_s=100, factor=3.0) is False


def test_stale_boundary_is_exclusive_not_stale():
    # gap tam olarak factor*period_s ise henuz "asan" degil.
    assert is_stale(last_sample_t_s=0, now_t_s=300, period_s=100, factor=3.0) is False


def test_de_energised_true_near_zero_current():
    assert is_de_energised(current_a=2.0, rated_current_a=RATED_A) is True  # 2/250 = 0.008


def test_de_energised_false_for_normal_load():
    assert is_de_energised(current_a=144.0, rated_current_a=RATED_A) is False


def test_de_energised_distinct_from_theta_uninformative_gate():
    """theta.py'nin %40 esiginin altinda ama DE_ENERGISED'in %2 esiginin
    USTUNDE bir akim: theta=None doner (uninformative) ama baglanti hala
    kesinlikle enerjili -- iki durum birbirine karismamali."""
    current_a = 0.30 * RATED_A  # 75A
    assert current_a / RATED_A < MIN_LOAD_FRACTION  # theta.py'nin gozunde "uninformative"
    assert current_a / RATED_A > DE_ENERGISED_MAX_LOAD_FRACTION  # ama DE_ENERGISED'in gozunde acik acik enerjili
    assert is_de_energised(current_a, RATED_A) is False


def test_flags_for_connection_all_clear():
    flags = flags_for_connection(
        last_sample_t_s=1000,
        now_t_s=1000,
        period_s=900,
        current_a=144.0,
        rated_current_a=RATED_A,
        sensor_drift_detected=False,
    )
    assert flags == set()


def test_flags_for_connection_sensor_drift_only():
    flags = flags_for_connection(
        last_sample_t_s=1000,
        now_t_s=1000,
        period_s=900,
        current_a=144.0,
        rated_current_a=RATED_A,
        sensor_drift_detected=True,
    )
    assert flags == {Flag.SENSOR_DRIFT}


def test_flags_for_connection_stale_and_de_energised_together():
    flags = flags_for_connection(
        last_sample_t_s=0,
        now_t_s=10_000,
        period_s=900,
        current_a=1.0,
        rated_current_a=RATED_A,
        sensor_drift_detected=False,
    )
    assert flags == {Flag.STALE, Flag.DE_ENERGISED}
