#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdatomic.h>
#include <errno.h>
static unsigned report[368], calls;
static int disarmed, read_error;
typedef _Atomic int atomic_t;
static atomic_t total, sampled[4];
static int atomic_cmpxchg(atomic_t *p,int before,int after) {
    atomic_compare_exchange_strong(p,&before,after); return before;
}
#define atomic_inc_return(p) (atomic_fetch_add(p,1)+1)
#define atomic_set(p,v) atomic_store(p,v)
#define smp_wmb() atomic_thread_fence(memory_order_release)
#define smp_mb() atomic_thread_fence(memory_order_seq_cst)
#define module_param_array(n,t,c,m) static const void *use_##n __attribute__((unused))=c
#define module_param(n,t,m)
static int take_early_record(const unsigned *regs) {
    calls++; report[24]=regs[0]; report[76]=calls*1000;
    /* Test reentry while this callback is active. */
    extern void a7_multi_record(unsigned,const unsigned *);
    a7_multi_record(2,regs);
    return read_error;
}
#ifdef TEST_LAYOUT
static unsigned extra_reads,extra_fail;
static int early_read(void *out,unsigned long address,unsigned bytes) {
    if(++extra_reads==extra_fail)return -EFAULT;
    memset(out,0,bytes);
    if(address==0x61000000&&bytes==512)((unsigned *)out)[4]=0x62000000;
    else if(address==0x62000000&&bytes==64){((unsigned *)out)[0]=0x64000000;((unsigned *)out)[2]=0x63000000;}
    else if(address==0x63000000&&bytes==384)((unsigned *)out)[0x88/4]=240;
    else if(address==0x64000000&&bytes==128)((unsigned *)out)[4]=3008;
    else if(address==0x641b7120&&bytes==256)((unsigned *)out)[0xc8/4]=1;
    else return -ERANGE;
    return 0;
}
#include "kernel_probe/capture_layout_record.h"
#define take_early_record take_layout_record
#endif
#include "kernel_probe/capture_geometry_record.h"
static void check(int ok) { if(!ok) {fputs("GEOMETRY_FAIL\n",stderr);exit(1);} }
int main(void) {
    unsigned regs[14]={0x641b6f10U};
    regs[6]=0x61000000;
    a7_multi_record(1,regs);check(calls==0);
    regs[0]++;a7_multi_record(2,regs);check(calls==0);regs[0]--;
    disarmed=1;a7_multi_record(2,regs);check(calls==0);disarmed=0;
    report[0]=0x4137434b;report[19]=123;report[20]=456;
    a7_multi_record(2,regs);check(calls==1&&geometry_captured==1&&geometry0[76]==1000);
    read_error=-EFAULT;report[99]=1234;a7_multi_record(2,regs);
    check(calls==2&&geometry_captured==2&&geometry1[18]==(unsigned)-EFAULT&&geometry1[99]==0);
    read_error=0;a7_multi_record(2,regs);check(calls==3&&geometry_captured==3&&geometry2[76]==3000);
    a7_multi_record(2,regs);check(calls==3&&geometry_captured==3);
    check(geometry0[76]==1000&&geometry0[0]==0x4137434b&&geometry2[19]==123&&geometry2[20]==456);
    check(geometry2[16]==3&&geometry2[17]==3&&geometry2[18]==0);
#ifdef TEST_LAYOUT
    check(layout0[2]==0&&layout0[5]==0x62000000&&layout0[6]==0x63000000&&layout0[7]==0x64000000);
    check(layout0[152+0x88/4]==240&&layout0[248+4]==3008&&layout0[280+0xc8/4]==1);
    check(layout1[2]==(unsigned)-EFAULT&&layout2[2]==0);
    for(unsigned fail=1;fail<=5;fail++){
        memset(layout0,0,sizeof layout0);geometry_captured=layout_captured=0;
        extra_reads=0;extra_fail=fail;
        a7_multi_record(2,regs);
        check(layout0[2]==(unsigned)-EFAULT&&geometry0[18]==(unsigned)-EFAULT&&extra_reads==fail);
    }
#endif
    puts("GEOMETRY_RECORDER_PASSED filtering, reentry, capacity, failed-read isolation, immutable slots");
}
