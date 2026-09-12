from panogoz.contracts.channels import Phase
from panogoz.detector.theta import MIN_LOAD_FRACTION, compute_theta_series
from panogoz.sim.ct_data import load_real_l1_series
from panogoz.sim.synthetic import simulate_three_phase_thermal

RATED_CURRENT_A = 250.0  # AG Pano Donanım Listesi: fider anma akımı 250/400A


def test_theta_stays_near_zero_in_normal_operation():
    l1 = load_real_l1_series()
    three_phase = simulate_three_phase_thermal(l1)
    theta_series = compute_theta_series(three_phase, rated_current_a=RATED_CURRENT_A)

    thetas = [s.theta for phase in Phase for s in theta_series[phase] if s.theta is not None]
    assert thetas, "en az bir informative theta örneği olmalı"
    assert max(abs(t) for t in thetas) < 5.0


def test_theta_rises_sharply_after_bolted_joint_fault():
    l1 = load_real_l1_series()
    fault_start_s = l1[len(l1) // 2].t_s
    three_phase = simulate_three_phase_thermal(l1, fault_phase=Phase.L2, fault_start_s=fault_start_s)
    theta_series = compute_theta_series(three_phase, rated_current_a=RATED_CURRENT_A)

    before = [s.theta for s in theta_series[Phase.L2] if s.theta is not None and s.t_s < fault_start_s]
    after = [s.theta for s in theta_series[Phase.L2] if s.theta is not None and s.t_s > fault_start_s + 3 * 3600]

    assert before, "arıza öncesi informative örnek olmalı"
    assert after, "arıza sonrası (ısıl gecikme geçtikten sonra) informative örnek olmalı"
    assert max(abs(t) for t in before) < 5.0
    assert min(after) > 20.0


def test_theta_is_none_below_minimum_load():
    l1 = load_real_l1_series()
    three_phase = simulate_three_phase_thermal(l1)
    theta_series = compute_theta_series(three_phase, rated_current_a=RATED_CURRENT_A)

    threshold_a = MIN_LOAD_FRACTION * RATED_CURRENT_A
    low_load_samples = [
        s
        for i, s in enumerate(theta_series[Phase.L1])
        if three_phase[Phase.L1][i].current_a < threshold_a
    ]
    assert low_load_samples, "eşiğin altında en az bir örnek olmalı ki test bir şey doğrulasın"
    assert all(s.theta is None for s in low_load_samples)
