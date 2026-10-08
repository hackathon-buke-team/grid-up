# PANO GÖZ · Sunum Metni ve Hazırlık Kılavuzu

**ADM & GDZ Elektrik · Grid Up Hackathon · Takım Büke**
Pano/Hücre İçi Anomali Erken Uyarı Sistemi

Bu belge sunumu yapan kişi içindir. Ezberlenmez, **okunur ve prova edilir**. İçinde projenin
tamamı var: bizden ne istendiği, bize ne verildiği, ne kurduğumuz, neyi neden kullandığımız,
slayt slayt ne söyleneceği, canlı demonun tıklama tıklama akışı ve jürinin sorabileceği sorular.

| Dosya | Ne için |
|---|---|
| [`PANO-GOZ-Final-Sunumu.pdf`](PANO-GOZ-Final-Sunumu.pdf) | Jüriye teslim edilen PDF (23 sayfa) |
| [`index.html`](index.html) | Sunumda açılan canlı deste. **N** konuşma metni · **S** konuşmacı ekranı · **O** slayt haritası · **Q** jüri soruları · **F** tam ekran · **B** karart |
| `.\baslat.ps1` | Canlı demo (aşağıda §8) |
| [`scada_kanit.py`](scada_kanit.py) | Demodaki SCADA kanıtı: blok okuma + reddedilen yazma |

---

## İçindekiler

0. [Tek sayfada: üç mesaj, süre, ezber](#0-tek-sayfada-üç-mesaj-süre-ezber)
1. [Proje neydi, bizden ne istendi?](#1-proje-neydi-bizden-ne-istendi)
2. [Bize verilen veriler ve onlarla ne yaptık](#2-bize-verilen-veriler-ve-onlarla-ne-yaptık)
3. [Çözümümüz: PANO GÖZ](#3-çözümümüz-pano-göz)
4. [Ne kullandık: teknoloji yığını](#4-ne-kullandık-teknoloji-yığını)
5. [Rakamlarla proje](#5-rakamlarla-proje)
6. [Sunum akışı ve süre planları](#6-sunum-akışı-ve-süre-planları)
7. [Slayt slayt konuşma metni](#7-slayt-slayt-konuşma-metni)
8. [Canlı demo: adım adım](#8-canlı-demo-adım-adım)
9. [Jüri soruları ve hazır cevaplar](#9-jüri-soruları-ve-hazır-cevaplar)
10. [Söylenmeyecekler: dürüst sınırlar](#10-söylenmeyecekler-dürüst-sınırlar)
11. [Ezber kartı](#11-ezber-kartı)
12. [Sunum günü kontrol listesi](#12-sunum-günü-kontrol-listesi)

---

## 0. Tek sayfada: üç mesaj, süre, ezber

**Tek cümle:** PANO GÖZ, 1600 kVA'lık bir TEDAŞ AG dağıtım panosunda gevşeyen bağlantıyı,
ısınan nötrü, nemi ve ark korumasının sağlığını arıza olmadan, haftalar önce, **tarihiyle ve
kalan süresiyle** haber veren uçtan uca izleme sistemidir. **Sıcaklığa değil, kardeşine göre
farka bakar.**

**Jürinin aklında kalması gereken üç şey (kapanışta da bunları söylüyoruz):**

1. **θ**: Bir bağlantının kendi kardeş fazlarına göre fazla ısısı, anma akımına normalize
   edilmiş hâli. Yükten ve mevsimden bağımsız. Montaj gününden itibaren çalışır.
2. **Bastırma**: Yüz panoyu yönetilebilir kılan şey ürettiğimiz alarmlar değil,
   **üretmediğimiz** alarmların gerekçeli listesi.
3. **Dürüstlük**: Kör olduğumuz yeri, gecikmenin bir aralık olduğunu ve verinin neyi
   ölçemediğini ekranda söylüyoruz.

**Son cümle:** "Soru kaç pano alacağınız değil, **hangi** panolara koyacağınız."

**Süre:** Tam akış ≈ 16 dk slayt + 5 dk demo = **21 dk**. Süre sınırı daha kısaysa §6'daki
15 ve 10 dakikalık planları kullanın.

**Demo komutu (sunumdan 5 dk önce):** `.\baslat.ps1 -Panels 24 -BackfillDays 45 -Reset`
Neden 24 pano olduğu §8.1'de; kısaca: varsayılan 112 pano bu bilgisayarda yetişemiyor.

---

## 1. Proje neydi, bizden ne istendi?

### 1.1 Yarışma ve problem

ADM ve GDZ Elektrik'in **Grid Up Hackathon**'unda konu: **"Pano/Hücre İçi Anomali Erken Uyarı
Sistemi"**. Şartnamenin problem tanımı özetle şu:

> OG hücreleri ve AG panolarda meydana gelen arızaların önemli bir bölümü; sıcaklık artışı,
> nem, aşırı akım, izolasyon zayıflığı ve kısmi deşarj gibi belirtilerle kritik arıza
> gerçekleşmeden **önce sinyal verebilmektedir**. Ancak mevcut yapılarda bu belirtilerin
> **birlikte ve sürekli** takip edilmesi sınırlıdır. Birçok durumda problem, ekipman arızası,
> enerji kesintisi veya yangın riski ortaya çıktıktan **sonra** fark edilmektedir.

**Amaç:** Pano veya hücre içindeki olağandışı durumların erken fark edilmesini ve ilgili
ekiplerin kritik bir arıza olmadan önce bilgilendirilmesini sağlayacak bir sistem yaklaşımı.

### 1.2 Sahadan gelen ihtiyaçlar (şartname, 7 madde)

1. Pano ve hücre içindeki anormal sıcaklık ve akım değişimlerinin erken tespiti
2. Nem ve çevresel koşulların takibi
3. Kablo akımı ile ortam ve yüzey sıcaklığının **birlikte** değerlendirilmesi
4. Kısmi deşarj ve benzeri erken arıza belirtilerinin izlenmesi
5. Ark flaşlarının izlenmesiyle pano ve trafo yangını riskinin önceden fark edilmesi
6. Sahadaki verinin merkezi operasyon sistemlerine aktarılması
7. Kritik durumlarda saha ve operasyon ekiplerinin otomatik bilgilendirilmesi

### 1.3 Challenge'ın zor tarafı

Şartname açıkça şu tuzakları koyuyor, ve çözümümüzün yarısı bunlara cevap:

- **Pano kalabalık:** Kablo yığını var; eklenecek kontrol ünitesi ve sensörler kaosu artırabilir.
- **Çift yönlü risk:** Şebeke kablolamasındaki çalışma sensöre zarar verebilir; sensör
  çalışması da şebeke bağlantılarına zarar verebilir.
- **Hayati risk ve planlı kesinti:** Kontrol ünitesindeki ufak bir çalışma bile hem hayati
  risk taşır hem de planlı kesinti gerektirir.
- **Mission critical:** Kurulum sırasında ve sonrasındaki tüm hatalar ve etkileri
  düşünülmeli. Örnek olarak **kablosuz, tak-çalıştır, bakım gerektirmeyen** bir sistem isteniyor.

**Bizim cevabımız:** Kit yalnız alt kablo bölmesine, ölçü kolonuna ve mevcut 10 A prize
dokunur. Delik delinmez, tip testli parça değişmez, bara bölmesine girilmez. Sensörler
kablosuz (868 MHz) ve pillidir. Kesinti gerekmez (§3.15).

### 1.4 Cevaplamamız beklenen sorular ve cevaplarımız

| Şartnamenin sorusu | Bizim cevabımız (tek satır) | Nerede |
|---|---|---|
| Hangi operasyonel ve çevresel veriler takip edilmeli? | Bağlantı yüzey sıcaklığı + kendi akımı (kelepçe), 48 pabucun termal görüntüsü, bölme havası ve nem, RF/TEV/ultrasonik, analizörden faz akım-gerilim-THD, ark rölesinden açma ve dedektör durumu | Slayt 6–7 |
| Normal ve anormal nasıl ayrışır? | Mutlak sıcaklık değil θ: kardeş fazlara göre fark, yüke normalize. Hava ve yük sadeleşir | Slayt 4–5 |
| Kritik durumdan önce nasıl tespit edilir? | Günlük θ medyanı üzerinde CUSUM + değişim noktası (başlangıç tarihi) + Theil-Sen eğimi (eşiğe kalan gün) | Slayt 9–10 |
| Saha verisi merkeze nasıl aktarılır? | 868 MHz → ağ geçidi → MQTT 5 / TLS / QoS 1, store-and-forward, 20 000 çerçeve tampon | Slayt 8 |
| Anlık durum, anomali ve alarm nasıl izlenir? | Filo haritası, dijital ikiz, kanıt, bastırılan alarmlar, PRPD, SCADA ekranları | Demo |
| Kritik durumda hangi otomatik aksiyon ve bildirim? | 5 basamaklı seviye merdiveni; yalnız Kritik ve Acil telefon çaldırır; SMS + onay kodu + eskalasyon | Slayt 14 |
| Gerçek sahada nasıl uygulanır ve yönetilir? | 2 kişi, 2,5 saat, kesintisiz kurulum; telefonla devreye alma; iki ayrı iş emri türü | Slayt 17 |
| Farklı sahalara ölçeklenir mi, maliyet sürdürülebilir mi? | 1000 pano tek düğüm; modül €470,59; en kötü %10'a konursa 2,2 yılda geri öder | Slayt 18–19 |
| Yüksek/düşük sıcaklık ve manyetik alan dikkate alındı mı? | −25…+70 °C, IP65, konformal kaplama; bara yüzeyi ~14,5 mT hesaplandı, kitin hiçbir parçası orada değil | Slayt 7 |

### 1.5 Beklenen teknik çıktılar ve durumumuz

| # | Şartname çıktısı | Durum | Ne teslim ettik |
|---|---|---|---|
| 1 | Kabin içi fiziksel modül / prototip tasarımı (1600 kVA pano çizimleriyle) | **Kısmen** | 9 cihazlık kit, EK-II/14 çizim koordinatlarına göre montaj yerleşimi, TEDAŞ madde eşlemesi, BOM. KiCad çizilmedi |
| 2 | Elektronik tasarım dokümantasyonu (PCB, I/O, bağlantı şeması) | **Kısmen** | Blok şema, I/O tabloları, konnektör pin dizilimleri, katman yığını, güç ağacı, BOM (docs/03). KiCad şematik/PCB yok |
| 3 | Yazılım mimarisi (MCU kaynak kodu, akış diyagramı, frontend) | **Tamam** | C99 firmware + akış diyagramı (firmware/AKIS-DIYAGRAMI.md) + Python sunucu + saf JS arayüz |
| 4 | Monitoring + SCADA Modbus haritalama + on-premise + SMS/WhatsApp | **Tamam / Kısmen** | Monitoring, Modbus TCP slave ve on-premise tamam. SMS **kısmen**: merdiven, onay kodu ve fırtına tavanı çalışıyor, gönderim simüle. WhatsApp yok |
| 5 | Ölçeklenebilirlik (≥ 100 modül) ve kaynak kullanımı | **Tamam** | 112 pano ile ölçüldü; 100 / 1000 / 10 000 pano kaynak profili (docs/06) |
| 6 | On-premise, Public Cloud yok | **Tamam** | Tek komut, internet yok, dış servis çağrısı yok |
| 7 | Alarm ve acil bildirim mekanizması | **Kısmen** | Kodlu ve testli; gerçek bir kanaldan mesaj gitmedi |

### 1.6 Final sunumunda gösterilmesi beklenenler ve karşılığı

| Şartname | Sunumdaki karşılığı |
|---|---|
| Fiziksel modül veya çalışan prototip | Slayt 6–7 (kit, kartlar, firmware) + canlı dijital ikiz |
| Uçtan uca veri akışı | Slayt 8 + demoda canlı WebSocket akışı |
| Monitoring / SCADA ekranları | Demo: Filo, Pano, Kanıt, Alarmlar, SCADA + `scada_kanit.py` |
| Normal ve anormal senaryolar | Demo: SOKE-14 gevşek bağlantı (anormal) + TURGUTLU-02 şebeke olayı (negatif kontrol) |
| Alarm ve bildirim mekanizması | Demo: ark olayı → ACİL alarm → SMS + sesli arama (simüle) |
| Sistem mimarisi | Slayt 8 |
| Saha uygulaması ve ölçekleme | Slayt 17–19 |

### 1.7 Değerlendirme kriterleri: hangi an hangi kriteri karşılıyor

| Kriter | En güçlü anımız |
|---|---|
| Problemin doğru anlaşılması | Slayt 3–4: arıza önce ısınır; sabit eşik ağustosa göre kurulur, şubatta kördür |
| Anomali ve risk tespit yaklaşımı | Slayt 5 (θ) + 9–10 (CUSUM, değişim noktası, eşiğe kalan gün) |
| Saha koşullarında uygulanabilirlik | Slayt 6 ve 17: delik yok, bara bölmesi yok, kesinti yok, telefonla devreye alma |
| Uçtan uca sistem | Slayt 8 + canlı demo |
| Mevcut sistemlerle entegrasyon | Slayt 15 + demoda canlı Modbus okuma, reddedilen yazma |
| Ölçeklenebilirlik | Slayt 18 |
| Kullanıcı / operasyon deneyimi | Demoda bastırılan alarmlar ekranı ve seviye merdiveni |
| Maliyet ve fayda | Slayt 19: önce kötü haber, sonra 2,2 yıl |
| Yenilikçilik | θ + görünürlük tabanı + "susma sözleşmesi" (yetersiz geçmişte sayı vermemek) |

### 1.8 Şartnamenin kısıtları (lehimize olanlar)

- Fiziksel sensör satın almak veya gerçek panoya kurulum yapmak **beklenmiyor**.
- Sistem **örnek veya sentetik veriyle** gösterilebilir; akım, gerilim, anahtarlama simüle edilebilir.
- RTU/SCADA entegrasyonu için **Modbus haritalamasını göstermek yeterli**; gerçek saha sistemine bağlanmak beklenmiyor.
- Tüm veri kaynaklarını kullanmak zorunlu değil; hangisinin anlamlı olduğuna takım karar verir.

---

## 2. Bize verilen veriler ve onlarla ne yaptık

Yarışmada `Hackathon Verileri` klasöründe dokuz dosya verildi. Her birinin projede karşılığı var:

| Dosya | Ne | Onunla ne yaptık |
|---|---|---|
| `1600kVA AG Pano Teknik Özellikleri.pdf` | Şartnamenin EK-I/8 donanım listesi (Tablo 8) | 1600 kVA sütunu: ana bara 2×(100×10 mm²) kalaylı bakır, giriş akım trafosu **2500/5** (yalnız girişte, çıkışlarda CT yok), 250/400 A DSYA çıkışlar + yedek yollar, DSYA terminal aralığı 185 mm, iç ihtiyaç 6 A gG. Kelepçelerin kendi CT'sini taşıması, Ç6/Ç7 seçimi ve manyetik alan hesabı (185 mm faz adımı) buradan. 2312 A, 1600 kVA'nın 400 V'taki anma akımıdır |
| `AG Pano Teknik Çizim-1600kVA.pdf` | EK-II/14 kesit çizimi | Dijital ikizin geometrisi: 12 yol, **74 cıvatalı bağlantı**, montaj koordinatları (`contracts/assets.py`) |
| `AG PANO MALZEME ŞARTNAMESİ.pdf` | TEDAŞ-MLZ/2003-06.B | Her montaj yüzeyini bir maddeye bağladık: galvaniz sac (2.2.1.vi) → mıknatıslı termal dizi; M12 topraklama saplaması (2.2.6.2.iii) → PD-01; 10 A priz (2.2.12) → ağ geçidi beslemesi; AG giriş kesicisi yok (2.2.10.2.vi) → bara bölmesine girilmez. Ortam zarfı (Tablo 1: dahili maks. 40 °C, min. −5 °C) yoğuşma modeline girdi |
| `1SFC170017M0201_Rev_D_TVOC-2_Modbus_Manual.pdf` + `tvoc.pdf` | ABB TVOC-2 ark rölesi kılavuzları | Register haritasını kılavuza sadık kurduk: reg 1300 sistem durumu, 222/223 dedektör sağlığı, 213 yalnız-yazılır, log delikleri, "0x0000 = aktif hata yok" tuzağı (`sim/tvoc.py`) |
| `MPR-53CS_Modbus_Register_Map_EN.pdf` | Entes enerji analizörü register haritası | Faz akımları, gerilimler, THD, CT oranı register'ı (`sim/mpr.py`) |
| `DS_HFCT30_eng.pdf` | Techimp HFCT30 veri sayfası | PD-01'in HFCT'si için referans; 1–3 MHz yüksek geçiren seçimi bu veri sayfasından |
| `DS_HFCT50_eng.pdf` | Techimp HFCT50 veri sayfası | OG hücre konseptinde kablo ekranı topraklamasına (docs/10) |
| `İstenen Veriler.xlsx` | "Örnek veri" | Analiz ettik: **sentetik**. Ayrıntı aşağıda |

### 2.1 `İstenen Veriler.xlsx`: veri sentetik, ve bunu sayıyla gösterdik

Dört sayfadan yalnız biri sayı taşıyor:

| Sayfa | İçerik |
|---|---|
| `Akım Sensörü` | 15 dakika aralıklı **152 satır** akım değeri (mA). B1 hücresinde zaten "Sentetik Data" yazıyor |
| `ARC` | Tek cümle: "ABB TVOC-2 verilerinden Modbus ile okunarak alınacaktır". Veri değil, yönlendirme. Biz de öyle yaptık |
| `PD` | Üç satır: `DS_HFCT30`, "ÇALIŞMA MANTIĞI", bir başlık. Yine yönlendirme |
| `Sıcaklık_Nem` | **Tamamen boş** |

Akım sayfasına altı bağımsız test uyguladık. Hepsi aynı şeyi söylüyor: bu, Excel'in
`=RASTGELEARADA(15;90)` fonksiyonuyla üretilmiş düzgün dağılımlı gürültüyle uyumlu.

| Test | Ölçülen | Gerçek bir fiderde beklenen |
|---|---:|---|
| Lag-1 otokorelasyon | **+0,0003** | > +0,97 |
| var(fark) / var(seri) | 2,0023 | ≪ 2 |
| Fazlalık basıklık | −1,2129 | ≈ 0 (−1,2 düzgün dağılım imzası) |
| KS testi, U(14,5; 90,5) | D = 0,0526 | 0,1101 kritik değerini aşmalı |
| χ², 76 tam sayı | p = 0,446 | reddedilmeli |
| Gün-üstü şekil korelasyonu | r = +0,0596 | > 0,85 |

Ek bulgular (sorulursa): n = 152, min 15, maks 90, ortalama 52,13. Saatlik ANOVA
F(23,128) = 1,375, p = 0,135; gerçek fiderde günün saati akımı belirler. Sayfa başlığı
"125 mA = 5 A" (40:1) der, formül 6,0 A/mA uygular; fark 3,33 kat. 125 mA × 6 = 750 A,
belirtilen 600 A tam ölçek değil. Bunu bir suçlama değil, entegrasyonda netleşecek bir
kalibrasyon sorusu olarak kaydettik.

**Bu veride olmayanlar, doğrudan bizim problemimiz:** sıcaklık ve nem yok (θ hesaplanamaz),
etiketli arıza geçmişi yok (yanlış alarm oranı hesaplanamaz), kardeş fazı yok, anomali yok
(pano anmasının %3,9–%23,4'ünde yaşıyor).

**Tasarıma yansıması:**

| Bulgu | Karar |
|---|---|
| Geçmiş ve eğitim kümesi yok | θ: montaj günü üç kardeş faz zaten referans. Geçmiş gerekmez |
| Sıcaklık/nem sayfası boş | Yoğuşma zincirini şartname Tablo 1'den ve Magnus–Tetens bağıntısından kurduk |
| Eşik kuralları bu veride çöker | Mutlak sıcaklık yalnız yedek kanal; birincil kanal yük-bağımsız θ |
| Düşük yükte görünürlük yok | `SENSITIVITY_LOW` birinci sınıf durum, ayrı raporlanır |
| Ölçek belirsizliği | Her kelepçede kendi split-core CT'si; analizörün CT oranı register'dan okunur |

**Ve en önemlisi:** Modeli bu veriye uydurmadık. Fizikten türetilmiş bir **dijital ikiz**
kurduk (17 senaryo, 7'si alarm üretmemesi gereken negatif kontrol), kabul kriterlerini ölçtük ve
verilen kümeyi de aynı testlerden geçirdik. **Bu paketteki hiçbir başarım sayısı saha
verisiyle doğrulanmış değil.** Gerçek yanlış alarm oranı ancak etiketli bir pilot sahada
ölçülür; bunu pilotun ölçeceği ilk şey olarak öneriyoruz.

**Ton:** "Verinizi yakaladık" değil. "Bunu ortaya çıkarmak bir başarı değil, sonuçlarını
dikkate almak bir zorunluluk."

---

## 3. Çözümümüz: PANO GÖZ

### 3.1 Tez

Her yarışmacı panoya bir termometre koyar ve bir eşiğin üstünde alarm üretir. Bu sahada
çalışmaz: bir bağlantının sıcaklığını **durumu değil, yükü ve mevsimi** belirler. Şubatta
09:00'da 62 °C okunan pabuç kusurludur; ağustosta 15:00'te tam yükte okunan aynı 62 °C
normaldir. Eşik ağustosu atlatacak kadar yüksek kurulmak zorundadır, dolayısıyla şubatta kördür.

PANO GÖZ bunun yerine **θ**'yı ölçer.

### 3.2 θ: kardeşine göre fark

```
θ_i = [ T_i − medyan(T_kardeşler) ] / (I / I_ref)²        birimi: kelvin
```

"Bu bağlantı anma akımını taşısaydı, kardeşlerinden ne kadar sıcak olurdu?"

- **Kardeş**: aynı fiderin üç fazı. Aynı akımı taşır, aynı havayı solur, 20 mm arayla durur, aynı yaştadır.
- **Medyan, bağlantının kendisi hariç** alınır. Kendini içeren medyan, kusurlu faz bir kardeşini geçtiği anda ona atlar ve sinyalin %40'ını yer.
- **Sadeleşenler:** yük (I² paydada), mevsim ve güneş (aynı hava), IR tarafında yayıcılık (aynı yüzey).
- **Örnek (slayt 5):** (71,90 − 69,05) / 0,67² = **6,35 K**, Uyarı. Hava dalgasında ölçülen θ kayması **0,0000 K**.
- **Yeni bir icat değil:** IR termografinin "benzer bileşene göre benzer yük altında ΔT" ölçütü. Fark: yılda bir müteahhit değil, dakikada bir sistem ölçüyor.

**"Geçmiş gerektirmez" cümlesinin kapsamı (yanlış anlaşılmasın):** Yalnız **kardeş
karşılaştırması** montaj günü çalışır. Haftalar önce haber veren sürüklenme yolu en az **5 gün**
günlük medyan ister; ileriye bakan "eşiğe kalan gün" 21 günlük pencerede en az **14 geçerli
gün** ister, yoksa `YETERSIZ_GECMIS` yazar.

**Kör noktası:** Üç faz birden ve aynı hızda bozulursa θ bunu görmez. Onu her koşulda açık
olan mutlak limitler (90 / 110 / 130 °C) kapsar.

### 3.3 Donanım: bir modül = bir pano = 9 cihaz

Şartname "en az 100 modül" der ama modülü tanımlamaz. Biz tanımladık:
**1 modül = 1 enstrümante pano = 9 cihaz.** Bu sayı kodda sabit (`DEVICES_PER_PANEL == 9`).

| # | Cihaz | İçinde | Nereye takılır | Hangi şartname maddesi izin veriyor |
|---|---|---|---|---|
| 1–6 | **TC ısıl kelepçe** ×6 | TMP117 (±0,1 °C) + kendi split-core CT'si | Çıkış 6 ve 7'nin üç fazı, kablo kılıfı üzerinde, pabuçtan 50–100 mm aşağıda | Alt kablo bölmesi tabanı açık (2.2.8.6), en az 400 mm |
| 7 | **TN-IR termal dizi** | MLX90640 32×24 + SHT41 | Bölme tabanına mıknatıslı kaide, yukarı bakar; 34 pabucu görür | Pano içi boyasız galvaniz sac (2.2.1.vi): mıknatıs tutar |
| 8 | **PD-01 RF ve ortam** | HFCT + TEV + 40 kHz ultrasonik + SHT41 | M12 topraklama saplaması; HFCT **yalnız PE** iletkenine | İki M12 topraklama terminali zorunlu (2.2.6.2.iii) |
| 9 | **GW-01 ağ geçidi** | STM32H563 + 868 MHz + LTE + 2× izole RS-485 | Ölçü kolonunda DIN ray, mevcut 10 A prizden beslenir | 10 A priz (2.2.12), haberleşme bölmesi ve dış anten (2.2.8.1.iv) |

- **Tek kural:** delik delinmez, tip testli parça değişmez, **bara bölmesine girilmez**. Çünkü
  panoda AG giriş kesicisi yok (2.2.10.2.vi); bara bölmesini enerjisiz yapmak bütün dağıtım
  merkezini OG tarafından karartmak demek.
- **Neden Çıkış 6 ve 7:** θ için en az üç kardeş gerekir (bir fiderin üç fazı). Bu iki yol
  400 A sınıfının en yüklü fiderleri; θ'nın görünürlüğü f² ile arttığı için en yüklü fider en
  görünür fiderdir.
- **Kalan 34 pabuç** yalnız termal dizi ile görülür ve kendi akımları yoktur (çıkışlarda dağıtım
  şirketinin CT'si yok, 2500/5 yalnız girişte). Yükleri analizörden orantısal pay ile
  **kestirilir** ve ekranda öyle etiketlenir.
- **74 bağlantı modellendi, 40'ı ölçülüyor.** Bara bölmesinin 30 ve çatının 4 bağlantısı
  izlenmez ve ekranda gridir: "Gri renk bir eksiklik değil, bir beyandır."
- Panoda **zaten bulunan** iki cihaz okunur: **ABB TVOC-2** ark rölesi ve **Entes MPR-53CS**
  enerji analizörü (RS-485 Modbus RTU).

### 3.4 Elektronik ve firmware

- **Dört kart:** PANOGOZ-TC-A1 (×6), IR-A1, PD-A1, GW-A1.
- **Sensör düğümleri STM32WLE5:** mikrodenetleyici ile 868 MHz radyo aynı yongada.
- **Neden 868 MHz, neden 2,4 GHz değil (kavite argümanı):** Sac kutunun güvenilir tek
  açıklığı tabandaki ≥ 400 mm boşluk. 868 MHz'in dalga boyu 345 mm, bu yarıktan kuplaj yapar;
  2,4 GHz'in 125 mm'si yapmaz ve kutunun içinde derin sıfırlar üretir. BLE yok.
- **Ağ geçidi STM32H563:** radyodan toplar, TVOC-2 ve MPR-53CS'i iki ayrı izole RS-485 hattından
  okur, LTE ile çıkar. Bağlantı koparsa **20 000 çerçeve** tamponlar; elektrik kesilirse
  süperkapasitörle **8 sn "son nefes"**.
- **Firmware C99:** float yok, malloc yok; θ kestiricisi uçta sabit noktada. "Pano enerjisiz"
  ve "pil zayıf" hata yolu değil, birinci sınıf durum.
- **Uyanma kadansı:** IDLE 900 s · WATCH 60 s · BURST 10 s.
- **Pil (hesap, tezgâh ölçümü değil):** kelepçe görev karması %97/2,5/0,5 ile ortalama
  8,89 µA → **13,1 yıl**; filonun en kısa ömürlü düğümü PD-01 ≈ **8,4 yıl**. Bant 8,4–16 yıl.
  Enerji hasadı iddia edilmiyor.
- **Çevre:** −25…+70 °C, IP65, yoğuşmalı nem için IPC-CC-830B kaplama. Bara yüzeyinde
  ~14,5 mT manyetik alan hesaplandı; kitin hiçbir parçası orada değil.
- **Modül donanımı:** **€470,59** (1000 adet) / **€660,91** (100 adet).

### 3.5 Uçtan uca mimari

```
Pano (9 cihaz)                      Dağıtım şirketi sunucu odası              Çıkışlar
TC ×6, TN-IR, PD-01 ─868 MHz─┐      ┌───────────────────────────┐   ┌─ İzleme arayüzü (REST + WebSocket 1 Hz)
TVOC-2, MPR-53CS ─RS-485─────┼─GW──►│ mesaj yolu → toplama →     │──►├─ SCADA / DMS (Modbus TCP, salt okunur)
                             │ yerel│ depo → dedektör → kurallar │   └─ Bildirim (SMS + sesli arama, onay kodu)
                             │kurallar└───────────────────────────┘
                             MQTT 5 · TLS · QoS 1 · store-and-forward
```

- **Ağ geçidi aptal bir köprü değil:** sunucu yolu kopsa bile üç kural yerelde çalışır:
  ≥ 90 °C, kardeş farkı ≥ 20 K, ark açması.
- **Store-and-forward:** bir çerçeve, broker'dan PUBACK gelene kadar tampondan silinmez.
- **Kamu bulutu yok:** ne hesaplama, ne depolama, ne bildirim. Gerekçe kurumsal (kritik
  altyapı verisi), teknik olarak da gerekmiyor (§3.14).
- **Her sayı tek yerde tanımlı:** ekrandaki değer ile SCADA register'ı aynı nesneden
  (`PanelLive`) üretilir, çelişemezler.
- **Tek yön:** sistemin hiçbir yerinde panoya komut veren bir yol yok.

### 3.6 Tespit zinciri

| Adım | Ne yapar | Birimi |
|---|---|---|
| Ölçüm | Dakikada bir T ve I | °C, A |
| Kardeş farkı | Medyan, kendisi hariç | K |
| θ kestirimi | Özyinelemeli en küçük kareler (RLS), ileri modelin içinden. Bağlantı bir ısıl kütle; dekonvolüsyon gürültüyü büyüttüğü için yapılmaz | K, anma akımında |
| Günlük medyan | Avlanan sinyal 0,2 K/hafta; doğru örnekleme adımı gün | K/gün |
| CUSUM | Sürüklenme var mı (k = 0,5, h = 8) | – |
| Değişim noktası | Bozulma ne zaman başladı (ikili bölütleme + BIC), aralıkla | tarih |
| Theil-Sen + Sen (1968) aralığı | Eğim ve bir sonraki basamağa kalan gün | K/hafta, gün |
| Bastırma | Okuma pano hakkında mı, hava/şebeke/yük/cihaz hakkında mı? | gerekçe |
| Füzyon | 7 arıza modu, tavanlı olabilirlik oranı | risk |
| Alarm | 3/5 gün debounce, %40 histerezis, iki sensör ailesi şartı | seviye |

**Yedi arıza modu ve ağırlıkları:** gevşek bağlantı 0,30 · aşırı yük 0,15 · ark koruma
bütünlüğü 0,15 · ısıl kaçış / soğutma 0,10 · harmonik nötr 0,10 · nem / yoğuşma 0,10 ·
yalıtım 0,10. Sağlık endeksi bunların ağırlıklı çarpımı; logaritması tam ayrışır:
"sağlık 67" dediğimizde eksik 33 puanın hangi moddan geldiği söylenebilir.

**Bilerek kullanmadıklarımız:** pano başına LSTM/otokodlayıcı (yavaş sürüklenmeyi öğrenir ve
yeniden üretir: avladığımız sinyale yapısal olarak kör; aylarca temiz geçmiş ister; 100 panoya
100 model), one-class SVM (kalibre skor yok), ham sıcaklıkta kümeleme (kümeler mevsimi bulur,
arızayı değil), tek karar olarak sabit eşik.

### 3.7 Haftalar önce: tarih ve ufuk

- **Geriye bakan yol:** CUSUM > 8 **ve** θ ≥ 5 K **ve** son 5 günün 3'ü → **Uyarı**, iş emri
  açılır, telefon çalmaz. θ ≥ 12 K ve ikinci bağımsız sensör ailesi hemfikir → **Kritik**, SMS.
- **Başlangıç tarihi:** CUSUM'dan değil (o gecikir), tüm seri üzerinde geriye dönük değişim
  noktası kestiriminden. **Aralık** olarak verilir; bozulma basamak değil rampa, kesin tarih
  sahte kesinlik olurdu.
- **İleri yön, "eşiğe kalan gün":** Eğimin güven aralığının iki ucuna bölünerek çıkar, örn.
  "ACİL'e ~15 gün (13–19)". İş emrini bu haftaya mı gelecek aya mı yazacağına karar vermeye
  yeter; kesinti planlamaya yetmez ve öyle sunulmaz.
- **Susma sözleşmesi:** 21 günde 14 geçerli gün yoksa sayı yok, `YETERSIZ_GECMIS`. "Sayı
  üretmek kolaydı; üretmemek ürünün kendisi."
- **Model doğrusal ve ekranda yazıyor.** Isıl kaçış süper-doğrusaldır; o modda sayı iyimserdir.
  Nominal %90 aralığın simülasyonda ölçülen kapsaması %88–93.

### 3.8 Görünürlük: kör olduğumuz yeri söyleriz

Bir kusur, yük faktörü f'te gözlenen farkı yalnız θ·f² kadar büyütür. Görülebilen en küçük θ:
**θ_min = 3σ / f²**. Kelepçe σ = 0,2 K, IR σ = 0,8 K. Gece 03:00, f = 0,18:
3 × 0,2 / 0,18² = **18,5 K**. f < 0,35'te durum "görünürlük düşük" olur, ayrı raporlanır,
SCADA'da STATUS_WORD bit 2. Mutlak limitler bu sırada da açık.

### 3.9 Bastırma: üretmediğimiz alarmlar

Her bastırma kuralı tek soruya cevap verir: **bu okuma pano hakkında mı, yoksa şebeke, hava,
yük ya da kendi cihazımız hakkında mı?** Gerekçeler Türkçe, sayılarıyla, kendi ekranında.

| Kod | Ne zaman | Ne yapar |
|---|---|---|
| `GRID_THD_3PH` | Üç fazın gerilim THD'si birlikte yükseldi | Kanıtı harmoniğin kendisi olan modlar kapanır (pano bir yüktür, kaynak değil) |
| `GRID_THD_3PH_CANDIDATE` | Aynı durum, ısıl bir bulgu varken | Isıl bulgu silinmez, bir kademe gerilir, **ekip vetolanmaz**: aynı ölçümü tesisteki bir sürücü/UPS de üretir |
| `LOAD_STEP` · `INRUSH` | Yük basamağı, trafo devreye alma | θ kararlı hâl içindir; 3τ askıya alınır |
| `SENSITIVITY_LOW` · `STALE` | Düşük yük, bayat veri | Pano arızası değil, durum |
| `DEVICE_MOUNT_LOST` · `DRIFT` | Kelepçe düştü, sensör kaydı | **Cihaz** iş emri; sağlam bağlantı asla sıktırılmaz |
| `LEARN_WEEK` | Montajdan sonraki ilk 7 gün | Taban toplanır; mutlak limitler yine açık |
| `NO_DISPATCH` | Tek sensör ailesi, 24 saat bekleme dolmadı | Alarm var ama telefon çalmaz; neden çalmadığı yazılı |

Sıcak hava dalgası örneği (slayt 12): ortam 41,2 °C, kırk bağlantının hepsi +6,1 K; 60 °C'lik
sabit eşik on üç alarm üretir, PANO GÖZ sıfır; θ değişimi **0,0000 K**.

### 3.10 Ark: koruma bizde değil

ABB TVOC-2 ışıktan kontağa ~1 ms'de, SIL-2 donanımda açar; bizi beklemez. Bizim işimiz
sonrasında başlar: **hangi dedektör** (örn. X2:3), **hangi röle** (K5), **ne zaman**, ve
nöbetçiye haber. Bildirim gecikmesi tek sayı değil, **4–13 s** aralığı:

| Adım | Süre |
|---|---|
| TVOC-2 ışık → kontak | ~1 ms |
| TVOC-2 Modbus görüntüsünün yenilenmesi | 0,2–2 s (ABB dokümante etmiyor, modellendi) |
| Ağ geçidi tarama | 1 s |
| Sunucu işleme | 0,3–2 s |
| SMS yolu | 2,5–8 s |

Register 222/223 yalnız X2 ve X3 kartlarını kapsar; X1'deki dedektörleri göremiyoruz ve ekranda
öyle yazıyor. Açmadan sonra pano enerjisizdir: AG'de giriş kesicisi yok.

### 3.11 Seviye merdiveni ve bildirim

| Seviye | θ | Ne olur |
|---|---|---|
| Bilgi | < 2 K | Kayıt |
| İzle | ≥ 2 K | Haftalık özet |
| Uyarı | ≥ 5 K | İş emri, planlı ziyaret |
| **Kritik** | ≥ 12 K | 7 gün içinde ziyaret, **SMS** |
| **Acil** | ≥ 25 K | Derhal ekip, **SMS + sesli arama** |

- **Yalnız Kritik ve Acil telefon çaldırır.** Bu bir ayar değil, kodda sözleşme
  (`DISPATCH_SEVERITIES`).
- Telefon çalmadan önce: **iki bağımsız sensör ailesi** hemfikir (örn. kelepçe + termal dizi) ve
  Kritik için **24 saat bekleme** (Acil muaf).
- SMS **UCS-2** (Türkçe karakter bozulmasın), iki parçaya sığar; örnek:
  `PANO GÖZ KRİTİK · SOKE-14 · Ç7·L2·pabuç θ=17.6K · bağlantıyı torkla · ACİL'e 15 g (13-19) · onay: TAMAM 1 0541`
- **Onay kodu** kişiye ve olaya bağlı, 4 hane; rotada olmayan biri onaylayamaz.
- **Eskalasyon:** onay gelmezse Acil'de 15, Kritik'te 45 dk sonra şef + sesli arama, sonra işletme müdürü.
- **Fırtına tavanı:** saatte en fazla 8 Kritik; **Acil muaf**.
- **Dürüst sınır:** GSM modem AT diyaloğu ve SMPP simüle, transkript kaydediliyor; gerçek
  kanaldan mesaj gitmedi. Sesli arama simülasyon. WhatsApp yok.

### 3.12 SCADA: Modbus haritalama

- **Çalışan Modbus TCP slave**, istisnasız **salt okunur**: FC 05/06/15/16 → exception 0x01.
- Her pano sabit, deliksiz **48 register**: taban adres **1000 + 48 × (n − 1)**.
  SOKE-14 (n = 14) → **1624**. SCADA mühendisi tek blok tanımlar, yüz kez kopyalar.
- Örnek: THETA_MAX ham 176, ölçek 0,1 → 17,6 K.
- En değerli iki register kaynak cihazların üretemediği ikisi: `STATUS_WORD` bit 8 (ark
  rölesiyle bağ koptu) ve `DATA_AGE_S` (blok ne kadar bayat).
- 100 panonun tamamı 4800 register; FC 03'ün 125 sınırı yüzünden **en az 39 istek**, ölçülen
  **19 ms**. 1 Hz'de SCADA'nın yaptığı 2 istek medyan 0,72 ms.
- ICD v2.0 belgesi ve CSV nokta listesi koddan üretilir. IEC 104 / OPC UA için nokta listesi
  var, sunucu yok.

### 3.13 On-premise

Uygulama sunucusu (4 vCPU / 16 GB / 500 GB NVMe) + sıcak yedek, Mosquitto broker, hedeflenen
TimescaleDB (bugün SQLite). Her ağ geçidi kendi X.509 sertifikasıyla bağlanır, ACL yalnız kendi
panosunun konusuna yayın izni verir. Demo tek komutla, internetsiz, Docker'sız çalışır.

### 3.14 Ölçek

| | 100 pano | 1 000 pano | 10 000 pano |
|---|---|---|---|
| Zarf / sn | 15 | 150 | 1 500 |
| Dedektör CPU | %2,2 çekirdek | %21,6 çekirdek | 2,2 çekirdek |
| Disk, kararlı hâl | 18 GB | 180 GB | 1,8 TB |
| Sunucu | 2 vCPU · 8 GB | 4 vCPU · 16 GB | bölge başına 4 düğüm |

Ölçülen en büyük filo **112 pano**; 10 000 kestirimdir. Ölçülenler: RLS güncellemesi 2,67 µs,
pano değerlendirmesi 12,95 ms, 112 panolu filo adımı 270 ms. Her panonun kendi kısa RS-485
hattı var; ölçekleme seri hatta değil broker'da olur. **Gerçek kısıtlar:** operatörün dikkati
(100 panoda haftada en fazla 3 telefon çaldıran alarm hedefi) ve kurulum kapasitesi (ekip-günü).

### 3.15 Saha uygulaması

- **2 kişi, 2,5 saat, kesinti yok** (ilk 5 kurulum 3,5–4 saat).
- **Güvenlik kapısı:** dokunmadan termal kamerayla tara; bir pabuç > 110 °C ise **dur**, montaj yapma.
- Sıra: 6 kelepçe (30 dk) → TN-IR nişan sihirbazı (20 dk) → PD-01 M12 (15 dk) → GW-01 DIN ray + priz (30 dk) → dizüstüsüz devreye alma (35 dk).
- **Dizüstüsüz devreye alma:** telefonla etiket OCR → NFC dokunuş → çizimde parmakla işaretle → otomatik doğrulama → test SMS'i.
- **RS-485 istisnası:** enerjili panoda iletken indirmek DSO kuralına bağlı; izin yoksa planlı kesintiye ertelenir, sistem RS-485'siz de çalışır.
- **7 gün öğrenme** (mutlak limitler açık). **Pano iş emri ≠ cihaz iş emri**, asla karışmaz.
- 100 modül = **25 ekip-günü**; 1000 modül = 4 ekiple 3 ay.

### 3.16 Maliyet ve fayda: önce kötü haber

| Senaryo | Sonuç |
|---|---|
| 100 pano, her panoya eşit | **6,9 yılda** geri öder; 5 yılda −€30 166. Başa baş 175 panoda |
| Aynı 100 modül, filonun **en kötü %10'una** | **2,2 yılda** geri öder; 5 yılda +€143 109 |
| 1000 pano, eşit dağıtım | **3,3 yıl** (öğrenme eğrisi donanımı %28,8 ucuzlatır) |

- Kurulum €150/modül; 100 pano 5 yıl TCO €154 591; tip testleri €22 500 tek seferlik.
- **Faydanın %43,5'i tespit oranından bağımsız:** termografi ziyareti pano başına yılda €130'dan
  €21,7'ye iner. DSO bunu kendi bakım bütçesinden doğrulayabilir.
- Varsayımlar (olay hızları, maliyetler) DSO kayıtlarıyla doğrulanmadı, hepsi etiketli
  (docs/07 §1). En kırılgan varsayım: arıza hızı %1,2/pano/yıl.

### 3.17 OG hücreler (sorulursa)

OG çizimi verilmedi; istedik. docs/10 jenerik 36 kV kablo bölmesi için konsept: HFCT50 kablo
ekranı topraklamasında, TEV, ultrasonik, kablo başlıklarında θ. Hücre başına ~€502 (özel HFCT)
/ ~€2 656 (katalog HFCT50). Montaj planlı bakım penceresine eklenir.

---

## 4. Ne kullandık: teknoloji yığını

| Katman | Kullandığımız | Neden |
|---|---|---|
| Uç düğüm MCU + radyo | STM32WLE5CC (MCU ve 868 MHz alıcı-verici tek yonga) | Tek yonga, düşük uyku akımı, kavite içinde çalışan bant |
| Ağ geçidi | STM32H563 · SX1262 · Quectel EC21-E LTE · 2× ADM2587E izole RS-485 · QSPI tampon · 2× 10 F süperkap | İki ayrı izole Modbus hattı, 20 000 çerçeve tampon, 8 sn son nefes |
| Sensörler | TMP117 (±0,1 °C), split-core CT 3000:1, MLX90640 32×24, SHT41, HFCT, TEV, MA40S4R 40 kHz | Fark ölçümü için kararlılık; mutlak doğruluk yalnız limitler için |
| Panoda mevcut | ABB TVOC-2 ark rölesi, Entes MPR-53CS analizör (Modbus RTU) | Yeni cihaz eklemeden ark ve elektriksel veri |
| Firmware | C99, sabit nokta, float yok, malloc yok; durum makinesi (COLD_START → SELF_TEST → PROVISION → döngü) | Öngörülebilir bellek ve enerji |
| Taşıma | MQTT 5 (paho-mqtt 2.1, Mosquitto), TLS, QoS 1, store-and-forward; demoda süreç-içi bus, tek ortam değişkeniyle MQTT | Dayanıklılık PUBACK'e dayanır; bu yüzden Sparkplug B değil |
| Sunucu | Python 3.11, FastAPI + Uvicorn (REST + WebSocket), pydantic | Tek süreçte tüm sistem: `python -m panogoz.run_local` |
| Depolama | SQLite, taşınabilir şema (`store/schema.sql`); hedef TimescaleDB (yazılmadı) | İnternetsiz, kurulumsuz demo |
| Saha protokolleri / SCADA | pymodbus 3.15: TVOC-2 ve MPR-53CS master'ı + SCADA Modbus TCP slave'i; ICD v2.0 koddan üretilir | Şartnamenin istediği Modbus haritalama |
| Tespit | RLS, CUSUM, değişim noktası (ikili bölütleme + BIC), Theil-Sen + Sen (1968) aralığı, Magnus–Tetens çiy noktası, tavanlı Naive Bayes füzyonu | Her çıktının birimi var: K, µΩ, gün |
| Sayısal ve analiz | numpy, scipy (KS, χ²), pandas + openpyxl (verilen xlsx), PyMuPDF + pypdf (çizim ve şartname çıkarımı), matplotlib | Veri analizi ve belge üretimi |
| Arayüz | Bağımlılıksız saf JavaScript (ES modülleri), kendi SVG Türkiye haritası, açık/koyu tema, WebSocket 1 Hz | İnternetsiz, framework'süz, ~7 900 satır |
| Bildirim | GSM modem AT / SMPP sürücüsü (simüle), UCS-2 SMS, onay jetonu, vardiya merdiveni, sesli arama (simüle) | On-premise kanal; bulut SMS servisi yok |
| Test | pytest, 172 test; gerileme testleri yaşanmış hataları kilitler; negatif kontroller gerçek boru hattından geçer | "Alarm yok" ile "dedektör yok" ayırt edilsin diye pozitif kontrol aynı koşumda |
| Simülasyon | Fizikten türetilmiş dijital ikiz: yük profili, ısıl model, 17 senaryo, TVOC-2/MPR-53CS register sunucuları, PRPD üreteci | Verilen veri sentetik ve eksik |
| Çalıştırma | `.\baslat.ps1` tek komut; Docker ve internet gerekmez; `docker-compose.yml` üretim topolojisi tarifidir | On-premise duruşun kanıtı |
| Sunum | Bağımlılıksız HTML deste, PDF (Chrome başsız baskı), Remotion ile video | Çevrimdışı açılır |

**Yapay zekâ / makine öğrenmesi:** Bilinçli olarak ürünün içinde yok (§3.6 ve §9). scikit-learn
yalnız değişim noktası ve kümeleme **denemelerinde** kullanıldı; kümelemenin arızayı değil
mevsimi bulduğunu bu denemelerde gördük.

---

## 5. Rakamlarla proje

| | |
|---|---|
| Python (sunucu, dedektör, dijital ikiz, analiz, testler) | ≈ 33 000 satır |
| C99 firmware | ≈ 4 500 satır |
| Arayüz (saf JS) | ≈ 7 900 satır |
| Otomatik test | 172 |
| Teknik belge | 11 + SCADA ICD (≈ 5 800 satır) |
| Senaryo | 17: 10 alarm üreten + 7 alarm üretmemesi gereken |
| Pano başına | 9 cihaz · 74 modellenen bağlantı · 40 ölçülen · 48 SCADA register'ı |
| Ölçülen en büyük filo | 112 pano |

**17 senaryo:** Gevşek bağlantı (yavaş), hızlı gevşeme, nötr gevşek, harmonik yüklenme, sürekli
aşırı yük, havalandırma tıkalı, yoğuşma, yüzen elektrot / mikro-ark, ark olayı, ark dedektörü
arızası **(alarm üretir)** · sensör takıldı, sensör kayması, düğüm sessiz, sıcak hava dalgası,
şebeke olayı, trafo devreye alma, pano enerjisiz **(alarm üretmemeli)**.

**Takım:** Melih Ekizce (İYTE, yüksek lisans), Mustafa Eren Işıktaşlı (YTÜ, yüksek lisans),
Serhat Özdemir (DEÜ), Mert Arı (BUÜ); dördü de Bilgisayar Mühendisliği. İş dört pakete
bölündü: donanım ve uç düğüm; sunucu, entegrasyon ve ölçek; izleme ekranları ve operasyon
deneyimi; bildirim, doğrulama ve sunum.

---

## 6. Sunum akışı ve süre planları

Jürinin süre sınırını öğrenince bir plan seçin. Slayt 12, 13 ve 15'in konusu (bastırma, ark,
SCADA) demoda canlı da gösterildiği için süre daraldığında **ilk kısalacaklar bunlardır**.

| # | Slayt | Tam | 15 dk | 10 dk |
|---:|---|---:|---:|---:|
| 1 | Kapak | 30 sn | 30 sn | 25 sn |
| 2 | Takım | 15 sn | 10 sn | atla (kapakta "Takım Büke" de) |
| 3 | Problem: arıza önce ısınır | 45 sn | 30 sn | 40 sn (3+4 birlikte) |
| 4 | Sabit eşik neden çalışmaz | 45 sn | 30 sn | ↑ |
| 5 | θ: kardeşine göre fark | 70 sn | 60 sn | 50 sn |
| 6 | Donanım: 9 cihaz | 60 sn | 45 sn | 30 sn |
| 7 | Elektronik ve firmware | 40 sn | 20 sn | atla |
| 8 | Uçtan uca mimari | 50 sn | 40 sn | 30 sn |
| 9 | Tespit zinciri | 50 sn | 30 sn | atla |
| 10 | Haftalar önce: tarih ve ufuk | 60 sn | 45 sn | 40 sn |
| 11 | Kör olduğumuz yer | 35 sn | 20 sn | atla (demoda tek cümle) |
| 12 | Bastırılmış alarmlar | 50 sn | atla → demo | atla → demo |
| 13 | Ark olayı | 45 sn | atla → demo | atla → demo |
| 14 | Seviye merdiveni ve bildirim | 50 sn | 40 sn | atla (demoda SMS) |
| 15 | SCADA: Modbus | 40 sn | atla → demo | atla → demo |
| 16 | **Canlı demo** | 5 dk | 5 dk | 4 dk |
| 17 | Saha uygulaması | 45 sn | 30 sn | atla |
| 18 | Ölçeklenebilirlik | 40 sn | 25 sn | atla |
| 19 | Maliyet ve fayda | 55 sn | 40 sn | 30 sn |
| 20 | Verilen veri ve dijital ikiz | 35 sn | 25 sn | atla |
| 21 | Yapmadıklarımız | 40 sn | 20 sn | atla |
| 22 | Şartname karşılığı | 30 sn | 15 sn | 15 sn |
| 23 | Kapanış | 30 sn | 25 sn | 20 sn |
| | **Toplam** | **≈ 21 dk** | **≈ 14,5 dk** | **≈ 9 dk** |

**Atlamak için:** canlı destede slayt numarasını yazıp **Enter** (örn. `16` Enter), ya da
**O** ile slayt haritası. Konuşmacı ekranı için **S** (ikinci monitörde; şimdiki slayt,
sıradaki, konuşma metni ve süre sayacı).

**Demonun yeri:** Destede demo 16. slaytta. Slayt 12–15'i atlıyorsanız 11'den sonra doğrudan
16'ya geçin (`16` Enter) ve demodan sonra 17 ile devam edin.

---

## 7. Slayt slayt konuşma metni

Her slayt için: **Ekranda** ne var, **Tıklama** (→ tuşu), **Söyle** (konuşma metni),
**Geçiş** (bir sonraki slayta köprü cümlesi), **Dikkat** (sorulursa, kaçınılacaklar).
**[→]** işareti, o noktada bir kez → tuşuna basılacağını gösterir.

> **Slaytlardaki demo sayıları hakkında:** Kapaktaki 17,6 K ve "ACİL'e ~15 gün (13–19)", slayt
> 10'daki 11 Eylül ve eğim, slayt 14'teki SMS ve slayt 15'teki register değerleri **3 Ekim**
> tarihli bir demo koşusundan alındı. Canlı sistem başka bir günde başka sayılar gösterir (8
> Ekim akşamı: θ 18,8 K, "ACİL'e 9 gün (7–13)"). Slaytta okurken "demo koşumuzda" deyin;
> demoda ise sayıları **ekrandan** okuyun. İkisinin farklı olması tutarsızlık değil:
> bozulma rampası koşunun yapıldığı güne göre ilerler.

---

### Slayt 1 · Kapak — ⏱ 30 sn

**Ekranda:** "PANO GÖZ" başlığı; sağda pano alt kablo bölmesinin termal görüntüsü, soldan sağa
bir tarama geçer ve tek bir pabuç (Ç7-L2) etiketlenir: θ = 17,6 K, Kritik.

**Söyle:**
> Merhaba, biz Takım Büke. ADM ve GDZ Elektrik'in Grid Up hackathon'unda "Pano/Hücre İçi
> Anomali Erken Uyarı Sistemi" problemini çalıştık. Ürünümüzün adı PANO GÖZ.
>
> Sağda gördüğünüz, 1600 kVA'lık bir TEDAŞ alçak gerilim dağıtım panosunun alt kablo bölmesi:
> on fider, kırk sekiz pabuç pozisyonu. Termal göz soldan sağa geçtiğinde pabuçların hepsi
> birbirine benziyor — biri hariç. Çıkış 7'nin L2 pabucu.
>
> Bu pabuç bugün yanmıyor. Ama kendi kardeş fazlarına göre, yüke göre düzeltildiğinde, demo
> koşumuzda 17,6 kelvin daha sıcak. Ve bu gidişle ACİL seviyesine yaklaşık on beş günü var.
>
> PANO GÖZ'ün işi tam olarak bu: arıza olmadan, haftalar önce o bağlantıyı bulmak, bozulmanın
> ne zaman başladığını ve ne kadar vaktimiz kaldığını söylemek. Tek cümlelik farkımız da şu:
> **sıcaklığa değil, kardeşine göre farka bakıyoruz.**

**Geçiş:** "Önce kim olduğumuzu bir cümleyle söyleyeyim."

**Dikkat:** 30 saniyeyi geçmeyin. "Biri hariç" cümlesini tarama bitip etiket çıktığında söyleyin.
Ezber: 1600 kVA · TEDAŞ-MLZ/2003-06.B · 48 pabuç pozisyonu · Ç7-L2.

---

### Slayt 2 · Takım — ⏱ 15 sn

**Söyle:**
> Takım Büke olarak dört kişiyiz ve dördümüz de Bilgisayar Mühendisliği okuyoruz: Melih Ekizce,
> İzmir Yüksek Teknoloji; Mustafa Eren Işıktaşlı, Yıldız Teknik; ikimiz yüksek lisanstayız.
> Serhat Özdemir, Dokuz Eylül; Mert Arı, Bursa Uludağ.
>
> İşi dört paralel pakete böldük: donanım ve uç düğüm; sunucu, entegrasyon ve ölçek; izleme
> ekranları ve operasyon deneyimi; bildirim, doğrulama ve sunum.

**Geçiş:** "Hemen problemin kendisine geçiyorum."

**Dikkat:** Uzun durmayın. Turuncu rozet yüksek lisansın sürdüğünü gösterir.

---

### Slayt 3 · Problem: arıza önce ısınır — ⏱ 45 sn

**Ekranda:** Bağlantı sıcaklığının zamanla üstel yükselen eğrisi: cıvata gevşer → ısınır →
oksitlenir → ark, yangın, kesinti. **Tıklama:** [→] ×2.

**Söyle:**
> Problemi şartnamenin kendi cümlesiyle başlatalım: OG hücre ve AG panolardaki arızaların
> önemli bir kısmı kritik andan önce sinyal veriyor — sıcaklık artışı, nem, aşırı akım, kısmi
> deşarj. Ama bu sinyaller birlikte ve sürekli izlenmiyor.
>
> En sık senaryo şu eğri: bir cıvatalı bağlantı gevşer, temas direnci artar. Bağlantı birkaç
> kelvin ısınır; kimse görmez. Isındıkça oksitlenir, oksitlendikçe direnci artar — süreç
> kendini besler. Sonunda ark, yangın, kesinti.
>
> **[→]** Bugün bu sürecin farkına buradan varılıyor: arıza olduğunda, müşteri karanlıkta
> kaldığında, bazen pano yandığında.
>
> **[→]** PANO GÖZ'ün hedefi ise eğrinin başı. Sıcaklık henüz tehlikeli değilken, sadece
> "kardeşlerinden farklı" olduğu anda. Aradaki fark haftalar — ve o haftalar bir arıza ekibi ile
> planlı bir tork iş emri arasındaki fark.

**Geçiş:** "Peki bu eğrinin başını bugün neden kimse yakalayamıyor? Çünkü herkesin ilk aklına
gelen çözüm sahada çalışmıyor."

**Dikkat:** Kırmızı "bugün" işaretinde bir an durun; jüri kendi sahasını düşünsün.

---

### Slayt 4 · Sabit eşik neden çalışmaz — ⏱ 45 sn

**Ekranda:** İki termometre: Şubat 09:00 yük %35 → 62 °C **Kusurlu**; Ağustos 15:00 yük %95 →
62 °C **Normal**. Sağda bir yıllık grafik ve "kör bölge". **Tıklama:** [→] ×2.

**Söyle:**
> Her yarışmacının ilk aklına gelen çözüm: panoya bir termometre koy, bir eşiğin üstünde alarm
> ver. Bu sahada çalışmaz. Nedeni şu iki termometrede.
>
> Şubat sabahı dokuzda, yüzde otuz beş yükte 62 derece okuyan bir pabuç kusurludur. Ağustos
> öğleden sonra, tam yükte okunan aynı 62 derece ise tamamen normaldir. Bir bağlantının
> sıcaklığını durumu değil, **yükü ve mevsimi** belirliyor.
>
> **[→]** Bir yıl boyunca aynı panoya bakalım. Yeşil sağlam pabuç, kırmızı kusurlu pabuç. Sabit
> eşiği ağustosta yanlış alarm üretmeyecek kadar yükseğe kurmak zorundasınız.
>
> **[→]** Sonuç: kasımdan nisana kadar kusurlu pabuç eşiğin altında kalıyor. Yılın neredeyse
> yarısında sistem kör. Eşiği düşürürseniz bu kez her yaz yüzlerce yanlış alarm gelir ve
> operatör sistemi üçüncü ayda kapatır.

**Geçiş:** "O hâlde sıcaklığın kendisine değil, başka bir şeye bakmamız gerekiyor."

**Dikkat:** Grafik şematik, ölçüm değil; sorulursa "fiziği anlatan bir çizim" deyin.
Ezber: "Eşik ağustosa göre kurulur, şubatta kördür."

---

### Slayt 5 · θ: kardeşine göre fark — ⏱ 70 sn

**Ekranda:** Formül; solda L1/L2/L3 üç termometre; animasyon kendini döndürür (~19 sn):
hava dalgası → yük artışı → yalnız L2 ısınır → yük değişse de θ sabit.

**Söyle:**
> Bizim cevabımız θ. Formül üstte: bir bağlantının sıcaklığından, kendi kardeşlerinin
> medyanını çıkarıyoruz ve sonucu anma akımına göre normalize ediyoruz — yani (I bölü I_ref)
> karesine bölüyoruz. Birimi kelvin: "bu bağlantı anma akımını taşısaydı, kardeşlerinden ne
> kadar sıcak olurdu?"
>
> Kardeş ne demek? Aynı fiderin üç fazı: aynı akımı taşıyorlar, aynı havayı soluyorlar, yirmi
> milimetre arayla duruyorlar, aynı yaştalar. Renkler TEDAŞ'ın kablo renkleri: L1 gri, L2
> siyah, L3 kahverengi.
>
> Animasyonu izleyelim:
> — Sıcak hava dalgası geliyor: üç faz birden 6,1 kelvin ısınıyor. Eşik sistemi burada alarm
> verirdi. θ ise kıpırdamıyor; çünkü hava üçüne birden aynı şeyi yapıyor ve fark sıfır kalıyor.
> — Yük artıyor: Joule ısısı üçünde de akımın karesiyle artıyor. Paydaya I² koyduğumuz için bu
> da sadeleşiyor.
> — Şimdi yalnız L2 ısınıyor. Gevşek bağlantı tam olarak budur: tek fazda fazla temas direnci.
> θ altı virgül otuz beş kelvine çıkıyor, Uyarı seviyesi.
> — Ve en önemlisi: yük düşse de artsa da θ aynı kalıyor. Ham sıcaklık farkı değişiyor, θ
> değişmiyor. Ölçtüğümüz şey yük değil, bağlantının kendisi.
>
> Üç şey sadeleşiyor: yük, mevsim ve güneş, IR tarafında yayıcılık. Ve kardeş karşılaştırması
> geçmiş gerektirmiyor: montaj günü üç kardeş zaten birbirinin referansı. Bu yeni bir icat
> değil — termografi pratiğinin "benzer bileşene göre benzer yük altında ΔT" ölçütü. Fark şu:
> yılda bir müteahhit değil, dakikada bir sistem ölçüyor.

**Geçiş:** "θ'yı ölçebilmek için panoya ne koyuyoruz? Donanıma geçelim."

**Dikkat:** Ezber: (71,90 − 69,05) / 0,67² = **6,35 K**; hava dalgasında θ kayması 0,0000 K.
"Kalibrasyon?" sorusu → §9 S1. Dürüst sınır: kabin havalandırması tıkanırsa sadeleşme tam
olmaz (ölçülen kayma ≤ 2,9 K); işareti her bağlantının birlikte yükselmesidir.

---

### Slayt 6 · Donanım: 9 cihazlık kit — ⏱ 60 sn

**Ekranda:** EK-II/14 kesiti; sağda kural ve cihaz listesi. **Tıklama:** [→] ×4 (kelepçeler →
termal dizi → PD-01 → ağ geçidi).

**Söyle:**
> "En az 100 modül" ifadesini şartname tanımlamıyor; biz tanımladık: bir modül, bir
> enstrümante edilmiş pano demek ve dokuz cihazdan oluşuyor. Bu sayı kodda sabit; dijital
> ikizde nokta sayan jüri üyesi ile malzeme listesinde satır sayan satın almacı aynı sayıyı bulur.
>
> Önce tek kural: hiçbir delik delinmiyor, tip testli hiçbir parça değişmiyor ve bara bölmesine
> girilmiyor. Neden? Bu panoda AG giriş kesicisi yok. Bara bölmesini enerjisiz yapmak, bütün
> dağıtım merkezini OG tarafından karartmak demek. O yüzden kit yalnız alt kablo bölmesine,
> ölçü kolonuna ve mevcut prize dokunuyor.
>
> **[→]** Altı ısıl kelepçe: Çıkış 6 ve 7'nin üç fazına. Her biri TMP117 sıcaklık sensörü ve
> kendi ayrılabilir akım trafosunu taşıyor — çünkü çıkışlarda dağıtım şirketinin CT'si yok.
> İkişer üçlü olmalarının sebebi θ: medyan alabilmek için en az üç kardeş gerekiyor.
>
> **[→]** Bir termal dizi: bölme tabanına mıknatısla oturuyor ve yukarı bakıyor. Kalan otuz
> dört pabucu görüyor. Mıknatıs tutuyor çünkü şartname pano içinin boyasız galvaniz sac
> olmasını zorunlu kılıyor.
>
> **[→]** RF ve ortam düğümü: şartnamenin zorunlu kıldığı M12 topraklama saplamasında. Kısmi
> deşarj göstergesi ve nemi ölçüyor. HFCT asla faz iletkenine değil, yalnız koruma iletkenine
> takılıyor.
>
> **[→]** Ve ağ geçidi: ölçü kolonunda DIN rayda, şartnamenin zaten istediği 10 amperlik
> prizden besleniyor. Panoda zaten bulunan ABB TVOC-2 ark rölesini ve Entes MPR-53CS
> analizörünü iki ayrı RS-485 hattından okuyor, sensörlerden 868 MHz ile veri topluyor.
>
> Kırmızı halka, kapaktaki o pabuç: Çıkış 7, L2.

**Geçiş:** "Bu dokuz cihazın içinde ne var?"

**Dikkat:** Ezber: 9 cihaz · 74 bağlantı modellendi · 40 ölçülüyor · 34 pabuç yalnız IR ile ·
bara bölmesinin 30 + çatının 4 bağlantısı izlenmez, ekranda gri. Sorular → §9 S2, S3.

---

### Slayt 7 · Elektronik ve firmware — ⏱ 40 sn

**Ekranda:** Dört kart, firmware döngüsü (SAMPLE → AGGREGATE → TX → SLEEP), kelepçe pil
bütçesi şeridi, modül maliyeti.

**Söyle:**
> Dört kart tasarladık. Altı adet ısıl kelepçe, bir termal dizi, bir RF ve ortam düğümü, bir
> ağ geçidi. Sensör düğümleri STM32WLE5 üzerinde: mikrodenetleyici ile 868 MHz radyo aynı
> yongada, tek pille yıllarca çalışacak şekilde.
>
> Ağ geçidi STM32H563 tabanlı: sensörleri radyodan topluyor, ark rölesini ve analizörü iki
> ayrı izole RS-485 hattından okuyor, LTE ile sunucuya çıkıyor. Bağlantı koparsa yirmi bin
> çerçeveyi tamponda tutuyor; elektrik kesilirse süperkapasitörle sekiz saniyelik bir "son
> nefes" bütçesi var.
>
> Firmware C99 ile yazıldı: tek bir float yok, malloc yok. θ'nın kestiricisi uç düğümde sabit
> noktada çalışıyor. "Pano enerjisiz" ve "pil zayıf" hata yolu değil, birinci sınıf durumlar.
>
> Alttaki şerit kelepçenin pil bütçesi, firmware'in kendi güç tablosundan. Sağlıklı panoda düğüm
> on beş dakikada bir uyanıyor, şüphede dakikada bir, olay anında on saniyede bir. Bu karışımla
> ortalama 8,89 mikroamper, öz deşarj dahil 13,1 yıl. Filoda en kısa ömürlü düğüm PD-01,
> yaklaşık 8,4 yıl. Hepsi hesap; tezgâhta ölçülmedi.
>
> Çevresel zarfı sahanın gerçeğine göre kurduk: −25 ile +70 derece, IP65, yoğuşmalı nem için
> koruyucu kaplama. Modül donanımı bin adette 470 euro, yüz adette 660 euro.

**Geçiş:** "Şimdi bu cihazlardan çıkan verinin operatöre ve SCADA'ya nasıl ulaştığını görelim."

**Dikkat:** KiCad şematik/PCB **çizilmedi**; blok şema, I/O, pin dizilimi, katman yığını ve BOM
düzeyinde belgelendi (docs/03). Sorulursa saklamayın. Manyetik alan sorusu → §9 S23.

---

### Slayt 8 · Uçtan uca mimari — ⏱ 50 sn

**Tıklama:** [→] ×2 (pano + ağ geçidi → sunucu odası → çıkışlar).

**Söyle:**
> Uçtan uca mimari. Soldan başlayalım. Panoda dokuz cihaz. Kelepçeler, termal dizi ve RF düğümü
> 868 MHz ile ağ geçidine konuşuyor. Panoda zaten bulunan ark rölesi ve analizör ise RS-485
> Modbus ile okunuyor. Ağ geçidi aptal bir köprü değil: sunucuya giden yol kopsa bile üç kural
> yerelde çalışıyor — herhangi bir bağlantı 90 dereceyi geçerse, kardeş farkı 20 kelvini
> geçerse ve ark açması olursa.
>
> **[→]** Ağ geçidinden sunucuya MQTT 5, TLS, QoS 1 ve store-and-forward. Bir çerçeve,
> broker'dan onay gelene kadar tampondan silinmiyor. Sunucu dağıtım şirketinin kendi sunucu
> odasında: kamu bulutu yok — ne hesaplama, ne depolama, ne bildirim.
>
> **[→]** Üç çıkış. İzleme arayüzü. SCADA için Modbus TCP — istisnasız salt okunur. Ve
> bildirim: SMS ve sesli arama, onay koduyla.
>
> Mimarinin taşıyıcı fikri: her sayı tek bir yerde tanımlı. Ekrandaki değer ile SCADA
> register'ındaki değer aynı nesneden üretiliyor, çelişemezler. Ve akış tek yönlü: sistemin
> hiçbir yerinde panoya komut veren bir yol yok.

**Geçiş:** "Sunucunun içinde veri hangi adımlardan geçiyor?"

**Dikkat:** Demo süreç-içi bus ve SQLite ile çalışır; TimescaleDB hedeflenen yol ve yazılmadı.
mTLS/ACL tasarlandı, saha sertifikalarıyla denenmedi. Sparkplug B sorusu → §9 S10.

---

### Slayt 9 · Tespit zinciri — ⏱ 50 sn

**Tıklama:** [→] ×2 (yedi mod → bilerek kullanmadıklarımız).

**Söyle:**
> Tespit zinciri soldan sağa. Ölçüm dakikada bir geliyor: sıcaklık ve akım. Kardeş farkını
> alıyoruz — medyan bağlantının kendisi hariç, yalnız kardeşleri üzerinden. Kendini de içeren
> bir medyan, kusurlu faz bir kardeşini geçtiği anda ona atlar ve sinyalin yüzde kırkını yer.
>
> θ'yı bir ileri modelin içinden, özyinelemeli en küçük kareler ile kestiriyoruz; çünkü bir
> bağlantı bir direnç değil, ısıl bir kütle. Dekonvolüsyon gürültüyü büyütür; yapmıyoruz.
>
> Sonra zaman ölçeği değişiyor: günlük medyanlar. Avladığımız sinyal haftada 0,2 kelvin; doğru
> adım gün. Üzerinde üç araç: CUSUM sürüklenmeyi, değişim noktası başlangıç tarihini,
> Theil-Sen eğimi veriyor. Sonra bastırma, füzyon, alarm. Sıra sabit: açıklanabilen kanıt hiç
> olasılığa girmiyor.
>
> **[→]** Füzyon yedi arıza moduna risk veriyor; sağlık endeksi bu risklerin ağırlıklı
> çarpımı. Logaritmasını aldığınızda tam ayrışıyor: "sağlık 67" dediğimizde eksik 33 puanın
> hangi moddan geldiğini söyleyebiliyoruz.
>
> **[→]** Ve bilerek kullanmadıklarımız. En çok sorulan: "Yapay zekâ nerede?" Kayan pencerede
> eğitilen bir otokodlayıcı, haftada 0,2 kelvinlik yavaş sürüklenmeyi normalin parçası olarak
> öğrenir ve yeniden üretir; tam avladığımız sinyale yapısal olarak kördür. Üstelik aylarca
> temiz geçmiş ister ve yüz panoya yüz model demek. Bizim her çıktımızın birimi var: kelvin,
> mikroohm, gün.

**Geçiş:** "Bu zincirin en değerli çıktısı: haftalar önce, tarihiyle haber vermek."

**Dikkat:** Ezber: CUSUM k = 0,5 · h = 8 · ARL0 ≈ 19 112 gün (bağlantı başına 52,3 yıl) · filo:
100 pano × 40 bağlantıda 4,8 günde bir yanlış CUSUM geçişi, ama alarm üç şartı birden ister.

---

### Slayt 10 · Haftalar önce: tarih ve ufuk — ⏱ 60 sn

**Ekranda:** Ç7-L2'nin günlük θ medyanı; Uyarı ve Kritik işaretleri, değişim noktası, ileriye
projeksiyon yelpazesi. **Tıklama:** [→] ×3.

**Söyle:**
> Ürünün haftalar önce haber veren yolu bu grafikte. Sarı çizgi, Çıkış 7 L2 pabucunun günlük θ
> medyanı.
>
> **[→]** Geriye bakan yol: CUSUM birikiyor, θ beş kelvini geçiyor ve son beş günün üçünde
> geçiyor — üç şart birden olunca Uyarı açılıyor, iş emri yazılıyor. Telefon çalmıyor. On iki
> kelvini geçip ikinci bağımsız sensör ailesi de hemfikir olunca Kritik oluyor ve nöbetçiye SMS
> gidiyor.
>
> **[→]** Ama asıl ikna edici cümle şu: demo koşumuzda bu bozulma 11 Eylül civarında hızlandı.
> Bunu CUSUM söylemiyor — CUSUM zaten gecikir. Tarihi, tüm seri üzerinde geriye dönük bir
> değişim noktası kestirimi veriyor. Ve tarihi bir aralık olarak veriyoruz; çünkü bozulma bir
> basamak değil bir rampa.
>
> **[→]** Bakım planlayıcısının sorduğu soru ise ileriye dönük: bu pabuç ne zaman benim sorunum
> olacak? Bu gidişle ACİL seviyesine on beş gün; on üç ile on dokuz arası. Aralık uydurulmadı:
> eğimin kendi güven aralığı var ve gün sayısı o aralığın iki ucuna bölünerek çıkıyor.
>
> Bu sayı bir iş emrinin bu haftaya mı gelecek aya mı yazılacağına karar vermeye yeter; bir
> kesinti tarihini planlamaya yetmez — ve öyle sunmuyoruz. Yirmi bir günlük pencerede en az on
> dört geçerli gün yoksa sistem gün sayısı üretmiyor; "yetersiz geçmiş" yazıyor. Sayı üretmek
> kolaydı; üretmemek ürünün kendisi.

**Geçiş:** "Ama her şeyi görebildiğimizi iddia etmiyoruz."

**Dikkat:** Grafik eğrisi şematik, işaretlerdeki sayılar 3 Ekim koşusundan. "Bozulma hızlanırsa?"
→ §9 S9.

---

### Slayt 11 · Kör olduğumuz yeri söyleriz — ⏱ 35 sn

**Ekranda:** θ_min = 3σ/f² eğrisi; nokta 24 saati ~12 sn'de döner.

**Söyle:**
> Bir kusur, yük faktörü f'te gözlenen farkı yalnız θ çarpı f kare kadar büyütür. Yük
> düştükçe aynı kusuru görmek zorlaşır. Bunu saklamıyoruz, hesaplıyoruz: görülebilen en küçük
> θ, üç sigma bölü f kare.
>
> Noktayı izleyin: öğleden sonra, tam yüke yakınken kelepçe yarım kelvinlik bir kusuru bile
> görüyor. Gece üçte, yüzde on sekiz yükte bu sayı on sekiz buçuk kelvine çıkıyor.
>
> Rakip bir ürün gece yarısı "her şey normal" der. Biz "şu anda on sekiz buçuk kelvinin
> altındaki bir kusuru göremiyorum" diyoruz. Bu bir arıza değil, bir görünürlük durumu: ayrı
> raporlanıyor, SCADA'da da ayrı bir bit. Mutlak sıcaklık limitleri bu sırada da açık.
> Kör olduğumuz yeri söylemek bir kusur değil, ürünün özelliği.

**Geçiş:** "Görmediğimizi söylemek kadar önemli bir şey daha var: üretmediğimiz alarmlar."

**Dikkat:** 110/130 °C bir standart alıntısı değil, mühendislik çıkarımı (§9 S7).

---

### Slayt 12 · Bastırılmış alarmlar — ⏱ 50 sn · **kesilmez (ya burada ya demoda)**

**Ekranda:** Solda sıcak hava dalgası: 40 bağlantı; sabit eşikli sistemin sayacı (60 °C eşiği
geçenler) tepe noktada **13**, PANO GÖZ **0**; sağda bastırma kodları. **Tıklama:** [→] ×1.

**Söyle:**
> Şimdi ürünün bence en önemli parçası: ürettiğimiz alarmların değil, üretmediğimiz alarmların
> listesi. Gerekçeleriyle.
>
> Solda bir sıcak hava dalgası. Ortam 41,2 derece — şartnamenin dahili maksimumu 40 derece.
> Kırk bağlantının hepsi birden 6,1 kelvin ısınıyor. Sabit eşikli bir sistem, eşiği geçen on üç
> bağlantı için on üç alarm üretiyor; dalga biraz daha sürse sayı artmaya devam eder. θ'nın değişimi tam sıfır: sıfır virgül sıfır sıfır sıfır sıfır. Çünkü kardeşler
> aynı havayı soluyor. Bu pano hakkında değil, hava hakkında bir okuma.
>
> **[→]** Sağda bastırma kurallarından bazıları. Her biri tek bir soruya cevap veriyor: bu
> okuma pano hakkında mı, yoksa şebeke, hava, yük ya da kendi cihazımız hakkında mı?
>
> Üç fazın gerilim bozulması birlikte yükselirse: pano bir yüktür, kaynak değil; harmonik
> kanıtlı modlar kapanır. Ama dürüst olalım — aynı ölçümü tesisteki büyük bir sürücü ya da UPS
> de üretir. O yüzden ısıl bulguyu silmiyoruz, yalnız bir kademe geriletiyoruz ve ekibi
> vetolamıyoruz. Sıcak bir cıvata, gerilim bozunumu sürüyor diye bekletilmez.
>
> Sensör kayarsa ya da kelepçe düşerse cihaz iş emri açılıyor — tork iş emri değil. Sapan bir
> sensör yüzünden bir ekibi sağlam bir bağlantıyı sıkmaya göndermek, sistemin güvenilirliğini
> bir seferde bitirir.
>
> Bu liste bir hata ayıklama günlüğü değil; **kendi ekranı olan bir ürün.**

**Geçiş:** "Bastırmanın tam tersi uçta ise ark var: orada hiçbir şey bastırılmaz."

**Dikkat:** Sol sayaç tepe noktada **13**'te durur; "kırk alarm" demeyin, ekranla çelişir. Ezber: ortam 41,2 °C · +6,1 K ·
Δθ = 0,0000 K · THD L1 %6,8 / L2 %7,1 / L3 %6,9, tabanlar %2,4 / 2,5 / 2,3. Sıcak hava dalgası
**canlı demoda gösterilmez** (§8.4); hikâyesini bu slayt anlatır.

---

### Slayt 13 · Ark olayı: koruma bizde değil — ⏱ 45 sn · **kesilmez (ya burada ya demoda)**

**Söyle:**
> Ark oluştu. Biz açmadık. Panodaki ABB TVOC-2 rölesi açtı: ışıktan kontağa yaklaşık bir
> milisaniye, SIL-2 donanımda. PANO GÖZ koruma yapmıyor ve yapmaya çalışmıyor; koruma bizi
> beklemez.
>
> Bizim işimiz ark olduktan sonra başlıyor: hangi dedektör gördü — X2:3. Hangi röle attı — K5.
> Ne zaman oldu. Ve nöbetçiye haber vermek.
>
> Gecikmeyi tek bir temiz sayı olarak vermiyoruz: dört ile on üç saniye arası. Çünkü TVOC-2'nin
> Modbus görüntüsünün ne kadar sürede güncellendiğini ABB dokümante etmemiş. Beş saniye
> deseydik, ölçmediğimiz bir şeyi ölçmüş gibi göstermiş olurduk.
>
> Bir şeye daha bakın: "sağlam dedektör 10/10" yazıyor; ama bu röleye yirmi dedektör bağlı
> olabilir. Register 222 ve 223 yalnız X2 ve X3 kartlarını kapsıyor. X1'deki dedektörlerin
> sağlığını göremiyoruz ve ekranda tam olarak öyle yazıyor. Görmediğimiz şeyi gördü gibi
> göstermek, en tehlikeli hatadır.

**Geçiş:** "Peki bir alarm açıldığında kimin telefonu, ne zaman çalıyor?"

**Dikkat:** Aritmetik (sorulursa): reg 1300 bit0 = aktif açma · dedektör LOW kelimesi 0x1000 →
bit 12 → X2:3 · röle bit alanı 0x0002 → bit1 → K5. En iyi 0,2 + 1 + 0,3 + 2,5 ≈ 4 s; en kötü
2 + 1 + 2 + 8 = 13 s. Otokontrol sorusu → §9 S17.

---

### Slayt 14 · Seviye merdiveni ve bildirim — ⏱ 50 sn

**Ekranda:** Beş basamak; ortada telefon, SMS kendini yazar; sağda eskalasyon kademeleri.
**Tıklama:** [→] ×1 (onay balonu).

**Söyle:**
> Seviye merdiveni beş basamak. Bilgi kayda geçer. İzle haftalık özete girer, ekip çıkmaz. Uyarı
> iş emri açar ve planlı bir ziyarette doğrulanır. **Yalnızca Kritik ve Acil bir telefonu
> çaldırır.** Bu tek kural, sistemin üçüncü aydan sonra da açık kalmasını sağlayan kural; bu
> yüzden bir ayar değil, kodda bir sözleşme.
>
> Telefon çalmadan önce iki şart daha var: iki bağımsız sensör ailesi hemfikir olmalı — örneğin
> kelepçe ve termal dizi — ve Kritik için yirmi dört saat bekleme var; Acil bundan muaf.
>
> Mesaja bakın: pano, bağlantı, θ, yapılacak iş, ACİL'e kalan gün ve onay kodu. Türkçe
> karakterler bozulmasın diye UCS-2 gidiyor; iki parçaya sığacak şekilde tasarlandı.
>
> **[→]** Nöbetçi "TAMAM 1 0541" yazıyor ve olay onaylanıyor. Kod kişiye ve olaya bağlı: rotada
> olmayan biri ya da yanlış kod onaylayamaz.
>
> Onay gelmezse merdiven yükseliyor: Acil'de on beş dakika, Kritik'te kırk beş dakika sonra şef
> ve sesli arama, ardından işletme müdürü. Bir de fırtına tavanı var: saatte en fazla sekiz
> Kritik — ama Acil muaf. Tavan bir Acil'i susturabilseydi tavan değil arıza olurdu.

**Geçiş:** "Operatör ekranı bir yana, dağıtım şirketinin kendi SCADA'sı bu veriyi nasıl alıyor?"

**Dikkat:** GSM modem ve SMPP **simüle**, transkript kaydedilir; gerçek kanaldan mesaj gitmedi.
Sesli arama simülasyon. WhatsApp yok. Sorulursa açıkça söyleyin (§9 S11).

---

### Slayt 15 · SCADA: Modbus haritalama — ⏱ 40 sn

**Tıklama:** [→] ×1 (yazma denemesi).

**Söyle:**
> Şartname SCADA entegrasyonu için Modbus haritalaması istiyor. Çalışan bir Modbus TCP slave
> teslim ettik.
>
> Her pano sabit adımlı, deliksiz bir bloğa sahip: bin artı kırk sekiz çarpı n eksi bir. On dört
> numaralı panonun adresi: bin artı kırk sekiz çarpı on üç, **bin altı yüz yirmi dört**. SCADA
> mühendisi tek bir blok tanımlıyor ve yüz kez kopyalıyor.
>
> Sağda bu bloktan birkaç register. THETA_MAX ham 176, ölçek 0,1: 17,6 kelvin. Bu sayı
> arayüzdeki sayıyla aynı nesneden geliyor. En değerli iki register ise kaynak cihazların
> üretemediği ikisi: ark rölesiyle bağın koptuğunu söyleyen durum biti ve bu bloğun ne kadar
> bayat olduğunu söyleyen veri yaşı.
>
> **[→]** Ve yazmayı deneyin: exception sıfır bir, ILLEGAL FUNCTION. İstisnası yok. Modbus'ta
> kimlik doğrulama yok; ark rölesine otokontrol komutu verebilen bir sisteme kimliksiz yazma
> yolu açmak kabul edilemez.
>
> Yüz panonun tamamını taramak dört bin sekiz yüz register; FC 03'ün 125 register sınırı
> yüzünden en az otuz dokuz istek — ölçtük, on dokuz milisaniye.

**Geçiş:** "Yeterince slayt; şimdi canlı sisteme geçiyorum."

**Dikkat:** IEC 104 / OPC UA için nokta listesi var, sunucu yok. "Eşiğe kalan gün" için SCADA
register'ı yok (blok dolu, büyütmek ICD v2.0'ı bozar).

---

### Slayt 16 · Canlı demo — ⏱ 5 dk

Tarayıcıya geçin (**Alt+Tab**). Akış, tıklamalar ve repliklerin tamamı **§8**'de.

**Canlı sistem açılmazsa:** bu slayttaki altı ekran 6 sn'de bir döner; sağdaki listeden
tıklayarak sabitleyip anlatın. Repliği değiştirmeyin, yalnız "canlı sistem yerine ekran
görüntüleri" deyin.

**Geçiş (demodan destede 17'ye dönerken):** "Ekranda gördüğünüz sistemin sahaya nasıl
kurulacağına gelelim."

---

### Slayt 17 · Saha uygulaması — ⏱ 45 sn

**Tıklama:** [→] ×1 (alt satır).

**Söyle:**
> Kurulum, şartnamenin en çok vurguladığı risk: kalabalık bir pano, hayati risk ve şebeke
> etkisi. Bu yüzden saha prosedürünü adım adım yazdık.
>
> İki kişi, hedef iki buçuk saat; ilk beş kurulumda üç buçuk-dört saat bekliyoruz. Kesinti
> gerekmiyor, çünkü yalnız alt kablo bölmesine, ölçü kolonuna ve mevcut prize dokunuyoruz.
>
> İlk adım bir güvenlik kapısı: hiçbir şeye dokunmadan termal kamerayla pabuç sırası taranıyor.
> Bir pabuç 110 derecenin üstündeyse ekip duruyor ve montaj yapmıyor.
>
> Sonra kelepçeler, termal dizinin nişanı, RF düğümü ve ağ geçidi. Tek bir adımı dürüstçe
> işaretledik: RS-485 hattını indirmek enerjili bir panoda iletken çekmeyi gerektiriyor.
> Dağıtım şirketinin kuralları izin vermiyorsa bu adım planlı bir kesintiye ertelenir; sistem
> RS-485 olmadan da çalışır.
>
> Devreye alma dizüstü bilgisayarsız, telefonla: etiket kamerayla okunuyor, her cihaza NFC ile
> dokunuluyor, teknisyen cihazın yerini pano çizimi üzerinde parmağıyla işaretliyor. Elle
> yazılan pano numarası filo yönetiminde en sık hata; onu ortadan kaldırıyoruz.
>
> **[→]** Sonra yedi günlük öğrenme penceresi — mutlak limitler bu sırada da açık. Ve iki iş
> emri türü asla karışmıyor: pano iş emri elektrik işi, cihaz iş emri panoya dokunmadan sensörü
> düzeltmek.

**Geçiş:** "Bir panoyu kurmak bir şey, yüz ya da bin panoyu işletmek başka bir şey."

**Dikkat:** NFC akışı tasarlandı, yonga tezgâhta denenmedi. Ezber: 100 modül = 25 ekip-günü;
1000 modül = 4 ekiple 3 ay.

---

### Slayt 18 · Ölçeklenebilirlik — ⏱ 40 sn

**Tıklama:** [→] ×1 (asıl kısıtlar).

**Söyle:**
> Şartname en az yüz modülü işleyebilecek bir tasarım ve kaynak değerlendirmesi istiyor.
> Sayıları kendi kodumuz üzerinde ölçtük.
>
> Yüz panoda saniyede on beş zarf geliyor. Dedektör bir çekirdeğin yüzde ikisini kullanıyor;
> disk kararlı hâlde on sekiz gigabayt. Bin panoda dedektör bir çekirdeğin beşte birinden az,
> disk yüz seksen gigabayt. On bin panoda iki çekirdek ve bölge başına düğümler — bu bir
> kestirim; ölçtüğümüz en büyük filo 112 pano.
>
> Klasik itiraz: yüz cihazı tek bir RS-485 hattına koyarsanız tarama saniyeler sürer. İtiraz
> doğru — ve biz o hattı kurmuyoruz. Her panonun kendi kısa hattı ve kendi master'ı var.
> Ölçekleme seri hatta değil, broker'da oluyor.
>
> **[→]** Gerçek ölçek kısıtları başka yerde: operatörün dikkati — bir nöbetçi günde beş-on
> gerçek alarmdan fazlasını işleyemez; bastırma ve seviye merdiveni tam bunun için var. Ve
> kurulum kapasitesi: yazılım değil, ekip-günü projenin takvimini belirler.

**Geçiş:** "Ölçek teknik olarak sorun değil; asıl soru parasal."

**Dikkat:** Çubuklar logaritmik; sayıları okuyun. SQLite ~10 000 panoda biter, TimescaleDB
sürücüsü yazılmadı. ICD MAX_PANELS = 200 bilinçli hackathon sınırı.

---

### Slayt 19 · Maliyet ve fayda — ⏱ 55 sn

**Tıklama:** [→] ×2 (kırmızı çizgi → yeşil çizgi → 1000 pano ve F1).

**Söyle:**
> Maliyet–fayda bölümüne kötü haberle başlıyoruz, çünkü bir dağıtım şirketinin varlık yönetimi
> ekibi bu hesabı zaten kendisi yapacak.
>
> Her panoya eşit dağıtılmış yüz modüllük bir pilot, beş yılda parasını geri ödemez. Beş yıllık
> toplam sahip olma maliyeti yüz elli dört bin euro, fayda yüz yirmi dört bin; net eksi otuz bin
> euro. Geri ödeme 6,9 yıl. Başa baş yüz yetmiş beş panoda.
>
> **[→]** Ama çözüm daha fazla pano almak değil. Aynı yüz modülü filonun en kötü onda birine
> koyarsanız — dağıtım şirketi bu panoları zaten biliyor: arıza kaydı, yaş, yük faktörü, son
> termografi raporu — geri ödeme 2,2 yıla iniyor. Beş yılda artı yüz kırk üç bin euro.
>
> **[→]** Bin panoda tekdüze dağıtım da 3,3 yılda geri öder, çünkü öğrenme eğrisi donanımı
> yüzde 28,8 ucuzlatıyor.
>
> Ve faydanın en sağlam kalemi: yüzde 43,5'i hiçbir kusuru tespit etmesek bile gerçekleşiyor.
> Bugün bu panolara yılda iki kez termal kamerayla gidiliyor; PANO GÖZ ile bara bölmesi ve çatı
> için üç yılda bir ziyaret yeterli. Bunu bir dağıtım şirketi kendi bakım bütçesinden
> doğrulayabilir; bizim modelimize inanması gerekmez.
>
> Soru kaç pano alacağınız değil, hangi panolara koyacağınız.

**Geçiş:** "Bu hesapların hiçbiri saha verisiyle doğrulanmadı; nedenini söylemeliyiz: bize
verilen veri."

**Dikkat:** Ezber: modül €470,59 / €660,91 · kurulum €150 · 100 pano 5 yıl TCO €154 591.
Varsayımlar DSO kayıtlarıyla doğrulanmadı. docs/07 §4.3'teki "+€142 109" yazım hatası; doğrusu
+€143 109 (slayt doğru).

---

### Slayt 20 · Verilen veri ve dijital ikiz — ⏱ 35 sn

**Tıklama:** [→] ×1.

**Söyle:**
> Yarışmada bize bir akım verisi verildi. Önce onu analiz ettik ve şunu bulduk: veri sentetik.
> Bunu bir "yakaladık" gösterisi olarak değil, sonuçlarını hesaba katmak için söylüyoruz.
>
> Üstte gerçek bir fiderin nasıl görünmesi gerektiği: sabah yükselen, öğleden sonra tepe yapan
> bir eğri. Komşu iki ölçüm neredeyse aynıdır; lag-1 otokorelasyonu 0,97'nin üstündedir.
>
> Altta verilen veri: lag-1 otokorelasyonu artı sıfır virgül sıfır sıfır sıfır üç. Altı bağımsız
> test aynı şeyi söylüyor: Excel'in RASTGELEARADA fonksiyonuyla on beş ile doksan arasında
> üretilmiş düzgün gürültüyle uyumlu. Sıcaklık-nem sayfası tamamen boş, etiketli arıza geçmişi
> yok, kardeş fazı yok, anomali yok.
>
> **[→]** Bu yüzden modelimizi bu veriye uydurmadık. Fizikten türetilmiş bir dijital ikiz
> kurduk: on yedi senaryo, bunların yedisi alarm vermemesi gereken negatif kontrol. Ve dürüst
> olalım: bu paketteki hiçbir başarım sayısı saha verisiyle doğrulanmış değil. Gerçek yanlış
> alarm oranı ancak etiketli saha geçmişi olan bir pilot tesiste ölçülebilir. Bunu pilotun
> ölçeceği ilk şey olarak öneriyoruz.

**Geçiş:** "Aynı dürüstlükle, bilerek yapmadıklarımızı da sayalım."

**Dikkat:** Ton suçlama değil, sonuç. Canlı arayüzde üst şeritteki **"Veri kanıtı"** düğmesi bu
analizin JSON hâlini açar.

---

### Slayt 21 · Yapmadıklarımız — ⏱ 40 sn

**Tıklama:** [→] ×1 ("belgelendi, kodlanmadı" şeridi).

**Söyle:**
> Bir hackathon teslimi için bence en değerli bölüm: bilerek yapmadıklarımız.
>
> Bara bölmesine sensör koymadık: AG giriş kesicisi yok; o bölmeye girmek ya dağıtım merkezini
> karartmak ya da 2312 amper taşıyan çıplak baranın kapağını enerjili açmak demek.
>
> Enerji hasadı iddia etmiyoruz: teorik olarak mümkün ama ölçmedik.
>
> Pano başına derin öğrenme kullanmadık: aradığımız yavaş sürüklenmeye yapısal olarak kör.
>
> SCADA'dan yazma yolu açmadık: Modbus'ta kimlik doğrulama yok.
>
> Sparkplug B rozetini takmadık: spesifikasyon bizim dayanıklılık mekanizmamızı yasaklıyor.
>
> Ve kısmi deşarj kanalını tek başına ekip yönlendirmek için kullanmıyoruz; 400 voltta klasik
> kısmi deşarj zaten oluşmaz. RF kanalı ısıl bulguyu destekliyor.
>
> **[→]** Bir de "belgelendi ama kodlanmadı" listemiz var: KiCad çizimleri, IEC 104 sunucusu,
> gerçek SMS gönderimi, TimescaleDB sürücüsü ve OG hücre donanımı.

**Geçiş:** "Toparlarsak, şartnamenin istediklerine bugün nerede duruyoruz?"

**Dikkat:** Süre daralırsa yalnız ilk üçünü söyleyin. OG hücre sorusu → §9 S15.

---

### Slayt 22 · Şartname karşılığı — ⏱ 30 sn

**Söyle:**
> Şartnamenin "beklenen teknik çıktılar" listesini bugünkü durumla eşledik ve renk yerine
> kelimeyle yazdık: Tamam ya da Kısmen.
>
> Yazılım mimarisi, izleme ekranları, SCADA Modbus haritalaması, on-premise altyapı ve yüz modül
> ölçeği tamam. Modül tasarımı ve elektronik dokümantasyon kısmen: blok şema, I/O tabloları, pin
> dizilimleri, katman yığını ve BOM var; KiCad çizimleri yok. SMS kısmen: merdiven, onay kodu ve
> fırtına tavanı çalışıyor; gönderim simüle.
>
> Arkasındaki iş: yaklaşık otuz üç bin satır Python, dört buçuk bin satır C99 firmware, sekiz
> bine yakın satır bağımlılıksız arayüz kodu, yüz yetmiş iki otomatik test ve on bir teknik
> belge artı SCADA arayüz dokümanı.

**Geçiş:** "Kapatırken üç şey."

**Dikkat:** "Kısmen" satırlarını siz söyleyin, sorulmasını beklemeyin.

---

### Slayt 23 · Kapanış — ⏱ 30 sn

**Söyle:**
> Kapatırken üç şey.
>
> Bir: **θ**. Yükten ve mevsimden bağımsız bir ölçü; montaj gününden itibaren çalışıyor ve
> haftalar önce, tarihiyle ve kalan süresiyle haber veriyor.
>
> İki: **bastırma**. Yüz panoyu yönetilebilir kılan şey ürettiğimiz alarmlar değil, üretmediğimiz
> alarmların gerekçeli listesi.
>
> Üç: **dürüstlük**. Kör olduğumuz yeri, gecikmenin bir aralık olduğunu ve verinin neyi
> ölçemediğini ekranda söylüyoruz. Bir dağıtım şirketi, ne zaman güvenmemesi gerektiğini
> söyleyen bir sisteme güvenir.
>
> Ve son cümle: aynı yüz modülü filonun en kötü onda birine koyarsanız 2,2 yılda geri öder.
> **Soru kaç pano alacağınız değil, hangi panolara koyacağınız.**
>
> Teşekkürler. Sorularınızı bekliyoruz.

**Dikkat:** Son cümleden sonra susun ve bekleyin. Soru-cevapta **Q** hazır cevap panelini açar
(arama kutulu); bir slayta dönmek için numarasını yazıp **Enter**.

---

## 8. Canlı demo: adım adım

Bu bölümdeki akış **8 Ekim 2026'da çalışan sistem üzerinde denendi.** Ekran adları,
düğmeler ve süreler gerçekte görülenlerdir. Ekrandaki **sayılar** ise koşunun yapıldığı güne
göre değişir: rakamları ezberden değil, **ekrandan okuyun.**

### 8.1 Sunumdan önce (T−30 dk … T−0)

1. **Diğer ağır programları kapatın** (fazla tarayıcı sekmesi, IDE, video).
2. **Demoyu başlatın** (proje kökünde, PowerShell):
   ```powershell
   .\baslat.ps1 -Panels 24 -BackfillDays 45 -Reset
   ```
   - 24 pano ile ~10 saniyede hazır olur ve tarayıcıyı açar (`http://127.0.0.1:8080`).
   - **Neden 24, neden 112 değil:** varsayılan 112 pano bu bilgisayarda denendi ve yetişemedi:
     dedektör geçişi 5 saniyelik periyodun ~3,9 saniyesini yedi, iç kuyrukta 20 000 mesaj
     birikti, mesajlar düştü ve ~3 dakikada **tüm filo "Veri bayat (STALE)"** durumuna geçti.
     24 panoda geçiş 0,33 sn, düşen mesaj yok. Slaytlardaki 3 Ekim koşusu da 24 pano + 45 gün idi.
   - `-Reset` eski veritabanını siler; önceki provalardan kalan enjeksiyonlar temizlenir.
   - **`--no-backfill` / `-NoBackfill` kullanmayın:** değişim noktası tarihi ve "eşiğe kalan
     gün" geçmiş olmadan hesaplanamaz.
3. **Tarayıcıda tam ekran** (F11). Tema varsayılan koyu; projektör soluksa üst şeritteki
   **açık tema** düğmesine geçin.
4. **T−20 dk: şebeke olayını enjekte edin** (bastırma beat'i için, satırların oluşması < 1 dk):
   - Üst şeritte **Pano seç…** → **TURGUTLU-02**.
   - Sol rayın altındaki **Demo · senaryo** → **Şebeke olayı (negatif kontrol)** → **Enjekte et**.
   - Çekmecenin üstünde "Hedef pano: TURGUTLU-02" yazdığını kontrol edin.
   - Sonra **Pano seç… → SOKE-14**'e geri dönün.
5. **İki PowerShell penceresi hazırlayın** (komutlar yazılı, **çalıştırılmamış**):
   - Pencere 1, ark olayı (demo sırasında çalıştırılacak):
     ```powershell
     Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8080/api/scenario/ark_olayi -ContentType 'application/json' -Body '{"panel_key":"SOKE-14","at_s":0,"detector":"X2:3","relay":"K5"}'
     ```
   - Pencere 2, SCADA kanıtı:
     ```powershell
     python sunum\scada_kanit.py
     ```
6. **Bugünün sayılarını not edin** (Filo → SOKE-14 satırı ve Kanıt ekranı): θ, "ACİL'e X gün
   (a–b)", değişim noktası tarihi. Demoda bunları söyleyeceksiniz.

> ⚠ **Demo çekmecesindeki "Ark olayı → Enjekte et" düğmesini KULLANMAYIN.** Senaryonun
> varsayılan gecikmesi **1 saattir** (`at_s = 3600`); düğmeye basınca ekranda hiçbir şey olmaz.
> Ark için yukarıdaki komut gecikmeyi sıfırlar ve dedektör/röle adını slaytla aynı yapar
> (X2:3, K5). 24 panoda ark **~10 saniyede** düşer.
>
> ⚠ **Arkı demodan önce enjekte etmeyin:** açmadan sonra SOKE-14 enerjisiz kalır (AG'de giriş
> kesicisi yok) ve kanıt ekranının hikâyesi bozulur.

### 8.2 Ekran haritası

Sol rayda: **Filo (S1)** · **Pano (S2 · ikiz)** · **Kanıt (S3)** · **PRPD (S4)** ·
**Alarmlar (S5)** · **SCADA (S6)** · **Demo (senaryo çekmecesi)**. Alarmlar ekranında üç sekme:
**Aktif** · **Bastırılan** · **Bildirimler**. Üst şeritte: **Pano seç…**, **Veri kanıtı**,
canlı bağlantı göstergesi, tema.

### 8.3 Akış (5 dakika)

| # | Beat | Süre | Başlangıç | Kesilebilir mi |
|---:|---|---:|---:|---|
| 1 | Filo ve tez | 30 sn | 0:00 | kısaltılabilir |
| 2 | Dijital ikiz | 45 sn | 0:30 | kısaltılabilir |
| 3 | Kanıt: bozulma, tarih, ufuk | 50 sn | 1:15 | kısaltılabilir |
| 4 | **Bastırılan alarmlar** | 45 sn | 2:05 | **asla** |
| 5 | **Ark olayı ve bildirim** | 50 sn | 2:50 | **asla** |
| 6 | SCADA kanıtı | 35 sn | 3:40 | kesilebilir |
| 7 | Kör olduğumuz yer | 20 sn | 4:15 | kesilebilir |
| 8 | Kapanış, slayta dönüş | 15 sn | 4:35 | kısaltılabilir |

---

**Beat 1 · Filo ve tez (30 sn)**
**Ekran:** Filo (S1): harita + pano tablosu, üstte sayaç kartları (pano, aktif alarm, bastırılan
24 sa, görüşü kısıtlı). **Tıklama:** yok.

> "Bu, Ege ve Güney Ege'de [ekrandaki sayı, 24 panoda 25] dağıtım panosu. Her biri bir PANO GÖZ
> modülü. Tablodaki 'Eşiğe' kolonuna bakın: yalnız bir-iki satır gün sayısı veriyor; geri
> kalanların yanında 'yetersiz geçmiş' yazıyor. Yirmi bir günde on dört geçerli gün yoksa bu
> sistem sayı üretmiyor."

**Beat 2 · Dijital ikiz (45 sn)**
**Tıklama:** tabloda **SOKE-14** satırına çift tıkla (ya da Pano seç… → SOKE-14, sonra **Pano S2**).

> "Tek panoya girelim. Dokuz cihaz — bu sayı donmuştur, sayabilirsiniz. Altı ısıl kelepçe iki
> fiderin üç fazında, bir termal dizi pabuç sırasına bakıyor, bir RF düğümü topraklama
> saplamasında, bir ağ geçidi ölçü kolonunda. Yetmiş dört cıvatalı bağlantı; kırkını ölçüyoruz.
> Kalan otuz dördü gri: bara bölmesinde ve çatıda. Onlara giremiyoruz, çünkü bu panonun AG
> giriş kesicisi yok. Gri renk bir eksiklik değil, bir **beyandır**."

**Beat 3 · Kanıt: bozulma, tarih, ufuk (50 sn)**
**Tıklama:** **Kanıt (S3)**. Bağlantı seçili gelmezse en kötü bağlantıyı seçin: **Çıkış 7 · L2 · çıkış
pabucu** (`C07-L2-PABUC`; Filo tablosunda ve SCADA'da da bu bağlantı görünür).

> "Çıkış 7, L2. Bu ekranda ham sıcaklık, yük, θ ve CUSUM aynı zaman ekseninde. θ şu anda
> [ekrandan oku, 8 Ekim'de 18,8] kelvin. CUSUM sürüklendiğini söylüyor. Ama asıl cümle şu:
> bu bozulma yaklaşık [değişim noktası tarihi] civarında başladı — bunu CUSUM değil, geriye
> dönük değişim noktası kestirimi söylüyor ve bir aralık olarak veriyor.
>
> Projeksiyon kartı ise planlayıcının sorusunu cevaplıyor: bu gidişle ACİL'e [X] gün, [a] ile
> [b] arası. Aralık eğimin kendi güven aralığından geliyor. İş emrini bu haftaya mı gelecek aya
> mı yazacağınıza yeter; kesinti planlamaya yetmez, öyle sunmuyoruz."

**Ek (varsa süre):** "Alarm üç şartın hepsini ister: CUSUM sekizi geçecek, θ beş kelvini geçecek
ve son beş günün üçünde geçecek."

**Beat 4 · Bastırılan alarmlar (45 sn) · ASLA KESİLMEZ**
**Tıklama:** **Alarmlar (S5)** → önce **Aktif** sekmesi (bir bakış), sonra **Bastırılan**.

Aktif sekmesinde SOKE-14 için **KRİTİK** bir gevşek bağlantı alarmı görünür:
"Çıkış 7 · L2 · çıkış pabucu — bağlantı direnci artıyor".

> "Bu alarm Kritik seviyede açık. Ama bakın: telefon çalmadı. Neden çalmadığı Bastırılan
> sekmesinde yazıyor." **(Bastırılan'a geç)**
>
> "Şimdi ürünün en önemli ekranı: ürettiğimiz değil, **üretmediğimiz** alarmlar. Gerekçeleriyle.
>
> SOKE-14 satırı: 'Bildirim yapılmadı: tek kanal teyidi — iki bağımsız ölçüm ilkesi gerekir;
> yirmi dört saat bekleme dolmadı.' Yalnız kelepçe görüyor; ikinci bağımsız aile teyit etmeden
> ekip yönlendirmiyoruz.
>
> TURGUTLU-02: üç fazın gerilim THD'si birlikte yükseldi. Pano bir yüktür, kaynak değil; harmonik
> kanıtlı bulgular kapanır. Ama aynı ölçümü tesisteki bir sürücü ya da UPS de üretir; o yüzden
> bunu bir **şebeke olayı adayı** olarak yazıyoruz ve ısıl bir bulguyu silmiyoruz.
>
> Görünürlük düşük, pano enerjisiz satırları da burada: bunlar arıza değil, durum.
>
> Bir operatör 'yetmiş sekiz derece okumuşsun, neden bana söylemedin?' diye sorduğunda cevap
> burada, kendi dilinde, sayılarıyla. Bu bir hata ayıklama günlüğü değil — **kendi ekranı olan
> bir üründür.**"

**Beat 5 · Ark olayı ve bildirim (50 sn) · ASLA KESİLMEZ**
**Tıklama:** PowerShell **Pencere 1**'deki komutu çalıştır (Enter), tarayıcıya dön,
**Alarmlar → Aktif**. ~10 saniye içinde **ACİL**: "SOKE-14 · ARK AÇMASI — dedektör X2:3".

> (Komutu çalıştırırken) "Şimdi SOKE-14'te bir ark olayı canlandırıyorum. (Alarm düşünce)
> Ark oluştu. **Biz açmadık.** ABB TVOC-2 açtı, yaklaşık bir milisaniyede, SIL-2 donanımda.
> Bizim işimiz sonrasında başlar: hangi dedektör gördü — X2:3; hangi röle attı — K5; ne zaman
> oldu; ve nöbetçiye haber vermek.
>
> Gecikmeyi tek bir temiz sayı olarak vermiyoruz: dört ile on üç saniye arası, çünkü TVOC-2'nin
> Modbus görüntüsünün ne kadar sürede güncellendiğini ABB dokümante etmemiş."

**Tıklama:** **Bildirimler** sekmesi. ACİL SMS'i ve sesli arama kaydı görünür, örn.:
`PANO GÖZ ACIL · SOKE-14 · pano geneli · ARK AÇMASI · ekip yönlendir · onay: TAMAM 2 1190`

> "Acil olduğu için bekleme yok: SMS nöbetçiye gitti, sesli arama da yapıldı. Onay kodu kişiye
> ve olaya bağlı. Dürüst olalım: GSM modem ve sesli arama bu sürümde simülasyon; transkripti
> burada görüyorsunuz."

**Beat 6 · SCADA kanıtı (35 sn)**
**Tıklama:** PowerShell **Pencere 2**'deki komutu çalıştır (`python sunum\scada_kanit.py`).
Çıktı örneği (8 Ekim, ark sonrası):

```
Pano 14 bloğu: 1000 + 48 × (14 − 1) = 1624
  +0   PANEL_ID         ham [0, 14]  →  14
  +2   HEALTH_INDEX     ham 67  →  67
  +3   SEVERITY         ham 4  →  ACIL
  +6   THETA_MAX        ham 188  →  18.8 K
  +7   THETA_MAX_JOINT  ham 25  →  C07-L2-PABUC
  +9   SENSITIVITY_PCT  ham 100  →  100 %
  +45  DATA_AGE_S       ham 5  →  5 s
FC 06 · 1624 adresine yazma deneniyor…
  REDDEDİLDİ: exception 0x01 (ILLEGAL FUNCTION). Harita salt okunur.
```

> "Bu, dağıtım şirketinin SCADA'sının gördüğü şey: bin altı yüz yirmi dört numaralı adresten
> başlayan kırk sekiz register. θ'nın ham değeri [188], ölçek 0,1: [18,8] kelvin — arayüzdekiyle
> aynı sayı, çünkü ikisi aynı nesneden geliyor. Ve yazmayı deniyorum: **exception sıfır bir,
> ILLEGAL FUNCTION.** Modbus'ta kimlik doğrulama yok; ark rölesine komut verebilen bir sisteme
> kimliksiz yazma yolu açmıyoruz."

**Alternatif:** Terminal istemezseniz arayüzdeki **SCADA (S6)** ekranı aynı register bloğunu
canlı gösterir; yazma reddini slayt 15'ten anlatın.

**Beat 7 · Kör olduğumuz yer (20 sn)**
**Tıklama:** **Filo (S1)** → süzgeç şeridindeki **Görüşü kısıtlı** düğmesi → listelenen bir pano.
Gerekçe metni (örn. "Yük faktörü %33. Görülebilir en küçük θ, 3σ/f² = 5,4 K'e çıktı. Bu bir pano
arızası değil, bir görünürlük durumudur…") **Alarmlar → Bastırılan** sekmesinde de
`SENSITIVITY_LOW` satırı olarak durur. Gece saatlerinde sayı slayt 11'deki 18,5 K'e yaklaşır.

> "Bu panolarda yük düşük. Rakip bir ürün burada 'her şey normal' der. Biz 'şu anda [gerekçedeki
> θ_min, örn. 5,4] kelvinin altındaki bir kusuru göremiyorum' diyoruz. Bu bir arıza değil, görünürlük
> durumu; SCADA'da da ayrı bir bit. Mutlak limitler bu sırada da açık."

**Beat 8 · Kapanış (15 sn)**

> "Gördüğünüz her ekran internetsiz, tek komutla bu bilgisayarda çalışıyor. Kamu bulutu yok."

**Alt+Tab** ile desteye dönün, **17** Enter (ya da →) ve saha uygulamasıyla devam edin.

### 8.4 Demoda gösterilmeyenler (ve neden)

- **Sıcak hava dalgası:** Senaryo ortamı 12 saatte tırmandırır ve ayrı bir bastırma satırı
  üretmez (θ zaten değişmediği için alarm koşulu hiç oluşmaz). Hikâyesini slayt 5 ve 12 anlatır.
  Demoda "sıcak hava dalgası satırı" vaat etmeyin.
- **Canlı `modpoll`:** Bu bilgisayarda kurulu değil; yerine `sunum\scada_kanit.py` aynı işi yapar.
- **Ark dedektörü arızası, yoğuşma, aşırı yük gibi diğer senaryolar:** Isıl senaryolar
  bağlantının zaman sabiti kadar (~15 dk) gecikir; 5 dakikalık demoya sığmaz. Jüri sorarsa
  **Demo** çekmecesindeki 17 senaryonun listesini gösterin.

### 8.5 Süre daralırsa: kesme sırası

1. Beat 6 SCADA → tek cümle: "SCADA bloğu 1624'te, yazma 0x01 ile reddediliyor" (−25 sn)
2. Beat 7 görünürlük → tek cümle (−15 sn)
3. Beat 3 içindeki CUSUM cümleleri → yalnız tarih ve kalan gün (−15 sn)
4. Beat 2 → "kırk bağlantı ölçülüyor, gerisi gri" (−20 sn)

**Beat 4 ve 5 hiçbir koşulda kesilmez.**

### 8.6 Bir şey ters giderse

| Belirti | Ne yapın |
|---|---|
| Sayfa açılmıyor | PowerShell'de `.\baslat.ps1 -Panels 24 -BackfillDays 45 -Reset` yeniden (~10 sn). Olmazsa desteye dönün, slayt 16'nın ekran görüntüleriyle anlatın |
| Filo "Veri bayat" ile dolu | Bilgisayar yetişemiyor: başka programları kapatın, 24 pano ile yeniden başlatın |
| Ark alarmı 20 sn'de gelmedi | Komutun çıktısında `ok: True` var mı bakın; yoksa adres/port yanlıştır. Gelmezse slayt 13'ten anlatın |
| Bastırılan sekmesinde şebeke olayı yok | T−20'deki enjeksiyon unutulmuş: Demo çekmecesinden TURGUTLU-02'ye şimdi enjekte edin (< 1 dk) |
| `scada_kanit.py` "açılamadı" diyor | Demo 5020 dışında bir SCADA portuyla başlatıldıysa `--port` verin |

**Demodan sonra sıfırlamak için:** Demo çekmecesinin altındaki **Demoyu sıfırla**, ya da
yeniden `-Reset` ile başlatma.

---

## 9. Jüri soruları ve hazır cevaplar

Canlı destede **Q** tuşu S1–S22'yi arama kutulu bir panelde açar.

**S1 · Kalibrasyonu nasıl yapıyorsunuz?**
θ bir farktır; iki sensörün ortak sapması çıkar. Mutlak doğruluk yalnız 110/130 °C limitleri
için gerekir ve TMP117 fabrikada ±0,1 °C'dir. IR dizisinde kardeş-fark gürültüsü 0,8 K alınır.

**S2 · Yükü nereden biliyorsunuz? Çıkışlarda CT yok.**
Doğru: dağıtım şirketinin CT'si yalnız girişte (2500/5). Bu yüzden her kelepçe kendi split-core
CT'sini taşır. Kalan 34 pabuçta yük, analizörün faz akımından orantısal pay ile kestirilir ve
ekranda öyle etiketlenir.

**S3 · Neden bara bölmesine koymuyorsunuz?**
Panoda AG giriş kesicisi yok (Madde 2.2.10.2.vi). Enerjisiz yapmak tüm dağıtım merkezini OG
tarafından karartmak; enerjili açmak 2312 A'lik çıplak bara üzerinde çalışmak demek. Bara
bölmesinin 30 + çatının 4 bağlantısı için periyodik termografi sürer, sıklığı düşer.

**S4 · Yapay zekâ nerede?**
Kasıtlı olarak yok. Kayan pencerede eğitilen bir otokodlayıcı, avladığımız 0,2 K/hafta
sürüklenmesini öğrenir ve yeniden üretir: yapısal körlük. Aylarca temiz geçmiş ister (yok), 100
panoya 100 model işletme yükü getirir. Kullandığımız: fizik tabanlı kestirici + istatistiksel
süreç kontrolü + tavanlı olabilirlik füzyonu; hepsinin birimi var. Saha verisi biriktikçe
yöntem, etiketli pilot verisiyle kalibre edilir.

**S5 · PD ölçümünüz IEC 60270'e göre mi?**
Hayır ve iddia etmiyoruz. 400 V'ta klasik PD oluşmaz (Paschen minimumu 327 V). RF kanalı gevşek
bağlantı mikro-arkını ölçer, pC eşdeğeri raporlar ve AG'de tek başına ekip yönlendirmez.

**S6 · Yanlış alarm hızınız ne?**
Analitik: 100 pano × 40 bağlantıda 4,8 günde bir yanlış CUSUM geçişi. Ama geçiş alarm değildir;
alarm üç şart ister (CUSUM > 8, θ ≥ 5 K, son 5 günün 3'ü). Bu bir üst sınırdır. Gerçek oran
ancak etiketli pilot sahada ölçülür.

**S7 · Standart hangi sıcaklığı yasaklıyor?**
TS EN 61439-1, bara cıvatalı bağlantısı için sayısal limit koymaz. 110/130 °C bizim mühendislik
çıkarımımızdır ve öyle etiketlidir (105 °C kablo yalıtımı, 120 °C üstü oksidasyon, kalayın 232 °C
erimesi). Çizelge 8 değerleri gelirse tek satırda değişir.

**S8 · Pil ne kadar dayanır?**
Hesaplandı, ölçülmedi: 8,4–16 yıl; bağlayıcı düğüm PD-01 (≈ 8,4 yıl). Kelepçe görev karmasıyla
13,1 yıl. Tezgâh ölçümü açık sorular listemizde. Pil zayıflarsa `CELL_LOW` cihaz iş emri açılır.

**S9 · Bozulma hızlanırsa "eşiğe kalan gün" ne olur?**
Model doğrusal ve ekranda yazıyor. Isıl kaçış süper-doğrusaldır; o modda sayı iyimserdir, gerçek
tarih daha erken olabilir. Süper-doğrusal model kalibre edecek saha verisi olmadan bir iddia
olurdu. 21 günde 14 geçerli gün yoksa sayı verilmez. Nominal %90 aralığın simülasyondaki
kapsaması %88–93.

**S10 · Neden Sparkplug B değil?**
Sparkplug 3.0 DDATA için QoS 0 zorunlu kılar; dayanıklılığımız PUBACK ile ilerleyen
store-and-forward filigranına dayanır. Doğum/vasiyet/monoton sıra numarası fikirlerini aldık,
rozeti bıraktık.

**S11 · Gerçekten SMS gidiyor mu? WhatsApp?**
GSM modem AT diyaloğu ve SMPP oturumu simüle edilir, transkript kaydedilir; gerçek kanaldan mesaj
gitmedi. Mesaj gövdesi, UCS-2 bütçesi, onay kodu, merdiven ve fırtına tavanı kodlu ve testli.
WhatsApp bulut tarafı gerektirdiği için yalnız "pano + seviye + onay kodu" çıkan bir DMZ
aynalama servisi önerildi, kurulmadı.

**S12 · Neden bulut yok? Ölçek için gerekmez mi?**
Gerekçe kurumsal: şebeke topolojisi ve arıza geçmişi kritik altyapı verisi. Teknik olarak da
gerekmiyor: 100 pano ≈ 18 GB disk, 1000 pano tek çekirdeğin dörtte biri. 500 GB NVMe 100 panoda
25 kat baş boşluğu bırakır.

**S13 · 1000 / 10 000 panoda ne olur?**
1000 pano: 4 vCPU / 16 GB, tek Mosquitto. 10 000: bölge başına (ADM / GDZ, sonra il) yığın +
federe salt okunur görünüm, bölge başına broker, ağ geçitlerinde 0–300 sn jitter. SQLite ~10 000'de
biter; TimescaleDB sürücüsü yazılmadı. ICD MAX_PANELS = 200.

**S14 · Verilen veriyi neden kullanmadınız?**
Sentetik: lag-1 otokorelasyon +0,0003 (gerçek fiderde > 0,97), altı bağımsız test. Sıcaklık-nem
sayfası boş, etiketli arıza yok, kardeş yapısı yok. Fizikten türetilmiş dijital ikiz kurduk ve
verilen kümeyi de aynı kabul testlerinden geçirdik.

**S15 · OG hücreler ne olacak?**
OG çizimi verilmedi; istedik. docs/10 jenerik 36 kV kablo bölmesi için konsept: HFCT kablo
ekranı topraklamasında, TEV, ultrasonik, kablo başlıklarında θ. Hücre başına ~€502 (özel HFCT).
Montaj planlı bakım penceresine eklenir.

**S16 · Kurulum için kesinti gerekir mi?**
Hayır: kit yalnız alt kablo bölmesi, ölçü kolonu DIN rayı ve mevcut 10 A prize dokunur. Tek
istisna RS-485'in TVOC-2 ve MPR-53CS'e indirilmesi: DSO kuralı enerjili iletken indirmeye izin
vermezse planlı kesintiye ertelenir; sistem RS-485'siz de çalışır.

**S17 · SCADA'dan komut verebilir miyiz?**
Hayır. Modbus slave istisnasız salt okunur; FC 05/06/15/16 exception 0x01 döner. TVOC-2 otokontrol
ve açma sıfırlama yalnız ağ geçidinde, operatör kimlik doğrulaması ve fiziksel anahtar arkasında.

**S18 · Sensör arızası sağlam bir bağlantıyı sıktırır mı?**
Hayır. DEVICE_MOUNT_LOST, AIM_SHIFTED, DRIFT, STUCK, CELL_LOW cihaz iş emri üretir, pano iş emri
asla. Kelepçe düşerse okunan sıcaklık havanınkidir; tork iş emri yapısal olarak engellenir.

**S19 · Nem ve yoğuşmayı nasıl izliyorsunuz?**
Su havadan değil, çiy noktasının altındaki yüzeyde yoğuşur. Duvar sıcaklığını havanın τ ≈ 90 dk
gecikmesi olarak modelliyoruz; pay = T_duvar − T_çiy. Boolean değil pay raporlanır. Tek başına
İzle/Uyarı; yükselen PD ile birlikte Kritik.

**S20 · Ağ geçidi ile sunucu bağlantısı koparsa?**
Üç yerel kural çalışmaya devam eder (≥ 90 °C, Δ ≥ 20 K, ark). 20 000 çerçeve halka tamponda
tutulur, PUBACK geldikçe filigran ilerler; ark olayı tamponun başına alınır. Tampon dolarsa en
eskiler düşer ve düşen sayısı bir sağlık metriği olarak yayınlanır.

**S21 · Maliyeti ne, ne zaman geri öder?**
Modül donanımı €470,59 (1000 adet) / €660,91 (100 adet), kurulum €150. 100 pano tekdüze: 6,9 yıl
(5 yılda −€30 166). Aynı 100 modül en kötü ondalıkta: 2,2 yıl. 1000 pano tekdüze: 3,3 yıl.
Faydanın %43,5'i tespit oranından bağımsız (termografi ziyareti).

**S22 · Kardeş fazlardan ikisi birden bozulursa?**
Medyan kendisi hariç iki kardeşten alınır, yani ikisinin ortalamasıdır. İki faz eşit bozulursa
her birinin θ'sı yaklaşık yarıya iner ama görünür kalır; sağlam üçüncü faz negatif θ gösterir.
Üç faz birden ve aynı hızda bozulursa θ bunu görmez: bu yöntemin kör noktasıdır ve onu her
koşulda açık olan mutlak limitler (90/110/130 °C) kapsar. *(Formülden türetildi, belgede ayrıca
yazılı değil; provada bir kez üzerinden geçin.)*

**Ek sorular (destede yok):**

**S23 · Manyetik alan cihazları etkilemez mi?**
Bara yüzeyi ~14,5 mT; kelepçenin kendi damarında 5,3 mT; diğer cihazlar < 0,25 mT. NdFeB kaide
etkilenmez. HFCT faz iletkenine takılmaz (takılırsa 400 A × 6 mV/A = 2,4 V kaçak; otomatik
doğrulama yakalar).

**S24 · Neden 868 MHz? Neden LoRa / Wi-Fi / BLE değil?**
Kavite argümanı: sac kutunun güvenilir tek açıklığı tabandaki ≥ 400 mm boşluk. 868 MHz'in
345 mm'lik dalga boyu bu yarıktan kuplaj yapar; 2,4 GHz'in 125 mm'si yapmaz ve kutu içinde derin
sıfırlar üretir. Kabin içi mesafe ~1,2 m; FSK, 14 dBm yeter. Ağ geçidi dışarıya LTE Cat-1 ya da
Ethernet ile çıkar.

**S25 · Siber güvenlik?**
Panoya giden komut yolu yok (tek yön). SCADA salt okunur. Her ağ geçidi kendi X.509 sertifikasıyla
bağlanır; ACL yalnız kendi panosunun konusuna yayın izni verir, ele geçirilmiş bir ağ geçidi
filo çapında sahte alarm üretemez. Üretimde süreç OT bölgesinde (IEC 62443-3-3, SL 2) mTLS
sonlandıran bir ters vekil arkasında. **Dürüst sınır:** mTLS/ACL tasarlandı, saha
sertifikalarıyla denenmedi; demo localhost'ta düz HTTP.

**S26 · Firmware güncellemesi (OTA)?**
İmzalı OTA politikası ve firmware'de OTA durum makinesi var; dağıtım altyapısı kurulmadı.

**S27 · Demo verisi gerçek mi?**
Hayır: fizikten türetilmiş dijital ikiz (yük profili, ısıl model, TVOC-2 ve MPR-53CS register
sunucuları). Şartname bunu açıkça kabul ediyor. Ekranlardaki her sayının arkasında aynı
dedektör kodu çalışıyor; sahada yalnız veri kaynağı değişir.

**S28 · Termal kamera / IR dizisi ile neden yetinmiyorsunuz?**
IR kardeş-fark gürültüsü 0,8 K, kelepçeninki 0,2 K; θ_min 3σ/f² olduğu için kelepçe dört kat
küçük kusuru görür. Ayrıca IR'nin kendi akımı yok. En yüklü iki fidere kelepçe, kalan 34 pabuca
IR: maliyet ile görünürlük arasındaki denge.

**S29 · Saha ekibi nasıl kullanır?**
Yalnız Kritik ve Acil telefonu çalar; mesajda pano, bağlantı, yapılacak iş ve onay kodu var.
Uyarı planlı iş emridir. Pano iş emri ile cihaz iş emri ayrı. Devreye alma telefonla.

---

## 10. Söylenmeyecekler: dürüst sınırlar

| Söylemeyin | Doğrusu |
|---|---|
| "PANO GÖZ arkı önler / pano korur" | Koruma TVOC-2'de (~1 ms, SIL-2). Biz gözler, konumlandırır, zaman damgalar, haber veririz |
| "Bildirim 5 saniyede gelir" | 4–13 saniyelik **aralık** |
| "SMS ve WhatsApp gönderiyoruz" | SMS ve sesli arama **simüle**; WhatsApp yok |
| "Sahada doğrulandı" / "yanlış alarm oranımız X" | Hiçbir başarım sayısı saha verisiyle doğrulanmadı; pilot ölçecek |
| "Geçmiş veri gerekmez" (koşulsuz) | Yalnız kardeş karşılaştırması için. Sürüklenme 5 gün, eşiğe kalan gün 14/21 gün ister |
| "KiCad / PCB tasarımı hazır" | Blok şema, I/O, pin dizilimi, BOM düzeyinde; çizilmedi |
| "Pil 13 yıl dayanır" | Hesap; tezgâhta ölçülmedi. Bant 8,4–16 yıl |
| "Enerji hasadı yapıyoruz" | İddia edilmiyor |
| "IEC 60270 uyumlu PD ölçümü" | pC eşdeğeri; IEC 60270 izlenebilir değil |
| "110/130 °C standart limit" | Mühendislik çıkarımı; standart sayı koymuyor |
| "10 000 panoyu test ettik" | Ölçülen en büyük filo 112; 10 000 kestirim |
| "TimescaleDB kullanıyoruz" | Hedef; bugün SQLite |
| "IEC 104 / OPC UA destekliyoruz" | Nokta listesi var, sunucu yok |
| "Verilen veri sahte, yanlış hazırlanmış" | "Sentetik; sonuçlarını dikkate aldık" (ton: suçlama değil) |

---

## 11. Ezber kartı

**Pano:** 1600 kVA · TEDAŞ-MLZ/2003-06.B · EK-II/14 · 2312 A ana bara · 38 kA rms / 80 kA tepe ·
1600×1500×450 mm · IP2X · Form 2B · AG giriş kesicisi yok (2.2.10.2.vi)

**Modül:** 9 cihaz = 6 TC + 1 TN-IR + 1 PD-01 + 1 GW-01 · 74 bağlantı modellendi, 40 ölçülüyor ·
34 pabuç yalnız IR · Çıkış 6 ve 7 · €470,59 (1000 ad.) / €660,91 (100 ad.) · kurulum €150

**θ:** [T − medyan(kardeşler, kendisi hariç)] / (I/I_ref)² · (71,90 − 69,05)/0,67² = 6,35 K ·
hava dalgasında Δθ = 0,0000 K

**Seviyeler:** İzle ≥ 2 K · Uyarı ≥ 5 K · Kritik ≥ 12 K · Acil ≥ 25 K · mutlak 90/110/130 °C

**Tespit:** CUSUM k = 0,5, h = 8 · alarm = CUSUM > 8 **ve** θ ≥ 5 K **ve** 3/5 gün · eşiğe kalan
gün için 21 günde ≥ 14 geçerli gün · %90 aralık, ölçülen kapsama %88–93

**Görünürlük:** θ_min = 3σ/f² · kelepçe σ 0,2 K, IR 0,8 K · f = 0,18 → 18,5 K · f < 0,35 görünürlük düşük

**Ark:** ~1 ms SIL-2 (TVOC-2) · bildirim 4–13 s · X2:3, K5 · reg 1300 · 222/223 yalnız X2 ve X3

**Bildirim:** yalnız Kritik/Acil telefon · iki sensör ailesi · Kritik 24 sa bekleme (Acil muaf) ·
UCS-2 · onay kodu · eskalasyon Acil 15 dk, Kritik 45 dk · fırtına tavanı 8 Kritik/sa (Acil muaf)

**SCADA:** 1000 + 48 × (n − 1) · SOKE-14 = 1624 · 48 register · salt okunur, yazma → 0x01 ·
100 pano = 39 istek, 19 ms · MAX_PANELS 200

**Ölçek:** 100 pano 15 zarf/sn, %2,2 çekirdek, 18 GB · 1000 pano %21,6, 180 GB, 4 vCPU/16 GB ·
ölçülen en büyük 112 pano

**Maliyet:** 100 pano eşit → 6,9 yıl, 5 yılda −€30 166 · en kötü %10 → 2,2 yıl, +€143 109 ·
1000 pano → 3,3 yıl · faydanın %43,5'i tespitten bağımsız

**Saha:** 2 kişi, 2,5 sa, kesinti yok · > 110 °C ise dur · 7 gün öğrenme · 100 modül = 25 ekip-günü

**Pil:** kelepçe 8,89 µA → 13,1 yıl · PD-01 ≈ 8,4 yıl · bant 8,4–16 yıl · hesap, ölçüm değil

**Verilen veri:** 152 satır · lag-1 +0,0003 (gerçek > 0,97) · RASTGELEARADA(15;90) · sıcaklık-nem boş

**Proje:** ≈ 33 bin satır Python · 4,5 bin C99 · 7,9 bin JS · 172 test · 11 belge + ICD · 17 senaryo

---

## 12. Sunum günü kontrol listesi

**Bir gün önce**
- [ ] Bu belgeyi baştan sona bir kez sesli okuyun; §6'dan bir süre planı seçin.
- [ ] Demoyu §8.1'e göre bir kez baştan sona prova edin (ark komutu ve `scada_kanit.py` dahil).
- [ ] PDF'i teslim edin: `sunum/PANO-GOZ-Final-Sunumu.pdf`.
- [ ] Sunum bilgisayarında `sunum/index.html`'in internetsiz açıldığını kontrol edin.

**Sunum öncesi (T−30 dk)**
- [ ] Ağır programları kapatın; şarj kablosu takılı, uyku modu kapalı, bildirimler sessiz.
- [ ] `.\baslat.ps1 -Panels 24 -BackfillDays 45 -Reset` → tarayıcı açıldı, harita doldu.
- [ ] T−20: TURGUTLU-02'ye şebeke olayı enjekte edildi; Alarmlar → Bastırılan'da satır görünüyor.
- [ ] Pano seçici tekrar SOKE-14'te.
- [ ] İki PowerShell penceresi hazır (ark komutu, `scada_kanit.py`), çalıştırılmadı.
- [ ] Bugünün SOKE-14 sayıları not edildi: θ ___ K · ACİL'e ___ gün (___–___) · başlangıç ~___.
- [ ] `sunum/index.html` tam ekranda (F); ikinci ekran varsa **S** ile konuşmacı ekranı.
- [ ] Projektörde koyu tema okunuyor mu? Okunmuyorsa demoda açık temaya geçin.

**Sunum sırasında**
- [ ] Slayt 16'da Alt+Tab ile tarayıcıya; demodan sonra Alt+Tab ve `17` Enter.
- [ ] Beat 4 (bastırılan) ve Beat 5 (ark) asla kesilmez.
- [ ] Sayıları ekrandan okuyun.
- [ ] Kapanıştan sonra susun; sorularda **Q**.
