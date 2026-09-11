"""The live panel image.

This is the one shape that the detector produces and that the REST API, the
web UI and the Modbus slave all consume.  Fixing it here means the number on
the operator's screen and the number in register `THETA_MAX` come from the same
object, and cannot disagree.

Everything is plain dataclasses with ``to_dict``.  No ORM, no serialiser
library: the payload is small, the shape is stable, and a judge who opens
``/api/panel/Soke-14`` should be able to read it without documentation.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field, asdict
from typing import Any

from panogoz.contracts import channels, icd


@dataclass
class JointView:
    key: str
    label: str
    zone: str
    conductor: str
    feeder_index: int | None
    rated_a: float
    monitored: bool
    x_mm: float = 0.0
    y_mm: float = 0.0

    # measurement
    temp_c: float | None = None
    sibling_median_c: float | None = None
    current_a: float | None = None
    load_factor: float = 0.0

    # theta and its interpretation
    theta_k: float | None = None
    theta_min_k: float | None = None
    sensitivity_pct: float = 0.0
    baseline_k: float | None = None
    #: Rise of theta above this joint's OWN commissioned baseline.
    #:
    #: Absolute theta and this rise answer two different questions and both
    #: matter.  A bolted joint has a manufacturing offset against its siblings:
    #: a lug that has sat 12 K above its phase mates since the day it was made
    #: is a genuinely defective crimp, and absolute theta is the number an IR
    #: thermographer would write down.  A lug drifting +0.2 K per week is not
    #: yet hot at all, and only the rise sees it.  Severity takes the worse of
    #: the two verdicts, so the system catches both the joint that was born bad
    #: and the joint that is going bad.
    #:
    #: The rise is also detectable far below the single-sample noise floor,
    #: because it is judged on daily medians (noise falls as 1/sqrt(n)) with a
    #: CUSUM confirmation, whereas absolute theta must clear theta_min.
    theta_rise_k: float | None = None
    #: Excess contact resistance, reported as an interval because R_th,local for
    #: a lug is only known to 2-4 K/W.  Never presented as an exact number.
    excess_r_uohm: float | None = None
    excess_r_lo_uohm: float | None = None
    excess_r_hi_uohm: float | None = None

    # drift
    cusum: float = 0.0
    slope_k_per_week: float = 0.0
    changepoint_ts: float | None = None
    alarm_days: int = 0

    # None means no detector verdict; fusion may then grade a manual snapshot.
    # BILGI is an explicit, authoritative decision, not a missing value.
    severity: str | None = None
    note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DeviceView:
    key: str
    kind: str
    label: str
    mount: str = ""
    online: bool = False
    last_seen: float | None = None
    rssi_dbm: float | None = None
    battery_pct: float | None = None
    battery_v: float | None = None
    #: Interval this device says it publishes at, in seconds.  None means the
    #: device never declared one and the server's fixed floors apply.
    period_s: float | None = None
    fw: str = ""
    faults: list[str] = field(default_factory=list)
    x_mm: float = 0.0
    y_mm: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ArcView:
    """State of the panel's arc protection, as read from an ABB TVOC-2.

    ``fitted`` is separate from ``online``: a panel with no TVOC-2 at all must
    look different from one whose relay we have lost contact with.  Collapsing
    those two into a single "no data" is how a monitoring system convinces an
    operator that unprotected switchgear is protected.
    """

    fitted: bool = False
    online: bool = False
    active_trip: bool = False
    active_error: bool = False
    start_sequence: bool = False
    diagnostics_running: bool = False
    detectors_ok: int = 0
    detectors_total: int = 0
    ambient_warn: int = 0
    ambient_warn_list: list[str] = field(default_factory=list)
    fault_list: list[str] = field(default_factory=list)
    detector_map_lo: int = 0
    detector_map_hi: int = 0
    last_trip: dict[str, Any] | None = None
    last_selftest_ts: float | None = None
    last_selftest_days: int = 9999
    selftest_enabled: bool = False
    firmware: str = ""
    #: Honest statement of what we can and cannot do, shown in the UI.
    caveat: str = (
        "PANO GÖZ koruma yapmaz. Açma, TVOC-2 donanımında yaklaşık 1 ms'de "
        "gerçekleşir (SIL-2). Biz gözlemler, konumlandırır, zaman damgalar ve "
        "haber veririz."
    )

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PdView:
    rate_per_s: float = 0.0
    qmax_db: float = 0.0
    nqn: float = 0.0
    tev_db: float = 0.0
    ultrasonic_db: float = 0.0
    klass: str = "GURULTU"
    klass_label: str = "Gürültü"
    features: dict[str, float] = field(default_factory=dict)
    trend_db_30d: float = 0.0
    hist_b64: str = ""
    caveat: str = (
        "400 V'ta klasik kısmi deşarj oluşmaz (Paschen minimumu 327 V). Bu kanal "
        "gevşek bağlantı mikro-arkını ölçer. Değer pC eşdeğeridir, IEC 60270 "
        "izlenebilir DEĞİLDİR; AG tarafında tek başına ekip yönlendirmez."
    )

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AlarmView:
    id: int
    panel_key: str
    joint_key: str | None
    mode: str
    mode_label: str
    severity: str
    state: str
    title: str
    opened_at: float
    updated_at: float
    acked_at: float | None = None
    acked_by: str | None = None
    action: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)
    ruled_out: list[str] = field(default_factory=list)
    dispatched: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SuppressionView:
    ts: float
    panel_key: str
    joint_key: str | None
    mode: str | None
    reason: str
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PanelLive:
    """Everything about one panel at one instant."""

    panel_key: str
    panel_index: int
    site: str
    name: str
    dso: str = ""
    lat: float = 0.0
    lon: float = 0.0

    ts: float = field(default_factory=time.time)
    data_age_s: float = 0.0

    health_index: float = 100.0
    severity: str = "BILGI"
    status_flags: list[str] = field(default_factory=list)

    risks: dict[str, float] = field(default_factory=dict)
    #: Exact decomposition of the health-index deficit.  Because
    #: HI = 100 * prod (1-r_m)^w_m, ln(HI/100) = sum w_m ln(1-r_m), so the
    #: contributions add up with no attribution heuristic.
    hi_waterfall: list[dict[str, Any]] = field(default_factory=list)

    theta_max: float = 0.0
    theta_max_joint: str | None = None
    theta_delta_7d: float = 0.0
    sensitivity_pct: float = 0.0
    # Mean main-busbar phase current / main-busbar rating.
    load_factor: float = 0.0
    # Estimated feeder loading, on the sum-of-feeder-ratings scale. None is
    # reserved for legacy/manual snapshots that do not carry this estimate.
    feeder_load_factor: float | None = None

    env: dict[str, float] = field(default_factory=dict)
    analyser: dict[str, float] = field(default_factory=dict)
    analyser_fitted: bool = True
    analyser_online: bool = False

    arc: ArcView = field(default_factory=ArcView)
    pd: PdView = field(default_factory=PdView)

    joints: list[JointView] = field(default_factory=list)
    devices: list[DeviceView] = field(default_factory=list)
    alarms: list[AlarmView] = field(default_factory=list)
    suppressed: list[SuppressionView] = field(default_factory=list)

    learn_mode: bool = False
    learn_until: float | None = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["severity_label"] = channels.SEVERITY_TR.get(self.severity, self.severity)
        d["severity_rank"] = channels.SEVERITY_RANK.get(self.severity, 0)
        return d

    # ---------------------------------------------------------------- ICD --

    def status_word(self) -> int:
        return icd.pack_bits(icd.STATUS_BITS, set(self.status_flags))

    def arc_word(self) -> int:
        flags: set[str] = set()
        a = self.arc
        if not a.fitted:
            flags.add("NOT_FITTED")
        if a.active_trip:
            flags.add("ACTIVE_TRIP")
        if a.active_error:
            flags.add("ACTIVE_ERROR")
        if a.start_sequence:
            flags.add("START_SEQUENCE")
        if a.diagnostics_running:
            flags.add("DIAGNOSTICS_RUNNING")
        if a.fitted and a.detectors_ok < a.detectors_total:
            flags.add("DETECTOR_FAULT")
        if a.ambient_warn:
            flags.add("AMBIENT_WARNING")
        if a.fitted and not a.online:
            flags.add("COMMS_LOST")
        if not a.selftest_enabled:
            flags.add("SELFTEST_DISABLED")
        return icd.pack_bits(icd.ARC_BITS, flags)

    def device_fault_word(self) -> int:
        order = ("TC-01", "TC-02", "TC-03", "TC-04", "TC-05", "TC-06", "TN-IR", "PD-01", "GW-01")
        by_key = {d.key: d for d in self.devices}
        word = 0
        for i, k in enumerate(order):
            d = by_key.get(k)
            if d is None or not d.online or d.faults:
                word |= 1 << i
        return word

    def theta_max_joint_index(self, joint_order: list[str]) -> int:
        if self.theta_max_joint is None:
            return 0
        try:
            return joint_order.index(self.theta_max_joint)
        except ValueError:
            return 0

    def to_registers(self, joint_order: list[str]) -> list[int]:
        """Encode into the ``REGS_PER_PANEL``-word block defined by the ICD."""
        words = [0] * icd.REGS_PER_PANEL
        R = icd.PANEL_BY_NAME

        def put(name: str, value: float | int | None) -> None:
            reg = R[name]
            enc = icd.encode(reg, value)
            for i, w in enumerate(enc):
                words[reg.offset + i] = w

        an = self.analyser
        put("PANEL_ID", self.panel_index)
        put("HEALTH_INDEX", round(self.health_index))
        put("SEVERITY", channels.SEVERITY_RANK.get(self.severity, 0))
        put("STATUS_WORD", self.status_word())
        put("ACTIVE_ALARMS", len(self.alarms))
        put("THETA_MAX", self.theta_max)
        put("THETA_MAX_JOINT", self.theta_max_joint_index(joint_order))
        put("THETA_SLOPE", self._worst_slope())
        put("SENSITIVITY_PCT", self.sensitivity_pct)
        for mode, reg in (
            ("loose_connection", "RISK_LOOSE"),
            ("overload", "RISK_OVERLOAD"),
            ("arc_integrity", "RISK_ARC_INTEGRITY"),
            ("thermal_runaway", "RISK_THERMAL"),
            ("harmonic_neutral", "RISK_HARMONIC"),
            ("moisture", "RISK_MOISTURE"),
            ("insulation", "RISK_INSULATION"),
        ):
            put(reg, 100.0 * self.risks.get(mode, 0.0))
        put("T_JOINT_MAX", max((j.temp_c for j in self.joints if j.temp_c is not None), default=0.0))
        put("T_AIR", self.env.get("env.air_c"))
        put("RH", self.env.get("env.rh_pct"))
        put("DEWPOINT_MARGIN", self.env.get("env.condensation_margin_k"))
        put("I_L1", an.get("mpr.i_l1_a"))
        put("I_L2", an.get("mpr.i_l2_a"))
        put("I_L3", an.get("mpr.i_l3_a"))
        put("I_N", an.get("mpr.i_n_a"))
        put("V_L1", an.get("mpr.v_l1_v"))
        put("V_L2", an.get("mpr.v_l2_v"))
        put("V_L3", an.get("mpr.v_l3_v"))
        put("FREQ", an.get("mpr.freq_hz"))
        put("THD_V_MAX", max((an.get(f"mpr.thd_v_l{p}_pct", 0.0) or 0.0) for p in (1, 2, 3)))
        put("THD_I_MAX", max((an.get(f"mpr.thd_i_l{p}_pct", 0.0) or 0.0) for p in (1, 2, 3)))
        put("LOAD_FACTOR", 100.0 * self.load_factor)
        put("PD_RATE", self.pd.rate_per_s)
        put("PD_QMAX", self.pd.qmax_db)
        put("PD_CLASS", channels.PRPD_CLASSES.index(self.pd.klass) if self.pd.klass in channels.PRPD_CLASSES else 0)
        put("TEV_LEVEL", self.pd.tev_db)
        put("ARC_STATE", self.arc_word())
        put("ARC_DETECTORS_OK", self.arc.detectors_ok)
        put("ARC_DETECTORS_TOTAL", self.arc.detectors_total)
        put("ARC_AMBIENT_WARN", self.arc.ambient_warn)
        put("ARC_DETECTOR_MAP_LO", self.arc.detector_map_lo)
        put("ARC_DETECTOR_MAP_HI", self.arc.detector_map_hi)
        put("ARC_LAST_SELFTEST_D", min(self.arc.last_selftest_days, 65535))
        put("DEVICES_ONLINE", sum(1 for d in self.devices if d.online))
        put("DEVICE_FAULT_MAP", self.device_fault_word())
        put("DATA_AGE_S", min(self.data_age_s, 65535))
        put("UPDATED_AT", self.ts)
        return words

    def _worst_slope(self) -> float:
        if self.theta_max_joint:
            for j in self.joints:
                if j.key == self.theta_max_joint:
                    return j.slope_k_per_week
        return 0.0


@dataclass
class FleetLive:
    ts: float = field(default_factory=time.time)
    panels: list[PanelLive] = field(default_factory=list)
    heartbeat: int = 0
    engine_flags: list[str] = field(default_factory=list)
    detector_lag_s: float = 0.0
    dispatch_queue: int = 0
    suppressed_24h: int = 0

    def global_registers(self) -> list[int]:
        words = [0] * icd.GLOBAL_SIZE
        G = icd.GLOBAL_BY_NAME

        def put(name: str, value: float | int | None) -> None:
            reg = G[name]
            for i, w in enumerate(icd.encode(reg, value)):
                words[reg.offset + i] = w

        online = [p for p in self.panels if "GATEWAY_COMMS_LOST" not in p.status_flags]
        healths = [p.health_index for p in self.panels] or [100.0]
        sev = max((channels.SEVERITY_RANK.get(p.severity, 0) for p in self.panels), default=0)
        alarms = sum(len(p.alarms) for p in self.panels)
        crit = sum(
            1
            for p in self.panels
            for a in p.alarms
            if a.severity in channels.DISPATCH_SEVERITIES
        )
        put("ICD_VERSION", icd.ICD_VERSION_ENCODED)
        put("PANEL_COUNT", len(self.panels))
        put("PANELS_ONLINE", len(online))
        put("FLEET_WORST_SEVERITY", sev)
        put("FLEET_ALARMS_ACTIVE", alarms)
        put("FLEET_ALARMS_CRITICAL", crit)
        put("WATCHDOG_HEARTBEAT", self.heartbeat % 65536)
        put("SERVER_TIME", self.ts)
        put("ENGINE_STATE", icd.pack_bits(icd.ENGINE_BITS, set(self.engine_flags)))
        put("DETECTOR_LAG_S", self.detector_lag_s)
        put("REGS_PER_PANEL", icd.REGS_PER_PANEL)
        put("PANEL_BLOCK_BASE", icd.PANEL_BASE)
        put("FLEET_HEALTH_MIN", min(healths))
        put("FLEET_HEALTH_MEAN", sum(healths) / len(healths))
        put("DISPATCH_QUEUE", self.dispatch_queue)
        put("SUPPRESSED_24H", self.suppressed_24h)
        put("PANELS_SENSITIVITY_LOW", sum(1 for p in self.panels if "SENSITIVITY_LOW" in p.status_flags))
        return words

    def to_dict(self) -> dict:
        return {
            "ts": self.ts,
            "heartbeat": self.heartbeat,
            "detector_lag_s": self.detector_lag_s,
            "engine_flags": self.engine_flags,
            "dispatch_queue": self.dispatch_queue,
            "suppressed_24h": self.suppressed_24h,
            "panels": [p.to_dict() for p in self.panels],
        }
