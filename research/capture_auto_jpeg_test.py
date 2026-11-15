#!/usr/bin/env python3
"""Compare L/M/S JPEGs with samples from their own encoder-source frames.

Sony vertically resizes M/S after this hook. An area resampler predicts patch
luminance, allowing lossy JPEG/filter error; it is not a bit-exact OEM model.
"""
import argparse
import json
import math
from pathlib import Path
from PIL import Image
from capture_auto_fetch import decode
from capture_vignette_jpeg_test import sha, metrics, ROOT

SIZES = [[6000,4000],[3936,2624],[3008,2000]]


def project(pixels, source_y, source_h, output_h):
    """Use only destination rows whose entire source footprint was sampled."""
    scale = source_h/output_h
    first = math.ceil(source_y/scale)
    end = math.floor((source_y+8)/scale)
    values = []
    for row in range(first, end):
        lo, hi = row*scale-source_y, (row+1)*scale-source_y
        for x in range(8):
            total = 0.
            for y in range(max(0,math.floor(lo)), min(8,math.ceil(hi))):
                total += pixels[y*8+x]*max(0., min(hi,y+1)-max(lo,y))
            values.append(total/scale)
    if not values:
        raise ValueError('No complete sampled rows after scaling')
    return first, end, values


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bundle', type=Path, required=True)
    a = p.parse_args()
    b = a.bundle.resolve()
    proof = json.loads((b/'proof.json').read_text())
    runs = [r for r in proof['live'] if r['action']=='collect' and r['verified']]
    if proof['route']!='auto' or not runs or runs[-1]['values'][355]!=3 or runs[-1]['values'][357]:
        raise ValueError('Require collected three-shot auto-size experiment without failures')
    samples = decode((b/'auto-samples.bin').read_bytes())
    if not all(s['verified'] for s in samples) or [s['output_size'] for s in samples]!=SIZES:
        raise ValueError('Source pixels or L/M/S capture order differ')
    manifest = json.loads((b/'photos/manifest.json').read_text())
    files = sorted((b/'photos').glob('*.JPG'))
    if len(files)!=3 or len(manifest['photos'])!=3:
        raise ValueError('Expected three complete JPEG transfers')
    results = []
    for i,(f,sample) in enumerate(zip(files,samples)):
        meta = json.loads(f.with_suffix('.json').read_text())
        if sha(f)!=meta['sha256'] or meta['entry']!=manifest['photos'][i]:
            raise ValueError('Photo transfer identity differs')
        im = Image.open(f)
        if list(im.size)!=SIZES[i]:
            raise ValueError('JPEG size or capture order differs')
        im.load()
        yimage = im.convert('YCbCr').getchannel(0)
        before,film,after = [bytes.fromhex(sample[k+'_hex']) for k in ('before','film','after')]
        patches,visible = [],0
        for point,(x,y) in enumerate(sample['points']):
            def luminance(raw):
                return raw[point*128:(point+1)*128][1::2]
            first,end,original = project(luminance(before),y,sample['source_size'][1],im.height)
            _,_,pre_vig = project(luminance(film),y,sample['source_size'][1],im.height)
            _,_,processed = project(luminance(after),y,sample['source_size'][1],im.height)
            actual = list(yimage.crop((x,first,x+8,end)).get_flattened_data())
            old,new,mid = metrics(actual,original),metrics(actual,processed),metrics(actual,pre_vig)
            delta = sum(a-b for a,b in zip(processed,pre_vig))/len(processed)
            active = point<4 and delta < -5
            visible += active
            # Fixed thresholds declared before camera JPEGs are read. Source
            # oracle is exact; JPEG tolerances include OEM resize/compression.
            passed = abs(new['bias'])<6 and new['rms']<12 and (not active or new['rms']*2<mid['rms'])
            patches.append(dict(point=point,pixel_box=[x,first,x+8,end],
                vignette_source_mean_delta=delta,jpeg_vs_original=old,
                jpeg_vs_before_vignette=mid,jpeg_vs_processed=new,passed=bool(passed)))
        ex=im.getexif().get_ifd(0x8769)
        results.append(dict(size=list(im.size),source_size=sample['source_size'],
            source_stride=sample['stride'],source_offset=sample['offset'],
            exposure=[str(ex.get(k)) for k in (33434,33437,34855)],
            passed=all(p['passed'] for p in patches) and visible>=2 and sample['film_sample_changed'],patches=patches))
    artifacts=files+[f.with_suffix('.json') for f in files]+[b/'photos/manifest.json',b/'auto-samples.bin',b/runs[-1]['report_file']]
    out=dict(passed=all(r['passed'] for r in results),sizes_verified=True,results=results,
        kernel_sha256=proof['module_sha256'],firmware_written=False,
        scope='Same-photo four-corner and center luminance samples after grain, halation and vignette; exact source vignette oracle; approximate area model for OEM vertical resizing. Not every JPEG pixel or every effect strength verified.',
        source_sha256={n:sha(ROOT/n) for n in ('research/capture_auto_jpeg_test.py','research/capture_auto_fetch.py','research/capture_vignette_jpeg_test.py','payloads/a7-film-frame.c','payloads/a7-film-vignette.c')},
        artifact_sha256={str(f.relative_to(b)):sha(f) for f in artifacts})
    (b/'jpeg-auto-proof.json').write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps(out,indent=2))
    if not out['passed']:
        raise ValueError('Auto-size JPEG verification failed')


if __name__=='__main__':
    main()
