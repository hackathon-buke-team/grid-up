"""Regressions for detector authority and busbar/feeder load units."""
import pytest

from panogoz.contracts import icd
from panogoz.contracts.envelope import Envelope
from panogoz.contracts.live import ArcView, JointView, PanelLive
from panogoz.detector.engine import DetectorEngine, _JointRuntime
from panogoz.rules import fusion
from panogoz.store.db import Store


def joint(**kwargs):
    return JointView(key="C01-L1-PABUC", label="lug", zone="bottom",
                     conductor="L1", feeder_index=1, rated_a=400,
                     monitored=True, **kwargs)


def test_ir_live_spike_does_not_override_daily_detector_verdict(tmp_path):
    store = Store(tmp_path / "test.db")
    try:
        engine = DetectorEngine(store)
        j = joint(temp_c=45, theta_k=20, theta_min_k=3)
        j.severity = engine._joint_severity(j, _JointRuntime(theta_daily=0.5), False)
        assert j.severity == "BILGI"
        live = PanelLive("test", 1, "site", "test", joints=[j])
        fusion.apply(live)
        assert j.severity == "BILGI"
    finally:
        store.close()


@pytest.mark.parametrize("verdict,theta,temp,want", [
    ("BILGI", 20, 45, "BILGI"),
    ("KRITIK", 40, 45, "KRITIK"),
    ("BILGI", 0, 130, "ACIL"),
    (None, 20, 45, "KRITIK"),
])
def test_fusion_respects_explicit_verdict_with_absolute_safety_floor(verdict, theta, temp, want):
    assert fusion.joint_severity(joint(severity=verdict, theta_k=theta,
                                     theta_min_k=3, temp_c=temp)) == want


def test_arc_trip_still_overrides_an_explicit_bilgi_joint():
    live = PanelLive("test", 1, "site", "test", joints=[joint(severity="BILGI")],
                     arc=ArcView(fitted=True, online=True, active_trip=True))
    fusion.apply(live)
    assert live.severity == "ACIL"


@pytest.mark.parametrize("currents,mean_ratio,peak_ratio,sensitivity", [
    ((2312, 2312, 2312), 1.0, 1.0, 100),
    ((3000, 1500, 1500), 2000 / 2312, 3000 / 2312, 100),
    ((975, 975, 975), 975 / 2312, 975 / 2312, 75),
])
def test_panel_load_uses_busbar_rating_and_overload_sees_peak_phase(tmp_path, currents, mean_ratio, peak_ratio, sensitivity):
    store = Store(tmp_path / "test.db")
    try:
        engine = DetectorEngine(store)
        engine.observe(Envelope(kind="data", site="test", panel="test", device="GW-01",
                                ts=1750000000, seq=1, boot=1,
                                values={**{f"mpr.i_l{p}_a": value for p, value in enumerate(currents, 1)},
                                        "mpr.online": 1}))
        live = engine.evaluate("test", 1750000001)
        assert live.load_factor == pytest.approx(mean_ratio)
        assert fusion.observations(live)["load_factor"] == pytest.approx(peak_ratio)
        reg = icd.PANEL_BY_NAME["LOAD_FACTOR"]
        words = live.to_registers([])
        assert icd.decode(reg, words[reg.offset:reg.offset + reg.words]) == pytest.approx(100 * mean_ratio, abs=0.1)
        assert live.feeder_load_factor == pytest.approx(sum(currents) / 3 / 3250)
        assert live.sensitivity_pct == pytest.approx(sensitivity)
        ir = next(j for j in live.joints if j.key == "C01-L1-PABUC")
        assert ir.load_factor == pytest.approx(currents[0] / 3250)
    finally:
        store.close()


def test_stored_history_primes_the_debounce_instead_of_grading_itself_bilgi(tmp_path):
    """A restart that loads its own proof must be able to raise on it.

    ``prime_alarm_debounce`` replays the stored daily medians through the shared
    severity function.  The ``JointView`` it builds is a SNAPSHOT: there is no
    detector attached to it, so its verdict field must carry the "no verdict"
    sentinel.  Writing an explicit ``BILGI`` there makes fusion - correctly -
    treat the placeholder as an authoritative decision, every replayed day
    grades BILGI, no bucket is written, and a panel with sixty days of proof in
    its own database can never open an incident.
    """
    from panogoz.api.runtime import Runtime
    from panogoz.contracts import assets
    from panogoz.rules import pipeline

    pipeline.reset()
    now = 1787500000.0
    rt = Runtime(n_panels=1, seed=42, db_path=str(tmp_path / "prime.db"),
                 backfill_days=0, scada_port=15781, quiet=True)
    try:
        j = assets.monitored_joints()[0]
        rt.store.upsert_panel(panel_key="PRIME-1", panel_index=1, site="Review",
                              name="PRIME-1", dso="", lat=0.0, lon=0.0,
                              rated_kva=assets.RATED_KVA, commissioned=now - 400 * 86400,
                              learn_until=now - 393 * 86400, has_analyser=1,
                              has_arc_relay=0, arc_detectors=0)
        today = int(now // 86400)
        for back in range(5):
            rt.store.upsert_joint_daily(
                day=today - back, panel_key="PRIME-1", joint_key=j.key,
                theta_med=8.0, theta_p90=8.4, n=16, load_mean=0.4,
                sens_pct=250.0, cusum=20.0, baseline=0.5, theta_min=2.0)
        rt.store.commit()

        written = rt.prime_alarm_debounce(now)
        assert written >= 3, f"{written} gün penceresi yazıldı, en az 3 bekleniyordu"
    finally:
        rt.stop()
        pipeline.reset()
