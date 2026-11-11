"""Read and durably back up the Sony WBI header; no write operation is exposed."""
import argparse,json,os,time
from pathlib import Path
from local import BUILD_ID,LAB,ROOT,file_sha,require
from camera.native_install import pin_sources,save,save_json
from research.native_menu_wbi import decode

def profile(directory):
    directory=Path(directory);p=json.loads((directory/'proof.json').read_text())
    pin_sources(p)
    require(p['mode']==0 and not p['write_payload_built'] and p['report_bytes']==1112,'WBI payload is not read-only.')
    require(file_sha(directory/'probe.so')==p['payload_sha256'] and file_sha(directory/'qemu.log')==p['qemu_log_sha256'],'WBI payload/proof changed.')
    require(b'NWB_ARM_ALL_PASS' in (directory/'qemu.log').read_bytes(),'Missing ARM proof.')
    return p,(directory/'probe.so').read_bytes()

def capture(camera,evidence,probe=LAB/'native-wbi'):
    """Batchable within the parent's existing authenticated read-only session."""
    from camera.service import Factory
    p,payload=profile(probe);evidence=Path(evidence);evidence.mkdir(mode=0o700,parents=True,exist_ok=False)
    factory=Factory(camera)
    require(factory.contents('/version.txt')==BUILD_ID and bytes(camera.readBackup(0x3e0005))==b'ILCE-7M3'+bytes(8),'Camera model/build mismatch.')
    raw=factory.run(payload,'a7wbi.bin');save(evidence/'report.bin',raw)
    result=decode(raw);save_json(evidence/'report.json',result);save_json(evidence/'proof.json',p)
    if result['phase']>=2 and any(raw[56:88]):
        save(evidence/'header.bin',raw[88:600]);save(evidence/'neighbor.bin',raw[600:1112]);save(evidence/'preimage.bin',raw[88:1112])
    fd=os.open(evidence,os.O_RDONLY)
    try:os.fsync(fd)
    finally:os.close(fd)
    fd=os.open(evidence.parent,os.O_RDONLY)
    try:os.fsync(fd)
    finally:os.close(fd)
    require(result['mode']==0 and result['written']==0,'Unexpected writable report.')
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--offline',action='store_true');p.add_argument('--decode',type=Path);p.add_argument('--direct',action='store_true');a=p.parse_args()
    if a.decode:print(json.dumps(decode(a.decode.read_bytes()),indent=2));return
    proof,_=profile(LAB/'native-wbi')
    if a.offline:print(json.dumps(dict(readonly=True,camera_contacted=False,probe_sha256=proof['payload_sha256'])));return
    from camera import service,handoff
    evidence=LAB/'native-wbi'/f'read-{time.time_ns()}';previous=service.perform;result=None
    def perform(camera,action):
        nonlocal result
        require(action=='settings-snapshot','Unexpected transport action.');result=capture(camera,evidence)
    service.perform=perform
    try:
        if a.direct:
            import fcntl
            with (LAB/'.usb-transport.lock').open('a') as lock:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);service.connect('settings-snapshot')
        else:handoff.run('settings-snapshot')
    finally:service.perform=previous
    require(result is not None,'No WBI report.');print(json.dumps(result,indent=2));print('EVIDENCE '+str(evidence))
if __name__=='__main__':main()
