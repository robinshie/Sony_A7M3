#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "../payloads/a7-fl-color.h"
static uint16_t expansion[129];
static uint8_t compression[513],base[1280];
static unsigned cases;
static void verify(A7FLColorParams p) {
    uint8_t guarded[1282];memset(guarded,0xa5,sizeof guarded);
    assert(a7_fl_adjust_lut(base,1280,expansion,compression,&p,guarded+1,1280)==0);
    assert(guarded[0]==0xa5 && guarded[1281]==0xa5);
    assert(!memcmp(guarded+1+1215,base+1215,65));
    for(unsigned i=0;i<1215;i++)assert(a7_fl_signed(guarded[i+1])>=-64 && a7_fl_signed(guarded[i+1])<=63);
    if(p.contrast || p.highlights || p.shadows || p.fade) {
        for(int b=0;b<9;b++)for(int c=0;c<9;c++) {
            int previous=0;
            for(int a=0;a<5;a++) {
                int y=a*64+a7_fl_signed(guarded[1+a*81+b*9+c]);
                assert(y>=previous && y<=256);previous=y;
            }
        }
    }
    cases++;
}
int main(void) {
    for(unsigned i=0;i<129;i++)expansion[i]=i*4;
    for(unsigned i=0;i<513;i++)compression[i]=(i+2)/4>128?128:(i+2)/4;
    for(unsigned i=1215;i<1280;i++)base[i]=(uint8_t)(i*37);
    A7FLColorParams zero={0,0,0,0,0};uint8_t out[1280];
    assert(a7_fl_adjust_lut(base,1280,expansion,compression,&zero,out,1280)==0);
    assert(!memcmp(out,base,1280));
    for(int contrast=-9;contrast<=9;contrast++)
    for(int high=-9;high<=9;high++)for(int shadow=-9;shadow<=9;shadow++) {
        A7FLColorParams p={contrast,high,shadow,0,0};verify(p);p.fade=9;verify(p);
    }
    for(int sat=-9;sat<=9;sat++)for(int fade=0;fade<=9;fade++) {
        A7FLColorParams p={0,0,0,fade,sat};verify(p);
    }
    for(unsigned i=0;i<1215;i++)base[i]=(uint8_t)((int)(i%128)-64);
    for(int sat=-9;sat<=9;sat++) {
        A7FLColorParams p={0,0,0,0,sat};verify(p);
    }
    memcpy(out,base,1280);
    assert(a7_fl_adjust_lut(out,1280,expansion,compression,&zero,out,1280)==0);
    assert(!memcmp(out,base,1280));
    memset(out,0xa5,sizeof out);A7FLColorParams invalid=zero;invalid.fade=10;
    assert(a7_fl_adjust_lut(base,1280,expansion,compression,&invalid,out,1280)==-1);
    base[5]=127;
    assert(a7_fl_adjust_lut(base,1280,expansion,compression,&zero,out,1280)==-3);
    for(unsigned i=0;i<1280;i++)assert(out[i]==0xa5);
    printf("NATIVE_COLOR_BOUNDS_PASSED %u cases; five LUT controls only\n",cases);
    return 0;
}
