"""Filo için CANLI Modbus TCP slave (ICD v2.0): register'lar her okumada filo servisinden hesaplanır.

Statik anlık görüntü (modbus_server.py, v1) yerine `SimDevice.action` kullanılır: master
bir FC04 okuması yaptığında önce simülasyon saati ilerletilir, sonra istenen aralık
`fleet_bridge.all_registers`'tan doldurulur. Böylece SCADA, konsolla AYNI anda AYNI değeri
görür. Yazma (FC06/16), Holding Register (FC03), Coil/DI okuması reddedilir: salt okunur.
"""
from __future__ import annotations

import asyncio
import threading
from typing import TYPE_CHECKING

from pymodbus.constants import ExcCodes
from pymodbus.server import ModbusTcpServer
from pymodbus.simulator import DataType, SimData, SimDevice

from panogoz.scada import icd
from panogoz.scada.fleet_bridge import all_registers

if TYPE_CHECKING:
    from panogoz.api.fleet_service import FleetService

READ_INPUT_REGISTERS = 4


def build_device(service: "FleetService", *, unit_id: int = 1) -> SimDevice:
    total = len(service.panels) * icd.BLOCK_SIZE

    async def action(function_code, start_address, address, count, current_registers, set_values):
        if set_values is not None:
            return ExcCodes.ILLEGAL_FUNCTION  # salt okunur
        if function_code != READ_INPUT_REGISTERS:
            return ExcCodes.ILLEGAL_FUNCTION  # FC03 (holding) vb. boş
        live = all_registers(service)
        for k in range(len(current_registers)):
            addr = start_address + k
            current_registers[k] = live[addr] if 0 <= addr < len(live) else 0
        return None

    bits = [SimData(0, count=16, values=False, datatype=DataType.BITS, readonly=True)]  # coil/DI: action reddeder
    holding = [SimData(0, count=1, datatype=DataType.INVALID)]  # FC03: tanımsız adres
    input_regs = [SimData(0, count=total, values=0, datatype=DataType.REGISTERS, readonly=True)]
    return SimDevice(unit_id, simdata=(list(bits), list(bits), holding, input_regs), action=action)


class FleetModbusServer:
    def __init__(self, service: "FleetService", *, host: str = "0.0.0.0", port: int = 5020, unit_id: int = 1) -> None:
        self.service, self.host, self.port, self.unit_id = service, host, port, unit_id
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._server: ModbusTcpServer | None = None

    def start(self, timeout: float = 5.0) -> "FleetModbusServer":
        ready = threading.Event()
        holder: dict = {}

        async def serve() -> None:
            server = ModbusTcpServer(build_device(self.service, unit_id=self.unit_id), address=(self.host, self.port))
            holder["server"] = server
            ready.set()
            await server.serve_forever()

        def run() -> None:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            try:
                self._loop.run_until_complete(serve())
            except asyncio.CancelledError:
                pass

        self._thread = threading.Thread(target=run, daemon=True, name="panogoz-modbus")
        self._thread.start()
        if not ready.wait(timeout):
            raise RuntimeError("Modbus sunucusu zaman aşımında başlamadı")
        self._server = holder["server"]
        return self

    def stop(self, timeout: float = 5.0) -> None:
        if self._server is not None and self._loop is not None:
            asyncio.run_coroutine_threadsafe(self._server.shutdown(), self._loop).result(timeout=timeout)
        if self._thread is not None:
            self._thread.join(timeout=timeout)
