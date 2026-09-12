"""Konsol/test kanalı — gerçek kanal yokken veya testlerde kullanılır."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ConsoleChannel:
    sent: list = field(default_factory=list)

    def send(self, text: str) -> dict:
        self.sent.append(text)
        print(f"[NOTIFY] {text}")
        return {"ok": True}
