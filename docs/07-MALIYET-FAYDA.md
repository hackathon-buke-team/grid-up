# 07 · Maliyet–Fayda

 > **K1 B1 maliyet revizyonu / 20.09.2026:** Aşağıdaki önceki maliyet-fayda senaryoları B1 tedarik teklifi değildir. Güncel [BOM](../hardware/B1/BOM.md) 214 satırdır; fiyatı doğrulanmış satırların 9 cihazlık kit ara toplamı **162,68 USD**, 206 satır için fiyat/MPN/termin teyidi gereklidir. Tam kit maliyeti = bu ara toplam + eksik teklifler + imalat/montaj + vergi/nakliye. Bunlar tamamlanmadan eski €470,59/€660,91 donanım toplamı veya geri ödeme yılı güncel sonuç olarak kullanılamaz. TC pil varsayımı yaklaşık 2 yıla indiği için 5 yıllık bakım/yenileme maliyeti de yeniden hesaplanmalıdır. K1 1.6 kısmen açıktır; güncel fiyatları eski EUR tahminleriyle kur belirtmeden toplamadık.

---

## 0. ÖNCE KÖTÜ HABER

> **Her panoya eşit dağıtılmış 100 modüllük bir pilot, 5 yıllık ufukta parasını
> geri ödemez.**
>
> * 5 yıllık toplam sahip olma maliyeti: **€154 591**
> * 5 yıllık toplam fayda (tekdüze filo): **€124 425**
> * **5 yıllık net: −€30 166.** Başa baş noktası **6.9 yıldadır.**
>
> Başa baş, **175 panoda** gelir.
>
> **Çözüm daha fazla pano almak değildir. Aynı 100 modülü, filonun en kötü
> ondalığındaki panolara koymaktır.** O durumda geri ödeme **2.2 yıla** iner.

Bu bölümü ilk yazmamızın sebebi şudur: bir dağıtım şirketinin varlık yönetimi ekibi bu
hesabı kendisi yapacaktır. Yapmadan önce biz yaparsak, geri kalan her sayı için de
güvenilir oluruz. Yapmazsak, sunumun on beşinci dakikasında bu sayı bize karşı kullanılır.

---

## 1. Varsayımlar — hepsi etiketli

Bu belgedeki her fayda kaleminin bir varsayımı vardır ve her varsayım **VARSAYIM** diye
işaretlidir. Bir tanesi bile ölçülmüş değildir; hepsi dağıtım şirketinin kendi kayıtlarından
doğrulanabilir ya da çürütülebilir. Bunları saklamak yerine listelemek, modelin kendisinden
daha değerlidir.

| # | Varsayım | Değer | Nasıl doğrulanır |
|---:|---|---:|---|
| V1 | Döviz kuru | **1 EUR = 47 TL** | Güncel kur |
| V2 | Yüklenmiş ekip maliyeti | €22 / kişi-saat | DSO bordro + genel gider |
| V3 | Kurulum süresi | 2 kişi × 2.5 saat + yol payı €40 → **€150/pano** | İlk 5 kurulumdan sonra ölçülür |
| V4 | Cihaz ömrü (pil düğümleri) | 9–16 yıl | [02] §5 — **hesaplandı, ölçülmedi** |
| V5 | Ağ geçidi ömrü | 10 yıl | Şebekeden beslenen, hareketsiz |
| V6 | SIM + veri | €30 / pano / yıl | Operatör teklifi |
| V7 | Platform işletmesi | 100 panoda €6 000/yıl, 1000 panoda €24 000/yıl | 0.1 → 0.25 FTE + sunucu + yedekleme |
| V8 | Tip testleri (10.10 + 10.12) | **€22 500 tek seferlik** | Akredite laboratuvar teklifi — bkz. [05] §9 |
| V9 | Mevcut termografi pratiği | Yılda 2 ziyaret × €65/pano | **DSO bakım bütçesinden bir öğleden sonrada doğrulanır** |
| V10 | Retrofit sonrası termografi | 3 yılda 1 ziyaret (bara bölmesi + çatı sapmaları için) | Politika kararı |
| V11 | Bağlantı kaynaklı plansız arıza hızı | **%1.2 / pano / yıl** | DSO arıza kayıtları |
| V12 | Bir plansız arızanın DSO'ya maliyeti | €4 800 | Acil ekip + DSYA/kablo + mesai |
| V13 | Pano yangını olasılığı | %0.05 / pano / yıl | DSO olay kayıtları |
| V14 | Bir pano yangınının DSO'ya maliyeti | €55 000 | Pano + trafo hasarı + geçici besleme |
| V15 | Ark-flaş yaralanması | 3 000 pano-yılında 1 | Sektör istatistiği |
| V16 | Ark-flaş yaralanmasının **DSO nakit** maliyeti | €70 000 | Tedavi, iş günü kaybı, soruşturma. **Toplumsal maliyet ayrı** |
| V17 | Tespit oranı (yakalayabildiğimiz kusur payı) | **%70** | [04] §3 görülebilirlik tablosundan türetildi: f ≥ 0.35 olan sürede kusurun görüldüğü olasılık |
| V18 | En kötü ondalıkta olay hızı çarpanı | **×4.0** (yönlendirme kaleminde ×2.0) | DSO arıza kayıtlarındaki pano bazlı çarpıklık |
| V19 | VoLL (kesilen enerjinin toplumsal değeri) | €3.2 / kWh | Karma AG yükü. **DSO nakit akışına sayılmaz** |
| V20 | Öğrenme eğrisi üssü | b = 0.1475 (`maliyet(N) = 470.59·(N/1000)^−0.1475`) | [03] §9.5'teki iki BOM noktasından |

---

## 2. Maliyet

### 2.1 Modül başına donanım

[03-ELEKTRONIK-DOKUMANTASYON.md] §9.5'ten:

| Kalem | 1000 adet | 100 adet |
|---|---:|---:|
| 6 × TC ısıl kelepçe | €177.90 | €255.60 |
| 1 × TN-IR termal dizi | €56.50 | €76.90 |
| 1 × PD-01 RF/ortam düğümü | €97.30 | €135.50 |
| 1 × GW-01 ağ geçidi | €112.25 | €155.50 |
| Lojistik, yedek, giriş testi (%6) | €26.64 | €37.41 |
| **Modül donanımı** | **€470.59** | **€660.91** |

Ağ geçidi amortismanı (V5, 10 yıl): **€11.2 – €15.6 / pano / yıl**. Pil düğümleri 9–16 yıl
(V4) ile 5 yıllık ufukta değiştirilmez; 8. yıldaki toplu hücre değişimi 5 yıllık modelin
**dışındadır** ve gösterge maliyeti modül başına €18 (hücre) + ziyaret payıdır.

### 2.2 Modül başına kurulum

| Kalem | Değer |
|---|---:|
| İşçilik: 2 kişi × 2.5 saat × €22 (V2, V3) | €110 |
| Araç + yol payı | €40 |
| **Toplam** | **€150** |

### 2.3 Sabit kalemler

| Kalem | Değer | Sıklık |
|---|---:|---|
| Sunucu (birincil + sıcak yedek) | €6 000 | Bir kez |
| **Tip testleri 10.10 + 10.12** (V8) | **€22 500** | Bir kez, tip başına |
| Platform işletmesi (V7) | €6 000 / yıl (100 pano) · €24 000 / yıl (1000 pano) | Yıllık |
| SIM + veri (V6) | €30 / pano / yıl | Yıllık |
| Yazılım lisansı | **€0** | Tüm yığın açık kaynak; sunucudan başka kalem yok |

Tip testleri 100 panoya bölününce modül başına **€225**, 1000 panoya bölününce **€22.50**
eder. Bu kalem, küçük pilotları orantısız cezalandıran tek kalemdir ve başa baş noktasını
yukarı iten üç etkenden biridir.

### 2.4 5 yıllık toplam sahip olma maliyeti

| | **100 pano** | **1000 pano** |
|---|---:|---:|
| Donanım (N × BOM) | €66 091 | €470 590 |
| Kurulum (N × €150) | €15 000 | €150 000 |
| Sunucu | €6 000 | €6 000 |
| Tip testleri | €22 500 | €22 500 |
| **CAPEX toplamı** | **€109 591** | **€649 090** |
| Yıllık OPEX (platform + SIM) | €9 000 | €54 000 |
| 5 yıllık OPEX | €45 000 | €270 000 |
| **5 YILLIK TCO** | **€154 591** | **€919 090** |
| Pano başına yıllık | **€309** | **€184** |
| TL karşılığı (V1) | **7.27 M TL** | **43.2 M TL** |

---

## 3. Fayda modeli

### 3.1 Tekdüze dağıtılmış filoda, pano başına yıllık

| # | Kalem | Hesap | €/pano/yıl | Tespit oranına bağlı mı |
|---:|---|---|---:|---|
| F1 | **Termografi ziyareti tasarrufu** | V9 (€130) − V10 (€21.7) | **€108.3** | **HAYIR** |
| F2 | Önlenen plansız arıza | V11 × V17 × V12 = 0.012 × 0.70 × 4 800 | €40.3 | Evet |
| F3 | Önlenen yangın | V13 × V17 × V14 = 0.0005 × 0.70 × 55 000 | €19.3 | Evet |
| F4 | Önlenen ark-flaş yaralanması (**yalnız DSO nakdi**) | (1/3000) × 0.40 × V16 | €9.3 | Evet |
| F5 | Hedefli ekip yönlendirme / kör araştırma tasarrufu | Yılda 1.7 kör araştırmanın önlenmesi × €22 | €38.0 | Kısmen |
| F6 | Kesinti süresi kalite yükümlülüğü / ENH | DSO regülasyon parametrelerinden | €34.0 | Evet |
| | **TOPLAM** | | **€248.9** | |

### 3.2 F1'i öne çıkarmak: tespit oranından bağımsız tek kalem

**Faydanın %43.5'i, hiçbir kusuru tespit etmesek bile gerçekleşir.**

Bugün bu panolara yılda iki kez müteahhit termal kamerayla gelir, kapağı açar, bakar,
fotoğraf çeker ve gider. Bu ziyaretin ürettiği bilgi, PANO GÖZ'ün **dakikada bir**
ürettiği bilginin bir örneklemesidir — üstelik o günün yükünde, o günün havasında ve o
teknisyenin açısından.

| Bugün | PANO GÖZ ile |
|---|---|
| 2 ziyaret/yıl × €65 = €130/pano/yıl | 3 yılda 1 ziyaret (yalnız bara bölmesi ve çatı sapmaları) = €21.7/pano/yıl |
| 730 günde 2 gözlem | 730 günde 1 051 200 gözlem (40 bağlantı × 1/dk) |
| Yük ve mevsim düzeltmesi **yok** | Her gözlem anma akımına normalize |
| Kayıt: fotoğraf ve PDF | Kayıt: sorgulanabilir zaman serisi + değişim noktası tarihi |

**Bu kalemi bir dağıtım şirketi bir öğleden sonrada kendi bakım bütçesinden doğrulayabilir.**
Bizim tespit oranımıza, modelimize ya da fiziğimize inanması gerekmez. F1'i öne çıkarmamızın
sebebi budur: modelin en az tartışmalı ve en kolay doğrulanan parçasıdır.

**Dürüst sınırı da söyleyelim:** termografiyi **sıfırlamıyoruz**. Panodaki 74 cıvatalı
bağlantının 40'ı alt bölmede ve enstrümantedir; 30'u bara bölmesinde, 4'ü çatıdadır ve
**izlenmez**.
Onlar için periyodik ziyaret devam eder, yalnız sıklığı düşer. "Termografiye artık gerek
yok" demek yanlış olurdu ve ilk denetimde ortaya çıkardı.

### 3.3 Toplumsal maliyet — ayrı tutulur

Bir AG pano arızası müşteri keser. V19 ile:

```
Tipik olay: 380 müşteri × 3.5 saat × ~220 kW kesilen yük = 770 kWh
Toplumsal maliyet = 770 kWh × €3.2/kWh = €2 464 / olay
100 panoda önlenen olay = 100 × 0.012 × 0.70 = 0.84 olay/yıl
Toplumsal fayda = €2 070 / yıl
```

**Bu tutar yukarıdaki hiçbir tabloya dahil DEĞİLDİR.** Toplumsal fayda, dağıtım şirketinin
nakit akışı değildir; ikisini toplamak, yatırımın geri dönüşünü olduğundan iyi göstermenin
en sık kullanılan yoludur. Ayrı tutuyoruz. Bir regülatörle konuşulurken bu satır ayrıca ve
açıkça sunulur — ama bir satın alma komitesine "tasarruf" diye götürülmez.

---

## 4. Sonuç: üç senaryo

### 4.1 100 pano, tekdüze dağıtım — **PARASINI GERİ ÖDEMEZ**

| | Değer |
|---|---:|
| CAPEX | €109 591 |
| Yıllık OPEX | €9 000 |
| Yıllık fayda | €24 885 |
| Yıllık net | €15 885 |
| **Geri ödeme süresi** | **6.90 yıl** |
| **5 yıllık net** | **−€30 166** |

### 4.2 Başa baş: **175 pano**

Tekdüze dağıtımda 5 yıllık net sıfıra, öğrenme eğrisi (V20) ve sabit kalemlerin (sunucu +
tip testleri) seyrelmesi sayesinde **N = 175'te** ulaşılır:

```
5y maliyet(175) = 175 × (€608.5 + €150 + €150) + €6 000 + €22 500 + 5 × €6 000
                = €158 982 + €58 500 = €217 482
5y fayda(175)   = 175 × 5 × €248.9 = €217 744
```

### 4.3 100 pano, **en kötü ondalığa** yerleştirilmiş — **2.2 yıl**

Aynı 100 modül, filonun en kötü %10'undaki panolara konur. Bu panolar zaten
bilinmektedir: arıza kaydı, yaş, yük faktörü ve son termografi raporu bir arada
kullanılarak sıralanır. Olay hızları filo ortalamasının **4 katıdır** (V18).

| Kalem | Tekdüze | En kötü ondalık |
|---|---:|---:|
| F1 Termografi | €108.3 | €108.3 (değişmez) |
| F2 Plansız arıza | €40.3 | **€161.2** |
| F3 Yangın | €19.3 | **€77.0** |
| F4 Ark-flaş (DSO nakdi) | €9.3 | **€37.2** |
| F5 Hedefli yönlendirme | €38.0 | €76.0 (×2) |
| F6 ENH / kalite | €34.0 | **€136.0** |
| **Toplam** | **€248.9** | **€595.4** |

| | Değer |
|---|---:|
| CAPEX (aynı) | €109 591 |
| Yıllık fayda | €59 540 |
| Yıllık net | €50 540 |
| **Geri ödeme süresi** | **2.17 yıl ≈ 2.2 yıl** |
| 5 yıllık net | **+€142 109** |

**Ürünün asıl mesajı budur:** soru "kaç pano alalım" değil, "**hangi** panolara koyalım"dır.
Ve bu soruyu cevaplamak için dağıtım şirketinin zaten sahip olduğu veriden başka bir şey
gerekmez.

### 4.4 1000 pano, tekdüze — **3.3 yıl**

| | Değer |
|---|---:|
| CAPEX | €649 090 |
| Yıllık OPEX | €54 000 |
| Yıllık fayda | €248 850 |
| Yıllık net | €194 850 |
| **Geri ödeme süresi** | **3.33 yıl** |
| 5 yıllık net | **+€325 160** |
| Pano başına yıllık TCO | €184 |

1000 panoda tekdüze dağıtım da geri döner, çünkü öğrenme eğrisi donanımı %28.8 ucuzlatır ve
sabit kalemler (sunucu + tip testleri) modül başına €285'ten €28.50'ye iner.

---

## 5. Duyarlılık

En kırılgan üç varsayım ve modeli kırma noktaları (100 pano, en kötü ondalık senaryosu):

| Varsayım | Baz | Geri ödeme 5 yılı aşar |
|---|---:|---|
| V17 tespit oranı | %70 | **%17'nin altına düşerse** |
| V9 mevcut termografi maliyeti | €130/pano/yıl | **€0'a inerse** (yani DSO hiç termografi yapmıyorsa) geri ödeme 2.8 yıla çıkar — hâlâ olumlu |
| V11 arıza hızı | %1.2/pano/yıl | **%0.25'in altına düşerse** |
| V18 en kötü ondalık çarpanı | ×4.0 | **×1.4'ün altına düşerse** |

**Modelin en dayanıklı yanı F1'dir**, çünkü tespit oranından bağımsızdır. En kırılgan yanı
V11'dir ve onu doğrulayacak veri **dağıtım şirketinin kendi arıza kayıtlarındadır**; bizim
elimizde değildir. Sağlanan veri kümesi bu konuda hiçbir şey söylemez (sahtedir, README §6).

---

## 6. Neyi maliyetlendirmediğimiz

Dürüstlük gereği, modele **girmeyen** kalemler:

| Kalem | Neden yok |
|---|---|
| Yazılım geliştirme maliyeti | Bu bir hackathon teslimidir; ürünleştirme bütçesi ayrı bir konuşmadır |
| Entegrasyon (SCADA, bakım yönetim sistemi) | Hangi sistemler olduğu bilinmiyor — [11] S9 |
| Eğitim | Operatör eğitimi 2 gün olarak öngörülüyor, fiyatlandırılmadı |
| Sertifikasyon (CE, TSE) | Ürünleştirme kalemi |
| 8. yıl toplu hücre değişimi | 5 yıllık ufkun dışında; gösterge modül başına €18 + ziyaret payı |
| OG hücre kapsamı | Ayrı bir hat — [10-MV-HUCRE-KONSEPTI.md] §7 |
| Toplumsal VoLL | §3.3 — **bilinçli olarak ayrı** |

---

## 7. Belgelendi, kodlanmadı

| Konu | Durum |
|---|---|
| V9–V16 arasındaki tüm olay hızları ve maliyetler | **DSO kayıtlarından doğrulanmadı**; hepsi etiketli varsayım |
| Tedarikçi fiyat teyidi | Alınmadı; gösterge liste fiyatı |
| Tip testi laboratuvar teklifi | Alınmadı; €22 500 gösterge |
| "En kötü ondalık" sıralama algoritması | Kavram; kodlanmadı. Girdi verisi (arıza kaydı, yaş, yük) DSO'da |
| ENH / kalite yükümlülüğü hesabı | Türkiye regülasyon parametreleriyle detaylandırılmadı |
| Öğrenme eğrisi | İki BOM noktasından türetildi; üç nokta ile doğrulanmadı |
