/* Read /proc/mounts as a stream; maintenance file reads use st_size=0 there. */
#include <stdint.h>
static long syscall3(long n,long a,long b,long c) {
    register long r7 __asm__("r7")=n;
    register long r0 __asm__("r0")=a;
    register long r1 __asm__("r1")=b;
    register long r2 __asm__("r2")=c;
    __asm__ volatile("svc #0":"+r"(r0):"r"(r7),"r"(r1),"r"(r2):"memory","cc");
    return r0;
}
static struct { uint32_t magic; int32_t count; char data[16384]; } result;
__attribute__((constructor)) static void inspect_mounts(void) {
    result.magic=0x41374d50;
    long fd=syscall3(5,(long)"/proc/mounts",0,0);
    if(fd<0) result.count=fd;
    else {
        while(result.count<(long)sizeof result.data) {
            long n=syscall3(3,fd,(long)(result.data+result.count),sizeof result.data-result.count);
            if(n<=0) { if(n<0)result.count=n; break; }
            result.count+=n;
        }
        if(result.count==sizeof result.data) result.count=-75;
        syscall3(6,fd,0,0);
    }
    syscall3(10,(long)"/tmp/jiritsu/libJit.so",0,0);
    fd=syscall3(5,(long)"/tmp/jiritsu/a7mount.bin",1|64|128,0600);
    if(fd>=0) {
        unsigned done=0;
        while(done<sizeof result) {
            long n=syscall3(4,fd,(long)((char *)&result+done),sizeof result-done);
            if(n<=0)break;
            done+=n;
        }
        syscall3(118,fd,0,0);syscall3(6,fd,0,0);
    }
}
