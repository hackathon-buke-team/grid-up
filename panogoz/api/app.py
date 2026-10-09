"""The REST + WebSocket API.

One FastAPI application in front of one :class:`~panogoz.api.runtime.Runtime`.
Every route is a projection of an object the detector or the rules layer already
built - nothing here decides anything, because a number that appears for the
first time in a web handler is a number nobody can reproduce from the store.

Two conventions the UI can rely on
----------------------------------

* **An unknown panel is a 404, a missing joint is not.**  A judge who mistypes a
  panel key should be told so.  A chart whose channel happens to be empty on
  this panel - the thirty-four lugs with no CT, a panel with no analyser, a PD
  record that has not been taken yet - must render as an empty chart with its
  axis labels intact, not as a red box.  So ``/trend`` and ``/daily`` always
  return the channel metadata and an empty ``series`` rather than an error.
* **Turkish for humans, English for machines.**  Field names, channel names and
  mode keys are English identifiers; every label, reason and action is Turkish.

Security, honestly
------------------

There is no authentication here, and that is a deliberate demo choice, not an
oversight.  In production this process sits inside the OT zone and the boundary
is drawn at the reverse proxy - see :data:`IEC62443_NOTE` and the one-line
marker in :func:`create_app`.
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import math
import os
import time
from pathlib import Path
from typing import Any

from fastapi import Body, FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles

from panogoz.api.runtime import (
    BACKFILL_KEEP_RAW_DAYS as RAW_RETENTION_DAYS,
    DAY_S, DEMO_PANEL, DETECT_PERIOD_S, VERSION, Runtime,
)
from panogoz.contracts import assets, channels, icd
from panogoz.contracts.live import AlarmView, EtaView, SuppressionView
from panogoz.sim import faults as fx

ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIR = ROOT / "frontend"
DOCS_DIR = ROOT / "docs"

#: Where the zone boundary goes when this stops being a demo.
IEC62443_NOTE = (
    "IEC 62443-3-3 zone boundary: in production this process runs inside the "
    "OT zone (SL 2) and is never exposed directly. The conduit is a reverse "
    "proxy terminating mTLS, enforcing SR 1.1/1.2 (human and device "
    "authentication) and SR 2.1 (authorisation enforcement), with the SCADA "
    "Modbus slave on a separate, read-only conduit. The demo binds plain HTTP "
    "on localhost with CORS wide open because it is a demo."
)

WS_PERIOD_S = 2.0


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _num(x: Any) -> Any:
    """JSON-safe float: NaN and +-inf are not valid JSON."""
    if isinstance(x, float):
        if math.isnan(x) or math.isinf(x):
            return None
        return x
    return x


def _clean(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_clean(v) for v in obj]
    return _num(obj)


def _jload(raw: Any, default: Any) -> Any:
    if raw is None:
        return default
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(raw)
    except Exception:  # noqa: BLE001
        return default


def mode_label(mode: str | None) -> str:
    for m in channels.FAILURE_MODES:
        if m.key == mode:
            return m.label_tr
    return mode or ""


#: Turkish gloss for every status flag, plus the one case where a flag means
#: something different from what it says.
FLAG_LABELS_TR: dict[str, str] = {b.name: b.label_tr for b in icd.STATUS_BITS}


def flag_notes(live) -> list[dict]:
    """Per-flag gloss, and the corrections a flag needs to be read honestly.

    One correction is load-bearing.  ``DE_ENERGISED`` is raised by the detector
    when the panel load factor is essentially zero, and the panel load factor
    comes from the Entes MPR-53CS.  TEDAS Madde 2.2.11 lets a panel be built
    WITHOUT an analyser (about one in eight of ours is), and on those panels the
    load factor is zero because nobody is measuring it - not because the busbar
    is dead.  Reporting "pano enerjisiz" for an energised panel is exactly the
    class of confident-and-wrong statement this system exists to avoid, so the
    API says so rather than repeating the flag.

    The correction belongs upstream, in the detector: DE_ENERGISED should be
    gated on ``analyser_fitted``.  Until it is, this is where a UI must read it.
    """
    out: list[dict] = []
    for f in live.status_flags:
        entry = {"flag": f, "label_tr": FLAG_LABELS_TR.get(f, f), "override_tr": None}
        if f == "DE_ENERGISED" and not live.analyser_fitted:
            entry["override_tr"] = (
                "DİKKAT: bu panoda enerji analizörü YOK (TEDAŞ Madde 2.2.11 "
                "seçenek 2). Akım ölçülmediği için yük faktörü sıfır görünüyor; "
                "bu 'pano enerjisiz' DEMEK DEĞİLDİR, 'akımı ölçmüyoruz' demektir. "
                "Isıl göstergeler yine de kardeş farkı olarak geçerlidir."
            )
            entry["label_tr"] = "Akım ölçümü yok (analizör takılı değil)"
        out.append(entry)
    return out


def panel_summary(live) -> dict:
    """The fleet-card projection.  Exactly the fields the spec fixes."""
    return _clean({
        "panel_key": live.panel_key,
        "panel_index": live.panel_index,
        "site": live.site,
        "name": live.name,
        "dso": live.dso,
        "lat": live.lat,
        "lon": live.lon,
        "health_index": round(live.health_index, 1),
        "severity": live.severity,
        "severity_label": channels.SEVERITY_TR.get(live.severity, live.severity),
        "severity_rank": channels.SEVERITY_RANK.get(live.severity, 0),
        "status_flags": list(live.status_flags),
        "theta_max": round(live.theta_max, 2),
        "theta_max_joint": live.theta_max_joint,
        "theta_delta_7d": round(live.theta_delta_7d, 2),
        "eta": live.eta.to_dict(),
        "sensitivity_pct": round(live.sensitivity_pct, 1),
        "load_factor": round(live.load_factor, 4),
        "alarm_count": len(live.alarms),
        "devices_online": sum(1 for d in live.devices if d.online),
        "devices_total": len(live.devices),
        "data_age_s": round(live.data_age_s, 1),
        "analyser_fitted": live.analyser_fitted,
        "arc_fitted": live.arc.fitted,
        "flag_notes": flag_notes(live),
    })


def alarm_from_row(row: dict) -> dict:
    """One ``incident`` row projected onto :class:`AlarmView`."""
    view = AlarmView(
        id=int(row["id"]),
        panel_key=row["panel_key"],
        joint_key=row.get("joint_key"),
        mode=row.get("mode") or "",
        mode_label=mode_label(row.get("mode")),
        severity=row.get("severity") or "BILGI",
        state=row.get("state") or "ACIK",
        title=row.get("title") or "",
        opened_at=float(row.get("opened_at") or 0.0),
        updated_at=float(row.get("updated_at") or 0.0),
        acked_at=row.get("acked_at"),
        acked_by=row.get("acked_by"),
        action=row.get("action") or "",
        evidence=_jload(row.get("evidence"), {}),
        ruled_out=_jload(row.get("ruled_out"), []),
        dispatched=bool(row.get("dispatched")),
    )
    d = view.to_dict()
    d["severity_label"] = channels.SEVERITY_TR.get(view.severity, view.severity)
    d["closed_at"] = row.get("closed_at")
    d["age_s"] = round(time.time() - view.opened_at, 1) if view.opened_at else None
    return _clean(d)


def suppression_from_row(row: dict) -> dict:
    view = SuppressionView(
        ts=float(row.get("ts") or 0.0),
        panel_key=row.get("panel_key") or "",
        joint_key=row.get("joint_key"),
        mode=row.get("mode"),
        reason=row.get("reason") or "",
        detail=_jload(row.get("detail"), {}),
    )
    d = view.to_dict()
    d["id"] = row.get("id")
    d["mode_label"] = mode_label(row.get("mode"))
    return _clean(d)


def channel_meta(name: str) -> dict:
    try:
        c = channels.get(name)
        return {"channel": c.name, "unit": c.unit, "label": c.label_tr,
                "decimals": c.decimals, "lo": c.lo, "hi": c.hi, "source": c.source,
                "kind": c.kind, "known": True}
    except Exception:  # noqa: BLE001
        return {"channel": name, "unit": "", "label": name, "decimals": 2,
                "lo": None, "hi": None, "source": "", "kind": "derived",
                "known": False}


def decode_block(regs, base: int, words: list[int]) -> list[dict]:
    out: list[dict] = []
    for r in regs:
        raw_words = words[r.offset:r.offset + r.words]
        if len(raw_words) < r.words:
            continue
        raw = raw_words[0] if r.words == 1 else (
            (raw_words[0] << 16) | raw_words[1])
        entry = {
            "name": r.name,
            "pdu": base + r.offset,
            "modicon_4x": 40001 + base + r.offset,
            "type": r.rtype,
            "words": r.words,
            "raw": raw,
            "eng": _num(round(icd.decode(r, raw_words), 4)),
            "unit": r.unit,
            "label_tr": r.label_tr,
            "note": r.note,
        }
        if r.rtype == "bits":
            bits = {"STATUS_WORD": icd.STATUS_BITS, "ARC_STATE": icd.ARC_BITS,
                    "DEVICE_FAULT_MAP": icd.DEVICE_FAULT_BITS,
                    "ENGINE_STATE": icd.ENGINE_BITS}.get(r.name)
            if bits:
                entry["flags"] = icd.unpack_bits(bits, raw)
        out.append(entry)
    return out


# --------------------------------------------------------------------------
# The RANDBETWEEN proof
# --------------------------------------------------------------------------

def supplied_data_analysis() -> dict:
    """The supplied "Akim Sensoru" sheet is synthetic, and here is the proof.

    Every number comes from :data:`panogoz.sim.load.SUPPLIED_SHEET_STATS`, which
    is the measured moment set of the actual sheet.  The point of putting it
    behind an endpoint is that the claim is checkable rather than asserted in a
    slide: each test names the statistic, the observed value, what a real feeder
    would give, and the verdict.
    """
    from panogoz.sim.load import SUPPLIED_SHEET_STATS as S

    tests = [
        {"key": "acf_1", "test_tr": "Gecikme-1 otokorelasyon",
         "observed": S["acf_1"], "expected_real": "> +0.97",
         "expected_random": "~ 0.00", "verdict": "SENTETIK",
         "why_tr": "Gerçek bir 15 dakikalık fider akımı komşu örnekle neredeyse "
                   "aynıdır. +0.0003 hafızasızlıktır."},
        {"key": "var_ratio", "test_tr": "var(fark)/var(seri)",
         "observed": S["var_ratio"], "expected_real": "< 0.1",
         "expected_random": "2.0000", "verdict": "SENTETIK",
         "why_tr": "Beyaz gürültü için tam olarak 2. Ölçülen 2.0023."},
        {"key": "excess_kurtosis", "test_tr": "Fazla basıklık",
         "observed": S["excess_kurtosis"], "expected_real": "> 0",
         "expected_random": "-1.2000 (ayrık düzgün)", "verdict": "SENTETIK",
         "why_tr": "-1.2129, düzgün dağılımın imzasıdır; yük eğrisinin değil."},
        {"key": "ks", "test_tr": "Kolmogorov-Smirnov, U(14.5, 90.5)",
         "observed": S["ks_d"], "critical": S["ks_crit"],
         "expected_real": "D >> kritik", "expected_random": "D < kritik",
         "verdict": "SENTETIK",
         "why_tr": f"D = {S['ks_d']} < kritik {S['ks_crit']}: düzgün dağılım reddedilemiyor."},
        {"key": "chi2", "test_tr": "Ki-kare düzgünlük (76 tamsayı)",
         "observed": S["chi2"], "df": S["chi2_df"], "p": S["chi2_p"],
         "expected_real": "p < 0.001", "expected_random": "p ~ 0.5",
         "verdict": "SENTETIK",
         "why_tr": "chi2 = 76.00, df = 75, p = 0.446. Kusursuz düzgünlük."},
        {"key": "day_shape_r", "test_tr": "Aynı saatte gün-güne şekil korelasyonu",
         "observed": S["day_shape_r"], "expected_real": "> +0.85",
         "expected_random": "~ 0.00", "verdict": "SENTETIK",
         "why_tr": "Bir fider her sabah aynı şeyi yapar. Bu veri yapmıyor."},
        {"key": "anova", "test_tr": "Saate göre ANOVA",
         "observed": S["anova_f"], "df": [23, 128], "p": S["anova_p"],
         "expected_real": "p < 1e-9", "expected_random": "p > 0.05",
         "verdict": "SENTETIK",
         "why_tr": "F(23,128) = 1.375, p = 0.135: günün saati hiçbir şey açıklamıyor."},
    ]
    return {
        "baslik_tr": "Verilen 'Akım Sensörü' sayfası =RANDBETWEEN(15;90) ile üretilmiştir",
        "ozet_tr": (
            "152 satır, 15 dakika aralık. Yedi bağımsız test aynı sonucu veriyor: "
            "bu bir ölçüm değil, düzgün dağılımlı sözde-rastgele sayı dizisidir. "
            "Bunu söylüyoruz çünkü bir erken uyarı sistemi, üzerine kurulduğu "
            "verinin ne olduğunu bilmek zorundadır."
        ),
        "n": int(S["n"]),
        "interval_min": 15,
        "span_h": round(S["n"] * 0.25, 2),
        "tests": tests,
        "verdict": "SENTETIK",
        "ma_stats": {"min": S["ma_min"], "max": S["ma_max"], "mean": S["ma_mean"],
                     "median": S["ma_median"], "sd_sample": S["ma_sd"], "cv": S["ma_cv"]},
        "primary_stats": {"min": S["a_min"], "max": S["a_max"], "mean": S["a_mean"],
                          "sd": S["a_sd"], "note_tr": "mA x 6, sayfanın kendi formülü"},
        "scaling_contradiction": {
            "baslik_tr": "Sayfanın ölçekleme zinciri kendi içinde tutarsız",
            "header_chain_tr": "5 A -> 125 mA ara akım trafosu (40:1), TEDAŞ 2500/5 (500:1) "
                               "ile kaskad = 20000:1 = 20.0 A/mA",
            "formula_chain_tr": "Uygulanan formül 600000/100 = 6000 = 6.0 A/mA",
            "ratio": round(20.0 / 6.0, 4),
            "full_scale_check_tr": "125 mA x 6.0 = 750 A; sayfanın belirttiği tam skala 600 A",
            "verdict_tr": "İki zincir 3.33 kat farklıdır. En az biri yanlıştır.",
        },
        "loading_context": {
            "panel_rated_a": assets.MAIN_BUSBAR_RATED_A,
            "min_pct_of_rating": round(100.0 * S["a_min"] / assets.MAIN_BUSBAR_RATED_A, 2),
            "max_pct_of_rating": round(100.0 * S["a_max"] / assets.MAIN_BUSBAR_RATED_A, 2),
            "note_tr": ("Tüm veri kümesi panonun anma akımının %3.9 - %23.4 aralığında "
                        "kalıyor. Aşırı yük yok, tepe yok, anomali yok: bu veriden "
                        "öğrenilecek bir arıza imzası yoktur."),
        },
        "what_we_did_tr": (
            "Veriyi atmadık, ne olduğunu söyledik ve yerine belgelere dayalı bir "
            "fiziksel simülatör koyduk: TEDAŞ-MLZ/2003-06.B panosu, 2312 A ana bara, "
            "gerçek yük/hava profili, ve bilinen kusur senaryoları. Simülatörün "
            "istatistikleri tests/test_sim_acceptance.py içinde ölçülüyor."
        ),
    }


# --------------------------------------------------------------------------
# Static files with a friendly fallback
# --------------------------------------------------------------------------

PLACEHOLDER_HTML = """<!doctype html>
<html lang="tr"><head><meta charset="utf-8">
<title>PANO GÖZ</title>
<style>
 body{margin:0;font:15px/1.6 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;
      background:#0d1117;color:#c9d1d9;padding:48px}
 code{background:#161b22;padding:2px 6px;border-radius:4px;color:#79c0ff}
 a{color:#58a6ff} h1{font-size:24px;margin:0 0 4px} h2{font-size:15px;margin:28px 0 8px;
 color:#8b949e;text-transform:uppercase;letter-spacing:.08em}
 li{margin:3px 0}
</style></head><body>
<h1>PANO GÖZ</h1>
<p>Pano/hücre içi anomali erken uyarı sistemi &mdash; API ayakta.</p>
<p><strong>frontend/index.html bulunamadı.</strong> Arayüz henüz yerleştirilmemiş;
API ve SCADA tarafı çalışıyor.</p>
<h2>Deneyin</h2>
<ul>
<li><a href="/api/health">/api/health</a></li>
<li><a href="/api/fleet">/api/fleet</a></li>
<li><a href="/api/panel/SOKE-14">/api/panel/SOKE-14</a></li>
<li><a href="/api/panel/SOKE-14/twin">/api/panel/SOKE-14/twin</a></li>
<li><a href="/api/alarms">/api/alarms</a></li>
<li><a href="/api/suppressions">/api/suppressions</a></li>
<li><a href="/api/scada/registers?panel=SOKE-14">/api/scada/registers?panel=SOKE-14</a></li>
<li><a href="/api/icd">/api/icd</a> &middot; <a href="/api/icd.csv">/api/icd.csv</a></li>
<li><a href="/api/analysis/supplied-data">/api/analysis/supplied-data</a></li>
<li><a href="/docs">/docs</a> (OpenAPI)</li>
</ul>
</body></html>"""


class UiFiles(StaticFiles):
    """Serve ``frontend/`` at ``/``, and say something useful when it is empty.

    Caching is disabled deliberately.  This is an on-premise appliance serving a
    handful of operators over a LAN, so the bandwidth saved by caching is
    irrelevant, while a browser holding a stale bundle after an update is a real
    failure mode - and one that is very hard to diagnose from the operator's
    side, because the page looks fine and simply behaves like the old version.
    """

    async def get_response(self, path: str, scope):  # type: ignore[override]
        try:
            resp = await super().get_response(path, scope)
        except Exception:  # noqa: BLE001 - StaticFiles raises HTTPException(404)
            if path in ("", ".", "index.html"):
                return HTMLResponse(PLACEHOLDER_HTML, status_code=200)
            raise
        resp.headers["Cache-Control"] = "no-store, must-revalidate"
        return resp


# --------------------------------------------------------------------------
# Application
# --------------------------------------------------------------------------

def create_app(runtime: Runtime) -> FastAPI:
    app = FastAPI(
        title="PANO GÖZ API",
        version=VERSION,
        description=("TEDAŞ 1600 kVA AG dağıtım panosu için pano içi anomali "
                     "erken uyarı sistemi. " + IEC62443_NOTE),
    )
    app.state.runtime = runtime
    app.state.started_at = time.time()

    # --- IEC 62443 ZONE BOUNDARY -----------------------------------------
    # In production the conduit terminates here: mTLS + RBAC in the reverse
    # proxy in front of this app; everything below is inside the OT zone.
    app.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_credentials=False,
        allow_methods=["*"], allow_headers=["*"],
    )

    rt = runtime

    def need_panel(panel_key: str) -> str:
        key = rt.resolve(panel_key)
        if key is None:
            raise HTTPException(status_code=404, detail={
                "error": "panel_not_found",
                "panel_key": panel_key,
                "message_tr": f"'{panel_key}' adlı pano yok.",
                "known": [p.panel_key for p in rt.fleet().panels][:20],
            })
        return key

    # ------------------------------------------------------------ health --

    @app.get("/api/health")
    def health() -> dict:
        st = rt.stats()
        return _clean({
            "ok": True,
            "version": VERSION,
            "uptime_s": round(time.time() - app.state.started_at, 1),
            "bus": st["bus"],
            "store": rt.store.stats(),
            "stats": st,
            "sim_running": bool(st["running"]),
            "panels": st["panels"],
            "demo_panel": DEMO_PANEL,
            "degraded": st["degraded"],
            "security_note": IEC62443_NOTE,
        })

    # ------------------------------------------------------------- fleet --

    @app.get("/api/fleet")
    def fleet() -> dict:
        f = rt.fleet()
        return _clean({
            "ts": f.ts,
            "heartbeat": f.heartbeat,
            "detector_lag_s": round(f.detector_lag_s, 2),
            "engine_flags": f.engine_flags,
            "dispatch_queue": f.dispatch_queue,
            "suppressed_24h": f.suppressed_24h,
            "panel_count": len(f.panels),
            "panels": [panel_summary(p) for p in f.panels],
        })

    @app.get("/api/panel/{panel_key}")
    def panel(panel_key: str) -> dict:
        key = need_panel(panel_key)
        live = rt.panel(key)
        d = live.to_dict()
        # The rules layer hangs its reasoning on the live object with setattr,
        # so it does not survive asdict().  Read it back through the accessors
        # rather than letting the UI guess why a severity is what it is.
        try:
            from panogoz.rules import fusion, pipeline, suppression
            d["reasoning"] = _clean(pipeline.summary(live))
            d["fusion_detail"] = _clean(fusion.detail(live))
            d["device_orders"] = suppression.device_orders(live)
        except Exception as exc:  # noqa: BLE001
            d["reasoning"] = {"error": repr(exc)}
        # "When could you have told me?" is not the changepoint - see
        # Runtime.first_alarm_day. Both dates are published, labelled.
        if live.theta_max_joint:
            d["onset"] = rt.first_alarm_day(key, live.theta_max_joint)
            d["onset"]["note_tr"] = (
                "changepoint_days_ago kusurun NE ZAMAN BAŞLADIĞININ kestirimidir "
                "ve doğrusal bir rampada BIC adım uydurması rampanın ortasına "
                "kaydığı için geç taraftan yanlıdır. cusum_first_days_ago "
                "kanıtın NE ZAMAN YETERLİ HÂLE GELDİĞİDİR; operatöre "
                "verilebilecek tarih budur.")
        d["flag_notes"] = flag_notes(live)
        d["scenarios_active"] = [
            {k: v for k, v in rec.items() if k != "describe"}
            for rec in rt.injected if rec["panel_key"] == key
        ]
        return _clean(d)

    # -------------------------------------------------------------- twin --

    @app.get("/api/panel/{panel_key}/twin")
    def twin(panel_key: str) -> dict:
        key = need_panel(panel_key)
        live = rt.panel(key)
        by_key = {j.key: j for j in live.joints}
        dev_by_key = {d.key: d for d in live.devices}
        return _clean({
            "panel": assets.panel_summary(),
            "panel_key": key,
            "geometry": {
                "w_mm": assets.PANEL_W_MM,
                "h_mm": assets.PANEL_H_MM,
                "d_mm": assets.PANEL_D_MM,
                "cable_compartment_min_mm": assets.CABLE_COMPARTMENT_MIN_MM,
                "busbar_terminal_pitch_mm": assets.BUSBAR_TERMINAL_PITCH_MM,
                "busbar_clear_gap_mm": assets.BUSBAR_CLEAR_GAP_MM,
                "feeder_pitch_mm": 100.0,
                "zones": {
                    "bottom": {"y0": 0, "y1": 700,
                               "label_tr": "Kablo bölmesi · gün-1 kiti burada"},
                    "instrument": {"y0": 700, "y1": 1040,
                                   "label_tr": "Ölçü kolonu · DIN ray, 10 A priz"},
                    "busbar": {"y0": 1040, "y1": 1440,
                               "label_tr": "Bara bölmesi · enerjisiz kalmadan erişilemez"},
                    "roof": {"y0": 1440, "y1": 1500,
                             "label_tr": "Çatı giriş pencereleri · 2312 A"},
                },
                "phase_colours": assets.PHASE_COLOURS,
                "note_tr": ("Koordinatlar EK-II/14 önden görünüşünden, mm. Sol alt köşe "
                            "orijindir. Sadece 'bottom' bölgesi gün-1'de enstrümanlıdır."),
            },
            "feeders": [
                {"index": f.index, "key": f.key, "name": f.name, "rated_a": f.rated_a,
                 "busono_boy": f.busono_boy, "spare": f.spare, "x_mm": f.x_mm}
                for f in assets.FEEDERS
            ],
            "joints": [
                {
                    "key": j.key, "label": j.label, "zone": j.zone,
                    "conductor": j.conductor, "feeder_index": j.feeder_index,
                    "rated_a": j.rated_a, "x_mm": j.x_mm, "y_mm": j.y_mm,
                    "sibling_group": (f"{j.zone}:N" if j.conductor == "N"
                                      else (f"{j.zone}:F{j.feeder_index:02d}"
                                            if j.feeder_index is not None
                                            else f"{j.zone}:GIRIS")),
                    "monitored": j.zone in assets.MONITORED_ZONES,
                    "live": (by_key[j.key].to_dict() if j.key in by_key else None),
                }
                for j in assets.JOINTS
            ],
            "devices": [
                {
                    "key": d.key, "kind": d.kind, "label": d.label, "zone": d.zone,
                    "mount": d.mount, "x_mm": d.x_mm, "y_mm": d.y_mm,
                    "covers": list(d.covers), "battery": d.battery,
                    "live": (dev_by_key[d.key].to_dict() if d.key in dev_by_key else None),
                }
                for d in assets.DEVICES
            ],
            "counts": {
                "joints_total": len(assets.JOINTS),
                "joints_monitored": len(assets.monitored_joints()),
                "devices": assets.DEVICES_PER_PANEL,
                "bottom_lugs": sum(1 for j in assets.JOINTS if j.zone == "bottom"),
                "busbar_joints": sum(1 for j in assets.JOINTS if j.zone == "busbar"),
                "roof_stubs": sum(1 for j in assets.JOINTS if j.zone == "roof"),
            },
        })

    # ------------------------------------------------------------- trend --

    @app.get("/api/panel/{panel_key}/trend")
    def trend(panel_key: str, joint: str | None = None,
              channel: str = "det.theta_k", hours: float = 168.0,
              limit: int = Query(default=20000, ge=1, le=200000)) -> dict:
        key = need_panel(panel_key)
        now = rt.now()
        since = now - max(0.0, float(hours)) * 3600.0
        meta = channel_meta(channel)
        if joint:
            series = rt.store.joint_series(key, joint, channel, since, now + 1, limit)
        else:
            series = rt.store.series(key, channel, since, now + 1, limit)
        # A missing joint or an unpopulated channel is an EMPTY CHART, never a
        # 500: a panel with no analyser genuinely has no mpr.* series, and the
        # UI must be able to say so with its axes still drawn.
        return _clean({
            **meta,
            "panel_key": key,
            "joint": joint,
            "hours": hours,
            "since": since,
            "until": now,
            "n": len(series),
            "series": [[t, _num(v)] for t, v in series],
            "empty_reason_tr": None if series else (
                "Bu kanal bu bağlantı için ölçülmüyor veya seçilen pencerede "
                f"kayıt yok. Ham örnekler {RAW_RETENTION_DAYS} gün saklanır; "
                "daha eskisi için günlük özet (/daily) ucunu kullanın."),
        })

    @app.get("/api/panel/{panel_key}/daily")
    def daily(panel_key: str, joint: str | None = None, days: int = 120) -> list:
        key = need_panel(panel_key)
        if not joint:
            live = rt.panel(key)
            joint = live.theta_max_joint or (
                assets.monitored_joints()[0].key if assets.monitored_joints() else "")
        rows = rt.store.joint_daily(key, joint, max(1, int(days)))
        out = []
        for r in sorted(rows, key=lambda x: x["day"]):
            out.append({
                "day": int(r["day"]),
                "date": time.strftime("%Y-%m-%d", time.gmtime(int(r["day"]) * DAY_S)),
                "ts": int(r["day"]) * DAY_S,
                "theta_med": _num(r.get("theta_med")),
                "theta_p90": _num(r.get("theta_p90")),
                "n": r.get("n"),
                "load_mean": _num(r.get("load_mean")),
                "sens_pct": _num(r.get("sens_pct")),
                # The CUSUM and the baseline it was measured against belong to
                # the daily table by construction: the statistic is defined over
                # daily medians, so there is no per-sample value anywhere. The
                # evidence screen plots this, which is why an operator can still
                # see the reasoning behind a decision after the raw samples have
                # been pruned.  Null on neutral lugs, which are judged by rule
                # H3 and never by a CUSUM.
                "cusum": _num(r.get("cusum")),
                "baseline": _num(r.get("baseline")),
                "theta_min": _num(r.get("theta_min")),
                "joint_key": joint,
            })
        return _clean(out)

    @app.get("/api/panel/{panel_key}/onset")
    def onset(panel_key: str, joint: str | None = None) -> dict:
        """When the defect started, and when the evidence became sufficient.

        Two different questions with two different answers, both replayed from
        ``joint_daily`` on demand so an auditor can re-derive them with a SELECT.
        """
        key = need_panel(panel_key)
        live = rt.panel(key)
        joint = joint or live.theta_max_joint or ""
        if not joint:
            # ``eta`` anahtari BURADA DA bulunur.  Arayuz alanin varligini
            # kontrol etmek zorunda kalmamali; bos bir EtaView "projeksiyon
            # yok" demenin sozlesmeye uygun halidir.
            return _clean({"panel_key": key, "joint_key": None, "days": 0,
                           "eta": EtaView().to_dict()})
        out = dict(rt.first_alarm_day(key, joint))
        # Ucun ucuncu zaman sorusu.  Ilk ikisi geriye bakiyor - bozulma ne zaman
        # BASLADI, kanit ne zaman YETERLI oldu.  Bu ileriye bakar ve ayni
        # joint_daily oynatmasindan cikar, bu yuzden ayri bir uc acilmiyor:
        # kanit ekrani ucunu tek istekle alir.
        jv = next((j for j in live.joints if j.key == joint), None)
        out["eta"] = jv.eta.to_dict() if jv is not None else EtaView().to_dict()
        return _clean(out)

    # -------------------------------------------------------------- PRPD --

    @app.get("/api/panel/{panel_key}/prpd")
    def prpd(panel_key: str) -> dict:
        key = need_panel(panel_key)
        row = rt.store.latest_prpd(key)
        if row is None:
            # Take one now rather than 404: the record is cheap and a judge who
            # clicks a panel should see its pattern, not an error.
            rt._make_prpd(key, rt.now())            # noqa: SLF001
            row = rt.store.latest_prpd(key)
        live = rt.panel(key)
        if row is None:
            return _clean({
                "panel_key": key, "ts": None, "klass": live.pd.klass,
                "label_tr": live.pd.klass_label, "features": {}, "hist": [],
                "n_phase": 64, "n_amp": 32, "caveat": live.pd.caveat,
                "empty_reason_tr": "PRPD modülü yüklenemedi; kayıt alınamadı.",
            })
        try:
            from panogoz.detector import prpd_classify as pc
            from panogoz.sim import prpd as pr
            hist = pr.unpack(row["hist"])
            sparse = [[int(p), int(a), int(hist[p][a])]
                      for p in range(hist.shape[0]) for a in range(hist.shape[1])
                      if hist[p][a]]
            feats = _jload(row.get("features"), {})
            klass = row.get("klass") or live.pd.klass
            sev = pc.severity(klass, live.pd.qmax_db, live.pd.trend_db_30d,
                              live.pd.rate_per_s)
            explain = pc.classify(feats) if feats else {}
            return _clean({
                "panel_key": key,
                "ts": row["ts"],
                "device": row.get("device", "PD-01"),
                "klass": klass,
                "label_tr": channels.PRPD_LABELS_TR.get(klass, klass),
                "severity": sev,
                "severity_label": channels.SEVERITY_TR.get(sev, sev),
                "features": feats,
                "feature_labels_tr": pc.FEATURE_LABELS_TR,
                "explain_tr": explain.get("explain_tr", ""),
                "rule": explain.get("rule", ""),
                "confidence": explain.get("confidence"),
                "hist": sparse,
                "n_phase": int(hist.shape[0]),
                "n_amp": int(hist.shape[1]),
                "deg_per_phase_bin": pr.DEG_PER_PHASE_BIN,
                "db_per_amp_bin": pr.DB_PER_AMP_BIN,
                "cycles": pr.DEFAULT_CYCLES,
                "live": live.pd.to_dict(),
                "caveat": live.pd.caveat,
            })
        except Exception as exc:  # noqa: BLE001
            return _clean({
                "panel_key": key, "ts": row.get("ts"), "klass": row.get("klass"),
                "label_tr": "", "features": {}, "hist": [], "n_phase": 64,
                "n_amp": 32, "caveat": live.pd.caveat, "error": repr(exc),
            })

    # ------------------------------------------------------------ alarms --

    @app.get("/api/alarms")
    def alarms(state: str | None = "ACIK", panel: str | None = None,
               limit: int = Query(default=200, ge=1, le=2000)) -> list:
        if state and state.upper() in ("ALL", "HEPSI", "*"):
            state = None
        rows = rt.store.incidents(state=state, limit=limit)
        if panel:
            key = need_panel(panel)
            rows = [r for r in rows if r["panel_key"] == key]
        return [alarm_from_row(r) for r in rows]

    @app.post("/api/alarms/{incident_id}/ack")
    def ack(incident_id: int, body: dict = Body(default={})) -> dict:
        by = str(body.get("by") or "").strip()
        token = str(body.get("token") or "").strip()
        if not by:
            return {"ok": False, "reason": "Kim onayladığı belirtilmedi ('by' alanı boş)."}
        row = rt.store.one("SELECT * FROM incident WHERE id=?", (incident_id,))
        if row is None:
            raise HTTPException(status_code=404, detail={
                "error": "incident_not_found", "id": incident_id,
                "message_tr": f"{incident_id} numaralı olay yok."})
        ok = False
        reason = ""
        if rt.notifier is not None:
            # The notifier's ack is the operator path: it checks the rota AND
            # the token, because an acknowledgement that anyone can send is not
            # an acknowledgement.
            ok = bool(rt.notifier.ack(incident_id, by, token))
            if not ok:
                reason = ("Onay reddedildi: gönderen nöbet listesinde değil veya "
                          "doğrulama kodu hatalı.")
        else:
            from panogoz.rules import pipeline as pl
            ok = bool(pl.get_manager(rt.store).ack(incident_id, by, token or None))
            reason = "" if ok else "Doğrulama kodu hatalı."
        if ok:
            rt.store.audit("api", "ack", str(incident_id), {"by": by})
            rt.store.commit()
            reason = "Onaylandı; tekrarlar durduruldu."
        fresh = rt.store.one("SELECT * FROM incident WHERE id=?", (incident_id,))
        return _clean({"ok": ok, "reason": reason,
                       "incident": alarm_from_row(fresh) if fresh else None})

    # ------------------------------------------------------ suppressions --

    @app.get("/api/suppressions")
    def suppressions(hours: float = 24.0, panel: str | None = None,
                     limit: int = Query(default=500, ge=1, le=5000),
                     group: bool = True) -> list:
        """Every alarm we deliberately did not raise, with its reason.

        Rolled up by (panel, joint, reason) by default.  The rules layer writes
        one row per suppressed candidate per evaluation, so a panel that has sat
        below the detectability floor all afternoon contributes hundreds of
        identical rows - true, and useless to read.  Grouping keeps the screen
        the operator actually opens legible while ``count`` and ``first_ts``
        preserve exactly how long and how often, and ``group=false`` returns the
        raw rows for an audit.
        """
        since = rt.now() - max(0.0, float(hours)) * 3600.0
        rows = rt.store.suppressions(since=since, limit=20000 if group else limit)
        if panel:
            key = need_panel(panel)
            rows = [r for r in rows if r["panel_key"] == key]
        if not group:
            return [suppression_from_row(r) for r in rows[:limit]]
        agg: dict[tuple, dict] = {}
        for r in rows:                      # newest first out of the store
            k = (r.get("panel_key"), r.get("joint_key"), r.get("reason"))
            hit = agg.get(k)
            if hit is None:
                hit = suppression_from_row(r)
                hit["count"] = 0
                hit["first_ts"] = r.get("ts")
                hit["last_ts"] = r.get("ts")
                agg[k] = hit
            hit["count"] += 1
            hit["first_ts"] = min(hit["first_ts"], r.get("ts") or hit["first_ts"])
        out = sorted(agg.values(), key=lambda d: (-d["count"], -(d["ts"] or 0)))
        for d in out:
            d["span_h"] = round(((d["last_ts"] or 0) - (d["first_ts"] or 0)) / 3600.0, 2)
        return _clean(out[:limit])

    # ----------------------------------------------------------- devices --

    @app.get("/api/devices")
    def devices(panel: str | None = None) -> list:
        f = rt.fleet()
        panels = f.panels
        if panel:
            key = need_panel(panel)
            panels = [p for p in panels if p.panel_key == key]
            if not panels:
                panels = [rt.panel(key)]
        out = []
        for p in panels:
            for d in p.devices:
                row = d.to_dict()
                row["panel_key"] = p.panel_key
                row["panel_index"] = p.panel_index
                row["site"] = p.site
                spec = assets.DEVICES_BY_KEY.get(d.key)
                if spec is not None:
                    row["kind"] = spec.kind
                    row["mount"] = spec.mount
                    row["covers"] = list(spec.covers)
                    row["battery"] = spec.battery
                out.append(row)
        return _clean(out)

    # ------------------------------------------------------------- SCADA --

    @app.get("/api/scada/registers")
    def scada_registers(panel: str | None = None) -> dict:
        if rt.scada is None:
            raise HTTPException(status_code=503, detail={
                "error": "scada_unavailable",
                "message_tr": "Modbus slave başlatılamadı."})
        gwords = rt.scada.read(icd.GLOBAL_BASE, icd.GLOBAL_SIZE)
        out: dict[str, Any] = {
            "icd_version": icd.ICD_VERSION,
            "global": {
                "base": icd.GLOBAL_BASE,
                "size": icd.GLOBAL_SIZE,
                "words": gwords,
                "decoded": decode_block(icd.GLOBAL_REGS, icd.GLOBAL_BASE, gwords),
            },
            "panel": None,
            "poll_stats": rt.scada.poll_stats,
            "panel_base": icd.PANEL_BASE,
            "regs_per_panel": icd.REGS_PER_PANEL,
            "max_panels": icd.MAX_PANELS,
            "stale_after_s": icd.STALE_AFTER_S,
        }
        key = panel or DEMO_PANEL
        resolved = rt.resolve(key)
        if resolved is None:
            raise HTTPException(status_code=404, detail={
                "error": "panel_not_found", "panel_key": key,
                "message_tr": f"'{key}' adlı pano yok."})
        live = rt.panel(resolved)
        base = icd.panel_base(live.panel_index)
        pwords = rt.scada.read(base, icd.REGS_PER_PANEL)
        out["panel"] = {
            "panel_key": resolved,
            "panel_index": live.panel_index,
            "base": base,
            "modicon_4x": 40001 + base,
            "size": icd.REGS_PER_PANEL,
            "words": pwords,
            "decoded": decode_block(icd.PANEL_REGS, base, pwords),
        }
        out["modpoll"] = rt.scada.modpoll_commands(live.panel_index, "127.0.0.1")
        return _clean(out)

    @app.get("/api/icd", response_class=PlainTextResponse)
    def icd_markdown() -> Response:
        doc = DOCS_DIR / "PANOGOZ-ICD-v2.0.md"
        text = doc.read_text(encoding="utf-8") if doc.exists() else icd.to_markdown()
        return Response(content=text, media_type="text/markdown; charset=utf-8")

    @app.get("/api/icd.csv", response_class=PlainTextResponse)
    def icd_csv() -> Response:
        doc = DOCS_DIR / "panogoz_points.csv"
        text = doc.read_text(encoding="utf-8") if doc.exists() else icd.to_csv()
        return Response(
            content=text, media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="panogoz_points.csv"'},
        )

    # ----------------------------------------------------- notifications --

    @app.get("/api/notifications")
    def notifications(limit: int = Query(default=50, ge=1, le=1000),
                      incident_id: int | None = None) -> list:
        rows = rt.store.notifications(incident_id=incident_id, limit=limit)
        out = []
        for r in rows:
            out.append({
                "id": r.get("id"),
                "incident_id": r.get("incident_id"),
                "ts": r.get("ts"),
                "channel": r.get("channel"),
                "target": r.get("target"),
                "body": r.get("body"),
                "state": r.get("state"),
                "transcript": r.get("transcript") or "",
            })
        return _clean(out)

    # -------------------------------------------------------- scenarios ---

    @app.get("/api/scenarios")
    def scenarios() -> list:
        out = []
        for key, spec in sorted(fx.SCENARIOS.items(),
                                key=lambda kv: (not kv[1]["expect_alarm"], kv[0])):
            out.append({
                "key": key,
                "label_tr": spec["label_tr"],
                "description_tr": spec["description_tr"],
                "expect_alarm": bool(spec["expect_alarm"]),
                "kind": spec["kind"],
                "expect_mode": spec.get("expect_mode"),
                "expect_mode_label": mode_label(spec.get("expect_mode")),
                "forbid_modes": list(spec.get("forbid_modes") or []),
                "default_kw": {k: v for k, v in spec["default_kw"].items()},
                "notes_tr": spec.get("notes_tr", ""),
            })
        return _clean(out)

    @app.post("/api/scenario/{key}")
    def inject(key: str, body: dict = Body(default={})) -> dict:
        panel_key = str(body.pop("panel_key", "") or DEMO_PANEL)
        resolved = rt.resolve(panel_key)
        if resolved is None:
            raise HTTPException(status_code=404, detail={
                "error": "panel_not_found", "panel_key": panel_key,
                "message_tr": f"'{panel_key}' adlı pano yok."})
        if key not in fx.SCENARIOS:
            raise HTTPException(status_code=404, detail={
                "error": "scenario_not_found", "scenario": key,
                "message_tr": f"'{key}' adlı senaryo yok.",
                "known": sorted(fx.SCENARIOS)})
        try:
            rec = rt.inject(resolved, key, **body)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail={
                "error": "inject_failed", "message_tr": str(exc)}) from exc
        return _clean({
            "ok": True,
            "injected": rec,
            "note_tr": ("Senaryo simülatöre uygulandı. Etkisi bir sonraki dedektör "
                        f"geçişinde ({DETECT_PERIOD_S:.0f} s) görünür; ısıl senaryolarda "
                        "bağlantının zaman sabiti kadar (~15 dk) gecikir."),
        })

    @app.post("/api/demo/reset")
    def demo_reset() -> dict:
        t0 = time.time()
        rt.reset()
        return _clean({"ok": True, "elapsed_s": round(time.time() - t0, 1),
                       "panels": len(rt.fleet().panels),
                       "message_tr": "Demo başlangıç durumuna döndürüldü."})

    @app.post("/api/demo/clear-faults")
    def demo_clear(panel: str | None = None) -> dict:
        n = rt.clear_faults(panel)
        return {"ok": True, "cleared_panels": n}

    # ------------------------------------------------------------ audit ---

    @app.get("/api/audit/verify")
    def audit_verify() -> dict:
        res = rt.store.verify_chain()
        return _clean({
            **res,
            "algorithm": "sha256(prev_hash|ts|actor|action|subject|detail)",
            "message_tr": ("Denetim zinciri bütünlüğü doğrulandı."
                           if res["ok"] else
                           f"Zincir {res['broken_at']} numaralı satırda kırılmış."),
        })

    @app.get("/api/audit")
    def audit_rows(limit: int = Query(default=100, ge=1, le=2000)) -> list:
        return _clean(rt.store.query(
            "SELECT id, ts, actor, action, subject, detail, hash FROM audit "
            "ORDER BY id DESC LIMIT ?", (limit,)))

    # --------------------------------------------------------- analysis ---

    @app.get("/api/analysis/supplied-data")
    def supplied_data() -> dict:
        return _clean(supplied_data_analysis())

    # --------------------------------------------------------------- ws ---

    @app.websocket("/ws")
    async def ws(sock: WebSocket) -> None:
        await sock.accept()
        watched: str | None = None
        last_alarm_id = 0
        rows = rt.store.incidents(limit=1)
        if rows:
            last_alarm_id = int(rows[0]["id"])
        try:
            while True:
                # Non-blocking read: the client may send {"panel": "SOKE-14"}
                # at any time to switch which panel it wants pushed.
                try:
                    raw = await asyncio.wait_for(sock.receive_text(), timeout=WS_PERIOD_S)
                    try:
                        msg = json.loads(raw)
                    except Exception:  # noqa: BLE001
                        msg = {"panel": raw.strip()}
                    if isinstance(msg, dict) and msg.get("panel"):
                        watched = rt.resolve(str(msg["panel"]))
                except asyncio.TimeoutError:
                    pass
                except WebSocketDisconnect:
                    return

                f = rt.fleet()
                await sock.send_text(json.dumps({
                    "type": "fleet",
                    "data": _clean({
                        "ts": f.ts, "heartbeat": f.heartbeat,
                        "detector_lag_s": round(f.detector_lag_s, 2),
                        "dispatch_queue": f.dispatch_queue,
                        "suppressed_24h": f.suppressed_24h,
                        "panels": [panel_summary(p) for p in f.panels],
                    }),
                }, ensure_ascii=False))

                if watched:
                    try:
                        live = rt.panel(watched)
                        await sock.send_text(json.dumps({
                            "type": "panel", "data": _clean(live.to_dict()),
                        }, ensure_ascii=False, default=str))
                    except KeyError:
                        watched = None

                fresh = [r for r in rt.store.incidents(limit=25)
                         if int(r["id"]) > last_alarm_id]
                if fresh:
                    last_alarm_id = max(int(r["id"]) for r in fresh)
                    for r in reversed(fresh):
                        await sock.send_text(json.dumps({
                            "type": "alarm", "data": alarm_from_row(r),
                        }, ensure_ascii=False))
        except WebSocketDisconnect:
            return
        except Exception:  # noqa: BLE001 - a dead socket is not a server error
            return

    # ------------------------------------------------------------ static --

    FRONTEND_DIR.mkdir(parents=True, exist_ok=True)
    app.mount("/", UiFiles(directory=str(FRONTEND_DIR), html=True), name="ui")
    return app


# --------------------------------------------------------------------------
# Self-test
# --------------------------------------------------------------------------

if __name__ == "__main__":  # pragma: no cover
    import shutil
    import tempfile

    from fastapi.testclient import TestClient

    from panogoz.bus.bus import InProcBus

    print("=" * 78)
    print("PANO GOZ · API self-test")
    print("=" * 78)
    print()

    tmp = tempfile.mkdtemp(prefix="panogoz-api-")
    rt = Runtime(n_panels=6, seed=42, db_path=os.path.join(tmp, "api.db"),
                 backfill_days=18, scada_port=5097, bus=InProcBus(), quiet=True)
    try:
        t0 = time.time()
        rt.bootstrap()
        rt.start()
        time.sleep(3.0)
        print(f"runtime up in {time.time() - t0:.1f} s")
        app = create_app(rt)
        c = TestClient(app)

        def show(method: str, path: str, **kw) -> Any:
            r = c.request(method, path, **kw)
            ctype = r.headers.get("content-type", "")
            body = r.json() if ctype.startswith("application/json") else r.text
            size = f"{len(body)} satir" if isinstance(body, list) else f"{len(r.content)} B"
            print(f"  {r.status_code}  {method:<4} {path:<52} {size}")
            return r, body

        print()
        print("1. every documented endpoint answers")
        r, health_body = show("GET", "/api/health")
        assert r.status_code == 200 and health_body["ok"]
        r, fleet_body = show("GET", "/api/fleet")
        assert r.status_code == 200 and fleet_body["panels"]
        r, panel_body = show("GET", f"/api/panel/{DEMO_PANEL}")
        assert r.status_code == 200 and panel_body["panel_key"] == DEMO_PANEL
        r, twin_body = show("GET", f"/api/panel/{DEMO_PANEL}/twin")
        assert len(twin_body["devices"]) == 9, "the digital twin draws exactly 9 dots"
        assert len(twin_body["joints"]) == len(assets.JOINTS)
        show("GET", f"/api/panel/{DEMO_PANEL}/trend?joint=C07-L2-PABUC&channel=det.theta_k&hours=168")
        show("GET", f"/api/panel/{DEMO_PANEL}/daily?joint=C07-L2-PABUC&days=120")
        show("GET", f"/api/panel/{DEMO_PANEL}/prpd")
        show("GET", "/api/alarms?state=ACIK&limit=200")
        show("GET", "/api/suppressions?hours=24")
        show("GET", f"/api/devices?panel={DEMO_PANEL}")
        r, scada_body = show("GET", f"/api/scada/registers?panel={DEMO_PANEL}")
        show("GET", "/api/icd")
        show("GET", "/api/icd.csv")
        show("GET", "/api/notifications?limit=50")
        show("GET", "/api/scenarios")
        show("GET", "/api/audit/verify")
        show("GET", "/api/analysis/supplied-data")
        print()

        print("2. a bad panel key is a 404, a bad joint is an empty chart")
        r, body = show("GET", "/api/panel/YOK-99")
        assert r.status_code == 404
        r, body = show("GET", f"/api/panel/{DEMO_PANEL}/trend?joint=YOK-99&channel=det.theta_k")
        assert r.status_code == 200 and body["series"] == [] and body["unit"]
        print(f"   empty series still carries unit '{body['unit']}' and label "
              f"'{body['label']}'")
        r, body = show("GET", f"/api/panel/{DEMO_PANEL}/trend?channel=mpr.no_such_channel")
        assert r.status_code == 200
        print(f"   lower-case key resolves: "
              f"{c.get('/api/panel/soke-14').json()['panel_key']}")
        print()

        print("3. SCADA block agrees with the panel object")
        base = scada_body["panel"]["base"]
        dec = {d["name"]: d for d in scada_body["panel"]["decoded"]}
        live_panel = c.get(f"/api/panel/{DEMO_PANEL}").json()
        print(f"   base PDU {base} (= {icd.PANEL_BASE} + {icd.REGS_PER_PANEL} x "
              f"{live_panel['panel_index'] - 1})")
        print(f"   PANEL_ID       {dec['PANEL_ID']['eng']:>8.0f}   "
              f"live {live_panel['panel_index']}")
        print(f"   HEALTH_INDEX   {dec['HEALTH_INDEX']['eng']:>8.1f}   "
              f"live {live_panel['health_index']:.1f}")
        print(f"   THETA_MAX      {dec['THETA_MAX']['eng']:>8.2f}   "
              f"live {live_panel['theta_max']:.2f}")
        print(f"   STATUS_WORD    {dec['STATUS_WORD']['raw']:>8}   "
              f"{dec['STATUS_WORD'].get('flags')}")
        assert base == icd.panel_base(live_panel["panel_index"])
        assert abs(dec["THETA_MAX"]["eng"] - live_panel["theta_max"]) <= 0.06
        print()

        print("4. the RANDBETWEEN proof")
        proof = c.get("/api/analysis/supplied-data").json()
        print(f"   {proof['baslik_tr']}")
        for t in proof["tests"]:
            obs = t.get("observed")
            print(f"     {t['test_tr']:<42} {obs:>10}  -> {t['verdict']}")
        print(f"   scaling: {proof['scaling_contradiction']['verdict_tr']}")
        assert proof["verdict"] == "SENTETIK"
        print()

        print("5. scenario injection over HTTP")
        r, body = show("POST", "/api/scenario/ark_olayi",
                       json={"panel_key": DEMO_PANEL})
        assert r.status_code == 200 and body["ok"]
        print(f"   {body['injected']['label_tr']} -> {DEMO_PANEL}")
        r, body = show("POST", "/api/scenario/yok_boyle_bir_sey", json={})
        assert r.status_code == 404
        print()

        print("6. acknowledgement needs a real token")
        rows = rt.store.incidents(limit=5)
        if rows:
            inc = rows[0]
            r, body = show("POST", f"/api/alarms/{inc['id']}/ack",
                           json={"by": "Nöbetçi tekniker · Söke", "token": "0000"})
            print(f"   wrong token -> ok={body['ok']}  {body['reason']}")
            from panogoz.notify.escalation import ack_token
            good = ack_token(int(inc["id"]))
            r, body = show("POST", f"/api/alarms/{inc['id']}/ack",
                           json={"by": "Nöbetçi tekniker · Söke", "token": good})
            print(f"   right token -> ok={body['ok']}  {body['reason']}")
        else:
            print("   no open incident in this short run; ack path exercised by tests")
        print()

        print("7. websocket push")
        with c.websocket_connect("/ws") as sock:
            sock.send_text(json.dumps({"panel": DEMO_PANEL}))
            kinds = []
            for _ in range(3):
                msg = json.loads(sock.receive_text())
                kinds.append(msg["type"])
                if msg["type"] == "fleet":
                    print(f"   fleet frame: {len(msg['data']['panels'])} panels, "
                          f"heartbeat {msg['data']['heartbeat']}")
                elif msg["type"] == "panel":
                    print(f"   panel frame: {msg['data']['panel_key']} "
                          f"HI {msg['data']['health_index']:.1f}")
            assert "fleet" in kinds
        print()

        print("8. static root falls back when the UI is not built yet")
        r = c.get("/")
        print(f"   GET /  -> {r.status_code}, {len(r.text)} B, "
              f"{'index.html' if 'PANO' in r.text and 'bulunamad' not in r.text else 'placeholder'}")
        assert r.status_code == 200
        print()
        print("API self-test PASSED")
    finally:
        try:
            rt.stop()
            rt.store.close()
        except Exception:
            pass
        shutil.rmtree(tmp, ignore_errors=True)
