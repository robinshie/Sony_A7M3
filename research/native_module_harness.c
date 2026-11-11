/* Reuse native backup transport/kernel services and the complete component tests. */
#define guest_main component_guest_main
#define A7_FL_SEPARATE_KERNEL_STACK 1
#include "native_fl_runtime_harness.c"
#undef guest_main
#include "a7-fl-module.h"
#define a7_fl_install a7_fl_install_prepared
#include "native_adjust.h"
#ifdef A7_FL_TEST_SAVED_BOOT
#include "a7-fl-module-data.h"
#endif
extern int stock_get(void *,int,int *);
extern int stock_set(void *,int,int);
extern void original_action(void *);
static uintptr_t manager_words[2],manager_vtable_words[28],process_element[2],process_vtable[28];
static int process_id,stock_value,stock_calls,event_ok;
static unsigned module_checks,slot_writes,slot_failed,heap_used;
static uint8_t slot_bytes[2][128];static unsigned slot_exists[2];
static uint32_t node_heap[262144];
static a7_menu_node parent,creative,siblings[5],*parent_children[6];
static uint8_t action_view[0x248];static a7_menu_node *action_selected;
static unsigned stock_actions,action_flags,action_fallbacks;
static void test(int ok,const char *message) {module_checks++;check(ok,message);}
void unexpected(void) {check(0,"unexpected original node dependency");}
void *allocate(unsigned n) {
    n=(n+3)/4;if(!n)n=1;check(heap_used+n<262144,"original heap fixture bounds");
    void *p=node_heap+heap_used;heap_used+=n;return p;
}
void release(void *p) {check(!p||((uintptr_t)p>=(uintptr_t)node_heap && (uintptr_t)p<(uintptr_t)(node_heap+262144)),"only heap clone storage released");}
static int element_init(void *p,int id) {check(p==process_element,"stock element this");process_id=id;return 1;}
static int element_get(void *p,int *value) {check(p==process_element,"stock element read");*value=process_id+1000;return 1;}
static int element_set(void *p,int value) {check(p==process_element,"stock element write");stock_value=value;return 1;}
void *mock_element_factory(void *p,int type) {(void)type;check(p==manager_words+1,"stock manager factory");stock_calls++;return process_element;}
static int event_guard(void *opaque,enum a7_fl_platform_event event) {(void)opaque;(void)event;return event_ok;}
static int memory_guard(void *opaque,uintptr_t address,unsigned length) {
    (void)opaque;return address>=0x40000000 && address<0x80000000 && length<0x80000000-address;
}
static int read_slot(void *opaque,unsigned slot,unsigned char *out,unsigned cap,unsigned *length) {
    (void)opaque;check(slot<2&&cap>=128,"module slot read ABI");
    *length=slot_exists[slot]?128:0;
    if(!slot_exists[slot])return 1;
    bytes(out,slot_bytes[slot],128);return 0;
}
static int replace_slot(void *opaque,unsigned slot,const unsigned char *before,unsigned n,int exists,const unsigned char after[128]) {
    (void)opaque;check(slot<2 && (exists!=0)==(slot_exists[slot]!=0),"exact inactive slot existence");
    check(exists?(n==128&&same(before,slot_bytes[slot],128)):n==0,"exact inactive slot preimage");
    if(slot_failed)return -1;
    bytes(slot_bytes[slot],after,128);slot_exists[slot]=1;slot_writes++;return 0;
}
static int set_value(int id,int value) {uintptr_t *vt=(uintptr_t *)manager_words[0];return ((int(*)(void *,int,int))vt[17])(manager_words,id,value);}
static int get_value(int id,int *value) {uintptr_t *vt=(uintptr_t *)manager_words[0];return ((int(*)(void *,int,int *))vt[3])(manager_words,id,value);}
void *mock_action_select(void *view) {check(view==action_view,"native action view ABI");return action_selected;}
int mock_action_process(void *view,void *node) {
    check(view==action_view&&node==action_selected,"native selected action");
    int id=-1;((int(*)(void *,int,int *))0x40683297)(node,0xe,&id);return id;
}
void mock_action_flag(int value) {check(value==1,"native action bookkeeping");action_flags++;}
static int stock_action(void *manager,int id) {(void)id;check(manager==manager_words,"stock action manager");stock_actions++;return 1;}
static int stock_condition(void *manager,int id,int value) {(void)id;(void)value;check(manager==manager_words,"stock action condition");action_fallbacks++;return 1;}
void guest_main(void) {
    /* Genuine kernel writer reads current thread_info based on this stack. */
    *(volatile uint32_t *)0x43ffe008=0x5f000000;
    test_native_abi();test_core();test_replacement();test_preferences();test_control();test_preview();test_recognition();test_recovery();
    reset();event_ok=1;slot_writes=slot_failed=0;
    manager_vtable_words[1]=0x12345678;manager_vtable_words[5]=(uintptr_t)stock_get;manager_vtable_words[19]=(uintptr_t)stock_set;
    manager_vtable_words[23]=(uintptr_t)stock_action;manager_vtable_words[24]=(uintptr_t)stock_condition;
    manager_words[0]=(uintptr_t)(manager_vtable_words+2);
    process_element[0]=(uintptr_t)process_vtable;process_vtable[2]=(uintptr_t)element_init;process_vtable[5]=(uintptr_t)element_get;process_vtable[22]=(uintptr_t)element_set;
    typedef void *(*Ctor)(void *,void *,int,const void *);
    Ctor ctor=(Ctor)0x4068338d;
    ctor(&creative,0,0,0);for(unsigned i=0;i<5;i++)ctor(siblings+i,0,0,0);
    parent_children[0]=siblings;parent_children[1]=siblings+1;parent_children[2]=&creative;
    parent_children[3]=siblings+2;parent_children[4]=siblings+3;parent_children[5]=siblings+4;
    ctor(&parent,parent_children,6,0);parent.depth=2;
    struct a7_fl_platform platform;
    clear(&platform,sizeof platform);platform.view_base=0x40000000;platform.caution_base=0x40000000;
    platform.view_manager=process_element;platform.manager=manager_words;platform.manager_vtable=manager_vtable_words+2;platform.parent_vtable=(uintptr_t *)0x40918ec8;
    platform.creative_style=&creative;platform.parents[0]=&parent;platform.parent_count=1;platform.backup=api;
    platform.storage=(struct a7_fl_store_io){read_slot,replace_slot,0};platform.identity=identity_guard;
    platform.event=event_guard;platform.readable=memory_guard;platform.opaque=&identity_calls;
#ifdef A7_FL_TEST_SAVED_BOOT
    platform.view_manager=0;parent.depth=0;
    struct a7_fl_preference saved_boot={7,1,{2,-3,4,5,-2,0,1,0},0};
    A7FLColorParams desired={2,-3,4,5,-2};uint8_t desired_table[1280];
    check(a7_fl_adjust_lut(CANDIDATE,1280,EXPAND,COMPRESS,&desired,desired_table,1280)==0,"saved boot generation");
    saved_boot.candidate_crc=a7_fl_crc(desired_table,1280);
    check(a7_fl_preference_encode(slot_bytes[0],&saved_boot,a7_pkg_original_sha,a7_pkg_build)==0,"saved boot record");slot_exists[0]=1;
    A7FLColorParams previous_preview={-7,8,-5,6,7};
    check(a7_fl_adjust_lut(CANDIDATE,1280,EXPAND,COMPRESS,&previous_preview,data_guarded+1,1280)==0,"old serialized preview");
    test(a7_fl_prepare(&platform)==0,"boot prepare without ViewManager");parent.vtable=0;
    test(a7_fl_initialize_color_prepared()==0 && a7_fl_status()->runtime_ready && !a7_fl_status()->installed && a7_fl_status()->mode==1 && write_calls==2 && slot_writes==0 && same(data_guarded+1,desired_table,1280),"cold boot recovers historic preview and applies durable ON recipe without any menu");
    parent.vtable=platform.parent_vtable;platform.view_manager=process_element;
    struct a7_fl_platform changed=platform;changed.backup.read=0;
    test(a7_fl_configure_menu(&changed)==A7_FL_MODULE_PLATFORM,"menu configure cannot replace backend");
    test(a7_fl_configure_menu(&platform)==0 && a7_fl_install(0x40000000,process_element)==0 && write_calls==2 && slot_writes==0,"first MENU config adopts real ViewManager without repeating color init");
    a7_menu_node *cold_look=parent.children[3];
    test(parent.depth==0 && !cold_look->parent,"cold menu templates await original main root initialization");
    typedef int (*DeepInit)(void *,void *,int,int);
    test(((DeepInit)parent.vtable[0xf8/4])(&parent,0,0,3)==1 && cold_look->parent==&parent && cold_look->depth==4,"subsequent original initialization supplies actual ancestry");
    typedef int (*GetSelected)(void *,void **);typedef int (*GetInt)(void *,int,int *);
    void *selected=0;int selected_value=-99;
    test(((GetSelected)0x40682951)(cold_look->children[0],&selected)==1 && ((GetInt)0x40683297)(selected,0x10,&selected_value)==1 && selected_value==1,"late original graph init retains saved ON cursor");
    test(((GetSelected)0x40682951)(cold_look->children[1],&selected)==1 && ((GetInt)0x40683297)(selected,0x10,&selected_value)==1 && selected_value==2,"late original graph init retains saved scalar cursor");
    unsigned char grayout=0;
    test(((int(*)(void *,unsigned char *))0x40682d0b)(cold_look->children[6],&grayout)==1,"late init keeps unsupported sharpness gray");
    put("NATIVE_FL_MODULE_BOOT_PASSED: historical disk recovery, saved ON parameters before MENU, first-MENU configuration, late native graph init/cursors\n");finish();
#endif
    test(a7_fl_install(0x40000000,process_element)==A7_FL_MODULE_PLATFORM && slot_writes==0,"missing platform refuses activation");
    test(a7_fl_prepare(&platform)==0,"prepare verified injected platform");
    test(a7_fl_install(0x40001000,process_element)==A7_FL_MODULE_PLATFORM,"wrong view base refused");
    test(a7_fl_install(0x40000000,manager_words)==A7_FL_MODULE_PLATFORM,"process manager cannot impersonate ViewManager argument");
    event_ok=0;test(a7_fl_install(0x40000000,process_element)==A7_FL_MODULE_WITNESS && slot_writes==0,"missing lifecycle witness no writes");event_ok=1;
    parent.vtable=0;test(a7_fl_install(0x40000000,process_element)==A7_FL_MODULE_PARENT && slot_writes==0,"wrong parent refuses before I/O");parent.vtable=platform.parent_vtable;
    A7FLColorParams old_preview={7,-8,5,6,-7};check(a7_fl_adjust_lut(CANDIDATE,1280,EXPAND,COMPRESS,&old_preview,data_guarded+1,1280)==0,"prior uncommitted preview setup");
    parent.vtable=0;
    test(a7_fl_initialize_color_prepared()==0 && a7_fl_status()->runtime_ready && !a7_fl_status()->installed && slot_writes==1 && parent.count==6 && manager_words[0]==(uintptr_t)(manager_vtable_words+2),"boot initializes color without touching unavailable menu graph");
    parent.vtable=platform.parent_vtable;
    test(a7_fl_install(0x40000000,process_element)==0,"full native module install");
    const struct a7_fl_module_status *state=a7_fl_status();
    test(state->installed && !state->fault && state->parents==1 && state->mode==0 && slot_writes==1,"resident module default Off with durable first record");
    test(parent.count==7 && parent.children[2]==&creative && parent.children[4]==siblings+2 && same(data_guarded+1,ORIGINAL,1280),"same-level insertion and historical baseline restored");
    a7_menu_node *look=parent.children[3];
    test(look!=&creative && look->count==10,"independent look root with explicit Save row");
    test(look->parent==&parent,"native parent ancestry");
    test(look->depth==3,"native root depth");
    test(parent.children[4]->index==5,"native stock sibling one-based index");
    test(a7_fl_install(0x40000000,process_element)==0 && parent.count==7 && slot_writes==1,"repeated install idempotent");
    int value;
    for(int id=0;id<618;id++)check(get_value(id,&value)==1&&value==id+1000&&set_value(id,id-300)==1&&stock_value==id-300,"all stock IDs preserve original dispatch");
    test(stock_calls==1236,"stock model routes remain intact");
    test(set_value(0x7000,1)==1 && state->mode==1 && state->dirty && slot_writes==1,"native mode setter performs RAM preview only");
    test(set_value(0x7001,3)==1 && get_value(0x7001,&value)==1 && value==3 && slot_writes==1,"native contrast setter reaches LUT backend");
    unsigned writes_before=write_calls;
    test(a7_fl_initialize_color_prepared()==0 && write_calls==writes_before && state->mode==1 && state->dirty && state->parameters[0]==3 && slot_writes==1,"later still-view entry preserves unsaved RAM preview");
    unsigned char gray=0;
    typedef int(*GetGray)(void *,unsigned char *);
    test(((GetGray)0x40682d0b)(look->children[6],&gray)==1 && set_value(0x7006,1)==0,"unsupported sharpness visible gray and write rejected");
    test(set_value(0x7007,2)==0 && set_value(0x7008,1)==0,"range and clarity reject");
    event_ok=0;test(a7_fl_confirm()==A7_FL_MODULE_EVENT && slot_writes==1,"unproven confirmation cannot persist");event_ok=1;
    *(uint32_t *)(action_view+0x130)=1;*(uintptr_t *)(action_view+0x150)=(uintptr_t)manager_words;*(int *)(action_view+0x158)=7;
    action_selected=look->children[9];original_action(action_view);
    test(slot_writes==2 && state->generation==2 && !state->dirty && action_flags==1 && action_fallbacks==0 && stock_actions==0,"original native Save action persists once");
    uint8_t committed[1280];bytes(committed,data_guarded+1,1280);
    test(set_value(0x7001,-3)==1 && a7_fl_cancel()==0 && get_value(0x7001,&value)==1 && value==3 && same(data_guarded+1,committed,1280) && slot_writes==2,"cancel restores committed LUT and native cursor state");
    test(set_value(0x7002,4)==1,"highlight preview");slot_failed=1;
    test(a7_fl_confirm()==A7_FL_CONTROL_PERSIST && state->dirty && state->generation==2,"durable write failure never claims committed UI");slot_failed=0;
    test(a7_fl_confirm()==0 && slot_writes==3 && state->generation==3,"explicit confirmation retry succeeds");
    test(set_value(0x7000,0)==1 && a7_fl_confirm()==0 && same(data_guarded+1,ORIGINAL,1280) && state->mode==0,"Off restores original and records Off preference");
    test(a7_fl_uninstall()==0 && parent.count==6 && parent.children==parent_children && parent.children[3]->index==4 && manager_words[0]==(uintptr_t)(manager_vtable_words+2),"uninstall restores native parent model and stock indices");
    test(saves==0,"module never requests calibration sync");
    put("NATIVE_FL_MODULE_PASSED: original nodes + 618 stock routes + runtime421checks; integrated preview/commit/cancel/store/rollback\n");
    put("PLATFORM_AND_FILESYSTEM_MODELED; NO_CAMERA_ACTIVATION_OR_NATIVE_RENDERER_TEST\n");finish();
}
