"""Gerçek kanaldan tek bir KRİTİK/ACİL mesaj gönderir (K4 §4.1 kabul kanıtı).

Kullanım: TELEGRAM_BOT_TOKEN ve TELEGRAM_CHAT_ID ortam değişkenleri ayarlıyken
    python -m tools.send_real_alarm_demo [SENARYO_ID]

TELEGRAM_GROUP_CHAT_ID ayarlıysa gruba da yayın yapılır; TWILIO_ACCOUNT_SID
(+ TWILIO_AUTH_TOKEN/TWILIO_FROM_NUMBER/TWILIO_TO_NUMBER) ayarlıysa aynı
alarm SMS ile de gönderilir. Açılan alarm `data/alarm_state.json`'a yazılır;
`python -m tools.run_telegram_ack_listener` bu dosyayı paylaşarak Telegram'a
yazılan `/onayla <alarm_id> <token>` komutunu gerçekten işleyebilir.

Varsayılan senaryo A4 (ısıl kaçış — EMERGENCY). Gönderilen alarm, gerçek
kural motorunun ürettiği kanıttan (şiddet, tetikleyen kanal aileleri) türer;
uydurma bir mesaj değildir.
"""
from __future__ import annotations

import os
import sys

from panogoz.notify.broadcast_channel import BroadcastChannel
from panogoz.notify.escalation import EscalationLadder
from panogoz.notify.sms_channel import TwilioSmsChannel
from panogoz.notify.telegram_channel import TelegramChannel
from panogoz.rules.engine import evaluate_connection
from panogoz.sim.scenarios import SCENARIOS_BY_ID

ALARM_STORE_PATH = "data/alarm_state.json"


def build_channel() -> object:
    channels = [TelegramChannel.from_env()]
    group_chat_id = os.environ.get("TELEGRAM_GROUP_CHAT_ID")
    if group_chat_id:
        channels.append(TelegramChannel(bot_token=channels[0].bot_token, chat_id=group_chat_id))
    if os.environ.get("TWILIO_ACCOUNT_SID"):
        channels.append(TwilioSmsChannel.from_env())
    return channels[0] if len(channels) == 1 else BroadcastChannel(channels=channels)


def main() -> None:
    scenario_id = sys.argv[1] if len(sys.argv) > 1 else "A4"
    scenario = SCENARIOS_BY_ID[scenario_id]
    records = scenario.run()
    result = evaluate_connection(records)

    if not result.alarm_ever_opened:
        print(f"{scenario_id} bir alarm üretmedi, gönderilecek gerçek kanıt yok.")
        return

    channel = build_channel()
    ladder = EscalationLadder(channel=channel, store_path=ALARM_STORE_PATH)
    alarm = ladder.open_alarm(
        connection_id=f"{scenario.feeder_id}-L2 ({scenario.title})",
        severity=result.max_severity_reached,
        families=result.families_triggered,
    )
    print(f"Gönderildi: {alarm.alarm_id} [{alarm.severity}] onay token'i={alarm.approval_token}")


if __name__ == "__main__":
    main()
