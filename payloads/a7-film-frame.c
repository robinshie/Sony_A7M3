#include "a7-film-frame.h"
#ifdef A7_FL_FILM_CONTROLS
#include "a7-fl-runtime-prefs.h"
#endif
static int clamp(int v,int a,int b){return v<a?a:v>b?b:v;}
static uint32_t hash(uint32_t x){x^=x>>16;x*=0x7feb352du;x^=x>>15;x*=0x846ca68bu;return x^(x>>16);}
unsigned a7_film_frame_reference_radius(unsigned width){
    if(!width||width>A7_FILM_FRAME_MAX_DIMENSION)return 0;
    unsigned r=(width*A7_FILM_REFERENCE_RADIUS+A7_FILM_REFERENCE_WIDTH/2)/A7_FILM_REFERENCE_WIDTH;
    return r?r:1;
}
#ifdef A7_FL_FILM_CONTROLS
int a7_film_frame_params_from_preference(const struct a7_fl_preference *p,unsigned width,
                                        uint32_t sequence,struct a7_film_frame_params *out){
    if(!p||!out||p->schema!=4||!p->generation||!a7_fl_preset_valid(p->enabled)||width<2||(width&1))return -1;
    unsigned radius=a7_film_frame_reference_radius(width);
    if(!radius)return -1;
    unsigned bank=p->enabled?(unsigned)p->enabled-1:0;
    for(unsigned i=0;i<7;i++)if(p->film[bank][i]<(i<2?0:-9)||p->film[bank][i]>9)return -1;
    struct a7_film_frame_params next={p->enabled?p->film[bank][0]:0,p->enabled?p->film[bank][1]:0,
        radius,hash(1987u^sequence)};
    *out=next;return 0;
}
#endif
static int overlap(const void *a,size_t an,const void *b,size_t bn){
    uintptr_t x=(uintptr_t)a,y=(uintptr_t)b;
    return x>UINTPTR_MAX-an||y>UINTPTR_MAX-bn||(x<y+bn&&y<x+an);
}
static size_t used(const struct a7_film_plane *p,unsigned rows,unsigned rowbytes){
    if(!p->data||!rows||p->stride<rowbytes||(rows>1&&p->stride>(SIZE_MAX-rowbytes)/(rows-1)))return 0;
    size_t n=(size_t)(rows-1)*p->stride+rowbytes;
    return p->bytes<n||(uintptr_t)p->data>UINTPTR_MAX-n?0:n;
}
static int packed(const struct a7_film_frame *f){return f->format>=A7_FILM_YUYV;}
static unsigned chroma_rows(const struct a7_film_frame *f){return f->format==A7_FILM_NV12?f->height/2:f->height;}
static size_t plane_used(const struct a7_film_frame *f,unsigned i){
    return used(&f->plane[i],i?chroma_rows(f):f->height,f->width*(packed(f)?2:1));
}
size_t a7_film_frame_workspace(unsigned w,unsigned r){
    if(!w||w>A7_FILM_FRAME_MAX_DIMENSION||r<1||r>A7_FILM_FRAME_MAX_RADIUS)return 0;
    return (size_t)w*(r+6); /* uint32_t vertical sums, byte history, byte NV12 glow */
}
int a7_film_frame_validate(const struct a7_film_frame *f,const struct a7_film_frame_params *p,void *ws,size_t wn){
    if(!f||!p||!ws||((uintptr_t)ws&3)||f->width<2||f->width>A7_FILM_FRAME_MAX_DIMENSION||
       (f->width&1)||!f->height||f->height>A7_FILM_FRAME_MAX_DIMENSION||
       f->format<A7_FILM_NV12||f->format>A7_FILM_UYVY||f->range<A7_FILM_FULL||f->range>A7_FILM_LIMITED||
       f->path<A7_FILM_PREVIEW||f->path>A7_FILM_CAPTURE||!f->cookie||
       (f->format==A7_FILM_NV12&&(f->height&1))||p->grain<0||p->grain>9||p->halation<0||p->halation>9)return -1;
    size_t need=a7_film_frame_workspace(f->width,p->radius),n[2]={plane_used(f,0),0};
    if(!need||need>wn||!n[0]||overlap(f,sizeof *f,ws,need)||overlap(p,sizeof *p,ws,need))return -1;
    if(packed(f)) {if(f->plane[1].data||f->plane[1].bytes||f->plane[1].stride)return -1;}
    else {n[1]=plane_used(f,1);if(!n[1]||overlap(f->plane[0].data,n[0],f->plane[1].data,n[1]))return -1;}
    for(unsigned i=0;i<2;i++)if(n[i]&&(overlap(f->plane[i].data,n[i],ws,need)||
        overlap(f->plane[i].data,n[i],f,sizeof *f)||overlap(f->plane[i].data,n[i],p,sizeof *p)))return -1;
    return 0;
}
static uint8_t *yp(const struct a7_film_frame *f,unsigned x,unsigned y){
    return f->plane[0].data+(size_t)y*f->plane[0].stride+(packed(f)?2*x+(f->format==A7_FILM_UYVY):x);
}
static unsigned window_start(const uint32_t *v,unsigned count,unsigned radius){
    unsigned last=count-1,hi=radius<last?radius:last;
    unsigned sum=v[0]*(radius+1)+v[hi]*(radius-hi);
    for(unsigned i=1;i<=hi;i++)sum+=v[i];
    return sum;
}
static int grain_field(unsigned x,unsigned y,uint32_t seed){
    uint32_t c=hash(seed^(x/2)*0x9e3779b9u^(y/2)*0x85ebca6bu);
    uint32_t n=hash(seed^0x51ed270bu^x*0x9e3779b9u^y*0x85ebca6bu);
    int cn=(int)(c&255)+(int)((c>>8)&255)-255,fn=(int)(n&255)+(int)((n>>8)&255)-255;
    return 3*cn+fn;
}
int a7_film_frame_apply(struct a7_film_frame *f,const struct a7_film_frame_params *p,void *ws,size_t wn){
    if(a7_film_frame_validate(f,p,ws,wn))return A7_FILM_FRAME_ARGUMENT;
    if(!p->grain&&!p->halation)return 0; /* including out-of-range studio codes */
    unsigned w=f->width,h=f->height,r=p->radius,rows=2*r+1,area=rows*rows;
    /* One reciprocal per frame replaces a software divide per pixel on A9.
     * floor(n/area) is recovered exactly with at most one correction. */
    uint32_t reciprocal=(uint32_t)(((uint64_t)1<<32)/area);
    uint32_t *vertical=ws;
    uint8_t *history=(uint8_t *)(vertical+w);
    uint8_t *previous=history+(size_t)w*(r+1);
    uint8_t masks[256],levels[256];
    int limited=f->range==A7_FILM_LIMITED;
    for(unsigned i=0;i<256;i++){
        int v=limited?clamp(((int)i-16)*255/219,0,255):(int)i;
        levels[i]=(uint8_t)v;
        masks[i]=(uint8_t)(v>200?(v-200)*255/55:0);
    }
    if(p->halation){
        unsigned hi=r<h?r:h-1;
        for(unsigned x=0;x<w;x++)
            vertical[x]=(r+1)*masks[*yp(f,x,0)]+(r-hi)*masks[*yp(f,x,hi)];
        for(unsigned row=1;row<=hi;row++)
            for(unsigned x=0;x<w;x++)vertical[x]+=masks[*yp(f,x,row)];
    }
    /* Preserve grain scale when the output is viewed at the reference size.
     * Cache both reference-row samples for each cell, then interpolate with a
     * fixed-point phase. At small sizes the original noise remains exact. */
    unsigned grain_step=w>A7_FILM_REFERENCE_WIDTH?(A7_FILM_REFERENCE_WIDTH<<16)/w:1u<<16;
    for(unsigned y=0;y<h;y++){
        unsigned sum=p->halation?window_start(vertical,w,r):0;
        /* Preserve original masks until they leave the vertical window. The
         * entering row is strictly ahead of y, even with clamped edges. */
        uint8_t *line=history+(size_t)(y%(r+1))*w;
        unsigned gy=y*grain_step,gx=0,grain_x=UINT32_MAX;
        int grain_y_weight=(int)((gy>>8)&255),n00=0,n01=0,n10=0,n11=0;
        for(unsigned x=0;x<w;x+=2){
            unsigned glow_sum=0;
            for(unsigned k=0;k<2;k++){
                unsigned xx=x+k;uint8_t *a=yp(f,xx,y);int v=levels[*a],noise=0,glow=0;
                if(p->halation){
                    uint32_t numerator=sum+area/2;
                    unsigned mean=(unsigned)(((uint64_t)numerator*reciprocal)>>32);
                    if(numerator-mean*area>=area)mean++;
                    line[xx]=masks[*a];
                    int halo=(int)mean-(int)line[xx];
                    glow=clamp(halo,0,255)*p->halation/24;
                    if(xx+1<w){
                        unsigned left=xx>=r?xx-r:0,right=xx+r+1<w?xx+r+1:w-1;
                        sum=sum-vertical[left]+vertical[right];
                    }
                    if(f->format==A7_FILM_NV12){
                        if(!(y&1))previous[xx]=(uint8_t)glow;
                        else glow_sum+=previous[xx];
                    }
                    glow_sum+=(unsigned)glow;
                }
                if(p->grain){
                    int field;
                    if(w<=A7_FILM_REFERENCE_WIDTH)field=grain_field(xx,y,p->seed);
                    else{
                        unsigned xi=gx>>16,yi=gy>>16;
                        if(xi!=grain_x){
                            n00=grain_field(xi,yi,p->seed);n01=grain_field(xi+1,yi,p->seed);
                            n10=grain_field(xi,yi+1,p->seed);n11=grain_field(xi+1,yi+1,p->seed);
                            grain_x=xi;
                        }
                        int wx=(int)((gx>>8)&255);
                        int top=n00*(256-wx)+n01*wx,bottom=n10*(256-wx)+n11*wx;
                        field=(top*(256-grain_y_weight)+bottom*grain_y_weight)/65536;
                        gx+=grain_step;
                    }
                    noise=field*p->grain*(64+(v<128?v:255-v))/65536;
                }
                int delta=noise+glow/2;if(limited)delta=delta*219/255;
                /* Zero delta preserves headroom/footroom as well as identity. */
                if(delta)*a=(uint8_t)clamp((int)*a+delta,limited?16:0,limited?235:255);
            }
            if(p->halation&&(f->format!=A7_FILM_NV12||(y&1))){
                int glow=(int)(glow_sum/(f->format==A7_FILM_NV12?4:2));
                int cb=-glow*13/64,cr=glow*21/64;
                if(limited){cb=cb*224/255;cr=cr*224/255;}
                uint8_t *u,*v;
                if(packed(f)){
                    u=f->plane[0].data+(size_t)y*f->plane[0].stride+2*x+(f->format==A7_FILM_YUYV);
                    v=u+2;
                }else{
                    u=f->plane[1].data+(size_t)(f->format==A7_FILM_NV12?y/2:y)*f->plane[1].stride+x;v=u+1;
                }
                if(cb)*u=(uint8_t)clamp(*u+cb,limited?16:0,limited?240:255);
                if(cr)*v=(uint8_t)clamp(*v+cr,limited?16:0,limited?240:255);
            }
        }
        if(p->halation&&y+1<h){
            unsigned old=y>=r?y-r:0,next=y+r+1<h?y+r+1:h-1;
            const uint8_t *original=history+(size_t)(old%(r+1))*w;
            for(unsigned x=0;x<w;x++)vertical[x]=vertical[x]-original[x]+masks[*yp(f,x,next)];
        }
    }
    return 0;
}
static void increment(unsigned *n){if(*n!=UINT32_MAX)(*n)++;}
typedef int (*resolve_params)(const void *,const struct a7_film_frame *,struct a7_film_frame_params *);
static int dispatch(struct a7_film_frame_stage *s,uintptr_t token,unsigned path,
                    const void *settings,resolve_params resolve){
    if(!s||!settings||!s->io.acquire||!s->io.for_cpu||!s->io.for_device||!s->io.release||
       path<A7_FILM_PREVIEW||path>A7_FILM_CAPTURE)return A7_FILM_FRAME_ARGUMENT;
    if(__atomic_exchange_n(&s->lock,1,__ATOMIC_ACQUIRE))return A7_FILM_FRAME_BUSY;
    int rc=0,disposition=0;struct a7_film_frame f={0};struct a7_film_frame_params snapshot;
    if(s->fault){rc=A7_FILM_FRAME_FAULT;goto done;}
    rc=s->io.acquire(s->io.opaque,token,path,&f);
    if(rc){rc=rc==1?A7_FILM_FRAME_SKIP:A7_FILM_FRAME_ACQUIRE;goto done;}
    if(f.path!=path||resolve(settings,&f,&snapshot)||
       a7_film_frame_validate(&f,&snapshot,s->workspace,s->workspace_bytes)){
        rc=A7_FILM_FRAME_ARGUMENT;goto release;
    }
    if(overlap(s,sizeof *s,s->workspace,a7_film_frame_workspace(f.width,snapshot.radius))||
       overlap(s,sizeof *s,f.plane[0].data,plane_used(&f,0))||
       (!packed(&f)&&overlap(s,sizeof *s,f.plane[1].data,plane_used(&f,1)))){
        rc=A7_FILM_FRAME_ARGUMENT;goto release;
    }
    if(!snapshot.grain&&!snapshot.halation)goto release;
    if(s->io.for_cpu(s->io.opaque,&f)){rc=A7_FILM_FRAME_SYNC_CPU;goto release;}
    rc=a7_film_frame_apply(&f,&snapshot,s->workspace,s->workspace_bytes);
    if(!rc){
        disposition=1;
        if(s->io.for_device(s->io.opaque,&f)){disposition=-1;rc=A7_FILM_FRAME_SYNC_DEVICE;s->fault=1;}
    }
release:
    if(s->io.release(s->io.opaque,&f,disposition)){s->fault=1;rc=A7_FILM_FRAME_RELEASE;}
done:
    if(rc<0)increment(&s->failed);else if(rc==A7_FILM_FRAME_SKIP)increment(&s->skipped);
    else if(!rc&&disposition==1)increment(&s->processed[path-1]);
    __atomic_store_n(&s->lock,0,__ATOMIC_RELEASE);return rc;
}

static int fixed(const void *p,const struct a7_film_frame *f,struct a7_film_frame_params *out){
    (void)f;*out=*(const struct a7_film_frame_params *)p;return 0;
}
int a7_film_frame_dispatch(struct a7_film_frame_stage *s,uintptr_t token,unsigned path,
                            const struct a7_film_frame_params *p){
    if(!p)return A7_FILM_FRAME_ARGUMENT;
    struct a7_film_frame_params snapshot=*p;
    return dispatch(s,token,path,&snapshot,fixed);
}

#ifdef A7_FL_FILM_CONTROLS
static int preference(const void *p,const struct a7_film_frame *f,struct a7_film_frame_params *out){
    return a7_film_frame_params_from_preference(p,f->width,f->sequence,out);
}
int a7_film_frame_dispatch_preference(struct a7_film_frame_stage *s,uintptr_t token,unsigned path,
                                     const struct a7_fl_preference *p){
    if(!p)return A7_FILM_FRAME_ARGUMENT;
    struct a7_fl_preference snapshot=*p;
    return dispatch(s,token,path,&snapshot,preference);
}
#endif
