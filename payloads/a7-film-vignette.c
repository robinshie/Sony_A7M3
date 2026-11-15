#include "a7-film-vignette.h"
static int clip(int n,int lo,int hi){return n<lo?lo:n>hi?hi:n;}
static int overlaps(const void *a,size_t an,const void *b,size_t bn){
    uintptr_t x=(uintptr_t)a,y=(uintptr_t)b;
    return x>UINTPTR_MAX-an||y>UINTPTR_MAX-bn||(x<y+bn&&y<x+an);
}
size_t a7_film_vignette_workspace(unsigned width){
    if(width<2||width>A7_FILM_FRAME_MAX_DIMENSION||(width&1))return 0;
    size_t own=(size_t)(width+1025)*sizeof(uint16_t),base=a7_film_frame_workspace(width,1);
    return own>base?own:base;
}
static unsigned axis(unsigned position,unsigned count){
    if(count==1)return 0;
    int d=(int)(2*position)-(int)(count-1);
    return (unsigned)((uint64_t)((int64_t)d*d)*1024/((uint64_t)(count-1)*(count-1)));
}
static unsigned transform(unsigned value,int origin,unsigned gain,int low,int high){
    int delta=(int)value-origin;
    /* Signed division rounds towards zero on both host and ARM. */
    return (unsigned)clip(origin+delta*(int)gain/1024,low,high);
}
int a7_film_vignette_apply(struct a7_film_frame *f,int strength,void *work,size_t bytes){
    struct a7_film_frame_params neutral={0,0,1,0};
    if(!f||strength<-9||strength>9||
       (f->format!=A7_FILM_UYVY&&f->format!=A7_FILM_YUYV)||
       f->path!=A7_FILM_CAPTURE||bytes<a7_film_vignette_workspace(f->width)||
       a7_film_frame_validate(f,&neutral,work,bytes))return A7_FILM_FRAME_ARGUMENT;
    size_t need=a7_film_vignette_workspace(f->width);
    size_t used=(size_t)(f->height-1)*f->plane[0].stride+f->width*2;
    if(overlaps(work,need,f,sizeof *f)||overlaps(work,need,f->plane[0].data,used))
        return A7_FILM_FRAME_ARGUMENT;
    if(!strength)return 0;
    uint16_t *xaxis=work,*gain=xaxis+f->width;
    for(unsigned x=0;x<f->width;x++)xaxis[x]=(uint16_t)axis(x,f->width);
    int amplitude=strength<0?strength*768/9:strength*1024/9;
    for(unsigned q=0;q<=1024;q++){
        unsigned t=q<=128?0:(q-128)*1024/896;
        unsigned weight=(t*t/1024)*(3072-2*t)/1024;
        gain[q]=(uint16_t)(1024+amplitude*(int)weight/1024);
    }
    unsigned offset=f->format==A7_FILM_UYVY;
    int limited=f->range==A7_FILM_LIMITED,black=limited?16:0,white=limited?235:255;
    int clo=limited?16:0,chi=limited?240:255;
    typedef uint32_t word __attribute__((may_alias));
    unsigned aligned=!(((uintptr_t)f->plane[0].data|f->plane[0].stride)&3);
    for(unsigned y=0;y<f->height;y++){
        uint8_t *p=f->plane[0].data+(size_t)y*f->plane[0].stride;
        unsigned yy=axis(y,f->height);
        for(unsigned x=0;x<f->width;x+=2,p+=4){
            unsigned g0=gain[(xaxis[x]+yy)/2],g1=gain[(xaxis[x+1]+yy)/2];
            if(g0==1024&&g1==1024)continue;
            unsigned gc=(g0+g1)/2;
            uint32_t original=aligned?*(word *)p:(uint32_t)p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;
            uint32_t next=0;
            for(unsigned i=0;i<4;i++){
                unsigned value=(original>>(8*i))&255;
                unsigned mapped=(i&1)==offset?transform(value,black,i<2?g0:g1,black,white):transform(value,128,gc,clo,chi);
                next|=mapped<<(8*i);
            }
            if(next!=original){
                if(aligned)*(word *)p=next;
                else for(unsigned i=0;i<4;i++)p[i]=(uint8_t)(next>>(8*i));
            }
        }
    }
    return 0;
}
