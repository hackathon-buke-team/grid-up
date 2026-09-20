# PANO GÖZ — Proje Briefi (K1–K4 tek dosya)

> Grid Up Hackathon (Patika.dev × ADM & GDZ Elektrik) için PANO GÖZ takımının tüm iş
> paketlerini (K1–K4) tek dosyada toplar. Proje kökünde `CLAUDE.md` olarak bırakılırsa
> Claude Code otomatik bağlam olarak okur; başka bir editörde de düz proje briefi olarak
> kullanılabilir.
>
> Kaynaklar: *Grid Up Hackathon Proje Konusu.pdf*, *Hackathon Verileri/* klasörü,
> *PANO-GOZ-TAKIM-GOREV-DAGILIMI-v1_1.docx* — 12 Eylül 2026 itibarıyla derlendi.

## 0. Durum Özeti

**Yarışma:** Grid Up Hackathon — Patika.dev × ADM & GDZ Elektrik. Online, 2–28 Eylül 2026,
takım azami 4 kişi, ödül 100.000 / 70.000 / 30.000 TL.

**Problem:** 1600 kVA'lık bir TEDAŞ AG panosunda (veya OG hücresinde) arıza öncesi
belirtileri — cıvatalı bağlantı gevşemesi, aşırı yük, yoğuşma, nötr harmonik yüklenme,
ark koruma bütünlüğü — haftalar önce yakalayıp ilgili ekipleri uyaran uçtan uca bir
izleme sistemi kurmak.

**Ürün fikri (θ metriği):** Sabit sıcaklık eşiği yerine, aynı ortamdaki kardeş
iletkenler arasındaki farkı anma akımına normalize eden bir metrik (θ) kullanmak.
Mevsim/yük etkisi sadeleşiyor: yazın körleşmeyen, kışın yanlış alarm üretmeyen bir
dedektör.

**İddia edilen bugünkü durum** (repo görülmedi — PANO-GOZ-TAKIM-GOREV-DAGILIMI-v1_1'den
aktarılıyor): ~39.300 satır (Python sunucu + C99 firmware + JS arayüz), 57 kanal,
7 arıza modu, 17 senaryo (10 alarm + 7 negatif kontrol), Modbus TCP slave (ICD v2.0.0,
pano başına 48 register, 200 pano kapasitesi), pytest 138 test. **Kod seviyesinde
doğrulanmadı** — bu dosya plan + şartname + sensör dokümantasyonundan derlendi.

**Gerçekten açık üç madde (P1):** fiziksel/mekanik yerleşim görseli · gerçek bildirim
kanalından tek mesaj · demo provası + video.

---

## 1. Sabit Kısıtlar (hepsi için geçerli)

- **On-premise zorunlu, Public Cloud YASAK.**
- Gerçek sensör/endüstriyel ekipman satın almaya, gerçek pano üzerinde saha kurulumuna
  **gerek yok** — sentetik/örnek veri kabul ediliyor.
- Gerçek RTU/SCADA'ya bağlanmak beklenmiyor — **sadece Modbus haritalamayı göstermek
  yeterli**.
- Fiziksel prototip **istenmiyor** — kabin içi modül için tasarım dosyası (şematik +
  PCB yerleşimi + mekanik görsel) yeterli, kart lehimlenmeyecek.
- Hedef ölçek: en az 100 modül/pano; pahalı işlemci/geliştirme kartına bağımlı olmayan
  donanım mimarisi.

---

## 2. Mimari (özet)

```
[Uç düğüm: TC / IR-PD / Gateway]
        │  MQTT (QoS1) veya in-proc bus
        ▼
[panogoz/bus] → [panogoz/store: SQLite outbox] → [panogoz/detector: θ/RLS, CUSUM, kurallar]
        │
        ├─→ [panogoz/scada] → Modbus TCP slave (+ planlanan IEC 60870-5-104)
        ├─→ [panogoz/rules] → bastırma → füzyon → alarm
        ├─→ [panogoz/notify] → SMS / WhatsApp / GSM modem
        └─→ [panogoz/api] → [frontend/] (izleme, alarm konsolu, kanıt ekranı, mobil)
```

- **Tespit:** θ = kardeş medyanına göre fark, anma akımına normalize; RLS ile ısıl
  gecikme çözülüyor. Sürüklenme: günlük medyanlarda CUSUM + değişim noktası. Nötr için
  ayrı kural: `K_N = ΔT/I²`. Yoğuşma: duvar sıcaklığı modeli + çiy noktası marjı. PD:
  faz çözünürlüklü histogram/sınıflandırıcı (AG'de tek başına ekip yönlendirmiyor).
  Ark: ABB TVOC-2 register'ları.
- **Alarm hijyeni:** sıra sabit — bastırma → füzyon → alarm. 3/5 günlük debounce, %40
  ölü bant, 7 gün kendiliğinden kapanma, iki kanal ailesi şartı, fırtına sınırı,
  kimliklendirilmiş onay (4 haneli token).
- **Taşıma:** in-proc bus / MQTT aynı arayüz arkasında; QoS1 store-and-forward, sıra
  numarası ileri-yalnız su damgası, cihaz yayın aralığı sözleşmeden (`dev.period_s`)
  türetiliyor.

---

## 3. Teknoloji Yığını

| Katman | Teknoloji |
| --- | --- |
| Sunucu | Python |
| Uç düğüm firmware | C99 (float/malloc yok), hedef **STM32WLE5CC**, `arm-none-eabi` |
| Frontend | Saf JS (framework yok) |
| Mesajlaşma | MQTT (Paho), QoS1; in-proc bus (dev/test) |
| SCADA | Modbus TCP slave (yalnız okuma) — ICD v2.0.0; planlanan IEC 60870-5-104 |
| Depolama | SQLite (outbox); TimescaleDB kapsam dışı bırakılabilir (P3) |
| Dağıtım | Docker Compose, on-premise; mTLS + ACL sertleştirme planlı |
| Test | pytest |

---

## 4. Referans Veri — sensör/pano gerçekleri (organizatör dosyalarından doğrulandı)

| Kaynak | Ne veriyor | Not |
| --- | --- | --- |
| **HFCT30 / HFCT50** (Techimp) | Kısmi deşarj (PD) sensörü, endüktif, BNC çıkış | **Tamamen pasif/analog** — 1–60 MHz (30mm) / 1–80 MHz (50mm) bant, 17 mV/mA hassasiyet, 50Ω yük. **Modbus'tan okunmuyor**; gerçek bir RF ön-uç + yüksek hızlı örnekleme zinciri ister. IR/PD düğümü şematiğinde bu ayrıca düşünülmeli. |
| **ABB TVOC-2(-COM)** | Ark koruma rölesi (Arc Guard System, SIL-2, <1ms tepki, 30 sensöre kadar) | Modbus register'ları: Trip 1-7 (detektör/röle/tarih/saat), Diagnostics (200-225), Error (son 6 hata, 6 haneli DTC), Sensor status (bit alanları), System state — tümü okunur (R), gerçek zamanlı durum. |
| **MPR-53CS** | 3 faz güç/enerji analizörü | Geniş Modbus register haritası: L1/L2/L3 gerilim-akım-P/Q/S, cosφ, frekans, THD, min/max, demand, enerji sayaçları, CT/VT oranı config register'ları. Akım örnek verisi bu cihazdan okunuyormuş gibi modelleniyor. |
| **1600 kVA AG Pano çizimi** (TEDAŞ-MLZ/2003-06.B, EK-II/14) | Mekanik zarf | **1600 (G) × 1500 (Y) × 450 (D) mm**, alt bölümde en az **400 mm** kablo/bara boşluğu. Mekanik yerleşim görseli (K1 · 1.3) bu ölçülere oturmalı. |
| **AG Pano Donanım Listesi** (1600 kVA satırı) | Elektriksel donanım | Ana bara 2×(100×10mm²) kalay kaplı elektrolitik bakır, CT oranı 2500/5, fider anma akımı 250/400A. |
| **AG Pano Malzeme Şartnamesi** (TEDAŞ, 66 sayfa) | Genel ulusal standart | Koruma derecesi, sıcaklık artışı, iç ark dayanımı, kablo giriş/çıkışı, havalandırma bölümleri — kabin tasarımı bu şartnameye referans vermeli. |
| **İstenen Veriler.xlsx** | Organizatörün verdiği örnek veri | Yalnız **"Akım Sensörü"** sekmesinde gerçek seri var: ~1,5 gün, 15 dk aralıklı, 100 mA sekonderli bir CT'nin (gerçek primer ~600A sınıfı) L1 fazı sekonder akımı + sayfadaki çarpanla hesaplanmış primer A karşılığı (örn. 53 mA → 318 A). **"Sıcaklık_Nem" sekmesi tamamen boş**, **"ARC"** ve **"PD"** sekmeleri de veri değil sadece referans notu (sırasıyla ABB TVOC-2 / DS_HFCT30'a işaret ediyor). **Bu üç kanalın sentetik verisi kendi fizik modelinizden üretilmeli** — organizatör hazır seri vermemiş. |

---

## 5. İş Paketleri

> Her paket ~6–6,5 iş günü, kasıtlı olarak farklı dosyalara dokunuyor. Ortak yüzey:
> `panogoz/contracts/` — buraya dokunmadan önce gruba haber verilir.

### K1 · Donanım ve Uç Düğüm
**Teslimat:** modülün TASARIM DOSYASI (şematik, PCB yerleşimi, mekanik montaj) + gerçek
hedefte derlenen firmware. **Fiziksel prototip beklenmiyor.**

- [x] **1.1** KiCad şematiği: TC düğümü, IR/PD düğümü, ağ geçidi kartı (besleme, sensör
      arayüzleri, RF ön ucu, koruma elemanları). *Bitti sayılır:* 3 şematik PDF, ERC
      temiz, docs/03 ile bileşen eşleşiyor. → `hardware/kicad/{tc-node,ir-pd-node,gateway}/`
      + `docs/03-ELEKTRONIK-DOKUMANTASYON.md`, gerçek `kicad-cli sch erc` ile 0 hata
      (2026-09-13).
- [x] **1.2** PCB yerleşimi + 3B görünüm (kart ölçüleri, katman yığını, konnektör
      tablosu, anten açıklığı). *Bitti sayılır:* her kart için üstten görünüm + 3D
      render PNG. → gerçek footprint'lerle (kurulu KiCad kütüphanelerinden verbatim)
      3 kart, gerçek `kicad-cli pcb drc` ile 0 kısa devre/clearance/courtyard-üst-üste
      (kalan uyarılar kozmetik — bkz. `docs/03-ELEKTRONIK-DOKUMANTASYON.md` §6),
      gerçek SVG üstten görünüm + gerçek 3D render PNG (2026-09-16).
- [x] **1.3** Mekanik: modülün 1600 kVA pano çizimi üzerinde montaj yerleşimi (mıknatıs
      kaide, kablo yolu, erişim mesafesi — bkz. §4 ölçüler). *Bitti sayılır:*
      ölçülendirilmiş yerleşim görseli. → `hardware/mekanik/kabin-ici-yerlesim.svg` +
      `docs/02-DONANIM-TASARIMI.md` (2026-09-13).
- [x] **1.4** STM32WLE5CC hedef derlemesi (`arm-none-eabi`, `make target`), flash/RAM
      raporu. *Bitti sayılır:* `make host && ./panogoz_node --selftest` (0
      failure) + gerçek `arm-none-eabi-gcc` ile 3 kart için `make target` (3/3
      link, flash/RAM raporu, 0 float instruction, pin haritası
      `hardware/kicad/build_boards.py` ile 15/15 eşleşiyor). →
      `firmware/node/`, `docs/07-FIRMWARE.md` (2026-09-16).
- [x] **1.5** Saha koşulları (yüksek/düşük sıcaklık, manyetik alan, titreşim) → şemadaki
      karşılığını dokümante et. *Bitti sayılır:* her bileşenin gerçek datasheet
      sıcaklık aralığı + manyetik alan/titreşim değerlendirmesi. → `docs/02-
      DONANIM-TASARIMI.md` §8 (gerçek zayıf halka: HLK-PM01, −20…+60°C —
      diğer tüm bileşenler ≥85°C'ye toleranslı) (2026-09-16).
- [ ] **1.6** BOM tazeleme (güncel fiyat/tedarikçi/alternatif).
- [ ] **1.7** *(opsiyonel — elde hazır kart varsa)* Ucuz kartla (Nucleo/ESP32) tek
      kardeş çiftinde gerçek θ demosu.

**Dosyalar:** `firmware/`, `hardware/` (yeni), `docs/02-DONANIM-TASARIMI.md`,
`docs/03-ELEKTRONIK-DOKUMANTASYON.md`

---

### K2 · Sunucu, Entegrasyon ve Ölçek
**Teslimat:** gerçek broker üzerinde çalışan sertleştirilmiş on-prem yığın + ikinci
SCADA protokolü.

- [x] **2.1** Gerçek Mosquitto ile uçtan uca test (bağlanma, yeniden bağlanma,
      broker/süreç restart, outbox replay, duplicate düşürme). *Bitti sayılır:*
      gerçek bir broker sürecine karşı 5 senaryonun hepsi geçen pytest. →
      `panogoz/bus/`, `panogoz/store/`, `tests/test_bus_mqtt_e2e.py`,
      `docs/01-MIMARI.md`. Not: bu makinede admin/UAC kısıtı yüzünden gerçek
      Eclipse Mosquitto ikili dosyası çalıştırılamadı (iki gerçek denemeyle
      doğrulandı, bkz. docs/01-MIMARI.md §2); yerine gerçek MQTT 3.1.1
      protokolü konuşan, ayrı process olarak çalışan `amqtt` kullanıldı —
      testler gerçek soket/gerçek protokol üzerinden geçiyor (2026-09-16).
- [ ] **2.2** Compose sertleştirme: mTLS listener, cihaz başına ACL, ters vekil, sağlık
      kontrolleri. **KISMİ (2026-09-19):** `docker-compose.yml`, `Dockerfile`,
      `deploy/mosquitto/{mosquitto.conf,acl}`, `deploy/nginx/*`, `tools/gen_certs.py`,
      `/healthz`+`/readyz`, `MqttBus` TLS yazıldı. **Doğrulanan:** yapılandırma
      değişmezleri, ACL anlamı (Python yeniden uygulaması), PKI + GERÇEK mTLS
      el sıkışması, MqttBus TLS yolu (`tests/test_deploy.py`, 31 test).
      **Doğrulanmayan:** `docker compose up` — bu makinede Docker/Mosquitto/nginx
      YOK, konteyner hiç çalıştırılmadı (bkz. `docs/13-DAGITIM-SERTLESTIRME.md` §0/§5).
      Docker'lı makinede canlı doğrulanınca `[x]` olur.
- [x] **2.3** IEC 60870-5-104 slave (nokta listesi + IOA şeması hazır → sunucu
      yazılacak: genel tarama, kendiliğinden bildirim, saat senkronu). *Bitti
      sayılır:* asyncio APCI durum makinesi (STARTDT/STOPDT/TESTFR, k/w penceresi,
      t1/t2/t3), genel tarama, kendiliğinden bildirim (M_ME_NB_1 + M_SP_TB_1/CP56),
      saat senkronu, okuma/test komutu, kontrol komutlarının reddi; **bağımsız
      üçüncü taraf master (Fraunhofer `c104`) ile** GI değerleri ICD register'larına
      eşit, olaylar/saat senkronu/komut reddi doğrulandı (30 test, 3 mutasyon
      yakalandı). Sınır: TLS (IEC 62351-3) yok, sahadaki farklı üretici
      master'larla denenmedi. → `panogoz/scada/{iec104,iec104_codec}.py`,
      `tests/test_iec104.py` (2026-09-19).
- [x] **2.4** 1000 pano yük testi + kaynak ölçümü (CPU/RAM/disk/yazma hızı/tur süresi)
      — kademeli 250→500→1000. *Bitti sayılır:* gerçek `psutil` ölçümü, 250/500/1000
      kademesinde doğrusal ölçekleniyor, kırılma noktası yok. →
      `panogoz/run_local.py`, `tools/run_load_test.py`,
      `docs/06-OLCEKLENEBILIRLIK.md` (2026-09-16).
- [x] **2.5** ICD ↔ Modbus otomatik tutarlılık testi + üçüncü taraf için CSV nokta
      listesi. *Bitti sayılır:* ICD v2.0 (pano başına 32 register, 200 pano)
      `panogoz/scada/icd.py`'de VERİ olarak tanımlı; doküman + CSV bundan ÜRETİLİR
      (`python -m tools.gen_icd`) ve test diskteki dosyanın koddan üretilenle aynı
      olduğunu doğrular; GERÇEK pymodbus istemcisiyle canlı Modbus sunucusu konsolla
      aynı değerleri okur, yazma/FC03/FC01 reddedilir. → `panogoz/scada/{icd,
      fleet_bridge,fleet_modbus}.py`, `docs/PANOGOZ-ICD-v2.0.md`,
      `docs/data/panogoz-icd-v2.0-points.csv`, `tests/test_icd.py` (2026-09-19).
      *(CLAUDE.md'nin eski "48 register/pano" iddiası bu depoda gerçek değildi;
      gerçek olan 32 register/pano.)*

**Dosyalar:** `panogoz/bus/`, `panogoz/store/`, `panogoz/scada/`, `panogoz/gateway/`,
`docker-compose.yml`, `Dockerfile`, `docs/01-MIMARI.md`, `docs/06-OLCEKLENEBILIRLIK.md`,
`docs/PANOGOZ-ICD-v2.0.md`

> **Not (şartname):** gerçek RTU/SCADA bağlantısı istenmiyor, yalnız Modbus haritalama
> yeterli — 2.1 ve 2.3 güzel ek puan ama zorunlu değil; vakit daralırsa ilk kısılacak
> yer burası.

---

### K3 · Monitoring ve Operasyon Deneyimi
**Teslimat:** jürinin ekranda göreceği her şey — merkez + saha için iki ayrı akış.

- [x] **3.1** Alarm konsolu: onay akışı, iş emri kartı, filtre/sıralama, fırtına
      görünümü, kapatma gerekçesi. *Bitti sayılır:* KPI şeridi, durum/şiddet/aile/pano
      filtresi + 5 sıralama, alarm detayı (kanıt grafiği, bastırma gerekçeleri, iş emri
      kartı: kesinti/güvenlik/adımlar, bildirim geçmişi), kimlikli onay (belirteç
      yalnız bildirim mesajında; "onay için doldur" telefon akışı), gerekçeli kapatma,
      sessize alma, fırtına bandı. GERÇEK Edge'de Playwright ile testli.
      → `frontend/{index.html,console.js,console.css,charts.js}`,
      `panogoz/api/{fleet_service,fleet_routes}.py`, `panogoz/rules/workorders.py`,
      `tests/test_{fleet_service,fleet_api,ui_e2e}.py` (2026-09-19).
- [x] **3.2** Kanıt ekranı: θ zaman serisi, CUSUM, değişim noktası işareti, kardeş
      karşılaştırma, bastırma gerekçeleri. *Bitti sayılır (kısmi — bkz. not):*
      θ serisi (zaten vardı) + kardeş faz karşılaştırması (3 fazın gerçek yüzey
      sıcaklığı, izlenen faz vurgulu — F02'de L2'nin ayrışması gözle net) +
      CUSUM/değişim noktası (gerçek demo filosunda dürüstçe "yetersiz veri",
      ayrı bir "uzatılmış demo örneği" düğmesiyle gerçekten tetiklenen bir
      CUSUM/değişim-noktası gösterimi — gün 30, gerçek ölçümün döşenmiş
      tekrarı). ~~"Bastırma gerekçeleri" kapsam dışı~~ — 2026-09-19'da bastırma→onay→
      füzyon→alarm katmanı kuruldu; gerekçeler artık alarm detayında ve Bastırma
      sekmesinde (bu eski ekran `frontend/kanit.html`'de olduğu gibi duruyor). → `panogoz/api/app.py` (`_evidence_payload`,
      `/api/connections/<i>/evidence`, `/api/cusum-demo/evidence`),
      `panogoz/sim/demo_fleet.py` (`build_cusum_demo_connection`),
      `frontend/{index.html,app.js,styles.css}`, `tests/test_api.py`
      (2026-09-16).
- [x] **3.3** Mobil/tablet görünüm: tek pano/bağlantı, konum, iş emri; QR ile doğrudan
      açılış (400px'te yatay kaydırma yok). *Bitti sayılır:* `saha.html` (tek pano,
      konum, aktif alarm + iş emri, mobilden onay); GERÇEK Edge'de 400 px'te
      `scrollWidth == 400` ölçüldü, QR ekran görüntüsünden OpenCV ile çözülüp doğru
      bağlantıyı verdi. → `frontend/saha.{html,css,js}`, `/api/fleet/panels/<id>/{qr.svg,link}`,
      `tests/test_ui_e2e.py` (2026-09-19).
- [x] **3.4** Bastırma ekranı + SCADA register canlı görünümü cilası (register ↔ ekran
      eşlemesi görsel olarak kanıtlı). *Bitti sayılır:* Bastırma sekmesi (gerekçe
      sayaçları: STALE/ENERJİSİZ/DÜŞÜK YÜK, füzyon tavanı, sessize alma) + SCADA sekmesi
      (32 register ham/hex/çözülmüş + her birinin konsoldaki karşılığı; canlı Modbus
      ile AYNI fonksiyon). → `frontend/console.js`, `panogoz/scada/fleet_bridge.py`.
- [x] **3.5** Demo kontrol paneli: senaryo enjekte/temizle, hız ayarı, sıfırlama —
      yalnız fareyle yönetilebilir. *Bitti sayılır:* saat başlat/duraklat/hız/güne atla,
      pano+senaryo seçip enjekte/temizle, fırtına başlat, sıfırla; hepsi düğme/açılır
      liste (klavye gerekmez); UI testiyle doğrulandı. Üretimde `--no-demo-controls`.
- [x] **3.6** Ekran görüntülerinin docs/08 demo senaryosuyla birebir eşlenmesi. *Bitti
      sayılır:* `docs/08-DEMO-SENARYOSU.md` 12 adımı, her biri GERÇEK Edge + çalışan
      sunucudan `tools/record_demo.py` ile çekilmiş 12 ekran görüntüsüne (+ GIF +
      `scada-okuma.txt`) eşler. Betik sessiz geçmez (mobilde alarm yok / [ÖZET] yok /
      yatay kaydırma / Modbus-IEC 104 okuması başarısız → çöker). Doğrulanan: fare-yalnız
      yollar (Gün 34→Başlat, Gün 52→Başlat, Sıfırla→Fırtına→Başlat) API ile denendi;
      07'de scrollWidth=400; SCADA okuması (pymodbus + c104) `10-scada.png` ile aynı
      değerler. Kayıtta iki gerçek kusur bulunup giderildi (yapışkan başlık tam sayfa
      çekimde ortaya düşüyordu; mobil görüntü alarmsız pano gösteriyordu; IEC 104 okuması
      Playwright döngüsü içinde başarısız oluyordu) (2026-09-20).

**Dosyalar:** `frontend/`, `panogoz/api/app.py`, `docs/08-DEMO-SENARYOSU.md`,
`docs/ekran-goruntuleri/`

---

### K4 · Bildirim, Doğrulama ve Sunum
**Teslimat:** telefonun gerçekten çalması + sistemin doğruluğunun sayıyla savunulması.

- [x] **4.1** Gerçek bildirim kanalı: WhatsApp Business API veya on-prem'e uygun
      alternatif (GSM modem/SMS). Seçim gerekçesi + veri mahremiyeti notu yazılı olsun.
      **TAMAM, tek yönlü (2026-09-20):** seçim gerekçesi + veri mahremiyeti notu yazıldı
      (`docs/12-BILDIRIM-ESKALASYON.md`: üretimde on-prem GSM modem SMS, demoda
      Telegram); iki kanal kodlu ve testli (Telegram sahte-HTTP, GSM modem sahte seri
      port). **GERÇEK Telegram Bot API'ye tek "DEMO-" önekli alarm mesajı gönderildi**
      (`python -m tools.send_real_alarm_demo --send --wait-ack 120`, kullanıcı onayıyla,
      yalnız `TELEGRAM_CHAT_ID` sohbetine; `sendMessage` HTTP 2xx, `[SENT]` kaydı).
      **Doğrulanmayan:** telefonda alındığı betikle ölçülmez; iki yönlü `ONAY` yanıtı
      120 sn içinde gelmedi (alarm açık kaldı) → bu yol yalnız sahte-HTTP testiyle
      doğrulanmış; gerçek GSM modemle hiç denenmedi.
- [x] **4.2** Eskalasyon: rota, onay token'ı, tekrar aralığı, fırtına sınırı, sessize
      alma, nöbet devri. *Bitti sayılır:* gerçek senaryodan uçtan uca testli;
      alarm yaşam döngüsü (aç/yükselt/temizle/onayla/7 gün otomatik kapan/sessize al)
      + kademeli eskalasyon + 4 haneli onay belirteci + fırtına sınırı/özet +
      kişi/tür bazlı sessize alma (KRİTİK bastırılamaz) + nöbet devri + teslimat
      hatasında kademe atlama + Telegram'dan `ONAY <id> <belirteç>` iki yönlü onay.
      → `panogoz/rules/alarms.py`, `panogoz/notify/{escalation,gsm_modem}.py`,
      `tests/test_{alarm_lifecycle,escalation,gsm_modem}.py` (51 test),
      `docs/12-BILDIRIM-ESKALASYON.md` (2026-09-19).
- [x] **4.3** `expect_flags` sözleşme açıkları: STALE, SENSOR_DRIFT, DE_ENERGISED
      bayrakları cihaz düzeyinde doğru mu kuruluyor? *Bitti sayılır:* üç bayrak
      da gerçek testle doğrulandı, θ'nın düşük-yük `None` durumuyla
      karışmadığı ayrıca test edildi, gerçek API endpoint'i (`/api/
      connections/<i>/flags`) canlı çalıştırılıp doğrulandı. Ayrıca CLAUDE.md
      §2'deki CUSUM/değişim-noktası katmanı (`panogoz/detector/cusum.py`,
      K3 3.2'nin arka uç temeli — UI kısmı henüz yapılmadı) sıfırdan kuruldu.
      → `panogoz/detector/{cusum,flags}.py`, `tests/test_cusum.py`,
      `tests/test_expect_flags.py`, `docs/04-ANOMALI-TESPIT.md` (2026-09-16).
- [x] **4.4** Doğruluk sunumu: senaryo × tespit matrisi, haber verme süresi
      dağılımı, yanlış alarm bütçesi, duyarlılık eğrisi. *Bitti sayılır:* gerçek
      koşuyla 22 senaryo (11 arıza + 1 yalnız-uyarı + 10 negatif kontrol) × 10
      tohum = 220 koşu: 110/110 tespit, 18,1 pano-yılında 0 ALARM-üstü yanlış
      alarm (%95 üst sınır 0,17/pano-yılı), sabit eşik kıyası, gürültü/τ
      dayanıklılığı, kör bölge. **Saha doğrulaması DEĞİL — model içi
      öz-tutarlılık** (docs/09 §0). Çok kanallı dedektörler (aşırı yük, nötr,
      yoğuşma/nem, PD, ark) + bastırma→onay→füzyon hattı da bu kapsamda kuruldu.
      → `panogoz/sim/scenarios.py`, `panogoz/detector/{overload,condensation,
      neutral,pd,arc,thermal_tau}.py`, `panogoz/rules/pipeline.py`,
      `panogoz/eval/matrix.py`, `tools/run_accuracy_matrix.py`,
      `docs/09-VERI-ANALIZI.md` (2026-09-19).
- [x] **4.5** Sunum paketi: 15 dk anlatı, slaytlar, demo videosu, jüri Q&A kartları,
      yedek plan. *Bitti sayılır:* zamanlanmış anlatı + gerçek çalışan konsoldan
      kaydedilmiş demo + Q&A kartları + yedek plan. → `sunum/anlati-script.md`,
      `sunum/juri-qa-kartlari.md`, `sunum/yedek-plan.md`, gerçek Chrome kaydından
      üretilen `docs/ekran-goruntuleri/panogoz-demo-walkthrough.gif`, görsel slayt
      artifact'i (linki `sunum/anlati-script.md`'de) (2026-09-16).

**Dosyalar:** `panogoz/notify/`, `panogoz/rules/`,
`panogoz/detector/engine.py` (yalnız bayrak bölümü), `tests/`,
`docs/04-ANOMALI-TESPIT.md`, `sunum/` (yeni)

---

## 6. Önerilen Repo İskeleti

```
grid-up/
├── CLAUDE.md                          ← bu dosya
├── README.md
├── docker-compose.yml
├── Dockerfile
├── firmware/                          (K1)
├── hardware/                          (K1 — KiCad projeleri, dışa aktarımlar)
├── panogoz/
│   ├── bus/                           (K2)
│   ├── store/                         (K2)
│   ├── scada/                         (K2 — Modbus + IEC104)
│   ├── gateway/                       (K2)
│   ├── detector/                      (çekirdek θ/RLS/CUSUM — ortak taban)
│   │   └── engine.py                  (bayrak bölümü: K4)
│   ├── rules/                         (K4)
│   ├── notify/                        (K4)
│   ├── api/
│   │   ├── app.py                     (K3)
│   │   └── runtime.py                 (K2 çalıştırır, K3 arayüz tarafı — ortak)
│   └── contracts/                     (ORTAK — channels.py, live.py, icd.py, envelope)
├── frontend/                          (K3)
├── tests/                             (K4 sahipliğinde, herkes kendi testini ekler)
├── docs/
│   ├── 01-MIMARI.md                   (K2)
│   ├── 02-DONANIM-TASARIMI.md         (K1)
│   ├── 03-ELEKTRONIK-DOKUMANTASYON.md (K1)
│   ├── 04-ANOMALI-TESPIT.md           (K4)
│   ├── 05-SAHA-UYGULAMASI.md          (olası — sıra tahmini)
│   ├── 06-OLCEKLENEBILIRLIK.md        (K2)
│   ├── 07-MALIYET-FAYDA.md            (K1 fiyatları besler)
│   ├── 08-DEMO-SENARYOSU.md           (K3)
│   ├── 09-VERI-ANALIZI.md             (olası)
│   ├── 10-OG-HUCRE-KONSEPTI.md        (olası)
│   ├── 11-ACIK-SORULAR.md             (olası)
│   ├── PANOGOZ-ICD-v2.0.md            (K2)
│   └── ekran-goruntuleri/             (K3)
└── sunum/                             (K4, yeni)
```

> docs/05, 09, 10, 11 numaraları takım dokümanındaki "11 teknik belge" listesinin
> sırasından tahmin edildi — gerçek repoda farklı adlandırılmış olabilir.

---

## 7. Git Akışı

Depo: `https://github.com/hackathon-buke-team/grid-up` (özel). `main` = entegrasyon
dalı, doğrudan push yok. Paket dalları: `k1-donanim-firmware`, `k2-sunucu-entegrasyon`,
`k3-monitoring-ui`, `k4-bildirim-sunum`.

```bash
git clone <depo>
git checkout <kendi dalın>
git fetch origin && git rebase origin/main   # günde en az 1
python -m pytest -q                          # PR'dan önce yeşil olmalı
```

**Değişmez kurallar:** önce kırmızı test, sonra düzelt · yapılmayan hiçbir şey yapılmış
gibi yazılmaz · `contracts/` değişikliği önce gruba duyurulur.

---

## 8. Öncelik Sırası

| Öncelik | Görev | Paket |
| --- | --- | --- |
| P1 | KiCad şematiği + PCB yerleşimi | K1 |
| P1 | Kabin içi mekanik yerleşim görseli | K1 |
| P1 | Gerçek kanaldan tek bildirim mesajı | K4 |
| P1 | Gerçek Mosquitto uçtan uca test | K2 |
| P1 | Demo provası + slayt + video | K4 |
| P2 | IEC 60870-5-104 slave | K2 |
| P2 | STM32 hedef derlemesi | K1 |
| P2 | Mobil/saha görünümü | K3 |
| P2 | 1000 pano yük testi | K2 |
| P2 | Kanıt ekranı güçlendirme | K3 |
| P2 | Doğruluk matrisi + haber verme süresi | K4 |
| P2 | Compose sertleştirme | K2 |
| P3 | expect_flags açıkları | K4 |
| P3 | Ucuz kartla canlı demo | K1 |
| P3 | TimescaleDB sürücüsü | K2 |
| P3 | BOM fiyat tazeleme | K1 |

---

## 9. Hızlı Komutlar

```bash
python -m panogoz.run_local --panels 112 --port 8080
python -m panogoz.run_local --panels 8 --backfill-days 20   # hızlı başlangıç
python -m pytest -q                                          # tüm regresyon (291 test, ~80 sn — 2026-09-20)
python -m pytest tests/test_theta.py                         # tek dosya (pytest ile, `python -m tests.X` DEĞİL)
python -m pytest tests/test_rules.py
python -m pytest tests/test_bus_mqtt_e2e.py -v                # gerçek broker E2E (K2 2.1)
python tools/run_load_test.py --panels 250 500 1000           # K2 2.4 yük testi
```

```bash
# firmware/node (K1 1.4) — toolchain PATH'e ekli değilse önce ekle
# (kurulum: docs/07-FIRMWARE.md §2, xPack + tcc, %LOCALAPPDATA%\panogoz-toolchain\)
cd firmware/node && make host && ./panogoz_node --selftest
make target   # gerçek arm-none-eabi-gcc ile 3 kart, flash/RAM raporu
```

*(Windows'ta Türkçe çıktı için komut başına `PYTHONIOENCODING=utf-8` eklenmeli. Yukarıdaki
`tests.test_rules`/`tests.test_detector`/`tests.test_integration`/`tests.test_scada`
biçimindeki eski komutlar 2026-09-12 sıfırdan-yeniden-yapılanmadan ÖNCEKİ plana
aitti, gerçek değildi — 2026-09-16'da gerçek dosya adları/`pytest` çağrısıyla
düzeltildi, bkz. `docs/06-OLCEKLENEBILIRLIK.md`.)*

---

## 10. Kaynak Doküman

Bu brief, `PANO-GOZ-TAKIM-GOREV-DAGILIMI-v1_1.docx` + yarışma şartnamesi +
`Hackathon Verileri/` klasöründeki datasheet'lerin (HFCT30/50, TVOC-2 Modbus manuel,
MPR-53CS register haritası, 1600 kVA pano çizimi/donanım listesi, TEDAŞ malzeme
şartnamesi) özetidir. Orijinal doküman çok daha fazla detay içeriyor (riskler,
kilometre taşları, geçmiş hata kayıtları, sunumda vurgulanacak cümleler) — gerekirse
oradan bakılabilir.
