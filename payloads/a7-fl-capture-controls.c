#include "a7-fl-capture-controls.h"
#include "a7-fl-runtime-prefs.h"
#ifdef A7_FL_FILM_CONTROLS
#include "a7-fl-fivepoint.h"
#endif
#ifdef A7_FL_DUAL_LOOK
#include "a7-fl-cinema.h"
#ifdef A7_FL_LEICA_LOOK
#include "a7-fl-leica.h"
#endif
#endif
static int equal(const uint8_t *a,const uint8_t *b,unsigned n) {
    for(unsigned i=0;i<n;i++)if(a[i]!=b[i])return 0;
    return 1;
}
static void copy(uint8_t *a,const uint8_t *b,unsigned n) {for(unsigned i=0;i<n;i++)a[i]=b[i];}
static int decode(unsigned v) {v&=127;return v<64?(int)v:(int)v-128;}
static uint8_t encode(int v,unsigned table) {return table?(uint8_t)(v&127):(uint8_t)v;}
static int packed(unsigned v,unsigned level) {
    int raw=a7_fl_signed((uint8_t)v);
    if(level<8)raw=a7_fl_floor_div(raw*(int)level,8);
    return decode((unsigned)raw);
}
static int allowed(unsigned stock,int candidate,unsigned table,unsigned limit) {
    if(candidate< -64||candidate>63)return 0;
    for(unsigned level=1;level<=8;level++) {
        int delta=packed(encode(candidate,table),level)-packed(stock,level);
        if(delta< -(int)limit||delta>(int)limit)return 0;
    }
    return 1;
}
int a7_capture_prepare(struct a7_capture_controls *c,const struct a7_fl_api *api,
                       const uint8_t *const stock[2],const uint8_t *const legacy[2],
                       const uint16_t *expand,const uint8_t *compress) {
    if(!c||c->prepared||!api||!api->size||!api->attr||!api->read||!api->write||
       !stock||!legacy||!stock[0]||!stock[1]||!legacy[0]||!legacy[1]||!expand||!compress)return A7_FL_ARGUMENT;
    c->api=*api;c->expand=expand;c->compress=compress;
    for(unsigned t=0;t<2;t++) {
        c->stock[t]=stock[t];c->legacy[t]=legacy[t];
        if(!equal(stock[t]+1215,legacy[t]+1215,65))return A7_FL_TABLE;
        copy(c->base[t],stock[t],1280);
        for(unsigned i=0;i<1215;i++) {
            if(t?(stock[t][i]>=128||legacy[t][i]>=128):
                 (a7_fl_signed(stock[t][i])!=decode(stock[t][i])||a7_fl_signed(legacy[t][i])!=decode(legacy[t][i])))return A7_FL_TABLE;
            /* Reject a malformed historical package; its old bounds are 8/12. */
            if(!allowed(stock[t][i],decode(legacy[t][i]),t,i<405?8:12))return A7_FL_TABLE;
            int original=decode(stock[t][i]),lo=original,hi=original;
            unsigned limit=i<405?24:32;
            while(allowed(stock[t][i],lo-1,t,limit))lo--;
            while(allowed(stock[t][i],hi+1,t,limit))hi++;
            c->low[t][i]=(int8_t)lo;c->high[t][i]=(int8_t)hi;
            int stronger=original+a7_fl_round_div((decode(legacy[t][i])-original)*3,2);
            c->base[t][i]=(uint8_t)a7_fl_clamp(stronger,lo,hi);
        }
        uint8_t scratch[1280];A7FLColorParams zero={0,0,0,0,0};
        if(a7_fl_adjust_lut(c->base[t],1280,expand,compress,&zero,scratch,1280))return A7_FL_TABLE;
#ifdef A7_FL_DUAL_LOOK
        for(unsigned i=0;i<1215;i++)scratch[i]=(uint8_t)decode(stock[t][i]);
        if(a7_cinema_base(scratch,expand,compress,c->cinema[t]))return A7_FL_TABLE;
#ifdef A7_FL_LEICA_LOOK
        if(a7_leica_base(scratch,expand,compress,c->leica[t]))return A7_FL_TABLE;
#endif
#endif
    }
    c->prepared=1;return 0;
}
static const uint8_t *preset_base(const struct a7_capture_controls *c,unsigned t,int preset) {
#ifdef A7_FL_DUAL_LOOK
    if(preset==A7_FL_PRESET_CINEMA)return c->cinema[t];
#ifdef A7_FL_LEICA_LOOK
    if(preset==A7_FL_PRESET_LEICA)return c->leica[t];
#endif
#else
    (void)preset;
#endif
    return c->base[t];
}
static int generate_with_curve(const struct a7_capture_controls *c,unsigned t,int preset,
                        const A7FLColorParams *p,const int *curve,uint8_t out[1280]) {
    if(!c||!c->prepared||t>1||!out||!a7_fl_params_valid(p))return A7_FL_ARGUMENT;
    uint8_t next[1280];
    if(a7_fl_adjust_lut(preset_base(c,t,preset),1280,c->expand,c->compress,p,next,1280))return A7_FL_TABLE;
    for(unsigned i=0;i<1215;i++)next[i]=encode(a7_fl_clamp(a7_fl_signed(next[i]),c->low[t][i],c->high[t][i]),t);
#ifdef A7_FL_FILM_CONTROLS
    if(curve&&a7_fl_fivepoint_lut(next,1280,next,1280,t,curve,c->low[t],c->high[t]))return A7_FL_TABLE;
#else
    (void)curve;
#endif
    copy(out,next,1280);return 0;
}
static int generate(const struct a7_capture_controls *c,unsigned t,int preset,
                    const A7FLColorParams *p,uint8_t out[1280]) {
    return generate_with_curve(c,t,preset,p,0,out);
}
#ifdef A7_FL_FILM_CONTROLS
int a7_capture_generate_curve(const struct a7_capture_controls *c,unsigned t,int preset,
                const A7FLColorParams *p,const int curve[5],uint8_t out[1280]) {
    if(preset<A7_FL_PRESET_FL||!a7_fl_preset_valid(preset)||!curve)return A7_FL_ARGUMENT;
    return generate_with_curve(c,t,preset,p,curve,out);
}
#endif
int a7_capture_generate(const struct a7_capture_controls *c,unsigned t,
                        const A7FLColorParams *p,uint8_t out[1280]) {
    return generate(c,t,A7_FL_PRESET_FL,p,out);
}
#ifdef A7_FL_DUAL_LOOK
int a7_capture_generate_preset(const struct a7_capture_controls *c,unsigned t,int preset,
                               const A7FLColorParams *p,uint8_t out[1280]) {
    if(preset<A7_FL_PRESET_FL||!a7_fl_preset_valid(preset))return A7_FL_ARGUMENT;
    return generate(c,t,preset,p,out);
}
#endif
/* Fast exact tone comparison; final full generation is always required. */
static int tone_equal(const struct a7_capture_controls *c,unsigned t,int preset,const uint8_t *table,const A7FLColorParams *p) {
    const uint8_t *base=preset_base(c,t,preset);
    if(!p->contrast&&!p->highlights&&!p->shadows&&!p->fade) {
        for(unsigned i=0;i<405;i++)if(table[i]!=encode(a7_fl_clamp(a7_fl_signed(base[i]),c->low[t][i],c->high[t][i]),t))return 0;
        return 1;
    }
    for(int b=0;b<9;b++)for(int d=0;d<9;d++) {
        int previous=0;
        for(int a=0;a<5;a++) {
            unsigned i=(unsigned)(a*81+b*9+d);
            int y=a7_fl_clamp(a*64+a7_fl_signed(base[i]),0,256);
            int lift=(p->highlights*y*y+p->shadows*(256-y)*(256-y))*6/65536;
            int adjusted=128+(y-128)*(256+p->contrast*14)/256+lift;
            adjusted=adjusted*(256-p->fade*5)/256+p->fade*4;
            int value=a7_fl_clamp(a7_fl_clamp(adjusted,0,256)-a*64,-64,63);
            y=a7_fl_clamp(a*64+value,previous,256);previous=y;
            value=a7_fl_clamp(y-a*64,c->low[t][i],c->high[t][i]);
            if(table[i]!=encode(value,t))return 0;
        }
    }
    return 1;
}
static int ordered(unsigned n) {return n&1?-(int)((n+1)/2):(int)(n/2);}
static int recognize(const struct a7_capture_controls *c,unsigned t,int preset,const uint8_t table[1280]) {
    if(!c||!c->prepared||t>1||!table)return A7_FL_ARGUMENT;
    if(!equal(table+1215,c->stock[t]+1215,65))return 0;
    uint8_t generated[1280];A7FLColorParams p={0,0,0,0,0};int saturation=99;
    for(unsigned s=0;s<19;s++) {
        p.saturation=ordered(s);
        if(generate(c,t,preset,&p,generated))return A7_FL_TABLE;
        if(equal(table+405,generated+405,810)){saturation=p.saturation;break;}
    }
    if(saturation==99)return 0;
    p.saturation=saturation;
    for(unsigned a=0;a<19;a++)for(unsigned b=0;b<19;b++)for(unsigned d=0;d<19;d++)for(int f=0;f<10;f++) {
        p.contrast=ordered(a);p.highlights=ordered(b);p.shadows=ordered(d);p.fade=f;
        if(tone_equal(c,t,preset,table,&p)&&!generate(c,t,preset,&p,generated)&&equal(table,generated,1280))return 1;
    }
    return 0;
}
int a7_capture_recognize(const struct a7_capture_controls *c,unsigned t,const uint8_t table[1280]) {
    int rc=recognize(c,t,A7_FL_PRESET_FL,table);
#ifdef A7_FL_DUAL_LOOK
    if(!rc)rc=recognize(c,t,A7_FL_PRESET_CINEMA,table);
#endif
#ifdef A7_FL_LEICA_LOOK
    if(!rc)rc=recognize(c,t,A7_FL_PRESET_LEICA,table);
#endif
    return rc;
}
static int read_table(const struct a7_capture_controls *c,unsigned t,uint8_t *out) {
    uint32_t id=A7_FL_PROPERTY+1+t;
    if(c->api.size(id)!=1280||c->api.attr(id)!=8)return A7_FL_LAYOUT;
    return c->api.read(id,out)==1280?0:A7_FL_READ;
}
static int unchanged(const struct a7_capture_controls *c) {
    uint8_t scratch[1280];
    for(unsigned t=0;t<2;t++) {
        int rc=read_table(c,t,scratch);if(rc)return rc;
        if(!equal(scratch,c->current[t],1280))return A7_FL_FOREIGN;
    }
    return 0;
}
int a7_capture_adopt(struct a7_capture_controls *c,const A7FLColorParams *saved) {
    if(!c||!c->prepared||c->initialized||!a7_fl_params_valid(saved))return A7_FL_ARGUMENT;
    uint8_t expected[1280];
    for(unsigned t=0;t<2;t++) {
        int rc=read_table(c,t,c->current[t]);if(rc)return rc;
        if(equal(c->current[t],c->stock[t],1280)||equal(c->current[t],c->legacy[t],1280))continue;
        if(a7_capture_generate(c,t,saved,expected))return A7_FL_TABLE;
        if(!equal(c->current[t],expected,1280)&&a7_capture_recognize(c,t,c->current[t])!=1)return A7_FL_FOREIGN;
    }
    int rc=unchanged(c);if(rc)return rc;
    c->initialized=1;return 0;
}
int a7_capture_verify(const struct a7_capture_controls *c,int mode,const A7FLColorParams *p) {
    if(!c||!c->initialized||!a7_fl_preset_valid(mode)||!a7_fl_params_valid(p))return A7_FL_ARGUMENT;
    uint8_t expected[1280];
    for(unsigned t=0;t<2;t++) {
        if(mode) {if(generate(c,t,mode,p,expected))return A7_FL_TABLE;}
        else copy(expected,c->stock[t],1280);
        if(!equal(c->current[t],expected,1280))return A7_FL_VERIFY;
    }
    return unchanged(c);
}
static int apply_with_curve(struct a7_capture_controls *c,int mode,const A7FLColorParams *p,
                            const int *curve) {
    if(!c||!c->initialized||!a7_fl_preset_valid(mode)||!a7_fl_params_valid(p))return A7_FL_ARGUMENT;
    uint8_t next[2][1280],scratch[1280];unsigned attempted=0;int rc;
    for(unsigned t=0;t<2;t++) {
        if(mode) {if(generate_with_curve(c,t,mode,p,curve,next[t]))return A7_FL_TABLE;}
        else copy(next[t],c->stock[t],1280);
    }
    rc=unchanged(c);if(rc)return rc;
    for(unsigned t=0;t<2;t++) {
        if(equal(c->current[t],next[t],1280))continue;
        for(unsigned j=0;j<2;j++) {
            rc=read_table(c,j,scratch);if(rc)goto failed;
            if(!equal(scratch,(attempted&(1u<<j))?next[j]:c->current[j],1280)){rc=A7_FL_FOREIGN;goto failed;}
        }
        attempted|=1u<<t;
        int result=c->api.write(3,A7_FL_PROPERTY+1+t,next[t]);
        rc=read_table(c,t,scratch);if(rc)goto failed;
        if(result!=1280){rc=A7_FL_WRITE;goto failed;}
        if(!equal(scratch,next[t],1280)){rc=A7_FL_VERIFY;goto failed;}
    }
    for(unsigned t=0;t<2;t++) {
        rc=read_table(c,t,scratch);if(rc)goto failed;
        if(!equal(scratch,next[t],1280)){rc=A7_FL_VERIFY;goto failed;}
    }
    for(unsigned t=0;t<2;t++)copy(c->current[t],next[t],1280);
    return 0;
failed:
    for(unsigned n=2;n>0;n--) {
        unsigned t=n-1;
        if((attempted&(1u<<t))&&!read_table(c,t,scratch)&&equal(scratch,next[t],1280)&&!equal(scratch,c->current[t],1280))
            (void)c->api.write(3,A7_FL_PROPERTY+1+t,c->current[t]);
    }
    return unchanged(c)?A7_FL_RECOVERY:rc;
}
int a7_capture_apply(struct a7_capture_controls *c,int mode,const A7FLColorParams *p) {
    return apply_with_curve(c,mode,p,0);
}
#ifdef A7_FL_FILM_CONTROLS
int a7_capture_apply_curve(struct a7_capture_controls *c,int mode,const A7FLColorParams *p,
                          const int curve[5]) {
    if(mode!=A7_FL_PRESET_LEICA||!curve)return A7_FL_ARGUMENT;
    return apply_with_curve(c,mode,p,curve);
}
#endif
