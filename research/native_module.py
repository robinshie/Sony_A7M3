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
    global OUT
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--usr',type=Path,required=True);ap.add_argument('--bundle',type=Path,required=True)
    ap.add_argument('--with-bootstrap',action='store_true',help='Link and verify the actual Linux/platform bootstrap for staging')
    ap.add_argument('--spatial-settings-only',action='store_true',help='Build a separate demo with editable and savable spatial settings, without image processing')
    ap.add_argument('--capture-look-proof',type=Path,help='Bind the two QEMU-verified fixed CAP looks')
    ap.add_argument('--capture-controls',action='store_true',help='Stronger CAP default and five capture controls; preserves legacy preferences')
    ap.add_argument('--save-dialog',action='store_true',help='Native Confirm/Cancel before saving, then completion feedback')
    ap.add_argument('--preview-refresh',action='store_true',help='Experimental same-value native style replay after color edits and Save')
    ap.add_argument('--preview-cycle',action='store_true',help='Experimental timed native style transition/restoration instead of r8 same-value replay')
    ap.add_argument('--dual-look',action='store_true',help='Add the FL2 reference approximation alongside the existing FL recipe')
    ap.add_argument('--look-banks',action='store_true',help='Separate FL/FL2 settings and dedicated FL2 label (schema 2)')
    ap.add_argument("--leica-look",action="store_true",help="Add independent FL3 warm film preset (schema 3)")
    ap.add_argument('--film-curves',action='store_true',help='Build the FL3 five-point curve candidate for offline validation')
    args=ap.parse_args()
    if args.leica_look and not args.look_banks:ap.error("--leica-look requires --look-banks")
    if args.look_banks and not args.dual_look:ap.error('--look-banks requires --dual-look')
    if args.dual_look and not args.preview_cycle:ap.error('--dual-look requires the r9 --preview-cycle pipeline')
    if args.preview_cycle:args.preview_refresh=True
    if args.spatial_settings_only:OUT=OUT.with_name('native-module-spatial-settings-only')
    if args.capture_look_proof:
        if not args.spatial_settings_only or not args.with_bootstrap:
            ap.error('CAP module preserves the installed spatial settings and requires the native bootstrap')
        OUT=OUT.with_name('native-module-capture-look')
    if args.capture_controls:
        if not args.capture_look_proof:ap.error('--capture-controls requires --capture-look-proof')
        OUT=OUT.with_name('native-module-capture-controls')
    if args.save_dialog:
        if not args.capture_controls:ap.error('--save-dialog requires the accepted capture-controls build')
        OUT=OUT.with_name('native-module-save-dialog')
    if args.preview_refresh:
        if not args.save_dialog:ap.error('--preview-refresh requires the accepted save-dialog build')
        OUT=OUT.with_name('native-module-preview-cycle' if args.preview_cycle else 'native-module-preview-refresh')
    if args.dual_look:OUT=OUT.with_name('native-module-fl2-reference')
    if args.look_banks:OUT=OUT.with_name('native-module-fl2-banks')
    if args.leica_look:OUT=OUT.with_name('native-module-fl3-leica')
    if args.film_curves:
        if not (args.leica_look and args.with_bootstrap and args.save_dialog):
            ap.error('--film-curves requires the complete FL3 build')
        OUT=OUT.with_name('native-module-fl3-curves')
    OUT.mkdir(parents=True,exist_ok=True);(OUT/'proof.json').unlink(missing_ok=True)
    locale_proof=json.loads((ROOT/'.lab/native-fl-strings/proof.json').read_text())
    for locale,labels in [('simplifiedchinese',('保存','完成','未完成')),('english',('Save','Complete','Not Complete'))]:
        name=f'string_{locale}.uxc';raw=(ROOT/'.lab/native-fl-strings'/name).read_bytes()
        if sha(raw)!=locale_proof['files'][name]['after_sha256']:raise ValueError('Feedback locale identity differs')
        strings=Strings(raw)
        if args.dual_look and strings.text(0x4eceb)!='Cinema':raise ValueError('Cinema stock resource differs')
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
    capture_look=None;dependency_proofs={}
    if args.look_banks:
        for name in ('native-fl2-strings/proof.json','native-resource-fl2/report.json'):
            path=ROOT/'.lab'/name;resource=json.loads(path.read_text())
            for resource_source,digest in resource['source_sha256'].items():
                if sha((ROOT/resource_source).read_bytes())!=digest:raise ValueError('Stale FL2 resource evidence')
            dependency_proofs[name]=sha(path.read_bytes())
        labels=json.loads((ROOT/'.lab/native-fl2-strings/proof.json').read_text())
        for name,entry in labels['files'].items():
            raw=(ROOT/'.lab/native-fl2-strings'/name).read_bytes()
            if sha(raw)!=entry['after_sha256'] or Strings(raw).text(0x4fda8)!='FL2':raise ValueError('Wrong FL2 text')
        resource=json.loads((ROOT/'.lab/native-resource-fl2/report.json').read_text())
        if resource['input_proof_sha256']!=dependency_proofs['native-fl2-strings/proof.json']:raise ValueError('Resource parser evidence mismatch')
    if args.leica_look:
        for name in ('native-fl3-strings/proof.json','native-resource-fl3/report.json'):
            path=ROOT/'.lab'/name;resource=json.loads(path.read_text())
            for key,digest in resource['source_sha256'].items():
                if sha((ROOT/key).read_bytes())!=digest:raise ValueError('Stale FL3 resource evidence')
            dependency_proofs[name]=sha(path.read_bytes())
        if resource['input_proof_sha256']!=dependency_proofs['native-fl3-strings/proof.json']:raise ValueError('FL3 resource evidence mismatch')
    if args.film_curves:
        locale_key='native-fl-curve-strings/proof.json'
        resource_key='native-resource-fl3-curves/report.json'
        for key in (locale_key,resource_key):
            path=ROOT/'.lab'/key
            data=json.loads(path.read_text())
            for source_path,digest in data['source_sha256'].items():
                if sha((ROOT/source_path).read_bytes())!=digest:raise ValueError('Stale curve resource proof: '+source_path)
            dependency_proofs[key]=sha(path.read_bytes())
        if data['input_proof_sha256']!=dependency_proofs[locale_key]:raise ValueError('Curve resource evidence mismatch')
        locale=json.loads((ROOT/'.lab'/locale_key).read_text())
        for name,entry in locale['files'].items():
            if sha((ROOT/'.lab/native-fl-curve-strings'/name).read_bytes())!=entry['after_sha256']:
                raise ValueError('Curve locale artifact identity differs')
    if args.preview_refresh:
        script='research/native_preview_cycle_test.py' if args.preview_cycle else 'research/native_preview_test.py'
        run([sys.executable,str(ROOT/script),'--usr',str(args.usr)])
        key='native-preview-cycle/proof.json' if args.preview_cycle else 'native-preview-request/proof.json'
        pp=ROOT/'.lab'/key
        dependency_proofs[key]=sha(pp.read_bytes())
    if args.save_dialog:
        run([sys.executable,str(ROOT/'research/native_save_dialog.py'),'--usr',str(args.usr)])
        dp=ROOT/'.lab/native-save-dialog/proof.json'
        dependency_proofs['native-save-dialog/proof.json']=sha(dp.read_bytes())
    if args.capture_look_proof:
        path=args.capture_look_proof.resolve()
        key=str(path.relative_to(ROOT/'.lab'))
        raw=path.read_bytes();capture=json.loads(raw);digest=sha(raw)
        if not capture.get('private_backup') or not any(x.startswith('NATIVE_3DLUT_CAPTURE_LOOK_PASSED:')
                for x in capture.get('log',[])) or not capture.get('source_sha256'):
            raise ValueError('Original CAP route and packed-table verification required')
        for source_path,source_digest in capture['source_sha256'].items():
            if sha((ROOT/source_path).read_bytes())!=source_digest:raise ValueError('Stale CAP proof: '+source_path)
        tables=capture.get('capture_candidates',[])
        if [t['property'] for t in tables]!=['0x30005','0x30006']:
            raise ValueError('Both CAP candidates are required')
        for i,t in enumerate(tables,1):
            if t['file']!=f'offline-capture-table{i}.bin' or t['tested_levels']!=list(range(1,9)):
                raise ValueError('Wrong CAP test artifact identity')
            table=(path.parent/t['file']).read_bytes()
            if (len(table)!=1280 or table[1215:]!=originals[i][1215:] or
                sha(table)!=t['candidate_sha256'] or sha(originals[i])!=t['original_sha256']):
                raise ValueError('CAP table proof and machine originals differ')
            header+=array(f'a7_pkg_capture{i}',table)
        capture_look=dict(fixed_capture_tables=True,property_ids=[0x30005,0x30006],tables=tables,
                          source_qemu_proof_sha256=digest)
        dependency_proofs[key]=digest
    if args.capture_controls:
        run([sys.executable,str(ROOT/'research/native_capture_controls_test.py'),'--route',str(args.capture_look_proof.resolve().parent),*(['--dual-look'] if args.dual_look else []),*(['--leica-look'] if args.leica_look else [])])
        cp=ROOT/'.lab/native-capture-controls-test/proof.json'
        capture_look.update(fixed_capture_tables=False,dynamic_capture_controls=True,control_count=5,
                            base_delta_scale=[3,2],max_packed_delta=[24,32,32],controls_proof_sha256=sha(cp.read_bytes()))
        dependency_proofs[str(cp.relative_to(ROOT/'.lab'))]=sha(cp.read_bytes())
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
    if capture_look:sources+=['payloads/a7-fl-capture.c']
    if args.capture_controls:sources+=['payloads/a7-fl-capture-controls.c']
    if args.film_curves:sources+=['payloads/a7-fl-fivepoint.c','payloads/a7-fl-worklog.c']
    if args.with_bootstrap:
        run([sys.executable,str(ROOT/'research/native_bootstrap.py'),'--usr',str(args.usr)])
        run([sys.executable,str(ROOT/'research/native_bootstrap_test.py')])
        # Older standalone node reports use paths relative to research/. Publish
        # a checked repo-relative copy for downstream bundle proof readers.
        if args.dual_look:
            for fixture in ('native_adjust_fixture.py','native_menu_action_tree.py'):
                run([sys.executable,str(ROOT/'research'/fixture),'--usr',str(args.usr)])
        adjust_dir='native-adjust'
        if args.film_curves:
            adjust_dir='native-adjust-film'
            run([sys.executable,str(ROOT/'research/native_adjust_fixture.py'),'--usr',str(args.usr),'--film-curve-menu'])
            run([sys.executable,str(ROOT/'research/film_worklog_test.py')])
            path=ROOT/'.lab/film-worklog/proof.json'
            worklog=json.loads(path.read_text())
            for source_path,digest in worklog['source_sha256'].items():
                if sha((ROOT/source_path).read_bytes())!=digest:raise ValueError('Stale curve journal proof: '+source_path)
            dependency_proofs['film-worklog/proof.json']=sha(path.read_bytes())
        adjust_path=ROOT/'.lab'/adjust_dir/'report.json';adjust=json.loads(adjust_path.read_text())
        for source_path,digest in adjust['source_sha256'].items():
            if sha((ROOT/'research'/source_path).read_bytes())!=digest:raise ValueError('Stale node fixture: '+source_path)
        adjust['input_report_sha256']=sha(adjust_path.read_bytes())
        adjust['source_sha256']={'research/'+p:d for p,d in adjust['source_sha256'].items()}
        (adjust_path.parent/'integration-proof.json').write_text(json.dumps(adjust,indent=2)+'\n')
        for name in ('native-bootstrap/compile-proof.json','native-bootstrap-test/proof.json','native-menu-boot-loader/proof.json','native-setting-loader/proof.json',f'{adjust_dir}/integration-proof.json','native-menu-action-tree/proof.json'):
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
    if args.dual_look:flags+=['-DA7_FL_DUAL_LOOK']
    if args.look_banks:flags+=['-DA7_FL_LOOK_BANKS']
    if args.leica_look:flags+=['-DA7_FL_LEICA_LOOK']
    if args.film_curves:flags+=['-DA7_FL_FILM_CONTROLS','-Wno-missing-field-initializers']
    if args.spatial_settings_only:flags+=['-DA7_FL_SPATIAL_SETTINGS_ONLY']
    if capture_look:flags+=['-DA7_FL_CAPTURE_LOOK']
    if args.capture_controls:flags+=['-DA7_FL_CAPTURE_CONTROLS']
    if args.save_dialog:flags+=['-DA7_FL_SAVE_DIALOG','-I',str(ROOT/'.lab/native-save-dialog')]
    if args.preview_refresh:flags+=['-DA7_FL_PREVIEW_REFRESH','-I',str(ROOT/('.lab/native-preview-cycle' if args.preview_cycle else '.lab/native-preview-request'))]
    run(['arm-none-eabi-gcc',*flags,'-nostdlib','-T','guest.ld','start.S','runtime.S','nodes.S',
         str(ROOT/'research/native_module_harness.c'),*[str(ROOT/p) for p in sources],'-lgcc','-o','module-test.elf'],cwd=OUT)
    # The module integration fixture models opening/answering the dialog;
    # native dialog lifecycle instructions are exercised by its own fixture.
    if args.save_dialog:sources+=['payloads/a7-fl-dialog.c']
    if args.preview_refresh:sources+=['payloads/a7-fl-preview-cycle.c' if args.preview_cycle else 'payloads/a7-fl-preview.c']
    objects=[]
    for i,path in enumerate(sources):
        name=f'part-{i}.o';objects.append(name)
        run(['arm-none-eabi-gcc',*flags,'-fPIC','-c',str(ROOT/path),'-o',name],cwd=OUT)
    run(['arm-none-eabi-gcc',*flags,'-nostdlib','-shared','-Wl,--no-undefined,-Bsymbolic-functions,-z,noexecstack',*objects,'-lgcc','-o','liba7-fl-module.so'],cwd=OUT)
    result=run(['qemu-system-arm','-M','virt','-cpu','cortex-a15','-m','1024','-smp','1','-nodefaults','-audio','none','-nic','none','-display','none','-monitor','none','-serial','stdio','-semihosting-config','enable=on,target=native','-device',f'loader,file={OUT}/module-test.elf,cpu-num=0'],capture_output=True,timeout=30)
    log=result.stdout+result.stderr;(OUT/'qemu.log').write_bytes(log);print(log.decode(),end='')
    if (b'NATIVE_FL_CURVE_MAIN_PASSED' if args.film_curves else b'NATIVE_FL_MODULE_PASSED') not in log or b'FAIL ' in log:raise ValueError('Integration fixture failed')
    run(['arm-none-eabi-gcc',*flags,'-DA7_FL_TEST_SAVED_BOOT',*(['-DA7_FL_TEST_LEICA_BOOT'] if args.film_curves else []),'-nostdlib','-T','guest.ld','start.S','runtime.S','nodes.S',
         str(ROOT/'research/native_module_harness.c'),*[str(ROOT/p) for p in sources if p not in ('payloads/a7-fl-dialog.c','payloads/a7-fl-preview.c','payloads/a7-fl-preview-cycle.c')],'-lgcc','-o','module-boot-test.elf'],cwd=OUT)
    boot_run=run(['qemu-system-arm','-M','virt','-cpu','cortex-a15','-m','1024','-smp','1','-nodefaults','-audio','none','-nic','none','-display','none','-monitor','none','-serial','stdio','-semihosting-config','enable=on,target=native','-device',f'loader,file={OUT}/module-boot-test.elf,cpu-num=0'],capture_output=True,timeout=30)
    boot_log=boot_run.stdout+boot_run.stderr;(OUT/'boot.log').write_bytes(boot_log);print(boot_log.decode(),end='')
    if (b'NATIVE_FL_CURVE_BOOT_PASSED' if args.film_curves else b'NATIVE_FL_MODULE_BOOT_PASSED') not in boot_log or b'FAIL ' in boot_log:raise ValueError('Cold boot integration fixture failed')
    if capture_look and not args.film_curves and (b'NATIVE_FL_CAPTURE_MODULE_PASSED' not in log or
                         b'NATIVE_FL_CAPTURE_BOOT_PASSED' not in boot_log):
        raise ValueError('CAP transaction integration fixture failed')
    if args.preview_refresh and not args.film_curves and b'NATIVE_FL_PREVIEW_INTEGRATION_PASSED' not in log:
        raise ValueError('Preview request integration fixture failed')
    source_files=sources+['payloads/a7-fl-module.h','payloads/a7-fl-runtime.h','payloads/a7-fl-runtime-prefs.h',
        'payloads/a7-fl-runtime-control.h','payloads/a7-fl-runtime-recovery.h','payloads/a7-fl-color.h','payloads/a7-fl-store.h',
        'research/native_adjust.h','research/native_menu.h','research/native_module.py','research/native_module_harness.c',
        'research/native_fl_runtime_harness.c','research/native_fl_runtime.py','research/native_adjust_fixture.py','research/native_adjust_harness.c','research/elf32.py','research/uxc_strings.py']
    if args.dual_look and not args.film_curves:
        if b'NATIVE_FL_DUAL_LOOK_PASSED' not in log:raise ValueError('Dual-look route did not pass')
        run(['arm-none-eabi-gcc',*flags,'-DA7_FL_TEST_SAVED_BOOT','-DA7_FL_TEST_CINEMA_BOOT','-nostdlib','-T','guest.ld','start.S','runtime.S','nodes.S',
             str(ROOT/'research/native_module_harness.c'),*[str(ROOT/p) for p in sources if p not in ('payloads/a7-fl-dialog.c','payloads/a7-fl-preview-cycle.c')],'-lgcc','-o','module-cinema-boot-test.elf'],cwd=OUT)
        cinema_run=run(['qemu-system-arm','-M','virt','-cpu','cortex-a15','-m','1024','-smp','1','-nodefaults','-audio','none','-nic','none','-display','none','-monitor','none','-serial','stdio','-semihosting-config','enable=on,target=native','-device',f'loader,file={OUT}/module-cinema-boot-test.elf,cpu-num=0'],capture_output=True,timeout=30)
        cinema_log=cinema_run.stdout+cinema_run.stderr;(OUT/'cinema-boot.log').write_bytes(cinema_log);print(cinema_log.decode(),end='')
        if b'NATIVE_FL_MODULE_BOOT_PASSED' not in cinema_log or b'FAIL ' in cinema_log:raise ValueError('Cinema cold boot integration failed')
        if args.look_banks:
            if b'NATIVE_FL_LOOK_BANKS_PASSED' not in log:raise ValueError('Independent bank integration failed')
            run(['arm-none-eabi-gcc',*flags,'-DA7_FL_TEST_SAVED_BOOT','-DA7_FL_TEST_CINEMA_BOOT','-DA7_FL_TEST_BANK_BOOT','-nostdlib','-T','guest.ld','start.S','runtime.S','nodes.S',str(ROOT/'research/native_module_harness.c'),*[str(ROOT/p) for p in sources if p not in ('payloads/a7-fl-dialog.c','payloads/a7-fl-preview-cycle.c')],'-lgcc','-o','module-bank-boot-test.elf'],cwd=OUT)
            bank_run=run(['qemu-system-arm','-M','virt','-cpu','cortex-a15','-m','1024','-smp','1','-nodefaults','-audio','none','-nic','none','-display','none','-monitor','none','-serial','stdio','-semihosting-config','enable=on,target=native','-device',f'loader,file={OUT}/module-bank-boot-test.elf,cpu-num=0'],capture_output=True,timeout=30)
            bank_log=bank_run.stdout+bank_run.stderr;(OUT/'bank-boot.log').write_bytes(bank_log);print(bank_log.decode(),end='')
            if b'NATIVE_FL_MODULE_BOOT_PASSED' not in bank_log or b'FAIL ' in bank_log:raise ValueError('Saved bank cold boot failed')
            if args.leica_look:
                run(['arm-none-eabi-gcc',*flags,'-DA7_FL_TEST_SAVED_BOOT','-DA7_FL_TEST_CINEMA_BOOT','-DA7_FL_TEST_BANK_BOOT','-DA7_FL_TEST_LEICA_BOOT','-nostdlib','-T','guest.ld','start.S','runtime.S','nodes.S',str(ROOT/'research/native_module_harness.c'),*[str(ROOT/p) for p in sources if p not in ('payloads/a7-fl-dialog.c','payloads/a7-fl-preview-cycle.c')],'-lgcc','-o','module-leica-boot-test.elf'],cwd=OUT)
                result=run(['qemu-system-arm','-M','virt','-cpu','cortex-a15','-m','1024','-smp','1','-nodefaults','-audio','none','-nic','none','-display','none','-monitor','none','-serial','stdio','-semihosting-config','enable=on,target=native','-device',f'loader,file={OUT}/module-leica-boot-test.elf,cpu-num=0'],capture_output=True,timeout=30)
                leica_log=result.stdout+result.stderr;(OUT/'leica-boot.log').write_bytes(leica_log);print(leica_log.decode(),end='')
                if b'NATIVE_FL_MODULE_BOOT_PASSED' not in leica_log or b'FAIL ' in leica_log:raise ValueError('FL3 saved cold boot failed')
    if args.dual_look:source_files+=['payloads/a7-fl-cinema.h','payloads/a7-fl-fl2-model.inc','recipes/fl2-reference-srgb.json']
    if args.leica_look:
        if not args.film_curves and b'NATIVE_FL3_LEICA_PASSED' not in log:raise ValueError('Third look integration failed')
        source_files+=['payloads/a7-fl-leica.h','payloads/a7-fl-leica-model.inc','recipes/leica-film-inspired.json','research/leica_film_recipe.py']
    if args.with_bootstrap:source_files+=['payloads/a7-fl-bootstrap.h','payloads/a7-fl-posix.h','research/native_bootstrap.py','research/native_bootstrap_test.py','research/native_bootstrap_test_harness.c']
    if capture_look:source_files+=['payloads/a7-fl-capture.h']
    if args.capture_controls:source_files+=['payloads/a7-fl-capture-controls.h']
    if args.save_dialog:source_files+=['payloads/a7-fl-dialog.h']
    if args.preview_refresh:source_files+=['payloads/a7-fl-preview.h']
    if args.preview_cycle:source_files+=['payloads/a7-fl-preview-cycle.h']
    proof={'scope':'Original Sony generic nodes, process-manager dispatch and backup writer with modeled platform/OSAL/kernel/filesystem; resident FL integration',
           'original_caution_sha256':CAUTION_SHA,'original_view_sha256':VIEW_SHA,'original_ranges':ranges,
           'source_sha256':{p:sha((ROOT/p).read_bytes()) for p in source_files},
           'artifact_sha256':{p:sha((OUT/p).read_bytes()) for p in ('module-test.elf','module-boot-test.elf','liba7-fl-module.so','qemu.log','boot.log','a7-fl-module-data.h')},
           'module_sha256':sha((OUT/'liba7-fl-module.so').read_bytes()),'placeholder':not args.with_bootstrap,
           'ready_for_staging':args.with_bootstrap and not args.film_curves,'dependency_proof_sha256':dependency_proofs,
           'platform_bootstrap_guard_fixture_verified':args.with_bootstrap,
           'live_platform_bootstrap_verified':False,'camera_integration':False,'flash_ready':False,
           'spatial_settings_only':args.spatial_settings_only,
           'save_confirmation_dialog':args.save_dialog,
           'preview_refresh_request':args.preview_refresh,
           'preview_timed_cycle':args.preview_cycle,
           'dual_look':args.dual_look,
           'leica_look':args.leica_look,
           'preference_schema':4 if args.film_curves else 3 if args.leica_look else 2 if args.look_banks else 1,
           'independent_look_banks':args.look_banks,
           'fl2_resource':0x0204fda8 if args.look_banks else None,
           'preview_refresh_hardware_verified':False,
           'feature_scope':('Still-photo Creative Look menu with native Page hierarchy and nonnegative selection enums; FL-inspired LUT with five signed backend controls and explicit Save; '+
                            ('three editable spatial settings persisted as preferences only; no spatial image effect' if args.spatial_settings_only else 'last three spatial controls disabled')),
           'hardware_validation_required':['Actual still-view boot Backup API readiness','Physical menu navigation and Save action','Cold-power persistence and calibration readback']}
    if args.film_curves:
        # Release evidence is regenerated by its owning tests, never promoted
        # by editing a report. Physical camera acceptance remains separate.
        run([sys.executable,str(ROOT/'research/film_controls_test.py')])
        run([sys.executable,str(ROOT/'research/native_capture_controls_test.py'),
             '--route',str(args.capture_look_proof.resolve().parent),
             '--dual-look','--leica-look','--film-curves'])
        for key in ('film-controls/proof.json','native-fivepoint-capture-test/proof.json'):
            path=ROOT/'.lab'/key
            check=json.loads(path.read_text())
            for name,digest in check['source_sha256'].items():
                if sha((ROOT/name).read_bytes())!=digest:raise ValueError('Stale curve validation: '+name)
            dependency_proofs[key]=sha(path.read_bytes())
        if b'NATIVE_FL_ALL_CURVE_BANKS_PASSED' not in log or b'NATIVE_FL_ALL_CURVE_BOOT_PASSED' not in boot_log:
            raise ValueError('All-look curve integration and cold boot evidence required')
        proof['all_look_curves']=True
        proof['curve_release_verified']=True
        proof['ready_for_staging']=True
        for p in ('payloads/a7-fl-fivepoint.h','payloads/a7-fl-fivepoint-preview.h','payloads/a7-fl-worklog.h'):
            proof['source_sha256'][p]=sha((ROOT/p).read_bytes())
        proof['feature_scope']='Independent FL/FL2/FL3 five-point curves through resident menu, preview and CAP tables; no grain or halation'
    if args.dual_look and not args.film_curves:
        for p in ('module-cinema-boot-test.elf','cinema-boot.log'):proof['artifact_sha256'][p]=sha((OUT/p).read_bytes())
    if args.look_banks and not args.film_curves:
        for p in ('module-bank-boot-test.elf','bank-boot.log'):proof['artifact_sha256'][p]=sha((OUT/p).read_bytes())
    if args.leica_look and not args.film_curves:
        for p in ('module-leica-boot-test.elf','leica-boot.log'):proof['artifact_sha256'][p]=sha((OUT/p).read_bytes())
    if capture_look:
        proof['capture_look']=dict(capture_look,arm_transaction_verified=True)
        proof['hardware_validation_required']+=['sRGB and Adobe RGB JPEG A/B; AV-CAM application']
    (OUT/'proof.json').write_text(json.dumps(proof,indent=2)+'\n')

if __name__=='__main__':main()
