#ifndef A7_FL_SHARPNESS_NATIVE_H
#define A7_FL_SHARPNESS_NATIVE_H
#include <stdint.h>
/* Caller pins exact view library, model/build, and thread/lifecycle context.
 * This calls the queue API for one native parameter. Return 1 means only that
 * the call was made, NOT acknowledged or completed. Read active sharpness
 * separately. Stock style/slot preset bytes are untouched.
 */
int a7_fl_sharpness_request(uintptr_t view_base,int value);
#endif
