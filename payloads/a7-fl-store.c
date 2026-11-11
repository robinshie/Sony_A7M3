#include "a7-fl-store.h"
static void copy(void *a,const void *b,unsigned n) {
    unsigned char *d=a; const unsigned char *s=b; while(n--) *d++=*s++;
}
static int equal(const void *a,const void *b,unsigned n) {
    const unsigned char *x=a,*y=b; while(n--) if(*x++!=*y++) return 0; return 1;
}
struct slots { unsigned char bytes[2][129]; unsigned length[2]; int exists[2],invalid[2],chosen; };
static int load(struct a7_fl_store *s,struct slots *r,struct a7_fl_preference *latest) {
    for(unsigned i=0;i<2;i++) {
        r->length[i]=0;
        int rc=s->io.read(s->io.opaque,i,r->bytes[i],129,&r->length[i]);
        if(rc<0 || rc>1) return -1;
        r->exists[i]=!rc;r->invalid[i]=0;
        if(rc) { if(r->length[i]) return -2; }
        else {
            struct a7_fl_preference p;
            r->invalid[i]=a7_fl_preference_decode(&p,r->bytes[i],r->length[i],s->original_sha,s->build)!=0;
        }
    }
    r->chosen=a7_fl_preference_choose(latest,r->bytes[0],r->length[0],r->bytes[1],r->length[1],s->original_sha,s->build);
    if(r->chosen==-2 || (r->chosen<0 && (r->exists[0]||r->exists[1]))) return -4;
    return 0;
}
int a7_fl_store_open(struct a7_fl_store *s,const struct a7_fl_store_io *io,
                    const unsigned char sha[32],const char build[24],
                    struct a7_fl_preference *latest,int *present) {
    if(!s || !io || !io->read || !io->replace || !sha || !build || !latest || !present) return -1;
    s->initialized=0; s->io=*io;copy(s->original_sha,sha,32);copy(s->build,build,24);
    struct slots r;
    int rc=load(s,&r,latest);if(rc) return rc;
    *present=r.chosen>=0;s->initialized=1;return 0;
}
int a7_fl_store_save(void *opaque,const struct a7_fl_preference *p) {
    struct a7_fl_store *s=opaque;
    if(!s || !s->initialized || !p) return -1;
    struct slots before,after;struct a7_fl_preference latest,verified;
    if(load(s,&before,&latest)) return -2;
    if(before.chosen<0 ? p->generation!=1 :
       (latest.generation==0xffffffffu || p->generation!=latest.generation+1)) return -3;
    unsigned char encoded[128];
    if(a7_fl_preference_encode(encoded,p,s->original_sha,s->build)) return -4;
    unsigned target=before.chosen<0?0u:(unsigned)(1-before.chosen);
    if(before.invalid[target]) return -7;
    if(s->io.replace(s->io.opaque,target,before.bytes[target],before.length[target],
                     before.exists[target],encoded)) return -5;
    if(load(s,&after,&verified) || after.chosen!=(int)target || after.length[target]!=128 ||
       !equal(encoded,after.bytes[target],128)) return -6;
    return 0;
}
