import pytest

from panogoz.api.app import create_app


@pytest.fixture
def client():
    app = create_app()
    app.testing = True
    with app.test_client() as c:
        yield c


def test_list_connections_returns_two_entries(client):
    resp = client.get("/api/connections")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data) == 2
    assert data[0]["severity"] == "NORMAL"
    assert data[1]["severity"] == "CRITICAL"


def test_series_endpoint_returns_full_history(client):
    resp = client.get("/api/connections/1/series")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["t_s"]) == 152
    assert len(data["theta"]) == 152
    assert data["severity"][-1] == 3


def test_unknown_connection_returns_404(client):
    resp = client.get("/api/connections/99/series")
    assert resp.status_code == 404


def test_index_serves_frontend_html(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"PANO G" in resp.data


# --- K3 3.2 (Kanıt ekranı): siblings + CUSUM -------------------------------


def test_evidence_endpoint_returns_all_three_siblings(client):
    resp = client.get("/api/connections/1/evidence")
    assert resp.status_code == 200
    data = resp.get_json()
    assert set(data["siblings"].keys()) == {"L1", "L2", "L3"}
    for phase_data in data["siblings"].values():
        assert len(phase_data["surface_temp_c"]) == 152
    assert data["watched_phase"] == "L2"


def test_evidence_endpoint_reports_insufficient_cusum_data_honestly(client):
    """Gerçek demo filosu ~1.6 gün -- CUSUM'un 31 günlük baseline'ını
    karşılamıyor; API bunu sahte bir sonuç yerine dürüst bir nota
    dönüştürmeli (bkz. panogoz/detector/cusum.py baseline_days=30)."""
    resp = client.get("/api/connections/0/evidence")
    data = resp.get_json()
    assert data["cusum"]["available"] is False
    assert data["cusum"]["changepoint_day_index"] is None
    assert "31 gun" in data["cusum"]["note"] or "31 gün" in data["cusum"]["note"]


def test_unknown_connection_evidence_returns_404(client):
    resp = client.get("/api/connections/99/evidence")
    assert resp.status_code == 404


def test_cusum_demo_endpoint_actually_detects_the_injected_changepoint(client):
    """K3 3.2 -- ayrı, uzatılmış (40 günlük döşenmiş gerçek desen) demo
    bağlantısı gerçekten CUSUM'u tetiklemeli (fault_start_day=30, bkz.
    panogoz/sim/demo_fleet.py build_cusum_demo_connection)."""
    resp = client.get("/api/cusum-demo/evidence")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["cusum"]["available"] is True
    assert data["cusum"]["changepoint_day_index"] == 30
    assert "DEMO" in data["connection_id"]
