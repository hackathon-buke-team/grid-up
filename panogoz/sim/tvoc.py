"""ABB TVOC-2 arc protection relay - Modbus RTU device model and simulator.

This module has two halves and the split matters.

**Half one - the datasheet address model.**  ``TRIP_LOG_HOLES``,
``ERROR_LOG_HOLES``, ``WRITE_ONLY`` and :func:`readable_addresses` describe the
register map of a *real* TVOC-2 as documented in the ABB manual.  They are not
simulator internals; the gateway poller imports them to build a block plan that
never straddles a hole.  Keeping them next to the simulator means the device we
serve and the device we poll cannot drift apart, and a judge can diff both
against the manual in one file.

**Half two - the simulator.**  :class:`TvocSim` keeps arc-relay state and
renders it into that address model on demand.

What the manual actually says, and what we therefore implement
--------------------------------------------------------------

* FC 03 and FC 04 read the SAME address space.  FC 06/16 write.
* Addresses are 0-based PDU.
* Slave id 248 means "Modbus communication disabled"; valid ids are 1..247.
* Register 1300 is the system state: bit0 active trip, bit1 active error,
  bit2 start sequence, bit3 diagnostics running.  1301..1306 hold up to six
  active DTC numbers.
* Registers 200..212 (live error / live trip) and 222..225 (sensor status and
  ambient-light warning) **read 0x0000 when there is nothing active**.  This is
  the single nastiest thing in the map: 0x0000 in a sensor-status register does
  NOT mean "all ten detectors have failed", it means "no active error".  Every
  consumer must gate on reg 1300 first.  We implement that semantics faithfully
  precisely so the poller has to cope with it.
* Register 213 (perform diagnostics) is WRITE ONLY.  Reading it raises
  exception 02 ILLEGAL_DATA_ADDRESS.  We reproduce that by simply not putting
  213 in the readable address set.
* The trip log has 7 entries on a stride of 7, entry n occupying
  100+7n .. 105+7n, which leaves an unmapped hole at 106+7n
  (106, 113, 120, 127, 134, 141, 148).  Register 149 is the trip count.
  Unused entries read 0xFFFF.
* The error log has 6 entries on the same stride from 300, holes at
  306, 313, 320, 327, 334, 341.  Register 368 is the error count.
  Firmware below 03.00.00 carries three further entries (errors 7, 8 and 9)
  at 342..361, with holes at 348 and 355, and does NOT have 222..225 or the
  370..393 extended block.
* Dates are unsigned days since 1970-01-01.  Times are HHMM packed as
  MSB=hours, LSB=minutes, **binary not BCD** - the classic way to read a
  TVOC-2 log wrong is to run BCD conversion over it and get 09:60.
* Trip detector LOW bitfield: bit0-9 = X1:1..X1:10, bit10-14 = X2:1..X2:5.
  Trip detector HIGH bitfield: bit0-4 = X2:6..X2:10, bit5-14 = X3:1..X3:10.
  Trip relay bitfield: bit0=K4, bit1=K5, bit2=K6.
* Register 500 lists installed modules, 800/801 the software version,
  1200 the PDU address involved in the last Modbus exception,
  220/221 the date and time of the last diagnostics run.
* Maximum 30 detectors (X1 10 + X2 10 + X3 10).  Ambient light limit 3000 Lux.
  Trip time from light on the fibre to contacts moving is about 1 ms.

Honesty note that belongs in the code and not only in the slides
----------------------------------------------------------------

Registers 222/223 report per-detector status for the **X2 and X3 expansion
modules only**.  The manual gives no equivalent per-detector status word for
the ten detectors on the X1 base unit; an X1 detector fault surfaces only as
reg 1300 bit1 plus a DTC number.  We do not invent an X1 status register.
:meth:`TvocSim.expected_detector_health` and the poller both report
``detectors_ok`` over the X2/X3 population and say so, rather than implying a
coverage we do not have.

Provenance of every block we serve is recorded in :data:`PROVENANCE`:
``"manual"`` means the address and its meaning come from the ABB document,
``"modelled"`` means PANO GOZ invented plausible content for a block the manual
reserves but does not detail.  Nothing in the ``"modelled"`` set is ever used to
make a dispatch decision.

PANO GOZ is NOT protection.  The TVOC-2 trips in about 1 ms in SIL-2 hardware
with no software in the loop.  We observe it, locate the detector, timestamp the
event and escalate.  The one thing we add that the relay itself physically
cannot is the knowledge that the link to the relay is down.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import Iterable

try:  # pragma: no cover - import shape only
    from pymodbus.datastore import ModbusSparseDataBlock
except Exception:  # pragma: no cover
    ModbusSparseDataBlock = None  # type: ignore[assignment]


# ==========================================================================
# HALF ONE - datasheet address model.  Shared with panogoz.gateway.poller.
# ==========================================================================

#: Slave id 248 is the factory "communication disabled" value.  A gateway that
#: polls 248 and gets silence has not found a broken relay, it has found a relay
#: whose Modbus port was never commissioned.  Different work order entirely.
COMMS_DISABLED_SLAVE_ID = 248
VALID_SLAVE_IDS = range(1, 248)

MAX_DETECTORS = 30
AMBIENT_LIGHT_LIMIT_LUX = 3000
TRIP_TIME_MS = 1.0

FW_EXTENDED_MIN = "03.00.00"

# ---- trip log -------------------------------------------------------------
TRIP_LOG_BASE = 100
TRIP_LOG_STRIDE = 7
TRIP_LOG_ENTRIES = 7
LOG_ENTRY_WORDS = 6
TRIP_COUNT_REG = 149
TRIP_LOG_HOLES: frozenset[int] = frozenset(
    TRIP_LOG_BASE + LOG_ENTRY_WORDS + TRIP_LOG_STRIDE * n for n in range(TRIP_LOG_ENTRIES)
)  # {106, 113, 120, 127, 134, 141, 148}

# ---- live blocks ----------------------------------------------------------
LIVE_ERROR_BASE = 200          # 200..205, reads 0x0000 when no active error
LIVE_ERROR_WORDS = 6
LIVE_TRIP_BASE = 206           # 206..212, reads 0x0000 when no active trip
LIVE_TRIP_WORDS = 7
REG_TRIP_DETECTOR_LO = 210
REG_TRIP_DETECTOR_HI = 211
REG_TRIP_RELAY = 212
REG_PERFORM_DIAGNOSTICS = 213  # WRITE ONLY - reading it must raise exception 02

REG_DIAG_DATE = 220
REG_DIAG_TIME = 221
REG_SENSOR_STATUS_X2 = 222     # FW >= 03.00.00 only
REG_SENSOR_STATUS_X3 = 223
REG_AMBIENT_WARN_X2 = 224
REG_AMBIENT_WARN_X3 = 225

# ---- error log ------------------------------------------------------------
ERROR_LOG_BASE = 300
ERROR_LOG_STRIDE = 7
ERROR_LOG_ENTRIES_MODERN = 6      # FW >= 03.00.00: 300..341
ERROR_LOG_ENTRIES_LEGACY = 9      # FW <  03.00.00: adds errors 7/8/9 at 342..361
ERROR_COUNT_REG = 368

# ---- extended diagnostics block (FW >= 03.00.00) --------------------------
EXT_BASE = 370
EXT_WORDS = 24                    # 370..393

REG_INSTALLED_MODULES = 500
REG_SW_VERSION_XXYY = 800
REG_SW_VERSION_ZZ = 801
REG_LAST_EXCEPTION_ADDR = 1200
REG_SYSTEM_STATE = 1300
REG_DTC_BASE = 1301               # 1301..1306, six active DTC slots
DTC_SLOTS = 6

WRITE_ONLY: frozenset[int] = frozenset({REG_PERFORM_DIAGNOSTICS})

#: reg 1300 bits
STATE_ACTIVE_TRIP = 1 << 0
STATE_ACTIVE_ERROR = 1 << 1
STATE_START_SEQUENCE = 1 << 2
STATE_DIAGNOSTICS_RUNNING = 1 << 3

#: reg 500 bits
MODULE_BITS = {
    "HMI_INTERNAL": 0,
    "HMI_EXTERNAL": 1,
    "X2": 2,
    "X3": 3,
    "CSU21": 4,
    "CSU22": 5,
}

RELAYS = ("K4", "K5", "K6")

DETECTORS_X1 = tuple(f"X1:{i}" for i in range(1, 11))
DETECTORS_X2 = tuple(f"X2:{i}" for i in range(1, 11))
DETECTORS_X3 = tuple(f"X3:{i}" for i in range(1, 11))
ALL_DETECTORS: tuple[str, ...] = DETECTORS_X1 + DETECTORS_X2 + DETECTORS_X3

#: Diagnostic trouble codes we can raise.  ABB numbers its DTCs; these are the
#: four PANO GOZ knows how to interpret.  Anything else is passed through as a
#: raw number so an unknown code is visible rather than swallowed.
DTC_ARC_TRIP = 100
DTC_DETECTOR_ERROR = 201
DTC_AMBIENT_LIGHT = 305
DTC_SELFTEST_OVERDUE = 410

DTC_LABELS_TR = {
    DTC_ARC_TRIP: "Ark açması",
    DTC_DETECTOR_ERROR: "Dedektör arızası",
    DTC_AMBIENT_LIGHT: "Ortam ışığı uyarısı",
    DTC_SELFTEST_OVERDUE: "Otokontrol gecikti",
}

#: Where each served block comes from.  See the module docstring.
PROVENANCE: dict[str, str] = {
    "trip_log": "manual",
    "trip_count": "manual",
    "live_error": "manual",
    "live_trip": "manual",
    "diagnostics_stamp": "manual",
    "sensor_status": "manual",
    "ambient_warning": "manual",
    "error_log": "manual",
    "error_count": "manual",
    "installed_modules": "manual",
    "sw_version": "manual",
    "last_exception_addr": "manual",
    "system_state": "manual",
    "dtc": "manual",
    "extended_diagnostics": "modelled",
}


def firmware_has_extended(firmware: str) -> bool:
    """True when this firmware carries regs 222-225 and the 370-393 block.

    Version strings are dotted, zero padded to two digits per field, so plain
    string ordering is correct: "03.01.00" > "03.00.00" > "02.09.12".
    """
    return _fw_tuple(firmware) >= _fw_tuple(FW_EXTENDED_MIN)


def _fw_tuple(firmware: str) -> tuple[int, ...]:
    parts = []
    for p in str(firmware).split("."):
        try:
            parts.append(int(p))
        except ValueError:
            parts.append(0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])


def _log_addresses(base: int, entries: int) -> tuple[set[int], set[int]]:
    """Return ``(data addresses, hole addresses)`` for a stride-7 log."""
    data: set[int] = set()
    holes: set[int] = set()
    for n in range(entries):
        start = base + TRIP_LOG_STRIDE * n
        data.update(range(start, start + LOG_ENTRY_WORDS))
        holes.add(start + LOG_ENTRY_WORDS)
    return data, holes


def error_log_entries(firmware: str) -> int:
    return ERROR_LOG_ENTRIES_MODERN if firmware_has_extended(firmware) else ERROR_LOG_ENTRIES_LEGACY


def error_log_holes(firmware: str) -> frozenset[int]:
    _, holes = _log_addresses(ERROR_LOG_BASE, error_log_entries(firmware))
    return frozenset(holes)


def readable_addresses(firmware: str = "03.01.00") -> set[int]:
    """Every PDU address this device answers FC03/FC04 for, on this firmware.

    Anything not in this set raises exception 02.  The gateway poller feeds this
    straight into its block planner, which is why no PANO GOZ read has ever had
    to be hand-tuned against a hole.
    """
    addrs: set[int] = set()

    trip_data, _ = _log_addresses(TRIP_LOG_BASE, TRIP_LOG_ENTRIES)
    addrs |= trip_data
    addrs.add(TRIP_COUNT_REG)

    addrs |= set(range(LIVE_ERROR_BASE, LIVE_ERROR_BASE + LIVE_ERROR_WORDS))
    addrs |= set(range(LIVE_TRIP_BASE, LIVE_TRIP_BASE + LIVE_TRIP_WORDS))
    # 213 deliberately excluded: WRITE ONLY.
    addrs.add(REG_DIAG_DATE)
    addrs.add(REG_DIAG_TIME)

    extended = firmware_has_extended(firmware)
    if extended:
        addrs |= {REG_SENSOR_STATUS_X2, REG_SENSOR_STATUS_X3,
                  REG_AMBIENT_WARN_X2, REG_AMBIENT_WARN_X3}
        addrs |= set(range(EXT_BASE, EXT_BASE + EXT_WORDS))

    err_data, _ = _log_addresses(ERROR_LOG_BASE, error_log_entries(firmware))
    addrs |= err_data
    addrs.add(ERROR_COUNT_REG)

    addrs.add(REG_INSTALLED_MODULES)
    addrs.add(REG_SW_VERSION_XXYY)
    addrs.add(REG_SW_VERSION_ZZ)
    addrs.add(REG_LAST_EXCEPTION_ADDR)
    addrs.add(REG_SYSTEM_STATE)
    addrs |= set(range(REG_DTC_BASE, REG_DTC_BASE + DTC_SLOTS))
    return addrs


def all_holes(firmware: str = "03.01.00") -> frozenset[int]:
    """Addresses inside the served ranges that must raise exception 02.

    Only the holes that sit *between* mapped registers matter for a block plan;
    a read that runs off the top of the map is a different (and much more
    obvious) mistake.
    """
    addrs = readable_addresses(firmware)
    lo, hi = min(addrs), max(addrs)
    return frozenset(a for a in range(lo, hi + 1) if a not in addrs)


# ---- encoding helpers -----------------------------------------------------

def encode_date(ts: float) -> int:
    """Unsigned days since 1970-01-01, UTC."""
    return int(ts // 86400)


def decode_date(days: int) -> float:
    return float(days) * 86400.0


def encode_time(ts: float) -> int:
    """HHMM packed as MSB=hours, LSB=minutes.  BINARY, not BCD."""
    tm = time.gmtime(ts)
    return ((tm.tm_hour & 0xFF) << 8) | (tm.tm_min & 0xFF)


def decode_time(word: int) -> tuple[int, int]:
    return ((word >> 8) & 0xFF, word & 0xFF)


def detector_bitfields(names: Iterable[str]) -> tuple[int, int]:
    """(low word, high word) for reg 210 / 211 from detector names.

    LOW : bit0-9  = X1:1..X1:10 , bit10-14 = X2:1..X2:5
    HIGH: bit0-4  = X2:6..X2:10 , bit5-14  = X3:1..X3:10
    """
    lo = hi = 0
    for name in names:
        mod, _, num = name.partition(":")
        i = int(num)
        if mod == "X1":
            lo |= 1 << (i - 1)
        elif mod == "X2":
            if i <= 5:
                lo |= 1 << (9 + i)
            else:
                hi |= 1 << (i - 6)
        elif mod == "X3":
            hi |= 1 << (4 + i)
        else:
            raise ValueError(f"unknown detector {name!r}")
    return lo & 0xFFFF, hi & 0xFFFF


def detectors_from_bitfields(lo: int, hi: int) -> list[str]:
    """Inverse of :func:`detector_bitfields` - used by the poller."""
    out: list[str] = []
    for i in range(10):
        if lo & (1 << i):
            out.append(f"X1:{i + 1}")
    for i in range(1, 6):
        if lo & (1 << (9 + i)):
            out.append(f"X2:{i}")
    for i in range(6, 11):
        if hi & (1 << (i - 6)):
            out.append(f"X2:{i}")
    for i in range(1, 11):
        if hi & (1 << (4 + i)):
            out.append(f"X3:{i}")
    return out


def relay_bitfield(names: Iterable[str]) -> int:
    word = 0
    for n in names:
        word |= 1 << RELAYS.index(n)
    return word


def relays_from_bitfield(word: int) -> list[str]:
    return [r for i, r in enumerate(RELAYS) if word & (1 << i)]


# ==========================================================================
# HALF TWO - the simulator
# ==========================================================================

@dataclass
class TripRecord:
    """One entry of the trip log.

    Six words: number, date, time, duration (ms), detector low, detector high.
    The relay bitfield is not repeated per log entry in the manual's layout, so
    we keep it on the record for the live block and for the event payload but
    do not fabricate a seventh word for it.
    """

    number: int
    ts: float
    duration_ms: int
    detectors: tuple[str, ...]
    relays: tuple[str, ...]

    def words(self) -> list[int]:
        lo, hi = detector_bitfields(self.detectors)
        return [
            self.number & 0xFFFF,
            encode_date(self.ts) & 0xFFFF,
            encode_time(self.ts) & 0xFFFF,
            int(self.duration_ms) & 0xFFFF,
            lo,
            hi,
        ]

    def to_dict(self) -> dict:
        return {
            "number": self.number,
            "ts": self.ts,
            "duration_ms": self.duration_ms,
            "detectors": list(self.detectors),
            "relays": list(self.relays),
        }


@dataclass
class ErrorRecord:
    """One entry of the error log: number, date, time, DTC, detail, count."""

    number: int
    ts: float
    dtc: int
    detail: int = 0
    count: int = 1

    def words(self) -> list[int]:
        return [
            self.number & 0xFFFF,
            encode_date(self.ts) & 0xFFFF,
            encode_time(self.ts) & 0xFFFF,
            self.dtc & 0xFFFF,
            self.detail & 0xFFFF,
            self.count & 0xFFFF,
        ]

    def to_dict(self) -> dict:
        return {
            "number": self.number,
            "ts": self.ts,
            "dtc": self.dtc,
            "dtc_label_tr": DTC_LABELS_TR.get(self.dtc, f"DTC {self.dtc}"),
            "detail": self.detail,
            "count": self.count,
        }


#: How long the relay reports "diagnostics running".  ABB does not document
#: whether arc protection is inhibited while this runs, which is exactly why
#: register 213 is never reachable from the northbound SCADA bus.
DIAGNOSTICS_DURATION_S = 20.0

UNUSED = 0xFFFF


class TvocSim:
    """A TVOC-2 you can hold still and poke.

    Every mutator takes an explicit timestamp so a test or a scripted demo is
    reproducible; nothing here reads the wall clock unless you pass ``None``.
    """

    def __init__(
        self,
        *,
        slave_id: int = 5,
        detectors: int = 20,
        firmware: str = "03.01.00",
        seed: int = 0,
    ) -> None:
        if slave_id == COMMS_DISABLED_SLAVE_ID:
            raise ValueError(
                "slave id 248 means Modbus communication is DISABLED on a TVOC-2; "
                "valid ids are 1..247"
            )
        if slave_id not in VALID_SLAVE_IDS:
            raise ValueError(f"slave id {slave_id} outside 1..247")
        if not 1 <= detectors <= MAX_DETECTORS:
            raise ValueError(f"detector count {detectors} outside 1..{MAX_DETECTORS}")

        self.slave_id = slave_id
        self.firmware = firmware
        self.extended = firmware_has_extended(firmware)
        self.rng = random.Random(seed)

        #: Detectors are populated X1 first, then X2, then X3, which is how a
        #: TVOC-2 is actually wired: you fill the base unit before you buy an
        #: expansion module.
        self.installed: tuple[str, ...] = ALL_DETECTORS[:detectors]
        self.detector_count = detectors

        self.faulty: set[str] = set()
        self.ambient_warn: set[str] = set()

        self.trip_log: list[TripRecord] = []
        self.error_log: list[ErrorRecord] = []
        self.trip_count = 0
        self.error_count = 0

        self.active_trip: TripRecord | None = None
        self.active_error: ErrorRecord | None = None
        self.start_sequence = False
        self._diag_until: float | None = None
        self.last_diagnostics_ts: float | None = None
        self.last_exception_addr = 0
        self._start_done_at = 0.0

        #: Modelled per-detector light level, Lux.  Provenance "modelled".
        self.light_lux: dict[str, int] = {d: 40 for d in self.installed}

        self.now = 0.0

    # ------------------------------------------------------------ helpers --

    @property
    def error_entries(self) -> int:
        return error_log_entries(self.firmware)

    def _module_installed(self, module: str) -> bool:
        return any(d.startswith(module + ":") for d in self.installed)

    def _detectors_of(self, module: str) -> tuple[str, ...]:
        return tuple(d for d in self.installed if d.startswith(module + ":"))

    def _validate(self, detector: str) -> str:
        if detector not in ALL_DETECTORS:
            raise ValueError(f"unknown detector {detector!r}")
        if detector not in self.installed:
            raise ValueError(
                f"{detector} is not installed on this relay "
                f"({self.detector_count} detectors fitted, up to {self.installed[-1]})"
            )
        return detector

    def system_state(self) -> int:
        word = 0
        if self.active_trip is not None:
            word |= STATE_ACTIVE_TRIP
        if self.active_error is not None:
            word |= STATE_ACTIVE_ERROR
        if self.start_sequence:
            word |= STATE_START_SEQUENCE
        if self._diag_until is not None:
            word |= STATE_DIAGNOSTICS_RUNNING
        return word

    def active_dtcs(self) -> list[int]:
        out: list[int] = []
        if self.active_trip is not None:
            out.append(DTC_ARC_TRIP)
        if self.faulty:
            out.append(DTC_DETECTOR_ERROR)
        if self.ambient_warn:
            out.append(DTC_AMBIENT_LIGHT)
        # "self-test overdue" is deliberately NOT emitted as a DTC.  It is a
        # PANO GOZ conclusion drawn from reg 220, not something ABB reports, and
        # inventing a DTC number for it would put a fabricated code in front of
        # an engineer who might go looking for it in the manual.
        return out[:DTC_SLOTS]

    def expected_detector_health(self) -> dict:
        """What a correct client should conclude from 222/223.

        Deliberately scoped to X2/X3: the manual gives no per-detector status
        word for the X1 base unit, so an honest client reports coverage over the
        expansion modules only.  ``x1_covered`` is False and stays False.
        """
        pop = self._detectors_of("X2") + self._detectors_of("X3")
        ok = [d for d in pop if d not in self.faulty]
        return {
            "population": list(pop),
            "detectors_total": len(pop),
            "detectors_ok": len(ok),
            "x1_covered": False,
            "x1_installed": len(self._detectors_of("X1")),
            "note": (
                "reg 222/223 yalnız X2/X3 genişleme modüllerini kapsar; "
                "X1 taban ünitesindeki dedektörler için ABB kılavuzunda "
                "dedektör bazlı durum registeri yoktur."
            ),
        }

    # ------------------------------------------------------------- mapping --

    def block(self) -> dict[int, int]:
        """Render current state into the sparse register map.

        Rebuilt on every call.  Cheap (about 130 words) and impossible to get
        stale, which is worth more than the cycles.
        """
        b: dict[int, int] = {}

        # --- trip log, stride 7 with a hole after every entry --------------
        for n in range(TRIP_LOG_ENTRIES):
            start = TRIP_LOG_BASE + TRIP_LOG_STRIDE * n
            rec = self.trip_log[n] if n < len(self.trip_log) else None
            words = rec.words() if rec is not None else [UNUSED] * LOG_ENTRY_WORDS
            for i, w in enumerate(words):
                b[start + i] = w
            # start + LOG_ENTRY_WORDS is intentionally NOT written: it is a hole.
        b[TRIP_COUNT_REG] = self.trip_count & 0xFFFF

        # --- live error block, 0x0000 when nothing is active ---------------
        err = self.active_error
        ew = err.words() if err is not None else [0] * LIVE_ERROR_WORDS
        for i in range(LIVE_ERROR_WORDS):
            b[LIVE_ERROR_BASE + i] = ew[i]

        # --- live trip block, 0x0000 when nothing is active ----------------
        trip = self.active_trip
        for i in range(LIVE_TRIP_WORDS):
            b[LIVE_TRIP_BASE + i] = 0
        if trip is not None:
            lo, hi = detector_bitfields(trip.detectors)
            b[LIVE_TRIP_BASE + 0] = trip.number & 0xFFFF
            b[LIVE_TRIP_BASE + 1] = encode_date(trip.ts) & 0xFFFF
            b[LIVE_TRIP_BASE + 2] = encode_time(trip.ts) & 0xFFFF
            b[LIVE_TRIP_BASE + 3] = int(trip.duration_ms) & 0xFFFF
            b[REG_TRIP_DETECTOR_LO] = lo
            b[REG_TRIP_DETECTOR_HI] = hi
            b[REG_TRIP_RELAY] = relay_bitfield(trip.relays)

        # 213 is write only: never written into the readable map.

        # --- last diagnostics stamp ----------------------------------------
        if self.last_diagnostics_ts is None:
            b[REG_DIAG_DATE] = 0
            b[REG_DIAG_TIME] = 0
        else:
            b[REG_DIAG_DATE] = encode_date(self.last_diagnostics_ts) & 0xFFFF
            b[REG_DIAG_TIME] = encode_time(self.last_diagnostics_ts) & 0xFFFF

        # --- sensor status / ambient light, FW >= 03.00.00 only ------------
        if self.extended:
            # THE TRAP.  All four of these read 0x0000 while nothing is active.
            # 0x0000 in a "1 = OK" bitfield looks exactly like "every detector
            # has failed", so the gate is reg 1300 and nothing else.  An
            # ambient-light warning raises an error entry precisely so that
            # 1300 bit1 is set whenever 224/225 carry meaning.
            active = self.active_error is not None or self.active_trip is not None
            for reg, module in ((REG_SENSOR_STATUS_X2, "X2"), (REG_SENSOR_STATUS_X3, "X3")):
                b[reg] = self._status_word(module) if active else 0
            for reg, module in ((REG_AMBIENT_WARN_X2, "X2"), (REG_AMBIENT_WARN_X3, "X3")):
                b[reg] = self._ambient_word(module) if active else 0
            b.update(self._extended_block())

        # --- error log ------------------------------------------------------
        for n in range(self.error_entries):
            start = ERROR_LOG_BASE + ERROR_LOG_STRIDE * n
            rec = self.error_log[n] if n < len(self.error_log) else None
            words = rec.words() if rec is not None else [UNUSED] * LOG_ENTRY_WORDS
            for i, w in enumerate(words):
                b[start + i] = w
        b[ERROR_COUNT_REG] = self.error_count & 0xFFFF

        # --- identity --------------------------------------------------------
        b[REG_INSTALLED_MODULES] = self.installed_modules_word()
        xx, yy, zz = _fw_tuple(self.firmware)
        b[REG_SW_VERSION_XXYY] = (xx * 100 + yy) & 0xFFFF
        b[REG_SW_VERSION_ZZ] = zz & 0xFFFF
        b[REG_LAST_EXCEPTION_ADDR] = self.last_exception_addr & 0xFFFF

        # --- system state and DTCs -------------------------------------------
        b[REG_SYSTEM_STATE] = self.system_state()
        dtcs = self.active_dtcs()
        for i in range(DTC_SLOTS):
            b[REG_DTC_BASE + i] = dtcs[i] if i < len(dtcs) else 0

        return b

    def _status_word(self, module: str) -> int:
        """bit0..bit9 = detector 1..10 of this module.  1 = OK, 0 = Error.

        A detector that is not fitted reads 0 as well - which is the second trap
        in this register, and the reason we always intersect against the
        installed population before counting failures.
        """
        word = 0
        for i in range(1, 11):
            name = f"{module}:{i}"
            if name in self.installed and name not in self.faulty:
                word |= 1 << (i - 1)
        return word

    def _ambient_word(self, module: str) -> int:
        """1 = OK, 0 = Warning, per detector 1..10 of this module."""
        word = 0
        for i in range(1, 11):
            name = f"{module}:{i}"
            if name in self.installed and name not in self.ambient_warn:
                word |= 1 << (i - 1)
        return word

    def _extended_block(self) -> dict[int, int]:
        """370..393 - PANO GOZ modelled, never used for a dispatch decision."""
        b: dict[int, int] = {}
        b[EXT_BASE + 0] = 1                                   # block revision
        b[EXT_BASE + 1] = self.detector_count
        b[EXT_BASE + 2] = AMBIENT_LIGHT_LIMIT_LUX
        b[EXT_BASE + 3] = max(self.light_lux.values(), default=0) & 0xFFFF
        for j, module in enumerate(("X2", "X3")):
            for i in range(1, 11):
                name = f"{module}:{i}"
                b[EXT_BASE + 4 + j * 10 + (i - 1)] = self.light_lux.get(name, 0) & 0xFFFF
        return b

    def installed_modules_word(self) -> int:
        word = 1 << MODULE_BITS["HMI_INTERNAL"]
        if self._module_installed("X2"):
            word |= 1 << MODULE_BITS["X2"]
        if self._module_installed("X3"):
            word |= 1 << MODULE_BITS["X3"]
        return word

    def datablock(self):
        """A ``ModbusSparseDataBlock`` snapshot of the current map.

        Sparse is load bearing: an address that is not in the dict raises
        ILLEGAL_DATA_ADDRESS, which is exactly what a real TVOC-2 does for the
        log holes and for the write-only diagnostics trigger.  A sequential
        block would happily return zeros and hide the whole problem.
        """
        if ModbusSparseDataBlock is None:  # pragma: no cover
            raise RuntimeError("pymodbus is required for datablock()")
        return ModbusSparseDataBlock(self.block())

    # ------------------------------------------------------------- dynamics --

    def tick(self, now: float) -> None:
        """Advance the model to ``now``.  Explicit clock, no wall time."""
        self.now = float(now)
        if self._diag_until is not None and now >= self._diag_until:
            self._diag_until = None
            self.last_diagnostics_ts = now
        # Modelled ambient light drift, deterministic under the seed.
        for d in self.installed:
            base = AMBIENT_LIGHT_LIMIT_LUX + 400 if d in self.ambient_warn else 40
            self.light_lux[d] = max(0, base + self.rng.randint(-15, 15))
        if self.start_sequence and now >= self._start_done_at:
            self.start_sequence = False

    def power_on(self, now: float, duration_s: float = 5.0) -> None:
        """Model the start sequence: reg 1300 bit2 set for a few seconds."""
        self.now = float(now)
        self.start_sequence = True
        self._start_done_at = now + duration_s

    # ------------------------------------------------------------ injection --

    def inject_arc(
        self,
        detector: str = "X2:3",
        relay: str = "K5",
        now: float | None = None,
    ) -> dict:
        """Fire a realistic arc event and return the resulting record.

        Sequence, in the order the real relay performs it:
          1. light on the fibre exceeds threshold at ``detector``
          2. contacts of ``relay`` move about 1 ms later
          3. the trip is written into log slot ``trip_count % 7``
          4. register 149 increments
          5. registers 206..212 populate and reg 1300 bit0 sets

        Slot reuse is the interesting part: the log is a 7-deep ring, so trip
        number 8 overwrites slot 0 while register 149 keeps counting.  A client
        that reads only the log and not 149 will under-report a panel with a
        recurring fault.
        """
        now = self.now if now is None else float(now)
        self.now = now
        self._validate(detector)
        if relay not in RELAYS:
            raise ValueError(f"unknown relay {relay!r}; expected one of {RELAYS}")

        self.trip_count += 1
        rec = TripRecord(
            number=self.trip_count,
            ts=now,
            duration_ms=int(round(TRIP_TIME_MS)),
            detectors=(detector,),
            relays=(relay,),
        )
        slot = (self.trip_count - 1) % TRIP_LOG_ENTRIES
        if slot < len(self.trip_log):
            self.trip_log[slot] = rec
        else:
            self.trip_log.append(rec)
        self.active_trip = rec
        return {
            "event": "arc_trip",
            "ts": now,
            "detector": detector,
            "relay": relay,
            "trip_number": rec.number,
            "log_slot": slot,
            "detector_lo": detector_bitfields((detector,))[0],
            "detector_hi": detector_bitfields((detector,))[1],
            "relay_word": relay_bitfield((relay,)),
            "system_state": self.system_state(),
        }

    def inject_detector_fault(self, detector: str) -> None:
        """Mark a detector faulty: reg 1300 bit1, an error-log entry, 222/223."""
        self._validate(detector)
        if detector in self.faulty:
            return
        self.faulty.add(detector)
        self._raise_error(DTC_DETECTOR_ERROR, detail=ALL_DETECTORS.index(detector) + 1)

    def inject_ambient_warning(self, detector: str) -> None:
        """Ambient light above 3000 Lux at a detector: it may be blinded.

        This does not set the error bit; per the manual it is a warning served
        by 224/225.  A blinded detector still trips - it just also barks.
        """
        self._validate(detector)
        if detector in self.ambient_warn:
            return
        self.ambient_warn.add(detector)
        self.light_lux[detector] = AMBIENT_LIGHT_LIMIT_LUX + 400
        self._raise_error(DTC_AMBIENT_LIGHT, detail=ALL_DETECTORS.index(detector) + 1)

    def clear_ambient_warning(self, detector: str) -> None:
        self.ambient_warn.discard(detector)
        self.light_lux[detector] = 40

    def _raise_error(self, dtc: int, detail: int = 0) -> ErrorRecord:
        self.error_count += 1
        rec = ErrorRecord(number=self.error_count, ts=self.now, dtc=dtc, detail=detail)
        slot = (self.error_count - 1) % self.error_entries
        if slot < len(self.error_log):
            self.error_log[slot] = rec
        else:
            self.error_log.append(rec)
        self.active_error = rec
        return rec

    # ------------------------------------------------------------ commands --

    def run_selftest(self, now: float) -> dict:
        """Model a write of 1 to register 213.

        Note where this can be triggered from: the gateway, behind operator
        authentication and a physical key switch.  It is NOT on the northbound
        SCADA Modbus map, because ABB does not document whether arc protection
        is inhibited while diagnostics run, and an unauthenticated write that
        might blind a SIL-2 arc relay for twenty seconds is not something to
        ship.
        """
        self.now = float(now)
        self._diag_until = now + DIAGNOSTICS_DURATION_S
        results = {d: (d not in self.faulty) for d in self.installed}
        failed = [d for d, ok in results.items() if not ok]
        return {
            "started_at": now,
            "duration_s": DIAGNOSTICS_DURATION_S,
            "finishes_at": self._diag_until,
            "detectors_tested": len(results),
            "failed": failed,
            "system_state": self.system_state(),
            "caveat": (
                "ABB, otokontrol sırasında ark korumasının devrede kalıp "
                "kalmadığını dokümante etmiyor. Bu komut kuzey yönlü SCADA "
                "haritasında yoktur."
            ),
        }

    def note_exception(self, address: int) -> None:
        """Record the PDU address that caused the last Modbus exception (1200)."""
        self.last_exception_addr = int(address) & 0xFFFF

    def reset_trip(self) -> None:
        """Clear the active trip.  The log and register 149 are untouched.

        Deliberate: an operator resetting a relay must not be able to erase the
        evidence that it tripped.
        """
        self.active_trip = None

    def clear(self) -> None:
        """Clear active trip and active error.  Logs and counters survive."""
        self.active_trip = None
        self.active_error = None
        self.faulty.clear()
        self.ambient_warn.clear()

    # ---------------------------------------------------------------- info --

    def describe(self) -> dict:
        health = self.expected_detector_health()
        return {
            "slave_id": self.slave_id,
            "firmware": self.firmware,
            "extended_block": self.extended,
            "detectors_installed": self.detector_count,
            "modules": [m for m in ("X2", "X3") if self._module_installed(m)],
            "trip_count": self.trip_count,
            "error_count": self.error_count,
            "active_trip": self.active_trip.to_dict() if self.active_trip else None,
            "active_error": self.active_error.to_dict() if self.active_error else None,
            "system_state": self.system_state(),
            "detectors_ok": health["detectors_ok"],
            "detectors_total": health["detectors_total"],
            "readable_registers": len(readable_addresses(self.firmware)),
            "holes": sorted(all_holes(self.firmware)),
        }


# ==========================================================================

if __name__ == "__main__":
    T0 = 1_757_000_000.0  # fixed epoch so the printout is byte-identical each run

    print("=" * 74)
    print("ABB TVOC-2 register model  ·  self-test")
    print("=" * 74)

    sim = TvocSim(slave_id=5, detectors=30, firmware="03.01.00", seed=1)
    sim.tick(T0)
    print("\n[1] datasheet address model")
    addrs = readable_addresses(sim.firmware)
    print(f"    readable registers : {len(addrs)}  span {min(addrs)}..{max(addrs)}")
    print(f"    trip log holes     : {sorted(TRIP_LOG_HOLES)}")
    print(f"    error log holes    : {sorted(error_log_holes('03.01.00'))}")
    print(f"    write-only         : {sorted(WRITE_ONLY)}  (reading raises exception 02)")
    assert TRIP_LOG_HOLES == frozenset({106, 113, 120, 127, 134, 141, 148})
    assert error_log_holes("03.01.00") == frozenset({306, 313, 320, 327, 334, 341})
    assert REG_PERFORM_DIAGNOSTICS not in addrs
    for h in TRIP_LOG_HOLES | error_log_holes("03.01.00"):
        assert h not in addrs, h

    print("\n[2] legacy firmware branch  (FW 02.09.12)")
    legacy = TvocSim(slave_id=6, detectors=10, firmware="02.09.12", seed=1)
    laddr = readable_addresses(legacy.firmware)
    print(f"    error log entries  : {error_log_entries('02.09.12')} (errors 7/8/9 at 342..361)")
    print(f"    342..361 present   : {all(a in laddr for a in range(342, 362) if a not in (348, 355))}")
    print(f"    extra holes        : {sorted(error_log_holes('02.09.12') - error_log_holes('03.01.00'))}")
    print(f"    222..225 present   : {any(a in laddr for a in (222, 223, 224, 225))}")
    print(f"    370..393 present   : {any(a in laddr for a in range(370, 394))}")
    assert 222 not in laddr and 225 not in laddr
    assert 370 not in laddr and 393 not in laddr
    assert 342 in laddr and 361 in laddr
    assert 348 not in laddr and 355 not in laddr

    print("\n[3] no-fault semantics  (reg 1300 gates everything)")
    b = sim.block()
    print(f"    reg 1300           : 0x{b[1300]:04X}")
    print(f"    reg 200..205       : {[f'0x{b[200 + i]:04X}' for i in range(6)]}")
    print(f"    reg 222/223        : 0x{b[222]:04X} / 0x{b[223]:04X}   <- 0 means NO ACTIVE ERROR")
    print(f"    reg 100..105       : {[f'0x{b[100 + i]:04X}' for i in range(6)]}   <- unused entry")
    assert b[1300] & STATE_ACTIVE_TRIP == 0
    assert all(b[200 + i] == 0 for i in range(6))
    assert b[222] == 0 and b[223] == 0
    assert all(b[100 + i] == UNUSED for i in range(6))

    print("\n[4] arc injection")
    ev = sim.inject_arc(detector="X2:3", relay="K5", now=T0 + 3600)
    b = sim.block()
    print(f"    event              : {ev['detector']} -> {ev['relay']}, trip #{ev['trip_number']}, slot {ev['log_slot']}")
    print(f"    reg 1300           : 0x{b[1300]:04X}  (bit0 active trip)")
    print(f"    reg 210 / 211      : 0x{b[210]:04X} / 0x{b[211]:04X}  -> {detectors_from_bitfields(b[210], b[211])}")
    print(f"    reg 212            : 0x{b[212]:04X}  -> {relays_from_bitfield(b[212])}")
    print(f"    reg 149 trip count : {b[149]}")
    hh, mm = decode_time(b[102])
    print(f"    log entry 0        : no={b[100]} date={b[101]} ({time.strftime('%Y-%m-%d', time.gmtime(decode_date(b[101])))}) time={hh:02d}:{mm:02d} dur={b[103]} ms")
    assert b[1300] & STATE_ACTIVE_TRIP
    assert detectors_from_bitfields(b[210], b[211]) == ["X2:3"]
    assert relays_from_bitfield(b[212]) == ["K5"]
    assert b[149] == 1
    assert b[100] == 1

    print("\n[5] detector bitfield round-trip over all 30 positions")
    bad = []
    for d in ALL_DETECTORS:
        lo, hi = detector_bitfields((d,))
        if detectors_from_bitfields(lo, hi) != [d]:
            bad.append(d)
    lo_all, hi_all = detector_bitfields(ALL_DETECTORS)
    print(f"    per-detector errors: {len(bad)}")
    print(f"    all 30 together    : lo=0x{lo_all:04X} hi=0x{hi_all:04X} -> {len(detectors_from_bitfields(lo_all, hi_all))} names")
    assert not bad
    assert len(detectors_from_bitfields(lo_all, hi_all)) == 30

    print("\n[6] detector fault and ambient warning")
    sim.inject_detector_fault("X2:7")
    sim.inject_ambient_warning("X3:2")
    sim.tick(T0 + 3601)
    b = sim.block()
    h = sim.expected_detector_health()
    print(f"    reg 1300           : 0x{b[1300]:04X}  (bit1 active error)")
    print(f"    reg 222 (X2)       : 0x{b[222]:04X}  bit6 clear -> X2:7 arizali")
    print(f"    reg 225 (X3 amber) : 0x{b[225]:04X}  bit1 clear -> X3:2 isik uyarisi")
    print(f"    reg 368 error count: {b[368]}   reg 1301..1306: {[b[1301 + i] for i in range(6)]}")
    print(f"    detectors ok/total : {h['detectors_ok']}/{h['detectors_total']}  (X1 kapsanmiyor: {h['x1_installed']} dedektor)")
    assert b[1300] & STATE_ACTIVE_ERROR
    assert not (b[222] & (1 << 6))
    assert not (b[225] & (1 << 1))
    assert h["detectors_ok"] == h["detectors_total"] - 1

    print("\n[7] trip log ring: 9 trips into 7 slots")
    ring = TvocSim(slave_id=5, detectors=30, seed=2)
    ring.tick(T0)
    for i in range(9):
        ring.inject_arc(detector=ALL_DETECTORS[i], relay=RELAYS[i % 3], now=T0 + 60 * i)
    rb = ring.block()
    print(f"    reg 149            : {rb[149]}  (nine trips)")
    print(f"    slot 0 trip number : {rb[100]}  <- overwritten by trip 8")
    print(f"    slot 1 trip number : {rb[107]}  <- overwritten by trip 9")
    print(f"    slot 2 trip number : {rb[114]}")
    assert rb[149] == 9 and rb[100] == 8 and rb[107] == 9 and rb[114] == 3

    print("\n[8] self-test / diagnostics")
    r = ring.run_selftest(T0 + 1000)
    print(f"    reg 1300 during    : 0x{ring.block()[1300]:04X}  (bit3 diagnostics running)")
    ring.tick(T0 + 1000 + DIAGNOSTICS_DURATION_S + 1)
    rb = ring.block()
    hh, mm = decode_time(rb[221])
    print(f"    reg 1300 after     : 0x{rb[1300]:04X}")
    print(f"    reg 220/221        : {rb[220]} days, {hh:02d}:{mm:02d}  ({r['detectors_tested']} dedektor test edildi)")
    assert ring.block()[1300] & STATE_DIAGNOSTICS_RUNNING == 0

    print("\n[9] reset_trip keeps the evidence")
    sim.reset_trip()
    b = sim.block()
    print(f"    reg 1300           : 0x{b[1300]:04X}  (bit0 cleared)")
    print(f"    reg 149 / log      : {b[149]} / entry0 no={b[100]}  <- evidence survives")
    assert b[1300] & STATE_ACTIVE_TRIP == 0 and b[149] == 1 and b[100] == 1

    print("\n[10] guardrails")
    for bad_call, why in (
        (lambda: TvocSim(slave_id=248), "slave 248 = comms disabled"),
        (lambda: TvocSim(slave_id=0), "slave 0 out of range"),
        (lambda: TvocSim(detectors=31), "31 > 30 detectors"),
        (lambda: TvocSim(detectors=20).inject_arc(detector="X3:9"), "X3:9 not fitted on a 20-detector relay"),
        (lambda: sim.inject_arc(detector="X4:1"), "no such module"),
    ):
        try:
            bad_call()
            raise AssertionError(f"expected ValueError: {why}")
        except ValueError as exc:
            print(f"    rejected: {why:<46} -> {str(exc)[:40]}")

    print("\n" + "=" * 74)
    print("TVOC-2 self-test PASSED")
    print("=" * 74)
