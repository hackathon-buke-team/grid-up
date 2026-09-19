# 09 · Veri Analizi ve Doğruluk Matrisi (K4 4.4)

> Bu belge, "sistemin doğruluğu sayıyla savunuluyor mu?" sorusuna cevaptır: 22
> senaryo × 10 rastgele tohum = **220 koşu**, gerçek komutla üretilmiş sonuçlar.
> Yeniden üretmek için: `python -m tools.run_accuracy_matrix --seeds 10 --workers 8`
> (~25 sn). Ham sonuçlar: `docs/data/dogruluk-matrisi.json`.

## 0. Önce dürüstlük notu (jüri sorusundan önce biz söyleyelim)

Bu bir **saha doğrulaması değildir**. Organizatör yalnız tek gerçek seri verdi
(L1 fazı CT akımı, ~1,6 gün). Sıcaklık/nem, PD ve ark sekmeleri boştu. Geri kalan
tüm kanalları biz açık fizik modellerinden ürettik (`panogoz/sim/scenarios.py`) ve
dedektörleri **o modellerin kendisine** karşı sınadık. Bu yüzden şunlar kanıt DEĞİL:
"%100 tespit" (model içi öz-tutarlılık), "0 yanlış alarm" (modelin sağlıklı
davranışı için). Şunlar **anlamlı**: (a) sabit eşiklerle yan yana kıyas, (b) kör
bölgenin ve kırılma noktalarının ölçülmesi, (c) model parametrelerine (gürültü,
ısıl zaman sabiti) dayanıklılık, (d) test sırasında bulunan gerçek hatalar (§4).

| Kanal | Kaynak | Not |
| --- | --- | --- |
| Akım (yük biçimi) | **Gerçek** (organizatör CT serisi, döşenmiş) | Genlik ölçeği modelimiz: RMS = `load_fraction × 250 A`. Ham seri RMS'i 341 A; anma akımı 250 A olan bir bağlantıyı sağlıklıyken "aşırı yüklü" gösterirdi. Gündüz/gece biçimi ve ani sıçramalar (90 → 540 A) gerçek. |
| Eklem sıcaklığı | Model | 1. derece ısıl gecikme, τ=1800 s, `T = T_iç + k·I²`, k=0,0006 K/A² (250 A'da ≈37,5 K). Sensör: 0,25 K çözünürlük (MAX31855), 0,25 K gürültü, sensörler arası σ=0,5 K statik ofset. |
| Nötr akım/sıcaklık | Model | Faz fazörlerinin toplamı + 3. harmonik (nötrde aritmetik toplanır). Nötr bara anma akımı = faz anmasının %50'si, k_N=0,0012. |
| Ortam / duvar / nem | Model | Dış sıcaklık: gün-içi sinüs + AR(1) hava; kapalı kabinde iç hava = dış + 8 K; duvar iç hava ile 3 sa gecikmeli dış sıcaklık arası; RH gece yüksek. |
| PD | Model | Taban gürültü + nemle büyüyen yüzey izlenmesi + anahtarlama patlamaları. |
| Ark | Model | ABB TVOC-2 trip kaydı + tanılama (sensör sağlıklı mı) biti. |

**Gerçek tehlike tanımı (ground truth):** eklem sıcaklık artışı ≥ 70 K
(IEC 61439-1 Tablo 6, harici yalıtımlı iletken terminalleri) veya gerçek yoğuşma
(duvar < çiy noktası). "Tehlikeye kalan süre" = tehlike anı − ilk ALARM.

## 1. Senaryo kütüphanesi (22)

**Arıza — tespit edilmeli (11):** gevşek cıvata ani (L2 ×2,2), kademeli (L3 28 günde ×4),
sıcak yazda (ortam +16 K), düşük yükte gizli (RMS %45); sürekli aşırı yük (+%35, 4 gün);
yoğuşma (RH %40→%92, 8 gün); nötr harmonik yüklenmesi (3. harmonik %12→%38); nötr
bağlantı gevşemesi (×3); PD + nem (yüzey izlenmesi); ark TRIP; ark koruma bütünlüğü kaybı.

**Yalnız uyarı (1):** PD tek başına (kuru hava) — ekip **sevk edilmemeli**.

**Negatif kontrol — alarm ÜRETMEMELİ (10):** sağlıklı referans, sıcak yaz (tüm fazlar
ısınır), ağır ama dengeli yük (%75), ölçülü yük basamağı, faz yük dengesizliği (%10/−%8),
tek örneklik sensör sıçramaları, bakım kesintisi (enerjisiz), haberleşme kaybı,
nemli ama marj yeterli, PD gürültü patlamaları.

> CLAUDE.md §0'daki "17 senaryo / 7 arıza modu" ifadesi eski, silinmiş koda aitti;
> bu depoda **gerçek olan bu 22 senaryodur.**

## 2. Tespit mimarisi (bastırma → onay → füzyon)

| İz (kind) | Aile | Puan | Eşik UYARI / ALARM / KRİTİK | Gerekçe |
| --- | --- | --- | --- | --- |
| `loose_bolt` | Isıl | \|θ\| (K), kardeş medyanına göre, süzülmüş I²'ye normalize | 15 / 30 / 60 | θ = "anma akımında ek sıcaklık artışı". Sağlıklı artış ≈37,5 K, ALARM'da (+30 K) anma akımında ≈67,5 K → **standart sınırı (70 K) anma yükünde aşacak** demek. Yük seviyesinden bağımsız. |
| `loose_bolt_trend` | Isıl | Günlük θ medyanı üzerinde nedensel CUSUM / h | 1,0 (yalnız UYARI) | Yavaş kalıcı kayma; σ tabanı 1 K. |
| `overload` | Yük | 1 sa RMS (en yüklü faz) / anma | 1,10 / 1,25 / 1,40 | Isınma I²'nin zaman ortalamasıyla belirlenir, anlık tepe ile değil. |
| `neutral_overload` | Yük | 1 sa RMS(I_N) / nötr anma | 0,85 / 1,00 / 1,20 | 3. harmonik nötrde aritmetik toplanır. |
| `neutral_joint` | Isıl | K_N oranı (rezidü tabanlı, süzülmüş I² ve ortam) | 1,5 / 2,0 / 3,0 | CLAUDE.md §2 `K_N=ΔT/I²`, ısıl gecikme telafili. |
| `condensation` | Ortam | max(0, 6 K − (T_duvar − T_çiy)) | 3 / 4,5 / 6 (marj ≤3 / 1,5 / 0 K) | Magnus çiy noktası. |
| `humidity_high` | Ortam | 1,5 sa medyan RH | 65 (yalnız UYARI) | Bağlam; PD için destekleyici. |
| `pd_tracking` | PD | 1,5 sa medyan PD indeksi | 15 / 30 / 60 | **Tavsiye**: ikinci aile olmadan UYARI'da tutulur. |
| `arc_trip` | Ark | TVOC-2 trip biti | tek örnek → KRİTİK | Olgudur; debounce yok, onaya kadar açık kalır (latching). |
| `arc_integrity` | Ark | TVOC-2 sensör hatası | ALARM | Koruma devre dışı. |
| `comms_lost` | Sistem | art arda geçersiz örnek | 3 / 96 örnek | Süreç alarmı sayılmaz. |

**Sıra sabit (CLAUDE.md §2):** (1) *bastırma* — geçersiz/enerjisiz/düşük-yük/ısınmamış
örnek gerekçesiyle (`STALE`, `DE_ENERGISED`, `LOW_LOAD`, `WARMUP`) puansız bırakılır,
gerekçe saklanır; (2) *onay* — %40 ölü bant histerezisi + 3/5 debounce; (3) *füzyon* —
PD, son 24 saatte ısıl veya ortam ailesinden en az UYARI gelmedikçe UYARI'da tutulur
("iki kanal ailesi şartı"). Kod: `panogoz/rules/{engine,pipeline}.py`.

## 3. Sonuçlar (10 tohum × 22 senaryo)

### 3.1 Senaryo × tespit matrisi

| Senaryo | Beklenen | Tespit (95% GA) | ALARM gecikmesi med/p90 (gün) | UYARI gecikmesi med (gün) | Tehlikeye kalan (ALARM) med/min (gün) | ALARM tehlikeden önce | Yanlış alarm (koşu) | Ek uyarı (koşu) |
|---|---|---|---|---|---|---|---|---|
| Gevşek cıvata (ani) | loose_bolt | 100% (72%–100%) | 0.02 / 0.03 | 0.02 | 0.33 / 0.32 | 100% | 0/10 | 0/10 |
| Gevşek cıvata (kademeli) | loose_bolt | 100% (72%–100%) | 7.67 / 8.05 | 3.02 | 2.60 / 0.95 | 100% | 0/10 | 0/10 |
| Gevşek cıvata (sıcak yaz) | loose_bolt | 100% (72%–100%) | 0.02 / 0.03 | 0.02 | 0.33 / 0.32 | 100% | 0/10 | 0/10 |
| Gevşek cıvata (düşük yükte gizli) | loose_bolt | 100% (72%–100%) | 0.02 / 0.03 | 0.02 | — / — | — | 0/10 | 0/10 |
| Sürekli aşırı yük | overload | 100% (72%–100%) | 1.27 / 1.27 | 0.36 | — / — | — | 0/10 | 0/10 |
| Yoğuşma riski (nem sızıntısı) | condensation | 100% (72%–100%) | 5.13 / 5.22 | 4.11 | 1.01 / 0.91 | 100% | 0/10 | 0/10 |
| Nötr harmonik yüklenmesi | neutral_overload | 100% (72%–100%) | 1.18 / 1.18 | 0.62 | 1.65 / 1.58 | 100% | 0/10 | 0/10 |
| Nötr bağlantı gevşemesi | neutral_joint | 100% (72%–100%) | 0.02 / 0.02 | 0.02 | — / — | — | 0/10 | 0/10 |
| PD + nem (yüzey izlenmesi) | pd_tracking | 100% (72%–100%) | 8.17 / 9.10 | 2.97 | — / — | — | 0/10 | 0/10 |
| Ark koruma tetiklemesi | arc_trip | 100% (72%–100%) | 0.00 / 0.00 | 0.00 | 0.00 / 0.00 | 100% | 0/10 | 0/10 |
| Ark koruma bütünlüğü kaybı | arc_integrity | 100% (72%–100%) | 0.02 / 0.02 | 0.02 | — / — | — | 0/10 | 0/10 |
| PD tek başına (kuru hava) | yalnız uyarı | sevk edildi **0/10** | — | 2.97 | — | — | 0/10 | 0/10 |
| Sağlıklı referans | sessiz | — | — | — | — | — | 0/10 | 0/10 |
| Sıcak yaz (tüm fazlar ısınır) | sessiz | — | — | — | — | — | 0/10 | 0/10 |
| Ağır ama dengeli yük | sessiz | — | — | — | — | — | 0/10 | 0/10 |
| Ölçülü yük basamağı | sessiz | — | — | — | — | — | 0/10 | 0/10 |
| Faz yük dengesizliği | sessiz | — | — | — | — | — | 0/10 | **3/10** |
| Tek örneklik sensör sıçramaları | sessiz | — | — | — | — | — | 0/10 | 0/10 |
| Bakım kesintisi (enerjisiz) | sessiz | — | — | — | — | — | 0/10 | 0/10 |
| Haberleşme kaybı | sessiz | — | — | — | — | — | 0/10 | 0/10 |
| Nemli ama marj yeterli | sessiz | — | — | — | — | — | 0/10 | **4/10** |
| PD gürültü patlamaları | sessiz | — | — | — | — | — | 0/10 | 0/10 |

**Genel:** DETECT senaryolarında 110/110 tespit. **Yanlış alarm bütçesi:** negatif
kontrol + tavsiye koşularında 6599 pano-günü (**18,1 pano-yılı**) boyunca **0
ALARM-üstü yanlış alarm** → %95 üst sınır **0,17 / pano-yılı** ("üçün kuralı", 3/18,1).
"Ek uyarı" sütunu ALARM olmayan UYARI-seviyesi gürültüyü gösterir:
- **Faz dengesizliği (3/10 koşu):** %10 dengesizlikte θ'nın yapısal medyanı 8–9 K
  (6,9 K dengesizlik + sensör ofseti); zaman zaman 15 K'yı (UYARI) geçen 3–12
  örneklik kısa dilimler var (tohum 1, 2, 8), ALARM eşiğine (30 K) hiç yaklaşmıyor.
  Bu **marjinal yanlış uyarıdır**, gerçek bir bilgi değil — dengesizlik %10'u aşarsa
  UYARI beklenmeli.
- **Nemli ama marj yeterli (4/10 koşu):** RH gece gerçekten %65'i aştı
  (`humidity_high`); bağlam bilgisi olarak doğru, sevk gerektirmiyor.

**Nasıl okunur:**
- *Ani* arızalarda "tehlikeye kalan" ≈ 0,3 gün: ×2,2 direnç yükün tepe saatinde
  birkaç saatte tehlikeye varır. Hiçbir dedektör bunu haftalar önce bilemez; ALARM
  yarım saat içinde gelir.
- *Kademeli* bozulmada UYARI 3 günde, ALARM 7,7 günde gelir, tehlikeye **≥0,95
  gün (medyan 2,6 gün)** kalır.
- Nötr eklem, PD ve ark bütünlüğünde tehlike anı tanımlı değil (ölçülen sıcaklık
  artışı 70 K'ya ulaşmıyor); yalnız gecikme raporlanır.

### 3.2 Sabit eşik kıyası

| Senaryo | Bu sistem: tespit / ALARM gecikmesi (gün) | Sabit 75 °C: tespit / yanlış alarm / gecikme (gün) | Sabit +45 K: tespit / yanlış alarm / gecikme (gün) |
|---|---|---|---|
| Gevşek cıvata (ani) | 10/10 / 0.02 | 10/10 / 0/10 / 0.16 | 10/10 / 0/10 / 0.16 |
| Gevşek cıvata (kademeli) | 10/10 / 7.67 | 10/10 / 0/10 / **5.84** | 10/10 / 0/10 / **5.84** |
| Gevşek cıvata (sıcak yaz) | 10/10 / 0.02 | **0/10 / 10/10 yanlış** / — | 10/10 / 0/10 / 0.16 |
| Gevşek cıvata (düşük yükte gizli) | 10/10 / 0.02 | **0/10** / 0/10 / — | **0/10** / 0/10 / — |
| Sürekli aşırı yük | 10/10 / 1.27 | 10/10 / 0/10 / 0.35 | 10/10 / 0/10 / 0.17 |
| Sıcak yaz (tüm fazlar ısınır) | — / 0/10 yanlış | 0/10 / **10/10 yanlış** / — | 0/10 / 0/10 / — |

Ne kazandırıyor, ne kazandırmıyor (dürüstçe):
- **Sabit 75 °C yazın kör ve yanlış alarmlı:** sıcak yaz kontrolünde 10/10 yanlış alarm, sıcak yazda gerçek arızayı ise hiç yakalayamıyor (alarm arızadan önce zaten çalıyor). θ ikisinde de doğru.
- **Düşük yükte gizli arıza:** hem 75 °C hem +45 K kuralı 0/10; θ yüke göre normalize ettiği için 10/10. Bu, θ'nın asıl üstünlüğü: bugün görünmeyen arıza, yük artınca yanacak.
- **Ortama göre +45 K kuralı güçlü bir rakip:** ani ve kademeli arızada bizden erken/eşit (kademelide **5,84 gün, bizim ALARM'ımız 7,67 gün**). Bizim kademeli arızadaki avantajımız ALARM değil **UYARI (3,0 gün)** ve düşük yük görünürlüğü.
- Aşırı yükte sıcaklık kuralları bizden erken (0,17–0,35 gün); bizim yük dedektörümüz (1,27 gün) ALARM eşiği (1,25× anma, 1 sa RMS) ve debounce nedeniyle daha ihtiyatlı. UYARI 0,36 günde.

### 3.3 Duyarlılık: kör bölge (L2 gevşek cıvata, direnç çarpanı)

| k çarpanı | UYARI oranı | ALARM oranı | ALARM gecikmesi med (gün) |
|---|---|---|---|
| 1,2 | 100% | **0%** | — |
| 1,4 | 100% | **0%** | — |
| 1,7 | 100% | 70% | 0,40 |
| 2,0 | 100% | 100% | 0,03 |
| 3,0 | 100% | 100% | 0,02 |
| 4,0 | 100% | 100% | 0,02 |

θ ALARM eşiği (30 K) ≈ ×1,8 direnç artışına denk gelir; bunun altı **ALARM kör bölgesi**dir.
UYARI'yı CUSUM (günlük θ medyanı, 1 K anlamlılık tabanı) verir: k=1,1 → 2–4 gün, k=1,2 →
1–2 gün, k=1,4 → 0,03–0,7 gün, k=1,7 → aynı gün (10 tohumun 10'unda, ayrı ölçüldü).

### 3.4 Haber verme süresi: kademeli gevşeme hızı (k: 1 → 4)

| Rampa (gün) | UYARI tehlikeye kalan med (gün) | ALARM tehlikeye kalan med (gün) |
|---|---|---|
| 7 | 1,65 | 0,67 |
| 14 | 2,92 | 1,03 |
| 28 | 7,56 | 2,60 |
| 56 | 14,98 | 3,07 |

Haber verme süresi bozulma hızına orantılı: yavaş (8 haftalık) gevşemede **UYARI
tehlikeden ~15 gün önce**, ALARM ~3 gün önce gelir. "Haftalar önce" iddiası yalnızca
bozulma haftalar sürüyorsa geçerlidir; bunu biz seçmiyoruz, fizik belirliyor.

### 3.5 Model parametrelerine dayanıklılık

**Sensör gürültüsü + ofset çarpanı** (×1: σ_gürültü=0,25 K, σ_ofset=0,5 K):

| Çarpan | Arıza (k×3) ALARM oranı | Arıza yanlış alarm koşusu | Sağlıklı yanlış alarm koşusu | Sağlıklı ek uyarı koşusu |
|---|---|---|---|---|
| ×1 | 100% | 0 | 0 | 0 |
| ×2 | 100% | 0 | 0 | 1 |
| ×4 | 100% | **1** | **1** | 10 |

×2'ye kadar sağlam; **×4'te (1 K gürültü, 2 K ofset) kırılma başlıyor** — sağlıklı
panoda her koşu UYARI veriyor, bir koşuda ALARM çıkıyor. Sahada sensör ofset
kalibrasyonu (sıfır-yük izotermal referans) bu yüzden bir kurulum adımı olmalıdır.

**Gerçek ısıl zaman sabiti** (dedektör τ'yu taban çizgisinden tahmin eder; gerçek
τ = 600…7200 s):

| Gerçek τ (s) | Sağlıklı yanlış alarm | Faz dengesizliği yanlış alarm | Arıza tespiti (k×2,2) |
|---|---|---|---|
| 600 | 0/10 | 0/10 | 10/10 |
| 1200 | 0/10 | 0/10 | 10/10 |
| 1800 | 0/10 | 0/10 | 10/10 |
| 3600 | 0/10 | 0/10 | 10/10 |
| 7200 | 0/10 | 0/10 | 10/10 |

(τ tahmini gerçeğin %0,5'i içinde: tohum 1'de 1799 / 3594 / 7169 s.) Bu tablonun bu hâline
gelmesi §4'teki ikinci bulgunun sonucudur; öncesinde 7200 s'de sağlıklı koşuların
10/10'unda yanlış alarm vardı.

## 4. Test sırasında bulunan gerçek hatalar (ders olarak kalsın)

1. **θ ısıl gecikmeyle sahte şişiyordu.** Yük hızlı düşerken (gerçek CT serisi 540→90 A
   sıçrıyor) ΔT henüz sönmemişken anlık I²'ye bölmek θ'yı şişirir. %10 dengesiz **sağlam**
   bir bağlantı UYARI seviyesine (>15 K) çıkıyordu. Çözüm: I², iletkenin ısıl modeliyle
   aynı süzgeçten (τ) geçirilir (`compute_theta_series(..., lag_tau_s=)`); geriye uyumlu,
   varsayılan davranış değişmedi. Test: `test_theta_lag_compensation_cancels_transient_false_theta`.
2. **K_N ve τ tahmini ortamı anlık çıkarıyordu.** Doğru model `T − LP_τ(T_ortam) = k·LP_τ(I²)+b`;
   ortamı anlık çıkarınca gün-içi ±6 K salınımın gecikmesi sahte artık bırakıyordu
   (τ=7200 s'de ~3 K → sağlıklı koşuların 10/10'unda yanlış alarm, τ=1800 s'de 0,8 K
   olduğu için fark edilmemişti). Çözüm: ortam da aynı süzgeçten geçer. Önce (yanlış)
   τ'yu **varsaymanın** eğimi zayıflatıp +%23 sapma verdiği de ölçüldü; bu yüzden τ artık
   veriden tahmin ediliyor (`panogoz/detector/thermal_tau.py`, log-üçlü arama).
3. **CUSUM 0,1 K'lık zararsız kaymayı "değişim noktası" ilan ediyordu.** Sağlıklı θ
   günlük medyanının σ'sı 0,11 K olduğundan h=5σ=0,55 K idi; tüm sağlıklı senaryolarda
   ~gün 41'de sahte UYARI çıktı (ve bu sahte destek PD füzyonunu bozup `pd_only_dry`'ı
   sevke çevirdi). Çözüm: pratik anlamlılık tabanı (`min_sigma=1 K`, ölçüm zincirinin
   çözünürlüğü altındaki sapma eyleme dönüşmez). Mutasyon testi: taban 0,05'e
   çekilince 7 test kırılıyor.
4. **Kendi senaryo hatalarımız (dedektör değil).** İlk "nemli ama sıcak" kontrolü
   fiziksel olarak yoğuşma sınırındaydı (RH %74 gece, marj ~2 K) → dedektör haklıydı,
   senaryo yanlıştı; RH %54'e çekildi. "Ani" arıza ×3 iken tehlikeye 14 dakikada
   varıyordu (hiçbir dedektör uyaramaz) → ×2,2'ye indirildi (erken evre gevşeme);
   ×3/×4 duyarlılık taramasında zaten duruyor. Aşırı yük ×1,45 saatler içinde tehlikeye
   varıyordu → ×1,35'e indirildi.
5. **Baz çizgisi kıyası adil değildi.** İlk simülatörde kabin içi hava dış sıcaklığı yalnız
   %60 izliyordu; sıcak-yaz kontrolünde sabit 75 °C bile tetiklenmedi ve kıyas anlamsızdı.
   Kapalı kabinde iç hava dış sıcaklığı bire bir izler (+8 K yük/güneş ısınması) —
   model buna göre düzeltildi. Bu değişiklik dedektör sonuçlarını iyileştirmek için
   değil, rakibi adil kılmak için yapıldı (θ kardeş farkı olduğundan ortam seviyesinden
   bağımsızdır).

## 5. Bilinen sınırlar (jüri sorusuna hazır)

- **Sentetik + öz-tutarlı:** dedektör ve simülatör aynı ekipten; 1. derece ısıl model
  gerçekte çok-kütleli olabilir. Gerçek pano verisi gelince ilk iş §3.5'i gerçek
  seride tekrarlamak.
- **Taban çizgisi sağlıklı varsayımı:** CUSUM (30 gün), K_N (14 gün) ve τ tahmini
  kurulum sonrası ilk günlerin sağlıklı olduğunu varsayar; o pencerede arıza varsa
  "normal" öğrenilir.
- **ALARM kör bölgesi:** direnç artışı < ~×1,8 iken yalnız UYARI (CUSUM). Bilinçli:
  15 K altına sevk çıkarmak yanlış alarm bütçesini bozar.
- **Ani şiddetli arıza:** haber verme ≈ 0 (fizik: dakikalar içinde tehlike). Sistem
  yarım saat içinde ALARM verir; "önceden" iddia edilmez.
- **Sensör gürültüsü ×4'te** yanlış alarm başlıyor (§3.5); ofset kalibrasyonu şart.
- **Donanımda eksik:** yoğuşma dedektörü için iç hava T/RH sensörü ve duvar (soğuk nokta)
  NTC'si var sayıldı; **bugünkü KiCad tasarımında (docs/03) yok.** IR/PD düğümüne
  I²C T/RH sensörü + NTC girişi eklenmesi K1'e açık madde.
- **PD ve ark modelleri basit:** PD indeksi gerçek faz-çözünürlüklü histogramın yerine
  tek bir skaler; TVOC-2 tetikleme mantığı yalnız bit düzeyinde. HFCT analog ön ucunun
  gerçek davranışı (docs/03) bu skalere dönüşmüyor.

## 6. Kod haritası

| Dosya | Görev |
| --- | --- |
| `panogoz/sim/scenarios.py` | 22 senaryo + fizik tabanlı üretici, ground truth |
| `panogoz/detector/{overload,condensation,neutral,pd,arc}.py` | Dedektör puanları + bastırma gerekçesi |
| `panogoz/detector/thermal_tau.py` | Isıl τ tahmini (sistem tanılama) |
| `panogoz/detector/theta.py` | θ; `lag_tau_s` ile gecikme telafisi |
| `panogoz/rules/engine.py` | Ölü bant histerezisi, 3/5 debounce |
| `panogoz/rules/pipeline.py` | Bastırma → onay → füzyon hattı |
| `panogoz/eval/matrix.py` | Matris, Wilson GA, sabit eşik kıyası, taramalar |
| `tools/run_accuracy_matrix.py` | Komut satırı, Markdown + JSON çıktısı |
| `tests/test_{detectors_multi,scenarios_pipeline,accuracy_matrix}.py` | 61 test |

CLAUDE.md K4 4.4 satırı `[x]` işaretlendi (2026-09-19) — kapsam: 22 senaryo × 10 tohum
matris, haber verme süresi, yanlış alarm bütçesi, duyarlılık eğrileri; **kapsam dışı:**
gerçek saha verisi, faz-çözünürlüklü PD sınıflandırıcı.
