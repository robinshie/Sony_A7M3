/* Bounded symbols and optional physical-code/dispatch-table readback.
 * No kernel calls, mappings, hooks, pixel writes, or firmware updates. */
#include <stdint.h>
static struct {uint32_t magic,version,status,scanned,used,matches,route[12];char lines[8192];} report;
static long sc3(long n,long a,long b,long c) {
    register long r7 __asm__("r7")=n,r0 __asm__("r0")=a,r1 __asm__("r1")=b,r2 __asm__("r2")=c;
    __asm__ volatile("svc #0":"+r"(r0):"r"(r7),"r"(r1),"r"(r2):"memory","cc");return r0;
}
static int equal(const char *a,const char *b) {while(*a&&*a==*b){a++;b++;}return !*a&&!*b;}
static void line(char *p,unsigned n) {
    static const char *const wanted[]={"_text","_stext","mmap_mem","phys_mem_access_prot",
        "phys_mem_access_prot_allowed","arch_phys_to_cache","arch_phys_to_noncache",
        "arch_phys_to_virt","cxd90014_phys_to_cache","cxd90014_phys_to_noncache",
        "dma_cache_maint_page","dmac_flush_range","dmac_inv_range","dmac_clean_range",
        "v7_dma_inv_range","v7_dma_clean_range","v7_dma_flush_range","outer_cache",
        "remap_pfn_range","valid_mmap_phys_addr_range","devmem_is_allowed",
        "cache_flush_range","cache_inv_range","cpu_cache","arch_va_to_phys","get_cp_start",
        "register_undef_hook","unregister_undef_hook","do_undefinstr","__und_svc",
        "kallsyms_lookup_name","stop_machine","__cpuc_coherent_kern_range"};
    p[n]=0;unsigned i=0;
    while(i<n&&p[i]!=' ')i++;
    if(i+3>=n)return;
    char *name=p+i+3; /* address, space, symbol type, space */
    for(unsigned j=i+3;j<n;j++)if(p[j]==' '||p[j]=='\t'){p[j]=0;break;}
    int found=0;for(unsigned j=0;j<sizeof wanted/sizeof wanted[0];j++)found|=equal(name,wanted[j]);
    if(!found)return;
    if(report.used+n+1>sizeof report.lines){report.status=4;return;}
    /* The original line has no embedded NUL for the built-in symbols above. */
    for(unsigned j=0;j<n;j++)report.lines[report.used++]=p[j]?p[j]:' ';
    report.lines[report.used++]='\n';report.matches++;
}
#ifdef A7_CACHE_ROUTE
#include "cache-route-pins.h"
static long pread_phys(long fd,void *out,unsigned size,uint32_t physical){
    register long r7 __asm__("r7")=180,r0 __asm__("r0")=fd,r1 __asm__("r1")=(long)out;
    register long r2 __asm__("r2")=size,r3 __asm__("r3")=0,r4 __asm__("r4")=physical,r5 __asm__("r5")=0;
    __asm__ volatile("svc #0":"+r"(r0):"r"(r7),"r"(r1),"r"(r2),"r"(r3),"r"(r4),"r"(r5):"memory","cc");return r0;
}
static int read_va(long fd,uint32_t va,void *out,unsigned size){
    /* Only the observed low kernel/LIRO DRAM window, never MMIO. */
    if(va<0x60108000u || va>=0x68000000u || size>64 || size>0x68000000u-va)return 0;
    report.route[3]++;
    return pread_phys(fd,out,size,va-0x60000000u)==(long)size;
}
static int pin_va(long fd,uint32_t va,const unsigned char *pin,unsigned size){
    unsigned char bytes[64];if(!read_va(fd,va,bytes,size))return 0;
    for(unsigned i=0;i<size;i++)if(bytes[i]!=pin[i])return 0;
    return 1;
}
static void read_route(void){
    report.route[0]=1;
    long fd=sc3(5,(long)"/dev/mem",0x1000,0);if(fd<0)return;
    report.route[0]=2;
    report.route[9]=pin_va(fd,0x60118470,kernel_pin,sizeof kernel_pin);
    report.route[10]=pin_va(fd,0x635e3c34,avcam_pin,sizeof avcam_pin);
    if(!report.route[9]||!report.route[10])goto close;
    report.route[0]=3;
    if(!read_va(fd,0x6475a218,&report.route[1],4) || report.route[1]!=0x635c6000u)goto close;
    if(!read_va(fd,report.route[1]+0x14,&report.route[2],4))goto close;
    report.route[0]=4;
    for(unsigned i=0;i<5;i++){
        if(report.route[2]>UINT32_MAX-0x30c || !read_va(fd,report.route[2]+0x2fc+i*4,&report.route[4+i],4))goto close;
    }
    report.route[0]=0;
close:
    if(sc3(6,fd,0,0)&&!report.route[0])report.route[0]=5;
}
#endif
__attribute__((constructor)) static void collect(void) {
    report.magic=0x41374353;report.version=2;report.status=1;
    long fd=sc3(5,(long)"/proc/kallsyms",0x8000,0);
    if(fd>=0){
        char buf[4096],pending[512];unsigned used=0;int overflow=0;
        while(report.scanned<4u*1024u*1024u){
            long n=sc3(3,fd,(long)buf,sizeof buf);
            if(n<0){report.status=2;break;}
            if(!n){report.status=0;break;}
            report.scanned+=(unsigned)n;
            for(unsigned i=0;i<(unsigned)n;i++){
                if(buf[i]=='\n'){if(!overflow)line(pending,used);used=0;overflow=0;}
                else if(used<sizeof pending-1)pending[used++]=buf[i];else overflow=1;
            }
            if(report.status==4)break;
        }
        if(report.scanned>=4u*1024u*1024u)report.status=3;
        if(sc3(6,fd,0,0)&&!report.status)report.status=5;
    }
#ifdef A7_CACHE_ROUTE
    if(!report.status)read_route();
#else
    report.route[0]=0xffffffffu;
#endif
    const char *path="/tmp/jiritsu/a7cs.bin";
    fd=sc3(5,(long)path,1|64|128|0x8000,0600);if(fd<0)return;
    unsigned at=0;const char *bytes=(const char *)&report;
    while(at<sizeof report){long n=sc3(4,fd,(long)(bytes+at),sizeof report-at);if(n<=0)break;at+=(unsigned)n;}
    long closed=sc3(6,fd,0,0);if(at!=sizeof report||closed)sc3(10,(long)path,0,0);
}
