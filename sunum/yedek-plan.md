# K4 · 4.5 Yedek Plan

> Canlı demo online bir yarışmada ağ/donanım riskiyle gelir. Her canlı adımın önceden
> kaydedilmiş/statik bir yedeği olmalı; hiçbiri "umarım çalışır"a bağlı kalmasın.
> **Son güncelleme: 2026-09-20.**

## Genel kural

Sunumdan **önce** (canlı demo başlamadan):
0. **Slayt çevrimdışı:** `sunum/slayt/index.html` (tarayıcıda aç; görseller `sunum/slayt/img/`, yazı tipi
   yoksa sistem yazı tipine düşer). Çevrimiçi sürüm: bağlantı `anlati-script.md` §8'de.
1. `docs/ekran-goruntuleri/panogoz-demo-walkthrough.gif` ve `01…12-*.png` açık bir görüntüleyicide
   hazır dursun. Hepsi çalışan sistemden `tools/record_demo.py` ile çekildi (elle çekim yok).
2. `docs/ekran-goruntuleri/scada-okuma.txt` (Modbus + IEC 104 okuması) hazır dursun.
3. Sunucu önceden başlatılıp ısıtılsın (≈15 sn): `python -m panogoz.run_local --port 8080
   --modbus-port 5020 --iec104-port 2404`. Sunumda ısınmayı bekleme.
4. 3 KiCad PDF + 3B render PNG'leri yerel diskte, internetsiz açılabilir (`hardware/kicad/*/export/`).
5. `python -m pytest -q` çıktısı (291 test, ~80 sn) sunumdan önce bir kez alınıp ekran görüntüsü kaydedilsin.

## Adım bazlı yedekler

| Canlı adım | Risk | Yedek |
| --- | --- | --- |
| Konsol (`run_local`) açılmıyor | Port çakışması, firewall, ısınma bitmedi | `--port` değiştir (8090); olmazsa GIF + PNG'ler (adım ↔ görüntü tablosu: `docs/08` §2). |
| Saat/demo düğmeleri tepki vermiyor | Sunucu takıldı | **Sıfırla**; olmazsa sunucuyu yeniden başlat (Windows'ta `pkill` yok: PowerShell `Get-CimInstance`+`Stop-Process`). Yedek: ilgili PNG. |
| Adım 2 (sıcak yaz) | Doğru güne atlanmadı | *Gün 34'e atla*, P14'e tıkla; yedek `02-sicak-yaz-normal.png`. |
| Adım 8 (PD füzyonu) | 12 sa/sn ile fazla ilerledi | **Sıfırla** → *Gün 52'ye atla* → ~5 sn → Duraklat; yedek `08-pd-fuzyon.png`. |
| Adım 10 (SCADA) canlı Modbus/IEC 104 istemcisi | Port/ağ, ikinci terminal | Konsolun SCADA sekmesi (ekran) + `scada-okuma.txt` (aynı anın gerçek okuması). Register haritası: `docs/PANOGOZ-ICD-v2.0.md`. |
| Adım 7 mobil/QR | Telefon aynı ağda değil | Dar tarayıcı penceresinde `saha.html?panel=P01`; yedek `07-mobil-saha.png`. |
| Gerçek Telegram/SMS gönderimi (yapılırsa) | Token/ağ, gecikme; **jüri önünde dış kanala mesaj öngörülemez** | Gerçek gönderim 2026-09-20'de yapıldı (tek yönlü, `sendMessage` HTTP 2xx, telefona ulaştığı teyit edildi); yedek kanıt olarak Telegram sohbetinin telefon ekran görüntüsü `docs/ekran-goruntuleri/`'ne konmalı. Canlı gönderim yalnız açıkça planlandıysa; yoksa Bildirimler sekmesi (bellek içi gösterim) ve anlatıda "iki yönlü ONAY gerçek Telegram'da doğrulanmadı" denir. Doğaçlama gönderim yapılmaz. |
| Gerçek MQTT E2E'yi canlı çalıştırma | ~13 sn, süreç/port çakışması | Önceden alınmış `pytest -v` çıktısı (`docs/01-MIMARI.md` §5'te ham çıktı var). |
| KiCad 3B render canlı açma | Jüri makinesinde KiCad yok | Statik PNG/PDF/SVG'ler (`hardware/kicad/*/export/`). |

## Zaman aşımı planı (15 dk yerine 10 dk verilirse)

Atlama sırası (önce bunlar):
1. §5 mimari/donanım bölümünü 3 cümleye indir: "3 kart, ERC+DRC temiz, firmware gerçek hedefte
   derleniyor, fiziksel prototip yok/istenmiyor."
2. Canlı demoyu 3 adıma indir: **sıcak yaz (2)**, **alarm + iş emri + onay (3–6)**, **PD füzyonu (8)**.
   Fırtına ve SCADA yalnız görüntüyle.
3. **Asla atlanmayacaklar:** θ'nın ne olduğu (ürünün kalbi), §3 doğruluk sayıları "öz-tutarlılık"
   çerçevesiyle ve §6 dürüst açık maddeler (jüri sormadan söylemek güven kurar).

## Soru anında donarsan

- "Bu konuda şu an elimde doğrulanmış bir veri yok, tahmin etmek istemiyorum." CLAUDE.md ilkesi:
  yapılmayan hiçbir şey yapılmış gibi yazılmaz.
- Kartlar tükenirse güvenli dönüş: "Şu an [X] doğrulanmadı, roadmap'te [Y] altında."
