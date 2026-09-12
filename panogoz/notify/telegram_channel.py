"""Telegram Bot API üzerinden gerçek bildirim kanalı (K4 §4.1).

Seçim gerekçesi: WhatsApp Business API ve Twilio, işletme onayı/telefon
doğrulaması gerektirir ve hackathon süresine sığmaz. Telegram Bot API
ücretsizdir, BotFather ile dakikalar içinde kurulur, gerçek push bildirimi
telefona düşürür ve on-prem kısıtına uyar: sunucudan yalnızca tek yönlü
dışa HTTPS çağrısı yapılır, hiçbir veri üçüncü tarafta saklanmaz/işlenmez
(mesaj içeriği dışında). Veri mahremiyeti: mesaj gövdesine yalnızca bağlantı
kimliği, şiddet ve onay token'ı yazılır; ham sensör verisi gönderilmez.
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


def fetch_latest_chat_id(bot_token: str) -> str | None:
    """Kullanıcı bota /start yazdıktan sonra chat_id'yi getUpdates ile bulur."""
    url = f"{TELEGRAM_API_BASE}/bot{bot_token}/getUpdates"
    resp = requests.get(url, timeout=10.0)
    resp.raise_for_status()
    updates = resp.json().get("result", [])
    if not updates:
        return None
    chat = updates[-1].get("message", {}).get("chat", {})
    return str(chat["id"]) if "id" in chat else None
