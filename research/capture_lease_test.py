#!/usr/bin/env python3
"""Run candidate lease guard with original DMM Open/Close on private QEMU state."""
import argparse,json,subprocess,shutil
from pathlib import Path
from kernel_probe import ROOT,sha
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--bundle',type=Path,required=True);p.add_argument('--grain',action='store_true');p.add_argument('--full',action='store_true');p.add_argument('--halation',action='store_true');p.add_argument('--film',action='store_true');a=p.parse_args()
if a.film:a.halation=True
if a.halation:a.full=True
if a.full:a.grain=True
native=ROOT/'.lab/dmm-exclusive';proof=json.loads((native/'proof.json').read_text())
if any(sha((ROOT/s).read_bytes())!=v for s,v in proof['source_sha256'].items()):raise ValueError('Refresh original DMM fixture')
out=ROOT/('.lab/capture-film-record' if a.film else '.lab/capture-halation-record' if a.halation else '.lab/capture-full-record' if a.full else '.lab/capture-grain-record' if a.grain else '.lab/capture-lease-record');out.mkdir(exist_ok=True);(out/'proof.json').unlink(missing_ok=True)
for n in ('native.S','start.S','guest.ld','handle.bin','lease.bin'):shutil.copyfile(native/n,out/n)
sources=['research/capture_lease_test.py','research/capture_lease_harness.c','research/kernel_probe/capture_lease_record.h','research/kernel_probe/capture_early_record.h']
if a.grain:sources+=['research/kernel_probe/capture_film_record.h' if a.film else 'research/kernel_probe/capture_halation_record.h' if a.halation else 'research/kernel_probe/capture_grain_record.h','payloads/a7-film-frame.c','payloads/a7-film-frame.h']
if a.full:sources+=['research/kernel_probe/grain_core.c']
subprocess.run(['arm-none-eabi-gcc','-mcpu=cortex-a15','-marm','-O2','-Wall','-Wextra','-Werror','-ffreestanding','-fno-builtin','-nostdlib',
    *(['-DTEST_FILM=1'] if a.film else []),*(['-DTEST_HALATION=1'] if a.halation else []),'-I'+str(ROOT/'payloads'),'-I'+str(a.bundle.resolve()),'-T','guest.ld','start.S','native.S',str(ROOT/sources[1]),
    *(['-DTEST_GRAIN=1','-DTEST_FULL=1',str(ROOT/'research/kernel_probe/grain_core.c')] if a.full else ['-DTEST_GRAIN=1',str(ROOT/'payloads/a7-film-frame.c')] if a.grain else []),'-lgcc','-o','test.elf'],cwd=out,check=True)
r=subprocess.run(['qemu-system-arm','-M','virt','-cpu','cortex-a15','-m','2048' if a.halation else '1024','-nodefaults','-audio','none','-nic','none','-display','none','-monitor','none',
    '-serial','stdio','-semihosting-config','enable=on,target=native','-device',f'loader,file={out}/test.elf,cpu-num=0'],capture_output=True,timeout=120)
log=r.stdout+r.stderr;(out/'qemu.log').write_bytes(log);print(log.decode(),end='')
if r.returncode or b'LEASE_CALLBACK_PASSED' not in log or b'FAIL' in log:raise ValueError('Lease fixture failed')
(out/'proof.json').write_text(json.dumps(dict(passed=True,source_sha256={s:sha((ROOT/s).read_bytes()) for s in sources},
    native_fixture_sha256=sha((native/'proof.json').read_bytes()),log=log.decode(),original_open_close_executed=True,
    lock_and_cachetype_mocked=True,private_records_only=True,private_pixels_modified=a.grain,camera_pixel_write=False),indent=2)+'\n')
