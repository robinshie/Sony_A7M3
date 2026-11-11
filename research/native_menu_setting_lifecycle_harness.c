#include <stdint.h>
extern void *stock_factory(void *,void *);
extern void stock_initialize(void *,void *);
extern uintptr_t dlopen_slot,dlsym_slot;
static unsigned scenario,stage,ctor_calls,init_calls,deep_calls,install_calls,widget_calls,root_count;
static uint8_t object[0x248],aux[16];
static uintptr_t root_vt[4],root[10],children[6];
unsigned mock_root_count=6;
static void put(const char*s){volatile unsigned*u=(volatile unsigned*)0x09000000;while(*s){while(u[6]&32){}u[0]=*s++;}}
static void finish(void){register unsigned r0 __asm__("r0")=0x18,r1 __asm__("r1")=0x20026;__asm__ volatile("svc 0x123456":"+r"(r0),"+r"(r1)::"memory");while(1){}}
static void check(int ok,const char*s){if(!ok){put("FAIL ");put(s);put("\n");finish();}}
static int equal(const char*a,const char*b){while(*a&&*a==*b){a++;b++;}return *a==*b;}
void *mock_alloc(unsigned n){if(n==sizeof object){check(stage==0,"factory first alloc");stage=1;return object;}check(n==16&&stage==6,"UserInitialize aux alloc");return aux;}
void *mock_base(void*self,void*vm){check(self==object&&vm==(void*)0x12345678,"original ctor r0/r1");check(stage==(scenario==1?2:scenario==2?3:4),"module before base ctor");*(uintptr_t*)(object+0x24)=(uintptr_t)vm;++ctor_calls;stage=5;return self;}
void *mock_widget(void*self){unsigned off[3]={0x1dc,0x1f8,0x220};check(widget_calls<3&&self==object+off[widget_calls],"original widget ctor order");widget_calls++;return self;}
void mock_ctor_final(void*self,unsigned n){check(self==object&&!n&&widget_calls==3,"original final ctor call");check(*(uintptr_t*)object==0x4087b600,"original SettingMenu vtable");check(*(uintptr_t*)(object+0x24)==0x12345678,"original VM owner");}
void *mock_zero(void*at,unsigned value,unsigned bytes){check(at==object+0x125&&value==0&&bytes==9&&stage==5,"original UserInitialize clear");uint8_t*p=at;while(bytes--)*p++=0;stage=6;return at;}
int mock_info(unsigned id,void*ptr){(void)id;check(ptr==object+0x193&&stage==6,"original model query");return 0;}
void *mock_aux_ctor(void*self){check(self==aux,"original aux ctor");return self;}
void mock_attach(void*self,unsigned event,void*fn){(void)event;(void)fn;check(self==object&&stage==6,"original attach callback");stage=7;}
void mock_schedule(void*self,unsigned event){check(self==object&&event==0x209&&stage==7,"original schedule call");stage=8;}
void *mock_select_root(void*self){check(self==object&&stage==8,"original select root before init");stage=9;return root;}
void *mock_select_children(void*self){check(self==root&&stage==9,"original child root selection");return children;}
static int deep_init(void*self,void*items,unsigned count){check(self==root&&items==children&&count==6,"original deep init argument ABI");check(stage==9&&root_count==(scenario==0?4u:3u),"attachment exists before original graph deep init");stage=10;++deep_calls;return 1;}
void mock_init_checked(void*self){check(self==object&&stage==10,"deep init reached before UI continuation");check(*(uintptr_t*)(object+0x184)==(uintptr_t)root,"native selected root stored");check(*(uintptr_t*)(object+0x244)==(uintptr_t)aux,"native aux stored");check(*(unsigned*)(object+0x134)==0xffffffffu&&*(unsigned*)(object+0x178)==0,"native init state stores");++init_calls;}
static int install(uintptr_t base,void*vm,unsigned mode){uintptr_t caller=(uintptr_t)__builtin_return_address(0);check(stage==3&&base==0x40000000&&vm==(void*)0x12345678&&mode==0,"module handoff ABI");check((caller&~1u)==0x405b9b30,"unchanged module caller PC");++install_calls;stage=4;if(scenario==0)root_count=4;return scenario==3?-7:0;}
static void*open_module(const char*p,int flags){check(stage==1&&equal(p,"/usr/lib/a7fl.so")&&flags==2,"dlopen contract");stage=2;return scenario==1?0:(void*)0x76543210;}
static void*find_symbol(void*h,const char*s){check(stage==2&&h==(void*)0x76543210&&equal(s,"a7_fl_install"),"dlsym contract");stage=3;return scenario==2?0:(void*)install;}
void guest_main(void){dlopen_slot=(uintptr_t)open_module;dlsym_slot=(uintptr_t)find_symbol;root[0]=(uintptr_t)root_vt;root_vt[2]=(uintptr_t)deep_init;
 for(scenario=0;scenario<4;scenario++){root_count=3;
  for(unsigned cycle=0;cycle<2;cycle++){stage=widget_calls=0;
   check(stock_factory((void*)0x11111111,(void*)0x12345678)==object,"original factory return");
   stock_initialize(object,(void*)0x87654320);check(stage==10,"original init reached continuation");
  }
 }
 check(ctor_calls==8&&init_calls==8&&deep_calls==8&&install_calls==4,"all lifecycle paths");
 put("NATIVE_SETTING_LIFECYCLE_PASSED: original factory + complete original SettingMenu constructor + original UserInitialize prefix through selected-root deep init; 4 loader outcomes x2 constructions; unchanged caller PC and original args; external services/node callbacks modeled\n");finish();}
