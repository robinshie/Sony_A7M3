/* Experimental spatial reference, independent of Sony's algorithms.
 * NOT connected to the camera capture/ISP pipeline. No hardware writes.
 * Input is an owned, CPU-readable 8-bit luma plane, not a guessed DMA buffer.
 */
#ifndef A7_FL_SPATIAL_H
#define A7_FL_SPATIAL_H
#include <stddef.h>
#include <stdint.h>
typedef struct { int sharpness,range,clarity; } A7FLSpatialParams;
/* Sharpness -3..3 (0 neutral), range 1..5 (higher = finer radius), clarity
 * 0..9. These are experimental semantics, NOT Sony A7 IV parameter equivalence.
 * Workspace must be 4-byte aligned; input, output and workspace cannot overlap.
 * No allocation, floating point, I/O or mutable global state. Borders replicate.
 */
size_t a7_fl_spatial_workspace(unsigned width);
int a7_fl_spatial_luma(const uint8_t *src,size_t src_bytes,unsigned src_stride,
                       uint8_t *dst,size_t dst_bytes,unsigned dst_stride,
                       unsigned width,unsigned height,const A7FLSpatialParams *,
                       void *workspace,size_t workspace_bytes);
/* Same output as a7_fl_spatial_luma, using one writable, exclusively owned
 * luma plane. The caller owns synchronization and buffer lifetime. */
size_t a7_fl_spatial_inplace_workspace(unsigned width);
int a7_fl_spatial_inplace(uint8_t *luma,size_t bytes,unsigned stride,
                          unsigned width,unsigned height,const A7FLSpatialParams *,
                          void *workspace,size_t workspace_bytes);
#endif
