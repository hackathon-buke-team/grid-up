"""K4 4.2: alarm yaşam döngüsü -- aç/yükselt/temizle/onayla/otomatik kapan/sessize al."""
import pytest

from panogoz.contracts.channels import Phase
from panogoz.rules.alarms import (
    AUTO_CLOSE_S,
    AckError,
    AlarmEngine,
    AlarmState,
    EventType,
    TrackNow,
    build_alarm_log,
)
from panogoz.rules.engine import Severity
from panogoz.rules.pipeline import SPECS, analyze
from panogoz.sim.scenarios import SCENARIOS, generate

H = 3600.0
D = 86400.0
BOLT = SPECS["loose_bolt"]


def tn(sev, spec=BOLT, phase=Phase.L2, score=None):
    return TrackNow(spec, phase, sev, score)


def engine():
    return AlarmEngine("F01", id_prefix="F01", seed=1)


def only(e):
    return next(iter(e.alarms.values()))


def test_warning_opens_alarm_and_only_alarm_level_needs_notification():
    e = engine()
    ev = e.step(0.0, [tn(Severity.WARNING)])
    assert [x.type for x in ev] == [EventType.OPENED]
    alarm = only(e)
    assert alarm.state is AlarmState.OPEN and not alarm.needs_notification
    e.step(900.0, [tn(Severity.ALARM)])
    assert alarm.needs_notification and alarm.severity is Severity.ALARM


def test_normal_severity_never_opens_alarm():
    e = engine()
    assert e.step(0.0, [tn(Severity.NORMAL)]) == []
    assert e.alarms == {}


def test_escalation_updates_severity_and_peak_but_keeps_single_alarm():
    e = engine()
    e.step(0, [tn(Severity.WARNING)])
    e.step(900, [tn(Severity.CRITICAL, score=70.0)])
    e.step(1800, [tn(Severity.ALARM)])
    assert len(e.alarms) == 1
    a = only(e)
    assert a.severity is Severity.ALARM and a.peak is Severity.CRITICAL and a.peak_score == 70.0
    assert [h[1] for h in a.history] == ["opened", "escalated", "deescalated"]


def test_clearing_waits_for_ack_and_auto_closes_after_seven_days():
    e = engine()
    e.step(0, [tn(Severity.ALARM)])
    e.step(900, [tn(Severity.NORMAL)])
    a = only(e)
    assert a.state is AlarmState.CLEARED  # otomatik kapanmaz
    e.step(900 + AUTO_CLOSE_S - 1, [tn(Severity.NORMAL)])
    assert a.state is AlarmState.CLEARED
    ev = e.step(900 + AUTO_CLOSE_S, [tn(Severity.NORMAL)])
    assert a.state is AlarmState.CLOSED and a.close_reason == "diger"
    assert ev[0].detail == "auto_7d"


def test_ack_requires_identity_and_correct_token():
    e = engine()
    e.step(0, [tn(Severity.ALARM)])
    a = only(e)
    wrong = "0000" if a.ack_token != "0000" else "1111"
    with pytest.raises(AckError, match="belirteci hatalı"):
        e.ack(a.id, wrong, "Ayşe", 10.0)
    with pytest.raises(AckError, match="kimlik"):
        e.ack(a.id, a.ack_token, "  ", 10.0)
    e.ack(a.id, a.ack_token, "Ayşe Yılmaz", 10.0, note="ekip yolda")
    assert a.state is AlarmState.ACKED and a.acked_by == "Ayşe Yılmaz" and a.ack_note == "ekip yolda"
    with pytest.raises(AckError, match="zaten onaylı"):
        e.ack(a.id, a.ack_token, "Ayşe", 20.0)


def test_ack_token_is_four_digits_and_deterministic_per_alarm():
    tokens = []
    for _ in range(2):
        e = engine()
        e.step(0, [tn(Severity.ALARM)])
        tokens.append(only(e).ack_token)
    assert tokens[0] == tokens[1] and len(tokens[0]) == 4 and tokens[0].isdigit()


def test_acked_alarm_closes_immediately_when_signal_returns_to_normal():
    e = engine()
    e.step(0, [tn(Severity.ALARM)])
    a = only(e)
    e.ack(a.id, a.ack_token, "Ali", 5.0)
    ev = e.step(900, [tn(Severity.NORMAL)])
    assert a.state is AlarmState.CLOSED and a.close_reason == "sahada_giderildi"
    assert ev[0].detail == "cleared_after_ack"


def test_ack_after_clear_closes_the_alarm():
    e = engine()
    e.step(0, [tn(Severity.ALARM)])
    e.step(900, [tn(Severity.NORMAL)])
    a = only(e)
    e.ack(a.id, a.ack_token, "Veli", 1000.0)
    assert a.state is AlarmState.CLOSED


def test_worse_severity_invalidates_earlier_ack():
    e = engine()
    e.step(0, [tn(Severity.ALARM)])
    a = only(e)
    e.ack(a.id, a.ack_token, "Ali", 5.0)
    assert a.state is AlarmState.ACKED
    e.step(900, [tn(Severity.CRITICAL)])
    assert a.state is AlarmState.OPEN  # daha kötü duruma verilmiş onay eski durum içindi
    assert "ack_invalidated" in [h[1] for h in a.history]


def test_same_or_lower_severity_keeps_ack():
    e = engine()
    e.step(0, [tn(Severity.ALARM)])
    a = only(e)
    e.ack(a.id, a.ack_token, "Ali", 5.0)
    e.step(900, [tn(Severity.ALARM)])
    e.step(1800, [tn(Severity.WARNING)])
    assert a.state is AlarmState.ACKED


def test_flapping_within_window_reopens_same_alarm_instead_of_new_one():
    e = engine()
    e.step(0, [tn(Severity.ALARM)])
    e.step(900, [tn(Severity.NORMAL)])
    ev = e.step(1800, [tn(Severity.ALARM)])
    assert len(e.alarms) == 1 and ev[0].type is EventType.REOPENED
    a = only(e)
    assert a.state is AlarmState.OPEN and a.flaps == 1


def test_reappearance_after_window_is_a_new_alarm_and_old_one_stays_pending():
    e = engine()
    e.step(0, [tn(Severity.ALARM)])
    e.step(900, [tn(Severity.NORMAL)])
    e.step(900 + 7 * H, [tn(Severity.ALARM)])
    assert len(e.alarms) == 2
    assert sorted(a.state.value for a in e.alarms.values()) == ["cleared", "open"]


def test_latching_event_alarm_survives_signal_reset_until_acknowledged():
    e = engine()
    trip = SPECS["arc_trip"]
    e.step(0, [tn(Severity.CRITICAL, trip, None)])
    e.step(900, [tn(Severity.NORMAL, trip, None)])
    a = only(e)
    assert a.state is AlarmState.OPEN and a.latching  # sinyal döndü ama alarm açık
    e.ack(a.id, a.ack_token, "Nöbetçi", 1000.0)
    assert a.state is AlarmState.CLOSED


def test_manual_close_requires_valid_reason_and_identity():
    e = engine()
    e.step(0, [tn(Severity.ALARM)])
    a = only(e)
    with pytest.raises(ValueError, match="gerekçesi"):
        e.close(a.id, "canım_istedi", "Ali", 5.0)
    with pytest.raises(ValueError, match="kimlik"):
        e.close(a.id, "yanlis_alarm", "", 5.0)
    e.close(a.id, "yanlis_alarm", "Ali", 5.0)
    assert a.state is AlarmState.CLOSED and a.close_reason == "yanlis_alarm" and a.closed_by == "Ali"
    with pytest.raises(ValueError, match="zaten kapalı"):
        e.close(a.id, "yanlis_alarm", "Ali", 6.0)


def test_mute_suppresses_below_critical_but_critical_always_passes():
    e = engine()
    e.mute("loose_bolt", until_t_s=10 * H, by="Ali", reason="bakım penceresi")
    assert e.step(0, [tn(Severity.ALARM)]) == []
    assert e.alarms == {} and e.suppressed[0].type is EventType.MUTED
    ev = e.step(900, [tn(Severity.CRITICAL)])
    assert ev[0].type is EventType.OPENED  # KRİTİK sessize alma ile bastırılamaz


def test_mute_expires_and_requires_reason():
    e = engine()
    with pytest.raises(ValueError):
        e.mute("loose_bolt", until_t_s=H, by="Ali", reason=" ")
    e.mute("loose_bolt", until_t_s=H, by="Ali", reason="bakım")
    e.step(0.5 * H, [tn(Severity.ALARM)])
    assert e.alarms == {}
    e.step(1.5 * H, [tn(Severity.ALARM)])
    assert len(e.alarms) == 1


def test_stronger_track_absorbs_weaker_trend_alarm_for_same_phase():
    e = engine()
    trend = SPECS["loose_bolt_trend"]
    e.step(0, [tn(Severity.WARNING, trend, Phase.L2)])
    trend_alarm = only(e)
    e.step(900, [tn(Severity.WARNING, trend, Phase.L2), tn(Severity.ALARM, BOLT, Phase.L2)])
    assert trend_alarm.state is AlarmState.CLOSED and "birleştirildi" in trend_alarm.closed_by
    open_ones = [a for a in e.alarms.values() if a.is_active]
    assert len(open_ones) == 1 and open_ones[0].kind == "loose_bolt"
    e2 = engine()  # farklı faz birleştirilmez
    e2.step(0, [tn(Severity.WARNING, trend, Phase.L1), tn(Severity.ALARM, BOLT, Phase.L2)])
    assert sum(1 for a in e2.alarms.values() if a.is_active) == 2


def test_unknown_alarm_id_raises_key_error():
    with pytest.raises(KeyError):
        engine().ack("yok", "0000", "Ali", 0.0)


def test_real_scenario_produces_one_dispatchable_alarm_on_the_faulty_phase_only():
    data = generate(SCENARIOS["loose_bolt_abrupt"], seed=1)
    log = build_alarm_log("F02", analyze(data), id_prefix="F02")
    dispatchable = [a for a in log.alarms.values() if a.peak >= Severity.ALARM]
    assert len(dispatchable) == 1
    a = dispatchable[0]
    assert a.kind == "loose_bolt" and a.phase == "L2"
    assert a.opened_t_s >= data.truth.onset_t_s  # onset'ten önce alarm yok
    assert a.state is AlarmState.OPEN  # arıza sürüyor, kimse onaylamadı


def test_negative_control_yields_no_alarm_records_in_lifecycle_log():
    data = generate(SCENARIOS["hot_summer"], seed=1)
    log = build_alarm_log("F09", analyze(data), id_prefix="F09")
    assert log.alarms == {}


def test_until_parameter_stops_the_replay_at_the_requested_time():
    data = generate(SCENARIOS["loose_bolt_abrupt"], seed=1)
    early = build_alarm_log("F02", analyze(data), id_prefix="F02", until_t_s=data.truth.onset_t_s - D)
    assert early.alarms == {}
