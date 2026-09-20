"""Çok kanallı filo servisinin (22 senaryo, 5 dedektör ailesi + bastırma/füzyon/alarm/eskalasyon) tek çekirdek
işlem hızı. docs/06 §5'teki sayıları üretir:  python -m tools.bench_fleet"""
from __future__ import annotations

import time

from panogoz.api.fleet_service import FleetService


def main() -> None:
    t0 = time.perf_counter()
    svc = FleetService()
    build_s = time.perf_counter() - t0
    n, samples = len(svc.panels), svc.n_samples
    t1 = time.perf_counter()
    svc.advance_to(svc.end_t_s)
    adv_s = time.perf_counter() - t1
    print(f"panolar={n} örnek/pano={samples} (gün={samples / 96:.1f})")
    print(f"kurulum (senaryo üretimi + tüm dedektör analizi): {build_s:.2f} s -> {build_s / n:.3f} s/pano, {n * samples / build_s:,.0f} pano-örneği/sn")
    print(f"filo ilerletme (alarm motoru + eskalasyon, {n * samples:,} pano-örneği): {adv_s:.2f} s -> {n * samples / adv_s:,.0f} pano-örneği/sn")


if __name__ == "__main__":
    main()
