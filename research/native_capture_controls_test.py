#!/usr/bin/env python3
"""Private-data host/ARM tests for adjustable capture tables. No device I/O."""
import argparse,hashlib,json,shutil,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'.lab/native-capture-controls-test'
LEGACY=ROOT/'.lab/native-module-capture-look'
ROUTE=ROOT/'.lab/lut3d-capture-look'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(args,**kw):return subprocess.run(args,check=True,**kw)
def main():
    global OUT
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--route',type=Path,default=ROUTE,help='Fresh original-LUT fixture with identical private tables')
    parser.add_argument('--dual-look',action='store_true')
    parser.add_argument("--leica-look",action="store_true")
    parser.add_argument('--film-curves',action='store_true',help='Test the new five-point kernel on all three looks, without installing it')
    options=parser.parse_args()
    if options.film_curves:
        if not options.dual_look or not options.leica_look:parser.error('--film-curves requires --dual-look --leica-look')
        OUT=ROOT/'.lab/native-fivepoint-capture-test'
    route_dir=options.route.resolve()
    OUT.mkdir(parents=True,exist_ok=True);(OUT/'proof.json').unlink(missing_ok=True)
    mp=json.loads((LEGACY/'proof.json').read_text())
    assert mp['module_sha256']=='1216dda332c42c6378fd993ccb89781d6229150c00798191835232de3923b675'
    assert sha(LEGACY/'a7-fl-module-data.h')==mp['artifact_sha256']['a7-fl-module-data.h']
    legacy_route=json.loads((ROUTE/'proof.json').read_text())
    assert sha(ROUTE/'proof.json')==mp['capture_look']['source_qemu_proof_sha256']
    route=json.loads((route_dir/'proof.json').read_text())
    for key in ('avcam_sha256','native_ranges','table_input_sha256','descriptor_controls_sha256','capture_candidates'):
        assert route[key]==legacy_route[key],key
    for p,d in route['source_sha256'].items():assert sha(ROOT/p)==d,p
    for name,r in route['native_ranges'].items():assert sha(route_dir/(name+'.bin'))==r['sha256'],name
    data=(route_dir/'table_inputs.bin').read_bytes()
    assert hashlib.sha256(data[:5120]).hexdigest()==route['table_input_sha256']
    assert hashlib.sha256(data[5120:9728]).hexdigest()==route['descriptor_controls_sha256']
    assert data[9728]==1
    for i,r in enumerate(route['capture_candidates']):assert hashlib.sha256(data[9729+i*1280:9729+(i+1)*1280]).hexdigest()==r['candidate_sha256']
    shutil.copyfile(LEGACY/'a7-fl-module-data.h',OUT/'a7-fl-module-data.h')
    sources=['payloads/a7-fl-capture-controls.c','research/native_capture_controls_test.c']
    flags=['-O2','-Wall','-Wextra','-Werror','-Wno-unused-function','-I'+str(ROOT/'payloads'),'-I'+str(OUT)]
    if options.dual_look:flags+=['-DA7_FL_DUAL_LOOK']
    if options.leica_look:flags+=['-DA7_FL_LEICA_LOOK']
    if options.film_curves:
        flags+=['-DA7_FL_FILM_CONTROLS']
        sources+=['payloads/a7-fl-fivepoint.c']
    (OUT/'host.c').write_text('''#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
static unsigned long checks;
void cc_check(int ok,const char *why){checks++;if(!ok){fprintf(stderr,"FAIL %s\\n",why);exit(1);}}
void cc_pack(const uint8_t *p,unsigned n){(void)p;(void)n;}
extern void a7_capture_controls_tests(void);
int main(void){a7_capture_controls_tests();printf("CAPTURE_CONTROLS_HOST_PASSED: %lu checks\\n",checks);return 0;}
''')
    if options.film_curves:
        p=OUT/'host.c';p.write_text(p.read_text().replace('a7_capture_controls_tests','a7_capture_curve_tests'))
    run(['clang',*flags,'-fsanitize=address,undefined','-fno-omit-frame-pointer','-DA7_CC_EXHAUSTIVE',
         str(OUT/'host.c'),*[str(ROOT/p) for p in sources],'-o',str(OUT/'host-test')])
    host=run([str(OUT/'host-test')],capture_output=True,timeout=120)
    (OUT/'host.log').write_bytes(host.stdout+host.stderr);print(host.stdout.decode(),end='')
    # Existing original generator, selector and packing fixture; only its entry
    # is replaced, and a new test calls the unmodified native Create function.
    for p in route_dir.iterdir():
        if p.suffix=='.bin' or p.name in ('native.S','start.S','guest.ld'):shutil.copyfile(p,OUT/p.name)
    (OUT/'arm.c').write_text('''#define guest_main unused_legacy_entry
#include "lut3d_harness.c"
#undef guest_main
void cc_check(int ok,const char *why){check(ok,why);}
void cc_pack(const uint8_t *source,unsigned level){
 static uint32_t params[0x220/4],mode[4],desc[0x70/4],work[0x700/4],output[407];
 uintptr_t a[2]={(uintptr_t)params,(uintptr_t)mode},b[5]={0,0,0,(uintptr_t)desc,(uintptr_t)work};
 native_set(params,0,sizeof params);native_set(mode,0,sizeof mode);native_set(desc,0,sizeof desc);native_set(work,0,sizeof work);
 ((uint8_t*)params)[0x29]=level;((uint8_t*)desc)[0x68]=1;desc[0x64/4]=(uintptr_t)source;work[0x6b8/4]=(uintptr_t)(output+1);
 for(unsigned i=0;i<407;i++)output[i]=GUARD;
 FN(0x5231fc,void (*)(void*,void*))(a,b);
 check(output[0]==GUARD&&output[406]==GUARD,"native CAP output extent");
 for(unsigned x=0;x<5;x++)for(unsigned y=0;y<9;y++)for(unsigned z=0;z<9;z++){
  unsigned i=x*81+y*9+z;
  check(output[1+index_of(x,y,z)]==word(scaled(source[i],level),scaled(source[i+405],level),scaled(source[i+810],level)),"original native Create matches generated CAP nodes");
 }
}
extern void a7_capture_controls_tests(void);
void guest_main(void){a7_capture_controls_tests();put("CAPTURE_CONTROLS_ARM_PASSED: controls, bounds, original Create, migration and rollback\\n");finish();}
''')
    if options.film_curves:
        p=OUT/'arm.c';p.write_text(p.read_text().replace('a7_capture_controls_tests','a7_capture_curve_tests')
            .replace('controls, bounds, original Create, migration and rollback','five-point preview, paired CAP apply/rollback and original Create; no camera I/O'))
    run(['arm-none-eabi-gcc',*flags,'-I'+str(ROOT/'research'),'-mcpu=cortex-a9','-mthumb','-mfloat-abi=soft','-mno-unaligned-access',
         '-ffreestanding','-fno-builtin','-nostdlib','-T','guest.ld','start.S','native.S','arm.c',
         *[str(ROOT/p) for p in sources],'-lgcc','-o','test.elf'],cwd=OUT)
    arm=run(['qemu-system-arm','-M','virt','-cpu','cortex-a15','-m','1024','-nodefaults','-audio','none','-nic','none','-display','none','-monitor','none','-serial','stdio','-semihosting-config','enable=on,target=native','-device',f'loader,file={OUT}/test.elf,cpu-num=0'],capture_output=True,timeout=60)
    log=arm.stdout+arm.stderr;(OUT/'qemu.log').write_bytes(log);print(log.decode(),end='')
    assert b'CAPTURE_CONTROLS_ARM_PASSED' in log and b'FAIL ' not in log
    sources+=['payloads/a7-fl-capture-controls.h','payloads/a7-fl-color.h','research/native_capture_controls_test.py','research/lut3d_harness.c']
    sources+=['payloads/a7-fl-runtime-prefs.h']
    if options.dual_look:sources+=['payloads/a7-fl-cinema.h','payloads/a7-fl-fl2-model.inc']
    if options.leica_look:sources+=['payloads/a7-fl-leica.h','payloads/a7-fl-leica-model.inc']
    if options.film_curves:sources+=['payloads/a7-fl-fivepoint.h','payloads/a7-fl-fivepoint-preview.h']
    proof={'leica_look_packed_bounds':options.leica_look,'dual_look_packed_bounds':options.dual_look,'source_sha256':{p:sha(ROOT/p) for p in sources},'artifacts':{p:sha(OUT/p) for p in ('host-test','test.elf','host.log','qemu.log','a7-fl-module-data.h','arm.c','native.S','guest.ld','start.S')},
           'legacy_module_sha256':mp['module_sha256'],'legacy_capture_proof_sha256':sha(ROUTE/'proof.json'),
           'current_capture_proof_sha256':sha(route_dir/'proof.json'),
           'all_single_control_values':True,'all_tone_combinations_host':True,'tone_combination_count':19**3*10*2,
           'tested_levels':list(range(1,9)),'max_packed_delta':[24,32,32],
           'base_delta_scale':[3,2],'host_sanitizers':True,'arm_original_create':True,'exact_recovery':True,'partial_write_rollback':True,'camera_pixels_verified':False}
    if options.film_curves:
        proof.update(fivepoint=True,curve_case_count=3*2*7*128,
                     all_single_control_values=False,all_single_curve_values=True,
                     all_tone_combinations_host=False,tone_combination_count=0,
                     exact_recovery=False,partial_write_rollback=True,camera_written=False,flash_ready=False,
                     scope='FL3 preview candidate and paired CAP write/rollback with simulated properties; original Create packing runs in QEMU RAM')
    (OUT/'proof.json').write_text(json.dumps(proof,indent=2)+'\n')
if __name__=='__main__':main()
