#!/usr/bin/env python3
"""Compare our bounded DMM channel with original 4.04 request producers in QEMU.

The original constructors/destructors run; only queue allocation and transport
are fixtures. Nothing is loaded onto the camera by this tool.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
from elf32 import ELF

ROOT = Path(__file__).resolve().parents[1]
PIN = '5ae5eaf81286d99214e14d640bd276277fd22a1d137aec502f508022b3409910'
BASE = 0x50000000
OVERRIDE = {
    '_ZN17OBJAVBBCBASECLASS15DataflowInfraCh11allocOsalIdEPjNS0_21OSALID_AUTO_FREE_MODEE': 'queue_alloc',
    '_ZN17OBJAVBBCBASECLASS15DataflowInfraCh10freeOsalIdEj': 'queue_free',
    '_ZN17OBJAVBBCBASECLASS15DataflowInfraCh17sndAsyncGlobalMsgEPvtjj': 'queue_send',
    '_ZN17OBJAVBBCBASECLASS15DataflowInfraCh17rcvAsyncGlobalMsgEPvtjj': 'queue_receive',
    '_ZN17OBJAVBBCBASECLASS13getPrintLevelEv': 'print_level',
    '_ZN17AvbbcBaseClassLog7SetLog0Ejjjjt': 'native_log',
    'memset': 'memset', 'memcpy': 'memcpy',
}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--library', type=Path, required=True)
    p.add_argument('--out', type=Path, default=ROOT / '.lab/dmm-channel')
    a = p.parse_args(); e = ELF(a.library)
    sha = lambda b: hashlib.sha256(b).hexdigest()
    if sha(e.data) != PIN:
        p.error('Requires the pinned private ILCE-7M3 4.04 libBizFw.so')
    out = a.out.resolve(); out.mkdir(parents=True, exist_ok=True)
    (out / 'proof.json').unlink(missing_ok=True)
    memory = bytearray(max(va + ms for k, _, va, _, _, ms, _, _ in e.segments if k == 1))
    for k, offset, va, _, size, _, _, _ in e.segments:
        if k == 1:
            memory[va:va + size] = e.data[offset:offset + size]
    fixups = []
    for address, (kind, symbol) in e.relocations.items():
        addend = struct.unpack_from('<I', memory, address)[0]
        name = symbol['name']
        if kind == 23:
            value = BASE + addend
        elif kind in (2, 21, 22):
            if name in OVERRIDE or not symbol['section']:
                fixups.append((BASE + address, OVERRIDE.get(name, 'forbidden_native_call'), addend if kind == 2 else 0))
                value = 0
            else:
                value = BASE + symbol['value'] + (addend if kind == 2 else 0)
        else:
            raise ValueError('Unsupported native relocation')
        struct.pack_into('<I', memory, address, value & 0xffffffff)
    (out / 'native.bin').write_bytes(memory)
    (out / 'native.S').write_text('.section .native,"awx"\n.incbin "native.bin"\n.section .note.GNU-stack,"",%progbits\n')
    (out / 'native-fixups.h').write_text('struct Fix {unsigned address;uintptr_t function;unsigned addend;};\n'
        'static const struct Fix fixups[]={\n' + ''.join(f'{{{at}u,(uintptr_t){fn},{add}u}},\n' for at, fn, add in fixups) + '};\n')
    (out / 'start.S').write_text('''.syntax unified
.arm
.section .text.start,"ax"
.global _start
_start:
    cpsid if
    ldr sp,=0x41000000
    ldr r0,=__bss_start
    ldr r1,=__bss_end
    mov r2,#0
1:  cmp r0,r1
    strlo r2,[r0],#4
    blo 1b
    bl guest_main
2:  wfi
    b 2b
.section .note.GNU-stack,"",%progbits
''')
    (out / 'guest.ld').write_text('''ENTRY(_start)
SECTIONS { . = 0x40200000;
.text : { *(.text.start) *(.text*) } .rodata : { *(.rodata*) }
.data : { *(.data*) } .bss (NOLOAD) : { __bss_start = .; *(.bss*) *(COMMON) . = ALIGN(8); __bss_end = .; }
.native 0x50000000 : { *(.native) } }
''')
    sources = ('payloads/a7-dmm-channel.c', 'payloads/a7-dmm-channel.h',
               'research/dmm_channel_harness.c', 'research/dmm_channel_test.py', 'research/elf32.py',
               'research/dmm_observer.c','research/dmm_observer.h','research/dmm_frame_dump.h')
    subprocess.run(['arm-none-eabi-gcc', '-mcpu=cortex-a9', '-mthumb', '-mno-unaligned-access', '-O2', '-Wall', '-Wextra', '-Werror',
                    '-Wno-misleading-indentation', '-ffreestanding', '-fno-builtin', '-nostdlib', '-I', str(out),
                    '-I', str(ROOT / 'payloads'), '-T', 'guest.ld', 'start.S', 'native.S',
                    str(ROOT / sources[0]), str(ROOT / sources[2]), '-lgcc', '-o', 'dmm.elf'], cwd=out, check=True)
    result = subprocess.run(['qemu-system-arm', '-M', 'virt', '-cpu', 'cortex-a15', '-smp', '1', '-m', '512',
                             '-nodefaults', '-audio', 'none', '-nic', 'none', '-display', 'none', '-monitor', 'none',
                             '-serial', 'stdio', '-semihosting-config', 'enable=on,target=native',
                             '-device', f'loader,file={out}/dmm.elf,cpu-num=0'], check=True, capture_output=True, timeout=30)
    log = result.stdout + result.stderr; (out / 'qemu.log').write_bytes(log); print(log.decode(), end='')
    if b'DMM_CHANNEL_PASSED' not in log or b'FAIL' in log:
        raise ValueError('DMM channel fixture failed')
    (out / 'proof.json').write_text(json.dumps(dict(library_sha256=PIN,
        source_sha256={s: sha((ROOT / s).read_bytes()) for s in sources}, qemu_log_sha256=sha(log),
        log=log.decode().splitlines(), native_queue_transport_mocked=True,
        camera_executed=False, exclusive_frame_ownership_proven=False, flash_ready=False), indent=2) + '\n')


if __name__ == '__main__':
    main()
