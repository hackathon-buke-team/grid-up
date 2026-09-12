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
