#!/usr/bin/env python3
"""Run original JPEG, SoftFocus and display handoff helpers in QEMU RAM only.

The stage, descriptor wrapper, packer, submit/wait and sharing are native.
Lower allocation, SoftFocus processing, OS transport and publication are fixtures.
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
    'softfocus_stage': (0x34f5ec, 0x34f824),
    'capture_swap': (0x326ef4, 0x327030),
    'softfocus_errors': (0x86923c, 0x869248),
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
    0x3277bc: 'soft_input', 0x327718: 'soft_other',
    0x54cb2c: 'soft_alloc', 0x3e67fc: 'soft_params',
    0x353f48: 'soft_trace', 0x3a42dc: 'soft_event',
    0x54ccd4: 'soft_execute', 0x353c24: 'soft_config_trace',
    0x54cbf8: 'soft_free',
}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--avcam', type=Path, required=True)
    cli.add_argument('--out', type=Path, default=ROOT / '.lab/jpeg-stage-fixture')
    cli.add_argument('--kernel-callback', action='store_true',
                     help='Exercise UDF.W exception redirect and the kernel Thumb bridge')
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
        block = bytearray(data[lo:hi])
        if a.kernel_callback and name == 'jpeg_stage':
            block[0x34019c-lo:0x3401a0-lo] = bytes.fromhex('f0f773aa')
        (out / (name + '.bin')).write_bytes(block)
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
''' + ('''
    cps #0x1b
    ldr sp,=0x40ff0000
    cps #0x13
    ldr r0,=vectors
    mcr p15,0,r0,c12,c0,0
    isb
''' if a.kernel_callback else '') + '''
    ldr sp,=0x41000000
    bl guest_main
1:  wfi
    b 1b
.section .note.GNU-stack,"",%progbits
''')
    if a.kernel_callback:
        with (out / 'start.S').open('a') as f:
            f.write('''
.section .text.vectors,"ax"
.arm
.balign 32
vectors:
    b .
    b undef_entry
    b .
    b .
    b .
    b .
    b .
    b .
undef_entry:
    push {r0-r12,lr}
    mrs r1,spsr
    sub sp,sp,#8
    str r1,[sp]
    sub r0,lr,#2
    bl a7_fixture_undef
    str r0,[sp,#60]
    ldr r1,[sp]
    msr spsr_cxsf,r1
    add sp,sp,#8
    pop {r0-r12,lr}
    movs pc,lr
''')
    ld = ('ENTRY(_start)\nSECTIONS { . = 0x40200000;\n'
          '.text : { *(.text.start) *(.text*) } .rodata : { *(.rodata*) }\n'
          '.data : { *(.data*) } .bss (NOLOAD) : { *(.bss*) *(COMMON) }\n')
    ld += ''.join(f'.{n} {addr:#x} : {{ *(.{n}) }}\n' for addr, n in sorted(sections))
    (out / 'guest.ld').write_text(ld + '}\n')
    sources = ('research/jpeg_stage_fixture.py', 'research/jpeg_stage_harness.c',
               'research/gamma_avcam.py')
    extra = []
    if a.kernel_callback:
        sources += ('research/kernel_probe/capture_bridge.S',)
        extra = ['-DA7_KERNEL_CALLBACK_FIXTURE', str(ROOT / sources[-1])]
    subprocess.run(['arm-none-eabi-gcc', '-mcpu=cortex-a15', '-mthumb', '-mno-unaligned-access', '-O2',
                    '-Wall', '-Wextra', '-Werror', '-ffreestanding', '-fno-builtin', '-nostdlib',
                    '-T', 'guest.ld', 'start.S', 'stage.S', str(ROOT / sources[1]), *extra,
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
                 scope='Original JPEG/SoftFocus stages, capture handle swap, StdYc allocation wrapper, request packer, DMM sharing and display selector; lower allocation, pixel processing, transport, and publisher substituted',
                 input_handle_context_offset='0x62f6', derived_handle_request_offset='0x1c',
                 jpeg_allocated_unit_type='0xe0b00',
                 share_wrapper_executes_in_qemu=True,
                 display_selector_executes_in_qemu=True,
                 display_descriptor_handle_offset='0x08',
                 display_selector_scope='Original scalar SA display selector; source mapping, geometry helper and buffer lifetime operations substituted',
                 actual_display_path_executes_in_qemu=False,
                 softfocus_stage_executes_in_qemu=True,
                 capture_handle_swap_executes_in_qemu=True,
                 processed_handle_reaches_jpeg_descriptor_in_fixture=True,
                 softfocus_processing_allocation_transport_substituted=True,
                 actual_softfocus_or_grain_pixels_processed=False,
                 original_softfocus_cleanup_error_still_swaps=True,
                 frame_format_verified=False, writable_ownership_verified=False,
                 live_view_verified=False, sensor_or_encoder_run=False,
                 camera_written=False, flash_ready=False)
    proof['kernel_callback_bridge_tested'] = a.kernel_callback
    proof['kernel_exception_handler_substituted'] = a.kernel_callback
    (out / 'proof.json').write_text(json.dumps(proof, indent=2) + '\n')
    print(out / 'proof.json')


if __name__ == '__main__':
    main()
