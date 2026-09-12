"""17 senaryo x tespit matrisi, haber verme süresi, yanlış alarm bütçesi, duyarlılık eğrisi (K4 §4.4).

Kullanım: python -m tools.run_accuracy_report
Çıktı: reports/dogruluk-matrisi.csv, reports/dogruluk-raporu.md, reports/duyarlilik-egrisi.png
"""
from __future__ import annotations

import csv
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from panogoz.rules.engine import THETA_PEAK_THRESHOLD, evaluate_connection
from panogoz.sim.scenarios import SCENARIOS

REPORTS_DIR = os.path.join(os.path.dirname(__file__), "..", "reports")
THETA_SENSITIVE_ALARM_IDS = {"A1", "A2", "A10"}
THETA_SENSITIVE_NEGATIVE_IDS = {"N1", "N2", "N5", "N6"}
SWEEP_THRESHOLDS = [0.0003, 0.0006, 0.001, 0.0015, 0.002, 0.005, 0.01, 0.02, 0.03, 0.05, 0.08, 0.12, 0.20]


def build_detection_matrix() -> list[dict]:
    rows = []
    for sc in SCENARIOS:
        records = sc.run()
        result = evaluate_connection(records)
        detect_day = (
            result.first_alarm_day - sc.fault_start_day
            if (result.first_alarm_day is not None and sc.fault is not None)
            else None
        )
        rows.append(
            {
                "id": sc.scenario_id,
                "title": sc.title,
                "expected_alarm": sc.expected_alarm,
                "detected": result.alarm_ever_opened,
                "match": result.alarm_ever_opened == sc.expected_alarm,
                "severity": result.max_severity_reached,
                "families": ",".join(sorted(result.families_triggered)) or "-",
                "days_to_detect": detect_day,
            }
        )
    return rows


def false_alarm_budget(rows: list[dict]) -> tuple[int, int]:
    negatives = [r for r in rows if not r["expected_alarm"]]
    false_alarms = [r for r in negatives if r["detected"]]
    return len(false_alarms), len(negatives)


def _naive_detected(records, threshold: float) -> bool:
    """Bastırmasız tek-örnek karar: herhangi bir gün theta tepe değeri eşiği aşarsa alarm.

    Üretim hattındaki debounce+CUSUM+korelasyon katmanlarının neden var olduğunu
    göstermek için kasıtlı olarak naif bırakıldı (sabit eşik yaklaşımının kendisi).
    """
    return any(r.theta_peak > threshold for r in records)


def sensitivity_sweep() -> list[dict]:
    alarm_scn = [s for s in SCENARIOS if s.scenario_id in THETA_SENSITIVE_ALARM_IDS]
    neg_scn = [s for s in SCENARIOS if s.scenario_id in THETA_SENSITIVE_NEGATIVE_IDS]
    cached_alarm = [(s, s.run()) for s in alarm_scn]
    cached_neg = [(s, s.run()) for s in neg_scn]

    sweep = []
    for threshold in SWEEP_THRESHOLDS:
        detected = sum(
            1 for _, recs in cached_alarm if evaluate_connection(recs, theta_peak_threshold=threshold).alarm_ever_opened
        )
        false_pos = sum(
            1 for _, recs in cached_neg if evaluate_connection(recs, theta_peak_threshold=threshold).alarm_ever_opened
        )
        naive_detected = sum(1 for _, recs in cached_alarm if _naive_detected(recs, threshold))
        naive_false_pos = sum(1 for _, recs in cached_neg if _naive_detected(recs, threshold))
        sweep.append(
            {
                "threshold": threshold,
                "detection_rate": detected / len(cached_alarm),
                "false_alarm_rate": false_pos / len(cached_neg),
                "naive_detection_rate": naive_detected / len(cached_alarm),
                "naive_false_alarm_rate": naive_false_pos / len(cached_neg),
            }
        )
    return sweep


def write_csv(rows: list[dict], path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_markdown_report(rows: list[dict], sweep: list[dict], false_count: int, neg_count: int, path: str) -> None:
    positives = [r for r in rows if r["expected_alarm"]]
    detected_positive = sum(1 for r in positives if r["detected"])
    detect_days = [r["days_to_detect"] for r in positives if r["days_to_detect"] is not None]

    lines = []
    lines.append("# Doğruluk Raporu — PANO GÖZ (K4 §4.4)\n")
    lines.append(f"Varsayılan theta eşiği: {THETA_PEAK_THRESHOLD}\n")
    lines.append("## 17 Senaryo x Tespit Matrisi\n")
    lines.append("| ID | Senaryo | Beklenen | Tespit | Uyum | Şiddet | Kanal Ailesi | Haber Verme (gün) |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for r in rows:
        lines.append(
            f"| {r['id']} | {r['title']} | {'ALARM' if r['expected_alarm'] else '-'} | "
            f"{'ALARM' if r['detected'] else '-'} | {'OK' if r['match'] else 'FAIL'} | "
            f"{r['severity']} | {r['families']} | {r['days_to_detect'] if r['days_to_detect'] is not None else '-'} |"
        )
    lines.append("")
    lines.append("## Özet\n")
    lines.append(f"- Duyarlılık (10 alarm senaryosu): {detected_positive}/{len(positives)}")
    lines.append(f"- Yanlış alarm bütçesi (7 negatif kontrol): {false_count}/{neg_count}")
    if detect_days:
        lines.append(
            f"- Haber verme süresi dağılımı (gün): min={min(detect_days)}, "
            f"medyan={sorted(detect_days)[len(detect_days)//2]}, max={max(detect_days)}"
        )
    lines.append("")
    lines.append("## Duyarlılık Eğrisi (theta eşiği taraması)\n")
    lines.append(
        "Üretim hattı = debounce + CUSUM + akım korelasyonu. Ham eşik = bastırmasız, "
        "tek örnekte eşik aşımı (klasik sabit eşik yaklaşımının simülasyonu).\n"
    )
    lines.append("| Eşik | Üretim - Tespit | Üretim - Yanlış Alarm | Ham Eşik - Tespit | Ham Eşik - Yanlış Alarm |")
    lines.append("|---|---|---|---|---|")
    for s in sweep:
        lines.append(
            f"| {s['threshold']:.3f} | {s['detection_rate']:.2f} | {s['false_alarm_rate']:.2f} | "
            f"{s['naive_detection_rate']:.2f} | {s['naive_false_alarm_rate']:.2f} |"
        )
    lines.append("")
    lines.append("Grafik: duyarlilik-egrisi.png\n")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def write_sensitivity_plot(sweep: list[dict], path: str) -> None:
    thresholds = [s["threshold"] for s in sweep]

    fig, ax = plt.subplots(figsize=(7.5, 5))
    ax.plot(thresholds, [s["detection_rate"] for s in sweep], marker="o", color="tab:blue", label="Üretim hattı - tespit")
    ax.plot(
        thresholds,
        [s["false_alarm_rate"] for s in sweep],
        marker="o",
        color="tab:blue",
        linestyle="--",
        label="Üretim hattı - yanlış alarm",
    )
    ax.plot(thresholds, [s["naive_detection_rate"] for s in sweep], marker="s", color="tab:red", label="Ham eşik - tespit")
    ax.plot(
        thresholds,
        [s["naive_false_alarm_rate"] for s in sweep],
        marker="s",
        color="tab:red",
        linestyle="--",
        label="Ham eşik - yanlış alarm",
    )
    ax.axvline(THETA_PEAK_THRESHOLD, color="gray", linestyle=":", label="seçilen eşik")
    ax.set_xscale("log")
    ax.set_xlabel("theta tepe eşiği (°C/A, log ölçek)")
    ax.set_ylabel("oran")
    ax.set_title("PANO GÖZ - theta eşiği duyarlılık eğrisi: üretim hattı vs ham eşik")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=150)


def main() -> None:
    os.makedirs(REPORTS_DIR, exist_ok=True)
    rows = build_detection_matrix()
    false_count, neg_count = false_alarm_budget(rows)
    sweep = sensitivity_sweep()

    write_csv(rows, os.path.join(REPORTS_DIR, "dogruluk-matrisi.csv"))
    write_csv(sweep, os.path.join(REPORTS_DIR, "duyarlilik-egrisi.csv"))
    write_markdown_report(rows, sweep, false_count, neg_count, os.path.join(REPORTS_DIR, "dogruluk-raporu.md"))
    write_sensitivity_plot(sweep, os.path.join(REPORTS_DIR, "duyarlilik-egrisi.png"))

    all_match = all(r["match"] for r in rows)
    print(f"Senaryo uyumu: {'TÜMÜ OK' if all_match else 'BAZI SENARYOLAR FAIL'}")
    print(f"Yanlış alarm bütçesi: {false_count}/{neg_count}")
    print(f"Raporlar yazıldı: {REPORTS_DIR}")


if __name__ == "__main__":
    main()
