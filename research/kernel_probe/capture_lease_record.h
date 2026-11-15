#ifndef A7_LEASE_FIXTURE
#include <linux/spinlock.h>
#include <linux/hardirq.h>
#endif
#define source_publish early_publish
#include "capture_early_record.h"
#undef source_publish
#include "dmm-close-pins.h"
#ifdef A7_AUTO_SIZE
#include "capture_auto_geometry.h"
#endif
extern int arch_phys_to_cachetype2(unsigned long,unsigned long);
static int (*native_open)(unsigned,unsigned,void *,unsigned short *);
static int (*native_close)(unsigned);
static raw_spinlock_t *native_lock;
#ifdef A7_GRAIN
static int grain_patch(unsigned handle);
#endif
static int source_publish(void)
{
    unsigned i,actual[sizeof(dmm_close_pin)/4],lock_address;
    unsigned long text;int err=early_publish();if(err)return err;
    text=dmm_open-0x889c;
    err=early_read(actual,text+0x85a4,sizeof(dmm_handle_pin));if(err)return err;
    if(memcmp(actual,dmm_handle_pin,sizeof(dmm_handle_pin)))return -ENODEV;
    if(kallsyms_lookup_name("dmm_unit_ctrl_Close")!=text+0x8a28)return -ENODEV;
    err=early_read(actual,text+0x8a28,sizeof(actual));if(err)return err;
    for(i=0;i<ARRAY_SIZE(actual);i++){
        unsigned at=0x8a28+i*4,w=dmm_close_pin[i];
        if(at>=0x8a8c && at<=0x8aa4)w+=text;
        if(at==0x8b18)w=dmm_root;
        if(actual[i]!=w)return -ENODEV;
    }
    err=early_read(&lock_address,text+0x3850,4);if(err)return err;
    if(lock_address!=dmm_root-0x94678+0x110 || sizeof(raw_spinlock_t)!=8)return -ENODEV;
    native_lock=(raw_spinlock_t *)(unsigned long)lock_address;
    native_open=(void *)dmm_open;native_close=(void *)(text+0x8a28);
    report[304]=lock_address;
    return 0;
}
static int take_lease_test(void)
{
    unsigned handle=report[21],unit=report[22],extents[32]={0};
    unsigned physical=0x1a000000;
    unsigned short count=0;unsigned char before[32],held[32],after[32];
    int acquired,closed,processing=0;unsigned long irq_flags;
#ifdef A7_HALATION_TEST
    /* Both bases were observed in the exact full-size source descriptor.
     * Do not admit arbitrary buffers: descriptor, extent and native Open
     * must agree, and grain_patch verifies the native uncached mapping. */
    physical=report[40+0xc0/4];
    if((physical!=0x1a000000&&physical!=0x24000000)||
       report[257]!=physical||report[258]||report[259]!=0x3000000)return -EINVAL;
#endif
#ifdef A7_AUTO_SIZE
    {
        struct a7_capture_geometry geometry;
        if(auto_geometry(&geometry))return -EINVAL;
    }
    if(((handle&0x3ff)+((handle>>15)<<10))>=0x580 ||
       (report[40+0xbc/4]&255)!=1 || report[40+0xc0/4]!=physical ||
       report[40+0xc4/4]!=0x3000000)return -EINVAL;
#else
    /* Exact observed image, source handle and idle stage guard. No pixel access. */
    if(((handle&0x3ff)+((handle>>15)<<10))>=0x580 || report[40+0x90/4]!=0x0fa01770 || report[40+0x94/4]!=0x0fa017c0 ||
       report[40+0x98/4]!=80 || (report[40+0xbc/4]&255)!=1 ||
       report[40+0xc0/4]!=physical || report[40+0xc4/4]!=0x3000000)return -EINVAL;
#endif
    for(acquired=184;acquired<208;acquired++)if(report[acquired])return -EBUSY;
    if(in_interrupt() || irqs_disabled() || in_atomic())return -EWOULDBLOCK;
    report[305]=arch_phys_to_cachetype2(physical,0x3000000);
    /* No unbounded wait: the intercepted caller could already own the lock.
     * Vignette allows a finite series of try-locks for transient contention;
     * interrupts are restored after every failed attempt. No pixel work,
     * allocation, logging or sleeping while holding it. */
#ifdef A7_VIGNETTE_BANKS
    {
        unsigned attempt;
        report[363]=0;
        for(attempt=0;attempt<64;attempt++){
            report[363]=attempt+1;
            if(raw_spin_trylock_irqsave(native_lock,irq_flags))break;
            cpu_relax();
        }
        if(attempt==64)return -EBUSY;
    }
#else
    if(!raw_spin_trylock_irqsave(native_lock,irq_flags))return -EBUSY;
#endif
    memcpy(before,(void *)(unsigned long)unit,sizeof(before));
    if(before[0x13]!=((handle>>10)&31) || before[0x11] || before[0x12] ||
       *(unsigned short *)(before+0x14)!=1 || *(unsigned short *)(before+0x16)!=1){
        raw_spin_unlock_irqrestore(native_lock,irq_flags);return -ESTALE;
    }
    acquired=native_open(handle,4,extents,&count);
    memcpy(held,(void *)(unsigned long)unit,sizeof(held));
#ifdef A7_GRAIN
    if(!acquired && count==1 && extents[0]==physical && extents[1]==0x3000000 &&
       held[0x11]==1 && *(unsigned short *)(held+0x14)==3){
        raw_spin_unlock_irqrestore(native_lock,irq_flags);
        processing=grain_patch(handle);
        /* The reference must be released even if processing was skipped.
         * No pixel work runs with the DMM global lock or interrupts disabled. */
        raw_spin_lock_irqsave(native_lock,irq_flags);
    }
#endif
    /* Close exactly our successful reference, under the same native lock. */
    closed=acquired?0:native_close(handle);
    memcpy(after,(void *)(unsigned long)unit,sizeof(after));
    raw_spin_unlock_irqrestore(native_lock,irq_flags);
    report[306]=acquired;report[307]=closed;report[308]=count;
    memcpy(report+312,extents,32);memcpy(report+320,before,32);
    memcpy(report+328,held,32);memcpy(report+336,after,32);
    report[309]=1;
    if(acquired)return acquired;
    if(closed)return closed;
    if(count!=1 || extents[0]!=physical || extents[1]!=0x3000000 ||
       held[0x11]!=1 || *(unsigned short *)(held+0x14)!=3 || memcmp(before,after,32))return -EIO;
    report[310]=1;return processing;
}
