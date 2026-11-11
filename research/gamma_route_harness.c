/* Offline, fixture-connected native blocks. No queue, ISP, camera or JPEG. */
#include <stdint.h>
#define BASE 0x635c6000u
#define GOT (BASE+0x118d8b4u)
#define STATE (BASE+0x1039774u)
#define CACHE (BASE+0x10ce7d0u)
static unsigned routes, sends, mode_calls, copy_calls;
static unsigned mode_result;
static void put(const char *s) {
    volatile unsigned *u=(volatile unsigned *)0x09000000;
    while (*s) { while (u[6]&32) {} u[0]=*s++; }
}
static void finish(void) {
    register unsigned r0 __asm__("r0")=0x18;
    register unsigned r1 __asm__("r1")=0x20026;
    __asm__ volatile("svc 0xab" : "+r"(r0), "+r"(r1) : : "memory");
    for (;;) {}
}
static void check(int ok,const char *s) {
    if (!ok) { put("FAIL "); put(s); put("\n"); finish(); }
}
static void fill(void *p,unsigned n,unsigned v) {
    unsigned char *q=p;
    for (unsigned i=0;i<n;i++) q[i]=v;
}
void *memset(void *p,int v,unsigned n) { fill(p,n,(unsigned char)v); return p; }
static void copy(void *dst,const void *src,unsigned n) {
    unsigned char *d=dst; const unsigned char *s=src;
    for (unsigned i=0;i<n;i++) d[i]=s[i];
}
static int equal(const void *a,const void *b,unsigned n) {
    const unsigned char *x=a,*y=b;
    for (unsigned i=0;i<n;i++) if (x[i]!=y[i]) return 0;
    return 1;
}
static void set32(void *p,uint32_t v) {
    unsigned char *b=p;
    for (unsigned i=0;i<4;i++) b[i]=v>>(8*i);
}
void *native_copy(void *dst,const void *src,unsigned n) {
    check(n==12,"report copy length"); copy_calls++; copy(dst,src,n); return dst;
}
void native_log(void) { check(0,"logging should be disabled"); }
unsigned native_mode(void) { mode_calls++; return mode_result; }
extern void route_bridge(void *,void *);
extern void route_descriptor(void *,void *);
extern void route_forward(void *,void *,void *);

static void report_test(unsigned char *frame,uint32_t pointer) {
    /* The native header initializer has not been traced. Preserve a distinct
     * eight-byte fixture header; do not claim it is a valid hardware message. */
    unsigned char *cache=(unsigned char *)CACHE;
    for (unsigned i=0;i<8;i++) cache[i]=0x61+i;
    set32(cache+8,pointer^0xffffffffu);
    unsigned char expected[12], output[32];
    copy(expected,cache,8); set32(expected+8,pointer);
    uintptr_t context[16]={0}; context[0x38/4]=(uintptr_t)frame;
    typedef unsigned (*Report)(void *,void *,unsigned);
    Report report=(Report)(uintptr_t)(BASE+0x6158bd);
    /* Changed, unchanged, forced-even-unchanged. */
    for (unsigned pass=0;pass<3;pass++) {
        unsigned emitted=pass!=1, force=pass==2;
        fill(output,sizeof output,0xa5); copy_calls=0;
        unsigned rc=report(context,output+8,force);
        check(rc==(emitted?12u:0u),"report changed/unchanged/forced return");
        check(copy_calls==emitted,"report copy count");
        for (unsigned i=0;i<sizeof output;i++) {
            unsigned value=emitted && i>=8 && i<20?expected[i-8]:0xa5;
            check(output[i]==value,"report bytes and destination guards");
        }
        check(equal(cache,expected,12),"report cache and header preserved");
        sends++;
    }
}

static void routes_test(void) {
    static uint32_t raw[0x300/4], params[0x710/4], expected[0x710/4];
    static uint32_t aggregate[0xb40/4], aggregate_expected[0xb40/4];
    static uint32_t frame[0x750/4], frame_expected[0x750/4];
    static uint32_t diag[0x920/4], diag_expected[0x920/4];
    static unsigned char overrides[3], debug[64];
    /* Deliberately opaque values. No test passes these to a curve reader. */
    static uint32_t override_table[]={0,0x01020304,0xfedcba98};
    const uint32_t pointers[]={0,1,0x12345678,0x80000000,0xffffffff};
    uintptr_t context[1]={STATE};
    *(volatile uintptr_t *)(GOT+0xa640)=(uintptr_t)&overrides[0];
    *(volatile uintptr_t *)(GOT+0xaa3c)=(uintptr_t)&overrides[1];
    *(volatile uintptr_t *)(GOT+0x9d44)=(uintptr_t)&overrides[2];
    *(volatile uintptr_t *)(GOT+0x9f3c)=(uintptr_t)override_table;
    *(volatile uintptr_t *)(GOT+0x49f8)=(uintptr_t)debug;
    fill(debug,sizeof debug,0);
    /* Full input-byte range with complementary force values, plus all four
     * valid 0/1 switch combinations. Cross both source override states, five
     * pointer patterns and six debug branches: 15,600 routes in total. */
    for (unsigned sample=0;sample<260;sample++)
    for (unsigned source=0;source<2;source++)
    for (unsigned p=0;p<5;p++)
    for (unsigned scenario=0;scenario<6;scenario++) {
        unsigned flag=sample<256?sample:(sample-256)/2;
        unsigned force=sample<256?255-sample:(sample-256)%2;
        fill(raw,sizeof raw,0x5a);
        raw[0x27c/4]=source;
        ((unsigned char *)raw)[0xec]=7;
        copy((void *)STATE,raw,sizeof raw);
        unsigned char wire[14]={5,0,0xf0,0x40,0,0,0,0,0,0,0,0,0,0};
        wire[8]=flag; wire[9]=force; set32(wire+10,pointers[p]);
        unsigned rc=((unsigned (*)(const void *))(uintptr_t)(BASE+0x61b235))(wire);
        check(rc==1,"original receiver return");
        raw[0x2bc/4]=flag; raw[0x2c0/4]=force; raw[0x2c4/4]=pointers[p];
        check(equal((void *)STATE,raw,sizeof raw),"receiver complete state guards");
        overrides[0]=scenario==1?1:scenario==2?2:0;
        overrides[1]=scenario==1?1:scenario==2?2:0;
        overrides[2]=scenario>=3?(scenario==5?2:1):0;
        mode_result=scenario==4; mode_calls=0;
        uint32_t ptr=overrides[2] && !mode_result?override_table[overrides[2]]:pointers[p];
        unsigned want_enable=overrides[1]?overrides[1]:flag;
        unsigned want_effect=overrides[0]?overrides[0]:force;
        fill(params,sizeof params,0xa5); copy(expected,params,sizeof params);
        expected[0x6e0/4]=want_enable;
        expected[0x6e4/4]=source==1?0:want_enable;
        expected[0x6e8/4]=want_effect; expected[0x6ec/4]=ptr;
        unsigned char *e=(unsigned char *)expected;
        e[0x6dc]=(want_enable==1 && ptr!=0);
        e[0x6dd]=(source!=1 && want_enable==1 && ptr!=0);
        e[0x642]=7; e[0x641]=want_effect==1?0:7;
        route_bridge(context,params);
        check(mode_calls==(overrides[2]!=0),"debug mode branch count");
        check(equal(params,expected,sizeof params),"native bridge values and write guards");
        check(equal((void *)STATE,raw,sizeof raw),"bridge source unchanged");

        /* Input fields normally produced by other native functions remain
         * fixtures here. Only the external pointer is connected from receiver. */
        unsigned char *s=(unsigned char *)params;
        s[0x639]=3; s[0x636]=1; s[0x6c8]=0x34; s[0x6c9]=0x12;
        s[0x637]=5; s[0x6da]=1;
        copy(expected,params,sizeof params);
        fill(aggregate,sizeof aggregate,0xa5);
        copy(aggregate_expected,aggregate,sizeof aggregate);
        unsigned char *a=(unsigned char *)aggregate_expected+0xb18;
        a[0]=3; a[1]=1; a[2]=0x34; a[3]=0x12; a[4]=5; a[12]=1;
        set32(a+8,ptr);
        route_descriptor(params,(unsigned char *)aggregate+0xb18);
        check(equal(aggregate,aggregate_expected,sizeof aggregate),"descriptor values and write guards");
        check(equal(params,expected,sizeof params),"descriptor input unchanged");

        fill(frame,sizeof frame,0xa5); copy(frame_expected,frame,sizeof frame);
        fill(diag,sizeof diag,0xa5); copy(diag_expected,diag,sizeof diag);
        frame_expected[0x730/4]=ptr; diag_expected[0x904/4]=ptr;
        unsigned char *d=(unsigned char *)diag_expected;
        d[0x8fe]=0x57; d[0x8ff]=0x13;
        route_forward(aggregate,frame,diag);
        check(equal(frame,frame_expected,sizeof frame),"forward frame values and write guards");
        check(equal(diag,diag_expected,sizeof diag),"forward diagnostic values and write guards");
        check(equal(aggregate,aggregate_expected,sizeof aggregate),"forward source unchanged");
        report_test((unsigned char *)frame,ptr);
        check(equal(frame,frame_expected,sizeof frame),"report input unchanged");
        routes++;
    }
}
void guest_main(void) {
    routes_test();
    check(routes==15600 && sends==46800,"coverage totals");
    put("QEMU_GAMMA_ROUTE_PASSED: 15600 fixture-connected routes; 46800 report cases\n");
    put("ORIGINAL_RECEIVER_AND_BLOCKS; FLAG_GATES; OVERRIDES; POINTER_BYTES; WRITE_GUARDS\n");
    put("REPORT_HEADER_IS_FIXTURE; NO_TABLE_READ; NO_QUEUE_ISP_JPEG_OR_CAMERA_VALIDATION\n");
    finish();
}
