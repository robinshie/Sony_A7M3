#include "a7-fl-fivepoint.h"
#include "a7-fl-fivepoint-preview.h"
static int clamp(int v,int lo,int hi){return v<lo?lo:v>hi?hi:v;}
static int decode(unsigned v,unsigned encoding){return encoding?(v<64?(int)v:(int)v-128):(v<128?(int)v:(int)v-256);}
int a7_fl_fivepoint_knots(const int c[5],int knots[5]){
    if(!c||!knots)return -1;
    for(unsigned i=0;i<5;i++)if(c[i]<-9||c[i]>9)return -1;
    int next[5];for(unsigned i=0;i<5;i++)next[i]=clamp((int)i*64+c[i]*4,i?next[i-1]:0,256);
    for(unsigned i=0;i<5;i++)knots[i]=next[i];
    return 0;
}
int a7_fl_fivepoint_sample(const int k[5],int y){
    if(!k||y<0||y>256)return -1;
    for(unsigned i=0;i<5;i++)if(k[i]<0||k[i]>256||(i&&k[i]<k[i-1]))return -1;
    unsigned lo=(unsigned)y/64;if(lo==4)return k[4];
    return k[lo]+((k[lo+1]-k[lo])*(y-(int)lo*64)+32)/64;
}
int a7_fl_fivepoint_lut(const uint8_t *in,unsigned size,uint8_t *out,unsigned out_size,
                       unsigned encoding,const int controls[5],const int8_t *low,const int8_t *high){
    int knots[5];
    if(!in||!out||size!=1280||out_size!=1280||encoding>1||(!low)!=(!high)||
       a7_fl_fivepoint_knots(controls,knots))return -1;
    for(unsigned i=0;i<1215;i++)if((encoding&&in[i]>=128)||decode(in[i],encoding)<-64||decode(in[i],encoding)>63)return -2;
    if(low)for(unsigned i=0;i<405;i++)if(low[i]<-64||high[i]>63||low[i]>high[i]||
        decode(in[i],encoding)<low[i]||decode(in[i],encoding)>high[i])return -2;
    uint8_t next[1280];for(unsigned i=0;i<1280;i++)next[i]=in[i];
    int active=0;for(unsigned i=0;i<5;i++)active|=controls[i];
    if(active)for(unsigned column=0;column<81;column++){
        int lower[5],upper[5],previous=0;
        for(unsigned row=0;row<5;row++){
            unsigned i=row*81+column;int anchor=(int)row*64;
            lower[row]=clamp(anchor+(low?low[i]:-64),0,256);
            upper[row]=clamp(anchor+(high?high[i]:63),0,256);
        }
        /* A future row's upper bound also bounds every earlier monotone row. */
        for(int row=3;row>=0;row--)if(upper[row]>upper[row+1])upper[row]=upper[row+1];
        for(unsigned row=0;row<5;row++){
            unsigned i=row*81+column;int anchor=(int)row*64;
            int floor=lower[row]>previous?lower[row]:previous;
            if(floor>upper[row])return -2;
            int y=clamp(anchor+decode(in[i],encoding),0,256);
            y=clamp(a7_fl_fivepoint_sample(knots,y),floor,upper[row]);
            /* A factory black node may have a negative code while its effective
             * luminance is clamped to zero (similarly above white). Preserve
             * the encoded bound as well as the physical luminance bound. */
            int code=clamp(y-anchor,low?low[i]:-64,high?high[i]:63);
            previous=clamp(anchor+code,0,256);
            next[i]=(uint8_t)(code&(encoding?127:255));
        }
    }
    for(unsigned i=0;i<1280;i++)out[i]=next[i];
    return 0;
}
int a7_fl_fivepoint_preview(const uint8_t base[1280],const uint16_t expand[129],
                           const uint8_t compress[513],const A7FLColorParams *color,
                           const int controls[5],uint8_t out[1280]){
    uint8_t candidate[1280];
    if(!out||a7_fl_adjust_lut(base,1280,expand,compress,color,candidate,1280))return -1;
    return a7_fl_fivepoint_lut(candidate,1280,out,1280,0,controls,0,0);
}
