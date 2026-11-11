#!/usr/bin/env python3
"""Build resident FL integration and run original-node/backup ARM fixture.

Private firmware/LUT bytes remain under .lab. No USB or camera writes. A platform
bootstrap with proven lifecycle witnesses is still required for camera activation.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import zlib

from elf32 import ELF
from native_adjust_fixture import PIECES, STUBS, SHA as CAUTION_SHA
from creative_dispatch import VIEW_SHA
from uxc_strings import Strings

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'.lab/native-module'
BASE=0x40000000

def sha(data):return hashlib.sha256(data).hexdigest()
def run(args,**kw):return subprocess.run(args,check=True,**kw)
def array(name,values,kind='uint8_t'):
    rows=[','.join(str(x) for x in values[i:i+24]) for i in range(0,len(values),24)]
    return f'static const {kind} {name}[{len(values)}]={{\n'+',\n'.join(rows)+'\n};\n'

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--usr',type=Path,required=True);ap.add_argument('--bundle',type=Path,required=True)
    ap.add_argument('--with-bootstrap',action='store_true',help='Link and verify the actual Linux/platform bootstrap for staging')
    args=ap.parse_args();OUT.mkdir(parents=True,exist_ok=True);(OUT/'proof.json').unlink(missing_ok=True)
    locale_proof=json.loads((ROOT/'.lab/native-fl-strings/proof.json').read_text())
    for locale,labels in [('simplifiedchinese',('保存','完成','未完成')),('english',('Save','Complete','Not Complete'))]:
        name=f'string_{locale}.uxc';raw=(ROOT/'.lab/native-fl-strings'/name).read_bytes()
        if sha(raw)!=locale_proof['files'][name]['after_sha256']:raise ValueError('Feedback locale identity differs')
        strings=Strings(raw)
        if tuple(strings.text(key) for key in (0x4eaab,0x4ef85,0x4ef87))!=labels:raise ValueError('Feedback resource text differs')
    run([sys.executable,str(ROOT/'research/native_fl_runtime.py'),'--usr',str(args.usr),'--bundle',str(args.bundle)])
    source=ROOT/'.lab/native-fl-runtime'
    for p in source.glob('*.bin'):shutil.copyfile(p,OUT/p.name)
    shutil.copyfile(source/'native.S',OUT/'runtime.S')
    originals=[(args.bundle/f'{p:08x}.bin').read_bytes() for p in range(0x30004,0x30008)]
    base=(args.bundle/'candidate.bin').read_bytes();codec=(args.bundle/'codec.bin').read_bytes()
    if any(len(t)!=1280 for t in originals+[base]) or len(codec)!=771:raise ValueError('Private input lengths')
    header='#include <stdint.h>\nstatic const uint8_t a7_pkg_original[4][1280]={\n'
    header+=',\n'.join('{'+','.join(str(x) for x in t)+'}' for t in originals)+'\n};\n'
    header+=array('a7_pkg_original_crc',[zlib.crc32(t) for t in originals],'uint32_t')
    header+=array('a7_pkg_base',base)+f'static const uint32_t a7_pkg_base_crc={zlib.crc32(base)}u;\n'
    header+=array('a7_pkg_expand',struct.unpack('<129H',codec[:258]),'uint16_t')+array('a7_pkg_compress',codec[258:])
    header+=array('a7_pkg_original_sha',hashlib.sha256(originals[0]).digest())
    header+='static const char a7_pkg_build[24]="37114_13.2026020901";\n'
    (OUT/'a7-fl-module-data.h').write_text(header)
    caution=ELF(args.usr/'lib/CautionConfig.so');view=ELF(args.usr/'lib/viewUnified2.so')
    if sha(caution.data)!=CAUTION_SHA or sha(view.data)!=VIEW_SHA:raise ValueError('Pinned original native inputs required')
    sections=[];assembly='.syntax unified\n';ranges={}
    for va,size,name in PIECES:
        raw=caution.read(va,size);name='adjust_'+name;(OUT/f'{name}.bin').write_bytes(raw)
        assembly+=f'.section .{name},"ax"\n.incbin "{name}.bin"\n';sections.append((BASE+va,name));ranges[name]=[hex(va),size,sha(raw)]
    vt=bytearray(caution.read(0x918ec0,268))
    for off in range(4,268,4):
        _,symbol=caution.relocations[0x918ec0+off];value=symbol['value']
        struct.pack_into('<I',vt,off,BASE+value if value else 0)
    (OUT/'adjust_vtable.bin').write_bytes(vt)
    assembly+='.section .adjust_vtable,"a"\n.incbin "adjust_vtable.bin"\n.section .adjust_got,"a"\n.word 0x40918ec0\n'
    sections.extend(((BASE+0x918ec0,'adjust_vtable'),(BASE+0x9880b0,'adjust_got')))
    for va,(dest,thumb) in STUBS.items():
        name=f'adjust_stub_{va:x}';sections.append((BASE+va,name));assembly+=f'.section .{name},"ax"\n'
        dest=BASE+dest if isinstance(dest,int) else dest
        assembly+=(f'.thumb\nldr.w ip,[pc,#4]\nbx ip\nnop\n.word {dest}\n' if thumb else f'.arm\nldr ip,[pc,#0]\nbx ip\n.word {dest}\n')
    menu_ranges={'lookup':(0x2f2764,0x34),'stock_get':(0x2f2a2a,0x18),'stock_set':(0x2f2844,0x18),
                 'stock_invalid':(0x2f28a0,0x14),'dispatch_table':(0x72decc,618*4)}
    for name,(va,size) in menu_ranges.items():
        raw=view.read(va,size);(OUT/f'{name}.bin').write_bytes(raw);sections.append((BASE+va,name));ranges[name]=[hex(va),size,sha(raw)]
        assembly+=f'.section .{name},"a'+('x' if name!='dispatch_table' else '')+'"\n'
        assembly+=f'.global {name}\n'+('.thumb\n.thumb_func\n' if name!='dispatch_table' else '')+f'{name}: .incbin "{name}.bin"\n'
    raw=view.read(0x217c7c,0xd6);(OUT/'action.bin').write_bytes(raw);ranges['original_action']=['0x217c7c',len(raw),sha(raw)]
    assembly+='.section .original_action,"ax"\n.thumb\n.global original_action\n.thumb_func\noriginal_action: .incbin "action.bin"\n'
    sections.append((BASE+0x217c7c,'original_action'))
    for name,va,target in [('action_select_menu',0x216ea8,'mock_action_select'),('action_select_category',0x217144,'mock_action_select'),('action_process',0x216a18,'mock_action_process')]:
        assembly+=f'.section .{name},"ax"\n.thumb\nb.w {target}\n';sections.append((BASE+va,name))
    assembly+='.section .action_flag,"ax"\n.arm\nb mock_action_flag\n';sections.append((BASE+0x15aae8,'action_flag'))
    assembly+='''.section .factory,"ax"
.thumb
b.w mock_element_factory
.section .text.kernel_stack,"ax"
.arm
.global call_kernel_writer
call_kernel_writer:
 push {r4,lr}
 mov r4,sp
 ldr sp,=0x44000000
 push {r4,lr}
 ldr ip,=0x4040167c
 blx ip
 pop {r4,lr}
 mov sp,r4
 pop {r4,pc}
.section .note.GNU-stack,"",%progbits
'''
    sections.append((BASE+0x403840,'factory'));(OUT/'nodes.S').write_text(assembly)
    for name,address in re.findall(r'^\.(\w+) (0x[0-9a-f]+) :', (source/'guest.ld').read_text(),re.M):sections.append((int(address,16),name))
    (OUT/'start.S').write_text((source/'start.S').read_text().replace('0x41000000','0x43000000'))
    ld='ENTRY(_start)\nSECTIONS {\n. = 0x41000000;\n.text : { *(.text.start) *(.text*) }\n.rodata : { *(.rodata*) }\n.data : { *(.data*) }\n.bss (NOLOAD) : { __bss_start = .; *(.bss*) *(COMMON) . = ALIGN(8); __bss_end = .; }\n'
    ld+=''.join(f'.{name} {address:#x} : {{ *(.{name}) }}\n' for address,name in sorted(sections))+'}\n';(OUT/'guest.ld').write_text(ld)
    sources=['payloads/a7-fl-module.c','payloads/a7-fl-runtime.c','payloads/a7-fl-runtime-prefs.c',
             'payloads/a7-fl-runtime-control.c','payloads/a7-fl-runtime-recovery.c','payloads/a7-fl-store.c',
             'research/native_adjust.c','research/native_menu.c']
    dependency_proofs={}
    if args.with_bootstrap:
        run([sys.executable,str(ROOT/'research/native_bootstrap.py'),'--usr',str(args.usr)])
        run([sys.executable,str(ROOT/'research/native_bootstrap_test.py')])
        # Older standalone node reports use paths relative to research/. Publish
        # a checked repo-relative copy for downstream bundle proof readers.
        adjust_path=ROOT/'.lab/native-adjust/report.json';adjust=json.loads(adjust_path.read_text())
        for source_path,digest in adjust['source_sha256'].items():
            if sha((ROOT/'research'/source_path).read_bytes())!=digest:raise ValueError('Stale node fixture: '+source_path)
        adjust['input_report_sha256']=sha(adjust_path.read_bytes())
        adjust['source_sha256']={'research/'+p:d for p,d in adjust['source_sha256'].items()}
        (adjust_path.parent/'integration-proof.json').write_text(json.dumps(adjust,indent=2)+'\n')
        for name in ('native-bootstrap/compile-proof.json','native-bootstrap-test/proof.json','native-menu-boot-loader/proof.json','native-setting-loader/proof.json','native-adjust/integration-proof.json','native-menu-action-tree/proof.json'):
            path=ROOT/'.lab'/name;proof=json.loads(path.read_text())
            if not proof.get('source_sha256'):raise ValueError(f'Missing checked source provenance: {name}')
            for source_path,digest in proof['source_sha256'].items():
                source_file=ROOT/source_path
                if sha(source_file.read_bytes())!=digest:raise ValueError(f'Stale dependency evidence: {source_path}')
            dependency_proofs[name]=sha(path.read_bytes())
            if name=='native-setting-loader/proof.json' and (proof.get('module_call_return_va')!=0x5b9b30 or
                proof.get('module_call_lr_va')!=0x5b9b31 or not proof.get('lifecycle')):
                raise ValueError('SettingMenu loader lacks checked caller/lifecycle evidence')
        sources+=['payloads/a7-fl-bootstrap.c','payloads/a7-fl-posix.c']
    flags=['-mcpu=cortex-a9','-marm','-mfloat-abi=soft','-mno-unaligned-access','-Os','-Wall','-Wextra','-Werror','-ffreestanding',
           '-fno-builtin','-fno-strict-aliasing','-fstack-usage','-fno-unwind-tables','-fno-asynchronous-unwind-tables',
           '-I',str(ROOT/'payloads'),'-I',str(ROOT/'research'),'-I',str(OUT),'-I',str(ROOT/'.lab/native-bootstrap')]
    run(['arm-none-eabi-gcc',*flags,'-nostdlib','-T','guest.ld','start.S','runtime.S','nodes.S',
         str(ROOT/'research/native_module_harness.c'),*[str(ROOT/p) for p in sources],'-lgcc','-o','module-test.elf'],cwd=OUT)
    objects=[]
    for i,path in enumerate(sources):
        name=f'part-{i}.o';objects.append(name)
        run(['arm-none-eabi-gcc',*flags,'-fPIC','-c',str(ROOT/path),'-o',name],cwd=OUT)
    run(['arm-none-eabi-gcc',*flags,'-nostdlib','-shared','-Wl,--no-undefined,-Bsymbolic-functions,-z,noexecstack',*objects,'-lgcc','-o','liba7-fl-module.so'],cwd=OUT)
    result=run(['qemu-system-arm','-M','virt','-cpu','cortex-a15','-m','1024','-smp','1','-nodefaults','-audio','none','-nic','none','-display','none','-monitor','none','-serial','stdio','-semihosting-config','enable=on,target=native','-device',f'loader,file={OUT}/module-test.elf,cpu-num=0'],capture_output=True,timeout=30)
    log=result.stdout+result.stderr;(OUT/'qemu.log').write_bytes(log);print(log.decode(),end='')
    if b'NATIVE_FL_MODULE_PASSED' not in log or b'FAIL ' in log:raise ValueError('Integration fixture failed')
    run(['arm-none-eabi-gcc',*flags,'-DA7_FL_TEST_SAVED_BOOT','-nostdlib','-T','guest.ld','start.S','runtime.S','nodes.S',
         str(ROOT/'research/native_module_harness.c'),*[str(ROOT/p) for p in sources],'-lgcc','-o','module-boot-test.elf'],cwd=OUT)
    boot_run=run(['qemu-system-arm','-M','virt','-cpu','cortex-a15','-m','1024','-smp','1','-nodefaults','-audio','none','-nic','none','-display','none','-monitor','none','-serial','stdio','-semihosting-config','enable=on,target=native','-device',f'loader,file={OUT}/module-boot-test.elf,cpu-num=0'],capture_output=True,timeout=30)
    boot_log=boot_run.stdout+boot_run.stderr;(OUT/'boot.log').write_bytes(boot_log);print(boot_log.decode(),end='')
    if b'NATIVE_FL_MODULE_BOOT_PASSED' not in boot_log or b'FAIL ' in boot_log:raise ValueError('Cold boot integration fixture failed')
    source_files=sources+['payloads/a7-fl-module.h','payloads/a7-fl-runtime.h','payloads/a7-fl-runtime-prefs.h',
        'payloads/a7-fl-runtime-control.h','payloads/a7-fl-runtime-recovery.h','payloads/a7-fl-color.h','payloads/a7-fl-store.h',
        'research/native_adjust.h','research/native_menu.h','research/native_module.py','research/native_module_harness.c',
        'research/native_fl_runtime_harness.c','research/native_fl_runtime.py','research/native_adjust_fixture.py','research/native_adjust_harness.c','research/elf32.py','research/uxc_strings.py']
    if args.with_bootstrap:source_files+=['payloads/a7-fl-bootstrap.h','payloads/a7-fl-posix.h','research/native_bootstrap.py','research/native_bootstrap_test.py','research/native_bootstrap_test_harness.c']
    proof={'scope':'Original Sony generic nodes, process-manager dispatch and backup writer with modeled platform/OSAL/kernel/filesystem; resident FL integration',
           'original_caution_sha256':CAUTION_SHA,'original_view_sha256':VIEW_SHA,'original_ranges':ranges,
           'source_sha256':{p:sha((ROOT/p).read_bytes()) for p in source_files},
           'artifact_sha256':{p:sha((OUT/p).read_bytes()) for p in ('module-test.elf','module-boot-test.elf','liba7-fl-module.so','qemu.log','boot.log','a7-fl-module-data.h')},
           'module_sha256':sha((OUT/'liba7-fl-module.so').read_bytes()),'placeholder':not args.with_bootstrap,
           'ready_for_staging':args.with_bootstrap,'dependency_proof_sha256':dependency_proofs,
           'platform_bootstrap_guard_fixture_verified':args.with_bootstrap,
           'live_platform_bootstrap_verified':False,'camera_integration':False,'flash_ready':False,
           'feature_scope':'Still-photo Creative Look menu with native Page hierarchy and nonnegative selection enums; FL-inspired LUT with five signed backend controls and explicit Save; last three spatial controls disabled',
           'hardware_validation_required':['Actual still-view boot Backup API readiness','Physical menu navigation and Save action','Cold-power persistence and calibration readback']}
    (OUT/'proof.json').write_text(json.dumps(proof,indent=2)+'\n')

if __name__=='__main__':main()
