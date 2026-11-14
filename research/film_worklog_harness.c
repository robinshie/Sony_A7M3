#include "a7-fl-worklog.h"
#include "a7-fl-fivepoint.h"
#include "a7-fl-runtime.h"
#include <stddef.h>
#ifndef A7_WORKLOG_QEMU
#include <stdio.h>
#include <stdlib.h>
#endif
void *memcpy(void *d,const void *s,size_t n){uint8_t *a=d;const uint8_t *b=s;while(n--)*a++=*b++;return d;}
void *memset(void *d,int v,size_t n){uint8_t *a=d;while(n--)*a++=(uint8_t)v;return d;}
static int eq(const void *a,const void *b,unsigned n){for(unsigned i=0;i<n;i++)if(((const uint8_t *)a)[i]!=((const uint8_t *)b)[i])return 0;return 1;}
uint32_t a7_fl_crc(const uint8_t *p,uint32_t n){uint32_t c=~0u;while(n--){c^=*p++;for(unsigned i=0;i<8;i++)c=c>>1^((c&1)?0xedb88320u:0);}return ~c;}
static unsigned checks,cases;
static void put(const char *s){
#ifdef A7_WORKLOG_QEMU
    volatile unsigned *u=(void *)0x10009000;while(*s){while(u[6]&32){}u[0]=*s++;}
#else
    fputs(s,stdout);
#endif
}
static void num(unsigned n){char b[12];unsigned i=0;do{b[i++]=(char)('0'+n%10);n/=10;}while(n);while(i){char c[2]={b[--i],0};put(c);}}
static void stop(int status){
#ifdef A7_WORKLOG_QEMU
    (void)status;register unsigned r0 __asm__("r0")=0x18,r1 __asm__("r1")=0x20026;__asm__ volatile("svc 0xab":"+r"(r0),"+r"(r1)::"memory");while(1){}
#else
    exit(status);
#endif
}
static void check(int ok,const char *s){checks++;if(!ok){put("FAIL ");put(s);put(" case=");num(cases);put("\n");stop(1);}}
struct disk {uint8_t bytes[2][129];unsigned size[2],exists[2],writes,reads;int tear,fail,read_fail;};
static int rd(void *ctx,unsigned slot,uint8_t *out,unsigned cap,unsigned *length){
    struct disk *d=ctx;check(slot<2&&cap==129,"bounded namespace/read");
    if(d->read_fail&&++d->reads==(unsigned)d->read_fail)return -1;
    *length=d->size[slot];if(!d->exists[slot])return 1;
    memcpy(out,d->bytes[slot],*length);return 0;
}
static int wr(void *ctx,unsigned slot,const uint8_t *before,unsigned n,int exists,const uint8_t after[128]){
    struct disk *d=ctx;check(slot<2,"bounded replace");
    check((int)d->exists[slot]==exists&&d->size[slot]==n&&eq(before,d->bytes[slot],n),"exact inactive preimage");
    if(d->fail==1)return -1;
    d->writes++;d->exists[slot]=1;d->size[slot]=d->tear?(unsigned)d->tear:128;
    memcpy(d->bytes[slot],after,d->size[slot]);
    if(d->fail==3)d->bytes[slot][124]^=1;
    if(d->fail==4)d->bytes[1-slot][0]^=1;
    return d->tear||d->fail==2?-1:0;
}
static const uint8_t identity[32]={7,3,4};
static const char build[24]="37114_13.2026020901";
static int open_j(struct a7_fl_worklog *j,struct disk *d){struct a7_fl_store_io io={rd,wr,d};return a7_fl_worklog_open(j,&io,identity,build);}
static int generate(void *ctx,const struct a7_fl_preference *p,unsigned table,uint8_t out[1280]){
    (void)ctx;uint8_t base[1280];int curve[5];unsigned bank=p->enabled?(unsigned)p->enabled-1:0;
    for(unsigned i=0;i<1280;i++)base[i]=i<405?0:(uint8_t)((i+17*table)%(i<1215?32:256));
    for(unsigned i=0;i<5;i++)curve[i]=p->film[bank][i+2];
    return a7_fl_fivepoint_lut(base,1280,out,1280,table==2,curve,0,0);
}
static struct a7_fl_preference preference(int v){
    struct a7_fl_preference p={0};p.generation=44;p.enabled=3;p.schema=4;
    p.parameters[6]=p.other_parameters[6]=p.third_parameters[6]=3;
    for(unsigned b=0;b<3;b++){p.film[b][0]=(int8_t)(b+1);p.film[b][1]=(int8_t)(b+2);p.film[b][2]=(int8_t)((int)b-1);p.film[b][3]=(int8_t)v;p.film[b][5]=(int8_t)-v;}
    uint8_t table[1280];check(!generate(0,&p,0,table),"generate preview");p.candidate_crc=a7_fl_crc(table,1280);return p;
}
static void word(uint8_t *p,uint32_t v){for(unsigned i=0;i<4;i++)p[i]=(uint8_t)(v>>(8*i));}
static void sequence(struct disk *d,unsigned slot,uint32_t v){word(d->bytes[slot]+12,v);word(d->bytes[slot]+124,a7_fl_crc(d->bytes[slot],124));}
struct properties {uint8_t live[3][1280];unsigned writes,cut;};
static int read_property(void *ctx,unsigned slot,uint8_t out[1280]){
    struct properties *p=ctx;memcpy(out,p->live[slot],1280);return 0;
}
static int write_property(void *ctx,unsigned slot,const uint8_t before[1280],const uint8_t after[1280]){
    struct properties *p=ctx;
    if(!eq(before,p->live[slot],1280)||++p->writes==p->cut)return -1;
    memcpy(p->live[slot],after,1280);return 0;
}
static void curve_lifecycle(void){
    struct a7_fl_preference committed=preference(1),edited=preference(8),saved;
    committed.generation=1;edited.generation=2;
    struct disk prefs={0},work;
    struct a7_fl_store store;
    struct a7_fl_store_io pref_io={rd,wr,&prefs};
    int present=0;
    check(!a7_fl_store_open(&store,&pref_io,identity,build,&saved,&present)&&!present,"open dedicated settings");
    check(!a7_fl_store_save(&store,&committed),"save starting curve");
    struct disk prefs_snapshot=prefs;
    for(unsigned scenario=0;scenario<5;scenario++){
        unsigned cut=scenario<4?scenario:0,confirm=scenario==0;
        struct a7_fl_worklog log={0};
        struct properties props={0};
        struct a7_fl_curve_scratch scratch;
        struct a7_fl_curve_io io={generate,read_property,write_property,&props,&scratch};
        prefs=prefs_snapshot;work=(struct disk){0};
        for(unsigned t=0;t<3;t++)check(!generate(0,&committed,t,props.live[t]),"seed prior table");
        props.cut=cut;
        check(!open_j(&log,&work),"open dedicated worklog");
        int rc=a7_fl_curve_transition(&log,&io,&committed,&edited);
        check(cut?(rc==A7_FL_WORKLOG_WRITE&&log.fault):rc==0,"controlled interruption between LUT writes");
        if(confirm)check(!a7_fl_store_save(&store,&edited),"explicit Save commits successful preview");
        check(!a7_fl_store_open(&store,&pref_io,identity,build,&saved,&present)&&present&&
              saved.generation==(confirm?2u:1u),"reboot reloads last confirmed preference");
        props.cut=0;props.writes=0;
        check(!open_j(&log,&work)&&!a7_fl_curve_recover(&log,&io,&saved),"boot reconciles partial preview");
        for(unsigned t=0;t<3;t++){
            uint8_t expected[1280];
            check(!generate(0,&saved,t,expected)&&eq(expected,props.live[t],1280),"boot applies confirmed curve exactly");
        }
        props.live[2][1279]^=1;props.writes=0;
        check(a7_fl_curve_recover(&log,&io,&saved)==A7_FL_WORKLOG_UNKNOWN&&!props.writes,
             "foreign property aborts before any changes");
        cases++;
    }
    struct a7_fl_worklog log={0};
    struct properties props={0};
    struct a7_fl_curve_scratch scratch;
    struct a7_fl_curve_io io={generate,read_property,write_property,&props,&scratch};
    work=(struct disk){0};
    for(unsigned t=0;t<3;t++)check(!generate(0,&committed,t,props.live[t]),"prepare cancellation fixture");
    check(!open_j(&log,&work)&&!a7_fl_curve_transition(&log,&io,&committed,&edited)
          &&!a7_fl_curve_transition(&log,&io,&edited,&committed),"cancel restores confirmed curve");
    check(eq(&prefs,&prefs_snapshot,sizeof prefs),"preview and Cancel do not persist user settings");
    cases++;
}
static void tests(void){
    struct disk d={0},saved;struct a7_fl_worklog j={0},reboot={0};
    struct a7_fl_preference a=preference(-4),b=preference(5),c=preference(2),unchanged=a;
    check(!open_j(&j,&d)&&j.latest==-1,"empty worklog");
    check(!a7_fl_worklog_prepare(&j,&a)&&j.record[j.latest].generation==1,"first durable endpoint");
    check(eq(&a,&unchanged,sizeof a)&&a.generation==44,"user-confirmed generation untouched");
    check(!a7_fl_worklog_prepare(&j,&a)&&d.writes==1,"identical state no duplicate write");
    /* Model a completed three-table apply before starting another transition. */
    check(!a7_fl_worklog_prepare(&j,&b)&&d.writes==2,"next endpoint");
    check(!open_j(&reboot,&d)&&reboot.valid[0]&&reboot.valid[1],"both endpoints recoverable");
    check(eq(reboot.record[reboot.latest].film,b.film,sizeof b.film),"all three film banks persist");
    uint8_t tables[2][3][1280];
    for(unsigned t=0;t<3;t++){check(!generate(0,&a,t,tables[0][t]),"old curve");check(!generate(0,&b,t,tables[1][t]),"new curve");}
    for(unsigned combination=0;combination<8;combination++){
        for(unsigned t=0;t<3;t++)check(a7_fl_worklog_recognize(&reboot,t,tables[(combination>>t)&1][t],generate,0)==1,"power cut between three LUT writes");
        cases++;
    }
    for(unsigned t=0;t<3;t++)for(unsigned at=0;at<1280;at++){
        tables[0][t][at]^=1;
        check(a7_fl_worklog_recognize(&reboot,t,tables[0][t],generate,0)==0,"foreign LUT byte never recognized");
        tables[0][t][at]^=1;
    }
    cases++;saved=d;
    for(int tear=1;tear<128;tear++){
        d=saved;d.tear=tear;check(!open_j(&j,&d),"before torn prepare");
        check(a7_fl_worklog_prepare(&j,&c)==A7_FL_WORKLOG_WRITE&&j.fault,"torn journal forbids LUT write");
        unsigned w=d.writes;check(a7_fl_worklog_prepare(&j,&c)==A7_FL_WORKLOG_FAULT&&d.writes==w,"never retry writer");
        d.tear=0;check(!open_j(&reboot,&d)&&reboot.record[reboot.latest].generation==2,"last applied endpoint survives tear");
        for(unsigned t=0;t<3;t++)check(a7_fl_worklog_recognize(&reboot,t,tables[1][t],generate,0)==1,"reconcile only actual prior endpoint");
        check(a7_fl_worklog_prepare(&reboot,&c)!=0&&d.writes==w,"unknown inactive file not overwritten");cases++;
    }
    for(int failure=1;failure<=4;failure++){
        d=saved;d.fail=failure;check(!open_j(&j,&d),"before write failure");
        check(a7_fl_worklog_prepare(&j,&c)<0&&j.fault,"failure never authorizes table apply");
        unsigned w=d.writes;check(a7_fl_worklog_prepare(&j,&c)<0&&d.writes==w,"write failure no automatic retry");
        d.fail=0;
        if(failure==2){check(!open_j(&reboot,&d)&&reboot.record[reboot.latest].generation==3,"lost ack can leave complete next endpoint");for(unsigned t=0;t<3;t++)check(a7_fl_worklog_recognize(&reboot,t,tables[1][t],generate,0)==1,"lost ack retains actual previous tables");}
        cases++;
    }
    for(int failure=1;failure<=4;failure++){
        d=saved;check(!open_j(&j,&d),"before read failure");d.reads=0;d.read_fail=failure;
        check(a7_fl_worklog_prepare(&j,&c)<0&&j.fault,"read failure forbids apply");cases++;
    }
    d=saved;check(!open_j(&j,&d),"before foreign change");d.bytes[0][0]^=1;
    unsigned w=d.writes;check(a7_fl_worklog_prepare(&j,&c)==A7_FL_WORKLOG_CHANGED&&d.writes==w,"preimage changed no write");cases++;
    d=saved;sequence(&d,0,7);check(open_j(&j,&d)==A7_FL_WORKLOG_HISTORY,"sequence gap rejected");
    d=saved;sequence(&d,0,2);check(open_j(&j,&d)==A7_FL_WORKLOG_HISTORY,"duplicate sequence rejected");cases++;
    d=saved;sequence(&d,0,0xfffffffeu);sequence(&d,1,0xffffffffu);check(!open_j(&j,&d),"max sequence read");
    w=d.writes;check(a7_fl_worklog_prepare(&j,&c)==A7_FL_WORKLOG_EXHAUSTED&&d.writes==w,"sequence never wraps");cases++;
    d=(struct disk){0};d.exists[0]=1;d.size[0]=128;
    check(!a7_fl_preference_encode(d.bytes[0],&a,identity,build),"ordinary saved preferences");
    check(open_j(&j,&d)==A7_FL_WORKLOG_UNKNOWN,"saved preferences cannot masquerade as work records");cases++;
    d=saved;check(!open_j(&j,&d),"before record checksum mismatch");j.record[0].candidate_crc^=1;
    check(a7_fl_worklog_recognize(&j,1,tables[0][1],generate,0)==A7_FL_WORKLOG_ARGUMENT,"candidate CRC pins generating recipe");cases++;
    d=saved;check(!open_j(&j,&d),"before new state");check(!a7_fl_worklog_prepare(&j,&c),"subsequent alternating write");
    check(!open_j(&reboot,&d)&&reboot.record[reboot.latest].generation==3,"newest work sequence");
    check(a7_fl_worklog_recognize(&reboot,0,tables[0][0],generate,0)==0,"obsolete endpoint no longer authorizes writes");cases++;
    curve_lifecycle();
    put("FILM_WORKLOG_CASES ");num(cases);put(" CHECKS ");num(checks);put("\nFILM_WORKLOG_PASSED\n");
}
#ifdef A7_WORKLOG_QEMU
void guest_main(void){tests();stop(0);}
#else
int main(void){tests();return 0;}
#endif
