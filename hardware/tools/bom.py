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
