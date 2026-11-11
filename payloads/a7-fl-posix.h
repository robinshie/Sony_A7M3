#ifndef A7_FL_POSIX_H
#define A7_FL_POSIX_H
#include "a7-fl-store.h"
/* Linux ARM EABI, fixed camera-owned 8.3 paths on /setting. No raw block I/O. */
void a7_fl_posix_io(struct a7_fl_store_io *);
#endif
