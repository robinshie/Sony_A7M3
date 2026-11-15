/* Capture the native resize task while its lifetime is established. */
#define A7_CAPTURE_LAYOUT 1
#define A7_EARLY 1
#define a7_multi_record a7_unused_one_shot_record
#include "capture_frame.c"
#undef a7_multi_record
#include "capture_layout_record.h"
#define take_early_record take_layout_record
#include "capture_geometry_record.h"
