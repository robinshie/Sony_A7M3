#!/usr/bin/env python3
"""Temporary kernel pre-JPEG experiments. Grain route edits one bounded luma region.

Build, selftest, then arm the same bundle. An armed module is pinned until reboot.
Collect restores the original instruction and reads one bounded context snapshot.
"""
import argparse, hashlib, json, shutil, struct, subprocess, sys, time
from pathlib import Path
from kernel_probe import abi, PINS, sha, ROOT
from elf32 import ELF
sys.path.insert(0, str(ROOT))
SOURCES = ['research/capture_kernel_probe.py', 'research/kernel_probe_loader.c',
           'research/kernel_probe/capture_probe.c', 'research/kernel_probe/capture_bridge.S']
LIRO_PIN = '72b77031f00679877ac04edf452e9f49e5fbca05cb4ee4554ddd2e5243e8e0cc'
def build(a):
    av, kernel = a.avcam.read_bytes(), a.kernel.read_bytes()
    if sha(av)!=PINS['avcam'] or sha(kernel)!=PINS['kernel'] or sha(a.liro.read_bytes())!=LIRO_PIN:
        raise ValueError('Requires pinned original firmware')
    film = a.route == 'film'
    halo = a.route in ('halation','film')
    banks = a.route in ('banks','halation','film')
    repeat = a.route in ('repeat','banks','halation','film')
    fast = a.route == 'fast'
    full = a.route in ('full','fast','repeat','banks','halation','film')
    grain = a.route in ('grain','full','fast','repeat','banks','halation','film')
    lease = a.route in ('lease','grain','full','fast','repeat','banks','halation','film')
    early = a.route in ('early','lease','grain','full','fast','repeat','banks','halation','film')
    frame = a.route in ('frame','early','lease','grain','full','fast','repeat','banks','halation','film')
    vfx = a.route in ('vfx','frame','early','lease','grain','full','fast','repeat','banks','halation','film')
    detail = a.route == 'detail'
    multi = a.route in ('multi','detail','vfx','frame','early','lease','grain','full','fast','repeat','banks','halation','film')
    fixture_path=ROOT/('.lab/capture-film-test/proof.json' if film else '.lab/capture-halation-test/proof.json' if halo else '.lab/capture-banks-test/proof.json' if banks else '.lab/capture-repeat-test/proof.json' if repeat else '.lab/capture-fast-test/proof.json' if fast else '.lab/capture-full-test/proof.json' if full else '.lab/capture-grain-test/proof.json' if grain else '.lab/capture-lease-test/proof.json' if lease else '.lab/capture-early-test/proof.json' if early else '.lab/capture-frame-test/proof.json' if frame else '.lab/capture-vfx-test/proof.json' if vfx else '.lab/capture-detail-test/proof.json' if detail else '.lab/capture-multi-test/proof.json' if multi else '.lab/jpeg-kernel-callback/proof.json')
    fixture = json.loads(fixture_path.read_text())
    if not fixture.get('bridge_and_exception_abi_tested' if multi else 'kernel_callback_bridge_tested') or any(
        sha((ROOT/n).read_bytes())!=v for n,v in fixture['source_sha256'].items()):
        raise ValueError('Run the current QEMU callback fixture first')
    if grain:
        pixel_fixture=json.loads((ROOT/('.lab/capture-film-record/proof.json' if film else '.lab/capture-halation-record/proof.json' if halo else '.lab/capture-full-record/proof.json' if full else '.lab/capture-grain-record/proof.json')).read_text())
        if not pixel_fixture.get('passed') or any(sha((ROOT/n).read_bytes())!=v for n,v in pixel_fixture['source_sha256'].items()):
            raise ValueError('Run current bounded grain/lease/rollback fixture first')
    if repeat:
        control_fixture=json.loads((ROOT/('.lab/capture-film-control/proof.json' if film else '.lab/capture-halation-control/proof.json' if halo else '.lab/capture-repeat-control/proof.json')).read_text())
        if not control_fixture.get('passed') or any(sha((ROOT/n).read_bytes())!=v for n,v in control_fixture['source_sha256'].items()):
            raise ValueError('Run current repeat selection and dispatch fixture first')
    out = ROOT/'.lab/capture-kernel'/str(time.time_ns()); out.mkdir(parents=True)
    chosen = SOURCES[:2]+(['research/kernel_probe/capture_early.c','research/kernel_probe/capture_frame.c','research/kernel_probe/capture_early_bridge.S','research/kernel_probe/capture_early_record.h'] if early else ['research/kernel_probe/capture_frame.c','research/kernel_probe/capture_frame_bridge.S','research/kernel_probe/a7source.c'] if frame else ['research/kernel_probe/capture_vfx.c','research/kernel_probe/capture_vfx_bridge.S'] if vfx else ['research/kernel_probe/capture_detail.c','research/kernel_probe/capture_detail_bridge.S','research/kernel_probe/capture_detail_record.h'] if detail else ['research/kernel_probe/capture_multi.c','research/kernel_probe/capture_multi_bridge.S'] if multi else SOURCES[2:])
    if detail:
        sampler=json.loads((ROOT/'.lab/capture-detail-record/proof.json').read_text())
        if not sampler.get('passed') or any(sha((ROOT/n).read_bytes())!=v for n,v in sampler['source_sha256'].items()):
            raise ValueError('Run current bounded metadata sampler test first')
    if lease:
        chosen=[n for n in chosen if n not in ('research/kernel_probe/capture_early.c','research/kernel_probe/capture_early_bridge.S')]+['research/kernel_probe/capture_lease.c','research/kernel_probe/capture_lease_bridge.S','research/kernel_probe/capture_lease_record.h']
    if grain:
        chosen=[n for n in chosen if n not in ('research/kernel_probe/capture_lease.c','research/kernel_probe/capture_lease_bridge.S')]+['research/kernel_probe/capture_grain.c','research/kernel_probe/capture_grain_bridge.S','research/kernel_probe/capture_grain_record.h','research/kernel_probe/grain_core.c','research/kernel_probe/compat/stdint.h','research/kernel_probe/compat/stddef.h','payloads/a7-film-frame.c','payloads/a7-film-frame.h']
    if full:
        chosen=[n for n in chosen if n not in ('research/kernel_probe/capture_grain.c','research/kernel_probe/capture_grain_bridge.S')]+['research/kernel_probe/capture_full.c','research/kernel_probe/capture_full_bridge.S']
    if fast:
        chosen=[n for n in chosen if n not in ('research/kernel_probe/capture_full.c','research/kernel_probe/capture_full_bridge.S')]+['research/kernel_probe/capture_fast.c','research/kernel_probe/capture_fast_bridge.S']
    if repeat:
        chosen=[n for n in chosen if n not in ('research/kernel_probe/capture_full.c','research/kernel_probe/capture_full_bridge.S')]+['research/kernel_probe/capture_repeat.c','research/kernel_probe/capture_repeat_bridge.S','research/kernel_probe/capture_repeat_control.h']
    if banks:
        chosen=[n for n in chosen if n not in ('research/kernel_probe/capture_repeat.c','research/kernel_probe/capture_repeat_bridge.S')]+['research/kernel_probe/capture_banks.c','research/kernel_probe/capture_banks_bridge.S']
    if halo:
        chosen=[n for n in chosen if n not in ('research/kernel_probe/capture_banks.c','research/kernel_probe/capture_banks_bridge.S','research/kernel_probe/capture_repeat_control.h','research/kernel_probe/capture_grain_record.h')]+['research/kernel_probe/capture_halation.c','research/kernel_probe/capture_halation_bridge.S','research/kernel_probe/capture_halation_control.h','research/kernel_probe/capture_halation_record.h']
    if film:
        chosen=[n for n in chosen if 'capture_halation' not in n]+['research/kernel_probe/capture_film.c','research/kernel_probe/capture_film_bridge.S','research/kernel_probe/capture_film_control.h','research/kernel_probe/capture_film_record.h']
    sources = {n:sha((ROOT/n).read_bytes()) for n in chosen}
    identity = list(struct.unpack('<4I', hashlib.sha256(json.dumps(sources, sort_keys=True).encode()).digest()[:16]))
    name='a7capfilm' if film else 'a7caphalo3' if halo else 'a7capbanks' if banks else 'a7caprepeat' if repeat else 'a7capfast' if fast else 'a7capfull' if full else 'a7capgrain' if grain else 'a7caplease' if lease else 'a7capearly' if early else 'a7capframe' if frame else 'a7capvfx' if vfx else 'a7capdetail' if detail else 'a7capmulti' if multi else 'a7capture'
    units=('capture_halation.c','capture_halation_bridge.S','grain_core.c') if halo else ('capture_banks.c','capture_banks_bridge.S','grain_core.c') if banks else ('capture_repeat.c','capture_repeat_bridge.S','grain_core.c') if repeat else ('capture_fast.c','capture_fast_bridge.S','grain_core.c') if fast else ('capture_full.c','capture_full_bridge.S','grain_core.c') if full else ('capture_grain.c','capture_grain_bridge.S','grain_core.c') if grain else ('capture_lease.c','capture_lease_bridge.S') if lease else ('capture_early.c','capture_early_bridge.S') if early else ('capture_frame.c','capture_frame_bridge.S') if frame else ('capture_vfx.c','capture_vfx_bridge.S') if vfx else ('capture_detail.c','capture_detail_bridge.S') if detail else ('capture_multi.c','capture_multi_bridge.S') if multi else ('capture_probe.c','capture_bridge.S')
    if film:units=('capture_film.c','capture_film_bridge.S','grain_core.c')
    (out/'Makefile').write_text(f'obj-m += {name}.o\n{name}-y := '+ ' '.join(Path(n).stem+'.o' for n in units)+'\n')
    if halo:
        for n in ('capture_halation_control.h','capture_halation_record.h'):shutil.copyfile(ROOT/'research/kernel_probe'/n,out/n)
    if film:
        for n in ('capture_film_control.h','capture_film_record.h'):shutil.copyfile(ROOT/'research/kernel_probe'/n,out/n)
    if repeat:shutil.copyfile(ROOT/'research/kernel_probe/capture_repeat_control.h',out/'capture_repeat_control.h')
    if grain:
        with (out/'Makefile').open('a') as f:f.write('ccflags-y += -I$(src)/compat\nCFLAGS_grain_core.o += -std=gnu99\n')
        shutil.copytree(ROOT/'research/kernel_probe/compat',out/'compat')
        for n in ('a7-film-frame.c','a7-film-frame.h'):shutil.copyfile(ROOT/'payloads'/n,out/n)
        shutil.copyfile(ROOT/'research/kernel_probe/capture_grain_record.h',out/'capture_grain_record.h')
    for n in units:
        shutil.copyfile(ROOT/'research/kernel_probe'/n,out/n)
    if early:
        if not a.dmm or sha(a.dmm.read_bytes())!='f0df6a0e335e8a1bf71c01b9a7d1caeefdb8c7353f96ec8c699a0b3c8d6e1ae6':raise ValueError('Requires pinned DMM module')
        dmm=ELF(a.dmm).section(1)[0x889c:0x8a24]
        (out/'dmm-pins.h').write_text('static const unsigned char dmm_open_pin[]={'+','.join(map(str,dmm))+'};\n')
        for n in ('capture_frame.c','capture_early_record.h'):shutil.copyfile(ROOT/'research/kernel_probe'/n,out/n)
    if lease:
        code=ELF(a.dmm).section(1)[0x8a28:0x8b1c]
        handle=ELF(a.dmm).section(1)[0x85a4:0x85fc]
        (out/'dmm-close-pins.h').write_text('static const unsigned int dmm_close_pin[]={'+','.join(hex(x) for x in struct.unpack('<61I',code))+'};\n' +
            'static const unsigned char dmm_handle_pin[]={'+','.join(map(str,handle))+'};\n')
        shutil.copyfile(ROOT/'research/kernel_probe/capture_lease_record.h',out/'capture_lease_record.h')
    if frame and not early:shutil.copyfile(ROOT/'research/kernel_probe/a7source.c',out/'a7source.c')
    if detail:shutil.copyfile(ROOT/'research/kernel_probe/capture_detail_record.h',out/'capture_detail_record.h')
    header = 'static const unsigned int source_id[]={'+','.join(map(str,identity))+'};\n'
    header += '#define NATIVE_SITE_WORD '+hex(struct.unpack_from('<I',av,0x34019c)[0])+'U\n'
    sites=[0x134ccc,0x134c3c,0x11b344,0x11b098] if vfx else [0x33588c,0x11adf0,0x4e70e0,0x45ce58]
    if early:sites[2]=0x11c4e8
    if multi:
        header+='static const unsigned long capture_sites[]={'+','.join(hex(0x635c6000+s) for s in sites)+'};\n'
        header+='static const unsigned int native_words[]={'+','.join(hex(struct.unpack_from('<I',av,s)[0]) for s in sites)+'};\n'
    header += 'static const struct {unsigned long address; unsigned size; unsigned char bytes[512];} code_pins[]={\n'
    ranges = [(0x60108174, 0x60108308), (0x6010dae0,0x6010db88), (0x601118ac,0x60111940)]
    blocks = [(lo,kernel[lo-0x60108000:hi-0x60108000]) for lo,hi in ranges]
    if multi: blocks.extend((0x635c6000+s-12,av[s-12:s+16]) for s in sites)
    else: blocks.append((0x6390618c,av[0x34018c:0x3401b0]))
    for addr,b in blocks:
        header += '{'+hex(addr)+','+str(len(b))+',{'+','.join(map(str,b))+'}},\n'
    (out/'capture-pins.h').write_text(header+'};\n')
    (out/'pins.h').write_text(''.join('static const unsigned char '+name+'[]={'+','.join(map(str,b))+'};\n'
        for name,b in [('kernel_pin',kernel[0x10470:0x10490]),('stage_pin',av[0x34018c:0x3401b0])]))
    cmd=['make','-C',str(a.kernel_source.resolve()),'ARCH=arm','CROSS_COMPILE=arm-none-eabi-',
         'HOSTCC=clang','HOSTCFLAGS=-O2 -I'+str(ROOT/'.lab/kernel-host-include'),
         'KCFLAGS=-std=gnu89','LOCALVERSION=+']
    with (out/'build.log').open('w') as log:
        subprocess.run(cmd+['modules_prepare'],stdout=log,stderr=log,check=True)
        subprocess.run(cmd+['M='+str(out),'modules'],stdout=log,stderr=log,check=True)
    module=out/(name+'.ko')
    subprocess.run(['arm-none-eabi-strip','--strip-debug',str(module)],check=True)
    actual,reference=abi(module),abi(a.liro)
    for key in ('size','relocation_offsets','relocation_types','vermagic'):
        if actual[key]!=reference[key]:raise ValueError('Kernel module ABI mismatch: '+key)
    allowed={'__module_get','module_put','kallsyms_lookup_name','memcmp','on_each_cpu',
             'param_get_uint','param_array_ops','param_ops_uint','param_ops_bool','param_get_int',
             'probe_kernel_read','stop_machine','cpu_cache','kstrtoint',
             '__per_cpu_offset','preempt_schedule','memcpy','memset',
             '__aeabi_idiv','__aeabi_idivmod','__memzero','outer_cache','__aeabi_uidiv','__aeabi_uidivmod','__aeabi_uldivmod','_raw_spin_lock_irqsave','arch_va_to_cachetype','_raw_spin_trylock','_raw_spin_unlock','_raw_spin_unlock_irqrestore','arch_phys_to_cachetype2','arch_phys_to_va','jiffies','sysfs_create_bin_file','sysfs_remove_bin_file'}
    if not set(actual['undefined'])<=allowed:raise ValueError('Unexpected imports: '+str(actual['undefined']))
    elf = ELF(module)
    relocations = set()
    for section in elf.sections:
        if section[1] == 9:
            for at in range(section[4], section[4]+section[5], section[9]):
                relocations.add(struct.unpack_from('<II',elf.data,at)[1] & 255)
    # This non-Thumb Linux module loader cannot relocate Thumb branch opcodes.
    if not relocations <= {0,1,2,28,29,38,40,42,43,44}:
        raise ValueError('Unsupported original kernel relocation: '+str(relocations))
    (out/'embedded.S').write_text('.section .rodata\n.balign 4\n.global module_start,module_end\n'
        f'module_start:\n.incbin "{name}.ko"\nmodule_end:\n.section .note.GNU-stack,"",%progbits\n')
    payloads={}
    text_bytes=4096 if detail or vfx else 3072 if multi else 1024
    for i,action in enumerate(('selftest','arm','collect')):
        target=action+'.so'
        subprocess.run(['arm-none-eabi-gcc','-mcpu=cortex-a9','-marm','-mfloat-abi=soft','-fPIC','-Os',
            '-ffreestanding','-fno-builtin','-fno-unwind-tables','-fno-asynchronous-unwind-tables',
            '-nostdlib','-shared','-Wl,--no-undefined','-Wl,-z,noexecstack','-Wall','-Wextra','-Werror',
            '-DA7_CAPTURE_ACTION='+str(i),
            *(['-DA7_CAPTURE_ARGS="arm=1 selection=0"'] if film and action=='arm' else ['-DA7_CAPTURE_ARGS="arm=1 selection=1"'] if halo and action=='arm' else ['-DA7_CAPTURE_ARGS="arm=1 selection=57"'] if repeat and action=='arm' else []),'-DA7_CAPTURE_NAME="'+name+'"',
            '-DA7_REPORT_BYTES='+str(text_bytes),'-I'+str(out),str(ROOT/'research/kernel_probe_loader.c'),
            'embedded.S','-o',target],cwd=out,check=True)
        payloads[action]=sha((out/target).read_bytes())
    proof=dict(source_sha256=sources,source_id=identity,module_sha256=sha(module.read_bytes()),
        payload_sha256=payloads,pins=PINS,abi=actual,fixture_sha256=sha(fixture_path.read_bytes()),
        route=a.route,module_name=name,text_bytes=text_bytes,report_words=368 if detail or vfx else 256 if multi else 64,
        live=[],image_pixel_write_requested=grain,image_pixels_written=False,firmware_written=False,flash_ready=False)
    (out/'proof.json').write_text(json.dumps(proof,indent=2)+'\n')
    print('BUNDLE',out)
    return out

def run(out,action):
    proof=json.loads((out/'proof.json').read_text())
    blob=(out/(action+'.so')).read_bytes()
    if sha(blob)!=proof['payload_sha256'][action]:raise ValueError('Payload hash mismatch')
    if action=='arm' and not any(x['action']=='selftest' and x['verified'] for x in proof['live']):
        raise ValueError('Same bundle must pass real kernel self-test before arming')
    from camera import handoff,service
    def collect(camera, requested):
        if requested!='settings-snapshot':raise ValueError('Unexpected action')
        f=service.Factory(camera)
        if f.contents('/version.txt')!=b'37114_13.2026020901' or bytes(camera.readBackup(0x3e0005))!=b'ILCE-7M3'+bytes(8):
            raise ValueError('Wrong model/build')
        raw=f.run(blob,'a7kc.bin');stamp=str(time.time_ns())
        (out/(action+'-'+stamp+'.bin')).write_bytes(raw)
        text_bytes=proof.get('text_bytes',1024)
        if len(raw)!=92+text_bytes:raise ValueError('Wrong report size')
        magic,version,status,loaded,unloaded,used=struct.unpack_from('<IIiiiI',raw)
        if (magic,version)!=(0x41374b4c,1) or used>=text_bytes:raise ValueError('Wrong report identity')
        result=dict(action=action,status=status,load_result=loaded,unload_result=unloaded,
                    release=raw[24:89].split(b'\0')[0].decode(),report=raw[92:92+used].decode(),
                    report_file=action+'-'+stamp+'.bin',temporary_files_removed=True,verified=False)
        proof['live'].append(result)
        def save(): (out/'proof.json').write_text(json.dumps(proof,indent=2)+'\n')
        save()
        if status or (action!='collect' and loaded) or (action=='selftest' and unloaded):
            print(json.dumps(result,indent=2),flush=True)
            raise ValueError('Kernel action failed; inspect result')
        values=[int(x) for x in result['report'].strip().split(',')]
        if len(values)!=proof.get('report_words',64) or values[0]!=0x4137434b or values[3]!=1 or values[4]!=1 or values[12:16]!=proof['source_id']:
            raise ValueError('Wrong module report/source identity')
        if action=='arm' and (values[1]!=1 or values[11]!=1):raise ValueError('Probe not armed')
        if action=='collect' and values[5]!=1:raise ValueError('Probe was not disarmed')
        result.update(verified=True,values=values,module_pinned_until_reboot=bool(values[11]))
        if proof.get('route') in ('early','lease','grain','full','fast','repeat','banks','halation','film'):
            result['early_source']=dict(state=values[17],status=values[18] if values[18]<0x80000000 else values[18]-0x100000000,handle=hex(values[21]),unit=hex(values[22]),dmm_root=hex(values[20]),open_count=(values[228]>>8)&255,rendezvous=(values[228]>>16)&255,generation=values[228]>>24,unit_state=values[229]&65535,extent_count=values[229]>>16,extent_words=[hex(x) for x in values[256:268]])
        if proof.get('route') in ('lease','grain','full','fast','repeat','banks','halation','film'):
            result['lease_test']=dict(attempted=bool(values[309]),passed=bool(values[310]),cache_type=values[305],open_status=values[306],close_status=values[307],count=values[308])
        if proof.get('route') in ('grain','full','fast','repeat','banks','halation','film'):
            result['grain_patch']=dict(state=values[344],status=values[345],changed=values[346],ticks=values[348],rollback=values[350],private_selftest=values[352])
            result['grain_patch']['processed_luma_pixels' if proof.get('route') in ('full','fast','repeat','banks','halation','film') else 'written_luma_bytes']=values[349]
            if values[349]:proof['image_pixels_written']=True
        if proof.get('route') in ('repeat','banks','halation','film'):
            result['repeat']=dict(selection=values[353],seed=values[354],completed=values[355],skipped_off=values[356],failed=values[357])
        if proof.get('route')=='frame':
            result['source_sample']=dict(state=values[17],status=values[18] if values[18]<0x80000000 else values[18]-0x100000000,rows=values[19],va=hex(values[20]),base=hex(values[21]))
        if proof.get('route')=='vfx':
            result['snapshots']=[dict(label=label,state=values[n],sequence=values[n+1],address=hex(values[n+2]),status=values[n+4]) for label,n in [('vfx_input',16),('vfx_driver',136),('encoder_object',252)]]
            result['site_hits']=values[364:368]
        if proof.get('route')=='detail':
            result['metadata_samples']=[]
            for label,offset in [('first',16),('latest',192)]:
                slot=values[offset:offset+176]
                signed=lambda x:x if x<0x80000000 else x-0x100000000
                result['metadata_samples'].append(dict(label=label,state=slot[0],sequence=slot[1],
                    end_sequence=slot[175],statuses=list(map(signed,slot[166:171])),
                    registers=[hex(x) for x in slot[2:10]]))
        if proof.get('route')=='multi':
            labels=['capture_selector','exec_jpeg_wrapper','scalar_jpeg_stage','sa_jpeg_start']
            result['records']=[]
            for i,label in enumerate(labels):
                slot=values[16+i*60:16+(i+1)*60]
                signed=lambda x:x if x<0x80000000 else x-0x100000000
                result['records'].append(dict(label=label,hits=slot[0],snapshot_state=slot[1],
                    registers=[hex(x) for x in slot[4:18]],
                    first_read_status=signed(slot[58]),second_read_status=signed(slot[59])))
        save()
        shown={k:v for k,v in result.items() if k not in ('report','values')}
        shown['callback_hits']=values[2];shown['disarmed']=bool(values[5])
        print(json.dumps(shown,indent=2),flush=True)
    old,sw=service.perform,handoff.SWITCH
    service.perform=collect;handoff.SWITCH+=' --host-identity-check'
    try:handoff.run('settings-snapshot')
    finally:service.perform=old;handoff.SWITCH=sw

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['build','selftest','arm','collect'])
    p.add_argument('--bundle',type=Path)
    p.add_argument('--route',choices=['stage','multi','detail','vfx','frame','early','lease','grain','full','fast','repeat','banks','halation','film'],default='stage')
    for name in ('avcam','kernel','liro','kernel-source','dmm'):p.add_argument('--'+name,type=Path)
    a=p.parse_args()
    if a.bundle:out=a.bundle.resolve()
    else:
        if a.action!='build' or any(getattr(a,n.replace('-','_')) is None for n in ('avcam','kernel','liro','kernel-source')):
            p.error('Build requires all firmware paths; live actions require --bundle')
        out=build(a)
    if a.action!='build':run(out,a.action)
if __name__=='__main__':main()
