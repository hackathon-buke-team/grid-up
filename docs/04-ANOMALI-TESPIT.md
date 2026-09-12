# 04 — Anomali Tespiti, Bastırma, Bildirim (K4)

Bu belge K4 (Bildirim, Doğrulama, Sunum) paketinin uyguladığı dedektör, kural ve
bildirim mantığını anlatır. Kod: `panogoz/detector/engine.py`,
`panogoz/rules/`, `panogoz/notify/`, `panogoz/sim/scenarios.py`.

> **Dürüstlük notu:** Bu dosyanın altındaki her mekanizma bu depoda çalışır kod
> olarak mevcuttur ve `python -m pytest -q` ile doğrulanır (45/45 yeşil, bu
> yazının tarihi itibarıyla). Ölçülmeyen hiçbir sayı burada "sonuç" olarak
> sunulmuyor; eşik sabitleri kendi sentetik senaryo kütüphanemize göre
> kalibre edildi ve `tools/run_accuracy_report.py` ile tekrar üretilebilir.

## 1. θ metriği

```
theta_raw(T_hedef, T_kardesler, I_anma) = (T_hedef - medyan(T_kardesler)) / I_anma
```

Aynı fiderdeki üç faz, aynı ortamı (ortam sıcaklığı, havalandırma, yük profili)
paylaştığı için kardeş medyanına göre fark, mevsim ve günlük yük dalgalanmasını
büyük ölçüde sadeleştirir. Anma akımına bölme, 250 A ve 400 A fiderleri aynı
ölçekte karşılaştırılabilir kılar.

## 2. Isıl gecikme düzeltmesi (RLS)

`ThermalRLS` (`panogoz/detector/engine.py`), theta_raw'ı ΔI² üzerine çevrimiçi
(recursive) bir doğrusal regresyona sokar. Yük değişimi ile orantılı olan
bileşen katsayıya (`a`) yazılır; kalan kalıntı (residual) yükten bağımsız,
yani gerçek arıza kaynaklı bileşendir. Sentetik senaryolarda hedef faz akımı
kardeşleriyle aynı kaldığı için (gevşek bağlantı yalnız direnci değiştirir,
akımı değil), regresör kalıntıyı neredeyse hiç açıklamaz ve theta_raw'ın
tamamına yakını kalıntıda kalır — bu da dedektörü gerçekten yük-bağımsız yapar.

## 3. CUSUM — haftalar önce haber verme

`CusumDetector`, günlük medyan theta üzerinde klasik CUSUM algoritmasını
çalıştırır (`k` = izin verilen sürüklenme payı, `h` = alarm eşiği). A2
senaryosunda (yavaş gevşeme, 12 günde k=1.0→3.0) sistem arızayı **5. günde**
yakalıyor; bağlantı mutlak güvenlik limitine (110 °C) hiç ulaşmıyor bile —
"ağustosta kör olmayan, şubatta yanlış alarm üretmeyen" iddiasının somut
kanıtı budur (bkz. `tests/test_rules.py::test_slow_drift_detected_weeks_before_absolute_limit`).

## 4. Mutlak güvenlik limitleri

110 °C KRİTİK, 130 °C ACİL — öğrenme/ısınma dönemi dahil ilk andan itibaren
aktif ve tüm bastırma/debounce mantığını bypass eder (`absolute_severity`).
Bu, görev dağılımı belgesindeki "füzyon, dedektörün kararını anlık θ ile
eziyordu" hatasının kalıcı çözümüdür: **mutlak limitler her zaman üstte kalır**
(`panogoz/rules/fusion.py::max_severity`).

## 5. Diğer arıza aileleri

| Aile | Metrik | Konum |
|---|---|---|
| Aşırı yük | `current_ratio_peak > 1.10` (anma akımına oranla), 3/5 gün | `rules/engine.py` |
| Nötr harmonik yüklenme | `I_nötr / I_anma > 0.15`, 3/5 gün | `rules/engine.py` |
| K_N (gevşek nötr ayrımı) | `K_N = ΔT/I²` — koddadır (`detector/engine.py::neutral_k`), 17 senaryoda ayrı test edilmedi; açık madde | docs, bkz. §7 |
| Nem/yoğuşma | çiy noktası marjı (Magnus formülü) < 0, 3/5 gün | `rules/engine.py` |
| Yalıtım/PD | PD skoru > 0.5, 3/5 gün + akım korelasyonu | `rules/engine.py` |
| Ark bütünlüğü | TVOC-2 öz test hatası → anlık ALARM; gerçek trip → anlık EMERGENCY | `rules/engine.py` |

## 6. expect_flags (§4.3 sözleşme açıkları)

`compute_expect_flags` üç bayrağı hesaplar:

- **STALE** — `now - last_ts > period_s * stale_factor` (varsayılan 2.5×).
- **DE_ENERGISED** — akım, enerjisiz kabul edilen eşiğin altında.
- **SENSOR_DRIFT** — cihazın kendi bildirdiği kalibrasyon sapma skoru eşiği aşıyor.

N3 (iletişim kopması) yalnız STALE, N4 (planlı bakım) yalnız DE_ENERGISED, N7
(kalibrasyon kayması) yalnız SENSOR_DRIFT üretir ve **hiçbiri gerçek alarm
açmaz** — bu üçü `tests/test_rules.py` içinde ayrı ayrı doğrulanıyor.

## 7. Bastırma → Füzyon → Alarm (sabit sıra)

1. **Bastırma** (`rules/suppression.py`): 3/5 günlük debounce, %40 ölü bant
   (kapanmak için değerin eşik×0,6 altına inmesi gerekir), iki kanal ailesi
   şartı — termal/PD bulgusu yalnız akım ailesinin devrenin enerjili olduğunu
   doğrulamasıyla (DE_ENERGISED yokluğu + asgari yük) alarm'a yükselir.
2. **Füzyon** (`rules/fusion.py`): tek karar mercii, `max_severity` — mutlak
   limitler ve gerçek ark trip'i her zaman kazanır.
3. **Alarm/Eskalasyon** (`notify/escalation.py`): 4 haneli kimliklendirilmiş
   onay token'ı, şiddete göre tekrar aralığı (ALARM 30dk / CRITICAL 15dk /
   EMERGENCY 5dk), saatlik 5 bildirimlik fırtına sınırı (aşan olaylar
   `storm_digest`'e düşer), sessize alma, vardiya devri özeti.

Her bastırılan (eşiği aşıp da alarm açmayan) gün, sayısı ve zaman damgasıyla
`PipelineResult.suppression_log`'a yazılır — "78 °C okudun, neden söylemedin?"
sorusunun cevabı budur.

## 8. Bildirim kanalı seçimi (§4.1)

**Seçim: Telegram Bot API.**

- WhatsApp Business API ve Twilio, işletme onayı ve/veya telefon numarası
  doğrulaması ister; hackathon süresine (birkaç saat) sığmaz.
- Telegram Bot API ücretsizdir, BotFather üzerinden dakikalar içinde kurulur,
  gerçek push bildirimini doğrudan telefona düşürür.
- On-premise kısıtına uyar: sunucudan yalnızca tek yönlü, dışa giden bir HTTPS
  çağrısı yapılır (`panogoz/notify/telegram_channel.py`); hiçbir veri
  Telegram dışında üçüncü bir bulut hizmetinde saklanmaz/işlenmez.
- **Veri mahremiyeti:** mesaj gövdesine yalnızca bağlantı kimliği, şiddet
  seviyesi ve onay token'ı yazılır; ham sensör verisi veya pano/lokasyon
  detayı gönderilmez.

Kod seviyesinde `ConsoleChannel` (test/geliştirme) ve `TelegramChannel`
(gerçek kanal) aynı `send(text) -> dict` arayüzünü paylaşır; `EscalationLadder`
hangisiyle çalıştığını bilmez.

## 9. Doğruluk sunumu (§4.4)

`python -m tools.run_accuracy_report` şunları üretir (`reports/` altına):

- `dogruluk-matrisi.csv` / `dogruluk-raporu.md` — 17 senaryo × tespit sonucu.
- `duyarlilik-egrisi.png` / `.csv` — θ eşiği taraması: üretim hattı (debounce +
  CUSUM + akım korelasyonu) tüm taranan eşik aralığında 10/10 tespit, 0/7
  yanlış alarm veriyor; ham (bastırmasız) tek-örnek eşik ise dar bir güvenli
  aralık dışında ya gürültüden yanlış alarm üretiyor ya da yavaş gelişen
  arızayı kaçırıyor. Bu, "sabit eşik" yaklaşımına karşı asıl argümanın görsel
  kanıtıdır.

En son çalıştırmada: **10/10 duyarlılık, 0/7 yanlış alarm**, haber verme
süresi dağılımı (arıza başlangıcından itibaren gün): min 0, medyan 2, maks 8.

## 10. Açık maddeler (dürüstçe)

- K_N (gevşek nötr / harmonik ayrımı) koddadır ama 17 senaryo kütüphanesi bunu
  ayrı bir vaka olarak sınamıyor; A5 alarmı doğrudan nötr akım oranı eşiğiyle
  tetikleniyor. Gelecek iş: "yüksek K_N + normal akım" ve "normal K_N + yüksek
  akım" vakalarını ayıran özel bir senaryo.
- Eşik sabitleri (`THETA_PEAK_THRESHOLD`, `OVERLOAD_RATIO`, vb.)
  `panogoz/rules/engine.py` içinde kendi sentetik fizik modelimize göre
  kalibre edildi; gerçek saha verisiyle yeniden kalibrasyon gerekir.
- Bu K4 paketi bağımsız çalışabilmesi için minimal bir θ/RLS/CUSUM dedektör
  omurgası ve kanal sözleşmesi de içeriyor (`panogoz/contracts/`,
  `panogoz/detector/`, `panogoz/sim/`); K1/K2/K3 gerçek modülleri hazır
  olduğunda bu arayüzler üzerinden değiştirilebilir.
