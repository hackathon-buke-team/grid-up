# 10 · OG Hücre Konsepti

---

## 0. Önce dürüstlük: elimizde OG çizimi yok

Yarışma metni "pano/**hücre** içi anomali" der ve varlık kapsamının yarısı orta gerilim
hücreleridir. Ancak:

* Sağlanan veri paketinde **hiçbir OG çizimi, şartnamesi ya da tip bilgisi yoktur.**
  Paketteki dört TEDAŞ belgesinin dördü de 1600 kVA **AG** panosuna aittir.
* Bu yüzden çizim **istedik**; alınamadı.
* Dolayısıyla bu belge bir **konsepttir**, bir tasarım değil. AG tarafındaki gibi madde
  numarasına dayanan tek bir cümle bulamazsınız, çünkü dayanacağımız bir madde yok.

**Yarısını görmezden gelmek yerine, bilmediğimizi söyleyerek yazıyoruz.** Aşağıdaki her
şey, jenerik bir **36 kV kablo bölmeli, metal muhafazalı, IEC 62271-200'e göre iç ark
sınıflandırılmış** hücre varsayımı üzerine kuruludur.

---

## 1. OG neden AG'den kolay ve neden zor

### 1.1 Kolay olan: fizik gerçekten çalışıyor

AG'de bir dürüstlük problemi vardır: **400 V'ta klasik kısmi deşarj oluşmaz** (Paschen
minimumu 327 V). Orada ölçtüğümüz şey gevşek bağlantı mikro-arkıdır, pC **eşdeğeridir** ve
tek başına ekip yönlendirmez.

36 kV'ta bu kısıt **yoktur**. Faz-toprak 20.8 kV'tur; kablo başlıklarındaki epoksi/EPDM
boşlukları, stres konisi arayüzleri, yüzen ekran uçları ve yüzey kirlenmesi **gerçek kısmi
deşarj** üretir. Kısmi deşarj, OG şalt ekipmanında yalıtım bozulmasının **kabul görmüş**
öncü göstergesidir.

Daha önemlisi **kuplaj noktası doğrudur.** AG'de HFCT'yi koyacak fizikî olarak doğru bir
yer yoktur: PE iletkeni paylaşılan, gürültülü bir yoldur ve tanımlı bir PD kaynağı
taşımaz. OG'de ise:

> Kablo başlığındaki bir deşarjın yüksek frekanslı akım darbesi, **kablo ekranının
> topraklama örgüsünden** döner. HFCT'yi oraya kenetlemek ders kitabı kuplajıdır ve
> yönlüdür: hücre içinden gelen darbe ile şebekeden gelen darbe **ters kutuplu** görünür.

### 1.2 Zor olan: iç ark ve erişim

| Zorluk | AG'de | OG'de |
|---|---|---|
| Bölmeyi güvenli hâle getirme | **İmkânsız** — AG giriş kesicisi yok, karartma gerekir | **Mümkün** — topraklama ayırıcısı + kilitleme; bu OG'yi **daha kolay** yapar |
| İç ark sınıflandırması | Yok (IP2X, Form 2B) | **IEC 62271-200 IAC** — eklenen her nesne sertifikayı sorgulanır kılar |
| Yalıtım mesafeleri | 85 mm faz arası | **270–320 mm** faz-toprak (36 kV, Ud 70 kV, BIL 170 kV) |
| Yardımcı besleme | 6 A gG "İç İhtiyaç" prizi | Hücrenin kendi yardımcı 230 V AC / 48 V DC beslemesi (kurmalı mekanizma, röle) |
| Isıl erişim | Pabuçlar görünür | Bara bağlantıları kapalı bölmede; **IR penceresi yoksa görülmez** |

**En önemli tersine dönüş:** AG'de montaj enerjili yapılmak zorundadır ve bu, projenin en
zor kısıtıdır. OG'de kablo bölmesi topraklama ayırıcısıyla emniyete alınabilir; yani
**OG montajı fiziksel olarak AG montajından güvenlidir**, ama planlı bir kesinti ister.

---

## 2. Kanal seti

```
        ┌───────────────── 36 kV KABLO BÖLMESİ (jenerik) ─────────────────┐
        │                                                                  │
        │   L1        L2        L3      kablo başlıkları / stres konileri  │
        │   ║         ║         ║                                          │
        │  [TC]      [TC]      [TC]   ← 3 × ısıl kelepçe, θ (§2.4)         │
        │   ║         ║         ║       başlık gövdesi üzerinde            │
        │   ╬═════════╬═════════╬══  ekran topraklama örgüleri             │
        │   │         │         │                                          │
        │  (○)       (○)       (○)   ← 3 × HFCT50, ekran örgüsünde (§2.1)  │
        │   │         │         │                                          │
        │   └────┬────┴────┬────┘                                          │
        │        │  toprak barası (earthed volume)                         │
        │      [DÜĞÜM]  ← MV-NODE, toprak barasına sabitli                 │
        │        │                                                          │
        │  [US]──┘  40 kHz ultrasonik alıcı, kapı contası hizası (§2.3)    │
        │                                                                  │
        └─────────────┬────────────────────────────────────────────────────┘
                      │
              [TEV] ─┘  hücrenin ÖN METAL YÜZEYİNDE, dışarıda (§2.2)
```

### 2.1 HFCT50 — kablo ekranı topraklama örgüsünde

| Özellik | Değer | Kaynak |
|---|---|---|
| Bant genişliği | 1 – 80 MHz | HFCT50 veri sayfası |
| Delik çapı | 50 mm | Aynı |
| Boyut | 111 × 123 × 38 mm | Aynı |
| Transfer empedansı / pC duyarlılığı | **VERİLMEDİ** | Sağlanan veri sayfası özetinde yok |

> **AÇIK BEYAN:** HFCT30 için 42 MHz'de 17 mV/mA ve 100 pC'de 0.4 Vpp verilmiştir; HFCT50
> için sağlanan özette **yalnız bant genişliği, delik çapı ve boyut** vardır. Dolayısıyla
> pC cinsinden duyarlılığı **bilmiyoruz** ve tahmin etmiyoruz. Bir PD kalibratörüyle
> ölçülmesi, §6'daki doğrulama listesinin birinci maddesidir.

**Neden 50 mm ve neden HFCT30 değil:** ekran topraklama örgüsü, 36 kV kablolarda tipik
olarak 25–35 mm² kesitli örgülü bakırdır ve kablo başlığının etrafından toplandığında
30 mm'lik bir delikten geçmeyebilir. 50 mm delik, montaj sırasında örgüyü kesip yeniden
sonlandırmak zorunda kalmamayı sağlar — **topraklama iletkenini kesmek kabul edilemez.**

**Yönlülük.** Üç fazın üçünde de HFCT olduğu için darbelerin varış zamanı farkı ölçülebilir
(1 µs çözünürlükte). Hücre içinden gelen bir deşarj üç ekranda **farklı** işaret ve
gecikmeyle görünür; şebekeden gelen bir gürültü darbesi **eşzamanlı ve eş kutuplu**
görünür. Bu, OG'nin AG'de sahip olmadığımız ikinci hediyesidir: **gürültü kapılama fizikî
olarak yapılabilir.**

### 2.2 TEV plakası — hücrenin dış metal yüzeyinde

Geçici toprak gerilimi (Transient Earth Voltage), iç deşarjın metal muhafazada oluşturduğu
yüzey akımının bir aralık ya da conta üzerinden dışarı sızmasıdır. Ölçüm noktası hücrenin
**dışıdır** — yani montaj için hücreyi açmak bile gerekmez.

* Kapasitif plaka, ön panel üzerinde bir birleşim yerine (kapı contası, panel ek yeri)
  yakın konumlandırılır.
* 3–30 MHz bant geçiren, aynı AD8318 logaritmik dedektörüne bir RF anahtarla girer.
* **Bağımsız bir ölçüm ilkesi değildir** — HFCT ile aynı fiziksel olayı farklı bir yoldan
  görür — ama farklı bir gürültü ortamındadır, bu yüzden ikinci bir aile olarak sayılabilir
  mi sorusu, saha ölçümüyle cevaplanmalıdır. Şu an için **RF ailesinin içinde** sayıyoruz.

### 2.3 40 kHz ultrasonik alıcı

Hava yoluyla yayılan ultrason, yalnız **yüzey** deşarjını duyar; kapalı bir boşluk
deşarfını duymaz (ses metal muhafazadan çıkamaz). Bu bir sınırlama değil, bir **ayırt
edici**dir:

| Kanal | Ne duyar |
|---|---|
| HFCT | İç boşluk **ve** yüzey deşarjı |
| Ultrasonik | **Yalnız** yüzey deşarjı ve korona |
| İkisi birlikte | HFCT var + ultrason yok → **iç** kusur (daha ciddi). İkisi de var → **yüzey** kusuru (nem/kirlenme, temizlenebilir) |

Alıcı (Murata MA40S4R), kapı contası hizasına, bölmenin dışından bakacak biçimde
konumlandırılır.

### 2.4 θ — OG'de de çalışır

AG'de bulduğumuz şeyin OG'ye taşınmayan bir tarafı yoktur: **üç kablo başlığı, üç özdeş
kardeştir.** Aynı akımı taşır, aynı havadadır, aynı yaştadır, aynı yüzeyi gösterir.

```
θ_i = [ T_i − medyan(diğer iki başlık) ] / (I / I_ref)²
```

Isıl kelepçe, kablo başlığının gövdesine (stres konisinin **altına**, kablo kılıfının
üzerine) oturur. Akım, hücrenin kendi koruma akım trafolarından ya da röleden okunabilir —
AG'nin aksine OG hücrelerinde **her fider zaten CT'lidir**. Bu, AG'deki en büyük
eksikliğimizi (çıkışta CT yokluğu) ortadan kaldırır ve 34 pabuçtaki "orantısal pay
kestirimi" sorunu OG'de hiç doğmaz.

**Bara bağlantıları için ise ısıl kanal yoktur**, çünkü kapalı bölmedeler ve bir IR
penceresi olmadan görülmezler. IR penceresi sonradan takmak, iç ark sınıflandırılmış bir
muhafazada bir **tip testi sorusudur** (§4) ve konsept bunu iddia etmez.

---

## 3. Düğüm tasarımı

AG düğümlerinden en önemli farkı: **şebekeden beslenir.**

| Özellik | AG düğümü | OG düğümü |
|---|---|---|
| Besleme | Birincil Li-SOCl₂ hücre, 9–16 yıl | Hücrenin **mevcut yardımcı beslemesi** (230 V AC ya da 48 V DC) |
| PD kayıt kadansı | Günde 1 × 60 s (pil bütçesi) | **Sürekli**, ya da dakikada bir 10 s |
| Analog zincir | Yalnız kayıt sırasında enerjili | Sürekli enerjili |
| Haberleşme | 868 MHz sub-GHz | RS-485 ya da Ethernet (hücre panosunda zaten kablo yolu var) |
| Ortam | SHT41 | SHT41 — **OG'de nem daha kritik** (yüzey kaçağı kablo başlığında başlar) |

Pil kısıtının kalkması, OG'de PD izlemenin AG'dekinden **niteliksel olarak daha güçlü**
olmasını sağlar: sürekli PRPD, kayan 30 günlük eğilim, olay tetiklemeli tam dalga biçimi
yakalama.

Sunucu tarafı **aynıdır**: aynı kanal kütüğü, aynı zarf, aynı PRPD sınıflandırıcı, aynı
füzyon motoru, aynı SCADA haritası. OG hücresi, `contracts/assets.py` içine yeni bir varlık
tipi olarak girer; dedektörde tek satır değişmez.

---

## 4. Montaj, mesafeler ve **IEC 62271-200 iç ark farkındalığı**

Bu bölüm konseptin en ciddi kısmıdır ve hafife alınmamalıdır.

### 4.1 İç ark sınıflandırması ne demektir

Bir OG hücresi, IEC 62271-200'e göre **IAC** (Internal Arc Classification) ile tip testine
tabi tutulur; örneğin `IAC AFLR 20 kA 1 s`. Test, kapalı bir hacimde başlatılan bir arkın
üreteceği basıncın **basınç tahliye kanatlarından** yönlendirilmesini ve muhafazanın
açılmamasını, dışarıya sıcak gaz ve parça savurmamasını doğrular.

**Bu hacme eklenen her nesne bu sertifikayı sorgulanır kılar.** Somut riskler:

| Risk | Sonuç |
|---|---|
| Eklenen nesne **mermi** hâline gelir | Ark basıncı 400 g'lık bir gövdeyi hızlandırır |
| Basınç tahliye yolunu **kısmen kapatır** | Basınç düşürme süresi uzar, muhafaza açılır |
| Bir **ark bariyeri** görevi gören bölmeye monte edilir | Bariyerin bütünlüğü bozulur |
| Kablosu tahliye kanadının menteşesine takılır | Kanat açılmaz |

### 4.2 Konseptin kuralları

| # | Kural | Gerekçe |
|---:|---|---|
| 1 | Düğüm ve HFCT'ler **yalnız topraklanmış hacimde** durur; hiçbir parça faz potansiyeline yaklaşmaz | Yalıtım mesafeleri korunur |
| 2 | Herhangi bir gerilim altındaki parçaya **≥ 320 mm** (36 kV) mesafe; imalatçının kendi mesafe tablosu daha büyükse **o** geçerlidir | Sertifikalı mesafeye dokunulmaz |
| 3 | Tekil nesne kütlesi **≤ 400 g**; toplam eklenen kütle **≤ 2 kg** | Mermi riski |
| 4 | Sabitleme **esirdir** (captive): toprak barasına M8 cıvata + emniyet somunu; **mıknatıs kaide OG'de kullanılmaz** | AG'de mıknatıs yeterlidir, OG'de değil |
| 5 | Hiçbir parça **basınç tahliye yolunda ya da bir kanadın süpürme hacminde** olmaz | Tahliye engellenemez |
| 6 | Kablolar toprak barası boyunca, tahliye yollarından uzakta, alev geciktirici (IEC 60332-1) kılıfla | Ark sonrası yangın yayılımı |
| 7 | HFCT ayrılabilir olmalı ve **topraklama örgüsü kesilmeden** takılmalı | Topraklama iletkeni kesilemez |
| 8 | Montaj **yalnız** topraklama ayırıcısı kapalı ve kilitlenmişken | Kesinti planı gerekir |
| 9 | İmalatçıdan **IAC sertifikasının geçerliliğini teyit eden yazılı görüş** alınmadan seri montaj yapılmaz | §6 M3 |

**Kural 9 pazarlık konusu değildir.** AG tarafında Madde 3.1 yorumu bizim yorumumuzdu
([05] §9.1); OG tarafında yorum yapmaya hakkımız yok, çünkü sonucu bir yaralanma olabilir.

### 4.3 LSC ve bölmeleme

Hücre `LSC2B` sınıfındaysa kablo bölmesi, bara bölmesi enerjiliyken erişilebilirdir ve bu,
montaj planını **çok** kolaylaştırır. `LSC1` ise tüm hücrenin enerjisiz olması gerekir.
Bu, hangi hücre tiplerinin sahada olduğuna bağlıdır ve **bilmiyoruz** (§6 M1).

---

## 5. Maliyet

> **VARSAYIM (etiketli):** [03] §9'daki fiyatlandırma yaklaşımının aynısı; gösterge
> dağıtıcı liste fiyatı, Eylül 2026.

| Kalem | Parça | 1000 adet | Not |
|---|---|---:|---|
| 3 × HFCT, 50 mm, ayrılabilir (**özel, nanokristal**) | özel | €186.00 | 3 × €62 |
| — alternatif: 3 × katalog HFCT50 | Techimp HFCT50 | €2 340.00 | Kalibre, izlenebilir; **8 kat pahalı** |
| MV-NODE kartı (analog + MCU + Ethernet/RS-485, şebeke beslemeli) | özel | €165.00 | AD8318 zinciri PD-01 ile aynı |
| TEV plakası | kart üzeri | €0.00 | Gövdeye entegre |
| Ultrasonik alıcı | Murata MA40S4R | €3.20 | |
| Sıcaklık/nem | SHT41-AD1B | €2.60 | |
| 3 × ısıl kelepçe (θ, kablo başlıkları) | PANOGOZ-TC-A1 | €88.95 | 3 × €29.65 |
| Muhafaza, esir sabitleme, kablaj, alev geciktirici kılıf | — | €38.00 | |
| Montaj + test | EMS | €18.00 | |
| **HÜCRE BAŞINA DONANIM (özel HFCT ile)** | | **€501.75** | |
| **HÜCRE BAŞINA DONANIM (katalog HFCT50 ile)** | | **€2 655.75** | |

**Kurulum:** planlı kesinti gerektirir, 2 kişi × 3 saat = 6 kişi-saat × €22 = €132, artı
kesinti koordinasyonu. **Kesintinin kendisi maliyet kalemidir ve dağıtım şirketinin
planına biner** — bu yüzden OG montajı, **zaten planlanmış bir bakım penceresine**
eklenmelidir. Ayrı bir kesinti talep eden bir izleme projesi kabul görmez.

Karşılaştırma: AG modülü €470.59 (1000 adet). OG hücresi özel HFCT ile benzer mertebede,
katalog HFCT50 ile beş katıdır. **Kalibre, izlenebilir bir HFCT'nin gerekip gerekmediği,
bu konseptin tek büyük maliyet sorusudur** ve cevabı §6 M1'e bağlıdır: dağıtım şirketi
sonucu bir **eğilim** olarak mı kullanacak (özel HFCT yeter), yoksa mutlak pC değeri
üzerinden bir kabul ölçütü mü uygulayacak (katalog + kalibrasyon şart)?

---

## 6. Dağıtımdan önce doğrulanması gerekenler

Bu liste, konseptin **ürün olmadan önce** cevaplanması gereken kısmıdır. Hiçbiri bizim
cevaplayabileceğimiz bir soru değildir.

| # | Doğrulanacak | Neden kritik | Kim cevaplar |
|---:|---|---|---|
| **M1** | **Sahadaki OG hücre tipleri**: gerilim (24/36 kV), yalıtım (hava/SF₆), LSC sınıfı, IAC sınıfı, imalatçı ve model | Her mesafe, her montaj noktası, her sertifika sorusu buna bağlı. **Çizim istendi, alınamadı** | DSO |
| **M2** | Kablo bölmesinin topraklama ayırıcısıyla emniyete alınıp alınamayacağı ve iş kurallarının buna izin verip vermediği | Montajın mümkün olup olmadığı | DSO iş güvenliği |
| **M3** | **İmalatçının, eklenen ekipmanla IAC sertifikasının geçerliliğini yazılı teyidi** | §4.2 Kural 9. Teyit yoksa seri montaj **yapılmaz** | Hücre imalatçısı |
| **M4** | HFCT50'nin pC cinsinden transfer duyarlılığı (kalibratörle) | Sağlanan veri sayfasında **yok**; şiddet eşikleri buna dayanır | Laboratuvar |
| **M5** | Hücre yardımcı beslemesinin varlığı, gerilimi ve yedek kapasitesi | Düğümün şebekeden beslenmesi konseptin temeli | DSO |
| **M6** | Dağıtım merkezi RF gürültü tabanı (komşu hücreler, OG şebekesi, sürücüler) | Gürültü tabanı yüksekse üç HFCT'li varış zamanı kapılaması **zorunlu** hâle gelir, opsiyonel değil | Saha ölçümü |
| **M7** | IR penceresi var mı, sonradan takılabilir mi | Bara bağlantılarının ısıl kanalı buna bağlı. IAC'li muhafazaya pencere açmak bir **tip testi** sorusudur | DSO + imalatçı |
| **M8** | PD ölçümünün hangi standarda göre raporlanacağı | On-site HFCT ölçümü **IEC 60270 izlenebilir değildir**; IEC 62478 (elektromanyetik/akustik yöntemler) kapsamındadır ve saha koşullarında görünür yük kalibrasyonu sağlamaz. Kabul ölçütü bu farkı bilmelidir | DSO + laboratuvar |
| **M9** | Kesinti planlamasına eklenebilirlik | Ayrı kesinti isteyen bir izleme projesi kabul görmez | DSO bakım planlama |

---

## 7. Bu konseptin AG teslimine etkisi: yok

Açıkça söylemek gerekir: **OG konsepti, AG teslimini hiçbir şekilde etkilemez.** Sunucu
tarafı, kanal kütüğü, dedektör, kurallar, SCADA haritası ve arayüz aynen çalışır; OG
hücresi eklendiğinde `contracts/assets.py` içine yeni bir varlık tipi girer ve `sim/`
altına yeni bir üreteç eklenir.

Bunun sebebi mimarinin varlık-agnostik olmasıdır: θ üç kardeş ister, PRPD bir faz referansı
ister, füzyon kanıt ister. Hiçbiri "bu bir AG panosu" varsayımına dayanmaz.

---

## 8. Belgelendi, kodlanmadı

| Konu | Durum |
|---|---|
| OG hücre çizimi ve tip bilgisi | **Verilmedi**; istendi |
| MV-NODE donanımı | Konsept; şematik yok, prototip yok |
| OG varlık modeli (`assets.py` içinde) | Yok; AG panosu için yazıldı |
| OG için PRPD sınıf parametreleri | AG için ayarlanmış parametreler kullanılabilir ama **OG'de doğrulanmadı** |
| Üç HFCT'li varış zamanı kapılaması | Fizik doğru; algoritma yazılmadı |
| HFCT50 kalibrasyonu | Yapılmadı; veri sayfasında duyarlılık yok |
| IAC sertifikası etkisi | **İmalatçı teyidi alınmadı** — bu belgede tek başına en riskli açık madde |
| Maliyet | Gösterge; tedarikçi teyidi yok |
