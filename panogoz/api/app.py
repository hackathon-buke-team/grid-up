"""Merkezi monitoring API'si: demo filosunun tam zaman serisini JSON olarak sunar.

Yarışma brifi "operasyon ekiplerinin anlık durumu, anomalileri ve alarmları takip
edebileceği bir izleme altyapısı" istiyor. Bu API, panogoz/sim + detector + rules
çekirdeğinin ürettiği gerçek/sentetik veriyi frontend/'e servis eder.
"""
from __future__ import annotations

from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

from panogoz.detector.cusum import cusum_changepoint, daily_median_series
from panogoz.detector.flags import Flag, flags_for_connection
from panogoz.rules.engine import Severity
from panogoz.sim.ct_data import SAMPLE_PERIOD_S
from panogoz.sim.demo_fleet import RATED_CURRENT_A, ConnectionTimeline, build_demo_fleet

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


def create_app(fleet: list[ConnectionTimeline] | None = None) -> Flask:
    """`fleet` verilmezse (varsayılan, mevcut davranış) sabit 2-panolu demo
    filosunu kullanır -- `panogoz.run_local` gibi çağıranlar kendi
    `build_fleet(n)` çıktısını geçirerek N-panolu bir sunucu ayağa
    kaldırabilir (bkz. K2 2.4, docs/06-OLCEKLENEBILIRLIK.md)."""
    if fleet is None:
        fleet = build_demo_fleet()
    app = Flask(__name__, static_folder=None)

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

    @app.get("/")
    def index():
        return send_from_directory(FRONTEND_DIR, "index.html")

    @app.get("/<path:filename>")
    def static_files(filename: str):
        return send_from_directory(FRONTEND_DIR, filename)

    return app


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=8080, debug=False)
