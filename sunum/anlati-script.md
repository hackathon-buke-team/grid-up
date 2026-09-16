# K4 · 4.5 Sunum Paketi — 15 Dakikalık Anlatı

> Bu belge K4 iş paketinin **4.5 Sunum paketi** maddesini karşılar: "15 dk anlatı,
> slaytlar, demo videosu, jüri Q&A kartları, yedek plan". Bitti sayılır kriteri:
> gerçekte var olan/doğrulanmış her şeyle birebir örtüşen, zamanlanmış bir anlatı +
> gerçek bir demo kaydı. Kardeş dosyalar: [`juri-qa-kartlari.md`](juri-qa-kartlari.md),
> [`yedek-plan.md`](yedek-plan.md).
>
> **Kural (bu proje boyunca geçerli):** burada "yapıldı" diye geçen her madde gerçekten
> çalıştırılıp doğrulanmış; "planlanan/sırada" diye geçen hiçbir şey "yapıldı" gibi
> sunulmuyor. Jüri karşısında da bu ayrımı koru — abartma, ama gerçek olanı da
> saklama.

## 0. Hazırlık (sunumdan önce)

- **Görsel slayt destesi (9 slayt, gerçek verilerle):**
  https://claude.ai/artifact/K1jkB1boP5dvzKd1KtV7Kt — bu belge o destenin
  konuşma metni/zamanlaması, içerik birebir örtüşüyor.
- `docs/ekran-goruntuleri/panogoz-demo-walkthrough.gif` gerçek, çalışan monitoring
  konsolundan bu oturumda kaydedildi (Chrome otomasyonuyla, gerçek Flask API'ye
  karşı) — sunumda ya bu GIF'i ya da canlı `python -m panogoz.api.app` + tarayıcı
  gösterimini kullan (canlı demo riskini azaltmak için GIF her zaman yedek olarak
  hazır tutulsun, bkz. [`yedek-plan.md`](yedek-plan.md)).
- 3 KiCad PDF'i (`hardware/kicad/*/export/*.pdf`) ve 3D render PNG'leri
  (`hardware/kicad/*/export/*-3d.png`) slayt gösterimine hazır aç.
- Mekanik yerleşim SVG'si (`hardware/mekanik/kabin-ici-yerlesim.svg`).

## 1. Açılış / Problem (0:00 – 1:30)

> "1600 kVA'lık bir TEDAŞ AG panosunda bir arıza olduğunda kimse önceden
> haberdar olmuyor. Cıvatalı bağlantı gevşer, aşırı ısınır, haftalarca kimse
> fark etmez — sonra bir gün arıza büyür, kesinti olur, bazen yangın riski
> doğar. Biz PANO GÖZ ile bu haftalarca süren sessiz ısınma sürecini
> yakalayıp erkenden uyarı vermeye çalışıyoruz."

- Sabit sıcaklık eşiği neden yetmiyor: yaz/kış, yük değişimi aynı sıcaklığı
  hem "normal yaz sıcağı" hem "gerçek arıza" olarak üretebiliyor — sabit eşik
  ya yazın körleşir ya kışın yanlış alarm üretir.
- Çözüm fikri tek cümleyle: **kardeş fazları birbirine göre karşılaştır,
  farkı yüke göre normalize et.**

## 2. θ metriği — ürün fikri (1:30 – 3:30)

Gerçek formül (`panogoz/detector/theta.py`):

```
θ = (T_faz − medyan(T_kardeş_fazlar)) / (I / I_anma)²
```

- Sağlıklı bir bağlantıda üç faz da yükle birlikte ısınır — bu ortak bileşen
  θ'da iptal olur.
- Bozulmuş (gevşek cıvata gibi) bir bağlantının **fazlar-arası fazladan
  ısınması yükten bağımsız bir sabittir** — θ bu sabiti tahmin ediyor.
- Düşük yükte (**< %40 anma akımı**) normalize etme gürültüyü patlatır, bu
  rejimde θ hesaplanmıyor (`None` — "uninformative", alarm üretmiyor).
- Alarm hijyeni: eşikler **15 / 30 / 60** (UYARI/ALARM/KRİTİK), tek örneklik
  gürültü alarm üretmesin diye **3/5 örneklik debounce** (`panogoz/rules/engine.py`).

*(Slayt: healthy vs. faulty θ zaman serisi grafiği — demo konsolundaki gerçek
grafik birebir bu.)*

## 3. Mimari — uçtan uca sistem yaklaşımı (3:30 – 6:00)

> "Jürinin en çok önemsediği kısım burası: tek bir demo scripti değil, uçtan
> uca gerçek bir sistem kurduk."

Akış: **Uç düğüm (TC/IR-PD/Gateway) → MQTT/in-proc bus → SQLite outbox →
θ/kural motoru → [SCADA (Modbus) / bildirim (Telegram) / API (monitoring)]**

Her ok için "gerçek" kanıt bu gece/önceki oturumlarda tek tek doğrulandı —
bkz. §5. Bu bölümde yalnızca şemayı anlat, kanıtları demo bölümünde canlı
göster.

## 4. Canlı demo (6:00 – 10:00)

1. **Monitoring konsolu** (`python -m panogoz.api.app`, tarayıcıda
   `127.0.0.1:8080`, ya da hazır GIF): iki bağlantı — F01-L1 (sağlıklı,
   NORMAL, θ≈-0.3) ve F02-L2 (gevşek cıvatalı, **KRİTİK**, θ≈316). Zaman
   kaydırma çubuğuyla arıza öncesi (θ≈0.9, NORMAL) ile arıza sonrası
   durumu karşılaştır — **aynı fiziksel yük, aynı sıcaklık aralığı, θ
   farkı arızayı yakalıyor.**
2. **Gerçek Telegram bildirimi:** ALARM→KRİTİK geçişinde bot gerçek bir
   mesaj gönderiyor (önceki oturumda gerçek token'la iki kez doğrulandı —
   bkz. `panogoz/notify/telegram_channel.py`). *(Canlı gönderim jüri
   önünde yapılacaksa önce kullanıcıyla teyit edilmeli — bkz.
   [`yedek-plan.md`](yedek-plan.md).)*
3. **Gerçek Modbus register'ı:** `tools/run_modbus_server.py` çalışırken
   gerçek bir Modbus client (`pymodbus`) ile bağlanıp θ/şiddet/akım/sıcaklık
   register'larını (8 register/bağlantı, FC04 salt-okunur) canlı oku —
   register haritası `docs/modbus-haritalama.md`.
4. **Gerçek MQTT broker + reconnect/restart:** bu gecenin işi — istenirse
   `tests/test_bus_mqtt_e2e.py -v` canlı çalıştırılıp 5 senaryonun (bağlanma,
   reconnect, broker restart, outbox replay, duplicate düşürme) hepsinin
   gerçek bir broker process'ine karşı geçtiği gösterilebilir.

## 5. Donanım tasarımı (10:00 – 12:30)

- 3 gerçek KiCad şematiği (TC düğümü ×6/pano, IR/PD düğümü ×1/pano, Gateway
  ×1/pano) — ERC 0 hata, gerçek kurulu kütüphane sembolleri.
- 3 gerçek PCB yerleşimi — DRC **0 kısa devre/clearance/courtyard**, gerçek
  footprint'ler, 3D render (QFN-48 MCU, MAX31855, W5500, HLK-PM01, RJ45/BNC/SMA
  gerçek gövdeleriyle).
- Kabin içi mekanik yerleşim: gerçek TEDAŞ 1600 kVA pano ölçülerine
  (1600×1500×450mm) oturan, mıknatıs kaide + kablo yolu gösteren ölçülendirilmiş
  SVG.
- *(Bilinçli sınır: fiziksel prototip yok — yarışma şartnamesi de istemiyor,
  bkz. CLAUDE.md §1. Kart lehimlenmedi.)*

## 6. Sayılarla doğruluk / dürüstlük (12:30 – 14:00)

> "Şimdi jürinin sormadan önce kendimizin söylemesi gereken kısım."

**Gerçekten doğrulanmış:**
- pytest **26/26** yeşil (21 çekirdek + 5 gerçek broker E2E).
- Gerçek Telegram mesajı, gerçek Modbus round-trip, gerçek MQTT broker
  (bağlanma/reconnect/restart/replay/dedup — hepsi ayrı bir OS process'ine
  karşı).
- 3 kart ERC+DRC temiz, gerçek footprint/gerçek kütüphane.

**Dürüst açık maddeler (uydurmuyoruz):**
- Şu an uçtan uca **tek bir arıza modu** (gevşek cıvatalı bağlantı) tam
  simüle edildi; aşırı yük/yoğuşma/nötr harmonik/ark için model tasarımı
  CLAUDE.md'de var ama sentetik senaryo + 17-senaryo doğruluk matrisi (K4 4.4)
  henüz kurulmadı — sıradaki adım.
- `panogoz/bus`/`panogoz/store` bu gece kuruldu ve gerçek broker'a karşı
  kanıtlandı, ama henüz üretim pipeline'ına (sim→detector→rules→api)
  bağlanmadı.
- Bu geliştirme ortamında gerçek Eclipse Mosquitto ikili dosyası
  çalıştırılamadı (Windows UAC kısıtı, iki gerçek denemeyle kanıtlandı) —
  yerine gerçek MQTT 3.1.1 protokolü konuşan `amqtt` kullanıldı, kod
  değişmeden gerçek Mosquitto'ya geçilebilir.
- IEC 60870-5-104, mTLS/ACL sertleştirme, 1000 pano yük testi, STM32 hedef
  derlemesi — henüz yapılmadı (CLAUDE.md §8 P2/P3).

## 7. Kapanış (14:00 – 15:00)

> "PANO GÖZ'ün iddiası büyük bir demo değil — gerçek entegrasyonların uçtan
> uca birbirine bağlı olması. Her ok gerçek bir protokolle, gerçek bir
> dış sistemle test edildi. Sıradaki adım aynı disiplinle diğer 4 arıza
> modunu ve ölçek testlerini eklemek. Sorularınızı bekliyorum."

*(Q&A için bkz. [`juri-qa-kartlari.md`](juri-qa-kartlari.md).)*
