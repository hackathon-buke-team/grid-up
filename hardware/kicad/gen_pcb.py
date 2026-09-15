"""PANO GOZ K1.2 -- generates the 3 KiCad PCBs (tc-node, ir-pd-node, gateway).

Same philosophy as gen_schematics.py: every footprint embedded here is
extracted VERBATIM (byte-for-byte S-expression block: outline graphics,
courtyard, silkscreen, real pad geometry, 3D model reference) from the real
KiCad 10.0.6 stock footprint libraries under
C:/Users/mert/AppData/Local/Programs/KiCad/10.0/share/kicad/footprints
-- nothing hand-retyped. Only the footprint's own top-level name and its
Reference/Value silkscreen text are rewritten per placed instance.

Pad NUMBERS on every chosen footprint are cross-checked against the REAL
symbol pin numbers already extracted by gen_schematics.py's _resolve() (both
ultimately come from the same manufacturer datasheet numbering), so this
module imports gen_schematics and reuses its symbol pin tables via `pinnum()`
instead of re-typing net-to-pin maps by hand -- single source of truth for
"which physical pin is net X on".

A handful of parts have no real KiCad-library footprint at all (the LiSOCl2
cell is wire-leaded, not a rigid outline; CT_Interface/RF_Frontend are the
same lumped, non-real blocks already flagged in gen_schematics.py). For
those, and only those, a small custom footprint is hand-built here -- same
documented-simplification policy as the schematic generator.
"""
import math
import os
import re
import sys
import uuid as _uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_schematics import _get as _sym_get  # noqa: E402 -- covers both real + custom lumped symbols

FPROOT = "C:/Users/mert/AppData/Local/Programs/KiCad/10.0/share/kicad/footprints"


def U():
    return str(_uuid.uuid4())


def pinnum(sym_lib_id, key):
    """Real datasheet pin NUMBER for symbol pin `key` (name or number),
    taken from gen_schematics.py's own verified symbol pin table (also
    covers the two lumped Generic: blocks via the same _get() dispatch)."""
    _, pins = _sym_get(sym_lib_id)
    return pins[key][0]


# ---------------------------------------------------------------------------
# Verbatim footprint extraction from the real installed KiCad libraries
# ---------------------------------------------------------------------------
# fp_id ("PrettyLib:BareName", the same form KiCad itself stores on a placed
# board) -> (pretty dir name, bare filename without .kicad_mod)
SOURCE = {
    "Resistor_SMD:R_0603_1608Metric": ("Resistor_SMD", "R_0603_1608Metric"),
    "Capacitor_SMD:C_0603_1608Metric": ("Capacitor_SMD", "C_0603_1608Metric"),
    "Capacitor_THT:CP_Radial_D8.0mm_P3.50mm": ("Capacitor_THT", "CP_Radial_D8.0mm_P3.50mm"),
    "Diode_SMD:D_SOD-123": ("Diode_SMD", "D_SOD-123"),
    "Diode_SMD:D_SOD-323": ("Diode_SMD", "D_SOD-323"),
    "Package_TO_SOT_SMD:SOT-23-5": ("Package_TO_SOT_SMD", "SOT-23-5"),
    "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm": ("Package_SO", "SOIC-8_3.9x4.9mm_P1.27mm"),
    "Package_DFN_QFN:QFN-48-1EP_7x7mm_P0.5mm_EP5.6x5.6mm": ("Package_DFN_QFN", "QFN-48-1EP_7x7mm_P0.5mm_EP5.6x5.6mm"),
    "Package_QFP:LQFP-48_7x7mm_P0.5mm": ("Package_QFP", "LQFP-48_7x7mm_P0.5mm"),
    "Package_DIP:DIP-6_W7.62mm": ("Package_DIP", "DIP-6_W7.62mm"),
    "Crystal:Crystal_SMD_HC49-SD": ("Crystal", "Crystal_SMD_HC49-SD"),
    "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical": ("Connector_PinHeader_2.54mm", "PinHeader_1x02_P2.54mm_Vertical"),
    "Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical": ("Connector_PinHeader_2.54mm", "PinHeader_1x04_P2.54mm_Vertical"),
    "Connector_Coaxial:BNC_Amphenol_031-5539_Vertical": ("Connector_Coaxial", "BNC_Amphenol_031-5539_Vertical"),
    "Connector_Coaxial:SMA_Amphenol_132134_Vertical": ("Connector_Coaxial", "SMA_Amphenol_132134_Vertical"),
    "Connector_RJ:RJ45_Hanrun_HR911105A_Horizontal": ("Connector_RJ", "RJ45_Hanrun_HR911105A_Horizontal"),
    "Button_Switch_SMD:SW_SPST_EVQP2_ShortPushTravel_H2.1mm": ("Button_Switch_SMD", "SW_SPST_EVQP2_ShortPushTravel_H2.1mm"),
    "Fuse:Fuse_1206_3216Metric": ("Fuse", "Fuse_1206_3216Metric"),
    "Converter_ACDC:Converter_ACDC_Hi-Link_HLK-PMxx": ("Converter_ACDC", "Converter_ACDC_Hi-Link_HLK-PMxx"),
    "RF_Antenna:NiceRF_SW868-TH13_868Mhz": ("RF_Antenna", "NiceRF_SW868-TH13_868Mhz"),
    "MountingHole:MountingHole_3.2mm_M3": ("MountingHole", "MountingHole_3.2mm_M3"),
}

# Custom (non-real) footprints for the two lumped schematic blocks and the
# wire-leaded primary cell -- documented simplifications, mirrors
# gen_schematics.py's Generic:CT_Interface / Generic:RF_Frontend policy.
_CUSTOM = {}


def _custom_2pad(name, descr, pitch=5.0):
    return f'''(footprint "{name}"
\t(layer "F.Cu")
\t(descr "{descr}")
\t(property "Reference" "REF**" (at 0 -3 0) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))
\t(property "Value" "{name}" (at 0 3 0) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))
\t(attr through_hole)
\t(fp_line (start {-pitch/2-1.5} -2) (end {pitch/2+1.5} -2) (stroke (width 0.12) (type solid)) (layer "F.SilkS"))
\t(fp_line (start {-pitch/2-1.5} 2) (end {pitch/2+1.5} 2) (stroke (width 0.12) (type solid)) (layer "F.SilkS"))
\t(pad "1" thru_hole circle (at {-pitch/2} 0) (size 1.7 1.7) (drill 1.0) (layers "*.Cu" "*.Mask"))
\t(pad "2" thru_hole circle (at {pitch/2} 0) (size 1.7 1.7) (drill 1.0) (layers "*.Cu" "*.Mask"))
)
'''


def _custom_box(name, descr, w, h, pad_positions):
    """pad_positions: list of (number, x, y) local pad centers -- NUMBERS
    must match the corresponding _CUSTOM_PINS table in gen_schematics.py so
    pinnum() resolves to the right physical pad."""
    hw, hh = w / 2, h / 2
    pads = "\n".join(
        f'\t(pad "{num}" smd rect (at {px} {py}) (size 1 1) (layers "F.Cu" "F.Mask" "F.Paste"))'
        for num, px, py in pad_positions)
    return f'''(footprint "{name}"
\t(layer "F.Cu")
\t(descr "{descr}")
\t(property "Reference" "REF**" (at 0 {-hh-2} 0) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))
\t(property "Value" "{name}" (at 0 {hh+2} 0) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))
\t(attr smd)
\t(fp_rect (start {-hw} {-hh}) (end {hw} {hh}) (stroke (width 0.12) (type solid)) (layer "F.SilkS") (fill none))
{pads}
)
'''


_CUSTOM["Generic:Battery_Wireleads"] = _custom_2pad(
    "Generic:Battery_Wireleads",
    "LiSOCl2 3.6V primary cell, wire-leaded (not board-mounted) -- 2 THT pads for the pigtail crimp/solder points, PANO GOZ K1.2 simplification, see docs/03.",
    pitch=7.62)
# Pad numbers below MUST match gen_schematics._CUSTOM_PINS for the same
# Generic: block (that dict is the single source of truth for which
# electrical pin is number "1".."5").
_CUSTOM["Generic:CT_Interface_PCB"] = _custom_box(
    "Generic:CT_Interface_PCB",
    "Lumped burden-R + bias-divider + AC-coupling block (1=CT+ 2=CT- 3=VCC 4=GND 5=AOUT), PANO GOZ K1.2 simplification, see docs/03.",
    9, 7,
    [("1", -3.5, -2.2), ("2", -3.5, 2.2), ("3", 0, -2.2), ("4", 0, 2.2), ("5", 3.5, 0)])
_CUSTOM["Generic:RF_Frontend_PCB"] = _custom_box(
    "Generic:RF_Frontend_PCB",
    "Lumped BPF+LNA+log-amp envelope detector block (1=RFIN 2=VCC 3=GND 4=ENVOUT), PANO GOZ K1.2 simplification, see docs/03.",
    11, 8,
    [("1", -4, 0), ("2", 0, -3), ("3", 0, 3), ("4", 4, 0)])

_PAD_HEAD_RE = re.compile(
    r'\(pad "([^"]*)"\s+(\w+)\s+(\w+)\s*\n?\s*\(at ([-\d.]+) ([-\d.]+)(?:\s+([-\d.]+))?\)')

_text_cache = {}


def _lib_text(fp_id):
    if fp_id not in _text_cache:
        if fp_id in _CUSTOM:
            _text_cache[fp_id] = _CUSTOM[fp_id]
        else:
            prettydir, bare = SOURCE[fp_id]
            path = os.path.join(FPROOT, f"{prettydir}.pretty", bare + ".kicad_mod")
            with open(path, encoding="utf-8") as f:
                _text_cache[fp_id] = f.read()
    return _text_cache[fp_id]


_resolved = {}


def _resolve(fp_id):
    if fp_id in _resolved:
        return _resolved[fp_id]
    text = _lib_text(fp_id)
    pads = {}
    for num, ptype, shape, x, y, rot in _PAD_HEAD_RE.findall(text):
        pads[num] = (float(x), float(y), float(rot) if rot else 0.0)
    _resolved[fp_id] = (text, pads)
    return _resolved[fp_id]


def _r(v):
    v = round(v, 4)
    return int(v) if v == int(v) else v


def _bare_name(fp_id):
    if fp_id in _CUSTOM:
        return fp_id  # custom blocks declare their own full "Generic:X" name internally
    return SOURCE[fp_id][1]


class Pad(tuple):
    """(x, y) global board position, plus the source pad number."""

    def __new__(cls, x, y, num):
        obj = tuple.__new__(cls, (x, y))
        return obj

    def __init__(self, x, y, num):
        self.num = num


class Board:
    LAYER_STACKUP_2L = True  # documented in docs/03: 2-layer board (F.Cu/B.Cu)

    def __init__(self, width, height, title):
        self.width = width
        self.height = height
        self.title = title
        self.footprints = {}   # ref -> [text_block] (single-element list, mutated in place)
        self.pads_global = {}  # ref -> {num: Pad}
        self.order = []        # placement order, for stable output
        self.graphics = []     # edge cuts, silkscreen, keepouts, mounting holes (raw text)
        self.segments = []     # raw (segment ...) text
        self.zones = []        # raw (zone ...) text
        self.nets = {"": 0}
        self.next_net = 1
        self.refc = {}
        self.origin = (10.0, 10.0)  # board-space offset so all coords are positive

    # -- net bookkeeping ----------------------------------------------------
    def net_id(self, name):
        if name not in self.nets:
            self.nets[name] = self.next_net
            self.next_net += 1
        return self.nets[name]

    def _ref(self, prefix):
        self.refc[prefix] = self.refc.get(prefix, 0) + 1
        return f"{prefix}{self.refc[prefix]}"

    # -- placement ------------------------------------------------------------
    def place(self, fp_id, x, y, rot, ref_prefix, value=None, ref_override=None):
        raw, pads = _resolve(fp_id)
        bare = _bare_name(fp_id)
        ref = ref_override or self._ref(ref_prefix)
        val = value if value is not None else fp_id.split(":")[1]
        ox, oy = self.origin
        bx, by = _r(x + ox), _r(y + oy)

        body = raw.replace(f'(footprint "{bare}"', f'(footprint "{fp_id}"', 1)
        at_clause = f'(at {bx} {by})' if not rot else f'(at {bx} {by} {_r(rot)})'
        body = re.sub(r'\(layer "F\.Cu"\)',
                       f'(layer "F.Cu")\n\t(uuid "{U()}")\n\t{at_clause}',
                       body, count=1)
        body = re.sub(r'\(property "Reference" "REF\*\*"',
                       f'(property "Reference" "{ref}"', body, count=1)
        body = re.sub(rf'\(property "Value" "{re.escape(bare)}"',
                       f'(property "Value" "{val}"', body, count=1)

        holder = [body]
        self.footprints[ref] = holder
        self.order.append(ref)

        rad = math.radians(rot)
        cos_r, sin_r = math.cos(rad), math.sin(rad)
        gp = {}
        for num, (px, py, prot) in pads.items():
            gx = x + px * cos_r - py * sin_r
            gy = y + px * sin_r + py * cos_r
            gp[num] = Pad(gx, gy, num)
        self.pads_global[ref] = gp
        return ref, gp

    # -- net / copper ---------------------------------------------------------
    def net(self, ref, padnum, net_name):
        """Tag pad `padnum` of footprint `ref` with `net_name` (injects a
        real (net N "name") clause into that pad's own S-expression block).
        Uses balanced-paren scanning (not a fixed-layout regex) so it works
        for both real multi-line library pads and the single-line custom
        pads emitted by _custom_2pad/_custom_box."""
        nid = self.net_id(net_name)
        holder = self.footprints[ref]
        text = holder[0]
        marker = f'(pad "{padnum}"'
        start = text.find(marker)
        if start == -1:
            raise KeyError(f"pad {padnum!r} not found on {ref}")
        depth = 0
        i = start
        while i < len(text):
            c = text[i]
            if c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        end = i  # index of the pad block's closing ')'
        insert = f' (net {nid} "{net_name}")'
        holder[0] = text[:end] + insert + text[end:]

    def track(self, net_name, x1, y1, x2, y2, layer="F.Cu", width=0.25):
        nid = self.net_id(net_name)
        ox, oy = self.origin
        self.segments.append(
            f'\t(segment (start {_r(x1+ox)} {_r(y1+oy)}) (end {_r(x2+ox)} {_r(y2+oy)}) '
            f'(width {width}) (layer "{layer}") (net {nid}) (uuid "{U()}"))\n')

    def route(self, net_name, p1, p2, layer="F.Cu", width=0.25, via_l_first=True):
        """Straight or single-bend (Manhattan) track between two Pads."""
        x1, y1 = p1
        x2, y2 = p2
        if abs(x1 - x2) < 1e-6 or abs(y1 - y2) < 1e-6:
            self.track(net_name, x1, y1, x2, y2, layer, width)
        elif via_l_first:
            self.track(net_name, x1, y1, x2, y1, layer, width)
            self.track(net_name, x2, y1, x2, y2, layer, width)
        else:
            self.track(net_name, x1, y1, x1, y2, layer, width)
            self.track(net_name, x1, y2, x2, y2, layer, width)

    # -- board graphics ---------------------------------------------------------
    def edge_rect(self):
        ox, oy = self.origin
        x0, y0 = ox, oy
        x1, y1 = ox + self.width, oy + self.height
        for (sx, sy, ex, ey) in [(x0, y0, x1, y0), (x1, y0, x1, y1),
                                  (x1, y1, x0, y1), (x0, y1, x0, y0)]:
            self.graphics.append(
                f'\t(gr_line (start {_r(sx)} {_r(sy)}) (end {_r(ex)} {_r(ey)}) '
                f'(stroke (width 0.15) (type default)) (layer "Edge.Cuts") (uuid "{U()}"))\n')

    def mounting_hole(self, x, y):
        """Real MountingHole_3.2mm_M3 footprint (NPTH, no net) -- enclosure /
        magnetic-base carrier standoff screw, not a direct magnet-to-PCB fixing."""
        return self.place("MountingHole:MountingHole_3.2mm_M3", x, y, 0, "H")

    def keepout_circle(self, cx, cy, r, layers=("F.Cu", "B.Cu"), label="RF keepout"):
        ox, oy = self.origin
        bx, by = cx + ox, cy + oy
        pts = []
        import math as _m
        for i in range(24):
            a = 2 * _m.pi * i / 24
            pts.append(f'(xy {_r(bx + r*_m.cos(a))} {_r(by + r*_m.sin(a))})')
        layer_str = " ".join(f'"{l}"' for l in layers)
        # Only the GND-pour fill is excluded here (real RF guideline: no
        # ground plane crowding the antenna near-field) -- tracks/vias/pads
        # stay allowed so the antenna's own feed trace can still reach it.
        self.graphics.append(
            f'\t(zone (net 0) (net_name "") (layers {layer_str}) (uuid "{U()}")\n'
            f'\t\t(name "{label}")\n'
            f'\t\t(hatch edge 0.5)\n'
            f'\t\t(keepout (tracks allowed) (vias allowed) (pads allowed) '
            f'(copperpour not_allowed) (footprints allowed))\n'
            f'\t\t(polygon (pts {" ".join(pts)}))\n'
            f'\t)\n')

    def gnd_pour(self, net_name="GND", layer="F.Cu"):
        # F.Cu (not B.Cu): every part in this design pass is placed on the
        # top side (SMD + THT-vertical), so a same-layer pour connects to
        # GND pads directly with no via-stitching needed -- see docs/03.
        ox, oy = self.origin
        m = 1.0
        x0, y0 = ox + m, oy + m
        x1, y1 = ox + self.width - m, oy + self.height - m
        nid = self.net_id(net_name)
        self.zones.append(
            f'\t(zone (net {nid}) (net_name "{net_name}") (layers "{layer}") (uuid "{U()}")\n'
            f'\t\t(hatch edge 0.5)\n'
            f'\t\t(connect_pads (clearance 0.2))\n'
            f'\t\t(min_thickness 0.2)\n'
            f'\t\t(fill yes (thermal_gap 0.5) (thermal_bridge_width 0.5))\n'
            f'\t\t(polygon (pts (xy {_r(x0)} {_r(y0)}) (xy {_r(x1)} {_r(y0)}) '
            f'(xy {_r(x1)} {_r(y1)}) (xy {_r(x0)} {_r(y1)})))\n'
            f'\t)\n')

    def silk_text(self, s, x, y, layer="F.SilkS", size=1.0):
        ox, oy = self.origin
        s = s.replace('"', "'")
        self.graphics.append(
            f'\t(gr_text "{s}" (at {_r(x+ox)} {_r(y+oy)} 0) (layer "{layer}") (uuid "{U()}") '
            f'(effects (font (size {size} {size}) (thickness 0.15))))\n')

    # -- render -----------------------------------------------------------------
    def render(self):
        net_decls = "\n".join(f'\t(net {nid} "{name}")' for name, nid in
                               sorted(self.nets.items(), key=lambda kv: kv[1]))
        fp_text = "".join(self.footprints[ref][0] for ref in self.order)
        gfx_text = "".join(self.graphics)
        seg_text = "".join(self.segments)
        zone_text = "".join(self.zones)
        return f'''(kicad_pcb
\t(version 20240108)
\t(generator "panogoz-gen-pcb")
\t(generator_version "10.0")
\t(general
\t\t(thickness 1.6)
\t\t(legacy_teardrops no)
\t)
\t(paper "A4")
\t(title_block
\t\t(title "{self.title}")
\t\t(date "2026-09-16")
\t\t(rev "A")
\t\t(company "PANO GOZ - K1")
\t)
\t(layers
\t\t(0 "F.Cu" signal)
\t\t(31 "B.Cu" signal)
\t\t(32 "B.Adhes" user "B.Adhesive")
\t\t(33 "F.Adhes" user "F.Adhesive")
\t\t(34 "B.Paste" user)
\t\t(35 "F.Paste" user)
\t\t(36 "B.SilkS" user "B.Silkscreen")
\t\t(37 "F.SilkS" user "F.Silkscreen")
\t\t(38 "B.Mask" user)
\t\t(39 "F.Mask" user)
\t\t(44 "Edge.Cuts" user)
\t\t(46 "B.CrtYd" user "B.Courtyard")
\t\t(47 "F.CrtYd" user "F.Courtyard")
\t\t(48 "B.Fab" user)
\t\t(49 "F.Fab" user)
\t)
\t(setup
\t\t(pad_to_mask_clearance 0.05)
\t\t(allow_soldermask_bridges_in_footprints no)
\t\t(pcbplotparams
\t\t\t(layerselection 0x00010fc_ffffffff)
\t\t\t(plot_on_all_layers_selection 0x0000000_00000000)
\t\t\t(disableapertmacros no)
\t\t\t(usegerberextensions no)
\t\t\t(usegerberattributes yes)
\t\t\t(usegerberadvancedattributes yes)
\t\t\t(creategerberjobfile yes)
\t\t\t(dashed_line_dash_ratio 12.000000)
\t\t\t(dashed_line_gap_ratio 3.000000)
\t\t\t(svgprecision 4)
\t\t\t(plotframeref no)
\t\t\t(viasonmask no)
\t\t\t(mode 1)
\t\t\t(useauxorigin no)
\t\t\t(hpglpennumber 1)
\t\t\t(hpglpenspeed 20)
\t\t\t(hpglpendiameter 15.000000)
\t\t\t(pdf_front_fp_property_popups yes)
\t\t\t(pdf_back_fp_property_popups yes)
\t\t\t(dxfpolygonmode yes)
\t\t\t(dxfimperialunits yes)
\t\t\t(dxfusepcbnewfont yes)
\t\t\t(psnegative no)
\t\t\t(psa4output no)
\t\t\t(plot_black_and_white yes)
\t\t\t(plotinvisibletext no)
\t\t\t(sketchpadsonfab no)
\t\t\t(plotpadnumbers no)
\t\t\t(hidednponfab no)
\t\t\t(sketchdnponfab yes)
\t\t\t(crossoutdnponfab yes)
\t\t\t(subtractmaskfromsilk no)
\t\t\t(outputformat 1)
\t\t\t(mirror no)
\t\t\t(drillshape 0)
\t\t\t(scaleselection 1)
\t\t\t(outputdirectory "export/")
\t\t)
\t)
{net_decls}
{fp_text}{gfx_text}{seg_text}{zone_text})
'''
