/* Write-ahead preview records, separate from user-confirmed preferences.
 * This coordinator does not access LUTs, camera files or Sony callbacks. */
#ifndef A7_FL_WORKLOG_H
#define A7_FL_WORKLOG_H
#include "a7-fl-store.h"
#ifndef A7_FL_FILM_CONTROLS
#error Worklog requires the schema-4 film preference codec
#endif
enum a7_fl_worklog_error {
    A7_FL_WORKLOG_ARGUMENT=-1, A7_FL_WORKLOG_READ=-2,
    A7_FL_WORKLOG_UNKNOWN=-3, A7_FL_WORKLOG_HISTORY=-4,
    A7_FL_WORKLOG_CHANGED=-5, A7_FL_WORKLOG_WRITE=-6,
    A7_FL_WORKLOG_READBACK=-7, A7_FL_WORKLOG_EXHAUSTED=-8,
    A7_FL_WORKLOG_FAULT=-9
};
struct a7_fl_worklog {
    struct a7_fl_store_io io; /* caller supplies a distinct two-file namespace */
    uint8_t original_sha[32]; char build[24];
    uint8_t raw[2][129]; unsigned length[2],exists[2],valid[2];
    struct a7_fl_preference record[2];
    int latest; unsigned initialized,fault;
};
/* Work records have their own magic/CRC domain. generation is a work sequence,
 * never the generation of the separately committed A7FL user preferences.
 * Both records are exposed so a boot reconciler can regenerate exact old/new
 * tables after a power cut between writes of the three LUT properties.
 * A torn inactive record permits recognition of the intact record but blocks
 * further journal writes. Unknown existing files are never overwritten. */
int a7_fl_worklog_open(struct a7_fl_worklog *,const struct a7_fl_store_io *,
                       const uint8_t original_sha[32],const char build[24]);
/* Caller serializes all journal/LUT operations and verifies the current three
 * LUTs before calling. On 0, the next state's record is durably read back; only
 * THEN may the caller change LUT RAM. Input preference remains unchanged.
 * No LUT change is authorized by a failed prepare. Any write/readback failure
 * faults this instance: do not retry; reopen and reconcile at next startup.
 * Before another prepare, all three target tables must be applied/read back,
 * or all three restored/read back to pinned stock. Otherwise the next write
 * could discard a still-needed old endpoint. An apply failure must fault the
 * calling controller and reconcile on restart. Keep the record after success;
 * do not clear records on Save or Cancel. */
int a7_fl_worklog_prepare(struct a7_fl_worklog *,const struct a7_fl_preference *next);
/* Exact-byte recognition only. The callback must use pinned, immutable factory
 * tables/code and the record's preset/controls. It returns 0 after filling the
 * requested table (0 preview, 1/2 capture); it must not write a device or state.
 * For enabled records the preview CRC must also match the record; Off records
 * are skipped because pinned stock recognition is owned by the caller.
 * Stock-table recognition, calibration identity and rechecking before writes
 * are the boot reconciler's separate responsibilities. */
int a7_fl_worklog_recognize(const struct a7_fl_worklog *,unsigned table,
                           const uint8_t actual[1280],
                           int (*generate)(void *,const struct a7_fl_preference *,unsigned,uint8_t[1280]),void *);
/* Serialized by the owner. Generator returns pinned stock for Off.
 * write must apply only if the property still equals before, and read back
 * exactly; the coordinator also rereads all properties before advancing. */
struct a7_fl_curve_scratch {
    uint8_t before[3][1280],target[3][1280],row[1280];
};
struct a7_fl_curve_io {
    int (*generate)(void *,const struct a7_fl_preference *,unsigned,uint8_t[1280]);
    int (*read)(void *,unsigned,uint8_t[1280]);
    int (*write)(void *,unsigned,const uint8_t[1280],const uint8_t[1280]);
    void *opaque;
    struct a7_fl_curve_scratch *scratch;
};
int a7_fl_curve_verify(const struct a7_fl_curve_io *,const struct a7_fl_preference *);
int a7_fl_curve_recover(struct a7_fl_worklog *,const struct a7_fl_curve_io *,
                        const struct a7_fl_preference *committed);
int a7_fl_curve_transition(struct a7_fl_worklog *,const struct a7_fl_curve_io *,
        const struct a7_fl_preference *before,const struct a7_fl_preference *next);
#endif
