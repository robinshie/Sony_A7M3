/* Read-only boot identity, module presence, and one original instruction word. */
#include <stdint.h>
static struct { uint32_t magic,version; int32_t module_open,physical_read,uptime_n,boot_id_n;
    uint32_t site; char uptime[64],boot_id[64]; } result;
static long sc(long n,long a,long b,long c){
    register long r7 __asm__("r7")=n,r0 __asm__("r0")=a,r1 __asm__("r1")=b,r2 __asm__("r2")=c;
    __asm__ volatile("svc #0":"+r"(r0):"r"(r7),"r"(r1),"r"(r2):"memory","cc");return r0;
}
static long read_word(long fd){
    register long r7 __asm__("r7")=180,r0 __asm__("r0")=fd,r1 __asm__("r1")=(long)&result.site;
    register long r2 __asm__("r2")=4,r3 __asm__("r3")=0,r4 __asm__("r4")=0x0390619c,r5 __asm__("r5")=0;
    __asm__ volatile("svc #0":"+r"(r0):"r"(r7),"r"(r1),"r"(r2),"r"(r3),"r"(r4),"r"(r5):"memory","cc");return r0;
}
static long read_file(const char *path,char *buf){
    long fd=sc(5,(long)path,0,0);if(fd<0)return fd;
    long n=sc(3,fd,(long)buf,63),c=sc(6,fd,0,0);return c?c:n;
}
__attribute__((constructor)) static void run(void){
    result.magic=0x41374b53;result.version=1;
    result.module_open=sc(5,(long)"/sys/module/a7capture",0x4000,0);
    if(result.module_open>=0)sc(6,result.module_open,0,0);
    result.uptime_n=read_file("/proc/uptime",result.uptime);
    result.boot_id_n=read_file("/proc/sys/kernel/random/boot_id",result.boot_id);
    long fd=sc(5,(long)"/dev/mem",0x1000,0);
    result.physical_read=fd<0?fd:read_word(fd);if(fd>=0)sc(6,fd,0,0);
    fd=sc(5,(long)"/tmp/jiritsu/a7ks.bin",1|64|128,0600);if(fd<0)return;
    long n=sc(4,fd,(long)&result,sizeof result),c=sc(6,fd,0,0);
    if(n!=sizeof result || c)sc(10,(long)"/tmp/jiritsu/a7ks.bin",0,0);
}
