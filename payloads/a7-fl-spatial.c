#include "a7-fl-spatial.h"
#define MAX_WIDTH 8192u
#define MAX_HEIGHT 8192u
#define CLARITY_RADIUS 16u
#define SHARP_RADIUS_MAX 5u
size_t a7_fl_spatial_workspace(unsigned width) {
    if(!width||width>MAX_WIDTH)return 0;
    return (size_t)width*(sizeof(uint32_t)+(2*CLARITY_RADIUS+1)*sizeof(uint16_t));
}
size_t a7_fl_spatial_inplace_workspace(unsigned width) {
    if(!width||width>MAX_WIDTH)return 0;
    return (size_t)width*(2*sizeof(uint32_t)+
        (2*CLARITY_RADIUS+1+2*SHARP_RADIUS_MAX+1)*sizeof(uint16_t));
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
static void seed(const uint8_t *src,unsigned stride,unsigned w,unsigned h,
                 unsigned radius,uint32_t *sum,uint16_t *ring) {
    for(unsigned x=0;x<w;x++)sum[x]=0;
    for(unsigned i=0;i<2*radius+1;i++) {
        unsigned row=(unsigned)clamp((int)i-(int)radius,0,(int)h-1);
        uint16_t *line=ring+(size_t)i*w;
        horizontal(src+(size_t)row*stride,w,radius,line);
        for(unsigned x=0;x<w;x++)sum[x]+=line[x];
    }
}
static void slide(const uint8_t *next,unsigned w,unsigned radius,
                  uint32_t *sum,uint16_t *line) {
    for(unsigned x=0;x<w;x++)sum[x]-=line[x];
    horizontal(next,w,radius,line);
    for(unsigned x=0;x<w;x++)sum[x]+=line[x];
}
static int detail_at(unsigned sum,unsigned area,int original) {
    return original-(int)((sum+area/2)/area);
}
static int clarity_delta(int original,int detail,int amount) {
    int weight=original<128?original*2:(255-original)*2;
    return clamp(divide(detail*amount*weight,18*255),-24,24);
}
static void pass(const uint8_t *src,unsigned ss,uint8_t *dst,unsigned ds,
                  unsigned width,unsigned height,unsigned radius,int amount,int clarity,
                  uint32_t *sum,uint16_t *ring) {
    unsigned count=2*radius+1,area=count*count,head=0;
    seed(src,ss,width,height,radius,sum,ring);
    for(unsigned y=0;y<height;y++) {
        for(unsigned x=0;x<width;x++) {
            int original=src[(size_t)y*ss+x];
            int detail=detail_at(sum[x],area,original),delta;
            if(clarity) {
                /* Midtone-weighted large-radius contrast; bounded to avoid
                 * strong halos and clipping in the first experimental recipe. */
                delta=clarity_delta(original,detail,amount);
                original=dst[(size_t)y*ds+x];
            }else delta=divide(detail*amount,4);
            dst[(size_t)y*ds+x]=(uint8_t)clamp(original+delta,0,255);
        }
        if(y+1<height) {
            uint16_t *row=ring+(size_t)head*width;
            unsigned next=(unsigned)clamp((int)y+(int)radius+1,0,(int)height-1);
            slide(src+(size_t)next*ss,width,radius,sum,row);
            if(++head==count)head=0;
        }
    }
}
int a7_fl_spatial_inplace(uint8_t *luma,size_t n,unsigned stride,unsigned w,unsigned h,
                         const A7FLSpatialParams *p,void *workspace,size_t wn) {
    size_t needed=a7_fl_spatial_inplace_workspace(w);
    if(!luma||!p||!workspace||!needed||!h||h>MAX_HEIGHT||stride<w||stride>SIZE_MAX/h||
       n<(size_t)(h-1)*stride+w||p->sharpness<-3||p->sharpness>3||
       p->range<1||p->range>5||p->clarity<0||p->clarity>9||wn<needed||
       ((uintptr_t)workspace&3)||overlap(luma,n,workspace,needed)||
       overlap(p,sizeof *p,luma,n)||overlap(p,sizeof *p,workspace,needed))return -1;
    int sharp=p->sharpness,clarity=p->clarity;
    if(!sharp&&!clarity)return 0;
    unsigned sr=(unsigned)(6-p->range),sc=2*sr+1,cc=2*CLARITY_RADIUS+1,sh=0,ch=0;
    uint32_t *ss=workspace,*cs=ss+w;
    uint16_t *sb=(uint16_t *)(cs+w),*cb=sb+(size_t)sc*w;
    if(sharp)seed(luma,stride,w,h,sr,ss,sb);
    if(clarity)seed(luma,stride,w,h,CLARITY_RADIUS,cs,cb);
    for(unsigned y=0;y<h;y++) {
        uint8_t *row=luma+(size_t)y*stride;
        for(unsigned x=0;x<w;x++) {
            int original=row[x],value=original;
            if(sharp)value=clamp(value+divide(detail_at(ss[x],sc*sc,original)*sharp,4),0,255);
            if(clarity)value=clamp(value+clarity_delta(original,detail_at(cs[x],cc*cc,original),clarity),0,255);
            row[x]=(uint8_t)value;
        }
        if(y+1==h)break;
        /* The last-row clamp still selects an untouched row: next > y.
         * All old rows needed later are retained as original horizontal sums. */
        if(sharp) {
            unsigned next=y+sr+1<h?y+sr+1:h-1;
            slide(luma+(size_t)next*stride,w,sr,ss,sb+(size_t)sh*w);
            if(++sh==sc)sh=0;
        }
        if(clarity) {
            unsigned next=y+CLARITY_RADIUS+1<h?y+CLARITY_RADIUS+1:h-1;
            slide(luma+(size_t)next*stride,w,CLARITY_RADIUS,cs,cb+(size_t)ch*w);
            if(++ch==cc)ch=0;
        }
    }
    return 0;
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
