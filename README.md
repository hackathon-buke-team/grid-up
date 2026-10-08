# PANO GÖZ

**Pano/hücre içi anomali erken uyarı sistemi — ADM & GDZ Elektrik "Grid Up" Hackathon**

Varlık: TEDAŞ-MLZ/2003-06.B, EK-II/14 çizimli, 1600 kVA dahili tip AG dağıtım panosu.
1600×1500×450 mm, 2312 A ana bara, 38 kA rms / 80 kA tepe kısa devre, IP2X, Form 2B.

---

## 1. Tez — bir paragrafta

Her yarışmacı panoya bir termometre koyar ve bir eşiğin üstünde alarm üretir. Bu sahada
çalışmaz: bir bağlantının sıcaklığını **durumu değil, yükü ve mevsimi** belirler. Şubatta
09:00'da 62 °C okunan bir pabuç kusurludur; ağustosta 15:00'te tam yükte okunan aynı 62 °C
normaldir. Sabit eşik ağustosu atlatacak kadar yükseğe kurulmak zorundadır, dolayısıyla
şubatta kördür. PANO GÖZ bunun yerine **θ**'yı ölçer:

```
θ_i = [ T_i − medyan(T_kardeşler) ] / (I / I_ref)²        [anma akımında kelvin]
```

Yük bölünerek düşer (I² sadeleşir), ortam sıcaklığı / mevsim / güneş kazancı çıkarılarak
düşer (aynı havadaki, 20 mm aralıklı, aynı yaştaki üç iletken), IR dizisinde yayıcılık
sadeleşir (aynı yüzey, aynı açı, aynı piksel dizisi). **Mutlak θ'nın kendisi geçmiş
gerektirmez**: bir bara üzerindeki üç özdeş faz, montaj gününde geçerli bir referanstır ve
ilk okumada doğrudan kullanılabilir. Bunun **kapsamı buraya kadardır**. Ürünün haftalar önce
haber veren yolu — kendi taban çizgisine göre yükselme, CUSUM teyidi, değişim noktası ve
3/5 günlük debounce — günlük medyanlar üzerinde çalışır ve **geçmiş gerektirir**: `joint_daily`
tablosunda en az beş gün olmadan sürüklenme teyit edilemez, kaynağından kurulan bir sistem o
beş günü beklemek zorundadır. Aynı tablodan **ileriye** bakan yol — bir sonraki seviye
basamağına kalan gün — daha fazlasını ister: 21 günlük pencerede en az **14 geçerli gün**
olmadan bir gün sayısı verilmez, `YETERSIZ_GECMIS` yazılır. İki yol birlikte satılır; "geçmiş gerektirmez" cümlesi yalnız
kardeş karşılaştırması için doğrudur. θ yeni bir icat değildir;
IR termografi pratiğinin zaten şart koştuğu "benzer bileşene göre benzer yük altında ΔT"
ölçütünün, yılda bir kez bir müteahhit tarafından değil, dakikada bir sürekli hesaplanan
hâlidir.

Sistem koruma yapmaz. Ark açması ABB TVOC-2 donanımında ~1 ms'de, SIL-2 seviyesinde
gerçekleşir ve bizi beklemez. Biz **gözlemler, konumlandırır, zaman damgalar, ilişkilendirir
ve yükseltiriz**.

---

## 2. Tek komutla çalıştırma

```powershell
# Windows PowerShell, proje kökünde
.\baslat.ps1
```

```bash
# ya da doğrudan
python -m panogoz.run_local
```

Docker gerekmez, broker kurulumu gerekmez, internet gerekmez. Varsayılan taşıma katmanı
süreç-içi bus'tır (`PANOGOZ_BUS=inproc`); gerçek Mosquitto'ya geçiş tek ortam değişkenidir
(`PANOGOZ_BUS=mqtt://host:1883`). Veri tabanının **tek sürücüsü vardır ve SQLite'tır**;
`PANOGOZ_DB` bir `postgresql://` adresi verildiğinde sessizce geri düşmez, hata verir.
TimescaleDB hedeflenen üretim yoludur ve **yazılmamıştır**: `schema.sql` taşınabilir SQL
olarak yazıldığı için PostgreSQL üzerinde değişmeden koşar, fakat hipertablo/sıkıştırma
cümleleri, toplu `COPY` yazma yolu ve Timescale üzerinde ölçüm yoktur.

Açılan uçlar:

| Uç | Adres | Ne için |
|---|---|---|
| Web arayüzü | http://127.0.0.1:8080/ | Dijital ikiz, alarm konsolu, bastırma ekranı |
| REST | http://127.0.0.1:8080/api/panel/SOKE-14 | Canlı pano görüntüsü (JSON) |
| WebSocket | ws://127.0.0.1:8080/ws | 1 Hz canlı akış |
| Sahte veri kanıtı | http://127.0.0.1:8080/api/analysis/supplied-data | §6'daki altı testin JSON hâli |
| SCADA southbound | Modbus TCP 127.0.0.1:5020 | Salt okunur register haritası |

Sık kullanılan seçenekler:

```
python -m panogoz.run_local --panels 112 --port 8080 --scada-port 5020 --backfill-days 75 --open
python -m panogoz.run_local --reset            # veritabanını silerek baştan
.\baslat.ps1 -Panels 24 -Port 8099            # daha küçük ve hızlı bir demo
```

### SCADA'yı kendiniz doğrulayın

```
modpoll -m tcp -0 -r 0    -c 20 -p 5020 127.0.0.1     # global blok
modpoll -m tcp -0 -r 1624 -c 48 -p 5020 127.0.0.1     # 14 numaralı pano bloğu
modpoll -m tcp -0 -r 1624 -p 5020 127.0.0.1 1         # yazma denemesi → exception 0x01
```

14 numaralı panonun adresi kafadan atılmadı: `PANEL_BASE + REGS_PER_PANEL × (n−1)`
= `1000 + 48 × 13` = **1624**. Yazma denemesi `ILLEGAL_FUNCTION` ile reddedilir — harita
istisnasız salt okunurdur (gerekçesi: [docs/PANOGOZ-ICD-v2.0.md](docs/PANOGOZ-ICD-v2.0.md)).

---

## 3. Jüri neye önce baksın

Beş dakikanız varsa sırayla şunlar:

1. **[docs/08-DEMO-SENARYOSU.md](docs/08-DEMO-SENARYOSU.md)** — ekranda ne olduğu, dakika dakika.
2. **Bastırılmış alarmlar ekranı.** Ürünün en ikna edici parçası ürettiğimiz alarmlar değil,
   **üretmediğimiz** alarmların gerekçeli listesidir. "78 °C okudun, neden bana söylemedin?"
   sorusunun cevabı ekranda, operatörün dilinde, sayılarıyla durur.
3. **Ark olayı beat'i.** TVOC-2 açar, biz açmayız; ekranda "koruma bizde değil" yazar ve
   bildirim gecikmesi tek bir temiz sayı olarak değil, **4–13 s aralığı** olarak gösterilir.
4. **[docs/04-ANOMALI-TESPIT.md](docs/04-ANOMALI-TESPIT.md) §3, görülebilirlik tablosu** —
   yük düştükçe kör olduğumuzu söyleyen tablo. Bunu saklamıyoruz, ekranda gösteriyoruz.
5. **Sağlanan verinin sentetik olduğu ve neyi ölçemediği** — altı istatistiksel ölçüm, §6.

Kod tarafında tek dosya okunacaksa: `panogoz/detector/theta.py`. Yöntemin tamamı ve neden
dekonvolüsyon yapmadığımız orada, ölçülmüş sayılarla yazılıdır.

---

## 4. Belge haritası

| Belge | İçerik |
|---|---|
| [docs/01-SISTEM-MIMARISI.md](docs/01-SISTEM-MIMARISI.md) | Uçtan uca mimari, "modül" tanımı, on-premise duruş, depolama aritmetiği, Sparkplug B reddi |
| [docs/02-DONANIM-TASARIMI.md](docs/02-DONANIM-TASARIMI.md) | 9 cihazlık kit, montaj yüzeyleri ve bunları sağlayan TEDAŞ maddeleri, çevresel tasarım, manyetik ortam |
| [docs/03-ELEKTRONIK-DOKUMANTASYON.md](docs/03-ELEKTRONIK-DOKUMANTASYON.md) | Kart blok şemaları, I/O tabloları, konnektör pin dizilimleri, katman yığını, HFCT analog zinciri, güç ağacı, BOM |
| [docs/04-ANOMALI-TESPIT.md](docs/04-ANOMALI-TESPIT.md) | θ türetimi, RLS kestirici, görülebilirlik tabanı, CUSUM/ARL0, yedi arıza modu, H3, yoğuşma, reddettiğimiz yöntemler |
| [docs/05-SAHA-UYGULAMA.md](docs/05-SAHA-UYGULAMA.md) | Kurulum prosedürü (yalnız Profil B), dizüstüsüz devreye alma, filo işletimi, TEDAŞ Madde 3.1 uyum notu |
| [docs/06-OLCEKLENEBILIRLIK.md](docs/06-OLCEKLENEBILIRLIK.md) | 100 → 1000 → 10 000 pano, ölçülmüş kaynak profili, RS-485 topolojisi |
| [docs/07-MALIYET-FAYDA.md](docs/07-MALIYET-FAYDA.md) | BOM maliyeti, 5 yıllık TCO, fayda modeli, **negatif senaryo önce** |
| [docs/08-DEMO-SENARYOSU.md](docs/08-DEMO-SENARYOSU.md) | 5 dakikalık demo, replikleriyle ve kesme çizgileriyle |
| [docs/09-VERI-ANALIZI.md](docs/09-VERI-ANALIZI.md) | Sağlanan `İstenen Veriler.xlsx` dosyasının tam karakterizasyonu — §6'daki kanıtların uzun hâli |
| [docs/10-MV-HUCRE-KONSEPTI.md](docs/10-MV-HUCRE-KONSEPTI.md) | OG hücre konsepti — çizim verilmedi, dürüstçe konsept |
| [docs/11-ACIK-SORULAR.md](docs/11-ACIK-SORULAR.md) | Yalnız müşterinin cevaplayabileceği sorular ve her birinin tasarımı nasıl değiştireceği |
| [docs/PANOGOZ-ICD-v2.0.md](docs/PANOGOZ-ICD-v2.0.md) | SCADA arayüz kontrol dokümanı — koddan üretilir, elle yazılmaz |
| [docs/panogoz_points.csv](docs/panogoz_points.csv) | Aynı haritanın SCADA import'u için düz nokta listesi |
| [sunum/PANO-GOZ-Final-Sunumu.pdf](sunum/PANO-GOZ-Final-Sunumu.pdf) | Final sunumu, PDF: 23 slayt, 16:9, yer imli |
| [sunum/index.html](sunum/index.html) | Aynı sunumun canlı hâli: tek dosya, internetsiz; N konuşma metni, S konuşmacı ekranı, Q jüri soruları. `python sunum/build.py --pdf` ikisini birlikte yeniden üretir |

---

## 5. Depo haritası

```
panogoz/
  contracts/      Tek doğruluk kaynağı — başka hiçbir yerde sayı tanımlanmaz
    assets.py       Pano geometrisi, 12 fider, 74 cıvatalı bağlantı, 9 cihaz, kardeş grupları
    channels.py     Kanal (metrik) kütüğü, 7 arıza modu ve ağırlıkları, 5 kademeli seviye merdiveni
    envelope.py     Telemetri zarfı, MQTT konu şeması, sıra numarası takibi
    icd.py          SCADA Modbus register haritası (ICD belgesi buradan üretilir)
    live.py         PanelLive / JointView / ArcView / PdView — ekran ile register aynı nesneden
  store/          SQLite (tek sürücü) + taşınabilir şema (store/schema.sql)
  bus/            Süreç-içi ve MQTT sürücüleri, aynı arayüz
  sim/            Dijital ikiz: yük, ısıl model, 17 arıza senaryosu, TVOC-2 ve MPR-53CS
                  register sunucuları, PRPD üreteci
  gateway/        Modbus master (poller), ağ geçidi, yerel kritik kurallar, store-and-forward
  detector/       θ (RLS), CUSUM, değişim noktası, çiy noktası, nötr H3, motor
  rules/          Bastırma → füzyon → alarm yaşam döngüsü
  notify/         GSM modem / SMPP, vardiya merdiveni, onay jetonu
  scada/          Modbus TCP slave (salt okunur) ve ICD üreteci
  api/            REST + WebSocket + demo senaryo uçları
  run_local.py    Tek süreçte tüm sistem — ana çalıştırma yolu
baslat.ps1        Windows tek komut sarmalayıcısı (ağa çıkmaz, paket kurmaz)
firmware/node/    Uç düğüm firmware'i, C99, STM32WLE5CC, float yok, malloc yok
frontend/         Arayüz: dijital ikiz, alarm konsolu, bastırma ekranı, SCADA görünümü
analysis/         Sağlanan xlsx dosyasının istatistiksel karakterizasyonu
tests/            Kabul testleri; her modülün ayrıca kendi self-test'i var
docs/             Bu belge paketi
```

Her modül tek başına çalışır ve kanıt basar:

```
PYTHONIOENCODING=utf-8 python -m panogoz.detector.theta      # θ kestiricisi, RLS vs dekonvolüsyon
PYTHONIOENCODING=utf-8 python -m panogoz.detector.cusum      # ARL0 aritmetiği ve otokorelasyon cezası
PYTHONIOENCODING=utf-8 python -m tests.test_integration      # uçtan uca kabul kapısı
PYTHONIOENCODING=utf-8 python -m tests.test_scada            # 100 panolu Modbus taraması
PYTHONIOENCODING=utf-8 python -m analysis.supplied_data      # sağlanan kümenin analizi
PYTHONIOENCODING=utf-8 python -m pytest -q                   # gerileme takımı (regression)
```

Gerileme takımı, daha önce gerçekten yaşanmış hataları yeniden üretip kilitler:

| Dosya | Neyi kilitler |
|---|---|
| `tests/test_alarm_load_regression.py` | Dedektör kararının anlık θ ile ezilmemesi; bara/fider yük ölçeklerinin ayrı kalması; geçmişten debounce penceresi kurulabilmesi |
| `tests/test_transport_regression.py` | Paho `ReasonCode` işlenmesi; PUBACK'sız mesajın tampondan düşmemesi; yeniden başlatmada outbox'ın geri yüklenmesi |
| `tests/test_stream_regression.py` | Tekrarlanan/eski zarfın canlı değeri, RLS'yi ve tazelik saatini geri almaması |
| `tests/test_cadence_regression.py` | Tazelik pencerelerinin cihazın ilan ettiği periyottan türetilmesi (900/60/10 s) |
| `tests/test_thd_attribution_regression.py` | Üç faz THD'sinin şebeke olayı **adayı** sayılması; ısıl bulguyu tek başına silmemesi |
| `tests/test_negative_pipeline.py` | Yedi negatif kontrolün gerçek boru hattında alarm üretmemesi — ve aynı koşumda pozitif kontrolün üretmesi |

---

## 6. Sağlanan veri hakkında — sentetiktir, bu yüzden saha başarısı bununla ölçülemez

Yarışma verisi örnek/sentetik bir kümedir; bunu ortaya çıkarmak bir başarı değildir,
**sonuçlarını dikkate almak** bir zorunluluktur. Aşağıdaki ölçümler "verinizi yakaladık"
demek için değil, bu kümeyle **neyin ölçülemeyeceğini** sayıyla göstermek için yapılmıştır.

Kümede olmayanlar, doğrudan bizim problemimiz oldukları için önemlidir:

* **Sıcaklık ve nem yok.** `Sıcaklık_Nem` sayfası tamamen boştur. θ bir sıcaklık farkıdır;
  sıcaklık serisi olmayan bir veri kümesinde θ hesaplanamaz, dolayısıyla bu dosya
  dedektörün doğruluğu hakkında hiçbir şey söyleyemez.
* **Etiketli arıza geçmişi yok.** Hangi bağlantının ne zaman gevşediği kayıtlı değildir;
  yanlış alarm oranı ya da haber verme süresi bu kümeden **hesaplanamaz**.
* **Kardeş yapısı yok.** Tek bir akım serisi vardır; θ'nın dayandığı üç faz / komşu pabuç
  eşleşmesi yoktur.
* **Anomali yok.** Küme panonun anmasının %3.9 ile %23.4'ü arasında yaşar: aşırı yük yok,
  tepe yok, olay yok.

"Akım Sensörü" sayfası 15 dakika aralıklı 152 satırdır ve düzgün dağılımlı gürültü
imzası taşır (`=RASTGELEARADA(15;90)` ile uyumlu). Altı bağımsız ölçüm:

| Test | Ölçülen | Gerçek bir fiderde beklenen |
|---|---:|---|
| Lag-1 otokorelasyon | +0.0003 | > +0.97 |
| var(fark)/var(seri) | 2.0023 | ≪ 2 (tam beyaz gürültü değeri 2) |
| Fazlalık basıklık | −1.2129 | ≈ 0 (−1.2 kesikli düzgün dağılım imzasıdır) |
| KS testi, U(14.5, 90.5) | D = 0.0526 | 0.1101 kritik değerini aşmalı |
| 76 tam sayı üzerinde χ² düzgünlük | χ² = 76.00, sd = 75, p = 0.446 | reddedilmeli |
| Aynı saatte gün-üstü şekil korelasyonu | r = +0.0596 | > 0.85 |

Saatlik ANOVA da farksızdır: F(23,128) = 1.375, p = 0.135 — gerçek bir fiderde günün saati
akımı belirler. Ham istatistikler: n = 152, min 15, maks 90, ortalama 52.1316, medyan 49.5,
sd 22.6504, CV 0.4345 mA; ×6 ile primer 90…540 A, ortalama 312.79 A.

Ek olarak sayfanın kendi başlığı çelişkilidir: "125 mA karşılığı 5 A" bir 40:1 ara akım
trafosunu tarif eder, TEDAŞ 2500/5 ile kaskat 20 000:1 = 20.0 A/mA eder; oysa formül
`600000/100` = 6000 = **6.0 A/mA** uygular. Aradaki fark 3.33 kattır. Üstelik
125 mA × 6.0 = 750 A'dir, belirtilen 600 A tam ölçek değil.

Bu yüzden model eğitimini sağlanan veriye dayandırmadık. Fizikten türetilmiş bir dijital
ikiz kurduk (`panogoz/sim/`), kabul kriterlerini ölçtük (`tests/test_sim_acceptance.py`) ve
sağlanan kümeyi de aynı testlerden geçirdik. Bunun sonucu şudur ve açıkça söylenmelidir:
**bu paketteki hiçbir başarım sayısı saha verisiyle doğrulanmış değildir.** Hepsi ya
fizikten türetilmiş bir simülatör üzerinde, ya da analitik olarak (CUSUM ARL formülü,
θ_min = 3σ/f²) hesaplanmıştır. Gerçek yanlış alarm oranı ancak etiketli saha geçmişi olan
bir pilot tesiste ölçülebilir.

---

## 7. Yapmadıklarımız ve nedenleri

Bir hackathon teslimi için en değerli bölüm budur.

| Yapmadık | Neden |
|---|---|
| **Bara bölmesine sensör** | Panoda AG giriş kesicisi **yoktur** ("direk bara bağlantı", Madde 2.2.10.2.vi). Bara bölmesini enerjisiz yapmak, tüm dağıtım merkezini OG tarafından karartmak demektir. 1. gün kiti yalnız alt kablo bölmesi + ölçü kolonu + mevcut 10 A prizdir. Bara bölmesi profilini yazmadık, **sildik**. |
| **Enerji hasadı iddiası** | Bara yakınında akım trafosuyla hasat teorik olarak mümkündür; ölçmedik. Ölçmediğimiz bir şeyi teklif etmeyiz. Birincil Li-SOCl2 hücre, 9–16 yıl tasarım ömrü. Hasat, tezgâh ölçümüne bağlı belgelenmiş bir gelecek seçeneği olarak durur. |
| **Tek başına PD ile ekip yönlendirme** | 400 V'ta klasik kısmi deşarj oluşmaz (Paschen minimumu 327 V). RF kanalı gevşek bağlantı mikro-arkını ölçer, pC **eşdeğeri** raporlar, IEC 60270 izlenebilir **değildir** ve AG'de tek başına asla ekip yönlendirmez — yalnız ısıl bulguyu destekler. |
| **Derin öğrenme / pano başına LSTM** | Kayan pencerede eğitilen bir otokodlayıcı yavaş sürüklenmeyi **öğrenir ve yeniden üretir**; yani tam olarak avladığımız 0.2 K/hafta sinyaline yapısal olarak kördür. Ayrıca elimizde olmayan aylarca temiz geçmiş ister ve 100 panoya özel 100 model bir işletme yüküdür. Gerekçeler: [docs/04](docs/04-ANOMALI-TESPIT.md) §10. |
| **SCADA'ya yazma yolu** | Modbus'ta kimlik doğrulama yoktur. TVOC-2'ye otokontrol komutu verebilen bir sisteme kimliksiz yazma açmak kabul edilemez. FC 05/06/15/16 istisnasız reddedilir. |
| **Sparkplug B** | Sparkplug 3.0, DDATA için QoS 0 **zorunlu** kılar. Dayanıklılık hikâyemiz ağ geçidinde PUBACK ile ilerleyen bir store-and-forward filigranına dayanır ve bu mekanizma QoS 0'da yoktur. Doğum/vasiyet/monoton sıra numarasını koruduk, markayı bıraktık. |
| **IEC 60870-5-104 ve OPC UA sunucuları** | Nokta listeleri yazıldı, sunucular kurulmadı. Bu hackathonda **yalnız Modbus TCP slave çalışır durumda** teslim edilmiştir. |
| **Gerçek SMS gönderimi** | GSM modem AT diyaloğu ve SMPP oturumu gerçekçi biçimde simüle edilir, transkript kaydedilir; hiçbir yere mesaj gitmez. Sesli arama yolu da simülasyondur; gerçek dağıtım TTS ağ geçidi ister. |
| **KiCad kaynak dosyaları** | Kart tasarımı blok şema, I/O tablosu, konnektör pin dizilimi, katman yığını ve BOM düzeyinde belgelenmiştir. Saklanan bir dosya yoktur; **çizilmemiştir**. |
| **OG hücre donanımı** | Hiçbir OG çizimi verilmedi; istedik. [docs/10](docs/10-MV-HUCRE-KONSEPTI.md) jenerik 36 kV kablo bölmesi için konsept, montaj ve maliyet verir, ürün iddia etmez. |

---

## 8. Dürüstlük kuralları

Bunlar pazarlama cümlesi değil, kodda karşılığı olan kurallardır.

1. **PANO GÖZ koruma değildir.** Bildirim gecikmesi bir aralıktır: TVOC-2 Modbus görüntüsünün
   yenilenmesi (ABB dokümante etmiyor, 0.2–2 s modellendi) + 1 s tarama + sunucu + SMS yolu
   = **4–13 s**. Tek temiz sayı vermiyoruz.
2. **Kör olduğumuz yeri söyleriz.** `DE_ENERGISED`, `SENSITIVITY_LOW`, `MOUNT_LOST`,
   `AIM_SHIFTED`, `CELL_LOW`, `STALE` birinci sınıf durumlardır; pano arızalarından ayrı
   raporlanır, asla karıştırılmaz.
3. **Bastırılmış alarmlar kendi ekranı ve kendi gerekçesi olan bir üründür.**
4. **Enerji hasadı iddia edilmez.**
5. **Enerjili bara bölmesine montaj iddia edilmez.**

---

## 9. Belgelendi, kodlanmadı

Bu paketin her belgesinin sonunda aynı başlıkla bir liste vardır. Kısa özet:

| Konu | Durum |
|---|---|
| IEC 60870-5-104 / OPC UA sunucuları | Nokta listesi var, sunucu yok |
| KiCad şematik ve PCB kaynağı | Blok/I-O/BOM düzeyinde belgelendi, çizilmedi |
| Gerçek GSM/SMPP gönderimi, sesli arama | Simüle edildi, transkript üretiliyor |
| OTA imzalı firmware dağıtımı | Politika yazıldı, dağıtım altyapısı kurulmadı |
| TimescaleDB sürücüsü | **Yok.** `Store` yalnız SQLite'tır; `postgresql://` adresi reddedilir |
| TimescaleDB hipertablo/sıkıştırma/sürekli toplam cümleleri | **Yazılmadı.** `schema_timescale.sql` diye bir dosya yoktur |
| Timescale toplu `COPY` yazma yolu | Yok; belgelerdeki Timescale rakamları yayınlanmış veriden türetilmiştir, ölçüm değildir |
| `docker-compose.yml` güvenlik seviyesi | Topoloji tarifidir, sertleştirme değildir: çalışan dinleyici anonim düz MQTT, mTLS ve ACL yorum satırında, host portları doğrudan yayında |
| Enerji hasadı | Ölçülmedi, iddia edilmiyor |
| OG hücre donanımı | Konsept, prototip yok |
| NFC ile devreye alma | Akış tasarlandı, NFC yongası tezgâhta denenmedi |
| "Eşiğe kalan gün" için SCADA register'ı | **Yok.** 48 register'lık pano bloğu tam dolu; büyütmek her panonun taban adresini kaydırır ve yayınlanmış ICD v2.0'ı bozar. Eklemeli bir ETA bloğu [docs/04](docs/04-ANOMALI-TESPIT.md) §6.1.5'te tarif edildi, kurulmadı |
| Ufuk projeksiyonunun saha kalibrasyonu | Güven aralığının kapsaması **simülasyonda** ölçüldü (nominal %90'a karşı %88-93). Gerçek haber verme süresi ancak etiketli saha geçmişiyle ölçülebilir |
