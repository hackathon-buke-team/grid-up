"""Twilio üzerinden gerçek kanaldan tek bir SMS gönderir (K4 §4.1 ikinci kanal kanıtı).

Kullanım: TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER,
TWILIO_TO_NUMBER ortam değişkenleri ayarlıyken
    python -m tools.send_real_sms_demo [SENARYO_ID]

Varsayılan senaryo A4 (ısıl kaçış — EMERGENCY). Gönderilen mesaj, gerçek
kural motorunun ürettiği kanıttan (şiddet, tetikleyen kanal aileleri) türer.
"""
from __future__ import annotations

import sys

from panogoz.notify.escalation import EscalationLadder
from panogoz.notify.sms_channel import TwilioSmsChannel
from panogoz.rules.engine import evaluate_connection
from panogoz.sim.scenarios import SCENARIOS_BY_ID


def main() -> None:
    scenario_id = sys.argv[1] if len(sys.argv) > 1 else "A4"
    scenario = SCENARIOS_BY_ID[scenario_id]
    records = scenario.run()
    result = evaluate_connection(records)

    if not result.alarm_ever_opened:
        print(f"{scenario_id} bir alarm üretmedi, gönderilecek gerçek kanıt yok.")
        return

    channel = TwilioSmsChannel.from_env()
    ladder = EscalationLadder(channel=channel)
    alarm = ladder.open_alarm(
        connection_id=f"{scenario.feeder_id}-L2 ({scenario.title})",
        severity=result.max_severity_reached,
        families=result.families_triggered,
    )
    print(f"SMS gönderildi: {alarm.alarm_id} [{alarm.severity}] onay token'i={alarm.approval_token}")


if __name__ == "__main__":
    main()
