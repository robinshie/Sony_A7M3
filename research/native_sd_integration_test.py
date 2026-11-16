from pathlib import Path
import subprocess,json,hashlib
root=Path(__file__).resolve().parents[1]; base=root/'.lab/native-module-six-auto-size';out=root/'.lab/native-module-sd-candidate';out.mkdir(exist_ok=True)
proof=json.loads((base/'proof.json').read_text())
sources=[p for p in proof['source_sha256'] if p.endswith('.c') and (p.startswith('payloads/') or p in ('research/native_menu.c','research/native_adjust.c'))]
sources+=['payloads/a7-fl-sd-recipe.c','payloads/a7-fl-sd-files.c']
features='SIX_LOOKS FILM_CONTROLS CAPTURE_VIGNETTE CAPTURE_HALATION CAPTURE_GRAIN CAPTURE_GRAIN_BACKEND LOOK_BANKS LEICA_LOOK DUAL_LOOK CAPTURE_LOOK CAPTURE_CONTROLS SAVE_DIALOG PREVIEW_REFRESH SD_IMPORT'.split()
flags=['-mcpu=cortex-a9','-marm','-mfloat-abi=soft','-mno-unaligned-access','-Os','-Wall','-Wextra','-Werror','-Wno-missing-field-initializers','-ffreestanding','-fno-builtin','-fno-strict-aliasing','-fPIC',*['-DA7_FL_'+f for f in features],'-DA7_FL_SD_IMPORT_TITLE=0x0204fdb5']
for p in ['payloads','research','.lab/native-module-six-auto-size','.lab/native-bootstrap','.lab/native-save-dialog','.lab/native-preview-cycle']:
 flags+=['-I',str(root/p)]
objects=[]
for i,src in enumerate(sources):
 obj=out/f'part-{i}.o'
 subprocess.run(['arm-none-eabi-gcc',*flags,'-c',str(root/src),'-o',str(obj)],check=True)
 objects.append(str(obj))
objects.append(str(base/'grain-blob.o'))
target=out/'liba7-fl-module.so'
subprocess.run(['arm-none-eabi-gcc',*flags,'-nostdlib','-shared','-Wl,--no-undefined,-Bsymbolic-functions,-z,noexecstack',*objects,'-lgcc','-o',str(target)],check=True)
report=dict(binary_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),bytes=target.stat().st_size,flash_ready=False,normal_mode_verified=False,source_sha256={s:hashlib.sha256((root/s).read_bytes()).hexdigest() for s in sources})
(out/'build-only.json').write_text(json.dumps(report,indent=2)+'\n')
print(target,report['bytes'],report['binary_sha256'])

flags+=['-DA7_FL_SD_TEST']
ss=[s for s in sources if s not in ('payloads/a7-fl-grain-backend.c','payloads/a7-fl-dialog.c','payloads/a7-fl-preview-cycle.c')]
subprocess.run(['arm-none-eabi-gcc',*flags,'-nostdlib','-T',str(base/'guest.ld'),str(base/'start.S'),str(base/'runtime.S'),str(base/'nodes.S'),str(root/'research/native_module_harness.c'),*[str(root/s) for s in ss],'-lgcc','-o',str(out/'module-test.elf')],check=True,cwd=base)
r=subprocess.run(['qemu-system-arm','-M','virt','-cpu','cortex-a15','-m','1024','-nodefaults','-audio','none','-nic','none','-display','none','-monitor','none','-serial','stdio','-semihosting-config','enable=on,target=native','-device',f'loader,file={out}/module-test.elf,cpu-num=0'],capture_output=True,timeout=30)
(out/'qemu.log').write_bytes(r.stdout+r.stderr);print((r.stdout+r.stderr).decode());r.check_returncode()
if b'FAIL' in r.stdout or b'NATIVE_FL_CURVE_MAIN_PASSED' not in r.stdout:raise RuntimeError('Integration failed')

dflags=['-mcpu=cortex-a9','-marm','-mfloat-abi=soft','-Os','-Wall','-Wextra','-Werror','-ffreestanding','-fno-builtin','-fno-unwind-tables','-fno-asynchronous-unwind-tables','-I',str(root/'payloads'),'-I',str(root/'.lab/native-save-dialog'),'-DA7_FL_DIALOG_TEST','-DA7_FL_SD_IMPORT']
d=root/'.lab/native-save-dialog'
subprocess.run(['arm-none-eabi-gcc',*dflags,'-nostdlib','-T',str(d/'test.ld'),str(d/'start.S'),str(d/'native.S'),str(root/'payloads/a7-fl-dialog.c'),str(root/'research/native_save_dialog_harness.c'),'-lgcc','-o',str(out/'dialog-test.elf')],check=True,cwd=d)
r=subprocess.run(['qemu-system-arm','-M','virt','-cpu','cortex-a15','-m','1024','-nodefaults','-audio','none','-nic','none','-display','none','-monitor','none','-serial','stdio','-semihosting-config','enable=on,target=native','-device',f'loader,file={out}/dialog-test.elf,cpu-num=0'],capture_output=True,timeout=30)
(out/'dialog.log').write_bytes(r.stdout+r.stderr);print((r.stdout+r.stderr).decode());r.check_returncode()
if b'FAIL' in r.stdout or b'SD_FILE_DIALOG_PASSED' not in r.stdout:raise RuntimeError('Dialog failed')
bootflags=[f for f in flags if f!='-DA7_FL_SD_TEST']+['-DA7_FL_TEST_SAVED_BOOT','-DA7_FL_TEST_SIX_SAVED_BOOT']
subprocess.run(['arm-none-eabi-gcc',*bootflags,'-nostdlib','-T',str(base/'guest.ld'),str(base/'start.S'),str(base/'runtime.S'),str(base/'nodes.S'),str(root/'research/native_module_harness.c'),*[str(root/s) for s in ss],'-lgcc','-o',str(out/'six-boot-test.elf')],check=True,cwd=base)
r=subprocess.run(['qemu-system-arm','-M','virt','-cpu','cortex-a15','-m','1024','-nodefaults','-audio','none','-nic','none','-display','none','-monitor','none','-serial','stdio','-semihosting-config','enable=on,target=native','-device',f'loader,file={out}/six-boot-test.elf,cpu-num=0'],capture_output=True,timeout=30)
(out/'six-boot.log').write_bytes(r.stdout+r.stderr);print((r.stdout+r.stderr).decode());r.check_returncode()
if b'FAIL' in r.stdout or b'NATIVE_FL_SIX_BOOT_PASSED' not in r.stdout:raise RuntimeError('Saved boot failed')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
tracked=set(sources)|{str(p.relative_to(root)) for p in (root/'payloads').glob('*.h')}|{'research/native_sd_integration_test.py','research/native_module_harness.c','research/native_save_dialog_harness.c','research/native_fl_runtime_harness.c','research/native_adjust.h','research/native_menu.h'}
report.update(module_sha256=sha(target),placeholder=False,ready_for_staging=True,passed=True,normal_mode_verified=False,scope='Candidate trial: ARM native node/dialog and mocked filesystem transaction; hardware menu remains unverified',source_sha256={s:sha(root/s) for s in sorted(tracked)},artifact_sha256={n:sha(out/n) for n in ('liba7-fl-module.so','qemu.log','module-test.elf','dialog-test.elf','dialog.log','six-boot-test.elf','six-boot.log')},fixture_sha256={str(p.relative_to(root)):sha(p) for p in [base/'a7-fl-module-data.h',base/'grain-blob.o',base/'runtime.S',base/'nodes.S',base/'guest.ld',d/'native.S',d/'test.ld',d/'a7-fl-dialog-pins.h']})
(out/'proof.json').write_text(json.dumps(report,indent=2)+'\n')
