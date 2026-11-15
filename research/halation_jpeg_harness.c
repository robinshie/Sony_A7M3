/* Host-only end-to-end capture fixture; all frames are owned synthetic memory. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <jpeglib.h>
#include "a7-film-frame.h"
#include "a7-fl-runtime-prefs.h"

enum { WIDTH=6000, HEIGHT=4000, STRIDE=12160, LEFT=160, EDGE=3200, BG=105 };
enum { BYTES=STRIDE*HEIGHT, POINTS=4 };
static const unsigned xx[POINTS]={EDGE+48, EDGE+256, 20, WIDTH/2};
static const unsigned yy[POINTS]={HEIGHT/2, HEIGHT/2, 20, HEIGHT/2};

struct producer {
    uint8_t *pixels;
    unsigned state; /* 0 idle, 1 leased, 2 CPU, 3 synced, 4 published */
};
struct measure { int y, cb, cr; };

static void check(int ok,const char *why){
    if(!ok){fprintf(stderr,"FAIL: %s\n",why);exit(1);}
}
static void fill(uint8_t *out){
    for(unsigned y=0;y<HEIGHT;y++){
        uint8_t *row=out+(size_t)y*STRIDE;
        memset(row,0xc7,LEFT);
        for(unsigned x=0;x<WIDTH;x+=2){
            /* Bright panel is centered; all corners have the same neutral
             * background as the pixels that receive the halo. */
            uint8_t value=y>=1600&&y<2400&&x>=2800&&x<EDGE?250:BG;
            uint8_t *p=row+LEFT+x*2;
            p[0]=p[2]=128;p[1]=p[3]=value;
        }
    }
}
static int acquire(void *opaque,uintptr_t token,unsigned path,struct a7_film_frame *f){
    struct producer *p=opaque;
    check(!p->state&&token==1&&path==A7_FILM_CAPTURE,"capture lease");
    p->state=1;
    *f=(struct a7_film_frame){WIDTH,HEIGHT,A7_FILM_UYVY,A7_FILM_FULL,A7_FILM_CAPTURE,
        {{p->pixels+LEFT,BYTES-LEFT,STRIDE},{0}},token,1};
    return 0;
}
static int cpu(void *opaque,const struct a7_film_frame *f){
    struct producer *p=opaque;check(p->state==1&&f->plane[0].data==p->pixels+LEFT,"CPU fence");
    p->state=2;return 0;
}
static int device(void *opaque,const struct a7_film_frame *f){
    struct producer *p=opaque;check(p->state==2&&f->cookie==1,"encoder fence");
    p->state=3;return 0;
}
static int release(void *opaque,struct a7_film_frame *f,int disposition){
    struct producer *p=opaque;
    check(p->state==3&&disposition==1&&f->cookie==1,"publish only a complete frame");
    p->state=4;return 0;
}
static void encode(const char *filename,const uint8_t *frame){
    FILE *out=fopen(filename,"wb");check(out!=NULL,"open JPEG output");
    struct jpeg_compress_struct c;struct jpeg_error_mgr err;
    c.err=jpeg_std_error(&err);jpeg_create_compress(&c);jpeg_stdio_dest(&c,out);
    c.image_width=WIDTH;c.image_height=HEIGHT;c.input_components=3;c.in_color_space=JCS_YCbCr;
    jpeg_set_defaults(&c);
    c.comp_info[0].h_samp_factor=2;c.comp_info[0].v_samp_factor=1;
    c.comp_info[1].h_samp_factor=c.comp_info[1].v_samp_factor=1;
    c.comp_info[2].h_samp_factor=c.comp_info[2].v_samp_factor=1;
    jpeg_set_quality(&c,95,TRUE);
    jpeg_start_compress(&c,TRUE);
    uint8_t line[WIDTH*3];JSAMPROW scanline=line;
    while(c.next_scanline<c.image_height){
        const uint8_t *row=frame+(size_t)c.next_scanline*STRIDE+LEFT;
        for(unsigned x=0;x<WIDTH;x+=2){
            const uint8_t *p=row+x*2;uint8_t *q=line+x*3;
            q[0]=p[1];q[3]=p[3];q[1]=q[4]=p[0];q[2]=q[5]=p[2];
        }
        check(jpeg_write_scanlines(&c,&scanline,1)==1,"write JPEG row");
    }
    jpeg_finish_compress(&c);jpeg_destroy_compress(&c);
    check(!fclose(out),"close JPEG output");
}
static void decode(const char *filename,struct measure out[POINTS]){
    FILE *in=fopen(filename,"rb");check(in!=NULL,"open encoded JPEG");
    struct jpeg_decompress_struct d;struct jpeg_error_mgr err;
    d.err=jpeg_std_error(&err);jpeg_create_decompress(&d);jpeg_stdio_src(&d,in);
    check(jpeg_read_header(&d,TRUE)==JPEG_HEADER_OK,"valid JPEG");
    check(d.image_width==WIDTH&&d.image_height==HEIGHT&&d.num_components==3&&
          d.comp_info[0].h_samp_factor==2&&d.comp_info[0].v_samp_factor==1,"JPEG L geometry and 4:2:2");
    d.out_color_space=JCS_YCbCr;jpeg_start_decompress(&d);
    uint8_t line[WIDTH*3];JSAMPROW scanline=line;
    while(d.output_scanline<d.output_height){
        unsigned y=d.output_scanline;
        check(jpeg_read_scanlines(&d,&scanline,1)==1,"decode JPEG row");
        for(unsigned i=0;i<POINTS;i++)if(y==yy[i]){
            const uint8_t *p=line+xx[i]*3;out[i]=(struct measure){p[0],p[1],p[2]};
        }
    }
    jpeg_finish_decompress(&d);jpeg_destroy_decompress(&d);
    check(!fclose(in),"close JPEG input");
}
int main(void){
    uint8_t *original=malloc(BYTES),*frame=malloc(BYTES);
    unsigned radius=a7_film_frame_reference_radius(WIDTH);
    size_t bytes=a7_film_frame_workspace(WIDTH,radius);
    void *scratch=malloc(bytes);
    check(original&&frame&&scratch,"allocate private frames and workspace");
    fill(original);
    struct measure decoded[3][POINTS];
    const char *names[3]={"halation-minus9.jpg","halation-zero.jpg","halation-plus9.jpg"};
    for(unsigned i=0;i<3;i++){
        int strength=9*((int)i-1);memcpy(frame,original,BYTES);
        struct a7_fl_preference preference={0};
        preference.enabled=A7_FL_PRESET_LEICA;preference.schema=4;preference.generation=1;
        preference.film[2][1]=(int8_t)strength;
        struct producer producer={frame,0};
        struct a7_film_frame_stage stage={{acquire,cpu,device,release,&producer},scratch,bytes,0,0,{0},0,0};
        check(a7_film_capture_texture_dispatch(&stage,1,A7_FILM_PREVIEW,&preference)==A7_FILM_FRAME_SKIP&&
              !producer.state,"preview bypass");
        int rc=a7_film_capture_texture_dispatch(&stage,1,A7_FILM_CAPTURE,&preference);
        if(!strength)check(rc==A7_FILM_FRAME_SKIP&&!producer.state&&!memcmp(original,frame,BYTES),"zero never leases or changes bytes");
        else check(!rc&&producer.state==4&&stage.processed[1]==1,"effect finishes before encoding");
        for(unsigned y=0;y<HEIGHT;y++){
            const uint8_t *a=original+(size_t)y*STRIDE,*b=frame+(size_t)y*STRIDE;
            check(!memcmp(a,b,LEFT),"line padding unchanged");
            if(strength<0)for(unsigned x=LEFT;x<STRIDE;x+=2)
                check(a[x]==b[x],"negative halo preserves chroma");
        }
        encode(names[i],frame);decode(names[i],decoded[i]);
        printf("%+d,%d,%d,%d,%d,%d,%d\n",strength,decoded[i][0].y,decoded[i][0].cb,
               decoded[i][0].cr,decoded[i][1].y,decoded[i][2].y,decoded[i][3].y);
    }
    const struct measure neg=decoded[0][0],zero=decoded[1][0],pos=decoded[2][0];
    check(neg.y+5<zero.y&&zero.y+5<pos.y,"a visible signed halo survives JPEG encoding");
    check(neg.cb==zero.cb&&neg.cr==zero.cr,"negative JPEG halo stays neutral");
    check(pos.cb<zero.cb&&pos.cr>zero.cr,"positive JPEG halo is warm");
    for(unsigned i=0;i<3;i++)for(unsigned j=1;j<POINTS;j++)
        check(decoded[i][j].y==decoded[1][j].y,"far background, corner and light core stay unchanged");
    printf("HALATION_JPEG_PASSED radius=%u scratch=%zu\n",radius,bytes);
    free(scratch);free(frame);free(original);return 0;
}
