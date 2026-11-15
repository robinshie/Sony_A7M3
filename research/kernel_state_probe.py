#!/usr/bin/env python3
"""Read boot identity, capture probe presence and the JPEG marker instruction."""
import argparse,json,struct,subprocess,sys,time
from pathlib import Path
from kernel_probe import ROOT,sha
sys.path.insert(0,str(ROOT))
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--live',action='store_true');a=p.parse_args()
    out=ROOT/'.lab/kernel-state'/str(time.time_ns());out.mkdir(parents=True)
    src=ROOT/'research/kernel_state_probe.c'
    subprocess.run(['arm-none-eabi-gcc','-mcpu=cortex-a9','-marm','-mfloat-abi=soft','-fPIC','-Os',
        '-ffreestanding','-fno-builtin','-nostdlib','-shared','-Wl,--no-undefined','-Wl,-z,noexecstack',
        '-Wall','-Wextra','-Werror',str(src),'-o',str(out/'probe.so')],check=True)
    proof=dict(source_sha256=sha(src.read_bytes()),payload_sha256=sha((out/'probe.so').read_bytes()),camera_run=False,firmware_written=False)
    if a.live:
        from camera import handoff,service
        def collect(camera,action):
            if action!='settings-snapshot':raise ValueError('Unexpected action')
            f=service.Factory(camera)
            if f.contents('/version.txt')!=b'37114_13.2026020901' or bytes(camera.readBackup(0x3e0005))!=b'ILCE-7M3'+bytes(8):raise ValueError('Wrong model/build')
            raw=f.run((out/'probe.so').read_bytes(),'a7ks.bin');(out/'live.bin').write_bytes(raw)
            if len(raw)!=156:raise ValueError('Wrong report size')
            magic,version,opened,physical,uptime_n,boot_n,site=struct.unpack_from('<IIiiiiI',raw)
            if (magic,version)!=(0x41374b53,1) or not 0<uptime_n<64 or not 0<boot_n<64:raise ValueError('Invalid state report')
            result=dict(module_open=opened,physical_read=physical,site_word=hex(site),
                uptime=raw[28:28+uptime_n].decode().strip(),boot_id=raw[92:92+boot_n].decode().strip(),temporary_files_removed=True)
            proof.update(camera_run=True,result=result);print(json.dumps(result,indent=2))
        old,sw=service.perform,handoff.SWITCH;service.perform=collect;handoff.SWITCH+=' --host-identity-check'
        try:handoff.run('settings-snapshot')
        finally:service.perform=old;handoff.SWITCH=sw
    (out/'proof.json').write_text(json.dumps(proof,indent=2)+'\n');print('EVIDENCE',out)
if __name__=='__main__':main()
