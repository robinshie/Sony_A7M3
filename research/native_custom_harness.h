#include "a7-fl-custom-store.h"
static unsigned char custom_disk[2][A7_CUSTOM_RECORD_BYTES];
static unsigned custom_sizes[2],custom_writes;
static int custom_exists[2];
static const char *(*custom_names)(uint32_t);
int a7_fl_dialog_names(uintptr_t view,void*manager,const char*(*name)(uint32_t)){
 check(view==0x40000000&&manager==process_element&&name,"custom name binding uses owned native menu");custom_names=name;return 0;
}
static int custom_read_slot(void*ctx,unsigned i,unsigned char*b,unsigned cap,unsigned*n){
 (void)ctx;check(i<2&&custom_sizes[i]<=cap,"bounded independent catalog read");*n=custom_sizes[i];bytes(b,custom_disk[i],*n);return custom_exists[i]?0:1;
}
static int custom_replace_slot(void*ctx,unsigned i,const unsigned char*before,unsigned n,int exists,const unsigned char*after,unsigned size){
 (void)ctx;check(i<2&&size==A7_CUSTOM_RECORD_BYTES&&exists==custom_exists[i]&&n==custom_sizes[i]&&same(before,custom_disk[i],n),"catalog exact independent preimage");
 bytes(custom_disk[i],after,size);custom_sizes[i]=size;custom_exists[i]=1;custom_writes++;return 0;
}
void a7_custom_posix_io(struct a7_custom_io*io){*io=(struct a7_custom_io){custom_read_slot,custom_replace_slot,0};}
static const char custom_recipe[]="{\"format\":\"A7FL-LOOK/1\",\"id\":\"portrait-grain\",\"name\":\"人像颗粒\",\"base\":\"FL6\",\"parameters\":{\"contrast\":4,\"highlights\":0,\"shadows\":0,\"fade\":0,\"saturation\":0,\"sharpness\":0,\"sharpness_range\":3,\"clarity\":0,\"grain\":7,\"halation\":-2,\"black\":0,\"curve_shadow\":0,\"midtone\":0,\"curve_highlight\":0,\"white\":0,\"vignette\":-6}}";
static unsigned custom_file_read(void*b,unsigned size,unsigned count,void*f){
 (void)f;check(size==1,"recipe read byte count");unsigned left=sizeof custom_recipe-1-sd_position;if(count>left)count=left;bytes(b,custom_recipe+sd_position,count);sd_position+=count;return count;
}
static int custom_file_eof(void*f){(void)f;return sd_position==sizeof custom_recipe-1;}
static int custom_file_error(void*f){return custom_file_eof(f)?8:0;}
int a7_fl_dialog_delete(uintptr_t view,void*manager,const char*name,int(*commit)(void)){
 check(view==0x40000000&&manager==process_element&&name&&name[0],"delete names owned look");dialog_commit=commit;return 0;
}
static void test_custom_flow(a7_menu_node*look){
 (void)sd_read;(void)sd_eof;(void)sd_error;
 struct a7_sd_api fs={sd_first,sd_next,sd_open,custom_file_read,sd_close,custom_file_eof,custom_file_error,sd_drive,sd_mounted};a7_fl_sd_test_api(&fs);
 unsigned initial=slot_writes;unsigned char original[2][128];bytes(original,slot_bytes,sizeof original);
 check(parent.count==8&&parent.children[3]==look&&look->count==4,"same-level import follows Creative Look");
 action_selected=parent.children[4];original_action(action_view);
 check(dialog_commit&&sd_file_count==1&&!custom_writes,"same-level action opens native file picker");
 check(!sd_select_callback(0)&&!confirm_dialog()&&custom_writes==1,"new recipe stored through confirm");
 check(look_row(look,0)->count==8,"native mode list grows to eight including Off");
 const char*name=custom_names(A7_FL_CUSTOM_TITLE_FIRST);check(name&&name[0]&&custom_names(A7_FL_CUSTOM_TITLE_FIRST+1)==0,"dynamic name belongs to imported slot only");
 check(slot_writes==initial&&same(original,slot_bytes,sizeof original),"import never overwrites original FL slots");
 check(set_value(0x7000,7),"select new mode via original process manager");
 int mode=-1;check(get_value(0x7000,&mode)&&mode==7,"native selected enum remains new slot, not base FL6");
 check(a7_fl_status()->parameters[0]==4&&capture_matches(6),"new controls reach original real preview/CAP generators");
 check(grain_selection==23&&halo_selection==-2&&vignette_selection==-6,"new spatial controls reach actual module adapter");
 action_selected=look_row(look,NATIVE_ADJUST_FIELDS+1);original_action(action_view);
 check(!confirm_dialog()&&custom_writes==2&&slot_writes==initial&&same(original,slot_bytes,sizeof original),"save new look exclusively in catalog");
 struct a7_custom_catalog saved;
 check(!a7_custom_decode(custom_disk[1],custom_sizes[1],&saved)&&saved.active==7&&saved.looks[0].values[0]==4,"new selected slot and controls persisted together");
 check(set_value(native_adjust_field_id(NATIVE_ADJUST_GRAIN_FIELD),3),"edit new grain through native controls");
 original_action(action_view);check(!confirm_dialog()&&custom_writes==3&&slot_writes==initial,"edit save remains independent");
 check(set_value(0x7000,6)&&get_value(0x7000,&mode)&&mode==6,"return to original FL6 keeps native selection aligned");
 check(a7_fl_status()->parameters[0]==-3&&grain_selection==22&&halo_selection==-2&&vignette_selection==8,"original FL6 values restored after custom look");
 check(same(original,slot_bytes,sizeof original)&&!a7_fl_status()->fault,"all original saved banks unchanged and runtime healthy");
 check(!a7_fl_confirm(),"save return to builtin before reselect");
 check(set_value(0x7000,7),"select imported look for delete");
 unsigned before_delete=custom_writes;
 action_selected=look->children[3]->children[0];original_action(action_view);
 check(custom_writes==before_delete,"opening delete never saves");
 check(!confirm_dialog()&&custom_writes==before_delete+1,"confirmed delete persists once");
 check(look_row(look,0)->count==7&&custom_names(A7_FL_CUSTOM_TITLE_FIRST)==0,"delete removes selector and dynamic name");
 check(a7_fl_status()->parameters[0]==-3&&!a7_fl_status()->dirty,"delete returns unchanged built-in processing");
 put("NATIVE_CUSTOM_DELETE_PASSED\n");
 put("NATIVE_CUSTOM_FLOW_PASSED\n");
}
