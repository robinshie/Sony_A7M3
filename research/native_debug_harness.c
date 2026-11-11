#include "a7-fl-inspect.h"
#include "a7-fl-inspect-pins.h"
#include "a7-fl-debug-pins.h"
extern int a7_fl_debug_test_run(void);
extern const void *a7_fl_debug_test_report(void);
#define VB 0x40000000u
#define MB 0x60000000u
#define OB 0x50000000u
#define CB 0x54000000u
#define VM 0x52000000u
static unsigned checks,opens,syms,closes,position[5];static int absent;
static const char *streams[5];
static const char maps[]=
 "40000000-40800000 r-xp 00000000 00:01 1 /usr/lib/viewUnified2.so\n"
 "40800000-40c00000 rw-p 00800000 00:01 1 /usr/lib/viewUnified2.so\n"
 "50000000-51000000 r-xp 00000000 00:01 3 /usr/lib/libObj.so\n"
 "51000000-51400000 rw-p 01000000 00:01 3 /usr/lib/libObj.so\n"
 "52000000-52001000 rw-p 00000000 00:00 0\n"
 "54000000-55000000 r-xp 00000000 00:01 4 /usr/lib/CautionConfig.so\n"
 "55000000-56000000 rw-p 01000000 00:01 4 /usr/lib/CautionConfig.so\n"
 "60000000-60009000 r-xp 00000000 00:01 2 /usr/lib/a7fl.so\n"
 "60009000-60061000 rw-p 00009000 00:00 0\n";
static void put(const char*s){volatile unsigned*u=(volatile unsigned*)0x09000000;while(*s){while(u[6]&32){}u[0]=*s++;}}
static void number(unsigned n){char b[12];unsigned i=0;do{b[i++]=(char)('0'+n%10);n/=10;}while(n);while(i){char s[2]={b[--i],0};put(s);}}
static void finish(void){register unsigned r0 __asm__("r0")=0x18;register unsigned r1 __asm__("r1")=0x20026;__asm__ volatile("svc 0x123456":"+r"(r0),"+r"(r1)::"memory");while(1){}}
static void check(int ok,const char*s){checks++;if(!ok){put("FAIL ");put(s);put("\n");finish();}}
static int equal(const char*a,const char*b){while(*a&&*a==*b){a++;b++;}return *a==*b;}
static void zero(uintptr_t ptr,unsigned n){for(unsigned i=0;i<n;i++)((unsigned char*)ptr)[i]=0;}
long a7_fl_debug_syscall(long n,long a,long b,long c){
 if(n==5){check(b==0x8000&&c==0,"only read-only path opens");int fd=equal((const char*)a,"/version.txt")?3:4;
  check(fd==3||equal((const char*)a,"/proc/self/maps"),"path allowlist");streams[fd]=fd==3?"37114_13.2026020901":maps;position[fd]=0;return fd;}
 if(n==3){check(a==3||a==4,"read fd");unsigned i=0;while(i<(unsigned)c&&streams[a][position[a]])((char*)b)[i++]=streams[a][position[a]++];return i;}
 if(n==6){check(a==3||a==4,"close read-only fd");return 0;}
 check(0,"no mutation syscall");return -1;
}
void*mock_dlopen(const char*p,int flags){check(equal(p,"/usr/lib/a7fl.so")&&flags==6,"no-load only");opens++;return absent?0:(void*)123;}
void*mock_dlsym(void*h,const char*n){check(h==(void*)123,"lookup handle");syms++;int b=equal(n,"a7_fl_bootstrap_status");check(b||equal(n,"a7_fl_status"),"pure exports only");return(void*)(MB+(b?a7_inspect_boot_va:a7_inspect_runtime_va));}
int mock_dlclose(void*h){check(h==(void*)123,"close handle");closes++;return 0;}
static unsigned *boot=(void*)(MB+A7_DEBUG_BOOT_VA),*prefix=(void*)(MB+A7_DEBUG_MODULE_VA),*page=(void*)(VB+0xa6dfa4);
static void setup(void){
 zero(MB+A7_DEBUG_BOOT_VA,A7_DEBUG_BOOT_SIZE);zero(MB+A7_DEBUG_MODULE_VA,212);zero(VB+0xa6dfa4,40);
 boot[1]=1;boot[3]=1;boot[5]=VB;boot[6]=CB;boot[7]=0x57000000;boot[12]=3;
 boot[13]=VB;boot[14]=VB+0xc00000;boot[15]=VM;boot[16]=VM+0x1000;boot[17]=CB;boot[18]=CB+0x2000000;
 unsigned *p=(void*)((uintptr_t)boot+0x12034);p[0]=VB;p[1]=CB;p[3]=VB+0xa61c18;p[4]=VB+0x87f720;p[5]=CB+0x918ec8;
 for(unsigned i=0;i<35;i++)prefix[i+1]=p[i];
 prefix[36]=1;prefix[41]=1;prefix[42]=1;prefix[51]=1;
 struct a7_fl_bootstrap_report *diag=((struct a7_fl_bootstrap_report*(*)(void))(MB+a7_inspect_boot_va))();
 zero((uintptr_t)diag,sizeof *diag);diag->version=1;diag->calls=10;diag->mode=1;diag->stage=3;diag->ready=1;diag->view=VB;diag->caution=CB;diag->backup=0x57000000;
 *(unsigned*)(OB+A7_DEBUG_VM_GLOBAL)=VM;zero(VM,112);*(unsigned*)(VB+0xa61c18)=VB+0x87f720;
 page[0]=CB+0x918ec8;page[1]=VB+0x8f3214;page[2]=3;page[3]=VB+0xa725a0;page[4]=VB+0xa69c88;page[5]=3;page[7]=14;page[8]=14;
 for(unsigned i=0;i<3;i++){((unsigned*)(VB+0x8f3214))[i]=0x55000000+i*64;zero(0x55000000+i*64,40);}
}
void guest_main(void){
 setup();check(a7_fl_debug_test_run()==1,"debug success");const unsigned*r=a7_fl_debug_test_report();
 check(r[0]==0x41374644&&r[1]==1&&r[3]==66740&&r[4]==255&&r[5]==1,"debug ABI and full spans");
 check(r[146]==OB&&r[147]==OB+A7_DEBUG_VM_GLOBAL&&r[148]==VM,"actual libObj global and VM");
 const unsigned*c=r+277;check(c[1]&&c[2]&&c[4]&&c[6]&&c[7]&&c[8]&&c[10]&&c[11]&&c[13]&&c[14]&&c[15],"all actual warm guards pass");
 check(!c[12]&&!c[18]&&!c[19]&&!c[20],"warm and never configured VM identified");
 check(prefix[36]==1&&prefix[37]==0&&prefix[42]==1&&boot[11]==0,"private state unchanged");
 *(unsigned*)(OB+A7_DEBUG_VM_GLOBAL)=OB+0x1328000;check(a7_fl_debug_test_run()==1,"read excluded-map VM safely");r=a7_fl_debug_test_report();c=r+277;
 check(!c[1]&&!c[2]&&(r[4]&16),"readable libObj VM rejected by deployed allowlist");
 setup();page[7]=13;check(a7_fl_debug_test_run()==1,"inspect mismatched page without methods");c=(const unsigned*)a7_fl_debug_test_report()+277;check(!c[11]&&!c[12],"warm field mismatch pinpointed");
 setup();for(unsigned i=4;i<10;i++)page[i]=0;check(a7_fl_debug_test_run()==1,"cold profile snapshot");c=(const unsigned*)a7_fl_debug_test_report()+277;check(c[12]&&!c[11],"cold profile exact");
 setup();unsigned *p=(void*)((uintptr_t)boot+0x12034);p[2]=VM;check(a7_fl_debug_test_run()==1,"bootstrap VM captured before core configured");c=(const unsigned*)a7_fl_debug_test_report()+277;check(c[19]&&!c[18]&&!c[20],"configuration progress separated");
 prefix[3]=VM;boot[11]=VM;check(a7_fl_debug_test_run()==1,"all VM stages captured");c=(const unsigned*)a7_fl_debug_test_report()+277;check(c[18]&&c[19]&&c[20],"configuration complete witness");
 setup();page[1]=0x33000000;check(a7_fl_debug_test_run()==1,"foreign child pointer not dereferenced");r=a7_fl_debug_test_report();c=r+277;check(!(r[4]&128)&&!c[10]&&!c[13],"unreadable child array flagged");
 absent=1;check(a7_fl_debug_test_run()==-3,"absent handle fails without private dereference");check(opens==8&&closes==7&&syms==14,"all no-load refs balanced");
 put("NATIVE_DEBUG_PASSED checks=");number(checks);put("; private prefix snapshots, actual VM, page guards, original accessors, no mutations\n");finish();
}
