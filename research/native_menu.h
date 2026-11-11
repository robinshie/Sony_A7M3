/* A7M3 4.04 native node insertion and process-manager adapter.
 * No constructor, filesystem write, USB access or code-memory patch.
 * Caller must bind verified live objects while the menu is idle. */
#ifndef A7_NATIVE_MENU_H
#define A7_NATIVE_MENU_H
#include <stdint.h>
#include <stddef.h>

#define A7_MENU_PROCESS_FIRST 0x7000
#define A7_MENU_PROCESS_LAST  0x7008
#define A7_MENU_MANAGER_WORDS 26

typedef struct a7_menu_node {
    uintptr_t *vtable;
    struct a7_menu_node **children;
    int count;
    const void *properties;
    struct a7_menu_node *parent;
    int depth, selected, serial, index, state;
} a7_menu_node;

typedef struct {
    a7_menu_node *parent, *inserted;
    a7_menu_node **before, **after;
    int before_count;
} a7_menu_attachment;

/* Return 1 only when the output/value was successfully read/applied.
 * An unsuccessful write must leave the backend's reported state unchanged. */
typedef int (*a7_menu_read)(void *, int process_id, int *value);
typedef int (*a7_menu_write)(void *, int process_id, int value);
typedef int (*a7_menu_action)(void *, int process_id);

typedef struct {
    void *manager;
    uintptr_t *before;
    uintptr_t table[A7_MENU_MANAGER_WORDS + 2];
    a7_menu_read read;
    a7_menu_write write;
    void *opaque;
    a7_menu_action action;
    int action_id;
} a7_menu_model;

/* Caller provides persistent storage for count+1 pointers, never a stack array.
 * Returns 1 inserted, 0 already present, negative on mismatch. */
int a7_menu_attach(a7_menu_attachment *, a7_menu_node *parent,
                   a7_menu_node *creative_style, a7_menu_node *look,
                   a7_menu_node **storage, unsigned capacity);
int a7_menu_detach(a7_menu_attachment *);

/* Only the scalar get/set slots are intercepted. All other methods/IDs retain
 * original behavior. Manager table expected_va is verified before modification.
 * Only one adapter may be bound in a process. Context must outlive the binding. */
int a7_menu_bind_model(a7_menu_model *, void *manager, uintptr_t *expected_va,
                       a7_menu_read, a7_menu_write, void *opaque);
int a7_menu_unbind_model(a7_menu_model *);
/* Optional explicit action, distinct from scalar preview writes. Only the
 * supplied out-of-stock process ID is intercepted in original execProc slot.
 * Install while idle, before exposing the corresponding action node. */
int a7_menu_bind_action(a7_menu_model *, int process_id, a7_menu_action);

/* Identify initialized generic main-menu parents in a known mapped BSS span.
 * Reads children only inside the supplied file-backed view2 data interval.
 * Does not modify any object. Returns count, -1 if output capacity is exceeded.
 * A runtime installer still needs to verify the active menu layout/capacity. */
int a7_menu_find_parents(void *bss, size_t bytes, uintptr_t *base_node_vtable,
                         const void *data_start, const void *data_end,
                         a7_menu_node *creative_style,
                         a7_menu_node **out, unsigned capacity);
#endif
