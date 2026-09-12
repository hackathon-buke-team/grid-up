"""Telegram'dan gelen /onayla komutunu dinleyip eskalasyon merdivenini tetikler.

Açık kalan madde: bildirim tek yönlüydü (yalnız gönderim), kullanıcının Telegram'a
yazdığı onay hiçbir yere ulaşmıyordu. Bu modül uzun-polling (`getUpdates`) kullanır;
on-prem kısıtına uyar çünkü dışa açık bir webhook/URL gerektirmez — sunucudan
periyodik olarak Telegram'a tek yönlü HTTPS çağrısı yapılır.

Komut biçimi: `/onayla <alarm_id> <token>` — token, open_alarm() ile üretilen
4 haneli kimliklendirilmiş onay koduyla eşleşmelidir (K4 §4.2).
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

import requests

from panogoz.notify.escalation import EscalationLadder
from panogoz.notify.telegram_channel import TELEGRAM_API_BASE

ACK_PATTERN = re.compile(r"^/onayla(?:@\w+)?\s+(\S+)\s+(\d{4})\s*$")


def parse_ack_command(text: str) -> tuple[str, str] | None:
    """'/onayla <alarm_id> <token>' -> (alarm_id, token); eşleşmezse None."""
    if not text:
        return None
    match = ACK_PATTERN.match(text.strip())
    if not match:
        return None
    return match.group(1), match.group(2)


@dataclass
class TelegramAckListener:
    bot_token: str
    ladder: EscalationLadder
    poll_timeout_s: int = 30
    offset: int = 0
    processed_log: list = field(default_factory=list)

    def _reply(self, chat_id: int, text: str) -> None:
        url = f"{TELEGRAM_API_BASE}/bot{self.bot_token}/sendMessage"
        requests.post(url, json={"chat_id": chat_id, "text": text}, timeout=10.0)

    def process_update(self, update: dict) -> bool:
        """Tek bir Telegram update'ini işler. Komut işlendiyse True döner (ağ çağrısı
        `_reply` hariç saf mantık — testlerde `_reply`'ı override etmek yeterli)."""
        message = update.get("message") or update.get("channel_post")
        if not message:
            return False
        parsed = parse_ack_command(message.get("text", ""))
        if parsed is None:
            return False
        alarm_id, token = parsed
        sender = message.get("from", {})
        person = sender.get("username") or sender.get("first_name") or "bilinmeyen"
        chat_id = message["chat"]["id"]
        ok = self.ladder.acknowledge(alarm_id, token=token, person=person)
        if ok:
            self._reply(chat_id, f"✅ {alarm_id} onaylandı — {person}")
        else:
            self._reply(chat_id, f"❌ Onay reddedildi: {alarm_id} bulunamadı ya da token hatalı")
        self.processed_log.append((alarm_id, ok))
        return True

    def poll_once(self) -> int:
        """getUpdates ile bekleyen mesajları çeker ve işler; işlenen komut sayısını döner."""
        url = f"{TELEGRAM_API_BASE}/bot{self.bot_token}/getUpdates"
        params = {"offset": self.offset, "timeout": self.poll_timeout_s}
        resp = requests.get(url, params=params, timeout=self.poll_timeout_s + 10)
        resp.raise_for_status()
        updates = resp.json().get("result", [])
        handled = 0
        for update in updates:
            self.offset = update["update_id"] + 1
            if self.process_update(update):
                handled += 1
        return handled

    def run_forever(self) -> None:
        while True:
            try:
                self.poll_once()
            except requests.RequestException:
                time.sleep(2.0)
