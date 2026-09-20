"""Telegram transport - the doorbell, not the house.

Where this sits in the architecture
-----------------------------------

Telegram is a public cloud service.  The competition brief says *no public cloud*
and the README's honest position on WhatsApp (``escalation.whatsapp_status``) is
that a public messenger may be used only as a **data-minimised mirror**: the
outside world learns that something happened, never what the measurements were.
This module is that mirror.

* **Outbound only.**  We never open a listening port.  Replies are fetched with
  long polling (``getUpdates``) from inside the network, so the substation LAN
  needs an outbound HTTPS path to one host and nothing inbound.
* **Data-minimised by default** (``privacy="minimal"``).  The message carries the
  panel, the severity, the action and the acknowledgement code - asset identifiers
  and an instruction - and no measurement.  The details live behind the firewall
  in the field app (``panogoz.notify.saha``); the Telegram message links to it.
* **Advisory, never authoritative.**  A crew that never sees the Telegram message
  is still reached by SMS; an acknowledgement typed into Telegram is still
  checked against the rota and the per-incident token.  Telegram is one more
  independent path, and no other path depends on it.

What this file is
-----------------

Standard library only (``urllib``), so the on-premise install gains no dependency.
It is a *transport*: it sends what it is given and hands inbound messages to a
callback.  Message wording lives in ``escalation.compose_telegram``.

The bot token is a credential.  It is held in one private attribute, is never
part of ``repr``, ``status()``, a transcript or an exception message, and the
request path is logged as ``/bot<gizli>/...``.

What is NOT verified: this code has been exercised against a local stand-in that
speaks the Bot API wire format (``tests/fake_telegram.py``).  Delivery to a real
phone requires a real bot token and is checked by hand - see docs/12.
"""

from __future__ import annotations

import json
import re
import threading
import time
import urllib.error
import urllib.request
from collections import OrderedDict
from typing import Any, Callable
from urllib.parse import urlsplit

DEFAULT_API = "https://api.telegram.org"

#: ``callback_data`` is capped at 64 bytes by Telegram; ``ack:<id>:<token>`` is ~15.
ACK_PREFIX = "ack:"
_ACK_RE = re.compile(r"^ack:(\d+):(\d+)$")

_SENT_TEXT_KEEP = 256          #: remembered message bodies, for editing after an ack
_STATUS_CACHE_S = 30.0
_BACKOFF_CAP_S = 30.0


class TelegramChannel:
    """One bot.  Thread-safe for concurrent ``send`` calls."""

    path = "Telegram Bot API"

    def __init__(self, token: str, *, api_base: str = DEFAULT_API, privacy: str = "minimal",
                 http_timeout_s: float = 8.0, poll_timeout_s: float = 20.0,
                 on_message: Callable[[dict], None] | None = None) -> None:
        if not token or ":" not in token:
            raise ValueError("Telegram bot token bicimi 'sayilar:harfler' olmali (BotFather verir)")
        if privacy not in ("minimal", "standard"):
            raise ValueError("privacy 'minimal' veya 'standard' olmali")
        self._token = token
        self.api_base = api_base.rstrip("/")
        self.privacy = privacy
        self.http_timeout_s = float(http_timeout_s)
        self.poll_timeout_s = float(poll_timeout_s)
        self.on_message = on_message

        self._offset = 0
        self._sent_text: "OrderedDict[tuple[int, int], str]" = OrderedDict()
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._me: dict | None = None
        self._me_at = 0.0

        self.sent_count = 0
        self.received_count = 0
        self.consecutive_errors = 0
        self.last_error: str | None = None

    # --------------------------------------------------------------- basics --

    def __repr__(self) -> str:                      # never includes the token
        return f"TelegramChannel(api={urlsplit(self.api_base).netloc}, privacy={self.privacy})"

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _exchange(self, method: str, payload: dict, *, timeout: float | None = None) -> dict:
        """One API call.  Returns a plain dict and never raises.

        ``ok``, ``result``, ``error``, ``status`` (HTTP), ``retry_after``,
        ``latency_s`` and a one-line ``line`` for the transcript.
        """
        url = f"{self.api_base}/bot{self._token}/{method}"
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST",
                                     headers={"Content-Type": "application/json"})
        t0 = time.time()
        status = 0
        body: dict = {}
        error: str | None = None
        try:
            with urllib.request.urlopen(req, timeout=timeout or self.http_timeout_s) as resp:
                status = resp.status
                body = json.loads(resp.read().decode("utf-8") or "{}")
        except urllib.error.HTTPError as exc:
            status = exc.code
            try:
                body = json.loads(exc.read().decode("utf-8") or "{}")
            except Exception:  # noqa: BLE001 - an unreadable error body is still an error
                body = {}
            error = body.get("description") or f"HTTP {status}"
        except (urllib.error.URLError, OSError, ValueError) as exc:
            reason = getattr(exc, "reason", exc)
            error = f"baglanti hatasi: {type(reason).__name__}: {reason}"
        latency = round(time.time() - t0, 3)

        ok = bool(body.get("ok")) and error is None
        if not ok and error is None:
            error = body.get("description") or "beklenmeyen yanit"
        retry_after = (body.get("parameters") or {}).get("retry_after")
        # The token is masked in every human-readable line.
        line = (f"POST /bot<gizli>/{method}  ({len(data)} B)\n"
                f"-> {status or 'yok'} {'ok' if ok else 'HATA: ' + str(error)}  ({latency:.2f} s)")
        return {"ok": ok, "result": body.get("result"), "error": error, "status": status,
                "retry_after": retry_after, "latency_s": latency, "line": line}

    # ------------------------------------------------------------- outbound --

    def send(self, chat_id: int | str, text: str, *, buttons: list[list[dict]] | None = None,
             silent: bool = False) -> dict:
        """Send one HTML message, optionally with inline buttons.

        A URL button pointing at a private address is refused by Telegram
        ("Wrong HTTP URL").  That is cosmetic; the acknowledgement button is what
        matters.  So a refusal for that reason retries once without URL buttons.
        """
        payload: dict[str, Any] = {"chat_id": chat_id, "text": text, "parse_mode": "HTML",
                                   "disable_web_page_preview": True}
        if silent:
            payload["disable_notification"] = True
        if buttons:
            payload["reply_markup"] = {"inline_keyboard": buttons}

        res = self._exchange("sendMessage", payload)
        lines = [res["line"]]
        dropped = False
        if not res["ok"] and buttons and _has_url_button(buttons) and _mentions_button(res["error"]):
            kept = [[b for b in row if "url" not in b] for row in buttons]
            kept = [row for row in kept if row]
            payload2 = dict(payload)
            if kept:
                payload2["reply_markup"] = {"inline_keyboard": kept}
            else:
                payload2.pop("reply_markup", None)
            lines.append("# URL dugmesi reddedildi (ozel adres); dugmesiz yeniden deneniyor")
            res = self._exchange("sendMessage", payload2)
            lines.append(res["line"])
            dropped = True

        message_id = None
        if res["ok"] and isinstance(res["result"], dict):
            message_id = res["result"].get("message_id")
            self.sent_count += 1
            if isinstance(message_id, int):
                self._remember(chat_id, message_id, text)
                lines.append(f"# message_id={message_id}")
        if not res["ok"]:
            self.last_error = res["error"]
        return {"ok": res["ok"], "message_id": message_id, "error": res["error"],
                "retry_after": res["retry_after"], "latency_s": res["latency_s"],
                "transcript": "\n".join(lines), "path": self.path, "chat_id": chat_id,
                "dropped_url_button": dropped}

    def _remember(self, chat_id: int | str, message_id: int, text: str) -> None:
        try:
            key = (int(chat_id), message_id)
        except (TypeError, ValueError):
            return
        with self._lock:
            self._sent_text[key] = text
            while len(self._sent_text) > _SENT_TEXT_KEEP:
                self._sent_text.popitem(last=False)

    # ------------------------------------------------------------- feedback --

    def answer_callback(self, callback_id: str, text: str, *, alert: bool = False) -> dict:
        return self._exchange("answerCallbackQuery", {
            "callback_query_id": callback_id, "text": text[:190], "show_alert": alert})

    def mark_acked(self, chat_id: int | str, message_id: int, note: str) -> dict:
        """Strike the buttons and stamp who acknowledged, on the original message."""
        try:
            original = self._sent_text.get((int(chat_id), int(message_id)))
        except (TypeError, ValueError):
            original = None
        if original is None:
            return self._exchange("editMessageReplyMarkup", {
                "chat_id": chat_id, "message_id": message_id,
                "reply_markup": {"inline_keyboard": []}})
        return self._exchange("editMessageText", {
            "chat_id": chat_id, "message_id": message_id, "parse_mode": "HTML",
            "text": f"{original}\n\n✅ <b>Onaylandı</b> · {_esc(note)}",
            "reply_markup": {"inline_keyboard": []}})

    def reply(self, chat_id: int | str, text: str) -> dict:
        return self.send(chat_id, text, silent=True)

    # -------------------------------------------------------------- inbound --

    def poll_once(self) -> int:
        """One ``getUpdates`` round.  Returns how many updates were handled."""
        res = self._exchange(
            "getUpdates",
            {"offset": self._offset, "timeout": int(self.poll_timeout_s),
             "allowed_updates": ["message", "callback_query"]},
            timeout=self.poll_timeout_s + self.http_timeout_s)
        if not res["ok"]:
            self.consecutive_errors += 1
            self.last_error = res["error"]
            return 0
        self.consecutive_errors = 0
        handled = 0
        for upd in res["result"] or []:
            try:
                uid = int(upd.get("update_id", 0))
                self._offset = max(self._offset, uid + 1)   # advance first: no redelivery loop
                msg = self._normalise(upd)
                if msg is None:
                    continue
                handled += 1
                self.received_count += 1
                if self.on_message is not None:
                    self.on_message(msg)
            except Exception as exc:  # noqa: BLE001 - one bad update must not stop the rest
                self.last_error = f"isleyici hatasi: {exc!r}"
        return handled

    @staticmethod
    def _normalise(upd: dict) -> dict | None:
        """Telegram update -> the same shape the SMS inbox produces."""
        cq = upd.get("callback_query")
        if cq:
            frm = cq.get("from") or {}
            m = cq.get("message") or {}
            chat = (m.get("chat") or {}).get("id", frm.get("id"))
            data = str(cq.get("data") or "")
            hit = _ACK_RE.match(data)
            text = f"TAMAM {hit.group(1)} {hit.group(2)}" if hit else data
            return {"channel": "telegram", "number": f"tg:{frm.get('id')}", "chat_id": chat,
                    "text": text, "callback_id": cq.get("id"), "message_id": m.get("message_id"),
                    "from_name": frm.get("first_name", ""), "ts": time.time()}
        m = upd.get("message")
        if m and m.get("text"):
            frm = m.get("from") or {}
            return {"channel": "telegram", "number": f"tg:{frm.get('id')}",
                    "chat_id": (m.get("chat") or {}).get("id"), "text": str(m["text"]),
                    "callback_id": None, "message_id": m.get("message_id"),
                    "from_name": frm.get("first_name", ""), "ts": time.time()}
        return None

    # ------------------------------------------------------------ lifecycle --

    def start(self) -> None:
        """Begin long polling in a daemon thread.  Idempotent."""
        if self.running:
            return
        self._stop.clear()
        # A webhook registered elsewhere makes getUpdates fail with 409.
        self._exchange("deleteWebhook", {"drop_pending_updates": False})
        self._thread = threading.Thread(target=self._loop, name="panogoz:telegram", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        t = self._thread
        if t is not None and t.is_alive() and t is not threading.current_thread():
            t.join(timeout=3.0)
        self._thread = None

    def _loop(self) -> None:
        while not self._stop.is_set():
            self.poll_once()
            if self.consecutive_errors:
                self._stop.wait(min(_BACKOFF_CAP_S, 1.5 ** self.consecutive_errors))

    # --------------------------------------------------------------- status --

    def status(self) -> dict:
        now = time.time()
        if self._me is None or now - self._me_at > _STATUS_CACHE_S:
            res = self._exchange("getMe", {}, timeout=min(self.http_timeout_s, 4.0))
            self._me = {"ok": res["ok"], "result": res["result"], "error": res["error"]}
            self._me_at = now
        me = self._me
        username = (me["result"] or {}).get("username") if me["ok"] else None
        return {
            "path": self.path, "configured": True, "ok": bool(me["ok"]),
            "bot": f"@{username}" if username else None,
            "privacy": self.privacy, "api": urlsplit(self.api_base).netloc,
            "running": self.running, "sent": self.sent_count, "received": self.received_count,
            "consecutive_errors": self.consecutive_errors,
            "error": me["error"] or self.last_error,
        }


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def _esc(text: str) -> str:
    """Telegram HTML mode needs exactly these three escaped."""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _has_url_button(buttons: list[list[dict]]) -> bool:
    return any("url" in b for row in buttons for b in row)


def _mentions_button(error: str | None) -> bool:
    e = (error or "").lower()
    return "button" in e or "url" in e
