"""K4 4.2: eskalasyon -- rota, onay belirteci, tekrar, fırtına sınırı, sessize alma, nöbet devri."""
import pytest

from panogoz.contracts.channels import Phase
from panogoz.notify.escalation import (
    ConsoleDispatcher,
    EscalationManager,
    EscalationPolicy,
    OnCallSchedule,
    Recipient,
    RoutedDispatcher,
    Shift,
    TelegramAckPoller,
    parse_ack,
)
from panogoz.rules.alarms import AlarmEngine, AlarmState, TrackNow, build_alarm_log
from panogoz.rules.engine import Severity
from panogoz.rules.pipeline import SPECS, analyze
from panogoz.sim.scenarios import SCENARIOS, generate

M = 60.0
H = 3600.0

AYSE = Recipient("Ayşe", "saha nöbetçisi", "console", "1001")
MEHMET = Recipient("Mehmet", "bölge sorumlusu", "console", "1002")
ZEYNEP = Recipient("Zeynep", "operasyon müdürü", "console", "1003")
KEMAL = Recipient("Kemal", "gece nöbetçisi", "console", "2001")
NUR = Recipient("Nur", "gece bölge sorumlusu", "console", "2002")
DAY_TIERS = ((AYSE,), (MEHMET,), (ZEYNEP,))
NIGHT_TIERS = ((KEMAL,), (NUR,), (ZEYNEP,))
BOLT = SPECS["loose_bolt"]
NOON = 12 * H  # gündüz vardiyası


def schedule():
    return OnCallSchedule([Shift(8, 20, DAY_TIERS), Shift(20, 8, NIGHT_TIERS)])


def setup(policy=None):
    disp = ConsoleDispatcher()
    mgr = EscalationManager(schedule(), disp, policy)
    eng = AlarmEngine("F02", id_prefix="F02", seed=1)
    return disp, mgr, eng


def feed(mgr, eng, t, sev, score=45.0, spec=BOLT, phase=Phase.L2):
    events = eng.step(t, [TrackNow(spec, phase, sev, score)])
    for ev in events:
        mgr.on_event(ev, eng.alarms[ev.alarm_id])
    return events


def to_names(disp):
    return [r.name for r, _ in disp.delivered]


def test_warning_is_console_only_no_page_sent():
    disp, mgr, eng = setup()
    feed(mgr, eng, NOON, Severity.WARNING)
    assert disp.delivered == [] and mgr.log == []


def test_alarm_pages_only_first_tier_with_ack_instruction_and_no_raw_data():
    disp, mgr, eng = setup()
    feed(mgr, eng, NOON, Severity.ALARM, score=45.2)
    assert to_names(disp) == ["Ayşe"]
    text = disp.delivered[0][1]
    alarm = next(iter(eng.alarms.values()))
    assert "[ALARM] F02 faz L2" in text and "Gevşek cıvatalı bağlantı" in text and "45.2" in text
    assert f"ONAY {alarm.id} {alarm.ack_token}" in text
    assert "°C" not in text and "mA" not in text  # ham sensör verisi gitmez


def test_critical_pages_first_two_tiers_at_once():
    disp, mgr, eng = setup()
    feed(mgr, eng, NOON, Severity.CRITICAL, score=70.0)
    assert to_names(disp) == ["Ayşe", "Mehmet"]
    assert all("[KRİTİK]" in t for _, t in disp.delivered)


def test_unacknowledged_alarm_gets_reminders_then_escalates_to_next_tier():
    disp, mgr, eng = setup()
    feed(mgr, eng, NOON, Severity.ALARM)
    alarms = list(eng.alarms.values())
    mgr.tick(NOON + 14 * M, alarms)
    assert len(disp.delivered) == 1  # henüz erken
    mgr.tick(NOON + 15 * M, alarms)
    assert to_names(disp) == ["Ayşe", "Ayşe"] and "HATIRLATMA 1/6" in disp.delivered[-1][1]
    mgr.tick(NOON + 30 * M, alarms)  # onay zaman aşımı: üst kademe
    assert to_names(disp)[-1] == "Mehmet" and "ESKALASYON" in disp.delivered[-1][1]
    mgr.tick(NOON + 60 * M, alarms)
    assert to_names(disp)[-1] == "Zeynep"
    kinds = [m.kind for m in mgr.sent()]
    assert kinds[0] == "first" and "reminder" in kinds and kinds.count("escalation") == 2


def test_ack_stops_reminders_and_notifies_everyone_who_was_paged():
    disp, mgr, eng = setup()
    feed(mgr, eng, NOON, Severity.CRITICAL)
    alarm = next(iter(eng.alarms.values()))
    ack_t = NOON + 2 * M
    eng.ack(alarm.id, alarm.ack_token, "Ayşe Yılmaz", ack_t)
    for ev in eng.events[-1:]:
        mgr.on_event(ev, alarm)
    confirmations = [m for m in mgr.sent() if m.kind == "ack"]
    assert {m.recipient for m in confirmations} == {"Ayşe", "Mehmet"}
    assert "Ayşe Yılmaz" in confirmations[0].text
    before = len(disp.delivered)
    mgr.tick(NOON + 2 * H, list(eng.alarms.values()))
    assert len(disp.delivered) == before  # onaydan sonra hatırlatma/eskalasyon yok


def test_reminders_are_capped_at_max_repeats():
    policy = EscalationPolicy(ack_timeout_s={Severity.ALARM: 10**9, Severity.CRITICAL: 10**9}, max_repeats=3)
    disp, mgr, eng = setup(policy)
    feed(mgr, eng, NOON, Severity.ALARM)
    alarms = list(eng.alarms.values())
    for k in range(1, 20):
        mgr.tick(NOON + k * 15 * M, alarms)
    assert sum(1 for m in mgr.sent() if m.kind == "reminder") == 3


def test_severity_increase_repages_and_adds_tiers():
    disp, mgr, eng = setup()
    feed(mgr, eng, NOON, Severity.ALARM)
    assert to_names(disp) == ["Ayşe"]
    feed(mgr, eng, NOON + 10 * M, Severity.CRITICAL, score=75.0)
    assert to_names(disp)[1:] == ["Ayşe", "Mehmet"]
    assert "ŞİDDET YÜKSELDİ" in disp.delivered[1][1] and "[KRİTİK]" in disp.delivered[1][1]


def test_rate_limit_suppresses_storm_and_sends_single_digest_later():
    policy = EscalationPolicy(rate_limit_per_hour=2, repeat_s={Severity.ALARM: 60.0, Severity.CRITICAL: 60.0}, max_repeats=50,
                              ack_timeout_s={Severity.ALARM: 10**9, Severity.CRITICAL: 10**9})
    disp, mgr, eng = setup(policy)
    feed(mgr, eng, NOON, Severity.ALARM)
    alarms = list(eng.alarms.values())
    for k in range(1, 8):
        mgr.tick(NOON + k * 60.0, alarms)
    assert len(mgr.sent()) == 2  # sınır: saatte 2
    assert len(mgr.sent(status="rate_limited")) >= 5
    mgr.tick(NOON + H + 2 * M, [])  # pencere boşaldı, alarm yok: yalnız özet
    digests = [m for m in mgr.sent() if m.kind == "digest"]
    assert len(digests) == 1 and "bastırıldı" in digests[0].text


def test_critical_first_page_bypasses_rate_limit():
    policy = EscalationPolicy(rate_limit_per_hour=0)
    disp, mgr, eng = setup(policy)
    feed(mgr, eng, NOON, Severity.CRITICAL)
    assert to_names(disp) == ["Ayşe", "Mehmet"]


def test_silenced_person_is_skipped_and_next_tier_is_paged_immediately():
    disp, mgr, eng = setup()
    mgr.silence("Ayşe", until_t_s=NOON + H, by="Zeynep")
    feed(mgr, eng, NOON, Severity.ALARM)
    assert to_names(disp) == ["Mehmet"]
    assert [m.status for m in mgr.log][:1] == ["silenced"]


def test_critical_alarm_pages_even_a_silenced_person():
    disp, mgr, eng = setup()
    mgr.silence("Ayşe", until_t_s=NOON + H, by="Zeynep")
    feed(mgr, eng, NOON, Severity.CRITICAL)
    assert "Ayşe" in to_names(disp)
    with pytest.raises(ValueError):
        mgr.silence("Ayşe", until_t_s=1.0, by=" ")


def test_delivery_failure_is_recorded_and_next_tier_is_paged_immediately():
    disp, mgr, eng = setup()
    disp.fail_for = {"Ayşe"}
    feed(mgr, eng, NOON, Severity.ALARM)
    statuses = [(m.recipient, m.status) for m in mgr.log]
    assert statuses == [("Ayşe", "failed"), ("Mehmet", "sent")]
    assert mgr.log[0].error == "kanal erişilemiyor"


def test_shift_change_pages_new_on_call_with_handover_prefix():
    disp, mgr, eng = setup()
    feed(mgr, eng, 19.9 * H, Severity.ALARM)  # gündüz nöbetçisi Ayşe
    assert to_names(disp) == ["Ayşe"]
    alarms = list(eng.alarms.values())
    mgr.tick(20.0 * H + 5 * M, alarms)  # 20:05, vardiya değişti
    assert to_names(disp)[-1] == "Kemal" and disp.delivered[-1][1].startswith("NÖBET DEVRİ")


def test_explicit_handover_note_travels_with_the_page():
    disp, mgr, eng = setup()
    feed(mgr, eng, NOON, Severity.ALARM)
    mgr.schedule.handover(NOON + 5 * M, ((NUR,), (ZEYNEP,)), note="Ayşe hastalandı, Nur devraldı")
    mgr.tick(NOON + 6 * M, list(eng.alarms.values()))  # hatırlatma zamanı (15 dk) gelmeden, devir anında
    last = disp.delivered[-1]
    assert last[0].name == "Nur" and "Devir notu: Ayşe hastalandı, Nur devraldı" in last[1]


def test_parse_ack_accepts_expected_forms_only():
    assert parse_ack("ONAY F02-0001 4271") == ("F02-0001", "4271")
    assert parse_ack("/onay F02-0001 4271") == ("F02-0001", "4271")
    assert parse_ack("  onay   F02-0001   0042 ") == ("F02-0001", "0042")
    assert parse_ack("onay F02-0001") is None
    assert parse_ack("onay F02-0001 12345") is None
    assert parse_ack("merhaba") is None and parse_ack("") is None


def test_routed_dispatcher_selects_channel_by_route_and_rejects_unknown():
    seen = []
    d = RoutedDispatcher({"telegram": lambda r, t: seen.append((r.address, t))})
    d.deliver(Recipient("A", "x", "telegram", "42"), "merhaba")
    assert seen == [("42", "merhaba")]
    with pytest.raises(ValueError, match="bilinmeyen rota"):
        d.deliver(Recipient("B", "x", "sms", "5"), "merhaba")


def _fake_updates(*messages):
    def http_get(url, params):
        assert "getUpdates" in url
        return {"result": [
            {"update_id": 100 + i, "message": {"chat": {"id": chat}, "from": {"first_name": first, "last_name": last}, "text": text}}
            for i, (chat, first, last, text) in enumerate(messages)
        ]}
    return http_get


def test_telegram_poller_acks_only_from_allowed_chat_with_correct_token():
    eng = AlarmEngine("F02", id_prefix="F02", seed=1)
    eng.step(0.0, [TrackNow(BOLT, Phase.L2, Severity.ALARM, 40.0)])
    alarm = next(iter(eng.alarms.values()))
    good = f"ONAY {alarm.id} {alarm.ack_token}"
    bad = f"ONAY {alarm.id} {'0000' if alarm.ack_token != '0000' else '1111'}"
    poller = TelegramAckPoller(
        "TOKEN", {"1001"},
        http_get=_fake_updates(("9999", "Kötü", "Niyetli", good), ("1001", "Ayşe", "Yılmaz", bad)),
    )
    assert poller.poll(lambda a, t, by: eng.ack(a, t, by, 10.0)) == []
    assert alarm.state is AlarmState.OPEN  # yetkisiz sohbet + hatalı belirteç: alarm açık kaldı
    poller2 = TelegramAckPoller("TOKEN", {"1001"}, http_get=_fake_updates(("1001", "Ayşe", "Yılmaz", good)))
    assert poller2.poll(lambda a, t, by: eng.ack(a, t, by, 20.0)) == [alarm.id]
    assert alarm.state is AlarmState.ACKED and alarm.acked_by == "Ayşe Yılmaz"  # kimlik Telegram'dan, uydurulamaz


def test_telegram_poller_advances_offset_so_updates_are_not_reprocessed():
    calls = []

    def http_get(url, params):
        calls.append(params["offset"])
        return {"result": [{"update_id": 7, "message": {"chat": {"id": 1}, "text": "selam"}}]} if len(calls) == 1 else {"result": []}

    poller = TelegramAckPoller("T", {"1"}, http_get=http_get)
    poller.poll(lambda *a: None)
    poller.poll(lambda *a: None)
    assert calls == [0, 8]


def test_end_to_end_real_scenario_pages_once_then_stops_after_ack():
    data = generate(SCENARIOS["loose_bolt_abrupt"], seed=1)
    analysis = analyze(data)
    disp = ConsoleDispatcher()
    mgr = EscalationManager(OnCallSchedule([Shift(0, 24, DAY_TIERS)]), disp)
    eng = AlarmEngine("F02 (gevşek cıvatalı)", id_prefix="F02", seed=1)
    from panogoz.rules.alarms import tracks_now

    onset_i = int(data.truth.onset_t_s // data.period_s)
    acked = False
    for i in range(onset_i - 4, onset_i + 4 * 96):
        t = data.t_s[i]
        for ev in eng.step(t, tracks_now(analysis, i)):
            mgr.on_event(ev, eng.alarms[ev.alarm_id])
        mgr.tick(t, list(eng.alarms.values()))
        dispatchable = [a for a in eng.alarms.values() if a.needs_notification and a.state is AlarmState.OPEN]
        if dispatchable and not acked and t >= data.truth.onset_t_s + 3 * H:
            a = dispatchable[0]
            eng.ack(a.id, a.ack_token, "Ayşe Yılmaz", t)
            mgr.on_event(eng.events[-1], a)
            acked = True
            sent_at_ack = len(disp.delivered)
    assert acked
    first = mgr.sent()[0]
    assert first.kind == "first" and first.t_s >= data.truth.onset_t_s
    assert any(m.kind == "reminder" for m in mgr.sent())  # 3 saat onaysız kaldı
    assert any(m.kind == "escalation" for m in mgr.sent())
    after = [m for m in mgr.sent() if m.t_s > data.truth.onset_t_s + 3 * H and m.kind in ("reminder", "escalation")]
    assert after == []  # onaydan sonra sessizlik


def test_flapping_reopen_does_not_repage_a_person_already_notified():
    disp, mgr, eng = setup()
    feed(mgr, eng, NOON, Severity.ALARM)
    assert to_names(disp) == ["Ayşe"]
    feed(mgr, eng, NOON + 15 * M, Severity.NORMAL)  # CLEARED (yayın yok)
    feed(mgr, eng, NOON + 30 * M, Severity.ALARM)  # REOPENED (aynı alarm)
    assert to_names(disp) == ["Ayşe"]  # yeniden sayfalama yok
    assert [m.kind for m in mgr.sent()] == ["first"]
    # bekleyen hatırlatma zamanlayıcısı sürer
    mgr.tick(NOON + 15 * M + 1, list(eng.alarms.values()))
    assert [m.kind for m in mgr.sent()][-1] == "reminder"


def test_system_alarm_never_pages_anyone():
    disp, mgr, eng = setup()
    feed(mgr, eng, NOON, Severity.ALARM, spec=SPECS["comms_lost"], phase=None)
    assert disp.delivered == []


def test_cleared_alarm_gets_no_reminders():
    disp, mgr, eng = setup()
    feed(mgr, eng, NOON, Severity.ALARM)
    feed(mgr, eng, NOON + 5 * M, Severity.NORMAL)
    before = len(disp.delivered)
    mgr.tick(NOON + 3 * H, list(eng.alarms.values()))
    assert len(disp.delivered) == before
