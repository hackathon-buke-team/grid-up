"""PANO GOZ K1.1 -- generates the 3 KiCad schematics (tc-node, ir-pd-node, gateway).

Every symbol embedded here is extracted VERBATIM (byte-for-byte S-expression
block, including all properties/metadata) from the real KiCad 10.0.6 stock
libraries under C:/Users/mert/AppData/Local/Programs/KiCad/10.0/share/kicad/symbols
-- nothing is hand-retyped. Only the outer "(symbol "<name>"" identifier is
rewritten to the full "Library:Name" lib_id form used elsewhere in this file
(matching how KiCad itself names embedded lib_symbols cache entries).

Three parts (AP2112K-3.3, RJ45, PTVS5V0Z1USK) are defined in the real library
via "(extends "<base>")" (a value/voltage variant of a shared base part).
Embedding an "extends" relationship inside a schematic's own cache is
unreliable, so for these three we instead embed the BASE part's full body
verbatim (byte-for-byte) and only relabel the outer symbol name + the visible
Value/Reference text to the target part number -- electrically and
graphically identical to the base, same footprint family. This is the one
documented simplification left in the design; see docs/03.

Pin coordinates and electrical types are parsed out of that same verbatim
text (never hand-copied), so there is a single source of truth and no risk
of a transcription error between the schematic graphics and the connectivity
model.
"""
import os
import re
import uuid as _uuid

SYMDIR = "C:/Users/mert/AppData/Local/Programs/KiCad/10.0/share/kicad/symbols"


def U():
    return str(_uuid.uuid4())


# ---------------------------------------------------------------------------
# Verbatim symbol extraction from the real installed KiCad libraries
# ---------------------------------------------------------------------------
_PIN_RE = re.compile(
    r'\(pin\s+(\S+)\s+line\s*\(at\s+([-\d.]+)\s+([-\d.]+)\s+(\d+)\)\s*\(length\s+([-\d.]+)\)'
    r'(\s+hide)?.*?\(name\s+"([^"]*)".*?\(number\s+"([^"]*)"',
    re.DOTALL)
_EXTENDS_RE = re.compile(r'\(extends\s+"([^"]+)"\)')
_MARKUP_RE = re.compile(r'[~_]\{([^}]*)\}')  # KiCad overbar ~{X} / subscript _{X} display markup

# lib_id -> (library file (no ext), bare symbol name as it appears in that file)
SOURCE = {
    "Device:R": ("Device", "R"),
    "Device:C": ("Device", "C"),
    "Device:C_Polarized": ("Device", "C_Polarized"),
    "Device:D": ("Device", "D"),
    "Device:LED": ("Device", "LED"),
    "Device:Fuse": ("Device", "Fuse"),
    "Device:Crystal": ("Device", "Crystal"),
    "Device:Battery_Cell": ("Device", "Battery_Cell"),
    "Device:Antenna": ("Device", "Antenna"),
    "Regulator_Linear:AP2112K-3.3": ("Regulator_Linear", "AP2112K-3.3"),
    "Sensor_Temperature:MAX31855KASA": ("Sensor_Temperature", "MAX31855KASA"),
    "Converter_ACDC:HLK-PM01": ("Converter_ACDC", "HLK-PM01"),
    "Connector:RJ45": ("Connector", "RJ45"),
    "Connector:Conn_Coaxial_Small": ("Connector", "Conn_Coaxial_Small"),
    "Isolator:4N25": ("Isolator", "4N25"),
    "Diode:PTVS5V0Z1USK": ("Diode", "PTVS5V0Z1USK"),
    "Switch:SW_Push": ("Switch", "SW_Push"),
    "Connector_Generic:Conn_01x02": ("Connector_Generic", "Conn_01x02"),
    "Connector_Generic:Conn_01x04": ("Connector_Generic", "Conn_01x04"),
    "power:GND": ("power", "GND"),
    "power:+3V3": ("power", "+3V3"),
    "power:+5V": ("power", "+5V"),
    "power:VBUS": ("power", "VBUS"),
    "power:PWR_FLAG": ("power", "PWR_FLAG"),
    "MCU_ST_STM32WL:STM32WLE5CCUx": ("MCU_ST_STM32WL", "STM32WLE5CCUx"),
    "Interface_Ethernet:W5500": ("Interface_Ethernet", "W5500"),
}

_text_cache = {}


def _lib_text(fname):
    if fname not in _text_cache:
        with open(os.path.join(SYMDIR, fname + ".kicad_sym"), encoding="utf-8") as f:
            _text_cache[fname] = f.read()
    return _text_cache[fname]


def _find_block(text, name):
    marker = f'(symbol "{name}"'
    idx = text.find(marker)
    if idx == -1:
        raise KeyError(f"symbol {name!r} not found")
    depth = 0
    i = idx
    n = len(text)
    while i < n:
        c = text[i]
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return text[idx:i + 1]
        i += 1
    raise ValueError("unbalanced parens for " + name)


def _clean(name):
    """Strip KiCad's ~{X} (overbar) / _{X} (subscript) display markup."""
    return _MARKUP_RE.sub(r"\1", name)


_resolved = {}


def _resolve(lib_id):
    """Returns (embed_text, pins) where pins maps every alias (number, real
    name, cleaned name, '/'-as-'_' alias) -> (number, x, y, rot)."""
    if lib_id in _resolved:
        return _resolved[lib_id]
    fname, bare = SOURCE[lib_id]
    text = _lib_text(fname)
    block = _find_block(text, bare)
    m = _EXTENDS_RE.search(block)
    if m:
        base_name = m.group(1)
        base_block = _find_block(text, base_name)
        pin_source = base_block
        target_bare = lib_id.split(":", 1)[1]
        # The BASE block is what actually carries the full graphics/pins
        # (the extends-child block itself has none). Its inner "_0_1"/"_1_1"
        # sub-unit names share the base's bare name as their prefix, so
        # renaming only the outer wrapper (leaving the base's bare name on
        # the sub-units) produces a name mismatch KiCad can't parse -- rename
        # every occurrence of the base's bare name to the target's bare name
        # first, then prefix only the outer with the library name, exactly
        # matching how KiCad itself names non-extends embedded symbols
        # (e.g. outer "Device:R", bare "R_0_1"/"R_1_1" sub-units).
        renamed = base_block.replace(base_name, target_bare)
        embed_src = renamed.replace(f'(symbol "{target_bare}"', f'(symbol "{lib_id}"', 1)
        embed_text = re.sub(r'\(property "Value" "[^"]*"', f'(property "Value" "{target_bare}"', embed_src, count=1)
    else:
        pin_source = block
        embed_text = block.replace(f'(symbol "{bare}"', f'(symbol "{lib_id}"', 1)

    pins = {}
    for etype, x, y, rot, length, hide, name, number in _PIN_RE.findall(pin_source):
        entry = (number, float(x), float(y), int(rot))
        pins[number] = entry
        if name and name != "~":
            cleaned = _clean(name)
            pins.setdefault(cleaned, entry)
            if "/" in cleaned:
                pins.setdefault(cleaned.replace("/", "_"), entry)
    _resolved[lib_id] = (embed_text, pins)
    return _resolved[lib_id]


# ---------------------------------------------------------------------------
# Custom (non-library) lumped blocks -- documented simplifications, not real
# parts, so there is no real library to extract them from.
# ---------------------------------------------------------------------------
_CUSTOM_RAW = {}
_CUSTOM_PINS = {}

_CUSTOM_RAW["Generic:CT_Interface"] = '''
\t(symbol "Generic:CT_Interface"
\t\t(exclude_from_sim no) (in_bom yes) (on_board yes) (in_pos_files yes) (duplicate_pin_numbers_are_jumpers no)
\t\t(property "Reference" "A" (at -12.7 10.16 0) (effects (font (size 1.27 1.27)) (justify left)))
\t\t(property "Value" "CT_Interface" (at -12.7 -10.16 0) (effects (font (size 1.27 1.27)) (justify left)))
\t\t(property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
\t\t(symbol "CT_Interface_0_1"
\t\t\t(rectangle (start -10 7.62) (end 10 -7.62) (stroke (width 0.254) (type default)) (fill (type background))))
\t\t(symbol "CT_Interface_1_1"
\t\t\t(pin passive line (at -12.7 2.54 0) (length 2.7) (name "CT+" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27)))))
\t\t\t(pin passive line (at -12.7 -2.54 0) (length 2.7) (name "CT-" (effects (font (size 1.27 1.27)))) (number "2" (effects (font (size 1.27 1.27)))))
\t\t\t(pin power_in line (at 0 10.16 270) (length 2.54) (name "VCC" (effects (font (size 1.27 1.27)))) (number "3" (effects (font (size 1.27 1.27)))))
\t\t\t(pin power_in line (at 0 -10.16 90) (length 2.54) (name "GND" (effects (font (size 1.27 1.27)))) (number "4" (effects (font (size 1.27 1.27)))))
\t\t\t(pin output line (at 12.7 0 180) (length 2.7) (name "AOUT" (effects (font (size 1.27 1.27)))) (number "5" (effects (font (size 1.27 1.27))))))
\t)
'''
_CUSTOM_PINS["Generic:CT_Interface"] = {
    "1": ("1", -12.7, 2.54, 0), "CT+": ("1", -12.7, 2.54, 0),
    "2": ("2", -12.7, -2.54, 0), "CT-": ("2", -12.7, -2.54, 0),
    "3": ("3", 0, 10.16, 270), "VCC": ("3", 0, 10.16, 270),
    "4": ("4", 0, -10.16, 90), "GND": ("4", 0, -10.16, 90),
    "5": ("5", 12.7, 0, 180), "AOUT": ("5", 12.7, 0, 180),
}

_CUSTOM_RAW["Generic:RF_Frontend"] = '''
\t(symbol "Generic:RF_Frontend"
\t\t(exclude_from_sim no) (in_bom yes) (on_board yes) (in_pos_files yes) (duplicate_pin_numbers_are_jumpers no)
\t\t(property "Reference" "A" (at -10 10.16 0) (effects (font (size 1.27 1.27)) (justify left)))
\t\t(property "Value" "RF_Frontend (BPF+LNA+LogDet)" (at -10 -10.16 0) (effects (font (size 1.27 1.27)) (justify left)))
\t\t(property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
\t\t(symbol "RF_Frontend_0_1"
\t\t\t(rectangle (start -10 7.62) (end 10 -7.62) (stroke (width 0.254) (type default)) (fill (type background))))
\t\t(symbol "RF_Frontend_1_1"
\t\t\t(pin input line (at -12.7 0 0) (length 2.7) (name "RFIN" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27)))))
\t\t\t(pin power_in line (at 0 10.16 270) (length 2.54) (name "VCC" (effects (font (size 1.27 1.27)))) (number "2" (effects (font (size 1.27 1.27)))))
\t\t\t(pin power_in line (at 0 -10.16 90) (length 2.54) (name "GND" (effects (font (size 1.27 1.27)))) (number "3" (effects (font (size 1.27 1.27)))))
\t\t\t(pin output line (at 12.7 0 180) (length 2.7) (name "ENVOUT" (effects (font (size 1.27 1.27)))) (number "4" (effects (font (size 1.27 1.27))))))
\t)
'''
_CUSTOM_PINS["Generic:RF_Frontend"] = {
    "1": ("1", -12.7, 0, 0), "RFIN": ("1", -12.7, 0, 0),
    "2": ("2", 0, 10.16, 270), "VCC": ("2", 0, 10.16, 270),
    "3": ("3", 0, -10.16, 90), "GND": ("3", 0, -10.16, 90),
    "4": ("4", 12.7, 0, 180), "ENVOUT": ("4", 12.7, 0, 180),
}


def _get(lib_id):
    if lib_id in _CUSTOM_RAW:
        return _CUSTOM_RAW[lib_id], _CUSTOM_PINS[lib_id]
    return _resolve(lib_id)


# ---------------------------------------------------------------------------
# Outward-facing direction per pin rotation, in SHEET space.
#
# A pin "(at X Y ROT) (length L)" in LIBRARY space (+Y up) has its
# electrical connection point at (X,Y) and its body-ward end at
# (X + L*cos(ROT), Y + L*sin(ROT)) -- verified against Device:R pin 1
# ((at 0 3.81 270), body edge at y=2.54: 3.81 + 1.27*sin(270) = 2.54).
# The outward direction (continuing a wire AWAY from the body) is therefore
# (-cos(ROT), -sin(ROT)) in library space. place() maps library (px,py) to
# sheet (x+px, y-py) -- a Y-sign flip -- so the same flip applies to this
# direction vector's Y component to keep it visually "outward" on the page.
# ---------------------------------------------------------------------------
_OUTWARD = {0: (-1, 0), 90: (0, 1), 180: (1, 0), 270: (0, -1)}

STUB = 2.54  # wire stub length (2 grid units), mm


def _r(v):
    """Round away binary-float noise (e.g. -198.12 + 254.0 == 55.879999999999995)
    so every coordinate that is intended to land on the 1.27mm grid actually
    does, textually, in the emitted S-expression."""
    v = round(v, 6)
    return int(v) if v == int(v) else v


def _snap(v):
    """Snap a layout coordinate to the nearest 1.27mm (KiCad's symbol pin
    grid). build_boards.py's placement coordinates (x0, y0 passed to
    place()) are chosen for readable layout spacing, not grid alignment --
    only the pin offsets baked into each real library symbol are guaranteed
    multiples of 1.27. Snapping the component origin here, once, keeps every
    pin's absolute position (origin + pin offset, both then multiples of
    1.27) genuinely on-grid instead of merely close to it."""
    return _r(round(v / 1.27) * 1.27)


class Pin(tuple):
    """A 2-tuple (x, y) in sheet space that also carries the source pin's
    rotation, so callers that only need `x, y = pins[key]` keep working."""

    def __new__(cls, x, y, rot):
        obj = tuple.__new__(cls, (x, y))
        return obj

    def __init__(self, x, y, rot):
        self.rot = rot


class Sheet:
    # KiCad's sheet origin is the page's top-left corner; this generator's
    # layout math uses (0,0) as its own logical center, so every written
    # coordinate is shifted by (OX, OY) to land on an A2 page. OX/OY must be
    # an exact multiple of 1.27mm (KiCad's symbol/connection grid) or every
    # single placed pin -- even though each one is individually grid-aligned
    # in library space -- lands off-grid on the sheet.
    OX = 254.0   # = 200 * 1.27
    OY = 254.0

    def __init__(self):
        self.used = set()
        self.body = []
        self.refc = {}

    def _ref(self, prefix):
        self.refc[prefix] = self.refc.get(prefix, 0) + 1
        return f"{prefix}{self.refc[prefix]}"

    def place(self, lib_id, x0, y0, ref_prefix, value=None, footprint=None):
        embed_text, pin_table = _get(lib_id)
        x0, y0 = _snap(x0), _snap(y0)
        x, y = _r(x0 + self.OX), _r(y0 + self.OY)
        self.used.add(lib_id)
        ref = self._ref(ref_prefix)
        val = value if value is not None else lib_id.split(":")[1]
        su = U()
        props = f'\t\t(property "Reference" "{ref}" (at {x} {_r(y + 6)} 0) (effects (font (size 1.27 1.27))))\n'
        props += f'\t\t(property "Value" "{val}" (at {x} {_r(y - 6)} 0) (effects (font (size 1.27 1.27))))\n'
        props += f'\t\t(property "Footprint" "{footprint or ""}" (at {x} {y} 0) (effects (font (size 1.27 1.27)) hide))\n'
        pin_uuids = "".join(
            f'\t\t(pin "{num}" (uuid "{U()}"))\n'
            for key, (num, px, py, prot) in pin_table.items() if key == num
        )
        block = (f'\t(symbol (lib_id "{lib_id}") (at {x} {y} 0) (unit 1)\n'
                 f'\t\t(exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no) (uuid "{su}")\n'
                 f'{props}{pin_uuids}\t)\n')
        self.body.append(block)
        pins_abs = {}
        for key, (num, px, py, prot) in pin_table.items():
            pins_abs[key] = Pin(_r(x0 + px), _r(y0 - py), prot)
        return ref, pins_abs

    def _stub(self, x0, y0, rot):
        """Draw a short outward wire stub from (x0,y0); return its far end."""
        dx, dy = _OUTWARD.get(rot, (0, -1))
        ex, ey = _r(x0 + dx * STUB), _r(y0 + dy * STUB)
        x, y = _r(x0 + self.OX), _r(y0 + self.OY)
        ex_s, ey_s = _r(ex + self.OX), _r(ey + self.OY)
        self.body.append(
            f'\t(wire (pts (xy {x} {y}) (xy {ex_s} {ey_s})) (stroke (width 0) (type default)) (uuid "{U()}"))\n')
        return ex, ey, dx, dy

    def label(self, net, x0, y0, rot=0):
        x, y = _r(x0 + self.OX), _r(y0 + self.OY)
        self.body.append(
            f'\t(label "{net}" (at {x} {y} {rot}) (effects (font (size 1.27 1.27)) (justify left bottom)) (uuid "{U()}"))\n')

    def wire_label(self, net, x0, y0, rot):
        ex, ey, dx, dy = self._stub(x0, y0, rot)
        label_rot = 0 if dx != 0 else 90
        self.label(net, ex, ey, label_rot)

    def pwr_flag(self, x0, y0):
        x, y = _r(x0 + self.OX), _r(y0 + self.OY)
        self.used.add("power:PWR_FLAG")
        ref = self._ref("#FLG")
        su = U()
        block = (f'\t(symbol (lib_id "power:PWR_FLAG") (at {x} {y} 0) (unit 1)\n'
                 f'\t\t(exclude_from_sim no) (in_bom no) (on_board yes) (dnp no) (uuid "{su}")\n'
                 f'\t\t(property "Reference" "{ref}" (at {x} {y - 2.54} 0) (effects (font (size 1.27 1.27)) hide))\n'
                 f'\t\t(property "Value" "PWR_FLAG" (at {x} {y + 2.5} 0) (effects (font (size 1.27 1.27))))\n'
                 f'\t\t(property "Footprint" "" (at {x} {y} 0) (effects (font (size 1.27 1.27)) hide))\n'
                 f'\t\t(pin "1" (uuid "{U()}"))\n'
                 f'\t)\n')
        self.body.append(block)

    def power(self, net, x0, y0):
        x, y = _r(x0 + self.OX), _r(y0 + self.OY)
        lib_id = f"power:{net}"
        self.used.add(lib_id)
        ref = self._ref("#PWR")
        su = U()
        block = (f'\t(symbol (lib_id "{lib_id}") (at {x} {y} 0) (unit 1)\n'
                 f'\t\t(exclude_from_sim no) (in_bom no) (on_board yes) (dnp no) (uuid "{su}")\n'
                 f'\t\t(property "Reference" "{ref}" (at {x} {y - 2.54} 0) (effects (font (size 1.27 1.27)) hide))\n'
                 f'\t\t(property "Value" "{net}" (at {x} {y + 2.5} 0) (effects (font (size 1.27 1.27))))\n'
                 f'\t\t(property "Footprint" "" (at {x} {y} 0) (effects (font (size 1.27 1.27)) hide))\n'
                 f'\t\t(pin "1" (uuid "{U()}"))\n'
                 f'\t)\n')
        self.body.append(block)

    def wire_power(self, net, x0, y0, rot):
        ex, ey, dx, dy = self._stub(x0, y0, rot)
        self.power(net, ex, ey)

    def no_connect(self, x0, y0):
        x, y = _r(x0 + self.OX), _r(y0 + self.OY)
        self.body.append(f'\t(no_connect (at {x} {y}) (uuid "{U()}"))\n')

    def text(self, s, x0, y0, size=1.27):
        x, y = _r(x0 + self.OX), _r(y0 + self.OY)
        s = s.replace('"', "'")
        self.body.append(
            f'\t(text "{s}" (at {x} {y} 0) (effects (font (size {size} {size}))) (uuid "{U()}"))\n')

    def render(self, title):
        libsyms = "\n".join(_get(k)[0] for k in sorted(self.used))
        return f'''(kicad_sch
\t(version 20231120)
\t(generator "panogoz-gen")
\t(generator_version "10.0")
\t(uuid "{U()}")
\t(paper "A2")
\t(title_block
\t\t(title "{title}")
\t\t(date "2026-09-13")
\t\t(rev "A")
\t\t(company "PANO GOZ - K1")
\t)
\t(lib_symbols
{libsyms}
\t)
{''.join(self.body)}\t(sheet_instances
\t\t(path "/" (page "1"))
\t)
)
'''
