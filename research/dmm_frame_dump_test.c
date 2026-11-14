#include <stdint.h>
#include <stddef.h>
#ifndef DUMP_QEMU
#include <stdio.h>
#include <stdlib.h>
#endif
static unsigned checks,cases,mode,clocks,reads,writes,closed,created,removed,position;
static unsigned physical=0x20000000;
#ifdef A7_DMM_SPARSE_FRAME
#define TOTAL 4177920u
#define OUTPUT_TOTAL 261120u
#define READ_BYTES 1920u
#define SOURCE_STEP 30720u
#else
#define TOTAL 1048576u
#define OUTPUT_TOTAL TOTAL
#define READ_BYTES 4096u
#define SOURCE_STEP READ_BYTES
#endif
static void put(const char *s){
#ifdef DUMP_QEMU
 volatile uint32_t *u=(void*)0x10009000;while(*s){while(u[6]&32){}u[0]=*s++;}
#else
 fputs(s,stdout);
#endif
}
static void number(unsigned n){char b[12];unsigned i=0;do{b[i++]=(char)('0'+n%10);n/=10;}while(n);while(i){char s[2]={b[--i],0};put(s);}}
static void stop(int rc){
#ifdef DUMP_QEMU
 (void)rc;register unsigned r0 __asm__("r0")=0x18,r1 __asm__("r1")=0x20026;
 __asm__ volatile("svc 0xab":"+r"(r0),"+r"(r1)::"memory");while(1){}
#else
 exit(rc);
#endif
}
static void check(int yes){checks++;if(!yes){put("FAIL FRAME_DUMP case=");number(cases);put(" checks=");number(checks);put("\n");stop(1);}}
static int same(const char*a,const char*b){while(*a&&*a==*b){a++;b++;}return *a==*b;}
static long dump_sc6(long nr,long a,long b,long c,long d,long e,long f){
 if(nr==263){check(a==1);clocks++;if(mode==1)return -38;uint32_t *p=(void*)b;p[0]=100+(mode==2&&reads?2:0);p[1]=1234;return 0;}
 if(nr==5){const char *name=(void*)a;
  if(same(name,"/dev/mem")){check(b==0x1000);return mode==3?-13:3;}
  check(same(name,"/tmp/jiritsu/a7yc-frame.bin")&&b==(1|64|128|0x8000)&&c==0600);
  if(mode==4)return -17;created++;return 4;
 }
 if(nr==180){check(a==3&&d==0&&f==0&&e==(long)(physical+reads*SOURCE_STEP)&&c==READ_BYTES);reads++;
  if(mode==5)return c-1;uint8_t *p=(void*)b;for(long i=0;i<c;i++)p[i]=(uint8_t)((e+i)*13u);return c;}
 if(nr==4){check(a==4&&created&&c>0&&c<=4096);writes++;
  if(mode==6)return -5;if(mode==8)return c+1;
  long n=mode==7&&c>1?c/2:c;const uint8_t*p=(void*)b;
  for(long i=0;i<n;i++){unsigned pos=position+(unsigned)i;check(p[i]==(uint8_t)((physical+(pos/READ_BYTES)*SOURCE_STEP+pos%READ_BYTES)*13u));}position+=(unsigned)n;return n;
 }
 if(nr==118){check(a==4&&position==OUTPUT_TOTAL);return mode==9?-5:0;}
 if(nr==6){check((a==3||a==4)&&!(closed&(1u<<a)));closed|=1u<<a;return (mode==10&&a==4)||(mode==11&&a==3)?-5:0;}
 if(nr==10){check(created&&same((void*)a,"/tmp/jiritsu/a7yc-frame.bin"));removed++;return 0;}
 check(0);return -1;
}
#define A7_DMM_DUMP_TEST
#include "dmm_frame_dump.c"
static void run(void){
 for(mode=0;mode<12;mode++){
  cases++;clocks=reads=writes=closed=created=removed=position=0;
  struct a7_dmm_dump_result r;a7_dmm_frame_dump(&r,physical,TOTAL);
  if(mode==0||mode==7)check(!r.status&&r.written==OUTPUT_TOTAL&&r.reads==OUTPUT_TOTAL/READ_BYTES&&position==OUTPUT_TOTAL&&!removed&&closed==24);
  else{
   check(r.status<0);
   if(mode==1)check(!created&&!closed&&!reads);
   else if(mode==3)check(!created&&!closed&&!reads);
   else if(mode==4)check(!created&&closed==8&&!removed);
   else check(created==1&&removed==1&&closed==24);
  }
 }
 static const uint32_t invalid[][2]={{0,1048576},{0x0fffffff,1048576},{0x40000000,1048576},{0xf0200000,1048576},
  {0x3ffff000,1048576},{0x20000000,0},{0x20000000,1048575},{0x20000000,8388609},{0x20000000,0xffffffff}};
 for(unsigned i=0;i<sizeof invalid/sizeof *invalid;i++){
  cases++;clocks=reads=writes=closed=created=removed=0;struct a7_dmm_dump_result r;
  a7_dmm_frame_dump(&r,invalid[i][0],invalid[i][1]);check(r.status==-1&&!clocks&&!reads&&!writes&&!created&&!closed&&!removed);
 }
 put("DMM_FRAME_DUMP_PASSED cases=");number(cases);put(" checks=");number(checks);put("\n");
}
#ifdef DUMP_QEMU
void guest_main(void){run();stop(0);}
#else
int main(void){run();return 0;}
#endif
