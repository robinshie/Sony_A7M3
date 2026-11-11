#include "a7-fl-posix.h"
#include <stdint.h>
#ifndef A7_FL_POSIX_TEST
static long call3(long nr,long a,long b,long c) {
    register long r7 __asm__("r7")=nr;
    register long r0 __asm__("r0")=a;
    register long r1 __asm__("r1")=b;
    register long r2 __asm__("r2")=c;
    __asm__ volatile("svc #0":"+r"(r0):"r"(r7),"r"(r1),"r"(r2):"memory","cc");return r0;
}
#else
extern long a7_fl_test_syscall(long,long,long,long);
#define call3 a7_fl_test_syscall
#endif
static const char *const paths[2]={"/setting/A7FL0.CFG","/setting/A7FL1.CFG"};
/* ARM overrides asm-generic: Linux arch/arm/include/asm/fcntl.h, v2.6.35.
 * O_NOFOLLOW=0100000 octal. 0x20000 means O_LARGEFILE on ARM. */
enum { A7_O_NOFOLLOW=0x8000, A7_O_NONBLOCK=0x800 };
static int equal(const unsigned char *a,const unsigned char *b,unsigned n) {
    while(n--)if(*a++!=*b++)return 0;
    return 1;
}
/* ARM Linux struct stat64: mode@16, size@48; request104bytes aligned8. */
static int bounded_regular(long fd,unsigned *size) {
    union {uint64_t align;unsigned char bytes[104];} st;
    for(unsigned i=0;i<104;i++)st.bytes[i]=0;
    if(call3(197,fd,(long)st.bytes,0))return -1;
    uint32_t mode=0;uint64_t n=0;
    for(unsigned i=0;i<4;i++)mode|=(uint32_t)st.bytes[16+i]<<(8*i);
    for(unsigned i=0;i<8;i++)n|=(uint64_t)st.bytes[48+i]<<(8*i);
    if((mode&0xf000)!=0x8000 || n>129)return -2;
    *size=(unsigned)n;return 0;
}
static int read_fd(long fd,unsigned char *out,unsigned cap,unsigned *length) {
    unsigned size;if(bounded_regular(fd,&size)||size>cap)return -1;
    unsigned n=0;
    while(n<size){long r=call3(3,fd,(long)(out+n),size-n);if(r<=0)return -2;n+=(unsigned)r;}
    unsigned char extra;long eof=call3(3,fd,(long)&extra,1);
    if(eof!=0)return -3;
    *length=n;return 0;
}
static int read_slot(void *ctx,unsigned slot,unsigned char *out,unsigned cap,unsigned *n) {
    (void)ctx;if(slot>1||!out||!n)return -1;*n=0;
    long fd=call3(5,(long)paths[slot],A7_O_NOFOLLOW|A7_O_NONBLOCK,0);
    if(fd==-2)return 1;
    if(fd<0)return -2;
    int rc=read_fd(fd,out,cap,n);if(call3(6,fd,0,0)&&!rc)rc=-4;return rc;
}
static int replace_slot(void *ctx,unsigned slot,const unsigned char *before,unsigned before_size,
                        int existed,const unsigned char after[128]) {
    (void)ctx;if(slot>1||!after||before_size>128||(existed&&!before))return -1;
    /* Never O_TRUNC before checking the exact inactive preimage. */
    long fd=call3(5,(long)paths[slot],2|A7_O_NOFOLLOW|A7_O_NONBLOCK|(existed?0:64|128),0600);
    if(fd<0)return -2;
    int rc=-3;unsigned char check[129];unsigned size=0;
    if(read_fd(fd,check,129,&size)||size!=before_size||(existed&&!equal(before,check,size)))goto done;
    if(call3(19,fd,0,0)!=0)goto done;
    for(unsigned n=0;n<128;) {
        long wrote=call3(4,fd,(long)(after+n),128-n);
        if(wrote<=0)goto done;
        n+=(unsigned)wrote;
    }
    if(call3(93,fd,128,0)||call3(118,fd,0,0))goto done;
    if(call3(19,fd,0,0)!=0||read_fd(fd,check,129,&size)||size!=128||!equal(after,check,128))goto done;
    rc=0;
done:
    if(call3(6,fd,0,0)&&!rc)rc=-4;
    return rc;
}
void a7_fl_posix_io(struct a7_fl_store_io *io) {
    if(io){io->read=read_slot;io->replace=replace_slot;io->opaque=0;}
}
