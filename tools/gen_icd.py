"""ICD v2.0 dokümanını ve CSV nokta listesini panogoz/scada/icd.py'den ÜRETİR.

    python -m tools.gen_icd            # docs/PANOGOZ-ICD-v2.0.md + docs/data/panogoz-icd-v2.0-points.csv yazar
    python -m tools.gen_icd --check    # diskteki dosyalar koddan üretilenle aynı mı? (CI/test)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from panogoz.scada import icd

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "PANOGOZ-ICD-v2.0.md"
CSV = ROOT / "docs" / "data" / "panogoz-icd-v2.0-points.csv"


def _norm(text: str) -> str:
    return text.replace("\r\n", "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    outputs = {DOC: icd.markdown_doc(), CSV: icd.csv_point_list()}
    if args.check:
        stale = [str(p) for p, text in outputs.items() if not p.exists() or _norm(p.read_text(encoding="utf-8")) != _norm(text)]
        if stale:
            print("ESKİ (koddan farklı): " + ", ".join(stale), file=sys.stderr)
            return 1
        print("ICD dokümanı ve CSV koddan üretilenle aynı.")
        return 0
    CSV.parent.mkdir(parents=True, exist_ok=True)
    for path, text in outputs.items():
        path.write_text(text, encoding="utf-8", newline="\n")
        print(f"yazıldı: {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
