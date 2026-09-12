# Yedek Plan — Demo Çökerse (K4 §4.5)

Görev dağılımı belgesi §6 riskini doğrudan kapatır: "Demo makinede canlı
sistem çöker → önceden çekilmiş demo videosu hazır olacak."

## Kurallar

1. Final provadan (G+7) önce, çalışan sistemin ekran kaydı alınır — canlı
   demoyla birebir aynı senaryo sırasıyla (bkz. `sunum/15-dakika-anlati.md`).
2. Video, sunum bilgisayarında **çevrimdışı** oynatılabilir halde tutulur
   (internet/Telegram bağlantısı gerektirmez).
3. Sunumu yapan kişi, canlı demo 30 saniye içinde beklenen ekrana gelmezse
   videoya geçer; bunu jüriye açıkça söyler ("canlı bağlantı yerine
   kaydımızı izleyelim") — gizlemeye çalışmak güven kaybettirir.
4. Video en az şunları içerir: normal senaryo (alarm yok), bir alarm senaryosu
   tetiklenmesi, Telegram'a düşen gerçek bildirim, doğruluk raporu ekranı.

## Bugün (K4) hazır olan çevrimdışı kanıtlar

Bunların hiçbiri canlı bağlantı gerektirmez, sunum makinesinde yerel olarak
çalıştırılabilir:

- `python -m pytest -q` çıktısı (45/45 yeşil) — ekran görüntüsü alınıp
  slayta gömülsün.
- `reports/dogruluk-raporu.md` ve `reports/duyarlilik-egrisi.png` — statik
  dosyalar, internet gerektirmez.
- Telegram mesajının ekran görüntüsü (gerçek gönderim bir kez yapılıp kayıt
  altına alınmalı; canlı gönderim sunum sırasında ağ bağımlı olduğu için
  riskli).

## Kontrol listesi (sunumdan 1 gün önce)

- [ ] Video, sunum makinesine kopyalandı (bulut linkine değil, yerel diske).
- [ ] `reports/` klasörü güncel senaryo sonuçlarıyla yeniden üretildi.
- [ ] Telegram bot token'ı süresi dolmamış / bot hâlâ yanıt veriyor.
- [ ] Sunum yapan kişi videoyu tek başına, klavye/fare karışıklığı olmadan
      başlatabiliyor.
