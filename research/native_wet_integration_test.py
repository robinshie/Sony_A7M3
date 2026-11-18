from pathlib import Path
import subprocess,json,hashlib,argparse
root=Path(__file__).resolve().parents[1]; base=root/'.lab/native-module-six-auto-size';out=root/'.lab/native-module-wet-candidate';out.mkdir(exist_ok=True)
args=argparse.ArgumentParser();args.add_argument('--kernel',type=Path,required=True);args=args.parse_args()
kernel=args.kernel.resolve();kp=json.loads((kernel/'proof.json').read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
if kp['route']!='wet' or kp['module_name']!='a7capwet' or sha(kernel/'a7capwet.ko')!=kp['module_sha256']:raise ValueError('Wrong wet kernel')
if any(sha(root/n)!=h for n,h in kp['source_sha256'].items()):raise ValueError('Wet kernel sources changed')
(out/'grain.ko').write_bytes((kernel/'a7capwet.ko').read_bytes())
(out/'a7-fl-grain-kernel.h').write_text('#define A7_GRAIN_KERNEL_NAME "a7capwet"\nstatic const unsigned a7_grain_kernel_source_id[]={'+','.join(map(str,kp['source_id']))+'};\n')
(out/'grain-blob.S').write_text('.section .rodata\n.balign 4\n.global a7_grain_kernel_start,a7_grain_kernel_end\na7_grain_kernel_start:\n.incbin "grain.ko"\na7_grain_kernel_end:\n.section .note.GNU-stack,"",%progbits\n')
subprocess.run(['arm-none-eabi-gcc','-mcpu=cortex-a9','-marm','-c','grain-blob.S','-o','grain-blob.o'],cwd=out,check=True)
proof=json.loads((base/'proof.json').read_text())
sources=[p for p in proof['source_sha256'] if p.endswith('.c') and (p.startswith('payloads/') or p in ('research/native_menu.c','research/native_adjust.c'))]
sources+=['payloads/a7-fl-sd-recipe.c','payloads/a7-fl-sd-files.c']+[f'payloads/a7-fl-custom{suffix}.c' for suffix in ('','-store','-effective','-session','-posix','-text')]
features='CAPTURE_WET SIX_LOOKS FILM_CONTROLS CAPTURE_VIGNETTE CAPTURE_HALATION CAPTURE_GRAIN CAPTURE_GRAIN_BACKEND LOOK_BANKS LEICA_LOOK DUAL_LOOK CAPTURE_LOOK CAPTURE_CONTROLS SAVE_DIALOG PREVIEW_REFRESH SD_IMPORT CUSTOM_LOOKS'.split()
flags=['-I'+str(out),'-mcpu=cortex-a9','-marm','-mfloat-abi=soft','-mno-unaligned-access','-Os','-Wall','-Wextra','-Werror','-Wno-missing-field-initializers','-ffreestanding','-fno-builtin','-fno-strict-aliasing','-fPIC',*['-DA7_FL_'+f for f in features],'-DA7_FL_SD_IMPORT_TITLE=0x0204fdb5','-DA7_FL_CUSTOM_TITLE_FIRST=0x0204fdb9']
for p in ['payloads','research','.lab/native-module-six-auto-size','.lab/native-bootstrap','.lab/native-save-dialog','.lab/native-preview-cycle']:
 flags+=['-I',str(root/p)]
objects=[]
for i,src in enumerate(sources):
 obj=out/f'part-{i}.o'
 subprocess.run(['arm-none-eabi-gcc',*flags,'-c',str(root/src),'-o',str(obj)],check=True)
 objects.append(str(obj))
objects.append(str(out/'grain-blob.o'))
target=out/'liba7-fl-module.so'
subprocess.run(['arm-none-eabi-gcc',*flags,'-nostdlib','-shared','-Wl,--no-undefined,-Bsymbolic-functions,-z,noexecstack',*objects,'-lgcc','-o',str(target)],check=True)
report=dict(binary_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),bytes=target.stat().st_size,flash_ready=False,normal_mode_verified=False,source_sha256={s:hashlib.sha256((root/s).read_bytes()).hexdigest() for s in sources})
(out/'build-only.json').write_text(json.dumps(report,indent=2)+'\n')
print(target,report['bytes'],report['binary_sha256'])

flags+=['-DA7_FL_SD_TEST']
ss=[s for s in sources if s not in ('payloads/a7-fl-grain-backend.c','payloads/a7-fl-dialog.c','payloads/a7-fl-preview-cycle.c','payloads/a7-fl-custom-posix.c')]
subprocess.run(['arm-none-eabi-gcc',*flags,'-nostdlib','-T',str(base/'guest.ld'),str(base/'start.S'),str(base/'runtime.S'),str(base/'nodes.S'),str(root/'research/native_module_harness.c'),*[str(root/s) for s in ss],'-lgcc','-o',str(out/'module-test.elf')],check=True,cwd=base)
r=subprocess.run(['qemu-system-arm','-M','virt','-cpu','cortex-a15','-m','1024','-nodefaults','-audio','none','-nic','none','-display','none','-monitor','none','-serial','stdio','-semihosting-config','enable=on,target=native','-device',f'loader,file={out}/module-test.elf,cpu-num=0'],capture_output=True,timeout=30)
(out/'qemu.log').write_bytes(r.stdout+r.stderr);print((r.stdout+r.stderr).decode());r.check_returncode()
if b'FAIL' in r.stdout or b'NATIVE_WET_FLOW_PASSED' not in r.stdout:raise RuntimeError('Integration failed')


boot=out/'module-boot-test.elf'
subprocess.run(['arm-none-eabi-gcc',*flags,'-DA7_FL_TEST_SAVED_BOOT','-DA7_FL_TEST_SIX_SAVED_BOOT','-DA7_FL_TEST_CUSTOM_BOOT','-nostdlib','-T',str(base/'guest.ld'),str(base/'start.S'),str(base/'runtime.S'),str(base/'nodes.S'),str(root/'research/native_module_harness.c'),*[str(root/s) for s in ss],'-lgcc','-o',str(boot)],check=True,cwd=base)
r=subprocess.run(['qemu-system-arm','-M','virt','-cpu','cortex-a15','-m','1024','-nodefaults','-audio','none','-nic','none','-display','none','-monitor','none','-serial','stdio','-semihosting-config','enable=on,target=native','-device',f'loader,file={boot},cpu-num=0'],capture_output=True,timeout=30)
(out/'qemu-boot.log').write_bytes(r.stdout+r.stderr);print((r.stdout+r.stderr).decode());r.check_returncode()
if b'FAIL' in r.stdout or b'NATIVE_WET_BOOT_PASSED' not in r.stdout:raise RuntimeError('Custom cold boot failed')
d=root/'.lab/native-save-dialog'
for name in ('dialog-test.elf','qemu.log'):
 (out/('dialog.log' if name=='qemu.log' else name)).write_bytes((d/name).read_bytes())
if b'SD_FILE_DIALOG_PASSED' not in (out/'dialog.log').read_bytes():raise RuntimeError('Missing native dialog evidence')
subprocess.run(['cc','-Wall','-Wextra','-Werror','-DA7_CUSTOM_POSIX_TEST','-DA7_FL_FILM_CONTROLS',str(root/'research/custom_look_posix_test.c'),str(root/'payloads/a7-fl-custom-posix.c'),'-o',str(out/'posix-test')],check=True)
r=subprocess.run([str(out/'posix-test')],capture_output=True,check=True);(out/'posix.log').write_bytes(r.stdout+r.stderr)
subprocess.run(['cc','-O2','-Wall','-Wextra','-Werror',*['-DA7_FL_'+x for x in features],'-I'+str(root/'payloads'),str(root/'research/custom_look_session_test.c'),*[str(root/f'payloads/a7-fl-custom{x}.c') for x in ('','-store','-effective','-session')],str(root/'payloads/a7-fl-runtime-prefs.c'),str(root/'payloads/a7-fl-runtime.c'),'-o',str(out/'session-test')],check=True)
r=subprocess.run([str(out/'session-test')],capture_output=True,check=True);(out/'session.log').write_bytes(r.stdout+r.stderr)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
tracked=set(sources)|{str(p.relative_to(root)) for p in (root/'payloads').glob('*.h')}|{'research/native_wet_integration_test.py','research/native_wet_harness.h','research/native_custom_harness.h','research/native_module_harness.c','research/native_save_dialog.py','research/native_save_dialog_harness.c','research/custom_look_posix_test.c','research/custom_look_session_test.c','research/native_fl_runtime_harness.c','research/native_adjust.h','research/native_menu.h'}
report.update(module_sha256=sha(target),placeholder=False,kernel_bound=True,kernel_sha256=kp['module_sha256'],kernel_bundle=str(kernel),ready_for_staging=False,passed=True,normal_mode_verified=False,scope='Candidate: native ARM graph/engine integration and cold boot with modeled storage, native dialog lifecycle with modeled widgets; physical menu still requires cold boot trial',source_sha256={s:sha(root/s) for s in sorted(tracked)},artifact_sha256={n:sha(out/n) for n in ('grain.ko','grain-blob.S','grain-blob.o','a7-fl-grain-kernel.h','liba7-fl-module.so','qemu.log','module-test.elf','dialog-test.elf','dialog.log','module-boot-test.elf','qemu-boot.log','posix.log','posix-test','session.log','session-test')},fixture_sha256={str(p.relative_to(root)):sha(p) for p in [base/'a7-fl-module-data.h',base/'runtime.S',base/'nodes.S',base/'guest.ld',d/'native.S',d/'test.ld',d/'a7-fl-dialog-pins.h']},dependency_proof_sha256={'native-resource-wet/report.json':sha(root/'.lab/native-resource-wet/report.json'),'native-fl-wet-strings/proof.json':sha(root/'.lab/native-fl-wet-strings/proof.json'),str((kernel/'proof.json').relative_to(root/'.lab')):sha(kernel/'proof.json')})
(out/'proof.json').write_text(json.dumps(report,indent=2)+'\n')
print('WET_CANDIDATE_BUILT_AWAITING_REAL_JPEG_VERIFICATION')
