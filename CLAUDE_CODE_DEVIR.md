> **K1 B1 / 20.09.2026:** K1 alanında gerçek KiCad/STEP ve STM32WLE5 TC hedef derlemesi eklendi; giriş `hardware/README.md`. Aşağıdaki geçmiş enerji sonuçları B1 için güncel değildir: görev karması artık 58,92 µA / 721 gün varsayımıdır. contracts ve K2/K3/K4 uygulama kodu değişmedi. Gerçek kart/RF testi, IR/PD/GW hedef sürücüleri ve eksiksiz tedarik fiyatı açık kalır.

# Claude Code devir notu

Tarih: 11 Eylül 2026
Proje: `grid-up-v2 / PANO GÖZ`
Amaç: Kod incelemesinde bulunan gerçek hataları düzeltmek ve README/docs iddialarını
çalışan kodla uyumlu hâle getirmek.

Bu not iki turu birlikte içerir. **Tur 1** Codex tarafından yapıldı (alarm seviyesi,
yük ölçeği, MQTT taşıma). **Tur 2** Claude Code tarafından yapıldı ve Codex'in bıraktığı
sırayı takip etti. Projede `.git` deposu yoktur; commit akışı uygulanmadı. Tur 1 öncesi
kaynak yedeği: `C:\Users\darkb\AppData\Local\Temp\panogoz-before-fixes-wxppxtwv\source.zip`

---

## Tur 1 (Codex) — tamamlanan işler

### 1. Alarm seviyesi tekilleştirildi

`panogoz/contracts/live.py`, `panogoz/detector/engine.py`, `panogoz/rules/fusion.py`,
`tests/test_alarm_load_regression.py`

`JointView.severity` için `None`, "dedektör henüz karar vermedi" anlamına gelen açık
sentineldir. Füzyon geçerli bir dedektör kararını anlık `theta_k` ile tekrar yükseltmez;
anlık theta fallback'i yalnız karar yoksa çalışır. Mutlak sıcaklık ve aktif ark açması
güvenlik override'ları korunur.

### 2. Bara yükü ve fider yükü ayrıldı

`PanelLive.load_factor` üç faz ortalaması / 2312 A ana bara anmasıdır.
`PanelLive.feeder_load_factor` ayrı nullable alandır ve 3250 A toplam fider anması
ölçeğindedir. SCADA ve arayüzdeki `LOAD_FACTOR` ana bara oranıdır.

### 3. MQTT bağlantı ve güvenilir aktarım

`panogoz/bus/bus.py`, `panogoz/gateway/gateway.py`, `panogoz/store/db.py`,
`panogoz/store/schema.sql`, `panogoz/api/runtime.py`, `tests/test_transport_regression.py`

Paho 2.x `ReasonCode` işleniyor; QoS 1 için `PublishReceipt`; PUBACK gelmeden mesaj
tamamlanmış sayılmıyor; `gateway_outbox` tablosu ile yeniden başlatmada onaysız mesajlar
geri yükleniyor; outbox dolunca `BufferError`; SQLite dışı DSN açıkça reddediliyor.

---

## Tur 2 (Claude Code) — tamamlanan işler

Her madde için önce gerçek davranışı gösteren **kırmızı** bir regresyon testi yazıldı,
sonra düzeltme yapıldı.

### 1. Tekrarlanan ve eski zarflar canlı durumu geri almıyor

`panogoz/contracts/envelope.py`, `panogoz/detector/engine.py`,
**yeni** `tests/test_stream_regression.py` (7 test)

`SeqTracker.check()` artık:

- `data` ve `event` dışındaki kinds için `"unsequenced"` döner ve su damgasına dokunmaz.
  Önceden `birth`/`death` (ikisi de `seq=0`) su damgasını akış ortasında sıfırlayabiliyordu.
- Su damgasını **yalnız ileri** taşır. Tekrar gelen zarf `duplicate` raporlanır ve
  takipçiyi bulduğu gibi bırakır; böylece bir sonraki gerçek mesaj hayalet boşluk
  saymıyor (eskiden 1 → 2 → 1 → 3 dizisi `gap:1` üretiyordu).
- `duplicates` sayacı tutar; `DetectorEngine.stats()` ve `/api/health` bunu gösterir.

`DetectorEngine.observe()` artık `is_stale()` sonucuna uyar ve tekrarlanan zarfı düşürür.
Kırmızıda üretilen hata: sıra 1 → 100 A, sıra 2 → 200 A, sıra 1 tekrarı → canlı değer
100 A'ya geri dönüyordu; RLS aynı fiziksel örneği iki kez yiyordu; cihaz `last_seen`
geriye gidiyordu.

### 2. Yayın kadansı cihaz sözleşmesine bağlandı

`panogoz/contracts/channels.py`, `panogoz/contracts/live.py`,
`panogoz/detector/engine.py`, `panogoz/gateway/gateway.py`, `panogoz/api/runtime.py`,
`docs/04-ANOMALI-TESPIT.md` §10.1, **yeni** `tests/test_cadence_regression.py` (12 test)

Yeni kanal `dev.period_s`: düğümün bir sonraki yayına kadar geçmesini beklediği süre.
Her veri zarfında ve birth olayında taşınır. `channels.CADENCE_PERIOD_S` firmware
tablosunu aynalar (IDLE 900 / WATCH 60 / BURST 10) ve test ikisinin ayrışmasında düşer.

Sunucuda tek sabit eşik yerine üç ayrı pencere:

| Soru | Pencere | Taban |
|---|---|---|
| Cihaz konuşuyor mu | `DEVICE_MISS_BUDGET`(3) × kendi periyodu | `DEVICE_OFFLINE_S` 180 s |
| Analizör taze mi | 3 × **ağ geçidinin** periyodu | `ANALYSER_OFFLINE_S` 180 s |
| İki kardeş çıkarılabilir mi | `PEER_PERIOD_BUDGET`(2) × panodaki en uzun periyot | `peer_max_age_s` 300 s |

Periyot ilan etmeyen kaynak eski sabit eşikleri aynen alır: **geniş pencere ilan
ederek kazanılır, varsayılmaz.** `Gateway.set_period()` ile kadans bildirilir; `Runtime`
backfill'de burst aralığını, canlı döngüde `SIM_PERIOD_S`'i ilan eder.

Firmware **değiştirilmedi**; kadans zaten `pg_frame_t.cadence` alanında taşınıyordu,
eksik olan sunucu tarafıydı. Pil ömrü bu yüzden değişmedi ve firmware'in kendi hesabıyla
doğrulandı: `--scenario energy` → görev karması %97/2.5/0.5 ile ortalama 8.89 µA,
4781 gün = **13.1 yıl**.

Dürüstçe yazılan bedel (docs/04 §10.1): IDLE kadansında iki kardeş okuma 900 s arayla
alınabilir ve pabucun ısıl zaman sabiti de ~900 s'dir; θ yük normalize olduğu için yavaş
yük değişimi bölünür, fakat ortak-mod sadeleşmesi BURST kadansındaki kadar güçlü değildir.

### 3. Negatif senaryolar gerçek boru hattından geçiriliyor

**yeni** `tests/test_negative_pipeline.py` (10 test), `tests/test_integration.py`

Eski test yalnız `SCENARIOS` sözlüğünde `expect_alarm=False` yazdığını doğruluyordu;
dedektörü kapalı bir sürümde de geçerdi. Yeni test yedi negatif kontrolün **her birini**
gerçek zincirden geçiriyor: simülatör → ağ geçidi → dedektör → suppression → fusion →
alarm yöneticisi, 40 günlük backfill ile.

İki şey testin anlamını veriyor:

- **Pozitif kontrol aynı koşumda**: `gevsek_baglanti` aynı ayarlarla `KRITIK`
  `loose_connection` alarmı açıyor. Onsuz "alarm yok" ile "dedektör yok" ayırt edilemezdi.
- **Her senaryo değerlendirme anında hâlâ çalışıyor** (`ACTIVE_AGO_DAYS`). Dün biten bir
  sıcak hava dalgası, sıcak hava dalgasında ne olduğu hakkında hiçbir şey kanıtlamaz.

Testin gerçekten iş gördüğü kanıtlandı: `fusion.joint_severity` geçici olarak sabotajlanıp
her zaman `BILGI` döndürüldüğünde pozitif kontrol ve eşzamanlılık testi düştü, sonra
sabotaj geri alındı ve dosya yedekle bit bazında karşılaştırıldı.

Karşı senaryo eklendi: **gerçek gevşek bağlantı + eşzamanlı şebeke olayı** → gevşek
bağlantı alarmı hâlâ açılıyor. `test_integration.py` içindeki eski kontrol artık
kapsamayı doğruluyor (sözleşmeye eklenip hiç sürülmeyen negatif kontrol yakalanır).

### 4. THD kaynağı "şebeke olayı adayı" olarak sınıflandırılıyor

`panogoz/rules/suppression.py`, `panogoz/rules/alarms.py` (dolaylı),
`docs/04-ANOMALI-TESPIT.md`, `docs/08-DEMO-SENARYOSU.md`, `tests/test_rules.py`,
**yeni** `tests/test_thd_attribution_regression.py` (7 test)

Sorun: üç faz gerilim THD artışı kesin şebeke olayı sayılıyor, `IN_PANEL_MODES`'un
tamamına `GRID_LLR = -1.5` itiliyor ve `GRID_DISTURBANCE` bayrağı **ekip yönlendirmesini
tamamen vetoluyordu** (`alarms.NO_DISPATCH_FLAGS`). Oysa panonun beslediği taraftaki büyük
bir sürücü, UPS ya da redresör de üç faza harmonik akım basar ve gerilim bozunumu ortak
yukarı akış empedansında oluşur; analizör ikisini ayırt edemez.

Yeni davranış:

- `THD_ATTRIBUTABLE_MODES` (`harmonic_neutral`, `insulation`) — kanıtı harmoniğin kendisi
  olan modlar, tam `GRID_LLR` almaya devam eder, kod `GRID_THD_3PH`.
- `THD_CANDIDATE_MODES` (`loose_connection`, `overload`, `thermal_runaway`) — yalnız
  `GRID_CANDIDATE_LLR = -0.5` alır, kod `GRID_THD_3PH_CANDIDATE`, gerekçe metni "ADAYIDIR"
  ve "EK KANIT gerekir" der, ekip kararı vermez.
- Bayrak `GRID_DISTURBANCE_CANDIDATE` kurulur; **`GRID_DISTURBANCE` kurulmaz**, dolayısıyla
  ekip vetosu konmaz.
- Teyit geldiğinde (frekans penceresi dışı ya da inrush sınıflandırması) aday
  `GRID_DISTURBANCE`'a yükselir ve veto o zaman devreye girer.

`tests/test_rules.py` bölüm 3 bu yeni sözleşmeye göre yeniden yazıldı (40/40).

### 5. Bulunan ve düzeltilen ek hata: geçmişten debounce penceresi kurulamıyordu

`panogoz/api/runtime.py`, `tests/test_alarm_load_regression.py`

Tur 1 tamamlandıktan sonra `tests/test_integration.py` uçtan uca testi düşüyordu
("kritik bağlantı için olay açılmadı"). Kök neden Tur 2'nin değişikliği değildi
(`duplicates = 0` ölçüldü), Tur 1'in füzyon değişikliğinin yan etkisiydi:

`prime_alarm_debounce()` saklanan günlük medyanları yeniden oynatırken sentetik bir
`JointView` kuruyor ve ona `severity="BILGI"` yazıyordu. Yeni sözleşmede açık `BILGI`
"dedektör karar verdi" demektir, dolayısıyla füzyon anlık theta fallback'ini çalıştırmıyor,
her gün `BILGI` çıkıyor, hiçbir pencere yazılmıyor ve altmış günlük kanıtı kendi veri
tabanında duran bir pano hiçbir zaman olay açamıyordu. Sentinel `None` olarak düzeltildi.

### 6. README, docs ve Compose gerçek duruma çekildi

| Dosya | Ne düzeltildi |
|---|---|
| `panogoz/store/db.py` | "İki sürücü" iddiası kaldırıldı; **tek sürücü SQLite**, Timescale yolunun neyi olmadığı tek tek sayıldı |
| `panogoz/store/schema.sql` | `schema_timescale.sql` diye bir dosya olmadığı yazıldı; **20 → 200 nokta/s** düzeltildi |
| `docker-compose.yml` | Başlık "INTENDED"; "WHAT THIS FILE IS NOT" bloğu: çalışan dinleyici anonim düz MQTT, mTLS/ACL yorum satırında, host portları doğrudan yayında, `db` servisine hiçbir şey bağlanmıyor. Veri hacmi 200 nokta/s ve ~18 GB olarak docs/01 ve docs/06 ile tekleştirildi |
| `README.md` §2, §9 | Timescale sürücüsünün olmadığı; Compose'un sertleştirme olmadığı |
| `README.md` §1 | "Geçmiş gerektirmez" yalnız kardeş karşılaştırmasıyla sınırlandı; drift/CUSUM yolunun `joint_daily` gerektirdiği yazıldı |
| `README.md` §6 | "Sahtedir ve ispatı elimizdedir" → "sentetiktir, bu yüzden saha başarısı bununla ölçülemez". Eksikler (sıcaklık/nem yok, etiketli arıza geçmişi yok, kardeş yapısı yok, anomali yok) ve "bu pakette saha verisiyle doğrulanmış hiçbir başarım sayısı yoktur" cümlesi eklendi |
| `README.md` §5 | Gerileme takımı tablosu eklendi |
| `docs/01` §3, §5, kapanış | Timescale hedef olarak işaretlendi; "yazılmadı" satırları |
| `docs/06` §2.3, §2.4 | Timescale rakamlarının kestirim olduğu açıkça yazıldı |
| `docs/09` §0 | "Bu dosyayla ölçülemeyecek olanlar" tablosu |
| `docs/11` D6 | "Sürücü yazılmadı" |
| `docs/04` §10, §10.1 | THD aday sınıflandırması; kadans sözleşmesi ve tazelik pencereleri |
| `docs/08` | Şebeke olayı beat'i aday sınıflandırmasına göre yeniden yazıldı |

---

## Tur 3 (K4 · bildirim) — üç gerçek kanal, tek merdiven

Tarih: 20 Eylül 2026 · Dal: `k4-bildirim-sunum` · Ayrıntı: [docs/12](docs/12-BILDIRIM-KANALLARI.md)

**Ne eklendi.** Şartname madde 7'nin gerçek karşılığı: SMS + Telegram + saha uygulaması,
aynı eskalasyon merdiveninde. Her kanal ayrı `notification` satırı ve ayrı gönderim hattıdır;
bir kanaldan onay hepsinde tekrarı durdurur ve her Telegram kopyasının düğmesini kaldırır.

| Yeni | Dosya |
|---|---|
| Telegram taşıması (yalnız `urllib`, token sızmaz, çıkış yönlü uzun yoklama, `minimal` gizlilik) | `panogoz/notify/telegram.py` |
| Gerçek GSM modem (PDU/UCS2, birleşik SMS, port kilidi, önbellekli durum) | `panogoz/notify/gsm_serial.py` |
| Saha uygulaması sunucusu (`/api/saha`, `/api/notify`, `/saha/`) | `panogoz/notify/saha.py` |
| Yapılandırma ve fabrika (sırlar dosyada/ortamda; gerçek kanal yalnız başlatıcıdan) | `panogoz/notify/config.py`, `factory.py`, `notify.example.json` |
| Saha uygulaması (PWA, sıfır bağımlılık) | `saha/` |
| Merdiven: `TELEGRAM` + `MOBIL` kanalları, asenkron gönderim, çok kanallı onay, `/start` `/durum` | `panogoz/notify/escalation.py` |
| Testler (+117) | `tests/test_notify_*.py`, `test_gsm_serial.py`, `test_saha_api.py`, `fake_telegram.py` |

**Yolda bulunan ve düzeltilen gerçek hatalar** (her biri önce kırmızı testle):

| Hata | Sonucu | Şimdi |
|---|---|---|
| `Notifier._send_one` `compose(incident)`'i `live` vermeden çağırıyordu | Son commit'in "eşiğe kalan gün" satırı testlerde vardı, **gerçek SMS'te asla** | `live` merdivenden geçiyor |
| `ark_olayi` varsayılanı `at_s=3600`; konsol düğmesi yalnız `{panel_key}` gönderiyor | Düğmeye basınca ark **1 saat sonra** oluyordu; docs/08 §5 sunumcuya 4–13 s gecikmeyi anlatmasını söylüyor | `api/app.py` `LIVE_DEMO_AT_S`: gecikme verilmemişse 3 s |
| `requirements.txt`'te `pytest` yoktu | `python -m pytest -q` (README'deki komut) temiz kurulumda çalışmıyordu | Eklendi |

**Bulundu, DÜZELTİLMEDİ (karar takımın).** Canlı demoda ark dışındaki senaryolar telefonu
çaldırmaz: KRİTİK, `alarms._maybe_dispatch`'in 24 saatlik bekleme + iki bağımsız ölçüm ailesi
kapılarından geçer (ACİL muaf). Ölçülen gerekçe: *"Tek kanal teyidi (TC)"* ve *"24 saat bekleme
süresi dolmadı"*. Güvenlik özelliği olduğu için gevşetilmedi; ayrıntı ve sunum önerisi docs/12 §6.1.

**Başkasının dosyasına dokunulan yerler** (K3'e/K2'ye haber verilecek; hepsi küçük ve yorumlu):
`panogoz/api/app.py` (+`saha.install(app, rt)`, +`LIVE_DEMO_AT_S`), `panogoz/api/runtime.py`
(notifier'ı fabrikadan kurar; `stop()` bildirim hatlarını kapatır), `panogoz/run_local.py`
(`PANOGOZ_NOTIFY_LIVE=1`, açılış özeti), `baslat.ps1` (`-Telefon`), `requirements.txt`, `.gitignore`.
`frontend/`, `panogoz/contracts/`, `store/schema.sql` **değişmedi**; iş emri durumu şema
değişikliği olmadan `audit` zincirine yazılır.

**Doğrulandı.** `python -m pytest -q` → **285 geçti, 4 düştü** (172 taban + 117 yeni = 289; bir önceki tam koşumda 6 düşmüştü, yani düşen sayı koşumdan koşuma değişiyor). Düşen
testler `tests/test_negative_pipeline.py::test_negative_control_opens_no_incident_or_horizon[*]`'tir ve
**bu turun değişikliğinden bağımsızdır**: değişmemiş `origin/main`'in izole bir kopyasında (git
worktree) aynı testler aynı biçimde düştü ve aynı gün iki tam koşumda (14:5x, 15:5x) geçmişti.
Sağlıklı bir pabuç için ufuk özelliği, testin sözleşmesinin (90 günlük tavanın **altında** gün
yok) tersine 68–87 günlük bir "IZLE'ye kalan gün" üretiyor; sonuç saate göre değişiyor gibi
görünüyor (kök neden **araştırılmadı**, test gevşetilmedi). Bu, görev 4.4'ün "yanlış alarm
bütçesi" konusudur ve `main`'in bazı saatlerde yeşil olmadığı anlamına gelir. Bilerek sabotajla
(`_after_ack` devre dışı) uçtan uca ve merdiven testleri beklenen yerde düştü, dosya bit bit
geri yüklendi. Gerçek `Runtime` + sahte Bot API + Chrome'da (400 px çerçeve) elle: ark senaryosu →
iki kişiye Telegram → tam ekran alarm → uygulamadan onay → iki Telegram mesajı "Onaylandı" oldu →
iş emri adımları → zaman çizgisi; 400 px'te yatay kaydırma yok.

**Doğrulanmadı.** Gerçek Telegram botu (anahtar yok), gerçek GSM modem, gerçek Android/iOS
telefonda uygulama (siren/titreşim/bildirim/ekran kilidi), HTTPS altında service worker
bildirimi. Ayrıntı: docs/12 §9.

**Açık (görev 4.2).** "Sessize alma" ve "nöbet devri" yok; `/sessiz`, `/devral` komutları ve
rota değişikliği eklenmedi.

---

## Doğrulama sonuçları (Tur 2 sonunda, hepsi bu turda koşturuldu)

```text
python -m pytest -q                     138 passed
python -m tests.test_rules              40/40 kontrol geçti
python -m tests.test_detector           all detector claims verified
python -m tests.test_scada              30 passed, 0 failed
python -m tests.test_modbus             8/8 passed
python -m tests.test_prpd               ALL CHECKS PASSED
python -m tests.test_sim_acceptance     52/52 passed
python -m tests.test_integration        geçti 17 · kaldı 0 · atlandı 0

firmware/node: gcc -std=c99 -Wall -Wextra -Werror -O2 -Wdouble-promotion -DPG_HOST=1
  → uyarı yok;  ./panogoz_node --selftest → ozet: 0 hata
  → ./panogoz_node --scenario energy → görev karması 8.89 µA, 13.1 yıl

API smoke (run_local --panels 8 --backfill-days 20):
  /api/health           ok, degraded=[]
  /api/panel/SOKE-14    sev=UYARI HI=79.9 theta_max=31.03 K (C07-L2-PABUC)
                        load_factor=0.6517 (bara) feeder_load_factor=0.4636
                        TC-01 online=True period_s=2.0
                        alarm: ACIL loose_connection
  detector stats        observed=4284 rejected=0 seq_gaps=0 duplicates=0 reboots=0
  Modbus TCP FC03       hata yok
```

---

## Kalan işler

### 1. Gerçek Mosquitto ile entegrasyon testi — YAPILMADI

Makinede Mosquitto kurulu değil (`which mosquitto` boş). `tests/test_transport_regression.py`
Paho publish/ACK sınırını kontrollü test eder, gerçek broker'ı değil. Yapılması gerekenler:
bağlantı, yeniden bağlanma, broker restart sırasında outbox, süreç restart sonrası replay,
ve **replay'in artık duplicate olarak düşürüldüğünün** gerçek broker üzerinde doğrulanması.

### 2. Senaryo `expect_flags` sözleşmesi tutmuyor — BULUNDU, DÜZELTİLMEDİ

Negatif senaryoları gerçek boru hattından geçirirken çıktı. `panogoz/sim/faults.py`
şu bayrakları vaat ediyor, boru hattı üretmiyor:

| Senaryo | Beklenen | Gerçekte çıkan | Neden |
|---|---|---|---|
| `sensor_takildi` | `STALE` | (yok) | `STALE` pano düzeyinde `data_age_s > STALE_AFTER_S`'tir; donmuş **tek bir kelepçe** panoyu bayat yapmaz |
| `sensor_kaydi` | `SENSOR_DRIFT` | (yok) | `icd.STATUS_BITS` içinde `SENSOR_DRIFT` diye bir bit **yok**; en yakınları `MOUNT_LOST` ve `AIM_SHIFTED` |
| `dugum_sessiz` | `STALE` | `DEVICE_FAULT`, `SUPPRESSED` | Suppression cihaz çevrimdışı gerekçesini doğru yazıyor, fakat ilan edilen bayrak bu değil |
| `pano_enerjisiz` | `DE_ENERGISED` | `ANALYSER_COMMS_LOST` | `DE_ENERGISED`, `analyser_online` şartına bağlı. Pano enerjisizken MPR-63 de beslemesini kaybedip susuyor, dolayısıyla şart hiç sağlanmıyor |

Son satır **bilerek düzeltilmedi**: pano enerjisiz ile RS-485 kablosu kopmuş arasındaki
farkı bu sistem ölçemez ve veri yokken `DE_ENERGISED` iddia etmek, kod tabanının her yerde
karşı çıktığı türden bir sahtelik olurdu. Karar verilmesi gereken: ya `expect_flags`
sözleşmesi gerçeğe çekilecek, ya cihaz düzeyinde ayrı bayraklar (`DEVICE_STALE`) eklenecek,
ya da `DE_ENERGISED` için ikinci bir kanıt kanalı (örneğin ark rölesinin de susması)
tanımlanacak. Kapsam genişletmemek için bu turda yalnız raporlandı.

### 3. Ölçülmemiş ve doğrulanmamış kalanlar

Gerçek sensör donanımı, STM32 hedef derlemesi, TimescaleDB (sürücü yok), gerçek
SMS/WhatsApp gönderimi, saha EMC ve elektrik güvenliği. Hiçbiri bu çalışmada doğrulanmış
sayılmamalıdır.

---

## Değişen dosyalar (Tur 2)

```
panogoz/contracts/envelope.py      SeqTracker: unsequenced kinds, ileri-yönlü su damgası,
                                   duplicates sayacı, is_stale()
panogoz/contracts/channels.py      dev.period_s kanalı, CADENCE_PERIOD_S, CADENCE_BY_CODE
panogoz/contracts/live.py          DeviceView.period_s
panogoz/detector/engine.py         is_stale ile duplicate düşürme; DEVICE_MISS_BUDGET,
                                   PEER_PERIOD_BUDGET, ANALYSER_DEVICE; _device_period,
                                   _online_window, _analyser_window, _peer_window;
                                   stats()["duplicates"]
panogoz/gateway/gateway.py         period_s parametresi, set_period(), her data zarfında
                                   ve birth olayında dev.period_s, NODE_HEALTH güncellendi
panogoz/api/runtime.py             _burst ve _sim_pass kadansı ilan ediyor;
                                   prime_alarm_debounce sentinel None
panogoz/rules/suppression.py       GRID_CANDIDATE_LLR, THD_ATTRIBUTABLE_MODES,
                                   THD_CANDIDATE_MODES, GRID_THD_3PH_CANDIDATE gerekçesi,
                                   aday → kesin yükseltmesi
panogoz/store/db.py                modül docstring'i gerçeğe çekildi
panogoz/store/schema.sql           başlık düzeltildi, 20 → 200 nokta/s

tests/test_stream_regression.py            YENİ  (7)
tests/test_cadence_regression.py           YENİ  (12)
tests/test_negative_pipeline.py            YENİ  (10)
tests/test_thd_attribution_regression.py   YENİ  (7)
tests/test_alarm_load_regression.py        +1 (debounce priming)
tests/test_rules.py                        bölüm 3 yeniden yazıldı
tests/test_integration.py                  negatif kontrol kapsama bağlantısı

README.md, docker-compose.yml, docs/01, docs/04, docs/06, docs/08, docs/09, docs/11
```

Devam eden kişi bu notu temel almalı; değiştirilmiş dosyaları geri almamalı ve kalan her
iş için önce gerçek davranışı gösteren regresyon testi yazmalıdır.
