"""Gerçek kanaldan tek bir KRİTİK/ACİL mesaj gönderir (K4 §4.1 kabul kanıtı).

Kullanım: TELEGRAM_BOT_TOKEN ve TELEGRAM_CHAT_ID ortam değişkenleri ayarlıyken
    python -m tools.send_real_alarm_demo [SENARYO_ID]

Varsayılan senaryo A4 (ısıl kaçış — EMERGENCY). Gönderilen alarm, gerçek
kural motorunun ürettiği kanıttan (şiddet, tetikleyen kanal aileleri) türer;
uydurma bir mesaj değildir.
"""
from __future__ import annotations

import os
import sys

from panogoz.notify.broadcast_channel import BroadcastChannel
from panogoz.notify.escalation import EscalationLadder
from panogoz.notify.telegram_channel import TelegramChannel
from panogoz.rules.engine import evaluate_connection
from panogoz.sim.scenarios import SCENARIOS_BY_ID


def build_channel() -> object:
    personal = TelegramChannel.from_env()
    group_chat_id = os.environ.get("TELEGRAM_GROUP_CHAT_ID")
    if not group_chat_id:
        return personal
    group = TelegramChannel(bot_token=personal.bot_token, chat_id=group_chat_id)
    return BroadcastChannel(channels=[personal, group])


def main() -> None:
    scenario_id = sys.argv[1] if len(sys.argv) > 1 else "A4"
    scenario = SCENARIOS_BY_ID[scenario_id]
    records = scenario.run()
    result = evaluate_connection(records)

    if not result.alarm_ever_opened:
        print(f"{scenario_id} bir alarm üretmedi, gönderilecek gerçek kanıt yok.")
        return

    channel = build_channel()
    ladder = EscalationLadder(channel=channel)
    alarm = ladder.open_alarm(
        connection_id=f"{scenario.feeder_id}-L2 ({scenario.title})",
        severity=result.max_severity_reached,
        families=result.families_triggered,
    )
    print(f"Gönderildi: {alarm.alarm_id} [{alarm.severity}] onay token'i={alarm.approval_token}")


if __name__ == "__main__":
    main()
