/* Executes the production activation core with ARM Linux mmap/procfs/VFS.
 * Only mount state and injected I/O failures are substituted. */
#include "stock_activate.c"
#include "binding.h"
extern const NmaBundle nma_input;
static unsigned checks,writes;
static int ro=1,writefd=-1,fail_page=-1,fail_phase,shadow_fail;
static unsigned position;
static long raw(long n,long a,long b,long c,long d,long e,long f){return nma_linux_syscall(0,n,a,b,c,d,e,f);}
static unsigned len(const char*s){unsigned n=0;while(s[n])n++;return n;}
static void say(const char*s){raw(4,1,(long)s,len(s),0,0,0);}
static void number(unsigned n){char s[12];unsigned k=0;do{unsigned q=(unsigned)(((uint64_t)n*0xcccccccdull)>>35);s[k++]=(char)('0'+n-q*10);n=q;}while(n);while(k)raw(4,1,(long)&s[--k],1,0,0,0);}
static void failure(unsigned line){say("STOCK_ACT_FAIL ");number(line);say("\n");raw(1,99,0,0,0,0,0);for(;;){}}
#define CHECK(x) do{checks++;if(!(x))failure(__LINE__);}while(0)
static long shim(void*ctx,long n,long a,long b,long c,long d,long e,long f){(void)ctx;
 if(n==OPEN){const char*p=(void*)a;
  if(exact(p,"/proc/self/mounts"))a=(long)(ro?"/mount-ro":"/mount-rw");
  if(shadow_fail&&exact(p,"/proc/self/smaps"))a=(long)"/empty";
  long v=raw(n,a,b,c,d,e,f);if(exact(p,view_path)&&(b&3)==O_RDWR)writefd=(int)v;return v;
 }
 if(n==MOUNT){ro=!!(d&1);return 0;}
 if(n==LSEEK&&a==writefd)position=(unsigned)b;
 if(n==WRITE&&a==writefd){writes++;
  if(fail_page>=0&&position==offsets[fail_page]&&!fail_phase){fail_phase=1;long k=raw(n,a,b,c/2,d,e,f);if(k>0)position+=(unsigned)k;return k;}
  if(fail_phase==1){fail_phase=2;return -5;}
  long k=raw(n,a,b,c,d,e,f);if(k>0)position+=(unsigned)k;return k;
 }
 if(n==CLOSE&&a==writefd)writefd=-1;
 return raw(n,a,b,c,d,e,f);
}
static void create(const char*p,const char*s){int fd=(int)raw(5,(long)p,1|64|512,0600,0,0,0);CHECK(fd>=0);CHECK(raw(4,fd,(long)s,len(s),0,0,0)==(long)len(s));CHECK(!raw(6,fd,0,0,0,0,0));}
static void reset(void){CHECK(ro);writes=0;writefd=-1;fail_page=-1;fail_phase=shadow_fail=0;raw(10,(long)NMA_JOURNAL,0,0,0,0,0);raw(10,(long)NMA_RECOVERY_JOURNAL,0,0,0,0,0);}
static int hashed(int after){Work w;NmaReport r;zero(&w,sizeof w);zero(&r,sizeof r);w.sys=shim;w.r=&r;return hashfile(&w,view_path,nma_input.view_size,after?nma_input.view_after:nma_input.view_before);}
static int old_ram(void){
#if !NMA_CREATE_MAPPING
 for(unsigned i=0;i<NMA_PAGE_COUNT;i++)if(!same((void*)(uintptr_t)(0x20000000+offsets[i]),nma_input.pages[i],4096))return 0;
#endif
 return 1;
}
__attribute__((constructor)) static void test(void){
 CHECK(sizeof(NmaReport)==80);
 create("/mount-ro","/dev/nflasha15 /usr ext2 ro,relatime,errors=continue 0 0\n");
 create("/mount-rw","/dev/nflasha15 /usr ext2 rw,relatime,errors=continue 0 0\n");create("/empty","");
#if !NMA_CREATE_MAPPING
 int fd=(int)raw(5,(long)view_path,0,0,0,0,0);CHECK(fd>=0);
 CHECK(raw(192,0x20000000,nma_input.view_size,5,0x12,fd,0)==0x20000000);CHECK(!raw(6,fd,0,0,0,0,0));
#endif
 NmaReport r;reset();CHECK(!nma_run(&nma_input,nma_expected,shim,0,0,&r));CHECK(!writes&&r.phase==3&&r.readonly_confirmed);say("STOCK_PREFLIGHT_PASS\n");
 reset();shadow_fail=1;CHECK(nma_run(&nma_input,nma_expected,shim,0,1,&r)<0);CHECK(!writes&&hashed(0)&&old_ram());say("STOCK_COW_FAILURE_REFUSED\n");
 for(unsigned i=0;i<NMA_PAGE_COUNT;i++){
  reset();fail_page=(int)i;CHECK(nma_run(&nma_input,nma_expected,shim,0,1,&r)<0);
  CHECK(fail_phase==2&&r.rollback_ok&&r.readonly_confirmed&&hashed(0)&&old_ram());
 }
 say("STOCK_PARTIAL_WRITES_RESTORED\n");
 reset();CHECK(!nma_run(&nma_input,nma_expected,shim,0,1,&r));
 CHECK(r.phase==100&&r.cow_mask==NMA_PAGE_MASK&&r.written_mask==NMA_PAGE_MASK&&r.readonly_confirmed&&hashed(1)&&old_ram());say("STOCK_REAL_VFS_ACTIVATION_PASS\n");
 reset();CHECK(nma_run(&nma_input,nma_expected,shim,0,1,&r)<0);CHECK(!writes);say("STOCK_REPLAY_REFUSED\n");
#if !NMA_CREATE_MAPPING
 reset();CHECK(!nma_run(&nma_input,nma_expected,shim,0,2,&r));CHECK(hashed(0)&&old_ram());say("STOCK_INDEPENDENT_RECOVERY_PASS\n");
 CHECK(!raw(91,0x20000000,nma_input.view_size,0,0,0,0));
#endif
 say("STOCK_ACT_ALL_PASS checks=");number(checks);say("\n");
}
