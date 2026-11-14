#!/usr/bin/env python3
"""Run the original JPEG and display handoff helpers in QEMU RAM only.

The stage, descriptor wrapper, packer, submit/wait and sharing are native.
Lower allocation, OS transport and publication are replaced by test fixtures.
This does not execute an encoder, modify pixels, or communicate with a camera.
"""
import argparse
import json
from pathlib import Path
import subprocess

from gamma_avcam import BASE, SHA, sha

ROOT = Path(__file__).resolve().parents[1]
RANGES = {
    'jpeg_stage': (0x33ff20, 0x340334),
    'alloc_set_std_yc': (0x35cfc8, 0x35d060),
    'alloc_share': (0x3a5868, 0x3a58f0),
    'display_select': (0x4e88a0, 0x4e89f4),
}
STUBS = {
    0x76633e: 'get_context', 0x775b00: 'mark_stage', 0x77812c: 'scope_init',
    0x765ece: 'enter_stage', 0x31c7dc: 'optional_trace', 0x3279f0: 'get_slot',
    0x35e060: 'alloc_descriptor', 0x35cf10: 'describe_input', 0x77817c: 'hold_descriptor',
    0x3567cc: 'get_param', 0x50ca58: 'copy_word',
    0x35c9a0: 'get_byte', 0x350f14: 'publish', 0x77819e: 'drop_descriptor',
    0x35e520: 'scope_close', 0x3a4bc0: 'native_log',
    0x71c86c: 'channel_init', 0x772854: 'channel_available', 0x35d6b4: 'resource',
    0x772850: 'channel_token', 0x35ca98: 'channel_tag', 0x71c8a4: 'channel_id',
    0x71c88c: 'channel_close', 0x31fbf4: 'send_request', 0x31fc60: 'receive_reply',
    0x77aa04: 'valid_handle', 0x3a5140: 'alloc_share',
    0x4e6ab4: 'display_access_init', 0x7c3712: 'display_entry',
    0x7c591a: 'display_geometry', 0x4e1848: 'display_release',
    0x4e15f4: 'display_prepare', 0x4e690c: 'display_access_done',
    0x65be62: 'display_log', 0x7c7d9c: 'display_exception',
}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--avcam', type=Path, required=True)
    cli.add_argument('--out', type=Path, default=ROOT / '.lab/jpeg-stage-fixture')
    a = cli.parse_args()
    data = a.avcam.read_bytes()
    if sha(data) != SHA:
        cli.error('Requires pinned ILCE-7M3 4.04 AV-CAM')
    out = a.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    (out / 'proof.json').unlink(missing_ok=True)
    asm = '.syntax unified\n'
    sections = []
    for name, (lo, hi) in RANGES.items():
        (out / (name + '.bin')).write_bytes(data[lo:hi])
        asm += f'.section .{name},"ax"\n.incbin "{name}.bin"\n'
        sections.append((BASE + lo, name))
    # Model a channel whose static initialization has already happened.
    # No arbitrary camera data address is accessed by this fixture.
    asm += '.section .channel_ready,"aw"\n.word 1\n'
    sections.append((BASE + 0xd73db4, 'channel_ready'))
    for address, target in STUBS.items():
        name = f'stub_{address:x}'
        sections.append((BASE + address, name))
        asm += f'.section .{name},"ax"\n'
        if address == 0x50ca58:
            asm += f'.arm\nldr ip,1f\nbx ip\n1: .word {target}\n'
            continue
        asm += '.thumb\n'
        if address in (0x772850, 0x772854):
            # Adjacent original entries are four bytes apart.
            veneer = f'veneer_{address:x}'
            asm += f'b.w {veneer}\n.section .{veneer},"ax"\n{veneer}:\n'
            sections.append((BASE + 0x772c00 + (address - 0x772850) * 4, veneer))
        asm += f'movw ip,#:lower16:{target}\nmovt ip,#:upper16:{target}\nbx ip\n'
    asm += '.section .note.GNU-stack,"",%progbits\n'
    (out / 'stage.S').write_text(asm)
    (out / 'start.S').write_text('''.syntax unified
.arm
.section .text.start,"ax"
.global _start
_start:
    cpsid if
    ldr sp,=0x41000000
    bl guest_main
1:  wfi
    b 1b
.section .note.GNU-stack,"",%progbits
''')
    ld = ('ENTRY(_start)\nSECTIONS { . = 0x40200000;\n'
          '.text : { *(.text.start) *(.text*) } .rodata : { *(.rodata*) }\n'
          '.data : { *(.data*) } .bss (NOLOAD) : { *(.bss*) *(COMMON) }\n')
    ld += ''.join(f'.{n} {addr:#x} : {{ *(.{n}) }}\n' for addr, n in sorted(sections))
    (out / 'guest.ld').write_text(ld + '}\n')
    sources = ('research/jpeg_stage_fixture.py', 'research/jpeg_stage_harness.c',
               'research/gamma_avcam.py')
    subprocess.run(['arm-none-eabi-gcc', '-mcpu=cortex-a15', '-mthumb', '-mno-unaligned-access', '-O2',
                    '-Wall', '-Wextra', '-Werror', '-ffreestanding', '-fno-builtin', '-nostdlib',
                    '-T', 'guest.ld', 'start.S', 'stage.S', str(ROOT / sources[1]),
                    '-lgcc', '-o', 'stage.elf'], cwd=out, check=True)
    run = subprocess.run(['qemu-system-arm', '-M', 'virt', '-cpu', 'cortex-a15', '-m', '1024',
                          '-nodefaults', '-audio', 'none', '-nic', 'none', '-display', 'none',
                          '-monitor', 'none', '-serial', 'stdio',
                          '-semihosting-config', 'enable=on,target=native', '-device',
                          f'loader,file={out}/stage.elf,cpu-num=0'], capture_output=True, timeout=20)
    log = run.stdout + run.stderr
    (out / 'qemu.log').write_bytes(log)
    print(log.decode(errors='replace'), end='')
    if run.returncode or b'JPEG_STAGE_FIXTURE_PASSED' not in run.stdout or b'FAIL' in log:
        raise ValueError('Original JPEG stage fixture failed')
    proof = dict(avcam_sha256=SHA,
                 native={name: dict(file_offset=hex(lo), size=hi-lo, sha256=sha(data[lo:hi]))
                         for name, (lo, hi) in RANGES.items()},
                 source_sha256={p: sha((ROOT / p).read_bytes()) for p in sources},
                 log=log.decode().splitlines(), qemu_log_sha256=sha(log),
                 scope='Original stage, StdYc allocation wrapper, request packer and DMM sharing wrapper; lower allocation, transport, and publisher substituted',
                 input_handle_context_offset='0x62f6', derived_handle_request_offset='0x1c',
                 jpeg_allocated_unit_type='0xe0b00',
                 share_wrapper_executes_in_qemu=True,
                 display_selector_executes_in_qemu=True,
                 display_descriptor_handle_offset='0x08',
                 display_selector_scope='Original scalar SA display selector; source mapping, geometry helper and buffer lifetime operations substituted',
                 actual_display_path_executes_in_qemu=False,
                 frame_format_verified=False, writable_ownership_verified=False,
                 live_view_verified=False, sensor_or_encoder_run=False,
                 camera_written=False, flash_ready=False)
    (out / 'proof.json').write_text(json.dumps(proof, indent=2) + '\n')
    print(out / 'proof.json')


if __name__ == '__main__':
    main()
