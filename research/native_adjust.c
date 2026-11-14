#include "native_adjust.h"

typedef void *(*Ctor)(NativeAdjustNode *, NativeAdjustNode **, int,
                      const NativeAdjustProperties *);
typedef int (*Init)(NativeAdjustNode *, NativeAdjustNode **, int);
typedef int (*Select)(NativeAdjustNode *, int);
typedef int (*Gray)(NativeAdjustNode *, int, int);
typedef NativeAdjustNode *(*Clone)(NativeAdjustNode *);
typedef int (*DeepInit)(NativeAdjustNode *,NativeAdjustNode **,int,int);
typedef int (*GetInt)(NativeAdjustNode *,int,int *);

static void zero(void *p, unsigned n) {
    unsigned char *b=p;
    while(n--) *b++=0;
}
static void prop(NativeAdjustProperty *p,int key,int type,uint32_t value) {
    p->key=key;p->type=type;p->value=value;
}
/* A parent may own its pointer array, but it does not own this tree's embedded
 * nodes. Clearing parent prevents dangling ancestry when an original view dies.
 * Clone hooks retain stock owning destructors on allocated copies.
 */
static NativeAdjustNode *embedded_destroy(NativeAdjustNode *node) {
    node->parent=0;return node;
}
static NativeAdjustTree *owner(NativeAdjustNode *node) {
    return (NativeAdjustTree *)node->vtable[65];
}
static NativeAdjustNode *owned_clone(NativeAdjustNode *node) {
    NativeAdjustTree *t=owner(node);
    NativeAdjustNode *copy=((Clone)(t->caution_base+0x683369))(node);
    if(copy) copy->vtable=t->clone_vtable+2;
    return copy;
}
static int initialize(NativeAdjustNode *node,NativeAdjustNode **aliases,int count,int depth) {
    NativeAdjustTree *t=owner(node);
    int rc=((DeepInit)(t->caution_base+0x6830ab))(node,aliases,count,depth);
    int process_id=0;
    if(rc && ((GetInt)(t->caution_base+0x683297))(node,0xe,&process_id)) {
        unsigned field=native_adjust_field_index(process_id);
        if(field<NATIVE_ADJUST_FIELDS) {
            rc=((Gray)(t->caution_base+0x682edb))(node,!(t->enabled_mask&(1u<<field)),0);
            if(rc)rc=((Select)(t->caution_base+0x682e59))(node,t->specs[field].maximum-t->current[field]+1);
        } else if(process_id==0x7000)
            rc=((Select)(t->caution_base+0x682e59))(node,t->current_mode+1);
    }
    return rc;
}
static void construct(NativeAdjustTree *t,NativeAdjustNode *n,NativeAdjustNode **children,
                      int count,const NativeAdjustProperties *properties) {
    ((Ctor)(t->caution_base+0x68338d))(n,children,count,properties);
    n->vtable=t->node_vtable+2;
}
uint32_t native_adjust_number_resid(int value) {
    if(value < -15 || value > 15) return 0;
    return value ? (uint32_t)(0x0204e7ad+value) : 0x0204e39c;
}
#ifdef A7_FL_FILM_CONTROLS
int native_adjust_curve_specs(NativeAdjustSpec specs[NATIVE_ADJUST_FIELDS],const int8_t points[5]){
    if(!specs||!points)return 0;
    for(unsigned i=0;i<5;i++)if(points[i]<-9||points[i]>9)return 0;
    for(unsigned i=0;i<5;i++)
        specs[NATIVE_ADJUST_BASE_FIELDS+i]=(NativeAdjustSpec){NATIVE_ADJUST_CURVE_TITLE_FIRST+i,0,-9,9,points[i]};
    return 1;
}
#endif
int native_adjust_build(NativeAdjustTree *t,uintptr_t base,uint32_t title,uint32_t help,uint32_t fl_title,
                        const NativeAdjustSpec specs[NATIVE_ADJUST_FIELDS],unsigned enabled) {
    if(!t || !specs || !title || !fl_title || enabled>>NATIVE_ADJUST_FIELDS) return 0;
    for(unsigned f=0;f<NATIVE_ADJUST_FIELDS;f++) {
        const NativeAdjustSpec *s=&specs[f];
        if(!s->title || s->minimum < -15 || s->maximum > 15 ||
           s->minimum>s->maximum || s->initial<s->minimum || s->initial>s->maximum)
            return 0;
    }
    zero(t,sizeof *t);t->caution_base=base;t->enabled_mask=enabled;
    const uintptr_t *native_vtable=(const uintptr_t *)(base+0x918ec0);
    for(unsigned i=0;i<67;i++) t->node_vtable[i]=t->clone_vtable[i]=native_vtable[i];
    t->node_vtable[2]=t->node_vtable[3]=(uintptr_t)embedded_destroy;
    t->node_vtable[2+0xe4/4]=t->clone_vtable[2+0xe4/4]=(uintptr_t)owned_clone;
    t->node_vtable[2+0xf8/4]=t->clone_vtable[2+0xf8/4]=(uintptr_t)initialize;
    t->node_vtable[67]=t->clone_vtable[67]=(uintptr_t)t;
    for(unsigned j=0;j<2;j++) {
        NativeAdjustProperty *p=t->mode_value_props[j];
        prop(p+0,0,0,j?fl_title:0x0204e0d2);prop(p+1,6,0,help);
        prop(p+2,0xb,1,0);prop(p+3,0xc,1,1);prop(p+4,0xf,1,j);prop(p+5,0x10,1,j);
        t->mode_value_properties[j]=(NativeAdjustProperties){p,5};
        construct(t,&t->mode_values[j],0,0,&t->mode_value_properties[j]);
        t->mode_ptrs[j]=&t->mode_values[j];
    }
    prop(t->mode_props+0,0,0,title);prop(t->mode_props+1,6,0,help);
    prop(t->mode_props+2,0xb,1,2);prop(t->mode_props+3,0xc,1,0);
    prop(t->mode_props+4,0xe,1,0x7000);
    t->mode_properties=(NativeAdjustProperties){t->mode_props,4};
    construct(t,&t->mode,t->mode_ptrs,2,&t->mode_properties);
    t->field_ptrs[0]=&t->mode;
    for(unsigned f=0;f<NATIVE_ADJUST_FIELDS;f++) {
        const NativeAdjustSpec *s=&specs[f];t->specs[f]=*s;t->current[f]=s->initial;
        unsigned count=(unsigned)(s->maximum-s->minimum+1);
        for(unsigned j=0;j<count;j++) {
            /* Original PP lists descend from positive to negative. */
            int value=s->maximum-(int)j;
            NativeAdjustProperty *p=t->value_props[f][j];
            prop(p+0,0,0,native_adjust_number_resid(value));prop(p+1,6,0,s->help);
            prop(p+2,0xb,1,0);prop(p+3,0xc,1,1);
            /* Signed -1 is a missing-value sentinel in SettingMenu. Labels
             * retain signed numbers; process values use nonnegative enums. */
            prop(p+4,0xf,1,(uint32_t)(value-s->minimum));prop(p+5,0x10,1,(uint32_t)(value-s->minimum));
            t->value_properties[f][j]=(NativeAdjustProperties){p,5};
            construct(t,&t->values[f][j],0,0,&t->value_properties[f][j]);
            t->value_ptrs[f][j]=&t->values[f][j];
        }
        NativeAdjustProperty *p=t->field_props[f];
        prop(p+0,0,0,s->title);prop(p+1,6,0,s->help);prop(p+2,0xb,1,2);
        prop(p+3,0xc,1,0);prop(p+4,0xe,1,native_adjust_field_id(f));
        t->field_properties[f]=(NativeAdjustProperties){p,4};
        construct(t,&t->fields[f],t->value_ptrs[f],(int)count,&t->field_properties[f]);
        t->field_ptrs[f+1]=&t->fields[f];
    }
    prop(t->root_props+0,0,0,title);prop(t->root_props+1,6,0,help);
    prop(t->root_props+2,0xb,1,2);prop(t->root_props+3,0xc,1,3);
    t->root_properties=(NativeAdjustProperties){t->root_props,3};
    prop(t->page_props,0xb,1,0);
    t->page_properties=(NativeAdjustProperties){t->page_props,0};
    for(unsigned p=0;p<NATIVE_ADJUST_PAGES;p++) {
        unsigned remaining=NATIVE_ADJUST_FIELDS+1-p*6;
        construct(t,&t->pages[p],t->field_ptrs+p*6,remaining>6?6:(int)remaining,&t->page_properties);
        t->page_ptrs[p]=&t->pages[p];
    }
    construct(t,&t->root,t->page_ptrs,NATIVE_ADJUST_PAGES,&t->root_properties);
    if(!((Init)(base+0x682869))(&t->root,0,0)) return 0;
    for(unsigned f=0;f<NATIVE_ADJUST_FIELDS;f++) {
        if(!((Select)(base+0x682e59))(&t->fields[f],specs[f].maximum-specs[f].initial+1))
            return 0;
        if(!(enabled&(1u<<f)))
            if(!((Gray)(base+0x682edb))(&t->fields[f],1,0)) return 0;
    }
    return 1;
}
int native_adjust_add_look(NativeAdjustTree *t,uint32_t title) {
    if(!t || !title || t->root.parent || (t->mode.count<2||t->mode.count>=NATIVE_ADJUST_MODES) ||
       t->mode.children!=t->mode_ptrs || t->mode.vtable!=t->node_vtable+2) return 0;
    unsigned index=(unsigned)t->mode.count;
    NativeAdjustProperty *p=t->mode_value_props[index];
    for(unsigned i=0;i<6;i++)p[i]=t->mode_value_props[1][i];
    p[0].value=title;p[4].value=p[5].value=index;
    t->mode_value_properties[index]=(NativeAdjustProperties){p,5};
    construct(t,&t->mode_values[index],0,0,&t->mode_value_properties[index]);
    t->mode_ptrs[index]=&t->mode_values[index];t->mode.count=(int)index+1;
    return 1; /* The subsequent Save append deep-initializes all children. */
}
int native_adjust_add_save(NativeAdjustTree *t,uint32_t title) {
    if(!t || !title || t->root.parent || t->root.count!=NATIVE_ADJUST_PAGES ||
       t->pages[NATIVE_ADJUST_PAGES-1].count!=NATIVE_ADJUST_FIELDS+1-6*(NATIVE_ADJUST_PAGES-1) ||
       t->root.children!=t->page_ptrs || t->root.vtable!=t->node_vtable+2) return 0;
    NativeAdjustProperty *p=t->save_props;
    prop(p+0,0,0,title);prop(p+1,6,0,0);prop(p+2,0xb,1,2);
    prop(p+3,0xc,1,4);prop(p+4,0xe,1,NATIVE_ADJUST_SAVE_ID);
    t->save_properties=(NativeAdjustProperties){p,4};
    construct(t,&t->save,0,0,&t->save_properties);
    t->field_ptrs[NATIVE_ADJUST_FIELDS+1]=&t->save;
    t->pages[NATIVE_ADJUST_PAGES-1].count++;
    if(!initialize(&t->root,0,0,t->root.depth)) return 0;
    if(!((Select)(t->caution_base+0x682e59))(&t->mode,t->current_mode+1)) return 0;
    for(unsigned f=0;f<NATIVE_ADJUST_FIELDS;f++)
        if(!((Select)(t->caution_base+0x682e59))(&t->fields[f],
                                            t->specs[f].maximum-t->current[f]+1)) return 0;
    return 1;
}
int native_adjust_save_title(NativeAdjustTree*t,uint32_t title) {
    if(!t||!title||t->save.properties!=&t->save_properties||
       t->save_properties.list!=t->save_props||t->save_properties.last!=4||
       t->save_props[0].key!=0||t->save_props[4].value!=NATIVE_ADJUST_SAVE_ID)return 0;
    t->save_props[0].value=title;return 1;
}
int native_adjust_encode(const NativeAdjustTree*t,int id,int value,int*out) {
    if(!t||!out)return 0;
    if(id==0x7000) {if(value<0||value>=t->mode.count)return 0;*out=value;return 1;}
    unsigned f=native_adjust_field_index(id);if(f>=NATIVE_ADJUST_FIELDS)return 0;
    if(value<t->specs[f].minimum||value>t->specs[f].maximum)return 0;
    *out=value-t->specs[f].minimum;return 1;
}
int native_adjust_decode(const NativeAdjustTree*t,int id,int encoded,int*out) {
    if(!t||!out)return 0;
    if(id==0x7000) {if(encoded<0||encoded>=t->mode.count)return 0;*out=encoded;return 1;}
    unsigned f=native_adjust_field_index(id);if(f>=NATIVE_ADJUST_FIELDS)return 0;
    if(encoded<0||encoded>t->specs[f].maximum-t->specs[f].minimum)return 0;
    *out=encoded+t->specs[f].minimum;return 1;
}
int native_adjust_read(const NativeAdjustTree *t,int process_id,int *value) {
    if(t && value && process_id==0x7000) {*value=t->current_mode;return 1;}
    unsigned f=native_adjust_field_index(process_id);
    if(!t || !value || f>=NATIVE_ADJUST_FIELDS) return 0;
    *value=t->current[f];return 1;
}
int native_adjust_write(NativeAdjustTree *t,int process_id,int value,
                        int (*apply)(void *,unsigned,int),void *ctx) {
    if(process_id==0x7000) {
        if(!t || !apply || value<0 || value>=t->mode.count) return 0;
        if(value==t->current_mode)
            return ((Select)(t->caution_base+0x682e59))(&t->mode,value+1);
        if(!apply(ctx,NA_MODE,value)) return 0;
        t->current_mode=value;
        return ((Select)(t->caution_base+0x682e59))(&t->mode,value+1);
    }
    unsigned f=native_adjust_field_index(process_id);
    if(!t || f>=NATIVE_ADJUST_FIELDS || !(t->enabled_mask&(1u<<f)) || !apply) return 0;
    if(value<t->specs[f].minimum || value>t->specs[f].maximum) return 0;
    if(value==t->current[f])
        return ((Select)(t->caution_base+0x682e59))(&t->fields[f],t->specs[f].maximum-value+1);
    if(!apply(ctx,f,value)) return 0;
    t->current[f]=value;
    return ((Select)(t->caution_base+0x682e59))(&t->fields[f],t->specs[f].maximum-value+1);
}
