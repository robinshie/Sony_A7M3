#!/usr/bin/env python3
"""Fault-test the five-point write-ahead coordinator; no camera access."""
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '.lab/film-worklog'


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'proof.json').unlink(missing_ok=True)
    sources = ['payloads/a7-fl-worklog.c', 'payloads/a7-fl-worklog.h',
               'payloads/a7-fl-runtime-prefs.c', 'payloads/a7-fl-runtime-prefs.h',
               'payloads/a7-fl-fivepoint.c', 'payloads/a7-fl-fivepoint.h',
               'payloads/a7-fl-store.h', 'payloads/a7-fl-runtime.h',
               'research/film_worklog_harness.c', 'research/film_worklog_test.py', 'ui/start.S',
               'payloads/a7-fl-store.c', 'payloads/a7-fl-fivepoint-preview.h','payloads/a7-fl-color.h']
    flags = ['-O2', '-Wall', '-Wextra', '-Werror', '-ffreestanding', '-fno-builtin',
             '-DA7_FL_FILM_CONTROLS', '-DA7_FL_LEICA_LOOK', '-I', str(ROOT / 'payloads')]
    code = [str(ROOT / sources[i]) for i in (0, 2, 4, 8, 11)]
    subprocess.run(['clang', *flags, '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
                    *code, '-o', str(OUT / 'host')], check=True)
    host = subprocess.run([str(OUT / 'host')], capture_output=True, timeout=60)
    (OUT / 'host.log').write_bytes(host.stdout + host.stderr)
    if host.returncode:
        print((host.stdout + host.stderr).decode(), end='')
        host.check_returncode()
    (OUT / 'guest.ld').write_text('''ENTRY(_start)
SECTIONS { . = 0x100000; .text : { *(.text.start) *(.text*) }
.rodata : { *(.rodata*) } .data : { *(.data*) }
.bss (NOLOAD) : { __bss_start = .; *(.bss*) *(COMMON) . = ALIGN(8); __bss_end = .; } }
''')
    subprocess.run(['arm-none-eabi-gcc', *flags, '-mcpu=cortex-a9', '-mthumb',
                    '-mno-unaligned-access', '-DA7_WORKLOG_QEMU', '-nostdlib',
                    '-T', str(OUT / 'guest.ld'), str(ROOT / 'ui/start.S'), *code,
                    '-lgcc', '-o', str(OUT / 'test.elf')], check=True)
    arm = subprocess.run(['qemu-system-arm', '-M', 'realview-pbx-a9', '-smp', '1', '-m', '64',
                          '-nodefaults', '-audio', 'none', '-nic', 'none', '-display', 'none',
                          '-monitor', 'none', '-serial', 'stdio', '-semihosting-config',
                          'enable=on,target=native', '-device', f'loader,file={OUT}/test.elf,cpu-num=0'],
                         capture_output=True, timeout=60, check=True)
    (OUT / 'qemu.log').write_bytes(arm.stdout + arm.stderr)
    for result in (host, arm):
        print(result.stdout.decode(), end='')
        if b'FILM_WORKLOG_PASSED' not in result.stdout or b'FAIL' in result.stdout + result.stderr:
            raise ValueError('Worklog test failed')
    if host.stdout != arm.stdout:
        raise ValueError('Host and ARM evidence differ')
    sha = lambda b: hashlib.sha256(b).hexdigest()
    (OUT / 'proof.json').write_text(json.dumps(dict(
        source_sha256={p: sha((ROOT / p).read_bytes()) for p in sources},
        host_log_sha256=sha(host.stdout + host.stderr), qemu_log_sha256=sha(arm.stdout + arm.stderr),
        log=host.stdout.decode().splitlines(), camera_written=False,
        resident_integrated=False, filesystem_durability_verified=False, flash_ready=False,
        scope='Five-point preview/Save/Cancel/reboot transaction coordinator, exact old/new table recognition; 127 torn writes and preimage guards. In-memory I/O only.'
    ), indent=2) + '\n')


if __name__ == '__main__':
    main()
