"""Twilio REST API üzerinden gerçek SMS bildirim kanalı (K4 §4.1 — ikinci kanal).

Seçim gerekçesi: Textbelt'in ücretsiz katmanı günde tek mesajla sınırlı, demo
provasında tekrarlanan gerçek testi imkansız kılıyor. Twilio deneme hesabı
(kart doğrulamalı ama ücretsiz kredili) sınırsız tekrar testine izin veriyor —
hackathon süresince tercih edilen budur. On-prem kısıtına Telegram kanalıyla
aynı gerekçeyle uyar: sunucudan yalnızca tek yönlü dışa HTTPS POST çağrısı
yapılır (Twilio SDK'sı değil, doğrudan `requests` ile Basic Auth), hiçbir
sensör verisi taşınmaz — yalnız bağlantı kimliği, şiddet ve onay token'ı.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

import requests

TWILIO_API_BASE = "https://api.twilio.com/2010-04-01"


@dataclass
class TwilioSmsChannel:
    account_sid: str
    auth_token: str
    from_number: str
    to_number: str
    timeout_s: float = 10.0

    @classmethod
    def from_env(cls) -> "TwilioSmsChannel":
        account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
        auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
        from_number = os.environ.get("TWILIO_FROM_NUMBER")
        to_number = os.environ.get("TWILIO_TO_NUMBER")
        missing = [
            name
            for name, value in [
                ("TWILIO_ACCOUNT_SID", account_sid),
                ("TWILIO_AUTH_TOKEN", auth_token),
                ("TWILIO_FROM_NUMBER", from_number),
                ("TWILIO_TO_NUMBER", to_number),
            ]
            if not value
        ]
        if missing:
            raise RuntimeError(f"Eksik ortam değişkenleri: {', '.join(missing)}")
        return cls(account_sid=account_sid, auth_token=auth_token, from_number=from_number, to_number=to_number)

    def send(self, text: str) -> dict:
        url = f"{TWILIO_API_BASE}/Accounts/{self.account_sid}/Messages.json"
        resp = requests.post(
            url,
            data={"From": self.from_number, "To": self.to_number, "Body": text},
            auth=(self.account_sid, self.auth_token),
            timeout=self.timeout_s,
        )
        resp.raise_for_status()
        return resp.json()
