#!/usr/bin/env python3
"""Test original 4.04 3D LUT packing and register-write routines, offline only.

Create3DLUT executes with depth adjustments and SD conversion disabled. Hardware
registers are represented by guarded RAM. This does not emulate the Sony ISP.
"""
import argparse
import io
import json
import os
from pathlib import Path
import struct
import subprocess
import sys

from gamma_avcam import BASE, SHA, sha
from lut3d_format import packed_index, pack, unpack, BANK_COUNTS, BANK_REGISTERS

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '.lab/lut3d-native'
RANGES = {
    'pack': (0x522da8, 0x522dec),
    'create_copy': (0x5231fc, 0x523894),
    'permutation': (0x8a9658, 0x8a9982),
    'depth_reset': (0x7cd4de, 0x7cd4f0),
    'register_base': (0x706e08, 0x706e0c),
    'bank_copy': (0x70e8d4, 0x70e96c),
    'write_table': (0x70ea4c, 0x70eafe),
    'copy_trampoline': (0x7f41d0, 0x7f41d8),
    'sd_condition': (0x523194, 0x5231fc),
    'select_table': (0x523894, 0x523bb8),
    'two_plane_amount': (0x526978, 0x526a2c),
    'bit_getter': (0x7cbc9e, 0x7cbca6),
    'low_nibble': (0x7cd5ba, 0x7cd5c0),
}


def verify_format(data):
    original = struct.unpack_from('<405H', data, 0x8a9658)
    independently_derived = tuple(packed_index(a, b, c)
                                  for a in range(5) for b in range(9) for c in range(9))
    if sorted(original) != list(range(405)) or original != independently_derived:
        raise ValueError('Original permutation does not match the parity-bank model')
    # Exhaust every signed seven-bit component code across all node positions.
    for k in range(128):
        planes = [[(i * (p * 2 + 1) + k) % 128 - 64 for i in range(405)] for p in range(3)]
        if unpack(pack(planes)) != planes:
            raise ValueError('LUT format round-trip mismatch')
    for bad in (-65, 64, 0.5, True):
        planes = [[0] * 405 for _ in range(3)]
        planes[0][0] = bad
        try:
            pack(planes)
        except ValueError:
            pass
        else:
            raise ValueError('Out-of-range or noninteger code accepted')
    for bad in (b'', bytes(1619), bytes(1621), b'\x80' + bytes(1619), bytes(3) + b'\xff' + bytes(1616)):
        try:
            unpack(bad)
        except ValueError:
            pass
        else:
            raise ValueError('Invalid packed LUT accepted')


def main():
    os.umask(0o077)
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--avcam', required=True, type=Path)
    cli.add_argument('--settings', type=Path, help='Optional existing private BK4 snapshot; read only')
    cli.add_argument('--pmca', type=Path, help='Local PMCA source needed to read --settings')
    args = cli.parse_args()
    data = args.avcam.read_bytes()
    if sha(data) != SHA:
        cli.error('Requires the pinned ILCE-7M3 4.04 av-cam.bin')
    if bool(args.settings) != bool(args.pmca):
        cli.error('--settings and --pmca must be supplied together')
    # The two native backup-ID lists use the same indices for these four tables.
    backup_ids = (0x30004, 0x30005, 0x30006, 0x30007)
    for start in (0x1141964, 0x1141c18):
        if struct.unpack_from('<4I', data, start + 4*4) != backup_ids:
            raise ValueError('Backup-ID registry changed')
    destinations = (0x10c0235, 0x10c0769, 0x10c0e09, 0x10c1571)
    if struct.unpack_from('<4I', data, 0x1141ed8) != tuple(BASE+x for x in destinations):
        raise ValueError('Backup destination registry changed')
    fixture = bytes((i*37+i//1280*11)&255 for i in range(5120))
    backup_record = None
    if args.settings:
        sys.path.insert(0, str(args.pmca.resolve()))
        from pmca.backup import BackupFile
        raw = args.settings.read_bytes()
        backup = BackupFile(io.BytesIO(raw))
        if backup.revision != 4 or backup.size != len(raw):
            raise ValueError('Expected a complete checksum-verified BK4 snapshot')
        properties = [backup.getProperty(key) for key in backup_ids]
        if any(len(p.data) != 1280 for p in properties):
            raise ValueError('Unexpected LUT backup property length')
        fixture = b''.join(p.data for p in properties)
        backup_record = {'settings_sha256': sha(raw), 'properties': [
            {'id': hex(key), 'bytes': len(p.data), 'attributes': p.attr, 'sha256': sha(p.data),
             'runtime_destination_offset': hex(dst)}
            for key, p, dst in zip(backup_ids, properties, destinations)]}
    verify_format(data)
    OUT.mkdir(mode=0o700, parents=True, exist_ok=True)
    OUT.chmod(0o700)
    (OUT / 'proof.json').unlink(missing_ok=True)
    asm = '.syntax unified\n'
    sections = []
    (OUT / 'table_inputs.bin').write_bytes(fixture)
    asm += '.section .table_inputs,"a"\n.incbin "table_inputs.bin"\n'
    sections.append((0x40300000, 'table_inputs'))
    for name, (start, end) in RANGES.items():
        (OUT / (name + '.bin')).write_bytes(data[start:end])
        asm += f'.section .{name},"ax"\n.incbin "{name}.bin"\n'
        sections.append((BASE + start, name))
    for offset, target, arm in ((0x3a4bc0, 'native_log', False),
                                (0x50ca58, 'native_copy', True),
                                (0x50d13c, 'native_set', True)):
        name = f'stub_{offset:x}'
        asm += f'.section .{name},"ax"\n' + ('.arm\n' if arm else '.thumb\n')
        asm += f'ldr ip,1f\nbx ip\n.balign 4\n1: .word {target}\n'
        sections.append((BASE + offset, name))
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
    ld += ''.join(f'.{name} {address:#x} : {{ *(.{name}) }}\n' for address, name in sorted(sections))
    (OUT / 'guest.ld').write_text(ld + '}\n')
    subprocess.run(['arm-none-eabi-gcc', '-mcpu=cortex-a15', '-mthumb', '-Os', '-Wall',
                    '-Wextra', '-Werror', '-ffreestanding', '-fno-builtin', '-nostdlib',
                    '-T', 'guest.ld', 'start.S', str(ROOT / 'research/lut3d_harness.c'),
                    'native.S', '-lgcc', '-o', 'lut3d.elf'], cwd=OUT, check=True)
    result = subprocess.run(['qemu-system-arm', '-M', 'virt', '-cpu', 'cortex-a15', '-smp', '1',
                             '-m', '1024', '-nodefaults', '-audio', 'none', '-nic', 'none',
                             '-display', 'none', '-monitor', 'none', '-serial', 'stdio',
                             '-semihosting-config', 'enable=on,target=native', '-device',
                             f'loader,file={OUT}/lut3d.elf,cpu-num=0'],
                            capture_output=True, timeout=45)
    log = result.stdout + result.stderr
    (OUT / 'qemu.log').write_bytes(log)
    print(log.decode(errors='replace'), end='')
    if result.returncode or b'QEMU_NATIVE_3DLUT_PASSED' not in result.stdout or b'FAIL ' in log:
        raise ValueError('Native 3D LUT experiment failed')
    sources = ('research/lut3d_native.py', 'research/lut3d_format.py',
               'research/lut3d_harness.c', 'research/gamma_avcam.py')
    proof = {
        'avcam_sha256': SHA, 'load_base': hex(BASE),
        'native_ranges': {k: {'file_offset': hex(a), 'bytes': b-a, 'sha256': sha(data[a:b])}
                          for k, (a, b) in RANGES.items()},
        'source_sha256': {p: sha((ROOT/p).read_bytes()) for p in sources},
        'elf_sha256': sha((OUT/'lut3d.elf').read_bytes()), 'qemu_log_sha256': sha(log),
        'log': log.decode().splitlines(), 'logical_shape': [5, 9, 9],
        'input_bytes': {'three_planes': 1215, 'two_planes': 162}, 'packed_bytes': 1620,
        'bank_nodes': BANK_COUNTS, 'bank_register_offsets': [hex(x) for x in BANK_REGISTERS],
        'scope': 'Original pack/create/copy/writer; memcpy and memset mocked; logging trapped; register aperture is RAM',
        'pack_cases': 103680, 'table_cases': 180, 'selector_cases': 512, 'bank_copy_calls': 8,
        'table_input_sha256': sha(fixture), 'private_backup': backup_record,
        'depth_adjustment_tested': False, 'sd_conversion_tested': False,
        'storage_layout_verified': True, 'native_selection_executed': True,
        'selection_scope': 'All 256 selector byte values at levels 7 and 8; fixed zero mode/config and state=1; no scheduling',
        'color_space_and_units_known': False, 'hardware_interpolation_known': False,
        'jpeg_output_proven': False, 'camera_integration': False, 'flash_ready': False,
    }
    (OUT / 'proof.json').write_text(json.dumps(proof, indent=2) + '\n')


if __name__ == '__main__':
    main()
