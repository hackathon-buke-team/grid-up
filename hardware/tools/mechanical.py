"""Parametric K1 enclosures, mounting parts and STEP assemblies (CadQuery 2.6).

These are design envelopes, not vendor-qualified environmental enclosures.
All units mm. No holes are added to the distribution panel.
"""
from pathlib import Path
import sys,importlib,json
if sys.platform=='win32':
    import vtkmodules.vtkCommonCore,vtkmodules.vtkCommonDataModel
    sys.modules.setdefault('vtk',importlib.import_module('vtkmodules'))
import cadquery as cq
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

OUT=Path(__file__).resolve().parents[1]/'B1/mechanical';OUT.mkdir(parents=True,exist_ok=True)
def box(x,y,z,w,h,d):return cq.Workplane('XY').box(w,h,d,centered=(False,False,False)).translate((x,y,z))
def cylinder(x,y,z,r,h):return cq.Workplane('XY').circle(r).extrude(h).translate((x,y,z))
SPECS={'TC':(34,126,19.5,30,22,1.2),'IR':(54,82,26,45,35,1.5),'PD':(80,118,45,70,50,2),'GW':(112,112,54,100,90,2)}
reports={}
for kind,(w,h,depth,bw,bh,wall) in SPECS.items():
    folder=OUT/kind;folder.mkdir(exist_ok=True)
    ox=(w-bw)/2;oy=wall+1;z=wall+5
    base=box(0,0,0,w,h,depth-wall).cut(box(wall,wall,wall,w-2*wall,h-2*wall,depth))
    # Opposed guide rails retain the PCB without adding holes in the tiny boards.
    for xx in [ox-.5,ox+bw-.5]:base=base.union(box(xx,oy,wall,1,bh,4.9))
    lid=box(0,0,depth-wall,w,h,wall)
    parts={'base':base,'lid':lid,'pcb':box(ox,oy,z,bw,bh,1.6)}
    # Gasket center-line and lid are separate parts; target seal needs compression/ingress tests.
    gasket=box(.5,.5,depth-wall-.6,w-1,h-1,.6).cut(box(1.2,1.2,depth-wall-.7,w-2.4,h-2.4,.8))
    parts['gasket']=gasket
    if kind=='TC':
        # Mounted on edge: front projection 19.5 mm; long axis follows cable depth.
        # A flexible insulated thermal tongue contacts the cable sheath, not exposed conductor.
        parts['thermal_pad']=box(ox,oy,0,6,7,.8)
        parts['ER14250_envelope']=cq.Workplane('XZ').circle(7.25).extrude(25).rotate((0,0,0),(1,0,0),180).translate((17,36,9.75))
        parts['HLC_envelope']=cq.Workplane('XZ').circle(8.25).extrude(55).rotate((0,0,0),(1,0,0),180).translate((17,68,9.75))
        # Cable clamp with compliant insert and captive straps; fit range is a design input.
        clamp=cylinder(17,20,-9,21,7).cut(cylinder(17,20,-10,16,9)).cut(box(16,0,-10,2,42,10))
        parts['split_clamp']=clamp
        mount='Split clamp on insulated cable, nominal 32 mm; interchangeable insert, no drilling'
    elif kind=='IR':
        parts['battery_envelope']=cq.Workplane('YZ').circle(7.5).extrude(50).translate((2,61,13))
        # Optical opening directly above the TO39 package; ordinary glass is unsuitable for LWIR.
        lid=lid.cut(cylinder(ox+9,oy+8,depth-2*wall,5,3*wall));parts['lid']=lid
        parts['IR_window']=cylinder(ox+9,oy+8,depth-.4,5,.3)
        for xx in [10,w-10]:parts['magnet_'+str(xx)]=cylinder(xx,h-12,-3,5,3)
        mount='Two encapsulated magnets on galvanized floor; lens points upward; LWIR window and vent membrane'
    elif kind=='PD':
        parts['ER26500_envelope']=cq.Workplane('XZ').circle(13.5).extrude(50).rotate((0,0,0),(1,0,0),180).translate((26,55,23))
        parts['HLC_envelope']=cq.Workplane('XZ').circle(8.25).extrude(55).rotate((0,0,0),(1,0,0),180).translate((61,58,13))
        plate=box(-20,35,-3,25,34,3).cut(cylinder(-10,52,-4,6.5,5))
        parts['M12_bracket']=plate
        lid=lid.cut(cylinder(61,79,depth-2*wall,8.1,3*wall));parts['lid']=lid
        parts['ultrasound_envelope']=cylinder(61,79,depth-12,8,12)
        mount='Accessory bracket on existing M12 stud; existing PE lugs stay in place; HFCT clips around PE conductor'
    else:
        # Fixed DIN clip envelope and access apertures in this enclosure only.
        parts['DIN_clip']=box(36,34,-8,40,44,8).cut(box(37,38,-8,38,36,5))
        base=base.cut(box(0,3,10,wall+1,23,21)).cut(box(w-wall-1,4,10,wall+2,64,22));parts['base']=base
        parts['EC21_card_envelope']=box(ox+33,oy+26,z+1.6+2.05,30,51,4.9)
        mount='35 mm DIN rail in metering/auxiliary bay; external SELV PSU; external sealed antenna exit'
    assembly=cq.Assembly(name='PANOGOZ_'+kind+'_B1')
    palette={'base':(.70,.77,.82),'lid':(.82,.85,.88),'pcb':(.05,.40,.27),'gasket':(.12,.12,.14)}
    for name,part in parts.items():
        assembly.add(part,name=name,color=cq.Color(*palette.get(name,(.2,.35,.55))))
        assert part.val().isValid(),(kind,name)
    assembly.save(str(folder/'assembly.step'))
    cq.exporters.export(parts['base'],str(folder/'base.step'));cq.exporters.export(parts['lid'],str(folder/'lid.step'))
    # Deliver editable STEP and optional additive-manufacturing mesh for enclosure prototypes.
    cq.exporters.export(parts['base'],str(folder/'base.stl'),tolerance=.2)
    reports[kind]={'outer_mm':[w,h,depth],'pcb_mm':[bw,bh,1.6],'wall_mm':wall,
                   'board_origin_mm':[ox,oy,z],'mount':mount,'parts_valid':True,
                   'environmental_qualification':False,'fits_real_panel_verified':False,
                   'model_kind':'parametric enclosure and simplified component envelopes'}
    fig=plt.figure(figsize=(10,8),dpi=160);ax=fig.add_subplot(111,projection='3d')
    for name,part in parts.items():
        if name in ('lid','gasket'):continue
        if name=='base':part=part.cut(box(-25,-25,depth*.6,w+50,h+50,depth))
        verts,tri=part.val().tessellate(.6);vv=[(a.x,a.y,a.z) for a in verts]
        faces=[[vv[j] for j in t] for t in tri]
        ax.add_collection3d(Poly3DCollection(faces,facecolor=palette.get(name,(.2,.35,.55)),alpha=.10 if name=='base' else 1,edgecolor=(0,0,0,.06),linewidth=.15))
    ax.set_xlim(-22,w+5);ax.set_ylim(-5,h+5);ax.set_zlim(-12,depth+3);ax.set_box_aspect((w+27,h+10,depth+15));ax.view_init(34,-55)
    ax.set_xlabel('X / mm');ax.set_ylabel('Y / mm');ax.set_zlabel('Z / mm');ax.set_title(f'{kind} B1 / {w} x {h} x {depth} mm\nDesign envelope - lid removed',loc='left')
    fig.tight_layout();fig.savefig(folder/'assembly.png',facecolor='white');plt.close(fig)
    print(kind,'mechanical STEP and preview ready',flush=True)
(OUT/'dimensions.json').write_text(json.dumps(reports,indent=2),encoding='utf8')
# Portable 3D models for two custom footprints, intentionally identified as envelopes.
models=OUT.parent/'GW/models';models.mkdir(exist_ok=True)
cq.exporters.export(box(-5,-5,0,10,10,2.5),str(models/'E22-900MM22S-envelope.step'))
cq.exporters.export(box(-15,-4,0,30,8,4).union(box(-15,0,2.05,30,50.95,1)),str(models/'TE2041119-EC21-envelope.step'))
