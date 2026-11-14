/* Read-only DMM unit query. No hooks, unit Open/Close, mappings or pixel I/O.
 * A finite polling window never frees a queue that still has an in-flight reply.
 * An unfinished query lives in an anonymous allocation for explicit resumption. */
#define A7_RUNTIME_LIBRARY_ONLY
#include "a7-runtime-probe.c"
#include "a7-dmm-channel.h"
#include "dmm-query-pins.h"
#include <stddef.h>
void *memset(void *p,int value,size_t n){uint8_t *d=p;while(n--)*d++=(uint8_t)value;return p;}
struct State {uint32_t magic,version,self,base,handle;struct a7_dmm_channel channel;};
struct Output {uint32_t magic,version,base,address,retained,polls;int32_t status,disposal;struct State state;};
_Static_assert(sizeof(struct Output)==212,"query report ABI");
static struct Output output;
static int same(const void *a,const void *b,unsigned n){const volatile uint8_t *x=a;const uint8_t *y=b;while(n--)if(*x++!=*y++)return 0;return 1;}
static void copy(void *a,const void *b,unsigned n){uint8_t *x=a;const volatile uint8_t *y=b;while(n--)*x++=*y++;}
static int exact(const char *a,const char *b){while(*b&&*a==*b){a++;b++;}return !*b&&(!*a||*a=='\n');}
static uint32_t find_base(void){uint32_t found=0;
 for(const char *p=report.maps;*p;){const char *q=p;uint32_t lo=hex(&q);
  if(contains(p,"r-xp 00000000")){while(*q&&*q!='\n'&&*q!='/')q++;
   if(exact(q,"/usr/lib/libBizFw.so")){if(found)return 0;found=lo;}}
  while(*p&&*p!='\n')p++;if(*p)p++;
 }return found;
}
static int anonymous_writable(uint32_t address){
 static const char prefix[]=" rw-p 00000000 00:00 0";
 for(const char *p=report.maps;*p;){const char *q=p;uint32_t lo=hex(&q);if(*q++!='-')return 0;uint32_t hi=hex(&q);
  if(lo<=address&&address<=hi&&hi-address>=4096&&same(q,prefix,sizeof prefix-1)){
   q+=sizeof prefix-1;while(*q==' ')q++;return !*q||*q=='\n';}
  while(*p&&*p!='\n')p++;if(*p)p++;
 }return 0;
}
static int pinned(uint32_t base){
 if(!readable(base,sizeof library_header)||!same((void*)base,library_header,sizeof library_header))return 0;
 for(unsigned p=0;p<sizeof pins/sizeof *pins;p++){
  const struct Pin *pin=pins+p;uint32_t at=base+pin->offset;
  if(at<base||!readable(at,pin->size))return 0;
  for(unsigned i=0;i<pin->size;){unsigned relocated=0;
   for(unsigned j=0;j<pin->count;j++)if(pin->relocations[j]==i){
    const uint8_t *q=pin->bytes+i;uint32_t word=q[0]|((uint32_t)q[1]<<8)|((uint32_t)q[2]<<16)|((uint32_t)q[3]<<24);
    if(*(volatile uint32_t*)(at+i)!=word+base)return 0;i+=4;relocated=1;break;}
   if(!relocated){if(*(volatile uint8_t*)(at+i)!=pin->bytes[i])return 0;i++;}
  }
 }return 1;
}
static long allocate(void){register long r7 __asm__("r7")=192,r0 __asm__("r0")=0,r1 __asm__("r1")=4096,r2 __asm__("r2")=3,r3 __asm__("r3")=0x22,r4 __asm__("r4")=-1,r5 __asm__("r5")=0;
 __asm__ volatile("svc #0":"+r"(r0):"r"(r7),"r"(r1),"r"(r2),"r"(r3),"r"(r4),"r"(r5):"memory","cc");return r0;}
static int inspect(void){
 char version[24];static const char expected[]="37114_13.2026020901";
 if(read_proc("/version.txt",version,sizeof version)!=(long)sizeof expected-1||!same(version,expected,sizeof expected-1))return -101;
 report.maps_n=read_proc("/proc/self/maps",report.maps,sizeof report.maps-1);if(report.maps_n<=0)return -102;report.maps[report.maps_n]=0;
 uint32_t base=find_base();output.base=base;if(!base||!pinned(base))return -103;
 struct a7_dmm_native api={(void*)(base+PIN_CTOR),(void*)(base+PIN_DTOR),(void*)(base+PIN_SEND),(void*)(base+PIN_RECEIVE)};
 struct State *s;int status;
 if(QUERY_RESUME){
  if((QUERY_RESUME&4095)||!anonymous_writable(QUERY_RESUME))return -104;s=(void*)QUERY_RESUME;
  if(s->magic!=0x41374451||s->version!=1||s->self!=QUERY_RESUME||s->base!=base||s->handle!=QUERY_HANDLE||
     !same(&s->channel.api,&api,sizeof api)||!s->channel.constructed||!s->channel.pending||s->channel.held||
     s->channel.command!=0x13||s->channel.request_handle!=QUERY_HANDLE)return -105;
  status=s->channel.poisoned?a7_dmm_reconcile_info(&s->channel):a7_dmm_poll(&s->channel,0);
 }else{
  long at=allocate();if(!at||(uint32_t)at>=0xfffff001)return -106;
  s=(void*)at;s->magic=0x41374451;s->version=1;s->self=(uint32_t)at;s->base=base;s->handle=QUERY_HANDLE;
  status=a7_dmm_init(&s->channel,&api,41);
  if(!status)status=a7_dmm_info(&s->channel,QUERY_HANDLE,0);
 }
 output.address=(uint32_t)s;
 /* Timeout zero is nonblocking; the 20ms sleeps are Linux nanosleep, not
  * assumptions about the OSAL timeout unit. At most 200ms explicit waiting. */
 for(unsigned i=0;i<10&&s->channel.pending&&!s->channel.poisoned;i++){
  uint32_t delay[2]={0,20000000};if(sc3(162,(long)delay,0,0))break;
  status=a7_dmm_poll(&s->channel,0);output.polls++;
 }
 output.retained=s->channel.pending||s->channel.held||s->channel.poisoned;
 output.disposal=-999;
 if(!output.retained&&s->channel.constructed){output.disposal=a7_dmm_dispose(&s->channel);if(output.disposal)output.retained=1;}
 copy(&output.state,s,sizeof *s);
 if(!output.retained)sc3(91,(long)s,4096,0);
 return status;
}
__attribute__((constructor)) static void query(void){
 output.magic=0x41374452;output.version=1;output.status=inspect();
 sc3(10,(long)"/tmp/jiritsu/libJit.so",0,0);
 long fd=sc3(5,(long)"/tmp/jiritsu/a7dmm.bin",1|64|128|0x8000,0600);if(fd<0)return;
 unsigned done=0;while(done<sizeof output){long n=sc3(4,fd,(long)((uint8_t*)&output+done),sizeof output-done);if(n<=0||(unsigned)n>sizeof output-done)break;done+=(unsigned)n;}
 sc3(118,fd,0,0);sc3(6,fd,0,0);
}
