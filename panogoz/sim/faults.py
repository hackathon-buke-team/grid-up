"""Injectable fault scenarios, including the negative controls.

A monitoring system is only as good as the things it refuses to alarm on.  Half
the scenarios in this file exist to be *quiet*: a heat wave, an upstream power
quality event, a transformer energisation, a de-energised panel.  If any of them
raises a joint alarm, the system would raise it in the field too, and the crew
would stop answering the phone by month three.

Every scenario carries ``expect_alarm`` so the acceptance test can assert both
directions, and the ones that must alarm carry ``expect_mode`` /
``forbid_modes`` so that "it alarmed" is not enough - it has to alarm for the
right reason and open the right work order.  Blocked ventilation and a loose
connection both make a lug hotter; only one of them is fixed with a torque
wrench.

Physics that has to be right in here
------------------------------------

* A **series arc** across a degrading joint extinguishes and reignites near
  **current zero**, so its pulses cluster at the current zero crossings
  (0 deg / 180 deg on the current wave).  Voltage-driven PD clusters on the
  voltage rising slopes.  Anyone who writes "micro-arcs follow the current
  peaks" has it backwards.
* At 400 V classical partial discharge does not occur at all: the Paschen
  minimum is 327 V.  The LV RF channel measures loose-joint micro-arcing, is
  reported as a pC **equivalent** in dB, is not IEC 60270 traceable, and never
  dispatches a crew on its own.
* Condensation is driven by **warm moist air arriving faster than the steel
  warms**, not by cold.  The alarm compares the *estimated wall temperature*
  against the dewpoint, never the air temperature.
* A **blocked ventilation path** raises every joint together.  theta is a
  sibling difference, so theta does not move.  That is the signature.
* **Harmonic loading** raises I_N without raising ``K_N = dT_N / I_N^2``.  A
  **bad neutral joint** raises K_N against its own trend.  Same hot bar,
  different work order.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Iterable

from panogoz.contracts import assets, channels
from panogoz.sim import thermal
from panogoz.sim.load import gauss, local_hour, tag, vnoise

WEEK_S = 7.0 * 86400.0
DAY_S = 86400.0

#: Default target joint for the joint-level scenarios: a phase covered by a
#: thermal clip (TC-05 on feeder 7, L2), so the demo shows the contact-sensor
#: path rather than relying on the IR array alone.
DEFAULT_JOINT = "C07-L2-PABUC"
DEFAULT_NEUTRAL_JOINT = "C07-N-PABUC"


def uohm_per_week_for(rate_k_per_week: float, i_ref_a: float,
                      r_th: float = thermal.R_TH_LUG_NOM_K_PER_W) -> float:
    """Convert a drift expressed in theta-kelvin per week into microohm per week.

    The brief specifies the two loose-connection scenarios in kelvin because
    that is what an operator sees on the trend.  The simulator has to inject
    resistance, so the conversion lives here, once, using the nominal 3.0 K/W
    mid-point of the 2-4 K/W lug interval.
    """
    if i_ref_a <= 0.0:
        return 0.0
    return 1e6 * rate_k_per_week / (r_th * i_ref_a * i_ref_a)


# --------------------------------------------------------------------------
# Base class
# --------------------------------------------------------------------------

@dataclass
class Fault:
    """One injected scenario.

    Hooks default to "no effect".  A subclass overrides only what it changes,
    which keeps each scenario readable next to the physics it represents.
    """

    name: str
    start_ts: float
    kw: dict[str, Any] = field(default_factory=dict)
    seed: int = 0

    # -------------------------------------------------------------- helpers

    def elapsed_s(self, ts: float) -> float:
        return max(0.0, ts - self.start_ts)

    def elapsed_days(self, ts: float) -> float:
        return self.elapsed_s(ts) / DAY_S

    def elapsed_weeks(self, ts: float) -> float:
        return self.elapsed_s(ts) / WEEK_S

    def active(self, ts: float) -> bool:
        dur = self.kw.get("duration_s")
        if ts < self.start_ts:
            return False
        return dur is None or ts <= self.start_ts + float(dur)

    def spec(self) -> dict[str, Any]:
        return SCENARIOS[self.name]

    def describe(self) -> dict[str, Any]:
        sp = self.spec()
        return {
            "scenario": self.name,
            "label_tr": sp["label_tr"],
            "description_tr": sp["description_tr"],
            "kind": sp["kind"],
            "expect_alarm": sp["expect_alarm"],
            "expect_mode": sp.get("expect_mode"),
            "forbid_modes": list(sp.get("forbid_modes", ())),
            "expect_flags": list(sp.get("expect_flags", ())),
            "start_ts": self.start_ts,
            "kw": dict(self.kw),
        }

    # ---------------------------------------------------------------- hooks

    def d_r_joint_uohm(self, joint: assets.Joint, ts: float) -> float:
        """Excess contact resistance added to this joint, microohm."""
        return 0.0

    def current_scale(self, joint: assets.Joint, ts: float) -> float:
        """Multiplier on this joint's current."""
        return 1.0

    def panel_current_scale(self, ts: float) -> float:
        return 1.0

    def h3_scale(self, ts: float) -> float:
        """Multiplier on the third-harmonic fraction (drives I_N and THD_I)."""
        return 1.0

    def vent_factor(self, ts: float) -> float:
        """Fraction of nominal ventilation effectiveness."""
        return 1.0

    def air_offset_k(self, ts: float) -> float:
        return 0.0

    def ambient_offset_k(self, ts: float) -> float:
        return 0.0

    def dewpoint_offset_k(self, ts: float) -> float:
        return 0.0

    def thd_v_offset_pct(self, ts: float) -> float:
        return 0.0

    def voltage_scale(self, ts: float) -> float:
        return 1.0

    def pd_override(self, ts: float, base: dict[str, Any]) -> dict[str, Any] | None:
        return None

    def arc_override(self, ts: float, st: dict[str, Any]) -> None:
        return None

    def sensor_value(self, device_key: str, joint_key: str | None, channel: str,
                     value: float, ts: float) -> float:
        return value

    def device_silent(self, device_key: str, ts: float) -> bool:
        return False

    def de_energised(self, ts: float) -> bool:
        return False

    def status_hints(self, ts: float) -> list[str]:
        """Flags the *simulator* knows are true.  For test assertions only - the
        detector has to work these out for itself from the channels."""
        return []

    def events(self, ts: float, prev_ts: float) -> list[dict[str, Any]]:
        """One-shot events fired when the window ``(prev_ts, ts]`` contains them."""
        return []


# --------------------------------------------------------------------------
# Joint-level thermal scenarios
# --------------------------------------------------------------------------

class LooseConnection(Fault):
    """A bolted lug losing preload.

    Contact resistance grows roughly linearly once fretting starts, and the
    thermal signature grows with it.  Parameterised in theta-kelvin per week
    because that is the axis the operator reads, converted to microohm here.
    """

    def d_r_joint_uohm(self, joint: assets.Joint, ts: float) -> float:
        if joint.key != self.kw.get("joint_key", DEFAULT_JOINT):
            return 0.0
        onset = float(self.kw.get("onset_days", 0.0))
        w = (self.elapsed_days(ts) - onset) / 7.0
        if w <= 0.0:
            return 0.0
        rate = uohm_per_week_for(float(self.kw["rate_k_per_week"]),
                                 assets.reference_current(joint))
        return min(float(self.kw.get("cap_uohm", 600.0)), rate * w)


class NeutralLoose(Fault):
    """A neutral lug losing preload.

    Injected directly in microohm per week, not in kelvin: the neutral carries
    only 10-25 % of a phase current, so a kelvin-per-week figure quoted at the
    feeder rating would be meaningless there.  The discriminator downstream is
    ``K_N = dT_N / I_N^2`` rising against its own trend while I_N does not move.
    """

    def d_r_joint_uohm(self, joint: assets.Joint, ts: float) -> float:
        if joint.key != self.kw.get("joint_key", DEFAULT_NEUTRAL_JOINT):
            return 0.0
        onset = float(self.kw.get("onset_days", 0.0))
        w = (self.elapsed_days(ts) - onset) / 7.0
        if w <= 0.0:
            return 0.0
        return min(float(self.kw.get("cap_uohm", 1200.0)),
                   float(self.kw["uohm_per_week"]) * w)


class HarmonicLoad(Fault):
    """Nonlinear load builds up: I_N rises, K_N does not.

    The neutral bar and its joints get hotter, because dT ~ I_N^2 and I_N has
    gone up.  Nothing is loose.  The correct work order is a harmonic survey, a
    rebalance or a derate - not a torque wrench.
    """

    def h3_scale(self, ts: float) -> float:
        ramp = min(1.0, self.elapsed_days(ts) / max(0.1, float(self.kw.get("ramp_days", 3.0))))
        return 1.0 + ramp * (float(self.kw.get("h3_multiplier", 4.5)) - 1.0)


class Overload(Fault):
    """Sustained overload on one outgoing way."""

    def current_scale(self, joint: assets.Joint, ts: float) -> float:
        if joint.feeder_index != int(self.kw.get("feeder_index", 7)):
            return 1.0
        ramp = min(1.0, self.elapsed_days(ts) / max(0.05, float(self.kw.get("ramp_days", 0.5))))
        return 1.0 + ramp * (float(self.kw.get("scale", 2.4)) - 1.0)


class BlockedVentilation(Fault):
    """Filters clogged, louvres blocked, cable trench sealed off.

    Every joint in the panel warms together.  theta is a sibling difference, so
    theta stays where it was.  ``T_JOINT_MAX`` and ``T_AIR`` climb, the absolute
    limits fire, and the mode is thermal_runaway.  A system that calls this a
    loose connection sends a crew with the wrong tools.
    """

    def vent_factor(self, ts: float) -> float:
        ramp = min(1.0, self.elapsed_days(ts) / max(0.1, float(self.kw.get("ramp_days", 2.0))))
        v = float(self.kw.get("vent_factor", 0.32))
        return 1.0 + ramp * (v - 1.0)


class Condensation(Fault):
    """Moist-air advection at dawn against a wall still at the night minimum."""

    def _window(self, ts: float) -> float:
        h = local_hour(ts)
        start = float(self.kw.get("start_hour", 5.2))
        dur = float(self.kw.get("duration_h", 2.5))
        days = float(self.kw.get("days", 3.0))
        if self.elapsed_days(ts) > days:
            return 0.0
        if not (start <= h <= start + dur):
            return 0.0
        edge = 0.4
        return min(1.0, (h - start) / edge, (start + dur - h) / edge)

    def dewpoint_offset_k(self, ts: float) -> float:
        return float(self.kw.get("dewpoint_boost_k", 7.0)) * self._window(ts)

    def status_hints(self, ts: float) -> list[str]:
        return ["CONDENSATION"] if self._window(ts) > 0.0 else []


# --------------------------------------------------------------------------
# RF / arc scenarios
# --------------------------------------------------------------------------

class PdFloating(Fault):
    """Floating-electrode micro-arcing at one joint.

    The PRPD class walks GURULTU -> YUZEY -> YUZEN as the discharge organises
    itself.  Pulses cluster at the **current zero crossings** (0 deg and
    180 deg on the current wave), because a series arc across a degrading
    contact extinguishes and restrikes near current zero.  If they clustered on
    the voltage rising slopes it would be voltage-driven PD, and at 400 V that
    cannot happen - the Paschen minimum is 327 V.
    """

    def pd_override(self, ts: float, base: dict[str, Any]) -> dict[str, Any] | None:
        ramp_days = max(0.5, float(self.kw.get("ramp_days", 12.0)))
        p = min(1.0, self.elapsed_days(ts) / ramp_days)
        if p <= 0.0:
            return None
        out = dict(base)
        out["rate_per_s"] = base["rate_per_s"] + p * float(self.kw.get("peak_rate", 900.0))
        out["qmax_db"] = base["qmax_db"] + p * float(self.kw.get("peak_qmax_db", 30.0))
        out["nqn"] = base["nqn"] + p * 480.0
        out["tev_db"] = base["tev_db"] + p * 16.0
        out["ultrasonic_db"] = base["ultrasonic_db"] + p * 11.0
        if p < 0.25:
            out["klass"] = "GURULTU"
        elif p < 0.55:
            out["klass"] = "YUZEY"
        else:
            out["klass"] = "YUZEN"
        # Phase clustering, degrees on the CURRENT wave.  Series arcing sits at
        # the current zeros; this is the feature that separates it from PD.
        out["phase_clusters_deg"] = [0.0, 180.0]
        out["cluster_sigma_deg"] = max(6.0, 26.0 - 16.0 * p)
        out["joint_key"] = self.kw.get("joint_key", DEFAULT_JOINT)
        out["progress"] = p
        return out


#: TVOC-2 detector addressing.  Trip detector LOW bitfield: bit0-9 = X1:1..10,
#: bit10-14 = X2:1..5.  Trip detector HIGH bitfield: bit0-4 = X2:6..10,
#: bit5-14 = X3:1..10.  Anything outside those maps does not exist.
_DETECTOR_ORDER: tuple[str, ...] = (
    tuple(f"X1:{i}" for i in range(1, 11))
    + tuple(f"X2:{i}" for i in range(1, 11))
    + tuple(f"X3:{i}" for i in range(1, 11))
)


def detector_bits(name: str) -> tuple[int, int]:
    """``(low_word, high_word)`` bit masks for one detector name."""
    if name not in _DETECTOR_ORDER:
        raise KeyError(f"unknown TVOC-2 detector {name!r}; valid: {_DETECTOR_ORDER}")
    i = _DETECTOR_ORDER.index(name)
    if i < 15:                       # X1:1-10 and X2:1-5
        return (1 << i, 0)
    return (0, 1 << (i - 15))        # X2:6-10 and X3:1-10


#: TVOC-2 output relays.  Trip relay bitfield bit0=K4, bit1=K5, bit2=K6.
_RELAY_BITS = {"K4": 0, "K5": 1, "K6": 2}


class ArcFlash(Fault):
    """An arc flash and the TVOC-2 trip that follows it.

    PANO GOZ does not trip.  The TVOC-2 does, in about 1 millisecond, in SIL-2
    hardware, from light plus current.  Our job starts afterwards: we observe
    the trip, name the detector and the relay, timestamp it, and escalate.

    The notification latency is a **range**, never a single clean number.  ABB
    does not document how quickly the trip appears in the Modbus register image,
    so we model 0.2-2 s for that, add our 1 s poll, the server hop and the SMS
    path, and quote 4-13 seconds end to end.

    After the trip the panel is dead: there is no LV incoming breaker
    (Madde 2.2.10.2.vi, "direk bara baglanti"), so the trip has opened the MV
    side and blacked out the whole secondary substation.
    """

    def _trip_ts(self) -> float:
        return self.start_ts + float(self.kw.get("at_s", 0.0))

    def _tripped(self, ts: float) -> bool:
        return ts >= self._trip_ts()

    def de_energised(self, ts: float) -> bool:
        return self._tripped(ts) and bool(self.kw.get("de_energise", True))

    def arc_override(self, ts: float, st: dict[str, Any]) -> None:
        if not self._tripped(ts):
            return
        det = str(self.kw.get("detector", "X2:4"))
        rel = str(self.kw.get("relay", "K4"))
        lo, hi = detector_bits(det)
        st["active_trip"] = True
        st["trip_detector_lo"] = lo
        st["trip_detector_hi"] = hi
        st["trip_relay"] = 1 << _RELAY_BITS.get(rel, 0)
        st["trip_detector_name"] = det
        st["trip_relay_name"] = rel
        st["trip_ts"] = self._trip_ts()
        # Count of trips *currently asserted*, not a running total.  The panel
        # owns the persistent counter that reg 149 mirrors; incrementing here
        # would double-count every time the register image is read.
        st["active_trips"] = st.get("active_trips", 0) + 1

    def status_hints(self, ts: float) -> list[str]:
        return ["DE_ENERGISED"] if self.de_energised(ts) else []

    def events(self, ts: float, prev_ts: float) -> list[dict[str, Any]]:
        t = self._trip_ts()
        if not (prev_ts < t <= ts):
            return []
        det = str(self.kw.get("detector", "X2:4"))
        rel = str(self.kw.get("relay", "K4"))
        return [{
            "type": "arc_trip",
            "ts": t,
            "detector": det,
            "relay": rel,
            "source": "ABB TVOC-2",
            "trip_time_ms": 1.0,
            "note_tr": (
                "TVOC-2 yaklaşık 1 ms'de açtırdı. PANO GÖZ koruma yapmaz; "
                "olayı gözler, konumlandırır, zaman damgalar ve haber verir."
            ),
            "notify_latency_s": [4.0, 13.0],
            "latency_breakdown_s": {
                "tvoc_modbus_image": [0.2, 2.0],
                "panogoz_poll": [0.0, 1.0],
                "server": [0.3, 2.0],
                "sms_path": [3.5, 8.0],
            },
        }]


class DetectorFault(Fault):
    """One arc detector fails; another reports an ambient-light warning.

    Both live in registers that exist only on firmware 03.00.00 and later
    (reg 222/223 sensor status, reg 224/225 ambient light).  And both read
    0x0000 when there is **no active error at all** - manual 4.4.2 - so a naive
    reader sees "all ten detectors failed" on a perfectly healthy relay.  The
    only safe way to read them is to gate on reg 1300, which is what the
    simulator reproduces so the gateway can be tested against it.
    """

    def arc_override(self, ts: float, st: dict[str, Any]) -> None:
        if self.elapsed_s(ts) < float(self.kw.get("at_s", 0.0)):
            return
        failed = str(self.kw.get("detector", "X2:7"))
        warn = str(self.kw.get("ambient_detector", "X2:9"))
        st["active_error"] = True
        st.setdefault("failed_detectors", [])
        if failed not in st["failed_detectors"]:
            st["failed_detectors"].append(failed)
        st.setdefault("ambient_warn_detectors", [])
        if warn not in st["ambient_warn_detectors"]:
            st["ambient_warn_detectors"].append(warn)
        st.setdefault("dtc", [])
        for code in (int(self.kw.get("dtc_detector", 4021)),
                     int(self.kw.get("dtc_ambient", 4102))):
            if code not in st["dtc"]:
                st["dtc"].append(code)

    def events(self, ts: float, prev_ts: float) -> list[dict[str, Any]]:
        t = self.start_ts + float(self.kw.get("at_s", 0.0))
        if not (prev_ts < t <= ts):
            return []
        return [{
            "type": "arc_detector_fault",
            "ts": t,
            "detector": str(self.kw.get("detector", "X2:7")),
            "ambient_detector": str(self.kw.get("ambient_detector", "X2:9")),
            "note_tr": (
                "Ark koruma bütünlüğü azaldı. Bu bir pano arızası değil, "
                "koruma sisteminin kendi arızasıdır ve ayrı raporlanır."
            ),
            "caveat": "reg 222/223 ve 224/225 yalnızca FW >= 03.00.00 sürümünde geçerlidir",
        }]


# --------------------------------------------------------------------------
# Sensor and node scenarios - these must NOT become panel faults
# --------------------------------------------------------------------------

class SensorStuck(Fault):
    """A clip freezes at its last value.

    The tell is that the reading stops moving while its two siblings continue to
    breathe with the load and the room.  A stuck sensor is a device fault and a
    suppression, never a joint alarm - and never a reassuring green tile.
    """

    def __init__(self, *a, **k) -> None:
        super().__init__(*a, **k)
        self._held: dict[tuple[str, str], float] = {}

    def sensor_value(self, device_key, joint_key, channel, value, ts):
        if device_key != self.kw.get("device_key", "TC-05"):
            return value
        key = (device_key, channel)
        if self.elapsed_s(ts) < float(self.kw.get("at_s", 0.0)):
            self._held[key] = value
            return value
        # Freeze on the first sample at or after the failure instant, so
        # ``at_s=0`` sticks immediately instead of passing values through.
        return self._held.setdefault(key, value)

    def status_hints(self, ts: float) -> list[str]:
        return ["SENSOR_STUCK"] if self.elapsed_s(ts) >= float(self.kw.get("at_s", 0.0)) else []


class SensorDrift(Fault):
    """A clip drifts linearly.

    Deliberately steeper than any real joint degradation, so that a system which
    cannot tell a sensor from a joint will confidently open a torque-wrench work
    order on a healthy lug.  The discriminator: a drifting *sensor* moves the
    joint's reading without moving its dissipation, so theta rises while the
    joint's own current and the sibling air do not, and the drift is
    load-independent - it does not shrink when the feeder unloads at 04:00.
    """

    def sensor_value(self, device_key, joint_key, channel, value, ts):
        if device_key != self.kw.get("device_key", "TC-05"):
            return value
        if channel != "tc.temp_c":
            return value
        return value + float(self.kw.get("k_per_day", 0.35)) * self.elapsed_days(ts)

    def status_hints(self, ts: float) -> list[str]:
        return ["SENSOR_DRIFT"]


class NodeSilent(Fault):
    """A node stops transmitting.

    STALE is a first-class state.  The wrong answer is to keep republishing the
    last good value, which is exactly what a conventional gateway does.
    """

    def device_silent(self, device_key: str, ts: float) -> bool:
        if device_key != self.kw.get("device_key", "TC-03"):
            return False
        return self.elapsed_s(ts) >= float(self.kw.get("at_s", 0.0))

    def status_hints(self, ts: float) -> list[str]:
        return ["STALE"] if self.elapsed_s(ts) >= float(self.kw.get("at_s", 0.0)) else []

    def events(self, ts: float, prev_ts: float) -> list[dict[str, Any]]:
        t = self.start_ts + float(self.kw.get("at_s", 0.0))
        if not (prev_ts < t <= ts):
            return []
        return [{"type": "node_silent", "ts": t,
                 "device": str(self.kw.get("device_key", "TC-03")),
                 "note_tr": "Düğüm sustu. Son değer tekrar yayınlanmaz, STALE olarak işaretlenir."}]


# --------------------------------------------------------------------------
# Negative controls - these must produce ZERO panel alarms
# --------------------------------------------------------------------------

class HeatWave(Fault):
    """Six days of +12 K ambient.

    Every absolute temperature in the panel climbs.  theta does not, because it
    is a difference between co-located siblings.  This is the single scenario
    that best separates PANO GOZ from a thermometer with a threshold.
    """

    def ambient_offset_k(self, ts: float) -> float:
        d = self.elapsed_days(ts)
        days = float(self.kw.get("days", 6.0))
        if d > days:
            return 0.0
        edge = 0.5
        w = min(1.0, d / edge, (days - d) / edge)
        return float(self.kw.get("delta_k", 12.0)) * max(0.0, w)


class GridEvent(Fault):
    """Voltage THD rises on all three phases together.

    Three phases moving as one is the signature of something upstream: a
    neighbouring industrial customer, a capacitor bank, an MV network event.
    Nothing inside this panel can raise the voltage distortion of all three
    phases equally.  Report it, attribute it upstream, do not open a work order.
    """

    def thd_v_offset_pct(self, ts: float) -> float:
        d = self.elapsed_days(ts)
        hours = float(self.kw.get("duration_h", 30.0))
        if d * 24.0 > hours:
            return 0.0
        return float(self.kw.get("thd_v_add_pct", 4.2))


class TransformerEnergisation(Fault):
    """Transformer inrush.

    Six to ten times rated current for a couple of cycles, decaying over
    roughly a second, with a deep voltage dip and heavy even-harmonic content.
    It carries no energy worth speaking of: at a 1 s poll it is one elevated
    sample.  A peak-hold rule alarms on it.  A rule that asks "how long was it
    hot" does not.
    """

    def _tau(self) -> float:
        return float(self.kw.get("decay_s", 0.55))

    def _t0(self) -> float:
        return self.start_ts + float(self.kw.get("at_s", 0.0))

    def panel_current_scale(self, ts: float) -> float:
        dt = ts - self._t0()
        if dt < 0.0 or dt > 6.0 * self._tau():
            return 1.0
        peak = float(self.kw.get("peak_multiple", 7.0))
        return 1.0 + (peak - 1.0) * math.exp(-dt / self._tau())

    def voltage_scale(self, ts: float) -> float:
        dt = ts - self._t0()
        if dt < 0.0 or dt > 6.0 * self._tau():
            return 1.0
        return 1.0 - float(self.kw.get("dip", 0.18)) * math.exp(-dt / self._tau())

    def thd_v_offset_pct(self, ts: float) -> float:
        dt = ts - self._t0()
        if dt < 0.0 or dt > 6.0 * self._tau():
            return 0.0
        return 9.0 * math.exp(-dt / self._tau())

    def events(self, ts: float, prev_ts: float) -> list[dict[str, Any]]:
        t = self._t0()
        if not (prev_ts < t <= ts):
            return []
        return [{"type": "inrush", "ts": t,
                 "peak_multiple": float(self.kw.get("peak_multiple", 7.0)),
                 "decay_s": self._tau(),
                 "note_tr": "Trafo devreye alma darbesi. Enerjisi yok, iş emri açılmaz."}]


class DeEnergised(Fault):
    """The panel goes dead.

    No current means no I^2R, which means every thermal indicator is
    meaningless - not good, meaningless.  DE_ENERGISED is a state we report, and
    it is reported separately from panel faults.  Note there is no LV incoming
    breaker at all (Madde 2.2.10.2.vi): this condition arrives from the MV side.
    """

    def de_energised(self, ts: float) -> bool:
        if self.elapsed_s(ts) < float(self.kw.get("at_s", 0.0)):
            return False
        dur = self.kw.get("duration_s")
        if dur is None:
            return True
        return self.elapsed_s(ts) <= float(self.kw.get("at_s", 0.0)) + float(dur)

    def status_hints(self, ts: float) -> list[str]:
        return ["DE_ENERGISED"] if self.de_energised(ts) else []

    def events(self, ts: float, prev_ts: float) -> list[dict[str, Any]]:
        t = self.start_ts + float(self.kw.get("at_s", 0.0))
        if not (prev_ts < t <= ts):
            return []
        return [{"type": "de_energised", "ts": t,
                 "note_tr": ("Pano enerjisiz. AG'de giriş kesicisi yoktur "
                             "(Madde 2.2.10.2.vi); kesinti OG tarafından gelmiştir. "
                             "Isıl göstergeler bu süre boyunca anlamsızdır.")}]


# --------------------------------------------------------------------------
# Registry
# --------------------------------------------------------------------------

SCENARIOS: dict[str, dict[str, Any]] = {
    # ---- must alarm ------------------------------------------------------
    "gevsek_baglanti": {
        "label_tr": "Gevşek bağlantı (yavaş)",
        "description_tr": (
            "Bir çıkış pabucu ön yükünü yavaşça kaybediyor. θ haftada ~0.2 K "
            "artıyor; günlük medyan üzerindeki CUSUM haftalar önce değişim "
            "noktasını yakalar, mutlak sıcaklık hâlâ normaldir."
        ),
        "kind": "joint_thermal",
        "expect_alarm": True,
        "expect_mode": "loose_connection",
        "forbid_modes": ("thermal_runaway", "overload"),
        "cls": LooseConnection,
        "default_kw": {"joint_key": DEFAULT_JOINT, "rate_k_per_week": 0.2,
                       "onset_days": 0.0, "cap_uohm": 600.0},
        "notes_tr": "60 günde ~1.7 K θ: alarm değil, trend ve değişim noktası gösterimi.",
    },
    "hizli_gevseme": {
        "label_tr": "Hızlı gevşeme",
        "description_tr": (
            "Aynı mekanizma, on kat hızlı: θ haftada ~2 K. Üç günlük kural ve "
            "5 K eşiği ile birkaç hafta içinde iş emri açılır."
        ),
        "kind": "joint_thermal",
        "expect_alarm": True,
        "expect_mode": "loose_connection",
        "forbid_modes": ("thermal_runaway",),
        "cls": LooseConnection,
        "default_kw": {"joint_key": DEFAULT_JOINT, "rate_k_per_week": 2.0,
                       "onset_days": 0.0, "cap_uohm": 900.0},
    },
    "notr_gevsek": {
        "label_tr": "Nötr bağlantısı gevşek",
        "description_tr": (
            "Nötr pabucunun direnci artıyor. I_N değişmiyor ama "
            "K_N = ΔT_N / I_N² kendi trendine karşı yükseliyor. İş emri: "
            "nötr bağlantısını tork anahtarı ile sık."
        ),
        "kind": "neutral",
        "expect_alarm": True,
        "expect_mode": "loose_connection",
        "forbid_modes": ("harmonic_neutral",),
        "cls": NeutralLoose,
        "default_kw": {"joint_key": DEFAULT_NEUTRAL_JOINT, "uohm_per_week": 25.0,
                       "onset_days": 0.0, "cap_uohm": 1200.0},
    },
    "harmonik_yuk": {
        "label_tr": "Harmonik yüklenme",
        "description_tr": (
            "Doğrusal olmayan yük artıyor: I_N faz akımının %50-60'ına çıkıyor, "
            "nötr barası ısınıyor, ama K_N NORMAL. Hiçbir şey gevşek değil. "
            "İş emri: harmonik ölçümü, filtre veya dengeleme."
        ),
        "kind": "neutral",
        "expect_alarm": True,
        "expect_mode": "harmonic_neutral",
        "forbid_modes": ("loose_connection",),
        "cls": HarmonicLoad,
        "default_kw": {"h3_multiplier": 4.5, "ramp_days": 3.0},
    },
    "asiri_yuk": {
        "label_tr": "Sürekli aşırı yük",
        "description_tr": (
            "Bir çıkış kendi anma akımının üzerine çıkıyor ve orada kalıyor. "
            "Bağlantılar sağlam; sorun yükün kendisi. İş emri: yük aktarımı."
        ),
        "kind": "load",
        "expect_alarm": True,
        "expect_mode": "overload",
        "forbid_modes": ("loose_connection",),
        "cls": Overload,
        "default_kw": {"feeder_index": 7, "scale": 2.6, "ramp_days": 0.5},
    },
    "havalandirma_tikali": {
        "label_tr": "Havalandırma tıkalı",
        "description_tr": (
            "Filtreler tıkanmış, kabin havası ısınıyor. BÜTÜN bağlantılar "
            "birlikte ısınıyor, bu yüzden θ DEĞİŞMİYOR. Gevşek bağlantı "
            "DEĞİLDİR; ısıl kaçış olarak sınıflanmalıdır."
        ),
        "kind": "environment",
        "expect_alarm": True,
        "expect_mode": "thermal_runaway",
        "forbid_modes": ("loose_connection",),
        "cls": BlockedVentilation,
        "default_kw": {"vent_factor": 0.32, "ramp_days": 2.0},
    },
    "yogusma": {
        "label_tr": "Yoğuşma",
        "description_tr": (
            "Şafakta nemli hava geliyor, sac hâlâ gece sıcaklığında. Tahmini "
            "yüzey sıcaklığı çiy noktasının altına düşüyor. Pano tabanı kablo "
            "kanalına tamamen açıktır (Madde 2.2.8.6 Not:2)."
        ),
        "kind": "environment",
        "expect_alarm": True,
        "expect_mode": "moisture",
        "forbid_modes": ("loose_connection",),
        "cls": Condensation,
        "default_kw": {"dewpoint_boost_k": 7.0, "start_hour": 5.2,
                       "duration_h": 2.5, "days": 3.0},
    },
    "pd_yuzen": {
        "label_tr": "Yüzen elektrot / mikro-ark",
        "description_tr": (
            "Gevşek bir bağlantıda mikro-ark. PRPD sınıfı GURULTU → YUZEY → "
            "YUZEN yürüyor, darbeler AKIM SIFIR GEÇİŞLERİNDE kümeleniyor. "
            "400 V'ta klasik PD oluşmaz (Paschen minimumu 327 V); bu kanal tek "
            "başına ekip yönlendirmez, ısıl bulguyu destekler."
        ),
        "kind": "rf",
        "expect_alarm": True,
        "expect_mode": "insulation",
        "forbid_modes": (),
        "cls": PdFloating,
        "default_kw": {"joint_key": DEFAULT_JOINT, "ramp_days": 12.0,
                       "peak_rate": 900.0, "peak_qmax_db": 30.0},
        "notes_tr": "Tek başına KRITIK üretmez; ısıl bulgu ile birleşirse seviye yükselir.",
    },
    "ark_olayi": {
        "label_tr": "Ark olayı",
        "description_tr": (
            "TVOC-2 yaklaşık 1 ms'de açtırdı. Dedektör ve röle adıyla "
            "kaydedilir. Bildirim gecikmesi 4-13 saniye ARALIĞIDIR. Açmadan "
            "sonra pano enerjisizdir: AG'de giriş kesicisi yoktur."
        ),
        "kind": "arc",
        "expect_alarm": True,
        "expect_mode": "arc_integrity",
        "forbid_modes": (),
        "expect_flags": ("DE_ENERGISED",),
        "cls": ArcFlash,
        "default_kw": {"at_s": 3600.0, "detector": "X2:4", "relay": "K4",
                       "de_energise": True},
    },
    "dedektor_arizasi": {
        "label_tr": "Ark dedektörü arızası",
        "description_tr": (
            "Bir dedektör arızalandı, bir başkası ortam ışığı uyarısı veriyor. "
            "Koruma bütünlüğü azaldı; bu bir pano arızası değildir ve ayrı "
            "raporlanır. reg 222/223 ve 224/225 yalnız FW >= 03.00.00'dedir."
        ),
        "kind": "arc",
        "expect_alarm": True,
        "expect_mode": "arc_integrity",
        "forbid_modes": ("loose_connection",),
        "cls": DetectorFault,
        "default_kw": {"detector": "X2:7", "ambient_detector": "X2:9", "at_s": 600.0},
    },
    # ---- sensor / node: device faults, NOT panel faults -------------------
    "sensor_takildi": {
        "label_tr": "Sensör takıldı",
        "description_tr": (
            "Bir kelepçe son değerinde donmuş. Aynı çıkışın diğer fazları yükle ve odayla "
            "birlikte nefes almaya devam ediyor. Cihaz arızası olarak "
            "raporlanır; pano alarmı üretilmez ve yeşil kutucuk gösterilmez."
        ),
        "kind": "sensor",
        "expect_alarm": False,
        "expect_mode": None,
        "forbid_modes": ("loose_connection", "thermal_runaway"),
        "expect_flags": ("STALE",),
        "cls": SensorStuck,
        "default_kw": {"device_key": "TC-05", "at_s": 3600.0},
    },
    "sensor_kaydi": {
        "label_tr": "Sensör kayması",
        "description_tr": (
            "Bir kelepçe günde 0.35 K doğrusal kayıyor. SENSÖRE atfedilmelidir, "
            "bağlantıya değil: kayma yüke bağlı değildir, gece yük düştüğünde "
            "küçülmez ve akım ile θ arasındaki ilişki bozulur."
        ),
        "kind": "sensor",
        "expect_alarm": False,
        "expect_mode": None,
        "forbid_modes": ("loose_connection",),
        "expect_flags": ("SENSOR_DRIFT",),
        "cls": SensorDrift,
        "default_kw": {"device_key": "TC-05", "k_per_day": 0.35},
    },
    "dugum_sessiz": {
        "label_tr": "Düğüm sessiz",
        "description_tr": (
            "Bir düğüm yayın yapmıyor. Son iyi değer tekrar yayınlanmaz; "
            "STALE ilan edilir ve o bağlantı için körüz denir."
        ),
        "kind": "node",
        "expect_alarm": False,
        "expect_mode": None,
        "forbid_modes": ("loose_connection", "thermal_runaway"),
        "expect_flags": ("STALE",),
        "cls": NodeSilent,
        "default_kw": {"device_key": "TC-03", "at_s": 1800.0},
    },
    # ---- negative controls: ZERO panel alarms ----------------------------
    "sicak_hava_dalgasi": {
        "label_tr": "Sıcak hava dalgası (negatif kontrol)",
        "description_tr": (
            "Altı gün boyunca ortam +12 K. Panodaki her mutlak sıcaklık "
            "yükselir, θ YÜKSELMEZ. Eşikli bir termometre burada alarm verir; "
            "PANO GÖZ vermez."
        ),
        "kind": "negative",
        "expect_alarm": False,
        "expect_mode": None,
        "forbid_modes": ("loose_connection", "thermal_runaway"),
        "cls": HeatWave,
        "default_kw": {"delta_k": 12.0, "days": 6.0},
    },
    "sebeke_olayi": {
        "label_tr": "Şebeke olayı (negatif kontrol)",
        "description_tr": (
            "Gerilim THD'si ÜÇ FAZDA BİRDEN yükseliyor. Bu panonun içinde üç "
            "fazı birden eşit bozacak bir şey yoktur; kaynak yukarı akıştadır. "
            "Kaydedilir, yukarı akışa atfedilir, iş emri açılmaz."
        ),
        "kind": "negative",
        "expect_alarm": False,
        "expect_mode": None,
        "forbid_modes": ("loose_connection", "harmonic_neutral"),
        "cls": GridEvent,
        "default_kw": {"thd_v_add_pct": 4.2, "duration_h": 30.0},
    },
    "trafo_devreye_alma": {
        "label_tr": "Trafo devreye alma (negatif kontrol)",
        "description_tr": (
            "Devreye alma darbesi: birkaç periyot boyunca 7 katı akım, derin "
            "gerilim çökmesi, saniyenin altında sönüm. Tepe tutan bir kural "
            "alarm verir; 'ne kadar süre sıcak kaldı' diye soran kural vermez."
        ),
        "kind": "negative",
        "expect_alarm": False,
        "expect_mode": None,
        "forbid_modes": ("overload", "loose_connection"),
        "cls": TransformerEnergisation,
        "default_kw": {"at_s": 1800.0, "peak_multiple": 7.0, "decay_s": 0.55,
                       "dip": 0.18},
    },
    "pano_enerjisiz": {
        "label_tr": "Pano enerjisiz (negatif kontrol)",
        "description_tr": (
            "Akım yok. Hiçbir ısıl gösterge anlamlı değildir - iyi değil, "
            "ANLAMSIZ. DE_ENERGISED durumu ayrı raporlanır, alarm üretilmez."
        ),
        "kind": "negative",
        "expect_alarm": False,
        "expect_mode": None,
        "forbid_modes": ("loose_connection", "thermal_runaway", "overload"),
        "expect_flags": ("DE_ENERGISED",),
        "cls": DeEnergised,
        "default_kw": {"at_s": 600.0, "duration_s": 4.0 * 3600.0},
    },
}


def make_fault(name: str, start_ts: float, seed: int = 0, **kw) -> Fault:
    """Instantiate a scenario with its defaults, overridden by ``kw``."""
    try:
        spec = SCENARIOS[name]
    except KeyError as exc:  # pragma: no cover - programmer error
        raise KeyError(
            f"unknown scenario {name!r}; valid: {sorted(SCENARIOS)}"
        ) from exc
    merged = dict(spec["default_kw"])
    merged.update(kw)
    return spec["cls"](name=name, start_ts=start_ts, kw=merged, seed=seed)


def scenario_names(kind: str | None = None) -> list[str]:
    if kind is None:
        return sorted(SCENARIOS)
    return sorted(k for k, v in SCENARIOS.items() if v["kind"] == kind)


NEGATIVE_CONTROLS: tuple[str, ...] = tuple(
    k for k, v in SCENARIOS.items() if not v["expect_alarm"]
)
ALARMING: tuple[str, ...] = tuple(k for k, v in SCENARIOS.items() if v["expect_alarm"])


# --------------------------------------------------------------------------
# Consistency checks - these run at import time on purpose
# --------------------------------------------------------------------------

_VALID_MODES = {m.key for m in channels.FAILURE_MODES}
for _name, _spec in SCENARIOS.items():
    assert set(_spec) >= {"label_tr", "description_tr", "kind", "expect_alarm",
                          "default_kw", "cls"}, _name
    _m = _spec.get("expect_mode")
    assert _m is None or _m in _VALID_MODES, f"{_name}: unknown mode {_m}"
    for _f in _spec.get("forbid_modes", ()):
        assert _f in _VALID_MODES, f"{_name}: unknown forbidden mode {_f}"
    if _m is not None:
        assert _spec["expect_alarm"], f"{_name}: expect_mode without expect_alarm"
del _name, _spec, _m


if __name__ == "__main__":  # pragma: no cover
    print("PANO GOZ · fault scenarios")
    print("=" * 92)
    print(f"{len(SCENARIOS)} scenarios · {len(ALARMING)} must alarm · "
          f"{len(NEGATIVE_CONTROLS)} must stay silent")
    print()
    for kind in ("joint_thermal", "neutral", "load", "environment", "rf", "arc",
                 "sensor", "node", "negative"):
        names = scenario_names(kind)
        if not names:
            continue
        print(f"--- {kind} " + "-" * (86 - len(kind)))
        for n in names:
            s = SCENARIOS[n]
            flag = "ALARM" if s["expect_alarm"] else "SESSIZ"
            mode = s.get("expect_mode") or "-"
            print(f"  {n:<22} {flag:<7} mode={mode:<18} {s['label_tr']}")
        print()

    print("Conversion of the two loose-connection rates")
    j = assets.JOINTS_BY_KEY[DEFAULT_JOINT]
    for r in (0.2, 2.0):
        u = uohm_per_week_for(r, assets.reference_current(j))
        print(f"  {r:>4.1f} K/week at I_ref={assets.reference_current(j):.0f} A"
              f"  ->  {u:6.3f} uohm/week   (8 weeks: {8*u:6.2f} uohm, theta {8*r:5.2f} K)")

    print("\nTVOC-2 detector bit maps (LOW: X1:1-10 + X2:1-5, HIGH: X2:6-10 + X3:1-10)")
    for d in ("X1:1", "X1:10", "X2:1", "X2:5", "X2:6", "X2:10", "X3:1", "X3:10"):
        lo, hi = detector_bits(d)
        print(f"  {d:<6} low=0x{lo:04X}  high=0x{hi:04X}")

    print("\nHook smoke test")
    t0 = 1_767_225_600.0  # 2026-01-01T00:00:00Z
    jt = assets.JOINTS_BY_KEY[DEFAULT_JOINT]
    f = make_fault("gevsek_baglanti", t0)
    for d in (0, 14, 28, 56):
        print(f"  gevsek_baglanti  gun {d:>3}: +{f.d_r_joint_uohm(jt, t0 + d*86400):.3f} uohm")
    f = make_fault("hizli_gevseme", t0)
    for d in (0, 7, 21):
        print(f"  hizli_gevseme    gun {d:>3}: +{f.d_r_joint_uohm(jt, t0 + d*86400):.3f} uohm")
    f = make_fault("havalandirma_tikali", t0)
    print(f"  havalandirma     gun   4: vent={f.vent_factor(t0 + 4*86400):.2f}")
    f = make_fault("sicak_hava_dalgasi", t0)
    print("  sicak_hava       " + " ".join(
        f"g{d}:{f.ambient_offset_k(t0 + d*86400):+.1f}K" for d in (0, 1, 3, 6, 7)))
    f = make_fault("trafo_devreye_alma", t0)
    print("  trafo inrush     " + " ".join(
        f"{dt:.1f}s:{f.panel_current_scale(t0 + 1800 + dt):.2f}x"
        for dt in (0.0, 0.3, 1.0, 2.0, 4.0)))
    f = make_fault("ark_olayi", t0)
    st: dict[str, Any] = {}
    f.arc_override(t0 + 7200, st)
    print(f"  ark_olayi        {st['trip_detector_name']} / {st['trip_relay_name']}"
          f"  lo=0x{st['trip_detector_lo']:04X} hi=0x{st['trip_detector_hi']:04X}"
          f" relay=0x{st['trip_relay']:04X}")
    ev = f.events(t0 + 3601, t0 + 3599)
    print(f"  latency          {ev[0]['notify_latency_s']} s  (never a single number)")
    f = make_fault("pd_yuzen", t0)
    base = {"rate_per_s": 6.0, "qmax_db": 11.0, "nqn": 18.0, "tev_db": 8.0,
            "ultrasonic_db": 5.0, "klass": "GURULTU"}
    for d in (1, 4, 8, 14):
        o = f.pd_override(t0 + d * 86400, base)
        print(f"  pd_yuzen gun {d:>2}: rate={o['rate_per_s']:6.0f}/s"
              f" qmax={o['qmax_db']:5.1f} dB  sinif={o['klass']:<8}"
              f" kume={o['phase_clusters_deg']} deg (akim sifiri)")
