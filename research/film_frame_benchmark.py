#!/usr/bin/env python3
"""Benchmark grain/halation on owned synthetic memory; no image/firmware writes."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def decode(raw):
    if len(raw) != 400:
        raise ValueError('Unexpected benchmark report length')
    magic, version, count, stopped = struct.unpack_from('<4I', raw)
    if (magic, version) != (0x41374642, 1) or count > 12 or stopped > 3:
        raise ValueError('Unexpected benchmark report header')
    samples = []
    for i in range(count):
        row = struct.unpack_from('<4Ii3I', raw, 16 + 32 * i)
        samples.append(dict(zip(('width', 'height', 'grain', 'halation', 'rc',
                                 'elapsed_us', 'before', 'after'), row)))
    return dict(count=count, stopped=stopped, samples=samples,
                source='owned synthetic UYVY memory, not camera pixels',
                native_frame_bound=False, firmware_written=False)


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--live', action='store_true')
    cli.add_argument('--full-size', action='store_true',
                     help='Host only: 576, 960 and 6000 px widths using the approved 9/9 scale')
    args = cli.parse_args()
    if args.full_size and args.live:
        cli.error('The full-size benchmark cannot run on the camera')
    out = ROOT / '.lab/film-frame-benchmark' / str(time.time_ns())
    out.mkdir(parents=True)
    sources = ['research/film_frame_benchmark.c', 'payloads/a7-film-frame.c',
               'payloads/a7-film-frame.h', 'research/film_frame_benchmark.py']
    common = ['-O2', '-Wall', '-Wextra', '-Werror', '-Wno-misleading-indentation',
              '-I', str(ROOT / 'payloads'), *(str(ROOT / p) for p in sources[:2])]
    subprocess.run(['clang', *common, '-DA7_FILM_BENCH_HOST',
                    *(['-DA7_FILM_BENCH_FULL'] if args.full_size else []),
                    '-fsanitize=address,undefined', '-o', str(out / 'host')], check=True)
    raw = subprocess.run([str(out / 'host')], check=True, capture_output=True, timeout=30).stdout
    reference = decode(raw)
    if reference['count'] != 12 or reference['stopped']:
        raise ValueError('Incomplete host reference')
    for row in reference['samples']:
        if row['rc'] or (row['before'] == row['after']) != (not (row['grain'] or row['halation'])):
            raise ValueError('Synthetic effect or Off identity check failed')
    (out / 'host.bin').write_bytes(raw)
    digest = lambda b: hashlib.sha256(b).hexdigest()
    proof = dict(source_sha256={p: digest((ROOT / p).read_bytes()) for p in sources},
                 full_size_host_only=args.full_size,
                 reference=reference, camera_run=False, flash_ready=False)
    if not args.full_size:
        subprocess.run(['arm-none-eabi-gcc', *common, '-mcpu=cortex-a9', '-marm',
                        '-mfloat-abi=soft', '-mno-unaligned-access', '-fPIC',
                        '-fvisibility=hidden', '-ffreestanding', '-fno-builtin',
                        '-fno-unwind-tables', '-fno-asynchronous-unwind-tables',
                        '-nostdlib', '-shared', '-Wl,--no-undefined', '-Wl,-z,noexecstack',
                        '-lgcc', '-o', str(out / 'probe.so')], check=True)
        proof['probe_sha256'] = digest((out / 'probe.so').read_bytes())
    (out / 'proof.json').write_text(json.dumps(proof, indent=2) + '\n')
    if args.live:
        from camera import handoff, service

        def collect(camera, action):
            factory = service.Factory(camera)
            if (factory.contents('/version.txt') != b'37114_13.2026020901' or
                    bytes(camera.readBackup(0x3e0005)) != b'ILCE-7M3' + bytes(8)):
                raise ValueError('Wrong model/build; benchmark not run')
            live = factory.run((out / 'probe.so').read_bytes(), 'a7fb.bin')
            (out / 'live.bin').write_bytes(live)
            result = decode(live)
            if not result['count'] or result['stopped'] in (2, 3):
                raise ValueError('Camera benchmark failed; retain report')
            for i, row in enumerate(result['samples']):
                expected = reference['samples'][i]
                if any(row[k] != expected[k] for k in expected if k != 'elapsed_us'):
                    raise ValueError('Camera output does not match host kernel')
            result['host_pixels_match'] = True
            # Factory.run returns only after re-reading both temporary paths
            # and confirming they are absent.
            result['temporary_files_removed'] = True
            (out / 'live.json').write_text(json.dumps(result, indent=2) + '\n')
            proof.update(camera_run=True, live_sha256=digest(live),
                         temporary_files_removed=True,
                         live_result_sha256=digest((out / 'live.json').read_bytes()))
            (out / 'proof.json').write_text(json.dumps(proof, indent=2) + '\n')
            print(json.dumps(result, indent=2))

        service.perform = collect
        previous = handoff.SWITCH
        handoff.SWITCH += ' --host-identity-check'
        try:
            handoff.run('settings-snapshot')
        finally:
            handoff.SWITCH = previous
    print('EVIDENCE', out)


if __name__ == '__main__':
    main()
