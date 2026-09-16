from panogoz.contracts.channels import Phase
from panogoz.sim.demo_fleet import build_demo_fleet, build_fleet


def test_build_fleet_generates_requested_panel_count():
    fleet = build_fleet(17, seed=1)
    assert len(fleet) == 17
    ids = {tl.connection_id for tl in fleet}
    assert len(ids) == 17, "her panonun benzersiz bir connection_id'si olmalı"


def test_build_fleet_injects_some_but_not_all_faults():
    fleet = build_fleet(100, fault_fraction=0.12, seed=1)
    faulted = sum(1 for tl in fleet if any(e.severity for e in tl.severity))
    assert 0 < faulted < 100, "gerçekçi bir karışım için ne 0 ne 100 arıza olmalı"


def test_build_fleet_is_deterministic_for_same_seed():
    a = build_fleet(10, seed=7)
    b = build_fleet(10, seed=7)
    assert [tl.connection_id for tl in a] == [tl.connection_id for tl in b]
    assert [tl.theta[-1].theta for tl in a] == [tl.theta[-1].theta for tl in b]


def test_build_fleet_rejects_zero_panels():
    try:
        build_fleet(0)
        assert False, "n_panels=0 ValueError vermeli"
    except ValueError:
        pass


def test_build_demo_fleet_unchanged_by_build_fleet_refactor():
    fleet = build_demo_fleet()
    assert len(fleet) == 2
    assert fleet[0].connection_id == "F01-L1 (sağlıklı)"
    assert fleet[0].watched_phase is Phase.L1
    assert fleet[1].connection_id == "F02-L2 (gevşek cıvatalı bağlantı)"
    assert fleet[1].watched_phase is Phase.L2
    # F02 gercekten arizali olmali (theta buyuk), F01 saglikli (theta kucuk)
    assert abs(fleet[0].theta[-1].theta) < 5.0
    assert fleet[1].theta[-1].theta > 100.0
