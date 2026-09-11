"""Asset model for the TEDAS 1600 kVA LV distribution panel.

Every dimension, rating and clause reference in this file is traceable to the
documents supplied with the hackathon brief:

  * TEDAS-MLZ/2003-06.B "AG Dagitim Panolari Teknik Sartnamesi"
  * EK-I/8  Tablo 8  (printed p.34)  - 1600 kVA hardware list
  * EK-II/14         (printed p.51)  - 1250-1600 kVA dahili tip panel drawing
  * Tablo 1 / 2 / 3a / 3b            - service conditions and ratings

This module is the single source of truth for the digital twin geometry, the
device kit and the sibling (peer) grouping used by the theta detector.  The
simulator, the detector, the SCADA ICD and the UI all import from here, so a
number can never disagree between the demo screen and the register map.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict
from typing import Literal

# --------------------------------------------------------------------------
# Panel envelope and electrical ratings
# --------------------------------------------------------------------------

#: Outer dimensions, mm. EK-II/14 dimension table (A/B/C), tolerances +100/-0,
#: +100/-0, +50/-0.  1600 kVA exists only as a dahili (indoor) type (Madde 2.1.3).
PANEL_W_MM = 1600
PANEL_H_MM = 1500
PANEL_D_MM = 450

#: Minimum clear cable zone at the bottom of the panel, mm.
#: EK-II/14 carries the note "En az 400mm"; Madde 2.2.8.6 Not:2 leaves the panel
#: bottom fully open with no cable glands.  This compartment is the ONLY volume
#: the PANO GOZ day-1 kit occupies.
CABLE_COMPARTMENT_MIN_MM = 400

#: Rated values.  Tablo 2 (231/400 V, 3-phase 4-wire, 50 Hz, Uimp 8 kV) and
#: Tablo 3a (main busbar rated current) / Tablo 3b (prospective short circuit).
RATED_KVA = 1600.0
NOMINAL_LL_VOLTAGE = 400.0
NOMINAL_LN_VOLTAGE = 231.0
NOMINAL_FREQUENCY = 50.0
IMPULSE_WITHSTAND_KV = 8.0

#: Main busbar rated current, A.  Tablo 3a prints 2312 A for 1600 kVA.
#: The arithmetic check S/(sqrt(3)*U) = 1_600_000/(sqrt(3)*400) = 2309.4 A agrees.
MAIN_BUSBAR_RATED_A = 2312.0
RATED_CURRENT_CALC_A = RATED_KVA * 1000.0 / (math.sqrt(3.0) * NOMINAL_LL_VOLTAGE)

#: Prospective short circuit at the panel input.  Tablo 3b, based on %Uk = 6
#: for 800-1600 kVA transformers.
ISC_RMS_KA = 38.0
ISC_PEAK_KA = 80.0
ISC_COS_PHI = 0.25

#: Main busbar: 2 x (100 x 10) mm2 tinned electrolytic copper per phase.
#: EK-I/8 Tablo 8 + Madde 2.2.10.2.  Neutral cross-section equals the phase
#: cross-section.  Tin plating >= 3 micron, which is precisely why we never aim
#: an infrared sensor at bare bar: tinned copper has an emissivity around 0.05.
BUSBAR_BARS_PER_PHASE = 2
BUSBAR_BAR_W_MM = 100.0
BUSBAR_BAR_T_MM = 10.0
BUSBAR_AREA_MM2 = BUSBAR_BARS_PER_PHASE * BUSBAR_BAR_W_MM * BUSBAR_BAR_T_MM  # 2000
BUSBAR_TIN_PLATING_MIN_UM = 3.0
COPPER_CONDUCTIVITY_M_PER_OHM_MM2 = 56.0

#: "Ana bara terminalleri arasi mesafe 185 mm olacaktir" - EK-I/8, DSYA tipi row.
#: With a 100 mm bar height this leaves roughly 85 mm of clear air between
#: adjacent phase bars.  That 85 mm is the exclusion zone in the mounting drawing.
BUSBAR_TERMINAL_PITCH_MM = 185.0
BUSBAR_CLEAR_GAP_MM = BUSBAR_TERMINAL_PITCH_MM - BUSBAR_BAR_W_MM  # 85.0, derived

#: Main metering current transformer.  EK-I/8 Tablo 8, 1600 kVA column.
#: Note it measures the INCOMER only: no outgoing feeder has a utility CT, which
#: is why every PANO GOZ thermal clip carries its own split-core CT.
MAIN_CT_PRIMARY_A = 2500.0
MAIN_CT_SECONDARY_A = 5.0
MAIN_CT_RATIO = MAIN_CT_PRIMARY_A / MAIN_CT_SECONDARY_A  # 500.0

#: Auxiliary circuit protection, EK-I/8 Tablo 8.  The 6 A gG "Ic Ihtiyac"
#: circuit feeds the single-phase 10 A socket (Madde 2.2.12) that powers the
#: gateway.  The 2 A gG "Olcu Devresi" feeds the measurement circuit.
AUX_TM_INTERNAL_FUSE_A = 20
AUX_INTERNAL_FUSE_A = 6
AUX_MEASUREMENT_FUSE_A = 2

# --------------------------------------------------------------------------
# Service conditions - Tablo 1, Madde 1.4 (dahili / indoor column)
# --------------------------------------------------------------------------

AMBIENT_MAX_C = 40.0          #: absolute maximum ambient
AMBIENT_MEAN_24H_MAX_C = 35.0  #: 24 hour mean maximum
AMBIENT_MIN_INDOOR_C = -5.0
AMBIENT_MIN_OUTDOOR_C = -25.0
ALTITUDE_MAX_M = 2000
POLLUTION_DEGREE_INDOOR = 2
RH_AT_40C_PCT = 50.0
IP_INDOOR = "IP2X"             #: Madde 2.2.2
SEPARATION_FORM = "2B"         #: Madde 2.2.6.1, TS EN 61439-2


# --------------------------------------------------------------------------
# Outgoing ways (DSYA) - EK-I/8 Tablo 8, 1600 kVA column
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Feeder:
    """One outgoing DSYA way.

    ``rated_a`` is the DSYA nominal rating; ``spare`` marks the two "Yedek"
    positions which Madde 2.2.9.vii requires to be left physically empty with
    hand-removable covers.
    """

    index: int                 #: 1-based way number as printed on the panel
    name: str
    rated_a: int
    busono_boy: str            #: fuse-link size, "1 Boy" / "2 Boy" / "00 Boy"
    spare: bool = False
    x_mm: float = 0.0          #: horizontal centre on the EK-II/14 front view

    @property
    def key(self) -> str:
        return f"C{self.index:02d}"


#: EK-II/14 shows 12 DSYA strips at a measured ~100 mm pitch spanning
#: x = 38..1240 mm.  EK-I/8 gives the composition: 5 x 250 A (1 Boy) +
#: 5 x 400 A (2 Boy) + 2 Yedek.
_FEEDER_PITCH_MM = 100.0
_FEEDER_X0_MM = 88.0

FEEDERS: tuple[Feeder, ...] = tuple(
    Feeder(
        index=i + 1,
        name=f"Cikis {i + 1}",
        rated_a=(250 if i < 5 else 400),
        busono_boy=("1 Boy" if i < 5 else "2 Boy"),
        spare=(i >= 10),
        x_mm=_FEEDER_X0_MM + i * _FEEDER_PITCH_MM,
    )
    for i in range(12)
)

#: Street lighting is a separate section: 160 A DSYA (00 Boy) with an AC-5a
#: contactor and up to 4 outputs, plus a class 0.5 OSOS-capable meter.
STREET_LIGHTING_DSYA_A = 160
STREET_LIGHTING_MAX_OUTPUTS = 4

PHASES: tuple[str, ...] = ("L1", "L2", "L3")
CONDUCTORS: tuple[str, ...] = ("L1", "L2", "L3", "N")

#: Phase identification colours, Madde 2.2.10.5.  Used by the UI so the digital
#: twin matches what the crew actually sees inside the panel.
PHASE_COLOURS = {"L1": "gri", "L2": "siyah", "L3": "kahverengi", "N": "açık mavi"}


@dataclass(frozen=True)
class Joint:
    """One bolted connection we can develop excess resistance at.

    A 1600 kVA panel has, by EK-I/8 and Madde 2.2.10.3:
      * 12 ways x 3 phases  = 36 bolted busbar-to-DSYA joints (busbar chamber)
      * 12 ways x 4 lugs    = 48 bolted cable lugs (bottom compartment)
      * 4 incoming stubs    = the only joints carrying the full 2312 A

    ``zone`` decides whether PANO GOZ can reach it without an outage.  Only
    ``bottom`` joints are instrumented on day 1.
    """

    key: str
    label: str
    feeder_index: int | None
    conductor: str
    zone: Literal["bottom", "busbar", "roof"]
    rated_a: float
    x_mm: float
    y_mm: float

    @property
    def sibling_group(self) -> str:
        """Joints sharing this key form a valid peer set for theta.

        Peers must carry the same current, share the same air, be the same age
        and present the same surface.  The three phases of one feeder satisfy
        all four; the neutral does not (it carries the unbalance plus triplens)
        and therefore forms its own group and is judged by rule H3 instead.
        """
        if self.conductor == "N":
            return f"{self.zone}:N"
        return f"{self.zone}:F{self.feeder_index:02d}"


def _build_joints() -> tuple[Joint, ...]:
    out: list[Joint] = []

    # Outgoing cable lugs.  EK-II/14 puts the lug row on one line at
    # y ~ 490-510 mm measured from the panel bottom; four lugs per way.
    lug_y = 500.0
    for f in FEEDERS:
        if f.spare:
            continue
        for j, cond in enumerate(CONDUCTORS):
            out.append(
                Joint(
                    key=f"{f.key}-{cond}-PABUC",
                    label=f"{f.name} / {cond} / çıkış pabucu",
                    feeder_index=f.index,
                    conductor=cond,
                    zone="bottom",
                    rated_a=float(f.rated_a),
                    x_mm=f.x_mm + (j - 1.5) * 20.0,
                    y_mm=lug_y,
                )
            )

    # Busbar-to-DSYA bolted joints.  Busbar chamber, y ~ 1045-1440 mm.
    # NOT instrumented on day 1: reaching them means opening a cover over a
    # live 2312 A bar.  Kept in the model so the UI can show them as
    # "izlenmiyor" rather than pretending they do not exist.
    for f in FEEDERS:
        if f.spare:
            continue
        for j, cond in enumerate(PHASES):
            out.append(
                Joint(
                    key=f"{f.key}-{cond}-BARA",
                    label=f"{f.name} / {cond} / bara bağlantısı",
                    feeder_index=f.index,
                    conductor=cond,
                    zone="busbar",
                    rated_a=float(f.rated_a),
                    x_mm=f.x_mm,
                    y_mm=1100.0 + j * 64.0,
                )
            )

    # Incoming busbar stubs through the roof window (Madde 2.2.8.6 Not:1).
    # These four carry the full 2312 A and are the highest-energy joints in the
    # panel.  Also not reachable without an outage.
    for j, cond in enumerate(CONDUCTORS):
        out.append(
            Joint(
                key=f"GIRIS-{cond}",
                label=f"Ana giriş / {cond}",
                feeder_index=None,
                conductor=cond,
                zone="roof",
                rated_a=MAIN_BUSBAR_RATED_A,
                x_mm=485.0 + j * 125.0,
                y_mm=1460.0,
            )
        )

    return tuple(out)


JOINTS: tuple[Joint, ...] = _build_joints()

JOINTS_BY_KEY: dict[str, Joint] = {j.key: j for j in JOINTS}

#: Joints PANO GOZ actually measures on day 1.  Everything else is displayed as
#: uninstrumented.  Being explicit about this is a feature: the brief's hardest
#: constraint is that work inside a live panel is dangerous, and a system that
#: quietly implies coverage it does not have will not survive a field audit.
MONITORED_ZONES: tuple[str, ...] = ("bottom",)


def monitored_joints() -> tuple[Joint, ...]:
    return tuple(j for j in JOINTS if j.zone in MONITORED_ZONES)


def sibling_groups() -> dict[str, tuple[Joint, ...]]:
    """Group monitored joints into peer sets for the theta detector."""
    groups: dict[str, list[Joint]] = {}
    for j in monitored_joints():
        groups.setdefault(j.sibling_group, []).append(j)
    return {k: tuple(v) for k, v in sorted(groups.items())}


# --------------------------------------------------------------------------
# The device kit - frozen at 9 devices per panel
# --------------------------------------------------------------------------

DeviceKind = Literal["TC", "TN-IR", "PD", "GW"]


@dataclass(frozen=True)
class Device:
    """One physical device in the kit.

    ``mount`` names the TEDAS clause that supplies the mounting surface.  This
    is deliberate: every mounting point in the day-1 kit is something the
    specification already requires the panel to have, so nothing is drilled,
    nothing is modified and no type test is invalidated.
    """

    key: str
    kind: DeviceKind
    label: str
    zone: str
    mount: str
    x_mm: float
    y_mm: float
    covers: tuple[str, ...] = field(default_factory=tuple)
    battery: str | None = None


def _build_devices() -> tuple[Device, ...]:
    devs: list[Device] = []

    # Six thermal clips forming TWO sibling triplets.  A triplet is the minimum
    # unit that makes theta work, because theta needs peers.  Feeders 6 and 7
    # (400 A, 2 Boy) are chosen as the two most heavily loaded non-spare ways.
    for t, fidx in enumerate((6, 7)):
        f = FEEDERS[fidx - 1]
        for p, phase in enumerate(PHASES):
            devs.append(
                Device(
                    key=f"TC-{t * 3 + p + 1:02d}",
                    kind="TC",
                    label=f"Kelepçe {t * 3 + p + 1} · {f.name} / {phase}",
                    zone="bottom",
                    mount="kablo damarı üzerine geçmeli kelepçe, pabuçtan 50-100 mm aşağıda",
                    x_mm=f.x_mm + (p - 1.0) * 20.0,
                    y_mm=430.0,
                    covers=(f"{f.key}-{phase}-PABUC",),
                    battery="Li-SOCl2 ER14250 + HLC",
                )
            )

    # One thermal array looking UP at the whole 48-lug row from below.
    devs.append(
        Device(
            key="TN-IR",
            kind="TN-IR",
            label="Termal dizi · 48 pabuç sırası",
            zone="bottom",
            mount="Madde 2.2.1.vi boyasız galvaniz sac · mıknatıs kaide",
            x_mm=640.0,
            y_mm=150.0,
            covers=tuple(j.key for j in JOINTS if j.zone == "bottom"),
            battery="Li-SOCl2 ER14505",
        )
    )

    # One RF / environment node on the earth conductor.
    devs.append(
        Device(
            key="PD-01",
            kind="PD",
            label="RF + ortam düğümü · PE iletkeni",
            zone="bottom",
            mount="Madde 2.2.6.2.iii M12 topraklama saplaması · ayrılabilir HFCT",
            x_mm=1290.0,
            y_mm=230.0,
            covers=(),
            battery="Li-SOCl2 ER26500",
        )
    )

    # The gateway.  Instrument bay, DIN rail, fed from the existing socket.
    devs.append(
        Device(
            key="GW-01",
            kind="GW",
            label="Ağ geçidi · ölçü kolonu",
            zone="instrument",
            mount="Madde 2.2.12 mevcut 10 A priz · DIN ray · Madde 2.2.8.1.iv anten çıkışı",
            x_mm=1450.0,
            y_mm=980.0,
            covers=(),
            battery=None,
        )
    )

    return tuple(devs)


DEVICES: tuple[Device, ...] = _build_devices()
DEVICES_BY_KEY: dict[str, Device] = {d.key: d for d in DEVICES}

#: Frozen. The digital twin draws exactly this many dots, the BOM lists exactly
#: this many parts and the cost model multiplies exactly this many units.  A
#: judge who counts the dots on screen must get the same number as the BOM.
DEVICES_PER_PANEL = len(DEVICES)
assert DEVICES_PER_PANEL == 9, "device kit is frozen at 9 devices per panel"


# --------------------------------------------------------------------------
# Reference current for theta
# --------------------------------------------------------------------------

def reference_current(joint: Joint) -> float:
    """Current that theta is normalised to, in amperes.

    theta is reported as "excess kelvin at reference current".  For an outgoing
    way the natural reference is the DSYA rating, because that is the number a
    substation engineer already thinks in.  For the incomer it is the main
    busbar rating from Tablo 3a.
    """
    return joint.rated_a


# --------------------------------------------------------------------------
# Fleet helpers
# --------------------------------------------------------------------------

#: Aegean and southern-Aegean districts served by ADM and GDZ.  Used only to
#: give the simulated fleet plausible names and coordinates on the map.
FLEET_SITES: tuple[tuple[str, str, float, float], ...] = (
    ("Soke", "ADM", 37.7500, 27.4100),
    ("Nazilli", "ADM", 37.9130, 28.3200),
    ("Kusadasi", "ADM", 37.8600, 27.2600),
    ("Didim", "ADM", 37.3760, 27.2680),
    ("Aydin-Merkez", "ADM", 37.8450, 27.8390),
    ("Denizli-Merkez", "ADM", 37.7765, 29.0864),
    ("Mugla-Merkez", "ADM", 37.2153, 28.3636),
    ("Bodrum", "ADM", 37.0344, 27.4305),
    ("Fethiye", "ADM", 36.6210, 29.1160),
    ("Milas", "ADM", 37.3160, 27.7840),
    ("Izmir-Bornova", "GDZ", 38.4700, 27.2200),
    ("Izmir-Karsiyaka", "GDZ", 38.4600, 27.1100),
    ("Manisa-Merkez", "GDZ", 38.6191, 27.4289),
    ("Turgutlu", "GDZ", 38.4950, 27.7000),
    ("Salihli", "GDZ", 38.4840, 28.1390),
    ("Akhisar", "GDZ", 38.9170, 27.8410),
    ("Odemis", "GDZ", 38.2280, 27.9700),
    ("Tire", "GDZ", 38.0890, 27.7350),
    ("Bergama", "GDZ", 39.1200, 27.1800),
    ("Aliaga", "GDZ", 38.8000, 26.9700),
)


def panel_id(site: str, number: int) -> str:
    return f"{site}-{number:02d}"


def panel_summary() -> dict:
    """A compact description of the asset, for the UI header and the docs."""
    return {
        "tip": "TEDAŞ MLZ.DSYA 1600 kVA dahili tip AG dağıtım panosu",
        "sartname": "TEDAŞ-MLZ/2003-06.B",
        "cizim": "EK-II/14",
        "boyut_mm": [PANEL_W_MM, PANEL_H_MM, PANEL_D_MM],
        "anma_akimi_a": MAIN_BUSBAR_RATED_A,
        "kisa_devre_ka_rms": ISC_RMS_KA,
        "kisa_devre_ka_tepe": ISC_PEAK_KA,
        "ana_bara": f"{BUSBAR_BARS_PER_PHASE}x({BUSBAR_BAR_W_MM:.0f}x{BUSBAR_BAR_T_MM:.0f}) mm² kalaylı elektrolitik bakır",
        "akim_trafosu": f"{MAIN_CT_PRIMARY_A:.0f}/{MAIN_CT_SECONDARY_A:.0f}",
        "koruma_sinifi": IP_INDOOR,
        "ayirma_formu": SEPARATION_FORM,
        "cikis_sayisi": sum(1 for f in FEEDERS if not f.spare),
        "yedek_cikis": sum(1 for f in FEEDERS if f.spare),
        "toplam_civatali_baglanti": len(JOINTS),
        "izlenen_baglanti": len(monitored_joints()),
        "cihaz_sayisi": DEVICES_PER_PANEL,
    }


if __name__ == "__main__":  # pragma: no cover - manual inspection aid
    import json

    print(json.dumps(panel_summary(), indent=2, ensure_ascii=False))
    print()
    print(f"{len(JOINTS)} bolted joints total, {len(monitored_joints())} monitored")
    for name, group in sibling_groups().items():
        print(f"  {name}: {', '.join(g.key for g in group)}")
    print()
    for d in DEVICES:
        print(f"  {d.key:<7} {d.kind:<6} {d.label}")
