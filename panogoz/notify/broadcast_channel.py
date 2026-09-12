"""Aynı mesajı birden fazla kanala (ör. kişisel sohbet + grup) dağıtır."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class BroadcastChannel:
    channels: list = field(default_factory=list)

    def send(self, text: str) -> list:
        return [c.send(text) for c in self.channels]
