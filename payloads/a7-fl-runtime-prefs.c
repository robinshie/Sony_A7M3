#include "a7-fl-runtime-prefs.h"
#include "a7-fl-runtime.h"
static const uint8_t magic[8]={'A','7','F','L','P','0','0','1'};
static void word(uint8_t *p,uint32_t v) {for(unsigned i=0;i<4;i++)p[i]=(uint8_t)(v>>(i*8));}
static uint32_t read_word(const uint8_t *p) {return p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;}
static int equal(const void *a,const void *b,unsigned n) {for(unsigned i=0;i<n;i++)if(((const uint8_t *)a)[i]!=((const uint8_t *)b)[i])return 0;return 1;}
static int valid(const struct a7_fl_preference *p) {
    static const int low[8]={-9,-9,-9,0,-9,-3,1,0},high[8]={9,9,9,9,9,3,5,9};
    if(!p||!p->generation||(p->enabled!=0&&p->enabled!=1))return 0;
    for(unsigned i=0;i<8;i++)if(p->parameters[i]<low[i]||p->parameters[i]>high[i])return 0;
    return 1;
}
int a7_fl_preference_encode(uint8_t out[128],const struct a7_fl_preference *p,
                            const uint8_t hash[32],const char build[24]) {
    if(!out||!hash||!build||!valid(p))return -1;
    uint8_t next[128];for(unsigned i=0;i<128;i++)next[i]=0;
    for(unsigned i=0;i<8;i++)next[i]=magic[i];
    word(next+8,128);word(next+12,p->generation);word(next+16,1);word(next+20,(uint32_t)p->enabled);
    for(unsigned i=0;i<8;i++)word(next+24+i*4,(uint32_t)p->parameters[i]);
    for(unsigned i=0;i<32;i++)next[56+i]=hash[i];
    for(unsigned i=0;i<24;i++)next[88+i]=(uint8_t)build[i];
    word(next+112,p->candidate_crc);word(next+124,a7_fl_crc(next,124));
    for(unsigned i=0;i<128;i++)out[i]=next[i];
    return 0;
}
int a7_fl_preference_decode(struct a7_fl_preference *p,const uint8_t *in,unsigned n,
                            const uint8_t hash[32],const char build[24]) {
    if(!p||!in||!hash||!build||n!=128||!equal(in,magic,8)||read_word(in+8)!=128||
       read_word(in+16)!=1||!equal(in+56,hash,32)||!equal(in+88,build,24)||
       read_word(in+116)||read_word(in+120)||read_word(in+124)!=a7_fl_crc(in,124))return -1;
    struct a7_fl_preference next;
    next.generation=read_word(in+12);next.enabled=(int)read_word(in+20);
    for(unsigned i=0;i<8;i++)next.parameters[i]=(int32_t)read_word(in+24+i*4);
    next.candidate_crc=read_word(in+112);
    if(!valid(&next))return -1;
    *p=next;return 0;
}
int a7_fl_preference_choose(struct a7_fl_preference *out,const uint8_t *a,unsigned an,
                            const uint8_t *b,unsigned bn,const uint8_t hash[32],const char build[24]) {
    struct a7_fl_preference x,y;
    if(!out)return -1;
    int ax=a7_fl_preference_decode(&x,a,an,hash,build)==0;
    int by=a7_fl_preference_decode(&y,b,bn,hash,build)==0;
    if(!ax&&!by)return -1;
    if(ax&&by&&x.generation==y.generation&&!equal(a,b,128))return -2;
    if(ax&&(!by||x.generation>=y.generation)) {*out=x;return 0;}
    *out=y;return 1;
}
