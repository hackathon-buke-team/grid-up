"""Presentation PDF: dimensioned panel placement and traceable K1 evidence.
Run after export.py, mechanical.py and bom.py. Requires ReportLab.
"""
from pathlib import Path
import json,math
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph,Table,TableStyle
from reportlab.lib.styles import ParagraphStyle
ROOT=Path(__file__).resolve().parents[1];B=ROOT/'B1';M=B/'mechanical'
for name,file in [('Sans','arial.ttf'),('Bold','arialbd.ttf')]:pdfmetrics.registerFont(TTFont(name,'C:/Windows/Fonts/'+file))
W,H=1190.55,841.89
c=canvas.Canvas(str(B/'K1-B1-TASARIM-DOSYASI.pdf'),pagesize=(W,H));c.setTitle('PANO GÖZ / K1 B1 tasarım dosyası')
navy=HexColor('#102E43');teal=HexColor('#007F83');orange=HexColor('#BC6E15');grey=HexColor('#5D6C75');light=HexColor('#EAF0F3')
ps=ParagraphStyle('body',fontName='Sans',fontSize=12,leading=18,textColor=navy)
def text(t,x,y,size=12,font='Sans',color=navy):c.setFillColor(color);c.setFont(font,size);c.drawString(x,y,t)
def para(t,x,y,w,size=12):
 st=ParagraphStyle('p',parent=ps,fontSize=size,leading=size*1.45);p=Paragraph(t,st);_,h=p.wrap(w,1000);p.drawOn(c,x,y-h);return y-h
def page(n,title,sub):
 c.setFillColor(navy);c.rect(0,H-120,W,120,fill=1,stroke=0)
 text('GRID UP  /  PANO GÖZ  /  K1',42,H-35,12,'Bold',HexColor('#72D8D2'))
 text(title,42,H-73,28,'Bold',HexColor('#FFFFFF'));text(sub,42,H-102,11,color=HexColor('#D6E4EB'))
 c.setStrokeColor(light);c.line(42,48,W-42,48)
 text('B1  •  20.09.2026  •  TASARIM / FİZİKSEL ÜRETİM YOK',42,29,10,color=grey)
 text(f'{n:02d} / 07',W-93,29,10,'Bold',grey)
def pic(path,x,y,w,h):c.drawImage(str(path),x,y,w,h,preserveAspectRatio=True,anchor='c',mask='auto')
def dim(x1,y1,x2,y2,label):
 c.setStrokeColor(grey);c.setLineWidth(.65);c.line(x1,y1,x2,y2)
 if y1==y2:
  for x in (x1,x2):c.line(x,y1-5,x,y1+5)
  text(label,(x1+x2)/2-pdfmetrics.stringWidth(label,'Sans',10)/2,y1+7,10)
 else:
  for y in (y1,y2):c.line(x1-5,y,x1+5,y)
  c.saveState();c.translate(x1-9,(y1+y2)/2);c.rotate(90);text(label,-pdfmetrics.stringWidth(label,'Sans',10)/2,0,10);c.restoreState()
def table(rows,x,y,widths):
 st=ParagraphStyle('t',parent=ps,fontSize=11,leading=15)
 data=[[Paragraph(str(z),st) for z in row] for row in rows]
 t=Table(data,colWidths=widths,hAlign='LEFT');t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),light),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),9),('RIGHTPADDING',(0,0),(-1,-1),9),('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8),('LINEBELOW',(0,0),(-1,-1),.4,light)]));_,h=t.wrap(sum(widths),1000);t.drawOn(c,x,y-h);return y-h

page(1,'Dokuz cihaz, dört kart, tek pano','K1 / 1.3  •  Verilen EK-II/14 teknik çizimi üzerinde montaj konsepti')
pic(M/'panel-reference.png',55,220,365,460)
text('Verilen teknik çizim / açıklamalı alıntı',55,200,12,'Bold')
# Source crop x58..264, y300..587. Original front panel inner x67..253, y330..560.
ix,iy,iw,ih=55,220,365,460;scale=min(iw/206,ih/287);ox=ix+(iw-206*scale)/2;oy=iy+(ih-287*scale)/2
def srcpt(x,y):return ox+(x-58)*scale,oy+(587-y)*scale
devices=[('TC-01..03',588,430),('TC-04..06',688,430),('TN-IR',640,150),('PD-01',1290,230),('GW-01',1450,980)]
for i,(label,x,y) in enumerate(devices,1):
 px,py=srcpt(67+186*x/1600,560-230*y/1500)
 c.setFillColor(teal);c.circle(px,py,9,fill=1,stroke=0);text(str(i),px-3,py-4,11,'Bold',HexColor('#FFFFFF'))
para('Kaynak çizimde cihaz işaretleri konsept konumlarını gösterir. Sağdaki yeniden çizim ölçülüdür; kaynak PDF kağıdındaki görüntü ölçeği mekanik ölçü olarak kullanılmaz.',55,172,365,11)
px,py,s=580,211,.30;c.setStrokeColor(navy);c.setLineWidth(1.2);c.rect(px,py,1600*s,1500*s)
for y in (700,1045):c.line(px,py+y*s,px+1600*s,py+y*s)
c.line(px+1360*s,py,px+1360*s,py+1500*s)
text('Üst bara / ana donanım',px+20,py+1320*s,12,'Bold');text('K1 bağlantısı yok',px+20,py+1230*s,11,color=grey)
text('Pabuç sırası, y≈500',px+15,py+525*s,10,color=grey)
c.setDash(3,3);c.line(px,py+500*s,px+1360*s,py+500*s);c.setDash()
for j,x in enumerate([568,588,608,668,688,708],1):
 c.setFillColor(teal);c.rect(px+(x-9.75)*s,py+(430-17)*s,19.5*s,34*s,fill=1,stroke=0)
for label,x,y in devices[2:]:
 c.setFillColor(teal);c.circle(px+x*s,py+y*s,6,fill=1,stroke=0)
 text(label,px+x*s-30,py+y*s+(-20 if label=='GW-01' else 14),10,'Bold')
text('1  TC-01..03',px+105,py+105,10,'Bold');text('2  TC-04..06',px+105,py+90,10,'Bold')
dim(px,py-25,px+480,py-25,'1600 mm');dim(px-25,py,px-25,py+450,'1500 mm')
para('Ön-sol-alt köşe: (0,0). x sağa, y yukarı; z ön yüzeyden içeri. Nominal derinlik 450 mm. Cihaz x/y kimlikleri repo sözleşmesinden korunmuştur.',505,153,575,12)
para('Pano üzerinde yeni delik, bara/iletken kesiti değişikliği veya PE pabuçlarının sökülmesi öngörülmez. İşaretler saha ölçümü değildir; servis ve elektriksel açıklıklar sahada yetkili tasarım incelemesiyle doğrulanır.',505,98,575,10)
c.showPage()

page(2,'Montaj, kablo yolu ve optik geometri','K1 / 1.3  •  Tüm ölçüler mm  •  Yeni pano deliği yok')
rows=[['Cihaz','Merkez x / y','Bağlama ve servis hedefi'],['TC-01 / 02 / 03','568 / 588 / 608 ; y=430','C06 faz kablosu; nominal Ø32 kelepçe. Kutu kenarı öne bakar: 19,5 mm izdüşüm.'],['TC-04 / 05 / 06','668 / 688 / 708 ; y=430','C07 faz kablosu; 50-100 mm pabuç altı. Yalıtımlı yüzeye ısıl temas.'],['TN-IR','640 / 150','Kapsüllü mıknatıs kaide; yukarı/öne yönlendirilmiş optik eksen.'],['PD-01','1290 / 230','Mevcut M12 aksesuar bağlantısı; PE bağlantısı bozulmadan. HFCT PE çevresine.'],['GW-01','1450 / 980','35 mm DIN ray; ölçü/yardımcı kolon; mevcut mühürlü anten geçişi.']]
y=table(rows,42,690,[180,230,696])
text('Kablo yığınına karşı tasarım',42,y-34,18,'Bold')
para('Sekiz pil düğümü için ortak güç veya veri demeti yoktur. TC-CT kablosu ≤150 mm; PD-HFCT/TEV koaksiyeli hedef ≤500 mm. GW-MPR ve GW-TVOC ayrı bükümlü ekranlı RS-485 hatlarıyla mevcut kanalı izler; hedef her biri ≤1,5 m. LTE SIM demeti ≤50 mm. Ekran ve fonksiyonel şasi bağlantısı sistem EMC incelemesinde tek noktada tanımlanır.',42,y-55,520,12)
para('Kutu kapağı için en az 30 mm, çıkarılabilir terminal önünde 50 mm ve DIN sökme yönünde 20 mm servis alanı hedeflenir. Bunlar erişim hedefidir; enerjili iletkenlere yaklaşma veya yalıtım mesafesi değildir. Anten ve batarya yalıtımlı kutudadır; sarkık metal ve açık pil bağlantısı bırakılmaz.',610,y-55,535,12)
text('20 mm faz adımı için derinlik kademesi',42,251,18,'Bold')
para('Ø42 mm dış kelepçe aynı düzlemde 20 mm adımda çakışır. Her üçlü için z=80 / 140 / 200 mm konsept kademesi seçilir; 126 mm gövdeyle en büyük z=326 mm, nominal 450 mm pano derinliğinin içindedir. Gerçek kablo bükülmesi, faz aralığı ve ulaşılabilirlik ölçülmeden montaj uygunluğu kesinleşmez.',42,230,520,12)
text('IR görüş alanı ve çözünürlük sınırı',610,251,18,'Bold')
para('MLX90640 BAA: 110° × 75°. 350 mm düşey fark ve 235 mm derinlik farkı: mesafe ≈422 mm; yatay görüş ≈1205 mm. Optik eksen yataydan ≈56°. Bu, görüş zarfıdır: 32 sütunda ≈38 mm/piksel, 20 mm aralıklı her pabucu bağımsız ayıramaz. ROI örtüşmesi ve engellenen pabuçlar kalibrasyonda işaretlenmelidir. TC altı noktayı doğrudan doğrular.',610,230,535,12)
text('Montaj doğrulaması: kapak/mandal toleransı, titreşim tutunması, pencere geçirgenliği ve açıklık ölçümü bekleniyor.',42,84,11,color=grey)
c.showPage()

dimensions=json.loads((M/'dimensions.json').read_text())
notes={
 'TC':('Altı kablo kelepçesi','TMP117AIDRVR + 3000:1 CT; STM32WLE5CC. PCB 30×22 mm, iki yüzlü bileşen yerleşimi. ER14250 ve HLC gövde içinde ayrı hacimler. Termal ada bakır dolgu/via kısıtı içerir; temas direnci ve kablo kılıfı gecikmesi kalibre edilir.'),
 'IR':('Tek termal dizi / hava düğümü','MLX90640 BAA + SHT41; anahtarlanan sensör beslemesi ve I²C pull-up’ları. IR optik açıklığı ve havalandırma membranı ayrı tutulur. Sıradan cam/polikarbonat pencere LWIR için uygun değildir. Kutunun eğimi ayarlanabilir kaideyle ayarlanır; STEP genel hacim modelidir.'),
 'PD':('RF / TEV / ultrasonik düğümü','AD8318 ve PGA-103+ ayrı anahtarlanan 5 V hattındadır. Analog güç için yaklaşık 0,35 A pil tepe akımı bütçelenir; HLC/pil paketi seçimi gereklidir. HFCT/TEV sırayla ölçülür. Faz girişi yalnız yalıtılmış 0..3,3 V işaret kabul eder; şebeke gerilimi bağlanmaz.'),
 'GW':('DIN ray ağ geçidi taşıyıcısı','STM32H563 + LAN8742A + 2× ADM2587E + E22/SX1262 + EC21-E MiniPCIe. İki RS-485 izole bölgesi ayrı kalır. 5 V SELV harici PSU; taşıyıcıda şebeke yok. Süperkapasitör yalnız mantık hattını tutar; LTE güç kesilmesinde kapanır.')}
for page_no,kind in enumerate(('TC','IR','PD','GW'),3):
 info=dimensions[kind];w,h,dep=info['outer_mm'];bw,bh,_=info['pcb_mm'];subtitle,note=notes[kind]
 page(page_no,f'{kind} / {subtitle}',f'PANOGOZ-{kind}-B1  •  Kutu {w} × {h} × {dep} mm  •  PCB {bw} × {bh} × 1,6 mm / 4 katman')
 pic(M/kind/'assembly.png',42,330,510,350);pic(B/kind/'pcb-3d.png',625,350,510,320)
 text('Parametrik STEP / şeffaf gövde / sadeleştirilmiş hacimler',42,311,11,'Bold');text('KiCad 3B / yerleşim aşaması / bakır yönlendirme yok',625,331,11,'Bold')
 sc=min(220/w,160/h);x,y=85,100;c.setStrokeColor(teal);c.setLineWidth(1.2);c.rect(x,y,w*sc,h*sc)
 ox,oy,_=info['board_origin_mm'];c.setDash(3,2);c.rect(x+ox*sc,y+oy*sc,bw*sc,bh*sc);c.setDash()
 dim(x,y-20,x+w*sc,y-20,str(w));dim(x-20,y,x-20,y+h*sc,str(h))
 sx=x+w*sc+48;c.rect(sx,y,dep*sc,h*sc);dim(sx,y-20,sx+dep*sc,y-20,str(dep))
 para('Üst / yan dış zarf<br/>Kesik çizgi: PCB izdüşümü<br/>Gövde et kalınlığı: '+str(info['wall_mm'])+' mm<br/>PCB altı tasarım payı: 5 mm',sx+dep*sc+25,255,200,10)
 para(note,625,294,510,12)
 para('Kaynaklar: '+kind+'/PANOGOZ-'+kind+'-B1.kicad_pro, pinmap.csv, circuit.json; mechanical/'+kind+'/assembly.step, base.step, lid.step. PCB ve mekanik görünüm ölçüm veya çevre test raporu değildir. Kapak kilidi/conta basısı ve bütün bileşenlerin 3B çakışması üretim öncesi gözden geçirilmelidir.',625,154,510,10)
 c.showPage()

page(7,'Teslim kanıtı ve açık sınırlar','K1 / 1.1-1.6  •  Kaynak dosyalar, test çıktıları ve doğrulama durumu')
v=json.loads((B/'verification.json').read_text());mem=json.loads((ROOT.parent/'firmware/node/build/stm32wle5/memory_report.json').read_text());bom=json.loads((B/'bom.json').read_text())
table([['Kontrol','TC','IR','PD','GW'],['Şematik ERC hata / uyarı','0 / 0','0 / 0','0 / 0','0 / 0'],['PCB-şematik eşleme','0 fark','0 fark','0 fark','0 fark'],['Yerleşim DRC ihlali','0','0','0','0'],['Yönlendirilmemiş bağlantı',*[v[k]['unconnected'] for k in ('TC','IR','PD','GW')]],['PCB kaynak / PNG / STEP mekanik','var','var','var','var']],42,690,[380,180,180,180,180])
text('Hedef derlemesi ve uç düğüm',42,403,18,'Bold')
para(f'STM32WLE5CC / TC-04 örnek imajı. Arm GNU 14.3.Rel1; {mem["flash_bytes"]:,} bayt flash, {mem["sram_reserved_bytes"]:,} bayt RAM (4096 bayt yığın dahil); 0 derleyici uyarısı, 0 çözümsüz sembol. BIN, ELF, MAP ve derleme günlüğü teslimdedir. TC-01..06 için --node seçeneği vardır. Fiziksel kartta çalışma test edilmedi.',42,377,520,12)
para('Host öz testi: 0 hata; kimlik, geçersiz CT ve enerji bütçesi regresyonları geçti. C radyo paketleri mevcut Envelope/kanal/cihaz sözleşmesine dönüştürülür. Gerçek sensör → GW → MQTT entegrasyonu bu aşamada yapılmış değildir. IR/PD sürücüleri, GW MCU firmware’i ve imzalı OTA hedef portu kapsamı açık geliştirme kalemidir.',42,263,520,12)
text('Maliyet, çevre ve üretim',610,403,18,'Bold')
para(f'BOM: {len(bom["rows"])} satın alma satırı. Doğrulanmış fiyatlı satırların kit ara toplamı {bom["known_subtotal_usd"]:.2f} USD; {bom["unpriced_line_count"]} satırın fiyat/termin/üretici kodu teklife bağlıdır. Bu rakam tam kit fiyatı değildir. K1 1.6 tam kapanmış sayılmaz. Fiyat gözlemleri 20.09.2026; kaynaklar BOM.md/bom.json içinde.',610,377,525,12)
para('Yerleşim aşaması: bakır izler, RF empedansı, termal akış, izolasyon testleri ve fabrika çıktıları tamamlanmadı. Gerber/üretim onayı verilmez. -25..+55°C pano ortamı bir tasarım hedefidir; IP, EMC ve titreşim uygunluğu ölçülmedi. TC pil ömrü ≈2 yıl hesabı varsayımdır; IR/PD görev çevrimi ayrıca ölçülmelidir.',610,263,525,12)
para('Kaynak dizini: hardware/README.md ve docs/02-03. Orijinal görev belgesindeki üç işlev grubu, repodaki TC / IR / PD / GW ayrımı nedeniyle dört fiziksel kartla teslim edilir. Ortak contracts dosyaları değiştirilmemiştir.',42,111,1080,11)
c.save();print('PDF ready',B/'K1-B1-TASARIM-DOSYASI.pdf')
