#!/usr/bin/env python3
"""Exercise the original 4.04 creative-style setter with recording QEMU stubs.

Sony code is extracted locally; no camera or image-processing hardware is used.
The stubs record persistence requests and model messages, not their completion.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

from elf32 import ELF
from creative_dispatch import VIEW_SHA

ROOT = Path(__file__).resolve().parents[1]
START, END = 0x420d18, 0x420fb0
STUBS = {
    0x15867c: ('allocate', False), 0x15d504: ('copy_bytes', False),
    0x15a598: ('no_op', False), 0x15a4cc: ('no_op', False),
    0x1617cc: ('param_init', True), 0x16180c: ('param_value', True),
    0x158810: ('backup_write', False), 0x15d230: ('list_init', False),
    0x15c7b8: ('list_add', False), 0x15aa58: ('model_execute', False),
    0x159c64: ('unexpected', False), 0x159ba8: ('unexpected', False),
}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--usr', required=True, type=Path)
    args = cli.parse_args()
    view = ELF(args.usr / 'lib/viewUnified2.so')
    if hashlib.sha256(view.data).hexdigest() != VIEW_SHA:
        cli.error('Unexpected firmware library SHA-256')
    out = ROOT / '.lab/creative-setter'
    out.mkdir(parents=True, exist_ok=True)
    (out / 'report.json').unlink(missing_ok=True)
    pieces = [(START, END-START, 'setter'), (0x74f608, 28, 'box_ids'),
              (0x74f31c, 240, 'parameter_ids'), (0x63fc55, 6, 'model_name')]
    assembly = '.syntax unified\n'
    sections = []
    for va, size, name in pieces:
        (out / f'{name}.bin').write_bytes(view.read(va, size))
        assembly += f'.section .native_{name},"a"\n.incbin "{name}.bin"\n'
        sections.append((va, f'.native_{name}'))
    for va, (name, thumb) in STUBS.items():
        section = f'.stub_{va:x}'
        sections.append((va, section))
        assembly += f'.section {section},"ax"\n'
        assembly += f'.thumb\nb.w {name}\n' if thumb else f'.arm\nldr ip, [pc, #0]\nbx ip\n.word {name}\n'
    (out / 'native.S').write_text(assembly)
    # Preserve original virtual addresses, including all PC-relative tables.
    script = 'ENTRY(_start)\nSECTIONS {\n. = 0x100000;\n'
    script += '.text : { *(.text.start) *(.text*) }\n.rodata : { *(.rodata*) }\n. = ALIGN(4096);\n'
    script += '.data : { *(.data*) }\n.bss (NOLOAD) : { __bss_start = .; *(.bss*) *(COMMON) . = ALIGN(8); __bss_end = .; }\n'
    script += ''.join(f'{name} {va:#x} : {{ *({name}) }}\n' for va, name in sorted(sections))
    script += '}\n'
    (out / 'guest.ld').write_text(script)
    gcc, qemu = shutil.which('arm-none-eabi-gcc'), shutil.which('qemu-system-arm')
    if not gcc or not qemu:
        cli.error('Install ARM GCC and QEMU')
    subprocess.run([gcc, '-mcpu=cortex-a9', '-mthumb', '-mno-unaligned-access', '-Os', '-Wall', '-Wextra',
                    '-ffreestanding', '-fno-builtin', '-nostdlib', '-T', 'guest.ld',
                    str(ROOT / 'ui/start.S'), str(ROOT / 'research/creative_setter_harness.c'),
                    'native.S', '-lgcc', '-o', 'setter.elf'], cwd=out, check=True)
    run = subprocess.run([qemu, '-M', 'realview-pbx-a9', '-smp', '1', '-m', '64',
                          '-nodefaults', '-audio', 'none', '-nic', 'none', '-display', 'none',
                          '-monitor', 'none', '-serial', 'stdio',
                          '-semihosting-config', 'enable=on,target=native',
                          '-device', f'loader,file={out}/setter.elf,cpu-num=0'],
                         capture_output=True, text=True, timeout=20, check=True)
    (out / 'setter.log').write_text(run.stdout + run.stderr)
    print(run.stdout, end='')
    if 'NATIVE_SETTER_TESTS_PASSED' not in run.stdout or any(line.startswith('FAIL ') for line in run.stdout.splitlines()):
        raise ValueError('Native setter tests failed')
    report = {'view_sha256': VIEW_SHA, 'setter_va': hex(START), 'setter_size': END-START,
              'setter_sha256': hashlib.sha256(view.read(START, END-START)).hexdigest(),
              'harness_sha256': hashlib.sha256((ROOT / 'research/creative_setter_harness.c').read_bytes()).hexdigest(),
              'scope': 'Original setter, mocked backup writes and model execution; no ISP or camera validation',
              'flash_ready': False, 'log': run.stdout.splitlines()}
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
