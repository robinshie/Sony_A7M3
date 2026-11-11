#!/usr/bin/env python3
"""Build pinned read-only / activate / recover helpers; never execute on a camera."""
import argparse, hashlib, json, struct, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'.lab/native-menu-activate'
FLAGS=['-mcpu=cortex-a9','-marm','-mfloat-abi=soft','-mno-unaligned-access','-fPIC','-ffreestanding','-fno-builtin','-fno-stack-protector','-fno-unwind-tables','-fno-asynchronous-unwind-tables','-Os','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-I',str(ROOT/'research')]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(cmd,**kw):return subprocess.run(cmd,check=True,**kw)
def build(out=OUT,setting=False):
 out.mkdir(parents=True,exist_ok=True)
 before=ROOT/('.lab/native-menu-boot-loader/viewUnified2.so' if setting else '.lab/creative-icons-belt/viewUnified2.so')
 after=ROOT/('.lab/native-setting-loader/viewUnified2.so' if setting else '.lab/native-menu-boot-loader/viewUnified2.so')
 flags=FLAGS+(['-DNMA_LAYOUT_HEADER="native_setting_layout.h"'] if setting else [])
 names=['menu_loader_a','menu_loader_b','restore_global_hook','setting_hook'] if setting else ['menu_loader_a','menu_loader_b','menu_hook','boot_hook']
 page_offsets=[0x214000,0x20d000,0x5b9000] if setting else [0x188000,0x20d000,0x5b9000]
 loader=json.loads((after.parent/'proof.json').read_text());stage=json.loads((ROOT/'.lab/native-install-bound/manifest.json').read_text())
 for key,path in [('before',before),('after',after)]:
  if sha(path)!=loader[key+'_sha256']:raise ValueError('Loader hash changed: '+key)
 for name,digest in loader['source_sha256'].items():
  if sha(ROOT/name)!=digest:raise ValueError('Loader proof stale: '+name)
 sources=[ROOT/'.lab/native-install-bound'/f'input{i}.bin' for i in range(3)]
 for path,meta in zip(sources,stage['files']):
  if sha(path)!=meta['sha256'] or path.stat().st_size!=meta['size']:raise ValueError('Staged file changed')
 old=before.read_bytes();new=after.read_bytes()
 if len(old)!=10854816 or len(new)!=len(old):raise ValueError('Wrong ELF size')
 blob=struct.pack('<II',1,len(old))+hashlib.sha256(old).digest()+hashlib.sha256(new).digest()
 for path in sources:blob+=struct.pack('<I',path.stat().st_size)+bytes.fromhex(sha(path))
 patches=[]
 for name in names:
  p=loader['patches'][name];off=p['va'];size=p['size'];a=bytes.fromhex(p['before_hex']);b=bytes.fromhex(p['after_hex'])
  if old[off:off+size]!=a or new[off:off+size]!=b:raise ValueError('Patch does not match ELF')
  blob+=struct.pack('<II',off,size)+a.ljust(80,b'\0')+b.ljust(80,b'\0');patches.append({'name':name,'offset':off,'size':size})
 check=bytearray(old)
 for p in patches:check[p['offset']:p['offset']+p['size']]=new[p['offset']:p['offset']+p['size']]
 if check!=new:raise ValueError('Unaccounted loader differences')
 for offset in page_offsets:blob+=old[offset:offset+4096]
 if len(blob)!=13140:raise ValueError('Unexpected C bundle ABI '+str(len(blob)))
 binding=hashlib.sha256(b'A7M3-4.04-cow-activate-v1\0'+blob).digest()
 (out/'bundle.bin').write_bytes(blob)
 (out/'bundle.S').write_text('.syntax unified\n.section .rodata.bundle,"a"\n.balign 4\n.global nma_input\nnma_input:\n.incbin "bundle.bin"\n.section .note.GNU-stack,"",%progbits\n')
 (out/'binding.h').write_text('static const unsigned char nma_expected[32]={'+','.join(map(str,binding))+'};\n')
 (out/'entry.c').write_text('''#include "native_menu_activate.h"
#include "binding.h"
extern const NmaBundle nma_input;
static NmaReport report;
__attribute__((constructor)) static void entry(void){
 long fd=nma_linux_syscall(0,5,(long)"/tmp/jiritsu/a7activate.bin",1|64|128,0600,0,0,0);if(fd<0)return;
 nma_run(&nma_input,nma_expected,nma_linux_syscall,0,NMA_MODE,&report);
 unsigned done=0;while(done<sizeof report){long n=nma_linux_syscall(0,4,fd,(long)((unsigned char*)&report+done),sizeof report-done,0,0,0);if(n<=0)break;done+=(unsigned)n;}
 nma_linux_syscall(0,118,fd,0,0,0,0,0);nma_linux_syscall(0,6,fd,0,0,0,0,0);
}
''')
 objects=[]
 for name,path in [('core',ROOT/'research/native_menu_activate.c'),('linux',ROOT/'research/native_menu_activate_linux.c'),('data',out/'bundle.S')]:
  run(['arm-none-eabi-gcc',*flags,'-c',str(path),'-o',str(out/(name+'.o'))],cwd=out);objects.append(str(out/(name+'.o')))
 payloads={}
 for mode,name in enumerate(['preflight','activate','recover','deactivate','deactivate-recover']):
  run(['arm-none-eabi-gcc',*flags,'-I',str(out),f'-DNMA_MODE={mode}','-c',str(out/'entry.c'),'-o',str(out/'entry.o')])
  run(['arm-none-eabi-ld','-shared','--no-undefined','-z','noexecstack',*objects,str(out/'entry.o'),'-o',str(out/(name+'.so'))])
  payloads[name]={'sha256':sha(out/(name+'.so')),'size':(out/(name+'.so')).stat().st_size}
 manifest={'bundle_sha256':binding.hex(),'before_sha256':sha(before),'after_sha256':sha(after),'files':stage['files'],'patches':patches,'payloads':payloads,'source_sha256':{n:sha(ROOT/n) for n in ['research/native_menu_activate.c','research/native_menu_activate.h','research/native_menu_activate_linux.c','research/native_menu_activate_build.py','payloads/sha256.h']},'executed_on_camera':False,'scope':'Build only; requires independent QEMU test proof and live read-only census before activation'}
 manifest.update(profile='setting-menu' if setting else 'global-menu',page_offsets=page_offsets,loader_proof_sha256=sha(after.parent/'proof.json'))
 if setting:manifest['source_sha256']['research/native_setting_layout.h']=sha(ROOT/'research/native_setting_layout.h')
 (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');return manifest
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path);p.add_argument('--setting-menu',action='store_true');a=p.parse_args();print(json.dumps(build(a.out or (ROOT/'.lab/native-setting-activate' if a.setting_menu else OUT),a.setting_menu)['payloads'],indent=2))
