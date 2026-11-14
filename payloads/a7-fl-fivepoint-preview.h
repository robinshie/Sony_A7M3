#ifndef A7_FL_FIVEPOINT_PREVIEW_H
#define A7_FL_FIVEPOINT_PREVIEW_H
#include "a7-fl-color.h"
/* Compose the existing color recipe and curve into a preview candidate.
 * No hardware writes; output is unchanged if either pass fails. */
int a7_fl_fivepoint_preview(const uint8_t base[1280],const uint16_t expand[129],
                           const uint8_t compress[513],const A7FLColorParams *,
                           const int controls[5],uint8_t out[1280]);
#endif
