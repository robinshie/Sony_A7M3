/* Filesystem-only installer: no raw metadata, no executable patch, no reboot. */
#include "native_install.h"
#include "../payloads/sha256.h"
enum { N_OPEN=5,N_CLOSE=6,N_READ=3,N_WRITE=4,N_LINK=9,N_UNLINK=10,N_MOUNT=21,
       N_EUID=49,N_IOCTL=54,N_STATFS=99,N_FSYNC=118,N_CAPGET=184,N_RENAME=38 };
enum { O_WRONLY=1,O_CREAT=64,O_EXCL=128,O_DIRECTORY=0x4000,O_NOFOLLOW=0x8000 };
static const char *const final_path[3]={"/usr/lib/a7fl.so","/usr/share/app/string_simplifiedchinese.uxc","/usr/share/app/string_english.uxc"};
static const char *const stage_path[3]={"/usr/lib/.a7fl.new","/usr/share/app/.a7fl-zh.new","/usr/share/app/.a7fl-en.new"};
static const char *const backup_path[2]={"/usr/share/app/.a7fl-zh.orig","/usr/share/app/.a7fl-en.orig"};
static const char journal_path[]="/setting/A7FL.INSTALL";
static volatile int busy;
typedef struct {
    const NativeInstallBundle *bundle;NativeInstallSyscall sys;void *context;
    NativeInstallReport *report;int journal,remounted;unsigned sequence;
    unsigned char buffer[4096];
} Install;
static int same(const void *aa,const void *bb,unsigned n){const unsigned char *a=aa,*b=bb;while(n--)if(*a++!=*b++)return 0;return 1;}
static int any(const unsigned char *p,unsigned n){while(n--)if(*p++)return 1;return 0;}
static void zero(void *p,unsigned n){unsigned char *s=p;while(n--)*s++=0;}
static long call(Install *i,long n,long a,long b,long c,long d,long e){long r=i->sys(i->context,n,a,b,c,d,e,0);if(r<0&&!i->report->first_error)i->report->first_error=(int)r;return r;}
static void hash32(Sha256 *s,uint32_t n){unsigned char b[4];for(unsigned j=0;j<4;j++)b[j]=(unsigned char)(n>>(8*j));sha_update(s,b,4);}
void native_install_bundle_sha(const NativeInstallBundle *b,unsigned char out[32]){
    Sha256 s;sha_init(&s);static const unsigned char domain[]="A7M3-4.04-filesystem-stage-v1";
    sha_update(&s,domain,sizeof domain);hash32(&s,b->version);hash32(&s,b->placeholder);
    sha_update(&s,b->module_attestation,32);
    for(unsigned j=0;j<3;j++){hash32(&s,b->files[j].size);sha_update(&s,b->files[j].sha256,32);}
    for(unsigned j=0;j<2;j++){hash32(&s,b->old_locale_sizes[j]);sha_update(&s,b->old_locale_sha[j],32);}
    hash32(&s,b->view_size);sha_update(&s,b->view_sha,32);sha_finish(&s,out);
}
static int write_all(Install *i,int fd,const unsigned char *p,unsigned size){
    while(size){long n=call(i,N_WRITE,fd,(long)p,size,0,0);if(n<=0||(unsigned)n>size)return 0;p+=n;size-=(unsigned)n;}return 1;
}
static int close_fd(Install *i,int fd){return call(i,N_CLOSE,fd,0,0,0,0)==0;}
static int journal(Install *i,unsigned phase){
    struct {uint32_t magic,sequence,phase,created,published,backed;unsigned char bundle[32],digest[32];} record;
    record.magic=0x4137464a;record.sequence=++i->sequence;record.phase=phase;
    record.created=i->report->created;record.published=i->report->published;record.backed=i->report->backed_up;
    for(unsigned j=0;j<32;j++)record.bundle[j]=i->report->bundle_sha[j];
    Sha256 s;sha_init(&s);sha_update(&s,(unsigned char *)&record,sizeof record-32);sha_finish(&s,record.digest);
    i->report->phase=phase;
    return write_all(i,i->journal,(unsigned char *)&record,sizeof record)&&call(i,N_FSYNC,i->journal,0,0,0,0)==0;
}
static int sync_dir(Install *i,const char *path){
    long fd=call(i,N_OPEN,(long)path,O_DIRECTORY|O_NOFOLLOW,0,0,0);if(fd<0)return 0;
    int ok=call(i,N_FSYNC,fd,0,0,0,0)==0;if(!close_fd(i,fd))ok=0;return ok;
}
static int absent(Install *i,const char *path){
    long fd=i->sys(i->context,N_OPEN,(long)path,O_NOFOLLOW,0,0,0,0);
    if(fd==-2)return 1;if(fd>=0)close_fd(i,fd);return 0;
}
static int hash_file(Install *i,const char *path,uint32_t size,const unsigned char expected[32]){
    long fd=call(i,N_OPEN,(long)path,O_NOFOLLOW,0,0,0);if(fd<0)return 0;
    Sha256 s;sha_init(&s);unsigned used=0;int ok=1;unsigned char digest[32];
    for(;;){long n=call(i,N_READ,fd,(long)i->buffer,sizeof i->buffer,0,0);
        if(n<0||(unsigned)n>sizeof i->buffer){ok=0;break;}if(!n)break;
        if((unsigned)n>size-used){ok=0;break;}sha_update(&s,i->buffer,(unsigned)n);used+=(unsigned)n;}
    sha_finish(&s,digest);if(!close_fd(i,fd))ok=0;
    return ok&&used==size&&same(digest,expected,32);
}
static int mount_is(Install *i,int read_only){
    long fd=call(i,N_OPEN,(long)"/proc/mounts",0,0,0,0);if(fd<0)return 0;
    unsigned used=0;int ok=1;
    for(;;){if(used==sizeof i->buffer-1){ok=0;break;}
        long n=call(i,N_READ,fd,(long)i->buffer+used,sizeof i->buffer-1-used,0,0);
        if(n<0||(unsigned)n>sizeof i->buffer-1-used){ok=0;break;}if(!n)break;used+=(unsigned)n;}
    if(!close_fd(i,fd))ok=0;if(!ok)return 0;i->buffer[used]=0;
    const char *wanted=read_only?"/dev/nflasha15 /usr ext2 ro,relatime,errors=continue 0 0\n":"/dev/nflasha15 /usr ext2 rw,relatime,errors=continue 0 0\n";
    unsigned length=0;while(wanted[length])length++;unsigned matches=0;
    for(unsigned j=0;j+length<=used;j++)if((!j||i->buffer[j-1]=='\n')&&same(i->buffer+j,wanted,length))matches++;
    return matches==1;
}
static int remount(Install *i,int ro){
    return call(i,N_MOUNT,(long)"/dev/nflasha15",(long)"/usr",(long)"ext2",32|(1<<21)|(ro?1:0),(long)"errors=continue")==0;
}
static int preflight(Install *i){
    if(call(i,N_EUID,0,0,0,0,0)!=0||!mount_is(i,1))return 0;
    uint32_t header[2]={0x20080522,0},caps[6],stat[16];zero(caps,sizeof caps);zero(stat,sizeof stat);
    if(call(i,N_CAPGET,(long)header,(long)caps,0,0,0)<0||!(caps[0]&(1u<<21)))return 0;
    long fd=call(i,N_OPEN,(long)"/dev/nflasha15",0,0,0,0);int readonly=-1;
    if(fd<0)return 0;int ok=call(i,N_IOCTL,fd,0x125e,(long)&readonly,0,0)==0&&readonly==0;
    if(!close_fd(i,fd))ok=0;if(!ok)return 0;
    if(call(i,N_STATFS,(long)"/usr",(long)stat,0,0,0)<0||stat[0]!=0xef53||stat[1]!=1024||!(stat[11]&1))return 0;
    unsigned needed=16;
    for(unsigned j=0;j<3;j++){unsigned blocks=(i->bundle->files[j].size+1023)/1024;needed+=blocks+2+(blocks+255)/256;}
    if(stat[4]<needed||stat[6]<3)return 0;
    if(!hash_file(i,"/usr/lib/viewUnified2.so",i->bundle->view_size,i->bundle->view_sha)||!absent(i,final_path[0]))return 0;
    for(unsigned j=0;j<3;j++)if(!absent(i,stage_path[j]))return 0;
    for(unsigned j=0;j<2;j++)if(!absent(i,backup_path[j])||!hash_file(i,final_path[j+1],i->bundle->old_locale_sizes[j],i->bundle->old_locale_sha[j]))return 0;
    return 1;
}
static int stage(Install *i,unsigned j){
    long fd=call(i,N_OPEN,(long)stage_path[j],O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW,j?0444:0555,0,0);
    if(fd<0)return 0;i->report->created|=1u<<j;
    int ok=write_all(i,fd,i->bundle->files[j].bytes,i->bundle->files[j].size)&&call(i,N_FSYNC,fd,0,0,0,0)==0;
    if(!close_fd(i,fd))ok=0;
    return ok&&hash_file(i,stage_path[j],i->bundle->files[j].size,i->bundle->files[j].sha256)&&sync_dir(i,j?"/usr/share/app":"/usr/lib");
}
static int rollback(Install *i){
    int ok=1;
    for(int j=1;j>=0;j--)if(i->report->published&(1u<<(j+1))){
        if(!hash_file(i,backup_path[j],i->bundle->old_locale_sizes[j],i->bundle->old_locale_sha[j])||
           call(i,N_RENAME,(long)backup_path[j],(long)final_path[j+1],0,0,0)<0||!sync_dir(i,"/usr/share/app"))ok=0;
        else {i->report->published&=~(1u<<(j+1));i->report->backed_up&=~(1u<<j);}
    }
    if(i->report->published&1){
        if(!hash_file(i,final_path[0],i->bundle->files[0].size,i->bundle->files[0].sha256)||call(i,N_UNLINK,(long)final_path[0],0,0,0,0)<0||!sync_dir(i,"/usr/lib"))ok=0;
        else i->report->published&=~1u;
    }
    for(unsigned j=0;j<3;j++)if(i->report->created&(1u<<j)){
        if(call(i,N_UNLINK,(long)stage_path[j],0,0,0,0)<0)ok=0;else i->report->created&=~(1u<<j);
    }
    if(!sync_dir(i,"/usr/lib")||!sync_dir(i,"/usr/share/app"))ok=0;
    for(unsigned j=0;j<2;j++)if(!hash_file(i,final_path[j+1],i->bundle->old_locale_sizes[j],i->bundle->old_locale_sha[j]))ok=0;
    return ok;
}
int native_install_run(const NativeInstallBundle *b,const unsigned char expected[32],NativeInstallSyscall sys,void *ctx,NativeInstallReport *r){
    if(!b||!expected||!sys||!r)return -1;
    zero(r,sizeof *r);r->magic=0x41374649;r->version=1;r->status=-1;
    if(__sync_lock_test_and_set(&busy,1))return -2;
    Install i;zero(&i,sizeof i);i.bundle=b;i.sys=sys;i.context=ctx;i.report=r;i.journal=-1;int success=0;
    native_install_bundle_sha(b,r->bundle_sha);
    if(b->version!=1||b->placeholder||!any(b->module_attestation,32)||!any(expected,32)||!same(expected,r->bundle_sha,32))goto done;
    for(unsigned j=0;j<3;j++){
        const NativeInstallFile *f=&b->files[j];unsigned char digest[32];Sha256 h;
        if(!f->bytes||!f->size||f->size>1024*1024)goto done;
        sha_init(&h);sha_update(&h,f->bytes,f->size);sha_finish(&h,digest);if(!same(digest,f->sha256,32))goto done;
    }
    if(b->files[0].size<52||!same(b->files[0].bytes,"\177ELF\1\1\1",7)||!same(b->files[0].bytes+16,"\3\0\50\0",4))goto done;
    if(!preflight(&i))goto done;
    i.journal=call(&i,N_OPEN,(long)journal_path,O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW,0600,0,0);
    if(i.journal<0)goto done;
    if(!journal(&i,1)||!sync_dir(&i,"/setting"))goto done;
    if(!remount(&i,0))goto done;i.remounted=1;
    if(!mount_is(&i,0)||!journal(&i,2))goto fail;
    for(unsigned j=0;j<3;j++)if(!journal(&i,10+j)||!stage(&i,j)||!journal(&i,20+j))goto fail;
    /* Link publishes module without overwriting an unexpected existing name. */
    if(!journal(&i,30)||call(&i,N_LINK,(long)stage_path[0],(long)final_path[0],0,0,0)<0)goto fail;
    r->published|=1;
    if(!sync_dir(&i,"/usr/lib")||call(&i,N_UNLINK,(long)stage_path[0],0,0,0,0)<0)goto fail;
    r->created&=~1u;if(!sync_dir(&i,"/usr/lib")||!journal(&i,31))goto fail;
    for(unsigned j=0;j<2;j++){
        if(!journal(&i,40+j*4)||call(&i,N_LINK,(long)final_path[j+1],(long)backup_path[j],0,0,0)<0)goto fail;
        r->backed_up|=1u<<j;
        if(!sync_dir(&i,"/usr/share/app")||!hash_file(&i,backup_path[j],b->old_locale_sizes[j],b->old_locale_sha[j])||!journal(&i,41+j*4))goto fail;
        if(call(&i,N_RENAME,(long)stage_path[j+1],(long)final_path[j+1],0,0,0)<0)goto fail;
        r->created&=~(1u<<(j+1));r->published|=1u<<(j+1);
        if(!sync_dir(&i,"/usr/share/app")||!journal(&i,42+j*4))goto fail;
    }
    for(unsigned j=0;j<3;j++)if(!hash_file(&i,final_path[j],b->files[j].size,b->files[j].sha256))goto fail;
    if(!hash_file(&i,"/usr/lib/viewUnified2.so",b->view_size,b->view_sha)||!journal(&i,60))goto fail;
    success=1;goto restore_ro;
fail:
    r->rollback_ok=rollback(&i);journal(&i,90);
restore_ro:
    if(remount(&i,1)&&mount_is(&i,1)){r->readonly_confirmed=1;i.remounted=0;}
    else {success=0;r->status=-4;}
    if(!journal(&i,success?100:99))success=0;
done:
    if(i.remounted){if(remount(&i,1)&&mount_is(&i,1))r->readonly_confirmed=1;else r->status=-4;}
    if(i.journal>=0&&!close_fd(&i,i.journal))success=0;
    if(success)r->status=0;else if(r->status!=-4)r->status=-3;
    __sync_lock_release(&busy);return r->status;
}
