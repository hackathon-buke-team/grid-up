# K4 · 4.5 Sunum Paketi — 15 Dakikalık Anlatı

> Zamanlanmış anlatı. Kardeş dosyalar: [`juri-qa-kartlari.md`](juri-qa-kartlari.md),
> [`yedek-plan.md`](yedek-plan.md); canlı demo adım adım [`docs/08-DEMO-SENARYOSU.md`](../docs/08-DEMO-SENARYOSU.md).
>
> **Kural:** burada "yapıldı" diye geçen her şey çalıştırılıp doğrulandı (sayıların kaynağı
> her satırın yanında). "Yapılmadı / ölçülmedi" diyenler §6'da açıkça söylenir. Jüri karşısında
> bu ayrımı koru: abartma, ama gerçek olanı da saklama. **Son güncelleme: 2026-09-20**
> (bu tarihte `python -m pytest -q` → **291 test yeşil**, 82 sn).

## 0. Hazırlık (sunumdan önce)

- **Slayt destesi (gerçek ekran görüntüleri ve gerçek veriyle):** artifact linki dosyanın en
  altında (§8). Anlatı o destenin konuşma metnidir.
- **Canlı demo:** `python -m panogoz.run_local --port 8080 --modbus-port 5020 --iec104-port 2404`
  (≈15 sn ısınır). Adımlar ve fare yolları: `docs/08-DEMO-SENARYOSU.md`.
- **Yedek:** `docs/ekran-goruntuleri/01…12-*.png` + `panogoz-demo-walkthrough.gif` +
  `scada-okuma.txt` (hepsi gerçek çalışmadan çekildi; bkz. [`yedek-plan.md`](yedek-plan.md)).
- Donanım gösterimi: `hardware/kicad/*/export/*.pdf` (şematik), `*-3d.png`, `*-top.svg`;
  mekanik: `hardware/mekanik/kabin-ici-yerlesim.svg`.

## 1. Açılış / Problem (0:00 – 1:30)

> "1600 kVA'lık bir TEDAŞ AG panosunda cıvatalı bir bağlantı gevşer, direnci artar, ısınır.
> Bu haftalar sürebilir ve kimse görmez. Sonra kesinti olur, bazen yangın riski. PANO GÖZ bu
> sessiz süreci yakalamak için kuruldu."

- Sabit sıcaklık eşiği neden yetmez: yazın zaten sıcak olduğu için körleşir, kışın yanlış alarm
  üretir. Sayıyla: **sabit 75 °C eşiği "sıcak yaz" kontrolünde 10/10 yanlış alarm veriyor,
  düşük yükte gizli arızada 0/10 tespit** (`docs/09` §3.2).
- Çözüm tek cümle: **kardeş fazları birbirine göre karşılaştır, farkı yüke göre normalize et.**

## 2. θ metriği — ürün fikri (1:30 – 3:30)

```
θ = (T_faz − medyan(T_kardeş_fazlar)) / (I / I_anma)²        (ısıl gecikme telafili)
```

- Üç faz aynı ortamda, aynı yükle birlikte ısınır: ortak bileşen (yük + mevsim) medyanla iptal olur.
- Gevşek bağlantının **fazlar-arası fazladan ısınması** yükten bağımsız bir sabittir; θ onu tahmin eder.
- **Isıl gecikme telafisi:** yük hızlı değişirken ΔT henüz oturmamıştır; anlık I²'ye bölmek θ'yı
  şişirir. I², iletkenin ısıl modeliyle aynı süzgeçten geçirilir, τ veriden tahmin edilir
  (`docs/09` §4 madde 1–2; bu hata test sırasında bulundu ve düzeltildi).
- Düşük yükte (**< %40 anma**) θ hesaplanmaz: "bilgi yok" ile "arıza yok" karıştırılmaz.
- Eşikler UYARI/ALARM/KRİTİK = **15 / 30 / 60 K**; 3/5 debounce, %40 ölü bant. Yavaş kalıcı
  ısınma için günlük θ medyanı üzerinde **CUSUM**: ALARM kör bölgesinde (direnç artışı < ≈×1,8) UYARI verir.

## 3. Sayıyla doğruluk (3:30 – 5:30)

> "Bu bir saha doğrulaması değil, model içi öz-tutarlılık. Bunu biz söylüyoruz; jüri sormadan."

Kaynak: `docs/09-VERI-ANALIZI.md`, yeniden üret: `python -m tools.run_accuracy_matrix --seeds 10`.

- **22 senaryo × 10 tohum = 220 koşu.** 11 arıza + 1 yalnız-uyarı + 10 negatif kontrol.
- **110/110 tespit; ALARM-üstü yanlış alarm 0** (6599 pano-günü = 18,1 pano-yılı; %95 üst sınır
  **0,17 / pano-yılı**, "üçün kuralı").
- **Haber verme süresi bozulma hızına bağlı:** 8 haftalık yavaş gevşemede UYARI tehlikeden ≈15 gün,
  ALARM ≈3 gün önce. **Ani arızada ≈0**: hiçbir dedektör dakikalar içinde gelişen arızayı haftalar
  önce bilemez; ALARM yarım saat içinde gelir. "Haftalar önce" iddiası yalnız bozulma haftalar
  sürüyorsa geçerli, bunu fizik belirliyor.
- **Bilinen sınırlar (biz ölçtük):** ALARM kör bölgesi direnç artışı < ≈×1,8 (yalnız UYARI);
  sensör gürültüsü ×4'te 3/10 sağlıklı koşuda yanlış ALARM başlıyor, sahada ofset kalibrasyonu şart.
- **Adil kıyas:** ortama göre +45 K kuralı güçlü bir rakip; kademeli arızada bizden erken
  (5,84 gün vs. bizim ALARM 7,58). Bizim avantajımız kademelide **UYARI (3,0 gün)** ve **düşük
  yükte görünürlük**.

## 4. Canlı demo (5:30 – 10:30)

Tam akış 12 adım (`docs/08`); 5 dakikada şu 6'yı göster:

1. **Sıcak yaz (P14, adım 2):** üç faz birden ısınıyor; bağlantı sıcaklığı 80,8 °C'ye çıkıyor (10 saatlik
   örnekte 75 °C üstü) ama θ en çok 9,4 K (UYARI eşiği 15), hiçbir alarm yok. *(Gün 34,4 penceresinin
   14 günlük saatlik serisinden ölçüldü.)*
2. **Alarm (P01, adım 3–4):** Gün 34 00:45'te L2'de θ sıçradı → ALARM. Kanıt grafiği, **iş emri kartı**
   (24 saat içinde, planlı kesinti, 2 kişi, 6 adım, güvenlik uyarıları), bildirim geçmişi.
3. **Telefon + onay (adım 5–6):** kademeli eskalasyon (kademe 1→2→3), nöbet devri; **4 haneli belirteç
   yalnız mesajda**, kimlikli onay; onaylanınca tüm kademelere [ONAYLANDI].
4. **PD füzyonu (adım 8):** aynı büyüklükte iki PD: nemin desteklediği ALARM, kuru havada tek başına
   UYARI'da tavanlı, ekip sevk edilmiyor ("iki kanal ailesi şartı").
5. **SCADA (adım 10):** 32 register/pano, ICD v2.0, ekrandaki karşılığıyla; bağımsız Modbus istemcisi ve
   IEC 104 master'ı aynı değerleri okuyor, yazma reddediliyor (`scada-okuma.txt`).
6. **Fırtına (adım 11–12):** 8 panoda ortak olay; nöbetçi telefonu kilitlenmesin diye saatlik sınır,
   fazlası tek [ÖZET] mesajı.

*(Süre kısalırsa 3 ve 6'yı at; 1, 2 ve 4 kalır. Canlı akış bozulursa yedek GIF, bkz. `yedek-plan.md`.)*

## 5. Mimari, entegrasyon, donanım (10:30 – 13:00)

Akış: **uç düğüm → bus (MQTT / in-proc) → store (SQLite outbox) → dedektörler (θ/RLS, CUSUM, yük, nötr,
yoğuşma, PD, ark) → bastırma → onay → füzyon → alarm → [SCADA · bildirim · API/konsol/mobil]**.
Sıra sabit; her aşamanın gerekçesi saklanır.

Gerçek (kanıtı olan) entegrasyonlar:

| Parça | Ne doğrulandı | Kanıt |
| --- | --- | --- |
| MQTT bus + outbox | Bağlanma, yeniden bağlanma, broker süreç restart (farklı PID), outbox replay, duplicate düşürme; ayrı OS sürecindeki gerçek MQTT 3.1.1 broker'a karşı | `tests/test_bus_mqtt_e2e.py` (5 senaryo) |
| Modbus TCP slave | ICD v2.0: 32 register/pano, 200 pano; gerçek `pymodbus` istemcisi konsolla aynı değerleri okur, FC06/FC03/FC01 reddedilir; ICD dokümanı + CSV koddan ÜRETİLİR | `tests/test_icd.py`, `docs/PANOGOZ-ICD-v2.0.md` |
| IEC 60870-5-104 slave | APCI durum makinesi, genel tarama, kendiliğinden bildirim, saat senkronu, komut reddi; **bağımsız üçüncü taraf master (Fraunhofer `c104`)** ile doğrulandı | `tests/test_iec104.py` (30 test) |
| Alarm + eskalasyon | Aç/yükselt/temizle/onayla/7 gün otomatik kapan/sessize al; kademeli eskalasyon, 4 haneli belirteç, fırtına sınırı + özet, nöbet devri, teslimat hatasında kademe atlama | `tests/test_{alarm_lifecycle,escalation,gsm_modem}.py` (51 test) |
| Firmware | STM32WLE5CC için gerçek `arm-none-eabi-gcc` ile 3/3 kart link, **0 float komutu**; host'ta `--selftest` 0 hata | `docs/07-FIRMWARE.md` |
| Donanım | 3 KiCad şematiği ERC **0 hata**; 3 PCB gerçek footprint'lerle DRC **0 kısa devre/clearance/courtyard**; 3B render; ölçülü kabin-içi yerleşim (1600×1500×450 mm) | `docs/02`, `docs/03`, `hardware/` |
| Ölçek | Yalnız-θ yolu 250→500→1000 pano doğrusal (1000 panoda RSS 173 MB). Çok kanallı filo: ≈11 bin pano-örneği/sn toplu analiz, ≈170 bin/sn alarm motoru | `docs/06` §2, §3b |

## 6. Dürüst açık maddeler (13:00 – 14:30)

> "Şimdi jürinin sormadan önce kendimizin söylemesi gereken kısım."

- **Veri sentetik.** Organizatör yalnız L1 fazı CT akımı verdi (~1,5 gün); sıcaklık/nem, PD ve ark
  sekmeleri boştu. Onlar fizik modelimizden; dedektörleri **o modele** karşı sınadık. "%100 tespit" ve
  "0 yanlış alarm" bu yüzden kanıt değil, öz-tutarlılık (`docs/09` §0). Anlamlı olanlar: sabit eşiklerle
  kıyas, kör bölge ölçümü, parametre dayanıklılığı, test sırasında bulunan gerçek hatalar.
- **Gerçek bildirim kanalından mesaj:** Telegram ve on-prem GSM modem kanalları kodlu ve testli
  (sahte HTTP / sahte seri port ile). Bu kodla **gerçek bir Telegram/SMS gönderimi henüz yapılmadı**
  (K4 4.1 açık; `docs/12` §0). Arayüzdeki telefonlar bellek içi gösterimdir.
- **Mosquitto yerine `amqtt`:** bu makinede Windows UAC/admin kısıtı yüzünden Eclipse Mosquitto
  çalıştırılamadı (iki gerçek denemeyle doğrulandı); gerçek MQTT 3.1.1 protokolü konuşan ayrı-süreç
  `amqtt` kullanıldı. Ayrıca `bus/store` çalışan konsol boru hattına henüz **bağlı değil** (bileşen
  olarak testli).
- **Docker Compose yazıldı, çalıştırılmadı.** Yapılandırma, ACL anlamı ve gerçek mTLS el sıkışması
  doğrulandı; `docker compose up` bu makinede denenemedi (`docs/13` §0).
- **IEC 104'te TLS (IEC 62351-3) yok;** sahada farklı üretici master'larla denenmedi.
- **Ölçek:** 1000 panoluk **çok kanallı** yük testi yapılmadı; §5'teki 22 panolu ölçümden doğrusal
  ölçekleme kestirimi var (`docs/06` §3b).
- **Donanımda eksik:** yoğuşma dedektörü iç hava T/RH sensörü + duvar NTC'si varsayıyor, mevcut KiCad
  tasarımında yok (K1'e açık madde). PD indeksi tek skaler; HFCT analog ön ucunun gerçek davranışı
  buna dönüşmüyor. Firmware iskelet (θ sabit-nokta çekirdeği + MAX31855 çözücü), tam ürün değil.
  Fiziksel prototip yok (şartname de istemiyor). BOM/fiyat tazelenmedi.
- **Eşikler (15/30/60)** model tabanlı ilk plan değerleri; sahada gerçek veriyle ayarlanmalı.

## 7. Kapanış (14:30 – 15:00)

> "PANO GÖZ'ün iddiası büyük bir demo değil: ölçtüğümüzü ölçtüğümüz kadar söylüyoruz. Sabit
> eşiğin göremediği düşük yükteki gizli arızayı ve sıcak yazı doğru ayıran bir fikir, bunu
> sayıyla savunan bir matris, gerçek protokollerle çalışan bir SCADA katmanı ve alarm hijyeniyle
> nöbetçiyi yormayan bir bildirim hattı. Sıradaki adım gerçek pano verisiyle aynı matrisi tekrarlamak.
> Sorularınızı bekliyorum."

## 8. Slayt destesi

13 slayt. Artifact linki: https://claude.ai/artifact/K1jkB1boP5dvzKd1KtV7Kt (2026-09-20'de gerçek
verilerle yeniden kuruldu; θ/sıcaklık grafikleri çalışan sunucunun `/api/fleet/panels/<id>/series`
çıktısından, ekran görüntüleri `tools/record_demo.py` kaydından, 3B renderlar KiCad'den). Çevrimdışı
kopya: `sunum/slayt/index.html`. Slayt ↔ bölüm: 1–2 Problem, 3 θ, 4–7 Kanıt ve demo, 8 Doğruluk,
9–11 Mimari/SCADA/Donanım, 12 Dürüst açık maddeler, 13 Kapanış.
