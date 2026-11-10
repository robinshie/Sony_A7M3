#!/usr/bin/env python3
"""Execute one unmodified 4.04 UI dispatch routine in isolated ARM QEMU.

Does not boot camera firmware, exercise the ISP, connect USB, or flash anything.
Original Sony bytes are extracted locally and stay in ignored .lab/.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess

from elf32 import ELF

ROOT = Path(__file__).resolve().parents[1]
VIEW_SHA = 'f561a1e5fa0d10d55727dd4a10ced97c9613b698a40b489ff9317634485e5129'
CONFIG_SHA = '0b9f2b855c032fc36cc83386a1fe706a8b59042e52702035a7d1a293b4e9f8a0'
START, END = 0x5b98dc, 0x5b9b6e


def inspect(config):
    properties = {}
    for name, sym in config.symbols.items():
        if not name.startswith('cmnViewSettingPropertyListCreativeStyle'):
            continue
        data = config.read(sym['value'], sym['size'])
        if len(data) % 12:
            raise ValueError('Unexpected property array layout')
        properties[name.removeprefix('cmnViewSettingPropertyList')] = {
            'address': hex(sym['value']),
            'triples': list(struct.iter_unpack('<III', data)),
        }
    # These are exported native arrays; record their relocation names rather
    # than guessing which product-specific array the camera chooses at runtime.
    lists = {}
    for name, sym in config.symbols.items():
        if 'CreativeStyle' not in name or sym['size'] < 8:
            continue
        targets = []
        for at in range(sym['value'], sym['value']+sym['size'], 4):
            rel = config.relocations.get(at)
            if rel and rel[1]['name'].startswith('cmnViewSettingNodeCreativeStyle'):
                targets.append(rel[1]['name'])
        if targets:
            lists[name] = targets
    return {'properties': properties, 'node_arrays': lists,
            'list_selector_backup_id': hex(config.word(0x6933f8))}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--usr', required=True, type=Path, help='Local nflasha15_unpacked')
    args = cli.parse_args()
    view = ELF(args.usr / 'lib/viewUnified2.so')
    config = ELF(args.usr / 'lib/CautionConfig.so')
    if hashlib.sha256(view.data).hexdigest() != VIEW_SHA or hashlib.sha256(config.data).hexdigest() != CONFIG_SHA:
        cli.error('Input hashes do not match the inspected 4.04 libraries')
    out = ROOT / '.lab/creative-research'
    out.mkdir(parents=True, exist_ok=True)
    code = view.read(START, END-START)
    (out/'dispatch.bin').write_bytes(code)
    (out/'dispatch.S').write_text('.syntax unified\n.thumb\n.section .text.native,"ax"\n'
        '.balign 4\n.global native_dispatch\n.thumb_func\nnative_dispatch:\n.incbin "dispatch.bin"\n')
    # This routine only uses arguments, its local jump table, and the stack.
    # No Sony imports, relocations or model service are supplied by this harness.
    (out/'harness.c').write_text(r'''
#include <stdint.h>
extern int native_dispatch(void *, int, int *);
static void put(const char *p) {
    volatile uint32_t *u=(volatile uint32_t *)0x10009000;
    while (*p) { while(u[6]&32) {} u[0]=*p++; }
}
static void num(int n) {
    char b[12]; int k=0;
    if(n<0) { put("-"); n=-n; }
    do { b[k++]='0'+n%10; n/=10; } while(n);
    while(k) { char c[2]={b[--k],0}; put(c); }
}
void guest_main(void) {
    for(int id=-1;id<=98;id++) {
        int box=-99;
        int style=native_dispatch(0,id,&box);
        put("MAP "); num(id); put(" "); num(style); put(" "); num(box); put("\n");
    }
    put("DISPATCH_DONE\n");
    register unsigned r0 __asm__("r0")=0x18;
    register unsigned r1 __asm__("r1")=0x20026;
    __asm__ volatile("svc 0x123456" : "+r"(r0), "+r"(r1) : : "memory");
}
''')
    gcc = shutil.which('arm-none-eabi-gcc')
    qemu = shutil.which('qemu-system-arm')
    if not gcc or not qemu:
        cli.error('arm-none-eabi-gcc and qemu-system-arm are required')
    subprocess.run([gcc, '-mcpu=cortex-a9', '-marm', '-Os', '-Wall', '-Wextra', '-ffreestanding',
                    '-fno-builtin', '-nostdlib', '-T', str(ROOT/'ui/guest.ld'),
                    str(ROOT/'ui/start.S'), 'harness.c', 'dispatch.S', '-lgcc',
                    '-o', 'dispatch.elf'], cwd=out, check=True)
    run = subprocess.run([qemu, '-M', 'realview-pbx-a9', '-smp', '1', '-m', '64',
        '-nodefaults', '-audio', 'none', '-nic', 'none', '-display', 'none', '-monitor', 'none',
        '-serial', 'stdio', '-semihosting-config', 'enable=on,target=native',
        '-device', f'loader,file={out}/dispatch.elf,cpu-num=0'],
        capture_output=True, text=True, timeout=12, check=True)
    (out/'dispatch.log').write_text(run.stdout + run.stderr)
    rows = [tuple(map(int, m)) for m in re.findall(r'^MAP (-?\d+) (-?\d+) (-?\d+)$', run.stdout, re.M)]
    if len(rows) != 100 or 'DISPATCH_DONE' not in run.stdout:
        raise ValueError('Incomplete QEMU execution')
    if any(rows[i+1] != (i,14,-99) for i in (-1,97,98)):
        raise ValueError('Unexpected out-of-range behavior')
    if any(not (0 <= style <= 13 and 0 <= box <= 6) for _,style,box in rows[1:98]):
        raise ValueError('Unexpected in-range dispatch output')
    report = inspect(config)
    report.update(view_sha256=VIEW_SHA, config_sha256=CONFIG_SHA,
                  routine_sha256=hashlib.sha256(code).hexdigest(),
                  routine_va=hex(START), routine_size=len(code), mappings=rows,
                  scope='Unmodified UI dispatch only; no ISP or camera integration tested',
                  flash_ready=False)
    (out/'dispatch-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS: executed original 4.04 dispatch for 97 valid and 3 out-of-range IDs.')
    print('ID 97: return 14; output slot remains untouched (-99).')
    print(f'Report: {out}/dispatch-report.json')
    print('FLASH_READY=false: native menu insertion and parameter application are unimplemented.')


if __name__ == '__main__':
    main()
