"""θ metriği: kardeş fazlar arasındaki sıcaklık farkının yüke göre normalize hâli.

Sabit sıcaklık eşiği kullanmıyoruz çünkü üç faz da ortam/mevsim/yük etkisiyle
birlikte ısınıp soğuyor — bu ortak bileşen θ'da iptal olur, geriye yalnızca
fazlar arasındaki anormal fark kalır. Fiziksel gerekçe: sağlıklı bir bağlantının
fazlar-arası sıcaklık farkı yükle beraber ölçeklenir (ΔT ∝ I²), bozulmuş
(gevşek cıvata gibi) bir bağlantının fazlar-arası excess ısınması ise yükten
bağımsız bir katsayıdır — θ = ΔT / (I/I_rated)² bu katsayıyı tahmin eder.

Akım anma akımının %10'unun altındayken (I≈0) normalize etme gürültüyü
patlatır; bu rejimde θ hesaplanmaz (uninformative sayılır).
"""
from __future__ import annotations

from dataclasses import dataclass
from statistics import median

from panogoz.contracts.channels import Phase
from panogoz.sim.synthetic import ThermalSample

MIN_LOAD_FRACTION = 0.40  # 1/load_fraction^2 çarpanı düşük yükte gürültüyü patlatır


@dataclass(frozen=True)
class ThetaSample:
    t_s: float
    phase: Phase
    theta: float | None  # None: akım çok düşük, normalize edilemez (uninformative)


def compute_theta_series(
    three_phase: dict[Phase, list[ThermalSample]], *, rated_current_a: float
) -> dict[Phase, list[ThetaSample]]:
    """Her zaman adımında faz sıcaklığının kardeş medyanından sapmasını yüke göre normalize eder."""
    length = len(next(iter(three_phase.values())))
    result: dict[Phase, list[ThetaSample]] = {phase: [] for phase in Phase}
    min_load_a = MIN_LOAD_FRACTION * rated_current_a

    for i in range(length):
        row = {phase: three_phase[phase][i] for phase in Phase}
        sibling_median_c = median(sample.surface_temp_c for sample in row.values())
        t_s = row[Phase.L1].t_s
        for phase, sample in row.items():
            if sample.current_a < min_load_a:
                theta = None
            else:
                load_fraction = sample.current_a / rated_current_a
                theta = (sample.surface_temp_c - sibling_median_c) / (load_fraction**2)
            result[phase].append(ThetaSample(t_s=t_s, phase=phase, theta=theta))
    return result
