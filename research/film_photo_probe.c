/* One supplied RGB photo in private buffers. No camera pipeline or flash IO. */
#include <stdint.h>
#include "a7-film-texture.h"

#define PHOTO_BYTES (PHOTO_WIDTH * PHOTO_HEIGHT * 3u)
extern const uint8_t photo_rgb[PHOTO_BYTES] __attribute__((visibility("hidden")));
static uint8_t pixels[PHOTO_BYTES];
static uint32_t workspace[PHOTO_WIDTH * 18u];
_Static_assert(PHOTO_WIDTH >= 1 && PHOTO_WIDTH <= 576 &&
               PHOTO_HEIGHT >= 1 && PHOTO_HEIGHT <= 384, "bounded probe dimensions");

static long syscall3(long nr,long a,long b,long c) {
    register long r7 __asm__("r7")=nr,r0 __asm__("r0")=a;
    register long r1 __asm__("r1")=b,r2 __asm__("r2")=c;
    __asm__ volatile("svc #0":"+r"(r0):"r"(r7),"r"(r1),"r"(r2):"memory","cc");
    return r0;
}

static int write_all(long fd, const void *data, unsigned size) {
    const uint8_t *p=data;
    for (unsigned at=0; at<size;) {
        long n=syscall3(4,fd,(long)(p+at),size-at);
        if(n<=0||(unsigned long)n>size-at)return -1;
        at+=(unsigned)n;
    }
    return 0;
}

__attribute__((constructor)) static void render(void) {
    const A7FilmTexture look={9,9,{0,0,0,0,0},16,1987};
    const int status=a7_film_texture(photo_rgb,PHOTO_BYTES,PHOTO_WIDTH*3u,
        pixels,PHOTO_BYTES,PHOTO_WIDTH*3u,PHOTO_WIDTH,PHOTO_HEIGHT,
        &look,workspace,sizeof workspace);
    const uint32_t header[]={0x41374650,1,PHOTO_WIDTH,PHOTO_HEIGHT,(uint32_t)status};
    const char *path="/tmp/jiritsu/a7fp.bin";
    long fd=syscall3(5,(long)path,1|64|128|0x8000,0600);
    if(fd<0)return;
    int failed=write_all(fd,header,sizeof header);
    if(!failed&&!status)failed=write_all(fd,pixels,PHOTO_BYTES);
    if(syscall3(6,fd,0,0)<0||failed)syscall3(10,(long)path,0,0);
}
