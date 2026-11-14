/* Fault injection for the production two-slot coordinator. */
#include <stdio.h>
#include <string.h>
#include <assert.h>
#include "../payloads/a7-fl-store.h"
/* Keep this host test independent of ARM exclusive-lock instructions. */
uint32_t a7_fl_crc(const uint8_t *p,uint32_t n) {
    uint32_t c=~0u;while(n--){c^=*p++;for(unsigned i=0;i<8;i++)c=(c>>1)^((c&1)?0xedb88320u:0);}return ~c;
}
struct disk { unsigned char data[2][129]; unsigned n[2],writes; int exists[2],fail,tear,readfail; };
static int rd(void *ctx,unsigned slot,unsigned char *out,unsigned cap,unsigned *n) {
    struct disk *d=ctx;assert(slot<2);if(d->readfail)return -1;
    if(!d->exists[slot]){*n=0;return 1;}*n=d->n[slot];assert(*n<=cap);memcpy(out,d->data[slot],*n);return 0;
}
static int wr(void *ctx,unsigned slot,const unsigned char *old,unsigned n,int existed,const unsigned char after[128]) {
    struct disk *d=ctx;assert(slot<2);if(d->fail)return -1;
    if(d->exists[slot]!=existed || (existed&&(d->n[slot]!=n || memcmp(d->data[slot],old,n))))return -2;
    d->writes++;d->exists[slot]=1;d->n[slot]=d->tear?(unsigned)d->tear:128;
    memcpy(d->data[slot],after,d->n[slot]);return d->tear?-3:0;
}
int main(void) {
    unsigned char sha[32]={7};char build[24]="37114_13.2026020901";
    struct a7_fl_preference p={.generation=1,.parameters={0,0,0,0,0,0,1,0},.candidate_crc=42},latest;
    struct disk d={0};struct a7_fl_store s;int present;
    struct a7_fl_store_io io={rd,wr,&d};
    assert(!a7_fl_store_open(&s,&io,sha,build,&latest,&present)&&!present);
    assert(!a7_fl_store_save(&s,&p)&&d.writes==1);
    assert(a7_fl_store_save(&s,&p)!=0&&d.writes==1);
    for(unsigned i=2;i<=100;i++){p.generation=i;p.parameters[0]=(int)(i%19)-9;assert(!a7_fl_store_save(&s,&p));}
    assert(!a7_fl_store_open(&s,&io,sha,build,&latest,&present)&&present&&latest.generation==100);
    struct disk good=d;
    assert(a7_fl_preference_migrate(&p)==1);assert(a7_fl_preference_migrate_three(&p)==1);p.generation=101;p.other_parameters[0]=-8;
#ifdef A7_FL_FILM_CONTROLS
    assert(a7_fl_preference_migrate_film(&p)==1);p.film[2][0]=7;p.film[2][4]=-9;
#endif
    assert(!a7_fl_store_save(&s,&p));
    assert(!a7_fl_store_open(&s,&io,sha,build,&latest,&present) && latest.schema==p.schema && latest.other_parameters[0]==-8 && latest.third_parameters[6]==3);
#ifdef A7_FL_FILM_CONTROLS
    assert(latest.film[2][0]==7&&latest.film[2][4]==-9);
#endif
    d=good;
    d.fail=1;p.generation=101;assert(a7_fl_store_save(&s,&p)!=0&&d.writes==100);d=good;
    for(int n=1;n<128;n++) {
        d=good;d.tear=n;assert(a7_fl_store_save(&s,&p)!=0);
        assert(!a7_fl_store_open(&s,&io,sha,build,&latest,&present)&&present&&latest.generation==100);
        d.tear=0;unsigned w=d.writes;assert(a7_fl_store_save(&s,&p)!=0&&d.writes==w);
    }
    d=good;d.data[0][0]^=1;assert(!a7_fl_store_open(&s,&io,sha,build,&latest,&present));
    assert(a7_fl_store_save(&s,&p)!=0);d.data[1][0]^=1;assert(a7_fl_store_open(&s,&io,sha,build,&latest,&present)!=0);
    d=good;d.readfail=1;assert(a7_fl_store_open(&s,&io,sha,build,&latest,&present)!=0);
    d=good;sha[0]^=1;assert(a7_fl_store_open(&s,&io,sha,build,&latest,&present)!=0);
    puts("NATIVE_STORE_PASSED 127 torn-write boundaries, generation guards, foreign files, read/write failures");
}
