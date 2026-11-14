/* Original Sony generic nodes + our adapter. Backend calls are recording mocks. */
#include "native_adjust.h"
_Static_assert(sizeof(NativeAdjustNode)==40,"ARM native node ABI");
_Static_assert(sizeof(NativeAdjustProperties)==8,"ARM native properties ABI");
static NativeAdjustTree tree;
static unsigned heap[16384],used,checks,backend_calls,last_field;
static void *allocations[1024];
static unsigned nalloc,nfree;
static int last_value,backend_ok;
static void put(const char *s) {
    volatile unsigned *uart=(volatile unsigned *)0x10009000;
    while(*s) {while(uart[6]&32) {} uart[0]=*s++;}
}
static void number(unsigned n) {char b[12];unsigned i=0;do {b[i++]='0'+n%10;n/=10;}while(n);while(i){char c[2]={b[--i],0};put(c);}}
static void finish(void) {
    register unsigned r0 __asm__("r0")=0x18,r1 __asm__("r1")=0x20026;
    __asm__ volatile("svc 0xab" : "+r"(r0),"+r"(r1) : : "memory");while(1) {}
}
void unexpected(void) {put("FAIL unexpected original dependency\n");finish();}
void *allocate(unsigned n) {
    unsigned words=(n+3)/4;if(!words)words=1;
    if(used+words>16384||nalloc>=1024)unexpected();
    void *p=heap+used;used+=words;allocations[nalloc++]=p;return p;
}
void release(void *p) {
    if(!p)return;
    for(unsigned i=0;i<nalloc;i++)if(allocations[i]==p){allocations[i]=0;nfree++;return;}
    put("FAIL release of unowned pointer or double free\n");finish();
}
static void check(int condition,const char *name) {checks++;if(!condition){put("FAIL ");put(name);put("\n");finish();}}
static int backend(void *context,unsigned field,int value) {
    check(context==&tree,"backend context");backend_calls++;last_field=field;last_value=value;return backend_ok;
}
typedef int (*GetInt)(NativeAdjustNode *,int,int *);
typedef int (*GetCount)(NativeAdjustNode *,int *);
typedef int (*GetSelected)(NativeAdjustNode *,NativeAdjustNode **);
typedef int (*GetGray)(NativeAdjustNode *,unsigned char *);
typedef int (*SelectDiff)(NativeAdjustNode *,int);
typedef int (*Select)(NativeAdjustNode *,int);
typedef NativeAdjustNode *(*Clone)(NativeAdjustNode *);
typedef NativeAdjustNode *(*Destroy)(NativeAdjustNode *);
typedef void *(*Ctor)(NativeAdjustNode *,NativeAdjustNode **,int,const NativeAdjustProperties *);
typedef int (*Init)(NativeAdjustNode *,NativeAdjustNode **,int);
static int get(NativeAdjustNode *node,int key) {
    int value=0;check(((GetInt)0x683297)(node,key,&value),"original property lookup");return value;
}
static NativeAdjustNode *field_node(NativeAdjustNode *root,unsigned index) {
    return root->children[index/6]->children[index%6];
}
/* Actual PAS_SelectListTab layer-one consumer, with rendering setters modeled.
 * It reads original node vtables to derive page/row counts and selected rows. */
static unsigned char widget[0x16000];
static int widget_pages,widget_rows,widget_page,widget_row,widget_refresh;
void widget_set_pages(void*p,int n){check(p==widget,"page setter context");widget_pages=n;}
void widget_set_rows(void*p,int n){check(p==widget,"row setter context");widget_rows=n;}
void widget_set_page(void*p,int n){check(p==widget,"selected page context");widget_page=n;}
void widget_set_row(void*p,int n){check(p==widget,"selected row context");widget_row=n;}
int widget_has_subcursor(void*p){check(p==widget,"subcursor context");return 1;}
void widget_render(void*p){check(p==widget,"render context");widget_refresh++;}
static void widget_check(NativeAdjustNode*root,int pages,int rows,int page,int row) {
    for(unsigned i=0;i<sizeof widget;i++)widget[i]=0;
    *(unsigned*)(widget+0x1cc)=1;widget_pages=widget_rows=widget_page=widget_row=-99;widget_refresh=0;
    check(((int(*)(void*,void*))0x5741bd)(widget,root)==1,"original widget initializes list");
    check(widget_pages==pages&&widget_rows==rows&&widget_page==page&&widget_row==row&&widget_refresh==1,
          "original widget consumes exact page and row structure");
}
void guest_main(void) {
    NativeAdjustSpec specs[NATIVE_ADJUST_FIELDS];
    for(unsigned f=0;f<NATIVE_ADJUST_FIELDS;f++) specs[f]=(NativeAdjustSpec){0x7f000010+f,0,-9,9,0};
    specs[3].minimum=0;specs[5].minimum=-3;specs[5].maximum=3;
    specs[6].minimum=0;specs[6].maximum=4;specs[7].minimum=0;specs[7].maximum=9;
#ifdef A7_FL_FILM_CONTROLS
    static const int8_t saved_points[]={9,-6,3,0,-9};
    check(native_adjust_curve_specs(specs,saved_points),"set five curve specs from saved bank");
    check(native_adjust_build(&tree,0,0x7f000001,0,0x7f000002,specs,0x1fff),"build film menu");
    check(native_adjust_add_look(&tree,0x7f000003)&&native_adjust_add_look(&tree,0x7f000004),"add FL2 and FL3");
    check(native_adjust_add_save(&tree,0x0204eaab),"add film Save");
    check(tree.root.count==3&&tree.pages[0].count==6&&tree.pages[1].count==6&&tree.pages[2].count==3,"film page sizes");
    backend_ok=1;
    check(native_adjust_write(&tree,0x7000,3,backend,&tree)&&last_field==NA_MODE,"select FL3");
    for(unsigned f=8;f<13;f++) {
        int id=native_adjust_field_id(f),encoded=-1,value=0;
        NativeAdjustNode *node=field_node(&tree.root,f+1),*leaf=0;
        check(get(node,0xe)==id&&id!=NATIVE_ADJUST_SAVE_ID&&node->parent==&tree.pages[(f+1)/6],"curve ID and native ancestry");
        check(get(node,0)==(int)(NATIVE_ADJUST_CURVE_TITLE_FIRST+f-8),"curve resolves dedicated label ID");
        check(((GetSelected)0x682951)(node,&leaf)&&get(leaf,0x10)==saved_points[f-8]+9,"saved curve restores initial cursor");
        check(native_adjust_encode(&tree,id,-1,&encoded)&&encoded==8&&
              native_adjust_decode(&tree,id,encoded,&value)&&value==-1,"curve enum round trip");
        check(native_adjust_write(&tree,id,-1,backend,&tree)&&last_field==f&&last_value==-1,"curve dispatch");
        check(((GetSelected)0x682951)(node,&leaf)&&get(leaf,0x10)==8,"curve cursor selects negative value");
    }
    check(!native_adjust_write(&tree,NATIVE_ADJUST_SAVE_ID,0,backend,&tree),"Save cannot hit a curve field");
    check(tree.save.parent==&tree.pages[2]&&get(&tree.save,0xe)==NATIVE_ADJUST_SAVE_ID,"Save after all curves");
    for(int p=0;p<3;p++){
        int rows=p==2?3:6;
        check(((Select)0x682e59)(&tree.root,p+1)&&((Select)0x682e59)(&tree.pages[p],rows),"select last row on each page");
        widget_check(&tree.root,3,rows,p+1,rows-1);
    }
    put("NATIVE_ADJUST_TESTS_PASSED: three film pages and all five curve fields\n");finish();
#endif
    check(native_adjust_build(&tree,0,0x7f000001,0,0x7f000002,specs,0x3f),"build original graph");
    check(used==0,"unique graph requires no clone/allocation");
    int count=0;check(((GetCount)0x68289f)(&tree.root,&count)&&count==2,"two root pages");
    check(tree.pages[0].count==6&&tree.pages[1].count==3&&get(&tree.pages[0],0xb)==0,"native page wrappers before Save");
    check(get(&tree.root,0xc)==3,"root generic group kind");
    check(get(&tree.mode,0xe)==0x7000,"mode process id");
    check(get(&tree.mode_values[0],0)==0x0204e0d2,"stock Off label");
    check(get(&tree.mode_values[1],0)==0x7f000002,"custom FL label");
    NativeAdjustNode *selected=0;
    check(((GetSelected)0x682951)(&tree.root,&selected)&&selected==&tree.pages[0],"initial first page focus");
    check(((GetSelected)0x682951)(selected,&selected)&&selected==&tree.mode,"initial mode row focus");
    widget_check(&tree.root,2,6,1,0);
    NativeAdjustNode old_flat=tree.root;old_flat.children=tree.field_ptrs;old_flat.count=9;
    widget_check(&old_flat,9,2,1,0); /* reproduces old fields-as-pages bug */
    for(unsigned f=0;f<8;f++) {
        check(get(&tree.fields[f],0xe)==(int)(0x7001+f),"isolated field process id");
        check(tree.fields[f].parent==&tree.pages[(f+1)/6],"original page parent linkage");
        check(((GetSelected)0x682951)(&tree.fields[f],&selected),"initial scalar selection");
        check(get(selected,0x10)==specs[f].initial-specs[f].minimum,"initial scalar enum");
        unsigned char gray=0;check(((GetGray)0x682d0b)(&tree.fields[f],&gray)==(f>=6),"original grayout state");
        for(int v=specs[f].minimum;v<=specs[f].maximum;v++) {
            NativeAdjustNode *n=&tree.values[f][specs[f].maximum-v];
            int encoded=-99,decoded=-99;
            check(native_adjust_encode(&tree,0x7001+(int)f,v,&encoded)&&encoded>=0&&
                  native_adjust_decode(&tree,0x7001+(int)f,encoded,&decoded)&&decoded==v,"signed backend enum roundtrip");
            check(get(n,0xf)==encoded&&get(n,0x10)==encoded,"nonnegative native option enums");
            check((uint32_t)get(n,0)==native_adjust_number_resid(v),"stock numeric labels");
        }
    }
    backend_ok=1;
    for(unsigned f=0;f<6;f++) for(int value=specs[f].minimum;value<=specs[f].maximum;value++) {
        check(native_adjust_write(&tree,(int)(0x7001+f),value,backend,&tree),"accepted scalar update");
        int read=0;check(native_adjust_read(&tree,(int)(0x7001+f),&read)&&read==value,"read accepted scalar");
        check(((GetSelected)0x682951)(&tree.fields[f],&selected)&&get(selected,0x10)==value-specs[f].minimum,"original cursor tracks accepted enum");
    }
    unsigned before=backend_calls;
    check(!native_adjust_write(&tree,0x7007,1,backend,&tree),"range unsupported rejects");
    check(!native_adjust_write(&tree,0x7008,1,backend,&tree),"clarity unsupported rejects");
    check(!native_adjust_write(&tree,0x7001,10,backend,&tree),"out of bounds rejects");
    check(!native_adjust_write(&tree,0x144,1,backend,&tree),"PP process id rejects");
    check(backend_calls==before,"invalid writes never call backend");
    backend_ok=0;int old=tree.current[0];
    check(!native_adjust_write(&tree,0x7001,0,backend,&tree),"backend failure rejected");
    check(tree.current[0]==old,"backend failure preserves value");
    check(((GetSelected)0x682951)(&tree.fields[0],&selected)&&get(selected,0x10)==old-specs[0].minimum,"backend failure preserves cursor");
    backend_ok=1;
    check(native_adjust_write(&tree,0x7000,1,backend,&tree),"FL enable request");
    check(last_field==NA_MODE&&last_value==1,"mode callback discriminator");
    check(((GetSelected)0x682951)(&tree.mode,&selected)&&selected==&tree.mode_values[1],"mode cursor FL");
    check(((SelectDiff)0x682e9d)(&tree.pages[0],1),"original forward navigation");
    check(((GetSelected)0x682951)(&tree.pages[0],&selected)&&selected==&tree.fields[0],"original row navigation selects contrast");
    widget_check(&tree.root,2,6,1,1);
    int rejected=777;check(!native_adjust_decode(&tree,0x7001,-1,&rejected)&&rejected==777,"minus one missing-value enum rejected");
    check(!native_adjust_decode(&tree,0x7001,19,&rejected)&&rejected==777,"out of range enum rejected");
    check(!native_adjust_encode(&tree,0x7009,0,&rejected)&&rejected==777,"Save cannot encode scalar");
    check(native_adjust_encode(&tree,0x7001,-1,&rejected)&&rejected==8,"real minus one has nonnegative enum");
    check(!native_adjust_build(&tree,0,0x7f000001,0,0x7f000002,specs,0x100),"invalid capabilities rejected");
    /* Destroy an original owning parent whose child is our embedded root. */
    NativeAdjustNode *parent=allocate(sizeof *parent);
    NativeAdjustNode **children=allocate(sizeof *children);children[0]=&tree.root;
    check(native_adjust_write(&tree,0x7001,-2,backend,&tree),"set scalar before reparent");
    ((Ctor)0x68338d)(parent,children,1,0);
    check(((Init)0x682869)(parent,0,0),"stock heap parent initializes embedded root");
    check(tree.root.parent==parent,"embedded root attached to owning parent");
    check(((GetSelected)0x682951)(&tree.fields[0],&selected)&&get(selected,0x10)==7,
          "late original parent init retains accepted scalar automatically");
    check(((GetSelected)0x682951)(&tree.mode,&selected)&&selected==&tree.mode_values[1],
          "late original parent init retains accepted mode automatically");
    before=backend_calls;
    check(native_adjust_write(&tree,0x7001,-2,backend,&tree),"equal-value restores scalar cursor after reparent");
    check(((GetSelected)0x682951)(&tree.fields[0],&selected)&&get(selected,0x10)==7,"restored scalar cursor matches saved enum");
    check(native_adjust_write(&tree,0x7000,1,backend,&tree),"equal-value restores mode cursor after reparent");
    check(((GetSelected)0x682951)(&tree.mode,&selected)&&selected==&tree.mode_values[1],"restored mode cursor remains FL");
    check(backend_calls==before,"cursor restoration does not reapply backend");
    ((Destroy)parent->vtable[1])(parent);
    check(nalloc==nfree,"stock parent destruction frees only owned parent and array");
    check(tree.root.parent==0,"embedded destructor removes dangling parent");
    check(get(&tree.fields[0],0xe)==0x7001,"embedded graph survives parent destruction");
    /* Stock shallow clone owns a new root and pointer array, but not embedded children. */
    NativeAdjustNode *copy=((Clone)tree.root.vtable[0xe4/4])(&tree.root);
    check(copy->vtable[0]==((const uintptr_t *)0x918ec8)[0]&&
          copy->vtable[1]==((const uintptr_t *)0x918ec8)[1],"clone retains owning original destructors");
    ((Destroy)copy->vtable[1])(copy);
    check(nalloc==nfree,"uninitialized clone destruction respects embedded children");
    /* Reinitialize original graph, then initialize a second copy; original init
     * must deep-clone its aliased children into separately owned allocations. */
    check(((Init)0x682869)(&tree.root,0,0),"reinitialize embedded graph");
    copy=((Clone)tree.root.vtable[0xe4/4])(&tree.root);
    check(((Init)0x682869)(copy,0,0),"original init deep clones shared children");
    check(field_node(copy,1)!=&tree.fields[0],"deep clone field storage is independent");
    check(field_node(copy,1)->children[0]!=&tree.values[0][0],"deep clone leaf storage is independent");
    check(field_node(copy,1)->children[0]->parent==field_node(copy,1),"deep clone parent linkage");
    check(get(field_node(copy,1),0xe)==0x7001,"deep clone retains custom process id");
    check(((GetSelected)0x682951)(field_node(copy,1),&selected)&&get(selected,0x10)==7,
          "deep-cloned scalar restores accepted owner state");
    check(((GetSelected)0x682951)(field_node(copy,0),&selected)&&get(selected,0x10)==1,
          "deep-cloned mode restores accepted owner state");
    for(unsigned f=0;f<8;f++) {
        unsigned char gray=0;
        check(((GetGray)0x682d0b)(field_node(copy,f+1),&gray)==(f>=6),"deep clone preserves capability grayout");
    }
    ((Destroy)copy->vtable[1])(copy);
    check(nalloc==nfree,"stock deep clone destruction frees every native allocation");
    check(get(&tree.fields[0],0xe)==0x7001,"embedded graph survives deep clone destruction");
    /* Optional explicit Save action uses the same original node ownership and
     * dispatch metadata without masquerading as a scalar field. */
    check(!native_adjust_add_save(&tree,0),"Save rejects missing resource");
    check(native_adjust_add_save(&tree,0x0204eaab),"append optional native Save action");
    check(((GetCount)0x68289f)(&tree.root,&count)&&count==2&&tree.pages[1].count==4,"Save fourth row on second page");
    check(field_node(&tree.root,9)==&tree.save&&tree.save.parent==&tree.pages[1],
          "Save original ancestry");
    check(tree.save.index==4,"Save original page-local one-based index");
    check(get(&tree.save,0)==0x0204eaab&&get(&tree.save,0xb)==2&&
          get(&tree.save,0xc)==4&&get(&tree.save,0xe)==NATIVE_ADJUST_SAVE_ID,"Save native action properties");
    check(tree.save.count==0&&!tree.save.children,"Save has no scalar child values");
    check(!native_adjust_add_save(&tree,0x0204eaab),"Save duplicate append rejects");
    before=backend_calls;int ignored=0;
    check(!native_adjust_read(&tree,NATIVE_ADJUST_SAVE_ID,&ignored)&&
          !native_adjust_write(&tree,NATIVE_ADJUST_SAVE_ID,1,backend,&tree),"Save never routes through scalar API");
    check(backend_calls==before,"Save append and invalid scalar call never invoke backend");
    check(((GetSelected)0x682951)(&tree.fields[0],&selected)&&get(selected,0x10)==7,
          "Save append restores scalar cursor");
    check(((GetSelected)0x682951)(&tree.mode,&selected)&&selected==&tree.mode_values[1],
          "Save append restores mode cursor");
    check(((Select)0x682e59)(&tree.root,2)&&((Select)0x682e59)(&tree.pages[1],4)&&
          ((GetSelected)0x682951)(&tree.pages[1],&selected)&&selected==&tree.save,"Save native selectable action row");
    widget_check(&tree.root,2,4,2,3);
    parent=allocate(sizeof *parent);children=allocate(sizeof *children);children[0]=&tree.root;
    ((Ctor)0x68338d)(parent,children,1,0);
    check(((Init)0x682869)(parent,0,0),"stock parent initializes Save graph");
    check(!native_adjust_add_save(&tree,0x0204eaab),"attached tree cannot append Save");
    ((Destroy)parent->vtable[1])(parent);
    check(nalloc==nfree&&tree.root.parent==0,"stock parent destruction preserves Save graph");
    copy=((Clone)tree.root.vtable[0xe4/4])(&tree.root);
    ((Destroy)copy->vtable[1])(copy);
    check(nalloc==nfree,"Save shallow clone destruction frees only owned storage");
    check(((Init)0x682869)(&tree.root,0,0),"reinitialize embedded Save graph");
    copy=((Clone)tree.root.vtable[0xe4/4])(&tree.root);
    check(((Init)0x682869)(copy,0,0),"deep clone Save graph using original init");
    check(copy->count==2&&copy->children[1]->count==4&&field_node(copy,9)!=&tree.save&&
          field_node(copy,9)->parent==copy->children[1]&&get(field_node(copy,9),0xe)==NATIVE_ADJUST_SAVE_ID,
          "deep cloned Save action has owned storage and original ancestry");
    check(!native_adjust_save_title(&tree,0),"save feedback rejects missing resource");
    check(native_adjust_save_title(&tree,0x0204ef85)&&get(&tree.save,0)==0x0204ef85&&
          get(field_node(copy,9),0)==0x0204ef85,"Complete feedback reaches original embedded and cloned property readers");
    check(native_adjust_save_title(&tree,0x0204eaab)&&get(field_node(copy,9),0)==0x0204eaab,
          "new edits can restore Save label on existing clone");
    check(((GetSelected)0x682951)(field_node(copy,1),&selected)&&get(selected,0x10)==7&&
          ((GetSelected)0x682951)(field_node(copy,0),&selected)&&get(selected,0x10)==1,
          "late original Save graph clone preserves scalar and mode cursor");
    unsigned char save_gray=0;
    check(((GetGray)0x682d0b)(field_node(copy,9),&save_gray)==0,
          "late initialized Save action stays selectable");
    ((Destroy)copy->vtable[1])(copy);
    check(nalloc==nfree,"Save deep clone destruction frees every original allocation");
    check(get(&tree.save,0xe)==NATIVE_ADJUST_SAVE_ID,"embedded Save survives original destruction");
    put("NATIVE_ADJUST_LIFETIME_ALLOCATIONS ");number(nalloc);put(" FREED ");number(nfree);put("\n");
    put("NATIVE_ADJUST_CHECKS ");number(checks);put("\n");
    put("NATIVE_ADJUST_TESTS_PASSED\n");finish();
}
