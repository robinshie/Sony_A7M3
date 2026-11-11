#include <stdint.h>
extern int a7yc_hook(void *,void *);
extern uintptr_t a7yc_state;
static struct {uint32_t magic,version,original,lock,armed,count,dropped,max;
    uint32_t records[128][16],guard[4];} state;
static uint32_t object[20],calls,cases,checks,large;
static void put(const char *s){volatile uint32_t *u=(void*)0x10009000;while(*s){while(u[6]&32){}u[0]=*s++;}}
static void number(unsigned n){char b[12];unsigned i=0;do{b[i++]=(char)('0'+n%10);n/=10;}while(n);while(i){char s[2]={b[--i],0};put(s);}}
static void stop(void){register unsigned r0 __asm__("r0")=0x18,r1 __asm__("r1")=0x20026;__asm__ volatile("svc 0xab":"+r"(r0),"+r"(r1)::"memory");while(1){}}
static void check(int ok){checks++;if(!ok){put("FAIL YC_TRACE case=");number(cases);put("\n");stop();}}
static int original(void *input,uint32_t *out){calls++;for(unsigned i=0;i<20;i++)out[i]=0x12340000+cases*32+i;out[13]=large?(6000u|(4000u<<16)):(1920u|(1080u<<16));return (int)(intptr_t)input;}
void guest_main(void){
 a7yc_state=(uintptr_t)&state;
 for(unsigned count=0;count<=129;count++)for(unsigned armed=0;armed<2;armed++)
 for(unsigned busy=0;busy<2;busy++)for(int result=-1;result<=0;result++)for(large=0;large<2;large++){
  for(unsigned i=0;i<sizeof state/4;i++)((uint32_t*)&state)[i]=0xdeadbeef;
  state.original=(uintptr_t)original;state.lock=busy;state.armed=armed;state.count=count;state.dropped=0;state.max=128;calls=0;
  int rc=a7yc_hook((void*)(intptr_t)result,object);
  int record=!result&&armed&&!busy&&large&&count<128;
  check(rc==result&&calls==1&&state.lock==busy&&state.count==count+(unsigned)record);
  check(state.dropped==(unsigned)(!result&&armed&&!busy&&large&&count>=128));
  for(unsigned i=0;i<128;i++)for(unsigned j=0;j<16;j++){
   if(record&&i==count)check(j?state.records[i][j]==object[j+4]:state.records[i][j]!=0);
   else check(state.records[i][j]==0xdeadbeef);
  }
  for(unsigned i=0;i<4;i++)check(state.guard[i]==0xdeadbeef);
  cases++;
 }
 put("YC_TRACE_HOOK_PASSED cases=");number(cases);put(" checks=");number(checks);put("\n");
 put("METADATA_ONLY; CAMERA_CALLSITE_NOT_YET_OBSERVED\n");stop();
}
