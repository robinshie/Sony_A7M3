/* Temporary, one-shot metadata probe at the original pre-JPEG stage.
 * No pixel access or DMM acquisition. Retained until reboot once armed. */
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

#define SITE 0x6390619cUL
#define UDF_WORD 0xaa73f7f0U
static unsigned int report[64];
static int count = ARRAY_SIZE(report);
module_param_array(report, uint, &count, 0444);
static bool arm;
module_param(arm, bool, 0400);
static int disarmed;
static atomic_t sampled = ATOMIC_INIT(0);
static atomic_t hits = ATOMIC_INIT(0);
static unsigned int self_hits;
static void (*register_hook)(struct undef_hook *);
static void (*unregister_hook)(struct undef_hook *);
extern unsigned int a7_undef_test(void);
extern char a7_undef_test_site[], a7_jpeg_bridge[];

void a7_jpeg_record(unsigned long ctx, unsigned int stage)
{
    int err;
    report[2] = atomic_inc_return(&hits);
    if (atomic_cmpxchg(&sampled, 0, 1)) return;
    report[1] = 2;
    report[8] = ctx;
    report[9] = stage;
    if (stage != 0x12a || ctx < 0x60000000UL || ctx > 0x7fff8000UL) {
        report[1] = 4;
        return;
    }
    err = probe_kernel_read(report + 16, (void *)(ctx + 0x62e0), 64);
    if (!err) err = probe_kernel_read(report + 32, (void *)(ctx + 0x6700), 64);
    if (!err) err = probe_kernel_read(report + 48, (void *)(ctx + 0x6750), 32);
    report[10] = err;
    smp_wmb();
    report[1] = err ? 5 : 3;
}

static int undef_callback(struct pt_regs *regs, unsigned int insn)
{
    if (insn != UDF_WORD) return 1;
    if (regs->ARM_pc == (unsigned long)a7_undef_test_site) {
        self_hits++;
        regs->ARM_pc += 4;
        return 0;
    }
    if (regs->ARM_pc != SITE) return 1;
    regs->ARM_pc = (unsigned long)a7_jpeg_bridge & ~1UL;
    return 0;
}
static struct undef_hook hook = {
    .instr_mask = ~0U, .instr_val = UDF_WORD,
    .cpsr_mask = MODE_MASK | PSR_T_BIT, .cpsr_val = SVC_MODE | PSR_T_BIT,
    .fn = undef_callback,
};

static void sync_code(void *unused)
{
    (void)unused;
    flush_icache_range(SITE, SITE + 4);
}
static int change_site(void *to_restore)
{
    unsigned int expected = to_restore ? UDF_WORD : NATIVE_SITE_WORD;
    unsigned int replacement = to_restore ? NATIVE_SITE_WORD : UDF_WORD;
    if (*(volatile unsigned int *)SITE != expected) return -ESTALE;
    /* One aligned word: readers see either the original complete BL or UDF.W. */
    *(volatile unsigned int *)SITE = replacement;
    sync_code(NULL);
    return 0;
}
static int disarm_set(const char *val, const struct kernel_param *kp)
{
    int n, err;
    (void)kp;
    err = kstrtoint(val, 0, &n);
    if (err || n != 1) return -EINVAL;
    if (!arm || disarmed) return 0;
    err = stop_machine(change_site, (void *)1, NULL);
    if (err) return err;
    on_each_cpu(sync_code, NULL, 1);
    disarmed = 1;
    report[5] = 1;
    /* Keep both hook and module alive even for a delayed exception return. */
    return 0;
}
static const struct kernel_param_ops disarm_ops = { .set = disarm_set, .get = param_get_int };
module_param_cb(disarm, &disarm_ops, &disarmed, 0600);

static int __init capture_init(void)
{
    unsigned int i;
    int err;
    for (i = 0; i < ARRAY_SIZE(code_pins); i++)
        if (memcmp((void *)code_pins[i].address, code_pins[i].bytes, code_pins[i].size))
            return -ENODEV;
    if (kallsyms_lookup_name("register_undef_hook") != 0x601118acUL ||
        kallsyms_lookup_name("unregister_undef_hook") != 0x601118f4UL)
        return -ENODEV;
    register_hook = (void *)0x601118acUL;
    unregister_hook = (void *)0x601118f4UL;
    report[0] = 0x4137434b;
    report[3] = 1;
    report[6] = sizeof(struct module);
    report[7] = SITE;
    for (i = 0; i < 4; i++) report[12+i] = source_id[i];
    register_hook(&hook);
    if (a7_undef_test() != 0x7a73 || self_hits != 1) {
        unregister_hook(&hook);
        return -EINVAL;
    }
    report[4] = self_hits;
    if (!arm) return 0;
    /* Pin before publishing the detour. An armed probe cannot be unloaded. */
    __module_get(THIS_MODULE);
    report[1] = 1;
    err = stop_machine(change_site, NULL, NULL);
    if (err) {
        module_put(THIS_MODULE);
        unregister_hook(&hook);
        return err;
    }
    on_each_cpu(sync_code, NULL, 1);
    report[11] = 1; /* module pinned until cold reboot */
    return 0;
}
static void __exit capture_exit(void)
{
    /* Only self-test mode has zero module references and can reach this. */
    unregister_hook(&hook);
}
module_init(capture_init);
module_exit(capture_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("A7 III temporary pre-JPEG metadata callback; no pixel writes");
