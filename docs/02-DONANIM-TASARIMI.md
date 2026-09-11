# 02 · Donanım Tasarımı

Bir modülün fiziksel hâli: 9 cihaz, her birinin montaj yüzeyi, o yüzeyi **zaten şartnamenin
zorunlu kıldığı** madde, çevresel tasarım zarfı ve pil bütçesi.

Taşıyıcı kural: **hiçbir delik delinmez, hiçbir tip testli bileşen değiştirilmez, hiçbir
bara kesiti değişmez.** 1. gün kitinin her montaj noktası, TEDAŞ-MLZ/2003-06.B'nin panoda
zaten bulunmasını şart koştuğu bir yüzeydir.

---

## 1. Dokuz cihazlık kit

| # | Cihaz | Algılayıcı | Ölçtüğü | Montaj yüzeyi | Bu yüzeyi sağlayan madde |
|---|---|---|---|---|---|
| 1–3 | **TC-01…03** | TMP117 (±0.1 °C) + ayrılabilir split-core CT | Damar yüzey sıcaklığı + damar akımı | Çıkış 6'nın L1/L2/L3 kablo damarına geçmeli kelepçe, pabuçtan 50–100 mm aşağıda | 1 kV kablo kılıfı üzeri; bölme Madde 2.2.8.6 Not:2 ile tam açık, EK-II/14 "En az 400 mm" |
| 4–6 | **TC-04…06** | TMP117 + split-core CT | Aynı, çıkış 7 | Çıkış 7'nin L1/L2/L3 damarı | Aynı |
| 7 | **TN-IR** | MLX90640 32×24 termal dizi + SHT41 | 48 pabuç sırasının sıcaklık alanı + bölme havası/nemi | Bölme tabanına mıknatıs kaide, **yukarı** bakar | **Madde 2.2.1.vi** — pano içi boyasız galvaniz sac, yani ferromanyetik; mıknatıs tutar |
| 8 | **PD-01** | HFCT (ayrılabilir) + TEV plakası + MA40S4R 40 kHz + SHT41 | RF mikro-ark, TEV, ultrasonik, ortam | **M12 paslanmaz topraklama saplaması**; HFCT PE iletkenine kenetlenir | **Madde 2.2.6.2.iii** — iki adet M12 paslanmaz topraklama terminali zorunlu |
| 9 | **GW-01** | — (ağ geçidi) | RS-485 master, radyo toplayıcı, WAN | Ölçü/iç ihtiyaç kolonunda DIN ray; mevcut prizden beslenir; anten dışarı | **Madde 2.2.12** (1 fazlı 10 A priz, 6 A gG "İç İhtiyaç" devresi) + **Madde 2.2.8.1.iv** (haberleşme üniteleri için bölme ve mühürlü dış anten çıkışı) |

`contracts/assets.py` içinde `DEVICES_PER_PANEL == 9` import anında assert edilir. Dijital
ikizde nokta sayan jüri üyesi, BOM satırı sayan satın almacı ve sahada kutu sayan tekniker
aynı sayıyı bulur.

### 1.1 Neden 6 kelepçe ve neden 6. ile 7. çıkış

θ **kardeş** ister. Kardeş kümesinin en küçük geçerli hâli bir fiderin üç fazıdır: aynı
akımı taşırlar, aynı havayı solurlar, aynı yaştadırlar ve aynı yüzeyi gösterirler. Bir
fidere iki kelepçe koymak işe yaramaz — medyan alınamaz, tek kardeşle fark almak ise
gürültüyü √2 ile çarpar. Bu yüzden kelepçeler **iki üçlü** hâlinde gider.

Çıkış 6 ve 7 seçilir çünkü ikisi de 400 A (2 Boy) sınıfının başındaki, tipik olarak en çok
yüklenen yollardır; θ'nın görülebilirliği f² ile arttığı için (§4, [04-ANOMALI-TESPIT.md])
en yüklü fider en görünür fiderdir.

Kalan **34 pabuç** yalnız TN-IR dizisi tarafından görülür ve **kendi akımları yoktur** —
hiçbir çıkış yolunda dağıtım şirketinin akım trafosu yoktur, 2500/5 yalnız girişi ölçer.
Bu 34 bağlantı için yük faktörü, analizörün faz akımından orantısal pay varsayımıyla
kestirilir ve bu **ekranda etiketlenir**. Kestirimi ölçüm gibi göstermek yasaktır.

---

## 2. Montaj yerleşimi — EK-II/14 koordinatlarına göre

Koordinat çerçevesi: orijin panonun **ön-sol-alt** köşesi, x sağa (0…1600 mm), y yukarı
(0…1500 mm). Sayılar `contracts/assets.py` içindeki `x_mm` / `y_mm` alanlarıyla birebir
aynıdır; dijital ikiz de aynı sayıları çizer.

```
 y=1500  ┌────────────────────────────────────────────────────────────────┐
         │  ÇATI PENCERESİ · 4 giriş sapması GIRIS-L1/L2/L3/N   y≈1460    │
         │  x = 485 / 610 / 735 / 860        (tam 2312 A taşır)           │
 y=1440  ├────────────────────────────────────────────────────────────────┤
         │  BARA BÖLMESİ                                                  │
         │  Ana bara 2×(100×10) mm² kalaylı elektrolitik bakır            │
         │  Terminal adımı 185 mm  →  fazlar arası açık hava 85 mm        │
         │  36 adet bara–DSYA cıvatalı bağlantı   y ≈ 1100 … 1290         │
         │                                                                │
         │        ██  1. GÜN KİTİ BU BÖLMEYE GİRMEZ  ██                   │
         │        AG giriş kesicisi YOK (Madde 2.2.10.2.vi)               │
 y=1045  ├────────────────────────────────────────────────────────────────┤
         │  ÖLÇÜ / İÇ İHTİYAÇ KOLONU                                      │
         │  [ GW-01 ]  x=1450  y=980   DIN ray · 10 A priz · anten çıkışı │
 y= 700  ├────────────────────────────────────────────────────────────────┤
         │  ALT KABLO BÖLMESİ · EK-II/14 "En az 400 mm" · taban tam açık  │
         │                                                                │
         │  48 PABUÇ SIRASI                                     y = 500   │
         │   C01  C02  C03  C04  C05  C06  C07  C08  C09  C10  |Y1  Y2|   │
         │   x=88 188  288  388  488  588  688  788  888  988  1088 1188  │
         │   250A 250A 250A 250A 250A 400A 400A 400A 400A 400A  yedek     │
         │                          ↑↑↑  ↑↑↑                              │
         │  [TC-01 02 03] x=568,588,608 y=430   [TC-04 05 06] x=668,688,708│
         │                                                                │
         │                                       [ PD-01 ] x=1290 y=230   │
         │                                       M12 topraklama saplaması │
         │                                                                │
         │            [ TN-IR ] x=640 y=150  ▲▲▲ yukarı bakar             │
         │            32×24 piksel · 110°×75° görüş · mıknatıs kaide       │
 y=   0  └────────────────────────────────────────────────────────────────┘
         x=0                                                       x=1600
```

### 2.1 TN-IR görüş geometrisi

MLX90640'ın standart lensi 55° × 35°'dir. y = 150 mm'den y = 500 mm'deki pabuç sırasına
mesafe **350 mm**; bu mesafede yatay görüş alanı 2 × 350 × tan(27.5°) = **364 mm**. 1200 mm
genişliğindeki pabuç sırasının tamamı tek bakışa sığmaz.

Bu yüzden dizi **eğik yerleştirilir** (x = 640, yani 10 çıkışın ağırlık merkezine yakın) ve
şu üç şey birlikte kullanılır:

1. **Geniş açı lensi** (110° × 75° varyantı): 350 mm'de yatay alan 2 × 350 × tan(55°) =
   **1000 mm** — 10 aktif çıkışın (x = 88…988, 900 mm) tamamını kapsar.
2. **Piksel–pabuç eşlemesi devreye almada kilitlenir** ve üç sabit referans noktası
   (bölme köşesindeki üç vida başı) her karede yeniden bulunur.
3. Referanslar eşleşmezse **`AIM_SHIFTED`** bayrağı kurulur, o dizinin tüm ölçümleri
   ısıl kanıt olmaktan çıkar ve bir **cihaz iş emri** açılır — tork iş emri değil.

Açısal çözünürlük: 110°/32 ≈ 3.44°/piksel → 350 mm'de piksel ayak izi ≈ 21 mm. Bir 400 A
pabuç yaklaşık 40 × 25 mm'dir, yani **1–2 piksele** düşer. Bu, kardeş farkı için yeterlidir
(θ üç pabuç arasındaki farkı ister, mutlak sıcaklığı değil) ama mutlak sıcaklık için
kenar-piksel karışımı nedeniyle iyimserdir; bu yüzden IR dizisinin kardeş-fark gürültüsü
σ = 0.8 K alınır, kelepçenin 0.2 K'i değil.

### 2.2 Fazlar arası dışlama bölgesi — 85 mm

EK-I/8, DSYA tipi satırı: *"Ana bara terminalleri arası mesafe 185 mm olacaktır."* Bara
yüksekliği 100 mm olduğuna göre komşu faz baraları arasında kalan açık hava:

```
185 mm (terminal adımı) − 100 mm (bara genişliği) = 85 mm serbest aralık
```

**Kural:** bu 85 mm'lik hava kanalına hiçbir cihaz, kablo, mıknatıs kaide ya da bağ teli
giremez. 1. gün kitinde bu kural kendiliğinden sağlanır, çünkü bara bölmesine hiç
girilmiyor. Kural yine de yazılıdır, çünkü (a) gelecekteki bara-bölmesi seçeneğinin ön
şartıdır, (b) montaj ekibi kabloyu bölmeler arasında çekerken bilmek zorundadır.

Alt kablo bölmesinde ölçüt farklıdır: kelepçe **1 kV kablonun kendi kılıfının üstüne**
oturur (temel yalıtım), çıplak metale — pabuç gövdesine, cıvataya, bara ucuna — en yakın
noktası **≥ 25 mm** olacak şekilde konumlanır ve kelepçenin gövdesi UL94 V-0, CTI ≥ 600
malzemedir.

---

## 3. Manyetik ortam — yöntemi dürüstçe

Pano içi bir cihaz, 2312 A taşıyan bir barayla aynı hacimde yaşar. Alanı hesaplarken hangi
formülün geçerli olduğunu söylemek, sayının kendisinden önemlidir.

### 3.1 Sonsuz iletken (filaman) formülü ve nerede geçersiz olduğu

```
B = μ₀ I / (2π r)
```

Bu formül **iletken boyutlarına göre uzak** alanda geçerlidir. 100 mm × 10 mm'lik yassı bir
bara için "uzak", bar yüksekliğinin (100 mm) birkaç katı demektir. r = 50 mm için formül
9.25 mT verir, ama **o mesafede geçerli değildir** ve bunu yazmadan sayıyı kullanmak
yanlıştır.

### 3.2 Geniş yassı bara için yüzey alanı

Genişliği kalınlığından çok büyük bir bara, akımı iki yüzeye yayılmış bir tabaka gibi
davranır. Sonsuz akım tabakası için yüzeydeki alan:

```
B_yüzey ≈ μ₀ I / (2 w),      w = bara genişliği
        = (4π×10⁻⁷ × 2312) / (2 × 0.100)
        = 2.9055×10⁻³ / 0.200
        = 1.45×10⁻² T = 14.5 mT
```

**Bara yüzeyinde ~14.5 mT.** Bu, 1. gün kitinin hiçbir cihazının bulunmadığı yerdir.

### 3.3 Cihazların fiilen gördüğü alan

| Konum | Kaynak | Mesafe | Formül | Alan |
|---|---|---:|---|---:|
| Bara yüzeyi (kimse yok) | 2312 A yassı bara | 0 | μ₀I/(2w) | **14.5 mT** |
| TC kelepçesi, kendi damarı | 400 A tek damar | 15 mm (kablo yarıçapı) | μ₀I/(2πr) | **5.3 mT** |
| TN-IR, bara bölmesinden | 3 faz × 2312 A, 185 mm adım | ~950 mm | 3 fazlı, ~d/r ile sönümlü | **< 0.2 mT** |
| PD-01, PE saplaması | Denge akımı, tipik < 200 A | ~300 mm | μ₀I/(2πr) | **< 0.14 mT** |
| GW-01, ölçü kolonu | Bara | ~700 mm | 3 fazlı | **< 0.25 mT** |

Üç fazlı sistemde uzak alan tek bir iletkeninki gibi 1/r ile değil, faz adımı d ve mesafe r
için kabaca **(d/r)** çarpanıyla sönümlenir; dengeli yükte alanlar birbirini büyük ölçüde
götürür. Türkiye AG şebekesinde %20–40 dengesizlik rutindir, bu yüzden hesapta dengeli yük
varsayılmaz: yukarıdaki değerler en kötü faz için verilmiştir.

### 3.4 Sonuçları

| Bileşen | Etkilenir mi | Gerekçe |
|---|---|---|
| NdFeB mıknatıs kaide | **Hayır** | N42 için içsel koersivite ≈ 1000 kA/m (≈ 1.25 T eşdeğeri). 14.5 mT bunun binde onikisidir; kalıcı mıknatıslığı bozmaz. |
| Split-core CT çekirdeği | **Evet, tasarım kısıtı** | Nanokristal çekirdek 400 A'de doymayacak şekilde boyutlandırılır; ayrıca komşu fazın dış alanı kaçak akı olarak girer. Bu, ölçümde ±%1.5 hata sınırının ana kalemidir. |
| HFCT | **Evet, kritik** | 50 Hz besleme geri kaçışı **6 mV_pp / amper**'dir. Bu yüzden HFCT **asla faz iletkenine kenetlenmez**, yalnız PE'ye; ve 1–3 MHz yüksek geçiren filtre **zorunludur**. |
| TMP117, SHT41, MLX90640 | Hayır | Optik/kapasitif/direnç esaslı; manyetik duyarlılıkları yok. |
| Reed anahtar / Hall | Kullanılmıyor | Bilinçli: pano içinde manyetik anahtar kullanmak yanlış tetikleme davetiyesidir. Kaide teması kapasitif ve ısıl tutarlılıkla doğrulanır (`MOUNT_LOST`). |

### 3.5 Kısa devre kuvveti

Tablo 3b: 80 kA tepe, cos φ = 0.25. 185 mm adımlı iki komşu bara arasındaki birim boy kuvveti:

```
F/l = μ₀ i² / (2π d) = (4π×10⁻⁷ × (80 000)²) / (2π × 0.185)
    = 8042 / 1.1624 ≈ 6.9 kN/m
```

Bu, bara sisteminin tip testiyle taşıdığı kuvvettir. **Kitin hiçbir parçası bu kuvvet
yolunda değildir**; ancak alt bölmedeki kelepçeler, arıza anında kablo damarlarının
savrulmasına maruz kalır. Bu yüzden kelepçe gövdesi kabloyu **saran** (kavrayan değil, ön
gerilmeli) bir kelepçedir ve kopma yükü 250 N'dir; kopması hâlinde kablonun üzerinde
kalması için 0.5 mm² paslanmaz emniyet teli ile pabuç civatasına değil, **kablo kanalı
askısına** bağlanır.

---

## 4. Çevresel tasarım zarfı

Şartname (Tablo 1, dahili sütunu) ortam için −5 … +40 °C, 24 saatlik ortalama maks. 35 °C,
%50 bağıl nem (40 °C'de) der. **Cihazları bu zarfa göre tasarlamak yanlış olur.** Gerekçe:

1. Tablo 1 panonun **şartlandığı** ortamdır, dağıtım merkezi odasının **tuttuğu** ortam
   değildir. Dijital ikizimizin hava modeli, Ege'de yaz öğleden sonralarında 42–43 °C
   ortam üretir ve bunu kırpmayız — bu bir "hizmet zarfı dışı" bulgusudur, bir hata değil.
2. Pano **içi** hava, anma yükünde ortamın ~20 K üstündedir (kayıp modeli,
   `sim/thermal.py`). 40 °C ortam → ~60 °C bölme havası.
3. Kelepçe, havadan da sıcak olan bir **kablo damarının** üstündedir.
4. Alt bölme tabanı tamamen açıktır ve nemli bir kablo kanalına bakar; kışın yüzey
   sıcaklığı ortamın altına düşer.

Tasarım zarfı:

| Parametre | Değer | Gerekçe |
|---|---|---|
| Çalışma sıcaklığı | **−25 … +70 °C** | Yukarıdaki 1–4; ayrıca Tablo 1'in harici sütunundaki −25 °C |
| Depolama | −40 … +85 °C | Sevkiyat ve depo |
| Bağıl nem | %0–100, **yoğuşmalı** | Alt bölme kablo kanalına açık |
| Koruma sınıfı | **IP65** (cihaz gövdesi) | Pano IP2X'tir; cihaz kendi korumasını kendi sağlar |
| Koruyucu kaplama | IPC-CC-830B, Sınıf 3, akrilik (AR) ya da poliüretan (UR), 50 µm | Yoğuşma + kükürt/klor içerikli endüstriyel atmosfer |
| Titreşim | IEC 60068-2-6, 10–150 Hz, 1 g, 3 eksen × 2 h | Trafo manyetostriksiyonu (100 Hz) + sokak aydınlatma kontaktörü (AC-5a) darbeleri |
| Mekanik şok | IEC 60068-2-27, 15 g / 11 ms | Nakliye ve kapak çarpması |
| Kirlilik derecesi | 2 (Madde 1.4) | Kaplama bunu 3'e kadar tolere eder |
| Yükseklik | ≤ 2000 m | Madde 1.4 |

Bileşen sıcaklık aralıkları bu zarfı kapsar: TMP117 −55…+150 °C, SHT41 −40…+125 °C,
MLX90640 −40…+85 °C, Li-SOCl₂ −55…+85 °C, MCU (endüstriyel) −40…+85 °C.

**Ek not:** MLX90640'ın −40…+85 °C sınırı zarfın en dar kalemidir; +70 °C hedefinde 15 K
marj vardır ve dizi bölmenin **tabanındadır**, yani bölmenin en soğuk yerindedir.

---

## 5. Pil bütçesi — hesaplandı, tezgâhta ölçülmedi

> **VARSAYIM (etiketli):** aşağıdaki akımlar bileşen veri sayfalarından alınmıştır; hiçbiri
> tezgâhta ölçülmemiştir. Ölçüm, [11-ACIK-SORULAR.md] listesindeki doğrulama kalemlerinden
> biridir. Faydalı kapasite, nominal kapasitenin **%85**'i alınmıştır (düşük sıcaklık,
> pasivasyon, ömür sonu gerilimi); ayrıca %1/yıl kendi kendine deşarj vardır.

### 5.1 TC ısıl kelepçe — ER14250 (½ AA, 1200 mAh) + HLC

| Kalem | Akım × süre | Uyanma başına |
|---|---|---:|
| Radyo TX (868 MHz, 14 dBm, 32 B) | 30 mA × 8 ms | 0.240 mA·s |
| Radyo RX penceresi | 12 mA × 6 ms | 0.072 mA·s |
| MCU aktif | 4 mA × 25 ms | 0.100 mA·s |
| TMP117 dönüşümü | 135 µA × 20 ms | 0.003 mA·s |
| **Toplam** | | **0.415 mA·s** |

```
1/dk kadans:  1440 × 0.415 mA·s = 597 mA·s/gün = 0.166 mAh/gün
uyku akımı:   3 µA × 24 h                      = 0.072 mAh/gün
toplam                                          = 0.238 mAh/gün = 86.9 mAh/yıl
faydalı kapasite: 1200 × 0.85                   = 1020 mAh
ömür (kendi deşarjı hariç)                      = 11.7 yıl
%1/yıl kendi deşarjı ile                        ≈ 10.4 yıl
```

1/5 dk kadansta (hafif yüklü, düşük öncelikli panolar) tüketim 38.4 mAh/yıl'a iner ve ömür
raf ömrüyle sınırlı hâle gelir: **~16 yıl**.

### 5.2 TN-IR termal dizi — ER14505 (AA, 2600 mAh)

MLX90640 pahalı bir algılayıcıdır: bir kare için ~23 mA × 0.5 s = 11.5 mA·s, artı 48 pabuç
değerini taşıyan daha büyük bir radyo yükü (30 mA × 60 ms = 1.8 mA·s) ve MCU işlemesi
(0.7 mA·s) → **kare başına ≈ 14 mA·s**.

```
Kararlı hâl kadansı: 1 kare / 10 dk  →  144 kare/gün
144 × 14 mA·s = 2016 mA·s/gün = 0.560 mAh/gün
uyku + SHT41 + radyo bakımı                    = 0.096 mAh/gün
toplam                                          = 0.656 mAh/gün = 239 mAh/yıl
faydalı kapasite: 2600 × 0.85                   = 2210 mAh
ömür                                            = 9.2 yıl
```

**IR dizisi bilinçli olarak yavaş kanaldır.** Hızlı kanal kelepçelerdir. Bir kelepçe θ'da
yükseliş bildirirse dizi 30 dakika boyunca 1/dk'ya çıkar (olay güdümlü yoğunlaştırma).
Böyle bir 30 **günlük** yoğunlaştırma nöbeti 168 mAh, yani **8.5 aylık pil bütçesi** yer;
bu yüzden yazılım bunu yılda 2 nöbetle sınırlar ve sayacı telemetriye basar.

### 5.3 PD-01 RF/ortam düğümü — ER26500 (C, 8500 mAh)

AD8318 logaritmik dedektör 68 mA çeker; LNA ile birlikte kayıt sırasında ~88 mA. Bu yüzden
analog zincir **yalnız kayıt sırasında** enerjilenir. Sürekli açık olan tek şey, pasif bir
zarf dedektörü (Schottky + komparatör, ~15 µA) ve MCU uykusudur.

```
Nöbetçi (pasif zarf dedektörü + MCU uykusu): 19 µA  = 0.456 mAh/gün
Planlı kayıt: 1/gün × 60 s × 88 mA = 5280 mA·s      = 1.467 mAh/gün
Ortam (SHT41 1/dk) + radyo                          = 0.250 mAh/gün
toplam                                               = 2.173 mAh/gün = 793 mAh/yıl
faydalı kapasite: 8500 × 0.85                        = 7225 mAh
ömür (olaysız)                                       = 9.1 yıl
tipik olay hızıyla (0.3 tetikli kayıt/gün, 0.54 mAh) ≈ 8.4 yıl
```

60 s'lik kayıt, 50 Hz'de **3000 çevrim** demektir ve bu, `sim/prpd.py` içindeki
`DEFAULT_CYCLES = 3000` ile birebir aynıdır: PRPD histogramının çözünürlüğünü belirleyen
sayı ile pil bütçesini belirleyen sayı aynı sayıdır.

### 5.4 Özet ve bağlayıcı düğüm

| Cihaz | Hücre | Hesaplanan ömür | Not |
|---|---|---:|---|
| TC-01…06 | ER14250 + HLC | 10.4 y (1/dk) … 16 y (1/5 dk) | HLC, radyo darbesinde gerilim çökmesini önler |
| TN-IR | ER14505 | 9.2 y | Yoğunlaştırma nöbetleri yılda 2 ile sınırlı |
| PD-01 | ER26500 | 8.4 – 9.1 y | **Bağlayıcı düğüm** |
| GW-01 | — | — | Şebekeden (10 A priz); süperkapasitör tutması yalnız son nefes mesajı için |

Kit için ilan edilen tasarım ömrü **9–16 yıl**dır; alt uç PD-01, üst uç düşük kadanslı
kelepçelerdir. Bakım modeli bu yüzden **8. yılda tek bir hücre değişim ziyareti** planlar
(bkz. [05-SAHA-UYGULAMA.md] §7).

### 5.5 Enerji hasadı — iddia edilmiyor

Bara yakınında bir akım trafosuyla enerji hasadı fiziksel olarak mümkündür ve bu pazarda
sıkça pazarlanır. **Ölçmedik, dolayısıyla iddia etmiyoruz.** Nedenleri:

* Hasat edilen güç I² ile gider; panonun günün üçte birini geçirdiği %20–35 yük bandında
  bir CT hasatçısı tipik olarak sadece onlarca mikrowatt verir ve tam da bizim en çok ölçüm
  yapmak istediğimiz düşük yükte en zayıftır.
* Panonun **enerjisiz** olduğu durum ([04] §7'deki `DE_ENERGISED`), hasatla beslenen bir
  düğümün tamamen sustuğu durumdur; oysa o an "pano enerjisiz" diyebilmek bir üründür.
* Hasat devresi, ölçüm yaptığımız CT'nin manyetik yükünü değiştirir; akım ölçümünün
  doğruluğunu hasat için feda etmek yanlış takastır.

Hasat, **tezgâh ölçümüne bağlı belgelenmiş bir gelecek seçeneği** olarak durur: 1/dk
kadansta TC düğümü ortalama 27 µW harcar, dolayısıyla 100 µW mertebesinde kararlı bir hasat
düğümü şebekeden bağımsız kılar. Bu sayıyı ölçmeden ürüne yazmayız.

---

## 6. Radyo ve haberleşme

| Bağlantı | Teknoloji | Gerekçe |
|---|---|---|
| Cihaz → GW | 868 MHz sub-GHz, FSK, 14 dBm, kabin içi ~1.2 m | **Kavite argümanı**, aşağıda |
| GW → RS-485 | Modbus RTU, izole, 2 slave (TVOC-2 @19200 8E1, MPR-53CS) | Panoda **zaten var olan** iki cihaz |
| GW → sunucu | LTE Cat-1 (birincil) / Ethernet (varsa) | Anten Madde 2.2.8.1.iv mühürlü dış çıkışından |

**Neden 868 MHz ve neden 2.4 GHz değil — kavite argümanı.** Çalışması gereken bağlantı,
alt kablo bölmesinden (Madde 2.2.8.6 Not:2 ile tabanı tam açık) ölçü kolonuna, yani
1600×1500×450 mm'lik bir sac kutunun içinden geçer. Arada 2 mm galvaniz DSYA montaj plakası
vardır. Bu hacim 2.4 GHz'de **ağır biçimde aşırı modludur** (overmoded): dalga kutunun
içinde çarpar durur ve derin sıfırlar üretir; birkaç santimetrelik bir yer değişimi bağlantıyı
koparır. 868 MHz'de kutu yalnız zayıf biçimde aşırı modludur.

Daha önemlisi **açıklık**: kutunun güvenilir tek açıklığı, tabandaki ≥ 400 mm'lik boşluktur.
868 MHz'in dalga boyu **345 mm**'dir ve 400 mm'lik bir yarıktan kuplaj yapar; 2.4 GHz'in
**125 mm**'lik dalga boyu yapmaz. Tek radyo, tek yonga (STM32WLE5CC entegre alıcı-verici),
hiçbir yerde BLE yok.

**Anten uyarısı:** Madde 2.2.8.1.iv haberleşme üniteleri için bir bölme **ve mühürlü dış
anten çıkışı** şart koşar; ancak sahadaki panolarda bunun fiilen mevcut olup olmadığı
sipariş anındaki alıcı talebine bağlıdır. Bu, [11-ACIK-SORULAR.md] listesinin **1. sorusudur**
ve cevabı montaj süresini doğrudan değiştirir: gland varsa anten 4 dakikada takılır,
yoksa ya IP2X'i bozmadan bir geçiş yolu bulunmalı ya da LTE anteni kabin içinde kalır (bu
durumda alan kaybı tipik 12–20 dB'dir ve zayıf sahalarda bağlantıyı kaybettirir).

---

## 7. Mekanik ve malzeme

| Parça | Malzeme | Not |
|---|---|---|
| TC kelepçe gövdesi | PA66-GF30, UL94 V-0, CTI ≥ 600 | Kabloyu saran iki yarım kabuk, paslanmaz yay ile ön gerilmeli |
| TN-IR / PD-01 gövdesi | PC/ABS UL94 V-0 + alüminyum taban | Taban aynı zamanda ısıl kütle ve mıknatıs arayüzü |
| Mıknatıs kaide | 2 × Ø20 NdFeB N42, kauçuk kaplı, ~90 N çekme | Madde 2.2.1.vi boyasız galvaniz sac üzerine |
| HFCT ayrılabilir çekirdek | Nanokristal, 30 mm delik | PE iletkenine kenetlenir; klemp noktası M12 saplaması |
| Emniyet teli | 0.5 mm² paslanmaz | Kablo kanalı askısına; **pabuç civatasına değil** |
| GW-01 muhafaza | DIN ray, 6 modül, PC UL94 V-0 | Ölçü kolonunda |

**Mıknatıs kaide neden yeterli:** Madde 2.2.1.vi pano içini boyasız galvaniz sac bırakır,
yani yüzey ferromanyetiktir ve mıknatıs doğrudan tutar. 90 N çekme kuvveti, 180 g'lık bir
düğüm için 50 kat emniyet payıdır ve titreşim zarfında (1 g) kaymaz. Kaide teması
kaybolursa (`MOUNT_LOST`) sıcaklık okuması artık bağlantının değil **havanın** sıcaklığıdır;
sistem bunu tespit eder ve bir **cihaz** iş emri açar, bağlantıyı sıktırmaz.

---

## 8. Belgelendi, kodlanmadı

| Konu | Durum |
|---|---|
| Pil akımlarının tezgâhta ölçülmesi | **Yapılmadı**; tüm ömür hesapları veri sayfası akımlarından |
| MLX90640 geniş açı lens seçeneğinin optik doğrulaması | Hesaplandı, ölçülmedi |
| Split-core CT'nin komşu faz kaçak akısı altında hata bandı | ±%1.5 tahmin; kalibrasyon tezgâhında doğrulanmadı |
| Mıknatıs kaidenin 1 g/150 Hz titreşimde kayma testi | Yapılmadı |
| IP65 gövde ve IPC-CC-830B kaplama nitelendirmesi | Şartname yazıldı, numune üretilmedi |
| Enerji hasadı | Ölçülmedi, iddia edilmiyor |
| Anten glandının filoda fiilen bulunup bulunmadığı | Bilinmiyor — [11-ACIK-SORULAR.md] S1 |
