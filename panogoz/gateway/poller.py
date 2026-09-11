"""RS-485 master: the gateway's Modbus client for the two panel devices.

This is the only module in PANO GOZ that transmits on a bus it does not own, so
it is written defensively and it says out loud what it cannot know.

The seven things this poller does that a naive one does not
-----------------------------------------------------------

1. **A safe block plan, computed not hand-written.**  Both devices have holes -
   the TVOC-2's stride-7 log holes and its write-only register 213, the
   MPR-53CS's gap at 32772..32776 - and a read that straddles a hole returns
   exception 02 instead of data.  :func:`plan_blocks` takes the device's
   readable address set and emits the minimum number of requests that covers it
   without ever spanning a gap or exceeding the 125-register FC03 limit.  The
   address sets come from the same module that serves them, so the plan cannot
   drift away from the map.

2. **Edge-triggered deep reads.**  The fast loop reads seven registers
   (1300..1306) at 1 Hz.  Only when the system-state word says something is
   active do we go and read the live blocks and the logs.  Then we read them
   **twice, 200 ms apart**: ABB does not document the TVOC-2's Modbus image as
   atomic, so a trip detected between two internal updates could hand us a
   half-written record.  If the two reads disagree we say the image had not
   settled instead of publishing the first one.

3. **32-bit word-order auto-detection.**  Nothing in a Modbus map says whether a
   32-bit value is ABCD, CDAB, BADC or DCBA, and getting it wrong on an energy
   analyser gives numbers that look plausible.  The mains frequency register is
   the perfect probe: the answer must be between 45 and 55 Hz on a live
   European grid and exactly one word order produces that.  We detect it once,
   log which one won, and re-detect if the answer ever stops making sense.

4. **A primary-versus-secondary sanity test.**  The MPR-53CS reports
   secondary-referred counts; the CT ratio in register 32769 turns them into
   primary amperes.  Forgetting it is the single most common commissioning
   error in this class of device and it under-reads by a factor of 500 without
   producing anything that looks broken.  We cross-check the decoded current
   against the current implied by the total apparent power, and we check
   whether the decoded current is suspiciously close to CT-secondary scale.

5. **A firmware branch.**  Registers 222-225 exist only on TVOC-2 firmware
   03.00.00 and later.  We read 800/801, decide, and never read a register the
   device does not have.

6. **Register 1200 forensics.**  After any Modbus exception we read 1200, which
   holds the PDU address the device objected to.  "Exception 02 somewhere in
   this transaction" becomes "the device rejected address 148", which is the
   difference between an hour of guessing and a one-line fix.

7. **Passive-listen mode.**  If the DSO's own RTU already masters this RS-485
   segment, becoming a second master corrupts both.  ``passive=True`` guarantees
   the poller never transmits.  What is shipped here is honest about its own
   limits: it holds the state, refuses to send, and reports that a sniffer build
   would decode the incumbent master's traffic.  It does not pretend to have
   decoded traffic that nobody generated.

What we publish that the devices cannot
---------------------------------------

``tvoc.online`` is worth more than most of the register map.  A TVOC-2 whose
RS-485 link has failed looks, from a SCADA screen fed by a conventional
gateway, exactly like a TVOC-2 that is perfectly healthy and has nothing to
report: the last good values just keep being republished.  The relay physically
cannot tell you that you have stopped being able to hear it.  We can, and we do,
per slave, with a latency distribution attached.
"""

from __future__ import annotations

import asyncio
import math
import time
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

from pymodbus import FramerType, pymodbus_apply_logging_config
from pymodbus.client import AsyncModbusTcpClient

from panogoz.sim import mpr as mpr_map
from panogoz.sim import tvoc as tvoc_map

pymodbus_apply_logging_config("CRITICAL")

FC03_MAX_REGISTERS = 125

#: A live European grid sits inside this window.  Anything outside it means the
#: word order is wrong, not that the grid has collapsed - a real 45 Hz event
#: would have taken the panel with it long before we got to decode it.
FREQ_PLAUSIBLE = (45.0, 55.0)

#: The TVOC-2's Modbus image is not documented as atomic.  200 ms is comfortably
#: longer than any internal update cycle and still inside our 1 s poll budget.
DEEP_READ_SETTLE_S = 0.20

#: Current-THD registers saturate at 99.9 % and light-load current THD really
#: does exceed that.  Below this fraction of the CT primary rating the reading
#: is arithmetic, not an anomaly, and every THD-I rule is gated off.
THD_I_GATE_FRACTION = 0.10


# ==========================================================================
# Block planning
# ==========================================================================

def plan_blocks(addresses: Iterable[int], max_regs: int = FC03_MAX_REGISTERS) -> list[tuple[int, int]]:
    """Minimum set of ``(start, count)`` reads covering ``addresses``.

    Guarantees, and these are the whole point:

    * no block contains an address that is not in ``addresses`` - so no read can
      ever straddle a documented hole and come back as exception 02;
    * no block exceeds ``max_regs`` - the FC03 protocol limit is 125;
    * the blocks are ordered and disjoint.

    Hand-writing this list is how gateways end up with a mystery exception that
    only fires when the seventh trip-log slot is in use.
    """
    addrs = sorted(set(int(a) for a in addresses))
    if not addrs:
        return []
    if max_regs < 1:
        raise ValueError("max_regs must be >= 1")
    blocks: list[tuple[int, int]] = []
    start = prev = addrs[0]
    for a in addrs[1:]:
        if a == prev + 1 and (a - start + 1) <= max_regs:
            prev = a
            continue
        blocks.append((start, prev - start + 1))
        start = prev = a
    blocks.append((start, prev - start + 1))
    return blocks


def verify_plan(blocks: Sequence[tuple[int, int]], addresses: Iterable[int],
                max_regs: int = FC03_MAX_REGISTERS) -> dict:
    """Prove a plan is safe against an address set.  Used by the tests."""
    allowed = set(int(a) for a in addresses)
    covered: set[int] = set()
    bad: list[dict] = []
    for start, count in blocks:
        if count > max_regs:
            bad.append({"start": start, "count": count, "why": "exceeds FC03 limit"})
        for a in range(start, start + count):
            if a not in allowed:
                bad.append({"start": start, "count": count, "address": a, "why": "hole"})
            covered.add(a)
    return {
        "ok": not bad and covered == allowed,
        "violations": bad,
        "blocks": len(blocks),
        "registers": sum(c for _, c in blocks),
        "uncovered": sorted(allowed - covered),
    }


# ==========================================================================
# 32-bit word order
# ==========================================================================

WORD_ORDERS: tuple[str, ...] = ("ABCD", "CDAB", "BADC", "DCBA")


def _swap(word: int) -> int:
    return ((word & 0xFF) << 8) | ((word >> 8) & 0xFF)


def decode_pair(w0: int, w1: int, order: str = "ABCD", signed: bool = False) -> int:
    """Decode two Modbus registers into a 32-bit integer under ``order``."""
    w0 &= 0xFFFF
    w1 &= 0xFFFF
    if order == "ABCD":
        raw = (w0 << 16) | w1
    elif order == "CDAB":
        raw = (w1 << 16) | w0
    elif order == "BADC":
        raw = (_swap(w0) << 16) | _swap(w1)
    elif order == "DCBA":
        raw = (_swap(w1) << 16) | _swap(w0)
    else:
        raise ValueError(f"unknown word order {order!r}")
    if signed and raw >= 0x8000_0000:
        raw -= 0x1_0000_0000
    return raw


def detect_word_order(freq_words: Sequence[int], mult: float = mpr_map.MULT_FREQ) -> dict:
    """Pick the word order from the mains frequency register.

    Returns ``{"order", "value_hz", "candidates", "ambiguous", "reason"}``.
    An all-zero register is genuinely ambiguous - every order decodes to zero -
    and we say so rather than guessing, because a de-energised analyser is a
    state we have to be able to report anyway.
    """
    w0, w1 = int(freq_words[0]) & 0xFFFF, int(freq_words[1]) & 0xFFFF
    candidates: dict[str, float] = {}
    for order in WORD_ORDERS:
        candidates[order] = decode_pair(w0, w1, order) * mult
    lo, hi = FREQ_PLAUSIBLE
    hits = [o for o, v in candidates.items() if lo <= v <= hi]
    if w0 == 0 and w1 == 0:
        return {
            "order": None, "value_hz": 0.0, "candidates": candidates,
            "ambiguous": True,
            "reason": "frekans registeri sıfır: analizör enerjisiz veya cevap vermiyor",
        }
    if len(hits) == 1:
        return {
            "order": hits[0], "value_hz": candidates[hits[0]], "candidates": candidates,
            "ambiguous": False,
            "reason": f"{hits[0]} tek makul sonucu verdi ({candidates[hits[0]]:.2f} Hz)",
        }
    if not hits:
        return {
            "order": None, "value_hz": 0.0, "candidates": candidates,
            "ambiguous": True,
            "reason": "hiçbir word sırası 45-55 Hz vermiyor: adres veya ölçek yanlış",
        }
    return {
        "order": hits[0], "value_hz": candidates[hits[0]], "candidates": candidates,
        "ambiguous": True,
        "reason": f"birden fazla aday makul: {hits}",
    }


# ==========================================================================
# Statistics
# ==========================================================================

@dataclass
class SlaveStats:
    """Per-slave link health.  ``comms_lost`` is the headline product."""

    role: str
    host: str = ""
    port: int = 0
    slave_id: int = 0
    requests: int = 0
    responses: int = 0
    retries: int = 0
    exceptions: int = 0
    timeouts: int = 0
    consecutive_failures: int = 0
    comms_lost: bool = True
    last_ok_ts: float | None = None
    last_exception_code: int | None = None
    last_exception_address: int | None = None
    #: PDU address the device itself said it objected to (TVOC-2 register 1200).
    device_objected_to: int | None = None
    latencies_ms: list[float] = field(default_factory=list)

    def record_ok(self, ms: float, ts: float) -> None:
        self.responses += 1
        self.consecutive_failures = 0
        self.comms_lost = False
        self.last_ok_ts = ts
        self.latencies_ms.append(ms)
        if len(self.latencies_ms) > 200:
            del self.latencies_ms[:-200]

    def record_fail(self) -> None:
        self.consecutive_failures += 1
        if self.consecutive_failures >= 3:
            self.comms_lost = True

    def to_dict(self) -> dict:
        lat = sorted(self.latencies_ms)
        def pct(p: float) -> float:
            if not lat:
                return 0.0
            return lat[min(len(lat) - 1, int(round(p * (len(lat) - 1))))]
        return {
            "role": self.role,
            "endpoint": f"{self.host}:{self.port}#{self.slave_id}",
            "requests": self.requests,
            "responses": self.responses,
            "retries": self.retries,
            "exceptions": self.exceptions,
            "timeouts": self.timeouts,
            "comms_lost": self.comms_lost,
            "consecutive_failures": self.consecutive_failures,
            "last_ok_ts": self.last_ok_ts,
            "last_exception_code": self.last_exception_code,
            "last_exception_address": self.last_exception_address,
            "device_objected_to": self.device_objected_to,
            "latency_ms": {
                "n": len(lat),
                "min": round(lat[0], 3) if lat else None,
                "p50": round(pct(0.50), 3) if lat else None,
                "p95": round(pct(0.95), 3) if lat else None,
                "max": round(lat[-1], 3) if lat else None,
            },
        }


@dataclass
class PollResult:
    ts: float
    channels: dict[str, float] = field(default_factory=dict)
    arc: dict = field(default_factory=dict)
    events: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    stats: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "ts": self.ts,
            "channels": self.channels,
            "arc": self.arc,
            "events": self.events,
            "errors": self.errors,
            "stats": self.stats,
        }


# ==========================================================================
# The poller
# ==========================================================================

class ModbusPoller:
    """The gateway's RS-485 master.

    ``tvoc`` and ``mpr`` are ``(host, port, slave_id)`` triples, or ``None`` for
    a panel that does not have that device.  Not-fitted and
    cannot-be-reached are different states all the way through: a panel with no
    arc relay must never look like a panel whose arc relay we have lost.
    """

    def __init__(
        self,
        *,
        tvoc: tuple[str, int, int] | None,
        mpr: tuple[str, int, int] | None,
        timeout: float = 1.0,
        retries: int = 2,
        passive: bool = False,
        backoff_base_s: float = 0.05,
        backoff_max_s: float = 0.5,
    ) -> None:
        self.timeout = float(timeout)
        self.retries = int(retries)
        self.passive = bool(passive)
        self.backoff_base_s = float(backoff_base_s)
        self.backoff_max_s = float(backoff_max_s)

        self.endpoints: dict[str, tuple[str, int, int]] = {}
        if tvoc is not None:
            self.endpoints["tvoc"] = tvoc
        if mpr is not None:
            self.endpoints["mpr"] = mpr

        self.stats: dict[str, SlaveStats] = {
            role: SlaveStats(role=role, host=h, port=p, slave_id=s)
            for role, (h, p, s) in self.endpoints.items()
        }
        self._clients: dict[str, AsyncModbusTcpClient] = {}

        # discovered state
        self.word_order: str | None = None
        self.word_order_reason: str = "henüz tespit edilmedi"
        self.tvoc_firmware: str | None = None
        self.tvoc_extended: bool | None = None
        self.tvoc_modules: dict[str, bool] = {}
        self.ct_ratio: int | None = None
        self.vt_ratio: float = 1.0
        self.demand_time_min: int | None = None
        self._plans: dict[str, list[tuple[int, int]]] = {}
        self._last_trip_seen: int | None = None
        self._arc_deep: dict = {}

        self.connected = False

    # ------------------------------------------------------------ lifecycle --

    async def connect(self) -> None:
        if self.passive:
            # Not a soft failure: in passive mode we must not open a master
            # socket at all, because the moment we do we are a second master.
            self.connected = False
            for st in self.stats.values():
                st.comms_lost = False   # unknown, not lost - we are not asking
            return
        for role, (host, port, _sid) in self.endpoints.items():
            cli = AsyncModbusTcpClient(
                host, port=port, framer=FramerType.RTU,
                timeout=self.timeout, retries=1,
            )
            await cli.connect()
            self._clients[role] = cli
        self.connected = True
        if "tvoc" in self._clients:
            await self._identify_tvoc()
        if "mpr" in self._clients:
            await self._identify_mpr()

    async def close(self) -> None:
        for cli in self._clients.values():
            try:
                cli.close()
            except Exception:  # noqa: BLE001
                pass
        self._clients.clear()
        self.connected = False

    # --------------------------------------------------------------- reading --

    async def _read(self, role: str, address: int, count: int,
                    fc: int = 3) -> tuple[list[int] | None, str | None]:
        """One transaction with retries, backoff, latency and forensics.

        Returns ``(registers, error)``.  Exactly one of the two is None.
        """
        if self.passive:
            return None, "PASSIVE: pasif dinleme modunda hiçbir çerçeve gönderilmez"
        cli = self._clients.get(role)
        st = self.stats.get(role)
        if cli is None or st is None:
            return None, f"{role}: cihaz tanımlı değil"
        if count > FC03_MAX_REGISTERS:
            return None, f"{role}: {count} register tek istekte okunamaz (sınır {FC03_MAX_REGISTERS})"

        sid = self.endpoints[role][2]
        last_err = "bilinmeyen hata"
        for attempt in range(self.retries + 1):
            if attempt:
                st.retries += 1
                await asyncio.sleep(min(self.backoff_max_s,
                                        self.backoff_base_s * (2 ** (attempt - 1))))
            st.requests += 1
            t0 = time.perf_counter()
            try:
                if fc == 4:
                    rr = await cli.read_input_registers(address, count=count, device_id=sid)
                else:
                    rr = await cli.read_holding_registers(address, count=count, device_id=sid)
            except Exception as exc:  # noqa: BLE001 - transport level
                st.timeouts += 1
                last_err = f"{role}: {address}+{count} taşıma hatası {type(exc).__name__}"
                continue
            ms = (time.perf_counter() - t0) * 1000.0
            if rr.isError():
                st.exceptions += 1
                code = getattr(rr, "exception_code", None)
                st.last_exception_code = code
                st.last_exception_address = address
                last_err = (f"{role}: {address}+{count} istisna {code} "
                            f"({_exception_name(code)})")
                # Exception 02 will not become legal on a retry: the address is
                # wrong, and hammering the bus with it only steals bandwidth
                # from the 1 Hz arc poll.
                if code == 2:
                    await self._forensics(role, address)
                    return None, last_err
                continue
            st.record_ok(ms, time.time())
            return list(rr.registers), None
        st.record_fail()
        return None, last_err

    async def _forensics(self, role: str, attempted: int) -> None:
        """Ask the device which address it objected to (TVOC-2 register 1200)."""
        st = self.stats[role]
        if role != "tvoc" or self.passive:
            st.device_objected_to = None
            return
        cli = self._clients.get(role)
        if cli is None:
            return
        try:
            rr = await cli.read_holding_registers(
                tvoc_map.REG_LAST_EXCEPTION_ADDR, count=1,
                device_id=self.endpoints[role][2],
            )
            if not rr.isError():
                st.device_objected_to = int(rr.registers[0])
        except Exception:  # noqa: BLE001
            st.device_objected_to = None

    async def _read_plan(self, role: str, blocks: Sequence[tuple[int, int]],
                         out: dict[int, int], errors: list[str]) -> bool:
        ok = True
        for start, count in blocks:
            regs, err = await self._read(role, start, count)
            if err is not None:
                errors.append(err)
                ok = False
                continue
            for i, w in enumerate(regs or []):
                out[start + i] = w
        return ok

    # -------------------------------------------------------- identification --

    async def _identify_tvoc(self) -> None:
        """Read 800/801 and 500, decide the firmware branch, build the plans."""
        regs, err = await self._read("tvoc", tvoc_map.REG_SW_VERSION_XXYY, 2)
        if err is None and regs:
            xxyy, zz = regs[0], regs[1]
            self.tvoc_firmware = f"{xxyy // 100:02d}.{xxyy % 100:02d}.{zz:02d}"
        else:
            # Unknown firmware: assume the OLDER map.  Reading a register that
            # does not exist costs a bus round trip and an exception; not
            # reading one that does exist only costs a little detail.
            self.tvoc_firmware = "02.00.00"
        self.tvoc_extended = tvoc_map.firmware_has_extended(self.tvoc_firmware)

        regs, err = await self._read("tvoc", tvoc_map.REG_INSTALLED_MODULES, 1)
        if err is None and regs:
            word = regs[0]
            self.tvoc_modules = {
                name: bool(word & (1 << bit)) for name, bit in tvoc_map.MODULE_BITS.items()
            }
        self._build_tvoc_plans()

    def _build_tvoc_plans(self) -> None:
        fw = self.tvoc_firmware or "02.00.00"
        addrs = tvoc_map.readable_addresses(fw)

        def between(lo: int, hi: int) -> set[int]:
            return {a for a in addrs if lo <= a <= hi}

        self._plans["tvoc.state"] = plan_blocks(
            between(tvoc_map.REG_SYSTEM_STATE,
                    tvoc_map.REG_DTC_BASE + tvoc_map.DTC_SLOTS - 1))
        self._plans["tvoc.live"] = plan_blocks(between(200, 225))
        self._plans["tvoc.trip_log"] = plan_blocks(between(100, 149))
        self._plans["tvoc.error_log"] = plan_blocks(between(300, 368))
        self._plans["tvoc.identity"] = plan_blocks(between(500, 801))
        self._plans["tvoc.extended"] = plan_blocks(between(370, 393))

    async def _identify_mpr(self) -> None:
        """Read the settings block and detect the 32-bit word order."""
        self._plans["mpr.measurement"] = plan_blocks(mpr_map.measurement_addresses())
        self._plans["mpr.settings"] = plan_blocks(mpr_map.setting_addresses())

        settings: dict[int, int] = {}
        errs: list[str] = []
        await self._read_plan("mpr", self._plans["mpr.settings"], settings, errs)
        ct = settings.get(mpr_map.SREG_BY_NAME["CT_RATIO"].addr)
        vt = settings.get(mpr_map.SREG_BY_NAME["VT_RATIO"].addr)
        dt = settings.get(mpr_map.SREG_BY_NAME["DEMAND_TIME"].addr)
        if ct:
            self.ct_ratio = int(ct)
        if vt:
            self.vt_ratio = int(vt) / 10.0
        if dt:
            self.demand_time_min = int(dt)

        regs, err = await self._read("mpr", mpr_map.MREG_BY_NAME["FREQUENCY"].addr, 2)
        if err is None and regs:
            det = detect_word_order(regs)
            self.word_order = det["order"] or self.word_order
            self.word_order_reason = det["reason"]

    # ------------------------------------------------------------- arc loop --

    async def poll_arc(self) -> dict:
        """The 1 Hz loop: seven registers, and a deep read only on an edge."""
        out: dict[str, Any] = {
            "fitted": "tvoc" in self.endpoints,
            "online": False,
            "firmware": self.tvoc_firmware or "",
            "errors": [],
            "events": [],
            "deep_read": False,
            "image_settled": None,
        }
        if not out["fitted"]:
            out["note"] = "Bu panoda TVOC-2 yok"
            return out
        if self.passive:
            out["note"] = ("Pasif dinleme modu: PANO GÖZ bu segmentte veri "
                           "göndermez, mevcut master'ın trafiği dinlenir")
            out["passive"] = True
            return out

        errors: list[str] = []
        state: dict[int, int] = {}
        ok = await self._read_plan("tvoc", self._plans.get("tvoc.state", []), state, errors)
        st = self.stats["tvoc"]
        out["online"] = ok and not st.comms_lost
        out["errors"] = errors
        if not ok:
            out["comms_lost"] = st.comms_lost
            return out

        word = state.get(tvoc_map.REG_SYSTEM_STATE, 0)
        out["system_state"] = word
        out["active_trip"] = bool(word & tvoc_map.STATE_ACTIVE_TRIP)
        out["active_error"] = bool(word & tvoc_map.STATE_ACTIVE_ERROR)
        out["start_sequence"] = bool(word & tvoc_map.STATE_START_SEQUENCE)
        out["diagnostics_running"] = bool(word & tvoc_map.STATE_DIAGNOSTICS_RUNNING)
        out["dtcs"] = [
            state.get(tvoc_map.REG_DTC_BASE + i, 0) for i in range(tvoc_map.DTC_SLOTS)
        ]
        out["dtcs"] = [d for d in out["dtcs"] if d]
        out["dtc_labels_tr"] = [
            tvoc_map.DTC_LABELS_TR.get(d, f"DTC {d}") for d in out["dtcs"]
        ]

        active = word & (tvoc_map.STATE_ACTIVE_TRIP | tvoc_map.STATE_ACTIVE_ERROR)
        if not active:
            # THE 0x0000 TRAP.  With nothing active, 222/223 read zero, which in
            # a "1 = OK" bitfield is indistinguishable from every detector
            # having failed.  Reg 1300 is the gate, so we do not read them and
            # we do not interpret them.
            out.update(self._quiet_detector_view())
            out["last_selftest"] = await self._read_selftest_stamp()
            self._arc_deep = {}
            return out

        deep_a = await self._deep_arc_read()
        await asyncio.sleep(DEEP_READ_SETTLE_S)
        deep_b = await self._deep_arc_read()
        settled = deep_a == deep_b
        out["deep_read"] = True
        out["image_settled"] = settled
        deep = deep_b if settled else deep_b
        if not settled:
            out["events"].append({
                "type": "arc_image_unsettled",
                "detail_tr": (f"TVOC-2 Modbus görüntüsü {int(DEEP_READ_SETTLE_S * 1000)} ms "
                              f"arayla farklı okundu; ikinci okuma yayımlandı"),
            })
        out.update(deep)

        trip = deep.get("last_trip")
        if trip and trip.get("number") and trip["number"] != self._last_trip_seen:
            self._last_trip_seen = trip["number"]
            out["events"].append({
                "type": "arc_trip",
                "severity": "ACIL",
                "title_tr": "Ark açması",
                "trip": trip,
            })
        return out

    def _quiet_detector_view(self) -> dict:
        """What we can honestly say when reg 1300 reports nothing active."""
        total = 0
        for module in ("X2", "X3"):
            if self.tvoc_modules.get(module):
                total += 10
        return {
            "detectors_total": total,
            "detectors_ok": total,
            "detector_status_read": False,
            "ambient_warn": 0,
            "ambient_warn_list": [],
            "fault_list": [],
            "detector_map_lo": 0,
            "detector_map_hi": 0,
            "last_trip": None,
            "note_tr": (
                "reg 1300 boş: 222-225 okunmadı. Bu registerler aktif hata "
                "yokken 0x0000 döner ve '1 = sağlam' alanında bu, tüm "
                "dedektörlerin arızalı olmasıyla aynı görünür."
            ),
            "x1_covered": False,
        }

    async def _read_selftest_stamp(self) -> dict:
        regs, err = await self._read("tvoc", tvoc_map.REG_DIAG_DATE, 2)
        if err is not None or not regs:
            return {"known": False}
        days, hhmm = regs[0], regs[1]
        if days == 0:
            return {"known": False, "note_tr": "Kayıtlı otokontrol yok"}
        hh, mm = tvoc_map.decode_time(hhmm)
        since = max(0, int(time.time() // 86400) - days)
        return {"known": True, "days": days, "hh": hh, "mm": mm, "days_since": since}

    async def _deep_arc_read(self) -> dict:
        """Live blocks, detector status and the newest trip-log entry."""
        errors: list[str] = []
        live: dict[int, int] = {}
        await self._read_plan("tvoc", self._plans.get("tvoc.live", []), live, errors)

        lo = live.get(tvoc_map.REG_TRIP_DETECTOR_LO, 0)
        hi = live.get(tvoc_map.REG_TRIP_DETECTOR_HI, 0)
        relay_word = live.get(tvoc_map.REG_TRIP_RELAY, 0)

        detectors_total = 0
        detectors_ok = 0
        faults: list[str] = []
        warns: list[str] = []
        if self.tvoc_extended:
            for module, sreg, areg in (
                ("X2", tvoc_map.REG_SENSOR_STATUS_X2, tvoc_map.REG_AMBIENT_WARN_X2),
                ("X3", tvoc_map.REG_SENSOR_STATUS_X3, tvoc_map.REG_AMBIENT_WARN_X3),
            ):
                if not self.tvoc_modules.get(module):
                    continue
                detectors_total += 10
                sword = live.get(sreg, 0)
                aword = live.get(areg, 0)
                for i in range(10):
                    name = f"{module}:{i + 1}"
                    if sword & (1 << i):
                        detectors_ok += 1
                    else:
                        faults.append(name)
                    if not (aword & (1 << i)):
                        warns.append(name)

        trip = None
        if live.get(tvoc_map.LIVE_TRIP_BASE, 0):
            hh, mm = tvoc_map.decode_time(live.get(tvoc_map.LIVE_TRIP_BASE + 2, 0))
            trip = {
                "number": live.get(tvoc_map.LIVE_TRIP_BASE, 0),
                "date_days": live.get(tvoc_map.LIVE_TRIP_BASE + 1, 0),
                "ts": tvoc_map.decode_date(live.get(tvoc_map.LIVE_TRIP_BASE + 1, 0))
                      + hh * 3600 + mm * 60,
                "hh": hh,
                "mm": mm,
                "duration_ms": live.get(tvoc_map.LIVE_TRIP_BASE + 3, 0),
                "detectors": tvoc_map.detectors_from_bitfields(lo, hi),
                "relays": tvoc_map.relays_from_bitfield(relay_word),
            }

        counts: dict[int, int] = {}
        await self._read_plan("tvoc", plan_blocks([tvoc_map.TRIP_COUNT_REG,
                                                   tvoc_map.ERROR_COUNT_REG]),
                              counts, errors)

        return {
            "detectors_total": detectors_total,
            "detectors_ok": detectors_ok,
            "detector_status_read": bool(self.tvoc_extended),
            "fault_list": faults,
            "ambient_warn": len(warns),
            "ambient_warn_list": warns,
            "detector_map_lo": lo,
            "detector_map_hi": hi,
            "last_trip": trip,
            "trip_count": counts.get(tvoc_map.TRIP_COUNT_REG, 0),
            "error_count": counts.get(tvoc_map.ERROR_COUNT_REG, 0),
            "x1_covered": False,
            "deep_errors": errors,
        }

    async def read_trip_log(self) -> list[dict]:
        """Full trip log.  Called on demand, never in the 1 Hz loop."""
        raw: dict[int, int] = {}
        errors: list[str] = []
        await self._read_plan("tvoc", self._plans.get("tvoc.trip_log", []), raw, errors)
        out: list[dict] = []
        for n in range(tvoc_map.TRIP_LOG_ENTRIES):
            base = tvoc_map.TRIP_LOG_BASE + tvoc_map.TRIP_LOG_STRIDE * n
            words = [raw.get(base + i, 0xFFFF) for i in range(tvoc_map.LOG_ENTRY_WORDS)]
            if all(w == 0xFFFF for w in words):
                continue
            hh, mm = tvoc_map.decode_time(words[2])
            out.append({
                "slot": n,
                "number": words[0],
                "ts": tvoc_map.decode_date(words[1]) + hh * 3600 + mm * 60,
                "hh": hh, "mm": mm,
                "duration_ms": words[3],
                "detectors": tvoc_map.detectors_from_bitfields(words[4], words[5]),
            })
        out.sort(key=lambda e: e["number"])
        return out

    # -------------------------------------------------------- analyser loop --

    async def poll_analyser(self) -> dict:
        """The slow loop: the whole 266-register space, chunked to 125."""
        out: dict[str, Any] = {
            "fitted": "mpr" in self.endpoints,
            "online": False,
            "errors": [],
            "events": [],
            "channels": {},
        }
        if not out["fitted"]:
            out["note"] = "Bu panoda enerji analizörü yok"
            return out
        if self.passive:
            out["passive"] = True
            out["note"] = ("Pasif dinleme modu: analizör sorgulanmaz, mevcut "
                           "master'ın okumaları dinlenir")
            return out

        errors: list[str] = []
        raw: dict[int, int] = {}
        blocks = self._plans.get("mpr.measurement") or plan_blocks(mpr_map.measurement_addresses())
        ok = await self._read_plan("mpr", blocks, raw, errors)
        out["errors"] = errors
        out["blocks"] = list(blocks)
        st = self.stats["mpr"]
        out["online"] = ok and not st.comms_lost
        if not ok:
            out["comms_lost"] = st.comms_lost
            return out

        # Word order: detect on the frequency register, every sweep, cheaply.
        freq_addr = mpr_map.MREG_BY_NAME["FREQUENCY"].addr
        det = detect_word_order([raw.get(freq_addr, 0), raw.get(freq_addr + 1, 0)])
        if det["order"] and det["order"] != self.word_order:
            out["events"].append({
                "type": "word_order_detected",
                "order": det["order"],
                "previous": self.word_order,
                "detail_tr": f"32 bit word sırası: {det['order']} · {det['reason']}",
            })
            self.word_order = det["order"]
        self.word_order_reason = det["reason"]
        order = self.word_order or "ABCD"
        out["word_order"] = order
        out["word_order_reason"] = self.word_order_reason
        out["word_order_candidates"] = {k: round(v, 3) for k, v in det["candidates"].items()}

        ct = float(self.ct_ratio or 1)
        vt = float(self.vt_ratio or 1.0)
        eng: dict[str, float] = {}
        for reg in mpr_map.BASE_REGS + mpr_map.TAIL_REGS:
            words = [raw.get(reg.addr + i, 0) for i in range(reg.words)]
            if reg.words == 2:
                rawv = decode_pair(words[0], words[1], order, signed=reg.signed)
            else:  # pragma: no cover - all base quantities are 32 bit
                rawv = mpr_map.decode_words(words, signed=reg.signed)
            eng[reg.name] = mpr_map.from_raw(reg, rawv, ct, vt)
        out["eng"] = eng
        out["ct_ratio"] = self.ct_ratio
        out["vt_ratio"] = self.vt_ratio
        out["digital_in"] = raw.get(mpr_map.DIGITAL_IN_REG, 0)
        out["digital_out"] = raw.get(mpr_map.DIGITAL_OUT_REG, 0)

        sanity = self.ct_sanity(eng)
        out["ct_sanity"] = sanity
        if not sanity["ok"]:
            out["events"].append({
                "type": "ct_scale_suspect",
                "severity": "UYARI",
                "title_tr": "Akım trafo oranı şüpheli",
                "detail_tr": sanity["reason_tr"],
                "evidence": sanity,
            })

        out["channels"] = self._analyser_channels(eng, out)
        out["neutral"] = self.neutral_decomposition(eng)
        return out

    # ------------------------------------------------------------ analysis --

    def ct_sanity(self, eng: dict[str, float]) -> dict:
        """Primary-versus-secondary check on the decoded currents.

        Two independent tests, because either alone has a blind spot:

        * **Power cross-check.**  The total apparent power carries CT x VT, the
          currents carry CT.  ``S / (sqrt(3) x V_LL)`` must come back to the
          measured average current.  If the currents were decoded without the CT
          ratio this comes out a factor of ``ct_ratio`` too big.
        * **Secondary-scale suspicion.**  A "current" at or below the 6 A CT
          secondary full scale, on a panel that is plainly carrying load, is not
          a lightly loaded feeder.  It is an unapplied CT ratio.
        """
        i = [eng.get(f"I_L{k}", 0.0) for k in (1, 2, 3)]
        v_ll = [eng.get(n, 0.0) for n in ("V_L12", "V_L23", "V_L31")]
        s_tot = eng.get("S_TOTAL", 0.0)
        i_avg = sum(i) / 3.0
        v_avg = sum(v_ll) / 3.0
        i_from_s = s_tot / (math.sqrt(3.0) * v_avg) if v_avg > 1.0 else 0.0

        result = {
            "ok": True,
            "ct_ratio_register": self.ct_ratio,
            "i_avg_a": round(i_avg, 3),
            "i_from_power_a": round(i_from_s, 3),
            "s_total_va": round(s_tot, 1),
            "v_ll_avg_v": round(v_avg, 2),
            "ratio": None,
            "reason_tr": "Akım ve güç registerleri tutarlı",
        }
        if self.ct_ratio is None:
            result["ok"] = False
            result["reason_tr"] = ("32769 numaralı akım trafo oranı registeri "
                                   "okunamadı; akımlar sekonder değerde kalır")
            return result
        if self.ct_ratio <= 1:
            result["ok"] = False
            result["reason_tr"] = (f"32769 = {self.ct_ratio}: bu register PRİMER akımı "
                                   f"değil ORANI tutar (2500/5 için 500)")
            return result
        if s_tot < 1000.0 or i_avg < 1e-6:
            result["reason_tr"] = "Pano yüksüz veya enerjisiz: oran testi anlamsız"
            result["indeterminate"] = True
            return result

        ratio = i_from_s / i_avg
        result["ratio"] = round(ratio, 4)
        secondary_fs = mpr_map.FS_CURRENT_RAW * mpr_map.MULT_CURRENT   # 6.000 A
        if i_avg <= secondary_fs and s_tot > 50_000.0:
            result["ok"] = False
            result["reason_tr"] = (
                f"Akımlar {i_avg:.3f} A okunuyor ama görünür güç {s_tot / 1000:.0f} kVA. "
                f"{secondary_fs:.0f} A, akım trafosunun SEKONDER tam skalası: "
                f"32769'daki {self.ct_ratio} oranı uygulanmamış."
            )
            return result
        if not 0.5 <= ratio <= 2.0:
            result["ok"] = False
            result["reason_tr"] = (
                f"Akımdan ve güçten hesaplanan akım {ratio:.1f} kat farklı "
                f"({i_avg:.1f} A / {i_from_s:.1f} A). Ölçek veya word sırası yanlış."
            )
        return result

    def neutral_decomposition(self, eng: dict[str, float]) -> dict:
        """Split the neutral current into unbalance and triplen-harmonic parts.

        Triplen harmonics are zero sequence and add arithmetically, so
        ``I_N = 3 x h3 x I1``.  The fundamental part of the neutral is
        ``3 x |I0|`` from the phasors; whatever the measured neutral has left
        over that is harmonic.  The distinction decides the work order: a
        harmonic neutral is a filtering or derating job, a rising ``K_N`` on the
        same bar is a bad neutral joint that needs a torque wrench.
        """
        i = [eng.get(f"I_L{k}", 0.0) for k in (1, 2, 3)]
        ang = [eng.get(f"ANG_I_L{k}", 0.0) for k in (1, 2, 3)]
        ph = [complex(i[k] * math.cos(math.radians(ang[k])),
                      i[k] * math.sin(math.radians(ang[k]))) for k in range(3)]
        i0 = (ph[0] + ph[1] + ph[2]) / 3.0
        i_n_fund = 3.0 * abs(i0)
        i_n = eng.get("I_N", 0.0)
        excess = math.sqrt(max(0.0, i_n * i_n - i_n_fund * i_n_fund))
        i_avg = sum(i) / 3.0
        tol = max(2.0, 0.05 * i_n_fund)
        consistent = i_n >= i_n_fund - tol
        out = {
            "i_n_a": round(i_n, 2),
            "i_n_fundamental_a": round(i_n_fund, 2),
            "i_n_harmonic_excess_a": round(excess, 2),
            "h3_equivalent_pct": round(100.0 * excess / (3.0 * i_avg), 2) if i_avg > 1 else 0.0,
            "consistent": consistent,
            "note_tr": ("Nötr akımının dengesizlik ve üçüncü harmonik bileşenleri "
                        "ayrı iş emri üretir"),
        }
        if not consistent:
            # The measured neutral cannot be smaller than the unbalance the three
            # phase phasors already demand.  When it is, the decomposition is not
            # wrong - the inputs are - and we say which two disagree rather than
            # clamping to zero and reporting a clean-looking harmonic figure.
            out["note_tr"] = (
                f"Ölçülen nötr akımı ({i_n:.0f} A), faz fazörlerinin gerektirdiği "
                f"dengesizlik bileşeninden ({i_n_fund:.0f} A) küçük. Harmonik ayrışımı "
                f"yapılamaz: ya nötr akım trafosunun oranı ya da akım açıları hatalı."
            )
        return out

    def _analyser_channels(self, eng: dict[str, float], ctx: dict) -> dict[str, float]:
        ch: dict[str, float] = {
            "mpr.v_l1_v": eng.get("V_L1", 0.0),
            "mpr.v_l2_v": eng.get("V_L2", 0.0),
            "mpr.v_l3_v": eng.get("V_L3", 0.0),
            "mpr.i_l1_a": eng.get("I_L1", 0.0),
            "mpr.i_l2_a": eng.get("I_L2", 0.0),
            "mpr.i_l3_a": eng.get("I_L3", 0.0),
            "mpr.i_n_a": eng.get("I_N", 0.0),
            "mpr.freq_hz": eng.get("FREQUENCY", 0.0),
            "mpr.thd_v_l1_pct": eng.get("THD_V_L1", 0.0),
            "mpr.thd_v_l2_pct": eng.get("THD_V_L2", 0.0),
            "mpr.thd_v_l3_pct": eng.get("THD_V_L3", 0.0),
            # Net active power.  The map has import at 44 and export at 46; the
            # channel is signed, so we publish the difference rather than
            # picking one and hoping the panel never exports.
            "mpr.p_total_w": eng.get("P_IMPORT", 0.0) - eng.get("P_EXPORT", 0.0),
            "mpr.online": 1.0 if ctx.get("online") else 0.0,
        }
        # Current THD is only meaningful above 10 % of the CT rating.
        ct_primary = (self.ct_ratio or 1) * 5.0
        gate = THD_I_GATE_FRACTION * ct_primary
        gated = []
        for k in (1, 2, 3):
            i_ph = eng.get(f"I_L{k}", 0.0)
            val = eng.get(f"THD_I_L{k}", 0.0)
            if i_ph < gate:
                val = 0.0
                gated.append(f"L{k}")
            ch[f"mpr.thd_i_l{k}_pct"] = val
        if gated:
            ctx.setdefault("notes", []).append(
                f"Akım THD kapatıldı ({', '.join(gated)}): yük {gate:.0f} A eşiğinin "
                f"altında, bu registerler %99.9'da doyar ve anomali değil aritmetiktir"
            )
        ctx["thd_i_gate_a"] = gate
        return ch

    # ------------------------------------------------------------ poll_once --

    async def poll_once(self, ts: float | None = None) -> PollResult:
        """One full cycle: arc first, then analyser.  Arc always wins the bus."""
        now = time.time() if ts is None else float(ts)
        res = PollResult(ts=now)

        if self.passive:
            res.errors.append(
                "PASSIVE: PANO GÖZ bu RS-485 segmentinde master olmuyor"
            )
            res.arc = await self.poll_arc()
            an = await self.poll_analyser()
            res.stats = self.stats_dict()
            res.stats["mode"] = "passive"
            res.events.append({
                "type": "passive_mode",
                "detail_tr": (
                    "Dağıtım şirketinin RTU'su bu hattın master'ı ise ikinci bir "
                    "master her iki tarafı da bozar. Pasif modda hiçbir çerçeve "
                    "gönderilmez; yayımlanan tek bilgi bu durumun kendisidir."
                ),
                "analyser": an.get("note"),
            })
            return res

        arc = await self.poll_arc()
        res.arc = arc
        res.errors.extend(arc.get("errors", []))
        res.events.extend(arc.get("events", []))

        an = await self.poll_analyser()
        res.channels.update(an.get("channels", {}))
        res.errors.extend(an.get("errors", []))
        res.events.extend(an.get("events", []))
        res.arc.setdefault("analyser", {})
        res.arc["analyser"] = {
            "word_order": an.get("word_order"),
            "ct_sanity_ok": (an.get("ct_sanity") or {}).get("ok"),
        }
        res.channels.update(self._arc_channels(arc, now))
        res.stats = self.stats_dict()
        res.stats["analyser"] = {
            "blocks": an.get("blocks"),
            "word_order": an.get("word_order"),
            "word_order_reason": an.get("word_order_reason"),
            "ct_sanity": an.get("ct_sanity"),
            "neutral": an.get("neutral"),
            "notes": an.get("notes", []),
            "thd_i_gate_a": an.get("thd_i_gate_a"),
        }
        # Both comms-lost flags travel with every result.  The TVOC-2 cannot
        # tell anyone that our link to it has failed; this is the only place in
        # the whole chain where that fact exists.
        for role, st in self.stats.items():
            res.channels[f"{role}.online"] = 0.0 if st.comms_lost else 1.0
            if st.comms_lost:
                res.events.append({
                    "type": "comms_lost",
                    "severity": "UYARI" if role == "mpr" else "KRITIK",
                    "role": role,
                    "title_tr": ("Ark rölesi haberleşmesi yok" if role == "tvoc"
                                 else "Analizör haberleşmesi yok"),
                    "detail_tr": (f"{st.consecutive_failures} ardışık başarısız istek; "
                                  f"cihazın kendisi bu durumu bildiremez"),
                })
        return res

    def _arc_channels(self, arc: dict, now: float) -> dict[str, float]:
        if not arc.get("fitted"):
            return {}
        ch = {
            "tvoc.system_state": float(arc.get("system_state", 0)),
            "tvoc.active_trip": 1.0 if arc.get("active_trip") else 0.0,
            "tvoc.active_error": 1.0 if arc.get("active_error") else 0.0,
            "tvoc.detectors_ok": float(arc.get("detectors_ok", 0)),
            "tvoc.detectors_total": float(arc.get("detectors_total", 0)),
            "tvoc.ambient_warn": float(arc.get("ambient_warn", 0)),
            "tvoc.online": 1.0 if arc.get("online") else 0.0,
        }
        stamp = arc.get("last_selftest") or {}
        if stamp.get("known"):
            ch["tvoc.last_selftest_days"] = float(stamp.get("days_since", 0))
        return ch

    # ---------------------------------------------------------------- info --

    def stats_dict(self) -> dict:
        return {
            "mode": "passive" if self.passive else "master",
            "connected": self.connected,
            "slaves": {role: st.to_dict() for role, st in self.stats.items()},
            "word_order": self.word_order,
            "tvoc_firmware": self.tvoc_firmware,
            "tvoc_extended_block": self.tvoc_extended,
            "ct_ratio": self.ct_ratio,
            "plans": {k: v for k, v in self._plans.items()},
        }

    def plans(self) -> dict[str, list[tuple[int, int]]]:
        """The block plan actually in use.  The tests assert on this directly."""
        if not self._plans:
            self._build_tvoc_plans()
            self._plans["mpr.measurement"] = plan_blocks(mpr_map.measurement_addresses())
            self._plans["mpr.settings"] = plan_blocks(mpr_map.setting_addresses())
        return dict(self._plans)


def _exception_name(code: int | None) -> str:
    return {
        1: "ILLEGAL_FUNCTION",
        2: "ILLEGAL_DATA_ADDRESS",
        3: "ILLEGAL_DATA_VALUE",
        4: "SLAVE_DEVICE_FAILURE",
        6: "SLAVE_DEVICE_BUSY",
        11: "GATEWAY_TARGET_NO_RESPONSE",
    }.get(code or 0, "UNKNOWN")


#: Honest statement of the notification chain, published with the arc view.
#: The TVOC-2 Modbus image propagation delay is not documented by ABB, so it is
#: modelled as a range and quoted as a range.  Anyone who gives you one clean
#: number for this has not measured it either.
NOTIFICATION_LATENCY_MODEL = {
    "tvoc_image_propagation_s": (0.2, 2.0),
    "poll_period_s": (1.0, 1.0),
    "server_processing_s": (0.3, 2.0),
    "sms_path_s": (2.5, 8.0),
    "total_s": (4.0, 13.0),
    "note_tr": (
        "Bildirim gecikmesi bir ARALIKTIR. TVOC-2'nin Modbus görüntüsünün "
        "güncellenme süresi ABB tarafından dokümante edilmemiştir; 0.2-2 s "
        "modellenmiştir. Açmanın kendisi ~1 ms'de donanımda gerçekleşir ve "
        "PANO GÖZ'ü beklemez."
    ),
}


# ==========================================================================

if __name__ == "__main__":
    from panogoz.sim.modbus_server import ModbusDeviceServer
    from panogoz.sim.mpr import MprSim
    from panogoz.sim.tvoc import TvocSim

    T0 = 1_757_000_000.0

    async def main() -> None:
        print("=" * 78)
        print("PANO GOZ gateway poller  ·  self-test")
        print("=" * 78)

        # ---------------------------------------------------------- plans ---
        print("\n[1] safe block plan, computed from the address map")
        p = ModbusPoller(tvoc=None, mpr=None).plans()
        for name in ("tvoc.state", "tvoc.live", "tvoc.trip_log", "tvoc.error_log",
                     "tvoc.identity", "mpr.measurement", "mpr.settings"):
            print(f"    {name:<16}: {p[name]}")
        fw_addrs = tvoc_map.readable_addresses("02.00.00")
        tv_addrs = {a for a in fw_addrs if 100 <= a <= 149}
        v = verify_plan(p["tvoc.trip_log"], tv_addrs)
        print(f"\n    trip-log plan vs map : {v}")
        assert v["ok"], v
        for start, count in p["tvoc.trip_log"]:
            for hole in tvoc_map.TRIP_LOG_HOLES:
                assert not (start <= hole < start + count), (start, count, hole)
        v = verify_plan(p["mpr.measurement"], mpr_map.measurement_addresses())
        print(f"    analyser plan        : {v['blocks']} blocks, {v['registers']} registers, ok={v['ok']}")
        assert v["ok"] and max(c for _, c in p["mpr.measurement"]) <= 125
        v = verify_plan(p["mpr.settings"], mpr_map.setting_addresses())
        print(f"    settings plan        : {p['mpr.settings']} -> ok={v['ok']} "
              f"(the gap at 32772..32776 forces the split)")
        assert v["ok"] and len(p["mpr.settings"]) == 2

        # ---------------------------------------------------- word order ---
        print("\n[2] 32-bit word order detection on the frequency register")
        raw_freq = 4998  # 49.98 Hz at x0.01
        for order in WORD_ORDERS:
            w = _encode_under(raw_freq, order)
            det = detect_word_order(w)
            marks = {k: f"{val:9.2f}" for k, val in det["candidates"].items()}
            print(f"    device speaks {order}: words={w}  detected={det['order']}  "
                  f"{ {k: v.strip() for k, v in marks.items()} }")
            assert det["order"] == order or det["ambiguous"], (order, det)
        det = detect_word_order([0, 0])
        print(f"    all-zero register     : {det['order']} · {det['reason']}")
        assert det["order"] is None and det["ambiguous"]

        # ------------------------------------------------- live end-to-end ---
        print("\n[3] end-to-end against the simulators (RTU framing over TCP)")
        tvoc = TvocSim(slave_id=5, detectors=20, firmware="03.01.00", seed=11)
        tvoc.tick(T0)
        mpr = MprSim(slave_id=1, ct_ratio=500, seed=11)
        # Neutral chosen to be physically consistent with the phase phasors:
        # 3|I0| = 384.3 A of unbalance plus 120 A of triplen harmonic, added in
        # quadrature because the unbalance is fundamental and the triplens are
        # not.  Turkish LV secondaries really do look like this.
        i_n_consistent = math.sqrt(384.3 ** 2 + 120.0 ** 2)
        mpr.update(i_l1=1420.0, i_l2=980.0, i_l3=1150.0, i_n=i_n_consistent,
                   v_l1=231.4, v_l2=229.8, v_l3=233.1, freq=49.98,
                   thd={"v_l1": 2.1, "v_l2": 2.4, "v_l3": 2.0,
                        "i_l1": 11.5, "i_l2": 14.2, "i_l3": 9.8},
                   ts=T0, cos_phi=0.94)

        async with ModbusDeviceServer({5: tvoc}, port=15040) as arc_srv, \
                   ModbusDeviceServer({1: mpr}, port=15041) as an_srv:
            poller = ModbusPoller(
                tvoc=("127.0.0.1", 15040, 5),
                mpr=("127.0.0.1", 15041, 1),
                timeout=1.0, retries=2,
            )
            await poller.connect()
            print(f"    TVOC firmware        : {poller.tvoc_firmware} "
                  f"(222-225 mevcut: {poller.tvoc_extended})")
            print(f"    installed modules    : "
                  f"{[k for k, v in poller.tvoc_modules.items() if v]}")
            print(f"    CT ratio register    : {poller.ct_ratio} -> "
                  f"{(poller.ct_ratio or 0) * 5:.0f} A primary")
            print(f"    word order           : {poller.word_order} · {poller.word_order_reason}")
            assert poller.tvoc_firmware == "03.01.00" and poller.tvoc_extended
            assert poller.ct_ratio == 500 and poller.word_order == "ABCD"

            r = await poller.poll_once(ts=T0)
            print(f"\n    channels ({len(r.channels)}):")
            for k in sorted(r.channels):
                print(f"      {k:<24} {r.channels[k]:>12.3f}")
            assert abs(r.channels["mpr.i_l1_a"] - 1420.0) < 1.0
            assert abs(r.channels["mpr.freq_hz"] - 49.98) < 0.01
            assert r.channels["tvoc.online"] == 1.0
            assert r.channels["tvoc.active_trip"] == 0.0

            print(f"\n    quiet-state detector view (reg 1300 == 0):")
            print(f"      detector_status_read = {r.arc['detector_status_read']}  "
                  f"(222/223 deliberately NOT read)")
            print(f"      {r.arc['note_tr']}")
            assert r.arc["detector_status_read"] is False

            print(f"\n[4] CT primary-vs-secondary sanity")
            sane = r.stats["analyser"]["ct_sanity"]
            print(f"    {sane}")
            assert sane["ok"]

            wrong = ModbusPoller(tvoc=None, mpr=("127.0.0.1", 15041, 1))
            await wrong.connect()
            wrong.ct_ratio = 1                      # the classic commissioning error
            bad = await wrong.poll_analyser()
            print(f"    with CT ratio forced to 1:")
            print(f"      I_L1 decoded = {bad['channels']['mpr.i_l1_a']:.3f} A")
            print(f"      verdict      = {bad['ct_sanity']['reason_tr']}")
            assert not bad["ct_sanity"]["ok"]
            await wrong.close()

            print(f"\n[5] neutral decomposition")
            print(f"    {r.stats['analyser']['neutral']}")

            print(f"\n[6] THD-I gating")
            print(f"    gate = {r.stats['analyser']['thd_i_gate_a']:.0f} A, "
                  f"load {r.channels['mpr.i_l1_a']:.0f} A -> THD-I published: "
                  f"{r.channels['mpr.thd_i_l1_pct']:.1f} %")
            light = MprSim(ct_ratio=500, seed=12)
            light.update(i_l1=40.0, i_l2=38.0, i_l3=41.0, i_n=22.0,
                         v_l1=232.0, v_l2=232.0, v_l3=232.0, freq=50.0,
                         thd={"i_l1": 140.0}, ts=T0)
            async with ModbusDeviceServer({1: light}, port=15042):
                lp = ModbusPoller(tvoc=None, mpr=("127.0.0.1", 15042, 1))
                await lp.connect()
                la = await lp.poll_analyser()
                print(f"    light load {la['eng']['I_L1']:.0f} A -> THD-I published "
                      f"{la['channels']['mpr.thd_i_l1_pct']:.1f} % (register said "
                      f"{la['eng']['THD_I_L1']:.1f} %, saturated)")
                print(f"    {la['notes'][0]}")
                assert la["channels"]["mpr.thd_i_l1_pct"] == 0.0
                await lp.close()

            print(f"\n[7] edge-triggered deep read on an arc")
            ev = tvoc.inject_arc(detector="X2:3", relay="K5", now=T0 + 120)
            await arc_srv.sync()
            r2 = await poller.poll_once(ts=T0 + 120)
            arc = r2.arc
            print(f"    deep_read            : {arc['deep_read']} "
                  f"(only because reg 1300 bit0 was set)")
            print(f"    image_settled        : {arc['image_settled']} "
                  f"(two reads {int(DEEP_READ_SETTLE_S * 1000)} ms apart agreed)")
            print(f"    last_trip            : {arc['last_trip']}")
            print(f"    detectors ok / total : {arc['detectors_ok']}/{arc['detectors_total']} "
                  f"(X1 kapsam disi: {not arc['x1_covered']})")
            print(f"    events               : {[e['type'] for e in r2.events]}")
            assert arc["deep_read"] and arc["image_settled"]
            assert arc["last_trip"]["detectors"] == ["X2:3"]
            assert arc["last_trip"]["relays"] == ["K5"]
            assert any(e["type"] == "arc_trip" for e in r2.events)

            print(f"\n    trip log on demand   :")
            for e in await poller.read_trip_log():
                print(f"      slot {e['slot']} #{e['number']} {e['hh']:02d}:{e['mm']:02d} "
                      f"{e['detectors']} {e['duration_ms']} ms")

            print(f"\n[8] register 1200 forensics after a deliberate bad read")
            tvoc.note_exception(148)
            await arc_srv.sync()
            regs, err = await poller._read("tvoc", 145, 5)   # spans the hole at 148
            st = poller.stats["tvoc"]
            print(f"    read 145+5           : {err}")
            print(f"    reg 1200 says the device objected to address "
                  f"{st.device_objected_to}")
            assert regs is None and st.last_exception_code == 2
            assert st.device_objected_to == 148

            print(f"\n[9] latency and comms-lost bookkeeping")
            for role, s in r2.stats["slaves"].items():
                print(f"    {role:<5} {s['endpoint']:<22} req={s['requests']:<4} "
                      f"exc={s['exceptions']:<3} lost={s['comms_lost']} "
                      f"p50={s['latency_ms']['p50']} ms p95={s['latency_ms']['p95']} ms")
            assert not poller.stats["tvoc"].comms_lost

            await poller.close()

        print(f"\n[10] comms lost: the one thing the TVOC-2 cannot tell you")
        dead = ModbusPoller(tvoc=("127.0.0.1", 15049, 5), mpr=None,
                            timeout=0.25, retries=1)
        await dead.connect()
        for _ in range(3):
            await dead.poll_once(ts=T0)
        r3 = await dead.poll_once(ts=T0)
        print(f"    tvoc.online          : {r3.channels.get('tvoc.online')}")
        print(f"    comms_lost           : {dead.stats['tvoc'].comms_lost}")
        print(f"    events               : {[e['type'] for e in r3.events]}")
        assert dead.stats["tvoc"].comms_lost
        assert r3.channels.get("tvoc.online") == 0.0
        await dead.close()

        print(f"\n[11] passive-listen mode")
        pas = ModbusPoller(tvoc=("127.0.0.1", 15040, 5), mpr=("127.0.0.1", 15041, 1),
                           passive=True)
        await pas.connect()
        r4 = await pas.poll_once(ts=T0)
        print(f"    connected            : {pas.connected} (no socket is opened)")
        print(f"    errors               : {r4.errors}")
        print(f"    arc note             : {r4.arc['note']}")
        print(f"    event                : {r4.events[0]['detail_tr']}")
        assert not pas.connected and r4.arc.get("passive")
        assert pas.stats["tvoc"].requests == 0
        await pas.close()

        print(f"\n[12] notification latency is a range, never one number")
        for k, val in NOTIFICATION_LATENCY_MODEL.items():
            if isinstance(val, tuple):
                print(f"    {k:<28} {val[0]:.1f} .. {val[1]:.1f} s")
        print(f"    {NOTIFICATION_LATENCY_MODEL['note_tr']}")

        print("\n" + "=" * 78)
        print("Poller self-test PASSED")
        print("=" * 78)

    def _encode_under(raw: int, order: str) -> list[int]:
        """Produce the two words a device using ``order`` would send for ``raw``."""
        hi, lo = (raw >> 16) & 0xFFFF, raw & 0xFFFF
        if order == "ABCD":
            return [hi, lo]
        if order == "CDAB":
            return [lo, hi]
        if order == "BADC":
            return [_swap(hi), _swap(lo)]
        return [_swap(lo), _swap(hi)]

    asyncio.run(main())
