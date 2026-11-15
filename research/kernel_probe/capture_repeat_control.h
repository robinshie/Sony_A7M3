/* Atomic one-word selection; no kernel filesystem preference reads. */
static unsigned selection;
static unsigned frame_selection,frame_seed,completed,skipped,failed;
static int selection_valid(unsigned value){return value<=0x39 && (value&15)<=9 && (value>>4)<=3 && ((value>>4)||!(value&15));}
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
