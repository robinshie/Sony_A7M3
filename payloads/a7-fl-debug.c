/* Standalone read-only diagnostic extension. The deployed module/probe remain
 * unchanged. No install, prepare, lifecycle or setting method is called. */
#define A7_FL_INSPECT_TEST 1
#include "a7-fl-inspect.c"
#include "a7-fl-debug-pins.h"
#include <stddef.h>
struct BootImage {
    uint32_t lock,ready,installing,mode;
    uintptr_t caller,view,caution,backup,prepared_view,prepared_caution,prepared_backup;
    void *view_manager;unsigned count;
    struct {uintptr_t lo,hi;} ranges[1024];
    char maps[65536];struct a7_fl_platform platform;
};
struct ModulePrefix {uint32_t lock;struct a7_fl_platform platform;struct a7_fl_module_status status;};
_Static_assert(sizeof(struct BootImage)==A7_DEBUG_BOOT_SIZE,"pinned private boot ABI");
_Static_assert(offsetof(struct ModulePrefix,status)==144,"pinned module status ABI");
struct DebugReport {
    uint32_t magic,version;int32_t status;uint32_t size,flags,private_stable,map_bytes,reserved;
    struct a7_fl_inspect_report baseline;
    uint32_t boot_head[13];struct a7_fl_platform boot_platform;
    struct ModulePrefix module;
    uint32_t libobj,vm_global,vm,vm_words[28],manager[2],page[10],children[8],child_words[8][10],checks[24];
    char maps[65536];
};
_Static_assert(sizeof(struct DebugReport)==66740,"debug report ABI");
static struct BootImage snapshot,again;
static struct ModulePrefix module_again;
static struct DebugReport result;
long a7_fl_inspect_syscall(long number,long a,long b,long c) {
#ifdef A7_FL_DEBUG_TEST
    extern long a7_fl_debug_syscall(long,long,long,long);return a7_fl_debug_syscall(number,a,b,c);
#else
    register long r7 __asm__("r7")=number;
    register long r0 __asm__("r0")=a,r1 __asm__("r1")=b,r2 __asm__("r2")=c;
    __asm__ volatile("svc #0":"+r"(r0):"r"(r7),"r"(r1),"r"(r2):"memory","cc");return r0;
#endif
}
void a7_fl_inspect_copy_hook(void) {}
static int cached_span(uintptr_t address,unsigned n) {
    if(!address||n>UINT32_MAX-address||snapshot.count>1024)return 0;
    uintptr_t end=address+n;unsigned i=0;
    while(i<snapshot.count&&snapshot.ranges[i].hi<=address)i++;
    if(i==snapshot.count||snapshot.ranges[i].lo>address)return 0;
    while(snapshot.ranges[i].hi<end){uintptr_t last=snapshot.ranges[i].hi;
        if(++i==snapshot.count||snapshot.ranges[i].lo!=last)return 0;
    }return 1;
}
static const char *debug_map_name(const char *p) {
    for(unsigned i=0;i<5;i++){
        while(*p==' ')p++;
        while(*p&&*p!=' '&&*p!='\n')p++;
    }
    while(*p==' ')p++;
    return p;
}
static int debug_exact(const char*p,const char*q){while(*q&&*p==*q){p++;q++;}return !*q&&(!*p||*p=='\n');}
static int current_allowed(uintptr_t address,unsigned n) {
    if(!address||n>UINT32_MAX-address)return 0;
    uintptr_t cursor=address,end=address+n;
    for(const char *p=memory.maps;*p;){const char *after=p;uintptr_t lo=hex(&after);after++;uintptr_t hi=hex(&after);
        const char *name=debug_map_name(p);
        int allowed=debug_exact(name,"/usr/lib/viewUnified2.so")||debug_exact(name,"/usr/lib/CautionConfig.so")||
          debug_exact(name,"/usr/lib/libbackup.so")||debug_exact(name,"/usr/lib/a7fl.so")||!*name||*name=='\n'||*name=='[';
        if(lo<=cursor&&cursor<hi&&after[0]==' '&&after[1]=='r'&&after[4]=='p'&&allowed) {
            if(end<=hi)return 1;
            cursor=hi;
        }
        while(*p&&*p!='\n')p++;
        if(*p)p++;
    }return 0;
}
static void inspect_debug(void) {
    for(unsigned i=0;i<sizeof result;i++)((unsigned char*)&result)[i]=0;
    result.magic=0x41374644;result.version=1;result.size=sizeof result;
    result.status=a7_fl_inspect_read(&result.baseline);
    for(unsigned i=0;i<sizeof memory.maps&&memory.maps[i];i++)result.maps[result.map_bytes++]=memory.maps[i];
    if(result.status!=1)return;
    uintptr_t base=memory.module;
    if(span(base+A7_DEBUG_BOOT_VA,sizeof snapshot))result.flags|=1;
    if(span(base+A7_DEBUG_MODULE_VA,sizeof result.module))result.flags|=2;
    if((result.flags&3)!=3){result.status=-20;return;}
    for(unsigned attempt=0;attempt<3;attempt++){
        read_copy(&snapshot,(void*)(base+A7_DEBUG_BOOT_VA),sizeof snapshot);
        read_copy(&result.module,(void*)(base+A7_DEBUG_MODULE_VA),sizeof result.module);
        __asm__ volatile("dmb ish":::"memory");
        read_copy(&again,(void*)(base+A7_DEBUG_BOOT_VA),sizeof again);
        read_copy(&module_again,(void*)(base+A7_DEBUG_MODULE_VA),sizeof module_again);
        if(same(&snapshot,&again,sizeof snapshot)&&same(&result.module,&module_again,sizeof result.module)){
            result.private_stable=1;break;
        }
    }
    if(!result.private_stable){result.status=-21;return;}
    read_copy(result.boot_head,&snapshot,sizeof result.boot_head);
    read_copy(&result.boot_platform,&snapshot.platform,sizeof result.boot_platform);
    for(const char*p=memory.maps;*p;){
        if(contains(p,"r-xp 00000000")&&ends_with(p,"/usr/lib/libObj.so")){
            const char *end=p;result.libobj=hex(&end);result.flags|=4;
        }
        while(*p&&*p!='\n')p++;
        if(*p)p++;
    }
    if(result.libobj && A7_DEBUG_VM_GLOBAL<=UINT32_MAX-result.libobj) {
        result.vm_global=result.libobj+A7_DEBUG_VM_GLOBAL;
        if(span(result.vm_global,4)){read_copy(&result.vm,(void*)result.vm_global,4);result.flags|=8;}
    }
    if(result.vm && !(result.vm&3) && span(result.vm,sizeof result.vm_words)){
        read_copy(result.vm_words,(void*)result.vm,sizeof result.vm_words);result.flags|=16;
    }
    uintptr_t view=result.baseline.view_base,caution=result.baseline.bootstrap.caution;
    uintptr_t manager=view+0xa61c18,page_address=view+0xa6dfa4;
    if(span(manager,sizeof result.manager)){read_copy(result.manager,(void*)manager,sizeof result.manager);result.flags|=32;}
    if(span(page_address,sizeof result.page)){read_copy(result.page,(void*)page_address,sizeof result.page);result.flags|=64;}
    a7_menu_node *page=(void*)result.page;
    if((result.flags&64)&&page->count>=0&&page->count<=64&&span((uintptr_t)page->children,(unsigned)page->count*4)) {
        result.flags|=128;unsigned count=page->count>8?8:(unsigned)page->count;
        read_copy(result.children,page->children,count*4);
        for(unsigned i=0;i<count;i++)if(span(result.children[i],40))read_copy(result.child_words[i],(void*)result.children[i],40);
    }
    uint32_t *c=result.checks;
    c[0]=result.vm&&!(result.vm&3);c[1]=current_allowed(result.vm,4);c[2]=cached_span(result.vm,4);
    c[3]=current_allowed(manager,4);c[4]=(result.flags&32)&&result.manager[0]==view+0x87f720;
    c[5]=!(page_address&3);c[6]=(result.flags&64)&&(uintptr_t)page->vtable==caution+0x918ec8;
    c[7]=(result.flags&64)&&page->count==3;c[8]=(result.flags&64)&&(uintptr_t)page->properties==view+0xa725a0;
    c[9]=(result.flags&64)&&!((uintptr_t)page->children&3);c[10]=(result.flags&64)&&current_allowed((uintptr_t)page->children,12);
    c[11]=(result.flags&64)&&page->depth==3&&(uintptr_t)page->parent==view+0xa69c88&&page->serial==14&&page->index==14;
    c[12]=(result.flags&64)&&(uintptr_t)page->children==view+0x8f3214&&!page->parent&&!page->depth&&!page->selected&&!page->serial&&!page->index&&!page->state;
    c[13]=(result.flags&128)&&page->count==3;
    for(unsigned i=0;i<3;i++)if(!result.children[i]||(result.children[i]&3)||!current_allowed(result.children[i],40))c[13]=0;
    c[14]=current_allowed(view+0x87f720-8,(A7_MENU_MANAGER_WORDS+2)*4);
    c[15]=current_allowed(caution+0x918ec8-8,268);
    c[16]=(uintptr_t)snapshot.platform.manager==manager;c[17]=(uintptr_t)snapshot.platform.manager_vtable==view+0x87f720;
    c[18]=result.vm&&(uintptr_t)result.module.platform.view_manager==result.vm;
    c[19]=result.vm&&(uintptr_t)snapshot.platform.view_manager==result.vm;
    c[20]=result.vm&&(uintptr_t)snapshot.view_manager==result.vm;
    c[21]=snapshot.count<=1024;c[22]=result.module.status.installed;c[23]=result.module.status.fault;
}
#ifndef A7_FL_DEBUG_TEST
__attribute__((constructor)) static void debug_resident(void) {
    inspect_debug();call3(10,(long)"/tmp/jiritsu/libJit.so",0,0);
    long fd=call3(5,(long)"/tmp/jiritsu/a7fldbg.bin",1|64|128|0x8000,0600);if(fd<0)return;
    unsigned done=0;
    while(done<sizeof result){long n=call3(4,fd,(long)((unsigned char*)&result+done),sizeof result-done);
        if(n<=0||(unsigned)n>sizeof result-done)break;
        done+=(unsigned)n;
    }call3(118,fd,0,0);call3(6,fd,0,0);
}
#else
int a7_fl_debug_test_run(void){inspect_debug();return result.status;}
const void *a7_fl_debug_test_report(void){return &result;}
#endif
