#ifndef A7_FL_INSPECT_H
#define A7_FL_INSPECT_H
#include "a7-fl-bootstrap.h"
#include "a7-fl-module.h"
enum a7_fl_inspect_error {
    A7_FL_INSPECT_NOT_LOADED=0,A7_FL_INSPECT_LOADED=1,
    A7_FL_INSPECT_IDENTITY=-1,A7_FL_INSPECT_PINS=-2,
    A7_FL_INSPECT_NOLOAD=-3,A7_FL_INSPECT_SYMBOL=-4,
    A7_FL_INSPECT_POINTER=-5,A7_FL_INSPECT_UNSTABLE=-6,
    A7_FL_INSPECT_CLOSE=-7
};
struct a7_fl_inspect_report {
    uint32_t magic,version;
    int32_t status;
    uint32_t view_base,module_base,bootstrap_symbol,runtime_symbol;
    int32_t dlclose_result;
    uint32_t bootstrap_bytes,runtime_bytes,stable;
    struct a7_fl_bootstrap_report bootstrap;
    struct a7_fl_module_status runtime;
};
/* Reads an already loaded module only. RTLD_NOLOAD, exact status-only symbol
 * names/code pins, owned mapping checks and balanced dlclose. No install calls. */
int a7_fl_inspect_read(struct a7_fl_inspect_report *);
#endif
