"""Canonical channel (metric) registry.

Everything that flows through PANO GOZ is one of these channels.  The simulator
produces them, the envelope carries them, the store persists them, the detector
consumes them and the UI labels them.  Adding a channel anywhere else is a bug.

Naming rule: ``<domain>.<quantity>`` in lower snake case, ASCII only.  The
Turkish label lives in ``label_tr`` so the code stays language-neutral while the
operator sees Turkish.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Kind = Literal["measured", "derived", "state"]


@dataclass(frozen=True)
class Channel:
    name: str
    unit: str
    label_tr: str
    kind: Kind
    #: Decimal places the UI should show.  Also the quantisation the simulator
    #: applies, so a value never displays more precision than the sensor has.
    decimals: int = 2
    #: Physically plausible range.  The ingest layer rejects anything outside
    #: this, which is how a stuck or garbage sensor is caught at the edge
    #: instead of poisoning a baseline.
    lo: float | None = None
    hi: float | None = None
    source: str = ""


def _c(*args, **kw) -> Channel:
    return Channel(*args, **kw)


CHANNELS: tuple[Channel, ...] = (
    # ---- thermal clip (TC) --------------------------------------------------
    _c("tc.temp_c", "°C", "Kablo yüzey sıcaklığı", "measured", 2, -40, 150,
       "TMP117, ±0.1 °C, 1 kV kablo kılıfı üzerinde"),
    _c("tc.current_a", "A", "Damar akımı", "measured", 1, 0, 1200,
       "Ayrılabilir CT, kelepçenin içinde, aynı damarda"),
    # ---- thermal array (TN-IR) ---------------------------------------------
    _c("ir.lug_temp_c", "°C", "Pabuç sıcaklığı", "measured", 2, -40, 200,
       "MLX90640 32x24, düğümde 48 pabuç ortalamasına indirgenir"),
    _c("ir.air_top_c", "°C", "Bölme üstü hava", "measured", 2, -40, 120, "SHT41"),
    _c("ir.aim_ok", "-", "Nişan doğrulama", "state", 0, 0, 1,
       "Üç sabit referans noktası; kayarsa AIM_SHIFTED"),
    # ---- RF / environment node (PD) ----------------------------------------
    _c("pd.rate_per_s", "1/s", "Darbe hızı", "measured", 1, 0, 100000, "HFCT + AD8318 + komparatör"),
    _c("pd.qmax_db", "dB", "Tepe genlik", "measured", 1, 0, 80, "AD8318, 24 mV/dB"),
    _c("pd.nqn", "-", "Normalize gürültü sayısı", "derived", 1, 0, 10000, ""),
    _c("pd.class", "-", "PRPD sınıfı", "state", 0, 0, 4,
       "0 GURULTU · 1 BOSLUK · 2 YUZEY · 3 KORONA · 4 YUZEN"),
    _c("pd.tev_db", "dB", "TEV seviyesi", "measured", 1, 0, 60, "PCB kapasitif plaka"),
    _c("pd.ultrasonic_db", "dB", "Ultrasonik 40 kHz", "measured", 1, 0, 60, "MA40S4R"),
    _c("env.air_c", "°C", "Bölme havası", "measured", 2, -40, 120, "SHT41"),
    _c("env.rh_pct", "%", "Bağıl nem", "measured", 1, 0, 100, "SHT41"),
    _c("env.dewpoint_c", "°C", "Çiy noktası", "derived", 2, -60, 80,
       "Magnus-Tetens, Alduchov-Eskridge a=17.62 b=243.12"),
    _c("env.wall_c", "°C", "Tahmini yüzey sıcaklığı", "derived", 2, -40, 120,
       "Dış ortamın 90 dakikalık birinci derece gecikmesi"),
    _c("env.condensation_margin_k", "K", "Yoğuşma payı", "derived", 2, -40, 60, ""),
    # ---- energy analyser (Entes MPR-53CS over RS-485) -----------------------
    _c("mpr.v_l1_v", "V", "L1 faz gerilimi", "measured", 1, 0, 520, "MPR-53CS reg 0"),
    _c("mpr.v_l2_v", "V", "L2 faz gerilimi", "measured", 1, 0, 520, "MPR-53CS reg 2"),
    _c("mpr.v_l3_v", "V", "L3 faz gerilimi", "measured", 1, 0, 520, "MPR-53CS reg 4"),
    _c("mpr.i_l1_a", "A", "L1 faz akımı", "measured", 1, 0, 3000, "MPR-53CS reg 6"),
    _c("mpr.i_l2_a", "A", "L2 faz akımı", "measured", 1, 0, 3000, "MPR-53CS reg 8"),
    _c("mpr.i_l3_a", "A", "L3 faz akımı", "measured", 1, 0, 3000, "MPR-53CS reg 10"),
    _c("mpr.i_n_a", "A", "Nötr akımı", "measured", 1, 0, 3000, "MPR-53CS reg 12"),
    _c("mpr.freq_hz", "Hz", "Frekans", "measured", 2, 40, 70, "MPR-53CS reg 58"),
    _c("mpr.thd_v_l1_pct", "%", "L1 gerilim THD", "measured", 1, 0, 99.9, "MPR-53CS reg 72"),
    _c("mpr.thd_v_l2_pct", "%", "L2 gerilim THD", "measured", 1, 0, 99.9, "MPR-53CS reg 74"),
    _c("mpr.thd_v_l3_pct", "%", "L3 gerilim THD", "measured", 1, 0, 99.9, "MPR-53CS reg 76"),
    _c("mpr.thd_i_l1_pct", "%", "L1 akım THD", "measured", 1, 0, 99.9, "MPR-53CS reg 78"),
    _c("mpr.thd_i_l2_pct", "%", "L2 akım THD", "measured", 1, 0, 99.9, "MPR-53CS reg 80"),
    _c("mpr.thd_i_l3_pct", "%", "L3 akım THD", "measured", 1, 0, 99.9, "MPR-53CS reg 82"),
    _c("mpr.p_total_w", "W", "Toplam aktif güç", "measured", 0, -3e6, 3e6, "MPR-53CS reg 46"),
    _c("mpr.online", "-", "Analizör haberleşmesi", "state", 0, 0, 1, ""),
    # ---- arc protection (ABB TVOC-2 over RS-485) ---------------------------
    _c("tvoc.system_state", "-", "Sistem durumu", "state", 0, 0, 65535, "TVOC-2 reg 1300"),
    _c("tvoc.active_trip", "-", "Aktif açma", "state", 0, 0, 1, "reg 1300 bit0"),
    _c("tvoc.active_error", "-", "Aktif hata", "state", 0, 0, 1, "reg 1300 bit1"),
    _c("tvoc.detectors_ok", "-", "Sağlam dedektör sayısı", "derived", 0, 0, 30,
       "reg 222/223 bit sayımı, yalnız FW >= 03.00.00"),
    _c("tvoc.detectors_total", "-", "Kurulu dedektör", "derived", 0, 0, 30, ""),
    _c("tvoc.ambient_warn", "-", "Ortam ışığı uyarısı", "state", 0, 0, 30, "reg 224/225"),
    _c("tvoc.last_selftest_days", "gün", "Son otokontrolden beri", "derived", 0, 0, 3650, "reg 220/221"),
    _c("tvoc.online", "-", "Ark rölesi haberleşmesi", "state", 0, 0, 1, ""),
    # The 30-bit detector location map and the trip relay.  These are the
    # registers that turn "there was an arc somewhere in the substation" into
    # "detector X2:3, cable compartment, relay K5", which is the difference
    # between a crew searching a panel and a crew walking to a compartment.
    _c("tvoc.detector_map_lo", "-", "Dedektör haritası (düşük)", "state", 0, 0, 65535,
       "TVOC-2 reg 210 · bit0-9 X1:1-10, bit10-14 X2:1-5"),
    _c("tvoc.detector_map_hi", "-", "Dedektör haritası (yüksek)", "state", 0, 0, 65535,
       "TVOC-2 reg 211 · bit0-4 X2:6-10, bit5-14 X3:1-10"),
    _c("tvoc.trip_relay", "-", "Açma rölesi", "state", 0, 0, 7,
       "TVOC-2 reg 212 · bit0 K4, bit1 K5, bit2 K6"),
    # ---- derived detector outputs ------------------------------------------
    _c("det.theta_k", "K", "θ · anma akımında sıcaklık fazlası", "derived", 2, -50, 300,
       "[T - diğer fazların medyanı] / (I/I_ref)²"),
    _c("det.theta_min_k", "K", "Görülebilir en küçük θ", "derived", 2, 0, 1000,
       "3σ / f² · yük düştükçe büyür"),
    _c("det.sensitivity_pct", "%", "Görünürlük", "derived", 0, 0, 100, ""),
    _c("det.excess_r_uohm", "µΩ", "Fazla temas direnci", "derived", 1, -100, 5000,
       "θ / (R_th · I_ref²), R_th aralığıyla birlikte raporlanır"),
    _c("det.cusum", "-", "CUSUM istatistiği", "derived", 2, 0, 200, "k=0.5 h=8"),
    _c("det.slope_k_per_week", "K/hafta", "θ eğimi", "derived", 3, -20, 20, ""),
    _c("det.health_index", "-", "Sağlık endeksi", "derived", 0, 0, 100, ""),
    # ---- device health -----------------------------------------------------
    _c("dev.rssi_dbm", "dBm", "Sinyal seviyesi", "measured", 0, -140, 0, ""),
    _c("dev.battery_v", "V", "Pil gerilimi", "measured", 3, 0, 4.5, "Li-SOCl2 3.6 V nominal"),
    _c("dev.battery_pct", "%", "Tahmini pil ömrü", "derived", 0, 0, 100, ""),
    _c("dev.uptime_s", "s", "Çalışma süresi", "measured", 0, 0, 1e9, ""),
    _c("dev.seq", "-", "Çerçeve sayacı", "state", 0, 0, 4294967295, ""),
    _c("dev.temp_mcu_c", "°C", "MCU sıcaklığı", "measured", 1, -50, 130, ""),
    _c("dev.period_s", "s", "Beklenen yayın aralığı", "state", 0, 1, 86400,
       "Düğümün bir sonraki yayına kadar geçmesini beklediği süre; "
       "sunucunun tazelik pencereleri bu sayıdan türetilir"),
)

#: Firmware cadence table, mirrored from ``firmware/node/node.h``.
#:
#: ``PG_PERIOD_IDLE_S``/``WATCH``/``BURST``.  The node picks one of these three
#: with a 2-up/4-down hysteresis and reports the choice in the frame's
#: ``cadence`` field; this table is how the server turns that enum back into
#: seconds.  It is duplicated rather than derived because the two sides are
#: separately compiled artefacts, and :mod:`tests.test_cadence_regression`
#: fails if they drift apart.
CADENCE_PERIOD_S: dict[str, float] = {
    "IDLE": 900.0,
    "WATCH": 60.0,
    "BURST": 10.0,
}

#: ``pg_cadence_t`` enum value -> name, in firmware order.
CADENCE_BY_CODE: tuple[str, ...] = ("IDLE", "WATCH", "BURST")

BY_NAME: dict[str, Channel] = {c.name: c for c in CHANNELS}


def get(name: str) -> Channel:
    try:
        return BY_NAME[name]
    except KeyError as exc:  # pragma: no cover - programmer error
        raise KeyError(
            f"unknown channel {name!r}; add it to panogoz.contracts.channels"
        ) from exc


def validate(name: str, value: float) -> bool:
    """True when the value is physically plausible for this channel."""
    ch = BY_NAME.get(name)
    if ch is None:
        return False
    if value != value:  # NaN
        return False
    if ch.lo is not None and value < ch.lo:
        return False
    if ch.hi is not None and value > ch.hi:
        return False
    return True


def quantise(name: str, value: float) -> float:
    ch = BY_NAME.get(name)
    if ch is None:
        return value
    return round(value, ch.decimals)


# --------------------------------------------------------------------------
# PRPD classes
# --------------------------------------------------------------------------

PRPD_CLASSES = ("GURULTU", "BOSLUK", "YUZEY", "KORONA", "YUZEN")
PRPD_LABELS_TR = {
    "GURULTU": "Gürültü",
    "BOSLUK": "İç boşluk deşarjı",
    "YUZEY": "Yüzey kaçağı",
    "KORONA": "Korona",
    "YUZEN": "Yüzen elektrot / gevşek bağlantı",
}

# --------------------------------------------------------------------------
# Failure modes and their fusion weights
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class FailureMode:
    key: str
    label_tr: str
    weight: float
    action_tr: str


FAILURE_MODES: tuple[FailureMode, ...] = (
    FailureMode("loose_connection", "Gevşek bağlantı", 0.30,
                "Bağlantıyı tork anahtarı ile yeniden sıkın, temas yüzeyini kontrol edin"),
    FailureMode("overload", "Aşırı yük", 0.15,
                "Yük profilini inceleyin, fider dengeleme veya kapasite artırımı planlayın"),
    FailureMode("arc_integrity", "Ark koruma bütünlüğü", 0.15,
                "Ark dedektörlerini kontrol edin, otokontrol sonucunu doğrulayın"),
    FailureMode("thermal_runaway", "Isıl kaçış / soğutma kaybı", 0.10,
                "Havalandırma menfezlerini ve filtreleri kontrol edin"),
    FailureMode("harmonic_neutral", "Harmonik nötr yüklenmesi", 0.10,
                "3. harmonik seviyesini ölçün, filtre veya dengeleme değerlendirin"),
    FailureMode("moisture", "Nem / yoğuşma", 0.10,
                "Kablo kanalı sızdırmazlığını ve varsa ısıtıcıyı kontrol edin"),
    FailureMode("insulation", "Yalıtım zayıflaması", 0.10,
                "PD trendini izleyin, planlı kesintide yalıtım ölçümü yapın"),
)

MODES_BY_KEY: dict[str, FailureMode] = {m.key: m for m in FAILURE_MODES}

# Weights must sum to 1 so ln(HI/100) decomposes exactly into a waterfall.
assert abs(sum(m.weight for m in FAILURE_MODES) - 1.0) < 1e-9

# --------------------------------------------------------------------------
# Severity ladder
# --------------------------------------------------------------------------

SEVERITIES = ("BILGI", "IZLE", "UYARI", "KRITIK", "ACIL")

SEVERITY_RANK = {s: i for i, s in enumerate(SEVERITIES)}

SEVERITY_TR = {
    "BILGI": "Bilgi",
    "IZLE": "İzle",
    "UYARI": "Uyarı",
    "KRITIK": "Kritik",
    "ACIL": "Acil",
}

#: Seviye adinin YONELME hali ("KRITIK'e 21 gun").  Turkce'de ek unlu uyumuna
#: gore degisir ve tek bir "'e" ile gecistirilemez: UYARI'ya, IZLE'ye, KRITIK'e,
#: ACIL'e.  Ufuk projeksiyonunun cumlesi bu tabloyu kullanir; "UYARI'e" yazan
#: bir arayuz, kendi dilini bilmeyen bir arayuzdur.
SEVERITY_DATIVE_TR = {
    "BILGI": "BILGI'ye",
    "IZLE": "IZLE'ye",
    "UYARI": "UYARI'ya",
    "KRITIK": "KRITIK'e",
    "ACIL": "ACIL'e",
}

#: Operational meaning of each level.  These are shown in the UI next to the
#: badge so an operator never has to guess what a colour means.
SEVERITY_ACTION_TR = {
    "BILGI": "Kayda alınır, aksiyon yok",
    "IZLE": "Haftalık özet listesine girer, ekip çıkmaz",
    "UYARI": "İş emri açılır, bir sonraki planlı ziyarette doğrulanır",
    "KRITIK": "7 gün içinde saha ziyareti, yük aktarımı planlanır",
    "ACIL": "Derhal ekip yönlendirilir, SMS ve sesli arama tetiklenir",
}

#: Only these two escalate to a person's phone.  Everything else is a queue
#: item.  This single rule is what keeps the system switched on after month
#: three, so it is a contract, not a configuration value.
DISPATCH_SEVERITIES = ("KRITIK", "ACIL")


if __name__ == "__main__":  # pragma: no cover
    print(f"{len(CHANNELS)} channels")
    for c in CHANNELS:
        print(f"  {c.name:<26} {c.unit:<8} {c.kind:<9} {c.label_tr}")
