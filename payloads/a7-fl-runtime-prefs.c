#include "a7-fl-runtime-prefs.h"
#include "a7-fl-runtime.h"
static const uint8_t magic[8]={'A','7','F','L','P','0','0','1'};
static void word(uint8_t *p,uint32_t v) {for(unsigned i=0;i<4;i++)p[i]=(uint8_t)(v>>(i*8));}
static uint32_t read_word(const uint8_t *p) {return p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;}
static int equal(const void *a,const void *b,unsigned n) {for(unsigned i=0;i<n;i++)if(((const uint8_t *)a)[i]!=((const uint8_t *)b)[i])return 0;return 1;}
static const int low[16]={-9,-9,-9,0,-9,-3,1,0,0,-9,-9,-9,-9,-9,-9,-9};
static const int high[16]={9,9,9,9,9,3,5,9,9,9,9,9,9,9,9,9};
#ifdef A7_FL_SIX_LOOKS
static int8_t *inactive(struct a7_fl_preference *p,unsigned row) {
    return row==0?p->other_parameters:row==1?p->third_parameters:p->extra_parameters[row-2];
}
static int inactive_value(const struct a7_fl_preference *p,unsigned row,unsigned field) {
    return row==0?p->other_parameters[field]:row==1?p->third_parameters[field]:p->extra_parameters[row-2][field];
}
#endif
static int valid(const struct a7_fl_preference *p) {
    if(!p||!p->generation||!a7_fl_preset_valid(p->enabled)||(p->schema!=0&&p->schema!=2&&p->schema!=3
#ifdef A7_FL_FILM_CONTROLS
       &&!a7_fl_film_schema(p->schema)
#endif
       ))return 0;
    for(unsigned i=0;i<8;i++)if(p->parameters[i]<low[i]||p->parameters[i]>high[i])return 0;
    if(p->schema>=2)for(unsigned i=0;i<8;i++)if(p->other_parameters[i]<low[i]||p->other_parameters[i]>high[i])return 0;
    if(p->schema>=3)for(unsigned i=0;i<8;i++)if(p->third_parameters[i]<low[i]||p->third_parameters[i]>high[i])return 0;
    if(p->enabled==3&&p->schema<3)return 0;
#ifdef A7_FL_SIX_LOOKS
    if(p->schema<6&&p->enabled>=A7_FL_EXTENDED_FIRST)return 0;
    for(unsigned b=0;b<3;b++)for(unsigned i=0;i<8;i++){
        int v=p->extra_parameters[b][i];
        if(p->schema==6?(v<low[i]||v>high[i]):v!=0)return 0;
    }
#endif
#ifdef A7_FL_FILM_CONTROLS
    for(unsigned b=0;b<A7_FL_FILM_BANKS;b++)for(unsigned i=0;i<7;i++) {
        int value=p->film[b][i];
#ifdef A7_FL_CAPTURE_HALATION
        int minimum=i==0?0:-9;
#else
        int minimum=i<2?0:-9;
#endif
        if(p->schema<4||(p->schema<6&&b>=3) ? value!=0 : (value<minimum||value>9))return 0;
    }
#ifdef A7_FL_CAPTURE_VIGNETTE
    for(unsigned b=0;b<A7_FL_FILM_BANKS;b++)
        if(p->schema<5||(p->schema<6&&b>=3) ? p->vignette[b]!=0 : (p->vignette[b]<-9||p->vignette[b]>9))return 0;
#endif
#endif
    return 1;
}
#ifdef A7_FL_FILM_CONTROLS
static int bank_value(const struct a7_fl_preference *p,unsigned bank,unsigned field) {
    unsigned active=p->enabled?(unsigned)p->enabled-1:0;
#ifdef A7_FL_SIX_LOOKS
    if(field==15)return p->vignette[bank];
#endif
    if(field>=8)return p->film[bank][field-8];
    if(bank==active)return p->parameters[field];
#ifdef A7_FL_SIX_LOOKS
    return inactive_value(p,bank<active?bank:bank-1,field);
#else
    return (bank<active?bank:bank-1)==0?p->other_parameters[field]:p->third_parameters[field];
#endif
}
static void bank_set(struct a7_fl_preference *p,unsigned bank,unsigned field,int value) {
    unsigned active=p->enabled?(unsigned)p->enabled-1:0;
#ifdef A7_FL_SIX_LOOKS
    if(field==15){p->vignette[bank]=(int8_t)value;return;}
#endif
    if(field>=8)p->film[bank][field-8]=(int8_t)value;
    else if(bank==active)p->parameters[field]=value;
#ifdef A7_FL_SIX_LOOKS
    else inactive(p,bank<active?bank:bank-1)[field]=(int8_t)value;
#else
    else if((bank<active?bank:bank-1)==0)p->other_parameters[field]=(int8_t)value;
    else p->third_parameters[field]=(int8_t)value;
#endif
}
#endif
#ifdef A7_FL_SIX_LOOKS
/* Schema 6 uses byte 8 as a format marker (legacy starts with length 128).
 * Each bank is a little-endian mixed radix integer, including all 16 controls.
 * 19^11 * 10^3 * 7 * 5 fits in 62 bits. The identity and CRC stay full length.
 * The first 8 bytes and trailing CRC remain compatible with the work journal. */
enum { six_generation=9, six_mode=13, six_banks=14, six_hash=62,
       six_build=94, six_candidate=118, six_reserved=122 };
static void encode_six(uint8_t out[128],const struct a7_fl_preference *p,
                       const uint8_t hash[32],const char build[24]) {
    out[8]=6;word(out+six_generation,p->generation);out[six_mode]=(uint8_t)p->enabled;
    for(unsigned b=0;b<A7_FL_FILM_BANKS;b++){
        uint64_t code=0;
        for(unsigned f=16;f-->0;)code=code*(unsigned)(high[f]-low[f]+1)+(unsigned)(bank_value(p,b,f)-low[f]);
        for(unsigned k=0;k<8;k++)out[six_banks+b*8+k]=(uint8_t)(code>>(k*8));
    }
    for(unsigned i=0;i<32;i++)out[six_hash+i]=hash[i];
    for(unsigned i=0;i<24;i++)out[six_build+i]=(uint8_t)build[i];
    word(out+six_candidate,p->candidate_crc);
}
static int decode_six(struct a7_fl_preference *p,const uint8_t in[128],
                      const uint8_t hash[32],const char build[24]) {
    if(in[six_reserved]||in[six_reserved+1]||!a7_fl_preset_valid(in[six_mode])||
       !equal(in+six_hash,hash,32)||!equal(in+six_build,build,24)||
       read_word(in+124)!=a7_fl_crc(in,124))return -1;
    struct a7_fl_preference next;
    next.schema=6;next.generation=read_word(in+six_generation);next.enabled=in[six_mode];
    next.candidate_crc=read_word(in+six_candidate);
    for(unsigned b=0;b<A7_FL_FILM_BANKS;b++){
        uint64_t code=0;
        for(unsigned k=0;k<8;k++)code|=(uint64_t)in[six_banks+b*8+k]<<(k*8);
        for(unsigned f=0;f<16;f++){
            unsigned radix=(unsigned)(high[f]-low[f]+1);
            bank_set(&next,b,f,(int)(code%radix)+low[f]);code/=radix;
        }
        if(code)return -1;
    }
    if(!valid(&next))return -1;
    *p=next;return 0;
}
#endif
int a7_fl_preference_encode(uint8_t out[128],const struct a7_fl_preference *p,
                            const uint8_t hash[32],const char build[24]) {
    if(!out||!hash||!build||!valid(p))return -1;
    uint8_t next[128];for(unsigned i=0;i<128;i++)next[i]=0;
    for(unsigned i=0;i<8;i++)next[i]=magic[i];
#ifdef A7_FL_SIX_LOOKS
    if(p->schema==6){
        encode_six(next,p,hash,build);word(next+124,a7_fl_crc(next,124));
        for(unsigned i=0;i<128;i++)out[i]=next[i];
        return 0;
    }
#endif
    word(next+8,128);word(next+12,p->generation);word(next+16,p->schema?p->schema:1);word(next+20,(uint32_t)p->enabled);
#ifdef A7_FL_FILM_CONTROLS
    if(a7_fl_film_schema(p->schema)) {
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
#ifdef A7_FL_CAPTURE_VIGNETTE
    if(p->schema==5)for(unsigned b=0;b<3;b++)next[116+b]=(uint8_t)p->vignette[b];
#endif
    word(next+124,a7_fl_crc(next,124));
    for(unsigned i=0;i<128;i++)out[i]=next[i];
    return 0;
}
int a7_fl_preference_decode(struct a7_fl_preference *p,const uint8_t *in,unsigned n,
                            const uint8_t hash[32],const char build[24]) {
    if(!p||!in||!hash||!build||n!=128||!equal(in,magic,8))return -1;
#ifdef A7_FL_SIX_LOOKS
    if(in[8]==6)return decode_six(p,in,hash,build);
#endif
    if(read_word(in+8)!=128||
       (read_word(in+16)!=1&&read_word(in+16)!=2&&read_word(in+16)!=3
#ifdef A7_FL_FILM_CONTROLS
        &&!(a7_fl_film_schema(read_word(in+16))&&read_word(in+16)<=5)
#endif
       )||!equal(in+56,hash,32)||!equal(in+88,build,24)||
       (read_word(in+16)!=2
#ifdef A7_FL_CAPTURE_VIGNETTE
        &&read_word(in+16)!=5
#endif
        &&(read_word(in+116)||read_word(in+120)))||read_word(in+124)!=a7_fl_crc(in,124))return -1;
    struct a7_fl_preference next;next.schema=0;
#ifdef A7_FL_FILM_CONTROLS
    for(unsigned b=0;b<A7_FL_FILM_BANKS;b++)for(unsigned f=0;f<7;f++)next.film[b][f]=0;
#ifdef A7_FL_CAPTURE_VIGNETTE
    for(unsigned b=0;b<A7_FL_FILM_BANKS;b++)next.vignette[b]=0;
    if(read_word(in+16)==5){
        if(in[119]||read_word(in+120))return -1;
        for(unsigned b=0;b<3;b++)next.vignette[b]=(int8_t)in[116+b];
    }
#endif
#ifdef A7_FL_SIX_LOOKS
    for(unsigned b=0;b<3;b++)for(unsigned f=0;f<8;f++)next.extra_parameters[b][f]=0;
#endif
#endif
    for(unsigned i=0;i<8;i++)next.other_parameters[i]=next.third_parameters[i]=0;
    next.generation=read_word(in+12);next.enabled=(int)read_word(in+20);
    if(!a7_fl_preset_valid(next.enabled)||next.enabled>3)return -1;
    for(unsigned i=0;i<8;i++)next.parameters[i]=(int32_t)read_word(in+24+i*4);
    next.candidate_crc=read_word(in+112);
    if(read_word(in+16)==2){next.schema=2;for(unsigned i=0;i<8;i++)next.other_parameters[i]=(int8_t)in[116+i];}
    if(read_word(in+16)==3){
        if(read_word(in+48)||read_word(in+52))return -1;
        next.schema=3;
        for(unsigned i=0;i<8;i++){next.parameters[i]=(int8_t)in[24+i];next.other_parameters[i]=(int8_t)in[32+i];next.third_parameters[i]=(int8_t)in[40+i];}
    }
#ifdef A7_FL_FILM_CONTROLS
    if(a7_fl_film_schema(read_word(in+16))){
        if(in[52]&0xfe||in[53]||in[54]||in[55])return -1;
        next.schema=read_word(in+16);
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
    if(!p)return;
#ifdef A7_FL_SIX_LOOKS
    if(p->schema==6){
        if(!a7_fl_preset_valid(preset)||!a7_fl_preset_valid(p->enabled))return;
        unsigned active=preset?(unsigned)preset-1:0;
        int8_t banks[A7_FL_FILM_BANKS][8];
        for(unsigned b=0;b<A7_FL_FILM_BANKS;b++)
            for(unsigned f=0;f<8;f++)banks[b][f]=(int8_t)bank_value(p,b,f);
        p->enabled=preset;
        for(unsigned b=0;b<A7_FL_FILM_BANKS;b++)for(unsigned f=0;f<8;f++)
            if(b==active)p->parameters[f]=banks[b][f];else inactive(p,b<active?b:b-1)[f]=banks[b][f];
        return;
    }
#endif
    if(preset<0||preset>3||p->enabled<0||p->enabled>3)return;
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
    if(p->schema==A7_FL_FILM_SCHEMA)return 0;
    a7_fl_preference_migrate_three(p);
#ifdef A7_FL_SIX_LOOKS
    for(unsigned b=0;b<3;b++)p->extra_parameters[b][6]=3;
#endif
    p->schema=A7_FL_FILM_SCHEMA;return 1;
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
