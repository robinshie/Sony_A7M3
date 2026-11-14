#include <stdint.h>
extern int a7yc_hook(void *,void *,unsigned,unsigned);
extern int a7yc_five(void *,void *,unsigned,unsigned,unsigned) __asm__("a7yc_hook");
extern uintptr_t a7yc_state;
static struct {uint32_t magic,version,original,lock,armed,count,dropped,max;
    uint32_t calls,failures,last_error,area,mode,reserved[3];
    uint32_t records[128][20],guard[4];} state;
static uint32_t object[850],parameter[8],calls,cases,checks,large,sample_calls;
static unsigned query_calls;
static void put(const char *s){volatile uint32_t *u=(void*)0x10009000;while(*s){while(u[6]&32){}u[0]=*s++;}}
static void number(unsigned n){char b[12];unsigned i=0;do{b[i++]=(char)('0'+n%10);n/=10;}while(n);while(i){char s[2]={b[--i],0};put(s);}}
static void stop(void){register unsigned r0 __asm__("r0")=0x18,r1 __asm__("r1")=0x20026;__asm__ volatile("svc 0xab":"+r"(r0),"+r"(r1)::"memory");while(1){}}
static void check(int ok){checks++;if(!ok){put("FAIL YC_TRACE case=");number(cases);put(" checks=");number(checks);put("\n");stop();}}
static int original(void *input,uint32_t *out,unsigned second,unsigned third){calls++;
 check(third==0x50607080);check(state.mode>=3?(!second||second==(input?1:(uintptr_t)object)):second==0x10203040);
 if(input)return (int)(intptr_t)input;
 if(!out){check(state.mode==2);return 0;}
 if(state.mode>=3&&!second)return 0;
 for(unsigned i=0;i<850;i++)object[i]=0x12340000+cases*32+i;
 object[13]=large?(6000u|(4000u<<16)):(1920u|(1080u<<16));
 check(out==(state.mode==1||state.mode>=3?parameter:object));return 0;}
void a7yc_sample(const uint32_t*info,uint32_t*out){sample_calls++;check(state.mode==4);for(unsigned i=0;i<850;i++)check(info[i]==object[i]);for(unsigned i=0;i<792;i++)out[i]=0x12345600+i;}
static int mapped(void *self,void *r1,unsigned r2,unsigned r3){
 check(self==object&&r1==(void*)0x10203040&&r2==0x50607080&&r3==0x90a0b0c0);calls++;
 return (int)object[2];
}
static int opened(void *self,void *out,unsigned handle,unsigned flags,unsigned timeout){
 check(out==object&&handle==0x1234&&flags==0x5678&&timeout==0xabcdef01);calls++;
 if(!self){for(unsigned i=0;i<6;i++)object[i]=0xaabb0000+i;object[0]=5;object[5]=cases+2048;}
 return (int)(intptr_t)self;
}
void a7yc_dmm_observe(void *trace,const uint8_t *metadata){
 check(trace==&state&&metadata==(void*)(object+5)&&state.mode>=7&&state.mode<=9&&state.lock==1);query_calls++;
}
static int queried(void *input,void *out,unsigned a,unsigned b){
 calls++;check(out==object&&a==0x10203040&&b==0x50607080);
 for(unsigned i=0;i<20;i++)object[i]=0x12340000+i;
 return (int)(uintptr_t)input;
}
void guest_main(void){
 a7yc_state=(uintptr_t)&state;parameter[0]=(uintptr_t)object;
 for(unsigned count=0;count<=128;count++)for(unsigned armed=0;armed<2;armed++)
 for(unsigned busy=0;busy<2;busy++)for(int result=-1;result<=0;result++)for(large=0;large<2;large++)for(unsigned mode=0;mode<5;mode++){
  for(unsigned i=0;i<sizeof state/4;i++)((uint32_t*)&state)[i]=0xdeadbeef;
  state.original=(uintptr_t)original;state.lock=busy;state.armed=armed;state.count=count;state.dropped=0;state.max=128;
  state.calls=state.failures=state.area=state.last_error=0;state.mode=mode;calls=sample_calls=0;
  unsigned limit=mode==4?1:mode==3?2:127;
  int observed=armed&&!busy,success=!result&&observed,record=success&&count<limit,largest=success&&!mode;
  void *argument=result?(void*)1:mode==1||mode>=3?(void*)parameter:(void*)object;
  unsigned second=mode>=3?(result?1:(uintptr_t)object):0x10203040;
  int rc=a7yc_hook((void*)(intptr_t)result,argument,second,0x50607080);
  check(rc==result&&calls==1&&state.lock==busy&&state.count==count+(unsigned)record);
  check(state.calls==(unsigned)observed&&state.failures==(unsigned)(observed&&result));
  check(state.last_error==(observed&&result?(uint32_t)result:0));
  check(state.dropped==(unsigned)(success&&count>=limit));
  check(state.area==(largest?(large?24000000u:2073600u):0));
  check(sample_calls==(unsigned)(record&&mode==4));
  for(unsigned k=0;k<2560;k++){
   unsigned stride=mode==4?2048:mode==3?1024:20;
   unsigned i=k/stride,j=k%stride,value=((uint32_t*)state.records)[k];
   if((record&&i==count&&j<(mode==4?1646:mode==3?854:20))||(largest&&i==127)){
    if(j==0)check(value!=0);
    else if(j==1||j==3)check(value==0);
    else if(j==2)check(value==mode);
    else if(!mode&&j==19)check(value==0);
    else if(mode==4&&j>=854)check(value==0x12345600+j-854);
    else check(value==object[j-4+(mode?0:5)]);
   }else check(value==0xdeadbeef);
  }
  for(unsigned i=0;i<4;i++)check(state.guard[i]==0xdeadbeef);
  cases++;
 }
 for(unsigned mode=2;mode<5;mode++)for(unsigned armed=0;armed<2;armed++)for(int rc=-1;rc<=0;rc++){
  for(unsigned i=0;i<sizeof state/4;i++)((uint32_t*)&state)[i]=0;
  state.original=(uintptr_t)original;state.mode=mode;state.armed=armed;state.max=128;calls=sample_calls=0;
  check(a7yc_hook((void*)(intptr_t)rc,mode>=3?(void*)parameter:0,mode>=3?0:0x10203040,0x50607080)==rc);
  check(calls==1&&state.calls==armed&&state.failures==(unsigned)(armed&&rc));
  check(state.count==0&&state.area==0&&state.lock==0&&sample_calls==0);
  for(unsigned i=0;i<128;i++)for(unsigned j=0;j<20;j++)check(state.records[i][j]==0);
  for(unsigned i=0;i<4;i++)check(state.guard[i]==0);
  cases++;
 }
 for(unsigned count=0;count<=128;count++)for(unsigned armed=0;armed<2;armed++)for(unsigned busy=0;busy<2;busy++)for(unsigned value=0;value<4;value++){
  for(unsigned i=0;i<sizeof state/4;i++)((uint32_t*)&state)[i]=0xdeadbeef;
  static const uint32_t outputs[4]={0,1,0x12345678,0xfedcba98};
  state.original=(uintptr_t)mapped;state.lock=busy;state.armed=armed;state.count=count;state.dropped=0;state.max=128;
  state.calls=state.failures=state.area=state.last_error=0;state.mode=5;calls=sample_calls=0;
  for(unsigned i=0;i<8;i++)object[i]=0xaabbcc00+i;
  object[2]=outputs[value];
  int observed=armed&&!busy,success=observed&&value,record=success&&count<127;
  int rc=a7yc_hook(object,(void*)0x10203040,0x50607080,0x90a0b0c0);
  check((uint32_t)rc==outputs[value]&&calls==1&&state.lock==busy&&state.count==count+(unsigned)record);
  check(state.calls==(unsigned)observed&&state.failures==(unsigned)(observed&&!value));
  check(!state.last_error&&!state.area&&!sample_calls&&state.dropped==(unsigned)(success&&count>=127));
  for(unsigned i=0;i<128;i++)for(unsigned j=0;j<20;j++){
   uint32_t v=state.records[i][j];
   if(record&&i==count){if(!j)check(v!=0);else if(j==1)check(v==outputs[value]);else if(j==2)check(v==5);
    else if(j==3||j>=12)check(!v);else check(v==object[j-4]);}
   else check(v==0xdeadbeef);
  }
  for(unsigned i=0;i<4;i++)check(state.guard[i]==0xdeadbeef);
  cases++;
 }
 for(unsigned count=0;count<=128;count++)for(unsigned armed=0;armed<2;armed++)for(unsigned busy=0;busy<2;busy++)for(unsigned error=0;error<2;error++){
  for(unsigned i=0;i<sizeof state/4;i++)((uint32_t*)&state)[i]=0xdeadbeef;
  state.original=(uintptr_t)opened;state.lock=busy;state.armed=armed;state.count=count;state.dropped=0;state.max=128;
  state.calls=state.failures=state.area=state.last_error=0;state.mode=6;calls=sample_calls=0;
  int observed=armed&&!busy,success=observed&&!error,record=success&&count<127;
  int rc=a7yc_five((void*)error,object,0x1234,0x5678,0xabcdef01);
  check(rc==(int)error&&calls==1&&state.lock==busy&&state.count==count+(unsigned)record);
  check(state.calls==(unsigned)observed&&state.failures==(unsigned)(observed&&error));
  check(state.last_error==(unsigned)(observed&&error)&&state.area==(success?object[5]:0)&&!sample_calls&&state.dropped==(unsigned)(success&&count>=127));
  for(unsigned i=0;i<128;i++)for(unsigned j=0;j<20;j++){
   uint32_t v=state.records[i][j];
   if((record&&i==count)||(success&&i==127)){if(!j)check(v!=0);else if(j==1)check(!v);else if(j==2)check(v==6);
    else if(j==3)check(v==0x1234);else if(j>=10)check(!v);else check(v==object[j-4]);}
   else check(v==0xdeadbeef);
  }
  for(unsigned i=0;i<4;i++)check(state.guard[i]==0xdeadbeef);
  cases++;
 }
 for(unsigned mode=7;mode<=9;mode++)for(unsigned armed=0;armed<2;armed++)for(unsigned busy=0;busy<2;busy++)for(unsigned count=0;count<2;count++)for(unsigned error=0;error<2;error++){
  for(unsigned i=0;i<sizeof state/4;i++)((uint32_t*)&state)[i]=0xdeadbeef;
  state.original=(uintptr_t)queried;state.lock=busy;state.armed=armed;state.count=count;state.dropped=0;state.max=128;
  state.calls=state.failures=state.area=state.last_error=0;state.mode=mode;calls=query_calls=0;
  unsigned observes=armed&&!busy,success=observes&&!error,record=success&&!count;
  check(a7yc_hook((void*)error,object,0x10203040,0x50607080)==(int)error);
  check(calls==1&&query_calls==success&&state.lock==busy&&state.count==count+record&&!state.area);
  check(state.calls==observes&&state.failures==(observes&&error)&&state.dropped==(success&&count));
  for(unsigned i=0;i<2560;i++){
   unsigned v=((uint32_t*)state.records)[i];
   if(record&&i<20){if(!i)check(v!=0);else if(i==1||i==3||i==19)check(!v);else if(i==2)check(v==mode);else check(v==object[i+1]);}
   else check(v==0xdeadbeef);
  }
  for(unsigned i=0;i<4;i++)check(state.guard[i]==0xdeadbeef);
  cases++;
 }
 put("YC_TRACE_HOOK_PASSED cases=");number(cases);put(" checks=");number(checks);put("\n");
 put("METADATA_ONLY; CAMERA_CALLSITE_NOT_YET_OBSERVED\n");stop();
}
