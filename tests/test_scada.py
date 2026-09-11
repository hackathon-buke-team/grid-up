"""End-to-end proof that the PANO GÖZ northbound Modbus TCP slave works.

Run it::

    cd C:/Users/darkb/Desktop/grid-up-v2
    PYTHONIOENCODING=utf-8 python -m tests.test_scada

Every check below is performed by a real pymodbus client over a real TCP
socket against a real :class:`panogoz.scada.slave.ScadaSlave`.  Nothing is
mocked, because the whole value of this interface is that a judge can point
their own laptop at it, and a mocked test proves nothing about that.
"""

from __future__ import annotations

import asyncio
import statistics
import sys
import time

from pymodbus.client import AsyncModbusTcpClient

from panogoz.contracts import icd
from panogoz.scada.slave import (
    JOINT_ORDER,
    POLL_TIMEOUT_S,
    ScadaSlave,
    demo_fleet,
)

#: FC 03 / FC 04 may not carry more than 125 registers in one request.  This is
#: a protocol limit, not ours: the response byte count is a single byte, so
#: 2*125 = 250 <= 255.  Every "how many requests" number below follows from it.
MAX_REGS_PER_REQUEST = 125

_PASS = 0
_FAIL = 0
_LINES: list[str] = []


def check(label: str, cond: bool, detail: str = "") -> bool:
    global _PASS, _FAIL
    if cond:
        _PASS += 1
    else:
        _FAIL += 1
    line = f"  [{'PASS' if cond else 'FAIL'}] {label}"
    if detail:
        line += f"\n         {detail}"
    print(line)
    _LINES.append(line)
    return bool(cond)


def head(title: str) -> None:
    print(f"\n{title}\n{'-' * len(title)}")


def g(name: str, words: list[int]) -> float:
    """Decode a global-block point from a window that starts at PDU 0."""
    reg = icd.GLOBAL_BY_NAME[name]
    return icd.decode(reg, words[reg.offset : reg.offset + reg.words])


def p(name: str, words: list[int]) -> float:
    """Decode a panel-block point from a window that starts at the panel base."""
    reg = icd.PANEL_BY_NAME[name]
    return icd.decode(reg, words[reg.offset : reg.offset + reg.words])


def praw(name: str, words: list[int]) -> int:
    reg = icd.PANEL_BY_NAME[name]
    return words[reg.offset]


# --------------------------------------------------------------------------
# 1 - global block
# --------------------------------------------------------------------------

async def t1_global_block(client: AsyncModbusTcpClient, n_panels: int) -> None:
    head("1. Global block: ICD_VERSION, PANEL_COUNT, heartbeat")
    rr = await client.read_holding_registers(icd.GLOBAL_BASE, count=icd.GLOBAL_SIZE, device_id=1)
    if not check("FC 03 read of the 32-word global block succeeds", not rr.isError()):
        return
    w = rr.registers

    ver = int(g("ICD_VERSION", w))
    major, minor, patch = ver // 10000, (ver // 100) % 100, ver % 100
    check(
        "ICD_VERSION recovered",
        ver == icd.ICD_VERSION_ENCODED,
        f"raw words {w[0:2]} -> {ver} -> v{major}.{minor}.{patch}  (document says v{icd.ICD_VERSION})",
    )
    check("PANEL_COUNT recovered", int(g("PANEL_COUNT", w)) == n_panels,
          f"PANEL_COUNT = {int(g('PANEL_COUNT', w))}, expected {n_panels}")
    check("PANELS_ONLINE <= PANEL_COUNT",
          int(g("PANELS_ONLINE", w)) <= int(g("PANEL_COUNT", w)),
          f"PANELS_ONLINE = {int(g('PANELS_ONLINE', w))}")
    check("REGS_PER_PANEL / PANEL_BLOCK_BASE self-describe the map",
          int(g("REGS_PER_PANEL", w)) == icd.REGS_PER_PANEL
          and int(g("PANEL_BLOCK_BASE", w)) == icd.PANEL_BASE,
          f"a client that reads only the global block learns stride "
          f"{int(g('REGS_PER_PANEL', w))} at base {int(g('PANEL_BLOCK_BASE', w))}")
    hb = int(g("WATCHDOG_HEARTBEAT", w))
    check("WATCHDOG_HEARTBEAT present", 0 <= hb <= 65535, f"heartbeat = {hb}")
    engine = int(g("ENGINE_STATE", w))
    check("ENGINE_STATE decodes to bit names", engine != 0,
          f"0x{engine:04X} = {icd.unpack_bits(icd.ENGINE_BITS, engine)}")
    print(f"         SERVER_TIME = {int(g('SERVER_TIME', w))} (unix, UTC)"
          f" · FLEET_WORST_SEVERITY = {int(g('FLEET_WORST_SEVERITY', w))}"
          f" · FLEET_HEALTH_MIN = {int(g('FLEET_HEALTH_MIN', w))}")


# --------------------------------------------------------------------------
# 2 - panel 14 at PDU 1624
# --------------------------------------------------------------------------

async def t2_panel_14(client: AsyncModbusTcpClient, slave: ScadaSlave) -> None:
    head("2. Panel 14 at PDU 1624: HEALTH_INDEX, THETA_MAX, STATUS_WORD, ARC_STATE")
    base = icd.panel_base(14)
    check("panel 14 base is the documented 1624", base == 1624, f"panel_base(14) = {base}")

    r3 = await client.read_holding_registers(base, count=icd.REGS_PER_PANEL, device_id=1)
    r4 = await client.read_input_registers(base, count=icd.REGS_PER_PANEL, device_id=1)
    if not check("FC 03 read of panel 14 succeeds", not r3.isError()):
        return
    check("FC 04 reads the SAME address space as FC 03",
          not r4.isError() and r4.registers == r3.registers,
          "48 words identical from both function codes")
    w = r3.registers

    live = next(x for x in slave._fleet.panels if x.panel_index == 14)

    hi = p("HEALTH_INDEX", w)
    check("HEALTH_INDEX recovered", abs(hi - round(live.health_index)) < 0.51,
          f"{hi:.0f}/100 on the wire, {live.health_index:.1f} in the live image")

    theta = p("THETA_MAX", w)
    check("THETA_MAX recovered (i16 x 0.1 K)", abs(theta - live.theta_max) <= 0.05,
          f"raw 0x{w[icd.PANEL_BY_NAME['THETA_MAX'].offset]:04X} -> {theta:+.1f} K "
          f"(anma akımında sıcaklık fazlası), live = {live.theta_max:+.2f} K")

    jidx = int(p("THETA_MAX_JOINT", w))
    check("THETA_MAX_JOINT indexes the frozen joint list",
          0 <= jidx < len(JOINT_ORDER) and JOINT_ORDER[jidx] == live.theta_max_joint,
          f"index {jidx} of {len(JOINT_ORDER)} -> {JOINT_ORDER[jidx]} = {live.theta_max_joint}")

    status = praw("STATUS_WORD", w)
    names = icd.unpack_bits(icd.STATUS_BITS, status)
    labels = {b.name: b.label_tr for b in icd.STATUS_BITS}
    check("STATUS_WORD decodes to named bits and DATA_VALID is set",
          "DATA_VALID" in names,
          f"0x{status:04X} = " + " | ".join(f"{n} ({labels[n]})" for n in names))

    arc = praw("ARC_STATE", w)
    anames = icd.unpack_bits(icd.ARC_BITS, arc)
    alabels = {b.name: b.label_tr for b in icd.ARC_BITS}
    check("ARC_STATE decodes to named bits",
          "SELFTEST_DISABLED" in anames and "NOT_FITTED" not in anames,
          f"0x{arc:04X} = " + " | ".join(f"{n} ({alabels[n]})" for n in anames))
    check("ARC detector census agrees with ARC_STATE",
          int(p("ARC_DETECTORS_OK", w)) == int(p("ARC_DETECTORS_TOTAL", w))
          and "DETECTOR_FAULT" not in anames,
          f"{int(p('ARC_DETECTORS_OK', w))}/{int(p('ARC_DETECTORS_TOTAL', w))} dedektör sağlam")

    print(f"         SEVERITY={int(p('SEVERITY', w))} "
          f"SENSITIVITY={int(p('SENSITIVITY_PCT', w))}% "
          f"LOAD_FACTOR={p('LOAD_FACTOR', w):.1f}% "
          f"I_L1/L2/L3/N={p('I_L1', w):.1f}/{p('I_L2', w):.1f}/"
          f"{p('I_L3', w):.1f}/{p('I_N', w):.1f} A "
          f"FREQ={p('FREQ', w):.2f} Hz DATA_AGE_S={int(p('DATA_AGE_S', w))} s")
    if int(p("SENSITIVITY_PCT", w)) < 100 or "SENSITIVITY_LOW" in names:
        print("         (SENSITIVITY_LOW means θ is temporarily unreliable at this load - "
              "reported separately from any panel fault, never mixed with one.)")


# --------------------------------------------------------------------------
# 3 - writes are refused
# --------------------------------------------------------------------------

async def t3_writes_rejected(client: AsyncModbusTcpClient, slave: ScadaSlave) -> None:
    head("3. Write function codes are refused with exception 0x01 ILLEGAL_FUNCTION")
    base = icd.panel_base(14)
    before = slave.read(base, icd.REGS_PER_PANEL)

    r6 = await client.write_register(base + 2, 0xDEAD, device_id=1)
    check("FC 06 Write Single Register rejected",
          r6.isError() and getattr(r6, "exception_code", 0) == 1,
          f"response {type(r6).__name__} function_code=0x{r6.function_code:02X} "
          f"exception_code=0x{getattr(r6, 'exception_code', 0):02X} ILLEGAL_FUNCTION")

    r16 = await client.write_registers(base, [0, 0, 0, 0], device_id=1)
    check("FC 16 Write Multiple Registers rejected",
          r16.isError() and getattr(r16, "exception_code", 0) == 1,
          f"response {type(r16).__name__} function_code=0x{r16.function_code:02X} "
          f"exception_code=0x{getattr(r16, 'exception_code', 0):02X} ILLEGAL_FUNCTION")

    r5 = await client.write_coil(0, True, device_id=1)
    r15 = await client.write_coils(0, [True, False], device_id=1)
    check("FC 05 and FC 15 rejected too",
          r5.isError() and getattr(r5, "exception_code", 0) == 1
          and r15.isError() and getattr(r15, "exception_code", 0) == 1,
          "there is no writable point anywhere in the map, and no flag that creates one")

    after = slave.read(base, icd.REGS_PER_PANEL)
    check("the image is byte-for-byte unchanged after four write attempts",
          before == after,
          "an unauthenticated Modbus write into a system that talks to a TVOC-2 "
          "arc relay is the worst possible thing to ship, so the path does not exist")

    bad = await client.read_holding_registers(icd.TOP_ADDRESS - 2, count=10, device_id=1)
    check("a read past the top of the map returns 0x02 ILLEGAL_ADDRESS, not garbage",
          bad.isError() and getattr(bad, "exception_code", 0) == 2,
          f"read {icd.TOP_ADDRESS - 2}+10 (top address is {icd.TOP_ADDRESS}) -> "
          f"exception 0x{getattr(bad, 'exception_code', 0):02X}")


# --------------------------------------------------------------------------
# 4 - an unpopulated panel
# --------------------------------------------------------------------------

async def t4_unpopulated(client: AsyncModbusTcpClient, first_empty: int) -> None:
    head(f"4. Unpopulated panel {first_empty}: zeros, DATA_VALID clear")
    base = icd.panel_base(first_empty)
    rr = await client.read_holding_registers(base, count=icd.REGS_PER_PANEL, device_id=1)
    if not check("the block reads without an exception", not rr.isError(),
                 "a polling failure and an empty panel must look different, so an "
                 "uncommissioned block answers normally instead of raising"):
        return
    w = rr.registers
    status = praw("STATUS_WORD", w)
    check("all 48 words are zero", set(w) == {0}, f"PDU {base}..{base + 47} = 0")
    check("STATUS_WORD.DATA_VALID is clear",
          not (status & (1 << next(b.bit for b in icd.STATUS_BITS if b.name == "DATA_VALID"))),
          f"STATUS_WORD = 0x{status:04X}, decoded bits = {icd.unpack_bits(icd.STATUS_BITS, status)} "
          f"(empty list = 'not commissioned', not 'healthy')")


# --------------------------------------------------------------------------
# 5 - the heartbeat
# --------------------------------------------------------------------------

async def t5_heartbeat(client: AsyncModbusTcpClient, slave: ScadaSlave) -> None:
    head("5. WATCHDOG_HEARTBEAT advances")
    off = icd.GLOBAL_BY_NAME["WATCHDOG_HEARTBEAT"].offset
    samples: list[int] = []
    for i in range(4):
        rr = await client.read_holding_registers(off, count=1, device_id=1)
        samples.append(rr.registers[0])
        if i < 3:
            slave.tick(ts=1_800_000_000.0 + i)
    deltas = [b - a for a, b in zip(samples, samples[1:])]
    check("one tick advances the heartbeat by exactly one",
          deltas == [1, 1, 1], f"samples {samples}, deltas {deltas}")

    # Wrap-around: 65535 -> 0 must not look like "the server died".
    slave._heartbeat = 65534
    slave.tick(ts=1_800_000_100.0)
    a = (await client.read_holding_registers(off, count=1, device_id=1)).registers[0]
    slave.tick(ts=1_800_000_101.0)
    b = (await client.read_holding_registers(off, count=1, device_id=1)).registers[0]
    check("the heartbeat wraps 65535 -> 0 instead of sticking",
          (a, b) == (65535, 0), f"{a} -> {b}  (SCADA compares (n1-n0) mod 65536 != 0)")

    # Staleness is computed by the server against its own clock.
    st = slave.poll_stats
    check("poll_stats knows when SCADA last spoke to us",
          st["ever_polled"] and st["seconds_since_last_poll"] is not None
          and not st["poll_lost"],
          f"{st['request_count']} requests, last {st['seconds_since_last_poll']:.3f} s ago, "
          f"poll_lost threshold {POLL_TIMEOUT_S:.0f} s, clients {st['clients']}")
    print("         A SCADA poll that stops is itself an alarm: from inside SCADA the "
          "silence is invisible,\n         so the slave is the only place it can be seen. "
          "poll_lost drives that incident.")


# --------------------------------------------------------------------------
# 6 - fleet poll latency
# --------------------------------------------------------------------------

async def t6_fleet_poll(client: AsyncModbusTcpClient, n_panels: int) -> None:
    head(f"6. Fleet poll: {n_panels} panels")

    # (a) the two-request poll a SCADA front end actually runs at 1 Hz:
    #     global block, then the one panel block it is displaying.
    base14 = icd.panel_base(14)
    lat: list[float] = []
    for _ in range(20):
        t0 = time.perf_counter()
        a = await client.read_holding_registers(icd.GLOBAL_BASE, count=icd.GLOBAL_SIZE, device_id=1)
        b = await client.read_holding_registers(base14, count=icd.REGS_PER_PANEL, device_id=1)
        lat.append((time.perf_counter() - t0) * 1000.0)
        if a.isError() or b.isError():
            check("two-request poll", False)
            return
    check("two-request poll (global block + one panel block) completes",
          True,
          f"20 iterations: median {statistics.median(lat):.2f} ms, "
          f"min {min(lat):.2f} ms, max {max(lat):.2f} ms over loopback TCP "
          f"({icd.GLOBAL_SIZE} + {icd.REGS_PER_PANEL} = "
          f"{icd.GLOBAL_SIZE + icd.REGS_PER_PANEL} registers)")

    # (b) the whole fleet.  Honest arithmetic first: 100 panels x 48 registers
    #     is 4800 registers, and FC 03 carries at most 125 per request, so a
    #     full fleet scan is 39 packed requests - it cannot be two, and saying
    #     otherwise would be the kind of number that falls apart in front of a
    #     customer's integration engineer.
    total_regs = n_panels * icd.REGS_PER_PANEL
    packed = -(-total_regs // MAX_REGS_PER_REQUEST)
    per_req_aligned = (MAX_REGS_PER_REQUEST // icd.REGS_PER_PANEL) * icd.REGS_PER_PANEL  # 96
    aligned = -(-total_regs // per_req_aligned)
    print(f"         {n_panels} panels x {icd.REGS_PER_PANEL} registers = {total_regs} registers.")
    print(f"         FC 03 carries at most {MAX_REGS_PER_REQUEST} registers per request "
          f"(response byte count is one byte),")
    print(f"         so a full fleet scan is {packed} packed requests, or {aligned} "
          f"block-aligned requests of {per_req_aligned}.")

    start = icd.PANEL_BASE
    t0 = time.perf_counter()
    words: list[int] = []
    requests = 0
    for addr in range(start, start + total_regs, MAX_REGS_PER_REQUEST):
        count = min(MAX_REGS_PER_REQUEST, start + total_regs - addr)
        rr = await client.read_holding_registers(addr, count=count, device_id=1)
        requests += 1
        if rr.isError():
            check("full fleet scan", False, f"error at PDU {addr}")
            return
        words.extend(rr.registers)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    valid_bit = 1 << next(b.bit for b in icd.STATUS_BITS if b.name == "DATA_VALID")
    sw_off = icd.PANEL_BY_NAME["STATUS_WORD"].offset
    id_off = icd.PANEL_BY_NAME["PANEL_ID"].offset
    populated = 0
    ids_ok = True
    for n in range(n_panels):
        blk = words[n * icd.REGS_PER_PANEL : (n + 1) * icd.REGS_PER_PANEL]
        if blk[sw_off] & valid_bit:
            populated += 1
        pid = (blk[id_off] << 16) | blk[id_off + 1]
        if pid != n + 1:
            ids_ok = False

    check(f"{n_panels}-panel fleet scan completes in {requests} requests",
          len(words) == total_regs and requests == packed,
          f"{len(words)} registers in {requests} requests, {elapsed_ms:.1f} ms total "
          f"= {elapsed_ms / n_panels:.3f} ms/panel = "
          f"{elapsed_ms / requests:.3f} ms/request "
          f"({total_regs / (elapsed_ms / 1000.0):,.0f} registers/s over loopback TCP)")
    check("every panel block in the scan carries DATA_VALID and its own PANEL_ID",
          populated == n_panels and ids_ok,
          f"{populated}/{n_panels} blocks valid, PANEL_ID 1..{n_panels} in order, "
          f"fixed stride of {icd.REGS_PER_PANEL} with no holes")
    print(f"         At a 30 s SCADA scan cycle, {requests} requests is "
          f"{requests / 30.0:.1f} requests/s - a rounding error for any RTU.")


# --------------------------------------------------------------------------
# runner
# --------------------------------------------------------------------------

async def run(n_panels: int = 100) -> int:
    print("PANO GÖZ · northbound SCADA slave · end-to-end test")
    print(f"pymodbus client over real TCP · ICD v{icd.ICD_VERSION} · "
          f"{len(JOINT_ORDER)} monitored joints per panel")

    slave = ScadaSlave(host="127.0.0.1", port=0, auto_tick=False)
    slave.update_fleet(demo_fleet(n_panels))
    await slave.start()
    port = slave.bound_port
    print(f"slave listening on 127.0.0.1:{port} · unit id {slave.unit_id} · "
          f"PDU 0..{icd.TOP_ADDRESS} · {n_panels} panels populated")

    client = AsyncModbusTcpClient("127.0.0.1", port=port)
    await client.connect()
    try:
        await t1_global_block(client, n_panels)
        await t2_panel_14(client, slave)
        await t3_writes_rejected(client, slave)
        await t4_unpopulated(client, min(icd.MAX_PANELS, n_panels + 20))
        await t5_heartbeat(client, slave)
        await t6_fleet_poll(client, n_panels)
    finally:
        head("Poll statistics as the platform sees them")
        for k, v in slave.poll_stats.items():
            print(f"  {k:<24} {v}")
        client.close()

        head("What a judge types")
        print("  # start the server (a second terminal):")
        print("  python -m panogoz.scada.slave --serve --port 5020 --panels 100")
        print()
        print("  # then, with modpoll (0-based addressing, -0):")
        for line in slave.modpoll_commands(14, host="127.0.0.1", port=5020):
            print("  " + line)
        print()
        print("  # the same two reads with mbpoll:")
        print(f"  mbpoll -m tcp -a 1 -r 1 -c {icd.GLOBAL_SIZE} -t 4 -1 -p 5020 127.0.0.1")
        print(f"  mbpoll -m tcp -a 1 -r {icd.panel_base(14) + 1} -c {icd.REGS_PER_PANEL} "
              f"-t 4 -1 -p 5020 127.0.0.1   # mbpoll is 1-based")
        print()
        print("  # ... and from Python:")
        print("  python -c \"from pymodbus.client import ModbusTcpClient as C;"
              "c=C('127.0.0.1',port=5020);c.connect();"
              "print(c.read_holding_registers(1624,count=48,device_id=1).registers)\"")
        await slave.stop()

    head("Result")
    print(f"  {_PASS} passed, {_FAIL} failed")
    return 0 if _FAIL == 0 else 1


def test_scada_slave() -> None:
    """pytest entry point - the whole suite as one test."""
    assert asyncio.run(run(100)) == 0


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    raise SystemExit(asyncio.run(run(n)))
