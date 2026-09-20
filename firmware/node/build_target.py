"""Build the real Cortex-M4 image on Windows/Linux; fail if tools are absent."""
from pathlib import Path
import argparse, json, os, re, shutil, subprocess

ROOT=Path(__file__).resolve().parent
PORT=ROOT/'port/stm32wle5'
OUT=ROOT/'build/stm32wle5'

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--toolchain',default=os.environ.get('ARM_GCC_BIN',''))
    ap.add_argument('--node',type=int,choices=range(1,7),default=4,help='TC number, 1..6; default TC-04')
    args=ap.parse_args()
    def tool(name):
        path=shutil.which('arm-none-eabi-'+name,path=args.toolchain or None)
        if path is None: raise SystemExit('Required tool missing: arm-none-eabi-'+name)
        return str(Path(path).resolve())
    cc=tool('gcc'); OUT.mkdir(parents=True,exist_ok=True)
    common=['-mcpu=cortex-m4','-mthumb','-mfloat-abi=soft','-Os','-g3',
            '-ffunction-sections','-fdata-sections','-fno-common',
            '-DSTM32WLE5xx','-DUSE_HAL_DRIVER','-DPG_TARGET=1','-DPG_OTA_DISABLED=1',f'-DPG_NODE_ID={0x100+args.node}']
    inc=[PORT,ROOT,PORT/'vendor/device/Include',PORT/'vendor/cmsis/Include',PORT/'vendor/hal/Inc']
    common += ['-I'+str(p) for p in inc]
    sources=[ROOT/f for f in ['main.c','theta_edge.c','prpd_bin.c','radio.c','power.c']]
    sources+=list(PORT.glob('*.c'))+[PORT/'startup_stm32wle5xx.s']
    modules=['','_cortex','_rcc','_rcc_ex','_pwr','_pwr_ex','_flash','_flash_ex',
             '_gpio','_dma','_dma_ex','_exti','_adc','_adc_ex','_i2c','_i2c_ex',
             '_spi','_rtc','_rtc_ex','_iwdg','_subghz']
    sources += [PORT/'vendor/hal/Src'/('stm32wlxx_hal'+m+'.c') for m in modules]
    objects=[]; log=[]
    def run(cmd, quiet=False):
        result=subprocess.run(cmd,cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        log.append('$ '+' '.join(str(c) for c in cmd)+'\n'+result.stdout)
        if result.stdout and not quiet: print(result.stdout,end='')
        (OUT/'build.log').write_text('\n'.join(log),encoding='utf8')
        if result.returncode: raise SystemExit(result.returncode)
        return result.stdout
    version=run([cc,'--version']).splitlines()[0]
    for src in sources:
        obj=OUT/(src.stem+'.o')
        flags=['-std=c99','-Wall','-Wextra','-Werror','-Wdouble-promotion',
               '-ffreestanding','-fno-builtin','-fstack-usage'] if src.suffix=='.c' else []
        if 'vendor' in src.parts:
            flags+=['-Wno-unused-parameter']  # ST callback/API parameters, only vendor code
        run([cc,*common,*flags,'-c',str(src),'-o',str(obj)])
        objects.append(str(obj))
    elf=OUT/'panogoz_tc.elf'; mp=OUT/'panogoz_tc.map'
    run([cc,*common,*objects,'-T'+str(PORT/'STM32WLE5CCUX_FLASH.ld'),
         '-nostartfiles','-nostdlib','-Wl,--gc-sections','-Wl,--fatal-warnings',
         '-Wl,-Map='+str(mp),'-lgcc','-o',str(elf)])
    size=run([tool('size'),str(elf)])
    text,data,bss=map(int,size.splitlines()[-1].split()[:3])
    nm=run([tool('nm'),'-u',str(elf)])
    if nm.strip(): raise SystemExit('Undefined symbols remain')
    symbols=run([tool('nm'),str(elf)],quiet=True)
    if re.search(r'\b(malloc|calloc|realloc|free|__aeabi_[df](?:add|sub|mul|div))\b',symbols):
        raise SystemExit('Forbidden heap/float symbols in target')
    run([tool('objcopy'),'-O','binary',str(elf),str(OUT/'panogoz_tc.bin')])
    report={'target':'STM32WLE5CCU6','board':'PANOGOZ-TC-B1','device':f'TC-{args.node:02}','toolchain':version,
            'flash_bytes':text+data,'sram_reserved_bytes':data+bss,
            'stack_reserved_bytes':4096,'flash_device_bytes':262144,'sram_device_bytes':65536,
            'slot_budget_bytes':90112,'warnings':0,'undefined_symbols':0,
            'physical_execution_tested':False,'ota_enabled':False,
            'flash_address':'0x08000000','source_count':len(sources)}
    (OUT/'memory_report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__': main()
