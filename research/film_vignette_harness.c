#include "a7-film-vignette.h"
#ifdef A7_FL_FILM_CONTROLS
#include "a7-fl-runtime-prefs.h"
#endif
#ifndef A7_TEXTURE_QEMU
#include <stdio.h>
#include <stdlib.h>
#endif
#ifdef A7_TEXTURE_QEMU
void *memcpy(void *d,const void *s,size_t n){uint8_t *a=d;const uint8_t *b=s;while(n--)*a++=*b++;return d;}
void *memset(void *d,int v,size_t n){uint8_t *a=d;while(n--)*a++=(uint8_t)v;return d;}
#endif
static unsigned cases,checks,checksum=2166136261u;
static void put(const char *s){
#ifdef A7_TEXTURE_QEMU
    volatile unsigned *u=(void *)0x10009000;while(*s){while(u[6]&32){}u[0]=*s++;}
#else
    fputs(s,stdout);
#endif
}
static void number(unsigned n){char b[12];unsigned i=0;do{b[i++]=(char)('0'+n%10);n/=10;}while(n);while(i){char c[2]={b[--i],0};put(c);}}
static void stop(int status){
#ifdef A7_TEXTURE_QEMU
    (void)status;register unsigned r0 __asm__("r0")=0x18,r1 __asm__("r1")=0x20026;
    __asm__ volatile("svc 0xab":"+r"(r0),"+r"(r1)::"memory");while(1){}
#else
    exit(status);
#endif
}
static void check(int ok,const char *s){checks++;if(!ok){put("FAIL ");put(s);put(" case ");number(cases);put("\n");stop(1);}}

static uint8_t pixels[32*20+16],before[sizeof pixels];
static uint32_t work[800];
static unsigned oracle_gain(unsigned x,unsigned y,unsigned w,unsigned h,int strength){
    /* Direct scalar rational reference; no lookup tables or packed IO. */
    int64_t dx=(int64_t)2*x-(w-1),dy=(int64_t)2*y-(h-1);
    unsigned qx=(unsigned)(dx*dx*1024/((int64_t)(w-1)*(w-1)));
    unsigned qy=h==1?0:(unsigned)(dy*dy*1024/((int64_t)(h-1)*(h-1)));
    unsigned q=(qx+qy)/2,t=q<=128?0:(q-128)*1024/896;
    int weight=(int)((t*t/1024)*(3072-2*t)/1024);
    int amplitude=strength<0?strength*768/9:strength*1024/9;
    return (unsigned)(1024+amplitude*weight/1024);
}
static int bound(int n,int a,int b){return n<a?a:n>b?b:n;}
static void exercise(unsigned w,unsigned h,unsigned fmt,unsigned range,int strength,unsigned unaligned){
    cases++;for(unsigned i=0;i<sizeof pixels;i++)pixels[i]=before[i]=(uint8_t)((i*37+cases*19)&255);
    struct a7_film_frame f={.width=w,.height=h,.format=fmt,.range=range,.path=A7_FILM_CAPTURE,
        .plane={{pixels+4+unaligned,32*h,32},{0}},.cookie=1,.sequence=1};
    check(!a7_film_vignette_apply(&f,strength,work,sizeof work),"valid frame");
    unsigned offset=fmt==A7_FILM_UYVY;
    for(unsigned y=0;y<h;y++)for(unsigned x=0;x<w;x+=2){
        unsigned g[2]={oracle_gain(x,y,w,h,strength),oracle_gain(x+1,y,w,h,strength)};
        for(unsigned i=0;i<4;i++){
            unsigned at=4+unaligned+y*32+2*x+i;int value=before[at],target=value;
            if(strength&&(g[0]!=1024||g[1]!=1024)){
                int luma=(i&1)==offset,origin=luma?(range==2?16:0):128;
                int lo=range==2?16:0,hi=range==2?(luma?235:240):255;
                unsigned gain=luma?g[i/2]:(g[0]+g[1])/2;
                target=bound(origin+(value-origin)*(int)gain/1024,lo,hi);
            }
            check(pixels[at]==target,"independent pixel reference");before[at]=(uint8_t)target;
        }
    }
    for(unsigned i=0;i<sizeof pixels;i++){check(pixels[i]==before[i],"padding and guards unchanged");checksum=(checksum^pixels[i])*16777619u;}
}
static void guards(void){
    struct a7_film_frame f={.width=12,.height=8,.format=A7_FILM_UYVY,.range=A7_FILM_FULL,.path=A7_FILM_CAPTURE,.plane={{pixels,32*8,32},{0}},.cookie=1};
    for(unsigned i=0;i<sizeof pixels;i++)pixels[i]=before[i]=128;
    check(a7_film_vignette_apply(&f,10,work,sizeof work)<0,"out of range");
    check(a7_film_vignette_apply(&f,-10,work,sizeof work)<0,"negative range");
    check(a7_film_vignette_apply(&f,9,work,8)<0,"short workspace");
    check(a7_film_vignette_apply(&f,9,pixels,sizeof pixels)<0,"aliased workspace");
    f.plane[0].data=(uint8_t *)work+1000;
    check(a7_film_vignette_apply(&f,9,work,sizeof work)<0,"lookup tail overlaps source");
    f.plane[0].data=pixels;
    f.path=A7_FILM_PREVIEW;check(a7_film_vignette_apply(&f,9,work,sizeof work)<0,"preview rejected");
    f.path=A7_FILM_CAPTURE;f.plane[0].bytes=4;check(a7_film_vignette_apply(&f,9,work,sizeof work)<0,"short plane");
    for(unsigned i=0;i<sizeof pixels;i++)check(pixels[i]==before[i],"no writes on rejection");
    f.plane[0].bytes=32*8;
    check(!a7_film_vignette_apply(&f,-9,work,sizeof work),"dark sample");
    check(pixels[1]==32&&pixels[3*32+2*6+1]==128,"dark corner, unchanged center");
    for(unsigned i=0;i<sizeof pixels;i++)pixels[i]=80;
    check(!a7_film_vignette_apply(&f,9,work,sizeof work),"bright sample");
    check(pixels[1]==160&&pixels[3*32+2*6+1]==80,"bright corner, unchanged center");
    cases++;
}
int main(void){
    for(unsigned w=2;w<=12;w+=2)for(unsigned h=1;h<=8;h++)for(unsigned fmt=3;fmt<=4;fmt++)
      for(unsigned range=1;range<=2;range++)for(int s=-9;s<=9;s++)for(unsigned u=0;u<=1;u++)exercise(w,h,fmt,range,s,u);
    guards();put("VIGNETTE_PASSED cases=");number(cases);put(" checks=");number(checks);put(" checksum=");number(checksum);put("\n");stop(0);return 0;
}
#ifdef A7_TEXTURE_QEMU
void guest_main(void){(void)main();}
#endif
