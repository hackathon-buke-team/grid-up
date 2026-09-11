"""Entes MPR-53CS energy analyser - Modbus RTU device model and simulator.

Like :mod:`panogoz.sim.tvoc` this module is half datasheet, half simulator.  The
tables :data:`MEASUREMENT_REGS`, :data:`SETTING_REGS` and the helpers around
them describe a real MPR-53CS; the gateway poller imports them so there is one
decode table, not two that can disagree.

The one fact that decides the whole map
---------------------------------------

**Every numeric measurement register is 32 bits, i.e. two Modbus registers.**
That is not an assumption, it is forced by the address list: every measurement
address steps by 2 - 0, 2, 4, 6 ... 82 - and the only two addresses that step by
1 are 84 and 85, the digital output and digital input status words, which are
genuinely 16 bit.  A map where some measurements were 16 bit and some 32 bit
could not produce that pattern.

Address plan (0-based PDU)::

     0  V_L1        2  V_L2        4  V_L3        6  I_L1
     8  I_L2       10  I_L3       12  I_N
    14  V_L12      16  V_L23      18  V_L31
    20/22/24  P per phase         26/28/30  Q per phase
    32/34/36  S per phase         38/40/42  cos phi per phase
    44  P import total            46  P export total
    48  Q inductive total         50  Q capacitive total     52  S total
    54  avg inductive cos phi     56  avg capacitive cos phi
    58  FREQUENCY
    60/62/64  voltage angles      66/68/70  current angles
    72/74/76  voltage THD         78/80/82  current THD
    84  digital output status (16 bit)   85  digital input status (16 bit)
    86..117   energy counters, 64 bit = four registers each, eight counters
    118..173  minimum block, 28 quantities mirroring addresses 0..54
    174..265  maximum and demand block, 46 quantities

Scaling, and the asymmetry that is the point of the map
-------------------------------------------------------

Multipliers: voltage 0.1, current 0.001, power 0.1, cos phi 0.001,
frequency 0.01, angle 1, THD 0.1.

    engineering value = raw x multiplier x (CT ratio for currents,
                                            CT x VT ratio for powers)

The analyser reports **secondary-referred** raw counts.  Full scale is
3000 x 0.1 = 300.0 V phase-to-neutral and 6000 x 0.001 = 6.000 A - the CT
secondary rating, not the primary.  A client that applies the CT ratio from
register 32769 recovers 3000.0 A full scale, which is 130 % of the 2309.4 A
that 1600 kVA at 400 V draws; a client that forgets it reads 6 A on a panel
carrying 1500 A and quietly believes it.  We reproduce that asymmetry
faithfully so the poller's primary-versus-secondary sanity check has something
real to catch.

Register 32769 holds the **ratio**, not the primary current.  For the TEDAS
2500/5 main CT it reads 500, not 2500.  Getting this wrong scales every current
and every power by 5.

Register 32778, the baud rate, uses an **inverted** enumeration:
1 = 38400, 2 = 19200, 3 = 9600, 4 = 4800, 5 = 2400.  Bigger number, slower
link.  Every other Modbus device in the panel counts the other way.

THD saturation
--------------

THD registers have a range of 0..999 at x0.1, i.e. they pin at 99.9 %.  At light
load the current THD of a real LV feeder routinely exceeds that, because the
fundamental in the denominator has collapsed while the harmonic currents from
switch-mode loads have not.  A saturated register is not an anomaly, it is
arithmetic.  Every current-THD rule in PANO GOZ is therefore gated on
I > 10 % of the CT rating, and the analyser here saturates rather than wrapping
so a consumer can see it happen.
"""

from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass
from typing import Sequence

try:  # pragma: no cover
    from pymodbus.datastore import ModbusSparseDataBlock
except Exception:  # pragma: no cover
    ModbusSparseDataBlock = None  # type: ignore[assignment]


# ==========================================================================
# Datasheet model
# ==========================================================================

#: Function code 3 may not ask for more than 125 registers in one request.
#: The measurement space is 266 registers, so it always takes several reads.
FC03_MAX_REGISTERS = 125

MEASUREMENT_SPACE = (0, 265)          # inclusive, 266 registers
DIGITAL_OUT_REG = 84                  # genuinely 16 bit
DIGITAL_IN_REG = 85                   # genuinely 16 bit

#: Multipliers, from the device documentation.
MULT_VOLTAGE = 0.1
MULT_CURRENT = 0.001
MULT_POWER = 0.1
MULT_COS = 0.001
MULT_FREQ = 0.01
MULT_ANGLE = 1.0
MULT_THD = 0.1
MULT_ENERGY = 1.0

#: Secondary-referred full scale, raw counts.
FS_VOLTAGE_RAW = 3000                 # 300.0 V L-N, documented
#: Line-to-line full scale is not printed in the documentation we were given.
#: sqrt(3) x 300.0 V = 519.6 V, so 5200 counts is the smallest round value that
#: covers the L-N full scale; it also matches the 520 V ceiling the channel
#: registry carries for a phase voltage.  Marked derived, not quoted.
FS_VOLTAGE_LL_RAW = 5200              # 520.0 V L-L, derived from FS_VOLTAGE_RAW
FS_CURRENT_RAW = 6000                 # 6.000 A CT secondary
FS_THD_RAW = 999                      # 99.9 %
FS_COS_RAW = 1000                     # 1.000

Ratio = str  # "none" | "ct" | "vt" | "ctvt"


@dataclass(frozen=True)
class MReg:
    """One 32-bit measurement quantity (two Modbus registers)."""

    addr: int
    name: str
    mult: float
    ratio: Ratio
    unit: str
    label_tr: str
    signed: bool = False
    raw_max: int | None = None
    words: int = 2


def _v(addr, name, tr):
    return MReg(addr, name, MULT_VOLTAGE, "vt", "V", tr, raw_max=FS_VOLTAGE_RAW)


def _vll(addr, name, tr):
    return MReg(addr, name, MULT_VOLTAGE, "vt", "V", tr, raw_max=FS_VOLTAGE_LL_RAW)


def _i(addr, name, tr):
    return MReg(addr, name, MULT_CURRENT, "ct", "A", tr, raw_max=FS_CURRENT_RAW)


def _p(addr, name, tr, unit="W"):
    return MReg(addr, name, MULT_POWER, "ctvt", unit, tr, signed=True)


def _cos(addr, name, tr):
    return MReg(addr, name, MULT_COS, "none", "-", tr, signed=True, raw_max=FS_COS_RAW)


def _thd(addr, name, tr):
    return MReg(addr, name, MULT_THD, "none", "%", tr, raw_max=FS_THD_RAW)


def _ang(addr, name, tr):
    return MReg(addr, name, MULT_ANGLE, "none", "°", tr)


#: The 28 quantities that the minimum and maximum blocks mirror, addresses 0..54.
BASE_REGS: tuple[MReg, ...] = (
    _v(0, "V_L1", "L1 faz gerilimi"),
    _v(2, "V_L2", "L2 faz gerilimi"),
    _v(4, "V_L3", "L3 faz gerilimi"),
    _i(6, "I_L1", "L1 akımı"),
    _i(8, "I_L2", "L2 akımı"),
    _i(10, "I_L3", "L3 akımı"),
    _i(12, "I_N", "Nötr akımı"),
    _vll(14, "V_L12", "L1-L2 gerilimi"),
    _vll(16, "V_L23", "L2-L3 gerilimi"),
    _vll(18, "V_L31", "L3-L1 gerilimi"),
    _p(20, "P_L1", "L1 aktif güç"),
    _p(22, "P_L2", "L2 aktif güç"),
    _p(24, "P_L3", "L3 aktif güç"),
    _p(26, "Q_L1", "L1 reaktif güç", "var"),
    _p(28, "Q_L2", "L2 reaktif güç", "var"),
    _p(30, "Q_L3", "L3 reaktif güç", "var"),
    _p(32, "S_L1", "L1 görünür güç", "VA"),
    _p(34, "S_L2", "L2 görünür güç", "VA"),
    _p(36, "S_L3", "L3 görünür güç", "VA"),
    _cos(38, "COS_L1", "L1 güç katsayısı"),
    _cos(40, "COS_L2", "L2 güç katsayısı"),
    _cos(42, "COS_L3", "L3 güç katsayısı"),
    _p(44, "P_IMPORT", "Toplam çekilen aktif güç"),
    _p(46, "P_EXPORT", "Toplam verilen aktif güç"),
    _p(48, "Q_INDUCTIVE", "Toplam endüktif reaktif", "var"),
    _p(50, "Q_CAPACITIVE", "Toplam kapasitif reaktif", "var"),
    _p(52, "S_TOTAL", "Toplam görünür güç", "VA"),
    _cos(54, "COS_AVG_IND", "Ortalama endüktif cos φ"),
)

#: Everything above 54 up to 82 that the min/max blocks do NOT mirror.
TAIL_REGS: tuple[MReg, ...] = (
    _cos(56, "COS_AVG_CAP", "Ortalama kapasitif cos φ"),
    MReg(58, "FREQUENCY", MULT_FREQ, "none", "Hz", "Frekans", raw_max=10000),
    _ang(60, "ANG_V_L1", "L1 gerilim açısı"),
    _ang(62, "ANG_V_L2", "L2 gerilim açısı"),
    _ang(64, "ANG_V_L3", "L3 gerilim açısı"),
    _ang(66, "ANG_I_L1", "L1 akım açısı"),
    _ang(68, "ANG_I_L2", "L2 akım açısı"),
    _ang(70, "ANG_I_L3", "L3 akım açısı"),
    _thd(72, "THD_V_L1", "L1 gerilim THD"),
    _thd(74, "THD_V_L2", "L2 gerilim THD"),
    _thd(76, "THD_V_L3", "L3 gerilim THD"),
    _thd(78, "THD_I_L1", "L1 akım THD"),
    _thd(80, "THD_I_L2", "L2 akım THD"),
    _thd(82, "THD_I_L3", "L3 akım THD"),
)

#: Eight 64-bit energy counters at 86, 90, 94 ... 114.
ENERGY_NAMES: tuple[str, ...] = (
    "E_IMPORT_ACTIVE",
    "E_EXPORT_ACTIVE",
    "E_INDUCTIVE_REACTIVE",
    "E_CAPACITIVE_REACTIVE",
    "E_IMPORT_ACTIVE_T2",
    "E_EXPORT_ACTIVE_T2",
    "E_INDUCTIVE_REACTIVE_T2",
    "E_CAPACITIVE_REACTIVE_T2",
)
ENERGY_BASE = 86
ENERGY_WORDS = 4                       # 64 bit
ENERGY_REGS: tuple[MReg, ...] = tuple(
    MReg(ENERGY_BASE + 4 * i, n, MULT_ENERGY, "ctvt", "kWh/kvarh", n, words=ENERGY_WORDS)
    for i, n in enumerate(ENERGY_NAMES)
)

MIN_BASE = 118
MAX_BASE = 174
DEMAND_BASE = 230                      # inside the max/demand block

MIN_REGS: tuple[MReg, ...] = tuple(
    MReg(MIN_BASE + 2 * i, f"MIN_{r.name}", r.mult, r.ratio, r.unit,
         f"{r.label_tr} · minimum", r.signed, r.raw_max)
    for i, r in enumerate(BASE_REGS)
)

MAX_REGS: tuple[MReg, ...] = tuple(
    MReg(MAX_BASE + 2 * i, f"MAX_{r.name}", r.mult, r.ratio, r.unit,
         f"{r.label_tr} · maksimum", r.signed, r.raw_max)
    for i, r in enumerate(BASE_REGS)
)

#: 18 demand quantities filling 230..265.
DEMAND_SPEC: tuple[tuple[str, str, str, Ratio, float], ...] = (
    ("DEM_I_L1", "L1 akım talebi", "A", "ct", MULT_CURRENT),
    ("DEM_I_L2", "L2 akım talebi", "A", "ct", MULT_CURRENT),
    ("DEM_I_L3", "L3 akım talebi", "A", "ct", MULT_CURRENT),
    ("DEM_I_N", "Nötr akım talebi", "A", "ct", MULT_CURRENT),
    ("DEM_P_IMPORT", "Çekilen aktif güç talebi", "W", "ctvt", MULT_POWER),
    ("DEM_P_EXPORT", "Verilen aktif güç talebi", "W", "ctvt", MULT_POWER),
    ("DEM_Q_IND", "Endüktif reaktif talebi", "var", "ctvt", MULT_POWER),
    ("DEM_Q_CAP", "Kapasitif reaktif talebi", "var", "ctvt", MULT_POWER),
    ("DEM_S", "Görünür güç talebi", "VA", "ctvt", MULT_POWER),
    ("MAXDEM_I_L1", "L1 azami akım talebi", "A", "ct", MULT_CURRENT),
    ("MAXDEM_I_L2", "L2 azami akım talebi", "A", "ct", MULT_CURRENT),
    ("MAXDEM_I_L3", "L3 azami akım talebi", "A", "ct", MULT_CURRENT),
    ("MAXDEM_I_N", "Nötr azami akım talebi", "A", "ct", MULT_CURRENT),
    ("MAXDEM_P_IMPORT", "Azami çekilen aktif güç talebi", "W", "ctvt", MULT_POWER),
    ("MAXDEM_P_EXPORT", "Azami verilen aktif güç talebi", "W", "ctvt", MULT_POWER),
    ("MAXDEM_Q_IND", "Azami endüktif reaktif talebi", "var", "ctvt", MULT_POWER),
    ("MAXDEM_Q_CAP", "Azami kapasitif reaktif talebi", "var", "ctvt", MULT_POWER),
    ("MAXDEM_S", "Azami görünür güç talebi", "VA", "ctvt", MULT_POWER),
)

DEMAND_REGS: tuple[MReg, ...] = tuple(
    MReg(DEMAND_BASE + 2 * i, n, mult, ratio, unit, tr, signed=(ratio == "ctvt"))
    for i, (n, tr, unit, ratio, mult) in enumerate(DEMAND_SPEC)
)

MEASUREMENT_REGS: tuple[MReg, ...] = (
    BASE_REGS + TAIL_REGS + ENERGY_REGS + MIN_REGS + MAX_REGS + DEMAND_REGS
)

MREG_BY_NAME: dict[str, MReg] = {r.name: r for r in MEASUREMENT_REGS}
MREG_BY_ADDR: dict[int, MReg] = {r.addr: r for r in MEASUREMENT_REGS}


# ---- settings -------------------------------------------------------------

@dataclass(frozen=True)
class SReg:
    addr: int
    name: str
    label_tr: str
    note: str = ""


#: Note the gap: 32772..32776 are not in the documented list, so a read that
#: spans them raises exception 02.  The poller's block planner must split here,
#: which is the second place in the system where the hole rule earns its keep.
SETTING_REGS: tuple[SReg, ...] = (
    SReg(32768, "VT_RATIO", "Gerilim trafo oranı", "x0.1, yani 10 = 1.0"),
    SReg(32769, "CT_RATIO", "Akım trafo ORANI", "2500/5 için 500, 2500 değil"),
    SReg(32770, "CALC_METHOD", "Hesaplama yöntemi", ""),
    SReg(32771, "DEMAND_TIME", "Talep süresi", "1..60 dakika"),
    SReg(32777, "COMMS_ADDRESS", "Haberleşme adresi", "0..247"),
    SReg(32778, "BAUD_RATE", "Baud hızı", "TERS ENUM 1=38400 2=19200 3=9600 4=4800 5=2400"),
    SReg(32779, "PARITY", "Eşlik", "0 yok · 1 tek · 2 çift"),
)

SREG_BY_NAME: dict[str, SReg] = {r.name: r for r in SETTING_REGS}

#: Inverted on purpose - see the module docstring.
BAUD_ENUM: dict[int, int] = {1: 38400, 2: 19200, 3: 9600, 4: 4800, 5: 2400}
BAUD_ENUM_INV: dict[int, int] = {v: k for k, v in BAUD_ENUM.items()}
PARITY_ENUM: dict[int, str] = {0: "N", 1: "O", 2: "E"}

DEMAND_TIME_RANGE = (1, 60)


def setting_addresses() -> set[int]:
    return {r.addr for r in SETTING_REGS}


def measurement_addresses() -> set[int]:
    lo, hi = MEASUREMENT_SPACE
    return set(range(lo, hi + 1))


def readable_addresses() -> set[int]:
    return measurement_addresses() | setting_addresses()


# ---- encode / decode ------------------------------------------------------

def encode_words(raw: int, words: int = 2) -> list[int]:
    """Big-endian, high word first, two's complement for negatives."""
    bits = 16 * words
    raw = int(raw) & ((1 << bits) - 1)
    return [(raw >> (16 * (words - 1 - i))) & 0xFFFF for i in range(words)]


def decode_words(regs: Sequence[int], signed: bool = False, words: int | None = None) -> int:
    words = len(regs) if words is None else words
    raw = 0
    for w in regs[:words]:
        raw = (raw << 16) | (int(w) & 0xFFFF)
    if signed:
        top = 1 << (16 * words - 1)
        if raw >= top:
            raw -= 1 << (16 * words)
    return raw


def ratio_factor(reg: MReg, ct_ratio: float, vt_ratio: float) -> float:
    if reg.ratio == "ct":
        return float(ct_ratio)
    if reg.ratio == "vt":
        return float(vt_ratio)
    if reg.ratio == "ctvt":
        return float(ct_ratio) * float(vt_ratio)
    return 1.0


def to_raw(reg: MReg, value: float, ct_ratio: float, vt_ratio: float) -> tuple[int, bool]:
    """Engineering (primary) value -> raw counts.  Returns ``(raw, saturated)``."""
    denom = reg.mult * ratio_factor(reg, ct_ratio, vt_ratio)
    raw = int(round(float(value) / denom)) if denom else 0
    sat = False
    if reg.raw_max is not None:
        lo = -reg.raw_max if reg.signed else 0
        if raw > reg.raw_max:
            raw, sat = reg.raw_max, True
        elif raw < lo:
            raw, sat = lo, True
    else:
        bits = 16 * reg.words
        if reg.signed:
            hi = (1 << (bits - 1)) - 1
            lo = -(1 << (bits - 1))
        else:
            hi, lo = (1 << bits) - 1, 0
        if raw > hi:
            raw, sat = hi, True
        elif raw < lo:
            raw, sat = lo, True
    return raw, sat


def from_raw(reg: MReg, raw: int, ct_ratio: float, vt_ratio: float) -> float:
    """Raw counts -> engineering (primary) value.  The poller's decode path."""
    return raw * reg.mult * ratio_factor(reg, ct_ratio, vt_ratio)


# ==========================================================================
# Simulator
# ==========================================================================

class MprSim:
    """An MPR-53CS whose numbers you supply.

    The simulator does no load modelling of its own: :meth:`update` takes the
    per-phase currents and voltages from whatever is driving the demo and turns
    them into a physically consistent register image - line voltages from the
    phasors, powers from V x I x cos phi, angles, min/max tracking, demand
    windows and integrating energy counters.  Keeping the load model outside
    means the panel simulator and the analyser cannot tell two different stories
    about the same instant.
    """

    def __init__(
        self,
        *,
        slave_id: int = 1,
        ct_ratio: int = 500,
        vt_ratio: float = 1.0,
        seed: int = 0,
    ) -> None:
        if not 0 <= slave_id <= 247:
            raise ValueError(f"comms address {slave_id} outside 0..247")
        if ct_ratio <= 0:
            raise ValueError("CT ratio must be positive; register 32769 holds the RATIO (2500/5 -> 500)")
        self.slave_id = slave_id
        self.ct_ratio = int(ct_ratio)
        self.vt_ratio = float(vt_ratio)
        self.rng = random.Random(seed)

        self.baud = 19200
        self.parity = "E"
        self.calc_method = 0
        self.demand_time_min = 15

        self.digital_out = 0
        self.digital_in = 0

        self.ts: float = 0.0
        self._last_ts: float | None = None

        self.eng: dict[str, float] = {r.name: 0.0 for r in BASE_REGS + TAIL_REGS}
        self.minima: dict[str, float] = {}
        self.maxima: dict[str, float] = {}
        self.energy: dict[str, float] = {n: 0.0 for n in ENERGY_NAMES}
        self.demand: dict[str, float] = {r.name: 0.0 for r in DEMAND_REGS}
        self.saturated: list[str] = []

        self.updates = 0

    # ---------------------------------------------------------------- CT --

    @property
    def ct_primary_a(self) -> float:
        """Primary rating implied by the ratio register, assuming a 5 A secondary."""
        return self.ct_ratio * 5.0

    @property
    def current_full_scale_a(self) -> float:
        return FS_CURRENT_RAW * MULT_CURRENT * self.ct_ratio

    # ------------------------------------------------------------ update --

    def update(
        self,
        *,
        i_l1: float,
        i_l2: float,
        i_l3: float,
        i_n: float,
        v_l1: float,
        v_l2: float,
        v_l3: float,
        freq: float,
        thd: dict,
        ts: float,
        cos_phi: float | tuple[float, float, float] = 0.95,
        digital_in: int | None = None,
        digital_out: int | None = None,
    ) -> None:
        """Load one instant into the register image.

        ``thd`` accepts either short keys (``"v_l1"``, ``"i_l3"``) or the
        canonical channel names (``"mpr.thd_v_l1_pct"``); missing entries stay
        at zero rather than being invented.
        """
        self.ts = float(ts)
        dt = 0.0 if self._last_ts is None else max(0.0, self.ts - self._last_ts)
        self._last_ts = self.ts
        self.updates += 1
        self.saturated = []

        if isinstance(cos_phi, (int, float)):
            cp = (float(cos_phi),) * 3
        else:
            cp = tuple(float(c) for c in cos_phi)  # type: ignore[assignment]

        v = (float(v_l1), float(v_l2), float(v_l3))
        i = (float(i_l1), float(i_l2), float(i_l3))

        e = self.eng
        e["V_L1"], e["V_L2"], e["V_L3"] = v
        e["I_L1"], e["I_L2"], e["I_L3"] = i
        e["I_N"] = float(i_n)

        # Line voltages from the phasors at the nominal 120 degree spacing.
        # Turkish LV secondaries are heavily single-phase loaded, so the phase
        # magnitudes genuinely differ; assuming sqrt(3) x average would hide it.
        angles = (0.0, -120.0, 120.0)
        ph = [complex(v[k] * math.cos(math.radians(angles[k])),
                      v[k] * math.sin(math.radians(angles[k]))) for k in range(3)]
        e["V_L12"] = abs(ph[0] - ph[1])
        e["V_L23"] = abs(ph[1] - ph[2])
        e["V_L31"] = abs(ph[2] - ph[0])

        p_tot = q_tot = s_tot = 0.0
        for k, tag in enumerate(("L1", "L2", "L3")):
            c = max(-1.0, min(1.0, cp[k]))
            s = v[k] * i[k]
            p = s * c
            q = s * math.sqrt(max(0.0, 1.0 - c * c))
            e[f"S_{tag}"], e[f"P_{tag}"], e[f"Q_{tag}"] = s, p, q
            e[f"COS_{tag}"] = c
            p_tot += p
            q_tot += q
            s_tot += s

        e["P_IMPORT"] = max(0.0, p_tot)
        e["P_EXPORT"] = max(0.0, -p_tot)
        e["Q_INDUCTIVE"] = max(0.0, q_tot)
        e["Q_CAPACITIVE"] = max(0.0, -q_tot)
        e["S_TOTAL"] = s_tot
        e["COS_AVG_IND"] = (p_tot / s_tot) if s_tot > 1e-9 else 1.0
        e["COS_AVG_CAP"] = 0.0
        e["FREQUENCY"] = float(freq)

        for k, tag in enumerate(("L1", "L2", "L3")):
            e[f"ANG_V_{tag}"] = angles[k] % 360.0
            phi = math.degrees(math.acos(max(-1.0, min(1.0, cp[k]))))
            e[f"ANG_I_{tag}"] = (angles[k] - phi) % 360.0

        for tag in ("v_l1", "v_l2", "v_l3", "i_l1", "i_l2", "i_l3"):
            name = "THD_" + tag.upper()
            e[name] = float(self._thd_lookup(thd, tag))

        if digital_in is not None:
            self.digital_in = int(digital_in) & 0xFFFF
        if digital_out is not None:
            self.digital_out = int(digital_out) & 0xFFFF

        self._track_min_max()
        self._integrate_energy(dt)
        self._update_demand(dt)

    @staticmethod
    def _thd_lookup(thd: dict, tag: str) -> float:
        if not thd:
            return 0.0
        for key in (tag, tag.upper(), f"mpr.thd_{tag}_pct", f"thd_{tag}", f"thd_{tag}_pct"):
            if key in thd:
                return float(thd[key])
        return 0.0

    def _track_min_max(self) -> None:
        for r in BASE_REGS:
            val = self.eng.get(r.name, 0.0)
            cur_min = self.minima.get(r.name)
            cur_max = self.maxima.get(r.name)
            self.minima[r.name] = val if cur_min is None else min(cur_min, val)
            self.maxima[r.name] = val if cur_max is None else max(cur_max, val)

    def _integrate_energy(self, dt: float) -> None:
        if dt <= 0:
            return
        h = dt / 3600.0
        e = self.eng
        self.energy["E_IMPORT_ACTIVE"] += e["P_IMPORT"] * h / 1000.0
        self.energy["E_EXPORT_ACTIVE"] += e["P_EXPORT"] * h / 1000.0
        self.energy["E_INDUCTIVE_REACTIVE"] += e["Q_INDUCTIVE"] * h / 1000.0
        self.energy["E_CAPACITIVE_REACTIVE"] += e["Q_CAPACITIVE"] * h / 1000.0
        for n in ("E_IMPORT_ACTIVE", "E_EXPORT_ACTIVE",
                  "E_INDUCTIVE_REACTIVE", "E_CAPACITIVE_REACTIVE"):
            self.energy[n + "_T2"] += self.energy[n] * 0.0  # tariff 2 unused on this feeder

    def _update_demand(self, dt: float) -> None:
        """Sliding demand, modelled as a first-order lag over the demand window.

        A real MPR-53CS integrates over a fixed block; a first-order lag with the
        same time constant is within a couple of percent of it and needs no
        history buffer, which matters when the gateway is a DIN-rail box.  The
        difference is documented rather than papered over.
        """
        window = max(1, int(self.demand_time_min)) * 60.0
        alpha = 1.0 if dt <= 0 else min(1.0, dt / window)
        pairs = (
            ("DEM_I_L1", "I_L1"), ("DEM_I_L2", "I_L2"), ("DEM_I_L3", "I_L3"),
            ("DEM_I_N", "I_N"), ("DEM_P_IMPORT", "P_IMPORT"),
            ("DEM_P_EXPORT", "P_EXPORT"), ("DEM_Q_IND", "Q_INDUCTIVE"),
            ("DEM_Q_CAP", "Q_CAPACITIVE"), ("DEM_S", "S_TOTAL"),
        )
        for dem, src in pairs:
            cur = self.demand.get(dem, 0.0)
            new = cur + alpha * (self.eng.get(src, 0.0) - cur) if self.updates > 1 else self.eng.get(src, 0.0)
            self.demand[dem] = new
            mx = "MAXDEM_" + dem[4:]
            self.demand[mx] = max(self.demand.get(mx, 0.0), new)

    # ------------------------------------------------------------- mapping --

    def block(self) -> dict[int, int]:
        """Render the whole 266-register measurement space plus the settings."""
        b: dict[int, int] = {}
        sat: list[str] = []

        def put(reg: MReg, value: float) -> None:
            raw, s = to_raw(reg, value, self.ct_ratio, self.vt_ratio)
            for k, w in enumerate(encode_words(raw, reg.words)):
                b[reg.addr + k] = w
            if s:
                sat.append(reg.name)

        for r in BASE_REGS + TAIL_REGS:
            put(r, self.eng.get(r.name, 0.0))

        # 84 / 85 are genuine 16-bit registers, and the reason we know the rest
        # are 32-bit: they are the only two addresses that step by one.
        b[DIGITAL_OUT_REG] = self.digital_out & 0xFFFF
        b[DIGITAL_IN_REG] = self.digital_in & 0xFFFF

        for r in ENERGY_REGS:
            raw = int(round(self.energy.get(r.name, 0.0) / MULT_ENERGY))
            for k, w in enumerate(encode_words(max(0, raw), r.words)):
                b[r.addr + k] = w

        for r in MIN_REGS:
            put(r, self.minima.get(r.name[4:], 0.0))
        for r in MAX_REGS:
            put(r, self.maxima.get(r.name[4:], 0.0))
        for r in DEMAND_REGS:
            put(r, self.demand.get(r.name, 0.0))

        # Any address inside 0..265 we did not name reads zero rather than
        # raising: the measurement space is contiguous on a real device.
        lo, hi = MEASUREMENT_SPACE
        for a in range(lo, hi + 1):
            b.setdefault(a, 0)

        b[SREG_BY_NAME["VT_RATIO"].addr] = int(round(self.vt_ratio * 10)) & 0xFFFF
        b[SREG_BY_NAME["CT_RATIO"].addr] = self.ct_ratio & 0xFFFF
        b[SREG_BY_NAME["CALC_METHOD"].addr] = self.calc_method & 0xFFFF
        b[SREG_BY_NAME["DEMAND_TIME"].addr] = int(self.demand_time_min) & 0xFFFF
        b[SREG_BY_NAME["COMMS_ADDRESS"].addr] = self.slave_id & 0xFFFF
        b[SREG_BY_NAME["BAUD_RATE"].addr] = BAUD_ENUM_INV.get(self.baud, 3)
        b[SREG_BY_NAME["PARITY"].addr] = {"N": 0, "O": 1, "E": 2}.get(self.parity, 0)
        # 32772..32776 deliberately absent.

        self.saturated = sat
        return b

    def datablock(self):
        if ModbusSparseDataBlock is None:  # pragma: no cover
            raise RuntimeError("pymodbus is required for datablock()")
        return ModbusSparseDataBlock(self.block())

    # ---------------------------------------------------------------- info --

    def expected(self, name: str) -> float:
        """The engineering value a correct client must recover for ``name``."""
        if name in self.eng:
            return self.eng[name]
        if name.startswith("MIN_"):
            return self.minima.get(name[4:], 0.0)
        if name.startswith("MAX_"):
            return self.maxima.get(name[4:], 0.0)
        if name in self.demand:
            return self.demand[name]
        if name in self.energy:
            return self.energy[name]
        raise KeyError(name)

    def describe(self) -> dict:
        return {
            "slave_id": self.slave_id,
            "ct_ratio": self.ct_ratio,
            "ct_primary_a": self.ct_primary_a,
            "vt_ratio": self.vt_ratio,
            "current_full_scale_a": self.current_full_scale_a,
            "demand_time_min": self.demand_time_min,
            "baud": self.baud,
            "baud_enum": BAUD_ENUM_INV.get(self.baud),
            "parity": self.parity,
            "measurement_registers": MEASUREMENT_SPACE[1] - MEASUREMENT_SPACE[0] + 1,
            "reads_needed_fc03": math.ceil(
                (MEASUREMENT_SPACE[1] - MEASUREMENT_SPACE[0] + 1) / FC03_MAX_REGISTERS
            ),
            "saturated": list(self.saturated),
        }


# ==========================================================================

if __name__ == "__main__":
    from panogoz.contracts import assets

    T0 = 1_757_000_000.0

    print("=" * 74)
    print("Entes MPR-53CS register model  ·  self-test")
    print("=" * 74)

    sim = MprSim(slave_id=1, ct_ratio=500, vt_ratio=1.0, seed=3)
    print("\n[1] configuration")
    d = sim.describe()
    print(f"    CT ratio register  : {d['ct_ratio']}   (2500/5 -> 500, NOT 2500)")
    print(f"    implied primary    : {d['ct_primary_a']:.0f} A")
    print(f"    current full scale : {d['current_full_scale_a']:.1f} A "
          f"= {100 * d['current_full_scale_a'] / assets.MAIN_BUSBAR_RATED_A:.0f}% of the {assets.MAIN_BUSBAR_RATED_A:.0f} A busbar rating")
    print(f"    measurement space  : {d['measurement_registers']} registers "
          f"-> {d['reads_needed_fc03']} FC03 reads at the 125-register limit")
    assert d["ct_primary_a"] == 2500.0
    assert abs(d["current_full_scale_a"] - 3000.0) < 1e-6
    assert d["reads_needed_fc03"] == 3

    print("\n[2] one instant, unbalanced as a Turkish LV secondary really is")
    sim.update(
        i_l1=1420.0, i_l2=980.0, i_l3=1150.0, i_n=310.0,
        v_l1=231.4, v_l2=229.8, v_l3=233.1, freq=49.98,
        thd={"v_l1": 2.1, "v_l2": 2.4, "v_l3": 2.0, "i_l1": 11.5, "i_l2": 14.2, "i_l3": 9.8},
        ts=T0, cos_phi=0.94,
    )
    b = sim.block()
    unb = 100 * (max(1420.0, 980.0, 1150.0) - min(1420.0, 980.0, 1150.0)) / ((1420 + 980 + 1150) / 3)
    print(f"    phase unbalance    : {unb:.1f}%  (20-40% is routine, never assume balance)")
    print(f"    reg 6/7 raw        : {b[6]}, {b[7]}  -> secondary {decode_words([b[6], b[7]]) * 0.001:.3f} A")
    print(f"    with CT ratio      : {decode_words([b[6], b[7]]) * 0.001 * 500:.1f} A  <- correct")
    print(f"    without CT ratio   : {decode_words([b[6], b[7]]) * 0.001:.3f} A  <- the trap")
    assert abs(decode_words([b[6], b[7]]) * 0.001 * 500 - 1420.0) < 0.5

    print("\n[3] full round-trip through the documented arithmetic")
    worst = 0.0
    for r in BASE_REGS + TAIL_REGS:
        raw = decode_words([b[r.addr + k] for k in range(r.words)], signed=r.signed)
        got = from_raw(r, raw, sim.ct_ratio, sim.vt_ratio)
        want = sim.expected(r.name)
        err = abs(got - want)
        rel = err / max(1.0, abs(want))
        worst = max(worst, rel)
        if r.name in ("V_L1", "I_L2", "I_N", "V_L12", "P_L1", "S_TOTAL", "COS_L1",
                      "FREQUENCY", "THD_I_L2", "ANG_I_L2"):
            print(f"    {r.name:<11} raw {raw:>10}  ->  {got:>12.3f} {r.unit:<4} (beklenen {want:.3f})")
    print(f"    worst relative error over {len(BASE_REGS + TAIL_REGS)} quantities: {worst:.2e}")
    assert worst < 1e-3, worst

    print("\n[4] 16-bit islands at 84 and 85")
    sim.update(i_l1=1420.0, i_l2=980.0, i_l3=1150.0, i_n=310.0,
               v_l1=231.4, v_l2=229.8, v_l3=233.1, freq=49.98,
               thd={}, ts=T0 + 60, digital_in=0b0101, digital_out=0b0010)
    b = sim.block()
    print(f"    reg 84 (out)       : 0x{b[84]:04X}")
    print(f"    reg 85 (in)        : 0x{b[85]:04X}")
    print(f"    reg 86 (energy)    : 64-bit at 86..89 -> {decode_words([b[86 + k] for k in range(4)])} kWh")
    assert b[84] == 0b0010 and b[85] == 0b0101

    print("\n[5] settings block, with its hole")
    for r in SETTING_REGS:
        print(f"    {r.addr}  {r.name:<14} = {b[r.addr]:<6} {r.note}")
    missing = [a for a in range(32772, 32777) if a in b]
    print(f"    32772..32776       : absent from the map -> {missing == []}")
    print(f"    baud enum          : {b[32778]} = {BAUD_ENUM[b[32778]]} baud  (INVERTED: bigger = slower)")
    assert b[32769] == 500
    assert b[32768] == 10
    assert b[32771] == 15
    assert BAUD_ENUM[b[32778]] == 19200
    assert not missing

    print("\n[6] THD saturation at light load")
    light = MprSim(ct_ratio=500, seed=4)
    light.update(i_l1=40.0, i_l2=38.0, i_l3=41.0, i_n=22.0,
                 v_l1=232.0, v_l2=232.0, v_l3=232.0, freq=50.0,
                 thd={"i_l1": 140.0, "i_l2": 99.9, "i_l3": 220.0, "v_l1": 2.0},
                 ts=T0)
    lb = light.block()
    ct_primary = light.ct_primary_a
    gate = 0.10 * ct_primary
    print(f"    reg 78 raw         : {decode_words([lb[78], lb[79]])} -> {decode_words([lb[78], lb[79]]) * 0.1:.1f} %  (pinned at 99.9)")
    print(f"    saturated          : {[s for s in light.saturated if s.startswith('THD')]}")
    print(f"    load               : {40.0:.0f} A = {100 * 40.0 / ct_primary:.1f}% of the {ct_primary:.0f} A CT")
    print(f"    THD-I rule gate    : I > {gate:.0f} A  ->  gated OFF, this reading is arithmetic not anomaly")
    assert decode_words([lb[78], lb[79]]) == FS_THD_RAW
    assert 40.0 < gate

    print("\n[7] current saturation at full scale")
    over = MprSim(ct_ratio=500, seed=5)
    over.update(i_l1=4000.0, i_l2=100.0, i_l3=100.0, i_n=50.0,
                v_l1=230.0, v_l2=230.0, v_l3=230.0, freq=50.0, thd={}, ts=T0)
    ob = over.block()
    print(f"    4000 A requested   : raw {decode_words([ob[6], ob[7]])} = full scale {FS_CURRENT_RAW}")
    print(f"    recovered          : {decode_words([ob[6], ob[7]]) * 0.001 * 500:.0f} A  (saturates, does not wrap)")
    print(f"    flagged            : {over.saturated[:3]}")
    assert decode_words([ob[6], ob[7]]) == FS_CURRENT_RAW
    assert "I_L1" in over.saturated

    print("\n[8] min / max / demand blocks are populated")
    for nm in ("MIN_V_L1", "MIN_I_L1", "MAX_I_L1", "MAX_S_TOTAL"):
        r = MREG_BY_NAME[nm]
        val = from_raw(r, decode_words([b[r.addr], b[r.addr + 1]], signed=r.signed), 500, 1.0)
        print(f"    {nm:<12} @ {r.addr:>3} : {val:>12.1f} {r.unit}   (beklenen {sim.expected(nm):.1f})")
        assert abs(val - sim.expected(nm)) / max(1.0, abs(sim.expected(nm))) < 1e-3
    dem = MREG_BY_NAME["DEM_I_L1"]
    print(f"    DEM_I_L1 @ {dem.addr}  : "
          f"{from_raw(dem, decode_words([b[dem.addr], b[dem.addr + 1]]), 500, 1.0):.1f} A "
          f"({sim.demand_time_min} dakikalik pencere)")
    print(f"    map spans          : {min(b)}..{max(a for a in b if a < 1000)} plus settings {sorted(setting_addresses())}")
    assert MAX_REGS[-1].addr + 1 == 229
    assert DEMAND_REGS[-1].addr + 1 == 265

    print("\n[9] guardrails")
    for bad, why in (
        (lambda: MprSim(slave_id=300), "address 300 > 247"),
        (lambda: MprSim(ct_ratio=0), "CT ratio 0"),
    ):
        try:
            bad()
            raise AssertionError(why)
        except ValueError as exc:
            print(f"    rejected: {why:<24} -> {exc}")

    print("\n" + "=" * 74)
    print("MPR-53CS self-test PASSED")
    print("=" * 74)
