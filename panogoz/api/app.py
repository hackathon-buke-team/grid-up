"""Merkezi monitoring API'si: demo filosunun tam zaman serisini JSON olarak sunar.

Yarışma brifi "operasyon ekiplerinin anlık durumu, anomalileri ve alarmları takip
edebileceği bir izleme altyapısı" istiyor. Bu API, panogoz/sim + detector + rules
çekirdeğinin ürettiği gerçek/sentetik veriyi frontend/'e servis eder.
"""
from __future__ import annotations

from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

from panogoz.api.fleet_routes import register_fleet_routes
from panogoz.api.fleet_service import FleetService
from panogoz.contracts.channels import Phase
from panogoz.detector.cusum import cusum_changepoint, daily_median_series
from panogoz.detector.flags import Flag, flags_for_connection
from panogoz.rules.engine import Severity
from panogoz.sim.ct_data import SAMPLE_PERIOD_S
from panogoz.sim.demo_fleet import (
    RATED_CURRENT_A,
    ConnectionTimeline,
    build_cusum_demo_connection,
    build_demo_fleet,
)

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"

SEVERITY_LABELS = {
    Severity.NORMAL: "NORMAL",
    Severity.WARNING: "UYARI",
    Severity.ALARM: "ALARM",
    Severity.CRITICAL: "KRİTİK",
}


def _connection_summary(index: int, timeline: ConnectionTimeline) -> dict:
    last_theta = timeline.theta[-1]
    last_severity = timeline.severity[-1]
    last_thermal = timeline.three_phase[timeline.watched_phase][-1]
    return {
        "index": index,
        "connection_id": timeline.connection_id,
        "watched_phase": timeline.watched_phase.value,
        "sample_count": len(timeline.theta),
        "severity": last_severity.severity.name,
        "severity_label": SEVERITY_LABELS[last_severity.severity],
        "theta": last_theta.theta,
        "current_a": last_thermal.current_a,
        "surface_temp_c": last_thermal.surface_temp_c,
    }


def _connection_series(timeline: ConnectionTimeline) -> dict:
    watched = timeline.watched_phase
    return {
        "connection_id": timeline.connection_id,
        "t_s": [s.t_s for s in timeline.theta],
        "theta": [s.theta for s in timeline.theta],
        "severity": [int(e.severity) for e in timeline.severity],
        "current_a": [s.current_a for s in timeline.three_phase[watched]],
        "surface_temp_c": [s.surface_temp_c for s in timeline.three_phase[watched]],
    }


def _connection_flags(timeline: ConnectionTimeline, now_t_s: float | None) -> dict:
    """K4 4.3 -- expect_flags (STALE/SENSOR_DRIFT/DE_ENERGISED), bkz.
    panogoz.detector.flags. Bu demo verisi tek seferde onceden hesaplanmis
    tarihsel bir seri oldugu icin gercek bir 'simdi' kavrami yok -- `now_t_s`
    verilmezse son ornegin kendi zaman damgasi kullanilir (gap=0, asla stale
    degil); canli akan bir sistemde bu her zaman gercek duvar-saati olurdu."""
    watched = timeline.watched_phase
    last_theta = timeline.theta[-1]
    last_thermal = timeline.three_phase[watched][-1]
    effective_now = last_theta.t_s if now_t_s is None else now_t_s

    sensor_drift = False
    drift_note = None
    try:
        daily = daily_median_series(timeline.theta)
        result = cusum_changepoint(daily)
        sensor_drift = result.changepoint_day_index is not None
    except ValueError:
        drift_note = "yetersiz gunluk veri (CUSUM icin en az 31 gun gerekir, bu seri ~%.1f gun)" % (
            last_theta.t_s / 86400.0
        )

    flags = flags_for_connection(
        last_sample_t_s=last_theta.t_s,
        now_t_s=effective_now,
        period_s=SAMPLE_PERIOD_S,
        current_a=last_thermal.current_a,
        rated_current_a=RATED_CURRENT_A,
        sensor_drift_detected=sensor_drift,
    )
    return {
        "connection_id": timeline.connection_id,
        "flags": sorted(f.value for f in flags),
        "stale": Flag.STALE in flags,
        "de_energised": Flag.DE_ENERGISED in flags,
        "sensor_drift": Flag.SENSOR_DRIFT in flags,
        "sensor_drift_note": drift_note,
    }


def _cusum_payload(timeline: ConnectionTimeline) -> dict:
    """K3 3.2 -- CUSUM/değişim noktası. Gerçek sonucu döner; `baseline_days`
    (varsayılan 30) karşılanmıyorsa (mevcut demo filosunun ~1.6 günlük
    serisinde her zaman böyle) `available: false` + insan-okur bir not döner
    -- frontend bunu sahte bir eğriyle DEĞİL, dürüst bir mesajla göstermeli."""
    try:
        daily = daily_median_series(timeline.theta)
        result = cusum_changepoint(daily)
        return {
            "available": True,
            "note": None,
            "day_index": result.day_index,
            "s_pos": result.s_pos,
            "s_neg": result.s_neg,
            "h": result.h,
            "mu0": result.mu0,
            "sigma0": result.sigma0,
            "changepoint_day_index": result.changepoint_day_index,
        }
    except ValueError:
        last_theta = timeline.theta[-1]
        return {
            "available": False,
            "note": "yetersiz gunluk veri (CUSUM icin en az 31 gun gerekir, bu seri ~%.1f gun)"
            % (last_theta.t_s / 86400.0),
            "day_index": [],
            "s_pos": [],
            "s_neg": [],
            "h": None,
            "mu0": None,
            "sigma0": None,
            "changepoint_day_index": None,
        }


def _evidence_payload(timeline: ConnectionTimeline) -> dict:
    """K3 3.2 (Kanıt ekranı): θ serisi (zaten `/series`'te var, burada da
    tekrar edilir ki tek bir istekle tüm kanıt ekranı çizilebilsin) + kardeş
    faz karşılaştırması (üç fazın ham yüzey sıcaklığı/akımı -- θ zaten bu
    kardeş medyanına göre normalize ediyor, bkz. panogoz.detector.theta) +
    CUSUM. "Bastırma gerekçeleri" (CLAUDE.md Sec.2 dead-band/fırtına/7-gün
    kapanma) kasıtlı olarak burada YOK -- o katman repo'da henüz kurulmadı
    (yalnız basit eşik+debounce var, panogoz/rules/engine.py), ayrı bir
    gelecek görev."""
    siblings = {
        phase.value: {
            "t_s": [s.t_s for s in timeline.three_phase[phase]],
            "surface_temp_c": [s.surface_temp_c for s in timeline.three_phase[phase]],
            "current_a": [s.current_a for s in timeline.three_phase[phase]],
        }
        for phase in Phase
    }
    return {
        "connection_id": timeline.connection_id,
        "watched_phase": timeline.watched_phase.value,
        "t_s": [s.t_s for s in timeline.theta],
        "theta": [s.theta for s in timeline.theta],
        "siblings": siblings,
        "cusum": _cusum_payload(timeline),
    }


_cusum_demo_cache: ConnectionTimeline | None = None


def _get_cusum_demo_connection() -> ConnectionTimeline:
    """Bir kez inşa edilip önbelleğe alınır (40 günlük döşenmiş seri +
    θ/CUSUM hesaplaması ucuz değil, her istekte yeniden üretmeye gerek yok
    -- girdisi sabit, salt-okunur bir demo örneği)."""
    global _cusum_demo_cache
    if _cusum_demo_cache is None:
        _cusum_demo_cache = build_cusum_demo_connection()
    return _cusum_demo_cache


def create_app(
    fleet: list[ConnectionTimeline] | None = None,
    *,
    fleet_service: FleetService | None = None,
    demo_controls: bool = True,
) -> Flask:
    """`fleet` verilmezse (varsayılan, mevcut davranış) sabit 2-panolu demo
    filosunu kullanır -- `panogoz.run_local` gibi çağıranlar kendi
    `build_fleet(n)` çıktısını geçirerek N-panolu bir sunucu ayağa
    kaldırabilir (bkz. K2 2.4, docs/06-OLCEKLENEBILIRLIK.md).

    `/api/fleet/*` ve `/api/sim/*`: çok kanallı senaryo filosu + alarm konsolu
    (panogoz/api/fleet_routes.py). `fleet_service` verilmezse ilk istekte varsayılan
    22 panolu filo kurulur (~15 sn); `app.config["FLEET_GETTER"]()` ile önceden
    ısıtılabilir."""
    if fleet is None:
        fleet = build_demo_fleet()
    app = Flask(__name__, static_folder=None)
    app.config["FLEET_GETTER"] = register_fleet_routes(app, fleet_service=fleet_service, demo_controls=demo_controls)

    @app.get("/api/connections")
    def list_connections():
        return jsonify([_connection_summary(i, t) for i, t in enumerate(fleet)])

    @app.get("/api/connections/<int:index>/series")
    def connection_series(index: int):
        if index < 0 or index >= len(fleet):
            return jsonify({"error": "bağlantı bulunamadı"}), 404
        return jsonify(_connection_series(fleet[index]))

    @app.get("/api/connections/<int:index>/flags")
    def connection_flags(index: int):
        if index < 0 or index >= len(fleet):
            return jsonify({"error": "bağlantı bulunamadı"}), 404
        now_t_s = request.args.get("now_t_s", type=float)
        return jsonify(_connection_flags(fleet[index], now_t_s))

    @app.get("/api/connections/<int:index>/evidence")
    def connection_evidence(index: int):
        if index < 0 or index >= len(fleet):
            return jsonify({"error": "bağlantı bulunamadı"}), 404
        return jsonify(_evidence_payload(fleet[index]))

    @app.get("/api/cusum-demo/evidence")
    def cusum_demo_evidence():
        """K3 3.2: CUSUM'un gerçekten tetiklendiği, açıkça etiketli, AYRI bir
        uzatılmış demo örneği (bkz. build_cusum_demo_connection) -- gerçek
        filodaki hiçbir bağlantının verisi/indexi değil."""
        return jsonify(_evidence_payload(_get_cusum_demo_connection()))

    @app.get("/")
    def index():
        return send_from_directory(FRONTEND_DIR, "index.html")

    @app.get("/<path:filename>")
    def static_files(filename: str):
        return send_from_directory(FRONTEND_DIR, filename)

    return app


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=8080, debug=False)
