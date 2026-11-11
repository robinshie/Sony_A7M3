/* Native 4.04 setting-node adapter. No firmware bytes and no device I/O. */
#ifndef NATIVE_ADJUST_H
#define NATIVE_ADJUST_H
#include <stdint.h>

#define NATIVE_ADJUST_FIELDS 8
#define NATIVE_ADJUST_VALUES 31
#define NATIVE_ADJUST_ID_FIRST 0x7001
#define NATIVE_ADJUST_SAVE_ID 0x7009
enum NativeAdjustField {
    NA_CONTRAST, NA_HIGHLIGHTS, NA_SHADOWS, NA_FADE, NA_SATURATION,
    NA_SHARPNESS, NA_SHARPNESS_RANGE, NA_CLARITY, NA_MODE
};
typedef struct { int key, type; uint32_t value; } NativeAdjustProperty;
/* The second member is the inclusive last index, NOT the element count. */
typedef struct { const NativeAdjustProperty *list; int last; } NativeAdjustProperties;
typedef struct NativeAdjustNode NativeAdjustNode;
struct NativeAdjustNode {
    const uintptr_t *vtable;
    NativeAdjustNode **children;
    int count;
    const NativeAdjustProperties *properties;
    NativeAdjustNode *parent;
    int depth, selected_index, selectable_index, index, state;
};
typedef struct {
    uint32_t title, help;
    int minimum, maximum, initial;
} NativeAdjustSpec;
typedef struct {
    /* Original RTTI prefix + 65 slots + owner pointer. Heap-clone table retains
     * owning destructors; both tables restore capability grayout after init. */
    uintptr_t node_vtable[68], clone_vtable[68];
    NativeAdjustNode root, mode, mode_values[2], fields[NATIVE_ADJUST_FIELDS], save;
    NativeAdjustNode values[NATIVE_ADJUST_FIELDS][NATIVE_ADJUST_VALUES];
    NativeAdjustNode *field_ptrs[NATIVE_ADJUST_FIELDS+2], *mode_ptrs[2];
    NativeAdjustNode *value_ptrs[NATIVE_ADJUST_FIELDS][NATIVE_ADJUST_VALUES];
    NativeAdjustProperty root_props[4], field_props[NATIVE_ADJUST_FIELDS][5];
    NativeAdjustProperty mode_props[5], mode_value_props[2][6];
    NativeAdjustProperty save_props[5];
    NativeAdjustProperty value_props[NATIVE_ADJUST_FIELDS][NATIVE_ADJUST_VALUES][6];
    NativeAdjustProperties root_properties, field_properties[NATIVE_ADJUST_FIELDS];
    NativeAdjustProperties mode_properties, mode_value_properties[2];
    NativeAdjustProperties save_properties;
    NativeAdjustProperties value_properties[NATIVE_ADJUST_FIELDS][NATIVE_ADJUST_VALUES];
    NativeAdjustSpec specs[NATIVE_ADJUST_FIELDS];
    unsigned enabled_mask;
    int current[NATIVE_ADJUST_FIELDS];
    int current_mode;
    uintptr_t caution_base;
} NativeAdjustTree;

/* Call only after the original CautionConfig.so has been relocated/initialized.
 * The owner must keep the tree alive. Its vtable overrides D0/D1 for embedded
 * storage; native heap clones keep original owning destructors. One tree
 * must not be attached to two parents at the same time without original init
 * cloning it. Never bypass vtable dispatch to call stock D0/D1 on embedded data.
 * title/help are real registered resource IDs supplied by the integration.
 * Supported numeric resources are -15..+15; broader ranges are rejected.
 */
int native_adjust_build(NativeAdjustTree *, uintptr_t caution_base,
                        uint32_t title, uint32_t help, uint32_t fl_title,
                        const NativeAdjustSpec specs[NATIVE_ADJUST_FIELDS],
                        unsigned enabled_mask);
/* Append an explicit native action row before attachment or cloning. The stock
 * Save resource is 0x0204eaab. Process 0x7009 uses execution type 4, not a scalar
 * setter; integration must handle its original execProc dispatch explicitly.
 * Rejects a second append or a tree already attached to a parent. */
int native_adjust_add_save(NativeAdjustTree *, uint32_t title_resid);
/* Callbacks for the custom process-data IDs, not stock PP IDs. A successful
 * setter means the real backend accepted the change. Disabled fields reject.
 * Backend updates happen BEFORE state/cursor commits; errors preserve them.
 * Mode ID 0x7000 invokes apply(ctx, NA_MODE, 0 or 1), for Off or FL.
 */
int native_adjust_read(const NativeAdjustTree *, int process_id, int *value);
int native_adjust_write(NativeAdjustTree *, int process_id, int value,
                        int (*apply)(void *, unsigned field, int value), void *ctx);
uint32_t native_adjust_number_resid(int value);
#endif
