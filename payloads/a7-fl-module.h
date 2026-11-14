/* Resident integration, with an explicit platform-evidence boundary. */
#ifndef A7_FL_MODULE_H
#define A7_FL_MODULE_H
#include "a7-fl-runtime.h"
#include "a7-fl-store.h"
#include "native_menu.h"
#define A7_FL_MODULE_PARENTS 8u
enum a7_fl_module_error {
    A7_FL_MODULE_PLATFORM=-100,A7_FL_MODULE_WITNESS=-101,A7_FL_MODULE_PARENT=-102,
    A7_FL_MODULE_STORE=-103,A7_FL_MODULE_NODES=-104,A7_FL_MODULE_MODEL=-105,
    A7_FL_MODULE_ATTACH=-106,A7_FL_MODULE_BUSY=-107,A7_FL_MODULE_EVENT=-108,
    A7_FL_MODULE_ROLLBACK=-109
};
enum a7_fl_platform_event { A7_FL_INSTALL_EVENT=0,A7_FL_CONFIRM_EVENT=1,A7_FL_CANCEL_EVENT=2,A7_FL_UNINSTALL_EVENT=3,A7_FL_BOOT_EVENT=4 };
struct a7_fl_platform {
    uintptr_t view_base,caution_base;
    void *view_manager; /* Original SettingMenu constructor argument; may be NULL before first MENU. */
    void *manager; /* ProcessDataMgr singleton used for scalar dispatch. */
    uintptr_t *manager_vtable,*parent_vtable;
    a7_menu_node *creative_style,*parents[A7_FL_MODULE_PARENTS];
    /* Optional per-page insertion anchors. Null means the Creative Style root.
     * A short existing page may append after its current final native item. */
    a7_menu_node *anchors[A7_FL_MODULE_PARENTS];
    unsigned parent_count;
    struct a7_fl_api backup;
    struct a7_fl_store_io storage;
#ifdef A7_FL_FILM_CONTROLS
    struct a7_fl_store_io film_storage;
#endif
    /* Must prove camera identity+build and stable live mappings. */
    int (*identity)(void *);
    /* Install/uninstall: verified scheduler seam, menu idle, ownership and all
     * current objects. Confirm/cancel: actual event within this feature graph.
     * A generic process setter is NOT sufficient evidence of confirmation. */
    int (*event)(void *,enum a7_fl_platform_event);
    /* Validate a range before the module follows a live native pointer. */
    int (*readable)(void *,uintptr_t,unsigned);
    void *opaque;
};
struct a7_fl_module_status {
    uint32_t prepared,installed,fault,parents,dirty,generation,runtime_ready;
    int last_error,mode,parameters[8];
};
/* Zero-success APIs. Configuration must come from verified live platform
 * bootstrap; its callback context must outlive this resident module. */
int a7_fl_prepare(const struct a7_fl_platform *);
/* After color-only boot preparation, replace only witnessed menu objects.
 * Backend/storage/base/identity callbacks and their context must be identical. */
int a7_fl_configure_menu(const struct a7_fl_platform *);
int a7_fl_install_prepared(uintptr_t view_base,void *view_manager);
/* Production bootstrap export: mode0 MENU with real ViewManager; mode1 still-
 * view entry, ignoring context. The checked dual loader owns callsite validation. */
int a7_fl_install(uintptr_t view_base,void *context,unsigned mode);
/* Verified still-view entry seam: no ViewManager and no parent access/binding.
 * Reconciles/apply saved color once. Repeated view entries leave previews alone. */
int a7_fl_initialize_color_prepared(void);
int a7_fl_confirm(void);
int a7_fl_cancel(void);
int a7_fl_uninstall(void);
const struct a7_fl_module_status *a7_fl_status(void);
#endif
