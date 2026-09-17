"""Bir sonraki seviye basamagina kalan gun.

Neden bu modul var
------------------
Urun "haftalar once haber veririm" diyor ve bunu kanitliyor: CUSUM surukelenmeyi
teyit ediyor, changepoint bozulmanin BASLADIGI gunu tarihliyor, theta_delta son
yedi gunun hareketini gosteriyor.  Uc sayinin hepsi GECMISE bakiyor.  Bakim
planlayicisinin sordugu soru ise ileriye bakar::

    "Bu pabuc ne zaman benim sorunum olacak?"

Cevap elimizdeki verinin icinde duruyor.  ``slope_per_week()`` zaten K/hafta
cinsinden bir egim veriyor; eksik olan egimin BELIRSIZLIGI ve sayi vermeyi
REDDETME kurallariydi.  Bu modul yeni bir kestirici degildir; var olan
kestiriciyi bir tarihe cevirir.

Fayda iddiasi sinirlidir ve boyle satilir: bir is emrinin bu haftaya mi gelecek
aya mi yazilacagina karar vermeye yeter.  Bir kesinti tarihini bu sayiya gore
planlamaya YETMEZ.

Yontem
------
Hedef, theta'nin GUNLUK degerinin bulundugu bandin bir ustudur.  Kalan kelvin,
egimin guven araliginin uc ucuna bolunur::

    gun_med = kalan_K * 7 / egim_med
    gun_lo  = kalan_K * 7 / egim_hi      (hizli uc -> az gun)
    gun_hi  = kalan_K * 7 / egim_lo      (yavas uc -> cok gun)

``egim_lo <= 0`` ise ust gun sinirsizdir.  Bu, "yukseliyor olabilir de olmayabilir
de" cumlesinin matematikten cikan halidir; elle yazilan bir uyari degildir.

Susma
-----
Kapilar sirayla degerlendirilir, ilk tutan kazanir.  Kapilarin varligi bu
modulun urun olan kismidir: her zaman bir tarih veren bir kestirici, saglikli
bir baglanti icin de tarih verir ve bir ekip bosa gittiginde sistem kapatilir.

Sozlesme tek cumleyle: ``reason`` bos ISE VE YALNIZ ISE ``days`` dolu.  Bu
modul bes kapi uygular (notr, zirve, gecmis, gorunurluk, egim); altincisi
- ``IZLENMIYOR`` - hic olculmeyen baglantilar icin ``engine`` tarafindan
kurulur, cunku olcum olmadigini bu modul degil o bilir.

Dogrusallik
-----------
Model dogrusaldir.  ``thermal_runaway`` super-dogrusaldir - isinan bir temas
direncinin artmasi daha fazla isinmaya yol acar - yani o modda bu projeksiyon
IYIMSERDIR ve gercek tarih hesaplanandan erkendir.  Sayi gizlenmez, ``model``
alani tasinir ve arayuz o modda "en gec" der.  Super-dogrusal bir model
uydurmak, kalibre edecek saha verisi olmadan olculemeyen bir iddia eklemek
olurdu.
"""

from __future__ import annotations

import math
from statistics import median
from typing import Sequence

from panogoz.contracts.live import EtaView
from panogoz.detector import changepoint as cp

DAY_S = 86400.0

#: Egimin uzerinde hesaplandigi pencere.  changepoint.slope_per_week ile AYNI
#: olmak zorunda; ayrisirsa ekrandaki egim ile projeksiyonun egimi ayrisir.
#:
#: Sinir ``times[i] >= son - WINDOW_DAYS * DAY_S`` seklinde KAPALIDIR, yani tam
#: 21 gun onceki nokta da pencereye girer ve gunluk bir seride 22 nokta gorulur.
#: Bu, ``changepoint._window``'un bastan beri kullandigi semantiktir ve bilincli
#: olarak degistirilmedi: iki kestirici ayni pencereyi gormek zorunda.
WINDOW_DAYS = 21

#: Pencerede istenen en az gecerli gun sayisi.
#:
#: Istatistiksel gucten DEGIL, pencere kapsamasindan geliyor: pencere 21 gun,
#: 14 gecerli gun istemek pencerenin en cok bir haftasinin bos olmasina izin
#: vermek demektir.  Gurultuye karsi koruma bu kapida degil, guven araliginin
#: KENDISINDEDIR - seri gurultuluyse alt sinir sifirin altina iner, ust gun
#: sinirsiz olur ve sayi kendi suphesini tasir.  Iki ayri mekanizmayi tek kapiya
#: yuklemiyoruz.
MIN_VALID_DAYS = 14

#: Bunun otesinde gun sayisi yazilmaz, ">90 g" yazilir.
#:
#: 21 gunluk bir pencereden 412 gunluk bir tarih turetmek, gozlem penceresinin
#: yirmi katina ekstrapolasyondur.  Ayrica 90 gun ileri bir mevsim sinirini
#: gecer; theta yuk icin normalize edilmistir ama gunluk medyanin gurultu tabani
#: yukle birlikte hareket eder ve o hareket modelin icinde degildir.
MAX_HORIZON_DAYS = 90.0

#: Nominal guven seviyesi.  "Nominal" kelimesi onemli: muhafazakar rank secimi
#: yuzunden fiili kapsama %88-93 olculdu.
CONF = 0.90

#: Baglanti hic olculmuyor: canli bara bolmesi, gun 1 kiti kapsaminda
#: degil.  Bu bir ariza degil, kapsamin kendisidir - ve gerekce olarak
#: yazilmak zorunda, cunku filo kolonu yalniz EtaView'e bakar.
REASON_UNMONITORED = "IZLENMIYOR"
REASON_NEUTRAL = "NOTR_KAPSAM_DISI"
REASON_TOP = "ZIRVEDE"
REASON_HISTORY = "YETERSIZ_GECMIS"
REASON_BLIND = "GORUNURLUK_DUSUK"
REASON_FLAT = "EGIM_YOK"

#: Kapilarin sirasi, yani bir baglantinin NE KADAR ILERI gidebildigi.
#:
#: Pano duzeyine yukseltirken gerekir: bir panoda hicbir baglanti sayi
#: vermiyorsa, panonun tasidigi gerekce en ileri gidebilmis baglantinin
#: gerekcesidir.  Bir baglanti yalnizca "egim yok" diye susuyorsa panonun dogru
#: cumlesi "burada tirmanan bir baglanti yok"tur, "yetersiz gecmis" degil.
GATE_ORDER: dict[str, int] = {
    REASON_UNMONITORED: 0,
    REASON_NEUTRAL: 1,
    REASON_TOP: 2,
    REASON_HISTORY: 3,
    REASON_BLIND: 4,
    REASON_FLAT: 5,
}


def next_step(theta: float,
              ladder: Sequence[tuple[str, float]]) -> tuple[str, float] | None:
    """Bu theta degerinin bir USTUNDEKI basamak, ya da None (zirvede).

    Merdiven parametredir, import edilmez: engine -> changepoint bagimliligi
    zaten var ve ters yonde bir import dongu kurardi.  Esik sayilari
    ``engine.THETA_ABS_LADDER``'da bir kez tanimlidir.
    """
    for name, threshold in ladder:
        if theta < threshold:
            return name, threshold
    return None


def project(values: Sequence[float], times: Sequence[float],
            theta_min: Sequence[float],
            ladder: Sequence[tuple[str, float]],
            *, conductor: str = "L") -> EtaView:
    """Gunluk theta serisinden bir sonraki basamaga kalan gun.

    ``values`` / ``times`` / ``theta_min`` ayni uzunlukta ve gune gore ARTAN
    siradadir, ve yalnizca GECERLI gunleri icerir (n > 0 ve theta_med dolu).
    Filtreleme cagirana aittir: bu modul "bir satir var" ile "bir satir var ama
    ici bos" arasindaki farki store'un semasina sormak zorunda kalmaz.
    """
    eta = EtaView()

    # 1. Notr kapsam disi: serisi theta degil K_N'dir, mutlak esik merdiveni
    #    ona uygulanmaz.  H3 kurali notru kendi yontemiyle yargilar.
    if conductor == "N":
        eta.reason = REASON_NEUTRAL
        return eta

    n = min(len(values), len(times), len(theta_min))
    if n == 0:
        eta.reason = REASON_HISTORY
        return eta

    cut = times[n - 1] - WINDOW_DAYS * DAY_S
    idx = [i for i in range(n) if times[i] >= cut]
    eta.valid_days = len(idx)
    if not idx:
        eta.reason = REASON_HISTORY
        return eta

    # Projeksiyon GUNLUK medyanin son gecerli gununden baslar, anlik theta'dan
    # baslamaz: egim gunluk medyanlar uzerinde hesaplanmistir ve anlik bir
    # okumayi gunluk bir egimle birlestirmek birim uyusmazligidir.  Ayni gun
    # icinde iki kez sorulan soru ayni cevabi vermek zorundadir.
    theta_now = values[idx[-1]]

    # 2. Zirvede: ustunde basamak yok.  Ariza degil.
    step = next_step(theta_now, ladder)
    if step is None:
        eta.reason = REASON_TOP
        return eta
    eta.target, threshold = step

    # 3. Yetersiz gecmis.
    if len(idx) < MIN_VALID_DAYS:
        eta.reason = REASON_HISTORY
        return eta

    # 4. Gorunurluk dusuk: theta_min hedef esigin ustundeyse o esige dogru
    #    yapilan projeksiyon anlamsizdir, cunku esigin kendisi gurultu tabaninin
    #    altinda kalir.  Kriter yuzde DEGIL: sensitivity_pct < 100 olsaydi tam
    #    yukun altindaki her baglanti susturulurdu.
    if median([theta_min[i] for i in idx]) >= threshold:
        eta.reason = REASON_BLIND
        return eta

    # Pencerede bir degisim noktasi varsa egim YALNIZ ondan sonrasindan
    # hesaplanir.  10 gun once 3 K kademe atlayip duzlesen bir seri, aksi halde
    # sahte bir rampa uretir ve uydurma bir tarih verir.
    seg = idx
    onset = cp.detect_changepoint([values[i] for i in idx],
                                  [times[i] for i in idx])
    if onset is not None:
        after = [i for i in idx if times[i] >= onset]
        if len(after) >= 3:
            seg = after
            eta.from_changepoint = True
            eta.changepoint_ts = onset

    lo, med, hi = cp.theil_sen_ci([values[i] for i in seg],
                                  [times[i] for i in seg], CONF)
    per_week = 7.0 * DAY_S
    eta.slope_lo_k_per_week = lo * per_week
    eta.slope_k_per_week = med * per_week
    eta.slope_hi_k_per_week = hi * per_week

    # 5. Egim yok.
    if eta.slope_k_per_week <= 0.0:
        eta.reason = REASON_FLAT
        return eta

    remaining = threshold - theta_now
    # Yuvarlama yonu muhafazakardir: aralik daralmaz, genisler.
    eta.days = float(round(remaining * 7.0 / eta.slope_k_per_week))
    if eta.slope_hi_k_per_week > 0.0:
        eta.days_lo = float(math.floor(remaining * 7.0 / eta.slope_hi_k_per_week))
    if eta.slope_lo_k_per_week > 0.0:
        eta.days_hi = float(math.ceil(remaining * 7.0 / eta.slope_lo_k_per_week))
    # days_hi None kalir: guven araligi sifiri iceriyor, ust sinir sonsuzdur.
    if eta.days > MAX_HORIZON_DAYS:
        eta.capped = True
    return eta


# --------------------------------------------------------------------------
# Self-test
# --------------------------------------------------------------------------

if __name__ == "__main__":
    import random

    LADDER = (("IZLE", 2.0), ("UYARI", 5.0), ("KRITIK", 12.0), ("ACIL", 25.0))

    def _days(n: int, t0: float = 1_750_000_000.0) -> list[float]:
        return [t0 + i * DAY_S for i in range(n)]

    print("=" * 78)
    print("horizon.py self-test")
    print("=" * 78)

    print("\n[1] elle hesaplanmis ornek · kalan 3.6 K, egim +1.20 K/hafta")
    vals = [8.4 - 1.20 * ((20 - i) / 7.0) for i in range(21)]
    e = project(vals, _days(21), [0.5] * 21, LADDER)
    print(f"    theta_son {vals[-1]:.2f} K   hedef {e.target} 12 K   "
          f"kalan {12.0 - vals[-1]:.2f} K")
    print(f"    egim {e.slope_k_per_week:+.2f} K/hafta "
          f"(%90 CI: {e.slope_lo_k_per_week:+.2f} … {e.slope_hi_k_per_week:+.2f})")
    print(f"    -> {e.target}'e {e.days:.0f} g "
          f"({e.days_lo:.0f}-{e.days_hi:.0f})")
    assert e.days == 21.0, e.days

    print("\n[2] bes susma kapisi")
    rows = [
        ("notr", project(vals, _days(21), [0.5] * 21, LADDER, conductor="N")),
        ("zirve", project([30.0] * 21, _days(21), [0.5] * 21, LADDER)),
        ("gecmis", project(vals[:9], _days(9), [0.5] * 9, LADDER)),
        ("kor", project(vals, _days(21), [14.0] * 21, LADDER)),
        ("duz", project([3.0] * 21, _days(21), [0.5] * 21, LADDER)),
    ]
    for name, r in rows:
        print(f"    {name:8} -> {r.reason or '(sayi var)':18} "
              f"hedef {r.target or '—'}")
    assert [r.reason for _n, r in rows] == [
        REASON_NEUTRAL, REASON_TOP, REASON_HISTORY, REASON_BLIND, REASON_FLAT]

    print("\n[3] kademe rampa sanilmiyor")
    rng = random.Random(7)
    step_series = ([1.0 + rng.gauss(0, 0.15) for _ in range(11)]
                   + [4.0 + rng.gauss(0, 0.15) for _ in range(10)])
    e3 = project(step_series, _days(21), [0.5] * 21, LADDER)
    _lo, med3, _hi = cp.slope_ci_per_week(step_series, _days(21), 21, CONF)
    print(f"    pencere butunu   egim {med3:+.2f} K/hafta  (sahte rampa)")
    print(f"    degisim sonrasi  egim {e3.slope_k_per_week:+.2f} K/hafta  "
          f"-> {e3.reason}")
    assert e3.from_changepoint and e3.reason == REASON_FLAT

    print("\n[4] 90 gun tavani")
    slow = [3.0 + 0.02 * (i / 7.0) for i in range(21)]
    e4 = project(slow, _days(21), [0.5] * 21, LADDER)
    print(f"    egim {e4.slope_k_per_week:+.3f} K/hafta  medyan {e4.days:.0f} g  "
          f"capped={e4.capped}  -> ekranda '>90 g'")
    assert e4.capped

    print("\nOK - horizon.py self-test passed")
