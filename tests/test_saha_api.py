"""The field-crew app's API: who may see what, and what an acknowledgement means.

The contract under test:

* nothing is reachable without a session, and a session needs a rota name + PIN;
* the PIN is protected by lock-out, and a wrong name and a wrong PIN look identical;
* a crew member sees the incidents that were sent to them (or, on request, all);
* the per-incident acknowledgement token is never sent to the phone: the session
  is the credential, and the server applies the token itself;
* acknowledgement, and the "on the way / on site / done" work-order status, are
  recorded in the hash-chained audit trail;
* no response, ever, carries the bot token or a PIN.
"""

from __future__ import annotations

import json
import time
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from panogoz.contracts.live import EtaView, JointView, PanelLive
from panogoz.notify import escalation as esc
from panogoz.notify import saha
from panogoz.notify.sms import GsmModem
from panogoz.notify.telegram import TelegramChannel
from panogoz.store.db import Store
from tests.fake_telegram import FakeTelegram

TOKEN = "123456:TEST-TOKEN"
ROTA = [
    {"name": "Nöbetçi tekniker", "number": "+905321112233", "role": "birincil", "level": 1,
     "telegram_chat_id": 111, "pin": "4821"},
    {"name": "Vardiya amiri", "number": "+905321112244", "role": "ikincil", "level": 2,
     "telegram_chat_id": 222, "pin": "5932"},
]


class Clock:
    def __init__(self) -> None:
        self.t = 1_760_000_000.0

    def __call__(self) -> float:
        return self.t


def make_live() -> PanelLive:
    live = PanelLive(panel_key="SOKE-14", panel_index=14, site="Söke", name="Söke 14",
                     dso="ADM", lat=37.75, lon=27.41)
    jv = JointView(key="C07-L2-PABUC", label="", zone="", conductor="L", feeder_index=7,
                   rated_a=400.0, monitored=True)
    jv.theta_k = 14.2
    jv.temp_c = 99.0
    jv.eta = EtaView(target="KRITIK", days=21.0, days_lo=13.0, days_hi=32.0)
    live.joints = [jv]
    live.health_index = 71.0
    return live


@pytest.fixture()
def env(tmp_path):
    fake = FakeTelegram(TOKEN).start()
    store = Store(str(tmp_path / "s.db"))
    tg = TelegramChannel(TOKEN, api_base=fake.url, poll_timeout_s=0, http_timeout_s=2.0)
    notifier = esc.Notifier(store, modem=GsmModem(), rota=ROTA, telegram=tg,
                            public_url="http://192.168.1.201:8080", app_enabled=True)
    clock = Clock()
    live = make_live()
    rt = SimpleNamespace(notifier=notifier, store=store, panel=lambda k: live,
                         resolve=lambda k: k, now=clock)
    app = FastAPI()
    saha.install(app, rt, clock=clock)
    client = TestClient(app)
    yield SimpleNamespace(client=client, store=store, notifier=notifier, fake=fake, clock=clock,
                          live=live, rt=rt)
    store.close()
    fake.stop()


def open_incident(env, severity="KRITIK", mode="loose_connection", notify=True):
    iid = env.store.open_incident(
        panel_key="SOKE-14", joint_key="C07-L2-PABUC", mode=mode, severity=severity,
        title="Çıkış 7 · L2 · çıkış pabucu — bağlantı direnci artıyor",
        action="Bağlantıyı torkla", dispatched=1,
        evidence={"joint": {"theta_k": 14.2, "temp_c": 99.0, "sibling_median_c": 62.0},
                  "load_factor": 0.65, "family_labels_tr": ["Isıl (TC)", "Kızılötesi (IR)"],
                  "terms": [{"label_tr": "θ eşiği aşıldı", "llr": 2.1}]},
        ruled_out=["Yük etkisi ELENDİ — θ normalize edildi.", "Yayıcılık ELENDİ."],
        opened_at=env.clock.t, updated_at=env.clock.t)
    env.store.update_incident(iid, ack_token=esc.ack_token(iid))
    inc = dict(env.store.one("SELECT * FROM incident WHERE id=?", (iid,)))
    if notify:
        env.notifier.on_incident(inc, env.live, env.clock.t)
    return inc


def login(env, name="Nöbetçi tekniker", pin="4821"):
    r = env.client.post("/api/saha/login", json={"name": name, "pin": pin})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["token"]}


# ------------------------------------------------------------------- login --

def test_rota_list_shows_names_and_nothing_secret(env):
    body = env.client.get("/api/saha/rota").json()
    assert [m["name"] for m in body] == ["Nöbetçi tekniker", "Vardiya amiri"]
    blob = json.dumps(body)
    for secret in ("4821", "5932", "+90532", "111", "pin", "number"):
        assert secret not in blob


def test_login_returns_a_session_and_no_pin(env):
    r = env.client.post("/api/saha/login", json={"name": "Nöbetçi tekniker", "pin": "4821"})
    assert r.status_code == 200
    body = r.json()
    assert body["member"] == {"name": "Nöbetçi tekniker", "role": "birincil", "level": 1}
    assert len(body["token"]) >= 32 and "4821" not in json.dumps(body)


def test_wrong_pin_and_unknown_name_are_indistinguishable(env):
    a = env.client.post("/api/saha/login", json={"name": "Nöbetçi tekniker", "pin": "0000"})
    b = env.client.post("/api/saha/login", json={"name": "Kimse Yok", "pin": "0000"})
    assert a.status_code == b.status_code == 401
    assert a.json() == b.json()


def test_five_wrong_pins_lock_the_account_even_for_the_right_pin(env):
    for _ in range(5):
        assert env.client.post("/api/saha/login",
                               json={"name": "Nöbetçi tekniker", "pin": "0000"}).status_code == 401
    r = env.client.post("/api/saha/login", json={"name": "Nöbetçi tekniker", "pin": "4821"})
    assert r.status_code == 429 and r.json()["retry_after_s"] > 0
    env.clock.t += 61
    assert env.client.post("/api/saha/login",
                           json={"name": "Nöbetçi tekniker", "pin": "4821"}).status_code == 200


def test_lockout_is_per_member(env):
    for _ in range(5):
        env.client.post("/api/saha/login", json={"name": "Nöbetçi tekniker", "pin": "0000"})
    assert env.client.post("/api/saha/login",
                           json={"name": "Vardiya amiri", "pin": "5932"}).status_code == 200


@pytest.mark.parametrize("method,path", [
    ("GET", "/api/saha/olaylar"), ("GET", "/api/saha/olay/1"),
    ("POST", "/api/saha/olay/1/onay"), ("POST", "/api/saha/olay/1/durum"),
    ("POST", "/api/saha/logout"),
])
def test_every_endpoint_needs_a_session(env, method, path):
    r = env.client.request(method, path, json={})
    assert r.status_code == 401
    r = env.client.request(method, path, json={}, headers={"Authorization": "Bearer nope"})
    assert r.status_code == 401


def test_sessions_expire(env):
    h = login(env)
    assert env.client.get("/api/saha/olaylar", headers=h).status_code == 200
    env.clock.t += 13 * 3600
    assert env.client.get("/api/saha/olaylar", headers=h).status_code == 401


def test_logout_revokes_the_session(env):
    h = login(env)
    assert env.client.post("/api/saha/logout", headers=h).status_code == 200
    assert env.client.get("/api/saha/olaylar", headers=h).status_code == 401


# ------------------------------------------------------------------- inbox --

def test_inbox_shows_incidents_sent_to_me_and_not_to_others(env):
    inc = open_incident(env)                    # KRITIK: level 1 only at t=0
    mine = env.client.get("/api/saha/olaylar", headers=login(env)).json()
    assert [o["id"] for o in mine["olaylar"]] == [inc["id"]]
    other = env.client.get("/api/saha/olaylar", headers=login(env, "Vardiya amiri", "5932")).json()
    assert other["olaylar"] == []
    everything = env.client.get("/api/saha/olaylar?tum=1",
                                headers=login(env, "Vardiya amiri", "5932")).json()
    assert [o["id"] for o in everything["olaylar"]] == [inc["id"]]


def test_inbox_card_carries_what_a_crew_needs_at_a_glance(env):
    inc = open_incident(env)
    card = env.client.get("/api/saha/olaylar", headers=login(env)).json()["olaylar"][0]
    assert card["panel_key"] == "SOKE-14" and card["joint_short"] == "Ç7·L2·pabuç"
    assert card["severity"] == "KRITIK" and card["severity_label"] == "Kritik"
    assert card["action"] == "Bağlantıyı torkla" and card["mode_label"] == "Gevşek bağlantı"
    assert card["needs_ack"] is True and card["sound"] is True
    assert card["state"] == "ACIK" and card["work"] is None
    assert card["notified_at"] is not None


def test_uyari_is_in_the_inbox_but_never_makes_a_sound(env):
    open_incident(env, severity="UYARI")
    card = env.client.get("/api/saha/olaylar", headers=login(env)).json()["olaylar"][0]
    assert card["severity"] == "UYARI" and card["sound"] is False


def test_first_fetch_marks_the_app_notification_as_delivered(env):
    inc = open_incident(env)
    row = lambda who: env.store.one(
        "SELECT state FROM notification WHERE incident_id=? AND channel='MOBIL' AND target=?",
        (inc["id"], who))
    assert row("Nöbetçi tekniker")["state"] == "GONDERILDI"
    env.client.get("/api/saha/olaylar", headers=login(env))
    assert row("Nöbetçi tekniker")["state"] == "ILETILDI"


def test_acknowledged_incident_stops_sounding(env):
    inc = open_incident(env)
    h = login(env)
    assert env.client.post(f"/api/saha/olay/{inc['id']}/onay", headers=h).json()["ok"]
    card = env.client.get("/api/saha/olaylar", headers=h).json()["olaylar"][0]
    assert card["state"] == "ONAYLANDI" and card["sound"] is False and card["needs_ack"] is False


# ------------------------------------------------------------------ detail --

def test_detail_has_location_measurements_and_the_reasoning(env):
    inc = open_incident(env)
    d = env.client.get(f"/api/saha/olay/{inc['id']}", headers=login(env)).json()
    assert d["pano"]["lat"] == 37.75 and d["pano"]["lon"] == 27.41 and d["pano"]["dso"] == "ADM"
    assert "37.75,27.41" in d["pano"]["maps_url"] and d["pano"]["geo_url"].startswith("geo:37.75,27.41")
    assert d["olcum"]["theta_k"] == 14.2 and d["olcum"]["temp_c"] == 99.0
    assert d["olcum"]["eta"] == "KRITIK'e 21 g (13-32)"
    assert d["neden"]["aileler"] == ["Isıl (TC)", "Kızılötesi (IR)"]
    assert any("ELENDİ" in x for x in d["neden"]["elenenler"])


def test_detail_never_carries_the_ack_token_or_a_secret(env):
    inc = open_incident(env)
    r = env.client.get(f"/api/saha/olay/{inc['id']}", headers=login(env))
    assert "ack_token" not in r.text and TOKEN not in r.text and "4821" not in r.text


def test_detail_timeline_lists_notifications_then_the_acknowledgement(env):
    inc = open_incident(env)
    h = login(env)
    env.client.post(f"/api/saha/olay/{inc['id']}/onay", headers=h)
    tl = env.client.get(f"/api/saha/olay/{inc['id']}", headers=h).json()["zaman_cizgisi"]
    kinds = [e["tip"] for e in tl]
    assert kinds[0] == "acilis" and "bildirim" in kinds and kinds[-1] == "onay"
    assert any(e["kanal"] == "TELEGRAM" for e in tl if e["tip"] == "bildirim")


def test_unknown_incident_is_a_404(env):
    assert env.client.get("/api/saha/olay/999", headers=login(env)).status_code == 404


# --------------------------------------------------------------------- ack --

def test_app_acknowledgement_is_recorded_with_its_channel(env):
    inc = open_incident(env)
    r = env.client.post(f"/api/saha/olay/{inc['id']}/onay", headers=login(env)).json()
    assert r["ok"] is True
    row = env.store.one("SELECT * FROM incident WHERE id=?", (inc["id"],))
    assert row["state"] == "ONAYLANDI" and row["acked_by"] == "Nöbetçi tekniker · uygulama"
    audit = env.store.one("SELECT detail FROM audit WHERE action='ack' ORDER BY id DESC LIMIT 1")
    assert '"app"' in audit["detail"]


def test_app_acknowledgement_strikes_the_telegram_button(env):
    inc = open_incident(env)
    env.client.post(f"/api/saha/olay/{inc['id']}/onay", headers=login(env))
    edit = env.fake.sent("editMessageText")
    assert edit and edit[0]["reply_markup"] == {"inline_keyboard": []}


def test_acknowledging_a_closed_incident_is_refused(env):
    inc = open_incident(env)
    env.store.update_incident(inc["id"], state="KAPANDI")
    r = env.client.post(f"/api/saha/olay/{inc['id']}/onay", headers=login(env)).json()
    assert r["ok"] is False and r["reason"]


# -------------------------------------------------------------- work order --

def test_work_status_needs_an_acknowledgement_first(env):
    inc = open_incident(env)
    r = env.client.post(f"/api/saha/olay/{inc['id']}/durum", headers=login(env),
                        json={"durum": "yolda"})
    assert r.status_code == 409


def test_work_status_flow_is_recorded_in_the_audit_chain(env):
    inc = open_incident(env)
    h = login(env)
    env.client.post(f"/api/saha/olay/{inc['id']}/onay", headers=h)
    for step in ("yolda", "sahada", "tamam"):
        r = env.client.post(f"/api/saha/olay/{inc['id']}/durum", headers=h,
                            json={"durum": step, "not": "tork 40 Nm" if step == "tamam" else ""})
        assert r.status_code == 200 and r.json()["ok"]
    card = env.client.get("/api/saha/olaylar", headers=h).json()["olaylar"][0]
    assert card["work"]["durum"] == "tamam" and card["work"]["by"] == "Nöbetçi tekniker"
    assert env.store.verify_chain()["ok"]
    wo = env.client.get(f"/api/notify/is-emri/{inc['id']}").json()
    assert [e["durum"] for e in wo["adimlar"]] == ["yolda", "sahada", "tamam"]
    assert wo["adimlar"][-1]["not"] == "tork 40 Nm" and wo["son"]["durum"] == "tamam"


def test_unknown_work_status_is_rejected(env):
    inc = open_incident(env)
    h = login(env)
    env.client.post(f"/api/saha/olay/{inc['id']}/onay", headers=h)
    assert env.client.post(f"/api/saha/olay/{inc['id']}/durum", headers=h,
                           json={"durum": "uyuyorum"}).status_code == 422


def test_work_status_cannot_go_backwards(env):
    inc = open_incident(env)
    h = login(env)
    env.client.post(f"/api/saha/olay/{inc['id']}/onay", headers=h)
    env.client.post(f"/api/saha/olay/{inc['id']}/durum", headers=h, json={"durum": "sahada"})
    r = env.client.post(f"/api/saha/olay/{inc['id']}/durum", headers=h, json={"durum": "yolda"})
    assert r.status_code == 409


# ------------------------------------------------------------ notify admin --

def test_status_endpoint_lists_channels_without_secrets(env):
    r = env.client.get("/api/notify/status")
    assert r.status_code == 200
    body = r.json()
    assert body["channels"]["telegram"]["configured"] is True
    assert body["channels"]["sms"]["simulated"] is True
    assert body["saha_url"] == "http://192.168.1.201:8080/saha/"
    for secret in (TOKEN, "4821", "5932"):
        assert secret not in r.text


def test_test_endpoint_sends_only_to_a_named_rota_member(env):
    r = env.client.post("/api/notify/test", json={"to": "Vardiya amiri"})
    assert r.status_code == 200
    assert {x["channel"] for x in r.json()["sonuc"]} == {"SMS", "TELEGRAM"}
    assert [m["chat_id"] for m in env.fake.sent()] == [222]
    assert env.client.post("/api/notify/test", json={"to": "Kimse Yok"}).status_code == 404
    assert env.client.post("/api/notify/test", json={}).status_code == 422


def test_test_endpoint_is_rate_limited(env):
    assert env.client.post("/api/notify/test", json={"to": "Vardiya amiri"}).status_code == 200
    assert env.client.post("/api/notify/test", json={"to": "Vardiya amiri"}).status_code == 429
    env.clock.t += 11
    assert env.client.post("/api/notify/test", json={"to": "Vardiya amiri"}).status_code == 200


# ------------------------------------------------------------------- static --

def test_the_app_shell_is_served(env):
    r = env.client.get("/saha/")
    assert r.status_code == 200 and "<title>" in r.text and "PANO GÖZ" in r.text
    assert r.headers["cache-control"].startswith("no-store")
    m = env.client.get("/saha/manifest.webmanifest")
    assert m.status_code == 200 and json.loads(m.text)["start_url"].startswith("/saha/")
    assert env.client.get("/saha/sw.js").status_code == 200


def test_without_a_notifier_the_routes_say_so(tmp_path):
    rt = SimpleNamespace(notifier=None, store=Store(str(tmp_path / "x.db")),
                         panel=lambda k: None, resolve=lambda k: k, now=time.time)
    app = FastAPI()
    saha.install(app, rt)
    c = TestClient(app)
    assert c.get("/api/saha/rota").status_code == 503
    assert c.get("/api/notify/status").status_code == 503
