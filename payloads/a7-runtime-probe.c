/* Read the hosting process layout. Only writes a new temporary report. */
#include <stdint.h>
static inline long sc3(long nr,long a,long b,long c) {
    register long r7 __asm__("r7")=nr;
    register long r0 __asm__("r0")=a;
    register long r1 __asm__("r1")=b;
    register long r2 __asm__("r2")=c;
    __asm__ volatile("svc #0" : "+r"(r0) : "r"(r7),"r"(r1),"r"(r2) : "memory","cc");
    return r0;
}
static struct {
    uint32_t magic; int32_t maps_n,cmdline_n;
    char maps[65536],cmdline[512];
    uint32_t caution_base, node_status;
    uint32_t root[10],neutral[10],real[10],neutral_properties[2],real_properties[2];
    uint32_t view_base,view_status,mdt_root[10],mdt_entries[190],manager[2],element[6];
} report;
static uint32_t hex(const char **p) {
    uint32_t v=0;
    while(1) {
        unsigned d=(unsigned char)**p;
        if(d>='0'&&d<='9') d-='0';
        else if(d>='a'&&d<='f') d=d-'a'+10;
        else break;
        v=(v<<4)|d; ++*p;
    }
    return v;
}
static int contains(const char *line,const char *needle) {
    for(;*line&&*line!='\n';line++) {
        const char *a=line,*b=needle;
        while(*b&&*a==*b) {a++;b++;}
        if(!*b) return 1;
    }
    return 0;
}
static int readable(uint32_t address,uint32_t size) {
    for(const char *p=report.maps;*p;) {
        const char *next=p; uint32_t lo=hex(&next);
        if(*next++!='-') return 0;
        uint32_t hi=hex(&next);
        if(next[0]==' '&&next[1]=='r'&&lo<=address&&address<=hi&&size<=hi-address) return 1;
        while(*p&&*p!='\n') p++;
        if(*p) p++;
    }
    return 0;
}
static int copy_address(uint32_t address,uint32_t *to,uint32_t words) {
    if(!readable(address,words*4)) return 0;
    const volatile uint32_t *from=(const volatile uint32_t *)(uintptr_t)address;
    for(uint32_t i=0;i<words;i++) to[i]=from[i];
    return 1;
}
static int copy_words(uint32_t offset,uint32_t *to,uint32_t words) {
    return copy_address(report.caution_base+offset,to,words);
}
static void inspect_view(void) {
    if(report.maps_n<=0) return;
    for(const char *p=report.maps;*p;) {
        if(contains(p,"r-xp 00000000")&&contains(p,"/usr/lib/viewUnified2.so")) {
            report.view_base=hex(&p);break;
        }
        while(*p&&*p!='\n') p++;
        if(*p) p++;
    }
    if(!report.view_base) return;
    report.view_status=1;
    uint32_t base=report.view_base;
    if(!copy_address(base+0xa60c90,report.mdt_root,10)) return;
    /* Refuse an unexpected or already modified root before following its pointer. */
    if(report.mdt_root[0]!=base+0xa60998||report.mdt_root[1]!=19||report.mdt_root[2]!=97) return;
    if(copy_address(report.mdt_root[0],report.mdt_entries,190)&&
       copy_address(base+0xa61c18,report.manager,2)&&copy_address(base+0xa87ce0,report.element,6))
        report.view_status=2;
}
static void inspect_nodes(void) {
    if(report.maps_n<=0) return;
    for(const char *p=report.maps;*p;) {
        if(contains(p,"r-xp 00000000")&&contains(p,"/usr/lib/CautionConfig.so")) {
            report.caution_base=hex(&p);break;
        }
        while(*p&&*p!='\n') p++;
        if(*p) p++;
    }
    if(!report.caution_base) return;
    report.node_status=1;
    if(copy_words(0xa75ff4,report.root,10)&&copy_words(0x9ee0a0,report.neutral,10)&&
       copy_words(0xa03560,report.real,10)&&copy_words(0xa16c68,report.neutral_properties,2)&&
       copy_words(0x9f8308,report.real_properties,2)) report.node_status=2;
}
static long read_proc(const char *name,char *data,long capacity) {
    long fd=sc3(5,(long)name,0,0), n=0;
    if(fd<0) return fd;
    while(n<capacity) {
        long got=sc3(3,fd,(long)(data+n),capacity-n);
        if(got<=0) { if(got<0) n=got; break; }
        n+=got;
    }
    sc3(6,fd,0,0);
    return n==capacity?-75:n;
}
#ifndef A7_RUNTIME_LIBRARY_ONLY
__attribute__((constructor)) static void capture(void) {
    report.magic=0x41375254;
    report.maps_n=read_proc("/proc/self/maps",report.maps,sizeof report.maps);
    report.cmdline_n=read_proc("/proc/self/cmdline",report.cmdline,sizeof report.cmdline);
    inspect_nodes();
    inspect_view();
    sc3(10,(long)"/tmp/jiritsu/libJit.so",0,0);
    long fd=sc3(5,(long)"/tmp/jiritsu/a7rt.bin",1|64|128,0600);
    if(fd>=0) {
        long n=0;
        while(n<(long)sizeof report) {
            long wrote=sc3(4,fd,(long)((char *)&report+n),sizeof report-n);
            if(wrote<=0) break;
            n+=wrote;
        }
        sc3(118,fd,0,0);
        sc3(6,fd,0,0);
    }
}
#endif
