/* In-place film texture stage. This is our ABI, not an assumed Sony ABI.
 * A native producer must supply a fenced, exclusively writable frame lease.
 * A mapped address or a metadata getter does not establish that lease. */
#ifndef A7_FILM_FRAME_H
#define A7_FILM_FRAME_H
#include <stdint.h>
#include <stddef.h>
#define A7_FILM_FRAME_MAX_DIMENSION 16384u
#define A7_FILM_REFERENCE_WIDTH 576u
#define A7_FILM_REFERENCE_RADIUS 16u
#define A7_FILM_FRAME_MAX_RADIUS 455u /* radius at the maximum supported width */
enum a7_film_format { A7_FILM_NV12=1, A7_FILM_NV16, A7_FILM_YUYV, A7_FILM_UYVY };
enum a7_film_range { A7_FILM_FULL=1, A7_FILM_LIMITED };
enum a7_film_path { A7_FILM_PREVIEW=1, A7_FILM_CAPTURE };
struct a7_film_plane { uint8_t *data; size_t bytes; unsigned stride; };
struct a7_film_frame {
    unsigned width,height,format,range,path;
    struct a7_film_plane plane[2];
    uintptr_t cookie; /* producer-owned lease, never interpreted as an address */
    uint32_t sequence;
};
struct a7_film_frame_params { int grain,halation; unsigned radius; uint32_t seed; };
enum a7_film_frame_result {
    A7_FILM_FRAME_OK=0,A7_FILM_FRAME_SKIP=1,A7_FILM_FRAME_BUSY=2,
    A7_FILM_FRAME_ARGUMENT=-1,A7_FILM_FRAME_ACQUIRE=-2,
    A7_FILM_FRAME_SYNC_CPU=-3,A7_FILM_FRAME_SYNC_DEVICE=-4,
    A7_FILM_FRAME_RELEASE=-5,A7_FILM_FRAME_FAULT=-6
};
/* Full-range and studio-range BT.709 8-bit, progressive, linear frames only.
 * Grain changes luma; halation spreads highlights and warms their surroundings.
 * Curves belong in the upstream LUT; this stage does not apply them twice.
 * All preflight failures leave pixels unchanged. No allocation or file I/O. */
size_t a7_film_frame_workspace(unsigned width,unsigned radius);
/* Radius of the approved 576 px reference, expressed in output pixels. */
unsigned a7_film_frame_reference_radius(unsigned width);
int a7_film_frame_validate(const struct a7_film_frame *,const struct a7_film_frame_params *,void *,size_t);
int a7_film_frame_apply(struct a7_film_frame *,const struct a7_film_frame_params *,void *,size_t);
struct a7_film_frame_io {
    /* 0=lease acquired, 1=not this stream, negative=failure. The producer must
     * keep the frame alive and exclude DMA/other writers until release. */
    int (*acquire)(void *,uintptr_t token,unsigned path,struct a7_film_frame *);
    /* Cache/fence callbacks must not change the acquired descriptor. A
     * failed for_cpu must leave the lease safe to return unchanged. */
    int (*for_cpu)(void *,const struct a7_film_frame *);
    int (*for_device)(void *,const struct a7_film_frame *);
    /* Always called once after a successful acquire. disposition is 0 for
     * unchanged, 1 for complete/synchronized, -1 for a failed modified frame.
     * On -1 the producer must quarantine/drop, never publish this frame. */
    int (*release)(void *,struct a7_film_frame *,int disposition);
    void *opaque;
};
struct a7_film_frame_stage {
    struct a7_film_frame_io io;
    void *workspace; size_t workspace_bytes;
    unsigned lock,fault,processed[2],skipped,failed;
};
/* Does not install a hook. Only a verified native producer calls this dispatch.
 * The supplied params are snapshotted before acquiring the lease. */
int a7_film_frame_dispatch(struct a7_film_frame_stage *,uintptr_t token,unsigned path,
                            const struct a7_film_frame_params *);
#ifdef A7_FL_FILM_CONTROLS
struct a7_fl_preference;
/* Bridge from an immutable schema-4 snapshot. Selects the active independent
 * bank; Off returns neutral settings. Radius is scaled from 16 pixels at
 * 576-pixel width. A native caller supplies its real frame sequence number.
 * Does not register a Sony callback, save a setting or apply a curve twice. */
int a7_film_frame_params_from_preference(const struct a7_fl_preference *,unsigned width,
                                        uint32_t sequence,struct a7_film_frame_params *);
/* Resolve texture settings using the acquired frame's width and sequence,
 * for either producer. Use separate stage/workspace instances for independent
 * concurrent preview and capture. Do not share DMA buffers between leases. */
int a7_film_frame_dispatch_preference(struct a7_film_frame_stage *,uintptr_t token,unsigned path,
                                     const struct a7_fl_preference *);
#endif
#endif
