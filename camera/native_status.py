"""Read resident FL diagnostics without loading, installing or changing the module.

--decode reads a saved report; --offline verifies local evidence only. Neither
imports camera transport. Live inspection uses RTLD_NOLOAD in the attested probe,
reads existing preferences/calibration, and never applies or saves settings.
"""
import argparse
import json
from pathlib import Path
import struct
import time
import zlib

from local import BUILD_ID, LAB, ROOT, file_sha, require, sha
from camera.native_install import Bundle, pin_sources, save, save_json
from research.elf32 import ELF

PREFERENCES=('/setting/A7FL0.CFG','/setting/A7FL1.CFG')
PARAMETERS=('contrast','highlights','shadows','fade','saturation','sharpness','sharpness_range','clarity')
LOW=(-9,-9,-9,0,-9,-3,1,0)
HIGH=(9,9,9,9,9,3,5,9)


def trunc_div(value,divisor):
    return value//divisor if value>=0 else -((-value)//divisor)


def round_div(value,divisor):
    return (value+divisor//2)//divisor if value>=0 else -((-value+divisor//2)//divisor)


def adjusted_lut(base,codec,parameters):
    """Exact integer equivalent of the attested a7-fl-color.h; no spatial effects."""
    require(len(base)==1280 and len(codec)==771 and len(parameters)==5,'Unexpected color input lengths.')
    require(all(type(v) is int and LOW[i]<=v<=HIGH[i] for i,v in enumerate(parameters)), 'Color control out of range.')
    expand=struct.unpack('<129H',codec[:258]);compress=codec[258:]
    require(expand[0]==0 and expand[-1]==512 and compress[0]==0 and compress[-1]==128 and
            all(a<=b for a,b in zip(expand,expand[1:])) and
            all(a<=b for a,b in zip(compress,compress[1:])),'Invalid chroma codec.')
    signed=lambda v:v if v<128 else v-256
    clamp=lambda v,lo,hi:min(max(v,lo),hi)
    require(all(-64<=signed(v)<=63 for v in base[:1215]),'Base LUT contains unsupported signed values.')
    if not any(parameters):return bytes(base)
    contrast,highlights,shadows,fade,saturation=parameters
    result=bytearray(base)
    for b in range(9):
        for c in range(9):
            previous=0
            for a in range(5):
                at=a*81+b*9+c
                y=clamp(a*64+signed(base[at]),0,256)
                if contrast or highlights or shadows or fade:
                    lift=trunc_div((highlights*y*y+shadows*(256-y)*(256-y))*6,65536)
                    value=128+trunc_div((y-128)*(256+contrast*14),256)+lift
                    value=trunc_div(value*(256-fade*5),256)+fade*4
                    value=clamp(clamp(value,0,256)-a*64,-64,63)
                    y=clamp(a*64+value,previous,256)
                    result[at]=(y-a*64)&255
                previous=y
                if saturation:
                    for plane in (1,2):
                        index=at+plane*405;value=signed(base[index]);grid=((b if plane==1 else c)-4)*32
                        compressed=clamp(grid+(value*3//4),-128,128)
                        linear=(-1 if compressed<0 else 1)*expand[abs(compressed)]
                        scaled=round_div(linear*(256+saturation*24),256)
                        new=(-1 if scaled<0 else 1)*compress[clamp(abs(scaled),0,512)]
                        value+=round_div((new-compressed)*4,3)
                        result[index]=clamp(value,-64,63)&255
    return bytes(result)


def decode_preference(raw,original_sha,build=BUILD_ID):
    if raw is None:return dict(state='absent')
    error=None
    if len(raw)!=128:error='length'
    elif raw[:8]!=b'A7FLP001' or struct.unpack_from('<I',raw,8)[0]!=128 or struct.unpack_from('<I',raw,16)[0]!=1:error='format'
    elif raw[56:88].hex()!=original_sha or raw[88:112]!=build+bytes(24-len(build)):error='identity'
    elif any(raw[116:124]) or struct.unpack_from('<I',raw,124)[0]!=zlib.crc32(raw[:124]):error='checksum/reserved'
    if error:return dict(state='invalid',reason=error,size=len(raw),sha256=sha(raw))
    generation,_,enabled=struct.unpack_from('<3I',raw,12)
    parameters=list(struct.unpack_from('<8i',raw,24))
    if not generation or enabled not in (0,1) or any(not LOW[i]<=v<=HIGH[i] for i,v in enumerate(parameters)):
        return dict(state='invalid',reason='values',size=len(raw),sha256=sha(raw))
    return dict(state='valid',generation=generation,enabled=enabled,parameters=parameters,
                candidate_crc32=struct.unpack_from('<I',raw,112)[0],sha256=sha(raw))


def select_preferences(raw,original_sha):
    require(len(raw)==2,'Exactly two preference slots are required.')
    slots=[decode_preference(value,original_sha) for value in raw]
    valid=[i for i,p in enumerate(slots) if p['state']=='valid']
    if len(valid)==2 and slots[0]['generation']==slots[1]['generation'] and raw[0]!=raw[1]:
        return dict(state='conflicting',selected=None,slots=slots)
    if not valid:return dict(state='absent' if all(p['state']=='absent' for p in slots) else 'invalid',selected=None,slots=slots)
    chosen=max(valid,key=lambda i:(slots[i]['generation'],-i))
    return dict(state='valid',selected=chosen,slots=slots,preference=slots[chosen])


def decode_report(raw,expected_symbols=None):
    require(len(raw)==148,'Unexpected resident report length.')
    values=struct.unpack_from('<IIi4Ii3I',raw)
    names=('magic','version','status','view_base','module_base','bootstrap_symbol','runtime_symbol',
           'dlclose_result','bootstrap_bytes','runtime_bytes','stable')
    header=dict(zip(names,values))
    require(header['magic']==0x41374653 and header['version']==1 and header['status']<=1 and
            header['bootstrap_bytes']==36 and header['runtime_bytes']==68 and header['stable'] in (0,1),
            'Malformed resident report header.')
    if header['status']<=0:
        return dict(state='not-loaded' if header['status']==0 else 'probe-error',header=header,
                    bootstrap=None,runtime=None,physical_menu_verified=False,cold_power_verified=False)
    require(all(header[key] for key in ('view_base','module_base','bootstrap_symbol','runtime_symbol')),
            'Loaded report is missing native addresses.')
    if expected_symbols:
        require(all(header[key]==header['module_base']+offset for key,offset in expected_symbols.items()),
                'Resident status symbol addresses differ from attested module.')
    bootstrap=dict(zip(('version','calls','mode','stage','result','ready','view','caution','backup'),
                       struct.unpack_from('<4Ii4I',raw,44)))
    values=struct.unpack_from('<7I10i',raw,80)
    runtime=dict(zip(('prepared','installed','fault','parents','dirty','generation','runtime_ready','last_error','mode'),values[:9]))
    runtime['parameters']=list(values[9:])
    require(bootstrap['version'] in (0,1) and bootstrap['ready'] in (0,1) and
            all(runtime[k] in (0,1) for k in ('prepared','installed','fault','dirty','runtime_ready')) and
            runtime['parents']<=8 and runtime['mode'] in (-2,-1,0,1), 'Resident status fields are invalid.')
    if runtime['runtime_ready']:
        require(all(LOW[i]<=v<=HIGH[i] for i,v in enumerate(runtime['parameters'])), 'Resident controls out of range.')
    state=('unstable' if not header['stable'] else 'probe-error' if header['dlclose_result'] else
           'module-fault' if runtime['fault'] or runtime['mode']==-2 else
           'module-reported-error' if runtime['last_error']<0 or bootstrap['result']<0 else
           'loaded-awaiting-initialization' if not runtime['runtime_ready'] else
           'color-ready-menu-pending' if not runtime['installed'] else 'resident-ready')
    return dict(state=state,header=header,bootstrap=bootstrap,runtime=runtime,
                physical_menu_verified=False,cold_power_verified=False)


class Profile:
    def __init__(self,bundle_directory,module_proof,probe_directory,data_directory):
        self.bundle=Bundle(bundle_directory,module_proof,LAB/'creative-icons-belt',LAB/'native-fl-strings')
        self.proof_path=probe_directory/'proof.json';self.proof=json.loads(self.proof_path.read_text());p=self.proof
        pin_sources(p)
        require(p['module_sha256']==self.bundle.files[0]['sha256'],'Inspector/module identity mismatch.')
        self.payload=(probe_directory/'inspect.so').read_bytes()
        require(52<len(self.payload)<=65536 and sha(self.payload)==p['payload_sha256'] and
                self.payload[:7]==b'\x7fELF\x01\x01\x01','Inspector payload changed.')
        self.original=[(data_directory/f'{key:08x}.bin').read_bytes() for key in range(0x30004,0x30008)]
        self.base=(data_directory/'candidate.bin').read_bytes();self.codec=(data_directory/'codec.bin').read_bytes()
        require(all(len(t)==1280 for t in self.original+[self.base]) and len(self.codec)==771,'Private diagnostic data length mismatch.')
        require(all(sha(value)==p['original_lut_sha256'][f'{key:08x}'] for key,value in zip(range(0x30004,0x30008),self.original)) and
                sha(self.base)==p['base_fl_sha256'] and sha(self.codec)==p['codec_sha256'] and
                p['build'].encode()==BUILD_ID and p['original_sha256']==sha(self.original[0]),'Private diagnostic data identity mismatch.')
        self.original_sha=sha(self.original[0])
        module=ELF(bundle_directory/'input0.bin')
        self.symbols={key:module.symbols[name]['value'] for key,name in
                      (('bootstrap_symbol','a7_fl_bootstrap_status'),('runtime_symbol','a7_fl_status'))}
        require(all(self.symbols.values()),'Module lacks resident status exports.')


def observations(profile,report,prefs,tables):
    require(len(tables)==4 and all(len(t)==1280 for t in tables),'Four complete LUT reads required.')
    selection=select_preferences(prefs,profile.original_sha)
    candidate=None
    if selection['selected'] is not None:
        p=selection['preference'];candidate=adjusted_lut(profile.base,profile.codec,p['parameters'][:5])
        selection['candidate_crc_matches']=zlib.crc32(candidate)==p['candidate_crc32']
    runtime=report['runtime'];expected=None
    if (report['header']['status']==1 and report['header']['stable'] and not report['header']['dlclose_result'] and
            runtime and runtime['runtime_ready'] and not runtime['fault']):
        if runtime['mode']==0:expected=profile.original[0]
        elif runtime['mode']==1:expected=adjusted_lut(profile.base,profile.codec,runtime['parameters'][:5])
    table_states=[]
    for i,(actual,original) in enumerate(zip(tables,profile.original)):
        state='original' if actual==original else 'foreign'
        if i==0 and actual==profile.base:state='base-FL'
        if i==0 and candidate is not None and actual==candidate:state='saved-FL'
        if i==0 and expected is not None and actual==expected:state='runtime-expected'
        table_states.append(dict(property=f'{0x30004+i:08x}',state=state,sha256=sha(actual)))
    saved_match=None
    if selection['selected'] is not None and expected is not None:
        p=selection['preference']
        saved_match=(not runtime['dirty'] and runtime['generation']==p['generation'] and
                     runtime['mode']==p['enabled'] and runtime['parameters']==p['parameters'] and
                     selection['candidate_crc_matches'])
    return dict(preferences=selection,tables=table_states,
                active_table_matches_runtime=None if expected is None else tables[0]==expected,
                other_three_tables_original=all(a==b for a,b in zip(tables[1:],profile.original[1:])),
                runtime_matches_saved_preferences=saved_match,
                physical_menu_verified=False,cold_power_verified=False)


def inspect_camera(camera,profile,evidence,report_only=False):
    from camera.service import Factory
    factory=Factory(camera)
    require(factory.contents('/version.txt')==BUILD_ID and bytes(camera.readBackup(0x3e0005))==b'ILCE-7M3'+bytes(8),
            'Camera model/build mismatch.')
    module=factory.contents('/usr/lib/a7fl.so')
    require(sha(module)==profile.bundle.files[0]['sha256'],'Installed module differs from attested artifact.')
    raw=factory.run(profile.payload,'a7status.bin');save(evidence/'resident.bin',raw)
    result=decode_report(raw,profile.symbols)
    if not report_only:
        prefs=[]
        for index,path in enumerate(PREFERENCES):
            status,data=factory.read(path,maximum=160)
            require(status in ((0,0),factory.missing),'Preference read failed.')
            prefs.append(None if status==factory.missing else data)
            if status==(0,0):save(evidence/f'preference-{index}.bin',data)
        tables=[]
        for key in range(0x30004,0x30008):
            data=bytes(camera.readBackup(key));save(evidence/f'{key:08x}.bin',data);tables.append(data)
        result['observations']=observations(profile,result,prefs,tables)
    result['probe_loads_module']=False
    result['persistent_device_writes']=False
    save_json(evidence/'status.json',result)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--decode',type=Path,help='Decode an existing 148-byte report without contacting a camera')
    parser.add_argument('--offline',action='store_true',help='Verify local probe/module proofs only')
    parser.add_argument('--report-only',action='store_true',help='Read resident report without preferences/calibration tables')
    parser.add_argument('--direct',action='store_true')
    parser.add_argument('--bundle',type=Path,default=LAB/'native-install-bound')
    parser.add_argument('--module-proof',type=Path,default=LAB/'native-module/proof.json')
    parser.add_argument('--probe',type=Path,default=LAB/'native-inspect')
    parser.add_argument('--data',type=Path,default=LAB/'native-fl-01')
    args=parser.parse_args()
    require(not(args.offline and args.decode),'Choose --offline or --decode, not both.')
    profile=Profile(args.bundle.resolve(),args.module_proof.resolve(),args.probe.resolve(),args.data.resolve())
    if args.offline:
        print(json.dumps(dict(local_proofs_verified=True,camera_contacted=False,probe_loads_module=False,
                              module_sha256=profile.bundle.files[0]['sha256']),indent=2));return 0
    if args.decode:
        result=decode_report(args.decode.read_bytes(),profile.symbols);result['camera_contacted']=False
        print(json.dumps(result,indent=2));return 0
    evidence=args.probe.resolve()/f'read-{time.time_ns()}';evidence.mkdir(mode=0o700)
    save(evidence/'probe-proof.json',profile.proof_path.read_bytes())
    from camera import service,handoff
    previous=service.perform;result=None
    def perform(camera,action):
        nonlocal result
        require(action=='settings-snapshot','Unexpected transport action.')
        result=inspect_camera(camera,profile,evidence,args.report_only)
    service.perform=perform
    try:
        if args.direct:
            import fcntl
            with (LAB/'.usb-transport.lock').open('a') as lock:
                fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);service.connect('settings-snapshot')
        else:handoff.run('settings-snapshot')
    finally:service.perform=previous
    require(result is not None,'Transport returned without diagnostics.')
    print('LIVE_NATIVE_RESIDENT_STATUS '+json.dumps(result,ensure_ascii=False),flush=True)
    print('EVIDENCE '+str(evidence),flush=True)
    return 0


if __name__=='__main__':raise SystemExit(main())
