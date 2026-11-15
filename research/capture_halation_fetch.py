#!/usr/bin/env python3
"""Fetch frozen three-shot samples and verify them with an independent oracle.

The oracle sums the original highlight mask using an integral image. It does
not call the production streaming filter. Passing proves the sampled source
pixels, not yet the saved JPEG or full-frame byte identity.
"""
import argparse
import ctypes
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import random

from capture_source_fetch import SOURCE, ROOT

W, H, BORDER, RADIUS = 368, 352, 168, 167
TW, TH = 32, 16
NB, NT = W * H * 2, TW * TH * 2
RECORD = 44 + NB + 2 * NT
TOTAL = 3 * RECORD


def tile(before):
    return b''.join(before[((BORDER+y)*W+BORDER)*2:
                          ((BORDER+y)*W+BORDER+TW)*2] for y in range(TH))


def oracle(before, strength):
    if len(before) != NB or strength not in (-9, 0, 9):
        raise ValueError('Wrong oracle dimensions/strength')
    wanted = bytearray(tile(before))
    if not strength:
        return bytes(wanted)
    pitch = W + 1
    integral = [0] * (pitch * (H + 1))
    for y in range(H):
        row_sum = 0
        for x in range(W):
            value = before[(y * W + x) * 2 + 1]
            row_sum += max(0, value - 200) * 255 // 55
            integral[(y+1)*pitch+x+1] = integral[y*pitch+x+1] + row_sum
    area = (2 * RADIUS + 1) ** 2
    clamp = lambda n: min(255, max(0, n))
    for y in range(TH):
        for x in range(0, TW, 2):
            glows = []
            for k in range(2):
                xx, yy = x + k + BORDER, y + BORDER
                x0, x1 = xx - RADIUS, xx + RADIUS + 1
                y0, y1 = yy - RADIUS, yy + RADIUS + 1
                total = (integral[y1*pitch+x1] - integral[y0*pitch+x1] -
                         integral[y1*pitch+x0] + integral[y0*pitch+x0])
                mean = (total + area // 2) // area
                at = (y*TW+x+k)*2+1
                mask = max(0, wanted[at] - 200) * 255 // 55
                glow = max(0, mean - mask) * abs(strength) // 24
                glows.append(glow)
                wanted[at] = clamp(wanted[at] + (glow//2 if strength > 0 else -(glow//2)))
            if strength > 0:
                glow = sum(glows) // 2
                at = (y*TW+x)*2
                wanted[at] = clamp(wanted[at] - glow * 13 // 64)
                wanted[at+2] = clamp(wanted[at+2] + glow * 21 // 64)
    return bytes(wanted)


def selftest():
    checks = 0
    for level in (0, 105, 250, 255):
        before = bytes((128, level)) * (W * H)
        for strength in (-9, 0, 9):
            assert oracle(before, strength) == tile(before)
            checks += 1
    before = b''.join(bytes((128, 105 if x < W//2 else 255)) for _ in range(H) for x in range(W))
    for strength in (-9, 0, 9):
        actual = oracle(before, strength)
        original = tile(before)
        for y in range(TH):
            for x in range(TW):
                # Closed-form number of bright columns in the full square.
                xx = x + BORDER
                columns = min(2*RADIUS+1, max(0, xx+RADIUS-W//2+1))
                mean = (255 * columns * (2*RADIUS+1) + (2*RADIUS+1)**2//2) // (2*RADIUS+1)**2
                mask = 0 if xx < W//2 else 255
                glow = max(0, mean-mask)*abs(strength)//24
                at = (y*TW+x)*2+1
                expected = original[at] + (glow//2 if strength >= 0 else -(glow//2))
                assert actual[at] == min(255, max(0, expected))
                if strength <= 0:
                    assert actual[at-1] == original[at-1]
                checks += 1
    out = ROOT / '.lab/capture-halation-oracle'
    out.mkdir(exist_ok=True)
    source = '''#include "a7-film-frame.h"
int check_frame(unsigned char *b,int strength){
 struct a7_film_frame f={.width=368,.height=352,.format=A7_FILM_UYVY,
 .range=A7_FILM_FULL,.path=A7_FILM_CAPTURE,.plane={{b,259072,736},{0}},.cookie=1,.sequence=1};
 struct a7_film_frame_params p={0,strength,167,0};
 unsigned ws[368*(167+6)/4];
 return a7_film_frame_apply(&f,&p,ws,sizeof ws);
}
'''
    (out/'check.c').write_text(source)
    subprocess.run(['clang', '-O2', '-Wall', '-Wextra', '-Werror', '-Wno-misleading-indentation',
                    '-dynamiclib', '-I'+str(ROOT/'payloads'), str(out/'check.c'),
                    str(ROOT/'payloads/a7-film-frame.c'), '-o', str(out/'check.dylib')], check=True)
    apply = ctypes.CDLL(str(out/'check.dylib')).check_frame
    apply.argtypes = [ctypes.c_void_p, ctypes.c_int]
    apply.restype = ctypes.c_int
    rng = random.Random(0xa7a80)
    for before in (before, bytes(rng.randrange(256) for _ in range(NB))):
        for strength in (-9, 0, 9):
            frame = ctypes.create_string_buffer(before, NB)
            assert apply(frame, strength) == 0
            assert oracle(before, strength) == tile(frame.raw)
            checks += 1
    proof = dict(passed=True, checks=checks, camera_run=False,
                 scope='Integral-image oracle against analytic fields and production streaming filter; all three strengths',
                 source_sha256={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                for p in (Path(__file__), ROOT/'payloads/a7-film-frame.c', ROOT/'payloads/a7-film-frame.h')})
    (out/'proof.json').write_text(json.dumps(proof, indent=2)+'\n')
    print('HALATION_ORACLE_PASSED', checks)


def decode(data, completed=3):
    if len(data)<8:
        raise ValueError('Incomplete sample header')
    version=struct.unpack_from('<I',data,4)[0]
    header_bytes=44 if version==1 else 60 if version==2 else 0
    record_size=header_bytes+NB+2*NT
    if not header_bytes or len(data) != 3*record_size:
        raise ValueError('Incomplete three-shot sample')
    results = []
    for index, strength in enumerate((-9, 0, 9)[:completed]):
        record = data[index*record_size:(index+1)*record_size]
        header = struct.unpack_from('<3Ii7I', record)
        if header[:8] != (0x4137484c, version, index, strength, W, H, BORDER, RADIUS):
            raise ValueError('Unexpected captured sample identity')
        x,y=header[8:10]
        if not (80<=x<=6080-W and not x%2 and 0<=y<=4000-H):
            raise ValueError('Sample lies outside verified active source')
        before = record[header_bytes:header_bytes+NB]
        wanted = record[header_bytes+NB:header_bytes+NB+NT]
        actual = record[header_bytes+NB+NT:]
        original, expected = tile(before), oracle(before, strength)
        changed = sum(a != b for a, b in zip(original, actual))
        luma = [b-a for a, b in zip(original[1::2], actual[1::2])]
        chroma_changed = sum(a != b for a, b in zip(original[::2], actual[::2]))
        result = dict(index=index, strength=strength, matches_oracle=actual == expected,
                      matches_on_camera_reference=actual == wanted,
                      changed_bytes=changed, changed_count_matches=changed == header[10],
                      chroma_changed=chroma_changed, luma_delta_min=min(luma),
                      luma_delta_max=max(luma), source_sha256=hashlib.sha256(before).hexdigest(),
                      actual_sha256=hashlib.sha256(actual).hexdigest())
        result['direction_valid'] = (max(luma) <= 0 and chroma_changed == 0 if strength < 0 else
                                     changed == 0 if strength == 0 else min(luma) >= 0)
        result['verified'] = all(result[k] for k in ('matches_oracle', 'matches_on_camera_reference',
                                                    'changed_count_matches', 'direction_valid'))
        result['visible_effect_in_sample'] = bool(changed)
        result.update(sample_x=x-80,sample_y=y,neighbourhood_luma_min=min(before[1::2]),
                      neighbourhood_luma_max=max(before[1::2]))
        if version==2:
            physical,virtual,cache_type,ticks=struct.unpack_from('<4I',record,44)
            result.update(physical=hex(physical),virtual_address=hex(virtual),cache_type=cache_type,
                          elapsed_ticks=ticks,elapsed_seconds=ticks/100.0)
            result['mapping_valid']=physical in (0x1a000000,0x24000000) and virtual==physical+0x60000000 and cache_type==0x12
            result['verified'] &= result['mapping_valid']
        results.append(result)
    return results


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--bundle', type=Path)
    cli.add_argument('--selftest', action='store_true')
    cli.add_argument('--partial', action='store_true', help='Recover completed samples after a stopped experiment; cannot certify all three shots')
    args = cli.parse_args()
    if args.selftest:
        selftest()
        return
    if not args.bundle:
        cli.error('--bundle is required')
    bundle = args.bundle.resolve()
    proof = json.loads((bundle / 'proof.json').read_text())
    runs = [r for r in proof['live'] if r['action'] == 'collect' and r['verified']]
    name=proof.get('module_name')
    if proof.get('route') != 'halation' or name not in ('a7caphalo','a7caphalo2','a7caphalo3') or not runs:
        raise ValueError('Collect and disarm this halation module first')
    values = runs[-1]['values']
    completed = values[355]
    if values[5] != 1 or not 1 <= completed <= 3:
        raise ValueError('No frozen successful samples')
    if not args.partial and (completed != 3 or values[357] or values[345] or values[310] != 1):
        raise ValueError('Three successful frames required before result validation')
    total=TOTAL if name=='a7caphalo' else TOTAL+3*16
    source = SOURCE.replace('97988', str(total)).replace('/sys/module/a7capframe/sample',
               '/sys/module/'+name+'/halation').replace('a7sf.bin', 'a7hf.bin')
    (bundle / 'fetch-halation.c').write_text(source)
    subprocess.run(['arm-none-eabi-gcc', '-mcpu=cortex-a9', '-marm', '-mfloat-abi=soft',
                    '-fPIC', '-Os', '-ffreestanding', '-fno-builtin', '-nostdlib', '-shared',
                    '-Wl,--no-undefined', '-Wl,-z,noexecstack', '-Wall', '-Wextra', '-Werror',
                    'fetch-halation.c', '-o', 'fetch-halation.so'], cwd=bundle, check=True)
    from camera import handoff, service
    def collect(camera, action):
        if action != 'settings-snapshot':
            raise ValueError('Unexpected action')
        f = service.Factory(camera)
        if (f.contents('/version.txt') != b'37114_13.2026020901' or
                bytes(camera.readBackup(0x3e0005)) != b'ILCE-7M3' + bytes(8)):
            raise ValueError('Wrong camera/build')
        raw = f.run((bundle / 'fetch-halation.so').read_bytes(), 'a7hf.bin')
        (bundle / 'halation-samples.bin').write_bytes(raw)
        results = decode(raw, completed)
        digest = lambda b: hashlib.sha256(b).hexdigest()
        summary = dict(frames=results, sampled_source_pixels_verified=all(r['verified'] for r in results),
                       three_shot_test_passed=completed==3 and not values[357] and all(r['verified'] for r in results),
                       completed_frames=completed, failed_frames=values[357], partial=args.partial,
                       scope='32x16 tile per frame with recorded coordinates, 368x352 original neighbourhood; not every output pixel',
                       binary_sha256=digest(raw), trace_sha256=digest((bundle/runs[-1]['report_file']).read_bytes()),
                       script_sha256=digest(Path(__file__).read_bytes()),
                       helper_sha256=digest((bundle/'fetch-halation.so').read_bytes()),
                       temporary_files_removed=True, firmware_written=False, jpeg_effect_verified=False)
        (bundle / 'halation-samples.json').write_text(json.dumps(summary, indent=2) + '\n')
        print(json.dumps(summary, indent=2), flush=True)
        if not summary['sampled_source_pixels_verified']:
            raise ValueError('Captured source verification failed')
    old, sw = service.perform, handoff.SWITCH
    service.perform = collect
    handoff.SWITCH += ' --host-identity-check'
    try:
        handoff.run('settings-snapshot')
    finally:
        service.perform, handoff.SWITCH = old, sw


if __name__ == '__main__':
    main()
