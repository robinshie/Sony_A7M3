#!/usr/bin/env python3
"""Build the accepted six-look v0.01 bundle, excluding private device data."""
import argparse
import base64
import hashlib
import io
import json
from pathlib import Path
import subprocess
import zipfile
from apply_release_locales import apply

ROOT=Path(__file__).resolve().parents[1]
EXPECTED='e5a530c3fe3790b829d3ee0cca7ff2628bf6a7a24f952c4f3cf46bcad8316feb'
KERNEL='707362fc67da61b834757849fa056a2bb4c6d80a09f9469743e0a02e19f7bc0f'
BASELINE='5fb33e6955b81e02144463e6fb7e09aaa042b3e4df536fd9523854a91d2fa6d5'
JPEG_SIZES={'L':[6000,4000],'M':[3936,2624],'S':[3008,2000]}

def sha(data):return hashlib.sha256(data).hexdigest()

def validate_acceptance(path,module):
    p=json.loads(path.read_text())
    if not (p.get('accepted') is True and p.get('edition')=='v0.01-six-looks-auto-size' and
            p.get('module_sha256')==sha(module)==EXPECTED and len(module)==126480 and
            p.get('kernel_sha256')==KERNEL and p.get('resident_state')=='resident-ready' and
            p.get('diagnostic')==0 and p.get('runtime_fault')==0 and p.get('runtime_last_error')==0 and
            p.get('preference_schema')==6 and p.get('all_installed_files_verified') is True):
        raise ValueError('Accepted auto-size device readback required')
    confirmation=p.get('user_confirmation',{})
    if not all(confirmation.get(k) is True for k in
               ('cold_boot_six_looks','jpeg_m_s_shoot_playback')):
        raise ValueError('Physical L/M/S acceptance is incomplete')
    capture=p.get('cold_boot_capture',{})
    if not (p.get('runtime_matches_saved') is True and p.get('kernel_matches_saved') is True and
            capture.get('kernel_sha256')==KERNEL and capture.get('armed') is True and
            capture.get('diagnostic')==0 and capture.get('completed',0)>=2 and capture.get('failed')==0):
        raise ValueError('Cold boot capture or saved settings not verified')
    jpeg_proofs=[]
    for key in ('artifact_sha256','inspection_source_sha256'):
        if not p.get(key):raise ValueError('Evidence identities required')
        for name,digest in p[key].items():
            target=(ROOT/name).resolve()
            boundary=ROOT/'.lab' if key=='artifact_sha256' else ROOT
            if not target.is_relative_to(boundary) or sha(target.read_bytes())!=digest:
                raise ValueError('Acceptance evidence changed: '+name)
            if key=='artifact_sha256' and target.name=='jpeg-auto-proof.json':
                jpeg_proofs.append(json.loads(target.read_text()))
    if len(jpeg_proofs)!=1:raise ValueError('Expected one L/M/S JPEG proof')
    jpeg=jpeg_proofs[0]
    if not (jpeg.get('passed') is True and jpeg.get('kernel_sha256')==KERNEL and
            [r['size'] for r in jpeg['results'] if r.get('passed') is True]==list(JPEG_SIZES.values())):
        raise ValueError('Same-kernel L/M/S JPEG proof required')
    return p

def locale_delta(name,verified):
    before=(ROOT/'.lab/native-fl-vignette-strings'/name).read_bytes()
    after=(ROOT/'.lab/native-fl-classic-strings'/name).read_bytes()
    changes=[];i=0
    while i<len(after):
        if i<len(before) and before[i]==after[i]:i+=1;continue
        start=i;i+=1
        while i<len(after) and (i>=len(before) or before[i]!=after[i]):i+=1
        changes.append(dict(offset=start,data=base64.b64encode(after[start:i]).decode()))
    p=dict(file=name,before=dict(size=len(before),sha256=sha(before)),
           after=dict(size=len(after),sha256=sha(after)),changes=changes)
    if p['after']!=verified or apply(before,p)!=after:
        raise ValueError('Locale delta differs from accepted resources: '+name)
    return (json.dumps(p,indent=2)+'\n').encode()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--module',type=Path,required=True)
    parser.add_argument('--acceptance',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    module=args.module.read_bytes();acceptance=validate_acceptance(args.acceptance,module)
    if subprocess.check_output(['git','status','--porcelain'],cwd=ROOT):
        raise ValueError('Commit intended sources first')
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    files={'a7fl.so':module,
           '先读我.md':(ROOT/'docs/six-look-release.md').read_bytes(),
           'tools/apply_release_locales.py':(ROOT/'tools/apply_release_locales.py').read_bytes()}
    for name,key in (('string_simplifiedchinese.uxc','1701'),('string_english.uxc','1702')):
        files['locales/'+name+'.json']=locale_delta(name,acceptance['installed_files'][key])
    for name in ('edition-comparison.md','release-workflow.md','vignette.md','grain-research.md',
                 'fl3-film-controls.md','updater.md','jpeg-size-adaptation.md','images/classic-look-comparison.png'):
        files['docs/'+name]=(ROOT/'docs'/name).read_bytes()
    source=subprocess.check_output(['git','archive','--format=zip','HEAD'],cwd=ROOT)
    with zipfile.ZipFile(io.BytesIO(source)) as archive:
        for name in archive.namelist():
            if not name.endswith('/'):files['source/'+name]=archive.read(name)
    files['release-manifest.json']=(json.dumps(dict(
        release='v0.01',edition='six-looks-integrated-auto-size',source_commit=commit,
        looks=['FL','FL2','FL3','FL4 经典负片','FL5 经典纪实','FL6 自然人像'],
        preference_schema=6,module=dict(file='a7fl.so',size=len(module),sha256=EXPECTED),
        kernel_sha256=KERNEL,device_write_and_full_readback_verified=True,
        user_verified=acceptance['user_confirmation'],
        required_module_sha256=BASELINE,
        required_baseline='Prior six-look build, installed matching locales, schema 6 and existing project loader',
        complete_source_included=True,locale_deltas_included=True,universal_installer=False,
        spatial_effect_scope='Post-capture only, full-frame 3:2 JPEG L/M/S',
        verified_jpeg_output_sizes=JPEG_SIZES,
        sharpness_range_clarity_image_effect_verified=False,brand_match_verified=False,
    ),ensure_ascii=False,indent=2)+'\n').encode()
    files['SHA256SUMS']=''.join(f'{sha(data)}  {name}\n' for name,data in sorted(files.items())).encode()
    args.out.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(args.out,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for name,data in sorted(files.items()):
            info=zipfile.ZipInfo('Sony_A7M3-v0.01/'+name,(2026,11,15,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16
            archive.writestr(info,data)
    with zipfile.ZipFile(args.out) as archive:
        assert archive.testzip() is None
        for name,data in files.items():assert archive.read('Sony_A7M3-v0.01/'+name)==data
    print(json.dumps(dict(archive=str(args.out),bytes=args.out.stat().st_size,
                         sha256=sha(args.out.read_bytes()),source_commit=commit),indent=2))

if __name__=='__main__':main()
