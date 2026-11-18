#!/usr/bin/env python3
"""Package installed wet-plate firmware with explicit user/readback evidence boundaries."""
import argparse,base64,hashlib,io,json,subprocess,sys,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from apply_release_locales import apply
from camera.native_wet_release import require_wet_release
EXPECTED='ece2cf2c868ddb66cc3c18265abcdc398909e4796cc3c7836e63c47eac99ae31'
KERNEL='a5ef08615a085f3c33940ad0f5081a5910498e58534fe9dfcae27b4bfa8f54fa'
BASELINE='30474345352eaed6b1feb8f33e389278febaeb6c3fc493dc2355ab560ca591a4'
BASE=ROOT/'.lab/native-fl-releases/update-v001-wet-plate-6pocs7rl'
EVIDENCE=BASE/'write-1795004322417930000'
sha=lambda data:hashlib.sha256(data).hexdigest()

def validate_acceptance(path):
    user=json.loads(path.read_text())
    required=('physical_menu_verified_by_user','physical_jpeg_switch_verified_by_user','cold_boot_persistence_verified_by_user')
    if not all(user.get(k) is True for k in required) or user.get('installed_module_sha256')!=EXPECTED:
        raise ValueError('Explicit cold-boot/menu/JPEG user acceptance missing')
    if user.get('post_boot_readback_completed') is not False or user.get('readback_deferred_by_user') is not True:
        raise ValueError('Unexpected acceptance boundary; review before publishing')
    proof=json.loads((BASE/'27/module-proof.json').read_text());require_wet_release(proof)
    installed=json.loads((EVIDENCE/'verified.json').read_text());preserved=json.loads((EVIDENCE/'catalog-preserved.json').read_text())
    if not (installed['verified'] and installed['preferences_unchanged'] and installed['work_records_unchanged'] and preserved['verified'] and preserved['unchanged']):
        raise ValueError('Installation/configuration preservation proof missing')
    files={}
    for rev,name in ((27,'a7fl.so'),(2701,'string_simplifiedchinese.uxc'),(2702,'string_english.uxc')):
        m=json.loads((BASE/str(rev)/'manifest.json').read_text());data=(EVIDENCE/str(rev)/'new-module-readback.so').read_bytes()
        record=next(r for r in installed['files'] if r['new_sha256']==m['new']['sha256'])
        if not (record['verified'] and record['readonly_confirmed'] and record['view_unchanged'] and record['wbi_unchanged'] and len(data)==m['new']['size'] and sha(data)==m['new']['sha256'] and data==(BASE/str(rev)/'new-module.so').read_bytes()):
            raise ValueError('Installed artifact differs: '+name)
        files[name]=data
    if sha(files['a7fl.so'])!=EXPECTED or len(files['a7fl.so'])!=159528 or proof['kernel_sha256']!=KERNEL:
        raise ValueError('Wrong complete module')
    kernel=(Path(proof['kernel_bundle'])/'a7capwet.ko').read_bytes()
    if sha(kernel)!=KERNEL or kernel not in files['a7fl.so']:raise ValueError('Wrong embedded kernel')
    return files

def delta(name,before,after):
    changes=[];i=0
    while i<len(after):
        if i<len(before) and before[i]==after[i]:i+=1;continue
        start=i;i+=1
        while i<len(after) and (i>=len(before) or before[i]!=after[i]):i+=1
        changes.append(dict(offset=start,data=base64.b64encode(after[start:i]).decode()))
    patch=dict(file=name,before=dict(size=len(before),sha256=sha(before)),after=dict(size=len(after),sha256=sha(after)),changes=changes)
    if apply(before,patch)!=after:raise ValueError('Locale reconstruction failed')
    return (json.dumps(patch,indent=2)+'\n').encode()

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--acceptance',type=Path,required=True);p.add_argument('--out',type=Path);p.add_argument('--check',action='store_true');a=p.parse_args()
    verified=validate_acceptance(a.acceptance)
    if a.check:print('WET_RELEASE_EVIDENCE_VERIFIED');return
    if not a.out:p.error('--out is required')
    if subprocess.check_output(['git','status','--porcelain'],cwd=ROOT):raise ValueError('Commit intended source first')
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    files={'a7fl.so':verified['a7fl.so'],'先读我.md':(ROOT/'docs/wet-plate-release.md').read_bytes(),'tools/apply_release_locales.py':(ROOT/'tools/apply_release_locales.py').read_bytes()}
    for name in ('string_simplifiedchinese.uxc','string_english.uxc'):
        for path,baseline in [('locales/','native-fl-classic-strings'),('locales/from-previous/','native-fl-custom-strings')]:
            files[path+name+'.json']=delta(name,(ROOT/'.lab'/baseline/name).read_bytes(),verified[name])
    for path in sorted((ROOT/'recipes').rglob('*.a7look')):files[str(path.relative_to(ROOT))]=path.read_bytes()
    for name in ('wet-plate-release.md','wet-plate-jpeg.md','custom-look-release.md','look-recipes.md','edition-comparison.md','release-workflow.md','vignette.md','grain-research.md','fl3-film-controls.md','updater.md','jpeg-size-adaptation.md','images/classic-look-comparison.png'):
        files['docs/'+name]=(ROOT/'docs'/name).read_bytes()
    source=subprocess.check_output(['git','archive','--format=zip','HEAD'],cwd=ROOT)
    with zipfile.ZipFile(io.BytesIO(source)) as z:
        for name in z.namelist():
            if not name.endswith('/'):files['source/'+name]=z.read(name)
    manifest=dict(release='v0.01',edition='integrated-fl7-wet-plate',source_commit=commit,
        looks=['FL','FL2','FL3','FL4 经典负片','FL5 经典纪实','FL6 自然人像','FL7 湿版黑白'],
        module=dict(file='a7fl.so',size=len(files['a7fl.so']),sha256=EXPECTED),kernel_sha256=KERNEL,
        required_module_sha256=BASELINE,required_baseline='Existing project loader, exact 30474345 module and matching custom locales; this is not a stock 4.04 universal installer',
        preference_schema=6,custom_catalog_schema=3,compatible_catalog_schemas=[1,2,3],custom_look_limit=16,fl7_consumes_custom_slot=True,
        recipe_format='A7FL-LOOK/1',recipe_extension='.a7look',wet_recipe_field_supported=False,
        features=['FL7 independent high-contrast wet-plate B&W JPEG','independent default-off post-capture B&W switches on existing looks','six original color engines and controls','five-point curves','post-capture grain/signed halation/signed vignette','JPEG L/M/S geometry','SD independent look import','built-in and custom deletion','immediate list refresh','continuous selection','dynamic names','save confirmation/cancel/completion'],
        device_write_and_full_readback_verified=True,configuration_preserved_during_install=True,
        user_verified=dict(fl7_black_white_jpeg=True,existing_look_black_white_switch=True,cold_boot_persistence=True),
        post_boot_status_readback_verified=False,post_boot_status_readback='Deferred at user request after USB pipe error; no post-boot machine status claimed',
        capture_acceptance='Same embedded kernel: L/M/S source samples and real JPEG verified; complete persisted menu and switch/cold-boot behavior confirmed by user',
        spatial_effect_scope='Post-capture only, full-frame 3:2 JPEG L/M/S',verified_jpeg_output_sizes={'L':[6000,4000],'M':[3936,2624],'S':[3008,2000]},
        complete_source_included=True,locale_deltas_included=True,universal_installer=False,sharpness_range_clarity_image_effect_verified=False,brand_match_verified=False)
    files['release-manifest.json']=(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode()
    files['SHA256SUMS']=''.join(f'{sha(data)}  {name}\n' for name,data in sorted(files.items())).encode()
    if any('/.lab/' in n or n.endswith(('.CFG','.JPG','.dmg','.img')) for n in files):raise ValueError('Private data path in release')
    a.out.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(a.out,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name,data in sorted(files.items()):
            info=zipfile.ZipInfo('Sony_A7M3-v0.01/'+name,(2026,11,18,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16;z.writestr(info,data)
    with zipfile.ZipFile(a.out) as z:
        if z.testzip():raise ValueError('ZIP CRC failed')
        for name,data in files.items():
            if z.read('Sony_A7M3-v0.01/'+name)!=data:raise ValueError('ZIP content differs: '+name)
    print(json.dumps(dict(archive=str(a.out),bytes=a.out.stat().st_size,sha256=sha(a.out.read_bytes()),source_commit=commit),indent=2))
if __name__=='__main__':main()
