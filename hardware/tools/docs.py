"""Regenerate K1-owned documentation from B1 electrical manifests."""
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[2];B=ROOT/'hardware/B1'
circuits={k:json.loads((B/k/'circuit.json').read_text()) for k in ('TC','IR','PD','GW')}
bom=json.loads((B/'bom.json').read_text());mem=json.loads((ROOT/'firmware/node/build/stm32wle5/memory_report.json').read_text())
d02='''# 02 · Donanım tasarımı / B1

20.09.2026. Bu belge K1'in repo ile uyumlu B1 sürümünü tanımlar. Önceki A1 blok tasarımındaki fiyat/pil ömrü ve parça varyantı varsayımlarının yerine geçer. Ana teslim dizini [hardware/README.md](../hardware/README.md); ölçülendirilmiş montaj çizimi [tasarım dosyası](../hardware/B1/K1-B1-TASARIM-DOSYASI.pdf).

## Dokuz cihazın sınırı

| Kart | Adet | Kimlik ve konum | Bileşenler / rol |
|---|---:|---|---|
| TC 30×22 mm | 6 | TC-01..03 / C06 L1..L3, TC-04..06 / C07 L1..L3; x=568/588/608/668/688/708, y=430 | STM32WLE5CC, endüstriyel TMP117AIDRVR, 400 A / 3000:1 CT |
| IR 45×35 mm | 1 | TN-IR, x=640/y=150 | MLX90640 **BAA** 110°×75°, SHT41, STM32WL |
| PD 70×50 mm | 1 | PD-01, x=1290/y=230 | HFCT50, TEV, MA40S4R, SHT41, AD8318, STM32WL |
| GW 100×90 mm | 1 | GW-01, x=1450/y=980 | STM32H563, E22/SX1262, LAN8742A, 2× ADM2587E, EC21-E MiniPCIe |

IR/PD görev belgesinde tek işlev grubu, mevcut repoda iki ayrı karttır. Bu nedenle üç grup dört fiziksel kart tipiyle gösterilir. Ortak asset/kanal/zarf sözleşmeleri aynen korunur. Gateway ekranı halen dijital ikizdir; simülasyon verisi ölçülmüş veri sayılmaz.

## Mekanik montaj

Referans: repo içindeki `AG Pano Teknik Çizim-1600kVA.pdf`, EK-II/14, 1600×1500×450 mm nominal zarf. Orijin ön-sol-alt, x sağa/y yukarı/z derinlik. Kaynak çizim üzerine cihaz işaretleri ve ayrı ölçülü görünüm PDF sayfa 1'dedir; STEP modeller mm birimindedir.

TC gövdesi 34×126×19,5 mm, kenarı öne döndürülür. 20 mm faz adımında Ø42 mm dış kelepçeler aynı düzlemde çakışacağından z=80/140/200 mm kademesi tasarlanır. En gerideki 126 mm gövde z=326 mm'ye ulaşır. Gerçek kablo bükülmesi ve elektriksel açıklıklar bilinmediğinden sahaya sığdığı iddia edilmez. Nominal Ø32 mm kelepçe için değişebilir yalıtkan insert ve kayış öngörülür. Pabuçtan 50-100 mm aşağıdaki **yalıtılmış kablo yüzeyi** ölçülür; çıplak bara üzerine pil/PCB temas etmez.

IR kutusu 54×82×26 mm; iki kapsüllü mıknatıs ve ayarlanabilir kaide konsepti. SHT açıklığı kaplanmaz; su itici geçirgen membran gerekir. IR pencere LWIR uyumlu olmalı; sıradan cam uygun değildir. 350 mm düşey +235 mm derinlik farkında optik mesafe 422 mm, yatay görüş yaklaşık 1205 mm olur. Ancak 32 piksel genişlik yaklaşık 38 mm/piksel demektir: **20 mm adımlı tüm pabuçlar tek tek çözülemez**. Engellenen/örtüşen ROI ölçümleri geçerli gibi sunulmamalıdır; K3/K4 saha kalibrasyonunda bunu göstermelidir.

PD kutusu 80×118×45 mm. Mevcut M12 saplamaya aksesuar braket konsepti; PE bağlantısı gevşetilmez/sökülmez. HFCT ayrılabilir çekirdeği PE üzerine oturur. TEV yalıtılmış yüzey kuplajıdır. Faz konnektörü yalnız harici yalıtılmış 0..3,3 V referans alır.

GW kutusu 112×112×54 mm, 35 mm DIN klipsi. Mevcut ölçü/yardımcı kolon ve mühürlü anten geçişi kullanılır. Harici, uygunluk belgeli 5 V SELV/4 A PSU seçimi gerekir; taşıyıcıda 230/400 V yoktur. Kapak önünde 30 mm, terminallerde 50 mm, DIN sökme yönünde 20 mm servis hedefi vardır; bu değerler yüksek gerilim yaklaşma mesafesi değildir.

Sekiz pil düğümü ortak besleme/veri kablosu gerektirmez. TC-CT ≤150 mm, PD koaksiyel ≤500 mm, GW RS-485 hatları ayrı bükümlü ekranlı ve her biri hedef ≤1,5 m; SIM demeti ≤50 mm. Mevcut kablo kanalları kullanılır, servis halkası sabitlenir, pano üzerinde yeni delik açılmaz. Tüm uzunluklar tasarım hedefidir.

## Pil ve enerji hesabı

Eski 3 µA uyku/13,1 yıl hesabı B1 için kullanılmaz. OPA333 yaklaşık 17 µA tipik tüketir; bias bölücü 1,5 µA, FRAM bekleme, MCU/RTC/LSI/IWDG ve periyodik uyanma yükü ayrıca vardır. TC için **50 µA** bekleme bütçesi varsayılmıştır. TX/RX değerleri etkin MCU'yu içerir. Batarya yük testi 68 ohm/10 ms yaklaşık 530 µAs ekler; WAKE satırında eşdeğer yük olarak hesaba katılır.

| TC ER14250, 1,2 Ah; %85 kullanılabilir, yıllık %1 özdeşarj | Ortalama + özdeşarj | Hesaplanan ömür |
|---|---:|---:|
| IDLE 900 s | 55,58 µA | 764 gün |
| WATCH 60 s | 114,49 µA | 371 gün |
| BURST 10 s | 430,07 µA | 98 gün |
| %97 idle / %2,5 watch / %0,5 burst | 58,92 µA | 721 gün ≈2 yıl |

Kaynak `firmware/node/power.c` ve `hardware/B1/evidence/energy.log`. Bu ömürler ölçüm/garanti değildir; sıcaklık, HLC kaçağı, RF tekrarları ve hata durumları ayrıca ölçülmelidir. Hücre geriliminden kalan kapasite hesabı Li-SOCl2'nin düz deşarj eğrisinde kesin SoC ölçümü sağlamaz.

IR MLX90640 güç anahtarlamasıyla uyur; 25 mA/1 s/60 s örnek pencere tek başına 0,417 mA yapar. 2,6 Ah hücrede %85 kapasiteyle sensörün tek başına teorik üst sınırı yaklaşık 221 gündür; uzun ömür için gerçek pencere/kadans optimizasyonu gerekir. Bu, TC 2 yıl hesabıyla aynı değildir.

PD RF ön ucu 5 V/0,2 A varsayımı ve %80 verimde pilde yaklaşık 0,35 A ister. 60 s/saat sürekli pencere ortalama 5,83 mA; 8,5 Ah hücrede %85 kapasiteyle diğer yükler hariç yaklaşık 52 gün. Eski 1,8 mA PRPD bütçesi geçersizdir. Olay tetiklemeli kısa pencere ve HLC paketi gerekir; hedef PD sürücüsü henüz olmadığı için uzun pil ömrü taahhüt edilmez.

GW 2×10 F/2,7 V seri EDLC paketi yaklaşık 5 F eşdeğerdir; 10k dengeleme ve akım sınırlı şarj vardır. 4,6→3,6 V aralığında teorik enerji 20,5 J; %80 dönüşüm ve 2 W mantık yüküyle yaklaşık 8 s üst sınırdır. Gerçek ESR, sıcaklık, yük ve buck dropout ölçülmeden yedekleme süresi ilan edilmez. LTE hold-up hattında değildir.

## BOM / tedarik

'''
d02+=f'B1 BOM {len(bom["rows"])} satır içerir. Doğrulanmış fiyatlı satırların kit ara toplamı **{bom["known_subtotal_usd"]:.2f} USD**, fiyatı bilinmeyen satır sayısı **{bom["unpriced_line_count"]}**. Tam kit maliyeti henüz hesaplanamaz. Eski €470,59/€660,91 tabloları B1 için güncel teklif değildir. docs/07 başındaki revizyon notu bu sınırı açıklar. Kaynak/alternatif/termin: [BOM.md](../hardware/B1/BOM.md), [bom.json](../hardware/B1/bom.json).\n'
d03='''# 03 · Elektronik dokümantasyon / B1

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

'''
d03+=f'STM32WLE5CC gerçek ARM derlemesi: **{mem["flash_bytes"]} bayt flash**, **{mem["sram_reserved_bytes"]} bayt RAM** (4096 bayt yığın dahil), 0 uyarı, 0 undefined symbol. Kaynak 29 derleme birimi; MAP/ELF/BIN `hardware/B1/evidence/target/` içinde. Fiziksel çalıştırma yok. TC kimlikleri/CT hata semantiği/enerji regresyonları ve matematik öz testi ayrı doğrulanır. Ayrıntılar [hedef README](../firmware/node/port/stm32wle5/README.md).\n\n'
d03+='## Konnektörler (kart üzerindeki fiziksel pin numarası)\n\n'
for k,d in circuits.items():
 d03+=f'### {k}\n\n| Ref / işlev | Pin → ağ |\n|---|---|\n'
 for a in d['components']:
  if a['ref'].startswith('J') or a['value']=='EC21-E MiniPCIe SOCKET':
   ns=', '.join(f'{n}: {net or "NC"}' for n,net in a['nets'].items())
   d03+=f'| {a["ref"]} / {a["value"]} | {ns} |\n'
 d03+='\n'
d03+='''## Parça, kaynak ve düzenleme

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
'''
(ROOT/'docs/02-DONANIM-TASARIMI.md').write_text(d02,encoding='utf8');(ROOT/'docs/03-ELEKTRONIK-DOKUMANTASYON.md').write_text(d03,encoding='utf8')
print('docs/02 and docs/03 refreshed')
