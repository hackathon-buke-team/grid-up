"""Filo API'si (K3 3.1/3.4/3.5): alarm konsolu, iş emri kartı, bildirim günlüğü, demo kontrolleri.

Kimlik doğrulama BU KATMANDA YOK: ack/close gövdesindeki `by` bir kimlik iddiasıdır, kanıtı
değil. Üretimde bu API bir ters vekil + mTLS arkasında olmalı (K2 2.2, henüz yapılmadı;
docs/12 §5). Belirteç yine de zorunludur: onay, bildirimi alan kişinin elindeki 4 haneli
kodu ister -- konsolda GÖSTERİLMEZ, yalnız bildirim mesajında gider.
"""
from __future__ import annotations

import io
import socket
import threading
from typing import Callable
from urllib.parse import quote, urlsplit

from flask import Flask, Response, jsonify, request

from panogoz.api.fleet_service import FleetService
from panogoz.rules.alarms import CLOSE_REASONS, AckError
from panogoz.scada import icd
from panogoz.scada.fleet_bridge import scada_view
from panogoz.sim.scenarios import SCENARIOS


def lan_ip() -> str:
    """Yerel ağdaki bu makinenin IP'si (telefonun taraması için). Paket GÖNDERİLMEZ:
    UDP 'connect' yalnız yönlendirme tablosuna bakar."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("10.255.255.255", 1))
            return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def panel_link(base_url: str, panel_id: str, host_url: str) -> str:
    """Saha görünümüne doğrudan bağlantı. `base_url` verilmemişse isteğin kendi adresi kullanılır;
    o localhost ise telefon erişemeyeceği için LAN IP'siyle değiştirilir."""
    base = (base_url or host_url).rstrip("/")
    parts = urlsplit(base)
    if parts.hostname in ("localhost", "127.0.0.1", "::1"):
        port = f":{parts.port}" if parts.port else ""
        base = f"{parts.scheme}://{lan_ip()}{port}"
    return f"{base}/saha.html?panel={quote(panel_id)}"


def qr_svg(url: str) -> str:
    import segno

    buf = io.BytesIO()
    segno.make(url, error="m").save(buf, kind="svg", scale=6, border=2, dark="#111827", light="#ffffff", xmldecl=False, nl=False)
    return buf.getvalue().decode("utf-8")


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

    app.config["FLEET_READY"] = lambda: holder["svc"] is not None

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

    @app.get("/api/fleet/panels/<panel_id>/link")
    def panel_link_route(panel_id: str):
        def build():
            get().panels[panel_id]  # yoksa KeyError -> 404
            return {"panel_id": panel_id, "url": panel_link(request.args.get("base", ""), panel_id, request.host_url)}

        return guarded(build)

    @app.get("/api/fleet/panels/<panel_id>/qr.svg")
    def panel_qr(panel_id: str):
        try:
            get().panels[panel_id]
        except KeyError:
            return err("pano bulunamadı", 404)
        return Response(qr_svg(panel_link(request.args.get("base", ""), panel_id, request.host_url)), mimetype="image/svg+xml")

    @app.get("/api/fleet/scada")
    def scada():
        """SCADA sekmesi: bir panonun ICD v2 register bloğu (ham + çözülmüş + ekran eşlemesi)."""
        svc = get()
        panel_id = request.args.get("panel") or next(iter(svc.panels))
        return guarded(lambda: scada_view(svc, panel_id))

    @app.get("/api/fleet/scada/points.csv")
    def scada_points_csv():
        return Response(icd.csv_point_list(), mimetype="text/csv; charset=utf-8")

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
