# 12 · Bildirim Kanalı ve Eskalasyon (K4 4.1 + 4.2)

> Şartname §7: "Kritik durumların yalnızca monitoring ekranında gösterilmesi yeterli
> değildir; SMS, WhatsApp veya benzeri anlık bildirim kanalları üzerinden uyarı
> gönderebilecek bir mekanizma tasarlanmalı veya prototip üzerinde gösterilmelidir."

## 0. Durum (dürüst)

| Parça | Durum | Kanıt |
| --- | --- | --- |
| Alarm yaşam döngüsü (aç/yükselt/temizle/onayla/7 gün otomatik kapan/sessize al) | **Bitti, testli** | `panogoz/rules/alarms.py`, `tests/test_alarm_lifecycle.py` (21 test) |
| Eskalasyon (rota, belirteç, tekrar, fırtına sınırı, sessize alma, nöbet devri, teslimat hatası) | **Bitti, testli** | `panogoz/notify/escalation.py`, `tests/test_escalation.py` (19 test) |
| Telegram kanalı, tek yönlü gönderim | **GERÇEK gönderim yapıldı (2026-09-20):** `send_real_alarm_demo --send` ile fizik senaryosundan açılan ilk ALARM için tek "DEMO-" önekli mesaj gerçek Telegram Bot API'ye gönderildi; `sendMessage` HTTP 2xx döndü (`raise_for_status` geçti, `[SENT]` kaydı düştü). Mesajın telefona ulaştığı kullanıcı tarafından teyit edildi (betik bunu kendisi ölçmez). | `panogoz/notify/telegram_channel.py`, `tools/send_real_alarm_demo.py` |
| Telegram `ONAY <alarm> <belirteç>` yanıtını okuma (iki yönlü) | Kod + sahte-HTTP testi hazır. Gerçek koşuda 120 sn beklendi, **yanıt gelmedi** (alarm açık kaldı): iki yönlü yol gerçek Telegram'da **doğrulanmadı** | `TelegramAckPoller`, `tests/test_escalation.py` |
| On-prem GSM modem SMS kanalı | Kod + AT-protokol testi **sahte seri portla**; **gerçek modemle denenmedi** | `panogoz/notify/gsm_modem.py`, `tests/test_gsm_modem.py` (11 test) |
| "Gerçek kanaldan tek mesaj" (CLAUDE.md §8 P1) | **Tamam (tek yönlü), 2026-09-20** | Yukarıdaki satır; komut aşağıda |

Gerçek mesajı göndermek için (tek satır, kimlik bilgileri ortam değişkeninde):

```
TELEGRAM_BOT_TOKEN=... TELEGRAM_CHAT_ID=... python -m tools.send_real_alarm_demo --send --wait-ack 120
```

Betik gerçek fizik senaryosunu çalıştırır, ilk ALARM açılınca **tek** mesaj gönderir
("DEMO-" önekli, gerçek arıza sanılmasın), 120 sn boyunca Telegram'dan
`ONAY <alarm> <belirteç>` yanıtını bekler ve alarmı gerçekten onaylar. `--send`
olmadan (varsayılan) hiçbir dış sisteme bağlanmaz.

## 1. Kanal seçimi

| Kanal | Artı | Eksi | Karar |
| --- | --- | --- | --- |
| **GSM modem SMS** (yerel modem, AT komutları) | Bulut hizmeti yok, yalnız operatör şebekesi (**on-prem'e en uygun**); internet kesikken de çalışır; alıcıda uygulama gerekmez | Modem + SIM maliyeti; teslim raporu yok (şu an); 160 karakter, ASCII; iki yönlü onay yok | **Üretim birincil kanalı (önerilen)** |
| **Telegram Bot API** | Ücretsiz, dakikalar içinde kurulur, HTTPS push; iki yönlü (`ONAY` yanıtı) | Mesaj sağlayıcı bulutundan geçer; alıcı botu bir kez başlatmış olmalı; internet gerekir | **Demo + ikincil kanal** (iki yönlü onay burada gösterilir) |
| WhatsApp Business API | Kullanıcı bunu zaten kullanıyor | Meta bulutu; iş doğrulaması ve şablon onayı gerekir (kurulum süresi belirsiz); bu hackathon süresinde güvenilir kurulamaz | Seçilmedi; dispatcher'da `route` olarak eklenebilir |
| Sesli arama / e-posta | — | Kritik alarm için gecikme/bayat okuma riski | Kapsam dışı |

Karar: kanal soyutlaması `Dispatcher` arkasında (`RoutedDispatcher`, `route` alanı:
`telegram` / `sms` / `console`), yani seçim yapılandırmadır, kod değişikliği değil.
**Üretimde SMS/GSM modem, demoda Telegram** — çünkü şartname "Public Cloud yok" diyor
ve alarm meta verisi (hangi panoda hangi arıza) enerji dağıtımında operasyonel olarak
hassastır.

Yapılan kanıt: GSM yolu yalnız sahte seri portla sınandı (gerçek modemle hiç denenmedi).
Telegram yolu sahte HTTP ile sınandı **ve 2026-09-20'de gerçek Bot API'ye tek yönlü bir
gerçek mesaj gönderildi** (telefona ulaştığı teyit edildi); iki yönlü `ONAY` yanıtı gerçek
Telegram'da doğrulanmadı.

## 2. Veri mahremiyeti notu

Mesajda **yalnız** şunlar var: bağlantı kimliği, faz, şiddet (UYARI/ALARM/KRİTİK), alarm
türü etiketi, tek bir puan (θ vb.), alarm kimliği ve onay belirteci. **Ham sensör
serisi, akım/sıcaklık/nem değerleri, pano konumu ve kişisel veri mesaja girmez.**

| Kanal | Sağlayıcıya ne gider | Not |
| --- | --- | --- |
| GSM modem | Mesaj metni operatör SMSC'sine gider | Kendi altyapımızda bulut yok; SMS şifresizdir |
| Telegram | Mesaj metni + alıcının `chat_id`'si Telegram sunucularına gider | Bot sohbetleri "cloud chat"tir (uçtan uca şifreli değil); sunucular birden çok yargı alanında |

Kişisel veri: nöbetçilerin telefon numarası / `chat_id`'si kişisel veridir (KVKK);
`SentMessage` günlüğünde adres saklanmaz (yalnız isim/rota/durum). **Hukuki KVKK
değerlendirmesi yapılmadı** — sahaya çıkmadan önce yapılmalı.

## 3. Eskalasyon politikası (`EscalationPolicy` varsayılanları)

| Şiddet | Kim, ne zaman | Onaysızsa |
| --- | --- | --- |
| UYARI | Yalnız konsol; **mesaj yok** | — |
| ALARM | 1. kademe (saha nöbetçisi) | 15 dk'da bir hatırlatma (en çok 6); 30 dk onaysız → 2. kademe (bölge sorumlusu); 30 dk daha → 3. kademe (müdür) |
| KRİTİK | 1.+2. kademe **aynı anda** | 5 dk'da bir hatırlatma; 10 dk onaysız → 3. kademe |

- **Onay belirteci:** her mesajda `ONAY <alarm-id> <4 haneli belirteç>`. Belirteç
  alarm başına deterministik/gizli; belirteçsiz veya isimsiz onay reddedilir
  (`AckError`). Telegram yolunda kimlik Telegram'ın `from` alanından gelir, uydurulamaz;
  yalnız izinli `chat_id`'lerden gelen yanıt işlenir.
- **Şiddet yükselirse** önceki onay geçersiz olur ve alarm yeniden sevk edilir
  ("ŞİDDET YÜKSELDİ"); daha kötü duruma verilmiş onay eski durum içindi.
- **Fırtına sınırı:** alıcı başına saatte en çok 6 mesaj; fazlası "N bildirim bastırıldı"
  özetine dönüşür. Bastırma bir teslimat hatası **sayılmaz** (eskalasyon tetiklemez).
  KRİTİK ilk sevk sınırı aşar.
- **Sessize alma:** iki düzey — alarm motorunda tür/iz bazlı (bakım penceresi, gerekçe +
  kişi zorunlu) ve alıcı bazlı. İkisi de KRİTİK'i **bastıramaz**.
- **Nöbet devri:** vardiya takvimi (`Shift`, gece yarısını aşan vardiya desteklenir) +
  açık devir kaydı (`handover(t, kademeler, not)`). Alarm sürerken nöbetçi değişirse
  yeni kişi hatırlatma zamanlayıcısı **beklenmeden** "NÖBET DEVRİ" önekiyle aranır.
- **Teslimat hatası sessiz yutulmaz:** kanal hata verirse mesaj `failed` kaydedilir ve
  aynı anda bir üst kademe aranır. Sessizdeki kişi de atlanır, kademe boş kalırsa sıradaki
  aranır.
- **Kapanış döngüsü:** onay, temizlenme ve kapanış bildirimi aranmış herkese gider.

Alarm hijyeni (bastırma → füzyon → alarm; %40 ölü bant, 3/5 debounce, 7 gün otomatik
kapanma, iki kanal ailesi şartı) için bkz. `docs/09-VERI-ANALIZI.md` §2 ve
`panogoz/rules/`.

## 4. Test kanıtı (bizzat çalıştırıldı)

- `tests/test_alarm_lifecycle.py` — 21 test (tüm durum geçişleri, belirteç/kimlik, flapping,
  latching ark TRIP, gerçek senaryo).
- `tests/test_escalation.py` — 19 test (rota, hatırlatma, eskalasyon, onay sonrası sessizlik,
  fırtına sınırı+özet, sessize alma, teslimat hatası, nöbet devri, Telegram okuyucu,
  **gerçek senaryodan uçtan uca**).
- `tests/test_gsm_modem.py` — 11 test (AT akışı, SIM PIN, hata kodu, zaman aşımı, ASCII katlama).
- **Mutasyon kontrolü:** fırtına sınırı, sessize alma ve hata-sonrası kademe atlama
  koduna tek tek bozulma sokuldu; ilgili testler kırıldı, geri alındı.

Testte bulunup düzeltilen iki tasarım hatası: (1) fırtına sınırıyla bastırılan mesaj
"teslimat başarısız" sayılıp üst kademeyi arıyordu — bastırma kasıtlıdır, eskalasyon
tetiklemez; (2) nöbet değişince yeni nöbetçi bir sonraki hatırlatma zamanlayıcısını
beklemek zorunda kalıyordu — devir anında derhal aranmalı.

## 5. Açık maddeler

- **İki yönlü onay, gerçek Telegram'da:** 2026-09-20 koşusunda tek yönlü gönderim çalıştı ve
  telefona ulaştı; `--wait-ack 120` süresince `ONAY` yanıtı gelmedi, yani `TelegramAckPoller`
  gerçek kanalda hiç doğrulanmadı (yalnız sahte-HTTP testi). Yeniden denemek yeni bir gerçek
  mesaj gönderir. (Not: 2026-09-12'de silinen eski uygulamayla da bir gönderim denenmişti,
  teyit kaydı yoktu; bu satır yalnız yeni koddur.)
- GSM modem gerçek cihazla denenmedi; teslim raporu (`+CDS`) okunmuyor.
- SMS'te iki yönlü onay yok; onay konsol/API veya Telegram üzerinden.
- Alarm günlüğü/eskalasyon durumu bellekte; yeniden başlatmada kalıcı değil
  (`panogoz/store` outbox'ına bağlanması docs/01-MIMARI.md §6 açık maddesiyle aynı iş).
- KVKK hukuki değerlendirmesi.
