#ifndef A7_GRAIN_FIXTURE
#include <linux/sysfs.h>
#include <linux/jiffies.h>
#endif
#include "a7-film-frame.h"
extern unsigned long arch_phys_to_va(unsigned long);
extern int arch_va_to_cachetype(unsigned long);
#define GW 256U
#define GH 128U
#define BORDER 8U
#define TW (GW+2*BORDER)
#define TH (GH+2*BORDER)
#define TS (TW*2)
#define TB (TH*TS)
#define GX (80+(6000-GW)/2-BORDER)
#define GY ((4000-GH)/2-BORDER)
static struct {unsigned magic,version,width,height,stride,x,y,seed;unsigned char before[TB],wanted[TB],actual[TB];} grain;
static unsigned grain_workspace[GW*7/4];
#ifdef A7_GRAIN_FULL
static unsigned full_workspace[6000*7/4];
extern void a7_grain_region_reference(unsigned char *,const unsigned char *,unsigned,unsigned,unsigned,unsigned,unsigned,unsigned,unsigned);
#endif
static bool grain_published;
static int grain_inside(unsigned i){unsigned y=i/TS,x=(i%TS)/2;return (i&1)&&y>=BORDER&&y<BORDER+GH&&x>=BORDER&&x<BORDER+GW;}
static int grain_render(unsigned handle)
{
    struct a7_film_frame f={.width=GW,.height=GH,.format=A7_FILM_UYVY,.range=A7_FILM_FULL,.path=A7_FILM_CAPTURE,
        .plane={{grain.wanted+BORDER*TS+BORDER*2,TB-BORDER*TS-BORDER*2,TS},{0}},.cookie=handle,.sequence=1};
    struct a7_film_frame_params p={9,0,1,0x5a7f1203};
    unsigned i,changed=0;int err;
    memcpy(grain.wanted,grain.before,TB);
    err=a7_film_frame_apply(&f,&p,grain_workspace,sizeof(grain_workspace));if(err)return err;
    for(i=0;i<TB;i++)if(grain.wanted[i]!=grain.before[i]){
        if(!grain_inside(i))return -EFAULT;
        changed++;
    }
    report[346]=changed;return 0;
}
static void grain_read_pixels(unsigned long va,unsigned char *out)
{
    unsigned y,x;
    for(y=0;y<TH;y++)for(x=0;x<TS;x++)out[y*TS+x]=*(volatile unsigned char *)(va+(GY+y)*12160+GX*2+x);
}
#ifndef A7_GRAIN_FULL
static void grain_write_pixels(unsigned long va,const unsigned char *bytes)
{
    unsigned y,x;
    for(y=BORDER;y<BORDER+GH;y++)for(x=BORDER*2+1;x<(BORDER+GW)*2;x+=2)
        *(volatile unsigned char *)(va+(GY+y)*12160+GX*2+x)=bytes[y*TS+x];
    mb();
}
#endif
static int grain_patch(unsigned handle)
{
    unsigned long va,start=jiffies;int err;
    report[344]=1;
    /* Use the native established uncached mapping; never introduce an alias. */
    if(report[305]!=0x12 || arch_phys_to_cachetype2(0x1a000000,0x3000000)!=0x12)return -EINVAL;
    va=arch_phys_to_va(0x1a000000);
    if(va!=0x7a000000 || arch_va_to_cachetype(va)!=0x12)return -EINVAL;
    mb();grain_read_pixels(va,grain.before);
#ifdef A7_GRAIN_FULL
    {
        struct a7_film_frame full={.width=6000,.height=4000,.format=A7_FILM_UYVY,.range=A7_FILM_FULL,.path=A7_FILM_CAPTURE,
            .plane={{(unsigned char *)(va+160),0x3000000-160,12160},{0}},.cookie=handle,.sequence=1};
        struct a7_film_frame_params params={9,0,1,0x5a7f1203};
        unsigned i;
#ifdef A7_GRAIN_REPEAT
        params.grain=frame_selection&15;params.seed=frame_seed;
        grain.seed=frame_seed;
#endif
        err=a7_film_frame_validate(&full,&params,full_workspace,sizeof(full_workspace));
        if(err){report[345]=err;return err;}
        a7_grain_region_reference(grain.wanted,grain.before,TW,TH,GX-80,GY,6000,params.seed,params.grain);
        report[346]=0;
        for(i=0;i<TB;i++)if(grain.wanted[i]!=grain.before[i])report[346]++;
        report[344]=2;
        err=a7_film_frame_apply(&full,&params,full_workspace,sizeof(full_workspace));
        mb();report[349]=6000*4000;
        grain_read_pixels(va,grain.actual);
        if(!err&&memcmp(grain.actual,grain.wanted,TB))err=-EIO;
        /* This full-frame experiment retains a diagnostic tile, not a full
         * original frame. A mismatch must not be reported as rolled back. */
        if(err)report[350]=2;
    }
#else
    err=grain_render(handle);if(err){report[345]=err;return err;}
    report[344]=2;
    grain_write_pixels(va,grain.wanted);report[349]=GW*GH;
    grain_read_pixels(va,grain.actual);
    err=memcmp(grain.actual,grain.wanted,TB)?-EIO:0;
    if(err){
        grain_write_pixels(va,grain.before);grain_read_pixels(va,grain.actual);
        report[350]=memcmp(grain.actual,grain.before,TB)?2:1;
    }
#endif
    report[348]=jiffies-start;report[345]=err;report[344]=3;
    return err;
}
static ssize_t grain_read(struct file *f,struct kobject *k,struct bin_attribute *a,char *out,loff_t off,size_t n)
{
    (void)f;(void)k;(void)a;
    if(report[17]!=3)return -EAGAIN;
    if(off<0)return -EINVAL;
    if(off>=sizeof(grain))return 0;
    if(n>sizeof(grain)-off)n=sizeof(grain)-off;
    memcpy(out,(char *)&grain+off,n);return n;
}
static struct bin_attribute grain_attr={.attr={.name="grain",.mode=0400},.size=sizeof(grain),.read=grain_read};
static int grain_publish(void)
{
    unsigned i;int err;
    grain.magic=0x41374752;grain.version=1;grain.width=TW;grain.height=TH;grain.stride=TS;grain.x=GX;grain.y=GY;grain.seed=0x5a7f1203;
    for(i=0;i<TB;i++)grain.before[i]=(unsigned char)(i*37+53);
    err=grain_render(1);if(err||!report[346])return -EINVAL;
    report[352]=1;report[346]=0;
    memset(grain.before,0,TB);memset(grain.wanted,0,TB);
    err=sysfs_create_bin_file(&THIS_MODULE->mkobj.kobj,&grain_attr);
    if(!err)grain_published=true;
    return err;
}
static void grain_remove(void){if(grain_published)sysfs_remove_bin_file(&THIS_MODULE->mkobj.kobj,&grain_attr);}
