"""Kural motoru: bastırma -> füzyon -> alarm, sabit sırayla (K4 sahipliği)."""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field

from panogoz.detector.engine import CusumDetector, absolute_severity
from panogoz.rules.fusion import max_severity
from panogoz.rules.suppression import DebounceTracker, current_family_corroborates
from panogoz.sim.scenarios import DailyRecord

THETA_PEAK_THRESHOLD = 0.02
CUSUM_K = 0.0015
CUSUM_H = 0.015
OVERLOAD_RATIO = 1.10
NEUTRAL_CURRENT_RATIO_THRESHOLD = 0.15
CONDENSATION_MARGIN_THRESHOLD = 0.0
PD_SCORE_THRESHOLD = 0.5
NEUTRAL_BASELINE_DAYS = 5


@dataclass
class PipelineResult:
    alarm_ever_opened: bool = False
    first_alarm_day: int | None = None
    max_severity_reached: str = "NORMAL"
    families_triggered: set = field(default_factory=set)
    suppression_log: list = field(default_factory=list)
    all_flags: set = field(default_factory=set)
    daily_severity: list = field(default_factory=list)


def evaluate_connection(records: list[DailyRecord], *, theta_peak_threshold: float = THETA_PEAK_THRESHOLD) -> PipelineResult:
    result = PipelineResult()
    thermal_debounce = DebounceTracker()
    overload_debounce = DebounceTracker()
    neutral_debounce = DebounceTracker()
    condensation_debounce = DebounceTracker()
    pd_debounce = DebounceTracker()
    cusum = CusumDetector(k=CUSUM_K, h=CUSUM_H)
    neutral_baseline_vals: list[float] = []
    neutral_baseline: float | None = None

    for rec in records:
        result.all_flags |= rec.flags
        day_families: set[str] = set()
        day_severity = "NORMAL"
        corroborated = current_family_corroborates(rec.current_ratio_avg, rec.flags)

        abs_sev = absolute_severity(rec.temp_peak_c)
        if abs_sev:
            day_severity = max_severity(day_severity, abs_sev)
            day_families.add("thermal_absolute")

        theta_exceeds = rec.theta_peak > theta_peak_threshold
        debounced = thermal_debounce.push(theta_exceeds)
        cusum_triggered = cusum.update_daily(rec.theta_median)
        if (debounced or cusum_triggered) and corroborated:
            day_severity = max_severity(day_severity, "ALARM")
            day_families.add("thermal")
        elif theta_exceeds:
            result.suppression_log.append(
                f"gün {rec.day_idx}: theta {rec.theta_peak:.4f} eşiği aştı ama debounce/korelasyon "
                "şartı henüz sağlanmadı, alarm açılmadı"
            )

        if overload_debounce.push(rec.current_ratio_peak > OVERLOAD_RATIO) and "DE_ENERGISED" not in rec.flags:
            day_severity = max_severity(day_severity, "ALARM")
            day_families.add("overload")

        if len(neutral_baseline_vals) < NEUTRAL_BASELINE_DAYS:
            neutral_baseline_vals.append(rec.i_neutral_ratio_avg)
            if len(neutral_baseline_vals) == NEUTRAL_BASELINE_DAYS:
                neutral_baseline = statistics.mean(neutral_baseline_vals)
        neutral_exceeds = rec.i_neutral_ratio_avg > NEUTRAL_CURRENT_RATIO_THRESHOLD
        if neutral_debounce.push(neutral_exceeds):
            day_severity = max_severity(day_severity, "ALARM")
            day_families.add("neutral_harmonic")

        if condensation_debounce.push(rec.condensation_margin_min < CONDENSATION_MARGIN_THRESHOLD):
            day_severity = max_severity(day_severity, "ALARM")
            day_families.add("condensation")

        if pd_debounce.push(rec.pd_score_peak > PD_SCORE_THRESHOLD) and corroborated:
            day_severity = max_severity(day_severity, "ALARM")
            day_families.add("insulation_pd")

        if not rec.arc_health_ok:
            day_severity = max_severity(day_severity, "ALARM")
            day_families.add("arc_integrity")
        if rec.arc_trip_delta > 0:
            day_severity = max_severity(day_severity, "EMERGENCY")
            day_families.add("arc_trip")

        result.daily_severity.append(day_severity)
        if day_severity in ("ALARM", "CRITICAL", "EMERGENCY"):
            if not result.alarm_ever_opened:
                result.alarm_ever_opened = True
                result.first_alarm_day = rec.day_idx
            result.families_triggered |= day_families
            result.max_severity_reached = max_severity(result.max_severity_reached, day_severity)

    _ = neutral_baseline  # gelecekte K_N tabanlı gevşek-nötr ayrımı için ayrılmış (bkz. docs/04)
    return result
