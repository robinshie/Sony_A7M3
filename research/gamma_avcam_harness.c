/* Offline component experiment. Never a camera payload or ISP emulator. */
#include <stdint.h>
#define BASE 0x635c6000u
static unsigned logs, receivers, samples;
static uint32_t log_values[3];
static void put(const char *s) {
    volatile unsigned *uart=(volatile unsigned *)0x09000000;
    while (*s) { while (uart[6]&32) {} uart[0]=*s++; }
}
static void finish(void) {
    register unsigned r0 __asm__("r0")=0x18;
    register unsigned r1 __asm__("r1")=0x20026;
    __asm__ volatile("svc 0xab" : "+r"(r0), "+r"(r1) : : "memory");
    while (1) {}
}
static void check(int ok,const char *s) {
    if (!ok) { put("FAIL "); put(s); put("\n"); finish(); }
}
void divide_zero(void) { check(0,"unexpected division by zero"); }
void native_log(const char *format,uint32_t a,uint32_t b,uint32_t c) {
    (void)format; logs++; log_values[0]=a; log_values[1]=b; log_values[2]=c;
}
static void receiver_test(void) {
    static unsigned char debug[64];
    volatile uint32_t *state=(volatile uint32_t *)(BASE+0x1039774);
    *(volatile uintptr_t *)(BASE+0x118d8b4+0x49f8)=(uintptr_t)debug;
    const uint32_t pointers[]={0,1,0x12345678,0x80000000,0xffffffff};
    for (unsigned logging=0;logging<2;logging++)
    for (unsigned flag=0;flag<256;flag++)
    for (unsigned p=0;p<5;p++) {
        unsigned char wire[14];
        for (unsigned i=0;i<14;i++) wire[i]=0xa5;
        wire[0]=5; wire[2]=0xf0; wire[3]=0x40;
        wire[8]=flag; wire[9]=255-flag;
        for (unsigned i=0;i<4;i++) wire[10+i]=pointers[p]>>(i*8);
        for (unsigned i=0;i<0x300/4;i++) state[i]=0xdeadbeef;
        debug[0x32]=logging; logs=0;
        int rc=((int (*)(const void *))(uintptr_t)(BASE+0x61b235))(wire);
        check(rc==1,"receiver return");
        for (unsigned i=0;i<0x300/4;i++) {
            uint32_t expected=i==0x2bc/4?flag:i==0x2c0/4?255-flag:
                              i==0x2c4/4?pointers[p]:0xdeadbeef;
            check(state[i]==expected,"receiver values and write bounds");
        }
        check(logs==logging,"receiver logging branch");
        if (logging) check(log_values[0]==flag && log_values[1]==255-flag &&
                           log_values[2]==pointers[p],"receiver log arguments");
        receivers++;
    }
}
static void sampler_test(void) {
    static uint16_t table[1025],input[96];
    static uint32_t output[98];
    const uint16_t *native_identity=(const uint16_t *)(BASE+0x8b5f52);
    const uint16_t modes[]={0,1,2,65535};
    const uint16_t *candidate=(const uint16_t *)0x40300000;
    for (unsigned curve=0;curve<4;curve++) {
        for (unsigned i=0;i<1025;i++) {
            uint32_t x=i==1024?65535:i*64;
            table[i]=curve==0?native_identity[i]:curve==1?(uint32_t)(((uint64_t)x*x)/65535):
                     curve==2?43210:candidate[i];
        }
        for (unsigned m=0;m<4;m++)
        for (unsigned start=0;start<65536;start+=96) {
            for (unsigned j=0;j<96;j++) input[j]=start+j>65535?65535:start+j;
            for (unsigned j=0;j<98;j++) output[j]=0xdeadbeef;
            ((void (*)(const uint16_t *,uint32_t *,const uint16_t *,const uint16_t *))
             (uintptr_t)(BASE+0x7f8aaf))(&modes[m],output+1,input,table);
            check(output[0]==0xdeadbeef && output[97]==0xdeadbeef,"sampler output bounds");
            for (unsigned j=0;j<96;j++) {
                unsigned x=input[j],i=x>>6;
                unsigned value=table[i]+(((x&63)*(table[i+1]-table[i])+32)/64);
                unsigned expected=modes[m]==1?value:(value+32)/64;
                if (modes[m]!=1 && expected>1023) expected=1023;
                check(output[j+1]==expected,"native interpolation and quantization");
                samples++;
            }
        }
    }
}
void guest_main(void) {
    receiver_test(); sampler_test();
    check(receivers==2560 && samples==1049088,"coverage");
    put("QEMU_AVCAM_GAMMA_PASSED: 2560 receiver cases; 1049088 sample comparisons\n");
    put("ALL_UINT16_INPUTS; 4_MODES; 4_CURVES_INCLUDING_FL_TONE; ORIGINAL_DIVISION; WRITE_GUARDS\n");
    put("RECEIVER_TO_SAMPLER_UNPROVEN; NO_ISP_OR_JPEG_VALIDATION; NOT_FLASH_READY\n");
    finish();
}
