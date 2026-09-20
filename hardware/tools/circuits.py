"""B1 electrical source of truth. Each entry is a real component/pin/net mapping.

Reference footprints come from KiCad 10. Placement is a design-stage deliverable,
not a manufacturing release. No network access is performed by this generator.
"""
from pathlib import Path
import os, copy
from sexpr import parse, find, allof

KICAD=Path(os.environ.get('KICAD_SHARE',Path(os.environ.get('LOCALAPPDATA',''))/'Programs/KiCad/10.0/share/kicad'))
CACHE={}
def library(spec):
    lib,name=spec.split(':')
    if lib not in CACHE:
        CACHE[lib]={str(s[1]):s for s in allof(parse((KICAD/'symbols'/(lib+'.kicad_sym')).read_text(encoding='utf8')),'symbol')}
    s=copy.deepcopy(CACHE[lib][name]); ext=find(s,'extends')
    if ext:
        base=library(lib+':'+str(ext[1])); props={str(p[1]):p for p in allof(s,'property')}
        s=[props.get(str(p[1]),p) if isinstance(p,list) and p[0]=='property' else p for p in base]
    return s
def pinlist(s):
    return [(str(find(p,'number')[1]),str(find(p,'name')[1]),str(p[1])) for sub in allof(s,'symbol') for p in allof(sub,'pin')]

RFP='Resistor_SMD:R_0402_1005Metric'
CFP='Capacitor_SMD:C_0402_1005Metric'
SOT='Package_TO_SOT_SMD:SOT-23-5'
QFN='Package_DFN_QFN:QFN-48-1EP_7x7mm_P0.5mm_EP5.6x5.6mm'
class Circuit:
    def __init__(self,kind,w,h):
        self.kind=kind; self.w=w; self.h=h; self.cs=[]; self.idx={}; self.group='POWER'; self.rail='V3V0' if kind=='TC' else 'V3V3'
        self.notes=[]; self.keepouts=[]
    def add(self,value,spec,nets,fp=None,ref=None,mpn=None,place=None,side='F',note='',pins=None):
        prefix='U'
        if spec in ('Device:R','Device:C','Device:L','Device:D_Schottky','Device:D_TVS','Device:Crystal','Device:Crystal_GND24'):
            prefix={'Device:R':'R','Device:C':'C','Device:L':'L','Device:D_Schottky':'D','Device:D_TVS':'D','Device:Crystal':'Y','Device:Crystal_GND24':'Y'}[spec]
        if spec.startswith('Connector'):prefix='J'
        if spec.startswith('Transistor'):prefix='Q'
        if ref is None:
            while ref is None or any(c['ref']==ref for c in self.cs):
                self.idx[prefix]=self.idx.get(prefix,0)+1; ref=prefix+str(self.idx[prefix])
        if pins is None:
            s=library(spec); pins=pinlist(s)
            if fp is None:fp=str(next(p[2] for p in allof(s,'property') if p[1]=='Footprint'))
        if not fp: raise ValueError((value,'No footprint'))
        ns={str(k):v for k,v in nets.items()}
        assert set(ns)<=set(n for n,_,_ in pins),(value,set(ns)-set(n for n,_,_ in pins))
        c=dict(ref=ref,value=value,spec=spec,pins=pins,fp=fp,nets=ns,group=self.group,mpn=mpn or value,note=note,place=place,side=side)
        self.cs.append(c);return c
    def custom(self,name,pins,nets,fp,**kw):
        return self.add(name,'B1:'+name,nets,fp,pins=[(str(i),n,t) for i,n,t in pins],**kw)
    def r(self,val,a,b,**kw):return self.add(val,'Device:R',{1:a,2:b},kw.pop('fp',RFP),mpn='1% thick film '+val,**kw)
    def c(self,val,a,b='GND',**kw):return self.add(val,'Device:C',{1:a,2:b},kw.pop('fp',CFP),mpn='X7R 16V '+val,**kw)
    def l(self,val,a,b,**kw):return self.add(val,'Device:L',{1:a,2:b},kw.pop('fp','Inductor_SMD:L_0402_1005Metric'),**kw)
    def j(self,name,nets,fp=None,**kw):
        return self.add(name,'Connector_Generic:Conn_01x%02d'%len(nets),dict(enumerate(nets,1)),fp or 'Connector_JST:JST_SH_SM%02dB-SRSS-TB_1x%02d-1MP_P1.00mm_Horizontal'%(len(nets),len(nets)),**kw)
    def op(self,name,plus,minus,out,v=None,**kw):
        return self.custom(name,[(1,'OUT','output'),(2,'V-','power_in'),(3,'IN+','input'),(4,'IN-','input'),(5,'V+','power_in')],{1:out,2:'GND',3:plus,4:minus,5:v or self.rail},SOT,**kw)
    def mos(self,name,g,s,d,**kw):
        return self.add(name,'Transistor_FET:AO3401A' if name=='AO3401A' else 'Transistor_FET:2N7002',{1:g,2:s,3:d},'Package_TO_SOT_SMD:SOT-23',**kw)

def wl_node(d):
    v=d.rail
    d.group='POWER'
    d.j('CELL + HLC', ['VBAT','GND'],place=None)
    if d.kind=='TC':
        d.custom('TPS7A0230PDBVR',[(1,'IN','power_in'),(2,'GND','power_in'),(3,'EN','input'),(4,'NC','no_connect'),(5,'OUT','power_out')],{1:'VBAT',2:'GND',3:'VBAT',5:v},SOT)
        d.c('1uF','VBAT'); d.c('1uF',v)
    else:
        d.add('TPS63900DSKR','Regulator_Switching:TPS63900',{1:'VBAT',2:'GND',3:'CFG1',4:'GND',5:'CFG3',6:v,7:'LX2',8:'GND',9:'LX1',10:'VBAT',11:'GND'})
        d.l('2.2uH Isat>=1A','LX1','LX2',fp='Inductor_SMD:L_0805_2012Metric')
        d.r('36.5k','CFG1','GND');d.r('16.2k','CFG3','GND')
        d.c('10uF','VBAT',fp='Capacitor_SMD:C_0805_2012Metric');d.c('22uF',v,fp='Capacitor_SMD:C_0805_2012Metric')
    # A two-transistor switch prevents 3.6 V on the 3.0 V GPIO and fully turns off the divider.
    d.mos('AO3401A','DIV_GATE','VBAT','DIV_SUPPLY')
    d.mos('2N7002','DIV_EN','GND','DIV_GATE')
    d.r('1M','DIV_GATE','VBAT');d.r('1M','DIV_EN','GND')
    d.r('100k','DIV_SUPPLY','BAT_ADC');d.r('100k','BAT_ADC','GND');d.c('10nF','BAT_ADC')
    d.r('68R 0.5W','VBAT','LOAD_D',fp='Resistor_SMD:R_1210_3225Metric')
    d.mos('2N7002','LOAD_EN','GND','LOAD_D');d.r('100k','LOAD_EN','GND')
    d.group='MCU'
    pins={1:'MOUNT_N',2:'DIV_EN',3:'LOAD_EN',4:'I2C_SCL',5:'I2C_SDA',7:'CT_ADC' if d.kind=='TC' else ('PD_ADC' if d.kind=='PD' else None),9:'BAT_ADC',11:v,12:'FRAM_CS',13:'SPI_SCK',14:'SPI_MISO',15:'SPI_MOSI',16:'PHASE',17:'PD_PULSE' if d.kind=='PD' else None,18:'NRST',19:'BOOT0',20:'RFI_P',21:'RFI_N',22:'RFO_LP',24:'VR_PA',25:'V1V55',26:'HSE_IN',27:'HSE_OUT',28:v,29:'V1V55',30:'RF_CTRL',32:'RF_CTRL_N',36:'SWDIO',37:v,39:'LSE_IN',40:'LSE_OUT',41:'VDDA',42:'SWCLK',44:v,45:'V1V55',46:v,48:'GND',49:'GND'}
    if d.kind=='PD':pins.update({8:'PD_EN',10:'ULTRA_ADC',33:'TEV_SEL',34:'TEV_SEL_N'})
    d.add('STM32WLE5CCU6','MCU_ST_STM32WL:STM32WLE5CCUx',pins,QFN,ref='U10',place=(d.w*.48,d.h*.49))
    d.r('10k','BOOT0','GND');d.r('10k','NRST',v);d.c('100nF','NRST')
    d.j('SWD TC2030',[v,'SWDIO','GND','SWCLK','NRST',None],fp='Connector:Tag-Connect_TC2030-IDC-NL_2x03_P1.27mm_Vertical',side='B')
    d.j('MOUNT switch',['MOUNT_N','GND']);d.r('100k','MOUNT_N',v)
    for _ in range(4):d.c('100nF',v)
    d.c('4.7uF',v);d.c('4.7uF','V1V55');d.c('100nF','V1V55')
    d.r('0R','VDDA',v);d.c('100nF','VDDA');d.c('1uF','VDDA')
    d.add('32MHz CL=10pF','Device:Crystal_GND24',{1:'HSE_IN',2:'GND',3:'HSE_OUT',4:'GND'},'Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm',note='Internal HSE tuning capacitors; trim before RF qualification')
    d.add('32.768kHz CL=6pF','Device:Crystal',{1:'LSE_IN',2:'LSE_OUT'},'Crystal:Crystal_SMD_3215-2Pin_3.2x1.5mm');d.c('6pF','LSE_IN');d.c('6pF','LSE_OUT')
    d.add('MB85RS64V','Memory_NVRAM:MB85RS64',{1:'FRAM_CS',2:'SPI_MISO',3:v,4:'GND',5:'SPI_MOSI',6:'SPI_SCK',7:v,8:v},'Package_SO:SOIC-8_3.9x4.9mm_P1.27mm')
    d.r('100k','FRAM_CS',v);d.c('100nF',v)
    d.r('4.7k','I2C_SCL',v);d.r('4.7k','I2C_SDA',v)
    d.group='RADIO'
    # Differential receive network and low-power transmit branch; values require VNA tuning on routed board.
    d.l('47nH','VR_PA','RFO_LP');d.c('47nF','VR_PA');d.c('68pF','VR_PA')
    d.l('4.4nH','RFO_LP','TX_1');d.c('5.5pF','RFO_LP');d.c('2.5pF','TX_1')
    d.l('3.4nH','TX_1','TX_2');d.c('4.3pF','TX_2');d.c('68pF','TX_2','TX_3')
    d.l('9.2nH','TX_3','TX_RF');d.c('3.5pF','TX_RF')
    d.c('4.5pF','RX_RF','RFI_P');d.l('12nH','RFI_P','RFI_N');d.c('2.7pF','RFI_N')
    d.custom('PE4259',[(1,'RF1','passive'),(2,'GND','power_in'),(3,'RF2','passive'),(4,'CTRL','input'),(5,'RFC','passive'),(6,'CTRL_N','input')],{1:'TX_RF',2:'GND',3:'RX_RF',4:'RF_CTRL',5:'RF_COMMON',6:'RF_CTRL_N'},'Package_TO_SOT_SMD:SOT-363_SC-70-6')
    d.c('68pF','RF_COMMON','ANT');d.add('868 MHz u.FL','Connector:Conn_Coaxial',{1:'ANT',2:'GND'},'Connector_Coaxial:U.FL_Hirose_U.FL-R-SMT-1_Vertical',place=(d.w-3,3),note='Insulated 868 MHz antenna in enclosure; 50 ohm feed, no mains contact')
    d.keepouts.append(('ANTENNA_EXIT',(d.w-6,0,d.w,6)))

def tc():
    d=Circuit('TC',30,22);wl_node(d);d.group='SENSORS';v=d.rail
    d.add('TMP117AIDRVR','Sensor_Temperature:TMP117xxDRV',{1:'I2C_SCL',2:'GND',4:'GND',5:v,6:'I2C_SDA'},'Package_SON:WSON-6-1EP_2x2mm_P0.65mm_EP1x1.6mm',place=(3,4),note='Industrial -55..150C ordering code; EP grounded on thermal island; no plane fill or vias in keepout; final thermal neck requires routed-board validation')
    d.cs[-1]['pins'].append(('7','EP','power_in'));d.cs[-1]['nets']['7']='GND'
    d.c('100nF',v)
    d.j('CT 3000:1',['CT_PLUS','CT_MINUS'],place=(5,14),note='400A rated split core; captive 5.6V bidirectional secondary clamp mandatory')
    d.r('5.1R 0.1% 0.5W','CT_PLUS','CT_MINUS',fp='Resistor_SMD:R_1210_3225Metric',note='Direct secondary burden, never put 100R in primary burden path')
    # AC coupling keeps CT current in its own closed burden loop instead of forcing it into Vmid.
    d.r('0R','CT_MINUS','GND');d.c('1uF','CT_PLUS','CT_AC');d.r('100k','CT_AC','VMID');d.r('1k','CT_AC','CT_ADC');d.c('47nF','CT_ADC')
    d.r('1M',v,'MID_DIV');d.r('1M','MID_DIV','GND');d.c('1uF','MID_DIV')
    d.op('OPA333AIDBVR','MID_DIV','VMID','VMID');d.c('100nF',v)
    d.add('BAT54S','Diode:BAT54S',{1:'GND',2:v,3:'CT_ADC'},'Package_TO_SOT_SMD:SOT-23')
    d.custom('TLV3691IDCKR',[(1,'IN+','input'),(2,'GND','power_in'),(3,'IN-','input'),(4,'OUT','output'),(5,'VDD','power_in')],{1:'CT_ADC',2:'GND',3:'VMID',4:'PHASE',5:v},'Package_TO_SOT_SMD:SOT-353_SC-70-5',note='CT zero crossings are current phase only; not a voltage-phase PRPD reference')
    d.keepouts.append(('THERMAL_ISLAND',(0,0,6,7)))
    return d

def ir():
    d=Circuit('IR',45,35);wl_node(d);d.group='SENSORS';v=d.rail
    for c in d.cs:
        if c['ref']=='U10':c['nets']['8']='SENS_EN'
        if c['spec']=='Device:R' and any(n in ('I2C_SCL','I2C_SDA') for n in c['nets'].values()):
            c['nets']={p:('SENS_3V3' if n==v else n) for p,n in c['nets'].items()}
    d.mos('AO3401A','SENS_GATE',v,'SENS_3V3');d.mos('2N7002','SENS_EN','GND','SENS_GATE');d.r('100k','SENS_GATE',v);d.r('100k','SENS_EN','GND')
    v='SENS_3V3'
    d.custom('MLX90640ESF-BAA-000-TU',[(1,'SDA','bidirectional'),(2,'VDD','power_in'),(3,'VSS','power_in'),(4,'SCL','input')],{1:'I2C_SDA',2:v,3:'GND',4:'I2C_SCL'},'Package_TO_SOT_THT:TO-39-4_Window',place=(9,8),note='110x75 degree FoV, PCB top towards lugs; optical opening must transmit LWIR')
    d.c('100nF',v);d.c('10uF',v,fp='Capacitor_SMD:C_0805_2012Metric')
    d.add('SHT41-AD1B-R2','Sensor_Humidity:SHT4x',{1:'I2C_SDA',2:'I2C_SCL',3:v,4:'GND'},place=(3,29),note='Vent membrane; no conformal coat over aperture')
    d.c('100nF',v);d.j('PHASE optional',['PHASE','GND'])
    return d

def pd():
    d=Circuit('PD',70,50);wl_node(d);v=d.rail
    d.group='PD_POWER'
    d.custom('TPS61023DRLR',[(1,'FB','input'),(2,'EN','input'),(3,'VIN','power_in'),(4,'GND','power_in'),(5,'SW','passive'),(6,'VOUT','power_out')],{1:'PD_FB',2:'PD_EN',3:'VBAT',4:'GND',5:'PD_SW',6:'PD_5V'},'Package_TO_SOT_SMD:SOT-563')
    d.l('1uH Isat>=4A','VBAT','PD_SW',fp='Inductor_SMD:L_1210_3225Metric')
    d.r('732k','PD_5V','PD_FB');d.r('100k','PD_FB','GND');d.r('100k','PD_EN','GND')
    d.c('10uF','VBAT',fp='Capacitor_SMD:C_0805_2012Metric');d.c('22uF','PD_5V',fp='Capacitor_SMD:C_0805_2012Metric')
    d.group='PD_ANALOG'
    for name,net,xy in [('HFCT50','HFCT_IN',(5,10)),('TEV plate','TEV_IN',(5,24))]:
        d.add(name,'Connector:Conn_Coaxial',{1:net,2:'GND'},'Connector_Coaxial:SMA_Amphenol_132134_Vertical',place=xy)
        d.r('49.9R',net,'GND');d.c('10nF',net,net+'_AC')
    d.custom('PE4259',[(1,'RF1','passive'),(2,'GND','power_in'),(3,'RF2','passive'),(4,'CTRL','input'),(5,'RFC','passive'),(6,'CTRL_N','input')],{1:'HFCT_IN_AC',2:'GND',3:'TEV_IN_AC',4:'TEV_SEL',5:'RF_PD_SEL',6:'TEV_SEL_N'},'Package_TO_SOT_SMD:SOT-363_SC-70-6',note='Complementary CTRL/CTRL_N; sequential channel acquisition, not simultaneous pulses')
    d.c('100nF',v);d.c('100pF','RF_PD_SEL','RF_PD_1');d.l('1uH','RF_PD_1','GND',note='10 MHz high-pass starting network, qualify amplitude transfer')
    d.add('PGA-103+','RF_Amplifier:PGA-103',{1:'RF_PD_1',2:'GND',3:'RF_PD_AMP'},'Package_TO_SOT_SMD:SOT-89-3')
    d.l('1uH','PD_5V','RF_PD_AMP',fp='Inductor_SMD:L_0805_2012Metric');d.c('100nF','PD_5V');d.c('1nF','RF_PD_AMP','LOG_IN')
    p=[(i,n,t) for i,n,t in [(1,'CMIP','power_in'),(2,'CMIP','power_in'),(3,'VPSI','power_in'),(4,'VPSI','power_in'),(5,'CLPF','passive'),(6,'VOUT','output'),(7,'VSET','input'),(8,'CMOP','power_in'),(9,'VPSO','power_in'),(10,'TADJ','passive'),(11,'CMIP','power_in'),(12,'CMIP','power_in'),(13,'TEMP','output'),(14,'INHI','input'),(15,'INLO','input'),(16,'ENBL','input'),(17,'EP','power_in')]]
    d.custom('AD8318ACPZ',p,{1:'GND',2:'GND',3:'PD_5V',4:'PD_5V',5:'LOG_CLPF',6:'LOG_OUT',7:'LOG_OUT',8:'GND',9:'PD_5V',10:'LOG_TADJ',11:'GND',12:'GND',14:'LOG_IN',15:'LOG_LO',16:'PD_EN',17:'GND'},'Package_CSP:Analog_LFCSP-16-1EP_4x4mm_P0.65mm_EP2.35x2.35mm')
    d.c('1nF','LOG_LO');d.c('220pF','LOG_CLPF');d.r('499R','LOG_TADJ','GND');d.c('100nF','PD_5V');d.c('10nF','PD_5V')
    # ADC sees raw negative log slope; PD firmware must convert before positive-amplitude PRPD bins.
    d.r('1k','LOG_OUT','PD_ADC');d.c('1nF','PD_ADC')
    d.custom('TLV3201AIDBVR',[(1,'OUT','output'),(2,'V-','power_in'),(3,'IN+','input'),(4,'IN-','input'),(5,'V+','power_in')],{1:'PD_PULSE',2:'GND',3:'PD_THRESHOLD',4:'LOG_OUT',5:v},SOT)
    d.r('100k',v,'PD_THRESHOLD');d.r('100k','PD_THRESHOLD','GND');d.c('100nF','PD_THRESHOLD')
    d.group='ENV_ULTRASOUND'
    d.add('SHT41-AD1B-R2','Sensor_Humidity:SHT4x',{1:'I2C_SDA',2:'I2C_SCL',3:v,4:'GND'},place=(65,43));d.c('100nF',v)
    d.j('MA40S4R receiver',['US_IN','GND']);d.c('10nF','US_IN','US_AC');d.r('100k','US_AC','US_MID')
    d.r('100k',v,'US_MID');d.r('100k','US_MID','GND');d.c('1uF','US_MID')
    d.mos('AO3401A','PD3_GATE',v,'PD_A3V3');d.mos('2N7002','PD_EN','GND','PD3_GATE');d.r('100k','PD3_GATE',v)
    d.op('OPA320AIDBVR','US_AC','US_FB','ULTRA_ADC',v='PD_A3V3');d.r('100k','ULTRA_ADC','US_FB');d.r('10k','US_FB','US_MID');d.c('100nF','PD_A3V3')
    for c in d.cs:
        if c['value']=='TLV3201AIDBVR':c['nets']['5']='PD_A3V3'
        if c['spec']=='Device:R' and any(n in ('PD_THRESHOLD','US_MID') for n in c['nets'].values()):
            c['nets']={p:('PD_A3V3' if n==v else n) for p,n in c['nets'].items()}
    d.j('ISOLATED 50Hz PHASE',['PHASE','GND'],note='SELV 0..3.3 V from isolated voltage reference; never connect line voltage')
    return d

def gw():
    d=Circuit('GW',100,90);v=d.rail
    d.j('5V SELV 4A', ['V5_IN','GND'],fp='TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-2-5.08_1x02_P5.08mm_Horizontal',place=(10,81),note='External isolated DIN 5V supply; no mains on this PCB')
    d.add('3.15A slow','Device:Fuse',{1:'V5_IN',2:'V5_FUSED'},'Fuse:Fuse_1206_3216Metric',ref='F1')
    d.mos('AO3401A','GND','V5','V5_FUSED');d.c('100uF','V5',fp='Capacitor_SMD:C_1210_3225Metric')
    for suffix,out in [('LOGIC',v),('LTE','LTE_3V3')]:
        d.add('TPS62130RGTR','Regulator_Switching:TPS62130',{1:'SW_'+suffix,2:'SW_'+suffix,3:'SW_'+suffix,5:'FB_'+suffix,6:'GND',7:'GND',8:'GND',9:'SS_'+suffix,10:'V5',11:'V5',12:'V5',13:'V5',14:out,15:'GND',16:'GND',17:'GND'})
        d.l('2.2uH Isat>=4A','SW_'+suffix,out,fp='Inductor_SMD:L_1210_3225Metric');d.r('316k',out,'FB_'+suffix);d.r('100k','FB_'+suffix,'GND');d.c('10nF','SS_'+suffix)
        d.c('22uF','V5',fp='Capacitor_SMD:C_0805_2012Metric');d.c('47uF',out,fp='Capacitor_SMD:C_1210_3225Metric')
    d.c('470uF low ESR','LTE_3V3',fp='Capacitor_SMD:CP_Elec_8x10')
    d.group='MCU_MEMORY'
    pins=pinlist(library('MCU_ST_STM32H5:STM32H563ZITx'))
    ns={int(n):('GND' if name.startswith('VSS') else v) for n,name,t in pins if name.startswith(('VDD','VSS'))}
    ns.update({6:v,8:'LSE_IN',9:'LSE_OUT',23:'HSE_IN',24:'HSE_OUT',25:'NRST',32:v,33:v,35:'ETH_CLK50',36:'ETH_MDIO',43:'ETH_CRS',44:'ETH_RXD0',45:'ETH_RXD1',27:'ETH_MDC',69:'RS1_TX',73:'RS1_DE',74:'ETH_TXEN',75:'ETH_TXD0',76:'ETH_TXD1',77:'RS2_TX',78:'RS2_RX',79:'RS2_DE',136:'GW_SCL',137:'GW_SDA',103:'USB_DM',104:'USB_DP',105:'SWDIO',109:'SWCLK',138:'BOOT0',70:'VCAP1',142:'VCAP2',41:'RF_SCK',42:'RF_MISO',135:'RF_MOSI',40:'RF_CS',46:'RF_BUSY',47:'RF_DIO1',48:'RF_RST',12:'FLASH_CS',19:'MEM_IO0',20:'MEM_IO1',21:'MEM_IO2',22:'MEM_IO3',125:'MEM_CLK',124:'RAM_CS',96:'RS1_RX',97:'ETH_RST'})
    # USART3 PB10/PC11 is not a valid mixed pair; use PD8/PD9 for USART3 and PD5/PD6 for USART2.
    ns[69]=None;ns[96]=None;ns[77]='RS1_TX';ns[78]='RS1_RX';ns[119]='RS2_TX';ns[122]='RS2_RX'
    # DS14258 Rev 6 table 16, LQFP144: AF10 IO[0:3], AF9 CLK; GPIO CS,
    # indirect transactions only (both CS high at idle; never memory-mapped).
    ns.update({18:'MEM_IO3',19:'MEM_IO2',20:'MEM_IO0',21:'MEM_IO1',22:'MEM_CLK',125:None})
    # RMII AF11 outputs. PB13/14/15 were not the selected H563 RMII pin set.
    ns.update({74:None,75:None,76:None,126:'ETH_TXEN',128:'ETH_TXD0',129:'ETH_TXD1'})
    d.add('STM32H563ZIT6','MCU_ST_STM32H5:STM32H563ZITx',ns,ref='U20',place=(18,48))
    d.c('2.2uF','VCAP1');d.c('2.2uF','VCAP2')
    for _ in range(14):d.c('100nF',v)
    d.c('10uF',v,fp='Capacitor_SMD:C_0805_2012Metric');d.r('10k','NRST',v);d.c('100nF','NRST');d.r('10k','BOOT0','GND')
    d.add('25MHz CL=12pF','Device:Crystal_GND24',{1:'HSE_IN',2:'GND',3:'HSE_OUT',4:'GND'},'Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm');d.c('18pF','HSE_IN');d.c('18pF','HSE_OUT')
    d.add('32.768kHz','Device:Crystal',{1:'LSE_IN',2:'LSE_OUT'},'Crystal:Crystal_SMD_3215-2Pin_3.2x1.5mm');d.c('6pF','LSE_IN');d.c('6pF','LSE_OUT')
    d.j('SWD TC2030',[v,'SWDIO','GND','SWCLK','NRST',None],fp='Connector:Tag-Connect_TC2030-IDC-NL_2x03_P1.27mm_Vertical',side='B')
    mp=[(1,'CS','input'),(2,'IO1','bidirectional'),(3,'IO2','bidirectional'),(4,'GND','power_in'),(5,'IO0','bidirectional'),(6,'CLK','input'),(7,'IO3','bidirectional'),(8,'VCC','power_in')]
    for name,cs in [('W25Q64JVSSIQ','FLASH_CS'),('APS6404L-3SQR-SN','RAM_CS')]:
        d.custom(name,mp,{1:cs,2:'MEM_IO1',3:'MEM_IO2',4:'GND',5:'MEM_IO0',6:'MEM_CLK',7:'MEM_IO3',8:v},'Package_SO:SOIC-8_3.9x4.9mm_P1.27mm');d.r('10k',cs,v);d.c('100nF',v)
    d.add('RV-3028-C7','Timer_RTC:RV-3028-C7',{3:'GW_SCL',4:'GW_SDA',5:'GND',6:'RTC_BACKUP',7:v,8:'GND'})
    d.j('RTC primary cell',['RTC_BACKUP','GND']);d.c('100nF',v);d.r('4.7k','GW_SCL',v);d.r('4.7k','GW_SDA',v)
    d.group='ETHERNET'
    d.add('LAN8742A-CZ-TR','Interface_Ethernet:LAN8742A',{1:v,2:'PHY_INTSEL',3:'PHY_REGOFF',5:'ETH_CLK50',6:'VDDCR',7:'ETH_RXD1',8:'ETH_RXD0',9:v,10:'PHY_ADDR',11:'ETH_CRS',12:'ETH_MDIO',13:'ETH_MDC',15:'ETH_RST',16:'ETH_TXEN',17:'ETH_TXD0',18:'ETH_TXD1',19:v,20:'TXN',21:'TXP',22:'RXN',23:'RXP',24:'RBIAS',25:'GND'},place=(16,29))
    d.custom('50MHz 3V3 OSC',[(1,'OE','input'),(2,'GND','power_in'),(3,'OUT','output'),(4,'VDD','power_in')],{1:v,2:'GND',3:'ETH_CLK50',4:v},'Oscillator:Oscillator_SMD_Abracon_ASE-4Pin_3.2x2.5mm');d.c('100nF',v)
    for net,rail in [('PHY_INTSEL',v),('PHY_REGOFF','GND'),('PHY_ADDR','GND'),('ETH_RXD0',v),('ETH_RXD1',v),('ETH_CRS',v),('ETH_MDIO',v),('ETH_RST',v)]:d.r('10k',net,rail)
    d.r('12.1k 1%','RBIAS','GND');d.c('1uF','VDDCR');d.c('100nF','VDDCR')
    for _ in range(3):d.c('100nF',v)
    d.add('HR911105A','Connector:RJ45_Hanrun_HR911105A_Horizontal',{1:'TXP',2:'TXN',3:'RXP',4:'ETH_CT',5:'ETH_CT',6:'RXN',8:'CHASSIS','SH':'CHASSIS'},place=(10,6),note='Internal magnetics; connector shield to functional chassis point')
    d.c('100nF','ETH_CT');d.r('1M','CHASSIS','GND');d.c('1nF 2kV','CHASSIS','GND',fp='Capacitor_SMD:C_1206_3216Metric')
    d.group='RS485'
    for i,y in [(1,17),(2,49)]:
        g='ISO%d_GND'%i;iv='ISO%d_V'%i;a='RS%d_A'%i;b='RS%d_B'%i
        d.add('ADM2587EBRWZ','Interface_UART:ADM2587E',{1:'GND',2:v,3:'GND',4:'RS%d_RX'%i,5:'RS%d_DE'%i,6:'RS%d_DE'%i,7:'RS%d_TX'%i,8:v,9:'GND',10:'GND',11:g,12:iv,13:a,14:g,15:b,16:g,17:b,18:a,19:iv,20:g},place=(74,y))
        for rail,gn in [(v,'GND'),(iv,g)]:
            d.c('100nF',rail,gn);d.c('100nF',rail,gn);d.c('10uF',rail,gn,fp='Capacitor_SMD:C_0805_2012Metric')
        d.r('10k','RS%d_DE'%i,'GND');d.r('10k','RS%d_TX'%i,v)
        d.j('MPR' if i==1 else 'TVOC',[a,b,g],fp='TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-3-5.08_1x03_P5.08mm_Horizontal',place=(85,y-5))
        d.custom('SM712',[(1,'A','passive'),(2,'B','passive'),(3,'GND','passive')],{1:a,2:b,3:g},'Package_TO_SOT_SMD:SOT-23')
        d.r('120R',a,'TERM%d'%i,fp='Resistor_SMD:R_0805_2012Metric');d.j('TERM OPEN',['TERM%d'%i,b],fp='Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical',note='Shunt only at bus endpoint')
        d.keepouts.append(('RS%d_ISOLATION'%i,(72,y-10,76,y+10)))
    d.group='LORA'
    # Same SX1262 radio architecture; the matched RF network and 32 MHz crystal
    # are implemented in a documented 10x10 mm Ebyte module.
    for c in d.cs:
        if c['ref']=='U20':c['nets'].update({'10':'RF_TXEN','11':'RF_RXEN'})
    pn=[(1,'VCC','power_in'),(2,'GND','power_in'),(3,'NRST','input'),(4,'NC','no_connect'),(5,'NC','no_connect'),(6,'ANT','passive'),(7,'GND','power_in'),(8,'NC','no_connect'),(9,'TXEN','input'),(10,'RXEN','input'),(11,'BUSY','output'),(12,'MISO','output'),(13,'MOSI','input'),(14,'NSS','input'),(15,'SCK','input'),(16,'GND','power_in'),(17,'NC','no_connect'),(18,'DIO3','bidirectional'),(19,'DIO2','bidirectional'),(20,'DIO1','bidirectional')]
    d.custom('E22-900MM22S SX1262',pn,{1:v,2:'GND',3:'RF_RST',6:'GW_ANT',7:'GND',9:'RF_TXEN',10:'RF_RXEN',11:'RF_BUSY',12:'RF_MISO',13:'RF_MOSI',14:'RF_CS',15:'RF_SCK',16:'GND',20:'RF_DIO1'},'B1:E22-900MM22S',place=(22,69),mpn='E22-900MM22S')
    d.c('100nF',v);d.c('10uF',v,fp='Capacitor_SMD:C_0805_2012Metric');d.r('10k','RF_CS',v);d.r('10k','RF_RST',v);d.r('100k','RF_TXEN','GND');d.r('100k','RF_RXEN','GND')
    d.add('868MHz antenna','Connector:Conn_Coaxial',{1:'GW_ANT',2:'GND'},'Connector_Coaxial:U.FL_Hirose_U.FL-R-SMT-1_Vertical',place=(25,82))
    d.group='LTE'
    pn={i:('GND' if i in [4,9,15,18,21,26,27,29,34,35,37,40,43,50] else 'LTE_3V3' if i in [2,39,41,52] else None) for i in range(1,53)}
    pn.update({8:'SIM_VDD',10:'SIM_IO',12:'SIM_CLK',14:'SIM_RST',36:'USB_DM',38:'USB_DP'})
    d.custom('EC21-E MiniPCIe SOCKET',[(i,'PIN_%d'%i,'passive') for i in range(1,53)],pn,'B1:TE_2041119_1',place=(48,77),mpn='2041119-1',note='TE drawing C-2041119 rev D sheet 2; EC21 MiniPCIe V1.5 pin assignment')
    d.j('SIM connector',['SIM_VDD','SIM_RST','SIM_CLK','GND','SIM_IO',None],fp='Connector_PinHeader_2.00mm:PinHeader_1x06_P2.00mm_Vertical',note='External enclosed SIM socket harness <=50mm; six pins by signal name, not ISO contact order')
    d.keepouts.append(('LTE_CARD_ENVELOPE',(34,24,64,78)))
    # Independent UART option on the MiniPCIe form factor (3.3 V per Quectel section 3.8).
    for c in d.cs:
        if c['ref']=='U20':c['nets'].update({'101':'LTE_TX','102':'LTE_RX','34':'PFAIL_ADC'})
        if c['value']=='EC21-E MiniPCIe SOCKET':c['nets'].update({'11':'LTE_TX','13':'LTE_RX'})
    d.group='HOLDUP'
    # Two external EDLCs, series balancing, resistor-limited charge and reverse blocking.
    # Hold-up feeds only LOGIC buck. LTE is on the original V5 supply and loses power immediately.
    for c in d.cs:
        if c['value']=='TPS62130RGTR' and c['nets'].get('14')=='V3V3':
            for n in ('10','11','12','13'):c['nets'][n]='V5_HOLD'
    d.add('SS34','Device:D_Schottky',{1:'V5_HOLD',2:'V5'},'Diode_SMD:D_SMA')
    d.add('SS34','Device:D_Schottky',{1:'V5_HOLD',2:'SC_TOP'},'Diode_SMD:D_SMA')
    d.add('BAT54','Device:D_Schottky',{1:'SC_CHARGE',2:'V5'},'Diode_SMD:D_SOD-123')
    d.r('100R 1W','SC_CHARGE','SC_TOP',fp='Resistor_SMD:R_2512_6332Metric')
    d.j('2x10F 2.7V EDLC pack',['SC_TOP','SC_MID','GND'],note='Enclosed 2-cell series pack, 10k balancing resistors are on carrier; never short or reverse pack')
    d.r('10k','SC_TOP','SC_MID');d.r('10k','SC_MID','GND');d.c('22uF','V5_HOLD',fp='Capacitor_SMD:C_0805_2012Metric')
    d.r('100k','V5','PFAIL_ADC');d.r('100k','PFAIL_ADC','GND');d.c('10nF','PFAIL_ADC')
    d.notes.append('SX1262 is inside E22-900MM22S. EC21-E uses the MiniPCIe 3.3V form factor. Manufacturing routing and qualification follow this placement stage.')
    return d
