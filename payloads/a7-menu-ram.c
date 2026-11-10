/* Temporary menu-routing experiment. No firmware or backup writes.
 * The allocation is retained until power-off so cached UI pointers stay valid.
 * Native bytes and the replacement dispatcher come from a private build header.
 */
#define A7_RUNTIME_LIBRARY_ONLY
#include "a7-runtime-probe.c"
#include "menu-ram-data.h"
#ifndef ACTION
#define ACTION 0
#endif
struct State {
    uint32_t magic,base,old_table,old_count;
    uint32_t trace[4],entries[200];
};
static struct {
    uint32_t magic,action,status,base,allocation,code_changed,count,trace[4];
    int32_t error;
} result;
#ifdef MENU_DEBUG
#define DEBUG(s) sc3(4,1,(long)(s),sizeof(s)-1)
#else
#define DEBUG(s) ((void)0)
#endif
static long map_page(void) {
    register long r7 __asm__("r7")=192;
    register long r0 __asm__("r0")=0;
    register long r1 __asm__("r1")=4096;
    register long r2 __asm__("r2")=3;
    register long r3 __asm__("r3")=0x22;
    register long r4 __asm__("r4")=-1;
    register long r5 __asm__("r5")=0;
    __asm__ volatile("svc #0" : "+r"(r0) : "r"(r7),"r"(r1),"r"(r2),"r"(r3),"r"(r4),"r"(r5) : "memory","cc");
    return r0;
}
static int same(const volatile unsigned char *a,const unsigned char *b,unsigned n) {
    for(unsigned i=0;i<n;i++) if(a[i]!=b[i]) return 0;
    return 1;
}
static void copy(volatile unsigned char *a,const unsigned char *b,unsigned n) {
    for(unsigned i=0;i<n;i++) a[i]=b[i];
}
static int writable(uint32_t address,uint32_t size) {
    for(const char *p=report.maps;*p;) {
        const char *next=p;uint32_t lo=hex(&next);
        if(*next++!='-') return 0;
        uint32_t hi=hex(&next);
        if(next[0]==' '&&next[1]=='r'&&next[2]=='w'&&lo<=address&&address<=hi&&size<=hi-address) return 1;
        while(*p&&*p!='\n') p++;
        if(*p) p++;
    }
    return 0;
}
static int code_write(uint32_t address,const unsigned char *bytes,unsigned n) {
    long rc=sc3(125,address&~4095u,4096,7);
    if(rc) {result.error=rc;return 0;}
    copy((void *)(uintptr_t)address,bytes,n);
    rc=sc3(0xf0002,address,address+n,0);
    long protect=sc3(125,address&~4095u,4096,5);
    if(rc||protect) {result.error=rc?rc:protect;return 0;}
    return same((void *)(uintptr_t)address,bytes,n);
}
static void run(void) {
    DEBUG("MENU_RUN\n");
    report.maps_n=read_proc("/proc/self/maps",report.maps,sizeof report.maps);
    inspect_view();
    DEBUG("MENU_LAYOUT_READ\n");
    if(!report.view_base) {result.error=-1;return;}
    uint32_t base=report.view_base, code=base+0x5b98dc;
    result.base=base;
    if(!readable(code,sizeof original_dispatch)||!writable(base+0xa60c90,40)) {result.error=-2;return;}
    volatile uint32_t *root=(void *)(uintptr_t)(base+0xa60c90);
    struct State *state=0;
    unsigned char replacement[sizeof original_dispatch];
    copy(replacement,original_dispatch,sizeof replacement);
    copy(replacement,patched_dispatch,sizeof patched_dispatch);
    if(root[1]==20&&root[2]==97&&root[0]>=32&&writable(root[0]-32,sizeof(struct State))) {
        state=(void *)(uintptr_t)(root[0]-32);
        if(state->magic!=0x41374d52||state->base!=base||state->old_table!=base+0xa60998||state->old_count!=19)
            {result.error=-3;return;}
        uint32_t ptr=(uintptr_t)state->trace;
        copy(replacement+TRACE_OFFSET,(void *)&ptr,4);
        if(!same((void *)(uintptr_t)code,replacement,sizeof replacement)) {result.error=-4;return;}
        result.allocation=(uintptr_t)state;result.count=root[1];result.code_changed=1;
        for(unsigned i=0;i<4;i++) result.trace[i]=state->trace[i];
        if(ACTION==2) {
            root[1]=19;
            __asm__ volatile("dmb ish" ::: "memory");
            root[0]=state->old_table;
            if(!code_write(code,original_dispatch,sizeof original_dispatch)) {result.error=-5;return;}
            result.code_changed=0;result.count=19;result.status=3;
        } else result.status=2;
        return;
    }
    if(ACTION!=0) {result.error=-6;return;}
    if(report.view_status!=2||!same((void *)(uintptr_t)code,original_dispatch,sizeof original_dispatch))
        {result.error=-7;return;}
    for(unsigned row=0;row<19;row++) for(unsigned column=0;column<10;column++) {
        unsigned i=row*10+column;
        uint32_t expected=original_entries[i];
        if(column==0&&expected) expected+=base;
        if(report.mdt_entries[i]!=expected) {result.error=-8;return;}
    }
    long allocation=map_page();
    DEBUG("MENU_ALLOCATED\n");
    if(!allocation||(uint32_t)allocation>=0xfffff001u) {result.error=allocation?allocation:-9;return;}
    state=(void *)(uintptr_t)allocation;
    state->magic=0x41374d52;state->base=base;state->old_table=root[0];state->old_count=root[1];
    for(unsigned i=0;i<190;i++) state->entries[i]=report.mdt_entries[i];
    for(unsigned i=0;i<10;i++) state->entries[190+i]=report.mdt_entries[20+i];
    state->entries[192]=98;
    state->entries[193]=0x0204f7e6; /* Existing, known title resource: test label only. */
    uint32_t ptr=(uintptr_t)state->trace;
    copy(replacement+TRACE_OFFSET,(void *)&ptr,4);
    DEBUG("MENU_PATCHING_CODE\n");
    if(!code_write(code,replacement,sizeof replacement)) {
        code_write(code,original_dispatch,sizeof original_dispatch);result.error=-10;return;
    }
    root[0]=(uintptr_t)state->entries;
    DEBUG("MENU_CODE_PATCHED\n");
    __asm__ volatile("dmb ish" ::: "memory");
    root[1]=20;
    result.allocation=(uintptr_t)state;result.code_changed=1;result.count=root[1];result.status=1;
}
__attribute__((constructor)) static void menu_experiment(void) {
    DEBUG("MENU_CONSTRUCTOR\n");
    result.magic=0x41374d54;result.action=ACTION;
    long fd=sc3(5,(long)"/tmp/jiritsu/a7menu.bin",1|64|128,0600);
    if(fd<0) return;
    run();
    sc3(10,(long)"/tmp/jiritsu/libJit.so",0,0);
    long n=0;
    while(n<(long)sizeof result) {
        long got=sc3(4,fd,(long)((char *)&result+n),sizeof result-n);
        if(got<=0) break;
        n+=got;
    }
    sc3(118,fd,0,0);sc3(6,fd,0,0);
}
