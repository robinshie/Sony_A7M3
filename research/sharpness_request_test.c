#include "a7-fl-sharpness-native.h"
static unsigned values[2][5],allocs,fail_at,adds,requests,deletes;
static int expected;
static void put(const char *s){volatile unsigned *u=(void *)0x10009000;while(*s){while(u[6]&32){}u[0]=*s++;}}
static void stop(void){register unsigned r0 __asm__("r0")=0x18,r1 __asm__("r1")=0x20026;__asm__ volatile("svc 0xab":"+r"(r0),"+r"(r1)::"memory");while(1){}}
static void check(int v){if(!v){put("FAIL native sharpness request\n");stop();}}
void *allocate(unsigned n){check(n==20&&allocs<2);allocs++;return allocs==fail_at?0:values[allocs-1];}
void *parameter(unsigned *p,int v){check(p==values[0]&&v==expected);p[4]=(unsigned)v;return p;}
void *list(unsigned *p,int v){check(p==values[1]&&!v);return p;}
void add(void *p,unsigned id,void *value){check(p==values[1]&&id==392&&value==values[0]);adds++;}
void release(void *p){check(p==values[0]);deletes++;}
void request(const char *name,unsigned id,void *p){static const char text[]="@M00B";for(unsigned i=0;i<sizeof text;i++)check(name[i]==text[i]);check(id==38&&p==values[1]);requests++;}
void guest_main(void){
 for(int v=-4;v<=4;v++)for(unsigned fail=0;fail<=2;fail++){
  allocs=adds=requests=deletes=0;fail_at=fail;expected=v;
  int actual=a7_fl_sharpness_request(0x01000000,v);
  if(v<-3||v>3)check(actual==-1&&!allocs&&!adds&&!requests&&!deletes);
  else if(fail)check(actual==-2&&allocs==fail&&!adds&&!requests&&deletes==(fail==2));
  else check(actual==1&&allocs==2&&adds==1&&requests==1&&!deletes);
 }
 check(a7_fl_sharpness_request(0,0)==-1&&a7_fl_sharpness_request(0xffffffff,0)==-1);
 put("SHARPNESS_REQUEST_PASSED 27 combinations; single model parameter and allocation failure; call issued is not completion\n");stop();
}
