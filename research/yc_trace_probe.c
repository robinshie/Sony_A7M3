/* Temporary RAM-only import-slot instrumentation. No firmware, calibration or
 * pixel writes. Detach retains code/data until process exit for in-flight calls. */
#ifndef A7YC_PROBE_TEST
#define A7_RUNTIME_LIBRARY_ONLY
#include "a7-runtime-probe.c"
#endif
#include "yc-trace-pins.h"
#if A7YC_KIND >= 7
#include "dmm_observer.h"
__attribute__((visibility("hidden"))) void *memset(void *p,int value,unsigned n){uint8_t *d=p;while(n--)*d++=(uint8_t)value;return p;}
#endif
#ifndef ACTION
#define ACTION 0
#endif
struct Trace {uint32_t magic,version,original,lock,armed,count,dropped,maximum;
 uint32_t calls,failures,last_error,area,mode,restore_slot,reserved[2];uint32_t records[128][20];};
struct Result {uint32_t magic,version,action;int32_t status;uint32_t object_base,dataflow_base,code,state,slot,original;struct Trace trace;};
static struct Result result;
_Static_assert(sizeof(struct Trace)==10304,"trace ABI");
_Static_assert(sizeof(struct Result)==10344,"result ABI");
static int same(const void *a,const void *b,unsigned n){const volatile unsigned char *x=a;const unsigned char *y=b;for(unsigned i=0;i<n;i++)if(x[i]!=y[i])return 0;return 1;}
static void copy(void *a,const void *b,unsigned n){unsigned char *x=a;const volatile unsigned char *y=b;for(unsigned i=0;i<n;i++)x[i]=y[i];}
static int original_matches(uint32_t address,uint32_t load_base){
 for(unsigned i=0;i<sizeof original_pin;){unsigned relocated=0;
  for(unsigned j=0;j!=A7YC_RELOCATION_COUNT;j++)if(target_relocations[j]==i){
   uint32_t word=(uint32_t)original_pin[i]|((uint32_t)original_pin[i+1]<<8)|((uint32_t)original_pin[i+2]<<16)|((uint32_t)original_pin[i+3]<<24);
   if(*(volatile uint32_t*)(address+i)!=word+load_base)return 0;i+=4;relocated=1;break;
  }
  if(!relocated){if(*(volatile unsigned char*)(address+i)!=original_pin[i])return 0;i++;}
 }return 1;
}
static int exact(const char *a,const char *b){while(*b&&*a==*b){a++;b++;}return !*b&&(!*a||*a=='\n');}
struct Map {uint32_t lo,hi;const char *permissions,*name;};
static int parse(const char *p,struct Map *m){const char *q=p;m->lo=hex(&q);if(*q++!='-')return 0;m->hi=hex(&q);if(m->hi<=m->lo||*q++!=' ')return 0;m->permissions=q;
 for(unsigned field=0;field<4;field++){while(*q==' ')q++;while(*q&&*q!=' '&&*q!='\n')q++;}while(*q==' ')q++;m->name=q;return 1;}
static int range(uint32_t a,unsigned n,const char *permissions,int anonymous){
 if(!a||n>UINT32_MAX-a)return 0;
 for(const char *p=report.maps;*p;){struct Map m;if(!parse(p,&m))return 0;
  if(m.lo<=a&&a+n<=m.hi&&same(m.permissions,permissions,4)&&(!anonymous||!*m.name||*m.name=='\n'))return 1;
  while(*p&&*p!='\n')p++;if(*p)p++;
 }return 0;
}
static uint32_t base(const char *path){uint32_t found=0;for(const char *p=report.maps;*p;){struct Map m;if(!parse(p,&m))return 0;
 if(contains(p,"r-xp 00000000")&&exact(m.name,path)){if(found)return 0;found=m.lo;}
 while(*p&&*p!='\n')p++;if(*p)p++;
 }return found;}
#if A7YC_KIND >= 7 && !defined(A7YC_PROBE_TEST)
static int query_bind(struct a7_dmm_native *api){
 uint32_t biz=base("/usr/lib/libBizFw.so");if(!biz||!readable(biz,sizeof biz_header)||!same((void*)biz,biz_header,sizeof biz_header))return 0;
 for(unsigned i=0;i<sizeof dmm_pins/sizeof *dmm_pins;i++){
  const struct DmmPin *p=dmm_pins+i;if(biz>UINT32_MAX-p->offset-p->size||!readable(biz+p->offset,p->size)||!same((void*)(biz+p->offset),p->bytes,p->size))return 0;
 }
 api->construct=(void*)(biz+A7YC_DMM_CTOR);api->destroy=(void*)(biz+A7YC_DMM_DTOR);
 api->send=(void*)(biz+A7YC_DMM_SEND);api->receive=(void*)(biz+A7YC_DMM_RECEIVE);return 1;
}
#endif
#ifndef A7YC_PROBE_TEST
static long allocate(void){register long r7 __asm__("r7")=192,r0 __asm__("r0")=0,r1 __asm__("r1")=16384,r2 __asm__("r2")=3,r3 __asm__("r3")=0x22,r4 __asm__("r4")=-1,r5 __asm__("r5")=0;
 __asm__ volatile("svc #0":"+r"(r0):"r"(r7),"r"(r1),"r"(r2),"r"(r3),"r"(r4),"r"(r5):"memory","cc");return r0;}
#endif
static int inspect(void){
#ifdef A7YC_STOP_ONLY
 if(ACTION!=2)return -19;
#endif
 char version[24];static const char build[]="37114_13.2026020901";
 if(read_proc("/version.txt",version,sizeof version)!=(long)sizeof build-1||!same(version,build,sizeof build-1))return -1;
 report.maps_n=read_proc("/proc/self/maps",report.maps,sizeof report.maps-1);if(report.maps_n<=0)return -2;report.maps[report.maps_n]=0;
 uint32_t obj=base("/usr/lib/libObj.so"),flow=base(A7YC_TARGET_PATH);
 result.object_base=obj;result.dataflow_base=flow;
 if(!obj||!flow||obj>UINT32_MAX-A7YC_SLOT-4||flow>UINT32_MAX-A7YC_ORIGINAL-sizeof original_pin)return -3;
 if(!readable(obj,sizeof object_header)||!readable(flow,sizeof flow_header)||
    !same((void*)obj,object_header,sizeof object_header)||!same((void*)flow,flow_header,sizeof flow_header)||
    !readable(flow+A7YC_ORIGINAL,sizeof original_pin)||!original_matches(flow+A7YC_ORIGINAL,flow)||
    !readable(obj+A7YC_LAZY,sizeof lazy_pin)||!same((void*)(obj+A7YC_LAZY),lazy_pin,sizeof lazy_pin)||
    !readable(obj+A7YC_DLSYM,sizeof dlsym_pin)||!same((void*)(obj+A7YC_DLSYM),dlsym_pin,sizeof dlsym_pin))return -4;
 uint32_t *slot=(void*)(obj+A7YC_SLOT),original=flow+A7YC_ORIGINAL+1;
 result.slot=(uintptr_t)slot;result.original=original;
 if(!range((uintptr_t)slot,4,"rw-p",0))return -5;
 uint32_t current=__atomic_load_n(slot,__ATOMIC_ACQUIRE);struct Trace *state;
#if A7YC_KIND >= 7
 struct a7_dmm_native query_api;if(!query_bind(&query_api))return -17;
#endif
 /* Preserve the observed slot for diagnosing rejected lazy/interposed imports.
  * A nonzero code field alone never means an installed or executable hook. */
 result.code=current;
 if(current==obj+A7YC_LAZY){
  /* Validate the dynamic linker's result without invoking the image encoder
   * or changing its import slot. Unknown/interposed targets stay rejected. */
  void *(*lookup)(void*,const char*)=(void*)(obj+A7YC_DLSYM);
  if((uintptr_t)lookup(0,A7YC_SYMBOL)!=original)return -15;
  uint32_t observed=__atomic_load_n(slot,__ATOMIC_ACQUIRE);
  if(observed!=current&&observed!=original)return -16;
  current=observed;result.code=current;
 }
 if(current==original||current==obj+A7YC_LAZY){
  if(ACTION!=0)return -6;
  long allocation=allocate();if(!allocation||(uint32_t)allocation>=0xfffff001u)return -7;
  uint32_t code=(uint32_t)allocation;state=(void*)(code+4096);result.code=code;result.state=(uintptr_t)state;
  copy((void*)code,hook_code,sizeof hook_code);*(uint32_t*)(code+A7YC_STATE_LITERAL)=(uintptr_t)state;
  state->magic=0x41375943;state->version=9;state->original=original;state->maximum=128;state->armed=1;state->mode=A7YC_KIND;state->restore_slot=current;
#if A7YC_KIND >= 7
  struct a7_dmm_observer *o=(void*)((uint8_t*)state+A7_DMM_OBSERVER_OFFSET);o->disposal=-999;
  if(a7_dmm_init(&o->channel,&query_api,41)){sc3(91,code,16384,0);return -17;}
#endif
  if(sc3(0xf0002,code,code+sizeof hook_code,0)||sc3(125,code,4096,5)){
#if A7YC_KIND >= 7
   a7_dmm_dispose(&o->channel);
#endif
   sc3(91,code,16384,0);return -8;}
  uint32_t expected=current;
  if(!__atomic_compare_exchange_n(slot,&expected,code,0,__ATOMIC_ACQ_REL,__ATOMIC_ACQUIRE)){
#if A7YC_KIND >= 7
   a7_dmm_dispose(&o->channel);
#endif
   sc3(91,code,16384,0);return -9;}
 }else{
  if((current&4095)||current>UINT32_MAX-16384||!range(current,4096,"r-xp",1)||!range(current+4096,12288,"rw-p",1))return -10;
  state=(void*)(current+4096);result.code=current;result.state=(uintptr_t)state;
  for(unsigned i=0;i<sizeof hook_code;i++)if((i<A7YC_STATE_LITERAL||i>=A7YC_STATE_LITERAL+4)&&((volatile unsigned char*)current)[i]!=hook_code[i])return -11;
  if(*(uint32_t*)(current+A7YC_STATE_LITERAL)!=(uintptr_t)state||state->magic!=0x41375943||state->version!=9||state->original!=original||state->maximum!=128||state->mode!=A7YC_KIND||
     (state->restore_slot!=original&&state->restore_slot!=obj+A7YC_LAZY))return -12;
 }
 if(ACTION==2)__atomic_store_n(&state->armed,0,__ATOMIC_RELEASE);
 /* Keep the slot discoverable if a current recorder owns the lock. A later
  * stop can retry the known disarmed hook and collect its completed record. */
 if(__atomic_exchange_n(&state->lock,1,__ATOMIC_ACQUIRE))return -14;
#if A7YC_KIND >= 7
 struct a7_dmm_observer *o=(void*)((uint8_t*)state+A7_DMM_OBSERVER_OFFSET);
 if(!same(&o->channel.api,&query_api,sizeof query_api)||!o->channel.constructed||(A7YC_KIND<8&&o->channel.held)){
  __atomic_store_n(&state->lock,0,__ATOMIC_RELEASE);return -17;}
 if(ACTION==2){
  if(o->channel.pending)o->status=o->channel.poisoned?a7_dmm_reconcile_info(&o->channel):a7_dmm_poll(&o->channel,0);
  if(A7YC_KIND>=8&&!o->channel.pending&&!o->channel.poisoned&&o->channel.held){
   o->phase=3;o->status=a7_dmm_close(&o->channel,0);o->close_status=o->status;
  }
  if(A7YC_KIND>=8&&o->phase==3&&!o->channel.pending&&!o->channel.poisoned){
   copy(o->close_reply,o->channel.reply,24);if(!o->channel.held)o->phase=4;
  }
  o->disposal=a7_dmm_dispose(&o->channel);
  if(o->disposal){copy(&result.trace,state,sizeof *state);__atomic_store_n(&state->lock,0,__ATOMIC_RELEASE);return -18;}
 }
#endif
 if(ACTION==2){uint32_t expected=result.code;
  if(!__atomic_compare_exchange_n(slot,&expected,state->restore_slot,0,__ATOMIC_ACQ_REL,__ATOMIC_ACQUIRE)){
   __atomic_store_n(&state->lock,0,__ATOMIC_RELEASE);return -13;
  }
 }
 copy(&result.trace,state,sizeof *state);__atomic_store_n(&state->lock,0,__ATOMIC_RELEASE);
 return ACTION==2?2:1;
}
#ifndef A7YC_PROBE_TEST
__attribute__((constructor)) static void constructor(void){
 result.magic=0x41375950;result.version=9;result.action=ACTION;result.status=inspect();
 sc3(10,(long)"/tmp/jiritsu/libJit.so",0,0);long fd=sc3(5,(long)"/tmp/jiritsu/a7yc.bin",1|64|128|0x8000,0600);if(fd<0)return;
 unsigned done=0;while(done<sizeof result){long n=sc3(4,fd,(long)((unsigned char*)&result+done),sizeof result-done);if(n<=0||(unsigned)n>sizeof result-done)break;done+=(unsigned)n;}
 sc3(118,fd,0,0);sc3(6,fd,0,0);
}
#endif
