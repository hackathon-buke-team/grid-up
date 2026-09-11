"""Message transport.

Two drivers behind one interface:

* **inproc** - an in-process publish/subscribe bus.  Default.  Same envelopes,
  same topics, same wildcard matching, no broker to install.  This is what makes
  the demo start with one command on a laptop with no Docker.
* **mqtt** - Mosquitto over MQTT 5 with TLS and per-device certificates.  The
  documented production path, used by ``docker compose up``.

Selected by ``PANOGOZ_BUS``: ``inproc`` (default) or ``mqtt://host:port``.

The topic grammar and the wildcard rules are MQTT's in both drivers, so code
written against the in-process bus works unchanged against a real broker.  That
matters: a fallback that behaves differently from the real thing is not a
fallback, it is a second system to debug on stage.
"""

from __future__ import annotations

import os
import queue
import threading
import time
from typing import Callable, Iterable

from panogoz.contracts.envelope import Envelope

Handler = Callable[[str, bytes], None]


class PublishReceipt:
    """A broker acknowledgement, including MQTT 5 negative acknowledgements."""

    def __init__(self) -> None:
        self._done = threading.Event()
        self.error: str | None = None

    def finish(self, error: str | None = None) -> None:
        self.error = error
        self._done.set()

    def is_published(self) -> bool:
        if not self._done.is_set():
            return False
        if self.error:
            raise ConnectionError(self.error)
        return True


def _topic_matches(filt: str, topic: str) -> bool:
    """MQTT topic filter matching, including ``+`` and ``#``."""
    f = filt.split("/")
    t = topic.split("/")
    for i, part in enumerate(f):
        if part == "#":
            return i <= len(t)
        if i >= len(t):
            return False
        if part != "+" and part != t[i]:
            return False
    return len(f) == len(t)


class Bus:
    """Common interface."""

    def publish(self, topic: str, payload: bytes, retain: bool = False, qos: int = 1) -> None:
        raise NotImplementedError

    def subscribe(self, topic_filter: str, handler: Handler) -> None:
        raise NotImplementedError

    def publish_envelope(self, env: Envelope, retain: bool = False) -> PublishReceipt | None:
        return self.publish(env.topic, env.to_json(), retain=retain)

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    @property
    def kind(self) -> str:
        return "?"


class InProcBus(Bus):
    """Thread-safe in-process bus with a delivery worker per subscription.

    Delivery is asynchronous, exactly as a broker's would be, so a slow
    subscriber cannot block a publisher.  Queues are bounded; a subscriber that
    falls behind drops the oldest message and increments ``dropped``, which is
    reported rather than hidden.
    """

    def __init__(self, maxsize: int = 20000) -> None:
        self._subs: list[tuple[str, Handler, queue.Queue]] = []
        self._retained: dict[str, bytes] = {}
        self._lock = threading.RLock()
        self._threads: list[threading.Thread] = []
        self._running = False
        self._maxsize = maxsize
        self.published = 0
        self.delivered = 0
        self.dropped = 0

    @property
    def kind(self) -> str:
        return "inproc"

    def start(self) -> None:
        self._running = True

    def stop(self) -> None:
        self._running = False
        with self._lock:
            for _, _, q in self._subs:
                try:
                    q.put_nowait(None)
                except queue.Full:
                    pass
        for t in self._threads:
            t.join(timeout=1.0)

    def subscribe(self, topic_filter: str, handler: Handler) -> None:
        q: queue.Queue = queue.Queue(maxsize=self._maxsize)
        with self._lock:
            self._subs.append((topic_filter, handler, q))
            retained = [(t, p) for t, p in self._retained.items() if _topic_matches(topic_filter, t)]
        self._running = True

        def worker() -> None:
            while True:
                item = q.get()
                if item is None:
                    return
                topic, payload = item
                try:
                    handler(topic, payload)
                    self.delivered += 1
                except Exception as exc:  # noqa: BLE001 - a bad handler must not kill the bus
                    print(f"[bus] handler error on {topic}: {exc!r}")

        t = threading.Thread(target=worker, name=f"bus:{topic_filter}", daemon=True)
        t.start()
        self._threads.append(t)

        for topic, payload in retained:
            q.put((topic, payload))

    def publish(self, topic: str, payload: bytes, retain: bool = False, qos: int = 1) -> None:
        self.published += 1
        with self._lock:
            if retain:
                self._retained[topic] = payload
            targets = [q for f, _, q in self._subs if _topic_matches(f, topic)]
        for q in targets:
            try:
                q.put_nowait((topic, payload))
            except queue.Full:
                try:
                    q.get_nowait()
                    q.put_nowait((topic, payload))
                    self.dropped += 1
                except queue.Empty:  # pragma: no cover
                    pass

    def stats(self) -> dict:
        return {
            "kind": "inproc",
            "published": self.published,
            "delivered": self.delivered,
            "dropped": self.dropped,
            "subscriptions": len(self._subs),
            "backlog": sum(q.qsize() for _, _, q in self._subs),
        }


class MqttBus(Bus):
    """Mosquitto / MQTT 5 driver.

    Uses paho-mqtt v2 callbacks.  Store-and-forward at the gateway sits above
    this class and advances its watermark on PUBACK, which is exactly why we do
    not use Sparkplug B: Sparkplug 3.0 mandates QoS 0 for DDATA and a PUBACK
    watermark cannot exist there.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 1883, client_id: str = "",
                 username: str | None = None, password: str | None = None,
                 tls: dict | None = None) -> None:
        import paho.mqtt.client as mqtt  # imported lazily so sqlite-only runs need no paho

        self._mqtt = mqtt
        self.host, self.port = host, port
        self._subs: list[tuple[str, Handler]] = []
        self._client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=client_id or f"panogoz-{int(time.time() * 1000) % 100000}",
            protocol=mqtt.MQTTv5,
        )
        if username:
            self._client.username_pw_set(username, password)
        if tls:
            self._client.tls_set(**tls)
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        self._client.on_publish = self._on_publish
        self._client.on_disconnect = self._on_disconnect
        self._publish_lock = threading.RLock()
        self._pending: dict[int, PublishReceipt] = {}
        self._connection_result = threading.Event()
        self.published = 0
        self.delivered = 0
        self.connected = False

    @property
    def kind(self) -> str:
        return "mqtt"

    def _on_connect(self, client, userdata, flags, reason_code, properties=None) -> None:
        self.connected = reason_code == 0
        self._connection_result.set()
        if self.connected:
            for f, _ in self._subs:
                client.subscribe(f, qos=1)

    def _on_publish(self, client, userdata, mid, reason_code, properties=None) -> None:
        with self._publish_lock:
            receipt = self._pending.pop(mid, None)
            if receipt is not None:
                failure = getattr(reason_code, "is_failure", False)
                receipt.finish(f"MQTT PUBACK rejected: {reason_code}" if failure else None)

    def _on_disconnect(self, client, userdata, flags, reason_code, properties=None) -> None:
        self.connected = False
        with self._publish_lock:
            for receipt in self._pending.values():
                receipt.finish("MQTT disconnected before PUBACK")
            self._pending.clear()

    def _on_message(self, client, userdata, msg) -> None:
        self.delivered += 1
        for f, h in self._subs:
            if _topic_matches(f, msg.topic):
                try:
                    h(msg.topic, msg.payload)
                except Exception as exc:  # noqa: BLE001
                    print(f"[bus] handler error on {msg.topic}: {exc!r}")

    def start(self) -> None:
        self._connection_result.clear()
        self._client.connect(self.host, self.port, keepalive=30)
        self._client.loop_start()
        self._connection_result.wait(5.0)
        if not self.connected:
            self.stop()
            raise ConnectionError("MQTT connection rejected or timed out")

    def stop(self) -> None:
        self._client.loop_stop()
        try:
            self._client.disconnect()
        except Exception:  # noqa: BLE001
            pass
        self._on_disconnect(self._client, None, None, None)

    def subscribe(self, topic_filter: str, handler: Handler) -> None:
        self._subs.append((topic_filter, handler))
        if self.connected:
            self._client.subscribe(topic_filter, qos=1)

    def publish(self, topic: str, payload: bytes, retain: bool = False,
                qos: int = 1) -> PublishReceipt:
        if qos != 1:
            raise ValueError("Gateway delivery requires MQTT QoS 1")
        with self._publish_lock:
            if not self.connected:
                raise ConnectionError("MQTT broker is not connected")
            info = self._client.publish(topic, payload, qos=qos, retain=retain)
            if info.rc != self._mqtt.MQTT_ERR_SUCCESS:
                raise ConnectionError(f"MQTT publish failed: {info.rc}")
            receipt = PublishReceipt()
            self._pending[info.mid] = receipt
            self.published += 1
            return receipt

    def stats(self) -> dict:
        return {
            "kind": "mqtt",
            "host": f"{self.host}:{self.port}",
            "connected": self.connected,
            "published": self.published,
            "delivered": self.delivered,
            "subscriptions": len(self._subs),
        }


# --------------------------------------------------------------------------

_default: Bus | None = None


def make_bus(spec: str | None = None) -> Bus:
    spec = spec or os.environ.get("PANOGOZ_BUS", "inproc")
    if spec.startswith("mqtt://"):
        rest = spec[len("mqtt://"):]
        host, _, port = rest.partition(":")
        return MqttBus(host or "127.0.0.1", int(port or 1883))
    return InProcBus()


def get_bus() -> Bus:
    global _default
    if _default is None:
        _default = make_bus()
        _default.start()
    return _default


def set_bus(bus: Bus) -> None:
    global _default
    _default = bus
