/* Three capture metadata snapshots, no pixel access or DMM ownership changes. */
#define A7_EARLY 1
#define a7_multi_record a7_unused_one_shot_record
#include "capture_frame.c"
#undef a7_multi_record
#include "capture_geometry_record.h"
