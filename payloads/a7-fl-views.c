/* Read-only bounded ViewManager slot traversal. Kept independent from the
 * frozen debug-v1 source, deployed FL module and original status probe. */
#define A7_FL_DEBUG_TEST 1
#include "a7-fl-debug.c"
struct ViewRecord {uint32_t flags,slot[4],object[10];};
struct ViewsReport {
    uint32_t magic,version,size;int32_t status;
    uint32_t count,arrays[2],records;
    struct DebugReport debug;
    struct ViewRecord views[512];
};
_Static_assert(sizeof(struct ViewsReport)==97492,"views report ABI");
static struct ViewsReport views_result;
#ifndef A7_FL_VIEWS_TEST
long a7_fl_debug_syscall(long number,long a,long b,long c) {
    register long r7 __asm__("r7")=number;
    register long r0 __asm__("r0")=a,r1 __asm__("r1")=b,r2 __asm__("r2")=c;
    __asm__ volatile("svc #0":"+r"(r0):"r"(r7),"r"(r1),"r"(r2):"memory","cc");return r0;
}
#endif
static void inspect_views(void) {
    for(unsigned i=0;i<sizeof views_result;i++)((unsigned char*)&views_result)[i]=0;
    views_result.magic=0x41374656;views_result.version=1;views_result.size=sizeof views_result;
    inspect_debug();read_copy(&views_result.debug,&result,sizeof result);
    views_result.status=result.status;if(result.status!=1)return;
    if(!(result.flags&16)){views_result.status=-30;return;}
    views_result.count=result.vm_words[0];
    views_result.arrays[0]=result.vm_words[8];views_result.arrays[1]=result.vm_words[9];
    if(!views_result.count||views_result.count>256){views_result.status=-31;return;}
    unsigned count=views_result.count;
    for(unsigned table=0;table<2;table++) {
        uintptr_t array=views_result.arrays[table];
        if((array&3)||!span(array,count*16)){views_result.status=-32;continue;}
        for(unsigned i=0;i<count;i++) {
            struct ViewRecord *r=&views_result.views[table*count+i];
            read_copy(r->slot,(void*)(array+i*16),16);r->flags=1;views_result.records++;
            uintptr_t object=r->slot[1];
            if(!object||(object&3)||!span(object,sizeof r->object))continue;
            read_copy(r->object,(void*)object,sizeof r->object);r->flags|=2;
            if(r->object[9]==result.vm)r->flags|=4;
            if(r->object[0]==result.baseline.view_base+0x87a9c8)r->flags|=8;
            if(r->object[0]==result.baseline.view_base+0x87b600)r->flags|=16;
        }
    }
}
#ifndef A7_FL_VIEWS_TEST
__attribute__((constructor)) static void resident_views(void) {
    inspect_views();call3(10,(long)"/tmp/jiritsu/libJit.so",0,0);
    long fd=call3(5,(long)"/tmp/jiritsu/a7flview.bin",1|64|128|0x8000,0600);if(fd<0)return;
    unsigned done=0;
    while(done<sizeof views_result){long n=call3(4,fd,(long)((unsigned char*)&views_result+done),sizeof views_result-done);
        if(n<=0||(unsigned)n>sizeof views_result-done)break;
        done+=(unsigned)n;
    }call3(118,fd,0,0);call3(6,fd,0,0);
}
#else
int a7_fl_views_test_run(void){inspect_views();return views_result.status;}
const void *a7_fl_views_test_report(void){return &views_result;}
#endif
