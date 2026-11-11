#!/usr/bin/env python3
"""Bind the tested WBI invalidator to one actual read-only 1024-byte capture."""
import argparse,hashlib,json,subprocess
from pathlib import Path
from native_menu_wbi import ROOT,OUT,FLAGS,decode,sha,run
def bind(capture,out):
 capture=Path(capture).resolve();out=Path(out).resolve()
 p=json.loads((OUT/'proof.json').read_text())
 for n,d in p['source_sha256'].items():
  if sha(ROOT/n)!=d:raise ValueError('Read-only source proof changed: '+n)
 if sha(OUT/'qemu.log')!=p['qemu_log_sha256'] or b'NWB_ARM_ALL_PASS' not in (OUT/'qemu.log').read_bytes():raise ValueError('Missing exact ARM core proof')
 report=(capture/'report.bin').read_bytes();r=decode(report);pre=(capture/'preimage.bin').read_bytes()
 if not(r['mode']==0 and r['status']==0 and r['phase']==3 and not r['error'] and r['capacity_lo']==62914560 and not r['capacity_hi'] and r['header_kind'] in (1,2) and r['neighbor_ok']==1 and not r['written']):raise ValueError('Capture is not a successful writable-header preflight')
 if len(pre)!=1024 or pre!=report[88:] or hashlib.sha256(pre).hexdigest()!=r['preimage_sha256']:raise ValueError('Capture preimage mismatch')
 if (capture/'header.bin').read_bytes()!=pre[:512] or (capture/'neighbor.bin').read_bytes()!=pre[512:]:raise ValueError('Capture backups mismatch')
 out.mkdir(mode=0o700,parents=True,exist_ok=False)
 (out/'preimage.bin').write_bytes(pre);(out/'source-report.bin').write_bytes(report)
 (out/'data.S').write_text('.syntax unified\n.section .rodata,"a"\n.balign 4\n.global nwb_expected\nnwb_expected:\n.incbin "preimage.bin"\n.section .note.GNU-stack,"",%progbits\n')
 entry='''#include "native_menu_wbi.h"
extern long nma_linux_syscall(void*,long,long,long,long,long,long,long);
extern const unsigned char nwb_expected[1024];
static NwbReport r;
__attribute__((constructor)) static void entry(void){long fd=nma_linux_syscall(0,5,(long)"/tmp/jiritsu/a7wbi.bin",1|64|128,0600,0,0,0);if(fd<0)return;nwb_run(nma_linux_syscall,0,1,nwb_expected,&r);unsigned done=0;while(done<sizeof r){long n=nma_linux_syscall(0,4,fd,(long)((unsigned char*)&r+done),sizeof r-done,0,0,0);if(n<=0)break;done+=(unsigned)n;}nma_linux_syscall(0,118,fd,0,0,0,0,0);nma_linux_syscall(0,6,fd,0,0,0,0,0);}
'''
 (out/'entry.c').write_text(entry)
 for n,path in [('core',ROOT/'research/native_menu_wbi.c'),('linux',ROOT/'research/native_menu_activate_linux.c'),('entry',out/'entry.c'),('data',out/'data.S')]:run(['arm-none-eabi-gcc',*FLAGS,'-fPIC','-c',str(path),'-o',str(out/(n+'.o'))],cwd=out)
 run(['arm-none-eabi-ld','-shared','--no-undefined','-z','noexecstack',*[str(out/(n+'.o')) for n in ('core','linux','entry','data')],'-o',str(out/'invalidate.so')])
 sources={**p['source_sha256'],**{n:sha(ROOT/n) for n in ['research/native_menu_wbi_bind.py','camera/native_wbi.py','camera/native_wbi_write.py']}}
 manifest={'version':1,'source_capture':str(capture),'source_report_sha256':sha(out/'source-report.bin'),'preimage_sha256':sha(out/'preimage.bin'),'header_sha256':hashlib.sha256(pre[:512]).hexdigest(),'neighbor_sha256':hashlib.sha256(pre[512:]).hexdigest(),'payload_sha256':sha(out/'invalidate.so'),'payload_bytes':(out/'invalidate.so').stat().st_size,'entry_sha256':sha(out/'entry.c'),'data_source_sha256':sha(out/'data.S'),'readonly_proof_sha256':sha(OUT/'proof.json'),'source_sha256':sources,'scope':'Exact tested ARM core bound to captured1024; host requires fresh same-session preflight, explicit write authorization and fsynced intent; only first512 zeroed; no undo'}
 (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');return manifest
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--capture',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();print(json.dumps(bind(a.capture,a.out),indent=2))
