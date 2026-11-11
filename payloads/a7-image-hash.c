/* Fixed-path, read-only ARM O_DIRECT hash. Writes only a small temporary report. */
#include "sha256.h"
static inline long call3(long nr,long a,long b,long c){
    register long r7 __asm__("r7")=nr;register long r0 __asm__("r0")=a;
    register long r1 __asm__("r1")=b;register long r2 __asm__("r2")=c;
    __asm__ volatile("svc #0":"+r"(r0):"r"(r7),"r"(r1),"r"(r2):"memory","cc");return r0;
}
static unsigned char buffer[4096] __attribute__((aligned(4096)));
static struct {uint32_t magic;int32_t status;uint32_t bytes;unsigned char digest[32];} result;
__attribute__((constructor)) static void inspect(void){
    result.magic=0x41374948;
    /* ARM's O_DIRECT is 0x10000; 0x4000 is O_DIRECTORY on this ABI. */
    long fd=call3(5,(long)"/usr/share/app/image_cmn_43.uxc",0x10000,0);
    result.status=fd<0?(int)fd:-1;
    if(fd>=0){
        Sha256 hash;sha_init(&hash);
        for(;;){
            long n=call3(3,fd,(long)buffer,sizeof buffer);
            if(n<0){result.status=(int)n;break;}
            if(!n){result.status=result.bytes==26481288?0:-2;break;}
            if((unsigned)n>sizeof buffer||result.bytes+(unsigned)n>26481288){result.status=-3;break;}
            sha_update(&hash,buffer,(unsigned)n);result.bytes+=(unsigned)n;
            /* The final short read may leave an unaligned EOF position. */
            if(result.bytes==26481288){result.status=0;break;}
            if(n!=sizeof buffer){result.status=-4;break;}
        }
        sha_finish(&hash,result.digest);call3(6,fd,0,0);
    }
    call3(10,(long)"/tmp/jiritsu/libJit.so",0,0);
    fd=call3(5,(long)"/tmp/jiritsu/a7imagehash.bin",1|64|128,0600);
    if(fd>=0){
        unsigned done=0;
        while(done<sizeof result){long n=call3(4,fd,(long)((unsigned char *)&result+done),sizeof result-done);if(n<=0)break;done+=(unsigned)n;}
        call3(6,fd,0,0);
    }
}
