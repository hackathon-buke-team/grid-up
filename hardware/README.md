# K1 / B1 tasarım teslimi

20.09.2026. `k1-b1-tasarim-firmware` dalı; başlangıç: `74490f50`.
Bu klasör repodaki STM32/LoRa mimarisine göre oluşturulmuştur. Önceki bağımsız ESP32 RevA paketi bu teslimin kaynağı değildir.

## Önce açılacak dosyalar

- [Tasarım ve ölçülendirilmiş montaj dosyası](B1/K1-B1-TASARIM-DOSYASI.pdf): verilen 1600 kVA çizimi üzerinde montaj, kutular, kablo yolları ve sınırlar.
- [TC şematiği](B1/TC/schematic.pdf), [IR şematiği](B1/IR/schematic.pdf), [PD şematiği](B1/PD/schematic.pdf), [GW şematiği](B1/GW/schematic.pdf).
- [BOM ve güncel fiyat kaynakları](B1/BOM.md), [satır bazında teklif/alternatif/termin](B1/bom.json).
- [Doğrulama raporları](B1/verification.json), [firmware hedef portu](../firmware/node/port/stm32wle5/README.md).

Her `B1/TC`, `IR`, `PD`, `GW` klasöründeki `PANOGOZ-*-B1.kicad_pro` dosyası **KiCad 10** ile açılır. Şematik sayfaları, PCB, yerel semboller, modeller, `pinmap.csv`, `circuit.json`, `pcb-top.png`, `pcb-bottom.png`, `pcb-3d.png` aynı dizindedir. `mechanical/*/assembly.step`, `base.step`, `lid.step` STEP uyumlu CAD yazılımlarında düzenlenebilir; parametrik kaynak `tools/mechanical.py` dosyasıdır.

## Kabul matrisi

| K1 | Yapılan / kanıt | Durum |
|---|---|---|
| 1.1 | Dört fiziksel kartın elektriksel bağlantılı şematiği; PDF; ERC 0 hata/0 uyarı; BOM/pinmap manifestten üretilir | Tasarım aşaması tamam |
| 1.2 | Boyut, dört katman, konnektörler, keepout, üst/alt/3B PNG; yerleşim DRC 0; şematik-PCB farkı 0 | Yerleşim tamam; bakır yönlendirme yapılmadı |
| 1.3 | Orijinal pano çizimi üstüne montaj, ölçülü ön görünüş, derinlik kademesi, kablo/erişim, kutu STEP dosyaları | Konsept çizimleri tamam; saha ölçümü yapılmadı |
| 1.4 | Gerçek Cortex-M4 ELF/BIN/MAP; ST HAL/CMSIS; uyarısız derleme ve host öz testi | TC hedefi tamam; fiziksel çalıştırma yok |
| 1.5 | Çevre/koruma önlemlerinin bileşen ve yerleşim karşılıkları docs/03 içinde | Tasarım karşılıkları yazılı; test/sertifika yok |
| 1.6 | 214 BOM satırı; 15 parça tipinin 19 satırda gözlenen USD fiyatları; ref bazlı tedarik açıkları ve yeniden üretilen maliyet hesabı | **Kısmen**: 195 satırda fiyat eksik; kesin MPN/teslim teyitleri açık |
| 1.7 | İsteğe bağlı gerçek sensör demosu | Donanım satın alınmadı; uygulanmadı |

Görev belgesi “TC, IR/PD, GW” olarak üç işlev grubu sayar. Mevcut repo IR ve PD'yi iki farklı pil düğümü olarak tanımlar; bu nedenle dört kart tipi, **6 TC + 1 IR + 1 PD + 1 GW = 9 cihaz** korunur. `panogoz/contracts/` değişmedi. K1 uyum düzeltmesi; gateway'de kalıcı düğüm kabulü, simülasyonda B1 optik/pil sınırları, API/arayüzde kapsam ve ölçümsüz bağlantının tahmin gerekçesini kapsar. Bu ortak dosyalar ekip birleştirmesinde gözden geçirilmelidir.

## B1 yazılım uyumu

Varsayılan dijital ikiz 6 TC noktasından bağımsız sıcaklık/akım üretir. 38 mm/piksel ve 20 mm pabuç adımı nedeniyle kalibre edilmiş tekil IR ROI listesi boştur; 34 diğer nokta için sahte IR sıcaklığı verilmez. Fizik modeli 40 bağlantının gerçeğini ayrı tutar. `ideal_ir=True` yalnız açıkça seçilen çevrimdışı sensör deneyidir; çalışan filo bunu kullanmaz. Eski pil ve geri ödeme iddiaları kaldırılmıştır. Radyo zarfı kalıcı gateway kuyruğuna bağlanmıştır; fiziksel alıcı sürücüsü hâlâ açık iştir.

[Güncel maliyet](../docs/07-MALIYET-FAYDA.md), [tedarik açıkları](B1/TEDARIK-ACIKLARI.md), [maliyet çıktısı](B1/cost-summary.json). Eski demo veritabanı ideal IR geçmişi içerebilir; B1 demosu yeni bir `PANOGOZ_DB` dosyasıyla başlatılmalıdır, eski veri silinmez.

## Dijital ikizde K1 çizimleri

Pano ekranındaki bir cihaza veya **Kart ve kutu çizimlerini aç** düğmesine basın. TC-01–TC-06 aynı TC kartına; TN-IR, PD-01 ve GW-01 kendi B1 tasarımlarına bağlanır. Galeride mekanik kutu modeli, PCB 3B/üst/alt görünümleri, şematik PDF, STEP ve KiCad PCB bağlantıları bulunur. Pano montaj PDF'si de buradan açılır. Önizlemeler mevcut CAD çıktılarıdır; etkileşimli 3B döndürme yoktur, STEP dosyası CAD yazılımında açılabilir.

Pano çizimindeki cihaz kutuları `mechanical/dimensions.json` nominal ölçülerini kullanır. İçlerindeki izometrik görsel ön görünüş ölçülendirmesi değildir; gerçek pano açıklıkları ve montaj hâlâ fiziksel doğrulama gerektirir. Canlı ölçümler ve bağlantı tıklamaları korunur.

Sunucu `/api/panel/{key}/twin` yanıtında cihaz–tasarım eşlemesini ve `design_catalog` alanını verir; `/api/hardware/B1/` yalnız 29 açıkça listelenmiş teslim dosyasını sunar. Başka donanım dosyaları servis edilmez. Ekip güncellemesinde API, arayüz ve `hardware/B1/` birlikte alınmalı ve sunucu yeniden başlatılmalıdır. Ek program kurulumu gerekmez.

## Testlerin anlamı

KiCad ERC elektriksel pin/ağ tutarlılığını kontrol eder; analog doğruluk, RF uyumu veya doğru firmware pin-mux seçimini tek başına kanıtlamaz. Pin-mux kontrolü üretici tablolarına göre ayrıca yapılmıştır. Yerleşim DRC ihlali 0 olmakla birlikte TC/IR/PD/GW için sırasıyla **167/162/253/396 yönlendirilmemiş bağlantı** vardır. Bu paket bir Gerber/üretim sürümü değildir. DRC bulguları gizlenmedi; raporların `unconnected_items` alanları teslim edilir.

Repo testleri ve host/ARM çıktıları `B1/evidence/` altında saklanır. B1 uyum güncellemesinin sonuçları [uyum doğrulamasında](B1/UYUM-DOGRULAMA.md) bulunur. Tam repo testi temiz değildir: sağlıklı bağlantıya 90 gün altında IZLE tarihi veren negatif kontrol hataları vardır; `trafo_devreye_alma` hatası değişmemiş ana sürümde de yeniden üretildi. Alarm/tahmin eşikleri ve negatif kontrol testleri değiştirilmedi. Ölçüm almayan bağlantıların boş tahmin gerekçesi düzeltildi. Önceki başarılı koşu bu açık hataları ortadan kaldırmaz.

## Üretim öncesi açık işler

RF eşleme değerleri başlangıç değerleridir; QFN/868 MHz için son PCB üzerinde VNA/iletim testi gerekir. Analog koruma, CT/HFCT transferi, pil/HLC tepe akımı, kutu sızdırmazlığı/mandalı, termal temas, IR piksel ayrımı ve gerçek pano açıklıkları ölçülmedi. IR/PD hedef sensör portları, H563 GW MCU yazılımı ve fiziksel radyo alıcısı henüz yok. Yazılım radyo zarfı → kalıcı gateway kuyruğu → QoS1/PUBACK yolu testlidir. TC hedefinde imzalı bootloader olmadığı için OTA kapalıdır.

## Yeniden üretim

```powershell
# KiCad Python; KICAD_SHARE gerekirse kurulum dizinine ayarlanır
& '<KiCad>/bin/python.exe' hardware/tools/generate.py
python hardware/tools/export.py # KICAD_CLI ile CLI yolu seçilebilir
python hardware/tools/bom.py
python hardware/tools/costs.py
# CadQuery 2.6 + matplotlib bulunan Python
python hardware/tools/mechanical.py
# ReportLab; fontlar Windows Arial
python hardware/tools/report.py
python firmware/node/build_target.py --toolchain '<ARM GCC>/bin' --node 4
python -m pytest -q
```

Model ve PDF dışa aktarımlarında KiCad'in normal kullanıcı önbelleğine yazabilmesi gerekir. İlk CAD üretiminden önce `mechanical.py` özel GW model zarflarını üretir; sonrasında `generate.py → export.py → bom.py → report.py` sırası kullanılır. Şematikteki fiziksel pinler kaynak manifestte tanımlıdır; elle CAD düzenlenecekse `generate.py` yeniden çalıştırmak bu düzenlemeleri üzerine yazar.

Standart sembol/ayak izi/3B modeller KiCad kütüphanelerinden alınmıştır (CC BY-SA 4.0 ve KiCad library exception); özel E22/TE geometrileri üretici ölçülerinden türetilmiş yaklaşık modellerdir. QFN gövde önizlemesinde 5,15 mm EP modeli kullanılabilir, elektriksel footprint EP ölçüsü 5,6 mm kalır. `model_report.json` eksik/temsili modelleri belirtir. ST/CMSIS yazılımlarının ayrı lisansları vendor dizininde korunur.
