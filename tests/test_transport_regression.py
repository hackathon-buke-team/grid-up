"""Transport contracts: broker acceptance and restart-safe gateway replay."""
from types import SimpleNamespace
import pytest
from paho.mqtt.packettypes import PacketTypes
from paho.mqtt.reasoncodes import ReasonCode

from panogoz.bus.bus import MqttBus
from panogoz.contracts.envelope import Envelope
from panogoz.gateway.gateway import Gateway
from panogoz.store.db import Store


def envelope(seq=1):
    return Envelope(kind='data', site='Review', panel='REVIEW-1', device='GW-01',
                    ts=1700000000 + seq, seq=seq, boot=1,
                    values={'mpr.i_l1_a': 100.0})


def connected_bus(monkeypatch):
    bus = MqttBus()
    bus._on_connect(bus._client, None, {}, ReasonCode(PacketTypes.CONNACK, identifier=0))
    mids = iter(range(1, 100))
    monkeypatch.setattr(bus._client, 'publish',
                        lambda *a, **kw: SimpleNamespace(rc=0, mid=next(mids)))
    return bus


def test_paho_success_and_rejection_control_connection_state():
    bus = MqttBus()
    bus._on_connect(bus._client, None, {}, ReasonCode(PacketTypes.CONNACK, identifier=0))
    assert bus.connected
    bus._on_connect(bus._client, None, {}, ReasonCode(PacketTypes.CONNACK, identifier=135))
    assert not bus.connected


def test_disconnected_mqtt_keeps_gateway_message():
    gateway = Gateway(panel_key='REVIEW-1', site='Review', bus=MqttBus())
    gateway._emit(envelope())
    assert len(gateway.buffer) == 1
    assert gateway.published == 0


def test_gateway_retires_only_after_positive_puback(monkeypatch):
    bus = connected_bus(monkeypatch)
    gateway = Gateway(panel_key='REVIEW-1', site='Review', bus=bus)
    gateway._emit(envelope())
    assert len(gateway.buffer) == 1
    bus._on_publish(bus._client, None, 1, ReasonCode(PacketTypes.PUBACK, identifier=0))
    gateway.drain()
    assert len(gateway.buffer) == 0
    assert gateway.published == 1


def test_rejected_puback_does_not_retire_message(monkeypatch):
    bus = connected_bus(monkeypatch)
    gateway = Gateway(panel_key='REVIEW-1', site='Review', bus=bus)
    gateway._emit(envelope())
    bus._on_publish(bus._client, None, 1, ReasonCode(PacketTypes.PUBACK, identifier=135))
    gateway.drain()
    assert len(gateway.buffer) == 1
    assert gateway.published == 0


def test_gateway_restores_pending_message_and_retain_after_restart(tmp_path):
    path = tmp_path / 'gateway.db'
    store = Store(path)
    gateway = Gateway(panel_key='REVIEW-1', site='Review', bus=MqttBus(), outbox_store=store)
    gateway._emit(envelope(), retain=True)
    store.close()
    store = Store(path)
    delivered = []
    class RecordingBus:
        def publish_envelope(self, env, retain=False):
            delivered.append((env.seq, retain))
    gateway = Gateway(panel_key='REVIEW-1', site='Review', bus=RecordingBus(), outbox_store=store)
    gateway.drain()
    assert delivered == [(1, True)]
    store.close()
    store = Store(path)
    gateway = Gateway(panel_key='REVIEW-1', site='Review', bus=RecordingBus(), outbox_store=store)
    assert len(gateway.buffer) == 0
    store.close()


def test_persistent_queue_refuses_overflow_without_dropping_head(tmp_path):
    store = Store(tmp_path / 'gateway.db')
    gateway = Gateway(panel_key='REVIEW-1', site='Review', bus=MqttBus(),
                      outbox_store=store, buffer_size=1)
    gateway._emit(envelope(1))
    with pytest.raises(BufferError):
        gateway._emit(envelope(2))
    assert [env.seq for env in gateway.buffer] == [1]
    store.close()


def test_postgres_dsn_is_rejected_before_creating_paths():
    with pytest.raises(ValueError, match='SQLite'):
        Store('postgresql://localhost/panogoz')
