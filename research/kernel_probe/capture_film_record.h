#ifndef A7_GRAIN_FIXTURE
#include <linux/jiffies.h>
#endif
#include "a7-film-frame.h"
extern unsigned long arch_phys_to_va(unsigned long);
extern int arch_va_to_cachetype(unsigned long);
static unsigned film_workspace[6000*(167+6)/4];
static int grain_patch(unsigned handle)
{
    unsigned physical=report[40+0xc0/4];
    unsigned long va,start=jiffies;
    int err;
    struct a7_film_frame frame;
    struct a7_film_frame_params params;
    report[344]=1;
    if((physical!=0x1a000000&&physical!=0x24000000)||report[305]!=0x12||
       arch_phys_to_cachetype2(physical,0x3000000)!=0x12)return -EINVAL;
    va=arch_phys_to_va(physical);
    if(va!=physical+0x60000000UL||arch_va_to_cachetype(va)!=0x12)return -EINVAL;
    memset(&frame,0,sizeof(frame));
    frame.width=6000;frame.height=4000;frame.format=A7_FILM_UYVY;
    frame.range=A7_FILM_FULL;frame.path=A7_FILM_CAPTURE;
    frame.plane[0].data=(unsigned char *)(va+160);
    frame.plane[0].bytes=0x3000000-160;frame.plane[0].stride=12160;
    frame.cookie=handle;frame.sequence=completed+1;
    params.grain=frame_grain;params.halation=frame_halation;
    params.radius=167;params.seed=frame_seed;
    err=a7_film_frame_validate(&frame,&params,film_workspace,sizeof(film_workspace));
    if(err)return err;
    report[344]=2;mb();
    err=a7_film_frame_apply(&frame,&params,film_workspace,sizeof(film_workspace));
    mb();report[344]=3;report[345]=err;report[348]=jiffies-start;
    report[349]=24000000;report[350]=err?2:0;
    report[359]=physical;report[360]=va;report[361]=frame_grain;
    return err;
}
static int grain_publish(void)
{
    unsigned char pixels[64],original[64];
    unsigned i;int strength,err;
    struct a7_film_frame f={.width=8,.height=4,.format=A7_FILM_UYVY,
        .range=A7_FILM_FULL,.path=A7_FILM_CAPTURE,.plane={{pixels,64,16},{0}},.cookie=1,.sequence=1};
    struct a7_film_frame_params p={0,0,1,0x5a7f1203};
    for(i=0;i<64;i++)original[i]=(i&1)?((i/2)%8<4?105:250):128;
    for(strength=-9;strength<=9;strength+=9){
        memcpy(pixels,original,64);p.halation=strength;
        err=a7_film_frame_apply(&f,&p,film_workspace,sizeof(film_workspace));if(err)return err;
        if((strength==0&&memcmp(pixels,original,64))||
           (strength<0&&pixels[7]>=105)||(strength>0&&pixels[7]<=105))return -EINVAL;
    }
    memcpy(pixels,original,64);p.grain=9;p.halation=0;
    err=a7_film_frame_apply(&f,&p,film_workspace,sizeof(film_workspace));
    if(err||!memcmp(pixels,original,64))return -EINVAL;
    report[352]=1;return 0;
}
static void grain_remove(void){}
