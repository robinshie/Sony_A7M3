/* Execute the production inspector against fixed ARM mappings and the actual
 * pinned Sony dlsym PLT. Only OS allocation/maps and dlsym itself are mocked. */
#include <stdint.h>
#include "yc-trace-pins.h"
#define OBJ 0x200000u
#define FLOW 0x1800000u
#define HEAP 0x2400000u
#define ORIGINAL (FLOW+A7YC_ORIGINAL+1)
static struct {char maps[2048];long maps_n;} report;
static unsigned checks,cases,lookups,allocations,releases,lookup_mode,allocation_fail,protect_fail,slot_race,bad_version;
static unsigned action;
static uint32_t *const import_slot=(void*)(OBJ+A7YC_SLOT);
static void put(const char*s){volatile uint32_t*u=(void*)0x10009000;while(*s){while(u[6]&32){}u[0]=*s++;}}
static void number(unsigned n){char b[12];unsigned i=0;do{b[i++]=(char)('0'+n%10);n/=10;}while(n);while(i){char s[2]={b[--i],0};put(s);}}
static void stop(void){register unsigned r0 __asm__("r0")=0x18,r1 __asm__("r1")=0x20026;__asm__ volatile("svc 0x123456":"+r"(r0),"+r"(r1)::"memory");while(1){}}
static void check(int ok){checks++;if(!ok){put("FAIL YC_PROBE case=");number(cases);put(" checks=");number(checks);put("\n");stop();}}
static unsigned length(const char*s){unsigned n=0;while(s[n])n++;return n;}
static int equal(const char*a,const char*b){while(*a&&*a==*b){a++;b++;}return *a==*b;}
static uint32_t hex(const char**s){uint32_t v=0;while(1){unsigned c=(unsigned char)**s;if(c>='0'&&c<='9')c-='0';else if(c>='a'&&c<='f')c=c-'a'+10;else return v;v=v*16+c;(*s)++;}}
static int contains(const char*s,const char*needle){for(;*s&&*s!='\n';s++){const char*a=s,*b=needle;while(*b&&*a==*b){a++;b++;}if(!*b)return 1;}return 0;}
static int readable(uint32_t a,unsigned n){return n<=UINT32_MAX-a&&((a>=OBJ&&a+n<=0x1500000)||(a>=FLOW&&a+n<=0x2200000)||(a>=HEAP&&a+n<=HEAP+16384));}
static long read_proc(const char*path,char*out,long capacity){
 const char *s=equal(path,"/version.txt")?(bad_version?"wrong":"37114_13.2026020901"):
 "00200000-01400000 r-xp 00000000 00:00 1 /usr/lib/libObj.so\n"
 "01400000-01500000 rw-p 01200000 00:00 1 /usr/lib/libObj.so\n"
 "01800000-02200000 r-xp 00000000 00:00 2 " A7YC_TARGET_PATH "\n"
 "02400000-02401000 r-xp 00000000 00:00 0\n"
 "02401000-02404000 rw-p 00000000 00:00 0\n";
 unsigned n=length(s);check(n<(unsigned)capacity);for(unsigned i=0;i<n;i++)out[i]=s[i];return n;
}
static long allocate(void){allocations++;return allocation_fail?-12L:(long)HEAP;}
static long sc3(long nr,long a,long b,long c){(void)a;(void)b;(void)c;
 if(nr==91){releases++;return 0;}if(nr==125){if(slot_race)*import_slot=0x12345678;return protect_fail?-1:0;}check(nr==0xf0002);return 0;
}
static void *lookup(void*h,const char*name){lookups++;check(h==0&&equal(name,A7YC_SYMBOL));
 if(lookup_mode==1)return 0;if(lookup_mode==2)return(void*)(ORIGINAL+2);
 if(lookup_mode==3)*import_slot=0x12345678;if(lookup_mode==4)*import_slot=ORIGINAL;
 return(void*)ORIGINAL;
}
#define A7YC_PROBE_TEST
#define ACTION action
/* Pins already included above. Suppress their second inclusion. */
#include "yc_trace_probe.c"
static void reset(unsigned lazy){
 for(unsigned i=0;i<sizeof result;i++)((unsigned char*)&result)[i]=0;
 for(unsigned i=0;i<16384;i++)((unsigned char*)HEAP)[i]=0;
 copy((void*)OBJ,object_header,sizeof object_header);copy((void*)FLOW,flow_header,sizeof flow_header);
 copy((void*)(FLOW+A7YC_ORIGINAL),original_pin,sizeof original_pin);
 copy((void*)(OBJ+A7YC_LAZY),lazy_pin,sizeof lazy_pin);
 copy((void*)(OBJ+A7YC_DLSYM),dlsym_pin,sizeof dlsym_pin);
 *(uint32_t*)(OBJ+0x126c750)=(uintptr_t)lookup;
 *import_slot=lazy?OBJ+A7YC_LAZY:ORIGINAL;
 lookups=allocations=releases=lookup_mode=allocation_fail=protect_fail=slot_race=bad_version=0;action=1;cases++;
}
void guest_main(void){
 struct Trace *state=(void*)(HEAP+4096);
 reset(0);check(inspect()==-6&&lookups==0&&allocations==0&&*import_slot==ORIGINAL);
 reset(1);check(inspect()==-6&&lookups==1&&allocations==0&&*import_slot==OBJ+A7YC_LAZY);
 for(unsigned mode=1;mode<=2;mode++){reset(1);lookup_mode=mode;check(inspect()==-15&&allocations==0&&*import_slot==OBJ+A7YC_LAZY);}
 reset(1);lookup_mode=3;check(inspect()==-16&&allocations==0&&*import_slot==0x12345678);
 reset(1);lookup_mode=4;check(inspect()==-6&&allocations==0&&*import_slot==ORIGINAL);
 reset(0);*import_slot=0x12345678;check(inspect()==-10&&allocations==0);
 for(unsigned lazy=0;lazy<=1;lazy++){
  reset(lazy);action=0;check(inspect()==1&&allocations==1&&*import_slot==HEAP&&state->original==ORIGINAL);
  check(state->restore_slot==(lazy?OBJ+A7YC_LAZY:ORIGINAL)&&state->armed==1&&state->version==3);
  action=1;check(inspect()==1&&*import_slot==HEAP&&state->lock==0);
  state->lock=1;check(inspect()==-14&&state->armed==1&&*import_slot==HEAP);
  action=2;check(inspect()==-14&&state->armed==0&&*import_slot==HEAP);
  state->lock=0;check(inspect()==2&&state->armed==0&&state->lock==0);
  check(*import_slot==(lazy?OBJ+A7YC_LAZY:ORIGINAL)&&releases==0);
 }
 reset(1);action=0;check(inspect()==1);state->restore_slot=0x12345678;action=2;check(inspect()==-12&&*import_slot==HEAP&&state->armed==1);
 reset(1);action=0;check(inspect()==1);state->version=2;action=2;check(inspect()==-12&&*import_slot==HEAP);
 reset(0);action=0;check(inspect()==1);*(unsigned char*)HEAP^=1;action=2;check(inspect()==-11&&*import_slot==HEAP);
 reset(1);action=0;slot_race=1;check(inspect()==-9&&releases==1&&*import_slot==0x12345678);
 reset(1);action=0;allocation_fail=1;check(inspect()==-7&&releases==0&&*import_slot==OBJ+A7YC_LAZY);
 reset(1);action=0;protect_fail=1;check(inspect()==-8&&releases==1&&*import_slot==OBJ+A7YC_LAZY);
 reset(1);*(unsigned char*)(OBJ+A7YC_DLSYM)^=1;check(inspect()==-4&&lookups==0&&allocations==0);
 reset(1);*(unsigned char*)(OBJ+A7YC_LAZY)^=1;check(inspect()==-4&&lookups==0&&allocations==0);
 reset(1);*(unsigned char*)(FLOW+A7YC_ORIGINAL)^=1;check(inspect()==-4&&lookups==0&&allocations==0);
 reset(1);bad_version=1;check(inspect()==-1&&lookups==0&&allocations==0);
 put("YC_TRACE_PROBE_PASSED cases=");number(cases);put(" checks=");number(checks);put("\n");stop();
}
