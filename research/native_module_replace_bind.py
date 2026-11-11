#!/usr/bin/env python3
"""Bind the tested single-module atomic upgrade; never access a camera."""
import argparse,hashlib,json,struct,subprocess
from pathlib import Path
from elf32 import ELF
ROOT=Path(__file__).resolve().parents[1];LAB=ROOT/'.lab'
OLD='2478cec27f88e838f03915da36ac09c66efff9d6a3bd53d59fc487f6cd345aac'
VIEW='a1c4d8e88f54f71786ff53bc15a59c32a2969a6ffc934ef77728123d8af172a7'
FLAGS=['-mcpu=cortex-a9','-marm','-mfloat-abi=soft','-mno-unaligned-access','-fPIC','-Os','-ffreestanding','-fno-builtin','-fno-stack-protector','-fno-unwind-tables','-fno-asynchronous-unwind-tables','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-I',str(ROOT/'research')]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def pin(p):
 if not p.get('source_sha256'):raise ValueError('Missing source attestation')
 for n,d in p['source_sha256'].items():
  if sha(ROOT/n)!=d:raise ValueError('Source changed: '+n)
def arr(b):return '{'+','.join(str(v) for v in b)+'}'
def bind(old,module,proof,view,out):
 old,module,proof,view,out=map(lambda p:Path(p).resolve(),(old,module,proof,view,out))
 p=json.loads(proof.read_text());pin(p)
 if p.get('placeholder') is not False or p.get('ready_for_staging') is not True or p['module_sha256']!=sha(module):raise ValueError('Unattested module')
 for n,d in p['dependency_proof_sha256'].items():
  if sha(LAB/n)!=d:raise ValueError('Module dependency changed: '+n)
  pin(json.loads((LAB/n).read_text()))
 core_path=LAB/'native-module-replace-test/proof.json';core=json.loads(core_path.read_text());pin(core)
 action_path=LAB/'native-menu-action-tree/proof.json';action=json.loads(action_path.read_text());pin(action)
 if sha(LAB/'native-menu-action-tree/qemu.log')!=action['qemu_log_sha256']:raise ValueError('Action fixture log changed')
 if sha(old)!=OLD or old.stat().st_size!=42208 or sha(view)!=VIEW or view.stat().st_size!=10854816:raise ValueError('Incorrect deployment baseline')
 if 'a7_fl_install' not in ELF(module).symbols:raise ValueError('Missing module entry')
 sizes=[old.stat().st_size,module.stat().st_size,view.stat().st_size]
 hashes=[bytes.fromhex(sha(x)) for x in (old,module,view,proof)]
 binding=hashlib.sha256(b'A7M3-single-module-r1\0'+struct.pack('<4I',1,*sizes)+b''.join(hashes)).digest()
 out.mkdir(mode=0o700,parents=True,exist_ok=False)
 for name,path in [('old-module.so',old),('new-module.so',module),('module-proof.json',proof)]: (out/name).write_bytes(path.read_bytes())
 (out/'data.S').write_text('.syntax unified\n.section .rodata,"a"\n.balign 4\n.global candidate\ncandidate:\n.incbin "new-module.so"\n.section .note.GNU-stack,"",%progbits\n')
 code='#include "native_module_replace.h"\nextern const unsigned char candidate[];\n'
 code+='/* Model identity is checked by the authenticated host in this session.\n * This callback records that integration precondition, not a native model read.\n * Native core separately enforces BUILD and full old-module/view hashes. */\nstatic int host_identity_precondition(void*p){(void)p;return 1;}\n'
 code+='static const NMRBundle bundle={1,'+','.join(str(v) for v in sizes)+',candidate,'+','.join(arr(v) for v in hashes)+'};\n'
 code+='static const unsigned char expected[32]='+arr(binding)+';\n'
 code+='''static NMRReport report;
__attribute__((constructor)) static void entry(void){
 long fd=nmr_linux_call(0,5,(long)"/tmp/jiritsu/a7modup.bin",1|64|128|0x8000,0600,0,0,0);if(fd<0)return;
 nmr_run(&bundle,expected,nmr_linux_call,0,host_identity_precondition,0,NMR_WRITE,&report);
 unsigned n=0;while(n<sizeof report){long k=nmr_linux_call(0,4,fd,(long)((unsigned char*)&report+n),sizeof report-n,0,0,0);if(k<=0)break;n+=(unsigned)k;}
 nmr_linux_call(0,118,fd,0,0,0,0,0);nmr_linux_call(0,6,fd,0,0,0,0,0);
}
'''
 (out/'entry.c').write_text(code)
 objects=[]
 for name,path in [('core',ROOT/'research/native_module_replace.c'),('linux',ROOT/'research/native_module_replace_linux.c'),('data',out/'data.S')]:
  obj=out/(name+'.o');subprocess.run(['arm-none-eabi-gcc',*FLAGS,'-c',str(path),'-o',str(obj)],cwd=out,check=True);objects.append(str(obj))
 payloads={}
 for name,mode in [('preflight',0),('replace',1)]:
  obj=out/(name+'.o');subprocess.run(['arm-none-eabi-gcc',*FLAGS,f'-DNMR_WRITE={mode}','-c',str(out/'entry.c'),'-o',str(obj)],cwd=out,check=True)
  target=out/(name+'.so');subprocess.run(['arm-none-eabi-ld','-shared','--no-undefined','-z','noexecstack',*objects,str(obj),'-o',str(target)],check=True)
  payloads[name]={'sha256':sha(target),'size':target.stat().st_size}
 sources={**core['source_sha256'],**{n:sha(ROOT/n) for n in ['research/native_module_replace_bind.py','camera/native_module_replace.py']}}
 manifest={'version':1,'kind':'native-module-replace-r1','bundle_sha256':binding.hex(),'old':{'sha256':OLD,'size':sizes[0]},'new':{'sha256':sha(module),'size':sizes[1]},'view':{'sha256':VIEW,'size':sizes[2]},'module_proof_sha256':sha(proof),'core_proof_sha256':sha(core_path),'action_proof_sha256':sha(action_path),'model_identity_boundary':'Authenticated same-session host check before either payload; native callback does not read model','payloads':payloads,'entry_sha256':sha(out/'entry.c'),'data_sha256':sha(out/'data.S'),'source_sha256':sources,'scope':'Only /usr/lib/a7fl.so atomic replacement; existing mapped old DSO survives until reboot; no loader, locale, LUT, or WBI changes'}
 (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');return manifest
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('old','module','proof','view','out'):p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args();print(json.dumps(bind(a.old,a.module,a.proof,a.view,a.out),indent=2))
