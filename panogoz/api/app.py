"""Merkezi monitoring API'si: demo filosunun tam zaman serisini JSON olarak sunar.

Yarışma brifi "operasyon ekiplerinin anlık durumu, anomalileri ve alarmları takip
edebileceği bir izleme altyapısı" istiyor. Bu API, panogoz/sim + detector + rules
çekirdeğinin ürettiği gerçek/sentetik veriyi frontend/'e servis eder.
"""
from __future__ import annotations

from pathlib import Path

from flask import Flask, jsonify, send_from_directory

from panogoz.rules.engine import Severity
from panogoz.sim.demo_fleet import ConnectionTimeline, build_demo_fleet

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

    @app.get("/")
    def index():
        return send_from_directory(FRONTEND_DIR, "index.html")

    @app.get("/<path:filename>")
    def static_files(filename: str):
        return send_from_directory(FRONTEND_DIR, filename)

    return app


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=8080, debug=False)
