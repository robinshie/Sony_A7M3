#!/usr/bin/env python3
"""Test native Gamma pointer forwarding; no camera transport or flash output.

This connects extracted basic blocks with fixtures. It does not execute their
enclosing functions, schedules or queues, and never dereferences the pointer.
"""
import argparse
import json
from pathlib import Path
import struct
import subprocess

from gamma_avcam import BASE, SHA, sha

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '.lab/gamma-route'
RANGES = {
    'receiver': (0x61b234, 0x61b288),
    'bridge': (0x5e797a, 0x5e7a24),
    'bridge_literals': (0x5e7ca4, 0x5e7cb4),
    'descriptor': (0x7f8a3c, 0x7f8a60),
    'forward': (0x5e008a, 0x5e009a),
    'report': (0x6158bc, 0x61591c),
}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--avcam', required=True, type=Path)
    args = cli.parse_args()
    data = args.avcam.read_bytes()
    if sha(data) != SHA:
        cli.error('Requires the pinned ILCE-7M3 4.04 av-cam.bin')
    if struct.unpack_from('<2I', data, 0x1173a98) != (0x2072, BASE+0x6158bd):
        raise ValueError('Unexpected pointer report registry')
    if struct.unpack_from('<4I', data, 0x5e7ca4) != (0xa640, 0xaa3c, 0x9d44, 0x9f3c):
        raise ValueError('Unexpected bridge GOT literals')
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'proof.json').unlink(missing_ok=True)
    asm = '.syntax unified\n'
    sections = []
    for name, (start, end) in RANGES.items():
        (OUT / (name+'.bin')).write_bytes(data[start:end])
        asm += f'.section .{name},"ax"\n.incbin "{name}.bin"\n'
        sections.append((BASE+start, name))
    # Block exits and runtime boundary replacements; original block bytes and
    # PC-relative literals are unchanged. The memcpy boundary uses an ARM stub
    # because the original caller explicitly BLXes to ARM state.
    stubs = [
        (0x5e7a24, 'route_bridge_return', False),
        (0x7f8a60, 'route_descriptor_return', False),
        (0x5e009a, 'route_forward_return', False),
        (0x31c680, 'native_mode', False),
        (0x3a4bc0, 'native_log', False),
        (0x50ca58, 'native_copy', True),
    ]
    for offset, target, arm in stubs:
        name = f'stub_{offset:x}'
        asm += f'.section .{name},"ax"\n'+('.arm\n' if arm else '.thumb\n')
        asm += f'ldr ip,1f\nbx ip\n.balign 4\n1: .word {target}\n'
        sections.append((BASE+offset, name))
    asm += '.section .note.GNU-stack,"",%progbits\n'
    (OUT / 'native.S').write_text(asm)
    (OUT / 'start.S').write_text('''.syntax unified
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
    ld = 'ENTRY(_start)\nSECTIONS {\n. = 0x40200000;\n'
    ld += '.text : { *(.text.start) *(.text*) }\n.rodata : { *(.rodata*) }\n.data : { *(.data*) }\n'
    ld += '.bss (NOLOAD) : { __bss_start = .; *(.bss*) *(COMMON) . = ALIGN(8); __bss_end = .; }\n'
    ld += ''.join(f'.{name} {address:#x} : {{ *(.{name}) }}\n' for address,name in sorted(sections))
    (OUT / 'guest.ld').write_text(ld+'}\n')
    subprocess.run(['arm-none-eabi-gcc','-mcpu=cortex-a15','-mthumb','-Os','-Wall',
                    '-Wextra','-Werror','-ffreestanding','-fno-builtin','-nostdlib',
                    '-T','guest.ld','start.S',str(ROOT/'research/gamma_route.S'),
                    str(ROOT/'research/gamma_route_harness.c'),'native.S','-lgcc',
                    '-o','route.elf'],cwd=OUT,check=True)
    result = subprocess.run(['qemu-system-arm','-M','virt','-cpu','cortex-a15','-smp','1',
                             '-m','1024','-nodefaults','-audio','none','-nic','none',
                             '-display','none','-monitor','none','-serial','stdio',
                             '-semihosting-config','enable=on,target=native','-device',
                             f'loader,file={OUT}/route.elf,cpu-num=0'],
                            capture_output=True,timeout=45)
    log = result.stdout+result.stderr
    (OUT / 'qemu.log').write_bytes(log)
    print(log.decode(errors='replace'),end='')
    if result.returncode or b'QEMU_GAMMA_ROUTE_PASSED' not in result.stdout or b'FAIL ' in log:
        raise ValueError('Native pointer forwarding test failed')
    sources = ('research/gamma_route.py','research/gamma_route.S',
               'research/gamma_route_harness.c','research/gamma_avcam.py')
    proof = {
        'avcam_sha256': SHA, 'load_base': hex(BASE),
        'native_ranges': {k:{'file_offset':hex(a),'bytes':b-a,'sha256':sha(data[a:b])}
                          for k,(a,b) in RANGES.items()},
        'source_sha256': {p:sha((ROOT/p).read_bytes()) for p in sources},
        'elf_sha256': sha((OUT/'route.elf').read_bytes()), 'qemu_log_sha256': sha(log),
        'log': log.decode().splitlines(), 'routes':15600, 'report_cases':46800,
        'report_control_id':'0x2072','report_registry_offset':'0x1173a98',
        'scope':'Fixture-connected native blocks and full receiver/report; memcpy and mode boundary mocked; logging trapped',
        'native_full_call_chain_executed':False, 'report_header_initialized_by_fixture':True,
        'pointer_forwarding_blocks_verified':True,'table_dereferenced':False,
        'pointer_address_space_known':False,'external_pointer_to_sampler_proven':False,
        'jpeg_output_proven':False,'camera_integration':False,'flash_ready':False,
    }
    (OUT/'proof.json').write_text(json.dumps(proof,indent=2)+'\n')


if __name__ == '__main__':
    main()
