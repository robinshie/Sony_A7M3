#include "a7-film-texture.h"
static int clamp(int v,int lo,int hi){return v<lo?lo:v>hi?hi:v;}
static unsigned y8(const uint8_t *p){return (54u*p[0]+183u*p[1]+19u*p[2]+128u)>>8;}
static uint32_t mix(uint32_t n){n^=n>>16;n*=0x7feb352du;n^=n>>15;n*=0x846ca68bu;return n^(n>>16);}
static int overlaps(const void *a,size_t an,const void *b,size_t bn){
    uintptr_t x=(uintptr_t)a,y=(uintptr_t)b;
    return x>UINTPTR_MAX-an||y>UINTPTR_MAX-bn|| (x<y+bn&&y<x+an);
}
size_t a7_film_texture_workspace(unsigned w,unsigned r){
    if(!w||w>16384||r<1||r>16)return 0;
    size_t ring=(size_t)w*(2*r+1)*sizeof(uint16_t);
    return ((ring+3)&~(size_t)3)+(size_t)w*sizeof(uint32_t);
}
static unsigned mask(const uint8_t *p,const uint8_t curve[256]){
    int v=(int)curve[y8(p)]-200;return v>0?(unsigned)(v*255/55):0;
}
static void horizontal(const uint8_t *row,unsigned w,unsigned r,const uint8_t curve[256],uint16_t *out){
    unsigned sum=0;
    for(int d=-(int)r;d<=(int)r;d++)sum+=mask(row+3*(unsigned)clamp(d,0,(int)w-1),curve);
    for(unsigned x=0;x<w;x++){
        out[x]=(uint16_t)sum;
        sum-=mask(row+3*(unsigned)clamp((int)x-(int)r,0,(int)w-1),curve);
        sum+=mask(row+3*(unsigned)clamp((int)x+(int)r+1,0,(int)w-1),curve);
    }
}
int a7_film_texture(const uint8_t *src,size_t sn,unsigned ss,uint8_t *dst,size_t dn,unsigned ds,
                    unsigned w,unsigned h,const A7FilmTexture *p,void *workspace,size_t wn){
    if(!src||!dst||!p||!workspace||!w||!h||w>16384||h>16384||w>ss/3||w>ds/3)return -1;
    if(p->grain<0||p->grain>9||p->halation<0||p->halation>9)return -1;
    for(unsigned i=0;i<5;i++)if(p->curve[i]<-9||p->curve[i]>9)return -1;
    size_t needed=a7_film_texture_workspace(w,p->radius);
    if(h>1&&(ss>(SIZE_MAX-(size_t)3*w)/(h-1)||ds>(SIZE_MAX-(size_t)3*w)/(h-1)))return -1;
    size_t used_src=(size_t)(h-1)*ss+3*w,used_dst=(size_t)(h-1)*ds+3*w;
    if(!needed||wn<needed||((uintptr_t)workspace&3)||sn<used_src||dn<used_dst||
       overlaps(src,used_src,dst,used_dst)||overlaps(src,used_src,workspace,needed)||
       overlaps(dst,used_dst,workspace,needed)||overlaps(p,sizeof *p,dst,used_dst)||
       overlaps(p,sizeof *p,workspace,needed))return -1;
    static const int x[5]={0,64,128,192,255};int knots[5];uint8_t curve[256];
    for(unsigned i=0;i<5;i++)knots[i]=clamp(x[i]+p->curve[i]*4,i?knots[i-1]:0,255);
    unsigned part=0;
    for(unsigned v=0;v<256;v++){
        if(part<3&&(int)v>x[part+1])part++;
        int span=x[part+1]-x[part];
        curve[v]=(uint8_t)(knots[part]+((knots[part+1]-knots[part])*((int)v-x[part])+span/2)/span);
    }
    unsigned r=p->radius,rows=2*r+1,area=rows*rows;
    uint16_t *ring=workspace;
    uint32_t *sum=(void *)((uint8_t *)workspace+(((size_t)w*rows*2+3)&~(size_t)3));
    if(p->halation){
        for(unsigned i=0;i<w;i++)sum[i]=0;
        for(unsigned row=0;row<rows;row++){
            unsigned sy=(unsigned)clamp((int)row-(int)r,0,(int)h-1);
            horizontal(src+(size_t)sy*ss,w,r,curve,ring+(size_t)row*w);
            for(unsigned i=0;i<w;i++)sum[i]+=ring[(size_t)row*w+i];
        }
    }
    for(unsigned y=0;y<h;y++){
        for(unsigned x0=0;x0<w;x0++){
            const uint8_t *a=src+(size_t)y*ss+3*x0;uint8_t *b=dst+(size_t)y*ds+3*x0;
            int luma=(int)y8(a),shift=(int)curve[luma]-luma,glow=0,noise=0;
            if(p->halation){
                int halo=(int)((sum[x0]+area/2)/area)-(int)mask(a,curve);
                glow=clamp(halo,0,255)*p->halation/24;
            }
            if(p->grain){
                uint32_t coarse=mix(p->seed^(x0/2)*0x9e3779b9u^(y/2)*0x85ebca6bu);
                uint32_t fine=mix(p->seed^0x51ed270bu^x0*0x9e3779b9u^y*0x85ebca6bu);
                int c=(int)(coarse&255)+(int)((coarse>>8)&255)-255;
                int f=(int)(fine&255)+(int)((fine>>8)&255)-255;
                int level=(int)curve[luma],envelope=64+(level<128?level:255-level);
                noise=(3*c+f)*p->grain*envelope/(4*128*128);
            }
            b[0]=(uint8_t)clamp(a[0]+shift+glow+noise,0,255);
            b[1]=(uint8_t)clamp(a[1]+shift+glow*3/8+noise,0,255);
            b[2]=(uint8_t)clamp(a[2]+shift+glow/8+noise,0,255);
        }
        if(p->halation&&y+1<h){
            uint16_t *line=ring+(size_t)(y%rows)*w;
            for(unsigned i=0;i<w;i++)sum[i]-=line[i];
            unsigned sy=(unsigned)clamp((int)y+(int)r+1,0,(int)h-1);
            horizontal(src+(size_t)sy*ss,w,r,curve,line);
            for(unsigned i=0;i<w;i++)sum[i]+=line[i];
        }
    }
    return 0;
}
