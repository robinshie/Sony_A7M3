#!/usr/bin/env python3
"""Package tested executable first-install candidates, never a camera operation."""
import argparse,hashlib,json,struct,subprocess,zipfile
from pathlib import Path
from stock_activate_build import ROOT,FLAGS
from stock_first_install import json_bytes
from elf32 import ELF
from local import file_sha


def checked_proof(path):
    p=json.loads(path.read_text())
    for n,d in p['source_sha256'].items():
        if file_sha(ROOT/n)!=d:raise ValueError('Stale source proof: '+n)
    return p


def build(candidate,stage,activation,out):
    out.mkdir(parents=True,exist_ok=False)
    s=checked_proof(stage/'manifest.json')
    a=checked_proof(activation/'manifest.json')
    proof=checked_proof(activation/'proof.json')
    if not proof['passed'] or proof['manifest_sha256']!=file_sha(activation/'manifest.json'):raise ValueError('Missing activation proof')
    if s['candidate_sha256']!=file_sha(candidate) or a['candidate_sha256']!=file_sha(candidate):raise ValueError('Mismatched candidates')
    if file_sha(stage/'stock-stage-only.so')!=s['payload_sha256']:raise ValueError('Staging payload changed')
    if s['module_proof_sha256']!=file_sha(ROOT/'.lab/native-module-custom-candidate/proof.json'):raise ValueError('Stale module proof')
    checked_proof(ROOT/'.lab/native-module-custom-candidate/proof.json')
    if s['fault_proof_sha256']!=file_sha(ROOT/'.lab/native-install-test/proof.json'):raise ValueError('Stale stage fault proof')
    checked_proof(ROOT/'.lab/native-install-test/proof.json')
    w=checked_proof(ROOT/'.lab/native-wbi/proof.json')
    if w['payload_sha256']!=file_sha(ROOT/'.lab/native-wbi/probe.so'):raise ValueError('WBI probe changed')
    marker=b'A7ST-WBI-EXPECTED1'+bytes([0xa5])*(1024-len(b'A7ST-WBI-EXPECTED1'))
    # A fixed exported data slot allows per-device binding without a host compiler.
    source='''#include "native_menu_wbi.h"
extern long nma_linux_syscall(void*,long,long,long,long,long,long,long);
const unsigned char a7stock_expected[1024]={VALUES};
static NwbReport r;
__attribute__((constructor)) static void entry(void){
 long fd=nma_linux_syscall(0,5,(long)"/tmp/jiritsu/a7wbi.bin",1|64|128,0600,0,0,0);if(fd<0)return;
 nwb_run(nma_linux_syscall,0,1,a7stock_expected,&r);
 unsigned n=0;while(n<sizeof r){long k=nma_linux_syscall(0,4,fd,(long)((unsigned char*)&r+n),sizeof r-n,0,0,0);if(k<=0)break;n+=(unsigned)k;}
 nma_linux_syscall(0,118,fd,0,0,0,0,0);nma_linux_syscall(0,6,fd,0,0,0,0,0);
}
'''.replace('VALUES',','.join(map(str,marker)))
    (out/'wbi-entry.c').write_text(source)
    objects=[]
    for i,path in enumerate([ROOT/'research/native_menu_wbi.c',ROOT/'research/native_menu_activate_linux.c',out/'wbi-entry.c']):
        obj=out/f'wbi-{i}.o';subprocess.run(['arm-none-eabi-gcc',*FLAGS,'-c',str(path),'-o',str(obj)],check=True);objects.append(str(obj))
    writer=out/'wbi-template.so'
    subprocess.run(['arm-none-eabi-ld','-shared','-Bsymbolic','--no-undefined','-z','noexecstack',*objects,'-o',str(writer)],check=True)
    elf=ELF(writer);symbol=elf.symbols['a7stock_expected'];va=symbol['value']
    offset=next(off+va-base for kind,off,base,_,size,_,_,_ in elf.segments if kind==1 and base<=va and va+1024<=base+size)
    if symbol['size']!=1024 or elf.data[offset:offset+1024]!=marker:raise ValueError('WBI slot not file-backed')
    files={'candidate.zip':candidate.read_bytes(),'stage.so':(stage/'stock-stage-only.so').read_bytes(),
           'wbi-probe.so':(ROOT/'.lab/native-wbi/probe.so').read_bytes(),'wbi-template.so':writer.read_bytes()}
    for profile in a['profiles']:
        folder=activation/profile['name']
        if proof['logs'][profile['name']]!=file_sha(folder/'qemu.log'):raise ValueError('Activation test log changed')
        for mode,meta in profile['payloads'].items():
            p=folder/(mode+'.so')
            if file_sha(p)!=meta['sha256']:raise ValueError('Activation payload changed')
            files[profile['name']+'/'+mode+'.so']=p.read_bytes()
    manifest=dict(kind='a7m3-stock-installer-experimental-v1',model='ILCE-7M3',firmware='4.04',
                  hardware_verified=False,stage=s,activation=a,
                  wbi=dict(offset=offset,bytes=1024,marker_sha256=hashlib.sha256(marker).hexdigest()),
                  sha256={n:hashlib.sha256(v).hexdigest() for n,v in files.items()},
                  scope='Executable experimental stock-only install; physical first-install acceptance pending')
    files['install-manifest.json']=json_bytes(manifest)
    package=out/'Sony_A7M3-Stock404-Experimental.zip'
    with zipfile.ZipFile(package,'x',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name,raw in sorted(files.items()):z.writestr(name,raw)
    package.with_suffix('.zip.sha256').write_text(file_sha(package)+'  '+package.name+'\n')
    print(package);print(file_sha(package))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('candidate','stage','activation','out'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();out=a.out.resolve()
    if not out.is_relative_to((ROOT/'.lab').resolve()):p.error('Output must be under .lab')
    build(a.candidate.resolve(),a.stage.resolve(),a.activation.resolve(),out)
