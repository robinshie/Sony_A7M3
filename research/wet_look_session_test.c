/* Test persistent wet flags against the real catalog/dual-slot/session code. */
#define main legacy_session_main
#include "custom_look_session_test.c"
#undef main
static unsigned wet_seen;
static int wet_apply(void*c,const struct a7_fl_preference*b,struct a7_fl_preference*a,const struct a7_custom_catalog*k){
 int rc=apply(c,b,a);if(!rc)wet_seen=a7_custom_wet_value(k,a->enabled);return rc;
}
int main(void){
 struct a7_custom_io io={readslot,replace,0};struct a7_custom_engine engine={apply,0,wet_apply};
 struct a7_fl_preference builtin={.schema=6,.enabled=1,.generation=72};
 builtin.parameters[0]=8;builtin.parameters[6]=3;builtin.film[5][0]=1;
 struct a7_fl_preference original=builtin;struct a7_custom_session s,reboot;
 assert(!a7_custom_session_open(&s,&io,&engine,&builtin));
 assert(!a7_custom_session_import(&s,recipe,sizeof recipe-1));
 struct a7_custom_look preserved=s.saved.looks[0];
 assert(!a7_custom_wet_install(&s)&&s.saved.count==2&&s.saved.wet_initialized&&!s.saved.wet_builtin);
 assert(!memcmp(&preserved,&s.saved.looks[0],sizeof preserved));
 assert(!memcmp(&s.builtin,&original,sizeof original));
 unsigned installed_writes=writes;
 assert(!a7_custom_wet_install(&s)&&writes==installed_writes);
 for(unsigned mode=1;mode<=6;mode++){
  assert(!a7_custom_wet_value(&s.working,mode));
  builtin.enabled=mode;
  assert(!a7_custom_session_open(&s,&io,&engine,&builtin)&&!wet_seen);
  assert(!a7_custom_wet_edit(&s,mode,1)&&wet_seen);
  for(unsigned other=mode+1;other<=6;other++)assert(!a7_custom_wet_value(&s.working,other));
  assert(!a7_custom_session_save(&s));
  assert(!a7_custom_session_open(&reboot,&io,&engine,&builtin)&&wet_seen);
  assert(!memcmp(&reboot.builtin,&builtin,sizeof builtin));
 }
 assert(s.saved.wet_builtin==63);
 assert(!a7_custom_session_select(&s,8)&&wet_seen);
 assert(a7_custom_wet_edit(&s,1,0)<0&&wet_seen);
 assert(!a7_custom_session_save(&s));
 assert(!a7_custom_session_open(&reboot,&io,&engine,&builtin)&&reboot.saved.active==8&&wet_seen);
 assert(!strcmp(reboot.saved.looks[1].name,"FL7 湿版黑白"));
 assert(!a7_custom_session_select(&reboot,7)&&!wet_seen); /* imported recipe independent of base FL6 flag */
 fail_apply=1;assert(a7_custom_wet_edit(&reboot,6,1)<0&&!wet_seen&&!reboot.working.looks[0].wet);fail_apply=0;
 assert(!a7_custom_wet_edit(&reboot,6,1)&&wet_seen);
 assert(!a7_custom_session_cancel(&reboot)&&wet_seen&&reboot.working.active==8);
 assert(!a7_custom_session_delete(&reboot,8));
 assert(!a7_custom_session_open(&s,&io,&engine,&builtin));
 installed_writes=writes;assert(!a7_custom_wet_install(&s)&&writes==installed_writes&&s.saved.count==1);
 assert(!memcmp(&preserved,&s.saved.looks[0],sizeof preserved));
 /* Rejection of unknown bits and legacy serialization stays canonical. */
 unsigned char raw[A7_CUSTOM_RECORD_BYTES];struct a7_custom_catalog c=s.saved,decoded;
 assert(!a7_custom_encode(&c,raw)&&raw[8]==3&&!a7_custom_decode(raw,sizeof raw,&decoded));
 c.wet_builtin=64;assert(a7_custom_encode(&c,raw)<0);
 puts("WET_SESSION_PASSED: six independent default-off flags, FL7 always-on, old banks unchanged, save/cold boot/cancel/failure/deletion");
 return 0;
}
