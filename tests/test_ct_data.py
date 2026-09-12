from panogoz.sim.ct_data import SAMPLE_PERIOD_S, load_real_l1_series


def test_loads_all_real_samples():
    samples = load_real_l1_series()
    assert len(samples) == 152


def test_first_sample_matches_known_value():
    samples = load_real_l1_series()
    assert samples[0].secondary_ma == 53
    assert samples[0].primary_a == 318
    assert samples[0].t_s == 0


def test_samples_are_evenly_spaced():
    samples = load_real_l1_series()
    for i in range(1, len(samples)):
        assert samples[i].t_s - samples[i - 1].t_s == SAMPLE_PERIOD_S


def test_series_spans_about_a_day_and_a_half():
    samples = load_real_l1_series()
    total_hours = samples[-1].t_s / 3600
    assert 36 <= total_hours <= 40
