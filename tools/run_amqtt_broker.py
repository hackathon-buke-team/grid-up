"""Runs a real MQTT broker as a standalone OS process on 127.0.0.1:<port>.

Used by tests/test_bus_mqtt_e2e.py (and can be used manually) to exercise
panogoz/bus + panogoz/store against a real, separate-process MQTT broker
speaking the real MQTT 3.1.1 wire protocol over a real TCP socket.

Why amqtt instead of Eclipse Mosquitto: CLAUDE.md K2 2.1 asks for "gercek
Mosquitto". On this machine the official Windows Mosquitto installer
requires UAC elevation (verified twice: a bare `/S` silent-install attempt
hung for 600s with no interactive prompt to answer, and a PowerShell
Start-Process attempt returned "Islem kullanici tarafindan iptal edildi" --
Windows auto-declining the elevation request in this non-interactive
session) and there is no portable/zip distribution on mosquitto.org for
Windows. amqtt is a real MQTT protocol implementation (real CONNECT/
CONNACK/PUBLISH/PUBACK/SUBSCRIBE frames over a real socket, real QoS1) that
installs with plain `pip install amqtt` and runs as an ordinary Python
process with no elevation -- the paho-mqtt client on the other end cannot
tell the difference. See docs/01-MIMARI.md for the full story.

Prints "AMQTT_BROKER_READY port=<port>" to stdout once the listener is
actually bound and accepting connections, then blocks forever until killed.
"""
from __future__ import annotations

import argparse
import asyncio
import logging

from amqtt.broker import Broker
from amqtt.contexts import BrokerConfig, ListenerConfig


async def _run(port: int) -> None:
    config = BrokerConfig()
    config.listeners = {"default": ListenerConfig(bind=f"127.0.0.1:{port}")}
    broker = Broker(config)
    await broker.start()
    print(f"AMQTT_BROKER_READY port={port}", flush=True)
    try:
        await asyncio.Event().wait()
    finally:
        await broker.shutdown()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING)
    asyncio.run(_run(args.port))


if __name__ == "__main__":
    main()
