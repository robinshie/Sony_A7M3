/* Bounded, fault-reporting reads while the native StillInfo caller is active.
 * No image writes. A valid mapping alone is still not proof of pixel ownership. */
#include <stdint.h>
#ifdef A7YC_SAMPLE_TEST
extern long test_sc6(long,long,long,long,long,long,long);
#define syscall6 test_sc6
#else
static long syscall6(long nr,long a,long b,long c,long d,long e,long f){
 register long r7 __asm__("r7")=nr,r0 __asm__("r0")=a,r1 __asm__("r1")=b,r2 __asm__("r2")=c,r3 __asm__("r3")=d,r4 __asm__("r4")=e,r5 __asm__("r5")=f;
 __asm__ volatile("svc #0":"+r"(r0):"r"(r7),"r"(r1),"r"(r2),"r"(r3),"r"(r4),"r"(r5):"memory","cc");return r0;
}
#endif
struct A7YCSample {int32_t result;uint32_t count;unsigned char data[256];};
void a7yc_sample(const uint32_t *info,struct A7YCSample *samples){
 long fd=syscall6(5,(long)"/proc/self/mem",0x80000,0,0,0,0);
 for(unsigned i=0;i<12;i++){
  struct A7YCSample*s=&samples[i];uint32_t address=info[2+i*4],length=info[3+i*4];s->count=0;
  if(!address&&!length){s->result=0;continue;}
  if(!address||!length||address>UINT32_MAX-length){s->result=-22;continue;}
  if(fd<0){s->result=fd;continue;}
  unsigned n=length<256?length:256;
  /* ARM EABI pread64: r3 is alignment padding, low/high offset in r4/r5. */
  long got=syscall6(180,fd,(long)s->data,n,0,address,0);
  if(got>(long)n){s->result=-75;continue;}
  s->result=got;if(got>0)s->count=got;
 }
 if(fd>=0)(void)syscall6(6,fd,0,0,0,0,0);
}
