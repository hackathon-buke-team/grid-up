"""Gerçek L1 akım serisinden üç fazlı yüzey sıcaklığı üreten fizik tabanlı simülatör.

Isıl model: dT/dt = (T_hedef - T) / tau, T_hedef = T_ortam + k * I^2 (birinci
dereceden gecikme; bağlantı noktasının ısıl kütlesini temsil eder). Cıvatalı
bağlantı gevşemesi temas direncini artırıp k katsayısını yükseltir — bu da o
fazda kardeşlerinden sapan bir sıcaklık eğilimi üretir; θ metriği bunu yakalar
(bkz. panogoz/detector/theta.py).

L2/L3 için gerçek veri yok — organizatör yalnız L1 sekonderini sağladı; normal
çalışmada üç faz da aynı yükü çektiği varsayılıp L1 + küçük gürültüyle türetilir.
Bu, gerçek veriye dayanan tek fazı, sentetik üretilen kardeşlerle karşılaştırıp
tespit mantığını göstermeye yeter; gerçek üç fazlı veri geldiğinde bu fonksiyon
değişmeden kalır, yalnızca girdi kaynağı değişir.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from panogoz.contracts.channels import Phase
from panogoz.sim.ct_data import CtSample

AMBIENT_TEMP_C = 30.0
K_THERMAL_NORMAL = 0.0006  # target sıcaklık artışı / A^2, sağlıklı bağlantı direnci
TAU_S = 1800.0  # ısıl zaman sabiti (bağlantı noktası kütlesi)


@dataclass(frozen=True)
class ThermalSample:
    t_s: float
    phase: Phase
    current_a: float
    surface_temp_c: float


PHASE_LOAD_NOISE_FRACTION = 0.01  # sağlıklı bir panoda fazlar arası tipik yük dengesizliği


def _phase_current(base_a: float, phase: Phase, *, rng: random.Random) -> float:
    if phase is Phase.L1:
        return base_a
    return base_a * (1.0 + rng.uniform(-PHASE_LOAD_NOISE_FRACTION, PHASE_LOAD_NOISE_FRACTION))


def simulate_three_phase_thermal(
    l1_series: list[CtSample],
    *,
    fault_phase: Phase | None = None,
    fault_start_s: float = 0.0,
    fault_k_multiplier: float = 3.0,
    ambient_c: float = AMBIENT_TEMP_C,
    seed: int = 42,
) -> dict[Phase, list[ThermalSample]]:
    """Her faz için ısıl gecikme modeliyle yüzey sıcaklığı serisi üretir.

    fault_phase verilirse, fault_start_s'den sonra o fazın ısıl katsayısı
    fault_k_multiplier ile çarpılır (gevşek cıvatalı bağlantı benzetimi).
    """
    rng = random.Random(seed)
    result: dict[Phase, list[ThermalSample]] = {phase: [] for phase in Phase}
    temps = {phase: ambient_c for phase in Phase}
    prev_t_s: float | None = None

    for sample in l1_series:
        dt_s = 0.0 if prev_t_s is None else sample.t_s - prev_t_s
        prev_t_s = sample.t_s
        for phase in Phase:
            current_a = _phase_current(sample.primary_a, phase, rng=rng)
            k = K_THERMAL_NORMAL
            if fault_phase is not None and phase is fault_phase and sample.t_s >= fault_start_s:
                k *= fault_k_multiplier
            target_c = ambient_c + k * current_a**2
            if dt_s > 0:
                alpha = min(dt_s / TAU_S, 1.0)
                temps[phase] += alpha * (target_c - temps[phase])
            else:
                temps[phase] = target_c
            result[phase].append(
                ThermalSample(t_s=sample.t_s, phase=phase, current_a=current_a, surface_temp_c=temps[phase])
            )
    return result
