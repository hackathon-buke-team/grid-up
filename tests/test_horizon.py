"""Eşiğe kalan gün: güven aralığı ve projeksiyon testleri."""
from __future__ import annotations

import math
import random

from panogoz.detector import changepoint as cp

DAY_S = 86400.0


def _days(n: int, t0: float = 1_750_000_000.0) -> list[float]:
    return [t0 + i * DAY_S for i in range(n)]


def _ramp(n: int, per_week: float, sigma: float, seed: int) -> list[float]:
    r = random.Random(seed)
    return [per_week * (i / 7.0) + r.gauss(0.0, sigma) for i in range(n)]


def test_ci_monotonic():
    """lo <= medyan <= hi, her zaman."""
    for seed in range(20):
        vals = _ramp(21, 0.2, 0.8, seed)
        lo, med, hi = cp.theil_sen_ci(vals, _days(21), 0.90)
        assert lo <= med <= hi, (lo, med, hi)


def test_ci_ranks_match_the_documented_arithmetic():
    """Spec §2.3: n=14 icin N=91, Var(S)=333.67, C=30.05, lo_rank=30, hi_rank=62."""
    n = 14
    N = n * (n - 1) // 2
    var_s = n * (n - 1) * (2 * n + 5) / 18.0
    c = cp.Z_TWO_SIDED[0.90] * math.sqrt(var_s)
    assert N == 91
    assert abs(var_s - 333.67) < 0.01
    assert abs(c - 30.05) < 0.02
    assert math.floor((N - c) / 2.0) == 30
    assert math.ceil((N + c) / 2.0) + 1 == 62


def test_ci_covers_the_true_slope():
    """Spec §12.1: 400 kosum, kapsama %84-96 arasinda."""
    hit = 0
    runs = 400
    for seed in range(runs):
        vals = _ramp(21, 0.2, 0.8, 5000 + seed)
        lo, _med, hi = cp.slope_ci_per_week(vals, _days(21), 21, 0.90)
        if lo <= 0.2 <= hi:
            hit += 1
    pct = 100.0 * hit / runs
    assert 84.0 <= pct <= 96.0, f"kapsama {pct:.1f}% - kestirici bozuk"


def test_ci_is_scale_invariant():
    """Aralik ve gurultu sigma ile dogrusal olceklendigi icin kapsama sigmadan bagimsiz."""
    def coverage(sigma: float) -> int:
        hit = 0
        for seed in range(200):
            vals = _ramp(21, 0.2, sigma, 7000 + seed)
            lo, _m, hi = cp.slope_ci_per_week(vals, _days(21), 21, 0.90)
            if lo <= 0.2 <= hi:
                hit += 1
        return hit
    assert coverage(0.8) == coverage(0.4)


def test_ci_lower_bound_goes_negative_on_a_flat_series():
    """Duz ve gurultulu seride alt sinir sifirin altina iner - sonsuz ust gun sinirinin kaynagi."""
    r = random.Random(99)
    flat = [1.2 + r.gauss(0.0, 0.8) for _ in range(21)]
    lo, _med, hi = cp.slope_ci_per_week(flat, _days(21), 21, 0.90)
    assert lo < 0.0 < hi


def test_theil_sen_return_value_is_unchanged_by_the_refactor():
    """Tek 25 K aykiri deger altinda egim hala 0.05 K/hafta icinde (modulun kendi iddiasi)."""
    vals = _ramp(21, 0.2, 0.0, 1)
    dirty = list(vals)
    dirty[10] += 25.0
    assert abs(cp.slope_per_week(dirty, _days(21)) - 0.2) < 0.05


def test_unsupported_confidence_is_refused():
    try:
        cp.theil_sen_ci(_ramp(21, 0.2, 0.8, 1), _days(21), 0.80)
    except ValueError as exc:
        assert "0.8" in str(exc)
    else:
        raise AssertionError("desteklenmeyen guven seviyesi sessizce kabul edildi")


def test_ci_short_series_returns_zeros():
    assert cp.theil_sen_ci([1.0, 2.0], _days(2), 0.90) == (0.0, 0.0, 0.0)
    assert cp.slope_ci_per_week([1.0, 2.0], _days(2)) == (0.0, 0.0, 0.0)


# --------------------------------------------------------------- EtaView --

from panogoz.contracts.live import EtaView, JointView, PanelLive  # noqa: E402


def test_etaview_defaults_are_the_silent_case():
    e = EtaView()
    assert e.target is None
    assert e.days is None and e.days_lo is None and e.days_hi is None
    assert e.valid_days == 0
    assert e.from_changepoint is False and e.changepoint_ts is None
    assert e.model == "dogrusal"
    assert e.capped is False
    assert e.reason == ""


def test_etaview_hangs_on_both_views():
    jv = JointView(key="C07-L2-PABUC", label="", zone="", conductor="L",
                   feeder_index=7, rated_a=400.0, monitored=True)
    assert isinstance(jv.eta, EtaView)
    pl = PanelLive(panel_key="SOKE-14", panel_index=14, site="", name="")
    assert isinstance(pl.eta, EtaView)
    # Iki gorunum ayri nesne tasir; paylasilan bir varsayilan mutasyonu
    # butun panolara sizmaz.
    jv.eta.days = 21.0
    assert pl.eta.days is None


def test_etaview_serialises_inside_the_panel_dict():
    pl = PanelLive(panel_key="SOKE-14", panel_index=14, site="", name="")
    pl.eta.target = "KRITIK"
    pl.eta.days = 21.0
    d = pl.to_dict()
    assert d["eta"]["target"] == "KRITIK"
    assert d["eta"]["days"] == 21.0


# --------------------------------------------------------------- horizon --

from panogoz.detector import horizon as hz  # noqa: E402

LADDER = (("IZLE", 2.0), ("UYARI", 5.0), ("KRITIK", 12.0), ("ACIL", 25.0))


def _series(n, start, per_week, sigma=0.0, seed=1):
    r = random.Random(seed)
    return [start + per_week * (i / 7.0) + r.gauss(0.0, sigma) for i in range(n)]


def test_next_step_picks_the_band_above_the_daily_value():
    assert hz.next_step(0.5, LADDER) == ("IZLE", 2.0)
    assert hz.next_step(3.0, LADDER) == ("UYARI", 5.0)
    assert hz.next_step(8.4, LADDER) == ("KRITIK", 12.0)
    assert hz.next_step(20.0, LADDER) == ("ACIL", 25.0)
    assert hz.next_step(25.0, LADDER) is None
    assert hz.next_step(31.0, LADDER) is None


def test_arithmetic_matches_the_hand_worked_example():
    """Spec §3: kalan 3.6 K, egim +1.20 K/hafta -> 21 gun."""
    vals = _series(21, 8.4 - 1.20 * (20 / 7.0), 1.20)
    times = _days(21)
    eta = hz.project(vals, times, [0.5] * 21, LADDER)
    assert eta.reason == ""
    assert eta.target == "KRITIK"
    assert abs(eta.slope_k_per_week - 1.20) < 0.01
    assert eta.days == 21.0
    assert eta.model == "dogrusal"


def test_rounding_direction_widens_the_interval():
    vals = _series(21, 0.0, 1.20, sigma=0.5, seed=3)
    eta = hz.project(vals, _days(21), [0.5] * 21, LADDER)
    assert eta.reason == ""
    assert eta.days_lo <= eta.days <= eta.days_hi
    assert eta.days_lo == math.floor(eta.days_lo)
    assert eta.days_hi == math.ceil(eta.days_hi)


def test_infinite_upper_bound_when_the_ci_spans_zero():
    r = random.Random(99)
    flat = [3.0 + r.gauss(0.0, 0.8) for _ in range(21)]
    eta = hz.project(flat, _days(21), [0.5] * 21, LADDER)
    if eta.reason == "":
        assert eta.days_hi is None
        assert eta.slope_lo_k_per_week <= 0.0
    else:
        assert eta.reason == hz.REASON_FLAT


def test_gate_neutral_is_out_of_scope():
    eta = hz.project(_series(21, 1.0, 1.0), _days(21), [0.5] * 21, LADDER,
                     conductor="N")
    assert eta.reason == hz.REASON_NEUTRAL
    assert eta.days is None and eta.target is None


def test_gate_top_of_ladder():
    eta = hz.project(_series(21, 30.0, 1.0), _days(21), [0.5] * 21, LADDER)
    assert eta.reason == hz.REASON_TOP
    assert eta.days is None and eta.target is None


def test_gate_insufficient_history():
    eta = hz.project(_series(9, 3.0, 1.0), _days(9), [0.5] * 9, LADDER)
    assert eta.reason == hz.REASON_HISTORY
    assert eta.valid_days == 9
    assert eta.days is None
    # Hedef yine bildirilir: operator neye dogru sayamadigimizi gorur.
    assert eta.target == "UYARI"


def test_gate_low_visibility_uses_theta_min_not_a_percentage():
    """theta_min hedef esigin ustundeyse o esige projeksiyon anlamsizdir."""
    vals = _series(21, 3.0, 1.0)
    # Son gunluk deger 5.86 K, yani UYARI'yi (5 K) gecmis: hedef KRITIK (12 K).
    assert 5.0 < vals[-1] < 12.0
    eta = hz.project(vals, _days(21), [14.0] * 21, LADDER)
    assert eta.reason == hz.REASON_BLIND
    assert eta.target == "KRITIK"
    assert eta.days is None
    # Ayni seri, gorunur bir tabanla: sayi cikar.
    ok = hz.project(vals, _days(21), [0.5] * 21, LADDER)
    assert ok.reason == ""


def test_gate_flat_slope():
    eta = hz.project(_series(21, 3.0, 0.0), _days(21), [0.5] * 21, LADDER)
    assert eta.reason == hz.REASON_FLAT
    assert eta.days is None


def test_gate_negative_slope():
    eta = hz.project(_series(21, 3.0, -1.0), _days(21), [0.5] * 21, LADDER)
    assert eta.reason == hz.REASON_FLAT


def test_horizon_is_capped_at_90_days():
    vals = _series(21, 3.0, 0.02)
    eta = hz.project(vals, _days(21), [0.5] * 21, LADDER)
    assert eta.reason == ""
    assert eta.capped is True
    assert eta.days > hz.MAX_HORIZON_DAYS
    assert eta.target == "UYARI"


def test_a_step_is_not_read_as_a_ramp():
    """EN ONEMLI GERILEME TESTI.

    10 gun once 3 K kademe atlayip sonra duzlesen bir seri, 21 gunluk pencerede
    sahte bir rampa uretir.  Projeksiyon degisim noktasindan SONRASINI kullanmak
    zorunda; kullanmazsa kademeyi rampa sayar ve uydurma bir tarih verir.
    """
    r = random.Random(7)
    vals = ([1.0 + r.gauss(0, 0.15) for _ in range(11)]
            + [4.0 + r.gauss(0, 0.15) for _ in range(10)])
    eta = hz.project(vals, _days(21), [0.5] * 21, LADDER)
    assert eta.from_changepoint is True
    assert eta.changepoint_ts is not None
    # Kademe sonrasi duz: egim ~0, yani sayi YOK.
    assert eta.reason == hz.REASON_FLAT
    # Kanit: ayni seride pencere butunu kullanilsa egim pozitif cikardi.
    lo, med, hi = cp.slope_ci_per_week(vals, _days(21), 21, 0.90)
    assert med > 0.5


def test_a_real_ramp_after_a_step_is_still_projected():
    """Degisim noktasi sonrasi gercekten tirmaniyorsa sayi CIKAR."""
    r = random.Random(11)
    vals = ([1.0 + r.gauss(0, 0.1) for _ in range(9)]
            + [3.0 + 1.2 * (i / 7.0) + r.gauss(0, 0.1) for i in range(12)])
    eta = hz.project(vals, _days(21), [0.5] * 21, LADDER)
    assert eta.reason == ""
    assert eta.target == "UYARI"
    assert eta.days is not None


def test_empty_series_is_insufficient_history_not_a_crash():
    eta = hz.project([], [], [], LADDER)
    assert eta.reason == hz.REASON_HISTORY
    assert eta.valid_days == 0
