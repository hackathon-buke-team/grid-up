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
from panogoz.detector.common import lowpass
from panogoz.sim.synthetic import ThermalSample

MIN_LOAD_FRACTION = 0.40  # 1/load_fraction^2 çarpanı düşük yükte gürültüyü patlatır


@dataclass(frozen=True)
class ThetaSample:
    t_s: float
    phase: Phase
    theta: float | None  # None: akım çok düşük, normalize edilemez (uninformative)


def compute_theta_series(
    three_phase: dict[Phase, list[ThermalSample]],
    *,
    rated_current_a: float,
    lag_tau_s: float | None = None,
) -> dict[Phase, list[ThetaSample]]:
    """Her zaman adımında faz sıcaklığının kardeş medyanından sapmasını yüke göre normalize eder.

    `lag_tau_s` verilmezse (varsayılan) normalizasyon ANLIK (I/I_rated)^2 iledir.
    Verilirse (ısıl gecikme telafisi) (I/I_rated)^2, iletkenin ısıl modeliyle aynı
    birinci derece süzgeçten (tau=lag_tau_s) geçirilir. Gerekçe: ısıl model
    dT/dt = (k I^2 - dT)/tau olduğundan sıcaklık farkı ANLIK yükü değil süzülmüş
    I^2'yi izler. Yük hızla düşerken (gerçek CT serisinde 540 A -> 90 A sıçramaları)
    anlık I^2'ye bölmek hâlâ sıcak olan bir farkı küçük bir paya böler ve θ'yı
    sahte şişirir; süzülmüş I^2 bu geçici rejimi iptal eder. Tau, bilerek gerçek
    değerden farklı bir *tahmin* olarak verilmelidir (saha tau'sunu bilmez).
    """
    length = len(next(iter(three_phase.values())))
    result: dict[Phase, list[ThetaSample]] = {phase: [] for phase in Phase}
    min_load_a = MIN_LOAD_FRACTION * rated_current_a

    lagged_f2: dict[Phase, list[float]] | None = None
    if lag_tau_s is not None:
        first = three_phase[Phase.L1]
        period_s = first[1].t_s - first[0].t_s if length > 1 else lag_tau_s
        alpha = min(period_s / lag_tau_s, 1.0)
        lagged_f2 = {
            phase: lowpass([(s.current_a / rated_current_a) ** 2 for s in three_phase[phase]], alpha)
            for phase in Phase
        }

    for i in range(length):
        row = {phase: three_phase[phase][i] for phase in Phase}
        sibling_median_c = median(sample.surface_temp_c for sample in row.values())
        t_s = row[Phase.L1].t_s
        for phase, sample in row.items():
            if lagged_f2 is not None:
                f2 = lagged_f2[phase][i]
                theta = None if f2 < MIN_LOAD_FRACTION**2 else (sample.surface_temp_c - sibling_median_c) / f2
            elif sample.current_a < min_load_a:
                theta = None
            else:
                load_fraction = sample.current_a / rated_current_a
                theta = (sample.surface_temp_c - sibling_median_c) / (load_fraction**2)
            result[phase].append(ThetaSample(t_s=t_s, phase=phase, theta=theta))
    return result
