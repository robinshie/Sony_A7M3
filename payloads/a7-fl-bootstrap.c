/* Actual ILCE-7M3 4.04 platform binding. Called by checked MENU and StillView
 * entry loaders, never by an ELF constructor. Boot ignores the UI argument. */
#include <stdint.h>
#include "a7-fl-module.h"
#include "a7-fl-posix.h"
#include "a7-fl-bootstrap.h"
#include "a7-fl-bootstrap-pins.h" /* generated privately from pinned Sony ELFs */
extern int a7_fl_install_prepared(uintptr_t,void *);
static struct {
    uint32_t lock,ready,installing,mode;
    uintptr_t caller,view,caution,backup;
    uintptr_t prepared_view,prepared_caution,prepared_backup;
    void *view_manager;
    unsigned count;
    struct {uintptr_t lo,hi;} ranges[1024];
    char maps[65536];
    struct a7_fl_platform platform;
} boot;
static struct a7_fl_bootstrap_report diagnostic;
const struct a7_fl_bootstrap_report *a7_fl_bootstrap_status(void){return &diagnostic;}
static long syscall3(long nr,long a,long b,long c) {
#ifdef A7_FL_BOOTSTRAP_TEST
    extern long a7_fl_bootstrap_test_syscall3(long,long,long,long);
    return a7_fl_bootstrap_test_syscall3(nr,a,b,c);
#else
    register long r7 __asm__("r7")=nr;
    register long r0 __asm__("r0")=a,r1 __asm__("r1")=b,r2 __asm__("r2")=c;
    __asm__ volatile("svc #0":"+r"(r0):"r"(r7),"r"(r1),"r"(r2):"memory","cc");return r0;
#endif
}
static int same(const void *aa,const void *bb,unsigned n) {
    const unsigned char *a=aa,*b=bb;while(n--)if(*a++!=*b++)return 0;return 1;
}
static int contains(const char *p,const char *needle) {
    for(;*p&&*p!='\n';p++){const char *a=p,*b=needle;while(*b&&*a==*b){a++;b++;}if(!*b)return 1;}return 0;
}
static const char *map_name(const char *end) {
    for(unsigned field=0;field<4;field++){
        while(*end==' ')end++;
        while(*end&&*end!=' '&&*end!='\n')end++;
    }
    while(*end==' ')end++;
    return end;
}
static int exact_path(const char *name,const char *expected) {
    while(*expected&&*name==*expected){name++;expected++;}
    return !*expected&&(!*name||*name=='\n');
}
static uintptr_t hex(const char **p) {
    uintptr_t value=0;
    for(;;){unsigned c=(unsigned char)**p;
        if(c>='0'&&c<='9')c-='0';else if(c>='a'&&c<='f')c=c-'a'+10;else break;
        if(value>0x0fffffffu)return 0;
        value=(value<<4)|c;++*p;
    }return value;
}
static int span(void *unused,uintptr_t address,unsigned bytes) {
    (void)unused;if(!address||bytes>UINT32_MAX-address)return 0;
    uintptr_t end=address+bytes;unsigned i=0;
    while(i<boot.count&&boot.ranges[i].hi<=address)i++;
    if(i==boot.count||boot.ranges[i].lo>address)return 0;
    while(boot.ranges[i].hi<end){uintptr_t next=boot.ranges[i].hi;if(++i==boot.count||boot.ranges[i].lo!=next)return 0;}
    return 1;
}
static int maps(void) {
    boot.view=boot.caution=boot.backup=0;
    long fd=syscall3(5,(long)"/proc/self/maps",0,0);if(fd<0)return 0;
    unsigned n=0;int ok=1;
    while(n<sizeof boot.maps-1){long got=syscall3(3,fd,(long)(boot.maps+n),sizeof boot.maps-1-n);
        if(got<0){ok=0;break;}if(!got)break;n+=(unsigned)got;
    }
    syscall3(6,fd,0,0);if(!ok||n==sizeof boot.maps-1)return 0;boot.maps[n]=0;boot.count=0;
    for(const char *p=boot.maps;*p;){
        const char *end=p;uintptr_t lo=hex(&end);if(*end++!='-')return 0;uintptr_t hi=hex(&end);
        if(!lo||hi<=lo)return 0;
        const char *name=map_name(end);
        int is_view=exact_path(name,"/usr/lib/viewUnified2.so");
        int is_caution=exact_path(name,"/usr/lib/CautionConfig.so");
        int is_backup=exact_path(name,"/usr/lib/libbackup.so");
        int allowed=is_view||is_caution||is_backup||exact_path(name,"/usr/lib/a7fl.so")||
                    !*name||*name=='\n'||*name=='[';
        /* Only private ordinary memory and exact pinned module paths are used. */
        if(end[0]==' '&&end[1]=='r'&&end[4]=='p'&&allowed){
            if(boot.count==1024)return 0;
            boot.ranges[boot.count].lo=lo;boot.ranges[boot.count++].hi=hi;
        }
        if(contains(p,"r-xp 00000000")){
            if(is_view)boot.view=lo;
            if(is_caution)boot.caution=lo;
            if(is_backup)boot.backup=lo;
        }
        while(*p&&*p!='\n')p++;
        if(*p)p++;
    }
    return boot.view&&boot.caution&&boot.backup;
}
static int pin(uintptr_t base,unsigned offset,const unsigned char *expected,unsigned size) {
    return span(0,base+offset,size)&&same((const void *)(base+offset),expected,size);
}
static int identity(void *unused) {
    (void)unused;char version[24];long fd=syscall3(5,(long)"/version.txt",0x8000,0);
    if(fd<0)return 0;
    long n=syscall3(3,fd,(long)version,sizeof version);syscall3(6,fd,0,0);
    static const char build[]="37114_13.2026020901";
    if(n!=(long)sizeof build-1||!same(version,build,sizeof build-1))return 0;
    if(!pin(boot.backup,0x1174,a7_pin_size,16)||!pin(boot.backup,0x11d4,a7_pin_attr,16)||
       !pin(boot.backup,0x1204,a7_pin_read,16)||!pin(boot.backup,0x1358,a7_pin_write,16)||
       !pin(boot.caution,0x68338c,a7_pin_ctor,16)||!pin(boot.caution,0x6830aa,a7_pin_init,16))return 0;
    const struct a7_fl_api *api=&boot.platform.backup;unsigned char model[16];
    static const unsigned char expected[16]={'I','L','C','E','-','7','M','3',0,0,0,0,0,0,0,0};
    return api->size(0x3e0005)==16&&api->attr(0x3e0005)==1&&api->read(0x3e0005,model)==16&&same(model,expected,16);
}
static int event(void *unused,enum a7_fl_platform_event kind) {
    (void)unused;
    /* Explicit Save has its own checked native execProc callback. External
     * confirm/cancel/uninstall calls are not authorized by this platform. */
    return boot.installing&&(boot.caller&~(uintptr_t)1)==boot.view+0x5b9b30&&
           ((kind==A7_FL_INSTALL_EVENT&&boot.mode==0)||(kind==A7_FL_BOOT_EVENT&&boot.mode==1));
}
static int page(a7_menu_node *p) {
    if(((uintptr_t)p&3)||!span(0,(uintptr_t)p,sizeof *p)||
       p->vtable!=(uintptr_t *)(boot.caution+0x918ec8)||p->count!=3||
       (uintptr_t)p->properties!=boot.view+0xa725a0||
       ((uintptr_t)p->children&3)||!span(0,(uintptr_t)p->children,12))return 0;
    if(p->depth==3)return (uintptr_t)p->parent==boot.view+0xa69c88&&p->serial==14&&p->index==14;
    return (uintptr_t)p->children==boot.view+0x8f3214&&!p->parent&&!p->depth&&
           !p->selected&&!p->serial&&!p->index&&!p->state;
}
static int prepare(void) {
    struct a7_fl_platform *p=&boot.platform;
    p->view_base=boot.view;p->caution_base=boot.caution;p->view_manager=0;
    p->manager=(void *)(boot.view+0xa61c18);p->manager_vtable=(uintptr_t *)(boot.view+0x87f720);
    p->parent_vtable=(uintptr_t *)(boot.caution+0x918ec8);
    p->backup.size=(void *)(boot.backup+0x1175);p->backup.attr=(void *)(boot.backup+0x11d5);
    p->backup.read=(void *)(boot.backup+0x1205);p->backup.write=(void *)(boot.backup+0x1359);
#ifdef A7_FL_BOOTSTRAP_TEST
    extern void a7_fl_bootstrap_test_backup(struct a7_fl_api *);
    a7_fl_bootstrap_test_backup(&p->backup);
#endif
    p->identity=identity;p->event=event;p->readable=span;p->opaque=0;
    a7_fl_posix_io(&p->storage);
    if(!identity(0))return A7_FL_MODULE_WITNESS;
    /* Color startup does not dereference menu/model objects. The menu-specific
     * profile is validated later, at the original SettingMenu construction seam. */
    p->creative_style=(void *)(boot.caution+0xa75ff4);
    p->parents[0]=(void *)(boot.view+0xa6dfa4);p->parent_count=1;
    int rc=a7_fl_prepare(p);
    if(!rc){boot.ready=1;boot.prepared_view=boot.view;boot.prepared_caution=boot.caution;boot.prepared_backup=boot.backup;}
    return rc;
}
static int configure_menu(void *view_manager) {
    struct a7_fl_platform *p=&boot.platform;
    if(((uintptr_t)view_manager&3)||!span(0,(uintptr_t)view_manager,4)||!span(0,(uintptr_t)p->manager,4)||
       *(uintptr_t **)p->manager!=p->manager_vtable)return A7_FL_MODULE_WITNESS;
    a7_menu_node *still=(void *)(boot.view+0xa6dfa4);
    if(!page(still))return A7_FL_MODULE_PARENT;
    for(unsigned i=0;i<3;i++)if(((uintptr_t)still->children[i]&3)||!span(0,(uintptr_t)still->children[i],40))return A7_FL_MODULE_PARENT;
    p->parents[0]=still;p->anchors[0]=still->children[2];p->parent_count=1;
    /* The core permits only menu fields to change once color startup is ready. */
    p->view_manager=view_manager;
    int rc=a7_fl_configure_menu(p);if(!rc)boot.view_manager=view_manager;return rc;
}
__attribute__((noinline)) int a7_fl_install(uintptr_t view_base,void *view_manager,unsigned mode) {
    uintptr_t caller=(uintptr_t)__builtin_return_address(0);
    if(__atomic_exchange_n(&boot.lock,1,__ATOMIC_ACQUIRE))return A7_FL_MODULE_BUSY;
    diagnostic.version=1;diagnostic.calls++;diagnostic.mode=mode;diagnostic.stage=0;
    int rc=A7_FL_MODULE_WITNESS;
    if(mode>1||(caller&~(uintptr_t)1)!=view_base+0x5b9b30)goto done;
    diagnostic.stage=1;
    if(!maps()||boot.view!=view_base)goto done;
    if(boot.ready&&(boot.view!=boot.prepared_view||boot.caution!=boot.prepared_caution||boot.backup!=boot.prepared_backup))goto done;
    diagnostic.stage=2;
    boot.caller=caller;boot.installing=1;boot.mode=mode;
    if(!boot.ready){rc=prepare();if(rc)goto done;}
    diagnostic.stage=3;
    if(mode==1)rc=a7_fl_initialize_color_prepared();
    else {
        if(!a7_fl_status()->installed){rc=configure_menu(view_manager);if(rc)goto done;}
        else if(boot.view_manager!=view_manager)goto done;
        rc=a7_fl_install_prepared(view_base,view_manager);
    }
done:
    diagnostic.result=rc;diagnostic.ready=boot.ready;
    diagnostic.view=boot.view;diagnostic.caution=boot.caution;diagnostic.backup=boot.backup;
    boot.installing=0;__atomic_store_n(&boot.lock,0,__ATOMIC_RELEASE);return rc;
}
