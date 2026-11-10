/* Read-only witnesses for the v3 cursor calls and Fn label property. */
#define A7_RUNTIME_LIBRARY_ONLY
#include "a7-runtime-probe.c"
static struct {uint32_t magic,view,config,status,remember,reopen,label;} result;
static int read_word(uint32_t address,uint32_t *out) {
    if(!readable(address,4))return 0;
    volatile unsigned char *p=(void*)(uintptr_t)address;
    *out=(uint32_t)p[0]|((uint32_t)p[1]<<8)|((uint32_t)p[2]<<16)|((uint32_t)p[3]<<24);
    return 1;
}
__attribute__((constructor)) static void inspect_identity(void) {
    result.magic=0x41374944;
    report.maps_n=read_proc("/proc/self/maps",report.maps,sizeof report.maps);
    inspect_nodes();inspect_view();
    result.view=report.view_base;result.config=report.caution_base;
    if(result.view&&read_word(result.view+0x5bb18e,&result.remember))result.status|=1;
    if(result.view&&read_word(result.view+0x5bb9de,&result.reopen))result.status|=2;
    if(result.config&&read_word(result.config+0x8359f0,&result.label))result.status|=4;
    sc3(10,(long)"/tmp/jiritsu/libJit.so",0,0);
    long fd=sc3(5,(long)"/tmp/jiritsu/a7identity.bin",1|64|128,0600);
    if(fd>=0){sc3(4,fd,(long)&result,sizeof result);sc3(118,fd,0,0);sc3(6,fd,0,0);}
}
