/* Read-only samples from previously observed descriptor addresses. Readability
 * does NOT establish that a buffer still belongs to the captured photograph. */
#define A7_RUNTIME_LIBRARY_ONLY
#include "a7-runtime-probe.c"
#include "still-buffer-pins.h"
struct Sample {uint32_t offset,address,length;int32_t status;uint32_t copied;unsigned char data[256];};
struct Result {uint32_t magic,version;int32_t status;uint32_t count;struct Sample samples[12];};
static struct Result result;
_Static_assert(sizeof(struct Result)==3328,"sample report ABI");
static int same(const void*a,const void*b,unsigned n){const unsigned char*x=a,*y=b;for(unsigned i=0;i<n;i++)if(x[i]!=y[i])return 0;return 1;}
static int inspect(void){
 char build[24];static const char expected[]="37114_13.2026020901";
 if(read_proc("/version.txt",build,sizeof build)!=(long)sizeof expected-1||!same(build,expected,sizeof expected-1))return -1;
 report.maps_n=read_proc("/proc/self/maps",report.maps,sizeof report.maps-1);
 if(report.maps_n<=0)return -2;report.maps[report.maps_n]=0;
 for(unsigned i=0;i<12;i++){
  struct Sample*s=&result.samples[i];s->offset=8+i*16;s->address=sample_areas[i][0];s->length=sample_areas[i][1];
  if(!s->address&&!s->length)continue;
  if(!s->address||!s->length||s->address>UINT32_MAX-s->length){s->status=-1;continue;}
  unsigned n=s->length<256?s->length:256;
  if(!readable(s->address,n)){s->status=-2;continue;}
  const volatile unsigned char*p=(const volatile unsigned char*)(uintptr_t)s->address;
  for(unsigned j=0;j<n;j++)s->data[j]=p[j];s->copied=n;s->status=1;
 }return 1;
}
__attribute__((constructor)) static void capture(void){
 result.magic=0x41375342;result.version=1;result.count=12;result.status=inspect();
 sc3(10,(long)"/tmp/jiritsu/libJit.so",0,0);
 long fd=sc3(5,(long)"/tmp/jiritsu/a7sb.bin",1|64|128|0x8000,0600);if(fd<0)return;
 unsigned at=0;while(at<sizeof result){long n=sc3(4,fd,(long)((char*)&result+at),sizeof result-at);if(n<=0||(unsigned)n>sizeof result-at)break;at+=(unsigned)n;}
 sc3(118,fd,0,0);sc3(6,fd,0,0);
}
