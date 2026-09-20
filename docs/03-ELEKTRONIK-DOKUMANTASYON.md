# 03 · Elektronik dokümantasyon / B1

Bu sürüm gerçek KiCad 10 şematik/PCB kaynaklarını belgeler. [hardware/README.md](../hardware/README.md) dosya dizinidir. Her fiziksel pin ve ağ `circuit.json` ile `pinmap.csv` içinde bulunur. Aşağıdaki tablolar aynı manifestten üretilir; sanal kaynak bayrakları BOM'a/PCB'ye eklenmez.

## Elektriksel kararlar ve hesaplar

**TC:** STM32WLE5CCU6, LDO modunda TPS7A0230PDBVR ile 3,0 V. TMP117 **AIDRVR** (-55..150°C sipariş varyantı); MAI tıbbi 0..85°C varyantı kullanılmaz. 400 A/3000=133 mA rms CT sekonder akımı, 5,1 ohm burden üzerinde 0,68 V rms/0,96 V tepe, yaklaşık 0,091 W üretir; 0,5 W/0,1% seçilir. AC kuplaj sonrası 1,5 V bias ile ADC 0,54..2,46 V aralığında kalır. 1k/47nF filtre yaklaşık 3,39 kHz; 64 örnek/20 ms RMS yalnız temel güç akımı içindir, hassas harmonik analiz iddiası yoktur. BAT54S orta ucu ADC'ye, dış uçları GND/3 V'a bağlıdır. CT sekonderinde harici sabit koruyucu kelepçe zorunlu; açık sekonder oluşturacak montaj yapılmaz.

**IR:** TPS63900 / SEL düşük / CFG3=16,2k ile 3,3 V. MLX90640 **BAA** 110×75 derece; BAB 55×35 derecedir. Sensör ve I²C pull-up beslemeleri birlikte anahtarlanır; kapanınca SDA/SCL yüksek sürülerek geri besleme yapılmamalıdır. Sensör sürücüsü ve piksel/ROI kalibrasyonu hedef firmware'de henüz yoktur.

**PD:** AD8318 ve PGA-103+ 3,3 V ile beslenmez. TPS61023 ayrı anahtarlanan 5 V üretir; 732k/100k ile nominal 4,992 V. PE4259 HFCT/TEV yollarını CTRL/CTRL_N tamamlayıcı girişleriyle sırayla seçer. AD8318 çıkışı RF güç artarken düşer; eşik karşılaştırıcısının yönü buna göre kuruludur. Ham ADC'nin pozitif PRPD genliğine dönüştürülmesi ve RF kazanç kalibrasyonu PD sürücüsünde yapılmalıdır. Ultrasonik OPA320 ve karşılaştırıcı analog 3,3 V hattı kapatılabilir. Akım-fazı ile PRPD gerilim-fazı aynı sayılmaz.

**RF düğüm:** STM32WL LP TX/RX ağı, PE4259 ve u.FL çıkışları çizilmiştir. Eşleme değerleri ST AN5457'deki referans topolojiden alınan **başlangıç değerleridir**; ilgili tablo farklı paket/frekans örnekleri içerir, B1 QFN/868 MHz için son değer sayılmaz. PCB empedansı ve VNA doğrulaması tamamlanmadan RF performans iddiası yoktur. HSE tuning, frekans hatası, duty cycle ve TX gücü son donanımda ölçülür.

**GW:** STM32H563ZIT6; RMII TX_EN=PG11, TXD0=PG13, TXD1=PG14 AF11. LAN8742A için harici 50 MHz saat, PHY adres/REG_OFF/INTSEL strap'leri ve 12,1k RBIAS vardır. 8 MB W25Q64 NOR +8 MB APS6404 PSRAM ortak quad veri hattında; IO0/1/2/3=PF8/PF9/PF7/PF6 AF10, CLK=PF10 AF9. CS'ler PF2/PG9 GPIO; **yalnız indirect transfer**, aynı anda biri düşük, ikisi boşta yüksek; doğrudan memory-mapped kullanım yoktur. Gerçek GW uygulaması bu gereksinimleri sağlamalıdır.

SX1262, kendi kristali/eşlemesi olan E22-900MM22S modülünün içindedir. E22 RF kontrol hatları TXEN/RXEN ayrıdır. EC21-E **MiniPCIe** formu 3,3 V ile beslenir; çıplak EC21 LCC modülüyle karıştırılmaz. Bu formun UART'ı üretici §3.8'e göre 3,3 V'tur. USB çiftinin H563 host modunda kullanılması veya UART AT/PPP yolu için sürücü gerekir. TE2041119-1 özel footprint'i üretici C-2041119 rev D çiziminden oluşturuldu; üretim öncesi mating-card kontrolü gerekir.

İki ADM2587E'nin ISO1/ISO2 toprak ve güç alanları ayrıdır. SM712, ayrı opsiyonel 120 ohm jumper ve kutuplu terminal bulunur. Jumper varsayılan açık, yalnız hat sonunda takılır. K1 harici RS-485 master/Modbus firmware'ini yazmaz. 5 V giriş sigorta/ters kutup MOSFET yolundan iki buck'a gider. 100 ohm şarj direnci, seri EDLC dengelemesi ve Schottky OR'lama yalnız mantık buck'ını tutar; PF_AIL ADC harici 5 V kesilmesini izler. RTC yedek pili primerdir; şarj işlevi yazılımda kapalı tutulmalıdır.

## PCB yerleşimi ve üretim sınırı

Dört bakır katman / toplam 1,6 mm: L1 bileşen-sinyal, L2 yerel GND, L3 güç/seyrek sinyal, L4 sinyal. Bu işlev atamasıdır; prepreg, bakır kalınlığı ve dielektrik üreticiyle seçilmeden 50 ohm iz genişliği ilan edilmez. Planlanan minimum iz/boşluk 0,15 mm, minimum mekanik delik 0,20 mm; via 0,6/0,3 mm. Bunlar fabrika onayı değildir.

TC termal ada ve anten çıkışları keepout olarak tanımlı. GW iki izole alan arasında düzlem/iz geçişini engelleyen kurallar içerir. PCB kaynaklarında **0 bakır iz** vardır: elektriksel ağlar ve bileşen yerleşimi tamamlanmış, yönlendirme yapılmamıştır. Üst/alt/3B PNG'ler aynı kaynaktan alınır. Yerleşim DRC'si 0; TC/IR/PD/GW bağlantısız ağ öğeleri 167/162/253/396. Bunlar gizlenmez ve üretim için DRC temiz iddiası yapılmaz.

## Saha şartı - tasarım karşılığı

| Etki | Bileşen / karar | Doğrulama sınırı |
|---|---|---|
| Sıcak/soğuk ortam | Endüstriyel MCU; TMP117AIDRVR; 16 V kapasitörler, 5,1 ohm 0,5 W burden; pil ayrı hacim | Pano -25..+55°C tasarım hedefi; daha yüksek iç sıcaklıkta pil/kutu/modem derating gerekir |
| Kuvvetli manyetik alan | CT gerçek alanı ölçer, dış alana hassastır; kısa bükümlü CT kablosu, küçük döngü, yerel GND | “Manyetik hassas parça yok” iddiası kaldırıldı; CT doyumu ve dış alan enjeksiyonu test edilir |
| RF/ESD | 50 ohm koaksiyel, u.FL keepout, yerel bypass; PD kısa analog yol; RS-485 SM712 | Son routing/ekran kutusu/harici port ESD tasarımı ve EMC testleri açık |
| Darbe/titreşim | Captive konnektör, kablo gerilim giderme, TC kayışlı kelepçe, GW DIN klipsi | Mıknatıs/klips tutunması, kapak mandalı ve gevşeme test edilmedi |
| Yoğuşma | SHT41 açıklığı, membran ve conta konsepti; optik/sensör yüzeyi kaplanmaz | IP sınıfı ve kaplama uygunluğu iddiası yok |
| Hata/sensör kopması | ADC ray doyumu, TMP zaman aşımı, SENSOR_FAULT; FRAM geri okuma; IWDG | Bias ortasında kalan açık CT ek öz test gerektirir |
| Pil pasivasyonu/tepe yük | 68 ohm yük testi, 100k/100k anahtarlı bölücü, HLC hacmi; ayrı PD 5 V anahtarı | Hücre/HLC paket MPN ve soğukta yük testi eksik |
| Koruma bağımsızlığı | Yalnız izleme; TVOC-2/MPR okuma hedefi; PE/topraklama işlevi değiştirilmez | PANO GÖZ koruma rölesi değildir |

## Hedef firmware kanıtı

STM32WLE5CC gerçek ARM derlemesi: **26592 bayt flash**, **9856 bayt RAM** (4096 bayt yığın dahil), 0 uyarı, 0 undefined symbol. Kaynak 29 derleme birimi; MAP/ELF/BIN `hardware/B1/evidence/target/` içinde. Fiziksel çalıştırma yok. TC kimlikleri/CT hata semantiği/enerji regresyonları ve matematik öz testi ayrı doğrulanır. Ayrıntılar [hedef README](../firmware/node/port/stm32wle5/README.md).

## Konnektörler (kart üzerindeki fiziksel pin numarası)

### TC

| Ref / işlev | Pin → ağ |
|---|---|
| J1 / CELL + HLC | 1: VBAT, 2: GND |
| J2 / SWD TC2030 | 1: V3V0, 2: SWDIO, 3: GND, 4: SWCLK, 5: NRST, 6: NC |
| J3 / MOUNT switch | 1: MOUNT_N, 2: GND |
| J4 / 868 MHz u.FL | 1: ANT, 2: GND |
| J5 / CT 3000:1 | 1: CT_PLUS, 2: CT_MINUS |

### IR

| Ref / işlev | Pin → ağ |
|---|---|
| J1 / CELL + HLC | 1: VBAT, 2: GND |
| J2 / SWD TC2030 | 1: V3V3, 2: SWDIO, 3: GND, 4: SWCLK, 5: NRST, 6: NC |
| J3 / MOUNT switch | 1: MOUNT_N, 2: GND |
| J4 / 868 MHz u.FL | 1: ANT, 2: GND |
| J5 / PHASE optional | 1: PHASE, 2: GND |

### PD

| Ref / işlev | Pin → ağ |
|---|---|
| J1 / CELL + HLC | 1: VBAT, 2: GND |
| J2 / SWD TC2030 | 1: V3V3, 2: SWDIO, 3: GND, 4: SWCLK, 5: NRST, 6: NC |
| J3 / MOUNT switch | 1: MOUNT_N, 2: GND |
| J4 / 868 MHz u.FL | 1: ANT, 2: GND |
| J5 / HFCT50 | 1: HFCT_IN, 2: GND |
| J6 / TEV plate | 1: TEV_IN, 2: GND |
| J7 / MA40S4R receiver | 1: US_IN, 2: GND |
| J8 / ISOLATED 50Hz PHASE | 1: PHASE, 2: GND |

### GW

| Ref / işlev | Pin → ağ |
|---|---|
| J1 / 5V SELV 4A | 1: V5_IN, 2: GND |
| J2 / SWD TC2030 | 1: V3V3, 2: SWDIO, 3: GND, 4: SWCLK, 5: NRST, 6: NC |
| J3 / RTC primary cell | 1: RTC_BACKUP, 2: GND |
| J4 / HR911105A | 1: TXP, 2: TXN, 3: RXP, 4: ETH_CT, 5: ETH_CT, 6: RXN, 8: CHASSIS, SH: CHASSIS |
| J5 / MPR | 1: RS1_A, 2: RS1_B, 3: ISO1_GND |
| J6 / TERM OPEN | 1: TERM1, 2: RS1_B |
| J7 / TVOC | 1: RS2_A, 2: RS2_B, 3: ISO2_GND |
| J8 / TERM OPEN | 1: TERM2, 2: RS2_B |
| J9 / 868MHz antenna | 1: GW_ANT, 2: GND |
| U13 / EC21-E MiniPCIe SOCKET | 1: NC, 2: LTE_3V3, 3: NC, 4: GND, 5: NC, 6: NC, 7: NC, 8: SIM_VDD, 9: GND, 10: SIM_IO, 11: LTE_TX, 12: SIM_CLK, 13: LTE_RX, 14: SIM_RST, 15: GND, 16: NC, 17: NC, 18: GND, 19: NC, 20: NC, 21: GND, 22: NC, 23: NC, 24: NC, 25: NC, 26: GND, 27: GND, 28: NC, 29: GND, 30: NC, 31: NC, 32: NC, 33: NC, 34: GND, 35: GND, 36: USB_DM, 37: GND, 38: USB_DP, 39: LTE_3V3, 40: GND, 41: LTE_3V3, 42: NC, 43: GND, 44: NC, 45: NC, 46: NC, 47: NC, 48: NC, 49: NC, 50: GND, 51: NC, 52: LTE_3V3 |
| J10 / SIM connector | 1: SIM_VDD, 2: SIM_RST, 3: SIM_CLK, 4: GND, 5: SIM_IO, 6: NC |
| J11 / 2x10F 2.7V EDLC pack | 1: SC_TOP, 2: SC_MID, 3: GND |

## Parça, kaynak ve düzenleme

Tam referans/değer/footprint/adet/fiyat [BOM](../hardware/B1/BOM.md), üretici-kod alanı ve alternatif/termin [JSON](../hardware/B1/bom.json) içindedir. Pasiflerde genel değerler sipariş MPN'i değildir; fiyat/MPN eksikleri açık gösterilir. Üretim satın alması bu nedenle onaylanmaz.

Kaynaklar (20.09.2026 erişimi):

- [ST STM32WLE5CC DS13105](https://www.st.com/resource/en/datasheet/stm32wle5cc.pdf): beslemeler, QFN pinler, RF.
- [ST STM32H563 DS14258 tablo 15/16](https://www.st.com/resource/en/datasheet/stm32h563zi.pdf): fiziksel pin/alternatif işlev.
- [ST AN5457](https://www.st.com/resource/en/application_note/an5457-rf-matching-network-design-guide-for-stm32wl-series-stmicroelectronics.pdf): RF topoloji, son eşleme için başlangıç referansı.
- [TI TMP117](https://www.ti.com/lit/ds/symlink/tmp117.pdf), [TPS63900](https://www.ti.com/lit/ds/symlink/tps63900.pdf), [TPS61023](https://www.ti.com/lit/ds/symlink/tps61023.pdf), [TLV3691](https://www.ti.com/lit/ds/symlink/tlv3691.pdf).
- [Melexis MLX90640](https://media.melexis.com/-/media/files/documents/datasheets/mlx90640-datasheet-melexis.pdf): BAA geniş görüş ve TO39 pinler.
- [Analog AD8318](https://www.analog.com/media/en/technical-documentation/data-sheets/AD8318.pdf): 5 V analog zincir ve negatif log eğimi.
- [pSemi PE4259](https://www.psemi.com/pdf/datasheets/pe4259ds.pdf): tamamlayıcı kontrol uçları.
- [Quectel EC21 MiniPCIe V1.5](https://www.quectel.com/content/uploads/2024/04/Quectel_EC21_Series_Mini_PCIe_Hardware_Design_V1.5.pdf): form faktörü, 3,3 V besleme/UART.
- [Ebyte E22-900MM22S](https://www.ebyte.com/product/1946.html) ve [üretici kılavuzu](https://www.ebyte.com/downpdf/1946.html): 20 pin / 10×10 mm.
- [TE2041119-1](https://www.te.com/en/product-2041119-1.html): C-2041119 rev D, sayfa 2 PCB geometrisi.
- Verilen yarışma teknik çizim/şartname/HFCT belgeleri repodaki `Hackathon Verileri` klasöründedir.

Yapılan: bağlantılı şematik, yerleşim, dosya/rapor dışa aktarımı, parametrik mekanik zarf, TC hedef derlemesi. Yapılmayan: PCB yönlendirme/imalat, sensör kalibrasyonu, sahada uygunluk, IR/PD/GW uygulama firmware'i, gerçek sensörden MQTT'ye entegrasyon, imzalı OTA ve eksiksiz tedarik teklifi.
