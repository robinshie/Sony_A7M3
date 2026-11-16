#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "a7-fl-custom-session.h"
static unsigned char disk[2][A7_CUSTOM_RECORD_BYTES];static unsigned lengths[2],writes,applies;static int present[2],fail_apply;
static struct a7_fl_preference applied;
static int readslot(void*c,unsigned i,unsigned char*b,unsigned cap,unsigned*n){(void)c;assert(i<2&&lengths[i]<=cap);*n=lengths[i];memcpy(b,disk[i],*n);return present[i]?0:1;}
static int replace(void*c,unsigned i,const unsigned char*before,unsigned n,int exists,const unsigned char*after,unsigned size){(void)c;assert(i<2&&exists==present[i]&&n==lengths[i]&&!memcmp(before,disk[i],n)&&size==A7_CUSTOM_RECORD_BYTES);memcpy(disk[i],after,size);lengths[i]=size;present[i]=1;writes++;return 0;}
static int apply(void*c,const struct a7_fl_preference*before,struct a7_fl_preference*after){
 (void)c;assert(before&&after);if(fail_apply)return -1;applied=*after;applies++;return 0;
}
static const unsigned char recipe[]="{\"format\":\"A7FL-LOOK/1\",\"id\":\"portrait-grain\",\"name\":\"人像颗粒\",\"base\":\"FL6\",\"parameters\":{\"contrast\":4,\"highlights\":2,\"shadows\":-3,\"fade\":1,\"saturation\":2,\"sharpness\":1,\"sharpness_range\":4,\"clarity\":2,\"grain\":7,\"halation\":-2,\"black\":1,\"curve_shadow\":2,\"midtone\":3,\"curve_highlight\":4,\"white\":5,\"vignette\":-6}}";
int main(void){
 struct a7_custom_io io={readslot,replace,0};struct a7_custom_engine engine={apply,0};
 struct a7_fl_preference builtin={.schema=6,.enabled=1,.generation=72};builtin.parameters[0]=8;builtin.parameters[6]=3;builtin.film[5][0]=1;
 struct a7_fl_preference original=builtin;struct a7_custom_session s,reboot;
 assert(!a7_custom_session_open(&s,&io,&engine,&builtin));
 assert(!a7_custom_session_import(&s,recipe,sizeof recipe-1)&&writes==1&&s.working.count==1);
 uint32_t slot;assert(!strcmp(a7_custom_session_name(&s,0,&slot),"人像颗粒")&&slot==7);
 assert(s.working.active==0&&!memcmp(&applied,&original,sizeof original));
 assert(!a7_custom_session_select(&s,7)&&s.dirty&&applied.enabled==6&&applied.parameters[0]==4&&applied.film[5][0]==7);
 assert(!a7_custom_session_edit(&s,8,3)&&applied.film[5][0]==3);
 assert(!a7_custom_session_save(&s)&&writes==2&&!s.dirty);
 assert(!a7_custom_session_open(&reboot,&io,&engine,&builtin)&&reboot.working.active==7&&applied.film[5][0]==3);
 assert(!strcmp(a7_custom_session_name(&reboot,0,&slot),"人像颗粒")&&slot==7);
 assert(a7_custom_session_import(&reboot,recipe,sizeof recipe-1)<0&&writes==2);
 fail_apply=1;assert(a7_custom_session_select(&reboot,0)<0&&reboot.working.active==7&&!reboot.dirty);fail_apply=0;
 assert(!a7_custom_session_edit(&reboot,8,5)&&applied.film[5][0]==5);
 assert(!a7_custom_session_cancel(&reboot)&&applied.film[5][0]==3&&!reboot.dirty);
 assert(!a7_custom_session_select(&reboot,0)&&!memcmp(&applied,&original,sizeof original));
 assert(!a7_custom_session_save(&reboot)&&writes==3);
 assert(!a7_custom_session_open(&s,&io,&engine,&builtin)&&!s.working.active&&!memcmp(&applied,&original,sizeof original));
 assert(!memcmp(&s.builtin,&original,sizeof original)&&!memcmp(&builtin,&original,sizeof original));
 unsigned char second[sizeof recipe];memcpy(second,recipe,sizeof recipe);
 unsigned char*id=(unsigned char*)strstr((char*)second,"portrait-grain");assert(id);id[0]='x';
 assert(!a7_custom_session_import(&s,second,sizeof second-1)&&s.saved.count==2);
 assert(!a7_custom_session_select(&s,7));
 unsigned before_delete=writes;fail_apply=1;
 assert(a7_custom_session_delete(&s,7)<0&&writes==before_delete&&s.saved.count==2);fail_apply=0;
 assert(a7_custom_session_delete(&s,6)<0&&writes==before_delete);
 assert(!a7_custom_session_delete(&s,7)&&s.saved.count==1&&s.saved.looks[0].slot==7&&s.saved.looks[0].id[0]=='x');
 assert(!memcmp(&builtin,&original,sizeof original)&&!memcmp(&s.builtin,&original,sizeof original));
 assert(!a7_custom_session_open(&reboot,&io,&engine,&builtin)&&reboot.saved.count==1&&!reboot.saved.active);
 assert(!a7_custom_session_select(&reboot,7)&&!a7_custom_session_delete(&reboot,7));
 assert(!a7_custom_session_open(&s,&io,&engine,&builtin)&&!s.saved.count&&s.saved.next_slot==7);
 assert(!a7_custom_session_import(&s,recipe,sizeof recipe-1)&&s.saved.looks[0].slot==7);

 unsigned built_writes=writes;
 fail_apply=1;assert(a7_custom_session_delete_builtin(&s,1)<0&&writes==built_writes&&!s.saved.hidden_builtin);fail_apply=0;
 assert(!a7_custom_session_delete_builtin(&s,1)&&s.saved.hidden_builtin==1&&s.effective.enabled==0);
 assert(!memcmp(&builtin,&original,sizeof original));
 assert(!a7_custom_session_open(&reboot,&io,&engine,&builtin)&&reboot.saved.hidden_builtin==1&&applied.enabled==0);
 for(unsigned mode=2;mode<=6;mode++){
  builtin.enabled=mode;
  assert(!a7_custom_session_open(&s,&io,&engine,&builtin));
  assert(!a7_custom_session_delete_builtin(&s,mode));
 }
 assert(!a7_custom_session_open(&reboot,&io,&engine,&builtin)&&reboot.saved.hidden_builtin==63&&applied.enabled==0);
 assert(!a7_custom_session_select(&reboot,7)&&applied.enabled==6);
 assert(!a7_custom_session_save(&reboot));
 assert(!a7_custom_session_open(&s,&io,&engine,&builtin)&&s.saved.active==7&&s.saved.hidden_builtin==63&&applied.enabled==6);
 puts("BUILTIN_DELETE_REBOOT_REIMPORT_PASSED");
 puts("CUSTOM_DELETE_REBOOT_PASSED");
 puts("CUSTOM_SESSION_FLOW_PASSED: import/name/select/edit/save/reopen/cancel/restore; original six banks unchanged; capture callback modeled");
}
