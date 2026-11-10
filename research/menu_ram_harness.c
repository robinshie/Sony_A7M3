/* QEMU-only driver. Loads tested RAM payloads against a synthetic mapped library. */
#define A7_RUNTIME_LIBRARY_ONLY
#include "../payloads/a7-runtime-probe.c"
#include "menu-ram-data.h"
extern void *dlopen(const char *,int);
extern int dlclose(void *);
extern void *dlsym(void *,const char *);
static void message(const char *s) {unsigned n=0;while(s[n])n++;sc3(4,1,(long)s,n);}
static void fail(const char *s) {message("FAIL ");message(s);message("\n");sc3(1,77,0,0);}
#define CHECK(x,s) do {if(!(x))fail(s);} while(0)
static uint32_t returned[13];
static void module(const char *name,int action,int status,int error) {
    sc3(10,(long)"/tmp/jiritsu/a7menu.bin",0,0);
    void *h=dlopen(name,2);
    CHECK(h,"dlopen");
    CHECK(read_proc("/tmp/jiritsu/a7menu.bin",(char *)returned,49)==48,"report size");
    CHECK(returned[0]==0x41374d54&&returned[1]==(unsigned)action&&returned[2]==(unsigned)status&&
          (int)returned[11]==error,"report status");
    CHECK(dlclose(h)==0,"dlclose");
}
int main(void) {
    message("RAM_TEST_START\n");
    unsigned *entries=dlsym(0,"synthetic_menu_entries");
    CHECK(entries,"fixture");
    uintptr_t base=(uintptr_t)entries-0xa60998;
    unsigned *root=(void *)(base+0xa60c90);
    int (*dispatch)(void *,int,int *)=(void *)(base+0x5b98dd);
    int before[102][2];
    for(int i=-2;i<100;i++) {before[i+2][1]=-99;before[i+2][0]=dispatch(0,i,&before[i+2][1]);}
    message("RAM_TEST_BASELINE_OK\n");
    module("/tmp/install.so",0,1,0);
    message("RAM_TEST_INSTALL_OK\n");
    CHECK(root[1]==20&&root[2]==97&&root[0]!=(uintptr_t)entries,"new root");
    unsigned *new_entries=(void *)(uintptr_t)root[0];
    for(unsigned i=0;i<190;i++) CHECK(new_entries[i]==entries[i],"old entry preserved");
    CHECK(new_entries[192]==98&&new_entries[193]==0x0204f7e6,"new entry");
    for(int i=-2;i<100;i++) {
        int box=-99,style=dispatch(0,i,&box);
        if(i==98) CHECK(style==3&&box==3,"new dispatch");
        else CHECK(style==before[i+2][0]&&box==before[i+2][1],"old dispatch preserved");
    }
    message("RAM_TEST_DISPATCH_OK\n");
    int box=-99;
    CHECK(dispatch(0,98,&box)==3&&box==3,"trace call");
    module("/tmp/inspect.so",1,2,0);
    CHECK(returned[7]==103&&returned[8]==98&&returned[9]==3&&returned[10]==3,"trace values");
    module("/tmp/install.so",0,2,0);
    CHECK(root[1]==20,"idempotent install");
    module("/tmp/restore.so",2,3,0);
    message("RAM_TEST_RESTORE_OK\n");
    CHECK(root[1]==19&&root[0]==(uintptr_t)entries,"restored root");
    const unsigned char *code=(void *)(base+0x5b98dc);
    for(unsigned i=0;i<sizeof original_dispatch;i++) CHECK(code[i]==original_dispatch[i],"restored code");
    for(int i=-2;i<100;i++) {
        int slot=-99,style=dispatch(0,i,&slot);
        CHECK(style==before[i+2][0]&&slot==before[i+2][1],"restored dispatch");
    }
    module("/tmp/restore.so",2,0,-6);
    root[1]=18;
    module("/tmp/install.so",0,0,-7);
    CHECK(root[1]==18&&root[0]==(uintptr_t)entries,"wrong root untouched");
    root[1]=19;
    CHECK(sc3(125,(base+0x5b98dc)&~4095u,4096,7)==0,"test code permission");
    ((unsigned char *)code)[0]^=1;
    module("/tmp/install.so",0,0,-7);
    CHECK(code[0]==(original_dispatch[0]^1)&&root[1]==19,"wrong code untouched");
    ((unsigned char *)code)[0]^=1;
    sc3(0xf0002,(long)code,(long)code+sizeof original_dispatch,0);
    CHECK(sc3(125,(base+0x5b98dc)&~4095u,4096,5)==0,"restore test permission");
    message("QEMU_MENU_RAM_TESTS_PASSED\n");
    return 0;
}
