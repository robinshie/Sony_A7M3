static int wet_same_text(const char*a,const char*b){while(*a&&*a==*b){a++;b++;}return *a==*b;}
static void test_wet_flow(a7_menu_node*look){
 unsigned old_writes=custom_writes;int value=-1;
 check(look_row(look,0)->count==8,"FL7 is a separate eighth entry including Off");
 check(custom_names(A7_FL_CUSTOM_TITLE_FIRST)&&wet_same_text(custom_names(A7_FL_CUSTOM_TITLE_FIRST),"FL7 湿版黑白"),"FL7 native dynamic name");
 struct a7_fl_preference before,after;
 check(a7_fl_preference_choose(&before,slot_bytes[0],128,slot_bytes[1],128,a7_pkg_original_sha,a7_pkg_build)>=0,"snapshot existing six banks");
 int id=native_adjust_field_id(NATIVE_ADJUST_WET_FIELD);
 check(set_value(0x7000,1)&&!a7_fl_confirm(),"baseline builtin committed");
 int contrast=0;check(get_value(0x7001,&contrast),"read contrast before mixed edit");
 int changed=contrast==18?17:contrast+1;
 check(set_value(0x7001,changed)&&set_value(id,0)&&a7_fl_status()->dirty,"same wet value preserves unsaved color edit");
 check(set_value(id,1)&&wet_selection&&!a7_fl_cancel()&&get_value(0x7001,&value)&&value==contrast&&!wet_selection&&!a7_fl_status()->dirty,"mixed wet/color cancellation restores committed values");
 grain_fail_once=1;
 check(!set_value(id,1)&&get_value(id,&value)&&value==0&&!wet_selection&&!a7_fl_status()->fault,"failed wet backend write rolls back state");
 for(int mode=1;mode<=6;mode++){
  check(set_value(0x7000,mode)&&get_value(id,&value)&&value==0&&!wet_selection,"each old style defaults to color");
  check(set_value(id,1)&&get_value(id,&value)&&value==1&&wet_selection==1,"native switch reaches capture backend");
  check(!a7_fl_confirm(),"wet flag saved by camera commit path");
 }
 for(int mode=1;mode<=6;mode++)check(set_value(0x7000,mode)&&get_value(id,&value)&&value==1&&wet_selection,"six switches remain independent");
 check(a7_fl_preference_choose(&after,slot_bytes[0],128,slot_bytes[1],128,a7_pkg_original_sha,a7_pkg_build)>=0,"decode post-save settings");
 before.generation=after.generation;before.candidate_crc=after.candidate_crc;
 check(same(&before,&after,sizeof before),"wet edits preserve all six color/curve/spatial banks");
 check(set_value(0x7000,7)&&wet_selection&&get_value(id,&value)&&value==1,"FL7 forces capture monochrome");
 check(!set_value(id,0)&&wet_selection,"FL7 cannot silently become color");
 check(!a7_fl_confirm(),"selected FL7 durable save");
 struct a7_custom_catalog a,b,*latest;
 check(!a7_custom_decode(custom_disk[0],custom_sizes[0],&a)&&!a7_custom_decode(custom_disk[1],custom_sizes[1],&b),"both wet catalog slots valid");
 latest=a.generation>b.generation?&a:&b;
 check(latest->active==7&&latest->wet_builtin==63&&latest->wet_initialized&&custom_writes>old_writes,"selected FL7 and all wet flags persisted");
 check(set_value(0x7000,0)&&!wet_selection,"Off disables wet processing");
 put("NATIVE_WET_FLOW_PASSED\n");
}
