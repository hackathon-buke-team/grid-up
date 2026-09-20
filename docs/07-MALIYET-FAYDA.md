# 07 · B1 maliyet ve fayda hesabı

20.09.2026. Bu sürüm eski EUR maliyet ve 9–16 yıl pil ömrü senaryolarının yerine geçer. Güncel BOM'un 214 satırından 19 satırında USD liste fiyatı gözlendi; 195 satırın fiyatı bilinmiyor. **Tam kit maliyeti ve geri ödeme süresi henüz hesaplanamaz.** Eski 2,2 / 6,9 yıl geri ödeme rakamları B1 sonucu değildir ve sunumda kullanılmamalıdır.

## Kaynak ve hesaplama

Tek fiyat kaynağı [bom.json](../hardware/B1/bom.json); okunabilir karşılığı [BOM.md](../hardware/B1/BOM.md). Her fiyatın ürün sayfası, tarih, sipariş adedi, alternatif ve tedarik notu vardır. Stok bilgisi teslimat taahhüdü değildir. Özellikle AD8318, TPS62130 ve TLV3201 için stok yokluğu; TLV3691 için kit adedine yetmeyen stok gözlendi. Farklı ülkedeki mağaza/para birimi fiyatları USD ile toplanmaz.

`python hardware/tools/bom.py` ardından `python hardware/tools/costs.py` çalıştırılır. Makinece okunabilir sonuç [cost-summary.json](../hardware/B1/cost-summary.json). Eksik fiyat `null` kalır; sıfır sayılmaz.

| Kapsam | Fiyatı bilinen kalemler ara toplamı, USD | Tam donanım maliyeti |
|---|---:|---|
| 1 pano / 9 cihaz | 260.09 | Eksik |
| 100 pano / 900 cihaz | 26009.00 | Eksik |
| 1000 pano / 9000 cihaz | 260090.00 | Eksik |

Bu çarpımlar yalnız birim-adet liste fiyatlarıyla ölçeği gösterir; hacimli satın alma teklifi veya indirim değildir. PCB/montaj, CT/HFCT, pil/HLC, anten, modem, kablo ve kutu dahil bilinmeyen fiyatlar eklenmeden bu ara toplam pano başı maliyet olarak sunulamaz. Tasarım kartları üretilmeyecek; fiyat araştırması satın alma emri değildir.

## Beş yıllık bakım bütçesi

TC görev karması %97 IDLE / %2,5 WATCH / %0,5 BURST, 50 µA bekleme bütçesi ve 1,2 Ah hücre ile **721 gün** tasarım hesabıdır; ölçülmüş ömür değildir. Yeni hücreyle başlayan beş yıllık senaryoda 721 ve 1442. günlerde iki değişim turu gerekir: **6 TC × 2 = 12 ek hücre/kit**, ayrıca servis işçiliği, yol ve paket uygunluk maliyeti.

IR için 221 gün ve PD için yaklaşık 52 gün, docs/02'deki örnek görev çevrimlerinde yalnız belirli yükleri içeren iyimser üst sınırlardır. Bunlar bakım aralığı veya ürün ömrü olarak kullanılmaz. IR/PD pilleri için beş yıl boyunca değişim yok varsayımı kaldırılmıştır; görev çevrimi ve toplam akım bütçesi doğrulanmadan TCO kapatılamaz.

## Tam maliyet formülü

`K_kit = fiyatlı BOM ara toplamı + tüm eksik BOM teklifleri`

`TCO_5 = N × (K_kit + kurulum + 12 × TC_yedek_hücre + TC_servis + IR_PD_bakım) + ortak_sunucu + 5 × yıllık_işletme + vergi/nakliye`

Satın alma BOM'undaki başlangıç hücreleri ile sonradan değiştirilen hücreler farklıdır; başlangıç maliyeti iki kere eklenmez. RFQ kalemleri imalat/montajı zaten içeriyorsa tekrar sayılmaz. Para birimi dönüşümü yapılacaksa tek kur, kaynak ve tarih kaydedilir.

## Fayda ve geri ödeme

Fayda; DSO'nun geçmiş bağlantı arızaları, olay başı maliyet, kaçınılan olay oranı ve gerçekten tasarruf edilen bakım ziyaretlerinden hesaplanmalıdır. **B1'de 40 bağımsız IR ölçüm noktası yoktur; 6 TC noktası vardır.** Eski bütün-pano kapsaması ve %70 tespit oranı maliyet-fayda hesabına doğrulanmış veri olarak taşınmaz. Rutin termografi ziyaretlerinin azaltılacağı da varsayılmaz.

Eksik teklif, IR/PD bakım aralığı ve saha fayda verisi nedeniyle toplam TCO, net fayda ve geri ödeme sonucu `null` bırakılır. Bu bir başarısız hesap değil, eksik girdilerle yanlış kesinlik üretmeme kuralıdır.

## K1 1.6 kapanış koşulu

[Tedarik açıkları](../hardware/B1/TEDARIK-ACIKLARI.md) her fiyatı eksik kalemi ref/footprint/adediyle listeler. MPN/alternatif uygunluğu ve güncel fiyat/teslim tarihi tamamlandığında aynı araçlar maliyetleri tekrar üretir. **K1 1.6 kısmen açıktır**; RFQ hazırlığının bitmesi tedarikçi teyidinin alındığı anlamına gelmez.
