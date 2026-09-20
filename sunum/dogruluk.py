"""Doğruluk sunumu (görev 4.4): 17 senaryo × tespit matrisi, haber verme süresi,
yanlış alarm bütçesi, duyarlılık eğrisi.

Her sayı bir KOŞUMDAN çıkar ve o koşum yeniden üretilebilir:

* Her koşum ayrı bir süreçte, GERÇEK boru hattından geçer (simülatör → ağ geçidi →
  dedektör → bastırma → füzyon → alarm yöneticisi).
* Koşum bir izleme sisteminin arıza sırasında çalıştığı gibi GÜN GÜN işletilir: her günün
  patlamaları beslenir, o günlerde tespit turu çalıştırılır ve alarmın ilk ne zaman açıldığı
  gerçek alarm yöneticisinden okunur.  Yalnız "geçmişi toplu yükle, bir kez değerlendir"
  yolu (``Runtime.bootstrap``) panel düzeyi modları ölçemez: alarm yöneticisi günlük kovalarda
  3/5 kuralı arar ve toplu yükleme yalnız eklem modlarının kovalarını önyükler.
* Duvar saati SABİTLENİR.  Ölçüldü: aynı tohum ve aynı saat bit bit aynı sonucu verir;
  saat 5 saat kaydırılınca θ tepesi, CUSUM ilk aşım günü ve "eşiğe kalan gün" değişir
  (simülatör mutlak zamana bağlıdır).  Saati sabitlemeden bir doğruluk sayısı, raporun
  çekildiği saate bağlı bir sayıdır.
* "Yineleme" = (filo tohumu, saat kayması) çifti; tek çekilişe güvenilmez.

Ne DEĞİLDİR: bu sayıların hiçbiri saha verisiyle doğrulanmış değildir.  Hepsi fizikten
türetilmiş bir simülatör üzerindedir (bkz. README §6).  Simülatörün kendi varsayımlarını
(yük profili, gürültü, arıza modeli) ölçmez; dedektörün BU varsayımlar altındaki
davranışını ölçer.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DAY_S = 86400.0

#: Sabitlenen "şimdi": 2026-08-29 10:40:00 UTC.  Herhangi bir sabit an olurdu.
FROZEN_BASE = 1_788_000_000.0
#: Yineleme r için saat kayması (sn).  3737 s asaldır: yinelemeler günün saatine düzgün yayılır.
FROZEN_STEP = 3737.0
SEED_BASE = 100
DEMO_JOINT = "C07-L2-PABUC"
#: Koşumun ilk günleri ISINMADIR ve değerlendirilmez.  Üretimde yeni kurulumun ilk haftası
#: LEARN_MODE'dur (bayrak, sevk kapısı); bu düzenek panoyu "393 gün önce devreye alınmış"
#: kaydettiği için o kapı yoktur ve dedektör soğuk başlar (baseline yok, RLS soğuk).
WARMUP_DAYS = 7.0


_SEV_RANK = {"BILGI": 0, "IZLE": 1, "UYARI": 2, "KRITIK": 3, "ACIL": 4}


def _merge_sev(acc: dict[str, str], modes: dict[str, str]) -> None:
    for m, sev in modes.items():
        if _SEV_RANK.get(sev, 0) > _SEV_RANK.get(acc.get(m, ""), -1):
            acc[m] = sev


def frozen_now(rep: int) -> float:
    return FROZEN_BASE + rep * FROZEN_STEP


# --------------------------------------------------------------------------
# Tek koşum (ayrı süreçte çalışır, saat sabit)
# --------------------------------------------------------------------------

def run_case(case: dict) -> dict:
    """Bir senaryoyu gerçek boru hattından gün gün geçirir ve ham kaydı döndürür.

    ``case``: ``scenario`` (None = sağlıklı pano), ``ago_days``, ``kw``, ``seed``, ``rep``,
    ``backfill_days`` (toplam koşum süresi), ``eval_days`` (son kaç gün değerlendirilir),
    ``evals_per_day`` (1 = günün son patlaması, 6 = her patlama).

    SAAT SABİTLENMİŞ bir süreçte çağrılmalıdır (bkz. ``_worker_main``).
    """
    from panogoz.api import runtime as rtmod
    from panogoz.rules import pipeline
    from panogoz.sim import faults as fx

    now = time.time()
    scenario = case.get("scenario")
    ago = float(case.get("ago_days") or 0.0)
    kw = dict(case.get("kw") or {})
    days = float(case["backfill_days"])
    per_day = rtmod.BACKFILL_BURSTS_PER_DAY
    every = max(1, per_day // int(case.get("evals_per_day", per_day)))

    rtmod.DEMO_SCENARIOS = () if scenario is None else (
        {"index": 14, "scenario": scenario, "ago_days": ago, "kw": kw, "why_tr": "doğruluk ölçümü"},)
    pipeline.reset()
    t0 = time.perf_counter()
    db = tempfile.mktemp(suffix=".db")
    rt = rtmod.Runtime(n_panels=3, seed=case["seed"], db_path=db, backfill_days=days,
                       scada_port=15999, quiet=True)
    try:
        # bootstrap()'ın 1. ve 2. adımı; geri doldurma yerine gün gün işletme.
        rt.boot_ts = now
        for p in rt.fleet_sim.panels():
            rt._register_panel(p, now)
        rt.store.commit()
        rt._seed_scenarios(now)

        key = rtmod.DEMO_PANEL
        sim = rt.fleet_sim.get(key)
        direct = rtmod._DirectBus(rt.engine.observe)
        gw = rt._gateway(key, direct)
        rt._emit_births(gw, now - days * DAY_S, direct)

        spec = fx.SCENARIOS.get(scenario) if scenario else None
        expected = spec.get("expect_mode") if spec else None
        at_s = float(kw.get("at_s", (spec or {}).get("default_kw", {}).get("at_s", 0.0) or 0.0))
        onset = None if scenario is None else now - ago * DAY_S + at_s

        # Örnekleme planı.  Uzak geçmiş SEYREK (günde 6 patlama × 2 kare), son ``dense_days`` gün
        # YOĞUN (her ``dense_gap_s`` saniyede bir kare).  Zaman biriktiren modlar (ıslanma süresi,
        # aşırı yük süresi, ısıl bekleme) ve olay tipi senaryolar (ark açması) seyrek örneklemede
        # kaçar; üretimde kareler dakikalık gelir.
        dense_days = float(case.get("dense_days", 0.0))
        gap = float(case.get("dense_gap_s", 120.0))
        eval_s = float(case.get("dense_eval_s", 3600.0))
        dense_start = now - dense_days * DAY_S
        sparse_days = days - dense_days
        eval_from = max(now - float(case["eval_days"]) * DAY_S, now - days * DAY_S + WARMUP_DAYS * DAY_S)
        plan: list[tuple[float, int, float, bool]] = []      # (t_end, kare sayısı, aralık, değerlendir)
        n_sparse = int(round(sparse_days * per_day))
        if n_sparse > 0:
            spacing = sparse_days * DAY_S / n_sparse
            for i in range(n_sparse):
                t_end = dense_start - (n_sparse - 1 - i) * spacing
                ev = t_end >= eval_from and (i % per_day) % every == every - 1
                plan.append((t_end, rtmod.BACKFILL_BURST_FRAMES, rtmod.BACKFILL_BURST_GAP_S, ev))
        if dense_days > 0:
            n_dense = int(dense_days * DAY_S / gap)
            eval_every = max(1, int(round(eval_s / gap)))
            for k in range(n_dense):
                plan.append((dense_start + (k + 1) * gap, 1, gap, k % eval_every == eval_every - 1))
        plan[-1] = (plan[-1][0], plan[-1][1], plan[-1][2], True)    # son an her zaman değerlendirilir
        now = plan[-1][0] if abs(plan[-1][0] - now) < 1.0 else now

        # Olay anahtarı "mod|eklem".  Bir olay, beklenen olay ise "hedef"tir: eklem modlarında
        # (gevşek bağlantı) AYNI eklemdeki olay, panel modlarında aynı moddaki herhangi bir olay.
        # Başka bir eklemdeki olay hedefi ALGILAMIŞ sayılmaz (yanlış alarmdır).
        joint_kind = bool(spec) and spec.get("kind") == "joint_thermal"
        target_joint = (kw.get("joint_key") or (spec or {}).get("default_kw", {}).get("joint_key")
                        if joint_kind else None)
        inc_pre: dict[str, str] = {}           # arızadan ÖNCE (sağlıklı dönem): yanlış alarm
        inc_other: dict[str, str] = {}         # arızadan SONRA, hedef olmayan olaylar
        target_first: dict[str, float] = {}    # seviye -> hedef olayın o seviyeye ilk ulaştığı an
        target_max = ""
        risk_peak: dict[str, float] = {}
        first_seen: dict[str, float] = {}      # olay -> koşum başından kaç gün sonra İLK görüldü
        run_start = now - days * DAY_S
        passes = 0
        last_day = None
        live = None
        for t_end, frames, gap_s, do_eval in plan:
            rt._burst(gw, sim, t_end, frames, gap_s)
            day = int(t_end // DAY_S)
            if day != last_day:                       # gün geçişi: günlük özet (rollup döngüsü gibi)
                rt.engine.roll_daily(t_end, days_back=2, panel_key=key)
                last_day = day
            if do_eval:
                rt._detect_pass(t_end)
                passes += 1
                live = rt.panel(key)
                for m, v in (live.risks or {}).items():
                    risk_peak[m] = max(risk_peak.get(m, 0.0), float(v))
                for a in live.alarms:
                    ikey = f"{a.mode}|{a.joint_key or ''}"
                    first_seen.setdefault(ikey, round((t_end - run_start) / DAY_S, 2))
                    is_target = bool(expected) and a.mode == expected and (
                        target_joint is None or a.joint_key == target_joint)
                    if onset is not None and t_end < onset:
                        _merge_sev(inc_pre, {ikey: a.severity})       # arızadan önceki olay = yanlış alarm
                    elif is_target:
                        target_first.setdefault(a.severity, t_end)
                        if _SEV_RANK.get(a.severity, 0) > _SEV_RANK.get(target_max, -1):
                            target_max = a.severity
                    else:
                        _merge_sev(inc_other, {ikey: a.severity})     # hedef olmayan olay

        rt.engine.roll_daily(now, days_back=int(days) + 2, panel_key=key)
        joint = case.get("joint") or DEMO_JOINT
        fa = rt.first_alarm_day(key, joint)
        jv = next((j for j in live.joints if j.key == joint), None)
        codes = sorted({str((getattr(s, "detail", None) or {}).get("code", ""))
                        for s in live.suppressed} - {""})

        def days_since(ts: float | None) -> float | None:
            return None if ts is None or onset is None else round((ts - onset) / DAY_S, 2)

        def first_at_least(level: str) -> float | None:
            """Hedef olayın ``level`` ve üstü bir seviyeye İLK ulaştığı an."""
            ts = [t for sev, t in target_first.items() if _SEV_RANK[sev] >= _SEV_RANK[level]]
            return min(ts) if ts else None

        return {
            "case": case,
            "secs": round(time.perf_counter() - t0, 1),
            "passes": passes,
            "alarms": sorted([a.severity, a.mode, a.joint_key or ""] for a in live.alarms),
            "target_joint": target_joint,
            "target_max_severity": target_max or None,
            "first_izle_days": days_since(first_at_least("IZLE")),
            "first_uyari_days": days_since(first_at_least("UYARI")),
            "incidents_pre_onset": dict(sorted(inc_pre.items())),
            "incidents_other": dict(sorted(inc_other.items())),
            "incident_first_day": dict(sorted(first_seen.items())),
            "risk_peak": {k: round(v, 3) for k, v in sorted(risk_peak.items())},
            "flags": sorted(live.status_flags),
            "suppress_codes": codes,
            "eta_soon": sorted([j.key, j.eta.target, round(float(j.eta.days), 1)]
                               for j in live.joints if j.eta.days is not None and not j.eta.capped),
            "eta_heavy": sorted([j.key, j.eta.target, round(float(j.eta.days), 1)]
                                for j in live.joints if j.eta.days is not None
                                and j.eta.target in ("UYARI", "KRITIK", "ACIL")),
            "theta_max": fa["theta_max"], "theta_last": fa["theta_last"],
            "cusum_first_days_ago": fa["cusum_first_days_ago"],
            "changepoint_days_ago": fa["changepoint_days_ago"],
            "lug_temp_c": None if jv is None or jv.temp_c is None else round(float(jv.temp_c), 1),
            "sibling_median_c": None if jv is None or jv.sibling_median_c is None
            else round(float(jv.sibling_median_c), 1),
            "risks": {k: round(float(v), 3) for k, v in sorted((live.risks or {}).items())},
            "arc": {k: getattr(live.arc, k, None) for k in ("fitted", "online", "active_trip", "active_error",
                                                            "detectors_ok", "detectors_total")},
            "panel_severity": live.severity,
            "health_index": round(float(live.health_index), 1),
        }
    finally:
        rt.stop()
        for suf in ("", "-wal", "-shm"):
            try:
                os.unlink(db + suf)
            except OSError:
                pass


def _worker_main(payload: str) -> int:
    case = json.loads(payload)
    frozen = frozen_now(int(case["rep"]))
    time.time = lambda: frozen                                # SAATİ SABİTLE (bkz. modül başlığı)
    sys.path.insert(0, str(ROOT))
    rec = run_case(case)
    print("KAYIT " + json.dumps(rec, ensure_ascii=False, sort_keys=True), flush=True)
    return 0


def run_case_subprocess(case: dict, timeout: float = 600.0) -> dict:
    """Bir koşumu temiz bir süreçte çalıştırır (paylaşılan durum, port ya da modül yaması sızmaz)."""
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PANOGOZ_NOTIFY_LIVE="0")
    p = subprocess.run([sys.executable, "-m", "sunum.dogruluk", "--worker", json.dumps(case)],
                       cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8",
                       timeout=timeout, env=env)
    for line in p.stdout.splitlines():
        if line.startswith("KAYIT "):
            return json.loads(line[6:])
    raise RuntimeError(f"koşum kayıt üretmedi ({case.get('scenario')}, rep {case.get('rep')}): "
                       f"{(p.stderr or p.stdout)[-800:]}")


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--worker":
        raise SystemExit(_worker_main(sys.argv[2]))
