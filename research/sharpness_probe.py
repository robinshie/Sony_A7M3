#!/usr/bin/env python3
"""Temporary stock sharpness round trip; never replaces camera firmware.

Only --live opens USB. It checks the current installed r3 identity, saves a
complete private settings snapshot, builds exact-preimage probes, checks active
readback, and restores the original style and sharpness. An acknowledged setter
does NOT count as a successful change. Offline validation requires the user's
Sony firmware and the original-setter QEMU test.
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

VIEW_ORIGINAL='f561a1e5fa0d10d55727dd4a10ced97c9613b698a40b489ff9317634485e5129'
VIEW_INSTALLED='a1c4d8e88f54f71786ff53bc15a59c32a2969a6ffc934ef77728123d8af172a7'
MODULE='f3e2d657a83569f19ddafcd843a40601f1d953da0a20a8f8617c5e299e73a063'
MODEL_STYLES=(1,2,3,7,8,9,4,5,10,11,12,6,0,14)
CONTRAST_IDS=(0x1070735,0x1070736,0x107073a,0x107073b,0x107073c,0x107073d,
              0x107073e,0x107073f,0x1070740,0x1070741,0x1070737,0x1070738,0,0x1070739)
ACTIVE=(0x1070175,0x1070178,0x1070187,0x107018a)
BUILD=b'37114_13.2026020901'

def sha(b): return hashlib.sha256(b).hexdigest()
def require(ok,message):
    if not ok: raise ValueError(message)
def signed(value): return value if value<128 else value-256
def array(name,data): return f'static const unsigned char {name}[]={{'+','.join(map(str,data))+'};\n'
def construct(usr,out,guards,target,model_only=False):
    view=ELF(usr/'lib/viewUnified2.so');backup=ELF(usr/'lib/libbackup.so')
    require(sha(view.data)==VIEW_ORIGINAL,'Unexpected original view library')
    require(sha(backup.data)=='b6420f8f7cacade524e1ba7c5b0d8b06691c22ed793dca084fdf1c1d9ae092f3','Unexpected backup library')
    current=[guards[k] for k in ACTIVE];style=MODEL_STYLES.index(current[0])
    require(style!=12,'Unsupported native style')
    slot=guards[0x1070762];box=0 if slot==255 else slot+1
    require(0<=box<=6,'Invalid native slot')
    c,s=map(signed,current[1:3])
    require(all(-3<=v<=3 for v in (c,s,target,signed(current[3]))),'Invalid stock parameters')
    h=array('setter_pin',view.read(0x420d18,0x298))+array('size_pin',backup.read(0x1174,16))+array('read_pin',backup.read(0x1204,16))
    native_offsets=(0x15867c,0x1617cc,0x15d230,0x15c7b8,0x15aa58,0x159c64)
    h+='static const unsigned native_offsets[]={'+','.join(map(str,native_offsets))+'};\n'
    h+='static const unsigned char native_pins[][16]={'+','.join('{'+','.join(map(str,view.read(p,16)))+'}' for p in native_offsets)+'};\n'
    h+='static const unsigned guard_ids[]={'+','.join(str(k) for k in guards)+'};\n'
    h+=array('guard_values',guards.values())
    h+=f'static const int style={style},box={box},contrast={c},saturation={s},target={target};\n'
    h+=f'static const int model_only={int(model_only)};\n'
    out.mkdir(parents=True,exist_ok=False);(out/'sharpness-probe-pins.h').write_text(h)
    so=out/'probe.so'
    subprocess.run(['arm-none-eabi-gcc','-mcpu=cortex-a9','-marm','-mfloat-abi=soft',
                    '-mno-unaligned-access','-fPIC','-Os','-ffreestanding','-fno-builtin',
                    '-fno-unwind-tables','-fno-asynchronous-unwind-tables','-nostdlib',
                    '-Wall','-Wextra','-Wno-unused-function','-Wno-misleading-indentation',
                    '-shared','-Wl,--no-undefined','-Wl,-z,noexecstack','-I',str(ROOT/'payloads'),
                    '-I',str(out),str(ROOT/'research/sharpness_probe.c'),str(ROOT/'payloads/a7-fl-sharpness-native.c'),'-lgcc','-o',str(so)],check=True)
    (out/'manifest.json').write_text(json.dumps(dict(payload_sha256=sha(so.read_bytes()),
        guard_ids={hex(k):v for k,v in guards.items()},target=target,
        original_view_sha256=sha(view.data),backup_sha256=sha(backup.data),
        model_only=model_only,sources={p:sha((ROOT/p).read_bytes()) for p in ('research/sharpness_probe.c','research/sharpness_probe.py','payloads/a7-runtime-probe.c','payloads/a7-fl-sharpness-native.c','payloads/a7-fl-sharpness-native.h')}),indent=2)+'\n')
    return so.read_bytes()

def live(camera,usr,directory,model_only):
    from camera.service import Factory,settings_ok
    f=Factory(camera)
    require(f.contents('/version.txt')==BUILD and bytes(camera.readBackup(0x3e0005))==b'ILCE-7M3'+bytes(8),'Wrong camera/build')
    require(sha(f.contents('/usr/lib/a7fl.so'))==MODULE,'Unexpected installed module')
    require(sha(f.contents('/usr/lib/viewUnified2.so',11*1024*1024))==VIEW_INSTALLED,'Unexpected installed loader')
    snapshot=camera.getBackupPresetData(True);settings_ok(snapshot);(directory/'before-settings.bin').write_bytes(snapshot)
    def read(ids):
        result={}
        for key in ids:
            data=bytes(camera.readBackup(key));require(len(data)==1,f'Wrong property size: {key:#x}')
            result[key]=data[0]
        return result
    original=read((*ACTIVE,0x1070762))
    require(original[ACTIVE[0]] in MODEL_STYLES and original[ACTIVE[0]]!=0,'Unsupported current style')
    style=MODEL_STYLES.index(original[ACTIVE[0]]);slot=original[0x1070762]
    require(slot in (0,1,2,3,4,5,255),'Invalid style slot')
    cid=CONTRAST_IDS[style] if slot==255 else 0x1070a0f+slot
    gap=13 if slot==255 else 6
    ids=(*original,cid,cid+gap,cid+2*gap,*(() if slot==255 else (0x107075c+slot,)))
    original=read(ids)
    require([original[cid+i*gap] for i in range(3)]==[original[k] for k in ACTIVE[1:]],'Stored and active style disagree')
    if slot!=255:require(original[0x107075c+slot]==original[ACTIVE[0]],'Stored slot style disagrees')
    baseline=signed(original[ACTIVE[3]])
    require(-3<=baseline<=3,'Invalid baseline sharpness')
    (directory/'before.json').write_text(json.dumps({hex(k):v for k,v in original.items()},indent=2)+'\n')
    targets=[v for v in (-3,3) if v!=baseline]
    records=[];mutated=False
    try:
        for index,target in enumerate(targets):
            before=read(ids)
            expected=dict(original);expected[ACTIVE[3]]=target&255
            if not model_only:expected[cid+2*gap]=target&255
            payload=construct(usr,directory/f'target-{index}',before,target,model_only)
            # Set before entering the transport: even a timeout may follow acceptance.
            mutated=True
            raw=f.run(payload,'a7sharp.bin');(directory/f'target-{index}.bin').write_bytes(raw)
            require(len(raw)==20,'Bad probe report')
            values=struct.unpack('<3I2i',raw)
            require(values[0]==0x41375350 and values[3]==1,'Native guard rejected request')
            current=None
            for _ in range(10):
                current=read(ids)
                if current==expected:break
                time.sleep(.2)
            records.append(dict(target=target,report=list(values),actual={hex(k):v for k,v in current.items()},verified=current==expected))
            print('STOCK_SHARPNESS_READBACK',json.dumps(records[-1]),flush=True)
            require(current==expected,'Native request not independently confirmed; restore baseline')
    finally:
        if mutated:
            current=read(ids)
            unchanged=[k for k in original if k not in (ACTIVE[3],cid+2*gap)]
            require(all(current[k]==original[k] for k in unchanged),'Unexpected unrelated state change; no blind restoration')
            if current!=original:
                payload=construct(usr,directory/'restore',current,baseline,model_only)
                raw=f.run(payload,'a7sharp.bin');(directory/'restore.bin').write_bytes(raw)
                for _ in range(10):
                    current=read(ids)
                    if current==original:break
                    time.sleep(.2)
            restored=current==original
            (directory/'result.json').write_text(json.dumps(dict(tests=records,baseline_restored=restored,
                model_only=model_only,image_effect_verified=False,menu_integrated=False,firmware_replaced=False),indent=2)+'\n')
            print('STOCK_SHARPNESS_BASELINE_RESTORED',restored,flush=True)
            require(restored,'Failed baseline restoration: stop and inspect')

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--usr',required=True,type=Path)
    p.add_argument('--live',action='store_true');p.add_argument('--model-only',action='store_true');a=p.parse_args()
    subprocess.run([sys.executable,str(ROOT/'research/creative_setter.py'),'--usr',str(a.usr)],check=True)
    if a.model_only:subprocess.run([sys.executable,str(ROOT/'research/sharpness_request_test.py')],check=True)
    out=ROOT/'.lab/sharpness-probe'/str(time.time_ns());out.mkdir(parents=True,exist_ok=False)
    # Compile an offline fixture even without a camera; no transport imported.
    guards=dict(zip((*ACTIVE,0x1070762,0x1070a11,0x1070a17,0x1070a1d,0x107075e),(3,1,255,255,2,1,255,255,3)))
    construct(a.usr,out/'compile-fixture',guards,3,a.model_only)
    if a.live:
        from camera import handoff,service
        service.perform=lambda cam,action:live(cam,a.usr,out,a.model_only)
        handoff.run('settings-snapshot')
    print('EVIDENCE',out)
if __name__=='__main__':main()
