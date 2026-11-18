#define main legacy_session_main
#include "custom_look_session_test.c"
#undef main
int main(int argc,char**argv){
 assert(argc==3);
 for(unsigned i=0;i<2;i++){
  FILE*f=fopen(argv[i+1],"rb");assert(f);
  lengths[i]=(unsigned)fread(disk[i],1,sizeof disk[i],f);assert(lengths[i]==sizeof disk[i]&&fgetc(f)==EOF);fclose(f);present[i]=1;
 }
 struct a7_custom_io io={readslot,replace,0};struct a7_custom_engine engine={apply,0,0};
 struct a7_fl_preference builtin={.schema=6,.enabled=1,.generation=72};builtin.parameters[6]=3;
 struct a7_custom_session s,boot;
 assert(!a7_custom_session_open(&s,&io,&engine,&builtin));
 struct a7_custom_catalog old=s.saved;
 assert(!a7_custom_wet_install(&s)&&s.saved.count==old.count+1&&s.saved.generation==old.generation+1);
 assert(s.saved.active==old.active&&s.saved.hidden_builtin==old.hidden_builtin&&s.saved.wet_builtin==0);
 for(unsigned i=0;i<old.count;i++)assert(!memcmp(&s.saved.looks[i],&old.looks[i],sizeof old.looks[i]));
 assert(!a7_custom_session_open(&boot,&io,&engine,&builtin));
 assert(boot.saved.count==s.saved.count&&boot.saved.active==old.active&&boot.saved.wet_initialized);
 assert(!a7_custom_wet_value(&boot.saved,boot.effective.enabled));
 unsigned n=writes;assert(!a7_custom_wet_install(&boot)&&writes==n);
 printf("WET_ACTUAL_CATALOG_MIGRATION_PASSED old_count=%u new_count=%u active=%u hidden=%u unchanged_old_looks=%u\n",old.count,boot.saved.count,boot.saved.active,boot.saved.hidden_builtin,old.count);
 return 0;
}
