/* report[24..37]: original registers; [40..171]: encoder object;
 * [176..215]: stage state; [224..255]: unit before; [256..267]: extent;
 * [272..303]: unit after. No DMM calls, leases, cache operations or pixel reads. */
#include "dmm-pins.h"
static unsigned long dmm_open, dmm_root;
static int early_read(void *out,unsigned long address,unsigned size)
{
    if(address<0x50000000UL || size>0x1000 || address>0x80000000UL-size)return -ERANGE;
    return probe_kernel_read(out,(void *)address,size);
}
static int source_publish(void)
{
    unsigned char bytes[sizeof(dmm_open_pin)];int err;
    dmm_open=kallsyms_lookup_name("dmm_unit_ctrl_Open");
    err=early_read(bytes,dmm_open,sizeof(bytes));if(err)return err;
    if(memcmp(bytes,dmm_open_pin,sizeof(bytes)))return -ENODEV;
    err=early_read(&dmm_root,dmm_open+0x188,4);if(err)return err;
    if(dmm_root<0x50000000UL || dmm_root>0x80000000UL-0x74310)return -ERANGE;
    report[19]=dmm_open;report[20]=dmm_root;
    return 0;
}
static void source_remove(void){}
static int take_early_record(const unsigned *regs)
{
    unsigned handle,unit,extent,index;int err;
    memcpy(report+24,regs,14*4);
    err=early_read(report+40,regs[0],132*4);if(err)return err;
    err=early_read(report+176,regs[0]+0x470,40*4);if(err)return err;
    handle=report[40+0x84/4]&0xffff;
    /* Native parsers 0x85a4/0x85d8: bit 15 extends index, not generation.
     * Native Open limits the decoded index to 0x580 records. */
    index=(handle&0x3ff)+((handle>>15)<<10);
    if(index>=0x580)return -ERANGE;
    unit=dmm_root+index*0x150+0xb10;
    report[21]=handle;report[22]=unit;
    err=early_read(report+224,unit,128);if(err)return err;
    /* The generation must match before following the extent pointer. */
    if(((report[228]>>24)&255)!=((handle>>10)&31))return -ESTALE;
    if((report[229]>>16)!=1)return -EINVAL;
    extent=report[230];report[23]=extent;
    err=early_read(report+256,extent,48);if(err)return err;
    err=early_read(report+272,unit,128);if(err)return err;
    if(memcmp(report+224,report+272,128))return -EAGAIN;
    return 0;
}
