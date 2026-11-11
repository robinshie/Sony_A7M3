/* Experimental sRGB adjustments for the standalone QEMU guest.
 * Names/ranges follow A7 IV; formulas and defaults are our own, not Sony ISP. */
enum { FL_CONTRAST, FL_HIGHLIGHTS, FL_SHADOWS, FL_FADE, FL_SATURATION,
       FL_SHARPNESS, FL_RANGE, FL_CLARITY, FL_ADJUST_COUNT };
typedef struct { int v[FL_ADJUST_COUNT]; } FLAdjust;
static const FLAdjust fl_defaults={{0,0,0,0,0,3,3,0}};
static const int fl_minimum[]={-9,-9,-9,0,-9,0,1,0};
static const int fl_maximum[]={9,9,9,9,9,9,5,9};
static const char *const fl_adjust_names[]={"Contrast","Highlights","Shadows","Fade",
    "Saturation","Sharpness","Sharpness Range","Clarity"};
static uint32_t fl_work[W*H],fl_horizontal[W*H],fl_blurred[W*H];

static int fl_limit(int v,int lo,int hi) { return v<lo?lo:v>hi?hi:v; }
static bool fl_adjust_valid(const FLAdjust *a)
{
    for(int i=0;i<FL_ADJUST_COUNT;i++)
        if(a->v[i]<fl_minimum[i] || a->v[i]>fl_maximum[i]) return false;
    return true;
}
static bool fl_adjust_changed(const FLAdjust *a)
{
    for(int i=0;i<FL_ADJUST_COUNT;i++) if(a->v[i]!=fl_defaults.v[i]) return true;
    return false;
}
static int fl_luma(uint32_t p)
{ return (54*((p>>16)&255)+183*((p>>8)&255)+19*(p&255)+128)>>8; }
static uint32_t fl_tone(uint32_t p,const FLAdjust *a)
{
    int channels[3],y=fl_luma(p);
    int lift=(a->v[FL_HIGHLIGHTS]*y*y+a->v[FL_SHADOWS]*(255-y)*(255-y))*6/65025;
    for(int c=0;c<3;c++) {
        int v=(p>>(16-c*8))&255;
        v=128+(v-128)*(256+a->v[FL_CONTRAST]*14)/256+lift;
        v=v*(255-a->v[FL_FADE]*5)/255+a->v[FL_FADE]*4;
        channels[c]=fl_limit(v,0,255);
    }
    y=(54*channels[0]+183*channels[1]+19*channels[2]+128)>>8;
    uint32_t result=0;
    for(int c=0;c<3;c++) {
        int v=y+(channels[c]-y)*(256+a->v[FL_SATURATION]*24)/256;
        result=(result<<8)|fl_limit(v,0,255);
    }
    return result;
}
/* Separable box filter with replicated edge pixels and O(width*height) work.
 * Each intermediate channel is rounded to u8; all sums fit in a signed int. */
static void fl_blur_image(int w,int h,int radius)
{
    int n=2*radius+1;
    for(int y=0;y<h;y++) for(int c=0;c<3;c++) {
        int shift=16-c*8,sum=0;
        for(int k=-radius;k<=radius;k++) sum+=(fl_work[y*w+fl_limit(k,0,w-1)]>>shift)&255;
        for(int x=0;x<w;x++) {
            int at=y*w+x;
            if(c==0) fl_horizontal[at]=0;
            fl_horizontal[at]|=(uint32_t)((sum+n/2)/n)<<shift;
            sum+=((fl_work[y*w+fl_limit(x+radius+1,0,w-1)]>>shift)&255);
            sum-=((fl_work[y*w+fl_limit(x-radius,0,w-1)]>>shift)&255);
        }
    }
    for(int x=0;x<w;x++) for(int c=0;c<3;c++) {
        int shift=16-c*8,sum=0;
        for(int k=-radius;k<=radius;k++) sum+=(fl_horizontal[fl_limit(k,0,h-1)*w+x]>>shift)&255;
        for(int y=0;y<h;y++) {
            int at=y*w+x;
            if(c==0) fl_blurred[at]=0;
            fl_blurred[at]|=(uint32_t)((sum+n/2)/n)<<shift;
            sum+=((fl_horizontal[fl_limit(y+radius+1,0,h-1)*w+x]>>shift)&255);
            sum-=((fl_horizontal[fl_limit(y-radius,0,h-1)*w+x]>>shift)&255);
        }
    }
}
static void fl_detail(int w,int h,int radius,int amount,int divisor)
{
    if(!amount) return;
    fl_blur_image(w,h,radius);
    for(int i=0;i<w*h;i++) {
        int delta=(fl_luma(fl_work[i])-fl_luma(fl_blurred[i]))*amount/divisor;
        uint32_t p=fl_work[i],out=0;
        for(int c=0;c<3;c++)
            out=(out<<8)|fl_limit((int)((p>>(16-c*8))&255)+delta,0,255);
        fl_work[i]=out;
    }
}
static bool fl_process(uint32_t *target,int stride,int w,int h,const FLAdjust *a)
{
    if(!target || w<1 || h<1 || w>W || h>H || stride<w || !fl_adjust_valid(a)) return false;
    for(int y=0;y<h;y++) for(int x=0;x<w;x++)
        fl_work[y*w+x]=fl_tone(fl_rgb(target[y*stride+x]),a);
    /* Higher range uses a smaller radius: finer outlines. Sharpness 3 is
     * neutral in this model; lower values soften, higher values sharpen. */
    fl_detail(w,h,6-a->v[FL_RANGE],a->v[FL_SHARPNESS]-3,6);
    fl_detail(w,h,12,a->v[FL_CLARITY],12);
    for(int y=0;y<h;y++) for(int x=0;x<w;x++) target[y*stride+x]=fl_work[y*w+x];
    return true;
}
static bool fl_adjust_selftest(void)
{
    uint32_t pixels[82];
    for(unsigned i=0;i<82;i++) pixels[i]=0xdeadbeef;
    for(unsigned y=0;y<8;y++) for(unsigned x=0;x<8;x++)
        pixels[1+y*10+x]=(x*31<<16)|(y*31<<8)|((x+y)*15);
    if(!fl_process(pixels+1,10,8,8,&fl_defaults)) return false;
    for(unsigned y=0;y<8;y++) for(unsigned x=0;x<8;x++)
        if(pixels[1+y*10+x]!=fl_rgb((x*31<<16)|(y*31<<8)|((x+y)*15))) return false;
    FLAdjust a=fl_defaults;
    a.v[FL_SHARPNESS]=9;a.v[FL_CLARITY]=9;
    if(!fl_process(pixels+1,10,8,8,&a)) return false;
    for(unsigned i=0;i<82;i++)
        if((i==0 || i>78 || (i-1)%10>=8) && pixels[i]!=0xdeadbeef) return false;
    for(int range=1;range<=5;range++) {
        a.v[FL_RANGE]=range;
        for(unsigned y=0;y<8;y++) for(unsigned x=0;x<8;x++) pixels[1+y*10+x]=0x807060;
        if(!fl_process(pixels+1,10,8,8,&a)) return false;
        for(unsigned y=0;y<8;y++) for(unsigned x=0;x<8;x++)
            if(pixels[1+y*10+x]!=fl_rgb(0x807060)) return false;
    }
    a.v[FL_RANGE]=6;
    if(fl_process(pixels+1,10,8,8,&a)) return false;
    return true;
}
