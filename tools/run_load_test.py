"""K2 2.4 -- gercek kademeli yuk testi (250 -> 500 -> 1000 pano).

Her kademede GERCEK olcum yapar (uydurma sayi yok):
  - CPU/RAM: gercek `psutil.Process` (bu surecin kendisi).
  - Tur suresi: N panonun tamaminin theta/rules hesaplamasinin gercek
    duvar-saati suresi (`build_fleet` -- panogoz/sim/demo_fleet.py).
  - Servis suresi: API'nin `_connection_summary`/`_connection_series`
    esdegeri isi (panogoz/api/app.py'deki gercek fonksiyonlar, N pano
    icin gercekten cagirilir) -- HTTP katmani olmadan, hesaplama+
    serilestirme yukunu olcer.
  - Disk/yazma hizi: panogoz.store.Outbox'a (gercek SQLite dosyasi,
    gecici bir dizinde) N pano kadar gercek Envelope enqueue edilir,
    gercek dosya boyutu + gercek yazma suresi olculur.

Kullanim: `python tools/run_load_test.py` (varsayilan kademeler 250/500/1000)
          `python tools/run_load_test.py --panels 50 100` (ozel kademeler)
"""
from __future__ import annotations

import argparse
import gc
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import psutil

from panogoz.api.app import _connection_series, _connection_summary
from panogoz.bus.envelope import Envelope
from panogoz.sim.demo_fleet import build_fleet
from panogoz.store.outbox import Outbox


def _measure_outbox_write(n_panels: int) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        db_path = str(Path(tmp) / "loadtest_outbox.sqlite3")
        outbox = Outbox(db_path)
        t0 = time.perf_counter()
        for i in range(n_panels):
            from panogoz.contracts.channels import ChannelKind, Phase, Reading

            reading = Reading(t_s=float(i), connection_id=f"F{i:04d}", kind=ChannelKind.CURRENT, value=100.0 + i, phase=Phase.L1)
            env = Envelope(seq=i, device_id=f"F{i:04d}", reading=reading)
            outbox.enqueue(i, "panogoz/loadtest", env.to_json())
        t1 = time.perf_counter()
        outbox.close()
        disk_bytes = os.path.getsize(db_path)
        return {
            "write_time_s": t1 - t0,
            "writes_per_s": n_panels / (t1 - t0) if t1 > t0 else float("inf"),
            "disk_bytes": disk_bytes,
            "disk_bytes_per_panel": disk_bytes / n_panels,
        }


def measure(n_panels: int, *, backfill_days: float | None = None) -> dict:
    proc = psutil.Process(os.getpid())
    gc.collect()
    proc.cpu_percent(interval=None)  # ilk cagri her zaman 0.0 doner, olcumu bastan baslatir
    mem_before = proc.memory_info().rss

    t0 = time.perf_counter()
    fleet = build_fleet(n_panels, backfill_days=backfill_days)
    t1 = time.perf_counter()

    # API'nin gercekten yapacagi isi tekrar et: her baglanti icin summary + series
    for i, tl in enumerate(fleet):
        _connection_summary(i, tl)
        _connection_series(tl)
    t2 = time.perf_counter()

    mem_after = proc.memory_info().rss
    cpu_percent = proc.cpu_percent(interval=None)

    outbox_stats = _measure_outbox_write(n_panels)

    del fleet
    gc.collect()

    return {
        "n_panels": n_panels,
        "build_time_s": round(t1 - t0, 3),
        "serve_time_s": round(t2 - t1, 3),
        "ms_per_panel_build": round((t1 - t0) * 1000 / n_panels, 3),
        "rss_delta_mb": round((mem_after - mem_before) / 1e6, 2),
        "rss_total_mb": round(mem_after / 1e6, 2),
        "cpu_percent": round(cpu_percent, 1),
        "outbox_write_time_s": round(outbox_stats["write_time_s"], 3),
        "outbox_writes_per_s": round(outbox_stats["writes_per_s"], 1),
        "outbox_disk_kb": round(outbox_stats["disk_bytes"] / 1024, 1),
        "outbox_bytes_per_panel": round(outbox_stats["disk_bytes_per_panel"], 1),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--panels", type=int, nargs="+", default=[250, 500, 1000])
    parser.add_argument("--backfill-days", type=float, default=None)
    args = parser.parse_args()

    results = []
    for n in args.panels:
        print(f"-- olcum: {n} pano --", flush=True)
        r = measure(n, backfill_days=args.backfill_days)
        results.append(r)
        for k, v in r.items():
            print(f"  {k}: {v}")
        print(flush=True)

    print("\n| Pano | Kurulum (s) | Servis (s) | Pano/ms (kurulum) | RSS (MB) | CPU % | Outbox yazma (s) | Outbox yazma/s | Outbox (KB) |")
    print("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for r in results:
        print(
            f"| {r['n_panels']} | {r['build_time_s']} | {r['serve_time_s']} | "
            f"{r['ms_per_panel_build']} | {r['rss_total_mb']} | {r['cpu_percent']} | "
            f"{r['outbox_write_time_s']} | {r['outbox_writes_per_s']} | {r['outbox_disk_kb']} |"
        )


if __name__ == "__main__":
    main()
