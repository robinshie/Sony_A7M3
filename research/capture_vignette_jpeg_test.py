#!/usr/bin/env python3
"""Compare each JPEG's four corners and center with its own sampled pixels."""
import argparse
import hashlib
import json
import math
from pathlib import Path
from PIL import Image
from capture_vignette_fetch import decode, POINTS

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def metrics(actual, reference):
    delta = [a-b for a, b in zip(actual, reference)]
    return dict(rms=math.sqrt(sum(d*d for d in delta)/len(delta)),
                bias=sum(delta)/len(delta), mae=sum(map(abs, delta))/len(delta))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bundle', type=Path, required=True)
    p.add_argument('--partial', action='store_true')
    a = p.parse_args()
    b = a.bundle.resolve()
    proof = json.loads((b/'proof.json').read_text())
    runs = [r for r in proof['live'] if r['action'] == 'collect' and r['verified']]
    if proof['route'] != 'vignette' or not runs:
        raise ValueError('Expected collected vignette experiment')
    v = runs[-1]['values']
    if v[5] != 1 or not 1 <= v[355] <= 3 or (not a.partial and (v[355] != 3 or v[357])):
        raise ValueError('Incomplete three-shot test')
    samples = decode((b/'vignette-samples.bin').read_bytes(), v[355])
    if not all(r['verified'] for r in samples):
        raise ValueError('Source sample verification failed')
    manifest = json.loads((b/'photos/manifest.json').read_text())
    files = sorted((b/'photos').glob('*.JPG'))
    if len(files) != 3 or len(manifest['photos']) != 3:
        raise ValueError('Expected three JPEGs in capture order')
    results, exposures = [], []
    for i, (f, sample) in enumerate(zip(files, samples)):
        meta = json.loads(f.with_suffix('.json').read_text())
        if sha(f) != meta['sha256'] or meta['entry'] != manifest['photos'][i]:
            raise ValueError('Photo transfer identity differs')
        im = Image.open(f)
        if im.size != (6000, 4000):
            raise ValueError('Only JPEG L 3:2 geometry is verified')
        ex = im.getexif().get_ifd(0x8769)
        exposures.append([str(ex.get(k)) for k in (33434, 33437, 34855)])
        yimage = im.convert('YCbCr').getchannel(0)
        before, after = bytes.fromhex(sample['before_hex']), bytes.fromhex(sample['after_hex'])
        patches, visible = [], 0
        for point, (x, y) in enumerate(POINTS):
            original = before[point*128:(point+1)*128][1::2]
            processed = after[point*128:(point+1)*128][1::2]
            actual = list(yimage.crop((x, y, x+8, y+8)).get_flattened_data())
            old, new = metrics(actual, original), metrics(actual, processed)
            delta = sum(a-b for a, b in zip(processed, original))/64
            active = point < 4 and abs(delta) > 5
            visible += active
            direction = delta <= 0 if sample['strength'] < 0 else delta >= 0
            passed = new['rms'] < 4 and direction and (not active or new['rms']*3 < old['rms'])
            if point == 4 or sample['strength'] == 0:
                passed &= original == processed
            patches.append(dict(point=point, pixel_box=[x, y, x+8, y+8],
                                source_mean_delta=delta, jpeg_vs_original=old,
                                jpeg_vs_processed=new, passed=bool(passed)))
        passed = all(p['passed'] for p in patches) and (not sample['strength'] or visible >= 2)
        results.append(dict(strength=sample['strength'], passed=bool(passed), patches=patches))
    exposure_consistent = len(exposures) == 3 and exposures[1:] == exposures[:-1]
    artifacts = files+[f.with_suffix('.json') for f in files]+[b/'photos/manifest.json', b/'vignette-samples.bin', b/runs[-1]['report_file']]
    out = dict(passed=not a.partial and not v[357] and exposure_consistent and all(r['passed'] for r in results),
               partial=a.partial, results=results, exposures=exposures, exposure_consistent=exposure_consistent,
               kernel_sha256=proof['module_sha256'], firmware_written=False,
               scope='Same-photo 8x8 samples at four corners and center, lossy JPEG luminance comparison; not every output pixel verified.',
               source_sha256={n:sha(ROOT/n) for n in ('research/capture_vignette_jpeg_test.py', 'research/capture_vignette_fetch.py', 'payloads/a7-film-vignette.c', 'payloads/a7-film-vignette.h')},
               artifact_sha256={str(f.relative_to(b)):sha(f) for f in artifacts})
    (b/('jpeg-vignette-partial.json' if a.partial else 'jpeg-vignette-proof.json')).write_text(json.dumps(out, indent=2)+'\n')
    print(json.dumps(out, indent=2))
    if not a.partial and not out['passed']:
        raise ValueError('JPEG vignette verification failed')


if __name__ == '__main__':
    main()
