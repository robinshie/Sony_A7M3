/* One-shot capture experiment. Only A7_GRAIN enables a bounded pixel edit. */
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
#ifdef A7_GRAIN_BANKS
#define UDF_WORD 0xaa7ff7f0U
#define TEST_RETURN 0x7a7f
#elif defined(A7_GRAIN_REPEAT)
#define UDF_WORD 0xaa7ef7f0U
#define TEST_RETURN 0x7a7e
#elif defined(A7_GRAIN_FAST)
#define UDF_WORD 0xaa7df7f0U
#define TEST_RETURN 0x7a7d
#elif defined(A7_GRAIN_FULL)
#define UDF_WORD 0xaa7cf7f0U
#define TEST_RETURN 0x7a7c
#elif defined(A7_GRAIN)
#define UDF_WORD 0xaa7bf7f0U
#define TEST_RETURN 0x7a7b
#elif defined(A7_LEASE)
#define UDF_WORD 0xaa7af7f0U
#define TEST_RETURN 0x7a7a
#elif defined(A7_EARLY)
#define UDF_WORD 0xaa79f7f0U
#define TEST_RETURN 0x7a79
#else
#define UDF_WORD 0xaa78f7f0U
#define TEST_RETURN 0x7a78
#endif
static unsigned int report[368];
static int count = ARRAY_SIZE(report), disarmed;
static bool arm;
module_param_array(report, uint, &count, 0444);
module_param(arm, bool, 0400);
static atomic_t total = ATOMIC_INIT(0);
static atomic_t hits[4], sampled[4];
static unsigned self_hits;
static void (*register_hook)(struct undef_hook *), (*unregister_hook)(struct undef_hook *);
extern unsigned a7_undef_test(void);
extern char a7_undef_test_site[], a7_bridge_0[], a7_bridge_1[], a7_bridge_2[], a7_bridge_3[];
static char *bridges[] = {a7_bridge_0,a7_bridge_1,a7_bridge_2,a7_bridge_3};

#ifdef A7_GRAIN_REPEAT
#include <linux/jiffies.h>
#include "capture_repeat_control.h"
#endif
#ifdef A7_LEASE
#include "capture_lease_record.h"
#elif defined(A7_EARLY)
#include "capture_early_record.h"
#else
#define A7_SOURCE_CALLBACK 1
#include "a7source.c"
#endif
#ifdef A7_GRAIN
#include "capture_grain_record.h"
#endif
static void capture_remove(void)
{
#ifdef A7_GRAIN
    grain_remove();
#endif
    source_remove();
}
void a7_multi_record(unsigned index,const unsigned int *regs)
{
    unsigned n;int err;
    if(index!=2 || regs[0]!=0x641b6f10U)return;
#ifdef A7_GRAIN_REPEAT
    if(atomic_cmpxchg(sampled+2,0,1))return;
    n=atomic_inc_return(&total);report[2]=n;report[16]=n;
    frame_selection=ACCESS_ONCE(selection);
    report[353]=frame_selection;
    if(!(frame_selection>>4)||!(frame_selection&15)){
        report[356]=++skipped;report[17]=0;report[344]=0;report[349]=0;
        smp_mb();atomic_set(sampled+2,0);return;
    }
    memset(report+305,0,47*sizeof(unsigned));
    frame_seed=seed_for_frame(n,(unsigned)jiffies);report[354]=frame_seed;
#else
    n=atomic_inc_return(&total);report[2]=n;report[16]=n;
    if(atomic_cmpxchg(sampled+2,0,1))return;
#endif
    report[17]=2;
#ifdef A7_EARLY
    err=take_early_record(regs);
#ifdef A7_LEASE
    if(!err)err=take_lease_test();
#endif
    report[18]=err;
#else
    err=take_source_sample();
    report[18]=err?err:sample.status;report[19]=sample.rows;
    report[20]=sample.va;report[21]=sample.base;
#endif
    smp_wmb();report[17]=3;
#ifdef A7_GRAIN_REPEAT
    if(err){report[357]=++failed;ACCESS_ONCE(selection)=0;}
    else report[355]=++completed;
    smp_mb();atomic_set(sampled+2,0);
#endif
}
static int on_undef(struct pt_regs *regs,unsigned int insn)
{
    unsigned i;
    if(insn!=UDF_WORD)return 1;
    if(regs->ARM_pc==(unsigned long)a7_undef_test_site){self_hits++;regs->ARM_pc+=4;return 0;}
    for(i=2;i<3;i++)if(regs->ARM_pc==capture_sites[i]){
        regs->ARM_pc=(unsigned long)bridges[i]&~1UL;return 0;
    }
    return 1;
}
static struct undef_hook hook={.instr_mask=~0U,.instr_val=UDF_WORD,
    .cpsr_mask=MODE_MASK|PSR_T_BIT,.cpsr_val=SVC_MODE|PSR_T_BIT,.fn=on_undef};
static void sync_code(void *unused)
{
    unsigned i;(void)unused;
    for(i=2;i<3;i++)flush_icache_range(capture_sites[i],capture_sites[i]+4);
}
static int patch_sites(void *restore)
{
    unsigned i;
    for(i=2;i<3;i++)if(*(volatile unsigned *)capture_sites[i]!=(restore?UDF_WORD:native_words[i]))return -ESTALE;
    for(i=2;i<3;i++)*(volatile unsigned *)capture_sites[i]=restore?native_words[i]:UDF_WORD;
    sync_code(NULL);return 0;
}
static int disarm_set(const char *val,const struct kernel_param *kp)
{
    int n,err;(void)kp;
    if(kstrtoint(val,0,&n)||n!=1)return -EINVAL;
    if(!arm||disarmed)return 0;
#ifdef A7_GRAIN_REPEAT
    if(atomic_cmpxchg(sampled+2,0,1))return -EBUSY;
#endif
    err=stop_machine(patch_sites,(void *)1,NULL);
    if(err){
#ifdef A7_GRAIN_REPEAT
        atomic_set(sampled+2,0);
#endif
        return err;
    }
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
    report[0]=0x4137434b;report[3]=1;report[6]=sizeof(struct module);report[7]=capture_sites[2];report[8]=1;
    for(i=0;i<4;i++){report[12+i]=source_id[i];atomic_set(hits+i,0);atomic_set(sampled+i,0);}
    err=source_publish();if(err)return err;
#ifdef A7_GRAIN
    err=grain_publish();if(err){capture_remove();return err;}
#endif
    register_hook(&hook);
    if(a7_undef_test()!=TEST_RETURN || self_hits!=1){unregister_hook(&hook);capture_remove();return -EINVAL;}
    report[4]=self_hits;if(!arm)return 0;
    __module_get(THIS_MODULE);report[1]=1;
    err=stop_machine(patch_sites,NULL,NULL);
    if(err){module_put(THIS_MODULE);unregister_hook(&hook);capture_remove();return err;}
    on_each_cpu(sync_code,NULL,1);report[11]=1;return 0;
}
static void __exit capture_exit(void){unregister_hook(&hook);capture_remove();}
module_init(capture_init);module_exit(capture_exit);
MODULE_LICENSE("GPL");
#ifdef A7_GRAIN_REPEAT
MODULE_DESCRIPTION("Temporary repeated capture grain with atomic selection; source pixel writes");
#elif defined(A7_GRAIN)
MODULE_DESCRIPTION("Temporary one-shot capture grain experiment; source pixel writes");
#elif defined(A7_LEASE)
MODULE_DESCRIPTION("Temporary source exclusive Open/Close test; no pixel writes");
#else
MODULE_DESCRIPTION("Temporary in-call read-only source sampler; no image writes");
#endif
