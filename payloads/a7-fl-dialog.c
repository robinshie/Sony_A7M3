/* ILCE-7M3 4.04: reuse @V039's native layout, event translation and lifecycle.
 * Three writable data-vtable slots route only our private boot token to these
 * callbacks; two SettingMenu lifecycle slots observe our category. This also covers a framework-cached dialog instance. Other boot
 * elements use the original callbacks. No
 * instructions, locale files or Sony setting properties are overwritten. */
#include "a7-fl-dialog.h"
#include "a7-fl-dialog-pins.h"
#ifdef A7_FL_CUSTOM_LOOKS
#include "a7-fl-custom-text.h"
static const char *(*dynamic_name)(uint32_t);
static int prepare(uintptr_t,void*);
int a7_fl_dialog_names(uintptr_t view,void*manager,const char *(*resolve)(uint32_t)) {
    if(!resolve||dynamic_name||!prepare(view,manager))return -1;
    dynamic_name=resolve;return 0;
}
static void paint_names(void*);
#endif
#define TOKEN 0x41374644u
#define YES 0x9b9fd79fu
#define NO  0x9b9fd7a0u
enum { CLOSED, ASK, BUSY, DONE, FAILED, PICK };
static struct {
    uintptr_t view2,view6,obj;
    void *handle,*obj_handle,*manager,*instance;
    void *menu;
    int (*owns_root)(const void*);
    int (*commit)(void);
    unsigned phase;
#ifdef A7_FL_CUSTOM_LOOKS
    unsigned deleting;
#endif
#ifdef A7_FL_SD_IMPORT
    unsigned count,index;
    const char *(*filename)(unsigned);
    int (*select_file)(unsigned);
    char caption[384];
#endif
} dialog;
static int equal(const void *aa,const void *bb,unsigned n) {
    const unsigned char *a=aa,*b=bb;while(n--)if(*a++!=*b++)return 0;return 1;
}
static int own_menu(void *v) {
    return v&&dialog.owns_root&&*(uintptr_t*)v==dialog.view2+0x87b600&&
        *(void**)((char*)v+0x24)==dialog.manager&&
        *(unsigned*)((char*)v+0x130)==3&&
        dialog.owns_root(*(void**)((char*)v+0x188));
}
static void menu_draw(void *v,int reason) {
    ((void(*)(void*,int))(dialog.view2+0x21fc81))(v,reason);
    if(own_menu(v))dialog.menu=v;
    else if(dialog.menu==v)dialog.menu=0;
#ifdef A7_FL_CUSTOM_LOOKS
    if(own_menu(v))paint_names(v);
#endif
}
static void menu_terminate(void *v) {
    if(dialog.menu==v)dialog.menu=0;
    ((void(*)(void*))(dialog.view2+0x21e375))(v);
}
int a7_fl_dialog_watch_menu(uintptr_t view2,void *manager,int (*owns_root)(const void*)) {
    if(!view2||!manager||!owns_root)return -1;
    if(dialog.owns_root)return dialog.view2==view2&&dialog.manager==manager&&
        dialog.owns_root==owns_root?0:-1;
    for(unsigned i=0;i<sizeof a7_dialog_pins/sizeof a7_dialog_pins[0];i++) {
        const struct a7_dialog_pin *p=&a7_dialog_pins[i];
        if(p->library==2&&!equal((void*)(view2+p->offset),p->bytes,p->size))return -1;
    }
    uintptr_t *vt=(void*)(view2+0x87b5f8);
    if(*(uintptr_t*)(view2+0x8e5f44)!=(uintptr_t)vt||
       vt[65]!=view2+0x21fc81||vt[59]!=view2+0x21e375)return -1;
    dialog.view2=view2;dialog.manager=manager;dialog.owns_root=owns_root;
    __atomic_store_n(vt+65,(uintptr_t)menu_draw,__ATOMIC_RELEASE);
    __atomic_store_n(vt+59,(uintptr_t)menu_terminate,__ATOMIC_RELEASE);
    return 0;
}
static void refresh_menu(void) {
    void *v=dialog.menu;if(!own_menu(v))return;
    void *w=((void*(*)(void*,unsigned))(dialog.obj+0x12e4a9))(v,0xdabd8bcb);
    w=((void*(*)(void*))(dialog.view2+0x592991))(w);
    /* Native categorized-list row population reads property 0 for each title
     * and calls its original button setters. It does not navigate or save.
     * Require the widget and view to reference the same owned category. */
    if(!w||*(void**)((char*)w+0x124a8)!=*(void**)((char*)v+0x188))return;
    ((void(*)(void*))(dialog.view2+0x5944ad))(w);
#ifdef A7_FL_CUSTOM_LOOKS
    paint_names(v);
#endif
}
#ifdef A7_FL_CUSTOM_LOOKS
static void paint_names(void*v){
    if(!dynamic_name||!dialog.obj||!own_menu(v))return;
    void*w=((void*(*)(void*,unsigned))(dialog.obj+0x12e4a9))(v,0xdabd8bcb);
    w=((void*(*)(void*))(dialog.view2+0x592991))(w);
    if(!w||*(void**)((char*)w+0x124a8)!=*(void**)((char*)v+0x188))return;
    struct a7_custom_text_api api={
      (void*)(dialog.obj+0x10d26b),dynamic_name};
    (void)a7_custom_text_paint(&api,w);
}
#endif
static void call_action(void *v,int action) {
    ((void(*)(void*,int))(dialog.view6+0x43a5d))(v,action);
}
static int own(void *v) {
    return v&&*(uintptr_t *)v==dialog.view6+0x839c0&&
        *(uint32_t *)((char *)v+0x124)==TOKEN&&
        *(void **)((char *)v+0x24)==dialog.manager;
}
static void *widget(void *v,unsigned id) {
    return ((void*(*)(void*,unsigned))(dialog.obj+0x12e4a9))(v,id);
}
static void show(void *w,int visible) {
    ((void(*)(void*,int))(dialog.obj+0x155657))(w,visible);
}
static int paint(void *v) {
    void *title=widget(v,0x53034e72),*yes=widget(v,YES),*no=widget(v,NO);
    title=((void*(*)(void*))(dialog.view2+0x587be9))(title);
    yes=((void*(*)(void*))(dialog.view2+0x580995))(yes);
    no=((void*(*)(void*))(dialog.view2+0x580995))(no);
    if(!title||!yes||!no)return 0;
    /* Native wrappers prove GEN_Label offsets 0x1bc / 0xe00. Text remains
     * static for the lifetime of every widget and uses its original CJK font. */
    void (*text)(void*,const char*)=(void*)(dialog.obj+0x10d26b);
#ifdef A7_FL_SD_IMPORT
#ifdef A7_FL_CUSTOM_LOOKS
    if(dialog.deleting&&dialog.phase==ASK)text((char*)title+0x1bc,dialog.caption);
    else
#endif
    if(dialog.filename&&(dialog.phase==PICK||dialog.phase==ASK)){
        const char *prefix=dialog.phase==PICK?"左右选择配方：\n":"确认导入配方？\n";
        const char *name=dialog.filename(dialog.index);
        if(!name)return 0;
        unsigned n=0;
        while(*prefix&&n<sizeof dialog.caption-1)dialog.caption[n++]=*prefix++;
        while(*name&&n<sizeof dialog.caption-1)dialog.caption[n++]=*name++;
        if(*name)return 0;
        dialog.caption[n]=0;
        text((char*)title+0x1bc,dialog.caption);
    } else
#endif
    text((char*)title+0x1bc,dialog.phase==ASK?"确认保存？":
         dialog.phase==DONE?"完成":dialog.phase==FAILED?"保存未完成":"正在保存…");
    text((char*)yes+0xe00,"确认");text((char*)no+0xe00,"取消");
    show(title,1);show(yes,1);show(no,dialog.phase==ASK||dialog.phase==PICK);
    return 1;
}
static void close_own(void *v) {
    dialog.phase=CLOSED;dialog.instance=0;
    ((void(*)(void*,const char*))(dialog.obj+0x12fd09))(v,"@V039");
}
static void action(void *v,int id) {
    if(!own(v)){call_action(v,id);return;}
    if(v!=dialog.instance||dialog.phase==CLOSED||dialog.phase==BUSY)return;
    if(id==0){close_own(v);return;}
#ifdef A7_FL_SD_IMPORT
    if(dialog.phase==PICK){
        if(id==2||id==3){
            dialog.index=(dialog.index+dialog.count+(id==2?-1:1))%dialog.count;
        }else if(id==1){
            dialog.phase=dialog.select_file(dialog.index)?FAILED:ASK;
        }else return;
        if(!paint(v)){close_own(v);return;}
        ((void(*)(void*))(dialog.obj+0x862869))(v);
        return;
    }
#endif
    if(dialog.phase!=ASK){if(id==1)close_own(v);return;}
    if(id==2||id==3){call_action(v,id);return;}
    if(id!=1)return;
    dialog.phase=BUSY;
    int rc=dialog.commit();
    dialog.phase=rc?FAILED:DONE;
    refresh_menu();
    ((void(*)(void*,unsigned,unsigned))(dialog.view2+0x2a8c81))(v,YES,0);
    if(!paint(v)){close_own(v);return;}
    ((void(*)(void*))(dialog.obj+0x862869))(v);
}
static void draw(void *v,int reason) {
    ((void(*)(void*,int))(dialog.view6+0x43b15))(v,reason);
    if(!own(v))return;
    if(((int(*)(void*))(dialog.view6+0x1a7f9))(v)!=1)return;
    if(dialog.phase==CLOSED||!dialog.commit){close_own(v);return;}
    dialog.instance=v;
    if(dialog.phase!=ASK&&dialog.phase!=PICK)
        ((void(*)(void*,unsigned,unsigned))(dialog.view2+0x2a8c81))(v,YES,0);
    if(!paint(v))close_own(v);
}
static void terminate(void *v) {
    if(own(v)&&v==dialog.instance){dialog.phase=CLOSED;dialog.instance=0;}
    ((void(*)(void*))(dialog.view6+0x42b6f))(v);
}
#ifdef A7_FL_CUSTOM_LOOKS
static void custom_label_variant(void*label,void*value){
 ((void(*)(void*,void*))(dialog.obj+0x10d211))(label,value);
 uint32_t id=*(const uint32_t*)((const char*)label+0x2dc);
 const char*name=dynamic_name?dynamic_name(id):0;
 if(name)((void(*)(void*,const char*))(dialog.obj+0x10d26b))(label,name);
}
static void custom_label_text(void*label,uint32_t id){
 /* Popup population invokes GEN_Label::setText through its data vtable,
  * independently of the category view draw callback. Preserve stock setup
  * and replace only our allocated custom-look resource IDs. */
 ((void(*)(void*,uint32_t))(dialog.obj+0x10dcc5))(label,id);
 const char*name=dynamic_name?dynamic_name(id):0;
 if(name)((void(*)(void*,const char*))(dialog.obj+0x10d26b))(label,name);
}
#endif
static int prepare(uintptr_t view2,void *manager) {
    if(dialog.owns_root&&(dialog.view2!=view2||dialog.manager!=manager))return 0;
    if(dialog.handle)return dialog.view2==view2&&dialog.manager==manager;
    if(!view2||!manager)return 0;
    if(!equal((void*)(view2+0x15d958),a7_dialog_pin_dlopen,12)||
       !equal((void*)(view2+0x15c8dc),a7_dialog_pin_dlsym,12)||
       !equal((void*)(view2+0x15bf38),a7_dialog_pin_dlclose,12))return 0;
    void *(*open)(const char*,int)=(void*)(view2+0x15d958);
    void *(*symbol)(void*,const char*)=(void*)(view2+0x15c8dc);
    void *h=open("/usr/lib/viewUnified6.so",2),*objh=0;if(!h)return 0;
    uintptr_t f=(uintptr_t)symbol(h,"ViewExecuteConfirmDlgToInstance");
    if(!f)goto bad;
    uintptr_t view6=f-0x4391f;
    objh=open("/usr/lib/libObj.so",6);if(!objh)goto bad;
    uintptr_t get=(uintptr_t)symbol(objh,"_ZN8ViewBase9getWidgetEj");
    if(!get)goto bad;
    uintptr_t obj=get-0x12e4a9;
    for(unsigned i=0;i<sizeof a7_dialog_pins/sizeof a7_dialog_pins[0];i++) {
        const struct a7_dialog_pin *p=&a7_dialog_pins[i];
        uintptr_t base=p->library==2?view2:p->library==6?view6:obj;
        if(!equal((void*)(base+p->offset),p->bytes,p->size))goto bad;
    }
    uintptr_t *slot=(void*)(view6+0x85630),*original=(void*)(view6+0x839b8);
    if(*slot!=(uintptr_t)original||original[64]!=view6+0x43a5d||
       original[65]!=view6+0x43b15||original[59]!=view6+0x42b6f)goto bad;
#ifdef A7_FL_CUSTOM_LOOKS
    uintptr_t *label_slot=(void*)(obj+0x121d6dc);
    uintptr_t *direct_slot=(void*)(view2+0x8e5ae8),*variant_slot=(void*)(view2+0x8e40f4);
    if(*label_slot!=obj+0x10dcc5||*direct_slot!=obj+0x10dcc5||*variant_slot!=obj+0x10d211)goto bad;
#endif
    dialog.view2=view2;dialog.view6=view6;dialog.obj=obj;dialog.manager=manager;
    dialog.handle=h;dialog.obj_handle=objh;
#ifdef A7_FL_CUSTOM_LOOKS
    __atomic_store_n(label_slot,(uintptr_t)custom_label_text,__ATOMIC_RELEASE);
    __atomic_store_n(direct_slot,(uintptr_t)custom_label_text,__ATOMIC_RELEASE);
    __atomic_store_n(variant_slot,(uintptr_t)custom_label_variant,__ATOMIC_RELEASE);
#endif
    __atomic_store_n(original+64,(uintptr_t)action,__ATOMIC_RELEASE);
    __atomic_store_n(original+65,(uintptr_t)draw,__ATOMIC_RELEASE);
    __atomic_store_n(original+59,(uintptr_t)terminate,__ATOMIC_RELEASE);
    return 1;
bad:
    if(objh)((void(*)(void*))(view2+0x15bf38))(objh);
    ((void(*)(void*))(view2+0x15bf38))(h);
    return 0;
}
int a7_fl_dialog_open(uintptr_t view2,void *manager,int (*commit)(void)) {
    if(!commit||!prepare(view2,manager))return -1;
    /* Save is dispatched on the UI thread. openView queues an event; it does
     * not construct/draw/call commit synchronously. Its pinned implementation
     * reads only the alias map at +0x70 and the ViewManager at +0x24. */
    uintptr_t sender[29]={0};sender[9]=(uintptr_t)manager;
    dialog.commit=commit;dialog.instance=0;dialog.phase=ASK;
#ifdef A7_FL_SD_IMPORT
    dialog.filename=0;dialog.select_file=0;dialog.count=0;
#ifdef A7_FL_CUSTOM_LOOKS
    dialog.deleting=0;
#endif
#endif
    ((void(*)(void*,const char*,int,int))(dialog.obj+0x12fdcd))
        (sender,"@V039",TOKEN,0);
    return 0;
}
#ifdef A7_FL_SD_IMPORT
int a7_fl_dialog_files(uintptr_t view,void *manager,unsigned count,
 const char *(*name)(unsigned),int (*select_file)(unsigned),int (*commit)(void)){
 if(!count||count>32||!name||!select_file||dialog.phase!=CLOSED)return -1;
 int rc=a7_fl_dialog_open(view,manager,commit);
 if(rc)return rc;
 dialog.filename=name;dialog.select_file=select_file;
 dialog.count=count;dialog.index=0;dialog.phase=PICK;
 return 0;
}
#endif

#ifdef A7_FL_CUSTOM_LOOKS
int a7_fl_dialog_delete(uintptr_t view,void*manager,const char*name,int(*commit)(void)){
 if(!name||dialog.phase!=CLOSED)return -1;
 int rc=a7_fl_dialog_open(view,manager,commit);if(rc)return rc;
 const char*prefix="确认删除外观？\n";unsigned n=0;
 while(*prefix)dialog.caption[n++]=*prefix++;
 while(*name&&n<sizeof dialog.caption-1)dialog.caption[n++]=*name++;
 dialog.caption[n]=0;dialog.deleting=1;return 0;
}
#endif
