/* Signed spatial falloff applied to an exclusively owned pre-encode frame. */
#ifndef A7_FILM_VIGNETTE_H
#define A7_FILM_VIGNETTE_H
#include "a7-film-frame.h"
/* Packed 8-bit YUYV/UYVY only. -9 dims corners to 1/4, +9 brightens to 2x.
 * An elliptical smoothstep leaves the central region unchanged. Y and stored
 * chroma offsets share the gain; no claim of linear-light exposure accuracy.
 * 0 preserves every byte. All validation failures precede pixel writes. */
size_t a7_film_vignette_workspace(unsigned width);
int a7_film_vignette_apply(struct a7_film_frame *,int strength,void *,size_t);
#endif
