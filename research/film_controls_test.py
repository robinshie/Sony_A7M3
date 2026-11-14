#!/usr/bin/env python3
"""Verify schema-4 storage and native five-point LUT kernel, without USB."""
import hashlib
import argparse
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '.lab/film-controls'


def main():
    global OUT
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--legacy-records', nargs=2, type=Path, help='Optional two previously read camera preferences; offline only')
    options = cli.parse_args()
    if options.legacy_records:
        OUT = ROOT / '.lab/film-controls-private'
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'proof.json').unlink(missing_ok=True)
    sources = ['payloads/a7-fl-fivepoint.c', 'payloads/a7-fl-fivepoint.h',
               'payloads/a7-fl-runtime-prefs.c', 'payloads/a7-fl-runtime-prefs.h',
               'research/film_controls_harness.c', 'research/film_controls_test.py', 'ui/start.S']
    common = ['-O2', '-Wall', '-Wextra', '-Werror', '-DA7_FL_FILM_CONTROLS', '-DA7_FL_LEICA_LOOK',
              '-I', str(ROOT / 'payloads'), *[str(ROOT / sources[i]) for i in (0, 2, 4)]]
    private_hashes = []
    if options.legacy_records:
        data = [p.read_bytes() for p in options.legacy_records]
        if any(len(b) != 128 for b in data):
            cli.error('Expected complete 128-byte records')
        private_hashes = [hashlib.sha256(b).hexdigest() for b in data]
        (OUT / 'private-prefs.h').write_text('static const unsigned char private_preferences[2][128]={\n' +
            ',\n'.join('{' + ','.join(map(str, b)) + '}' for b in data) + '};\n')
        common += ['-DA7_FILM_PRIVATE_PREFS', '-I', str(OUT)]
    subprocess.run(['clang', *common, '-fsanitize=address,undefined', '-o', str(OUT / 'host-test')], check=True)
    host = subprocess.run([str(OUT / 'host-test')], capture_output=True, timeout=60)
    (OUT / 'host.log').write_bytes(host.stdout + host.stderr)
    if host.returncode:
        print(host.stdout.decode(), end=''); print(host.stderr.decode(), end=''); host.check_returncode()
    (OUT / 'guest.ld').write_text('''ENTRY(_start)
SECTIONS { . = 0x100000; .text : { *(.text.start) *(.text*) }
.rodata : { *(.rodata*) } .data : { *(.data*) }
.bss (NOLOAD) : { __bss_start = .; *(.bss*) *(COMMON) . = ALIGN(8); __bss_end = .; } }
''')
    subprocess.run(['arm-none-eabi-gcc', *common, '-mcpu=cortex-a9', '-mthumb', '-mno-unaligned-access',
                    '-DA7_FILM_QEMU', '-ffreestanding', '-fno-builtin', '-nostdlib', '-T', str(OUT / 'guest.ld'),
                    str(ROOT / 'ui/start.S'), '-lgcc', '-o', str(OUT / 'controls.elf')], check=True)
    arm = subprocess.run(['qemu-system-arm', '-M', 'realview-pbx-a9', '-smp', '1', '-m', '64', '-nodefaults',
                          '-audio', 'none', '-nic', 'none', '-display', 'none', '-monitor', 'none', '-serial', 'stdio',
                          '-semihosting-config', 'enable=on,target=native', '-device',
                          f'loader,file={OUT}/controls.elf,cpu-num=0'], check=True, capture_output=True, timeout=60)
    (OUT / 'qemu.log').write_bytes(arm.stdout + arm.stderr)
    for result in (host, arm):
        print(result.stdout.decode(), end='')
        if b'FILM_CONTROLS_PASSED' not in result.stdout or b'FAIL' in result.stdout + result.stderr:
            raise ValueError('Native film controls failed')
    if host.stdout != arm.stdout:
        raise ValueError('Host and ARM differ')
    # Exercise the existing actual two-slot coordinator in both legacy and film builds.
    stores = {}
    for film in (False, True):
        path = OUT / ('store-film' if film else 'store-legacy')
        subprocess.run(['clang', '-O2', '-Wall', '-Wextra', '-Werror', '-fsanitize=address,undefined',
                        '-DA7_FL_LEICA_LOOK', *(['-DA7_FL_FILM_CONTROLS'] if film else []),
                        str(ROOT / 'research/native_store_test.c'), str(ROOT / 'payloads/a7-fl-store.c'),
                        str(ROOT / 'payloads/a7-fl-runtime-prefs.c'), '-o', str(path)], check=True)
        log = subprocess.run([str(path)], capture_output=True, check=True, timeout=15)
        stores[str(film)] = log.stdout.decode(); print(log.stdout.decode(), end='')
    sources += ['research/native_store_test.c', 'payloads/a7-fl-store.c', 'payloads/a7-fl-store.h',
                'payloads/a7-fl-color.h', 'payloads/a7-fl-fivepoint-preview.h']
    sha = lambda b: hashlib.sha256(b).hexdigest()
    proof = dict(source_sha256={p: sha((ROOT / p).read_bytes()) for p in sources},
                 log=arm.stdout.decode().splitlines(), stores=stores,
                 host_log_sha256=sha(host.stdout + host.stderr), qemu_log_sha256=sha(arm.stdout + arm.stderr),
                 camera_written=False, menu_integrated=False, recovery_integrated=False, flash_ready=False,
                 private_preference_sha256=private_hashes,
                 scope='Schema-4 codec, old-record migration, five-point native LUT transform; no resident module build')
    (OUT / 'proof.json').write_text(json.dumps(proof, indent=2) + '\n')


if __name__ == '__main__':
    main()
