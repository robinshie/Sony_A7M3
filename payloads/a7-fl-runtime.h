/* Resident LUT switch core. Persistence and menu lifecycle belong to its caller. */
#ifndef A7_FL_RUNTIME_H
#define A7_FL_RUNTIME_H
#include <stdint.h>
#define A7_FL_BYTES 1280u
#define A7_FL_PROPERTY 0x00030004u

struct a7_fl_api {
    int (*size)(uint32_t);
    int (*attr)(uint32_t);
    int (*read)(uint32_t,void *);
    int (*write)(uint16_t,uint32_t,const void *);
};
enum a7_fl_error {
    A7_FL_OK=0, A7_FL_API=-1, A7_FL_TABLE=-2, A7_FL_LAYOUT=-3,
    A7_FL_READ=-4, A7_FL_FOREIGN=-5, A7_FL_WRITE=-6,
    A7_FL_VERIFY=-7, A7_FL_RECOVERY=-8, A7_FL_BUSY=-9,
    A7_FL_UNINITIALIZED=-10, A7_FL_ARGUMENT=-11
};
enum a7_fl_state { A7_FL_FAULT=-2, A7_FL_UNKNOWN=-1, A7_FL_OFF=0, A7_FL_ON=1 };
struct a7_fl_context {
    uint32_t lock,initialized;
    int state,last_error,write_result,read_result,recovery_result;
    struct a7_fl_api api;
    uint8_t original[A7_FL_BYTES],candidate[A7_FL_BYTES],scratch[A7_FL_BYTES];
};
uint32_t a7_fl_crc(const uint8_t *,uint32_t);
/* Context must be zero-initialized before its first use. Buffers are copied:
 * caller lifetime does not escape init(). No write occurs. */
int a7_fl_init(struct a7_fl_context *,const struct a7_fl_api *,
               const uint8_t *,uint32_t,const uint8_t *,uint32_t);
int a7_fl_set(struct a7_fl_context *,int enabled);
/* New control values generate a complete table outside this core. When ON it
 * is written/read back before replacing the owned candidate; when OFF only
 * the owned candidate changes. Tail and signed native range are checked. */
int a7_fl_replace_candidate(struct a7_fl_context *,const uint8_t *,uint32_t crc);
/* read_status is synchronous; state alone is a cached UI value. */
int a7_fl_read_status(struct a7_fl_context *);
#endif
