"""Konsol/dev kanalı - testlerde ve gerçek kanal yokken kullanılır."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ConsoleChannel:
    sent: list = field(default_factory=list)

    def send(self, text: str) -> dict:
        self.sent.append(text)
        print(f"[NOTIFY] {text}")
        return {"ok": True}
