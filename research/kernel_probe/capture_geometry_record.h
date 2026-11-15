/* Reuse the verified bounded early reader. Publish each slot only once. */
static unsigned geometry0[368], geometry1[368], geometry2[368];
static int geometry_words0=368, geometry_words1=368, geometry_words2=368;
static unsigned geometry_captured;
module_param_array(geometry0, uint, &geometry_words0, 0444);
module_param_array(geometry1, uint, &geometry_words1, 0444);
module_param_array(geometry2, uint, &geometry_words2, 0444);
module_param(geometry_captured, uint, 0444);
void a7_multi_record(unsigned index, const unsigned *regs)
{
    unsigned n, *slot; int err;
    if (index!=2 || regs[0]!=0x641b6f10U || disarmed) return;
    if (atomic_cmpxchg(sampled+2,0,1)) return;
    if (geometry_captured>=3) { atomic_set(sampled+2,0); return; }
    n=atomic_inc_return(&total);
    report[2]=n; report[16]=n;
    /* Erase prior partial reads so failed slots cannot borrow old metadata. */
    memset(report+21,0,(368-21)*sizeof(unsigned));
    report[17]=2;
    err=take_early_record(regs); report[18]=err;
    report[17]=3;
    slot=geometry_captured==0?geometry0:geometry_captured==1?geometry1:geometry2;
    memcpy(slot,report,sizeof report);
    smp_wmb(); geometry_captured++;
    smp_mb(); atomic_set(sampled+2,0);
}
