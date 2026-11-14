/* Executes original enum converters and effect-state checker, in QEMU RAM.
 * Does not execute an image processor, hardware request, or camera transport. */
#include <stdint.h>
static unsigned checks,cases,log_count,get_count;
static uint32_t state[256];
static void put(const char *s){volatile unsigned *u=(volatile unsigned *)0x09000000;while(*s){while(u[6]&32){}u[0]=*s++;}}
static void num(unsigned n){char b[12];unsigned i=0;do{b[i++]=(char)('0'+n%10);n/=10;}while(n);while(i){char s[2]={b[--i],0};put(s);}}
static void end(void){register unsigned r0 __asm__("r0")=0x18,r1 __asm__("r1")=0x20026;__asm__ volatile("svc 0xab":"+r"(r0),"+r"(r1)::"memory");while(1){}}
static void check(int ok,const char *msg){checks++;if(!ok){put("FAIL ");put(msg);put(" case=");num(cases);put("\n");end();}}
void log_open(void){}
void log_close(void){}
uint32_t *get_state(void){get_count++;return state;}
void native_log(uint32_t fmt,uint32_t fn,int current,int requested){(void)fmt;(void)fn;(void)current;(void)requested;log_count++;}
void guest_main(void){
    typedef int (*Convert)(void *,unsigned,uint32_t *);
    Convert grain=(Convert)0x5046beb1,soft=(Convert)0x5046bf09;
    for(unsigned i=0;i<9;i++){
        unsigned v=i==8?0xffffffffu:i;uint32_t out=0xdeadbeef;
        int rc=grain(0,v,&out);check(rc==(v<4),"grain accepted enum");check(out==(v<4?0x293+v:0xdeadbeef),"grain value");
        out=0xdeadbeef;rc=soft(0,v,&out);check(rc==(v<3),"soft accepted enum");check(out==(v<3?0x297+v:0xdeadbeef),"soft value");cases++;
    }
    typedef void (*Checker)(const uint8_t *,unsigned);
    Checker checker=(Checker)(0x635c6000+0x6224b1);
    for(unsigned mode=7;mode<=8;mode++)for(unsigned current=0;current<4;current++)
        for(unsigned requested=0;requested<4;requested++)for(unsigned unrelated=0;unrelated<4;unrelated++)for(unsigned active=0;active<2;active++){
            for(unsigned i=0;i<256;i++)state[i]=0xaabbccdd;
            state[0xec/4]=mode;state[0xf0/4]=current;
            uint8_t request[32];for(unsigned i=0;i<32;i++)request[i]=0x5a;
            request[8]=(uint8_t)mode;request[mode==7?0xd:0xe]=(uint8_t)requested;
            request[mode==7?0xe:0xd]=(uint8_t)unrelated;
            get_count=log_count=0;checker(request,active);
            check(get_count==1,"state read once");check(log_count==(active&&current!=requested),"only selected effect strength checked");
            for(unsigned i=0;i<256;i++)check(state[i]==(i==0xec/4?mode:i==0xf0/4?current:0xaabbccdd),"checker leaves model untouched");
            for(unsigned i=0;i<32;i++)check(request[i]==(i==8?mode:i==(mode==7?0xd:0xe)?requested:i==(mode==7?0xe:0xd)?unrelated:0x5a),"request unchanged");
            cases++;
        }
    put("FILM_EFFECT_INTERFACE_CASES ");num(cases);put(" CHECKS ");num(checks);
    put("\nFILM_EFFECT_INTERFACE_PASSED\n");end();
}
