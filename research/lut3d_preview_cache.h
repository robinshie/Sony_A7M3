/* Consumer-side cache for the offline preview fixture. The caller owns the
 * source and output for the whole selector call; these helpers do not provide
 * synchronization for a camera's processing threads. */
#ifndef LUT3D_PREVIEW_CACHE_H
#define LUT3D_PREVIEW_CACHE_H

#include <stdint.h>

#define LUT3D_PREVIEW_BYTES 1215u

struct lut3d_preview_cache {
    uint8_t rendered[LUT3D_PREVIEW_BYTES];
    int valid;
};

static inline int lut3d_preview_changed(const struct lut3d_preview_cache *cache,
                                        const uint8_t source[LUT3D_PREVIEW_BYTES]) {
    if(!cache->valid)return 1;
    for(unsigned i=0;i<LUT3D_PREVIEW_BYTES;i++)
        if(cache->rendered[i]!=source[i])return 1;
    return 0;
}

/* Record what was actually packed, not what was merely requested. */
static inline void lut3d_preview_rendered(struct lut3d_preview_cache *cache,
                                          const uint8_t source[LUT3D_PREVIEW_BYTES]) {
    for(unsigned i=0;i<LUT3D_PREVIEW_BYTES;i++)cache->rendered[i]=source[i];
    cache->valid=1;
}

#endif
