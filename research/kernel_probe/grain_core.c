/* Compile the existing tested algorithm against the camera's kernel types. */
#include "a7-film-frame.c"

/* Slow region reference for checking a full-frame write using the same noise
 * field. Unlike the fast path it does not reuse/interchange line caches. */
void a7_grain_region_reference(unsigned char *dst,const unsigned char *src,unsigned width,unsigned height,
                               unsigned x0,unsigned y0,unsigned full_width,unsigned seed,unsigned strength)
{
    unsigned step=(A7_FILM_REFERENCE_WIDTH<<16)/full_width;
    for(unsigned y=0;y<height;y++)for(unsigned x=0;x<width;x++){
        unsigned at=(y*width+x)*2,gx=(x0+x)*step,gy=(y0+y)*step,xi=gx>>16,yi=gy>>16;
        int wx=(gx>>8)&255,wy=(gy>>8)&255;
        int a=grain_field(xi,yi,seed)*(256-wx)+grain_field(xi+1,yi,seed)*wx;
        int b=grain_field(xi,yi+1,seed)*(256-wx)+grain_field(xi+1,yi+1,seed)*wx;
        int field=(a*(256-wy)+b*wy)/65536,v=src[at+1];
        int delta=field*(int)strength*(64+(v<128?v:255-v))/65536;
        dst[at]=src[at];dst[at+1]=(unsigned char)clamp(v+delta,0,255);
    }
}
