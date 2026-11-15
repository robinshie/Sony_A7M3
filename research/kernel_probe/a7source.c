/* Bounded read-only current capture-source sample. No hooks, cache changes or pixel writes. */
#include <linux/module.h>
#include <linux/init.h>
#include <linux/kernel.h>
#include <linux/sysfs.h>
#include <linux/uaccess.h>
#include <linux/jiffies.h>
#include "pins.h"
extern unsigned long arch_phys_to_va(unsigned long);
#define OBJECT 0x641b6f10UL
#define BASE 0x1a000000UL
#define CAPACITY 0x03000000UL
#define ROW 12160U
#define SMALL 1520U
static struct {
 unsigned magic,version;int status;unsigned rows,va,base,stride,step;
 unsigned object[100],after[5];int reads[64];unsigned char data[64*SMALL];
} sample;
static unsigned char line[ROW];
static int copy(void *out,unsigned long address,unsigned n)
{
 if(address<0x60000000UL||address>0x80000000UL-n)return -ERANGE;
 return probe_kernel_read(out,(void *)address,n);
}
static int matches(unsigned descriptor,unsigned base,unsigned capacity,unsigned geometry,unsigned pitch)
{
 return (descriptor&255)==1 && base==BASE && capacity==CAPACITY && geometry==0x0fa01770 && pitch==0x0fa017c0;
}
static ssize_t sample_read(struct file *file,struct kobject *obj,struct bin_attribute *attr,char *out,loff_t offset,size_t size)
{
 (void)file;(void)obj;(void)attr;
 if(offset<0)return -EINVAL;
 if(offset>=sizeof(sample))return 0;
 if(size>sizeof(sample)-offset)size=sizeof(sample)-offset;
 memcpy(out,(char *)&sample+offset,size);return size;
}
static struct bin_attribute sample_attr={.attr={.name="sample",.mode=0400},.size=sizeof(sample),.read=sample_read};
static int take_source_sample(void)
{
 unsigned i,j,g;unsigned long start,va;
 if(memcmp((void *)0x60118470,kernel_pin,sizeof(kernel_pin)) || memcmp((void *)0x6390618c,stage_pin,sizeof(stage_pin)) ||
    *(volatile unsigned *)0x6475a218!=0x635c6000 || *(volatile unsigned *)0x635c6014!=0x635c60b4)return -ENODEV;
 sample.magic=0x4137534b;sample.version=1;sample.status=-1;sample.base=BASE;sample.stride=ROW;sample.step=128;
 if(copy(sample.object,OBJECT,sizeof(sample.object)))goto publish;
 sample.status=-2;
 if(!matches(sample.object[47],sample.object[48],sample.object[49],sample.object[36],sample.object[37]))goto publish;
 va=arch_phys_to_va(BASE);sample.va=va;
 sample.status=-3;
 if(va<0x60000000UL || va>0x80000000UL-CAPACITY || (31*128+1)*ROW+ROW>CAPACITY)goto publish;
 start=jiffies;
 for(i=0;i<64;i++){
  unsigned row=(i/2)*128+i%2;
  sample.status=-4;if(time_after_eq(jiffies,start+HZ))goto publish;
  sample.reads[i]=copy(line,va+row*ROW,ROW);
  sample.status=-5;if(sample.reads[i])goto publish;
  for(g=0;g<ROW/32;g++)for(j=0;j<4;j++)sample.data[i*SMALL+g*4+j]=line[g*32+j];
  sample.rows=i+1;
 }
 sample.status=-6;
 if(copy(sample.after,OBJECT+0xbc,12) || copy(sample.after+3,OBJECT+0x90,8))goto publish;
 if(matches(sample.after[0],sample.after[1],sample.after[2],sample.after[3],sample.after[4]))sample.status=0;
publish:
 return 0;
}
static int source_publish(void){return sysfs_create_bin_file(&THIS_MODULE->mkobj.kobj,&sample_attr);}
static void source_remove(void){sysfs_remove_bin_file(&THIS_MODULE->mkobj.kobj,&sample_attr);}
#ifndef A7_SOURCE_CALLBACK
static int __init source_init(void){int err=take_source_sample();return err?err:source_publish();}
static void __exit source_exit(void){source_remove();}
module_init(source_init);module_exit(source_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("One-shot current capture source inspection without a frame lease");

#endif
