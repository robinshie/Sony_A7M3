#include "native_adjust.h"
#include "native_menu.h"
static NativeAdjustTree tree;
static unsigned char view[0x248];
static uintptr_t manager[2],table[28];
static a7_menu_model model;
static unsigned actions,flags,fallback,scalar,checks;
static int reject;
static void put(const char*s){volatile unsigned*u=(volatile unsigned*)0x10009000;while(*s){while(u[6]&32){}u[0]=*s++;}}
static void finish(void){register unsigned r0 __asm__("r0")=0x18,r1 __asm__("r1")=0x20026;__asm__ volatile("svc 0xab":"+r"(r0),"+r"(r1)::"memory");while(1){}}
static void check(int ok,const char*s){++checks;if(!ok){put("FAIL ");put(s);put("\n");finish();}}
void unexpected(void){check(0,"unexpected native dependency");}
void*allocate(unsigned n){(void)n;unexpected();return 0;}
void release(void*p){(void)p;unexpected();}
void model_flag(int value){check(value==1,"original model flag ABI");++flags;}
static int get(void*p,int id,int*v){(void)p;(void)id;*v=0;return 1;}
static int set(void*p,int id,int v){(void)p;(void)id;(void)v;++scalar;return 1;}
static int exec(void*p,int id){check(p==manager&&id==0x7009,"stock action should not run");unexpected();return 0;}
static int condition(void*p,int id,int v){check(p==manager&&id==0x7009&&v==7,"action failure fallback ABI");++fallback;return 1;}
static int save(void*p,int id){check(p==&tree&&id==0x7009,"explicit Save callback");++actions;return !reject;}
typedef int (*Select)(NativeAdjustNode*,int);
typedef NativeAdjustNode*(*Selected)(void*);
typedef void (*Action)(void*);
static void select_node(NativeAdjustNode*n,int index){check(((Select)0x682e59)(n,index)==1,"select native row");}
static void action(void){((Action)0x217c7d)(view);}
void guest_main(void){
 NativeAdjustSpec specs[8];for(unsigned i=0;i<8;i++)specs[i]=(NativeAdjustSpec){0x204fda0+i,0,-9,9,0};
 check(native_adjust_build(&tree,0,0x204fd9e,0,0x204fd9f,specs,0x1f),"build corrected native graph");
 check(native_adjust_add_save(&tree,0x204eaab),"Save row appended");
 table[5]=(uintptr_t)get;table[19]=(uintptr_t)set;table[23]=(uintptr_t)exec;table[24]=(uintptr_t)condition;manager[0]=(uintptr_t)(table+2);
 check(a7_menu_bind_model(&model,manager,table+2,get,set,&tree)==1,"bind real manager adapter");
 check(a7_menu_bind_action(&model,0x7009,save)==1,"bind Save action");
 *(uintptr_t*)(view+0x150)=(uintptr_t)manager;*(int*)(view+0x158)=7;*(int*)(view+0x130)=3;*(uintptr_t*)(view+0x188)=(uintptr_t)&tree.root;
 select_node(&tree.root,2);select_node(&tree.pages[1],4);
 check(((Selected)0x217145)(view)==&tree.save,"original submenu accessor reaches actual Save row");
 check(((int(*)(void*,void*))0x216a19)(view,&tree.save)==0x7009,"original selected-node property ID");
 action();check(actions==1&&flags==1&&!fallback&&!scalar,"real native tree dispatches explicit Save");
 reject=1;action();check(actions==2&&fallback==1&&!scalar,"backend failure reaches stock conditioned fallback");reject=0;
 /* Negative control: the deployed former graph omitted Page nodes. */
 NativeAdjustNode flat=tree.root;flat.children=tree.field_ptrs;flat.count=10;flat.selected_index=10;flat.selectable_index=10;
 *(uintptr_t*)(view+0x188)=(uintptr_t)&flat;
 check(((Selected)0x217145)(view)==0,"old flat root descends past Save to null");action();check(actions==2&&flags==2,"old graph cannot dispatch Save");
 *(uintptr_t*)(view+0x188)=(uintptr_t)&tree.root;
 /* Main menu's three levels need one category wrapper above page->row. */
 NativeAdjustNode main=tree.root;NativeAdjustNode*children[1]={&tree.root};main.children=children;main.count=1;main.selected_index=1;main.selectable_index=1;
 *(int*)(view+0x130)=1;*(uintptr_t*)(view+0x184)=(uintptr_t)&main;
 check(((Selected)0x216ea9)(view)==&tree.save,"original main accessor reaches actual Save row");action();check(actions==3&&flags==3,"main-mode Save preserves three-level selection");
 *(int*)(view+0x130)=2;action();check(actions==3,"non-action mode does not dispatch");
 check(a7_menu_unbind_model(&model)==1,"restore manager table");
 put("NATIVE_MENU_ACTION_TREE_PASSED: original main/submenu accessors, real page graph and property lookup, Save exec success/failure, old flat negative control\n");finish();
}
