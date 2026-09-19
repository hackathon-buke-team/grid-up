"""K4 4.4: çok kanallı senaryo üreticisi + bastırma/füzyon hattı (gerçek fizik modeli üzerinde)."""
import pytest

from panogoz.contracts.channels import Phase
from panogoz.detector.condensation import dew_margin_c
from panogoz.rules.engine import Severity
from panogoz.rules.pipeline import Family, analyze
from panogoz.sim.scenarios import DANGER_RISE_K, SCENARIOS, Expect, generate

DAY = 86400.0


@pytest.fixture(scope="module")
def runs():
    """Her senaryo tek tohumla bir kez üretilip analiz edilir (0,4 sn/senaryo)."""
    cache = {}

    def get(key: str, seed: int = 1):
        if (key, seed) not in cache:
            data = generate(SCENARIOS[key], seed=seed)
            cache[(key, seed)] = (data, analyze(data))
        return cache[(key, seed)]

    return get


def _first(track, level, start=0):
    return next((i for i in range(start, len(track.fused)) if track.fused[i] >= level), None)


def test_generation_is_deterministic_per_seed_and_differs_across_seeds():
    a = generate(SCENARIOS["healthy_baseline"], seed=3)
    b = generate(SCENARIOS["healthy_baseline"], seed=3)
    c = generate(SCENARIOS["healthy_baseline"], seed=4)
    assert a.joint_temp_c[Phase.L2] == b.joint_temp_c[Phase.L2]
    assert a.joint_temp_c[Phase.L2] != c.joint_temp_c[Phase.L2]


def test_all_channels_have_equal_length_and_15_minute_period():
    d = generate(SCENARIOS["healthy_baseline"], seed=1)
    n = len(d.t_s)
    assert n == 60 * 96
    assert d.t_s[1] - d.t_s[0] == 900.0
    for series in (d.neutral_current_a, d.neutral_temp_c, d.ambient_c, d.wall_temp_c, d.humidity_rh, d.pd_index, d.arc_trip, d.arc_sensor_ok, d.valid):
        assert len(series) == n
    for p in Phase:
        assert len(d.current_a[p]) == len(d.joint_temp_c[p]) == n


def test_healthy_panel_is_physically_plausible(runs):
    d, _ = runs("healthy_baseline")
    rise = max(max(d.joint_temp_c[p][i] for p in Phase) - d.ambient_c[i] for i in range(len(d.t_s)))
    assert 20.0 < rise < DANGER_RISE_K  # sağlıklı bağlantı standart sınırın altında ısınır
    assert min(dew_margin_c(a, r, w) for a, r, w in zip(d.ambient_c, d.humidity_rh, d.wall_temp_c)) > 3.0
    assert d.truth.kind is None and d.truth.danger_t_s is None


def test_load_profile_rms_is_scaled_to_requested_fraction():
    d = generate(SCENARIOS["healthy_baseline"], seed=1)
    rms = (sum(x * x for x in d.current_a[Phase.L1]) / len(d.t_s)) ** 0.5
    assert rms == pytest.approx(0.70 * d.rated_current_a, rel=0.02)


def test_gradual_fault_has_ground_truth_danger_after_onset(runs):
    d, _ = runs("loose_bolt_gradual")
    assert d.truth.onset_t_s == 32 * DAY
    assert d.truth.onset_t_s < d.truth.danger_t_s < d.t_s[-1]


def test_loose_bolt_is_detected_within_hours_and_only_on_the_faulty_phase(runs):
    d, an = runs("loose_bolt_abrupt")
    onset_i = int(d.truth.onset_t_s // d.period_s)
    faulty = an.track("loose_bolt:L2")
    i = _first(faulty, Severity.ALARM, onset_i)
    assert i is not None and (d.t_s[i] - d.truth.onset_t_s) < 0.5 * DAY
    assert _first(faulty, Severity.ALARM, 0) >= onset_i  # onset'ten önce alarm yok
    for other in ("loose_bolt:L1", "loose_bolt:L3"):
        assert max(an.track(other).fused) < Severity.ALARM


def test_theta_detects_fault_at_low_load_where_temperature_rules_are_blind(runs):
    d, an = runs("loose_bolt_low_load")
    assert max(an.track("loose_bolt:L2").fused) >= Severity.ALARM
    peak_rise = max(max(d.joint_temp_c[p][i] for p in Phase) - d.ambient_c[i] for i in range(len(d.t_s)))
    assert peak_rise < 45.0  # sabit +45 K kuralı bunu göremez


@pytest.mark.parametrize(
    "key",
    [k for k, s in SCENARIOS.items() if s.expect is Expect.QUIET],
)
def test_negative_controls_raise_no_alarm_level_process_finding(runs, key):
    _, an = runs(key)
    sc = SCENARIOS[key]
    for tr in an.tracks:
        if tr.spec.family is Family.SYSTEM and tr.spec.kind in sc.allowed_extra:
            continue
        assert max(tr.fused) < Severity.ALARM, f"{key}: {tr.key} ALARM üstü verdi"


def test_pd_alone_is_capped_at_warning_by_fusion(runs):
    _, an = runs("pd_only_dry")
    pd = an.track("pd_tracking")
    assert max(pd.confirmed) >= Severity.ALARM  # ham dedektör ALARM seviyesine ulaşıyor
    assert max(pd.fused) == Severity.WARNING  # füzyon: ikinci kanal ailesi yok -> UYARI'da tutulur
    assert sum(pd.capped) > 0


def test_pd_is_promoted_only_after_humidity_corroborates(runs):
    d, an = runs("pd_tracking_humid")
    pd, humidity = an.track("pd_tracking"), an.track("humidity_high")
    first_alarm = _first(pd, Severity.ALARM)
    first_support = _first(humidity, Severity.WARNING)
    assert first_alarm is not None and first_support is not None
    assert first_alarm >= first_support  # destekleyici aile gelmeden ALARM yok


def test_arc_trip_is_critical_immediately_and_latching_flagged(runs):
    d, an = runs("arc_trip")
    trip = an.track("arc_trip")
    i = _first(trip, Severity.CRITICAL)
    assert d.t_s[i] == pytest.approx(d.truth.onset_t_s)
    assert trip.spec.latching is True


def test_arc_integrity_fault_is_an_alarm_not_a_trip(runs):
    _, an = runs("arc_integrity_fault")
    assert max(an.track("arc_integrity").fused) == Severity.ALARM
    assert max(an.track("arc_trip").fused) == Severity.NORMAL


def test_communication_dropout_masks_detectors_with_stale_reason_and_raises_system_alarm(runs):
    d, an = runs("comms_dropout")
    gap = [i for i, ok in enumerate(d.valid) if not ok]
    assert gap
    theta = an.track("loose_bolt:L2")
    assert all(theta.reasons[i] == "STALE" for i in gap)
    assert max(an.track("comms_lost").fused) >= Severity.ALARM


def test_de_energised_feeder_is_suppressed_with_reason_not_alarmed(runs):
    d, an = runs("de_energised_maintenance")
    theta = an.track("loose_bolt:L2")
    reasons = {theta.reasons[i] for i, t in enumerate(d.t_s) if 38 * DAY < t < 40 * DAY - 3600}
    assert "DE_ENERGISED" in reasons
    assert max(theta.fused) < Severity.WARNING


def test_condensation_and_overload_lead_the_true_danger_time(runs):
    d, an = runs("condensation_leak")
    i = _first(an.track("condensation"), Severity.ALARM)
    assert d.t_s[i] < d.truth.danger_t_s  # gerçek yoğuşmadan ÖNCE ALARM
    d2, an2 = runs("overload_sustained")
    assert _first(an2.track("overload"), Severity.ALARM) is not None


def test_every_track_spec_is_wired_into_the_analysis(runs):
    _, an = runs("healthy_baseline")
    kinds = {t.spec.kind for t in an.tracks}
    assert kinds == {
        "loose_bolt", "loose_bolt_trend", "overload", "neutral_overload", "neutral_joint",
        "condensation", "humidity_high", "pd_tracking", "arc_trip", "arc_integrity", "comms_lost",
    }
    assert an.theta_tau_estimated and 1000.0 < an.theta_tau_s < 3000.0  # gerçek tau 1800 s, veriden tahmin


@pytest.mark.parametrize(
    "key",
    ["healthy_baseline", "hot_summer", "heavy_balanced_load", "load_step_moderate", "sensor_glitch",
     "de_energised_maintenance", "pd_noise_bursts"],
)
def test_strict_quiet_controls_raise_not_even_a_warning(runs, key):
    _, an = runs(key)
    noisy = [(t.key, max(t.fused).name) for t in an.tracks if max(t.fused) > Severity.NORMAL]
    assert noisy == [], f"{key}: {noisy}"
