/* Three captures in order: -9, 0, +9; no persistent parameter changes. */
static unsigned selection,frame_selection,frame_seed,completed,skipped,failed;
static int frame_halation;
static int selection_set(const char *val,const struct kernel_param *kp)
{
    int n;(void)kp;
    if(kstrtoint(val,0,&n)||(n!=0&&n!=1))return -EINVAL;
    ACCESS_ONCE(selection)=(unsigned)n;return 0;
}
static const struct kernel_param_ops selection_ops={.set=selection_set,.get=param_get_uint};
module_param_cb(selection,&selection_ops,&selection,0600);
static unsigned seed_for_frame(unsigned n,unsigned ticks){return n^ticks;}
