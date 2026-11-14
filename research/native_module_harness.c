/* Reuse native backup transport/kernel services and the complete component tests. */
#define guest_main component_guest_main
#define A7_FL_SEPARATE_KERNEL_STACK 1
#include "native_fl_runtime_harness.c"
#undef guest_main
#include "a7-fl-module.h"
#define a7_fl_install a7_fl_install_prepared
#include "native_adjust.h"
#include "a7-fl-module-data.h"
#ifdef A7_FL_FILM_CONTROLS
#include "a7-fl-fivepoint-preview.h"
#include "a7-fl-worklog.h"
#endif
#ifdef A7_FL_DUAL_LOOK
#include "a7-fl-cinema.h"
#ifdef A7_FL_LEICA_LOOK
#include "a7-fl-leica.h"
#endif
#endif
extern int stock_get(void *,int,int *);
extern int stock_set(void *,int,int);
extern void original_action(void *);
static uintptr_t manager_words[2],manager_vtable_words[28],process_element[2],process_vtable[28];
static int process_id,stock_value,stock_calls,event_ok;
static unsigned module_checks,slot_writes,slot_failed,heap_used;
static uint8_t slot_bytes[2][128];static unsigned slot_exists[2];
#ifdef A7_FL_FILM_CONTROLS
static uint8_t work_bytes[2][128];static unsigned work_exists[2];
#endif
static uint32_t node_heap[262144];
static a7_menu_node parent,creative,siblings[5],*parent_children[6];
static uint8_t action_view[0x248];static a7_menu_node *action_selected;
static unsigned stock_actions,action_flags,action_fallbacks;
#ifdef A7_FL_SAVE_DIALOG
static int (*dialog_commit)(void);
static int dialog_open_fail;
static int (*dialog_owns_root)(const void*);
int a7_fl_dialog_watch_menu(uintptr_t base,void*manager,int(*owns)(const void*)) {
    check(base==0x40000000&&manager==process_element&&owns,"menu observer platform");
    dialog_owns_root=owns;return 0;
}
int a7_fl_dialog_open(uintptr_t base,void*manager,int(*commit)(void)) {
    check(base==0x40000000&&manager==process_element&&commit,"dialog receives exact native platform");
    if(dialog_open_fail)return -1;
    dialog_commit=commit;return 0;
}
static int confirm_dialog(void){int(*commit)(void)=dialog_commit;dialog_commit=0;return commit?commit():-1;}
#endif
static void test(int ok,const char *message) {module_checks++;check(ok,message);}
#ifdef A7_FL_CAPTURE_LOOK
#ifdef A7_FL_CAPTURE_CONTROLS
#include "a7-fl-capture-controls.h"
static struct a7_capture_controls expected_capture;
#endif
static int capture_matches(int enabled) {
#ifdef A7_FL_CAPTURE_CONTROLS
    const struct a7_fl_module_status *s=a7_fl_status();
    A7FLColorParams p={s->parameters[0],s->parameters[1],s->parameters[2],s->parameters[3],s->parameters[4]};
    const uint8_t *stock[]={a7_pkg_original[1],a7_pkg_original[2]},*legacy[]={a7_pkg_capture1,a7_pkg_capture2};
    if(!expected_capture.prepared&&a7_capture_prepare(&expected_capture,&api,stock,legacy,EXPAND,COMPRESS))return 0;
    uint8_t expected[1280];
    for(unsigned i=0;i<2;i++) {
        if(enabled) {
#ifdef A7_FL_DUAL_LOOK
            if(a7_capture_generate_preset(&expected_capture,i,enabled,&p,expected))return 0;
#else
            if(a7_capture_generate(&expected_capture,i,&p,expected))return 0;
#endif
        }
        else bytes(expected,stock[i],1280);
        if(!same(expected,other_tables_data[i],1280))return 0;
    }
    return same(other_tables_data[2],a7_pkg_original[3],1280);
#else
    return same(other_tables_data[0],enabled?a7_pkg_capture1:a7_pkg_original[1],1280) &&
           same(other_tables_data[1],enabled?a7_pkg_capture2:a7_pkg_original[2],1280) &&
           same(other_tables_data[2],a7_pkg_original[3],1280);
#endif
}
#endif
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
    uint8_t (*records)[128]=slot_bytes;unsigned *exists=slot_exists;
#ifdef A7_FL_FILM_CONTROLS
    if(opaque){records=work_bytes;exists=work_exists;}
#else
    (void)opaque;
#endif
    check(slot<2&&cap>=128,"module slot read ABI");
    *length=exists[slot]?128:0;
    if(!exists[slot])return 1;
    bytes(out,records[slot],128);return 0;
}
static int replace_slot(void *opaque,unsigned slot,const unsigned char *before,unsigned n,int exists,const unsigned char after[128]) {
    uint8_t (*records)[128]=slot_bytes;unsigned *present=slot_exists;
#ifdef A7_FL_FILM_CONTROLS
    if(opaque){records=work_bytes;present=work_exists;}
#endif
    check(slot<2 && (exists!=0)==(present[slot]!=0),"exact inactive slot existence");
    check(exists?(n==128&&same(before,records[slot],128)):n==0,"exact inactive slot preimage");
    if(slot_failed)return -1;
    bytes(records[slot],after,128);present[slot]=1;if(!opaque)slot_writes++;return 0;
}
static int set_value(int id,int value) {uintptr_t *vt=(uintptr_t *)manager_words[0];return ((int(*)(void *,int,int))vt[17])(manager_words,id,value);}
static int get_value(int id,int *value) {uintptr_t *vt=(uintptr_t *)manager_words[0];return ((int(*)(void *,int,int *))vt[3])(manager_words,id,value);}
#ifdef A7_FL_PREVIEW_REFRESH
#include "a7-fl-preview.h"
static unsigned preview_requests;
static int preview_error;
int a7_fl_preview_request(uintptr_t base,const struct a7_fl_api *backup,
                         int (*readable)(void *,uintptr_t,unsigned),void *opaque) {
    test(base==0x40000000&&backup->read==api.read&&readable==memory_guard&&opaque==&identity_calls,"preview uses witnessed native platform");
    test(a7_fl_status()->installed,"no model request during early color boot");
    int enabled,values[5];test(get_value(0x7000,&enabled)==1,"current accepted mode readable");
    for(unsigned i=0;i<5;i++){test(get_value(0x7001+i,values+i)==1,"current accepted scalar readable");values[i]-=i==3?0:9;}
    A7FLColorParams p={values[0],values[1],values[2],values[3],values[4]};uint8_t expected[1280];
    const uint8_t *base_table=CANDIDATE;
#ifdef A7_FL_DUAL_LOOK
    uint8_t cinema_base[1280];
    if(enabled==2) {
        test(!a7_cinema_base(ORIGINAL,EXPAND,COMPRESS,cinema_base),"Cinema base generated");
        base_table=cinema_base;
    }
#endif
#ifdef A7_FL_LEICA_LOOK
    if(enabled==3){test(!a7_leica_base(ORIGINAL,EXPAND,COMPRESS,cinema_base),"FL3 expected base");base_table=cinema_base;}
#endif
 #ifdef A7_FL_FILM_CONTROLS
    if(enabled>0) {
        int points[5];
        for(unsigned i=0;i<5;i++){
            test(get_value(native_adjust_field_id(8+i),points+i)==1,"read curve enum");
            points[i]-=9;
        }
        test(!a7_fl_fivepoint_preview(base_table,EXPAND,COMPRESS,&p,points,expected),"curve preview expected");
    } else
 #endif
    if(enabled)test(a7_fl_adjust_lut(base_table,1280,EXPAND,COMPRESS,&p,expected,1280)==0,"expected source generated");
    else bytes(expected,ORIGINAL,1280);
    test(same(expected,data_guarded+1,1280),"refresh follows successful complete source-table update");
    preview_requests++;return preview_error?preview_error:1;
}
#endif
static a7_menu_node *look_row(a7_menu_node *look,unsigned index) {
    check(look&&look->count==NATIVE_ADJUST_PAGES&&index<=NATIVE_ADJUST_FIELDS+1,"look has native pages and bounded row");
    return look->children[index/6]->children[index%6];
}
static int row_title(a7_menu_node *look,unsigned index) {
    int value=0;check(((int(*)(void *,int,int *))0x40683297)(look_row(look,index),0,&value),"native row title lookup");return value;
}
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
#ifdef A7_FL_FILM_CONTROLS
    platform.film_storage=(struct a7_fl_store_io){read_slot,replace_slot,work_bytes};
#endif
#if defined(A7_FL_FILM_CONTROLS) && !defined(A7_FL_TEST_SAVED_BOOT)
    test(!a7_fl_prepare(&platform)&&!a7_fl_install(0x40000000,process_element),"curve resident installs");
    const struct a7_fl_module_status *film=a7_fl_status();
    a7_menu_node *film_look=parent.children[3];
    test(film->mode==0&&!slot_writes&&film_look->count==3,"curve menu starts Off without writes");
    int enum_value=0,black=native_adjust_field_id(8);
    test(!set_value(black,18),"cannot edit curve while Off");
    test(set_value(0x7000,3)&&capture_matches(3),"activate FL3");
    uint8_t before_film[3][1280];
    bytes(before_film[0],data_guarded+1,1280);
    for(unsigned t=1;t<3;t++)bytes(before_film[t],other_tables_data[t-1],1280);
    test(set_value(black,18)&&!same(before_film[0],data_guarded+1,1280),"black point updates preview");
    for(unsigned t=1;t<3;t++)test(!same(before_film[t],other_tables_data[t-1],1280),"black point updates CAP");
    test(film->dirty&&!slot_writes&&work_exists[0]&&work_exists[1],"preview records work without saving preferences");
    test(!a7_fl_cancel()&&film->mode==0&&!film->dirty&&!slot_writes,"cancel restores previously confirmed Off");
    test(set_value(0x7000,3),"select FL3 before Save");
    const int selected_points[5]={18,7,10,11,5};
    for(unsigned f=0;f<5;f++){
        int id=native_adjust_field_id(8+f);
        test(set_value(id,selected_points[f])&&get_value(id,&enum_value)&&enum_value==selected_points[f],
             "edit and read each native curve field");
    }
    *(uint32_t *)(action_view+0x130)=1;*(uintptr_t *)(action_view+0x150)=(uintptr_t)manager_words;*(int *)(action_view+0x158)=7;
    action_selected=look_row(film_look,NATIVE_ADJUST_FIELDS+1);
    original_action(action_view);
    test(dialog_commit&&slot_writes==0,"open native Save dialog without a settings write");
    test(!confirm_dialog()&&!film->dirty&&slot_writes==1,"native confirmed Save writes curve preference once");
    struct a7_fl_preference result;
    test(a7_fl_preference_choose(&result,slot_bytes[0],slot_exists[0]?128:0,slot_bytes[1],slot_exists[1]?128:0,
                                a7_pkg_original_sha,a7_pkg_build)>=0&&result.schema==4&&result.film[2][2]==9,
         "read back explicit Save and preserved schema");
    for(unsigned f=0;f<5;f++)test(result.film[2][2+f]==selected_points[f]-9,"all five curve values stored in FL3");
    test(set_value(black,5)&&!a7_fl_cancel()&&get_value(black,&enum_value)&&enum_value==18,"cancel restores saved curve");
    const int bank_points[3][5]={{11,6,13,8,7},{12,7,14,9,8},{18,7,10,11,5}};
    for(unsigned bank=1;bank<=2;bank++){
        test(set_value(0x7000,(int)bank)&&capture_matches(bank),"activate zero-curve FL/FL2");
        for(unsigned t=0;t<3;t++)bytes(before_film[t],t?other_tables_data[t-1]:data_guarded+1,1280);
        for(unsigned f=0;f<5;f++)test(set_value(native_adjust_field_id(8+f),bank_points[bank-1][f]),"all five controls enabled for FL and FL2");
        for(unsigned t=0;t<3;t++)test(!same(before_film[t],t?other_tables_data[t-1]:data_guarded+1,1280),"FL and FL2 curves affect preview and both capture tables");
        original_action(action_view);test(!confirm_dialog(),"save independent FL/FL2 curve");
    }
    for(unsigned bank=1;bank<=3;bank++){
        test(set_value(0x7000,(int)bank),"switch all three curve banks");
        for(unsigned f=0;f<5;f++)test(get_value(native_adjust_field_id(8+f),&enum_value)&&enum_value==bank_points[bank-1][f],"selected curve bank restored exactly");
    }
    test(a7_fl_preference_choose(&result,slot_bytes[0],128,slot_bytes[1],128,a7_pkg_original_sha,a7_pkg_build)>=0,"decode saved three-bank record");
    for(unsigned bank=0;bank<3;bank++)for(unsigned f=0;f<5;f++)
        test(result.film[bank][f+2]==bank_points[bank][f]-9,"durable independent curve banks");
    test(set_value(0x7000,0)&&!set_value(black,18),"Off rejects curve edits");
    test(set_value(0x7000,3)&&get_value(black,&enum_value)&&enum_value==18,"Off preserves FL3");
    put("NATIVE_FL_ALL_CURVE_BANKS_PASSED\n");
    test(!film->fault,"no resident fault after curve flow");
    put("NATIVE_FL_CURVE_MAIN_PASSED\n");finish();
#endif
#ifdef A7_FL_TEST_SAVED_BOOT
    platform.view_manager=0;parent.depth=0;
    struct a7_fl_preference saved_boot={7,1,{2,-3,4,5,-2,
#ifdef A7_FL_SPATIAL_SETTINGS_ONLY
        -2,4,7
#else
        0,1,0
#endif
    },0,0,{0},{0}
#ifdef A7_FL_FILM_CONTROLS
    ,{{0}}
#endif
    };
    A7FLColorParams desired={2,-3,4,5,-2};uint8_t desired_table[1280];
    const uint8_t *saved_base=CANDIDATE,*prior_base=CANDIDATE;
#ifdef A7_FL_DUAL_LOOK
    uint8_t cinema_base[1280];
    check(!a7_cinema_base(ORIGINAL,EXPAND,COMPRESS,cinema_base),"boot Cinema base generated");

#ifdef A7_FL_TEST_CINEMA_BOOT
    prior_base=cinema_base;
    saved_boot.enabled=2;saved_base=cinema_base;
#endif
#endif
#ifdef A7_FL_TEST_LEICA_BOOT
    check(!a7_leica_base(ORIGINAL,EXPAND,COMPRESS,cinema_base),"FL3 saved base");
    saved_boot.enabled=3;saved_base=prior_base=cinema_base;
#endif
#ifdef A7_FL_FILM_CONTROLS
    struct a7_fl_preference recovering=saved_boot;
    recovering.schema=4;recovering.other_parameters[6]=recovering.third_parameters[6]=3;
    for(unsigned b=0;b<2;b++)for(unsigned f=0;f<5;f++)recovering.film[b][f+2]=(int8_t)((int)b+(int)f-3);
    const int points[5]={5,-2,1,2,-4},transient[5]={-5,-2,1,2,-4};
    for(unsigned f=0;f<5;f++)recovering.film[2][2+f]=(int8_t)points[f];
    test(!a7_fl_fivepoint_preview(saved_base,EXPAND,COMPRESS,&desired,points,desired_table),"saved curve reconstruction");
    recovering.candidate_crc=a7_fl_crc(desired_table,1280);
    test(!a7_fl_preference_encode(slot_bytes[0],&recovering,a7_pkg_original_sha,a7_pkg_build),"store previous confirmed curve");slot_exists[0]=1;
    struct a7_fl_preference pending=recovering;pending.film[2][2]=-5;
    test(!a7_fl_fivepoint_preview(saved_base,EXPAND,COMPRESS,&desired,transient,data_guarded+1),"partially serialized unsaved curve");
    pending.candidate_crc=a7_fl_crc(data_guarded+1,1280);
    struct a7_fl_worklog prior={0};
    test(!a7_fl_worklog_open(&prior,&platform.film_storage,a7_pkg_original_sha,a7_pkg_build)&&
         !a7_fl_worklog_prepare(&prior,&recovering)&&!a7_fl_worklog_prepare(&prior,&pending),"saved and pending work endpoints");
    test(!a7_fl_prepare(&platform)&&!a7_fl_initialize_color_prepared()&&!slot_writes&&
         a7_fl_status()->runtime_ready&&a7_fl_status()->mode==3&&same(data_guarded+1,desired_table,1280),
         "runtime boot recovers last Save from partial serialization");
    const uint8_t *stock[]={a7_pkg_original[1],a7_pkg_original[2]},*legacy[]={a7_pkg_capture1,a7_pkg_capture2};
    test(!a7_capture_prepare(&expected_capture,&api,stock,legacy,EXPAND,COMPRESS),"expected recovery CAP context");
    for(unsigned t=0;t<2;t++){
        uint8_t target[1280];
        test(!a7_capture_generate_curve(&expected_capture,t,3,&desired,points,target)&&
             same(target,other_tables_data[t],1280),"both CAP tables recovered on boot");
    }
    platform.view_manager=process_element;
    test(!a7_fl_configure_menu(&platform)&&!a7_fl_install(0x40000000,process_element),"attach the menu after color boot");
    for(unsigned f=0;f<5;f++){
        int saved_enum=-1;
        test(get_value(native_adjust_field_id(8+f),&saved_enum)&&saved_enum==points[f]+9,
             "cold menu restores each confirmed curve point");
    }
    for(unsigned bank=1;bank<=2;bank++){
        test(set_value(0x7000,(int)bank),"cold boot switches FL and FL2");
        int bank_curve[5];
        for(unsigned f=0;f<5;f++){
            int value=-1;bank_curve[f]=recovering.film[bank-1][f+2];
            test(get_value(native_adjust_field_id(8+f),&value)&&value==bank_curve[f]+9,"cold boot keeps inactive curve bank");
        }
        const struct a7_fl_module_status *status=a7_fl_status();
        A7FLColorParams color={status->parameters[0],status->parameters[1],status->parameters[2],status->parameters[3],status->parameters[4]};
        for(unsigned t=0;t<2;t++){
            uint8_t target[1280];
            test(!a7_capture_generate_curve(&expected_capture,t,bank,&color,bank_curve,target)&&
                 same(target,other_tables_data[t],1280),"recovered FL and FL2 CAP curve applied");
        }
    }
    put("NATIVE_FL_ALL_CURVE_BOOT_PASSED\n");
    put("NATIVE_FL_CURVE_BOOT_PASSED\n");finish();
#endif
    check(a7_fl_adjust_lut(saved_base,1280,EXPAND,COMPRESS,&desired,desired_table,1280)==0,"saved boot generation");
    saved_boot.candidate_crc=a7_fl_crc(desired_table,1280);
#ifdef A7_FL_TEST_BANK_BOOT
    saved_boot.schema=2;
#ifdef A7_FL_TEST_LEICA_BOOT
    saved_boot.schema=3;for(unsigned i=0;i<8;i++)saved_boot.third_parameters[i]=(int8_t)(i==6?3:0);saved_boot.third_parameters[4]=-5;
#endif
    for(unsigned i=0;i<8;i++)saved_boot.other_parameters[i]=(int8_t)(i==6?5:0);
    saved_boot.other_parameters[0]=8;saved_boot.other_parameters[2]=-4;
#endif
    check(a7_fl_preference_encode(slot_bytes[0],&saved_boot,a7_pkg_original_sha,a7_pkg_build)==0,"saved boot record");slot_exists[0]=1;
    A7FLColorParams previous_preview={-7,8,-5,6,7};
    check(a7_fl_adjust_lut(prior_base,1280,EXPAND,COMPRESS,&previous_preview,data_guarded+1,1280)==0,"old serialized preview");
    unsigned boot_writes=2,boot_slot_writes=0;
#ifdef A7_FL_LOOK_BANKS
    /* Expected migration: preserve all shared legacy settings as FL. */
    #ifdef A7_FL_LEICA_LOOK
    int boot_migrated=a7_fl_preference_migrate_three(&saved_boot);
#else
    int boot_migrated=a7_fl_preference_migrate(&saved_boot);
#endif
    saved_boot.generation+=(unsigned)boot_migrated;
    desired=(A7FLColorParams){saved_boot.parameters[0],saved_boot.parameters[1],saved_boot.parameters[2],saved_boot.parameters[3],saved_boot.parameters[4]};
    check(!a7_fl_adjust_lut(saved_base,1280,EXPAND,COMPRESS,&desired,desired_table,1280),"migrated boot table");
    boot_slot_writes=(unsigned)boot_migrated;
#endif
#ifdef A7_FL_CAPTURE_LOOK
    /* A native global save might serialize only one of the two preview tables. */
#ifdef A7_FL_TEST_CINEMA_BOOT
    const uint8_t *stock[]={a7_pkg_original[1],a7_pkg_original[2]},*legacy[]={a7_pkg_capture1,a7_pkg_capture2};
    check(!a7_capture_prepare(&expected_capture,&api,stock,legacy,EXPAND,COMPRESS),"boot CAP prepare");
    check(!a7_capture_generate_preset(&expected_capture,0,saved_boot.enabled,&previous_preview,other_tables_data[0]),"serialized unsaved Cinema CAP");
#else
    bytes(other_tables_data[0],a7_pkg_capture1,1280);
#endif
    boot_writes++;
#ifdef A7_FL_CAPTURE_CONTROLS
    boot_writes++; /* Legacy CAP1 also migrates to the stronger dynamic recipe. */
#endif
#endif
    test(a7_fl_prepare(&platform)==0,"boot prepare without ViewManager");parent.vtable=0;
    test(a7_fl_initialize_color_prepared()==0 && a7_fl_status()->runtime_ready && !a7_fl_status()->installed && a7_fl_status()->mode==saved_boot.enabled && write_calls==boot_writes && slot_writes==boot_slot_writes && same(data_guarded+1,desired_table,1280),"cold boot recovers historic preview and applies durable ON recipe without any menu");
#ifdef A7_FL_CAPTURE_LOOK
#ifdef A7_FL_LOOK_BANKS
    struct a7_fl_preference boot_record;
    test(a7_fl_preference_choose(&boot_record,slot_bytes[0],slot_exists[0]?128:0,slot_bytes[1],slot_exists[1]?128:0,a7_pkg_original_sha,a7_pkg_build)>=0 && boot_record.schema==saved_boot.schema && boot_record.generation==saved_boot.generation,"cold boot keeps dual bank record");
    for(unsigned i=0;i<8;i++)test(boot_record.parameters[i]==saved_boot.parameters[i] && boot_record.other_parameters[i]==saved_boot.other_parameters[i] && boot_record.third_parameters[i]==saved_boot.third_parameters[i],"cold boot preserves both complete banks");
#endif
    test(capture_matches(saved_boot.enabled),"cold boot reconciles mixed stock and CAP preimages");
    put("NATIVE_FL_CAPTURE_BOOT_PASSED\n");
#endif
    parent.vtable=platform.parent_vtable;platform.view_manager=process_element;
    struct a7_fl_platform changed=platform;changed.backup.read=0;
    test(a7_fl_configure_menu(&changed)==A7_FL_MODULE_PLATFORM,"menu configure cannot replace backend");
    test(a7_fl_configure_menu(&platform)==0 && a7_fl_install(0x40000000,process_element)==0 && write_calls==boot_writes && slot_writes==boot_slot_writes,"first MENU config adopts real ViewManager without repeating color init");
    a7_menu_node *cold_look=parent.children[3];
    test(parent.depth==0 && !cold_look->parent,"cold menu templates await original main root initialization");
    typedef int (*DeepInit)(void *,void *,int,int);
    test(((DeepInit)parent.vtable[0xf8/4])(&parent,0,0,3)==1 && cold_look->parent==&parent && cold_look->depth==4,"subsequent original initialization supplies actual ancestry");
    typedef int (*GetSelected)(void *,void **);typedef int (*GetInt)(void *,int,int *);
    void *selected=0;int selected_value=-99;
    test(((GetSelected)0x40682951)(look_row(cold_look,0),&selected)==1 && ((GetInt)0x40683297)(selected,0x10,&selected_value)==1 && selected_value==saved_boot.enabled,"late original graph init retains saved preset cursor");
    test(((GetSelected)0x40682951)(look_row(cold_look,1),&selected)==1 && ((GetInt)0x40683297)(selected,0x10,&selected_value)==1 && selected_value==saved_boot.parameters[0]+9,"late original graph init retains saved scalar cursor as unsigned UI enum");
    unsigned char grayout=0;
#ifdef A7_FL_SPATIAL_SETTINGS_ONLY
    const int saved_spatial_enums[]={saved_boot.parameters[5]+3,saved_boot.parameters[6]-1,saved_boot.parameters[7]};
    for(unsigned i=0;i<3;i++)
        test(((int(*)(void *,unsigned char *))0x40682d0b)(look_row(cold_look,6+i),&grayout)==0 &&
             ((GetSelected)0x40682951)(look_row(cold_look,6+i),&selected)==1 &&
             ((GetInt)0x40683297)(selected,0x10,&selected_value)==1 && selected_value==saved_spatial_enums[i],
             "cold menu restores saved spatial cursor without grayout");
#else
    test(((int(*)(void *,unsigned char *))0x40682d0b)(look_row(cold_look,6),&grayout)==1,"late init keeps unsupported sharpness gray");
#endif
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
#ifdef A7_FL_SAVE_DIALOG
    test(dialog_owns_root&&dialog_owns_root(look)&&!dialog_owns_root(&creative)&&!dialog_owns_root(0),"refresh limited to owned look root");
#endif
    test(look!=&creative && look->count==2 && look->children[0]->count==6 && look->children[1]->count==4,"independent look root with two proper pages and explicit Save row");
    test(look->parent==&parent,"native parent ancestry");
    test(look->depth==3,"native root depth");
    test(parent.children[4]->index==5,"native stock sibling one-based index");
    test(a7_fl_install(0x40000000,process_element)==0 && parent.count==7 && slot_writes==1,"repeated install idempotent");
    int value;
    for(int id=0;id<618;id++)check(get_value(id,&value)==1&&value==id+1000&&set_value(id,id-300)==1&&stock_value==id-300,"all stock IDs preserve original dispatch");
    test(stock_calls==1236,"stock model routes remain intact");
#ifdef A7_FL_PREVIEW_REFRESH
    test(preview_requests==0,"neither boot nor unrelated stock IDs issues replay");
#endif
    test(set_value(0x7000,1)==1 && state->mode==1 && state->dirty && slot_writes==1,"native mode setter performs RAM preview only");
#ifdef A7_FL_PREVIEW_REFRESH
    test(preview_requests==1,"accepted FL enable requests preview refresh");
    test(set_value(0x7000,1)==1&&preview_requests==1,"same mode avoids duplicate request");
#endif
#ifdef A7_FL_CAPTURE_LOOK
    test(capture_matches(1),"FL switch writes both still capture properties");
    test(a7_fl_cancel()==0 && capture_matches(0) && state->mode==0,"cancel restores both CAP tables");
    test(set_value(0x7000,1)==1 && capture_matches(1),"FL switch reapplies both CAP tables");
#endif
    test(set_value(0x7001,12)==1 && get_value(0x7001,&value)==1 && value==12 && state->parameters[0]==3 && slot_writes==1,"native contrast enum reaches signed LUT backend");
#ifdef A7_FL_CAPTURE_CONTROLS
    test(capture_matches(1),"contrast dispatch updates both actual CAP properties");
#endif
    unsigned unchanged_writes=write_calls;
    test(set_value(0x7001,-1)==0 && set_value(0x7001,19)==0 && set_value(0x7000,A7_FL_PRESET_MAX+1)==0 && write_calls==unchanged_writes && state->parameters[0]==3 && slot_writes==1,"invalid native enums never reach LUT or preference writes");
    unsigned writes_before=write_calls;
    test(a7_fl_initialize_color_prepared()==0 && write_calls==writes_before && state->mode==1 && state->dirty && state->parameters[0]==3 && slot_writes==1,"later still-view entry preserves unsaved RAM preview");
    unsigned char gray=0;
    typedef int(*GetGray)(void *,unsigned char *);
#ifdef A7_FL_SPATIAL_SETTINGS_ONLY
    const int chosen_enum[]={1,3,7},chosen_value[]={-2,4,7},max_enum[]={6,4,9};
    uint8_t color_before[1280];bytes(color_before,data_guarded+1,1280);
    for(unsigned i=0;i<3;i++) {
        int id=0x7006+(int)i;
        test(((GetGray)0x40682d0b)(look_row(look,6+i),&gray)==0,"spatial menu row enabled");
        for(int e=0;e<=max_enum[i];e++)
            test(set_value(id,e)==1 && get_value(id,&value)==1 && value==e,"spatial option adjustable");
        test(set_value(id,chosen_enum[i])==1 && state->parameters[5+i]==chosen_value[i] &&
             set_value(id,-1)==0 && set_value(id,max_enum[i]+1)==0 && state->parameters[5+i]==chosen_value[i],
             "spatial menu enforces valid ranges");
    }
    test(slot_writes==1 && write_calls==writes_before && same(color_before,data_guarded+1,1280),"spatial edits never write LUT or persist before Save");
#else
    test(((GetGray)0x40682d0b)(look_row(look,6),&gray)==1 && set_value(0x7006,4)==0,"unsupported sharpness visible gray and write rejected");
    test(set_value(0x7007,2)==0 && set_value(0x7008,1)==0,"range and clarity reject");
#endif
    event_ok=0;test(a7_fl_confirm()==A7_FL_MODULE_EVENT && slot_writes==1,"unproven confirmation cannot persist");event_ok=1;
    *(uint32_t *)(action_view+0x130)=1;*(uintptr_t *)(action_view+0x150)=(uintptr_t)manager_words;*(int *)(action_view+0x158)=7;
    action_selected=look_row(look,9);original_action(action_view);
#ifdef A7_FL_SAVE_DIALOG
    test(slot_writes==1&&state->dirty&&dialog_commit,"Save opens dialog without durable write");
    dialog_commit=0;
    test(slot_writes==1&&state->dirty&&state->parameters[0]==3,"dialog cancel retains unsaved preview");
    original_action(action_view);
    test(confirm_dialog()==0&&confirm_dialog()!=0,"confirm callback persists once");
    action_flags--; /* two menu actions, one commit */
#endif
    test(slot_writes==2 && state->generation==2 && !state->dirty && action_flags==1 && action_fallbacks==0 && stock_actions==0,"original native Save action persists once");
    test(row_title(look,9)==0x0204ef85,"successful durable Save visibly becomes Complete");
#ifdef A7_FL_PREVIEW_REFRESH
    preview_error=A7_FL_PREVIEW_PIN;original_action(action_view);
    test(confirm_dialog()==A7_FL_PREVIEW_PIN&&row_title(look,9)==0x0204ef87&&slot_writes==2&&!state->dirty,"failed replay does not claim Complete or duplicate durable write");
    preview_error=0;original_action(action_view);
    test(confirm_dialog()==0&&row_title(look,9)==0x0204ef85&&slot_writes==2,"Save retries replay without changing settings");
#endif
#ifdef A7_FL_SPATIAL_SETTINGS_ONLY
    struct a7_fl_preference stored_recipe;
    test(a7_fl_preference_choose(&stored_recipe,slot_bytes[0],128,slot_bytes[1],128,a7_pkg_original_sha,a7_pkg_build)>=0 &&
         stored_recipe.generation==2 && write_calls==writes_before && same(color_before,data_guarded+1,1280),"Save stores only preference; active LUT unchanged");
    for(unsigned i=0;i<3;i++)
        test(stored_recipe.parameters[5+i]==chosen_value[i],"saved slot has exact spatial values");
    test(set_value(0x7008,9)==1 && a7_fl_cancel()==0 && get_value(0x7008,&value)==1 &&
         value==7 && slot_writes==2 && write_calls==writes_before,"cancel restores saved spatial cursor without writing");
#endif
#ifdef A7_FL_PREVIEW_REFRESH
    unsigned before_replay=preview_requests;
    preview_error=A7_FL_PREVIEW_READ;
    test(set_value(0x7001,13)==1&&state->parameters[0]==4&&state->last_error==A7_FL_PREVIEW_READ&&preview_requests==before_replay+1,"failed replay retains accepted scalar and exposes error");
    preview_error=0;test(a7_fl_cancel()==0&&state->parameters[0]==3&&preview_requests==before_replay+2,"cancel restores LUT then replays original active style");
#endif
    uint8_t committed[1280];bytes(committed,data_guarded+1,1280);
    test(set_value(0x7001,6)==1 && state->parameters[0]==-3 && a7_fl_cancel()==0 && get_value(0x7001,&value)==1 && value==12 && same(data_guarded+1,committed,1280) && slot_writes==2,"cancel restores committed signed LUT and native enum cursor state");
#ifdef A7_FL_CAPTURE_CONTROLS
    test(capture_matches(1),"cancel restores dynamic CAP recipe with same enabled state");
    for(unsigned f=1;f<5;f++) {
        test(set_value(0x7001+(int)f,5)==1&&capture_matches(1),"each color slider dispatch changes expected CAP source");
        test(a7_fl_cancel()==0&&capture_matches(1),"each color slider cancels back to committed CAP source");
    }
#endif
    test(set_value(0x7001,8)==1 && get_value(0x7001,&value)==1 && value==8 && state->parameters[0]==-1 && a7_fl_cancel()==0,"backend minus one is representable without missing-value sentinel");
    test(set_value(0x7002,13)==1 && state->parameters[1]==4,"highlight enum preview");slot_failed=1;
    test(row_title(look,9)==0x0204eaab,"editing restores Save label");
    original_action(action_view);
#ifdef A7_FL_SAVE_DIALOG
    test(confirm_dialog()==A7_FL_CONTROL_PERSIST,"dialog commit reports storage failure");
#endif
    test(state->last_error==A7_FL_CONTROL_PERSIST && state->dirty && state->generation==2 && row_title(look,9)==0x0204ef87,"failed native Save shows Not Complete and retains unsaved state");slot_failed=0;
    original_action(action_view);
#ifdef A7_FL_SAVE_DIALOG
    test(confirm_dialog()==0,"new confirmation retries failed save");
#endif
    test(slot_writes==3 && state->generation==3 && row_title(look,9)==0x0204ef85,"native Save retry visibly succeeds");
#ifdef A7_FL_DUAL_LOOK
    uint8_t original_fl[3][1280];
    bytes(original_fl[0],data_guarded+1,1280);
    bytes(original_fl[1],other_tables_data[0],1280);
    bytes(original_fl[2],other_tables_data[1],1280);
    NativeAdjustNode *mode_row=(NativeAdjustNode *)look_row(look,0);
    int cinema_label=0;
    test(mode_row->count==A7_FL_PRESET_MAX+1 &&
         ((int(*)(void *,int,int *))0x40683297)(mode_row->children[2],0,&cinema_label)==1 &&
         cinema_label==
#ifdef A7_FL_LOOK_BANKS
         0x0204fda8
#else
         0x0204eceb
#endif
         ,"third native option has the expected resource");
    unsigned before_cinema=preview_requests;
#ifdef A7_FL_LOOK_BANKS
    int fl_parameters[8];for(unsigned i=0;i<8;i++)fl_parameters[i]=state->parameters[i];
#endif
    test(set_value(0x7000,2)==1&&state->mode==2&&state->dirty&&slot_writes==3&&
         get_value(0x7000,&value)==1&&value==2&&capture_matches(2)&&preview_requests==before_cinema+1,
         "FL to Cinema updates three tables and requests refresh with no save");
#ifdef A7_FL_LOOK_BANKS
    for(unsigned i=0;i<8;i++)test(state->parameters[i]==(i==6?3:0),"FL2 starts with independent defaults");
#endif
    test(!same(data_guarded+1,original_fl[0],1215) &&
         !same(other_tables_data[0],original_fl[1],1215) &&
         !same(other_tables_data[1],original_fl[2],1215),"Cinema differs in preview and both CAP tables");
    test(a7_fl_cancel()==0&&state->mode==1&&!state->dirty&&slot_writes==3&&
         same(data_guarded+1,original_fl[0],1280)&&same(other_tables_data[0],original_fl[1],1280)&&
         same(other_tables_data[1],original_fl[2],1280),"cancel restores the exact original FL bytes");
    test(set_value(0x7000,2)==1&&set_value(0x7001,18)==1&&capture_matches(2),"Cinema shares working color controls");
    original_action(action_view);
    test(confirm_dialog()==0&&slot_writes==4&&!state->dirty&&row_title(look,9)==0x0204ef85,"confirmed Cinema saves and refreshes feedback");
    struct a7_fl_preference saved_cinema;
    test(a7_fl_preference_choose(&saved_cinema,slot_bytes[0],128,slot_bytes[1],128,a7_pkg_original_sha,a7_pkg_build)>=0&&
        saved_cinema.enabled==2&&saved_cinema.candidate_crc==a7_fl_crc(data_guarded+1,1280),"durable Cinema enum and candidate CRC");
    test(set_value(0x7000,1)==1&&a7_fl_cancel()==0&&state->mode==2&&capture_matches(2),"cancel restores committed Cinema");
#ifdef A7_FL_LOOK_BANKS
    test(saved_cinema.schema==
#ifdef A7_FL_LEICA_LOOK
        3
#else
        2
#endif
        ,"saved two-bank schema");
    for(unsigned i=0;i<8;i++)test(saved_cinema.other_parameters[i]==fl_parameters[i],"FL bank preserved in FL2 save");
    test(set_value(0x7000,1)==1&&capture_matches(1),"return FL applies its own controls");
    for(unsigned i=0;i<8;i++)test(state->parameters[i]==fl_parameters[i],"FL controls restored without reset");
    test(set_value(0x7000,0)==1&&set_value(0x7000,2)==1&&state->parameters[0]==9&&capture_matches(2),"Off roundtrip retains FL2 controls");
    test(a7_fl_cancel()==0&&!state->dirty,"bank switching cancel restores committed FL2");
    put("NATIVE_FL_LOOK_BANKS_PASSED\n");
#endif
#ifdef A7_FL_LEICA_LOOK
    int fl2_parameters[8];for(unsigned i=0;i<8;i++)fl2_parameters[i]=state->parameters[i];
    test(((int(*)(void *,int,int *))0x40683297)(mode_row->children[3],0,&cinema_label)==1&&cinema_label==0x0204fda9,"FL3 resource bound to fourth leaf");
    test(set_value(0x7000,3)==1&&state->mode==3&&capture_matches(3),"FL3 preview and JPEG apply");
    for(unsigned i=0;i<8;i++)test(state->parameters[i]==(i==6?3:0),"FL3 independent defaults");
    test(set_value(0x7001,11)==1&&set_value(0x7004,3)==1&&capture_matches(3),"FL3 contrast/fade update image tables");
    test(a7_fl_cancel()==0&&state->mode==2&&capture_matches(2),"cancel FL3 returns prior FL2");
    test(set_value(0x7000,3)==1&&set_value(0x7001,11)==1&&a7_fl_confirm()==0,"FL3 confirm persists third bank");
    struct a7_fl_preference three;
    test(a7_fl_preference_choose(&three,slot_bytes[0],128,slot_bytes[1],128,a7_pkg_original_sha,a7_pkg_build)>=0&&three.schema==3&&three.enabled==3&&three.parameters[0]==2,"third bank durable record");
    for(unsigned i=0;i<8;i++)test(three.other_parameters[i]==fl_parameters[i]&&three.third_parameters[i]==fl2_parameters[i],"both previous looks preserved by third save");
    test(set_value(0x7000,1)==1&&capture_matches(1),"FL restored from FL3");
    for(unsigned i=0;i<8;i++)test(state->parameters[i]==fl_parameters[i],"FL untouched");
    test(set_value(0x7000,2)==1&&capture_matches(2),"FL2 restored from FL");
    for(unsigned i=0;i<8;i++)test(state->parameters[i]==fl2_parameters[i],"FL2 untouched");
    test(set_value(0x7000,3)==1&&state->parameters[0]==2&&a7_fl_cancel()==0&&!state->dirty&&capture_matches(3),"all-bank roundtrip exact");
    put("NATIVE_FL3_LEICA_PASSED\n");
#endif
    put("NATIVE_FL_DUAL_LOOK_PASSED\n");
#endif
    test(set_value(0x7000,0)==1 && a7_fl_confirm()==0 && same(data_guarded+1,ORIGINAL,1280) && state->mode==0,"Off restores original and records Off preference");
#ifdef A7_FL_CAPTURE_LOOK
    test(capture_matches(0),"Off exactly restores stock in both CAP properties");
    write_calls=0;failure=6;
    test(set_value(0x7000,1)==0 && state->fault && state->mode==0 && write_calls==3 &&
         capture_matches(0) && same(data_guarded+1,ORIGINAL,1280),"failed second CAP write restores first and rejects FL toggle");
    failure=0;
    put("NATIVE_FL_CAPTURE_MODULE_PASSED\n");
#endif
    test(a7_fl_uninstall()==0 && parent.count==6 && parent.children==parent_children && parent.children[3]->index==4 && manager_words[0]==(uintptr_t)(manager_vtable_words+2),"uninstall restores native parent model and stock indices");
    test(saves==0,"module never requests calibration sync");
#ifdef A7_FL_PREVIEW_REFRESH
    put("NATIVE_FL_PREVIEW_INTEGRATION_PASSED: accepted color updates, save retry, cancel and early-boot isolation; downstream model mocked\n");
#endif
    put("NATIVE_FL_MODULE_PASSED: original nodes + 618 stock routes + runtime421checks; integrated preview/commit/cancel/store/rollback\n");
    put("PLATFORM_AND_FILESYSTEM_MODELED; NO_CAMERA_ACTIVATION_OR_NATIVE_RENDERER_TEST\n");finish();
}
