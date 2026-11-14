#include "a7-fl-runtime-prefs.h"
#include "a7-fl-runtime.h"
static const uint8_t magic[8]={'A','7','F','L','P','0','0','1'};
static void word(uint8_t *p,uint32_t v) {for(unsigned i=0;i<4;i++)p[i]=(uint8_t)(v>>(i*8));}
static uint32_t read_word(const uint8_t *p) {return p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;}
static int equal(const void *a,const void *b,unsigned n) {for(unsigned i=0;i<n;i++)if(((const uint8_t *)a)[i]!=((const uint8_t *)b)[i])return 0;return 1;}
static int valid(const struct a7_fl_preference *p) {
    static const int low[8]={-9,-9,-9,0,-9,-3,1,0},high[8]={9,9,9,9,9,3,5,9};
    if(!p||!p->generation||!a7_fl_preset_valid(p->enabled)||(p->schema!=0&&p->schema!=2&&p->schema!=3
#ifdef A7_FL_FILM_CONTROLS
       &&p->schema!=4
#endif
       ))return 0;
    for(unsigned i=0;i<8;i++)if(p->parameters[i]<low[i]||p->parameters[i]>high[i])return 0;
    if(p->schema>=2)for(unsigned i=0;i<8;i++)if(p->other_parameters[i]<low[i]||p->other_parameters[i]>high[i])return 0;
    if(p->schema>=3)for(unsigned i=0;i<8;i++)if(p->third_parameters[i]<low[i]||p->third_parameters[i]>high[i])return 0;
    if(p->enabled==3&&p->schema<3)return 0;
#ifdef A7_FL_FILM_CONTROLS
    for(unsigned b=0;b<3;b++)for(unsigned i=0;i<7;i++) {
        int value=p->film[b][i];
        if(p->schema<4?value!=0:(value<(i<2?0:-9)||value>9))return 0;
    }
#endif
    return 1;
}
#ifdef A7_FL_FILM_CONTROLS
static int bank_value(const struct a7_fl_preference *p,unsigned bank,unsigned field) {
    unsigned active=p->enabled?(unsigned)p->enabled-1:0;
    if(field>=8)return p->film[bank][field-8];
    if(bank==active)return p->parameters[field];
    return (bank<active?bank:bank-1)==0?p->other_parameters[field]:p->third_parameters[field];
}
static void bank_set(struct a7_fl_preference *p,unsigned bank,unsigned field,int value) {
    unsigned active=p->enabled?(unsigned)p->enabled-1:0;
    if(field>=8)p->film[bank][field-8]=(int8_t)value;
    else if(bank==active)p->parameters[field]=value;
    else if((bank<active?bank:bank-1)==0)p->other_parameters[field]=(int8_t)value;
    else p->third_parameters[field]=(int8_t)value;
}
#endif
int a7_fl_preference_encode(uint8_t out[128],const struct a7_fl_preference *p,
                            const uint8_t hash[32],const char build[24]) {
    if(!out||!hash||!build||!valid(p))return -1;
    uint8_t next[128];for(unsigned i=0;i<128;i++)next[i]=0;
    for(unsigned i=0;i<8;i++)next[i]=magic[i];
    word(next+8,128);word(next+12,p->generation);word(next+16,p->schema?p->schema:1);word(next+20,(uint32_t)p->enabled);
#ifdef A7_FL_FILM_CONTROLS
    if(p->schema==4) {
        /* 3 * 15 * 5 = 225 bits. Leave all seven high bits and reserved bytes zero. */
        for(unsigned b=0;b<3;b++)for(unsigned f=0;f<15;f++) {
            unsigned v=(unsigned)bank_value(p,b,f)&31u,bit=(b*15+f)*5;
            for(unsigned k=0;k<5;k++)next[24+(bit+k)/8]|=(uint8_t)(((v>>k)&1u)<<((bit+k)%8));
        }
    } else
#endif
    if(p->schema==3)for(unsigned i=0;i<8;i++) {
        next[24+i]=(uint8_t)p->parameters[i];next[32+i]=(uint8_t)p->other_parameters[i];next[40+i]=(uint8_t)p->third_parameters[i];
    } else for(unsigned i=0;i<8;i++)word(next+24+i*4,(uint32_t)p->parameters[i]);
    for(unsigned i=0;i<32;i++)next[56+i]=hash[i];
    for(unsigned i=0;i<24;i++)next[88+i]=(uint8_t)build[i];
    word(next+112,p->candidate_crc);
    if(p->schema==2)for(unsigned i=0;i<8;i++)next[116+i]=(uint8_t)p->other_parameters[i];
    word(next+124,a7_fl_crc(next,124));
    for(unsigned i=0;i<128;i++)out[i]=next[i];
    return 0;
}
int a7_fl_preference_decode(struct a7_fl_preference *p,const uint8_t *in,unsigned n,
                            const uint8_t hash[32],const char build[24]) {
    if(!p||!in||!hash||!build||n!=128||!equal(in,magic,8)||read_word(in+8)!=128||
       (read_word(in+16)!=1&&read_word(in+16)!=2&&read_word(in+16)!=3
#ifdef A7_FL_FILM_CONTROLS
        &&read_word(in+16)!=4
#endif
       )||!equal(in+56,hash,32)||!equal(in+88,build,24)||
       (read_word(in+16)!=2&&(read_word(in+116)||read_word(in+120)))||read_word(in+124)!=a7_fl_crc(in,124))return -1;
    struct a7_fl_preference next;next.schema=0;
#ifdef A7_FL_FILM_CONTROLS
    for(unsigned b=0;b<3;b++)for(unsigned f=0;f<7;f++)next.film[b][f]=0;
#endif
    for(unsigned i=0;i<8;i++)next.other_parameters[i]=next.third_parameters[i]=0;
    next.generation=read_word(in+12);next.enabled=(int)read_word(in+20);
    for(unsigned i=0;i<8;i++)next.parameters[i]=(int32_t)read_word(in+24+i*4);
    next.candidate_crc=read_word(in+112);
    if(read_word(in+16)==2){next.schema=2;for(unsigned i=0;i<8;i++)next.other_parameters[i]=(int8_t)in[116+i];}
    if(read_word(in+16)==3){
        if(read_word(in+48)||read_word(in+52))return -1;
        next.schema=3;
        for(unsigned i=0;i<8;i++){next.parameters[i]=(int8_t)in[24+i];next.other_parameters[i]=(int8_t)in[32+i];next.third_parameters[i]=(int8_t)in[40+i];}
    }
#ifdef A7_FL_FILM_CONTROLS
    if(read_word(in+16)==4){
        if(in[52]&0xfe||in[53]||in[54]||in[55])return -1;
        next.schema=4;
        for(unsigned b=0;b<3;b++)for(unsigned f=0;f<15;f++){
            unsigned bit=(b*15+f)*5,v=0;
            for(unsigned k=0;k<5;k++)v|=((unsigned)(in[24+(bit+k)/8]>>((bit+k)%8))&1u)<<k;
            bank_set(&next,b,f,v&16?(int)v-32:(int)v);
        }
    }
#endif
    if(!valid(&next))return -1;
    *p=next;return 0;
}
void a7_fl_preference_switch(struct a7_fl_preference *p,int preset) {
    if(p->schema>=3) {
        int from=p->enabled?p->enabled-1:0,to=preset?preset-1:0;
        if(from!=to){
            int8_t bank[3][8];
            for(int b=0;b<3;b++)for(unsigned i=0;i<8;i++)bank[b][i]=(int8_t)(b==from?p->parameters[i]:(b<from?b:b-1)==0?p->other_parameters[i]:p->third_parameters[i]);
            for(unsigned i=0;i<8;i++)p->parameters[i]=bank[to][i];
            unsigned n=0;for(int b=0;b<3;b++)if(b!=to){for(unsigned i=0;i<8;i++)(n==0?p->other_parameters:p->third_parameters)[i]=bank[b][i];n++;}
        }
    }
    if(p->schema==2 && ((p->enabled==2)!=(preset==2))) {
        for(unsigned i=0;i<8;i++){int v=p->parameters[i];p->parameters[i]=p->other_parameters[i];p->other_parameters[i]=v;}
    }
    p->enabled=preset;
}
int a7_fl_preference_migrate(struct a7_fl_preference *p) {
    if(p->schema>=2)return 0;
    p->schema=2;
    for(unsigned i=0;i<8;i++) {
        int initial=i==6?3:0;
        p->other_parameters[i]=p->enabled==2?p->parameters[i]:initial;
        if(p->enabled==2)p->parameters[i]=initial;
    }
    return 1;
}
int a7_fl_preference_migrate_three(struct a7_fl_preference *p) {
    if(p->schema>=3)return 0;
    a7_fl_preference_migrate(p);
    for(unsigned i=0;i<8;i++)p->third_parameters[i]=(int8_t)(i==6?3:0);
    p->schema=3;return 1;
}
#ifdef A7_FL_FILM_CONTROLS
int a7_fl_preference_migrate_film(struct a7_fl_preference *p) {
    if(!p||!valid(p))return -1;
    if(p->schema==4)return 0;
    a7_fl_preference_migrate_three(p);
    p->schema=4;return 1;
}
#endif
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
