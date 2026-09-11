# 09 — VERİ ANALİZİ
## Yarışma ile verilen `İstenen Veriler.xlsx` dosyasının karakterizasyonu

**PANO GÖZ** — Pano/Hücre İçi Anomali Erken Uyarı Sistemi
Adm & Gdz Elektrik "Grid Up" Hackathonu

> Bu bölümdeki **her sayı dosyadan hesaplanmıştır**, hiçbiri alıntı değildir.
> Üretici kod: `analysis/supplied_data.py`
> Çalıştırma: `PYTHONIOENCODING=utf-8 python -m analysis.supplied_data`
> API: `GET /api/analysis/supplied-data` (aynı sonucun JSON hâli)

---

## 0. Önce tavrımız

Organizatörler bize bir **yer tutucu** verdi. Bu makul bir tercihtir: gerçek
telemetri DSO güvenlik duvarının arkasındadır ve bir hackathon için dışarı
çıkarılması kolay değildir. Biz bu dosyayı bir kusur olarak değil, bir **girdi**
olarak ele aldık ve üç şey yaptık:

1. **Karakterize ettik** — dosyanın istatistiksel olarak ne olduğunu, dokuz
   bağımsız testle ölçtük.
2. **Fizikten yeniden kurduk** — aynı uzunlukta, aynı adımda, gerçek bir Türk AG
   fiderinin davranışını taşıyan bir seri ürettik ve iki seriyi aynı cetvelle
   ölçtük.
3. **Kendi dedektörümüzü orijinal dosyanın üzerinde çalıştırdık** ve ne yaptığını
   dürüstçe raporluyoruz: **alarm üretmiyor**, ve nedenini söylüyor.

Üçüncü madde bizim için en önemlisidir. "Verileriniz sahte" demek kolaydır ve
hiçbir şey kazandırmaz. Asıl soru şudur: *bu yükte bir sistem ne görebilir?*
Cevabımız ölçülmüştür ve aşağıdadır.

### Bu dosyayla ölçülemeyecek olanlar

Küme sentetiktir ve şunları **içermez**; her biri doğrudan bu ürünün ölçülmesini
engeller:

| Eksik | Neden önemli |
|---|---|
| Sıcaklık ve nem serisi (`Sıcaklık_Nem` sayfası boş) | θ bir sıcaklık farkıdır. Sıcaklık yoksa θ hesaplanamaz; dedektörün doğruluğu bu dosyayla **sınanamaz** |
| Etiketli arıza geçmişi | Hangi bağlantı ne zaman gevşedi bilinmiyor. Yanlış alarm oranı ve haber verme süresi bu dosyadan **hesaplanamaz** |
| Kardeş yapısı (üç faz / komşu pabuç) | Tek bir akım serisi var; θ'nın dayandığı eşleşme yok |
| Anomali | Küme anmanın %3.9–%23.4 aralığında yaşıyor; olay yok |

Sonuç açıkça yazılmalıdır: **bu pakette saha verisiyle doğrulanmış hiçbir başarım
sayısı yoktur.** Rakamlar ya fizikten türetilmiş simülatör üzerinde ölçülmüş, ya da
analitik olarak hesaplanmıştır. Gerçek performans ancak etiketli geçmişi olan bir
pilot tesiste ölçülebilir.

---

## 1. Dosya yapısı

| Sayfa | Boyut | Satır | Sütun | Dolu satır | Sayısal veri |
|---|---|---:|---:|---:|---:|
| `Akım Sensörü` | A1:F158 | 158 | 6 | 157 | **152** |
| `ARC` | A1:A2 | 2 | 1 | 2 | 0 |
| `PD` | A1:A4 | 4 | 1 | 3 | 0 |
| `Sıcaklık_Nem` | A1:A1 | 1 | 1 | 0 | **0 (tamamen boş)** |

Dört sayfadan yalnızca biri sayı taşıyor.

* `ARC` sayfası tek cümle: *"ABB TVOC-2 markası verilerinden Modbus ile okunarak
  alınacaktır"* — bu bir veri değil, bir yönlendirmedir. Biz de öyle yaptık:
  TVOC-2 Modbus haritasını `panogoz/contracts/icd.py` ve `panogoz/sim/tvoc.py`
  içinde, üretici kılavuzundaki 4.4.2 semantiğine (delik adresleri, 213'ün
  yalnız-yazılır olması, 200-212 ve 222-225'in aktif hata yokken 0x0000 okuması)
  sadık kalarak kurduk.
* `PD` sayfası üç satır: `DS_HFCT30`, `ÇALIŞMA MANTIĞI`, bir bağlantı başlığı.
  Yine veri değil, yönlendirme.
* **`Sıcaklık_Nem` sayfası tamamen boştur.** Bu projenin üzerine kurulduğu iki
  büyüklüğün — sıcaklık ve nem — sayfası boştur. Yoğuşma alarmı, duvar sıcaklığı
  ve çiy noktası için verilen veri sıfırdır. Bu zinciri şartnameden (Tablo 1,
  dahili: azami 40 °C, 24 saat ortalaması azami 35 °C, asgari −5 °C, 40 °C'de
  %50 BN) ve Magnus-Tetens/Alduchov-Eskridge bağıntısından yeniden kurduk.

### `Akım Sensörü` sayfasının başlıkları (satır 1–6)

| Hücre | İçerik |
|---|---|
| B1 | `Sentetik Data` |
| B2 | `Sekonderi 125 mA Olan Akım Sensörü` |
| F2 | `125 mA karşılığı 5 A Başka bir akım TR sekonderi` |
| B4 | `Sekonderi 100mA Primeri Değişken olmakla beraber elimizdeki 600A` |
| B5 | `L1 Fazı için` |
| B6 / D6 / E6 | `Sekonder Cinsten Akım Değeri` / `Çarpan` / `Hesaplanan Primer Akım` |

Formüller: `D7 = 600000/100` → `6000`, `E7 = B7*D7/1000` → `318`.

> Not: sayfanın kendi B1 hücresi zaten **"Sentetik Data"** diyor. Aşağıdaki
> analiz bu beyanı çürütmüyor — onu **niceliksel hâle getiriyor** ve bunun
> tasarımımız için ne anlama geldiğini gösteriyor.

---

## 2. "İkinci zaman bloğu" bir veri kümesi değil, bir görüntüleme artefaktıdır

Dosyayı `openpyxl` ile açan herkes A sütununda iki blok görür: satır 7–102
`datetime.time` (00:00 … 23:45), satır 103–158 ise `datetime.datetime(1900, 1, 1, …)`.
Bu, ikinci bir ölçüm kümesi gibi durur. **Değildir.**

Ham XML'i (`xl/worksheets/sheet1.xml`) doğrudan okuduk:

| | Değer |
|---|---|
| İlk seri değeri (A7) | `0` |
| Son seri değeri (A158) | `1.5729166666666701` |
| Monoton artan mı | **Evet, istisnasız** |
| Gözlenen adım kümesi | `{900.0 s}` — tek bir değer |
| Adım | 900.000 s = **15.000 dk = 1/96 gün** |
| Satır sayısı | **152** |
| Kapsam | 1.572917 gün = **37.75 saat** |
| Tip değişim noktası | Satır 103, seri değeri **tam olarak 1.0** |

`openpyxl.utils.datetime.from_excel` seri değeri `< 1` ise `datetime.time`,
`>= 1` ise 1900 epoch'u üzerinde `datetime.datetime` döndürür. `h:mm` biçimli
bir sütunda bu, seri 1.0'ı geçtiği anda görünümün "sıfırlanması" demektir.
Ham `<v>` değerleri sınırdan geçerken kesintisizdir: `0.98958333` → `1` →
`1.01041667`, hepsi 1/96 adımıyla.

**Sonuç:** tek bir kesintisiz kayıt vardır: 152 örnek, 15 dakika aralıklı,
37.75 saatlik bir pencere.

---

## 3. Tanımlayıcı istatistikler

| İstatistik | mA (sütun B) | A (= mA × 6, sütun E) |
|---|---:|---:|
| n | 152 | 152 |
| min | 15.0000 | 90.0000 |
| maks | 90.0000 | 540.0000 |
| ortalama | 52.1316 | 312.7895 |
| medyan | 49.5000 | 297.0000 |
| std sapma (n−1) | 22.6504 | 135.9026 |
| std sapma (n) | 22.5758 | 135.4548 |
| CV | 0.4345 | 0.4345 |
| çarpıklık g1 | +0.0587 | +0.0587 |
| aşırı basıklık g2 | −1.2129 | −1.2129 |
| açıklık | 75.0000 | 450.0000 |
| IQR | 40.5000 | 243.0000 |
| p01 / p05 / p10 | 15.0 / 17.1 / 22.0 | 90.0 / 102.6 / 132.0 |
| p25 / p50 / p75 | 33.5 / 49.5 / 74.0 | 201.0 / 297.0 / 444.0 |
| p90 / p95 / p99 | 84.0 / 86.0 / 89.0 | 504.0 / 516.0 / 534.0 |

Referanslar: 76 noktalı ayrık düzgün dağılımın aşırı basıklığı **−1.2004**;
U(15, 90) dağılımının CV'si **0.4124**.

Bütün değerler **tam sayıdır**, hepsi 15–90 aralığındadır, destek dışına düşen
tek bir değer yoktur, 76 olası tam sayının 68'i kullanılmıştır ve hiçbir hücre
6 kereden fazla tekrarlanmamıştır.

---

## 4. Bağımlılık testleri

### 4.1 Otokorelasyon (%95 bandı = ±0.1590)

| Gecikme | Süre | r | Bant içinde mi? |
|---:|---|---:|---|
| 1 | 15 dk | **+0.0003** | Evet (= gürültü) |
| 2 | 30 dk | −0.1134 | Evet |
| 4 | 60 dk | **−0.2184** | Hayır |
| 7 | 105 dk | +0.1855 | Hayır |
| 48 | 12 sa | +0.0868 | Evet |
| 96 | 24 sa | +0.0224 | Evet |

**Gecikme-1 = +0.0003 tek başına belirleyicidir.** Bir mahalle tüketimini her
on beş dakikada bir, bağımsız ve rastgele bir miktarda değiştiremez. Gerçek bir
15 dakikalık AG fiderinde bu sayı +0.97'nin üzerindedir; bizim gerçekçi
serimizde **+0.9954** ölçüldü.

### 4.2 Fark/seviye ve seri bağımsızlığı

| Test | Ölçülen | Beyaz gürültü beklentisi |
|---|---:|---|
| var(fark)/var(seri) | **2.0023** | tam olarak 2.0000 |
| Durbin–Watson | 1.9891 | ort 2.0132, sd 0.1622 → z = −0.149 |
| von Neumann oranı | 1.9891 | ≈ 2 |

`var(fark)/var(seri) = 2.0023` beyaz gürültünün **tam** değeridir, dört anlamlı
basamağa kadar. Gerçekçi seride aynı istatistik **0.0076**'dır — 260 kat fark.

### 4.3 Rastgelelik testleri

| Test | İstatistik | Beklenen | z | p | Hüküm |
|---|---:|---:|---:|---:|---|
| Koşu testi (medyan 49.5 etrafında) | R = 74 | 77.00 (sd 6.14) | −0.488 | 0.625 | rastgele |
| Yukarı/aşağı koşu testi | R = 98 | 99.00 (sd 5.12) | −0.195 | 0.845 | rastgele |
| Dönüş noktası testi | T = 95/150 (0.6333) | 100.00 (0.6667) | −0.968 | 0.333 | rastgele |

Dönüş noktası oranı **0.6333**, beyaz gürültünün teorik 2/3 = 0.6667 değerinin
tam üstünde. Gerçekçi seride **0.1984**.

### 4.4 Ljung–Box — *bizim en zayıf sayımız, jüriden gizlemiyoruz*

| m | Q(m) | df | p | %95 kritik | Hüküm |
|---:|---:|---:|---:|---:|---|
| 5 | 12.786 | 5 | 0.0255 | 11.07 | %5'te reddedildi |
| 10 | 21.002 | 10 | 0.0211 | 18.31 | %5'te reddedildi |
| 20 | 36.616 | 20 | 0.0130 | 31.41 | %5'te reddedildi |

Ljung–Box, denediğimiz her gecikme sayısında bağımsızlığı **%5 düzeyinde hafifçe
reddediyor** — ama hiçbirinde %1 düzeyinde reddetmiyor. Bunu saklamak yerine
açıkça söylüyoruz ve iki şey ekliyoruz:

1. n = 152 iken 5–20 gecikmeyi eşzamanlı test etmek Ljung–Box'ın ki-kare
   yaklaşımını şişirir (önerilen m ≈ ln n ≈ 5).
2. **Daha önemlisi: işaret ters.** Toplamın baskın terimi gecikme 4'te
   r = **−0.2184**, yani *negatif* — anti-kalıcılık. Gerçek bir 15 dakikalık
   fiderde 1 saatlik gecikmede r ≈ +0.95 beklenir. Yani bağımsızlığı hafifçe
   reddeden tek test bile bunu **bir yük profilinin yanlış yönünde** yapıyor.

Gerçekçi seride aynı istatistik Q(20) = **1466** (152 örnek) ve **31 635**
(30 gün).

---

## 5. Dağılım testleri

### 5.1 Ki-kare düzgünlük testi, 76 olası tam sayı üzerinde (15…90)

| | Değer |
|---|---:|
| n | 152 |
| Hücre başına beklenen | 2.0000 |
| **χ²** | **76.0000** |
| df | 75 |
| p | **0.4460** |
| %95 kritik | 96.22 |
| Destek dışı değer | 0 |
| Kullanılan farklı değer | 68 / 76 |
| En yoğun hücre | 6 |

χ² = 76.00, df = 75 ile neredeyse **tam** örtüşür (E[χ²] = df). Düzgün dağılım
hipotezi reddedilemez.

### 5.2 Kolmogorov–Smirnov, U(14.5, 90.5) karşısında

| | Değer |
|---|---:|
| D | **0.0526** |
| D⁺ / D⁻ | 0.0526 / 0.0395 |
| %95 kritik (1.36/√n) | **0.1103** |
| p (asimptotik) | 0.7832 |

Düzgün dağılım reddedilemez. `RANDBETWEEN(15;90)` tam olarak U(14.5, 90.5)
sürekli dağılımının tam sayıya yuvarlanmış hâlidir.

---

## 6. Günün saati yapısı

### 6.1 Tek yönlü ANOVA (gruplama: günün saati)

| | Değer |
|---|---:|
| Grup sayısı | 24 |
| n | 152 |
| **F(23, 128)** | **1.3755** |
| p | **0.1353** |
| η² | 0.1982 |
| SS_between / SS_within | 15 352.37 / 62 117.00 |

**Saat etkisi yok.** Her gerçek fiderin bir saat etkisi vardır: gerçekçi
serimizde p < 10⁻¹⁵.

### 6.2 Gün-gün şekil korelasyonu (aynı saat, aynı dakika)

| | Değer |
|---|---:|
| Çift sayısı | 56 |
| **r** | **+0.0596** |
| t (df = 54) | +0.439 |
| Gerçek fider | > +0.85 |
| Bizim gerçekçi serimiz | **+0.9945** |

Gerçek bir fiderde salı günü pazartesiye benzer. Burada benzemiyor.

### 6.3 Periyodogram

| k | Periyot (örnek) | Periyot (saat) | Pay % |
|---:|---:|---:|---:|
| 23 | 6.609 | **1.652** | 10.88 |
| 44 | 3.455 | 0.864 | 5.60 |
| 19 | 8.000 | 2.000 | 5.31 |
| 50 | 3.040 | 0.760 | 4.84 |
| 60 | 2.533 | 0.633 | 4.30 |

* Fisher g = 0.1088, p = 0.0149 → düzlük %5'te hafifçe reddedildi.
* En büyük ordinat / ortalama ordinat = **8.16** (gerçek fiderde 20–60).
* 24 saatlik harmonik k = 1.58 — tam sayı bile değil.

**Dürüst not:** Fisher testi de Ljung–Box gibi %5 düzeyinde hafifçe reddediyor.
Ama en büyük tepe **1.65 saatlik** periyotta, yani hiçbir yük sürecinin
yaşamadığı bir yerde; ve bu, §4.1'deki gecikme-4 negatif korelasyonunun *aynı*
tek anomalisidir — iki testte iki kez görülüyor, iki ayrı kanıt değil. Ayrıca
37.75 saatlik bir kayıttan 24 saatlik döngü zaten çözülemez; günlük yapıyı ACF
gecikme-96 (+0.0224) ve gün-gün şekil korelasyonu (+0.0596) üzerinden okuyoruz.

---

## 7. HÜKÜM

> **`Akım Sensörü` sütunu, [15, 90] aralığında düzgün dağılımlı sözde-rastgele
> tam sayılardır; `=RANDBETWEEN(15;90)` formülünün bir kez hesaplanıp değer
> olarak yapıştırılmasıyla tamamen uyumludur. Bu bir ölçüm değil, bir yer
> tutucudur.**

### Belirleyici kanıtlar

| Kanıt | Ölçülen | Gerçek fider | Beyaz gürültü |
|---|---:|---|---|
| **ACF gecikme-1 (15 dk)** ★ | **+0.0003** | > +0.97 | 0 ± 0.1590 |
| **var(fark)/var(seri)** ★ | **2.0023** | < 0.05 | tam olarak 2.0000 |
| **gün-gün şekil korelasyonu** ★ | **+0.0596** | > +0.85 | 0 |
| **tam sayı oranı** ★ | **152 / 152** | 0 (ADC kesir üretir) | hepsi |
| aşırı basıklık | −1.2129 | −1.1 (o da basık) | −1.2004 (76 noktalı ayrık düzgün, tam) |
| saat ANOVA F(23,128) | 1.375 (p = 0.135) | p < 0.001 | p ~ U(0,1) |

★ = tek başına belirleyici.

**Bu bir şikâyet değildir.** Bizim için sonucu şudur: PANO GÖZ ilk günden
**geçmiş gerektirmeyecek** şekilde tasarlandı. θ, panonun içinde zaten var olan
üç kardeş fazı karşılaştırır; eğitim kümesi istemez — ve zaten eğitim kümesi
yoktu.

---

## 8. YAN YANA — *aynı cetvel, iki seri*

Gerçekçi seri kaynağı: `panogoz.sim.load.LoadModel(seed=20260910, base_a=1100.0)`
— PANO GÖZ simülatörünün üretim yük modeli, `tests/test_sim_acceptance.py`
tarafından kabul edilen hâli.

Karşılaştırma pencereleri:

| Sütun | İçerik |
|---|---|
| **VERİLEN** | n = 152, 15 dk adım, 1.57 gün — *dosyada olan bu kadar* |
| **GERÇEKÇİ-152** | aynı uzunluk, aynı adım, aynı saat hizalaması |
| **GERÇEKÇİ-30g** | 2880 örnek = 30 gün — kabul ölçütlerinin yazıldığı pencere |

Pencereye bağlı istatistikler (★) 30 günlük sütundan puanlanır; diğerleri
152 örnekli sütundan. Verilen dosyada tek pencere vardır — bu da bulgunun bir
parçasıdır.

### 8.1 Birincil ölçütler — `tests/test_sim_acceptance.CRITERIA` ile birebir aynı

| İstatistik | VERİLEN | GERÇEKÇİ 152 | GERÇEKÇİ 30g | KABUL ÖLÇÜTÜ | verilen | gerçekçi |
|---|---:|---:|---:|---|:--:|:--:|
| ACF gecikme-1 (15 dk) | 0.0003 | 0.9861 | 0.9954 | ≥ 0.97 | **KALIR** | GEÇER |
| ACF gecikme-4 (1 sa) | −0.2184 | 0.9157 | 0.9519 | ≥ 0.85 | **KALIR** | GEÇER |
| ACF gecikme-96 (24 sa) ★ | 0.0224 | 0.3857 | 0.8894 | ≥ 0.60 | **KALIR** | GEÇER |
| var(fark)/var(seri) | 2.0023 | 0.0079 | 0.0076 | ≤ 0.05 | **KALIR** | GEÇER |
| ort \|15 dk adım\| % | 49.4800 | 1.6786 | 1.8546 | 1.5 … 4 | **KALIR** | GEÇER |
| dönüş noktası oranı | 0.6333 | 0.2933 | 0.1984 | 0.15 … 0.30 | **KALIR** | GEÇER |
| değişim katsayısı CV ★ | 0.4345 | 0.2314 | 0.2589 | 0.20 … 0.30 | **KALIR** | GEÇER |
| yük faktörü ort/maks ★ | 0.5792 | 0.7667 | 0.6176 | 0.55 … 0.70 | *GEÇER* | GEÇER |
| min/maks ★ | 0.1667 | 0.4608 | 0.3309 | 0.25 … 0.45 | **KALIR** | GEÇER |
| | | | | **TOPLAM** | **1/9** | **9/9** |

### 8.2 Destekleyici ölçütler

| İstatistik | VERİLEN | GERÇEKÇİ 152 | GERÇEKÇİ 30g | KABUL ÖLÇÜTÜ | verilen | gerçekçi |
|---|---:|---:|---:|---|:--:|:--:|
| gün-gün şekil korelasyonu | 0.0596 | 0.9945 | 0.9193 | ≥ 0.85 | **KALIR** | GEÇER |
| saat ANOVA p | 0.1353 | ~0 | ~0 | ≤ 0.001 | **KALIR** | GEÇER |
| medyan etrafı koşu z | −0.4883 | −11.8816 | −50.9167 | ≤ −3 | **KALIR** | GEÇER |
| Ljung–Box Q(20) | 36.62 | 1466.38 | 31 634.75 | ≥ 500 | **KALIR** | GEÇER |
| | | | | **TOPLAM** | **0/4** | **4/4** |

### 8.3 Tanı amaçlı — *puanlanmaz*

| İstatistik | VERİLEN | GERÇEKÇİ 152 | GERÇEKÇİ 30g |
|---|---:|---:|---:|
| aşırı basıklık ★ | −1.2129 | −1.3600 | −1.0759 |
| çarpıklık ★ | 0.0587 | −0.3979 | −0.0067 |

**Aşırı basıklık ve çarpıklık PUANLANMAZ ve bunu açıkça söylüyoruz.** Gerçek bir
fider serisi de basık çıkar (30 günlük gerçekçi seride g2 = −1.08), çünkü günlük
profil iki tepeli ve alttan/üstten sınırlıdır. Yani basıklık tek başına "düzgün
gürültü" ile "gerçek yük" ayrımını yapmaz; bir ölçüt olarak sunmak yanıltıcı
olurdu. Basıklığın değeri *destekleyicidir*: ölçülen −1.2129, 76 noktalı ayrık
düzgün dağılımın tam teorik değeri −1.2004'e 0.0125 uzaklıktadır — 152 örnekte
basıklık tahmininin standart hatası √(24/n) = 0.397 olduğu düşünülürse tam örtü.
Bütün değerlerin tam sayı olması ve 76 hücrenin 68'inin kullanılıp hiçbir değerin
destek dışına düşmemesiyle birlikte okununca `RANDBETWEEN(15;90)` parmak izini
tamamlar.

### 8.4 Dürüstlük notu — verilen serinin geçtiği tek ölçüt

Verilen seri **yük faktörü ort/maks** ölçütünü geçiyor (0.5792, bant 0.55–0.70).
Bu bir tesadüftür ve gizlemiyoruz: [15, 90] düzgün dağılımının ort/maks oranı
52.5/90 = 0.583'tür ve bant tam oraya denk gelir. Yük faktörü bir **seviye**
istatistiğidir, **şekil** hakkında hiçbir şey söylemez — şeklin reddedildiği
diğer sekiz satırda görülüyor.

---

## 9. DEDEKTÖR SONUCU — *asıl mesele bu*

### 9.1 Eşik tabanlı bir yaklaşım bu veride çöker

Rakip bir ekibin yazacağı iki klasik kural:

| Kural | Eşik | Seri maksimumu | Kaç kez tetikler |
|---|---:|---:|---|
| 1-σ (ort + 1sd) | 448.69 A | 540.00 A | 36/152 = **%23.7** |
| 2-σ (ort + 2sd) | **584.59 A** | 540.00 A | **hiç** (44.6 A yukarıda) |
| 3-σ (ort + 3sd) | **720.50 A** | 540.00 A | **hiç** (180.5 A yukarıda) |

| dI/dt kuralı (15 dk adım) | Tetikleme |
|---|---:|
| \|dI\|/I > %10 | 129/151 = **%85.4** |
| \|dI\|/I > %20 | 112/151 = **%74.2** |
| \|dI\|/I > %50 | 65/151 = **%43.0** |

**Mutlak eşik hiç atmaz, eğim eşiği sürekli atar.** İkisi de kullanılamaz. Bu,
eşik tabanlı yaklaşımın sahada neden çöktüğünün tam resmidir — ve bizim θ
tabanlı yaklaşımı seçmemizin niceliksel gerekçesidir.

### 9.2 Bizim dedektörümüz ne yapar: kör olduğunu söyler

Panonun anma akımı 2312 A (TEDAS-MLZ/2003-06.B Tablo 3a); 1600 kVA / 400 V için
In = 2309.4 A.

| | Değer |
|---|---:|
| Verideki yük faktörü | **%3.89 … %23.36** (ortalama %13.53) |
| Termal kazanç (I/In)² | 0.00152 … 0.05455 (ortalama 0.01830) |

Her termal imza (I/In)² ile çarpılır. Sonuç:

| | Değer |
|---|---:|
| 5 K'lik bir kusur ortalama yükte ne kadar görünür | **0.0915 K** |
| ...en yüksek yükte | **0.2728 K** |
| Sensör çifti gürültüsü σ_m (TMP117 çifti) | 0.20 K |
| 3-σ için gereken θ, ortalama yükte (3σ/f²) | **32.78 K** |
| 3-σ için gereken θ, en yüksek yükte | **11.00 K** |
| Başa baş noktası f = √(3σ/θ) | 0.3464 → **801 A** |
| Bu eşiğin üzerindeki örnek sayısı | **0 / 152** |
| Tam duyarlılıkta (f ≥ 0.35) örnek sayısı | **0 / 152** |
| **SENSITIVITY_LOW oranı** | **%100** |

### 9.3 Fiziksel karşılığı

50 μΩ'a bozulmuş bir 400 A kablo pabucu (sağlıklı 2–5 μΩ, fazla direnç 45 μΩ,
R_th,lokal = 2.0–4.0 K/W). Dosya panonun L1 **giriş** akımıdır (`L1 Fazı için`,
2500/5 üzerinden ölçekleniyor), o yüzden tek bir çıkış pabucundaki akım orantılı
paydır: I_fider = I_pano × 400 / 3250 (3250 A = beş 250 A + beş 400 A çıkışın
toplamı — dedektörün 34 IR pabucu için kullandığı aynı varsayım).

| | I_pano | I_fider | P | Yerel artış |
|---|---:|---:|---:|---:|
| Fider anma yükünde | 3250 A | 400.0 A | 7.200 W | **14.40 … 28.80 K** |
| Dosyanın maksimumunda | 540 A | 66.5 A | 0.199 W | **0.40 … 0.80 K** |
| Dosyanın ortalamasında | 313 A | 38.5 A | 0.067 W | **0.13 … 0.27 K** |

İlk satır bir iş emri yazdırır. **Son iki satır sensör gürültüsünün altında
kalır: aynı kusur, bu yükte görünmez.** θ ile tutarlıdır: θ = 14.4–28.8 K
(I_ref = 400 A) ve gözlenen artış = θ × (I_fider/400)², yukarıdaki iki satır tam
olarak budur.

> Fazla direnç **her zaman aralık olarak** verilir, çünkü R_th ancak bir çarpan
> mertebesinde bilinir: dR = θ / (R_th · I_ref²).

**Peki sağlıklı bir pabuç bu yükte ne kadar ısınır?** Pano havası artışı proje
kendi termal modelinden (`panogoz.sim.thermal.ThermalModel(air_rise_at_rated_k=20.0)`
— iki katman çelişemesin diye) alınmıştır; üzerine sağlıklı 2–5 μΩ pabucun yerel
artışı eklenir.

| | f | Pano havası | Ortama göre toplam artış |
|---|---:|---:|---:|
| Fider anma yükünde | 1.0000 | 20.00 K | 20.64 … 23.20 K |
| Dosyanın maksimumunda | 0.2336 | 1.95 K | **1.97 … 2.04 K** |
| Dosyanın ortalamasında | 0.1353 | 0.81 K | **0.82 … 0.84 K** |

**Bu dosyada mutlak sıcaklık da hiçbir şey söylemez:** sağlıklı bir pabuç ortamın
0.8–2.0 K üzerindedir, 50 μΩ'a bozulmuş olanı 1.0–2.8 K. İkisi arasındaki fark
sensör gürültüsü mertebesindedir. "Panoya termometre koy, eşiğin üstünde alarm
ver" yaklaşımının bu yükte ölçebileceği hiçbir şey yoktur.

### 9.4 Ne söylüyoruz

> **Verilen dosya üzerinde çalıştırıldığında PANO GÖZ hiçbir termal alarm
> üretmez ve örneklerin %100'ünde `SENSITIVITY_LOW` (düşük duyarlılık) bayrağını
> kaldırır: dosyadaki en yüksek yük faktörü %23.4, oysa 5 K'lik bir kusurun
> 3-σ ile görülmesi için %34.6 (801 A) gerekir. Bu reddediş **doğru cevaptır** ve
> sistem sessiz kalmak yerine bunu ekranda söyler.**

Bu, bizim "körüm dediğimizde bunu söylerim" kuralının (Dürüstlük Kuralı 2)
sayısal ispatıdır. Sadece yüksek yüklü örnekler bilgi taşır; bu veride öyle bir
örnek yoktur.

---

## 10. Ölçekleme çelişkisi — *bir soru, bir suçlama değil*

Sayfanın kendi başlıkları iki farklı ölçek tarif ediyor.

**Okuma 1 — başlığın tarif ettiği kaskat:**

| Kademe | Oran |
|---|---:|
| Ana akım trafosu 2500/5 (TEDAS Madde 2.2.11, yalnız giriş) | 500 : 1 |
| Ara trafo 5 A → 125 mA | 40 : 1 |
| **Toplam** | **20 000 : 1 = 20.0 A/mA** |

**Okuma 2 — D sütunundaki formülün uyguladığı:**

`D7 = 600000/100 = 6000`, `E7 = B7*D7/1000` → **6.0 A/mA**

**Fark: 20.0 / 6.0 = 3.333 kat.**

**Üçüncü bir tutarsızlık — tam skala:**

| Hesap | Sonuç |
|---|---:|
| 125 mA × 6.0 A/mA | **750 A** — ama başlık 600 A diyor (fark +150 A) |
| 600 A ÷ 125 mA | **4.8 A/mA** — üçüncü bir ölçek daha |
| 125 mA × 20.0 A/mA | 2500 A (kaskat okumasıyla, ana CT primeriyle tutarlı) |

**Aynı veri, iki ölçek:**

| Ölçek | min | maks | ortalama | sd | ort % In |
|---|---:|---:|---:|---:|---:|
| D sütunu (6.0 A/mA) | 90.0 A | 540.0 A | 312.8 A | 135.9 A | **%13.5** |
| Kaskat (20.0 A/mA) | 300.0 A | 1800.0 A | **1042.6 A** | 453.0 A | **%45.1** |

> **Soru (netleştirme talebi):** B sütunundaki mA değeri hangi kademeye aittir?
> Hangisinin doğru olduğu "bu pano yüklü mü" sorusunun cevabını tamamen
> değiştirir. 20.0 A/mA ile aynı veri 300–1800 A, ortalama 1042.6 A yani In'in
> %45.1'i olur — büyüklük olarak gayet makul bir AG fider yükü. **Şekli ise yine
> beyaz gürültüdür; ölçek düzeltmesi şekli düzeltmez.**

Bu soruyu bir kusur olarak değil, entegrasyon aşamasında netleşmesi gereken bir
kalibrasyon parametresi olarak kaydediyoruz. Bizim tarafımızda karşılığı vardır:
her PANO GÖZ termal klipsi **kendi split-core akım trafosunu** taşır (çünkü
hiçbir çıkış fiderinde şebeke CT'si yoktur — 2500/5 yalnız girişi ölçer), ve
MPR-53CS'in 32769 numaralı `CT RATIO` yazmacı **oranı** tutar (2500/5 → 500),
primer amperi değil. Ölçek belirsizliği bu iki yerde kapanır.

---

## 11. Bu analizin tasarıma yansıması

| Bulgu | Tasarım kararı |
|---|---|
| Geçmiş veri yok, eğitim kümesi yok | **θ = [T_i − medyan(kardeş fazlar)] / (I/I_ref)²** — kurulum gününde üç kardeş faz geçerli bir referanstır. Geçmiş gerekmez. |
| Sıcaklık/nem sayfası boş | Yoğuşma zinciri şartname Tablo 1'den ve Magnus-Tetens (a = 17.62, b = 243.12) bağıntısından kuruldu; duvar sıcaklığı ortam üzerinde τ ≈ 90 dk birinci mertebe gecikmeyle kestiriliyor. |
| Eşik kuralları çöküyor (§9.1) | Mutlak sıcaklık eşiği yalnız yedek kanaldır; birincil kanal yük-bağımsız θ'dır. |
| Düşük yükte görünürlük yok (§9.2) | `SENSITIVITY_LOW` birinci sınıf bir durumdur, ayrı raporlanır, panel arızasıyla asla karıştırılmaz. |
| Ölçek belirsizliği (§10) | Her klipste kendi split-core CT'si; analizör CT oranı yazmaçtan okunup doğrulanır. |
| ARC/PD sayfaları yönlendirme | TVOC-2 ve HFCT kanalları üretici kılavuzlarının semantiğine sadık modellendi; PD, AG'de asla tek başına sevk kanalı değildir (Paschen minimumu 327 V). |

---

## 12. Yeniden üretim

```
cd C:/Users/darkb/Desktop/grid-up-v2
PYTHONIOENCODING=utf-8 python -m analysis.supplied_data          # rapor + öz test
PYTHONIOENCODING=utf-8 python -m analysis.supplied_data --json   # JSON
```

Öz test **33 kontrolün 33'ünü** geçer ve bu belgedeki her sayıyı doğrular.
`ACCEPTANCE` tablosunun `tests/test_sim_acceptance.CRITERIA` ile birebir aynı
kaldığı da kod içinde denetlenir — iki tablo birbirinden kayarsa test kırılır.
