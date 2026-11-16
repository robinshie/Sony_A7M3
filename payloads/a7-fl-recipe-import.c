/* Fixed settings transaction. Uses the same inactive-slot writer as Save. */
#include "a7-fl-posix.h"
#include <stdint.h>

static int matches(const struct a7_fl_store_io *io,unsigned slot,const uint8_t expected[128]){
    uint8_t current[128];unsigned size=0;
    if(io->read(io->opaque,slot,current,sizeof current,&size)||size!=sizeof current)return 0;
    for(unsigned i=0;i<sizeof current;i++)if(current[i]!=expected[i])return 0;
    return 1;
}

/* Rows 0/1 are preferences; 2/3 are work records. Check all four again in
 * the target process before writing. The active slot remains the fallback. */
int a7_fl_import_slot(const struct a7_fl_store_io *prefs,const struct a7_fl_store_io *work,
                      const uint8_t before[4][128],unsigned target,const uint8_t after[128]){
    if(target>1)return -1;
    for(unsigned i=0;i<2;i++){
        if(!matches(prefs,i,before[i])||!matches(work,i,before[i+2]))return -2;
    }
    if(prefs->replace(prefs->opaque,target,before[target],128,1,after))return -3;
    if(!matches(prefs,target,after)||!matches(prefs,1-target,before[1-target])||
       !matches(work,0,before[2])||!matches(work,1,before[3]))return -4;
    return 0;
}

#ifdef A7_RECIPE_BOUND
#include "recipe-data.h"
static long sys(long n,long a,long b,long c){
    register long r7 __asm__("r7")=n,r0 __asm__("r0")=a,r1 __asm__("r1")=b,r2 __asm__("r2")=c;
    __asm__ volatile("svc #0":"+r"(r0):"r"(r7),"r"(r1),"r"(r2):"memory","cc");
    return r0;
}
__attribute__((constructor)) static void import_recipe(void){
    /* Reserve a unique report before any setting mutation. */
    static const char path[]="/tmp/jiritsu/a7recipe.bin";
    long fd=sys(5,(long)path,1|64|128|0x8000,0600);
    if(fd<0)return;
    struct a7_fl_store_io prefs,work;
    a7_fl_posix_io(&prefs);a7_fl_posix_worklog_io(&work);
    int32_t out[2]={0x41375249,a7_fl_import_slot(&prefs,&work,before,target,after)};
    long written=sys(4,fd,(long)out,sizeof out);
    long closed=sys(6,fd,0,0);
    if(written!=sizeof out||closed)sys(10,(long)path,0,0);
}
#endif
