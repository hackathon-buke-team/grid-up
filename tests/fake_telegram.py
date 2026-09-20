"""A local stand-in for the Telegram Bot API, for tests only.

It speaks the real wire format - ``POST /bot<token>/<method>`` with a JSON body,
``{"ok": true, "result": ...}`` back - so the code under test exercises its real
HTTP path (URL building, timeouts, error decoding, long polling) without a token
and without a network.  What it cannot prove is that Telegram itself accepts a
particular message; that needs a real bot and is stated as unverified in
docs/12-BILDIRIM-KANALLARI.md.

Failure injection is explicit: ``fail_next`` makes the next N calls fail with a
chosen HTTP status, ``reject_url_buttons`` reproduces the real API's refusal of
private-address inline URL buttons, and ``delay_s`` makes every call slow.
"""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


class FakeTelegram:
    def __init__(self, token: str = "123456:TEST-TOKEN", bot_username: str = "panogoz_test_bot") -> None:
        self.token = token
        self.bot_username = bot_username
        self.calls: list[tuple[str, dict]] = []
        self.delay_s = 0.0
        self.reject_url_buttons = False
        self._fail: list[tuple[int, str, dict]] = []
        self._updates: list[dict] = []
        self._next_update_id = 1000
        self._next_message_id = 500
        self._cv = threading.Condition()
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------ lifecycle --

    def start(self) -> "FakeTelegram":
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a: Any) -> None:  # silence the test output
                pass

            def do_POST(self) -> None:  # noqa: N802 - http.server API
                n = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(n) if n else b"{}"
                try:
                    payload = json.loads(raw or b"{}")
                except json.JSONDecodeError:
                    payload = {}
                status, body = fake._handle(self.path, payload)
                data = json.dumps(body).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._server.daemon_threads = True
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None

    def __enter__(self) -> "FakeTelegram":
        return self.start()

    def __exit__(self, *exc: Any) -> None:
        self.stop()

    @property
    def url(self) -> str:
        assert self._server is not None, "start() first"
        return f"http://127.0.0.1:{self._server.server_address[1]}"

    # ------------------------------------------------------------- scripting --

    def fail_next(self, n: int = 1, status: int = 500, description: str = "Internal error",
                  **parameters: Any) -> None:
        self._fail.extend([(status, description, parameters)] * n)

    def push_message(self, chat_id: int, text: str, first_name: str = "Test") -> None:
        self._push({"message": {
            "message_id": self._mid(), "date": int(time.time()),
            "chat": {"id": chat_id, "type": "private"},
            "from": {"id": chat_id, "is_bot": False, "first_name": first_name},
            "text": text,
        }})

    def push_callback(self, chat_id: int, data: str, message_id: int, first_name: str = "Test") -> None:
        self._push({"callback_query": {
            "id": f"cb{self._next_update_id}",
            "from": {"id": chat_id, "is_bot": False, "first_name": first_name},
            "message": {"message_id": message_id, "chat": {"id": chat_id, "type": "private"}},
            "data": data,
        }})

    def _mid(self) -> int:
        self._next_message_id += 1
        return self._next_message_id

    def _push(self, update: dict) -> None:
        with self._cv:
            self._next_update_id += 1
            update["update_id"] = self._next_update_id
            self._updates.append(update)
            self._cv.notify_all()

    # ------------------------------------------------------------- inspection --

    def sent(self, method: str = "sendMessage") -> list[dict]:
        return [p for m, p in list(self.calls) if m == method]

    def wait_for(self, method: str, n: int = 1, timeout: float = 5.0) -> bool:
        end = time.time() + timeout
        while time.time() < end:
            if len(self.sent(method)) >= n:
                return True
            time.sleep(0.02)
        return False

    # --------------------------------------------------------------- handler --

    def _handle(self, path: str, payload: dict) -> tuple[int, dict]:
        if self.delay_s:
            time.sleep(self.delay_s)
        parts = path.strip("/").split("/")
        if len(parts) != 2 or not parts[0].startswith("bot"):
            return 404, {"ok": False, "error_code": 404, "description": "Not Found"}
        token, method = parts[0][3:], parts[1]
        if token != self.token:
            return 401, {"ok": False, "error_code": 401, "description": "Unauthorized"}
        self.calls.append((method, payload))

        if method != "getUpdates" and self._fail:
            status, desc, params = self._fail.pop(0)
            body: dict = {"ok": False, "error_code": status, "description": desc}
            if params:
                body["parameters"] = params
            return status, body

        if method == "getMe":
            return 200, {"ok": True, "result": {"id": 1, "is_bot": True, "username": self.bot_username}}
        if method == "sendMessage":
            if self.reject_url_buttons and _has_url_button(payload.get("reply_markup")):
                return 400, {"ok": False, "error_code": 400, "description":
                             "Bad Request: inline keyboard button URL 'http://192.168.1.201:8080' "
                             "is invalid: Wrong HTTP URL"}
            return 200, {"ok": True, "result": {
                "message_id": self._mid(), "chat": {"id": payload.get("chat_id")},
                "date": int(time.time()), "text": payload.get("text", "")}}
        if method in ("answerCallbackQuery", "editMessageText", "editMessageReplyMarkup"):
            return 200, {"ok": True, "result": True}
        if method == "getUpdates":
            return self._get_updates(payload)
        return 404, {"ok": False, "error_code": 404, "description": f"unknown method {method}"}

    def _get_updates(self, payload: dict) -> tuple[int, dict]:
        offset = int(payload.get("offset") or 0)
        wait_s = min(float(payload.get("timeout") or 0), 1.0)
        end = time.time() + wait_s
        with self._cv:
            while True:
                self._updates = [u for u in self._updates if u["update_id"] >= offset]
                if self._updates or time.time() >= end:
                    return 200, {"ok": True, "result": list(self._updates)}
                self._cv.wait(timeout=max(0.01, end - time.time()))


def _has_url_button(markup: Any) -> bool:
    if not isinstance(markup, dict):
        return False
    for row in markup.get("inline_keyboard", []):
        for btn in row:
            if "url" in btn:
                return True
    return False
