#!/usr/bin/env python3
"""Fetch frozen before/wanted/readback tiles after collecting the grain callback."""
import argparse,json,struct,subprocess
from pathlib import Path
from capture_source_fetch import SOURCE,sha,ROOT

def decode(data,full=False,seed=0x5a7f1203):
    if len(data)!=235040:raise ValueError('Incomplete grain sample')
    header=struct.unpack_from('<8I',data)
    if header!=(0x41374752,1,272,144,544,2944,1928,seed):raise ValueError('Unexpected grain sample identity')
    n=78336;before=data[32:32+n];wanted=data[32+n:32+2*n];actual=data[32+2*n:]
    def inside(i):return bool(i&1) and (full or (8<=i//544<136 and 8<=(i%544)//2<264))
    changed=[i for i,(a,b) in enumerate(zip(before,actual)) if a!=b]
    intended=[i for i,(a,b) in enumerate(zip(before,wanted)) if a!=b]
    return dict(changed_luma_bytes=len(changed),intended_changes=len(intended),
        forbidden_changes=sum(not inside(i) for i in changed),
        forbidden_intended_changes=sum(not inside(i) for i in intended),
        matches_wanted=actual==wanted,matches_original=actual==before,
        before_sha256=sha(before),wanted_sha256=sha(wanted),actual_sha256=sha(actual))

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--bundle',type=Path,required=True);a=p.parse_args()
    proof=json.loads((a.bundle/'proof.json').read_text())
    runs=[r for r in proof['live'] if r['action']=='collect' and r['verified']]
    banks=proof.get('route')=='banks'
    repeat=proof.get('route') in ('repeat','banks')
    fast=proof.get('route')=='fast'
    full=proof.get('route') in ('full','fast','repeat','banks')
    name='a7capbanks' if banks else 'a7caprepeat' if repeat else 'a7capfast' if fast else 'a7capfull' if full else 'a7capgrain'
    if proof.get('route') not in ('grain','full','fast','repeat','banks') or proof.get('module_name')!=name or not runs:raise ValueError('Collect and disarm this candidate first')
    values=runs[-1]['values']
    if values[5]!=1 or values[17]!=3 or values[344]!=3:raise ValueError('No completed grain attempt to fetch')
    src=SOURCE.replace('97988','235040').replace('/sys/module/a7capframe/sample','/sys/module/'+name+'/grain').replace('a7sf.bin','a7gr.bin')
    (a.bundle/'fetch-grain.c').write_text(src)
    subprocess.run(['arm-none-eabi-gcc','-mcpu=cortex-a9','-marm','-mfloat-abi=soft','-fPIC','-Os',
        '-ffreestanding','-fno-builtin','-nostdlib','-shared','-Wl,--no-undefined','-Wl,-z,noexecstack',
        '-Wall','-Wextra','-Werror','fetch-grain.c','-o','fetch-grain.so'],cwd=a.bundle,check=True)
    from camera import handoff,service
    def collect(camera,action):
        if action!='settings-snapshot':raise ValueError('Wrong action')
        f=service.Factory(camera)
        if f.contents('/version.txt')!=b'37114_13.2026020901' or bytes(camera.readBackup(0x3e0005))!=b'ILCE-7M3'+bytes(8):raise ValueError('Wrong camera')
        data=f.run((a.bundle/'fetch-grain.so').read_bytes(),'a7gr.bin');(a.bundle/'grain-sample.bin').write_bytes(data)
        result=decode(data,full,values[354] if repeat else 0x5a7f1203)
        result.update(binary_sha256=sha(data),trace_sha256=sha((a.bundle/runs[-1]['report_file']).read_bytes()),
            source_sha256=sha(Path(__file__).read_bytes()),payload_sha256=sha((a.bundle/'fetch-grain.so').read_bytes()),
            temporary_files_removed=True,firmware_written=False,jpeg_effect_verified=False)
        result['full_frame_requested']=full
        if repeat:result.update(selection=values[353],seed=values[354],completed_frames=values[355],failed_frames=values[357])
        result['verification_scope']='272x144 captured tile; not every pixel of the full frame'
        result['source_pixel_write_verified']=bool(values[310]==1 and values[345]==0 and values[349]==(24000000 if full else 32768) and not values[350] and
            result['matches_wanted'] and not result['forbidden_changes'] and not result['forbidden_intended_changes'] and
            result['changed_luma_bytes']==values[346]>0)
        (a.bundle/'grain-sample.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
    old,sw=service.perform,handoff.SWITCH;service.perform=collect;handoff.SWITCH+=' --host-identity-check'
    try:handoff.run('settings-snapshot')
    finally:service.perform=old;handoff.SWITCH=sw
if __name__=='__main__':main()
