# PANO GÖZ — Uç Düğüm Üretici Yazılımı

**Hedef:** STM32WLE5CC — Cortex-M4, 256 kB flash, 64 kB SRAM, **868 MHz
sub-GHz alıcı-verici aynı yongada**.
**Dil:** C99. **Kayan nokta yok. libm yok. İlk kurulumdan sonra dinamik
bellek ayırma yok.**

Şartnamenin 3. maddesi mikrodenetleyici kaynak kodunu, programın çalışma
mantığını ve mümkünse bir akış diyagramını istiyor. Bu dizin üçünü de içerir:

| Ne | Nerede |
|---|---|
| Kaynak kod | `node/*.c`, `node/node.h` |
| Çalışma mantığı | bu dosya |
| Akış diyagramları | [`AKIS-DIYAGRAMI.md`](AKIS-DIYAGRAMI.md) — Mermaid |
| Çalıştırılabilir kanıt | `cd node && make host && ./panogoz_node --scenario drift` |

---

## 1. Merkezi fikir — düğüm neden bir termometre değil

Herkes panoya bir termometre koyup eşik üstünde alarm verecek. Bu sahada
başarısız olur, çünkü bir bağlantının sıcaklığını belirleyen şey onun
durumu değil, **yükü ve mevsimdir.**

PANO GÖZ **theta** ölçer: bir bağlantının, kendi iki kardeş fazına göre
sıcaklık fazlasının, referans akıma normalize edilmiş hâli.

```
theta_i = [ T_i − medyan(kardeşler) ] / (I / I_ref)²      [referans akımda kelvin]
```

* **Yükten bağımsız** — I² sadeleşir.
* **Ortamdan, mevsimden, güneşten bağımsız** — aynı yerdeki sensörlerin farkı.
* **Yayıcılıktan bağımsız** (kızılötesi için) — aynı yüzeyler sadeleşir.
* **GEÇMİŞ GEREKTİRMEZ** — aynı baradaki üç özdeş faz, kurulum gününde
  geçerli bir referanstır.

theta, IR termografi uygulamasının zaten şart koştuğu "benzer bileşene göre
yük düzeltmeli delta-T"nin ta kendisidir. Biz onu bir fotoğraf olmaktan
çıkarıp bir sayı yaptık.

**Düğüm theta'yı tek bir sebeple hesaplar: radyo enerjisini nasıl
harcayacağına karar vermek için.** Yetkili theta — RLS ısıl gecikme çözümü,
CUSUM, değişim noktası ve yük yanlılığı düzeltmesiyle — sunucuda, bu düğümün
gönderdiği ham LSB'lerden hesaplanır. Düğümün kopyası kasıtlı olarak daha
kabadır ve **asla tek başına alarm vermez.**

---

## 2. Çalışma mantığı

### 2.1 Ana durum makinesi

```
COLD_START → SELF_TEST → PROVISION → ┌→ SAMPLE → AGGREGATE → TX ─┐
                                     │                           │
                                     └───────── SLEEP ←──────────┘
```

İki dal daha vardır ve bunlar hata yolu değil, **birinci sınıf durumdur**:

| Durum | Ne zaman | Ne yapar |
|---|---|---|
| `DE_ENERGISED` | Sıfır geçişi YOK **ve** akım YOK | Bütün ısıl göstergeleri geçersiz ilan eder. Yavaş kalp atışı sürer — sessizlik ölü düğümden ayırt edilemez. |
| `LOW_BATTERY` | Hücre kritik | Hayatta kalma kadansı, sağlık çerçevesi. **Mutlak sıcaklık limitleri AÇIK kalır** — pilin bitmesi 110 °C'lik bir pabucu yutmak için gerekçe değildir. |
| `FAULT` | Öz test başarısız | Kimlik ve nedeni yavaşça yayınlar. Ofisten bakıldığında sessiz düğüm ile arızalı düğüm aynı görünür; sadece birine araç gerekir. |

`DE_ENERGISED` için ikisini birden şart koşuyoruz. CT'si düşmüş bir düğüm ölü
bir pano gibi görünmemeli, tersi de olmamalı: "pano kapalı" ile "sensörümüz
koptu" farklı iş emirleridir.

### 2.2 Uyarlanabilir kadans — 2 yukarı / 4 aşağı histerezis

| Kadans | Periyot | Ne zaman |
|---|---|---|
| `IDLE` | 900 s | Normal |
| `WATCH` | 60 s | theta yüksek veya yükseliyor (**yumuşak** tetik) |
| `BURST` | 10 s | Mutlak sıcaklık limiti veya 20 K ham kardeş farkı (**sert** tetik) |

* **Neden histerezis:** gerçek bir fiderde theta, yük şekli hareket ettikçe
  saatte birkaç kez eşiği geçer. Histerezissiz düğüm bütün gün 900 s ile 60 s
  arasında gidip gelir; 60 s, 900 s'nin yedi katı enerji harcar, ve zamanın
  yarısını salınarak geçiren düğümün ömrü on üç yıl değil beş yıldır.
* **Neden asimetrik:** bir çevrim erken yükselmek birkaç mikroamper-saate mal
  olur. Bir çevrim erken inmek, operatöre o ilginç dakikada ne olduğunu
  gösterecek örnekleri kaybetmeye mal olur.
* **Yumuşak tetik en fazla `WATCH`'a çıkar.** Günler içinde sürüklenen bir
  bağlantının on saniyede bir örneklenmesi gerekmez: 60 s zaten civatalı bir
  pabucun ısıl zaman sabitini (~900 s) on beş kat çözer, `BURST` ise
  `WATCH`'un altı katı enerjidir. Bunu yanlış ayarlamak on üç yıllık düğümü
  altı aylık düğüme çevirir.
* Sert tetik **saymadan** doğrudan `BURST`'e gider: 110 °C'lik bir pabucu iki
  kez doğrulayana kadar yirmi dakika kaybedilmiş olur.

### 2.3 Uçtaki analitik — hepsi tamsayı

| Büyüklük | Format | Not |
|---|---|---|
| Sıcaklık | `int16_t`, TMP117 ham LSB = **tam olarak 1/128 °C** | Düğümde asla dönüştürülmez |
| Akım | `int32_t` miliamper | Tam RMS, ≥ 1 şebeke çevrimi |
| Yük faktörü `f` | `uint32_t` Q16 | `f = I/I_ref`, 1.0 = 65536 |
| theta | `int32_t`, aynı LSB | `theta = dt/f²`, 64-bit ara değerle |
| Eğim | `int32_t` mK/gün | `86400000/128 = 675000`, tam bölünür |

**Sıcaklık neden TMP117 LSB'den hiç çıkmaz:** 1/128 °C ikinin kuvvetidir,
ikilikte tamdır, hiçbir aşamada yuvarlama hatası taşımaz. theta, aynı yerdeki
iki sensörün **farkının** bir yük oranına bölünmesidir; düğümde "dereceye"
her dönüştürme, bütün amacı 0.2 K çözmek olan bir büyüklüğe yuvarlama hatası
enjekte eder. Dolayısıyla düğüm ham LSB saklar, toplar, farkını alır, eğimini
çıkarır ve gönderir; insan birimi yalnızca yazdırma yardımcısında ve sunucuda
görünür.

**Kardeş medyanına KENDİSİ DAHİL DEĞİLDİR.** Üç fazla, üçünün medyanını almak
bir komut daha ucuzdur. Aynı zamanda yanlıştır: arızalı faz kardeşlerinden
birini geçtiği anda medyan başka bir üyeye atlar ve sinyalin yaklaşık %40'ı
sessizce yok olur. Tam iki kardeşle medyan onların ortalamasıdır; bu dosya
onu hesaplar.

**Eğim, ham sıcaklığın değil THETA'nın eğimidir.** Gerçek bir Türk AG
sekonder fiderinde bir pabuç her gün 04:00 ile 19:00 arasında 8 K ısınır;
buna doğru uydurmak kusursuz sağlıklı bir bağlantıda her sabah 12 K/gün
"yükselen eğilim" verir. theta yükü böler — projenin bütün tezi budur — o
yüzden eğilenen şey theta'dır.

**Eğim yazmacı, telemetri kadansından KOPUKTUR.** Düğüm ister 900 s'de ister
10 s'de örneklesin, yazmaca en fazla 30 dakikada bir theta girer ve eğime
ancak pencere ≥ 8 saati kapsadığında ve ≥ 12 örnek biriktiğinde inanılır.
Aksi hâlde bir olay patlamasında 32 örnek beş dakikayı kapsar ve beş dakikalık
0.2 K gürültüye uydurulmuş doğru, yüzlerce kelvin/gün eğim üretir.

**Eşikler gürültüye göre tabanlanır.** `theta = dt/f²`, 0.2 K'lık kardeş
çifti gürültüsünü `1/f²` ile büyütür: `f = 0.35`'te theta'nın bir sigması
1.6 K'dır. Tam yükte doğru olan sabit bir eşik, hafif yükte saf gürültüdür.
Bu yüzden hem eğim hem basamak eşiği, o pencerede gerçekten sahip olunan
çözünürlükten (`theta_min` medyanı) türetilir. Basamak testi tepe-tepe değil,
**pencerenin iki yarısının medyan farkıdır**: tepe-tepe genliğin standart
sapması örnek sayısıyla BÜYÜR, yani sağlıklı bir bağlantıyı daha uzun
izledikçe daha çok tetiklerdi. Bu tam tersidir ve bir trend dedektörünün
üçüncü ayda kapatılmasının olağan sebebidir.

### 2.4 Görülebilirlik — kör olduğumuzda söyleriz

```
theta_min(f) = 3σ / f²          σ_TC-çifti = 0.2 K
```

| f | theta_min |
|---|---|
| 0.85 | 0.84 K |
| 0.60 | 1.69 K |
| 0.40 | 3.80 K |
| 0.20 | **15.23 K** |

`f < 0.35` altında düğüm **azaltılmış duyarlılıktadır** ve `SENSITIVITY_LOW`
bayrağını kurar. Bu bir kusur değil, bir özelliktir: theta yine yayınlanır
(sunucu ham veriyi ister) ama düğümün kendi tetikleyicisi olarak
kullanılmaz, ve mutlak limitler açık kalır.

Kör olduğumuz her durumun **ayrı** bir bayrağı vardır ve hiçbiri pano
arızasıyla karıştırılmaz: `DE_ENERGISED`, `SENSITIVITY_LOW`, `MOUNT_LOST`,
`PEER_LOST`, `SENSOR_FAULT`, `CELL_LOW`, `BUFFERING`, `CLOCK_UNSYNCED`.

Özellikle `MOUNT_LOST`: kablodan düşmüş bir kelepçe bölme havasını okur, yani
"theta"sı bağlantının gerçek yükselişinin negatifidir — yaklaşık −19 K, ki bu
**eksi 59 µΩ fazla temas direncine** çevrilir. Bunu bir ölçüm olarak
yayınlamak, bir izleme sisteminin bir operatörü temelli kaybetmesinin tam
yoludur. `MOUNT_LOST` kurulu iken bu düğümden theta çıkmaz.

### 2.5 Fazla temas direnci — **her zaman bir aralık**

```
dR = theta / (R_th · I_ref²)
```

`R_th` yalnızca iki kat mertebesinde bilinir, dolayısıyla `dR` **hiçbir zaman
tek bir sayı olarak değil, R_th aralığı iliştirilmiş bir ARALIK olarak**
raporlanır.

* 240 mm² **civatalı kablo pabucu**: `R_th = 2.0 … 4.0 K/W`
* 2×(100×10) mm² kalaylı bakır **bara** üzerinde yerel kaynak, **iki taraflı
  kanat** olarak: `R_th = 1/(2·√(h·P·k·A)) = 0.24 … 0.38 K/W`
  (k=400 W/mK, A=2e-3 m², P≈0.44 m, h=5–12 W/m²K)

Bara sayısını pabuç için kullanmak (ya da daha kötüsü, dikkatsiz bir tek
boyutlu türetmenin bara için ürettiği 3.44 K/W'ı) fiziksel olarak imkânsız
bir yükselme öngörür ve bir izleme sisteminin sağlam bir bağlantıyı arızalı
raporlamasının yoludur.

Doğrulama, `--selftest` çıktısından:

```
   theta=32.00 K @ 400 A  ->  50.0 .. 100.0 uohm
      alt sinir (R_th=4.0)   got=50000    want=50000    OK
      ust sinir (R_th=2.0)   got=100000   want=100000   OK
```

400 A'lik bir pabuç 50 µΩ'da 8.0 W harcar ve 2–4 K/W ile 16–32 K yükselir;
32 K geri beslendiğinde aralık başladığımız 50 µΩ'u kapsar.

### 2.6 PRPD binleme — **hiçbir yerde logaritma yok**

Bir faz çözünürlüklü kısmi deşarj deseni normalde her darbenin
`20·log10(q)`'sü alınarak kurulur. Li-SOCl2 beslemeli bir düğümde 10 kdarbe/s
için bu saniyede 10 000 logaritma demektir — hem karşılanamaz hem
gereksizdir, çünkü **logaritma zaten analog dedektörde alınmıştır.** AD8318
bir demodüle eden logaritmik yükselteçtir: çıkış gerilimi 60 dB aralıkta
24 mV/dB ile giriş gücünde dB olarak doğrusaldır.

| | Aritmetik |
|---|---|
| **Genlik, sevk edilen kart** | AD8318 ile 12-bit 3.3 V ADC arasında 0.859 dirençsel bölücü → **tam olarak 25.6 ADC LSB/dB**, yani bir 2.5 dB bin = **tam 64 LSB**. `bin = (adc − adc0) >> 6`. Bir çıkarma, bir kaydırma. |
| **Genlik, bölücüsüz kart** | Ham eğim `24000 µV/dB ÷ 805.664 µV/LSB = 29.79 LSB/dB`, bir bin = 74.47 LSB. 74.47'ye bölmek = Q16 ters çarpan **880** ile çarpmak. `bin = ((adc − adc0) · 880) >> 16`. |
| **Faz** | **Şebeke çevrimi başına BİR bölme**, darbe başına değil. Sıfır geçişi kesmesi ölçülen periyodu verir, `recip = ceil((64 << 24) / periyot)` bir kez hesaplanır, sonra her darbe için `bin = (dt · recip) >> 24`. |

Tavan (kesme değil) alınması kasıtlıdır: kesilmiş bir ters çarpanla tam
yarım-çevrim noktası bir bin aşağı düşer, ve yarım çevrim tam olarak
ayırmaya çalıştığımız iki mekanizmanın yaşadığı yerdir.

**Darbelerin nerede olduğu ayırt edici özelliktir, ne kadar büyük oldukları
değil:**

* **Gerilim sürücülü deşarj** (boşluk, yüzey, korona) alan yüksek ve **hâlâ
  yükselirken** ateşlenir → **gerilimin yükselen eğimlerinde** kümelenir.
* **Bozulan bir bağlantıdaki seri mikro-ark** AKIM sürücülüdür. İçinden geçen
  akım çöktüğünde söner, aralıkta toparlanma gerilimi kurulduğunda yeniden
  tutuşur → **AKIM SIFIR GEÇİŞLERİNDE**, `φ` ve `180+φ`'de kümelenir. Akım
  **tepelerini izlemez.**

Çalıştırılmış kanıt (`--scenario prpd`), cos φ = 0.95 gecikmeli yük için
darbeler 8–31° ve 188–211° aralıklarında, yani 18° ve 198° çevresinde:

```
 faz cozunurlu desen (satir = genlik bin, sutun = 8 faz bin):
      0     45    90   135   180   225   270   315 derece
    37 dB |#...#...|
    32 dB |#...#...|
    27 dB |#...#...|
    22 dB |#...#...|
```

**DÜRÜSTLÜK:** 400 V'ta klasik kısmi deşarj **olmaz** — havada Paschen
minimumu 327 V'tur. Bu kanalın AG'da ölçtüğü şey gevşek bağlantı
mikro-arkıdır. **pC-eşdeğeri** olarak dB cinsinden raporlanır, **IEC 60270
izlenebilir değildir**, ve AG'da **asla tek başına bir iş emri açmaz** —
yalnızca ısıl bulguyu destekler.

Kablo biçimi, `panogoz/sim/prpd.py` ile **bayt bayt aynıdır** — doğrulandı:

```
firmware blob bytes : 136
unpacked shape      : (64, 32) uint16
total pulses        : 8976
repack identical    : True
phase degrees       : [8.4, 14.1, 19.7, 25.3, 30.9, 188.4, 194.1, 199.7, 205.3, 210.9]
```

### 2.7 Zaman senkronizasyonu — iki saat, iki iş

**1. İNCE FAZ: şebeke sıfır geçişi.** Kapasitif E-alan algılayıcısından
(düğüm kartındaki bir bakır ada; hiçbir şeye galvanik bağlantı yok, bir faz
iletkenine **kelepçe yok**). Bir karşılaştırıcı her geçişte serbest çalışan
zamanlayıcıyı yakalar. Bu referans:

* uzun vadede **sürüklenmesizdir** — Kıta Avrupası senkron alanında şebekenin
  zaman sapması etkin olarak denetlenir;
* pano genelinde **ortak moddur** — her düğüm aynı kutuda aynı üç faza bakar.

Karşılaştırıcı + kesme gecikmesi düğüm başına ≈ 1.5° (83 µs, 1σ) seğirme
verir. İki düğüm dolayısıyla şebeke çevriminin **neresinde** olunduğu
konusunda ≈ **±120 µs** içinde anlaşır.

**2. KABA DUVAR SAATİ:** 32.768 kHz kristal + RTC, artı ağ geçidinden 300 s
işaret. Kristal, parabolik sıcaklık katsayılı bir diyapazondur:
`df/f = −k(T−T0)²`, `k = 0.034 ppm/°C²`, `T0 = 25 °C`. Telafi edilmezse
yüklü bir pano içindeki 60 °C'de **−41.65 ppm** (öz testte hesaplanıyor);
saklanan eğriye karşı MCU'nun kendi sıcaklık sensörüyle telafi edildiğinde
artık hata ≈ **±5 ppm**.

**NE İDDİA EDİYORUZ, NE ETMİYORUZ**

| | |
|---|---|
| Düğüm ↔ ağ geçidi duvar saati, işaret alınırken | **± 5 ms** |
| Düğüm duvar saati, işaret 24 saat kaybolursa | **± 0.5 s** |
| Ağ geçidi ↔ UTC | **± 1 s** (WAN üzerinden NTP, PPS yok — daha iyisini iddia etmiyoruz) |
| Aynı panodaki iki düğüm, **göreli** olay zamanlaması | **± 120 µs** |

Mutlak mikrosaniye zaman damgası **iddia etmiyoruz**. Ark/PD korelasyonu için
önemli olan sayı görelidir, ve o sayı iyidir çünkü bizim kristalimize değil,
şebekeye biner.

---

## 3. Enerji bütçesi

### 3.1 Enerji hasadı **YOK**

İddia etmek kolay olurdu: bir metre ötede 2312 A taşıyan bir bara var, CT
hasadı sunumu kendi kendini yazar. **Etmiyoruz**, ve gerekçeleri bir dağıtım
mühendisinin cümleyi bitirmeden soracağı gerekçelerdir:

1. Düğüm **alt kablo bölmesinde**, ömrünün çoğunu anma değerinin %15–60'ı
   arasında geçiren bir çıkışta oturur. Buna göre boyutlanmış bir hasatçı
   şubat ayında saat 03:00'te hiçbir şey üretmez — ki bütün kış çevrim yapmış
   bir bağlantının nihayet bıraktığı an tam olarak odur.
2. Bir iletkenden hasat yapmak, ısıl davranışını ölçtüğümüz devreye bir yük
   ekler. Bir sistemi bozarak ölçmek, bozan şey ısı olduğunda kötü fikirdir.
3. Hasatçı + süperkapasitör + denetleyici daha çok parçadır ve her biri,
   izole edecek bir AG giriş kesicisi olmayan canlı bir panoda kapalı
   arızalanabilecek bir parçadır.

Yani: **birincil Li-SOCl2 hücre, şarj devresi yok, hasatçı yok**, 9–16 yıllık
tasarım ömrü — ve bu sayı bir slaytta iddia edilmiyor, `power.c` içinde
durum başına akım tablosundan **hesaplanıyor.**

### 3.2 Tablo (çalışma zamanında hesaplanır — `--scenario energy`)

Bütün akımlar 3.6 V'ta **tüm düğüme** aittir, sadece MCU'ya değil. Bunlar
veri sayfalarından + pay ile **bütçe rakamlarıdır**, kurulmuş bir karttan
alınmış ölçümler değil — var olmayan bir laboratuvarı ima etmek yerine bunu
söylüyoruz.

```
  ENERJI BUTCESI  (ER14250 Li-SOCl2, 1.2 Ah nominal, 3.6 V)
  ----------------------------------------------------------------
  durum      akim uA     sure ms      yuk nAs       enerji mJ
  WAKE           4500        1.50         6750          0.024
  SENSE          1335       15.50        20692          0.074
  CT             2000       22.00        44000          0.158
  COMPUTE        4500        3.00        13500          0.048
  FRAM           4000        1.20         4800          0.017
  TX            24000       77.00      1848000          6.652
  RX             5500       60.00       330000          1.188
  SLEEP           3.0   (uyanik olmayan tum sure; STOP2 + RTC + FRAM sleep)
  toplam/cevrim: 180.2 ms uyanik, 2267.7 uAs, 8163 uJ

  kadans      periyot   ort. akim   +oz desarj    omur
  IDLE          900 s      5.52 uA     6.89 uA    6171 gun (16.9 yil)
  WATCH          60 s     40.79 uA    42.15 uA    1008 gun (2.8 yil)
  BURST          10 s    229.72 uA   231.09 uA     183 gun (0.5 yil)
  GOREV KARMASI (%97.0 idle / %2.5 watch / %0.5 burst):
     ortalama 8.89 uA  ->  4781 gun = 13.1 YIL  (tasarim omru 9-16 yil)
  Enerji hasadi YOK. Birincil Li-SOCl2 hucre, sarj devresi yok.
```

Akım rakamlarının kaynağı:

| Durum | Kaynak |
|---|---|
| SLEEP 3.0 µA | STM32WLE5 STOP2 + RTC + 64 kB SRAM saklamalı 1.6 µA (DS13105 tipik, 3.0 V, 25 °C) + MB85RS64V uyku 0.9 µA + bölücü/LDO sızıntısı 0.5 µA |
| SENSE 1335 µA | TMP117 tek atım, 8 ortalama (15.5 ms boyunca 135 µA) + MCU LPSLEEP'te 1.2 mA |
| CT 2000 µA | ADC + burden tamponu, tam bir 20 ms şebeke çevrimi + kurulum |
| TX 24 mA / 77 ms | Sub-GHz PA, +14 dBm RFO_LP. 35 bayt @ SF7 BW125 CR4/5 = **77.06 ms**, `pg_airtime_ms()` ile hesaplanıyor, tahmin edilmiyor |
| RX 5.5 mA / 60 ms | Rx boosted; **onay + işaret + kardeş medyanı TEK pencerede** |

**Öz deşarj satırına dikkat.** "5.5 µA, demek ki 21 yıl" demek dörtte bir
oranında yanlış olurdu: 1.2 Ah'in yılda %1'i, düğüm açık olsun ya da
olmasın akan **1.37 µA**'dır ve boşta kadansta bütün bütçenin %20'sidir.

**Görev karması neden sevk edilen sayıdır:** bir düğüm sonsuza kadar 900
s'de oturmaz. Gerçekten bozulan bir bağlantıyı izleyen bir düğüm aylarca
`WATCH`'ta kalır ve üç yıldan kısa sürede biter. Bu **doğru** sonuçtur —
düğüm bağlantıyla birlikte değiştirilir — ama gizlenecek bir sayı değildir,
o yüzden `pg_power_report()` her satırı yazdırır.

**LDO notu:** hücre 3.67 V açık devre verir, MCU 1.8–3.6 V ister, dolayısıyla
25 nA sükûnet akımlı bir LDO (TPS7A02 sınıfı) 3.0 V'a düşürür ve aynı zamanda
kararlı bir ADC referansı sağlar. LDO ömrü etkilemez: aynı **yükü** geçirir,
ve hücrenin anma değeri Ah cinsindendir. Kaybedilen şey Wh'dir, Ah değil.

### 3.3 Hücre — Li-SOCl2 pasivasyonu

Li-SOCl2 deşarj eğrisi meşhur biçimde **düzdür**: uç gerilimi diz noktasına
kadar neredeyse hiçbir şey söylemez. Bu yüzden birincil kalan kapasite
kestirimi **harcananın integralidir** (coulomb sayımı), açık devre gerilimi
yalnızca çapraz kontrol ve ömür sonu dedektörüdür.

Yıllarca birkaç mikroamperde oturmuş bir hücrenin anotunda LiCl filmi
oluşur. Açık devre gerilimi hâlâ sağlıklı 3.6 V okur, coulomb sayımı hâlâ
%80 der — sonra PA ilk kez 24 mA istediğinde 2.4 V'a çöker, çerçeve kaybolur
ve düğüm ölü görünür. Bunu görmenin **tek** yolu yüklemektir:
`hal_vbat_loaded_mv()` 50 mA'lik bir darbe uygular ve altında ölçer. BOM'daki
**HLC** (hibrit katman kapasitörü) tam olarak o darbeyi tamponlamak için
vardır; hücre bozuk ilan edilmeden önce bir depasivasyon yükü uygulanır ve
test tekrarlanır.

---

## 4. Bellek haritası

### 4.1 Flash — STM32WLE5CC, 256 kB

| Adres | Boyut | İçerik | Koruma |
|---|---|---|---|
| `0x08000000` | 16 kB | **BOOTLOADER** | WRP + RDP seviye 1 — **asla güncellenmez** |
| `0x08004000` | 48 kB | **KURTARMA İMAJI** | WRP — **asla güncellenmez**; sadece işaret yayar ve OTA kabul eder |
| `0x08010000` | 88 kB | SLOT A | |
| `0x08026000` | 88 kB | SLOT B | |
| `0x0803C000` | 16 kB | OTA üstverisi / yapılandırma | 2 × 8 kB, dönüşümlü yazım |

### 4.2 FRAM — MB85RS64V, 8 kB, bayt yazılabilir

| Ofset | Boyut | İçerik |
|---|---|---|
| `0x0000` | 32 B | Halka başlığı A |
| `0x0020` | 32 B | Halka başlığı B (ayna — dönüşümlü yazımla atomik commit) |
| `0x0040` | 64 B | Devreye alma bloğu (pano · cihaz · bağlantı · I_ref · CT · kalibrasyon) |
| `0x0080` | 64 B | OTA durum bloğu |
| `0x00C0` | 8000 B | **Sakla-ilet halkası: 200 × 40 B kayıt** |

Halka kapasitesi: 900 s'de **50 saat**, 60 s'de 3.3 saat.

**Neden FRAM, ASLA dahili flash — üçü de ölümcül üç sebep:**

1. **Dayanım.** STM32WL flash'ı sayfa başına 10 000 silme çevrimi için
   belirtilmiştir. 60 s'de bir telemetri kaydı günde 1440 yazmadır; 64 kayıt
   tutan bir 2 kB sayfa günde 22 kez silinir ve anma dayanımına **yaklaşık
   15 AYDA** ulaşır. FRAM 1e13 çevrim için anmalıdır — saniyede bir yazmada
   300 000 yıl. 13 yıllık IDLE kadans ~1.37 M yazmadır: **yedi mertebe pay.**
2. **Atomiklik.** Bir flash sayfa silme ≈ 20 ms sürer ve sürdürülemez.
   Ortasındaki bir brown-out 64 kaydı yok eder — yani tam olarak düğümü
   brown-out eden olayı kapsayan kayıtları. Bir FRAM bayt yazması SPI
   işleminin içinde tamamlanır; bir brown-out en fazla bir bayta mal olur ve
   çift tamponlu CRC'li başlık onu yakalar.
3. **Yürütme duraklaması.** Dahili flash yazmak flash veri yolunu durdurur,
   yani ince faz referansımız olan sıfır geçişi kesmesi **tam da kayıt
   tuttuğumuz anda** gecikir. FRAM SPI2 üzerindedir ve hiçbir şeye dokunmaz.

Kayıt önce FRAM'e yazılır, **sonra** gönderilir. Su seviyesi bir **onayla**
ilerler, bir iletimle değil: antenden ayrılmış bir çerçeve, varmış bir çerçeve
değildir. Halka dolarsa **en eski** düşer, düşen sayılır ve **yayınlanır** —
gürültülü taşan sınırlı bir tampon dayanıklılıktır; pilli bir düğümdeki
sınırsız bir tampon gecikmeli bir çöküştür.

### 4.3 SRAM — 64 kB'ın kullanımı (ölçülmüş)

| Yapı | Boyut |
|---|---|
| `pg_node_t` (tüm düğüm bağlamı) | **1136 B** |
| — `pg_edge_t` (örnek penceresi + theta eğim yazmacı + kardeşler) | 756 B |
| — `pg_power_t` | 96 B |
| — `pg_agg_t` | 64 B |
| — `pg_time_t` / `pg_ring_hdr_t` / `pg_ota_t` | 32 B her biri |
| `pg_prpd_t` (64×32 uint16 histogram + durum) | **4120 B** — yalnızca PD-01 |

Isıl kelepçede statik RAM **1.1 kB**, PD düğümünde **5.3 kB**. Hepsi
`static`; **ilk kurulumdan sonra tek bir `malloc` yoktur.**

Çekirdek kod boyutu (x86-64, `-Os`, sadece `main/theta_edge/prpd_bin/radio/power`):
**18 780 bayt metin.** Thumb-2'de daha küçük olacaktır ama o rakamı
ölçmedik, o yüzden iddia etmiyoruz.

---

## 5. Bacak ataması

STM32WLE5CC, 48 bacak UFQFPN. *Kart bazlıdır; RF anahtar kontrolü kullanılan
ön uç modülüne göre değişir.*

| Bacak | İşlev | Bağlı |
|---|---|---|
| `PA4` | SPI1 `NSS` | MB85RS64V FRAM `/CS` |
| `PA5` | SPI1 `SCK` | FRAM |
| `PA6` | SPI1 `MISO` | FRAM |
| `PA7` | SPI1 `MOSI` | FRAM |
| `PB6` | I2C1 `SCL` | TMP117 (0x48) + SHT41 (0x44) |
| `PB7` | I2C1 `SDA` | TMP117 + SHT41 |
| `PB8` | `EXTI8` | TMP117 `ALERT` — dönüşüm bitti |
| `PA0` | `ADC1_IN5` | Ayrılabilir CT burden gerilimi (yarı besleme öngerilimli) |
| `PA1` | `ADC1_IN6` | AD8318 log dedektör çıkışı — **yalnızca PD-01** |
| `PA2` | `COMP1_INP` | Kapasitif E-alan algılayıcı → **şebeke sıfır geçişi** |
| `PA3` | `COMP1_INM` | Karşılaştırıcı öngerilim referansı |
| `PB3` | `EXTI3`, yukarı çekmeli | Kelepçe temas / mıknatıs kaide anahtarı → `MOUNT_LOST` |
| `PB4` | GPIO çıkış | Pil bölücü etkinleştirme (uykuda bölücü sızdırmasın) |
| `PB5` | GPIO çıkış | **50 mA pasivasyon test yükü** etkinleştirme |
| `PB9` | `TIM2_CH` yakalama | PD darbe zamanlayıcı yakalama (yalnızca PD-01) |
| `PB2` | `COMP2` | PD karşılaştırıcı eşiği (yalnızca PD-01) |
| `PA8` | `LPUART1_TX` | Servis konsolu — yalnızca test noktası, konnektör yok |
| `PA9` | `LPUART1_RX` | Servis konsolu |
| `PC3` / `PC4` / `PC5` | GPIO | `FE_CTRL1/2/3` RF anahtar (ön uca göre) |
| `PA13` / `PA14` | `SWDIO` / `SWCLK` | Üretim programlama pedleri; RDP seviye 1 ile kapatılır |
| `PC14` / `PC15` | `OSC32_IN/OUT` | 32.768 kHz kristal (diyapazon, ±20 ppm) |
| `PC13` | GPIO | LED — yalnızca devreye alma; üretimde takılmaz |
| `VDD` | | LDO'dan 3.0 V (TPS7A02 sınıfı, 25 nA I_q) |
| `VBAT_CELL` | | ER14250 Li-SOCl2 + HLC tamponu |

Kartta **kelepçe dışında hiçbir şey bir faz iletkenine dokunmaz** ve kelepçe
de 1 kV kablo kılıfının üzerindedir. E-alan algılayıcısı kapasitiftir, HFCT
PE saplamasına takılır (Madde 2.2.6.2.iii, M12 paslanmaz topraklama
terminali). **Bir faz iletkenine asla HFCT kelepçelenmez:** 50 Hz besleme
amperinde 6 mV_pp'dir ve dedektörü doyurur; 1–3 MHz yüksek geçiren filtre
zorunludur.

---

## 6. Derleme

### 6.1 Ana bilgisayar (bu, jüri ortamında çalışır)

```bash
cd firmware/node
make host                          # veya Windows'ta: mingw32-make host
./panogoz_node --scenario drift
```

`make` yoksa doğrudan:

```bash
gcc -std=c99 -Wall -Wextra -Werror -O2 -Wno-unused-parameter \
    -Wdouble-promotion -DPG_HOST=1 -o panogoz_node \
    main.c theta_edge.c prpd_bin.c radio.c power.c host_sim.c
```

Hedefler: `make host` · `make run` · `make test` · `make all-demo` ·
`make target` · `make clean`

Senaryolar:

| Senaryo | Ne gösterir |
|---|---|
| `healthy` | Negatif kontrol — 24 saat, sıfır tetik |
| `drift` | Civata yavaş gevşiyor (varsayılan) |
| `step` | Bir pabuç birden bozuluyor |
| `deenergised` | Pano enerjisiz — bütün ısıl göstergeler geçersiz |
| `lowbat` | Pil bitiyor — hayatta kalma kadansı |
| `mountlost` | Kelepçe düştü — theta yayınlanmaz |
| `burst` | Mutlak limit aşıldı — doğrudan 10 s |
| `outage` | Ağ geçidi yok — FRAM halkası dolar, sonra boşalır |
| `ota` | OTA durum makinesi: enerji kapısı, deneme, geri alma |
| `prpd` | PRPD biriktirme + paketleme + ASCII desen |
| `energy` | Sadece enerji bütçesi tablosu |
| `all` | Hepsi (~0.1 s) |

Seçenekler: `--hours N` · `--seed N` · `--verbose` · `--selftest` ·
`--prpd-hex` · `--list`

### 6.2 Hedef (STM32WLE5CC)

```bash
make target        # arm-none-eabi-gcc gerektirir
```

**Jüri ortamında ARM derleyicisi yoktur, o yüzden `make target` bir mesajla
atlanır ve sessizce başarısız olmaz.** Aynı beş `.c` dosyası değişmeden
derlenir; tek fark `hal_*` katmanının `host_sim.c` yerine
`port/stm32wle5/` altından gelmesidir:

```
port/stm32wle5/
  startup_stm32wle5xx.s      vektör tablosu
  STM32WLE5CCUX_FLASH.ld     bölüm 4.1'deki bağlayıcı betiği
  hal_stm32.c                hal_* → CubeWL LL sürücüleri
  bootloader/                ayrı proje, ayrı imza, WRP + RDP
```

Bayraklar: `-mcpu=cortex-m4 -mthumb -mfloat-abi=soft -Os -ffreestanding
-fno-builtin -nostdlib`. `-mfloat-abi=soft`, kayan nokta kuralının
derleyici tarafından zorlanmasıdır: bir yere `double` sızarsa bağlantı
`__aeabi_dadd` üzerinde kırılır.

**Bekçi köpeği notu:** IWDG, LSI'den beslenir ve azami zaman aşımı ≈ 32
s'dir; 900 s'lik bir uyku onu tetiklerdi. Bu yüzden `IWDG_STOP` seçenek
baytı **0** programlanır ve bekçi köpeği STOP2'de **dondurulur**. Böylece
uyanık evreyi — içinde kod olan tek evreyi — korur, ve olağan "çözüm"
(daha kısa uyku) bütün enerji bütçesine mal olmaz.

**Brown-out:** BOR seviye 2 (≈ 2.3 V). Bir BOR sıfırlamasından sonra FRAM'e
yazılmaz; çift tamponlu CRC'li başlık halkanın sağ çıkmasını garanti eder ve
`PG_F_BROWNOUT` bayrağı bir sonraki çerçeveyle raporlanır.

---

## 7. Doğrulama — gerçek çıktı

### 7.1 Sabit noktalı çekirdek öz testi

```
$ make test
  theta = dt / f^2   (dt LSB, f Q16)
   theta(1024 LSB, f=1.000)                       got=1024       want=1024       OK
   theta(1024 LSB, f=0.500)                       got=4096       want=4096       OK
   theta(1024 LSB, f=0.250)                       got=16384      want=16384      OK
  theta_min(f) = 3 sigma / f^2, sigma_TC = 26 LSB (0.20 K)
   f=0.85 -> 0.84 K   (beklenen 0.83-0.85)
   f=0.60 -> 1.69 K   (beklenen 1.67-1.70)
   f=0.40 -> 3.80 K   (beklenen 3.75-3.81)
   f=0.20 -> 15.23 K   (beklenen 15.0-15.3)  <- SENSITIVITY_LOW

  Fazla temas direnci ARALIK olarak (R_th 2.0-4.0 K/W):
   theta=32.00 K @ 400 A  ->  50.0 .. 100.0 uohm
      alt sinir (R_th=4.0)                        got=50000      want=50000      OK
      ust sinir (R_th=2.0)                        got=100000     want=100000     OK
   theta=16.00 K @ 400 A  ->  25.0 .. 50.0 uohm   (brief: 50 uohm -> 8.0 W -> 16-32 K)

  Tamsayi karekok ve RMS:
   isqrt64(1e12)                                  got=1000000    want=1000000    OK
   isqrt64(2)                                     got=1          want=1          OK

  Cerceve kodlama/cozme (35 bayt, CRC-16/CCITT):
   kodlanmis uzunluk 35 bayt, hava suresi 78 ms (LoRa SF7 BW125 CR4/5)
      cozme donus degeri                          got=35         want=35         OK
      seq round-trip                              got=123456     want=123456     OK
      theta round-trip                            got=812        want=812        OK
      i_rms round-trip                            got=287345     want=287345     OK
      bozulmus cerceve reddedildi                 got=-4         want=-4         OK

  PRPD binleme (logaritma yok):
      genlik: 640 ADC LSB (25 dB) -> bin          got=10         want=10         OK
      faz: 0 tick -> bin                          got=0          want=0          OK
      faz: yarim cevrim -> bin                    got=32         want=32         OK
      faz: cevrim sonu -> bin                     got=63         want=63         OK
      ham kart: 745 ADC LSB (25 dB) -> bin        got=10         want=10         OK

  Kadans histerezisi (2 yukari / 4 asagi):
      1 nitelikli cevrim sonrasi periyot          got=900        want=900        OK
      2 nitelikli cevrim sonrasi periyot          got=60         want=60         OK
      3 sessiz cevrim sonrasi periyot (hala 60)   got=60         want=60         OK
      4 sessiz cevrim sonrasi periyot             got=900        want=900        OK
      sert olay: dogrudan patlama                 got=10         want=10         OK

  Kristal sicaklik telafisi (parabolik, k=0.034 ppm/C^2):
   25 C -> 0.00 ppm, 60 C -> -41.65 ppm (telafi edilmezse)

  ozet: 0 hata
```

### 7.2 `--scenario drift` — 72 saatte gevşeyen bir civata

```
$ ./panogoz_node --scenario drift
 senaryo=drift  seed=20260910  sure=72 saat  fw=panogoz-node 1.0.0
 dugum: SOKE-14 / TC-04 / C06-L1-PABUC, 400 A DSYA cikisi
----------------------------------------------------------------
[COLD_START] boot=1 reset=0x01 ring=0/200 ota=IDLE
[SELF_TEST] TMP117=ok pil OCV=3610 mV yuklu=3410 mV kelepce=ok
[PROVISION] pano=SOKE-14 cihaz=TC-04 baglanti=C06-L1-PABUC I_ref=400 A CT=var
  t+   14 dk  KADANS -> 900 s   (theta n/a K, tetik: yok)
  t+  374 dk  T=25.73 C  I=114 A  theta=2.56 K  halka=0
  t+  749 dk  T=30.47 C  I=187 A  theta=4.50 K  halka=0
  t+ 1080 dk  KADANS -> 60 s   (theta 5.05 K, tetik: theta esigi asildi)
  t+ 1100 dk  KADANS -> 900 s   (theta 3.91 K, tetik: yok)
  t+ 1115 dk  T=34.97 C  I=248 A  theta=4.66 K  halka=0
  t+ 1490 dk  T=33.40 C  I=242 A  theta=0.57 K  halka=0
  t+ 1865 dk  T=26.59 C  I=124 A  theta=12.90 K  halka=0
  t+ 1986 dk  KADANS -> 60 s   (theta 15.52 K, tetik: theta esigi asildi)
  t+ 2225 dk  T=36.23 C  I=225 A  theta=5.60 K  halka=0
  t+ 2586 dk  T=39.73 C  I=299 A  theta=7.19 K  halka=0
  t+ 2947 dk  T=26.71 C  I=114 A  theta=8.98 K  halka=0
  t+ 3308 dk  T=29.54 C  I=168 A  theta=9.12 K  halka=0
  t+ 3669 dk  T=37.52 C  I=224 A  theta=10.33 K  halka=0
  t+ 4030 dk  T=42.34 C  I=302 A  theta=11.97 K  halka=0
----------------------------------------------------------------
 SONUC (2480 uyanma cevrimi, 72 saat sanal zaman)
  T ort 28.44 C  (min 27.66 / maks 29.45)   I_rms 130.7 A   n=32
  yuk faktoru f=0.327   kadans 60 s
  theta egimi 4.331 K/gun  (32 ornek, 15 saat kapsam)   ham sicaklik egimi -84.837 K/gun <- KARAR VERMEZ
  gurultu tabani: egim 2.407 K/gun, basamak 6.00 K (olculen basamak 1.45 K)
  theta = 13.17 K @ 400 A   (gorulebilir en kucuk theta 5.70 K)
  fazla temas direnci 20.6 .. 41.2 uohm  [R_th 2.0-4.0 K/W araligi ile]
  bayraklar: DATA_VALID SENSITIVITY_LOW LEARN_MODE
  tetik: theta yukselen egilimde
  radyo: 2480 gonderildi, 2480 onaylandi, 0 basarisiz, FRAM halka 0/200 (dusen 0)
  [GERCEK DEGER - dugum bunu asla gormez] enjekte edilen fazla
   temas direnci 27 uohm, o andaki kayip 0.46 W. Yukaridaki
   ARALIK bu degeri kapsiyorsa kestirim dogrudur.
  zaman: 2480 isaret alindi, 2480 sifir gecisi sayildi, duvar saati hatasi +/-2 ms
  ETSI kullanim orani: 4.45 s / 3600 s penceresinde (sinir %1.0)
```

Dikkat edilecek üç şey:

* **Ham sıcaklık eğimi −84.8 K/gün, theta eğimi +4.3 K/gün.** Ham sıcaklık
  günlük yük şeklini izler ve hiçbir şey söylemez. theta yükü böler. Bu tek
  satır, projenin bütün tezidir.
* **Fazla temas direnci `20.6 … 41.2 µΩ`; enjekte edilen gerçek değer
  `27 µΩ`.** Aralık doğruyu kapsıyor. Kapsayan bir aralık dürüst iddiadır;
  yakınına düşen bir nokta kestirimi değildir.
* **`SENSITIVITY_LOW` kurulu ama bulgu geçerli:** `f = 0.327`'de görülebilen
  en küçük theta 5.70 K'dır, ölçülen theta 13.17 K'dır. Düğüm hem
  görünürlüğünün düşük olduğunu hem de bulgunun yine de tabanın üstünde
  olduğunu söylüyor.

### 7.3 Kayan nokta / libm / malloc denetimi

Üç bağımsız kontrol. İlkinde yorum satırları soyuluyor, çünkü yorumlarda
"no float" yazıyor ve bir denetimi kendi belgelendirmesiyle geçmek denetim
sayılmaz:

```
$ sed 's://.*::' main.c theta_edge.c prpd_bin.c radio.c power.c \
    | grep -vE "^\s*\*|^\s*/\*" \
    | grep -nE "\b(float|double|malloc|calloc|free|sqrt|log|exp|pow)\b"
819:static pg_node_t g_node;          /* static, not malloc'd - see the header  */
995:  uint32_t rn = pg_isqrt64((uint64_t)n * 1000000ull);  /* sqrt(n)*1000 */
```

İki eşleşme de satır sonu yorumlarının içinde: kodda tek bir `float`,
`double`, `malloc` veya libm çağrısı yok. `pg_isqrt64` bit-bit tamsayı
karekökümüzdür, `sqrt()` değil.

```
$ gcc -O2 -c main.c theta_edge.c prpd_bin.c radio.c power.c
$ objdump -d *.o | grep -cE "movs[sd]|adds[sd]|muls[sd]|divs[sd]|cvts[si]"
0                                   <- tek bir kayan nokta komutu üretilmedi

$ nm *.o | grep " U "
(yalnızca hal_* ve pg_* — TEK BİR libc sembolü yok:
 memcpy yok, memset yok, printf yok, malloc yok)
```

Çekirdek gerçekten serbest duruyor: dışa bağımlılığı **sadece** kendi HAL'ı.
`-Wdouble-promotion` da açık ve `-Werror` ile birlikte derleniyor, yani
kurala derleyici de bekçilik ediyor.

### 7.4 Belirlenircilik

Sanal panoda duvar saati okunmaz; `hal_sleep_ms()` sanal bir saati ilerletir
ve her zaman tabanı açık bir argümandır. Aynı tohum bit bit aynı çıktıyı
verir:

```
$ ./panogoz_node --scenario drift --seed 7 | md5sum
68d62ebb29238ec755e1bbd4711ed02a
$ ./panogoz_node --scenario drift --seed 7 | md5sum
68d62ebb29238ec755e1bbd4711ed02a     <- aynı
$ ./panogoz_node --scenario drift --seed 8 | md5sum
8ac6420ad3e862bbd3d3ac881255c344     <- farklı tohum, farklı kosum
```

Bu, gösterimi bir gösteri olmaktan çıkarıp bir teste dönüştüren şeydir.

---

## 8. Ne uygulandı, ne belgelendi — dürüst beyan

| Bileşen | Durum |
|---|---|
| Ana durum makinesi, kadans, histerezis | **Uygulandı ve çalıştırıldı** |
| theta, theta_min, eğim, basamak, gürültü tabanları, RMS, min/maks | **Uygulandı, öz testi geçiyor** |
| Fazla direnç aralığı | **Uygulandı**, brief'in ters çevirmesine karşı doğrulandı |
| PRPD binleme + paketleme | **Uygulandı**, `panogoz.sim.prpd` ile bayt bayt aynı olduğu **doğrulandı** |
| Çerçeve kodlama/çözme + CRC-16 | **Uygulandı**, gidiş-dönüş ve bozulma testi geçiyor |
| LoRa hava süresi + ETSI kullanım oranı sınırlayıcı | **Uygulandı**, kayan noktasız tamsayı |
| FRAM halkası, çift tamponlu CRC'li başlık, sakla-ilet, birikim boşaltma | **Uygulandı ve `outage` senaryosunda çalıştırıldı** |
| Enerji muhasebesi ve ömür hesabı | **Uygulandı**, çalışma zamanında hesaplanıyor |
| Hücre modeli, pasivasyon testi, coulomb sayımı | **Uygulandı** |
| **OTA durum makinesi** | **Uygulandı ve `ota` senaryosunda dört yol boyunca çalıştırıldı** |
| **OTA flash sürücüsü (`hal_flash_*`)** | **TASLAK.** Bayt sayar ve CRC hesaplar; STM32 flash bankası programlamaz. Bu ağaçta ARM zinciri ve silikon yok, aksini ima etmek yalan olurdu. |
| Bootloader ve kurtarma imajı | **Belgelendi, kodlanmadı.** Ayrı proje, ayrı imza, WRP + RDP. Bölüm 4.1 ve `AKIS-DIYAGRAMI.md` §3a. |
| `port/stm32wle5/` (CubeWL LL sürücüleri, başlangıç kodu, bağlayıcı betiği) | **Belgelendi, sevk edilmedi.** Derleyemediğimiz bir portu göndermiyoruz. `hal_*` yüzeyi `node.h` bölüm 13'te tam olarak tanımlıdır. |
| Ana bilgisayar sanal panosu (`host_sim.c`) | **Uygulandı.** Kasıtlı olarak küçük ve tamsayı; gerçek simülatör `panogoz/sim/`'dir. |
| Kod boyutu ölçümü | **x86-64'te ölçüldü** (18 780 B). Cortex-M4 rakamı **ölçülmedi**, o yüzden iddia edilmiyor. |
| Akım tablosu değerleri | **Veri sayfası bütçesi**, kurulmuş karttan ölçüm **değil**. Her satır kaynağını adlandırıyor. |

### Ve bir kez daha, çünkü en önemli cümle bu

**PANO GÖZ koruma değildir.** Aynı panodaki ABB TVOC-2, arkı **yaklaşık
1 ms'de**, SIL-2 donanımda, döngüde hiç yazılım olmadan keser — ve bunu bu
düğüm hiç kurulmamış olsa da yapar. Bu üretici yazılımındaki her şey bir
**bildirimi** kısaltır, bir **açmayı** asla. Uçtan uca bildirim gecikmesi
**4–13 saniyelik bir ARALIKTIR** (TVOC-2 Modbus görüntüsünün yayılması, ki
ABB bunu dokümante etmiyor ve 0.2–2 s modellendi, artı 1 s tarama, artı
sunucu, artı SMS yolu) ve hiçbir yerde tek bir temiz sayı olarak yazılmaz.

---

*Not: C kaynağındaki ve konsol çıktısındaki Türkçe kasıtlı olarak ASCII'ye
çevrilmiştir ("sicaklik", "baglanti"). Bir UART servis konsolu 7 bit
dostudur ve bir düğüm günlüğünün kod sayfasına bağlı olmaması gerekir.
Operatörün gördüğü metin sunucuda ve arayüzde tam Türkçedir.*
