/* Execute original AV-CAM LUT routines in isolated QEMU RAM. No Sony ISP. */
#include <stdint.h>
#define BASE 0x635c6000u
#define FN(off, type) ((type)(uintptr_t)(BASE+(off)+1))
#define GUARD 0xa5a5a5a5u
static unsigned pack_cases, table_cases, selector_cases, bank_calls, coordinate_cases;
static uint32_t mock_registers[0x18000/4];
static const unsigned starts[8]={0,75,135,195,243,293,333,373};
static const unsigned counts[8]={75,60,60,48,50,40,40,32};
static const unsigned offsets[8]={0x17000,0x17200,0x17300,0x17400,
                                  0x17500,0x17600,0x17700,0x17800};
static const uint32_t *write_source;
static void put(const char *s) {
    volatile unsigned *uart=(volatile unsigned *)0x09000000;
    while (*s) { while(uart[6]&32) {} uart[0]=*s++; }
}
static void finish(void) {
    register unsigned r0 __asm__("r0")=0x18;
    register unsigned r1 __asm__("r1")=0x20026;
    __asm__ volatile("svc 0xab" : "+r"(r0), "+r"(r1) : : "memory");
    while(1) {}
}
static void check(int ok,const char *s) {
    if(!ok) { put("FAIL ");put(s);put("\n");finish(); }
}
void native_log(void) { check(0,"unexpected logging path"); }
void *native_set(void *dst,int value,unsigned size) {
    unsigned char *p=dst;
    for(unsigned i=0;i<size;i++) p[i]=(unsigned char)value;
    return dst;
}
/* libc memcpy is the only replacement in the register-write call chain. */
void *native_copy(void *dst,const void *src,unsigned size) {
    unsigned i=bank_calls;
    check(i<8,"bank count");
    check(dst==(unsigned char *)mock_registers+offsets[i],"bank destination");
    check(src==write_source+starts[i] && size==counts[i]*4,"bank source and length");
    check(mock_registers[0x15d40/4]==1,"write gate enabled before each copy");
    bank_calls++;
    unsigned char *d=dst;const unsigned char *s=src;
    for(unsigned j=0;j<size;j++) d[j]=s[j];
    return dst;
}
static unsigned index_of(unsigned a,unsigned b,unsigned c) {
    unsigned bank=(a%2)*4+(b%2)*2+c%2;
    return starts[bank]+((a/2)*(5-b%2)+b/2)*(5-c%2)+c/2;
}
static uint32_t word(int a,int b,int c) {
    return ((a&127)<<16)|((b&127)<<8)|(c&127);
}
static void coordinate_test(void) {
    const uint16_t *expand=(const uint16_t *)(BASE+0x8a999e);
    const unsigned char *compress=(const unsigned char *)(BASE+0x9b5921);
    for(int input=-2048;input<=2048;input++) {
        unsigned magnitude=(unsigned)(input<0?-input:input);
        int expected_expand=expand[magnitude>128?128:magnitude];
        int expected_compress=compress[magnitude>512?512:magnitude];
        if(input<0) {expected_expand=-expected_expand;expected_compress=-expected_compress;}
        check(FN(0x522d68,int (*)(int))(input)==expected_expand,"native chroma expansion");
        check(FN(0x522d2c,int (*)(int))(input)==expected_compress,"native chroma compression");
        coordinate_cases+=2;
    }
}
static void pack_test(void) {
    static uint32_t out[407];
    const uint16_t *permutation=(const uint16_t *)(BASE+0x8a9658);
    for(unsigned a=0;a<5;a++) for(unsigned b=0;b<9;b++) for(unsigned c=0;c<9;c++) {
        unsigned at=index_of(a,b,c);
        check(permutation[a*81+b*9+c]==at,"independent parity permutation");
        for(unsigned v=0;v<256;v++) {
            unsigned char in[3]={v,255-v,(v*37+17)&255};
            for(unsigned j=0;j<407;j++) out[j]=GUARD;
            FN(0x522da8,void (*)(unsigned,unsigned,unsigned,const void *,void *))
                (a,b,c,in,out+1);
            for(unsigned j=0;j<407;j++)
                check(out[j]==(j==at+1?word(in[0],in[1],in[2]):GUARD),"pack value and bounds");
            pack_cases++;
        }
    }
}
static int scaled(unsigned char value,unsigned level) {
    int v=value<128?(int)value:(int)value-256;
    if(level>=1 && level<=7) { v*=level;v=v>=0?v/8:-((-v+7)/8); }
    return v;
}
static int signed_packed(int value) {
    unsigned code=(unsigned)value&127;
    return code<64?(int)code:(int)code-128;
}
static void selector_test(void) {
    static uint32_t params_words[0x220/4], mode_words[0x240/4], descriptor_words[0x70/4];
    static uint32_t work[0x700/4], out[407];
    static unsigned char config[4608],debug[256],status[4];
    unsigned char *params=(void *)params_words,*mode=(void *)mode_words;
    unsigned char *descriptor=(void *)descriptor_words;
    uintptr_t a_context[2]={(uintptr_t)params,(uintptr_t)mode};
    uintptr_t b_context[7]={0,0,0,(uintptr_t)descriptor,(uintptr_t)work,0,(uintptr_t)status};
    volatile uintptr_t *got=(volatile uintptr_t *)(BASE+0x118d8b4);
    const unsigned char *inputs=(const unsigned char *)0x40300000;
    got[0x1ad8/4]=(uintptr_t)config;got[0x2b20/4]=(uintptr_t)debug;
    got[0x2b80/4]=(uintptr_t)inputs;got[0x7af0/4]=(uintptr_t)(inputs+1280);
    got[0x49c8/4]=(uintptr_t)(inputs+2560);got[0x6dd0/4]=(uintptr_t)(inputs+3840);
    for(unsigned selector=0;selector<256;selector++) for(unsigned level=7;level<=8;level++) {
        native_set(params,0,sizeof(params_words));native_set(mode,0,sizeof(mode_words));
        native_set(descriptor,0,sizeof(descriptor_words));native_set(work,0,sizeof(work));
        for(unsigned j=0;j<407;j++) out[j]=GUARD;
        params[0x29]=level;descriptor[4]=selector;
        ((unsigned char *)work)[0x27]=1;work[0x6b8/4]=(uintptr_t)(out+1);status[0]=1;
        FN(0x523894,void (*)(void *,void *))(a_context,b_context);
        unsigned group=(selector>>5)&3, number=selector&15;
        unsigned type=number<=2 && group<2?group+1:0;
        const unsigned char *source=type==1?inputs+number*1280:type==2?inputs+3840+number*162:0;
        check(descriptor[0x68]==type && descriptor[0x69]==0,"table selection and SD condition");
        check(descriptor_words[0x64/4]==(uintptr_t)source,"selected source address");
        check(descriptor_words[0x14/4]==(uintptr_t)(out+1) && descriptor[0x18]==1,"scheduled output table");
        check(((unsigned char *)work)[0x27]==2,"native state transition");
        check(descriptor[0xc]==(type!=0),"LUT enable flag");
        check(out[0]==GUARD && out[406]==GUARD,"selected table bounds");
        for(unsigned a=0;a<5;a++) for(unsigned b=0;b<9;b++) for(unsigned c=0;c<9;c++) {
            unsigned j=a*81+b*9+c,k=b*9+c;int x=0,y=0,z=0;
            if(source) {
                x=type==1?scaled(source[j],level):0;
                y=scaled(source[type==1?j+405:k],level);
                z=scaled(source[type==1?j+810:k+81],level);
            }
            check(out[1+index_of(a,b,c)]==word(x,y,z),"selected table contents");
        }
        selector_cases++;
    }
}
/* Prototype at the consumer refresh branch. QEMU supplies a stable, owned
 * source and one capture context. Neither lifetime is assumed on a device. */
static unsigned char refresh_previous[1215];
static const unsigned char *refresh_shadow;
static const void *refresh_context;
static unsigned refresh_forced;
int fixture_refresh_gate(void *a,void *b) {
    int stock=FN(0x522dec,int (*)(void *,void *))(a,b);
    if(b!=refresh_context)return stock;
    const uintptr_t *desc=(const void *)((const uintptr_t *)b)[3];
    if(((const unsigned char *)desc)[4]!=0 || desc[0x64/4]!=(uintptr_t)refresh_shadow)return stock;
    unsigned changed=0;
    for(unsigned i=0;i<1215;i++)changed|=refresh_previous[i]!=refresh_shadow[i];
    if(!changed)return stock;
    for(unsigned i=0;i<1215;i++)refresh_previous[i]=refresh_shadow[i];
    refresh_forced++;
    return 1;
}
static void refresh_test(void) {
    static uint32_t params_words[0x220/4], mode_words[0x240/4], descriptor_words[0x70/4];
    static uint32_t work[0x700/4], out[407], capture_epoch[0x508/4], capture_state[0xe64/4];
    static unsigned char config[4608],debug[256],status[4],shadow[1280];
    const unsigned char *fixture=(const void *)0x40300000;
    unsigned char *params=(void *)params_words,*descriptor=(void *)descriptor_words,*state=(void *)work;
    uintptr_t a_context[3]={(uintptr_t)params,(uintptr_t)mode_words,(uintptr_t)capture_state};
    uintptr_t b_context[7]={0,0,0,(uintptr_t)descriptor,(uintptr_t)work,0,(uintptr_t)status};
    volatile uintptr_t *got=(volatile uintptr_t *)(BASE+0x118d8b4);
    typedef int (*Dirty)(void *,void *);
    typedef void (*Select)(void *,void *);
    Dirty dirty=FN(0x522dec,Dirty);
    Select select=FN(0x523894,Select);
    got[0x1ad8/4]=(uintptr_t)config;got[0x2b20/4]=(uintptr_t)debug;
    got[0x2b80/4]=(uintptr_t)shadow;
    params_words[0xec/4]=(uintptr_t)capture_epoch;
    params[0x29]=8;descriptor[4]=0;status[0]=1;work[0x6b8/4]=(uintptr_t)(out+1);
    out[0]=out[406]=GUARD;
    for(unsigned i=0;i<1280;i++)shadow[i]=fixture[i];
    check(dirty(a_context,b_context)==1 && dirty(a_context,b_context)==0,"stable original refresh key");
    state[0x27]=1;
    select(a_context,b_context);
    check(state[0x27]==2 && out[1]==word(shadow[0],shadow[405],shadow[810]),"initial table 0 build");
    const uint32_t old=out[1];
    const unsigned char original=shadow[0];
    shadow[0]^=1;
    check(dirty(a_context,b_context)==0,"shadow byte alone does not invalidate native cache");
    select(a_context,b_context);
    check(state[0x27]==2 && out[1]==old,"state 2 reuses previous packed node after source change");
    /* Fixture intervention only. A device integration must use a verified
     * capture-side lifecycle and must not write a guessed state pointer. */
    state[0x27]=1;
    select(a_context,b_context);
    check(state[0x27]==2 && out[1]!=old && out[1]==word(shadow[0],shadow[405],shadow[810]),
          "native rebuild consumes new shadow byte");
    const uint32_t updated=out[1];
    shadow[0]=original;
    select(a_context,b_context);
    check(out[1]==updated,"restoring the source also needs invalidation");
    /* The original state=2 path detects level changes for a three-plane
     * table. This models an existing dirty key, not a camera menu setting. */
    params[0x29]=7;
    select(a_context,b_context);
    check(state[0x27]==2 && out[1]==word(scaled(shadow[0],7),scaled(shadow[405],7),scaled(shadow[810],7)),
          "original dirty key rebuilds while state is 2");
    params[0x29]=8;
    select(a_context,b_context);
    check(state[0x27]==2 && out[1]==old,"original dirty key rebuilds at unchanged final strength");
    check(dirty(a_context,b_context)==0,"refresh key is clean before prototype");
    refresh_context=b_context;refresh_shadow=shadow;
    for(unsigned i=0;i<1215;i++)refresh_previous[i]=shadow[i];
    shadow[0]^=1;
    select(a_context,b_context);
    check(state[0x27]==2 && out[1]==updated && refresh_forced==1,"source-change gate refreshes while mode and strength stay fixed");
    select(a_context,b_context);
    check(out[1]==updated && refresh_forced==1,"unchanged source does not force a rebuild");
    shadow[0]=original;
    select(a_context,b_context);
    check(out[1]==old && refresh_forced==2,"source-change gate refreshes the restored stock source");
    shadow[1279]^=1;
    select(a_context,b_context);
    check(out[1]==old && refresh_forced==2,"ignored table tail does not refresh");
    descriptor[4]=1;
    select(a_context,b_context);
    uint32_t other=out[1];
    shadow[0]^=1;
    select(a_context,b_context);
    check(out[1]==other && refresh_forced==2,"table 0 update does not refresh table 1");
    refresh_context=0;
    check(out[0]==GUARD && out[406]==GUARD,"refresh packed output bounds");
    put("NATIVE_3DLUT_REFRESH_PASSED: unchanged native path stays cached; source-change prototype rebuilds table 0 in both directions\n");
}
static void capture_route_test(void) {
    static uint32_t params_words[0x220/4], mode_words[0x240/4], descriptor_words[0x70/4];
    static uint32_t work[0x700/4], out[407], capture_epoch[0x508/4], capture_state[0xe64/4];
    static unsigned char config[4608],debug[256],status[4],report[0x370],shadow[1280];
    const unsigned char *fixture=(const void *)0x40300000;
    unsigned char *params=(void *)params_words,*mode=(void *)mode_words;
    unsigned char *descriptor=(void *)descriptor_words,*state=(void *)work;
    uintptr_t report_context[]={(uintptr_t)report};
    uintptr_t a_context[]={(uintptr_t)params,(uintptr_t)mode,(uintptr_t)capture_state};
    uintptr_t b_context[]={(uintptr_t)report_context,0,0,(uintptr_t)descriptor,(uintptr_t)work,0,(uintptr_t)status};
    volatile uintptr_t *got=(volatile uintptr_t *)(BASE+0x118d8b4);
    typedef void (*Stage)(void *,void *);
    Stage make_descriptor=FN(0x526a90,Stage),select=FN(0x523894,Stage);
    got[0x1ad8/4]=(uintptr_t)config;got[0x2b20/4]=(uintptr_t)debug;
    got[0x4b2c/4]=(uintptr_t)(fixture+5120);
    got[0x2b80/4]=(uintptr_t)fixture;got[0x7af0/4]=(uintptr_t)(fixture+1280);
    got[0x49c8/4]=(uintptr_t)shadow;got[0x6dd0/4]=(uintptr_t)(fixture+3840);
    out[0]=out[406]=GUARD;
    /* CAP and preview descriptor mapping are native. The mode/flag inputs
     * are explicit fixture values, not a dump of a running camera frame. */
    for(unsigned capture=0;capture<=1;capture++)
    for(unsigned alt=0;alt<=1;alt++)
    for(unsigned direct=0;direct<=1;direct++) {
        native_set(params,0,sizeof params_words);native_set(mode,0,sizeof mode_words);
        native_set(descriptor,0,sizeof descriptor_words);native_set(work,0,sizeof work);
        for(unsigned i=0;i<1280;i++)shadow[i]=fixture[2560+i];
        params_words[0xec/4]=(uintptr_t)capture_epoch;
        params[1]=direct;params[0x29]=8;params[0x2e]=alt;mode[3]=capture?2:0;
        work[0x6b8/4]=(uintptr_t)(out+1);state[0x27]=1;
        make_descriptor(a_context,b_context);
        unsigned expected=capture?(alt?1:2):0;
        check(descriptor[4]==expected && report[0x368]==expected,"stock descriptor routes still/preview");
        select(a_context,b_context);
        const unsigned char *source=expected==2?shadow:fixture+expected*1280;
        check(descriptor_words[0x64/4]==(uintptr_t)source && descriptor[0x68]==1 &&
              descriptor[0x18]==1 && descriptor_words[0x14/4]==(uintptr_t)(out+1),"descriptor reaches native LUT output");
        check(out[1]==word(source[0],source[405],source[810]),"stock packed node from routed source");
        if(expected==2) {
            /* State 1 builds without saving the comparison key; let the
             * original steady path see an unchanged frame before editing. */
            make_descriptor(a_context,b_context);select(a_context,b_context);
            const uint32_t before=out[1];
            shadow[0]^=1;
            make_descriptor(a_context,b_context);select(a_context,b_context);
            check(out[1]==(direct?word(shadow[0],shadow[405],shadow[810]):before),
                  direct?"CAP direct repacks table 2":"CAP steady mode caches table 2");
            shadow[0]^=1;
            make_descriptor(a_context,b_context);select(a_context,b_context);
            check(out[1]==before,"table 2 returns to original packed value");
        }
        check(out[0]==GUARD && out[406]==GUARD,"capture route output bounds");
    }
    put("NATIVE_3DLUT_CAPTURE_ROUTE_PASSED: preview table 0; CAP tables 2/1; CAP direct rebuilds table 2\n");
    const unsigned char *looks=fixture+5120+4608+1;
    if(!looks[-1])return;
    params[1]=1;mode[3]=2;
    /* Verify the actual candidate reaches every packed node, then restore
     * the entire stock source and verify the full output again. */
    for(unsigned table=1;table<=2;table++) {
        const unsigned char *stock=fixture+1280*table,*look=looks+1280*(table-1);
        unsigned slot=(table==1?0x7af0:0x49c8)/4,changed_nodes=0;
        params[0x2e]=(table==1);
        got[slot]=(uintptr_t)shadow;
        for(unsigned level=1;level<=8;level++)
        for(unsigned pass=0;pass<3;pass++) {
            const unsigned char *input=pass==1?look:stock;
            params[0x29]=level;
            for(unsigned i=0;i<1280;i++)shadow[i]=input[i];
            make_descriptor(a_context,b_context);select(a_context,b_context);
            check(descriptor[4]==table && descriptor[0x18]==1 &&
                  descriptor_words[0x14/4]==(uintptr_t)(out+1),"CAP candidate packed buffer is enabled");
            for(unsigned a=0;a<5;a++)for(unsigned b=0;b<9;b++)for(unsigned c=0;c<9;c++) {
                unsigned j=a*81+b*9+c;
                int component[3],different=0;
                for(unsigned plane=0;plane<3;plane++) {
                    unsigned i=j+plane*405;
                    component[plane]=scaled(input[i],level);
                    int delta=signed_packed(component[plane])-signed_packed(scaled(stock[i],level));
                    int limit=plane?12:8;
                    check(delta>=-limit && delta<=limit,"CAP candidate packed delta budget");
                    different|=delta!=0;
                }
                check(out[1+index_of(a,b,c)]==word(component[0],component[1],component[2]),
                      "CAP candidate full packed output");
                if(pass==1 && level==8)changed_nodes+=different;
            }
            check(out[0]==GUARD && out[406]==GUARD,"CAP candidate output bounds");
        }
        got[slot]=(uintptr_t)stock;
        check(changed_nodes>0,"CAP candidate changes packed nodes at full strength");
    }
    put("NATIVE_3DLUT_CAPTURE_LOOK_PASSED: two tables, eight levels, all 405 nodes verified for stock/FL/restore\n");
}
static void table_test(void) {
    static uint32_t params_words[0x220/4], mode_words[4], descriptor_words[0x70/4];
    static uint32_t work[0x700/4], banks[3*405+2];
    static unsigned char source[1215];
    unsigned char *params=(void *)params_words,*mode=(void *)mode_words;
    unsigned char *descriptor=(void *)descriptor_words;
    uintptr_t a_context[2]={(uintptr_t)params,(uintptr_t)mode};
    uintptr_t b_context[5]={0,0,0,(uintptr_t)descriptor,(uintptr_t)work};
    const unsigned levels[]={0,1,3,7,8,255};
    for(unsigned type=1;type<=2;type++)
    for(unsigned level_i=0;level_i<6;level_i++)
    for(unsigned destination=0;destination<3;destination++)
    for(unsigned pattern=0;pattern<5;pattern++) {
        unsigned level=levels[level_i];
        native_set(params,0,sizeof(params_words));native_set(mode,0,sizeof(mode_words));
        native_set(descriptor,0,sizeof(descriptor_words));
        for(unsigned j=0;j<sizeof(work)/4;j++) work[j]=GUARD;
        for(unsigned j=0;j<3*405+2;j++) banks[j]=GUARD;
        for(unsigned j=0;j<sizeof(source);j++)
            source[j]=pattern==0?0:pattern==1?63:pattern==2?192:(j*37+11)&255;
        params[0x29]=level;
        params[0x20e]=destination==2?1:0;
        mode[6]=destination==0?1:0;
        descriptor_words[0x64/4]=pattern==4?0:(uintptr_t)source;
        descriptor[0x68]=type;
        work[0x6b8/4]=(uintptr_t)(banks+1);
        uint32_t *output=destination==0?work+0x64/4:banks+1+(destination==2?405:0);
        FN(0x5231fc,void (*)(void *,void *))(a_context,b_context);
        for(unsigned a=0;a<5;a++) for(unsigned b=0;b<9;b++) for(unsigned c=0;c<9;c++) {
            unsigned j=a*81+b*9+c,k=b*9+c;
            int x=0,y=0,z=0;
            if(pattern!=4) {
                x=type==1?scaled(source[j],level):0;
                y=scaled(source[type==1?j+405:k],level);
                z=scaled(source[type==1?j+810:k+81],level);
            }
            check(output[index_of(a,b,c)]==word(x,y,z),"native create/copy table values");
        }
        for(unsigned j=0;j<sizeof(work)/4;j++) {
            if(j>=0x28/4 && j<0x34/4) check(work[j]==0,"depth initializer");
            else if(j==0x34/4) check(work[j]==0xa5a50000,"depth initializer final halfword");
            else if(j==0x6b8/4) check(work[j]==(uintptr_t)(banks+1),"output pointer retained");
            else if(!(destination==0 && j>=0x64/4 && j<(0x64+1620)/4))
                check(work[j]==GUARD,"work buffer guard");
        }
        for(unsigned j=0;j<3*405+2;j++)
            if(destination==0 || j<1+(destination==2?405:0) || j>=1+(destination==2?810:405))
                check(banks[j]==GUARD,"bank buffer guard");
        table_cases++;
    }
}
static void writer_test(void) {
    static uint32_t input[405];
    uintptr_t object[2]={0,(uintptr_t)mock_registers};
    uintptr_t descriptor[2]={0,(uintptr_t)input};
    for(unsigned j=0;j<405;j++) input[j]=j*0x10203u;
    for(unsigned j=0;j<sizeof(mock_registers)/4;j++) mock_registers[j]=GUARD;
    write_source=input;bank_calls=0;
    FN(0x70ea4c,void (*)(void *,void *))(object,descriptor);
    check(bank_calls==8,"eight banks copied");
    check(mock_registers[0x15d40/4]==0,"write gate cleared");
    for(unsigned j=0;j<sizeof(mock_registers)/4;j++) {
        uint32_t expected=j==0x15d40/4?0:GUARD;
        for(unsigned bank=0;bank<8;bank++)
            if(j>=offsets[bank]/4 && j<offsets[bank]/4+counts[bank])
                expected=input[starts[bank]+j-offsets[bank]/4];
        check(mock_registers[j]==expected,"register aperture and gaps");
    }
    for(unsigned invalid=8;invalid<256;invalid++)
        FN(0x70e8fc,void (*)(void *,unsigned,void *))(mock_registers,invalid,input);
    check(bank_calls==8,"invalid bank rejected");
}
void guest_main(void) {
    coordinate_test();pack_test();table_test();selector_test();refresh_test();capture_route_test();writer_test();
    check(pack_cases==103680 && table_cases==180 && selector_cases==512 && coordinate_cases==8194,"coverage");
    put("QEMU_NATIVE_3DLUT_PASSED: 103680 pack cases; 180 table cases; 512 selector cases; 8 bank writes\n");
    put("ORIGINAL_CHROMA_CODEC_PASSED: 8194 signed expansion/compression cases\n");
    put("ORIGINAL_PACK_CREATE_COPY_WRITER; MMIO_REPLACED_WITH_RAM; MEMCPY_MEMSET_MOCKED\n");
    put("NO_ISP_PIXEL_TEST; COLOR_ENCODING_UNPROVEN; NO_CAMERA_WRITE; NOT_FLASH_READY\n");
    finish();
}
