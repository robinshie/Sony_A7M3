#ifndef A7_FL_PREVIEW_CYCLE_H
#define A7_FL_PREVIEW_CYCLE_H
#include "a7-fl-preview.h"
enum { A7_FL_PREVIEW_TIMER=-156,A7_FL_PREVIEW_LIBRARY=-157 };
/* Timing/request evidence only. Neither counter is an ISP/frame acknowledgement. */
struct a7_fl_preview_cycle_report {
    uint32_t pending,restored,coalesced;
    int restore_result,temporary_style;
};
const struct a7_fl_preview_cycle_report *a7_fl_preview_cycle_status(void);
#endif
