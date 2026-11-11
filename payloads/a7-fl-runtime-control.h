/* NativeAdjust callback adapter. The installer owns boot reconciliation and I/O. */
#ifndef A7_FL_RUNTIME_CONTROL_H
#define A7_FL_RUNTIME_CONTROL_H
#include "a7-fl-runtime.h"
#include "a7-fl-runtime-prefs.h"
enum a7_fl_control_error {
    A7_FL_CONTROL_OK=0, A7_FL_CONTROL_ARGUMENT=-20,
    A7_FL_CONTROL_BIND=-21, A7_FL_CONTROL_UNSUPPORTED=-22,
    A7_FL_CONTROL_GENERATION=-23, A7_FL_CONTROL_PERSIST=-24,
    A7_FL_CONTROL_RECOVERY_PERSIST=-25, A7_FL_CONTROL_FAULT=-26
};
struct a7_fl_control {
    uint32_t lock,initialized,fault,dirty;
    int last_error,apply_error;
    struct a7_fl_context *runtime;
    /* Immutable module-owned inputs must outlive this adapter. */
    const uint8_t *base_fl,*compress;
    const uint16_t *expand;
    struct a7_fl_preference preference;
    struct a7_fl_preference committed;
    /* Return zero only after durable record write and exact file readback. */
    int (*store)(void *,const struct a7_fl_preference *);
    void *store_context;
};
/* Zero-initialized context required. Initial preference/table must ALREADY have
 * been reconciled at boot, including generation, mode and all parameters.
 * This reads/verifies only, never writes a preference or backup property.
 * Returns zero on success. Sharpness, range and clarity are carried but disabled.
 */
int a7_fl_control_init(struct a7_fl_control *,struct a7_fl_context *,
                       const uint8_t base_fl[1280],const uint16_t expand[129],
                       const uint8_t compress[513],const struct a7_fl_preference *,
                       int (*store)(void *,const struct a7_fl_preference *),void *);
/* Compatible with native_adjust_write: 1 accepted, 0 rejected. Field0..4 are
 * scalar LUT controls, field8 is Off/FL. Field5..7 always reject. Apply failure
 * faults this adapter after restoring baseline and recording Off if possible.
 * Caller must refresh mode to runtime->state and disable controls on fault;
 * do not leave a stale ON indicator after a failed backend transaction.
 */
int a7_fl_control_apply(void *,unsigned field,int value);
/* Preview-compatible native_adjust callback: 1 accepted, 0 rejected. Never
 * invokes store. It changes backup RAM and updates preference, preserving the
 * last durable record in committed. Recovery must recognize historic generated
 * candidates because unrelated native saves may serialize a transient preview.
 */
int a7_fl_control_preview(void *,unsigned field,int value);
/* Explicit confirmed-selection hook only. Returns zero on success. No backup
 * RAM write occurs here. Store failure leaves a dirty, uncommitted preview;
 * caller must keep the dialog open or cancel, not report a committed setting. */
int a7_fl_control_commit(struct a7_fl_control *);
/* Cancel/dispose hook restores committed values in RAM without filesystem I/O.
 * Returns zero on success. Calling it on a faulted adapter requires reconciliation. */
int a7_fl_control_cancel(struct a7_fl_control *);
#endif
