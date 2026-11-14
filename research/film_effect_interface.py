#!/usr/bin/env python3
"""Offline original grain/soft-focus enum and state-checker tests. No USB I/O.

This does NOT prove a pixel algorithm, a live-view hook, or composability with
FL3. Sony code is loaded only from user's pinned local firmware into .lab.
"""
import argparse
import json
from pathlib import Path
import struct
import subprocess

from gamma_avcam import BASE, SHA, sha

ROOT = Path(__file__).resolve().parents[1]
OBJ_SHA = '1117453a969c9dedeb9bf6b006514fd9c2644a79085590a797189df109d64d23'


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--avcam', type=Path, required=True)
    cli.add_argument('--object-library', type=Path, required=True)
    cli.add_argument('--out', type=Path, default=ROOT / '.lab/film-effect-interface')
    a = cli.parse_args()
    av, obj = a.avcam.read_bytes(), a.object_library.read_bytes()
    if sha(av) != SHA or sha(obj) != OBJ_SHA:
        cli.error('Requires the exact pinned ILCE-7M3 4.04 inputs')
    jump = [0x6224e0 + 2 * n for n in av[0x6224e0:0x6224ed]]
    if jump[6:8] != [0x622542, 0x622556]:
        raise ValueError('Unexpected effect checker branch table')
    for pool, pc, expected in ((0x622600, 0x622550, 0x9caa92), (0x622608, 0x622564, 0x9caadf)):
        if (struct.unpack_from('<I', av, pool)[0] + pc + 4) & 0xffffffff != expected:
            raise ValueError('Unexpected checker log identity')
    out = a.out.resolve(); out.mkdir(parents=True, exist_ok=True)
    (out / 'proof.json').unlink(missing_ok=True)
    ranges = {'grain_convert': (obj, 0x50000000, 0x46beb0, 0x46bf08),
              'soft_convert': (obj, 0x50000000, 0x46bf08, 0x46bf60),
              'effect_checker': (av, BASE, 0x6224b0, 0x622638)}
    sections = []; assembly = '.syntax unified\n'
    for name, (data, base, lo, hi) in ranges.items():
        (out / (name + '.bin')).write_bytes(data[lo:hi])
        assembly += f'.section .{name},"ax"\n.incbin "{name}.bin"\n'
        sections.append((base + lo, name))
    for address, name in ((0x504d02cc, 'log_open'), (0x504d0194, 'log_close'),
                          (BASE + 0x61f844, 'get_state'), (BASE + 0x3a4bc0, 'native_log')):
        assembly += f'.section .{name},"ax"\n.thumb\nldr.w ip,1f\nbx ip\n.balign 4\n1: .word {name}\n'
        sections.append((address, name))
    assembly += '.section .note.GNU-stack,"",%progbits\n'
    (out / 'native.S').write_text(assembly)
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
    linker = ('ENTRY(_start)\nSECTIONS { . = 0x40200000;\n'
              '.text : { *(.text.start) *(.text*) } .rodata : { *(.rodata*) }\n'
              '.data : { *(.data*) } .bss (NOLOAD) : { __bss_start = .; *(.bss*) *(COMMON) . = ALIGN(8); __bss_end = .; }\n')
    linker += ''.join(f'.{n} {addr:#x} : {{ *(.{n}) }}\n' for addr, n in sorted(sections))
    (out / 'guest.ld').write_text(linker + '}\n')
    subprocess.run(['arm-none-eabi-gcc', '-mcpu=cortex-a15', '-mthumb', '-O2', '-Wall', '-Wextra', '-Werror',
                    '-ffreestanding', '-fno-builtin', '-nostdlib', '-T', 'guest.ld', 'start.S', 'native.S',
                    str(ROOT / 'research/film_effect_interface_harness.c'), '-lgcc', '-o', 'effect.elf'], cwd=out, check=True)
    result = subprocess.run(['qemu-system-arm', '-M', 'virt', '-cpu', 'cortex-a15', '-smp', '1', '-m', '1024',
                             '-nodefaults', '-audio', 'none', '-nic', 'none', '-display', 'none', '-monitor', 'none',
                             '-serial', 'stdio', '-semihosting-config', 'enable=on,target=native',
                             '-device', f'loader,file={out}/effect.elf,cpu-num=0'], capture_output=True, timeout=30, check=True)
    log = result.stdout + result.stderr; (out / 'qemu.log').write_bytes(log)
    print(log.decode(errors='replace'), end='')
    if b'FILM_EFFECT_INTERFACE_PASSED' not in result.stdout or b'FAIL' in log:
        raise ValueError('Original interface fixture failed')
    proof = dict(avcam_sha256=SHA, object_sha256=OBJ_SHA,
                 native_ranges={n: dict(offset=hex(lo), size=hi-lo, sha256=sha(data[lo:hi]))
                                for n, (data, _, lo, hi) in ranges.items()},
                 source_sha256={n: sha((ROOT / n).read_bytes()) for n in
                                ('research/film_effect_interface.py', 'research/film_effect_interface_harness.c', 'research/gamma_avcam.py')},
                 qemu_log_sha256=sha(log), log=log.decode().splitlines(),
                 grain_enum_mapping={str(i): hex(0x293+i) for i in range(4)},
                 soft_focus_enum_mapping={str(i): hex(0x297+i) for i in range(3)},
                 checked_effect_modes=dict(rough_monochrome=7, soft_focus=8),
                 current_strength_field='state + 0xf0 shared by selected effect mode',
                 scope='Original enum converters and state checker; logger and model accessor mocked',
                 pixels_processed=False, runtime_effect_tested=False, composable_with_fl3_proven=False,
                 camera_written=False, flash_ready=False)
    (out / 'proof.json').write_text(json.dumps(proof, indent=2) + '\n')


if __name__ == '__main__':
    main()
