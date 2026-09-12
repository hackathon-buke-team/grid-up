"""Telegram'dan `/onayla <alarm_id> <token>` komutunu dinleyen uzun-polling süreci.

Kullanım: TELEGRAM_BOT_TOKEN ayarlıyken
    python -m tools.run_telegram_ack_listener

`tools.send_real_alarm_demo` ile aynı `data/alarm_state.json` dosyasını
paylaşır — önce bir alarm açılmalı (send_real_alarm_demo çalıştırılmalı),
sonra bu süreç ayakta kalıp gruba/kişiye yazılan onay komutunu işler ve
Telegram'a onay/ret cevabı yazar. Ctrl+C ile durur.
"""
from __future__ import annotations

import os

from panogoz.notify.console_channel import ConsoleChannel
from panogoz.notify.escalation import EscalationLadder
from panogoz.notify.telegram_ack_listener import TelegramAckListener

ALARM_STORE_PATH = "data/alarm_state.json"


def main() -> None:
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN ortam değişkeni eksik")

    ladder = EscalationLadder(channel=ConsoleChannel(), store_path=ALARM_STORE_PATH)
    listener = TelegramAckListener(bot_token=bot_token, ladder=ladder)

    print(f"Dinleniyor... açık alarm sayısı: {len(ladder.open_alarms)}")
    print("Telegram'a şu formatta yazın: /onayla <alarm_id> <token>")
    listener.run_forever()


if __name__ == "__main__":
    main()
