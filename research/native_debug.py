#!/usr/bin/env python3
"""Build or decode the read-only private-state diagnostic; no camera transport."""
import argparse,hashlib,json,struct,subprocess
from pathlib import Path
from elf32 import ELF
from native_inspect import sha
R=Path(__file__).resolve().parents[1];O=R/'.lab/native-debug'
CHECKS=['vm_aligned','vm_current_allowed','vm_cached_allowed','manager_allowed','manager_original_vtable',
 'page_aligned','page_vtable','page_count3','page_properties','page_children_aligned','page_children_allowed',
 'page_warm_profile','page_cold_profile','three_children_allowed','manager_vtable_allowed','parent_vtable_allowed',
 'bootstrap_manager_address','bootstrap_manager_vtable','module_vm_matches_actual','bootstrap_platform_vm_matches_actual',
 'bootstrap_bound_vm_matches_actual','cached_count_bounded','module_installed','module_fault']
def run(a,**kw):return subprocess.run(a,check=True,**kw)
def decode(path):
 b=path.read_bytes();assert len(b)==66740
 words=struct.unpack('<301I',b[:1204]);assert words[0:2]==(0x41374644,1) and words[3]==len(b)
 import sys
 sys.path.insert(0,str(R))
 from camera.native_status import decode_report
 def signed(x):return x if x<0x80000000 else x-0x100000000
 def platform(start):
  names=['view','caution','view_manager','process_manager','manager_vtable','parent_vtable','creative_style']
  return {**dict(zip(names,words[start:start+7])),'parents':list(words[start+7:start+15]),'anchors':list(words[start+15:start+23]),'parent_count':words[start+23]}
 result={'status':signed(words[2]),'flags':words[4],'private_stable':words[5],
  'baseline':decode_report(b[32:180]),'boot_head':dict(zip(['lock','ready','installing','mode','caller','view','caution','backup','prepared_view','prepared_caution','prepared_backup','bound_vm','cached_ranges'],words[45:58])),
  'bootstrap_platform':platform(58),'module_platform':platform(94),
  'libobj_base':words[146],'vm_global':words[147],'actual_vm':words[148],'vm_words':list(words[149:177]),'manager':list(words[177:179]),
  'page':dict(zip(['vtable','children','count','properties','parent','depth','selected','serial','index','state'],words[179:189])),
  'children':list(words[189:197]),'child_words':[list(words[197+i*10:207+i*10]) for i in range(8)],
  'checks':dict(zip(CHECKS,words[277:301])),'maps_bytes':words[6]}
 path.with_suffix('.maps').write_bytes(b[1204:1204+words[6]])
 path.with_suffix('.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));return result
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--usr',type=Path);p.add_argument('--decode',type=Path);a=p.parse_args()
 if a.decode:return decode(a.decode)
 assert a.usr
 O.mkdir(parents=True,exist_ok=True)
 original=R/'.lab/native-inspect';ip=json.loads((original/'proof.json').read_text())
 for name,digest in ip['source_sha256'].items():assert sha((R/name).read_bytes())==digest,name
 assert sha((original/'a7-fl-inspect-pins.h').read_bytes())==ip['pins_sha256']
 mp=R/'.lab/native-module';module=ELF(mp/'liba7-fl-module.so');assert sha(module.data)==ip['module_sha256']
 def private(name):
  result=[]
  for section in module.sections:
   if section[1]!=2:continue
   strings=module.section(section[6])
   for offset in range(section[4],section[4]+section[5],section[9]):
    n,v,s,_,_,_=struct.unpack_from('<IIIBBH',module.data,offset)
    if strings[n:strings.index(b'\0',n)].decode()==name:result.append((v,s))
  assert len(result)==1;return result[0]
 boot=private('boot');context=private('module');obj=ELF(a.usr/'lib/libObj.so');vm=obj.symbols['pViewManager']['value']
 assert boot==(0x4bb28,0x120c0) and context==(0x9a9c,0x42064) and vm==0x13289f4
 pins=f'#define A7_DEBUG_BOOT_VA {boot[0]}u\n#define A7_DEBUG_BOOT_SIZE {boot[1]}u\n#define A7_DEBUG_MODULE_VA {context[0]}u\n#define A7_DEBUG_VM_GLOBAL {vm}u\n'
 (O/'a7-fl-debug-pins.h').write_text(pins)
 flags=['-mcpu=cortex-a9','-marm','-mfloat-abi=soft','-mno-unaligned-access','-Os','-Wall','-Wextra','-Werror','-ffreestanding','-fno-builtin','-fno-unwind-tables','-fno-asynchronous-unwind-tables','-I',str(R/'payloads'),'-I',str(R/'research'),'-I',str(O),'-I',str(original)]
 run(['arm-none-eabi-gcc',*flags,'-fPIC','-nostdlib','-shared','-Wl,-Bsymbolic','-Wl,-z,noexecstack','-Wl,--no-undefined',str(R/'payloads/a7-fl-debug.c'),'-lgcc','-o',str(O/'debug.so')])
 # Reuse attested original PLT and module-accessor fixtures, without rebuilding
 # or modifying the frozen original inspector artifact.
 for name in ['native.S','test.ld','start.S','module-rx.bin','dlopen.bin','dlsym.bin','dlclose.bin']:(O/name).write_bytes((original/name).read_bytes())
 run(['arm-none-eabi-gcc',*flags,'-DA7_FL_DEBUG_TEST','-nostdlib','-T','test.ld','start.S','native.S',str(R/'payloads/a7-fl-debug.c'),str(R/'research/native_debug_harness.c'),'-lgcc','-o','debug-test.elf'],cwd=O)
 t=run(['qemu-system-arm','-M','virt','-cpu','cortex-a15','-m','1024','-nodefaults','-audio','none','-nic','none','-display','none','-monitor','none','-serial','stdio','-semihosting-config','enable=on,target=native','-device',f'loader,file={O}/debug-test.elf,cpu-num=0'],capture_output=True,timeout=15)
 log=t.stdout+t.stderr;(O/'qemu.log').write_bytes(log);print(log.decode(),end='');assert b'NATIVE_DEBUG_PASSED' in log and b'FAIL ' not in log
 sources=['payloads/a7-fl-debug.c','research/native_debug.py','research/native_debug_harness.c',*ip['source_sha256']]
 proof={'payload_sha256':sha((O/'debug.so').read_bytes()),'module_sha256':sha(module.data),'original_inspect_proof_sha256':sha((original/'proof.json').read_bytes()),'source_sha256':{s:sha((R/s).read_bytes()) for s in sources},'pins_sha256':sha(pins.encode()),'libobj_sha256':sha(obj.data),'private_symbols':{'boot':boot,'module':context,'pViewManager':vm},'report_bytes':66740,'report_name':'a7fldbg.bin','qemu_log_sha256':sha(log),'scope':'Read-only private snapshots and actual VM/page/span diagnostics; original module/accessor code pinned; no initializer or setter calls','camera_execution':False}
 (O/'proof.json').write_text(json.dumps(proof,indent=2)+'\n');print('payload_sha256',proof['payload_sha256'])
if __name__=='__main__':main()
