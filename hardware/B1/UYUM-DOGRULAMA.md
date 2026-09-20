# B1 / K1 uyum güncellemesi

20.09.2026 · `k1-b1-tasarim-firmware` · ana repo başlangıcı `74490f50a9def25faceb0655f27244f911683e74`.

## Değişiklikler

- BOM: 214 satın alma satırının 19'unda (15 parça tipi) kaynaklı USD liste fiyatı; 195 satır açık. 260,09 USD yalnız fiyatı bilinen parçaların ara toplamıdır. `TEDARIK-ACIKLARI.md` eksik MPN/fiyat/termin işlerini listeler. Teklif talebi gönderilmedi.
- Maliyet: `hardware/tools/costs.py`, BOM'dan maliyeti yeniden üretir. Eksik fiyat sıfır sayılmaz; tam kit, TCO ve geri ödeme sonuçları bilinmeyen olarak tutulur. Beş yılda varsayımsal iki TC pil değişimi (12 yedek hücre) hesaba girer; IR/PD bakım bütçesi açıktır.
- Enerji: TC simülasyonu 721 gün hesabına bağlandı; eski 9–16 yıl iddiası kaldırıldı. IR/PD için uydurulmuş kalan pil yüzdesi yoktur. Bu süre ölçülmüş ömür değildir.
- Optik: yaklaşık 38 mm/piksel, 20 mm pabuç adımını bağımsız çözmez. Varsayılan ikiz altı TC sıcaklık/akım noktasını üretir; 40 noktanın fiziksel gerçeği ayrı tutulur. `ideal_ir=True` yalnız açıkça seçilen çevrimdışı deneye aittir. Arayüz/API bu kapsamı gösterir.
- Radyo: `forward()` doğrulanmış C çerçevesini mevcut gateway'in SQLite kuyruğuna aktarır. Seq/boot/cadence korunur; yeniden başlatmada sıra kurtarılır, PUBACK gelmeden kayıt silinmez. Tam/bozuk kuyrukta veya CRC hatasında alıcı ACK vermemelidir. Fiziksel radyo alıcısı/sürücüsü teslim edilmedi.
- Veri yokluğu: ölçüm almayan bağlantının tahmin gerekçesi `YETERSIZ_GECMIS`; boş ve geçerliymiş gibi görünen ETA kaldırıldı. Ölçümü olmayan satırlar en yüksek sıcaklık farkı listesine girmez.

## Test sonucu ve sınırı

| Kontrol | Sonuç |
|---|---|
| Firmware/radyo/B1 kapsamı/maliyet/API ve simülasyon kabul testleri | **74 geçti**, 27,33 s |
| Tam repo testi (son iki küçük regresyon testi eklenmeden önce) | **188 geçti, 4 başarısız**, 1 kullanımdan kaldırma uyarısı; 141,97 s |
| Değişmemiş ana repo karşılaştırması | `trafo_devreye_alma` aynı C07-L3/IZLE sorunu ile başarısız; 90 gün |
| Canlı B1 API ve tarayıcı | 6 TC, 9 cihaz; doğrulanmış IR kapsamı boş; IR/PD pil yüzdesi belirsiz; örnek gevşek bağlantı alarmı var |
| Tasarım PDF'si | Güncellenen kanıt/maliyet/kapsam sayfası görüntü olarak kontrol edildi |
| Ortak `panogoz/contracts/` | Değişmedi |
| ARM derlemesi / KiCad | Önceki doğrulanmış kaynak ve çıktılar değişmedi; bu güncellemede yeniden tasarım/derleme yapılmadı |

Tam koşunun başarısız senaryoları: `dugum_sessiz`, `sicak_hava_dalgasi`, `sebeke_olayi`, `trafo_devreye_alma`. Alarm açılmadı; sağlıklı C07-L3 bağlantısı için sırasıyla 88/87/83/88 günlük IZLE tahmini üretildi ve testin 90 gün sınırı aşılamadı. Testler gerçek sistem saatine göre tarihli simülasyon başlatıyor. Değişmemiş ana repoda `trafo_devreye_alma` için 90 günlük aynı hata yeniden üretildi; bu karşılaştırma diğer üç hatanın tüm nedenlerini tek başına kanıtlamaz. **Tam repo testleri temiz değildir.** Alarm/tahmin eşikleri veya bu testlerin beklentileri değiştirilmedi.

Tam koşu çıktısı: `evidence/b1-update-full.log`. Odaklı koşu: `evidence/b1-update-focused.log`. Eski `pytest-final.log` önceki teslimin tarihsel kanıtıdır; bu güncellemenin tamamının geçtiği anlamına gelmez.

## Dijital ikiz–CAD bağlantısı (20.09.2026)

- Dört B1 kartı dokuz cihazla eşlendi; mekanik ve PCB görselleri pano ekranından açılır. Şematik PDF, kutu STEP, PCB KiCad ve pano montaj PDF bağlantıları kaynak teslim dosyalarını kullanır.
- Nominal kutu ölçüleri mekanik boyut dosyasından gelir; TC'nin uzun ekseni pano derinliğine yöneliktir. Çizimdeki izometrik küçük resim yalnız tanıtımdır; fiziksel montaj veya üretim doğrulaması sayılmaz.
- `firmware/tests/test_hardware_assets.py` ve `test_b1_integration.py`: **9 test geçti**. 29 sunulan dosyanın kaynak dosyalarla bayt düzeyinde aynı olduğu, MIME/indirme başlıkları, cihaz eşlemeleri ve izin verilmeyen yolların 404 döndürdüğü kontrol edildi. Çıktı: `evidence/hardware-ui-tests.log`.
- Canlı tarayıcıda pano üzerinden IR seçimi, klavye ile PD seçimi, GW seçimi ve PCB üst/alt geçişleri doğrulandı. Görseller başarıyla yüklendi; seçilen cihaz ve PCB görünümü telemetri yenilenirken korundu. Dar uygulama panelinde önizlemeler alt alta görünür.
- Bu bağlantı için şematik, PCB, firmware, ortak sözleşmeler ve alarm/tahmin eşikleri değiştirilmedi. Önceki tam repo testlerindeki açık negatif kontrol hataları bu sonuçla kapanmış değildir.

## Ekip birleştirmesi

K1 kaynaklarına ek olarak gateway, simülatör, API ve arayüz dosyaları değişti. Ortak kanal/varlık/Envelope sözleşmesi korunur. API'de mevcut `joints_monitored` ve `monitored` alanları aday bölgeyi temsil etmeyi sürdürür; gerçek B1 kapsamı `joints_resolved`, `measurement_supported` ve `hardware_profile` ile ayrıca verilir. Eski istemciler bu ayrımı kullanmıyorsa arayüzleri de güncellenmelidir.

Eski veritabanında ideal IR geçmişi bulunabilir. Silmek yerine yeni dosya kullanın:

```powershell
python -m panogoz.run_local --panels 12 --backfill-days 75 --host 127.0.0.1 --port 8081 --scada-host 127.0.0.1 --scada-port 5021 --db panogoz-b1.db
```

## Açık kabul kalemleri

**K1 1.6 kısmen açık:** 195 fiyat ve kesin MPN/alternatif/teslim teyitleri; tam maliyet için IR/PD görev çevrimi ve bakım girdileri. Satıcı teyidi veya fiziksel ölçüm yapılmış gibi sonuç üretilmedi. K1 1.1–1.5'in tasarım/yerleşim/TC hedef derlemesi kanıtları `hardware/README.md` kabul matrisindedir. PCB routing, kart üretimi ve lehimleme görev belgesindeki tasarım tesliminin yapılmış parçası olarak sunulmaz. Genel projenin negatif kontrol tahmin hataları da kapanmadan tüm projeye “tam uyumlu ve bütün testleri geçti” denemez.
