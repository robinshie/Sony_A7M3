/* Native model replay, not an acknowledgement that the ISP has refreshed. */
#ifndef A7_FL_PREVIEW_H
#define A7_FL_PREVIEW_H
#include "a7-fl-runtime.h"
enum { A7_FL_PREVIEW_ARGUMENT=-150,A7_FL_PREVIEW_PIN=-151,
       A7_FL_PREVIEW_READ=-152,A7_FL_PREVIEW_VALUE=-153,
       A7_FL_PREVIEW_ALLOC=-154,A7_FL_PREVIEW_CHANGED=-155 };
/* Returns 1 once the original asynchronous request wrapper was called.
 * Does not write Creative Style preferences or change its active values. */
int a7_fl_preview_request(uintptr_t,const struct a7_fl_api *,
                         int (*readable)(void *,uintptr_t,unsigned),void *);
struct a7_fl_preview_report { uint32_t attempts,issued; int last_result,active[4]; };
const struct a7_fl_preview_report *a7_fl_preview_status(void);
#endif
