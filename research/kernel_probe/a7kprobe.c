/* Read-only ABI/AV-CAM inspection. No hooks, cache calls or image writes. */
#include <linux/module.h>
#include <linux/init.h>
#include <linux/errno.h>
#include <linux/string.h>
#include "pins.h"

static unsigned int report[16];
static int report_count = ARRAY_SIZE(report);
module_param_array(report, uint, &report_count, 0444);
MODULE_PARM_DESC(report, "Read-only pinned AV-CAM inspection results");

static int __init inspect_init(void)
{
    const unsigned char *stage = (const void *)0x6390618c;
    const unsigned int *table;
    unsigned int root, i;
    /* Addresses are permitted only after the userspace physical-code preflight. */
    if (memcmp((const void *)0x60118470, kernel_pin, sizeof(kernel_pin)) ||
        memcmp(stage, stage_pin, sizeof(stage_pin)))
        return -ENODEV;
    root = *(const volatile unsigned int *)0x6475a218;
    if (root != 0x635c6000)
        return -ENODEV;
    table = *(const unsigned int * volatile *)(root + 0x14);
    if ((unsigned long)table != 0x635c60b4)
        return -ENODEV;
    report[0] = 0x41374b50;
    report[1] = 1;
    report[2] = sizeof(struct module);
    report[3] = offsetof(struct module, init);
    report[4] = offsetof(struct module, exit);
    report[5] = root;
    report[6] = (unsigned long)table;
    for (i = 0; i < 5; i++)
        report[7 + i] = table[(0x2fc / 4) + i];
    report[12] = 0x6390618c;
    report[13] = sizeof(stage_pin);
    report[14] = 0; /* no callback installed */
    report[15] = 0; /* no pixel writes */
    return 0;
}

static void __exit inspect_exit(void) { }
module_init(inspect_init);
module_exit(inspect_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("A7 III bounded read-only kernel ABI probe");
