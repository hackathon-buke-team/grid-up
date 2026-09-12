import pytest

from panogoz.notify.broadcast_channel import BroadcastChannel
from panogoz.notify.console_channel import ConsoleChannel
from panogoz.notify.escalation import AlarmState, EscalationLadder, generate_approval_token
from panogoz.notify.sms_channel import TwilioSmsChannel
from panogoz.notify.telegram_ack_listener import TelegramAckListener, parse_ack_command


def test_broadcast_channel_sends_to_all_targets():
    personal = ConsoleChannel()
    group = ConsoleChannel()
    broadcast = BroadcastChannel(channels=[personal, group])
    broadcast.send("test mesaji")
    assert personal.sent == ["test mesaji"]
    assert group.sent == ["test mesaji"]


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


def test_escalation_ladder_persists_and_reloads_open_alarms(tmp_path):
    store_path = str(tmp_path / "alarm_state.json")
    channel = ConsoleChannel()
    ladder = EscalationLadder(channel=channel, store_path=store_path)
    alarm = ladder.open_alarm(connection_id="F02-L2", severity="EMERGENCY", families={"arc_trip"}, now=0.0)

    reloaded = EscalationLadder(channel=ConsoleChannel(), store_path=store_path)
    assert alarm.alarm_id in reloaded.open_alarms
    restored = reloaded.open_alarms[alarm.alarm_id]
    assert restored.approval_token == alarm.approval_token
    assert restored.families == {"arc_trip"}
    assert restored.state == AlarmState.OPEN


def test_ack_persisted_across_reload(tmp_path):
    store_path = str(tmp_path / "alarm_state.json")
    ladder = EscalationLadder(channel=ConsoleChannel(), store_path=store_path)
    alarm = ladder.open_alarm(connection_id="F02-L2", severity="ALARM", families={"thermal"}, now=0.0)

    reloaded = EscalationLadder(channel=ConsoleChannel(), store_path=store_path)
    assert reloaded.acknowledge(alarm.alarm_id, token=alarm.approval_token, person="nöbetçi") is True

    reloaded_again = EscalationLadder(channel=ConsoleChannel(), store_path=store_path)
    assert reloaded_again.open_alarms[alarm.alarm_id].state == AlarmState.ACKED


def test_parse_ack_command_extracts_alarm_id_and_token():
    assert parse_ack_command("/onayla F02-L2-123 4821") == ("F02-L2-123", "4821")
    assert parse_ack_command("/onayla@panogoz_bot F02-L2-123 4821") == ("F02-L2-123", "4821")
    assert parse_ack_command("merhaba") is None
    assert parse_ack_command("/onayla eksik-token") is None


def test_ack_listener_process_update_acknowledges_matching_token():
    ladder = EscalationLadder(channel=ConsoleChannel())
    alarm = ladder.open_alarm(connection_id="F02-L2", severity="ALARM", families={"thermal"}, now=0.0)

    listener = TelegramAckListener(bot_token="dummy-token", ladder=ladder)
    replies = []
    listener._reply = lambda chat_id, text: replies.append((chat_id, text))

    update = {
        "update_id": 1,
        "message": {
            "text": f"/onayla {alarm.alarm_id} {alarm.approval_token}",
            "chat": {"id": 555},
            "from": {"username": "mert"},
        },
    }
    handled = listener.process_update(update)

    assert handled is True
    assert alarm.state == AlarmState.ACKED
    assert alarm.acknowledged_by == "mert"
    assert replies == [(555, f"✅ {alarm.alarm_id} onaylandı — mert")]


def test_ack_listener_process_update_rejects_wrong_token():
    ladder = EscalationLadder(channel=ConsoleChannel())
    alarm = ladder.open_alarm(connection_id="F02-L2", severity="ALARM", families={"thermal"}, now=0.0)

    listener = TelegramAckListener(bot_token="dummy-token", ladder=ladder)
    replies = []
    listener._reply = lambda chat_id, text: replies.append((chat_id, text))

    update = {
        "update_id": 1,
        "message": {"text": f"/onayla {alarm.alarm_id} 0000", "chat": {"id": 555}, "from": {}},
    }
    handled = listener.process_update(update)

    assert handled is True
    assert alarm.state == AlarmState.OPEN
    assert replies[0][1].startswith("❌")


def test_ack_listener_ignores_unrelated_messages():
    ladder = EscalationLadder(channel=ConsoleChannel())
    listener = TelegramAckListener(bot_token="dummy-token", ladder=ladder)
    assert listener.process_update({"update_id": 1, "message": {"text": "merhaba", "chat": {"id": 1}}}) is False


def test_twilio_channel_requires_all_env_vars(monkeypatch):
    monkeypatch.delenv("TWILIO_ACCOUNT_SID", raising=False)
    monkeypatch.delenv("TWILIO_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("TWILIO_FROM_NUMBER", raising=False)
    monkeypatch.delenv("TWILIO_TO_NUMBER", raising=False)
    with pytest.raises(RuntimeError):
        TwilioSmsChannel.from_env()


def test_twilio_channel_builds_expected_request(monkeypatch):
    calls = []

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"sid": "SM123"}

    def fake_post(url, data, auth, timeout):
        calls.append((url, data, auth, timeout))
        return FakeResponse()

    monkeypatch.setattr("panogoz.notify.sms_channel.requests.post", fake_post)
    channel = TwilioSmsChannel(
        account_sid="ACxxx", auth_token="secret", from_number="+15550001111", to_number="+15550002222"
    )
    result = channel.send("test mesaji")

    assert result == {"sid": "SM123"}
    url, data, auth, timeout = calls[0]
    assert url == "https://api.twilio.com/2010-04-01/Accounts/ACxxx/Messages.json"
    assert data == {"From": "+15550001111", "To": "+15550002222", "Body": "test mesaji"}
    assert auth == ("ACxxx", "secret")
