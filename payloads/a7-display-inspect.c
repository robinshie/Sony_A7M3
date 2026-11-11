/* Read-only witness of the two display call sites after a cold boot. */
#define A7_RUNTIME_LIBRARY_ONLY
#include "a7-runtime-probe.c"
static struct {uint32_t magic,base,status,footer,count;} result;
__attribute__((constructor)) static void capture(void) {
    result.magic=0x41374449;
    report.maps_n=read_proc("/proc/self/maps",report.maps,sizeof report.maps);
    inspect_view();result.base=report.view_base;
    if(result.base&&copy_address(result.base+0x5b9e36,&result.footer,1)&&
       copy_address(result.base+0x5bb998,&result.count,1))result.status=1;
    sc3(10,(long)"/tmp/jiritsu/libJit.so",0,0);
    long fd=sc3(5,(long)"/tmp/jiritsu/a7display.bin",1|64|128,0600);
    if(fd>=0) {sc3(4,fd,(long)&result,sizeof result);sc3(118,fd,0,0);sc3(6,fd,0,0);}
}
