#!/usr/bin/env python3
"""Run stock activation payload core in isolated Linux ARM QEMU, no camera I/O."""
import argparse,json,os,shutil,subprocess,tempfile
from pathlib import Path
from stock_activate_build import ROOT,FLAGS
from stock_first_install import read_files
from local import file_sha
from menu_ram import LIBS


def test(directory,firmware_lab,stock,installed):
    m=json.loads((directory/'manifest.json').read_text())
    for n,digest in m['source_sha256'].items():
        if file_sha(ROOT/n)!=digest:raise ValueError('Stale activation source: '+n)
    for profile in m['profiles']:
        folder=directory/profile['name']
        flags=[*FLAGS,'-I',str(folder)]
        subprocess.run(['arm-none-eabi-gcc',*flags,'-c',str(ROOT/'research/stock_activate_harness.c'),'-o',str(folder/'harness.o')],check=True)
        subprocess.run(['arm-none-eabi-ld','-shared','-Bsymbolic','--no-undefined','-z','noexecstack',str(folder/'harness.o'),str(folder/'linux.o'),str(folder/'data.o'),'-o',str(folder/'test.so')],check=True)
        with tempfile.TemporaryDirectory(dir=folder) as td:
            fs=Path(td)/'root'
            for p in ['bin','lib','sony/bin','sony/lib','sony/proc','sony/dev','sony/tmp','sony/setting','sony/usr/lib','sony/usr/share/app']:(fs/p).mkdir(parents=True,exist_ok=True)
            busy=firmware_lab/'guest/root/bin/busybox'
            sony=firmware_lab/'sony-4.04/firmware.tar_unpacked/0700_part_image/dev/nflasha7_unpacked'
            shutil.copyfile(busy,fs/'bin/busybox');(fs/'bin/busybox').chmod(0o755)
            shutil.copyfile(busy.parent.parent/'lib/ld-musl-armhf.so.1',fs/'lib/ld-musl-armhf.so.1')
            (fs/'lib/ld-musl-armhf.so.1').chmod(0o755)
            (fs/'lib/libc.musl-armv7.so.1').symlink_to('ld-musl-armhf.so.1')
            shutil.copyfile(sony/'bin/busybox',fs/'sony/bin/busybox');(fs/'sony/bin/busybox').chmod(0o755)
            for name,source in LIBS.items():
                shutil.copyfile(sony/'lib'/source,fs/'sony/lib'/name)
                (fs/'sony/lib'/name).chmod(0o755)
            shutil.copyfile(folder/'test.so',fs/'sony/tmp/test.so')
            path=profile['path'].removeprefix('/usr')
            raw=read_files(stock,[path])[path]
            (fs/'sony'/profile['path'].lstrip('/')).write_bytes(raw)
            wanted=[p.removeprefix('/usr') for p in profile['required']]
            for p,data in read_files(installed,wanted).items():(fs/'sony/usr'/p.lstrip('/')).write_bytes(data)
            (fs/'init').write_text('''#!/bin/busybox sh
set -e
b=/bin/busybox
$b mount -t proc proc /sony/proc
$b chroot /sony /bin/busybox sh -c 'LD_PRELOAD=/tmp/test.so /bin/busybox true'
echo STOCK_LINUX_ARM_DONE
$b poweroff -f
''');(fs/'init').chmod(0o755)
            initrd=Path(td)/'initrd.cpio'
            with initrd.open('wb') as stream:
                subprocess.run(['bsdtar','-c','--format=newc','-f','-','.'],cwd=fs,stdout=stream,env={**os.environ,'COPYFILE_DISABLE':'1'},check=True)
            result=subprocess.run(['qemu-system-arm','-M','virt','-cpu','cortex-a15','-m','768','-display','none','-serial','stdio','-monitor','none','-nic','none','-no-reboot','-kernel',str(firmware_lab/'guest/vmlinuz-lts'),'-initrd',str(initrd),'-append','console=ttyAMA0 rdinit=/init quiet panic=1'],capture_output=True,timeout=180)
            log=result.stdout+result.stderr;(folder/'qemu.log').write_bytes(log)
            print(profile['name'],log.decode(errors='replace'),flush=True)
            if b'STOCK_ACT_ALL_PASS' not in log or b'STOCK_LINUX_ARM_DONE' not in log or b'STOCK_ACT_FAIL' in log:raise ValueError('Activation test failed')
    proof=dict(passed=True,camera_contacted=False,manifest_sha256=file_sha(directory/'manifest.json'),
               logs={p['name']:file_sha(directory/p['name']/'qemu.log') for p in m['profiles']},
               source_sha256={**m['source_sha256'],**{p:file_sha(ROOT/p) for p in ['research/stock_activate_test.py','research/stock_activate_harness.c']}},
               scope='ARM Linux real page mappings and filesystem writes; mount syscalls modeled. Not Sony hardware acceptance.')
    (directory/'proof.json').write_text(json.dumps(proof,indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('directory','firmware-lab','stock','installed'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();test(a.directory.resolve(),a.firmware_lab.resolve(),a.stock.resolve(),a.installed.resolve())
