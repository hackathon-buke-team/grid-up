"""CUSUM (Page 1954 kumulatif toplam) tabanli degisim noktasi tespiti.

CLAUDE.md Sec.2: "Surukleme: gunluk medyanlarda CUSUM + degisim noktasi."
theta.py'nin anlik esik+debounce kurallari (panogoz.rules.engine) ani/buyuk
sapmalari yakalar; bu modul cok daha yavas, kalici bir kaymayi (sensor
suruklemesi, yavas gevseyen bir baglanti gibi) haftalar/aylar olceginde
yakalamak icin ayri bir katmandir -- gunluk theta medyanlari uzerinde calisir,
ham ornekler uzerinde degil.

Kullanilan varyant: standart iki-tarafli (two-sided) Page CUSUM testi.
Baslangic (baseline) gunlerinden referans ortalama mu0 ve std sigma0 tahmin
edilir; S+ ve S- kumulatif istatistikleri her gun icin:

    S+_i = max(0, S+_{i-1} + (x_i - mu0) - k)
    S-_i = min(0, S-_{i-1} + (x_i - mu0) + k)

k (allowance/gevseklik) ve h (karar esigi) sigma0'a orantili secilir --
literaturdeki yaygin kural-of-thumb (Montgomery, "Introduction to Statistical
Quality Control"): k = 0.5*sigma (1-sigma'lik bir kaymayi guvenilir yakalamak
icin) ve h = 4-5*sigma (yanlis alarm oranini dusuk tutmak icin). Degisim
noktasi, |S| ilk kez h'yi astiginda o gunun index'i olarak isaretlenir.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from statistics import mean, median, pstdev

from panogoz.detector.theta import ThetaSample

DAY_S = 24 * 3600.0

# Baseline tamamen duz (varyanssiz) bir seriyse pstdev=0 olur; bu durumda
# k=h=0 olup CUSUM ilk kucuk gurultude bile tetiklenir (yararsiz asiri
# duyarlilik). Gercekci hicbir sensor serisi tam duz olmadigindan bu yalnizca
# bir guvenlik tabani -- gercek veri icin devreye girmesi beklenmez.
MIN_SIGMA = 0.05


@dataclass(frozen=True)
class DailyMedian:
    day_index: int
    t_s: float
    median_theta: float


def daily_median_series(theta_samples: list[ThetaSample]) -> list[DailyMedian]:
    """Theta orneklerini gune gore gruplayip (t_s // DAY_S) gunluk medyani
    dondurur. theta=None (theta.py'nin dusuk-yuk 'uninformative' donusu)
    gunluk medyana katilmadan atlanir -- veri yoklugu ile gercek bir 0
    theta'yi karistirmamak icin."""
    buckets: dict[int, list[float]] = defaultdict(list)
    for s in theta_samples:
        if s.theta is None:
            continue
        day = int(s.t_s // DAY_S)
        buckets[day].append(s.theta)
    days = sorted(buckets)
    return [
        DailyMedian(day_index=d, t_s=d * DAY_S, median_theta=median(buckets[d]))
        for d in days
    ]


@dataclass(frozen=True)
class CusumResult:
    day_index: list[int]
    s_pos: list[float]
    s_neg: list[float]
    mu0: float
    sigma0: float
    k: float
    h: float
    changepoint_day_index: int | None


def cusum_changepoint(
    daily: list[DailyMedian],
    *,
    baseline_days: int = 30,
    k_sigma: float = 0.5,
    h_sigma: float = 5.0,
) -> CusumResult:
    """`daily` en az `baseline_days + 1` gun icermeli (baseline tahmini +
    en az bir izlenecek gun). Baseline penceresi serinin ilk `baseline_days`
    gunudur -- cagiran taraf bu pencerenin gercekten 'saglikli/kararli' bir
    donem oldugunu garanti etmeli (ilk kurulum sonrasi ilk N gun gibi).

    `baseline_days` varsayilani (30, yani ~1 ay) ampirik olarak belirlendi:
    `pstdev` kucuk n'de yuksek varyansli bir tahmin edici (standart hata
    ~sigma/sqrt(2n)) -- bu modulun gelistirilmesi sirasinda once n=7, sonra
    n=14 denendi, ikisinde de tests/test_cusum.py'deki saf-gurultu (sift
    olmayan) negatif kontrol testleri GERCEKTEN yanlis alarm uretti (h=5*sigma
    olmasina ragmen, tahmini sigma0 gercek sigma'dan %20-40 dusuk cikinca h de
    orantili kucaliyor ve CUSUM'un ARL0'i -- alarmlar-arasi beklenen ornek
    sayisi -- cok kisaliyor). n=30 ile standart hata ~%13'e iniyor ve
    tests/test_cusum.py'deki iki bagimsiz tohum + iki yonlu (pozitif/negatif)
    kayma testi de gercekten gecti -- bu sayi bir teorik secim degil, olcerek
    bulundu. Daha kisa bir baseline (ör. 14 gun) istenirse h_sigma'yi da
    (ör. 6-7'ye) artirmak dengelenmeyi geri getirebilir, ayrica test
    edilmeli."""
    if len(daily) < baseline_days + 1:
        raise ValueError(
            f"cusum_changepoint icin en az {baseline_days + 1} gunluk veri gerekli, {len(daily)} verildi"
        )

    baseline_vals = [d.median_theta for d in daily[:baseline_days]]
    mu0 = mean(baseline_vals)
    sigma0 = max(pstdev(baseline_vals), MIN_SIGMA)
    k = k_sigma * sigma0
    h = h_sigma * sigma0

    s_pos: list[float] = []
    s_neg: list[float] = []
    changepoint: int | None = None
    sp = 0.0
    sn = 0.0
    for d in daily:
        sp = max(0.0, sp + (d.median_theta - mu0) - k)
        sn = min(0.0, sn + (d.median_theta - mu0) + k)
        s_pos.append(sp)
        s_neg.append(sn)
        if changepoint is None and (sp > h or sn < -h):
            changepoint = d.day_index

    return CusumResult(
        day_index=[d.day_index for d in daily],
        s_pos=s_pos,
        s_neg=s_neg,
        mu0=mu0,
        sigma0=sigma0,
        k=k,
        h=h,
        changepoint_day_index=changepoint,
    )
