#include <stdint.h>
#include <string.h>
#include <stdio.h>
#include <stdlib.h>
#include <errno.h>
static unsigned report[368],reads,fail_at,change_after,cases;
static unsigned object[132],stage[40],unit[32],extent[12];
static unsigned long kallsyms_lookup_name(const char *s){(void)s;return 0x5100889c;}
static int probe_kernel_read(void *,const void *,unsigned);
#include "kernel_probe/capture_early_record.h"
static int probe_kernel_read(void *out,const void *in,unsigned n)
{
    uintptr_t a=(uintptr_t)in;const void *src=NULL;unsigned size=0;
    unsigned root=0x52094678;
    if(++reads==fail_at)return -EFAULT;
    if(a==0x5100889c){src=dmm_open_pin;size=sizeof dmm_open_pin;}
    if(a==0x51008a24){src=&root;size=4;}
    if(a==0x641b6f10){src=object;size=sizeof object;}
    if(a==0x641b7380){src=stage;size=sizeof stage;}
    unsigned h=object[0x84/4]&0xffff,unit_address=root+((h&0x3ff)+((h>>15)<<10))*0x150+0xb10;
    if(a==unit_address){src=unit;size=sizeof unit;}
    if(a==0x53000000){src=extent;size=sizeof extent;}
    if(!src||n>size)return -EFAULT;
    memcpy(out,src,n);
    if(a==0x52095ab8&&change_after&&reads==7)((unsigned *)out)[4]^=0x100;
    return 0;
}
static void check(int ok){if(!ok){fprintf(stderr,"FAIL case %u reads %u\n",cases,reads);exit(1);}}
static void reset(void)
{
    cases++;reads=fail_at=change_after=0;
    memset(report,0,sizeof report);memset(object,0,sizeof object);memset(unit,0,sizeof unit);
    object[0x84/4]=(3u<<10)|7;
    unit[4]=(3u<<24)|(2u<<8);unit[5]=(1u<<16)|2;unit[6]=0x53000000;
    extent[1]=0x1a000000;extent[3]=0x3000000;
}
int main(void)
{
    unsigned regs[14]={0x641b6f10};
    reset();check(!source_publish());check(!take_early_record(regs));check(reads==7);
    check(report[21]==((3u<<10)|7)&&report[22]==0x52095ab8&&report[257]==0x1a000000);
    for(unsigned f=1;f<=7;f++){
        reset();fail_at=f;
        int err=source_publish();if(!err)err=take_early_record(regs);
        check(err==-EFAULT&&reads==f);
    }
    reset();unit[4]^=1u<<24;check(!source_publish());check(take_early_record(regs)==-ESTALE&&reads==5);
    reset();unit[5]=2;check(!source_publish());check(take_early_record(regs)==-EINVAL&&reads==5);
    reset();unit[6]=0x40000000;check(!source_publish());check(take_early_record(regs)==-ERANGE&&reads==5);
    reset();change_after=1;check(!source_publish());check(take_early_record(regs)==-EAGAIN&&reads==7);
    reset();object[0x84/4]|=0x8000;check(!source_publish());check(!take_early_record(regs));
    check(report[22]==0x52095ab8+1024*0x150&&reads==7);
    reset();object[0x84/4]=0x8000|(3<<10)|0x180;check(!source_publish());check(take_early_record(regs)==-ERANGE&&reads==4);
    source_remove();printf("EARLY_RECORD_PASSED cases=%u\n",cases);return 0;
}
