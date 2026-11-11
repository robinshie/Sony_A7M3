#include "a7-fl-runtime-control.h"
#include "a7-fl-color.h"
static int generate(const struct a7_fl_control *c,const struct a7_fl_preference *p,uint8_t out[1280]) {
    A7FLColorParams controls={p->parameters[0],p->parameters[1],p->parameters[2],p->parameters[3],p->parameters[4]};
    return a7_fl_adjust_lut(c->base_fl,1280,c->expand,c->compress,&controls,out,1280);
}
static int finish(struct a7_fl_control *c,int result) {
    c->last_error=result;__atomic_store_n(&c->lock,0,__ATOMIC_RELEASE);return result;
}
static int differs(const struct a7_fl_preference *a,const struct a7_fl_preference *b) {
    if(a->enabled!=b->enabled||a->candidate_crc!=b->candidate_crc)return 1;
    for(unsigned i=0;i<8;i++)if(a->parameters[i]!=b->parameters[i])return 1;
    return 0;
}
int a7_fl_control_init(struct a7_fl_control *c,struct a7_fl_context *runtime,
                       const uint8_t base[1280],const uint16_t expand[129],const uint8_t compress[513],
                       const struct a7_fl_preference *pref,
                       int (*store)(void *,const struct a7_fl_preference *),void *storage) {
    if(!c||!runtime||!base||!expand||!compress||!pref||!store)return A7_FL_CONTROL_ARGUMENT;
    if(__atomic_exchange_n(&c->lock,1,__ATOMIC_ACQUIRE))return A7_FL_BUSY;
    if(c->initialized || !pref->generation || (pref->enabled!=0&&pref->enabled!=1) ||
       pref->parameters[5]<-3 || pref->parameters[5]>3 || pref->parameters[6]<1 ||
       pref->parameters[6]>5 || pref->parameters[7]<0 || pref->parameters[7]>9)
        return finish(c,A7_FL_CONTROL_ARGUMENT);
    c->runtime=runtime;c->base_fl=base;c->expand=expand;c->compress=compress;
    c->preference=*pref;c->committed=*pref;c->store=store;c->store_context=storage;
    uint8_t candidate[1280];
    if(generate(c,pref,candidate) || a7_fl_crc(candidate,1280)!=pref->candidate_crc ||
       a7_fl_read_status(runtime) || runtime->state!=pref->enabled)
        return finish(c,A7_FL_CONTROL_BIND);
    for(unsigned i=0;i<1280;i++)if(candidate[i]!=runtime->candidate[i])return finish(c,A7_FL_CONTROL_BIND);
    c->initialized=1;c->fault=0;c->dirty=0;return finish(c,0);
}
int a7_fl_control_apply(void *opaque,unsigned field,int value) {
    struct a7_fl_control *c=opaque;
    if(!c)return 0;
    if(__atomic_exchange_n(&c->lock,1,__ATOMIC_ACQUIRE))return 0;
    if(!c->initialized || c->fault) {finish(c,A7_FL_CONTROL_FAULT);return 0;}
    if((field>=5 && field!=8) || (field==8 && value!=0 && value!=1)) {
        finish(c,A7_FL_CONTROL_UNSUPPORTED);return 0;
    }
    if(a7_fl_read_status(c->runtime)) {c->fault=1;finish(c,c->runtime->last_error);return 0;}
    if(c->runtime->state!=c->preference.enabled) {
        c->fault=1;finish(c,A7_FL_CONTROL_BIND);return 0;
    }
    struct a7_fl_preference previous=c->committed,next=c->preference;
    if(!c->dirty && ((field==8 && next.enabled==value) || (field<5 && next.parameters[field]==value))) {
        finish(c,0);return 1;
    }
    /* Keep one generation available for a recovery-Off record. */
    if(c->committed.generation>=0xfffffffeu) {finish(c,A7_FL_CONTROL_GENERATION);return 0;}
    if(field==8)next.enabled=value;else next.parameters[field]=value;
    uint8_t generated[1280];
    if(generate(c,&next,generated)) {finish(c,A7_FL_CONTROL_ARGUMENT);return 0;}
    next.candidate_crc=a7_fl_crc(generated,1280);next.generation=c->committed.generation+1;
    if(c->store(c->store_context,&next)) {finish(c,A7_FL_CONTROL_PERSIST);return 0;}
    c->preference=next;c->committed=next;
    int error=a7_fl_replace_candidate(c->runtime,generated,next.candidate_crc);
    if(!error)error=a7_fl_set(c->runtime,next.enabled);
    if(!error) {c->dirty=0;finish(c,0);return 1;}
    /* A failed apply is visible and faults the adapter. Baseline restoration is
     * the safe failure state; no further preview is accepted until rebinding.
     * Roll preference parameters back so a rejected slider is not saved.
     */
    c->apply_error=error;c->fault=1;
    previous.generation=next.generation+1;previous.enabled=0;
    if(c->runtime->state==A7_FL_OFF && !generate(c,&previous,generated))
        (void)a7_fl_replace_candidate(c->runtime,generated,previous.candidate_crc);
    if(c->store(c->store_context,&previous)) {finish(c,A7_FL_CONTROL_RECOVERY_PERSIST);return 0;}
    c->preference=previous;c->committed=previous;c->dirty=0;finish(c,error);return 0;
}
int a7_fl_control_preview(void *opaque,unsigned field,int value) {
    struct a7_fl_control *c=opaque;if(!c)return 0;
    if(__atomic_exchange_n(&c->lock,1,__ATOMIC_ACQUIRE))return 0;
    if(!c->initialized||c->fault) {finish(c,A7_FL_CONTROL_FAULT);return 0;}
    if((field>=5&&field!=8)||(field==8&&value!=0&&value!=1)) {finish(c,A7_FL_CONTROL_UNSUPPORTED);return 0;}
    if(a7_fl_read_status(c->runtime)) {c->fault=1;finish(c,c->runtime->last_error);return 0;}
    if(c->runtime->state!=c->preference.enabled) {c->fault=1;finish(c,A7_FL_CONTROL_BIND);return 0;}
    struct a7_fl_preference next=c->preference;
    if((field==8&&next.enabled==value)||(field<5&&next.parameters[field]==value)) {finish(c,0);return 1;}
    if(field==8)next.enabled=value;else next.parameters[field]=value;
    uint8_t generated[1280];
    if(generate(c,&next,generated)) {finish(c,A7_FL_CONTROL_ARGUMENT);return 0;}
    next.candidate_crc=a7_fl_crc(generated,1280);
    int error=a7_fl_replace_candidate(c->runtime,generated,next.candidate_crc);
    if(!error)error=a7_fl_set(c->runtime,next.enabled);
    if(error) {
        c->fault=1;c->apply_error=error;
        if(c->runtime->state==A7_FL_OFF)c->preference.enabled=0;
        c->dirty=differs(&c->preference,&c->committed);finish(c,error);return 0;
    }
    c->preference=next;c->dirty=differs(&next,&c->committed);finish(c,0);return 1;
}
int a7_fl_control_commit(struct a7_fl_control *c) {
    if(!c)return A7_FL_CONTROL_ARGUMENT;
    if(__atomic_exchange_n(&c->lock,1,__ATOMIC_ACQUIRE))return A7_FL_BUSY;
    if(!c->initialized||c->fault)return finish(c,A7_FL_CONTROL_FAULT);
    if(a7_fl_read_status(c->runtime)) {c->fault=1;return finish(c,c->runtime->last_error);}
    if(c->runtime->state!=c->preference.enabled) {c->fault=1;return finish(c,A7_FL_CONTROL_BIND);}
    if(!c->dirty)return finish(c,0);
    if(c->committed.generation>=0xfffffffeu)return finish(c,A7_FL_CONTROL_GENERATION);
    struct a7_fl_preference next=c->preference;next.generation=c->committed.generation+1;
    if(c->store(c->store_context,&next))return finish(c,A7_FL_CONTROL_PERSIST);
    c->preference=next;c->committed=next;c->dirty=0;return finish(c,0);
}
int a7_fl_control_cancel(struct a7_fl_control *c) {
    if(!c)return A7_FL_CONTROL_ARGUMENT;
    if(__atomic_exchange_n(&c->lock,1,__ATOMIC_ACQUIRE))return A7_FL_BUSY;
    if(!c->initialized||c->fault)return finish(c,A7_FL_CONTROL_FAULT);
    if(!c->dirty)return finish(c,0);
    uint8_t generated[1280];
    if(generate(c,&c->committed,generated))return finish(c,A7_FL_CONTROL_BIND);
    int error=a7_fl_replace_candidate(c->runtime,generated,c->committed.candidate_crc);
    if(!error)error=a7_fl_set(c->runtime,c->committed.enabled);
    if(error) {c->fault=1;c->apply_error=error;return finish(c,error);}
    c->preference=c->committed;c->dirty=0;return finish(c,0);
}
