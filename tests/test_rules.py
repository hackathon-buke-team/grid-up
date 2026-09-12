from panogoz.contracts.channels import Phase
from panogoz.detector.theta import compute_theta_series
from panogoz.rules.engine import Severity, evaluate_severity_series
from panogoz.sim.ct_data import load_real_l1_series
from panogoz.sim.synthetic import simulate_three_phase_thermal

RATED_CURRENT_A = 250.0


def test_normal_operation_never_escalates_past_normal():
    l1 = load_real_l1_series()
    three_phase = simulate_three_phase_thermal(l1)
    theta_series = compute_theta_series(three_phase, rated_current_a=RATED_CURRENT_A)
    events = evaluate_severity_series(theta_series[Phase.L1])
    assert all(e.severity == Severity.NORMAL for e in events)


def test_bolted_joint_fault_eventually_reaches_critical():
    l1 = load_real_l1_series()
    fault_start_s = l1[len(l1) // 2].t_s
    three_phase = simulate_three_phase_thermal(l1, fault_phase=Phase.L2, fault_start_s=fault_start_s)
    theta_series = compute_theta_series(three_phase, rated_current_a=RATED_CURRENT_A)
    events = evaluate_severity_series(theta_series[Phase.L2])
    assert any(e.severity == Severity.CRITICAL for e in events)


def test_single_sample_spike_does_not_trigger_alarm():
    l1 = load_real_l1_series()
    three_phase = simulate_three_phase_thermal(l1)
    theta_series = compute_theta_series(three_phase, rated_current_a=RATED_CURRENT_A)
    spiked = list(theta_series[Phase.L1])
    for i, s in enumerate(spiked):
        if s.theta is not None:
            spiked[i] = type(s)(t_s=s.t_s, phase=s.phase, theta=100.0)
            break
    events = evaluate_severity_series(spiked)
    assert all(e.severity == Severity.NORMAL for e in events)
