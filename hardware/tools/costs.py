"""Recalculate the B1 procurement/TCO record without pricing unknowns at zero."""
from pathlib import Path
from math import ceil
import json

ROOT = Path(__file__).resolve().parents[2]


def calculate(bom: dict, years: float = 5) -> dict:
    if years <= 0:
        raise ValueError('years must be positive')
    rows = bom['rows']
    unknown = [r['line_id'] for r in rows if r['unit_usd'] is None]
    subtotal = round(sum(r['per_kit'] * r['unit_usd'] for r in rows
                         if r['unit_usd'] is not None), 2)
    # New TC cells at deployment. Do not replace one at the exact end of study.
    tc_visits = max(0, ceil(years * 365.25 / 721) - 1)
    return {
        'currency': 'USD', 'price_basis': 'observed quantity-one list prices',
        'date': bom['date'], 'years': years,
        'line_count': len(rows), 'priced_lines': len(rows) - len(unknown),
        'unpriced_lines': len(unknown), 'unpriced_line_ids': unknown,
        'known_kit_subtotal_usd': subtotal,
        'procurement_kit_usd': None if unknown else subtotal,
        'complete_installed_kit_usd': None,
        'tc_life_days_assumed': 721, 'tc_replacement_rounds': tc_visits,
        'tc_replacement_cells_per_kit': 6 * tc_visits,
        'ir_pd_replacement_cost_usd': None,
        'five_year_tco_usd': None, 'payback_years': None,
        'fleet_known_parts_subtotals_usd': {str(n): round(subtotal*n, 2) for n in (1, 100, 1000)},
        'open_inputs': ['unpriced BOM lines and approved MPNs', 'tax/freight/installation',
                        'TC replacement cell/HLC pack price and service cost',
                        'IR/PD duty-cycle validation and replacement intervals',
                        'on-premise/SIM/calibration/support costs',
                        'DSO avoided-failure and maintenance-benefit evidence'],
    }


def main():
    b = ROOT/'hardware/B1'
    result = calculate(json.loads((b/'bom.json').read_text(encoding='utf8')))
    (b/'cost-summary.json').write_text(json.dumps(result, indent=2, ensure_ascii=False)+'\n',encoding='utf8')
    text = f'''# 07 · B1 maliyet ve fayda hesabı

20.09.2026. Bu sürüm eski EUR maliyet ve 9–16 yıl pil ömrü senaryolarının yerine geçer. Güncel BOM'un {result['line_count']} satırından {result['priced_lines']} satırında USD liste fiyatı gözlendi; {result['unpriced_lines']} satırın fiyatı bilinmiyor. **Tam kit maliyeti ve geri ödeme süresi henüz hesaplanamaz.** Eski 2,2 / 6,9 yıl geri ödeme rakamları B1 sonucu değildir ve sunumda kullanılmamalıdır.

## Kaynak ve hesaplama

Tek fiyat kaynağı [bom.json](../hardware/B1/bom.json); okunabilir karşılığı [BOM.md](../hardware/B1/BOM.md). Her fiyatın ürün sayfası, tarih, sipariş adedi, alternatif ve tedarik notu vardır. Stok bilgisi teslimat taahhüdü değildir. Özellikle AD8318, TPS62130 ve TLV3201 için stok yokluğu; TLV3691 için kit adedine yetmeyen stok gözlendi. Farklı ülkedeki mağaza/para birimi fiyatları USD ile toplanmaz.

`python hardware/tools/bom.py` ardından `python hardware/tools/costs.py` çalıştırılır. Makinece okunabilir sonuç [cost-summary.json](../hardware/B1/cost-summary.json). Eksik fiyat `null` kalır; sıfır sayılmaz.

| Kapsam | Fiyatı bilinen kalemler ara toplamı, USD | Tam donanım maliyeti |
|---|---:|---|
| 1 pano / 9 cihaz | {result['known_kit_subtotal_usd']:.2f} | Eksik |
| 100 pano / 900 cihaz | {result['fleet_known_parts_subtotals_usd']['100']:.2f} | Eksik |
| 1000 pano / 9000 cihaz | {result['fleet_known_parts_subtotals_usd']['1000']:.2f} | Eksik |

Bu çarpımlar yalnız birim-adet liste fiyatlarıyla ölçeği gösterir; hacimli satın alma teklifi veya indirim değildir. PCB/montaj, CT/HFCT, pil/HLC, anten, modem, kablo ve kutu dahil bilinmeyen fiyatlar eklenmeden bu ara toplam pano başı maliyet olarak sunulamaz. Tasarım kartları üretilmeyecek; fiyat araştırması satın alma emri değildir.

## Beş yıllık bakım bütçesi

TC görev karması %97 IDLE / %2,5 WATCH / %0,5 BURST, 50 µA bekleme bütçesi ve 1,2 Ah hücre ile **721 gün** tasarım hesabıdır; ölçülmüş ömür değildir. Yeni hücreyle başlayan beş yıllık senaryoda 721 ve 1442. günlerde iki değişim turu gerekir: **6 TC × {result['tc_replacement_rounds']} = {result['tc_replacement_cells_per_kit']} ek hücre/kit**, ayrıca servis işçiliği, yol ve paket uygunluk maliyeti.

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
'''
    (ROOT/'docs/07-MALIYET-FAYDA.md').write_text(text,encoding='utf8')
    print(json.dumps({k:v for k,v in result.items() if k!='unpriced_line_ids'},indent=2))


if __name__ == '__main__':
    main()
