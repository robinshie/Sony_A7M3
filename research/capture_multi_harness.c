#include <stdint.h>
#ifndef TEST_UDF
#define TEST_UDF 0xaa75f7f0
#define TEST_RETURN 0x7a75
#endif
#ifdef TEST_EARLY
static const unsigned sites[]={0x636faccc,0x636fac3c,0x636e24e8,0x636e1098};
#elif defined(TEST_VFX)
static const unsigned sites[]={0x636faccc,0x636fac3c,0x636e1344,0x636e1098};
#else
static const unsigned sites[]={0x638fb88c,0x636e0df0,0x63aad0e0,0x63a22e58};
#endif
extern char a7_bridge_0[],a7_bridge_1[],a7_bridge_2[],a7_bridge_3[],a7_undef_test_site[];
extern unsigned a7_undef_test(void);
static char *const bridges[]={a7_bridge_0,a7_bridge_1,a7_bridge_2,a7_bridge_3};
static unsigned wanted[4],which,calls,records,checks,self_hits,exceptions;
static void print(const char *s){volatile unsigned *u=(void *)0x09000000;while(*s){while(u[6]&32){}u[0]=*s++;}}
static void number(unsigned n){char s[12];unsigned i=11;s[i]=0;do{s[--i]='0'+n%10;n/=10;}while(n);print(s+i);}
static void stop(void){register unsigned r0 __asm__("r0")=0x18,r1 __asm__("r1")=0x20026;__asm__ volatile("svc 0xab":"+r"(r0),"+r"(r1)::"memory");for(;;){}}
static void check(int b){checks++;if(!b){print("FAIL check ");number(checks);print("\n");stop();}}
unsigned fixture_undef(unsigned pc,unsigned cpsr){
    check((cpsr&0x3f)==0x33);check(*(unsigned *)pc==TEST_UDF);
    if(pc==(unsigned)a7_undef_test_site){self_hits++;return pc+4;}
    check(pc==sites[which]);exceptions++;return (unsigned)bridges[which]&~1u;
}
void a7_multi_record(unsigned index,const unsigned *regs){
    check(index==which);check(((unsigned)regs&7)==0);
    for(unsigned i=0;i<4;i++)check(regs[i]==wanted[i]);
    check(regs[13]!=0);records++;
    __asm__ volatile("movs r0,#0\nmovs r1,#0\nmovs r2,#0\nmovs r3,#0\nmov ip,r0":::"r0","r1","r2","r3","r12","cc");
}
unsigned original_call(unsigned a,unsigned b,unsigned c,unsigned d){
    check(a==wanted[0]&&b==wanted[1]&&c==wanted[2]&&d==wanted[3]);calls++;
    return a^b^c^d;
}
void guest_main(void){
    check(a7_undef_test()==TEST_RETURN&&self_hits==1);
    for(which=0;which<4;which++)for(unsigned n=0;n<32;n++){
        for(unsigned i=0;i<4;i++)wanted[i]=0x60000001u+n*0x12345u+i*0x234567u;
        unsigned (*fn)(unsigned,unsigned,unsigned,unsigned)=(void *)(sites[which]-3);
        unsigned r=fn(wanted[0],wanted[1],wanted[2],wanted[3]);
        check(r==(wanted[0]^wanted[1]^wanted[2]^wanted[3]));
    }
    check(calls==128&&records==calls&&exceptions==calls);
    print("MULTI_CALLBACK_PASSED calls=");number(calls);print(" checks=");number(checks);print("\n");stop();
}
