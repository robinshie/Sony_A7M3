#!/usr/bin/env python3
from pathlib import Path
import argparse,subprocess,shutil,hashlib,json
root=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description='Regression: previous confirmed LUTs and startup retry, with two failing controls');p.add_argument('--fixture',type=Path,required=True);a=p.parse_args();source=a.fixture.resolve();out=root/'.lab/native-boot-recovery';out.mkdir(exist_ok=True)
for name in ('guest.ld','start.S','runtime.S','nodes.S','a7-fl-module-data.h'):
 shutil.copyfile(source/name,out/name)
for path in source.glob('*.bin'):shutil.copyfile(path,out/path.name)
paths=['payloads/a7-fl-module.c','payloads/a7-fl-runtime.c','payloads/a7-fl-runtime-prefs.c','payloads/a7-fl-runtime-control.c','payloads/a7-fl-runtime-recovery.c','payloads/a7-fl-store.c','research/native_adjust.c','research/native_menu.c','payloads/a7-fl-capture.c','payloads/a7-fl-capture-controls.c','payloads/a7-fl-fivepoint.c','payloads/a7-fl-worklog.c','payloads/a7-fl-bootstrap.c','payloads/a7-fl-posix.c']
flags=['-mcpu=cortex-a9','-marm','-mfloat-abi=soft','-mno-unaligned-access','-Os','-Wall','-Wextra','-Werror','-ffreestanding','-fno-builtin','-fno-strict-aliasing','-fno-unwind-tables','-fno-asynchronous-unwind-tables','-Wno-missing-field-initializers']
for n in ('DUAL_LOOK','LOOK_BANKS','LEICA_LOOK','FILM_CONTROLS','CAPTURE_GRAIN','CAPTURE_HALATION','CAPTURE_VIGNETTE','CAPTURE_GRAIN_BACKEND','SPATIAL_SETTINGS_ONLY','CAPTURE_LOOK','CAPTURE_CONTROLS','SAVE_DIALOG','PREVIEW_REFRESH','TEST_SAVED_BOOT','TEST_LEICA_BOOT','TEST_BOOT_RECOVERY'):flags+=['-DA7_FL_'+n]
for p in ('payloads','research','.lab/native-bootstrap','.lab/native-save-dialog','.lab/native-preview-cycle'):flags+=['-I'+str(root/p)]
flags+=['-I'+str(out)]
module=(root/paths[0]).read_text()
variants={'missing_history':module.replace('a7_fl_curve_recover_history(&film_work,&film_io,&preference,have_previous?&previous:0)','a7_fl_curve_recover(&film_work,&film_io,&preference)'), 'missing_retry':module.replace('    if(!capture_controls.prepared)\n        rc=a7_capture_prepare','    rc=a7_capture_prepare'), 'fixed':module}
logs={}
for name,code in variants.items():
 (out/(name+'.c')).write_text(code)
 subprocess.run(['arm-none-eabi-gcc',*flags,'-nostdlib','-T','guest.ld','start.S','runtime.S','nodes.S',str(root/'research/native_module_harness.c'),name+'.c',*[str(root/n) for n in paths[1:]],'-lgcc','-o',name+'.elf'],cwd=out,check=True)
 run=subprocess.run(['qemu-system-arm','-M','virt','-cpu','cortex-a15','-m','1024','-smp','1','-nodefaults','-audio','none','-nic','none','-display','none','-monitor','none','-serial','stdio','-semihosting-config','enable=on,target=native','-device',f'loader,file={out}/{name}.elf,cpu-num=0'],capture_output=True,timeout=45)
 log=run.stdout+run.stderr;(out/(name+'.log')).write_bytes(log);logs[name]=log.decode();print(name,log.decode(),flush=True)
 if name=='fixed':assert run.returncode==0 and b'NATIVE_FL_CONFIRMED_HISTORY_RETRY_PASSED' in log and b'NATIVE_FL_CURVE_BOOT_PASSED' in log and b'FAIL' not in log
 else:
  expected=b'recover older saved tables before transient backend startup failure' if name=='missing_history' else b'runtime boot recovers last Save from partial serialization'
  assert b'FAIL' in log and expected in log
files=paths+['research/native_boot_recovery_test.py','research/native_module_harness.c','payloads/a7-fl-store.h','payloads/a7-fl-worklog.h']
(out/'proof.json').write_text(json.dumps(dict(passed=True,camera_run=False,firmware_written=False,logs=logs,source_sha256={n:hashlib.sha256((root/n).read_bytes()).hexdigest() for n in files}),indent=2)+'\n')
