"""Read existing mount and recipe files through the configured camera transport."""
import sys
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from camera import handoff,service
from local import BUILD_ID,LAB,require

def collect(camera,action):
    require(action=='settings-snapshot','Unexpected action')
    f=service.Factory(camera)
    require(f.contents('/version.txt')==BUILD_ID,'Firmware mismatch')
    require(bytes(camera.readBackup(0x3e0005))==b'ILCE-7M3'+bytes(8),'Model mismatch')
    out=LAB/'sd-mount-snapshot'/str(time.time_ns())
    out.mkdir(parents=True)
    for name,path,limit in (
        ('mounts','/proc/mounts',16384),
        ('fl0','/setting/A7FL0.CFG',160),
        ('fl1','/setting/A7FL1.CFG',160),
    ):
        data=f.contents(path,maximum=limit)
        (out/name).write_bytes(data)
        if name=='mounts':print(data.decode('ascii','replace'))
    print('READ_ONLY_EVIDENCE',out,flush=True)

if __name__=='__main__':
    service.perform=collect
    handoff.SWITCH+=' --host-identity-check'
    handoff.run('settings-snapshot')
