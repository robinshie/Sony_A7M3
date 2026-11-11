#include "native_fsmeta.h"
static long syscall6(void*ctx,long nr,long a,long b,long c,long d,long e,long f){
 (void)ctx;register long r7 __asm__("r7")=nr;register long r0 __asm__("r0")=a,r1 __asm__("r1")=b,r2 __asm__("r2")=c;
 register long r3 __asm__("r3")=d,r4 __asm__("r4")=e,r5 __asm__("r5")=f;
 __asm__ volatile("svc #0":"+r"(r0):"r"(r7),"r"(r1),"r"(r2),"r"(r3),"r"(r4),"r"(r5):"memory","cc");return r0;
}
static NfmReport report;
__attribute__((constructor))static void inspect(void){
 /* Exclusive report must exist before even read-only collection starts. */
 long fd=syscall6(0,5,(long)"/tmp/jiritsu/a7fsmeta.bin",1|64|128|0x8000,0600,0,0,0);if(fd<0)return;
 nfm_read(&report,syscall6,0);
 unsigned used=0;while(used<sizeof report){long n=syscall6(0,4,fd,(long)((unsigned char*)&report+used),sizeof report-used,0,0,0);if(n<=0||(unsigned)n>sizeof report-used)break;used+=(unsigned)n;}
 syscall6(0,6,fd,0,0,0,0,0);
}
