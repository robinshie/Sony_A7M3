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
EXPECTED='5fb33e6955b81e02144463e6fb7e09aaa042b3e4df536fd9523854a91d2fa6d5'
KERNEL='69213b30f04f6a9d97ae92cbc3d1b4e9da8c24a6192d84b1dc8435e468ca6277'

def sha(data):return hashlib.sha256(data).hexdigest()

def validate_acceptance(path,module):
    p=json.loads(path.read_text())
    if not (p.get('accepted') is True and p.get('edition')=='v0.01-six-looks' and
            p.get('module_sha256')==sha(module)==EXPECTED and len(module)==124980 and
            p.get('kernel_sha256')==KERNEL and p.get('resident_state')=='resident-ready' and
            p.get('diagnostic')==0 and p.get('runtime_fault')==0 and p.get('runtime_last_error')==0 and
            p.get('preference_schema')==6 and p.get('all_installed_files_verified') is True):
        raise ValueError('Accepted six-look device readback required')
    confirmation=p.get('user_confirmation',{})
    if not all(confirmation.get(k) is True for k in
               ('cold_boot_six_looks','fl4_fl5_fl6_shoot_playback','independent_parameters_survive_restart')):
        raise ValueError('Physical six-look acceptance is incomplete')
    if not p.get('runtime_matches_saved') and not (
            p.get('runtime_dirty')==1 and confirmation.get('unsaved_edits_after_acceptance') is True):
        raise ValueError('Unexplained runtime/saved mismatch')
    for key in ('artifact_sha256','inspection_source_sha256'):
        if not p.get(key):raise ValueError('Evidence identities required')
        for name,digest in p[key].items():
            target=(ROOT/name).resolve()
            boundary=ROOT/'.lab' if key=='artifact_sha256' else ROOT
            if not target.is_relative_to(boundary) or sha(target.read_bytes())!=digest:
                raise ValueError('Acceptance evidence changed: '+name)
    return p

def locale_delta(name):
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
    assert apply(before,p)==after
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
    for name in ('string_simplifiedchinese.uxc','string_english.uxc'):
        files['locales/'+name+'.json']=locale_delta(name)
    for name in ('edition-comparison.md','release-workflow.md','vignette.md','grain-research.md',
                 'fl3-film-controls.md','updater.md'):
        files['docs/'+name]=(ROOT/'docs'/name).read_bytes()
    source=subprocess.check_output(['git','archive','--format=zip','HEAD'],cwd=ROOT)
    with zipfile.ZipFile(io.BytesIO(source)) as archive:
        for name in archive.namelist():
            if not name.endswith('/'):files['source/'+name]=archive.read(name)
    files['release-manifest.json']=(json.dumps(dict(
        release='v0.01',edition='six-looks-integrated',source_commit=commit,
        looks=['FL','FL2','FL3','FL4 经典负片','FL5 经典纪实','FL6 自然人像'],
        preference_schema=6,module=dict(file='a7fl.so',size=len(module),sha256=EXPECTED),
        kernel_sha256=KERNEL,device_write_and_full_readback_verified=True,
        user_verified=acceptance['user_confirmation'],
        required_module_sha256='9fcaf13e5bcc5914d5721d797f16c3b059dc6f9b0cb99c94eda7632176306fe8',
        required_baseline='Accepted project r16 and existing loader; exact locale deltas included',
        complete_source_included=True,locale_deltas_included=True,universal_installer=False,
        spatial_effect_scope='Post-capture only, full-frame 3:2 JPEG L; not live view or RAW',
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
