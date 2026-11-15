/* Stubs for the original JPEG and display handoff code. No image or device I/O. */
#include <stdint.h>

enum { BASE = 0x635c6000, DEST = 0x1789,
       SOURCE_TYPE = 0x2f5, DEST_TYPE = 0x14a, OPTIONS = 0x11223344, LENGTH = 0x98765 };
enum scenario { OK, NO_SLOT, NO_CHANNEL, BAD_RESOURCE, SEND_ERROR, ACK_ERROR, ACK_STATUS,
                COMPLETION_ERROR, COMPLETION_STATUS };
enum event { MARK, SCOPE, STAGE, SLOT, ALLOC, DESCRIBE, HOLD, PARAM, COPY, BYTE, INIT, OPEN,
             RESOURCE, TOKEN, TAG, CHANNEL, SEND, RECEIVE, CLOSE, LOG, PUBLISH, DROP, CLEANUP,
             VALID, SHARE, DISP_INIT, DISP_ENTRY, DISP_GEOMETRY, DISP_RELEASE,
             DISP_PREPARE, DISP_LOG, DISP_DONE,
             SOFT_INPUT, SOFT_OTHER, SOFT_ALLOC, SOFT_PARAM, SOFT_TRACE, SOFT_EVENT,
             SOFT_EXEC, SOFT_CONFIG_TRACE, SOFT_FREE };
static _Alignas(4) uint8_t ctx[0x6da0];
static void *scope, *channel;
static unsigned scenario, at, checks, receives, tokens;
static unsigned source, derived;
static unsigned soft_mode, source_type = SOURCE_TYPE;
static const uint8_t *expected;
static _Alignas(4) uint8_t share_source[40], share_dest[40];
static _Alignas(4) uint8_t display[0x400], disp_yc[48], disp_meta[16], disp_timing[16];
static void *disp_access;

static void print(const char *str)
{
    volatile unsigned *uart = (volatile unsigned *)0x09000000;
    for (; *str; ++str) {
        while (uart[6] & 32) {}
        uart[0] = (uint8_t)*str;
    }
}

static void number(unsigned n)
{
    char buf[11];
    unsigned pos = sizeof(buf) - 1;
    buf[pos] = 0;
    do { buf[--pos] = (char)('0' + n % 10); n /= 10; } while (n);
    print(buf + pos);
}

static void stop(void)
{
    register unsigned r0 __asm__("r0") = 0x18, r1 __asm__("r1") = 0x20026;
    __asm__ volatile("svc 0xab" : "+r"(r0), "+r"(r1) :: "memory");
    for (;;) {}
}

static void check(int condition, const char *msg)
{
    ++checks;
    if (!condition) {
        print("FAIL "); print(msg); print(" scenario="); number(scenario);
        print(" event="); number(at); print("\n"); stop();
    }
}

static void step(enum event e)
{
    check(expected[at] == (unsigned)e, "unexpected call order");
    ++at;
}

static uint16_t read16(const uint8_t *p) { return (uint16_t)(p[0] | (p[1] << 8)); }
static uint32_t read32(const uint8_t *p) { return read16(p) | ((uint32_t)read16(p + 2) << 16); }
static void write16(uint8_t *p, unsigned v) { p[0] = (uint8_t)v; p[1] = (uint8_t)(v >> 8); }
static void write32(uint8_t *p, uint32_t v)
{
    for (unsigned i = 0; i < 4; ++i) p[i] = (uint8_t)(v >> (i * 8));
}

void *get_context(void) { return ctx; }
#ifdef A7_KERNEL_CALLBACK_FIXTURE
extern char a7_jpeg_bridge[], a7_undef_test_site[];
extern unsigned a7_undef_test(void);
static unsigned callback_hits, exception_hits, self_test_hits;
unsigned a7_fixture_undef(unsigned pc, unsigned cpsr)
{
    check((cpsr & 0x3f) == 0x33, "exception is privileged Thumb");
    check(*(unsigned *)pc == 0xaa73f7f0, "complete UDF.W opcode");
    if (pc == (unsigned)a7_undef_test_site) { ++self_test_hits; return pc + 4; }
    check(pc == BASE + 0x34019c, "exception at JPEG-only marker call");
    ++exception_hits;
    return (unsigned)a7_jpeg_bridge & ~1u;
}
void a7_jpeg_record(unsigned context, unsigned stage)
{
    check(context == (unsigned)ctx && stage == 0x12a, "callback arguments");
    check(at == 0 && !soft_mode, "callback precedes JPEG stage events only");
    check(read16(ctx + 0x62f6) == source, "callback source handle");
    ++callback_hits;
    /* A real C callback may destroy these caller-saved registers and flags. */
    __asm__ volatile("movs r0,#0\nmovs r1,#0\nmovs r2,#0\nmovs r3,#0\nmov ip,r0"
                     ::: "r0","r1","r2","r3","r12","cc");
}
#endif
void mark_stage(void *c, unsigned n) { step(MARK); check(c == ctx && n == (soft_mode ? 0xe1u : 0x12au), "stage mark"); }
void scope_init(void *p) { step(SCOPE); scope = p; }
void enter_stage(void *c, unsigned n, unsigned zero)
{ step(STAGE); check(c == ctx && n == (soft_mode ? 0x17u : 8u) && zero == 0, "stage entry"); }
unsigned optional_trace(void) { return 0; }
unsigned get_slot(void *c, unsigned kind)
{ step(SLOT); check(c == ctx && kind == (soft_mode ? 0x17u : 14u), "resource slot");
  return scenario == (soft_mode ? 3u : NO_SLOT) ? 0xffffu : DEST; }

unsigned alloc_descriptor(void *p, unsigned type, unsigned flag, uint8_t *report)
{
    step(ALLOC);
    check(p == scope && type == 0xe0b00 && flag == 1, "StdYc descriptor resource");
    write32(report + 4, 0xd5d50000 | derived);
    write32(report + 0x10, 0x04102030);
    write32(report + 0x14, 0x71890123);
    return 0;
}

void describe_input(unsigned word0, unsigned word1, unsigned type, unsigned handle,
                    unsigned zero, void *field, unsigned a, unsigned opts)
{
    step(DESCRIBE);
    check(word0 == 0x04102030 && word1 == 0x71890123, "allocated descriptor metadata");
    check(type == source_type && handle == source && zero == 0, "source comes from context");
    check(field == ctx + 0x6752 && opts == OPTIONS && a == 0, "descriptor inputs");
}

unsigned hold_descriptor(void *p, unsigned handle)
{ step(HOLD); check(p == scope && handle == derived, "hold allocated descriptor"); return 0; }
unsigned get_param(void *c) { step(PARAM); check(c == ctx, "parameter context"); return 0x654321; }
void copy_word(uint8_t *dest, const uint8_t *src, unsigned size)
{
    step(COPY);
    check(src == ctx + 0x675e && size == 4, "copy geometry bytes");
    for (unsigned i = 0; i < 4; ++i) dest[i] = src[i];
}
unsigned get_byte(unsigned opts) { step(BYTE); check(opts == OPTIONS, "encode options"); return 0x2a; }
void channel_init(void *p, unsigned a, unsigned b)
{ step(INIT); check(a == 2 && b == 5, "channel constructor"); channel = p; }
unsigned channel_available(void *p)
{ step(OPEN); check(p == channel, "channel availability"); return scenario != NO_CHANNEL; }
unsigned resource(unsigned type, unsigned opts, void *field)
{
    step(RESOURCE);
    check(type == 6 && opts == 0x88 && field == ctx + 0x6d78, "channel lookup");
    return scenario == BAD_RESOURCE ? 0xffu : 0x34u;
}
unsigned channel_token(void *p)
{ step(TOKEN); check(p == channel, "channel token"); return 0x1920 + ++tokens; }
unsigned channel_tag(unsigned slot)
{ step(TAG); check(slot == 0x34, "resolved channel slot"); return 0x20304050; }
unsigned channel_id(void *p)
{ step(CHANNEL); check(p == channel, "channel identifier"); return 0x222; }

int send_request(unsigned endpoint, const uint8_t *msg, unsigned size, unsigned id)
{
    step(SEND);
    check(endpoint == 0x560013 && size == 0x54 && id == 0x222, "request envelope");
    check(read16(msg) == 0x2000 && read16(msg + 2) == 6 && read16(msg + 4) == size, "request header");
    check(read16(msg + 0x1c) == derived && read16(msg + 0x1c) != source, "encoder receives derived handle");
    check(read32(msg + 0x24) == DEST_TYPE && read16(msg + 0x28) == DEST, "output resource");
    check(read32(msg + 0x40) == 0xe3e2e1e0 && read32(msg + 0x44) == 0xe3e2e1e0, "packed geometry bytes");
    check(msg[0x49] == 3 && msg[0x4a] == 0x2a && msg[0x4b] == 0, "packed mode bytes");
    return scenario == SEND_ERROR ? -3 : 0;
}

int receive_reply(unsigned endpoint, uint8_t *reply, unsigned size, unsigned id, int wait)
{
    step(RECEIVE);
    check(endpoint == 0x560013 && size == 0x10 && id == 0x222 && wait == -1, "reply envelope");
    for (unsigned i = 0; i < 16; ++i) reply[i] = 0;
    if (++receives == 1) {
        write32(reply + 8, scenario == ACK_STATUS ? 9 : 0);
        write32(reply + 12, 0xaf12); /* ACK output must not be published. */
        return scenario == ACK_ERROR ? -5 : 0;
    }
    check(receives == 2, "one ACK and one completion");
    write32(reply + 8, scenario == COMPLETION_STATUS ? 9 : 0);
    write32(reply + 12, LENGTH);
    return scenario == COMPLETION_ERROR ? -7 : 0;
}

void channel_close(void *p) { step(CLOSE); check(p == channel, "channel cleanup"); }
void native_log(unsigned fmt)
{
    step(LOG);
    if (soft_mode) return; /* Original literal pools retained; no log strings read. */
    check(fmt == BASE + 0x94e308 || fmt == BASE + 0x94e2b3 ||
          fmt == BASE + 0x94d10f || fmt == BASE + 0x94d137 ||
          fmt == BASE + 0x94d170 || fmt == BASE + 0x960230 ||
          fmt == BASE + 0x96025c, "expected original failure log");
}
void publish(void *field, unsigned mode, unsigned out_handle, unsigned zero,
             unsigned type, unsigned length)
{
    step(PUBLISH);
    check(field == ctx + 0x63c4 && mode == 0x5b && out_handle == DEST, "publication destination");
    check(zero == 0 && type == DEST_TYPE && length == LENGTH, "publication after completion");
}
void drop_descriptor(void *p, unsigned handle)
{ step(DROP); check(p == scope && handle == derived, "release derived descriptor"); }
void scope_close(void *p) { step(CLEANUP); check(p == scope, "stage cleanup"); }

int valid_handle(const uint8_t *p)
{
    step(VALID);
    check(p == share_source, "test original shared image reference");
    return read16(p) != 0xffff;
}

int alloc_share(unsigned type, unsigned handle, unsigned option, uint8_t *report, unsigned domain)
{
    step(SHARE);
    check(type == 0x193 && handle == read16(share_source) && option == 0 && domain == 5,
          "request sharing of existing handle with its original type");
    if (scenario == 2) return -17;
    write32(report + 4, 0xa1a10000 | derived);
    report[8] = scenario == 3 ? 7 : 1;
    for (unsigned i = 0; i < 32; ++i) report[0x10 + i] = (uint8_t)(i ^ 0x7b);
    return 0;
}

static unsigned test_share(void)
{
    static const uint8_t order[][5] = {
        {VALID,SHARE,255}, {VALID,LOG,255}, {VALID,SHARE,255}, {VALID,SHARE,LOG,255}
    };
    for (scenario = 0; scenario < sizeof(order) / sizeof(order[0]); ++scenario) {
        source = 0x279a;
        derived = 0x67d0;
        write32(share_source, scenario == 1 ? 0xffff : source);
        write32(share_source + 4, 0x193);
        for (unsigned i = 0; i < sizeof(share_dest); ++i) share_dest[i] = 0xba;
        at = 0;
        expected = order[scenario];
        int (*share)(void *, const void *, unsigned, unsigned) =
            (int (*)(void *, const void *, unsigned, unsigned))(BASE + 0x3a5869);
        const int codes[] = {0, -6, -17, 0};
        check(share(share_dest, share_source, 0, 5) == codes[scenario], "share status");
        check(expected[at] == 255, "full share sequence");
        if (codes[scenario]) {
            for (unsigned i = 0; i < sizeof(share_dest); ++i)
                check(share_dest[i] == 0xba, "no descriptor mutation on failure");
        } else {
            unsigned extents = scenario == 3 ? 4 : 1;
            check(read16(share_dest) == derived && share_dest[2] == extents && share_dest[3] == 1 &&
                  read32(share_dest + 4) == 0x193, "shared descriptor header");
            for (unsigned i = 0; i < 32; ++i)
                check(share_dest[8 + i] == (i < 8 * extents ? (i ^ 0x7b) : 0xba),
                      "copy only accepted extents");
        }
    }
    return scenario;
}

enum { SA_IN = 0x1327, SA_OUT = 0x5b84, RC = 0x1772, YC = 0x52a9, DISPLAY_UNIT = 0x413ae };

void *display_access_init(void *access, unsigned handle)
{
    step(DISP_INIT); check(handle == DISPLAY_UNIT, "display descriptor container");
    disp_access = access;
    return access;
}

void *display_entry(void *access, unsigned index)
{
    step(DISP_ENTRY); check(access == disp_access && index < 3, "display descriptor index");
    return index == 0 ? disp_yc : index == 1 ? disp_meta : disp_timing;
}

void display_geometry(unsigned mode, unsigned x, unsigned y, unsigned width,
                      unsigned height, void *width_out, void *height_out)
{
    step(DISP_GEOMETRY);
    check(mode == 2 && x == 1920 && y == 1080 && width == 1792 && height == 1008 &&
          width_out == disp_yc + 0x18 && height_out == disp_yc + 0x1a,
          "geometry helper updates descriptor fields");
    write16(width_out, 1616);
    write16(height_out, 912);
}

int display_release(void *entry, int arg1, int arg2)
{
    step(DISP_RELEASE); check(arg1 == -1 && arg2 == -1, "display release mode");
    unsigned expected_offset = expected[at] == DISP_RELEASE ? 0xc4 : scenario ? 0x294 : 0x114;
    check(entry == display + expected_offset, "only unselected source and RC released");
    return 0;
}

int display_prepare(void *entry)
{
    step(DISP_PREPARE);
    check(entry == display + (scenario ? 0x114 : 0x294), "selected input/output prepared");
    return 0;
}

void display_log(unsigned msg)
{
    static const unsigned offsets[] = {0x9ace03, 0x9acdee, 0x9acd52, 0x9acd7b, 0x9acda1, 0x9acdc7};
    step(DISP_LOG); check(msg == BASE + offsets[scenario], "display branch log");
}

void display_access_done(void *access)
{
    step(DISP_DONE); check(access == disp_access, "display accessor cleanup");
}

void display_exception(void) { check(0, "unexpected display exception"); }

static unsigned test_display(void)
{
    static const uint8_t ok[] = {
        DISP_INIT,DISP_ENTRY,DISP_GEOMETRY,DISP_ENTRY,DISP_ENTRY,DISP_RELEASE,DISP_RELEASE,
        DISP_PREPARE,DISP_LOG,DISP_DONE,255
    };
    static const uint8_t invalid[] = {DISP_LOG,255};
    static const unsigned offsets[] = {0x298,0x118,0x7c,0xc8};
    int (*select_yc)(void *) = (int (*)(void *))(BASE + 0x4e88a1);
    for (scenario = 0; scenario < 6; ++scenario) {
        for (unsigned i = 0; i < sizeof(display); ++i) display[i] = 0;
        for (unsigned i = 0; i < sizeof(disp_yc); ++i) disp_yc[i] = 0xa5;
        for (unsigned i = 0; i < sizeof(disp_meta); ++i) disp_meta[i] = disp_timing[i] = 0xa5;
        write16(display + 0x298, SA_OUT);
        write16(display + 0x118, SA_IN);
        write16(display + 0x7c, YC);
        write16(display + 0xc8, RC);
        write16(display + 0x2c, 1920);
        write16(display + 0x2e, 1080);
        write32(display + 0x84, DISPLAY_UNIT);
        write16(disp_yc + 0x18, 1792);
        write16(disp_yc + 0x1a, 1008);
        display[0x110] = 2;
        display[0x3f5] = (uint8_t)scenario;
        if (scenario >= 2) write16(display + offsets[scenario - 2], 0xffff);
        at = 0;
        expected = scenario < 2 ? ok : invalid;
        check(select_yc(display) == (scenario < 2 ? 0 : 8), "display selection result");
        check(expected[at] == 255, "display event sequence complete");
        if (scenario >= 2) {
            check(read16(disp_yc + 8) == 0xa5a5 && read32(disp_timing + 8) == 0xa5a5a5a5 &&
                  disp_meta[5] == 0xa5, "invalid request does not publish descriptor");
            for (unsigned i = 0; i < 4; ++i) {
                static const unsigned handles[] = {SA_OUT,SA_IN,YC,RC};
                check(read16(display + offsets[i]) == (i == scenario - 2 ? 0xffff : handles[i]),
                      "invalid request keeps references intact");
            }
            continue;
        }
        check(read32(disp_yc + 4) == 0x273 && read16(disp_yc + 8) == (scenario ? SA_IN : SA_OUT),
              "published metadata references selected existing YUV handle");
        check(read16(disp_yc + 0x20) == 1616 && read16(disp_yc + 0x22) == 912 &&
              read16(disp_yc + 0x28) == 1616 && read16(disp_yc + 0x2a) == 912,
              "descriptor uses geometry helper result");
        check(disp_meta[5] == 6 && read32(disp_timing + 8) == UINT32_MAX, "side metadata");
        check(read16(display + 0xc8) == 0xffff && read16(display + 0x118) == 0xffff &&
              read16(display + 0x298) == 0xffff && read16(display + 0x7c) == YC,
              "RC retired and source slots cleared after transfer");
    }
    return scenario;
}

/* Original SoftFocus stage and original context switch, with its processing
 * service replaced. This proves handle flow, NOT native pixel access. */
enum { SOFT_SOURCE=0x1379, SOFT_DEST=0x2468, SOFT_WORK=0x3579,
       SOFT_CONFIG=0x468a, SOFT_TYPE=0x52f };
unsigned soft_input(void *c, unsigned kind)
{ step(SOFT_INPUT); check(c==ctx && kind==1,"soft input query"); return scenario==1 ? 0xffff : SOFT_SOURCE; }
unsigned soft_other(void *c)
{ step(SOFT_OTHER); check(c==ctx,"soft second query"); return scenario==2 ? 0xffff : SOFT_DEST; }
int soft_alloc(uint8_t *selector,uint16_t *handle)
{ step(SOFT_ALLOC); *selector=0x31; *handle=SOFT_CONFIG; return scenario==4 ? 6 : 0; }
int soft_params(unsigned handle,void *p)
{ step(SOFT_PARAM); check(handle==SOFT_CONFIG && p==ctx+0x20,"soft config binding"); return scenario==5 ? 2 : 0; }
void soft_trace(unsigned event,unsigned handle,void *geometry,unsigned flag,unsigned zero)
{
    step(SOFT_TRACE);
    check((event==0x3b && handle==SOFT_SOURCE)||(event==0x3c && handle==SOFT_DEST),"soft source/destination trace");
    check(geometry==ctx+0x6752 && flag==7 && zero==0,"soft trace geometry");
}
void soft_event(unsigned category,unsigned event,unsigned zero0,unsigned zero1)
{ step(SOFT_EVENT); check(category==4 && (event==0x4011||event==0x4012) && !zero0&&!zero1,"soft processing events"); }
int soft_execute(unsigned selector,unsigned config,const uint8_t *input,uint32_t *out,uint8_t *done)
{
    step(SOFT_EXEC);
    check(selector==0x31 && config==SOFT_CONFIG,"soft dispatch identity");
    check(read16(input)==SOFT_SOURCE && read16(input+2)==SOFT_DEST && read16(input+4)==SOFT_WORK,"soft three resource handles");
    check(read32(input+8)==6000 && read32(input+12)==4000 && read32(input+16)==6016,"soft geometry arguments");
    for(unsigned i=0;i<4;i++)out[i]=0;
    *done=scenario==7 ? 0 : 1;
    return scenario==6 ? 1 : 0;
}
void soft_config_trace(unsigned event,unsigned config,unsigned flag)
{ step(SOFT_CONFIG_TRACE); check(event==0x3d && config==SOFT_CONFIG && flag==7,"soft config trace"); }
int soft_free(unsigned selector,unsigned config,const uint8_t *input)
{
    step(SOFT_FREE);
    check(selector==0x31 && config==SOFT_CONFIG && read16(input)==SOFT_SOURCE &&
          read16(input+2)==SOFT_DEST && read16(input+4)==SOFT_WORK,"soft resource cleanup");
    return scenario==8 ? 6 : 0;
}

static unsigned test_softfocus(void)
{
    #define SOFT_HEAD MARK,SCOPE,SOFT_INPUT
    #define SOFT_PREP SOFT_HEAD,SOFT_OTHER,SLOT,SOFT_ALLOC,SOFT_PARAM,SOFT_TRACE,SOFT_EVENT,SOFT_EXEC
    #define SOFT_DONE SOFT_PREP,SOFT_EVENT,SOFT_TRACE,SOFT_CONFIG_TRACE
    static const uint8_t order[][30]={
        {SOFT_DONE,SOFT_FREE,STAGE,CLEANUP,255},
        {SOFT_HEAD,CLEANUP,255},
        {SOFT_HEAD,SOFT_OTHER,CLEANUP,255},
        {SOFT_HEAD,SOFT_OTHER,SLOT,CLEANUP,255},
        {SOFT_HEAD,SOFT_OTHER,SLOT,SOFT_ALLOC,LOG,CLEANUP,255},
        {SOFT_HEAD,SOFT_OTHER,SLOT,SOFT_ALLOC,SOFT_PARAM,LOG,CLEANUP,255},
        {SOFT_PREP,LOG,CLEANUP,255},
        {SOFT_DONE,LOG,LOG,LOG,LOG,LOG,CLEANUP,255},
        {SOFT_DONE,SOFT_FREE,LOG,STAGE,CLEANUP,255},
    };
    static const uint8_t jpeg_order[]={
        MARK,SCOPE,STAGE,SLOT,ALLOC,DESCRIBE,HOLD,PARAM,COPY,COPY,BYTE,INIT,OPEN,
        RESOURCE,TOKEN,TOKEN,TAG,CHANNEL,SEND,RECEIVE,RECEIVE,CLOSE,PUBLISH,DROP,CLEANUP,255
    };
    unsigned cases=0;
    for(unsigned test=0;test<9;test++) {
        scenario=test; soft_mode=1;
        for(unsigned n=0;n<sizeof ctx;n++)ctx[n]=0;
        write32(ctx+0x34,OPTIONS);write32(ctx+0x200,0x15);
        write16(ctx+0x62f6,SOFT_SOURCE);write16(ctx+0x62f8,SOFT_DEST);
        write16(ctx+0x6316,SOFT_WORK);write16(ctx+0x6304,DEST);
        write32(ctx+0x6704,SOURCE_TYPE);write32(ctx+0x6708,SOFT_TYPE);
        write32(ctx+0x6710,DEST_TYPE);write16(ctx+0x6752,6016);
        write16(ctx+0x6756,6000);write16(ctx+0x6758,4000);
        write32(ctx+0x675e,0xe3e2e1e0);write32(ctx+0x6d74,0x88);
        ctx[0x6d98]=0x5b;ctx[0x6d99]=7;
        expected=order[test];at=0;
        unsigned (*stage)(void)=(unsigned (*)(void))(BASE+0x34f5ed);
        const unsigned codes[]={0,2,2,2,2,5,5,5,0};
        check(stage()==codes[test],"soft stage result");
        check(expected[at]==255,"full soft stage sequence");
        const unsigned swapped=test==0||test==8;
        check(read16(ctx+0x62f6)==(swapped?SOFT_DEST:SOFT_SOURCE) &&
              read16(ctx+0x62f8)==(swapped?SOFT_SOURCE:SOFT_DEST),"only completed processing swaps image handles");
        check(read32(ctx+0x6704)==(swapped?SOFT_TYPE:SOURCE_TYPE) &&
              read32(ctx+0x6708)==(swapped?SOURCE_TYPE:SOFT_TYPE),"resource types follow swapped handles");
        ++cases;
        if(swapped) {
            /* Execute original JPEG stage immediately using the same context.
             * describe_input asserts the new source and type reach the request. */
            soft_mode=0;scenario=OK;source=SOFT_DEST;source_type=SOFT_TYPE;derived=0x59a3;
            at=receives=tokens=0;expected=jpeg_order;
            stage=(unsigned (*)(void))(BASE+0x34018d);
            check(stage()==0,"post-processing JPEG handoff");
            check(expected[at]==255,"JPEG uses completed output");++cases;
        }
    }
    soft_mode=0;source_type=SOURCE_TYPE;
    return cases;
}

void guest_main(void)
{
    #define HEAD MARK,SCOPE,STAGE,SLOT
    #define PREP HEAD,ALLOC,DESCRIBE,HOLD,PARAM,COPY,COPY,BYTE,INIT,OPEN
    #define START PREP,RESOURCE,TOKEN,TOKEN,TAG,CHANNEL,SEND
    #define FAIL CLOSE,LOG,CLEANUP,255
    static const uint8_t order[][32] = {
        {START,RECEIVE,RECEIVE,CLOSE,PUBLISH,DROP,CLEANUP,255},
        {HEAD,CLEANUP,255}, {PREP,FAIL}, {PREP,RESOURCE,LOG,FAIL},
        {START,LOG,FAIL}, {START,RECEIVE,FAIL}, {START,RECEIVE,LOG,FAIL},
        {START,RECEIVE,RECEIVE,FAIL}, {START,RECEIVE,RECEIVE,LOG,FAIL}
    };
    unsigned cases = 0;
    checks = 0;
#ifdef A7_KERNEL_CALLBACK_FIXTURE
    check(a7_undef_test() == 0x7a73 && self_test_hits == 1, "private Thumb trap self-test");
#endif
    for (unsigned i = 0; i < 3; ++i) {
        source = 0x2147 + 0x5a40 * i;
        derived = 0x59a3 + 0x3410 * i;
        for (scenario = 0; scenario < sizeof(order) / sizeof(order[0]); ++scenario) {
            for (unsigned n = 0; n < sizeof(ctx); ++n) ctx[n] = 0;
            write32(ctx + 0x34, OPTIONS);
            write32(ctx + 0x200, 0x15);
            write32(ctx + 0x62f6, 0xd1d10000 | source);
            write32(ctx + 0x6304, 0xe2e20000 | DEST);
            write32(ctx + 0x6704, SOURCE_TYPE);
            write32(ctx + 0x6710, DEST_TYPE);
            write32(ctx + 0x675e, 0xe3e2e1e0);
            write32(ctx + 0x6d74, 0x88);
            ctx[0x6d98] = 0x5b;
            at = receives = tokens = 0;
            expected = order[scenario];
            unsigned (*stage)(void) = (unsigned (*)(void))(BASE + 0x34018d);
            /* The optional notification recipient is absent; in that case the
               success return is zero for the provided fixture. */
            check(stage() == (scenario == OK ? 0u : 2u), "stage status");
            check(expected[at] == 255, "full expected sequence");
            ++cases;
        }
    }
    cases += test_share();
    cases += test_display();
    cases += test_softfocus();
#ifdef A7_KERNEL_CALLBACK_FIXTURE
    check(callback_hits >= 27 && callback_hits == exception_hits, "one callback per JPEG stage");
    print("KERNEL_CALLBACK_HITS "); number(callback_hits); print("\n");
#endif
    print("JPEG_STAGE_FIXTURE_CASES "); number(cases); print(" CHECKS "); number(checks);
    print("\nJPEG_STAGE_FIXTURE_PASSED\n"); stop();
}
