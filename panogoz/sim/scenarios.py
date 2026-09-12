"""17 senaryo kütüphanesi: 10 alarm üreten + 7 negatif kontrol (K4 §4.4).

Her senaryo, gerçek L1 akım profiline (data/ct_l1_real.csv) dayalı bir yük
şekli üstüne fizik-temelli bir arıza enjekte eder ve günlük özet kayıt
(DailyRecord) üretir. rules/engine.py bu kayıtları tüketir.
"""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field

from panogoz.detector.engine import (
    ThermalRLS,
    compute_expect_flags,
    condensation_margin_c,
    neutral_k,
    theta_raw,
)
from panogoz.sim.ct_data import STEP_S, ambient_temp_c, real_profile_cycle

STEPS_PER_DAY = 96
TARGET_PHASE = "L2"


@dataclass
class DailyRecord:
    day_idx: int
    theta_peak: float
    theta_median: float
    temp_peak_c: float
    current_ratio_peak: float
    current_ratio_avg: float
    i_neutral_ratio_avg: float
    k_n: float
    condensation_margin_min: float
    pd_score_peak: float
    arc_health_ok: bool
    arc_trip_delta: int
    thd_event: bool
    flags: set[str] = field(default_factory=set)


def simulate_days(
    *,
    feeder_id: str,
    rated_a: float,
    days: int,
    fault: str | None,
    fault_start_day: int = 10,
    seed: int = 1,
) -> list[DailyRecord]:
    import random

    rng = random.Random(seed)
    rls = ThermalRLS()
    load_shape = real_profile_cycle(days * STEPS_PER_DAY, scale=0.55)
    device_last_ts = 0.0
    records: list[DailyRecord] = []
    global_step = 0

    for day in range(days):
        theta_vals, current_ratios, cond_margins, pd_scores, k_n_vals, i_neutral_ratios = [], [], [], [], [], []
        arc_health_ok_day = True
        arc_trip_delta = 0
        thd_event_day = False
        temp_peak_c = -999.0
        flags_day: set[str] = set()
        drift_score = 2.0 + 0.2 * (day - fault_start_day) if (fault == "sensor_drift" and day >= fault_start_day) else None

        for s in range(STEPS_PER_DAY):
            t_air = ambient_temp_c(global_step)
            base_ratio = load_shape[global_step]
            currents = {p: base_ratio * rated_a * (1 + rng.uniform(-0.02, 0.02)) for p in ("L1", "L2", "L3")}
            k = {"L1": 1.0, "L2": 1.0, "L3": 1.0}
            i_neutral = rated_a * 0.03 * (1 + rng.uniform(-0.3, 0.3))
            rh = 55 + 10 * math.sin(2 * math.pi * (global_step * STEP_S / 3600 - 3) / 24) + rng.uniform(-3, 3)
            t_wall = t_air - 1.5
            comms_ok = True
            pd_score = 0.05

            active = fault is not None and day >= fault_start_day
            if fault == "loose_fast" and active:
                k[TARGET_PHASE] = 3.2
            elif fault == "loose_slow" and active:
                progress = max(0.0, min(1.0, (day - fault_start_day) / 12))
                k[TARGET_PHASE] = 1.0 + 2.0 * progress
            elif fault == "overload" and active:
                currents = {p: rated_a * (1.15 + 0.04 * rng.uniform(-1, 1)) for p in currents}
            elif fault == "thermal_runaway" and active:
                growth = (day - fault_start_day) + s / STEPS_PER_DAY
                k[TARGET_PHASE] = 1.0 + growth * 2.2
            elif fault == "neutral_harmonic" and active:
                i_neutral = rated_a * 0.22 * (1 + rng.uniform(-0.05, 0.05))
            elif fault == "condensation" and active:
                rh = 92 + rng.uniform(-2, 2)
                t_wall = t_air - 4.5
            elif fault == "insulation_pd" and active:
                pd_score = min(0.95, 0.05 + 0.08 * (day - fault_start_day))
            elif fault == "arc_health_fail" and active:
                arc_health_ok_day = False
            elif fault == "arc_trip" and day == fault_start_day and s == 0:
                arc_trip_delta += 1
            elif fault == "combined_loose_overload" and active:
                k[TARGET_PHASE] = 2.6
                currents = {p: v * 1.15 for p, v in currents.items()}
            elif fault == "transient_spike" and day == fault_start_day and s in (40, 41, 42):
                currents = {p: v * 1.6 for p, v in currents.items()}
            elif fault == "comms_dropout" and day == fault_start_day and 20 <= s < 70:
                comms_ok = False
            elif fault == "de_energised" and active:
                currents = {p: rated_a * 0.005 for p in currents}
                i_neutral = 0.05
            elif fault == "condensation_within_margin" and active:
                rh = 75 + rng.uniform(-3, 3)
                t_wall = t_air - 2.0
            elif fault == "grid_event_thd" and day == fault_start_day and 30 <= s < 50:
                thd_event_day = True

            temps = {p: t_air + k[p] * (currents[p] / rated_a) ** 2 * 30.0 for p in currents}
            t_neutral = t_air + 0.5 * (i_neutral / (rated_a * 0.1 + 1e-6)) ** 2 * 8.0
            temp_peak_c = max(temp_peak_c, temps[TARGET_PHASE])

            sibling_phases = [p for p in ("L1", "L2", "L3") if p != TARGET_PHASE]
            sibling_temps = [temps[p] for p in sibling_phases]
            th = theta_raw(temps[TARGET_PHASE], sibling_temps, rated_a)
            sibling_i_sq_mean = statistics.mean([currents[p] ** 2 for p in sibling_phases])
            delta_i_sq = (currents[TARGET_PHASE] ** 2 - sibling_i_sq_mean) / (rated_a ** 2)
            residual = rls.update(th, delta_i_sq)
            theta_vals.append(residual)
            current_ratios.append(max(currents.values()) / rated_a)
            cond_margins.append(condensation_margin_c(t_wall, t_air, max(1.0, min(rh, 99.0))))
            pd_scores.append(pd_score)
            k_n_vals.append(neutral_k(t_neutral - t_air, i_neutral))
            i_neutral_ratios.append(i_neutral / rated_a)

            now_ts = global_step * STEP_S
            if comms_ok:
                device_last_ts = now_ts
            step_flags = compute_expect_flags(
                now_ts=now_ts,
                last_ts=device_last_ts,
                period_s=STEP_S,
                current_a=currents[TARGET_PHASE],
                drift_score=drift_score,
            )
            flags_day |= step_flags
            global_step += 1

        records.append(
            DailyRecord(
                day_idx=day,
                theta_peak=max(theta_vals),
                theta_median=statistics.median(theta_vals),
                temp_peak_c=temp_peak_c,
                current_ratio_peak=max(current_ratios),
                current_ratio_avg=statistics.mean(current_ratios),
                i_neutral_ratio_avg=statistics.mean(i_neutral_ratios),
                k_n=statistics.median(k_n_vals),
                condensation_margin_min=min(cond_margins),
                pd_score_peak=max(pd_scores),
                arc_health_ok=arc_health_ok_day,
                arc_trip_delta=arc_trip_delta,
                thd_event=thd_event_day,
                flags=flags_day,
            )
        )
    return records


@dataclass
class Scenario:
    scenario_id: str
    title: str
    fault: str | None
    expected_alarm: bool
    fault_start_day: int = 10
    days: int = 20
    feeder_id: str = "F02"
    rated_a: float = 250.0
    seed: int = 1
    expected_flags: frozenset[str] = frozenset()

    def run(self) -> list[DailyRecord]:
        return simulate_days(
            feeder_id=self.feeder_id,
            rated_a=self.rated_a,
            days=self.days,
            fault=self.fault,
            fault_start_day=self.fault_start_day,
            seed=self.seed,
        )


SCENARIOS: list[Scenario] = [
    Scenario("A1", "Gevşek bağlantı - hızlı gelişen", "loose_fast", True),
    Scenario("A2", "Gevşek bağlantı - yavaş sürüklenme (haftalar önce haber)", "loose_slow", True, days=26),
    Scenario("A3", "Aşırı yük - sürekli %118", "overload", True),
    Scenario("A4", "Isıl kaçış - mutlak limitlere tırmanış", "thermal_runaway", True, days=16),
    Scenario("A5", "Nötr harmonik yüklenme", "neutral_harmonic", True),
    Scenario("A6", "Nem/yoğuşma - marj ihlali", "condensation", True),
    Scenario("A7", "Yalıtım bozulması - PD artışı", "insulation_pd", True),
    Scenario("A8", "Ark bütünlüğü - dedektör öz test hatası", "arc_health_fail", True),
    Scenario("A9", "Ark bütünlüğü - gerçek trip olayı", "arc_trip", True),
    Scenario("A10", "Kombine arıza - gevşek bağlantı + aşırı yük", "combined_loose_overload", True),
    Scenario("N1", "Normal dengeli yük (mevsimsel dalgalanma)", None, False),
    Scenario("N2", "Ani yük geçişi (transient) - debounce eler", "transient_spike", False),
    Scenario("N3", "Sensör/iletişim kopması - yalnız STALE", "comms_dropout", False, expected_flags=frozenset({"STALE"})),
    Scenario("N4", "Planlı bakım - de-enerjize fider", "de_energised", False, expected_flags=frozenset({"DE_ENERGISED"})),
    Scenario("N5", "Hafif nem - marj içinde", "condensation_within_margin", False),
    Scenario("N6", "Şebeke olayı adayı (THD) - ısıl bulgu yok", "grid_event_thd", False),
    Scenario("N7", "Sensör drift - kalibrasyon kayması", "sensor_drift", False, expected_flags=frozenset({"SENSOR_DRIFT"})),
]

SCENARIOS_BY_ID = {s.scenario_id: s for s in SCENARIOS}
