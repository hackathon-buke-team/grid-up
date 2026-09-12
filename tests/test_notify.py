from panogoz.notify.alarm_notifier import AlarmNotifier
from panogoz.notify.console_channel import ConsoleChannel
from panogoz.rules.engine import Severity, SeverityEvent


def test_notifies_once_on_first_escalation():
    channel = ConsoleChannel()
    notifier = AlarmNotifier(channel=channel, connection_id="F02-L2")

    notified = notifier.process(SeverityEvent(t_s=0.0, severity=Severity.WARNING), theta=18.0)

    assert notified is True
    assert len(channel.sent) == 1
    assert "UYARI" in channel.sent[0]
    assert "F02-L2" in channel.sent[0]


def test_does_not_repeat_same_severity():
    channel = ConsoleChannel()
    notifier = AlarmNotifier(channel=channel, connection_id="F02-L2")

    notifier.process(SeverityEvent(t_s=0.0, severity=Severity.ALARM), theta=35.0)
    notifier.process(SeverityEvent(t_s=900.0, severity=Severity.ALARM), theta=36.0)

    assert len(channel.sent) == 1


def test_notifies_again_on_further_escalation():
    channel = ConsoleChannel()
    notifier = AlarmNotifier(channel=channel, connection_id="F02-L2")

    notifier.process(SeverityEvent(t_s=0.0, severity=Severity.WARNING), theta=18.0)
    notifier.process(SeverityEvent(t_s=900.0, severity=Severity.CRITICAL), theta=65.0)

    assert len(channel.sent) == 2
    assert "KRİTİK" in channel.sent[1]


def test_resets_after_returning_to_normal():
    channel = ConsoleChannel()
    notifier = AlarmNotifier(channel=channel, connection_id="F02-L2")

    notifier.process(SeverityEvent(t_s=0.0, severity=Severity.ALARM), theta=35.0)
    notifier.process(SeverityEvent(t_s=900.0, severity=Severity.NORMAL), theta=2.0)
    notifier.process(SeverityEvent(t_s=1800.0, severity=Severity.ALARM), theta=32.0)

    assert len(channel.sent) == 2
