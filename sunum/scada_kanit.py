"""Sunumdaki SCADA beat'i için Modbus kanıtı: bir pano bloğunu okur, sonra yazmayı dener.

    python sunum/scada_kanit.py                  # SOKE-14 (pano 14), 127.0.0.1:5020
    python sunum/scada_kanit.py --panel 3 --port 5028

modpoll jüri makinesinde kurulu olmayabilir; bu betik yalnız depoda zaten olan pymodbus'u
kullanır. Adresler ve ölçekler panogoz/contracts/icd.py'den gelir, burada sayı tanımlanmaz.
"""
from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from pymodbus.client import ModbusTcpClient  # noqa: E402

from panogoz.contracts import assets, icd  # noqa: E402

SEVERITY = ["BILGI", "IZLE", "UYARI", "KRITIK", "ACIL"]
SHOW = ["PANEL_ID", "HEALTH_INDEX", "SEVERITY", "STATUS_WORD", "ACTIVE_ALARMS",
        "THETA_MAX", "THETA_MAX_JOINT", "THETA_SLOPE", "SENSITIVITY_PCT", "DATA_AGE_S"]


def main() -> None:
    # Ayrı bir PowerShell penceresinde PYTHONIOENCODING ayarlı olmayabilir; "→", "−" yazılabilsin.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=5020)
    ap.add_argument("--panel", type=int, default=14, help="pano indeksi (SOKE-14 = 14)")
    args = ap.parse_args()

    base = icd.panel_base(args.panel)
    monitored = [j.key for j in assets.JOINTS if j.zone in assets.MONITORED_ZONES]
    print(f"Pano {args.panel} bloğu: {icd.PANEL_BASE} + {icd.REGS_PER_PANEL} × ({args.panel} − 1) = {base}")

    c = ModbusTcpClient(args.host, port=args.port)
    if not c.connect():
        sys.exit(f"{args.host}:{args.port} açılamadı; demo çalışıyor mu (.\\baslat.ps1)?")
    try:
        words = c.read_holding_registers(base, count=icd.REGS_PER_PANEL).registers
        print(f"\nFC 03 · {base}..{base + icd.REGS_PER_PANEL - 1} okundu ({len(words)} register)\n")
        for name in SHOW:
            r = icd.PANEL_BY_NAME[name]
            raw = words[r.offset:r.offset + r.words]
            eng = icd.decode(r, raw)
            if name == "SEVERITY":
                text = SEVERITY[int(eng)] if 0 <= int(eng) < len(SEVERITY) else str(eng)
            elif name == "STATUS_WORD":
                text = ", ".join(icd.unpack_bits(icd.STATUS_BITS, raw[0])) or "-"
            elif name == "THETA_MAX_JOINT":
                text = monitored[int(eng)] if 0 <= int(eng) < len(monitored) else str(eng)
            else:
                text = f"{eng:g} {r.unit if r.unit != '-' else ''}".strip()
            print(f"  +{r.offset:<3} {name:<16} ham {raw[0] if r.words == 1 else raw}  →  {text}")

        print(f"\nFC 06 · {base} adresine yazma deneniyor…")
        w = c.write_register(base, 1)
        if w.isError():
            print(f"  REDDEDİLDİ: exception 0x{w.exception_code:02X} (ILLEGAL FUNCTION). Harita salt okunur.")
        else:
            print("  BEKLENMEDİK: yazma kabul edildi.")
    finally:
        c.close()


if __name__ == "__main__":
    main()
