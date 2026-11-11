#include "native_module_replace.h"
long nmr_linux_call(void*unused,long nr,long a,long b,long c,long d,long e,long f){
 (void)unused;register long r7 __asm__("r7")=nr;register long r0 __asm__("r0")=a,r1 __asm__("r1")=b,r2 __asm__("r2")=c;
 register long r3 __asm__("r3")=d,r4 __asm__("r4")=e,r5 __asm__("r5")=f;
 __asm__ volatile("svc #0":"+r"(r0):"r"(r7),"r"(r1),"r"(r2),"r"(r3),"r"(r4),"r"(r5):"memory","cc");return r0;
}
