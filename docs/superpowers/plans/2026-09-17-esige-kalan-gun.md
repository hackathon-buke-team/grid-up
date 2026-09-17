# Eşiğe kalan gün · uygulama planı

> **Ajan işçiler için:** GEREKLİ ALT-SKILL: Bu planı görev görev uygulamak için
> `superpowers:subagent-driven-development` (önerilen) ya da
> `superpowers:executing-plans` kullanın. Adımlar takip için onay kutusu
> (`- [ ]`) sözdizimindedir.

**Hedef:** `joint_daily` üzerindeki günlük θ medyanlarının Theil-Sen eğimini, bir sonraki
seviye basamağına kalan gün olarak, güven aralığıyla ve beş susma koduyla raporlamak.

**Mimari:** Yeni kestirici yok. `changepoint.theil_sen()` içinde zaten üretilen ikili
eğim listesinin Sen (1968) rank kuantilleri eğimin güven aralığını verir; yeni
`detector/horizon.py` bu aralığı bir gün sayısına çevirir ve susma kapılarını uygular.
Sonuç `contracts/live.py`'deki `EtaView` olarak taşınır, `engine` onu `_refresh_stats()`
içinde `joint_daily`'den yeniden hesaplar, API/arayüz/bildirim onu okur. Yeni tablo,
yeni kolon ve yeni uç yok.

**Teknoloji:** Python 3.11, stdlib (`math`, `statistics`), FastAPI, SQLite, vanilya
ES modülleri + canvas. `detector/` altında yeni bağımlılık **yok** — `scipy` kurulu
olmasına rağmen kullanılmıyor.

**Spec:** `docs/superpowers/specs/2026-09-17-esige-kalan-gun-design.md`

## Global kısıtlar

- Dal `esige-kalan-gun`. `main`'e doğrudan push **yok**; birleştirme PR ile.
  `contracts/live.py` değiştiği için PR dört kişiye birden haber verilerek açılır.
- Eşik merdiveni: IZLE 2.0 K · UYARI 5.0 K · KRITIK 12.0 K · ACIL 25.0 K. Bu sayılar
  `engine.py`'de zaten tanımlı; **hiçbir yerde ikinci kez yazılmaz**.
- Pencere 21 gün · en az 14 geçerli gün · güven %90 nominal · ufuk tavanı 90 gün.
- Güven seviyesi metinde **"%90 nominal"** diye adlandırılır; "tam %90" denmez
  (ölçülen kapsama %88–93).
- Gerekçe kodları tam olarak bunlar, başka yazım yok: `NOTR_KAPSAM_DISI`, `ZIRVEDE`,
  `YETERSIZ_GECMIS`, `GORUNURLUK_DUSUK`, `EGIM_YOK`.
- `slope_per_week()`, `theta_delta()`, `theil_sen()` dönüş değerleri **değişmez**;
  `SLOPE_ESCALATE_K_PER_WEEK` kuralı ve filo tablosunun varsayılan sıralaması
  (`theta_delta_7d`) değişmez.
- Gün sayıları: `days_lo` aşağı yuvarlanır, `days` en yakına, `days_hi` yukarı.
- `days_hi is None` yalnız `reason == ""` iken ∞ demektir; `reason` doluysa "sayı yok".
- Türkçe çıktı basan modül öz-testleri Windows'ta `PYTHONIOENCODING=utf-8` ile koşar.
- Her görev: önce kırmızı test, sonra en küçük uygulama, sonra yeşil, sonra commit.

---

## Dosya yapısı

| Dosya | Sorumluluğu |
|---|---|
| `panogoz/detector/changepoint.py` | Günlük seri istatistikleri. **Eklenen:** ikili eğim listesi ve onun rank güven aralığı |
| `panogoz/detector/horizon.py` | **YENİ.** Eğimi gün sayısına çevirir, susma kapılarını uygular. Tek sorumluluk, kendi öz-testi |
| `panogoz/contracts/live.py` | Görünüm sözleşmesi. **Eklenen:** `EtaView` |
| `panogoz/detector/engine.py` | Merdiven ilanı, rollup'ta `theta_min` yazımı, `EtaView`'ın kurulması ve pano düzeyine yükseltilmesi |
| `panogoz/api/app.py` | `panel_summary()` ve `/onset` projeksiyonları |
| `panogoz/notify/escalation.py` | SMS gövdesine eta satırı ve parça sözleşmesi |
| `frontend/js/fmt.js` | `eta()` biçimleyicisi — üç ekran aynı biçimleyiciyi kullanır |
| `frontend/js/view-fleet.js` | "Eşiğe" kolonu ve bileşik sıralama |
| `frontend/js/view-evidence.js` | Projeksiyon kartı ve hedef eşik çizgisi |
| `frontend/js/view-alarms.js` | Olay kartındaki tek cümle |
| `tests/test_horizon.py` | **YENİ.** CI, projeksiyon, beş kapı, basamak/rampa gerilemesi |

### Spec'ten iki sapma — uygulamadan önce okunmalı

**1. `joint_daily.theta_min` bugün hiç yazılmıyor.** Şema kolonu tanımlıyor
(`schema.sql:106-125`), `roll_daily()` ise `theta_med`, `theta_p90`, `n`, `load_mean`,
`sens_pct` yazıp `theta_min`'i atlıyor — `det.theta_min_k` örneklerini okuyup yalnız
`load_mean`'i türetiyor. Spec §5.1'deki görünürlük kapısı bu kolona dayandığı için
**Görev 4 bunu düzeltir**; öncesinde kapı ölü doğar. Bu, bu planın bulduğu mevcut bir
eksiktir, yeni bir özellik değildir.

**2. Projeksiyon θ grafiğinin üstüne çizilemez.** Kanıt ekranının dört grafiği tek ve
ortak bir x ekseni paylaşıyor (`view-evidence.js` başlığındaki sözleşme) ve o eksenin
sağ kenarı "şimdi"dir. `TimeChart` noktaları `X(t)` ile alana eşler; `t > domain[1]`
olan bir nokta tuvalin dışına düşer, yani gelecekteki kesişim **hiç çizilmez**. Alanı
geleceğe uzatmak dört grafiğin hepsini birden sıkıştırır ve senkron eksen sözünü bozar.

Bu yüzden Görev 9 spec §9'dan şöyle sapar: θ grafiğine **hedef eşik yatay çizgisi**
eklenir (alan içi, bilgilendirici) ve projeksiyonun kendisi `resistanceCard` /
`factsCard` desenini izleyen ayrı bir **metin kartı** olur. Kesikli yelpaze çizilmez:
üç sayının (başlangıç θ, eğim + CI, hedef) taşımadığı hiçbir bilgiyi taşımaz ve ekranda
zaten dört grafik var.

---

## Görev 1: Theil-Sen güven aralığı

**Dosyalar:**
- Değiştir: `panogoz/detector/changepoint.py:209-251` (`theil_sen`, `slope_per_week`)
- Değiştir: `panogoz/detector/changepoint.py:310+` (öz-test bölümü)
- Test: `tests/test_horizon.py` (yeni dosya, bu görevde yalnız CI bölümü)

**Arayüzler:**
- Tüketir: yok
- Üretir:
  - `changepoint.Z_TWO_SIDED: dict[float, float]`
  - `changepoint._pairwise_slopes(values: Sequence[float], times: Sequence[float]) -> list[float]`
  - `changepoint.theil_sen_ci(values, times, conf: float = 0.90) -> tuple[float, float, float]`
    — (lo, medyan, hi), birim: değer-birimi **saniyede**
  - `changepoint.slope_ci_per_week(values, times, window_days: int = 21, conf: float = 0.90) -> tuple[float, float, float]`
    — birim: **K/hafta**

- [ ] **Adım 1: Kırmızı testi yaz**

`tests/test_horizon.py` dosyasını oluştur:

```python
"""Eşiğe kalan gün: güven aralığı ve projeksiyon testleri."""
from __future__ import annotations

import math
import random

from panogoz.detector import changepoint as cp

DAY_S = 86400.0


def _days(n: int, t0: float = 1_750_000_000.0) -> list[float]:
    return [t0 + i * DAY_S for i in range(n)]


def _ramp(n: int, per_week: float, sigma: float, seed: int) -> list[float]:
    r = random.Random(seed)
    return [per_week * (i / 7.0) + r.gauss(0.0, sigma) for i in range(n)]


def test_ci_monotonic():
    """lo <= medyan <= hi, her zaman."""
    for seed in range(20):
        vals = _ramp(21, 0.2, 0.8, seed)
        lo, med, hi = cp.theil_sen_ci(vals, _days(21), 0.90)
        assert lo <= med <= hi, (lo, med, hi)


def test_ci_ranks_match_the_documented_arithmetic():
    """Spec §2.3: n=14 icin N=91, Var(S)=333.67, C=30.05, lo_rank=30, hi_rank=62."""
    n = 14
    N = n * (n - 1) // 2
    var_s = n * (n - 1) * (2 * n + 5) / 18.0
    c = cp.Z_TWO_SIDED[0.90] * math.sqrt(var_s)
    assert N == 91
    assert abs(var_s - 333.67) < 0.01
    assert abs(c - 30.05) < 0.02
    assert math.floor((N - c) / 2.0) == 30
    assert math.ceil((N + c) / 2.0) + 1 == 62


def test_ci_covers_the_true_slope():
    """Spec §12.1: 400 kosum, kapsama %84-96 arasinda."""
    hit = 0
    runs = 400
    for seed in range(runs):
        vals = _ramp(21, 0.2, 0.8, 5000 + seed)
        lo, _med, hi = cp.slope_ci_per_week(vals, _days(21), 21, 0.90)
        if lo <= 0.2 <= hi:
            hit += 1
    pct = 100.0 * hit / runs
    assert 84.0 <= pct <= 96.0, f"kapsama {pct:.1f}% - kestirici bozuk"


def test_ci_is_scale_invariant():
    """Aralik ve gurultu sigma ile dogrusal olceklendigi icin kapsama sigmadan bagimsiz."""
    def coverage(sigma: float) -> int:
        hit = 0
        for seed in range(200):
            vals = _ramp(21, 0.2, sigma, 7000 + seed)
            lo, _m, hi = cp.slope_ci_per_week(vals, _days(21), 21, 0.90)
            if lo <= 0.2 <= hi:
                hit += 1
        return hit
    assert coverage(0.8) == coverage(0.4)


def test_ci_lower_bound_goes_negative_on_a_flat_series():
    """Duz ve gurultulu seride alt sinir sifirin altina iner - sonsuz ust gun sinirinin kaynagi."""
    r = random.Random(99)
    flat = [1.2 + r.gauss(0.0, 0.8) for _ in range(21)]
    lo, _med, hi = cp.slope_ci_per_week(flat, _days(21), 21, 0.90)
    assert lo < 0.0 < hi


def test_theil_sen_return_value_is_unchanged_by_the_refactor():
    """Tek 25 K aykiri deger altinda egim hala 0.05 K/hafta icinde (modulun kendi iddiasi)."""
    vals = _ramp(21, 0.2, 0.0, 1)
    dirty = list(vals)
    dirty[10] += 25.0
    assert abs(cp.slope_per_week(dirty, _days(21)) - 0.2) < 0.05


def test_unsupported_confidence_is_refused():
    try:
        cp.theil_sen_ci(_ramp(21, 0.2, 0.8, 1), _days(21), 0.80)
    except ValueError as exc:
        assert "0.8" in str(exc)
    else:
        raise AssertionError("desteklenmeyen guven seviyesi sessizce kabul edildi")


def test_ci_short_series_returns_zeros():
    assert cp.theil_sen_ci([1.0, 2.0], _days(2), 0.90) == (0.0, 0.0, 0.0)
    assert cp.slope_ci_per_week([1.0, 2.0], _days(2)) == (0.0, 0.0, 0.0)
```

- [ ] **Adım 2: Testi koştur, düştüğünü gör**

Koş: `python -m pytest tests/test_horizon.py -q`
Beklenen: `AttributeError: module 'panogoz.detector.changepoint' has no attribute 'Z_TWO_SIDED'`
ve `theil_sen_ci` / `slope_ci_per_week` için aynı hata.

- [ ] **Adım 3: `_pairwise_slopes` ve `Z_TWO_SIDED`'ı ekle, `theil_sen`'i onun üstüne kur**

`changepoint.py`'de `BIC_PARAMS = 3.0` satırından sonra ekle:

```python
#: Iki yonlu normal kuantiller.  scipy projenin bagimliligidir ama bu paketin
#: degildir: detector/ altinda prpd_classify.py disinda her modul stdlib'dir ve
#: guven araligi icin tam olarak iki kuantil gerekir.
Z_TWO_SIDED: dict[float, float] = {0.90: 1.6449, 0.95: 1.9600}
```

`theil_sen()` gövdesini (satır 209-227) şununla değiştir:

```python
def _pairwise_slopes(values: Sequence[float],
                     times: Sequence[float]) -> list[float]:
    """Butun ikili egimler, deger-birimi/saniye, siralanmamis.

    O(n^2) cift.  21 gunluk pencerede 210, 120 gunluk pencerede 7140 - ikisi de
    bedava.  Ayri bir fonksiyon oldugu icin medyan ve rank sinirlari AYNI
    listeden okunur; iki kez uretilmez.
    """
    n = min(len(values), len(times))
    out: list[float] = []
    for i in range(n - 1):
        ti, vi = times[i], values[i]
        for j in range(i + 1, n):
            dt = times[j] - ti
            if dt > 0:
                out.append((values[j] - vi) / dt)
    return out


def theil_sen(values: Sequence[float], times: Sequence[float]) -> float:
    """Median of pairwise slopes, in value-units per second.

    O(n^2) pairs.  With a 21-day window that is 210 pairs per joint per day,
    which is free; with a 120-day window it is 7140, still free.
    """
    n = min(len(values), len(times))
    if n < 3:
        return 0.0
    slopes = _pairwise_slopes(values, times)
    if not slopes:
        return 0.0
    return float(median(slopes))


def theil_sen_ci(values: Sequence[float], times: Sequence[float],
                 conf: float = 0.90) -> tuple[float, float, float]:
    """(alt, medyan, ust) egim araligi, deger-birimi/saniye.

    Sen (1968) rank araligi: N ikili egim siralanir, Kendall S istatistiginin
    varyansindan turetilen rank sinirlari okunur.  Parametrik olmayan, ek model
    varsaymayan bir aralik - ve zaten uretilmis olan listenin uzerinde bedava.

    Rank secimi ``floor`` / ``ceil+1`` ile BILINCLI OLARAK MUHAFAZAKARDIR:
    araligi bir rank genisletir.  Bedeli olculdu - nominal %90 seviyede fiili
    kapsama %88-93, yani aralik nominalden bir miktar genis.  Emniyetle ilgili
    bir sayida yanilma yonu budur.

    Deger tarafindaki baglanmalar Var(S)'den dusulur.  Zaman tarafinda baglanma
    OLAMAZ: joint_daily'nin birincil anahtari (day, panel_key, joint_key).
    """
    n = min(len(values), len(times))
    if n < 3:
        return 0.0, 0.0, 0.0
    z = Z_TWO_SIDED.get(conf)
    if z is None:
        raise ValueError(
            f"desteklenmeyen güven seviyesi: {conf} · "
            f"tanımlı olanlar {sorted(Z_TWO_SIDED)}")
    slopes = sorted(_pairwise_slopes(values, times))
    total = len(slopes)
    if total == 0:
        return 0.0, 0.0, 0.0
    counts: dict[float, int] = {}
    for v in list(values)[:n]:
        counts[v] = counts.get(v, 0) + 1
    ties = sum(t * (t - 1) * (2 * t + 5) for t in counts.values() if t > 1)
    var_s = (n * (n - 1) * (2 * n + 5) - ties) / 18.0
    c = z * math.sqrt(var_s) if var_s > 0.0 else 0.0
    lo_rank = max(1, min(total, int(math.floor((total - c) / 2.0))))
    hi_rank = max(1, min(total, int(math.ceil((total + c) / 2.0)) + 1))
    return slopes[lo_rank - 1], float(median(slopes)), slopes[hi_rank - 1]
```

- [ ] **Adım 4: Pencere mantığını ortaklaştır, `slope_ci_per_week`'i ekle**

`slope_per_week()` (satır 230-251) yerine:

```python
def _window(values: Sequence[float], times: Sequence[float],
            window_days: int) -> tuple[list[float], list[float]]:
    """Serinin son ``window_days`` gunu.  Uc noktadan az kalirsa son uc nokta.

    slope_per_week ve slope_ci_per_week AYNI pencereyi gormek zorundadir; ikisi
    ayri ayri kesse, ekranda gosterilen egim ile projeksiyonun kullandigi egim
    sessizce ayrisirdi.
    """
    n = min(len(values), len(times))
    if n < 3:
        return [], []
    t_end = times[n - 1]
    cut = t_end - window_days * DAY_S
    v = [values[i] for i in range(n) if times[i] >= cut]
    t = [times[i] for i in range(n) if times[i] >= cut]
    if len(v) < 3:
        v = list(values[max(0, n - 3):n])
        t = list(times[max(0, n - 3):n])
    return v, t


def slope_per_week(values: list[float], times: list[float], window_days: int = 21) -> float:
    """Theil-Sen slope of the last ``window_days`` of daily theta, in K/week.

    Three weeks is chosen deliberately: long enough that a 0.2 K/week drift is
    0.6 K of real movement against a ~0.8 K daily noise floor, short enough that
    a joint that stabilised a month ago is not still reported as climbing.
    """
    v, t = _window(values, times, window_days)
    if not v:
        return 0.0
    return theil_sen(v, t) * 7.0 * DAY_S


def slope_ci_per_week(values: Sequence[float], times: Sequence[float],
                      window_days: int = 21,
                      conf: float = 0.90) -> tuple[float, float, float]:
    """slope_per_week ile ayni pencere, bu kez (alt, medyan, ust) K/hafta."""
    v, t = _window(values, times, window_days)
    if not v:
        return 0.0, 0.0, 0.0
    lo, med, hi = theil_sen_ci(v, t, conf)
    k = 7.0 * DAY_S
    return lo * k, med * k, hi * k
```

- [ ] **Adım 5: Testi koştur, geçtiğini gör**

Koş: `python -m pytest tests/test_horizon.py -q`
Beklenen: 8 passed.

- [ ] **Adım 6: Modülün kendi kanıtını basmasını sağla**

`changepoint.py` öz-testinin `[5]` (Theil-Sen) bölümünden sonra, `[6]`'dan önce ekle
(numaraları kaydırmadan `[5b]` olarak):

```python
    # ----------------------------------------------------------------- 5b --
    print("\n[5b] Sen (1968) rank guven araligi")
    n_ci = 14
    N_ci = n_ci * (n_ci - 1) // 2
    var_ci = n_ci * (n_ci - 1) * (2 * n_ci + 5) / 18.0
    c_ci = Z_TWO_SIDED[0.90] * math.sqrt(var_ci)
    print(f"    n={n_ci}  N={N_ci}  Var(S)={var_ci:.2f}  C={c_ci:.2f}  "
          f"lo_rank={math.floor((N_ci - c_ci) / 2)}  "
          f"hi_rank={math.ceil((N_ci + c_ci) / 2) + 1}")
    hit_ci = 0
    for trial in range(400):
        r = random.Random(5000 + trial)
        v_ci = [0.2 * (i / 7.0) + r.gauss(0.0, 0.8) for i in range(21)]
        lo_ci, _m_ci, hi_ci = slope_ci_per_week(v_ci, _days(21), 21, 0.90)
        if lo_ci <= 0.2 <= hi_ci:
            hit_ci += 1
    print(f"    400 rampada kapsama {100 * hit_ci / 400:.1f} %   "
          f"nominal 90 % (muhafazakar rank secimi araligi genisletir)")
    assert 84.0 <= 100 * hit_ci / 400 <= 96.0
```

- [ ] **Adım 7: Öz-testi ve tüm takımı koştur**

Koş: `PYTHONIOENCODING=utf-8 python -m panogoz.detector.changepoint`
Beklenen: `OK - changepoint.py self-test passed`, `[5b]` bölümü basılı.

Koş: `python -m pytest -q`
Beklenen: 138 + 8 = 146 passed.

- [ ] **Adım 8: Commit**

```bash
git add panogoz/detector/changepoint.py tests/test_horizon.py
git commit -m "Theil-Sen eğimine Sen (1968) rank güven aralığı

theil_sen() zaten ürettiği ikili eğim listesinin medyanını alıp listeyi
atıyordu. _pairwise_slopes() ile liste ortaklaştırıldı; theil_sen_ci()
aynı listenin rank kuantillerini okuyor. Pencere mantığı _window() ile
tekilleştirildi, böylece ekrandaki eğim ile projeksiyonun kullandığı
eğim ayrışamaz.

Rank seçimi floor/ceil+1 ile muhafazakâr: nominal %90'da ölçülen
kapsama %88-93. 400 rampada kapsama testi hem pytest'te hem modülün
öz-testinde.

slope_per_week() ve theil_sen() dönüş değerleri değişmedi."
```

---

## Görev 2: `EtaView` sözleşmesi

**Dosyalar:**
- Değiştir: `panogoz/contracts/live.py:20` (`JointView`'ın hemen üstü) ve `JointView`,
  `PanelLive` gövdeleri
- Test: `tests/test_horizon.py`

**Arayüzler:**
- Tüketir: yok
- Üretir: `contracts.live.EtaView` — alanları aşağıdaki kodda tam olarak sayılı.
  `JointView.eta: EtaView`, `PanelLive.eta: EtaView`.

- [ ] **Adım 1: Kırmızı testi yaz**

`tests/test_horizon.py` sonuna ekle:

```python
from panogoz.contracts.live import EtaView, JointView, PanelLive


def test_etaview_defaults_are_the_silent_case():
    e = EtaView()
    assert e.target is None
    assert e.days is None and e.days_lo is None and e.days_hi is None
    assert e.valid_days == 0
    assert e.from_changepoint is False and e.changepoint_ts is None
    assert e.model == "dogrusal"
    assert e.capped is False
    assert e.reason == ""


def test_etaview_hangs_on_both_views():
    jv = JointView(key="C07-L2-PABUC", label="", zone="", conductor="L",
                   feeder_index=7, rated_a=400.0, monitored=True)
    assert isinstance(jv.eta, EtaView)
    pl = PanelLive(panel_key="SOKE-14", panel_index=14, site="", name="")
    assert isinstance(pl.eta, EtaView)
    # Iki gorunum ayri nesne tasir; paylasilan bir varsayilan mutasyonu
    # butun panolara sizmaz.
    jv.eta.days = 21.0
    assert pl.eta.days is None


def test_etaview_serialises_inside_the_panel_dict():
    pl = PanelLive(panel_key="SOKE-14", panel_index=14, site="", name="")
    pl.eta.target = "KRITIK"
    pl.eta.days = 21.0
    d = pl.to_dict()
    assert d["eta"]["target"] == "KRITIK"
    assert d["eta"]["days"] == 21.0
```

- [ ] **Adım 2: Testi koştur, düştüğünü gör**

Koş: `python -m pytest tests/test_horizon.py -q -k etaview`
Beklenen: `ImportError: cannot import name 'EtaView'`

- [ ] **Adım 3: `EtaView`'ı ekle**

`live.py`'de `@dataclass class JointView:` satırının **üstüne** ekle (JointView onu
varsayılan olarak kullandığı için önce tanımlanmak zorunda):

```python
@dataclass
class EtaView:
    """Bir sonraki seviye basamagina kalan gun, ve vermeyi reddetme gerekcesi.

    ``excess_r_*`` ile ayni dili konusur: bir kestirim ARALIK olarak verilir,
    tek sayi olarak asla.  Burada ek olarak bir de SUSMA vardir - gerekce kodu
    dolu oldugunda gun sayisi yoktur ve arayuz bunu bir arizadan ayri gosterir.

    ``days_hi is None`` IKI ayri sey demek olabilir ve karistirilmamalidir:
    ``reason`` bossa sonsuzdur (egimin guven araligi sifiri iceriyor, yani
    yukseliyor olabilir de olmayabilir de); ``reason`` doluysa sayi hic yoktur.
    Arayuz ``reason``a bakar, ``days_hi``ye bakmaz.
    """

    #: Hedef basamak adi.  theta'nin GUNLUK degerinin bir ustu; olayin fuzyon
    #: seviyesi DEGIL.  Ark rolesi acmis ama theta'si 3 K olan bir baglantiya
    #: "ACIL'e kalan gun" hesaplamak, isil olmayan bir kanitla isil bir
    #: projeksiyon kurmak olurdu.
    target: str | None = None

    days: float | None = None
    days_lo: float | None = None
    days_hi: float | None = None

    #: Projeksiyonun FIILEN kullandigi egim.  JointView.slope_k_per_week ile
    #: ayni olmak zorunda degil: pencerede bir degisim noktasi varsa bu yalniz
    #: ondan sonrasini gorur.  Iki sayi, iki soru.
    slope_k_per_week: float = 0.0
    slope_lo_k_per_week: float = 0.0
    slope_hi_k_per_week: float = 0.0

    #: Pencerede kac gecerli gun vardi.  14'un altinda YETERSIZ_GECMIS.
    valid_days: int = 0

    from_changepoint: bool = False
    changepoint_ts: float | None = None

    #: Model dogrusaldir.  thermal_runaway super-dogrusaldir, yani bu modda
    #: projeksiyon IYIMSERDIR ve gercek tarih daha erkendir.  Arayuz o modda
    #: "en gec" der, "en erken" demez.
    model: str = "dogrusal"

    #: Medyan 90 gunu gecti; arayuz ">90 g" yazar, 412 gun yazmaz.
    capped: bool = False

    #: "" = sayi gecerli.  Digerleri: NOTR_KAPSAM_DISI, ZIRVEDE,
    #: YETERSIZ_GECMIS, GORUNURLUK_DUSUK, EGIM_YOK.
    reason: str = ""

    def to_dict(self) -> dict:
        return asdict(self)
```

`JointView` gövdesinde `alarm_days: int = 0` satırından sonra ekle:

```python
    #: Bir sonraki basamaga kalan gun.  Tureilmis bir sayidir, joint_state'e
    #: yazilmaz: _refresh_stats her turda joint_daily'den yeniden hesaplar.
    eta: EtaView = field(default_factory=EtaView)
```

`PanelLive` gövdesinde `theta_delta_7d: float = 0.0` satırından sonra ekle:

```python
    #: Panonun projeksiyonu.  theta_delta_7d EN KOTU baglantidan yukseltilir;
    #: bu FARKLI bir anahtarla yukseltilir - hedef seviyesi en yuksek, esitlikte
    #: gunu en yakin olan.  Sadece min(gun) almak, IZLE'ye 3 gun kalan bir
    #: baglantiyi KRITIK'e 18 gun kalanin onune gecirir ve kontrol odasi yanlis
    #: panoya bakar.
    eta: EtaView = field(default_factory=EtaView)
```

- [ ] **Adım 4: Testi koştur, geçtiğini gör**

Koş: `python -m pytest tests/test_horizon.py -q`
Beklenen: 11 passed.

- [ ] **Adım 5: Commit**

```bash
git add panogoz/contracts/live.py tests/test_horizon.py
git commit -m "contracts: EtaView, bir sonraki basamağa kalan gün sözleşmesi

JointView ve PanelLive üzerine iç içe görünüm olarak oturur; ArcView /
PdView desenini izler. excess_r_* gibi aralık taşır, ek olarak bir de
susma gerekçesi taşır.

days_hi is None iki ayrı şey demektir ve sözleşme bunu açıkça yazıyor:
reason boşsa sonsuz, reason doluysa sayı yok. Arayüz reason'a bakar."
```

---

## Görev 3: `horizon.py` · projeksiyon ve susma kapıları

**Dosyalar:**
- Oluştur: `panogoz/detector/horizon.py`
- Test: `tests/test_horizon.py`

**Arayüzler:**
- Tüketir: `changepoint.slope_ci_per_week`, `changepoint.detect_changepoint`,
  `changepoint.theil_sen_ci`, `contracts.live.EtaView`
- Üretir:
  - `horizon.WINDOW_DAYS = 21`, `horizon.MIN_VALID_DAYS = 14`,
    `horizon.MAX_HORIZON_DAYS = 90.0`, `horizon.CONF = 0.90`
  - `horizon.REASON_NEUTRAL / REASON_TOP / REASON_HISTORY / REASON_BLIND / REASON_FLAT`
  - `horizon.next_step(theta: float, ladder: Sequence[tuple[str, float]]) -> tuple[str, float] | None`
  - `horizon.project(values: Sequence[float], times: Sequence[float], theta_min: Sequence[float], ladder: Sequence[tuple[str, float]], *, conductor: str = "L") -> EtaView`

- [ ] **Adım 1: Kırmızı testi yaz**

`tests/test_horizon.py` sonuna ekle:

```python
from panogoz.detector import horizon as hz

LADDER = (("IZLE", 2.0), ("UYARI", 5.0), ("KRITIK", 12.0), ("ACIL", 25.0))


def _series(n, start, per_week, sigma=0.0, seed=1):
    r = random.Random(seed)
    return [start + per_week * (i / 7.0) + r.gauss(0.0, sigma) for i in range(n)]


def test_next_step_picks_the_band_above_the_daily_value():
    assert hz.next_step(0.5, LADDER) == ("IZLE", 2.0)
    assert hz.next_step(3.0, LADDER) == ("UYARI", 5.0)
    assert hz.next_step(8.4, LADDER) == ("KRITIK", 12.0)
    assert hz.next_step(20.0, LADDER) == ("ACIL", 25.0)
    assert hz.next_step(25.0, LADDER) is None
    assert hz.next_step(31.0, LADDER) is None


def test_arithmetic_matches_the_hand_worked_example():
    """Spec §3: kalan 3.6 K, egim +1.20 K/hafta -> 21 gun."""
    vals = _series(21, 8.4 - 1.20 * (20 / 7.0), 1.20)
    times = _days(21)
    eta = hz.project(vals, times, [0.5] * 21, LADDER)
    assert eta.reason == ""
    assert eta.target == "KRITIK"
    assert abs(eta.slope_k_per_week - 1.20) < 0.01
    assert eta.days == 21.0
    assert eta.model == "dogrusal"


def test_rounding_direction_widens_the_interval():
    vals = _series(21, 0.0, 1.20, sigma=0.5, seed=3)
    eta = hz.project(vals, _days(21), [0.5] * 21, LADDER)
    assert eta.reason == ""
    assert eta.days_lo <= eta.days <= eta.days_hi
    assert eta.days_lo == math.floor(eta.days_lo)
    assert eta.days_hi == math.ceil(eta.days_hi)


def test_infinite_upper_bound_when_the_ci_spans_zero():
    r = random.Random(99)
    flat = [3.0 + r.gauss(0.0, 0.8) for _ in range(21)]
    eta = hz.project(flat, _days(21), [0.5] * 21, LADDER)
    if eta.reason == "":
        assert eta.days_hi is None
        assert eta.slope_lo_k_per_week <= 0.0
    else:
        assert eta.reason == hz.REASON_FLAT


def test_gate_neutral_is_out_of_scope():
    eta = hz.project(_series(21, 1.0, 1.0), _days(21), [0.5] * 21, LADDER,
                     conductor="N")
    assert eta.reason == hz.REASON_NEUTRAL
    assert eta.days is None and eta.target is None


def test_gate_top_of_ladder():
    eta = hz.project(_series(21, 30.0, 1.0), _days(21), [0.5] * 21, LADDER)
    assert eta.reason == hz.REASON_TOP
    assert eta.days is None and eta.target is None


def test_gate_insufficient_history():
    eta = hz.project(_series(9, 3.0, 1.0), _days(9), [0.5] * 9, LADDER)
    assert eta.reason == hz.REASON_HISTORY
    assert eta.valid_days == 9
    assert eta.days is None
    # Hedef yine bildirilir: operator neye dogru sayamadigimizi gorur.
    assert eta.target == "UYARI"


def test_gate_low_visibility_uses_theta_min_not_a_percentage():
    """theta_min hedef esigin ustundeyse o esige projeksiyon anlamsizdir."""
    vals = _series(21, 3.0, 1.0)
    eta = hz.project(vals, _days(21), [14.0] * 21, LADDER)
    assert eta.reason == hz.REASON_BLIND
    assert eta.target == "UYARI"
    assert eta.days is None
    # Ayni seri, gorunur bir tabanla: sayi cikar.
    ok = hz.project(vals, _days(21), [0.5] * 21, LADDER)
    assert ok.reason == ""


def test_gate_flat_slope():
    eta = hz.project(_series(21, 3.0, 0.0), _days(21), [0.5] * 21, LADDER)
    assert eta.reason == hz.REASON_FLAT
    assert eta.days is None


def test_gate_negative_slope():
    eta = hz.project(_series(21, 3.0, -1.0), _days(21), [0.5] * 21, LADDER)
    assert eta.reason == hz.REASON_FLAT


def test_horizon_is_capped_at_90_days():
    vals = _series(21, 3.0, 0.02)
    eta = hz.project(vals, _days(21), [0.5] * 21, LADDER)
    assert eta.reason == ""
    assert eta.capped is True
    assert eta.days > hz.MAX_HORIZON_DAYS
    assert eta.target == "UYARI"


def test_a_step_is_not_read_as_a_ramp():
    """EN ONEMLI GERILEME TESTI.

    10 gun once 3 K kademe atlayip sonra duzlesen bir seri, 21 gunluk pencerede
    sahte bir rampa uretir.  Projeksiyon degisim noktasindan SONRASINI kullanmak
    zorunda; kullanmazsa kademeyi rampa sayar ve uydurma bir tarih verir.
    """
    r = random.Random(7)
    vals = ([1.0 + r.gauss(0, 0.15) for _ in range(11)]
            + [4.0 + r.gauss(0, 0.15) for _ in range(10)])
    eta = hz.project(vals, _days(21), [0.5] * 21, LADDER)
    assert eta.from_changepoint is True
    assert eta.changepoint_ts is not None
    # Kademe sonrasi duz: egim ~0, yani sayi YOK.
    assert eta.reason == hz.REASON_FLAT
    # Kanit: ayni seride pencere butunu kullanilsa egim pozitif cikardi.
    lo, med, hi = cp.slope_ci_per_week(vals, _days(21), 21, 0.90)
    assert med > 0.5


def test_a_real_ramp_after_a_step_is_still_projected():
    """Degisim noktasi sonrasi gercekten tirmaniyorsa sayi CIKAR."""
    r = random.Random(11)
    vals = ([1.0 + r.gauss(0, 0.1) for _ in range(9)]
            + [3.0 + 1.2 * (i / 7.0) + r.gauss(0, 0.1) for i in range(12)])
    eta = hz.project(vals, _days(21), [0.5] * 21, LADDER)
    assert eta.reason == ""
    assert eta.target == "UYARI"
    assert eta.days is not None


def test_empty_series_is_insufficient_history_not_a_crash():
    eta = hz.project([], [], [], LADDER)
    assert eta.reason == hz.REASON_HISTORY
    assert eta.valid_days == 0
```

- [ ] **Adım 2: Testi koştur, düştüğünü gör**

Koş: `python -m pytest tests/test_horizon.py -q`
Beklenen: `ModuleNotFoundError: No module named 'panogoz.detector.horizon'`

- [ ] **Adım 3: `horizon.py`'yi yaz**

```python
"""Bir sonraki seviye basamagina kalan gun.

Neden bu modul var
------------------
Urun "haftalar once haber veririm" diyor ve bunu kanitliyor: CUSUM surukelenmeyi
teyit ediyor, changepoint bozulmanin BASLADIGI gunu tarihliyor, theta_delta son
yedi gunun hareketini gosteriyor.  Uc sayinin hepsi GECMISE bakiyor.  Bakim
planlayicisinin sordugu soru ise ileriye bakar: "bu pabuc ne zaman benim sorunum
olacak?"

Cevap elimizdeki verinin icinde duruyor.  slope_per_week() zaten K/hafta cinsinden
bir egim veriyor; eksik olan egimin BELIRSIZLIGI ve sayi vermeyi REDDETME
kurallariydi.  Bu modul yeni bir kestirici degildir; var olan kestiriciyi bir
tarihe cevirir.

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
Bes kapi, sirayla, ilk tutan kazanir.  Kapilarin varligi bu modulun urun olan
kismidir: her zaman bir tarih veren bir kestirici, saglikli bir baglanti icin de
tarih verir ve bir ekip bosa gittiginde sistem kapatilir.

Dogrusallik
-----------
Model dogrusaldir.  thermal_runaway super-dogrusaldir - isinan bir temas
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

REASON_NEUTRAL = "NOTR_KAPSAM_DISI"
REASON_TOP = "ZIRVEDE"
REASON_HISTORY = "YETERSIZ_GECMIS"
REASON_BLIND = "GORUNURLUK_DUSUK"
REASON_FLAT = "EGIM_YOK"


def next_step(theta: float,
              ladder: Sequence[tuple[str, float]]) -> tuple[str, float] | None:
    """Bu theta degerinin bir USTUNDEKI basamak, ya da None (zirvede).

    Merdiven parametredir, import edilmez: engine -> changepoint bagimliligi
    zaten var ve ters yonde bir import dongu kurardi.  Esik sayilari
    engine.THETA_ABS_LADDER'da bir kez tanimlidir.
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
    window_vals = [values[i] for i in idx]
    window_times = [times[i] for i in idx]
    onset = cp.detect_changepoint(window_vals, window_times)
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
    print(f"    theta_son {vals[-1]:.2f} K   hedef {e.target} {12.0:.0f} K   "
          f"kalan {12.0 - vals[-1]:.2f} K")
    print(f"    egim {e.slope_k_per_week:+.2f} K/hafta "
          f"(%90 CI: {e.slope_lo_k_per_week:+.2f} … {e.slope_hi_k_per_week:+.2f})")
    print(f"    -> {e.target}'e {e.days:.0f} g ({e.days_lo:.0f}-{e.days_hi:.0f})")
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
```

- [ ] **Adım 4: Testi koştur, geçtiğini gör**

Koş: `python -m pytest tests/test_horizon.py -q`
Beklenen: 26 passed.

Koş: `PYTHONIOENCODING=utf-8 python -m panogoz.detector.horizon`
Beklenen: `OK - horizon.py self-test passed`, dört bölüm basılı.

- [ ] **Adım 5: Commit**

```bash
git add panogoz/detector/horizon.py tests/test_horizon.py
git commit -m "detector/horizon: θ eğimini bir sonraki basamağa kalan güne çevirir

Beş susma kapısı sırayla: nötr kapsam dışı, zirvede, yetersiz geçmiş,
görünürlük düşük, eğim yok. Görünürlük kriteri yüzde değil
theta_min >= hedef eşik: sensitivity_pct < 100 olsaydı tam yükün
altındaki her bağlantı susturulurdu.

Pencerede değişim noktası varsa eğim yalnız ondan sonrasından
hesaplanır. Onsuz 10 gün önce kademe atlayıp düzleşen bir seri sahte
rampa üretip uydurma tarih veriyor; öz-testin [3] bölümü ikisini yan
yana basıyor.

Merdiven parametre olarak alınır, engine'den import edilmez: ters yönde
import döngü kurardı."
```

---

## Görev 4: Rollup `theta_min`'i yazsın

**Dosyalar:**
- Değiştir: `panogoz/detector/engine.py:750-758` (`roll_daily` içindeki `upsert_joint_daily` çağrısı)
- Test: `tests/test_horizon.py`

**Arayüzler:**
- Tüketir: yok
- Üretir: `joint_daily.theta_min` artık dolu · Görev 5'in görünürlük kapısı buna dayanır

**Neden:** Şema kolonu tanımlıyor, `roll_daily()` yazmıyor. `det.theta_min_k`
örnekleri okunuyor ama yalnız `load_mean` türetmek için kullanılıyor. Görünürlük kapısı
bu kolonu okuyacağı için önce doldurulmalı. Mevcut bir eksiğin kapatılmasıdır.

- [ ] **Adım 1: Kırmızı testi yaz**

`tests/test_horizon.py` sonuna ekle:

```python
def test_roll_daily_writes_theta_min(tmp_path):
    """Sema theta_min kolonunu tanimliyor; rollup onu doldurmak zorunda.

    Gorunurluk kapisi bu kolonu okur.  Bos kalirsa kapi olu dogar.
    """
    from panogoz.detector.engine import DetectorEngine
    from panogoz.store.db import Store

    store = Store(str(tmp_path / "t.db"))
    store.upsert_panel(panel_key="T-1", panel_index=1, site="T", name="T")
    day = 20_000
    ts0 = day * 86400.0 + 3600.0
    for i in range(16):
        ts = ts0 + i * 60.0
        for ch, val in (("det.theta_k", 3.0), ("det.theta_min_k", 1.25),
                        ("det.sensitivity_pct", 80.0)):
            store.execute(
                "INSERT INTO joint_sample (ts, panel_key, joint_key, channel, value) "
                "VALUES (?,?,?,?,?)", (ts, "T-1", "C07-L2-PABUC", ch, val))
    store.commit()

    eng = DetectorEngine(store)
    eng.roll_daily(ts0 + 3600.0, days_back=2, panel_key="T-1")
    store.commit()

    row = store.one("SELECT theta_min, theta_med FROM joint_daily "
                    "WHERE panel_key=? AND joint_key=?", ("T-1", "C07-L2-PABUC"))
    assert row is not None, "joint_daily satiri yazilmadi"
    assert row["theta_med"] is not None
    assert row["theta_min"] == 1.25, f"theta_min yazilmadi: {row['theta_min']!r}"
```

- [ ] **Adım 2: Testi koştur, düştüğünü gör**

Koş: `python -m pytest tests/test_horizon.py -q -k theta_min`
Beklenen: `AssertionError: theta_min yazilmadi: None`

- [ ] **Adım 3: Rollup'a tek kwarg ekle**

`engine.py`'de `upsert_joint_daily(...)` çağrısını (satır ~750) şu hâle getir:

```python
                self.store.upsert_joint_daily(
                    day, pk, jkey,
                    theta_med=float(median(s)), theta_p90=float(p90), n=n,
                    load_mean=float(median(loads)) if loads else 0.0,
                    sens_pct=float(median(sens)) if sens else 0.0,
                    # Gorulebilirlik tabaninin KENDISI.  Sema bu kolonu bastan
                    # tanimliyordu ama rollup onu atliyordu: tmins yalniz
                    # load_mean'i turetmek icin okunuyordu.  Ufuk projeksiyonu
                    # "bu esik bu yukte gorunur mu" sorusunu bu kolona soruyor,
                    # yuzdeye degil.
                    theta_min=float(median(tmins)) if tmins else None,
                )
```

- [ ] **Adım 4: Testi koştur, geçtiğini gör**

Koş: `python -m pytest tests/test_horizon.py -q -k theta_min`
Beklenen: 1 passed.

Koş: `python -m pytest -q`
Beklenen: hepsi yeşil (mevcut 138 + yeni testler).

- [ ] **Adım 5: Commit**

```bash
git add panogoz/detector/engine.py tests/test_horizon.py
git commit -m "roll_daily: joint_daily.theta_min artık yazılıyor

Şema bu kolonu baştan tanımlıyordu; rollup det.theta_min_k örneklerini
okuyup yalnız load_mean'i türetiyor, kolonu boş bırakıyordu. Ufuk
projeksiyonunun görünürlük kapısı bu kolonu okuyor.

Uyarı: joint_sample 90 günde budandığı için daha eski günlük satırlar
geriye doldurulamaz; onlar için kapı yetersiz veri tarafına düşer."
```

---

## Görev 5: `engine` bağlantısı

**Dosyalar:**
- Değiştir: `panogoz/detector/engine.py:122` (merdiven ilanı), `:243-252`
  (`_JointRuntime`), `:766-831` (`_refresh_stats`), `:925-1005` (`evaluate`)
- Test: `tests/test_horizon.py`

**Arayüzler:**
- Tüketir: `horizon.project`, `contracts.live.EtaView`
- Üretir:
  - `engine.THETA_ABS_LADDER: tuple[tuple[str, float], ...]`
  - `_JointRuntime.eta: EtaView`
  - `JointView.eta` dolu · `PanelLive.eta` en ağır hedeften yükseltilmiş

- [ ] **Adım 1: Kırmızı testi yaz**

```python
def test_ladder_is_built_from_the_existing_constants():
    from panogoz.detector import engine as eng
    assert eng.THETA_ABS_LADDER == (
        ("IZLE", eng.THETA_ABS_IZLE_K),
        ("UYARI", eng.THETA_ABS_UYARI_K),
        ("KRITIK", eng.THETA_ABS_KRITIK_K),
        ("ACIL", eng.THETA_ABS_ACIL_K))
    # Sayilar ikinci kez yazilmadi.
    assert [t for _n, t in eng.THETA_ABS_LADDER] == [2.0, 5.0, 12.0, 25.0]


def test_panel_eta_prefers_the_heaviest_target_not_the_soonest_day():
    """IZLE'ye 3 gun, KRITIK'e 18 gunun onune GECMEZ."""
    from panogoz.detector.engine import lift_panel_eta
    from panogoz.contracts.live import EtaView, JointView

    def jv(key, target, days):
        v = JointView(key=key, label="", zone="", conductor="L",
                      feeder_index=1, rated_a=400.0, monitored=True)
        v.eta = EtaView(target=target, days=days)
        return v

    joints = [jv("A", "IZLE", 3.0), jv("B", "KRITIK", 18.0),
              jv("C", "KRITIK", 41.0), jv("D", None, None)]
    got = lift_panel_eta(joints)
    assert got.target == "KRITIK" and got.days == 18.0

    # Hicbiri sayi vermiyorsa bos EtaView doner, uydurma yok.
    assert lift_panel_eta([jv("D", None, None)]).days is None
    assert lift_panel_eta([]).days is None
```

- [ ] **Adım 2: Testi koştur, düştüğünü gör**

Koş: `python -m pytest tests/test_horizon.py -q -k "ladder or panel_eta"`
Beklenen: `AttributeError: module ... has no attribute 'THETA_ABS_LADDER'` ve
`ImportError: cannot import name 'lift_panel_eta'`

- [ ] **Adım 3: Merdiveni ve yükseltme yardımcısını ekle**

`engine.py`'de `THETA_ABS_ACIL_K = 25.0` satırından sonra:

```python
#: Mutlak theta merdiveni, ufuk projeksiyonunun hedef sectigi sira.
#:
#: Dort sabitten TUREIR, onlari tekrar etmez: bir esigi degistiren kisi tek
#: yerde degistirir.  horizon.project() bunu PARAMETRE olarak alir; engine'i
#: import etmez, cunku engine zaten changepoint'i import ediyor ve ters yon
#: dongu kurardi.
THETA_ABS_LADDER: tuple[tuple[str, float], ...] = (
    ("IZLE", THETA_ABS_IZLE_K),
    ("UYARI", THETA_ABS_UYARI_K),
    ("KRITIK", THETA_ABS_KRITIK_K),
    ("ACIL", THETA_ABS_ACIL_K),
)
```

Aynı dosyanın modül düzeyinde (sınıfın dışında, `_JointRuntime`'dan önce) ekle:

```python
def lift_panel_eta(joints: Sequence[JointView]) -> EtaView:
    """Panonun projeksiyonu: hedefi en agir, esitlikte gunu en yakin baglanti.

    Sadece min(gun) almak yanlis olurdu: IZLE'ye 3 gun kalan bir baglanti,
    KRITIK'e 18 gun kalanin onune gecer ve kontrol odasi yanlis panoya bakar.
    theta_delta_7d EN KOTU baglantidan yukseltilir; bu FARKLI bir anahtarla
    yukseltilir ve ikisi ayni sey degildir.
    """
    ranked = [j.eta for j in joints
              if j.eta.days is not None and j.eta.target]
    if not ranked:
        return EtaView()
    return max(ranked, key=lambda e: (channels.SEVERITY_RANK.get(e.target, 0),
                                      -(e.days or 0.0)))
```

`import` satırlarına `Sequence` gerekiyorsa ekle (`from typing import Any, Sequence`),
ve `contracts.live` import satırına `EtaView` ekle:

```python
from panogoz.contracts.live import (ArcView, DeviceView, EtaView, JointView,
                                    PanelLive, PdView)
```

`panogoz.detector` import bloğuna ekle:

```python
from panogoz.detector import horizon as hz
```

- [ ] **Adım 4: Testi koştur, geçtiğini gör**

Koş: `python -m pytest tests/test_horizon.py -q -k "ladder or panel_eta"`
Beklenen: 2 passed.

- [ ] **Adım 5: `_JointRuntime`'a alanı ekle**

`_JointRuntime` gövdesinde `note: str = ""` satırından önce:

```python
    eta: EtaView = field(default_factory=EtaView)
```

- [ ] **Adım 6: `_refresh_stats`'te hesapla**

`_refresh_stats` içinde, nötr dalında `jr.delta_7d = cp.theta_delta(...)` satırından
sonra, `self._save_joint_state(...)` çağrısından önce ekle:

```python
                jr.eta = hz.project([], [], [], THETA_ABS_LADDER,
                                    conductor="N")
```

Aynı fonksiyonun ana dalında, `jr.alarm_days = sum(...)` bloğundan sonra, satır
sonundaki `self._save_joint_state(panel_key, j.key, jr)`'den önce ekle:

```python
            # Ufuk, gunluk tablonun GECERLI satirlarindan hesaplanir.  ``vals``
            # yukarida None'lari 0.0'a cevirdigi icin yeniden kullanilamaz: bos
            # bir gunu 0 K olarak okumak, olmayan bir gunu olculmus saymaktir.
            ok = [r for r in rows
                  if (r.get("n") or 0) > 0 and r.get("theta_med") is not None]
            jr.eta = hz.project(
                [float(r["theta_med"]) for r in ok],
                [float(r["day"]) * DAY_S for r in ok],
                [float(r["theta_min"]) if r.get("theta_min") is not None
                 else float("inf") for r in ok],
                THETA_ABS_LADDER,
                conductor=j.conductor,
            )
```

**Not:** `theta_min` bilinmiyorsa `inf` geçilir, yani kapı "görünürlük düşük"
tarafına düşer. Bilmediğimiz bir tabanla eşiğin görünür olduğunu **iddia etmeyiz**.
Görev 4 bu kolonu doldurduğu için yeni satırlarda `inf` görülmez.

- [ ] **Adım 7: `evaluate`'te görünümlere yaz**

Nötr dalında `jv.slope_k_per_week = jr.slope` satırından sonra:

```python
                jv.eta = jr.eta
```

Ana dalda `jv.alarm_days = jr.alarm_days` satırından sonra:

```python
            jv.eta = jr.eta
```

`live.joints = views` satırından sonra:

```python
        live.eta = lift_panel_eta(views)
```

- [ ] **Adım 8: Uçtan uca testi yaz ve koştur**

`tests/test_horizon.py` sonuna ekle:

```python
def test_engine_exposes_eta_on_joint_and_panel():
    """Dedektorun kendi kabul kosumu: demo panosunda projeksiyon gorunur."""
    from panogoz.detector.engine import demo_panel  # noqa: F401  (varsa)
```

> **Uygulayıcıya not:** `engine.py`'nin öz-testi (`if __name__ == "__main__"`,
> satır ~1490) 40 günlük bir rampa kuruyor ve `live` nesnesini basıyor. Uçtan uca
> doğrulama Görev 10'da `tests/test_integration.py` üzerinden yapılacak; burada
> yalnız modülün kendi öz-testine bir satır eklenir. Yukarıdaki iskelet testi
> **yazma**, yerine aşağıdaki adımı uygula.

`engine.py` öz-testinde, `jv.theta_min_k ... görünürlük` satırını basan `print`'ten
sonra ekle:

```python
    print(f"    ufuk: {jv.eta.target or '—'} · "
          f"{'—' if jv.eta.days is None else format(jv.eta.days, '.0f') + ' g'} "
          f"· gerekçe {jv.eta.reason or '(yok)'} · "
          f"geçerli gün {jv.eta.valid_days}")
```

Koş: `PYTHONIOENCODING=utf-8 python -m panogoz.detector.engine`
Beklenen: `all detector claims verified` ve yeni `ufuk:` satırı; 40 günlük rampada
`gerekçe (yok)` ve bir gün sayısı görünür.

Koş: `python -m pytest -q`
Beklenen: hepsi yeşil.

- [ ] **Adım 9: Commit**

```bash
git add panogoz/detector/engine.py tests/test_horizon.py
git commit -m "engine: ufuk projeksiyonunu joint_daily'den kurar ve görünümlere yazar

THETA_ABS_LADDER dört mevcut sabitten türer, onları tekrar etmez.
_refresh_stats her turda joint_daily'nin GEÇERLİ satırlarından yeniden
hesaplar: joint_state'e yazılmaz, çünkü sekiz ay sonra SELECT ile
yeniden üretilemeyen bir istatistik kanıt değildir.

theta_min bilinmiyorsa inf geçilir ve kapı 'görünürlük düşük' tarafına
düşer: bilmediğimiz bir tabanla eşiğin görünür olduğunu iddia etmeyiz.

lift_panel_eta hedefi en ağır bağlantıyı seçer, gününü en yakın olanı
değil. IZLE'ye 3 gün, KRITIK'e 18 günün önüne geçemez."
```

---

## Görev 6: API projeksiyonları

**Dosyalar:**
- Değiştir: `panogoz/api/app.py:145-173` (`panel_summary`), `:645-659` (`/onset`)
- Test: `tests/test_horizon.py`

**Arayüzler:**
- Tüketir: `PanelLive.eta`, `JointView.eta`
- Üretir: `/api/fleet` → `panels[].eta`; `/api/panel/{key}` → `eta` ve `joints[].eta`
  (`PanelLive.to_dict()` üzerinden kendiliğinden); `/api/panel/{key}/onset` → `eta`

- [ ] **Adım 1: Kırmızı testi yaz**

```python
def test_api_exposes_eta_in_fleet_and_panel():
    from fastapi.testclient import TestClient
    from panogoz.api.app import create_app
    from panogoz.api.runtime import Runtime

    rt = Runtime(panels=4, backfill_days=20, db_path=":memory:")
    rt.prime()
    app = create_app(rt)
    with TestClient(app) as c:
        fleet = c.get("/api/fleet").json()
        assert fleet["panels"], "filo bos"
        for p in fleet["panels"]:
            assert "eta" in p, "panel_summary eta tasimiyor"
            assert set(p["eta"]) >= {"target", "days", "days_lo", "days_hi",
                                     "reason", "valid_days", "capped", "model"}
        key = fleet["panels"][0]["panel_key"]
        panel = c.get(f"/api/panel/{key}").json()
        assert "eta" in panel
        assert all("eta" in j for j in panel["joints"])
        onset = c.get(f"/api/panel/{key}/onset").json()
        assert "eta" in onset
```

> **Uygulayıcıya not:** `Runtime`'ın kurucu imzası ve `prime()` adı bu depoda
> farklı olabilir. Testi yazmadan önce `panogoz/api/runtime.py` içindeki
> `class Runtime` kurucusunu ve `tests/test_integration.py`'nin Runtime'ı nasıl
> kurduğunu oku, **aynı çağrıyı kullan**. Kurulum satırını uydurmayın.

- [ ] **Adım 2: Testi koştur, düştüğünü gör**

Koş: `python -m pytest tests/test_horizon.py -q -k api`
Beklenen: `AssertionError: panel_summary eta tasimiyor`

- [ ] **Adım 3: `panel_summary`'ye ekle**

`"theta_delta_7d": round(live.theta_delta_7d, 2),` satırından sonra:

```python
        "eta": live.eta.to_dict(),
```

- [ ] **Adım 4: `/onset`'e ileri yönü ekle**

`/onset` gövdesindeki `return _clean(rt.first_alarm_day(key, joint))` satırını
şununla değiştir:

```python
        out = dict(rt.first_alarm_day(key, joint))
        # Ucun ucuncu zaman sorusu.  Ilk ikisi geriye bakiyor - bozulma ne zaman
        # BASLADI, kanit ne zaman YETERLI oldu.  Bu ileriye bakar ve ayni
        # joint_daily oynatmasindan cikar, bu yuzden ayri bir uc acilmiyor:
        # kanit ekrani ucunu tek istekle alir.
        jv = next((j for j in live.joints if j.key == joint), None)
        out["eta"] = jv.eta.to_dict() if jv is not None else EtaView().to_dict()
        return _clean(out)
```

`app.py`'nin import bloğuna `EtaView` ekle:

```python
from panogoz.contracts.live import AlarmView, EtaView
```

> **Uygulayıcıya not:** `app.py`'de `contracts.live`'dan hangi adların import
> edildiğini kontrol et ve **var olan satıra ekle**, yeni bir import satırı açma.

- [ ] **Adım 5: Testi koştur, geçtiğini gör**

Koş: `python -m pytest tests/test_horizon.py -q -k api`
Beklenen: 1 passed.

Koş: `python -m tests.test_integration`
Beklenen: mevcut sayıda geçti, kaldı 0.

- [ ] **Adım 6: Commit**

```bash
git add panogoz/api/app.py tests/test_horizon.py
git commit -m "api: eta filo kartında, pano görüntüsünde ve /onset'te

Yeni uç açılmadı. /onset iki zaman sorusunu cevaplıyordu (ne zaman
başladı, kanıt ne zaman yeterli oldu); üçüncüsü aynı joint_daily
oynatmasından çıkıyor, bu yüzden aynı uca kondu. Kanıt ekranı üç cevabı
tek istekle alıyor."
```

---

## Görev 7: Bildirim metni ve parça sözleşmesi

**Dosyalar:**
- Değiştir: `panogoz/notify/escalation.py:143-186` (`compose`)
- Test: `tests/test_horizon.py`

**Arayüzler:**
- Tüketir: `PanelLive.joints[].eta`
- Üretir: `compose()` gövdesi eta satırını taşır; gövde **2 UCS2 parçasını geçmez**

- [ ] **Adım 1: Kırmızı testi yaz**

```python
def test_sms_carries_the_horizon_and_never_a_third_part():
    from panogoz.contracts.live import EtaView, JointView, PanelLive
    from panogoz.notify import escalation as esc
    from panogoz.notify import sms

    live = PanelLive(panel_key="SOKE-14", panel_index=14, site="Söke", name="Söke 14")
    jv = JointView(key="C07-L2-PABUC", label="", zone="", conductor="L",
                   feeder_index=7, rated_a=400.0, monitored=True)
    jv.theta_k = 8.4
    jv.eta = EtaView(target="KRITIK", days=21.0, days_lo=13.0, days_hi=32.0)
    live.joints = [jv]
    live.health_index = 71.0
    inc = {"id": 1284, "panel_key": "SOKE-14", "joint_key": "C07-L2-PABUC",
           "severity": "KRITIK", "mode": "loose_connection"}

    body = esc.compose(inc, live)
    assert "KRITIK'e 21 g (13-32)" in body
    assert len(sms.split_ucs2(body)) <= 2, f"ucuncu parca acildi: {len(body)} karakter"

    # Gerekce kodu varsa satir HIC eklenmez.
    jv.eta = EtaView(reason="YETERSIZ_GECMIS", valid_days=9)
    assert "g (" not in esc.compose(inc, live)

    # Sonsuz ust sinir SMS'te '+' ile yazilir; unicode sonsuz isareti gitmez.
    jv.eta = EtaView(target="UYARI", days=62.0, days_lo=38.0, days_hi=None)
    inf_body = esc.compose(inc, live)
    assert "UYARI'e 62 g (38+)" in inf_body
    assert "∞" not in inf_body

    # Butce daralirsa ILK dusen sey eta satiridir, aksiyon metni degil.
    jv.eta = EtaView(target="KRITIK", days=21.0, days_lo=13.0, days_hi=32.0)
    long_inc = dict(inc, panel_key="X" * 60)
    long_live = PanelLive(panel_key="X" * 60, panel_index=1, site="", name="")
    long_live.joints = [jv]
    tight = esc.compose(long_inc, long_live)
    assert len(sms.split_ucs2(tight)) <= 2
    assert "onay: TAMAM" in tight
```

- [ ] **Adım 2: Testi koştur, düştüğünü gör**

Koş: `python -m pytest tests/test_horizon.py -q -k sms`
Beklenen: `AssertionError: assert "KRITIK'e 21 g (13-32)" in body`

- [ ] **Adım 3: `compose`'u değiştir**

`escalation.py`'de `head = f"PANO GÖZ ..."` satırından önce ekle:

```python
    # Ufuk satiri.  Metni kuran yer burasi; sms.py yalniz tasima katmanidir.
    #
    # Butce 160 DEGILDIR: Turkce metin GSM-7'ye girmedigi icin UCS2 gider ve tek
    # parca 70, birlesik parca 67 karakterdir.  Olculen mevcut govdeler 76-90
    # karakter, yani zaten iki parca; +24 karakter ucuncu parca acmiyor.
    eta_bit = ""
    if live is not None:
        jv_eta = next((j.eta for j in live.joints
                       if j.key == incident.get("joint_key")), None)
        if jv_eta is not None and not jv_eta.reason and jv_eta.days is not None:
            lo = 0 if jv_eta.days_lo is None else int(jv_eta.days_lo)
            # Sonsuz ust sinir '+' ile yazilir: Unicode sonsuz isareti UCS2'de
            # yer kaplar ve bazi eski terminallerde okunmaz.
            hi = f"{lo}+" if jv_eta.days_hi is None else f"{lo}-{int(jv_eta.days_hi)}"
            eta_bit = f" · {jv_eta.target}'e {int(jv_eta.days)} g ({hi})"
```

`body` kurulumunu ve bütçe döngüsünü şununla değiştir:

```python
    head = f"PANO GÖZ {SEVERITY_TR[sev].upper()} · {panel} · {joint}"

    def _build() -> str:
        return (f"{head} {metric} · {action}{eta_bit} · "
                f"onay: TAMAM {incident.get('id', 0)} {tok}")

    body = _build()
    # Butce daralirsa ILK dusen sey ufuk satiridir.  Operatore "baglantiyi
    # torkla" demek, "21 gun" demekten degerlidir.
    if eta_bit and len(split_ucs2(body)) > 2:
        eta_bit = ""
        body = _build()
    while len(body) > 2 * UCS2_SINGLE_CHARS and len(action) > 6:
        action = action[:-1].rstrip()
        body = _build()
    return body
```

`escalation.py`'nin `sms` import satırına `split_ucs2` ekle.

> **Uygulayıcıya not:** `escalation.py`'de `UCS2_SINGLE_CHARS`'ın nasıl import
> edildiğini kontrol et ve `split_ucs2`'yi **aynı satıra** ekle. `action`
> kısaltma döngüsünün mevcut gövdesini birebir koru; yalnız `body` kurulumunu
> `_build()`'e çevir.

- [ ] **Adım 4: Testi koştur, geçtiğini gör**

Koş: `python -m pytest tests/test_horizon.py -q -k sms`
Beklenen: 1 passed.

Koş: `PYTHONIOENCODING=utf-8 python -m panogoz.notify.escalation`
Beklenen: modülün kendi öz-testi geçer.

- [ ] **Adım 5: Commit**

```bash
git add panogoz/notify/escalation.py tests/test_horizon.py
git commit -m "escalation: SMS gövdesine ufuk satırı, iki parça sözleşmesiyle

Bütçe 160 değil: Türkçe metin UCS2 gidiyor, tek parça 70 karakter.
Ölçülen mevcut gövdeler 76-90 karakter ve zaten iki parça; +24 karakter
üçüncüyü açmıyor.

Marj ince olduğu için sözleşme açık: bütçe daralırsa ilk düşen şey eta
satırıdır, aksiyon metni değil. Operatöre 'bağlantıyı torkla' demek
'21 gün' demekten değerlidir.

Sonsuz üst sınır SMS'te '+' ile yazılıyor; ∞ işareti gönderilmiyor.

BULUNDU, DÜZELTİLMEDİ: mevcut bütçe tavanı len(body) > 140 karakteri
karşılaştırıyor, oysa iki birleşik UCS2 parçası 134 karakter tutar.
137 karakterlik bir gövde tavanı geçmeden üçüncü parçayı açabilir. Bu
eta satırından önce de vardı; kapsamı büyütmemek için yalnız eta yolu
split_ucs2 ile korundu."
```

---

## Görev 8: Filo kolonu

**Dosyalar:**
- Değiştir: `frontend/js/fmt.js` (sonuna), `frontend/js/view-fleet.js:30-49` (`COLS`),
  `:576-612` (`hucre`), `:626-632` (`satirImza`), `:633-641` (sıralama)
- Test: elle doğrulama (bu depoda JS test takımı yok)

**Arayüzler:**
- Tüketir: `/api/fleet` → `panels[].eta`
- Üretir: `fmt.eta(e) -> string`, `fmt.etaReason(e) -> string`,
  `fmt.ETA_TARGET_W: Record<string, number>`

- [ ] **Adım 1: `fmt.js`'e biçimleyiciyi ekle**

```js
/** Ufuk hedefi agirliklari: siralamada agir hedef one gecer. */
export const ETA_TARGET_W = { ACIL: 4, KRITIK: 3, UYARI: 2, IZLE: 1 };

const ETA_REASON_TR = {
  NOTR_KAPSAM_DISI: 'nötr · kapsam dışı',
  ZIRVEDE: 'en üst basamakta',
  YETERSIZ_GECMIS: 'yetersiz geçmiş',
  GORUNURLUK_DUSUK: 'görünürlük düşük',
  EGIM_YOK: 'eğim yok',
};

/** Gerekcenin operator dilindeki kisa hali; sayinin YERINE gecer. */
export function etaReason(e) {
  if (!e || !e.reason) return '';
  const base = ETA_REASON_TR[e.reason] || e.reason;
  if (e.reason === 'YETERSIZ_GECMIS') return `${base} (${int(e.valid_days)} gün)`;
  return base;
}

/**
 * "KRITIK'e 21 g (13-32)" · ">90 g" · "—"
 *
 * days_hi === null IKI ayri sey olabilir: reason bossa sonsuz (CI sifiri
 * iceriyor), reason doluysa sayi hic yok. Bu yuzden once reason'a bakariz.
 */
export function eta(e) {
  if (!e || e.reason || e.days === null || e.days === undefined) return '—';
  if (e.capped) return '>90 g';
  const lo = e.days_lo === null || e.days_lo === undefined ? 0 : Math.round(e.days_lo);
  const hi = e.days_hi === null || e.days_hi === undefined
    ? '∞' : Math.round(e.days_hi);
  return `${e.target}'e ${Math.round(e.days)} g (${lo}-${hi})`;
}
```

- [ ] **Adım 2: `COLS`'a kolonu ekle**

`view-fleet.js`'de `{ key: 'sensitivity_pct', ... }` girdisinden **önce** ekle:

```js
  {
    key: 'eta', label: 'Eşiğe', type: 'eta',
    tip: 'Bu gidişle bir sonraki seviye basamağına kalan gün, %90 nominal güven '
       + 'aralığıyla. Aralık θ eğiminin parametrik olmayan güven aralığından '
       + 'gelir; alt sınır sıfırı içeriyorsa üst gün sınırı ∞ olur. Sıralama '
       + 'ÖNCE hedefin ağırlığına, sonra güne bakar: IZLE\'ye 3 gün, KRITIK\'e '
       + '18 günün önüne geçmez. Sayı yerine gerekçe yazıyorsa sistem susmayı '
       + 'seçmiştir — yetersiz geçmiş, görünürlük düşük ya da eğim yok.',
  },
```

- [ ] **Adım 3: `hucre`'ye kipi ekle**

`case 'sens':` girdisinden önce ekle:

```js
      case 'eta': {
        const e = p.eta || {};
        if (e.reason || e.days === null || e.days === undefined) {
          return h('td.n', h('span.muted', { text: '—', title: fmt.etaReason(e) }),
            fmt.etaReason(e)
              ? h('span.tiny.muted', { text: ' ' + fmt.etaReason(e) })
              : null);
        }
        const w = fmt.ETA_TARGET_W[e.target] || 0;
        const cls = w >= 3 ? 'delta-up' : 'delta-flat';
        return h('td.n', h('span.' + cls, { text: fmt.eta(e) }));
      }
```

- [ ] **Adım 4: Satır imzasına ve sıralamaya ekle**

`satirImza` dizisine `fmt.signed(p.theta_delta_7d, 2)`'den sonra ekle:

```js
      fmt.eta(p.eta), fmt.etaReason(p.eta),
```

`cizTablo`'daki sıralama karşılaştırıcısına, `if (sortKey === 'severity')`
satırından **sonra** ekle:

```js
      if (sortKey === 'eta') {
        const ea = a.eta || {}, eb = b.eta || {};
        const na = ea.reason || ea.days === null || ea.days === undefined;
        const nb = eb.reason || eb.days === null || eb.days === undefined;
        // Sayi vermeyen satirlar siralama yonu ne olursa olsun SONA gider:
        // bos bir hucre "en yakin" listesinin basinda durmamalidir.
        if (na !== nb) return na ? 1 : -1;
        if (na && nb) return 0;
        const wa = fmt.ETA_TARGET_W[ea.target] || 0;
        const wb = fmt.ETA_TARGET_W[eb.target] || 0;
        if (wa !== wb) return (wb - wa) * sortDir;
        return ((Number(ea.days) || 0) - (Number(eb.days) || 0)) * sortDir;
      }
```

- [ ] **Adım 5: Elle doğrula**

Koş: `python -m panogoz.run_local --panels 12 --backfill-days 40 --port 8099`

Tarayıcıda `http://127.0.0.1:8099/`:
1. Filo tablosunda "Eşiğe" kolonu görünüyor.
2. Varsayılan sıralama hâlâ **Δ7 gün** (kolon başlığındaki ok orada).
3. "Eşiğe" başlığına tıklayınca ağır hedefler başa geliyor, `—` satırları sonda.
4. Tekrar tıklayınca yön dönüyor ama `—` satırları **hâlâ** sonda.
5. Kolon ipucu görünüyor.

- [ ] **Adım 6: Commit**

```bash
git add frontend/js/fmt.js frontend/js/view-fleet.js
git commit -m "Arayüz: filo tablosuna 'Eşiğe' kolonu

Sıralama bileşik: önce hedefin ağırlığı, sonra gün. Sayı vermeyen
satırlar sıralama yönü ne olursa olsun sona gider. Varsayılan sıralama
Δ7 gün olarak KALIYOR: belgelenmiş bir varsayılanı değiştirmiyoruz.

Biçimleyici fmt.js'te tek yerde; kanıt ve alarm ekranları da onu
kullanacak."
```

---

## Görev 9: Kanıt kartı ve alarm cümlesi

**Dosyalar:**
- Değiştir: `frontend/js/view-evidence.js` (yeni `projectionCard`, θ grafiğine hline,
  `update()` içine montaj)
- Değiştir: `frontend/js/view-alarms.js` (olay kartına tek cümle)

**Arayüzler:**
- Tüketir: `/api/panel/{key}` → `joints[].eta`, `fmt.eta`, `fmt.etaReason`
- Üretir: yok

**Spec sapması:** Projeksiyon θ grafiğinin üstüne **çizilmiyor**. Dört grafik tek ve
ortak x eksenini paylaşıyor ve eksenin sağ kenarı "şimdi"; gelecekteki kesişim tuvalin
dışına düşer, alanı uzatmak dört grafiği birden bozar. Onun yerine θ grafiğine hedef
eşik yatay çizgisi eklenir ve projeksiyon ayrı bir metin kartı olur.

- [ ] **Adım 1: θ grafiğine hedef eşik çizgisini ekle**

`view-evidence.js`'de üçüncü `TimeChart`'ın `hlines` dizisine, `alarm eşiği 5 K`
girdisinden sonra ekle:

```js
          ...(joint.eta && joint.eta.target && !joint.eta.reason
            ? [{ value: THETA_LADDER[joint.eta.target], color: C.esik,
                 label: `${joint.eta.target} eşiği `
                      + `${fmt.num(THETA_LADDER[joint.eta.target], 0)} K` }]
            : []),
```

Dosyanın `CH` bildiriminden sonra ekle:

```js
// Esik merdiveni. Sunucudaki engine.THETA_ABS_LADDER'in AYNISI olmak zorunda;
// burada yalniz cizgiyi nereye cizecegimizi bilmek icin duruyor.
const THETA_LADDER = { IZLE: 2, UYARI: 5, KRITIK: 12, ACIL: 25 };
```

- [ ] **Adım 2: Projeksiyon kartını yaz**

`resistanceCard` fonksiyonundan sonra ekle:

```js
  /** Projeksiyon: bir sonraki basamaga kalan gun, ya da neden susuyoruz.
   *
   *  Kesikli yelpaze CIZILMIYOR ve bu bilincli: dort grafik tek ve ortak bir x
   *  eksenini paylasiyor, o eksenin sag kenari "simdi"dir ve gelecekteki
   *  kesisim tuvalin disina duser. Alani gelecege uzatmak dort grafigi birden
   *  sikistirir. Uc sayinin tasimadigi bir bilgi de yok.
   */
  function projectionCard(joint) {
    const e = (joint && joint.eta) || {};
    const rows = [];
    if (e.reason) {
      rows.push(['durum', fmt.etaReason(e)]);
      if (e.target) rows.push(['hedef basamak', e.target]);
    } else if (e.days !== null && e.days !== undefined) {
      rows.push(['hedef basamak',
        `${e.target} · ${fmt.num(THETA_LADDER[e.target], 0)} K`]);
      rows.push(['kalan', fmt.eta(e)]);
      rows.push(['eğim (projeksiyonun kullandığı)',
        `${fmt.signed(e.slope_k_per_week, 2)} K/hafta`]);
      rows.push(['%90 nominal güven aralığı',
        `${fmt.signed(e.slope_lo_k_per_week, 2)} … `
        + `${fmt.signed(e.slope_hi_k_per_week, 2)} K/hafta`]);
      rows.push(['pencerede geçerli gün', `${fmt.int(e.valid_days)} / 21`]);
    } else {
      rows.push(['durum', '—']);
    }

    const notes = [];
    if (e.from_changepoint && e.changepoint_ts) {
      notes.push(`${fmt.date(e.changepoint_ts)} tarihinde bir basamak var; `
        + 'projeksiyon yalnız o günden sonrasını kullanıyor. Filo tablosundaki '
        + '21 günlük eğim pencerenin tamamını görür — iki sayı, iki soru.');
    }
    if (e.days_hi === null && !e.reason && e.days !== null
        && e.days !== undefined) {
      notes.push('Güven aralığının alt sınırı sıfırın altında: yükseliyor '
        + 'olabilir de olmayabilir de. Üst gün sınırı bu yüzden sonsuzdur.');
    }
    if (e.capped) {
      notes.push('Medyan 90 günü geçiyor. 21 günlük bir pencereden daha uzun '
        + 'bir tarih türetmek, gözlem penceresinin katlarına ekstrapolasyondur; '
        + 'bu yüzden gün sayısı değil eşik yazılır.');
    }
    if (!e.reason && e.days !== null && e.days !== undefined) {
      notes.push('Model doğrusaldır. Isıl kaçış süper-doğrusaldır, yani o modda '
        + 'bu sayı iyimserdir: gerçek tarih daha erken olabilir.');
    }

    return h('div.card',
      h('div.card-h', h('b', { text: 'Projeksiyon' }),
        h('span.tiny.muted', { text: 'θ eğiminden, ileriye' })),
      h('table.kv', ...rows.map(([k, v]) =>
        h('tr', h('th', { text: k }), h('td', { text: v })))),
      ...notes.map((t) => h('div.tiny.muted', { text: t })));
  }
```

- [ ] **Adım 3: Kartı `update()` içinde monte et**

`update(state)` içinde `resistanceCard(joint)`'ın monte edildiği yeri bul ve hemen
ardına `projectionCard(joint)` ekle — `resistanceCard` ile **aynı** kapsayıcıya,
aynı çağrı biçimiyle.

> **Uygulayıcıya not:** `update()` gövdesinde `resistanceCard` çağrısının hangi
> `mount(...)` / `h(...)` ağacında durduğunu oku ve `projectionCard(joint)`'ı
> o ağaca, ondan sonraki kardeş olarak ekle. Yeni bir kapsayıcı açma.

- [ ] **Adım 4: Alarm ekranına tek cümleyi ekle**

`view-alarms.js`'de olay kartının gövdesine, olayın `panel` nesnesi elde ediliyorsa
şu satırı ekle:

```js
      ...(eta && !eta.reason && eta.days !== null && eta.days !== undefined
        ? [h('div.tiny', { text: `Bu gidişle ${fmt.eta(eta)}.` })]
        : []),
```

> **Uygulayıcıya not:** `view-alarms.js` olay satırını `/api/alarms`'tan kuruyor
> ve o uç `eta` taşımıyor. Kartı çizen fonksiyonun elinde pano görüntüsü varsa
> `eta`'yı oradan al (`panel.joints.find((j) => j.key === inc.joint_key).eta`);
> **yoksa bu adımı atla ve atladığını raporla.** `/api/alarms`'a eta eklemek bu
> planın kapsamı dışındadır — olay satırı bir `incident` tablosu projeksiyonudur
> ve canlı bir türetilmiş sayıyı oraya koymak iki kaynağı karıştırır.

- [ ] **Adım 5: Elle doğrula**

Koş: `python -m panogoz.run_local --panels 12 --backfill-days 40 --port 8099`

1. Kanıt ekranında "Projeksiyon" kartı görünüyor.
2. Sayı çıkan bir bağlantıda: hedef, kalan, eğim, CI, geçerli gün ve doğrusallık
   notu var.
3. Sağlıklı bir bağlantıda: gerekçe yazıyor, uydurma sayı **yok**.
4. θ grafiğinde hedef eşik çizgisi ve etiketi görünüyor.
5. Dört grafiğin x ekseni hâlâ senkron, nişangâh hâlâ dördünde birlikte hareket
   ediyor.

- [ ] **Adım 6: Commit**

```bash
git add frontend/js/view-evidence.js frontend/js/view-alarms.js
git commit -m "Arayüz: kanıt ekranına projeksiyon kartı, θ grafiğine hedef eşik

Projeksiyon θ grafiğinin üstüne ÇİZİLMİYOR ve bu bilinçli: dört grafik
tek ve ortak bir x eksenini paylaşıyor, eksenin sağ kenarı 'şimdi' ve
gelecekteki kesişim tuvalin dışına düşüyor. Alanı geleceğe uzatmak dört
grafiği birden sıkıştırır ve senkron eksen sözünü bozar.

Kart susma gerekçesini sayının YERİNE yazıyor, yanına değil. Basamak
notu, sonsuz sınır notu ve doğrusallık notu koşullu."
```

---

## Görev 10: Negatif boru hattı, uçtan uca kapı, belgeler

**Dosyalar:**
- Değiştir: `tests/test_negative_pipeline.py`, `tests/test_integration.py`
- Değiştir: `docs/04-ANOMALI-TESPIT.md`, `README.md`, `docs/08-DEMO-SENARYOSU.md`,
  `docs/11-ACIK-SORULAR.md`

**Arayüzler:**
- Tüketir: hepsi
- Üretir: yok

- [ ] **Adım 1: Negatif kontrol testini yaz**

`tests/test_negative_pipeline.py`'ye, mevcut yedi negatif kontrolü gezen testin
yanına ekle:

```python
def test_negative_controls_produce_no_horizon():
    """Yedi negatif kontrolun hicbiri gecerli bir projeksiyon uretmemeli.

    Pozitif kontrol AYNI kosumda uretmeli; onsuz "projeksiyon yok" ile
    "projeksiyon calismiyor" ayirt edilemez.
    """
```

> **Uygulayıcıya not:** Bu dosyanın mevcut testleri simülatör → ağ geçidi →
> dedektör → suppression → fusion zincirini nasıl kurduğunu oku ve **aynı
> yardımcıyı** kullan. Her negatif senaryo için `live.eta.reason` dolu ya da
> `live.eta.days is None` olduğunu doğrula; `gevsek_baglanti` pozitif kontrolünde
> `live.eta.days is not None` ve `live.eta.target` dolu olduğunu doğrula.
> Yardımcı fonksiyonun adını uydurma.

- [ ] **Adım 2: Testi koştur**

Koş: `python -m pytest tests/test_negative_pipeline.py -q`
Beklenen: hepsi geçer; pozitif kontrol projeksiyon üretir.

- [ ] **Adım 3: Uçtan uca şema kapısını ekle**

`tests/test_integration.py`'de `/api/panel/{key}` çıktısını doğrulayan bölüme ekle:
`panel["eta"]` sözlüğünün `{"target","days","days_lo","days_hi","reason",
"valid_days","slope_k_per_week","capped","model","from_changepoint",
"changepoint_ts","slope_lo_k_per_week","slope_hi_k_per_week"}` anahtarlarını
taşıdığını ve `joints` içindeki her girdinin `eta` taşıdığını kontrol et.

- [ ] **Adım 4: Tüm takımı koştur**

```
python -m pytest -q
python -m tests.test_rules
python -m tests.test_detector
python -m tests.test_integration
PYTHONIOENCODING=utf-8 python -m panogoz.detector.changepoint
PYTHONIOENCODING=utf-8 python -m panogoz.detector.horizon
PYTHONIOENCODING=utf-8 python -m panogoz.detector.engine
```

Beklenen: hepsi yeşil. Çıktıları PR açıklamasına yapıştırılmak üzere sakla.

- [ ] **Adım 5: `docs/04`'e bölüm ekle**

`docs/04-ANOMALI-TESPIT.md`'ye yeni bölüm: yöntem (Sen rank aralığı, muhafazakâr
rank seçimi ve ölçülen %88–93 kapsama), susma sözleşmesi tablosu (beş kod),
görünürlük kriterinin neden yüzde olmadığı, basamak/rampa ayrımı ve iki eğimin neden
ayrı durduğu, doğrusallık itirafı, ve bölümün sonunda **"yapmadığı şeyler"** listesi:
süper-doğrusal model yok, mevsimsel model yok, otomatik iş emri yok, kesinti
planlaması yok, SCADA register'ı yok.

- [ ] **Adım 6: `README` ve `docs/08`, `docs/11`**

- `README.md` §1: ileri yönlü projeksiyonun da geçmiş gerektirdiği (≥14 geçerli gün)
  tek satır.
- `README.md` §9 "Belgelendi, kodlanmadı" tablosuna satır: **ETA için SCADA register
  bloğu — yazılmadı**, gerekçesi 48 register'lık pano bloğunun dolu olması.
- `docs/08-DEMO-SENARYOSU.md`: jürinin gün sayısını gördüğü beat, repliğiyle ve
  "bunu neden bazı bağlantılarda söylemiyoruz" cümlesiyle.
- `docs/11-ACIK-SORULAR.md`: yeni soru — DSO'nun iş emri planlama ufku kaç gündür?
  90 gün tavanı ve 14 gün kapısı bu cevaba göre değişir.

- [ ] **Adım 7: Commit**

```bash
git add tests/ docs/ README.md
git commit -m "Eşiğe kalan gün: negatif kontroller, uçtan uca kapı ve belgeler

Yedi negatif kontrolün hiçbiri projeksiyon üretmiyor; pozitif kontrol
aynı koşumda üretiyor. Onsuz 'projeksiyon yok' ile 'projeksiyon
çalışmıyor' ayırt edilemezdi.

docs/04'e yöntem, susma sözleşmesi ve yapmadığı şeyler; README §9'a
SCADA register bloğunun yazılmadığı ve nedeni; docs/11'e DSO'nun
planlama ufku sorusu."
```

---

## Öz-gözden geçirme

**1. Spec kapsaması.** Spec bölüm bölüm:

| Spec | Görev |
|---|---|
| §1 girdi ve birim sözleşmesi | 3 (`project` imzası), 5 (geçerli satır filtresi) |
| §2 Theil-Sen CI | 1 |
| §2.3 sayısal kontrol | 1 (test + öz-test) |
| §2.4 `theil_sen` değişmez | 1 (test) |
| §3 projeksiyon aritmetiği, §3.1 yuvarlama | 3 (test + uygulama) |
| §4 hedef seçimi, merdiven parametre | 3, 5 |
| §5 beş kapı | 3 |
| §5.1 görünürlük kriteri | 3 (kapı), **4** (kolonun doldurulması) |
| §5.2 14 gün, §5.3 90 gün | 3 (sabitler + testler) |
| §6.1 doğrusallık | 3 (`model`), 9 (arayüz notu), 10 (belge) |
| §6.2 basamak ↔ rampa | 3 (en önemli gerileme testi) |
| §7 pano yükseltme ve sıralama | 5 (`lift_panel_eta`), 8 (kolon sıralaması) |
| §8.1 kalıcılık yok | 5 (`_refresh_stats`, `_save_joint_state`'e **eklenmedi**) |
| §8.2 `EtaView` | 2 |
| §8.3 uçlar | 6 |
| §9 arayüz | 8, 9 (**sapma belgelendi**) |
| §10 bildirim | 7 |
| §11 SCADA'ya dokunulmuyor | — (kasıtlı olarak hiçbir görev) |
| §12 test planı, §12.1 | 1, 3, 10 |
| §13 belgeler | 10 |
| §14 kapsam dışı | — |

Boşluk yok. §5.1 spec yazılırken bilinmeyen bir ön koşul çıkardı (`theta_min`
yazılmıyor) ve Görev 4 olarak eklendi.

**2. Placeholder taraması.** "TBD"/"sonra"/"uygun hata yönetimi ekle" yok. Üç yerde
uygulayıcıya *oku ve aynısını kullan* notu var — Görev 6 Adım 1 (`Runtime` kurucusu),
Görev 9 Adım 3-4 (`update()` ağacı ve `view-alarms.js`'in veri kaynağı), Görev 10
Adım 1 (negatif boru hattı yardımcısı). Bunlar placeholder değil: kodu uydurmak yerine
depodaki gerçek çağrıyı okumayı **şart koşan** talimatlar, ve Görev 9 Adım 4'te
atlama koşulu açıkça tanımlı.

**3. Tip tutarlılığı.** `EtaView` alan adları Görev 2'de tanımlandığı gibi 3, 5, 6, 7,
8, 9'da birebir kullanıldı: `target`, `days`, `days_lo`, `days_hi`,
`slope_k_per_week`, `slope_lo_k_per_week`, `slope_hi_k_per_week`, `valid_days`,
`from_changepoint`, `changepoint_ts`, `model`, `capped`, `reason`. `horizon.project`
imzası Görev 3'te tanımlandı ve Görev 5'te aynı sırayla çağrıldı
(`values, times, theta_min, ladder, *, conductor`). `fmt.eta` / `fmt.etaReason` /
`fmt.ETA_TARGET_W` Görev 8'de tanımlandı, Görev 8 ve 9'da aynı adlarla kullanıldı.
`lift_panel_eta` Görev 5'te tanımlandı, yalnız orada kullanıldı.
`changepoint.slope_ci_per_week` Görev 1'de tanımlandı, Görev 3'te ve testlerde aynı
imzayla çağrıldı.
