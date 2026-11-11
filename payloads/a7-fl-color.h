/* Native-table scalar controls for the experimental FL runtime.
 * This operates on the experimentally interpreted Y/compressed-chroma grid.
 * It does not implement any spatial sharpness/range/clarity processing. */
#ifndef A7_FL_COLOR_H
#define A7_FL_COLOR_H
#include <stdint.h>
typedef struct {
    int contrast, highlights, shadows, fade, saturation;
} A7FLColorParams;
static int a7_fl_clamp(int x,int low,int high) {return x<low?low:x>high?high:x;}
static int a7_fl_signed(unsigned char x) {return x<128?(int)x:(int)x-256;}
static int a7_fl_floor_div(int x,int n) {return x>=0?x/n:-((-x+n-1)/n);}
static int a7_fl_round_div(int x,int n) {return x>=0?(x+n/2)/n:-((-x+n/2)/n);}
static int a7_fl_expand(int x,const uint16_t *table) {
    int sign=x<0?-1:1;
    return sign*table[a7_fl_clamp(x*sign,0,128)];
}
static int a7_fl_compress(int x,const uint8_t *table) {
    int sign=x<0?-1:1;
    return sign*table[a7_fl_clamp(x*sign,0,512)];
}
static int a7_fl_params_valid(const A7FLColorParams *p) {
    return p && p->contrast>=-9 && p->contrast<=9 &&
        p->highlights>=-9 && p->highlights<=9 && p->shadows>=-9 && p->shadows<=9 &&
        p->fade>=0 && p->fade<=9 && p->saturation>=-9 && p->saturation<=9;
}
/* Return zero on success. Invalid inputs leave the output untouched.
 * Caller must provide 129 expansion and 513 compression entries.
 * In-place base == output is supported. The 65-byte property tail is retained. */
static int a7_fl_adjust_lut(const uint8_t *base,unsigned base_size,
                           const uint16_t *expand,const uint8_t *compress,
                           const A7FLColorParams *p,uint8_t *output,unsigned output_size) {
    if(!base || !output || !expand || !compress || base_size!=1280 || output_size!=1280 ||
       !a7_fl_params_valid(p)) return -1;
    if(expand[0] || expand[128]!=512 || compress[0] || compress[512]!=128) return -2;
    for(unsigned i=1;i<129;i++) if(expand[i]<expand[i-1] || expand[i]>512) return -2;
    for(unsigned i=1;i<513;i++) if(compress[i]<compress[i-1] || compress[i]>128) return -2;
    for(unsigned i=0;i<1215;i++) {
        int value=a7_fl_signed(base[i]);if(value< -64 || value>63)return -3;
    }
    if(!p->contrast && !p->highlights && !p->shadows && !p->fade && !p->saturation) {
        for(unsigned i=0;i<1280;i++)output[i]=base[i];
        return 0;
    }
    uint8_t next[1280];
    for(unsigned i=0;i<1280;i++)next[i]=base[i];
    /* Keep each luminance column monotonic after tone edits. */
    for(int b=0;b<9;b++)for(int c=0;c<9;c++) {
        int previous=0;
        for(int a=0;a<5;a++) {
            unsigned i=(unsigned)(a*81+b*9+c);
            int old=a7_fl_signed(base[i]);
            int y=a7_fl_clamp(a*64+old,0,256);
            if(p->contrast || p->highlights || p->shadows || p->fade) {
                int lift=(p->highlights*y*y+p->shadows*(256-y)*(256-y))*6/65536;
                int adjusted=128+(y-128)*(256+p->contrast*14)/256+lift;
                adjusted=adjusted*(256-p->fade*5)/256+p->fade*4;
                adjusted=a7_fl_clamp(adjusted,0,256);
                int value=a7_fl_clamp(adjusted-a*64,-64,63);
                y=a7_fl_clamp(a*64+value,previous,256);
                next[i]=(uint8_t)(y-a*64);
            }
            previous=y;
            if(p->saturation) for(unsigned plane=1;plane<3;plane++) {
                unsigned at=i+plane*405;
                int value=a7_fl_signed(base[at]);
                int grid=((plane==1?b:c)-4)*32;
                int compressed=a7_fl_clamp(grid+a7_fl_floor_div(value*3,4),-128,128);
                int linear=a7_fl_expand(compressed,expand);
                int scaled=a7_fl_round_div(linear*(256+p->saturation*24),256);
                int result=a7_fl_compress(scaled,compress);
                value+=a7_fl_round_div((result-compressed)*4,3);
                next[at]=(uint8_t)a7_fl_clamp(value,-64,63);
            }
        }
    }
    for(unsigned i=0;i<1280;i++)output[i]=next[i];
    return 0;
}
#endif
