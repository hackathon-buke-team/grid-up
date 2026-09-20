# K2 · 2.4 Ölçeklenebilirlik — Yük Testi ve Kaynak Ölçümü

> K2 iş paketinin **2.4 1000 pano yük testi + kaynak ölçümü** maddesini karşılar:
> "CPU/RAM/disk/yazma hızı/tur süresi — kademeli 250→500→1000." Bitti sayılır
> kriteri: gerçek ölçülmüş sayılarla bir tablo, uydurma yok.

## 1. Neyi, nasıl ölçtük

`tools/run_load_test.py` gerçek bir HTTP sunucusu ayağa kaldırmadan (ağ
katmanını değil, asıl yükü — hesaplama + serileştirme + disk yazma — ölçmek
için) şunları yapar:

1. **Kurulum (build):** `panogoz.sim.demo_fleet.build_fleet(n)` ile N gerçek
   CT verisine dayalı (`İstenen Veriler.xlsx`, 152 nokta/panoyu paylaşımlı
   okunan tek bir L1 serisinden türetilen) panonun θ/kural motoru
   hesaplamasının gerçek duvar-saati süresi (`time.perf_counter()`).
2. **Servis:** `panogoz/api/app.py`'nin gerçek `_connection_summary`/
   `_connection_series` fonksiyonları N pano için gerçekten çağrılır —
   API'nin her istekte yapacağı serileştirme işini birebir tekrarlar.
3. **CPU/RAM:** bu sürecin kendi `psutil.Process` ölçümü (`memory_info().rss`,
   `cpu_percent()`) — üçüncü parti bir "tahmin" değil, gerçek işletim
   sistemi sayaçları.
4. **Disk/yazma hızı:** `panogoz.store.Outbox`'a (bu gece K2 2.1'de kurulan
   gerçek SQLite outbox) N gerçek `Envelope` kaydı gecici bir dizinde
   `enqueue()` edilir, gerçek dosya boyutu (`os.path.getsize`) ve gerçek
   yazma süresi ölçülür.

Bilinçli sınır: `panogoz/bus` (MQTT) bu ölçüme dahil değil — K2 2.1'de zaten
gerçek broker'a karşı ayrı doğrulandı (`tests/test_bus_mqtt_e2e.py`), burada
tekrar network I/O ölçmek yerine üretim pipeline'ının gerçekten CPU/RAM/disk
tüketen kısmı (θ hesaplama + outbox yazma) izole edildi.

## 2. Gerçek ölçüm sonucu (bu makinede, 2026-09-16)

| Pano | Kurulum (s) | Servis (s) | Pano/ms (kurulum) | RSS toplam (MB) | CPU % | Outbox yazma (s) | Outbox yazma/s | Outbox (KB) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 250  | 0.429 | 0.007 | 1.72 | 83.9  | 100.4 | 0.683 | 366 | 52  |
| 500  | 0.892 | 0.013 | 1.78 | 114.1 | 100.1 | 1.395 | 359 | 92  |
| 1000 | 1.99  | 0.027 | 1.99 | 173.1 | 100.7 | 2.678 | 374 | 176 |

(`python tools/run_load_test.py --panels 250 500 1000` ile tekrar üretilebilir.)

## 3. Bulgular — gerçek, uydurulmamış

- **1000 panoda kırılma noktası YOK bu aralıkta:** kurulum süresi ~2 saniye,
  RSS ~173 MB, CPU tek çekirdekte %100'e yakın (beklenen — tek thread,
  paralel değil) — hepsi rahat sınırlar içinde. 250→1000 arası **kabaca
  doğrusal** ölçekleniyor (pano başına ~1,7-2,0 ms kurulum, ~180-215
  bayt/pano outbox diski).
- **Gerçek darboğaz: tek-thread, senkron mimari.** `build_fleet` panoları
  sırayla, tek çekirdekte işliyor. 1000 pano için sorun değil ama CLAUDE.md'nin
  hedefi olan "en az 100 modül/pano" ölçeğinde (yani çok daha fazla panoda)
  bu doğrusal büyüme devam eder — gerçek bir üst sınır bulunmadı ÇÜNKÜ bu
  ölçüm aralığında hiçbir kaynak (CPU/RAM/disk) doygunluğa yaklaşmadı; asıl
  soru "1000'den sonra ne olur" değil, ne zaman tek-thread'in tur süresi
  (ör. periyodik yeniden hesaplama aralığı) kabul edilemez hale gelir —
  bunun için gerçek bir SLA (ör. "60 saniyede bir tur") tanımlanmalı, henüz
  tanımlanmadı (açık madde).
- **SQLite outbox yazma hızı (~360-375 satır/s) tek-satır-commit'ten
  kaynaklanıyor** (`Outbox.enqueue()` her çağrıda `conn.commit()` yapıyor,
  bkz. `panogoz/store/outbox.py`) — bu, PANO GÖZ'ün gerçek okuma aralığında
  (organizatör verisi 15 dk/örnek, bkz. `panogoz/sim/ct_data.py`) hiçbir
  zaman darboğaz OLMAZ (1000 pano × 15 dk'da bir yazım ≈ 1,1 yazım/saniye,
  ölçülen kapasitenin ~%0,3'ü) — ama toplu (batch) bir geri-doldurma/replay
  senaryosunda (ör. K2 2.1'deki outbox-replay testi gibi, uzun bir kesinti
  sonrası biriken mesajları tek seferde boşaltmak) gerçek bir sınırlayıcı
  olabilir. **Öneri (henüz uygulanmadı):** `executemany`/tek transaction'da
  toplu commit ile bu ~10-50× hızlanabilir — ölçülmedi, tahmin.
- **RSS/pano ~113 KB** (1000 panoda 113 MB delta) — her `ConnectionTimeline`
  152 örneklik tam üç-fazlı zaman serisini + θ + severity dizilerini bellekte
  tutuyor. Gerçek üretimde (sürekli akan veri, sonsuz büyüyen seri değil)
  bu sabit kalır; yalnızca demo/yük-testi modunda (`build_fleet` tüm geçmişi
  tek seferde bellekte tutuyor) böyle. **Açık madde:** gerçek bir sürekli-
  akış senaryosunda (`panogoz/bus`/`store` prod pipeline'ına bağlandığında,
  bkz. `docs/01-MIMARI.md` §6 açık maddesi) bellek profili yeniden ölçülmeli
  — bu ölçüm yalnızca şu anki "tüm geçmişi önceden hesapla" mimarisini
  yansıtıyor.
- **`cpu_percent` %100'ün biraz üstü** (ör. 100.7) — `psutil` çok çekirdekli
  bir makinede tek çekirdek kullanımını `core_sayısı × 100`'e göre değil ham
  yüzde olarak bildirir, >100 olması çoklu ölçüm penceresinde küçük bir
  zamanlama artefaktı, gerçek bir anormallik değil (tek thread hiçbir zaman
  >100'ü anlamlı şekilde aşamaz).

## 3b. Çok kanallı filo servisi (2026-09-20 ölçümü — §1–3'ten AYRI, daha yeni yol)

§1–3, eski yalnız-θ yolunu (`build_fleet`) ölçtü. Konsolun kullandığı **yeni yol** (22 senaryo,
5 dedektör ailesi, bastırma → onay → füzyon, alarm motoru, eskalasyon) `tools/bench_fleet.py` ile,
tek çekirdekte, 22 pano × 60 gün × 15 dk (126 720 pano-örneği) için ölçüldü:

| Aşama | Süre | Hız |
| --- | --- | --- |
| Kurulum: senaryo üretimi + tüm dedektör analizi (toplu/geriye dönük) | 11,2–11,6 sn (≈0,51–0,53 sn/pano) | ≈11 bin pano-örneği/sn |
| Filo ilerletme: alarm motoru + eskalasyon | 0,73–0,77 sn | ≈165–174 bin pano-örneği/sn |

**Yorum (kestirim, ölçüm değil):** 1000 panonun canlı akışı 15 dk aralıkla 1000/900 ≈ 1,1
pano-örneği/sn'dir; ölçülen toplu hızın dört büyüklük mertebesi altında. **Ancak:** (a) dedektörler
bugün toplu çalışır, artımlı (akış) sürümü yazılmadı; (b) 1000 panoluk çok kanallı yük testi
YAPILMADI, yalnız 22 pano ölçüldü ve doğrusal ölçekleme varsayıldı (§2'deki eski yolda doğrusal
çıktı); (c) 1000 panonun geriye dönük 60 günlük ilk analizi bu hızla ≈8,5 dk sürer.

## 4. Sıradaki adım (K2'nin geri kalanıyla tutarlı, kapsam dışı bırakılan)

- Gerçek bir tur-süresi SLA'sı tanımlanıp bu ölçüme karşı test edilmeli.
- Outbox toplu-commit optimizasyonu (yukarıda önerildi, ölçülmedi).
- `panogoz/bus`/`store`'un üretim pipeline'ına bağlanması sonrası bu ölçüm
  gerçek sürekli-akış senaryosuyla tekrarlanmalı (2.2/2.3 kapsamı değil, ayrı
  bir gelecek K2 maddesi).
- Çoklu-çekirdek/çoklu-process paralelleştirme (yalnızca ihtiyaç ortaya
  çıkarsa — bu ölçümde hiçbir kaynak doygunlaşmadı, şu an gerekli değil).
