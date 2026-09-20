"""Doğruluk raporu (görev 4.4): her sayı bir koşumdan mı çıkıyor, koşum tekrarlanabilir mi?

"Her sayı bir testten üretiliyor" şu üç şeyle sağlanır:

1. **Toplama saf ve testli**: ``rapor.aggregate`` ve ``render_markdown`` sentetik kayıtlarla
   sınanır (sınıflandırma, güven aralığı, olay oranı).
2. **Rapor kayıttan birebir üretilir**: ``sunum/dogruluk.json`` içindeki ham kayıtlardan raporu
   yeniden üretir ve kayıtlı raporla karşılaştırırız.  Elle değiştirilmiş bir sayı bu testi düşürür.
3. **Koşum tekrarlanabilir**: kayıtlı iki koşum (biri arıza, biri negatif kontrol) yeniden
   koşturulur ve aynı sonucu vermelidir.  Duvar saati sabitlenmeseydi bu test saate göre değişirdi
   (ölçüldü: saat 5 saat kayınca θ tepesi ve "eşiğe kalan gün" değişiyor).

Ayrıca bir düzenek hatasını kalıcı olarak yakalar: ark/analizör senaryoları donanımsız panoda
ALGILANAMAZ; bu yüzden hiçbir kayıt donanımsız bir tohumdan gelemez.
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from panogoz.sim import faults as fx
from sunum import dogruluk as dg
from sunum import rapor as rp


def stored() -> dict:
    assert rp.JSON_PATH.exists(), "sunum/dogruluk.json yok: python -m sunum.rapor ile üretin"
    return json.loads(rp.JSON_PATH.read_text(encoding="utf-8"))


# ------------------------------------------------------------------ istatistik --

def test_clopper_pearson_matches_the_exact_beta_bounds():
    lo, hi = rp.cp_interval(0, 20)
    assert lo == 0.0 and hi == pytest.approx(1 - 0.025 ** (1 / 20), abs=1e-6)
    lo, hi = rp.cp_interval(20, 20)
    assert hi == 1.0 and lo == pytest.approx(0.025 ** (1 / 20), abs=1e-6)
    lo, hi = rp.cp_interval(5, 10)              # klasik tablo değeri
    assert (lo, hi) == (pytest.approx(0.1871, abs=1e-3), pytest.approx(0.8129, abs=1e-3))


def test_poisson_lower_bound_is_the_exact_chi_square_bound():
    assert rp.poisson_lower(0, 1.0) == 0.0
    assert rp.poisson_lower(3, 1.0) == pytest.approx(0.6187, abs=1e-3)      # chi2(0.025; 6) / 2


def test_poisson_upper_bound_is_the_exact_chi_square_bound():
    assert rp.poisson_upper(0, 1.0) == pytest.approx(3.6889, abs=1e-3)      # -ln(0.025)
    assert rp.poisson_upper(3, 2.0) == pytest.approx(4.3836, abs=1e-2)      # chi2(0.975; 8) / 2 / 2


# ----------------------------------------------------------- toplama (sentetik) --

def rec(group: str, scenario: str | None, **over) -> dict:
    base = {
        "case": {"group": group, "scenario": scenario, "kw": {}, "seed": 101, "rep": 0},
        "target_joint": None, "target_max_severity": None, "first_uyari_days": None, "first_izle_days": None,
        "incidents_pre_onset": {}, "incidents_other": {}, "incident_first_day": {},
        "risk_peak": {}, "eta_soon": [], "flags": ["DATA_VALID"], "suppress_codes": [],
        "cusum_first_days_ago": None, "lug_temp_c": None,
    }
    base.update(over)
    return base


def row(agg: dict, name: str) -> dict:
    return next(r for r in agg["matrix"] if r["scenario"] == name)


def test_every_scenario_has_a_row_even_without_records():
    agg = rp.aggregate([])
    assert [r["scenario"] for r in agg["matrix"]] == list(fx.SCENARIOS)
    assert all(r["n"] == 0 for r in agg["matrix"])
    assert agg["healthy"]["runs"] == 0 and agg["dist"]["runs"] == 0


def test_a_positive_scenario_is_classified_by_the_severity_of_its_own_incident():
    recs = [rec("matrix", "asiri_yuk", target_max_severity="KRITIK", first_uyari_days=6.0, risk_peak={"overload": 0.9}),
            rec("matrix", "asiri_yuk", target_max_severity="UYARI", first_uyari_days=8.0, risk_peak={"overload": 0.7}),
            rec("matrix", "asiri_yuk", target_max_severity="IZLE", risk_peak={"overload": 0.5}),
            rec("matrix", "asiri_yuk", target_max_severity=None, risk_peak={"overload": 0.1})]
    r = row(rp.aggregate(recs), "asiri_yuk")
    assert (r["n"], r["team"], r["izle_only"], r["missed"]) == (4, 2, 1, 1)
    assert r["delay_median"] == 7.0 and r["risk_peak_median"] == 0.6


def test_an_incident_on_another_lug_is_a_false_alarm_not_a_detection():
    recs = [rec("matrix", "hizli_gevseme", target_joint="C07-L2-PABUC", target_max_severity=None,
                incidents_other={"loose_connection|C09-L1-PABUC": "UYARI"})]
    r = row(rp.aggregate(recs), "hizli_gevseme")
    assert r["team"] == 0 and r["missed"] == 1 and r["stray_uyari_runs"] == 1


def test_a_negative_control_counts_false_alarms_izle_and_quiet_separately():
    recs = [rec("matrix", "sicak_hava_dalgasi", incidents_other={"loose_connection|C01-L1-PABUC": "UYARI"}),
            rec("matrix", "sicak_hava_dalgasi", incidents_other={"loose_connection|C01-L1-PABUC": "IZLE"}),
            rec("matrix", "sicak_hava_dalgasi"),
            rec("matrix", "sicak_hava_dalgasi", incidents_pre_onset={"loose_connection|C02-L1-PABUC": "KRITIK"})]
    r = row(rp.aggregate(recs), "sicak_hava_dalgasi")
    assert (r["n"], r["false_alarm"], r["izle_only"], r["quiet"]) == (4, 2, 1, 1)


def test_the_target_lugs_own_horizon_is_not_a_false_horizon():
    """Kusurlu pabuç eşiğe gerçekten yaklaşıyor: onun ufku meşrudur.  Başka bir pabuç için
    takvime yazılabilir gün üretilirse o, yanlış ufuktur."""
    own = rec("matrix", "hizli_gevseme", target_joint="C07-L2-PABUC", eta_soon=[["C07-L2-PABUC", "ACIL", 20.0]])
    other = rec("matrix", "hizli_gevseme", target_joint="C07-L2-PABUC", eta_soon=[["C03-L1-PABUC", "IZLE", 70.0]])
    assert row(rp.aggregate([own]), "hizli_gevseme")["false_horizon_runs"] == 0
    assert row(rp.aggregate([other]), "hizli_gevseme")["false_horizon_runs"] == 1


def test_expected_flags_are_counted_from_the_flags_actually_set():
    ok = rec("matrix", "sensor_takildi", flags=["DATA_VALID", "STALE"])
    no = rec("matrix", "sensor_takildi", flags=["DATA_VALID"])
    assert row(rp.aggregate([ok, no]), "sensor_takildi")["flag_ok"] == 1


def test_the_false_alarm_budget_is_events_per_panel_year_with_an_exact_upper_bound():
    runs = [rec("healthy", None, incidents_other={"loose_connection|C01-L1-PABUC": "UYARI",
                                                   "loose_connection|C02-L1-PABUC": "IZLE"},
                incident_first_day={"loose_connection|C01-L1-PABUC": 12.0, "loose_connection|C02-L1-PABUC": 30.0}),
            rec("healthy", None, incidents_other={"loose_connection|C05-L2-PABUC": "KRITIK"},
                incident_first_day={"loose_connection|C05-L2-PABUC": 40.0}),
            rec("healthy", None), rec("healthy", None)]
    h = rp.aggregate(runs)["healthy"]
    days = 4 * (rp.HEALTHY["days"] - dg.WARMUP_DAYS)
    assert h["runs"] == 4 and h["panel_days"] == pytest.approx(days)
    assert (h["incidents_izle_plus"], h["incidents_uyari_plus"], h["incidents_kritik_plus"]) == (3, 2, 1)
    assert h["runs_with_uyari"] == 2
    assert h["uyari_per_panel_year"] == pytest.approx(2 / (days / 365.0), abs=0.01)
    assert h["uyari_per_panel_year_upper"] == pytest.approx(rp.poisson_upper(2, days / 365.0), abs=0.01)
    assert h["uyari_first_day_median"] == 26.0 and h["uyari_first_day_min"] == 12.0
    assert h["uyari_per_panel_year_lower"] == pytest.approx(rp.poisson_lower(2, days / 365.0), abs=0.01)
    assert h["docs04_per_panel_year"] == pytest.approx(0.209 / 100 * 365, abs=0.01)     # docs/04 §5.4
    assert (h["runs_without_uyari"], h["uyari_max_per_run"]) == (2, 1)
    assert h["uyari_distinct_joints"] == 2


def test_the_sensitivity_curve_merges_the_flagship_group_at_its_own_rate():
    sens = [rec("sens", "gevsek_baglanti", target_max_severity=None, case={
        "group": "sens", "scenario": "gevsek_baglanti", "kw": {"rate_k_per_week": 0.2}, "seed": 101, "rep": i})
        for i in range(4)]
    dist = [rec("dist", "gevsek_baglanti", target_max_severity="KRITIK", first_uyari_days=10.0 + i,
                cusum_first_days_ago=30.0, lug_temp_c=50.0) for i in range(5)]
    agg = rp.aggregate(sens + dist)
    by_rate = {s["rate"]: s for s in agg["sens"]}
    assert by_rate[0.2]["detected"] == 0 and by_rate[0.2]["n"] == 4
    assert by_rate[rp.FLAGSHIP_RATE]["detected"] == 5 and by_rate[rp.FLAGSHIP_RATE]["p"] == 1.0
    assert agg["dist"]["delay_median"] == 12.0 and agg["dist"]["fixed_threshold_hits"] == 0
    assert agg["dist"]["cusum_median"] == pytest.approx(rp.PLAN["gevsek_baglanti"]["ago"] - 30.0)


def test_the_rendered_report_is_deterministic_and_has_no_holes():
    agg = rp.aggregate(stored()["records"])
    md = rp.render_markdown(agg)
    assert md == rp.render_markdown(agg)
    # Kelime sınırıyla: "nan" alt dizesi "donanımlı" kelimesinde de geçer.
    import re
    assert not re.search(r"(None|nan|inf)", md), "rapor NaN/None sızdırıyor"
    assert "{" not in md and "}" not in md, "biçimlendirilmemiş yer tutucu kaldı"


# ------------------------------------------------------- plan ve düzenek koruması --

def test_the_plan_covers_exactly_the_seventeen_scenarios():
    assert set(rp.PLAN) == set(fx.SCENARIOS)
    assert len(rp.PLAN) == 17


def test_every_timing_puts_the_fault_inside_the_measured_window():
    for name, p in rp.PLAN.items():
        assert 0 < p["ago"] <= p["days"] - dg.WARMUP_DAYS + 0.5 or name == rp.FLAGSHIP, name
        assert p["dense"] <= p["days"], name
    # Yoğuşma yalnız 3 gün sürer (`days`): "10 gün önce" başlatmak onu ölçümden ÖNCE bitirirdi.
    assert rp.PLAN["yogusma"]["ago"] <= fx.SCENARIOS["yogusma"]["default_kw"]["days"]
    # Trafo devreye alma bir atımdır: 2 s'lik kareler yakalar, 120 s'lik kareler yakalayamazdı.
    assert rp.PLAN["trafo_devreye_alma"]["gap_s"] <= 2


def test_fitted_seeds_really_give_the_demo_panel_a_full_kit():
    """Bir seferinde ark senaryosu 'algılanmadı' göründü: tohumun panosunda ark rölesi yoktu."""
    from panogoz.api import runtime as rtmod
    seeds = rp.fitted_seeds(6)
    assert seeds == sorted(seeds) and len(set(seeds)) == 6
    for s in seeds:
        p = rtmod.build_fleet(3, s).get(rtmod.DEMO_PANEL)
        assert p.has_analyser and p.has_arc_relay, s


def test_no_stored_run_came_from_an_unequipped_panel():
    from panogoz.api import runtime as rtmod
    for seed in {r["case"]["seed"] for r in stored()["records"]}:
        p = rtmod.build_fleet(3, seed).get(rtmod.DEMO_PANEL)
        assert p.has_analyser and p.has_arc_relay, f"tohum {seed}: donanımsız pano ölçüm dışı olmalı"


# ------------------------------------------------- kayıt → rapor, birebir --

def test_the_stored_report_is_exactly_what_the_stored_records_produce():
    data = stored()
    agg = rp.aggregate(data["records"])
    assert json.loads(json.dumps(agg)) == data["aggregate"], "toplanmış sayılar kayıtlarla uyuşmuyor"
    assert rp.render_markdown(agg) == rp.MD_PATH.read_text(encoding="utf-8"), \
        "dogruluk.md, kayıtların ürettiği rapordan farklı (elle düzenlenmiş olabilir)"


def test_the_stored_records_cover_the_planned_runs():
    data = stored()
    reps = data["meta"]["reps"]
    expected = (16 * reps["rm"]) + reps["rh"] + len(rp.SENS_RATES) * reps["rs"] + reps["rd"]
    assert len(data["records"]) == expected
    assert {r["case"]["group"] for r in data["records"]} == {"matrix", "healthy", "sens", "dist"}


# ------------------------------------------------------ tekrarlanabilirlik --

def _same(a, b, path="") -> None:
    if isinstance(a, dict):
        assert isinstance(b, dict) and a.keys() == b.keys(), f"{path}: anahtarlar farklı"
        for k in a:
            _same(a[k], b[k], f"{path}.{k}")
    elif isinstance(a, list):
        assert isinstance(b, list) and len(a) == len(b), f"{path}: uzunluk farklı"
        for i, (x, y) in enumerate(zip(a, b)):
            _same(x, y, f"{path}[{i}]")
    elif isinstance(a, float) or isinstance(b, float):
        assert a == pytest.approx(b, rel=1e-3, abs=0.06), f"{path}: {a} != {b}"
    else:
        assert a == b, f"{path}: {a!r} != {b!r}"


def _pick(records: list[dict], group: str, scenario: str | None) -> dict:
    return next(r for r in records if r["case"]["group"] == group and r["case"]["scenario"] == scenario
                and r["case"]["rep"] == 0)


def test_two_stored_runs_reproduce_exactly_with_the_clock_frozen():
    """Bir arıza koşumu ve bir negatif kontrol, saklı kayıtla aynı sonucu vermeli.  Duvar saati
    sabitlenmeseydi sonuç saate göre değişirdi; bu, `test_negative_pipeline`'ın saate göre düşen
    kırmızılarının kök nedenidir."""
    recs = stored()["records"]
    picks = [_pick(recs, "dist", "gevsek_baglanti"), _pick(recs, "matrix", "sensor_takildi")]
    with ThreadPoolExecutor(max_workers=2) as ex:
        again = list(ex.map(lambda r: dg.run_case_subprocess(r["case"]), picks))
    for old, new in zip(picks, again):
        old, new = dict(old), dict(new)
        old.pop("secs"), new.pop("secs")
        _same(old, new, old["case"]["scenario"])


# ------------------------------------------- ölçülen sonuçlar: taban çizgisi ve boşluklar --

def test_the_two_things_the_demo_stands_on_are_detected_in_every_stored_run():
    """Taban çizgisi: amiral gemisi (gevşek bağlantı) ve ark açması.  Sunum bu ikisine dayanır;
    biri gerilerse rapor yenilendiğinde bu test düşer."""
    agg = stored()["aggregate"]
    d = agg["dist"]
    assert d["detected"] / d["runs"] >= 0.9, f"amiral gemisi {d['detected']}/{d['runs']}"
    ark = next(r for r in agg["matrix"] if r["scenario"] == "ark_olayi")
    assert ark["team"] == ark["n"] > 0, f"ark {ark['team']}/{ark['n']}"
    assert d["fixed_threshold_hits"] == 0, "sabit 90 °C eşiği artık alarm verir: 'eşik atmaz' anlatısı değişti"


def test_known_detection_gaps_are_locked_so_fixing_one_forces_a_documentation_update():
    """Ölçülmüş boşluklar.  Biri KAPANIRSA bu test düşer: iyi haber; rapor, README ve devir notu
    güncellenmeli ve bu küme daraltılmalı.  Bir tanesi YENİ eklenirse bu test düşer: kötü haber."""
    agg = stored()["aggregate"]
    never = {r["scenario"] for r in agg["matrix"]
             if r["expect_alarm"] and r["n"] and r["team"] == 0 and r["scenario"] not in rp.IZLE_BY_DESIGN}
    assert never == {"harmonik_yuk", "asiri_yuk", "havalandirma_tikali", "yogusma", "dedektor_arizasi"}, sorted(never)


def test_the_flag_contract_gaps_of_task_4_3_are_locked_by_measurement():
    """`faults.py` bazı senaryolar için bir bayrak ilan eder (`expect_flags`); ölçüm, hangilerinin
    HİÇBİR koşumda kurulmadığını sayar.  Kapanırsa bu test düşer ve görev 4.3 ilerlemiş demektir."""
    agg = stored()["aggregate"]
    unset = {r["scenario"] for r in agg["matrix"] if r["flag_ok"] == 0 and r["n"]}
    assert unset == {"ark_olayi", "sensor_takildi", "sensor_kaydi", "dugum_sessiz", "pano_enerjisiz"}, sorted(unset)


def test_the_scenarios_own_default_strength_is_below_the_alarm_gate():
    """`gevsek_baglanti` `expect_alarm: True` ilan eder ama varsayılan 0,2 K/hafta 41 günde ekip alarmı
    üretmez (ölçüldü).  Ya senaryo şiddeti ya da beklenti düzeltilene kadar bu, açık bir çelişkidir."""
    agg = stored()["aggregate"]
    default = next(s for s in agg["sens"] if abs(s["rate"] - rp.SCENARIO_DEFAULT_RATE) < 1e-9)
    assert fx.SCENARIOS["gevsek_baglanti"]["default_kw"]["rate_k_per_week"] == rp.SCENARIO_DEFAULT_RATE
    assert fx.SCENARIOS["gevsek_baglanti"]["expect_alarm"] is True
    assert default["detected"] == 0, "varsayılan şiddet artık alarm üretiyor: çelişki kapandı, belgeleri güncelleyin"


def test_the_documented_false_alarm_claim_is_not_supported_end_to_end():
    """docs/04 §5.4 + docs/08 §10: "100 pano × 40 bağlantıda 4,8 günde bir yanlış CUSUM geçişi, bu bir
    ÜST SINIR".  Uçtan uca ölçülen ≥ UYARI olay oranının %95 ALT sınırı bu rakamın ÜSTÜNDE: belge iddiası
    desteklenmiyor.  Bu test bugünkü durumu kilitler; ölçüm belgeyle uyuşursa düşer ve sevindirir."""
    h = stored()["aggregate"]["healthy"]
    assert h["uyari_per_panel_year_lower"] > h["docs04_per_panel_year"], (
        h["uyari_per_panel_year_lower"], h["docs04_per_panel_year"])
