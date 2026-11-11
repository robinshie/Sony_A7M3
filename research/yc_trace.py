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
}
SOURCES=('research/yc_trace.py','research/yc_trace_hook.S','research/yc_trace_hook_test.c',
         'research/yc_trace_probe.c','payloads/a7-runtime-probe.c','ui/start.S')
GETTER='_ZN26C_DataflowInfra_StdData_YC22GetEntry_ImageSizeInfoEP35C_DataflowInfra_Entry_ImageSizeInfo'
def sha(data):return hashlib.sha256(data).hexdigest()
def require(ok,message):
    if not ok:raise ValueError(message)
def run(args,**kw):return subprocess.run(args,check=True,**kw)
def array(name,data):return f'static const unsigned char {name}[]={{'+','.join(map(str,data))+'};\n'

def build(usr,out):
    elves={n:ELF(usr/'lib'/n) for n in PINS}
    for n,e in elves.items():require(sha(e.data)==PINS[n],f'Unexpected library: {n}')
    obj,flow=elves.values()
    slots=[a for a,(kind,s) in obj.relocations.items() if kind==22 and s['name']==GETTER]
    original=flow.symbols[GETTER]
    require(slots==[0x126ce20] and original['value']==0x22301 and original['size']==12,'Unexpected getter ABI')
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
    header=f'#define A7YC_SLOT {slots[0]}u\n#define A7YC_ORIGINAL {original["value"]&~1}u\n#define A7YC_STATE_LITERAL {literal}u\n'
    header+=array('object_header',obj.data[:64])+array('flow_header',flow.data[:64])
    header+=array('original_pin',flow.read(original['value']&~1,original['size']))+array('hook_code',code)
    (out/'yc-trace-pins.h').write_text(header)
    for action,index in (('install',0),('read',1),('stop',2)):
        run(['arm-none-eabi-gcc','-mcpu=cortex-a9','-marm','-mfloat-abi=soft','-mno-unaligned-access',
             '-fPIC','-Os','-ffreestanding','-fno-builtin','-fno-unwind-tables','-fno-asynchronous-unwind-tables',
             '-nostdlib','-shared','-Wl,--no-undefined','-Wl,-z,noexecstack','-Wall','-Wextra',
             '-Wno-unused-function','-Wno-misleading-indentation','-I',str(ROOT/'payloads'),'-I',str(out),
             f'-DACTION={index}',str(ROOT/'research/yc_trace_probe.c'),'-lgcc','-o',str(out/f'{action}.so')])
    (out/'proof.json').write_text(json.dumps(dict(source_sha256={n:sha((ROOT/n).read_bytes()) for n in SOURCES},
        library_sha256=PINS,hook_sha256=sha(code),qemu_log_sha256=sha(log),
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
    require(len(raw)==8264,'Unexpected report length')
    h=struct.unpack_from('<3Ii6I',raw)
    require(h[:2]==(0x41375950,1),'Unexpected report identity')
    state=struct.unpack_from('<8I',raw,40);rows=[]
    require(state[5]<=128,'Unexpected trace count')
    for i in range(state[5]):
        at=72+i*64;caller=struct.unpack_from('<I',raw,at)[0];entry=raw[at+4:at+64]
        row={name:int.from_bytes(entry[o:o+n],'little') for name,(o,n) in FIELDS.items()}
        row.update(caller=hex(caller),object_relative_return=hex(caller-h[4]),raw=entry.hex());rows.append(row)
    return dict(status=h[3],action=h[2],object_base=hex(h[4]),flow_base=hex(h[5]),
        code=hex(h[6]),state=hex(h[7]),slot=hex(h[8]),original=hex(h[9]),
        armed=state[4],count=state[5],dropped=state[6],records=rows,
        pixel_buffer_exported=False,capture_path_verified=False,firmware_replaced=False)

def live(camera,out,action):
    from camera.service import Factory
    f=Factory(camera)
    require(f.contents('/version.txt')==b'37114_13.2026020901' and bytes(camera.readBackup(0x3e0005))==b'ILCE-7M3'+bytes(8),'Wrong model/build')
    for name,digest in PINS.items():
        require(sha(f.contents('/usr/lib/'+name,32*1024*1024))==digest,'Unexpected installed '+name)
    raw=f.run((out/f'{action}.so').read_bytes(),'a7yc.bin')
    (out/'live.bin').write_bytes(raw);result=decode(raw)
    (out/'live.json').write_text(json.dumps(result,indent=2)+'\n')
    print('YC_TRACE',json.dumps({k:v for k,v in result.items() if k!='records'}),flush=True)
    require(result['status']==(2 if action=='stop' else 1),'Trace guard rejected operation; inspect saved report, no blind retry')

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--usr',required=True,type=Path)
    p.add_argument('--live',action='store_true');p.add_argument('--action',choices=('install','read','stop'),default='read');a=p.parse_args()
    out=ROOT/'.lab/yc-trace'/str(time.time_ns());build(a.usr,out)
    if a.live:
        from camera import handoff,service
        service.perform=lambda cam,action:live(cam,out,a.action)
        handoff.run('settings-snapshot')
    print('EVIDENCE',out)
if __name__=='__main__':main()
