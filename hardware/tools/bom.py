"""Generate the auditable engineering BOM from the exact KiCad circuit manifest."""
from pathlib import Path
import json,collections,urllib.parse
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'B1'
# USD, quantity-one published distributor observations on 2026-09-20.
# Stock is a web observation, not a purchase commitment or a delivery promise.
PRICES={
 'STM32WLE5CCU6':(9.26,'https://www.digikey.com/es/products/detail/stmicroelectronics/STM32WLE5CCU6/13557445','Stock shown 4540; shipping/lead time reconfirm','Same device, alternate authorized distributor'),
 'STM32H563ZIT6':(11.19,'https://www.digikey.com/en/products/detail/stmicroelectronics/STM32H563ZIT6/18110508','No stock; incoming date varies Nov 2026','STM32H563ZIT6TR; packaging only, verify quote'),
 'TMP117AIDRVR':(5.56,'https://www.digikey.com/en/products/detail/texas-instruments/TMP117AIDRVR/9685284','9 weeks standard; incoming 20 Oct 2026 shown','TMP117AIDRVT (same industrial die/package; reel size)'),
 'MLX90640ESF-BAA-000-TU':(38.15,'https://www.digikey.in/en/products/detail/melexis-technologies-nv/MLX90640ESF-BAA-000-TU/8638463','Stock shown 174; lead time unconfirmed','MLX90640ESF-BAA-000-SP; packaging only, NOT BAB'),
 'SHT41-AD1B-R2':(2.95,'https://www.digikey.com/en/products/detail/sensirion-ag/SHT41-AD1B-R2/15296591','8 weeks standard; stock shown','SHT41-AD1B-R3; manufacturer/distributor lists direct substitute'),
}
# Rechecked US storefront prices, 2026-09-20, quantity one, USD. Packaging
# alternatives are candidates; no different electrical device is substituted.
PRICES['MLX90640ESF-BAA-000-TU']=(38.52,'https://www.digikey.com/en/products/detail/melexis-technologies-nv/MLX90640ESF-BAA-000-TU/8638463','68 in stock observed; Turkey delivery unconfirmed','MLX90640ESF-BAA-000-SP; packaging only, NOT BAB')
PRICES.update({
 'TPS7A0230PDBVR':(.84,'https://www.digikey.com/en/products/detail/texas-instruments/TPS7A0230PDBVR/12165118','3398 in stock observed; delivery unconfirmed','Same MPN from another authorized distributor'),
 'TPS63900DSKR':(2.74,'https://www.digikey.com/en/products/detail/texas-instruments/TPS63900DSKR/13535479','17077 in stock observed; delivery unconfirmed','Same MPN from another authorized distributor'),
 'OPA333AIDBVR':(2.60,'https://www.digikey.com/en/products/detail/texas-instruments/OPA333AIDBVR/1572431','9715 in stock observed; delivery unconfirmed','OPA333AIDBVT packaging candidate; electrical review required'),
 'TLV3691IDCKR':(1.28,'https://www.digikey.com/en/products/detail/texas-instruments/TLV3691IDCKR/4555468','Only 3 in stock observed: insufficient for 6 TC; quote required','TLV3691IDCKT packaging candidate; supplier lists parametric equivalent'),
 'ADM2587EBRWZ':(17.36,'https://www.digikey.com/en/products/detail/analog-devices-inc/ADM2587EBRWZ/2261070','10206 in stock observed; delivery unconfirmed','ADM2587EBRWZ-REEL7 packaging candidate'),
 'AD8318ACPZ':(18.85,'https://www.digikey.com/en/products/detail/analog-devices-inc/AD8318ACPZ-REEL7/996044','No stock; 1500 incoming 24-Dec-2026 shown, not guaranteed','AD8318ACPZ-REEL7 ordered packaging; same LFCSP family'),
 'TPS61023DRLR':(1.22,'https://www.digikey.com/en/products/detail/texas-instruments/tps61023drlr/11310629','Delivery unconfirmed; price observation only','Same MPN from another authorized distributor'),
 'TPS62130RGTR':(1.99,'https://www.digikey.com/en/products/detail/texas-instruments/TPS62130RGTR/2833429','No stock; incoming 22/26-Oct-2026; manufacturer standard 16 weeks shown','TPS62130RGTT packaging candidate; TPS62130A requires electrical review'),
 'OPA320AIDBVR':(3.06,'https://www.digikey.com/en/products/detail/texas-instruments/OPA320AIDBVR/2747429','Manufacturer standard 16 weeks shown; delivery unconfirmed','OPA320AIDBVT packaging candidate; check ordering table'),
 'TLV3201AIDBVR':(1.41,'https://www.digikey.com/en/products/detail/texas-instruments/TLV3201AIDBVR/3188691','No stock; incoming 29-Oct/02-Nov-2026; standard 16 weeks shown','Same MPN elsewhere; suggested TS30xx devices are not approved substitutes'),
})
PRICES['STM32WLE5CCU6']=(9.26,'https://www.digikey.com/en/products/detail/stmicroelectronics/STM32WLE5CCU6/13557445','4486 in stock observed; delivery unconfirmed',PRICES['STM32WLE5CCU6'][3])
rows=[]
for kind,mult in [('TC',6),('IR',1),('PD',1),('GW',1)]:
 cs=json.loads((OUT/kind/'circuit.json').read_text())['components'];groups=collections.defaultdict(list)
 for c in cs:
  if not c.get('virtual'):groups[(c['value'],c['mpn'],c['fp'])].append(c['ref'])
 for (value,mpn,fp),refs in groups.items():
  r={'board':kind,'refs':refs,'value':value,'mpn_or_engineering_spec':mpn,'footprint':fp,'per_board':len(refs),'per_kit':len(refs)*mult,'supplier':'DigiKey / Mouser RFQ','unit_usd':None,'price_status':'QUOTE_REQUIRED','checked':'2026-09-20','lead_time':'Unconfirmed','alternative':'Same specification/package from authorized source; no unreviewed substitution','url':'https://www.digikey.com/en/products?keywords='+urllib.parse.quote(mpn)}
  if mpn in PRICES:
   r['unit_usd'],r['url'],r['lead_time'],r['alternative']=PRICES[mpn];r['supplier']='DigiKey';r['price_status']='OBSERVED_QTY1_USD'
  if value.startswith(('1uF','10uF','22uF','47uF','100uF')):r['alternative']='MLCC with verified effective capacitance at bias; exact vendor MPN pending'
  if mpn.startswith('1% thick film') and '0.1%' in value:r['mpn_or_engineering_spec']=value+' precision thin film; NOT generic 1%'
  if kind!='GW' and ('pF' in value or 'nH' in value):r['alternative']='RF C0G high-Q capacitor / RF high-Q inductor; exact Q/SRF and tuned value pending'
  rows.append(r)
externals=[
 ('TC',6,'CT 400 A / 3000:1 / split core / aperture >=32 mm','Custom CT supplier quote; captive secondary clamp 5.6 V and burden connector'),
 ('TC',6,'ER14250 3.6 V primary cell, 1.2 Ah envelope','EVE / Saft qualified equivalent; compare discharge limits'),
 ('TC+PD',7,'HLC pulse buffer <=16.5 x55 mm, compatible with Li-SOCl2','Tadiran hybrid battery supplier; selection and pack qualification pending'),
 ('IR',1,'ER14505 3.6 V 2.6 Ah, pulse-rated assembled pack','EVE / Tadiran; IR inrush <= selected pack rating'),
 ('PD',1,'ER26500 3.6 V 8.5 Ah','EVE / Tadiran; buffer mandatory for RF front-end peaks'),
 ('PD',1,'HFCT50','Power Diagnostix / authorized supplier; supplied DS_HFCT50_eng.pdf'),
 ('PD',1,'Insulated TEV capacitive plate assembly','Custom mechanical supplier; capacitance and transfer calibration pending'),
 ('PD',1,'MA40S4R 40 kHz receiver','Murata / authorized distributor'),
 ('PD',1,'Isolated 50 Hz voltage-phase reference, SELV 0..3.3 V output','Qualified external sensing accessory; never line voltage on header'),
 ('GW',1,'EC21-E MiniPCIe LTE modem (not bare LCC EC21)','Quectel authorized distributor; local bands/carrier approval check'),
 ('GW',1,'5 V SELV 4 A isolated DIN power supply','Industrial certified PSU RFQ; no mains design on carrier'),
 ('GW',2,'10 F / 2.7 V EDLC in enclosed series pack','Panasonic / Eaton; ESR/leakage/temperature data required'),
 ('GW',1,'Primary 3 V RTC backup cell, enclosed','No charging enabled in RV3028 configuration'),
 ('ALL',9,'Insulated 868 MHz antenna and captive coax','Antenna supplier; RF gain and mounting calibration'),
 ('GW',1,'LTE antenna + SIM holder + short USB/SIM harness','Quectel-compatible matched accessories'),
 ('ALL',1,'6 TC +1 IR +1 PD +1 GW enclosure/mount/gasket set','Local prototype shop; STEP models, flame grade and tolerance quote'),
 ('ALL',1,'4-layer PCB: 6 TC +1 IR +1 PD +1 GW; assembly','Board house RFQ AFTER routing, DRC and design release'),
 ('ALL',1,'Low-voltage cables, clamps, strain relief and labels','Lengths in mechanical document; assembly quote'),
]
for k,n,part,supplier in externals:rows.append({'board':k,'refs':['EXTERNAL'],'value':part,'mpn_or_engineering_spec':part,'footprint':'external','per_board':None,'per_kit':n,'supplier':supplier,'unit_usd':None,'price_status':'QUOTE_REQUIRED','checked':'2026-09-20','lead_time':'Unconfirmed','alternative':'Must satisfy mechanical, thermal and electrical design envelope','url':None})
for r in rows:
 r['line_id']=r['board']+':'+(','.join(r['refs']) if r['refs']!=['EXTERNAL'] else r['value'])
 r['order_mpn']='AD8318ACPZ-REEL7' if r['mpn_or_engineering_spec']=='AD8318ACPZ' else (r['mpn_or_engineering_spec'] if r['unit_usd'] is not None else None)
 r['lead_time_confirmed']=False
 r['price_quantity']=1 if r['unit_usd'] is not None else None
 r['procurement_status']=('PRICE_OBSERVED_DELIVERY_UNCONFIRMED' if r['unit_usd'] is not None else
                          'CUSTOM_OR_EXTERNAL_RFQ' if r['refs']==['EXTERNAL'] else 'MPN_AND_QUOTE_REVIEW')
known=sum(r['unit_usd']*r['per_kit'] for r in rows if r['unit_usd'] is not None)
doc={'currency':'USD','date':'2026-09-20','price_basis':'quantity-one list price; not a quote; taxes, shipping, assembly excluded','known_subtotal_usd':round(known,2),'complete_kit_cost_usd':None,'unpriced_line_count':sum(r['unit_usd'] is None for r in rows),'rows':rows}
(OUT/'bom.json').write_text(json.dumps(doc,indent=2,ensure_ascii=False),encoding='utf8')
lines=['# B1 mühendislik BOM ve fiyat kaydı','',f'20.09.2026. Doğrulanmış fiyatı bulunan satırların kit ara toplamı **{known:.2f} USD**. Bu, tam kit fiyatı değildir. Vergi, nakliye, üretim ve fiyatı bulunmayan satırlar hariçtir. Boş fiyat sıfır maliyet anlamına gelmez.','',f'Toplam {len(rows)} satın alma satırı; {doc["unpriced_line_count"]} satır için teklif gerekiyor. Kesin maliyet/geri dönüş süresi ilan edilemez. Parça bazında kaynak, alternatif ve termin için `bom.json` esas alınır.','', '| Kart / ref | Parça veya mühendislik tanımı | Kit adet | Birim USD | Durum / kaynak |','|---|---|---:|---:|---|']
for r in rows:
 price=f'{r["unit_usd"]:.2f}' if r['unit_usd'] is not None else 'teklif'
 source=f'[DigiKey]({r["url"]})' if r['unit_usd'] is not None else r['supplier']
 lines.append('| '+r['board']+' / '+','.join(r['refs'])+' | '+r['value']+' | '+str(r['per_kit'])+' | '+price+' | '+source+' |')
lines+=['','Pasifler için değer/paket/tolerans mühendislik şartıdır; `X7R 16V ...` veya `1% ...` sipariş edilebilir üretici kodu değildir. Satın alma BOM’u, eksik MPN ve teklifler tamamlanmadan serbest bırakılmayacaktır. RF kapasitörlerinde C0G ve yüksek Q, CT burden direncinde 0,1%/0,5 W zorunludur. Üretim katman yığını ve toleranslar üreticiyle onaylanmalıdır.']
(OUT/'BOM.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
print('BOM',len(rows),'rows; known subtotal USD',round(known,2))

# Every remaining line is actionable and retains its electrical reference.
pending=[r for r in rows if r['unit_usd'] is None]
rfq=['# B1 tedarik açıkları','',
     'Bu dosya teklif talebi hazırlığıdır; hiçbir tedarikçiye gönderilmedi. Her satır için kesin MPN, paket, pin dizilimi, sıcaklık sınıfı, birim fiyat/para birimi/adet, alternatif ve Türkiye teslim tarihi kaydedilmelidir.',
     '', 'RF eşleme parçalarının değerleri routing ve RF doğrulaması sonrası sabitlenir. CT, HLC, izole faz referansı ve kutu kalemlerinde ölçü/elektriksel uygunluk fiyatla birlikte onaylanmalıdır.',
     '', '| Kart / ref | Adet / kit | Teknik şart | Açık iş |', '|---|---:|---|---|']
for r in pending:rfq.append(f'| {r["board"]} / {",".join(r["refs"])} | {r["per_kit"]} | {r["mpn_or_engineering_spec"]} / {r["footprint"]} | {r["procurement_status"]} |')
(OUT/'TEDARIK-ACIKLARI.md').write_text('\n'.join(rfq)+'\n',encoding='utf8')
