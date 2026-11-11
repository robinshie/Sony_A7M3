/* Stand-alone navigation model for the Sony ILCE-7M3, not Sony firmware. */
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>

#define W 640
#define H 480
#define LCD ((volatile uint32_t *)0x10020000)
#define KMI ((volatile uint32_t *)0x10006000)
#define UART ((volatile uint32_t *)0x10009000)
#define COUNT(x) (sizeof(x) / sizeof(*(x)))
#define FG 0xf4f4f4
#define DARK 0x070707
#define DIM 0xa4a4a4
#define ROW_Y 126
#define ROW_H 51
#define MENU_LEFT 18
#define MENU_RIGHT 623
#define MENU_TEXT 0xdddddd

typedef struct { const char *name, *value; uint16_t first; uint8_t count, initial; } Item;
typedef struct { const char *title; uint8_t first, count; } Page;
typedef struct { const char *title; uint8_t first, count; } Tab;
typedef struct { uint32_t offset; uint16_t code; uint8_t advance, width; } Glyph;
typedef struct { const uint8_t *pixels; const Glyph *glyph; uint16_t count; uint8_t baseline, height; } Font;
typedef struct { const char *key, *text; } Translation;
typedef struct { const uint8_t *ink; uint8_t width, height; } Icon;

#include "menu_data.h"
#include "fonts.h"
#include "firmware_ui.h"
#if FL_LOOK_INDEX >= 0
#include "fl_lut.h"
#include "fl_adjust.h"
#endif

enum Screen { SHOOT, MENU, FN, PLAY, INDEX, OPTION, QUICK, PRESET, FLPREVIEW };
enum Key { NONE, UP, DOWN, LEFT, RIGHT, CONFIRM, BACK, MENUKEY, FNKEY,
           PLAYKEY, DISPKEY, PAGEUP, PAGEDOWN, SHUTTER, MOVIE, INDEXKEY,
           ZOOMKEY, DELETEKEY, LANGUAGEKEY, TAB1, TAB2, TAB3, TAB4, TAB5, TAB6 };

static uint32_t *pixels;
static uint8_t selected[COUNT(items)];
static uint8_t my_items[30];
static int my_count;
static enum Screen screen, parent, return_screen;
static int tab, page_no, row, option, option_id, fn_slot, disp, mode;
static bool adding, zoomed, recording, movie_frame, deleting;
static int shots, playback;
static int remembered[6];
static int creative_contrast, creative_saturation, creative_sharpness;
static const char *creative_base_style="Standard";
#if FL_LOOK_INDEX >= 0
static FLAdjust fl_saved,fl_draft;
static int fl_focus;
#endif
static const int fn_items[] = {
    ITEM_DRIVE_MODE, ITEM_FLASH_MODE, ITEM_FLASH_COMP_, ITEM_FOCUS_MODE,
    ITEM_FOCUS_AREA, ITEM_EXPOSURE_COMP_, ITEM_ISO, ITEM_METERING_MODE,
    ITEM_WHITE_BALANCE, ITEM_DRO_AUTO_HDR, ITEM_CREATIVE_STYLE,
#if FL_LOOK_INDEX >= 0
    ITEM_CREATIVE_LOOK
#else
    ITEM_PICTURE_EFFECT
#endif
};
static const char *const modes[] = {"AUTO", "P", "A", "S", "M", "1", "2", "SCN", "MOVIE", "S&Q"};
static const uint32_t tab_colors[] = {0x981811, 0x70317d, 0x28583b, 0x204779, 0x9b6f19, 0x646464};

static int min(int a, int b) { return a < b ? a : b; }
static int max(int a, int b) { return a > b ? a : b; }
static int wrap(int n, int lim) { return n < 0 ? lim - 1 : n >= lim ? 0 : n; }
static uint32_t mix(uint32_t a, uint32_t b, unsigned t)
{
    uint32_t rb = (((a & 0xff00ff) * (256 - t) + (b & 0xff00ff) * t) >> 8) & 0xff00ff;
    uint32_t g = (((a & 0xff00) * (256 - t) + (b & 0xff00) * t) >> 8) & 0xff00;
    return rb | g;
}
static void fill(int x, int y, int w, int h, uint32_t c)
{
    int x0 = max(0, x), x1 = min(W, x + w);
    int y0 = max(0, y), y1 = min(H, y + h);
    for (int j = y0; j < y1; ++j)
        for (int i = x0; i < x1; ++i)
            pixels[j*W+i] = c;
}
static void border(int x, int y, int w, int h, uint32_t c)
{
    fill(x,y,w,2,c); fill(x,y+h-2,w,2,c); fill(x,y,2,h,c); fill(x+w-2,y,2,h,c);
}
static void line(int x, int y, int x1, int y1, uint32_t c)
{
    int dx = x1-x, sx = dx < 0 ? -1 : 1, dy = y1-y, sy = dy < 0 ? -1 : 1;
    dx *= sx; dy *= -sy;
    int err = dx+dy;
    for (;;) {
        fill(x,y,2,2,c);
        if (x == x1 && y == y1) return;
        int e = 2*err;
        if (e >= dy) { err += dy; x += sx; }
        if (e <= dx) { err += dx; y += sy; }
    }
}
static void circle(int x, int y, int r, uint32_t color)
{
    for (int i = -r; i <= r; ++i)
        for (int j = -r; j <= r; ++j)
            if (i*i+j*j <= r*r) fill(x+j,y+i,1,1,color);
}
static bool use_chinese(void) { return selected[ITEM_LANGUAGE]==0; }
static int compare(const char *a, const char *b)
{
    while (*a && *a==*b) { a++; b++; }
    return (unsigned char)*a-(unsigned char)*b;
}
static const char *translate(const char *s)
{
    if (!*s || !use_chinese() || (unsigned char)*s>=128) return s;
    int lo=0, hi=COUNT(zh_strings);
    while (lo<hi) {
        int mid=(lo+hi)/2, cmp=compare(s,zh_strings[mid].key);
        if (!cmp) return zh_strings[mid].text;
        if (cmp<0) hi=mid; else lo=mid+1;
    }
    return s;
}
static unsigned next_code(const char **s)
{
    const unsigned char *p=(const unsigned char *)*s;
    unsigned c=*p++;
    if (c>=0xc2 && c<=0xdf && (*p&0xc0)==0x80) {
        c=((c&31)<<6)|(*p++&63);
    } else if (c>=0xe0 && c<=0xef && (p[0]&0xc0)==0x80 && (p[1]&0xc0)==0x80) {
        c=((c&15)<<12)|((p[0]&63)<<6)|(p[1]&63);
        p+=2;
    } else if (c>=0x80) {
        c='?';
    }
    *s=(const char *)p;
    return c;
}
static const Glyph *find_glyph(const Font *f, unsigned c)
{
    if(c>=32 && c<=126) return &f->glyph[c-32];
    int lo=95, hi=f->count;
    while(lo<hi) {
        int mid=(lo+hi)/2;
        if(c==f->glyph[mid].code) return &f->glyph[mid];
        if(c<f->glyph[mid].code) hi=mid; else lo=mid+1;
    }
    return &f->glyph['?'-32];
}
static int measure(const Font *f, const char *s)
{
    int w=0;
    for (s=translate(s); *s;) w+=find_glyph(f,next_code(&s))->advance;
    return w;
}
static void label_limit(const Font *f, int x, int base, const char *s, uint32_t color, int limit)
{
    int y = base-f->baseline;
    for (s=translate(s); *s;) {
        const Glyph *g=find_glyph(f,next_code(&s));
        if (x + g->advance > limit) break;
        const uint8_t *p = f->pixels+g->offset;
        for (int i=0; i<f->height; i++)
            for (int j=0; j<g->width; j++) {
                unsigned alpha=*p++;
                int px=x+j, py=y+i;
                if (alpha && px>=0 && px<W && py>=0 && py<H) {
                    uint32_t *d = &pixels[py*W+px];
                    *d = alpha==255 ? color : mix(*d,color,alpha);
                }
            }
        x += g->advance;
    }
}
static void label(const Font *f, int x, int y, const char *s, uint32_t c)
{ label_limit(f,x,y,s,c,W); }
static void center(const Font *f, int x, int y, const char *s, uint32_t c)
{ label(f,x-measure(f,s)/2,y,s,c); }
static void right(const Font *f, int x, int y, const char *s, uint32_t c)
{ label(f,x-measure(f,s),y,s,c); }
static void draw_icon(const Icon *i, int x, int y, uint32_t c, bool flip)
{
    for (int row=0; row<i->height; row++) {
        for (int col=0; col<i->width; col++) {
            int sx=flip?i->width-col-1:col;
            unsigned a=i->ink[row*i->width+sx];
            if (a) {
                uint32_t *p=&pixels[(y+row)*W+x+col];
                *p=a==255?c:mix(*p,c,a);
            }
        }
    }
}
static int nstr(char *s, int n)
{
    char tmp[12]; int len=0;
    do { tmp[len++]='0'+n%10; n/=10; } while(n);
    for (int i=0;i<len;i++) s[i]=tmp[len-1-i];
    s[len]=0;
    return len;
}
static void tab_icon(int id, int x, uint32_t c, uint32_t b)
{
    static const Icon *const tabs_ink[]={&ico_camera1,&ico_camera2,&ico_network,&ico_play,0,&ico_star};
    if (id == 4) {
        fill(x-25,26,50,27,c); fill(x-22,23,44,31,c);
        fill(x-10,19,20,8,c); fill(x-6,22,12,3,b);
        fill(x-25,34,50,4,b); fill(x-15,33,7,8,c); fill(x+8,33,7,8,c);
        return;
    }
    const Icon *shape=tabs_ink[id];
    draw_icon(shape,x-shape->width/2,36-shape->height/2,c,false);
}
static void footer(int p, int count)
{
    fill(0,SCREEN_FOOTER_Y,W,H-SCREEN_FOOTER_Y,0);
    fill(0,432,W,1,0x585858);
    for (int i=0; i<count; i++)
        fill(320-count*9+i*18+3,449,12,14,i==p?HIGHLIGHT:0x656565);
    draw_icon(&ico_menu,556,444,MENU_TEXT,false);
    draw_icon(&ico_back,597,443,MENU_TEXT,false);
}
static int current_total(void)
{
    return tabs[tab].count + (tab==5 ? (my_count+5)/6 : 0);
}
static const Page *current_page(void)
{
    return &pages[tabs[tab].first + (tab==5 ? 0 : page_no)];
}
static bool my_custom_page(void) { return tab==5 && page_no < current_total()-1; }
static int rows(void)
{
    return my_custom_page() ? min(6,my_count-page_no*6) : current_page()->count;
}
static int current_item(void)
{
    return my_custom_page() ? my_items[page_no*6+row] : current_page()->first + row;
}
static const char *value_of(int id)
{
#if FL_LOOK_INDEX >= 0
    if(id==ITEM_CREATIVE_STYLE && selected[ITEM_CREATIVE_LOOK]==FL_LOOK_INDEX)
        return "Look active";
    if(id==ITEM_CREATIVE_LOOK && selected[id]==FL_LOOK_INDEX && fl_adjust_changed(&fl_saved))
        return "FL (Experimental)*";
#endif
    const Item *a=&items[id];
    return a->count ? choices[a->first+selected[id]] : a->value;
}
static bool motion_icon(int id)
{
    return id >= pages[tabs[1].first].first &&
           id < pages[tabs[1].first+3].first;
}
static bool still_icon(int id) { return id <= ITEM_ASPECT_RATIO; }
static void draw_menu(void)
{
    fill(0,0,W,H,0);
    for (int i=0;i<6;i++) {
        int x=18+i*86;
        uint32_t shade = tab==i ? 0x646464 : DARK;
        for (int j=0;j<56;j++) {
            uint32_t c=tab==i ? mix(0x707070,0x303030,j*4) :
                j>38 ? mix(shade,tab_colors[i],(j-38)*14) : shade;
            fill(x,7+j,85,1,c);
        }
        fill(x+84,8,1,55,0x323232);
        if (tab==i) border(x,7,86,57,row==-1?HIGHLIGHT:0x959595);
        tab_icon(i,x+43,MENU_TEXT,shade);
    }
    fill(0,MENU_HEADER_H-1,W,1,0x585858);
    int count=current_total();
    char index[28], my[36];
    char *q=index;
    q+=nstr(q,page_no+1); *q++='/'; nstr(q,count);
    const char *title_text=current_page()->title;
    if (my_custom_page()) {
        const char *prefix=translate("My Menu");
        int i=0;
        for(;prefix[i];i++) my[i]=prefix[i];
        if(!use_chinese()) my[i++]=' ';
        nstr(my+i,page_no+1); title_text=my;
    }
    const char *heading=adding?"Add Item":title_text;
    center(measure(&title,heading)<414?&title:&compact,320,108,heading,MENU_TEXT);
    right(&compact,601,112,index,MENU_TEXT);
    if (page_no>0) draw_icon(&ico_next,586-measure(&compact,index),96,MENU_TEXT,true);
    if (page_no+1<count) draw_icon(&ico_next,619,96,MENU_TEXT,false);
    fill(0,ROW_Y-1,W,1,0x585858);
    for (int i=0;i<6;i++) {
        int y=ROW_Y+i*ROW_H, b=y+37;
        if(i==row) fill(MENU_LEFT,y,MENU_RIGHT-MENU_LEFT,ROW_H-1,HIGHLIGHT);
        if (i<rows()) {
            int id=my_custom_page()?my_items[page_no*6+i]:current_page()->first+i;
            bool m=motion_icon(id), s=still_icon(id);
            if (m||s) draw_icon(m?&ico_movie:&ico_still,30,y+10,MENU_TEXT,false);
            const char *v=value_of(id);
            const Font *vf=measure(&menu_text,v)<=265?&menu_text:&compact;
            int vw=min(265,measure(vf,v));
            int x=(m||s)?67:28, end=610-vw-14;
            const char *name=items[id].name;
            const Font *nf=measure(&menu_text,name)<=end-x?&menu_text:
                           measure(&compact,name)<=end-x?&compact:&body;
            label_limit(nf,x,b,name,MENU_TEXT,end);
            if (*v) {
                if (vw<265) right(vf,610,b,v,MENU_TEXT);
                else label_limit(vf,610-vw,b,v,MENU_TEXT,610);
            }
        }
        fill(MENU_LEFT,y+ROW_H-1,MENU_RIGHT-MENU_LEFT,1,0x151515);
    }
    footer(page_no,count);
}
static void test_target(int x,int y,int w,int h,int sample)
{
    static const uint32_t swatch[]={0xd6d6d6,0xc6b83a,0x4aadb2,0x569146,0xab609a,0xbd5d4a,0x415b93};
    fill(x,y,w,h,0x24272b);
    if (w<50 || h<50) return;
    for (int j=0;j<7;j++) fill(x+w*j/7,y+h/4,w*(j+1)/7-w*j/7,h/2,swatch[(j+sample)%7]);
    border(x+w/10,y+h/9,w*8/10,h*7/9,0x797c80);
    fill(x+w/2-16,y+h/2,32,1,0xededed); fill(x+w/2,y+h/2-16,1,32,0xededed);
#if FL_LOOK_INDEX >= 0
    if(selected[ITEM_CREATIVE_LOOK]==FL_LOOK_INDEX && (screen==SHOOT||screen==FN)) {
        fl_process(pixels+y*W+x,W,w,h,&fl_saved);
    }
#endif
    if (w>250) center(&small,x+w/2,y+h*7/8,"SIMULATED TEST TARGET",0xc4c4c4);
}
static void battery(int x,int y)
{
    border(x,y,32,14,FG); fill(x+32,y+4,3,6,FG); fill(x+4,y+4,22,6,FG);
}
static void draw_finder(bool editing);
static void draw_shoot(void)
{
    fill(0,0,W,H,0);
    if (disp==5 && screen!=FN) return;
    if (disp!=4) test_target(0,26,W,418,0);
    if (disp==2) return;
    if (disp==4) { draw_finder(false); return; }
    label(&body,16,34,modes[mode],FG);
    label(&small,100,30,"1   9999",FG);
    label(&small,243,30,"24M   3:2",FG);
    label(&small,375,30,value_of(ITEM_FILE_FORMAT),FG);
    battery(548,15);
    label(&small,589,29,"100%",FG);
#if FL_LOOK_INDEX >= 0
    if(selected[ITEM_CREATIVE_LOOK]==FL_LOOK_INDEX)
        label(&small,18,66,value_of(ITEM_CREATIVE_LOOK),HIGHLIGHT);
#endif
    if (disp==3) {
        int yy=376;
        fill(502,yy-77,122,78,0x151515); border(502,yy-77,122,78,DIM);
        for(int i=0;i<27;i++) fill(506+i*4,yy-4-(i*19+i*i*3)%53,3,4+(i*19+i*i*3)%53,FG);
    }
    if (disp==1) {
        line(228,218,410,218,0xbdbdbd); line(319,206,319,231,0x52ce78);
        circle(320,218,4,0x52ce78);
    }
    if (disp==6) {
        line(84,409,309,409,FG);
        for (int i=0;i<11;i++) fill(84+i*22,399,1,10,FG);
    }
    fill(0,445,W,35,0);
    label(&body,23,472,"1/125",FG);
    label(&body,152,472,"F4.0",FG);
    label(&body,260,472,"+/-0.0",FG);
    if(selected[ITEM_ISO]) {
        label(&body,414,472,"ISO",FG);
        label(&body,475,472,value_of(ITEM_ISO),FG);
    } else label(&body,414,472,"ISO AUTO",FG);
    if(recording) {
        circle(504,54,7,0xe63520);
        label(&body,522,64,"REC",0xff4027);
    }
}
static const char *fn_value(int slot)
{
    static const char *const focus[]={"AF-S","AF-A","AF-C","DMF","MF"};
    if (slot==0 && selected[ITEM_DRIVE_MODE]==0) return "Single";
    if (slot==3) return focus[selected[ITEM_FOCUS_MODE]];
    if (slot==7 && selected[ITEM_METERING_MODE]==3) return "Entire";
    if (slot==8 && selected[ITEM_WHITE_BALANCE]==0) return "AWB";
    if (slot==9) return "DRO AUTO";
    return value_of(fn_items[slot]);
}
static const char *const fn_names[]={"Drive","Flash","Flash +/-","Focus","Focus Area","Exposure",
        "ISO","Metering","White Bal.","DRO/HDR","Creative",
#if FL_LOOK_INDEX >= 0
        "Look"
#else
        "Effect"
#endif
};
static void fn_cell(int i,int x,int y,int w,int h,bool active)
{
    fill(x,y,w,h,active?HIGHLIGHT:0x212121);
    border(x,y,w,h,active?0xffb27a:0x6b6b6b);
    center(&micro,x+w/2,y+16,fn_names[i],FG);
    const char *v=fn_value(i);
    if (!*v) v="-";
    const Font *font=measure(&small,v)<=w-8?&small:&micro;
    if(measure(font,v)<=w-8) center(font,x+w/2,y+h-10,v,FG);
    else label_limit(font,x+4,y+h-10,v,FG,x+w-4);
}
static void draw_finder(bool editing)
{
    fill(0,0,W,H,0);
    fill(QUICK_PANEL_W,0,1,H,0x555555);
    battery(19,20); label(&small,58,34,"100",FG);
    label(&small,210,34,"3:2  24M",FG);
    right(&small,448,34,value_of(ITEM_FILE_FORMAT),FG);
    label(&body,18,173,modes[mode],FG);
    label(&large,154,175,"1/125",FG);
    right(&large,442,175,"F4.0",FG);
    fill(17,185,429,1,0x555555);
    line(28,213,309,213,0xc1c1c1);
    for(int i=0;i<=12;i++) fill(28+i*23,200+(i%3?5:0),1,(i%3?8:13),FG);
    label(&small,25,242,"-3",DIM); center(&small,166,242,"0",DIM); right(&small,308,242,"+3",DIM);
    right(&body,442,219,"+/-0.0",FG);
    right(&body,442,275,value_of(ITEM_ISO),FG);
    fill(17,302,429,1,0x555555);
    for(int i=0;i<86;i++) {
        int h=4+max(0,50-(i-25)*(i-25)/6)+max(0,34-(i-52)*(i-52)/8)+(i*13+i*i*3)%14;
        fill(20+i*4,405-h,4,h,0xcecece);
    }
    fill(17,413,429,1,0x555555);
    if(editing) label(&body,18,452,items[fn_items[fn_slot]].name,FG);
    for(int i=0;i<12;i++) {
        int x=quick_positions[i][0], y=quick_positions[i][1];
        fn_cell(i,x,y,QUICK_CELL_W,QUICK_CELL_H,editing&&i==fn_slot);
    }
}
static void draw_fn(bool quick)
{
    if(quick) { draw_finder(true); return; }
    draw_shoot();
    fill(0,304,W,124,0x141414);
    for(int i=0;i<12;i++) {
        fn_cell(i,fn_positions[i][0],fn_positions[i][1],FN_CELL_W,FN_CELL_H,i==fn_slot);
    }
    fill(0,SCREEN_FOOTER_Y,W,H-SCREEN_FOOTER_Y,0);
    label(&body,9,459,items[fn_items[fn_slot]].name,FG);
}
static void draw_play(void)
{
    fill(0,0,W,H,0);
    if (!shots) { center(&body,320,245,"No images.",FG); return; }
    if (screen==INDEX) {
        for(int i=0;i<shots;i++) {
            int x=19+(i%3)*203,y=40+(i/3)*136;
            test_target(x,y,196,129,i);
            border(x,y,196,129,playback==i?HIGHLIGHT:0x383838);
        }
    } else if (disp==3) {
        test_target(18,88,294,226,playback);
        for(int i=0;i<4;i++) {
            int y=44+i*92;
            uint32_t c=i==0?FG:i==1?0xe14b3d:i==2?0x64bd73:0x5889d7;
            border(342,y,277,82,0x737373);
            for(int j=0;j<59;j++) {
                int h=5+(j*19+i*22+j*j*3)%61;
                fill(351+j*4,y+73-h,3,h,c);
            }
        }
    } else {
        test_target(0,zoomed?-30:27,W,zoomed?516:421,playback);
    }
    if (disp!=2 || screen==INDEX || deleting) {
        char num[24]; int l=nstr(num,playback+1); num[l++]='/'; nstr(num+l,shots);
        label(&small,17,24,"1  100-0001",FG); right(&small,617,24,num,FG);
        label(&small,17,471,"1/125   F4.0   ISO100",FG);
        if (movie_frame) right(&small,617,471,"MOVIE",FG);
    }
    if (deleting) {
        fill(120,142,400,200,0x111111); border(120,142,400,200,DIM);
        center(&body,320,190,"Delete this image?",FG);
        fill(145,234,350,43,option==0?HIGHLIGHT:0x232323);
        fill(145,279,350,43,option==1?HIGHLIGHT:0x232323);
        center(&body,320,264,"Cancel",FG); center(&body,320,309,"Delete",FG);
    }
}
static void draw_options(void)
{
    const Item *a=&items[option_id];
    fill(0,0,W,H,0);
    center(measure(&title,a->name)<594?&title:&compact,320,85,a->name,FG);
    fill(0,112,W,1,0x737373);
    if (option_id==ITEM_VERSION) {
        label(&body,29,173,"Body",FG); right(&body,608,173,"Ver. 4.04",FG);
        label(&body,29,226,"Lens",FG); right(&body,608,226,"--",DIM);
        center(&small,320,369,"Reference value for UI verification",DIM);
    } else if (option_id==ITEM_SETTING_RESET || option_id==ITEM_FORMAT) {
        const char *v0=option_id==ITEM_SETTING_RESET?"Camera Settings Reset":"Cancel";
        const char *v1=option_id==ITEM_SETTING_RESET?"Initialize":"Enter";
        for(int i=0;i<2;i++) {
            fill(22,ROW_Y+i*ROW_H,596,ROW_H-2,i==option?HIGHLIGHT:0x121212);
            label(&body,38,ROW_Y+i*ROW_H+35,i?v1:v0,FG);
        }
        center(&small,320,370,"Applies only to this verification guest",DIM);
    } else if (a->count) {
        int first=min(max(0,option-2),max(0,a->count-6));
        for (int i=first;i<a->count && i<first+6;i++) {
            int y=ROW_Y+(i-first)*ROW_H;
            fill(17,y,606,ROW_H-2,i==option?HIGHLIGHT:0x121212);
            const char *choice=choices[a->first+i];
            label_limit(measure(&menu_text,choice)<525?&menu_text:&compact,
                        36,y+36,choice,FG,564);
            if (i==selected[option_id]) right(&small,605,y+35,"OK",FG);
        }
    } else {
        if (*a->value) center(&body,320,172,a->value,FG);
        center(&small,320,243,"Menu entry available for navigation checks.",DIM);
        center(&small,320,273,"This camera function is not simulated.",DIM);
    }
    footer(0,0);
}
static void draw_preset(void)
{
#if RETRO_STYLE_INDEX >= 0
    fill(0,0,W,H,0);
    center(&title,320,64,RETRO_NAME,FG);
    center(&small,320,100,"UI prototype - image processing not connected",DIM);
    fill(18,116,604,1,0x737373);
    const char *names[]={"Base style", "Contrast", "Saturation", "Sharpness", "White Balance"};
    static const char cv[3]={RETRO_CONTRAST<0?'-':'+','0'+(RETRO_CONTRAST<0?-RETRO_CONTRAST:RETRO_CONTRAST),0};
    static const char sv[3]={RETRO_SATURATION<0?'-':'+','0'+(RETRO_SATURATION<0?-RETRO_SATURATION:RETRO_SATURATION),0};
    static const char hv[3]={RETRO_SHARPNESS<0?'-':'+','0'+(RETRO_SHARPNESS<0?-RETRO_SHARPNESS:RETRO_SHARPNESS),0};
    const char *values[]={RETRO_BASE_STYLE,cv,sv,hv,RETRO_WHITE_BALANCE};
    for(int i=0;i<5;i++) {
        label(&body,34,155+i*43,names[i],FG);
        right(&body,604,155+i*43,values[i],FG);
    }
    center(&small,320,370,"Picture Profile / Picture Effect: Off",DIM);
    center(&small,320,409,"Enter: apply in QEMU / Esc: cancel",FG);
    footer(0,0);
#endif
}
static void draw_fl_preview(void)
{
#if FL_LOOK_INDEX >= 0
    fill(0,0,W,H,0);
    center(&menu_text,320,38,fl_adjust_changed(&fl_draft)?"FL (Experimental)*":FL_NAME,FG);
    center(&micro,320,62,"Creative Look / QEMU preview",DIM);
    static const uint32_t colors[]={0xc85c4d,0xd8ba62,0x71a55e,0x4da9ad,0x647bc1,0xb977ad,0xc85c4d};
    for(int side=0;side<2;side++) {
        int x=18+side*315;
        center(&small,x+144,89,side?FL_NAME:"Standard",FG);
        for(int y=0;y<144;y++) for(int i=0;i<289;i++) {
            uint32_t color;
            if(y<34) { unsigned v=i*255/288; color=v*0x010101; }
            else if(y<100) {
                unsigned q=i*6*256/289;
                color=mix(colors[q/256],colors[q/256+1],q%256);
                color=mix(0,color,32+(y-34)*224/65);
            } else {
                int step=1+i/97;
                unsigned v=((i/step+y/step)&1)?170:90;
                color=v*0x010101;
            }
            pixels[(y+100)*W+x+i]=color;
        }
        if(side) fl_process(pixels+100*W+x,W,289,144,&fl_draft);
        border(x,100,289,144,0x666666);
    }
    for(int i=0;i<FL_ADJUST_COUNT;i++) {
        int x=18+(i%4)*153,y=254+(i/4)*62;
        bool locked=i==FL_RANGE && (mode>=8||recording);
        fill(x,y,145,56,i==fl_focus?HIGHLIGHT:0x202020);
        border(x,y,145,56,i==fl_focus?0xffb27a:0x555555);
        center(&small,x+72,y+21,fl_adjust_names[i],locked?DIM:FG);
        char value[8];int at=0,n=fl_draft.v[i];
        if(n<0) {value[at++]='-';n=-n;} else if(fl_minimum[i]<0) value[at++]='+';
        nstr(value+at,n);
        center(&body,x+72,y+49,value,locked?DIM:FG);
    }
    label(&small,20,397,fl_adjust_names[fl_focus],FG);
    char range[24];int at=0,lo=fl_minimum[fl_focus];
    if(lo<0) {range[at++]='-';lo=-lo;}
    at+=nstr(range+at,lo);range[at++]=' ';range[at++]='.';range[at++]='.';range[at++]=' ';
    if(fl_minimum[fl_focus]<0) range[at++]='+';
    nstr(range+at,fl_maximum[fl_focus]);
    right(&small,620,397,fl_focus==FL_RANGE&&(mode>=8||recording)?"Unavailable in movie":range,DIM);
    center(&small,320,423,"Left/Right: item  Up/Down: value  C: reset",FG);
    fill(0,435,W,1,0x585858);
    center(&small,320,456,"Enter: apply in QEMU / Esc: cancel",FG);
    center(&micro,320,477,"Experimental model - not Sony processing",DIM);
#endif
}
static void uart(const char *s)
{
    for (;*s;s++) {
        while(UART[6] & 0x20) {}
        UART[0] = *s;
    }
}
static void report(void)
{
    static const char *const labels[]={"shoot","menu","fn","play","index","option","quick","preset","fl-preview"};
    char b[12];
    uart(labels[screen]); uart(" ");
    if (screen==MENU) {
        nstr(b,tab+1); uart(b); uart("/");
        nstr(b,page_no+1); uart(b); uart(" ");
        if (row<0) uart("tabs"); else uart(items[current_item()].name);
    } else if (screen==OPTION) {
        uart(items[option_id].name); uart(" ");
        nstr(b,option); uart(b);
    } else if(screen==FN || screen==QUICK) {
        nstr(b,fn_slot+1); uart(b);
    } else if(screen==PLAY || screen==INDEX) {
        nstr(b,shots); uart(b);
    }
    if (screen==OPTION && option_id==ITEM_CREATIVE_STYLE) {
        const int values[]={creative_contrast,creative_saturation,creative_sharpness};
        const char *names[]={" C="," S="," H="};
        for(int i=0;i<3;i++) {
            uart(names[i]); if(values[i]<0) uart("-");
            nstr(b,values[i]<0?-values[i]:values[i]); uart(b);
        }
        uart(" WB="); uart(value_of(ITEM_WHITE_BALANCE));
        uart(" PP="); uart(value_of(ITEM_PICTURE_PROFILE));
        uart(" FX="); uart(value_of(ITEM_PICTURE_EFFECT));
        uart(" BASE="); uart(creative_base_style);
    }
#if FL_LOOK_INDEX >= 0
    uart(selected[ITEM_CREATIVE_LOOK]==FL_LOOK_INDEX?" FL=1 LUT=33":" FL=0");
    if(screen==FLPREVIEW || (screen==OPTION && option_id==ITEM_CREATIVE_LOOK)) {
        const FLAdjust *a=screen==FLPREVIEW?&fl_draft:&fl_saved;
        uart(" ADJ=");
        for(int i=0;i<FL_ADJUST_COUNT;i++) {
            if(i) uart(",");
            int v=a->v[i];if(v<0) {uart("-");v=-v;}
            nstr(b,v);uart(b);
        }
        if(screen==FLPREVIEW) {uart(" FOCUS=");nstr(b,fl_focus);uart(b);}
    }
#endif
    uart(use_chinese()?" [zh-CN]\n":" [en]\n");
}
static void paint(void)
{
    static unsigned buffer;
    buffer ^= 1;
    pixels=(uint32_t *)(uintptr_t)(0x02000000u + buffer*0x200000u);
    switch (screen) {
    case SHOOT: draw_shoot(); break;
    case MENU: draw_menu(); break;
    case FN: draw_fn(false); break;
    case QUICK: draw_fn(true); break;
    case PLAY: case INDEX: draw_play(); break;
    case OPTION: draw_options(); break;
    case PRESET: draw_preset(); break;
    case FLPREVIEW: draw_fl_preview(); break;
    }
    __asm__ volatile("dsb sy" ::: "memory");
    LCD[4]=(uint32_t)(uintptr_t)pixels;
    report();
}
static void reset_choices(void)
{
    for (unsigned i=0;i<COUNT(items);i++) selected[i]=items[i].initial;
    creative_contrast=creative_saturation=creative_sharpness=0;
    creative_base_style="Standard";
#if FL_LOOK_INDEX >= 0
    fl_saved=fl_draft=fl_defaults;
    fl_focus=0;
#endif
}
#if RETRO_STYLE_INDEX >= 0
static void choose_value(int id, const char *value)
{
    for(int i=0;i<items[id].count;i++)
        if(!compare(choices[items[id].first+i],value)) { selected[id]=i; return; }
}
static void apply_preset(void)
{
#if FL_LOOK_INDEX >= 0
    selected[ITEM_CREATIVE_LOOK]=0;
#endif
    selected[ITEM_CREATIVE_STYLE]=RETRO_STYLE_INDEX;
    creative_contrast=RETRO_CONTRAST;
    creative_saturation=RETRO_SATURATION;
    creative_sharpness=RETRO_SHARPNESS;
    creative_base_style=RETRO_BASE_STYLE;
    choose_value(ITEM_WHITE_BALANCE,RETRO_WHITE_BALANCE);
    choose_value(ITEM_PICTURE_PROFILE,RETRO_PICTURE_PROFILE);
    choose_value(ITEM_PICTURE_EFFECT,RETRO_PICTURE_EFFECT);
}
#endif
static void choose_tab(int t)
{
    remembered[tab]=page_no;
    tab=t;
    page_no=min(remembered[tab],current_total()-1);
    row=-1;
}
static void choose_page(int p)
{
    page_no=wrap(p,current_total());
    row=row<0 ? -1 : min(row,rows()-1);
}
static void edit(int id)
{
    option_id=id; option=selected[id]; parent=screen; screen=OPTION;
}
static void open_menu(void)
{
    return_screen=screen==INDEX?PLAY:screen;
    screen=MENU;
}
static void close_menu(void)
{
    if (adding) {
        adding=false; choose_tab(5); page_no=current_total()-1; row=0;
    } else {
        screen=return_screen;
    }
}
static void clear_shots(void)
{
    shots=0; playback=0; movie_frame=false; zoomed=false;
}
static void add_sample(bool movie)
{
    if(shots<9) shots++;
    playback=shots-1;
    movie_frame=movie;
    zoomed=false;
}
static void handle(enum Key k)
{
    if (k==LANGUAGEKEY) {
        selected[ITEM_LANGUAGE]^=1;
        if (screen==OPTION && option_id==ITEM_LANGUAGE) option=selected[ITEM_LANGUAGE];
        return;
    }
    if (screen!=OPTION && screen!=PRESET && screen!=FLPREVIEW && k>=TAB1 && k<=TAB6) {
        if(screen!=MENU) open_menu();
        choose_tab(k-TAB1); page_no=0; row=0;
        return;
    }
    if(screen==FLPREVIEW) {
#if FL_LOOK_INDEX >= 0
        if(k==CONFIRM) {
            fl_saved=fl_draft;
            selected[ITEM_CREATIVE_LOOK]=FL_LOOK_INDEX;
            choose_value(ITEM_PICTURE_PROFILE,"Off");
            choose_value(ITEM_PICTURE_EFFECT,"Off");
            screen=parent;
        } else if(k==BACK||k==MENUKEY) screen=OPTION;
        else if(k==LEFT||k==RIGHT) fl_focus=wrap(fl_focus+(k==LEFT?-1:1),FL_ADJUST_COUNT);
        else if(k==UP||k==DOWN) {
            if(fl_focus!=FL_RANGE || (mode<8&&!recording))
                fl_draft.v[fl_focus]=fl_limit(fl_draft.v[fl_focus]+(k==UP?1:-1),
                                            fl_minimum[fl_focus],fl_maximum[fl_focus]);
        } else if(k==DELETEKEY) fl_draft=fl_defaults;
#endif
        return;
    }
    if(screen==PRESET) {
#if RETRO_STYLE_INDEX >= 0
        if(k==CONFIRM) { apply_preset(); screen=parent; }
        else if(k==BACK||k==MENUKEY) screen=OPTION;
#endif
        return;
    }
    if (screen==OPTION) {
        const Item *a=&items[option_id];
        int count=option_id==ITEM_FORMAT||option_id==ITEM_SETTING_RESET?2:a->count;
        if(k==UP||k==DOWN||k==LEFT||k==RIGHT) {
            if(count) option=wrap(option+((k==UP||k==LEFT)?-1:1),count);
        } else if(k==CONFIRM) {
            if(option_id==ITEM_CREATIVE_LOOK && option==FL_LOOK_INDEX) {
#if FL_LOOK_INDEX >= 0
                fl_draft=fl_saved;fl_focus=0;
#endif
                screen=FLPREVIEW;
                return;
            }
            if(option_id==ITEM_CREATIVE_STYLE && option==RETRO_STYLE_INDEX) {
                screen=PRESET;
                return;
            }
            if(a->count) selected[option_id]=option;
            if(option_id==ITEM_CREATIVE_STYLE) {
#if FL_LOOK_INDEX >= 0
                selected[ITEM_CREATIVE_LOOK]=0;
#endif
                creative_contrast=creative_saturation=creative_sharpness=0;
                creative_base_style=choices[a->first+option];
            }
            if((option_id==ITEM_PICTURE_PROFILE || option_id==ITEM_PICTURE_EFFECT) && option!=0) {
#if FL_LOOK_INDEX >= 0
                selected[ITEM_CREATIVE_LOOK]=0;
#endif
                selected[ITEM_CREATIVE_STYLE]=0;
                creative_contrast=creative_saturation=creative_sharpness=0;
                creative_base_style="Standard";
            }
            if(option_id==ITEM_SETTING_RESET) { reset_choices(); if(option==1) my_count=0; }
            if(option_id==ITEM_FORMAT && option==1) clear_shots();
            screen=parent;
        } else if(k==BACK||k==MENUKEY) screen=parent;
        return;
    }
    if (screen==MENU) {
        switch (k) {
        case MENUKEY: case BACK: close_menu(); break;
        case FNKEY: choose_tab(wrap(tab+1,6)); break;
        case PAGEUP: choose_page(page_no-1); break;
        case PAGEDOWN: choose_page(page_no+1); break;
        case LEFT: case RIGHT:
            if (row<0) choose_tab(wrap(tab+(k==LEFT?-1:1),6));
            else choose_page(page_no+(k==LEFT?-1:1));
            break;
        case UP: if(row>=0) row--; break;
        case DOWN: if(row<rows()-1) row++; break;
        case CONFIRM:
            if (row<0) { row=0; break; }
            if (adding) {
                if(tab!=5 && my_count<30) {
                    int id=current_item();
                    bool exists=false;
                    for(int i=0;i<my_count;i++) if(my_items[i]==id) exists=true;
                    if(!exists) my_items[my_count++]=id;
                }
                adding=false; choose_tab(5); page_no=0; row=0;
            } else if(current_item()==ITEM_ADD_ITEM) {
                adding=true; choose_tab(0); row=0;
            } else if(current_item()==ITEM_DELETE_ALL) {
                my_count=0; page_no=0; row=0;
            } else if(current_item()==ITEM_DELETE_PAGE && my_count) {
                my_count=max(0,my_count-6); page_no=current_total()-1;
            } else if(current_item()==ITEM_DELETE_ITEM && my_count) {
                my_count--; page_no=current_total()-1;
            } else {
                edit(current_item());
            }
            break;
        case SHUTTER: adding=false; screen=SHOOT; break;
        default: break;
        }
        return;
    }
    if (k==MENUKEY) { open_menu(); return; }
    if (screen==FN || screen==QUICK) {
        if (k==LEFT||k==RIGHT) fn_slot=wrap(fn_slot+(k==LEFT?-1:1),12);
        if (k==UP||k==DOWN) fn_slot=(fn_slot+12+
            (screen==QUICK?(k==UP?-2:2):6))%12;
        if (k==CONFIRM) edit(fn_items[fn_slot]);
        if (k==BACK||k==FNKEY) screen=SHOOT;
        return;
    }
    if (screen==PLAY||screen==INDEX) {
        if (deleting) {
            if(k==UP||k==DOWN||k==LEFT||k==RIGHT) option^=1;
            if(k==CONFIRM && option==1 && shots) { shots--; playback=max(0,min(playback,shots-1)); }
            if(k==CONFIRM||k==BACK) deleting=false;
            return;
        }
        if(k==PLAYKEY||k==SHUTTER) { screen=SHOOT; disp=0; }
        if(k==BACK) { screen=screen==INDEX?PLAY:SHOOT; disp=0; }
        if(k==DISPKEY) disp=disp==0?2:disp==2?3:0;
        if(k==INDEXKEY && shots) { screen=screen==INDEX?PLAY:INDEX; zoomed=false; }
        if(k==ZOOMKEY && shots) { screen=PLAY; zoomed=!zoomed; }
        if(k==CONFIRM && screen==INDEX) screen=PLAY;
        if(k==DELETEKEY && shots) { deleting=true; option=0; }
        if(shots && (k==LEFT||k==RIGHT)) playback=wrap(playback+(k==LEFT?-1:1),shots);
        if(screen==INDEX && shots && (k==UP||k==DOWN))
            playback=(playback+shots+(k==UP?-3:3)+shots)%shots;
        return;
    }
    switch(k) {
    case PLAYKEY: screen=PLAY; disp=0; break;
    case FNKEY: screen=disp==4?QUICK:FN; fn_slot=0; break;
    case DISPKEY: case UP: disp=(disp+1)%7; break;
    case LEFT: mode=wrap(mode-1,(int)COUNT(modes)); break;
    case RIGHT: mode=wrap(mode+1,(int)COUNT(modes)); break;
    case SHUTTER: add_sample(false); break;
    case MOVIE: recording=!recording;
        if(recording && disp==4) disp=0;
        if(!recording) add_sample(true);
        break;
    default: break;
    }
}

static enum Key get_key(void)
{
    static bool extended, released;
    if(!(KMI[1]&0x10)) return NONE;
    uint32_t code=KMI[2]&0xff;
    if(code==0xe0) { extended=true; return NONE; }
    if(code==0xf0) { released=true; return NONE; }
    bool e=extended, r=released;
    extended=released=false;
    if(r) return NONE;
    if(e) {
        switch(code) {
        case 0x75: return UP;
        case 0x72: return DOWN;
        case 0x6b: return LEFT;
        case 0x74: return RIGHT;
        case 0x7d: return PAGEUP;
        case 0x7a: return PAGEDOWN;
        case 0x71: return DELETEKEY;
        case 0x5a: return CONFIRM;
        default: return NONE;
        }
    }
    switch(code) {
    case 0x5a: return CONFIRM;
    case 0x66: case 0x76: return BACK;
    case 0x3a: return MENUKEY;
    case 0x2b: return FNKEY;
    case 0x4d: return PLAYKEY;
    case 0x23: return DISPKEY;
    case 0x29: case 0x1b: return SHUTTER;
    case 0x2d: return MOVIE;
    case 0x43: return INDEXKEY;
    case 0x21: return DELETEKEY; /* C4 on compact keyboards */
    case 0x1a: return ZOOMKEY;
    case 0x4b: return LANGUAGEKEY; /* L: toggle the verification locale. */
    case 0x16: return TAB1;
    case 0x1e: return TAB2;
    case 0x26: return TAB3;
    case 0x25: return TAB4;
    case 0x2e: return TAB5;
    case 0x36: return TAB6;
    default: return NONE;
    }
}
void guest_main(void)
{
    KMI[0]=4;
    LCD[0]=((W/16)-1)<<2;
    LCD[1]=H-1;
    reset_choices();
#if FL_LOOK_INDEX >= 0
    if(!fl_selftest()) { uart("FL_LUT_SELFTEST_FAIL\n"); for(;;) {} }
    uart("FL_LUT_SELFTEST_PASS 512\n");
    if(!fl_adjust_selftest()) {uart("FL_ADJUST_SELFTEST_FAIL\n");for(;;) {}}
    uart("FL_ADJUST_SELFTEST_PASS\n");
#endif
    screen=MENU;
    return_screen=SHOOT;
    paint();
    LCD[6]=0x92b;
    for (;;) {
        enum Key k=get_key();
        if(k!=NONE) { handle(k); paint(); }
    }
}
