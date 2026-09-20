"""Telegram transport: what goes on the wire, and what survives when the wire fails.

Everything here runs against ``tests/fake_telegram.py``, which speaks the real Bot
API wire format, so the real HTTP code path is exercised.  What is NOT proven here
is that Telegram accepts a given message - that needs a real bot token.
"""

from __future__ import annotations

import threading
import time

from panogoz.notify.telegram import TelegramChannel
from tests.fake_telegram import FakeTelegram

TOKEN = "123456:TEST-TOKEN"
ACK_BTN = {"text": "Onayla", "callback_data": "ack:7:1234"}
URL_BTN = {"text": "Ac", "url": "http://192.168.1.201:8080/saha/#/olay/7"}


def make(fake: FakeTelegram, **kw) -> TelegramChannel:
    return TelegramChannel(TOKEN, api_base=fake.url, poll_timeout_s=0,
                           http_timeout_s=2.0, **kw)


# ------------------------------------------------------------------ outbound --

def test_send_posts_a_real_shaped_request():
    with FakeTelegram(TOKEN) as fake:
        res = make(fake).send(42, "PANO GÖZ <b>test</b>", buttons=[[ACK_BTN]])
        assert res["ok"] is True
        assert isinstance(res["message_id"], int)
        body = fake.sent()[0]
        assert body["chat_id"] == 42
        assert body["parse_mode"] == "HTML"
        assert body["text"] == "PANO GÖZ <b>test</b>"
        assert body["reply_markup"]["inline_keyboard"] == [[ACK_BTN]]


def test_transcript_never_contains_the_token():
    with FakeTelegram(TOKEN) as fake:
        ch = make(fake)
        res = ch.send(42, "x")
        assert TOKEN not in res["transcript"]
        assert "sendMessage" in res["transcript"]
        assert TOKEN not in repr(ch) and TOKEN not in repr(ch.status())


def test_silent_flag_disables_the_ping():
    with FakeTelegram(TOKEN) as fake:
        make(fake).send(42, "sessiz", silent=True)
        assert fake.sent()[0]["disable_notification"] is True


def test_unreachable_server_is_a_failed_result_not_an_exception():
    ch = TelegramChannel(TOKEN, api_base="http://127.0.0.1:9", http_timeout_s=0.5,
                         poll_timeout_s=0)
    t0 = time.time()
    res = ch.send(42, "x")
    assert res["ok"] is False
    assert res["error"]
    assert time.time() - t0 < 5.0


def test_wrong_token_is_reported_as_unauthorized():
    with FakeTelegram("999:OTHER") as fake:
        res = make(fake).send(42, "x")
        assert res["ok"] is False and "Unauthorized" in res["error"]


def test_rate_limit_carries_retry_after():
    with FakeTelegram(TOKEN) as fake:
        fake.fail_next(1, status=429, description="Too Many Requests: retry after 3",
                       retry_after=3)
        res = make(fake).send(42, "x")
        assert res["ok"] is False and res["retry_after"] == 3


def test_private_address_url_button_is_dropped_and_the_message_still_goes():
    """Telegram rejects inline URL buttons that point at private addresses.  The
    alarm must not be lost to a cosmetic button: retry once without it, and keep
    the callback button, which is the acknowledgement."""
    with FakeTelegram(TOKEN) as fake:
        fake.reject_url_buttons = True
        res = make(fake).send(42, "x", buttons=[[ACK_BTN], [URL_BTN]])
        assert res["ok"] is True
        assert res["dropped_url_button"] is True
        first, second = fake.sent()
        assert any("url" in b for row in first["reply_markup"]["inline_keyboard"] for b in row)
        remaining = [b for row in second["reply_markup"]["inline_keyboard"] for b in row]
        assert remaining == [ACK_BTN]


# ------------------------------------------------------------------- inbound --

def test_poll_once_delivers_each_update_exactly_once():
    with FakeTelegram(TOKEN) as fake:
        got: list[dict] = []
        ch = make(fake, on_message=got.append)
        fake.push_message(42, "TAMAM 7 1234", first_name="Ali")
        fake.push_callback(42, "ack:7:1234", message_id=501)
        assert ch.poll_once() == 2
        assert ch.poll_once() == 0            # offset advanced: no redelivery
        text, cb = got
        assert text["number"] == "tg:42" and text["chat_id"] == 42
        assert text["text"] == "TAMAM 7 1234" and text["from_name"] == "Ali"
        assert cb["number"] == "tg:42" and cb["callback_id"]
        assert cb["message_id"] == 501
        assert cb["text"] == "TAMAM 7 1234"   # a button tap is normalised to the SMS grammar


def test_poll_survives_a_dead_network():
    ch = TelegramChannel(TOKEN, api_base="http://127.0.0.1:9", http_timeout_s=0.3,
                         poll_timeout_s=0)
    assert ch.poll_once() == 0
    assert ch.consecutive_errors == 1


def test_a_failing_handler_does_not_lose_the_next_update():
    with FakeTelegram(TOKEN) as fake:
        seen: list[str] = []

        def handler(msg: dict) -> None:
            seen.append(msg["text"])
            if msg["text"] == "boom":
                raise RuntimeError("handler bug")

        ch = make(fake, on_message=handler)
        fake.push_message(42, "boom")
        fake.push_message(42, "sonraki")
        ch.poll_once()
        assert seen == ["boom", "sonraki"]


def test_background_thread_starts_and_stops_promptly():
    with FakeTelegram(TOKEN) as fake:
        got: list[dict] = []
        ev = threading.Event()

        def handler(msg: dict) -> None:
            got.append(msg)
            ev.set()

        ch = TelegramChannel(TOKEN, api_base=fake.url, poll_timeout_s=1,
                             http_timeout_s=3.0, on_message=handler)
        ch.start()
        try:
            fake.push_message(42, "merhaba")
            assert ev.wait(5.0), "background poller never delivered the update"
            assert got[0]["text"] == "merhaba"
        finally:
            t0 = time.time()
            ch.stop()
            assert time.time() - t0 < 5.0
        assert not ch.running


# ------------------------------------------------------------------ feedback --

def test_answer_callback_and_mark_acked():
    with FakeTelegram(TOKEN) as fake:
        ch = make(fake)
        sent = ch.send(42, "<b>KRİTİK</b> SOKE-14", buttons=[[ACK_BTN]])
        ch.answer_callback("cb1", "Onaylandı")
        ch.mark_acked(42, sent["message_id"], "Ali · 14:32")
        ans = fake.sent("answerCallbackQuery")[0]
        assert ans["callback_query_id"] == "cb1" and ans["text"] == "Onaylandı"
        edit = fake.sent("editMessageText")[0]
        assert edit["message_id"] == sent["message_id"]
        assert "KRİTİK" in edit["text"] and "Ali · 14:32" in edit["text"]
        assert edit["reply_markup"] == {"inline_keyboard": []}


def test_status_reports_the_bot_and_the_privacy_mode():
    with FakeTelegram(TOKEN, bot_username="benim_botum") as fake:
        st = make(fake, privacy="minimal").status()
        assert st["configured"] is True and st["ok"] is True
        assert st["bot"] == "@benim_botum" and st["privacy"] == "minimal"
