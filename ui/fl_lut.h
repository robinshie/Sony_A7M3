/* Independent QEMU RGB processing, not Sony ISP code or a camera payload. */
#include "fl_data.h"

static unsigned fl_lerp(unsigned a, unsigned b, unsigned f)
{
    return (a*(255-f)+b*f+127)/255;
}
static uint32_t fl_rgb(uint32_t rgb)
{
    unsigned index[3], fraction[3];
    for(unsigned c=0;c<3;c++) {
        unsigned q=((rgb>>(16-c*8))&255)*(FL_LUT_SIZE-1);
        index[c]=q/255; fraction[c]=q%255;
        if(index[c]==FL_LUT_SIZE-1) { index[c]--; fraction[c]=255; }
    }
    unsigned at=3*(index[0]+FL_LUT_SIZE*(index[1]+FL_LUT_SIZE*index[2]));
    uint32_t result=0;
    for(unsigned c=0;c<3;c++) {
        unsigned plane[2];
        for(unsigned b=0;b<2;b++) {
            unsigned row[2];
            for(unsigned g=0;g<2;g++) {
                unsigned p=at+c+3*FL_LUT_SIZE*(g+FL_LUT_SIZE*b);
                row[g]=fl_lerp(fl_cube[p],fl_cube[p+3],fraction[0]);
            }
            plane[b]=fl_lerp(row[0],row[1],fraction[1]);
        }
        result=(result<<8)|((fl_lerp(plane[0],plane[1],fraction[2])+128)/257);
    }
    return result;
}
static bool fl_selftest(void)
{
    for(unsigned n=0;n<sizeof fl_vectors/sizeof *fl_vectors;n++) {
        uint32_t actual=fl_rgb(fl_vectors[n][0]), expected=fl_vectors[n][1];
        for(unsigned c=0;c<3;c++) {
            int delta=(int)((actual>>(c*8))&255)-(int)((expected>>(c*8))&255);
            if(delta < -1 || delta > 1) return false;
        }
    }
    return true;
}
