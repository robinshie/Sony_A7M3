#!/usr/bin/env python3
"""Compare grain-only kernels in owned camera memory, never real image buffers."""
import argparse,hashlib,json,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from research.film_frame_benchmark import decode

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live',action='store_true')
    args=parser.parse_args()
    out=ROOT/'.lab/grain-comparison'/str(time.time_ns())
    out.mkdir(parents=True)
    builds={}
    for mode in ('reference','optimized'):
        command=[sys.executable,str(ROOT/'research/film_frame_benchmark.py'),'--grain-only']
        if mode=='reference':command+=['--reference-grain']
        log=subprocess.check_output(command,cwd=ROOT,text=True)
        path=Path(next(line[9:] for line in log.splitlines() if line.startswith('EVIDENCE ')))
        proof=json.loads((path/'proof.json').read_text())
        builds[mode]=(path,proof)
    report=dict(camera_run=False,firmware_written=False,native_frame_bound=False,
                scope='Owned synthetic UYVY frames; no live-view/JPEG pixel access',
                builds={k:dict(path=str(p),proof_sha256=hashlib.sha256((p/'proof.json').read_bytes()).hexdigest()) for k,(p,d) in builds.items()})
    refs=[d['reference']['samples'] for p,d in builds.values()]
    for x,y in zip(*refs):
        assert all(x[k]==y[k] for k in x if k!='elapsed_us')
    if args.live:
        from camera import handoff,service
        def collect(camera,action):
            if action!='settings-snapshot':raise ValueError('Unexpected transport action')
            factory=service.Factory(camera)
            if factory.contents('/version.txt')!=b'37114_13.2026020901' or bytes(camera.readBackup(0x3e0005))!=b'ILCE-7M3'+bytes(8):
                raise ValueError('Camera identity differs')
            live={}
            for mode,(path,proof) in builds.items():
                blob=(path/'probe.so').read_bytes()
                if hashlib.sha256(blob).hexdigest()!=proof['probe_sha256']:raise ValueError('Benchmark changed')
                raw=factory.run(blob,'a7fb.bin')
                (out/(mode+'.bin')).write_bytes(raw)
                result=decode(raw)
                if result['stopped'] in (2,3) or not result['count']:raise ValueError('Invalid camera benchmark result')
                for sample,expected in zip(result['samples'],proof['reference']['samples']):
                    if any(sample[k]!=expected[k] for k in sample if k!='elapsed_us'):
                        raise ValueError('Camera kernel differs from host reference')
                result['temporary_files_removed']=True
                live[mode]=result
                (out/(mode+'.json')).write_text(json.dumps(result,indent=2)+'\n')
            rows=[]
            for before,after in zip(live['reference']['samples'],live['optimized']['samples']):
                if any(before[k]!=after[k] for k in before if k!='elapsed_us'):raise ValueError('Different kernel output')
                rows.append(dict(width=after['width'],height=after['height'],grain=after['grain'],
                                 reference_us=before['elapsed_us'],optimized_us=after['elapsed_us'],
                                 speedup=round(before['elapsed_us']/max(after['elapsed_us'],1),3)))
            report.update(camera_run=True,results=live,comparison=rows,
                          full_comparison=all(v['count']==12 for v in live.values()),
                          temporary_files_removed=True)
        previous,previous_switch=service.perform,handoff.SWITCH
        service.perform=collect
        handoff.SWITCH+=' --host-identity-check'
        try:handoff.run('settings-snapshot')
        finally:service.perform=previous;handoff.SWITCH=previous_switch
    sources=['research/grain_camera_benchmark.py','research/film_frame_benchmark.py',
             'research/film_frame_benchmark.c','payloads/a7-film-frame.c','payloads/a7-film-frame.h']
    report['source_sha256']={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in sources}
    (out/'proof.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    print('EVIDENCE',out)
if __name__=='__main__':main()
