#include <stdint.h>
extern int a7yc_hook(void *,void *);
extern uintptr_t a7yc_state;
static struct {uint32_t magic,version,original,lock,armed,count,dropped,max;
    uint32_t calls,failures,last_error,area,mode,reserved[3];
    uint32_t records[128][20],guard[4];} state;
static uint32_t object[20],parameter[8],calls,cases,checks,large;
static void put(const char *s){volatile uint32_t *u=(void*)0x10009000;while(*s){while(u[6]&32){}u[0]=*s++;}}
static void number(unsigned n){char b[12];unsigned i=0;do{b[i++]=(char)('0'+n%10);n/=10;}while(n);while(i){char s[2]={b[--i],0};put(s);}}
static void stop(void){register unsigned r0 __asm__("r0")=0x18,r1 __asm__("r1")=0x20026;__asm__ volatile("svc 0xab":"+r"(r0),"+r"(r1)::"memory");while(1){}}
static void check(int ok){checks++;if(!ok){put("FAIL YC_TRACE case=");number(cases);put(" checks=");number(checks);put("\n");stop();}}
static int original(void *input,uint32_t *out){calls++;if(input)return (int)(intptr_t)input;
 for(unsigned i=0;i<20;i++)object[i]=0x12340000+cases*32+i;
 object[13]=large?(6000u|(4000u<<16)):(1920u|(1080u<<16));
 check(out==(state.mode?parameter:object));return 0;}
void guest_main(void){
 a7yc_state=(uintptr_t)&state;parameter[0]=(uintptr_t)object;
 for(unsigned count=0;count<=128;count++)for(unsigned armed=0;armed<2;armed++)
 for(unsigned busy=0;busy<2;busy++)for(int result=-1;result<=0;result++)for(large=0;large<2;large++)for(unsigned mode=0;mode<2;mode++){
  for(unsigned i=0;i<sizeof state/4;i++)((uint32_t*)&state)[i]=0xdeadbeef;
  state.original=(uintptr_t)original;state.lock=busy;state.armed=armed;state.count=count;state.dropped=0;state.max=128;
  state.calls=state.failures=state.area=state.last_error=0;state.mode=mode;calls=0;
  int observed=armed&&!busy,success=!result&&observed,record=success&&count<127,largest=success&&!mode;
  void *argument=result?(void*)1:mode?(void*)parameter:(void*)object;
  int rc=a7yc_hook((void*)(intptr_t)result,argument);
  check(rc==result&&calls==1&&state.lock==busy&&state.count==count+(unsigned)record);
  check(state.calls==(unsigned)observed&&state.failures==(unsigned)(observed&&result));
  check(state.last_error==(observed&&result?(uint32_t)result:0));
  check(state.dropped==(unsigned)(success&&count>=127));
  check(state.area==(largest?(large?24000000u:2073600u):0));
  for(unsigned i=0;i<128;i++)for(unsigned j=0;j<20;j++){
   if((record&&i==count)||(largest&&i==127)){
    if(j==0)check(state.records[i][j]!=0);
    else if(j==1||j==3)check(state.records[i][j]==0);
    else if(j==2)check(state.records[i][j]==mode);
    else if(!mode&&j==19)check(state.records[i][j]==0);
    else check(state.records[i][j]==object[j-4+(mode?0:5)]);
   }else check(state.records[i][j]==0xdeadbeef);
  }
  for(unsigned i=0;i<4;i++)check(state.guard[i]==0xdeadbeef);
  cases++;
 }
 put("YC_TRACE_HOOK_PASSED cases=");number(cases);put(" checks=");number(checks);put("\n");
 put("METADATA_ONLY; CAMERA_CALLSITE_NOT_YET_OBSERVED\n");stop();
}
