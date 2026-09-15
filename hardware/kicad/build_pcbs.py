"""Lay out the 3 PANO GOZ PCBs using gen_pcb.Board.

Same ref designators, same component set and net names as build_boards.py
(the schematic generator) -- every net tag below is looked up by real pin
NAME via pinnum(), never hand-typed as a bare number, so it can't silently
drift from the schematic.

Routing policy (see docs/03 Sec. PCB): every net on every board is tagged
with `tag()` (a real (net N "name") on the right physical pad, checked by
DRC/ratsnest) -- but actual copper (`b.route()`/`mcu_stub_route()`) is only
hand-drawn for SHORT, LOCAL neighbour-pairs (a decoupling cap right next to
its IC pin, crystal load caps, reset pull-up + switch, LDO in/out caps).
Longer, cross-board nets (SWD lines, SPI bus, TC/CT sense lines, Ethernet
lines, ...) are deliberately left as tagged-but-unrouted ratsnest -- this is
the K1.2 "kismi rotalama" scope, not a full autorouted board, and it avoids
hand-drawn traces crossing over unrelated pads with no collision checking.
Board outline size is generous (every board here far exceeds any single
footprint's courtyard) specifically so DRC courtyard/clearance/shorting
violations come from real net-adjacency choices, not from cramped placement.
"""
import os
import sys

from gen_pcb import Board, pinnum

OUT = os.path.dirname(os.path.abspath(__file__))

MCU = "MCU_ST_STM32WL:STM32WLE5CCUx"
LDO = "Regulator_Linear:AP2112K-3.3"
BATT = "Device:Battery_Cell"
DIODE = "Device:D"
CRYSTAL = "Device:Crystal"
SWPUSH = "Switch:SW_Push"
ANTENNA = "Device:Antenna"
MAX31855 = "Sensor_Temperature:MAX31855KASA"
CT_IF = "Generic:CT_Interface"
RF_FE = "Generic:RF_Frontend"
TVS = "Diode:PTVS5V0Z1USK"
W5500 = "Interface_Ethernet:W5500"
HLK = "Converter_ACDC:HLK-PM01"

FP_QFN48 = "Package_DFN_QFN:QFN-48-1EP_7x7mm_P0.5mm_EP5.6x5.6mm"
FP_LQFP48 = "Package_QFP:LQFP-48_7x7mm_P0.5mm"
FP_SOT235 = "Package_TO_SOT_SMD:SOT-23-5"
FP_SOIC8 = "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm"
FP_R0603 = "Resistor_SMD:R_0603_1608Metric"
FP_C0603 = "Capacitor_SMD:C_0603_1608Metric"
FP_CP_SUPERCAP = "Capacitor_THT:CP_Radial_D8.0mm_P3.50mm"
FP_D_SOD123 = "Diode_SMD:D_SOD-123"
FP_D_SOD323 = "Diode_SMD:D_SOD-323"
FP_CRYSTAL = "Crystal:Crystal_SMD_HC49-SD"
FP_HDR2 = "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical"
FP_HDR4 = "Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical"
FP_BNC = "Connector_Coaxial:BNC_Amphenol_031-5539_Vertical"
FP_SMA = "Connector_Coaxial:SMA_Amphenol_132134_Vertical"
FP_DIP6 = "Package_DIP:DIP-6_W7.62mm"
FP_ANT868 = "RF_Antenna:NiceRF_SW868-TH13_868Mhz"
FP_BATT_WIRE = "Generic:Battery_Wireleads"
FP_CT_IF_PCB = "Generic:CT_Interface_PCB"
FP_RF_FE_PCB = "Generic:RF_Frontend_PCB"
FP_RJ45 = "Connector_RJ:RJ45_Hanrun_HR911105A_Horizontal"
FP_FUSE = "Fuse:Fuse_1206_3216Metric"
FP_HLK = "Converter_ACDC:Converter_ACDC_Hi-Link_HLK-PMxx"


def tag(b, ref, sym, key, net):
    b.net(ref, pinnum(sym, key), net)


def mcu_side_point(gp, sym_key, dist, perp_offset=0.0):
    """A point `dist` mm straight out from MCU pin `sym_key`'s own package
    edge -- a safe spot to place the 2-pad passive that connects to it
    (same exit-side logic mcu_local_route uses, so the passive always ends
    up on the side the real pin actually exits from instead of a
    hand-guessed coordinate that might be 180 degrees off). `perp_offset`
    slides the point sideways (along the package edge) so several targets
    on the same side don't collide with each other."""
    px, py = gp[pinnum(MCU, sym_key)]
    cx, cy = gp['_cx'], gp['_cy']
    dx, dy = px - cx, py - cy
    if abs(dx) > abs(dy):
        return (px + (dist if dx > 0 else -dist), py + perp_offset)
    return (px + perp_offset, py + (dist if dy > 0 else -dist))


def mcu_local_route(b, ref, gp, sym_key, target, net, width=0.2, stub=2.0):
    """Local-neighbour route from an MCU pin: exit straight away from the
    package body first (clears neighbouring 0.5mm-pitch pads), then one
    Manhattan bend into the target pad. Only ever called for targets placed
    immediately next to the MCU (decoupling caps, crystal) -- see module
    docstring for the routing-scope policy.

    `stub` MUST match the `dist` passed to mcu_side_point() for this same
    signal when 2+ signals leave the package on the same edge: the escape
    stub is also the row the horizontal bend runs along, so two signals
    escaping to the same row cross each other (give each one its own
    distance -- see the *_section() call sites for the staggered values)."""
    px, py = gp[pinnum(MCU, sym_key)]
    cx, cy = gp['_cx'], gp['_cy']
    dx, dy = px - cx, py - cy
    if abs(dx) > abs(dy):
        ex, ey = px + (stub if dx > 0 else -stub), py
    else:
        ex, ey = px, py + (stub if dy > 0 else -stub)
    b.track(net, px, py, ex, ey, width=width)
    b.route(net, (ex, ey), target, width=width)


def mcu_power_section(b, u1, mcu, sym, c1_xy, dist=20):
    """VR_PA decoupling (always local, always routed). C1 is rotated 180
    degrees so pad 1 (VRPA) faces back toward the MCU the route approaches
    from -- otherwise the approach has to pass pad 2 (GND) first."""
    tag(b, u1, sym, "VR_PA", "VRPA")
    c1, c1p = b.place(FP_C0603, *c1_xy, 180, "C", "100nF")
    tag(b, c1, "Device:C", "1", "VRPA"); tag(b, c1, "Device:C", "2", "GND")
    mcu_local_route(b, u1, mcu, "VR_PA", c1p['1'], "VRPA", stub=dist)
    return c1


def reset_section(b, u1, mcu, r_xy, sw_xy, sw_rot=90, dist=10):
    tag(b, u1, MCU, "NRST", "NRST")
    r1, r1p = b.place(FP_R0603, *r_xy, 0, "R", "10k")
    tag(b, r1, "Device:R", "1", "+3V3"); tag(b, r1, "Device:R", "2", "NRST")
    sw1, sw1p = b.place(FP_HDR2, *sw_xy, sw_rot, "SW", "RESET(SW_Push)")
    tag(b, sw1, SWPUSH, "1", "NRST"); tag(b, sw1, SWPUSH, "2", "GND")
    mcu_local_route(b, u1, mcu, "NRST", r1p['2'], "NRST", stub=dist)
    b.route("NRST", r1p['2'], sw1p['1'])


def swd_header(b, u1, mcu, j_xy, j_rot=90):
    j1, j1p = b.place(FP_HDR4, *j_xy, j_rot, "J", "SWD")
    tag(b, j1, "Connector_Generic:Conn_01x04", "Pin_1", "SWDIO")
    tag(b, j1, "Connector_Generic:Conn_01x04", "Pin_2", "SWCLK")
    tag(b, j1, "Connector_Generic:Conn_01x04", "Pin_3", "GND")
    tag(b, j1, "Connector_Generic:Conn_01x04", "Pin_4", "+3V3")
    tag(b, u1, MCU, "PA13", "SWDIO")
    tag(b, u1, MCU, "PA14", "SWCLK")
    # SWD header sits well away from the MCU on all 3 boards -- net-tagged
    # only (ratsnest), no cross-board hand-routed copper; see module docstring.


def hse_crystal(b, u1, mcu, y_xy, c2_xy, c3_xy):
    tag(b, u1, MCU, "OSC_IN", "OSC_IN")
    tag(b, u1, MCU, "OSC_OUT", "OSC_OUT")
    y1, y1p = b.place(FP_CRYSTAL, *y_xy, 0, "Y", "32MHz")
    tag(b, y1, CRYSTAL, "1", "OSC_IN"); tag(b, y1, CRYSTAL, "2", "OSC_OUT")
    c2, c2p = b.place(FP_C0603, *c2_xy, 0, "C", "12pF")
    c3, c3p = b.place(FP_C0603, *c3_xy, 0, "C", "12pF")
    tag(b, c2, "Device:C", "1", "OSC_IN"); tag(b, c2, "Device:C", "2", "GND")
    tag(b, c3, "Device:C", "1", "OSC_OUT"); tag(b, c3, "Device:C", "2", "GND")
    # Only OSC_IN gets copper: OSC_IN/OSC_OUT exit the QFN only ~0.5mm
    # apart, and Y1's own 2 pads are similarly close -- routing both in
    # parallel risks the two straight tracks clipping each other's target
    # pad. OSC_OUT stays tagged (real ratsnest, no track); see docstring.
    mcu_local_route(b, u1, mcu, "OSC_IN", y1p['1'], "OSC_IN")
    b.route("OSC_IN", y1p['1'], c2p['1'])


def battery_power_section(b, bt_xy, d_xy, u2_xy, c4_xy, c5_xy, c6_xy):
    # BT1 -- D1 -- U2 laid out collinear (D1 unrotated, K/A pads left-right
    # in the same direction as the signal flow) so neither route needs a
    # bend near D1's own two closely-pitched SOD-123 pads. BT1 itself is
    # rotated 180 degrees so its VBATT_RAW pad (not its GND pad) faces D1 --
    # otherwise the straight VBATT_RAW track runs right through BT1's own
    # GND pad on the way out.
    bt1, bt1p = b.place(FP_BATT_WIRE, *bt_xy, 180, "BT", "LiSOCl2 3.6V")
    tag(b, bt1, BATT, "+", "VBATT_RAW"); tag(b, bt1, BATT, "-", "GND")
    d1, d1p = b.place(FP_D_SOD123, *d_xy, 0, "D", "reverse-protect")
    tag(b, d1, DIODE, "K", "VBATT_RAW"); tag(b, d1, DIODE, "A", "VBATT")
    b.route("VBATT_RAW", bt1p['1'], d1p['1'])
    u2, u2p = b.place(FP_SOT235, *u2_xy, 0, "U", "AP2112K-3.3")
    tag(b, u2, LDO, "VIN", "VBATT"); tag(b, u2, LDO, "GND", "GND")
    tag(b, u2, LDO, "EN", "VBATT"); tag(b, u2, LDO, "VOUT", "+3V3")
    # via_l_first=False: reach VIN's own row before turning towards the
    # LDO, so the approach never cuts across GND/EN (pins 2/3, stacked
    # 0.95mm below VIN on the same SOT-23-5 edge).
    b.route("VBATT", d1p['2'], u2p[pinnum(LDO, "VIN")], via_l_first=False)
    c4, c4p = b.place(FP_C0603, *c4_xy, 0, "C", "1uF")
    tag(b, c4, "Device:C", "1", "VBATT"); tag(b, c4, "Device:C", "2", "GND")
    c5, c5p = b.place(FP_C0603, *c5_xy, 0, "C", "1uF")
    tag(b, c5, "Device:C", "1", "+3V3"); tag(b, c5, "Device:C", "2", "GND")
    b.route("+3V3", u2p[pinnum(LDO, "VOUT")], c5p['1'])
    c6, c6p = b.place(FP_CP_SUPERCAP, *c6_xy, 0, "C", "1F supercap")
    tag(b, c6, "Device:C_Polarized", "1", "+3V3"); tag(b, c6, "Device:C_Polarized", "2", "GND")
    b.route("+3V3", c5p['1'], c6p['1'])
    return u2, u2p


def rf_antenna_section(b, u1, mcu, c7_xy, ae_xy, keepout_r=9):
    # RFO_HP, VR_PA and NRST all exit the QFN within ~3mm of each other on
    # the same edge -- with 3 signals that close, routing all 3 the last
    # mile to the MCU pin makes their escape lanes cross. RF_HP is the one
    # left tagged-only (no track) here; VR_PA/NRST keep their copper (see
    # mcu_power_section/reset_section) since decoupling/reset are the more
    # electrically important of the three to actually show routed.
    tag(b, u1, MCU, "RFO_HP", "RF_HP")
    c7, c7p = b.place(FP_C0603, *c7_xy, 0, "C", "2.2pF match")
    tag(b, c7, "Device:C", "1", "RF_HP"); tag(b, c7, "Device:C", "2", "ANT")
    ae1, ae1p = b.place(FP_ANT868, *ae_xy, 0, "AE", "PCB chip antenna 868MHz")
    tag(b, ae1, ANTENNA, "A", "ANT")
    b.route("ANT", c7p['2'], ae1p['1'])
    b.keepout_circle(ae_xy[0], ae_xy[1], keepout_r, label="Antenna keepout (868MHz)")


def external_antenna_section(b, u1, mcu, c7_xy, sma_xy):
    # Gateway board only: schematic (build_boards.py build_gateway) wires
    # RFO_HP -> 2.2pF match -> an external SMA connector ("harici anten",
    # see docs/02 Sec.6 -- the cabinet's sheet-steel enclosure attenuates RF,
    # so the gateway's antenna is pigtailed outside the enclosure), NOT an
    # onboard chip antenna. Deliberately NOT rf_antenna_section() above --
    # that helper places Device:Antenna/FP_ANT868, which has no counterpart
    # in the gateway schematic (only tc-node/ir-pd-node place a real
    # Device:Antenna symbol). No RF near-field keepout here either: that
    # zone exists for an onboard radiator's near field, not a connector.
    tag(b, u1, MCU, "RFO_HP", "RF_HP")
    c7, c7p = b.place(FP_C0603, *c7_xy, 0, "C", "2.2pF match")
    tag(b, c7, "Device:C", "1", "RF_HP"); tag(b, c7, "Device:C", "2", "ANT")
    j2, j2p = b.place(FP_SMA, *sma_xy, 0, "J", "SMA (harici anten)")
    tag(b, j2, "Connector:Conn_Coaxial_Small", "In", "ANT")
    tag(b, j2, "Connector:Conn_Coaxial_Small", "Ext", "GND")
    b.route("ANT", c7p['2'], j2p[pinnum("Connector:Conn_Coaxial_Small", "In")])


# ---------------------------------------------------------------------------
def build_tc_node():
    b = Board(125, 110, "PANO GOZ - TC Dugumu PCB (Termal-Akim)")

    u1, mcu = b.place(FP_QFN48, 55, 30, 0, "U", "STM32WLE5CCUx")
    mcu['_cx'], mcu['_cy'] = 55, 30
    for k in ("VDD", "44", "VDDA", "VBAT", "VDDPA", "VDDRF", "VDDRF1V55", "VDDSMPS"):
        tag(b, u1, MCU, k, "+3V3")
    for k in ("VSS", "VSSSMPS"):
        tag(b, u1, MCU, k, "GND")
    tag(b, u1, MCU, "VFBSMPS", "+3V3")
    tag(b, u1, MCU, "PA5", "SPI1_SCK")
    tag(b, u1, MCU, "PA6", "SPI1_MISO")
    tag(b, u1, MCU, "PA7", "SPI1_MOSI")
    tc_cs = ["PA4", "PA15", "PC13"]
    ct_adc = ["PB3", "PB4", "PB2"]
    # VR_PA/NRST/RFO_HP all exit the QFN-48 on its SOUTH edge and OSC_IN/
    # OSC_OUT on its EAST edge (real footprint geometry, checked with
    # pinnum()+gen_pcb._resolve() before writing this) -- every local
    # target below is placed via mcu_side_point() on the matching side
    # instead of a hand-guessed coordinate, so mcu_local_route()'s exit
    # stub never has to detour back past the package to reach it.
    mcu_power_section(b, u1, mcu, MCU, mcu_side_point(mcu, "VR_PA", 20, -20))
    reset_section(b, u1, mcu, mcu_side_point(mcu, "NRST", 10, 0), mcu_side_point(mcu, "NRST", 10, 8))
    swd_header(b, u1, mcu, (100, 15))
    hse_crystal(b, u1, mcu, mcu_side_point(mcu, "OSC_IN", 15),
                mcu_side_point(mcu, "OSC_IN", 15, -8), mcu_side_point(mcu, "OSC_IN", 15, 8))
    battery_power_section(b, (10, 20), (24, 20), (40, 20), (34, 26), (46, 26), (40, 36))
    c7ae = mcu_side_point(mcu, "RFO_HP", 24, 20)
    rf_antenna_section(b, u1, mcu, c7ae, (c7ae[0] + 15, c7ae[1]))

    # 3x thermocouple channels (MAX31855, shared SPI1, per-channel CS) and
    # 3x CT clip-on channels (lumped CT_Interface block): fully net-tagged
    # for DRC/ratsnest, but the sense-line copper (T+/T-, CT+/CT-) is left
    # unrouted -- these headers sit right next to a multi-pad component
    # (SOIC-8 / the 5-pad CT_Interface block) and a hand-drawn straight
    # track from one of that component's pads grazes its own neighbouring
    # pads too easily; see module docstring on routing scope.
    for i in range(3):
        bx = 20 + i * 34
        by = 65
        ui, uip = b.place(FP_SOIC8, bx, by, 0, "U", f"MAX31855KASA (TC{i+1})")
        tag(b, ui, MAX31855, "VCC", "+3V3"); tag(b, ui, MAX31855, "GND", "GND")
        tag(b, ui, MAX31855, "SCK", "SPI1_SCK"); tag(b, ui, MAX31855, "SO", "SPI1_MISO")
        tag(b, ui, MAX31855, "CS", f"TC{i+1}_CS")
        tag(b, ui, MAX31855, "T+", f"TC{i+1}_T+"); tag(b, ui, MAX31855, "T-", f"TC{i+1}_T-")
        tag(b, u1, MCU, tc_cs[i], f"TC{i+1}_CS")
        ji, jip = b.place(FP_HDR2, bx, by + 16, 0, "J", f"TC{i+1} probe (K-type)")
        tag(b, ji, "Connector_Generic:Conn_01x02", "Pin_1", f"TC{i+1}_T+")
        tag(b, ji, "Connector_Generic:Conn_01x02", "Pin_2", f"TC{i+1}_T-")

    tag(b, u1, MCU, "PA5", "SPI1_SCK")
    tag(b, u1, MCU, "PA6", "SPI1_MISO")

    for i in range(3):
        bx = 20 + i * 34
        by = 90
        ai, aip = b.place(FP_CT_IF_PCB, bx, by, 0, "A", f"CT{i+1}_Interface")
        tag(b, ai, CT_IF, "VCC", "+3V3"); tag(b, ai, CT_IF, "GND", "GND")
        tag(b, ai, CT_IF, "AOUT", f"CT{i+1}_ADC")
        tag(b, u1, MCU, ct_adc[i], f"CT{i+1}_ADC")
        ji, jip = b.place(FP_HDR2, bx + 16, by, 90, "J", f"CT{i+1} clip-on")
        tag(b, ji, "Connector_Generic:Conn_01x02", "Pin_1", f"CT{i+1}+")
        tag(b, ji, "Connector_Generic:Conn_01x02", "Pin_2", f"CT{i+1}-")
        tag(b, ai, CT_IF, "CT+", f"CT{i+1}+"); tag(b, ai, CT_IF, "CT-", f"CT{i+1}-")

    b.edge_rect()
    b.mounting_hole(6, 6)
    b.mounting_hole(119, 6)
    b.gnd_pour()
    b.silk_text("PANO GOZ TC-NODE", 6, 3, size=1.5)
    return b


# ---------------------------------------------------------------------------
def build_ir_pd_node():
    b = Board(120, 105, "PANO GOZ - IR-PD Dugumu PCB (Kismi Desarj/Ark)")

    u1, mcu = b.place(FP_QFN48, 50, 28, 0, "U", "STM32WLE5CCUx")
    mcu['_cx'], mcu['_cy'] = 50, 28
    for k in ("VDD", "44", "VDDA", "VBAT", "VDDPA", "VDDRF", "VDDRF1V55", "VDDSMPS"):
        tag(b, u1, MCU, k, "+3V3")
    for k in ("VSS", "VSSSMPS"):
        tag(b, u1, MCU, k, "GND")
    tag(b, u1, MCU, "VFBSMPS", "+3V3")
    tag(b, u1, MCU, "PB3", "PD_ENV")
    tag(b, u1, MCU, "PA0", "ZC_SIG")

    mcu_power_section(b, u1, mcu, MCU, mcu_side_point(mcu, "VR_PA", 20, -20))
    reset_section(b, u1, mcu, mcu_side_point(mcu, "NRST", 10, 0), mcu_side_point(mcu, "NRST", 10, 8))
    swd_header(b, u1, mcu, (95, 12))
    hse_crystal(b, u1, mcu, mcu_side_point(mcu, "OSC_IN", 15),
                mcu_side_point(mcu, "OSC_IN", 15, -8), mcu_side_point(mcu, "OSC_IN", 15, 8))
    battery_power_section(b, (8, 55), (20, 55), (34, 55), (26, 60), (40, 60), (34, 68))
    c7ae = mcu_side_point(mcu, "RFO_HP", 24, 20)
    rf_antenna_section(b, u1, mcu, c7ae, (c7ae[0] + 15, c7ae[1]))

    # HFCT input chain: BNC -> TVS -> DC-block -> RF frontend (lumped) -> MCU.
    # Net-tagged only (no copper): the BNC/TVS pair's ground-shield pads sit
    # close enough to the signal path that a straight track clips them --
    # same rationale as the TC/CT sense lines; see module docstring.
    j2, j2p = b.place(FP_BNC, 15, 82, 0, "J", "BNC (HFCT30/50)")
    tag(b, j2, "Connector:Conn_Coaxial_Small", "In", "HFCT_IN")
    tag(b, j2, "Connector:Conn_Coaxial_Small", "Ext", "GND")
    d2, d2p = b.place(FP_D_SOD323, 30, 82, 0, "D", "TVS 5V")
    tag(b, d2, TVS, "K", "HFCT_IN"); tag(b, d2, TVS, "A", "GND")
    c8, c8p = b.place(FP_C0603, 42, 82, 0, "C", "1nF DC-block")
    tag(b, c8, "Device:C", "1", "HFCT_IN"); tag(b, c8, "Device:C", "2", "RF_IN")
    a1, a1p = b.place(FP_RF_FE_PCB, 56, 82, 0, "A", "HFCT front-end")
    tag(b, a1, RF_FE, "RFIN", "RF_IN"); tag(b, a1, RF_FE, "VCC", "+3V3")
    tag(b, a1, RF_FE, "GND", "GND"); tag(b, a1, RF_FE, "ENVOUT", "PD_ENV")
    b.route("RF_IN", c8p['2'], a1p[pinnum(RF_FE, "RFIN")])

    # Zero-cross phase reference via optocoupler -- net-tagged, unrouted
    # (same rationale as the TC/CT sense lines: too many small adjacent
    # pads for a hand-drawn straight track to clear safely).
    j3, j3p = b.place(FP_HDR2, 75, 90, 0, "J", "Olcu devresi referansi (LV)")
    tag(b, j3, "Connector_Generic:Conn_01x02", "Pin_1", "ACREF_A")
    tag(b, j3, "Connector_Generic:Conn_01x02", "Pin_2", "ACREF_B")
    r2, r2p = b.place(FP_R0603, 88, 90, 0, "R", "10k (akim sinirlama)")
    tag(b, r2, "Device:R", "1", "ACREF_A"); tag(b, r2, "Device:R", "2", "OPTO_A")
    u3, u3p = b.place(FP_DIP6, 100, 90, 0, "U", "4N25")
    tag(b, u3, "Isolator:4N25", "1", "OPTO_A"); tag(b, u3, "Isolator:4N25", "2", "ACREF_B")
    tag(b, u3, "Isolator:4N25", "4", "GND"); tag(b, u3, "Isolator:4N25", "6", "ZC_SIG")
    r3, r3p = b.place(FP_R0603, 100, 76, 0, "R", "10k pull-up")
    tag(b, r3, "Device:R", "1", "+3V3"); tag(b, r3, "Device:R", "2", "ZC_SIG")

    b.edge_rect()
    b.mounting_hole(6, 6)
    b.mounting_hole(114, 6)
    b.gnd_pour()
    b.silk_text("PANO GOZ IR-PD-NODE", 6, 3, size=1.5)
    return b


# ---------------------------------------------------------------------------
def build_gateway():
    b = Board(140, 115, "PANO GOZ - Gateway Karti PCB")

    u1, mcu = b.place(FP_QFN48, 40, 28, 0, "U", "STM32WLE5CCUx")
    mcu['_cx'], mcu['_cy'] = 40, 28
    for k in ("VDD", "44", "VDDA", "VBAT", "VDDPA", "VDDRF", "VDDRF1V55", "VDDSMPS"):
        tag(b, u1, MCU, k, "+3V3")
    for k in ("VSS", "VSSSMPS"):
        tag(b, u1, MCU, k, "GND")
    tag(b, u1, MCU, "VFBSMPS", "+3V3")
    tag(b, u1, MCU, "PA8", "ETH_SCLK"); tag(b, u1, MCU, "PA5", "ETH_MISO")
    tag(b, u1, MCU, "PA10", "ETH_MOSI"); tag(b, u1, MCU, "PA9", "ETH_CS")
    tag(b, u1, MCU, "PA11", "ETH_INT"); tag(b, u1, MCU, "PA12", "ETH_RST")

    mcu_power_section(b, u1, mcu, MCU, mcu_side_point(mcu, "VR_PA", 20, -20))
    reset_section(b, u1, mcu, mcu_side_point(mcu, "NRST", 10, 0), mcu_side_point(mcu, "NRST", 10, 8))
    swd_header(b, u1, mcu, (85, 12))
    hse_crystal(b, u1, mcu, mcu_side_point(mcu, "OSC_IN", 15),
                mcu_side_point(mcu, "OSC_IN", 15, -8), mcu_side_point(mcu, "OSC_IN", 15, 8))

    # Mains-tap power: fuse -> HLK-PM01 -> LDO 3V3. HLK-PM01's real
    # courtyard is a full mains-isolated module (~37x18mm) -- placed low
    # and to the left, clear of the MCU's south-side local cluster above.
    f1, f1p = b.place(FP_FUSE, 15, 75, 0, "F", "0.5A (modul dali)")
    tag(b, f1, "Device:Fuse", "1", "AC_L_PANEL"); tag(b, f1, "Device:Fuse", "2", "AC_L")
    u4, u4p = b.place(FP_HLK, 15, 88, 0, "U", "HLK-PM01")
    tag(b, u4, HLK, "AC/L", "AC_L"); tag(b, u4, HLK, "AC/N", "AC_N")
    tag(b, u4, HLK, "-Vout", "GND5V"); tag(b, u4, HLK, "+Vout", "V5")
    b.route("AC_L", f1p['2'], u4p[pinnum(HLK, "AC/L")])
    u2, u2p = b.place(FP_SOT235, 60, 88, 0, "U", "AP2112K-3.3")
    tag(b, u2, LDO, "VIN", "V5"); tag(b, u2, LDO, "GND", "GND5V")
    tag(b, u2, LDO, "EN", "V5"); tag(b, u2, LDO, "VOUT", "+3V3")
    # via_l_first=False for the same reason as battery_power_section's VIN
    # approach: land on VIN's / GND's own row before the final horizontal
    # run, so it can't cut across the SOT-23-5's other closely-pitched pins.
    b.route("V5", u4p[pinnum(HLK, "+Vout")], u2p[pinnum(LDO, "VIN")], via_l_first=False)
    b.route("GND5V", u4p[pinnum(HLK, "-Vout")], u2p[pinnum(LDO, "GND")], via_l_first=False)
    c_in, c_in_p = b.place(FP_C0603, 70, 88, 0, "C", "10uF")
    tag(b, c_in, "Device:C", "1", "V5"); tag(b, c_in, "Device:C", "2", "GND5V")
    c_out, c_out_p = b.place(FP_C0603, 76, 88, 0, "C", "1uF")
    tag(b, c_out, "Device:C", "1", "+3V3"); tag(b, c_out, "Device:C", "2", "GND")
    b.route("+3V3", u2p[pinnum(LDO, "VOUT")], c_out_p['1'])

    c7ae = mcu_side_point(mcu, "RFO_HP", 24, 20)
    external_antenna_section(b, u1, mcu, c7ae, (85, 55))

    # W5500 SPI Ethernet controller + support network + 25MHz crystal + RJ45
    u5, u5p = b.place(FP_LQFP48, 105, 55, 0, "U", "W5500")
    tag(b, u5, W5500, "VDD", "+3V3"); tag(b, u5, W5500, "GND", "GND")
    tag(b, u5, W5500, "4", "+3V3"); tag(b, u5, W5500, "3", "GND")
    tag(b, u5, W5500, "SCLK", "ETH_SCLK"); tag(b, u5, W5500, "MISO", "ETH_MISO")
    tag(b, u5, W5500, "MOSI", "ETH_MOSI"); tag(b, u5, W5500, "SCS", "ETH_CS")
    tag(b, u5, W5500, "INT", "ETH_INT"); tag(b, u5, W5500, "RST", "ETH_RST")
    tag(b, u5, W5500, "PMODE0", "GND"); tag(b, u5, W5500, "PMODE1", "GND")
    tag(b, u5, W5500, "PMODE2", "GND")
    tag(b, u5, W5500, "EXRES1", "EXRES1"); tag(b, u5, W5500, "TOCAP", "TOCAP")
    tag(b, u5, W5500, "VBG", "VBG"); tag(b, u5, W5500, "1V2O", "1V2O")
    tag(b, u5, W5500, "TXP", "ETH_TXP"); tag(b, u5, W5500, "TXN", "ETH_TXN")
    tag(b, u5, W5500, "RXP", "ETH_RXP"); tag(b, u5, W5500, "RXN", "ETH_RXN")

    rex, rexp = b.place(FP_R0603, 90, 72, 0, "R", "12k 1% (EXRES1 bias)")
    tag(b, rex, "Device:R", "1", "EXRES1"); tag(b, rex, "Device:R", "2", "GND")
    b.route("EXRES1", u5p[pinnum(W5500, "EXRES1")], rexp['1'])
    ctc, ctcp = b.place(FP_C0603, 97, 72, 0, "C", "2.2uF (TOCAP)")
    tag(b, ctc, "Device:C", "1", "TOCAP"); tag(b, ctc, "Device:C", "2", "GND")
    cvbg, cvbgp = b.place(FP_C0603, 104, 72, 0, "C", "0.1uF (VBG)")
    tag(b, cvbg, "Device:C", "1", "VBG"); tag(b, cvbg, "Device:C", "2", "GND")
    c1v2, c1v2p = b.place(FP_C0603, 111, 72, 0, "C", "1uF (1V2O)")
    tag(b, c1v2, "Device:C", "1", "1V2O"); tag(b, c1v2, "Device:C", "2", "GND")

    yw, ywp = b.place(FP_CRYSTAL, 130, 45, 0, "Y", "25MHz (W5500)")
    tag(b, yw, CRYSTAL, "1", "ETH_XI"); tag(b, yw, CRYSTAL, "2", "ETH_XO")
    tag(b, u5, W5500, "XI_CLKIN", "ETH_XI"); tag(b, u5, W5500, "XO", "ETH_XO")
    cw1, cw1p = b.place(FP_C0603, 122, 52, 0, "C", "18pF")
    cw2, cw2p = b.place(FP_C0603, 138, 52, 0, "C", "18pF")
    tag(b, cw1, "Device:C", "1", "ETH_XI"); tag(b, cw1, "Device:C", "2", "GND")
    tag(b, cw2, "Device:C", "1", "ETH_XO"); tag(b, cw2, "Device:C", "2", "GND")
    b.route("ETH_XI", ywp['1'], cw1p['1'])
    b.route("ETH_XO", ywp['2'], cw2p['1'])

    j3, j3p = b.place(FP_RJ45, 100, 88, 0, "J", "RJ45 (magnetics harici)")
    tag(b, j3, "Connector:RJ45", "1", "ETH_TXP"); tag(b, j3, "Connector:RJ45", "2", "ETH_TXN")
    tag(b, j3, "Connector:RJ45", "3", "ETH_RXP"); tag(b, j3, "Connector:RJ45", "4", "ETH_RXN")

    b.edge_rect()
    b.mounting_hole(6, 6)
    b.mounting_hole(134, 6)
    b.gnd_pour()
    b.silk_text("PANO GOZ GATEWAY", 6, 3, size=1.5)
    return b


BOARDS = {
    "tc-node": build_tc_node,
    "ir-pd-node": build_ir_pd_node,
    "gateway": build_gateway,
}

if __name__ == "__main__":
    names = sys.argv[1:] or list(BOARDS.keys())
    for name in names:
        d = os.path.join(OUT, name)
        os.makedirs(d, exist_ok=True)
        board = BOARDS[name]()
        pcb_path = os.path.join(d, f"{name}.kicad_pcb")
        with open(pcb_path, "w", encoding="utf-8") as f:
            f.write(board.render())
        print("wrote", pcb_path)
