/* Read-only task and original resize plan. Addresses are only followed through
 * early_read's bounded kernel RAM reader. All copies are made in the callback. */
static unsigned layout0[352],layout1[352],layout2[352],layout_captured;
module_param_array(layout0,uint,NULL,0400);
module_param_array(layout1,uint,NULL,0400);
module_param_array(layout2,uint,NULL,0400);
static int take_layout_record(const unsigned *regs)
{
    unsigned *out,slot=layout_captured;
    int err=take_early_record(regs);
    if(slot>=3)return -ENOSPC;
    out=slot==0?layout0:slot==1?layout1:layout2;
    out[0]=0x41374c59;out[1]=1;out[3]=slot+1;out[4]=regs[6];
    if(err)goto done;
    err=early_read(out+8,regs[6],512);if(err)goto done;
    out[5]=out[8+0x10/4];
    err=early_read(out+136,out[5],64);if(err)goto done;
    out[6]=out[136+8/4];out[7]=out[136];
    err=early_read(out+152,out[6],384);if(err)goto done;
    err=early_read(out+248,out[7],128);if(err)goto done;
    err=early_read(out+280,regs[0]+0x210,256);
done:
    out[2]=(unsigned)err;layout_captured++;return err;
}
