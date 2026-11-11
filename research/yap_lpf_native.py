#!/usr/bin/env python3
"""Execute pinned YAP low-pass parameter code against guarded RAM, offline only.

This verifies parameter selection and register packing, not filter semantics,
supported hardware values, scheduling, live-view effects, or flash readiness.
Sony code and private settings are extracted only into the ignored lab folder.
"""
import argparse
import io
import json
from pathlib import Path
import struct
import subprocess
import sys

from gamma_avcam import BASE, SHA, sha

ROOT = Path(__file__).resolve().parents[1]
RANGES = {
    'calc_lpf': (0x3f872c, 0x3f87b8),
    'device_base': (0x706e08, 0x706e0c),
    'device_dirty': (0x70d88e, 0x70d894),
    'write_lpf_word': (0x70fa24, 0x70fa30),
    'write_lpf': (0x70fc20, 0x70fc3c),
    'maker_get': (0x7821ea, 0x782214),
    'maker_write_lpf': (0x3cbd28, 0x3cbd58),
    'maker_read_lpf': (0x3cc000, 0x3cc030),
}
TABLES = ((0x30032, 0x10557e6, 2560),
          (0x30033, 0x1058606, 5120),
          (0x30139, 0x1058606, 5120))


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--avcam', required=True, type=Path)
    cli.add_argument('--settings', type=Path)
    cli.add_argument('--pmca', type=Path)
    cli.add_argument('--out', type=Path, default=ROOT/'.lab/yap-lpf-native')
    args = cli.parse_args()
    data = args.avcam.read_bytes()
    if sha(data) != SHA:
        cli.error('Requires the pinned ILCE-7M3 4.04 AV-CAM image')
    if bool(args.settings) != bool(args.pmca):
        cli.error('--settings and --pmca must be supplied together')
    # Both backup-ID registries point to the same destination array. The large
    # table ID differs between registries; do not silently choose one on camera.
    for table, ids in ((0x1141964, (0x30032, 0x30033)),
                       (0x1141c18, (0x30032, 0x30139))):
        if struct.unpack_from('<2I', data, table+133*4) != ids:
            raise ValueError('Unexpected YAP backup registry')
    destinations = (BASE+0x10557e6, BASE+0x1058606)
    if struct.unpack_from('<2I', data, 0x1141ec8+133*4) != destinations:
        raise ValueError('Unexpected YAP backup destinations')
    got = 0x118d8b4
    if (struct.unpack_from('<I', data, got+0x10ac)[0],
        struct.unpack_from('<I', data, got+0x7918)[0]) != destinations:
        raise ValueError('Unexpected native table pointers')

    private = None
    private_tables = []
    if args.settings:
        sys.path.insert(0, str(args.pmca.resolve()))
        from pmca.backup import BackupFile
        raw = args.settings.read_bytes()
        backup = BackupFile(io.BytesIO(raw))
        if backup.revision != 4 or backup.size != len(raw):
            raise ValueError('Expected complete BK4 settings')
        private = {'settings_sha256': sha(raw), 'tables': []}
        for key, destination, size in TABLES:
            prop = backup.getProperty(key)
            if len(prop.data) != size or prop.attr != 8:
                raise ValueError('Unexpected YAP property layout')
            private['tables'].append(dict(id=hex(key), bytes=size,
                sha256=sha(prop.data), runtime_offset=hex(destination)))
            private_tables.append(bytes(prop.data))

    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True, mode=0o700)
    (out/'proof.json').unlink(missing_ok=True)
    header = ''
    for index, table in enumerate(private_tables):
        header += f'static const unsigned char private_table_{index}[]={{'+','.join(map(str,table))+'};\n'
    (out/'private-tables.h').write_text(header)
    asm = '.syntax unified\n'
    sections = []
    for name, (start, end) in RANGES.items():
        (out/(name+'.bin')).write_bytes(data[start:end])
        asm += f'.section .{name},"ax"\n.incbin "{name}.bin"\n'
        sections.append((BASE+start, name))
    asm += ('.section .log_stub,"ax"\n.thumb\n'
            'ldr ip,1f\nbx ip\n.balign 4\n1: .word native_log\n'
            '.section .note.GNU-stack,"",%progbits\n')
    sections.append((BASE+0x3a4bc0, 'log_stub'))
    asm += ('.section .tag_stub,"ax"\n.thumb\n'
            'ldr ip,1f\nbx ip\n.balign 4\n1: .word native_tag_lookup\n')
    sections.append((BASE+0x75fbe8, 'tag_stub'))
    (out/'native.S').write_text(asm)
    (out/'start.S').write_text('''.syntax unified
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
    ld = ('ENTRY(_start)\nSECTIONS {\n. = 0x40200000;\n'
          '.text : { *(.text.start) *(.text*) }\n'
          '.rodata : { *(.rodata*) }\n.data : { *(.data*) }\n'
          '.bss (NOLOAD) : { __bss_start = .; *(.bss*) *(COMMON) '
          '. = ALIGN(8); __bss_end = .; }\n')
    ld += ''.join(f'.{name} {address:#x} : {{ *(.{name}) }}\n'
                  for address, name in sorted(sections))
    (out/'guest.ld').write_text(ld+'}\n')
    subprocess.run(['arm-none-eabi-gcc', '-mcpu=cortex-a15', '-mthumb',
                    '-mno-unaligned-access', '-O2', '-Wall', '-Wextra', '-Werror',
                    '-ffreestanding', '-fno-builtin', '-nostdlib', '-T', 'guest.ld',
                    '-I', str(out), *(['-DA7YAP_PRIVATE'] if private else []),
                    'start.S', str(ROOT/'research/yap_lpf_harness.c'), 'native.S',
                    '-lgcc', '-o', 'yap-lpf.elf'], cwd=out, check=True)
    result = subprocess.run(['qemu-system-arm', '-M', 'virt', '-cpu', 'cortex-a15',
        '-smp', '1', '-m', '1024', '-nodefaults', '-audio', 'none', '-nic', 'none',
        '-display', 'none', '-monitor', 'none', '-serial', 'stdio',
        '-semihosting-config', 'enable=on,target=native', '-device',
        f'loader,file={out}/yap-lpf.elf,cpu-num=0'], capture_output=True, timeout=45)
    log = result.stdout+result.stderr
    (out/'qemu.log').write_bytes(log)
    print(log.decode(errors='replace'), end='')
    if result.returncode or b'YAP_LPF_NATIVE_PASSED' not in log or b'FAIL' in log:
        raise ValueError('YAP parameter fixture failed')
    sources = ('research/yap_lpf_native.py', 'research/yap_lpf_harness.c',
               'research/gamma_avcam.py')
    proof = dict(avcam_sha256=SHA, load_base=hex(BASE),
        native_ranges={k:dict(offset=hex(a), bytes=b-a, sha256=sha(data[a:b]))
                       for k, (a,b) in RANGES.items()},
        source_sha256={s:sha((ROOT/s).read_bytes()) for s in sources},
        elf_sha256=sha((out/'yap-lpf.elf').read_bytes()), qemu_log_sha256=sha(log),
        log=log.decode().splitlines(), private_backup=private,
        private_tables_executed=bool(private),
        scope='Original CalcLpf and LPF writer; table inputs and register aperture are guarded RAM',
        maker_note_scope='Original Tag2010 lookup and LPF record read/write with a synthetic tag provider',
        maker_note_offsets={'rawdev': '0x1364', 'vaplpf': '0x167d', 'haplpf': '0x167e'},
        hardware_value_range_known=False, filter_frequency_response_known=False,
        realtime_schedule_executed=False, camera_executed=False, flash_ready=False)
    (out/'proof.json').write_text(json.dumps(proof,indent=2)+'\n')


if __name__ == '__main__':
    main()
