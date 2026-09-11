"""Serve the device simulators as real Modbus RTU slaves.

Why RTU framing over TCP
------------------------

The devices in a TEDAS LV panel speak Modbus **RTU** on RS-485: the ABB TVOC-2
at 19200 8E1 and the Entes MPR-53CS on its own port.  Windows has no ``socat``
and no free virtual serial pair, so instead of faking the protocol we keep the
protocol and change only the wire: pymodbus with ``framer=FramerType.RTU`` on a
TCP transport.

That is not a shortcut, it is the field topology.  A Moxa NPort, a Westermo, an
Advantech EKI - every serial device server in every substation in the Aegean -
carries exactly this: real RTU frames with real CRC-16, tunnelled over TCP.  The
bytes on this socket are the bytes on the twisted pair, CRC included.  What we
do not exercise is the RS-485 physical layer itself: bias resistors,
termination, the 3.5-character silent interval and the turnaround delay.  Those
are commissioning concerns and we say so rather than pretending a TCP socket
tested them.

Sparse blocks are the other half of the fidelity
------------------------------------------------

Both devices have unmapped holes in their register space - the TVOC-2's stride-7
log holes, its write-only register 213, the MPR-53CS's gap at 32772..32776.  A
sequential data block would answer those with a cheerful zero and the gateway
would never learn that its block plan was wrong.  We build the datastore from
sparse ``SimData`` runs, one run per contiguous stretch, so every hole answers
with exception 02 ILLEGAL_DATA_ADDRESS exactly as the hardware does.

One further detail: we hand the server a single shared register block per
device rather than separate holding and input blocks, because on both of these
devices FC 03 and FC 04 read **the same address space**.  Two blocks would let
them drift and would quietly hide a bug in any client that mixes the two.

Topologies
----------

Both are supported and both are demonstrated in the self-test:

* **one server, two slave ids** - the cheap way, one RS-485 pair, one port on
  the gateway.  Fine until a 266-register analyser read collides with the 1 Hz
  arc poll.
* **two servers, two ports** - what PANO GOZ actually specifies.  The arc relay
  gets its own isolated RS-485 port so that no analyser transaction, retry or
  timeout can ever delay the poll that tells us the relay is still answering.
"""

from __future__ import annotations

import asyncio
import warnings
from typing import Any, Protocol

from pymodbus import FramerType, pymodbus_apply_logging_config
from pymodbus.server import ModbusTcpServer
from pymodbus.simulator import DataType, SimData, SimDevice

#: pymodbus 3.15 logs every frame at DEBUG and warns loudly about the
#: SimData/SimDevice migration.  Both are noise on a demo console.
warnings.filterwarnings("ignore", message=".*SimData.*")
pymodbus_apply_logging_config("CRITICAL")

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 15020


class DeviceSim(Protocol):
    """What ``serve_devices`` needs from a simulator."""

    def block(self) -> dict[int, int]: ...


# --------------------------------------------------------------------------
# Sparse block construction
# --------------------------------------------------------------------------

def contiguous_runs(block: dict[int, int]) -> list[tuple[int, list[int]]]:
    """Split a sparse register dict into ``(start, values)`` contiguous runs.

    Each run becomes one ``SimData``.  Everything between runs stays INVALID,
    which is what makes a hole answer with exception 02.
    """
    if not block:
        return []
    addrs = sorted(block)
    runs: list[tuple[int, list[int]]] = []
    start = prev = addrs[0]
    vals = [block[start] & 0xFFFF]
    for a in addrs[1:]:
        if a == prev + 1:
            vals.append(block[a] & 0xFFFF)
            prev = a
        else:
            runs.append((start, vals))
            start = prev = a
            vals = [block[a] & 0xFFFF]
    runs.append((start, vals))
    return runs


def simdata_for(block: dict[int, int]) -> list[SimData]:
    return [
        SimData(start, values=values, datatype=DataType.REGISTERS)
        for start, values in contiguous_runs(block)
    ]


def _sim_device(slave_id: int, sim: DeviceSim) -> SimDevice:
    if slave_id <= 0:
        # SimCore falls back to device 0 for an unknown id, so an id of 0 would
        # turn every mis-addressed request into a plausible-looking answer from
        # the wrong device.  Refuse it.
        raise ValueError("slave id 0 is reserved (broadcast) and must not be served")
    return SimDevice(slave_id, simdata=simdata_for(sim.block()))


# --------------------------------------------------------------------------
# Server
# --------------------------------------------------------------------------

async def serve_devices(
    devices: dict[int, Any],
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
) -> ModbusTcpServer:
    """Start an RTU-framed Modbus server carrying ``{slave_id: sim}``.

    Returns the running server; the caller owns ``await server.shutdown()``.
    Prefer :class:`ModbusDeviceServer`, which owns it for you.
    """
    sim_devices = [_sim_device(sid, sim) for sid, sim in sorted(devices.items())]
    server = ModbusTcpServer(
        sim_devices if len(sim_devices) > 1 else sim_devices[0],
        framer=FramerType.RTU,
        address=(host, port),
    )
    await server.serve_forever(background=True)
    return server


class ModbusDeviceServer:
    """Async context manager around :func:`serve_devices`.

    ``async with ModbusDeviceServer({5: tvoc, 1: mpr}) as srv: ...``

    After mutating a simulator call :meth:`sync` to push the change into the
    live datastore.  We diff against the last pushed image and write only the
    registers that moved, in contiguous runs, so a 1 Hz demo loop costs a
    handful of list assignments rather than a rebuild of 400 registers.
    """

    def __init__(
        self,
        devices: dict[int, Any],
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
    ) -> None:
        if not devices:
            raise ValueError("at least one device is required")
        self.devices = dict(devices)
        self.host = host
        self.port = port
        self.server: ModbusTcpServer | None = None
        self._pushed: dict[int, dict[int, int]] = {}
        self._autosync: asyncio.Task | None = None
        self.writes = 0
        self.sync_calls = 0

    # ------------------------------------------------------------ lifecycle --

    async def start(self) -> "ModbusDeviceServer":
        self.server = await serve_devices(self.devices, self.host, self.port)
        self._pushed = {sid: dict(sim.block()) for sid, sim in self.devices.items()}
        return self

    async def stop(self) -> None:
        if self._autosync is not None:
            self._autosync.cancel()
            try:
                await self._autosync
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
            self._autosync = None
        if self.server is not None:
            await self.server.shutdown()
            self.server = None

    async def __aenter__(self) -> "ModbusDeviceServer":
        return await self.start()

    async def __aexit__(self, *exc: object) -> None:
        await self.stop()

    # ----------------------------------------------------------------- sync --

    async def sync(self) -> int:
        """Push simulator state into the live datastore.  Returns words written."""
        if self.server is None:
            raise RuntimeError("server is not running")
        self.sync_calls += 1
        written = 0
        for sid, sim in self.devices.items():
            new = sim.block()
            old = self._pushed.get(sid, {})
            if new.keys() != old.keys():
                raise RuntimeError(
                    f"slave {sid}: the served address set changed at runtime "
                    f"({len(old)} -> {len(new)} registers). A real device's map is "
                    f"fixed by its firmware; rebuild the server instead."
                )
            changed = {a: v for a, v in new.items() if old.get(a) != v}
            for start, values in contiguous_runs(changed):
                # Function code 3 and 4 share one block on these devices, so a
                # single write is visible to both.
                await self.server.async_setValues(sid, 3, start, values)
                written += len(values)
            if changed:
                self._pushed[sid] = new
        self.writes += written
        return written

    def start_autosync(self, period: float = 1.0) -> None:
        """Keep the datastore fresh from a background task, 1 Hz by default."""
        if self._autosync is not None:
            return

        async def loop() -> None:
            while True:
                await asyncio.sleep(period)
                try:
                    await self.sync()
                except Exception as exc:  # noqa: BLE001 - a sync error must not kill the demo
                    print(f"[modbus_server] sync error: {exc!r}")

        self._autosync = asyncio.create_task(loop())

    # ----------------------------------------------------------------- info --

    @property
    def endpoint(self) -> tuple[str, int]:
        return (self.host, self.port)

    def describe(self) -> dict:
        return {
            "endpoint": f"{self.host}:{self.port}",
            "framer": "RTU over TCP",
            "slaves": {
                sid: {
                    "type": type(sim).__name__,
                    "registers": len(self._pushed.get(sid, sim.block())),
                    "runs": len(contiguous_runs(self._pushed.get(sid, sim.block()))),
                }
                for sid, sim in self.devices.items()
            },
            "sync_calls": self.sync_calls,
            "words_written": self.writes,
        }


# ==========================================================================

if __name__ == "__main__":
    import time

    from pymodbus.client import AsyncModbusTcpClient

    from panogoz.sim.mpr import MprSim, decode_words
    from panogoz.sim.tvoc import TvocSim, detectors_from_bitfields, relays_from_bitfield

    T0 = 1_757_000_000.0

    async def main() -> None:
        print("=" * 74)
        print("Modbus RTU-over-TCP device server  ·  self-test")
        print("=" * 74)

        tvoc = TvocSim(slave_id=5, detectors=20, seed=7)
        tvoc.tick(T0)
        mpr = MprSim(slave_id=1, ct_ratio=500, seed=7)
        mpr.update(i_l1=1420.0, i_l2=980.0, i_l3=1150.0, i_n=310.0,
                   v_l1=231.4, v_l2=229.8, v_l3=233.1, freq=49.98,
                   thd={"i_l1": 11.5}, ts=T0)

        print("\n[1] sparse run structure")
        for name, sim in (("TVOC-2", tvoc), ("MPR-53CS", mpr)):
            b = sim.block()
            runs = contiguous_runs(b)
            print(f"    {name:<9}: {len(b):>4} registers in {len(runs):>3} contiguous runs "
                  f"(every gap between runs answers exception 02)")
        assert len(contiguous_runs(tvoc.block())) > 10

        # ---------------- topology A: one server, two slave ids -------------
        print("\n[2] topology A - one RS-485 pair, two slave ids on port 15020")
        async with ModbusDeviceServer({5: tvoc, 1: mpr}, port=15020) as srv:
            cli = AsyncModbusTcpClient("127.0.0.1", port=15020,
                                       framer=FramerType.RTU, timeout=2)
            await cli.connect()

            rr = await cli.read_holding_registers(1300, count=7, device_id=5)
            print(f"    slave 5 reg 1300..1306 : {rr.registers}  (TVOC-2 system state + DTCs)")
            assert not rr.isError()

            rr = await cli.read_holding_registers(6, count=2, device_id=1)
            i_l1 = decode_words(rr.registers) * 0.001 * 500
            print(f"    slave 1 reg 6..7       : {rr.registers} -> {i_l1:.1f} A primary")
            assert not rr.isError() and abs(i_l1 - 1420.0) < 0.5

            print("\n[3] holes answer with exception 02, not with zeros")
            for addr, count, what in (
                (100, 8, "trip log entry 0 + hole at 106"),
                (213, 1, "register 213, WRITE ONLY"),
                (145, 5, "hole at 148 inside 145..149"),
            ):
                rr = await cli.read_holding_registers(addr, count=count, device_id=5)
                print(f"    read {addr:>5} x{count:<3} {what:<34} -> "
                      f"isError={rr.isError()} exc={getattr(rr, 'exception_code', None)}")
                assert rr.isError() and rr.exception_code == 2
            rr = await cli.read_holding_registers(32770, count=4, device_id=1)
            print(f"    read 32770 x4   MPR gap at 32772..32776           -> "
                  f"isError={rr.isError()} exc={getattr(rr, 'exception_code', None)}")
            assert rr.isError() and rr.exception_code == 2

            print("\n[4] FC 03 and FC 04 read the same address space")
            a = await cli.read_holding_registers(149, count=1, device_id=5)
            b = await cli.read_input_registers(149, count=1, device_id=5)
            print(f"    FC03 reg 149 = {a.registers}   FC04 reg 149 = {b.registers}")
            assert a.registers == b.registers

            print("\n[5] live update: inject an arc, sync, re-read")
            before = (await cli.read_holding_registers(1300, count=1, device_id=5)).registers[0]
            ev = tvoc.inject_arc(detector="X2:3", relay="K5", now=T0 + 60)
            words = await srv.sync()
            rr = await cli.read_holding_registers(206, count=7, device_id=5)
            state = (await cli.read_holding_registers(1300, count=1, device_id=5)).registers[0]
            det = detectors_from_bitfields(rr.registers[4], rr.registers[5])
            print(f"    reg 1300 before/after  : 0x{before:04X} -> 0x{state:04X}")
            print(f"    words re-written       : {words} (diffed, not a full rebuild)")
            print(f"    reg 206..212           : {rr.registers}")
            print(f"    decoded                : {det} via {relays_from_bitfield(rr.registers[6])}")
            assert state & 1 and det == ["X2:3"] and ev["trip_number"] == 1
            assert 0 < words < 40

            print("\n[6] a read that spans the whole 266-register analyser space")
            t = time.perf_counter()
            got = []
            for start in (0, 125, 250):
                count = min(125, 266 - start)
                rr = await cli.read_holding_registers(start, count=count, device_id=1)
                assert not rr.isError(), (start, count)
                got.extend(rr.registers)
            dt = (time.perf_counter() - t) * 1000
            print(f"    3 reads x <=125 regs   : {len(got)} registers in {dt:.1f} ms")
            print(f"    one 266-register read  : refused by the protocol, FC03 limit is 125")
            assert len(got) == 266

            cli.close()
            print(f"\n    server: {srv.describe()}")

        # ---------------- topology B: two ports ------------------------------
        print("\n[7] topology B - two isolated RS-485 ports (what PANO GOZ specifies)")
        async with ModbusDeviceServer({5: tvoc}, port=15021) as arc_srv, \
                   ModbusDeviceServer({1: mpr}, port=15022) as an_srv:
            c1 = AsyncModbusTcpClient("127.0.0.1", port=15021, framer=FramerType.RTU, timeout=2)
            c2 = AsyncModbusTcpClient("127.0.0.1", port=15022, framer=FramerType.RTU, timeout=2)
            await c1.connect()
            await c2.connect()

            async def slow_analyser_read() -> float:
                t0 = time.perf_counter()
                for start in (0, 125, 250):
                    await c2.read_holding_registers(start, count=min(125, 266 - start), device_id=1)
                return (time.perf_counter() - t0) * 1000

            async def arc_poll() -> tuple[int, float]:
                t0 = time.perf_counter()
                n = 0
                for _ in range(10):
                    rr = await c1.read_holding_registers(1300, count=1, device_id=5)
                    assert not rr.isError()
                    n += 1
                    await asyncio.sleep(0.01)
                return n, (time.perf_counter() - t0) * 1000

            (an_ms, (polls, arc_ms)) = await asyncio.gather(slow_analyser_read(), arc_poll())
            print(f"    analyser sweep on 15022: {an_ms:.1f} ms")
            print(f"    {polls} arc polls on 15021 : {arc_ms:.1f} ms, concurrent and unblocked")
            print(f"    on one shared pair these would have serialised behind each other")
            assert polls == 10

            c1.close()
            c2.close()

        print("\n[8] guardrails")
        try:
            await serve_devices({0: tvoc}, port=15023)
            raise AssertionError("slave id 0 should be refused")
        except ValueError as exc:
            print(f"    rejected: slave id 0 -> {exc}")

        print("\n" + "=" * 74)
        print("Modbus device server self-test PASSED")
        print("=" * 74)

    asyncio.run(main())
