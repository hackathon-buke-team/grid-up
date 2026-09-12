"""Gerçek CT verisi + gevşek cıvata arıza simülasyonu üzerinden uçtan uca kanıt.

Boru hattı: gerçek L1 akımı (İstenen Veriler.xlsx) -> üç fazlı ısıl simülasyon
(L2'de arıza) -> θ metriği -> kural motoru (eşik+debounce) -> Telegram bildirimi.

Kullanım: TELEGRAM_BOT_TOKEN ve TELEGRAM_CHAT_ID ortam değişkenleri ayarlıyken
    python -m tools.send_real_alarm_demo
"""
from __future__ import annotations

from panogoz.contracts.channels import Phase
from panogoz.detector.theta import compute_theta_series
from panogoz.notify.alarm_notifier import AlarmNotifier
from panogoz.notify.telegram_channel import TelegramChannel
from panogoz.rules.engine import Severity, evaluate_severity_series
from panogoz.sim.ct_data import load_real_l1_series
from panogoz.sim.synthetic import simulate_three_phase_thermal

RATED_CURRENT_A = 250.0
CONNECTION_ID = "F02-L2 (gevşek cıvatalı bağlantı - AG pano)"


def main() -> None:
    l1 = load_real_l1_series()
    fault_start_s = l1[len(l1) // 2].t_s
    three_phase = simulate_three_phase_thermal(l1, fault_phase=Phase.L2, fault_start_s=fault_start_s)
    theta_series = compute_theta_series(three_phase, rated_current_a=RATED_CURRENT_A)
    events = evaluate_severity_series(theta_series[Phase.L2])

    channel = TelegramChannel.from_env()
    notifier = AlarmNotifier(channel=channel, connection_id=CONNECTION_ID)

    sent_any = False
    for event, theta_sample in zip(events, theta_series[Phase.L2]):
        if notifier.process(event, theta=theta_sample.theta):
            sent_any = True
            print(f"t={event.t_s/3600:.1f}sa -> {event.severity.name} (θ={theta_sample.theta:.1f}) gönderildi")

    max_severity = max(e.severity for e in events)
    if not sent_any:
        print(f"Hiç bildirim gönderilmedi (en yüksek şiddet: {max_severity.name})")
    else:
        print(f"Tamamlandı. En yüksek şiddet: {max_severity.name}")


if __name__ == "__main__":
    main()
