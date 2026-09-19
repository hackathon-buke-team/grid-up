"""Bastırma -> füzyon -> alarm hattının ilk iki katmanı (CLAUDE.md §2: "sıra sabit").

Her dedektörün puan serisi şu sırayla işlenir:

1. **Bastırma** -- dedektör kendi puanını üretirken geçersiz örnekleri (STALE),
   enerjisiz akımı (DE_ENERGISED), normalize edilemeyecek düşük yükü (LOW_LOAD) ve
   dolmamış pencereleri (WARMUP) None + gerekçe olarak işaretler. Gerekçe kaybolmaz,
   kanıt ekranı gösterir.
2. **Onay** -- histerezis (%40 ölü bant) + 3/5 debounce (panogoz/rules/engine.py).
3. **Füzyon** -- PD gibi "tavsiye" izleri, ikinci bir kanal ailesi (ısı veya nem)
   son 24 saatte en az UYARI vermedikçe UYARI'da tutulur ("iki kanal ailesi şartı").

Alarm yaşam döngüsü (aç/onayla/otomatik kapan/fırtına) bu dosyada değil,
panogoz/rules/alarms.py'de.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from panogoz.contracts.channels import Phase
from panogoz.detector.arc import arc_integrity_scores, arc_trip_scores
from panogoz.detector.common import (
    REASON_DE_ENERGISED,
    REASON_LOW_LOAD,
    REASON_STALE,
    REASON_WARMUP,
    Scored,
)
from panogoz.detector.condensation import condensation_scores, humidity_scores
from panogoz.detector.cusum import DAY_S, cusum_changepoint, daily_median_series
from panogoz.detector.flags import DE_ENERGISED_MAX_LOAD_FRACTION
from panogoz.detector.neutral import neutral_joint_scores, neutral_loading_scores
from panogoz.detector.overload import overload_scores
from panogoz.detector.pd import pd_scores
from panogoz.detector.theta import MIN_LOAD_FRACTION, ThetaSample, compute_theta_series
from panogoz.detector.thermal_tau import estimate_tau_s
from panogoz.rules.engine import (
    DEADBAND_FRACTION,
    THETA_THRESHOLDS,
    Severity,
    debounce_severity,
    severity_with_deadband,
)
from panogoz.sim.scenarios import ScenarioData
from panogoz.sim.synthetic import ThermalSample

FUSION_LOOKBACK_S = 24 * 3600.0
THETA_TAU_FALLBACK_S = 1500.0  # tau taban çizgisinden tahmin edilemezse (veri yok) kullanılan varsayılan
TAU_BASELINE_SAMPLES = 14 * 96
TREND_MIN_SIGMA_K = 1.0  # CUSUM pratik anlamlılık tabanı: θ'da 1 K'nın altı eyleme dönüşmez
_NEVER = 1e12  # bu seviyeye hiç ulaşılmaz (max_severity ile tavanlanan izler için)


class Family(str, Enum):
    THERMAL = "thermal"
    LOAD = "load"
    ENVIRONMENT = "environment"
    PD = "pd"
    ARC = "arc"
    SYSTEM = "system"


CORROBORATING_FAMILIES = frozenset({Family.THERMAL, Family.ENVIRONMENT})


@dataclass(frozen=True)
class TrackSpec:
    kind: str
    family: Family
    label: str
    unit: str
    thresholds: dict[Severity, float]
    deadband: float = DEADBAND_FRACTION
    debounce_window: int = 5
    debounce_hits: int = 3
    advisory: bool = False  # tek başına sevk edilmez; füzyon şartı
    max_severity: Severity = Severity.CRITICAL
    latching: bool = False  # olay tipi: sinyal dönse de onaya kadar açık kalır


def _thr(w: float, a: float, c: float) -> dict[Severity, float]:
    return {Severity.WARNING: w, Severity.ALARM: a, Severity.CRITICAL: c}


SPECS: dict[str, TrackSpec] = {
    s.kind: s
    for s in (
        TrackSpec("loose_bolt", Family.THERMAL, "Gevşek cıvatalı bağlantı (θ)", "K", dict(THETA_THRESHOLDS)),
        TrackSpec(
            "loose_bolt_trend", Family.THERMAL, "Kalıcı θ kayması (CUSUM)", "×h",
            _thr(1.0, _NEVER, _NEVER), deadband=0.20, max_severity=Severity.WARNING,
        ),
        TrackSpec("overload", Family.LOAD, "Aşırı yük (1 sa RMS / anma)", "×Ir", _thr(1.10, 1.25, 1.40), deadband=0.10),
        TrackSpec(
            "neutral_overload", Family.LOAD, "Nötr harmonik yüklenmesi", "×In", _thr(0.85, 1.00, 1.20), deadband=0.10
        ),
        TrackSpec("neutral_joint", Family.THERMAL, "Nötr bağlantı (K_N)", "×K0", _thr(1.5, 2.0, 3.0), deadband=0.20),
        TrackSpec("condensation", Family.ENVIRONMENT, "Yoğuşma riski (çiy marjı)", "K", _thr(3.0, 4.5, 6.0)),
        TrackSpec(
            "humidity_high", Family.ENVIRONMENT, "Yüksek nem (bağlam)", "%RH",
            _thr(65.0, _NEVER, _NEVER), deadband=0.10, max_severity=Severity.WARNING,
        ),
        TrackSpec("pd_tracking", Family.PD, "Kısmi deşarj (PD indeksi)", "idx", _thr(15.0, 30.0, 60.0), deadband=0.30, advisory=True),
        TrackSpec(
            "arc_trip", Family.ARC, "Ark koruma TRIP", "", _thr(0.5, 1.0, 2.0),
            deadband=0.0, debounce_window=1, debounce_hits=1, latching=True,
        ),
        TrackSpec("arc_integrity", Family.ARC, "Ark koruma bütünlüğü (sensör hatası)", "", _thr(0.5, 1.0, 2.0), deadband=0.0),
        TrackSpec(
            "comms_lost", Family.SYSTEM, "Cihaz susuyor (STALE)", "örnek",
            _thr(3.0, 96.0, _NEVER), deadband=0.0, debounce_window=1, debounce_hits=1,
        ),
    )
}


@dataclass
class Track:
    spec: TrackSpec
    phase: Phase | None
    scores: list[float | None]
    reasons: list[str | None]
    confirmed: list[Severity]
    fused: list[Severity]
    capped: list[bool]

    @property
    def key(self) -> str:
        return f"{self.spec.kind}:{self.phase.value}" if self.phase else self.spec.kind


@dataclass
class Analysis:
    data: ScenarioData
    tracks: list[Track] = field(default_factory=list)
    theta_tau_s: float = THETA_TAU_FALLBACK_S
    theta_tau_estimated: bool = False

    def track(self, key: str) -> Track:
        for t in self.tracks:
            if t.key == key:
                return t
        raise KeyError(key)

    def by_kind(self, kind: str) -> list[Track]:
        return [t for t in self.tracks if t.spec.kind == kind]


def _theta_inputs(data: ScenarioData) -> dict[Phase, list[ThermalSample]]:
    return {
        p: [
            ThermalSample(t_s=data.t_s[i], phase=p, current_a=data.current_a[p][i], surface_temp_c=data.joint_temp_c[p][i])
            for i in range(len(data.t_s))
        ]
        for p in Phase
    }


def _theta_scored(data: ScenarioData, theta: dict[Phase, list[ThetaSample]], phase: Phase) -> Scored:
    values: list[float | None] = []
    reasons: list[str | None] = []
    de_energised_a = DE_ENERGISED_MAX_LOAD_FRACTION * data.rated_current_a
    for i, sample in enumerate(theta[phase]):
        if not data.valid[i]:
            values.append(None)
            reasons.append(REASON_STALE)
        elif data.current_a[phase][i] < de_energised_a:
            values.append(None)
            reasons.append(REASON_DE_ENERGISED)
        elif sample.theta is None:
            values.append(None)
            reasons.append(REASON_LOW_LOAD)
        else:
            values.append(abs(sample.theta))
            reasons.append(None)
    return Scored(values, reasons)


def _trend_scored(data: ScenarioData, theta: dict[Phase, list[ThetaSample]], phase: Phase) -> Scored:
    """Günlük θ medyanları üzerinde nedensel (causal) CUSUM: gün d'nin örnekleri,
    yalnız gün d-1'in sonuna kadar görülen veriden hesaplanan istatistiği kullanır.

    Yalnız POZİTİF (ısınma) kayma izlenir: gevşek bağlantı direnç -> sıcaklık artışı
    üretir. Negatif kayma sağlıklı fazlarda 'kardeş medyanı' değişiminin yan etkisidir
    (arızalı faz medyanın üstüne çıkınca medyan diğer sağlam faza geçer ve o fazlar
    çıkarılmış olur); iki yönlü sürükleme SENSOR_DRIFT bayrağının (flags.py) işidir."""
    n = len(data.t_s)
    masked = [
        ThetaSample(t_s=s.t_s, phase=phase, theta=s.theta if (data.valid[i] and data.current_a[phase][i] >= DE_ENERGISED_MAX_LOAD_FRACTION * data.rated_current_a) else None)
        for i, s in enumerate(theta[phase])
    ]
    daily = daily_median_series(masked)
    try:
        result = cusum_changepoint(daily, min_sigma=TREND_MIN_SIGMA_K)
    except ValueError:
        return Scored([None] * n, [REASON_WARMUP] * n)

    baseline_end_day = result.day_index[29] if len(result.day_index) >= 30 else result.day_index[-1]
    ratio_by_day = {d: sp / result.h for d, sp in zip(result.day_index, result.s_pos)}  # yalnız ısınma yönü (S+)
    values: list[float | None] = []
    reasons: list[str | None] = []
    last_ratio: float | None = None
    days_sorted = sorted(ratio_by_day)
    pointer = 0
    for t in data.t_s:
        day = int(t // DAY_S)
        while pointer < len(days_sorted) and days_sorted[pointer] < day:
            last_ratio = ratio_by_day[days_sorted[pointer]]
            pointer += 1
        if day <= baseline_end_day or last_ratio is None:
            values.append(None)
            reasons.append(REASON_WARMUP)
        else:
            values.append(last_ratio)
            reasons.append(None)
    return Scored(values, reasons)


def _comms_scored(valid: list[bool]) -> Scored:
    values: list[float | None] = []
    run = 0
    for ok in valid:
        run = 0 if ok else run + 1
        values.append(float(run))
    return Scored(values, [None] * len(valid))


def _make_track(spec: TrackSpec, scored: Scored, phase: Phase | None) -> Track:
    raw = severity_with_deadband(scored.values, spec.thresholds, deadband=spec.deadband)
    confirmed = debounce_severity(raw, window=spec.debounce_window, min_hits=spec.debounce_hits)
    confirmed = [min(s, spec.max_severity) for s in confirmed]
    return Track(
        spec=spec,
        phase=phase,
        scores=scored.values,
        reasons=scored.reasons,
        confirmed=confirmed,
        fused=list(confirmed),
        capped=[False] * len(confirmed),
    )


def _apply_fusion(tracks: list[Track], period_s: float) -> None:
    n = len(tracks[0].confirmed)
    lookback = int(FUSION_LOOKBACK_S / period_s)
    support = [False] * n
    for tr in tracks:
        if not tr.spec.advisory and tr.spec.family in CORROBORATING_FAMILIES:
            for i, sev in enumerate(tr.confirmed):
                if sev >= Severity.WARNING:
                    support[i] = True
    recently_supported = [False] * n
    last_true = -10**9
    for i in range(n):
        if support[i]:
            last_true = i
        recently_supported[i] = (i - last_true) <= lookback
    for tr in tracks:
        if not tr.spec.advisory:
            continue
        for i, sev in enumerate(tr.confirmed):
            if sev > Severity.WARNING and not recently_supported[i]:
                tr.fused[i] = Severity.WARNING
                tr.capped[i] = True


def _estimate_joint_tau(data: ScenarioData) -> float | None:
    gate = (MIN_LOAD_FRACTION * data.rated_current_a) ** 2
    series = [(data.joint_temp_c[p], data.ambient_c, [i * i for i in data.current_a[p]]) for p in Phase]
    return estimate_tau_s(series, data.valid, gate, data.period_s, min(TAU_BASELINE_SAMPLES, len(data.t_s)))


def analyze(data: ScenarioData, *, use_trend: bool = True, theta_tau_s: float | None = None) -> Analysis:
    """`theta_tau_s=None` ise θ'nın ısıl gecikme telafisi için tau, üç fazın taban
    çizgisinden tahmin edilir (thermal_tau.py); tahmin edilemezse varsayılan kullanılır."""
    estimated = False
    tau = theta_tau_s
    if tau is None:
        tau = _estimate_joint_tau(data)
        estimated = tau is not None
        if tau is None:
            tau = THETA_TAU_FALLBACK_S
    theta = compute_theta_series(_theta_inputs(data), rated_current_a=data.rated_current_a, lag_tau_s=tau)
    tracks: list[Track] = []
    for phase in Phase:
        tracks.append(_make_track(SPECS["loose_bolt"], _theta_scored(data, theta, phase), phase))
        if use_trend:
            tracks.append(_make_track(SPECS["loose_bolt_trend"], _trend_scored(data, theta, phase), phase))
    tracks.append(_make_track(SPECS["overload"], overload_scores(data.current_a, data.rated_current_a, data.valid), None))
    tracks.append(
        _make_track(SPECS["neutral_overload"], neutral_loading_scores(data.neutral_current_a, data.neutral_rated_a, data.valid), None)
    )
    tracks.append(
        _make_track(
            SPECS["neutral_joint"],
            neutral_joint_scores(
                data.neutral_temp_c, data.ambient_c, data.neutral_current_a, data.neutral_rated_a, data.valid,
                period_s=data.period_s,
            ),
            None,
        )
    )
    tracks.append(_make_track(SPECS["condensation"], condensation_scores(data.ambient_c, data.humidity_rh, data.wall_temp_c, data.valid), None))
    tracks.append(_make_track(SPECS["humidity_high"], humidity_scores(data.humidity_rh, data.valid), None))
    tracks.append(_make_track(SPECS["pd_tracking"], pd_scores(data.pd_index, data.valid), None))
    tracks.append(_make_track(SPECS["arc_trip"], arc_trip_scores(data.arc_trip, data.valid), None))
    tracks.append(_make_track(SPECS["arc_integrity"], arc_integrity_scores(data.arc_sensor_ok, data.valid), None))
    tracks.append(_make_track(SPECS["comms_lost"], _comms_scored(data.valid), None))
    _apply_fusion(tracks, data.period_s)
    return Analysis(data=data, tracks=tracks, theta_tau_s=tau, theta_tau_estimated=estimated)
