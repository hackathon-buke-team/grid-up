# K1 · Donanım Tasarımı — Kabin İçi Mekanik Yerleşim (1.3)

> Bu belge K1 iş paketinin **1.3 Mekanik** maddesini karşılar: "modülün 1600 kVA pano
> çizimi üzerinde montaj yerleşimi (mıknatıs kaide, kablo yolu, erişim mesafesi)".
> Bitti sayılır kriteri: ölçülendirilmiş yerleşim görseli → [`hardware/mekanik/kabin-ici-yerlesim.svg`](../hardware/mekanik/kabin-ici-yerlesim.svg).

## 1. Kaynak ölçüler (organizatör PDF'lerinden, tahmin değil)

| Kaynak | Değer |
| --- | --- |
| Kabin dış ölçüsü (TEDAŞ-MLZ/2003-06.B, EK-II/14) | 1600 (Genişlik, +100/-0) × 1500 (Yükseklik) × 450 mm (Derinlik, +50/-0) |
| Alt bölüm kablo/bara boşluğu (aynı çizim) | **en az 400 mm** — PANO GÖZ modülü ve kablo demeti bu bölgeye giremez |
| Ana bara (EK-I/8, 1600 kVA satırı) | 2×(100×10 mm²) kalay kaplı elektrolitik bakır |
| Ana giriş akım trafosu (EK-I/8) | 2500/5 |
| Besleme çıkışı anma akımı (EK-I/8) | 250 A / 400 A |
| Besleme çıkış sayısı (EK-I/8) | 5 aktif + 2 yedek |
| Bara terminalleri arası mesafe (EK-I/8) | 185 mm |

Not: `B (Yükseklik)` toleransı kaynak PDF'te yalnızca "-0" olarak okunabiliyor
(A ve C için "+X/-0" çifti net); orijinal çizimden teyit edilmeli — açık madde.

## 2. Modül envanteri (bu pano için)

Toplam **8 modül**, tamamı §5'teki mimari şemasındaki "Uç düğüm" katmanına girer:

| Kod | Tip | Konum | Görev |
| --- | --- | --- | --- |
| TC-0 | Termal-Akım | Ana giriş barası | 2×(100×10mm²) ana bara — 3 faz sıcaklık farkı (θ) |
| TC-1 … TC-5 | Termal-Akım | Her besleme çıkışının DSYA'sı | Çıkış başına 3 faz kardeş karşılaştırması |
| PD-1 | HFCT / Ark-PD | Ana giriş kablo riseri | Kısmi deşarj + TVOC-2 ark verisiyle füzyon |
| GW-1 | Gateway | Kabin üstü, mevcut "Modem" bölgesi | Sub-GHz toplama → MQTT → `panogoz/bus` |

Yedek çıkışlara (Yedek 1, Yedek 2) sensör konmadı — kullanılmayan devrede
izlenecek gerçek yük yok.

**TC düğümü donanımı:** 3× temas tipi ısı probu (her faz pabucuna cıvatalı
bağlantı üzerine kelepçeli) + 3× split-core klip-on CT (hat kesilmeden akım
okur, mevcut 2500/5 ana CT'ye ek, invaziv değil).

**PD-1 donanımı:** HFCT30/50 (bkz. `Hackathon Verileri/DS_HFCT30_eng.pdf`) —
tamamen pasif/endüktif klips, BNC çıkışı düğüm gövdesindeki RF ön-uç +
yüksek hızlı ADC kartına bağlanır.

## 3. Montaj yöntemi — mıknatıs kaide

Her düğüm gövdesi kabin şasesindeki **ferromanyetik DIN ray / sac** üzerine
mıknatıs kaide ile tutturulur; kabine delik açılmaz (TEDAŞ sertifikalı pano
üzerinde kalıcı değişiklik yapılmaz).

**Kritik nokta:** ana bara ve pabuçlar **kalay kaplı bakırdır — manyetik
değildir.** Mıknatıs kaide düğüm gövdesini yakındaki çelik şaseye/DIN raya
sabitler; sıcaklık probu ve klip-on CT ise ayrıca, bağımsız bir mekanik
kelepçeyle doğrudan bara/kabloya temas ettirilir. Bu ayrım ilk taslakta
gözden kaçabilecek bir hataydı, bilerek burada netleştirildi.

## 4. Kablo yolu

Sinyal (termokupl + CT) ve anten kabloları, kabin sağ iç duvarındaki düşey
kanaldan yönlendirilir; bu kanal baradan **≥ 50 mm** ayrık tutulur ve
**hiçbir noktada §1'deki ≥400 mm kablo/bara boşluk bölgesine girmez.** Tüm
düğümlerin kabloları bu kanaldan GW-1'e toplanır.

## 5. Erişim mesafesi ve derinlik yerleşimi

- Modüller kabin derinliğinin **ön 2/3'üne** yerleştirilir (bara/ana bağlantı
  bölgesi arkada, son ~100 mm'de kalır) — kapı kapanışını engellemez, bakımda
  öne erişilebilir. Modül önden taşkınlığı ≤ 60 mm ile sınırlandı.
- Ön bakım/çalışma mesafesi olarak genel AG pano pratiğinde kullanılan
  **≥ 800 mm** varsayıldı; bu sayı `AG PANO MALZEME ŞARTNAMESİ.pdf`
  (66 sayfa) içinden henüz doğrulanmadı — **açık madde**, teyit gerekiyor.

## 6. RF / saha koşulu notu (K1 · 1.5 ile kesişim)

Kabin sac gövde sub-GHz (STM32WLE5CC LoRa bandı) sinyalini önemli ölçüde
zayıflatır. GW-1'in anteni bu yüzden kabin üstünden **harici stub anten +
SMA geçiş/kablo rakoru** ile dışarı çıkarılır; TC/PD düğümleri ile GW-1
arasındaki mesafe kabin içi olduğundan bu düğümlerin kendi linki için ayrı
bir önlem gerekmiyor (tek kabin içi, kısa mesafe).

## 7. Görsel

Ölçülendirilmiş yerleşim (ön görünüm + derinlik kesiti + lejant + notlar):
[`hardware/mekanik/kabin-ici-yerlesim.svg`](../hardware/mekanik/kabin-ici-yerlesim.svg)

Kaynak: `TEDAŞ-MLZ/2003-06.B` EK-II/14 (ölçüler) ve EK-I/8 (donanım listesi),
`Hackathon Verileri/` klasöründe mevcut.

## 8. Saha koşulları (1.5) — bileşen sıcaklık sınırları, manyetik alan, titreşim

> K1 1.5 maddesini karşılar: "yüksek/düşük sıcaklık, manyetik alan, titreşim
> → şemadaki karşılığını dokümante et." Sayılar gerçek üretici datasheet'lerinden
> (bu oturumda web araması ile doğrulandı, tahmin edilmedi) — kaynak linkleri
> her satırda.

### 8.1 Sıcaklık — gerçek zayıf halka HLK-PM01

| Bileşen | Kart | Çalışma sıcaklığı | Kaynak |
| --- | --- | --- | --- |
| MAX31855KASA | TC | **−40 … +125 °C** | [Analog Devices datasheet](https://www.analog.com/media/en/technical-documentation/data-sheets/max31855.pdf) |
| STM32WLE5CC | Hepsi | −40 … +105 °C (radyo aktifken +85 °C'ye sınırlı) | [ST datasheet](https://www.st.com/resource/en/datasheet/stm32wle5c8.pdf) |
| AP2112K-3.3 (LDO) | Hepsi | −40 … +85 °C ortam (150 °C junction max) | [Diodes Inc. datasheet](https://www.diodes.com/assets/Datasheets/AP2112.pdf) |
| W5500 | Gateway | −40 … +85 °C | [WIZnet datasheet](https://docs.wiznet.io/img/products/w5500/W5500_ds_v110e.pdf) |
| 4N25 optokuplör | IR-PD | −55 … +100 °C | [Vishay datasheet](https://www.vishay.com/docs/83725/4n25.pdf) |
| LiSOCl2 pil (BT1) | TC, IR-PD | Tipik −55 … +85 °C (bobin tipine göre değişir, spesifik parça seçimi K1 1.6 BOM'da netleşecek) | genel LiSOCl2 hücre özelliği |
| **HLK-PM01 (mains-tap)** | **Gateway** | **−20 … +60 °C — sistemdeki en dar aralık** | [datasheet](https://d229kd5ey79jzj.cloudfront.net/888/Datasheet%20HLK-PM01.pdf) |

**Sonuç:** zincirdeki gerçek zayıf halka Gateway'in mains-tap güç modülü
(HLK-PM01, +60 °C tavan) — diğer tüm bileşenler ≥ +85 °C'ye toleranslı.
Gateway kartı kabin içinde ana bara/ısınan bağlantı noktalarından uzağa,
İç İhtiyaç Devresi çıkışına yakın (zaten elektriksel olarak oradan besleniyor)
ve doğrudan bir arıza noktasının üstüne değil §5'teki ön 2/3 bölgesine
yerleştirilmeli — bu proje TAM OLARAK sıcak noktaları erken yakalamayı
hedeflediği için, Gateway'in kendisinin bir sıcak noktanın yanına
konmaması bilinçli bir yerleşim kısıtı olarak burada not edildi. TC/IR-PD
düğümleri (pil beslemeli, HLK-PM01 yok) bu kısıta tabi değil.

### 8.2 Manyetik alan / EMI

- Ana bara 250-400A anma, kısa devre/arıza anında bunun çok üzerinde (kA
  mertebesinde) akım taşıyabilir — CT/termokupl sense hatları bara
  yakınından geçtiği için endüktif gürültüye açık.
- Mevcut tasarımda buna karşı iki gerçek önlem var: (1) §3'teki mekanik
  ayrım — mıknatıs kaide düğüm gövdesini çelik şaseye sabitler, sıcaklık
  probu/CT ayrıca **bağımsız bir mekanik kelepçeyle** bağlanır (bara
  manyetik değil, bu ayrım docs/02 §3'te zaten belirtilmiş) — sensör
  kablosu bara yüzeyine bara akımı yolundan mümkün olduğunca dik/kısa
  geçecek şekilde yönlendirilmeli (saha kurulumu notu, PCB dışı).
  (2) IR/PD düğümündeki sıfır-geçiş faz referansı zaten bir optokuplör
  (4N25) ile galvanik izoleli alınıyor (`hardware/kicad/ir-pd-node/`,
  docs/03 §3) — bu tasarım zaten EMI/yalıtım bilincini yansıtıyor.
- **Açık madde:** twisted-pair/shielded sensör kablosu gereksinimi henüz
  BOM'a (1.6) yazılmadı — sıradan tek telli bağlantı yerine burada
  belirtilmeli.

### 8.3 Titreşim

- TEDAŞ AG panosu, motor/trafo gibi sürekli titreşim kaynaklarının
  yanında değil — asıl mekanik stres kaynağı yakındaki kesicilerin
  açma/kapama darbesi (şok, sürekli titreşim değil).
- Mevcut parça seçimi buna doğal olarak dayanıklı: BT1 (pil) ve HLK-PM01
  gibi en ağır/hacimli parçalar THT (delikli montaj, SMD'den daha yüksek
  mekanik tutunma), hiçbir BGA/ince pitch'li mekanik olarak kırılgan parça
  yok. Mıknatıs kaide montajı (§3) kendisi de bir miktar mekanik
  izolasyon sağlıyor (rijit vida bağlantısı değil).
- **Açık madde:** gerçek bir sayısal titreşim spesifikasyonu (ör. IEC
  60068-2-6 sınıfı) organizatör dosyalarında bulunamadı, bu oturumda
  aranmadı — K1 1.6/sonraki bir geçişte TEDAŞ AG PANO MALZEME
  ŞARTNAMESİ'nden (66 sayfa, henüz tam taranmadı) doğrulanabilir.

## 9. Açık maddeler

- [ ] Ön erişim mesafesi (§5) TEDAŞ AG PANO MALZEME ŞARTNAMESİ'nden sayısal
      olarak doğrulanmadı.
- [ ] B (Yükseklik) toleransı kaynak çizimde belirsiz okunuyor — teyit gerekli.
- [ ] Twisted-pair/shielded sensör kablosu gereksinimi BOM'a (1.6) eklenmedi (§8.2).
- [ ] Titreşim için sayısal bir standart/sınıf (IEC 60068-2-6 vb.) teyit edilmedi (§8.3).
- [ ] LiSOCl2 pil için spesifik bir üretici/parça numarası seçilmedi (§8.1) — BOM (1.6) işi.
- [x] KiCad şematiği (1.1) tamamlandı → [`docs/03-ELEKTRONIK-DOKUMANTASYON.md`](03-ELEKTRONIK-DOKUMANTASYON.md).
- [ ] PCB yerleşimi (1.2) henüz yapılmadı — sıradaki K1 maddesi.
