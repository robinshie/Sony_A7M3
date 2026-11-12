#include "a7-fl-runtime-recovery.h"
#include "a7-fl-color.h"
static int same(const uint8_t *a,const uint8_t *b,unsigned n) {
    for(unsigned i=0;i<n;i++)if(a[i]!=b[i])return 0;
    return 1;
}
static int ordered(unsigned n) {return n&1?-(int)((n+1)/2):(int)(n/2);}
static int tone_matches(const uint8_t *table,const uint8_t *base,const A7FLColorParams *p) {
    if(!p->contrast&&!p->highlights&&!p->shadows&&!p->fade)return same(table,base,405);
    for(int b=0;b<9;b++)for(int c=0;c<9;c++) {
        int previous=0;
        for(int a=0;a<5;a++) {
            unsigned i=(unsigned)(a*81+b*9+c);
            int y=a7_fl_clamp(a*64+a7_fl_signed(base[i]),0,256);
            int lift=(p->highlights*y*y+p->shadows*(256-y)*(256-y))*6/65536;
            int adjusted=128+(y-128)*(256+p->contrast*14)/256+lift;
            adjusted=adjusted*(256-p->fade*5)/256+p->fade*4;
            adjusted=a7_fl_clamp(adjusted,0,256);
            int value=a7_fl_clamp(adjusted-a*64,-64,63);
            y=a7_fl_clamp(a*64+value,previous,256);previous=y;
            if(table[i]!=(uint8_t)(y-a*64))return 0;
        }
    }
    return 1;
}
int a7_fl_recognize(const uint8_t table[1280],const uint8_t base[1280],
                    const uint16_t expand[129],const uint8_t compress[513],
                    int out[5],unsigned *trials) {
    if(!table||!base||!expand||!compress||!out)return A7_FL_ARGUMENT;
    if(trials)*trials=0;
    if(!same(table+1215,base+1215,65))return 0;
    uint8_t generated[1280];A7FLColorParams p;int saturation=99;
    p.contrast=p.highlights=p.shadows=p.fade=p.saturation=0;
    for(unsigned s=0;s<19;s++) {
        p.saturation=ordered(s);
        if(a7_fl_adjust_lut(base,1280,expand,compress,&p,generated,1280))return A7_FL_TABLE;
        if(same(table+405,generated+405,810)) {saturation=p.saturation;break;}
    }
    if(saturation==99)return 0;
    p.saturation=saturation;
    for(unsigned contrast=0;contrast<19;contrast++)for(unsigned high=0;high<19;high++)
    for(unsigned shadow=0;shadow<19;shadow++)for(int fade=0;fade<10;fade++) {
        p.contrast=ordered(contrast);p.highlights=ordered(high);p.shadows=ordered(shadow);p.fade=fade;
        if(trials)(*trials)++;
        if(!tone_matches(table,base,&p))continue;
        /* The search shortcut is never itself authorization. Regenerate and
         * compare all bytes with the authoritative current color implementation. */
        if(a7_fl_adjust_lut(base,1280,expand,compress,&p,generated,1280) || !same(table,generated,1280))continue;
        out[0]=p.contrast;out[1]=p.highlights;out[2]=p.shadows;out[3]=p.fade;out[4]=p.saturation;return 1;
    }
    return 0;
}
static int other_tables(const struct a7_fl_recovery *r,uint8_t scratch[1280]) {
    for(unsigned i=1;i<4;i++) {
        uint32_t id=A7_FL_PROPERTY+i;
        if(r->api->size(id)!=1280||r->api->attr(id)!=8||r->api->read(id,scratch)!=1280||
           (!same(scratch,r->original[i],1280) &&
            !(i<=2 && r->capture_alternate[i-1] && same(scratch,r->capture_alternate[i-1],1280))))
            return A7_FL_RECOVERY_OTHER_TABLE;
    }
    return 0;
}
int a7_fl_restore_baseline(const struct a7_fl_recovery *r,int parameters[5]) {
    if(!r||!parameters||!r->api||!r->api->size||!r->api->attr||!r->api->read||!r->api->write||
       !r->identity_guard||!r->base_fl||!r->expand||!r->compress)return A7_FL_ARGUMENT;
    if(r->identity_guard(r->identity_context)!=1)return A7_FL_RECOVERY_IDENTITY;
    for(unsigned i=0;i<4;i++)if(!r->original[i]||a7_fl_crc(r->original[i],1280)!=r->original_crc[i])return A7_FL_TABLE;
    if(a7_fl_crc(r->base_fl,1280)!=r->base_fl_crc || !same(r->base_fl+1215,r->original[0]+1215,65))return A7_FL_TABLE;
    uint8_t current[1280],scratch[1280];
    if(r->api->size(A7_FL_PROPERTY)!=1280||r->api->attr(A7_FL_PROPERTY)!=8)return A7_FL_LAYOUT;
    if(r->api->read(A7_FL_PROPERTY,current)!=1280)return A7_FL_READ;
    int rc=other_tables(r,scratch);if(rc)return rc;
    if(same(current,r->original[0],1280))return 0;
    if(a7_fl_recognize(current,r->base_fl,r->expand,r->compress,parameters,0)!=1)return A7_FL_RECOVERY_UNRECOGNIZED;
    if(r->identity_guard(r->identity_context)!=1)return A7_FL_RECOVERY_IDENTITY;
    rc=other_tables(r,scratch);if(rc)return rc;
    if(r->api->read(A7_FL_PROPERTY,scratch)!=1280||!same(current,scratch,1280))return A7_FL_FOREIGN;
    /* A failing acknowledgement can follow an accepted write. At most one
     * second restoration is permitted; every attempt is independently read. */
    for(unsigned attempt=0;attempt<2;attempt++) {
        int written=r->api->write(3,A7_FL_PROPERTY,r->original[0]);
        int read=r->api->read(A7_FL_PROPERTY,scratch);
        if(written==1280&&read==1280&&same(scratch,r->original[0],1280))return 1;
    }
    return A7_FL_RECOVERY;
}
