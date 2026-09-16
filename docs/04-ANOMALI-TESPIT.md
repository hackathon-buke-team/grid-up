# K4 · Anomali Tespit — CUSUM/Değişim Noktası ve expect_flags (4.3)

> Bu belge K4 iş paketinin **4.3 `expect_flags` sözleşme açıkları** maddesini
> karşılar, ve CLAUDE.md §2 mimarisinde geçen "günlük medyanlarda CUSUM +
> değişim noktası" katmanının çekirdek uygulamasını (K3 3.2 "Kanıt ekranı"nın
> arka uç temeli — **UI kısmı bu görevin kapsamında değil**, ayrı bir gelecek
> K3 maddesi) belgeler.

## 1. CUSUM + değişim noktası (`panogoz/detector/cusum.py`)

**Kullanılan varyant:** standart iki-taraflı Page CUSUM testi (Page, 1954;
parametreleme Montgomery'nin *Introduction to Statistical Quality Control*
kural-of-thumb'ına dayanıyor). θ'nın anlık eşik+debounce kuralları
(`panogoz/rules/engine.py`) ani/büyük sapmaları yakalar; CUSUM bunun
tamamlayıcısı — **haftalar/aylar ölçeğinde kalıcı, yavaş bir kaymayı**
(sensör sürüklemesi, yavaş gevşeyen bir bağlantı gibi) yakalamak için ayrı
bir katman, günlük θ medyanları üzerinde çalışır, ham örnekler üzerinde
değil.

```
S+_i = max(0, S+_{i-1} + (x_i - mu0) - k)
S-_i = min(0, S-_{i-1} + (x_i - mu0) + k)
```

`mu0`/`sigma0` bir taban çizgisi (baseline) penceresinden tahmin edilir;
`k = 0.5·sigma0`, `h = 5·sigma0` (1-sigma'lık bir kaymayı düşük yanlış-alarm
oranıyla yakalamak için standart tablo değerleri).

### 1.1 Gerçek bir bulgu: baseline pencere boyutu deneyerek bulundu

İlk geçişte `baseline_days=7` kullanıldı — **gerçek testlerde başarısız
oldu**: 7 günlük bir örneklemden `pstdev` ile tahmin edilen `sigma0`, gerçek
sigma'dan %30-45 düşük çıkabiliyor (küçük örneklemde beklenen istatistiksel
sapma), bu da `h`'yi orantılı küçültüp CUSUM'un **saf gürültüde bile** yanlış
alarm üretmesine yol açıyordu (`tests/test_cusum.py`'de iki bağımsız
tohumla gerçekten gözlemlendi). `baseline_days=14` denendi, biri hâlâ
başarısız oldu. **`baseline_days=30`'a çıkarılıp gerçekten yeniden
test edildi** — negatif kontrol (saf gürültü, kayma yok) iki bağımsız
tohumda da artık doğru şekilde alarm üretmiyor, pozitif kontrol (bilinen
4-sigma'lık kalıcı kayma) hem pozitif hem negatif yönde beklenen pencerede
doğru tespit ediliyor. Bu sayı teorik bir seçim değil, ölçerek bulundu — bkz.
`panogoz/detector/cusum.py`'nin docstring'i.

**Bilinen sınırlama (dürüstçe):** `pstdev` küçük örneklemde hâlâ bir miktar
şansa bağlı bir tahmin edici; `baseline_days=30` ile bile teorik olarak
şanssız bir taban çizgisi penceresi hâlâ yanlış alarm üretebilir (yalnızca
çok daha nadir). Üretimde genişleyen bir pencereyle sürekli güncellenen bir
`sigma0` tahmini (bu görevde uygulanmadı) bu riski daha da azaltır — açık
madde.

### 1.2 Test kanıtı (gerçek, bizzat çalıştırıldı)

```
tests/test_cusum.py::test_daily_median_series_aggregates_by_day_and_skips_none PASSED
tests/test_cusum.py::test_no_false_alarm_on_stationary_noise PASSED
tests/test_cusum.py::test_no_false_alarm_second_stationary_seed PASSED
tests/test_cusum.py::test_detects_known_persistent_shift PASSED
tests/test_cusum.py::test_detects_negative_shift_too PASSED
tests/test_cusum.py::test_raises_on_insufficient_data PASSED
```

- **Negatif kontrol** (2 bağımsız tohum, 90 günlük saf N(0,1) gürültü,
  kayma yok): `changepoint_day_index is None` — yanlış alarm yok.
- **Pozitif kontrol** (pozitif + negatif yönde, 4-sigma'lık kalıcı kayma
  45. günden itibaren): değişim noktası 45-65. gün aralığında tespit
  edildi — gecikme var (CUSUM'un doğası gereği, anlık değil kümülatif bir
  test) ama bilinen kayma gününe makul yakınlıkta.

## 2. `expect_flags` — üç bayrak (`panogoz/detector/flags.py`)

| Bayrak | Anlamı | Eşik | θ'nın `None` durumundan farkı |
| --- | --- | --- | --- |
| **STALE** | Cihazdan beklenen periyotta (`dev.period_s`) yeni örnek gelmiyor | son örnekten bu yana geçen süre > `3 × period_s` | — (bu bayrak veri akışı hakkında, θ hesabıyla ilgisiz) |
| **DE_ENERGISED** | Bağlantı gerçekten enerjisiz (kesici açık/besleme yok) | akım < anma akımının **%2**'si | **θ'nın `MIN_LOAD_FRACTION=0.40` eşiğinden kasıtlı olarak çok daha sıkı** — %2-%40 arası akım "veri var ama normalize güvenilir değil" demek, enerjisiz değil |
| **SENSOR_DRIFT** | Cihaz veri gönderiyor ama davranışı istatistiksel olarak sapıyor | CUSUM değişim noktası tespit edildi (§1) | — |

**Kritik ayrım (bilerek test edildi, `tests/test_expect_flags.py::
test_de_energised_distinct_from_theta_uninformative_gate`):** akım anma
akımının %30'unda olduğunda θ.py `None` döner ("uninformative" — düşük yükte
normalize etmek güvenilir değil) ama bağlantı **kesinlikle enerjili**;
`is_de_energised()` bu durumda `False` döner çünkü %30, DE_ENERGISED'in
%2'lik eşiğinin çok üzerinde. İki durum kodda da, kavramda da birbirine
karışmıyor.

### 2.1 Test kanıtı (gerçek, bizzat çalıştırıldı)

```
tests/test_expect_flags.py::test_stale_true_when_gap_exceeds_factor PASSED
tests/test_expect_flags.py::test_stale_false_within_period PASSED
tests/test_expect_flags.py::test_stale_boundary_is_exclusive_not_stale PASSED
tests/test_expect_flags.py::test_de_energised_true_near_zero_current PASSED
tests/test_expect_flags.py::test_de_energised_false_for_normal_load PASSED
tests/test_expect_flags.py::test_de_energised_distinct_from_theta_uninformative_gate PASSED
tests/test_expect_flags.py::test_flags_for_connection_all_clear PASSED
tests/test_expect_flags.py::test_flags_for_connection_sensor_drift_only PASSED
tests/test_expect_flags.py::test_flags_for_connection_stale_and_de_energised_together PASSED
```

## 3. API entegrasyonu (gerçek, çalışan)

`GET /api/connections/<index>/flags` (opsiyonel `?now_t_s=` — statik/tarihsel
demo verisinde gerçek bir "şimdi" olmadığı için test edilebilirlik amaçlı;
canlı bir sistemde bu her zaman gerçek duvar-saati olurdu). Gerçek HTTP
isteğiyle doğrulandı:

```
GET /api/connections/1/flags
  -> {"stale": false, "de_energised": false, "sensor_drift": false,
      "sensor_drift_note": "yetersiz gunluk veri (CUSUM icin en az 31 gun
      gerekir, bu seri ~1.6 gun)"}
GET /api/connections/1/flags?now_t_s=999999999
  -> {"stale": true, ...}
```

`sensor_drift_note` **dürüst bir sınır**: organizatörün gerçek CT verisi
yalnızca ~1,5-1,6 günlük (152 örnek × 15dk) — CUSUM'un gerektirdiği 31
günlük baseline'a hiç ulaşmıyor, bu yüzden mevcut demo filosunda
`sensor_drift` her zaman `False` + açık bir not döner, sessizce yanlış bir
"sürüklenme yok" iddiası olmaz.

## 4. Kapsam dışı (dürüstçe işaretli)

- **K3 3.2 (Kanıt ekranı UI'ı)** — bu görev yalnızca arka uç mantığını
  kurdu ve API'den erişilebilir yaptı; θ zaman serisi + CUSUM + değişim
  noktası işaretinin frontend'de görselleştirilmesi ayrı bir K3 görevi.
- `panogoz/rules/engine.py`'nin CUSUM/flags'i dikkate alan bir birleşik
  alarm kararı üretmesi (şu an ayrı, bağımsız katmanlar) — ileride
  entegre edilebilir.
- Genişleyen pencereli/sürekli güncellenen `sigma0` tahmini (§1.1'deki
  açık madde).

CLAUDE.md K4 4.3 satırı `[x]` işaretlendi (2026-09-16).
