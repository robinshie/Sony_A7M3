#include "a7-film-frame.h"
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
static int clamp(int x,int lo,int hi){return x<lo?lo:x>hi?hi:x;}
static uint32_t rnd(uint32_t x){x^=x>>16;x*=0x7feb352du;x^=x>>15;x*=0x846ca68bu;return x^(x>>16);}
#define MAXW 24u
#define MAXH 12u
#define STRIDE 56u
static uint8_t buffer[2][STRIDE*MAXH+16],expected[2][STRIDE*MAXH+16];
static uint8_t y_original[MAXH][MAXW];
static uint32_t work[MAXW*(A7_FILM_FRAME_MAX_RADIUS+6)/4+12];
static unsigned glow[MAXH][MAXW];
static struct a7_film_frame frame(unsigned w,unsigned h,unsigned format,unsigned range){
    struct a7_film_frame f={w,h,format,range,A7_FILM_PREVIEW,{{buffer[0]+8,STRIDE*h,STRIDE},{0,0,0}},123,7};
    if(format<3)f.plane[1]=(struct a7_film_plane){buffer[1]+8,STRIDE*(format==1?h/2:h),STRIDE};
    return f;
}
static unsigned ypos(unsigned x,unsigned y,unsigned fmt){return 8+y*STRIDE+(fmt<3?x:2*x+(fmt==4));}
static unsigned luma(unsigned v,unsigned range){return range==1?v:(unsigned)clamp(((int)v-16)*255/219,0,255);}
static unsigned mask(unsigned x,unsigned y,unsigned range){return (unsigned)clamp((int)luma(y_original[y][x],range)-200,0,55)*255/55;}
static void oracle(struct a7_film_frame f,struct a7_film_frame_params p){
    unsigned w=f.width,h=f.height,fmt=f.format,limited=f.range==2;
    for(unsigned plane=0;plane<2;plane++)for(unsigned i=0;i<sizeof buffer[0];i++)expected[plane][i]=buffer[plane][i];
    for(unsigned y=0;y<h;y++)for(unsigned x=0;x<w;x++)y_original[y][x]=buffer[0][ypos(x,y,fmt)];
    for(unsigned y=0;y<h;y++)for(unsigned x=0;x<w;x++){
        int g=0,n=0;unsigned v=luma(y_original[y][x],f.range);
        if(p.halation){
            unsigned s=0,count=0;
            for(int yy=(int)y-(int)p.radius;yy<=(int)y+(int)p.radius;yy++)
                for(int xx=(int)x-(int)p.radius;xx<=(int)x+(int)p.radius;xx++){
                    s+=mask((unsigned)clamp(xx,0,(int)w-1),(unsigned)clamp(yy,0,(int)h-1),f.range);count++;
                }
            g=clamp((int)((s+count/2)/count)-(int)mask(x,y,f.range),0,255)*p.halation/24;
        }
        glow[y][x]=(unsigned)g;
        if(p.grain){
            uint32_t a=rnd(p.seed^(x/2)*0x9e3779b9u^(y/2)*0x85ebca6bu);
            uint32_t b=rnd(p.seed^0x51ed270bu^x*0x9e3779b9u^y*0x85ebca6bu);
            int aa=(int)(a%256)+(int)((a/256)%256)-255,bb=(int)(b%256)+(int)((b/256)%256)-255;
            n=(3*aa+bb)*p.grain*(64+(int)(v<128?v:255-v))/65536;
        }
        int delta=n+g/2;if(limited)delta=delta*219/255;
        if(delta)expected[0][ypos(x,y,fmt)]=(uint8_t)clamp(y_original[y][x]+delta,limited?16:0,limited?235:255);
    }
    for(unsigned y=0;y<h;y+=fmt==1?2:1)for(unsigned x=0;x<w;x+=2){
        unsigned g=glow[y][x]+glow[y][x+1];
        if(fmt==1)g+=glow[y+1][x]+glow[y+1][x+1];g/=fmt==1?4:2;
        int cb=-(int)g*13/64,cr=(int)g*21/64;if(limited){cb=cb*224/255;cr=cr*224/255;}
        unsigned plane=fmt<3,at=fmt<3?8+(fmt==1?y/2:y)*STRIDE+x:8+y*STRIDE+2*x+(fmt==3);
        if(cb)expected[plane][at]=(uint8_t)clamp(expected[plane][at]+cb,limited?16:0,limited?240:255);
        at+=fmt<3?1:2;
        if(cr)expected[plane][at]=(uint8_t)clamp(expected[plane][at]+cr,limited?16:0,limited?240:255);
    }
}
static void exercise(unsigned w,unsigned h,unsigned fmt,unsigned range,unsigned pattern,struct a7_film_frame_params p){
    struct a7_film_frame f=frame(w,h,fmt,range);
    for(unsigned plane=0;plane<2;plane++)for(unsigned i=0;i<sizeof buffer[0];i++)buffer[plane][i]=(uint8_t)(rnd(plane*777+i)>>24);
    for(unsigned y=0;y<h;y++)for(unsigned x=0;x<w;x++){
        unsigned v=pattern==0?0:pattern==1?128:pattern==2?255:pattern==3?(x==w/2&&y==h/2?255:64):pattern==4?(x<w/2?30:245):rnd(y*w+x)>>24;
        buffer[0][ypos(x,y,fmt)]=(uint8_t)v;
    }
    oracle(f,p);for(unsigned i=0;i<sizeof work/4;i++)work[i]=0xabababab;
    size_t n=a7_film_frame_workspace(w,p.radius);
    check(!a7_film_frame_apply(&f,&p,work+1,n),"apply");
    check(work[0]==0xabababab,"workspace prefix");
    for(size_t i=n+4;i<sizeof work;i++)check(((uint8_t *)work)[i]==0xab,"workspace suffix");
    for(unsigned plane=0;plane<2;plane++)for(unsigned i=0;i<sizeof buffer[0];i++){
        check(buffer[plane][i]==expected[plane][i],"independent 2-D oracle / padding");
        checksum=(checksum^buffer[plane][i])*16777619u;
    }
    cases++;
}
static struct a7_film_frame given;
static unsigned order,acquires,releases,last_disposition,failure;
static int acquire(void *ctx,uintptr_t token,unsigned path,struct a7_film_frame *f){
    check(ctx==&given&&token==77&&path==1,"acquire arguments");acquires++;order=1;
    if(failure==1)return 1;if(failure==2)return -1;*f=given;return 0;
}
static int cpu(void *ctx,const struct a7_film_frame *f){check(ctx==&given&&f->cookie==123&&order==1,"CPU fence order");order=2;return failure==3?-1:0;}
static int device(void *ctx,const struct a7_film_frame *f){check(ctx==&given&&f->cookie==123&&order==2,"device fence order");order=3;return failure==4?-1:0;}
static int release(void *ctx,struct a7_film_frame *f,int disposition){
    check(ctx==&given&&f->cookie==123,"release lease");releases++;last_disposition=(unsigned)(disposition+1);order=4;return failure==5?-1:0;
}
static void lifecycle(void){
    struct a7_film_frame_params p={5,6,3,777};
    for(failure=0;failure<6;failure++){
        given=frame(12,8,1,1);order=acquires=releases=last_disposition=0;
        struct a7_film_frame_stage s={{acquire,cpu,device,release,&given},work,sizeof work,0,0,{0,0},0,0};
        int rc=a7_film_frame_dispatch(&s,77,1,&p);
        static const int results[6]={0,1,-2,-3,-4,-5};check(rc==results[failure],"dispatch result");
        check(acquires==1&&releases==(failure==1||failure==2?0u:1u),"balanced lease");
        if(failure==4)check(last_disposition==0&&s.fault,"quarantine unsynchronized pixels");
        if(!failure)check(last_disposition==2&&s.processed[0]==1&&!s.processed[1],"complete producer handoff");
        if(failure>=4){check(a7_film_frame_dispatch(&s,77,1,&p)==-6,"latched sync/release failure");check(acquires==1,"no reentry after fault");}
        s.lock=1;check(a7_film_frame_dispatch(&s,77,1,&p)==2,"nonblocking reentry");cases++;
    }
    failure=0;given=frame(12,8,1,1);
    struct a7_film_frame_stage s={{acquire,cpu,device,release,&given},work,sizeof work,0,0,{0,0},0,0};
    p.grain=p.halation=0;order=0;
    check(!a7_film_frame_dispatch(&s,77,1,&p)&&order==4&&!s.processed[0],"off bypass");
    given.format=99;order=0;
    check(a7_film_frame_dispatch(&s,77,1,&p)==-1&&order==4&&last_disposition==1,"unknown format released unchanged");
}
static void guards(void){
    struct a7_film_frame original=frame(12,8,1,1);struct a7_film_frame_params params={4,5,2,123};
    for(unsigned k=0;k<22;k++){
        struct a7_film_frame f=original;struct a7_film_frame_params p=params;void *ws=work;size_t n=sizeof work;
        switch(k){
        case 0:f.width=0;break;case 1:f.width=11;break;case 2:f.height=7;break;case 3:f.format=0;break;
        case 4:f.format=5;break;case 5:f.range=0;break;case 6:f.cookie=0;break;case 7:f.path=3;break;
        case 8:f.plane[0].bytes=1;break;case 9:f.plane[1].bytes=1;break;case 10:f.plane[1].data=f.plane[0].data;break;
        case 11:f.plane[0].stride=11;break;case 12:f.plane[0].data=0;break;case 13:p.grain=10;break;
        case 14:p.halation=-1;break;case 15:p.radius=0;break;case 16:p.radius=A7_FILM_FRAME_MAX_RADIUS+1;break;
        case 17:ws=buffer[0];break;case 18:ws=(uint8_t *)work+1;break;case 19:n=1;break;
        case 20:f.plane[0].data=(uint8_t *)(UINTPTR_MAX-8);break;case 21:f.format=3;break;
        }
        for(unsigned i=0;i<sizeof buffer[0];i++)buffer[0][i]=buffer[1][i]=0xa5;
        check(a7_film_frame_apply(&f,&p,ws,n)==-1,"invalid descriptor");
        for(unsigned i=0;i<sizeof buffer[0];i++)check(buffer[0][i]==0xa5&&buffer[1][i]==0xa5,"reject before writes");cases++;
    }
}
static void scales(void){
    enum { REF=576, HIGH=2*REF, H=4 };
    static uint8_t normal[REF*H*2],large[HIGH*H*2];
    static uint32_t wide_work[HIGH*38/4];
    check(a7_film_frame_reference_radius(0)==0 &&
          a7_film_frame_reference_radius(A7_FILM_FRAME_MAX_DIMENSION+1)==0,"radius width limits");
    check(a7_film_frame_reference_radius(REF)==16 &&
          a7_film_frame_reference_radius(HIGH)==32 &&
          a7_film_frame_reference_radius(6000)==167 &&
          a7_film_frame_reference_radius(A7_FILM_FRAME_MAX_DIMENSION)==A7_FILM_FRAME_MAX_RADIUS,
          "approved highlight spread scales with image width");
    for(unsigned i=0;i<sizeof normal;i++)normal[i]=128;
    for(unsigned i=0;i<sizeof large;i++)large[i]=128;
    struct a7_film_frame a={REF,H,A7_FILM_UYVY,A7_FILM_FULL,A7_FILM_PREVIEW,
        {{normal,sizeof normal,REF*2},{0,0,0}},1,1};
    struct a7_film_frame b={HIGH,H,A7_FILM_UYVY,A7_FILM_FULL,A7_FILM_CAPTURE,
        {{large,sizeof large,HIGH*2},{0,0,0}},2,2};
    struct a7_film_frame_params p={9,0,16,1987};
    check(!a7_film_frame_apply(&a,&p,wide_work,sizeof wide_work),"reference grain");
    p.radius=32;
    check(!a7_film_frame_apply(&b,&p,wide_work,sizeof wide_work),"scaled grain");
    unsigned seen=0;
    for(unsigned y=0;y<H/2;y++)for(unsigned x=0;x<REF;x++){
        unsigned ref=normal[(y*REF+x)*2+1],high=large[(2*y*HIGH+2*x)*2+1];
        check(ref==high,"grain aligns at shared sampling positions");
        seen+=ref!=128;
    }
    check(seen>0,"target grain changes luma");
    for(unsigned y=0;y<H;y++)for(unsigned x=0;x<HIGH;x++)
        large[(y*HIGH+x)*2+1]=(uint8_t)(x<HIGH/2?64:250);
    for(unsigned y=0;y<H;y++)for(unsigned x=0;x<REF;x++)
        normal[(y*REF+x)*2+1]=(uint8_t)(x<REF/2?64:250);
    p.grain=0;p.halation=9;
    check(!a7_film_frame_apply(&b,&p,wide_work,sizeof wide_work),"scaled halation");
    p.radius=16;
    check(!a7_film_frame_apply(&a,&p,wide_work,sizeof wide_work),"reference halation");
    check(normal[(REF/2-8)*2+1]>64 && large[(HIGH/2-16)*2+1]>64,
          "meaningful halo at same normalized distance");
    check(normal[(REF/2-17)*2+1]==64 && large[(HIGH/2-33)*2+1]==64,
          "halo ends at scaled radius");
    cases++;
}
#ifdef A7_FL_FILM_CONTROLS
struct stream {
    unsigned path, phase, completed;
    uintptr_t token;
    uint32_t sequence;
    int fail, disposition;
    struct a7_fl_preference *settings;
    uint8_t pixels[16*8*2];
};
static int stream_acquire(void *opaque,uintptr_t token,unsigned path,struct a7_film_frame *f){
    struct stream *s=opaque;
    check(s->phase==0&&path==s->path&&token==s->token,"separate producer/token");
    s->phase=1;
    *f=(struct a7_film_frame){16,8,A7_FILM_UYVY,A7_FILM_FULL,path,
        {{s->pixels,sizeof s->pixels,32},{0,0,0}},token,s->sequence};
    /* Deliberately change the source after entry; this frame uses its snapshot. */
    s->settings->enabled=A7_FL_PRESET_OFF;
    return 0;
}
static int stream_cpu(void *opaque,const struct a7_film_frame *f){
    struct stream *s=opaque;
    check(s->phase==1&&f->cookie==s->token,"CPU gets acquired stream");
    s->phase=2;return 0;
}
static int stream_device(void *opaque,const struct a7_film_frame *f){
    struct stream *s=opaque;
    check(s->phase==2&&f->cookie==s->token,"handoff after CPU processing");
    s->phase=3;return s->fail?-1:0;
}
static int stream_release(void *opaque,struct a7_film_frame *f,int disposition){
    struct stream *s=opaque;
    check(s->phase==(disposition?3u:1u)&&f->cookie==s->token,"release correct lease");
    s->phase=4;s->disposition=disposition;s->completed+=disposition==1;return 0;
}
static void stream_fill(uint8_t *p,size_t n){
    for(size_t i=0;i<n;i++)p[i]=(i&1)?(i%32<16?128:246):128;
}
static void dispatch_paths(void){
    struct a7_fl_preference p={0};
    p.schema=4;p.generation=2;p.film[2][0]=p.film[2][1]=9;
    struct stream preview={.path=A7_FILM_PREVIEW,.token=405,.sequence=35,.settings=&p};
    struct stream capture={.path=A7_FILM_CAPTURE,.token=730,.sequence=77,.settings=&p};
    uint32_t capture_work[64],preview_work[64];
    struct a7_film_frame_stage cv={{stream_acquire,stream_cpu,stream_device,stream_release,&capture},capture_work,sizeof capture_work,0,0,{0,0},0,0};
    struct a7_film_frame_stage pv={{stream_acquire,stream_cpu,stream_device,stream_release,&preview},preview_work,sizeof preview_work,0,0,{0,0},0,0};
    uint8_t reference[sizeof preview.pixels];
    for(unsigned path=A7_FILM_PREVIEW;path<=A7_FILM_CAPTURE;path++){
        struct stream *s=path==A7_FILM_PREVIEW?&preview:&capture;
        struct a7_film_frame_stage *stage=path==A7_FILM_PREVIEW?&pv:&cv;
        stream_fill(s->pixels,sizeof s->pixels);
        stream_fill(reference,sizeof reference);
        p.enabled=A7_FL_PRESET_LEICA;
        struct a7_film_frame_params params;
        check(!a7_film_frame_params_from_preference(&p,16,s->sequence,&params),"derive target parameters");
        struct a7_film_frame f={16,8,A7_FILM_UYVY,A7_FILM_FULL,path,
            {{reference,sizeof reference,32},{0,0,0}},s->token,s->sequence};
        check(!a7_film_frame_apply(&f,&params,work,sizeof work),"standalone target");
        check(!a7_film_frame_dispatch_preference(stage,s->token,path,&p),"process selected stream");
        check(s->phase==4&&s->completed==1&&s->disposition==1&&
              stage->processed[path-1]==1&&!stage->processed[2-path],"publish selected stream only");
        for(size_t i=0;i<sizeof reference;i++)check(s->pixels[i]==reference[i],"selected output pixels");
        cases++;
    }
    capture.phase=0;capture.fail=1;p.enabled=A7_FL_PRESET_LEICA;
    check(a7_film_frame_dispatch_preference(&cv,capture.token,capture.path,&p)==A7_FILM_FRAME_SYNC_DEVICE&&
          capture.disposition==-1&&capture.completed==1,"do not publish incoherent capture");
    preview.phase=0;stream_fill(preview.pixels,sizeof preview.pixels);stream_fill(reference,sizeof reference);
    p.enabled=A7_FL_PRESET_OFF;
    check(!a7_film_frame_dispatch_preference(&pv,preview.token,preview.path,&p)&&
          preview.disposition==0&&preview.completed==1,"capture fault does not break preview or Off");
    for(size_t i=0;i<sizeof reference;i++)check(preview.pixels[i]==reference[i],"Off keeps preview intact");
    cases+=2;
}
static void settings(void){
    struct a7_fl_preference pref={0};pref.schema=4;pref.generation=1;
    for(unsigned bank=0;bank<3;bank++){pref.film[bank][0]=(int8_t)(bank+2);pref.film[bank][1]=(int8_t)(bank+5);}
    for(int mode=0;mode<4;mode++)for(unsigned width=2;width<=6000;width+=2){
        pref.enabled=mode;struct a7_film_frame_params p={0},again={0};
        check(!a7_film_frame_params_from_preference(&pref,width,123,&p),"settings bridge");
        check(p.grain==(mode?mode+1:0)&&p.halation==(mode?mode+4:0),"independent bank and Off");
        check(p.radius==(unsigned)clamp((int)((width+18)/36),1,167),"resolution-scaled halo");
        check(!a7_film_frame_params_from_preference(&pref,width,124,&again)&&p.seed!=again.seed,"frame sequence grain");
    }
    struct a7_film_frame_params p={77,88,99,100};pref.film[2][0]=10;
    check(a7_film_frame_params_from_preference(&pref,6000,1,&p)==-1&&p.grain==77,"reject bad settings unchanged");
    pref.film[2][0]=4;pref.schema=3;
    check(a7_film_frame_params_from_preference(&pref,6000,1,&p)==-1,"explicit migration required");cases++;
}
#endif
int main(void){
    const unsigned dims[][2]={{2,2},{12,8},{24,12},{24,2},{2,12}};
    for(unsigned fmt=1;fmt<=4;fmt++)for(unsigned range=1;range<=2;range++)for(unsigned d=0;d<5;d++)
        for(unsigned pattern=0;pattern<6;pattern++)for(unsigned setting=0;setting<10;setting++)for(unsigned radius=1;radius<=16;radius*=4){
            struct a7_film_frame_params p={(int)setting,(int)(setting?10-setting:0),radius,1987};
            exercise(dims[d][0],dims[d][1],fmt,range,pattern,p);
        }
    for(unsigned fmt=1;fmt<=4;fmt++)for(unsigned strength=1;strength<=9;strength++){
        struct a7_film_frame_params p={(int)strength,0,16,78};exercise(24,12,fmt,1,5,p);
        p.grain=0;p.halation=(int)strength;exercise(24,12,fmt,2,3,p);
    }
    /* Edge replication beyond both dimensions, with values that overflow the
       old uint16 horizontal accumulator on a wide highlight. */
    exercise(2,2,A7_FILM_UYVY,A7_FILM_FULL,3,
             (struct a7_film_frame_params){9,9,A7_FILM_FRAME_MAX_RADIUS,1987});
    guards();lifecycle();scales();
#ifdef A7_FL_FILM_CONTROLS
    settings();dispatch_paths();
#endif
    put("FILM_FRAME_PASSED cases=");number(cases);put(" checks=");number(checks);put(" checksum=");number(checksum);put("\n");stop(0);return 0;
}
#ifdef A7_TEXTURE_QEMU
void guest_main(void){(void)main();}
#endif
