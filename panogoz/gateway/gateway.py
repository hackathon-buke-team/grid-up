"""The panel gateway: DIN rail, instrument bay, fed from the existing 10 A socket.

The gateway is the only thing in the panel with mains power and a WAN radio.  It
masters the two RS-485 segments (see :mod:`panogoz.gateway.poller`), receives the
sub-GHz frames from the eight battery nodes, and is the last point in the chain
that still works when everything north of it has failed.

Four jobs, in order of how much they matter at 03:00
-----------------------------------------------------

1. **Local critical rules.**  An arc trip, a lug at 90 C, a 20 K sibling
   difference on a loaded feeder - these fire a local dry contact and a local
   annunciator whether or not the WAN, the broker, the server or the SMS
   provider are alive.  A monitoring system whose critical path runs through
   somebody else's cloud is a monitoring system that is off the air whenever the
   storm that caused the fault also took out the base station.

2. **Store and forward.**  Every envelope goes into a bounded ring first and is
   only retired from it when the transport confirms the publish.  The ring is
   bounded on purpose: an unbounded buffer on a DIN-rail box with 256 MB of RAM
   is a delayed crash, not durability.  When it overflows we drop the oldest and
   count the drop, and the count is published.

3. **Self-describing birth messages.**  Each device announces the exact channel
   list it will ever send.  The server needs no prior configuration for a new
   panel, and a metric that arrives without having been declared is a bug we can
   see rather than a column that silently appears.

4. **Monotonic sequence plus a boot counter.**  ``seq`` increments per device;
   ``boot`` increments on every power-up.  Together they make a gap detectable
   and distinguish a lost message from a reboot.  The panel's 6 A gG "Ic Ihtiyac"
   fuse does blow, and gateways do restart.

Why not Sparkplug B
-------------------

Sparkplug is the obvious answer and it is the wrong one here.  Sparkplug 3.0
**mandates QoS 0 for DDATA**.  Our durability guarantee is a PUBACK-driven
store-and-forward watermark - the ring only advances when the broker acknowledges
the message - and PUBACK does not exist at QoS 0.  Building the guarantee on a
mechanism the specification forbids would be dishonest, so we keep the four
Sparkplug ideas that earn their keep (birth, will, per-device sequence,
death/rebirth) in about forty lines of :mod:`panogoz.contracts.envelope`, and we
keep QoS 1.

What this module is NOT
-----------------------

It is not protection.  The ABB TVOC-2 clears an arc in about 1 ms in SIL-2
hardware with no software in the loop, and it does that whether or not this
gateway has ever been installed.  The local rules here shorten a *notification*,
never a trip.  Notification latency is a range - 4 to 13 seconds - and the
module publishes it as a range.
"""

from __future__ import annotations

import statistics
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Sequence

from panogoz.contracts import assets, channels as ch
from panogoz.contracts.envelope import Envelope, birth as make_birth, death as make_death

# --------------------------------------------------------------------------
# Local critical thresholds
# --------------------------------------------------------------------------

#: Absolute lug temperature that fires locally regardless of load or siblings.
#: PVC-insulated LV cable is rated 70 C at the conductor.  A lug body sitting at
#: 90 C means the insulation immediately behind the crimp is already past its
#: rating, so this is not an early warning - it is "go now", and it must not
#: depend on a baseline, a peer or a server.
LOCAL_ABS_TEMP_C = 90.0

#: Raw difference against the sibling median.  IR thermography practice treats a
#: delta-T of 15 K over a similar component under similar load as "major
#: discrepancy, repair immediately".  We use 20 K raw - deliberately more
#: conservative than the theta detector on the server, because the gateway has
#: no history, no baseline and no ability to rule out a sensor fault.
LOCAL_DELTA_K = 20.0

#: Below this load factor theta noise dominates and the gateway says so rather
#: than firing.  theta_min(f) = 3 sigma / f^2, so at f = 0.35 an IR pixel pair
#: cannot resolve less than about 20 K anyway.
LOCAL_MIN_LOAD_FACTOR = 0.35

#: Ring size.  20000 envelopes at roughly 400 bytes is about 8 MB, and at one
#: envelope per device per minute that is roughly 36 hours of outage for a
#: nine-device panel.  Long enough to ride out a base-station failure, small
#: enough to fit in a DIN-rail box.
DEFAULT_BUFFER = 20000

#: Published with every birth so the honesty claim travels with the data.
LATENCY_NOTE_TR = (
    "Bildirim gecikmesi 4-13 saniye ARALIĞINDADIR: TVOC-2 Modbus görüntüsünün "
    "yayılması (ABB dokümante etmiyor, 0.2-2 s modellendi) + 1 s tarama + sunucu "
    "+ SMS yolu. Açmanın kendisi ~1 ms'de donanımda olur ve PANO GÖZ'ü beklemez."
)


# --------------------------------------------------------------------------
# Device / channel routing
# --------------------------------------------------------------------------

#: Which device owns which panel-level channel prefix.  Per-joint channels are
#: routed by coverage instead - see :meth:`Gateway._joint_owner`.
PREFIX_OWNER: tuple[tuple[str, str], ...] = (
    ("tc.", ""),          # per-joint, resolved by coverage
    ("ir.", "TN-IR"),
    ("pd.", "PD-01"),
    ("env.", "PD-01"),
    ("mpr.", "GW-01"),
    ("tvoc.", "GW-01"),
    ("det.", "GW-01"),
)

#: Channels every battery node reports about itself.
NODE_HEALTH = ("dev.rssi_dbm", "dev.battery_v", "dev.battery_pct",
               "dev.temp_mcu_c", "dev.uptime_s", "dev.seq", "dev.period_s")


def device_metrics(device_key: str) -> list[str]:
    """The exact channel list a device declares in its birth message."""
    kind = assets.DEVICES_BY_KEY[device_key].kind
    if kind == "TC":
        own = ["tc.temp_c", "tc.current_a"]
    elif kind == "TN-IR":
        own = ["ir.lug_temp_c", "ir.air_top_c", "ir.aim_ok"]
    elif kind == "PD":
        own = ["pd.rate_per_s", "pd.qmax_db", "pd.nqn", "pd.class", "pd.tev_db",
               "pd.ultrasonic_db", "env.air_c", "env.rh_pct", "env.dewpoint_c",
               "env.wall_c", "env.condensation_margin_k"]
    else:  # GW
        own = [c.name for c in ch.CHANNELS
               if c.name.startswith(("mpr.", "tvoc."))] + ["dev.uptime_s", "dev.seq",
                                                            "dev.period_s"]
        return own
    return own + list(NODE_HEALTH)


# --------------------------------------------------------------------------
# Simulator output normalisation
# --------------------------------------------------------------------------

@dataclass
class GatewayFrame:
    """What the gateway actually publishes, whatever shape it arrived in.

    The panel simulator lives in another module and is built by another hand, so
    we duck-type its output rather than importing a class we do not own.  Any
    object or mapping carrying ``ts``, ``values``, ``joints`` and ``events``
    works, and anything missing is absent rather than invented.
    """

    ts: float
    values: dict[str, float] = field(default_factory=dict)
    joints: dict[str, dict[str, float]] = field(default_factory=dict)
    events: list[dict] = field(default_factory=list)
    devices: dict[str, dict[str, float]] = field(default_factory=dict)
    arc: dict = field(default_factory=dict)


def _get(obj: Any, name: str, default: Any) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        val = obj.get(name, default)
    else:
        val = getattr(obj, name, default)
    return default if val is None else val


def normalise(out: Any, ts: float | None = None) -> GatewayFrame:
    """Coerce whatever the simulator produced into a :class:`GatewayFrame`."""
    if isinstance(out, GatewayFrame):
        return out
    frame_ts = _get(out, "ts", None)
    if frame_ts is None:
        frame_ts = time.time() if ts is None else ts
    return GatewayFrame(
        ts=float(frame_ts),
        values=dict(_get(out, "values", {}) or {}),
        joints={k: dict(v) for k, v in (_get(out, "joints", {}) or {}).items()},
        events=list(_get(out, "events", []) or []),
        devices={k: dict(v) for k, v in (_get(out, "devices", {}) or {}).items()},
        arc=dict(_get(out, "arc", {}) or {}),
    )


# --------------------------------------------------------------------------
# Gateway
# --------------------------------------------------------------------------

class Gateway:
    """One gateway for one panel."""

    def __init__(
        self,
        *,
        panel_key: str,
        site: str,
        sim: Any = None,
        bus: Any = None,
        poller: Any = None,
        store: Any = None,
        outbox_store: Any = None,
        buffer_size: int = DEFAULT_BUFFER,
        boot: int | None = None,
        fw: str = "panogoz-gw 1.0.0",
        period_s: float = ch.CADENCE_PERIOD_S["IDLE"],
        on_local_alarm: Callable[[dict], None] | None = None,
    ) -> None:
        self.panel_key = panel_key
        self.site = site
        self.sim = sim
        self.bus = bus
        self.poller = poller
        self.store = store
        self.fw = fw
        #: The interval this panel's devices are currently being published at.
        #:
        #: It is a declaration, not a wish: the server derives every freshness
        #: window from it, so a gateway that says 900 s and then goes quiet for
        #: 45 minutes is believed for 45 minutes.  Whoever drives ``publish``
        #: owns this number and must keep it honest - see :meth:`set_period`.
        self.period_s = float(period_s)
        self.on_local_alarm = on_local_alarm

        #: Persisted across restarts in the field (a counter in flash).  Here it
        #: is explicit so a test can pin it.
        self.boot = int(time.time()) % 65536 if boot is None else int(boot)
        self._seq: dict[str, int] = {}

        self.buffer: deque[Envelope] = deque(maxlen=int(buffer_size))
        self._buffer_lock = threading.RLock()
        self._retains: deque[bool] = deque()
        self._row_ids: deque[int | None] = deque()
        self._receipt: Any = None
        self.outbox_store: Any = None
        self.buffer_size = int(buffer_size)
        self.online = True
        self.published = 0
        self.buffered = 0
        self.dropped = 0
        self.drains = 0
        self.publish_failures = 0

        self.born = False
        self.cycles = 0
        self.local_alarms: list[dict] = []
        self._local_active: dict[str, dict] = {}
        self.last_frame: GatewayFrame | None = None
        self._started_at = time.time()
        if outbox_store is not None:
            self.attach_outbox(outbox_store)

    def attach_outbox(self, store: Any) -> None:
        """Restore unacknowledged messages before accepting new live traffic."""
        with self._buffer_lock:
            if self.outbox_store is store:
                return
            if self.buffer:
                raise RuntimeError("Attach persistent outbox before publishing")
            rows = store.outbox_rows(self.panel_key)
            if len(rows) > self.buffer_size:
                raise BufferError("Configured outbox capacity is smaller than pending queue")
            self.outbox_store = store
            self.boot = store.next_gateway_boot(self.panel_key, self.boot)
            self._seq.clear()
            self.born = False
            for row in rows:
                self.buffer.append(Envelope.from_json(row["payload"]))
                self._retains.append(bool(row["retain"]))
                self._row_ids.append(row["id"])
            self.buffered = len(self.buffer)

    # ------------------------------------------------------------- sequence --

    def set_period(self, period_s: float) -> None:
        """Declare the interval the devices will publish at from now on.

        The node changes cadence by itself (2-up / 4-down hysteresis between
        900 s, 60 s and 10 s); this is how that decision reaches the server.
        """
        self.period_s = float(period_s)

    def _next_seq(self, device: str) -> int:
        n = self._seq.get(device, 0) + 1
        self._seq[device] = n
        return n

    # ---------------------------------------------------------------- birth --

    def birth_envelopes(self) -> list[Envelope]:
        out: list[Envelope] = []
        for dev in assets.DEVICES:
            env = make_birth(self.site, self.panel_key, dev.key,
                             device_metrics(dev.key), self.fw, self.boot)
            env.event = {
                "kind": dev.kind,
                "label": dev.label,
                "mount": dev.mount,
                "covers": list(dev.covers),
                "battery": dev.battery,
                "x_mm": dev.x_mm,
                "y_mm": dev.y_mm,
            }
            env.event["period_s"] = self.period_s
            if dev.key == "GW-01":
                env.event["latency_note_tr"] = LATENCY_NOTE_TR
                env.event["protection_note_tr"] = (
                    "PANO GÖZ koruma değildir. Ark açması TVOC-2 donanımında "
                    "~1 ms'de gerçekleşir."
                )
            out.append(env)
        return out

    def emit_birth(self) -> int:
        n = 0
        for env in self.birth_envelopes():
            self._emit(env, retain=True)
            n += 1
        self.born = True
        return n

    def emit_death(self) -> None:
        self._emit(make_death(self.site, self.panel_key, "GW-01"), retain=True)

    # -------------------------------------------------------------- publish --

    def publish(self, out: Any) -> None:
        """Turn one simulator output into envelopes and put them on the bus."""
        frame = normalise(out)
        self.last_frame = frame
        if not self.born:
            self.emit_birth()

        per_device: dict[str, Envelope] = {}

        def env_for(device: str) -> Envelope:
            if device not in per_device:
                per_device[device] = Envelope(
                    kind="data", site=self.site, panel=self.panel_key,
                    device=device, ts=frame.ts, seq=0, boot=self.boot,
                )
            return per_device[device]

        # Panel-level channels routed by prefix.
        for name, value in frame.values.items():
            device = self._value_owner(name)
            if device is None:
                continue
            env_for(device).values[name] = ch.quantise(name, float(value))

        # Per-joint channels routed by which device actually covers the joint.
        for joint_key, readings in frame.joints.items():
            for name, value in readings.items():
                device = self._joint_owner(joint_key, name)
                if device is None:
                    continue
                e = env_for(device)
                e.joints.setdefault(joint_key, {})[name] = ch.quantise(name, float(value))

        # Device self-health.
        for device, vals in frame.devices.items():
            if device not in assets.DEVICES_BY_KEY:
                continue
            e = env_for(device)
            for name, value in vals.items():
                e.values[name] = ch.quantise(name, float(value))

        for device, env in sorted(per_device.items()):
            env.values["dev.period_s"] = self.period_s
            env.seq = self._next_seq(device)
            self._emit(env)

        for ev in frame.events:
            self._emit_event(ev, frame.ts)

        if self.store is not None:
            self._persist(frame)

    def _value_owner(self, name: str) -> str | None:
        for prefix, device in PREFIX_OWNER:
            if name.startswith(prefix):
                return device or None
        if name.startswith("dev."):
            return None      # only meaningful inside a device's own block
        return "GW-01"

    def _joint_owner(self, joint_key: str, channel: str) -> str | None:
        """A joint reading belongs to the device that physically covers it.

        A thermal clip owns the joint it is clamped below.  The IR array owns
        every bottom-compartment lug it can see, including the ones a clip also
        watches - two independent measurements of the same joint is the point,
        not a duplicate.
        """
        if channel.startswith("tc."):
            for dev in assets.DEVICES:
                if dev.kind == "TC" and joint_key in dev.covers:
                    return dev.key
            return None
        if channel.startswith("ir."):
            return "TN-IR"
        return "TN-IR"

    def _emit_event(self, ev: dict, ts: float) -> None:
        device = ev.get("device") or "GW-01"
        env = Envelope(kind="event", site=self.site, panel=self.panel_key,
                       device=device, ts=float(ev.get("ts", ts)),
                       seq=self._next_seq(device), boot=self.boot, event=dict(ev))
        self._emit(env)

    # ------------------------------------------------- store and forward ----

    def ingest_node_envelope(self, env: Envelope) -> None:
        """Take custody of a decoded node frame without changing seq/boot/cadence.

        Return only after durable storage (or completed delivery). The radio
        receiver may then ACK custody. A full/failed outbox raises: do not ACK.
        This is not an RF driver and does not synthesize gateway timestamps.
        """
        if self.outbox_store is None:
            raise RuntimeError("Node ingress requires a persistent outbox")
        if env.site != self.site or env.panel != self.panel_key:
            raise ValueError("Node frame belongs to another site/panel")
        if env.device not in assets.DEVICES_BY_KEY or env.device == "GW-01":
            raise ValueError("Unknown node")
        if env.kind not in ("data", "event", "birth", "state"):
            raise ValueError("Unsupported node frame kind")
        self._emit(env, retain=env.kind == "birth")

    def _emit(self, env: Envelope, retain: bool = False) -> None:
        """Ring first, transport second.  Ordering survives an outage."""
        with self._buffer_lock:
            row_id = None
            if self.outbox_store is not None:
                row_id = self.outbox_store.outbox_add(
                    self.panel_key, env.to_json(), retain, self.buffer_size)
            elif len(self.buffer) == self.buffer_size:
                self.dropped += 1
                self._retains.popleft()
                self._row_ids.popleft()
                self._receipt = None
            self.buffer.append(env)
            self._retains.append(retain)
            self._row_ids.append(row_id)
            self.buffered = len(self.buffer)
            self.drain()

    def drain(self, retain: bool = False) -> int:
        """Retire ordered messages after PUBACK (or inproc queue acceptance).

        Pending MQTT receipts never block the simulator. The delivery worker
        polls this method even when no new sensor samples arrive. Transport
        failures leave the operator-controlled ``online`` switch untouched.
        """
        with self._buffer_lock:
            if self.bus is None or not self.online:
                return 0
            sent = 0
            while self.buffer:
                try:
                    if self._receipt is None:
                        self._receipt = self.bus.publish_envelope(
                            self.buffer[0], retain=self._retains[0])
                    if self._receipt is not None and not self._receipt.is_published():
                        break
                    if self.outbox_store is not None:
                        self.outbox_store.outbox_ack(self._row_ids[0])
                except Exception:  # transport or storage failure: keep head
                    self.publish_failures += 1
                    self._receipt = None
                    break
                self.buffer.popleft()
                self._retains.popleft()
                self._row_ids.popleft()
                self._receipt = None
                self.published += 1
                sent += 1
            self.buffered = len(self.buffer)
            if sent:
                self.drains += 1
            return sent

    def set_online(self, online: bool) -> int:
        """Mark the WAN up or down.  Coming back up drains the ring."""
        was = self.online
        self.online = bool(online)
        if self.online and not was:
            return self.drain()
        return 0

    # ------------------------------------------------------- local rules ----

    def local_critical_rules(self, out: Any) -> list[dict]:
        """Rules that must fire with no server, no broker and no WAN.

        Deliberately dumb.  No baseline, no CUSUM, no history: every one of these
        is computable from a single frame with an explicit threshold, because
        anything that needs state is something that can be wrong after a reboot
        at exactly the moment we need it.  The server does the clever part; this
        does the part that has to work.
        """
        frame = normalise(out)
        now = frame.ts
        v = frame.values
        fired: list[dict] = []

        def fire(rule: str, severity: str, title: str, detail: str,
                 evidence: dict | None = None, joint: str | None = None) -> None:
            fired.append({
                "rule": rule, "severity": severity, "ts": now,
                "title_tr": title, "detail_tr": detail,
                "joint_key": joint, "evidence": evidence or {},
                "local": True,
                "action_tr": ch.SEVERITY_ACTION_TR.get(severity, ""),
            })

        # R1 - arc trip.  The relay has already cleared it; our job is to say so.
        if float(v.get("tvoc.active_trip", 0.0)) >= 1.0 or frame.arc.get("active_trip"):
            trip = frame.arc.get("last_trip") or {}
            fire("ARK_ACMA", "ACIL", "Ark açması",
                 "TVOC-2 ark açması yaptı. Açma ~1 ms'de donanımda gerçekleşti; "
                 "PANO GÖZ bunu konumlandırır ve zaman damgalar.",
                 {"detectors": trip.get("detectors", []),
                  "relays": trip.get("relays", []),
                  "trip_number": trip.get("number")})

        # R2 - we have lost the arc relay.  The relay cannot report this itself.
        if frame.arc.get("fitted") and "tvoc.online" in v and float(v["tvoc.online"]) < 1.0:
            fire("ARK_HABERLESME_YOK", "KRITIK", "Ark rölesi haberleşmesi yok",
                 "RS-485 bağlantısı yanıt vermiyor. Röle çalışıyor olabilir, ancak "
                 "durumunu doğrulayamıyoruz ve röle bunu kendisi bildiremez.",
                 {"consecutive_failures": frame.arc.get("consecutive_failures")})

        # R3/R4 - thermal, from the joint frame.
        temps = self._joint_temperatures(frame)
        for joint_key, (temp, current) in temps.items():
            joint = assets.JOINTS_BY_KEY.get(joint_key)
            if joint is None:
                continue
            if temp >= LOCAL_ABS_TEMP_C:
                fire("MUTLAK_SICAKLIK", "KRITIK", "Bağlantı sıcaklığı mutlak sınırda",
                     f"{joint.label} {temp:.1f} °C. PVC yalıtım sürekli 70 °C'ye "
                     f"göre anmalıdır; {LOCAL_ABS_TEMP_C:.0f} °C'de pabucun arkasındaki "
                     f"yalıtım zaten anma dışıdır.",
                     {"temp_c": round(temp, 2), "limit_c": LOCAL_ABS_TEMP_C}, joint_key)

        deltas = self._sibling_deltas(temps)
        for joint_key, info in deltas.items():
            joint = assets.JOINTS_BY_KEY[joint_key]
            f_load = info["load_factor"]
            if info["delta_k"] >= LOCAL_DELTA_K and f_load >= LOCAL_MIN_LOAD_FACTOR:
                fire("KARDES_FARKI", "KRITIK", "Kardeş fazlara göre aşırı sıcaklık",
                     f"{joint.label}, kardeş fazların medyanından "
                     f"{info['delta_k']:.1f} K sıcak (yük faktörü {f_load:.0%}). "
                     f"IR termografi pratiği benzer bileşene göre 15 K'yı "
                     f"'derhal onar' sayar.",
                     info, joint_key)
            elif info["delta_k"] >= LOCAL_DELTA_K:
                # Not an alarm.  A suppressed alarm with a stated reason is a
                # shipped feature, not a silence.
                fired.append({
                    "rule": "KARDES_FARKI", "severity": "IZLE", "ts": now,
                    "title_tr": "Kardeş farkı yüksek ama yük düşük",
                    "detail_tr": (f"{joint.label} {info['delta_k']:.1f} K sıcak, ancak "
                                  f"yük faktörü {f_load:.0%} < {LOCAL_MIN_LOAD_FACTOR:.0%}. "
                                  f"Bu seviyede θ güvenilir değil (GÖRÜNÜRLÜK DÜŞÜK)."),
                    "joint_key": joint_key, "evidence": info, "local": True,
                    "suppressed": True, "suppress_reason": "SENSITIVITY_LOW",
                    "action_tr": ch.SEVERITY_ACTION_TR["IZLE"],
                })

        # R5 - condensation on the coldest surface, not on the air.
        margin = v.get("env.condensation_margin_k")
        if margin is not None and float(margin) <= 0.0:
            fire("YOGUSMA", "UYARI", "Yoğuşma riski",
                 f"Tahmini yüzey sıcaklığı çiy noktasının {abs(float(margin)):.1f} K "
                 f"altında. Pano tabanı kablo kanalına açıktır (Madde 2.2.8.6 Not:2).",
                 {"margin_k": round(float(margin), 2)})

        # R6 - analyser link.
        if "mpr.online" in v and float(v["mpr.online"]) < 1.0:
            fire("ANALIZOR_HABERLESME_YOK", "UYARI", "Analizör haberleşmesi yok",
                 "Entes MPR-53CS yanıt vermiyor; akım ve gerilim kanalları bayat.",
                 {})

        self._record_local(fired)
        return fired

    def _joint_temperatures(self, frame: GatewayFrame) -> dict[str, tuple[float, float]]:
        """``{joint_key: (temp_c, current_a)}`` from whichever sensor reported."""
        out: dict[str, tuple[float, float]] = {}
        for joint_key, readings in frame.joints.items():
            temp = readings.get("tc.temp_c", readings.get("ir.lug_temp_c"))
            if temp is None:
                continue
            joint = assets.JOINTS_BY_KEY.get(joint_key)
            cur = readings.get("tc.current_a")
            if cur is None and joint is not None:
                # No clip on this lug: fall back to the analyser's phase current
                # scaled by the feeder's share of the busbar rating.  Explicitly
                # an estimate, and only ever used to decide whether we are
                # sensitive enough to alarm, never to compute theta.
                phase = frame.values.get(f"mpr.i_{joint.conductor.lower()}_a")
                if phase is not None:
                    cur = float(phase) * joint.rated_a / assets.MAIN_BUSBAR_RATED_A
            out[joint_key] = (float(temp), float(cur or 0.0))
        return out

    def _sibling_deltas(self, temps: dict[str, tuple[float, float]]) -> dict[str, dict]:
        """Raw temperature excess over the sibling median, per joint.

        This is theta's poor relation: no load normalisation, no baseline.  That
        is deliberate.  The gateway fires on the raw difference and gates on load
        factor; the server does the normalised, history-aware version.
        """
        out: dict[str, dict] = {}
        for group, joints in assets.sibling_groups().items():
            if group.endswith(":N"):
                # The neutral is not a peer of anything - it carries the
                # unbalance plus the triplens.  Rule H3 handles it on the server.
                continue
            present = [(j.key, temps[j.key]) for j in joints if j.key in temps]
            if len(present) < 3:
                continue
            values = [t for _, (t, _) in present]
            for key, (temp, cur) in present:
                others = [t for k, (t, _) in present if k != key]
                med = statistics.median(others)
                joint = assets.JOINTS_BY_KEY[key]
                out[key] = {
                    "group": group,
                    "temp_c": round(temp, 2),
                    "sibling_median_c": round(med, 2),
                    "delta_k": round(temp - med, 2),
                    "current_a": round(cur, 1),
                    "load_factor": round(cur / joint.rated_a, 3) if joint.rated_a else 0.0,
                    "siblings": [k for k, _ in present if k != key],
                }
        return out

    def _record_local(self, fired: Sequence[dict]) -> None:
        for ev in fired:
            key = f"{ev['rule']}:{ev.get('joint_key') or '-'}"
            prev = self._local_active.get(key)
            if prev is None or prev["severity"] != ev["severity"]:
                self._local_active[key] = ev
                self.local_alarms.append(ev)
                if ev["severity"] in ch.DISPATCH_SEVERITIES and self.on_local_alarm:
                    # The local dry contact and the annunciator.  No WAN needed.
                    self.on_local_alarm(ev)

    # ------------------------------------------------------------ persist ---

    def _persist(self, frame: GatewayFrame) -> None:
        rows = [(frame.ts, self.panel_key, name, float(val))
                for name, val in frame.values.items()
                if ch.validate(name, float(val))]
        if rows:
            self.store.add_samples(rows)
        jrows = [(frame.ts, self.panel_key, jk, name, float(val))
                 for jk, readings in frame.joints.items()
                 for name, val in readings.items()
                 if ch.validate(name, float(val))]
        if jrows:
            self.store.add_joint_samples(jrows)
        self.store.commit()

    # ---------------------------------------------------------------- run ---

    async def run(
        self,
        *,
        period: float = 1.0,
        cycles: int | None = None,
        t0: float | None = None,
        real_time: bool = False,
        stop: Callable[[], bool] | None = None,
    ) -> dict:
        """Main loop.

        Deterministic by construction: with ``t0`` given, every frame's
        timestamp is ``t0 + i * period`` and nothing reads the wall clock.  With
        ``real_time`` the loop also sleeps, which is what the live demo wants and
        what a test never does.
        """
        import asyncio

        i = 0
        while cycles is None or i < cycles:
            if stop is not None and stop():
                break
            ts = (t0 + i * period) if t0 is not None else time.time()
            frame = normalise(self._step_sim(ts), ts)
            frame.ts = ts

            if self.poller is not None:
                pr = await self.poller.poll_once(ts)
                frame.values.update(pr.channels)
                frame.events.extend(pr.events)
                frame.arc = pr.arc
                if pr.errors:
                    frame.events.append({"type": "modbus_errors", "errors": pr.errors})

            frame.values.setdefault("dev.uptime_s", round(ts - self._started_at, 0))
            fired = self.local_critical_rules(frame)
            for ev in fired:
                if ev["severity"] in ch.DISPATCH_SEVERITIES:
                    frame.events.append({"type": "local_rule", **ev})
            self.publish(frame)

            self.cycles += 1
            i += 1
            if real_time:
                await asyncio.sleep(period)
        return self.stats()

    def _step_sim(self, ts: float) -> Any:
        if self.sim is None:
            return None
        for name in ("step", "tick", "sample", "update"):
            fn = getattr(self.sim, name, None)
            if callable(fn):
                return fn(ts)
        if callable(self.sim):
            return self.sim(ts)
        return None

    # -------------------------------------------------------------- status --

    def stats(self) -> dict:
        return {
            "panel_key": self.panel_key,
            "site": self.site,
            "boot": self.boot,
            "cycles": self.cycles,
            "online": self.online,
            "published": self.published,
            "buffered": self.buffered,
            "buffer_size": self.buffer_size,
            "dropped": self.dropped,
            "drains": self.drains,
            "publish_failures": self.publish_failures,
            "devices": len(assets.DEVICES),
            "seq": dict(self._seq),
            "local_alarms": len(self.local_alarms),
            "local_critical": sum(1 for a in self.local_alarms
                                  if a["severity"] in ch.DISPATCH_SEVERITIES),
        }


# ==========================================================================

if __name__ == "__main__":
    import asyncio
    import json

    from panogoz.bus.bus import InProcBus
    from panogoz.contracts.envelope import SUBSCRIBE_ALL, Envelope as Env, SeqTracker

    T0 = 1_757_000_000.0

    class FlakyBus(InProcBus):
        """An in-process bus we can switch off, to prove the ring works."""

        def __init__(self) -> None:
            super().__init__()
            self.up = True
            self.refused = 0

        def publish(self, topic, payload, retain=False, qos=1):
            if not self.up:
                self.refused += 1
                raise ConnectionError("WAN down")
            super().publish(topic, payload, retain=retain, qos=qos)

    def make_frame(ts: float, *, hot: float = 0.0, load: float = 0.85,
                   trip: bool = False, margin: float = 6.0) -> GatewayFrame:
        """A minimal stand-in for the panel simulator's output."""
        joints: dict[str, dict[str, float]] = {}
        for j in assets.monitored_joints():
            base = 34.0 + 0.6 * (j.feeder_index or 0)
            cur = load * j.rated_a * (0.92 if j.conductor == "L2" else 1.0)
            if j.conductor == "N":
                cur = load * j.rated_a * 0.25
            temp = base + 8.0 * (cur / max(1.0, j.rated_a)) ** 2
            if j.key == "C06-L2-PABUC":
                temp += hot
            # The IR array sees all 40 lugs.  Feeders 6 and 7 additionally carry
            # a thermal clip, so those eight joints are measured twice by two
            # independent sensors - which is the point, not a duplicate.  The
            # clip sits 50-100 mm down the cable and reads a little cooler.
            reading: dict[str, float] = {"ir.lug_temp_c": temp}
            if j.feeder_index in (6, 7):
                reading["tc.temp_c"] = temp - 0.4
                reading["tc.current_a"] = cur
            joints[j.key] = reading
        return GatewayFrame(
            ts=ts,
            values={
                "env.air_c": 31.2, "env.rh_pct": 58.0, "env.dewpoint_c": 22.1,
                "env.wall_c": 28.1, "env.condensation_margin_k": margin,
                "mpr.i_l1_a": 1420.0, "mpr.i_l2_a": 980.0, "mpr.i_l3_a": 1150.0,
                "mpr.v_l1_v": 231.4, "mpr.freq_hz": 49.98, "mpr.online": 1.0,
                "tvoc.online": 1.0, "tvoc.active_trip": 1.0 if trip else 0.0,
                "tvoc.detectors_ok": 10.0, "tvoc.detectors_total": 10.0,
                "pd.rate_per_s": 12.0, "pd.qmax_db": 31.0, "pd.tev_db": 18.0,
                "ir.air_top_c": 33.4, "ir.aim_ok": 1.0,
            },
            joints=joints,
            devices={d.key: {"dev.battery_v": 3.58, "dev.battery_pct": 91.0,
                             "dev.rssi_dbm": -92.0}
                     for d in assets.DEVICES if d.kind != "GW"},
            arc={"fitted": True, "online": True, "active_trip": trip,
                 "last_trip": {"number": 1, "detectors": ["X2:3"], "relays": ["K5"]}},
        )

    async def main() -> None:
        print("=" * 78)
        print("PANO GOZ gateway  ·  self-test")
        print("=" * 78)

        bus = FlakyBus()
        bus.start()
        seen: list[Env] = []
        tracker = SeqTracker()
        bus.subscribe(SUBSCRIBE_ALL, lambda t, p: seen.append(Env.from_json(p)))

        alarms: list[dict] = []
        gw = Gateway(panel_key="SOKE-14", site="Soke", bus=bus, boot=7,
                     buffer_size=500, on_local_alarm=alarms.append)

        print("\n[1] birth: every device declares its own channel list")
        n = gw.emit_birth()
        await asyncio.sleep(0.15)
        births = [e for e in seen if e.kind == "birth"]
        print(f"    {n} birth messages, {len(births)} received")
        for e in sorted(births, key=lambda x: x.device)[:4]:
            print(f"      {e.device:<7} boot={e.boot} metrics={len(e.metrics):<2} "
                  f"{e.metrics[:3]}...")
        print(f"      ...")
        gwb = [e for e in births if e.device == "GW-01"][0]
        print(f"      GW-01   metrics={len(gwb.metrics)} (mpr.* + tvoc.*)")
        print(f"      topic   {gwb.topic}")
        assert n == 9 == assets.DEVICES_PER_PANEL
        assert len(births) == 9
        for e in births:
            assert e.metrics and all(m in ch.BY_NAME for m in e.metrics), e.device

        print("\n[2] one frame -> routed envelopes")
        seen.clear()
        gw.publish(make_frame(T0))
        await asyncio.sleep(0.15)
        data = [e for e in seen if e.kind == "data"]
        for e in sorted(data, key=lambda x: x.device):
            print(f"    {e.device:<7} seq={e.seq:<3} values={len(e.values):<3} "
                  f"joints={len(e.joints):<3} {sorted(e.values)[:2]}")
        by_dev = {e.device: e for e in data}
        assert "mpr.i_l1_a" in by_dev["GW-01"].values
        assert "env.rh_pct" in by_dev["PD-01"].values
        assert len(by_dev["TN-IR"].joints) == 40
        assert by_dev["TC-04"].joints and list(by_dev["TC-04"].joints) == ["C07-L1-PABUC"]
        assert len(by_dev["TC-04"].joints["C07-L1-PABUC"]) == 2  # temp + its own current
        print(f"    TC-04 covers exactly {list(by_dev['TC-04'].joints)} "
              f"(one clip, one joint)")
        print(f"    TN-IR covers {len(by_dev['TN-IR'].joints)} lugs "
              f"(the whole bottom row)")

        print("\n[3] monotonic seq per device, gap detection at the far end")
        for i in range(1, 4):
            gw.publish(make_frame(T0 + i))
        await asyncio.sleep(0.2)
        results = [tracker.check(e) for e in seen if e.kind == "data"]
        print(f"    {len(results)} data frames, statuses: "
              f"{ {r: results.count(r) for r in set(results)} }")
        print(f"    gaps={tracker.gaps} reboots={tracker.reboots} lost={tracker.lost}")
        assert tracker.gaps == 0 and tracker.lost == 0

        print("\n[4] store and forward across a WAN outage")
        before = gw.published
        bus.up = False
        for i in range(4, 14):
            gw.publish(make_frame(T0 + i))
        print(f"    WAN down: published={gw.published - before} "
              f"buffered={gw.buffered} failures={gw.publish_failures} "
              f"online={gw.online}")
        assert gw.buffered > 20 and not gw.online
        bus.up = True
        drained = gw.set_online(True)
        await asyncio.sleep(0.3)
        print(f"    WAN back: drained {drained} envelopes, buffered={gw.buffered}, "
              f"dropped={gw.dropped}")
        assert gw.buffered == 0 and gw.dropped == 0
        results = [tracker.check(e) for e in seen if e.kind == "data"]
        print(f"    sequence after recovery: gaps={tracker.gaps} lost={tracker.lost} "
              f"(nothing was lost, only delayed)")
        assert tracker.lost == 0

        print("\n[5] ring overflow is counted, not hidden")
        small = Gateway(panel_key="SOKE-15", site="Soke", bus=bus, boot=1, buffer_size=12)
        small.online = False
        for i in range(6):
            small.publish(make_frame(T0 + i))
        print(f"    buffer_size=12, buffered={small.buffered}, dropped={small.dropped}")
        print(f"    an unbounded buffer on a DIN-rail box is a delayed crash, "
              f"not durability")
        assert small.buffered == 12 and small.dropped > 0

        print("\n[6] local critical rules - no server, no broker, no WAN")
        bus.up = False
        gw.online = False
        cases = (
            ("healthy panel", make_frame(T0 + 100)),
            ("arc trip", make_frame(T0 + 101, trip=True)),
            ("lug at 95 C", make_frame(T0 + 102, hot=52.0)),
            ("25 K sibling delta at 85% load", make_frame(T0 + 103, hot=25.0)),
            ("25 K sibling delta at 15% load", make_frame(T0 + 104, hot=25.0, load=0.15)),
            ("condensation", make_frame(T0 + 105, margin=-1.4)),
        )
        for label, frame in cases:
            fired = gw.local_critical_rules(frame)
            crit = [f for f in fired if f["severity"] in ch.DISPATCH_SEVERITIES]
            supp = [f for f in fired if f.get("suppressed")]
            tag = ", ".join(sorted({f["rule"] for f in crit})) or "-"
            print(f"    {label:<32} kritik={len(crit):<2} bastirilan={len(supp):<2} {tag}")
        bus.up = True
        gw.set_online(True)
        await asyncio.sleep(0.2)

        print("\n    detail of the two thermal cases:")
        for label, frame in (("85% load", make_frame(T0 + 110, hot=25.0)),
                             ("15% load", make_frame(T0 + 111, hot=25.0, load=0.15))):
            g2 = Gateway(panel_key="X", site="Y", bus=None, boot=1)
            for f in g2.local_critical_rules(frame):
                if f["rule"] != "KARDES_FARKI":
                    continue
                print(f"      {label:<9} {f['severity']:<7} {f['detail_tr'][:96]}")
        print(f"      -> a suppressed alarm with a stated reason is a shipped "
              f"feature, not silence")

        print("\n[7] the local dry contact fired without any transport")
        print(f"    on_local_alarm callbacks: {len(alarms)}")
        for a in alarms[:4]:
            print(f"      {a['severity']:<7} {a['rule']:<22} {a['title_tr']}")
        assert any(a["rule"] == "ARK_ACMA" for a in alarms)
        assert any(a["rule"] == "MUTLAK_SICAKLIK" for a in alarms)

        print("\n[8] deterministic run loop")
        bus2 = FlakyBus()
        bus2.start()
        got: list[Env] = []
        bus2.subscribe(SUBSCRIBE_ALL, lambda t, p: got.append(Env.from_json(p)))
        gw3 = Gateway(panel_key="SOKE-16", site="Soke", bus=bus2, boot=3,
                      sim=lambda ts: make_frame(ts))
        st = await gw3.run(period=1.0, cycles=5, t0=T0)
        await asyncio.sleep(0.3)
        stamps = sorted({round(e.ts, 3) for e in got if e.kind == "data"})
        print(f"    cycles={st['cycles']} published={st['published']} "
              f"buffered={st['buffered']}")
        print(f"    timestamps: {stamps}  (t0 + i*period, no wall clock)")
        assert stamps == [T0 + i for i in range(5)]
        assert st["published"] == len(got)

        print("\n[9] final gateway status")
        print("    " + json.dumps(gw.stats(), indent=2).replace("\n", "\n    "))

        print("\n[10] the Sparkplug question, answered in one line")
        print("    Sparkplug 3.0 mandates QoS 0 for DDATA. A PUBACK-driven")
        print("    store-and-forward watermark cannot exist at QoS 0, so the")
        print("    durability shown in [4] would be a claim we could not keep.")
        print(f"    {LATENCY_NOTE_TR}")

        bus.stop()
        bus2.stop()
        print("\n" + "=" * 78)
        print("Gateway self-test PASSED")
        print("=" * 78)

    asyncio.run(main())
