/* No constructor and no raw flash writes. The loader must invoke install at a
 * verified native lifecycle seam. All Sony/calibration bytes are private inputs. */
#include "a7-fl-module.h"
#include "a7-fl-runtime-control.h"
#include "a7-fl-runtime-recovery.h"
#include "a7-fl-color.h"
#include "native_adjust.h"
#include "a7-fl-module-data.h"
#ifdef A7_FL_SAVE_DIALOG
#include "a7-fl-dialog.h"
#endif
#ifdef A7_FL_CAPTURE_LOOK
#include "a7-fl-capture.h"
static const uint8_t *const capture_stock[]={a7_pkg_original[1],a7_pkg_original[2]};
static const uint8_t *const capture_look[]={a7_pkg_capture1,a7_pkg_capture2};
#ifdef A7_FL_CAPTURE_CONTROLS
#include "a7-fl-capture-controls.h"
static struct a7_capture_controls capture_controls;
static A7FLColorParams capture_params(const struct a7_fl_preference *p) {
    A7FLColorParams result={p->parameters[0],p->parameters[1],p->parameters[2],p->parameters[3],p->parameters[4]};
    return result;
}
#endif
#endif
/* Compiler-emitted structure copies stay local to this freestanding DSO. */
__attribute__((visibility("hidden"))) void *memcpy(void *to,const void *from,size_t n) {
    unsigned char *d=to;const unsigned char *s=from;for(size_t i=0;i<n;i++)d[i]=s[i];return to;
}
__attribute__((visibility("hidden"))) void *memset(void *to,int value,size_t n) {
    unsigned char *d=to;for(size_t i=0;i<n;i++)d[i]=(unsigned char)value;return to;
}
static struct {
    uint32_t lock;
    struct a7_fl_platform platform;
    struct a7_fl_module_status status;
    struct a7_fl_context runtime;
    struct a7_fl_control control;
    struct a7_fl_store store;
    a7_menu_model model;
    a7_menu_attachment attachments[A7_FL_MODULE_PARENTS];
    a7_menu_node *pointers[A7_FL_MODULE_PARENTS][65];
    int parent_selected[A7_FL_MODULE_PARENTS];
    NativeAdjustTree trees[A7_FL_MODULE_PARENTS];
    unsigned attached,bound;
} module;
static void snapshot(int error) {
    module.status.last_error=error;module.status.parents=module.attached;
    module.status.mode=module.runtime.state;module.status.dirty=module.control.dirty;
    module.status.generation=module.control.committed.generation;
    for(unsigned i=0;i<8;i++)module.status.parameters[i]=module.control.preference.parameters[i];
    if(module.control.fault)module.status.fault=1;
}
static int leave(int rc) {snapshot(rc);__atomic_store_n(&module.lock,0,__ATOMIC_RELEASE);return rc;}
static int enter(void) {return __atomic_exchange_n(&module.lock,1,__ATOMIC_ACQUIRE)==0;}
const struct a7_fl_module_status *a7_fl_status(void) {return &module.status;}
static int readable(uintptr_t p,unsigned n) {return module.platform.readable(module.platform.opaque,p,n)==1;}
static int witnesses(enum a7_fl_platform_event event) {
    struct a7_fl_platform *p=&module.platform;
    return p->identity(p->opaque)==1 && p->event(p->opaque,event)==1;
}
static int capture_set(int mode) {
#ifdef A7_FL_CAPTURE_CONTROLS
    if(module.platform.identity(module.platform.opaque)!=1)return A7_FL_RECOVERY_IDENTITY;
    A7FLColorParams p=capture_params(&module.control.preference);
    return a7_capture_apply(&capture_controls,mode,&p);
#elif defined(A7_FL_CAPTURE_LOOK)
    if(module.platform.identity(module.platform.opaque)!=1)return A7_FL_RECOVERY_IDENTITY;
    return a7_fl_capture_set(&module.platform.backup,capture_stock,capture_look,mode);
#else
    (void)mode;return 0;
#endif
}
static int capture_check(int mode) {
#ifdef A7_FL_CAPTURE_CONTROLS
    A7FLColorParams p=capture_params(&module.control.preference);
    return a7_capture_verify(&capture_controls,mode,&p);
#elif defined(A7_FL_CAPTURE_LOOK)
    return a7_fl_capture_check(&module.platform.backup,capture_stock,capture_look,mode);
#else
    (void)mode;return 0;
#endif
}
static int commit_checked(void) {
    int rc=capture_check(module.control.preference.enabled);
    if(rc){module.status.fault=1;return rc;}
    return a7_fl_control_commit(&module.control);
}
static int reconcile_failed_color(int error) {
#ifdef A7_FL_CAPTURE_LOOK
    int mode=module.runtime.state;
    if((mode!=0 && mode!=1) || capture_set(mode)) {
        module.status.fault=1;return A7_FL_RECOVERY;
    }
#endif
    return error;
}
int a7_fl_prepare(const struct a7_fl_platform *p) {
    if(!p||!p->view_base||!p->manager||!p->manager_vtable||!p->parent_vtable||!p->creative_style||
       !p->identity||!p->event||!p->readable||!p->backup.size||!p->backup.attr||!p->backup.read||!p->backup.write||
       !p->storage.read||!p->storage.replace||!p->parent_count||p->parent_count>A7_FL_MODULE_PARENTS)return A7_FL_MODULE_PLATFORM;
    if(!enter())return A7_FL_MODULE_BUSY;
    if(module.status.prepared||module.status.installed)return leave(A7_FL_MODULE_PLATFORM);
    module.platform=*p;module.status.prepared=1;return leave(0);
}
static int verify_parents(void) {
    struct a7_fl_platform *p=&module.platform;
    if(!readable((uintptr_t)p->manager,4)||*(uintptr_t **)p->manager!=p->manager_vtable||
       !readable((uintptr_t)(p->manager_vtable-2),(A7_MENU_MANAGER_WORDS+2)*4)||
       !readable((uintptr_t)(p->parent_vtable-2),268))return 0;
    for(unsigned j=0;j<p->parent_count;j++) {
        a7_menu_node *node=p->parents[j];
        if(!node||!readable((uintptr_t)node,sizeof *node)||node->vtable!=p->parent_vtable||node->count<1||node->count>64||
           !readable((uintptr_t)node->children,(unsigned)node->count*4))return 0;
        for(unsigned k=0;k<j;k++)if(node==p->parents[k])return 0;
        a7_menu_node *anchor=p->anchors[j]?p->anchors[j]:p->creative_style;
        unsigned hits=0;for(int i=0;i<node->count;i++)hits+=node->children[i]==anchor;
        if(hits!=1)return 0;
    }
    return 1;
}
int a7_fl_configure_menu(const struct a7_fl_platform *p) {
    if(!p)return A7_FL_MODULE_PLATFORM;
    if(!enter())return A7_FL_MODULE_BUSY;
    struct a7_fl_platform *old=&module.platform;
    if(!module.status.prepared||module.status.installed||module.status.fault||!p->view_manager||
       !p->creative_style||!p->parent_count||p->parent_count>A7_FL_MODULE_PARENTS ||
       p->view_base!=old->view_base||p->caution_base!=old->caution_base||p->manager!=old->manager||
       p->manager_vtable!=old->manager_vtable||p->parent_vtable!=old->parent_vtable||
       p->backup.size!=old->backup.size||p->backup.attr!=old->backup.attr||p->backup.read!=old->backup.read||p->backup.write!=old->backup.write||
       p->storage.read!=old->storage.read||p->storage.replace!=old->storage.replace||p->storage.opaque!=old->storage.opaque||
       p->identity!=old->identity||p->event!=old->event||p->readable!=old->readable||p->opaque!=old->opaque)
        return leave(A7_FL_MODULE_PLATFORM);
    if(!witnesses(A7_FL_INSTALL_EVENT)||!readable((uintptr_t)p->view_manager,4))return leave(A7_FL_MODULE_WITNESS);
    struct a7_fl_platform before=*old;*old=*p;
    if(!verify_parents()){*old=before;return leave(A7_FL_MODULE_PARENT);}
    return leave(0);
}
static int accept_applied(void *unused,unsigned field,int value) {(void)unused;(void)field;(void)value;return 1;}
static void save_feedback(uint32_t title) {
    for(unsigned j=0;j<module.platform.parent_count;j++)
        (void)native_adjust_save_title(&module.trees[j],title);
}
static int synchronize(void) {
    for(unsigned j=0;j<module.platform.parent_count;j++) {
        if(!native_adjust_write(&module.trees[j],0x7000,module.control.preference.enabled,accept_applied,0))return 0;
        for(unsigned f=0;f<8;f++)
            if((A7_FL_EDITABLE_MASK&(1u<<f))&&
               !native_adjust_write(&module.trees[j],0x7001+(int)f,module.control.preference.parameters[f],accept_applied,0))return 0;
    }
    return 1;
}
static int model_read(void *unused,int id,int *value) {
    (void)unused;if(!module.status.installed||module.status.fault||!value)return 0;
    if(id==0x7000)return native_adjust_encode(&module.trees[0],id,module.control.preference.enabled,value);
    unsigned f=(unsigned)(id-0x7001);if(f>=8)return 0;
    /* Native SettingMenu reserves -1 as a missing-value sentinel. The UI uses
     * nonnegative selection enums; signed values belong only to our backend. */
    return native_adjust_encode(&module.trees[0],id,module.control.preference.parameters[f],value);
}
static int model_write(void *unused,int id,int value) {
    (void)unused;if(!enter())return 0;
    if(!module.status.installed||module.status.fault) {leave(A7_FL_MODULE_PLATFORM);return 0;}
    int decoded;
    if(!native_adjust_decode(&module.trees[0],id,value,&decoded)) {leave(A7_FL_CONTROL_ARGUMENT);return 0;}
#ifdef A7_FL_CAPTURE_CONTROLS
    if(id>=0x7000&&id<=0x7005) {
        int rc=capture_check(module.control.preference.enabled);
        struct a7_fl_preference next=module.control.preference;
        if(id==0x7000)next.enabled=decoded;else next.parameters[id-0x7001]=decoded;
        A7FLColorParams p=capture_params(&next);
        if(!rc&&module.platform.identity(module.platform.opaque)!=1)rc=A7_FL_RECOVERY_IDENTITY;
        if(!rc)rc=a7_capture_apply(&capture_controls,next.enabled,&p);
        if(rc){module.status.fault=1;leave(rc);return 0;}
    }
#else
    if(id==0x7000) {
        int rc=capture_check(module.control.preference.enabled);
        if(!rc && decoded!=module.control.preference.enabled)rc=capture_set(decoded);
        if(rc){module.status.fault=1;leave(rc);return 0;}
    }
#endif
    int accepted=native_adjust_write(&module.trees[0],id,decoded,a7_fl_control_preview,&module.control);
    if(!accepted) {leave(reconcile_failed_color(module.control.last_error));return 0;}
    if(!synchronize()) {module.status.fault=1;leave(A7_FL_MODULE_NODES);return 0;}
    if(module.control.dirty)save_feedback(0x0204eaab); /* Save */
    leave(0);return 1;
}
static int save_commit(void) {
    if(!enter())return A7_FL_MODULE_BUSY;
    if(!module.status.installed||module.status.fault||module.platform.identity(module.platform.opaque)!=1) {
        return leave(A7_FL_MODULE_EVENT);
    }
    /* This callback is bound only to the native execProc slot for our explicit
     * Save node. It is never reached by scalar preview setters. External confirm
     * remains separately witness-gated and may be disabled by the bootstrap. */
    int rc=commit_checked();
    /* The native action handler marks the model changed and refreshes the row.
     * Only a successful durable commit may show Complete; edits restore Save. */
    save_feedback(rc?0x0204ef87:0x0204ef85); /* Not Complete / Complete */
    return leave(rc);
}
static int model_action(void *unused,int id) {
    (void)unused;if(id!=0x7009)return 0;
#ifdef A7_FL_SAVE_DIALOG
    if(!enter())return 0;
    if(!module.status.installed||module.status.fault||module.platform.identity(module.platform.opaque)!=1) {
        leave(A7_FL_MODULE_EVENT);return 0;
    }
    int rc=a7_fl_dialog_open(module.platform.view_base,module.platform.view_manager,save_commit);
    return leave(rc)==0;
#else
    return save_commit()==0;
#endif
}
static int rollback(void) {
    int error=0;
    while(module.attached) {
        unsigned j=module.attached-1;a7_menu_node *parent=module.attachments[j].parent;
        if(a7_menu_detach(&module.attachments[module.attached-1])<0) {error=1;break;}
        module.attached--;
        /* Insertion initialization shifted stock sibling indices. Once exact
         * detach succeeds, native re-init restores the original ordering too.
         * A clone-changed child array fails detach above: keep all storage alive
         * and require restart/reconciliation rather than freeing guessed owners. */
        typedef int (*Init)(a7_menu_node *,a7_menu_node **,int,int);
        if(parent->depth>0 && !((Init)parent->vtable[0xf8/4])(parent,0,0,parent->depth))error=1;
        parent->selected=module.parent_selected[j];module.trees[j].root.parent=0;
    }
    if(!module.attached && module.bound) {
        if(a7_menu_unbind_model(&module.model)<0)error=1;else module.bound=0;
    }
    if(module.runtime.initialized && a7_fl_set(&module.runtime,0))error=1;
    if(module.runtime.initialized && capture_set(0))error=1;
    module.status.installed=0;
    if(error)module.status.fault=1;
    return error?A7_FL_MODULE_ROLLBACK:0;
}
static int initialize_color(void) {
    if(module.status.runtime_ready)return 0;
    if(module.runtime.initialized)return A7_FL_MODULE_PLATFORM;
    struct a7_fl_preference preference;int present=0;
    if(a7_fl_store_open(&module.store,&module.platform.storage,a7_pkg_original_sha,a7_pkg_build,&preference,&present))return A7_FL_MODULE_STORE;
    if(!present) {
        preference.generation=1;preference.enabled=0;
        for(unsigned i=0;i<8;i++)preference.parameters[i]=i==6?1:0;
        preference.candidate_crc=a7_fl_crc(a7_pkg_base,1280);
    }
    A7FLColorParams parameters={preference.parameters[0],preference.parameters[1],preference.parameters[2],preference.parameters[3],preference.parameters[4]};
    uint8_t candidate[1280];
    if(a7_fl_adjust_lut(a7_pkg_base,1280,a7_pkg_expand,a7_pkg_compress,&parameters,candidate,1280)||
       a7_fl_crc(candidate,1280)!=preference.candidate_crc)return A7_FL_TABLE;
    struct a7_fl_recovery recovery={0};
    recovery.api=&module.platform.backup;
    for(unsigned i=0;i<4;i++){recovery.original[i]=a7_pkg_original[i];recovery.original_crc[i]=a7_pkg_original_crc[i];}
    recovery.base_fl=a7_pkg_base;recovery.base_fl_crc=a7_pkg_base_crc;recovery.expand=a7_pkg_expand;recovery.compress=a7_pkg_compress;
    recovery.identity_guard=module.platform.identity;recovery.identity_context=module.platform.opaque;
#ifdef A7_FL_CAPTURE_CONTROLS
    int prepared=a7_capture_prepare(&capture_controls,&module.platform.backup,capture_stock,capture_look,a7_pkg_expand,a7_pkg_compress);
    if(prepared)return prepared;
    prepared=a7_capture_adopt(&capture_controls,&parameters);if(prepared)return prepared;
    for(unsigned i=0;i<2;i++)recovery.capture_alternate[i]=capture_controls.current[i];
#elif defined(A7_FL_CAPTURE_LOOK)
    for(unsigned i=0;i<2;i++)recovery.capture_alternate[i]=capture_look[i];
#endif
    int recognized[5],rc=a7_fl_restore_baseline(&recovery,recognized);
    if(rc<0)return rc;
    rc=a7_fl_init(&module.runtime,&module.platform.backup,a7_pkg_original[0],a7_pkg_original_crc[0],candidate,preference.candidate_crc);
    if(rc)return rc;
    if(!present && a7_fl_store_save(&module.store,&preference))return A7_FL_MODULE_STORE;
    rc=a7_fl_set(&module.runtime,preference.enabled);if(rc)return rc;
    rc=a7_fl_control_init(&module.control,&module.runtime,a7_pkg_base,a7_pkg_expand,a7_pkg_compress,&preference,a7_fl_store_save,&module.store);
    if(rc){rollback();return rc;}
    rc=capture_set(preference.enabled);
    if(rc){int restored=rollback();return restored?restored:rc;}
    module.status.runtime_ready=1;return 0;
}
int a7_fl_initialize_color_prepared(void) {
    if(!enter())return A7_FL_MODULE_BUSY;
    if(!module.status.prepared||module.status.fault)return leave(A7_FL_MODULE_PLATFORM);
    if(!witnesses(A7_FL_BOOT_EVENT))return leave(A7_FL_MODULE_WITNESS);
    int rc=initialize_color();
    if(rc && module.runtime.initialized)module.status.fault=1;
    return leave(rc);
}
int a7_fl_install_prepared(uintptr_t view_base,void *view_manager) {
    if(!enter())return A7_FL_MODULE_BUSY;
    if(!module.status.prepared||module.status.fault||view_base!=module.platform.view_base||!view_manager||
       (module.platform.view_manager && view_manager!=module.platform.view_manager))return leave(A7_FL_MODULE_PLATFORM);
    if(module.status.installed)return leave(0);
    if(!witnesses(A7_FL_INSTALL_EVENT))return leave(A7_FL_MODULE_WITNESS);
    if(!readable((uintptr_t)view_manager,4)||!verify_parents())return leave(A7_FL_MODULE_PARENT);
    module.platform.view_manager=view_manager;
    int rc=initialize_color();
    if(rc){if(module.runtime.initialized)module.status.fault=1;return leave(rc);}
    struct a7_fl_preference preference=module.control.preference;
    NativeAdjustSpec specs[8];
    for(unsigned f=0;f<8;f++) {
        specs[f].title=0x0204fda0+f;specs[f].help=0x0204fd9f;
        specs[f].minimum=f==3||f==7?0:f==6?1:f==5?-3:-9;
        specs[f].maximum=f==6?5:f==5?3:9;specs[f].initial=preference.parameters[f];
    }
    for(unsigned j=0;j<module.platform.parent_count;j++) {
        if(!native_adjust_build(&module.trees[j],module.platform.caution_base,0x0204fd9e,0x0204fd9f,0x0204fd9f,specs,A7_FL_EDITABLE_MASK)) {
            rollback();return leave(A7_FL_MODULE_NODES);
        }
        if(!native_adjust_add_save(&module.trees[j],0x0204eaab)){rollback();return leave(A7_FL_MODULE_NODES);}
    }
    if(!synchronize()){rollback();return leave(A7_FL_MODULE_NODES);}
    rc=a7_menu_bind_model(&module.model,module.platform.manager,module.platform.manager_vtable,model_read,model_write,0);
    if(rc!=1){rollback();return leave(A7_FL_MODULE_MODEL);}module.bound=1;
    if(a7_menu_bind_action(&module.model,0x7009,model_action)!=1){rollback();return leave(A7_FL_MODULE_MODEL);}
    for(unsigned j=0;j<module.platform.parent_count;j++) {
        module.parent_selected[j]=module.platform.parents[j]->selected;
        a7_menu_node *anchor=module.platform.anchors[j]?module.platform.anchors[j]:module.platform.creative_style;
        rc=a7_menu_attach(&module.attachments[j],module.platform.parents[j],anchor,
                         (a7_menu_node *)&module.trees[j].root,module.pointers[j],65);
        if(rc!=1){rollback();return leave(A7_FL_MODULE_ATTACH);}module.attached++;
    }
    /* The verified install seam is before SettingMenu construction while idle.
     * Its later UserInitialize initializes pages: for a warm graph invoke the native
     * four-argument deep init to fix parent/depth/indices, including stock
     * siblings following our new entry. It may create native owning clones. */
    for(unsigned j=0;j<module.platform.parent_count;j++) {
        a7_menu_node *parent=module.platform.parents[j];
        /* At a cold first MENU, original main-graph initialization occurs later
         * in ViewSettingMenu. Its verified constructor-state templates must
         * remain uninitialized so the stock root assigns the actual ancestry. */
        if(parent->depth==0 && !parent->parent && parent->state==0)continue;
        typedef int (*Init)(a7_menu_node *,a7_menu_node **,int,int);
        if(!((Init)parent->vtable[0xf8/4])(parent,0,0,parent->depth)) {
            module.status.fault=1;rollback();return leave(A7_FL_MODULE_NODES);
        }
    }
    if(!synchronize()){module.status.fault=1;rollback();return leave(A7_FL_MODULE_NODES);}
    module.status.installed=1;return leave(0);
}
int a7_fl_confirm(void) {
    if(!enter())return A7_FL_MODULE_BUSY;
    if(!module.status.installed||module.status.fault)return leave(A7_FL_MODULE_PLATFORM);
    if(!witnesses(A7_FL_CONFIRM_EVENT))return leave(A7_FL_MODULE_EVENT);
    return leave(commit_checked());
}
int a7_fl_cancel(void) {
    if(!enter())return A7_FL_MODULE_BUSY;
    if(!module.status.installed||module.status.fault)return leave(A7_FL_MODULE_PLATFORM);
    if(!witnesses(A7_FL_CANCEL_EVENT))return leave(A7_FL_MODULE_EVENT);
    int rc=capture_check(module.control.preference.enabled);
#ifdef A7_FL_CAPTURE_CONTROLS
    if(!rc&&module.control.dirty) {
        A7FLColorParams p=capture_params(&module.control.committed);
        rc=a7_capture_apply(&capture_controls,module.control.committed.enabled,&p);
    }
#else
    if(!rc && module.control.dirty && module.control.preference.enabled!=module.control.committed.enabled)
        rc=capture_set(module.control.committed.enabled);
#endif
    if(rc){module.status.fault=1;return leave(rc);}
    rc=a7_fl_control_cancel(&module.control);
    if(rc)rc=reconcile_failed_color(rc);
    if(!rc&&!synchronize()){module.status.fault=1;rc=A7_FL_MODULE_NODES;}
    return leave(rc);
}
int a7_fl_uninstall(void) {
    if(!enter())return A7_FL_MODULE_BUSY;
    if(!module.status.installed)return leave(A7_FL_MODULE_PLATFORM);
    if(!witnesses(A7_FL_UNINSTALL_EVENT))return leave(A7_FL_MODULE_EVENT);
    return leave(rollback());
}
