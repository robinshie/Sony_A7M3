#include <stdint.h>
#define A7YC_SAMPLE_TEST
#include "yc_trace_sample.c"
static uint32_t info[850];
static struct {uint32_t before[4];struct A7YCSample samples[12];uint32_t after[4];} output;
static unsigned checks,cases,opens,reads,closes,mode;
static void put(const char*s){volatile uint32_t*u=(void*)0x10009000;while(*s){while(u[6]&32){}u[0]=*s++;}}
static void number(unsigned n){char b[12];unsigned i=0;do{b[i++]=(char)('0'+n%10);n/=10;}while(n);while(i){char s[2]={b[--i],0};put(s);}}
static void stop(void){register unsigned r0 __asm__("r0")=0x18,r1 __asm__("r1")=0x20026;__asm__ volatile("svc 0x123456":"+r"(r0),"+r"(r1)::"memory");while(1){}}
static void check(int ok){checks++;if(!ok){put("FAIL SAMPLE case=");number(cases);put(" checks=");number(checks);put("\n");stop();}}
long test_sc6(long nr,long a,long b,long c,long d,long e,long f){
 if(nr==5){opens++;const char*x=(void*)a,*y="/proc/self/mem";while(*x&&*x==*y){x++;y++;}check(*x==*y&&b==0x80000&&!c&&!d&&!e&&!f);return mode==1?-13:71;}
 if(nr==6){closes++;check(a==71&&!b&&!c&&!d&&!e&&!f);return 0;}
 check(nr==180&&a==71&&c>0&&c<=256&&!d&&!f);unsigned i=reads++;check((uint32_t)e==0x200000+i*4096);
 check((uintptr_t)b==(uintptr_t)output.samples[i].data&&(unsigned)c==(info[3+i*4]<256?info[3+i*4]:256));
 if(mode==2)return -5;if(mode==3)return c+1;
 unsigned n=mode==4?(unsigned)c/2:(unsigned)c;
 for(unsigned j=0;j<n;j++)((unsigned char*)b)[j]=(unsigned char)(i*17+j);return n;
}
void guest_main(void){
 const uint32_t lengths[]={1,15,255,256,257,0x100000};
 for(mode=0;mode<5;mode++)for(unsigned size=0;size<6;size++){
  for(unsigned i=0;i<sizeof output/4;i++)((uint32_t*)&output)[i]=0xdeadbeef;
  for(unsigned i=0;i<850;i++)info[i]=0;
  for(unsigned i=0;i<8;i++){info[2+i*4]=0x200000+i*4096;info[3+i*4]=lengths[(size+i)%6];}
  info[2+9*4]=1; /* nonnull with zero length */
  info[3+10*4]=10; /* null with nonzero length */
  info[2+11*4]=0xfffffff0;info[3+11*4]=32; /* overflow */
  opens=reads=closes=0;a7yc_sample(info,output.samples);
  check(opens==1&&closes==(mode!=1)&&reads==(mode==1?0:8));
  for(unsigned i=0;i<12;i++){
   unsigned n=i<8?(info[3+i*4]<256?info[3+i*4]:256):0;
   int rc=i==8?0:i>8?-22:mode==1?-13:mode==2?-5:mode==3?-75:mode==4?(int)n/2:(int)n;
   check(output.samples[i].result==rc&&output.samples[i].count==(rc>0?(unsigned)rc:0));
   for(unsigned j=0;j<256;j++)check(output.samples[i].data[j]==(rc>0&&j<(unsigned)rc?(unsigned char)(i*17+j):((unsigned char[]){0xef,0xbe,0xad,0xde})[j%4]));
  }
  for(unsigned i=0;i<4;i++)check(output.before[i]==0xdeadbeef&&output.after[i]==0xdeadbeef);cases++;
 }
 put("YC_TRACE_SAMPLE_PASSED cases=");number(cases);put(" checks=");number(checks);put("\n");stop();
}
