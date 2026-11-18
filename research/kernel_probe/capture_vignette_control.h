/* Atomic preset/grain/signed-halo snapshot, independent of filesystem I/O. */
static unsigned selection,frame_selection,frame_seed,completed,skipped,failed;
static unsigned frame_grain;
static int frame_halation,frame_vignette;
#ifdef A7_WET_PLATE
static unsigned frame_wet;
#endif
static unsigned diagnostic;
/* Read-only after loading; normal resident boot leaves this disabled. */
module_param(diagnostic,uint,0400);
static int selection_valid(unsigned n)
{
#ifdef A7_WET_PLATE
    if(n>=131072)return 0;
    if((n&65536)&&!((n>>14)&3))return 0;
    n&=65535;
#endif
    return n==0||(n<65536&&(n>>14)>=1&&(n>>14)<=3&&(n&15)<=9&&((n>>4)&31)<=18&&((n>>9)&31)<=18);
}
static int selection_set(const char *val,const struct kernel_param *kp)
{
    int n;(void)kp;
    if(kstrtoint(val,0,&n)||n<0||!selection_valid((unsigned)n))return -EINVAL;
    ACCESS_ONCE(selection)=(unsigned)n;return 0;
}
static const struct kernel_param_ops selection_ops={.set=selection_set,.get=param_get_uint};
module_param_cb(selection,&selection_ops,&selection,0600);
static unsigned seed_for_frame(unsigned n,unsigned ticks)
{
    unsigned x=0x5a7f1203U^n^ticks;
    x^=x>>16;x*=0x7feb352dU;x^=x>>15;x*=0x846ca68bU;return x^(x>>16);
}
