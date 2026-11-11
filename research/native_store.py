#!/usr/bin/env python3
"""Test preference transactions and POSIX I/O locally; never connects to USB."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '.lab/native-store'
SOURCES = (
    'payloads/a7-fl-store.h', 'payloads/a7-fl-store.c',
    'payloads/a7-fl-posix.h', 'payloads/a7-fl-posix.c',
    'payloads/a7-fl-runtime-prefs.h', 'payloads/a7-fl-runtime-prefs.c',
    'research/native_store_test.c', 'research/native_posix_test.c',
    'research/native_store.py',
)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    proof = OUT / 'proof.json'
    proof.unlink(missing_ok=True)
    flags = ['-std=c11', '-Wall', '-Wextra', '-Werror', '-O1',
             '-fsanitize=address,undefined']
    cases = (
        ('store', [], ['research/native_store_test.c', 'payloads/a7-fl-store.c',
                       'payloads/a7-fl-runtime-prefs.c']),
        ('posix', ['-DA7_FL_POSIX_TEST'],
         ['research/native_posix_test.c', 'payloads/a7-fl-posix.c']),
    )
    logs = []
    for name, defines, sources in cases:
        executable = OUT / f'{name}-test'
        subprocess.run(['clang', *flags, *defines, *sources, '-o', str(executable)],
                       cwd=ROOT, check=True)
        result = subprocess.run([str(executable)], check=True, text=True,
                                capture_output=True, timeout=30)
        logs.append(result.stdout)
        print(result.stdout, end='')
    for name in ('store', 'posix'):
        subprocess.run(['arm-none-eabi-gcc', '-mcpu=cortex-a9', '-marm',
                        '-mfloat-abi=soft', '-mno-unaligned-access', '-Os', '-Wall', '-Wextra', '-Werror',
                        '-fPIC', '-ffreestanding', '-fno-builtin',
                        '-fno-unwind-tables', '-fno-asynchronous-unwind-tables',
                        '-c', f'payloads/a7-fl-{name}.c',
                        '-o', str(OUT / f'{name}-arm.o')], cwd=ROOT, check=True)
    (OUT / 'test.log').write_text(''.join(logs))
    proof.write_text(json.dumps({
        'source_sha256': {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest()
                          for p in SOURCES},
        'host_asan_ubsan': True, 'torn_write_boundaries': 127,
        'actual_host_filesystem_tested': True, 'arm_compile_verified': True,
        'camera_preference_io_tested': False, 'flash_ready': False,
        'limitations': ['ARM syscall numbers/layout compiled but not exercised on camera',
                        'Torn inactive records retain the prior setting but block future saves until recovery'],
    }, indent=2) + '\n')


if __name__ == '__main__':
    main()
