#ifndef A7_FL_FIVEPOINT_H
#define A7_FL_FIVEPOINT_H
#include <stdint.h>
/* Five luminance anchors in the native 0..256 domain. Each slider -9..9,
 * four native luminance units per step. This is a LUT transform, not grain. */
int a7_fl_fivepoint_knots(const int controls[5],int knots[5]);
int a7_fl_fivepoint_sample(const int knots[5],int luminance);
/* Exactly 1280-byte, 5x9x9 + chroma + calibration-tail tables.
 * encoding 0: signed-byte nodes, 1: packed signed seven-bit nodes.
 * Optional 405-cell limits apply in decoded signed units. Both or neither.
 * Preserves chroma and the calibration tail byte-for-byte. Input/output may
 * alias exactly; arbitrary partial overlap is safe via the local candidate.
 * Failure never writes output. No camera or filesystem access. */
int a7_fl_fivepoint_lut(const uint8_t *input,unsigned input_size,uint8_t *output,
                       unsigned output_size,unsigned encoding,const int controls[5],
                       const int8_t *low,const int8_t *high);
#endif
