"""Generate editable KiCad design documents. Run with KiCad's Python (pcbnew).

Usage: python generate.py [TC IR PD GW]. Set KICAD_SHARE if not in the default
Windows user installation. This does not download dependencies or route PCBs.
"""
from pathlib import Path
import json, math, uuid, copy, sys, csv, shutil
import pcbnew as p
from sexpr import Q, parse, dump, find, allof
from circuits import KICAD, tc, ir, pd, gw

OUT=Path(__file__).resolve().parents[1]/'B1'
def uid(s):return str(uuid.uuid5(uuid.NAMESPACE_URL,'panogoz/B1/'+s))
def q(s):return json.dumps(str(s),ensure_ascii=False)
def v(x,y):return p.VECTOR2I(p.FromMM(x),p.FromMM(y))
def line(parent,points,layer,width=.1):
    for a,b in zip(points,points[1:]):
        s=p.PCB_SHAPE(parent);s.SetShape(p.SHAPE_T_SEGMENT);s.SetStart(v(*a));s.SetEnd(v(*b));s.SetWidth(p.FromMM(width));s.SetLayer(layer);parent.Add(s)
def rect(parent,box,layer,width=.1):
    x1,y1,x2,y2=box;line(parent,[(x1,y1),(x2,y1),(x2,y2),(x1,y2),(x1,y1)],layer,width)
def pcb_text(board,s,x,y,layer=p.Dwgs_User,size=1):
    t=p.PCB_TEXT(board);t.SetText(s);t.SetPosition(v(x,y));t.SetTextSize(v(size,size));t.SetTextThickness(p.FromMM(.12));t.SetLayer(layer);board.Add(t)

def normalized(c):
    # Retain real electrical types and physical pin numbers. Names are not generic block ports.
    nm=c['ref'];pins=c['pins'];half=math.ceil(len(pins)/2);h=max(3.81,(half-1)*1.27+2.54);w=12.7
    ss=[]
    for i,(num,name,typ) in enumerate(pins):
        right=i>=half;x=w+5.08 if right else -w-5.08;y=(half-1)*1.27-(i%half)*2.54;a=180 if right else 0
        ss.append(f'(pin {typ} line (at {x} {y} {a}) (length 5.08) (name {q(name)} (effects (font (size .9 .9)))) (number {q(num)} (effects (font (size .9 .9)))))')
    s=f'(symbol {q(nm)} (pin_names (offset .5)) (in_bom yes) (on_board yes) (property "Reference" "U" (at 0 {h+5} 0) (effects (font (size 1 1)))) (property "Value" {q(c["value"])} (at 0 {-h-3} 0) (effects (font (size 1 1)))) (symbol {q(nm+"_0_1")} (rectangle (start {-w} {h}) (end {w} {-h}) (stroke (width .254) (type default)) (fill (type background)))) (symbol {q(nm+"_1_1")} {" ".join(ss)}))'
    parsed=parse(s)
    if c['spec'] in ('Device:R','Device:C','Device:L'):
        # Standard passive graphics with the same normalized two-pin coordinates.
        art=allof(parsed,'symbol')[0]
        art[:]=['symbol',Q(nm+'_0_1')]
        if c['spec']=='Device:R':
            art.append(parse('(rectangle (start -2.54 1.016) (end 2.54 -1.016) (stroke (width .254) (type default)) (fill (type none)))'))
            left,right=-2.54,2.54
        elif c['spec']=='Device:C':
            for x in [-.635,.635]:art.append(parse(f'(polyline (pts (xy {x} -2.54) (xy {x} 2.54)) (stroke (width .254) (type default)) (fill (type none)))'))
            left,right=-.635,.635
        else:
            for x in [-3,-1,1]:art.append(parse(f'(arc (start {x} 0) (mid {x+1} 1) (end {x+2} 0) (stroke (width .254) (type default)) (fill (type none)))'))
            left,right=-3,3
        for x1,x2 in [(-12.7,left),(right,12.7)]:art.append(parse(f'(polyline (pts (xy {x1} 0) (xy {x2} 0)) (stroke (width .254) (type default)) (fill (type none)))'))
    return parsed,h

def schematic(d,folder):
    name='PANOGOZ-'+d.kind+'-B1';rootid=uid(name+'/root'); pages=[];syms={}
    sources=['VBAT','GND','V1V55','VR_PA','VDDA']+(['SENS_3V3'] if d.kind=='IR' else ['PD_A3V3'] if d.kind=='PD' else []) if d.kind!='GW' else ['V5_IN','V5','GND','V3V3','LTE_3V3','RTC_BACKUP','ISO1_GND','ISO2_GND','V5_HOLD','VDDCR','CHASSIS']
    # Flags describe physical battery/connector sources, passive supply paths,
    # or the MCU's internal LDO/PA regulator (DS13105 figures 4, 8). No ERC suppression.
    for i,net in enumerate(sources,1):
        if any(t=='power_out' and c['nets'].get(n)==net for c in d.cs for n,_,t in c['pins']):continue
        d.cs.append(dict(ref='#FLG'+str(i),value='SOURCE '+net,spec='B1:PWR_FLAG',pins=[('1','pwr','power_out')],fp='',nets={'1':net},group='SUPPLY_REFERENCES',mpn='',note='Power source declaration; not a fitted component',place=None,side='F',virtual=True))
    for c in d.cs:
        syms[c['ref']],c['sym_h']=normalized(c)
    # One functional block per sheet, 4 columns, enough height for large MCUs.
    for group in dict.fromkeys(c['group'] for c in d.cs):
        cs=[c for c in d.cs if c['group']==group];page=[];x=52.07;y=43.18;row=0
        for c in cs:
            height=2*c['sym_h']+25.4
            if y+height>269:
                x+=99.06;y=43.18
            if x>350:
                pages.append((group,page));page=[];x=52.07;y=43.18
            c['xy']=(x,y+c['sym_h']);page.append(c);y+=height
        if page:pages.append((group,page))
    for number,(group,cs) in enumerate(pages,1):
        sheetid=uid(name+'/sheet'+str(number));pu=uid(name+'/page'+str(number));parts=[];libs=[]
        for c in cs:
            c['page']=number;c['uuid']=uid(name+'/'+c['ref']);c['path']=[rootid,sheetid,c['uuid']]
            lib=copy.deepcopy(syms[c['ref']]);lib[1]=Q('B1:'+c['ref']);libs.append(dump(lib))
            x,y=c['xy'];h=c['sym_h'];pr=[]
            for key,val,py,hide in [('Reference',c['ref'],y-h-5,False),('Value',c['value'],y+h+4,False),('Footprint',c['fp'],y,True),('MPN',c['mpn'],y,True)]:
                pr.append(f'(property {q(key)} {q(val)} (at {x} {py} 0) (effects (font (size {1 if key=="Reference" else .85} {1 if key=="Reference" else .85})) {"(hide yes)" if hide else ""}))')
            parts.append(f'(symbol (lib_id {q("B1:"+c["ref"])}) (at {x} {y} 0) (unit 1) (in_bom {"no" if c.get("virtual") else "yes"}) (on_board {"no" if c.get("virtual") else "yes"}) (uuid {q(c["uuid"])}) {" ".join(pr)} (instances (project {q(name)} (path {q("/"+rootid+"/"+sheetid)} (reference {q(c["ref"])}) (unit 1)))))')
            for sub in allof(lib,'symbol'):
                for pin in allof(sub,'pin'):
                    n=str(find(pin,'number')[1]);at=find(pin,'at');xx=x+float(at[1]);yy=y-float(at[2]);angle=int(at[3]);net=c['nets'].get(n)
                    if not net:parts.append(f'(no_connect (at {xx} {yy}) (uuid {q(uid(c["uuid"]+n+"nc"))}))');continue
                    ex=xx+(-2.54 if angle==0 else 2.54)
                    parts.append(f'(wire (pts (xy {xx} {yy}) (xy {ex} {yy})) (stroke (width 0) (type default)) (uuid {q(uid(c["uuid"]+n+"w"))}))')
                    parts.append(f'(global_label {q(net)} (shape bidirectional) (at {ex} {yy} {180 if angle==0 else 0}) (effects (font (size .85 .85)) (justify {"right" if angle==0 else "left"})) (uuid {q(uid(c["uuid"]+n+"lbl"))}) (property "Intersheetrefs" "${{INTERSHEET_REFS}}" (at {ex} {yy} 0) (effects (font (size 1 1)) (hide yes))))')
        header=f'(kicad_sch (version 20250114) (generator "eeschema") (uuid {q(pu)}) (paper "A3") (title_block (title {q(name+" / "+group)}) (date "2026-09-20") (rev "B1") (company "Grid Up / K1")) (lib_symbols {" ".join(libs)})'
        (folder/f'{number:02d}.kicad_sch').write_text(header+'\n'+'\n'.join(parts)+'\n)',encoding='utf8')
    def txt(s,x,y,size=1.6):return f'(text {q(s)} (at {x} {y} 0) (effects (font (size {size} {size})) (justify left)) (uuid {q(uid(name+s))}))'
    root=[f'(kicad_sch (version 20250114) (generator "eeschema") (uuid {q(rootid)}) (paper "A3") (lib_symbols) (title_block (title {q(name)}) (rev "B1") (date "2026-09-20"))',txt(name+' | K1 DESIGN REVIEW',20,20,4),txt(f'{d.w} x {d.h} mm / 4 layers / placement stage / no fabricated-board claim',20,31)]
    for i,(group,cs) in enumerate(pages,1):
        x=20+(i-1)%3*126;y=48+(i-1)//3*41
        root.append(f'(sheet (at {x} {y}) (size 112 23) (stroke (width .254) (type default)) (fill (color 0 0 0 0)) (uuid {q(uid(name+"/sheet"+str(i)))}) (property "Sheetname" {q(f"{i:02d} / {group}")} (at {x} {y-2} 0) (effects (font (size 1.1 1.1)) (justify left))) (property "Sheetfile" {q(f"{i:02d}.kicad_sch")} (at {x} {y+26} 0) (effects (font (size 1 1)) (justify left))) (instances (project {q(name)} (path {q("/"+rootid)} (page {q(i+1)})))))')
    root.extend([txt('All symbols carry physical pin numbers. Same-name global labels are electrically connected.',20,240),txt('See hardware/README.md and verification reports for limits, power sources and open review items.',20,251),'(sheet_instances (path "/" (page "1")))',')'])
    (folder/(name+'.kicad_sch')).write_text('\n'.join(root),encoding='utf8')
    (folder/'B1.kicad_sym').write_text('(kicad_symbol_lib (version 20250114) (generator "kicad_symbol_editor")\n'+'\n'.join(dump(s) for s in syms.values())+')',encoding='utf8')
    (folder/'sym-lib-table').write_text('(sym_lib_table (lib (name "B1") (type "KiCad") (uri "${KIPRJMOD}/B1.kicad_sym") (options "") (descr "B1 physical pin symbols")))')
    (folder/'fp-lib-table').write_text('(fp_lib_table (lib (name "B1") (type "KiCad") (uri "${KIPRJMOD}/B1.pretty") (options "") (descr "B1 placement footprints")))')
    project={'meta':{'filename':name+'.kicad_pro','version':1},'board':{'design_settings':{'rules':{'min_clearance':.15,'min_track_width':.15,'min_copper_edge_clearance':.3,'min_through_hole_diameter':.2,'min_hole_clearance':.2}}},'net_settings':{'classes':[{'name':'Default','clearance':.15,'track_width':.2,'via_diameter':.6,'via_drill':.3}],'meta':{'version':3}},'schematic':{'meta':{'version':1}}}
    (folder/(name+'.kicad_pro')).write_text(json.dumps(project,indent=2))
    return name

def board(d,folder,name):
    b=p.BOARD();b.SetCopperLayerCount(4);b.GetDesignSettings().SetCopperLayerCount(4)
    nets={}
    for n in sorted({n for c in d.cs for n in c['nets'].values() if n}):net=p.NETINFO_ITEM(b,n);b.Add(net);nets[n]=net
    local=folder/'B1.pretty';local.mkdir(exist_ok=True)
    # Source dimensions: TE C-2041119 rev D sheet 2 and Ebyte E22-M manual section 3.1.
    if d.kind=='GW':
        fp=p.FOOTPRINT(None);fp.SetFPID(p.LIB_ID('B1','TE_2041119_1'));fp.SetValue('TE 2041119-1')
        for n in range(1,53):
            i=(n-1)//2;even=n%2==0
            x=((1.1 if even else 1.5)+i*.8) if i<8 else ((10.7 if even else 10.3)+(i-8)*.8)
            pad=p.PAD(fp);pad.SetNumber(str(n));pad.SetAttribute(p.PAD_ATTRIB_SMD);pad.SetShape(p.PAD_SHAPE_RECT);pad.SetSize(v(.6,2));pad.SetLayerSet(p.PAD.SMDMask());pad.SetPosition(v(x-12.5,-3.1 if even else 3.1));fp.Add(pad)
        for x,drill in [(-12.5,1.6),(12.5,1.1)]:
            pad=p.PAD(fp);pad.SetAttribute(p.PAD_ATTRIB_NPTH);pad.SetShape(p.PAD_SHAPE_CIRCLE);pad.SetSize(v(drill,drill));pad.SetDrillSize(v(drill,drill));pad.SetLayerSet(p.PAD.UnplatedHoleMask());pad.SetPosition(v(x,0));fp.Add(pad)
        for x in [-14.65,14.65]:
            pad=p.PAD(fp);pad.SetNumber('MP');pad.SetAttribute(p.PAD_ATTRIB_SMD);pad.SetShape(p.PAD_SHAPE_RECT);pad.SetSize(v(2.3,3.5));pad.SetLayerSet(p.PAD.SMDMask());pad.SetPosition(v(x,1.85));fp.Add(pad)
        rect(fp,(-16.05,-51,16.05,4.4),p.F_CrtYd,.05);rect(fp,(-15.15,-3.8,15.15,3.8),p.F_Fab)
        rect(fp,(-15,-50.95,15,0),p.F_Fab)
        for x in [-12.1,12.1]:
            pad=p.PAD(fp);pad.SetAttribute(p.PAD_ATTRIB_NPTH);pad.SetShape(p.PAD_SHAPE_CIRCLE);pad.SetSize(v(2.6,2.6));pad.SetDrillSize(v(2.6,2.6));pad.SetLayerSet(p.PAD.UnplatedHoleMask());pad.SetPosition(v(x,-48.05));fp.Add(pad)
        p.PCB_IO_KICAD_SEXPR().FootprintSave(str(local),fp)
        fp=p.FOOTPRINT(None);fp.SetFPID(p.LIB_ID('B1','E22-900MM22S'));fp.SetValue('E22-900MM22S')
        for n in range(1,21):
            i=(n-1)%5
            x,y=(-5,-2.54+i*1.27) if n<=5 else (-2.54+i*1.27,5) if n<=10 else (5,2.54-i*1.27) if n<=15 else (2.54-i*1.27,-5)
            pad=p.PAD(fp);pad.SetNumber(str(n));pad.SetAttribute(p.PAD_ATTRIB_SMD);pad.SetShape(p.PAD_SHAPE_RECT);pad.SetSize(v(1.5,.8) if n<=5 or 11<=n<=15 else v(.8,1.5));pad.SetLayerSet(p.PAD.SMDMask());pad.SetPosition(v(x,y));fp.Add(pad)
        rect(fp,(-6,-6,6,6),p.F_CrtYd,.05);rect(fp,(-5,-5,5,5),p.F_Fab)
        p.PCB_IO_KICAD_SEXPR().FootprintSave(str(local),fp)
    loaded=[]; model_report=[]; replacements={};models=folder/'models';models.mkdir(exist_ok=True)
    for c in d.cs:
        if c.get('virtual'):continue
        lib,nm=c['fp'].split(':');fp=p.PCB_IO_KICAD_SEXPR().FootprintLoad(str(local if lib=='B1' else KICAD/'footprints'/(lib+'.pretty')),nm)
        if not fp:raise ValueError('Missing footprint: '+c['fp'])
        for model in fp.Models():
            original=model.m_Filename
            source=Path(model.m_Filename.replace('${KICAD10_3DMODEL_DIR}',str(KICAD/'3dmodels')))
            approximate=False
            if not source.exists() and 'QFN-48-1EP_7x7mm' in source.name:
                source=KICAD/'3dmodels/Package_DFN_QFN.3dshapes/QFN-48-1EP_7x7mm_P0.5mm_EP5.15x5.15mm.step';approximate=True
            if source.exists():
                dest=models/(source.parent.stem+'__'+source.name);shutil.copyfile(source,dest)
                model.m_Filename='${KIPRJMOD}/models/'+dest.name
                replacements[original]=model.m_Filename
            model_report.append({'ref':c['ref'],'available':source.exists(),'generic_body':approximate})
        if lib=='B1':
            mn='E22-900MM22S-envelope.step' if nm=='E22-900MM22S' else 'TE2041119-EC21-envelope.step'
            model=p.FP_3DMODEL();model.m_Filename='${KIPRJMOD}/models/'+mn;fp.Add3DModel(model)
            model_report.append({'ref':c['ref'],'available':(models/mn).exists(),'generic_body':True})
        fp.SetReference(c['ref']);fp.SetValue(c['value']);fp.SetFPID(p.LIB_ID(lib,nm));fp.Value().SetVisible(False);b.Add(fp)
        fp.SetAttributes(fp.GetAttributes() & ~p.FP_EXCLUDE_FROM_BOM)
        fp.SetField('MPN',c['mpn']);fp.GetField('MPN').SetVisible(False)
        path=p.KIID_PATH()
        for s in c['path']:path.push_back(p.KIID(s))
        fp.SetPath(path);fp.SetSheetfile('%02d.kicad_sch'%c['page']);fp.Reference().SetTextSize(v(.6,.6));fp.Reference().SetTextThickness(p.FromMM(.1));fp.Reference().SetVisible(False)
        pads={pad.GetNumber() for pad in fp.Pads() if pad.GetNumber()}
        extra=pads-set(n for n,_,_ in c['pins'])-{'MP'} # connector mounting pegs, not electrical contacts
        if extra:raise ValueError((c['ref'],c['fp'],'footprint pad absent from symbol',extra))
        for pad in fp.Pads():
            net=c['nets'].get(pad.GetNumber())
            if net:pad.SetNet(nets[net])
            elif pad.GetNumber() and pad.GetNumber()!='MP':
                pn=next(pn for n,pn,t in c['pins'] if n==pad.GetNumber())
                nc='unconnected-('+c['ref']+('-'+pn.replace('/','{slash}') if pn else '')+'-Pad'+pad.GetNumber()+')'
                nn=p.NETINFO_ITEM(b,nc);b.Add(nn);pad.SetNet(nn)
        loaded.append((c,fp))
    # Courtyard-aware packing. Fixed sensors/connectors first, ICs before passives.
    boxes=[];fail=[]
    def bounds(fp):
        pts=[]
        for g in fp.GraphicalItems():
            if g.GetLayer() in [p.F_CrtYd,p.B_CrtYd]:
                bb=g.GetBoundingBox();pts.extend([(p.ToMM(bb.GetX()),p.ToMM(bb.GetY())),(p.ToMM(bb.GetRight()),p.ToMM(bb.GetBottom()))])
        if not pts:
            bb=fp.GetBoundingBox(False,False);pts=[(p.ToMM(bb.GetX()),p.ToMM(bb.GetY())),(p.ToMM(bb.GetRight()),p.ToMM(bb.GetBottom()))]
        return min(x for x,y in pts),min(y for x,y in pts),max(x for x,y in pts),max(y for x,y in pts)
    def intersect(a,b):return a[0]<b[2]+.05 and a[2]>.05+b[0] and a[1]<b[3]+.05 and a[3]>.05+b[1]
    def allowed(c,box,side):
        if box[0]<.4 or box[1]<.4 or box[2]>d.w-.4 or box[3]>d.h-.4:return False
        if d.kind=='GW' and not c['value'].startswith('ADM2587'):
            iso=next((i for i in [1,2] if any(n and (n.startswith('ISO%d_'%i) or n in ('RS%d_A'%i,'RS%d_B'%i,'TERM%d'%i)) for n in c['nets'].values())),None)
            if iso and (box[0]<77 or box[1]<(0 if iso==1 else 33) or box[3]>(33 if iso==1 else 66)):return False
            if not iso and box[2]>71 and box[1]<66:return False
        for nm,keep in d.keepouts:
            if nm=='THERMAL_ISLAND' and 'TMP117' not in c['value'] and intersect(box,keep):return False
            if nm=='ANTENNA_EXIT' and 'u.FL' not in c['value'] and intersect(box,keep):return False
            if 'ISOLATION' in nm and 'ADM2587' not in c['value'] and intersect(box,keep):return False
        return not any(intersect(box,bx) and (sd==side or thru or c['thru']) for bx,sd,thru,f in boxes)
    def area(pair):
        z=bounds(pair[1]);return (z[2]-z[0])*(z[3]-z[1])
    ordered=sorted(loaded,key=lambda pair:(pair[0]['place'] is None,-area(pair)))
    for c,fp in ordered:
        done=False;side=c['side'];c['thru']=any(pad.GetAttribute()!=p.PAD_ATTRIB_SMD for pad in fp.Pads())
        for sd in [side]+(['B' if side=='F' else 'F'] if c['place'] is None else []):
            if sd=='B' and fp.GetLayer()!=p.B_Cu:fp.Flip(fp.GetPosition(),False)
            if sd=='F' and fp.GetLayer()!=p.F_Cu:fp.Flip(fp.GetPosition(),False)
            angles=[0,90] if c['place'] is None else [0]
            for angle in angles:
                fp.SetOrientationDegrees(angle);fp.SetPosition(v(0,0));off=bounds(fp)
                candidates=[c['place']] if c['place'] else [(x/2-off[0],y/2-off[1]) for y in range(1,int(d.h*2)) for x in range(1,int(d.w*2))]
                for x,y in candidates:
                    box=(x+off[0],y+off[1],x+off[2],y+off[3])
                    if allowed(c,box,sd):
                        fp.SetPosition(v(x,y))
                        boxes.append((box,sd,c['thru'],fp));c['placement']=[x,y,angle,sd];c['courtyard']=box;done=True;break
                if done:break
            if done:break
        if not done:
            # Never silently allow overlaps; stop and adjust the source placements.
            fail.append(c['ref']+' '+c['value'])
    if fail:raise ValueError('Placement failed: '+', '.join(fail))
    rect(b,(0,0,d.w,d.h),p.Edge_Cuts,.05)
    for nm,(x1,y1,x2,y2) in d.keepouts:
        z=p.ZONE(b);z.SetIsRuleArea(True);z.SetDoNotAllowTracks(nm!='THERMAL_ISLAND');z.SetDoNotAllowVias(True);z.SetDoNotAllowZoneFills(True);z.SetDoNotAllowPads(False);z.SetDoNotAllowFootprints(False);z.SetLayerSet(p.LSET.AllCuMask());z.SetZoneName(nm);poly=z.Outline();poly.NewOutline()
        for x,y in [(x1,y1),(x2,y1),(x2,y2),(x1,y2)]:poly.Append(p.FromMM(x),p.FromMM(y))
        b.Add(z);rect(b,(x1,y1,x2,y2),p.Dwgs_User)
    pcb_text(b,name,d.w/2,-3,size=1);pcb_text(b,'PLACEMENT ONLY / UNROUTED',d.w/2,d.h+3,size=1)
    p.SaveBoard(str(folder/(name+'.kicad_pcb')),b)
    # Models() exposes value copies in pcbnew 10; rewrite serialized paths.
    path=folder/(name+'.kicad_pcb');data=path.read_text(encoding='utf8')
    for old,new in replacements.items():data=data.replace(old,new)
    path.write_text(data,encoding='utf8')
    (folder/'model_report.json').write_text(json.dumps(model_report,indent=2))
    return {'components':len(loaded),'nets':len(nets),'tracks':0,'routing_complete':False,'courtyard_overlaps':0,'outside_board':0,'physical_test':False}

def run(kind):
    d={'TC':tc,'IR':ir,'PD':pd,'GW':gw}[kind]();folder=OUT/kind;folder.mkdir(parents=True,exist_ok=True)
    name=schematic(d,folder);project=(folder/(name+'.kicad_pro')).read_text()
    result=board(d,folder,name)
    # pcbnew.SaveBoard can write a default project alongside a newly-created BOARD.
    (folder/(name+'.kicad_pro')).write_text(project)
    (folder/'circuit.json').write_text(json.dumps({'name':name,'width_mm':d.w,'height_mm':d.h,'layers':4,'components':d.cs,'keepouts':d.keepouts,'notes':d.notes},indent=2),encoding='utf8')
    (folder/'placement_report.json').write_text(json.dumps(result,indent=2))
    with (folder/'pinmap.csv').open('w',newline='',encoding='utf-8-sig') as f:
        wr=csv.writer(f);wr.writerow(['reference','MPN','physical_pin','pin_name','electrical_type','net'])
        for c in d.cs:
            for n,pn,t in c['pins']:wr.writerow([c['ref'],c['mpn'],n,pn,t,c['nets'].get(n) or 'NC'])
    print(kind,result,flush=True)
if __name__=='__main__':
    for kind in sys.argv[1:] or ['TC','IR','PD','GW']:run(kind)
