import pytest

from panogoz.rules.engine import evaluate_connection
from panogoz.rules.fusion import max_severity
from panogoz.rules.suppression import DebounceTracker, current_family_corroborates, still_active
from panogoz.sim.scenarios import SCENARIOS


def test_max_severity_absolute_limits_always_win():
    assert max_severity("ALARM", "EMERGENCY") == "EMERGENCY"
    assert max_severity("NORMAL", "WATCH") == "WATCH"


def test_debounce_tracker_requires_three_of_five():
    tracker = DebounceTracker()
    assert tracker.push(True) is False
    assert tracker.push(True) is False
    assert tracker.push(True) is True


def test_debounce_tracker_forgets_outside_window():
    tracker = DebounceTracker()
    for _ in range(2):
        tracker.push(True)
    for _ in range(3):
        tracker.push(False)
    assert tracker.push(True) is False


def test_dead_band_hysteresis_keeps_alarm_open_below_raw_threshold():
    assert still_active(value=7.0, threshold=10.0) is True
    assert still_active(value=5.0, threshold=10.0) is False


def test_current_family_corroboration_blocked_when_de_energised():
    assert current_family_corroborates(0.3, set()) is True
    assert current_family_corroborates(0.3, {"DE_ENERGISED"}) is False
    assert current_family_corroborates(0.01, set()) is False


@pytest.mark.parametrize("scenario", SCENARIOS, ids=[s.scenario_id for s in SCENARIOS])
def test_scenario_matches_expected_alarm_outcome(scenario):
    records = scenario.run()
    result = evaluate_connection(records)
    assert result.alarm_ever_opened == scenario.expected_alarm, (
        f"{scenario.scenario_id} ({scenario.title}): beklenen={scenario.expected_alarm} "
        f"gerçekleşen={result.alarm_ever_opened}"
    )
    if scenario.expected_flags:
        assert scenario.expected_flags <= result.all_flags, (
            f"{scenario.scenario_id}: beklenen bayraklar {scenario.expected_flags} eksik, "
            f"gelenler {result.all_flags}"
        )


def test_slow_drift_detected_weeks_before_absolute_limit():
    scenario = next(s for s in SCENARIOS if s.scenario_id == "A2")
    records = scenario.run()
    result = evaluate_connection(records)
    assert result.first_alarm_day is not None
    assert result.first_alarm_day < scenario.days - 5
    assert all(r.temp_peak_c < 110.0 for r in records[: result.first_alarm_day + 1])
