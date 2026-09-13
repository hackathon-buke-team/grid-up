# K1 · Elektronik Dokümantasyon — KiCad Şematikleri (1.1)

> Bu belge K1 iş paketinin **1.1 KiCad şematiği** maddesini karşılar: "TC düğümü,
> IR/PD düğümü, ağ geçidi kartı (besleme, sensör arayüzleri, RF ön ucu, koruma
> elemanları)". Bitti sayılır kriteri: 3 şematik PDF, ERC temiz, bu belgeyle
> bileşen eşleşmesi. [`docs/02-DONANIM-TASARIMI.md`](02-DONANIM-TASARIMI.md)'deki
> modül envanteriyle (TC-0..5, PD-1, GW-1) birebir tutarlıdır.

## 0. Nasıl üretildi

KiCad 10.0.6 bu oturumda kuruldu (`kicad.org` → CERN S3 mirror, resmi installer,
967.8 MB, kullanıcı bazlı kurulum — admin gerektirmedi). Üç proje elle KiCad
GUI'sinde çizilmedi; bunun yerine [`hardware/kicad/gen_schematics.py`](../hardware/kicad/gen_schematics.py)
+ [`hardware/kicad/build_boards.py`](../hardware/kicad/build_boards.py) adlı bir
Python üretici yazıldı. Her sembol (`lib_id`, pin koordinatları, pin elektrik
tipleri) KiCad'in kendi kurulu kütüphane dosyalarından (`.../10.0/share/kicad/symbols/*.kicad_sym`)
gerçek metin olarak okunup doğrulandı — hiçbir pin ataması tahmin edilmedi.
`kicad-cli sch erc` ve `kicad-cli sch export pdf` ile gerçek KiCad araç zinciri
üzerinden ERC koşuldu ve PDF üretildi.

Her pinin bağlantısı **gerçek çizilmiş bir tel** ile yapılır: `place()` her
sembolü yerleştirdiğinde pinin kendi yönelimine (rotation) göre kısa bir
çıkıntı teli (`_stub`, 2.54mm) çizer, telin ucuna da ya aynı isimli bir
etiket (sinyal netleri) ya da bir güç sembolü (güç netleri) oturtulur — yani
şema gözle bakıldığında da gerçekten "bağlı" görünür, salt üst üste binen
metin etiketi değil.

Bu süreçte doğrulanan/düzeltilen gerçek KiCad davranışları:
- Sembol yerleştirilirken **Y ekseni ters çevrilir**: bir pinin kütüphanedeki
  yerel konumu `(at 0 3.81 ...)` ise, gövde (0,0)'a yerleştirildiğinde o
  pinin sayfadaki gerçek konumu Y=+3.81 değil **Y=-3.81**'dir.
- `power:GND` / `power:+3V3` gibi güç sembolleri **kendi başlarına** "bu net
  beslenmiştir" saymaz; ERC'nin `power_pin_not_driven` kuralını geçmek için
  gerçek bir çıkış tipi (`power_out`) pinine ihtiyaç var — standart KiCad
  çözümü `power:PWR_FLAG` sembolüdür (bkz. §4).
- **Yerleşim koordinatları (mm) 1.27mm gridine oturmazsa** (üreticinin
  okunabilirlik için seçtiği `-170`, `60`, `bx=-100+i*45` gibi rakamların çoğu
  1.27'nin katı değil) her tek pin "off-grid" sayılır — `place()` artık
  sembol orijinini yerleştirmeden önce en yakın 1.27mm'ye yuvarlıyor
  (`_snap`), gerçek kütüphane pin ofsetleri zaten 1.27'nin katı olduğundan
  sonuç kesin gride oturuyor.
- **`extends`li kütüphane sembolleri** (bir temel parçadan türeyen varyantlar,
  ör. `AP2112K-3.3` → `AP2204K-1.5`): şemanın kendi `lib_symbols` önbelleğine
  gömüldüğünde, iç alt-birim adları (`..._0_1`/`..._1_1`) DIŞ sembol adıyla
  aynı "çıplak" kökü paylaşmak zorunda — yalnız dış sarmalayıcıyı yeniden
  adlandırıp içindekileri temel parçanın adında bırakmak `kicad-cli`'nin
  dosyayı hiç açamamasına (sessiz çökme, çıkış kodu 3) yol açtı; düzeltme
  temel parçanın adını her yerde (dış + alt-birimler) hedef parça adıyla
  değiştirip yalnız dışa kütüphane önekini ekliyor.

## 1. ERC sonucu (üçü de gerçek, 0 hata)

| Şematik | Hata | Uyarı | PDF |
| --- | --- | --- | --- |
| TC düğümü | **0** | 5 | [`hardware/kicad/tc-node/export/tc-node.pdf`](../hardware/kicad/tc-node/export/tc-node.pdf) |
| IR/PD düğümü | **0** | 3 | [`hardware/kicad/ir-pd-node/export/ir-pd-node.pdf`](../hardware/kicad/ir-pd-node/export/ir-pd-node.pdf) |
| Gateway | **0** | 3 | [`hardware/kicad/gateway/export/gateway.pdf`](../hardware/kicad/gateway/export/gateway.pdf) |

Ham ERC raporları (`kicad-cli sch erc --format json`):
`hardware/kicad/<proje>/erc-report.json`.

**Kalan 11 uyarının tamamı açıklanabilir, hiçbiri bağlantı hatası değil:**

| Uyarı tipi | Nerede | Sebep |
| --- | --- | --- |
| `lib_symbol_mismatch` | AP2112K-3.3 (3 şemada), RJ45 (gateway), PTVS5V0Z1USK (ir-pd-node) | Bu 3 gerçek parça, gerçek kütüphanede `extends` ile bir temel parçadan (AP2204K-1.5 / 8P8C / ZPYxx) türüyor. Gömülü önbellekte extends ilişkisini tekrar kurmak yerine temel parçanın tam grafiği/pinleri birebir kopyalanıp hedef parça adıyla etiketlendi (aynı ayak izi ailesi, elektriksel olarak özdeş) — KiCad'in kendi extends-çözümlemesiyle birebir bayt eşleşmediği için ERC bunu "farklı" işaretliyor, ama içerik gerçek ve doğru. |
| `lib_symbol_issues` | `Generic:CT_Interface` (×3, TC düğümü), `Generic:RF_Frontend` (ir-pd-node) | Bu ikisi gerçek parça değil, bu proje için yazılmış temsili/lumped bloklar (bkz. §5) — "Generic" diye kayıtlı bir KiCad kütüphanesi olmadığı için beklenen. |
| `isolated_pin_label` | `SPI1_MOSI` (TC düğümü), `AC_L_PANEL` (gateway) | Kasıtlı tek-pin net: MAX31855 salt-okunur olduğu için MOSI hattı yalnız gelecekte kullanım için çekildi; `AC_L_PANEL` panonun kendi İç İhtiyaç Devresi'ne giden, şema dışına çıkan bir uçtur. |

## 2. TC düğümü (`hardware/kicad/tc-node/`) — pano başına 6 adet

| Ref | Parça | Değer/Model | Görev |
| --- | --- | --- | --- |
| U1 | STM32WLE5CCUx | MCU_ST_STM32WL kütüphanesi | MCU + entegre sub-GHz radyo |
| U2 | AP2112K-3.3 | LDO (SOT-23-5) | Pil → 3.3V |
| BT1 | Battery_Cell | LiSOCl2 3.6V | Birincil güç kaynağı |
| D1 | Diode | Ters polarite koruması | Pil girişi |
| C1, C5, C6 | C / C_Polarized | 100nF / 1uF / 1F | VR_PA decoupling, LDO çıkışı, TX süperkapasitör buffer |
| R1 | R | 10k | NRST pull-up |
| SW1 | SW_Push | Reset butonu | |
| J1 | Conn_01x04 | SWD (SWDIO/SWCLK/GND/3V3) | Programlama |
| Y1, C2, C3 | Crystal + 2×C | 32MHz + 12pF | Sub-GHz radyo zamanlama (HSE) |
| C7 | C | 2.2pF | RF eşleştirme (basit tek uçlu) |
| AE1 | Antenna | PCB chip anten | Kabin içi kısa mesafe → GW-1 |
| U3, U4, U5 | MAX31855KASA | SPI termokupl-dijital, K tipi | TC1/TC2/TC3 sıcaklık |
| J2, J3, J4 | Conn_01x02 | Termokupl probu girişi | |
| A1, A2, A3 | `Generic:CT_Interface` | Özel/temsili blok | Klip-on CT arayüzü (bkz. §5) |
| J5, J6, J7 | Conn_01x02 | CT klipsi girişi | |

**SPI1** (PA5/PA6/PA7) üç MAX31855 arasında paylaşılır, her biri kendi CS'i ile
(PA4, PA15, PC13). **ADC** kanalları CT1-3 için PB3/PB4/PB2.

## 3. IR/PD düğümü (`hardware/kicad/ir-pd-node/`) — pano başına 1 adet

| Ref | Parça | Değer/Model | Görev |
| --- | --- | --- | --- |
| U1, U2, BT1, D1, C1/C5/C6, R1, SW1, J1, Y1/C2/C3, C7, AE1 | *(TC düğümüyle aynı güç/MCU/RF bölümü)* | | |
| J2 | Conn_Coaxial_Small | BNC | HFCT30/50 klipsi girişi |
| D2 | PTVS5V0Z1USK | TVS 5V | BNC girişi ESD koruması |
| C8 | C | 1nF | DC blok |
| A1 | `Generic:RF_Frontend` | Özel/temsili blok | Bandpass + LNA + log-amp zarf dedektörü (bkz. §5) |
| J3 | Conn_01x02 | Ölçü Devresi referansı (LV) | Faz referansı kaynağı |
| R2 | R | 10k | Akım sınırlama (opto LED tarafı) |
| U3 | 4N25 | Optocoupler | İzoleli sıfır-geçiş algılama |
| R3 | R | 10k | Opto çıkışı pull-up |

RF zarf çıkışı PB3 (ADC), sıfır-geçiş sinyali PA0 (EXTI) üzerinden MCU'ya girer.

## 4. Gateway kartı (`hardware/kicad/gateway/`) — pano başına 1 adet

| Ref | Parça | Değer/Model | Görev |
| --- | --- | --- | --- |
| U1, R1, SW1, J1, Y1/C2/C3 | *(aynı MCU/reset/SWD/kristal bölümü)* | | |
| F1 | Fuse | 0.5A | Modül dalı sigortası (panonun İç İhtiyaç Devresi'nden) |
| U2 | HLK-PM01 | 220VAC→5V izoleli AC/DC modül | Mains-tap besleme |
| U3 | AP2112K-3.3 | LDO | 5V → 3.3V |
| C4, C5 | C | 10uF / 1uF | Giriş/çıkış decoupling |
| C7 | C | 2.2pF | RF eşleştirme |
| J2 | Conn_Coaxial_Small | SMA | **Harici anten** (kabin sac gövde RF zayıflatması — bkz. docs/02 §6) |
| U4 | W5500 | SPI Ethernet controller | TCP/IP + MAC/PHY |
| R2 | R | 12k 1% | EXRES1 bias (WIZnet referans devresi) |
| C7(W5500), C8, C9 | C | 2.2uF / 0.1uF / 1uF | TOCAP / VBG / 1V2O decoupling (WIZnet referansı) |
| Y2, C10, C11 | Crystal + 2×C | 25MHz + 18pF | W5500 saat kaynağı |
| J3 | RJ45 (8P8C) | — | Ethernet çıkışı (yalnız pin 1-4 kablolu, bkz. §5) |

**SPI2** (PA5/PA8/PA10, CS=PA9) MCU'yu W5500'e bağlar; INT=PA11, RST=PA12.
PMODE0-2 = GND (000, WIZnet otomatik-negosiasyon modu).

## 5. Bilinçli basitleştirmeler (gerçek, uydurulmadı)

- **`Generic:CT_Interface`** (TC düğümü, ×3): gerçek devre burden direnci +
  VDD/2 bias bölücü (2×R paylaşımlı) + AC-coupling kapasitörden oluşur; tek
  kutu olarak çizildi, PCB aşamasında açılacak.
- **`Generic:RF_Frontend`** (IR/PD düğümü): bandpass filtre + LNA + log-amp
  zarf dedektörü (AD8307 sınıfı) zincirini temsil eder; kesin IC seçimi HFCT
  çıkış seviyesine göre PCB aşamasında netleşecek.
- **W5500 ↔ RJ45 arası izolasyon magnetics modülü (entegre MagJack) bu
  şemada YOK** — gerçek PCB'de eklenmesi zorunlu (WIZnet referans tasarımı).
- **STM32WLE5CC dahili SMPS kullanılmadı** (LDO modu varsayıldı: VFBSMPS→VDD,
  VLXSMPS→NC) — ST AN5246 ile üretim öncesi doğrulanmalı.
- **RF eşleştirme tek uçlu ve minimal** (RFO_HP → 2.2pF → anten); RFI_P/N ve
  RFO_LP kullanılmadı (NC) — tam ST referans anahtarlama ağı PCB aşamasında.
- W5500 durum LED'leri (SPDLED/LINKLED/DUPLED/ACTLED) ve RSVD pinleri bu
  geçişte bağlanmadı (`no_connect` ile işaretli, ERC hatası değil).

## 6. Açık maddeler

- [ ] PCB yerleşimi (1.2) henüz yapılmadı — sıradaki K1 maddesi.
- [ ] `Generic:CT_Interface` / `Generic:RF_Frontend` gerçek devrelere
      (ayrı R/C/IC) PCB aşamasında açılmalı.
- [ ] SMPS LDO-modu tie-off'u (VFBSMPS→VDD) ST AN5246 ile teyit edilmeli.
- [ ] W5500-RJ45 magnetics modülü eklenmeli.
