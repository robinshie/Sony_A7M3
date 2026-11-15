#ifndef A7_GRAIN_FIXTURE
#include <linux/sysfs.h>
#include <linux/jiffies.h>
#endif
#include "a7-film-frame.h"
extern unsigned long arch_phys_to_va(unsigned long);
extern int arch_va_to_cachetype(unsigned long);
#define HW 32U
#define HH 16U
#define HB 168U
#define HR 167U
#define NW (HW+2*HB)
#define NH (HH+2*HB)
#define NB (NW*NH*2)
#define HBYTES (HW*HH*2)
#define HX (80+(6000-HW)/2-HB)
#define HY ((4000-HH)/2-HB)
static struct {
    unsigned magic,version,index;
    int strength;
    unsigned width,height,border,radius,x,y,changed;
    unsigned physical,virtual_address,cache_type,ticks;
    unsigned char before[NB],wanted[HBYTES],actual[HBYTES];
} halo[3];
static unsigned char rendered[NB];
static unsigned halo_workspace[6000*(HR+6)/4];
static bool halo_published;
static void choose_tile(unsigned long va,unsigned index)
{
    unsigned x,y,dx,dy,best=0,bx=HX,by=HY;
    /* Pick a dark-side sample near actual highlights. The previous fixed
     * centre landed on a flat label and could not attest a non-zero effect.
     * Only read the already leased source; all probes stay inside its ROI. */
    for(y=HB+HH/2;y<=4000-HB-HH/2;y+=64)
        for(x=80+HB+HW/2;x<=6080-HB-HW/2;x+=64){
            unsigned v=*(volatile unsigned char *)(va+y*12160+x*2+1),score=0;
            if(v>190)continue;
            for(dy=0;dy<5;dy++)for(dx=0;dx<5;dx++){
                unsigned px=x+dx*80-160,py=y+dy*80-160;
                unsigned q=*(volatile unsigned char *)(va+py*12160+px*2+1);
                if(q>200)score+=(q-200)*255/55;
            }
            if(score>best){best=score;bx=x-HW/2-HB;by=y-HH/2-HB;}
        }
    halo[index].x=bx;halo[index].y=by;report[367]=best;
}
static void extract_tile(unsigned char *to,const unsigned char *from)
{
    unsigned y;
    for(y=0;y<HH;y++)memcpy(to+y*HW*2,from+((y+HB)*NW+HB)*2,HW*2);
}
static int halo_reference(unsigned index)
{
    struct a7_film_frame f={.width=NW,.height=NH,.format=A7_FILM_UYVY,
        .range=A7_FILM_FULL,.path=A7_FILM_CAPTURE,
        .plane={{rendered,NB,NW*2},{0}},.cookie=1,.sequence=1};
    struct a7_film_frame_params p={0,halo[index].strength,HR,0};
    int err;
    memcpy(rendered,halo[index].before,NB);
    err=a7_film_frame_apply(&f,&p,halo_workspace,sizeof(halo_workspace));
    if(!err)extract_tile(halo[index].wanted,rendered);
    return err;
}
static int grain_patch(unsigned handle)
{
    unsigned index=completed,y,x,changed=0,physical=report[40+0xc0/4];
    unsigned long va,start=jiffies;
    int err;
    if(index>=3||frame_halation!=(index==0?-9:index==1?0:9))return -EINVAL;
    report[344]=1;
    if((physical!=0x1a000000&&physical!=0x24000000)||report[305]!=0x12||
       arch_phys_to_cachetype2(physical,0x3000000)!=0x12)return -EINVAL;
    va=arch_phys_to_va(physical);
    if(va!=physical+0x60000000UL||arch_va_to_cachetype(va)!=0x12)return -EINVAL;
    halo[index].index=index;halo[index].strength=frame_halation;
    halo[index].physical=physical;halo[index].virtual_address=va;halo[index].cache_type=report[305];
    mb();
    choose_tile(va,index);
    for(y=0;y<NH;y++)for(x=0;x<NW*2;x++)
        halo[index].before[y*NW*2+x]=*(volatile unsigned char *)(va+(halo[index].y+y)*12160+halo[index].x*2+x);
    err=halo_reference(index);if(err)return err;
    {
        struct a7_film_frame f={.width=6000,.height=4000,.format=A7_FILM_UYVY,
            .range=A7_FILM_FULL,.path=A7_FILM_CAPTURE,
            .plane={{(unsigned char *)(va+160),0x3000000-160,12160},{0}},.cookie=handle,.sequence=index+1};
        struct a7_film_frame_params p={0,frame_halation,HR,0};
        report[344]=2;
        err=a7_film_frame_apply(&f,&p,halo_workspace,sizeof(halo_workspace));
    }
    mb();
    for(y=0;y<HH;y++)for(x=0;x<HW*2;x++){
        unsigned char v=*(volatile unsigned char *)(va+(halo[index].y+HB+y)*12160+(halo[index].x+HB)*2+x);
        unsigned i=y*HW*2+x;
        halo[index].actual[i]=v;
        changed+=v!=halo[index].before[((y+HB)*NW+HB)*2+x];
    }
    if(!err&&memcmp(halo[index].wanted,halo[index].actual,HBYTES))err=-EIO;
    halo[index].changed=changed;
    halo[index].ticks=jiffies-start;
    report[345]=err;report[346]=changed;report[348]=jiffies-start;
    report[349]=frame_halation?24000000:0;report[350]=err?2:0;
    report[344]=3;
    return err;
}
static ssize_t halo_read(struct file *f,struct kobject *k,struct bin_attribute *a,char *out,loff_t off,size_t n)
{
    (void)f;(void)k;(void)a;
    if(!disarmed)return -EBUSY;
    if(off<0)return -EINVAL;
    if(off>=sizeof(halo))return 0;
    if(n>sizeof(halo)-off)n=sizeof(halo)-off;
    memcpy(out,(char *)halo+off,n);return n;
}
static struct bin_attribute halo_attr={.attr={.name="halation",.mode=0400},.size=sizeof(halo),.read=halo_read};
static int grain_publish(void)
{
    unsigned index,i;
    int err;
    for(index=0;index<3;index++){
        halo[index].magic=0x4137484c;halo[index].version=2;halo[index].index=index;
        halo[index].strength=index==0?-9:index==1?0:9;
        halo[index].width=NW;halo[index].height=NH;halo[index].border=HB;halo[index].radius=HR;
        halo[index].x=HX;halo[index].y=HY;
        for(i=0;i<NB;i++)halo[index].before[i]=(i&1)?((i/2)%NW<NW/2?105:250):128;
        err=halo_reference(index);report[359]=err;if(err)return err;
        i=halo[index].wanted[(HH/2*HW+HW/2-4)*2+1];
        report[360+index]=i;
        if((index==0&&i>=105)||(index==1&&i!=105)||(index==2&&i<=105))return -EINVAL;
        memset(halo[index].before,0,NB);memset(halo[index].wanted,0,HBYTES);
    }
    report[352]=1;
    /* Mapping queries are read-only; selftest records both before any frame
     * is touched. A pixel callback still rejects a mismatching mapping. */
    report[363]=arch_phys_to_va(0x1a000000);report[364]=arch_phys_to_cachetype2(0x1a000000,0x3000000);
    report[365]=arch_phys_to_va(0x24000000);report[366]=arch_phys_to_cachetype2(0x24000000,0x3000000);
    err=sysfs_create_bin_file(&THIS_MODULE->mkobj.kobj,&halo_attr);
    if(!err)halo_published=true;
    return err;
}
static void grain_remove(void){if(halo_published)sysfs_remove_bin_file(&THIS_MODULE->mkobj.kobj,&halo_attr);}
