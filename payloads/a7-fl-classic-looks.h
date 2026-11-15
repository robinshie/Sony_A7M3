/* Original palettes inspired by color negative, documentary and portrait rendering. */
#ifndef A7_FL_CLASSIC_LOOKS_H
#define A7_FL_CLASSIC_LOOKS_H
#include "a7-fl-color.h"
#include "a7-fl-runtime-prefs.h"

struct a7_classic_look {
    int tone[5];               /* Luma offsets at 0, 64, 128, 192, 256. */
    int saturation[5];         /* Chroma multiplier in Q8 at those same anchors. */
    int blue[5], red[5];       /* Signed offsets in the expanded chroma domain. */
    int hue_mix;               /* Mild cross-channel rotation, Q8. */
};
static const struct a7_classic_look a7_classic_looks[]={
    /* FL4: deep shadows, stronger midtone color, warm upper tones. */
    {{0,-13,-4,7,-7},{230,277,300,269,220},{0,15,2,-18,-8},{0,-10,6,16,5},-14},
    /* FL5: restrained color and distinctly cooler shadows. */
    {{0,-10,-7,1,-4},{190,183,201,220,224},{0,19,10,0,0},{0,-14,-8,0,0},8},
    /* FL6: gentle contrast, neutral darks, soft highlight shoulder. */
    {{0,4,7,3,-3},{250,253,251,246,235},{0,0,-2,-4,0},{0,1,4,3,0},0},
};

static inline int a7_classic_sample(const int knots[5],int y) {
    if(y==256)return knots[4];
    unsigned index=(unsigned)y>>6;
    return knots[index]+a7_fl_round_div((knots[index+1]-knots[index])*(y&63),64);
}

static inline int a7_classic_base(int preset,const uint8_t base[1280],
                                  const uint16_t *expand,const uint8_t *compress,uint8_t out[1280]) {
    if(preset<A7_FL_EXTENDED_FIRST||preset>A7_FL_PRESET_MAX||out==base)return -1;
    const struct a7_classic_look *look=&a7_classic_looks[preset-A7_FL_EXTENDED_FIRST];
    const A7FLColorParams zero={0,0,0,0,0};
    if(a7_fl_adjust_lut(base,1280,expand,compress,&zero,out,1280))return -1;
    for(int b=0;b<9;b++)for(int c=0;c<9;c++){
        int previous=0;
        for(int a=0;a<5;a++){
            unsigned i=(unsigned)(a*81+b*9+c);
            int y=a7_fl_clamp(a*64+a7_fl_signed(base[i]),0,256);
            int tone=a7_fl_clamp(y+a7_classic_sample(look->tone,y),a*64-64,a*64+63);
            tone=a7_fl_clamp(tone,previous,256);previous=tone;
            out[i]=(uint8_t)(tone-a*64);
            int code[2],grid[2],linear[2];
            for(unsigned p=0;p<2;p++){
                code[p]=a7_fl_signed(base[i+(p+1)*405]);
                grid[p]=a7_fl_clamp(((p?c:b)-4)*32+a7_fl_floor_div(code[p]*3,4),-128,128);
                linear[p]=a7_fl_expand(grid[p],expand);
            }
            int sat=a7_classic_sample(look->saturation,y);
            for(unsigned p=0;p<2;p++){
                int mix=p?-look->hue_mix:look->hue_mix;
                int target=a7_fl_round_div(sat*linear[p]+mix*linear[1-p],256)
                           +a7_classic_sample(p?look->red:look->blue,y);
                int delta=a7_fl_compress(target,compress)-grid[p];
                out[i+(p+1)*405]=(uint8_t)a7_fl_clamp(code[p]+a7_fl_round_div(delta*4,3),-64,63);
            }
        }
    }
    return 0;
}
#endif
