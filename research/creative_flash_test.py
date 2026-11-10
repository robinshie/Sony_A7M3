#!/usr/bin/env python3
"""Compile and exercise the exact multi-sector write/read/restore payloads."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from menu_ram import LIBS
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'.lab/creative-flash'
def run(cmd,**kw):return subprocess.run(cmd,check=True,**kw)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def build():
    (OUT/'qemu-proof.json').unlink(missing_ok=True)
    manifest=json.loads((OUT/'manifest.json').read_text())
    for name,digest in manifest['blobs'].items():
        if sha(OUT/name)!=digest:raise ValueError('Changed patch data')
    def array(name,data):return f'static const uint8_t {name}[]={{'+','.join(map(str,data))+'};\n'
    count=len(manifest['sectors'])
    header=f'#define COUNT {count}\nstatic const unsigned offsets[]={{'+','.join(map(str,manifest['sectors']))+'};\n'
    header+=array('expected_header',(OUT/'header.bin').read_bytes())
    for name in ('before','after'):
        data=(OUT/f'{name}.bin').read_bytes()
        header+=f'static const uint8_t {name}[COUNT][512]={{'+','.join('{'+','.join(map(str,data[i*512:(i+1)*512]))+'}' for i in range(count))+'};\n'
    (OUT/'creative-sectors.h').write_text(header)
    flags=['-mcpu=cortex-a9','-marm','-mfloat-abi=soft','-Os','-fPIC','-ffreestanding','-fno-builtin',
           '-fno-stack-protector','-fno-unwind-tables','-fno-asynchronous-unwind-tables','-I',str(OUT)]
    for name,action,fail in [('read',0,0),('write',1,0),('restore',2,0),('injected-failure',1,1)]:
        run(['arm-none-eabi-gcc',*flags,f'-DACTION={action}',f'-DTEST_FAIL_AFTER={fail}','-c',
             str(ROOT/'payloads/a7-creative-sectors.c'),'-o',f'{name}.o'],cwd=OUT)
        run(['arm-none-eabi-ld','-shared','--no-undefined','-z','noexecstack',f'{name}.o','-o',f'{name}.so'],cwd=OUT)
    return manifest

def test(manifest,kernel,busybox,sony_root):
    with tempfile.TemporaryDirectory(dir=OUT) as temporary:
        fs=Path(temporary)/'root'
        for name in ['bin','lib','sony/bin','sony/lib','sony/dev','sony/tmp/jiritsu','payloads']:
            (fs/name).mkdir(parents=True,exist_ok=True)
        shutil.copy2(busybox,fs/'bin/busybox');(fs/'bin/busybox').chmod(0o755)
        musl=busybox.parent.parent/'lib/ld-musl-armhf.so.1'
        if musl.exists():
            shutil.copy2(musl,fs/'lib/ld-musl-armhf.so.1');(fs/'lib/libc.musl-armv7.so.1').symlink_to('ld-musl-armhf.so.1')
        shutil.copy2(sony_root/'bin/busybox',fs/'sony/bin/busybox');(fs/'sony/bin/busybox').chmod(0o755)
        for name,source in LIBS.items():
            shutil.copy2(sony_root/'lib'/source,fs/'sony/lib'/name);(fs/'sony/lib'/name).chmod(0o755)
        for name in ('read','write','restore','injected-failure'):
            shutil.copyfile(OUT/f'{name}.so',fs/f'sony/tmp/{name}.so')
        for name in ('header','before','after'):shutil.copyfile(OUT/f'{name}.bin',fs/f'{name}.bin')
        sectors=' '.join(str(o//512) for o in manifest['sectors'])
        (fs/'init').write_text('''#!/bin/busybox sh
set -eu
b=/bin/busybox
d=/sony/dev/nflasha15
r=/sony/tmp/jiritsu/a7creative.bin
$b truncate -s 314572800 "$d"
$b dd if=/header.bin of="$d" bs=512 count=4 conv=notrunc status=none
i=0
for off in SECTORS; do
  $b dd if=/before.bin of="$d" bs=512 skip=$i seek=$off count=1 conv=notrunc status=none
  i=$((i+1))
done
printf 'untouched canary' | $b dd of="$d" bs=1 seek=8192 conv=notrunc status=none
invoke() {
  $b rm -f "$r"
  $b chroot /sony /bin/busybox sh -c "LD_PRELOAD=/tmp/$1.so /bin/busybox true"
}
field() { $b od -An -td4 -j "$1" -N4 "$r" | $b tr -d ' \\n'; }
match() { $b dd if="$r" bs=1 skip=40 status=none > /current; $b cmp /current "/$1.bin"; }
invoke read
test "$(field 8)" = 1; test "$(field 24)" = 1; match before
echo QEMU_CREATIVE_READ_PASSED
invoke injected-failure
test "$(field 8)" = 0; test "$(field 12)" = -90; test "$(field 36)" = 1; match before
echo QEMU_CREATIVE_ROLLBACK_PASSED
invoke write
test "$(field 8)" = 1; test "$(field 32)" = 1; match after
echo QEMU_CREATIVE_WRITE_PASSED
invoke write
test "$(field 8)" = 0; test "$(field 12)" = -13; match after
echo QEMU_CREATIVE_REPEAT_REFUSED
invoke restore
test "$(field 8)" = 1; match before
echo QEMU_CREATIVE_RESTORE_PASSED
# A known mixed state is recoverable, but cannot be installed over.
$b dd if=/after.bin of="$d" bs=512 seek=FIRST count=1 conv=notrunc status=none
invoke write
test "$(field 8)" = 0; test "$(field 12)" = -13; test "$(field 24)" = 3
invoke restore
test "$(field 8)" = 1; match before
echo QEMU_CREATIVE_MIXED_RECOVERY_PASSED
printf 'bad' | $b dd of="$d" bs=1 seek=FIRST_BYTE conv=notrunc status=none
invoke write
test "$(field 8)" = 0; test "$(field 12)" = -13; test "$(field 28)" = 0
echo QEMU_CREATIVE_WRONG_PREIMAGE_REFUSED
test "$($b dd if="$d" bs=1 skip=8192 count=16 status=none)" = 'untouched canary'
echo QEMU_CREATIVE_FLASH_ALL_PASSED
$b poweroff -f
'''.replace('SECTORS',sectors).replace('FIRST_BYTE',str(manifest['sectors'][0])).replace('FIRST',sectors.split()[0]))
        (fs/'init').chmod(0o755)
        initrd=Path(temporary)/'initrd.cpio'
        with initrd.open('wb') as stream:
            run([shutil.which('bsdtar') or 'tar','-c','--format=newc','-f','-','.'],cwd=fs,stdout=stream,
                env={**os.environ,'COPYFILE_DISABLE':'1'})
        r=run(['qemu-system-arm','-M','virt','-cpu','cortex-a15','-m','768','-display','none','-serial','stdio',
               '-monitor','none','-nic','none','-no-reboot','-kernel',str(kernel),'-initrd',str(initrd),
               '-append','console=ttyAMA0 rdinit=/init quiet panic=1'],capture_output=True,timeout=35)
        (OUT/'qemu.log').write_bytes(r.stdout+r.stderr);print(r.stdout.decode(errors='replace'),end='')
        if b'QEMU_CREATIVE_FLASH_ALL_PASSED' not in r.stdout:raise ValueError('Flash payload tests failed')
    proof={'manifest_sha256':sha(OUT/'manifest.json'),
           'payloads':{name:sha(OUT/f'{name}.so') for name in ('read','write','restore')},
           'source_sha256':{name:sha(ROOT/name) for name in ('payloads/a7-creative-sectors.c','research/creative_flash_test.py')}}
    (OUT/'qemu-proof.json').write_text(json.dumps(proof,indent=2)+'\n')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('kernel','busybox','sony-root'):p.add_argument('--'+name,required=True,type=Path)
    a=p.parse_args();test(build(),a.kernel,a.busybox,a.sony_root)
