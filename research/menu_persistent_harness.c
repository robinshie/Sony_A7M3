#include <stdint.h>
extern void *dlsym(void *,const char *);
static long sc(long n,long a,long b,long c) {
    register long r7 __asm__("r7")=n;
    register long r0 __asm__("r0")=a;
    register long r1 __asm__("r1")=b;
    register long r2 __asm__("r2")=c;
    __asm__ volatile("svc #0":"+r"(r0):"r"(r7),"r"(r1),"r"(r2):"memory","cc");
    return r0;
}
static void say(const char *s) {unsigned n=0;while(s[n])n++;sc(4,1,(long)s,n);}
static void fail(const char *s) {say("FAIL ");say(s);say("\n");sc(1,77,0,0);}
#define CHECK(x,s) do {if(!(x))fail(s);} while(0)
static const unsigned char original_map[]={
#include "map-values.h"
};
int main(void) {
    unsigned *entries=dlsym(0,"synthetic_menu_entries");
    unsigned *calls=dlsym(0,"old_init_calls");
    unsigned *root=(void *)((uintptr_t)entries+760);
    int (*dispatch)(void *,int,int *)=dlsym(0,"persistent_dispatch");
    void (*init)(void)=dlsym(0,"persistent_init");
    int (*parameters)(void *,int *)=dlsym(0,"test_parameters");
    CHECK(entries&&calls&&dispatch&&init&&parameters,"symbols");
    CHECK(*calls==1&&root[1]==20&&root[2]==97,"dynamic initializer and menu root");
    unsigned *extra=(void *)(uintptr_t)root[0];
    for(unsigned i=0;i<190;i++) CHECK(extra[i]==entries[i],"original rows");
    CHECK(extra[192]==98&&extra[193]==0x0204ed84,"new row");
    for(int i=-128;i<128;i++) {
        int box=-99,style=dispatch(0,i,&box);
        if(i>=0&&i<=96) CHECK(style==original_map[2*i]&&box==original_map[2*i+1],"original mapping");
        else if(i==98) CHECK(style==3&&box==3,"recipe mapping");
        else CHECK(style==14&&box==-99,"invalid mapping");
    }
    /* The hook runs in the original selection frame, before its setter call. */
    unsigned context[76]={0};
    int id;
    context[75]=(uintptr_t)&id;
    for(id=-1;id<100;id++) for(int c=-3;c<=3;c++) for(int s=-3;s<=3;s++) for(int h=-3;h<=3;h++) {
        int frame[3]={h,s,c};
        int got=parameters(context,frame);
        CHECK(frame[0]==(id==98?-1:h)&&frame[1]==(id==98?-1:s)&&frame[2]==(id==98?1:c),"parameter override");
        CHECK(got==frame[2],"original resumed instruction");
    }
    init();
    CHECK(*calls==2&&root[0]==(uintptr_t)extra&&root[1]==20,"duplicate init");
    say("QEMU_PERSISTENT_MENU_PASSED 256 dispatch cases; 34643 parameter cases\n");
    return 0;
}
