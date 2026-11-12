#include <stdint.h>
#include <stddef.h>
#include "a7-fl-dialog.h"
#include "a7-fl-dialog-pins.h"
#include "test-stubs.h"
static unsigned checks,used,event,highlight,commits,fail_save,closes,stock_writes,queued,redraws,terminations;
static uint32_t heap[4096],manager[8],title[1200],yes[1200],no[1200],label_vt[120],footer_vt[120];
static const char *message,*yes_text,*no_text;static unsigned no_visible;
static uint32_t pending_token,pending_id;
static unsigned loader_refs;
static void check(int ok,const char*s);
static uint32_t menu[0x248/4],list[0x12500/4],node_vt[66],root[1],page[1],rows[4];
static uint32_t save_title=0x0204eaab,painted_title[7],menu_draws,menu_ends,row_updates;
static int owns_root(const void*p){return p==root;}
void stock_menu_draw(void*v,int reason){check(v==menu&&reason==0,"native menu draw forwarded");menu_draws++;}
void stock_menu_terminate(void*v){check(v==menu,"native menu termination forwarded");menu_ends++;}
void variant_noop(void*v){(void)v;}
void variant_copy(void*to,const void*from){(void)to;(void)from;}
int popup_closed(void*w){check(w==list,"native popup state query");return 0;}
void footer_noop(void*w,void*f){(void)f;check(w==list,"native row footer update");}
void row_set(void*w,int index,int state,int gray,unsigned title_id,unsigned value,int variant,void*data){
    (void)value;(void)variant;(void)data;(void)gray;
    check(w==list&&index>=0&&index<7,"native row setter index");
    if(index<4)check(state==(index==3?2:1),"selection preserved by row refresh");
    painted_title[index]=title_id;row_updates++;
}
void icon_noop(void*w,unsigned id,unsigned flags){(void)w;(void)id;check(!flags,"native footer icon flags");}
int node_child(void*n,int index,void**out){
    if(n==root&&index==2){*out=page;return 1;}
    if(n==page&&index>=1&&index<=4){*out=rows+index-1;return 1;}
    *out=0;return 0;
}
int node_int(void*n,int key,int*out){(void)n;*out=key==14?0x7009:key==11?2:4;return 1;}
int node_gray(void*n,unsigned char*out){(void)n;*out=0;return 0;}
int node_res(void*n,int key,unsigned*out){check(key==0,"original row population reads title property");*out=n==rows+3?save_title:0x0204fda5+(unsigned)((uint32_t*)n-rows);return 1;}
int node_selected(void*n,void**out){(void)n;*out=0;return 0;}
static void observe_menu(void){((void(*)(void*,int))((uintptr_t*)menu[0])[0xfc/4])(menu,0);}
void *memset(void*p,int b,size_t n){unsigned char*d=p;while(n--)*d++=(unsigned char)b;return p;}
static void put(const char*s){volatile unsigned *uart=(void*)0x09000000;while(*s)*uart=(unsigned char)*s++;}
static void exit_test(int fail){register unsigned r0 __asm__("r0")=0x18;register unsigned r1 __asm__("r1")=fail?0x20023:0x20026;__asm__ volatile("svc 0x123456"::"r"(r0),"r"(r1):"memory");for(;;){}}
static int same(const char*a,const char*b){while(*a&&*a==*b){a++;b++;}return *a==*b;}
static void check(int ok,const char*s){checks++;if(!ok){put("FAIL ");put(s);put("\n");exit_test(1);}}
void unexpected(void){check(0,"unmodeled dependency");}
void *allocate(unsigned n){n=(n+3)/4;check(used+n<4096,"allocation bounds");void*p=heap+used;used+=n;return p;}
void base_ctor(void *v,void *vm){check(vm==manager,"constructor ViewManager");for(unsigned i=0;i<296/4;i++)((uint32_t*)v)[i]=0;((void**)v)[9]=vm;}
void model_request(void*v,int b){(void)v;check(b==0,"dialog has no model requests");}
unsigned event_id(void*v){(void)v;return event;}
void get_highlight(void*v,unsigned*a,unsigned*b){(void)v;*a=highlight;*b=0;}
void set_highlight(void*v,unsigned a,unsigned b){(void)v;check((a==0x9b9fd79f||a==0x9b9fd7a0)&&b==0,"native highlight ID");highlight=a;}
void *get_widget(void*v,unsigned id){if(id==0xdabd8bcb){check(v==menu,"refresh uses live menu instance");return list;}switch(id){case 0x53034e72:return title;case 0x9b9fd79f:return yes;case 0x9b9fd7a0:return no;case 0x35226f0d:return 0;default:unexpected();return 0;}}
void *cast_widget(void*w){return w;}
void *cast_footer(void*w){return w;}
void resource_text(void*w,unsigned id){check(w==title&&(id==0x0204e90f||id==0x0204fd94||id==0x0204e9e8),"original title method");}
void direct_text(void*w,const char*s){if(w==(char*)title+0x1bc)message=s;else if(w==(char*)yes+0xe00)yes_text=s;else if(w==(char*)no+0xe00)no_text=s;else unexpected();}
void display(void*w,int visible){check(w==title||w==yes||w==no,"widget visibility ABI");if(w==no)no_visible=visible;}
void redraw(void*v){(void)v;redraws++;}
void close_view(void*v,const char*n){(void)v;check(same(n,"@V039"),"only owned view closes");closes++;}
void stock_write(int prop,const void*data){check(prop==0x0107159b||prop==0x01071946||prop==0x01071baf,"original backup action");check(*(const unsigned char*)data<=1,"original bool");stock_writes++;}
void wrap_ctor(void*w){(void)w;}
void wrap_destroy(void*w){(void)w;}
void wrap_enable(void*w){(void)w;terminations++;}
unsigned id_get(const char*n){check(same(n,"@V039"),"dialog registry name");return 74;}
void event_ctor(void*e,unsigned id,unsigned dest,unsigned flags){check(id==0x11012001&&dest==4&&!flags,"native queued OpenView event");((unsigned*)e)[0]=id;}
void param_ctor(void*p,unsigned n){((unsigned*)p)[0]=n;}
void event_add(void*e,unsigned id,void*p){(void)e;if(id==6)pending_id=*(unsigned*)p;else if(id==26)pending_token=*(unsigned*)p;else unexpected();}
void push_event(void*sender,void*e){(void)e;check(((void**)sender)[9]==manager&&((unsigned*)sender)[28]==0,"native open sender/alias fields");queued++;}
void *mock_dlopen(const char*n,int flags){check((same(n,"/usr/lib/viewUnified6.so")&&flags==2)||(same(n,"/usr/lib/libObj.so")&&flags==6),"exact native libraries and loader flags");loader_refs++;return (void*)(flags==2?1:2);}
void *mock_dlsym(void*h,const char*n){if(h==(void*)1){check(same(n,"ViewExecuteConfirmDlgToInstance"),"exact dialog factory");return (void*)0x4204391f;}check(h==(void*)2&&same(n,"_ZN8ViewBase9getWidgetEj"),"exact libObj anchor");return (void*)0x4412e4a9;}
void mock_dlclose(void*h){check((h==(void*)1||h==(void*)2)&&loader_refs,"loader cleanup");loader_refs--;}
static int commit(void){commits++;save_title=fail_save?0x0204ef87:0x0204ef85;return fail_save?-7:0;}
static void *create(unsigned token){void*v=((void*(*)(void*,void*))0x4204391f)(0,manager);((unsigned*)v)[1]=1;((unsigned*)v)[0x124/4]=token;return v;}
static void draw(void*v){uintptr_t*vt=*(uintptr_t**)v;((void(*)(void*,int))vt[0xfc/4])(v,0);}
static void action(void*v,int a){uintptr_t*vt=*(uintptr_t**)v;((void(*)(void*,int))vt[0xf8/4])(v,a);}
static void key(void*v,unsigned id,int expected){int state=-1,act=-1;event=id;((void(*)(void*,int*,int*))0x42043799)(v,&state,&act);check(act==expected,"original event maps expected action");if(act>=0)action(v,act);}
static void *open_dialog(void){unsigned n=queued;check(a7_fl_dialog_open(0x40000000,manager,commit)==0&&queued==n+1,"Save queues native view");check(pending_id==74&&pending_token==0x41374644,"boot token carried by original open");void*v=create(pending_token);draw(v);check(same(message,"确认保存？")&&same(yes_text,"确认")&&same(no_text,"取消")&&no_visible,"confirmation widgets");return v;}
void guest_main(void){
    menu[0]=0x4087b600;menu[9]=(uintptr_t)manager;menu[0x130/4]=3;menu[0x188/4]=(uintptr_t)root;
    list[0x124a8/4]=(uintptr_t)root;list[0x1c8/4]=4;list[0x1cc/4]=2;list[0x1d0/4]=3;
    root[0]=page[0]=(uintptr_t)node_vt;for(unsigned i=0;i<4;i++)rows[i]=(uintptr_t)node_vt;
    node_vt[0x24/4]=(uintptr_t)node_child;node_vt[0x28/4]=(uintptr_t)node_selected;
    node_vt[0x5c/4]=(uintptr_t)node_int;node_vt[0x80/4]=(uintptr_t)node_res;node_vt[0xa0/4]=(uintptr_t)node_gray;
    footer_vt[0x104/4]=(uintptr_t)icon_noop;
    for(unsigned i=0;i<5;i++)list[(0xa5b0+i*544)/4]=(uintptr_t)footer_vt;
    title[0]=(uintptr_t)label_vt;label_vt[0x1b0/4]=(uintptr_t)resource_text;footer_vt[0]=0;
    for(unsigned i=0;i<sizeof saved_stubs/sizeof saved_stubs[0];i++)
        for(unsigned j=0;j<saved_stubs[i].size;j++)saved_stubs[i].bytes[j]=((unsigned char*)saved_stubs[i].address)[j];
    for(unsigned i=0;i<sizeof a7_dialog_pins/sizeof a7_dialog_pins[0];i++) {
        const struct a7_dialog_pin*p=&a7_dialog_pins[i];uintptr_t b=p->library==2?0x40000000:p->library==6?0x42000000:0x44000000;
        for(unsigned j=0;j<p->size;j++)((unsigned char*)(b+p->offset))[j]=p->bytes[j];
    }
    check(a7_fl_dialog_watch_menu(0x40000000,manager,owns_root)==0,"menu observer pins original callback slots");
    check(a7_fl_dialog_watch_menu(0x40000000,manager,owns_root)==0,"menu observer idempotent");
    check(a7_fl_dialog_watch_menu(0x40000000,manager+1,owns_root)<0,"foreign observer manager rejected");
    check(a7_fl_dialog_open(0x40000000,manager,0)<0&&!queued,"null callback rejected");
    *(uint32_t*)0x42085630=0x420839bc;
    check(a7_fl_dialog_open(0x40000000,manager,commit)<0&&!queued&&!loader_refs,"foreign GOT rejected and references released");
    *(uint32_t*)0x42085630=0x420839b8;
    *(unsigned char*)0x420437fc^=1;
    check(a7_fl_dialog_open(0x40000000,manager,commit)<0&&!queued&&!loader_refs,"foreign constructor rejected");
    *(unsigned char*)0x420437fc^=1;
    void *cached=create(0x41374644);
    check(a7_fl_dialog_open(0x40000000,manager,commit)==0&&queued==1&&loader_refs==2,"production binding pins and retains both libraries");
    check(*(uint32_t*)0x42085630==0x420839b8&&*(uint32_t*)0x42083ab8!=0x42043a5d,"only data callbacks change; factory GOT unchanged");
    check(a7_fl_dialog_open(0x40000000,manager+1,commit)<0&&queued==1,"different manager rejected");
    for(unsigned i=0;i<sizeof saved_stubs/sizeof saved_stubs[0];i++)
        for(unsigned j=0;j<saved_stubs[i].size;j++)((unsigned char*)saved_stubs[i].address)[j]=saved_stubs[i].bytes[j];
    observe_menu();check(menu_draws==1,"existing native menu observed before dialog");
    draw(cached);check(same(message,"确认保存？")&&!commits,"previously cached instance uses guarded callbacks");
    action(cached,0);check(!commits&&closes==1&&!stock_writes,"cached instance cancellation isolated");closes=0;
    void*v=open_dialog();check(!commits,"opening does not save");
    key(v,3,2);check(highlight==0x9b9fd79f,"native navigation changes highlight");
    key(v,4,3);check(highlight==0x9b9fd7a0,"native reverse navigation");
    key(v,1,0);check(!commits&&closes==1&&!stock_writes,"cancel never saves or runs stock property write");
    check(!row_updates&&save_title==0x0204eaab,"cancel leaves Save unchanged");
    action(v,1);check(!commits,"queued confirm after cancellation ignored");
    v=open_dialog();key(v,2,1);check(commits==1&&same(message,"完成")&&!no_visible&&redraws==1&&!stock_writes,"confirmation commits and shows completion");
    check(painted_title[3]==0x0204ef85&&row_updates==7&&list[0x1cc/4]==2&&list[0x1d0/4]==3,"original row population paints Complete before dialog closes without moving cursor");
    draw(v);check(highlight==0x9b9fd79f&&!no_visible&&same(message,"完成"),"completion redraw keeps visible focus");
    key(v,2,1);check(commits==1&&closes==2,"completion confirmation closes without second save");
    fail_save=1;v=open_dialog();key(v,2,1);check(commits==2&&same(message,"保存未完成")&&!no_visible,"failed commit never says complete");
    check(painted_title[3]==0x0204ef87&&row_updates==14,"failed save repaints Not Complete");
    key(v,6,0);check(closes==3&&commits==2,"MENU closes error");
    fail_save=0;v=open_dialog();key(v,5,0);check(commits==2&&closes==4,"alternate cancel event");
    v=open_dialog();uintptr_t*vt=*(uintptr_t**)v;((void(*)(void*))vt[0xe4/4])(v);action(v,1);
    check(terminations==1&&commits==2,"native termination drops stale confirmation");
    for(unsigned token=0;token<3;token++){
        void*stock=create(token);draw(stock);unsigned before=stock_writes;action(stock,1);check(stock_writes==before+1&&commits==2,"stock confirm unchanged");
        before=stock_writes;action(stock,0);check(stock_writes==before+(token==0)&&commits==2,"stock cancel unchanged");
    }
    unsigned before=row_updates;
    list[0x124a8/4]=(uintptr_t)page;v=open_dialog();action(v,1);
    check(row_updates==before,"foreign widget category never repainted");action(v,0);list[0x124a8/4]=(uintptr_t)root;
    menu[0x188/4]=(uintptr_t)page;observe_menu();v=open_dialog();action(v,1);
    check(row_updates==before,"stock menu category never repainted");action(v,0);
    menu[0x188/4]=(uintptr_t)root;observe_menu();
    ((void(*)(void*))((uintptr_t*)menu[0])[0xe4/4])(menu);v=open_dialog();action(v,1);
    check(menu_ends==1&&row_updates==before,"terminated menu pointer never used");action(v,0);
    put("NATIVE_SAVE_DIALOG_PASSED: original factory, open event, state dispatch, navigation, cancel, success, failure, repeated confirm, lifecycle, stock isolation, native cached menu row refresh\n");exit_test(0);
}
