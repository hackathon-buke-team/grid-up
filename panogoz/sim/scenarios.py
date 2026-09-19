"""Çok kanallı senaryo üreticisi: arıza + negatif kontrol kütüphanesi (K4 4.4).

Organizatör yalnız TEK gerçek seri verdi (L1 CT akımı, ~1,6 gün). Sıcaklık/Nem,
PD ve ARC sekmeleri boş (bkz. panogoz/sim/ct_data.py). Bu modül o boşluğu,
gerçek yük *biçimini* kullanıp geri kalan kanalları açık fizik modelinden
üreterek doldurur:

- Yük: gerçek CT serisi (152 nokta / 15 dk) uzun bir pencereye döşenir ve
  RMS'i `load_fraction x anma akımı` olacak şekilde ÖLÇEKLENİR. Ölçekleme
  bilinçli bir modelleme kararıdır: ham seri anma akımının (250 A) üstünde
  (RMS 341 A) olduğundan sağlıklı bir bağlantı "aşırı yüklü" görünürdü.
  Gündüz/gece biçimi ve ani sıçramalar gerçek veriden gelir, genlik ölçeği
  bizim modelimizdir.
- Isıl: panogoz/sim/synthetic.py ile aynı birinci derece gecikme modeli
  (tau=1800 s, T_hedef = T_iç + k I^2), ama zamanla değişen ortam, kademeli
  bozulma, nötr iletkeni, sensör gürültüsü (MAX31855: 0,25 °C çözünürlük) ve
  sensörler arası statik ofset ile.
- Nem/yoğuşma: dış sıcaklık gün-içi sinüsü + AR(1) hava durumu; duvar sıcaklığı
  iç hava ile (3 saat gecikmeli) dış sıcaklık arasında; RH gece yüksek.
- PD: taban gürültü + nemle büyüyen yüzey izlenmesi (tracking) bileşeni.
- Ark: ABB TVOC-2 trip kaydı + tanılama (sensör sağlıklı mı) bitleri.

Tüm parametreler bu dosyada açıkça görünür; sonuçlar SAHA doğrulaması DEĞİL,
tanımlı fizik modellerine karşı öz-tutarlılık doğrulamasıdır (docs/09).
"""
from __future__ import annotations

import cmath
import math
import random
from dataclasses import dataclass, field
from enum import Enum
from functools import lru_cache

from panogoz.contracts.channels import Phase
from panogoz.detector.condensation import dew_point_c
from panogoz.sim.ct_data import SAMPLE_PERIOD_S, load_real_l1_series
from panogoz.sim.demo_fleet import RATED_CURRENT_A, _tile_l1_series

DAY_S = 86400.0

INSIDE_RISE_K = 8.0  # kapalı kabinde iç hava, dış sıcaklığı bire bir izler + yük/güneş ısınması
K_PHASE_NORMAL = 0.0006  # K/A^2 (panogoz/sim/synthetic.py ile aynı, 250 A'da ~37,5 K)
K_NEUTRAL_NORMAL = 0.0012  # nötr bara daha küçük kesitli -> A^2 başına daha çok ısınır
TAU_S = 1800.0
NEUTRAL_RATED_FRACTION = 0.5  # nötr baranın anma akımı = faz anma akımının %50'si
SENSOR_NOISE_K = 0.25
SENSOR_OFFSET_SIGMA_K = 0.5
TEMP_QUANTUM_K = 0.25  # MAX31855 çözünürlüğü
DANGER_RISE_K = 70.0  # IEC 61439-1 Tablo 6: harici yalıtımlı iletken terminalleri (70 K)


class Expect(str, Enum):
    DETECT = "detect"
    ADVISORY = "advisory"
    QUIET = "quiet"


@dataclass(frozen=True)
class ScenarioParams:
    days: int = 60
    onset_day: float = 35.0
    load_fraction: float = 0.70
    overload_factor: float = 1.0
    overload_days: float = 0.0
    load_step_factor: float = 1.0
    load_step_days: float = 0.0
    phase_imbalance: tuple[float, float] = (0.01, -0.01)
    fault_phase: Phase | None = None
    fault_k_mult: float = 1.0
    fault_ramp_days: float = 0.0
    summer_delta_k: float = 0.0
    summer_full_day: float = 20.0
    h3_base: float = 0.12
    h3_final: float = 0.12
    h3_ramp_days: float = 0.0
    neutral_k_mult: float = 1.0
    neutral_ramp_days: float = 0.0
    rh_base: float = 40.0
    rh_delta_final: float = 0.0
    rh_ramp_days: float = 0.0
    pd_final: float = 0.0
    pd_ramp_days: float = 0.0
    pd_burst_prob: float = 0.0
    arc_trip_day: float | None = None
    arc_sensor_fault_day: float | None = None
    dropout: tuple[float, float] | None = None
    de_energised: tuple[float, float] | None = None
    temp_glitch_prob: float = 0.0
    sensor_noise_scale: float = 1.0  # sıcaklık gürültüsü ve ofset sigma'sı için çarpan (duyarlılık analizi)
    thermal_tau_s: float = TAU_S  # bağlantının GERÇEK ısıl zaman sabiti (dedektör bunu bilmez)


@dataclass(frozen=True)
class Scenario:
    key: str
    title: str
    description: str
    expect: Expect
    expected_kind: str | None
    params: ScenarioParams = field(default_factory=ScenarioParams)
    # Aynı fiziksel olayın doğal yan etkisi olarak ALARM verebilen ek dedektörler
    # (örn. aşırı yük nötr akımını da orantılı yükseltir). Bunlar yanlış alarm sayılmaz.
    allowed_extra: frozenset[str] = frozenset()


@dataclass(frozen=True)
class Truth:
    """Üreticinin bildiği gerçek: ne zaman başladı, ne zaman gerçekten tehlikeye girdi."""

    kind: str | None
    onset_t_s: float | None
    danger_t_s: float | None


@dataclass(frozen=True)
class ScenarioData:
    key: str
    seed: int
    rated_current_a: float
    neutral_rated_a: float
    period_s: float
    t_s: list[float]
    current_a: dict[Phase, list[float]]
    neutral_current_a: list[float]
    joint_temp_c: dict[Phase, list[float]]
    neutral_temp_c: list[float]
    ambient_c: list[float]
    wall_temp_c: list[float]
    humidity_rh: list[float]
    pd_index: list[float]
    arc_trip: list[int]
    arc_sensor_ok: list[int]
    valid: list[bool]
    truth: Truth


def _frac(day: float, onset: float, ramp_days: float) -> float:
    """Bozulma oranı 0..1: onset'ten önce 0; ramp_days=0 ise ani 1, aksi halde doğrusal."""
    if day < onset:
        return 0.0
    if ramp_days <= 0:
        return 1.0
    return min(1.0, (day - onset) / ramp_days)


def _in_window(day: float, start: float, length: float) -> bool:
    return length > 0 and start <= day < start + length


@lru_cache(maxsize=1)
def _real_l1():
    return tuple(load_real_l1_series())


@lru_cache(maxsize=8)
def _scaled_load_profile(days: int, load_fraction: float, rated_a: float) -> tuple[float, ...]:
    tiled = _tile_l1_series(list(_real_l1()), float(days))
    rms = math.sqrt(sum(s.primary_a**2 for s in tiled) / len(tiled))
    scale = load_fraction * rated_a / rms
    return tuple(s.primary_a * scale for s in tiled)


def _quantize(value: float) -> float:
    return round(value / TEMP_QUANTUM_K) * TEMP_QUANTUM_K


def generate(scenario: Scenario | ScenarioParams, *, seed: int = 1, key: str | None = None) -> ScenarioData:
    if isinstance(scenario, Scenario):
        params, key, kind = scenario.params, scenario.key, scenario.expected_kind
    else:
        params, key, kind = scenario, key or "custom", None

    rng = random.Random(seed)
    rated = RATED_CURRENT_A
    neutral_rated = NEUTRAL_RATED_FRACTION * rated
    dt = float(SAMPLE_PERIOD_S)
    base = _scaled_load_profile(params.days, params.load_fraction, rated)
    n = len(base)
    alpha = min(dt / params.thermal_tau_s, 1.0)
    wall_alpha = dt / (3 * 3600.0)
    phasor = cmath.exp(2j * math.pi / 3)

    noise_k = SENSOR_NOISE_K * params.sensor_noise_scale
    offsets = {p: rng.gauss(0.0, SENSOR_OFFSET_SIGMA_K * params.sensor_noise_scale) for p in Phase}
    neutral_offset = rng.gauss(0.0, SENSOR_OFFSET_SIGMA_K * params.sensor_noise_scale)
    imbalance = {Phase.L1: 0.0, Phase.L2: params.phase_imbalance[0], Phase.L3: params.phase_imbalance[1]}

    t_list: list[float] = []
    current = {p: [] for p in Phase}
    joint = {p: [] for p in Phase}
    neutral_i: list[float] = []
    neutral_t: list[float] = []
    ambient_l: list[float] = []
    wall_l: list[float] = []
    rh_l: list[float] = []
    pd_l: list[float] = []
    arc_l: list[int] = []
    arc_ok_l: list[int] = []
    valid_l: list[bool] = []

    weather = 0.0
    rh_noise = 0.0
    wall_out_lp: float | None = None
    temps: dict[Phase, float] = {}
    neutral_temp = 0.0
    onset = params.onset_day
    danger_t: float | None = None
    onset_t = onset * DAY_S

    for i in range(n):
        t = i * dt
        day = t / DAY_S
        dfrac = (t % DAY_S) / DAY_S
        diurnal = math.sin(2 * math.pi * (dfrac - 0.4))

        weather = 0.97 * weather + rng.gauss(0.0, 0.25)
        summer = params.summer_delta_k * min(1.0, day / params.summer_full_day) if params.summer_full_day > 0 else params.summer_delta_k
        outdoor = 22.0 + summer + 6.0 * diurnal + weather
        inside = outdoor + INSIDE_RISE_K + rng.gauss(0.0, 0.15)
        wall_out_lp = outdoor if wall_out_lp is None else wall_out_lp + wall_alpha * (outdoor - wall_out_lp)
        wall = inside - 0.35 * (inside - wall_out_lp)

        rh_noise = 0.95 * rh_noise + rng.gauss(0.0, 0.45)
        rh = params.rh_base + params.rh_delta_final * _frac(day, onset, params.rh_ramp_days) - 8.0 * diurnal + rh_noise
        rh = min(98.0, max(5.0, rh))

        load = base[i]
        if _in_window(day, onset, params.overload_days):
            load *= params.overload_factor
        if _in_window(day, onset, params.load_step_days):
            load *= params.load_step_factor
        energised = not (params.de_energised and params.de_energised[0] <= day < params.de_energised[1])
        if not energised:
            load = 0.3

        ip = {p: max(0.0, load * (1.0 + imbalance[p] + rng.gauss(0.0, 0.005))) for p in Phase}
        h3 = params.h3_base + (params.h3_final - params.h3_base) * _frac(day, onset, params.h3_ramp_days)
        mean_i = sum(ip.values()) / 3.0
        harmonic = 3.0 * h3 * mean_i
        unbalance = abs(ip[Phase.L1] + ip[Phase.L2] * phasor**2 + ip[Phase.L3] * phasor)
        in_a = math.sqrt(unbalance**2 + harmonic**2) if energised else 0.1

        fault_frac = _frac(day, onset, params.fault_ramp_days)
        neutral_frac = _frac(day, onset, params.neutral_ramp_days)
        targets: dict[Phase, float] = {}
        for p in Phase:
            k = K_PHASE_NORMAL
            if p is params.fault_phase:
                k *= 1.0 + (params.fault_k_mult - 1.0) * fault_frac
            targets[p] = inside + k * ip[p] ** 2
        kn = K_NEUTRAL_NORMAL * (1.0 + (params.neutral_k_mult - 1.0) * neutral_frac)
        neutral_target = inside + kn * in_a**2
        if i == 0:
            temps = dict(targets)
            neutral_temp = neutral_target
        else:
            for p in Phase:
                temps[p] += alpha * (targets[p] - temps[p])
            neutral_temp += alpha * (neutral_target - neutral_temp)

        if danger_t is None and day >= onset:
            if params.fault_phase is not None or params.overload_days > 0 or params.neutral_k_mult > 1.0 or params.h3_final > params.h3_base:
                rise = max(max(temps.values()), neutral_temp) - inside
                if rise >= DANGER_RISE_K:
                    danger_t = t
            if kind == "condensation" and wall < dew_point_c(inside, rh):
                danger_t = t

        readings = {p: temps[p] + offsets[p] + rng.gauss(0.0, noise_k) for p in Phase}
        n_reading = neutral_temp + neutral_offset + rng.gauss(0.0, noise_k)
        if params.temp_glitch_prob and rng.random() < params.temp_glitch_prob:
            victim = rng.choice(list(Phase))
            readings[victim] += rng.choice((-1.0, 1.0)) * rng.uniform(10.0, 25.0)

        humidity_factor = 1.0 + max(0.0, rh - 60.0) / 40.0
        pd = 3.0 * humidity_factor + abs(rng.gauss(0.0, 1.2))
        pd += params.pd_final * _frac(day, onset, params.pd_ramp_days) * (0.7 + 0.3 * humidity_factor)
        if params.pd_burst_prob and rng.random() < params.pd_burst_prob:
            pd += rng.uniform(40.0, 90.0)

        arc = 0
        if params.arc_trip_day is not None:
            trip_i = int(params.arc_trip_day * DAY_S / dt)
            if trip_i <= i < trip_i + 4:
                arc = 1
        arc_ok = 0 if (params.arc_sensor_fault_day is not None and day >= params.arc_sensor_fault_day) else 1

        ok = not (params.dropout and params.dropout[0] <= day < params.dropout[1])

        t_list.append(t)
        for p in Phase:
            current[p].append(ip[p])
            joint[p].append(_quantize(readings[p]))
        neutral_i.append(in_a)
        neutral_t.append(_quantize(n_reading))
        ambient_l.append(_quantize(inside + rng.gauss(0.0, 0.1)))
        wall_l.append(_quantize(wall + rng.gauss(0.0, 0.1)))
        rh_l.append(rh)
        pd_l.append(pd)
        arc_l.append(arc)
        arc_ok_l.append(arc_ok)
        valid_l.append(ok)

    if params.arc_trip_day is not None:
        danger_t = params.arc_trip_day * DAY_S
        onset_t = danger_t
    if params.arc_sensor_fault_day is not None:
        onset_t = params.arc_sensor_fault_day * DAY_S

    has_fault = kind is not None
    return ScenarioData(
        key=key,
        seed=seed,
        rated_current_a=rated,
        neutral_rated_a=neutral_rated,
        period_s=dt,
        t_s=t_list,
        current_a=current,
        neutral_current_a=neutral_i,
        joint_temp_c=joint,
        neutral_temp_c=neutral_t,
        ambient_c=ambient_l,
        wall_temp_c=wall_l,
        humidity_rh=rh_l,
        pd_index=pd_l,
        arc_trip=arc_l,
        arc_sensor_ok=arc_ok_l,
        valid=valid_l,
        truth=Truth(kind=kind, onset_t_s=onset_t if has_fault else None, danger_t_s=danger_t if has_fault else None),
    )


def _s(
    key: str, title: str, description: str, expect: Expect, kind: str | None, *, also: tuple[str, ...] = (), **params
) -> Scenario:
    return Scenario(key, title, description, expect, kind, ScenarioParams(**params), frozenset(also))


SCENARIOS: dict[str, Scenario] = {
    s.key: s
    for s in (
        # ---- arıza senaryoları (tespit edilmeli) ----
        _s("loose_bolt_abrupt", "Gevşek cıvata (ani)", "L2 bağlantı direnci gün 35'te 2,2 kat artar (erken evre gevşeme).", Expect.DETECT, "loose_bolt",
           also=("loose_bolt_trend",), fault_phase=Phase.L2, fault_k_mult=2.2),
        _s("loose_bolt_gradual", "Gevşek cıvata (kademeli)", "L3 direnci gün 32'den itibaren 28 günde 4 kata çıkar.", Expect.DETECT, "loose_bolt",
           also=("loose_bolt_trend",), onset_day=32.0, fault_phase=Phase.L3, fault_k_mult=4.0, fault_ramp_days=28.0),
        _s("loose_bolt_in_summer", "Gevşek cıvata (sıcak yaz)", "Ortam +16 K sıcak; L2 gevşemesi yine ayırt edilmeli.", Expect.DETECT, "loose_bolt",
           also=("loose_bolt_trend",), fault_phase=Phase.L2, fault_k_mult=2.2, summer_delta_k=16.0, summer_full_day=20.0),
        _s("loose_bolt_low_load", "Gevşek cıvata (düşük yükte gizli)", "Yük anma akımının %45'i; sabit sıcaklık kuralları göremez, θ yüke göre normalize eder.", Expect.DETECT, "loose_bolt",
           also=("loose_bolt_trend",), fault_phase=Phase.L2, fault_k_mult=2.2, load_fraction=0.45),
        _s("overload_sustained", "Sürekli aşırı yük", "Yük gün 35'ten itibaren 4 gün boyunca %35 artar.", Expect.DETECT, "overload",
           also=("neutral_overload",), overload_factor=1.35, overload_days=4.0),
        _s("condensation_leak", "Yoğuşma riski (nem sızıntısı)", "Bağıl nem 8 günde %40'tan %92'ye çıkar; gece duvar çiy noktasının altına iner.", Expect.DETECT, "condensation",
           also=("humidity_high",), rh_delta_final=52.0, rh_ramp_days=8.0),
        _s("neutral_harmonic", "Nötr harmonik yüklenmesi", "3. harmonik payı 3 günde %12'den %38'e çıkar; nötr akımı fazı geçer.", Expect.DETECT, "neutral_overload",
           h3_final=0.38, h3_ramp_days=3.0),
        _s("neutral_joint_loose", "Nötr bağlantı gevşemesi", "Nötr terminal direnci gün 35'te 3 kat artar.", Expect.DETECT, "neutral_joint",
           neutral_k_mult=3.0),
        _s("pd_tracking_humid", "PD + nem (yüzey izlenmesi)", "Nem ortalaması %64'e çıkarken PD indeksi 12 günde yükselir; iki kanal ailesi birlikte.", Expect.DETECT, "pd_tracking",
           also=("condensation", "humidity_high"), rh_delta_final=24.0, rh_ramp_days=12.0, pd_final=45.0, pd_ramp_days=12.0),
        _s("arc_trip", "Ark koruma tetiklemesi", "TVOC-2 trip kaydı gün 35'te set olur.", Expect.DETECT, "arc_trip",
           arc_trip_day=35.0),
        _s("arc_integrity_fault", "Ark koruma bütünlüğü kaybı", "TVOC-2 tanılama: sensör hatası (koruma devre dışı).", Expect.DETECT, "arc_integrity",
           arc_sensor_fault_day=35.0),
        # ---- yalnız tavsiye (sevk edilmemeli) ----
        _s("pd_only_dry", "PD tek başına (kuru hava)", "PD indeksi yükselir ama başka hiçbir kanal ailesi desteklemez.", Expect.ADVISORY, "pd_tracking",
           pd_final=45.0, pd_ramp_days=12.0),
        # ---- negatif kontroller (alarm ÜRETMEMELİ) ----
        _s("healthy_baseline", "Sağlıklı referans", "Hiçbir arıza yok, gerçek yük biçimi.", Expect.QUIET, None),
        _s("hot_summer", "Sıcak yaz (tüm fazlar ısınır)", "Ortam 50 günde +16 K yükselir; sabit eşik yanlış alarm verirdi.", Expect.QUIET, None,
           summer_delta_k=16.0, summer_full_day=50.0),
        _s("heavy_balanced_load", "Ağır ama dengeli yük", "RMS yük anma akımının %75'i; üç faz eşit ısınır.", Expect.QUIET, None,
           load_fraction=0.75),
        _s("load_step_moderate", "Ölçülü yük basamağı", "Yük 4 gün %12 artar (ısıl gecikme, kardeş medyanı iptal eder).", Expect.QUIET, None,
           load_step_factor=1.12, load_step_days=4.0),
        _s("phase_imbalance", "Faz yük dengesizliği", "L2 %10 fazla, L3 %8 az yüklü.", Expect.QUIET, None,
           phase_imbalance=(0.10, -0.08)),
        _s("sensor_glitch", "Tek örneklik sensör sıçramaları", "Termokupl rastgele ±10-25 K sıçrar (tek örnek).", Expect.QUIET, None,
           temp_glitch_prob=0.004),
        _s("de_energised_maintenance", "Bakım kesintisi (enerjisiz)", "Fider 2 gün açık; akım sıfır.", Expect.QUIET, None,
           de_energised=(38.0, 40.0)),
        _s("comms_dropout", "Haberleşme kaybı", "Cihaz 2 gün susar (STALE); süreç alarmı üretilmemeli.", Expect.QUIET, None,
           also=("comms_lost",), dropout=(38.0, 40.0)),
        _s("humid_but_warm", "Nemli ama marj yeterli", "RH ortalaması %54'e çıkar; duvar hâlâ çiy noktasının yeterince üstünde.", Expect.QUIET, None,
           rh_delta_final=14.0, rh_ramp_days=8.0),
        _s("pd_noise_bursts", "PD gürültü patlamaları", "Anahtarlama gürültüsü tek örneklik PD sıçramaları üretir.", Expect.QUIET, None,
           pd_burst_prob=0.003),
    )
}
