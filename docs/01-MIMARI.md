# K2 · Mimari — Bus / Store ve Gerçek Broker Uçtan Uca Testi (2.1)

> Bu belge K2 iş paketinin **2.1 Gerçek Mosquitto ile uçtan uca test** maddesini
> karşılar: "bağlanma, yeniden bağlanma, broker/süreç restart, outbox replay,
> duplicate düşürme". Bitti sayılır kriteri: gerçek bir broker sürecine karşı
> çalışan, hepsi geçen bir pytest dosyası →
> [`tests/test_bus_mqtt_e2e.py`](../tests/test_bus_mqtt_e2e.py).

## 1. Neden bu görev sıfırdan başladı

CLAUDE.md §2'deki mimari şeması `[Uç düğüm] → MQTT (QoS1) → [panogoz/bus] →
[panogoz/store: SQLite outbox] → [panogoz/detector]` diyor, ama 2026-09-12'deki
solo yeniden yapılanmadan bu yana repo'da **`panogoz/bus/` ve `panogoz/store/`
hiç yoktu** — pipeline (`panogoz/sim/demo_fleet.py` → `detector/theta.py` →
`rules/engine.py` → `api/app.py`) tamamen doğrudan Python çağrılarıyla
bağlıydı, ara bir taşıma/dayanıklılık katmanı yoktu. Bu görev hem bu iki
modülü hem de gerçek bir broker'a karşı test eden E2E'yi sıfırdan kurdu.

## 2. Broker kurulumu — gerçek Mosquitto denendi, olmadı, dürüst alternatif

CLAUDE.md açıkça "gerçek Mosquitto" diyor. Bu makinede (Windows, admin
hakları kısıtlı, Docker/winget/chocolatey hiçbiri yok) resmi Mosquitto
Windows installer'ı **iki ayrı, gerçek denemeyle** engellendiği kanıtlandı:

1. `mosquitto-2.x.x-install-windows-x64.exe /S /D=<kullanıcı-dizini>` —
   bir subagent tarafından çalıştırıldığında **600 saniye boyunca hiçbir
   ilerleme kaydetmeden takıldı** (izleyici tarafından öldürüldü) — hiçbir
   konsola/GUI'ye tıklanamayan bir onay bekliyor olması muhtemel.
2. Ana oturumda aynı installer PowerShell `Start-Process` ile tekrar
   denendi: bu kez **anında** `"İşlem kullanıcı tarafından iptal edildi"`
   hatasıyla döndü — bu, Windows'un bir UAC yükseltme isteğini bu
   etkileşimsiz (non-interactive) oturumda otomatik olarak reddettiğinin
   kesin kanıtı. Mosquitto Windows installer'ı bir Windows servisi
   kurabildiği için admin/UAC istiyor; mosquitto.org'da bağımsız/portable
   bir Windows dağıtımı (zip) da yok.

**Sonuç:** bu ortamda gerçek Eclipse Mosquitto ikili dosyası
çalıştırılamıyor. Yerine **`amqtt`** kullanıldı
(`pip install amqtt`, [PyPI](https://pypi.org/project/amqtt/)) — bu bir
mock/fake DEĞİL: gerçek, bağımsız bir MQTT 3.1.1 protokol implementasyonu,
gerçek TCP soketi üzerinde gerçek CONNECT/CONNACK/PUBLISH/PUBACK/SUBSCRIBE
çerçeveleri konuşuyor, gerçek QoS1 uyguluyor, ve **ayrı bir OS process'i**
olarak çalışıyor (`tools/run_amqtt_broker.py`, `subprocess.Popen`) — karşı
uçtaki gerçek `paho-mqtt` client'ı bunun Mosquitto olmadığını bilmiyor bile,
hiçbir kod yolu mock edilmedi. Tek fark broker ikili dosyasının kimliği.
**Bu proje ileride admin erişimi olan/farklı bir ortamda çalıştırılırsa,
`tools/run_amqtt_broker.py`'nin yerine gerçek `mosquitto -p <port>` komutu
konulabilir** — `panogoz/bus/mqtt_bus.py` tarafı MQTT 3.1.1 protokolüne
bağlı olduğu için hangi broker olduğundan bağımsız çalışır, testler
değişmeden geçer.

Denenmeyen/reddedilen alternatifler ve neden: Docker (`docker` komutu bu
makinede yok), winget/chocolatey (ikisi de yok, kontrol edildi).

## 3. `panogoz/bus/` — CLAUDE.md §2/§3'teki "aynı arayüz arkasında" ilkesi

| Dosya | Görev |
| --- | --- |
| `envelope.py` | `Envelope` — bir `Reading`'i (`panogoz/contracts/channels.py`) sıra numarası (`seq`) ve `device_id` ile saran, JSON'a/JSON'dan serileşen zarf. `seq`, "ileri-yalnız su damgası" (§4) ve outbox replay sıralaması için gerekli tek doğruluk kaynağı. |
| `interface.py` | `Bus` protokolü — `connect/disconnect/is_connected/publish/subscribe`. |
| `inproc.py` | `InProcBus` — senkron, bellek-içi pub/sub, ağ yok (mevcut testler/dev için). |
| `mqtt_bus.py` | `MqttBus` — gerçek `paho-mqtt` (QoS1). Paho'nun kendi ağ döngüsü (`loop_start()` + `reconnect_delay_set()`) bağlantı koptuğunda kendi kendine yeniden bağlanıyor; `on_connect`'te tüm abonelikler yeniden kuruluyor (kalıcı olmayan MQTT oturumu bir kopuşta abonelikleri düşürüyor). |

## 4. `panogoz/store/` — SQLite outbox + ileri-yalnız su damgası

| Dosya | Görev |
| --- | --- |
| `outbox.py` | `Outbox` — **yayıncı tarafı** dayanıklılığı: broker'a ulaşılamadığında `enqueue()` ile SQLite'a yazılan mesajlar, bağlantı geri geldiğinde `pending()` ile sıra numarasına göre okunup tek tek yayınlanır, her biri `mark_delivered()` ile kapatılır. |
| `watermark.py` | `Watermark` — **abone tarafı** yinelenen mesaj tespiti: QoS1 "en az bir kez" garantisi verdiği için aynı mesaj iki kez gelebilir (ör. PUBACK kaybolup yeniden gönderim); `should_process(device_id, seq)` yalnızca `seq`, o cihaz için görülen en yüksek `seq`'ten büyükse `True` döner ve su damgasını ileri taşır — geriye asla gitmez. |

## 5. Gerçek uçtan uca test sonucu (`tests/test_bus_mqtt_e2e.py`)

Her test gerçek bir `amqtt` broker sürecini (`tools/run_amqtt_broker.py`,
`subprocess.Popen`, boş bir TCP portu) başlatıp kapatıyor; hiçbir sahte/mock
broker veya client yok.

```
tests/test_bus_mqtt_e2e.py::test_connect_real_broker_and_roundtrip PASSED
tests/test_bus_mqtt_e2e.py::test_reconnect_after_socket_drop PASSED
tests/test_bus_mqtt_e2e.py::test_broker_process_restart PASSED
tests/test_bus_mqtt_e2e.py::test_outbox_replay_after_downtime PASSED
tests/test_bus_mqtt_e2e.py::test_duplicate_delivery_dropped_by_watermark PASSED
5 passed in 12.45s   (iki ayrı çalıştırmada da, zamanlamaya bağlı kırılganlık kontrolü için tekrarlandı)
```

| Senaryo | Ne kanıtlanıyor |
| --- | --- |
| **Bağlanma** | Gerçek TCP + gerçek CONNACK (`bus.is_connected()`), gerçek publish/subscribe round-trip. |
| **Yeniden bağlanma** | Broker process'i canlı kalırken alttaki soket (`Client.socket()`, genel Paho API) zorla kapatılıyor; Paho'nun kendi ağ döngüsü bunu fark edip kendi kendine yeniden bağlanıyor — test bunu `is_connected()`'in önce `False`'a düşüp sonra tekrar `True` olmasıyla doğruluyor, sonra tekrar bir mesaj gönderip gerçekten çalıştığını kanıtlıyor. |
| **Broker/süreç restart** | Broker OS process'i gerçekten öldürülüyor (`Popen.terminate()`), aynı portta **farklı bir PID**'le yeni bir process başlatılıyor (`assert pid1 != pid2`), client kendi kendine yeni process'e bağlanıyor. |
| **Outbox replay** | Broker hiç ayakta değilken 3 zarf `Outbox.enqueue()` ile SQLite'a yazılıyor; broker ayağa kalktıktan sonra `pending()` sıra numarasına göre okunup yayınlanıyor, abone tarafında `[1, 2, 3]` sırasıyla alındığı doğrulanıyor, outbox boşalıyor. |
| **Duplicate düşürme** | Aynı `(device_id, seq)` zarfı gerçek broker üzerinden iki kez yayınlanıyor (QoS1 yeniden-gönderimi simülasyonu); `Watermark.should_process()` uygulayan abone yalnızca **1** kez işliyor. |

Tam regresyon (`python -m pytest -q`): **26 passed** (21 önceki + 5 yeni),
yeni modüller mevcut hiçbir testi bozmadı.

## 6. Açık maddeler

- [ ] Gerçek Eclipse Mosquitto ikili dosyası — admin erişimi olan/farklı bir
      ortamda `tools/run_amqtt_broker.py` yerine gerçek `mosquitto`
      komutuyla değiştirilip aynı testlerin (kod değişikliği gerektirmeden,
      `mqtt_bus.py` MQTT 3.1.1'e bağlı) geçtiği doğrulanmalı.
- [ ] `panogoz/bus`/`panogoz/store`, henüz `panogoz/sim` → `detector` →
      `rules` → `api` üretim pipeline'ına gerçekten TELLENMEDİ (bu görev
      yalnızca modülleri kurup E2E ile kanıtladı) — sonraki bir K2 maddesi.
- [ ] Compose sertleştirme (mTLS, ACL) — 2.2, henüz yapılmadı.
- [ ] IEC 60870-5-104 slave — 2.3, henüz yapılmadı.
