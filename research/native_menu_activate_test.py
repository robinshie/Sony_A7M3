#!/usr/bin/env python3
"""Run the exact ARM activation core with real Linux private file mappings."""
import argparse,hashlib,json,os,shutil,subprocess,tempfile
from pathlib import Path
from native_menu_activate_build import ROOT,OUT,FLAGS,build,run,sha
from menu_ram import LIBS
LAB=Path(os.environ.get('A7M3_TEST_FIRMWARE_LAB',str(ROOT/'.lab/firmware-lab')))
def test(setting=False):
 global OUT
 if setting:OUT=ROOT/'.lab/native-setting-activate'
 manifest=build(OUT,setting)
 flags=FLAGS+(['-DNMA_LAYOUT_HEADER="native_setting_layout.h"'] if setting else [])
 run(['arm-none-eabi-gcc',*flags,'-I',str(OUT),'-c',str(ROOT/'research/native_menu_activate_harness.c'),'-o',str(OUT/'harness.o')])
 run(['arm-none-eabi-ld','-shared','--no-undefined','-z','noexecstack',str(OUT/'harness.o'),str(OUT/'linux.o'),str(OUT/'data.o'),'-o',str(OUT/'test.so')])
 with tempfile.TemporaryDirectory(dir=OUT) as td:
  fs=Path(td)/'root'
  for n in ['bin','lib','sony/bin','sony/lib','sony/proc','sony/dev','sony/tmp','sony/setting','sony/usr/lib','sony/usr/share/app']:(fs/n).mkdir(parents=True,exist_ok=True)
  busy=LAB/'guest/root/bin/busybox';sony=LAB/'sony-4.04/firmware.tar_unpacked/0700_part_image/dev/nflasha7_unpacked'
  shutil.copy2(busy,fs/'bin/busybox');shutil.copy2(busy.parent.parent/'lib/ld-musl-armhf.so.1',fs/'lib/ld-musl-armhf.so.1');(fs/'lib/libc.musl-armv7.so.1').symlink_to('ld-musl-armhf.so.1')
  shutil.copy2(sony/'bin/busybox',fs/'sony/bin/busybox');(fs/'sony/bin/busybox').chmod(0o755)
  for n,p in LIBS.items():shutil.copy2(sony/'lib'/p,fs/'sony/lib'/n);(fs/'sony/lib'/n).chmod(0o755)
  shutil.copyfile(OUT/'test.so',fs/'sony/tmp/test.so');shutil.copyfile(ROOT/('.lab/native-menu-boot-loader/viewUnified2.so' if setting else '.lab/creative-icons-belt/viewUnified2.so'),fs/'sony/usr/lib/viewUnified2.so')
  for i,name in enumerate(['lib/a7fl.so','share/app/string_simplifiedchinese.uxc','share/app/string_english.uxc']):shutil.copyfile(ROOT/'.lab/native-install-bound'/f'input{i}.bin',fs/'sony/usr'/name)
  (fs/'init').write_text('''#!/bin/busybox sh
set -e
b=/bin/busybox
$b mount -t proc proc /sony/proc
$b chroot /sony /bin/busybox sh -c 'LD_PRELOAD=/tmp/test.so /bin/busybox true'
echo NMA_LINUX_ARM_DONE
$b poweroff -f
''');(fs/'init').chmod(0o755)
  initrd=Path(td)/'initrd.cpio'
  with initrd.open('wb') as out:run(['bsdtar','-c','--format=newc','-f','-','.'],cwd=fs,stdout=out,env={**os.environ,'COPYFILE_DISABLE':'1'})
  p=subprocess.run(['qemu-system-arm','-M','virt','-cpu','cortex-a15','-m','768','-display','none','-serial','stdio','-monitor','none','-nic','none','-no-reboot','-kernel',str(LAB/'guest/vmlinuz-lts'),'-initrd',str(initrd),'-append','console=ttyAMA0 rdinit=/init quiet panic=1'],capture_output=True,timeout=90)
  (OUT/'qemu.log').write_bytes(p.stdout+p.stderr);print((p.stdout+p.stderr).decode(errors='replace'))
  if b'NMA_ALL_PASS' not in p.stdout or b'NMA_LINUX_ARM_DONE' not in p.stdout:raise ValueError('ARM Linux activation test failed')
 proof={'manifest_sha256':sha(OUT/'manifest.json'),'payloads':manifest['payloads'],'source_sha256':{**manifest['source_sha256'],**{n:sha(ROOT/n) for n in ['research/native_menu_activate_harness.c','research/native_menu_activate_test.py']}},'qemu_log_sha256':sha(OUT/'qemu.log'),'scope':'Real ARM Linux mmap/mprotect/smaps/pagemap and VFS page cache; mount state and injected I/O failures mocked. Actual Sony kernel behavior still requires live preflight/shadow evidence.'}
 (OUT/'proof.json').write_text(json.dumps(proof,indent=2)+'\n')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--setting-menu',action='store_true');a=p.parse_args();test(a.setting_menu)
