"""Create the K1 overlay archive and a SHA256 inventory; no Git mutation/push."""
from pathlib import Path
import subprocess,json,hashlib,zipfile
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT.parent/'K1_TESLIM_Repo_B1.zip'
prefixes=('firmware/','hardware/')
extras={'.gitignore','.gitattributes','README.md','CLAUDE_CODE_DEVIR.md',
        'docs/02-DONANIM-TASARIMI.md','docs/03-ELEKTRONIK-DOKUMANTASYON.md',
        'docs/07-MALIYET-FAYDA.md','docs/10-MV-HUCRE-KONSEPTI.md',
        'docs/11-ACIK-SORULAR.md','panogoz/hardware_profile.py',
        'panogoz/sim/panel.py','panogoz/api/app.py','panogoz/api/hardware.py','panogoz/detector/engine.py',
        'panogoz/gateway/gateway.py','frontend/js/view-panel.js','frontend/js/twin.js',
        'frontend/js/hardware-view.js','frontend/css/views.css','frontend/css/base.css','tests/test_sim_acceptance.py'}
files=subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode('utf8').split('\0')
chosen=[n for n in files if n and (n.startswith(prefixes) or n in extras)]
inventory={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in chosen}
readme='''K1 / REPO B1 / 20.09.2026

Bu bir K1 ekleme/guncelleme paketidir; mevcut grid-up reposuyla birlikte kullanilir.
Arsivdeki grid-up/ klasoru ayni repo kokune karsilik gelir. Ekip arkadaslarinin daha
yeni degisikliklerini korumak icin Git dalinda inceleyerek birlestirin.

Giris: grid-up/hardware/README.md
Gorsel tasarim: grid-up/hardware/B1/K1-B1-TASARIM-DOSYASI.pdf
KiCad 10: grid-up/hardware/B1/{TC,IR,PD,GW}/PANOGOZ-*-B1.kicad_pro
STEP: grid-up/hardware/B1/mechanical/*/assembly.step
Dijital ikiz: Pano ekraninda cihaz veya "Kart ve kutu cizimlerini ac" dugmesi.
API, arayuz ve hardware/B1 dosyalarini birlikte alin, sunucuyu yeniden baslatin.
Kutu/PCB onizlemeleri ve PDF/STEP/KiCad baglantilari kaynak CAD ciktilaridir.
Derleme kaniti: grid-up/hardware/B1/evidence/target/

Uyum dogrulamasi: grid-up/hardware/B1/UYUM-DOGRULAMA.md
K1 odakli 74 test basarili. Tam repo kosusu 188 basarili / 4 basarisiz;
negatif kontrol ufuk hatalarindan biri degismemis ana surumde de tekrarlandi.
Dijital ikiz-CAD baglantisi ve B1 entegrasyonu: ayrica 9 test basarili.
Host oz testi 0 hata; dort ERC temiz. PCB yerlesimdir,
bakir routing ve fiziksel test yoktur. Firmware hedef portu TC icindir.
BOM fiyat/MPN/termin teyitleri kismi (K1 1.6 acik). IR/PD/GW uygulama portlari,
fiziksel radyo alicisi ve imzali OTA sonraki gelistirmelerdir. Yazilim radyo
zarfi -> kalici gateway kuyrugu -> QoS1/PUBACK devri test edildi.
Git dali: k1-b1-tasarim-firmware. Onceki ESP32 RevA paketi bu teslim degildir.

SHA256SUMS.json, arsiv icindeki grid-up/ altindaki her dosyanin SHA256 ozetidir.
'''
with zipfile.ZipFile(OUT,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 z.writestr('README_K1_TESLIM.txt',readme)
 z.writestr('SHA256SUMS.json',json.dumps(inventory,indent=2))
 for n in chosen:z.write(ROOT/n,'grid-up/'+n)
with zipfile.ZipFile(OUT) as z:
 assert z.testzip() is None
 assert len(chosen)==len(inventory)
 for n,h in inventory.items():assert hashlib.sha256(z.read('grid-up/'+n)).hexdigest()==h,n
digest=hashlib.sha256(OUT.read_bytes()).hexdigest()
OUT.with_suffix('.zip.sha256').write_text(digest+'  '+OUT.name+'\n')
print(json.dumps({'archive':str(OUT),'files':len(chosen),'bytes':OUT.stat().st_size,'sha256':digest,'verified':True},indent=2))
