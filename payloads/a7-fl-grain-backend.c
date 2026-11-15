#include <stdint.h>
#include "a7-fl-grain-backend.h"
#include "a7-fl-grain-kernel.h" /* private name, four source words, exact blob */
extern const unsigned char a7_grain_kernel_start[],a7_grain_kernel_end[];
static long syscall3(long nr,long a,long b,long c){
#ifdef A7_FL_GRAIN_BACKEND_TEST
    extern long a7_grain_test_syscall(long,long,long,long);
    return a7_grain_test_syscall(nr,a,b,c);
#else
    register long r7 __asm__("r7")=nr,r0 __asm__("r0")=a,r1 __asm__("r1")=b,r2 __asm__("r2")=c;
    __asm__ volatile("svc #0":"+r"(r0):"r"(r7),"r"(r1),"r"(r2):"memory","cc");return r0;
#endif
}
static int read_text(const char *path,char *out,unsigned cap){
    long fd=syscall3(5,(long)path,0x8000,0);if(fd<0)return (int)fd;
    unsigned used=0;int err=0;
    for(;;){
        if(used+1==cap){err=-75;break;}
        long n=syscall3(3,fd,(long)(out+used),cap-used-1);
        if(n<0){err=(int)n;break;}if(!n)break;
        if((unsigned)n>cap-used-1){err=-5;break;}used+=(unsigned)n;
    }
    long closed=syscall3(6,fd,0,0);
    if(!err&&closed)err=(int)closed;
    if(err)return err;
    out[used]=0;return (int)used;
}
static int uint_word(const char **cursor,uint32_t *out){
    const char *p=*cursor;uint32_t n=0;
    if(*p<'0'||*p>'9')return 0;
    do{unsigned v=(unsigned)(*p-'0');if(n>(UINT32_MAX-v)/10)return 0;n=n*10+v;p++;}while(*p>='0'&&*p<='9');
    *cursor=p;*out=n;return 1;
}
static int kernel_identity(void){
    char text[4096];int n=read_text("/sys/module/" A7_GRAIN_KERNEL_NAME "/parameters/report",text,sizeof text);
    if(n<0)return n;
    const char *p=text;uint32_t value;
    for(unsigned i=0;i<368;i++){
        if(!uint_word(&p,&value))return -71;
        if((i==0&&value!=0x4137434b)||(i==1&&value!=1)||(i==3&&value!=1)||
           (i==4&&value!=1)||(i==5&&value)||(i==11&&value!=1)||
           (i>=12&&i<16&&value!=a7_grain_kernel_source_id[i-12]))return -116;
        if(i<367){if(*p++!=',')return -71;}
    }
    if(*p=='\n')p++;
    return *p?-71:0;
}
static int ensure_kernel(void){
    int rc=kernel_identity();if(rc!=-2)return rc;
    char uts[390];long result=syscall3(122,(long)uts,0,0);
    if(result)return (int)result;
    const char expected[]="3.0.27_nl-rt106+";
    for(unsigned i=0;i<sizeof expected;i++)if(uts[130+i]!=expected[i])return -19;
    result=syscall3(128,(long)a7_grain_kernel_start,
                    (long)(a7_grain_kernel_end-a7_grain_kernel_start),(long)"arm=1 selection=0");
    if(result&&result!=-17)return (int)result;
    /* Default off. Never configure an existing foreign or disarmed module. */
    return kernel_identity();
}
static int apply_selection(unsigned desired){
    int rc=ensure_kernel();if(rc)return rc;
    char value[12],reverse[10];unsigned used=0,digits=desired;
    do{reverse[used++]=(char)('0'+digits%10);digits/=10;}while(digits);
    for(unsigned i=0;i<used;i++)value[i]=reverse[used-i-1];
    value[used++]='\n';
    long fd=syscall3(5,(long)"/sys/module/" A7_GRAIN_KERNEL_NAME "/parameters/selection",1|0x8000,0);
    if(fd<0)return (int)fd;
    /* A sysfs parameter is one transaction; don't replay a short write. */
    long written=syscall3(4,fd,(long)value,used),closed=syscall3(6,fd,0,0);
    if(written!=(long)used||closed)return written<0?(int)written:closed?(int)closed:-5;
    char text[32];int n=read_text("/sys/module/" A7_GRAIN_KERNEL_NAME "/parameters/selection",text,sizeof text);
    if(n<0)return n;
    const char *p=text;uint32_t actual;
    if(!uint_word(&p,&actual))return -71;
    if(*p=='\n')p++;
    return *p||actual!=desired?-5:0;
}
int a7_fl_grain_apply(unsigned preset,unsigned strength){
    if(preset>3||strength>9)return -22;
    return apply_selection(preset?(preset<<4)|strength:0);
}
int a7_fl_film_apply(unsigned preset,unsigned grain,int halation){
    if(preset>3||grain>9||halation<-9||halation>9)return -22;
    return apply_selection(preset?(preset<<9)|((unsigned)(halation+9)<<4)|grain:0);
}

int a7_fl_vignette_apply(unsigned preset,unsigned grain,int halation,int vignette){
    if(preset>3||grain>9||halation<-9||halation>9||vignette<-9||vignette>9)return -22;
    return apply_selection(preset?(preset<<14)|((unsigned)(vignette+9)<<9)|((unsigned)(halation+9)<<4)|grain:0);
}
