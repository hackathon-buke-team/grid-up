"""K4 4.4 doğruluk matrisi: senaryo x tohum koşuları, duyarlılık taramaları, yanlış alarm bütçesi.

Kullanım:
    python -m tools.run_accuracy_matrix --seeds 10 --workers 4
    python -m tools.run_accuracy_matrix --seeds 3 --no-sweeps        # hızlı deneme

Markdown tablolarını stdout'a, ham sonuçları JSON dosyasına yazar
(docs/data/dogruluk-matrisi.json). docs/09-VERI-ANALIZI.md bu çıktıdaki gerçek
sayılarla yazılır.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import os
import time
from pathlib import Path

from panogoz.eval.matrix import (
    false_alarm_budget,
    run_matrix,
    summarize,
    sweep_fault_magnitude,
    sweep_ramp_duration,
    sweep_sensor_noise,
    sweep_thermal_tau,
)
from panogoz.sim.scenarios import SCENARIOS

OUT_DEFAULT = Path(__file__).resolve().parents[1] / "docs" / "data" / "dogruluk-matrisi.json"


def _f(value: float | None, digits: int = 1) -> str:
    return "—" if value is None else f"{value:.{digits}f}"


def _pct(value: float | None) -> str:
    return "—" if value is None else f"{100 * value:.0f}%"


def _print_matrix(summaries) -> None:
    print("\n### Senaryo × tespit matrisi\n")
    print("| Senaryo | Beklenen | Tespit (95% GA) | ALARM gecikmesi med/p90 (gün) | UYARI gecikmesi med (gün) | Tehlikeye kalan (ALARM) med/min (gün) | ALARM tehlikeden önce | Yanlış alarm (koşu) | Ek uyarı (koşu) |")
    print("|---|---|---|---|---|---|---|---|---|")
    for s in summaries:
        sc = SCENARIOS[s.key]
        if s.expect == "quiet":
            ci = "—"
            expected = "sessiz"
        elif s.expect == "advisory":
            ci = f"sevk edildi {int(round((s.detect_rate or 0) * s.runs))}/{s.runs}"
            expected = "yalnız uyarı"
        else:
            lo, hi = s.detect_ci
            ci = f"{_pct(s.detect_rate)} ({_pct(lo)}–{_pct(hi)})"
            expected = sc.expected_kind or ""
        print(
            f"| {sc.title} | {expected} | {ci} | "
            f"{_f(s.latency_days_median, 2)} / {_f(s.latency_days_p90, 2)} | {_f(s.warning_latency_days_median, 2)} | "
            f"{_f(s.lead_days_median, 2)} / {_f(s.lead_days_min, 2)} | {_pct(s.alarmed_before_danger)} | "
            f"{s.false_alarm_runs}/{s.runs} | {s.warning_runs}/{s.runs} |"
        )

    print("\n### Sabit eşik kıyası (yalnız eklem sıcaklığına bakan kurallar)\n")
    print("| Senaryo | Bu sistem: tespit / ALARM gecikmesi (gün) | Sabit 75 °C: tespit / yanlış alarm / gecikme (gün) | Sabit +45 K: tespit / yanlış alarm / gecikme (gün) |")
    print("|---|---|---|---|")
    for s in summaries:
        fa, fr = s.fixed_abs, s.fixed_rise
        interesting = s.key.startswith("loose_bolt") or s.key == "overload_sustained" or any(
            (fa.detected, fa.false_alarms, fr.detected, fr.false_alarms)
        )
        if not interesting:
            continue
        sc = SCENARIOS[s.key]
        if s.expect == "detect":
            ours = f"{round(s.detect_rate * s.runs)}/{s.runs} / {_f(s.latency_days_median, 2)}"
        else:
            ours = f"— / {s.false_alarm_runs}/{s.runs} yanlış"
        print(
            f"| {sc.title} | {ours} | {fa.detected}/{s.runs} / {fa.false_alarms}/{s.runs} / {_f(fa.latency_days_median, 2)} | "
            f"{fr.detected}/{s.runs} / {fr.false_alarms}/{s.runs} / {_f(fr.latency_days_median, 2)} |"
        )


def _print_sweep(title: str, header: str, points) -> None:
    print(f"\n### {title}\n")
    print(f"| {header} | Koşu | UYARI oranı | ALARM oranı | ALARM gecikmesi med (gün) | Tehlikeye kalan (ALARM) med (gün) | Tehlikeye kalan (UYARI) med (gün) | Yanlış alarm koşusu | Ek uyarı koşusu |")
    print("|---|---|---|---|---|---|---|---|---|")
    for p in points:
        print(
            f"| {p.label:g} | {p.runs} | {_pct(p.warning_rate)} | {_pct(p.alarm_rate)} | {_f(p.latency_days_median, 2)} | "
            f"{_f(p.lead_days_median, 2)} | {_f(p.warning_lead_days_median, 2)} | {p.false_alarm_runs} | {p.extra_warning_runs} |"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=10)
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) // 2))
    parser.add_argument("--no-sweeps", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT_DEFAULT)
    args = parser.parse_args()

    seeds = list(range(1, args.seeds + 1))
    t0 = time.time()
    results = run_matrix(seeds, workers=args.workers)
    summaries = summarize(results)
    budget = false_alarm_budget(results)
    print(f"# Doğruluk matrisi — {len(SCENARIOS)} senaryo x {len(seeds)} tohum = {len(results)} koşu ({time.time() - t0:.0f} sn)")
    _print_matrix(summaries)

    detect = [s for s in summaries if s.expect == "detect"]
    total_det = sum(round(s.detect_rate * s.runs) for s in detect)
    total_runs = sum(s.runs for s in detect)
    print(f"\n**Genel duyarlılık (DETECT senaryoları):** {total_det}/{total_runs} = {100 * total_det / total_runs:.1f}%")
    print(
        f"\n**Yanlış alarm bütçesi (QUIET+ADVISORY):** {budget.panel_days:.0f} pano-günü ({budget.panel_days / 365:.1f} pano-yılı), "
        f"{budget.false_alarm_episodes} ALARM-üstü yanlış alarm -> {budget.per_panel_year:.2f}/pano-yılı "
        f"(%95 üst sınır {budget.upper95_per_panel_year:.2f}/pano-yılı)"
    )

    payload: dict = {
        "seeds": seeds,
        "summaries": [dataclasses.asdict(s) for s in summaries],
        "false_alarm_budget": dataclasses.asdict(budget),
    }
    if not args.no_sweeps:
        mag = sweep_fault_magnitude(seeds)
        _print_sweep("Duyarlılık: gevşek cıvata direnç çarpanı (L2, ani)", "k çarpanı", mag)
        noise_detect, noise_healthy = sweep_sensor_noise(seeds)
        _print_sweep("Gürültü dayanıklılığı: arıza (k×3) tespiti", "gürültü çarpanı", noise_detect)
        _print_sweep("Gürültü dayanıklılığı: sağlıklı pano yanlış alarm", "gürültü çarpanı", noise_healthy)
        ramp = sweep_ramp_duration(seeds)
        _print_sweep("Haber verme süresi: kademeli gevşeme hızı (k 1→4)", "rampa (gün)", ramp)
        tau = sweep_thermal_tau(seeds)
        _print_sweep("Model uyumsuzluğu: gerçek ısıl tau değişir, dedektör tau'yu taban çizgisinden tahmin eder — sağlıklı", "gerçek tau (sn)", tau["healthy"])
        _print_sweep("Model uyumsuzluğu: gerçek ısıl tau — faz dengesizliği (en hassas negatif kontrol)", "gerçek tau (sn)", tau["imbalance"])
        _print_sweep("Model uyumsuzluğu: gerçek ısıl tau — gevşek cıvata (k×2,2) tespiti", "gerçek tau (sn)", tau["fault"])
        payload["sweeps"] = {
            "thermal_tau": {k: [dataclasses.asdict(p) for p in v] for k, v in tau.items()},
            "fault_magnitude": [dataclasses.asdict(p) for p in mag],
            "noise_detect": [dataclasses.asdict(p) for p in noise_detect],
            "noise_healthy": [dataclasses.asdict(p) for p in noise_healthy],
            "ramp_duration": [dataclasses.asdict(p) for p in ramp],
        }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(f"\nHam sonuçlar: {args.out}")


if __name__ == "__main__":
    main()
