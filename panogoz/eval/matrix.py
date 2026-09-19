"""Doğruluk matrisi: senaryo x tohum koşuları, tespit/gecikme/yanlış alarm istatistikleri (K4 4.4).

Her koşu: `generate` (fizik modeli) -> `analyze` (dedektörler + bastırma + füzyon)
-> ALARM-üstü izlerin ilk yükseliş zamanları. Gerçek (truth) bilgisi üreticiden
gelir: arızanın başladığı an ve bağlantının gerçekten tehlikeye girdiği an
(eklem sıcaklık artışı >= 70 K, IEC 61439-1 Tablo 6, veya gerçek yoğuşma).

DÜRÜSTLÜK NOTU: bu bir saha doğrulaması DEĞİL. Senaryolar aynı ekibin yazdığı
fizik modellerinden üretiliyor; dedektör, üretici modelin *kendisine* (ör. birinci
derece ısıl gecikme) karşı sınanıyor. Anlamlı olan: (a) negatif kontrollerde yanlış
alarm bütçesi, (b) sabit eşikle kıyas, (c) duyarlılık/kör bölge, (d) model
parametrelerine (gürültü, tau) dayanıklılık.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from statistics import median

from panogoz.contracts.channels import Phase
from panogoz.rules.engine import Severity, debounce_severity
from panogoz.rules.pipeline import Analysis, Family, analyze
from panogoz.sim.scenarios import SCENARIOS, Expect, Scenario, ScenarioData, ScenarioParams, generate

DAY_S = 86400.0
FIXED_ABSOLUTE_C = 75.0  # klasik sabit sıcaklık alarm noktası
FIXED_RISE_K = 45.0  # ortama göre sabit sıcaklık artışı alarm noktası


@dataclass(frozen=True)
class RunResult:
    key: str
    seed: int
    expect: str
    expected_kind: str | None
    detected: bool | None  # DETECT/ADVISORY: beklenen ALARM üstü var mı; QUIET: None
    first_warning_s: float | None  # beklenen türde (trend dahil termal) ilk UYARI üstü
    first_alarm_s: float | None
    onset_s: float | None
    danger_s: float | None
    false_alarm_kinds: tuple[str, ...]  # izin verilmeyen ALARM üstü dedektörler
    false_alarm_episodes: int
    warning_kinds: tuple[str, ...]
    advisory_capped_samples: int
    fixed_absolute_first_s: float | None
    fixed_rise_first_s: float | None
    days: float

    @property
    def latency_days(self) -> float | None:
        if self.first_alarm_s is None or self.onset_s is None:
            return None
        return (self.first_alarm_s - self.onset_s) / DAY_S

    @property
    def lead_days(self) -> float | None:
        """Tehlikeye kalan süre (gün): gerçek tehlike anı - ilk ALARM. Negatif = geç kaldı."""
        if self.first_alarm_s is None or self.danger_s is None:
            return None
        return (self.danger_s - self.first_alarm_s) / DAY_S

    @property
    def warning_lead_days(self) -> float | None:
        if self.first_warning_s is None or self.danger_s is None:
            return None
        return (self.danger_s - self.first_warning_s) / DAY_S


def wilson_interval(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def _first_index(series: list[Severity], level: Severity, start: int) -> int | None:
    for i in range(start, len(series)):
        if series[i] >= level:
            return i
    return None


def _episodes(series: list[Severity], level: Severity) -> int:
    count, active = 0, False
    for s in series:
        hit = s >= level
        if hit and not active:
            count += 1
        active = hit
    return count


def _fixed_threshold_first(data: ScenarioData, rise: bool) -> float | None:
    raw: list[Severity] = []
    for i in range(len(data.t_s)):
        if not data.valid[i]:
            raw.append(Severity.NORMAL)
            continue
        hottest = max(data.joint_temp_c[p][i] for p in Phase)
        value = hottest - data.ambient_c[i] if rise else hottest
        limit = FIXED_RISE_K if rise else FIXED_ABSOLUTE_C
        raw.append(Severity.ALARM if value >= limit else Severity.NORMAL)
    confirmed = debounce_severity(raw)
    idx = _first_index(confirmed, Severity.ALARM, 0)
    return None if idx is None else data.t_s[idx]


def evaluate(scenario: Scenario, data: ScenarioData, analysis: Analysis) -> RunResult:
    truth = data.truth
    onset_s = truth.onset_t_s
    onset_i = 0 if onset_s is None else int(onset_s // data.period_s)
    process = [t for t in analysis.tracks if t.spec.family is not Family.SYSTEM]
    allowed = set(filter(None, [scenario.expected_kind])) | set(scenario.allowed_extra)

    first_alarm_s = first_warning_s = None
    if scenario.expected_kind is not None:
        tracks = [t for t in analysis.tracks if t.spec.kind == scenario.expected_kind]
        idx = [i for i in (_first_index(t.fused, Severity.ALARM, onset_i) for t in tracks) if i is not None]
        first_alarm_s = data.t_s[min(idx)] if idx else None
        warn_tracks = tracks + [t for t in analysis.tracks if t.spec.kind == "loose_bolt_trend" and scenario.expected_kind == "loose_bolt"]
        widx = [i for i in (_first_index(t.fused, Severity.WARNING, onset_i) for t in warn_tracks) if i is not None]
        first_warning_s = data.t_s[min(widx)] if widx else None

    fa_kinds: dict[str, int] = {}
    warn_kinds: set[str] = set()
    for t in analysis.tracks:
        if t.spec.family is Family.SYSTEM and t.spec.kind in allowed:
            continue
        eps = _episodes(t.fused, Severity.ALARM)
        if eps and t.spec.kind not in allowed:
            fa_kinds[t.spec.kind] = fa_kinds.get(t.spec.kind, 0) + eps
        elif t.spec.kind in allowed and scenario.expected_kind is not None:
            pre = _episodes(t.fused[:onset_i], Severity.ALARM) if onset_i else 0
            if pre:
                fa_kinds[t.spec.kind] = fa_kinds.get(t.spec.kind, 0) + pre
        if _first_index(t.fused, Severity.WARNING, 0) is not None and t.spec.kind not in allowed:
            warn_kinds.add(t.spec.kind)
    capped = sum(sum(t.capped) for t in process if t.spec.advisory)

    detected: bool | None
    if scenario.expect is Expect.DETECT:
        detected = first_alarm_s is not None
    elif scenario.expect is Expect.ADVISORY:
        detected = first_alarm_s is not None  # ADVISORY'de True = sevk edildi = istenmeyen
    else:
        detected = None

    return RunResult(
        key=scenario.key,
        seed=data.seed,
        expect=scenario.expect.value,
        expected_kind=scenario.expected_kind,
        detected=detected,
        first_warning_s=first_warning_s,
        first_alarm_s=first_alarm_s,
        onset_s=onset_s,
        danger_s=truth.danger_t_s,
        false_alarm_kinds=tuple(sorted(fa_kinds)),
        false_alarm_episodes=sum(fa_kinds.values()),
        warning_kinds=tuple(sorted(warn_kinds)),
        advisory_capped_samples=capped,
        fixed_absolute_first_s=_fixed_threshold_first(data, rise=False),
        fixed_rise_first_s=_fixed_threshold_first(data, rise=True),
        days=data.t_s[-1] / DAY_S,
    )


def run_scenario(key: str, seed: int) -> RunResult:
    scenario = SCENARIOS[key]
    data = generate(scenario, seed=seed)
    return evaluate(scenario, data, analyze(data))


def run_custom(scenario: Scenario, seed: int) -> RunResult:
    data = generate(scenario, seed=seed)
    return evaluate(scenario, data, analyze(data))


def _run_pair(args: tuple[str, int]) -> RunResult:
    return run_scenario(*args)


def run_matrix(seeds: list[int], *, keys: list[str] | None = None, workers: int = 1) -> list[RunResult]:
    jobs = [(k, s) for k in (keys or list(SCENARIOS)) for s in seeds]
    if workers <= 1:
        return [_run_pair(j) for j in jobs]
    from concurrent.futures import ProcessPoolExecutor

    with ProcessPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(_run_pair, jobs, chunksize=1))


@dataclass(frozen=True)
class FixedStats:
    """Sabit eşik kuralının bu senaryodaki sonucu. DETECT: `detected` onset'ten SONRA
    tetiklenen koşu sayısı, `false_alarms` onset'ten ÖNCE tetiklenenler; QUIET/ADVISORY:
    her tetikleme yanlış alarmdır."""

    detected: int
    false_alarms: int
    latency_days_median: float | None


@dataclass
class ScenarioSummary:
    key: str
    expect: str
    expected_kind: str | None
    runs: int
    detect_rate: float | None
    detect_ci: tuple[float, float] | None
    warning_rate: float | None
    latency_days_median: float | None
    latency_days_p90: float | None
    lead_days_median: float | None
    lead_days_min: float | None
    warning_lead_days_median: float | None
    alarmed_before_danger: float | None
    false_alarm_runs: int
    false_alarm_episodes: int
    false_alarm_kinds: tuple[str, ...]
    advisory_capped_samples: int
    warning_runs: int = 0
    warning_latency_days_median: float | None = None
    fixed_abs: "FixedStats" = None  # type: ignore[assignment]
    fixed_rise: "FixedStats" = None  # type: ignore[assignment]
    days: float = 0.0


def _pct(values: list[float], q: float) -> float | None:
    if not values:
        return None
    s = sorted(values)
    idx = min(len(s) - 1, max(0, math.ceil(q * len(s)) - 1))
    return s[idx]


def summarize(results: list[RunResult]) -> list[ScenarioSummary]:
    by_key: dict[str, list[RunResult]] = {}
    for r in results:
        by_key.setdefault(r.key, []).append(r)
    out: list[ScenarioSummary] = []
    for key, runs in by_key.items():
        expect = runs[0].expect
        n = len(runs)
        lat = [r.latency_days for r in runs if r.latency_days is not None]
        lead = [r.lead_days for r in runs if r.lead_days is not None]
        wlead = [r.warning_lead_days for r in runs if r.warning_lead_days is not None]
        det = sum(1 for r in runs if r.detected) if expect != Expect.QUIET.value else 0
        warn = sum(1 for r in runs if r.first_warning_s is not None)

        def fixed_stats(getter) -> FixedStats:
            detected = false_alarms = 0
            lats: list[float] = []
            for r in runs:
                first = getter(r)
                if first is None:
                    continue
                if expect == Expect.DETECT.value and first >= (r.onset_s or 0.0):
                    detected += 1
                    lats.append((first - (r.onset_s or 0.0)) / DAY_S)
                else:
                    false_alarms += 1
            return FixedStats(detected, false_alarms, median(lats) if lats else None)

        wlat = [(r.first_warning_s - r.onset_s) / DAY_S for r in runs if r.first_warning_s is not None and r.onset_s is not None]

        out.append(
            ScenarioSummary(
                key=key,
                expect=expect,
                expected_kind=runs[0].expected_kind,
                runs=n,
                detect_rate=(det / n) if expect != Expect.QUIET.value else None,
                detect_ci=wilson_interval(det, n) if expect != Expect.QUIET.value else None,
                warning_rate=(warn / n) if expect != Expect.QUIET.value else None,
                latency_days_median=median(lat) if lat else None,
                latency_days_p90=_pct(lat, 0.9),
                lead_days_median=median(lead) if lead else None,
                lead_days_min=min(lead) if lead else None,
                warning_lead_days_median=median(wlead) if wlead else None,
                alarmed_before_danger=(sum(1 for x in lead if x >= 0) / len(lead)) if lead else None,
                false_alarm_runs=sum(1 for r in runs if r.false_alarm_episodes),
                false_alarm_episodes=sum(r.false_alarm_episodes for r in runs),
                false_alarm_kinds=tuple(sorted({k for r in runs for k in r.false_alarm_kinds})),
                fixed_abs=fixed_stats(lambda r: r.fixed_absolute_first_s),
                fixed_rise=fixed_stats(lambda r: r.fixed_rise_first_s),
                advisory_capped_samples=sum(r.advisory_capped_samples for r in runs),
                warning_runs=sum(1 for r in runs if r.warning_kinds),
                warning_latency_days_median=median(wlat) if wlat else None,
                days=runs[0].days,
            )
        )
    return out


@dataclass(frozen=True)
class FalseAlarmBudget:
    panel_days: float
    false_alarm_episodes: int
    per_panel_year: float
    upper95_per_panel_year: float


def false_alarm_budget(results: list[RunResult]) -> FalseAlarmBudget:
    """Yalnız QUIET/ADVISORY koşulları: panel-günü başına ALARM üstü yanlış alarm.
    Sıfır olay için %95 üst sınır "üçün kuralı" (3/N)."""
    runs = [r for r in results if r.expect in (Expect.QUIET.value, Expect.ADVISORY.value)]
    panel_days = sum(r.days for r in runs)
    episodes = sum(r.false_alarm_episodes for r in runs) + sum(1 for r in runs if r.expect == Expect.ADVISORY.value and r.detected)
    years = panel_days / 365.0
    per_year = episodes / years if years else 0.0
    upper = (3.0 / years) if episodes == 0 and years else (episodes + 1.96 * math.sqrt(max(episodes, 1))) / years
    return FalseAlarmBudget(panel_days, episodes, per_year, upper)


# ---------------------------------------------------------------- duyarlılık taramaları


@dataclass(frozen=True)
class SweepPoint:
    label: float
    runs: int
    warning_rate: float
    alarm_rate: float
    latency_days_median: float | None
    lead_days_median: float | None
    warning_lead_days_median: float | None
    false_alarm_runs: int
    extra_warning_runs: int = 0  # izin verilmeyen türde UYARI üstü (sağlıklı koşularda "uyarı yükü")


def _sweep_point(label: float, results: list[RunResult]) -> SweepPoint:
    n = len(results)
    lat = [r.latency_days for r in results if r.latency_days is not None]
    lead = [r.lead_days for r in results if r.lead_days is not None]
    wlead = [r.warning_lead_days for r in results if r.warning_lead_days is not None]
    return SweepPoint(
        label=label,
        runs=n,
        warning_rate=sum(1 for r in results if r.first_warning_s is not None) / n,
        alarm_rate=sum(1 for r in results if r.first_alarm_s is not None) / n,
        latency_days_median=median(lat) if lat else None,
        lead_days_median=median(lead) if lead else None,
        warning_lead_days_median=median(wlead) if wlead else None,
        false_alarm_runs=sum(1 for r in results if r.false_alarm_episodes),
        extra_warning_runs=sum(1 for r in results if r.warning_kinds),
    )


def _loose_bolt(params: ScenarioParams, key: str) -> Scenario:
    return Scenario(key, key, "", Expect.DETECT, "loose_bolt", params, frozenset({"loose_bolt_trend"}))


def sweep_fault_magnitude(seeds: list[int], multipliers: tuple[float, ...] = (1.2, 1.4, 1.7, 2.0, 3.0, 4.0)) -> list[SweepPoint]:
    """Gevşek cıvata direnç çarpanı -> tespit oranı. Kör bölgeyi gösterir."""
    points = []
    for m in multipliers:
        sc = _loose_bolt(ScenarioParams(fault_phase=Phase.L2, fault_k_mult=m), f"loose_bolt_x{m}")
        points.append(_sweep_point(m, [run_custom(sc, s) for s in seeds]))
    return points


def sweep_sensor_noise(seeds: list[int], scales: tuple[float, ...] = (1.0, 2.0, 4.0)) -> tuple[list[SweepPoint], list[SweepPoint]]:
    """Sensör gürültü+ofset çarpanı: (arıza tespiti, sağlıklı-yanlış alarm)."""
    detect, healthy = [], []
    for sc_scale in scales:
        fault = _loose_bolt(
            ScenarioParams(fault_phase=Phase.L2, fault_k_mult=3.0, sensor_noise_scale=sc_scale), f"noise_x{sc_scale}"
        )
        detect.append(_sweep_point(sc_scale, [run_custom(fault, s) for s in seeds]))
        quiet = Scenario(f"healthy_noise_x{sc_scale}", "", "", Expect.QUIET, None, ScenarioParams(sensor_noise_scale=sc_scale))
        healthy.append(_sweep_point(sc_scale, [run_custom(quiet, s) for s in seeds]))
    return detect, healthy


def sweep_ramp_duration(seeds: list[int], ramps: tuple[float, ...] = (7.0, 14.0, 28.0, 56.0)) -> list[SweepPoint]:
    """Bozulma hızı (gün): kademeli gevşemede tehlikeye kalan süre (haber verme süresi)."""
    points = []
    for ramp in ramps:
        params = ScenarioParams(
            days=int(32 + ramp + 14), onset_day=32.0, fault_phase=Phase.L3, fault_k_mult=4.0, fault_ramp_days=ramp
        )
        sc = _loose_bolt(params, f"ramp_{ramp}")
        points.append(_sweep_point(ramp, [run_custom(sc, s) for s in seeds]))
    return points


def sweep_thermal_tau(
    seeds: list[int], taus: tuple[float, ...] = (600.0, 1200.0, 1800.0, 3600.0, 7200.0)
) -> dict[str, list[SweepPoint]]:
    """MODEL UYUMSUZLUĞU: bağlantının gerçek ısıl tau'su değişir, dedektörün θ gecikme
    telafisi tau tahmini SABİT (1500 s) kalır. Sağlıklı, faz-dengesizliği (en hassas
    negatif kontrol) ve arızalı (k x2,2) durumlar."""
    healthy_sc = Scenario("tau_healthy", "", "", Expect.QUIET, None)
    result: dict[str, list[SweepPoint]] = {"healthy": [], "imbalance": [], "fault": []}
    for tau in taus:
        result["healthy"].append(
            _sweep_point(tau, [run_custom(replace(healthy_sc, params=ScenarioParams(thermal_tau_s=tau)), s) for s in seeds])
        )
        imb = Scenario("tau_imbalance", "", "", Expect.QUIET, None, ScenarioParams(thermal_tau_s=tau, phase_imbalance=(0.10, -0.08)))
        result["imbalance"].append(_sweep_point(tau, [run_custom(imb, s) for s in seeds]))
        fault = _loose_bolt(ScenarioParams(thermal_tau_s=tau, fault_phase=Phase.L2, fault_k_mult=2.2), f"tau_fault_{tau}")
        result["fault"].append(_sweep_point(tau, [run_custom(fault, s) for s in seeds]))
    return result
