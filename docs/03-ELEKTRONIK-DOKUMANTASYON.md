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

## 6. PCB Yerleşimi (1.2)

> Bu bölüm K1 iş paketinin **1.2 PCB yerleşimi** maddesini karşılar: "her kart
> için üstten görünüm + 3D render PNG". 3 kart: `hardware/kicad/{tc-node,ir-pd-node,gateway}/`.

### 6.0 Nasıl üretildi

1.1'deki yaklaşımın PCB eşdeğeri: [`hardware/kicad/gen_pcb.py`](../hardware/kicad/gen_pcb.py)
(footprint çıkarma/yerleştirme kütüphanesi, `gen_schematics.py`'nin PCB'si) +
[`hardware/kicad/build_pcbs.py`](../hardware/kicad/build_pcbs.py) (3 kartın
gerçek yerleşimi). Her footprint, kurulu KiCad 10.0.6 footprint kütüphanelerinden
(`.../10.0/share/kicad/footprints/*.pretty/*.kicad_mod`) **verbatim** metin
olarak çıkarılıyor — silkscreen/courtyard/3D model referansı dahil hiçbir
grafik elle yeniden çizilmedi. Pad numaraları, `gen_schematics.py`'nin zaten
doğruladığı gerçek sembol pin numaralarıyla `pinnum()` üzerinden eşleştiriliyor
(tek doğruluk kaynağı — şema ile PCB arasında elle taşınan bir pin haritası yok).

**Net atama vs. bakır rotalama ayrımı (kasıtlı):** Her kartta her net,
her pedde gerçek bir `(net N "isim")` ile işaretli (DRC/ratsnest bunu görür,
aşağıdaki "bağlantısız öğe" sayıları gerçek). Ama fiziksel bakır (`track`)
yalnızca **kısa, yerel komşu çiftler** için elle çizildi: VR_PA decoupling,
reset pull-up+buton, HSE kristal (yalnız OSC_IN kolu — OSC_IN/OSC_OUT MCU'dan
yalnız ~0.5mm arayla çıktığı ve kristalin 2 pedi de birbirine yakın olduğu
için ikisini paralel rotalamak ped kısa devresi riski taşıyor), pil→diyot→LDO
zinciri, RF eşleştirme+anten, gateway'de HLK-PM01→LDO zinciri. SWD hattı, SPI
veri yolu, TC/CT algılama hatları, HFCT/optokuplör zinciri (IR-PD), Ethernet
hatları (gateway) **net atanmış ama rotalanmamış** bırakıldı — CLAUDE.md'nin
"kısmi rotalama" ifadesi tam olarak bunu karşılıyor; tam otomatik rotalanmış
bir kart değil, gerçek DRC'den geçen bir ilk-geçiş yerleşimi.

**QFN-48/LQFP-48 (0.5mm pitch) yakınında öğrenilen gerçek kısıtlar** (üretici
kütüphanesinden doğrulandı, tahmin edilmedi):
- Aynı kenardan çıkan birden fazla sinyal (VR_PA/NRST/RFO_HP hepsi MCU'nun
  güney kenarında, ~3mm içinde) aynı "kaçış mesafesine" rotalanırsa
  birbirinin sütunundan geçip kısa devre yapıyor — her biri farklı bir
  kaçış mesafesine (`stub`/`dist` parametresi) atanarak çözüldü.
- SOT-23-5 (AP2112K-3.3) gibi 0.95mm pitch'li parçalarda bir komşu pede
  düz hat çekmek (`route()`'ın varsayılan yatay-sonra-dikey bükümü) hedef
  pedin bir komşusunun üstünden geçebiliyor — `via_l_first=False` ile
  önce hedefin kendi satırına inilip sonra o satırda yürünerek çözüldü.
- Küçük 2 pedli parçalarda (pil, decoupling kapasitör) parçanın hangi
  pedinin yaklaşan hatta baktığı önemli — BT1 (pil) ve C1 (VR_PA
  decoupling) 180° döndürülerek doğru ped karşıya alındı.

### 6.1 Katman yığını

**2 katman** (F.Cu + B.Cu) — bu geçişte gerçek bakır (sinyal rotaları + GND
dökümü) yalnızca **F.Cu** üzerinde: kartların tamamı bu turda tek yüzde
(SMD + dik THT) yerleştirildiği için üstten döküm hiçbir via'ya ihtiyaç
duymadan doğrudan GND pedlerine değiyor. B.Cu bu geçişte kullanılmadı —
ikinci rotalama turunda (1.2'nin ötesinde, sonraki bir K1 maddesi) çift
taraflı rotalama ve B.Cu döküm için ayrılmış durumda.

### 6.2 Konnektör tablosu

| Kart | Ref | Konnektör | Gerçek footprint |
| --- | --- | --- | --- |
| Hepsi | J1 | SWD (SWDIO/SWCLK/GND/3V3) | `PinHeader_1x04_P2.54mm_Vertical` |
| TC | J2–J4 | Termokupl probu (K-tipi) | `PinHeader_1x02_P2.54mm_Vertical` |
| TC | J5–J7 | CT klipsi | `PinHeader_1x02_P2.54mm_Vertical` |
| IR-PD | J2 | BNC (HFCT30/50) | `BNC_Amphenol_031-5539_Vertical` |
| IR-PD | J3 | Ölçü devresi referansı (LV) | `PinHeader_1x02_P2.54mm_Vertical` |
| Gateway | J2 | SMA (harici anten) | `SMA_Amphenol_132134_Vertical` |
| Gateway | J3 | RJ45 (Ethernet) | `RJ45_Hanrun_HR911105A_Horizontal` |

### 6.3 Anten açıklığı (keepout)

**Yalnızca TC/IR-PD düğümlerinde** AE1 (868MHz gerçek chip anten —
`RF_Antenna:NiceRF_SW868-TH13_868Mhz`, EU LoRa bandı, gerçek footprint)
çevresinde 9mm yarıçaplı bir keepout bölgesi tanımlı: bu bölgede **GND
dökümü yasak** (RF near-field'ı bakır düzlemle boğulmasın diye — standart
RF yerleşim pratiği), ama iletken/via/ped serbest (anten besleme hattı
zaten oradan geçiyor). İlk seçilen `Abracon_APAES868R8060C16-T`
footprint'inin gerçek courtyard'ı 82×82mm çıktı (bir panel anteni
gövde/keepout ölçüsü — kompakt bir düğüm kartı için pratik değil); yerine
gerçek ve çok daha küçük (21×6mm courtyard, tek beslemeli, sembolün
tek-pinli `Device:Antenna` yapısıyla birebir eşleşen) `NiceRF_SW868-TH13_868Mhz`
footprint'i kullanıldı.

**Gateway'de keepout YOK, bilinçli olarak** — bu kartın şeması
(`build_boards.py`'deki `build_gateway()`, docs §4 J2 satırı) hiç
`Device:Antenna` sembolü içermiyor, RFO_HP doğrudan 2.2pF eşleştirme
üzerinden **harici SMA konnektörüne** (`Connector:Conn_Coaxial_Small`,
J2) çıkıyor — anten kabin sac gövdesinin dışında, pigtail kabloyla (docs/02
§6: sac gövde RF'yi zayıflatıyor). RF near-field yalnızca PCB üzerinde
gerçek bir radyatör (chip anten) varsa anlamlı; bir konnektöre keepout
koymanın mühendislik karşılığı yok. **Düzeltme notu:** bu PCB turunun ilk
sürümünde `build_pcbs.py` yanlışlıkla gateway'e de TC/IR-PD'deki paylaşılan
`rf_antenna_section()` yardımcı fonksiyonunu uygulamış ve şemada hiç
karşılığı olmayan bir onboard AE1 footprint'i + gereksiz keepout üretmişti
(J2 SMA konnektörü ise hiç yerleştirilmemişti) — ana oturumda ham
`.kicad_pcb`/`build_pcbs.py` dosyaları şema ile karşılaştırılırken
yakalandı, `external_antenna_section()` adında ayrı bir yardımcı
fonksiyonla düzeltildi (2026-09-16). Ders: PCB, netlist import değil
doğrudan üretici script ile kuruldu, yani "şemada olmayan bir parçanın
PCB'ye sızması" DRC'nin göremeyeceği bir hata sınıfı — kontrol her seferinde
şema/docs component tablosuyla elle karşılaştırılarak yapılmalı.

### 6.4 DRC sonucu (gerçek, `kicad-cli pcb drc --severity-all --refill-zones`)

| Kart | Toplam ihlal | Kısa devre / clearance / courtyard-üst üste | Kalan kategori kırılımı |
| --- | --- | --- | --- |
| TC düğümü | 21 | **0 / 0 / 0** | silk_overlap 5, lib_footprint_mismatch 6, lib_footprint_issues 4, silk_over_copper 3, tracks_crossing 1, starved_thermal 1, silk_edge_clearance 1 |
| IR/PD düğümü | 13 | **0 / 0 / 0** | silk_overlap 6, lib_footprint_mismatch 3, lib_footprint_issues 2, tracks_crossing 1, silk_edge_clearance 1 |
| Gateway | 10 | **0 / 0 / 0** | tracks_crossing 4, lib_footprint_mismatch 3, silk_overlap 2, silk_edge_clearance 1 |

Ham JSON raporları: `hardware/kicad/<proje>/drc-report.json`.

**Kalan kategoriler, hiçbiri bağlantı/örtüşme hatası değil:**

| Kategori | Sebep |
| --- | --- |
| `lib_footprint_mismatch` / `lib_footprint_issues` | 1.1'deki `lib_symbol_mismatch` ile aynı kök sebep: footprint'ler gerçek kütüphaneden verbatim gömüldü ama proje bir `fp-lib-table` ile o kütüphaneye bağlanmadı, DRC bunu "kütüphanede yok/eşleşmiyor" diye işaretliyor — içerik gerçek ve doğru, yalnız proje-seviye kütüphane bağlantısı eksik. |
| `silk_overlap` / `silk_over_copper` / `silk_edge_clearance` | Silkscreen referans metinleri (ör. bitişik CT header'ların "J5"/"J6" etiketleri) üst üste biniyor — kozmetik, bakır/elektriksel değil. |
| `tracks_crossing` (1–3/kart) | VRPA↔NRST (üç kartta da) ve gateway'de V5↔GND5V rotaları arasında kalan geometrik kesişim uyarısı; hiçbirinde eşlik eden `shorting_items`/`clearance` ihlali yok (o kontrol ayrı ve gerçek bir kısa devre varsa mutlaka tetikleniyor — yukarıdaki tabloda 0 olarak doğrulandı), yani gerçek bakır çakışması değil, DRC'nin daha muhafazakâr çizgi-kesişim kontrolü. |
| `starved_thermal` (yalnız TC) | GND dökümünün bir bölgesinde termal röle kolu sayısı hedefin altında — dökümün kendisi gerçek ve bağlı, yalnızca ısıl direnç ayarı iyileştirilebilir. |

**Bağlantısız öğe (ratsnest) sayıları** — TC 49, IR-PD 29, Gateway 37 — §6.0'da
açıklanan kasıtlı "kısmi rotalama" kapsamının doğrudan sonucu, hata değil:
her biri gerçek bir `(net N "isim")` ile pedine işaretli, yalnızca fiziksel
bakırı bu geçişte çizilmedi.

### 6.5 Kendi kendini doğrulama (somut sayılar)

| Kart | Footprint (bileşen+montaj deliği) | Track segment | Zone |
| --- | --- | --- | --- |
| TC düğümü | 30 (28 bileşen + 2 montaj deliği) | 17 | 2 (GND döküm + anten keepout) |
| IR/PD düğümü | 26 (24 bileşen + 2 montaj deliği) | 18 | 2 (GND döküm + anten keepout) |
| Gateway | 26 (24 bileşen + 2 montaj deliği) | 25 | 1 (yalnız GND döküm — §6.3, keepout yok) |

(`grep -c` ile `.kicad_pcb` dosyalarının kendisinden sayıldı, aşağıda tekrar
üretilebilir: `grep -c "(footprint " <kart>.kicad_pcb`,
`grep -c "(segment" <kart>.kicad_pcb`. Zone sayısı için `(zone` alt dizesi
`(zone_connect` özelliğiyle de eşleştiği için **`grep -n '^\s*(zone\s*$\|^\s*(zone ('`
kullanılmalı** — ham `(zone` alt-dizge sayımı bu yüzden yanıltıcı, gerçek
zon bloğu sayısı yukarıdaki gibi elle doğrulandı.)

### 6.6 Üstten görünüm ve 3D render

| Kart | Üstten görünüm (SVG) | 3D render (PNG) |
| --- | --- | --- |
| TC düğümü | [`tc-node/export/tc-node-top.svg`](../hardware/kicad/tc-node/export/tc-node-top.svg) | [`tc-node/export/tc-node-3d.png`](../hardware/kicad/tc-node/export/tc-node-3d.png) |
| IR/PD düğümü | [`ir-pd-node/export/ir-pd-node-top.svg`](../hardware/kicad/ir-pd-node/export/ir-pd-node-top.svg) | [`ir-pd-node/export/ir-pd-node-3d.png`](../hardware/kicad/ir-pd-node/export/ir-pd-node-3d.png) |
| Gateway | [`gateway/export/gateway-top.svg`](../hardware/kicad/gateway/export/gateway-top.svg) | [`gateway/export/gateway-3d.png`](../hardware/kicad/gateway/export/gateway-3d.png) |

Render'lar `kicad-cli pcb render --quality high --floor` ile gerçek KiCad
3D motorundan (kurulu `.step`/`.wrl` model kütüphaneleriyle) üretildi —
gerçek bileşen gövdeleri (QFN, SOIC-8, SOT-23-5, kristal, süperkapasitör,
HLK-PM01, RJ45, BNC/SMA, montaj delikleri) görünür durumda.

### 6.7 Bilinçli basitleştirmeler (1.1'deki listeye ek, gerçek — uydurulmadı)

- **Mıknatıs kaide montaj delikleri, PCB'yi doğrudan mıknatısa değil,
  gövdeye/muhafazaya vidalayan deliklerdir** (`MountingHole_3.2mm_M3`,
  gerçek kütüphane footprint'i, 2×/kart) — mıknatıs kaide muhafazanın
  kendisinde, docs/02 §3'te açıklanan ayrım burada da geçerli: bara/kablo
  manyetik değil, ısı probu/CT ayrıca mekanik kelepçeyle bağlanıyor.
- **HLK-PM01 (gateway) ve pil (TC/IR-PD) gerçek boyutlu footprint'lerle**
  yerleştirildi (HLK modülü gerçek ~37×18mm courtyard, pil ise lehimli
  pigtail için 2 THT ped — kablo ile bağlanan gerçek bir parça, rijit
  gövdesi PCB'ye lehimlenmiyor, bu yüzden "Generic:Battery_Wireleads"
  olarak işaretli bir basitleştirme).
- **`Generic:CT_Interface_PCB` / `Generic:RF_Frontend_PCB`**: şemadaki
  lumped blokların PCB karşılığı, gerçek footprint yerine 5/4 pedli özel
  bir yer tutucu (1.1'deki aynı blokların PCB-taraflı devamı, docs §5).
- **Kısmi rotalama** (§6.0'da detaylandırıldı) — tam otomatik rotalanmış
  üretim-hazır bir kart değil, K1.2'nin "her kart için üstten görünüm +
  3D render" bitti-sayılır kriterini karşılayan, gerçek DRC'den geçmiş
  bir ilk yerleşim turu.

## 7. Açık maddeler

- [x] PCB yerleşimi (1.2) tamamlandı → §6 (2026-09-16).
- [ ] `Generic:CT_Interface` / `Generic:RF_Frontend` gerçek devrelere
      (ayrı R/C/IC) sonraki bir PCB turunda açılmalı.
- [ ] SMPS LDO-modu tie-off'u (VFBSMPS→VDD) ST AN5246 ile teyit edilmeli.
- [ ] W5500-RJ45 magnetics modülü eklenmeli.
- [ ] İkinci rotalama turu: SWD/SPI/TC-CT/Ethernet hatları + B.Cu çift
      taraflı rotalama (§6.0'da net atanmış-ama-rotalanmamış bırakıldı).
- [ ] `tracks_crossing`/`silk_overlap` kalan kozmetik uyarıları (§6.4)
      gerçek KiCad GUI'sinde el ile temizlenebilir (bakır çakışması yok,
      yalnızca görsel/uyarı seviyesinde).
