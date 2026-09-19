"""K4 4.1: uçtan uca alarm -> eskalasyon -> gerçek bildirim kanalı gösterimi.

Hat: senaryo (fizik modeli) -> dedektörler + bastırma/füzyon -> alarm motoru ->
eskalasyon -> Telegram (veya kuru çalıştırmada konsol). İlk sevk edilebilir (ALARM+)
alarm açılınca tek mesaj gider; isteğe bağlı olarak `ONAY <alarm> <belirteç>`
yanıtı beklenir ve alarm gerçekten onaylanır (iki yönlü).

Kullanım:
    python -m tools.send_real_alarm_demo                       # kuru çalıştırma, kimlik bilgisi gerekmez
    python -m tools.send_real_alarm_demo --scenario condensation_leak
    TELEGRAM_BOT_TOKEN=... TELEGRAM_CHAT_ID=... python -m tools.send_real_alarm_demo --send
    ... --send --wait-ack 120                                  # 120 sn yanıt bekle

`--send` olmadan hiçbir dış sisteme bağlanılmaz. Mesaj "DEMO" ön ekiyle gider ki
gerçek bir arıza sanılmasın.
"""
from __future__ import annotations

import argparse
import os
import sys
import time

from panogoz.notify.escalation import (
    ConsoleDispatcher,
    EscalationManager,
    OnCallSchedule,
    Recipient,
    RoutedDispatcher,
    Shift,
    TelegramAckPoller,
    telegram_route,
)
from panogoz.rules.alarms import AlarmEngine, AlarmState, tracks_now
from panogoz.rules.pipeline import analyze
from panogoz.sim.scenarios import SCENARIOS, generate


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", default="loose_bolt_abrupt", choices=sorted(SCENARIOS))
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--send", action="store_true", help="gerçek Telegram mesajı gönder")
    parser.add_argument("--wait-ack", type=int, default=0, metavar="SN", help="onay yanıtı için beklenecek saniye")
    args = parser.parse_args()

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if args.send and not (token and chat_id):
        print("HATA: --send için TELEGRAM_BOT_TOKEN ve TELEGRAM_CHAT_ID ortam değişkenleri gerekli.", file=sys.stderr)
        return 2

    if args.send:
        recipient = Recipient("Saha nöbetçisi", "saha nöbetçisi", "telegram", chat_id)
        dispatcher = RoutedDispatcher({"telegram": telegram_route(token)})
    else:
        recipient = Recipient("Saha nöbetçisi", "saha nöbetçisi", "console", "kuru-calistirma")
        console = ConsoleDispatcher()
        dispatcher = console

    manager = EscalationManager(OnCallSchedule([Shift(0, 24, ((recipient,),))]), dispatcher)
    scenario = SCENARIOS[args.scenario]
    print(f"Senaryo: {scenario.title} ({scenario.key}) tohum={args.seed}")
    data = generate(scenario, seed=args.seed)
    analysis = analyze(data)
    engine = AlarmEngine(f"DEMO-{scenario.key}", id_prefix="DEMO", seed=args.seed)

    paged = None
    for i, t in enumerate(data.t_s):
        for ev in engine.step(t, tracks_now(analysis, i)):
            alarm = engine.alarms[ev.alarm_id]
            manager.on_event(ev, alarm)
            if paged is None and alarm.needs_notification:
                paged = alarm
        if paged is not None:
            break
    if paged is None:
        print("Bu senaryoda sevk edilebilir (ALARM+) alarm oluşmadı.")
        return 1

    day = paged.opened_t_s / 86400.0
    print(f"ALARM açıldı: {paged.id} · {paged.label} · gün {day:.2f} · şiddet {paged.severity.name}")
    for m in manager.log:
        state = m.status.upper()
        print(f"  [{state}] -> {m.role} ({m.route}) :: {m.text.splitlines()[0] if m.text else ''}")
    if not args.send:
        print("\n--- kuru çalıştırma: gönderilecek mesajın tamamı ---")
        print(console.delivered[0][1] if console.delivered else "(mesaj yok)")
        print("\nGerçek Telegram mesajı için --send ve TELEGRAM_* değişkenleri gerekir.")
        return 0

    failed = [m for m in manager.log if m.status == "failed"]
    if failed:
        print(f"HATA: teslimat başarısız: {failed[0].error}", file=sys.stderr)
        return 3
    print("Gerçek Telegram mesajı gönderildi.")

    if args.wait_ack:
        poller = TelegramAckPoller(token, {chat_id})
        print(f"Onay bekleniyor ({args.wait_ack} sn): Telegram'da  ONAY {paged.id} {paged.ack_token}  yazın...")
        deadline = time.monotonic() + args.wait_ack
        while time.monotonic() < deadline and paged.state is AlarmState.OPEN:
            poller.poll(lambda a, tk, by: engine.ack(a, tk, by, paged.opened_t_s + 60.0))
            time.sleep(3)
        if paged.state is AlarmState.ACKED:
            print(f"ONAYLANDI: {paged.acked_by} alarmı üstlendi (kimlik Telegram'dan alındı).")
        else:
            print("Onay gelmedi; alarm açık kaldı.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
