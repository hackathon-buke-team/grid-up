"""K2 2.1 -- real broker end-to-end test (CLAUDE.md P1 item).

Every test here runs a REAL MQTT broker as a separate OS process
(tools/run_amqtt_broker.py, subprocess.Popen) and a real paho-mqtt client
talking to it over a real TCP socket on 127.0.0.1 -- no mocks, no fakes.

Why amqtt and not Eclipse Mosquitto: see tools/run_amqtt_broker.py's
docstring and docs/01-MIMARI.md -- the official Windows Mosquitto installer
requires UAC elevation, which is not obtainable in this non-interactive
session (verified twice, see docs). amqtt is a real, independent MQTT 3.1.1
protocol implementation; the client side has no idea it isn't Mosquitto.

Scenarios (CLAUDE.md K2 2.1):
  1. connect            -- real TCP + real CONNACK, real pub/sub round trip
  2. reconnect          -- underlying socket dropped while broker stays up,
                            paho's own reconnect loop restores the session
  3. broker restart     -- the broker OS process itself is killed and a new
                            one started on the same port (different PID)
  4. outbox replay      -- envelopes queued in panogoz.store.Outbox while
                            no broker is reachable get flushed in order once
                            one comes up
  5. duplicate dropped  -- the same envelope delivered twice (simulating a
                            QoS1 redelivery) is only processed once, per
                            panogoz.store.Watermark's forward-only sequence
"""
from __future__ import annotations

import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

from panogoz.bus.envelope import Envelope
from panogoz.bus.mqtt_bus import MqttBus
from panogoz.contracts.channels import ChannelKind, Phase, Reading
from panogoz.store.outbox import Outbox
from panogoz.store.watermark import Watermark

REPO_ROOT = Path(__file__).resolve().parents[1]
BROKER_SCRIPT = REPO_ROOT / "tools" / "run_amqtt_broker.py"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _start_broker(port: int, *, timeout: float = 10.0) -> subprocess.Popen:
    proc = subprocess.Popen(
        [sys.executable, str(BROKER_SCRIPT), "--port", str(port)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            output = proc.stdout.read() if proc.stdout else ""
            raise RuntimeError(f"broker process exited early (code {proc.returncode}): {output}")
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return proc
        except OSError:
            time.sleep(0.2)
    proc.terminate()
    raise TimeoutError(f"broker did not start listening on port {port} within {timeout}s")


def _stop_broker(proc: subprocess.Popen) -> None:
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)


def _reading(seq: int) -> Reading:
    return Reading(t_s=float(seq), connection_id="F01-L1", kind=ChannelKind.CURRENT, value=100.0 + seq, phase=Phase.L1)


@pytest.fixture
def broker_port() -> int:
    return _free_port()


@pytest.fixture
def broker(broker_port):
    proc = _start_broker(broker_port)
    yield proc, broker_port
    _stop_broker(proc)


def test_connect_real_broker_and_roundtrip(broker):
    proc, port = broker
    bus = MqttBus("127.0.0.1", port, client_id="test-connect")
    bus.connect(timeout=10)
    assert bus.is_connected()

    received: list[Envelope] = []
    bus.subscribe("panogoz/test/connect", lambda topic, env: received.append(env))
    time.sleep(0.3)  # let the SUBSCRIBE ack land

    env = Envelope(seq=1, device_id="TC-01", reading=_reading(1))
    ok = bus.publish("panogoz/test/connect", env)
    assert ok is True

    deadline = time.time() + 5
    while not received and time.time() < deadline:
        time.sleep(0.1)

    assert len(received) == 1
    assert received[0].seq == 1
    assert received[0].device_id == "TC-01"
    assert received[0].reading.value == pytest.approx(101.0)

    bus.disconnect()


def test_reconnect_after_socket_drop(broker):
    """Broker process stays alive; only the TCP connection is severed --
    paho's own network loop must notice and reconnect without the test
    calling connect() again."""
    proc, port = broker
    bus = MqttBus("127.0.0.1", port, client_id="test-reconnect")
    bus.connect(timeout=10)
    assert bus.is_connected()

    # Force-close the live socket from underneath paho (public API: Client.socket()).
    sock = bus._client.socket()
    assert sock is not None
    sock.close()

    deadline = time.time() + 5
    while bus.is_connected() and time.time() < deadline:
        time.sleep(0.1)
    assert not bus.is_connected(), "client did not notice the dropped socket"

    deadline = time.time() + 10
    while not bus.is_connected() and time.time() < deadline:
        time.sleep(0.2)
    assert bus.is_connected(), "client did not reconnect on its own after the socket drop"

    # prove the reconnected session actually works, not just the flag
    received: list[Envelope] = []
    bus.subscribe("panogoz/test/reconnect", lambda topic, env: received.append(env))
    time.sleep(0.3)
    bus.publish("panogoz/test/reconnect", Envelope(seq=1, device_id="TC-01", reading=_reading(1)))
    deadline = time.time() + 5
    while not received and time.time() < deadline:
        time.sleep(0.1)
    assert len(received) == 1

    bus.disconnect()


def test_broker_process_restart(broker_port):
    """The broker OS process itself is killed and a new one started on the
    same port -- two genuinely different PIDs -- and the client reconnects
    to the new process on its own."""
    proc1 = _start_broker(broker_port)
    pid1 = proc1.pid
    try:
        bus = MqttBus("127.0.0.1", broker_port, client_id="test-restart")
        bus.connect(timeout=10)
        assert bus.is_connected()

        _stop_broker(proc1)
        deadline = time.time() + 5
        while bus.is_connected() and time.time() < deadline:
            time.sleep(0.1)
        assert not bus.is_connected(), "client did not notice the broker process dying"

        proc2 = _start_broker(broker_port)
        pid2 = proc2.pid
        assert pid1 != pid2, "restarted broker somehow got the same PID"
        try:
            deadline = time.time() + 10
            while not bus.is_connected() and time.time() < deadline:
                time.sleep(0.2)
            assert bus.is_connected(), "client did not reconnect to the restarted broker process"

            received: list[Envelope] = []
            bus.subscribe("panogoz/test/restart", lambda topic, env: received.append(env))
            time.sleep(0.3)
            bus.publish("panogoz/test/restart", Envelope(seq=1, device_id="TC-01", reading=_reading(1)))
            deadline = time.time() + 5
            while not received and time.time() < deadline:
                time.sleep(0.1)
            assert len(received) == 1

            bus.disconnect()
        finally:
            _stop_broker(proc2)
    finally:
        if proc1.poll() is None:
            _stop_broker(proc1)


def test_outbox_replay_after_downtime(broker_port):
    """No broker is reachable while envelopes are produced -- they are
    queued in the SQLite outbox; once a broker comes up, they are flushed
    in sequence order and the outbox is drained."""
    with tempfile.TemporaryDirectory() as tmp:
        db_path = str(Path(tmp) / "outbox.sqlite3")
        outbox = Outbox(db_path)
        topic = "panogoz/test/replay"

        # "no broker reachable" -- queue 3 readings while disconnected
        for seq in (1, 2, 3):
            env = Envelope(seq=seq, device_id="TC-01", reading=_reading(seq))
            outbox.enqueue(seq, topic, env.to_json())

        assert len(outbox.pending()) == 3

        proc = _start_broker(broker_port)
        try:
            bus = MqttBus("127.0.0.1", broker_port, client_id="test-replay")
            bus.connect(timeout=10)

            received: list[Envelope] = []
            bus.subscribe(topic, lambda t, env: received.append(env))
            time.sleep(0.3)

            for seq, stored_topic, payload in outbox.pending():
                env = Envelope.from_json(payload)
                ok = bus.publish(stored_topic, env)
                assert ok is True
                outbox.mark_delivered(seq)

            deadline = time.time() + 5
            while len(received) < 3 and time.time() < deadline:
                time.sleep(0.1)

            assert [e.seq for e in received] == [1, 2, 3]
            assert outbox.pending() == []

            bus.disconnect()
        finally:
            _stop_broker(proc)
        outbox.close()


def test_duplicate_delivery_dropped_by_watermark(broker):
    """The same envelope (same device_id+seq) delivered twice over the real
    broker -- simulating a QoS1 redelivery -- must only be processed once
    by a consumer applying panogoz.store.Watermark's forward-only check."""
    proc, port = broker
    with tempfile.TemporaryDirectory() as tmp:
        db_path = str(Path(tmp) / "watermark.sqlite3")
        watermark = Watermark(db_path)
        processed: list[Envelope] = []

        def on_message(topic: str, env: Envelope) -> None:
            if watermark.should_process(env.device_id, env.seq):
                processed.append(env)

        bus = MqttBus("127.0.0.1", port, client_id="test-dedup")
        bus.connect(timeout=10)
        topic = "panogoz/test/dedup"
        bus.subscribe(topic, on_message)
        time.sleep(0.3)

        env = Envelope(seq=7, device_id="TC-01", reading=_reading(7))
        assert bus.publish(topic, env) is True
        assert bus.publish(topic, env) is True  # redelivery of the identical envelope

        deadline = time.time() + 5
        while len(processed) < 1 and time.time() < deadline:
            time.sleep(0.1)
        time.sleep(0.5)  # give a stray second delivery a chance to (wrongly) land

        assert len(processed) == 1, f"expected exactly 1 processed envelope, got {len(processed)}"
        assert processed[0].seq == 7

        bus.disconnect()
        watermark.close()
