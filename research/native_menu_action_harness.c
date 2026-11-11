#include "native_menu.h"
extern void original_action(void *);
static unsigned char view[0x248];
static uintptr_t manager[2], table[28];
static a7_menu_model model;
static int selected=0x7009, actions, scalar, originals, fallback, model_flag, reject;
static void put(const char *s){volatile unsigned *u=(volatile unsigned *)0x09000000;while(*s){while(u[6]&32){}u[0]=*s++;}}
static void finish(void){register unsigned r0 __asm__("r0")=0x18;register unsigned r1 __asm__("r1")=0x20026;__asm__ volatile("svc 0x123456":"+r"(r0),"+r"(r1)::"memory");while(1){}}
static void check(int ok,const char*s){if(!ok){put("FAIL ");put(s);put("\n");finish();}}
void *mock_select(void*p){check(p==view,"view argument");return selected==-2?0:&selected;}
int mock_process(void*p,void*n){check(p==view&&n==&selected,"selected node");return selected;}
void mock_flag(int b){check(b==1,"stock model flag");++model_flag;}
static int mock_get(void*p,int id,int*v){(void)p;(void)id;*v=0;return 1;}
static int mock_set(void*p,int id,int v){(void)p;(void)id;(void)v;++scalar;return 1;}
static int stock_exec(void*p,int id){check(p==manager,"stock manager");++originals;return id==0x55;}
static int stock_condition(void*p,int id,int v){check(p==manager&&v==7,"condition ABI");(void)id;++fallback;return 1;}
static int custom_read(void*p,int id,int*v){(void)p;(void)id;*v=0;return 1;}
static int custom_write(void*p,int id,int v){(void)p;(void)id;(void)v;++scalar;return 1;}
static int custom_action(void*p,int id){check(p==view&&id==0x7009,"explicit action ABI");++actions;return !reject;}
static void mode(int m){*(unsigned*)(view+0x130)=m;}
void guest_main(void){
 table[5]=(uintptr_t)mock_get;table[19]=(uintptr_t)mock_set;
 table[23]=(uintptr_t)stock_exec;table[24]=(uintptr_t)stock_condition;
 manager[0]=(uintptr_t)(table+2);*(uintptr_t*)(view+0x150)=(uintptr_t)manager;*(int*)(view+0x158)=7;
 check(a7_menu_bind_model(&model,manager,table+2,custom_read,custom_write,view)==1,"bind");
 check(a7_menu_bind_action(&model,0x28,custom_action)==-1,"refuse stock action ID");
 check(a7_menu_bind_action(&model,0x7008,custom_action)==-1,"refuse scalar ID collision");
 check(a7_menu_bind_action(&model,0x7009,custom_action)==1,"bind explicit action");
 mode(1);original_action(view);check(actions==1&&originals==0&&fallback==0&&scalar==0,"direct menu explicit action only");
 mode(3);original_action(view);check(actions==2&&scalar==0,"categorized menu action");
 mode(2);original_action(view);mode(0);original_action(view);check(actions==2,"other modes never execute");
 mode(1);selected=-1;original_action(view);selected=-2;original_action(view);check(actions==2,"missing selection never executes");
 selected=0x55;original_action(view);check(originals==1&&fallback==0&&actions==2,"stock action preserved");
 selected=0x56;original_action(view);check(originals==2&&fallback==1,"stock conditioned fallback preserved");
 selected=0x7009;reject=1;original_action(view);check(actions==3&&fallback==2,"failure propagated to native fallback");
 check(model_flag==5,"stock entry bookkeeping remains");
 check(a7_menu_unbind_model(&model)==1,"unbind");
 put("NATIVE_MENU_ACTION_PASSED: original native action dispatch, custom/stock isolation, failure, modes and missing selection; physical key mapping not asserted\n");finish();
}
