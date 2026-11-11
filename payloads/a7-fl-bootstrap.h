#ifndef A7_FL_BOOTSTRAP_H
#define A7_FL_BOOTSTRAP_H
#include <stdint.h>
struct a7_fl_bootstrap_report {
    uint32_t version,calls,mode,stage;
    int32_t result;
    uint32_t ready,view,caution,backup;
};
/* In-memory diagnostics only; no boot log or flash write. */
const struct a7_fl_bootstrap_report *a7_fl_bootstrap_status(void);
#endif
