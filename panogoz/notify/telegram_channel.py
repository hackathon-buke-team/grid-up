"""Telegram Bot API üzerinden gerçek anlık bildirim kanalı.

Yarışma brifi SMS/WhatsApp/benzeri anlık bildirim kanalı istiyor. WhatsApp
Business API işletme onayı/telefon doğrulaması gerektirir; Telegram Bot API
ücretsizdir, dakikalar içinde kurulur ve aynı işlevi görür: sunucudan tek
yönlü dışa HTTPS çağrısıyla telefona gerçek push bildirimi düşürür. On-prem
kısıtına uyar — hiçbir veri üçüncü tarafta saklanmaz/işlenmez (mesaj gövdesi
hariç); mesaja yalnızca bağlantı kimliği ve şiddet yazılır, ham sensör verisi
gönderilmez.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

import requests

TELEGRAM_API_BASE = "https://api.telegram.org"


@dataclass
class TelegramChannel:
    bot_token: str
    chat_id: str
    timeout_s: float = 10.0

    @classmethod
    def from_env(cls) -> "TelegramChannel":
        token = os.environ.get("TELEGRAM_BOT_TOKEN")
        chat_id = os.environ.get("TELEGRAM_CHAT_ID")
        if not token or not chat_id:
            raise RuntimeError("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID ortam değişkenleri eksik")
        return cls(bot_token=token, chat_id=chat_id)

    def send(self, text: str) -> dict:
        url = f"{TELEGRAM_API_BASE}/bot{self.bot_token}/sendMessage"
        resp = requests.post(url, json={"chat_id": self.chat_id, "text": text}, timeout=self.timeout_s)
        resp.raise_for_status()
        return resp.json()
