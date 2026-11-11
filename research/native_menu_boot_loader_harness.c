#include <stdint.h>
#include "entry_bytes.h"
#include "entry_table.h"
extern void *stock_factory(void *,void *);
extern void stock_entry(void *,void *);
extern uintptr_t dlopen_slot,dlsym_slot;
static unsigned scenario,stage,ctor_calls,install_calls,boot,baseline,model_state,state_calls;
static unsigned trace[32],trace_count,expected[32],expected_count;
static uint8_t object[0x13c],entry_object[0x890];
static uintptr_t vt[16];
static void put(const char*s){volatile unsigned*u=(volatile unsigned*)0x09000000;while(*s){while(u[6]&32){}u[0]=*s++;}}
static void finish(void){register unsigned r0 __asm__("r0")=0x18,r1 __asm__("r1")=0x20026;__asm__ volatile("svc 0x123456":"+r"(r0),"+r"(r1)::"memory");while(1){}}
static void check(int ok,const char*s){if(!ok){put("FAIL ");put(s);put("\n");finish();}}
static int equal(const char*a,const char*b){while(*a&&*a==*b){a++;b++;}return *a==*b;}
static int order(void){return stage==(scenario==0?4:scenario==1?2:3);}
void *mock_alloc(unsigned n){check(n==sizeof object,"MENU allocation");stage=1;return object;}
void *mock_ctor(void*self,void*manager){check(self==object&&manager==(void*)0x12345678,"MENU original args");check(order(),"MENU original constructor order");++ctor_calls;return self;}
unsigned mock_state(void*self,void*arg1){check(self==entry_object,"boot original r0 preserved");if(!state_calls){check(arg1==(void*)0x87654320,"boot original r1 preserved");check(baseline||order(),"module before original UserEntry");}++state_calls;return model_state;}
void mock_trigger(void*self,uintptr_t function){check(self==entry_object,"trigger this");check(function==expected_trigger[model_state],"original trigger table");check(trace_count<32,"trace bounds");trace[trace_count++]=function;}
static void action(void*self,unsigned id){check(self==entry_object,"original action this");check(trace_count<32,"trace bounds");trace[trace_count++]=id;}
static int install(uintptr_t base,void*manager,unsigned mode){check(stage==3&&base==0x40000000&&mode==boot,"module base/mode");check(manager==(boot?(void*)0x87654320:(void*)0x12345678),"second arg untouched");++install_calls;stage=4;return -7;}
static void*open_module(const char*p,int flags){check(stage==1&&equal(p,"/usr/lib/a7fl.so")&&flags==2,"dlopen contract");stage=2;return scenario==1?0:(void*)0x76543210;}
static void*find_symbol(void*h,const char*s){check(stage==2&&h==(void*)0x76543210&&equal(s,"a7_fl_install"),"dlsym contract");stage=3;return scenario==2?0:(void*)install;}
static void set_prologue(const unsigned char*p){volatile unsigned char*at=(void*)0x40188aec;for(unsigned i=0;i<4;i++)at[i]=p[i];__asm__ volatile("dsb\nisb":::"memory");}
void guest_main(void){dlopen_slot=(uintptr_t)open_module;dlsym_slot=(uintptr_t)find_symbol;
 for(scenario=0;scenario<3;scenario++){stage=0;check(stock_factory((void*)0x11111111,(void*)0x12345678)==object,"factory return");}
 check(ctor_calls==3&&install_calls==1,"MENU all fail paths retain original");
 boot=1;*(uintptr_t*)entry_object=(uintptr_t)vt;vt[0x14/4]=(uintptr_t)action;
 for(model_state=0;model_state<10;model_state++){
  baseline=1;set_prologue(prologue);state_calls=trace_count=0;stock_entry(entry_object,(void*)0x87654320);check(state_calls==2,"original state queries");expected_count=trace_count;for(unsigned i=0;i<trace_count;i++)expected[i]=trace[i];
  baseline=0;set_prologue(branch);
  for(scenario=0;scenario<3;scenario++){
   state_calls=trace_count=0;stage=1;stock_entry(entry_object,(void*)0x87654320);
   check(state_calls==2&&trace_count==expected_count,"original UserEntry action count");for(unsigned i=0;i<trace_count;i++)check(trace[i]==expected[i],"original UserEntry entire sequence preserved");
  }
 }
 check(install_calls==11&&ctor_calls==3,"distinct boot/menu entry dispatch");
 put("NATIVE_MENU_BOOT_LOADER_PASSED: MENU success/failure, all 10 original still UserEntry sequences, original r0/r1/LR return and prologue preserved, module before entry\n");finish();}
