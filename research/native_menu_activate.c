#include "native_menu_activate.h"
#include "../payloads/sha256.h"
#ifdef NMA_LAYOUT_HEADER
#include NMA_LAYOUT_HEADER
#endif
#ifndef NMA_PAGE_OFFSETS
#define NMA_PAGE_OFFSETS {0x188000,0x20d000,0x5b9000}
#define NMA_PATCH_OFFSETS {0x5b9a7c,0x5b9b1c,0x20d068,0x188aec}
#define NMA_JOURNAL "/setting/A7FL.ACTIVATE"
#define NMA_RECOVERY_JOURNAL "/setting/A7FL.ACTIVATE.RECOVER"
#define NMA_UNDO_JOURNAL "/setting/A7FL.DEACTIVATE"
#define NMA_UNDO_RECOVERY_JOURNAL "/setting/A7FL.DEACTIVATE.RECOVER"
#endif
enum {OPEN=5,CLOSE=6,READ=3,WRITE=4,LSEEK=19,GETPID=20,MOUNT=21,GETEUID=49,FSYNC=118,MPROTECT=125,GETDENTS64=217};
enum {O_RDWR=2,O_WRONLY=1,O_CREAT=64,O_EXCL=128,O_DIRECTORY=0x4000,O_NOFOLLOW=0x8000};
static const char *required[3]={"/usr/lib/a7fl.so","/usr/share/app/string_simplifiedchinese.uxc","/usr/share/app/string_english.uxc"};
static const char view_path[]="/usr/lib/viewUnified2.so";
static const uint32_t offsets[3]=NMA_PAGE_OFFSETS;
static volatile unsigned busy;
typedef struct {const NmaBundle*b;NmaSyscall sys;void*ctx;NmaReport*r;int journal,view,remounted,booted_new;unsigned sequence;char fileid[48];unsigned char buffer[4096];} Work;
typedef struct {Work*w;int fd;unsigned pos,size,total;unsigned char b[4096];} Lines;
static int same(const void*aa,const void*bb,unsigned n){const unsigned char*a=aa,*b=bb;while(n--)if(*a++!=*b++)return 0;return 1;}
static void zero(void*p,unsigned n){unsigned char*a=p;while(n--)*a++=0;}
static long sc(Work*w,long n,long a,long b,long c,long d,long e,long f){long r=w->sys(w->ctx,n,a,b,c,d,e,f);if(r<0&&!w->r->first_error)w->r->first_error=(int)r;return r;}
static int closefd(Work*w,int fd){return sc(w,CLOSE,fd,0,0,0,0,0)==0;}
static int writeall(Work*w,int fd,const void*ptr,unsigned n){const unsigned char*p=ptr;while(n){long r=sc(w,WRITE,fd,(long)p,n,0,0,0);if(r<=0||(unsigned)r>n)return 0;p+=r;n-=(unsigned)r;}return 1;}
static int readat(Work*w,int fd,unsigned off,void*ptr,unsigned n){if(sc(w,LSEEK,fd,off,0,0,0,0)!=(long)off)return 0;unsigned done=0;while(done<n){long r=sc(w,READ,fd,(long)((unsigned char*)ptr+done),n-done,0,0,0);if(r<=0||(unsigned)r>n-done)return 0;done+=(unsigned)r;}return 1;}
static int writeat(Work*w,unsigned off,const void*p,unsigned n){return sc(w,LSEEK,w->view,off,0,0,0,0)==(long)off&&writeall(w,w->view,p,n)&&sc(w,FSYNC,w->view,0,0,0,0,0)==0;}
static int hashfile(Work*w,const char*path,unsigned size,const unsigned char expected[32]){int fd=(int)sc(w,OPEN,(long)path,O_NOFOLLOW,0,0,0,0);if(fd<0)return 0;Sha256 h;sha_init(&h);unsigned used=0;int ok=1;unsigned char sum[32];for(;;){long n=sc(w,READ,fd,(long)w->buffer,sizeof w->buffer,0,0,0);if(n<0||(unsigned)n>sizeof w->buffer){ok=0;break;}if(!n)break;if((unsigned)n>size-used){ok=0;break;}used+=(unsigned)n;sha_update(&h,w->buffer,(unsigned)n);}sha_finish(&h,sum);if(!closefd(w,fd))ok=0;return ok&&used==size&&same(sum,expected,32);}
/* Whole text streams are bounded but not assumed to fit one read. */
static int line(Lines*l,char*out,unsigned cap){unsigned n=0;for(;;){if(l->pos==l->size){long r=sc(l->w,READ,l->fd,(long)l->b,sizeof l->b,0,0,0);if(r<0||(unsigned)r>sizeof l->b)return -1;if(!r){if(!n)return 0;out[n]=0;return 1;}l->pos=0;l->size=(unsigned)r;l->total+=(unsigned)r;if(l->total>2*1024*1024)return -1;}unsigned char c=l->b[l->pos++];if(n+1>=cap)return -1;out[n++]=(char)c;if(c=='\n'){out[n]=0;return 1;}}}
static int exact(const char*a,const char*b){while(*b&&*a==*b){a++;b++;}return !*b&&(!*a||*a=='\n');}
static uintptr_t hex(const char**p){uintptr_t v=0;unsigned n=0;for(;;){unsigned c=(unsigned char)**p;if(c>='0'&&c<='9')c-='0';else if(c>='a'&&c<='f')c=c-'a'+10;else break;if(++n>8)return 0;v=v*16+c;(*p)++;}return v;}
static const char*fields(const char*p,unsigned n){for(unsigned i=0;i<n;i++){while(*p==' ')p++;while(*p&&*p!=' '&&*p!='\n')p++;}while(*p==' ')p++;return p;}
static int mapline(const char*p,uintptr_t*lo,uintptr_t*hi,unsigned*off,const char**perm,const char**name){*lo=hex(&p);if(*p++!='-')return 0;*hi=hex(&p);if(!*lo||*hi<=*lo||*p++!=' ')return 0;*perm=p;p=fields(p,1);*off=(unsigned)hex(&p);*name=fields(p,2);return 1;}
/* Device/inode matching catches aliases as well as the literal path. */
static int identity(const char *line,char out[48]) {
 const char*p=fields(line,3);unsigned n=0;
 for(unsigned field=0;field<2;field++){
  if(field)out[n++]=' ';
  while(*p&&*p!=' '&&*p!='\n'){if(n>=46)return 0;out[n++]=*p++;}
  if(!n)return 0;while(*p==' ')p++;
 }
 out[n]=0;return 1;
}
static int viewname(const char *p){const char*q=view_path;while(*q&&*q==*p){q++;p++;}return !*q&&(!*p||*p=='\n'||*p==' ');}
static void procpath(char*out,unsigned pid,const char*suffix){char tmp[12];unsigned n=0,k=0;const char*p="/proc/";while(*p)out[k++]=*p++;do{unsigned q=(unsigned)(((uint64_t)pid*0xcccccccdull)>>35);tmp[n++]=(char)('0'+pid-q*10);pid=q;}while(pid);while(n)out[k++]=tmp[--n];while(*suffix)out[k++]=*suffix++;out[k]=0;}
static int maps_pid(Work*w,unsigned pid,int self){char path[48],s[512];procpath(path,pid,"/maps");long fd=w->sys(w->ctx,OPEN,(long)path,O_NOFOLLOW,0,0,0,0);if(fd==-2&&!self)return 1;if(fd<0)return 0;Lines l;zero(&l,sizeof l);l.w=w;l.fd=(int)fd;int r,ok=1;unsigned seen=0;while((r=line(&l,s,sizeof s))>0){uintptr_t lo,hi;unsigned off;const char*perm,*name;if(!mapline(s,&lo,&hi,&off,&perm,&name)){ok=0;break;}char id[48];if(!identity(s,id)){ok=0;break;}int named=viewname(name),matched=w->fileid[0]&&exact(id,w->fileid);if(!named&&!matched)continue;if(self&&named&&!w->fileid[0]){unsigned j=0;do{w->fileid[j]=id[j];}while(id[j++]);}if(!self){w->r->other_mappings++;ok=0;break;}if(perm[0]!='r'||perm[1]!='-'||perm[2]!='x'||perm[3]!='p')continue;if(off==0){if(w->r->view_base&&w->r->view_base!=lo){ok=0;break;}w->r->view_base=(uint32_t)lo;}for(unsigned i=0;i<3;i++){uintptr_t at=(uintptr_t)w->r->view_base+offsets[i];if(lo<=at&&at<=hi&&hi-at>=4096&&off+at-lo==offsets[i])seen|=1u<<i;}}if(r<0)ok=0;if(!closefd(w,(int)fd))ok=0;return ok&&(!self||(seen==7&&!(w->r->view_base&4095)));}
static int census(Work*w){if(!maps_pid(w,w->r->pid,1))return 0;int fd=(int)sc(w,OPEN,(long)"/proc",O_DIRECTORY|O_NOFOLLOW,0,0,0,0);if(fd<0)return 0;unsigned count=0;int ok=1;unsigned char dir[4096];for(;;){long n=sc(w,GETDENTS64,fd,(long)dir,sizeof dir,0,0,0);if(n<0||(unsigned)n>sizeof dir){ok=0;break;}if(!n)break;unsigned at=0;while(at<(unsigned)n){if((unsigned)n-at<20){ok=0;break;}unsigned len=dir[at+16]|((unsigned)dir[at+17]<<8);if(len<20||len>(unsigned)n-at){ok=0;break;}unsigned pid=0,k=19;int digits=1,ended=0;for(;k<len;k++){unsigned c=dir[at+k];if(!c){ended=1;break;}if(c<'0'||c>'9'||pid>100000000u){digits=0;break;}pid=pid*10+c-'0';}if(digits&&ended&&pid&&pid!=w->r->pid){if(++count>4096||!maps_pid(w,pid,0)){ok=0;break;}}at+=len;}if(!ok)break;}if(!closefd(w,fd))ok=0;return ok;}
static int mount_is(Work*w,int ro){int fd=(int)sc(w,OPEN,(long)"/proc/self/mounts",O_NOFOLLOW,0,0,0,0);if(fd<0)return 0;Lines l;zero(&l,sizeof l);l.w=w;l.fd=fd;char s[512];unsigned found=0;int n;const char*want=ro?"/dev/nflasha15 /usr ext2 ro,relatime,errors=continue 0 0":"/dev/nflasha15 /usr ext2 rw,relatime,errors=continue 0 0";while((n=line(&l,s,sizeof s))>0)if(exact(s,want))found++;int ok=n==0&&found==1;if(!closefd(w,fd))ok=0;return ok;}
static int remount(Work*w,int ro){return sc(w,MOUNT,(long)"/dev/nflasha15",(long)"/usr",(long)"ext2",32|(1<<21)|(ro?1:0),(long)"errors=continue",0)==0;}
static int kb4(const char *line,const char *key) {
 while(*key&&*line==*key){line++;key++;}if(*key)return 0;
 while(*line==' '||*line=='\t')line++;
 if(*line++!='4')return 0;while(*line==' '||*line=='\t')line++;
 return exact(line,"kB");
}
static int private_page(Work*w,uintptr_t page){
 char s[512];int fd=(int)sc(w,OPEN,(long)"/proc/self/smaps",O_NOFOLLOW,0,0,0,0);if(fd<0)return 0;
 Lines l;zero(&l,sizeof l);l.w=w;l.fd=fd;int n,found=0,dirty=0,anon=0,active=0;
 while((n=line(&l,s,sizeof s))>0){uintptr_t lo,hi;unsigned off;const char*perm,*name;
  if(mapline(s,&lo,&hi,&off,&perm,&name)){
   active=lo==page&&hi==page+4096&&same(perm,"rwxp",4)&&exact(name,view_path);
   if(active)found++;
  }else if(active){if(kb4(s,"Private_Dirty:"))dirty=1;if(kb4(s,"Anonymous:"))anon=1;}
 }
 int ok=n==0&&found==1&&dirty&&anon;if(!closefd(w,fd))ok=0;return ok;
}
/* Linux 3.0 bit61 is reserved, not a file/anon flag. Only presence and swap
 * are portable here; COW ownership is established by isolated-VMA smaps. */
static int pagemap_present(Work*w,uintptr_t page){uint32_t entry[2];int fd=(int)sc(w,OPEN,(long)"/proc/self/pagemap",O_NOFOLLOW,0,0,0,0);if(fd<0)return 0;int ok=readat(w,fd,(unsigned)(page>>12)*8,entry,8);if(!closefd(w,fd))ok=0;return ok&&(entry[1]&0xc0000000u)==0x80000000u;}
static int protect_rx(Work*w,uintptr_t page){
 /* A failed syscall has no effect; bounded retries restore RX after any
  * later verification failure as well as transient protection errors. */
 for(unsigned j=0;j<3;j++)if(sc(w,MPROTECT,page,4096,5,0,0,0)==0)return 1;
 w->r->status=-5;return 0;
}
static int page_matches(Work*w,unsigned i){
 const unsigned char*expected=w->b->pages[i];
 if(w->booted_new){
  for(unsigned j=0;j<4096;j++)w->buffer[j]=expected[j];
  for(unsigned j=0;j<4;j++){const NmaPatch*p=&w->b->patches[j];
   if(p->offset>=offsets[i]&&p->offset-offsets[i]<4096)
    for(unsigned k=0;k<p->size;k++)w->buffer[p->offset-offsets[i]+k]=p->after[k];
  }
  expected=w->buffer;
 }
 return same((const void*)((uintptr_t)w->r->view_base+offsets[i]),expected,4096);
}
static int shadow(Work*w,unsigned i){
 uintptr_t page=(uintptr_t)w->r->view_base+offsets[i];volatile unsigned char*p=(void*)page;
 if(!page_matches(w,i))return 0;
 if(sc(w,MPROTECT,page,4096,7,0,0,0))return 0;
 unsigned char value=*p;*p=value;
 int ok=private_page(w,page);if(!protect_rx(w,page))return 0;
 return ok&&pagemap_present(w,page)&&page_matches(w,i);
}
static int snapshot_same(Work*w){for(unsigned i=0;i<3;i++)if(!page_matches(w,i)||!pagemap_present(w,(uintptr_t)w->r->view_base+offsets[i]))return 0;return 1;}
void nma_bundle_sha(const NmaBundle*b,unsigned char out[32]){Sha256 s;sha_init(&s);static const unsigned char domain[]="A7M3-4.04-cow-activate-v1";sha_update(&s,domain,sizeof domain);sha_update(&s,(const unsigned char*)b,sizeof *b);sha_finish(&s,out);}
static int journal(Work*w,unsigned phase){struct{uint32_t magic,seq,phase,cow,written;unsigned char bundle[32],digest[32];}r;r.magic=0x41374641;r.seq=++w->sequence;r.phase=phase;r.cow=w->r->cow_mask;r.written=w->r->written_mask;for(unsigned i=0;i<32;i++)r.bundle[i]=w->r->bundle_sha[i];Sha256 s;sha_init(&s);sha_update(&s,(unsigned char*)&r,sizeof r-32);sha_finish(&s,r.digest);w->r->phase=phase;return writeall(w,w->journal,&r,sizeof r)&&sc(w,FSYNC,w->journal,0,0,0,0,0)==0;}
static int valid_bundle(const NmaBundle*b){static const unsigned loc[4]=NMA_PATCH_OFFSETS;static const unsigned size[4]={44,80,4,4};if(b->version!=1||b->view_size!=10854816)return 0;for(unsigned i=0;i<3;i++)if(!b->required[i].size||b->required[i].size>1024*1024)return 0;for(unsigned i=0;i<4;i++){if(b->patches[i].offset!=loc[i]||b->patches[i].size!=size[i])return 0;unsigned pg=i<2?2:i==2?1:0;if(loc[i]<offsets[pg]||loc[i]-offsets[pg]>4096-size[i]||!same(b->patches[i].before,b->pages[pg]+loc[i]-offsets[pg],size[i]))return 0;}return 1;}
/* A recovery may see a torn range, but every byte must be one of its two
 * attested versions; masking those ranges must reproduce the full old hash. */
static int known_view(Work*w,int mixed){
 if(!mixed)return hashfile(w,view_path,w->b->view_size,w->b->view_before);
 int fd=(int)sc(w,OPEN,(long)view_path,O_NOFOLLOW,0,0,0,0);if(fd<0)return 0;
 Sha256 h;sha_init(&h);unsigned used=0;int ok=1;unsigned char digest[32];
 for(;;){long n=sc(w,READ,fd,(long)w->buffer,sizeof w->buffer,0,0,0);
  if(n<0||(unsigned)n>sizeof w->buffer){ok=0;break;}if(!n)break;
  if(used>w->b->view_size||(unsigned)n>w->b->view_size-used){ok=0;break;}
  for(unsigned j=0;j<4;j++){const NmaPatch*p=&w->b->patches[j];
   for(unsigned k=0;k<p->size;k++){unsigned at=p->offset+k;if(at<used||at-used>=(unsigned)n)continue;
    unsigned char current=w->buffer[at-used];if(current!=p->before[k]&&current!=p->after[k])ok=0;
    w->buffer[at-used]=p->before[k];
   }
  }
  sha_update(&h,w->buffer,(unsigned)n);used+=(unsigned)n;
 }
 sha_finish(&h,digest);if(!closefd(w,fd))ok=0;
 return ok&&used==w->b->view_size&&same(digest,w->b->view_before,32);
}
static int sync_setting(Work*w){int fd=(int)sc(w,OPEN,(long)"/setting",O_DIRECTORY|O_NOFOLLOW,0,0,0,0);if(fd<0)return 0;int ok=sc(w,FSYNC,fd,0,0,0,0,0)==0;if(!closefd(w,fd))ok=0;return ok;}
static int restore_readonly(Work*w){for(unsigned j=0;j<3;j++)if(remount(w,1)&&mount_is(w,1)){w->r->readonly_confirmed=1;w->remounted=0;return 1;}w->r->status=-4;return 0;}
int nma_run(const NmaBundle*b,const unsigned char expected[32],NmaSyscall sys,void*ctx,int mode,NmaReport*r){
 if(!b||!expected||!sys||!r||mode<0||mode>4)return -1;
 zero(r,sizeof *r);r->magic=0x41374e41;r->version=1;r->status=-1;
 if(__sync_lock_test_and_set(&busy,1)){r->status=-2;return -2;}
 Work w;zero(&w,sizeof w);w.b=b;w.sys=sys;w.ctx=ctx;w.r=r;w.journal=w.view=-1;w.booted_new=mode>=3;
 nma_bundle_sha(b,r->bundle_sha);
 if(!valid_bundle(b)||!same(expected,r->bundle_sha,32))goto done;
 r->phase=1;
 if(sc(&w,GETEUID,0,0,0,0,0,0)!=0||!mount_is(&w,1))goto done;
 long pid=sc(&w,GETPID,0,0,0,0,0,0);if(pid<=1)goto done;r->pid=(unsigned)pid;
 if(!census(&w))goto done;r->phase=2;
 if(mode==3?!hashfile(&w,view_path,b->view_size,b->view_after):!known_view(&w,mode==2||mode==4)){r->status=-10;goto done;}
 for(unsigned i=0;i<3;i++)if(!hashfile(&w,required[i],b->required[i].size,b->required[i].sha)){r->status=-11-(int)i;goto done;}
 for(unsigned i=0;i<3;i++)if(!page_matches(&w,i)){r->status=-20-(int)i;goto done;}
 r->phase=3;
 if(!mode){r->status=0;r->readonly_confirmed=1;goto done;}
 const char*jp=mode==4?NMA_UNDO_RECOVERY_JOURNAL:mode==3?NMA_UNDO_JOURNAL:mode==2?NMA_RECOVERY_JOURNAL:NMA_JOURNAL;
 w.journal=(int)sc(&w,OPEN,(long)jp,O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW,0600,0,0,0);
 if(w.journal<0||!journal(&w,10)||!sync_setting(&w))goto done;
 if(!census(&w))goto done;
 for(unsigned i=0;i<3;i++){
  if(!shadow(&w,i))goto done;r->cow_mask|=1u<<i;
  if(!journal(&w,20+i))goto done;
 }
 if(!snapshot_same(&w)||(mode==3?!hashfile(&w,view_path,b->view_size,b->view_after):!known_view(&w,mode>=2)))goto done;
 if(!remount(&w,0))goto done;w.remounted=1;
 if(!mount_is(&w,0)||!journal(&w,30))goto restore;
 w.view=(int)sc(&w,OPEN,(long)view_path,O_RDWR|O_NOFOLLOW,0,0,0,0);if(w.view<0)goto restore;
 for(unsigned step=0;step<4;step++){
  unsigned i=mode>=2?3-step:step;const NmaPatch*p=&b->patches[i];
  if(!journal(&w,40+step*2)||!snapshot_same(&w)||!readat(&w,w.view,p->offset,w.buffer,p->size))goto rollback;
  for(unsigned k=0;k<p->size;k++)if(w.buffer[k]!=p->before[k]&&!(mode>=2&&w.buffer[k]==p->after[k]))goto rollback;
  r->written_mask|=1u<<i;const unsigned char*target=mode>=2?p->before:p->after;
  if(!writeat(&w,p->offset,target,p->size)||!readat(&w,w.view,p->offset,w.buffer,p->size)||!same(w.buffer,target,p->size)||!journal(&w,41+step*2))goto rollback;
 }
 if(!snapshot_same(&w)||!hashfile(&w,view_path,b->view_size,mode>=2?b->view_before:b->view_after))goto rollback;
 r->status=0;goto restore;
rollback:
 r->rollback_ok=1;
 for(int i=3;i>=0;i--)if(mode>=2||(r->written_mask&(1u<<i))){const NmaPatch*p=&b->patches[i];if(!writeat(&w,p->offset,p->before,p->size))r->rollback_ok=0;}
 if(!hashfile(&w,view_path,b->view_size,b->view_before)||!snapshot_same(&w))r->rollback_ok=0;
 journal(&w,90);
restore:
 if(w.view>=0){if(!closefd(&w,w.view))r->status=-1;w.view=-1;}
 restore_readonly(&w);
 if(!journal(&w,r->status==0?100:99))r->status=-1;
done:
 if(w.remounted)restore_readonly(&w);
 if(w.view>=0&&!closefd(&w,w.view))r->status=-1;
 if(w.journal>=0&&!closefd(&w,w.journal))r->status=-1;
 __sync_lock_release(&busy);return r->status;
}
