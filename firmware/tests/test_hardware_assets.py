"""The twin serves the actual CAD exports; no arbitrary hardware-directory access."""
from types import SimpleNamespace

from fastapi.testclient import TestClient

from panogoz.api.app import create_app
from panogoz.api.hardware import ASSETS
from panogoz.contracts.live import PanelLive


def client():
    live = PanelLive(panel_key='B1-1', panel_index=1, site='Soke', name='B1')
    return TestClient(create_app(SimpleNamespace(resolve=lambda key: key, panel=lambda key: live)))


def test_twin_maps_every_device_to_the_correct_b1_design():
    with client() as http:
        data = http.get('/api/panel/B1-1/twin').json()
    boards = data['design_catalog']['boards']
    assert set(boards) == {'TC', 'IR', 'PD', 'GW'}
    assert [d['hardware_board'] for d in data['devices']].count('TC') == 6
    assert {d['key']: d['hardware_board'] for d in data['devices'] if d['kind'] != 'TC'} == {
        'TN-IR': 'IR', 'PD-01': 'PD', 'GW-01': 'GW'}
    assert boards['TC']['front_mm'] == [19.5, 34]
    assert boards['GW']['outer_mm'] == [112, 112, 54]


def test_design_links_serve_exact_exports_and_real_file_types():
    with client() as http:
        for key, (path, content_type) in ASSETS.items():
            response = http.get('/api/hardware/B1/' + key)
            assert response.status_code == 200, key
            assert response.content == path.read_bytes(), key
            assert response.headers['content-type'].split(';')[0] == content_type
            assert response.headers['x-content-type-options'] == 'nosniff'
            if path.suffix in ('.step', '.kicad_pcb'):
                assert response.headers['content-disposition'].startswith('attachment;')


def test_missing_or_unlisted_assets_are_404_not_frontend_html(tmp_path, monkeypatch):
    with client() as http:
        for path in ('TC/circuit.json', 'evidence/target/panogoz_tc.bin',
                     'dimensions.json', 'TC/%2e%2e/%2e%2e/README.md',
                     'TC/%2e%2e%5c%2e%2e%5cREADME.md'):
            response = http.get('/api/hardware/B1/' + path)
            assert response.status_code == 404, path
        monkeypatch.setitem(ASSETS, 'TC/assembly.png', (tmp_path / 'missing.png', 'image/png'))
        assert http.get('/api/hardware/B1/TC/assembly.png').status_code == 404
