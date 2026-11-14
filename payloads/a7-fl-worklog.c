#include "a7-fl-worklog.h"
#include "a7-fl-runtime.h"
static const uint8_t work_magic[8]={'A','7','F','L','W','0','0','1'};
static const uint8_t pref_magic[8]={'A','7','F','L','P','0','0','1'};
static void copy(void *d,const void *s,unsigned n) {
    for(unsigned i=0;i<n;i++)((uint8_t *)d)[i]=((const uint8_t *)s)[i];
}
static int equal(const void *a,const void *b,unsigned n) {
    for(unsigned i=0;i<n;i++)if(((const uint8_t *)a)[i]!=((const uint8_t *)b)[i])return 0;
    return 1;
}
static uint32_t get(const uint8_t *p) {
    return p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;
}
static void put(uint8_t *p,uint32_t v) {
    for(unsigned i=0;i<4;i++)p[i]=(uint8_t)(v>>(8*i));
}
static int encode(const struct a7_fl_worklog *j,const struct a7_fl_preference *p,uint8_t out[128]) {
    if(p->schema!=4||a7_fl_preference_encode(out,p,j->original_sha,j->build))return -1;
    copy(out,work_magic,8);put(out+124,a7_fl_crc(out,124));return 0;
}
static int decode(const struct a7_fl_worklog *j,struct a7_fl_preference *p,const uint8_t *raw,unsigned n) {
    if(n!=128||!equal(raw,work_magic,8)||get(raw+124)!=a7_fl_crc(raw,124))return -1;
    uint8_t next[128];copy(next,raw,128);copy(next,pref_magic,8);put(next+124,a7_fl_crc(next,124));
    if(a7_fl_preference_decode(p,next,128,j->original_sha,j->build)||p->schema!=4)return -1;
    return 0;
}
static int load(struct a7_fl_worklog *j) {
    j->latest=-1;
    for(unsigned i=0;i<2;i++) {
        j->length[i]=0;j->valid[i]=j->exists[i]=0;
        int rc=j->io.read(j->io.opaque,i,j->raw[i],129,&j->length[i]);
        if(rc<0||rc>1||j->length[i]>129||(rc==1&&j->length[i]))return A7_FL_WORKLOG_READ;
        j->exists[i]=rc==0;
        if(rc==0)j->valid[i]=decode(j,&j->record[i],j->raw[i],j->length[i])==0;
        if(j->valid[i]&&(j->latest<0||j->record[i].generation>j->record[j->latest].generation))j->latest=(int)i;
    }
    if(j->latest<0&&(j->exists[0]||j->exists[1]))return A7_FL_WORKLOG_UNKNOWN;
    if(j->valid[0]&&j->valid[1]) {
        uint32_t a=j->record[j->latest].generation,b=j->record[1-j->latest].generation;
        if(a-b!=1)return A7_FL_WORKLOG_HISTORY;
    }
    return 0;
}
int a7_fl_worklog_open(struct a7_fl_worklog *j,const struct a7_fl_store_io *io,
                       const uint8_t original_sha[32],const char build[24]) {
    if(!j||!io||!io->read||!io->replace||!original_sha||!build)return A7_FL_WORKLOG_ARGUMENT;
    j->initialized=0;j->fault=0;j->io=*io;
    copy(j->original_sha,original_sha,32);copy(j->build,build,24);
    int rc=load(j);if(rc)return rc;j->initialized=1;return 0;
}
int a7_fl_worklog_prepare(struct a7_fl_worklog *j,const struct a7_fl_preference *p) {
    if(!j||!p)return A7_FL_WORKLOG_ARGUMENT;
    if(!j->initialized||j->fault)return A7_FL_WORKLOG_FAULT;
    struct a7_fl_worklog observed=*j;
    int rc=load(&observed);if(rc){j->fault=1;return rc;}
    for(unsigned i=0;i<2;i++) {
        if(observed.exists[i]!=j->exists[i]||observed.length[i]!=j->length[i]||
           !equal(observed.raw[i],j->raw[i],j->length[i])) {
            j->fault=1;return A7_FL_WORKLOG_CHANGED;
        }
        if(observed.exists[i]&&!observed.valid[i])return A7_FL_WORKLOG_UNKNOWN;
    }
    struct a7_fl_preference next=*p;
    next.generation=j->latest<0?1:j->record[j->latest].generation;
    uint8_t record[128];
    if(encode(j,&next,record))return A7_FL_WORKLOG_ARGUMENT;
    if(j->latest>=0&&equal(record,j->raw[j->latest],128))return 0;
    if(j->latest>=0) {
        if(next.generation==0xffffffffu)return A7_FL_WORKLOG_EXHAUSTED;
        next.generation++;if(encode(j,&next,record))return A7_FL_WORKLOG_ARGUMENT;
    }
    unsigned target=j->latest<0?0u:(unsigned)(1-j->latest);
    rc=j->io.replace(j->io.opaque,target,j->raw[target],j->length[target],j->exists[target],record);
    if(rc){j->fault=1;return A7_FL_WORKLOG_WRITE;}
    observed=*j;
    if(load(&observed)||observed.latest!=(int)target||observed.length[target]!=128||
       !equal(record,observed.raw[target],128)) {j->fault=1;return A7_FL_WORKLOG_READBACK;}
    unsigned other=1-target;
    if(observed.exists[other]!=j->exists[other]||observed.length[other]!=j->length[other]||
       !equal(observed.raw[other],j->raw[other],j->length[other])) {
        j->fault=1;return A7_FL_WORKLOG_CHANGED;
    }
    *j=observed;return 0;
}
int a7_fl_worklog_recognize(const struct a7_fl_worklog *j,unsigned table,const uint8_t actual[1280],
                           int (*generate)(void *,const struct a7_fl_preference *,unsigned,uint8_t[1280]),void *ctx) {
    if(!j||!j->initialized||j->fault||table>2||!actual||!generate)return A7_FL_WORKLOG_ARGUMENT;
    uint8_t candidate[1280];
    for(unsigned i=0;i<2;i++)if(j->valid[i]&&j->record[i].enabled) {
        if(generate(ctx,&j->record[i],0,candidate)||
           a7_fl_crc(candidate,1280)!=j->record[i].candidate_crc)return A7_FL_WORKLOG_ARGUMENT;
        if(table&&generate(ctx,&j->record[i],table,candidate))return A7_FL_WORKLOG_ARGUMENT;
        if(equal(candidate,actual,1280))return 1;
    }
    return 0;
}
static int valid_curve_io(const struct a7_fl_worklog *j,const struct a7_fl_curve_io *io){
    return j&&j->initialized&&!j->fault&&io&&io->generate&&io->read&&io->write&&io->scratch;
}
static int curve_tables(const struct a7_fl_curve_io *io,const struct a7_fl_preference *p,
                        uint8_t tables[3][1280]){
    if(!p||p->schema!=4)return -1;
    for(unsigned t=0;t<3;t++)if(io->generate(io->opaque,p,t,tables[t]))return -1;
    if(p->enabled&&a7_fl_crc(tables[0],1280)!=p->candidate_crc)return -1;
    return 0;
}
int a7_fl_curve_verify(const struct a7_fl_curve_io *io,const struct a7_fl_preference *p){
    if(!io||!io->read||!io->generate||!io->scratch)return A7_FL_WORKLOG_ARGUMENT;
    uint8_t (*expected)[1280]=io->scratch->target,*actual=io->scratch->row;
    if(curve_tables(io,p,expected))return A7_FL_WORKLOG_ARGUMENT;
    for(unsigned t=0;t<3;t++){
        if(io->read(io->opaque,t,actual))return A7_FL_WORKLOG_READ;
        if(!equal(actual,expected[t],1280))return A7_FL_WORKLOG_CHANGED;
    }
    return 0;
}
static int write_curve_tables(struct a7_fl_worklog *j,const struct a7_fl_curve_io *io,
            uint8_t before[3][1280],uint8_t target[3][1280]){
    uint8_t *scratch=io->scratch->row;
    for(unsigned t=0;t<3;t++){
        if(!equal(before[t],target[t],1280)&&io->write(io->opaque,t,before[t],target[t])){
            j->fault=1;return A7_FL_WORKLOG_WRITE;
        }
    }
    for(unsigned t=0;t<3;t++)if(io->read(io->opaque,t,scratch)||!equal(scratch,target[t],1280)){
        j->fault=1;return A7_FL_WORKLOG_READBACK;
    }
    return 0;
}
int a7_fl_curve_recover(struct a7_fl_worklog *j,const struct a7_fl_curve_io *io,
                        const struct a7_fl_preference *committed){
    if(!valid_curve_io(j,io))return A7_FL_WORKLOG_ARGUMENT;
    uint8_t (*actual)[1280]=io->scratch->before,(*target)[1280]=io->scratch->target;
    uint8_t *stock=io->scratch->row;
    if(curve_tables(io,committed,target))return A7_FL_WORKLOG_ARGUMENT;
    struct a7_fl_preference off=*committed;a7_fl_preference_switch(&off,0);
    for(unsigned t=0;t<3;t++){
        if(io->read(io->opaque,t,actual[t]))return A7_FL_WORKLOG_READ;
        if(equal(actual[t],target[t],1280))continue;
        if(io->generate(io->opaque,&off,t,stock))return A7_FL_WORKLOG_ARGUMENT;
        if(equal(actual[t],stock,1280))continue;
        if(a7_fl_worklog_recognize(j,t,actual[t],io->generate,io->opaque)!=1)
            return A7_FL_WORKLOG_UNKNOWN;
    }
    return write_curve_tables(j,io,actual,target);
}
int a7_fl_curve_transition(struct a7_fl_worklog *j,const struct a7_fl_curve_io *io,
        const struct a7_fl_preference *before,const struct a7_fl_preference *next){
    if(!valid_curve_io(j,io))return A7_FL_WORKLOG_ARGUMENT;
    uint8_t (*prior)[1280]=io->scratch->before,(*after)[1280]=io->scratch->target;
    uint8_t *scratch=io->scratch->row;
    if(curve_tables(io,before,prior)||curve_tables(io,next,after))return A7_FL_WORKLOG_ARGUMENT;
    for(unsigned t=0;t<3;t++){
        if(io->read(io->opaque,t,scratch))return A7_FL_WORKLOG_READ;
        if(!equal(scratch,prior[t],1280))return A7_FL_WORKLOG_CHANGED;
    }
    /* Before advancing the two-slot log, keep an exact description of the
     * current tables as well as the destination, including on first use. */
    int rc=a7_fl_worklog_prepare(j,before);
    if(!rc)rc=a7_fl_worklog_prepare(j,next);
    if(rc)return rc;
    return write_curve_tables(j,io,prior,after);
}
