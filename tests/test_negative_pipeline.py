"""Negative controls, run through the real pipeline rather than asserted.

The previous version of this check read ``expect_alarm`` out of the scenario
dictionary and asserted that the dictionary said what the dictionary said.  That
passes on a system whose detector is switched off.

Every case here drives the shipped chain - simulator, gateway, detector,
suppression, fusion, alarm manager - over enough history for a defect to be
provable, and then looks at the incidents that came out.  The positive control
in this file is what gives the negative ones their meaning: it proves the same
harness, at the same settings, does raise an incident when the panel really is
degrading.  Without it, "no alarm" would be indistinguishable from "no detector".
"""
import tempfile

import pytest

from panogoz.api import runtime as rtmod
from panogoz.rules import pipeline
from panogoz.sim import faults as fx

#: Enough history for the CUSUM to confirm a drift and for the 3-of-5 debounce
#: to have five day-buckets to look at.  Below this the positive control stops
#: firing, which is checked rather than assumed.
BACKFILL_DAYS = 40

#: When each negative scenario is started, so that it is STILL RUNNING at the
#: instant the panel is evaluated.  A heat wave that ended yesterday proves
#: nothing about how the detector behaves during a heat wave.
ACTIVE_AGO_DAYS = {
    "sensor_takildi": 1.0,        # clip froze 23 h ago, still frozen
    "sensor_kaydi": 3.0,          # 3 days of 0.35 K/day sensor drift
    "dugum_sessiz": 0.4,          # node went quiet ~9 h ago
    "sicak_hava_dalgasi": 3.0,    # day 3 of a 6-day wave
    "sebeke_olayi": 0.3,          # 7 h into a 30 h upstream disturbance
    "trafo_devreye_alma": 0.03,   # energisation pulse ~43 min ago
    "pano_enerjisiz": 0.05,       # 72 min into a 4 h outage
}

#: The flagship defect, with the injection strength the demo ships.
LOOSE_CONNECTION = {
    "index": 14, "scenario": "gevsek_baglanti", "ago_days": 41.0,
    "kw": {"joint_key": "C07-L2-PABUC", "rate_k_per_week": 4.00,
           "cap_uohm": 900.0},
    "why_tr": "pozitif kontrol",
}

_PORT = iter(range(15840, 15960))


def run_panel(monkeypatch, scenarios):
    """Bootstrap the real runtime with exactly ``scenarios`` seeded."""
    monkeypatch.setattr(rtmod, "DEMO_SCENARIOS", tuple(scenarios))
    pipeline.reset()
    rt = rtmod.Runtime(n_panels=3, seed=42, db_path=tempfile.mktemp(suffix=".db"),
                       backfill_days=BACKFILL_DAYS, scada_port=next(_PORT),
                       quiet=True)
    try:
        rt.bootstrap()
        return rt.panel(rtmod.DEMO_PANEL)
    finally:
        rt.stop()
        pipeline.reset()


def modes(live):
    return [(a.severity, a.mode, a.joint_key) for a in live.alarms]


def test_positive_control_raises_an_incident(monkeypatch):
    """The measuring stick.  Every negative case below is read against this."""
    live = run_panel(monkeypatch, [LOOSE_CONNECTION])
    loose = [a for a in live.alarms if a.mode == "loose_connection"]
    assert loose, f"pozitif kontrol alarm üretmedi: {modes(live)}"
    assert loose[0].joint_key == "C07-L2-PABUC"

    # Ölçü çubuğunun ikinci yarısı: projeksiyon da ÇIKMALI. Onsuz negatif
    # kontrollerdeki "ağır hedefe projeksiyon yok" iddiası, projeksiyonu hiç
    # hesaplamayan bir sürümde de geçerdi.
    hit = [j for j in live.joints if j.key == "C07-L2-PABUC"]
    assert hit, "pozitif kontrolün bağlantısı görünümde yok"
    eta = hit[0].eta
    assert eta.reason == "", f"pozitif kontrolde projeksiyon susturuldu: {eta.reason}"
    assert eta.days is not None and eta.target, "pozitif kontrolde gün yok"
    assert eta.slope_k_per_week > 0.0
    assert live.eta.days is not None and live.eta.target, "pano düzeyine yükselmedi"


@pytest.mark.parametrize("name", fx.NEGATIVE_CONTROLS)
def test_negative_control_opens_no_incident_or_horizon(monkeypatch, name):
    spec = fx.SCENARIOS[name]
    live = run_panel(monkeypatch, [{
        "index": 14, "scenario": name,
        "ago_days": ACTIVE_AGO_DAYS[name], "kw": {}, "why_tr": "negatif kontrol",
    }])
    forbidden = [a for a in live.alarms if a.mode in spec.get("forbid_modes", ())]
    assert not forbidden, f"{name} yasak modda alarm açtı: {forbidden}"
    assert not live.alarms, f"{name} pano alarmı açtı: {modes(live)}"

    # AYNI koşumun ikinci iddiası: ekip yola çıkaracak bir projeksiyon da yok.
    # Ayrı bir test yazmak bu bootstrap'ı yedi kez daha kurardı; kanıt aynı,
    # bedeli iki katı olurdu.
    #
    # Ölçülen davranış: sağlıklı bir pabuç, gürültü seviyesinde pozitif bir
    # eğimle IZLE eşiğine 117-211 gün mesafede görünebilir. Bu bir alarm
    # değildir ve öyle de sunulmaz - 90 gün tavanının üstünde olduğu için
    # ekranda ">90 g" yazar, bir tarih yazmaz. §8'in merdiveninde IZLE zaten
    # "haftalık özet listesine girer, ekip çıkmaz" demektir. Sözleşme bu yüzden
    # "projeksiyon yok" değil, ikisi birden: ağır hedefe projeksiyon yok, VE
    # tavanın altında (takvime yazılabilir) gün yok.
    heavy = [(j.key, j.eta.target, j.eta.days) for j in live.joints
             if j.eta.days is not None
             and j.eta.target in ("UYARI", "KRITIK", "ACIL")]
    assert not heavy, f"{name} ağır hedefe projeksiyon üretti: {heavy}"
    soon = [(j.key, j.eta.target, j.eta.days) for j in live.joints
            if j.eta.days is not None and not j.eta.capped]
    assert not soon, f"{name} takvime yazılabilir bir gün verdi: {soon}"
    # Gerekçe boş ISE VE YALNIZ ISE gün dolu. Sessiz boşluk yok.
    for jv in live.joints:
        if jv.eta.reason:
            assert jv.eta.days is None, f"{name}: {jv.key} gerekçe VE gün taşıyor"
        else:
            assert jv.eta.days is not None, (
                f"{name}: {jv.key} ne gerekçe ne gün taşıyor")


def test_every_negative_control_is_covered():
    """A scenario added to the contract must be exercised, not just declared."""
    assert set(ACTIVE_AGO_DAYS) == set(fx.NEGATIVE_CONTROLS)


def test_grid_event_does_not_hide_a_real_defect_underneath_it(monkeypatch):
    """The counter-scenario, and the reason suppression is dangerous.

    An upstream disturbance and a loosening bolt are not mutually exclusive, and
    the disturbance is exactly when a marginal joint is most likely to fail.  A
    suppression rule that explains away the whole panel because the voltage THD
    moved would delete the one incident that mattered.
    """
    live = run_panel(monkeypatch, [
        LOOSE_CONNECTION,
        {"index": 14, "scenario": "sebeke_olayi", "ago_days": 0.3,
         "kw": {"duration_h": 120.0}, "why_tr": "eşzamanlı şebeke olayı"},
    ])
    loose = [a for a in live.alarms if a.mode == "loose_connection"]
    assert loose, (
        "eşzamanlı şebeke olayı gerçek gevşek bağlantıyı sildi: "
        f"alarms={modes(live)} suppressed={[s.reason for s in live.suppressed]}")
    assert loose[0].joint_key == "C07-L2-PABUC"
