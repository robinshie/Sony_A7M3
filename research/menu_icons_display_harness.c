#define main stock_suite
#include "menu_lazy_harness.c"
#undef main

static unsigned combo[900], table[120], items[13][6], sizes[13];
static unsigned widgets[7][4];
static unsigned image, selected, called, csh[3];
static void nothing(void) {}
static void *get_widget(void *view,unsigned id) {
    (void)view;
    const unsigned ids[]={0x3e08b7c1,0x654cb9e6,0xa52216b1,
        0xce1ddaaf,0x278a4743,0x6c1ae279,0xbf331baa};
    if(id==0x33540d88)return combo;
    for(unsigned i=0;i<7;i++)if(id==ids[i])return widgets[i];
    return widgets[0];
}
static void set_image(void *icon,unsigned resource,unsigned flag) {
    CHECK(icon==(void *)((char *)combo+3092)&&flag==0,"native icon receiver");
    image=resource;called++;
}
static void set_index(void *widget,unsigned index) {
    CHECK(widget==combo&&index<13,"native index bounds");
    selected=index;
}
static void parameter(void *widget,int value) {
    for(unsigned i=0;i<3;i++)if(widget==widgets[i+2])csh[i]=value;
}
int main(void) {
    CHECK(stock_suite()==0,"native menu regression");
    unsigned *entries=dlsym(0,"synthetic_menu_entries");
    unsigned *root=(void *)((uintptr_t)entries+760);
    unsigned *rows=(void *)(uintptr_t)root[0];
    CHECK(rows[194]==0x0205c87e&&rows[198]==0x0205c823,"existing mapped RW references");
    for(unsigned i=0;i<19;i++)for(unsigned j=0;j<10;j++)
        CHECK(rows[i*10+j]==entries[i*10+j],"original rows preserved");
    void (**callbacks)(void)=dlsym(0,"display_callbacks");
    void (*display)(void *,int,int,int,int,int)=dlsym(0,"native_display");
    int (*count)(int)=dlsym(0,"native_count");
    CHECK(callbacks&&display&&count,"display symbols");
    callbacks[0]=(void (*)(void))get_widget;
    callbacks[1]=(void (*)(void))set_image;
    callbacks[2]=(void (*)(void))set_index;
    callbacks[3]=(void (*)(void))parameter;
    table[107]=(uintptr_t)dlsym(0,"native_combo_select");
    table[112]=(uintptr_t)nothing;
    combo[0]=(uintptr_t)table;combo[113]=13;
    combo[766]=(uintptr_t)items;combo[770]=(uintptr_t)sizes;
    combo[114]=80;combo[115]=70;
    for(unsigned i=0;i<13;i++) {items[i][0]=0x0205c863+i;sizes[i]=(60u<<16)|70;}
    CHECK(count(19)==13&&count(20)==13,"exact 13 model styles, no accidental box item");
    unsigned cases=0;
    /* Invoke the complete original display routine and original combo drawer.
     * Traverse both directions repeatedly to detect stale RW/Neutral state.
     */
    for(int pass=0;pass<3;pass++)for(int box=1;box<=6;box++)for(int j=1;j<=13;j++) {
        int style=pass==1?14-j:j;
        image=0;called=0;selected=99;csh[0]=csh[1]=csh[2]=99;
        display(0,style,1,-1,-1,box);
        unsigned resource=style==3&&box==3?0x0205c823:0x0205c862+style;
        CHECK(called==1&&selected==(unsigned)style-1&&image==resource,"original drawer resource and model index");
        CHECK(csh[0]==1&&csh[1]==(unsigned)-1&&csh[2]==(unsigned)-1,"parameter display unchanged");
        for(unsigned i=0;i<13;i++)if(i!=2)CHECK(items[i][0]==0x0205c863+i,"unrelated combo images");
        cases++;
    }
    /* A different widget layout must not receive a write. */
    combo[113]=12;items[2][0]=0x0205c865;
    display(0,3,1,-1,-1,3);
    CHECK(items[2][0]==0x0205c865,"unexpected count guarded");
    combo[113]=13;items[2][0]=0x12345678;
    display(0,3,1,-1,-1,3);
    CHECK(items[2][0]==0x12345678,"unexpected resource guarded");
    CHECK(cases==234,"case count");
    say("QEMU_RW_DISPLAY_PASSED 234 native display/draw transitions; guards; 19 stock rows; 13 model indices\n");
    return 0;
}
