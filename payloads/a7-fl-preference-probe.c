/* Bounded production-store smoke test. Initializes only default OFF generation1
 * when BOTH fixed preference paths are absent. Never changes a backup LUT. */
#include "a7-fl-posix.h"
#include "a7-fl-runtime.h"
#include "preference-probe-config.h" /* private, source-pinned build inputs */
__attribute__((visibility("hidden"))) void *memset(void *destination,int value,unsigned size) {
    unsigned char *p=destination;while(size--)*p++=(unsigned char)value;return destination;
}
static long call3(long nr,long a,long b,long c) {
    register long r7 __asm__("r7")=nr;
    register long r0 __asm__("r0")=a,r1 __asm__("r1")=b,r2 __asm__("r2")=c;
    __asm__ volatile("svc #0":"+r"(r0):"r"(r7),"r"(r1),"r"(r2):"memory","cc");return r0;
}
static struct {uint32_t magic,version,bytes;int32_t status,present,save,reopen;
               struct a7_fl_preference preference;uint8_t record[128];} report;
static int equal(const void *a,const void *b,unsigned n) {
    const unsigned char *x=a,*y=b;while(n--)if(*x++!=*y++)return 0;return 1;
}
__attribute__((constructor)) static void test_store(void) {
    report.magic=0x41374653;report.version=1;report.bytes=sizeof report;report.status=-1;
    char version[24]={0};long fd=call3(5,(long)"/version.txt",0,0);
    if(fd<0)goto done;
    long n=call3(3,fd,(long)version,24);call3(6,fd,0,0);
    if(n!=A7_PROBE_BUILD_LENGTH || !equal(version,a7_probe_build,A7_PROBE_BUILD_LENGTH))goto done;
    struct a7_fl_store_io io;a7_fl_posix_io(&io);
    struct a7_fl_store store;struct a7_fl_preference before;
    int existed=0;
    report.status=a7_fl_store_open(&store,&io,a7_probe_original_sha,a7_probe_build,&before,&existed);
    report.present=existed;
    if(report.status)goto done;
    if(report.present){report.status=-10;goto done;}
    struct a7_fl_preference p={.generation=1,.enabled=0,.parameters={0,0,0,0,0,0,1,0},.candidate_crc=A7_PROBE_CANDIDATE_CRC};
    report.save=a7_fl_store_save(&store,&p);if(report.save){report.status=-11;goto done;}
    int present=0;
    report.reopen=a7_fl_store_open(&store,&io,a7_probe_original_sha,a7_probe_build,&report.preference,&present);
    if(report.reopen||!present||!equal(&p,&report.preference,sizeof p)){report.status=-12;goto done;}
    unsigned length=0;
    if(io.read(io.opaque,0,report.record,128,&length)||length!=128){report.status=-13;goto done;}
    report.status=1;
done:
    fd=call3(5,(long)"/tmp/jiritsu/a7flstore.bin",1|64|128,0600);
    if(fd>=0){unsigned written=0;while(written<sizeof report){
        long w=call3(4,fd,(long)((unsigned char *)&report+written),sizeof report-written);
        if(w<=0)break;
        written+=(unsigned)w;
    }call3(118,fd,0,0);call3(6,fd,0,0);}
}
