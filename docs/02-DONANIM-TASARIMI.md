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

## 8. Açık maddeler

- [ ] Ön erişim mesafesi (§5) TEDAŞ AG PANO MALZEME ŞARTNAMESİ'nden sayısal
      olarak doğrulanmadı.
- [ ] B (Yükseklik) toleransı kaynak çizimde belirsiz okunuyor — teyit gerekli.
- [ ] KiCad şematiği (1.1) ve PCB yerleşimi (1.2) henüz bu belgeye referans
      vermiyor — sıradaki K1 maddeleri.
