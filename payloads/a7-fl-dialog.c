/* ILCE-7M3 4.04: reuse @V039's native layout, event translation and lifecycle.
 * Three writable data-vtable slots route only our private boot token to these
 * callbacks. This also covers a framework-cached dialog instance. Other boot
 * elements use the original callbacks. No
 * instructions, locale files or Sony setting properties are overwritten. */
#include "a7-fl-dialog.h"
#include "a7-fl-dialog-pins.h"
#define TOKEN 0x41374644u
#define YES 0x9b9fd79fu
#define NO  0x9b9fd7a0u
enum { CLOSED, ASK, BUSY, DONE, FAILED };
static struct {
    uintptr_t view2,view6,obj;
    void *handle,*obj_handle,*manager,*instance;
    int (*commit)(void);
    unsigned phase;
} dialog;
static int equal(const void *aa,const void *bb,unsigned n) {
    const unsigned char *a=aa,*b=bb;while(n--)if(*a++!=*b++)return 0;return 1;
}
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
    text((char*)title+0x1bc,dialog.phase==ASK?"确认保存？":
         dialog.phase==DONE?"完成":dialog.phase==FAILED?"保存未完成":"正在保存…");
    text((char*)yes+0xe00,"确认");text((char*)no+0xe00,"取消");
    show(title,1);show(yes,1);show(no,dialog.phase==ASK);
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
    if(dialog.phase!=ASK){if(id==1)close_own(v);return;}
    if(id==2||id==3){call_action(v,id);return;}
    if(id!=1)return;
    dialog.phase=BUSY;
    int rc=dialog.commit();
    dialog.phase=rc?FAILED:DONE;
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
    if(dialog.phase!=ASK)
        ((void(*)(void*,unsigned,unsigned))(dialog.view2+0x2a8c81))(v,YES,0);
    if(!paint(v))close_own(v);
}
static void terminate(void *v) {
    if(own(v)&&v==dialog.instance){dialog.phase=CLOSED;dialog.instance=0;}
    ((void(*)(void*))(dialog.view6+0x42b6f))(v);
}
static int prepare(uintptr_t view2,void *manager) {
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
    dialog.view2=view2;dialog.view6=view6;dialog.obj=obj;dialog.manager=manager;
    dialog.handle=h;dialog.obj_handle=objh;
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
    ((void(*)(void*,const char*,int,int))(dialog.obj+0x12fdcd))
        (sender,"@V039",TOKEN,0);
    return 0;
}
