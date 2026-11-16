#!/usr/bin/env python3
"""Build real stock COW/VFS activation payloads; does not open camera USB."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'tools')]
from stock_install_bundle import read_bundle,apply_delta,sha
from stock_first_install import stock_input,read_files,json_bytes
from native_menu_activate_build import FLAGS
from local import file_sha

PROFILES=[('icons','/share/app/image_cmn_43.uxc',True),
          ('config','/lib/CautionConfig.so',False),('loader','/lib/viewUnified2.so',False)]


def build(stock,candidate,out):
    stock_input(stock)
    _,deltas,module=read_bundle(candidate)
    old=read_files(stock,deltas)
    new={p:apply_delta(old[p],deltas[p]) for p in deltas}
    out.mkdir(parents=True,exist_ok=False)
    required={'/lib/a7fl.so':module,**{p:new[p] for p in new if p.endswith('.uxc') and 'string_' in p}}
    profiles=[]
    for name,path,own_mapping in PROFILES:
        folder=out/name;folder.mkdir()
        pages=[i for i in range(0,len(old[path]),4096) if old[path][i:i+4096]!=new[path][i:i+4096]]
        if name=='loader':
            # Helpers and RW dispatch first, setting/boot branch pages last.
            pages=[0x5b9000,0x5bb000,0x214000,0x188000]
        if any(i+4096>len(old[path]) for i in pages): raise ValueError('Partial tail page unsupported')
        check=bytearray(old[path])
        for i in pages:check[i:i+4096]=new[path][i:i+4096]
        if check!=new[path]:raise ValueError('Unaccounted activation difference')
        layout=f'''#define NMA_PAGE_COUNT {len(pages)}
#define NMA_PATCH_COUNT {len(pages)}
#define NMA_REQUIRED_COUNT {len(required)}
#define NMA_FILE_SIZE {len(old[path])}
#define NMA_TARGET_PATH "/usr{path}"
#define NMA_CREATE_MAPPING {int(own_mapping)}
#define NMA_PAGE_OFFSETS {{{','.join(hex(i) for i in pages)}}}
#define NMA_REQUIRED_PATHS {{{','.join(json.dumps('/usr'+p) for p in required)}}}
#define NMA_JOURNAL "/setting/A7ST.{name}"
#define NMA_RECOVERY_JOURNAL "/setting/A7ST.{name}.RECOVER"
#define NMA_UNDO_JOURNAL "/setting/A7ST.{name}.UNDO"
#define NMA_UNDO_RECOVERY_JOURNAL "/setting/A7ST.{name}.UNDO.RECOVER"
'''
        (folder/'stock_layout.h').write_text(layout)
        blob=struct.pack('<II',1,len(old[path]))+bytes.fromhex(sha(old[path]))+bytes.fromhex(sha(new[path]))
        for data in required.values():blob+=struct.pack('<I',len(data))+bytes.fromhex(sha(data))
        for i in pages:blob+=struct.pack('<II',i,4096)+old[path][i:i+4096]+new[path][i:i+4096]
        for i in pages:blob+=old[path][i:i+4096]
        binding=hashlib.sha256(b'A7M3-4.04-stock-activate-v1\0'+blob).hexdigest()
        (folder/'bundle.bin').write_bytes(blob)
        (folder/'bundle.S').write_text('.syntax unified\n.section .rodata.bundle,"a"\n.balign 4\n.global nma_input\nnma_input:\n.incbin "bundle.bin"\n.section .note.GNU-stack,"",%progbits\n')
        (folder/'binding.h').write_text('static const unsigned char nma_expected[32]={'+','.join(map(str,bytes.fromhex(binding)))+'};\n')
        (folder/'entry.c').write_text('''#include "stock_activate.h"
#include "binding.h"
extern const NmaBundle nma_input;
static NmaReport report;
__attribute__((constructor)) static void entry(void){
 long fd=nma_linux_syscall(0,5,(long)"/tmp/jiritsu/a7stockact.bin",1|64|128,0600,0,0,0);if(fd<0)return;
 nma_run(&nma_input,nma_expected,nma_linux_syscall,0,NMA_MODE,&report);
 unsigned done=0;while(done<sizeof report){long n=nma_linux_syscall(0,4,fd,(long)((unsigned char*)&report+done),sizeof report-done,0,0,0);if(n<=0)break;done+=(unsigned)n;}
 nma_linux_syscall(0,118,fd,0,0,0,0,0);nma_linux_syscall(0,6,fd,0,0,0,0,0);
}
''')
        flags=[*FLAGS,'-I',str(folder)]
        objects=[]
        for label,src in [('core',ROOT/'research/stock_activate.c'),('linux',ROOT/'research/native_menu_activate_linux.c'),('data',folder/'bundle.S')]:
            obj=folder/(label+'.o')
            subprocess.run(['arm-none-eabi-gcc',*flags,'-c',str(src),'-o',str(obj)],cwd=folder,check=True)
            objects.append(str(obj))
        payloads={}
        for mode,label in enumerate(('preflight','activate','recover')):
            subprocess.run(['arm-none-eabi-gcc',*flags,f'-DNMA_MODE={mode}','-c',str(folder/'entry.c'),'-o',str(folder/'entry.o')],check=True)
            so=folder/(label+'.so')
            subprocess.run(['arm-none-eabi-ld','-shared','-Bsymbolic','--no-undefined','-z','noexecstack',*objects,str(folder/'entry.o'),'-o',str(so)],check=True)
            payloads[label]={'size':so.stat().st_size,'sha256':file_sha(so)}
        profile=dict(name=name,path='/usr'+path,before_sha256=sha(old[path]),after_sha256=sha(new[path]),
                     file_size=len(old[path]),page_offsets=pages,bundle_sha256=binding,payloads=payloads,
                     required={('/usr'+p):dict(size=len(data),sha256=sha(data)) for p,data in required.items()},
                     generated_sha256={n:file_sha(folder/n) for n in ('stock_layout.h','binding.h','bundle.bin','entry.c')})
        (folder/'manifest.json').write_bytes(json_bytes(profile))
        profiles.append(profile)
        required[path]=new[path]
    result=dict(kind='stock-activation-candidate-v1',candidate_sha256=file_sha(candidate),profiles=profiles,
                executed_on_camera=False,flash_ready=False,source_sha256={n:file_sha(ROOT/n) for n in
                    ['research/stock_activate.c','research/stock_activate.h','research/stock_activate_build.py',
                     'research/native_menu_activate_linux.c','payloads/sha256.h']})
    (out/'manifest.json').write_bytes(json_bytes(result))
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('stock','candidate','out'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();out=a.out.resolve()
    if not out.is_relative_to((ROOT/'.lab').resolve()):p.error('Output must be a new .lab directory')
    result=build(a.stock.resolve(),a.candidate.resolve(),out)
    print(json.dumps({r['name']:r['payloads'] for r in result['profiles']},indent=2))
