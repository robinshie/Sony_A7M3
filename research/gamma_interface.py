#!/usr/bin/env python3
"""Reproduce the 4.04 extended-Gamma message ABI in isolated ARM/QEMU.

Requires the user's extracted firmware. No USB, camera writes, table creation
or real ISP emulation. Sony bytes remain in the ignored .lab directory.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from elf32 import ELF

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '.lab/gamma-interface'
SHA = '1117453a969c9dedeb9bf6b006514fd9c2644a79085590a797189df109d64d23'
START, END = 0xab69c4, 0xab6af0
STUBS = {0x105754: ('message_id', False), 0x10598c: ('get_param', False),
         0x102e34: ('get_value', False), 0xa8d390: ('log_error', True)}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--usr', required=True, type=Path)
    args = cli.parse_args()
    obj = ELF(args.usr / 'lib/libObj.so')
    if sha(obj.data) != SHA:
        cli.error('Unexpected libObj.so; this experiment is pinned to 4.04')
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'proof.json').unlink(missing_ok=True)
    native = obj.read(START, END - START)
    (OUT / 'marshaller.bin').write_bytes(native)
    assembly = '.syntax unified\n.section .native,"ax"\n.incbin "marshaller.bin"\n'
    sections = [(START, '.native')]
    # Preserve the original common dispatcher and its GOT. Only the 0x40f0
    # route is executed; no other routines, devices or message queues exist.
    got = next(s for s in obj.sections if s[3] <= 0x126ae58 < s[3] + s[5])
    if obj.word(0x126eabc) != START + 1:
        raise ValueError('Unexpected Gamma dispatch pointer')
    for address, size, name in ((0xaced80, 0xad0034 - 0xaced80, 'dispatch'),
                                (got[3], got[5], 'original_got')):
        (OUT / (name + '.bin')).write_bytes(obj.read(address, size))
        assembly += f'.section .{name},"ax"\n.incbin "{name}.bin"\n'
        sections.append((address, '.' + name))
    for address, (name, thumb) in STUBS.items():
        section = f'.stub_{address:x}'
        sections.append((address, section))
        assembly += f'.section {section},"ax"\n'
        assembly += f'.thumb\nb.w {name}\n' if thumb else f'.arm\nldr ip,[pc,#0]\nbx ip\n.word {name}\n'
    assembly += '.section .note.GNU-stack,"",%progbits\n'
    (OUT / 'native.S').write_text(assembly)
    script = 'ENTRY(_start)\nSECTIONS {\n. = 0x100000;\n'
    script += '.text : { *(.text.start) *(.text*) }\n.rodata : { *(.rodata*) }\n. = ALIGN(4096);\n'
    script += '.data : { *(.data*) }\n.bss (NOLOAD) : { __bss_start = .; *(.bss*) *(COMMON) . = ALIGN(8); __bss_end = .; }\n'
    script += ''.join(f'{name} {address:#x} : {{ *({name}) }}\n' for address, name in sorted(sections)) + '}\n'
    (OUT / 'guest.ld').write_text(script)
    subprocess.run(['arm-none-eabi-gcc', '-mcpu=cortex-a9', '-mthumb', '-mno-unaligned-access',
                    '-Os', '-Wall', '-Wextra', '-ffreestanding', '-fno-builtin', '-nostdlib',
                    '-T', 'guest.ld', str(ROOT / 'ui/start.S'),
                    str(ROOT / 'research/gamma_interface_harness.c'), 'native.S', '-lgcc',
                    '-o', 'gamma.elf'], cwd=OUT, check=True)
    r = subprocess.run(['qemu-system-arm', '-M', 'realview-pbx-a9', '-smp', '1', '-m', '64',
                        '-nodefaults', '-audio', 'none', '-nic', 'none', '-display', 'none',
                        '-monitor', 'none', '-serial', 'stdio', '-semihosting-config',
                        'enable=on,target=native', '-device', f'loader,file={OUT}/gamma.elf,cpu-num=0'],
                       capture_output=True, timeout=20, check=True)
    (OUT / 'qemu.log').write_bytes(r.stdout + r.stderr)
    print(r.stdout.decode(errors='replace'), end='')
    if b'QEMU_GAMMA_INTERFACE_PASSED' not in r.stdout or b'FAIL ' in r.stdout:
        raise ValueError('Original ARM marshaller failed the ABI experiment')
    sources = ('research/gamma_interface.py', 'research/gamma_interface_harness.c',
               'research/elf32.py', 'ui/start.S')
    proof = {'libobj_sha256': SHA, 'routine_va': hex(START), 'routine_bytes': END - START,
             'routine_sha256': sha(native), 'qemu_log_sha256': sha(r.stdout + r.stderr),
             'dispatch_va': '0xaced80', 'control_id': '0x40f0', 'got_pointer_va': '0x126eabc',
             'source_sha256': {p: sha((ROOT / p).read_bytes()) for p in sources},
             'scope': 'Original ARM control dispatch and message packing with mocked ObjMsg, Param and logging boundaries',
             'table_format_known': False, 'output_path_known': False, 'flash_ready': False,
             'log': r.stdout.decode().splitlines()}
    (OUT / 'proof.json').write_text(json.dumps(proof, indent=2) + '\n')


if __name__ == '__main__':
    main()
