"""End to end: a demo scenario -> detection -> alarm -> three channels -> acknowledgement.

This is the test that answers "does the telephone actually ring when the demo
operator clicks Ark olayı?".  It uses the production wiring, not a hand-built
notifier: a real ``Runtime`` builds its notifier from a configuration file through
``factory.build_notifier``, exactly as ``run_local`` does.  Only two things are
stand-ins: Telegram's servers (``tests/fake_telegram.py``, same wire format) and the
GSM modem (the simulated one; no hardware here).
"""

from __future__ import annotations

import json
import re
import time

import pytest
from fastapi.testclient import TestClient

from panogoz.api.app import create_app
from panogoz.api.runtime import DEMO_PANEL, Runtime
from panogoz.bus.bus import InProcBus
from tests.fake_telegram import FakeTelegram

TOKEN = "123456:TEST-TOKEN"


def wait(pred, timeout=60.0, step=0.25):
    end = time.time() + timeout
    while time.time() < end:
        v = pred()
        if v:
            return v
        time.sleep(step)
    return None


@pytest.fixture()
def system(tmp_path, monkeypatch):
    fake = FakeTelegram(TOKEN).start()
    cfg = tmp_path / "notify.local.json"
    cfg.write_text(json.dumps({
        "public_url": "http://192.168.1.201:8080",
        "telegram": {"token": TOKEN, "api_base": fake.url, "privacy": "minimal"},
        "rota": [
            {"name": "Nöbetçi tekniker", "role": "birincil", "level": 1,
             "number": "+905321112233", "telegram_chat_id": 111, "pin": "4821"},
            {"name": "Vardiya amiri", "role": "ikincil", "level": 2,
             "number": "+905321112244", "telegram_chat_id": 222, "pin": "5932"},
            {"name": "İşletme müdürü", "role": "yönetici", "level": 3,
             "number": "+905321112255", "telegram_chat_id": 333, "pin": "6043"},
        ],
    }), encoding="utf-8")
    monkeypatch.setenv("PANOGOZ_NOTIFY_LIVE", "1")
    monkeypatch.setenv("PANOGOZ_NOTIFY_CONFIG", str(cfg))
    rt = Runtime(n_panels=6, seed=42, db_path=str(tmp_path / "e2e.db"), backfill_days=18,
                 scada_port=15931, bus=InProcBus(), quiet=True)
    rt.bootstrap()
    rt.start()
    client = TestClient(create_app(rt))
    yield rt, client, fake
    rt.stop()
    rt.store.close()
    fake.stop()


def test_the_arc_scenario_reaches_a_phone_and_can_be_acknowledged_from_telegram(system):
    rt, client, fake = system
    assert rt.notifier.telegram is not None and rt.notifier.async_dispatch is True

    # 1. the demo operator clicks "Ark olayı" (at_s=2: the trip happens 2 s after injection)
    r = client.post("/api/scenario/ark_olayi", json={"panel_key": DEMO_PANEL, "at_s": 2})
    assert r.status_code == 200 and r.json()["ok"]

    # 2. the detector opens an ACIL incident and the ladder fans out
    assert wait(lambda: fake.sent()), "hicbir Telegram mesaji gitmedi"
    msgs = fake.sent()
    first = msgs[0]
    assert first["chat_id"] in (111, 222)
    assert "ACİL" in first["text"] and DEMO_PANEL in first["text"]
    assert "θ" not in first["text"] and "°C" not in first["text"], "minimal mod olcum sizdirdi"
    kb = [b for row in first["reply_markup"]["inline_keyboard"] for b in row]
    ack_btn = next(b for b in kb if "callback_data" in b)
    inc_id = int(ack_btn["callback_data"].split(":")[1])

    # 3. every channel has its own row, settled by the dispatch lanes
    assert wait(lambda: rt.notifier.flush(timeout=1.0))
    rows = rt.store.notifications(inc_id, limit=200)
    by = {}
    for x in rows:
        by.setdefault(x["channel"], []).append(x)
    assert {"SMS", "TELEGRAM", "MOBIL", "SESLI"} <= set(by), sorted(by)
    assert all(x["state"] == "GONDERILDI" for x in by["TELEGRAM"]), by["TELEGRAM"]
    assert TOKEN not in json.dumps(rows), "bot anahtari veritabanina sizdi"

    # 4. the crew member taps the button on their phone
    tg_row = next(x for x in by["TELEGRAM"] if x["target"] == "tg:111")
    mid = int(re.search(r"message_id=(\d+)", tg_row["transcript"]).group(1))
    fake.push_callback(111, ack_btn["callback_data"], message_id=mid, first_name="Ali")

    def acked():
        row = rt.store.one("SELECT state, acked_by FROM incident WHERE id=?", (inc_id,))
        return row if row and row["state"] == "ONAYLANDI" else None

    row = wait(acked, timeout=15.0)
    assert row, "dugmeye basildi ama olay onaylanmadi"
    assert row["acked_by"] == "Nöbetçi tekniker · Telegram"

    # 5. the phone gets its answer and every Telegram copy loses its button
    assert fake.wait_for("answerCallbackQuery", 1, timeout=10.0)
    assert fake.wait_for("editMessageText", 2, timeout=10.0), "diger kopyalarin dugmesi kalkmadi"
    assert {e["chat_id"] for e in fake.sent("editMessageText")} >= {111, 222}

    # 6. the console API and the field app both see the acknowledged state
    console = {a["id"]: a for a in client.get("/api/alarms?state=ALL").json()}
    assert console[inc_id]["state"] == "ONAYLANDI"
    login = client.post("/api/saha/login", json={"name": "Nöbetçi tekniker", "pin": "4821"}).json()
    h = {"Authorization": "Bearer " + login["token"]}
    card = next(c for c in client.get("/api/saha/olaylar", headers=h).json()["olaylar"]
                if c["id"] == inc_id)
    assert card["state"] == "ONAYLANDI" and card["sound"] is False

    # 7. and no more repeats are scheduled for it
    before = len(rt.store.notifications(inc_id, limit=500))
    rt.notifier.tick(time.time() + 3600)
    rt.notifier.flush(timeout=5.0)
    assert len(rt.store.notifications(inc_id, limit=500)) == before
    assert rt.store.verify_chain()["ok"]


def test_health_reports_the_channels_that_are_configured(system):
    rt, client, fake = system
    st = client.get("/api/notify/status").json()
    assert st["channels"]["telegram"]["configured"] is True
    assert st["channels"]["telegram"]["bot"] == "@panogoz_test_bot"
    assert st["channels"]["sms"]["simulated"] is True
    assert st["saha_url"] == "http://192.168.1.201:8080/saha/"
    assert TOKEN not in json.dumps(st) and "4821" not in json.dumps(st)
    assert client.get("/saha/").status_code == 200
    health = client.get("/api/health").json()
    assert health["ok"] and not [d for d in health.get("degraded", []) if "notify" in d]


def test_the_consoles_ark_button_rings_a_phone_without_an_hour_of_waiting(system):
    """Regression: the console's 'Ark olayı enjekte et' sends only ``{panel_key}``
    (frontend/js/app.js), and ``ark_olayi`` defaults to ``at_s=3600`` - the trip
    happens one hour after the click.  docs/08 §5 tells the presenter to click it
    and talk about the 4-13 s notification latency; with the default the presenter
    talks to an idle phone for an hour."""
    rt, client, fake = system
    r = client.post("/api/scenario/ark_olayi", json={"panel_key": DEMO_PANEL})   # exactly what the UI sends
    assert r.status_code == 200 and r.json()["ok"]
    assert wait(lambda: fake.sent(), timeout=45), \
        "Ark olayi dugmesine basildi, 45 s icinde hicbir Telegram mesaji gitmedi"
    assert "ACİL" in fake.sent()[0]["text"]
