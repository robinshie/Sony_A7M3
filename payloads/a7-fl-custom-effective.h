#ifndef A7_FL_CUSTOM_EFFECTIVE_H
#define A7_FL_CUSTOM_EFFECTIVE_H
#include "a7-fl-custom.h"
#include "a7-fl-runtime-prefs.h"
/* Build an isolated working copy for the existing LUT and capture generators.
 * Never save this working copy into the six built-in preference slots.
 * The caller must regenerate candidate_crc before applying it. */
int a7_custom_effective(const struct a7_custom_catalog*,uint32_t,
 const struct a7_fl_preference*,struct a7_fl_preference*);
#endif
