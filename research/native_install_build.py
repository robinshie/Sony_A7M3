#!/usr/bin/env python3
"""Bind a reviewed real-module bundle to the tested filesystem-only installer.

Builds a payload but never uploads or executes it. Rejects placeholder/unattested
modules. This stage installs module/locales only; loader activation is separate.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
from elf32 import ELF

ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def pin_sources(proof):
    if not proof.get('source_sha256'):raise ValueError('Missing source attestation')
    for path,digest in proof['source_sha256'].items():
        if sha(ROOT/path)!=digest:raise ValueError('Source changed after proof: '+path)
def array(data):return '{'+','.join(str(x) for x in data)+'}'


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--module',required=True,type=Path)
    cli.add_argument('--module-proof',required=True,type=Path)
    cli.add_argument('--base',type=Path,default=ROOT/'.lab/creative-icons-belt')
    cli.add_argument('--strings',type=Path,default=ROOT/'.lab/native-fl-strings')
    cli.add_argument('--out',type=Path,default=ROOT/'.lab/native-install-bound')
    a=cli.parse_args()
    module_proof=json.loads(a.module_proof.read_text())
    if module_proof.get('placeholder') is not False or module_proof.get('ready_for_staging') is not True:
        raise ValueError('Real module is not explicitly attested ready for staging')
    if module_proof.get('module_sha256')!=sha(a.module):raise ValueError('Module attestation hash mismatch')
    pin_sources(module_proof)
    module=ELF(a.module)
    if 'a7_fl_install' not in module.symbols or not module.symbols['a7_fl_install']['value']:raise ValueError('Missing resident module entry')
    plan_manifest=ROOT/'.lab/native-install-plan/manifest.json'
    if plan_manifest.exists():
        plan=json.loads(plan_manifest.read_text())
        if plan.get('module_placeholder') is True and plan['module']['sha256']==sha(a.module):
            raise ValueError('Known offline placeholder cannot be installed')
    fault=json.loads((ROOT/'.lab/native-install-test/proof.json').read_text());pin_sources(fault)
    strings=json.loads((a.strings/'proof.json').read_text());pin_sources(strings)
    native_resource=json.loads((ROOT/'.lab/native-resource/report.json').read_text())
    for n,digest in native_resource['source_sha256'].items():
        if sha(ROOT/'research'/n)!=digest:raise ValueError('Native resource test changed')
    if native_resource['input_proof_sha256']!=sha(a.strings/'proof.json'):raise ValueError('Native resource proof is stale')
    base=json.loads((a.base/'manifest.json').read_text())
    paths=[a.module,a.strings/'string_simplifiedchinese.uxc',a.strings/'string_english.uxc']
    for p in paths[1:]:
        if sha(p)!=strings['files'][p.name]['after_sha256']:raise ValueError('Locale output changed')
        if base['files']['/share/app/'+p.name]['after_sha256']!=strings['files'][p.name]['before_sha256']:raise ValueError('Locale baseline differs')
    view=a.base/'viewUnified2.so'
    if sha(view)!=base['files']['/lib/viewUnified2.so']['after_sha256']:raise ValueError('View baseline changed')
    sizes=[p.stat().st_size for p in paths];digests=[bytes.fromhex(sha(p)) for p in paths]
    oldsizes=[strings['files'][p.name]['before_bytes'] for p in paths[1:]]
    oldhash=[bytes.fromhex(strings['files'][p.name]['before_sha256']) for p in paths[1:]]
    attestation=bytes.fromhex(sha(a.module_proof));vhash=bytes.fromhex(sha(view));vsize=view.stat().st_size
    h=hashlib.sha256(b'A7M3-4.04-filesystem-stage-v1\0'+struct.pack('<II',1,0)+attestation)
    for size,digest in zip(sizes,digests):h.update(struct.pack('<I',size)+digest)
    for size,digest in zip(oldsizes,oldhash):h.update(struct.pack('<I',size)+digest)
    h.update(struct.pack('<I',vsize)+vhash);binding=h.digest()
    out=a.out;out.mkdir(parents=True,exist_ok=True);(out/'manifest.json').unlink(missing_ok=True)
    asm='.syntax unified\n.section .rodata.bundle,"a"\n'
    for j,p in enumerate(paths):
        name=f'input{j}.bin';(out/name).write_bytes(p.read_bytes())
        asm+=f'.balign 4\n.global input{j}\ninput{j}:\n.incbin "{name}"\n'
    asm+='.section .note.GNU-stack,"",%progbits\n';(out/'bundle.S').write_text(asm)
    text='#include "native_install.h"\nextern const unsigned char input0[],input1[],input2[];\n'
    text+='static const NativeInstallBundle bundle={1,0,'+array(attestation)+',{'+','.join('{input%d,%d,%s}'%(j,sizes[j],array(digests[j])) for j in range(3))+'},'+array(oldsizes)+','+str(vsize)+',{'+','.join(array(x) for x in oldhash)+'},'+array(vhash)+'};\n'
    text+='static const unsigned char expected[32]='+array(binding)+';\n'
    text+='''static NativeInstallReport report;
__attribute__((constructor)) static void install(void){
 long fd=native_install_linux_syscall(0,5,(long)"/tmp/jiritsu/a7install.bin",1|64|128,0600,0,0,0);
 if(fd<0)return;
 native_install_run(&bundle,expected,native_install_linux_syscall,0,&report);
 unsigned used=0;while(used<sizeof report){long n=native_install_linux_syscall(0,4,fd,(long)((unsigned char *)&report+used),sizeof report-used,0,0,0);if(n<=0)break;used+=(unsigned)n;}native_install_linux_syscall(0,118,fd,0,0,0,0,0);native_install_linux_syscall(0,6,fd,0,0,0,0,0);
}
'''
    (out/'bundle.c').write_text(text)
    common=['arm-none-eabi-gcc','-mcpu=cortex-a9','-marm','-mfloat-abi=soft','-mno-unaligned-access','-fPIC','-ffreestanding','-fno-builtin','-fno-stack-protector','-fno-unwind-tables','-fno-asynchronous-unwind-tables','-Os','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-I',str(ROOT/'research')]
    objects=[]
    for name,path in [('core',ROOT/'research/native_install.c'),('linux',ROOT/'research/native_install_linux.c'),('entry',out/'bundle.c'),('data',out/'bundle.S')]:
        subprocess.run(common+['-c',str(path),'-o',str(out/(name+'.o'))],cwd=out,check=True);objects.append(str(out/(name+'.o')))
    subprocess.run(['arm-none-eabi-ld','-shared','--no-undefined','-z','noexecstack',*objects,'-o',str(out/'install.so')],cwd=out,check=True)
    proof={'package_kind':'native-filesystem-module-locales-only-v1','loader_activated':False,'executed':False,
           'module_placeholder':False,'bundle_sha256':binding.hex(),'payload_sha256':sha(out/'install.so'),
           'module_proof_sha256':sha(a.module_proof),'fault_proof_sha256':sha(ROOT/'.lab/native-install-test/proof.json'),
           'resource_proof_sha256':sha(ROOT/'.lab/native-resource/report.json'),
           'source_sha256':{n:sha(ROOT/n) for n in ['research/native_install.c','research/native_install.h','research/native_install_linux.c','research/native_install_build.py','payloads/sha256.h']},
           'files':[{'name':p.name,'size':size,'sha256':digest.hex()} for p,size,digest in zip(paths,sizes,digests)],
           'scope':'Real-module-bound filesystem installer only; no live execution, loader patch, or whole-firmware flash'}
    (out/'manifest.json').write_text(json.dumps(proof,indent=2)+'\n');print('NATIVE_INSTALL_BUNDLE_BUILT',binding.hex())


if __name__=='__main__':main()
