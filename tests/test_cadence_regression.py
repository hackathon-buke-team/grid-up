"""The publish cadence is part of the device contract, not a server guess.

The node's idle cadence is 900 s (``PG_PERIOD_IDLE_S``), its watch cadence 60 s
and its burst cadence 10 s.  A server that hard-codes a 180 s offline window
declares a perfectly healthy node dead three minutes into a fifteen-minute sleep
and throws away its sibling reading two minutes after that, which disables the
whole differential detector at the cadence the product is designed to run at.

So the device advertises the interval it intends to publish at, and the server
derives its freshness windows from that number.  Three different questions get
three different windows, because they are three different questions:

* is the device still talking to us          -> misses of its own period
* is the analyser reading fresh enough to use -> the gateway's own period
* were two sibling lugs read close enough together to subtract -> one period
"""
import pytest

from panogoz.contracts import channels
from panogoz.contracts.envelope import Envelope
from panogoz.detector.engine import DetectorEngine
from panogoz.gateway.gateway import Gateway
from panogoz.store.db import Store

T0 = 1700000000.0
IDLE_S = 900.0


def engine_for(tmp_path):
    store = Store(tmp_path / "cadence.db")
    return DetectorEngine(store, persist_samples=False), store


def frame(device, ts, *, seq, period_s=IDLE_S, values=None, joints=None):
    vals = dict(values or {})
    if period_s is not None:
        vals["dev.period_s"] = period_s
    return Envelope(kind="data", site="Review", panel="REVIEW-1", device=device,
                    ts=ts, seq=seq, boot=1, values=vals, joints=joints or {})


def test_period_is_a_declared_channel():
    assert channels.get("dev.period_s").unit == "s"
    assert channels.validate("dev.period_s", IDLE_S)


def test_idle_node_stays_online_between_two_publications(tmp_path):
    engine, store = engine_for(tmp_path)
    try:
        engine.observe(frame("TC-01", T0, seq=1))
        live = engine.evaluate("REVIEW-1", T0 + 600.0)
        dev = next(d for d in live.devices if d.key == "TC-01")
        assert dev.period_s == IDLE_S
        assert dev.online
    finally:
        store.close()


def test_node_that_missed_three_publications_is_offline(tmp_path):
    engine, store = engine_for(tmp_path)
    try:
        engine.observe(frame("TC-01", T0, seq=1))
        live = engine.evaluate("REVIEW-1", T0 + 3 * IDLE_S + 1.0)
        dev = next(d for d in live.devices if d.key == "TC-01")
        assert not dev.online
    finally:
        store.close()


def test_burst_cadence_does_not_shorten_the_window_below_the_floor(tmp_path):
    engine, store = engine_for(tmp_path)
    try:
        engine.observe(frame("TC-01", T0, seq=1, period_s=10.0))
        live = engine.evaluate("REVIEW-1", T0 + 120.0)
        dev = next(d for d in live.devices if d.key == "TC-01")
        assert dev.online, "10 s kadansta 3 kayıp = 30 s; taban 180 s korunmalı"
    finally:
        store.close()


def test_device_that_declares_no_period_keeps_the_legacy_window(tmp_path):
    engine, store = engine_for(tmp_path)
    try:
        engine.observe(frame("TC-01", T0, seq=1, period_s=None))
        assert engine.evaluate("REVIEW-1", T0 + 170.0).devices
        near = next(d for d in engine.evaluate("REVIEW-1", T0 + 170.0).devices
                    if d.key == "TC-01")
        far = next(d for d in engine.evaluate("REVIEW-1", T0 + 190.0).devices
                   if d.key == "TC-01")
        assert near.online and not far.online
        assert near.period_s is None
    finally:
        store.close()


def test_analyser_read_at_idle_cadence_is_not_declared_stale(tmp_path):
    engine, store = engine_for(tmp_path)
    try:
        engine.observe(frame("GW-01", T0, seq=1,
                             values={"mpr.i_l1_a": 800.0, "mpr.i_l2_a": 800.0,
                                     "mpr.i_l3_a": 800.0}))
        live = engine.evaluate("REVIEW-1", T0 + 600.0)
        assert live.analyser_online
        assert live.load_factor > 0.0
    finally:
        store.close()


#: Three clips on one feeder, each on its own 900 s schedule with a staggered
#: phase - which is what independently woken battery nodes actually do.
CLIP_SCHEDULE = (
    ("TC-01", "C06-L1-PABUC", 44.0, 0.0),
    ("TC-02", "C06-L2-PABUC", 41.0, 300.0),
    ("TC-03", "C06-L3-PABUC", 41.0, 600.0),
)


def run_idle_feeder(engine, *, period_s):
    engine.observe(frame("GW-01", T0, seq=1, period_s=period_s,
                         values={"mpr.i_l1_a": 700.0, "mpr.i_l2_a": 700.0,
                                 "mpr.i_l3_a": 700.0}))
    for round_i in (0, 1):
        for device, joint, temp, phase in CLIP_SCHEDULE:
            engine.observe(frame(device, T0 + phase + round_i * IDLE_S,
                                 seq=round_i + 1, period_s=period_s,
                                 joints={joint: {"tc.temp_c": temp}}))
    return engine.evaluate("REVIEW-1", T0 + IDLE_S + 600.0)


def test_siblings_one_idle_period_apart_still_produce_theta(tmp_path):
    engine, store = engine_for(tmp_path)
    try:
        live = run_idle_feeder(engine, period_s=IDLE_S)
        hot = next(j for j in live.joints if j.key == "C06-L1-PABUC")
        assert hot.theta_k is not None, "900 s kadansta kardeş karşılaştırması düştü"
        assert hot.theta_k > 0.0
    finally:
        store.close()


def test_undeclared_cadence_keeps_the_narrow_peer_window(tmp_path):
    """The wider window is EARNED by declaring a cadence, never assumed."""
    engine, store = engine_for(tmp_path)
    try:
        live = run_idle_feeder(engine, period_s=None)
        hot = next(j for j in live.joints if j.key == "C06-L1-PABUC")
        assert hot.theta_k is None
    finally:
        store.close()


def test_gateway_publishes_the_period_it_is_driven_at():
    published = []

    class RecordingBus:
        def publish_envelope(self, env, retain=False):
            published.append(env)

    gw = Gateway(panel_key="REVIEW-1", site="Review", bus=RecordingBus(),
                 period_s=IDLE_S)
    assert gw.period_s == IDLE_S
    envs = gw.birth_envelopes()
    assert any(e.event.get("period_s") == IDLE_S for e in envs if e.device == "TC-01")


@pytest.mark.parametrize("cadence,want", [("IDLE", 900.0), ("WATCH", 60.0), ("BURST", 10.0)])
def test_python_mirrors_the_firmware_cadence_table(cadence, want):
    assert channels.CADENCE_PERIOD_S[cadence] == want
