# 08 · Demo Senaryosu (K3 3.6)

> Jüri önünde ~10–12 dakikalık canlı akış. **Her adımın ekran görüntüsü, çalışan sistemden
> otomatik çekildi** (`python -m tools.record_demo`, gerçek Edge + gerçek sunucu); elle
> çekilmiş veya düzenlenmiş görüntü yok. Adım ↔ görüntü eşlemesi §2'de birebirdir.
>
> Veri **simülasyondur** (22 senaryolu pano filosu, gerçek CT yük biçimi + fizik tabanlı
> sentetik kanallar, bkz. [09-VERI-ANALIZI.md](09-VERI-ANALIZI.md) §0); saha doğrulaması değildir.
> Arayüzün altbilgisi de bunu her ekranda söyler.

## 0. Hazırlık

```
python -m panogoz.run_local --port 8080 --modbus-port 5020 --iec104-port 2404
```

Filo ≈15 sn ısınır, konsol "hazırlanıyor" gösterir. Tarayıcıda `http://127.0.0.1:8080`.
Her şey **fareyle** yönetilir (klavye gerekmez): üst şeritteki *Başlat/Duraklat*, hız
menüsü, *Güne atla…*, senaryo + *Enjekte et / Temizle*, *Fırtına başlat*, *Sıfırla*.
Demo her zaman **Gün 30**'da başlar; *Sıfırla* buraya döner.

Telefon gösterimi için ikinci bir pencere/telefon: `http://<sunucu-IP>:8080/saha.html`
(QR, adım 7). Bildirimler sekmesindeki telefonlar **bellek içi gösterimdir**; gerçek
Telegram/SMS yalnız `PANOGOZ_LIVE_NOTIFY=1` + kanal kimlik bilgileriyle açılır
([12-BILDIRIM-ESKALASYON.md](12-BILDIRIM-ESKALASYON.md)).

## 1. Akış

| # | Süre | Ne yapılır (fare) | Ne söylenir | Görüntü |
| --- | --- | --- | --- | --- |
| 1 | 0:00 | **Panolar** sekmesi. Sıfırla → Gün 30. | "22 panoluk filo, hepsi NORMAL, aktif alarm yok. Her kartta akım, bağlantı sıcaklığı, nem." | `01-normal-filo.png` |
| 2 | 1:00 | *Güne atla → Gün 34* (duraklı). **P14** kartına tıkla. | "P14'te ortam çok sıcak, üç faz birden ısınıyor: bağlantı sıcaklığı 80,8 °C'ye çıkıyor, 10 saatlik örnekte 75 °C'nin üstünde. Sabit 75 °C eşiği bu kontrol koşusunda 10/10 yanlış alarm verir (docs/09 §3.2). θ ise kardeş fazların farkına baktığı için düz kalır (en çok 9,4 K, UYARI eşiği 15), izlerin hepsi NORMAL." *(Rakamlar Gün 34,4 penceresinin 14 günlük saatlik serisinden; `/api/fleet/panels/P14/series`.)* | `02-sicak-yaz-normal.png` |
| 3 | 2:30 | **Başlat** (1 sa/sn) ~3 sn → **Duraklat**. **Alarmlar** sekmesi. | "Gün 34, 00:45'te P01'in L2 fazında θ sıçradı: ALARM açıldı, onay bekliyor. KPI şeridi: 1 ALARM, 1 onay bekleyen, filoda 1/22 pano ALARM+." | `03-alarm-acildi.png` |
| 4 | 3:30 | Alarm satırına tıkla. | "Kanıt: θ grafiği, ALARM 30 K / UYARI 15 K eşikleri, açılış çizgisi. İş emri kartı: 24 saat içinde, planlı kesinti gerekir, 2 kişilik bakım ekibi, 2–4 saat, 6 adım ve güvenlik uyarıları. Altta bildirim geçmişi." | `04-alarm-detay.png` |
| 5 | 5:00 | **Bildirimler** sekmesi. | "Nöbetçilerin telefonları: 00:45 ilk bildirim (kademe 1), 01:00 hatırlatma, onaylanmayınca 01:15'te kademe 2, 01:45'te kademe 3'e eskalasyon; 08:00'de nöbet devri yeni nöbetçileri arıyor. Onay belirteci **konsolda görünmez**, yalnız mesajdadır." | `05-telefon.png` |
| 6 | 6:00 | Telefondaki **Onay için doldur** → **Onayla**. | "4 haneli belirteç ve kimlik olmadan onay kabul edilmez. Onaylayan Kemal D. görünür; tüm kademelere [ONAYLANDI] gider; şiddet yükselirse onay geçersiz olur ve yeniden sevk edilir." | `06-onay.png` |
| 7 | 7:00 | Telefonda / dar pencerede `saha.html?panel=P01` (veya QR'ı okut). | "Sahadaki teknisyen panonun kapağındaki QR'ı okutur: tek pano, konum, aktif alarm ve iş emri, mobilden onay. 400 px'te yatay kaydırma yok." | `07-mobil-saha.png` |
| 8 | 8:00 | **Sıfırla** → *Gün 52'ye atla* → **Başlat** (12 sa/sn) ~5 sn → **Duraklat**. Alarmlar → Aile: **PD**. | "İki PD alarmı var. P09'da nem de yüksek: ikinci kanal ailesi destekliyor, ALARM. P12'de kuru hava, PD tek başına: aynı büyüklükte ama füzyon UYARI'da tavanlıyor, ekip sevk edilmiyor." | `08-pd-fuzyon.png` |
| 9 | 9:00 | **Bastırma** sekmesi. | "Sıra sabit: bastırma → onay → füzyon. Bilgi yokken alarm üretmiyoruz ve nedenini sayıyoruz: P20 haberleşme kaybı (veri yok), P19 bakım kesintisi (enerjisiz), P04 düşük yük, P09/P12 PD tavanlama." | `09-bastirma.png` |
| 10 | 10:00 | **SCADA (Modbus)** sekmesi. | "32 register/pano, ICD v2.0, yalnız okuma. Her register'ın konsoldaki karşılığı yanında. Aynı değerleri bağımsız bir Modbus istemcisi ve bir IEC 104 master'ı da okuyor, yazma reddediliyor." | `10-scada.png` + `scada-okuma.txt` |
| 11 | 11:00 | **Sıfırla** (Gün 30) → **Fırtına başlat** → **Başlat** (1 sa/sn) ~1 sn → **Duraklat**. Alarmlar sekmesi. | "8 panoda aynı anda ortak neden: alarm fırtınası. Nöbetçi telefon kilitlenmesin diye alıcı başına saatlik sınır var; bant yalnız olayın ilk saatinde görünür." | `11-firtina.png` |
| 12 | 11:45 | **Başlat** ~3 sn daha → **Duraklat**. **Bildirimler** sekmesi. | "İlk iki mesaj gitti, kalanı 'fırtına sınırı' olarak kaydedildi; saatlik pencere açılınca tek bir [ÖZET] mesajına döndü: 'N bildirim bastırıldı'." | `12-firtina-telefon.png` |

`panogoz-demo-walkthrough.gif`: 9 kare (adım 3–8 ve 10–12), sunumda yedek olarak hazır.

**Ekran kaydı:** `panogoz-demo-video.webm` (≈88 sn, 1280×720, `python -m tools.record_video`). Adım 1–6 ve 8–12'yi
yalnız arayüzün kendi düğmeleriyle yürütür (Sıfırla, *Güne atla*, Başlat/Duraklat, hız, sekmeler, filtre, *Onay için
doldur*, *Onayla*, *Fırtına başlat*); ekrana adım başlığı ve imleç noktası bindirilir. Adım 7 (mobil/QR) ayrı bir
cihaz olduğundan videoda yok, `07-mobil-saha.png`'ye bakın.

## 2. Ekran görüntüsü ↔ adım ↔ ne kanıtlıyor

| Görüntü | Adım | Sistemde ne gerçek | Nereden bakılır |
| --- | --- | --- | --- |
| `01-normal-filo.png` | 1 | 22 pano, 0 alarm, gerçek CT yük biçimi | `panogoz/api/fleet_service.py` |
| `02-sicak-yaz-normal.png` | 2 | 7 kanal grafiği + 15 iz; θ kardeş medyanına göre, sıcak yazda düz | [04](04-ANOMALI-TESPIT.md), [09](09-VERI-ANALIZI.md) §3.2 |
| `03-alarm-acildi.png` | 3 | Alarm yaşam döngüsü, KPI şeridi | `panogoz/rules/alarms.py` |
| `04-alarm-detay.png` | 4 | Kanıt grafiği, iş emri kartı, bildirim geçmişi | `panogoz/rules/workorders.py` |
| `05-telefon.png` | 5 | Kademeli eskalasyon, hatırlatma, nöbet devri | [12](12-BILDIRIM-ESKALASYON.md), `panogoz/notify/escalation.py` |
| `06-onay.png` | 6 | Kimlikli + belirteçli onay, [ONAYLANDI] yayını | `tests/test_alarm_lifecycle.py` |
| `07-mobil-saha.png` | 7 | 400 px'te `scrollWidth ≤ 400` (betik doğrular; kayıtta 400), QR | `frontend/saha.*`, `tests/test_ui_e2e.py` |
| `08-pd-fuzyon.png` | 8 | İki kanal ailesi şartı: PD tek başına UYARI'da tavanlı | `panogoz/rules/pipeline.py` |
| `09-bastirma.png` | 9 | STALE / ENERJİSİZ / DÜŞÜK YÜK / PD tavanlama sayaçları | `panogoz/rules/pipeline.py` |
| `10-scada.png` | 10 | 32 register, ham/hex/çözülmüş + konsol eşlemesi | [PANOGOZ-ICD-v2.0.md](PANOGOZ-ICD-v2.0.md) |
| `scada-okuma.txt` | 10 | pymodbus FC04 okuması + FC06 yazma reddi + c104 GI; değerler `10-scada.png` ile aynı (θ 451 = 45,10 K, L2 125,2 A, 68,0 °C, %32,7 RH) | `tools/record_demo.py` |
| `11-firtina.png` | 11 | Fırtına bandı, KPI'da "fırtına sınırı" sayacı | `panogoz/notify/escalation.py` |
| `12-firtina-telefon.png` | 12 | Sınırlanan mesajlar + tek [ÖZET] | `tests/test_escalation.py` |

## 3. Yeniden üretme

```
python -m panogoz.run_local --port 8090 --modbus-port 5030 --iec104-port 2414
python -m tools.record_demo --base http://127.0.0.1:8090 --modbus-port 5030 --iec104-port 2414
```

Önkoşul: `pip install playwright pillow`, Edge kurulu (`--browser chromium` alternatif). Video için ayrıca
`python -m playwright install ffmpeg` (kullanıcı dizinine iner, yönetici izni gerekmez) ve `python -m tools.record_video`.
Betik hata verirse **sessizce geçmez**: 07'de P01'de gerçek alarm yoksa, 12'de [ÖZET] yoksa,
mobilde yatay kaydırma varsa veya SCADA okuması (Modbus/IEC 104) başarısızsa çöker.

## 4. Dürüstlük notları

- **Ara günler:** görüntüler saat ucuna (`/api/sim/clock`, arayüzdeki düğmelerin çağırdığı
  aynı uç) ara günlerle atlanarak çekildi (ör. Gün 34,4 = 09:30). Arayüzün *Güne atla*
  menüsü yalnız 34/38/42/46/52 sunar. §1'deki fare yolları (Gün 34 → Başlat ~3 sn; Gün 52 →
  12 sa/sn ~5 sn; Sıfırla → Fırtına başlat → Başlat 1 sa/sn) ayrıca denendi: P01-0001 ALARM,
  P09 ALARM + P12 UYARI ve 8 panolu fırtına + [ÖZET] aynı şekilde oluştu. Belirteç ve
  [ÖZET] içindeki bastırılan sayısı çalıştırmaya/saate göre değişir (kayıtta belirteç 6276, N=10).
- **Fare yolu uçtan uca sınandı:** `panogoz-demo-video.webm` API'ye hiç dokunmadan yalnız arayüz düğmeleriyle
  adım 1–6 ve 8–12'yi yürüttü (betik `wait_for_*` koşullarıyla doğrular, koşul sağlanmazsa çöker).
- **Bildirimler bellek içi gösterimdir**; telefon kartları gerçek bir kanaldan gelmiyor.
- **Sabit eşik kıyası (adım 2)** model içi öz-tutarlılıktır (docs/09 §0): rakip eşik ve
  sağlıklı davranış aynı simülatörde. "Yanlış alarm" savı buna göre okunmalı.
- **IEC 104 okuması** Playwright'ın olay döngüsü içinde el sıkışamadığı için betikte ayrı
  bir alt süreçte yapılır; sunucu tarafında sorun yoktur (bağımsız c104 master ile ayrıca
  doğrulandı, `tests/test_iec104.py`).
