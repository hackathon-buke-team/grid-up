# 08 · Demo Senaryosu — 5 dakika

Sunumu yapan kişi bu belgeyi ezberlemez, **okur**. Her beat'in repliği, ekranı, tıklaması,
ekranda görünen her sayının aritmetiği ve süre daralırsa nereden kesileceği yazılıdır.

**Demo panosu:** `SOKE-14` · pano indeksi 14 · Modbus blok adresi **1624**
(`1000 + 48 × 13`).

**Asla kesilmeyen iki beat:** ARK OLAYI (§4) ve BASTIRILMIŞ ALARM (§3). Süre daralırsa
kesme sırası §8'dedir.

**Açılış komutu (sunumdan 2 dakika önce çalıştırılır):**

```powershell
.\baslat.ps1
```

Arayüz `http://127.0.0.1:8080/`, SCADA `127.0.0.1:5020`. Demo panosu **SOKE-14**, kontrol
(negatif) panosu **TURGUTLU-02**. Senaryo uçları: `GET /api/scenarios`,
`POST /api/scenario/{key}`, `POST /api/demo/clear-faults`, `POST /api/demo/reset`.

⚠ **`--no-backfill` ile başlatmayın.** 3. beat'in tarihli değişim noktası, geçmiş veri
olmadan hesaplanamaz; varsayılan 75 günlük geri doldurma zorunludur.

---

## 0. Zaman planı

| Beat | Süre | Başlangıç | Kesilebilir mi |
|---|---:|---:|---|
| 1 · Tez | 35 s | 0:00 | Hayır (kısaltılabilir) |
| 2 · Dijital ikiz ve canlı θ | 45 s | 0:35 | Kısaltılabilir |
| 3 · Yavaş bozulma ve tarih | 50 s | 1:20 | Kısaltılabilir |
| 4 · **BASTIRILMIŞ ALARM** | 45 s | 2:10 | **ASLA** |
| 5 · **ARK OLAYI** | 45 s | 2:55 | **ASLA** |
| 6 · SCADA kanıtı | 40 s | 3:40 | Kesilebilir |
| 7 · Kör olduğumuz yer | 25 s | 4:20 | Kesilebilir |
| 8 · Kapanış | 15 s | 4:45 | Kısaltılabilir |

---

## 1. Tez · 0:00 – 0:35

**Ekran:** Filo haritası. 112 pano, Ege ve Güney Ege. Üçü sarı, biri kırmızı.
**Tıklama:** yok.

> "Bu 112 tane 1600 kVA'lık TEDAŞ alçak gerilim panosu. Her yarışmacı bunlardan birine
> termometre koyar ve bir eşiğin üstünde alarm verir. Bu sahada çalışmaz — çünkü bir
> bağlantının sıcaklığını durumu değil, **yükü ve mevsimi** belirler.
>
> Şubat sabahı 62 derece okuyan bir pabuç kusurludur. Ağustos öğleden sonrası tam yükte
> okunan aynı 62 derece normaldir. Eşik ağustosu atlatacak kadar yüksek olmak zorunda,
> dolayısıyla şubatta kör.
>
> Biz **θ**'yı ölçüyoruz: bir bağlantının **kendi iki kardeş fazına** göre sıcaklık fazlası,
> anma akımına normalize edilmiş hâli. Yük bölünerek düşüyor, ortam çıkarılarak düşüyor. Ve
> **geçmiş gerektirmiyor** — bir bara üzerindeki üç özdeş faz, montaj gününde geçerli bir
> referanstır."

**Ekranda formül kartı:**

```
θ = [ T − medyan(kardeşler) ] / (I / I_ref)²
```

---

## 2. Dijital ikiz ve canlı θ · 0:35 – 1:20

**Ekran:** `SOKE-14` panosunun dijital ikizi — EK-II/14 kesiti, 74 cıvatalı bağlantı, 9
cihaz noktası.
**Tıklama:** haritada `SOKE-14` → panoya gir → `C06 / L2 / çıkış pabucu` bağlantısına tıkla.

> "Tek panoya girelim. **Dokuz cihaz** — bu sayı donmuştur, sayabilirsiniz. Altı ısıl
> kelepçe iki fiderin üç fazında, bir termal dizi 48 pabuç sırasına bakıyor, bir RF düğümü
> topraklama saplamasında, bir ağ geçidi ölçü kolonunda.
>
> **Yetmiş dört** cıvatalı bağlantı var — tasarımda kırk sekiz pabuç pozisyonu vardır ama iki
> Yedek yol şartname gereği boş bırakılır. Kırk tanesini ölçüyoruz. Kalan otuz dördü ekranda
> gri: bara bölmesinde ve çatıda. Onlara **giremiyoruz**, çünkü bu panonun AG giriş kesicisi
> yok — kapağı açmak dağıtım merkezini karartmak demek. Gri renk bir eksiklik değil,
> bir **beyandır**."

**Tıklama:** `C06 / L2` bağlantısı → kanıt paneli açılır.

**Ekranda görünen ve aritmetiği:**

| Ekrandaki değer | Nereden geliyor |
|---|---|
| `T = 71.9 °C` | TC-02 TMP117 ham okuma |
| `Kardeş medyanı = 69.05 °C` | L1 = 68.9, L3 = 69.2 → medyan(68.9, 69.2) = 69.05. **Kendisi hariç** |
| `Fark = 2.85 K` | 71.9 − 69.05 |
| `I = 268 A · f = 0.670` | Kelepçenin kendi split-core CT'si; 268 / 400 A anma |
| `f² = 0.4489` | 0.670² |
| **`θ = 6.35 K`** | 2.85 / 0.4489 |
| `θ_min = 1.34 K` | 3 × 0.2 K / 0.4489 — **görülebilirlik tabanı** |
| `Görünürlük: %100` | θ_min (1.34 K) < uyarı eşiği (5 K) |
| `ΔR = 9.9 … 19.8 µΩ` | 6.35 / (R_th × 400²); R_th = 4 → 9.9 µΩ, R_th = 2 → 19.8 µΩ |
| `Fazla kayıp = 1.6 … 3.2 W` | ΔR × 400² |

> "Altı virgül üç beş kelvin. Bu, **bugünkü sıcaklık değil** — bu bağlantı anma akımını
> taşısaydı kardeşlerinden ne kadar sıcak olacağının ölçüsü.
>
> Ve fazla temas direncini **tek bir sayı olarak vermiyoruz**: dokuz virgül dokuz ile on
> dokuz virgül sekiz mikroohm arası. Çünkü yerel ısıl direnç bir çarpan kadar biliniyor.
> Tek sayı verseydik, o sayı uydurma olurdu."

---

## 3. Yavaş bozulma ve başlangıç tarihi · 1:20 – 2:10

**Ekran:** aynı bağlantının 90 günlük θ grafiği, CUSUM izi, değişim noktası işareti.
**Tıklama:** kanıt panelinde `Geçmiş` sekmesi.

**Ekranda görünen ve aritmetiği:**

| Ekrandaki değer | Aritmetiği |
|---|---|
| `CUSUM = 14.2` | k = 0.5, h = 8, günlük medyan üzerinde. 14.2 > 8 → geçti |
| `Eğim = +0.31 K/hafta` | 21 günlük pencerede Theil-Sen |
| `Başlangıç: ~14 Temmuz, ±3 hafta` | İkili bölütleme + BIC testi; **rampaya basamak uydurmanın medyan gecikmesi +18 gün** olduğu için aralık verilir |
| `41 gün önce` | Bugün − 14 Temmuz |
| `Nitelikli gün: 4/5` | Son 5 günün 4'ünde θ ≥ 5 K |
| `Sağlık endeksi: 75` | HI = 100 × (1 − 0.62)^0.30 = 74.8 → 75 |
| `Şelale: gevşek bağlantı −25.2` | ln(HI/100) = Σ w·ln(1−r); tek modlu olduğu için tüm eksiklik ona düşer |
| `Seviye: KRİTİK` | θ = 6.35 K, iki bağımsız aile (TC + IR) hemfikir |

> "CUSUM bu bağlantının **sürüklendiğini** söylüyor: on dört virgül iki, eşiğimiz sekiz.
> Ama asıl cümle şu: **bu bozulma yaklaşık 14 Temmuz'da başladı, kırk bir gün önce.**
>
> Bunu söyleyebilmemizin sebebi CUSUM değil — CUSUM zaten gecikir, 0.2 K/hafta'lık bir
> sürüklenmede eşiği otuz beş gün sonra aşar. Tarihi, tüm seri üzerinde geriye dönük bir
> değişim noktası kestirimi veriyor.
>
> Ve tarihi **üç haftalık bir belirsizlikle** veriyoruz, çünkü bozulma bir basamak değil bir
> rampa; basamağı rampanın ortasına oturtuyoruz. Kesin tarih vermek burada sahte kesinlik
> olurdu — planlayıcı o günkü manevra kaydını açar ve olmayan bir şeyi arar."

**Ek cümle (varsa süre):**
> "Alarm üç şartın **hepsini** ister: CUSUM sekizi geçecek, θ beş kelvini geçecek ve son
> beş günün üçünde geçecek. Yalnız CUSUM geçtiğinde telefon çalmaz."

---

## 4. BASTIRILMIŞ ALARM · 2:10 – 2:55 · **ASLA KESİLMEZ**

**Ekran:** `Bastırılmış Alarmlar` ekranı. Son 24 saatte 7 satır.
**Tıklama:** üst menüde `Bastırılanlar` → ilk satırı aç.

> "Şimdi ürünün en önemli ekranı. Bu, **ürettiğimiz** alarmların değil, **üretmediğimiz**
> alarmların listesi. Gerekçeleriyle."

**Satır 1 — Sıcak hava dalgası:**

| Ekrandaki değer | Aritmetiği |
|---|---|
| `Ortam: 41.2 °C` | Dış hava; Tablo 1 dahili maksimumu 40 °C — **hizmet zarfı dışı bir bulgu** |
| `40 bağlantının tamamı birlikte +6.1 K` | Mutlak sıcaklıklar yükseldi |
| `Δθ = 0.0000 K` | **Ölçülen değer.** Kardeşler aynı havada; fark tam olarak sıfır |
| `Karar: alarm yok` | Bu pano hakkında değil, hava hakkında |

> "Kırk bağlantının hepsi altı kelvin birden ısındı. Bir eşik sistemi burada kırk alarm
> üretirdi. θ'nın değişimi **tam sıfır** — sıfır virgül sıfır sıfır sıfır sıfır. Çünkü
> kardeşler aynı havayı soluyor."

**Satır 2 — Şebeke olayı:**

| Ekrandaki değer | Aritmetiği |
|---|---|
| `THD_V: L1 %6.8 · L2 %7.1 · L3 %6.9` | Üçü birden yükseldi |
| `Taban çizgileri: %2.4 · %2.5 · %2.3` | Her faz kendi tabanının > %1.5 üstünde |
| `Karar: ŞEBEKE OLAYI ADAYI` | Harmonik modlar atfedildi; **ısıl bulgu silinmedi** |

> "Üç fazın gerilim bozulması **birlikte** yükseldi. Bu panonun kendisi bunu yapamaz —
> pano bir yüktür, kaynak değil. Kanıtı harmoniğin kendisi olan bulgular burada kapanır.
>
> Ama dürüst olalım: aynı ölçümü tesisin içindeki büyük bir sürücü ya da UPS de üretir,
> çünkü o yük bu panonun **beslediği** taraftadır ve harmonik akımı üç faza birden basar.
> Analizör ikisini ayırt edemez. Bu yüzden bunu bir **aday** olarak sınıflandırıyoruz:
> harmonik modlar bastırılır, ısıl bir bulgu ise yalnızca bir kademe geriletilir ve ekip
> yönlendirmesi **vetolanmaz**. Sıcak bir cıvata, gerilim bozunumu sürüyor diye
> bekletilmez — bozunum, zaten marjinal bir bağlantının bırakması için en olası andır.
>
> Atfın kesinleşmesi için panonun uyduramayacağı bir teyit isteriz: frekans penceresinin
> dışına çıkması, inrush sınıflandırması ya da filo genelinde eşzamanlılık. Frekans teyit
> ederse bayrak `GRID_DISTURBANCE` olur ve ekip vetosu o zaman devreye girer.
>
> Bu deseni tanımak, yüz panoyu yönetilebilir kılan şeydir. Aksi hâlde bölgesel bir olay,
> yüz dürüst dedektörden **yüz eşzamanlı alarm** üretir ve sistem üçüncü ayda kapatılır.
> Fazla tanımak ise daha kötüdür: gerçek arızayı siler."

**Kapanış cümlesi (bu beat'in can alıcı yeri):**
> "Bir operatör size 'yetmiş sekiz derece okumuşsun, neden bana söylemedin?' diye
> sorduğunda, cevap burada, kendi dilinde, sayılarıyla hazır duruyor. Bu bir hata ayıklama
> günlüğü değil — **kendi ekranı olan bir üründür.**"

---

## 5. ARK OLAYI · 2:55 – 3:40 · **ASLA KESİLMEZ**

**Ekran:** dijital ikiz. Kırmızı bir olay şeridi düşer.
**Tıklama:** demo kontrolünde `Ark olayı enjekte et` → olay kartını aç.

**Ekranda görünen ve aritmetiği:**

| Ekrandaki değer | Aritmetiği |
|---|---|
| `TVOC-2 reg 1300 = 0x0001` | bit0 = aktif açma |
| `Dedektör: X2:3` | Açma dedektör LOW kelimesi = `0x1000` → bit 12 → X2:1..X2:5 bit10–14 → X2:3 |
| `Röle: K5` | Röle bit alanı = `0x0002` → bit1 = K5 |
| `Açma süresi: ~1 ms` | ABB, ışıktan kontağa, SIL-2 donanım |
| `Bildirim gecikmesi: 4 – 13 s` | Aşağıdaki tablo |
| `Sağlam dedektör: 10/10` | reg 222/223 **yalnız X2 ve X3'ü kapsar**; 20 dedektörlü bir rölede X1'in 10'u **kapsam dışıdır** |

**Ekranda açılan gecikme tablosu:**

| Adım | Süre |
|---|---|
| TVOC-2 ışık → kontak | ~1 ms (**bizi beklemez**) |
| TVOC-2 Modbus görüntüsünün yenilenmesi | 0.2 – 2 s (**ABB dokümante etmiyor — modellendi**) |
| Ağ geçidi tarama periyodu | 1 s |
| Sunucu işleme | 0.3 – 2 s |
| SMS yolu | 2.5 – 8 s |
| **Toplam** | **4 – 13 s** |

> "Ark oluştu. **Biz açmadık.** ABB TVOC-2 açtı, yaklaşık bir milisaniyede, SIL-2
> donanımda. Bizim yaptığımız şey ark olduktan sonra başlar: hangi dedektör gördü — X2:3;
> hangi röle attı — K5; ne zaman oldu; ve nöbetçiye haber vermek.
>
> Ve gecikmeyi **tek bir temiz sayı olarak vermiyoruz**: dört ile on üç saniye arası.
> Çünkü TVOC-2'nin Modbus görüntüsünün ne kadar sürede güncellendiğini **ABB dokümante
> etmemiş**. Beş saniye deseydik, ölçmediğimiz bir şeyi ölçmüş gibi göstermiş olurduk.
>
> Bir şeye daha bakın: 'sağlam dedektör 10/10' yazıyor, ama bu röleye yirmi dedektör bağlı.
> Çünkü register 222 ve 223 **yalnız X2 ve X3 kartlarını** kapsıyor; X1'deki on dedektörün
> sağlığını **göremiyoruz** ve ekranda öyle yazıyor. Görmediğimiz şeyi gördü gibi
> göstermek, en tehlikeli hatadır."

---

## 6. SCADA kanıtı · 3:40 – 4:20

**Ekran:** terminal, yan yana iki pencere.
**Tıklama:** terminale geç.

```
modpoll -m tcp -0 -r 1624 -c 48 -p 5020 127.0.0.1
```

**Ekranda görünen ve aritmetiği:**

| Register | Ofset | Ham | Ölçek | Mühendislik | Aritmetiği |
|---|---:|---:|---|---|---|
| `PANEL_ID` | +0 | 14 | 1 | 14 | Pano indeksi |
| `HEALTH_INDEX` | +2 | 75 | 1 | 75 | §3 |
| `SEVERITY` | +3 | 3 | 1 | KRİTİK | 0 BILGI · 1 IZLE · 2 UYARI · **3 KRITIK** · 4 ACIL |
| `THETA_MAX` | +6 | 64 | 0.1 | **6.4 K** | 6.35 → round(6.35/0.1) = 64 |
| `THETA_MAX_JOINT` | +7 | 21 | 1 | `C06-L2-PABUC` | 40 elemanlı `JOINT_ORDER` dizisindeki sıra |
| `SENSITIVITY_PCT` | +9 | 100 | 1 | %100 | §2 |
| `DATA_AGE_S` | +45 | 2 | 1 | 2 s | Son güncellemeden beri |

> "Bu ekranda gördüğünüz altı virgül dört, **aynı nesneden** geliyor. Arayüzdeki sayı ile
> register'daki sayı çelişemez, çünkü ikisi de `PanelLive`'ın `to_registers()` çıktısı.
>
> On dört numaralı panonun adresi de kafadan atılmadı: bin artı kırk sekiz çarpı on üç,
> **bin altı yüz yirmi dört**. SCADA mühendisi tek blok tanımlar, yüz kez kopyalar."

**Tıklama:** ikinci komut.

```
modpoll -m tcp -0 -r 1624 -p 5020 127.0.0.1 1
→ Illegal Function exception response!
```

> "Ve yazmayı deneyin: **exception sıfır bir, ILLEGAL FUNCTION.** İstisnası yok. Modbus'ta
> kimlik doğrulama yoktur; ark rölesine otokontrol komutu verebilen bir sisteme kimliksiz
> yazma yolu açmak kabul edilebilir değil. O iki aktüatör yolu ağ geçidinde, operatör
> kimlik doğrulaması **ve fiziksel bir anahtar** arkasında."

**Ek (varsa süre):**
> "Yüz panonun tamamını taramak kırk sekiz çarpı yüz, dört bin sekiz yüz register eder ve
> FC 03'ün yüz yirmi beş register sınırı yüzünden **en az otuz dokuz istek** gerektirir;
> ölçtük, on dokuz milisaniye. 'İki istekte olur' demiyoruz, çünkü olmuyor."

---

## 7. Kör olduğumuz yer · 4:20 – 4:45

**Ekran:** başka bir pano, gece 03:00, yük faktörü %18.
**Tıklama:** haritada `NAZILLI-07`.

| Ekrandaki değer | Aritmetiği |
|---|---|
| `Yük faktörü: 0.18` | I_ort / 2312 A |
| `θ_min = 18.5 K` | 3 × 0.2 / 0.18² = 0.6 / 0.0324 = 18.5 |
| `Durum: GÖRÜNÜRLÜK DÜŞÜK` | f < 0.35 |
| `Mutlak limitler: AKTİF` | 90 / 110 / 130 °C her koşulda |

> "Bu pano gece yarısı, yüzde on sekiz yükte. Rakip bir ürün burada 'her şey normal' der.
> Biz **'şu anda on sekiz buçuk kelvinin altındaki bir kusuru göremiyorum'** diyoruz.
>
> Bu bir arıza değil, bir **görünürlük durumu** ve ayrı raporlanıyor — SCADA'da da ayrı bir
> bit. Mutlak sıcaklık limitleri bu sırada da açık: yüz otuz derece olan bir pabuç, yükün ne
> olduğundan bağımsız olarak yüz otuz derecedir.
>
> Kör olduğumuz yeri söylemek bir kusur değil, **ürünün özelliğidir.**"

---

## 8. Kapanış · 4:45 – 5:00

**Ekran:** iki kart yan yana — "Sağlanan veri sahtedir" ve "100 pano parasını geri ödemez".

> "İki cümle.
>
> **Bir:** bize verilen akım verisi sahtedir ve ispatı elimizde — lag-1 otokorelasyonu
> artı sıfır virgül sıfır sıfır sıfır üç; gerçek bir fiderde bu sayı sıfır virgül doksan
> yedinin üstündedir. Altı bağımsız test. O yüzden modeli o veriye uydurmadık, fizikten
> kurduk.
>
> **İki:** her panoya eşit dağıtılmış yüz modüllük bir pilot **parasını geri ödemez** —
> beş yılda eksi otuz bin euro. Başa baş yüz yetmiş beş panoda. Ama **aynı yüz modülü
> filonun en kötü ondalığına koyarsanız iki virgül iki yılda döner.** Soru kaç pano
> alacağınız değil, **hangi** panolara koyacağınız."

---

## 9. Süre daralırsa: kesme sırası

Kesmeler bu sırayla yapılır. **4 ve 5 numaralı beat'ler hiçbir koşulda kesilmez.**

| Sıra | Kesilen | Yerine | Kazanılan |
|---:|---|---|---:|
| 1 | §6 canlı `modpoll` | Ekran görüntüsü + "yazma reddediliyor, exception 0x01" cümlesi | 25 s |
| 2 | §7 görünürlük beat'i | Tek cümle: "Yük düşükken kör olduğumuzu ekranda yazıyoruz" | 20 s |
| 3 | §8'in birinci cümlesi (sahte veri) | README'ye referans | 8 s |
| 4 | §3 içindeki CUSUM açıklaması | Yalnız değişim noktası tarihi söylenir | 15 s |
| 5 | §2'deki 88/40 bağlantı açıklaması | "Kırk bağlantı ölçülüyor, gerisi gri" | 12 s |
| 6 | §1'in ikinci paragrafı | Doğrudan formüle geçilir | 12 s |

Tüm kesmeler uygulandığında demo **3 dakika 28 saniyeye** iner ve iki kritik beat tam
uzunlukta kalır.

---

## 10. Jüri sorularına hazır cevaplar

| Soru | Cevap | Referans |
|---|---|---|
| "Kalibrasyonu nasıl yapıyorsunuz?" | θ bir **fark**tır; her iki sensörün ortak sapması çıkar. Mutlak doğruluk yalnız 110/130 °C limitleri için gerekir ve TMP117 fabrikada ±0.1 °C'dir | [04] §1 |
| "Yükü nereden biliyorsunuz? Çıkışta CT yok ki." | Doğru — hiçbir çıkışta dağıtım şirketi CT'si yok, 2500/5 yalnız girişi ölçüyor. Bu yüzden **her kelepçe kendi split-core CT'sini taşıyor**. Kalan 34 pabuç için yük **kestiriliyor** ve ekranda öyle etiketleniyor | [02] §1.1 |
| "Neden bara bölmesine koymuyorsunuz?" | Panoda **AG giriş kesicisi yok**. Enerjisiz yapmak dağıtım merkezini karartmak demek | [05] §1 |
| "Yapay zekâ nerede?" | Kasıtlı olarak yok. Kayan pencerede eğitilen bir otokodlayıcı, avladığımız 0.2 K/hafta sürüklenmesini **öğrenir ve yeniden üretir** — yapısal olarak kör | [04] §11.3 |
| "PD ölçümünüz IEC 60270'e göre mi?" | **Hayır ve öyle olduğunu iddia etmiyoruz.** 400 V'ta klasik PD zaten oluşmaz (Paschen minimumu 327 V). pC **eşdeğeri** raporluyoruz ve AG'de tek başına ekip yönlendirmiyor | [04] §9.3 |
| "Yanlış alarm hızınız ne?" | Ölçülmüş: 100 pano × 40 bağlantıda **4.8 günde bir** yanlış CUSUM geçişi. Ama geçiş alarm değil — üç şart birden gerekiyor. Bu bir üst sınır | [04] §5.4 |
| "Standart hangi sıcaklığı yasaklıyor?" | **TS EN 61439-1 bara cıvatalı bağlantısı için sayısal limit koymaz.** 110/130 °C bizim mühendislik çıkarımımızdır ve öyle etiketlidir. Sert malzeme sınırı kalayın 232 °C erime noktasıdır | [04] §8.2 |
| "Pil ne kadar dayanır?" | Hesaplandı, **ölçülmedi**: 8.4–16 yıl, bağlayıcı düğüm PD-01. Tezgâh ölçümü açık sorular listemizde | [02] §5 |

---

## 11. Belgelendi, kodlanmadı

| Konu | Durum |
|---|---|
| Demo kontrol paneli ("ark olayı enjekte et" düğmesi) | **Çalışıyor**: 17 senaryo `sim/faults.py` içinde, uçları `GET /api/scenarios` ve `POST /api/scenario/{key}` |
| Sunum sırasında canlı `modpoll` | `modpoll` ikili dosyası depoda yok; jüri makinesinde kurulu olmalı ya da ekran görüntüsü kullanılır |
| Demoda geçen tarih ("14 Temmuz") | Değişim noktası kestiricisi tarihi **hesaplar**; buradaki tarih senaryonun enjeksiyon anına bağlıdır |
