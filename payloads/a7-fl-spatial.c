#include "a7-fl-spatial.h"
#define MAX_WIDTH 8192u
#define MAX_HEIGHT 8192u
#define CLARITY_RADIUS 16u
size_t a7_fl_spatial_workspace(unsigned width) {
    if(!width||width>MAX_WIDTH)return 0;
    return (size_t)width*(sizeof(uint32_t)+(2*CLARITY_RADIUS+1)*sizeof(uint16_t));
}
static int clamp(int value,int low,int high) {return value<low?low:value>high?high:value;}
static int divide(int value,int denominator) {
    return value<0?-((-value+denominator/2)/denominator):(value+denominator/2)/denominator;
}
static int overlap(const void *a,size_t an,const void *b,size_t bn) {
    uintptr_t x=(uintptr_t)a,y=(uintptr_t)b;
    if(an>UINTPTR_MAX-x||bn>UINTPTR_MAX-y)return 1;
    return x<y+bn&&y<x+an;
}
static void horizontal(const uint8_t *src,unsigned width,unsigned radius,uint16_t *out) {
    unsigned sum=0;
    for(int x=-(int)radius;x<=(int)radius;x++)sum+=src[clamp(x,0,(int)width-1)];
    for(unsigned x=0;x<width;x++) {
        out[x]=(uint16_t)sum;
        sum-=src[clamp((int)x-(int)radius,0,(int)width-1)];
        sum+=src[clamp((int)x+(int)radius+1,0,(int)width-1)];
    }
}
static void pass(const uint8_t *src,unsigned ss,uint8_t *dst,unsigned ds,
                  unsigned width,unsigned height,unsigned radius,int amount,int clarity,
                  uint32_t *sum,uint16_t *ring) {
    unsigned count=2*radius+1,area=count*count,head=0;
    for(unsigned x=0;x<width;x++)sum[x]=0;
    for(unsigned i=0;i<count;i++) {
        unsigned row=(unsigned)clamp((int)i-(int)radius,0,(int)height-1);
        horizontal(src+(size_t)row*ss,width,radius,ring+(size_t)i*width);
        for(unsigned x=0;x<width;x++)sum[x]+=ring[(size_t)i*width+x];
    }
    for(unsigned y=0;y<height;y++) {
        for(unsigned x=0;x<width;x++) {
            int original=src[(size_t)y*ss+x];
            int blurred=(int)((sum[x]+area/2)/area),detail=original-blurred,delta;
            if(clarity) {
                /* Midtone-weighted large-radius contrast; bounded to avoid
                 * strong halos and clipping in the first experimental recipe. */
                int weight=original<128?original*2:(255-original)*2;
                delta=clamp(divide(detail*amount*weight,18*255),-24,24);
                original=dst[(size_t)y*ds+x];
            }else delta=divide(detail*amount,4);
            dst[(size_t)y*ds+x]=(uint8_t)clamp(original+delta,0,255);
        }
        if(y+1<height) {
            uint16_t *row=ring+(size_t)head*width;
            for(unsigned x=0;x<width;x++)sum[x]-=row[x];
            unsigned next=(unsigned)clamp((int)y+(int)radius+1,0,(int)height-1);
            horizontal(src+(size_t)next*ss,width,radius,row);
            for(unsigned x=0;x<width;x++)sum[x]+=row[x];
            if(++head==count)head=0;
        }
    }
}
int a7_fl_spatial_luma(const uint8_t *src,size_t sn,unsigned ss,
                       uint8_t *dst,size_t dn,unsigned ds,unsigned w,unsigned h,
                       const A7FLSpatialParams *p,void *workspace,size_t wn) {
    size_t needed=a7_fl_spatial_workspace(w);
    if(!src||!dst||!p||!workspace||!needed||!h||h>MAX_HEIGHT||ss<w||ds<w||
       ss>SIZE_MAX/h||ds>SIZE_MAX/h||sn<(size_t)(h-1)*ss+w||dn<(size_t)(h-1)*ds+w||
       p->sharpness<-3||p->sharpness>3||p->range<1||p->range>5||p->clarity<0||p->clarity>9||
       wn<needed||((uintptr_t)workspace&3)||overlap(src,sn,dst,dn)||
       overlap(src,sn,workspace,needed)||overlap(dst,dn,workspace,needed)||
       overlap(p,sizeof *p,dst,dn)||overlap(p,sizeof *p,workspace,needed))return -1;
    uint32_t *sum=workspace;uint16_t *ring=(uint16_t *)(sum+w);
    if(p->sharpness)pass(src,ss,dst,ds,w,h,(unsigned)(6-p->range),p->sharpness,0,sum,ring);
    else for(unsigned y=0;y<h;y++)for(unsigned x=0;x<w;x++)dst[(size_t)y*ds+x]=src[(size_t)y*ss+x];
    if(p->clarity)pass(src,ss,dst,ds,w,h,CLARITY_RADIUS,p->clarity,1,sum,ring);
    return 0;
}
