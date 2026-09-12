# Jüri Soru-Cevap Kartları (K4 §4.5)

Her kart: olası soru → kısa cevap → kanıta işaret.

## Tespit / doğruluk

**S: θ eşiğini nasıl seçtiniz, keyfi değil mi?**
C: Kendi 17 senaryolu sentetik kütüphanemizle taradık (`reports/duyarlilik-egrisi.png`).
Üretim hattı (debounce+CUSUM+akım korelasyonu) taranan tüm eşik aralığında
10/10 tespit, 0/7 yanlış alarm veriyor — yani karar tek bir eşik sabitine
aşırı duyarlı değil. Gerçek saha verisiyle yeniden kalibre edilecek, bunu
belgede açıkça yazdık (`docs/04-ANOMALI-TESPIT.md` §10).

**S: Yanlış alarm oranınız gerçekte ne olur, sentetik veriyle sınırlı değil mi?**
C: Evet, bugünkü sayı sentetik senaryo kütüphanesine dayanıyor; bunu
gizlemiyoruz. Gerçek sahada K2'nin 1000 pano yük testi ve gerçek Mosquitto
entegrasyonu tamamlandığında aynı doğruluk matrisi gerçek veriyle
tekrarlanacak.

**S: CUSUM neden "haftalar önce" haber verebiliyor?**
C: Günlük medyan theta'daki küçük ama sürekli sapmayı biriktiriyor. A2
senaryomuzda (12 günde yavaş gevşeyen bağlantı) sistem 5. günde haber
veriyor, bağlantı hiçbir zaman mutlak güvenlik limitine (110°C) ulaşmıyor
(`tests/test_rules.py::test_slow_drift_detected_weeks_before_absolute_limit`).

## Bildirim

**S: Neden WhatsApp/SMS değil de Telegram?**
C: WhatsApp Business API ve Twilio SMS, işletme onayı/telefon doğrulaması
istiyor; hackathon süresine sığmıyor. Telegram Bot API ücretsiz, dakikalar
içinde kurulur, gerçek push bildirimi telefona düşürür ve on-prem kısıtına
uyar (sunucudan yalnız tek yönlü dışa HTTPS çağrısı). Üretim ortamında GSM
modem/SMS'e geçiş, `notify/` arayüzü aynı kaldığı için kanal değişimi
gerektirmiyor — `ConsoleChannel`/`TelegramChannel` aynı `send()` arayüzünü
paylaşıyor.

**S: Alarm fırtınası olursa telefon sürekli mi çalar?**
C: Hayır — `EscalationLadder` saatlik 5 bildirimle sınırlı; aşan olaylar tek
bir özet halinde (`storm_digest`) toplanıyor.

**S: Biri alarmı yanlışlıkla mı kapatabilir?**
C: Hayır — onay, tahmin edilemeyen 4 haneli token + kişi eşleşmesi
gerektiriyor (`notify/escalation.py::acknowledge`); yanlış token reddediliyor.

## Genel / dürüstlük

**S: Bu sistem gerçek bir panoda test edildi mi?**
C: Hayır, şartname bunu istemiyor ve biz de yapmadık. Sentetik veri gerçek
CT ölçümüne (`İstenen Veriler.xlsx`, L1 fazı, 1,5 gün/15 dk) dayanıyor;
sıcaklık/nem/ARC/PD kanalları kendi fizik modelimizden üretildi çünkü
organizatör bu kanallarda hazır veri sağlamadı.

**S: Sistem koruma (trip) yapıyor mu?**
C: Hayır ve bunu açıkça söylüyoruz. Ark açması SIL-2 donanımda (ABB TVOC-2)
~1ms'de gerçekleşiyor; biz yalnız gözlüyoruz, konumlandırıyoruz, zaman
damgalıyoruz ve haber veriyoruz.

**S: Eksik olan en büyük şey ne?**
C: Fiziksel/mekanik yerleşim görseli, gerçek Mosquitto uçtan uca testi ve
demo provası — bunlar sırasıyla K1, K2, K4 tarafından kapatılıyor
(bkz. görev dağılımı §3 Geliştirilecekler, P1 satırları).
