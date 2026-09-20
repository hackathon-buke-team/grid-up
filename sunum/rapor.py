"""Doğruluk raporu: plan → koşumlar → toplama → tek sayfalık rapor + iki grafik.

    python -m sunum.rapor               # tüm koşumlar (≈ 8-10 dk, tüm çekirdekler) → rapor
    python -m sunum.rapor --hizli       # küçük yineleme sayıları (deneme, ≈ 2 dk)
    python -m sunum.rapor --kayittan    # kayıtlı koşumlardan raporu yeniden üret (koşum yok)

Ne üretir (hepsi ``sunum/`` altında):

* ``dogruluk.json``            ham koşum kayıtları + toplanmış sayılar
* ``dogruluk.md``              tek sayfalık rapor (tablo + üç kısa bölüm)
* ``dogruluk-haber-verme.png`` grafik 1: haber verme süresi dağılımı
* ``dogruluk-duyarlilik.png``  grafik 2: duyarlılık eğrisi

Rapordaki HER sayı ``aggregate()`` çıktısından ``render_markdown()`` ile basılır; elle
yazılmış bir sayı yoktur.  ``tests/test_dogruluk.py`` kayıtlardan raporu yeniden üretip
birebir karşılaştırır ve iki kaydı yeniden koşturup aynı sonucu aldığını doğrular.
"""

from __future__ import annotations

import json
import math
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from sunum import dogruluk as dg

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "sunum"
JSON_PATH = OUT / "dogruluk.json"
MD_PATH = OUT / "dogruluk.md"
PNG_TIME = OUT / "dogruluk-haber-verme.png"
PNG_SENS = OUT / "dogruluk-duyarlilik.png"

RANK = dg._SEV_RANK
FLAGSHIP = "gevsek_baglanti"
FLAGSHIP_RATE = 4.0                      # K/hafta: demonun gönderdiği şiddet
SCENARIO_DEFAULT_RATE = 0.2              # K/hafta: faults.SCENARIOS["gevsek_baglanti"] varsayılanı
FIXED_THRESHOLD_C = 90.0                 # mutlak sıcaklık UYARI sınırı (docs/04)
#: docs/04 §5.4 tablosu: 100 pano × 40 izlenen bağlantı için filoda günde 0,209 yanlış CUSUM GEÇİŞİ
#: ("~4,8 günde bir").  docs/08 §10 jüri cevabı bunu "bir üst sınır" diye sunar.
DOCS04_FALSE_CROSSINGS_PER_DAY_100_PANELS = 0.209

# --------------------------------------------------------------------------
# Plan: her senaryo, arızanın koşum boyunca AKTİF olduğu bir zamanlamayla
# --------------------------------------------------------------------------
#: ago = arıza koşumun bitiminden kaç gün önce başladı; days = koşum süresi;
#: dense = son kaç gün YOĞUN örneklenir (gap_s saniyede bir kare, eval_s'de bir tespit turu).
#: Zamanlamalar senaryonun KENDİ tanımına uyar: yoğuşma yalnız 05:12-07:42'de ve 3 gün süreli,
#: yani "10 gün önce" başlatmak onu ölçümden ÖNCE bitirirdi; trafo devreye alma bir atımdır
#: (0,55 s sönüm), 2 s'lik karelerle yakalanır; ark açması kilitlidir.
_D = {"days": 14, "dense": 1.0, "gap_s": 120, "eval_s": 3600}
PLAN: dict[str, dict[str, Any]] = {
    "gevsek_baglanti": {"ago": 41.0, "kw": {"joint_key": dg.DEMO_JOINT, "rate_k_per_week": FLAGSHIP_RATE,
                                            "cap_uohm": 900.0}, "days": 60, "dense": 0.0, "gap_s": 120, "eval_s": 3600},
    "hizli_gevseme": {"ago": 30.0, "kw": {}, "days": 45, "dense": 0.0, "gap_s": 120, "eval_s": 3600},
    "notr_gevsek": {"ago": 30.0, "kw": {}, "days": 45, "dense": 0.0, "gap_s": 120, "eval_s": 3600},
    "harmonik_yuk": {"ago": 14.0, "kw": {}, "days": 24, "dense": 2.0, "gap_s": 120, "eval_s": 3600},
    "asiri_yuk": {"ago": 10.0, "kw": {}, "days": 20, "dense": 2.0, "gap_s": 120, "eval_s": 3600},
    "havalandirma_tikali": {"ago": 10.0, "kw": {}, "days": 20, "dense": 2.0, "gap_s": 120, "eval_s": 3600},
    "yogusma": {"ago": 2.5, "kw": {}, "days": 20, "dense": 2.5, "gap_s": 120, "eval_s": 3600},
    "pd_yuzen": {"ago": 20.0, "kw": {}, "days": 30, "dense": 1.0, "gap_s": 120, "eval_s": 3600},
    "ark_olayi": {"ago": 0.2, "kw": {}, "days": 12, "dense": 0.25, "gap_s": 10, "eval_s": 300},
    "dedektor_arizasi": {"ago": 5.0, "kw": {}, **_D},
    "sensor_takildi": {"ago": 1.0, "kw": {}, **_D},
    "sensor_kaydi": {"ago": 3.0, "kw": {}, **_D},
    "dugum_sessiz": {"ago": 0.4, "kw": {}, **_D},
    "sicak_hava_dalgasi": {"ago": 3.0, "kw": {}, **_D},
    "sebeke_olayi": {"ago": 0.3, "kw": {}, **_D},
    "trafo_devreye_alma": {"ago": 0.03, "kw": {}, "days": 14, "dense": 0.0208, "gap_s": 2, "eval_s": 60},
    "pano_enerjisiz": {"ago": 0.05, "kw": {}, **_D},
}
HEALTHY = {"days": 60, "dense": 2.0, "gap_s": 120, "eval_s": 3600}
#: Negatif kontrol koşumlarının DEĞERLENDİRME günü (ısınma hariç).  Sağlıklı koşumlar 53 gündür.
NEG_EVAL_DAYS = _D["days"] - dg.WARMUP_DAYS
#: Tasarım gereği yalnız İZLE'ye çıkması BEKLENEN senaryolar: bunlar "kaçtı" sayılmaz.
IZLE_BY_DESIGN = {"pd_yuzen": "400 V'ta klasik PD oluşmaz ve PD kanalı AG'de tek başına ekip yönlendirmez; İZLE beklenen sonuçtur (README §7, docs/04 §9.3)"}
SENS_RATES = (0.05, 0.1, 0.2, 0.35, 0.5, 1.0, 2.0)          # + FLAGSHIP_RATE (dağılım grubu)


def fitted_seeds(n: int) -> list[int]:
    """Demo panelinin TAM DONANIMLI (analizör + ark rölesi) olduğu ilk ``n`` tohum.

    Donanım tohuma göre rastgeledir (ölçüldü: 30 tohumun 16'sında tam).  Ark, PD ve
    analizör senaryoları donanımsız panoda ALGILANAMAZ; bu bir ürün bulgusu değil, dağıtım
    koşuludur (docs/05).  Bu rapor tam donanımlı panoyu ölçer.
    """
    from panogoz.api import runtime as rtmod

    out: list[int] = []
    seed = dg.SEED_BASE
    while len(out) < n:
        p = rtmod.build_fleet(3, seed).get(rtmod.DEMO_PANEL)
        if p.has_analyser and p.has_arc_relay:
            out.append(seed)
        seed += 1
    return out


def _case(group: str, scenario: str | None, p: dict, seed: int, rep: int, kw: dict | None = None) -> dict:
    return {"group": group, "scenario": scenario, "ago_days": p.get("ago", 0.0),
            "kw": dict(p.get("kw", {}) if kw is None else kw), "seed": seed, "rep": rep,
            "backfill_days": p["days"], "eval_days": p["days"], "evals_per_day": 1,
            "dense_days": p["dense"], "dense_gap_s": p["gap_s"], "dense_eval_s": p["eval_s"]}


def build_cases(rm: int = 6, rh: int = 20, rs: int = 8, rd: int = 30) -> list[dict]:
    seeds = fitted_seeds(max(rm, rh, rs, rd))
    cases: list[dict] = []
    for name, p in PLAN.items():
        if name == FLAGSHIP:
            continue                                      # amiral gemisi "dist" grubunda (rd yineleme)
        for r in range(rm):
            cases.append(_case("matrix", name, p, seeds[r], r))
    for r in range(rh):
        cases.append(_case("healthy", None, HEALTHY, seeds[r], r))
    flag = PLAN[FLAGSHIP]
    for rate in SENS_RATES:
        for r in range(rs):
            cases.append(_case("sens", FLAGSHIP, flag, seeds[r], r,
                               kw={**flag["kw"], "rate_k_per_week": rate}))
    for r in range(rd):
        cases.append(_case("dist", FLAGSHIP, flag, seeds[r], r))
    return cases


def run_all(cases: list[dict], workers: int | None = None) -> list[dict]:
    import os
    workers = workers or max(2, (os.cpu_count() or 4) - 2)
    t0 = time.time()
    done = 0
    recs: list[dict | None] = [None] * len(cases)

    def one(i: int) -> None:
        nonlocal done
        recs[i] = dg.run_case_subprocess(cases[i])
        done += 1
        if done % 10 == 0 or done == len(cases):
            print(f"  {done}/{len(cases)} koşum · {time.time() - t0:.0f} s", flush=True)

    with ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(one, range(len(cases))))
    return [r for r in recs if r is not None]


# --------------------------------------------------------------------------
# İstatistik
# --------------------------------------------------------------------------

def cp_interval(k: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    """Clopper-Pearson (kesin) iki yanlı %95 aralığı."""
    from scipy.stats import beta
    lo = 0.0 if k == 0 else float(beta.ppf(alpha / 2, k, n - k + 1))
    hi = 1.0 if k == n else float(beta.ppf(1 - alpha / 2, k + 1, n - k))
    return lo, hi


def poisson_upper(k: int, exposure: float, alpha: float = 0.05) -> float:
    """Gözlenen ``k`` olay için oranın (olay / birim maruziyet) kesin %95 üst sınırı."""
    from scipy.stats import chi2
    return float(chi2.ppf(1 - alpha / 2, 2 * (k + 1)) / 2.0 / exposure)


def poisson_lower(k: int, exposure: float, alpha: float = 0.05) -> float:
    """Gözlenen ``k`` olay için oranın kesin %95 ALT sınırı (k = 0 için 0)."""
    from scipy.stats import chi2
    return 0.0 if k <= 0 else float(chi2.ppf(alpha / 2, 2 * k) / 2.0 / exposure)


def _median(xs: list[float]) -> float | None:
    return round(float(statistics.median(xs)), 2) if xs else None


def _q(xs: list[float], q: float) -> float | None:
    if not xs:
        return None
    s = sorted(xs)
    i = q * (len(s) - 1)
    lo, hi = int(math.floor(i)), int(math.ceil(i))
    return round(s[lo] + (s[hi] - s[lo]) * (i - lo), 2)


def _first_days(recs: list[dict], level: int) -> list[float]:
    """``level`` ve üstü olayların koşum başından İLK görüldüğü günler."""
    return [r["incident_first_day"][k] for r in recs for k, v in r["incidents_other"].items()
            if RANK.get(v, 0) >= level and k in r.get("incident_first_day", {})]


def _max_rank(d: dict[str, str]) -> int:
    return max((RANK.get(v, 0) for v in d.values()), default=-1)


# --------------------------------------------------------------------------
# Toplama: kayıtlar → sayılar (saf fonksiyon; test bunu doğrudan çağırır)
# --------------------------------------------------------------------------

def aggregate(records: list[dict]) -> dict:
    from panogoz.sim import faults as fx

    by: dict[str, list[dict]] = {}
    for r in records:
        by.setdefault(r["case"]["group"], []).append(r)

    UY = RANK["UYARI"]
    matrix: list[dict] = []
    for name, sp in fx.SCENARIOS.items():
        recs = by.get("dist", []) if name == FLAGSHIP else [
            r for r in by.get("matrix", []) if r["case"]["scenario"] == name]
        n = len(recs)
        row: dict[str, Any] = {"scenario": name, "label_tr": sp["label_tr"], "n": n,
                               "expect_alarm": bool(sp["expect_alarm"]),
                               "expect_mode": sp.get("expect_mode"),
                               "expect_flags": list(sp.get("expect_flags", ()))}
        stray = [r for r in recs if _max_rank(r["incidents_pre_onset"]) >= UY
                 or _max_rank(r["incidents_other"]) >= UY]
        stray_izle = [r for r in recs if r not in stray and (r["incidents_pre_onset"] or r["incidents_other"])]
        mode = sp.get("expect_mode")
        if sp["expect_alarm"]:
            team = [r for r in recs if RANK.get(r["target_max_severity"] or "", -1) >= UY]
            izle = [r for r in recs if r["target_max_severity"] == "IZLE"]
            row.update(team=len(team), izle_only=len(izle), missed=n - len(team) - len(izle),
                       delay_median=_median([r["first_uyari_days"] for r in team
                                             if r["first_uyari_days"] is not None]),
                       risk_peak_median=_median([r["risk_peak"].get(mode, 0.0) for r in recs]),
                       stray_uyari_runs=len(stray))
        else:
            row.update(false_alarm=len(stray), izle_only=len(stray_izle),
                       quiet=n - len(stray) - len(stray_izle))
        # HEDEF pabucun kendi ufku meşrudur (kusurlu pabuç eşiğe gerçekten yaklaşıyor); yalnız
        # hedef DIŞI bir pabuç için üretilen takvime yazılabilir gün "yanlış ufuk"tur.
        row["false_horizon_runs"] = sum(1 for r in recs if any(e[0] != r.get("target_joint") for e in r["eta_soon"]))
        row["flag_ok"] = (sum(1 for r in recs if all(f in r["flags"] for f in row["expect_flags"]))
                          if row["expect_flags"] else None)
        row["suppress_codes"] = sorted({c for r in recs for c in r["suppress_codes"]})
        matrix.append(row)

    # ---- yanlış alarm bütçesi: sağlıklı pano, arızasız koşumlar
    hs = by.get("healthy", [])
    eval_days = HEALTHY["days"] - dg.WARMUP_DAYS
    n_h = len(hs)
    exposure_days = n_h * eval_days

    def incs(r: dict) -> dict[str, str]:
        return r["incidents_other"]

    n_uy = sum(1 for r in hs for v in incs(r).values() if RANK.get(v, 0) >= UY)
    n_kr = sum(1 for r in hs for v in incs(r).values() if RANK.get(v, 0) >= RANK["KRITIK"])
    n_iz = sum(len(incs(r)) for r in hs)
    runs_uy = sum(1 for r in hs if _max_rank(incs(r)) >= UY)
    up_uy = poisson_upper(n_uy, exposure_days / 365.0) if hs else None
    up_kr = poisson_upper(n_kr, exposure_days / 365.0) if hs else None
    lo_r, hi_r = cp_interval(runs_uy, n_h) if hs else (None, None)
    healthy = {
        "runs": n_h, "eval_days_per_run": eval_days, "panel_days": round(exposure_days, 1),
        "incidents_izle_plus": n_iz, "incidents_uyari_plus": n_uy, "incidents_kritik_plus": n_kr,
        "runs_with_uyari": runs_uy,
        "runs_with_uyari_ci": [None if lo_r is None else round(lo_r, 3), None if hi_r is None else round(hi_r, 3)],
        "uyari_per_panel_year": None if not hs else round(n_uy / (exposure_days / 365.0), 2),
        "uyari_per_panel_year_upper": None if up_uy is None else round(up_uy, 2),
        "kritik_per_panel_year": None if not hs else round(n_kr / (exposure_days / 365.0), 2),
        "kritik_per_panel_year_upper": None if up_kr is None else round(up_kr, 2),
        "false_horizon_runs": sum(1 for r in hs if r["eta_soon"]),
        "uyari_per_panel_year_lower": None if not hs else round(poisson_lower(n_uy, exposure_days / 365.0), 2),
        "docs04_per_panel_year": round(DOCS04_FALSE_CROSSINGS_PER_DAY_100_PANELS / 100.0 * 365.0, 2),
        "uyari_distinct_joints": len({k for r in hs for k, v in incs(r).items() if RANK.get(v, 0) >= UY}),
        "runs_without_uyari": sum(1 for r in hs if _max_rank(incs(r)) < UY),
        "uyari_max_per_run": max([sum(1 for v in incs(r).values() if RANK.get(v, 0) >= UY) for r in hs], default=0),
        "uyari_first_day_median": _median(_first_days(hs, UY)),
        "uyari_first_day_min": min(_first_days(hs, UY), default=None),
    }

    # ---- duyarlılık eğrisi: gevşek bağlantı şiddeti → ekip alarmı olasılığı
    sens_rows: list[dict] = []
    groups: dict[float, list[dict]] = {}
    for r in by.get("sens", []):
        groups.setdefault(float(r["case"]["kw"]["rate_k_per_week"]), []).append(r)
    groups[FLAGSHIP_RATE] = by.get("dist", [])
    for rate in sorted(groups):
        recs = groups[rate]
        if not recs:
            continue
        hit = [r for r in recs if RANK.get(r["target_max_severity"] or "", -1) >= UY]
        lo, hi = cp_interval(len(hit), len(recs))
        sens_rows.append({"rate": rate, "n": len(recs), "detected": len(hit),
                          "p": round(len(hit) / len(recs), 3), "ci": [round(lo, 3), round(hi, 3)],
                          "delay_median": _median([r["first_uyari_days"] for r in hit
                                                   if r["first_uyari_days"] is not None])})

    # ---- haber verme süresi dağılımı: amiral gemisi, demo şiddeti
    ds = by.get("dist", [])
    ago = PLAN[FLAGSHIP]["ago"]
    delays = [r["first_uyari_days"] for r in ds if r["first_uyari_days"] is not None]
    cusum = [round(ago - r["cusum_first_days_ago"], 2) for r in ds if r["cusum_first_days_ago"] is not None]
    temps = [r["lug_temp_c"] for r in ds if r["lug_temp_c"] is not None]
    dist = {
        "runs": len(ds), "detected": len(delays), "missed": len(ds) - len(delays),
        "delays": sorted(delays), "delay_median": _median(delays),
        "delay_p10": _q(delays, 0.10), "delay_p90": _q(delays, 0.90),
        "cusum_delays": sorted(cusum), "cusum_median": _median(cusum),
        "lug_temp_median_c": _median(temps), "lug_temp_max_c": round(max(temps), 1) if temps else None,
        "fixed_threshold_c": FIXED_THRESHOLD_C,
        "fixed_threshold_hits": sum(1 for t in temps if t >= FIXED_THRESHOLD_C),
        "lug_temp_n": len(temps),
    }
    return {"matrix": matrix, "healthy": healthy, "sens": sens_rows, "dist": dist}


# --------------------------------------------------------------------------
# Rapor (Markdown)
# --------------------------------------------------------------------------

def fx_days(name: str) -> str:
    from panogoz.sim import faults as fx
    return _f(float(fx.SCENARIOS[name]["default_kw"]["days"]), 0)


def _f(x: float | None, d: int = 1) -> str:
    if x is None:
        return "—"
    return f"{x:.{d}f}".replace(".", ",")


def _pct(p: float | None) -> str:
    return "—" if p is None else f"%{round(p * 100)}"


def render_markdown(agg: dict) -> str:
    m = {r["scenario"]: r for r in agg["matrix"]}
    h, d, sens = agg["healthy"], agg["dist"], agg["sens"]
    pos = [r for r in agg["matrix"] if r["expect_alarm"]]
    neg = [r for r in agg["matrix"] if not r["expect_alarm"]]
    pos_team = [r for r in pos if r["n"] and r["team"] == r["n"]]
    pos_none = [r for r in pos if r["n"] and r["team"] == 0]
    neg_clean = sum(r["false_alarm"] for r in neg)
    neg_runs = sum(r["n"] for r in neg)
    default = next((s for s in sens if abs(s["rate"] - SCENARIO_DEFAULT_RATE) < 1e-9), None)
    demo = next((s for s in sens if abs(s["rate"] - FLAGSHIP_RATE) < 1e-9), None)

    L: list[str] = []
    L += ["# Doğruluk raporu — PANO GÖZ (görev 4.4)", "",
          "> **Bu sayıların hiçbiri saha verisiyle doğrulanmış değildir.** Hepsi fizikten türetilmiş "
          "bir simülatör üzerindedir; simülatörün varsayımlarını değil, dedektörün BU varsayımlar "
          "altındaki davranışını ölçer. Gerçek yanlış alarm oranı ancak etiketli saha geçmişi olan bir "
          "pilotta ölçülebilir (README §6).", ""]

    L += ["## Özet", ""]
    L += [f"* **Kayma tipi arızalar yakalanıyor.** Amiral gemisi (gevşek bağlantı, {_f(FLAGSHIP_RATE)} K/hafta): "
          f"{d['detected']}/{d['runs']} koşumda ekip alarmı (≥ UYARI) açıldı; arıza başladıktan medyan "
          f"**{_f(d['delay_median'])} gün** sonra (%10–%90: {_f(d['delay_p10'])}–{_f(d['delay_p90'])} gün). "
          f"Kusurlu pabucun son sıcaklığı medyan {_f(d['lug_temp_median_c'])} °C, en yüksek {_f(d['lug_temp_max_c'])} °C: "
          f"**{FIXED_THRESHOLD_C:.0f} °C'lik sabit eşik {d['fixed_threshold_hits']}/{d['lug_temp_n']} koşumda "
          f"hiç alarm vermezdi.**"]
    pos_some = [x for x in pos if x["n"] and 0 < x["team"] < x["n"]]
    by_design = [x for x in pos_none if x["scenario"] in IZLE_BY_DESIGN]
    pos_none = [x for x in pos_none if x["scenario"] not in IZLE_BY_DESIGN]
    names = lambda rows: ", ".join(x["scenario"] for x in rows) or "—"
    L += [f"* **Panel düzeyi modlar ve ark dedektörü arızası zayıf.** {len(pos)} alarm-beklenen senaryodan "
          f"{len(pos_team)}'inde TÜM koşumlarda ekip alarmı açıldı ({names(pos_team)}); {len(pos_some)}'inde bazı "
          f"koşumlarda ({names(pos_some)}); {len(pos_none)}'inde hiçbirinde ({names(pos_none)}); {len(by_design)}'i tasarım gereği yalnız İZLE'ye çıkar "
          f"({names(by_design)}). Tabloda tepe risk yazılı: "
          f"bunlar \"algılanmıyor\" değil, **varsayılan senaryo şiddetinde birleşik risk alarm eşiğine "
          f"(≥ 0,40 İZLE, ≥ 0,65 UYARI) ulaşmıyor** demektir; nedeni (şiddet, füzyon ağırlığı, eşik) bu ölçümle ayrılamaz."]
    L += [f"* **Duyarlılık: varsayılan şiddet alarm üretmiyor.** Gevşek bağlantı senaryosunun kendi varsayılanı "
          f"({_f(SCENARIO_DEFAULT_RATE)} K/hafta) 41 günde ekip alarmı verme olasılığı "
          f"{_pct(default['p']) if default else '—'} ({default['detected'] if default else '—'}/"
          f"{default['n'] if default else '—'}); demonun {_f(FLAGSHIP_RATE)} K/haftası "
          f"{_pct(demo['p']) if demo else '—'}. `faults.py` bu senaryoyu `expect_alarm: True` ilan ediyor."]
    L += [f"* **Yanlış alarm bütçesi.** Arızasız pano, {h['runs']} koşum × {_f(h['eval_days_per_run'], 0)} gün "
          f"= {_f(h['panel_days'], 0)} pano-günü: ekip alarmı (≥ UYARI) **{h['incidents_uyari_plus']} olay** "
          f"({h['runs_with_uyari']}/{h['runs']} koşumda); yıllık oran {_f(h['uyari_per_panel_year'], 2)} "
          f"olay/pano-yıl, %95 üst sınır {_f(h['uyari_per_panel_year_upper'], 2)}. Telefona çıkan (≥ KRİTİK): "
          f"{h['incidents_kritik_plus']} olay, üst sınır {_f(h['kritik_per_panel_year_upper'], 2)} olay/pano-yıl. "
          f"**docs/04 §5.4'ün analitik yanlış CUSUM geçişi {_f(h['docs04_per_panel_year'], 2)} olay/pano-yıl'dır; ölçülen "
          f"≥ UYARI oranının %95 ALT sınırı {_f(h['uyari_per_panel_year_lower'], 2)}: analitik rakam uçtan uca ölçümle "
          f"desteklenmiyor** (bkz. §3)."]
    L += [f"* **Negatif kontroller:** {len(neg)} senaryo × ~{neg[0]['n'] if neg else 0} koşum = {neg_runs} koşumda "
          f"ekip alarmı (≥ UYARI) **{neg_clean}** kez açıldı. Bu koşumlar yalnız {NEG_EVAL_DAYS:.0f} değerlendirme günü içerir; "
          f"yanlış alarmlar zamanla biriktiği için 53 günlük sağlıklı koşumlarla (aşağıdaki bütçe) doğrudan kıyaslanmamalıdır."]
    L += [""]

    L += ["## 1. Tespit matrisi — 17 senaryo", ""]
    L += ["Sütunlar: **Ekip** = beklenen olay ≥ UYARI seviyesine çıktı · **İZLE** = yalnız izleme listesine düştü · "
          "**Kaçtı** = hiç olay yok · **Gecikme** = arıza başlangıcından ekip alarmına medyan gün · **Risk** = tepe birleşik "
          "risk medyanı (≥ 0,40 İZLE, ≥ 0,65 UYARI; ark için mutlak kural, risk yok) · **Bayrak** = `expect_flags` koşum sonunda kurulu · "
          "**Y.ufuk** = HEDEF DIŞI bir pabuç için takvime yazılabilir (< 90 g) \"eşiğe kalan gün\" üretilen koşum.", ""]
    L += ["| Senaryo | Beklenen | n | Ekip | İZLE | Kaçtı | Gecikme (g) | Risk | Bayrak | Y.ufuk |",
          "|---|---|--:|--:|--:|--:|--:|--:|--:|--:|"]
    for r in pos:
        flag = "—" if r["flag_ok"] is None else f"{r['flag_ok']}/{r['n']}"
        L.append(f"| {r['label_tr']} | alarm · {r['expect_mode']} | {r['n']} | {r['team']} | {r['izle_only']} | "
                 f"{r['missed']} | {'≤ ' + str(round(PLAN[r['scenario']]['eval_s'] / 60)) + ' dk' if r['expect_mode'] == 'arc_integrity' and r['delay_median'] is not None else _f(r['delay_median'])} | {'mutlak kural' if r['expect_mode'] == 'arc_integrity' else _f(r['risk_peak_median'], 2)} | {flag} | "
                 f"{r['false_horizon_runs']}/{r['n']} |")
    L += [""]
    for name, why in IZLE_BY_DESIGN.items():
        if name in m and m[name]["n"]:
            L += [f"* **{m[name]['label_tr']}:** {m[name]['izle_only']}/{m[name]['n']} İZLE. {why}."]
    if "ark_olayi" in m and m["ark_olayi"]["n"]:
        L += [f"* **Ark olayı:** {m['ark_olayi']['team']}/{m['ark_olayi']['n']} ekip alarmı; gecikme değerlendirme aralığıdır "
              f"({round(PLAN['ark_olayi']['eval_s'] / 60)} dk). Bildirim gecikmesi bu raporda ölçülmez (docs/08 §5)."]
    if "dedektor_arizasi" in m and m["dedektor_arizasi"]["n"]:
        L += [f"* **Ark dedektörü arızası:** {m['dedektor_arizasi']['team']}/{m['dedektor_arizasi']['n']}. docs: reg 222/223 yalnız "
              f"FW ≥ 03.00.00'da bulunur; simülatörün bu yazmaçları dedektörün beklediği biçimde sunup sunmadığı bu ölçümle "
              f"ayrılamaz (doğrulanmadı)."]
    if "yogusma" in m:
        L += [f"* **Yoğuşma:** senaryo yalnız 05:12–07:42'de ve {fx_days('yogusma')} gün süreli; koşum bu pencerenin içinde ölçer "
              f"(arıza {_f(PLAN['yogusma']['ago'])} gün önce başladı)."]
    gaps = [x for x in agg["matrix"] if x["flag_ok"] == 0 and x["n"]]
    if gaps:
        L += [f"* **Bayrak sözleşmesi (görev 4.3):** {len(gaps)} senaryonun ilan ettiği bayrak HİÇBİR koşumda kurulmadı: "
              + "; ".join(f"{x['scenario']} ({', '.join(x['expect_flags'])})" for x in gaps) + "."]
    L += ["", "Negatif kontroller (sessiz kalmalı): **Yanlış** = ekip alarmı açıldı · **İZLE** = yalnız izleme kaydı (arka plan gürültüsü dahil) · "
              "**Sessiz** = olay yok.", "",
          "| Senaryo | n | Yanlış | İZLE | Sessiz | Bayrak | Y.ufuk | Bastırma gerekçesi |",
          "|---|--:|--:|--:|--:|--:|--:|---|"]
    for r in neg:
        flag = "—" if r["flag_ok"] is None else f"{r['flag_ok']}/{r['n']}"
        codes = ", ".join(r["suppress_codes"]) or "—"
        L.append(f"| {r['label_tr']} | {r['n']} | {r['false_alarm']} | {r['izle_only']} | {r['quiet']} | {flag} | "
                 f"{r['false_horizon_runs']}/{r['n']} | {codes} |")
    L += [""]

    L += ["## 2. Haber verme süresi (grafik 1)", "",
          f"![haber verme süresi](dogruluk-haber-verme.png)", "",
          f"Amiral gemisi, {d['runs']} yineleme. Kanıtın yeterli olduğu an (CUSUM ilk aşımı) arızadan medyan "
          f"{_f(d['cusum_median'])} gün sonra; ekip alarmı (3/5 gün kuralı + iki bağımsız ölçüm ilkesi) medyan "
          f"{_f(d['delay_median'])} gün sonra. Fark bilinçlidir: alarm kapıları gürültüden korur ve gecikme bedelidir. "
          f"{d['missed']} koşumda ekip alarmı hiç açılmadı.", ""]

    L += ["## 3. Yanlış alarm bütçesi", "",
          f"Arızasız pano ({h['runs']} koşum, {_f(h['panel_days'], 0)} pano-günü, ilk {dg.WARMUP_DAYS:.0f} gün ısınma hariç): "
          f"İZLE ve üstü {h['incidents_izle_plus']} olay, UYARI ve üstü {h['incidents_uyari_plus']}, KRİTİK ve üstü "
          f"{h['incidents_kritik_plus']}. UYARI'lı koşum oranı {h['runs_with_uyari']}/{h['runs']} "
          f"(%95 aralık {_pct(h['runs_with_uyari_ci'][0])}–{_pct(h['runs_with_uyari_ci'][1])}). "
          f"\"Yanlış ufuk\" (sağlıklı pabuç için < 90 günlük \"eşiğe kalan gün\"): {h['false_horizon_runs']}/{h['runs']} koşum. "
          f"Bu, `tests/test_negative_pipeline.py`'nin saate göre değişen kırmızı testinin ölçülmüş hâlidir. "
          f"Yanlış UYARI'ların koşum başından ilk görüldüğü gün: medyan {_f(h['uyari_first_day_median'])}, "
          f"en erken {_f(h['uyari_first_day_min'])} (ısınma {dg.WARMUP_DAYS:.0f} gün; bu değerler ısınma sınırına "
          f"yakınsa yanlış alarmların bir kısmı öğrenme haftası artefaktıdır).", "",
          f"**Dağılım eşit değil:** {h['runs_without_uyari']}/{h['runs']} koşum hiç yanlış UYARI üretmedi, en kötü koşum "
          f"{h['uyari_max_per_run']} üretti; olaylar birkaç pabuçta yığılmıyor ({h['uyari_distinct_joints']} farklı pabuç/mod). Poisson varsayımı gevşektir; "
          f"aralıklar bu yüzden olduğundan dar olabilir.", "",
          f"**Belgeyle çelişki.** docs/04 §5.4, 100 pano × 40 bağlantı için filoda günde {_f(DOCS04_FALSE_CROSSINGS_PER_DAY_100_PANELS, 3)} "
          f"yanlış CUSUM GEÇİŞİ hesaplar (= {_f(h['docs04_per_panel_year'], 2)} olay/pano-yıl) ve docs/08 §10 jüri cevabı bunu "
          f"\"üst sınır\" diye sunar. Uçtan uca ölçülen ≥ UYARI olay oranı {_f(h['uyari_per_panel_year'], 2)} olay/pano-yıl "
          f"(%95 aralık {_f(h['uyari_per_panel_year_lower'], 2)}–{_f(h['uyari_per_panel_year_upper'], 2)}) ve geçişten daha ağır bir "
          f"olaydır. Analitik hesap gürültünün bağımsız ve Gauss olduğunu varsayar; simülatörün sağlıklı pabuç dağılımı ya da "
          f"dedektörün gürültü varsayımı bundan sapıyor olabilir (bu ölçümle ayrılamaz). **Jüri cevabı sunumdan önce güncellenmeli.**", ""]

    L += ["## 4. Duyarlılık eğrisi (grafik 2)", "", "![duyarlılık eğrisi](dogruluk-duyarlilik.png)", "",
          "| Gevşeme hızı (K/hafta) | n | Ekip alarmı | Olasılık | %95 aralık | Gecikme medyanı (g) |", "|--:|--:|--:|--:|--:|--:|"]
    for s in sens:
        L.append(f"| {_f(s['rate'], 2)} | {s['n']} | {s['detected']} | {_pct(s['p'])} | "
                 f"{_pct(s['ci'][0])}–{_pct(s['ci'][1])} | {_f(s['delay_median'])} |")
    L += [""]

    L += ["## Yöntem ve sınırlar", "",
          "* Her koşum ayrı süreçte, **gerçek boru hattından** geçer (simülatör → ağ geçidi → dedektör → bastırma → füzyon → "
          "alarm yöneticisi) ve **gün gün** işletilir; alarmın ilk açıldığı an gerçek alarm yöneticisinden okunur. "
          f"İlk {dg.WARMUP_DAYS:.0f} gün ısınmadır (üretimde `LEARN_MODE`).",
          "* Duvar saati **sabitlenir**: aynı tohum ve saat bit bit aynı sonucu verir; saat kaydırılınca θ tepesi ve "
          "\"eşiğe kalan gün\" değişir (simülatör mutlak zamana bağlı). Yineleme = (tohum, saat kayması).",
          "* Pano **tam donanımlı** (analizör + ark rölesi) seçilir. Demo filosunda 14 panonun yalnız 7'sinde ark rölesi var; "
          "rölesiz panoda ark alarmı VERİLEMEZ — bu bir dağıtım koşuludur, dedektör kusuru değil.",
          "* Tespit = beklenen olay, **hedef eklemde** (eklem modları) ya da aynı modda (panel modları), ≥ UYARI. Başka eklemdeki "
          "olay hedefi yakalamış sayılmaz.",
          "* Aralıklar Clopper–Pearson (oranlar) ve kesin Poisson (olay oranları), iki yanlı %95. Küçük n'de aralıklar geniştir "
          "ve öyle okunmalıdır.",
          "* Kaçırılan panel modları için **neden** tanı konmadı: risk yükseliyor ama eşiğe ulaşmıyor; senaryo şiddeti mi, "
          "füzyon ağırlığı mı, eşik mi bu ölçümle ayrılamaz.", "",
          "## Yeniden üretme", "",
          "```",
          "python -m sunum.rapor               # koşumları çalıştır, raporu ve grafikleri üret",
          "python -m sunum.rapor --kayittan    # kayıtlardan raporu yeniden üret",
          "python -m pytest tests/test_dogruluk.py -q   # her sayı kayıttan üretilebiliyor mu, koşum tekrarlanabilir mi",
          "```", ""]
    return "\n".join(L)


# --------------------------------------------------------------------------
# Grafikler
# --------------------------------------------------------------------------

#: Aydınlık yüzey için jetonlar (saha uygulamasının ``--fg``/``--fg-mute``/``--accent`` değerleri).
INK, INK_MUTE, GRID, ACCENT, SURFACE = "#12181a", "#64747a", "#dde3e6", "#0f6ba0", "#ffffff"
WARN = "#8a5600"


def _style(ax) -> None:
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=INK_MUTE, labelsize=9, length=3)
    ax.yaxis.grid(True, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)


def chart_time(agg: dict, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    d = agg["dist"]
    fig, ax = plt.subplots(figsize=(8.4, 4.4), dpi=200, facecolor=SURFACE)
    _style(ax)
    bins = list(range(0, int(max(d["delays"] + d["cusum_delays"] + [40])) + 4, 3))
    ax.hist(d["delays"], bins=bins, color=ACCENT, edgecolor=SURFACE, linewidth=2, alpha=0.95,
            label="Ekip alarmı (≥ UYARI)")
    ax.hist(d["cusum_delays"], bins=bins, histtype="step", color=INK_MUTE, linewidth=1.4,
            label="Kanıt yeterli (CUSUM ilk aşım)")
    from matplotlib.ticker import MaxNLocator
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    ymax = ax.get_ylim()[1]
    ax.set_ylim(0, ymax * 1.32)
    # İki medyan etiketi çizgilerin KARŞI taraflarına konur; aynı yana konunca birbirinin çizgisine biner.
    labels = ((d["cusum_median"], f"CUSUM medyan {_f(d['cusum_median'])} g", INK_MUTE, "right", -0.4),
              (d["delay_median"], f"Ekip alarmı medyan {_f(d['delay_median'])} g", INK, "left", 0.4))
    for x, txt, col, ha, dx in labels:
        if x is not None:
            ax.axvline(x, color=col, linewidth=1.2, linestyle=(0, (4, 3)))
            ax.text(x + dx, ymax * 1.30, txt, color=col, fontsize=9, va="top", ha=ha)
    ax.set_xlabel("Arıza başladıktan sonra geçen gün", color=INK, fontsize=10)
    ax.set_ylabel("Koşum sayısı", color=INK, fontsize=10)
    ax.legend(loc="upper right", frameon=False, fontsize=9, labelcolor=INK, bbox_to_anchor=(1.0, 0.72))
    fig.suptitle(f"Amiral gemisi kusuru medyan {_f(d['delay_median'])} günde ekip alarmına çıkıyor "
                 f"({d['detected']}/{d['runs']} koşum)", x=0.075, ha="left", fontsize=12.5, color=INK, fontweight="bold")
    ax.set_title(f"Sabit {d['fixed_threshold_c']:.0f} °C eşiği {d['fixed_threshold_hits']}/{d['lug_temp_n']} koşumda hiç "
                 f"alarm vermezdi: kusurlu pabuç son günde medyan {_f(d['lug_temp_median_c'])} °C "
                 f"(en yüksek {_f(d['lug_temp_max_c'])} °C)", loc="left", fontsize=9, color=INK_MUTE, pad=8)
    fig.text(0.075, 0.015, "Simülatör verisi; saha verisiyle doğrulanmamıştır. Gevşek bağlantı, "
             f"{_f(FLAGSHIP_RATE)} K/hafta, gün gün işletme, saat sabit.", fontsize=7.5, color=INK_MUTE)
    fig.subplots_adjust(top=0.84, bottom=0.16, left=0.075, right=0.97)
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)


def chart_sens(agg: dict, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rows = agg["sens"]
    x = [r["rate"] for r in rows]
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(8.4, 5.6), dpi=200, facecolor=SURFACE, sharex=True,
                                 gridspec_kw={"height_ratios": [1.5, 1]})
    for ax in (a1, a2):
        _style(ax)
    # Her hız BAĞIMSIZ bir koşul: aralık dikey çubuktur, iki hız arasını dolduran bir bant
    # (yorumlanmamış aradeğerleme) değildir.
    a1.vlines(x, [r["ci"][0] for r in rows], [r["ci"][1] for r in rows], color=ACCENT, linewidth=1.6, alpha=0.45)
    a1.plot(x, [r["p"] for r in rows], color=ACCENT, linewidth=1.6, marker="o", markersize=7,
            markeredgecolor=SURFACE, markeredgewidth=2)
    a1.set_ylim(-0.03, 1.08)
    a1.set_yticks([0, 0.5, 1.0])
    a1.set_yticklabels(["%0", "%50", "%100"])
    a1.set_ylabel("Ekip alarmı olasılığı", color=INK, fontsize=10)
    for r in rows:
        a1.annotate(f"{r['detected']}/{r['n']}", (r["rate"], r["p"]), textcoords="offset points", xytext=(11, 9),
                    ha="left", fontsize=8, color=INK_MUTE, bbox=dict(facecolor=SURFACE, edgecolor="none", pad=1.2))
    dl = [(r["rate"], r["delay_median"]) for r in rows if r["delay_median"] is not None]
    if dl:
        a2.plot([p[0] for p in dl], [p[1] for p in dl], color=INK, linewidth=1.8, marker="o", markersize=6,
                markeredgecolor=SURFACE, markeredgewidth=2)
        for rx, ry in dl:
            a2.annotate(_f(ry), (rx, ry), textcoords="offset points", xytext=(9, 7), ha="left", fontsize=8,
                        color=INK_MUTE, bbox=dict(facecolor=SURFACE, edgecolor="none", pad=1.2))
    a2.set_ylabel("Medyan gecikme (gün)", color=INK, fontsize=10)
    a2.text(0.995, 0.96, "yalnız ekip alarmı açılan koşumlar", transform=a2.transAxes, ha="right", va="top",
            fontsize=8, color=INK_MUTE)
    a2.set_ylim(bottom=0)
    a2.set_xscale("log")
    a2.set_xticks(x)
    a2.set_xticklabels([_f(v, 2) for v in x])
    a2.set_xlabel("Gevşeme hızı (K/hafta, log ölçek)", color=INK, fontsize=10)
    for v, txt in ((SCENARIO_DEFAULT_RATE, "senaryo\nvarsayılanı"), (FLAGSHIP_RATE, "demo\nşiddeti")):
        for ax in (a1, a2):
            ax.axvline(v, color=INK_MUTE, linewidth=1, linestyle=(0, (4, 3)))
        a1.text(v * 1.04, 0.16, txt, fontsize=8, color=INK_MUTE, va="bottom")
    default = next((r for r in rows if abs(r["rate"] - SCENARIO_DEFAULT_RATE) < 1e-9), None)
    ttl = "Senaryonun kendi varsayılan şiddeti ekip alarmı üretmiyor" if default and default["p"] < 0.5 \
        else "Duyarlılık eğrisi"
    fig.suptitle(ttl, x=0.08, ha="left", fontsize=12.5, color=INK, fontweight="bold")
    a1.set_title("41 günlük gevşeme; her nokta 8 yineleme (demo şiddeti 30), çubuk = Clopper–Pearson %95 aralığı",
                 loc="left", fontsize=9, color=INK_MUTE, pad=8)
    fig.text(0.08, 0.012, "Simülatör verisi; saha verisiyle doğrulanmamıştır.", fontsize=7.5, color=INK_MUTE)
    fig.subplots_adjust(top=0.86, bottom=0.12, left=0.08, right=0.97, hspace=0.12)
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)


# --------------------------------------------------------------------------
# Giriş noktası
# --------------------------------------------------------------------------

def write_outputs(records: list[dict], meta: dict) -> dict:
    agg = aggregate(records)
    JSON_PATH.write_text(json.dumps({"meta": meta, "aggregate": agg, "records": records},
                                    ensure_ascii=False, sort_keys=True, indent=1), encoding="utf-8")
    MD_PATH.write_text(render_markdown(agg), encoding="utf-8")
    chart_time(agg, PNG_TIME)
    chart_sens(agg, PNG_SENS)
    return agg


def main(argv: list[str]) -> int:
    if "--kayittan" in argv:
        data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
        agg = write_outputs(data["records"], data["meta"])
        print(f"rapor kayıtlardan yeniden üretildi: {MD_PATH}")
        return 0
    small = "--hizli" in argv
    reps = dict(rm=2, rh=4, rs=3, rd=6) if small else dict(rm=6, rh=20, rs=8, rd=30)
    cases = build_cases(**reps)
    print(f"{len(cases)} koşum planlandı ({reps}); saat sabit, tam donanımlı tohumlar")
    records = run_all(cases)
    meta = {"reps": reps, "plan": PLAN, "healthy": HEALTHY, "sens_rates": list(SENS_RATES),
            "warmup_days": dg.WARMUP_DAYS, "frozen_base": dg.FROZEN_BASE, "frozen_step": dg.FROZEN_STEP,
            "seed_base": dg.SEED_BASE, "seeds": fitted_seeds(max(reps.values()))}
    agg = write_outputs(records, meta)
    print(f"tamam: {JSON_PATH.name}, {MD_PATH.name}, {PNG_TIME.name}, {PNG_SENS.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
