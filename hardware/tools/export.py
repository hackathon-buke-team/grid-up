"""KiCad CLI evidence and presentation exports; never suppress ERC/DRC findings."""
import os,json,subprocess
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[1]
CLI=Path(os.environ.get('KICAD_CLI',Path(os.environ.get('LOCALAPPDATA',''))/'Programs/KiCad/10.0/bin/kicad-cli.exe'))
summary={}
for kind in ('TC','IR','PD','GW'):
    d=ROOT/'B1'/kind; name='PANOGOZ-'+kind+'-B1'
    sch=d/(name+'.kicad_sch');pcb=d/(name+'.kicad_pcb')
    def run(*args):
        r=subprocess.run([str(CLI),*map(str,args)],capture_output=True)
        with (d/'export.log').open('ab') as f:f.write(r.stdout+r.stderr)
        if r.returncode:raise RuntimeError((kind,args,r.returncode,r.stderr[-1000:]))
    (d/'export.log').write_bytes(b'')
    run('sch','erc','--format','json','-o',d/'erc.json',sch)
    run('sch','export','pdf','-o',d/'schematic.pdf',sch)
    run('pcb','drc','--format','json','--schematic-parity','-o',d/'drc.json',pcb)
    for side,rotation,filename in [('top','0,0,0','pcb-top.png'),('bottom','0,0,0','pcb-bottom.png'),('top','35,0,25','pcb-3d.png')]:
        run('pcb','render','--width','1600','--height','1200','--side',side,'--rotate',rotation,'--quality','basic','--background','opaque','-o',d/filename,pcb)
    erc=json.loads((d/'erc.json').read_text());drc=json.loads((d/'drc.json').read_text())
    es=[v for s in erc['sheets'] for v in s.get('violations',[])]
    summary[kind]={'erc':dict(Counter(x['severity'] for x in es)),'drc':dict(Counter(x['type'] for x in drc.get('violations',[]))),
                   'unconnected':len(drc.get('unconnected_items',[])),'schematic_parity':len(drc.get('schematic_parity',[]))}
    print(kind,json.dumps(summary[kind]),flush=True)
(ROOT/'B1/verification.json').write_text(json.dumps(summary,indent=2))
