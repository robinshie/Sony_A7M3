#include "native_module_replace.h"
#include "../payloads/sha256.h"
enum {RD=3,WR=4,OPEN=5,CLOSE=6,MOUNT=21,UID=49,IOCTL=54,STATFS=99,SYNC=118,CAP=184,FSTAT=197,
      OPENAT=322,UNLINKAT=328,RENAMEAT=329,LINKAT=330};
enum {NOFOLLOW=0x8000,NONBLOCK=0x800,DIRECTORY=0x4000,CREAT=64,EXCL=128};
#ifndef NMR_REVISION
#define NMR_REVISION 1
#endif
#if NMR_REVISION == 1
static const char temporary[]=".a7fl-r1.new",backup[]=".a7fl-2478cec2.orig",logname[]="A7FLUP1.LOG";
#elif NMR_REVISION == 2
static const char temporary[]=".a7fl-r2.new",backup[]=".a7fl-e64867d2.orig",logname[]="A7FLUP2.LOG";
#elif NMR_REVISION == 3
static const char temporary[]=".a7fl-r3.new",backup[]=".a7fl-f3e2d657.orig",logname[]="A7FLUP3.LOG";
#elif NMR_REVISION == 4
static const char temporary[]=".a7fl-r4.new",backup[]=".a7fl-bd01f7b1.orig",logname[]="A7FLUP4.LOG";
#elif NMR_REVISION == 5
static const char temporary[]=".a7fl-r5.new",backup[]=".a7fl-1216dda3.orig",logname[]="A7FLUP5.LOG";
#elif NMR_REVISION == 6
static const char temporary[]=".a7fl-r6.new",backup[]=".a7fl-62c85626.orig",logname[]="A7FLUP6.LOG";
#elif NMR_REVISION == 7
static const char temporary[]=".a7fl-r7.new",backup[]=".a7fl-25d5f6f1.orig",logname[]="A7FLUP7.LOG";
#elif NMR_REVISION == 8
static const char temporary[]=".a7fl-r8.new",backup[]=".a7fl-74d1df6c.orig",logname[]="A7FLUP8.LOG";
#elif NMR_REVISION == 9
static const char temporary[]=".a7fl-r9.new",backup[]=".a7fl-a332915e.orig",logname[]="A7FLUP9.LOG";
#else
#error Unsupported module replacement revision
#endif
static const char current[]="a7fl.so";
static volatile unsigned busy;
typedef struct {uint64_t dev,ino;uint32_t size,links,mode;} File;
typedef struct {const NMRBundle*b;NMRCall call;void*ctx;NMRReport*r;int lib,setting,log,rw;unsigned sequence,temp_old;
                File old,new_file;unsigned char buffer[4096];} Work;
static void zero(void*p,unsigned n){unsigned char*s=p;while(n--)*s++=0;}
static int same(const void*a,const void*b,unsigned n){const unsigned char*x=a,*y=b;while(n--)if(*x++!=*y++)return 0;return 1;}
static int any(const unsigned char*p,unsigned n){while(n--)if(*p++)return 1;return 0;}
static uint32_t u32(const unsigned char*p){return p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;}
static uint64_t u64(const unsigned char*p){return (uint64_t)u32(p)|(uint64_t)u32(p+4)<<32;}
static void hashword(Sha256*h,uint32_t x){unsigned char b[4];for(unsigned i=0;i<4;i++)b[i]=(unsigned char)(x>>(8*i));sha_update(h,b,4);}
void nmr_binding(const NMRBundle*b,unsigned char out[32]){Sha256 h;sha_init(&h);static const unsigned char domain[]="A7M3-single-module-r1";
 sha_update(&h,domain,sizeof domain);hashword(&h,b->version);hashword(&h,b->old_size);hashword(&h,b->new_size);hashword(&h,b->view_size);
 sha_update(&h,b->old_sha,32);sha_update(&h,b->new_sha,32);sha_update(&h,b->view_sha,32);sha_update(&h,b->new_proof_sha,32);sha_finish(&h,out);}
static long sc(Work*w,long n,long a,long b,long c,long d,long e,long f){long r=w->call(w->ctx,n,a,b,c,d,e,f);if(r<0&&!w->r->first_error)w->r->first_error=(int)r;return r;}
static int closefd(Work*w,int fd){return sc(w,CLOSE,fd,0,0,0,0,0)==0;}
/* ARM EABI stat64 is104bytes: dev0,mode16,nlink20,uid24,size48,ino96. */
/* Original Sony /usr/lib and view inode retain uid57285/gid1000; the new
 * module/backup and /setting are root-owned. Ownership is path-specific. */
static int statfd(Work*w,int fd,File*f,unsigned uid,unsigned gid){union{uint64_t aligned;unsigned char b[104];}s;zero(&s,sizeof s);
 if(sc(w,FSTAT,fd,(long)s.b,0,0,0,0)||u32(s.b+24)!=uid||u32(s.b+28)!=gid||u64(s.b+48)>0xffffffffu)return 0;
 f->dev=u64(s.b);f->ino=u64(s.b+96);f->mode=u32(s.b+16);f->links=u32(s.b+20);f->size=(uint32_t)u64(s.b+48);return f->ino!=0;}
static int ident(const File*a,const File*b){return a->dev==b->dev&&a->ino==b->ino;}
static int absent(Work*w,int dir,const char*name){long fd=w->call(w->ctx,OPENAT,dir,(long)name,NOFOLLOW|NONBLOCK,0,0,0);
 if(fd==-2)return 1;if(fd>=0)closefd(w,(int)fd);return 0;}
static int hashfd(Work*w,int fd,unsigned size,const unsigned char expected[32]){Sha256 h;sha_init(&h);unsigned used=0;int ok=1;unsigned char sum[32];
 for(;;){long n=sc(w,RD,fd,(long)w->buffer,sizeof w->buffer,0,0,0);if(n<0||(unsigned)n>sizeof w->buffer){ok=0;break;}if(!n)break;
  if(used>size||(unsigned)n>size-used){ok=0;break;}sha_update(&h,w->buffer,(unsigned)n);used+=(unsigned)n;}
 sha_finish(&h,sum);return ok&&used==size&&same(sum,expected,32);}
static int named(const char*a,const char*b){while(*a&&*a==*b){a++;b++;}return *a==*b;}
static int file(Work*w,int dir,const char*name,unsigned size,const unsigned char hash[32],unsigned links,const File*expected,File*out){
 int fd=(int)sc(w,OPENAT,dir,(long)name,NOFOLLOW|NONBLOCK,0,0,0);if(fd<0)return 0;File a,b;
 unsigned original=named(name,"viewUnified2.so"),uid=original?57285:0,gid=original?1000:0;
 int ok=statfd(w,fd,&a,uid,gid)&&(a.mode&0xf000)==0x8000&&a.links==links&&a.size==size&&(!expected||ident(&a,expected))&&hashfd(w,fd,size,hash)&&statfd(w,fd,&b,uid,gid)&&ident(&a,&b)&&a.size==b.size&&a.links==b.links;
 if(!closefd(w,fd))ok=0;if(ok&&out)*out=a;return ok;}
static int writeall(Work*w,int fd,const void*p,unsigned size){const unsigned char*s=p;while(size){long n=sc(w,WR,fd,(long)s,size,0,0,0);if(n<=0||(unsigned)n>size)return 0;s+=n;size-=(unsigned)n;}return 1;}
static int journal(Work*w,unsigned phase){struct{uint32_t magic,sequence,phase,created,backed,published;unsigned char binding[32],hash[32];}v;
 v.magic=0x41374655;v.sequence=++w->sequence;v.phase=phase;v.created=w->r->created;v.backed=w->r->backed_up;v.published=w->r->published;
 for(unsigned i=0;i<32;i++)v.binding[i]=w->r->binding[i];Sha256 h;sha_init(&h);sha_update(&h,(unsigned char*)&v,56);sha_finish(&h,v.hash);w->r->phase=phase;
 return writeall(w,w->log,&v,sizeof v)&&sc(w,SYNC,w->log,0,0,0,0,0)==0;}
static int mount_is(Work*w,int ro){int fd=(int)sc(w,OPEN,(long)"/proc/self/mounts",NOFOLLOW,0,0,0,0);if(fd<0)return 0;unsigned n=0;int ok=1;
 while(n<sizeof w->buffer-1){long got=sc(w,RD,fd,(long)(w->buffer+n),sizeof w->buffer-1-n,0,0,0);if(got<0||(unsigned)got>sizeof w->buffer-1-n){ok=0;break;}if(!got)break;n+=(unsigned)got;}
 if(!closefd(w,fd))ok=0;if(!ok||n==sizeof w->buffer-1)return 0;
 const char*s=ro?"/dev/nflasha15 /usr ext2 ro,relatime,errors=continue 0 0\n":"/dev/nflasha15 /usr ext2 rw,relatime,errors=continue 0 0\n";unsigned len=0,hits=0;while(s[len])len++;
 for(unsigned i=0;i+len<=n;i++)if((!i||w->buffer[i-1]=='\n')&&same(w->buffer+i,s,len))hits++;return hits==1;}
static int remount(Work*w,int ro){return sc(w,MOUNT,(long)"/dev/nflasha15",(long)"/usr",(long)"ext2",32|(1<<21)|(ro?1:0),(long)"errors=continue",0)==0;}
static int preflight(Work*w,NMRIdentity identity,void*ctx){
 w->r->phase=1000;if(!identity||identity(ctx)!=1||sc(w,UID,0,0,0,0,0,0))return 0;
 w->r->phase=1001;if(!mount_is(w,1))return 0;w->r->readonly_confirmed=1;
 static const unsigned char build[]="37114_13.2026020901";unsigned char hash[32];Sha256 h;sha_init(&h);sha_update(&h,build,sizeof build-1);sha_finish(&h,hash);
 w->r->phase=1002;int fd=(int)sc(w,OPEN,(long)"/version.txt",NOFOLLOW|NONBLOCK,0,0,0,0);if(fd<0)return 0;int ok=hashfd(w,fd,sizeof build-1,hash);if(!closefd(w,fd))ok=0;if(!ok)return 0;
 uint32_t caphead[2]={0x20080522,0},caps[6],stat[16];zero(caps,sizeof caps);zero(stat,sizeof stat);
 w->r->phase=1003;if(sc(w,CAP,(long)caphead,(long)caps,0,0,0,0)||!(caps[0]&(1u<<21)))return 0;
 w->r->phase=1004;fd=(int)sc(w,OPEN,(long)"/dev/nflasha15",0,0,0,0,0);if(fd<0)return 0;int ro=-1;ok=sc(w,IOCTL,fd,0x125e,(long)&ro,0,0,0)==0&&ro==0;if(!closefd(w,fd))ok=0;if(!ok)return 0;
 w->r->phase=1005;if(sc(w,STATFS,(long)"/usr",(long)stat,0,0,0,0)||stat[0]!=0xef53||stat[1]!=1024||!(stat[11]&1)||stat[6]<1||stat[4]<(w->b->new_size+1023)/1024+32)return 0;
 w->r->phase=1006;
 w->lib=(int)sc(w,OPEN,(long)"/usr/lib",DIRECTORY|NOFOLLOW,0,0,0,0);if(w->lib<0)return 0;
 w->setting=(int)sc(w,OPEN,(long)"/setting",DIRECTORY|NOFOLLOW,0,0,0,0);if(w->setting<0)return 0;
 File d;if(!statfd(w,w->lib,&d,57285,1000)||(d.mode&0xf000)!=0x4000||!statfd(w,w->setting,&d,0,0)||(d.mode&0xf000)!=0x4000)return 0;
 w->r->phase=1007;if(!file(w,w->lib,current,w->b->old_size,w->b->old_sha,1,0,&w->old))return 0;
 w->r->phase=1008;if(!file(w,w->lib,"viewUnified2.so",w->b->view_size,w->b->view_sha,1,0,0))return 0;
 w->r->phase=1009;return absent(w,w->lib,temporary)&&absent(w,w->lib,backup)&&absent(w,w->setting,logname);
}
static int unlink_owned_temp(Work*w){
 if(!w->r->created)return 1;File*expected=w->temp_old?&w->old:&w->new_file;
 if(!expected->ino)return 0;int fd=(int)sc(w,OPENAT,w->lib,(long)temporary,NOFOLLOW|NONBLOCK,0,0,0);if(fd<0)return 0;File st;
 int ok=statfd(w,fd,&st,0,0)&&ident(&st,expected)&&(st.mode&0xf000)==0x8000;if(!closefd(w,fd))ok=0;
 if(!ok||sc(w,UNLINKAT,w->lib,(long)temporary,0,0,0,0))return 0;w->r->created=0;return sc(w,SYNC,w->lib,0,0,0,0,0)==0;
}
static int rollback(Work*w){int ok=1;
 if(w->r->published){
  if(!file(w,w->lib,current,w->b->new_size,w->b->new_sha,1,&w->new_file,0)||
     !file(w,w->lib,backup,w->b->old_size,w->b->old_sha,1,&w->old,0)||!absent(w,w->lib,temporary)||
     sc(w,LINKAT,w->lib,(long)backup,w->lib,(long)temporary,0,0))ok=0;
  else {w->r->created=1;w->temp_old=1;
   if(sc(w,SYNC,w->lib,0,0,0,0,0)||sc(w,RENAMEAT,w->lib,(long)temporary,w->lib,(long)current,0,0))ok=0;
   else{w->r->created=w->r->published=0;if(sc(w,SYNC,w->lib,0,0,0,0,0))ok=0;}}
 }
 if(!unlink_owned_temp(w))ok=0;
 if(!file(w,w->lib,current,w->b->old_size,w->b->old_sha,w->r->backed_up?2:1,&w->old,0))ok=0;
 return ok;
}
int nmr_run(const NMRBundle*b,const unsigned char expected[32],NMRCall call,void*ctx,NMRIdentity identity,void*idctx,int write,NMRReport*r){
 if(!b||!expected||!call||!r)return -1;zero(r,sizeof*r);r->magic=0x41374652;r->version=1;r->status=-1;
 if(__sync_lock_test_and_set(&busy,1))return -2;Work w;zero(&w,sizeof w);w.b=b;w.call=call;w.ctx=ctx;w.r=r;w.lib=w.setting=w.log=-1;int success=0;
 nmr_binding(b,r->binding);unsigned char sum[32];Sha256 h;sha_init(&h);
 if(b->version!=NMR_REVISION||(write!=0&&write!=1)||!b->new_bytes||b->old_size<52||b->old_size>1048576||b->new_size<52||b->new_size>1048576||
    b->view_size<4096||b->view_size>16*1048576||!same(expected,r->binding,32)||same(b->old_sha,b->new_sha,32)||!any(b->new_proof_sha,32))goto done;
 sha_update(&h,b->new_bytes,b->new_size);sha_finish(&h,sum);
 if(!same(sum,b->new_sha,32)||!same(b->new_bytes,"\177ELF\1\1\1",7)||!same(b->new_bytes+16,"\3\0\50\0",4))goto done;
 if(!preflight(&w,identity,idctx))goto done;r->phase=1;if(!write){success=1;goto done;}
 w.log=(int)sc(&w,OPENAT,w.setting,(long)logname,1|CREAT|EXCL|NOFOLLOW|NONBLOCK,0600,0,0);if(w.log<0)goto done;
 if(!journal(&w,1)||sc(&w,SYNC,w.setting,0,0,0,0,0)||!remount(&w,0))goto done;w.rw=1;r->readonly_confirmed=0;
 if(!mount_is(&w,0)||!journal(&w,2)||!journal(&w,10))goto fail;
 int fd=(int)sc(&w,OPENAT,w.lib,(long)temporary,1|CREAT|EXCL|NOFOLLOW|NONBLOCK,0555,0,0);if(fd<0)goto fail;r->created=1;
 int ok=statfd(&w,fd,&w.new_file,0,0)&&(w.new_file.mode&0xf000)==0x8000&&w.new_file.links==1&&w.new_file.size==0&&
        writeall(&w,fd,b->new_bytes,b->new_size)&&sc(&w,SYNC,fd,0,0,0,0,0)==0;
 if(!closefd(&w,fd))ok=0;
 if(!ok||!file(&w,w.lib,temporary,b->new_size,b->new_sha,1,&w.new_file,0)||sc(&w,SYNC,w.lib,0,0,0,0,0)||!journal(&w,20))goto fail;
 if(!file(&w,w.lib,current,b->old_size,b->old_sha,1,&w.old,0)||!journal(&w,30)||
    sc(&w,LINKAT,w.lib,(long)current,w.lib,(long)backup,0,0))goto fail;r->backed_up=1;
 if(sc(&w,SYNC,w.lib,0,0,0,0,0)||!file(&w,w.lib,backup,b->old_size,b->old_sha,2,&w.old,0)||!journal(&w,31))goto fail;
 if(!file(&w,w.lib,current,b->old_size,b->old_sha,2,&w.old,0)||!file(&w,w.lib,temporary,b->new_size,b->new_sha,1,&w.new_file,0)||!journal(&w,40)||
    sc(&w,RENAMEAT,w.lib,(long)temporary,w.lib,(long)current,0,0))goto fail;r->created=0;r->published=1;
 if(sc(&w,SYNC,w.lib,0,0,0,0,0)||!journal(&w,41)||!file(&w,w.lib,current,b->new_size,b->new_sha,1,&w.new_file,0)||
    !file(&w,w.lib,backup,b->old_size,b->old_sha,1,&w.old,0)||!file(&w,w.lib,"viewUnified2.so",b->view_size,b->view_sha,1,0,0)||!journal(&w,60))goto fail;
 success=1;goto restore;
fail:r->rollback_ok=rollback(&w);journal(&w,90);
restore:if(remount(&w,1)&&mount_is(&w,1)){r->readonly_confirmed=1;w.rw=0;}else{success=0;r->status=-4;}
 if(!journal(&w,success?100:99))success=0;
done:
 if(w.rw){if(remount(&w,1)&&mount_is(&w,1))r->readonly_confirmed=1;else r->status=-4;}
 if(w.log>=0&&!closefd(&w,w.log))success=0;if(w.lib>=0&&!closefd(&w,w.lib))success=0;if(w.setting>=0&&!closefd(&w,w.setting))success=0;
 r->status=success?0:r->status==-4?-4:-3;__sync_lock_release(&busy);return r->status;
}
