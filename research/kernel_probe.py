#!/usr/bin/env python3
"""Build a read-only kernel ABI probe; --live loads, reads, then unloads it.

No capture hooks, cache operations, image writes or persistent installation.
Requires a prepared Sony kernel tree; validates module layout against liro.ko.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import time
from elf32 import ELF
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
PINS = {
    'avcam': 'e1b0f84e8323005a34b43de6dd0083fca712d2c654f0d9716512e0a54631bbe7',
    'kernel': '175df4fc47ddf51c1677cb71066e76552c62cfbe0df1ea5fe752589098a06f4d',
}
def sha(data): return hashlib.sha256(data).hexdigest()

def abi(path):
    e = ELF(path)
    header = struct.unpack_from('<16sHHIIIIIHHHHHH', e.data)
    names = e.section(header[-1])
    sections = {names[s[0]:names.index(b'\0', s[0])].decode(): i for i, s in enumerate(e.sections)}
    idx = sections['.gnu.linkonce.this_module']
    rel = e.section(sections['.rel.gnu.linkonce.this_module'])
    offsets = [struct.unpack_from('<II', rel, i) for i in range(0, len(rel), 8)]
    info = e.section(sections['.modinfo']).split(b'\0')
    vermagic = next(x.split(b'=', 1)[1].decode() for x in info if x.startswith(b'vermagic='))
    undefined = []
    for s in e.sections:
        if s[1] != 2: continue
        strings = e.section(s[6])
        for at in range(s[4], s[4]+s[5], s[9]):
            name, _, _, _, _, section = struct.unpack_from('<IIIBBH', e.data, at)
            if name and section == 0:
                undefined.append(strings[name:strings.index(b'\0', name)].decode())
    return dict(size=e.sections[idx][5], relocation_offsets=[x[0] for x in offsets],
                relocation_types=[x[1] & 255 for x in offsets], vermagic=vermagic,
                undefined=sorted(undefined))

def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('avcam', 'kernel', 'liro', 'kernel-source'):
        p.add_argument('--'+name, type=Path, required=True)
    p.add_argument('--live', action='store_true')
    p.add_argument('--source-sample', action='store_true',help='Bounded current DRAM sample, no frame lease')
    a = p.parse_args()
    data = {name: getattr(a, name).read_bytes() for name in PINS}
    if any(sha(data[n]) != pin for n, pin in PINS.items()):
        raise ValueError('Wrong pinned original firmware')
    out = ROOT/'.lab/kernel-probe-runs'/str(time.time_ns())
    out.mkdir(parents=True)
    header = ''.join('static const unsigned char '+name+'[]={'+','.join(map(str, b))+'};\n'
        for name, b in [('stage_pin', data['avcam'][0x34018c:0x34019a]),
                        ('kernel_pin', data['kernel'][0x10470:0x10490])])
    (out/'pins.h').write_text(header)
    name='a7source' if a.source_sample else 'a7kprobe'
    (out/'Makefile').write_text(f'obj-m += {name}.o\n')
    shutil.copyfile(ROOT/'research/kernel_probe'/(name+'.c'),out/(name+'.c'))
    cmd = ['make', '-C', str(a.kernel_source.resolve()), 'ARCH=arm',
           'CROSS_COMPILE=arm-none-eabi-', 'HOSTCC=clang',
           'HOSTCFLAGS=-O2 -I'+str(ROOT/'.lab/kernel-host-include'),
           'KCFLAGS=-std=gnu89', 'LOCALVERSION=+']
    with (out/'build.log').open('w') as log:
        subprocess.run(cmd+['modules_prepare'], stdout=log, stderr=log, check=True)
        subprocess.run(cmd+['M='+str(out), 'modules'], stdout=log, stderr=log, check=True)
    module = out/(name+'.ko')
    subprocess.run(['arm-none-eabi-strip', '--strip-debug', str(module)], check=True)
    actual, reference = abi(module), abi(a.liro)
    for key in ('size', 'relocation_offsets', 'relocation_types', 'vermagic'):
        if actual[key] != reference[key]: raise ValueError('Module ABI mismatch: '+key)
    if actual['size'] != 0x13c or actual['relocation_offsets'] != [0xbc, 0x134]:
        raise ValueError('Unexpected original module layout')
    allowed={'memcmp','param_array_ops','param_ops_uint'} if not a.source_sample else {'memcmp','memcpy','probe_kernel_read','arch_phys_to_va','jiffies','sysfs_create_bin_file','sysfs_remove_bin_file'}
    if not set(actual['undefined']) <= allowed:
        raise ValueError('Unexpected kernel dependencies')
    (out/'embedded.S').write_text('.section .rodata\n.balign 4\n.global module_start,module_end\n'
        f'module_start:\n.incbin "{name}.ko"\nmodule_end:\n'
        '.section .note.GNU-stack,"",%progbits\n')
    subprocess.run(['arm-none-eabi-gcc', '-mcpu=cortex-a9', '-marm', '-mfloat-abi=soft',
        '-fPIC', '-Os', '-ffreestanding', '-fno-builtin', '-fno-unwind-tables',
        '-fno-asynchronous-unwind-tables', '-nostdlib', '-shared', '-Wl,--no-undefined',
        '-Wl,-z,noexecstack', '-Wall', '-Wextra', '-Werror', '-I'+str(out),
        *(['-DA7_SOURCE_SAMPLE=1','-DA7_REPORT_BYTES=98000'] if a.source_sample else []),
        str(ROOT/'research/kernel_probe_loader.c'), 'embedded.S', '-o', 'loader.so'], cwd=out, check=True)
    sources = ['research/kernel_probe.py', 'research/kernel_probe_loader.c',
               'research/kernel_probe/'+name+'.c']
    proof = dict(source_sha256={n: sha((ROOT/n).read_bytes()) for n in sources},
        module_sha256=sha(module.read_bytes()), loader_sha256=sha((out/'loader.so').read_bytes()),
        kernel_config_sha256=sha((a.kernel_source/'.config').read_bytes()),
        reference_liro_sha256=sha(a.liro.read_bytes()), pins=PINS, abi=actual,
        source_sample=a.source_sample,camera_run=False, callback_installed=False, pixel_write=False, firmware_written=False)
    def save(): (out/'proof.json').write_text(json.dumps(proof, indent=2)+'\n')
    save()
    if a.live:
        from camera import handoff, service
        def collect(camera, action):
            if action != 'settings-snapshot': raise ValueError('Unexpected action')
            f = service.Factory(camera)
            if f.contents('/version.txt') != b'37114_13.2026020901' or bytes(camera.readBackup(0x3e0005)) != b'ILCE-7M3'+bytes(8):
                raise ValueError('Wrong model/build')
            raw = f.run((out/'loader.so').read_bytes(), 'a7ss.bin' if a.source_sample else 'a7kp.bin')
            (out/'live.bin').write_bytes(raw)
            if len(raw) != (98092 if a.source_sample else 1116): raise ValueError('Wrong report size')
            magic, version, status, loaded, unloaded, used = struct.unpack_from('<IIiiiI', raw)
            if (magic, version) != (0x41374b4c, 1) or used > (97988 if a.source_sample else 1023): raise ValueError('Wrong report identity')
            result = dict(status=status, load_result=loaded, unload_result=unloaded,
                release=raw[24:89].split(b'\0')[0].decode(),
                report='' if a.source_sample else raw[92:92+used].decode(), temporary_files_removed=True)
            proof.update(camera_run=True, result=result)
            save(); print(json.dumps(result, indent=2), flush=True)
            if status or loaded or unloaded: raise ValueError('Kernel probe did not complete cleanly')
            if a.source_sample:
                data=raw[92:92+used];(out/'sample-report.bin').write_bytes(data)
                if len(data)!=97988:raise ValueError('Incomplete kernel sample report')
                magic,version,status,rows,va,base,stride,step=struct.unpack_from('<IIi5I',data)
                if (magic,version)!=(0x4137534b,1):raise ValueError('Wrong kernel sample identity')
                proof['sample']=dict(status=status,rows=rows,va=hex(va),base=hex(base),stride=stride,step=step,
                    metadata=[hex(x) for x in struct.unpack_from('<100I',data,32)],
                    after=[hex(x) for x in struct.unpack_from('<5I',data,432)],
                    read_statuses=list(struct.unpack_from('<64i',data,452)),frame_lease=False,cache_sync_called=False)
                proof['kernel_module_loaded_and_unloaded']=True;save()
                print(json.dumps({k:v for k,v in proof['sample'].items() if k not in ('metadata','read_statuses')},indent=2))
                if status:raise ValueError('Current source could not be sampled; no image writes')
                if rows!=64 or stride!=12160 or step!=128 or any(proof['sample']['read_statuses']):raise ValueError('Incomplete pixel sampling')
                (out/'sample.raw').write_bytes(data[708:]);proof['sample_sha256']=sha(data[708:]);save();return
            values = [int(x) for x in result['report'].strip().split(',')]
            if len(values) != 16 or values[:5] != [0x41374b50,1,316,188,308] or values[12:] != [0x6390618c,14,0,0]:
                raise ValueError('Unexpected kernel inspection result')
            proof['kernel_module_loaded_and_unloaded'] = True; save()
        old, sw = service.perform, handoff.SWITCH
        service.perform = collect; handoff.SWITCH += ' --host-identity-check'
        try: handoff.run('settings-snapshot')
        finally: service.perform = old; handoff.SWITCH = sw
    print('EVIDENCE', out)
if __name__ == '__main__': main()
