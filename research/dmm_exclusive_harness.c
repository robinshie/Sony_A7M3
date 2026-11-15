/* Execute original kernel resource bookkeeping; no OS, pixel, or DMA access. */
#include <stdint.h>
enum { HANDLE=(3u<<10)|7, BUSY=-13057, BAD_GENERATION=-517 };
static unsigned checks;
static uint8_t *unit=(uint8_t *)(0x42000000u+0x94678+7*0x150+0xb10);
static uint32_t extent[12],out[4];
static uint16_t count;
static int (*const open_unit)(unsigned,unsigned,void *,void *)=(void *)0x4100889c;
static int (*const close_unit)(unsigned)=(void *)0x41008a28;
static void print(const char *p){volatile unsigned *u=(void *)0x09000000;while(*p){while(u[6]&32){}u[0]=(uint8_t)*p++;}}
static void stop(void){register unsigned r0 __asm__("r0")=0x18,r1 __asm__("r1")=0x20026;__asm__ volatile("svc 0x123456":"+r"(r0),"+r"(r1)::"memory");for(;;){}}
static void check(int ok,const char *name){checks++;if(!ok){print("FAIL ");print(name);print("\n");stop();}}
static unsigned state(void){return *(uint16_t *)(unit+0x14);}
static void reset(void){
    for(unsigned i=0;i<0x150;i++)unit[i]=0;
    unit[0x13]=3;*(uint16_t *)(unit+0x14)=1;*(uint16_t *)(unit+0x16)=1;
    extent[1]=0x18000000;extent[2]=0x1000;extent[3]=0x2000;
    *(uintptr_t *)(unit+0x18)=(uintptr_t)extent;
    for(unsigned i=0;i<4;i++)out[i]=0xa5a5a5a5;
    count=0xaaaa;
}
static void bounds(void){check(out[0]==0x18001000 && out[1]==0x2000 && out[2]==0xa5a5a5a5 && count==1,"single extent output");}
void guest_main(void){
    checks=0;
    unsigned (*index_of)(unsigned)=(void *)0x410085a4;
    unsigned (*generation_of)(unsigned)=(void *)0x410085d8;
    for(unsigned h=0;h<65536;h++){
        check(index_of(h)==(h&1023)+((h>>15)<<10),"original handle index all 65536 values");
        check(generation_of(h)==((h>>10)&31),"original handle generation all 65536 values");
    }
    for(unsigned index=0;index<0x580;index++){
        unsigned h=(index&1023)|((index>>10)<<15)|(3<<10);
        unit=(void *)(0x42094678+index*0x150+0xb10);reset();
        check(open_unit(h,4,out,&count)==0&&state()==3&&unit[0x11]==1,"both index banks exclusive open");
        check(close_unit(h)==0&&state()==1&&!unit[0x11],"both index banks close");
    }
    check(open_unit(0x8000|(3<<10)|0x180,4,out,&count)==-261,"native index limit 0x580");
    unit=(void *)(0x42094678+7*0x150+0xb10);reset();
    check(open_unit(HANDLE,4,out,&count)==0,"exclusive acquisition");bounds();
    check(state()==3 && unit[0x11]==1,"exclusive state");
    check(open_unit(HANDLE,0,out,&count)==BUSY && count==0,"ordinary open excluded");
    check(open_unit(HANDLE,1,out,&count)==BUSY,"mode one excluded");
    check(open_unit(HANDLE,4,out,&count)==BUSY,"second exclusive excluded");
    check(state()==3 && unit[0x11]==1,"failed opens preserve owner");
    check(close_unit(HANDLE)==0 && state()==1 && !unit[0x11],"exclusive release");
    check(open_unit(HANDLE,0,out,&count)==0,"ordinary after release");bounds();
    check(open_unit(HANDLE,1,out,&count)==0 && state()==2 && unit[0x11]==2,"ordinary sharing permitted");
    check(open_unit(HANDLE,4,out,&count)==BUSY && unit[0x11]==2,"exclusive refuses active references");
    check(close_unit(HANDLE)==0 && state()==2 && unit[0x11]==1,"first reference released");
    check(open_unit(HANDLE,4,out,&count)==BUSY,"remaining reader blocks exclusive");
    check(close_unit(HANDLE)==0 && state()==1 && unit[0x11]==0,"last reference released");
    check(open_unit(HANDLE,4,out,&count)==0,"exclusive after all references close");bounds();
    check(close_unit(HANDLE)==0,"second release");
    reset();unit[0x12]=1;
    check(open_unit(HANDLE,4,out,&count)==-1 && count==0 && state()==1 && !unit[0x11],"rendezvous blocks exclusive");
    reset();check(open_unit(HANDLE^(1<<10),4,out,&count)==BAD_GENERATION && state()==1,"retired generation rejected");
    reset();check(open_unit(HANDLE,2,out,&count)==-4 && state()==1,"unknown access mode rejected");
    reset();*(uint16_t *)(unit+0x14)=0;
    check(open_unit(HANDLE,4,out,&count)==-1 && count==0,"inactive unit rejected");
    reset();unit[0x11]=255;*(uint16_t *)(unit+0x14)=2;
    check(open_unit(HANDLE,0,out,&count)==-1 && unit[0x11]==255,"reference overflow rejected");
    check(open_unit(HANDLE,4,out,&count)==BUSY && unit[0x11]==255,"overflow is not exclusivity");
    char b[12];unsigned at=11,n=checks;b[at]=0;do{b[--at]=(char)('0'+n%10);n/=10;}while(n);
    print("DMM_EXCLUSIVE_PASSED checks=");print(b+at);print("\n");stop();
}
