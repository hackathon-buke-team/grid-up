"""K4 4.3 -- expect_flags sozlesme acliklari: STALE, SENSOR_DRIFT, DE_ENERGISED.

CLAUDE.md Sec.2: cihaz yayin araligi sozlesmeden (`dev.period_s`) turetiliyor.
Bu modul o sozlesmenin cihaz-duzeyinde dogru kurulup kurulmadigini kontrol
eden uc bagimsiz bayragi tanimlar -- hicbiri theta.py'nin kendi "dusuk yuk,
theta hesaplanamaz" (`MIN_LOAD_FRACTION=0.40`, bkz. panogoz.detector.theta)
durumuyla KARISTIRILMAMALI: o durum "veri var ama normalize etmek icin cok
dusuk yuk, theta=None" demek -- baglanti hala enerjili. DE_ENERGISED ise cok
daha siki bir esikle (`DE_ENERGISED_MAX_LOAD_FRACTION`, varsayilan 0.02 --
theta'nin 0.40'indan kasitli olarak cok daha kucuk) gercekten sifira yakin
akimi, yani kesicinin acik/besleme yok olma ihtimalini yakalar.
"""
from __future__ import annotations

from enum import Enum


class Flag(Enum):
    STALE = "STALE"
    SENSOR_DRIFT = "SENSOR_DRIFT"
    DE_ENERGISED = "DE_ENERGISED"


# "Stale" sayilmasi icin son ornekten bu yana gecen surenin dev.period_s'in
# kac kati olmasi gerektigi -- 3x, tek bir kacirilan orneği (agdaki gecici
# bir aksama) yanlis alarma cevirmeden gercek bir kesintiyi yakalar.
DEFAULT_STALE_FACTOR = 3.0

# theta.py'deki MIN_LOAD_FRACTION (0.40) "theta guvenilir hesaplanamaz" demek,
# "enerjisiz" degil. DE_ENERGISED bilinctli olarak COK daha siki: gercek
# sifira yakin akim (rated'in %2'sinin altinda) -- kesici acik/besleme yok
# senaryosunu, "sadece hafif yuklu" senaryosundan ayirmak icin.
DE_ENERGISED_MAX_LOAD_FRACTION = 0.02


def is_stale(
    last_sample_t_s: float,
    now_t_s: float,
    period_s: float,
    *,
    factor: float = DEFAULT_STALE_FACTOR,
) -> bool:
    if period_s <= 0:
        raise ValueError("period_s pozitif olmali")
    return (now_t_s - last_sample_t_s) > factor * period_s


def is_de_energised(
    current_a: float,
    rated_current_a: float,
    *,
    max_load_fraction: float = DE_ENERGISED_MAX_LOAD_FRACTION,
) -> bool:
    if rated_current_a <= 0:
        raise ValueError("rated_current_a pozitif olmali")
    return current_a < max_load_fraction * rated_current_a


def flags_for_connection(
    *,
    last_sample_t_s: float,
    now_t_s: float,
    period_s: float,
    current_a: float,
    rated_current_a: float,
    sensor_drift_detected: bool,
    stale_factor: float = DEFAULT_STALE_FACTOR,
    de_energised_max_load_fraction: float = DE_ENERGISED_MAX_LOAD_FRACTION,
) -> set[Flag]:
    """Uc bayragi birlestirir. `sensor_drift_detected` cagiran tarafca
    ayrica hesaplanir (bkz. panogoz.detector.cusum.cusum_changepoint) --
    bu fonksiyon CUSUM'u kendi calistirmiyor, yalnizca sonucu birlestiriyor
    (gunluk-agregasyon gerektiren CUSUM ile anlik bayrak kontrolunun farkli
    veri ihtiyaclarini ayri tutmak icin)."""
    flags: set[Flag] = set()
    if is_stale(last_sample_t_s, now_t_s, period_s, factor=stale_factor):
        flags.add(Flag.STALE)
    if is_de_energised(current_a, rated_current_a, max_load_fraction=de_energised_max_load_fraction):
        flags.add(Flag.DE_ENERGISED)
    if sensor_drift_detected:
        flags.add(Flag.SENSOR_DRIFT)
    return flags
