/* Four bounded pre-encode candidate counters/snapshots. No image writes. */
#include <linux/module.h>
#include <linux/init.h>
#include <linux/kernel.h>
#include <linux/kallsyms.h>
#include <linux/stop_machine.h>
#include <linux/smp.h>
#include <linux/uaccess.h>
#include <linux/atomic.h>
#include <asm/traps.h>
#include <asm/ptrace.h>
#include <asm/cacheflush.h>
#include "capture-pins.h"
#define UDF_WORD 0xaa76f7f0U
static unsigned int report[368];
static int count = ARRAY_SIZE(report), disarmed;
static bool arm;
module_param_array(report, uint, &count, 0444);
module_param(arm, bool, 0400);
static atomic_t total = ATOMIC_INIT(0);
static atomic_t hits[4], sampled[4];
static atomic_t last_busy = ATOMIC_INIT(0);
static unsigned self_hits;
static void (*register_hook)(struct undef_hook *), (*unregister_hook)(struct undef_hook *);
extern unsigned a7_undef_test(void);
extern char a7_undef_test_site[], a7_bridge_0[], a7_bridge_1[], a7_bridge_2[], a7_bridge_3[];
static char *bridges[] = {a7_bridge_0,a7_bridge_1,a7_bridge_2,a7_bridge_3};

/* Only metadata reads. No image addresses are dereferenced. */
static int read_metadata(void *dest, unsigned long address, unsigned size)
{
    if (address < 0x60000000UL || address > 0x80000000UL-size) return -ERANGE;
    return probe_kernel_read(dest, (void *)address, size);
}
#define DETAIL_READ read_metadata
#define DETAIL_BARRIER() smp_wmb()
#include "capture_detail_record.h"
void a7_multi_record(unsigned index, const unsigned int *regs)
{
    unsigned n;
    if (index >= 4) return;
    report[2]=atomic_inc_return(&total);
    n=atomic_inc_return(hits+index);
    if(index==1)report[9]=n;
    if(index==0){
        unsigned mode=0;
        if(!read_metadata(&mode,regs[0]+0x20,4))report[8]=mode;
    }
    if(index!=1)return;
    if(!atomic_cmpxchg(sampled+1,0,1))detail_snapshot(report+16,regs,n);
    if(!atomic_cmpxchg(&last_busy,0,1)){
        detail_snapshot(report+192,regs,n);
        smp_wmb();atomic_set(&last_busy,0);
    }
}
static int on_undef(struct pt_regs *regs,unsigned int insn)
{
    unsigned i;
    if(insn!=UDF_WORD)return 1;
    if(regs->ARM_pc==(unsigned long)a7_undef_test_site){self_hits++;regs->ARM_pc+=4;return 0;}
    for(i=0;i<4;i++)if(regs->ARM_pc==capture_sites[i]){
        regs->ARM_pc=(unsigned long)bridges[i]&~1UL;return 0;
    }
    return 1;
}
static struct undef_hook hook={.instr_mask=~0U,.instr_val=UDF_WORD,
    .cpsr_mask=MODE_MASK|PSR_T_BIT,.cpsr_val=SVC_MODE|PSR_T_BIT,.fn=on_undef};
static void sync_code(void *unused)
{
    unsigned i;(void)unused;
    for(i=0;i<4;i++)flush_icache_range(capture_sites[i],capture_sites[i]+4);
}
static int patch_sites(void *restore)
{
    unsigned i;
    for(i=0;i<4;i++)if(*(volatile unsigned *)capture_sites[i]!=(restore?UDF_WORD:native_words[i]))return -ESTALE;
    for(i=0;i<4;i++)*(volatile unsigned *)capture_sites[i]=restore?native_words[i]:UDF_WORD;
    sync_code(NULL);return 0;
}
static int disarm_set(const char *val,const struct kernel_param *kp)
{
    int n,err;(void)kp;
    if(kstrtoint(val,0,&n)||n!=1)return -EINVAL;
    if(!arm||disarmed)return 0;
    err=stop_machine(patch_sites,(void *)1,NULL);if(err)return err;
    on_each_cpu(sync_code,NULL,1);
    disarmed=1;report[5]=1;return 0;
}
static const struct kernel_param_ops disarm_ops={.set=disarm_set,.get=param_get_int};
module_param_cb(disarm,&disarm_ops,&disarmed,0600);
static int __init capture_init(void)
{
    unsigned i;int err;
    for(i=0;i<ARRAY_SIZE(code_pins);i++)if(memcmp((void *)code_pins[i].address,code_pins[i].bytes,code_pins[i].size))return -ENODEV;
    if(kallsyms_lookup_name("register_undef_hook")!=0x601118acUL || kallsyms_lookup_name("unregister_undef_hook")!=0x601118f4UL)return -ENODEV;
    register_hook=(void *)0x601118acUL;unregister_hook=(void *)0x601118f4UL;
    report[0]=0x4137434b;report[3]=1;report[6]=sizeof(struct module);report[7]=capture_sites[0];report[8]=4;
    for(i=0;i<4;i++){report[12+i]=source_id[i];atomic_set(hits+i,0);atomic_set(sampled+i,0);}
    register_hook(&hook);
    if(a7_undef_test()!=0x7a76 || self_hits!=1){unregister_hook(&hook);return -EINVAL;}
    report[4]=self_hits;if(!arm)return 0;
    __module_get(THIS_MODULE);report[1]=1;
    err=stop_machine(patch_sites,NULL,NULL);
    if(err){module_put(THIS_MODULE);unregister_hook(&hook);return err;}
    on_each_cpu(sync_code,NULL,1);report[11]=1;return 0;
}
static void __exit capture_exit(void){unregister_hook(&hook);}
module_init(capture_init);module_exit(capture_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Temporary read-only JPEG submission candidate recorder");
