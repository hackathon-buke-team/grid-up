# 02 · Donanım tasarımı / B1

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

B1 BOM 214 satır içerir. Doğrulanmış fiyatlı satırların kit ara toplamı **162.68 USD**, fiyatı bilinmeyen satır sayısı **206**. Tam kit maliyeti henüz hesaplanamaz. Eski €470,59/€660,91 tabloları B1 için güncel teklif değildir. docs/07 başındaki revizyon notu bu sınırı açıklar. Kaynak/alternatif/termin: [BOM.md](../hardware/B1/BOM.md), [bom.json](../hardware/B1/bom.json).
