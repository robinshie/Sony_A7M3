#include "dmm_frame_dump.h"
#ifndef A7_DMM_DUMP_TEST
static long dump_sc6(long nr,long a,long b,long c,long d,long e,long f){
 register long r7 __asm__("r7")=nr,r0 __asm__("r0")=a,r1 __asm__("r1")=b,r2 __asm__("r2")=c,r3 __asm__("r3")=d,r4 __asm__("r4")=e,r5 __asm__("r5")=f;
 __asm__ volatile("svc #0":"+r"(r0):"r"(r7),"r"(r1),"r"(r2),"r"(r3),"r"(r4),"r"(r5):"memory","cc");return r0;}
#endif
static long dcall(long nr,long a,long b,long c){return dump_sc6(nr,a,b,c,0,0,0);}
static int expired(const uint32_t start[2]){
 uint32_t now[2];if(dcall(263,1,(long)now,0))return 1;
 if(now[0]<start[0])return 1;
 uint32_t seconds=now[0]-start[0];return seconds>1||(seconds==1&&now[1]>=start[1]);
}
void a7_dmm_frame_dump(struct a7_dmm_dump_result *r,uint32_t physical,uint32_t length){
 if(!r)return;r->status=-1;r->physical=physical;r->length=length;r->written=r->reads=0;
 /* Pinned kernel iomem proves low DRAM ends at 0x40000000. Narrow further to
  * the observed DMM area, excluding the Linux kernel/low-memory region. This
  * is only a guard in addition to a caller-held native DMM reference. */
 if(physical<0x10000000||physical>=0x40000000||length<1024*1024||length>8*1024*1024||length>0x40000000-physical)return;
#ifdef A7_DMM_SPARSE_FRAME
 /* Diagnostic byte rows, not a claim that the camera uses NV16. Require the
  * observed 1920-byte row hypothesis, retain one row out of every sixteen. */
 if(length!=4177920u)return;
 uint32_t target=length/16;
#else
 uint32_t target=length;
#endif
 uint32_t started[2];if(dcall(263,1,(long)started,0)){r->status=-2;return;}
 long input=dcall(5,(long)"/dev/mem",0x1000,0);if(input<0){r->status=-3;return;}
 /* Never overwrite or remove a preexisting file. This is a temporary report,
  * not a firmware file, and the source descriptor is read-only. */
 long output=dcall(5,(long)A7_DMM_DUMP_PATH,1|64|128|0x8000,0600);
 if(output<0){r->status=-4;dcall(6,input,0,0);return;}
 uint8_t bytes[4096];r->status=-5;
 while(r->written<target){
  if(expired(started)){r->status=-6;break;}
  uint32_t n,offset;
#ifdef A7_DMM_SPARSE_FRAME
  n=1920;offset=r->written*16;
#else
  n=target-r->written;if(n>sizeof bytes)n=sizeof bytes;offset=r->written;
#endif
  long got=dump_sc6(180,input,(long)bytes,n,0,physical+offset,0);r->reads++;
  if(got!=(long)n){r->status=-7;break;}
  uint32_t done=0;
  while(done<n){long put=dcall(4,output,(long)(bytes+done),n-done);
   if(put<=0||(unsigned long)put>n-done){r->status=-8;break;}done+=(uint32_t)put;}
  if(done!=n)break;r->written+=n;
 }
 if(r->written==target)r->status=dcall(118,output,0,0)?-9:0;
 if(dcall(6,output,0,0)&&!r->status)r->status=-10;
 if(dcall(6,input,0,0)&&!r->status)r->status=-11;
 if(r->status)dcall(10,(long)A7_DMM_DUMP_PATH,0,0);
}
