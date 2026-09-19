"""Filo API'si (K3 3.1/3.4/3.5): alarm konsolu, iş emri kartı, bildirim günlüğü, demo kontrolleri.

Kimlik doğrulama BU KATMANDA YOK: ack/close gövdesindeki `by` bir kimlik iddiasıdır, kanıtı
değil. Üretimde bu API bir ters vekil + mTLS arkasında olmalı (K2 2.2, henüz yapılmadı;
docs/12 §5). Belirteç yine de zorunludur: onay, bildirimi alan kişinin elindeki 4 haneli
kodu ister -- konsolda GÖSTERİLMEZ, yalnız bildirim mesajında gider.
"""
from __future__ import annotations

import threading
from typing import Callable

from flask import Flask, jsonify, request

from panogoz.api.fleet_service import FleetService
from panogoz.rules.alarms import CLOSE_REASONS, AckError
from panogoz.sim.scenarios import SCENARIOS


def register_fleet_routes(
    app: Flask,
    *,
    fleet_service: FleetService | None = None,
    demo_controls: bool = True,
) -> Callable[[], FleetService]:
    """Rotaları ekler; hizmete (varsayılan filo dahil) lazily erişen bir fonksiyon döner."""
    holder: dict = {"svc": fleet_service, "building": False}
    lock = threading.Lock()

    def get() -> FleetService:
        with lock:
            if holder["svc"] is None:
                holder["building"] = True
                try:
                    holder["svc"] = FleetService()
                finally:
                    holder["building"] = False
            return holder["svc"]

    def body() -> dict:
        data = request.get_json(silent=True)
        return data if isinstance(data, dict) else {}

    def err(message: str, code: int = 400):
        return jsonify({"error": message}), code

    def guarded(fn):
        try:
            return jsonify(fn())
        except AckError as exc:
            return err(str(exc), 400)
        except (ValueError, TypeError) as exc:
            return err(str(exc), 400)
        except KeyError as exc:
            return err(str(exc).strip("'\""), 404)

    @app.get("/api/sim/status")
    def sim_status():
        return jsonify({"ready": holder["svc"] is not None, "building": holder["building"], "demo_controls": demo_controls})

    @app.get("/api/scenarios")
    def scenarios():
        return jsonify(
            [
                {
                    "key": s.key, "title": s.title, "description": s.description,
                    "expect": s.expect.value, "expected_kind": s.expected_kind,
                }
                for s in SCENARIOS.values()
            ]
        )

    @app.get("/api/fleet")
    def fleet():
        svc = get()
        return jsonify({"clock": svc.clock_state(), "kpis": svc.kpis(), "panels": svc.panels_summary()})

    @app.get("/api/fleet/panels/<panel_id>/series")
    def panel_series(panel_id: str):
        days = request.args.get("days", default=14.0, type=float)
        return guarded(lambda: get().panel_series(panel_id, days=max(1.0, min(days, 60.0))))

    @app.get("/api/fleet/alarms")
    def alarms():
        a = request.args
        return guarded(
            lambda: get().alarms(
                state=a.get("state"), min_severity=a.get("min_severity"), family=a.get("family"),
                panel_id=a.get("panel"), kind=a.get("kind"), sort=a.get("sort", "priority"),
            )
        )

    @app.get("/api/fleet/alarms/<alarm_id>")
    def alarm_detail(alarm_id: str):
        return guarded(lambda: get().alarm_detail(alarm_id))

    @app.post("/api/fleet/alarms/<alarm_id>/ack")
    def ack(alarm_id: str):
        b = body()
        return guarded(lambda: get().ack(alarm_id, str(b.get("token", "")), str(b.get("by", ""))))

    @app.post("/api/fleet/alarms/<alarm_id>/close")
    def close(alarm_id: str):
        b = body()
        return guarded(lambda: get().close(alarm_id, str(b.get("reason", "")), str(b.get("by", ""))))

    @app.get("/api/fleet/close-reasons")
    def close_reasons():
        return jsonify(list(CLOSE_REASONS))

    @app.post("/api/fleet/mute")
    def mute():
        b = body()
        return guarded(
            lambda: get().mute(str(b.get("panel_id", "")), str(b.get("scope", "")), float(b.get("minutes", 0)),
                               str(b.get("by", "")), str(b.get("reason", "")))
        )

    @app.post("/api/fleet/silence")
    def silence():
        b = body()
        return guarded(lambda: get().silence(str(b.get("name", "")), float(b.get("minutes", 0)), str(b.get("by", ""))))

    @app.get("/api/fleet/notifications")
    def notifications():
        limit = request.args.get("limit", default=100, type=int)
        return guarded(lambda: get().notifications(max(1, min(limit, 500))))

    @app.get("/api/fleet/storms")
    def storms():
        return guarded(lambda: get().storms())

    @app.get("/api/fleet/suppression")
    def suppression():
        return guarded(lambda: get().suppression_summary(request.args.get("panel")))

    # ---- demo kontrol paneli (K3 3.5): yalnız `demo_controls=True` iken
    def demo_only(fn):
        if not demo_controls:
            return err("demo kontrolleri kapalı", 403)
        return guarded(fn)

    @app.get("/api/sim/clock")
    def clock_get():
        return guarded(lambda: get().clock_state())

    @app.post("/api/sim/clock")
    def clock_set():
        b = body()
        return demo_only(
            lambda: get().set_clock(
                speed=float(b["speed"]) if "speed" in b else None,
                running=bool(b["running"]) if "running" in b else None,
                jump_to_day=float(b["jump_to_day"]) if "jump_to_day" in b else None,
            )
        )

    @app.post("/api/sim/inject")
    def inject():
        b = body()
        return demo_only(
            lambda: get().inject(str(b.get("panel_id", "")), str(b.get("scenario_key", "")),
                                 onset_in_s=float(b.get("onset_in_min", 60)) * 60.0)
        )

    @app.post("/api/sim/clear")
    def clear():
        b = body()
        return demo_only(lambda: get().clear(str(b.get("panel_id", ""))))

    @app.post("/api/sim/storm")
    def storm():
        b = body()
        return demo_only(lambda: {"panels": get().inject_storm(b.get("panel_ids"), scenario_key=str(b.get("scenario_key", "arc_integrity_fault")))})

    @app.post("/api/sim/reset")
    def reset():
        return demo_only(lambda: (get().reset(), get().clock_state())[1])

    return get
