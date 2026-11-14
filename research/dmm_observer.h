#ifndef A7_DMM_OBSERVER_H
#define A7_DMM_OBSERVER_H
#include "a7-dmm-channel.h"
#include "dmm_frame_dump.h"
/* Inside the trace's unused record area; mode 7 keeps at most record zero. */
#define A7_DMM_OBSERVER_OFFSET 224u
struct a7_dmm_observer {
    struct a7_dmm_channel channel;
    uint32_t attempted,polls;
    int32_t status,disposal;
    uint8_t metadata[60];
    uint32_t phase; /* 0 Info, 1 Open, 2 read, 3 Close, 4 done */
    int32_t info_status,open_status,close_status;
    uint8_t info_reply[24],open_reply[24],close_reply[24];
    struct a7_dmm_dump_result dump;
};
_Static_assert(sizeof(struct a7_dmm_observer)==344,"DMM observer report ABI");
void a7yc_dmm_observe(void *trace,const uint8_t *metadata);
#endif
