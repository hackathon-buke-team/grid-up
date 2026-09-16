"""Common interface both the in-proc bus and the real MQTT bus implement,
so callers (store/detector wiring) don't care which transport is behind it
-- see CLAUDE.md Sec.2: "in-proc bus / MQTT ayni arayuz arkasinda"."""
from __future__ import annotations

from typing import Callable, Protocol

from panogoz.bus.envelope import Envelope

OnMessage = Callable[[str, Envelope], None]


class Bus(Protocol):
    def connect(self) -> None: ...

    def disconnect(self) -> None: ...

    def is_connected(self) -> bool: ...

    def publish(self, topic: str, envelope: Envelope, *, qos: int = 1) -> bool:
        """Returns True if the message was actually handed to the transport
        (delivered, for in-proc; acked/queued for send, for MQTT). Returns
        False if the transport is currently disconnected -- the caller
        (see panogoz.store.outbox) is expected to persist it for replay."""
        ...

    def subscribe(self, topic: str, on_message: OnMessage) -> None: ...
