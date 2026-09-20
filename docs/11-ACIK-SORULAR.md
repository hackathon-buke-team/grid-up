# 11 · Açık Sorular

Yalnız müşterinin cevaplayabileceği sorular. Her biri için: **neden önemli**, **cevabına
göre tasarım nasıl değişir**, **kim cevaplar** ve **şimdilik ne varsaydık**.

Bu listeyi yazmamızın sebebi, cevapları bilmiyor görünmek değil — cevapları
**uydurmamış** olmak. Aşağıdaki her soru için bir varsayım yaptık; hepsi kodda ve
belgelerde etiketlidir. Bir tanesi bile "muhtemelen böyledir" diye sessizce ürüne
gömülmedi.

| Öncelik | Sorular |
|---|---|
| **ENGELLEYİCİ** — cevaplanmadan saha montajı yapılamaz | S4, S5, S13 |
| **YÜKSEK** — kapsamı ve maliyeti doğrudan değiştirir | S1, S2, S3, S6, S7 |
| **ORTA** — modeli ve entegrasyonu etkiler | S8, S9, S10, S11, S12 |
| **OG hattı** | [10-MV-HUCRE-KONSEPTI.md] §6, M1–M9 |

---

## ENGELLEYİCİ

### S4 · Pano enerjiliyken RS-485 iletkeni indirmeye DSO iş kuralları izin veriyor mu?

**Neden önemli.** Kurulum prosedürünün 9. adımı ([05] §3), ağ geçidinden TVOC-2 ve
MPR-53CS'e birer çift bükümlü çift indirmeyi gerektirir. Bu, alt kablo bölmesi ve ölçü
kolonu arasında, **pano enerjiliyken** yapılan bir iletken indirme işidir. Panonun AG giriş
kesicisi olmadığı için enerjisiz yapmak, dağıtım merkezini karartmak demektir
([05] §1.1).

**Cevaba göre tasarım.**

| Cevap | Sonuç |
|---|---|
| **İzin var** (uygun PPE ve iş izniyle) | Tam kapsam: analizör + ark rölesi kanalları 1. günde çalışır. Kurulum 2.5 saat |
| **İzin yok** | 9. adım **planlı bir kesintiye ertelenir**. Sistem RS-485 olmadan da çalışır ama: (a) yük faktörü yalnız 6 kelepçe CT'sinden gelir, 34 IR pabucu için orantısal pay kestirimi **yapılamaz**; (b) ark rölesi durumu okunamaz, `ARC_STATE.NOT_FITTED` görünür; (c) THD, nötr ayrıştırma ve şebeke olayı bastırması (`GRID_THD_3PH`) **devre dışı kalır** — bu, filo ölçeğinde en değerli bastırma kuralıdır |
| **Kısmen** (yalnız ölçü kolonu içinde) | TVOC-2 ve MPR-53CS ölçü kolonundaysa tam kapsam; değilse yukarıdaki kısıtlı hâl |

**Şimdilik varsaydık:** izin var, iş izni ve DSO PPE matrisiyle. Kod, RS-485'siz duruma
zaten düzgün düşer (`analyser_fitted=False`, `arc.fitted=False`) — yani yanlış varsayım
sistemi bozmaz, kapsamını daraltır.

**Kim cevaplar:** DSO iş güvenliği ve şebeke işletme müdürlüğü.

---

### S5 · Geçerli bir IEEE 1584 (ya da eşdeğer) ark-flaş olay enerjisi etüdü var mı?

**Neden önemli.** Enerjili bir panonun içinde çalışılacaktır. Kişisel koruyucu donanım
seviyesini olay enerjisi belirler ve olay enerjisini yalnız dağıtım şirketinin kendi etüdü
bilir: kaynak empedansı, koruma açma süresi, çalışma mesafesi ve muhafaza geometrisine
bağlıdır.

**Bu belgede hiçbir cal/cm² sayısı yoktur ve bu bilinçlidir** ([05] §1.2). Bir tedarikçinin
müşterinin tesisi için olay enerjisi belirlemesi tehlikeli bir davranıştır.

**Cevaba göre tasarım.**

| Cevap | Sonuç |
|---|---|
| **Etüt var** | PPE matrisi etütten okunur, montaj planlanır |
| **Etüt yok** | **Montaj bekler.** Bunu biz belirlemeyiz ve "muhtemelen düşük seviyedir" demeyiz |
| Etüt var ama bu pano tipi kapsam dışı | Etüdün genişletilmesi, projenin ön koşulu olur |

**Şimdilik varsaydık:** hiçbir şey. Bu, cevabını varsaymadığımız tek sorudur.

**Kim cevaplar:** DSO iş güvenliği.

---

### S13 · Hizmetteki bir panoya ekipman montajı için bir DSO iç prosedürü var mı?

**Neden önemli.** **TEDAŞ-MLZ/2003-06.B'nin hiçbir maddesi, hizmetteki bir panoya sonradan
ekipman takılmasından bahsetmez.** Şartname bir panonun **imalatını ve kabulünü** yönetir;
sahadaki bir panoya retrofit yapılmasını ne yasaklar ne izin verir — konuyu hiç ele almaz.

Madde 3.1'i "yalnız etkilenen doğrulamalar yeniden koşturulur" biçiminde uygulamak ve
gerçekçi olarak 10.10 (sıcaklık artışı) ile 10.12 (EMC) ile sınırlamak **bizim
yorumumuzdur** ([05] §9) ve bir yorum olduğunu söylüyoruz.

**Cevaba göre tasarım.**

| Cevap | Sonuç |
|---|---|
| Prosedür var | Ona uyulur; test kapsamı prosedürden okunur |
| Prosedür yok, DSO yazacak | Projenin gerçek başlangıç noktası budur. Teknik olan her şey çözülebilir; bu çözülmezse **hiçbir şey monte edilemez** |
| DSO retrofit'i kabul etmiyor | Ürün, yalnız **yeni imal edilen** panolara fabrikada takılan bir seçenek hâline gelir. Bu tamamen farklı bir iş modelidir ve maliyet modeli ([07]) baştan yazılır |

**Şimdilik varsaydık:** DSO bir iç prosedür yazacak ve 10.10 + 10.12 tip testleri
bütçelenecek (€22 500, [07] §2.3).

**Kim cevaplar:** DSO varlık yönetimi + TEDAŞ ile mutabakat.

---

## YÜKSEK ÖNCELİK

### S1 · Filodaki panolarda Madde 2.2.8.1.iv anten çıkışı (gland) fiilen var mı?

**Neden önemli.** Madde 2.2.8.1.iv, haberleşme üniteleri için bir bölme **ve mühürlü dış
anten çıkışı** şart koşar. Ancak bu, alıcının sipariş anındaki talebine bağlı olarak
sağlanan bir özelliktir; şartnamede olması, sahadaki her panoda bulunduğu anlamına gelmez.

**Cevaba göre tasarım.**

| Cevap | Sonuç | Etki |
|---|---|---|
| Gland var | Anten 4 dakikada dışarı alınır | Baz senaryo |
| Gland yok, açılabilir | IP2X doğrulaması (10.3) yeniden koşturulmalı — test kapsamı **genişler** | Tip testi maliyeti artar |
| Gland yok, açılamaz | LTE anteni kabin içinde kalır: tipik **12–20 dB** kayıp. Zayıf kapsama alanındaki dağıtım merkezlerinde bağlantı kaybedilir | Filonun bir kısmı Ethernet/fiber ister ya da kapsam dışı kalır |

**Şimdilik varsaydık:** filonun çoğunluğunda gland var; kutuda hem dış hem iç anten
seçeneği gidiyor.

**Kim cevaplar:** DSO varlık kaydı; ya da 20 panoluk bir fotoğraf örneklemesi.

---

### S2 · Panoların yüzde kaçında ABB TVOC-2 var, olanların yüzde kaçında COM modülü takılı?

**Neden önemli.** Ark koruma bütünlüğü, yedi arıza modundan biridir (%15 ağırlık) ve
`ARC_STATE` register'ının tamamı buna bağlıdır. Üstelik TVOC-2 **kendi haberleşmesinin
koptuğunu bildiremez** — o biti biz üretiriz ve bu, ICD'nin en değerli iki bitinden biridir.

COM modülü olmayan bir TVOC-2, koruma yapar ama **okunamaz**.

**Cevaba göre tasarım.**

| Cevap | Sonuç |
|---|---|
| Çoğunda var + COM takılı | Tam kapsam. `arc_detectors_missing`, `arc_selftest_days`, `arc_ambient_warn` kanıtları çalışır |
| Var ama COM yok | `ARC_STATE.NOT_FITTED` kurulur ve ekranda **öyle yazar**. COM modülü eklemek bir maliyet kalemi olur (indikatif €250/pano) |
| Yok | `arc_integrity` modu yalnız "takılı değil" kanıtıyla çalışır ve bu bir **öneri** üretir: bu panoya ark koruma ekleyin |

**Ek uyarı — kodda zaten var:** register 222/223 (dedektör sağlığı) **yalnız X2 ve X3
kartlarını** kapsar. 20 dedektörlü bir röle (X1 + X2) ekranda **10/10** gösterir, 20/20
değil; X1'in on dedektörünün sağlığı **görülemez**. Bu, hem sim hem poller tarafında
`x1_covered=False` ile taşınır ve arayüzde yazılmalıdır. Ayrıca reg 222/223/224/225 yalnız
**FW ≥ 03.00.00**'da vardır.

**Şimdilik varsaydık:** filonun %65'inde TVOC-2 var (`sim/fleet.py`:
`NO_ARC_RELAY_FRACTION = 0.35`), dedektör sayısı 10/20/30 karışımı.

**Kim cevaplar:** DSO varlık kaydı.

---

### S3 · Panoların yüzde kaçı Madde 2.2.11 **seçenek 1** (RS-485'li analizör), yüzde kaçı **seçenek 2** (elektronik sayaç + 3 ampermetre)?

**Neden önemli.** Bu, cevabı en çok şeyi değiştiren sorudur. Seçenek 2'de panoda **hiç
Modbus yoktur**: elektronik sayaç ve üç analog ampermetre vardır.

**Cevaba göre tasarım.**

| Cevap | Kaybedilen | Sonuç |
|---|---|---|
| Seçenek 1 (MPR-53CS + RS-485) | — | Tam kapsam |
| Seçenek 2 (sayaç + ampermetre) | Faz akımları, gerilimler, THD, frekans, nötr akımı, cos φ | (a) 34 IR pabucu için **yük faktörü kestirilemez** — orantısal pay hesabının girdisi yok; (b) `GRID_THD_3PH` bastırması **çalışmaz** (filo ölçeğinde en değerli kural); (c) `GRID_FREQUENCY` bastırması çalışmaz; (d) nötr kuralı H3 çalışmaz; (e) PRPD'nin akım fazı referansı için cos φ okunamaz |

**Seçenek 2 için telafi:** ağ geçidine bir **ek 3 fazlı enerji analizörü** takmak
(indikatif €180 + DIN ray yeri + ölçü akım trafolarına erişim). Bu, ölçü devresine
girmeyi gerektirir ve **kendi başına bir tip test sorusudur**; kolay bir telafi değildir.
Alternatif: yalnız 6 kelepçe CT'siyle çalışmak ve 34 IR pabucunu "yük bilinmiyor" olarak
işaretlemek — ürün çalışır, kapsamı daralır.

**Şimdilik varsaydık:** filonun %88'i seçenek 1 (`sim/fleet.py`:
`NO_ANALYSER_FRACTION = 0.12`).

**Kim cevaplar:** DSO varlık kaydı.

---

### S6 · ABB, register 213 otokontrolü sırasında ark korumasının **devre dışı kalmadığını** yazılı olarak teyit ediyor mu?

**Neden önemli.** TVOC-2 register 213 "perform diagnostics" komutudur ve **yalnız
yazılabilir** bir register'dır (okumaya teşebbüs exception 02 verir). ABB'nin Modbus
kılavuzu, tanılama çalışırken ark korumasının **inhibe olup olmadığını söylemiyor.**

Eğer inhibe oluyorsa ve biz bunu uzaktan tetikliyorsak, **koruma penceresini biz
kapatmış oluruz**. Bir arkın tam o anda oluşma olasılığı düşüktür; sonucu kabul edilemez.

**Cevaba göre tasarım.**

| Cevap | Sonuç |
|---|---|
| **Yazılı teyit: inhibe olmuyor** | Otokontrol, planlı bir pencerede uzaktan tetiklenebilir; `SELFTEST_DUE` bayrağı otomatik kapatılabilir |
| Teyit yok ya da inhibe oluyor | **Mevcut varsayılan davranış:** otokontrol **devre dışıdır** (`ARC_STATE.SELFTEST_DISABLED` biti sürekli kuruludur). Sistem yalnız *"son otokontrolden beri N gün geçti"* der ve bir insanın, sahada, bilinçli olarak tetiklemesini önerir. Yazma yolu ağ geçidinde operatör kimlik doğrulaması **ve fiziksel anahtar** arkasındadır |

**Şimdilik varsaydık:** teyit yok → otokontrol devre dışı. Kodda `SELFTEST_DISABLED`
varsayılan olarak kuruludur ve ICD'de "ABB yazılı teyidi alınana kadar varsayılan" notuyla
belgelidir.

**Kim cevaplar:** ABB Türkiye teknik destek, yazılı.

---

### S7 · TS EN 61439-1 **Çizelge 8**'in sayısal sıcaklık artışı limitleri nedir?

**Neden önemli.** TEDAŞ şartnamesi sıcaklık artışı için TS EN 61439-1'e atıf yapar; standart
ise bara **cıvatalı bağlantısı** için sayısal bir limit **koymaz** — erişilebilir yüzeyler,
terminaller ve el ile kumanda organları için Çizelge 8'e, baralar için "komşu parçalara
zarar vermeme" ölçütüne bırakır. **Çizelge 8 sağlanan belgelerde yoktu.**

Bu yüzden PANO GÖZ'ün mutlak limitleri (**110 °C kritik / 130 °C acil**) bir standart
alıntısı değil, **mühendislik çıkarımıdır** ([04] §8.2): 105 °C sınıfı kablo yalıtımının
uzun süreli sınırı, kalayın **232 °C** erime noktası ve bakır oksidasyon hızının 120 °C
üzerinde belirginleşmesi bir arada değerlendirilmiştir.

**Cevaba göre tasarım.** Çizelge 8'in gerçek değerleri geldiğinde `detector/engine.py`
içindeki `T_JOINT_KRITIK_C` ve `T_JOINT_ACIL_C` sabitleri **tek satırda** değişir. Şiddet
merdiveninin θ tarafı etkilenmez (o zaten IR termografi pratiğine dayanır).

**Şimdilik varsaydık:** 110 / 130 °C, **etiketli çıkarım olarak**.

**Kim cevaplar:** DSO ya da TSE — standart metnine erişim.

---

## ORTA ÖNCELİK

### S8 · DSO hangi bakım yönetim sistemini (CMMS/EAM) kullanıyor?

**Neden önemli.** PANO GÖZ iki tür iş emri üretir ve bunları **ayrı** tutar: PANO iş emri
(bağlantıyı sık) ve CİHAZ iş emri (sensörü yerine oturt). Bu ayrım, sistemin uzun vadede
güvenilir kalmasının anahtarıdır ([05] §8.2). Ancak iş emirlerinin **DSO'nun kendi
sisteminde** açılması gerekir; bizim ekranımızda kalırsa hiçbir ekip görmez.

**Cevaba göre tasarım.** SAP PM, IBM Maximo, Infor EAM ya da yerli bir çözüm — her biri
farklı bir entegrasyon (REST, IDoc, dosya, veritabanı görünümü). Entegrasyon maliyeti
[07] §6'da **fiyatlandırılmamıştır**, çünkü hedef sistem bilinmiyor.

**Şimdilik varsaydık:** hiçbir şey; PANO GÖZ kendi alarm konsolunu ve REST API'sini sunar,
entegrasyon ayrı bir kalem olarak durur.

**Kim cevaplar:** DSO bilgi işlem.

---

### S9 · Sağlanan çalışma kitabındaki **iki farklı sensör tarifinden** hangisi kastediliyor?

**Neden önemli.** `İstenen Veriler.xlsx` → `Akım Sensörü` sayfası, aynı sütunlar için **iki
çelişkili tarif** taşır:

| Satır | Tarif | İma ettiği ölçek |
|---|---|---|
| 2 | *"Sekonderi 125 mA Olan Akım Sensörü"* + *"125 mA karşılığı 5 A"* | 40:1 ara CT; TEDAŞ 2500/5 ile kaskat → **20 000:1 = 20.0 A/mA** |
| 4 | *"Sekonderi 100 mA, primeri değişken olmakla beraber elimizdeki 600 A"* | 6000:1 |
| 7+ (formül) | `=600000/100` = 6000 | **6.0 A/mA** |

Üç okuma birbirini tutmuyor. Fark **3.33 kattır**. Üstelik 125 mA × 6.0 = **750 A**'dir,
belirtilen 600 A tam ölçek değil.

**Cevaba göre tasarım.** Bir ara akım trafosunun oranı, ölçülen her akımın ölçeğini
belirler; yanlış oran her θ paydasını yanlış yapar. Ancak **bu, sağlanan verinin sahte
olması nedeniyle şu an sonuç değiştirmiyor** (README §6: lag-1 ACF = +0.0003, χ² p = 0.446
ve dört kanıt daha). Biz kendi kelepçemizin CT'sini kullanıyoruz ve oranını kendimiz
belirliyoruz (3000:1, [03] §1.1), dolayısıyla bu belirsizlik ürüne girmiyor.

Yine de sormak gerekir: **organizatörler hangisini kastetti?** Cevap, veri setinin nasıl
yorumlanmasını istediklerini gösterir.

**Ek not:** `Sıcaklık_Nem` sayfası **tamamen boştur.** Hiç sıcaklık ya da nem verisi
verilmemiştir. Bu bir eksiklik mi, yoksa "bu veriyi siz üretin" anlamına mı geliyor?

**Şimdilik varsaydık:** sağlanan veri sentetiktir ve model kalibrasyonu için
kullanılmamalıdır; kendi fizik tabanlı ikizimizi kurduk.

**Kim cevaplar:** organizasyon komitesi.

---

### S9b · DSO'nun iş emri planlama ufku kaç gündür?

**Neden önemli.** "Eşiğe kalan gün" projeksiyonunun iki sayısı bu cevaba bağlıdır
([04] §6.1): 90 günlük **ufuk tavanı** ve 14 günlük **geçmiş kapısı**. Tavanın gerekçesi
istatistikseldir (21 günlük pencereden daha uzun bir tarih türetmek ekstrapolasyondur),
fakat *hangi* uzunluğun operasyonel olarak anlamlı olduğunu yalnız planlama süreci bilir.

**Cevaba göre tasarım.**

| Cevap | Sonuç |
|---|---|
| **Haftalık çizelge** (ufuk ~14 gün) | Tavan 30 güne inebilir; 30 günün ötesi "uzak" diye tek kelimeyle raporlanır ve kolon çok daha sakin olur |
| **Aylık planlama** (ufuk ~90 gün) | Mevcut tavan doğrudur, değişiklik gerekmez |
| **Yıllık bütçe / bakım kampanyası** | Tavan yükseltilemez: 21 günlük pencere daha uzun bir tarihi taşımaz. Bunun yerine **mevsimsel** bir model gerekir ve o model ancak bir yıllık saha geçmişiyle kalibre edilebilir |

**Şimdilik varsaydık:** aylık planlama, tavan 90 gün. Yanlış varsayım sistemi bozmaz,
kolonun işe yararlığını azaltır.

**Kim cevaplar:** DSO varlık yönetimi / bakım planlama.

---

### S10 · Filodaki MPR-53CS'lerin haberleşme ayarları nedir?

**Neden önemli.** MPR-53CS'in baud oranı enum'u **terstir** (1 = 38400, 2 = 19200,
3 = 9600, 4 = 4800, 5 = 2400) ve sahada 9600 ile 38400 arasında herhangi bir yerde
olabilir; parite de değişkendir. Ayrıca **CT oranı register 32769'da tutulur ve bu register
primer akımı değil ORANI taşır** (2500/5 → 500). Yanlış bir CT oranı tüm akımları
ölçekler ve bunu fark etmek zordur.

**Cevaba göre tasarım.** Ağ geçidi, kelime sırasını (`ABCD/CDAB/BADC/DCBA`) **frekans
register'ından otomatik tespit eder** — 50 Hz, makul aralığı en dar olan ve dolayısıyla
en güvenli değerdir. Baud/parite taraması ise devreye almada yapılır ve doğrulama
listesinin 10. maddesidir ([05] §6). Yani cevap bilinmese de sistem çalışır; bilinmesi
devreye almayı hızlandırır.

**Şimdilik varsaydık:** otomatik tespit; CT oranı 500 beklenir ve farklıysa
`CONFIG_MISMATCH` bayrağı kurulur.

**Kim cevaplar:** DSO ölçüm ekibi ya da devreye alma taraması.

---

### S11 · `mpr.p_total_w` neyi göstermeli: net mi, yalnız ithal mi?

**Neden önemli.** Kanal kütüğü bu kanalın kaynağını "MPR-53CS reg 46" olarak belgeliyor;
register haritası ise reg 44'ü **ithal**, reg 46'yı **ihraç** aktif güç olarak veriyor.
Kanal aralığı işaretlidir (−3×10⁶ … +3×10⁶ W), dolayısıyla ağ geçidi bunu **net**
(reg 44 − reg 46) olarak yayınlıyor — iki kaynağı da tutan tek okuma budur.

**Cevaba göre tasarım.** Yalnız ithal isteniyorsa **tek satırlık** bir değişiklik. Hiçbir
tespit kuralı bu kanala dayanmıyor; yalnız arayüzde gösteriliyor.

**Şimdilik varsaydık:** net güç.

**Kim cevaplar:** DSO ölçüm ekibi / Entes dokümantasyonu.

---

### S12 · "En kötü ondalık" sıralaması için hangi veri var?

**Neden önemli.** [07] §4.3'ün tüm sonucu buna dayanır: aynı 100 modül, tekdüze
dağıtıldığında **parasını geri ödemez**, en kötü ondalığa konduğunda **2.2 yılda** döner.
Ama "en kötü ondalık" bir varsayımdır (V18: olay hızı çarpanı ×4.0) ve sıralamayı yapacak
veri **DSO'dadır**: arıza kaydı, pano yaşı, yük faktörü geçmişi, son termografi raporu.

**Cevaba göre tasarım.**

| Cevap | Sonuç |
|---|---|
| Veri var ve çarpıklık ×4 civarında | Pilot en kötü ondalığa yerleştirilir, 2.2 yıl geri ödeme |
| Veri var ama çarpıklık düşük (×1.4'ün altında) | Hedefleme avantajı kaybolur; pilot 175 panonun altında ekonomik olmaz ([07] §5) |
| Veri yok | Pilot **tekdüze** dağıtılmak zorunda kalır ve ilk yıl kendi sıralama verisini üretir. Bu savunulabilir ama geri ödeme 6.9 yıla çıkar |

**Şimdilik varsaydık:** V11 (%1.2/pano/yıl) ve V18 (×4.0), ikisi de **etiketli varsayım**.
Sağlanan veri kümesi bu konuda hiçbir şey söylemez.

**Kim cevaplar:** DSO varlık yönetimi + arıza kayıt sistemi.

---

## Ek: bizim kendi doğrulama borçlarımız

Bunlar müşteri sorusu değil, **bizim ölçmediğimiz** şeylerdir. Aynı listede dururlar, çünkü
aynı dürüstlük kuralına tabidirler.

| # | Doğrulanacak | Şimdiki durum | Etki |
|---:|---|---|---|
| D1 | Pil akımlarının tezgâhta ölçülmesi | Veri sayfası akımlarından hesaplandı | B1 TC 721 gün hesabı ölçülmedi; IR/PD toplam görev bütçesi açık |
| D2 | Split-core CT'nin komşu faz kaçak akısı altındaki hatası | ±%1.5 tahmin | θ'nın paydası |
| D3 | HFCT analog zincirinin kazanç, gürültü ve 50 Hz bastırma ölçümü | Hesaplandı | RF kanalının anlamlılığı |
| D4 | MLX90640 geniş açı lensin sahada 10 çıkışı kapsaması | Optik hesap | 34 IR pabucunun kapsamı |
| D5 | Mıknatıs kaidenin titreşim altında kayma testi | Yapılmadı | `MOUNT_LOST` hızı |
| D6 | TimescaleDB üzerinde başarım ölçümü | **Sürücü yazılmadı**; SQLite'ta ölçüldü, Timescale rakamları yayınlanmış veriden | [06] §2.3 |
| D7 | 10 000 panoluk yük testi | En büyük ölçülen filo 112 pano | [06] §5 |
| D8 | EMC ön uyum taraması | Önlem listesi var, tarama yok | [03] §8 |
| D9 | Saha güvenilirlik verisi (MTBSV) | Parça sayımı kestirimi | [05] §8.5 |
| D10 | Özel HFCT (nanokristal, 30 mm) tasarımı ve kalibrasyonu | BOM'da var, tasarlanmadı | [03] §9.3 |
| D11 | Ufuk projeksiyonunun gerçek isabeti | Güven aralığı kapsaması simülasyonda ölçüldü (nominal %90'a karşı %88-93); saha isabeti etiketli geçmiş ister | [04] §6.1.2 |

---

## Kapanış

On dört müşteri sorusu, on bir doğrulama borcu ve dokuz OG sorusu. Otuz dört açık madde.

Bunu bir zayıflık olarak sunmuyoruz. Bir hackathon teslimi ile sahaya çıkabilir bir ürün
arasındaki fark tam olarak bu listedir; ve bu listeyi **yazmayan** bir teslim, listenin
olmadığını değil, listenin **görülmediğini** gösterir.

Otuz iki maddenin **yalnız üçü engelleyicidir** (S4, S5, S13) ve üçü de teknik değil,
**kurumsal** sorulardır: iş kuralları, iş güvenliği etüdü ve retrofit prosedürü. Teknik
olan her şey ya çözülmüştür ya da ölçüm bekliyor.
