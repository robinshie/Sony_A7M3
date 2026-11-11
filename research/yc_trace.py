#!/usr/bin/env python3
"""Build a bounded RAM metadata trace; no capture/ISP or firmware file writes.

Offline by default. --live --action install attaches a temporary import hook;
--live --action stop detaches and returns observations. The camera must remain
powered between those steps. A successful trace is not a pixel-buffer license:
ownership, compression/packing, mapping and synchronization still need proof.
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
from research.elf32 import ELF

PINS={
    'libObj.so':'1117453a969c9dedeb9bf6b006514fd9c2644a79085590a797189df109d64d23',
    'dataflowInfraFramework.so':'ad77c2ffd1497d919b401c0d8582eb5fad4c0cf807e109e1ec3fa87adc389780',
    'libmpr.so':'16b0260a33748838ba05fdb79e11392e7562052f79ed072123b1bf991bab966d',
}
SOURCES=('research/yc_trace.py','research/yc_trace_hook.S','research/yc_trace_hook_test.c',
         'research/yc_trace_probe.c','research/yc_trace_probe_test.c','payloads/a7-runtime-probe.c','ui/start.S')
GETTER='_ZN26C_DataflowInfra_StdData_YC22GetEntry_ImageSizeInfoEP35C_DataflowInfra_Entry_ImageSizeInfo'
PROFILES={
    'metadata':(0,'dataflowInfraFramework.so',GETTER,0x126ce20,0x22301,12),
    'jpeg':(1,'libmpr.so','_ZN5MprIf11EncodeStillEPNS_16EncodeStillParamE',0x126b17c,0x85ecbd,30),
    'write':(2,'libmpr.so','_ZN5MprIf10WriteStillEPNS_15WriteStillParamEPN3MPR9StillInfoEm',0x126cce0,0x85ed3b,48),
    'make':(2,'libmpr.so','_ZN5MprIf19MakeWriteStillImageEPNS_20WriteStillImageParamEPN3MPR9StillInfoE',0x126cec0,0x85ee15,56),
    'write_info':(3,'libmpr.so','_ZN5MprIf10WriteStillEPNS_15WriteStillParamEPN3MPR9StillInfoEm',0x126cce0,0x85ed3b,48),
    'make_info':(3,'libmpr.so','_ZN5MprIf19MakeWriteStillImageEPNS_20WriteStillImageParamEPN3MPR9StillInfoE',0x126cec0,0x85ee15,56),
}
def sha(data):return hashlib.sha256(data).hexdigest()
def require(ok,message):
    if not ok:raise ValueError(message)
def run(args,**kw):return subprocess.run(args,check=True,**kw)
def array(name,data):return f'static const unsigned char {name}[]={{'+','.join(map(str,data))+'};\n'

def build(usr,out,kind='metadata'):
    mode,target,symbol,expected_slot,expected_address,expected_size=PROFILES[kind]
    elves={n:ELF(usr/'lib'/n) for n in ('libObj.so',target)}
    for n,e in elves.items():require(sha(e.data)==PINS[n],f'Unexpected library: {n}')
    obj,flow=elves.values()
    slots=[a for a,(reloc,s) in obj.relocations.items() if reloc==22 and s['name']==symbol]
    original=flow.symbols[symbol]
    require(slots==[expected_slot] and original['value']==expected_address and original['size']==expected_size,'Unexpected import ABI')
    start=original['value']&~1
    relocations=[(a,reloc,s) for a,(reloc,s) in flow.relocations.items() if start<=a<start+expected_size]
    require(all(reloc==23 and (a-start)%4==0 and a+4<=start+expected_size for a,reloc,s in relocations),'Unsupported code relocation')
    out.mkdir(parents=True,exist_ok=True)
    (out/'hook.ld').write_text('ENTRY(a7yc_hook)\nSECTIONS { . = 0; .text : { *(.text*) } }\n')
    run(['arm-none-eabi-gcc','-mcpu=cortex-a9','-marm','-nostdlib','-T',str(out/'hook.ld'),
         str(ROOT/'research/yc_trace_hook.S'),'-o',str(out/'hook.elf')])
    run(['arm-none-eabi-objcopy','-O','binary','-j','.text',str(out/'hook.elf'),str(out/'hook.bin')])
    listing=run(['arm-none-eabi-nm','-n',str(out/'hook.elf')],capture_output=True,text=True).stdout
    symbols={line.split()[-1]:int(line.split()[0],16) for line in listing.splitlines() if len(line.split())==3}
    code=(out/'hook.bin').read_bytes();literal=symbols['a7yc_state']
    require(symbols['a7yc_hook']==0 and symbols['a7yc_hook_end']==len(code) and literal+4==len(code),'Hook layout changed')
    (out/'test.ld').write_text('''ENTRY(_start)
SECTIONS { . = 0x100000; .text : { *(.text.start) *(.text*) }
.rodata : { *(.rodata*) } .data : { *(.data*) }
.bss (NOLOAD) : { __bss_start = .; *(.bss*) *(COMMON) . = ALIGN(8); __bss_end = .; } }
''')
    run(['arm-none-eabi-gcc','-mcpu=cortex-a9','-mthumb','-mno-unaligned-access','-O2',
         '-ffreestanding','-fno-builtin','-nostdlib','-Wall','-Wextra','-Werror','-T',str(out/'test.ld'),
         str(ROOT/'ui/start.S'),str(ROOT/'research/yc_trace_hook.S'),
         str(ROOT/'research/yc_trace_hook_test.c'),'-lgcc','-o',str(out/'test.elf')])
    t=run(['qemu-system-arm','-M','realview-pbx-a9','-smp','1','-m','64','-nodefaults',
           '-audio','none','-nic','none','-display','none','-monitor','none','-serial','stdio',
           '-semihosting-config','enable=on,target=native','-device',f'loader,file={out}/test.elf,cpu-num=0'],
           capture_output=True,timeout=20)
    log=t.stdout+t.stderr;(out/'qemu.log').write_bytes(log);print(log.decode(),end='')
    require(b'YC_TRACE_HOOK_PASSED' in log and b'FAIL' not in log,'Hook test failed')
    require(obj.word(slots[0])==0xffc24 and obj.relocations[0x126c750][1]['name']=='dlsym','Unexpected lazy binding ABI')
    require(obj.read(0x104ae4,12).hex()=='11c68fe267ca8ce264fcbce5','Unexpected dlsym PLT')
    header=f'#define A7YC_SLOT {slots[0]}u\n#define A7YC_ORIGINAL {original["value"]&~1}u\n#define A7YC_STATE_LITERAL {literal}u\n'
    header+=f'#define A7YC_LAZY 0xffc24u\n#define A7YC_DLSYM 0x104ae4u\n#define A7YC_SYMBOL "{symbol}"\n'
    header+=f'#define A7YC_TARGET_PATH "/usr/lib/{target}"\n#define A7YC_KIND {mode}u\n'
    header+=array('object_header',obj.data[:64])+array('flow_header',flow.data[:64])
    header+=array('original_pin',flow.read(original['value']&~1,original['size']))+array('hook_code',code)
    header+=array('lazy_pin',obj.read(0xffc24,20))+array('dlsym_pin',obj.read(0x104ae4,12))
    header+=f'#define A7YC_RELOCATION_COUNT {len(relocations)}u\n'
    header+='static const unsigned target_relocations[]={'+(','.join(str(a-start) for a,_,_ in relocations) or '0')+'};\n'
    (out/'yc-trace-pins.h').write_text('#ifndef A7YC_PINS_H\n#define A7YC_PINS_H\n'+header+'#endif\n')
    run(['arm-none-eabi-gcc','-mcpu=cortex-a9','-marm','-mno-unaligned-access','-O2',
         '-ffreestanding','-fno-builtin','-nostdlib','-Wall','-Wextra','-Werror',
         '-Wno-misleading-indentation','-I',str(out),'-T',str(out/'test.ld'),
         str(ROOT/'ui/start.S'),str(ROOT/'research/yc_trace_probe_test.c'),
         '-lgcc','-o',str(out/'probe-test.elf')])
    t=run(['qemu-system-arm','-M','realview-pbx-a9','-smp','1','-m','64','-nodefaults',
           '-audio','none','-nic','none','-display','none','-monitor','none','-serial','stdio',
           '-semihosting-config','enable=on,target=native','-device',f'loader,file={out}/probe-test.elf,cpu-num=0'],
           capture_output=True,timeout=20)
    probe_log=t.stdout+t.stderr;(out/'probe-qemu.log').write_bytes(probe_log);print(probe_log.decode(),end='')
    require(b'YC_TRACE_PROBE_PASSED' in probe_log and b'FAIL' not in probe_log,'Import lifecycle test failed')
    for action,index in (('install',0),('read',1),('stop',2)):
        run(['arm-none-eabi-gcc','-mcpu=cortex-a9','-marm','-mfloat-abi=soft','-mno-unaligned-access',
             '-fPIC','-Os','-ffreestanding','-fno-builtin','-fno-unwind-tables','-fno-asynchronous-unwind-tables',
             '-nostdlib','-shared','-Wl,--no-undefined','-Wl,-z,noexecstack','-Wall','-Wextra',
             '-Wno-unused-function','-Wno-misleading-indentation','-I',str(ROOT/'payloads'),'-I',str(out),
             f'-DACTION={index}',str(ROOT/'research/yc_trace_probe.c'),'-lgcc','-o',str(out/f'{action}.so')])
    (out/'proof.json').write_text(json.dumps(dict(source_sha256={n:sha((ROOT/n).read_bytes()) for n in SOURCES},
        library_sha256={n:PINS[n] for n in elves},kind=kind,version=5,hook_sha256=sha(code),qemu_log_sha256=sha(log),
        probe_qemu_log_sha256=sha(probe_log),
        payload_sha256={a:sha((out/f'{a}.so').read_bytes()) for a in ('install','read','stop')},
        scope='Temporary bounded metadata import hook; no pixel writes or firmware replacement',
        camera_executed=False,capture_path_verified=False),indent=2)+'\n')

FIELDS={'attached':(0,1),'unit_type':(4,4),'unit_handle':(8,2),'unit_data_offset':(12,4),
        'record_width':(20,2),'record_height':(22,2),'canvas_width':(24,2),'canvas_height':(26,2),
        'valid_x':(28,2),'valid_y':(30,2),'valid_width':(32,2),'valid_height':(34,2),
        'target_x':(36,2),'target_y':(38,2),'target_width':(40,2),'target_height':(42,2),
        'data_site':(44,1),'aspect':(46,1),'yc_compress_enum':(47,1),'transfer_enum':(48,1),
        'placement_enum':(49,1),'content_enum':(50,1),'scan_enum':(51,1),'strip_width':(52,2),'bit_depth_enum':(54,1)}
def decode(raw):
    require(len(raw)==10344,'Unexpected report length')
    h=struct.unpack_from('<3Ii6I',raw)
    require(h[:2]==(0x41375950,5),'Unexpected report identity')
    state=struct.unpack_from('<16I',raw,40);rows=[]
    require(state[5]<=(2 if state[12]==3 else 127),'Unexpected trace count')
    def record(i):
        at=104+i*(4096 if state[12]==3 else 80);caller,result,kind,_=struct.unpack_from('<IiII',raw,at);entry=raw[at+16:at+16+(3400 if kind==3 else 64)]
        row={name:int.from_bytes(entry[o:o+n],'little') for name,(o,n) in FIELDS.items()} if kind==0 else {('region_words' if kind==1 else 'still_info_words' if kind==3 else 'parameter_words'):list(struct.unpack('<'+str(len(entry)//4)+'I',entry))}
        row.update(caller=hex(caller),object_relative_return=hex(caller-h[4]),result=result,kind=kind,raw=entry.hex());return row
    for i in range(state[5]):
        rows.append(record(i))
    return dict(status=h[3],action=h[2],object_base=hex(h[4]),target_base=hex(h[5]),
        code=hex(h[6]),state=hex(h[7]),slot=hex(h[8]),original=hex(h[9]),
        armed=state[4],count=state[5],dropped=state[6],records=rows,observed_calls=state[8],failures=state[9],last_error=state[10]-(1<<32) if state[10]>>31 else state[10],restore_slot=hex(state[13]),
        largest_area=state[11],kind=state[12],largest=record(127) if state[11] else None,
        pixel_buffer_exported=False,capture_path_verified=False,firmware_replaced=False)

def live(camera,out,action,kinds):
    from camera.service import Factory
    f=Factory(camera)
    require(f.contents('/version.txt')==b'37114_13.2026020901' and bytes(camera.readBackup(0x3e0005))==b'ILCE-7M3'+bytes(8),'Wrong model/build')
    names={'libObj.so',*(PROFILES[k][1] for k in kinds)}
    for name in sorted(names):
        require(sha(f.contents('/usr/lib/'+name,32*1024*1024))==PINS[name],'Unexpected installed '+name)
    if action=='install':
        # Validate every target before attaching either hook. Status -6 is
        # returned only after all identity/range/slot checks pass and the slot
        # still points to its original function; this read does not allocate.
        for kind in kinds:
            folder=out/kind;raw=f.run((folder/'read.so').read_bytes(),'a7yc.bin')
            (folder/'preflight.bin').write_bytes(raw);result=decode(raw)
            (folder/'preflight.json').write_text(json.dumps(result,indent=2)+'\n')
            require(result['status']==-6,'Target is not a verified original slot; no new hooks attached')
            print('YC_TRACE_PREFLIGHT',kind,'ORIGINAL_SLOT',flush=True)
    for kind in kinds:
        folder=out/kind;raw=f.run((folder/f'{action}.so').read_bytes(),'a7yc.bin')
        (folder/'live.bin').write_bytes(raw);result=decode(raw)
        (folder/'live.json').write_text(json.dumps(result,indent=2)+'\n')
        print('YC_TRACE',kind,json.dumps({k:v for k,v in result.items() if k not in ('records','largest')}),flush=True)
        require(result['status']==(2 if action=='stop' else 1),'Trace guard rejected operation; inspect saved report, no blind retry')

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--usr',required=True,type=Path)
    p.add_argument('--live',action='store_true');p.add_argument('--action',choices=('install','read','stop'),default='read')
    p.add_argument('--host-identity-check',action='store_true',help='Avoid a stuck MSC extended-info query; verify the exact model/build through maintenance before any payload instead')
    p.add_argument('--kind',choices=(*PROFILES,'both','capture','buffers'),default='metadata');a=p.parse_args()
    kinds={'both':('metadata','jpeg'),'capture':('write','make'),'buffers':('write_info','make_info')}.get(a.kind,(a.kind,))
    out=ROOT/'.lab/yc-trace'/str(time.time_ns())
    for kind in kinds:build(a.usr,out/kind,kind)
    if a.live:
        from camera import handoff,service
        service.perform=lambda cam,action:live(cam,out,a.action,kinds)
        previous=handoff.SWITCH
        if a.host_identity_check:handoff.SWITCH+=' --host-identity-check'
        try:handoff.run('settings-snapshot')
        finally:handoff.SWITCH=previous
    print('EVIDENCE',out)
if __name__=='__main__':main()
