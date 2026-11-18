#ifdef A7_WET_PLATE
#include "a7-wet-plate.h"
#endif
#ifndef A7_GRAIN_FIXTURE
#include <linux/jiffies.h>
#endif
#include "a7-film-frame.h"
#include "a7-film-vignette.h"
extern unsigned long arch_phys_to_va(unsigned long);
extern int arch_va_to_cachetype(unsigned long);
static unsigned film_workspace[6000*(167+6)/4];
static unsigned auto_sample0[334],auto_sample1[334],auto_sample2[334];
module_param_array(auto_sample0,uint,NULL,0400);
module_param_array(auto_sample1,uint,NULL,0400);
module_param_array(auto_sample2,uint,NULL,0400);
static unsigned auto_film0[160],auto_film1[160],auto_film2[160];
module_param_array(auto_film0,uint,NULL,0400);
module_param_array(auto_film1,uint,NULL,0400);
module_param_array(auto_film2,uint,NULL,0400);
static void sample_auto(unsigned *out,const struct a7_film_frame *f){
    const unsigned char *source=f->plane[0].data;
    unsigned coords[5][2]={{0,0},{f->width-8,0},{0,f->height-8},{f->width-8,f->height-8},{((f->width-8)/2)&~1u,(f->height-8)/2}};
    unsigned point,row,col;
    for(point=0;point<5;point++)for(row=0;row<8;row++)for(col=0;col<4;col++)
        *out++=*(const unsigned *)(source+(coords[point][1]+row)*f->plane[0].stride+coords[point][0]*2+col*4);
}
static int grain_patch(unsigned handle)
{
    unsigned physical=report[40+0xc0/4];
    unsigned long va,start=jiffies;
    int err;
    unsigned *sample=NULL,*film=NULL;
    struct a7_capture_geometry geometry;
    struct a7_film_frame frame;
    struct a7_film_frame_params params;
    report[344]=1;
    if(auto_geometry(&geometry))return -EINVAL;
    if((physical!=0x1a000000&&physical!=0x24000000)||report[305]!=0x12||
       arch_phys_to_cachetype2(physical,0x3000000)!=0x12)return -EINVAL;
    va=arch_phys_to_va(physical);
    if(va!=physical+0x60000000UL||arch_va_to_cachetype(va)!=0x12)return -EINVAL;
    memset(&frame,0,sizeof(frame));
    frame.width=geometry.width;frame.height=geometry.height;frame.format=A7_FILM_UYVY;
    frame.range=A7_FILM_FULL;frame.path=A7_FILM_CAPTURE;
    frame.plane[0].data=(unsigned char *)(va+geometry.offset);
    frame.plane[0].bytes=0x3000000-geometry.offset;frame.plane[0].stride=geometry.stride;
    frame.cookie=handle;frame.sequence=completed+1;
    params.grain=frame_grain;params.halation=frame_halation;
    params.radius=a7_film_frame_reference_radius(frame.width);params.seed=frame_seed;
    err=a7_film_frame_validate(&frame,&params,film_workspace,sizeof(film_workspace));
    if(err)return err;
    if(frame_vignette < -9 || frame_vignette > 9)return -EINVAL;
    if(diagnostic){
        if(completed>=3||frame.width<8||frame.height<8)return -EINVAL;
        sample=completed==0?auto_sample0:completed==1?auto_sample1:auto_sample2;
        sample[0]=0x41375647;sample[1]=completed;sample[2]=frame_grain;sample[3]=(unsigned)frame_halation;
        sample[4]=(unsigned)frame_vignette;sample[5]=physical;
        sample_auto(sample+6,&frame);
        film=completed==0?auto_film0:completed==1?auto_film1:auto_film2;
        sample[326]=frame.width;sample[327]=frame.height;sample[328]=geometry.stride;
        sample[329]=geometry.offset;sample[330]=report[40+0x90/4]&65535;
        sample[331]=report[40+0x74/4];sample[332]=frame_seed;
    }
    report[344]=2;mb();
    err=a7_film_frame_apply(&frame,&params,film_workspace,sizeof(film_workspace));
    if(!err&&film)sample_auto(film,&frame);
    if(!err)err=a7_film_vignette_apply(&frame,frame_vignette,film_workspace,sizeof(film_workspace));
#ifdef A7_WET_PLATE
    if(!err&&frame_wet){
        int rendered=a7_wet_render(frame.plane[0].data,frame.plane[0].bytes,
            frame.plane[0].stride,frame.width,frame.height,0);
        if(rendered!=1)err=-EINVAL;
    }
#endif
    mb();
    if(!err&&sample)sample_auto(sample+166,&frame);
    report[362]=(unsigned)frame_vignette;
    report[344]=3;report[345]=err;report[348]=jiffies-start;
    report[349]=(frame_grain||frame_halation||frame_vignette)?frame.width*frame.height:0;report[350]=err?2:0;
#ifdef A7_WET_PLATE
    if(!err&&frame_wet)report[349]=frame.width*frame.height;
#endif
    report[359]=physical;report[360]=va;report[361]=frame_grain;
    report[364]=geometry.width;report[365]=geometry.height;report[366]=geometry.stride;report[367]=geometry.offset;
    if(sample)sample[333]=(unsigned)(jiffies-start);
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
    for(strength=-9;strength<=9;strength+=9){
        memcpy(pixels,original,64);
        err=a7_film_vignette_apply(&f,strength,film_workspace,sizeof(film_workspace));if(err)return err;
        if((strength==0&&memcmp(pixels,original,64))||
           (strength<0&&pixels[1]>=105)||(strength>0&&pixels[1]<=105))return -EINVAL;
    }
#ifdef A7_WET_PLATE
    for(i=0;i<64;i++)pixels[i]=(i&1)?((i/2)%8<4?50:200):((i&2)?180:80);
    if(a7_wet_render(pixels,64,16,8,4,0)!=1)return -EINVAL;
    for(i=0;i<64;i+=2)if(pixels[i]!=128)return -EINVAL;
    if(pixels[1]>=60||pixels[9]<=pixels[1]+100)return -EINVAL;
#endif
    report[352]=1;return 0;
}
static void grain_remove(void){}
