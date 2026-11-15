/* Bounds arithmetic for linear, packed 8-bit 4:2:2 source frames.
 * This does not identify a Sony format or grant access to any buffer. The
 * native adapter must establish format, ownership and extent independently. */
#ifndef A7_CAPTURE_GEOMETRY_H
#define A7_CAPTURE_GEOMETRY_H
#include <stdint.h>
struct a7_capture_geometry {
    unsigned width,height,stride,offset,span,canvas_bytes;
};
static int a7_capture_geometry_decode(uint32_t active,uint32_t canvas,
                                     uint32_t origin,uint32_t capacity,
                                     struct a7_capture_geometry *out)
{
    struct a7_capture_geometry g;
    unsigned w=active&65535u,h=active>>16;
    unsigned cw=canvas&65535u,ch=canvas>>16;
    unsigned x=origin&65535u,y=origin>>16;
    uint64_t offset,span,full;
    if(!out||w<2||w>6000||!h||h>4000||(w&1)||!cw||!ch||(cw&1)||
       w>cw||h>ch||x>cw-w||y>ch-h||(x&1)||!capacity||capacity>0x03000000u)
        return -1;
    g.width=w;g.height=h;g.stride=cw*2;
    offset=(uint64_t)y*g.stride+x*2;
    span=(uint64_t)(h-1)*g.stride+w*2;
    full=(uint64_t)g.stride*ch;
    if(full>capacity||offset+span>capacity)return -1;
    g.offset=(unsigned)offset;g.span=(unsigned)span;g.canvas_bytes=(unsigned)full;
    *out=g;return 0;
}
#endif
