/* display-suite.h is reproduced from the pinned previous harness, with only
 * its main renamed. Includes the complete menu, recipe and footer tests. */
#include "display-suite.h"
static unsigned belt[1100], menu_data[20], menu_vtable[30];
static int count_rows(void *unused,unsigned *row) {(void)unused;return row[1]&255;}
static int no_children(void *unused,unsigned *row) {(void)unused;(void)row;return 0;}
static int subitem(void *unused,unsigned *row,int index,unsigned **out) {
    (void)unused;
    *out=(unsigned *)(uintptr_t)row[0]+10*index;
    return 1;
}
static const unsigned expected[2][13][2]={
#include "belt-expected.h"
};
int main(void) {
    CHECK(display_suite()==0,"menu and footer regression");
    unsigned *entries=dlsym(0,"synthetic_menu_entries");
    unsigned *root=entries+190;
    unsigned *rows=(void *)(uintptr_t)root[0];
    unsigned (*ordinary)(void *,int)=dlsym(0,"native_belt_ordinary");
    unsigned (*highlighted)(void *,int)=dlsym(0,"native_belt_highlighted");
    void *getter=dlsym(0,"native_belt_getter");
    CHECK(ordinary&&highlighted&&getter,"native belt symbols");
    CHECK(rows[196]==359&&rows[26]==320,"custom belt index and original Neutral");
    menu_vtable[8]=(uintptr_t)count_rows;menu_vtable[12]=(uintptr_t)getter;
    menu_vtable[24]=(uintptr_t)no_children;menu_vtable[25]=(uintptr_t)subitem;
    menu_data[0]=(uintptr_t)menu_vtable;menu_data[19]=0;
    belt[1034]=(uintptr_t)root;belt[1036]=(uintptr_t)menu_data;
    unsigned cases=0;
    for(unsigned panel=0;panel<2;panel++) {
        belt[1032]=panel;
        /* First reproduce the user's failure with the old custom index. */
        rows[196]=320;
        CHECK(ordinary(belt,19)==0x0205c7af,"old row reproduces white Ntrl");
        CHECK(highlighted(belt,19)==0x0205c9e7,"old row reproduces orange Ntrl");
        rows[196]=359;
        CHECK(ordinary(belt,19)==0x0205c76d,"custom ordinary RW");
        CHECK(highlighted(belt,19)==0x0205c9b5,"custom orange RW");
        CHECK(belt[1030]==98,"selected identity remains 98");
        cases+=4;
        for(unsigned i=0;i<13;i++) {
            CHECK(ordinary(belt,i)==expected[panel][i][0],"all stock ordinary images");
            CHECK(highlighted(belt,i)==expected[panel][i][1],"all stock orange images");
            CHECK(belt[1030]==i,"stock selected identity");
            cases+=2;
        }
        CHECK(ordinary(belt,-1)==0x0205c6bd&&ordinary(belt,20)==0x0205c6bd,"ordinary range guard");
        CHECK(highlighted(belt,-1)==0x0205c6bd&&highlighted(belt,20)==0x0205c6bd,"selected range guard");
        cases+=4;
    }
    CHECK(cases==68,"belt case count");
    for(unsigned i=0;i<190;i++)CHECK(rows[i]==entries[i],"19 stock rows remain exact");
    say("QEMU_RW_BELT_PASSED 68 native normal/highlighted lookups; old failure reproduced; both panel tables; stock Neutral preserved\n");
    return 0;
}
