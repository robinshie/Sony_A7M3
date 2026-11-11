/* Host sanitizer tests for the same adjustment code compiled into ARM/QEMU. */
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#define W 640
#define H 480
#include "fl_lut.h"
#include "fl_adjust.h"

static void check_blur(int w,int h,int radius)
{
    for(int i=0;i<w*h;i++) fl_work[i]=((i*73197u)^0x817263)&0xffffff;
    fl_blur_image(w,h,radius);
    int n=2*radius+1;
    for(int y=0;y<h;y++) for(int x=0;x<w;x++) for(int c=0;c<3;c++) {
        unsigned total=0,shift=c*8;
        /* Independent direct 2D convolution; separable rounding may differ 1. */
        for(int dy=-radius;dy<=radius;dy++) for(int dx=-radius;dx<=radius;dx++)
            total+=(fl_work[fl_limit(y+dy,0,h-1)*w+fl_limit(x+dx,0,w-1)]>>shift)&255;
        int expected=(total+n*n/2)/(n*n),actual=(fl_blurred[y*w+x]>>shift)&255;
        assert(abs(actual-expected)<=1);
    }
}
int main(void)
{
    assert(fl_selftest() && fl_adjust_selftest());
    assert(!fl_adjust_changed(&fl_defaults));
    assert(sizeof fl_adjust_names/sizeof *fl_adjust_names==8);
    const int shapes[][2]={{1,1},{1,9},{11,1},{9,7}};
    for(unsigned i=0;i<sizeof shapes/sizeof *shapes;i++)
        for(int r=1;r<=12;r++) check_blur(shapes[i][0],shapes[i][1],r);
    FLAdjust a=fl_defaults;
    a.v[FL_HIGHLIGHTS]=9;assert(fl_tone(0xc0c0c0,&a)>0xc0c0c0);
    a=fl_defaults;a.v[FL_SHADOWS]=9;assert(fl_tone(0x303030,&a)>0x303030);
    a=fl_defaults;a.v[FL_FADE]=9;assert(fl_tone(0,&a)>0 && fl_tone(0xffffff,&a)<0xffffff);
    a=fl_defaults;a.v[FL_CONTRAST]=9;
    assert(fl_tone(0x303030,&a)<0x303030 && fl_tone(0xc0c0c0,&a)>0xc0c0c0);
    a=fl_defaults;a.v[FL_SATURATION]=-9;
    assert(fl_tone(0x808080,&a)==0x808080);
    uint32_t desaturated=fl_tone(0xff0000,&a);
    assert(((desaturated>>16)&255)-(desaturated&255)<255);
    /* Full LCD-sized data, nontrivial stride and outer/padding guards. */
    int stride=W+3,count=stride*H+2;
    uint32_t *buffer=malloc((unsigned)count*sizeof *buffer);assert(buffer);
    for(int i=0;i<count;i++) buffer[i]=0xdeadbeef;
    for(int y=0;y<H;y++) for(int x=0;x<W;x++) buffer[1+y*stride+x]=(x+y)*0x010203&0xffffff;
    a=fl_defaults;a.v[FL_SHARPNESS]=9;a.v[FL_CLARITY]=9;a.v[FL_RANGE]=1;
    assert(fl_process(buffer+1,stride,W,H,&a));
    assert(buffer[0]==0xdeadbeef && buffer[count-1]==0xdeadbeef);
    for(int y=0;y<H;y++) for(int x=W;x<stride;x++) assert(buffer[1+y*stride+x]==0xdeadbeef);
    assert(!fl_process(buffer,1,2,2,&a));
    assert(!fl_process(buffer,stride,W+1,H,&a));
    assert(!fl_process(buffer,stride,W,H+1,&a));
    assert(!fl_process(NULL,stride,W,H,&a));
    for(int i=0;i<8;i++) {
        a=fl_defaults;a.v[i]=fl_minimum[i]-1;assert(!fl_adjust_valid(&a));
        a.v[i]=fl_maximum[i]+1;assert(!fl_process(buffer+1,stride,W,H,&a));
    }
    free(buffer);
    puts("PASS: native LUT vectors; adjustment invariants; 48 independent blur checks; full-frame bounds; invalid dimensions/parameters (ASan/UBSan)");
    return 0;
}
