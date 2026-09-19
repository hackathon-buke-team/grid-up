"""K4 4.4: doğruluk matrisi hesaplayıcısı (tek tohum, tüm senaryolar)."""
import math

import pytest

from panogoz.eval.matrix import (
    RunResult,
    false_alarm_budget,
    run_matrix,
    summarize,
    wilson_interval,
)
from panogoz.sim.scenarios import SCENARIOS, Expect


@pytest.fixture(scope="module")
def results():
    return run_matrix([1])


def test_wilson_interval_matches_known_values():
    lo, hi = wilson_interval(10, 10)
    assert lo == pytest.approx(0.722, abs=0.005) and hi == pytest.approx(1.0, abs=1e-9)
    lo, hi = wilson_interval(0, 10)
    assert lo == 0.0 and hi == pytest.approx(0.278, abs=0.005)
    assert wilson_interval(0, 0) == (0.0, 1.0)


def test_every_detect_scenario_is_detected_on_the_reference_seed(results):
    for r in results:
        if r.expect == Expect.DETECT.value:
            assert r.detected, f"{r.key} tespit edilemedi"
            assert r.latency_days is not None and r.latency_days >= 0.0


def test_no_quiet_or_advisory_scenario_dispatches_a_false_alarm(results):
    for r in results:
        if r.expect in (Expect.QUIET.value, Expect.ADVISORY.value):
            assert r.false_alarm_episodes == 0, f"{r.key}: {r.false_alarm_kinds}"
    advisory = [r for r in results if r.expect == Expect.ADVISORY.value]
    assert advisory and all(not r.detected for r in advisory)


def test_result_covers_every_scenario_once_per_seed(results):
    assert {r.key for r in results} == set(SCENARIOS)
    assert len(results) == len(SCENARIOS)


def test_lead_time_is_positive_for_gradual_faults_and_none_without_danger(results):
    by = {r.key: r for r in results}
    assert by["loose_bolt_gradual"].lead_days > 0
    assert by["condensation_leak"].lead_days > 0
    assert by["neutral_joint_loose"].lead_days is None  # bu senaryoda tehlikeye varılmıyor


def test_fixed_threshold_baseline_shows_summer_blindness_and_low_load_blindness(results):
    by = {r.key: r for r in results}
    assert by["hot_summer"].fixed_absolute_first_s is not None  # sabit 75 °C yazın yanlış alarm verir
    assert by["hot_summer"].fixed_rise_first_s is None
    assert by["loose_bolt_low_load"].fixed_absolute_first_s is None  # düşük yükte gizli arıza
    assert by["loose_bolt_low_load"].fixed_rise_first_s is None


def test_summary_aggregates_detection_and_false_alarm_counts(results):
    summaries = {s.key: s for s in summarize(results)}
    s = summaries["loose_bolt_abrupt"]
    assert s.runs == 1 and s.detect_rate == 1.0 and s.detect_ci[0] < 1.0 <= s.detect_ci[1]
    assert s.fixed_abs.detected == 1 and s.fixed_abs.false_alarms == 0
    q = summaries["hot_summer"]
    assert q.expect == "quiet" and q.detect_rate is None and q.fixed_abs.false_alarms == 1


def test_false_alarm_budget_uses_rule_of_three_when_no_events(results):
    b = false_alarm_budget(results)
    assert b.false_alarm_episodes == 0 and b.per_panel_year == 0.0
    assert b.upper95_per_panel_year == pytest.approx(3.0 / (b.panel_days / 365.0))


def test_false_alarm_budget_counts_advisory_dispatch_as_false_alarm():
    base = dict(
        seed=1, expected_kind="pd_tracking", first_warning_s=None, first_alarm_s=1.0, onset_s=0.0, danger_s=None,
        false_alarm_kinds=(), false_alarm_episodes=0, warning_kinds=(), advisory_capped_samples=0,
        fixed_absolute_first_s=None, fixed_rise_first_s=None, days=60.0,
    )
    r = RunResult(key="pd_only_dry", expect="advisory", detected=True, **base)
    b = false_alarm_budget([r])
    assert b.false_alarm_episodes == 1
    assert b.per_panel_year == pytest.approx(1 / (60 / 365))
    assert math.isfinite(b.upper95_per_panel_year)
