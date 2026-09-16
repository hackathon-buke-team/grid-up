"""In-process bus: synchronous, in-memory pub/sub, no network. Used by
dev/test code paths that want the same Bus interface as the real MQTT bus
without needing a broker (see CLAUDE.md Sec.2/Sec.3)."""
from __future__ import annotations

from panogoz.bus.envelope import Envelope
from panogoz.bus.interface import OnMessage


class InProcBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[OnMessage]] = {}
        self._connected = True

    def connect(self) -> None:
        self._connected = True

    def disconnect(self) -> None:
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def publish(self, topic: str, envelope: Envelope, *, qos: int = 1) -> bool:
        if not self._connected:
            return False
        for cb in self._subscribers.get(topic, []):
            cb(topic, envelope)
        return True

    def subscribe(self, topic: str, on_message: OnMessage) -> None:
        self._subscribers.setdefault(topic, []).append(on_message)
