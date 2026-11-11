/* Linux ARM integration fixture. Real mmap/mprotect/procfs/page cache; only
 * mount state and selected fault responses are mocked. Never a camera tool. */
#include "native_menu_activate.c"
#include "binding.h"
extern const NmaBundle nma_input;
static unsigned checks;
static int ro=1,viewfd=-1,fail_patch=-1,fail_step,fail_sync,shadow_fail,other_fake,other_sent,bad_maps,rx_fail,ro_fail;
static unsigned writes,protects,mounts,viewpos;
static unsigned char temp[4096];
static long raw(long n,long a,long b,long c,long d,long e,long f){return nma_linux_syscall(0,n,a,b,c,d,e,f);}
static unsigned length(const char*s){unsigned n=0;while(s[n])n++;return n;}
static void say(const char*s){raw(4,1,(long)s,length(s),0,0,0);}
static void number(unsigned n){char b[12];unsigned i=0;do{unsigned q=(unsigned)(((uint64_t)n*0xcccccccdull)>>35);b[i++]=(char)('0'+n-q*10);n=q;}while(n);while(i)raw(4,1,(long)&b[--i],1,0,0,0);}
static void fail(unsigned line){say("NMA_FAIL line ");number(line);say("\n");raw(1,99,0,0,0,0,0);for(;;){}}
#define CHECK(x) do{checks++;if(!(x))fail(__LINE__);}while(0)
static void output(const NmaReport*r){say("report status ");number((unsigned)(r->status<0?-r->status:r->status));say(" phase ");number(r->phase);say(" error ");number((unsigned)(r->first_error<0?-r->first_error:r->first_error));say(" cow ");number(r->cow_mask);say(" writes ");number(r->written_mask);say("\n");}
static int stringeq(const char*a,const char*b){while(*a&&*a==*b){a++;b++;}return *a==*b;}
static int ends(const char*s,const char*t){unsigned n=length(s),m=length(t);return n>=m&&stringeq(s+n-m,t);}
static long shim(void*ctx,long n,long a,long b,long c,long d,long e,long f){(void)ctx;
 if(n==OPEN){const char*p=(const char*)a;
  if(stringeq(p,"/proc/self/mounts"))a=(long)(ro?"/test-mounts-ro":"/test-mounts-rw");
  if(shadow_fail&&stringeq(p,"/proc/self/smaps"))a=(long)"/test-empty";
  if(other_fake&&stringeq(p,"/proc/98765/maps"))a=(long)"/test-other-maps";
  if(bad_maps&&ends(p,"/maps")&&!stringeq(p,"/proc/98765/maps"))a=(long)"/test-badmaps";
  long result=raw(n,a,b,c,d,e,f);
  if(stringeq(p,view_path)&&(b&3)==O_RDWR)viewfd=(int)result;
  return result;
 }
 if(n==MOUNT){mounts++;if(d&1){if(ro_fail){ro_fail--;return -5;}ro=1;}else ro=0;return 0;}
 if(n==MPROTECT){protects++;if(c==5&&rx_fail){rx_fail--;return -5;}return raw(n,a,b,c,d,e,f);}
 if(n==GETDENTS64&&other_fake&&!other_sent){other_sent=1;unsigned char*p=(void*)b;zero(p,32);p[16]=32;p[18]=4;const char*s="98765";for(unsigned j=0;j<6;j++)p[19+j]=s[j];return 32;}
 if(n==LSEEK&&a==viewfd&&c==0)viewpos=(unsigned)b;
 if(n==WRITE&&a==viewfd){writes++;
  if(fail_patch>=0){const NmaPatch*p=&nma_input.patches[fail_patch];
   if(viewpos==p->offset&&!fail_step){fail_step=1;long k=raw(n,a,b,c/2,d,e,f);if(k>0)viewpos+=(unsigned)k;return k;}
   if(fail_step==1){fail_step=2;return -5;}
  }
  long k=raw(n,a,b,c,d,e,f);if(k>0)viewpos+=(unsigned)k;return k;
 }
 if(n==FSYNC&&a==viewfd&&fail_sync){fail_sync=0;return -5;}
 if(n==CLOSE&&a==viewfd)viewfd=-1;
 return raw(n,a,b,c,d,e,f);
}
static void reset_counters(void){writes=protects=mounts=0;viewfd=-1;fail_patch=-1;fail_step=fail_sync=shadow_fail=other_fake=other_sent=bad_maps=rx_fail=ro_fail=0;CHECK(ro==1);raw(10,(long)NMA_JOURNAL,0,0,0,0,0);raw(10,(long)NMA_RECOVERY_JOURNAL,0,0,0,0,0);raw(10,(long)NMA_UNDO_JOURNAL,0,0,0,0,0);raw(10,(long)NMA_UNDO_RECOVERY_JOURNAL,0,0,0,0,0);}
static void mount_view(void){int fd=(int)raw(5,(long)view_path,0,0,0,0,0);CHECK(fd>=0);CHECK(raw(192,0x20000000,nma_input.view_size,5,0x12,fd,0)==0x20000000);CHECK(raw(6,fd,0,0,0,0,0)==0);}
static int old_ram(void){for(unsigned i=0;i<3;i++)if(!same((void*)(uintptr_t)(0x20000000+offsets[i]),nma_input.pages[i],4096))return 0;return 1;}
static void file_patch(unsigned i,int after,unsigned count){const NmaPatch*p=&nma_input.patches[i];int fd=(int)raw(5,(long)view_path,2,0,0,0,0);CHECK(fd>=0);CHECK(raw(19,fd,p->offset,0,0,0,0)==(long)p->offset);CHECK(raw(4,fd,(long)(after?p->after:p->before),count?count:p->size,0,0,0)==(long)(count?count:p->size));CHECK(raw(118,fd,0,0,0,0,0)==0);CHECK(raw(6,fd,0,0,0,0,0)==0);}
static int hash_view(int after){NmaReport r;Work w;zero(&r,sizeof r);zero(&w,sizeof w);w.sys=shim;w.r=&r;return hashfile(&w,view_path,nma_input.view_size,after?nma_input.view_after:nma_input.view_before);}
static void makefile(const char*path,const void*data,unsigned size){int fd=(int)raw(5,(long)path,1|64|512,0600,0,0,0);CHECK(fd>=0);CHECK(raw(4,fd,(long)data,size,0,0,0)==(long)size);CHECK(raw(6,fd,0,0,0,0,0)==0);}
__attribute__((constructor)) static void test(void){
 CHECK(sizeof(NmaBundle)==13140);CHECK(sizeof(NmaReport)==80);
 CHECK(raw(5,(long)"/proc/mounts",O_NOFOLLOW,0,0,0,0)==-40);
 int mountsfd=(int)raw(5,(long)"/proc/self/mounts",O_NOFOLLOW,0,0,0,0);CHECK(mountsfd>=0);CHECK(raw(6,mountsfd,0,0,0,0,0)==0);
 say("NMA_PROC_MOUNTS_SYMLINK_REGRESSION_PASS\n");
 const char*roline="/dev/nflasha15 /usr ext2 ro,relatime,errors=continue 0 0\n";
 const char*rwline="/dev/nflasha15 /usr ext2 rw,relatime,errors=continue 0 0\n";
 makefile("/test-mounts-ro",roline,length(roline));makefile("/test-mounts-rw",rwline,length(rwline));
 makefile("/test-empty","",0);makefile("/test-badmaps","broken\n",7);
 const char*other="20000000-20a5b000 r-xp 00000000 00:01 999 /usr/lib/viewUnified2.so\n";makefile("/test-other-maps",other,length(other));
 CHECK(kb4("Anonymous:      4 kB\n","Anonymous:"));CHECK(kb4("Private_Dirty:\t4 kB\n","Private_Dirty:"));CHECK(!kb4("Anonymous: 40 kB\n","Anonymous:"));
 uintptr_t lo,hi;unsigned off;const char*perm,*name;CHECK(mapline(other,&lo,&hi,&off,&perm,&name));CHECK(lo==0x20000000&&hi==0x20a5b000&&off==0&&same(perm,"r-xp",4)&&exact(name,view_path));
 char id[48];CHECK(identity(other,id)&&stringeq(id,"00:01 999"));
 mount_view();NmaReport r;
 reset_counters();CHECK(nma_run(&nma_input,nma_expected,shim,0,0,&r)==0);CHECK(r.phase==3&&r.view_base==0x20000000&&r.readonly_confirmed);CHECK(!writes&&!protects&&!mounts);say("NMA_PREFLIGHT_PASS\n");
 reset_counters();other_fake=1;CHECK(nma_run(&nma_input,nma_expected,shim,0,1,&r)<0);CHECK(r.other_mappings==1&&!writes&&!protects&&!mounts);say("NMA_OTHER_PROCESS_REFUSED\n");
 reset_counters();bad_maps=1;CHECK(nma_run(&nma_input,nma_expected,shim,0,1,&r)<0);CHECK(!writes&&!protects&&!mounts);say("NMA_MALFORMED_MAPS_REFUSED\n");
 reset_counters();shadow_fail=1;CHECK(nma_run(&nma_input,nma_expected,shim,0,1,&r)<0);CHECK(r.phase==10&&!writes&&protects==2&&!mounts);CHECK(old_ram()&&hash_view(0));say("NMA_SHADOW_FAILURE_REFUSED\n");
 for(unsigned i=0;i<4;i++){
  reset_counters();fail_patch=(int)i;CHECK(nma_run(&nma_input,nma_expected,shim,0,1,&r)<0);output(&r);CHECK(fail_step==2&&r.rollback_ok&&r.readonly_confirmed&&r.cow_mask==7);CHECK(old_ram()&&hash_view(0));
 }
 say("NMA_ALL_PARTIAL_WRITES_ROLLED_BACK\n");
 reset_counters();fail_sync=1;CHECK(nma_run(&nma_input,nma_expected,shim,0,1,&r)<0);CHECK(r.rollback_ok&&r.readonly_confirmed&&old_ram()&&hash_view(0));say("NMA_FSYNC_FAILURE_ROLLED_BACK\n");
 reset_counters();rx_fail=1;ro_fail=1;CHECK(nma_run(&nma_input,nma_expected,shim,0,1,&r)==0);output(&r);CHECK(r.cow_mask==7&&r.written_mask==15&&r.phase==100&&r.readonly_confirmed);CHECK(old_ram()&&hash_view(1));
 int fd=(int)raw(5,(long)view_path,0,0,0,0,0);CHECK(fd>=0);CHECK(raw(192,0x30000000,nma_input.view_size,5,0x12,fd,0)==0x30000000);CHECK(raw(6,fd,0,0,0,0,0)==0);
 for(unsigned i=0;i<4;i++){const NmaPatch*p=&nma_input.patches[i];CHECK(same((void*)(uintptr_t)(0x30000000+p->offset),p->after,p->size));}
 CHECK(raw(91,0x30000000,nma_input.view_size,0,0,0,0)==0);CHECK(old_ram());say("NMA_COW_VFS_ACTIVATION_PASS\n");
 reset_counters();CHECK(nma_run(&nma_input,nma_expected,shim,0,0,&r)<0);CHECK(!writes&&!protects&&!mounts);
 reset_counters();CHECK(nma_run(&nma_input,nma_expected,shim,0,2,&r)==0);CHECK(r.phase==100&&r.readonly_confirmed&&hash_view(0)&&old_ram());say("NMA_INDEPENDENT_RECOVERY_PASS\n");
 for(unsigned i=0;i<4;i++)file_patch(i,1,nma_input.patches[i].size/2);
 reset_counters();CHECK(nma_run(&nma_input,nma_expected,shim,0,1,&r)<0);CHECK(!writes&&!protects&&!mounts);
 reset_counters();CHECK(nma_run(&nma_input,nma_expected,shim,0,2,&r)==0);CHECK(r.phase==100&&r.readonly_confirmed&&hash_view(0)&&old_ram());say("NMA_TORN_MIXED_RECOVERY_PASS\n");
 /* Model a cold boot by replacing the old mapping with the new file. */
 for(unsigned i=0;i<4;i++)file_patch(i,1,0);
 CHECK(raw(91,0x20000000,nma_input.view_size,0,0,0,0)==0);mount_view();
 reset_counters();CHECK(nma_run(&nma_input,nma_expected,shim,0,2,&r)<0);CHECK(!writes&&!protects&&!mounts);
 reset_counters();CHECK(nma_run(&nma_input,nma_expected,shim,0,3,&r)==0);CHECK(hash_view(0)&&r.phase==100&&r.cow_mask==7&&r.readonly_confirmed);
 for(unsigned i=0;i<4;i++){const NmaPatch*p=&nma_input.patches[i];CHECK(same((void*)(uintptr_t)(0x20000000+p->offset),p->after,p->size));}
 say("NMA_POSTBOOT_DEACTIVATION_PASS\n");
 for(unsigned i=0;i<4;i++)file_patch(i,1,nma_input.patches[i].size/2);
 reset_counters();CHECK(nma_run(&nma_input,nma_expected,shim,0,3,&r)<0);CHECK(!writes&&!protects&&!mounts);
 reset_counters();CHECK(nma_run(&nma_input,nma_expected,shim,0,4,&r)==0);CHECK(hash_view(0)&&r.phase==100&&r.cow_mask==7&&r.readonly_confirmed);
 for(unsigned i=0;i<4;i++){const NmaPatch*p=&nma_input.patches[i];CHECK(same((void*)(uintptr_t)(0x20000000+p->offset),p->after,p->size));}
 say("NMA_POSTBOOT_TORN_RECOVERY_PASS\n");
 CHECK(raw(91,0x20000000,nma_input.view_size,0,0,0,0)==0);mount_view();
 /* A foreign changed byte cannot be normalized into our old-file hash. */
 fd=(int)raw(5,(long)view_path,2,0,0,0,0);CHECK(fd>=0);CHECK(raw(19,fd,4096,0,0,0,0)==4096);CHECK(raw(3,fd,(long)temp,1,0,0,0)==1);temp[0]^=0x80;CHECK(raw(19,fd,4096,0,0,0,0)==4096);CHECK(raw(4,fd,(long)temp,1,0,0,0)==1);CHECK(raw(6,fd,0,0,0,0,0)==0);
 reset_counters();CHECK(nma_run(&nma_input,nma_expected,shim,0,2,&r)<0);CHECK(!writes&&!protects&&!mounts);say("NMA_FOREIGN_CHANGE_REFUSED\n");
 say("NMA_ALL_PASS checks=");number(checks);say("\n");
}
