#include "native_menu.h"
extern int stock_get(void *, int, int *);
extern int stock_set(void *, int, int);
extern int stock_invalid(void *, int);
static uintptr_t manager_table[28], element_table[28], element[2], manager[2];
static a7_menu_model model, rejected;
static int calls, current_id, actual_value, accepted[9], backend_calls, reject;
static a7_menu_node nodes[5], *old[4], *storage[5], *found[5];
static uintptr_t node_table[68];
static a7_menu_attachment attachment;
static void put(const char *s) {
    volatile unsigned *u=(volatile unsigned *)0x09000000;
    while(*s) {while(u[6]&32) {} u[0]=*s++;}
}
static void finish(void) {
    register unsigned r0 __asm__("r0")=0x18;
    register unsigned r1 __asm__("r1")=0x20026;
    __asm__ volatile("svc 0x123456" : "+r"(r0), "+r"(r1) : : "memory");
    while(1) {}
}
static void check(int ok,const char *s) {if(!ok) {put("FAIL ");put(s);put("\n");finish();}}
static int init_element(void *p,int id) {check(p==element,"element this");current_id=id;return 1;}
static int get_element(void *p,int *value) {check(p==element,"get this");*value=current_id+1000;return 1;}
static int set_element(void *p,int value) {check(p==element,"set this");actual_value=value;return 1;}
void *mock_element_factory(void *p,int type) {
    (void)type;check(p==manager+1,"native factory this offset");++calls;return element;
}
static int read_custom(void *p,int id,int *value) {
    check(p==accepted,"callback context");++backend_calls;*value=accepted[id-0x7000];return 1;
}
static int write_custom(void *p,int id,int value) {
    check(p==accepted,"callback context");++backend_calls;
    if(reject || value < -9 || value > 9) return 0;
    accepted[id-0x7000]=value;return 1;
}
static int call_get(int id,int *value) {
    uintptr_t *t=(uintptr_t *)manager[0];return ((int (*)(void *,int,int *))t[3])(manager,id,value);
}
static int call_set(int id,int value) {
    uintptr_t *t=(uintptr_t *)manager[0];return ((int (*)(void *,int,int))t[17])(manager,id,value);
}
void guest_main(void) {
    int v=-123,n,i;
    check(sizeof(a7_menu_node)==40,"native node size");
    element[0]=(uintptr_t)element_table;
    element_table[2]=(uintptr_t)init_element;element_table[5]=(uintptr_t)get_element;
    element_table[22]=(uintptr_t)set_element;
    manager_table[1]=0x12345678;manager_table[5]=(uintptr_t)stock_get;
    manager_table[19]=(uintptr_t)stock_set;manager[0]=(uintptr_t)(manager_table+2);
    check(a7_menu_bind_model(&model,manager,manager_table+3,read_custom,write_custom,accepted)==-2,"wrong vtable refuses");
    check(a7_menu_bind_model(&model,manager,manager_table+2,read_custom,write_custom,accepted)==1,"bind");
    check(model.table[1]==manager_table[1],"RTTI preserved");
    check(a7_menu_bind_model(&model,manager,manager_table+2,read_custom,write_custom,accepted)==0,"bind idempotent");
    check(a7_menu_bind_model(&rejected,manager,manager_table+2,read_custom,write_custom,accepted)==-2,"second binding refuses");
    for(i=0;i<=0x269;++i) {
        check(call_get(i,&v)==1 && v==i+1000,"all original IDs preserve get dispatch");
        check(call_set(i,i-300)==1 && current_id==i && actual_value==i-300,"all original IDs preserve set dispatch");
    }
    n=calls;
    for(i=0;i<9;++i) {
        check(call_set(0x7000+i,i-4)==1,"custom set");
        check(call_get(0x7000+i,&v)==1 && v==i-4,"custom readback");
        check(stock_invalid(manager,0x7000+i)==0,"stock rejects custom ID without fallback");
    }
    check(calls==n && backend_calls==18,"custom bypasses all stock process factories");
    reject=1;check(call_set(0x7000,1)==0,"failed backend reports failure");
    check(call_get(0x7000,&v)==1 && v==-4,"failed backend preserves state");
    v=-123;check(call_get(0x7009,&v)==0 && v==-123,"outside custom and stock ranges refuses");
    check(a7_menu_unbind_model(&model)==1 && manager[0]==(uintptr_t)(manager_table+2),"unbind restores exact table");
    check(a7_menu_unbind_model(&model)==-1,"second unbind refuses");
    for(i=0;i<5;++i) nodes[i].vtable=node_table;
    old[0]=&nodes[1];old[1]=&nodes[2];old[2]=&nodes[3];old[3]=0;
    nodes[0].children=old;nodes[0].count=3;
    n=a7_menu_find_parents(nodes,sizeof nodes,node_table,old,old+4,&nodes[2],found,5);
    check(n==1 && found[0]==nodes,"read-only known-span discovery");
    check(a7_menu_find_parents(nodes,sizeof nodes,node_table,old,old+4,&nodes[2],found,0)==-1,"discovery fails closed on capacity");
    check(a7_menu_attach(&attachment,nodes,&nodes[2],&nodes[4],storage,3)==-3,"no truncation");
    check(nodes[0].count==3 && nodes[0].children==old,"failed attach unchanged");
    check(a7_menu_attach(&attachment,nodes,&nodes[2],&nodes[4],storage,5)==1,"append sibling");
    check(nodes[0].count==4 && storage[0]==old[0] && storage[1]==old[1] && storage[2]==&nodes[4] && storage[3]==old[2],"same level and original order");
    check(old[0]==&nodes[1] && old[1]==&nodes[2] && old[2]==&nodes[3],"original array preserved");
    check(a7_menu_detach(&attachment)==1 && nodes[0].children==old && nodes[0].count==3,"detach restores exact parent");
    old[0]=&nodes[2];check(a7_menu_attach(&attachment,nodes,&nodes[2],&nodes[4],storage,5)==-4,"duplicate source refuses");
    put("NATIVE_MENU_PASSED: 618 original scalar get/set IDs, 9 custom IDs, failure state, native invalid fallback, sibling insertion and rollback\n");
    finish();
}
