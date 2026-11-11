/* Independent slow 2-D convolution oracle against the streaming C kernel.
 * Runs unchanged on host with sanitizers and ARM in QEMU; no Sony bytes. */
#include "a7-fl-spatial.h"
#ifndef A7_SPATIAL_QEMU
#include <stdio.h>
#include <stdlib.h>
#endif
#define W 35u
#define H 33u
#define STRIDE 39u
static unsigned char input[STRIDE*H+16],output[STRIDE*H+16],blurs[6][W*H];
static uint32_t memory[W*70/4+8];
static unsigned cases,checks;
static void put(const char *s) {
#ifdef A7_SPATIAL_QEMU
    volatile unsigned *uart=(volatile unsigned *)0x10009000;
    while(*s){while(uart[6]&32){}uart[0]=*s++;}
#else
    fputs(s,stdout);
#endif
}
static void number(unsigned n) {char b[12];unsigned i=0;do{b[i++]=(char)('0'+n%10);n/=10;}while(n);while(i){char s[2]={b[--i],0};put(s);}}
static void stop(int failed) {
#ifdef A7_SPATIAL_QEMU
    (void)failed;
    register unsigned r0 __asm__("r0")=0x18,r1 __asm__("r1")=0x20026;
    __asm__ volatile("svc 0xab":"+r"(r0),"+r"(r1)::"memory");while(1){}
#else
    exit(failed);
#endif
}
static void check(int ok,const char *why) {checks++;if(!ok){put("FAIL ");put(why);put(" case=");number(cases);put("\n");stop(1);}}
static int cl(int x,int hi) {return x<0?0:x>hi?hi:x;}
static int round_signed(int x,int div) {int s=x<0?-1:1;return s*((s*x+div/2)/div);}
static void reference_blur(unsigned w,unsigned h,unsigned r,unsigned char *out) {
    for(unsigned y=0;y<h;y++)for(unsigned x=0;x<w;x++) {
        unsigned sum=0,count=0;
        for(int yy=(int)y-(int)r;yy<=(int)y+(int)r;yy++)
            for(int xx=(int)x-(int)r;xx<=(int)x+(int)r;xx++) {
                sum+=input[(unsigned)cl(yy,(int)h-1)*STRIDE+(unsigned)cl(xx,(int)w-1)];count++;
            }
        out[y*w+x]=(unsigned char)((sum+count/2)/count);
    }
}
static void exercise(unsigned w,unsigned h,unsigned pattern) {
    unsigned random=0x8f32a19;
    for(unsigned i=0;i<sizeof input;i++)input[i]=0xc7;
    for(unsigned y=0;y<h;y++)for(unsigned x=0;x<w;x++) {
        random=random*1664525+1013904223;
        unsigned value=pattern==0?0:pattern==1?128:pattern==2?255:
            pattern==3?(x==w/2&&y==h/2?255:64):pattern==4?(x<w/2?96:160):
            pattern==5?(x*13+y*7)%256:random>>24;
        input[y*STRIDE+x]=(unsigned char)value;
    }
    for(unsigned r=1;r<=5;r++)reference_blur(w,h,r,blurs[r-1]);
    reference_blur(w,h,16,blurs[5]);
    for(int s=-3;s<=3;s++)for(int r=1;r<=5;r++)for(int c=0;c<=9;c++) {
        for(unsigned i=0;i<sizeof output;i++)output[i]=0xa5;
        for(unsigned i=0;i<sizeof memory/4;i++)memory[i]=0xdeadbeef;
        A7FLSpatialParams p={s,r,c};size_t wn=a7_fl_spatial_workspace(w);
        check(a7_fl_spatial_luma(input,sizeof input,STRIDE,output,sizeof output,STRIDE,w,h,&p,memory+1,wn)==0,"apply");
        check(memory[0]==0xdeadbeef,"workspace prefix");
        for(size_t i=4+wn;i<sizeof memory;i++)check(((unsigned char *)memory)[i]==((unsigned char *)memory)[i%4],"workspace suffix");
        for(unsigned y=0;y<h;y++)for(unsigned x=0;x<w;x++) {
            int original=input[y*STRIDE+x],value=original;
            if(s)value=cl(value+round_signed((original-blurs[5-r][y*w+x])*s,4),255);
            if(c) {
                int weight=original<128?original*2:2*(255-original);
                int d=round_signed((original-blurs[5][y*w+x])*c*weight,4590);
                d=d<-24?-24:d>24?24:d;value=cl(value+d,255);
            }
            check(output[y*STRIDE+x]==value,"naive 2-D oracle");
            if(pattern<=2||(!s&&!c))check(value==original,"constant/identity invariance");
        }
        for(unsigned i=0;i<sizeof output;i++)if(i/STRIDE>=h||i%STRIDE>=w)check(output[i]==0xa5,"destination padding");
        cases++;
    }
}
void guest_main(void) {
    const unsigned dims[][2]={{1,1},{1,33},{35,1},{2,3},{35,33}};
    for(unsigned d=0;d<5;d++)for(unsigned p=0;p<7;p++)exercise(dims[d][0],dims[d][1],p);
    A7FLSpatialParams p={0,1,0};
    for(unsigned i=0;i<sizeof output;i++)output[i]=0xa5;
    check(a7_fl_spatial_luma(input,sizeof input,STRIDE,input,sizeof input,STRIDE,W,H,&p,memory,sizeof memory)<0,"alias rejected");
    check(a7_fl_spatial_luma(input,sizeof input,STRIDE,output,sizeof output,STRIDE,W,H,&p,memory,2)<0,"short workspace");
    check(a7_fl_spatial_luma(input,sizeof input,STRIDE,output,sizeof output,STRIDE,W,H,&p,((char *)memory)+1,sizeof memory-1)<0,"unaligned workspace");
    check(a7_fl_spatial_luma(input,sizeof input,STRIDE,output,1,STRIDE,W,H,&p,memory,sizeof memory)<0,"short output");
    check(a7_fl_spatial_luma(input,1,STRIDE,output,sizeof output,STRIDE,W,H,&p,memory,sizeof memory)<0,"short input");
    check(a7_fl_spatial_luma(input,sizeof input,W-1,output,sizeof output,STRIDE,W,H,&p,memory,sizeof memory)<0,"short input stride");
    check(a7_fl_spatial_luma(input,sizeof input,STRIDE,output,sizeof output,W-1,W,H,&p,memory,sizeof memory)<0,"short output stride");
    check(a7_fl_spatial_luma(input,sizeof input,STRIDE,output,sizeof output,STRIDE,W,0,&p,memory,sizeof memory)<0,"empty image");
    static const A7FLSpatialParams invalid[]={{-4,1,0},{4,1,0},{0,0,0},{0,6,0},{0,1,-1},{0,1,10}};
    for(unsigned i=0;i<sizeof invalid/sizeof invalid[0];i++)
        check(a7_fl_spatial_luma(input,sizeof input,STRIDE,output,sizeof output,STRIDE,W,H,&invalid[i],memory,sizeof memory)<0,"parameter bounds");
    union {A7FLSpatialParams p;uint32_t words[40];unsigned char bytes[160];} alias;
    alias.p.sharpness=0;alias.p.range=1;alias.p.clarity=0;
    check(a7_fl_spatial_luma(input,sizeof input,STRIDE,alias.bytes,sizeof alias,2,2,2,&alias.p,memory,sizeof memory)<0,"parameters overlap output");
    check(a7_fl_spatial_luma(input,sizeof input,STRIDE,output,sizeof output,STRIDE,2,2,&alias.p,alias.words,sizeof alias)<0,"parameters overlap workspace");
    for(unsigned i=0;i<sizeof output;i++)check(output[i]==0xa5,"reject before output mutation");
    put("SPATIAL_REFERENCE_PASSED cases=");number(cases);put(" checks=");number(checks);put("\n");
    put("EXPERIMENTAL_REFERENCE_ONLY; NO_CAMERA_BUFFER_HOOK; NO_SONY_FL_EQUIVALENCE\n");stop(0);
}
#ifndef A7_SPATIAL_QEMU
int main(void){guest_main();return 0;}
#endif
