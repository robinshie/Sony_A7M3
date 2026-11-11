#!/usr/bin/env python3
"""Execute pinned AV-CAM Gamma receiver and curve sampler in isolated QEMU.

No camera transport or writes. Firmware excerpts remain under ignored .lab/.
The receiver and sampler are separate tests: their connection is NOT proven.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess

from fl_look import DEFAULT_RECIPE, native_tone, validate

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '.lab/gamma-avcam'
BASE = 0x635c6000
SHA = 'e1b0f84e8323005a34b43de6dd0083fca712d2c654f0d9716512e0a54631bbe7'
RANGES = {
    'receiver': (0x61b234, 0x61b288),
    'sampler': (0x7f8a82, 0x7f8b06),
    'division': (0x19f40, 0x1a19c),
    'identity': (0x8b5f52, 0x8b5f52 + 1025 * 2),
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--avcam', required=True, type=Path)
    args = cli.parse_args()
    data = args.avcam.read_bytes()
    if sha(data) != SHA:
        cli.error('Unexpected av-cam.bin; experiment requires the pinned 4.04 image')
    record = struct.unpack_from('<4I', data, 0x1174a20)
    if record != (0x40f0, BASE + 0x61b235, 0, BASE + 0x623d4d):
        raise ValueError('Unexpected native receiver registry')
    identity = struct.unpack_from('<1025H', data, 0x8b5f52)
    if identity != tuple(min(i * 64, 65535) for i in range(1025)):
        raise ValueError('Unexpected native identity curve')
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'proof.json').unlink(missing_ok=True)
    asm = '.syntax unified\n'
    sections = []
    for name, (start, end) in RANGES.items():
        (OUT / (name + '.bin')).write_bytes(data[start:end])
        asm += f'.section .{name},"ax"\n.incbin "{name}.bin"\n'
        sections.append((BASE + start, name))
    candidate = native_tone(validate(json.loads(DEFAULT_RECIPE.read_text())))
    (OUT / 'candidate.bin').write_bytes(candidate)
    asm += '.section .candidate,"a"\n.incbin "candidate.bin"\n'
    sections.append((0x40300000, 'candidate'))
    # Logging is the only reachable mocked call. Division-by-zero is a trap,
    # never expected: the original sampler always uses a denominator of 64.
    for offset, target in ((0x3a4bc0, 'native_log'), (0x646e4e, 'divide_zero')):
        name = f'stub_{offset:x}'
        asm += f'.section .{name},"ax"\n.thumb\nldr.w ip,1f\nbx ip\n.balign 4\n1: .word {target}\n'
        sections.append((BASE + offset, name))
    asm += '.section .note.GNU-stack,"",%progbits\n'
    (OUT / 'native.S').write_text(asm)
    (OUT / 'start.S').write_text('''.syntax unified
.arm
.section .text.start,"ax"
.global _start
_start:
    cpsid if
    ldr sp, =0x41000000
    ldr r0, =__bss_start
    ldr r1, =__bss_end
    mov r2, #0
1:  cmp r0, r1
    strlo r2, [r0], #4
    blo 1b
    bl guest_main
2:  wfi
    b 2b
.section .note.GNU-stack,"",%progbits
''')
    ld = 'ENTRY(_start)\nSECTIONS {\n. = 0x40200000;\n'
    ld += '.text : { *(.text.start) *(.text*) }\n.rodata : { *(.rodata*) }\n'
    ld += '.data : { *(.data*) }\n.bss (NOLOAD) : { __bss_start = .; *(.bss*) *(COMMON) . = ALIGN(8); __bss_end = .; }\n'
    ld += ''.join(f'.{name} {address:#x} : {{ *(.{name}) }}\n' for address, name in sorted(sections))
    ld += '}\n'
    (OUT / 'guest.ld').write_text(ld)
    subprocess.run(['arm-none-eabi-gcc', '-mcpu=cortex-a15', '-mthumb', '-Os', '-Wall',
                    '-Wextra', '-Werror', '-ffreestanding', '-fno-builtin', '-nostdlib',
                    '-T', 'guest.ld', 'start.S', str(ROOT / 'research/gamma_avcam_harness.c'),
                    'native.S', '-lgcc', '-o', 'gamma.elf'], cwd=OUT, check=True)
    r = subprocess.run(['qemu-system-arm', '-M', 'virt', '-cpu', 'cortex-a15', '-smp', '1',
                        '-m', '1024', '-nodefaults', '-audio', 'none', '-nic', 'none',
                        '-display', 'none', '-monitor', 'none', '-serial', 'stdio',
                        '-semihosting-config', 'enable=on,target=native', '-device',
                        f'loader,file={OUT}/gamma.elf,cpu-num=0'], capture_output=True,
                       timeout=30)
    log = r.stdout + r.stderr
    (OUT / 'qemu.log').write_bytes(log)
    print(log.decode(errors='replace'), end='')
    if r.returncode or b'QEMU_AVCAM_GAMMA_PASSED' not in r.stdout or b'FAIL ' in log:
        raise ValueError('Native AV-CAM Gamma experiment failed')
    proof = {
        'avcam_sha256': SHA, 'load_base': hex(BASE),
        'control_registry_file_offset': '0x1174a20',
        'native_ranges': {k: {'file_offset': hex(a), 'bytes': b-a,
                             'sha256': sha(data[a:b])} for k, (a, b) in RANGES.items()},
        'source_sha256': {p: sha((ROOT / p).read_bytes()) for p in
                          ('research/gamma_avcam.py', 'research/gamma_avcam_harness.c',
                           'research/fl_look.py', 'recipes/fl-inspired-v0.json')},
        'candidate_tone_sha256': sha(candidate),
        'qemu_log_sha256': sha(log), 'log': log.decode().splitlines(),
        'scope': 'Separate original receiver and original 1025-node sampler with original unsigned division; logging mocked',
        'sampler_format_known': True, 'external_pointer_to_sampler_proven': False,
        'pointer_address_space_known': False, 'jpeg_output_proven': False,
        'sony_fl_reproduced': False, 'flash_ready': False,
    }
    (OUT / 'proof.json').write_text(json.dumps(proof, indent=2) + '\n')


if __name__ == '__main__':
    main()
