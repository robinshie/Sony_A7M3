/* Independent full 2-D halo oracle, identity and curve semantics; host + ARM. */
#include "a7-film-texture.h"
#ifndef A7_TEXTURE_QEMU
#include <stdio.h>
#include <stdlib.h>
#endif
#ifdef A7_TEXTURE_QEMU
void *memcpy(void *dst,const void *src,size_t n){uint8_t *d=dst;const uint8_t *s=src;while(n--)*d++=*s++;return dst;}
#endif
#define W 19u
#define H 13u
#define STRIDE 63u
static uint8_t input[STRIDE*H+16],output[STRIDE*H+16],again[STRIDE*H+16];
static uint32_t work[W*70/4+8];
static unsigned cases,checks,checksum=2166136261u;
static void put(const char *s){
#ifdef A7_TEXTURE_QEMU
    volatile unsigned *uart=(volatile unsigned *)0x10009000;
    while(*s){while(uart[6]&32){}uart[0]=*s++;}
#else
    fputs(s,stdout);
#endif
}
static void number(unsigned n){char b[12];unsigned i=0;do{b[i++]=(char)('0'+n%10);n/=10;}while(n);while(i){char s[2]={b[--i],0};put(s);}}
static void stop(int failed){
#ifdef A7_TEXTURE_QEMU
    (void)failed;register unsigned r0 __asm__("r0")=0x18,r1 __asm__("r1")=0x20026;
    __asm__ volatile("svc 0xab":"+r"(r0),"+r"(r1)::"memory");while(1){}
#else
    exit(failed);
#endif
}
static void check(int ok,const char *why){checks++;if(!ok){put("FAIL ");put(why);put(" case=");number(cases);put("\n");stop(1);}}
static int clamp(int v,int hi){return v<0?0:v>hi?hi:v;}
static int luminance(const uint8_t *p){return (54*p[0]+183*p[1]+19*p[2]+128)/256;}
static uint32_t random_word(uint32_t n){n^=n>>16;n*=0x7feb352du;n^=n>>15;n*=0x846ca68bu;return n^(n>>16);}
static int curve_at(int v,const A7FilmTexture *p){
    const int x[5]={0,64,128,192,255};int knots[5];
    for(int i=0;i<5;i++){knots[i]=clamp(x[i]+4*p->curve[i],255);if(i&&knots[i]<knots[i-1])knots[i]=knots[i-1];}
    for(int i=0;i<4;i++)if(v<=x[i+1])return knots[i]+((v-x[i])*(knots[i+1]-knots[i])+(x[i+1]-x[i])/2)/(x[i+1]-x[i]);
    return knots[4];
}
static int highlight(const uint8_t *p,const A7FilmTexture *a){return clamp(curve_at(luminance(p),a)-200,55)*255/55;}
static void oracle(unsigned w,unsigned h,unsigned x,unsigned y,const A7FilmTexture *p,uint8_t out[3]){
    const uint8_t *a=input+y*STRIDE+x*3;int v=luminance(a),mapped=curve_at(v,p),glow=0,noise=0;
    if(p->halation){
        unsigned sum=0,n=0;
        for(int yy=(int)y-(int)p->radius;yy<=(int)y+(int)p->radius;yy++)
            for(int xx=(int)x-(int)p->radius;xx<=(int)x+(int)p->radius;xx++){
                sum+=(unsigned)highlight(input+(unsigned)clamp(yy,(int)h-1)*STRIDE+3*(unsigned)clamp(xx,(int)w-1),p);n++;
            }
        glow=clamp((int)((sum+n/2)/n)-highlight(a,p),255)*p->halation/24;
    }
    if(p->grain){
        uint32_t c=random_word(p->seed^(x/2)*0x9e3779b9u^(y/2)*0x85ebca6bu);
        uint32_t f=random_word(p->seed^0x51ed270bu^x*0x9e3779b9u^y*0x85ebca6bu);
        int cn=(int)(c%256)+(int)((c/256)%256)-255,fn=(int)(f%256)+(int)((f/256)%256)-255;
        int envelope=64+(mapped<128?mapped:255-mapped);
        noise=(3*cn+fn)*p->grain*envelope/65536;
    }
    out[0]=(uint8_t)clamp(a[0]+mapped-v+glow+noise,255);
    out[1]=(uint8_t)clamp(a[1]+mapped-v+glow*3/8+noise,255);
    out[2]=(uint8_t)clamp(a[2]+mapped-v+glow/8+noise,255);
}
static void exercise(unsigned w,unsigned h,unsigned pattern,A7FilmTexture p){
    uint32_t random=0x32748951;
    for(unsigned i=0;i<sizeof input;i++)input[i]=0xc7;
    for(unsigned i=0;i<sizeof output;i++)output[i]=0xa5;
    for(unsigned i=0;i<sizeof work/4;i++)work[i]=0xabababab;
    for(unsigned y=0;y<h;y++)for(unsigned x=0;x<w;x++)for(unsigned c=0;c<3;c++){
        random=random*1664525u+1013904223u;
        input[y*STRIDE+3*x+c]=(uint8_t)(pattern==0?0:pattern==1?128:pattern==2?255:
            pattern==3?(x==w/2&&y==h/2?255:64):pattern==4?(x<w/2?20:240):(random>>24));
    }
    size_t wn=a7_film_texture_workspace(w,p.radius);
    check(!a7_film_texture(input,sizeof input,STRIDE,output,sizeof output,STRIDE,w,h,&p,work+1,wn),"apply");
    check(work[0]==0xabababab,"workspace prefix");
    for(size_t i=4+wn;i<sizeof work;i++)check(((uint8_t *)work)[i]==0xab,"workspace suffix");
    for(unsigned y=0;y<h;y++)for(unsigned x=0;x<w;x++){
        uint8_t expected[3];oracle(w,h,x,y,&p,expected);
        for(unsigned c=0;c<3;c++){
            unsigned offset=y*STRIDE+3*x+c;
            check(output[offset]==expected[c],"independent 2-D oracle");
            checksum=(checksum^output[offset])*16777619u;
            if(!p.grain&&!p.halation&&!p.curve[0]&&!p.curve[1]&&!p.curve[2]&&!p.curve[3]&&!p.curve[4])
                check(output[offset]==input[offset],"identity");
        }
    }
    for(unsigned i=0;i<sizeof output;i++)if(i/STRIDE>=h||i%STRIDE>=3*w)check(output[i]==0xa5,"row padding");
    check(!a7_film_texture(input,sizeof input,STRIDE,again,sizeof again,STRIDE,w,h,&p,work+1,wn),"repeat apply");
    for(unsigned y=0;y<h;y++)for(unsigned x=0;x<3*w;x++)check(again[y*STRIDE+x]==output[y*STRIDE+x],"deterministic seed");
    cases++;
}
static void semantics(void){
    static uint8_t ramp[256*3],result[256*3];static uint32_t ws[256*70/4];
    A7FilmTexture p={0,0,{0,0,0,0,0},2,1};
    for(unsigned i=0;i<256;i++)for(unsigned c=0;c<3;c++)ramp[3*i+c]=(uint8_t)i;
    const unsigned x[5]={0,64,128,192,255};
    for(unsigned point=0;point<5;point++)for(int value=-9;value<=9;value++){
        p.curve[point]=value;
        check(!a7_film_texture(ramp,sizeof ramp,sizeof ramp,result,sizeof result,sizeof result,256,1,&p,ws,sizeof ws),"curve ramp");
        for(unsigned i=0;i<256;i++){
            check(result[3*i]==curve_at((int)i,&p),"curve full ramp");
            check(result[3*i]==result[3*i+1]&&result[3*i]==result[3*i+2],"gray preserved");
            if(i)check(result[3*i]>=result[3*(i-1)],"monotone curve");
        }
        for(unsigned k=0;k<5;k++)check(result[3*x[k]]==clamp((int)x[k]+(k==point?value*4:0),255),"independent curve knot");
        p.curve[point]=0;cases++;
    }
    /* Spatial effect needs neighboring highlights: uniform areas have no halo. */
    for(unsigned i=0;i<sizeof input;i++)input[i]=64;
    unsigned center=(H/2)*STRIDE+(W/2)*3;
    for(unsigned c=0;c<3;c++)input[center+c]=255;
    p.halation=9;
    check(!a7_film_texture(input,sizeof input,STRIDE,output,sizeof output,STRIDE,W,H,&p,work,sizeof work),"halo impulse");
    check(output[center+3]>64&&output[center+3]>output[center+4],"warm halo neighbor");
    check(output[0]==64&&output[center]==255,"halo stays local and does not blow white");
    p.halation=0;p.grain=9;
    for(unsigned i=0;i<sizeof input;i++)input[i]=128;
    check(!a7_film_texture(input,sizeof input,STRIDE,output,sizeof output,STRIDE,W,H,&p,work,sizeof work),"grain");
    unsigned varied=0;int total=0;
    for(unsigned y=0;y<H;y++)for(unsigned x0=0;x0<W;x0++){
        unsigned i=y*STRIDE+x0*3;varied+=output[i]!=128;total+=(int)output[i]-128;
        check(output[i]==output[i+1]&&output[i]==output[i+2],"monochrome grain");
    }
    check(varied>W*H/2&&total>-2*(int)(W*H)&&total<2*(int)(W*H),"grain texture without strong bias");
    p.seed++;
    check(!a7_film_texture(input,sizeof input,STRIDE,again,sizeof again,STRIDE,W,H,&p,work,sizeof work),"new grain seed");
    varied=0;for(unsigned y=0;y<H;y++)for(unsigned x0=0;x0<W;x0++)varied+=again[y*STRIDE+x0*3]!=output[y*STRIDE+x0*3];
    check(varied>W*H/2,"different seed changes grain");
}
static void rejection(void){
    A7FilmTexture p={0,0,{0,0,0,0,0},2,1};
    for(unsigned i=0;i<sizeof output;i++)output[i]=0xa5;
#define CALL(S,SN,SS,D,DN,DS,WW,HH,P,M,MN) a7_film_texture(S,SN,SS,D,DN,DS,WW,HH,P,M,MN)
#define VALID(P) CALL(input,sizeof input,STRIDE,output,sizeof output,STRIDE,W,H,P,work,sizeof work)
    check(CALL(input,1,STRIDE,output,sizeof output,STRIDE,W,H,&p,work,sizeof work)<0,"short input");
    check(CALL(input,sizeof input,STRIDE,output,1,STRIDE,W,H,&p,work,sizeof work)<0,"short output");
    check(CALL(input,sizeof input,STRIDE,input,sizeof input,STRIDE,W,H,&p,work,sizeof work)<0,"source output alias");
    check(CALL(input,sizeof input,STRIDE,output,sizeof output,STRIDE,W,H,&p,work,1)<0,"short workspace");
    check(CALL(input,sizeof input,STRIDE,output,sizeof output,STRIDE,W,H,&p,((uint8_t *)work)+1,sizeof work-1)<0,"unaligned scratch");
    check(CALL(input,sizeof input,STRIDE,output,sizeof output,STRIDE,W,H,&p,input,sizeof input)<0,"source workspace alias");
    check(CALL(input,sizeof input,STRIDE,output,sizeof output,STRIDE,W,H,&p,output,sizeof output)<0,"destination workspace alias");
    check(CALL(input,sizeof input,3*W-1,output,sizeof output,STRIDE,W,H,&p,work,sizeof work)<0,"bad stride");
    check(CALL(input,sizeof input,STRIDE,output,sizeof output,STRIDE,W,0,&p,work,sizeof work)<0,"zero height");
    check(CALL(0,sizeof input,STRIDE,output,sizeof output,STRIDE,W,H,&p,work,sizeof work)<0,"null input");
    check(CALL(input,sizeof input,STRIDE,0,sizeof output,STRIDE,W,H,&p,work,sizeof work)<0,"null output");
    check(VALID(0)<0,"null params");
    check(CALL(input,SIZE_MAX,UINT32_MAX,output,SIZE_MAX,UINT32_MAX,1,16384,&p,work,sizeof work)<0,"size overflow");
    for(unsigned k=0;k<5;k++)for(int v=-10;v<=10;v+=20){p.curve[k]=v;check(VALID(&p)<0,"curve range");p.curve[k]=0;}
    p.grain=10;check(VALID(&p)<0,"grain range");p.grain=-1;check(VALID(&p)<0,"grain negative");p.grain=0;
    p.halation=10;check(VALID(&p)<0,"halo range");p.halation=-1;check(VALID(&p)<0,"halo negative");p.halation=0;
    p.radius=0;check(VALID(&p)<0,"radius zero");p.radius=17;check(VALID(&p)<0,"radius bound");
    for(unsigned i=0;i<sizeof output;i++)check(output[i]==0xa5,"reject before write");
}
void guest_main(void){
    const unsigned dims[][2]={{1,1},{1,H},{W,1},{3,2},{W,H}},radii[]={1,2,7,16};
    const A7FilmTexture ps[]={
        {0,0,{0,0,0,0,0},1,1},{9,0,{0,0,0,0,0},1,1},
        {0,9,{0,0,0,0,0},1,7},{4,5,{2,-3,0,2,-2},1,1987},
        {9,9,{9,9,9,9,9},1,0xffffffff},{1,1,{-9,-9,-9,-9,-9},1,0},
        {5,8,{-9,9,-9,9,-9},1,7},{8,5,{9,-9,9,-9,9},1,9}};
    for(unsigned d=0;d<5;d++)for(unsigned pat=0;pat<6;pat++)for(unsigned r=0;r<4;r++)for(unsigned k=0;k<8;k++){
        A7FilmTexture p=ps[k];p.radius=radii[r];exercise(dims[d][0],dims[d][1],pat,p);
    }
    semantics();rejection();
    put("FILM_TEXTURE_CASES ");number(cases);put(" CHECKS ");number(checks);put(" CHECKSUM ");number(checksum);
    put("\nFILM_TEXTURE_PASSED\n");stop(0);
}
#ifndef A7_TEXTURE_QEMU
int main(void){guest_main();return 0;}
#endif
