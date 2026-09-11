"""Regressions for duplicate and out-of-order telemetry.

A QoS 1 broker is allowed to redeliver, and a gateway that restarts with an
unacknowledged outbox will replay.  Both put an OLD envelope on the wire after a
newer one has already been applied.  The live image must not walk backwards
because of it.
"""
from panogoz.contracts.envelope import Envelope, SeqTracker
from panogoz.detector.engine import DetectorEngine
from panogoz.store.db import Store

T0 = 1700000000.0
JOINT = "C01-L1-PABUC"


def data(seq, *, amps, ts=None, boot=1, temp=None):
    joints = {JOINT: {"ir.lug_temp_c": temp}} if temp is not None else {}
    return Envelope(kind="data", site="Review", panel="REVIEW-1", device="GW-01",
                    ts=T0 + (seq * 60.0 if ts is None else ts), seq=seq, boot=boot,
                    values={"mpr.i_l1_a": amps}, joints=joints)


def engine_for(tmp_path):
    store = Store(tmp_path / "stream.db")
    return DetectorEngine(store, persist_samples=False), store


def test_duplicate_envelope_does_not_revert_live_current(tmp_path):
    engine, store = engine_for(tmp_path)
    try:
        engine.observe(data(1, amps=100.0))
        engine.observe(data(2, amps=200.0))
        engine.observe(data(1, amps=100.0))
        live = engine.evaluate("REVIEW-1", T0 + 180.0)
        assert live.analyser["mpr.i_l1_a"] == 200.0
    finally:
        store.close()


def test_stale_envelope_does_not_revert_device_freshness(tmp_path):
    engine, store = engine_for(tmp_path)
    try:
        engine.observe(data(1, amps=100.0))
        engine.observe(data(2, amps=200.0))
        engine.observe(data(1, amps=100.0))
        dev = engine._pr("REVIEW-1").devices["GW-01"]
        assert dev["last_seen"] == T0 + 120.0
        assert dev["seq"] == 2
    finally:
        store.close()


def test_duplicate_envelope_does_not_feed_the_rls_twice(tmp_path):
    engine, store = engine_for(tmp_path)
    try:
        engine.observe(data(1, amps=100.0, temp=40.0))
        engine.observe(data(2, amps=100.0, temp=41.0))
        engine.observe(data(1, amps=100.0, temp=40.0))
        jr = engine._pr("REVIEW-1").jr(JOINT)
        assert jr.last_theta_ts == T0 + 120.0
    finally:
        store.close()


def test_duplicate_is_counted_and_not_charged_as_a_gap(tmp_path):
    engine, store = engine_for(tmp_path)
    try:
        engine.observe(data(1, amps=100.0))
        engine.observe(data(2, amps=200.0))
        engine.observe(data(1, amps=100.0))
        stats = engine.stats()
        assert stats["duplicates"] == 1
        assert stats["seq_gaps"] == 0
        assert stats["seq_lost"] == 0
    finally:
        store.close()


def test_replayed_envelope_does_not_turn_the_next_live_one_into_a_gap():
    tracker = SeqTracker()
    assert tracker.check(data(1, amps=100.0)) == "first"
    assert tracker.check(data(2, amps=200.0)) == "ok"
    assert tracker.check(data(1, amps=100.0)) == "duplicate"
    assert tracker.check(data(3, amps=300.0)) == "ok"
    assert tracker.lost == 0


def test_real_gap_is_still_counted_and_the_message_still_applies(tmp_path):
    engine, store = engine_for(tmp_path)
    try:
        engine.observe(data(1, amps=100.0))
        engine.observe(data(4, amps=400.0))
        live = engine.evaluate("REVIEW-1", T0 + 300.0)
        assert live.analyser["mpr.i_l1_a"] == 400.0
        assert engine.stats()["seq_lost"] == 2
    finally:
        store.close()


def test_reboot_restarts_the_sequence_without_discarding_the_message(tmp_path):
    engine, store = engine_for(tmp_path)
    try:
        engine.observe(data(7, amps=100.0))
        engine.observe(data(1, amps=250.0, ts=480.0, boot=2))
        live = engine.evaluate("REVIEW-1", T0 + 540.0)
        assert live.analyser["mpr.i_l1_a"] == 250.0
        assert engine.stats()["reboots"] == 1
    finally:
        store.close()
