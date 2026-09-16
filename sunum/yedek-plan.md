# K4 · 4.5 Yedek Plan

> Canlı demo bir online yarışmada ağ/donanım riskiyle geliyor. Her canlı adımın
> önceden kaydedilmiş/statik bir yedeği olmalı — hiçbiri "umarım çalışır"a
> bağlı kalmasın.

## Genel kural

Sunumdan **önce** (canlı demo başlamadan):
1. `docs/ekran-goruntuleri/panogoz-demo-walkthrough.gif` açık bir sekmede/
   görüntüleyicide hazır dursun (gerçek, önceden kaydedilmiş çalışma kaydı).
2. 3 KiCad PDF + 3D render PNG'leri yerel diskte, internetsiz açılabilir
   şekilde hazır olsun (`hardware/kicad/*/export/`).
3. `python -m pytest -q` çıktısının bir ekran görüntüsü/kaydı alınsın (26/26
   yeşil) — canlı çalıştırma başarısız olursa bu gösterilir.

## Adım bazlı yedekler

| Canlı adım | Risk | Yedek |
| --- | --- | --- |
| Monitoring konsolu (`python -m panogoz.api.app`) | Port çakışması, ağ/firewall, Flask başlamama | `panogoz-demo-walkthrough.gif` — aynı iki bağlantıyı (F01 sağlıklı, F02 kritik) ve zaman kaydırmayı gösteriyor, gerçek kayıt. |
| Gerçek Telegram mesajı gönderimi | Bot token/ağ sorunu, mesaj geç gelebilir, **jüri önünde gerçek bir dış kanala mesaj atmak öngörülemez bir zamanlama riski taşır** | Önceki oturumdan gerçek gönderim kanıtı (kod + `panogoz/notify/telegram_channel.py` + proje notlarındaki doğrulama) anlatılır; canlı gönderim yalnızca zaman/ortam uygunsa ve **açıkça planlanmışsa** yapılır — anlık doğaçlama gönderim yapılmaz. |
| Gerçek Modbus client bağlantısı (`tools/run_modbus_server.py`) | Port/ağ, iki terminal senkronizasyonu | Register haritası tablosu (`docs/modbus-haritalama.md`) + önceden alınmış bir client çıktısı ekran görüntüsü gösterilir. |
| Gerçek MQTT E2E testi canlı çalıştırma | ~13 saniye sürüyor ama process/port çakışması olabilirse | Önceden alınmış `pytest -v` çıktısı (bu oturumda doğrulandı, `docs/01-MIMARI.md` §5'te ham çıktı zaten var) okunur/gösterilir. |
| KiCad 3D render canlı KiCad GUI'sinde açma | KiCad kurulum/lisans/performans riski, jüri makinesinde KiCad olmayabilir | Statik PNG render'lar (`hardware/kicad/*/export/*-3d.png`) ve PDF'ler — zaten "bitti sayılır" kriterinin kendisi bu dosyalar. |

## Zaman aşımı planı (15 dk yerine 10 dk verilirse)

Kısaltma sırası (önce bunlar atlanır, en son bunlar kalır):
1. §5 Donanım bölümünü (anlati-script.md) 3 cümleye indir: "3 kart, ERC+DRC
   temiz, fiziksel prototip yok/istenmiyor."
2. Canlı Modbus/MQTT gösterimini atla, yalnızca "gerçek broker'a karşı 5/5
   test geçti" diye söyle.
3. **Asla atlanmayacak iki şey:** θ metriğinin ne olduğu (ürünün kalbi) ve
   §6'daki dürüst açık maddeler (jüri bunu sormadan söylemek güven inşa
   ediyor).

## Soru anında donarsan

- Bilmediğin bir şey sorulursa: "Bu konuda şu an elimde doğrulanmış bir veri
  yok, tahmin etmek istemiyorum" de — CLAUDE.md'nin kendi ilkesi de bu
  ("yapılmayan hiçbir şey yapılmış gibi yazılmaz").
- `juri-qa-kartlari.md`'deki kartlar tükenirse, en güvenli dönüş cümlesi:
  "Şu an [X] doğrulanmadı, roadmap'te [Y] maddesi altında."
