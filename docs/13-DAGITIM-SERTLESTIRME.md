# 13 · On-Prem Dağıtım ve Sertleştirme (K2 2.2)

> Şartname: Public Cloud yok; sistem şirket içinde çalışmalı; mission-kritik. Bu belge dağıtım
> topolojisini, tehdit modelini ve **neyin gerçekten doğrulandığını** anlatır.

## 0. Durum (dürüst)

| Parça | Durum | Kanıt |
| --- | --- | --- |
| `docker-compose.yml`, `Dockerfile`, `deploy/mosquitto/{mosquitto.conf,acl}`, `deploy/nginx/*` | **Yazıldı; çalıştırılmadı** — bu makinede Docker/Mosquitto/nginx yok | — |
| Yapılandırma değişmezleri (root olmayan kullanıcı, `cap_drop: ALL`, salt okunur kök FS, sağlık kontrolü, yalnız istenen portlar, iç ağ, sertifikalar `:ro`, CA anahtarı hiçbir yerde yok, sürüm sabitleme, yalnız mTLS dinleyici) | **Doğrulandı** (metin/YAML düzeyinde) | `tests/test_deploy.py` |
| Mosquitto ACL anlamı (cihaz yalnız kendi konusu, joker ile dinleme yok, sunucu telemetri UYDURAMAZ) | **Doğrulandı — Mosquitto kurallarının Python yeniden uygulamasıyla** (gerçek broker DEĞİL) | `tools/mosquitto_acl.py`, `tests/test_deploy.py` |
| PKI: kök CA + sunucu/istemci sertifikaları, cihaz kimliği = CN | **Doğrulandı — GERÇEK karşılıklı TLS el sıkışmasıyla** (Python `ssl`) | `tools/gen_certs.py`, `tests/test_deploy.py` |
| `MqttBus` TLS/mTLS yolu | **Doğrulandı** — sahte MQTT-over-TLS sunucusuna karşı: geçerli sertifika bağlanır, sunucu cihaz CN'ini görür; sertifikasız/yabancı CA reddedilir | `panogoz/bus/mqtt_bus.py`, `tests/test_deploy.py` |
| `/healthz`, `/readyz` | **Doğrulandı** | `tests/test_deploy.py` |
| Üretim sınıfı WSGI (`waitress`) | Kodlandı, elle çalıştırılabilir (`python -m panogoz.run_local`) | — |

Gerçek konteynerde `docker compose up` sonrası davranış (Mosquitto'nun ACL'yi gerçekten uygulaması,
nginx'in istemci sertifikası zorlaması, sağlık kontrollerinin geçmesi) **denenmemiştir**. Bunu ilk
Docker'lı makinede yapmak §5'in ilk maddesidir.

## 1. Topoloji

```
 saha düğümleri (TC / IR-PD / ağ geçidi)
        │  MQTT 8883, karşılıklı TLS (cihaz sertifikası, CN = cihaz kimliği)
        ▼
 ┌─ ingest ─┐         ┌────────── backend (internal: dış çıkış YOK) ──────────┐
 │ mosquitto │◄───────►│ mosquitto ◄──► panogoz (uygulama) ◄──► proxy (nginx)  │
 └───────────┘         └───────────────────────────┬──────────────┬────────────┘
                                           scada ──┘              └── edge ──► operatör (TLS 443 + istemci sertifikası)
                       Modbus TCP 5020 · IEC 104 2404  (yalnız SCADA arayüzüne bağlanır)
```

- `backend` ağı `internal: true`: broker, uygulama ve vekil birbirini görür, **dışarıya çıkamaz**.
- Uygulamanın HTTP'si (8080) **hiçbir yere yayınlanmaz**; yalnız vekil erişir.
- SCADA protokolleri varsayılan olarak `127.0.0.1`'e bağlanır (`SCADA_BIND_ADDR` ile SCADA arayüzü verilir).

## 2. Tehdit modeli → önlem

| Tehdit | Önlem | Doğrulama |
| --- | --- | --- |
| Sahte cihaz telemetri gönderir | Karşılıklı TLS: yalnız CA'nın imzaladığı istemci sertifikası; `allow_anonymous false`; parola yok | mTLS testleri (sertifikasız/yabancı CA reddedilir) |
| Cihaz başkası adına yayın yapar | Kimlik = sertifika CN'i; ACL `pattern write panogoz/v1/dev/%u/telemetry` | ACL testleri |
| Ele geçirilmiş cihaz tüm filoyu dinler | ACL yalnız kendi `.../cmd` konusunu okutur; joker abonelik reddedilir | ACL testleri |
| Ele geçirilmiş **sunucu** cihaz adına telemetri uydurur | `panogoz-server` telemetri konularını YAZAMAZ (yalnız okur; yalnız `cmd` yazar) | ACL testleri |
| Cihaz sertifikasıyla brokerı taklit etme | Cihaz sertifikası EKU=clientAuth; istemci `serverAuth` ister | mTLS testi (`impersonate_the_broker`) |
| Ortadaki adam / yanlış sunucu | İstemci CA'ya ve ana bilgisayar adına (SAN) karşı doğrular, `tls_insecure` yok | mTLS testleri |
| Konsola yetkisiz erişim | nginx: TLS 1.2+/1.3 + **operatör istemci sertifikası zorunlu**, HSTS, CSP, `X-Frame-Options: DENY` | nginx yapılandırma testi (çalıştırılmadı) |
| Demo kontrol uçlarının (`/api/sim/*`) üretimde kullanılması | Vekil 403; uygulama `--no-demo-controls` ile başlar | yapılandırma testi + `test_fleet_api` |
| Onay/kapatma uçlarında kaba kuvvet (4 haneli belirteç) | nginx `limit_req` (2 istek/sn) + uygulama belirteci yalnız mesajda | yapılandırma testi (canlı denenmedi) |
| Konteyner kaçışı / ayrıcalık yükseltme | Root olmayan kullanıcı, `cap_drop: ALL`, `no-new-privileges`, salt okunur kök FS | compose değişmez testleri |
| Broker'ın boğulması | `max_connections`, `max_packet_size`, `message_size_limit`, `max_queued_messages` | yapılandırma testi |
| Gizli anahtar sızıntısı | `deploy/certs/` ve `*.key` `.gitignore`'da ve `.dockerignore`'da; CA anahtarı çevrimdışı, hiçbir konteynere verilmez | `test_private_keys_are_git_ignored` vb. |
| Test araçlarının üretim imajına girmesi | Ayrı `requirements-runtime.txt`; Dockerfile yalnız onu kurar | `test_dockerfile_...` |

## 3. Kurulum

```bash
python -m tools.gen_certs --out deploy/certs --devices TC-0001 IRPD-0001 GW-0001
# deploy/certs/ca.key'i ÇEVRİMDIŞI bir yere taşıyın (sunucuda tutulmaz)
docker compose up -d --build
# operatör sertifikası: tools.gen_certs.issue(...) ile CN=<operatör adı>, tarayıcıya içe aktarın
```

Cihaz eklemek: yeni bir CN üret (`topics.valid_device_id`: harf/rakam/`-`/`_`, 2–32 karakter; `panogoz-server` ve
`panogoz-health` ayrılmıştır), sertifika+anahtarı cihaza yükle. ACL dosyası **değişmez** (kurallar `%u` ile genel).

Konu şeması (`panogoz/bus/topics.py`): `panogoz/v1/dev/<id>/telemetry` (cihaz→sunucu), `panogoz/v1/dev/<id>/cmd`
(sunucu→cihaz), `panogoz/v1/srv/#` (sunucu içi), `panogoz/v1/health/health-probe`.

Not (gerçek bir hata): Mosquitto'da `%u`/`%c` yer tutucuları **yalnız `pattern` satırlarında** çalışır; `user` altındaki
`topic` satırında değişmez metindir. İlk ACL taslağı sağlık kullanıcısı için `topic ... %c` yazmıştı — bu gerçek
Mosquitto'da hiçbir şeye eşleşmezdi; ACL testi yakaladı ve sabit kimlikle düzeltildi.

## 4. Sertifika yaşam döngüsü

- Cihaz/sunucu sertifikaları 365 gün (`--days`), kök CA 10 yıl. Rotasyon: yeni sertifika üret, cihaza yükle.
- **İptal (revocation) YOK:** kaybolan/ele geçirilen cihazı engellemek için şu an yalnızca CA'yı değiştirmek veya
  Mosquitto'ya `crlfile` eklemek gerekir (§5).

## 5. Açık maddeler (dürüstçe)

1. **Gerçek konteynerde doğrulama:** `docker compose up` çalıştırılmadı; Mosquitto'nun ACL'yi/ mTLS'i gerçekten
   uyguladığı, nginx'in istemci sertifikası zorladığı, sağlık kontrollerinin geçtiği canlı denenmeli
   (`mosquitto_pub` ile yetkisiz konu, `curl` ile sertifikasız istek).
2. **MQTT → boru hattı bağlantısı yok:** uygulama bugün SİMÜLE filoyu sunar; broker'dan gelen telemetri henüz
   `bus → store → detector` zincirine bağlı değil (docs/01-MIMARI.md §6). Compose, düğümlerin bağlanacağı sertleştirilmiş
   iskelettir.
3. **Kimlik `by` alanında iddiadır:** vekil `X-Client-CN` başlığını iletir ama uygulama onay/kapatma `by` alanını bu
   başlığa bağlamıyor.
4. **Sertifika iptali** (CRL/OCSP) yok.
5. **SCADA protokolleri TLS'siz:** Modbus TCP ve IEC 104 açık metindir (protokol gereği); ağ düzeyinde SCADA VLAN'ına
   bağlama + salt okunur olma ile sınırlandı. IEC 62351-3 (TLS üzerinden 104) uygulanmadı.
6. Günlük toplama/merkezi izleme, yedekleme/geri yükleme, imaj zafiyet taraması, `mosquitto` kalıcı verisinin şifrelenmesi
   ele alınmadı.
7. `run_local` dev senaryo sunucusudur; canlı ortamda fleet servisi yerine gerçek veri kaynağı bağlanmalıdır.
