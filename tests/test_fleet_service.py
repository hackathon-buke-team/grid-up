"""K3 3.1/3.4/3.5: filo servisi -- alarm konsolu arka ucu, ack akışı, fırtına, enjeksiyon, saat."""
import re

import pytest

from panogoz.api.fleet_service import (
    DAY_S,
    FleetService,
    PanelSpec,
    SimClock,
    default_fleet_specs,
)
from panogoz.notify.escalation import EscalationPolicy
from panogoz.rules.alarms import AckError, AlarmState
from panogoz.sim.scenarios import SCENARIOS

SPECS = [
    PanelSpec("P01", "Test TM · Pano 1", "Konum 1", "loose_bolt_abrupt", 34.0),
    PanelSpec("P02", "Test TM · Pano 2", "Konum 2", "loose_bolt_low_load", 34.0),
    PanelSpec("P03", "Test TM · Pano 3", "Konum 3", "pd_only_dry", 34.0),
    PanelSpec("P04", "Test TM · Pano 4", "Konum 4", "healthy_baseline"),
    PanelSpec("P05", "Test TM · Pano 5", "Konum 5", "comms_dropout"),
    PanelSpec("P06", "Test TM · Pano 6", "Konum 6", "arc_trip", 35.0),
]


class FakeWall:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def make(**kw):
    return FleetService(SPECS, wall=FakeWall(), **kw)


def token_for(svc, alarm_id):
    """Onay belirteci konsolda GÖSTERİLMEZ; yalnız bildirim mesajından okunur (telefon gibi)."""
    for m in svc.notifications(500):
        if m["alarm_id"] == alarm_id and m["kind"] in ("first", "reminder", "escalation", "escalated_severity", "handover"):
            found = re.search(rf"ONAY {re.escape(alarm_id)} (\d{{4}})", m["text"])
            if found:
                return found.group(1)
    raise AssertionError(f"{alarm_id} için belirteçli mesaj yok")


def test_default_fleet_has_one_panel_per_scenario_with_staggered_fault_onsets():
    specs = default_fleet_specs()
    assert len(specs) == len(SCENARIOS) == 22
    onsets = [s.onset_day for s in specs if s.onset_day is not None]
    assert len(onsets) == 12 and onsets == sorted(onsets) and len(set(onsets)) == 12  # 11 arıza + 1 yalnız-uyarı
    assert max(onsets) - min(onsets) > 10  # aynı dakikada başlamaz


def test_service_starts_at_day_30_with_no_alarms_and_six_panels():
    svc = make()
    assert svc.clock_state()["day"] == pytest.approx(30.0, abs=0.02)
    assert len(svc.panels_summary()) == 6
    assert svc.alarms() == []
    assert svc.kpis()["awaiting_ack"] == 0


def test_time_advances_only_forward_and_alarm_opens_when_fault_appears():
    svc = make()
    svc.advance_to(33.9 * DAY_S)
    assert svc.alarms(min_severity="ALARM") == []
    svc.advance_to(34.3 * DAY_S)
    rows = svc.alarms(min_severity="ALARM")
    p01 = [r for r in rows if r["panel_id"] == "P01"]
    assert len(p01) == 1 and p01[0]["kind"] == "loose_bolt" and p01[0]["phase"] == "L2"
    assert p01[0]["state"] == "open" and p01[0]["opened_t_s"] >= 34 * DAY_S
    before = svc.now_t_s
    svc.advance_to(20 * DAY_S)  # geri sarma yok
    assert svc.now_t_s == before


def test_alarm_pages_on_call_once_and_console_never_shows_the_ack_token():
    svc = make()
    svc.advance_to(34.3 * DAY_S)
    a = next(r for r in svc.alarms(min_severity="ALARM") if r["panel_id"] == "P01")
    assert "ack_token" not in a and "ack_token" not in svc.alarm_detail(a["id"])["alarm"]
    firsts = [m for m in svc.notifications(500) if m["alarm_id"] == a["id"] and m["kind"] == "first"]
    assert len(firsts) == 1 and "saha" in firsts[0]["role"]
    assert token_for(svc, a["id"]).isdigit()


def test_ack_needs_the_token_from_the_message_and_stops_further_pages():
    svc = make()
    svc.advance_to(34.3 * DAY_S)
    a = next(r for r in svc.alarms(min_severity="ALARM") if r["panel_id"] == "P01")
    with pytest.raises(AckError, match="belirteci hatalı"):
        svc.ack(a["id"], "0000" if token_for(svc, a["id"]) != "0000" else "1111", "Ayşe Yılmaz")
    with pytest.raises(AckError, match="kimlik"):
        svc.ack(a["id"], token_for(svc, a["id"]), " ")
    acked = svc.ack(a["id"], token_for(svc, a["id"]), "Ayşe Yılmaz")
    assert acked["state"] == "acked" and acked["acked_by"] == "Ayşe Yılmaz"
    sent_before = len(svc.notifications(500))
    svc.advance_to(34.9 * DAY_S)
    later = [m for m in svc.notifications(500)[: len(svc.notifications(500)) - sent_before] if m["alarm_id"] == a["id"]]
    assert all(m["kind"] not in ("reminder", "escalation") for m in later)


def test_close_requires_valid_reason_and_identity_and_unknown_alarm_is_404_class():
    svc = make()
    svc.advance_to(34.3 * DAY_S)
    a = next(r for r in svc.alarms(min_severity="ALARM") if r["panel_id"] == "P01")
    with pytest.raises(ValueError, match="gerekçesi"):
        svc.close(a["id"], "keyfim", "Ali")
    closed = svc.close(a["id"], "yanlis_alarm", "Ali")
    assert closed["state"] == "closed" and closed["close_reason"] == "yanlis_alarm"
    with pytest.raises(KeyError):
        svc.close("YOK-0001", "yanlis_alarm", "Ali")


def test_low_load_fault_does_not_flap_into_dozens_of_alarms_or_pages():
    """Regresyon: LOW_LOAD maskesi durumu sıfırlarken tek arıza 6,4 günde 179 mesaj üretmişti."""
    svc = make()
    svc.advance_to(40 * DAY_S)
    p02 = [r for r in svc.alarms(panel_id="P02") if r["kind"] == "loose_bolt"]
    assert len(p02) <= 2 and max(r["flaps"] for r in p02) <= 2
    firsts = [m for m in svc.notifications(500) if m["kind"] == "first" and m["alarm_id"].startswith("P02")]
    assert len(firsts) <= 2


def test_pd_alone_only_ever_yields_a_warning_alarm_and_no_page():
    svc = make()
    svc.advance_to(45 * DAY_S)
    p03 = svc.alarms(panel_id="P03")
    assert p03 and all(r["severity"] == "WARNING" and r["advisory"] for r in p03)
    assert not any(m["alarm_id"].startswith("P03") for m in svc.notifications(500))
    assert svc.suppression_summary("P03")[0]["advisory_capped"] > 0


def test_communication_loss_is_a_system_alert_that_never_pages():
    svc = make()
    svc.advance_to(41 * DAY_S)  # dropout 38-40 (96 örnek = 24 sa sonra ALARM seviyesi)
    system = [r for r in svc.alarms(panel_id="P05") if r["category"] == "sistem"]
    assert system and system[0]["kind"] == "comms_lost"
    assert not any(m["alarm_id"].startswith("P05") and m["status"] == "sent" for m in svc.notifications(500))
    assert svc.suppression_summary("P05")[0]["reasons"].get("STALE", 0) > 0


def test_arc_trip_is_critical_pages_two_tiers_and_is_latching():
    svc = make()
    svc.advance_to(35.2 * DAY_S)
    trip = next(r for r in svc.alarms() if r["panel_id"] == "P06" and r["kind"] == "arc_trip")
    assert trip["severity"] == "CRITICAL" and trip["latching"] is True
    firsts = [m for m in svc.notifications(500) if m["alarm_id"] == trip["id"] and m["kind"] == "first"]
    assert len(firsts) == 2  # KRİTİK: ilk iki kademe aynı anda


def test_alarm_list_filters_and_priority_sort_put_critical_first():
    svc = make()
    svc.advance_to(36 * DAY_S)
    rows = svc.alarms(state="active")
    assert rows and rows[0]["severity"] == "CRITICAL"
    only_bolt = svc.alarms(kind="loose_bolt")
    assert only_bolt and all(r["kind"] == "loose_bolt" for r in only_bolt)
    assert all(r["panel_id"] == "P06" for r in svc.alarms(panel_id="P06"))
    by_panel = svc.alarms(sort="panel")
    assert [r["panel_id"] for r in by_panel] == sorted(r["panel_id"] for r in by_panel)


def test_alarm_detail_carries_evidence_work_order_and_messages():
    svc = make()
    svc.advance_to(34.5 * DAY_S)
    a = next(r for r in svc.alarms(min_severity="ALARM") if r["panel_id"] == "P01")
    d = svc.alarm_detail(a["id"])
    ev = d["evidence"]
    assert ev["track_key"] == "loose_bolt:L2" and ev["thresholds"] == {"WARNING": 15.0, "ALARM": 30.0, "CRITICAL": 60.0}
    assert len(ev["t_s"]) == len(ev["score"]) == len(ev["severity"]) > 10
    wo = d["work_order"]
    assert wo["needs_outage"] is True and wo["priority"] in ("Yüksek", "ACİL") and any("kesinti" in step.lower() for step in wo["steps"])
    assert wo["location"] == "Konum 1" and d["messages"]


def test_panel_series_is_hourly_and_consistent_across_channels():
    svc = make()
    svc.advance_to(35 * DAY_S)
    s = svc.panel_series("P01", days=3)
    n = len(s["t_s"])
    assert 60 < n <= 73 and s["t_s"][1] - s["t_s"][0] == 3600.0
    for series in (s["ambient_c"], s["humidity_rh"], s["pd_index"], s["dew_margin_c"], s["neutral_current_a"]):
        assert len(series) == n
    assert len(s["current_a"]["L2"]) == len(s["joint_temp_c"]["L2"]) == n
    assert {"loose_bolt:L2", "overload", "condensation", "pd_tracking", "arc_trip"} <= set(s["tracks"])
    assert 1000.0 < s["theta_tau_s"] < 3000.0


def test_storm_is_detected_and_rate_limit_produces_single_digest():
    policy = EscalationPolicy(rate_limit_per_hour=3)
    svc = make(policy=policy)
    svc.advance_to(31 * DAY_S)
    assert not svc.storms()["active"]
    svc.inject_storm(list(svc.panels), scenario_key="arc_integrity_fault")
    svc.advance_to(31 * DAY_S + 1.5 * 3600.0)  # alarmlar ~45 dk sonra açılır
    storms = svc.storms()
    assert storms["active"] and storms["episodes"][0]["count"] >= 5
    limited = [m for m in svc.notifications(500) if m["status"] == "rate_limited"]
    assert limited, "alıcı başına saatlik sınır devreye girmeli"
    assert svc.kpis()["storm_active"] is True
    svc.advance_to(31 * DAY_S + 5 * 3600.0)
    assert any(m["kind"] == "digest" for m in svc.notifications(500))
    assert svc.storms()["active"] is False  # olay penceresi kapandı, fırtına sönmüş


def test_inject_and_clear_change_a_panel_at_runtime_and_close_old_alarms():
    svc = make()
    svc.advance_to(31 * DAY_S)
    state = svc.inject("P04", "loose_bolt_abrupt", onset_in_s=3600.0)
    assert state["revision"] == 1 and state["scenario_key"] == "loose_bolt_abrupt"
    svc.advance_to(31.5 * DAY_S)
    injected = [r for r in svc.alarms(panel_id="P04") if r["kind"] == "loose_bolt" and r["severity"] in ("ALARM", "CRITICAL")]
    assert injected and injected[0]["id"].startswith("P04r1-")
    cleared = svc.clear("P04")
    assert cleared["revision"] == 2
    old = svc.alarms(panel_id="P04", state="closed")
    assert any(r["close_reason"] == "diger" and "senaryo değiştirildi" in r["closed_by"] for r in old)
    with pytest.raises(KeyError):
        svc.inject("P04", "olmayan_senaryo")
    with pytest.raises(ValueError):
        make().inject("P04", "loose_bolt_abrupt", onset_in_s=40 * DAY_S)  # pencere sonu


def test_inject_before_baseline_is_learned_is_rejected():
    svc = FleetService(SPECS, wall=FakeWall(), start_t_s=10 * DAY_S)
    with pytest.raises(ValueError, match="taban çizgisi"):
        svc.inject("P04", "loose_bolt_abrupt")


def test_engine_level_mute_suppresses_alarm_below_critical():
    svc = make()
    svc.mute("P02", "loose_bolt", minutes=20 * 24 * 60, by="Ali", reason="planlı bakım penceresi")
    svc.advance_to(40 * DAY_S)
    assert [r for r in svc.alarms(panel_id="P02") if r["kind"] == "loose_bolt"] == []
    assert svc.suppression_summary("P02")[0]["muted_events"] > 0 and svc.suppression_summary("P02")[0]["mutes"] == ["loose_bolt"]
    with pytest.raises(ValueError):
        svc.mute("P02", "loose_bolt", minutes=5, by="Ali", reason="")


def test_person_silence_skips_that_person():
    svc = make()
    first_recipient = None
    svc.advance_to(30 * DAY_S)
    svc.silence("Gece nöbetçisi (Kemal D.)", minutes=10 * 24 * 60, by="Zeynep A.")
    svc.advance_to(34.3 * DAY_S)
    msgs = [m for m in svc.notifications(500) if m["alarm_id"].startswith("P01")]
    assert any(m["status"] == "silenced" for m in msgs)
    assert any(m["status"] == "sent" and m["to"] != "Gece nöbetçisi (Kemal D.)" for m in msgs)


def test_sim_clock_runs_from_wall_time_and_never_rewinds():
    wall = FakeWall()
    svc = FleetService(SPECS, wall=wall, speed=3600.0)
    start = svc.clock_state()["day"]
    svc.set_clock(running=True)
    wall.t += 24.0  # 24 gerçek sn x 3600 = 24 sim saati
    assert svc.sync() >= (start + 0.99) * DAY_S
    assert svc.clock_state()["day"] == pytest.approx(start + 1.0, abs=0.02)
    svc.set_clock(speed=86400.0)  # 1 gerçek sn = 1 sim günü
    wall.t += 2.0
    svc.sync()
    assert svc.clock_state()["day"] == pytest.approx(start + 3.0, abs=0.02)
    svc.set_clock(jump_to_day=10.0)  # geri sarma yok: mevcut andan geri gidilmez
    assert svc.clock_state()["day"] >= start + 3.0 - 0.02
    svc.set_clock(jump_to_day=200.0)
    assert svc.clock_state()["day"] == pytest.approx(svc.clock_state()["end_day"], abs=0.02)
    assert svc.clock_state()["running"] is False  # pencere sonu
    with pytest.raises(ValueError):
        svc.set_clock(speed=0)


def test_reset_returns_to_initial_state():
    svc = make()
    svc.advance_to(36 * DAY_S)
    assert svc.alarms()
    svc.reset()
    assert svc.alarms() == [] and svc.clock_state()["day"] == pytest.approx(30.0, abs=0.02)
    assert svc.notifications() == []


def test_simclock_unit_behaviour():
    wall = FakeWall()
    c = SimClock(100.0, speed=10.0, running=False, wall=wall)
    wall.t = 5.0
    assert c.now() == 100.0  # durmuş saat ilerlemez
    c.set(running=True)
    wall.t = 8.0
    assert c.now() == pytest.approx(130.0)
    c.set(running=False)
    wall.t = 50.0
    assert c.now() == pytest.approx(130.0)
