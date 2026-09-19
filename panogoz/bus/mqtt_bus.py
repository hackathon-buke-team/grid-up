"""Real MQTT bus (Paho, QoS1) -- see CLAUDE.md Sec.2/Sec.3. Same Bus
interface as InProcBus (panogoz.bus.inproc), so store/detector wiring is
transport-agnostic.

Reconnection: paho's own network loop thread (`loop_start()` +
`reconnect_delay_set()`) retries the TCP connection on its own after a
drop; this class just tracks connected/disconnected state via the
on_connect/on_disconnect callbacks and re-issues subscriptions on every
(re)connect, since a non-persistent MQTT session drops them.
"""
from __future__ import annotations

import ssl
import threading

import paho.mqtt.client as mqtt

from panogoz.bus.envelope import Envelope
from panogoz.bus.interface import OnMessage


class MqttBus:
    def __init__(
        self,
        host: str,
        port: int,
        *,
        client_id: str | None = None,
        keepalive: int = 5,
        tls_ca: str | None = None,
        tls_cert: str | None = None,
        tls_key: str | None = None,
    ) -> None:
        """`tls_ca` verilirse bağlantı TLS'tir: sunucu sertifikası bu CA'ya karşı DOĞRULANIR (ana bilgisayar
        adı dahil, `tls_insecure` yok). `tls_cert`+`tls_key` = istemci sertifikası (karşılıklı TLS; cihaz
        kimliği = sertifika CN'i, bkz. panogoz/bus/topics.py)."""
        self._host = host
        self._port = port
        self._keepalive = keepalive
        self._client = mqtt.Client(
            client_id=client_id,
            protocol=mqtt.MQTTv311,
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        )
        if tls_ca:
            self._client.tls_set(
                ca_certs=tls_ca,
                certfile=tls_cert,
                keyfile=tls_key,
                cert_reqs=ssl.CERT_REQUIRED,
                tls_version=ssl.PROTOCOL_TLS_CLIENT,
            )
            self._client.tls_insecure_set(False)
        elif tls_cert or tls_key:
            raise ValueError("istemci sertifikası için tls_ca da verilmeli")
        self._client.reconnect_delay_set(min_delay=1, max_delay=4)
        self._client.on_connect = self._handle_connect
        self._client.on_disconnect = self._handle_disconnect
        self._client.on_message = self._handle_message

        self._connected = threading.Event()
        self._subscriptions: dict[str, OnMessage] = {}
        self._lock = threading.Lock()

    def connect(self, *, timeout: float = 10.0) -> None:
        self._client.connect(self._host, self._port, self._keepalive)
        self._client.loop_start()
        if not self._connected.wait(timeout=timeout):
            raise TimeoutError(f"MQTT connect to {self._host}:{self._port} timed out after {timeout}s")

    def disconnect(self) -> None:
        self._client.loop_stop()
        self._client.disconnect()
        self._connected.clear()

    def is_connected(self) -> bool:
        return self._connected.is_set()

    def publish(self, topic: str, envelope: Envelope, *, qos: int = 1) -> bool:
        if not self._connected.is_set():
            return False
        info = self._client.publish(topic, envelope.to_json(), qos=qos)
        info.wait_for_publish(timeout=5)
        return info.is_published()

    def subscribe(self, topic: str, on_message: OnMessage) -> None:
        with self._lock:
            self._subscriptions[topic] = on_message
        if self._connected.is_set():
            self._client.subscribe(topic, qos=1)

    def _handle_connect(self, client, userdata, flags, reason_code, properties=None) -> None:
        self._connected.set()
        with self._lock:
            topics = list(self._subscriptions.keys())
        for topic in topics:
            client.subscribe(topic, qos=1)

    def _handle_disconnect(self, client, userdata, flags, reason_code, properties=None) -> None:
        self._connected.clear()

    def _handle_message(self, client, userdata, msg) -> None:
        with self._lock:
            callback = self._subscriptions.get(msg.topic)
        if callback is not None:
            callback(msg.topic, Envelope.from_json(msg.payload))
