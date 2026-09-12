from panogoz.notify.console_channel import ConsoleChannel
from panogoz.notify.escalation import AlarmState, EscalationLadder, generate_approval_token


def test_approval_token_is_four_digits():
    for _ in range(50):
        token = generate_approval_token()
        assert len(token) == 4
        assert token.isdigit()


def test_open_alarm_sends_one_notification_with_token():
    channel = ConsoleChannel()
    ladder = EscalationLadder(channel=channel)
    alarm = ladder.open_alarm(connection_id="F02-L2", severity="ALARM", families={"thermal"}, now=0.0)
    assert len(channel.sent) == 1
    assert alarm.approval_token in channel.sent[0]
    assert alarm.state == AlarmState.OPEN


def test_tick_repeats_notification_after_interval_elapses():
    channel = ConsoleChannel()
    ladder = EscalationLadder(channel=channel)
    ladder.open_alarm(connection_id="F02-L2", severity="EMERGENCY", families={"arc_trip"}, now=0.0)
    ladder.tick(now=60.0)
    assert len(channel.sent) == 1
    ladder.tick(now=5 * 60 + 1)
    assert len(channel.sent) == 2


def test_acknowledge_requires_matching_token():
    channel = ConsoleChannel()
    ladder = EscalationLadder(channel=channel)
    alarm = ladder.open_alarm(connection_id="F02-L2", severity="ALARM", families={"thermal"}, now=0.0)
    assert ladder.acknowledge(alarm.alarm_id, token="0000", person="nöbetçi") is False
    assert ladder.acknowledge(alarm.alarm_id, token=alarm.approval_token, person="nöbetçi") is True
    assert alarm.state == AlarmState.ACKED
    assert alarm.acknowledged_by == "nöbetçi"


def test_acked_alarm_is_not_repeated_by_tick():
    channel = ConsoleChannel()
    ladder = EscalationLadder(channel=channel)
    alarm = ladder.open_alarm(connection_id="F02-L2", severity="EMERGENCY", families={"arc_trip"}, now=0.0)
    ladder.acknowledge(alarm.alarm_id, token=alarm.approval_token, person="nöbetçi")
    ladder.tick(now=10_000)
    assert len(channel.sent) == 1


def test_storm_limit_caps_notifications_per_hour():
    channel = ConsoleChannel()
    ladder = EscalationLadder(channel=channel)
    for i in range(8):
        ladder.open_alarm(connection_id=f"F0{i}-L2", severity="ALARM", families={"thermal"}, now=float(i))
    assert len(channel.sent) == 5
    assert len(ladder.storm_digest) == 3


def test_snooze_and_close_change_state():
    channel = ConsoleChannel()
    ladder = EscalationLadder(channel=channel)
    alarm = ladder.open_alarm(connection_id="F02-L2", severity="ALARM", families={"thermal"}, now=0.0)
    assert ladder.snooze(alarm.alarm_id, until=3600.0, person="vardiya-1") is True
    assert alarm.state == AlarmState.SNOOZED
    assert ladder.close(alarm.alarm_id) is True
    assert alarm.alarm_id not in ladder.open_alarms


def test_shift_handover_summary_lists_open_alarms():
    channel = ConsoleChannel()
    ladder = EscalationLadder(channel=channel)
    ladder.open_alarm(connection_id="F02-L2", severity="ALARM", families={"thermal"}, now=0.0)
    summary = ladder.shift_handover_summary()
    assert "Açık alarm sayısı: 1" in summary
    assert "F02-L2" in summary
