#!/usr/bin/env python3
"""Encode and decode three 6000×4000 synthetic JPEGs using the host only."""
import csv
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parent = ROOT / '.lab' / 'halation-jpeg'
    parent.mkdir(parents=True, exist_ok=True)
    out = Path(tempfile.mkdtemp(prefix='proof-', dir=parent))
    flags = shlex.split(subprocess.check_output(['pkg-config', '--cflags', '--libs', 'libjpeg'], text=True))
    sources = ('research/halation_jpeg_harness.c', 'payloads/a7-film-frame.c')
    subprocess.run(['clang', '-O2', '-Wall', '-Wextra', '-Werror', '-fsanitize=address,undefined',
                    '-DA7_FL_FILM_CONTROLS', '-DA7_FL_LEICA_LOOK', '-I', str(ROOT / 'payloads'),
                    *(str(ROOT / p) for p in sources), *flags, '-o', str(out / 'jpeg-test')], check=True)
    log = subprocess.check_output([str(out / 'jpeg-test')], cwd=out, text=True, timeout=60)
    rows = log.splitlines()
    if len(rows) != 4 or not rows[-1].startswith('HALATION_JPEG_PASSED '):
        raise ValueError('Missing successful JPEG metrics')
    fields = ('strength', 'near_y', 'near_cb', 'near_cr', 'far_y', 'corner_y', 'core_y')
    samples = []
    for row, strength in zip(csv.reader(rows[:3]), (-9, 0, 9)):
        if len(row) != len(fields) or int(row[0]) != strength:
            raise ValueError('Unexpected JPEG metric format')
        samples.append(dict(zip(fields, map(int, row))))
    names = ('halation-minus9.jpg', 'halation-zero.jpg', 'halation-plus9.jpg')
    for name, sample in zip(names, samples):
        sample.update(file=name, sha256=digest(out / name))
    proof = dict(scope='Owned synthetic 6000x4000 full-range UYVY frame; host JPEG 4:2:2',
                 hardware_jpeg_verified=False, flash_ready=False, samples=samples,
                 source_sha256={p: digest(ROOT / p) for p in (*sources, 'payloads/a7-film-frame.h',
                                'payloads/a7-fl-runtime-prefs.h', 'research/halation_jpeg_test.py')})
    (out / 'proof.json').write_text(json.dumps(proof, indent=2) + '\n')
    print(log, end='')
    print(out)


if __name__ == '__main__':
    main()
