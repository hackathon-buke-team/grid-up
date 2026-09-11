"""Three-phase voltage THD is a grid-event CANDIDATE, not a verdict.

The panel is a load and cannot lift the voltage distortion of three phases on
its own - but the non-linear loads it FEEDS can.  A VFD bank, a UPS or a large
rectifier downstream of this very busbar injects harmonic current into all three
phases, and that current develops a voltage distortion across the shared upstream
impedance.  The measurement at the analyser looks the same either way.

So the rule is kept, and its certainty is not.  The modes whose evidence IS the
distortion still get the full negative push.  A thermal finding at one bolt has
an independent evidence channel and must not be argued away by a measurement that
has a plausible in-facility explanation, because that is the exact moment a
marginal joint is most likely to be failing.
"""
from panogoz.contracts.live import JointView, PanelLive
from panogoz.rules import suppression as sup

BASELINE = {"L1": 2.5, "L2": 2.5, "L3": 2.5}


def panel(*, thd_pct=7.0, freq_hz=50.0):
    j = JointView(key="C07-L2-PABUC", label="lug", zone="bottom", conductor="L2",
                  feeder_index=7, rated_a=400, monitored=True,
                  temp_c=68.0, theta_k=14.0, theta_min_k=2.0, severity="KRITIK")
    return PanelLive(
        "REVIEW-1", 1, "Review", "REVIEW-1", joints=[j], load_factor=0.45,
        analyser={"mpr.thd_v_l1_pct": thd_pct, "mpr.thd_v_l2_pct": thd_pct,
                  "mpr.thd_v_l3_pct": thd_pct, "mpr.freq_hz": freq_hz},
        analyser_online=True)


def evaluate(**kw):
    live = panel(**kw)
    return sup.evaluate(live, {"now": 1700000000.0, "thd_v_baseline": dict(BASELINE)})


def codes_for(res, mode):
    return {s["reason"] for s in res.suppressed if s["mode"] == mode}


def test_three_phase_thd_is_detected_at_all():
    assert sup.three_phase_thd_event(panel(), {"thd_v_baseline": dict(BASELINE)})


def test_harmonic_modes_are_still_fully_attributed_to_the_grid():
    res = evaluate()
    assert res.negative_evidence["harmonic_neutral"] == sup.GRID_LLR
    assert "GRID_THD_3PH" in codes_for(res, "harmonic_neutral")


def test_thermal_finding_is_only_flagged_as_a_candidate():
    res = evaluate()
    pushed = res.negative_evidence["loose_connection"]
    assert pushed == sup.GRID_CANDIDATE_LLR
    assert abs(pushed) < abs(sup.GRID_LLR), "ısıl bulgu tam bastırılmamalı"
    assert "GRID_THD_3PH_CANDIDATE" in codes_for(res, "loose_connection")
    assert "GRID_THD_3PH" not in codes_for(res, "loose_connection")


def test_the_candidate_reason_does_not_claim_the_source_is_upstream():
    res = evaluate()
    text = next(s["reason_tr"] for s in res.suppressed
                if s["mode"] == "loose_connection")
    # Case-folded matching is avoided on purpose: Python lowercases the Turkish
    # dotless/dotted I wrongly, and a test that quietly compares the wrong string
    # is worse than no test.
    assert "EK KANIT" in text, text
    assert "ADAYIDIR" in text, text
    assert "ekip yönlendirilmez" not in text, "aday sınıflandırma ekip kararı vermemeli"


def test_a_frequency_excursion_confirms_the_grid_and_restores_full_suppression():
    """Independent corroboration the panel cannot manufacture.

    Nothing downstream of an LV busbar moves the system frequency.  When THD and
    frequency agree, the grid attribution is no longer a candidate.
    """
    res = evaluate(freq_hz=50.9)
    assert "GRID_WINDOW" in res.flags
    assert res.negative_evidence["loose_connection"] <= sup.GRID_LLR


def test_candidate_flag_is_distinct_from_a_confirmed_disturbance():
    assert "GRID_DISTURBANCE_CANDIDATE" in evaluate().flags
    assert "GRID_DISTURBANCE" not in evaluate().flags


def test_thd_alone_does_not_block_a_crew_dispatch():
    """``GRID_DISTURBANCE`` is a dispatch veto, so it has to be earned.

    See ``alarms.NO_DISPATCH_FLAGS``: the flag stops a crew being sent at all.
    Handing that veto to a measurement a downstream rectifier can produce means
    a 99 C lug goes unattended for as long as the distortion lasts.
    """
    from panogoz.rules.alarms import NO_DISPATCH_FLAGS

    flags = evaluate().flags
    assert not (flags & set(NO_DISPATCH_FLAGS)), sorted(flags)
    assert "GRID_DISTURBANCE" in evaluate(freq_hz=50.9).flags
