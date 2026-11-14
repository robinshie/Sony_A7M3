/* Exact historical-candidate recognition; no arbitrary calibration overwrite. */
#ifndef A7_FL_RUNTIME_RECOVERY_H
#define A7_FL_RUNTIME_RECOVERY_H
#include "a7-fl-runtime.h"
struct a7_fl_recovery {
    const struct a7_fl_api *api;
    const uint8_t *original[4];
    uint32_t original_crc[4];
    const uint8_t *base_fl,*compress;
    const uint16_t *expand;
    uint32_t base_fl_crc;
#ifdef A7_FL_DUAL_LOOK
    const uint8_t *base_cinema;
#ifdef A7_FL_LEICA_LOOK
    const uint8_t *base_leica;
#endif
#endif
    /* Must verify this camera identity AND firmware build against the immutable
     * package; 1 verified, any other result refuses all writes. */
    int (*identity_guard)(void *);
    void *identity_context;
    /* Exact optional, immutable alternate preimages for LUT1 and LUT2. */
    const uint8_t *capture_alternate[2];
};
enum a7_fl_recovery_error {
    A7_FL_RECOVERY_IDENTITY=-30, A7_FL_RECOVERY_OTHER_TABLE=-31,
    A7_FL_RECOVERY_UNRECOGNIZED=-32
};
/* Returns 1 only if every byte is reproducible by this exact base/codec/five-
 * control generator. Returns 0 for a foreign table, negative for bad inputs.
 * The family search is bounded by 19 chroma + 68,590 tone candidates and uses
 * early rejection. No watermark, table-tail change, filesystem or device I/O.
 */
int a7_fl_recognize(const uint8_t table[1280],const uint8_t base_fl[1280],
                    const uint16_t expand[129],const uint8_t compress[513],
                    int parameters[5],unsigned *tone_trials);
/* Startup/reconciliation only, before installing UI callbacks. Checks identity,
 * original/base CRCs, exact LUT1..3, original tail and exact generated LUT0
 * membership. Rechecks identity/other tables/current preimage immediately before
 * writing original LUT0. Returns 0 already original, 1 restored, negative failure.
 * There is no exposed native compare-and-swap; caller must serialize this with
 * its own feature and ensure another calibration writer is not active.
 */
int a7_fl_restore_baseline(const struct a7_fl_recovery *,int recognized_parameters[5]);
#endif
