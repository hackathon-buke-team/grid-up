"""Two-node thermal model of one bolted joint inside the panel, plus sensors.

    ambient  --[ tau_air 45-90 min ]-->  cabinet air  --[ tau_joint 5-40 min ]-->  joint

Node 1 is the cabinet air.  Node 2 is the joint itself.  Both are first order.
The joint sees the cabinet air, not the outdoor ambient, and that distinction is
the whole reason a bare temperature threshold fails in the field.

The heat sources, and the one everybody forgets
-----------------------------------------------

The obvious source is the busbar: 2 x (100 x 10) mm2 tinned copper per phase
carrying up to 2312 A dissipates roughly 200 W across the whole panel at rated
current.  That is not the dominant term.

The dominant term is the NH fuse-links.  A 1600 kVA panel has ten live
fuse-switch-disconnectors (five 1 Boy at 250 A, five 2 Boy at 400 A), each with
three poles, and an NH link dissipates on the order of 20-25 W per pole at its
own rating.  At a realistic 50 % feeder loading that is 5-8 W per pole and
150-250 W in total; pushed to 80 % it passes 450 W.  So the fuses put two to
three times as much heat into the cabinet as the busbar does.

This matters for more than realism.  Fuse heating is load dependent AND phase
specific: an unbalanced feeder heats the air above its heaviest pole more than
the air above its lightest one.  If the model lumps all that into one air node,
the phase-dependent part of it lands in the theta residual and is
indistinguishable from a developing joint.  Modelling it explicitly is what lets
the detector be tested against the confounder it will actually meet.

Thermal resistances - get these right
-------------------------------------

For a localised source on a busbar the bar acts as a **two-sided fin**::

    R_th = 1 / ( 2 * sqrt(h * P * k * A) )

with k = 400 W/mK, A = 2e-3 m2 (2 x 100 x 10 mm2), P ~ 0.44 m and
h = 5-12 W/m2K, giving **0.24-0.38 K/W**.  The figure 3.44 K/W that appears in
some notes is wrong by about a factor of ten: it would predict a 919 K rise for
a 50 microohm main-busbar joint at 2312 A, which would have melted the copper.

A 240 mm2 **cable lug** is a much worse heat spreader and sits at
**R_th,local ~ 2-4 K/W**.  Worked case, which is also the consistency check the
detector relies on: a 400 A feeder lug degraded to 50 microohm dissipates
I^2 R = 8.0 W; at 2-4 K/W that is a **16-32 K** local rise at rated feeder
current, and inverting ``dR = theta / (R_th * I_ref^2)`` over the same interval
returns 50 microohm.  Because R_th is only known to a factor, excess resistance
is always reported as an interval with the R_th range attached, never as a
single number.

Convection is not linear.  Natural convection on a small body gives roughly
``dT ~ P^0.8``, so each joint carries its own exponent ``n`` in 0.75-0.90 and
the effective R_th rises at low dissipation.  Ignoring this makes a lightly
loaded panel look better than it is.

Solar gain does not apply: TEDAS-MLZ/2003-06.B lists 1600 kVA as a *dahili*
(indoor) type only.  The substation-room swing does apply and is the ambient
input to this model.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from panogoz.contracts import assets
from panogoz.sim.load import gauss, tag, vnoise

# --------------------------------------------------------------------------
# Material and geometry constants
# --------------------------------------------------------------------------

COPPER_K_W_PER_MK = 400.0
#: Main busbar per phase: 2 x (100 x 10) mm2 = 2000 mm2 = 2.0e-3 m2.
BUSBAR_AREA_M2 = assets.BUSBAR_AREA_MM2 * 1e-6
#: Wetted perimeter of the two-bar stack, metres.  2 x (2*(0.100+0.010)) = 0.44 m.
BUSBAR_PERIMETER_M = 2.0 * 2.0 * (assets.BUSBAR_BAR_W_MM + assets.BUSBAR_BAR_T_MM) * 1e-3

#: Natural-convection film coefficient inside a closed IP2X enclosure, W/m2K.
H_ENCLOSURE_LO = 5.0
H_ENCLOSURE_HI = 12.0

#: Localised thermal resistance of a 240 mm2 compression lug on a cable tail.
R_TH_LUG_LO_K_PER_W = 2.0
R_TH_LUG_HI_K_PER_W = 4.0
R_TH_LUG_NOM_K_PER_W = 3.0

#: A healthy tinned bolted joint.  At 2312 A a 5 microohm joint burns 27 W.
HEALTHY_R_UOHM_LO = 2.0
HEALTHY_R_UOHM_HI = 5.0

#: Per-joint departure from the sibling group's shared heat-spreading path.
R_TH_JOINT_JITTER_K_PER_W = 0.15
N_JOINT_JITTER = 0.015

#: Reference dissipation for the convection non-linearity.  ``R_th_local`` is
#: quoted *at* this power; below it the effective resistance rises.
P_REF_W = 5.0

# --------------------------------------------------------------------------
# In-panel heat budget
# --------------------------------------------------------------------------

#: Whole-panel busbar and connection losses at the 2312 A of Tablo 3a.
BUSBAR_LOSS_AT_RATED_W = 200.0

#: NH fuse-link dissipation per pole at the link's own rated current.
FUSE_POLE_LOSS_W = {160: 14.0, 250: 20.0, 400: 25.0}

#: Cabinet air rise above ambient at rated current, kelvin.  Anchored so that
#: ``dT_air = 20 K`` at ``I = In`` exactly, with the P^n curve giving the shape
#: in between.
AIR_RISE_AT_RATED_K = 20.0

#: Convection exponent for the cabinet air node.
AIR_CONV_EXPONENT = 0.80


def _live_feeders() -> tuple:
    return tuple(f for f in assets.FEEDERS if not f.spare)


def fuse_loss_w(load_factor: float, feeders=None) -> float:
    """Total NH fuse-link dissipation across the panel, watts.

    Every live pole is assumed to carry ``load_factor`` of its own DSYA rating,
    and link loss scales as I^2.
    """
    tot = 0.0
    for f in feeders or _live_feeders():
        per_pole = FUSE_POLE_LOSS_W.get(f.rated_a, 20.0)
        tot += 3.0 * per_pole * load_factor * load_factor
    return tot


def panel_loss_w(load_factor: float) -> float:
    """Busbar plus fuse-link dissipation, watts."""
    lf = max(0.0, load_factor)
    return BUSBAR_LOSS_AT_RATED_W * lf * lf + fuse_loss_w(lf)


#: Calibration constant: ``dT_air = K_AIR * P ** AIR_CONV_EXPONENT``.
_P_AT_RATED_W = panel_loss_w(1.0)
K_AIR = AIR_RISE_AT_RATED_K / (_P_AT_RATED_W ** AIR_CONV_EXPONENT)

# Coupling from one fuse pole's own dissipation down to the lug below it.
#
# Weak, and weak for a reason: the lug row sits in the bottom cable compartment
# and the fuse bases sit above it, so buoyancy carries the plume away upward.
# What does reach the lug is conduction along the cable tail from its own pole,
# which is why the term is small rather than zero.  Calibrated to about 0.6 K at
# the pole's rated current.
#
# It matters far beyond its size.  This is the one heat source in the panel that
# is BOTH load dependent AND phase specific, so on an unbalanced feeder it does
# not cancel between siblings: it lands directly in the theta residual and looks
# like a developing joint.  A simulator that lumps it into the single air node
# hands the detector an easier problem than the field will.
POLE_LOCAL_AT_RATED_K = 0.6
_POLE_P_AT_RATED_W = FUSE_POLE_LOSS_W[400]
K_POLE_LOCAL = POLE_LOCAL_AT_RATED_K / (_POLE_P_AT_RATED_W ** AIR_CONV_EXPONENT)


def busbar_r_th_k_per_w(h_w_m2k: float = 8.0,
                        k: float = COPPER_K_W_PER_MK,
                        area_m2: float = BUSBAR_AREA_M2,
                        perimeter_m: float = BUSBAR_PERIMETER_M) -> float:
    """Two-sided fin resistance for a localised source on the main busbar.

    ``R_th = 1 / (2 sqrt(h P k A))``.  With h from 5 to 12 W/m2K this returns
    0.38 down to 0.24 K/W.  Nothing in PANO GOZ may use 3.44 K/W for a busbar.
    """
    return 1.0 / (2.0 * math.sqrt(h_w_m2k * perimeter_m * k * area_m2))


BUSBAR_R_TH_HI_K_PER_W = busbar_r_th_k_per_w(H_ENCLOSURE_LO)
BUSBAR_R_TH_LO_K_PER_W = busbar_r_th_k_per_w(H_ENCLOSURE_HI)


def excess_r_interval_uohm(theta_k: float, i_ref_a: float,
                           r_th_lo: float = R_TH_LUG_LO_K_PER_W,
                           r_th_hi: float = R_TH_LUG_HI_K_PER_W) -> tuple[float, float]:
    """Invert theta into an excess-resistance **interval**, microohm.

    ``dR = theta / (R_th * I_ref^2)``.  A large R_th means a small resistance
    explains the same rise, so the low end of the resistance interval pairs with
    the high end of the R_th interval.
    """
    if i_ref_a <= 0.0:
        return (0.0, 0.0)
    lo = 1e6 * theta_k / (r_th_hi * i_ref_a * i_ref_a)
    hi = 1e6 * theta_k / (r_th_lo * i_ref_a * i_ref_a)
    return (lo, hi)


def joint_rise_k(power_w: float, r_th: float, n: float = 0.82,
                 p_ref: float = P_REF_W) -> float:
    """Steady-state joint rise above its local air, with convection curvature.

    ``dT = R_th * P * (P / P_ref)^(n-1)``.  At ``P = P_ref`` this is exactly
    ``R_th * P``; below it the effective resistance grows, because a cooler body
    drives a weaker plume.
    """
    if power_w <= 0.0:
        return 0.0
    return r_th * power_w * (max(power_w, 1e-9) / p_ref) ** (n - 1.0)


def theta_from_rise(dt_excess_k: float, current_a: float, i_ref_a: float) -> float:
    """``theta = dT / (I / I_ref)^2`` - excess kelvin at reference current."""
    if current_a <= 0.0 or i_ref_a <= 0.0:
        return 0.0
    f = current_a / i_ref_a
    return dt_excess_k / (f * f)


def theta_load_bias(load_factor: float, n: float = 0.82) -> float:
    """How much theta over-reports at partial load, as a multiplier.

    theta divides out the I^2 in the *dissipation*, but the removal side is
    ``dT ~ P^n`` with n about 0.82, not n = 1.  What survives is
    ``f^(2(n-1))``: at f = 0.55 and n = 0.82 the same defect reads about 1.24x
    higher than it does at rated current.

    This is a real residual load dependence and PANO GOZ does not pretend it
    away.  It is small compared with the 10-50x that an uncorrected raw
    temperature swings by, it is monotone, and it is in the conservative
    direction (a defect looks worse at light load, never better).  The detector
    is free to divide it out; the simulator's job is to produce it.
    """
    f = max(1e-6, load_factor)
    return f ** (2.0 * (n - 1.0))


# Per-joint mounting variation.  This - not the TMP117 electronics - is what
# sets the 0.2 K sibling-differential sigma the 3-sigma detectability rule is
# built on, and it decomposes into three timescales that matter very differently:
#
#   fixed  a clip's seating, its contact conductance, the exact air pocket
#          around one lug.  Large, and completely removed by the commissioning
#          baseline, so it never limits anything.  Lives in the sensor models.
#   fast   micro-turbulence in the cabinet, minutes.  Large per sample, and it
#          averages out of the daily median, which is why the detector runs
#          CUSUM on the daily median and not on raw samples.
#   slow   gradual re-seating over weeks.  Small, does NOT average out, and is
#          therefore the real floor on long-term trending.
#
# Quoting a single "sensor accuracy" number and stopping there is how monitoring
# systems end up promising a sensitivity they cannot hold for six months.
MOUNT_MICRO_FAST_SD_K = 0.135
MOUNT_MICRO_FAST_PERIOD_S = 25.0 * 60.0
MOUNT_MICRO_SLOW_SD_K = 0.030
MOUNT_MICRO_SLOW_PERIOD_S = 18.0 * 86400.0
#: Single-sample sibling-pair sigma implied by the two wandering terms.
MOUNT_MICRO_SD_K = math.sqrt(MOUNT_MICRO_FAST_SD_K ** 2 + MOUNT_MICRO_SLOW_SD_K ** 2)
_S_MOUNT = tag("sensor.mount.micro")
_VNOISE_SD = 0.862  # rms of smoothstep value noise, so the constants read as sigma


def mount_micro_k(seed: int, stream: int, ts: float) -> float:
    """Per-joint mounting offset, kelvin: fast term plus slow term."""
    fast = vnoise(seed, _S_MOUNT + stream, ts, MOUNT_MICRO_FAST_PERIOD_S)
    slow = vnoise(seed, _S_MOUNT + stream + 7919, ts, MOUNT_MICRO_SLOW_PERIOD_S)
    return (MOUNT_MICRO_FAST_SD_K * fast + MOUNT_MICRO_SLOW_SD_K * slow) / _VNOISE_SD


# --------------------------------------------------------------------------
# Sensors
# --------------------------------------------------------------------------

#: TMP117: +-0.1 C over -20..+50 C, 16-bit at 7.8125 mK.
TMP117_LSB_C = 1.0 / 128.0
TMP117_ACCURACY_C = 0.1
TMP117_NOISE_SD_K = 0.015

#: MLX90640: the number that matters for us is the *differential* pixel noise
#: between two pixels of the same frame, about 0.8 K rms.  Split evenly, each
#: pixel carries 0.8/sqrt(2).
MLX90640_DIFF_NOISE_K = 0.8
MLX90640_PIXEL_NOISE_K = MLX90640_DIFF_NOISE_K / math.sqrt(2.0)
MLX90640_LSB_C = 0.02
#: Fixed per-pixel bias from emissivity and view angle.  Stable, so a
#: sibling-differential baseline removes it - which is exactly why the detector
#: is allowed to trust an uncalibrated array.
MLX90640_FIXED_BIAS_SD_K = 0.35

_S_TMP_OFF = tag("sensor.tmp117.offset")
_S_TMP_N = tag("sensor.tmp117.noise")
_S_IR_OFF = tag("sensor.mlx.offset")
_S_IR_N = tag("sensor.mlx.noise")


def tmp117_offset_k(seed: int, stream: int) -> float:
    """Fixed calibration offset of one part, inside the +-0.1 C data-sheet band."""
    return max(-TMP117_ACCURACY_C, min(TMP117_ACCURACY_C,
                                       0.045 * gauss(seed, _S_TMP_OFF, stream)))


def tmp117_read(true_c: float, seed: int, stream: int, ts: float) -> float:
    """Quantised TMP117 reading with its fixed offset and its noise."""
    v = true_c + tmp117_offset_k(seed, stream)
    v += TMP117_NOISE_SD_K * gauss(seed, _S_TMP_N, stream, int(ts))
    return round(v / TMP117_LSB_C) * TMP117_LSB_C


def mlx90640_bias_k(seed: int, stream: int) -> float:
    return MLX90640_FIXED_BIAS_SD_K * gauss(seed, _S_IR_OFF, stream)


def mlx90640_read(true_c: float, seed: int, stream: int, ts: float) -> float:
    """One MLX90640 pixel (or small pixel patch) reading of a lug."""
    v = true_c + mlx90640_bias_k(seed, stream)
    v += MLX90640_PIXEL_NOISE_K * gauss(seed, _S_IR_N, stream, int(ts))
    return round(v / MLX90640_LSB_C) * MLX90640_LSB_C


# --------------------------------------------------------------------------
# The model
# --------------------------------------------------------------------------

@dataclass
class ThermalModel:
    """Cabinet air and one joint, both first order.

    ``r_th_local`` defaults to the 3.0 K/W mid-point of the 2-4 K/W lug
    interval.  ``conv_exponent`` is drawn per joint in 0.75-0.90 by
    :meth:`for_joint`, because two lugs on the same bar do not have identical
    plumes.
    """

    joint_key: str = ""
    rated_a: float = 400.0
    r_th_local: float = R_TH_LUG_NOM_K_PER_W
    tau_joint_s: float = 15.0 * 60.0
    tau_air_s: float = 60.0 * 60.0
    conv_exponent: float = 0.82
    air_rise_at_rated_k: float = AIR_RISE_AT_RATED_K
    seed: int = 0

    t_air_c: float = float("nan")
    t_joint_c: float = float("nan")
    _k_air: float = field(default=0.0, init=False)

    def __post_init__(self) -> None:
        self._k_air = self.air_rise_at_rated_k / (_P_AT_RATED_W ** AIR_CONV_EXPONENT)

    # ------------------------------------------------------------ factories

    @classmethod
    def for_joint(cls, joint, seed: int, *, air_rise_at_rated_k: float = AIR_RISE_AT_RATED_K
                  ) -> "ThermalModel":
        """Build a model for an :class:`assets.Joint`.

        The scatter is deliberately split into a **group** part and a **joint**
        part, and the split is the physics, not a convenience.

        Three phases of one outgoing way are the same lug, on the same cable
        size, crimped by the same crew on the same day, in the same air pocket
        200 mm apart.  Their heat-spreading path is therefore nearly identical -
        R_th and the convection exponent belong to the *group*, with only a
        small per-joint jitter.  What genuinely differs bolt to bolt is the
        contact resistance, because torque does.

        This is what makes three siblings a valid baseline on installation day
        with no history at all.  Drawing R_th independently per joint would
        manufacture a large load-dependent offset between siblings that a real
        panel does not have, and would make the simulator harder to detect in
        than the field.
        """
        g = tag(joint.sibling_group)
        s = tag(joint.key)
        r_th = (R_TH_LUG_LO_K_PER_W
                + (R_TH_LUG_HI_K_PER_W - R_TH_LUG_LO_K_PER_W) * _u(seed, g, 1)
                + R_TH_JOINT_JITTER_K_PER_W * (2.0 * _u(seed, s, 1) - 1.0))
        r_th = min(R_TH_LUG_HI_K_PER_W, max(R_TH_LUG_LO_K_PER_W, r_th))
        n = 0.75 + 0.15 * _u(seed, g, 2) + N_JOINT_JITTER * (2.0 * _u(seed, s, 2) - 1.0)
        n = min(0.90, max(0.75, n))
        tau_j = (5.0 + 35.0 * _u(seed, g, 3)) * 60.0 * (0.92 + 0.16 * _u(seed, s, 3))
        tau_a = (45.0 + 45.0 * _u(seed, g, 4)) * 60.0
        return cls(
            joint_key=joint.key,
            rated_a=joint.rated_a,
            r_th_local=r_th,
            tau_joint_s=tau_j,
            tau_air_s=tau_a,
            conv_exponent=n,
            air_rise_at_rated_k=air_rise_at_rated_k,
            seed=seed,
        )

    # ----------------------------------------------------------------- step

    def steady_air_rise_k(self, panel_load_factor: float, vent_factor: float = 1.0) -> float:
        """Cabinet air rise above ambient, kelvin.

        ``vent_factor`` is the fraction of nominal ventilation effectiveness.
        Blocking the louvres does not change the heat input, it changes the
        removal, so the rise scales as 1/vent_factor.
        """
        p = panel_loss_w(panel_load_factor)
        return self._k_air * (p ** AIR_CONV_EXPONENT) / max(0.05, vent_factor)

    def local_air_adder_k(self, pole_current_a: float, pole_rated_a: float,
                          vent_factor: float = 1.0) -> float:
        """Extra air temperature under this joint's own fuse pole."""
        if pole_rated_a <= 0.0:
            return 0.0
        f = pole_current_a / pole_rated_a
        p_pole = FUSE_POLE_LOSS_W.get(int(pole_rated_a), 20.0) * f * f
        if p_pole <= 0.0:
            return 0.0
        return K_POLE_LOCAL * (p_pole ** AIR_CONV_EXPONENT) / max(0.05, vent_factor)

    def step(
        self,
        ts: float,
        dt_s: float,
        current_a: float,
        ambient_c: float,
        r_joint_uohm: float,
        *,
        panel_load_factor: float | None = None,
        pole_current_a: float | None = None,
        pole_rated_a: float | None = None,
        vent_factor: float = 1.0,
        air_offset_k: float = 0.0,
        air_c_override: float | None = None,
    ) -> dict[str, float]:
        """Advance both nodes by ``dt_s`` seconds and return the state.

        Parameters
        ----------
        current_a
            Current through **this joint**.
        ambient_c
            Substation-room air temperature (the outdoor/indoor ambient, not the
            cabinet air).
        r_joint_uohm
            Total contact resistance of the joint, microohm.  Healthy is 2-5.
        panel_load_factor
            Whole-panel load factor driving the cabinet air node.  Defaults to
            this joint's own ``current_a / rated_a`` when the caller has no
            panel-level figure, which is the ``has_analyser=False`` case.
        vent_factor
            1.0 normal, below 1.0 for a blocked ventilation path.
        air_offset_k
            Direct additive offset on the air node, for scenarios that heat the
            whole cabinet without changing the load.
        air_c_override
            Use this cabinet air temperature instead of integrating one.  The
            panel simulator owns a single air node and passes it to all forty
            joints, because a panel has one volume of air, not forty.
        """
        lf = panel_load_factor if panel_load_factor is not None else (
            current_a / max(1e-6, self.rated_a)
        )
        pc = pole_current_a if pole_current_a is not None else current_a
        pr = pole_rated_a if pole_rated_a is not None else self.rated_a

        if air_c_override is not None:
            # One cabinet has one air node.  When the panel owns it, every joint
            # shares the same value instead of integrating 40 slightly different
            # copies of the same physics.
            self.t_air_c = air_c_override
        else:
            air_target = ambient_c + self.steady_air_rise_k(lf, vent_factor) + air_offset_k
            if self.t_air_c != self.t_air_c:  # NaN -> cold start at steady state
                self.t_air_c = air_target
            a_air = 1.0 - math.exp(-max(0.0, dt_s) / self.tau_air_s)
            self.t_air_c += (air_target - self.t_air_c) * a_air

        local_air = self.t_air_c + self.local_air_adder_k(pc, pr, vent_factor)

        p_joint = current_a * current_a * r_joint_uohm * 1e-6
        rise_ss = joint_rise_k(p_joint, self.r_th_local, self.conv_exponent)
        joint_target = local_air + rise_ss
        if self.t_joint_c != self.t_joint_c:
            self.t_joint_c = joint_target
        a_j = 1.0 - math.exp(-max(0.0, dt_s) / self.tau_joint_s)
        self.t_joint_c += (joint_target - self.t_joint_c) * a_j

        return {
            "t_joint_c": self.t_joint_c,
            "t_air_c": self.t_air_c,
            "t_local_air_c": local_air,
            "dt_excess_k": self.t_joint_c - local_air,
            "dt_excess_ss_k": rise_ss,
            "dt_air_k": self.t_air_c - ambient_c,
            "p_joint_w": p_joint,
            "p_panel_w": panel_loss_w(lf),
            "theta_k": theta_from_rise(self.t_joint_c - local_air, current_a, self.rated_a),
        }

    def prime(self, current_a: float, ambient_c: float, r_joint_uohm: float,
              **kw) -> dict[str, float]:
        """Jump straight to steady state.  Used at the head of a backfill so the
        first day of history is not a warm-up transient."""
        self.t_air_c = float("nan")
        self.t_joint_c = float("nan")
        return self.step(0.0, 0.0, current_a, ambient_c, r_joint_uohm, **kw)


def _u(seed: int, *parts: int) -> float:
    """Uniform 0..1 from the same hash family as the load model."""
    from panogoz.sim.load import _u01

    return _u01(seed, *parts)


# --------------------------------------------------------------------------
# Detectability, straight from the brief's arithmetic
# --------------------------------------------------------------------------

SIGMA_TC_PAIR_K = 0.2      #: sibling-differential noise, thermocouple/TMP117 pair
SIGMA_IR_PAIR_K = 0.8      #: sibling-differential noise, MLX90640 pixel pair


def theta_min_k(load_factor: float, sigma_pair_k: float = SIGMA_TC_PAIR_K) -> float:
    """Smallest theta visible at 3 sigma when the panel is at load factor ``f``.

    ``theta_min(f) = 3 sigma / f^2``.  Below f ~ 0.35 the system is in reduced
    sensitivity and must say so on the screen rather than reporting a quiet
    green panel it cannot actually see into.
    """
    f = max(1e-6, load_factor)
    return 3.0 * sigma_pair_k / (f * f)


SENSITIVITY_FLOOR_F = 0.35


if __name__ == "__main__":  # pragma: no cover
    print("PANO GOZ · thermal model self-test")
    print("=" * 78)

    print("\nThermal resistances")
    print(f"  busbar fin, h=5  W/m2K : {busbar_r_th_k_per_w(5.0):.3f} K/W")
    print(f"  busbar fin, h=8  W/m2K : {busbar_r_th_k_per_w(8.0):.3f} K/W")
    print(f"  busbar fin, h=12 W/m2K : {busbar_r_th_k_per_w(12.0):.3f} K/W")
    print(f"  -> interval {BUSBAR_R_TH_LO_K_PER_W:.2f}-{BUSBAR_R_TH_HI_K_PER_W:.2f} K/W"
          f"  (expected 0.24-0.38; 3.44 K/W is wrong by ~10x)")
    print(f"  240 mm2 cable lug      : {R_TH_LUG_LO_K_PER_W:.1f}-{R_TH_LUG_HI_K_PER_W:.1f} K/W")

    print("\nDocumented failure cases")
    for label, i, r, rlo, rhi in (
        ("main busbar joint, healthy 3 uohm @2312 A", 2312.0, 3.0,
         BUSBAR_R_TH_LO_K_PER_W, BUSBAR_R_TH_HI_K_PER_W),
        ("main busbar joint, 50 uohm  @2312 A", 2312.0, 50.0,
         BUSBAR_R_TH_LO_K_PER_W, BUSBAR_R_TH_HI_K_PER_W),
        ("400 A feeder lug, healthy 3 uohm", 400.0, 3.0,
         R_TH_LUG_LO_K_PER_W, R_TH_LUG_HI_K_PER_W),
        ("400 A feeder lug, 50 uohm", 400.0, 50.0,
         R_TH_LUG_LO_K_PER_W, R_TH_LUG_HI_K_PER_W),
    ):
        p = i * i * r * 1e-6
        print(f"  {label:<42} P={p:7.1f} W   dT={p*rlo:6.1f}-{p*rhi:6.1f} K")
    lo, hi = excess_r_interval_uohm(8.0 * R_TH_LUG_NOM_K_PER_W, 400.0)
    print(f"  inversion check: theta={8.0*R_TH_LUG_NOM_K_PER_W:.1f} K at 400 A"
          f" -> dR interval {lo:.1f}-{hi:.1f} uohm, brackets the 50 uohm injected")
    print("  (never a single number: R_th,local is only known to a factor of two)")

    print("\nResidual load dependence of theta, f^(2(n-1)) with n=0.82")
    print("  " + "  ".join(f"f={f:.2f}:{theta_load_bias(f):.3f}x"
                           for f in (1.0, 0.85, 0.70, 0.55, 0.40)))

    print("\nIn-panel heat budget (10 live ways: 5x250 A + 5x400 A, 30 poles)")
    print(f"  {'load':<8}{'busbar W':>10}{'fuses W':>10}{'total W':>10}{'dT air K':>10}")
    tm = ThermalModel(rated_a=400.0)
    for lf in (0.10, 0.25, 0.40, 0.55, 0.70, 0.85, 1.00):
        bus = BUSBAR_LOSS_AT_RATED_W * lf * lf
        fus = fuse_loss_w(lf)
        print(f"  {lf:<8.2f}{bus:>10.0f}{fus:>10.0f}{bus+fus:>10.0f}"
              f"{tm.steady_air_rise_k(lf):>10.1f}")
    print(f"  fuse share at lf=0.55: {100*fuse_loss_w(0.55)/panel_loss_w(0.55):.0f} %"
          f"  ({fuse_loss_w(0.55)/30:.1f} W per pole, 5-15 W is the expected band)")
    print(f"  blocked ventilation (vent=0.35) at lf=0.55:"
          f" {tm.steady_air_rise_k(0.55, 0.35):.1f} K vs {tm.steady_air_rise_k(0.55):.1f} K")

    print("\nStep response, 400 A lug, ambient 25 C, panel at 55 %")
    tm = ThermalModel(rated_a=400.0, tau_joint_s=15 * 60, tau_air_s=60 * 60)
    tm.prime(220.0, 25.0, 3.0, panel_load_factor=0.55)
    print(f"  primed: air {tm.t_air_c:.2f} C   joint {tm.t_joint_c:.2f} C")
    print(f"  {'t (min)':>8}{'air C':>9}{'joint C':>9}{'dT exc':>9}{'theta K':>9}")
    for minute in range(0, 181, 15):
        r = tm.step(minute * 60.0, 900.0 if minute else 0.0, 220.0, 25.0,
                    3.0 if minute < 60 else 50.0, panel_load_factor=0.55)
        print(f"  {minute:>8}{r['t_air_c']:>9.2f}{r['t_joint_c']:>9.2f}"
              f"{r['dt_excess_k']:>9.2f}{r['theta_k']:>9.2f}")

    print("\nSibling-differential noise budget (10 000 draws, 60 s apart)")
    n = 10000
    ts = [i * 60.0 for i in range(n)]
    d_elec = [tmp117_read(40.0, 7, 1, t) - tmp117_read(40.0, 7, 2, t) for t in ts]
    d_mount = [mount_micro_k(7, 1, t) - mount_micro_k(7, 2, t) for t in ts]
    d_tc = [a + b for a, b in zip(d_elec, d_mount)]
    d_ir = [mlx90640_read(40.0, 7, 1, t) - mlx90640_read(40.0, 7, 2, t) for t in ts]

    def stat(d):
        m = sum(d) / len(d)
        return m, math.sqrt(sum((x - m) ** 2 for x in d) / (len(d) - 1))

    for label, d, want in (
        ("TMP117 electronics", d_elec, "quantisation and noise only"),
        ("mounting micro", d_mount, "clip seating, contact, air pocket"),
        ("CONTACT PAIR", d_tc, "design sigma_m = 0.2 K"),
        ("MLX90640 pixel pair", d_ir, "design sigma_m = 0.8 K"),
    ):
        m, sd = stat(d)
        print(f"  {label:<20} mean {m:+.4f} K   sd {sd:.4f} K   ({want})")
    print("  The fixed part of each mean is removed once by the commissioning")
    print("  baseline; what limits detection is the sd, and for a contact pair the")
    print("  mounting term dominates the electronics by more than an order of")
    print("  magnitude.  Quoting the data-sheet accuracy as the system sensitivity")
    print("  would overstate it by exactly that factor.")
    print(f"  TMP117 LSB {TMP117_LSB_C*1000:.4f} mK   MLX90640 LSB {MLX90640_LSB_C*1000:.0f} mK")

    print("\nDetectability, theta_min(f) = 3 sigma / f^2")
    print(f"  {'f':>6}{'TC (0.2 K)':>13}{'IR (0.8 K)':>13}   state")
    for f in (0.85, 0.60, 0.40, 0.35, 0.20):
        state = "OK" if f >= SENSITIVITY_FLOOR_F else "SENSITIVITY_LOW"
        print(f"  {f:>6.2f}{theta_min_k(f):>13.2f}{theta_min_k(f, SIGMA_IR_PAIR_K):>13.2f}"
              f"   {state}")
