#include <stdint.h>
#include "a7-text-pages-pins.h"
extern int a7_text_test_read(void);extern const void*a7_text_test_report(void);
static unsigned checks,position[5],copy_calls;static int bad_version,map_mode,change;
static const char*streams[5];
static const char full[]="40000000-40600000 r-xp 00000000 00:01 1 /usr/lib/viewUnified2.so\n";
static const char absent[]="40000000-40600000 r-xp 00000000 00:01 1 /usr/lib/not-view.so\n";
static const char short_map[]="40000000-405b9000 r-xp 00000000 00:01 1 /usr/lib/viewUnified2.so\n";
static const char wrong_offset[]="40000000-40200000 r-xp 00000000 00:01 1 /usr/lib/viewUnified2.so\n40200000-40600000 r-xp 00100000 00:01 1 /usr/lib/viewUnified2.so\n";
static const char shared[]="40000000-40600000 r-xs 00000000 00:01 1 /usr/lib/viewUnified2.so\n";
static const char malformed[]="40000000-40600000 r-xp 00000000 00:01 1 /usr/lib/viewUnified2.so\n3fffffff-40000000 r-xp 00000000 00:01 1 /usr/lib/other.so\n";
static void put(const char*s){volatile unsigned*u=(volatile unsigned*)0x09000000;while(*s){while(u[6]&32){}u[0]=*s++;}}
static void number(unsigned n){char b[12];unsigned i=0;do{b[i++]=(char)('0'+n%10);n/=10;}while(n);while(i){char s[2]={b[--i],0};put(s);}}
static void finish(void){register unsigned r0 __asm__("r0")=0x18;register unsigned r1 __asm__("r1")=0x20026;__asm__ volatile("svc 0x123456":"+r"(r0),"+r"(r1)::"memory");while(1){}}
static void check(int ok,const char*s){checks++;if(!ok){put("FAIL ");put(s);put("\n");finish();}}
static int eq(const char*a,const char*b){while(*a&&*a==*b){a++;b++;}return *a==*b;}
long a7_text_syscall(long n,long a,long b,long c){
 if(n==5){check(b==0x8000&&c==0,"only readonly opens");int fd=eq((const char*)a,"/version.txt")?3:4;check(fd==3||eq((const char*)a,"/proc/self/maps"),"exact readonly path allowlist");
  streams[fd]=fd==3?(bad_version?"wrong":"37114_13.2026020901"):(map_mode==1?absent:map_mode==2?short_map:map_mode==3?wrong_offset:map_mode==4?shared:map_mode==5?malformed:full);position[fd]=0;return fd;
 }
 if(n==3){check(a==3||a==4,"read fd");unsigned i=0;while(i<(unsigned)c&&streams[a][position[a]])((char*)b)[i++]=streams[a][position[a]++];return i;}
 if(n==6){check(a==3||a==4,"close read fd");return 0;}
 check(0,"no loader/native/memory mutation syscall");return -1;
}
void a7_text_copy_hook(unsigned page,unsigned attempt){(void)attempt;copy_calls++;if(page==0&&(change==2||(change==1&&copy_calls==1)))((unsigned char*)0x40214000)[4095]^=1;}
void guest_main(void){
 for(unsigned i=0;i<sizeof a7_text_header;i++)((unsigned char*)0x40000000)[i]=a7_text_header[i];
 check(a7_text_test_read()==1,"all fixed pages captured");const unsigned*r=a7_text_test_report();
 check(r[0]==0x41375450&&r[1]==1&&r[3]==0x40000000&&r[5]==7&&r[6]==7,"report ABI and complete stable pages");
 static const uint32_t offsets[3]={0x214000,0x20d000,0x5b9000};
 for(unsigned p=0;p<3;p++){
  check(r[7+p*6]==offsets[p]&&r[8+p*6]==0x40000000+offsets[p]&&r[9+p*6]==0x40000000&&r[10+p*6]==0x40600000,"exact RX page provenance");
  const unsigned char *copy=(const unsigned char*)r+100+p*4096,*original=(void*)(0x40000000+offsets[p]);
  for(unsigned i=0;i<4096;i++)check(copy[i]==original[i],"entire native text page copied exactly");
 }
 bad_version=1;check(a7_text_test_read()==-1,"wrong firmware denied");bad_version=0;
 for(unsigned i=0;i<52;i++){((unsigned char*)0x40000000)[i]^=1;check(a7_text_test_read()==-3,"exact ELF identity pinned");((unsigned char*)0x40000000)[i]^=1;}
 map_mode=1;check(a7_text_test_read()==-2,"wrong path denied");
 map_mode=2;check(a7_text_test_read()==-12,"third page outside RX denied");r=a7_text_test_report();check(r[5]==3&&r[6]==3,"partial verified masks retained");
 map_mode=3;check(a7_text_test_read()==-10,"wrong file offset denied");
 map_mode=4;check(a7_text_test_read()==-2,"shared map denied");
 map_mode=5;check(a7_text_test_read()==-2,"out of order map denied");map_mode=0;
 change=2;copy_calls=0;check(a7_text_test_read()==-20,"unstable first page denied");r=a7_text_test_report();check(copy_calls==3&&r[5]==1&&r[6]==0,"bounded double copy retries");
 change=1;copy_calls=0;check(a7_text_test_read()==1,"single transient change accepted after retry");check(copy_calls==4,"only changed page retried");
 put("NATIVE_TEXT_PAGES_PASSED checks=");number(checks);put("; exact paths, private RX/file offsets, full native pages, stable copies; no native calls\n");finish();
}
