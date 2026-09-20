"""B1 measurement limits and radio custody on the team's actual gateway."""
import json
from pathlib import Path
from types import SimpleNamespace
import pytest

from firmware.tools.radio_bridge import forward
from panogoz.gateway.gateway import Gateway
from panogoz.hardware_profile import TC_JOINTS, IR_PIXEL_MM, TC_LIFE_DAYS
from panogoz.sim.panel import PanelSim, DEFAULT_START_TS
from panogoz.store.db import Store
from panogoz.contracts.envelope import Envelope
from panogoz.detector.engine import DetectorEngine


def panel(**kw):
    return PanelSim(panel_key='B1-1', panel_index=1, site='Soke', name='B1',
                    dso='ADM', lat=37.75, lon=27.41, start_ts=DEFAULT_START_TS, **kw)


def packet():
    return bytes.fromhex(json.loads((Path(__file__).parents[1] /
                                    'node/tests/radio_vectors.json').read_text())[3])


def test_default_b1_does_not_invent_individual_ir_lug_measurements():
    sim = panel()
    out = sim.step(DEFAULT_START_TS)
    assert 37 < IR_PIXEL_MM < 39  # physically wider than 20 mm lug pitch
    assert set(out.joints) == TC_JOINTS
    assert all('ir.lug_temp_c' not in v for v in out.joints.values())
    # Ground truth remains available to evaluate blind spots, never telemetry.
    assert len(out.truth['joints']) == 40
    assert sim.describe()['monitored_joints'] == 6


def test_battery_model_uses_tc_budget_and_leaves_ir_pd_capacity_unknown():
    sim = panel()
    out = sim.step(DEFAULT_START_TS)
    assert sim._battery_life_y['TC-01'] * 365.25 == TC_LIFE_DAYS
    for key in ('TN-IR', 'PD-01'):
        assert 'dev.battery_pct' not in out.devices[key]
        assert out.devices[key]['dev.battery_v'] == 3.65
    before = out.devices['TC-01']['dev.battery_pct']
    later = sim.step(DEFAULT_START_TS + 100 * 86400)
    # Registry encodes whole percent; differencing two rounded samples loses <1%.
    assert before - later.devices['TC-01']['dev.battery_pct'] == pytest.approx(10000 / 721, abs=1)


def test_unmeasured_joint_has_a_reason_instead_of_an_empty_prediction(tmp_path):
    store = Store(str(tmp_path / 'unmeasured.db'))
    engine = DetectorEngine(store)
    live = engine.evaluate('B1-1', DEFAULT_START_TS)
    joint = next(j for j in live.joints if j.key == 'C02-L1-PABUC')
    assert joint.temp_c is None and joint.eta.days is None
    assert joint.eta.reason == 'YETERSIZ_GECMIS'
    store.close()


def test_api_twin_reports_six_resolved_points_and_no_ir_coverage(tmp_path):
    from panogoz.api.app import create_app
    store = Store(str(tmp_path / 'twin.db'))
    engine = DetectorEngine(store)
    runtime = SimpleNamespace(resolve=lambda key: key,
                              panel=lambda key: engine.evaluate(key, DEFAULT_START_TS))
    app = create_app(runtime)
    route = next(r for r in app.routes if r.path == '/api/panel/{panel_key}/twin')
    twin = route.endpoint('B1-1')
    assert twin['counts']['joints_resolved'] == 6
    assert sum(j['measurement_supported'] for j in twin['joints']) == 6
    ir = next(d for d in twin['devices'] if d['key'] == 'TN-IR')
    assert ir['covers'] == [] and len(ir['candidate_covers']) == 40
    store.close()


def test_radio_custody_survives_restart_and_waits_for_puback(tmp_path):
    store = Store(str(tmp_path / 'radio.db'))
    gw = Gateway(panel_key='B1-1', site='Soke', outbox_store=store)
    env = forward(packet(), gw)
    row = store.outbox_rows('B1-1')[0]
    assert Envelope.from_json(row['payload']) == env
    assert (env.device, env.seq, env.boot, env.values['dev.period_s']) == ('TC-04', 42, 3, 60)
    store.close()
    restored = Store(str(tmp_path / 'radio.db'))
    sent = []
    receipt = SimpleNamespace(acked=False)
    receipt.is_published = lambda: receipt.acked
    class Bus:
        def publish_envelope(self, e, retain=False):
            sent.append(e)
            return receipt
    gw2 = Gateway(panel_key='B1-1', site='Soke', outbox_store=restored, bus=Bus())
    assert gw2.drain() == 0 and len(restored.outbox_rows('B1-1')) == 1
    assert sent == [env]
    receipt.acked = True
    assert gw2.drain() == 1 and not restored.outbox_rows('B1-1')
    restored.close()


def test_no_radio_ack_custody_when_outbox_missing_full_or_corrupt(tmp_path):
    with pytest.raises(RuntimeError, match='persistent'):
        forward(packet(), Gateway(panel_key='B1-1', site='Soke'))
    store = Store(str(tmp_path / 'full.db'))
    gw = Gateway(panel_key='B1-1', site='Soke', outbox_store=store, buffer_size=1)
    forward(packet(), gw)
    with pytest.raises(BufferError):
        forward(packet(), gw)
    broken = bytearray(packet()); broken[16] ^= 1
    with pytest.raises(ValueError, match='CRC'):
        forward(bytes(broken), gw)
    assert len(store.outbox_rows('B1-1')) == 1
    store.close()
