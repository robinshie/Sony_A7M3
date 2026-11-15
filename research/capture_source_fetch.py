#!/usr/bin/env python3
"""Read the already-disarmed in-call sample; no new callbacks or camera writes."""
import argparse,json,struct,sys,subprocess
from pathlib import Path
from kernel_probe import ROOT,sha
sys.path.insert(0,str(ROOT))
SOURCE=r'''
static unsigned char data[97988];
static long sc(long n,long a,long b,long c){
 register long r7 __asm__("r7")=n,r0 __asm__("r0")=a,r1 __asm__("r1")=b,r2 __asm__("r2")=c;
 __asm__ volatile("svc #0":"+r"(r0):"r"(r7),"r"(r1),"r"(r2):"memory","cc");return r0;
}
__attribute__((constructor)) static void run(void){
 long fd=sc(5,(long)"/sys/module/a7capframe/sample",0,0);if(fd<0)return;
 unsigned pos=0;
 while(pos<sizeof data){long n=sc(3,fd,(long)(data+pos),sizeof data-pos);if(n<=0)break;pos+=n;}
 long c=sc(6,fd,0,0);if(pos!=sizeof data||c)return;
 fd=sc(5,(long)"/tmp/jiritsu/a7sf.bin",1|64|128,0600);if(fd<0)return;
 pos=0;while(pos<sizeof data){long n=sc(4,fd,(long)(data+pos),sizeof data-pos);if(n<=0)break;pos+=n;}
 c=sc(6,fd,0,0);if(pos!=sizeof data||c)sc(10,(long)"/tmp/jiritsu/a7sf.bin",0,0);
}
'''
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--bundle',type=Path,required=True);a=p.parse_args()
    proof=json.loads((a.bundle/'proof.json').read_text())
    runs=[r for r in proof['live'] if r['action']=='collect' and r['verified']]
    if proof.get('route')!='frame' or proof.get('module_name')!='a7capframe' or not runs:raise ValueError('Collect and disarm the source callback first')
    v=runs[-1]['values']
    if (v[5],v[17],v[18],v[19])!=(1,3,0,64):raise ValueError('No complete successful source sample')
    (a.bundle/'fetch.c').write_text(SOURCE)
    subprocess.run(['arm-none-eabi-gcc','-mcpu=cortex-a9','-marm','-mfloat-abi=soft','-fPIC','-Os',
        '-ffreestanding','-fno-builtin','-nostdlib','-shared','-Wl,--no-undefined','-Wl,-z,noexecstack',
        '-Wall','-Wextra','-Werror','fetch.c','-o','fetch.so'],cwd=a.bundle,check=True)
    from camera import handoff,service
    def collect(camera,action):
        if action!='settings-snapshot':raise ValueError('Unexpected action')
        f=service.Factory(camera)
        if f.contents('/version.txt')!=b'37114_13.2026020901' or bytes(camera.readBackup(0x3e0005))!=b'ILCE-7M3'+bytes(8):raise ValueError('Wrong camera')
        data=f.run((a.bundle/'fetch.so').read_bytes(),'a7sf.bin');(a.bundle/'source-sample.bin').write_bytes(data)
        if len(data)!=97988:raise ValueError('Incomplete binary sysfs sample: '+str(len(data)))
        header=struct.unpack_from('<IIi5I',data)
        if header!=(0x4137534b,1,0,64,v[20],v[21],12160,128):raise ValueError('Sample identity differs from disarmed callback')
        if any(struct.unpack_from('<64i',data,452)):raise ValueError('Incomplete source reads')
        obj=struct.unpack_from('<100I',data,32);after=struct.unpack_from('<5I',data,432)
        if obj[47]&255!=1 or (obj[48],obj[49],obj[36],obj[37])!=(0x1a000000,0x3000000,0x0fa01770,0x0fa017c0):raise ValueError('Wrong captured source')
        if after[0]&255!=1 or tuple(after[1:])!=(0x1a000000,0x3000000,0x0fa01770,0x0fa017c0):raise ValueError('Source metadata changed while sampling')
        raw=data[708:];(a.bundle/'source-sample.raw').write_bytes(raw)
        result=dict(binary_sha256=sha(data),sample_sha256=sha(raw),trace_sha256=sha((a.bundle/runs[-1]['report_file']).read_bytes()),
            source_sha256=sha(Path(__file__).read_bytes()),payload_sha256=sha((a.bundle/'fetch.so').read_bytes()),temporary_files_removed=True,
            sample_in_call=True,frame_lease=False,pixel_format_verified=False,
            pixel_write=False,cache_sync_called=False,firmware_written=False,
            sampling=dict(source_stride=12160,row_indices=[(i//2)*128+i%2 for i in range(64)],sample_row_bytes=1520,byte_groups='keep bytes 0..3 of every 32-byte group'),
            metadata=[hex(x) for x in obj],after=[hex(x) for x in after])
        (a.bundle/'source-sample.json').write_text(json.dumps(result,indent=2)+'\n');print('SOURCE_SAMPLE_FETCHED',len(raw),flush=True)
    old,sw=service.perform,handoff.SWITCH;service.perform=collect;handoff.SWITCH+=' --host-identity-check'
    try:handoff.run('settings-snapshot')
    finally:service.perform=old;handoff.SWITCH=sw
if __name__=='__main__':main()
