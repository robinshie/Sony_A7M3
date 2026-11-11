#define main stock_suite
#include "menu_lazy_harness.c"
#undef main
int main(void) {
    CHECK(stock_suite()==0,"v3 menu regression");
    unsigned *entries=dlsym(0,"synthetic_menu_entries");
    unsigned *root=(void *)((uintptr_t)entries+760);
    unsigned *rows=(void *)(uintptr_t)root[0];
    CHECK(rows[194]==0x0205c049,"RW large badge");
    CHECK(rows[198]==0x0205c04a,"RW small badge");
    for(unsigned i=0;i<19;i++) {
        CHECK(rows[i*10+4]==entries[i*10+4],"original large badges");
        CHECK(rows[i*10+8]==entries[i*10+8],"original small badges");
    }
    say("QEMU_ICONS_MENU_PASSED custom row and 19 preserved original rows\n");
    return 0;
}
