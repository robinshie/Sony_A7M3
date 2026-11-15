/* Differential test against the unchanged reference path; owned memory only. */
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include "a7-film-frame.h"
extern int a7_film_frame_reference_apply(struct a7_film_frame *,const struct a7_film_frame_params *,void *,size_t);
static unsigned char a[2][(16384*2+20)*6+8],b[2][(16384*2+20)*6+8];
static uint32_t wa[16384*7/4+8],wb[16384*7/4+8];
static void need(int ok){if(!ok){fputs("GRAIN_FAST_FAIL\n",stderr);exit(1);}}
int main(void){
    const unsigned widths[]={2,24,576,578,960,6000,16384};
    unsigned cases=0;
    for(unsigned wi=0;wi<7;wi++)for(unsigned fmt=1;fmt<=4;fmt++)
    for(unsigned range=1;range<=2;range++)for(unsigned level=0;level<=9;level++)
    for(unsigned seed=0;seed<3;seed++)for(unsigned layout=0;layout<4;layout++){
        unsigned offset=layout==1?1:layout==2?2:0;
        unsigned w=widths[wi],h=6,stride=w*(fmt<3?1:2)+16+(layout==3?2:0);
        size_t size=(size_t)stride*h;
        for(unsigned plane=0;plane<2;plane++)for(size_t i=0;i<size+8;i++)
            a[plane][i]=b[plane][i]=(uint8_t)(i*13+plane*37+seed*53);
        struct a7_film_frame f={w,h,fmt,range,A7_FILM_PREVIEW,
            {{a[0]+offset,size,stride},{0,0,0}},1,1},g=f;
        g.plane[0].data=b[0]+offset;
        if(fmt<3){f.plane[1]=(struct a7_film_plane){a[1]+offset,size,stride};g.plane[1]=f.plane[1];g.plane[1].data=b[1]+offset;}
        struct a7_film_frame_params p={(int)level,0,1,seed*0x517cc1b7u};
        size_t wn=a7_film_frame_workspace(w,1);
        memset(wa,0xa5,sizeof wa);memset(wb,0xa5,sizeof wb);
        need(!a7_film_frame_apply(&f,&p,wa,wn));
        need(!a7_film_frame_reference_apply(&g,&p,wb,wn));
        for(unsigned plane=0;plane<2;plane++)need(!memcmp(a[plane],b[plane],size+8));
        for(size_t i=wn;i<sizeof wa;i++)need(((uint8_t *)wa)[i]==0xa5);
        cases++;
    }
    printf("GRAIN_FAST_PASSED %u cases; exact pixels, chroma, padding and workspace bounds\n",cases);
}
