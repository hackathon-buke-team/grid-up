"""The escalation ladder across SMS, Telegram and the field app.

Each test states one rule of the contract:

* only KRITIK and ACIL reach a phone; UYARI is an in-app inbox item, never a ring;
* every rung of the ladder fans out to every configured channel of that rota level;
* an acknowledgement from ANY channel stops the repeats on ALL of them;
* both gates (on the rota, and the per-incident token) hold on every channel;
* the network never runs inside the detector's thread (asynchronous dispatch);
* Telegram is a data-minimised mirror: no measurements leave the building.
"""

from __future__ import annotations

import re
import time

import pytest

from panogoz.contracts.live import EtaView, JointView, PanelLive
from panogoz.notify import escalation as esc
from panogoz.notify.sms import GsmModem
from panogoz.notify.telegram import TelegramChannel
from panogoz.store.db import Store
from tests.fake_telegram import FakeTelegram

TOKEN = "123456:TEST-TOKEN"
T0 = 1_760_000_000.0

ROTA = [
    {"name": "Nöbetçi tekniker", "number": "+905321112233", "role": "birincil", "level": 1,
     "telegram_chat_id": 111},
    {"name": "Vardiya amiri", "number": "+905321112244", "role": "ikincil", "level": 2,
     "telegram_chat_id": 222},
    {"name": "İşletme müdürü", "number": "+905321112255", "role": "yönetici", "level": 3,
     "telegram_chat_id": 333},
]


@pytest.fixture()
def fake():
    with FakeTelegram(TOKEN) as f:
        yield f


@pytest.fixture()
def store(tmp_path):
    s = Store(str(tmp_path / "n.db"))
    yield s
    s.close()


def make_notifier(store, fake=None, *, privacy="minimal", public_url=None, app=True,
                  async_dispatch=False):
    tg = None
    if fake is not None:
        tg = TelegramChannel(TOKEN, api_base=fake.url, poll_timeout_s=0, http_timeout_s=2.0,
                             privacy=privacy)
    return esc.Notifier(store, modem=GsmModem(), rota=ROTA, telegram=tg, public_url=public_url,
                        app_enabled=app, async_dispatch=async_dispatch)


def open_incident(store, severity="KRITIK", mode="loose_connection", **kw):
    iid = store.open_incident(
        panel_key="SOKE-14", joint_key="C07-L2-PABUC", mode=mode, severity=severity,
        title="Çıkış 7 · L2 · çıkış pabucu — bağlantı direnci artıyor", action="Torkla",
        evidence={"joint": {"theta_k": 14.2, "temp_c": 99.0}}, dispatched=1, **kw)
    store.update_incident(iid, ack_token=esc.ack_token(iid))
    return dict(store.one("SELECT * FROM incident WHERE id=?", (iid,)))


def live_with_eta():
    live = PanelLive(panel_key="SOKE-14", panel_index=14, site="Söke", name="Söke 14")
    jv = JointView(key="C07-L2-PABUC", label="", zone="", conductor="L", feeder_index=7,
                   rated_a=400.0, monitored=True)
    jv.theta_k = 14.2
    jv.eta = EtaView(target="KRITIK", days=21.0, days_lo=13.0, days_hi=32.0)
    live.joints = [jv]
    live.health_index = 71.0
    return live


def rows(store, iid, channel=None):
    r = store.notifications(iid, limit=999)
    return [x for x in r if channel is None or x["channel"] == channel]


# ---------------------------------------------------------------- the ladder --

def test_kritik_fans_out_to_sms_telegram_and_app_for_level_one(store, fake):
    n = make_notifier(store, fake)
    inc = open_incident(store)
    n.on_incident(inc, live_with_eta(), T0)

    by_ch = {}
    for r in rows(store, inc["id"]):
        by_ch.setdefault(r["channel"], []).append(r["target"])
    assert by_ch["SMS"] == ["+905321112233"]
    assert by_ch["TELEGRAM"] == ["tg:111"]
    assert by_ch["MOBIL"] == ["Nöbetçi tekniker"]
    assert "SESLI" not in by_ch, "sesli arama KRITIK'te 30. dakikada baslar"
    assert len(fake.sent()) == 1 and fake.sent()[0]["chat_id"] == 111


def test_level_two_and_three_join_at_15_and_45_minutes(store, fake):
    n = make_notifier(store, fake)
    inc = open_incident(store)
    n.on_incident(inc, live_with_eta(), T0)
    n.tick(T0 + 900)
    assert {r["target"] for r in rows(store, inc["id"], "TELEGRAM")} >= {"tg:111", "tg:222"}
    assert "tg:333" not in {r["target"] for r in rows(store, inc["id"], "TELEGRAM")}
    n.tick(T0 + 2700)
    assert "tg:333" in {r["target"] for r in rows(store, inc["id"], "TELEGRAM")}
    assert "İşletme müdürü" in {r["target"] for r in rows(store, inc["id"], "MOBIL")}


def test_acil_reaches_two_people_on_every_channel_at_once(store, fake):
    n = make_notifier(store, fake)
    inc = open_incident(store, severity="ACIL", mode="arc_integrity")
    n.on_incident(inc, live_with_eta(), T0)
    tg = {r["target"] for r in rows(store, inc["id"], "TELEGRAM")}
    sms = {r["target"] for r in rows(store, inc["id"], "SMS")}
    assert tg == {"tg:111", "tg:222"} and sms == {"+905321112233", "+905321112244"}


def test_uyari_never_rings_a_phone_but_lands_in_the_app_inbox(store, fake):
    n = make_notifier(store, fake)
    inc = open_incident(store, severity="UYARI")
    n.on_incident(inc, live_with_eta(), T0)
    channels = {r["channel"] for r in rows(store, inc["id"])}
    assert "MOBIL" in channels
    assert not channels & {"SMS", "TELEGRAM", "SESLI"}, channels
    assert fake.sent() == []


def test_izle_is_dashboard_only(store, fake):
    n = make_notifier(store, fake)
    inc = open_incident(store, severity="IZLE")
    n.on_incident(inc, live_with_eta(), T0)
    assert {r["channel"] for r in rows(store, inc["id"])} == {"PANO"}


def test_unconfigured_telegram_is_skipped_not_an_error(store):
    n = make_notifier(store, fake=None)
    inc = open_incident(store)
    n.on_incident(inc, live_with_eta(), T0)
    chans = {r["channel"] for r in rows(store, inc["id"])}
    assert "TELEGRAM" not in chans and {"SMS", "MOBIL"} <= chans


def test_app_channel_is_off_unless_enabled(store):
    n = make_notifier(store, app=False)
    inc = open_incident(store)
    n.on_incident(inc, live_with_eta(), T0)
    assert "MOBIL" not in {r["channel"] for r in rows(store, inc["id"])}


def test_unacknowledged_kritik_repeats_on_sms_and_telegram(store, fake):
    n = make_notifier(store, fake)
    inc = open_incident(store)
    n.on_incident(inc, live_with_eta(), T0)
    before = (len(rows(store, inc["id"], "SMS")), len(rows(store, inc["id"], "TELEGRAM")))
    n.tick(T0 + 301)
    after = (len(rows(store, inc["id"], "SMS")), len(rows(store, inc["id"], "TELEGRAM")))
    assert after == (before[0] + 1, before[1] + 1)
    assert "tekrar" in fake.sent()[-1]["text"].lower()


def test_acknowledged_incident_stops_repeating_everywhere(store, fake):
    n = make_notifier(store, fake)
    inc = open_incident(store)
    n.on_incident(inc, live_with_eta(), T0)
    assert n.ack(inc["id"], "Nöbetçi tekniker", inc["ack_token"], channel="app")
    total = len(rows(store, inc["id"]))
    n.tick(T0 + 301)
    n.tick(T0 + 4000)
    assert len(rows(store, inc["id"])) == total


# --------------------------------------------------------- message contents --

def test_ladder_sms_carries_the_horizon_line(store):
    """Regression: compose(incident) was called without `live`, so the 'eşiğe kalan
    gün' line - the newest feature - never reached a real SMS."""
    n = make_notifier(store)
    inc = open_incident(store)
    n.on_incident(inc, live_with_eta(), T0)
    body = rows(store, inc["id"], "SMS")[0]["body"]
    assert "KRITIK'e 21 g (13-32)" in body, body


def test_minimal_telegram_carries_no_measurement(store, fake):
    n = make_notifier(store, fake, privacy="minimal")
    inc = open_incident(store)
    n.on_incident(inc, live_with_eta(), T0)
    text = fake.sent()[0]["text"]
    assert "SOKE-14" in text and "KRİTİK" in text and esc.ack_token(inc["id"]) in text
    assert "torkla" in text.lower()
    assert "θ" not in text and "°C" not in text and "14.2" not in text and "99 °C" not in text
    assert "21 g" not in text


def test_standard_telegram_adds_the_measurements(store, fake):
    n = make_notifier(store, fake, privacy="standard")
    inc = open_incident(store)
    n.on_incident(inc, live_with_eta(), T0)
    text = fake.sent()[0]["text"]
    assert "θ=14.2" in text and "99 °C" in text and "21 g" in text


def test_telegram_message_has_an_ack_button_and_a_field_app_link(store, fake):
    n = make_notifier(store, fake, public_url="http://192.168.1.201:8080")
    inc = open_incident(store)
    n.on_incident(inc, live_with_eta(), T0)
    kb = fake.sent()[0]["reply_markup"]["inline_keyboard"]
    flat = [b for row in kb for b in row]
    tok = esc.ack_token(inc["id"])
    assert {"text": "✅ Onayla", "callback_data": f"ack:{inc['id']}:{tok}"} in flat
    assert any(b.get("url") == f"http://192.168.1.201:8080/saha/#/olay/{inc['id']}" for b in flat)


def test_telegram_text_is_html_escaped(store, fake):
    n = make_notifier(store, fake)
    inc = open_incident(store)
    inc["panel_key"] = "A<B>&C"
    n.on_incident(inc, live_with_eta(), T0)
    text = fake.sent()[0]["text"]
    assert "A&lt;B&gt;&amp;C" in text and "<B>" not in text


def test_no_row_and_no_message_ever_contains_the_bot_token(store, fake):
    n = make_notifier(store, fake)
    inc = open_incident(store)
    n.on_incident(inc, live_with_eta(), T0)
    for r in rows(store, inc["id"]):
        assert TOKEN not in (r["body"] + r["transcript"] + r["target"])


# --------------------------------------------------- acknowledgement gates --

def _message_id(store, iid):
    tr = rows(store, iid, "TELEGRAM")[0]["transcript"]
    return int(re.search(r"message_id=(\d+)", tr).group(1))


def test_button_tap_from_a_rota_chat_acknowledges_and_stamps_the_message(store, fake):
    n = make_notifier(store, fake)
    inc = open_incident(store)
    n.on_incident(inc, live_with_eta(), T0)
    mid = _message_id(store, inc["id"])
    fake.push_callback(111, f"ack:{inc['id']}:{inc['ack_token']}", message_id=mid, first_name="Ali")
    n.telegram.poll_once()

    row = store.one("SELECT * FROM incident WHERE id=?", (inc["id"],))
    assert row["state"] == "ONAYLANDI"
    assert "Nöbetçi tekniker" in row["acked_by"] and "Telegram" in row["acked_by"]
    ans = fake.sent("answerCallbackQuery")[0]
    assert "Onaylandı" in ans["text"]
    edit = fake.sent("editMessageText")[0]
    assert edit["message_id"] == mid and edit["reply_markup"] == {"inline_keyboard": []}
    assert "Nöbetçi tekniker" in edit["text"]
    audit = store.one("SELECT detail FROM audit WHERE action='ack' ORDER BY id DESC LIMIT 1")
    assert '"telegram"' in audit["detail"]


def test_button_tap_from_a_chat_off_the_rota_is_rejected(store, fake):
    n = make_notifier(store, fake)
    inc = open_incident(store)
    n.on_incident(inc, live_with_eta(), T0)
    fake.push_callback(999, f"ack:{inc['id']}:{inc['ack_token']}", message_id=1)
    n.telegram.poll_once()
    assert store.one("SELECT state FROM incident WHERE id=?", (inc["id"],))["state"] == "ACIK"
    assert n.rejected_acks[-1]["reason"] == "not_on_rota"
    ans = fake.sent("answerCallbackQuery")[0]
    assert ans["show_alert"] is True and "nöbet listesinde değil" in ans["text"]


def test_typed_ack_with_a_wrong_token_is_rejected(store, fake):
    n = make_notifier(store, fake)
    inc = open_incident(store)
    n.on_incident(inc, live_with_eta(), T0)
    fake.push_message(111, f"TAMAM {inc['id']} 0000")
    n.telegram.poll_once()
    assert store.one("SELECT state FROM incident WHERE id=?", (inc["id"],))["state"] == "ACIK"
    assert n.rejected_acks[-1]["reason"] == "bad_token"
    assert "hatalı" in fake.sent()[-1]["text"]


def test_typed_ack_with_the_right_token_works(store, fake):
    n = make_notifier(store, fake)
    inc = open_incident(store)
    n.on_incident(inc, live_with_eta(), T0)
    fake.push_message(111, f"TAMAM {inc['id']} {inc['ack_token']}")
    n.telegram.poll_once()
    assert store.one("SELECT state FROM incident WHERE id=?", (inc["id"],))["state"] == "ONAYLANDI"


def test_an_ack_on_one_channel_strikes_the_buttons_on_every_telegram_message(store, fake):
    """Level 1 and level 2 both got the ACIL message.  When level 1 acknowledges by
    SMS, level 2's Telegram message must stop offering an acknowledge button."""
    n = make_notifier(store, fake)
    inc = open_incident(store, severity="ACIL", mode="arc_integrity")
    n.on_incident(inc, live_with_eta(), T0)
    n.modem.inject_reply("+905321112233", f"TAMAM {inc['id']} {inc['ack_token']}")
    assert n.check_replies(T0 + 5) == 1
    edits = fake.sent("editMessageText")
    assert {e["chat_id"] for e in edits} == {111, 222}


def test_start_command_tells_a_stranger_their_chat_id_and_nothing_else(store, fake):
    n = make_notifier(store, fake)
    fake.push_message(777, "/start")
    n.telegram.poll_once()
    reply = fake.sent()[-1]
    assert reply["chat_id"] == 777
    assert "777" in reply["text"] and "listesinde değil" in reply["text"]


def test_start_command_recognises_a_rota_member(store, fake):
    n = make_notifier(store, fake)
    fake.push_message(111, "/start")
    n.telegram.poll_once()
    assert "Nöbetçi tekniker" in fake.sent()[-1]["text"]


def test_durum_command_is_for_the_rota_only(store, fake):
    n = make_notifier(store, fake)
    inc = open_incident(store)
    n.on_incident(inc, live_with_eta(), T0)
    fake.calls.clear()
    fake.push_message(777, "/durum")
    fake.push_message(111, "/durum")
    n.telegram.poll_once()
    stranger, member = fake.sent()[-2:]
    assert stranger["chat_id"] == 777 and "SOKE-14" not in stranger["text"]
    assert member["chat_id"] == 111 and "SOKE-14" in member["text"]


# ----------------------------------------------------- failure independence --

def test_a_dead_telegram_does_not_stop_the_sms(store):
    dead = TelegramChannel(TOKEN, api_base="http://127.0.0.1:9", http_timeout_s=0.3,
                           poll_timeout_s=0)
    n = esc.Notifier(store, modem=GsmModem(), rota=ROTA, telegram=dead, app_enabled=True)
    inc = open_incident(store)
    n.on_incident(inc, live_with_eta(), T0)
    tg = rows(store, inc["id"], "TELEGRAM")[0]
    assert tg["state"] == "HATA" and "baglanti hatasi" in tg["transcript"]
    assert rows(store, inc["id"], "SMS")[0]["state"] == "GONDERILDI"


def test_dispatch_never_blocks_the_caller_when_the_network_is_slow(store, fake):
    """The detector thread calls on_incident.  A slow Telegram must cost it
    nothing: the row appears as KUYRUKTA immediately and settles later."""
    fake.delay_s = 0.8
    n = make_notifier(store, fake, async_dispatch=True)
    inc = open_incident(store)
    t0 = time.time()
    n.on_incident(inc, live_with_eta(), T0)
    assert time.time() - t0 < 0.4, "on_incident beklemis: tespit dongusu bloke olurdu"
    assert rows(store, inc["id"], "TELEGRAM")[0]["state"] == "KUYRUKTA"
    assert n.flush(timeout=10.0)
    assert rows(store, inc["id"], "TELEGRAM")[0]["state"] == "GONDERILDI"
    n.close()


def test_send_test_reaches_only_the_named_person(store, fake):
    n = make_notifier(store, fake)
    res = n.send_test("Vardiya amiri")
    assert {r["channel"] for r in res} == {"SMS", "TELEGRAM"}
    assert all(r["target_name"] == "Vardiya amiri" for r in res)
    assert [m["chat_id"] for m in fake.sent()] == [222]
    assert "TEST" in fake.sent()[0]["text"]


def test_status_lists_channels_and_never_a_secret(store, fake):
    n = make_notifier(store, fake)
    st = n.status()
    assert st["channels"]["telegram"]["configured"] is True
    assert st["channels"]["sms"]["simulated"] is True
    assert st["channels"]["mobil"]["enabled"] is True
    blob = repr(st)
    assert TOKEN not in blob and "pin" not in blob.lower()
