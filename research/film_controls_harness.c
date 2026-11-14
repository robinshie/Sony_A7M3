#include "a7-fl-runtime-prefs.h"
#include "a7-fl-fivepoint.h"
#ifndef A7_FILM_QEMU
#include <stdio.h>
#include <stdlib.h>
#else
void *memcpy(void *d,const void *s,unsigned n){uint8_t *a=d;const uint8_t *b=s;while(n--)*a++=*b++;return d;}
void *memset(void *d,int v,unsigned n){uint8_t *a=d;while(n--)*a++=(uint8_t)v;return d;}
#endif
static unsigned checks,cases,hash=2166136261u,rng=0x74616e67;
static unsigned random_word(void){rng=rng*1664525u+1013904223u;return rng;}
static void put(const char *s){
#ifdef A7_FILM_QEMU
    volatile unsigned *u=(volatile unsigned *)0x10009000;while(*s){while(u[6]&32){}u[0]=*s++;}
#else
    fputs(s,stdout);
#endif
}
static void num(unsigned n){char b[12];unsigned i=0;do{b[i++]=(char)('0'+n%10);n/=10;}while(n);while(i){char s[2]={b[--i],0};put(s);}}
static void end(int failed){
#ifdef A7_FILM_QEMU
    (void)failed;register unsigned r0 __asm__("r0")=0x18,r1 __asm__("r1")=0x20026;__asm__ volatile("svc 0xab":"+r"(r0),"+r"(r1)::"memory");while(1){}
#else
    exit(failed);
#endif
}
static void check(int ok,const char *msg){checks++;if(!ok){put("FAIL ");put(msg);put(" case=");num(cases);put("\n");end(1);}}
uint32_t a7_fl_crc(const uint8_t *p,uint32_t n){uint32_t c=~0u;while(n--){c^=*p++;for(unsigned i=0;i<8;i++)c=(c>>1)^((c&1)?0xedb88320u:0);}return ~c;}
static int equal(const void *a,const void *b,unsigned n){const uint8_t *x=a,*y=b;while(n--)if(*x++!=*y++)return 0;return 1;}
static int clamp(int v,int lo,int hi){return v<lo?lo:v>hi?hi:v;}
static int decoded(uint8_t v,unsigned packed){return packed?(v<64?v:(int)v-128):(v<128?v:(int)v-256);}
static void crc(uint8_t record[128]){uint32_t c=a7_fl_crc(record,124);for(unsigned i=0;i<4;i++)record[124+i]=(uint8_t)(c>>(8*i));}
static void test_preferences(void){
    const int lo[8]={-9,-9,-9,0,-9,-3,1,0},hi[8]={9,9,9,9,9,3,5,9};
    uint8_t identity[32]={4},record[128],again[128];const char build[24]="37114_13.2026020901";
    for(unsigned trial=0;trial<2000;trial++){
        struct a7_fl_preference p={0},q={0};p.generation=trial+1;p.enabled=(int)(trial%4);p.schema=4;p.candidate_crc=random_word();
        int banks[3][8];for(unsigned b=0;b<3;b++)for(unsigned f=0;f<8;f++)banks[b][f]=lo[f]+(int)(random_word()%(unsigned)(hi[f]-lo[f]+1));
        unsigned active=p.enabled?(unsigned)p.enabled-1:0,n=0;
        for(unsigned b=0;b<3;b++){
            for(unsigned f=0;f<8;f++)if(b==active)p.parameters[f]=banks[b][f];else (n?p.third_parameters:p.other_parameters)[f]=(int8_t)banks[b][f];
            if(b!=active)n++;
            for(unsigned f=0;f<7;f++)p.film[b][f]=(int8_t)(f<2?(int)(random_word()%10):(int)(random_word()%19)-9);
        }
        check(!a7_fl_preference_encode(record,&p,identity,build),"encode film");
        check(!a7_fl_preference_decode(&q,record,128,identity,build),"decode film");
        check(q.schema==4&&q.enabled==p.enabled&&q.generation==p.generation&&q.candidate_crc==p.candidate_crc,"metadata roundtrip");
        check(equal(q.parameters,p.parameters,sizeof p.parameters)&&equal(q.other_parameters,p.other_parameters,8)&&equal(q.third_parameters,p.third_parameters,8)&&equal(q.film,p.film,21),"all banks roundtrip");
        for(unsigned mode=0;mode<4;mode++){
            a7_fl_preference_switch(&q,(int)mode);unsigned bank=mode?mode-1:0;
            for(unsigned f=0;f<8;f++)check(q.parameters[f]==banks[bank][f],"original parameters remain independent");
            check(equal(q.film,p.film,21),"film parameters remain independent");
            check(!a7_fl_preference_encode(again,&q,identity,build),"switched encode");
            check(equal(record+24,again+24,29),"stable bank packing independent of selected mode");
        }
        for(unsigned i=0;i<128;i++)hash=(hash^record[i])*16777619u;
        cases++;
    }
    for(unsigned schema=0;schema<=3;schema++)if(schema!=1)for(int mode=0;mode<=(schema==3?3:2);mode++){
        struct a7_fl_preference p={0},q={0};p.generation=1;p.schema=schema;p.enabled=mode;p.parameters[0]=8;p.parameters[6]=3;p.other_parameters[0]=-7;p.other_parameters[6]=2;p.third_parameters[0]=6;p.third_parameters[6]=4;
        check(!a7_fl_preference_encode(record,&p,identity,build),"legacy encode");
        check(!a7_fl_preference_decode(&q,record,128,identity,build),"legacy decode with film build");
        struct a7_fl_preference expected=q;a7_fl_preference_migrate_three(&expected);
        check(a7_fl_preference_migrate_film(&q)==1&&q.schema==4,"migrate film");
        check(equal(q.parameters,expected.parameters,32)&&equal(q.other_parameters,expected.other_parameters,8)&&equal(q.third_parameters,expected.third_parameters,8),"migration preserves legacy banks");
        for(unsigned b=0;b<3;b++)for(unsigned f=0;f<7;f++)check(q.film[b][f]==0,"new controls neutral");
        check(a7_fl_preference_migrate_film(&q)==0,"idempotent migration");cases++;
    }
    struct a7_fl_preference p={0},q={0};p.generation=2;p.schema=4;p.parameters[6]=p.other_parameters[6]=p.third_parameters[6]=3;
    check(!a7_fl_preference_encode(record,&p,identity,build),"valid rejection baseline");
    for(unsigned bit=225;bit<256;bit++){
        for(unsigned i=0;i<128;i++)again[i]=record[i];
        again[24+bit/8]|=(uint8_t)(1u<<(bit%8));crc(again);
        check(a7_fl_preference_decode(&q,again,128,identity,build)<0,"reserved bits rejected with valid CRC");
    }
    for(unsigned f=0;f<7;f++)for(int v=-16;v<=15;v++){
        p.film[2][f]=(int8_t)v;
        int valid=v>=(f<2?0:-9)&&v<=9;
        check((a7_fl_preference_encode(again,&p,identity,build)==0)==valid,"film control bounds");p.film[2][f]=0;
    }
    check(!a7_fl_preference_encode(again,&p,identity,build),"valid record");again[12]=3;crc(again);
    check(a7_fl_preference_choose(&q,record,128,again,128,identity,build)==1&&q.generation==3,"new slot selected");
    for(unsigned n=0;n<128;n++)check(a7_fl_preference_choose(&q,record,128,again,n,identity,build)==0&&q.generation==2,"torn record ignored");
}
static void test_curve(void){
    uint8_t input[1280],out[1280],again[1280];int8_t low[405],high[405];int c[5]={0},knots[5];
    for(unsigned trial=0;trial<800;trial++){
        for(unsigned i=0;i<5;i++)c[i]=trial==0?0:trial<=95?(i==(trial-1)/19?(int)((trial-1)%19)-9:0):(int)(random_word()%19)-9;
        check(!a7_fl_fivepoint_knots(c,knots),"five knots");
        for(int y=0;y<=256;y++){
            int v=a7_fl_fivepoint_sample(knots,y);check(v>=0&&v<=256,"curve domain");
            if(y)check(v>=a7_fl_fivepoint_sample(knots,y-1),"curve monotonic");
            if(!(y%64))check(v==knots[y/64],"independent point interpolation");
        }
        for(unsigned encoding=0;encoding<2;encoding++)for(unsigned bounded=0;bounded<2;bounded++){
            for(unsigned i=0;i<1280;i++)input[i]=(uint8_t)(i>=1215?random_word():0);
            for(unsigned i=0;i<1215;i++){
                int value=(int)(random_word()%41)-20;
                input[i]=(uint8_t)(value&(encoding?127:255));
                if(i<405){low[i]=(int8_t)(bounded?clamp(value-7,-64,63):-64);high[i]=(int8_t)(bounded?clamp(value+7,-64,63):63);}
            }
            check(!a7_fl_fivepoint_lut(input,1280,out,1280,encoding,c,low,high),"native table transform");
            check(equal(input+405,out+405,875),"chroma and calibration preserved");
            if(trial==0)check(equal(input,out,1280),"zero identity");
            for(unsigned col=0;col<81;col++){
                int previous=0;
                for(unsigned row=0;row<5;row++){
                    unsigned i=row*81+col;int v=decoded(out[i],encoding),y=clamp((int)row*64+v,0,256);
                    check(v>=low[i]&&v<=high[i],"capture bound maintained");
                    if(trial)check(y>=previous,"table monotonic");
                    previous=y;
                }
            }
            for(unsigned i=0;i<1280;i++)again[i]=input[i];
            check(!a7_fl_fivepoint_lut(again,1280,again,1280,encoding,c,low,high),"in-place");
            check(equal(out,again,1280),"in-place identical");
            for(unsigned i=0;i<1280;i++)hash=(hash^out[i])*16777619u;
            cases++;
        }
    }
    for(unsigned i=0;i<1280;i++)out[i]=0xa5;
    for(unsigned i=0;i<5;i++)c[i]=0;
    c[2]=10;
    check(a7_fl_fivepoint_lut(input,1280,out,1280,1,c,0,0)<0,"invalid point");c[2]=0;
    check(a7_fl_fivepoint_lut(input,1279,out,1280,1,c,0,0)<0,"invalid table length");
    check(a7_fl_fivepoint_lut(input,1280,out,1280,1,c,low,0)<0,"incomplete bounds");
    input[700]=128;check(a7_fl_fivepoint_lut(input,1280,out,1280,1,c,0,0)<0,"invalid packed node");
    for(unsigned i=0;i<1280;i++)check(out[i]==0xa5,"rejection leaves output untouched");
}
#ifdef A7_FILM_PRIVATE_PREFS
#include "private-prefs.h"
static void test_private(void){
    for(unsigned slot=0;slot<2;slot++){
        const uint8_t *raw=private_preferences[slot];uint8_t out[128];
        struct a7_fl_preference p={0},q={0};
        check(!a7_fl_preference_decode(&p,raw,128,raw+56,(const char *)raw+88),"actual saved record decodes");
        check(!a7_fl_preference_encode(out,&p,raw+56,(const char *)raw+88)&&equal(out,raw,128),"actual saved record byte-exact roundtrip");
        struct a7_fl_preference expected=p;a7_fl_preference_migrate_three(&expected);
        check(a7_fl_preference_migrate_film(&p)==1,"actual saved record migrates");
        check(!a7_fl_preference_encode(out,&p,raw+56,(const char *)raw+88),"actual migrated record encodes");
        check(!a7_fl_preference_decode(&q,out,128,raw+56,(const char *)raw+88),"actual migrated record decodes");
        for(int mode=0;mode<4;mode++){
            a7_fl_preference_switch(&q,mode);a7_fl_preference_switch(&expected,mode);
            check(equal(q.parameters,expected.parameters,32),"actual saved banks preserved through mode switches");
            for(unsigned b=0;b<3;b++)for(unsigned f=0;f<7;f++)check(q.film[b][f]==0,"actual migration initializes film controls neutral");
        }
        cases++;
    }
}
#endif
void guest_main(void){test_preferences();test_curve();
#ifdef A7_FILM_PRIVATE_PREFS
    test_private();
#endif
    put("FILM_CONTROLS_CASES ");num(cases);put(" CHECKS ");num(checks);put(" HASH ");num(hash);put("\nFILM_CONTROLS_PASSED\n");end(0);}
#ifndef A7_FILM_QEMU
int main(void){guest_main();return 0;}
#endif
