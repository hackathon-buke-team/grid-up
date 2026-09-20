# K4 · 4.5 Jüri Soru-Cevap Kartları

> Her kart: olası soru → kısa, dürüst cevap → nereye bakılacağı. Anlatı script'iyle
> çelişen hiçbir şey söyleme; "yapıldı" ile "yapılmadı/ölçülmedi" ayrımını koru
> ([`anlati-script.md`](anlati-script.md) §6). **Son güncelleme: 2026-09-20.**

## Ürün / metodoloji

**S: θ neden sabit sıcaklık eşiğinden iyi?**
> Sabit eşik yük ve mevsimi ayıramaz. Aynı simülatörde ölçtük: sabit 75 °C "sıcak yaz" kontrolünde
> 10/10 yanlış alarm veriyor, düşük yükte gizli arızayı 0/10 yakalıyor; θ ilkinde 0 yanlış alarm,
> ikincisinde 10/10 tespit. θ kardeş fazların ortak ısınmasını medyanla iptal eder, kalan farkı yükün
> karesine böler. (`docs/09` §3.2)

**S: Sabit eşik tamamen kötü mü, sizin avantajınız ne?**
> Hayır. Ortama göre "+45 K" kuralı güçlü bir rakip: kademeli arızada bizden erken (5,84 gün; bizim
> ALARM'ımız 7,58 gün). Bizim avantajımız kademelide **UYARI'nın 3,0 günde gelmesi**, **düşük yükte
> görünürlük** ve sıcak yazda yanlış alarm üretmemek. Bunu tabloda kendimiz gösteriyoruz.

**S: Kaç arıza modu / senaryo var?**
> 22 senaryo: 11 arıza (gevşek cıvata ani/kademeli/sıcak yazda/düşük yükte gizli, sürekli aşırı yük,
> yoğuşma, nötr harmonik yüklenme, nötr bağlantı gevşemesi, PD + nem, ark TRIP, ark koruma bütünlüğü
> kaybı), 1 yalnız-uyarı (PD tek başına) ve 10 negatif kontrol. (`docs/09` §1)

**S: Eski planda "17 senaryo / 7 arıza modu" yazıyordu?**
> O rakamlar projenin sıfırdan yeniden yazılan önceki sürümünün plan belgesinden; CLAUDE.md'de bilerek
> "kod seviyesinde doğrulanmadı" diye işaretli. Bu depoda gerçek olan yukarıdaki 22 senaryodur.

**S: %100 tespit ve 0 yanlış alarm çok iyi görünüyor, güvenilir mi?**
> Bu bir saha doğrulaması değil, **model içi öz-tutarlılık**: dedektörü yazdığımız fizik modeline karşı
> sınadık; organizatör yalnız L1 CT akımı verdi, sıcaklık/nem/PD/ark sekmeleri boştu. Anlamlı olanlar:
> sabit eşiklerle kıyas, kör bölge ve kırılma noktası ölçümü, model parametrelerine dayanıklılık ve
> test sırasında bulduğumuz 6 gerçek hata (`docs/09` §0, §4). 0 yanlış alarm için dürüst ifade:
> 18,1 pano-yılında 0, %95 üst sınır 0,17 / pano-yılı.

**S: "Haftalar önce" uyarı iddianız sağlam mı?**
> Yalnız bozulma haftalar sürüyorsa. 8 haftalık yavaş gevşemede UYARI tehlikeden ≈15 gün, ALARM ≈3 gün
> önce gelir. Ani arızada (dakikalar içinde gelişen) haber verme ≈0; ALARM yarım saat içinde gelir ve
> bunu "önceden" diye sunmuyoruz. Bunu fizik belirliyor, biz seçmiyoruz. (`docs/09` §3.4)

**S: Sistem neyi göremez?**
> (1) **ALARM kör bölgesi:** direnç artışı < ≈×1,8'de yalnız UYARI (günlük θ medyanı üzerinde CUSUM);
> bilinçli, 15 K altına sevk çıkarmak yanlış alarm bütçesini bozar. (2) **Sensör gürültüsü ×4'te**
> (1 K gürültü, 2 K ofset) 3/10 sağlıklı koşuda yanlış ALARM; sahada sıfır-yük izotermal ofset
> kalibrasyonu kurulum adımı olmalı. (3) Taban çizgisinde arıza varsa "normal" öğrenilir.

**S: Düşük yükte (gece) çalışır mı?**
> %40 anma altında θ hesaplanmaz; "bilgi yok" ile "arıza yok" karıştırılmaz ve bu örnekler Bastırma
> ekranında sayılır. "Düşük yükte gizli arıza" senaryosunda (RMS %45) θ 10/10 yakalıyor, sabit eşikler 0/10.

**S: Alarm yorgunluğunu nasıl önlüyorsunuz?**
> Sıra sabit: bastırma → onay → füzyon. 3/5 debounce, %40 ölü bant, iki kanal ailesi şartı (PD tek
> başına UYARI'da kalır, ekip sevk edilmez), 7 gün kendiliğinden kapanma, alıcı başına saatlik fırtına
> sınırı + tek [ÖZET] mesajı, KRİTİK bastırılamaz. Yanlış alarm bütçesi ölçüldü. (`docs/12`)

## Mühendislik / gerçeklik

**S: Bu gerçekten çalışıyor mu, yoksa hepsi simülasyon mu?**
> Yazılım gerçek ve çalışır; **veri** sentetik. Gerçek olanlar: organizatörün CT serisinin yük biçimi,
> gerçek Modbus TCP ve IEC 104 sunucuları (bağımsız istemcilerle okundu), gerçek MQTT protokolüyle ayrı
> süreçteki broker'a karşı 5 senaryo, gerçek Edge'de çekilmiş arayüz görüntüleri, 291 test. Sentetik
> olanlar: sıcaklık/nem/PD/ark kanalları (fizik modelimiz) ve arızalar.

**S: Gerçek bir SMS/Telegram mesajı gönderdiniz mi?**
> Bu kodla henüz **hayır**. Telegram kanalı (tek yönlü + `ONAY` yanıtı) ve on-prem GSM modem SMS
> kanalı kodlu ve testli (sahte HTTP / sahte seri port); arayüzdeki telefonlar bellek içi gösterim.
> Gönderim komutu hazır: `python -m tools.send_real_alarm_demo --send --wait-ack 120`. (`docs/12` §0)

**S: Neden üretimde SMS/GSM modem, Telegram değil?**
> On-prem zorunluluğu ve veri mahremiyeti: GSM modem yerel, üçüncü taraf bulut yok. Mesaj yalnız
> bağlantı kimliği, şiddet, alarm türü ve puanı taşır; ham sensör verisi dışarı çıkmaz. Telegram demo
> içindir. (`docs/12` §1, §3)

**S: Neden Eclipse Mosquitto değil de amqtt?**
> Denedik: bu makinede Windows UAC/admin kısıtı yüzünden Mosquitto ikili dosyası çalıştırılamadı (iki
> gerçek denemeyle doğrulandı). `amqtt` gerçek bir MQTT 3.1.1 uygulaması; ayrı süreç, gerçek TCP. Kod
> MQTT 3.1.1'e bağlı olduğundan admin erişimli makinede değişmeden Mosquitto'ya geçilir. Ayrıca
> `bus/store` çalışan konsol boru hattına henüz bağlı değil; bileşen olarak testli. (`docs/01` §2, §6)

**S: SCADA gerçek bir RTU'ya mı bağlanıyor?**
> Hayır, şartname bunu istemiyor; haritalama yeterli. Bizim tarafımız gerçek: Modbus TCP slave (ICD
> v2.0, 32 register/pano, 200 pano, yalnız okuma) ve IEC 60870-5-104 slave (genel tarama, kendiliğinden
> bildirim, saat senkronu, kontrol komutu reddi) çalışıyor; ikisi de bağımsız istemcilerle doğrulandı.
> Sınırlar: IEC 62351-3 (TLS) yok, sahadaki farklı üretici master'larla denenmedi.

**S: Ölçek? 100 modül/pano, 1000 pano?**
> Ölçtüğümüz iki şey: (1) yalnız-θ yolu 250→500→1000 pano doğrusal, 1000 panoda RSS 173 MB;
> (2) çok kanallı filo: 22 pano × 60 gün için toplu analiz ≈11 bin pano-örneği/sn, alarm motoru
> ≈170 bin/sn tek çekirdekte. 1000 panonun canlı akışı ≈1,1 pano-örneği/sn, yani kestirimle dört
> büyüklük mertebesi pay. **Ölçülmeyen:** 1000 panoluk çok kanallı yük testi ve dedektörlerin artımlı
> (akış) sürümü. Bunu kestirim olarak sunuyoruz. (`docs/06` §2–3b)

**S: Sistem on-prem mi, güvenli mi?**
> On-prem tasarlandı, public cloud yok. Compose'da mTLS dinleyici, cihaz başına ACL (cihaz yalnız kendi
> konusuna yazar), kök olmayan kullanıcı, `cap_drop: ALL`, iç ağ. **Doğrulanan:** yapılandırma
> değişmezleri, ACL anlamı (Python yeniden uygulamasıyla), PKI + gerçek mTLS el sıkışması, `MqttBus`
> TLS yolu. **Doğrulanmayan:** `docker compose up`; bu makinede Docker yok, konteyner hiç çalıştırılmadı.
> (`docs/13` §0)

## Donanım

**S: Fiziksel prototip var mı?**
> Yok ve şartname istemiyor (kart lehimlenmeyecek). Elimizde tasarım dosyaları var: 3 KiCad şematiği
> (ERC 0 hata), 3 PCB (gerçek footprint'lerle DRC 0 kısa devre/clearance/courtyard, kalan uyarılar
> kozmetik), 3B render, ölçülü kabin-içi yerleşim (1600×1500×450 mm, alt bölümde ≥400 mm boşluk).

**S: Firmware gerçek mi?**
> Gerçek hedefte derleniyor: `arm-none-eabi-gcc` ile STM32WLE5CC için 3/3 kart link, 0 float komutu
> (objdump ile doğrulandı), host'ta `--selftest` 0 hata. **Ama iskelet:** θ sabit-nokta çekirdeği +
> MAX31855 çözücü + startup; PD histogramı/sınıflandırıcı yok, gerçek donanımda hiç flash'lanmadı.
> (`docs/07`)

**S: Neden STM32WLE5CC?**
> Tek çipte MCU + sub-GHz radyo, düşük güç, pille çalışan uç düğümler (TC/IR-PD) için. Gateway kablolu
> Ethernet (W5500) kullanır; sabit, şebeke beslemeli, güvenilirlik öncelikli.

**S: HFCT/PD sensörü Modbus'tan mı okunuyor?**
> Hayır, HFCT30/50 tamamen pasif/analog endüktif sensör; RF ön uç + yüksek hızlı örnekleme ister. IR/PD
> düğümü şemasında bunun için ayrı analog zincir var (bant geçiren filtre + LNA + log-amp zarf
> dedektörü). Ama yazılımdaki PD modeli tek skaler indeks; gerçek analog zincirin davranışı ona
> dönüşmüyor. (`docs/03` §5, `docs/09` §5)

**S: Yoğuşma dedektörü için donanımda sensör var mı?**
> **Hayır, bilinçli olarak açık madde:** dedektör iç hava T/RH sensörü ve duvar (soğuk nokta) NTC'si
> varsayıyor; bugünkü KiCad tasarımında yok. IR/PD düğümüne I²C T/RH + NTC girişi eklenmeli (K1).

**S: Saha koşullarına dayanır mı?**
> Bileşen bileşen değerlendirdik (`docs/02` §8): tek gerçek zayıf halka **HLK-PM01 besleme modülü
> (−20…+60 °C)**; diğer tüm bileşenler ≥85 °C'ye toleranslı. Kabin içi sıcak noktada besleme modülü
> yeniden seçilmeli.

**S: Maliyet?**
> BOM fiyat/tedarikçi tazelemesi yapılmadı (K1 1.6 açık); kesin bir maliyet rakamı vermiyoruz.

## Zor / tuzak sorular

**S: Bu kodun ne kadarını AI yazdı?**
> Proje Claude Code ile birlikte geliştirildi; kod üretimi AI destekli, çıktılar ham dosya ve gerçek
> araçlarla doğrulandı (KiCad `erc/drc`, `arm-none-eabi-gcc`, gerçek tarayıcı, mutasyon testi).
> Örnek: filo testinde tek arıza için 179 mesaj üreten bir hata testler yeşilken canlı akışta bulundu
> (`docs/09` §4 madde 6); ayrıca bir alt-ajanın "kontrol ettim" dediği ama hatalı çıkan çıktılar ham
> dosyadan yakalandı. Süreç şeffaf.

**S: Yarın gerçek bir panoya kurulsa?**
> Olmaz henüz; bu tasarım ve yazılım kanıtı. Saha kurulumu ayrı aşama: sensör ofset kalibrasyonu,
> taban çizgisi öğrenme, gerçek arıza dağılımıyla eşik ayarı, gerçek veriyle `docs/09` matrisinin
> tekrarı. 15/30/60 K eşikleri model tabanlı ilk plan değerleri.

**S: Bilmediğin bir şey sorulursa?**
> "Bu konuda şu an doğrulanmış verimiz yok, tahmin etmek istemiyorum; roadmap'te [X] altında." CLAUDE.md
> ilkesi: yapılmayan hiçbir şey yapılmış gibi yazılmaz.
