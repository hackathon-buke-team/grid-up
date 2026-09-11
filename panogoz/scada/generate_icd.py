"""Generate the SCADA ICD document and point list from ``contracts.icd``.

The PDF a utility's integration engineer reads and the registers their RTU
actually polls are produced from the same tables, in the same run.  There is no
hand-maintained copy of the map anywhere, so the document cannot drift from the
server - the usual way an ICD becomes a lie.

Outputs
-------
``docs/PANOGOZ-ICD-v<major>.<minor>.md``
    ``icd.to_markdown()`` verbatim.
``docs/panogoz_points.csv``
    ``icd.to_csv()`` verbatim - importable as a SCADA point list.

Before writing either file this module runs the checks in :func:`check_map`.
They are cheap enough to run in CI on every commit, and they are the checks
that catch the two mistakes that actually happen to register maps: a new point
quietly landing on top of an old one, and a scale factor that cannot represent
the range the document promises.

Usage::

    python -m panogoz.scada.generate_icd            # check, then write
    python -m panogoz.scada.generate_icd --check    # check only, write nothing
"""

from __future__ import annotations

import argparse
import csv
import io
from pathlib import Path
from typing import Sequence

from panogoz.contracts import icd

__all__ = ["check_map", "generate", "CheckFailure", "doc_paths"]

#: ``panogoz/scada/generate_icd.py`` -> project root
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = PROJECT_ROOT / "docs"

#: The four named bitfield tables in the ICD, by the name their ``note`` uses.
BIT_TABLES = {
    "STATUS_BITS": icd.STATUS_BITS,
    "ARC_BITS": icd.ARC_BITS,
    "DEVICE_FAULT_BITS": icd.DEVICE_FAULT_BITS,
    "ENGINE_BITS": icd.ENGINE_BITS,
}


class CheckFailure(Exception):
    """Raised when the register map fails a CI assertion."""


def doc_paths(docs_dir: Path | str = DOCS_DIR) -> tuple[Path, Path]:
    """The two files this generator owns, named from ``ICD_VERSION`` itself."""
    docs = Path(docs_dir)
    major, minor = icd.ICD_VERSION.split(".")[:2]
    return docs / f"PANOGOZ-ICD-v{major}.{minor}.md", docs / "panogoz_points.csv"


# --------------------------------------------------------------------------
# CI assertions
# --------------------------------------------------------------------------

def _overlap_checks(problems: list[str]) -> list[str]:
    """No two registers may claim the same word, in any block, ever."""
    notes: list[str] = []

    for what, regs, base, size in (
        ("global", icd.GLOBAL_REGS, icd.GLOBAL_BASE, icd.GLOBAL_SIZE),
        ("panel", icd.PANEL_REGS, icd.PANEL_BASE, icd.REGS_PER_PANEL),
    ):
        owner: dict[int, str] = {}
        for r in regs:
            if r.words != (2 if r.rtype == "u32" else 1):
                problems.append(f"{what}: {r.name} word count {r.words} disagrees with type {r.rtype}")
            for w in range(r.words):
                off = r.offset + w
                if off in owner:
                    problems.append(
                        f"{what}: word +{off} claimed by both {owner[off]} and {r.name}"
                    )
                if not 0 <= off < size:
                    problems.append(
                        f"{what}: {r.name} word +{off} falls outside the {size}-word block"
                    )
                owner[off] = r.name
        notes.append(
            f"{what} block: {len(regs)} points, {len(owner)}/{size} words used, "
            f"{size - len(owner)} reserved, 0 collisions"
        )

    # Blocks must not collide with each other.
    if icd.GLOBAL_BASE + icd.GLOBAL_SIZE > icd.PANEL_BASE:
        problems.append(
            f"global block ends at {icd.GLOBAL_BASE + icd.GLOBAL_SIZE - 1} "
            f"but panel blocks start at {icd.PANEL_BASE}"
        )
    # Fixed stride: consecutive panels must be exactly REGS_PER_PANEL apart, and
    # the panel block must fit in that stride.  If either failed, panel n would
    # overwrite panel n+1 - the single most damaging bug a register map can have.
    strides = {
        icd.panel_base(n + 1) - icd.panel_base(n) for n in range(1, icd.MAX_PANELS)
    }
    if strides != {icd.REGS_PER_PANEL}:
        problems.append(f"panel stride is not constant: {sorted(strides)}")
    used = max(r.offset + r.words for r in icd.PANEL_REGS)
    if used > icd.REGS_PER_PANEL:
        problems.append(f"panel block uses {used} words but stride is {icd.REGS_PER_PANEL}")
    if icd.TOP_ADDRESS > 0xFFFF:
        problems.append(f"top address {icd.TOP_ADDRESS} does not fit a 16-bit PDU address")
    notes.append(
        f"address plan: global {icd.GLOBAL_BASE}..{icd.GLOBAL_BASE + icd.GLOBAL_SIZE - 1}, "
        f"panels {icd.PANEL_BASE}..{icd.TOP_ADDRESS} at a constant stride of "
        f"{icd.REGS_PER_PANEL}, {icd.MAX_PANELS} panels, no holes"
    )

    names = [r.name for r in icd.GLOBAL_REGS] + [r.name for r in icd.PANEL_REGS]
    dupes = sorted({n for n in names if names.count(n) > 1})
    if dupes:
        problems.append(f"duplicate register names across blocks: {dupes}")
    return notes


def _range_checks(problems: list[str]) -> list[str]:
    """Extreme raw values must land inside the documented engineering range.

    Three separate things are checked, because they fail for different reasons:

    * the documented range is exactly what the raw extremes decode to (the
      document promises what the wire can carry);
    * encode/decode round-trips at both extremes and at zero (no off-by-one at
      the sign boundary, no lost high word on a u32);
    * values beyond the range **saturate rather than wrap**.  A wrapped register
      looks like a plausible small number and silently misleads SCADA; a
      saturated one pins at full scale and is obviously out of range.
    """
    notes: list[str] = []
    tested = 0
    for what, regs in (("global", icd.GLOBAL_REGS), ("panel", icd.PANEL_REGS)):
        for r in regs:
            raw_lo, raw_hi = r.raw_range
            eng_lo, eng_hi = r.eng_range

            if abs(eng_lo - raw_lo * r.scale) > 1e-9 or abs(eng_hi - raw_hi * r.scale) > 1e-9:
                problems.append(f"{what}.{r.name}: documented range disagrees with raw*scale")

            for eng in (eng_lo, 0.0 if eng_lo <= 0.0 <= eng_hi else eng_lo, eng_hi):
                words = icd.encode(r, eng)
                if len(words) != r.words:
                    problems.append(f"{what}.{r.name}: encode produced {len(words)} words")
                    continue
                if any(not 0 <= w <= 0xFFFF for w in words):
                    problems.append(f"{what}.{r.name}: encode produced a non-16-bit word {words}")
                back = icd.decode(r, words)
                if abs(back - eng) > max(1e-6, abs(r.scale) / 2):
                    problems.append(
                        f"{what}.{r.name}: round trip {eng} -> {words} -> {back}"
                    )
                if not eng_lo - 1e-9 <= back <= eng_hi + 1e-9:
                    problems.append(
                        f"{what}.{r.name}: {back} outside documented {eng_lo}..{eng_hi}"
                    )
                tested += 1

            # Saturation, not wrap-around.
            over = icd.decode(r, icd.encode(r, eng_hi * 4 + 1000))
            under = icd.decode(r, icd.encode(r, eng_lo * 4 - 1000))
            if abs(over - eng_hi) > max(1e-6, abs(r.scale) / 2):
                problems.append(f"{what}.{r.name}: over-range wrapped to {over}, expected {eng_hi}")
            if abs(under - eng_lo) > max(1e-6, abs(r.scale) / 2):
                problems.append(f"{what}.{r.name}: under-range wrapped to {under}, expected {eng_lo}")

            # None must read as zero, never as a plausible measurement.
            if any(w != 0 for w in icd.encode(r, None)):
                problems.append(f"{what}.{r.name}: None does not encode as zero")

    notes.append(
        f"engineering range: {tested} extreme raw values decoded inside their documented "
        f"range across {len(icd.GLOBAL_REGS) + len(icd.PANEL_REGS)} points, "
        f"over/under-range saturates on all of them"
    )
    return notes


def _bit_checks(problems: list[str]) -> list[str]:
    notes: list[str] = []
    for name, bits in BIT_TABLES.items():
        seen: dict[int, str] = {}
        for b in bits:
            if not 0 <= b.bit <= 15:
                problems.append(f"{name}: {b.name} at bit {b.bit} is outside a 16-bit word")
            if b.bit in seen:
                problems.append(f"{name}: bit {b.bit} used by both {seen[b.bit]} and {b.name}")
            seen[b.bit] = b.name
        word = icd.pack_bits(bits, {b.name for b in bits})
        if sorted(icd.unpack_bits(bits, word)) != sorted(b.name for b in bits):
            problems.append(f"{name}: pack/unpack does not round trip")
        notes.append(f"{name}: {len(bits)} bits, unique, all inside a 16-bit word, "
                     f"all-set word 0x{word:04X} round trips")

    # DEVICE_FAULT_BITS must match the frozen 9-device kit.
    from panogoz.contracts import assets

    if len(icd.DEVICE_FAULT_BITS) != assets.DEVICES_PER_PANEL:
        problems.append(
            f"DEVICE_FAULT_BITS has {len(icd.DEVICE_FAULT_BITS)} bits but the kit is "
            f"frozen at {assets.DEVICES_PER_PANEL} devices"
        )
    else:
        notes.append(
            f"DEVICE_FAULT_BITS: {assets.DEVICES_PER_PANEL} bits, one per device in the frozen kit"
        )

    bits_regs = [r for r in icd.GLOBAL_REGS + icd.PANEL_REGS if r.rtype == "bits"]
    named = [r for r in bits_regs if r.note in BIT_TABLES]
    for r in named:
        if not BIT_TABLES[r.note]:
            problems.append(f"{r.name} names an empty bit table {r.note}")
    notes.append(
        f"bitfields: {len(bits_regs)} 'bits' registers, {len(named)} of them name one of the "
        f"{len(BIT_TABLES)} published bit tables"
    )
    return notes


def _document_checks(problems: list[str]) -> list[str]:
    """The generated artefacts must agree with the tables they came from."""
    notes: list[str] = []
    rows = list(csv.DictReader(io.StringIO(icd.to_csv())))
    by_key = {(r["block"], r["name"]): r for r in rows}
    expected = len(icd.GLOBAL_REGS) + len(icd.PANEL_REGS)
    if len(rows) != expected:
        problems.append(f"CSV has {len(rows)} rows, expected {expected}")

    for block, regs, base in (
        ("GLOBAL", icd.GLOBAL_REGS, icd.GLOBAL_BASE),
        ("PANEL[n]", icd.PANEL_REGS, icd.PANEL_BASE),
    ):
        for r in regs:
            row = by_key.get((block, r.name))
            if row is None:
                problems.append(f"CSV is missing {block}.{r.name}")
                continue
            if int(row["pdu_dec"]) != base + r.offset:
                problems.append(f"CSV {r.name}: pdu {row['pdu_dec']} != {base + r.offset}")
            if int(row["modicon_4x"]) != 40001 + base + r.offset:
                problems.append(f"CSV {r.name}: 4x address wrong")
            elo, ehi = r.eng_range
            if abs(float(row["eng_min"]) - round(elo, 4)) > 1e-6:
                problems.append(f"CSV {r.name}: eng_min {row['eng_min']} != {elo}")
            if abs(float(row["eng_max"]) - round(ehi, 4)) > 1e-6:
                problems.append(f"CSV {r.name}: eng_max {row['eng_max']} != {ehi}")

    md = icd.to_markdown()
    for token in (
        icd.ICD_VERSION,
        str(icd.panel_base(14)),  # the panel-14 worked example and modpoll line
        "ILLEGAL_FUNCTION",
    ):
        if token not in md:
            problems.append(f"markdown is missing {token!r}")
    for r in icd.PANEL_REGS:
        if f"`{r.name}`" not in md:
            problems.append(f"markdown is missing point {r.name}")
    notes.append(
        f"documents: {len(rows)} CSV rows and {len(md.splitlines())} markdown lines, "
        f"every point present, PDU and 4x addresses agree with the tables"
    )
    return notes


def check_map() -> list[str]:
    """Run every CI assertion.  Returns evidence lines, raises on failure."""
    problems: list[str] = []
    notes: list[str] = []
    notes += _overlap_checks(problems)
    notes += _range_checks(problems)
    notes += _bit_checks(problems)
    notes += _document_checks(problems)
    if problems:
        raise CheckFailure(
            f"{len(problems)} problem(s) in the register map:\n  - "
            + "\n  - ".join(problems)
        )
    return notes


# --------------------------------------------------------------------------
# Generation
# --------------------------------------------------------------------------

def generate(docs_dir: Path | str = DOCS_DIR, *, check: bool = True) -> tuple[Path, Path]:
    """Write both artefacts.  Returns the two paths written."""
    if check:
        check_map()
    md_path, csv_path = doc_paths(docs_dir)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(icd.to_markdown(), encoding="utf-8", newline="\n")
    csv_path.write_text(icd.to_csv(), encoding="utf-8", newline="\n")
    return md_path, csv_path


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Generate the PANO GÖZ SCADA ICD and point list from contracts.icd"
    )
    ap.add_argument("--out-dir", default=str(DOCS_DIR), help="output directory (default: docs/)")
    ap.add_argument("--check", action="store_true", help="run the CI assertions only, write nothing")
    args = ap.parse_args(argv)

    print(f"PANO GÖZ ICD v{icd.ICD_VERSION} (encoded {icd.ICD_VERSION_ENCODED})")
    try:
        notes = check_map()
    except CheckFailure as exc:
        print(f"\nFAIL: {exc}")
        return 1
    for n in notes:
        print(f"  ok  {n}")

    if args.check:
        print("\n--check: no files written.")
        return 0

    md_path, csv_path = generate(args.out_dir, check=False)
    for p in (md_path, csv_path):
        print(f"  wrote {p}  ({p.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
