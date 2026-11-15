#!/usr/bin/env python3
"""Exercise the in-place YUV stage and lease adapter; does not access USB."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '.lab/film-vignette'


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'proof.json').unlink(missing_ok=True)
    sources = ['payloads/a7-film-frame.c', 'payloads/a7-film-frame.h',
               'research/film_vignette_harness.c', 'research/film_vignette_test.py', 'ui/start.S',
               'payloads/a7-fl-runtime-prefs.h', 'payloads/a7-film-vignette.c', 'payloads/a7-film-vignette.h']
    common = ['-O2', '-Wall', '-Wextra', '-Werror', '-Wno-misleading-indentation',
              '-DA7_FL_FILM_CONTROLS', '-DA7_FL_DUAL_LOOK', '-DA7_FL_LEICA_LOOK',
              '-I', str(ROOT / 'payloads'), str(ROOT / sources[0]), str(ROOT / 'payloads/a7-film-vignette.c'), str(ROOT / sources[2])]
    subprocess.run(['clang', *common, '-fsanitize=address,undefined', '-o', str(OUT / 'host-test')], check=True)
    host = subprocess.run([str(OUT / 'host-test')], check=True, capture_output=True, timeout=90)
    (OUT / 'host.log').write_bytes(host.stdout + host.stderr)
    (OUT / 'guest.ld').write_text('''ENTRY(_start)
SECTIONS { . = 0x100000; .text : { *(.text.start) *(.text*) }
.rodata : { *(.rodata*) } .data : { *(.data*) }
.bss (NOLOAD) : { __bss_start = .; *(.bss*) *(COMMON) . = ALIGN(8); __bss_end = .; } }
''')
    subprocess.run(['arm-none-eabi-gcc', *common, '-mcpu=cortex-a9', '-mthumb', '-mno-unaligned-access',
                    '-DA7_TEXTURE_QEMU', '-ffreestanding', '-fno-builtin', '-nostdlib', '-T', str(OUT / 'guest.ld'),
                    str(ROOT / 'ui/start.S'), '-lgcc', '-o', str(OUT / 'frame.elf')], check=True)
    arm = subprocess.run(['qemu-system-arm', '-M', 'realview-pbx-a9', '-smp', '1', '-m', '64', '-nodefaults',
                          '-audio', 'none', '-nic', 'none', '-display', 'none', '-monitor', 'none', '-serial', 'stdio',
                          '-semihosting-config', 'enable=on,target=native', '-device',
                          f'loader,file={OUT}/frame.elf,cpu-num=0'], check=True, capture_output=True, timeout=90)
    (OUT / 'qemu.log').write_bytes(arm.stdout + arm.stderr)
    for result in (host, arm):
        print(result.stdout.decode(), end='')
        if b'VIGNETTE_PASSED' not in result.stdout or b'FAIL' in result.stdout + result.stderr:
            raise ValueError('Frame checks failed')
    if host.stdout != arm.stdout:
        raise ValueError('Host and ARM outputs differ')
    digest = lambda data: hashlib.sha256(data).hexdigest()
    proof = dict(source_sha256={p: digest((ROOT / p).read_bytes()) for p in sources},
                 host_log_sha256=digest(host.stdout + host.stderr), qemu_log_sha256=digest(arm.stdout + arm.stderr),
                 log=arm.stdout.decode().splitlines(),
                 passed=True, workspace_bytes_at_6000_pixels=42000,
                 native_producer_bound=False, camera_image_tested=False, flash_ready=False,
                 scope='Packed capture vignette: full/limited range, signed levels, padding, byte/word IO and scalar reference; no camera execution')
    (OUT / 'proof.json').write_text(json.dumps(proof, indent=2) + '\n')


if __name__ == '__main__':
    main()
