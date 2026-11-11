/* Bounded read-only ext2/VFS comparison. No mounts, sync, cache invalidation,
 * executable patch, or block-device write. Report output is separate. */
#include "native_fsmeta.h"
enum {READ=3,OPEN=5,CLOSE=6,LSEEK=19,LSTAT64=196,FSTAT64=197,GETDENTS64=217};
enum {NOFOLLOW=0x8000,DIRECTORY=0x4000,NONBLOCK=0x800};
static const uint32_t offsets[20]={1024,2048,67111936,67129344,67115008,109054976,
 73928704,79055872,82013184,10354688,17866752,34941952,38861824,44438528,
 115868672,117974016,146781184,186749952,189675520,195015680};
static const char *const paths[8]={"/usr/share/app","/usr/lib","/usr/share/app/string_simplifiedchinese.uxc",
 "/usr/share/app/string_english.uxc","/usr/share/app/.a7fl-zh.orig","/usr/share/app/.a7fl-en.orig",
 "/usr/lib/a7fl.so","/usr/lib/viewUnified2.so"};
typedef struct {NfmReport*r;NfmSyscall sys;void*ctx;int device;} Work;
static void zero(void*p,unsigned n){unsigned char*d=p;while(n--)*d++=0;}
static uint32_t u32(const unsigned char*p){return (uint32_t)p[0]|((uint32_t)p[1]<<8)|((uint32_t)p[2]<<16)|((uint32_t)p[3]<<24);}
static unsigned u16(const unsigned char*p){return p[0]|((unsigned)p[1]<<8);}
static int named(const unsigned char*p,unsigned n,const char*s){unsigned i=0;while(s[i]){if(i>=n||p[i]!=(unsigned char)s[i])return 0;i++;}return i==n;}
static long call(Work*w,long n,long a,long b,long c){long r=w->sys(w->ctx,n,a,b,c,0,0,0);if(r<0&&!w->r->first_error)w->r->first_error=(int)r;return r;}
static int closefd(Work*w,int fd){return call(w,CLOSE,fd,0,0)==0;}
static int read_exact(Work*w,int fd,unsigned char*p,unsigned n){unsigned used=0;while(used<n){long r=call(w,READ,fd,(long)(p+used),n-used);if(r<=0||(unsigned)r>n-used)return 0;used+=(unsigned)r;}return 1;}
static int block(Work*w,uint32_t offset,uint32_t tag){
 if(w->r->raw_count==32||offset&1023||offset>212172u*1024u-1024)return 0;
 NfmRaw*b=&w->r->raw[w->r->raw_count++];b->offset=offset;b->size=1024;b->tag=tag;b->result=-1;
 if(call(w,LSEEK,w->device,offset,0)!=(long)offset||!read_exact(w,w->device,b->bytes,1024))return 0;
 b->result=0;return 1;
}
static int inode(Work*w,unsigned number){
 if(!number||number>53248)return 0;
 unsigned group=(number-1)/2048,index=(number-1)%2048;
 unsigned table=u32(w->r->raw[1].bytes+group*32+8);
 if(table<3||table>=212172)return 0;
 uint32_t at=table*1024+index*128;
 if(at<table*1024||at>212172u*1024u-128)return 0;
 return block(w,at&~1023u,0x10000000u|number);
}
static int directory_inodes(Work*w,unsigned start,unsigned count){
 for(unsigned b=0;b<count;b++){
  const unsigned char*p=w->r->raw[start+b].bytes;unsigned pos=0;
  while(pos<1024){if(1024-pos<8)return 0;unsigned number=u32(p+pos),length=u16(p+pos+4),n=p[pos+6];
   if(length<8||length&3||length>1024-pos||n>length-8)return 0;
   const unsigned char*name=p+pos+8;
   if(number&&(named(name,n,"a7fl.so")||named(name,n,"string_simplifiedchinese.uxc")||named(name,n,"string_english.uxc")||
      named(name,n,".a7fl-zh.orig")||named(name,n,".a7fl-en.orig")||named(name,n,".a7fl-zh.new")||named(name,n,".a7fl-en.new")||named(name,n,".a7fl.new")))
      if(!inode(w,number))return 0;
   pos+=length;
  }
 }
 return 1;
}
static int read_mounts(Work*w){
 int fd=(int)call(w,OPEN,(long)"/proc/self/mounts",NOFOLLOW|NONBLOCK,0);if(fd<0)return 0;int ok=1;
 while(w->r->mount_size<sizeof w->r->mounts){long r=call(w,READ,fd,(long)(w->r->mounts+w->r->mount_size),sizeof w->r->mounts-w->r->mount_size);
  if(r<0||(unsigned)r>sizeof w->r->mounts-w->r->mount_size){ok=0;break;}if(!r)break;w->r->mount_size+=(unsigned)r;}
 if(w->r->mount_size==sizeof w->r->mounts)ok=0;
 if(!closefd(w,fd))ok=0;return ok;
}
static void read_stat(Work*w,unsigned i){
 NfmStat*s=&w->r->stats[i];s->open_result=s->fstat_result=s->close_result=-999;
 s->lstat_result=(int)call(w,LSTAT64,(long)paths[i],(long)s->lstat64,0);
 int fd=(int)call(w,OPEN,(long)paths[i],NOFOLLOW|NONBLOCK|(i<2?DIRECTORY:0),0);s->open_result=fd;
 if(fd>=0){s->fstat_result=(int)call(w,FSTAT64,fd,(long)s->fstat64,0);s->close_result=(int)call(w,CLOSE,fd,0,0);}
 w->r->stat_count++;
}
static int read_directory(Work*w,unsigned i){
 NfmDirectory*d=&w->r->directories[i];d->read_result=d->close_result=-999;
 int fd=(int)call(w,OPEN,(long)paths[i],DIRECTORY|NOFOLLOW|NONBLOCK,0);d->open_result=fd;
 if(fd<0)return 0;int ok=1;
 while(d->size<sizeof d->bytes){long n=call(w,GETDENTS64,fd,(long)(d->bytes+d->size),sizeof d->bytes-d->size);
  d->read_result=(int)n;if(n<0||(unsigned)n>sizeof d->bytes-d->size){ok=0;break;}if(!n)break;
  unsigned at=0;while(at<(unsigned)n){const unsigned char*p=d->bytes+d->size+at;
   if((unsigned)n-at<20){ok=0;break;}unsigned len=u16(p+16);if(len<20||len>(unsigned)n-at){ok=0;break;}
   unsigned j=19;while(j<len&&p[j])j++;if(j==len){ok=0;break;}at+=len;}
  if(!ok)break;d->size+=(unsigned)n;
 }
 if(d->size==sizeof d->bytes)ok=0;d->close_result=(int)call(w,CLOSE,fd,0,0);if(d->close_result)ok=0;
 w->r->directory_count++;return ok;
}
int nfm_read(NfmReport*r,NfmSyscall sys,void*ctx){
 if(!r||!sys)return -1;zero(r,sizeof*r);r->magic=0x4137464d;r->version=1;r->size=sizeof*r;r->status=-1;
 Work w={r,sys,ctx,-1};unsigned char st[104];zero(st,sizeof st);
 w.device=(int)call(&w,OPEN,(long)"/dev/nflasha15",NOFOLLOW|NONBLOCK,0);if(w.device<0)return r->status=-2;
 if(call(&w,FSTAT64,w.device,(long)st,0)||(u32(st+16)&0xf000)!=0x6000)goto done;
 long capacity=call(&w,LSEEK,w.device,0,2);if(capacity!=300*1024*1024)goto done;r->capacity=(uint32_t)capacity;
 if(!block(&w,1024,0))goto done;const unsigned char*s=r->raw[0].bytes;
 if(u16(s+56)!=0xef53||u32(s)!=53248||u32(s+4)!=212172||u32(s+20)!=1||u32(s+24)||
    u32(s+32)!=8192||u32(s+40)!=2048||u16(s+88)!=128||u32(s+96)!=2)goto done;
 r->geometry_ok=1;
 for(unsigned i=1;i<20;i++)if(!block(&w,offsets[i],i))goto done;
 if(!directory_inodes(&w,6,8)||!directory_inodes(&w,14,6))goto done;
 r->status=0;
done:
 if(!closefd(&w,w.device))r->status=-3;
 if(!r->status){if(!read_mounts(&w))r->status=-4;for(unsigned i=0;i<8;i++)read_stat(&w,i);
  for(unsigned i=0;i<2;i++)if(!read_directory(&w,i))r->status=-5;}
 return r->status;
}
