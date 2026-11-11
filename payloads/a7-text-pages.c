/* Fixed three-page read-only snapshot. No dynamic-loader, native firmware,
 * process mutation or memory-protection function is called. */
#include <stdint.h>
#include "a7-text-pages-pins.h"
struct PageInfo {uint32_t offset,address,lo,hi,file_offset,permissions;};
struct PageReport {
    uint32_t magic,version;int32_t status;
    uint32_t view_base,maps_bytes,valid_mask,stable_mask;
    struct PageInfo page[3];unsigned char bytes[3][4096];
};
_Static_assert(sizeof(struct PageReport)==12388,"fixed-page report ABI");
static struct PageReport report;
static char maps_text[65536];static unsigned char second[4096];
#ifdef A7_TEXT_PAGES_TEST
extern long a7_text_syscall(long,long,long,long);
extern void a7_text_copy_hook(unsigned,unsigned);
#else
static long a7_text_syscall(long number,long a,long b,long c){
    register long r7 __asm__("r7")=number;
    register long r0 __asm__("r0")=a,r1 __asm__("r1")=b,r2 __asm__("r2")=c;
    __asm__ volatile("svc #0":"+r"(r0):"r"(r7),"r"(r1),"r"(r2):"memory","cc");return r0;
}
#endif
static int same(const void*a,const void*b,unsigned n){const unsigned char*x=a,*y=b;for(unsigned i=0;i<n;i++)if(x[i]!=y[i])return 0;return 1;}
static void copy(void*a,const volatile void*b,unsigned n){unsigned char*x=a;const volatile unsigned char*y=b;for(unsigned i=0;i<n;i++)x[i]=y[i];}
static int exact(const char*a,const char*b){while(*b&&*a==*b){a++;b++;}return !*b&&(!*a||*a=='\n');}
static int hex(const char**p,uint32_t*out){uint32_t value=0;unsigned count=0;for(;;){unsigned c=(unsigned char)**p;
    if(c>='0'&&c<='9')c-='0';else if(c>='a'&&c<='f')c=c-'a'+10;else break;
    if(count++==8)return 0;
    value=(value<<4)|c;++*p;
}*out=value;return count!=0;}
static long read_file(const char*p,void*out,unsigned cap){long fd=a7_text_syscall(5,(long)p,0x8000,0);if(fd<0)return fd;
    unsigned n=0;long error=0;
    while(n<cap){long got=a7_text_syscall(3,fd,(long)((char*)out+n),cap-n);if(got<0){error=got;break;}if(!got)break;n+=(unsigned)got;}
    if(a7_text_syscall(6,fd,0,0)<0)return -1;
    return error?error:n==cap?-75:(long)n;
}
struct Map {uint32_t lo,hi,offset,permissions;const char*name;};
static int parse(const char*p,struct Map*m){
    if(!hex(&p,&m->lo)||*p++!='-'||!hex(&p,&m->hi)||m->lo>=m->hi||*p++!=' ')return 0;
    if(!p[0]||!p[1]||!p[2]||!p[3]||p[4]!=' ')return 0;
    copy(&m->permissions,p,4);p+=5;
    if(!hex(&p,&m->offset)||*p!=' ')return 0;
    for(unsigned i=0;i<2;i++){while(*p==' ')p++;while(*p&&*p!=' '&&*p!='\n')p++;}
    while(*p==' ')p++;
    m->name=p;return 1;
}
static int view_map(const struct Map*m){return m->permissions==0x70782d72&&exact(m->name,"/usr/lib/viewUnified2.so");}
static int page_map(uint32_t address,uint32_t file_offset,struct Map*out){
    if(address>UINT32_MAX-4096)return 0;
    for(const char*p=maps_text;*p;){struct Map m;if(!parse(p,&m))return 0;
        if(view_map(&m)&&m.lo<=address&&address+4096<=m.hi&&address-m.lo<=UINT32_MAX-m.offset&&m.offset+address-m.lo==file_offset){*out=m;return 1;}
        while(*p&&*p!='\n')p++;
        if(*p)p++;
    }return 0;
}
static void read_pages(void){
    for(unsigned i=0;i<sizeof report;i++)((unsigned char*)&report)[i]=0;
    report.magic=0x41375450;report.version=1;report.status=-1;
    static const char build[]="37114_13.2026020901";char version[24];
    long n=read_file("/version.txt",version,sizeof version);
    if(n!=(long)sizeof build-1||!same(version,build,sizeof build-1))return;
    report.status=-2;n=read_file("/proc/self/maps",maps_text,sizeof maps_text-1);
    if(n<=0)return;
    report.maps_bytes=(uint32_t)n;maps_text[n]=0;unsigned count=0;uint32_t previous=0;
    for(const char*p=maps_text;*p;){struct Map m;if(!parse(p,&m)||m.lo<previous)return;previous=m.hi;
        if(view_map(&m)&&m.offset==0){report.view_base=m.lo;count++;}
        while(*p&&*p!='\n')p++;
        if(*p)p++;
    }
    if(count!=1)return;
    struct Map first;report.status=-3;
    if(!page_map(report.view_base,0,&first)||!same((void*)report.view_base,a7_text_header,sizeof a7_text_header))return;
    static const uint32_t offsets[3]={0x214000,0x20d000,0x5b9000};
    for(unsigned i=0;i<3;i++){
        struct PageInfo*p=&report.page[i];struct Map m;p->offset=offsets[i];report.status=-10-(int)i;
        if(offsets[i]>UINT32_MAX-report.view_base)return;
        p->address=report.view_base+offsets[i];
        if(!page_map(p->address,p->offset,&m))return;
        p->lo=m.lo;p->hi=m.hi;p->file_offset=m.offset;p->permissions=m.permissions;report.valid_mask|=1u<<i;
        for(unsigned attempt=0;attempt<3;attempt++){
            copy(report.bytes[i],(void*)p->address,4096);__asm__ volatile("dmb ish":::"memory");
#ifdef A7_TEXT_PAGES_TEST
            a7_text_copy_hook(i,attempt);
#endif
            copy(second,(void*)p->address,4096);
            if(same(report.bytes[i],second,4096)){report.stable_mask|=1u<<i;break;}
        }
        if(!(report.stable_mask&(1u<<i))){report.status=-20-(int)i;return;}
    }
    report.status=1;
}
#ifndef A7_TEXT_PAGES_TEST
__attribute__((constructor)) static void constructor(void){
    read_pages();a7_text_syscall(10,(long)"/tmp/jiritsu/libJit.so",0,0);
    long fd=a7_text_syscall(5,(long)"/tmp/jiritsu/a7pages.bin",1|64|128|0x8000,0600);if(fd<0)return;
    unsigned done=0;while(done<sizeof report){long n=a7_text_syscall(4,fd,(long)((char*)&report+done),sizeof report-done);
        if(n<=0||(unsigned)n>sizeof report-done)break;
        done+=(unsigned)n;
    }a7_text_syscall(118,fd,0,0);a7_text_syscall(6,fd,0,0);
}
#else
int a7_text_test_read(void){read_pages();return report.status;}
const void*a7_text_test_report(void){return &report;}
#endif
