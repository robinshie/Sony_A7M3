/* Standalone RGB24 reference. No Sony frame access or ISP binding. */
#ifndef A7_FILM_TEXTURE_H
#define A7_FILM_TEXTURE_H
#include <stdint.h>
#include <stddef.h>
typedef struct {
    int grain,halation; /* 0..9 */
    int curve[5]; /* black,shadow,midtone,highlight,white: -9..9 */
    unsigned radius; /* 1..16 pixels at this working resolution */
    uint32_t seed;
} A7FilmTexture;
/* Workspace must be uint32 aligned; src/dst/workspace must be disjoint.
 * Bounded streaming blur uses O(width*radius) scratch. No heap or file I/O. */
size_t a7_film_texture_workspace(unsigned width,unsigned radius);
int a7_film_texture(const uint8_t *src,size_t src_bytes,unsigned src_stride,
                    uint8_t *dst,size_t dst_bytes,unsigned dst_stride,
                    unsigned width,unsigned height,const A7FilmTexture *,
                    void *workspace,size_t workspace_bytes);
#endif
