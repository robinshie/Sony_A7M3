#include "a7-fl-inspect.h"
#include "a7-fl-inspect-pins.h"
#define VB 0x40000000u
#define MB 0x60000000u
static unsigned checks,opens,symbols,closes,copy_calls,flags_seen;
static int loaded=1,missing_symbol,wrong_symbol,close_failure,copy_changes,version_bad,map_mode;
static const char *streams[5];static unsigned position[5];
static struct a7_fl_bootstrap_report *boot;
static struct a7_fl_module_status *runtime;
static struct a7_fl_inspect_report out;
static void put(const char*s){volatile unsigned*u=(volatile unsigned*)0x09000000;while(*s){while(u[6]&32){}u[0]=*s++;}}
static void number(unsigned n){char b[12];unsigned i=0;do{b[i++]=(char)('0'+n%10);n/=10;}while(n);while(i){char s[2]={b[--i],0};put(s);}}
static void finish(void){register unsigned r0 __asm__("r0")=0x18;register unsigned r1 __asm__("r1")=0x20026;__asm__ volatile("svc 0x123456":"+r"(r0),"+r"(r1)::"memory");while(1){}}
static void check(int ok,const char*s){checks++;if(!ok){put("FAIL ");put(s);put(" check=");number(checks);put("\n");finish();}}
static int equal(const char*a,const char*b){while(*a&&*a==*b){a++;b++;}return *a==*b;}
static int same(const void*a,const void*b,unsigned n){for(unsigned i=0;i<n;i++)if(((const unsigned char*)a)[i]!=((const unsigned char*)b)[i])return 0;return 1;}
static const char maps_full[]=
 "40000000-40800000 r-xp 00000000 00:01 1 /usr/lib/viewUnified2.so\n"
 "40800000-40900000 rw-p 00800000 00:01 1 /usr/lib/viewUnified2.so\n"
 "60000000-60009000 r-xp 00000000 00:01 2 /usr/lib/a7fl.so\n"
 "60009000-6000a000 rw-p 00009000 00:01 2 /usr/lib/a7fl.so\n"
 "6000a000-60060000 rw-p 00000000 00:00 0\n";
static const char maps_absent[]=
 "40000000-40800000 r-xp 00000000 00:01 1 /usr/lib/viewUnified2.so\n"
 "40800000-40900000 rw-p 00800000 00:01 1 /usr/lib/viewUnified2.so\n";
static const char maps_no_data[]=
 "40000000-40800000 r-xp 00000000 00:01 1 /usr/lib/viewUnified2.so\n"
 "40800000-40900000 rw-p 00800000 00:01 1 /usr/lib/viewUnified2.so\n"
 "60000000-60009000 r-xp 00000000 00:01 2 /usr/lib/a7fl.so\n";
static const char maps_overlap[]=
 "40000000-40800000 r-xp 00000000 00:01 1 /usr/lib/viewUnified2.so\n"
 "40001000-40900000 rw-p 00800000 00:01 1 /usr/lib/viewUnified2.so\n";
long a7_fl_inspect_syscall(long n,long a,long b,long c){
 if(n==5){check(b==0x8000&&c==0,"read-only proc/version open flags");
  if(equal((const char*)a,"/version.txt")){streams[3]=version_bad?"bad":"37114_13.2026020901";position[3]=0;return 3;}
  check(equal((const char*)a,"/proc/self/maps"),"bounded path allowlist");
  streams[4]=map_mode==1?maps_absent:map_mode==2?maps_no_data:map_mode==3?maps_overlap:maps_full;position[4]=0;return 4;
 }
 if(n==3){check(a==3||a==4,"read fd");unsigned count=0;while(count<(unsigned)c&&streams[a][position[a]])((char*)b)[count++]=streams[a][position[a]++];return count;}
 if(n==6){check(a==3||a==4,"close readonly fd");return 0;}
 check(0,"no write, unlink, install or commit syscall in inspect read");return -1;
}
void *mock_dlopen(const char *path,int flags){opens++;flags_seen=(unsigned)flags;check(equal(path,"/usr/lib/a7fl.so")&&flags==6,"RTLD_NOW|NOLOAD exact");return loaded?(void*)0x1234:0;}
void *mock_dlsym(void*handle,const char *name){symbols++;check(handle==(void*)0x1234,"symbol handle");
 int is_boot=equal(name,"a7_fl_bootstrap_status");check(is_boot||equal(name,"a7_fl_status"),"only pure status exports");
 if(missing_symbol)return 0;
 return (void*)(MB+(is_boot?a7_inspect_boot_va:a7_inspect_runtime_va)+(wrong_symbol?4:0));
}
int mock_dlclose(void*handle){closes++;check(handle==(void*)0x1234,"balanced handle close");return close_failure?-1:0;}
void a7_fl_inspect_copy_hook(void){copy_calls++;if(copy_changes==2||(copy_changes==1&&copy_calls==1))runtime->generation++;}
static void reset(void){opens=symbols=closes=copy_calls=flags_seen=0;loaded=1;missing_symbol=wrong_symbol=close_failure=copy_changes=version_bad=map_mode=0;
 for(unsigned i=0;i<sizeof *boot;i++)((unsigned char*)boot)[i]=0;
 for(unsigned i=0;i<sizeof *runtime;i++)((unsigned char*)runtime)[i]=0;
 boot->version=1;boot->calls=9;boot->mode=1;boot->stage=9;boot->result=0;boot->ready=1;boot->view=VB;boot->caution=0x50000000;boot->backup=0x51000000;
 runtime->prepared=1;runtime->installed=1;runtime->parents=1;runtime->generation=3;runtime->runtime_ready=1;runtime->mode=1;runtime->parameters[0]=-3;runtime->parameters[3]=4;runtime->parameters[6]=1;
}
static void expected(int rc,const char*label){check(a7_fl_inspect_read(&out)==rc&&out.status==rc,label);check(out.magic==0x41374653&&out.version==1&&out.bootstrap_bytes==36&&out.runtime_bytes==68,"report ABI");}
void guest_main(void){
 boot=((struct a7_fl_bootstrap_report*(*)(void))(MB+a7_inspect_boot_va))();
 runtime=((struct a7_fl_module_status*(*)(void))(MB+a7_inspect_runtime_va))();
 check((uintptr_t)boot>=MB+a7_inspect_rw_begin&&(uintptr_t)runtime>=MB+a7_inspect_rw_begin,"actual compiled accessor pointers");
 reset();expected(1,"loaded success");check(opens==1&&symbols==2&&closes==1&&flags_seen==6,"lookup and reference balance");
 check(out.view_base==VB&&out.module_base==MB&&out.stable==1,"mapped identity");
 check(same(&out.bootstrap,boot,sizeof *boot)&&same(&out.runtime,runtime,sizeof *runtime),"exact native status data");
 reset();loaded=0;map_mode=1;expected(0,"unloaded never loaded by inspection");check(opens==1&&symbols==0&&closes==0,"absent reference balance");
 reset();loaded=0;expected(-3,"mapped but no-load failed");check(closes==0,"no invalid close");
 reset();version_bad=1;expected(-1,"wrong version");check(opens==0,"wrong version before loader call");
 reset();map_mode=3;expected(-1,"overlapping mappings rejected");check(opens==0,"bad maps before loader call");
 const unsigned offsets[3]={0x15d958,0x15c8dc,0x15bf38};
 for(unsigned i=0;i<3;i++)for(unsigned j=0;j<12;j++){
  reset();unsigned char*p=(unsigned char*)(VB+offsets[i]+j);*p^=1;expected(-2,"every PLT byte pinned");*p^=1;check(opens==0,"tampered PLT never called");
 }
 for(unsigned j=0;j<52;j++){
  reset();unsigned char*p=(unsigned char*)(MB+j);*p^=1;expected(-2,"every module ELF header byte pinned");*p^=1;check(closes==1&&symbols==0,"header rejection closes reference");
 }
 for(unsigned i=0;i<2;i++){
  unsigned va=i?a7_inspect_runtime_va:a7_inspect_boot_va,n=i?sizeof a7_inspect_runtime_code:sizeof a7_inspect_boot_code;
  for(unsigned j=0;j<n;j++){
   reset();unsigned char*p=(unsigned char*)(MB+va+j);*p^=1;expected(-2,"every actual accessor byte pinned");*p^=1;check(closes==1&&symbols==0,"code rejection before symbol call");
  }
 }
 reset();missing_symbol=1;expected(-4,"missing symbol");check(closes==1&&symbols==2,"missing symbol reference balance");
 reset();wrong_symbol=1;expected(-4,"wrong function pointer");check(closes==1,"wrong symbol reference balance");
 reset();map_mode=2;expected(-5,"status data outside readable maps");check(closes==1,"pointer rejection reference balance");
 reset();copy_changes=2;expected(-6,"unstable status rejected");check(copy_calls==3&&closes==1&&out.stable==0,"bounded stable copy retries");
 reset();copy_changes=1;expected(1,"retry accepts stable snapshot");check(copy_calls==2&&out.runtime.generation==4&&closes==1,"snapshot after transient mutation");
 reset();close_failure=1;expected(-7,"close error is reported");check(closes==1&&out.dlclose_result==-1,"close only once");
 check(a7_fl_inspect_read(0)==-1,"null output rejection");
 put("NATIVE_INSPECT_PASSED checks=");number(checks);put("; original Sony PLTs and staged module accessors, absent module, exact pins, bounded map and symbol guards, stable copies, balanced refs; no camera\n");finish();
}
