"""Demo/yük testi filosu: gerçek CT verisinden sağlıklı ve arızalı bağlantılar üretir.

`build_demo_fleet()` -- sabit 2 bağlantılık (biri sağlıklı, biri gevşek cıvatalı
arızalı) orijinal demo seti; hem Modbus demo sunucusu hem de monitoring API'si
(varsayılan mod) ve K4 sunum paketindeki kayıtlar bu ÇIKTIYA dayanıyor -- davranışı
değişmedi.

`build_fleet(n)` -- K2 2.4 (1000 pano yük testi) için genelleştirilmiş N-panolu
üretici, aynı gerçek CT verisi + θ/rules çekirdeğini kullanır, panoların bir
kısmına (varsayılan %12) rastgele arıza enjekte eder. Gerçek L1 serisi yalnızca
BİR KEZ okunup tüm panolar arasında paylaşılır -- her panonun kendi ayrı bir
`openpyxl` dosya okuması yapması (N pano için N kez aynı dosyayı ayrıştırmak)
gerçek bir performans israfı olurdu; bkz. docs/06-OLCEKLENEBILIRLIK.md.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from panogoz.contracts.channels import Phase
from panogoz.detector.theta import ThetaSample, compute_theta_series
from panogoz.rules.engine import SeverityEvent, evaluate_severity_series
from panogoz.sim.ct_data import CtSample, load_real_l1_series
from panogoz.sim.synthetic import ThermalSample, simulate_three_phase_thermal

RATED_CURRENT_A = 250.0  # AG Pano Donanım Listesi: fider anma akımı 250/400A
DEFAULT_FAULT_FRACTION = 0.12  # yük testinde gerçekçi bir karışım için


def _tile_l1_series(base: list[CtSample], days: float) -> list[CtSample]:
    """Gerçek ~1,5 günlük (152 nokta, 15dk aralık) L1 serisini istenen gün
    sayısına ulaşana kadar art arda tekrarlar (döngü başına son zaman
    damgasından devam ederek). Bu, GERÇEK ölçülmüş veri noktalarını
    çoğaltıyor -- uydurma/ekstrapole edilmiş yeni veri DEĞİL; yalnızca daha
    uzun bir yük-testi/backfill penceresi simüle etmek için gerçek desenin
    tekrarı (organizatör yalnızca 1,5 günlük gerçek seri verdi, bkz.
    panogoz/sim/ct_data.py docstring'i)."""
    if not base:
        return base
    period_s = base[1].t_s - base[0].t_s if len(base) > 1 else 900.0
    base_span_s = base[-1].t_s + period_s
    target_span_s = days * 86400.0
    if target_span_s <= base_span_s:
        cutoff = max(1, int(target_span_s / period_s))
        return base[:cutoff]
    tiles = int(target_span_s // base_span_s) + 1
    out: list[CtSample] = []
    for tile_i in range(tiles):
        offset_s = tile_i * base_span_s
        for s in base:
            out.append(CtSample(t_s=s.t_s + offset_s, secondary_ma=s.secondary_ma, primary_a=s.primary_a))
    cutoff = max(1, int(target_span_s / period_s))
    return out[:cutoff]


@dataclass(frozen=True)
class ConnectionTimeline:
    connection_id: str
    watched_phase: Phase
    three_phase: dict[Phase, list[ThermalSample]]
    theta: list[ThetaSample]
    severity: list[SeverityEvent]


def _build_timeline_from_series(
    connection_id: str,
    watched_phase: Phase,
    l1: list[CtSample],
    *,
    fault_phase: Phase | None,
    fault_start_s: float,
    rated_current_a: float = RATED_CURRENT_A,
    seed: int = 42,
) -> ConnectionTimeline:
    three_phase = simulate_three_phase_thermal(l1, fault_phase=fault_phase, fault_start_s=fault_start_s, seed=seed)
    theta_series = compute_theta_series(three_phase, rated_current_a=rated_current_a)
    return ConnectionTimeline(
        connection_id=connection_id,
        watched_phase=watched_phase,
        three_phase=three_phase,
        theta=theta_series[watched_phase],
        severity=evaluate_severity_series(theta_series[watched_phase]),
    )


def _build_timeline(connection_id: str, watched_phase: Phase, *, fault_phase: Phase | None, fault_start_s: float) -> ConnectionTimeline:
    """Geriye dönük uyumluluk sarmalayıcısı -- kendi L1 okumasını yapar (yalnızca
    build_demo_fleet()'in sabit 2-panolu, davranışı değişmemesi gereken yolu
    için; N-panolu yol _build_timeline_from_series'i doğrudan, paylaşılan tek
    bir l1 ile çağırır)."""
    l1 = load_real_l1_series()
    return _build_timeline_from_series(connection_id, watched_phase, l1, fault_phase=fault_phase, fault_start_s=fault_start_s)


def build_demo_fleet() -> list[ConnectionTimeline]:
    l1 = load_real_l1_series()
    fault_start_s = l1[len(l1) // 2].t_s
    return [
        _build_timeline("F01-L1 (sağlıklı)", Phase.L1, fault_phase=None, fault_start_s=0.0),
        _build_timeline("F02-L2 (gevşek cıvatalı bağlantı)", Phase.L2, fault_phase=Phase.L2, fault_start_s=fault_start_s),
    ]


def build_cusum_demo_connection(
    *, backfill_days: float = 40.0, fault_start_day: float = 30.0
) -> ConnectionTimeline:
    """K3 3.2 (Kanıt ekranı) için AYRI, açıkça etiketli bir örnek bağlantı --
    `build_demo_fleet()`'in sabit 2 panosuna DAHİL DEĞİL, o listeyi/davranışını
    değiştirmez. `panogoz.detector.cusum.cusum_changepoint()` varsayılan
    `baseline_days=30` istiyor; gerçek organizatör verisi yalnızca ~1.6 gün
    olduğu için CUSUM gerçek filoda her zaman "yetersiz veri" döner (dürüst
    durum, UI'da öyle gösterilir). Bu fonksiyon, CUSUM'un GERÇEKTEN tetiklendiği
    çalışan bir örnek görebilmek için `_tile_l1_series` ile gerçek ölçülen
    deseni (uydurma yeni veri değil, aynı gerçek noktaların tekrarı) 40 güne
    uzatır, gün 30'dan sonra L3'e arıza enjekte eder (~29 günlük durağan
    taban çizgisi + ~10 gün kalıcı kayma)."""
    l1 = load_real_l1_series()
    l1 = _tile_l1_series(l1, backfill_days)
    return _build_timeline_from_series(
        "DEMO-L3 (uzatılmış CUSUM örneği — gerçek ölçümün tekrarı)",
        Phase.L3,
        l1,
        fault_phase=Phase.L3,
        fault_start_s=fault_start_day * 86400.0,
    )


def build_fleet(
    n_panels: int,
    *,
    rated_current_a: float = RATED_CURRENT_A,
    fault_fraction: float = DEFAULT_FAULT_FRACTION,
    backfill_days: float | None = None,
    seed: int = 42,
) -> list[ConnectionTimeline]:
    """N sentetik pano üretir (K2 2.4 yük testi + `panogoz.run_local` için).

    Gerçek CT L1 serisi yalnızca bir kez okunur (bkz. modül docstring'i).
    `fault_fraction` kadarına rastgele bir fazda gevşek-cıvata arızası enjekte
    edilir (deterministik: `seed`), gerçekçi bir sağlıklı/arızalı karışımı
    için -- 0 arıza veya %100 arıza tek başına bir yük testini temsil etmez.
    """
    if n_panels < 1:
        raise ValueError("n_panels >= 1 olmalı")
    rng = random.Random(seed)
    l1 = load_real_l1_series()
    if backfill_days is not None:
        l1 = _tile_l1_series(l1, backfill_days)
    if len(l1) < 2:
        raise ValueError("backfill_days çok küçük, en az 2 örnek gerekiyor")
    fault_start_s = l1[len(l1) // 2].t_s
    phases = list(Phase)
    timelines: list[ConnectionTimeline] = []
    for i in range(n_panels):
        watched = phases[i % len(phases)]
        has_fault = rng.random() < fault_fraction
        fault_phase = watched if has_fault else None
        suffix = " (gevşek cıvatalı bağlantı)" if has_fault else " (sağlıklı)"
        connection_id = f"F{i + 1:04d}-{watched.value}{suffix}"
        timelines.append(
            _build_timeline_from_series(
                connection_id,
                watched,
                l1,
                fault_phase=fault_phase,
                fault_start_s=fault_start_s,
                rated_current_a=rated_current_a,
                seed=seed + i,
            )
        )
    return timelines
