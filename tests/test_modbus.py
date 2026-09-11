"""Proofs for the Modbus layer: simulators, server and gateway poller.

Run it directly - ``python -m tests.test_modbus`` - and it prints the evidence
for each claim as it checks it.  It is also importable by pytest: every check is
a plain ``test_*`` function.

Six claims, each of which would be a real field failure if it were false:

  1. A read that spans a documented hole returns an exception, not data.
     If the simulator answered holes with zeros, every hole-related bug in the
     gateway would be invisible until the day we met real hardware.
  2. Reading register 213 returns exception 02.  It is write-only on a real
     TVOC-2, and a client that reads it and believes the answer is reading noise.
  3. An injected arc appears consistently in register 1300, in 210/211/212, in
     the trip log and in the trip counter 149 - five places that must agree.
  4. A known primary current survives the whole 32-bit / multiplier / CT-ratio
     round trip, and visibly does not survive it when the CT ratio is dropped.
  5. Word-order auto-detection picks the right one of ABCD/CDAB/BADC/DCBA for a
     device speaking each of them.
  6. The poller's block plan contains no read that spans a hole - asserted
     against the plan itself, and again against the transactions actually sent.

The transport is real Modbus RTU framing with real CRC-16, carried over TCP the
way a serial device server carries it in the field.
"""

from __future__ import annotations

import asyncio
import sys
import traceback

from pymodbus import FramerType
from pymodbus.client import AsyncModbusTcpClient

from panogoz.gateway import poller as P
from panogoz.sim import mpr as mpr_map
from panogoz.sim import tvoc as tvoc_map
from panogoz.sim.modbus_server import ModbusDeviceServer
from panogoz.sim.mpr import MprSim
from panogoz.sim.tvoc import TvocSim

T0 = 1_757_000_000.0
HOST = "127.0.0.1"

_log: list[str] = []


def say(msg: str = "") -> None:
    _log.append(msg)
    print(msg)


# ==========================================================================
# 1 - a hole-spanning read returns an exception rather than data
# ==========================================================================

async def _check_holes() -> None:
    tvoc = TvocSim(slave_id=5, detectors=20, seed=1)
    tvoc.tick(T0)
    mpr = MprSim(slave_id=1, ct_ratio=500, seed=1)
    mpr.update(i_l1=1200.0, i_l2=1100.0, i_l3=1150.0, i_n=180.0,
               v_l1=231.0, v_l2=231.0, v_l3=231.0, freq=50.0, thd={}, ts=T0)

    async with ModbusDeviceServer({5: tvoc, 1: mpr}, port=15060):
        cli = AsyncModbusTcpClient(HOST, port=15060, framer=FramerType.RTU, timeout=2)
        await cli.connect()

        say("  address    count  what                                    result")
        say("  " + "-" * 76)

        cases = [
            # (slave, start, count, description, expect_error)
            (5, 100, 6, "trip log entry 0, stops before the hole at 106", False),
            (5, 100, 7, "trip log entry 0 PLUS the hole at 106", True),
            (5, 105, 3, "straddles the hole at 106", True),
            (5, 142, 8, "entry 6 plus the hole at 148 plus reg 149", True),
            (5, 149, 1, "trip counter alone", False),
            (5, 300, 6, "error log entry 0", False),
            (5, 300, 7, "error log entry 0 plus the hole at 306", True),
            (5, 220, 6, "diagnostics stamp + sensor status, contiguous", False),
            (1, 32768, 4, "MPR settings up to 32771", False),
            (1, 32768, 12, "MPR settings across the gap 32772..32776", True),
            (1, 32770, 4, "starts inside, runs into the gap", True),
        ]
        failures = 0
        for sid, start, count, what, expect_error in cases:
            rr = await cli.read_holding_registers(start, count=count, device_id=sid)
            got_error = rr.isError()
            code = getattr(rr, "exception_code", None)
            verdict = "OK" if got_error == expect_error else "MISMATCH"
            if verdict == "MISMATCH":
                failures += 1
            detail = (f"exception {code} {P._exception_name(code)}" if got_error
                      else f"{len(rr.registers)} registers")
            say(f"  {start:>7}  {count:>5}  {what:<38}  {detail}  [{verdict}]")
            assert got_error == expect_error, (sid, start, count, what)

        say("")
        say(f"  every documented hole answers ILLEGAL_DATA_ADDRESS: "
            f"{len(cases) - failures}/{len(cases)} cases as expected")
        say(f"  a sequential datastore would have returned plausible zeros for all of them")
        cli.close()


def test_hole_spanning_read_raises_exception() -> None:
    asyncio.run(_check_holes())


# ==========================================================================
# 2 - register 213 is write only and reading it raises exception 02
# ==========================================================================

async def _check_213() -> None:
    tvoc = TvocSim(slave_id=5, detectors=20, seed=2)
    tvoc.tick(T0)
    async with ModbusDeviceServer({5: tvoc}, port=15061):
        cli = AsyncModbusTcpClient(HOST, port=15061, framer=FramerType.RTU, timeout=2)
        await cli.connect()

        for fc, name in ((3, "FC03 read holding"), (4, "FC04 read input")):
            if fc == 3:
                rr = await cli.read_holding_registers(213, count=1, device_id=5)
            else:
                rr = await cli.read_input_registers(213, count=1, device_id=5)
            code = getattr(rr, "exception_code", None)
            say(f"  {name:<22} reg 213 -> isError={rr.isError()} "
                f"exception={code} ({P._exception_name(code)})")
            assert rr.isError() and code == 2

        rr = await cli.read_holding_registers(212, count=2, device_id=5)
        say(f"  FC03 read 212..213     -> isError={rr.isError()} "
            f"exception={getattr(rr, 'exception_code', None)}  "
            f"(212 alone is readable, 212+213 is not)")
        assert rr.isError() and rr.exception_code == 2
        rr = await cli.read_holding_registers(212, count=1, device_id=5)
        assert not rr.isError()
        say(f"  FC03 read 212 alone    -> {rr.registers}")

        say("")
        say("  213 triggers a TVOC-2 self-test.  ABB does not document whether arc")
        say("  protection is inhibited while diagnostics run, which is exactly why")
        say("  this register is not reachable from the northbound SCADA map at all.")
        say(f"  213 in readable_addresses(): "
            f"{tvoc_map.REG_PERFORM_DIAGNOSTICS in tvoc_map.readable_addresses()}")
        assert tvoc_map.REG_PERFORM_DIAGNOSTICS not in tvoc_map.readable_addresses()
        cli.close()


def test_register_213_is_write_only() -> None:
    asyncio.run(_check_213())


# ==========================================================================
# 3 - an injected arc appears in 1300, 210/211/212, the trip log and 149
# ==========================================================================

async def _check_arc() -> None:
    tvoc = TvocSim(slave_id=5, detectors=30, firmware="03.01.00", seed=3)
    tvoc.tick(T0)
    async with ModbusDeviceServer({5: tvoc}, port=15062) as srv:
        cli = AsyncModbusTcpClient(HOST, port=15062, framer=FramerType.RTU, timeout=2)
        await cli.connect()

        before_state = (await cli.read_holding_registers(1300, count=1, device_id=5)).registers[0]
        before_count = (await cli.read_holding_registers(149, count=1, device_id=5)).registers[0]
        say(f"  before : reg 1300 = 0x{before_state:04X}   reg 149 = {before_count}")
        assert before_state == 0 and before_count == 0

        ev = tvoc.inject_arc(detector="X3:7", relay="K6", now=T0 + 3_723)
        await srv.sync()
        say(f"  inject : {ev['detector']} -> {ev['relay']} at t0+3723 s, "
            f"trip #{ev['trip_number']} into log slot {ev['log_slot']}")

        state = (await cli.read_holding_registers(1300, count=7, device_id=5)).registers
        live = (await cli.read_holding_registers(206, count=7, device_id=5)).registers
        count = (await cli.read_holding_registers(149, count=1, device_id=5)).registers[0]
        log0 = (await cli.read_holding_registers(100, count=6, device_id=5)).registers

        det_live = tvoc_map.detectors_from_bitfields(live[4], live[5])
        det_log = tvoc_map.detectors_from_bitfields(log0[4], log0[5])
        relays = tvoc_map.relays_from_bitfield(live[6])
        hh, mm = tvoc_map.decode_time(log0[2])

        say("")
        say(f"  reg 1300     0x{state[0]:04X}  bit0 ACTIVE_TRIP="
            f"{bool(state[0] & tvoc_map.STATE_ACTIVE_TRIP)}")
        say(f"  reg 1301-06  {state[1:]}  -> DTC "
            f"{[tvoc_map.DTC_LABELS_TR.get(d, d) for d in state[1:] if d]}")
        say(f"  reg 210      0x{live[4]:04X}")
        say(f"  reg 211      0x{live[5]:04X}   -> detector {det_live}")
        say(f"  reg 212      0x{live[6]:04X}   -> relay {relays}")
        say(f"  reg 149      {count}")
        say(f"  log slot 0   no={log0[0]} date={log0[1]} days "
            f"time={hh:02d}:{mm:02d} duration={log0[3]} ms detector={det_log}")

        assert state[0] & tvoc_map.STATE_ACTIVE_TRIP
        assert tvoc_map.DTC_ARC_TRIP in state[1:]
        assert det_live == ["X3:7"], det_live
        assert relays == ["K6"]
        assert count == 1
        assert log0[0] == 1
        assert det_log == det_live
        # 3723 s past midnight-aligned T0 is 01:02 later; check the binary HHMM
        # decode rather than a BCD one, which would have produced nonsense.
        assert (hh, mm) == tvoc_map.decode_time(tvoc_map.encode_time(T0 + 3723))
        assert log0[3] == 1  # ~1 ms light-to-contacts

        say("")
        say("  ring behaviour: 7 log slots, counter keeps counting")
        for i in range(2, 10):
            tvoc.inject_arc(detector=tvoc_map.ALL_DETECTORS[i], relay="K4", now=T0 + 60 * i)
        await srv.sync()
        count = (await cli.read_holding_registers(149, count=1, device_id=5)).registers[0]
        slot0 = (await cli.read_holding_registers(100, count=6, device_id=5)).registers
        slot1 = (await cli.read_holding_registers(107, count=6, device_id=5)).registers
        say(f"  after 9 trips: reg 149 = {count}, slot0 holds trip #{slot0[0]}, "
            f"slot1 holds trip #{slot1[0]}")
        say(f"  a client that reads only the log under-reports a recurring fault; "
            f"reg 149 is the truth")
        assert count == 9 and slot0[0] == 8 and slot1[0] == 9

        say("")
        say("  the 0x0000 trap: with nothing active, 222/223 read zero")
        tvoc.reset_trip()
        tvoc.clear()
        await srv.sync()
        quiet = (await cli.read_holding_registers(222, count=4, device_id=5)).registers
        state = (await cli.read_holding_registers(1300, count=1, device_id=5)).registers[0]
        say(f"  reg 1300 = 0x{state:04X}, reg 222..225 = {quiet}")
        say(f"  in a '1 = OK' bitfield that is indistinguishable from all 30")
        say(f"  detectors having failed.  Reg 1300 is the gate, and the poller")
        say(f"  refuses to read 222-225 at all while it is clear.")
        assert state == 0 and quiet == [0, 0, 0, 0]
        cli.close()


def test_injected_arc_is_consistent_across_five_registers() -> None:
    asyncio.run(_check_arc())


# ==========================================================================
# 4 - the MPR 32-bit round trip through the CT ratio
# ==========================================================================

async def _check_mpr_roundtrip() -> None:
    known_a = 1683.5          # a current a 1600 kVA panel really carries
    mpr = MprSim(slave_id=1, ct_ratio=500, vt_ratio=1.0, seed=4)
    mpr.update(i_l1=known_a, i_l2=1290.0, i_l3=1455.0, i_n=402.5,
               v_l1=231.4, v_l2=229.8, v_l3=233.1, freq=49.97,
               thd={"i_l1": 12.4, "v_l1": 2.2}, ts=T0, cos_phi=0.94,
               digital_in=0b1011, digital_out=0b0110)

    async with ModbusDeviceServer({1: mpr}, port=15063):
        cli = AsyncModbusTcpClient(HOST, port=15063, framer=FramerType.RTU, timeout=2)
        await cli.connect()

        rr = await cli.read_holding_registers(6, count=2, device_id=1)
        w = rr.registers
        raw = P.decode_pair(w[0], w[1], "ABCD")
        secondary = raw * mpr_map.MULT_CURRENT
        primary = secondary * 500

        say(f"  injected primary current      : {known_a:.1f} A")
        say(f"  registers 6,7 on the wire     : {w}  (big-endian, high word first)")
        say(f"  raw 32-bit                    : {raw}")
        say(f"  x 0.001 multiplier            : {secondary:.3f} A  <- CT SECONDARY")
        say(f"  x CT ratio 500 (reg 32769)    : {primary:.1f} A    <- primary, correct")
        say(f"  error                         : {abs(primary - known_a):.3f} A "
            f"({abs(primary - known_a) / known_a * 1e6:.0f} ppm)")
        assert abs(primary - known_a) <= 0.5

        settings = (await cli.read_holding_registers(32768, count=4, device_id=1)).registers
        say("")
        say(f"  reg 32768 VT ratio x0.1       : {settings[0]} -> {settings[0] / 10:.1f}")
        say(f"  reg 32769 CT RATIO            : {settings[1]}  (2500/5 = 500, NOT 2500)")
        assert settings[1] == 500

        say("")
        say("  what happens to a client that forgets the ratio:")
        say(f"    reported current            : {secondary:.3f} A on a panel carrying "
            f"{known_a:.0f} A")
        say(f"    under-read by               : {known_a / secondary:.0f}x")
        say(f"    and it looks perfectly healthy - nothing is out of range")
        assert abs(known_a / secondary - 500) < 1

        say("")
        say("  full-map round trip:")
        raw_map: dict[int, int] = {}
        for start in (0, 125, 250):
            n = min(125, 266 - start)
            rr = await cli.read_holding_registers(start, count=n, device_id=1)
            assert not rr.isError()
            for i, val in enumerate(rr.registers):
                raw_map[start + i] = val
        worst = ("", 0.0)
        for reg in mpr_map.BASE_REGS + mpr_map.TAIL_REGS:
            words = [raw_map[reg.addr + i] for i in range(reg.words)]
            rawv = P.decode_pair(words[0], words[1], "ABCD", signed=reg.signed)
            got = mpr_map.from_raw(reg, rawv, 500, 1.0)
            want = mpr.expected(reg.name)
            rel = abs(got - want) / max(1.0, abs(want))
            if rel > worst[1]:
                worst = (reg.name, rel)
        say(f"    {len(mpr_map.BASE_REGS + mpr_map.TAIL_REGS)} quantities decoded, "
            f"worst relative error {worst[1]:.2e} on {worst[0]}")
        assert worst[1] < 1e-3

        say(f"    registers 84/85 are the only 16-bit ones: "
            f"out=0b{raw_map[84]:04b} in=0b{raw_map[85]:04b} - one register each,")
        say(f"    which is precisely how we know every other measurement is 32 bit:")
        say(f"    they are the only two addresses in the map that step by one.")
        assert raw_map[84] == 0b0110 and raw_map[85] == 0b1011
        cli.close()


def test_mpr_32bit_roundtrip_through_ct_ratio() -> None:
    asyncio.run(_check_mpr_roundtrip())


# ==========================================================================
# 5 - word-order auto-detection
# ==========================================================================

def _words_for(raw: int, order: str) -> list[int]:
    hi, lo = (raw >> 16) & 0xFFFF, raw & 0xFFFF
    if order == "ABCD":
        return [hi, lo]
    if order == "CDAB":
        return [lo, hi]
    if order == "BADC":
        return [P._swap(hi), P._swap(lo)]
    return [P._swap(lo), P._swap(hi)]


def test_word_order_autodetection() -> None:
    say("  probing on the mains frequency register (58), which must land 45-55 Hz")
    say("")
    say(f"  {'device speaks':<14} {'words':<16} " +
        " ".join(f"{o:>12}" for o in P.WORD_ORDERS) + "   detected")
    say("  " + "-" * 88)
    for raw_hz in (4998, 5000, 5012):
        for order in P.WORD_ORDERS:
            words = _words_for(raw_hz, order)
            det = P.detect_word_order(words)
            cand = " ".join(f"{det['candidates'][o]:>12.2f}" for o in P.WORD_ORDERS)
            say(f"  {order:<14} {str(words):<16} {cand}   {det['order']}")
            assert det["order"] == order, (raw_hz, order, det)
            assert not det["ambiguous"]
        say("")

    det = P.detect_word_order([0, 0])
    say(f"  all-zero register  -> order={det['order']} ambiguous={det['ambiguous']}")
    say(f"     {det['reason']}")
    assert det["order"] is None and det["ambiguous"]

    det = P.detect_word_order([0x1234, 0x5678])
    say(f"  garbage register   -> order={det['order']} ambiguous={det['ambiguous']}")
    say(f"     {det['reason']}")
    assert det["order"] is None and det["ambiguous"]

    say("")
    say("  a wrong word order does not look broken - CDAB read as ABCD gives")
    say(f"  {P.decode_pair(*_words_for(4998, 'CDAB'), 'ABCD') * 0.01:,.2f} Hz, which is obviously")
    say("  wrong here but on a power register would just be a plausible number.")


async def _check_word_order_live() -> None:
    mpr = MprSim(slave_id=1, ct_ratio=500, seed=5)
    mpr.update(i_l1=1200.0, i_l2=1100.0, i_l3=1150.0, i_n=180.0,
               v_l1=231.0, v_l2=231.0, v_l3=231.0, freq=49.94, thd={}, ts=T0)
    async with ModbusDeviceServer({1: mpr}, port=15064):
        p = P.ModbusPoller(tvoc=None, mpr=(HOST, 15064, 1))
        await p.connect()
        say("")
        say(f"  live against the simulator: order={p.word_order}  "
            f"({p.word_order_reason})")
        r = await p.poll_analyser()
        say(f"  decoded frequency         : {r['channels']['mpr.freq_hz']:.2f} Hz")
        say(f"  candidates                : {r['word_order_candidates']}")
        assert p.word_order == "ABCD"
        assert abs(r["channels"]["mpr.freq_hz"] - 49.94) < 0.01
        await p.close()


def test_word_order_detected_live() -> None:
    asyncio.run(_check_word_order_live())


# ==========================================================================
# 6 - the poller's block plan never spans a hole
# ==========================================================================

def test_block_plan_never_spans_a_hole() -> None:
    say("  (a) the plan itself, checked against the device address maps")
    say("")
    fw_cases = ("03.01.00", "02.09.12")
    for fw in fw_cases:
        p = P.ModbusPoller(tvoc=None, mpr=None)
        p.tvoc_firmware = fw
        p._build_tvoc_plans()
        plans = p.plans()
        addrs = tvoc_map.readable_addresses(fw)
        holes = tvoc_map.all_holes(fw)
        say(f"  TVOC firmware {fw}  ({len(addrs)} readable registers, "
            f"{len(holes)} unmapped addresses in span)")
        total = 0
        for name in ("tvoc.state", "tvoc.live", "tvoc.trip_log",
                     "tvoc.error_log", "tvoc.identity", "tvoc.extended"):
            blocks = plans[name]
            total += sum(c for _, c in blocks)
            for start, count in blocks:
                assert count <= P.FC03_MAX_REGISTERS, (name, start, count)
                for a in range(start, start + count):
                    assert a in addrs, f"{name} block ({start},{count}) covers hole {a}"
                    assert a not in holes
                    assert a != tvoc_map.REG_PERFORM_DIAGNOSTICS
            say(f"    {name:<16} {len(blocks):>2} blocks  {blocks}")
        say(f"    total registers requested: {total}")
        say("")

    p = P.ModbusPoller(tvoc=None, mpr=None)
    plans = p.plans()
    for name, allowed in (
        ("mpr.measurement", mpr_map.measurement_addresses()),
        ("mpr.settings", mpr_map.setting_addresses()),
    ):
        v = P.verify_plan(plans[name], allowed)
        say(f"  {name:<16} {plans[name]}")
        say(f"    -> {v}")
        assert v["ok"], v
    say(f"  the MPR settings plan splits at the 32772..32776 gap; a single")
    say(f"  32768..32779 read would return exception 02 for the whole request.")

    say("")
    say("  (b) a plan that DOES span a hole is caught by the same verifier")
    naive = [(100, 50)]      # the obvious hand-written "just read the log"
    v = P.verify_plan(naive, {a for a in tvoc_map.readable_addresses() if 100 <= a <= 149})
    say(f"  naive plan {naive} -> ok={v['ok']}, "
        f"{len(v['violations'])} violations, first at address "
        f"{v['violations'][0]['address']}")
    assert not v["ok"] and v["violations"]

    huge = [(0, 266)]
    v = P.verify_plan(huge, mpr_map.measurement_addresses())
    say(f"  single 266-register read {huge} -> ok={v['ok']}, "
        f"{v['violations'][0]['why']}")
    assert not v["ok"]


async def _check_plan_live() -> None:
    """(c) capture every transaction the poller actually sends."""
    tvoc = TvocSim(slave_id=5, detectors=20, firmware="03.01.00", seed=6)
    tvoc.tick(T0)
    mpr = MprSim(slave_id=1, ct_ratio=500, seed=6)
    mpr.update(i_l1=1420.0, i_l2=980.0, i_l3=1150.0, i_n=402.5,
               v_l1=231.4, v_l2=229.8, v_l3=233.1, freq=49.98,
               thd={"i_l1": 11.5}, ts=T0, cos_phi=0.94)

    async with ModbusDeviceServer({5: tvoc}, port=15065) as arc_srv, \
               ModbusDeviceServer({1: mpr}, port=15066):
        p = P.ModbusPoller(tvoc=(HOST, 15065, 5), mpr=(HOST, 15066, 1))

        sent: list[tuple[str, int, int]] = []
        original = p._read

        async def traced(role: str, address: int, count: int, fc: int = 3):
            sent.append((role, address, count))
            return await original(role, address, count, fc)

        p._read = traced  # type: ignore[method-assign]

        await p.connect()
        await p.poll_once(ts=T0)
        tvoc.inject_arc(detector="X2:4", relay="K5", now=T0 + 30)
        await arc_srv.sync()
        await p.poll_once(ts=T0 + 30)
        await p.read_trip_log()

        say("")
        say(f"  (c) {len(sent)} transactions actually sent by the poller")
        tv_addrs = tvoc_map.readable_addresses("03.01.00")
        mp_addrs = mpr_map.readable_addresses()
        bad = []
        for role, start, count in sent:
            allowed = tv_addrs if role == "tvoc" else mp_addrs
            if count > P.FC03_MAX_REGISTERS:
                bad.append((role, start, count, "too long"))
            for a in range(start, start + count):
                if a not in allowed:
                    bad.append((role, start, count, f"hole at {a}"))
                    break
        uniq: dict[tuple[str, int, int], int] = {}
        for t in sent:
            uniq[t] = uniq.get(t, 0) + 1
        for (role, start, count), n in sorted(uniq.items()):
            say(f"    {role:<5} read {start:>6} x{count:<4} x{n}")
        say(f"  transactions that span a hole or break the 125 limit: {len(bad)}")
        assert not bad, bad

        st = p.stats_dict()
        say(f"  exceptions raised by either device during the whole run: "
            f"{sum(s['exceptions'] for s in st['slaves'].values())}")
        assert sum(s["exceptions"] for s in st["slaves"].values()) == 0
        say("  zero exceptions is the proof: the plan is right, not merely careful.")
        await p.close()


def test_block_plan_live_transactions() -> None:
    asyncio.run(_check_plan_live())


# ==========================================================================

TESTS = (
    ("1. a hole-spanning read returns an exception rather than data",
     test_hole_spanning_read_raises_exception),
    ("2. reading register 213 returns exception 02",
     test_register_213_is_write_only),
    ("3. an injected arc appears in 1300, 210/211/212, the trip log and 149",
     test_injected_arc_is_consistent_across_five_registers),
    ("4. the MPR 32-bit encode/decode round-trips a known current through the CT ratio",
     test_mpr_32bit_roundtrip_through_ct_ratio),
    ("5. word-order auto-detection picks the right one",
     test_word_order_autodetection),
    ("5b. and does so live against the simulator",
     test_word_order_detected_live),
    ("6. the poller's safe block plan issues no read that spans a hole",
     test_block_plan_never_spans_a_hole),
    ("6b. and neither does any transaction it actually sends",
     test_block_plan_live_transactions),
)


def main() -> int:
    print("=" * 84)
    print("PANO GOZ  ·  Modbus layer proofs")
    print("=" * 84)
    print("Transport: real Modbus RTU framing with CRC-16, carried over TCP exactly")
    print("the way a Moxa NPort carries it on a substation RS-485 pair.")
    failed = 0
    for title, fn in TESTS:
        print()
        print("-" * 84)
        print(title)
        print("-" * 84)
        try:
            fn()
        except Exception:  # noqa: BLE001
            failed += 1
            traceback.print_exc()
            print(f"  !! FAILED")
        else:
            print(f"  PASS")
    print()
    print("=" * 84)
    print(f"{len(TESTS) - failed}/{len(TESTS)} passed")
    print("=" * 84)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
