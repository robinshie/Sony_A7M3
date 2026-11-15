#!/usr/bin/env python3
"""Verify each real JPEG against its own before/after source pixels.

This avoids conflating camera movement or ambient-light drift between shots
with the effect. JPEG Y is reconstructed from decoded RGB, so small rounding
and quantization differences are expected; no lossless JPEG claim is made.
"""
import argparse,hashlib,json,math,struct
from pathlib import Path
from PIL import Image
from capture_halation_fetch import decode,NB,NT,BORDER,TW,TH,tile
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def metrics(jpeg,reference):
 differences=[a-b for a,b in zip(jpeg,reference)]
 return dict(mae=sum(map(abs,differences))/len(differences),bias=sum(differences)/len(differences),rms=math.sqrt(sum(d*d for d in differences)/len(differences)))
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--bundle',type=Path,required=True);a=p.parse_args()
 b=a.bundle.resolve();proof=json.loads((b/'proof.json').read_text())
 runs=[r for r in proof['live'] if r['action']=='collect' and r['verified']]
 if proof['route']!='halation' or not runs:raise ValueError('Expected collected halation experiment')
 v=runs[-1]['values']
 if v[355]!=3 or v[357] or v[18] or v[5]!=1:raise ValueError('Three complete captures required')
 sample=json.loads((b/'halation-samples.json').read_text())
 if not sample['three_shot_test_passed'] or sha(b/'halation-samples.bin')!=sample['binary_sha256']:raise ValueError('Source sample evidence differs')
 raw=(b/'halation-samples.bin').read_bytes();decoded=decode(raw)
 if not all(r['verified'] for r in decoded):raise ValueError('Independent source oracle failed')
 version=struct.unpack_from('<I',raw,4)[0];header_size=44 if version==1 else 60;record_size=header_size+NB+2*NT
 files=sorted((b/'photos').glob('*.JPG'))
 if len(files)!=3:raise ValueError('Expected exactly three JPEGs in capture order')
 manifest=json.loads((b/'photos/manifest.json').read_text());exposures=[];results=[]
 for i,f in enumerate(files):
  meta=json.loads(f.with_suffix('.json').read_text())
  if sha(f)!=meta['sha256'] or meta['entry']!=manifest['photos'][i]:raise ValueError('Photo transfer identity differs')
  im=Image.open(f)
  if im.size!=(6000,4000):raise ValueError('Only verified JPEG L geometry')
  ex=im.getexif().get_ifd(0x8769);exposures.append([str(ex.get(k)) for k in (33434,33437,34855)])
  header=struct.unpack_from('<3Ii7I',raw,i*record_size);at=i*record_size+header_size
  before=tile(raw[at:at+NB])[1::2];after=raw[at+NB+NT:at+NB+2*NT][1::2]
  x,y=header[8]-80+BORDER,header[9]+BORDER
  jpeg=list(im.convert('YCbCr').getchannel(0).crop((x,y,x+TW,y+TH)).get_flattened_data())
  original_error,processed_error=metrics(jpeg,before),metrics(jpeg,after)
  delta=[a-b for a,b in zip(after,before)];mean_delta=sum(delta)/len(delta);strength=header[3]
  direction=mean_delta<-5 if strength<0 else mean_delta>5 if strength>0 else before==after
  target_dominates=processed_error['rms']*3<original_error['rms'] if strength else True
  # Small lossy-codec error is allowed, but an active effect must exceed five
  # levels and match the processed source at least three times better.
  passed=direction and target_dominates and processed_error['rms']<4
  results.append(dict(strength=strength,source_mean_delta=mean_delta,jpeg_vs_original=original_error,jpeg_vs_processed=processed_error,pixel_box=[x,y,x+TW,y+TH],direction_verified=bool(passed),source_reference_verified=decoded[i]['verified']))
 exposure_consistent=exposures[1:]==exposures[:-1]
 out=dict(passed=exposure_consistent and all(r['direction_verified'] for r in results),camera_capture_verified=True,
          results=results,exposures=exposures,exposure_consistent=exposure_consistent,dimensions=[6000,4000],
          scope='Each real JPEG compared with its own 32x16 source tile before and after processing. Full frame processed, but not every output pixel checked; lossy JPEG is not byte-identical.',
          source_sha256={str(Path(__file__).relative_to(ROOT)):sha(Path(__file__)),'research/capture_halation_fetch.py':sha(ROOT/'research/capture_halation_fetch.py')},
          artifact_sha256={str(f.relative_to(b)):sha(f) for f in files+[b/'halation-samples.bin',b/runs[-1]['report_file']]},
          algorithm_sha256=proof['source_sha256']['payloads/a7-film-frame.c'],kernel_sha256=proof['module_sha256'],firmware_written=False)
 (b/'jpeg-halation-proof.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
 if not out['passed']:raise ValueError('JPEG comparison did not pass')
if __name__=='__main__':main()
