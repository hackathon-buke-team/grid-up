"""K3 3.1/3.4/3.5: filo HTTP API'si (Flask test istemcisi, gerçek servis)."""
import re

import pytest

from panogoz.api.app import create_app
from panogoz.api.fleet_service import DAY_S, FleetService
from tests.test_fleet_service import SPECS, FakeWall


@pytest.fixture()
def svc():
    return FleetService(SPECS, wall=FakeWall())


@pytest.fixture()
def client(svc):
    app = create_app(fleet_service=svc)
    return app.test_client()


def token_from_messages(client, alarm_id):
    for m in client.get("/api/fleet/notifications?limit=500").get_json():
        if m["alarm_id"] == alarm_id and m["status"] == "sent" and m["kind"] == "first":
            return re.search(r"ONAY \S+ (\d{4})", m["text"]).group(1)
    raise AssertionError("belirteçli mesaj yok")


def first_alarm(client, svc):
    svc.advance_to(34.3 * DAY_S)
    rows = client.get("/api/fleet/alarms?state=active&min_severity=ALARM").get_json()
    return next(r for r in rows if r["panel_id"] == "P01")


def test_fleet_endpoint_returns_clock_kpis_and_panel_cards(client):
    body = client.get("/api/fleet").get_json()
    assert body["clock"]["day"] == pytest.approx(30.0, abs=0.02) and body["clock"]["end_day"] > 59
    assert len(body["panels"]) == 6 and body["kpis"]["panels_total"] == 6
    p = body["panels"][0]
    assert {"id", "name", "location", "severity_label", "current_a", "joint_temp_c", "humidity_rh"} <= set(p)


def test_scenario_library_endpoint_lists_all_22(client):
    rows = client.get("/api/scenarios").get_json()
    assert len(rows) == 22 and {"key", "title", "description", "expect", "expected_kind"} <= set(rows[0])
    assert {r["expect"] for r in rows} == {"detect", "advisory", "quiet"}


def test_alarm_list_supports_filters_and_returns_turkish_labels(client, svc):
    a = first_alarm(client, svc)
    assert a["severity_label"] in ("ALARM", "KRİTİK") and a["category"] == "süreç"
    assert "ack_token" not in a  # belirteç API'de yok
    assert client.get("/api/fleet/alarms?kind=loose_bolt&panel=P01").get_json()
    assert client.get("/api/fleet/alarms?kind=arc_trip&panel=P01").get_json() == []


def test_invalid_severity_filter_is_a_client_error_not_a_crash(client, svc):
    svc.advance_to(34.3 * DAY_S)
    resp = client.get("/api/fleet/alarms?min_severity=BOGUS")
    assert resp.status_code == 400
    assert "geçersiz şiddet" in resp.get_json()["error"]


def test_ack_flow_over_http_wrong_token_then_correct_token(client, svc):
    a = first_alarm(client, svc)
    bad = client.post(f"/api/fleet/alarms/{a['id']}/ack", json={"token": "abcd", "by": "Ayşe Y."})
    assert bad.status_code == 400 and "belirteci hatalı" in bad.get_json()["error"]
    no_id = client.post(f"/api/fleet/alarms/{a['id']}/ack", json={"token": token_from_messages(client, a["id"]), "by": ""})
    assert no_id.status_code == 400 and "kimlik" in no_id.get_json()["error"]
    ok = client.post(f"/api/fleet/alarms/{a['id']}/ack", json={"token": token_from_messages(client, a["id"]), "by": "Ayşe Y."})
    assert ok.status_code == 200 and ok.get_json()["state"] == "acked"
    detail = client.get(f"/api/fleet/alarms/{a['id']}").get_json()
    assert detail["alarm"]["acked_by"] == "Ayşe Y." and any(m["kind"] == "ack" for m in detail["messages"])


def test_close_reasons_and_close_flow(client, svc):
    a = first_alarm(client, svc)
    reasons = client.get("/api/fleet/close-reasons").get_json()
    assert "sahada_giderildi" in reasons and "yanlis_alarm" in reasons
    assert client.post(f"/api/fleet/alarms/{a['id']}/close", json={"reason": "uydurma", "by": "Ali"}).status_code == 400
    ok = client.post(f"/api/fleet/alarms/{a['id']}/close", json={"reason": "yanlis_alarm", "by": "Ali"})
    assert ok.status_code == 200 and ok.get_json()["state"] == "closed"


def test_unknown_alarm_and_panel_are_404(client):
    assert client.get("/api/fleet/alarms/YOK-0001").status_code == 404
    assert client.post("/api/fleet/alarms/YOK-0001/ack", json={"token": "1234", "by": "x"}).status_code == 404
    assert client.get("/api/fleet/panels/P99/series").status_code == 404


def test_alarm_detail_has_evidence_and_work_order_card(client, svc):
    a = first_alarm(client, svc)
    d = client.get(f"/api/fleet/alarms/{a['id']}").get_json()
    assert d["work_order"]["needs_outage"] is True and d["work_order"]["steps"] and d["work_order"]["safety"]
    assert d["evidence"]["thresholds"]["ALARM"] == 30.0 and d["evidence"]["score"]


def test_panel_series_endpoint_clamps_days_and_returns_channels(client, svc):
    svc.advance_to(35 * DAY_S)
    body = client.get("/api/fleet/panels/P01/series?days=2").get_json()
    assert len(body["t_s"]) <= 49 and body["panel"]["id"] == "P01" and "tracks" in body
    huge = client.get("/api/fleet/panels/P01/series?days=9999").get_json()
    assert len(huge["t_s"]) <= 60 * 24 + 1


def test_mute_and_silence_endpoints_validate_input(client, svc):
    svc.advance_to(30.1 * DAY_S)
    bad = client.post("/api/fleet/mute", json={"panel_id": "P02", "scope": "loose_bolt", "minutes": 30, "by": "Ali", "reason": ""})
    assert bad.status_code == 400
    ok = client.post("/api/fleet/mute", json={"panel_id": "P02", "scope": "loose_bolt", "minutes": 30, "by": "Ali", "reason": "bakım"})
    assert ok.status_code == 200 and ok.get_json()["scope"] == "loose_bolt"
    assert client.post("/api/fleet/silence", json={"name": "X", "minutes": 5, "by": ""}).status_code == 400
    assert client.post("/api/fleet/silence", json={"name": "X", "minutes": 5, "by": "Zeynep"}).status_code == 200


def test_notifications_storms_and_suppression_endpoints(client, svc):
    svc.advance_to(41 * DAY_S)
    notes = client.get("/api/fleet/notifications?limit=5").get_json()
    assert 0 < len(notes) <= 5 and {"t_s", "to", "role", "route", "kind", "status", "text"} <= set(notes[0])
    assert notes[0]["t_s"] >= notes[-1]["t_s"]  # en yeni önce
    assert set(client.get("/api/fleet/storms").get_json()) == {"limit", "window_s", "active", "episodes"}
    sup = client.get("/api/fleet/suppression").get_json()
    assert len(sup) == 6 and next(r for r in sup if r["panel_id"] == "P05")["reasons"].get("STALE", 0) > 0
    assert len(client.get("/api/fleet/suppression?panel=P05").get_json()) == 1


def test_demo_controls_clock_inject_clear_storm_reset(client, svc):
    assert client.post("/api/sim/clock", json={"speed": 7200, "running": True}).get_json()["speed"] == 7200
    assert client.post("/api/sim/clock", json={"speed": -1}).status_code == 400
    client.post("/api/sim/clock", json={"running": False, "jump_to_day": 31.0})
    inj = client.post("/api/sim/inject", json={"panel_id": "P04", "scenario_key": "loose_bolt_abrupt", "onset_in_min": 30})
    assert inj.status_code == 200 and inj.get_json()["revision"] == 1
    assert client.post("/api/sim/inject", json={"panel_id": "P04", "scenario_key": "yok"}).status_code == 404
    assert client.post("/api/sim/clear", json={"panel_id": "P04"}).get_json()["revision"] == 2
    storm = client.post("/api/sim/storm", json={"panel_ids": ["P01", "P02", "P03"]}).get_json()
    assert storm["panels"] == ["P01", "P02", "P03"]
    reset = client.post("/api/sim/reset").get_json()
    assert reset["day"] == pytest.approx(30.0, abs=0.02)
    assert client.get("/api/fleet/alarms").get_json() == []


def test_demo_controls_can_be_disabled_for_production(svc):
    app = create_app(fleet_service=svc, demo_controls=False)
    c = app.test_client()
    assert c.get("/api/sim/status").get_json()["demo_controls"] is False
    for path, body in (("/api/sim/clock", {"running": True}), ("/api/sim/inject", {"panel_id": "P04", "scenario_key": "loose_bolt_abrupt"}),
                       ("/api/sim/reset", {})):
        assert c.post(path, json=body).status_code == 403
    assert c.get("/api/fleet").status_code == 200  # okuma açık


def test_legacy_endpoints_still_work_alongside_fleet_api(client):
    assert client.get("/api/connections").status_code == 200
    assert client.get("/").status_code == 200


# ---- K3 3.3: QR + doğrudan bağlantı ----------------------------------------------------
def test_panel_link_uses_lan_ip_instead_of_localhost_so_a_phone_can_open_it(client, monkeypatch):
    from panogoz.api import fleet_routes

    monkeypatch.setattr(fleet_routes, "lan_ip", lambda: "10.20.30.40")
    url = client.get("/api/fleet/panels/P01/link", base_url="http://localhost:8080").get_json()["url"]
    assert url == "http://10.20.30.40:8080/saha.html?panel=P01"
    explicit = client.get("/api/fleet/panels/P01/link?base=https://konsol.ornek.local").get_json()["url"]
    assert explicit == "https://konsol.ornek.local/saha.html?panel=P01"
    assert client.get("/api/fleet/panels/P99/link").status_code == 404


def test_qr_endpoint_serves_svg_and_404s_for_unknown_panel(client):
    resp = client.get("/api/fleet/panels/P02/qr.svg?base=http://10.0.0.5:8080")
    assert resp.status_code == 200 and resp.mimetype == "image/svg+xml" and resp.data.startswith(b"<svg")
    assert client.get("/api/fleet/panels/P99/qr.svg").status_code == 404


def test_qr_code_decodes_back_to_the_panel_link():
    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")
    import io

    import segno

    from panogoz.api.fleet_routes import panel_link

    url = panel_link("http://10.0.0.5:8080", "P07", "http://x/")
    buf = io.BytesIO()
    segno.make(url, error="m").save(buf, kind="png", scale=8, border=4)
    img = cv2.imdecode(np.frombuffer(buf.getvalue(), np.uint8), cv2.IMREAD_COLOR)
    decoded, _, _ = cv2.QRCodeDetector().detectAndDecode(img)
    assert decoded == url == "http://10.0.0.5:8080/saha.html?panel=P07"
