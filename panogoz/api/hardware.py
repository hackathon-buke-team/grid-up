"""Public B1 design assets. Only explicit deliverables are served, never a directory."""
from functools import lru_cache
import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

ROOT = Path(__file__).resolve().parents[2] / 'hardware' / 'B1'
PREFIX = '/api/hardware/B1'
KINDS = {'TC': 'TC', 'TN-IR': 'IR', 'PD': 'PD', 'GW': 'GW'}
LABELS = {'TC': 'Isıl kelepçe', 'IR': 'Termal dizi',
          'PD': 'RF ve ortam düğümü', 'GW': 'Ağ geçidi'}
MOUNTS = {
    'TC': 'Yalıtımlı kabloya kelepçe. Kutu kenarı öne bakar; üçlülerde z = 80 / 140 / 200 mm derinlik kademesi.',
    'IR': 'Alt bölmede kapsüllü mıknatıs kaide; ayarlanabilir optik eksen. Pabuç ayrımı kalibre edilmedi.',
    'PD': 'Mevcut M12 aksesuar saplamasında braket; PE bağlantısı korunur.',
    'GW': 'Ölçü kolonundaki 35 mm DIN ray; harici SELV besleme.',
}


def _assets():
    files = {'report.pdf': (ROOT / 'K1-B1-TASARIM-DOSYASI.pdf', 'application/pdf')}
    for board in LABELS:
        for name in ('pcb-3d.png', 'pcb-top.png', 'pcb-bottom.png'):
            files[f'{board}/{name}'] = (ROOT / board / name, 'image/png')
        files[f'{board}/assembly.png'] = (ROOT / 'mechanical' / board / 'assembly.png', 'image/png')
        files[f'{board}/assembly.step'] = (ROOT / 'mechanical' / board / 'assembly.step', 'application/step')
        files[f'{board}/schematic.pdf'] = (ROOT / board / 'schematic.pdf', 'application/pdf')
        files[f'{board}/board.kicad_pcb'] = (ROOT / board / f'PANOGOZ-{board}-B1.kicad_pcb', 'application/octet-stream')
    return files


ASSETS = _assets()
router = APIRouter()


@lru_cache(maxsize=1)
def catalog():
    try:
        dims = json.loads((ROOT / 'mechanical' / 'dimensions.json').read_text(encoding='utf8'))
    except (OSError, ValueError):
        return {'revision': 'B1', 'available': False, 'boards': {}}
    boards = {}
    for board, label in LABELS.items():
        d = dims[board]
        w, h, depth = d['outer_mm']
        boards[board] = {
            'key': board, 'label': label, 'outer_mm': d['outer_mm'],
            'pcb_mm': d['pcb_mm'], 'mount_tr': MOUNTS[board],
            # TC's long axis runs into the panel, as in the B1 mounting report.
            'front_mm': [depth, w] if board == 'TC' else [w, h],
            'images': {name: f'{PREFIX}/{board}/{filename}' for name, filename in (
                ('assembly', 'assembly.png'), ('pcb3d', 'pcb-3d.png'),
                ('top', 'pcb-top.png'), ('bottom', 'pcb-bottom.png'))},
            'files': {name: f'{PREFIX}/{board}/{filename}' for name, filename in (
                ('schematic', 'schematic.pdf'), ('step', 'assembly.step'),
                ('pcb', 'board.kicad_pcb'))},
        }
    return {
        'revision': 'B1', 'available': True, 'report_url': f'{PREFIX}/report.pdf',
        'note_tr': 'K1 B1 tasarım dosyaları · kutu modeli ve PCB yerleşimi. Fiziksel üretim ve pano üzerinde montaj doğrulaması yapılmadı.',
        'boards': boards,
    }


@router.get(PREFIX + '/{asset:path}', include_in_schema=False)
def design_asset(asset: str):
    selected = ASSETS.get(asset)
    if selected is None:
        raise HTTPException(status_code=404, detail='Design asset not found')
    path, media_type = selected
    if not path.is_file():
        raise HTTPException(status_code=404, detail='Design asset is unavailable')
    download = path.suffix in ('.step', '.kicad_pcb')
    return FileResponse(path, media_type=media_type,
                        filename=path.name if download else None,
                        headers={'X-Content-Type-Options': 'nosniff',
                                 'Cache-Control': 'no-cache'})
