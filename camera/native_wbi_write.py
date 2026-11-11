"""Invalidate only a captured WBI header, with fresh guards and durable evidence."""
import argparse,hashlib,json,os,time
from pathlib import Path
from local import LAB,ROOT,file_sha,require
from camera.native_install import pin_sources,save,save_json
from camera.native_wbi import capture,profile
from research.native_menu_wbi import decode
def syncdir(p):
    fd=os.open(p,os.O_RDONLY)
    try:os.fsync(fd)
    finally:os.close(fd)
def verify(directory):
    d=Path(directory);m=json.loads((d/'manifest.json').read_text());pin_sources(m)
    require(m['version']==1,'Unknown binding version.');profile(LAB/'native-wbi')
    require(file_sha(LAB/'native-wbi/proof.json')==m['readonly_proof_sha256'],'Read-only proof changed.')
    for f,k in [('source-report.bin','source_report_sha256'),('preimage.bin','preimage_sha256'),('invalidate.so','payload_sha256'),('entry.c','entry_sha256'),('data.S','data_source_sha256')]:require(file_sha(d/f)==m[k],'Binding changed: '+f)
    pre=(d/'preimage.bin').read_bytes();r=decode((d/'source-report.bin').read_bytes())
    require(len(pre)==1024 and pre==(d/'source-report.bin').read_bytes()[88:] and r['status']==0 and r['phase']==3 and r['mode']==0 and not r['error'],'Binding report invalid.')
    require(hashlib.sha256(pre[:512]).hexdigest()==m['header_sha256'] and hashlib.sha256(pre[512:]).hexdigest()==m['neighbor_sha256'],'Binding sector digests differ.')
    return m,pre,(d/'invalidate.so').read_bytes()
def invalidate(camera,binding,evidence,write_device=False):
    require(write_device,'Explicit --write-device is required.');m,expected,payload=verify(binding)
    e=Path(evidence);e.mkdir(mode=0o700,parents=True,exist_ok=False);syncdir(e.parent)
    before=capture(camera,e/'preflight')
    require(before['status']==0 and before['phase']==3 and not before['error'] and (e/'preflight/preimage.bin').read_bytes()==expected,'Fresh same-session preimage differs; no WBI write sent.')
    save(e/'expected-1024.bin',expected);save_json(e/'binding.json',m)
    save_json(e/'write-intent.json',dict(operation='invalidate-WBI-header',path='/dev/nflasha5',offset=0,length=512,preimage_sha256=m['preimage_sha256'],pid=before['pid'],no_automatic_undo=True));syncdir(e);syncdir(e.parent)
    from camera.service import Factory
    raw=Factory(camera).run(payload,'a7wbi.bin');save(e/'write-report.bin',raw);result=decode(raw);save_json(e/'write-report.json',result);syncdir(e)
    require(result['status']==0 and result['phase']==100 and not result['error'] and result['mode']==1 and result['pid']==before['pid'] and result['written']==512 and result['fsync_ok']==1 and result['neighbor_ok']==1 and raw[88:]==expected,'WBI write did not fully verify; retained evidence, no automatic retry/undo.')
    after=capture(camera,e/'readback')
    require(after['status']==1 and after['mode']==0 and not after['written'] and (e/'readback/header.bin').read_bytes()==bytes(512) and (e/'readback/neighbor.bin').read_bytes()==expected[512:],'Independent zero-header/neighbor readback failed; no automatic retry/undo.')
    result={'operation':'invalidate-WBI-header','verified':True,'written_bytes':512,'neighbor_unchanged':True,'cold_boot_required':True,'original_header_sha256':m['header_sha256'],'evidence':str(e)}
    save_json(e/'verified.json',result);syncdir(e);return result
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--binding',type=Path,required=True);p.add_argument('--offline',action='store_true');p.add_argument('--write-device',action='store_true');p.add_argument('--direct',action='store_true');a=p.parse_args();m,_,_=verify(a.binding)
    if a.offline or not a.write_device:print(json.dumps(dict(local_binding_verified=True,camera_contacted=False,write_enabled=False,preimage_sha256=m['preimage_sha256'])));return
    from camera import service,handoff
    e=a.binding.resolve()/f'write-{time.time_ns()}';previous=service.perform;result=None
    def perform(camera,action):
        nonlocal result
        require(action=='settings-snapshot','Unexpected transport action.');result=invalidate(camera,a.binding,e,True)
    service.perform=perform
    try:
        if a.direct:
            import fcntl
            with (LAB/'.usb-transport.lock').open('a') as lock:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);service.connect('settings-snapshot')
        else:handoff.run('settings-snapshot')
    finally:service.perform=previous
    require(result is not None,'No WBI result.');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
