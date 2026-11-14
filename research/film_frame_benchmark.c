/* Owned synthetic memory only. No Sony calls, image hooks or firmware writes.
 * Measure the real CPU cost before choosing a live-frame integration route. */
#include <stdint.h>
#include "a7-film-frame.h"
#ifdef A7_FILM_BENCH_HOST
#include <stdio.h>
#include <time.h>
#else
void *memset(void *out,int value,size_t n) {
    uint8_t *p=out;for(size_t i=0;i<n;i++)p[i]=(uint8_t)value;return out;
}
static long syscall3(long nr,long a,long b,long c) {
    register long r7 __asm__("r7")=nr,r0 __asm__("r0")=a;
    register long r1 __asm__("r1")=b,r2 __asm__("r2")=c;
    __asm__ volatile("svc #0":"+r"(r0):"r"(r7),"r"(r1),"r"(r2):"memory","cc");
    return r0;
}
#endif
#if defined(A7_FILM_BENCH_FULL) && !defined(A7_FILM_BENCH_HOST)
#error Full-size experiment is host-only
#endif
struct sample {uint32_t width,height,grain,halation;int32_t rc;uint32_t elapsed_us,before,after;};
struct output {uint32_t magic,version,count,stopped;struct sample samples[12];};
static struct output result;
#ifdef A7_FILM_BENCH_FULL
static uint8_t pixels[6000*4000*2];
static uint32_t workspace[6000*(167+6)/4];
#else
static uint8_t pixels[960*540*2];
static uint32_t workspace[960*74/4];
#endif
static int now(uint32_t *seconds,uint32_t *nanoseconds) {
#ifdef A7_FILM_BENCH_HOST
    struct timespec t;if(clock_gettime(CLOCK_MONOTONIC,&t))return -1;
#else
    struct {int32_t tv_sec,tv_nsec;} t;
    if(syscall3(263,1,(long)&t,0))return -1;
#endif
    if(t.tv_sec<0||t.tv_nsec<0||t.tv_nsec>=1000000000)return -1;
    *seconds=(uint32_t)t.tv_sec;*nanoseconds=(uint32_t)t.tv_nsec;return 0;
}
static uint32_t checksum(unsigned bytes) {
    uint32_t c=2166136261u;
    for(unsigned i=0;i<bytes;i++)c=(c^pixels[i])*16777619u;
    return c;
}
static void fill(unsigned w,unsigned h) {
    for(unsigned y=0;y<h;y++)for(unsigned x=0;x<w;x+=2) {
        unsigned a=(y*w+x)*2;
        pixels[a]=(uint8_t)(96+(x/16)%64);pixels[a+2]=(uint8_t)(96+(y/8)%64);
        for(unsigned k=0;k<2;k++)pixels[a+1+2*k]=
            (uint8_t)(((x+k)%80<8&&y%60<8)?250:32+((x+k)*3+y*5)%150);
    }
}
static void run(void) {
    result.magic=0x41374642;result.version=1;
#ifdef A7_FILM_BENCH_FULL
    const unsigned widths[3]={576,960,6000},heights[3]={384,540,4000};
#else
    const unsigned widths[3]={320,640,960},heights[3]={180,360,540};
#endif
#ifndef A7_FILM_BENCH_HOST
    uint32_t total=0;
#endif
    for(unsigned size=0;size<3;size++)for(unsigned effect=0;effect<4;effect++) {
        unsigned w=widths[size],h=heights[size];
        struct sample *s=&result.samples[result.count];
        s->width=w;s->height=h;s->grain=(effect&1)?5:0;s->halation=(effect&2)?6:0;
        struct a7_film_frame frame={w,h,A7_FILM_UYVY,A7_FILM_FULL,A7_FILM_PREVIEW,
            {{pixels,w*h*2,w*2},{0,0,0}},1,1};
#ifdef A7_FILM_BENCH_FULL
        s->grain=(effect&1)?9:0;s->halation=(effect&2)?9:0;
        unsigned radius=a7_film_frame_reference_radius(w);
        if(!radius){result.stopped=3;return;}
#else
        unsigned radius=3;
#endif
        struct a7_film_frame_params p={(int)s->grain,(int)s->halation,radius,1987};
        uint32_t sec0,ns0,sec1,ns1;
        fill(w,h);s->before=checksum(w*h*2);
        if(now(&sec0,&ns0)){result.stopped=2;return;}
        s->rc=a7_film_frame_apply(&frame,&p,workspace,sizeof workspace);
        if(now(&sec1,&ns1)||sec1<sec0||sec1-sec0>10||
           (sec1==sec0&&ns1<ns0)){result.stopped=2;return;}
        int64_t elapsed=(int64_t)(sec1-sec0)*1000000000+(int64_t)ns1-ns0;
        s->elapsed_us=(uint32_t)(elapsed/1000);s->after=checksum(w*h*2);
        result.count++;
        if(s->rc){result.stopped=3;return;}
#ifndef A7_FILM_BENCH_HOST
        total+=s->elapsed_us;
        /* Check between bounded frames. This is not a preemptive deadline. */
        if(s->elapsed_us>250000||total>750000){result.stopped=1;return;}
#endif
    }
}
#ifdef A7_FILM_BENCH_HOST
int main(void){run();return fwrite(&result,1,sizeof result,stdout)==sizeof result?0:1;}
#else
_Static_assert(sizeof result==400,"benchmark report ABI");
__attribute__((constructor)) static void measure(void) {
    run();
    syscall3(10,(long)"/tmp/jiritsu/libJit.so",0,0);
    long fd=syscall3(5,(long)"/tmp/jiritsu/a7fb.bin",1|64|128|0x8000,0600);
    if(fd<0)return;
    unsigned at=0;
    while(at<sizeof result){
        long n=syscall3(4,fd,(long)((char*)&result+at),sizeof result-at);
        if(n<=0||(unsigned)n>sizeof result-at)break;
        at+=(unsigned)n;
    }
    syscall3(118,fd,0,0);syscall3(6,fd,0,0);
}
#endif
