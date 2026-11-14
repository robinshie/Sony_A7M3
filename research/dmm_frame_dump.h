#ifndef A7_DMM_FRAME_DUMP_H
#define A7_DMM_FRAME_DUMP_H
#include <stdint.h>
struct a7_dmm_dump_result {int32_t status;uint32_t physical,length,written,reads;};
/* Caller must hold a successful DMM Open reference to this exact extent.
 * Copies only to a new private temporary file, never modifies source memory.
 * No assertion of pixel format or exclusive ownership follows from success. */
void a7_dmm_frame_dump(struct a7_dmm_dump_result *,uint32_t physical,uint32_t length);
#define A7_DMM_DUMP_PATH "/tmp/jiritsu/a7yc-frame.bin"
#endif
