/* Verify fault-reporting self-memory reads against our own small test buffer. */
#define A7_RUNTIME_LIBRARY_ONLY
#include "a7-runtime-probe.c"
static long sc6(long nr,long a,long b,long c,long d,long e,long f){
 register long r7 __asm__("r7")=nr,r0 __asm__("r0")=a,r1 __asm__("r1")=b,r2 __asm__("r2")=c,r3 __asm__("r3")=d,r4 __asm__("r4")=e,r5 __asm__("r5")=f;
 __asm__ volatile("svc #0":"+r"(r0):"r"(r7),"r"(r1),"r"(r2),"r"(r3),"r"(r4),"r"(r5):"memory","cc");return r0;
}
struct Iov{void*base;uint32_t length;};
static long self_read(void*out,const void*in,unsigned n){
 struct Iov local={out,n},remote={(void*)in,n};
 return sc6(376,sc3(20,0,0,0),(long)&local,1,(long)&remote,1,0);
}
static struct {uint32_t magic,version;int32_t vm_read,vm_invalid,mem_open,mem_read,mem_invalid;uint32_t vm_matches,mem_matches;int32_t kernel_n,meminfo_n;char kernel[256],meminfo[2048];} result;
static unsigned char source[16],a[16],b[16];
__attribute__((constructor)) static void capture(void){
 for(unsigned i=0;i<16;i++)source[i]=(unsigned char)(17+i*13);
 result.magic=0x41374d52;result.version=1;
 result.kernel_n=read_proc("/proc/version",result.kernel,sizeof result.kernel-1);
 result.meminfo_n=read_proc("/proc/meminfo",result.meminfo,sizeof result.meminfo-1);
 result.vm_read=self_read(a,source,16);result.vm_invalid=self_read(a,(void*)1,16);
 long fd=sc3(5,(long)"/proc/self/mem",0,0);result.mem_open=fd;
 if(fd>=0){
  result.mem_read=sc6(180,fd,(long)b,16,0,(uint32_t)(uintptr_t)source,0);
  result.mem_invalid=sc6(180,fd,(long)b,16,0,1,0);sc3(6,fd,0,0);
 }
 result.vm_matches=result.vm_read==16;result.mem_matches=result.mem_read==16;
 for(unsigned i=0;i<16;i++){if(a[i]!=source[i])result.vm_matches=0;if(b[i]!=source[i])result.mem_matches=0;}
 sc3(10,(long)"/tmp/jiritsu/libJit.so",0,0);fd=sc3(5,(long)"/tmp/jiritsu/a7mr.bin",1|64|128|0x8000,0600);if(fd<0)return;
 unsigned at=0;while(at<sizeof result){long n=sc3(4,fd,(long)((char*)&result+at),sizeof result-at);if(n<=0||(unsigned)n>sizeof result-at)break;at+=(unsigned)n;}
 sc3(118,fd,0,0);sc3(6,fd,0,0);
}
