/* Guarded sector transaction. Activation sector is last; restore reverses it.
 * Firmware bytes come only from this camera's verified local image build. */
#include <stdint.h>
#include "creative-sectors.h"
#ifndef ACTION
#define ACTION 0
#endif
#ifndef TEST_FAIL_AFTER
#define TEST_FAIL_AFTER 0
#endif
static inline long sc(long n,long a,long b,long c) {
    register long r7 __asm__("r7")=n;
    register long r0 __asm__("r0")=a;
    register long r1 __asm__("r1")=b;
    register long r2 __asm__("r2")=c;
    __asm__ volatile("svc #0":"+r"(r0):"r"(r7),"r"(r1),"r"(r2):"memory","cc");
    return r0;
}
static struct {
    uint32_t magic,action,status;
    int32_t error,capacity,header_ok,preimage,written,readback_ok,rollback_ok;
    uint8_t current[COUNT][512];
} report;
static uint8_t initial[COUNT][512],header[2048];
static int same(const uint8_t *a,const uint8_t *b,unsigned n) {
    for(unsigned i=0;i<n;i++)if(a[i]!=b[i])return 0;
    return 1;
}
static long transfer(long fd,unsigned offset,void *data,int write) {
    if(sc(19,fd,offset,0)!=offset)return -1;
    unsigned done=0;
    while(done<512) {
        long got=sc(write?4:3,fd,(long)((uint8_t *)data+done),512-done);
        if(got<=0)return got?got:-2;
        done+=got;
    }
    return done;
}
static int read_all(long fd) {
    for(unsigned i=0;i<COUNT;i++)
        if(transfer(fd,offsets[i],report.current[i],0)!=512)return 0;
    return 1;
}
__attribute__((constructor)) static void update(void) {
    report.magic=0x41374346;report.action=ACTION;
    long rep=sc(5,(long)"/tmp/jiritsu/a7creative.bin",1|64|128,0600);
    if(rep<0)return;
    long fd=sc(5,(long)"/dev/nflasha15",ACTION?2|0x101000:0,0);
    uint64_t capacity=0;
    unsigned touched[COUNT],attempts=0;
    if(fd<0){report.error=fd;goto output;}
    if(sc(54,fd,0x80041272,(long)&capacity)||!capacity) {
        long end=sc(19,fd,0,2);if(end>0)capacity=(uint32_t)end;
    }
    if(capacity!=300*1024*1024){report.error=-10;goto close;}
    report.capacity=capacity;
    if(sc(19,fd,0,0)||sc(3,fd,(long)header,2048)!=2048||!same(header,expected_header,2048))
        {report.error=-11;goto close;}
    report.header_ok=1;
    if(!read_all(fd)){report.error=-12;goto close;}
    int all_before=1,all_after=1,known=1;
    for(unsigned i=0;i<COUNT;i++) {
        int b=same(report.current[i],before[i],512),a=same(report.current[i],after[i],512);
        all_before&=b;all_after&=a;known&=b||a;
        for(unsigned j=0;j<512;j++)initial[i][j]=report.current[i][j];
    }
    report.preimage=all_before?1:all_after?2:known?3:0;
    if(ACTION==0){report.status=1;report.readback_ok=1;goto close;}
    if((ACTION==1&&!all_before)||(ACTION==2&&!known)){report.error=-13;goto close;}
    for(unsigned order=0;order<COUNT;order++) {
        unsigned i=ACTION==1?order:COUNT-1-order;
        const uint8_t *expected=ACTION==1?after[i]:before[i];
        if(same(initial[i],expected,512))continue;
        touched[attempts++]=i;
        if(transfer(fd,offsets[i],(void *)expected,1)!=512){report.error=-20;goto rollback;}
        report.written++;
        if(sc(118,fd,0,0)){report.error=-21;goto rollback;}
        if(transfer(fd,offsets[i],report.current[i],0)!=512||!same(report.current[i],expected,512))
            {report.error=-22;goto rollback;}
        if(TEST_FAIL_AFTER&&report.written==TEST_FAIL_AFTER){report.error=-90;goto rollback;}
    }
    if(!read_all(fd)){report.error=-23;goto rollback;}
    for(unsigned i=0;i<COUNT;i++)if(!same(report.current[i],ACTION==1?after[i]:before[i],512))
        {report.error=-24;goto rollback;}
    report.readback_ok=1;report.status=1;goto close;
rollback:
    report.rollback_ok=1;
    while(attempts) {
        unsigned i=touched[--attempts];
        if(transfer(fd,offsets[i],initial[i],1)!=512||sc(118,fd,0,0))report.rollback_ok=0;
    }
    if(!read_all(fd))report.rollback_ok=0;
    for(unsigned i=0;i<COUNT;i++)if(!same(report.current[i],initial[i],512))report.rollback_ok=0;
close:
    sc(6,fd,0,0);
output:
    sc(10,(long)"/tmp/jiritsu/libJit.so",0,0);
    unsigned done=0;
    while(done<sizeof report) {
        long n=sc(4,rep,(long)((uint8_t *)&report+done),sizeof report-done);
        if(n<=0)break;
        done+=n;
    }
    sc(118,rep,0,0);sc(6,rep,0,0);
}
