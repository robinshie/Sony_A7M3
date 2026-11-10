/* Read-only diagnostics of already loaded native code versus its disk file. */
#define A7_RUNTIME_LIBRARY_ONLY
#include "a7-runtime-probe.c"
static struct {
    uint32_t magic,base,status,count;
    uint32_t root[10];
    unsigned char code[660],hook[4],dynamic_init[4];
    uint32_t entries[200];
    int32_t cmdline_size;
    char cmdline[1024];
    unsigned char create_hook[4];
} result;
static int bytes(uint32_t from,unsigned char *to,unsigned n) {
    if(!readable(from,n))return 0;
    const volatile unsigned char *p=(void *)(uintptr_t)from;
    for(unsigned i=0;i<n;i++)to[i]=p[i];
    return 1;
}
__attribute__((constructor)) static void inspect(void) {
    result.magic=0x41374349;
    report.maps_n=read_proc("/proc/self/maps",report.maps,sizeof report.maps);
    inspect_view();result.base=report.view_base;
    if(result.base) {
        for(unsigned i=0;i<10;i++)result.root[i]=report.mdt_root[i];
        result.count=result.root[1];
        if(bytes(result.base+0x5b98dc,result.code,658)&&bytes(result.base+0x5b9fba,result.hook,4)&&
           bytes(result.base+0x8e3760,result.dynamic_init,4)&&
           bytes(result.base+0x5bb266,result.create_hook,4))result.status=1;
        if((result.count==19||result.count==20)&&
           copy_address(result.root[0],result.entries,result.count*10))result.status|=2;
    }
    result.cmdline_size=read_proc("/proc/cmdline",result.cmdline,sizeof result.cmdline);
    sc3(10,(long)"/tmp/jiritsu/libJit.so",0,0);
    long fd=sc3(5,(long)"/tmp/jiritsu/a7inspect.bin",1|64|128,0600);
    if(fd<0)return;
    unsigned done=0;
    while(done<sizeof result) {
        long n=sc3(4,fd,(long)((unsigned char *)&result+done),sizeof result-done);
        if(n<=0)break;
        done+=n;
    }
    sc3(118,fd,0,0);sc3(6,fd,0,0);
}
