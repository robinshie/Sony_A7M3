/* Execute original wrappers and original kernel writer around the new core. */
#include <stdarg.h>
#include <stdint.h>
#include "a7-fl-runtime.h"
#include "a7-fl-runtime-prefs.h"
#include "a7-fl-runtime-control.h"
#include "a7-fl-runtime-recovery.h"
#include "a7-fl-color.h"
#define L 0x40300000u
#define K 0x40400000u
#define ORIGINAL ((const uint8_t *)0x40600000u)
#define CANDIDATE (ORIGINAL+1280)
#define EXPAND ((const uint16_t *)(CANDIDATE+1280))
#define COMPRESS (CANDIDATE+1280+258)
#define OTHER (ORIGINAL+3332)
#define CALL(off,type) ((type)(uintptr_t)(L+(off)+1))
static struct a7_fl_context context;
static struct a7_fl_control control;
static unsigned stored,store_failure,store_write_count;
static struct a7_fl_preference saved;
static uint8_t data_guarded[1282];
static uint8_t other_tables_data[3][1280];
static unsigned identity_calls,identity_failure;
static unsigned properties_size,attributes,callback_count,write_calls,rpc_calls;
static unsigned lock_depth,saves,scenario,failure,reentrant,tests;
static uint32_t header[16],property[16];
#ifdef A7_FL_SEPARATE_KERNEL_STACK
extern int call_kernel_writer(unsigned,unsigned,const void *);
#endif
uint8_t mock_locks[28*256];
static void put(const char *s) {
    volatile unsigned *u=(volatile unsigned *)0x09000000;
    while(*s) {while(u[6]&32) {}u[0]=*s++;}
}
static void finish(void) {
    register unsigned r0 __asm__("r0")=0x18;
    register unsigned r1 __asm__("r1")=0x20026;
    __asm__ volatile("svc 0x123456" : "+r"(r0), "+r"(r1) : : "memory");
    while(1) {}
}
static void check(int ok,const char *s) {if(!ok) {put("FAIL ");put(s);put("\n");finish();}}
static void bytes(void *d,const void *s,unsigned n) {for(unsigned i=0;i<n;i++) ((uint8_t *)d)[i]=((const uint8_t *)s)[i];}
static void clear(void *d,unsigned n) {for(unsigned i=0;i<n;i++) ((uint8_t *)d)[i]=0;}
static int same(const void *a,const void *b,unsigned n) {for(unsigned i=0;i<n;i++) if(((const uint8_t *)a)[i]!=((const uint8_t *)b)[i]) return 0;return 1;}
void *mock_header(void) {return header;}
void mock_lock(void *p) {check(p==mock_locks+3*28 && lock_depth==0,"kernel subsystem lock");lock_depth=1;}
void mock_unlock(void *p) {check(p==mock_locks+3*28 && lock_depth==1,"kernel unlock");lock_depth=0;}
void *mock_search(uint32_t id) {return id==A7_FL_PROPERTY?property:0;}
unsigned mock_attr(void *p) {check(p==property,"kernel attr token");return attributes;}
unsigned mock_id1(void *p) {check(p==header,"kernel header token");return 1;}
unsigned mock_vmax(void *p) {check(p==property,"kernel size token");return 0;}
unsigned mock_size(void *p) {check(p==property,"kernel fixed-size token");return properties_size;}
void *mock_size_ptr(void *p) {(void)p;check(0,"fixed-size LUT must not resize");return 0;}
void *mock_data(void *p) {check(p==property && lock_depth==1,"kernel data under lock");return data_guarded+1;}
void mock_log(void) {}
void *mock_copy(void *d,const void *s,unsigned n) {
    check(d==data_guarded+1 && n==1280 && lock_depth==1,"kernel write copy bounds");bytes(d,s,n);return d;
}
unsigned mock_copy_user(void *d,const void *s,unsigned n) {mock_copy(d,s,n);return 0;}
void mock_zero(void *d,unsigned n) {(void)d;(void)n;check(0,"unexpected bad user pointer");}
void mock_notify(unsigned id,unsigned n,const void *p) {
    check(id==A7_FL_PROPERTY && n==1280 && lock_depth==0,"callback after lock release");
    check(same(data_guarded+1,p,1280),"callback sees committed RAM");callback_count++;
    if(reentrant) check(a7_fl_set(&context,0)==A7_FL_BUSY,"recursive UI entry refuses without deadlock");
}
int fake_rpc(int *result,unsigned queue,unsigned command,unsigned count,...) {
    check(queue==0x3e014d,"native queue");rpc_calls++;
    va_list ap;va_start(ap,count);uint32_t a[3]={0,0,0};
    check(count<=3,"native varargs count");for(unsigned i=0;i<count;i++) a[i]=va_arg(ap,unsigned);va_end(ap);
    if(command==0) {check(count==1 && a[0]>=A7_FL_PROPERTY && a[0]<=A7_FL_PROPERTY+3,"native size ABI");*result=(int)properties_size;}
    else if(command==2) {check(count==1 && a[0]>=A7_FL_PROPERTY && a[0]<=A7_FL_PROPERTY+3,"native attr ABI");*result=(int)attributes;}
    else if(command==3) {
        check(count==2 && a[0]>=A7_FL_PROPERTY && a[0]<=A7_FL_PROPERTY+3,"native read ABI");
        const void *source=a[0]==A7_FL_PROPERTY?data_guarded+1:other_tables_data[a[0]-A7_FL_PROPERTY-1];
        bytes((void *)(uintptr_t)a[1],source,1280);*result=failure==5?1279:1280;
    } else if(command==8) {
        check(count==3,"native write three arguments");write_calls++;
        if((failure==1&&write_calls==1)||(failure==4&&write_calls>=2)) {*result=-1;return 0;}
#ifdef A7_FL_SEPARATE_KERNEL_STACK
        *result=call_kernel_writer(a[0],a[1],(const void *)(uintptr_t)a[2]);
#else
        *result=((int (*)(unsigned,unsigned,const void *))(K+0x167c))(a[0],a[1],(const void *)(uintptr_t)a[2]);
#endif
        if(write_calls==1 && (failure==2||failure==4)) *result=-1;
        if(write_calls==1 && (failure==3||failure==4)) bytes(data_guarded+641,ORIGINAL+640,640);
    } else if(command==14) {check(count==1 && a[0]==3,"native sync subsystem ABI");saves++;*result=-77;}
    else if(command==15) {check(count==0,"native sync all ABI");saves++;*result=-77;}
    else check(0,"unexpected RPC opcode");
    return 0;
}
static const struct a7_fl_api api={
    CALL(0x1174,int (*)(uint32_t)),CALL(0x11d4,int (*)(uint32_t)),
    CALL(0x1204,int (*)(uint32_t,void *)),CALL(0x1358,int (*)(uint16_t,uint32_t,const void *))};
static void reset(void) {
    clear(&context,sizeof context);bytes(data_guarded+1,ORIGINAL,1280);
    data_guarded[0]=data_guarded[1281]=0xa5;
    properties_size=1280;attributes=8;callback_count=write_calls=rpc_calls=lock_depth=saves=failure=reentrant=0;
    for(unsigned i=0;i<3;i++)bytes(other_tables_data[i],OTHER+i*1280,1280);
    identity_calls=identity_failure=0;
}
static int init(void) {return a7_fl_init(&context,&api,ORIGINAL,a7_fl_crc(ORIGINAL,1280),CANDIDATE,a7_fl_crc(CANDIDATE,1280));}
static void test_native_abi(void) {
    reset();check(api.size(A7_FL_PROPERTY)==1280 && api.attr(A7_FL_PROPERTY)==8,"native query returns values");
    uint8_t readback[1280];check(api.read(A7_FL_PROPERTY,readback)==1280 && same(readback,ORIGINAL,1280),"native read count and data");
    check(api.write(4,A7_FL_PROPERTY,CANDIDATE)==-4 && callback_count==0,"kernel rejects subsystem mismatch");
    check(api.write(3,A7_FL_PROPERTY,CANDIDATE)==1280 && callback_count==1,"kernel writes and reports byte count");
    check(data_guarded[0]==0xa5 && data_guarded[1281]==0xa5,"kernel destination guard");
    attributes=1;check(api.write(3,A7_FL_PROPERTY,ORIGINAL)==-3,"kernel read-only attribute");
    CALL(0x14f0,void (*)(uint16_t))(3);CALL(0x151c,void (*)(void))();
    check(saves==2,"native sync wrappers have distinct opcodes");tests+=8;
}
static void test_core(void) {
    reset();check(init()==0 && context.state==A7_FL_OFF && write_calls==0,"init inspects without write");tests++;
    reentrant=1;check(a7_fl_set(&context,1)==0 && context.state==A7_FL_ON,"enable native LUT");
    check(write_calls==1 && callback_count==1 && same(data_guarded+1,CANDIDATE,1280),"enable bytes and native callback");tests+=2;
    check(a7_fl_set(&context,1)==0 && write_calls==1,"no repeated write");tests++;
    check(a7_fl_set(&context,0)==0 && context.state==A7_FL_OFF && same(data_guarded+1,ORIGINAL,1280),"disable restores original");
    check(saves==0,"runtime never requests flash sync");tests+=2;
    for(unsigned mode=1;mode<=4;mode++) {
        reset();check(init()==0,"fault fixture init");failure=mode;
        int rc=a7_fl_set(&context,1);
        if(mode==4) check(rc==A7_FL_RECOVERY && context.state==A7_FL_FAULT,"explicit recovery failure state");
        else check(rc<0 && context.state==A7_FL_OFF && same(data_guarded+1,ORIGINAL,1280),"interrupted write restored");
        check(write_calls==2 && saves==0,"failure recovery bounded and no sync");tests+=2;
    }
    reset();check(init()==0,"foreign fixture init");data_guarded[1]^=127;
    check(a7_fl_set(&context,1)==A7_FL_FOREIGN && write_calls==0,"foreign current LUT refused");tests++;
    reset();properties_size=1279;check(init()==A7_FL_LAYOUT && write_calls==0,"size mismatch refused");tests++;
    reset();attributes=9;check(init()==A7_FL_LAYOUT && write_calls==0,"attribute mismatch refused");tests++;
    reset();failure=5;check(init()==A7_FL_READ && write_calls==0,"short read refused");tests++;
    reset();check(a7_fl_init(&context,&api,ORIGINAL,0,CANDIDATE,0)==A7_FL_TABLE && rpc_calls==0,"bad CRC refused before API");tests++;
    reset();bytes(data_guarded+1,CANDIDATE,1280);check(init()==0 && context.state==A7_FL_ON && write_calls==0,"attach to already enabled state");tests++;
    check(a7_fl_set(&context,2)==A7_FL_ARGUMENT && write_calls==0,"invalid enum refused");tests++;
}
static void test_replacement(void) {
    uint8_t next[1280];bytes(next,CANDIDATE,1280);
    next[0]=next[0]==63?62:(uint8_t)(next[0]+1);
    uint32_t crc=a7_fl_crc(next,1280);
    reset();check(init()==0,"replacement init");
    check(a7_fl_replace_candidate(&context,next,crc)==0 && write_calls==0 && same(context.candidate,next,1280),"off replacement owns data without write");tests++;
    next[0]^=1;check(context.candidate[0]!=next[0],"replacement input lifetime independent");next[0]^=1;tests++;
    check(a7_fl_set(&context,1)==0 && same(data_guarded+1,next,1280),"new candidate enabled");tests++;
    check(a7_fl_replace_candidate(&context,CANDIDATE,a7_fl_crc(CANDIDATE,1280))==0 && same(context.candidate,CANDIDATE,1280) && same(data_guarded+1,CANDIDATE,1280),"on replacement native write and readback");tests++;
    unsigned before=write_calls;check(a7_fl_replace_candidate(&context,CANDIDATE,a7_fl_crc(CANDIDATE,1280))==0 && write_calls==before,"same replacement avoids write");tests++;
    for(unsigned mode=1;mode<=4;mode++) {
        reset();check(init()==0 && a7_fl_set(&context,1)==0,"replacement fault init");write_calls=0;failure=mode;
        int rc=a7_fl_replace_candidate(&context,next,crc);
        if(mode==4)check(rc==A7_FL_RECOVERY && context.state==A7_FL_FAULT,"replacement recovery failure explicit");
        else check(rc<0 && context.state==A7_FL_OFF && same(data_guarded+1,ORIGINAL,1280),"replacement failure restores original");
        check(same(context.candidate,CANDIDATE,1280) && write_calls==2 && saves==0,"failure retains old owned candidate and no sync");tests+=2;
    }
    reset();check(init()==0,"replacement rejection init");
    check(a7_fl_replace_candidate(&context,next,crc^1)==A7_FL_TABLE && write_calls==0,"replacement CRC reject");tests++;
    next[1279]^=1;check(a7_fl_replace_candidate(&context,next,a7_fl_crc(next,1280))==A7_FL_TABLE && write_calls==0,"replacement tail reject");next[1279]^=1;tests++;
    next[0]=64;check(a7_fl_replace_candidate(&context,next,a7_fl_crc(next,1280))==A7_FL_TABLE && write_calls==0,"replacement native code range reject");tests++;
}
static void test_preferences(void) {
    static const uint8_t hash[32]={1,2,3,4,5};static const char build[24]="a7fl-runtime-test-v1";
    struct a7_fl_preference p={7,1,{-9,9,-2,4,-1,-3,3,0},0x12345678},out;
    uint8_t a[128],b[128],scratch[128],bad_hash[32];char bad_build[24];
    check(a7_fl_preference_encode(a,&p,hash,build)==0 && a7_fl_preference_decode(&out,a,128,hash,build)==0 && same(&out,&p,sizeof p),"preference roundtrip");tests++;
    for(unsigned i=0;i<128;i++) {
        bytes(scratch,a,128);scratch[i]^=1;
        check(a7_fl_preference_decode(&out,scratch,128,hash,build)<0 && same(&out,&p,sizeof p),"single-byte damaged record rejected without output mutation");tests++;
        check(a7_fl_preference_decode(&out,a,i,hash,build)<0,"every truncated record rejected");tests++;
    }
    p.generation++;check(a7_fl_preference_encode(b,&p,hash,build)==0,"next record encode");
    check(a7_fl_preference_choose(&out,a,128,b,128,hash,build)==1 && out.generation==8,"newest valid slot chosen");tests++;
    check(a7_fl_preference_choose(&out,b,128,a,128,hash,build)==0 && out.generation==8,"generation independent of slot number");tests++;
    check(a7_fl_preference_choose(&out,a,128,b,127,hash,build)==0 && out.generation==7,"torn inactive record falls back");tests++;
    check(a7_fl_preference_choose(&out,0,0,0,0,hash,build)==-1,"no valid records explicit");tests++;
    check(a7_fl_preference_choose(&out,b,128,b,128,hash,build)==0,"same generation identical accepted");tests++;
    p.enabled=0;check(a7_fl_preference_encode(scratch,&p,hash,build)==0 && a7_fl_preference_choose(&out,b,128,scratch,128,hash,build)==-2,"conflicting same-generation records rejected");tests++;
    bytes(bad_hash,hash,32);bad_hash[0]^=1;bytes(bad_build,build,24);bad_build[0]^=1;
    check(a7_fl_preference_decode(&out,a,128,bad_hash,build)<0 && a7_fl_preference_decode(&out,a,128,hash,bad_build)<0,"factory hash and build binding");tests++;
    bytes(scratch,a,128);p.parameters[0]=10;
    check(a7_fl_preference_encode(scratch,&p,hash,build)<0 && same(scratch,a,128),"invalid control leaves output untouched");tests++;
    p.parameters[0]=0;p.generation=0;check(a7_fl_preference_encode(b,&p,hash,build)<0,"zero generation rejected");tests++;
}
static int fake_store(void *ctx,const struct a7_fl_preference *p) {
    check(ctx==&stored,"store context ABI");
    if(!stored)check(write_calls==store_write_count,"desired record precedes RAM write");
    stored++;
    check(a7_fl_control_apply(&control,8,0)==0,"store callback reentry fails without deadlock");
    if(stored==store_failure)return -1;
    saved=*p;return 0;
}
static void control_reset(void) {
    reset();clear(&control,sizeof control);clear(&saved,sizeof saved);
    stored=store_failure=store_write_count=0;check(init()==0,"control runtime init");
    struct a7_fl_preference p={1,0,{0,0,0,0,0,0,3,0},0};p.candidate_crc=a7_fl_crc(CANDIDATE,1280);
    check(a7_fl_control_init(&control,&context,CANDIDATE,EXPAND,COMPRESS,&p,fake_store,&stored)==0,"control bind exact generated LUT");
}
static void test_control(void) {
    control_reset();check(stored==0 && write_calls==0,"bind never persists or writes");tests++;
    check(a7_fl_control_apply(&control,8,1)==1 && context.state==A7_FL_ON && stored==1 && saved.enabled==1 && saved.generation==2,"mode callback persisted before native apply");tests++;
    check(a7_fl_control_apply(&control,0,2)==1 && context.state==A7_FL_ON && stored==2 && saved.parameters[0]==2 && !same(data_guarded+1,CANDIDATE,1280),"contrast generates changed native LUT");tests++;
    check(a7_fl_control_apply(&control,8,0)==1 && context.state==A7_FL_OFF && same(data_guarded+1,ORIGINAL,1280),"off restores factory through callback");tests++;
    unsigned before=write_calls;
    check(a7_fl_control_apply(&control,4,-2)==1 && context.state==A7_FL_OFF && write_calls==before && saved.parameters[4]==-2,"off slider saves recipe without native write");tests++;
    before=stored;
    for(unsigned f=5;f<8;f++){check(a7_fl_control_apply(&control,f,1)==0 && stored==before,"unsupported spatial control never stored");tests++;}
    check(a7_fl_control_apply(&control,0,10)==0 && stored==before,"invalid scalar control rejected");tests++;
    check(a7_fl_control_apply(&control,8,2)==0 && stored==before,"invalid mode rejected");tests++;
    control_reset();store_failure=1;
    check(a7_fl_control_apply(&control,8,1)==0 && context.state==A7_FL_OFF && write_calls==0 && control.preference.generation==1 && control.last_error==A7_FL_CONTROL_PERSIST,"failed durable prewrite prevents all camera changes");tests++;
    control_reset();failure=1;
    check(a7_fl_control_apply(&control,8,1)==0 && context.state==A7_FL_OFF && control.fault && stored==2 && saved.generation==3 && saved.enabled==0,"native failure records newer recovery Off");tests++;
    before=stored;check(a7_fl_control_apply(&control,8,1)==0 && stored==before,"fault disables further preview");tests++;
    control_reset();failure=1;store_failure=2;
    check(a7_fl_control_apply(&control,8,1)==0 && context.state==A7_FL_OFF && control.fault && control.last_error==A7_FL_CONTROL_RECOVERY_PERSIST && saved.enabled==1,"recovery record failure explicit fatal state");tests++;
    control_reset();control.preference.generation=control.committed.generation=0xfffffffe;
    check(a7_fl_control_apply(&control,8,1)==0 && stored==0 && write_calls==0 && control.last_error==A7_FL_CONTROL_GENERATION,"generation overflow cannot erase recovery space");tests++;
    control_reset();check(a7_fl_set(&context,1)==0,"foreign mode fixture");
    check(a7_fl_control_apply(&control,8,1)==0 && stored==0 && control.fault,"external mode change requires reconciliation");tests++;
}
static void test_preview(void) {
    control_reset();
    check(a7_fl_control_preview(&control,8,1)==1 && context.state==A7_FL_ON && control.dirty && stored==0,"mode preview RAM only");tests++;
    for(int value=-9;value<=9;value++)check(a7_fl_control_preview(&control,0,value)==1,"wheel preview accepted");
    check(stored==0 && control.committed.generation==1 && control.committed.parameters[0]==0 && control.preference.parameters[0]==9,"nineteen wheel steps make no filesystem write");tests++;
    store_write_count=write_calls;unsigned before=write_calls;
    check(a7_fl_control_commit(&control)==0 && stored==1 && write_calls==before && !control.dirty && saved.parameters[0]==9 && saved.enabled==1 && saved.generation==2,"explicit confirm persists once without native write");tests++;
    check(a7_fl_control_commit(&control)==0 && stored==1,"repeated confirmation no write");tests++;
    check(a7_fl_control_preview(&control,0,-9)==1 && control.dirty,"new pending preview");
    check(a7_fl_control_cancel(&control)==0 && stored==1 && !control.dirty && control.preference.parameters[0]==9 && context.state==A7_FL_ON,"cancel restores committed ON recipe without file write");tests++;
    check(a7_fl_control_preview(&control,8,0)==1 && stored==1 && context.state==A7_FL_OFF,"Off is also RAM preview");tests++;
    check(a7_fl_control_cancel(&control)==0 && stored==1 && context.state==A7_FL_ON,"cancel Off restores committed enabled mode");tests++;
    control_reset();check(a7_fl_control_preview(&control,0,5)==1 && a7_fl_control_preview(&control,8,1)==1,"cancel initial previews");
    check(a7_fl_control_cancel(&control)==0 && stored==0 && context.state==A7_FL_OFF && same(data_guarded+1,ORIGINAL,1280) && same(context.candidate,CANDIDATE,1280),"cancel initial experiment restores baseline and candidate");tests++;
    control_reset();check(a7_fl_control_preview(&control,8,1)==1,"store failure preview");store_failure=1;store_write_count=write_calls;before=write_calls;
    check(a7_fl_control_commit(&control)==A7_FL_CONTROL_PERSIST && control.dirty && write_calls==before && control.committed.enabled==0,"failed confirm stays visibly uncommitted");tests++;
    check(a7_fl_control_cancel(&control)==0 && context.state==A7_FL_OFF && stored==1,"failed confirmation can be canceled without file write");tests++;
    control_reset();failure=1;
    check(a7_fl_control_preview(&control,8,1)==0 && control.fault && context.state==A7_FL_OFF && stored==0,"preview write failure restores factory without file write");tests++;
    control_reset();check(a7_fl_control_preview(&control,0,3)==1 && a7_fl_control_preview(&control,0,0)==1 && !control.dirty && stored==0,"return to committed value clears dirty state");tests++;
    check(a7_fl_control_preview(&control,5,1)==0 && stored==0,"preview rejects unsupported sharpness");tests++;
    control_reset();check(a7_fl_control_preview(&control,0,2)==1,"confirmed adapter pending fixture");
    check(a7_fl_control_apply(&control,0,2)==1 && stored==1 && !control.dirty && saved.parameters[0]==2,"confirmed adapter commits an already previewed value");tests++;
}
static int identity_guard(void *opaque) {
    check(opaque==&identity_calls,"identity callback context");identity_calls++;
    if(identity_failure==1 || (identity_failure==2 && identity_calls==2))return 0;
    if(identity_calls==2 && identity_failure==3)other_tables_data[1][0]^=1;
    if(identity_calls==2 && identity_failure==4)data_guarded[1]^=1;
    return 1;
}
static struct a7_fl_recovery recovery_inputs(void) {
    struct a7_fl_recovery r;
    r.api=&api;r.original[0]=ORIGINAL;r.original_crc[0]=a7_fl_crc(ORIGINAL,1280);
    for(unsigned i=1;i<4;i++) {r.original[i]=OTHER+(i-1)*1280;r.original_crc[i]=a7_fl_crc(r.original[i],1280);}
    r.base_fl=CANDIDATE;r.base_fl_crc=a7_fl_crc(CANDIDATE,1280);r.expand=EXPAND;r.compress=COMPRESS;
    r.identity_guard=identity_guard;r.identity_context=&identity_calls;return r;
}
static void test_recognition(void) {
    uint8_t generated[1280],again[1280];int found[5];unsigned trials;
    check(a7_fl_recognize(CANDIDATE,CANDIDATE,EXPAND,COMPRESS,found,&trials)==1 && trials==1,"base FL recognized immediately");tests++;
    for(unsigned bits=0;bits<32;bits++) {
        A7FLColorParams p={bits&1?9:-9,bits&2?9:-9,bits&4?9:-9,bits&8?9:0,bits&16?9:-9};
        check(a7_fl_adjust_lut(CANDIDATE,1280,EXPAND,COMPRESS,&p,generated,1280)==0,"corner candidate generation");
        check(a7_fl_recognize(generated,CANDIDATE,EXPAND,COMPRESS,found,&trials)==1 && trials<=68590,"all extreme historical candidate combinations recognized");
        A7FLColorParams q={found[0],found[1],found[2],found[3],found[4]};
        check(a7_fl_adjust_lut(CANDIDATE,1280,EXPAND,COMPRESS,&q,again,1280)==0 && same(generated,again,1280),"recognized parameters reproduce all bytes");tests++;
    }
    uint32_t seed=0x12345678;
    for(unsigned n=0;n<32;n++) {
        int values[5];for(unsigned i=0;i<5;i++){seed=seed*1664525+1013904223;values[i]=(int)((seed>>16)%19)-9;}values[3]=(int)((seed>>8)%10);
        A7FLColorParams p={values[0],values[1],values[2],values[3],values[4]};
        check(a7_fl_adjust_lut(CANDIDATE,1280,EXPAND,COMPRESS,&p,generated,1280)==0,"random candidate generation");
        check(a7_fl_recognize(generated,CANDIDATE,EXPAND,COMPRESS,found,&trials)==1 && trials<=68590,"random historical candidate recognized");tests++;
    }
    generated[1215]^=1;check(a7_fl_recognize(generated,CANDIDATE,EXPAND,COMPRESS,found,&trials)==0,"foreign tail refused");generated[1215]^=1;tests++;
    generated[405]^=1;check(a7_fl_recognize(generated,CANDIDATE,EXPAND,COMPRESS,found,&trials)==0,"foreign chroma refused despite valid shape");tests++;
    bytes(generated,CANDIDATE,1280);generated[0]=64;
    check(a7_fl_recognize(generated,CANDIDATE,EXPAND,COMPRESS,found,&trials)==0 && trials==68590,"foreign tone exhaustive bounded rejection");tests++;
}
static void test_recovery(void) {
    int found[5];reset();struct a7_fl_recovery r=recovery_inputs();
    check(a7_fl_restore_baseline(&r,found)==0 && write_calls==0,"factory baseline never rewritten");tests++;
    bytes(data_guarded+1,CANDIDATE,1280);
    check(a7_fl_restore_baseline(&r,found)==1 && write_calls==1 && same(data_guarded+1,ORIGINAL,1280) && saves==0,"known base candidate restored with all guards");tests++;
    reset();A7FLColorParams p={7,-8,5,6,-7};check(a7_fl_adjust_lut(CANDIDATE,1280,EXPAND,COMPRESS,&p,data_guarded+1,1280)==0,"historic recovery generation");
    check(a7_fl_restore_baseline(&r,found)==1 && write_calls==1 && same(data_guarded+1,ORIGINAL,1280),"historic candidate independent of preference slots restored");tests++;
    reset();bytes(data_guarded+1,CANDIDATE,1280);data_guarded[406]^=1;
    check(a7_fl_restore_baseline(&r,found)==A7_FL_RECOVERY_UNRECOGNIZED && write_calls==0,"arbitrary calibration never overwritten");tests++;
    for(unsigned mode=1;mode<=4;mode++) {
        reset();bytes(data_guarded+1,CANDIDATE,1280);identity_failure=mode;
        int rc=a7_fl_restore_baseline(&r,found);
        check(rc==(mode<=2?A7_FL_RECOVERY_IDENTITY:mode==3?A7_FL_RECOVERY_OTHER_TABLE:A7_FL_FOREIGN) && write_calls==0,"identity and cross-table prewrite changes refused");tests++;
    }
    reset();bytes(data_guarded+1,CANDIDATE,1280);other_tables_data[0][0]^=1;
    check(a7_fl_restore_baseline(&r,found)==A7_FL_RECOVERY_OTHER_TABLE && write_calls==0,"modified other LUT refuses restoration");tests++;
    reset();r.base_fl_crc^=1;check(a7_fl_restore_baseline(&r,found)==A7_FL_TABLE && write_calls==0,"wrong immutable base CRC refused");r.base_fl_crc^=1;tests++;
    reset();bytes(data_guarded+1,CANDIDATE,1280);failure=1;
    check(a7_fl_restore_baseline(&r,found)==1 && write_calls==2 && same(data_guarded+1,ORIGINAL,1280),"bounded restoration retry after failed native write");tests++;
    reset();bytes(data_guarded+1,CANDIDATE,1280);failure=4;
    check(a7_fl_restore_baseline(&r,found)==A7_FL_RECOVERY && write_calls==2,"restoration acknowledgement failure remains explicit");tests++;
}
void guest_main(void) {
    /* Model the kernel thread address limit for its genuine __copy_from_user
     * branch. The rest of thread_info is never touched in this fixed writer.
     */
    *(volatile uint32_t *)0x40ffe008=0x5f000000;
    scenario=0;test_native_abi();scenario=1;test_core();test_replacement();test_preferences();test_control();test_preview();test_recognition();test_recovery();
    check(tests==421,"coverage count");
    put("NATIVE_FL_RUNTIME_PASSED: 421 checks; original libbackup wrappers and kernel writer; preference controls; preview/commit; exact historical recovery\n");
    put("NO_CAMERA_WRITE; OSAL_KERNEL_SERVICES_MODELED; NO_DURABLE_IO_OR_MENU_LIFECYCLE_TEST\n");
    finish();
}
