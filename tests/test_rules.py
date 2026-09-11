"""Proofs for the fusion / suppression / alarm / notification layer.

Run standalone::

    cd grid-up-v2 && PYTHONIOENCODING=utf-8 python -m tests.test_rules

Six claims are made elsewhere in the project.  Each one is proved here with
printed evidence, not with a silent assertion:

1. the health-index waterfall sums EXACTLY to the deficit;
2. a single channel pinned at maximum evidence cannot reach KRITIK on its own;
3. voltage THD rising on all three phases together is suppressed, with its
   Turkish reason written to the store;
4. the 40 % hysteresis dead band and the asymmetric seven-day de-escalation
   behave as specified;
5. an acknowledgement with a wrong token is rejected, and so is one from a
   number that is not on the active rota;
6. the UCS2 SMS encoding round-trips a Turkish message containing ı ş ğ İ Ş Ğ.

Every test is deterministic: explicit ``ts``, explicit seeds, a temporary
database per test, no wall clock in any decision path.
"""

from __future__ import annotations

import json
import math
import os
import sys
import tempfile
import traceback

from panogoz.contracts import assets
from panogoz.contracts.channels import FAILURE_MODES, SEVERITY_RANK
from panogoz.contracts.live import DeviceView, PanelLive
from panogoz.notify import sms
from panogoz.notify.escalation import DEFAULT_ROTA, Notifier, ack_token, compose
from panogoz.rules import alarms, fusion, pipeline, suppression
from panogoz.rules.fusion import _demo_live
from panogoz.store.db import Store

T0 = 1_760_000_000.0
DAY = 86400.0

_RESULTS: list[tuple[str, bool, str]] = []


def _store(tag: str) -> Store:
    return Store(os.path.join(tempfile.mkdtemp(prefix=f"panogoz-{tag}-"), "t.db"))


def _rule(title: str) -> None:
    print()
    print("-" * 78)
    print(title)
    print("-" * 78)


def check(name: str, ok: bool, note: str = "") -> None:
    _RESULTS.append((name, bool(ok), note))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {note}" if note else ""))


# ==========================================================================
# 1. The health-index waterfall sums exactly to the deficit
# ==========================================================================

def test_waterfall_closes() -> None:
    _rule("1 · Sağlık endeksi şelalesi açığı TAM OLARAK kapatır")
    print("  HI = 100 · Π (1-r_m)^w_m  ⇒  ln(HI/100) = Σ w_m ln(1-r_m)")
    print("  ΔHI teleskopik kısmi çarpımlardan gelir, hiçbir atıf sezgiseli yok.")
    print()

    worst_abs = 0.0
    worst_ln = 0.0
    for case, risks in (
        ("hepsi sıfır", {m.key: 0.0 for m in FAILURE_MODES}),
        ("karışık", {m.key: 0.05 + 0.11 * i for i, m in enumerate(FAILURE_MODES)}),
        ("hepsi yüksek", {m.key: 0.93 for m in FAILURE_MODES}),
        ("tek mod", {**{m.key: 0.0 for m in FAILURE_MODES}, "loose_connection": 0.97}),
    ):
        hi, wf = fusion.health_index(risks)
        total = sum(w["delta_hi"] for w in wf)
        residual = total - (hi - 100.0)
        ln_total = sum(w["contribution"] for w in wf)
        ln_residual = ln_total - math.log(hi / 100.0)
        worst_abs = max(worst_abs, abs(residual))
        worst_ln = max(worst_ln, abs(ln_residual))
        print(f"  {case:<14} HI={hi:9.5f}  ΣΔHI={total:10.5f}  HI-100={hi - 100.0:10.5f}  "
              f"kalıntı={residual:+.3e}  ln-kalıntı={ln_residual:+.3e}")

    live = _demo_live()
    j = [x for x in live.joints if x.key == "C07-L2-PABUC"][0]
    j.theta_k, j.temp_c, j.cusum, j.theta_min_k = 14.0, 99.0, 20.0, 0.9
    fusion.apply(live)
    hi_exact = fusion.detail(live)["health_index"]   # unrounded; live.health_index is 2dp
    total = sum(w["delta_hi"] for w in live.hi_waterfall)
    residual = total - (hi_exact - 100.0)
    print()
    print(f"  canlı görüntü: HI={hi_exact:.6f} (ekranda {live.health_index:.2f})")
    for w in live.hi_waterfall:
        print(f"    {w['mode']:<18} r={w['risk']:.4f} w={w['weight']:.2f} "
              f"ln-pay={w['contribution']:+.5f}  ΔHI={w['delta_hi']:+8.4f}")
    print(f"    {'TOPLAM':<18} {'':>25} ΣΔHI={total:+.6f}  (HI-100 = "
          f"{hi_exact - 100.0:+.6f})   kalıntı={residual:+.3e}")

    check("şelale açığı tam kapatır (|kalıntı| < 1e-9)",
          worst_abs < 1e-9 and abs(residual) < 1e-9,
          f"en kötü kalıntı {worst_abs:.3e}, canlı kalıntı {residual:.3e}")
    check("logaritmik paylar da tam toplanır", worst_ln < 1e-9,
          f"en kötü ln-kalıntı {worst_ln:.3e}")


# ==========================================================================
# 2. One channel at maximum evidence cannot reach KRITIK
# ==========================================================================

def test_single_channel_cannot_dispatch() -> None:
    _rule("2 · Tek kanal, azami kanıtta bile KRITIK'e ULAŞAMAZ")
    print(f"  |llr| ≤ {fusion.LLR_CAP};  ön olasılık %2 ⇒ tek kanalın ulaşabileceği en "
          f"yüksek risk = {fusion.sigmoid(fusion.logit(0.02) + fusion.LLR_CAP):.4f}")
    print("  Ayrıca iki bağımsız ölçüm ilkesi yoksa seviye UYARI ile sınırlanır.")
    print()

    live = _demo_live()
    for x in live.joints:
        x.temp_c = None            # termal dizi yok -> IR ailesi yok
        x.sibling_median_c = None
    live.pd.qmax_db = live.pd.tev_db = live.pd.rate_per_s = 0.0
    j = [x for x in live.joints if x.key == "C07-L2-PABUC"][0]
    j.theta_k, j.theta_min_k, j.cusum, j.slope_k_per_week = 400.0, 0.9, 500.0, 20.0
    fusion.apply(live)
    d = fusion.detail(live)
    print(f"  θ = {j.theta_k:.0f} K (saçma derecede yüksek), CUSUM = {j.cusum:.0f}, "
          f"eğim = {j.slope_k_per_week:.0f} K/hafta")
    print(f"  aileler        : {d['families']}")
    print(f"  risk(gevşek)   : {live.risks['loose_connection']:.4f}")
    print(f"  sağlık endeksi : {live.health_index:.2f}")
    print(f"  seviye         : {live.severity}")
    for c in d["severity"]["caps"]:
        print(f"  sınırlama      : {c}")

    check("tek aile ile seviye KRITIK'e çıkamaz",
          SEVERITY_RANK[live.severity] < SEVERITY_RANK["KRITIK"],
          f"seviye = {live.severity}")

    st = _store("t2")
    pipeline.reset()
    hist: dict = {}
    for dd in range(5):
        lv = _demo_live()
        lv.ts = T0 + dd * DAY
        for x in lv.joints:
            x.temp_c = None
            x.sibling_median_c = None
        lv.pd.qmax_db = lv.pd.tev_db = lv.pd.rate_per_s = 0.0
        jj = [x for x in lv.joints if x.key == "C07-L2-PABUC"][0]
        jj.theta_k, jj.theta_min_k, jj.cusum, jj.slope_k_per_week = 400.0, 0.9, 500.0, 20.0
        pipeline.run(lv, st, hist, T0 + dd * DAY)
    dispatched = [a for a in lv.alarms if a.dispatched]
    print()
    print(f"  5 gün sonra açık alarm = {len(lv.alarms)}, telefona çıkan = {len(dispatched)}")
    reasons = [r["reason"] for r in st.suppressions(since=0) if "Bildirim yapılmadı" in r["reason"]]
    if reasons:
        print(f"  gerekçe: {reasons[0][:130]}")
    check("tek kanal ekip yönlendirmez", len(dispatched) == 0,
          f"{len(dispatched)} yönlendirme")

    # And the contrast: add the second, genuinely independent family.
    lv2 = _demo_live()
    j2 = [x for x in lv2.joints if x.key == "C07-L2-PABUC"][0]
    j2.theta_k, j2.theta_min_k, j2.cusum, j2.temp_c = 14.0, 0.9, 20.0, 99.0
    fusion.apply(lv2)
    d2 = fusion.detail(lv2)
    print()
    print(f"  karşılaştırma · ikinci bağımsız aile eklendiğinde: aileler={d2['families']} "
          f"HI={lv2.health_index:.1f} seviye={lv2.severity}")
    check("iki bağımsız aile KRITIK üretebilir",
          SEVERITY_RANK[lv2.severity] >= SEVERITY_RANK["KRITIK"],
          f"seviye = {lv2.severity}")


# ==========================================================================
# 3. Three-phase voltage THD is suppressed, with a recorded reason
# ==========================================================================

def test_three_phase_thd_suppressed() -> None:
    _rule("3 · Üç fazda birlikte yükselen gerilim THD'si ŞEBEKE OLAYI ADAYIDIR")

    def build(thd: tuple[float, float, float], freq: float = 50.0) -> PanelLive:
        lv = _demo_live()
        j = [x for x in lv.joints if x.key == "C07-L2-PABUC"][0]
        j.theta_k, j.temp_c, j.cusum, j.slope_k_per_week, j.theta_min_k = (
            14.0, 99.0, 20.0, 0.8, 0.9)
        lv.analyser.update({"mpr.thd_v_l1_pct": thd[0], "mpr.thd_v_l2_pct": thd[1],
                            "mpr.thd_v_l3_pct": thd[2], "mpr.freq_hz": freq})
        lv.pd.klass, lv.pd.qmax_db = "YUZEN", 34.0
        return lv

    st_a = _store("t3a")
    st_b = _store("t3b")
    pipeline.reset()
    ha: dict = {}
    for dd in range(4):
        a = build((2.1, 2.0, 2.2))
        a.ts = T0 + dd * DAY
        pipeline.run(a, st_a, ha, T0 + dd * DAY)
    pipeline.reset()
    hb: dict = {}
    for dd in range(4):
        b = build((6.5, 6.2, 6.8))
        b.ts = T0 + dd * DAY
        pipeline.run(b, st_b, hb, T0 + dd * DAY)

    print(f"  A · şebeke sakin  THD_V = %2.1 / %2.0 / %2.2")
    print(f"      HI={a.health_index:6.2f}  seviye={a.severity:<7} "
          f"risk(gevşek)={a.risks['loose_connection']:.3f}  "
          f"risk(yalıtım)={a.risks['insulation']:.3f}  "
          f"telefona çıkan={sum(1 for x in a.alarms if x.dispatched)}")
    print(f"  B · şebeke olayı  THD_V = %6.5 / %6.2 / %6.8")
    print(f"      HI={b.health_index:6.2f}  seviye={b.severity:<7} "
          f"risk(gevşek)={b.risks['loose_connection']:.3f}  "
          f"risk(yalıtım)={b.risks['insulation']:.3f}  "
          f"telefona çıkan={sum(1 for x in b.alarms if x.dispatched)}")
    print(f"      bayraklar={b.status_flags}")

    rows = [r for r in st_b.suppressions(since=0)
            if json.loads(r["detail"]).get("code") == "GRID_THD_3PH"]
    print()
    print(f"  mağazadaki GRID_THD_3PH satırı: {len(rows)}")
    if rows:
        print(f"  gerekçe (operatörün gördüğü metin):")
        print(f"    {rows[0]['reason']}")
        print(f"  etkilenen modlar: "
              f"{sorted({r['mode'] for r in rows if r['mode']})}")

    neg = fusion.negative_evidence(b)
    print(f"  negatif kanıt: { {k: round(v, 2) for k, v in neg.items()} }")

    check("ADAY bayrağı kuruldu, KESİN bayrak kurulmadı",
          "GRID_DISTURBANCE_CANDIDATE" in b.status_flags
          and "GRID_DISTURBANCE" not in b.status_flags,
          f"{b.status_flags}")
    check("kanıtı harmoniğin kendisi olan modlara tam -1.5 llr itildi",
          all(abs(neg.get(m, 0.0) - suppression.GRID_LLR) < 1e-9
              for m in suppression.THD_ATTRIBUTABLE_MODES),
          f"{ {k: round(v, 2) for k, v in neg.items()} }")
    check("ısıl modlara yalnızca aday itmesi (-0.5) uygulandı",
          all(abs(neg.get(m, 0.0) - suppression.GRID_CANDIDATE_LLR) < 1e-9
              for m in suppression.THD_CANDIDATE_MODES),
          f"{ {k: round(v, 2) for k, v in neg.items()} }")
    check("risk gizlenmedi, DÜŞÜRÜLDÜ",
          b.risks["loose_connection"] < a.risks["loose_connection"]
          and b.risks["insulation"] < a.risks["insulation"],
          f"gevşek {a.risks['loose_connection']:.3f} → {b.risks['loose_connection']:.3f}")
    check("SCADA'ya giden sağlık endeksi de toparlandı",
          b.health_index > a.health_index,
          f"{a.health_index:.1f} → {b.health_index:.1f}")
    # THE DELIBERATE CHANGE.  Voltage THD on three phases is also what a large
    # in-facility rectifier, VFD bank or UPS produces, and the analyser cannot
    # tell that apart from a regional event.  Vetoing a crew on that basis would
    # leave a 99 C lug unattended for as long as the distortion lasted, so the
    # veto now has to be EARNED by evidence the panel cannot manufacture.
    check("THD tek başına ekip vetosu koymuyor",
          any(x.dispatched for x in b.alarms),
          f"gönderilen={sum(1 for x in b.alarms if x.dispatched)}")

    pipeline.reset()
    st_c = _store("t3c")
    hc: dict = {}
    for dd in range(4):
        c = build((6.5, 6.2, 6.8), freq=50.9)
        c.ts = T0 + dd * DAY
        pipeline.run(c, st_c, hc, T0 + dd * DAY)
    print(f"  C · THD + frekans sapması  bayraklar={c.status_flags}")
    check("frekans teyit edince aday KESİN şebeke olayına yükseldi",
          "GRID_DISTURBANCE" in c.status_flags, f"{c.status_flags}")
    check("teyit edilmiş şebeke olayında ekip yönlendirilmedi",
          not any(x.dispatched for x in c.alarms))
    check("gerekçe Türkçe olarak mağazaya yazıldı",
          bool(rows) and "şebeke" in rows[0]["reason"].lower(),
          f"{len(rows)} satır")
    check("şebeke sakinken aynı ölçüm ekip yönlendirir",
          any(x.dispatched for x in a.alarms))


# ==========================================================================
# 4. Hysteresis and asymmetric de-escalation
# ==========================================================================

def test_hysteresis_and_deescalation() -> None:
    _rule("4 · %40 ölü bant ve asimetrik 7 günlük geri çekilme")
    st = _store("t4")
    pipeline.reset()
    mgr = alarms.AlarmManager(st, fleet_size=20)
    pipeline.set_manager(st, mgr)
    hist: dict = {}
    target = "C07-L2-PABUC"

    def day(dd: int, theta: float, temp: float) -> PanelLive:
        lv = _demo_live()
        lv.ts = T0 + dd * DAY
        j = [x for x in lv.joints if x.key == target][0]
        j.theta_k, j.temp_c, j.theta_min_k = theta, temp, 0.9
        j.cusum = max(0.0, (theta - 2.0) * 2.0)
        j.slope_k_per_week = 0.4 if theta > 3 else 0.0
        pipeline.run(lv, st, hist, T0 + dd * DAY)
        return lv

    raise_k = fusion.THETA_RAISE["KRITIK"]
    clear_k = fusion.HYSTERESIS * raise_k
    print(f"  kaldırma eşiği (KRITIK) = {raise_k:.1f} K")
    print(f"  temizlenme eşiği        = {fusion.HYSTERESIS:.0%} × {raise_k:.1f} = {clear_k:.1f} K")
    print(f"  N-of-M debounce         = {alarms.DEBOUNCE_N}/{alarms.DEBOUNCE_M} günlük "
          f"değerlendirme")
    print(f"  kapanış koşulu          = {alarms.CLEAR_DAYS} ardışık temiz gün")
    print()

    print("  faz 1 · yükselme (θ = 13.5 K)")
    for dd in range(4):
        day(dd, 13.5, 98.0)
        n = len(st.query("SELECT id FROM incident WHERE joint_key=? AND state!='KAPANDI'",
                         (target,)))
        print(f"    gün {dd}: açık olay = {n}")
    inc = st.one("SELECT * FROM incident WHERE joint_key=? ORDER BY id LIMIT 1", (target,))
    opened_ok = inc is not None
    debounce_ok = opened_ok and inc["opened_at"] >= T0 + 2 * DAY - 1
    print(f"    olay #{inc['id'] if inc else '-'} seviye={inc['severity'] if inc else '-'} "
          f"açılış günü={(inc['opened_at'] - T0) / DAY:.0f}")
    check("olay 3/5 debounce dolmadan açılmaz", debounce_ok,
          f"açılış günü {(inc['opened_at'] - T0) / DAY:.0f}" if inc else "olay yok")

    print()
    print(f"  faz 2 · ölü bant (θ = 9.0 K: kaldırma eşiğinin ALTINDA, temizlenme "
          f"eşiğinin ÜSTÜNDE)")
    for dd in range(4, 10):
        day(dd, 9.0, 60.0)
    row = st.one("SELECT * FROM incident WHERE id=?", (inc["id"],))
    print(f"    6 gün sonra durum={row['state']} seviye={row['severity']}")
    check("ölü bant içinde olay kapanmaz", row["state"] == alarms.STATE_ACIK)
    check("açık olayın seviyesi düşmez (asimetri)", row["severity"] == inc["severity"],
          f"{inc['severity']} → {row['severity']}")

    print()
    print(f"  faz 3 · gerçek temizlenme (θ = 1.0 K < {clear_k:.1f} K)")
    closed_on = None
    for dd in range(10, 20):
        day(dd, 1.0, 42.0)
        row = st.one("SELECT * FROM incident WHERE id=?", (inc["id"],))
        print(f"    temiz gün {dd - 9}: durum = {row['state']}")
        if row["state"] == alarms.STATE_KAPANDI:
            closed_on = dd - 9
            break
    check(f"tam {alarms.CLEAR_DAYS} temiz günde kapanır", closed_on == alarms.CLEAR_DAYS,
          f"{closed_on} günde kapandı")
    row = st.one("SELECT * FROM incident WHERE id=?", (inc["id"],))
    print(f"    kapanış gerekçesi: {row['action']}")
    check("kapanış gerekçesi kaydedildi", bool(row["action"]) and row["closed_at"] is not None)


# ==========================================================================
# 5. Acknowledgement authentication
# ==========================================================================

def test_ack_authentication() -> None:
    _rule("5 · Onay kimlik doğrulaması: yanlış token ve rota dışı numara REDDEDİLİR")
    st = _store("t5")
    modem = sms.GsmModem()
    notifier = Notifier(st, modem=modem)

    inc_id = st.open_incident(
        panel_key="SOKE-14", joint_key="C07-L2-PABUC", mode="loose_connection",
        severity="KRITIK", opened_at=T0, updated_at=T0,
        title="Çıkış 7 · L2 · çıkış pabucu — bağlantı direnci artıyor",
        action="Bağlantıyı tork anahtarı ile yeniden sıkın",
        evidence={"joint": {"theta_k": 14.2, "temp_c": 99.0}}, ruled_out=[])
    tok = ack_token(inc_id)
    st.update_incident(inc_id, ack_token=tok)
    st.commit()

    on_rota = DEFAULT_ROTA[0]["number"]
    off_rota = "+905559998877"
    print(f"  olay #{inc_id}  token = {tok}")
    print(f"  rotadaki numara  = {on_rota} ({DEFAULT_ROTA[0]['name']})")
    print(f"  rota dışı numara = {off_rota}")
    print()

    r1 = notifier.ack(inc_id, on_rota, "0000")
    print(f"  rotadaki + YANLIŞ token '0000'   -> {r1}")
    r2 = notifier.ack(inc_id, on_rota, None)
    print(f"  rotadaki + token YOK             -> {r2}")
    r3 = notifier.ack(inc_id, off_rota, tok)
    print(f"  ROTA DIŞI + doğru token          -> {r3}")
    r4 = notifier.ack(inc_id, on_rota, tok)
    print(f"  rotadaki + doğru token           -> {r4}")

    row = st.one("SELECT * FROM incident WHERE id=?", (inc_id,))
    print(f"  sonuç: durum={row['state']} onaylayan={row['acked_by']}")
    print(f"  reddedilenler: {[x['reason'] for x in notifier.rejected_acks]}")

    check("yanlış token reddedilir", r1 is False)
    check("token olmadan onay reddedilir", r2 is False)
    check("rota dışı numara doğru token ile bile reddedilir", r3 is False)
    check("rotadaki numara + doğru token kabul edilir", r4 is True)
    check("her ret denetim zincirine yazıldı",
          {"bad_token", "not_on_rota"} <= {x["reason"] for x in notifier.rejected_acks})

    # And the same two gates over the SMS reply path.
    inc2 = st.open_incident(
        panel_key="SOKE-14", joint_key="C08-L1-PABUC", mode="loose_connection",
        severity="KRITIK", opened_at=T0, updated_at=T0,
        title="Çıkış 8 · L1 · çıkış pabucu — bağlantı direnci artıyor", action="Torkla")
    tok2 = ack_token(inc2)
    st.update_incident(inc2, ack_token=tok2)
    st.commit()
    print()
    print(f"  SMS yanıt yolu · olay #{inc2} token={tok2}")
    modem.inject_reply(off_rota, f"TAMAM {inc2} {tok2}")
    a1 = notifier.check_replies(T0)
    modem.inject_reply(on_rota, f"TAMAM {inc2} 1234")
    a2 = notifier.check_replies(T0)
    modem.inject_reply(on_rota, f"TAMAM {inc2} {tok2}")
    a3 = notifier.check_replies(T0)
    print(f"    rota dışı gönderen, doğru token -> onaylanan {a1}")
    print(f"    rotadaki gönderen, yanlış token -> onaylanan {a2}")
    print(f"    rotadaki gönderen, doğru token  -> onaylanan {a3}")
    check("SMS yolunda da iki kapı birden uygulanır",
          a1 == 0 and a2 == 0 and a3 == 1, f"{a1}/{a2}/{a3}")
    check("denetim zinciri bozulmadı", st.verify_chain()["ok"] is True,
          json.dumps(st.verify_chain()))


# ==========================================================================
# 6. UCS2 round-trip
# ==========================================================================

def test_ucs2_roundtrip() -> None:
    _rule("6 · UCS2 kodlaması ı ş ğ İ Ş Ğ içeren Türkçe mesajı kayıpsız taşır")
    msg = ("PANO GÖZ KRITIK · SÖKE-14 · Çıkış 7 · L2 pabuç: bağlantı direnci artıyor. "
           "İŞĞ ışğ · Şalteri AÇMAYIN, ekip yönlendirin.")
    print(f"  metin  : {msg}")
    print(f"  uzunluk: {len(msg)} karakter, {sms.ucs2_octets(msg)} oktet")
    print()
    print(f"  gsm7_encodable = {sms.gsm7_encodable(msg)}")
    print(f"  GSM 03.38'in taşıyamadığı karakterler = "
          f"{''.join(sms.missing_in_gsm7(msg))}")
    print(f"  (translit alternatifi, VARSAYILAN DEĞİL): "
          f"{sms.transliterate(msg)[:70]}…")

    hexed = sms.ucs2_encode(msg)
    back = sms.ucs2_decode(hexed)
    print()
    print(f"  hex ilk 64 : {hexed[:64]}…")
    print(f"  geri dönüş : {back}")
    per_char = {c: (sms.ucs2_encode(c), sms.ucs2_decode(sms.ucs2_encode(c)) == c)
                for c in sms.TURKISH_MISSING}
    print()
    print("  karakter bazında:")
    for c, (h, ok) in per_char.items():
        print(f"    {c}  U+{h}  gidiş-dönüş {'OK' if ok else 'HATA'}")

    parts = sms.split_ucs2(msg)
    print()
    print(f"  parça bütçesi: tek parça {sms.UCS2_SINGLE_CHARS} karakter, "
          f"birleşik {sms.UCS2_CONCAT_CHARS} karakter/parça")
    print(f"  bu mesaj {len(parts)} parça: {[len(p) for p in parts]} karakter")

    modem = sms.GsmModem()
    res = modem.send("+905321112233", msg)
    at = res["transcript"]
    print()
    print("  AT dökümünden alıntı:")
    for line in at.split(chr(10)):
        if line.startswith(("AT+CSCS", "AT+CSMP", "AT+CMGS", "+CMGS", "# GSM")):
            print(f"    {line[:96]}")

    sent_hex = [ln[2:].rstrip(sms.SUB) for ln in at.split(chr(10)) if ln.startswith("> ")]
    rebuilt = "".join(sms.ucs2_decode(h) for h in sent_hex)
    print(f"  dökümdeki hex'ten yeniden kurulan metin eşleşiyor mu: {rebuilt == msg}")

    check("UCS2 gidiş-dönüş kayıpsız", back == msg)
    check("altı Türkçe karakterin hepsi korunuyor",
          all(ok for _, ok in per_char.values()) and all(c in back for c in sms.TURKISH_MISSING),
          sms.TURKISH_MISSING)
    check("GSM 03.38 bu metni taşıyamaz (bu yüzden UCS2)",
          not sms.gsm7_encodable(msg))
    check("modem UCS2'ye geçti", res["encoding"] == "UCS2" and 'AT+CSCS="UCS2"' in at)
    check("AT dökümü gerçek bir alışveriş",
          all(t in at for t in ("AT", "ATE0", "AT+CMGF=1", 'AT+CSCS="GSM"', "AT+CSQ",
                                "AT+CMGS=", "> ", "+CMGS:", "OK")) and sms.SUB in at)
    check("dökümdeki yükten metin birebir geri kuruluyor", rebuilt == msg)
    check("70 karakter tek parça sınırı uygulanıyor",
          len(sms.split_ucs2("A" * 70)) == 1 and len(sms.split_ucs2("A" * 71)) == 2)

    demo = compose({"id": 42, "panel_key": "SOKE-14", "joint_key": "C07-L2-PABUC",
                    "mode": "loose_connection", "severity": "KRITIK",
                    "ack_token": "4712",
                    "evidence": {"joint": {"theta_k": 14.2, "temp_c": 99.0}}})
    print()
    print(f"  gerçek alarm gövdesi ({len(demo)} karakter): {demo}")
    check("alarm gövdesi 140 UCS2 karakterin altında", len(demo) <= 140, f"{len(demo)}")


# ==========================================================================
# Extra: device attribution, storm cap and the suppression console
# ==========================================================================

def test_device_attribution() -> None:
    _rule("Ek · Sapan sensör CİHAZ iş emri üretir, tork iş emri DEĞİL")
    st = _store("tdev")
    pipeline.reset()
    lv = _demo_live()
    lv.devices = [DeviceView(key=d.key, kind=d.kind, label=d.label, online=True)
                  for d in assets.DEVICES]
    lv.devices[1].faults = ["MOUNT_LOST"]
    for jk in ("C06-L1-PABUC", "C06-L2-PABUC", "C06-L3-PABUC"):
        j = [x for x in lv.joints if x.key == jk][0]
        j.theta_k, j.temp_c, j.theta_min_k = 16.0, 101.0, 0.9
    hist = {"device_residual": {"TC-03": {"drift_k_per_day": 0.62}}}
    pipeline.run(lv, st, hist, T0)

    orders = suppression.device_orders(lv)
    out = fusion.suppressed_joints(lv)
    print(f"  cihaz iş emirleri: {[(o['device'], o['reason']) for o in orders]}")
    print(f"  panonun riskinden çıkarılan bağlantılar: {sorted(out)}")
    for o in orders:
        print(f"    · {o['reason_tr'][:150]}")
    joint_incidents = st.query(
        "SELECT joint_key FROM incident WHERE joint_key IN (?,?)",
        ("C06-L2-PABUC", "C06-L3-PABUC"))
    print(f"  bu bağlantılar için açılan tork iş emri: {len(joint_incidents)}")
    check("cihaz arızası olan bağlantılar pano riskine girmez",
          {"C06-L2-PABUC", "C06-L3-PABUC"} <= out)
    check("sapan/düşen sensör için tork iş emri açılmaz", len(joint_incidents) == 0)
    check("her cihaz iş emri 'bağlantıya müdahale etmeyin' der",
          all("etmeyin" in o["action_tr"] for o in orders))


def test_storm_cap_exempts_acil() -> None:
    _rule("Ek · Fırtına sınırı ACİL'i muaf tutar")
    print(f"  saatlik sınırlar: {alarms.STORM_CAP_PER_HOUR}")
    print(f"  ACIL sınır tablosunda YOK ⇒ muaf")
    check("ACIL fırtına sınırına tabi değil", "ACIL" not in alarms.STORM_CAP_PER_HOUR)
    check("KRITIK sınırlı", alarms.STORM_CAP_PER_HOUR.get("KRITIK", 0) > 0,
          f"saatte {alarms.STORM_CAP_PER_HOUR['KRITIK']}")


# ==========================================================================

def main() -> int:
    print("=" * 78)
    print("PANO GOZ · kural katmanı testleri (fusion · suppression · alarms · notify)")
    print("=" * 78)

    tests = (
        test_waterfall_closes,
        test_single_channel_cannot_dispatch,
        test_three_phase_thd_suppressed,
        test_hysteresis_and_deescalation,
        test_ack_authentication,
        test_ucs2_roundtrip,
        test_device_attribution,
        test_storm_cap_exempts_acil,
    )
    for t in tests:
        try:
            t()
        except Exception:  # pragma: no cover - a crashed test is a failed test
            traceback.print_exc()
            _RESULTS.append((t.__name__, False, "istisna"))

    print()
    print("=" * 78)
    passed = sum(1 for _, ok, _ in _RESULTS if ok)
    for name, ok, note in _RESULTS:
        if not ok:
            print(f"  FAIL {name} {note}")
    print(f"{passed}/{len(_RESULTS)} kontrol geçti")
    print("=" * 78)
    return 0 if passed == len(_RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
