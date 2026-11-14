#include "native_menu.h"

static a7_menu_model *bound;
typedef int (*native_get)(void *, int, int *);
typedef int (*native_set)(void *, int, int);
typedef int (*native_action)(void *, int);

static int custom(int id) {
#ifdef A7_FL_FILM_CONTROLS
    if(id>=0x700a&&id<=0x700e)return 1;
#endif
    return id >= A7_MENU_PROCESS_FIRST && id <= A7_MENU_PROCESS_LAST;
}

static int menu_get(void *manager, int id, int *value) {
    a7_menu_model *m = bound;
    if (!m || manager != m->manager) return 0;
    if (custom(id)) return value && m->read(m->opaque, id, value) == 1;
    return ((native_get)m->before[0x0c / 4])(manager, id, value);
}

static int menu_set(void *manager, int id, int value) {
    a7_menu_model *m = bound;
    if (!m || manager != m->manager) return 0;
    if (custom(id)) return m->write(m->opaque, id, value) == 1;
    return ((native_set)m->before[0x44 / 4])(manager, id, value);
}

static int menu_action(void *manager, int id) {
    a7_menu_model *m = bound;
    if (!m || manager != m->manager) return 0;
    if (id == m->action_id && m->action)
        return m->action(m->opaque, id) == 1;
    return ((native_action)m->before[0x54 / 4])(manager, id);
}

int a7_menu_bind_action(a7_menu_model *m, int id, a7_menu_action action) {
    if (!m || bound != m || !m->manager || !action ||
        id <= A7_MENU_PROCESS_LAST || id > 0x7fff || custom(id) ||
        *(uintptr_t **)m->manager != m->table + 2) return -1;
    if (!m->before[0x54 / 4]) return -2;
    m->action_id = id;
    m->action = action;
    m->table[2 + 0x54 / 4] = (uintptr_t)menu_action;
    return 1;
}

int a7_menu_bind_model(a7_menu_model *m, void *manager, uintptr_t *expected,
                       a7_menu_read read, a7_menu_write write, void *opaque) {
    uintptr_t **p = manager;
    unsigned i;
    if (!m || !p || !expected || !read || !write) return -1;
    if (bound == m && m->manager == manager && *p == m->table + 2) return 0;
    if (bound || *p != expected || !expected[3] || !expected[17]) return -2;
    for (i = 0; i < A7_MENU_MANAGER_WORDS + 2; ++i)
        m->table[i] = expected[(int)i - 2];
    m->manager = manager; m->before = expected;
    m->read = read; m->write = write; m->opaque = opaque;
    m->action = 0; m->action_id = -1;
    m->table[2 + 3] = (uintptr_t)menu_get;
    m->table[2 + 17] = (uintptr_t)menu_set;
    bound = m;
    *p = m->table + 2;
    return 1;
}

int a7_menu_unbind_model(a7_menu_model *m) {
    uintptr_t **p;
    if (!m || bound != m || !m->manager) return -1;
    p = m->manager;
    if (*p != m->table + 2) return -2;
    *p = m->before;
    bound = 0;
    m->manager = 0;
    return 1;
}

int a7_menu_attach(a7_menu_attachment *a, a7_menu_node *p,
                   a7_menu_node *cs, a7_menu_node *look,
                   a7_menu_node **storage, unsigned capacity) {
    int i, at = -1;
    if (!a || !p || !cs || !look || !storage || p == look || cs == look)
        return -1;
    if (p->count < 1 || p->count > 64 || !p->children) return -2;
    if (capacity < (unsigned)p->count + 1 || storage == p->children) return -3;
    for (i = 0; i < p->count; ++i) {
        if (p->children[i] == look) return 0;
        if (p->children[i] == cs) {
            if (at >= 0) return -4;
            at = i;
        }
    }
    if (at < 0) return -5;
    for (i = 0; i <= at; ++i) storage[i] = p->children[i];
    storage[at + 1] = look;
    for (i = at + 1; i < p->count; ++i) storage[i + 1] = p->children[i];
    a->parent = p; a->inserted = look; a->before = p->children;
    a->after = storage; a->before_count = p->count;
    p->children = storage;
    p->count += 1;
    return 1;
}

int a7_menu_detach(a7_menu_attachment *a) {
    a7_menu_node *p;
    int i, n = 0;
    if (!a || !(p = a->parent)) return -1;
    if (p->children != a->after || p->count != a->before_count + 1) return -2;
    for (i = 0; i < p->count; ++i) {
        if (p->children[i] == a->inserted) ++n;
        else if (i - n >= a->before_count || p->children[i] != a->before[i - n])
            return -3;
    }
    if (n != 1) return -4;
    p->children = a->before; p->count = a->before_count;
    a->parent = 0;
    return 1;
}

int a7_menu_find_parents(void *bss, size_t bytes, uintptr_t *vtable,
                         const void *start, const void *end,
                         a7_menu_node *cs, a7_menu_node **out, unsigned cap) {
    uintptr_t at = (uintptr_t)bss, stop, lo = (uintptr_t)start, hi = (uintptr_t)end;
    unsigned found = 0;
    if (!bss || !vtable || !cs || !out || bytes < sizeof(a7_menu_node) || hi <= lo)
        return -2;
    stop = at + bytes - sizeof(a7_menu_node);
    if (stop < at || (at % sizeof(uintptr_t))) return -2;
    for (; at <= stop; at += sizeof(uintptr_t)) {
        a7_menu_node *p = (a7_menu_node *)at;
        uintptr_t children;
        unsigned i, hits = 0;
        if (p->vtable != vtable || p->count < 1 || p->count > 64) continue;
        children = (uintptr_t)p->children;
        if (children < lo || children >= hi || children % sizeof(uintptr_t) ||
            (size_t)p->count > (hi - children) / sizeof(uintptr_t)) continue;
        for (i = 0; i < (unsigned)p->count; ++i) hits += p->children[i] == cs;
        if (hits != 1) continue;
        if (found == cap) return -1;
        out[found++] = p;
    }
    return (int)found;
}
