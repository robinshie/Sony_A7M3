/* Bounded Sony 4.04 WBI header operation. Mode zero never opens writable.
 * Mode one requires an exact previously captured 1024-byte preimage.
 * No bound write payload is produced by the default builder. */
#include "native_menu_wbi.h"
#include "../payloads/sha256.h"
enum {RD=3,WR=4,OPEN=5,CLOSE=6,SEEK=19,PID=20,EUID=49,IOCTL=54,SYNC=118,FSTAT64=197};
static const char path[]="/dev/nflasha5";
static volatile unsigned busy;
static int eq(const void*a,const void*b,unsigned n){const unsigned char*x=a,*y=b;while(n--)if(*x++!=*y++)return 0;return 1;}
static void clear(void*p,unsigned n){unsigned char*x=p;while(n--)*x++=0;}
typedef struct {NwbSys sys;void*ctx;NwbReport*r;} W;
static long call(W*w,long n,long a,long b,long c){long k=w->sys(w->ctx,n,a,b,c,0,0,0);if(k<0&&!w->r->error)w->r->error=(int)k;return k;}
static int read0(W*w,int fd,void*p){if(call(w,SEEK,fd,0,0))return 0;unsigned done=0;while(done<1024){long k=call(w,RD,fd,(long)((unsigned char*)p+done),1024-done);if(k<=0||(unsigned)k>1024-done)return 0;done+=(unsigned)k;}return 1;}
static int identity(W*w,int fd){unsigned char st[128];uint32_t cap[2]={0,0};clear(st,sizeof st);if(call(w,FSTAT64,fd,(long)st,0)||((*(uint32_t*)(st+16))&0xf000)!=0x6000)return 0;if(call(w,IOCTL,fd,0x80041272u,(long)cap))return 0;w->r->capacity_lo=cap[0];w->r->capacity_hi=cap[1];return cap[0]==0x03c00000&&!cap[1];}
int nwb_run(NwbSys sys,void*ctx,unsigned mode,const unsigned char*expected,NwbReport*r){
 if(!sys||!r||mode>1||(mode&&!expected))return -1;
 clear(r,sizeof *r);r->magic=0x57423741;r->version=1;r->status=-1;r->mode=mode;
 if(__sync_lock_test_and_set(&busy,1)){r->status=-2;return -2;}
 W w={sys,ctx,r};int fd=-1;unsigned char check[1024],zeros[512];clear(zeros,sizeof zeros);
 r->phase=1;if(call(&w,EUID,0,0,0)!=0)goto end;long pid=call(&w,PID,0,0,0);if(pid<=1)goto end;r->pid=(unsigned)pid;
 fd=(int)call(&w,OPEN,(long)path,0x8000,0);if(fd<0||!identity(&w,fd))goto end;r->phase=2;
 if(!read0(&w,fd,r->data)||!read0(&w,fd,check)||!eq(check,r->data,1024))goto end;
 Sha256 h;sha_init(&h);sha_update(&h,r->data,1024);sha_finish(&h,r->preimage_sha);
 r->neighbor_ok=1;
 uint32_t magic=*(uint32_t*)r->data;
 if(eq(r->data,zeros,512)){r->header_kind=0;r->status=mode?-3:1;goto end;}
 if((magic!=0x30494257u&&magic!=0x31494257u)||*(uint32_t*)(r->data+20)!=512){r->status=-4;goto end;}
 r->header_kind=magic==0x30494257u?1:2;r->phase=3;
 if(!mode){r->status=0;goto end;}
 if(!eq(expected,r->data,1024)){r->status=-5;goto end;}
 if(call(&w,CLOSE,fd,0,0)){fd=-1;goto end;}fd=-1;
 fd=(int)call(&w,OPEN,(long)path,0x8000|0x1002,0);if(fd<0||!identity(&w,fd)||!read0(&w,fd,check)||!eq(check,expected,1024)){r->status=-5;goto end;}
 r->phase=4;if(call(&w,SEEK,fd,0,0))goto end;
 while(r->written<512){long k=call(&w,WR,fd,(long)(zeros+r->written),512-r->written);if(k<=0||(unsigned)k>512-r->written)goto end;r->written+=(unsigned)k;}
 if(call(&w,SYNC,fd,0,0))goto end;r->fsync_ok=1;
 if(call(&w,CLOSE,fd,0,0)){fd=-1;goto end;}fd=-1;
 fd=(int)call(&w,OPEN,(long)path,0x8000,0);if(fd<0||!identity(&w,fd)||!read0(&w,fd,check))goto end;
 r->neighbor_ok=eq(check+512,expected+512,512);
 if(!eq(check,zeros,512)||!r->neighbor_ok)goto end;r->phase=100;r->status=0;
end:
 if(fd>=0&&call(&w,CLOSE,fd,0,0))r->status=-1;
 __sync_lock_release(&busy);return r->status;
}
