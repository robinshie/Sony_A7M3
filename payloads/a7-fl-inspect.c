/* Read-only resident-state inspector; temporary maintenance report only. */
#include "a7-fl-inspect.h"
#include "a7-fl-inspect-pins.h"
_Static_assert(sizeof(struct a7_fl_bootstrap_report)==36,"bootstrap report ABI");
_Static_assert(sizeof(struct a7_fl_module_status)==68,"runtime report ABI");
#ifdef A7_FL_INSPECT_PREVIEW
_Static_assert(sizeof(struct a7_fl_inspect_report)==184,"preview inspect report ABI");
#else
_Static_assert(sizeof(struct a7_fl_inspect_report)==148,"inspect report ABI");
#endif
static struct {uintptr_t view,module;unsigned count;struct{uintptr_t lo,hi;}ranges[1024];char maps[65536];} memory;
#ifdef A7_FL_INSPECT_TEST
extern long a7_fl_inspect_syscall(long,long,long,long);
extern void a7_fl_inspect_copy_hook(void);
#define call3 a7_fl_inspect_syscall
#else
static long call3(long number,long a,long b,long c) {
    register long r7 __asm__("r7")=number;
    register long r0 __asm__("r0")=a,r1 __asm__("r1")=b,r2 __asm__("r2")=c;
    __asm__ volatile("svc #0":"+r"(r0):"r"(r7),"r"(r1),"r"(r2):"memory","cc");return r0;
}
#endif
static int same(const void *a,const void *b,unsigned n) {
    const unsigned char *x=a,*y=b;for(unsigned i=0;i<n;i++)if(x[i]!=y[i])return 0;return 1;
}
static void read_copy(void *a,const volatile void *b,unsigned n) {
    unsigned char *x=a;const volatile unsigned char *y=b;for(unsigned i=0;i<n;i++)x[i]=y[i];
}
static long read_file(const char *path,char *out,unsigned capacity) {
    long fd=call3(5,(long)path,0x8000,0);if(fd<0)return fd;
    long used=0;
    while((unsigned)used<capacity) {
        long n=call3(3,fd,(long)(out+used),capacity-(unsigned)used);
        if(n<0){used=n;break;}if(!n)break;used+=n;
    }
    if(call3(6,fd,0,0)<0)return -1;
    return used==(long)capacity?-75:used;
}
static uintptr_t hex(const char **p) {
    uintptr_t value=0;unsigned count=0;
    for(;;){unsigned c=(unsigned char)**p;
        if(c>='0'&&c<='9')c-='0';else if(c>='a'&&c<='f')c=c-'a'+10;else break;
        if(count++==8)return 0;
        value=(value<<4)|c;++*p;
    }return value;
}
static int ends_with(const char *line,const char *path) {
    const char *end=line;while(*end&&*end!='\n')end++;
    unsigned n=0;while(path[n])n++;
    return end-line>(long)n && end[-(long)n-1]==' ' && same(end-n,path,n);
}
static int contains(const char *line,const char *needle) {
    for(;*line&&*line!='\n';line++){const char *a=line,*b=needle;while(*b&&*a==*b){a++;b++;}if(!*b)return 1;}return 0;
}
static int span(uintptr_t address,unsigned n) {
    if(!address||n>UINT32_MAX-address)return 0;
    uintptr_t end=address+n;unsigned i=0;
    while(i<memory.count&&memory.ranges[i].hi<=address)i++;
    if(i==memory.count||memory.ranges[i].lo>address)return 0;
    while(memory.ranges[i].hi<end) {
        uintptr_t previous=memory.ranges[i].hi;
        if(++i==memory.count||memory.ranges[i].lo!=previous)return 0;
    }return 1;
}
static int maps(void) {
    memory.count=0;memory.view=memory.module=0;
    long n=read_file("/proc/self/maps",memory.maps,sizeof memory.maps-1);if(n<=0)return 0;memory.maps[n]=0;
    unsigned views=0,modules=0;uintptr_t previous=0;
    for(const char *p=memory.maps;*p;) {
        const char *end=p;uintptr_t lo=hex(&end);if(*end++!='-')return 0;uintptr_t hi=hex(&end);
        if(!lo||hi<=lo||lo<previous||end[0]!=' ')return 0;
        previous=hi;
        if(end[1]=='r'&&end[4]=='p'&&!contains(p,"/dev/")) {
            if(memory.count==1024)return 0;
            memory.ranges[memory.count].lo=lo;memory.ranges[memory.count++].hi=hi;
        }
        if(contains(p,"r-xp 00000000")) {
            if(ends_with(p,"/usr/lib/viewUnified2.so")){memory.view=lo;views++;}
            if(ends_with(p,"/usr/lib/a7fl.so")){memory.module=lo;modules++;}
        }
        while(*p&&*p!='\n')p++;
        if(*p)p++;
    }
    return views==1&&modules<=1;
}
static int pin(uintptr_t base,unsigned offset,const unsigned char *expected,unsigned n) {
    return offset<=UINT32_MAX-base&&span(base+offset,n)&&same((const void *)(base+offset),expected,n);
}
static int owned_data(uintptr_t address,unsigned n) {
    uintptr_t base=memory.module;
    if(a7_inspect_rw_begin>UINT32_MAX-base||a7_inspect_rw_end>UINT32_MAX-base)return 0;
    return address>=base+a7_inspect_rw_begin && address<=base+a7_inspect_rw_end &&
           n<=base+a7_inspect_rw_end-address && span(address,n);
}
int a7_fl_inspect_read(struct a7_fl_inspect_report *out) {
    if(!out)return A7_FL_INSPECT_IDENTITY;
    for(unsigned i=0;i<sizeof *out;i++)((unsigned char *)out)[i]=0;
    out->magic=0x41374653;out->version=1;out->status=A7_FL_INSPECT_IDENTITY;
    out->bootstrap_bytes=sizeof out->bootstrap;out->runtime_bytes=sizeof out->runtime;
#ifdef A7_FL_INSPECT_PREVIEW
    out->version=2;out->preview_bytes=sizeof out->preview;
#endif
    char version[24];static const char expected[]="37114_13.2026020901";
    long length=read_file("/version.txt",version,sizeof version);
    if(length!=(long)sizeof expected-1||!same(version,expected,sizeof expected-1)||!maps())return out->status;
    out->view_base=memory.view;out->module_base=memory.module;
    if(!pin(memory.view,0x15d958,a7_inspect_dlopen,12)||!pin(memory.view,0x15c8dc,a7_inspect_dlsym,12)||
       !pin(memory.view,0x15bf38,a7_inspect_dlclose,12))return out->status=A7_FL_INSPECT_PINS;
    typedef void *(*Open)(const char *,int);typedef void *(*Symbol)(void *,const char *);typedef int(*Close)(void *);
    void *handle=((Open)(memory.view+0x15d958))("/usr/lib/a7fl.so",2|4);
    if(!handle)return out->status=memory.module?A7_FL_INSPECT_NOLOAD:A7_FL_INSPECT_NOT_LOADED;
    int rc=A7_FL_INSPECT_PINS;
    if(!memory.module || !pin(memory.module,0,a7_inspect_module_header,sizeof a7_inspect_module_header)||
       !pin(memory.module,a7_inspect_boot_va&~1u,a7_inspect_boot_code,sizeof a7_inspect_boot_code)||
       !pin(memory.module,a7_inspect_runtime_va&~1u,a7_inspect_runtime_code,sizeof a7_inspect_runtime_code))goto close;
#ifdef A7_FL_INSPECT_PREVIEW
    if(!pin(memory.module,a7_inspect_preview_va&~1u,a7_inspect_preview_code,sizeof a7_inspect_preview_code))goto close;
#endif
    void *bootstrap=((Symbol)(memory.view+0x15c8dc))(handle,"a7_fl_bootstrap_status");
    void *runtime=((Symbol)(memory.view+0x15c8dc))(handle,"a7_fl_status");
#ifdef A7_FL_INSPECT_PREVIEW
    void *preview=((Symbol)(memory.view+0x15c8dc))(handle,"a7_fl_preview_status");
    out->preview_symbol=(uintptr_t)preview;
    if((uintptr_t)preview!=memory.module+a7_inspect_preview_va) {rc=A7_FL_INSPECT_SYMBOL;goto close;}
#endif
    out->bootstrap_symbol=(uintptr_t)bootstrap;out->runtime_symbol=(uintptr_t)runtime;
    if((uintptr_t)bootstrap!=memory.module+a7_inspect_boot_va || (uintptr_t)runtime!=memory.module+a7_inspect_runtime_va) {
        rc=A7_FL_INSPECT_SYMBOL;goto close;
    }
    const struct a7_fl_bootstrap_report *b=((const struct a7_fl_bootstrap_report *(*)(void))bootstrap)();
    const struct a7_fl_module_status *r=((const struct a7_fl_module_status *(*)(void))runtime)();
    if(!owned_data((uintptr_t)b,sizeof *b)||!owned_data((uintptr_t)r,sizeof *r)){rc=A7_FL_INSPECT_POINTER;goto close;}
#ifdef A7_FL_INSPECT_PREVIEW
    const struct a7_fl_preview_report *p=((const struct a7_fl_preview_report *(*)(void))preview)();
    if(!owned_data((uintptr_t)p,sizeof *p)){rc=A7_FL_INSPECT_POINTER;goto close;}
#endif
    for(unsigned attempt=0;attempt<3;attempt++) {
        struct a7_fl_bootstrap_report again_boot;struct a7_fl_module_status again_runtime;
        read_copy(&out->bootstrap,b,sizeof *b);read_copy(&out->runtime,r,sizeof *r);
#ifdef A7_FL_INSPECT_PREVIEW
        struct a7_fl_preview_report again_preview;
        read_copy(&out->preview,p,sizeof *p);
#endif
        __asm__ volatile("dmb ish":::"memory");
#ifdef A7_FL_INSPECT_TEST
        a7_fl_inspect_copy_hook();
#endif
        read_copy(&again_boot,b,sizeof *b);read_copy(&again_runtime,r,sizeof *r);
#ifdef A7_FL_INSPECT_PREVIEW
        read_copy(&again_preview,p,sizeof *p);
        if(!same(&out->preview,&again_preview,sizeof *p))continue;
#endif
        if(same(&out->bootstrap,&again_boot,sizeof *b)&&same(&out->runtime,&again_runtime,sizeof *r)) {
            out->stable=1;rc=A7_FL_INSPECT_LOADED;goto close;
        }
    }
    rc=A7_FL_INSPECT_UNSTABLE;
close:
    out->dlclose_result=((Close)(memory.view+0x15bf38))(handle);
    out->status=out->dlclose_result?A7_FL_INSPECT_CLOSE:rc;return out->status;
}
#ifndef A7_FL_INSPECT_TEST
static struct a7_fl_inspect_report report;
__attribute__((constructor)) static void inspect_resident(void) {
    a7_fl_inspect_read(&report);
    call3(10,(long)"/tmp/jiritsu/libJit.so",0,0);
    long fd=call3(5,(long)"/tmp/jiritsu/a7status.bin",1|64|128|0x8000,0600);
    if(fd<0)return;
    unsigned done=0;
    while(done<sizeof report) {
        long n=call3(4,fd,(long)((unsigned char *)&report+done),sizeof report-done);
        if(n<=0||(unsigned)n>sizeof report-done)break;
        done+=(unsigned)n;
    }
    call3(118,fd,0,0);call3(6,fd,0,0);
}
#endif
