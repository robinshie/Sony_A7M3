/* Offline ABI experiment. This is never a camera payload.
 * Run the original message marshaller; mock only ObjMsg/Param/log boundaries. */
#include <stdint.h>
typedef struct { uint32_t id, present, values[3]; } Message;
static unsigned logs, reads, cases, dispatch;
static void put(const char *s) {
    volatile unsigned *u=(volatile unsigned *)0x10009000;
    while(*s) { while(u[6]&32) {} u[0]=*s++; }
}
static void finish(void) {
    register unsigned r0 __asm__("r0")=0x18;
    register unsigned r1 __asm__("r1")=0x20026;
    __asm__ volatile("svc 0xab" : "+r"(r0), "+r"(r1) : : "memory");
    while(1) {}
}
static void check(int ok,const char *reason) {
    if(!ok) { put("FAIL ");put(reason);put("\n");finish(); }
}
uint32_t message_id(Message *m) { return m->id; }
void *get_param(Message *m,uint32_t id) {
    check(id>=0x9a18 && id<=0x9a1a,"unexpected parameter request");
    unsigned i=id-0x9a18;reads++;
    return m->present & (1u<<i) ? &m->values[i] : 0;
}
uint32_t get_value(uint32_t *p) { return *p; }
void log_error(void) { logs++; } /* Do not dereference original format pointers. */
static void exercise(Message m,uint32_t sequence,int valid,int supported) {
    unsigned char buffer[48];
    for(unsigned i=0;i<sizeof buffer;i++)buffer[i]=0xa5;
    unsigned char *out=buffer+16;
    logs=reads=0;
    typedef int (*Marshal)(Message *,void *,uint32_t);
    typedef int (*Dispatch)(uint32_t,Message *,void *,uint32_t);
    int rc=dispatch?((Dispatch)(uintptr_t)0xaced81)(0x40f0,&m,out,sequence):
                    ((Marshal)(uintptr_t)0xab69c5)(&m,out,sequence);
    check(rc==(valid?0:4),"return status");
    check(reads==(supported?3u:0u),"parameter access count");
    check(valid?logs==0:logs>0,"error logging");
    for(unsigned i=0;i<sizeof buffer;i++)
        if(i<16||i>=30)check(buffer[i]==0xa5,"output bounds");
    check(out[1]==0xa5,"header byte 1 belongs to caller");
    if(!supported)for(unsigned i=0;i<14;i++)check(out[i]==0xa5,"unsupported message changed output");
    if(valid) {
        check(out[0]==5 && out[2]==0xf0 && out[3]==0x40,"wire header");
        for(unsigned i=0;i<4;i++)check(out[4+i]==((sequence>>(8*i))&255),"sequence little endian");
        check(out[8]==m.values[0]-0x4da && out[9]==m.values[1]-0x4dc,"switch encoding");
        for(unsigned i=0;i<4;i++)check(out[10+i]==((m.values[2]>>(8*i))&255),"pointer copied as uint32");
    }
    cases++;
}
void guest_main(void) {
    for(dispatch=0;dispatch<2;dispatch++) {
    const uint32_t ids[]={0x75e6,0x76ac};
    const uint32_t pointers[]={0,1,0x12345678,0x80000000,0xffffffff};
    for(unsigned id=0;id<2;id++)for(unsigned a=0;a<2;a++)for(unsigned b=0;b<2;b++)
        for(unsigned p=0;p<5;p++) {
            Message m={ids[id],7,{0x4da+a,0x4dc+b,pointers[p]}};
            exercise(m,0x89abcdef,1,1);
        }
    for(unsigned id=0;id<2;id++) {
        Message m={ids[id],7,{0x4db,0x4dd,0x12345678}};
        for(unsigned mask=0;mask<7;mask++) { m.present=mask;exercise(m,0,0,1); }
        m.present=7;
        const uint32_t invalid[]={0,0x4d9,0x4de,0xffffffff};
        for(unsigned i=0;i<4;i++) {
            m.values[0]=invalid[i];m.values[1]=0x4dc;exercise(m,1,0,1);
            m.values[0]=0x4da;m.values[1]=invalid[i];exercise(m,1,0,1);
        }
    }
    const uint32_t wrong[]={0,0x413c,0x75e5,0x75e7,0x76ab,0x76ad,0xffffffff};
    for(unsigned i=0;i<7;i++) {Message m={wrong[i],7,{0x4db,0x4dd,0}};exercise(m,0,0,0);}
    }
    check(cases==154,"coverage");
    put("QEMU_GAMMA_INTERFACE_PASSED 154 cases: direct and original 0x40f0 dispatch; packing, missing parameters, invalid enums, unrelated messages, buffer guards\n");
    put("POINTER_IS_COPIED_NOT_DEREFERENCED; NO_TABLE_FORMAT_OR_ISP_VALIDATION\n");
    finish();
}
