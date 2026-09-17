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
