#ifndef A7_FL_CAPTURE_H
#define A7_FL_CAPTURE_H
#include "a7-fl-runtime.h"

/* Table order is Adobe RGB (0x30005), sRGB (0x30006). Both full 1280-byte
 * originals and candidates are supplied by the identity-pinned package. The
 * caller must serialize access with the FL module and verify camera identity.
 * These routines check Backup bytes, not the ISP shadow or image output. */
int a7_fl_capture_check(const struct a7_fl_api *api,
                        const uint8_t *const stock[2],
                        const uint8_t *const candidate[2], int expected);
/* expected=-1 accepts each known table independently, including a mixed state. */

/* On failure, restore and verify the exact preimage of each touched table.
 * Unknown bytes are never overwritten even during rollback. A7_FL_RECOVERY
 * signals that the complete previous state could not be verified. */
int a7_fl_capture_set(const struct a7_fl_api *api,
                      const uint8_t *const stock[2],
                      const uint8_t *const candidate[2], int enabled);
#endif
