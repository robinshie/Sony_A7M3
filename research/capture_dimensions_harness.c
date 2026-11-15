#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "a7-capture-geometry.h"
#include "a7-film-frame.h"
#include "a7-film-vignette.h"
static unsigned checks,frames;
static void check(int ok){checks++;if(!ok){fprintf(stderr,"DIMENSION_FAIL %u frame %u\n",checks,frames);exit(1);}}
static uint32_t pair(unsigned x,unsigned y){return x|(y<<16);}
static void bounds(void){
    struct a7_capture_geometry g,old;
    memset(&g,0x55,sizeof g);old=g;
    check(a7_capture_geometry_decode(0,0,0,0,&g)<0&&!memcmp(&g,&old,sizeof g));
    check(!a7_capture_geometry_decode(pair(6000,4000),pair(6080,4000),80,0x3000000,&g));
    check(g.offset==160&&g.stride==12160&&g.span==48639840&&g.canvas_bytes==48640000);
    check(!a7_capture_geometry_decode(pair(20,10),pair(32,16),pair(4,3),1024,&g));
    check(g.offset==200&&g.stride==64&&g.span==616);
    const uint32_t bad[][4]={
        {pair(19,10),pair(32,16),0,1024},{pair(20,0),pair(32,16),0,1024},
        {pair(20,10),pair(31,16),0,1024},{pair(20,10),pair(32,16),1,1024},
        {pair(20,10),pair(32,16),14,1024},{pair(20,10),pair(32,16),pair(0,7),1024},
        {pair(20,10),pair(32,16),0,1023},{pair(20,10),pair(65534,65535),0,0xffffffff},
        {pair(6002,4000),pair(6080,4000),0,0x3000000},
        {pair(6000,4001),pair(6080,4001),0,0x3000000},
        {pair(20,10),pair(32,16),0,0x3000001}};
    for(unsigned i=0;i<sizeof bad/sizeof bad[0];i++){
        old=g;check(a7_capture_geometry_decode(bad[i][0],bad[i][1],bad[i][2],bad[i][3],&g)<0);
        check(!memcmp(&g,&old,sizeof g));
    }
    check(a7_capture_geometry_decode(pair(20,10),pair(32,16),0,1024,NULL)<0);
}
static void frame(unsigned w,unsigned h,int halo,int vig,int grain){
    frames++;
    unsigned cw=w+16,ch=h+4,capacity=cw*ch*2;
    struct a7_capture_geometry g;
    check(!a7_capture_geometry_decode(pair(w,h),pair(cw,ch),pair(8,2),capacity,&g));
    unsigned char *storage=malloc(capacity+128),*original=malloc(capacity+128);
    check(storage&&original);memset(storage,0xa5,capacity+128);
    unsigned char *pixels=storage+64+g.offset;
    for(unsigned y=0;y<h;y++)for(unsigned x=0;x<w;x++){
        pixels[y*g.stride+2*x]=128;
        pixels[y*g.stride+2*x+1]=x<w/2?100:250;
    }
    memcpy(original,storage,capacity+128);
    struct a7_film_frame f={.width=w,.height=h,.format=A7_FILM_UYVY,.range=A7_FILM_FULL,
        .path=A7_FILM_CAPTURE,.plane={{pixels,capacity-g.offset,g.stride},{0}},.cookie=1,.sequence=frames};
    struct a7_film_frame_params p={grain,halo,a7_film_frame_reference_radius(w),1987};
    size_t need=a7_film_frame_workspace(w,p.radius),vn=a7_film_vignette_workspace(w);
    if(vn>need)need=vn;
    void *work=malloc(need);check(work!=NULL);
    check(!a7_film_frame_apply(&f,&p,work,need));
    check(!a7_film_vignette_apply(&f,vig,work,need));
    unsigned changed=0;
    for(unsigned i=0;i<capacity+128;i++){
        int inside=0;
        if(i>=64+g.offset){unsigned at=i-64-g.offset;inside=at/g.stride<h&&at%g.stride<w*2;}
        if(!inside)check(storage[i]==original[i]);
        else if(storage[i]!=original[i])changed++;
    }
    check((grain||halo||vig)?changed>0:changed==0);
    if(grain&&!halo&&!vig){
        for(unsigned y=0;y<h;y++)for(unsigned x=0;x<w;x++)check(pixels[y*g.stride+2*x]==128);
    }
    if(halo&&!vig&&!grain){unsigned at=(w/2-2)*2+1;
        check(halo>0?pixels[at]>100:pixels[at]<100);}
    if(vig&&!halo&&!grain)check(vig>0?pixels[1]>100:pixels[1]<100);
    free(work);free(original);free(storage);
}
int main(void){
    bounds();
    /* Synthetic size/stride cases, not claims about camera M/S descriptors. */
    const unsigned sizes[][2]={{6000,4000},{3936,2624},{3008,2000},{384,256},{2,1}};
    for(unsigned i=0;i<sizeof sizes/sizeof sizes[0];i++){
        unsigned w=sizes[i][0],h=sizes[i][1];
        frame(w,h,0,0,0);frame(w,h,0,0,9);
        if(w>2){frame(w,h,-9,0,0);frame(w,h,9,0,0);frame(w,h,0,-9,0);frame(w,h,0,9,0);frame(w,h,9,-9,9);}
    }
    printf("CAPTURE_DIMENSIONS_PASSED frames=%u checks=%u\n",frames,checks);
}
