"""PRPD (phase-resolved partial discharge) generator, sensor model and packer.

This is the *physics + front-end* half of the PANO GOZ RF channel.  It produces
the same object the PD-01 node produces: a 64 phase x 32 amplitude histogram of
pulses, packed into a few hundred bytes.  ``panogoz.detector.prpd_classify``
consumes it.

What is actually being measured
-------------------------------
PD-01 clamps a Techimp HFCT30 (1-60 MHz, 17 mV/mA at 42 MHz into 50 ohm) around
the *protective earth* stud - one of the two M12 stainless earth terminals of
Madde 2.2.6.2.iii - never around a phase conductor: the HFCT sees 0.6 Vpp per
100 A of 50 Hz current, i.e. 6 mV_pp per amp, so a phase clamp would be
saturated by load current alone.  A 1-3 MHz high-pass is mandatory.

The signal chain modelled here is

    HFCT -> 1..30 MHz band-pass -> AD8318 logarithmic detector -> peak hold -> ADC

Amplitude scale: the HFCT30 gives 0.4 Vpp per 100 pC into a matched 50 ohm
load, i.e. ``k_50 = 2 mV_pp/pC``, about ``1 mV_peak/pC``.  The AD8318 has a
60 dB linear-in-dB range at 24 mV/dB, so ~0.35 pC .. 300 pC of *coupled* charge
lands inside the detector window.  0 dB(pC) is defined as 1 pC-equivalent.

Phase reference
---------------
The PRPD abscissa is the mains phase angle taken from the node's own supply
(the 6 A gG "Ic Ihtiyac" circuit, Madde 2.2.12).  Which of the three phases
that socket sits on is *not known to the node*, so every record carries an
unknown offset of 0, 120 or 240 degrees.  The classifier de-rotates to a
canonical frame; see ``prpd_classify.features``.

Where the pulses sit in phase - THE discriminator
-------------------------------------------------
Two different mechanisms live on this channel and they are separated by phase,
not by amplitude:

* **Voltage-driven discharge** (void, surface, corona) ignites when the applied
  field is high and *still rising*, so it clusters on the **rising slopes of
  the voltage**, 0-90 deg and 180-270 deg, ahead of the voltage peaks.
* **A series micro-arc across a degrading joint** is *current* driven.  The arc
  extinguishes when the current through it collapses and reignites when the
  recovery voltage across the gap is re-established, so its pulses cluster
  around the **current zero crossings**, at ``phi`` and ``180 + phi`` where
  ``phi = acos(cos_phi)`` is the load's power-factor angle.  They do NOT follow
  the current peaks.

At 400 V that second mechanism is the only one that is physically available -
see the honesty note in ``panogoz.detector.prpd_classify``.

Everything is deterministic given ``seed``.  No wall clock is read anywhere.
"""

from __future__ import annotations

import math

import numpy as np

# ---------------------------------------------------------------------------
# Grid / histogram geometry
# ---------------------------------------------------------------------------

F_NOMINAL_HZ = 50.0
DEFAULT_CYCLES = 3000                      # 60 s at 50 Hz

N_PHASE = 64
N_AMP = 32
DEG_PER_PHASE_BIN = 360.0 / N_PHASE        # 5.625 deg
AMP_MIN_DB = 0.0
AMP_MAX_DB = 80.0
DB_PER_AMP_BIN = (AMP_MAX_DB - AMP_MIN_DB) / N_AMP   # 2.5 dB

PHASE_CENTRES_DEG = (np.arange(N_PHASE) + 0.5) * DEG_PER_PHASE_BIN
AMP_CENTRES_DB = AMP_MIN_DB + (np.arange(N_AMP) + 0.5) * DB_PER_AMP_BIN

# ---------------------------------------------------------------------------
# Front-end constants (used by the fixed-point binning below)
# ---------------------------------------------------------------------------

#: Techimp HFCT30 into a matched 50 ohm load: 0.4 Vpp @ 100 pC.
K50_MV_PP_PER_PC = 2.0
#: ... which is ~1 mV of peak amplitude per pC.
MV_PEAK_PER_PC = K50_MV_PP_PER_PC / 2.0
#: AD8318 logarithmic slope.  The detector output is already linear in dB, so
#: the MCU never computes a logarithm.
AD8318_MV_PER_DB = 24.0
#: A 0.859 resistive divider between the AD8318 and a 12-bit 3.3 V ADC
#: (0.80566 mV/LSB) makes the effective slope exactly 25.6 counts per dB, so
#: one 2.5 dB amplitude bin is exactly 64 ADC counts.
ADC_COUNTS_PER_DB = 25.6
#: 64 = 1 << 6.  Amplitude binning on the node is therefore ONE SUBTRACT (the
#: calibration offset, which also absorbs the AD8318's inverted slope) and ONE
#: RIGHT SHIFT.  No float, no libm, no division - which is what lets an
#: STM32L0 running from a Li-SOCl2 cell accumulate a PRPD for 60 s at
#: 10 kpulse/s inside a 2 kB buffer.
AMP_BIN_SHIFT = 6
assert DB_PER_AMP_BIN * ADC_COUNTS_PER_DB == float(1 << AMP_BIN_SHIFT)

#: Phase binning is the same trick: the zero-cross comparator latches the
#: timer, and ``bin = (dt_ticks << 6) / period_ticks`` is one shift and one
#: divide by a value the node already has.
PHASE_BIN_SHIFT = 6
assert (1 << PHASE_BIN_SHIFT) == N_PHASE

# ---------------------------------------------------------------------------
# Sensor-model constants
# ---------------------------------------------------------------------------

Q_THRESHOLD_PC = 5.0        # field detection threshold, pC-equivalent
AMP_NOISE_DB = 0.7          # log-detector + ADC amplitude noise, 1 sigma
PHASE_JITTER_DEG = 1.5      # zero-cross comparator + interrupt latency, 1 sigma
DEAD_TIME_US = 2.0          # peak-hold reset, non-paralysable
GRID_F_SIGMA_HZ = 0.05      # grid frequency spread around 50 Hz
PHASE_OFFSET_CHOICES = (0.0, 120.0, 240.0)   # which phase the node's supply is on
BG_SIGMA_PC = 3.0           # Rayleigh scale of the ambient RF background
BG_RATE_PER_CYCLE = 5.0     # Poisson rate of that background, at 50 Hz

# ---------------------------------------------------------------------------
# Load power factor -> current zero crossing
# ---------------------------------------------------------------------------

#: Typical Turkish LV secondary feeder, compensated: cos phi 0.95 lagging.
DEFAULT_COS_PHI = 0.95


def current_zero_phase_deg(cos_phi: float = DEFAULT_COS_PHI, lagging: bool = True) -> float:
    """Phase angle (deg, voltage-referenced) of the rising current zero crossing.

    With ``v = sin(theta)`` and a lagging load the current is
    ``i = sin(theta - phi)``, so ``i`` crosses zero going positive at
    ``theta = phi``.  The other zero is 180 deg later.  A series micro-arc
    across a loose joint reignites just after each of those two instants.
    """
    c = min(1.0, max(-1.0, float(cos_phi)))
    phi = math.degrees(math.acos(c))
    return phi if lagging else -phi % 360.0


#: Power-factor angle used to place the floating/loose-joint comb.
PF_ANGLE_DEG = current_zero_phase_deg(DEFAULT_COS_PHI)          # 18.19 deg
#: The arc does not reignite exactly at the zero: the gap needs a recovery
#: voltage, which takes a few electrical degrees to build.
FIRST_REIGNITION_DEG = 11.81
#: Successive reignition steps as the half-cycle current builds.
REIGNITION_STEP_DEG = 11.0
#: -> first comb lobe at 18.19 + 11.81 = 30.0 deg, then 41, 52, 63, 74, 85 deg,
#:    mirrored at 210 .. 265 deg.  Those are exactly the lobe positions our
#:    research-phase prototype validated at 99/100; what changed is that they
#:    are now *derived from the current zero crossing* instead of being pinned
#:    to the voltage peaks, which is the physically correct anchor.


def _lobe(mu_deg, sigma_deg, rate_per_cycle, alpha_pc, beta, coupling=0.0) -> dict:
    return {
        "mu_deg": float(mu_deg) % 360.0,
        "sigma_deg": float(sigma_deg),
        # None = Bernoulli U{0,1} per cycle (at most one event per lobe per
        # cycle, which is what makes a floating electrode look like a comb).
        "rate_per_cycle": None if rate_per_cycle is None else float(rate_per_cycle),
        "alpha_pc": float(alpha_pc),
        "beta": float(beta),
        # Amplitude multiplied by |sin(phase)| ** coupling: models a discharge
        # whose magnitude follows the instantaneous voltage.
        "coupling": float(coupling),
    }


CLASS_PARAMS: dict[str, dict] = {
    "GURULTU": {
        "label_tr": "Gürültü",
        "anchor": "none",
        "anchor_deg": None,
        "lobes": [],
        "physics": "Ambient broadband RF only: SMPS, thyristor drives, ISM band, "
                   "own gateway modem.  Uniform in phase by construction.",
        "note_tr": "Faz ile ilişkisiz arka plan. Sağlıklı panonun normal hali.",
    },
    "BOSLUK": {
        "label_tr": "İç boşluk deşarjı",
        "anchor": "voltage_rising",
        "anchor_deg": 0.0,
        "lobes": [
            _lobe(55, 22, 12, 60, 2.2, 0.0),
            _lobe(235, 22, 12, 58, 2.2, 0.0),
        ],
        "physics": "Gas-filled cavity inside solid insulation.  Ignites once the "
                   "cavity field passes its inception value, i.e. on the RISING "
                   "slope of each half cycle, ahead of the voltage peak.  Two "
                   "mirror-image lobes, moderate amplitude scatter.",
        "note_tr": "Yalıtım içi boşluk. Gerilimin yükselen kenarında ateşlenir, "
                   "iki yarım dalga birbirinin aynasıdır.",
    },
    "YUZEY": {
        "label_tr": "Yüzey kaçağı",
        "anchor": "voltage_rising",
        "anchor_deg": 0.0,
        "lobes": [
            _lobe(75, 45, 40, 250, 1.4, 1.5),
            _lobe(255, 48, 25, 400, 1.6, 1.5),
        ],
        "physics": "Tracking across a contaminated / damp surface.  The channel "
                   "length follows the instantaneous voltage, so amplitude rises "
                   "with |sin(phase)| and the phase spread is wide and asymmetric.",
        "note_tr": "Kirli veya nemli yüzeyde kaçak izi. Geniş faz yayılımı, "
                   "genlik gerilimle birlikte büyür.",
    },
    "KORONA": {
        "label_tr": "Korona",
        "anchor": "voltage_peak",
        "anchor_deg": 0.0,
        "lobes": [
            _lobe(270, 15, 150, 12, 8.0, 0.0),
            _lobe(90, 12, 12, 10, 8.0, 0.0),
        ],
        "physics": "Point discharge in air.  Strongly polarity dependent: a dense "
                   "train of small, very uniform Trichel pulses on the negative "
                   "peak and a sparse train on the positive peak.",
        "note_tr": "Havada uç deşarjı. Tek kutupta yoğun, küçük ve çok düzgün "
                   "darbeler. AG panosunda genelde pano dışı bir RF kaynağıdır.",
    },
    "YUZEN": {
        "label_tr": "Yüzen elektrot / gevşek bağlantı",
        "anchor": "current_zero",
        "anchor_deg": PF_ANGLE_DEG,
        "lobes": [
            _lobe(PF_ANGLE_DEG + FIRST_REIGNITION_DEG + REIGNITION_STEP_DEG * k,
                  4, None, 1500 - 3 * k, 14.0, 0.0)
            for k in range(6)
        ] + [
            _lobe(180 + PF_ANGLE_DEG + FIRST_REIGNITION_DEG + REIGNITION_STEP_DEG * k,
                  4, None, 1480 - 3 * k, 14.0, 0.0)
            for k in range(6)
        ],
        "physics": "Series micro-arc across a degrading bolted joint (or an "
                   "ungrounded floating metal part).  The arc extinguishes as the "
                   "current collapses and reignites once the recovery voltage is "
                   "re-established, so the events form an evenly spaced comb "
                   "ANCHORED ON THE CURRENT ZERO CROSSINGS at phi and 180+phi.  "
                   "The same gap breaks down every cycle, so the amplitude is "
                   "almost constant - Weibull beta = 14.",
        "note_tr": "Gevşek bağlantı üzerinde seri mikro-ark. Darbeler AKIM SIFIR "
                   "GEÇİŞLERİ çevresinde, eşit aralıklı ve neredeyse sabit "
                   "genliklidir. Bu kanalın asıl aradığı imza budur.",
    },
}

#: English aliases so the research-phase vocabulary keeps working.
CLASS_ALIASES = {
    "noise": "GURULTU", "healthy": "GURULTU",
    "void": "BOSLUK", "internal": "BOSLUK", "cavity": "BOSLUK",
    "surface": "YUZEY", "tracking": "YUZEY",
    "corona": "KORONA",
    "floating": "YUZEN", "loose": "YUZEN", "arc": "YUZEN",
}

CLASSES = tuple(CLASS_PARAMS)   # ("GURULTU","BOSLUK","YUZEY","KORONA","YUZEN")


def resolve_class(klass: str) -> str:
    """Canonical class key from a Turkish contract name or an English alias."""
    k = str(klass).strip()
    if k in CLASS_PARAMS:
        return k
    low = k.lower()
    if low in CLASS_ALIASES:
        return CLASS_ALIASES[low]
    up = k.upper()
    if up in CLASS_PARAMS:
        return up
    raise KeyError(f"unknown PRPD class {klass!r}; known: {sorted(CLASS_PARAMS)} "
                   f"+ aliases {sorted(CLASS_ALIASES)}")


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------

def _vonmises_deg(mu_deg: float, sigma_deg: float, n: int, rng) -> np.ndarray:
    """Wrapped-normal-like phase draw.  kappa ~ 1/sigma^2 for small sigma."""
    kappa = (180.0 / (math.pi * max(sigma_deg, 1e-3))) ** 2
    return np.degrees(rng.vonmises(math.radians(mu_deg), kappa, n)) % 360.0


def _generate_arrays(klass: str, cycles: int, seed: int, f_hz: float,
                     phase_offset_deg: float, noise_rate: float
                     ) -> tuple[np.ndarray, np.ndarray]:
    """Array-valued core of :func:`generate`.  See there for the physics.

    Kept separate so :func:`record` never has to materialise half a million
    Python tuples on the way to a histogram.  ``generate`` is the documented
    interface; this is the same numbers without the boxing.
    """
    if cycles <= 0:
        raise ValueError("cycles must be positive")
    if not (40.0 <= f_hz <= 70.0):
        raise ValueError(f"f_hz {f_hz} outside the plausible grid range")

    key = resolve_class(klass)
    spec = CLASS_PARAMS[key]
    rng = np.random.default_rng(seed)

    ph_parts: list[np.ndarray] = []
    q_parts: list[np.ndarray] = []

    for lobe in spec["lobes"]:
        lam = lobe["rate_per_cycle"]
        if lam is None:
            counts = rng.integers(0, 2, cycles)
        else:
            counts = rng.poisson(lam, cycles)
        total = int(counts.sum())
        if total == 0:
            continue
        ph = _vonmises_deg(lobe["mu_deg"], lobe["sigma_deg"], total, rng)
        q = lobe["alpha_pc"] * rng.weibull(lobe["beta"], total)
        cpl = lobe["coupling"]
        if cpl:
            q = q * np.abs(np.sin(np.radians(ph))) ** cpl
        ph_parts.append(ph)
        q_parts.append(q)

    # Ambient background: always superimposed, uniform in phase, Rayleigh in
    # amplitude.  Poisson in TIME, hence the F_NOMINAL_HZ / f_hz scaling.
    bg_lambda = float(noise_rate) * (F_NOMINAL_HZ / f_hz)
    counts = rng.poisson(bg_lambda, cycles)
    total = int(counts.sum())
    if total:
        ph_parts.append(rng.uniform(0.0, 360.0, total))
        q_parts.append(rng.rayleigh(BG_SIGMA_PC, total))

    if not ph_parts:
        return np.zeros(0), np.zeros(0)
    ph = (np.concatenate(ph_parts) + float(phase_offset_deg)) % 360.0
    q = np.concatenate(q_parts)
    return ph, q


def generate(klass: str, cycles: int = DEFAULT_CYCLES, seed: int = 0,
             f_hz: float = F_NOMINAL_HZ, phase_offset_deg: float = 0.0,
             noise_rate: float = BG_RATE_PER_CYCLE) -> list[tuple[float, float]]:
    """Physical pulse train for one PRPD record.

    Returns ``[(phase_deg, q_pC), ...]`` - the charge that actually reaches the
    HFCT, *before* any threshold, noise, dead time or quantisation.  Feed it to
    :func:`sensor_model` to get what the node digitises.

    ``cycles`` mains cycles at ``f_hz`` is a record of ``cycles / f_hz`` seconds.
    Lobe rates are specified per cycle because the discharge processes are field
    driven; the ambient RF background is a process in *time*, so its per-cycle
    count is scaled by the cycle duration - that is the only place ``f_hz``
    enters the physics.

    ``phase_offset_deg`` rotates the whole record; use it to place a defect on a
    known phase.  The *unknown* 0/120/240 deg reference ambiguity is applied by
    :func:`sensor_model`, not here.
    """
    ph, q = _generate_arrays(klass, cycles, seed, f_hz, phase_offset_deg, noise_rate)
    return list(zip(ph.tolist(), q.tolist()))


# ---------------------------------------------------------------------------
# Sensor / front-end model
# ---------------------------------------------------------------------------

def _amp_bin_fixed_point(db: np.ndarray) -> np.ndarray:
    """dB(pC) -> amplitude bin, the way the node does it.

    ``code`` is the ADC reading of the AD8318 output (25.6 counts per dB by
    front-end design).  The node then does ``bin = (code - code0) >> 6``:
    one subtract of the calibration offset and one shift.  No logarithm is
    taken anywhere - the log already happened in the analogue detector.
    """
    code = np.rint(db * ADC_COUNTS_PER_DB).astype(np.int64)   # ADC codes
    code = np.maximum(code, 0)                                # code0 subtracted
    return np.clip(code >> AMP_BIN_SHIFT, 0, N_AMP - 1)


def _phase_bin_fixed_point(deg: np.ndarray) -> np.ndarray:
    """phase deg -> phase bin, the way the node does it (shift + divide)."""
    ticks = np.rint((deg % 360.0) / 360.0 * 65536.0).astype(np.int64)
    return np.clip((ticks << PHASE_BIN_SHIFT) >> 16, 0, N_PHASE - 1)


def sensor_model(pulses: list[tuple[float, float]], q_thr_pc: float = Q_THRESHOLD_PC,
                 seed: int = 0, cycles: int = DEFAULT_CYCLES,
                 dead_time_us: float = DEAD_TIME_US,
                 offset_choices: tuple[float, ...] = PHASE_OFFSET_CHOICES,
                 ) -> list[tuple[float, float]]:
    """Turn physical pulses into what PD-01 actually digitises.

    Returns ``[(phase_deg, amplitude_dB_pC), ...]`` already snapped to the
    64 x 32 bin centres, because the node has no finer resolution to give.

    Chain, in order:

    1. **log detection** - ``dB(pC) = 20 log10(q)``, done in the AD8318, plus
       N(0, 0.7 dB) of detector + ADC noise, clipped to the 0..80 dB window.
    2. **comparator threshold** - the discriminator sits *after* the log amp,
       so the 5 pC-equivalent threshold is applied to the noisy dB value.
    3. **phase jitter** - N(0, 1.5 deg) from the zero-cross comparator and the
       interrupt latency.
    4. **grid frequency** - drawn N(50, 0.05) Hz.  The node re-syncs on every
       zero crossing, so the only residual is the comparator's fixed ~200 us
       propagation delay beating against the frequency error: 360*df*200e-6 is
       under 0.004 deg.  It is applied anyway, and it is negligible next to the
       1.5 deg jitter - which is the honest answer, not a hand-wave.
    5. **pile-up** - non-paralysable dead time of 2 us: the surviving fraction
       in a phase bin whose local rate is ``lam`` is ``1/(1 + lam*tau)``.  This
       is what flat-tops a dense corona lobe.
    6. **unknown phase reference** - a 0/120/240 deg rotation, because the node
       takes its phase from the "Ic Ihtiyac" socket and does not know which
       phase that socket is fed from.
    7. **quantisation** - 5.625 deg x 2.5 dB, by shift and subtract.
    """
    if len(pulses) == 0:
        return []
    arr = np.asarray(pulses, dtype=float)
    ph, db = _sensor_arrays(arr[:, 0], arr[:, 1], q_thr_pc, seed, cycles,
                            dead_time_us, offset_choices)
    return list(zip(ph.tolist(), db.tolist()))


def _sensor_arrays(ph: np.ndarray, q: np.ndarray, q_thr_pc: float, seed: int,
                   cycles: int, dead_time_us: float,
                   offset_choices: tuple[float, ...]
                   ) -> tuple[np.ndarray, np.ndarray]:
    """Array-valued core of :func:`sensor_model`.  See there for the chain."""
    if ph.size == 0:
        return np.zeros(0), np.zeros(0)
    rng = np.random.default_rng(seed)
    ph = ph % 360.0
    q = np.maximum(q, 1e-6)

    # 1 + 2 - log detector, noise, comparator
    db = 20.0 * np.log10(q) + rng.normal(0.0, AMP_NOISE_DB, q.size)
    thr_db = 20.0 * math.log10(max(q_thr_pc, 1e-6))
    keep = db > thr_db
    ph, db = ph[keep], np.clip(db[keep], AMP_MIN_DB, AMP_MAX_DB)
    if ph.size == 0:
        return np.zeros(0), np.zeros(0)

    # 3 + 4 - phase jitter and the (negligible) grid-frequency residual
    f_true = float(rng.normal(F_NOMINAL_HZ, GRID_F_SIGMA_HZ))
    comparator_delay_s = 200e-6
    df_bias_deg = 360.0 * (f_true - F_NOMINAL_HZ) * comparator_delay_s
    ph = (ph + rng.normal(0.0, PHASE_JITTER_DEG, ph.size) + df_bias_deg) % 360.0

    # 5 - non-paralysable pile-up, evaluated per phase bin so a dense lobe
    #     saturates and a sparse one does not.
    tau = dead_time_us * 1e-6
    if tau > 0.0 and cycles > 0:
        pb = _phase_bin_fixed_point(ph)
        counts = np.bincount(pb, minlength=N_PHASE).astype(float)
        bin_seconds = cycles * (1.0 / f_true) * (DEG_PER_PHASE_BIN / 360.0)
        lam = counts / max(bin_seconds, 1e-12)          # pulses per second
        p_keep = 1.0 / (1.0 + lam * tau)
        alive = rng.random(ph.size) < p_keep[pb]
        ph, db = ph[alive], db[alive]
        if ph.size == 0:
            return np.zeros(0), np.zeros(0)

    # 6 - unknown phase reference
    if offset_choices:
        ph = (ph + float(rng.choice(np.asarray(offset_choices, dtype=float)))) % 360.0

    # 7 - quantisation to the bin grid the node transmits
    ph_q = PHASE_CENTRES_DEG[_phase_bin_fixed_point(ph)]
    db_q = AMP_CENTRES_DB[_amp_bin_fixed_point(db)]
    return ph_q, db_q


# ---------------------------------------------------------------------------
# Histogram
# ---------------------------------------------------------------------------

def histogram(pulses, n_phase: int = N_PHASE, n_amp: int = N_AMP) -> np.ndarray:
    """Accumulate ``[(phase_deg, amp_dB)]`` into a uint16 PRPD histogram.

    Counts saturate at 65535 - the node's accumulator is 16-bit and saturating
    is safer than wrapping, so the model does the same.
    """
    if len(pulses) == 0:
        return np.zeros((n_phase, n_amp), dtype=np.uint16)
    arr = np.asarray(pulses, dtype=float)
    return _histogram_arrays(arr[:, 0], arr[:, 1], n_phase, n_amp)


def _histogram_arrays(ph: np.ndarray, db: np.ndarray, n_phase: int = N_PHASE,
                      n_amp: int = N_AMP) -> np.ndarray:
    """Array-valued core of :func:`histogram`."""
    h = np.zeros((n_phase, n_amp), dtype=np.uint32)
    if ph.size:
        pi = np.clip((ph % 360.0) / (360.0 / n_phase), 0, n_phase - 1e-9).astype(int)
        ai = np.clip((db - AMP_MIN_DB) / ((AMP_MAX_DB - AMP_MIN_DB) / n_amp),
                     0, n_amp - 1e-9).astype(int)
        np.add.at(h, (pi, ai), 1)
    return np.minimum(h, 65535).astype(np.uint16)


# ---------------------------------------------------------------------------
# Wire format: sparse run-length + LEB128 varint
# ---------------------------------------------------------------------------

_PACK_MAGIC = b"PG"
_PACK_VERSION = 1


def _put_varint(out: bytearray, value: int) -> None:
    v = int(value)
    if v < 0:
        raise ValueError("varint is unsigned")
    while True:
        b = v & 0x7F
        v >>= 7
        out.append(b | (0x80 if v else 0x00))
        if not v:
            return


def _get_varint(blob: bytes, i: int) -> tuple[int, int]:
    v = 0
    shift = 0
    while True:
        b = blob[i]
        i += 1
        v |= (b & 0x7F) << shift
        if not (b & 0x80):
            return v, i
        shift += 7


def pack(hist: np.ndarray) -> bytes:
    """Sparse RLE + varint encoding of a PRPD histogram.

    Layout: ``b"PG"``, version, varint(n_phase), varint(n_amp), then records of
    ``varint(zeros_skipped) varint(run_len) run_len * varint(count)`` over the
    row-major flattening.  Trailing zeros are implicit.

    A PRPD is mostly empty - the occupied cells are the two discharge lobes plus
    a thin background band just above the threshold - so this is lossless and
    still small enough for a 255-byte-class radio payload once the record is
    split over a few frames.  ``pack``/``unpack`` round-trip exactly; the
    self-test prints the real sizes rather than a marketing number.
    """
    h = np.asarray(hist)
    n_phase, n_amp = h.shape
    flat = h.reshape(-1).astype(np.int64)
    out = bytearray(_PACK_MAGIC)
    out.append(_PACK_VERSION)
    _put_varint(out, n_phase)
    _put_varint(out, n_amp)

    i = 0
    n = flat.size
    while i < n:
        z = 0
        while i < n and flat[i] == 0:
            z += 1
            i += 1
        start = i
        while i < n and flat[i] != 0:
            i += 1
        run = flat[start:i]
        if run.size == 0:
            break                      # trailing zeros, implicit
        _put_varint(out, z)
        _put_varint(out, int(run.size))
        for v in run.tolist():
            _put_varint(out, int(v))
    return bytes(out)


def unpack(blob: bytes) -> np.ndarray:
    """Inverse of :func:`pack`."""
    if len(blob) < 4 or blob[:2] != _PACK_MAGIC:
        raise ValueError("not a PANO GOZ PRPD blob")
    if blob[2] != _PACK_VERSION:
        raise ValueError(f"unsupported PRPD blob version {blob[2]}")
    i = 3
    n_phase, i = _get_varint(blob, i)
    n_amp, i = _get_varint(blob, i)
    flat = np.zeros(n_phase * n_amp, dtype=np.uint16)
    pos = 0
    end = len(blob)
    while i < end:
        z, i = _get_varint(blob, i)
        run_len, i = _get_varint(blob, i)
        pos += z
        for k in range(run_len):
            v, i = _get_varint(blob, i)
            flat[pos + k] = v
        pos += run_len
    return flat.reshape(n_phase, n_amp)


# ---------------------------------------------------------------------------
# Convenience + display
# ---------------------------------------------------------------------------

def record(klass: str, cycles: int = DEFAULT_CYCLES, seed: int = 0,
           f_hz: float = F_NOMINAL_HZ, phase_offset_deg: float = 0.0,
           noise_rate: float = BG_RATE_PER_CYCLE,
           offset_choices: tuple[float, ...] = PHASE_OFFSET_CHOICES) -> np.ndarray:
    """generate -> sensor_model -> histogram, in one call.

    Numerically identical to calling the three by hand; it just skips boxing
    every pulse into a Python tuple on the way, which matters when a corona
    record holds half a million of them.
    """
    ph, q = _generate_arrays(klass, cycles, seed, f_hz, phase_offset_deg, noise_rate)
    ph, db = _sensor_arrays(ph, q, Q_THRESHOLD_PC, seed + 7919, cycles,
                            DEAD_TIME_US, offset_choices)
    return _histogram_arrays(ph, db)


_RAMP = " .:-=+*#%@"


def ascii_prpd(hist: np.ndarray, height: int = 16, phase_group: int = 1) -> str:
    """Small log-scaled ASCII PRPD.  Phase across, amplitude up."""
    h = np.asarray(hist, dtype=float)
    n_phase, n_amp = h.shape
    if phase_group > 1:
        h = h.reshape(n_phase // phase_group, phase_group, n_amp).sum(axis=1)
        n_phase = h.shape[0]
    group = max(1, n_amp // height)
    h = h[:, : group * height].reshape(n_phase, height, group).sum(axis=2)
    peak = h.max()
    lines = []
    for row in range(height - 1, -1, -1):
        db_lo = AMP_MIN_DB + row * group * DB_PER_AMP_BIN
        cells = []
        for col in range(n_phase):
            v = h[col, row]
            if v <= 0:
                cells.append(_RAMP[0])
            else:
                lvl = 1 + int((len(_RAMP) - 2) * math.log10(1.0 + v) / math.log10(1.0 + peak))
                cells.append(_RAMP[min(lvl, len(_RAMP) - 1)])
        lines.append(f"{db_lo:5.1f} dB |" + "".join(cells) + "|")
    lines.append("        +" + "-" * n_phase + "+")
    ticks = [" "] * n_phase
    for deg in (0, 90, 180, 270):
        ticks[int(deg / 360.0 * n_phase)] = "|"
    lines.append("         " + "".join(ticks) + "   0/90/180/270 deg")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":  # pragma: no cover
    import time

    print("PANO GOZ - PRPD generator self-test")
    print("=" * 72)
    print(f"grid   : {N_PHASE} phase bins x {DEG_PER_PHASE_BIN} deg, "
          f"{N_AMP} amplitude bins x {DB_PER_AMP_BIN} dB, 0..{AMP_MAX_DB:.0f} dB(pC)")
    print(f"scale  : k_50 = {K50_MV_PP_PER_PC} mV_pp/pC -> {MV_PEAK_PER_PC} mV_peak/pC; "
          f"AD8318 {AD8318_MV_PER_DB} mV/dB -> {ADC_COUNTS_PER_DB} ADC counts/dB")
    print(f"binning: 1 amplitude bin = {DB_PER_AMP_BIN} dB = "
          f"{DB_PER_AMP_BIN * ADC_COUNTS_PER_DB:.0f} ADC counts = 1 << {AMP_BIN_SHIFT}"
          "  (subtract + shift, no libm on the node)")
    print(f"current zero at cos phi = {DEFAULT_COS_PHI}: {PF_ANGLE_DEG:.2f} deg and "
          f"{180 + PF_ANGLE_DEG:.2f} deg")
    first = CLASS_PARAMS["YUZEN"]["lobes"][0]["mu_deg"]
    last = CLASS_PARAMS["YUZEN"]["lobes"][5]["mu_deg"]
    print(f"YUZEN comb: {first:.1f} .. {last:.1f} deg  (anchored on the current zero, "
          "NOT on the current peak)")
    print()

    t0 = time.time()
    for klass in CLASSES:
        pulses = generate(klass, cycles=DEFAULT_CYCLES, seed=1)
        seen = sensor_model(pulses, seed=1234, cycles=DEFAULT_CYCLES)
        h = histogram(seen)
        blob = pack(h)
        back = unpack(blob)
        assert np.array_equal(back, h), f"pack/unpack mismatch for {klass}"
        occupied = int((h > 0).sum())
        raw = h.size * 2
        print(f"{klass:<9} physical={len(pulses):>7}  detected={len(seen):>7}  "
              f"cells={occupied:>4}/{h.size}  packed={len(blob):>5} B  "
              f"(raw {raw} B, x{raw / max(len(blob), 1):.1f})  "
              f"rate={len(seen) / (DEFAULT_CYCLES / 50.0):>8.1f}/s")

    # a shorter record, which is what a battery node would really send hourly
    print()
    for cyc in (600, 1500, 3000):
        sizes = [len(pack(record(k, cycles=cyc, seed=3))) for k in CLASSES]
        print(f"{cyc:>5} cycles ({cyc / 50.0:>5.1f} s): packed "
              f"{min(sizes)}..{max(sizes)} B over the five classes")

    print()
    print("empty record:", len(pack(histogram([]))), "B; "
          "unpack round-trip:", np.array_equal(unpack(pack(histogram([]))),
                                               histogram([])))
    print(f"elapsed {time.time() - t0:.1f} s")
    print()
    for klass in ("BOSLUK", "YUZEN"):
        print(f"--- {klass} ({CLASS_PARAMS[klass]['label_tr']}) ---")
        print(ascii_prpd(record(klass, seed=5, offset_choices=(0.0,)),
                         height=12, phase_group=1))
        print()
    print("OK")
