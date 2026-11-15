#!/usr/bin/env python3
"""Read kernel symbols and optionally pinned physical code/dispatch pointers.
No calls into kernel code, physical mappings, pixel writes or firmware writes.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--live',action='store_true')
    p.add_argument('--avcam',type=Path);p.add_argument('--kernel',type=Path);a=p.parse_args()
    if bool(a.avcam)!=bool(a.kernel):p.error('--avcam and --kernel must be supplied together')
    out=ROOT/'.lab/cache-symbols'/str(time.time_ns());out.mkdir(parents=True)
    src=ROOT/'research/cache_symbols_probe.c'
    digest=lambda b:hashlib.sha256(b).hexdigest()
    flags=[];pins={}
    if a.avcam:
        av,k=a.avcam.read_bytes(),a.kernel.read_bytes()
        if digest(av)!='e1b0f84e8323005a34b43de6dd0083fca712d2c654f0d9716512e0a54631bbe7' or digest(k)!='175df4fc47ddf51c1677cb71066e76552c62cfbe0df1ea5fe752589098a06f4d':raise ValueError('Wrong pinned AV-CAM/kernel')
        header=''
        for name,b in [('avcam_pin',av[0x1dc34:0x1dc48]),('kernel_pin',k[0x10470:0x10490])]:
            header+='static const unsigned char '+name+'[]={'+','.join(map(str,b))+'};\n'
        (out/'cache-route-pins.h').write_text(header)
        flags=['-DA7_CACHE_ROUTE','-I'+str(out)]
        pins=dict(avcam_sha256=digest(av),kernel_sha256=digest(k),header_sha256=digest(header.encode()))
    subprocess.run(['arm-none-eabi-gcc','-mcpu=cortex-a9','-marm','-mfloat-abi=soft','-fPIC','-Os',
        '-ffreestanding','-fno-builtin','-fno-unwind-tables','-fno-asynchronous-unwind-tables',
        '-nostdlib','-shared','-Wl,--no-undefined','-Wl,-z,noexecstack','-Wall','-Wextra','-Werror',
        *flags,str(src),'-o',str(out/'probe.so')],check=True)
    proof=dict(source_sha256={str(f.relative_to(ROOT)):digest(f.read_bytes()) for f in (src,Path(__file__))},
               payload_sha256=digest((out/'probe.so').read_bytes()),camera_run=False,
               physical_code_read_requested=bool(a.avcam),pins=pins,
               pixel_write=False,firmware_written=False)
    if a.live:
        from camera import handoff,service
        def collect(camera,action):
            if action!='settings-snapshot':raise ValueError('Unexpected action')
            f=service.Factory(camera)
            if f.contents('/version.txt')!=b'37114_13.2026020901' or bytes(camera.readBackup(0x3e0005))!=b'ILCE-7M3'+bytes(8):raise ValueError('Wrong model/build')
            raw=f.run((out/'probe.so').read_bytes(),'a7cs.bin');(out/'live.bin').write_bytes(raw)
            if len(raw)!=8264:raise ValueError('Wrong report size')
            magic,version,status,scanned,used,matches=struct.unpack_from('<6I',raw)
            if (magic,version)!=(0x41374353,2) or used>8192:raise ValueError('Wrong report identity')
            route=list(struct.unpack_from('<12I',raw,24))
            result=dict(status=status,scanned=scanned,used=used,matches=matches,
                        symbols=raw[72:72+used].decode('ascii'),temporary_files_removed=True,
                        route_status=route[0],root=hex(route[1]),table=hex(route[2]),physical_reads=route[3],
                        callbacks=[hex(x) for x in route[4:9]],kernel_bytes_match=bool(route[9]),avcam_bytes_match=bool(route[10]))
            (out/'live.json').write_text(json.dumps(result,indent=2)+'\n')
            proof.update(camera_run=True,result=result)
            print(json.dumps(result,indent=2))
        old,sw=service.perform,handoff.SWITCH;service.perform=collect;handoff.SWITCH+=' --host-identity-check'
        try:handoff.run('settings-snapshot')
        finally:service.perform=old;handoff.SWITCH=sw
    (out/'proof.json').write_text(json.dumps(proof,indent=2)+'\n');print('EVIDENCE',out)
if __name__=='__main__':main()
