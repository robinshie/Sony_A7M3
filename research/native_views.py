#!/usr/bin/env python3
"""Build/decode the independent bounded ViewManager inspection probe."""
import argparse,json,subprocess,struct
from pathlib import Path
from native_inspect import sha
from native_debug import decode as decode_debug
R=Path(__file__).resolve().parents[1];O=R/'.lab/native-views'
def run(a,**kw):return subprocess.run(a,check=True,**kw)
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--decode',type=Path);a=p.parse_args()
 if a.decode:
  b=a.decode.read_bytes();assert len(b)==97492
  head=struct.unpack_from('<3Ii4I',b);assert head[:3]==(0x41374656,1,97492)
  debug_path=a.decode.with_suffix('.debug.bin');debug_path.write_bytes(b[32:66772]);d=decode_debug(debug_path)
  count=head[4];records=[]
  if 0<count<=256:
   for index in range(count*2):
    w=struct.unpack_from('<15I',b,66772+index*60)
    records.append({'table':index//count,'index':index%count,'flags':w[0],'slot':list(w[1:5]),'object':list(w[5:]),'kind':'SettingMenu' if w[0]&16 else 'GlobalMenu' if w[0]&8 else 'other' if w[0]&2 else 'unreadable-or-empty','owner_matches':bool(w[0]&4)})
  out={'status':head[3],'count':count,'arrays':list(head[5:7]),'records_read':head[7],'views':records,'debug_json':str(debug_path.with_suffix('.json')),'global_menu_count':sum(r['kind']=='GlobalMenu' for r in records),'setting_menu_count':sum(r['kind']=='SettingMenu' for r in records)}
  a.decode.with_suffix('.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2));return
 O.mkdir(parents=True,exist_ok=True);D=R/'.lab/native-debug';I=R/'.lab/native-inspect'
 proof=json.loads((D/'proof.json').read_text())
 for name,digest in proof['source_sha256'].items():assert sha((R/name).read_bytes())==digest,name
 assert sha((D/'a7-fl-debug-pins.h').read_bytes())==proof['pins_sha256']
 flags=['-mcpu=cortex-a9','-marm','-mfloat-abi=soft','-mno-unaligned-access','-Os','-Wall','-Wextra','-Werror','-ffreestanding','-fno-builtin','-fno-unwind-tables','-fno-asynchronous-unwind-tables','-I',str(R/'payloads'),'-I',str(R/'research'),'-I',str(D),'-I',str(I)]
 run(['arm-none-eabi-gcc',*flags,'-fPIC','-nostdlib','-shared','-Wl,-Bsymbolic','-Wl,-z,noexecstack','-Wl,--no-undefined',str(R/'payloads/a7-fl-views.c'),'-lgcc','-o',str(O/'views.so')])
 for name in ['native.S','test.ld','start.S','module-rx.bin','dlopen.bin','dlsym.bin','dlclose.bin']:(O/name).write_bytes((I/name).read_bytes())
 run(['arm-none-eabi-gcc',*flags,'-DA7_FL_VIEWS_TEST','-nostdlib','-T','test.ld','start.S','native.S',str(R/'payloads/a7-fl-views.c'),str(R/'research/native_views_harness.c'),'-lgcc','-o','views-test.elf'],cwd=O)
 t=run(['qemu-system-arm','-M','virt','-cpu','cortex-a15','-m','1024','-nodefaults','-audio','none','-nic','none','-display','none','-monitor','none','-serial','stdio','-semihosting-config','enable=on,target=native','-device',f'loader,file={O}/views-test.elf,cpu-num=0'],capture_output=True,timeout=15)
 log=t.stdout+t.stderr;(O/'qemu.log').write_bytes(log);print(log.decode(),end='');assert b'NATIVE_VIEWS_PASSED' in log and b'FAIL ' not in log
 sources=['payloads/a7-fl-views.c','research/native_views.py','research/native_views_harness.c',*proof['source_sha256']]
 proof={'payload_sha256':sha((O/'views.so').read_bytes()),'module_sha256':proof['module_sha256'],'debug_proof_sha256':sha((D/'proof.json').read_bytes()),'source_sha256':{s:sha((R/s).read_bytes()) for s in sources},'report_bytes':97492,'report_name':'a7flview.bin','qemu_log_sha256':sha(log),'scope':'Read-only bounded ViewManager slot arrays; type by pinned original vtable and owner by View+0x24; no initializer/setter calls','camera_execution':False}
 (O/'proof.json').write_text(json.dumps(proof,indent=2)+'\n');print('payload_sha256',proof['payload_sha256'])
if __name__=='__main__':main()
