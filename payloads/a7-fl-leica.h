/* Original warm, high-contrast film palette; not an official Leica LUT. */
#ifndef A7_FL_LEICA_H
#define A7_FL_LEICA_H
#include "a7-fl-color.h"
#include "a7-fl-leica-model.inc"
static inline int a7_leica_delta(unsigned channel,int y,int cb,int cr) {
    int k=y>>5,f=y&31;
    if(k==8){k=7;f=32;}
    /* cb/cr are a symmetric signed Q9 approximation to twice normalized Cb/Cr. */
    int w[5]={512,cb,cr,a7_fl_round_div(cb*cb,512),a7_fl_round_div(cr*cr,512)};
    int sum=0;
    for(unsigned n=0;n<5;n++) {
        const int16_t (*p)[3]=a7_leica_coefficients[n];
        sum+=w[n]*(p[k][channel]*(32-f)+p[k+1][channel]*f);
    }
    return a7_fl_round_div(sum,512*32);
}
static inline int a7_leica_base(const uint8_t base[1280],const uint16_t *expand,
                                 const uint8_t *compress,uint8_t out[1280]) {
    const A7FLColorParams zero={0,0,0,0,0};
    if(a7_fl_adjust_lut(base,1280,expand,compress,&zero,out,1280))return -1;
    for(int b=0;b<9;b++)for(int c=0;c<9;c++) {
        int previous=0;
        for(int a=0;a<5;a++) {
            unsigned i=(unsigned)(a*81+b*9+c);
            int y=a7_fl_clamp(a*64+a7_fl_signed(base[i]),0,256);
            int compressed[2],linear[2],code[2];
            for(unsigned p=0;p<2;p++) {
                code[p]=a7_fl_signed(base[i+(p+1)*405]);
                int grid=((p?c:b)-4)*32;
                compressed[p]=a7_fl_clamp(grid+a7_fl_floor_div(code[p]*3,4),-128,128);
                linear[p]=a7_fl_expand(compressed[p],expand);
            }
            int tone=a7_fl_clamp(y+a7_fl_round_div(a7_leica_delta(0,y,linear[0],linear[1]),4),0,256);
            tone=a7_fl_clamp(tone,a*64-64,a*64+63);
            tone=a7_fl_clamp(tone,previous,256);previous=tone;
            out[i]=(uint8_t)(tone-a*64);
            for(unsigned p=0;p<2;p++) {
                unsigned j=i+(p+1)*405;
                int delta=a7_leica_delta(p+1,y,linear[0],linear[1]);
                int mapped=a7_fl_compress(linear[p]+delta,compress);
                out[j]=(uint8_t)a7_fl_clamp(code[p]+a7_fl_round_div((mapped-compressed[p])*4,3),-64,63);
            }
        }
    }
    return 0;
}
#endif
