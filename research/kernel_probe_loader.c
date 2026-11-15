/* Temporary read-only kernel probe loader. No forced unload or persistent files. */
#include <stdint.h>
#include "pins.h"
#ifndef A7_CAPTURE_ACTION
#ifdef A7_SOURCE_SAMPLE
#define MODULE_NAME "a7source"
#define OUTPUT_NAME "a7ss.bin"
#else
#define MODULE_NAME "a7kprobe"
#define OUTPUT_NAME "a7kp.bin"
#endif
#define MODULE_ARGS ""
#else
#ifdef A7_CAPTURE_NAME
#define MODULE_NAME A7_CAPTURE_NAME
#else
#define MODULE_NAME "a7capture"
#endif
#define OUTPUT_NAME "a7kc.bin"
#if A7_CAPTURE_ACTION == 1
#ifdef A7_CAPTURE_ARGS
#define MODULE_ARGS A7_CAPTURE_ARGS
#else
#define MODULE_ARGS "arm=1"
#endif
#else
#define MODULE_ARGS ""
#endif
#endif
extern const unsigned char module_start[], module_end[];
#ifndef A7_REPORT_BYTES
#define A7_REPORT_BYTES 1024
#endif
static struct {
    uint32_t magic, version;
    int32_t status, load_result, unload_result;
    uint32_t used;
    char release[65], reserved[3], text[A7_REPORT_BYTES];
} report;
static long sc3(long n,long a,long b,long c) {
    register long r7 __asm__("r7")=n,r0 __asm__("r0")=a,r1 __asm__("r1")=b,r2 __asm__("r2")=c;
    __asm__ volatile("svc #0":"+r"(r0):"r"(r7),"r"(r1),"r"(r2):"memory","cc");return r0;
}
static __attribute__((unused)) long pread_phys(long fd,void *out,unsigned size,uint32_t physical){
    register long r7 __asm__("r7")=180,r0 __asm__("r0")=fd,r1 __asm__("r1")=(long)out;
    register long r2 __asm__("r2")=size,r3 __asm__("r3")=0,r4 __asm__("r4")=physical,r5 __asm__("r5")=0;
    __asm__ volatile("svc #0":"+r"(r0):"r"(r7),"r"(r1),"r"(r2),"r"(r3),"r"(r4),"r"(r5):"memory","cc");return r0;
}
static int eq(const unsigned char *a,const unsigned char *b,unsigned n){
    for(unsigned i=0;i<n;i++)if(a[i]!=b[i])return 0;
    return 1;
}
static __attribute__((unused)) int preflight(void){
    unsigned char b[64];uint32_t root=0,table=0;
    long fd=sc3(5,(long)"/dev/mem",0x1000,0);if(fd<0)return 0;
    int ok=pread_phys(fd,b,sizeof kernel_pin,0x00118470)==sizeof kernel_pin && eq(b,kernel_pin,sizeof kernel_pin);
    ok=ok && pread_phys(fd,b,sizeof stage_pin,0x0390618c)==sizeof stage_pin && eq(b,stage_pin,sizeof stage_pin);
    ok=ok && pread_phys(fd,&root,4,0x0475a218)==4 && root==0x635c6000;
    ok=ok && pread_phys(fd,&table,4,0x035c6014)==4 && table==0x635c60b4;
    return sc3(6,fd,0,0)==0 && ok;
}
__attribute__((constructor)) static void run(void){
    report.magic=0x41374b4c;report.version=1;report.status=1;
    report.load_result=report.unload_result=-9999;
    static char uts[390];
    if(sc3(122,(long)uts,0,0))goto output;
    for(unsigned i=0;i<65;i++)report.release[i]=uts[130+i];
    static const unsigned char expected[]="3.0.27_nl-rt106+";
    if(!eq((const unsigned char *)report.release,expected,sizeof expected))goto output;
    report.status=2;
    /* ARM O_DIRECTORY is 040000 octal; 0x10000 is ARM O_DIRECT. */
    long fd=sc3(5,(long)"/sys/module/" MODULE_NAME,0x4000,0);
#if defined(A7_CAPTURE_ACTION) && A7_CAPTURE_ACTION == 2
    if(fd<0){report.load_result=fd;goto output;}
    sc3(6,fd,0,0);
    report.status=8;
    fd=sc3(5,(long)"/sys/module/" MODULE_NAME "/parameters/disarm",1,0);
    if(fd<0)goto output;
    long written=sc3(4,fd,(long)"1",1),closed=sc3(6,fd,0,0);
    if(written!=1 || closed)goto output;
#else
    if(fd>=0){sc3(6,fd,0,0);goto output;}
    if(fd!=-2)goto output;
    report.status=3;if(!preflight())goto output;
    report.status=4;
    report.load_result=sc3(128,(long)module_start,module_end-module_start,(long)MODULE_ARGS);
    if(report.load_result)goto output;
#endif
    report.status=5;
#ifdef A7_SOURCE_SAMPLE
    fd=sc3(5,(long)"/sys/module/" MODULE_NAME "/sample",0,0);
    if(fd>=0){
        long n=0,c;
        while(report.used<sizeof report.text){
            n=sc3(3,fd,(long)(report.text+report.used),sizeof report.text-report.used);
            if(n<=0)break;
            report.used+=n;
        }
        c=sc3(6,fd,0,0);
        if(n==0 && report.used==97988 && !c)report.status=0;
    }
#else
    fd=sc3(5,(long)"/sys/module/" MODULE_NAME "/parameters/report",0,0);
    if(fd>=0){
        long n=sc3(3,fd,(long)report.text,sizeof report.text-1);
        long c=sc3(6,fd,0,0);
        if(n>0 && n<(long)sizeof report.text-1 && !c){report.used=n;report.status=0;}
    }
#endif
#if !defined(A7_CAPTURE_ACTION) || A7_CAPTURE_ACTION == 0
    /* O_NONBLOCK only; never O_TRUNC / force. Nothing remains registered. */
    report.unload_result=sc3(129,(long)MODULE_NAME,0x800,0);
    if(report.unload_result){report.status=6;goto output;}
    fd=sc3(5,(long)"/sys/module/" MODULE_NAME,0x4000,0);
    if(fd>=0){sc3(6,fd,0,0);report.status=7;}
    else if(fd!=-2)report.status=7;
#endif
output:
    fd=sc3(5,(long)"/tmp/jiritsu/" OUTPUT_NAME,1|64|128,0600);if(fd<0)return;
    unsigned at=0;const char *b=(const char *)&report;
    while(at<sizeof report){long n=sc3(4,fd,(long)(b+at),sizeof report-at);if(n<=0)break;at+=n;}
    long c=sc3(6,fd,0,0);if(at!=sizeof report || c)sc3(10,(long)"/tmp/jiritsu/" OUTPUT_NAME,0,0);
}
