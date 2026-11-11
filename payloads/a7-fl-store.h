/* Durable two-slot preference I/O; does not open a camera or flash partition. */
#ifndef A7_FL_STORE_H
#define A7_FL_STORE_H
#include "a7-fl-runtime-prefs.h"
struct a7_fl_store_io {
    /* read: 0 existing, 1 absent, negative failure; length must include overflow. */
    int (*read)(void *, unsigned slot, unsigned char *, unsigned capacity, unsigned *length);
    /* replace must check old bytes/absence again, fsync, and return 0 on success. */
    int (*replace)(void *, unsigned slot, const unsigned char *before, unsigned before_size,
                   int existed, const unsigned char after[128]);
    void *opaque;
};
struct a7_fl_store {
    struct a7_fl_store_io io;
    unsigned char original_sha[32];
    char build[24];
    unsigned initialized;
};
/* A surviving valid record can be read when the other slot is torn. Unknown or
 * torn existing files are never overwritten; saving then requires recovery. */
int a7_fl_store_open(struct a7_fl_store *, const struct a7_fl_store_io *,
                     const unsigned char [32], const char [24],
                     struct a7_fl_preference *, int *present);
/* Matches a7_fl_control store callback. Generation starts at1 and increments
 * exactly once. Re-reads both records before and after the durable write. */
int a7_fl_store_save(void *, const struct a7_fl_preference *);
#endif
