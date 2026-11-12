#!/usr/bin/env python3
"""Private-data host/ARM tests for adjustable capture tables. No device I/O."""
import hashlib,json,shutil,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'.lab/native-capture-controls-test'
LEGACY=ROOT/'.lab/native-module-capture-look'
ROUTE=ROOT/'.lab/lut3d-capture-look'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(args,**kw):return subprocess.run(args,check=True,**kw)
def main():
    OUT.mkdir(parents=True,exist_ok=True);(OUT/'proof.json').unlink(missing_ok=True)
    mp=json.loads((LEGACY/'proof.json').read_text())
    assert mp['module_sha256']=='1216dda332c42c6378fd993ccb89781d6229150c00798191835232de3923b675'
    assert sha(LEGACY/'a7-fl-module-data.h')==mp['artifact_sha256']['a7-fl-module-data.h']
    route=json.loads((ROUTE/'proof.json').read_text())
    assert sha(ROUTE/'proof.json')==mp['capture_look']['source_qemu_proof_sha256']
    for p,d in route['source_sha256'].items():assert sha(ROOT/p)==d,p
    for name,r in route['native_ranges'].items():assert sha(ROUTE/(name+'.bin'))==r['sha256'],name
    data=(ROUTE/'table_inputs.bin').read_bytes()
    assert hashlib.sha256(data[:5120]).hexdigest()==route['table_input_sha256']
    assert hashlib.sha256(data[5120:9728]).hexdigest()==route['descriptor_controls_sha256']
    assert data[9728]==1
    for i,r in enumerate(route['capture_candidates']):assert hashlib.sha256(data[9729+i*1280:9729+(i+1)*1280]).hexdigest()==r['candidate_sha256']
    shutil.copyfile(LEGACY/'a7-fl-module-data.h',OUT/'a7-fl-module-data.h')
    sources=['payloads/a7-fl-capture-controls.c','research/native_capture_controls_test.c']
    flags=['-O2','-Wall','-Wextra','-Werror','-Wno-unused-function','-I'+str(ROOT/'payloads'),'-I'+str(OUT)]
    (OUT/'host.c').write_text('''#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
static unsigned long checks;
void cc_check(int ok,const char *why){checks++;if(!ok){fprintf(stderr,"FAIL %s\\n",why);exit(1);}}
void cc_pack(const uint8_t *p,unsigned n){(void)p;(void)n;}
extern void a7_capture_controls_tests(void);
int main(void){a7_capture_controls_tests();printf("CAPTURE_CONTROLS_HOST_PASSED: %lu checks\\n",checks);return 0;}
''')
    run(['clang',*flags,'-fsanitize=address,undefined','-fno-omit-frame-pointer','-DA7_CC_EXHAUSTIVE',
         str(OUT/'host.c'),*[str(ROOT/p) for p in sources],'-o',str(OUT/'host-test')])
    host=run([str(OUT/'host-test')],capture_output=True,timeout=120)
    (OUT/'host.log').write_bytes(host.stdout+host.stderr);print(host.stdout.decode(),end='')
    # Existing original generator, selector and packing fixture; only its entry
    # is replaced, and a new test calls the unmodified native Create function.
    for p in ROUTE.iterdir():
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
    run(['arm-none-eabi-gcc',*flags,'-I'+str(ROOT/'research'),'-mcpu=cortex-a9','-mthumb','-mfloat-abi=soft','-mno-unaligned-access',
         '-ffreestanding','-fno-builtin','-nostdlib','-T','guest.ld','start.S','native.S','arm.c',
         *[str(ROOT/p) for p in sources],'-lgcc','-o','test.elf'],cwd=OUT)
    arm=run(['qemu-system-arm','-M','virt','-cpu','cortex-a15','-m','1024','-nodefaults','-audio','none','-nic','none','-display','none','-monitor','none','-serial','stdio','-semihosting-config','enable=on,target=native','-device',f'loader,file={OUT}/test.elf,cpu-num=0'],capture_output=True,timeout=60)
    log=arm.stdout+arm.stderr;(OUT/'qemu.log').write_bytes(log);print(log.decode(),end='')
    assert b'CAPTURE_CONTROLS_ARM_PASSED' in log and b'FAIL ' not in log
    sources+=['payloads/a7-fl-capture-controls.h','payloads/a7-fl-color.h','research/native_capture_controls_test.py','research/lut3d_harness.c']
    proof={'source_sha256':{p:sha(ROOT/p) for p in sources},'artifacts':{p:sha(OUT/p) for p in ('host-test','test.elf','host.log','qemu.log','a7-fl-module-data.h','arm.c','native.S','guest.ld','start.S')},
           'legacy_module_sha256':mp['module_sha256'],'legacy_capture_proof_sha256':sha(ROUTE/'proof.json'),
           'all_single_control_values':True,'all_tone_combinations_host':True,'tone_combination_count':19**3*10*2,
           'tested_levels':list(range(1,9)),'max_packed_delta':[24,32,32],
           'base_delta_scale':[3,2],'host_sanitizers':True,'arm_original_create':True,'exact_recovery':True,'partial_write_rollback':True,'camera_pixels_verified':False}
    (OUT/'proof.json').write_text(json.dumps(proof,indent=2)+'\n')
if __name__=='__main__':main()
