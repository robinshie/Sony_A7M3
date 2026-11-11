#include <stdint.h>
extern void *stock_factory(void *,void *);
extern uintptr_t dlopen_slot,dlsym_slot;
static unsigned scenario,stage,ctor_calls,install_calls;
static uint8_t object[0x13c];
static void put(const char *s) {volatile unsigned *u=(volatile unsigned *)0x09000000;while(*s){while(u[6]&32){}u[0]=*s++;}}
static void finish(void) {
 register unsigned r0 __asm__("r0")=0x18,r1 __asm__("r1")=0x20026;
 __asm__ volatile("svc 0x123456":"+r"(r0),"+r"(r1)::"memory");while(1){}
}
static void check(int ok,const char *s){if(!ok){put("FAIL ");put(s);put("\n");finish();}}
static int equal(const char *a,const char *b){while(*a&&*a==*b){a++;b++;}return *a==*b;}
void *mock_alloc(unsigned size){check(size==sizeof object,"original factory allocation size");stage=1;return object;}
void *mock_ctor(void *self,void *manager){
 check(self==object && manager==(void *)0x12345678,"original ctor args preserved");
 check(stage==(scenario==0?4:scenario==1?2:3),"fallback/success constructor order");++ctor_calls;return self;
}
static int install(uintptr_t base,void *manager){
 check(stage==3 && base==0x40000000 && manager==(void *)0x12345678,"module base and manager args");
 ++install_calls;stage=4;return -7; /* Even installation failure must retain stock MENU. */
}
static void *open_module(const char *path,int flags){
 check(stage==1 && equal(path,"/usr/lib/a7fl.so") && flags==2,"dlopen contract");stage=2;
 return scenario==1?0:(void *)0x76543210;
}
static void *find_symbol(void *handle,const char *symbol){
 check(stage==2 && handle==(void *)0x76543210 && equal(symbol,"a7_fl_install"),"dlsym contract");stage=3;
 return scenario==2?0:(void *)install;
}
void guest_main(void){
 dlopen_slot=(uintptr_t)open_module;dlsym_slot=(uintptr_t)find_symbol;
 for(scenario=0;scenario<3;++scenario){
  stage=0;check(stock_factory((void *)0x11111111,(void *)0x12345678)==object,"factory return preserved");
 }
 check(ctor_calls==3 && install_calls==1,"all outcomes tail stock ctor exactly once");
 put("NATIVE_MENU_LOADER_PASSED: original factory, module-call ABI, dlopen/dlsym failures, installer failure preserves MENU\n");finish();
}
