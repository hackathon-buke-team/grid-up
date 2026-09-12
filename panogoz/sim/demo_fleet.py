"""Demo filosu: gerçek CT verisinden sağlıklı ve arızalı örnek bağlantı üretir.

Hem Modbus demo sunucusu hem de monitoring API'si tutarlı bir gösterim için
aynı iki bağlantıyı (biri sağlıklı, biri gevşek cıvatalı arızalı) kullanır.
"""
from __future__ import annotations

from dataclasses import dataclass

from panogoz.contracts.channels import Phase
from panogoz.detector.theta import ThetaSample, compute_theta_series
from panogoz.rules.engine import SeverityEvent, evaluate_severity_series
from panogoz.sim.ct_data import load_real_l1_series
from panogoz.sim.synthetic import ThermalSample, simulate_three_phase_thermal

RATED_CURRENT_A = 250.0  # AG Pano Donanım Listesi: fider anma akımı 250/400A


@dataclass(frozen=True)
class ConnectionTimeline:
    connection_id: str
    watched_phase: Phase
    three_phase: dict[Phase, list[ThermalSample]]
    theta: list[ThetaSample]
    severity: list[SeverityEvent]


def _build_timeline(connection_id: str, watched_phase: Phase, *, fault_phase: Phase | None, fault_start_s: float) -> ConnectionTimeline:
    l1 = load_real_l1_series()
    three_phase = simulate_three_phase_thermal(l1, fault_phase=fault_phase, fault_start_s=fault_start_s)
    theta_series = compute_theta_series(three_phase, rated_current_a=RATED_CURRENT_A)
    return ConnectionTimeline(
        connection_id=connection_id,
        watched_phase=watched_phase,
        three_phase=three_phase,
        theta=theta_series[watched_phase],
        severity=evaluate_severity_series(theta_series[watched_phase]),
    )


def build_demo_fleet() -> list[ConnectionTimeline]:
    l1 = load_real_l1_series()
    fault_start_s = l1[len(l1) // 2].t_s
    return [
        _build_timeline("F01-L1 (sağlıklı)", Phase.L1, fault_phase=None, fault_start_s=0.0),
        _build_timeline("F02-L2 (gevşek cıvatalı bağlantı)", Phase.L2, fault_phase=Phase.L2, fault_start_s=fault_start_s),
    ]
