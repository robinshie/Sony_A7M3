#include "native_menu_activate.h"
long nma_linux_syscall(void*ctx,long nr,long a,long b,long c,long d,long e,long f){(void)ctx;register long r7 __asm__("r7")=nr;register long r0 __asm__("r0")=a,r1 __asm__("r1")=b,r2 __asm__("r2")=c,r3 __asm__("r3")=d,r4 __asm__("r4")=e,r5 __asm__("r5")=f;__asm__ volatile("svc #0":"+r"(r0):"r"(r7),"r"(r1),"r"(r2),"r"(r3),"r"(r4),"r"(r5):"memory","cc");return r0;}
