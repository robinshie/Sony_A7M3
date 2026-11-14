#!/usr/bin/env python3
"""Read-only native DMM GetUnitInfo for an observed handle; never open a frame.

Offline by default. A historical handle may already be retired or reused: its
reply does not establish current frame identity or license pixel access.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import time
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from research.elf32 import ELF
from research.dmm_channel_test import PIN

SOURCE = ('research/dmm_unit_query.py', 'research/dmm_unit_query.c',
          'payloads/a7-dmm-channel.h', 'payloads/a7-dmm-channel.c', 'payloads/a7-runtime-probe.c')
FUNCTIONS = {
    'CTOR': ('_ZN17OBJAVBBCBASECLASS5DmmChC1Et', 0x35ba9, 112),
    'DTOR': ('_ZN17OBJAVBBCBASECLASS5DmmChD1Ev', 0x35b55, 64),
    'SEND': ('_ZN17OBJAVBBCBASECLASS15DataflowInfraCh17sndAsyncGlobalMsgEPvtjj', 0x33bdd, 236),
    'RECEIVE': ('_ZN17OBJAVBBCBASECLASS15DataflowInfraCh17rcvAsyncGlobalMsgEPvtjj', 0x33cc9, 192),
}
def sha(data): return hashlib.sha256(data).hexdigest()
def require(ok, message):
    if not ok: raise ValueError(message)
def array(name, data): return 'static const unsigned char '+name+'[]={'+','.join(map(str,data))+'};\n'

def build(usr, out, handle, resume):
    e = ELF(usr / 'lib/libBizFw.so')
    require(sha(e.data) == PIN, 'Unrecognized native library')
    # This executes the pinned original request producers in ARM QEMU and
    # covers ownership/timeout/error paths of the C channel we link below.
    subprocess.run([sys.executable, str(ROOT/'research/dmm_channel_test.py'),
                    '--library', str(usr/'lib/libBizFw.so')], check=True)
    out.mkdir(parents=True, exist_ok=True)
    header = f'#define QUERY_HANDLE {handle}u\n#define QUERY_RESUME {resume}u\n'
    header += array('library_header', e.data[:64])
    entries = []
    for key, (name, address, size) in FUNCTIONS.items():
        s = e.symbols[name]
        require((s['value'], s['size']) == (address, size), 'Native function ABI changed')
        start = address & ~1
        relocations = [(a-start,k) for a,(k,_) in e.relocations.items() if start<=a<start+size]
        require(all(k==23 and a%4==0 and a+4<=size for a,k in relocations), 'Unsupported code relocation')
        header += f'#define PIN_{key} {address}u\n'+array('bytes_'+key, e.read(start,size))
        header += 'static const unsigned reloc_'+key+'[]={'+(','.join(str(a) for a,_ in relocations) or '0')+'};\n'
        entries.append(f'{{{start}u,{size}u,{len(relocations)}u,bytes_{key},reloc_{key}}}')
    header += 'struct Pin {unsigned offset,size,count;const unsigned char *bytes;const unsigned *relocations;};\n'
    header += 'static const struct Pin pins[]={'+','.join(entries)+'};\n'
    (out/'dmm-query-pins.h').write_text(header)
    subprocess.run(['arm-none-eabi-gcc','-mcpu=cortex-a9','-marm','-mfloat-abi=soft','-mno-unaligned-access',
        '-fPIC','-fvisibility=hidden','-Os','-ffreestanding','-fno-builtin','-fno-unwind-tables','-fno-asynchronous-unwind-tables',
        '-nostdlib','-shared','-Wl,--no-undefined','-Wl,-z,noexecstack','-Wall','-Wextra','-Werror',
        '-Wno-unused-function','-Wno-misleading-indentation','-I',str(ROOT/'payloads'),'-I',str(out),
        str(ROOT/'research/dmm_unit_query.c'),str(ROOT/'payloads/a7-dmm-channel.c'),'-lgcc','-o',str(out/'query.so')],check=True)
    (out/'proof.json').write_text(json.dumps(dict(source_sha256={p:sha((ROOT/p).read_bytes()) for p in SOURCE},
        library_sha256=PIN, payload_sha256=sha((out/'query.so').read_bytes()), handle=handle,resume=hex(resume),
        channel_proof_sha256=sha((ROOT/'.lab/dmm-channel/proof.json').read_bytes()),
        camera_executed=False,firmware_replaced=False,pixel_io=False,scope=__doc__),indent=2)+'\n')

def decode(raw):
    require(len(raw)==212, 'Unexpected query report size')
    magic,version,base,address,retained,polls,status,disposal=struct.unpack_from('<6I2i',raw)
    require((magic,version)==(0x41374452,1), 'Unexpected query report identity')
    state=struct.unpack_from('<5I',raw,32); c=52
    obj=struct.unpack_from('<16I',raw,c)
    constructed,pending,held,poisoned,command,handle,transport,remote=struct.unpack_from('<6I2i',raw,c+80)
    return dict(status=status,base=hex(base),allocation=hex(address),retained=bool(retained) if address else None,polls=polls,disposal=disposal,
        state_magic=hex(state[0]),state_version=state[1],observed_handle=state[4],reply_queue=hex(obj[1]),
        constructed=constructed,pending=pending,held=held,poisoned=poisoned,command=hex(command),request_handle=handle,
        transport_error=transport,remote_status=remote,validated_reply=raw[c+112:c+136].hex(),
        observed_reply=raw[c+136:c+160].hex(),firmware_replaced=False,pixel_io=False,
        current_frame_identity_proven=False)

def live(camera,out):
    from camera.service import Factory
    f=Factory(camera)
    require(f.contents('/version.txt')==b'37114_13.2026020901' and bytes(camera.readBackup(0x3e0005))==b'ILCE-7M3'+bytes(8),'Wrong model/build')
    require(sha(f.contents('/usr/lib/libBizFw.so',2*1024*1024))==PIN,'Unexpected installed native library')
    raw=f.run((out/'query.so').read_bytes(),'a7dmm.bin');(out/'live.bin').write_bytes(raw)
    result=decode(raw);(out/'live.json').write_text(json.dumps(result,indent=2)+'\n');print('DMM_QUERY',json.dumps(result),flush=True)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--usr',required=True,type=Path);p.add_argument('--handle',required=True,type=lambda s:int(s,0))
    p.add_argument('--resume',default=0,type=lambda s:int(s,0));p.add_argument('--live',action='store_true')
    p.add_argument('--host-identity-check',action='store_true');a=p.parse_args()
    require(0<a.handle<65536 and 0<=a.resume<0xfffff001 and not a.resume%4096,'Invalid handle/allocation')
    out=ROOT/'.lab/dmm-query'/str(time.time_ns());build(a.usr,out,a.handle,a.resume)
    if a.live:
        from camera import handoff,service
        service.perform=lambda cam,action:live(cam,out)
        previous=handoff.SWITCH
        if a.host_identity_check:handoff.SWITCH+=' --host-identity-check'
        try:handoff.run('settings-snapshot')
        finally:handoff.SWITCH=previous
    print('EVIDENCE',out)
if __name__=='__main__':main()
