/* Bounded diagnostic of the ORIGINAL Creative Style setter. Not an installer.
 * The private generated header pins model/build, code and the exact current
 * style/slot/parameters. This changes one stock sharpness setting; the host
 * independently reads the active property and restores the initial setting.
 */
#define A7_RUNTIME_LIBRARY_ONLY
#include "a7-runtime-probe.c"
#include "sharpness-probe-pins.h"
#include "a7-fl-sharpness-native.h"
static struct { uint32_t magic,view,backup; int32_t status,returned; } answer;
static int same(const void *a,const void *b,unsigned n) {
    const unsigned char *x=a,*y=b;while(n--)if(*x++!=*y++)return 0;return 1;
}
static int pin(uint32_t base,uint32_t offset,const void *bytes,unsigned n) {
    return offset<=UINT32_MAX-base && readable(base+offset,n) &&
           same((void *)(uintptr_t)(base+offset),bytes,n);
}
static uint32_t base(const char *path) {
    for(const char *p=report.maps;*p;) {
        const char *end=p;while(*end&&*end!='\n')end++;
        unsigned n=0;while(path[n])n++;
        if(end-p>(int)n && end[-(int)n-1]==' ' && same(end-n,path,n) &&
           contains(p,"r-xp 00000000"))return hex(&p);
        p=*end?end+1:end;
    }return 0;
}
static int execute(void) {
    char version[24];static const char build[]="37114_13.2026020901";
    long n=read_proc("/version.txt",version,sizeof version);
    if(n!=(long)sizeof build-1||!same(version,build,sizeof build-1))return -1;
    report.maps_n=read_proc("/proc/self/maps",report.maps,sizeof report.maps-1);
    if(report.maps_n<=0)return -2;
    report.maps[report.maps_n]=0;
    answer.view=base("/usr/lib/viewUnified2.so");answer.backup=base("/usr/lib/libbackup.so");
    if(!answer.view||!answer.backup)return -3;
    if(!pin(answer.view,0x420d18,setter_pin,sizeof setter_pin)||
       !pin(answer.backup,0x1174,size_pin,sizeof size_pin)||
       !pin(answer.backup,0x1204,read_pin,sizeof read_pin))return -4;
    for(unsigned i=0;i<sizeof native_offsets/sizeof native_offsets[0];i++)
        if(!pin(answer.view,native_offsets[i],native_pins[i],16))return -4;
    int (*size)(unsigned)=(void *)(uintptr_t)(answer.backup+0x1175);
    int (*read)(unsigned,void *)=(void *)(uintptr_t)(answer.backup+0x1205);
    unsigned char model[16];static const char expected[16]="ILCE-7M3";
    if(size(0x3e0005)!=16||read(0x3e0005,model)!=16||!same(model,expected,16))return -5;
    for(unsigned i=0;i<sizeof guard_ids/sizeof guard_ids[0];i++) {
        unsigned char value=0;
        if(size(guard_ids[i])!=1||read(guard_ids[i],&value)!=1||value!=guard_values[i])return -6;
    }
    if(style<0||style>13||style==12||box<0||box>6||contrast<-3||contrast>3||
       saturation<-3||saturation>3||target<-3||target>3)return -7;
    typedef int (*Setter)(void *,int,int,int,int,int);
    answer.returned=model_only?a7_fl_sharpness_request(answer.view,target):
        ((Setter)(uintptr_t)(answer.view+0x420d19))(0,style,box,contrast,saturation,target);
    /* A return of 1 only means queued, not applied. Host MUST verify separately. */
    return 1;
}
__attribute__((constructor)) static void entry(void) {
    answer.magic=0x41375350;answer.status=execute();
    sc3(10,(long)"/tmp/jiritsu/libJit.so",0,0);
    long fd=sc3(5,(long)"/tmp/jiritsu/a7sharp.bin",1|64|128|0x8000,0600);if(fd<0)return;
    unsigned done=0;
    while(done<sizeof answer) {
        long n=sc3(4,fd,(long)((unsigned char *)&answer+done),sizeof answer-done);
        if(n<=0)break;done+=(unsigned)n;
    }
    sc3(118,fd,0,0);sc3(6,fd,0,0);
}
