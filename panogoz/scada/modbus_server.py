"""Bağlantı anlık durumlarından gerçek bir Modbus TCP slave (yalnız okuma) kurar.

pymodbus'un ModbusTcpServer'ı kullanılır; register'lar yalnızca "Input Register"
(function code 04) bloğuna yazılır, "Holding Register" bloğu kasten boş bırakılır
— böylece bir master hiçbir şeyi yazamaz, yalnızca okuyabilir.
"""
from __future__ import annotations

import asyncio
import threading

from pymodbus.datastore import ModbusDeviceContext, ModbusSequentialDataBlock, ModbusServerContext
from pymodbus.server import ModbusTcpServer

from panogoz.scada.register_map import ConnectionSnapshot, REGISTERS_PER_CONNECTION, connection_base_address


def build_context(snapshots_by_index: dict[int, ConnectionSnapshot], *, register_count: int | None = None) -> ModbusServerContext:
    """connection_index -> ConnectionSnapshot eşlemesinden bir Modbus veri deposu kurar."""
    if register_count is None:
        max_index = max(snapshots_by_index, default=0)
        register_count = connection_base_address(max_index + 1)

    values = [0] * register_count
    for index, snapshot in snapshots_by_index.items():
        base = connection_base_address(index)
        for offset, register_value in enumerate(snapshot.to_registers()):
            values[base + offset] = register_value

    # ModbusSequentialDataBlock, verilen adresi dahili olarak 1 azaltıyor (pymodbus
    # 3.15 SimData uyumluluğu) — PDU adresi 0'dan başlasın diye burada 1 veriyoruz.
    input_registers = ModbusSequentialDataBlock(1, values)
    device_context = ModbusDeviceContext(ir=input_registers)
    return ModbusServerContext(devices=device_context, single=True)


def run_standalone(snapshots_by_index: dict[int, ConnectionSnapshot], *, host: str = "0.0.0.0", port: int = 5020) -> None:
    """Bloklayan, tek seferlik sunucu — bağımsız bir script'ten (tools/) çağırmak için."""
    from pymodbus.server import StartTcpServer

    context = build_context(snapshots_by_index)
    StartTcpServer(context, address=(host, port))


async def _serve(context: ModbusServerContext, host: str, port: int, holder: dict, ready: threading.Event) -> None:
    # ModbusTcpServer'ın __init__'i asyncio.get_running_loop() çağırıyor; bu yüzden
    # nesne bir event loop'un GERÇEKTEN çalıştığı bir coroutine içinde kurulmalı.
    server = ModbusTcpServer(context, address=(host, port))
    holder["server"] = server
    ready.set()
    await server.serve_forever()


def run_in_background_thread(
    snapshots_by_index: dict[int, ConnectionSnapshot], *, host: str = "0.0.0.0", port: int = 5020
) -> tuple[ModbusTcpServer, threading.Thread, asyncio.AbstractEventLoop]:
    """Modbus TCP sunucusunu kendi event loop'unda ayrı bir thread'de çalıştırır (testler ve demo için)."""
    context = build_context(snapshots_by_index)
    loop = asyncio.new_event_loop()
    holder: dict[str, ModbusTcpServer] = {}
    ready = threading.Event()

    def _run() -> None:
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_serve(context, host, port, holder, ready))

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    if not ready.wait(timeout=5.0):
        raise RuntimeError("Modbus sunucusu zaman aşımında başlamadı")
    return holder["server"], thread, loop


def stop_background_server(
    server: ModbusTcpServer, thread: threading.Thread, loop: asyncio.AbstractEventLoop, *, timeout: float = 5.0
) -> None:
    asyncio.run_coroutine_threadsafe(server.shutdown(), loop).result(timeout=timeout)
    thread.join(timeout=timeout)
