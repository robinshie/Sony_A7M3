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
EXPECTED='30474345352eaed6b1feb8f33e389278febaeb6c3fc493dc2355ab560ca591a4'
KERNEL='707362fc67da61b834757849fa056a2bb4c6d80a09f9469743e0a02e19f7bc0f'
BASELINE='a6545d1306c78872b2b28acecb3640d139cd6919a5818e5aa3de4ecb4870e927'
JPEG_SIZES={'L':[6000,4000],'M':[3936,2624],'S':[3008,2000]}

def sha(data):return hashlib.sha256(data).hexdigest()

def validate_acceptance(path,module):
    p=json.loads(path.read_text())
    if not (p.get('verified') is True and p.get('module_sha256')==sha(module)==EXPECTED and len(module)==155840
            and p.get('user_confirmed_immediate_list') is True and p.get('user_confirmed_continuous_selection') is True
            and p.get('original_banks_byte_identical') is True and p.get('status',[0,0,1])[:3]==[1,1,0]
            and p.get('status',[])[7]==0 and p.get('persistent_writes') is False):
        raise ValueError('Accepted live-list and continuous-selection device readback required')
    base=ROOT/'.lab/native-fl-releases/update-v001-live-list-zp6tdr0i'
    proof=json.loads((base/'26/module-proof.json').read_text())
    for name,digest in proof['source_sha256'].items():
        if sha((ROOT/name).read_bytes())!=digest:raise ValueError('Built module source changed: '+name)
    evidence=base/'write-1794824541467165000'
    verified=json.loads((evidence/'verified.json').read_text())
    preserved=json.loads((evidence/'catalog-preserved.json').read_text())
    if not (verified['verified'] and verified['work_records_unchanged'] and preserved['unchanged']
            and verified['files'][0]['new_sha256']==EXPECTED and verified['files'][0]['readonly_confirmed']
            and (evidence/'26/new-module-readback.so').read_bytes()==module):
        raise ValueError('Full installed-module readback/preservation missing')
    locales={}
    for name in ('string_simplifiedchinese.uxc','string_english.uxc'):
        data=(evidence/'26'/('required-'+name)).read_bytes()
        if data!=(ROOT/'.lab/native-fl-custom-strings'/name).read_bytes():raise ValueError('Locale readback mismatch')
        locales[name]=dict(size=len(data),sha256=sha(data))
    p['locales']=locales
    if not (p.get('hidden_builtin_mask')==14 and p.get('imported_bases')==[2,3,4] and p.get('catalog_generation')==14):
        raise ValueError('Persisted built-in deletions and imported banks required')
    p['user_confirmation']={'sd_file_import':True,'independent_look_name_dropdown_and_selected':True,
      'builtin_deletions_and_reimport_persisted':True,'import_visible_without_reboot':True,
      'continuous_unsaved_selection':True,'final_selection_saved':False}
    # Prior L/M/S acceptance applies to the unchanged embedded capture kernel;
    # do not claim this menu-only candidate was reshot at all sizes.
    kernel=ROOT/'.lab/capture-kernel/1794741362254373000'
    matches=[x for x in kernel.rglob('*') if x.is_file() and sha(x.read_bytes())==KERNEL]
    if not matches or matches[0].read_bytes() not in module:raise ValueError('Expected unchanged capture kernel missing')
    return p

def locale_delta(name,verified):
    before=(ROOT/'.lab/native-fl-classic-strings'/name).read_bytes()
    after=(ROOT/'.lab/native-fl-custom-strings'/name).read_bytes()
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
           '先读我.md':(ROOT/'docs/custom-look-release.md').read_bytes(),
           'tools/apply_release_locales.py':(ROOT/'tools/apply_release_locales.py').read_bytes()}
    for name,key in (('string_simplifiedchinese.uxc','string_simplifiedchinese.uxc'),('string_english.uxc','string_english.uxc')):
        files['locales/'+name+'.json']=locale_delta(name,acceptance['locales'][key])
    files['recipes/Portrait-grain-1.a7look']=(ROOT/'recipes/Portrait-grain-1.a7look').read_bytes()
    for path in sorted((ROOT/'recipes/defaults').glob('*.a7look')):
        files['recipes/defaults/'+path.name]=path.read_bytes()
    for name in ('custom-look-release.md','look-recipes.md','edition-comparison.md','release-workflow.md','vignette.md','grain-research.md',
                 'fl3-film-controls.md','updater.md','jpeg-size-adaptation.md','images/classic-look-comparison.png'):
        files['docs/'+name]=(ROOT/'docs'/name).read_bytes()
    source=subprocess.check_output(['git','archive','--format=zip','HEAD'],cwd=ROOT)
    with zipfile.ZipFile(io.BytesIO(source)) as archive:
        for name in archive.namelist():
            if not name.endswith('/'):files['source/'+name]=archive.read(name)
    files['release-manifest.json']=(json.dumps(dict(
        release='v0.01',edition='integrated-removable-looks-live-import',source_commit=commit,
        looks=['FL','FL2','FL3','FL4 经典负片','FL5 经典纪实','FL6 自然人像'],
        preference_schema=6,module=dict(file='a7fl.so',size=len(module),sha256=EXPECTED),
        kernel_sha256=KERNEL,device_write_and_full_readback_verified=True,
        user_verified=acceptance['user_confirmation'],
        required_module_sha256=BASELINE,
        required_baseline='Latest validated module-only transition: a6545d13, matching custom locales and project loader; earlier releases require matching staged migration, not a universal direct installer'
        ,custom_catalog_schema=2,compatible_catalog_schemas=[1,2],custom_look_limit=16,recipe_format='A7FL-LOOK/1',recipe_extension='.a7look',
        features=['built-in FL deletion','immediate imported list refresh','continuous unsaved look switching','SD file selection and confirmed import','independent custom looks','confirmed deletion','dynamic names in dropdown and selected row','original six banks preserved'],
        capture_acceptance='L/M/S verified on previous edition with the same embedded kernel; current acceptance covers menu/import/delete/name persistence',
        complete_source_included=True,locale_deltas_included=True,universal_installer=False,
        spatial_effect_scope='Post-capture only, full-frame 3:2 JPEG L/M/S',
        verified_jpeg_output_sizes=JPEG_SIZES,
        sharpness_range_clarity_image_effect_verified=False,brand_match_verified=False,
    ),ensure_ascii=False,indent=2)+'\n').encode()
    files['SHA256SUMS']=''.join(f'{sha(data)}  {name}\n' for name,data in sorted(files.items())).encode()
    args.out.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(args.out,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for name,data in sorted(files.items()):
            info=zipfile.ZipInfo('Sony_A7M3-v0.01/'+name,(2026,11,16,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16
            archive.writestr(info,data)
    with zipfile.ZipFile(args.out) as archive:
        assert archive.testzip() is None
        for name,data in files.items():assert archive.read('Sony_A7M3-v0.01/'+name)==data
    print(json.dumps(dict(archive=str(args.out),bytes=args.out.stat().st_size,
                         sha256=sha(args.out.read_bytes()),source_commit=commit),indent=2))

if __name__=='__main__':main()
