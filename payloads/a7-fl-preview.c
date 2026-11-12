#include "a7-fl-preview.h"
#include "a7-fl-preview-pins.h"
static struct a7_fl_preview_report report;
const struct a7_fl_preview_report *a7_fl_preview_status(void) {return &report;}
struct native_api {
    void *(*allocate)(unsigned);
    void *(*parameter)(void *,int);
    void *(*list)(void *,unsigned);
    void (*add)(void *,unsigned,void *);
    void (*request)(const char *,unsigned,void *);
    void (*release)(void *);
};
static int finish(int result) {report.last_result=result;return result;}
static int active(const struct a7_fl_api *api,int out[4]) {
    static const uint32_t ids[]={0x1070175,0x1070178,0x1070187,0x107018a};
    for(unsigned i=0;i<4;i++) {
        uint8_t value=0;
        if(api->size(ids[i])!=1||api->read(ids[i],&value)!=1)return A7_FL_PREVIEW_READ;
        out[i]=i?(int)(int8_t)value:(int)value;
    }
    if(!((out[0]>=1&&out[0]<=12)||out[0]==14))return A7_FL_PREVIEW_VALUE;
    for(unsigned i=1;i<4;i++)if(out[i]<-3||out[i]>3)return A7_FL_PREVIEW_VALUE;
    return 0;
}
int a7_fl_preview_request(uintptr_t base,const struct a7_fl_api *api,
                         int (*readable)(void *,uintptr_t,unsigned),void *opaque) {
    report.attempts++;
    if(!base||base>UINT32_MAX-0x1617dcu||!api||!api->size||!api->read||!readable)
        return finish(A7_FL_PREVIEW_ARGUMENT);
    for(unsigned i=0;i<6;i++) {
        uintptr_t address=base+a7_preview_offsets[i];
        if(readable(opaque,address,16)!=1)return finish(A7_FL_PREVIEW_PIN);
        const uint8_t *code=(const uint8_t *)address;
        for(unsigned j=0;j<16;j++)if(code[j]!=a7_preview_pins[i][j])return finish(A7_FL_PREVIEW_PIN);
    }
    int values[4],again[4],rc=active(api,values);
    if(rc)return finish(rc);
    struct native_api n={(void *)(base+0x15867c),(void *)(base+0x1617cd),
        (void *)(base+0x15d230),(void *)(base+0x15c7b8),
        (void *)(base+0x15aa58),(void *)(base+0x159c64)};
#ifdef A7_FL_PREVIEW_TEST
    extern void a7_fl_preview_test_bind(struct native_api *);
    a7_fl_preview_test_bind(&n);
#endif
    /* Allocate everything before construction/ownership transfer. Failure frees
     * only raw storage. These objects are exactly 20 bytes in the pinned setter. */
    void *objects[5];unsigned count=0;
    while(count<5) {
        objects[count]=n.allocate(20);
        if(!objects[count]) {rc=A7_FL_PREVIEW_ALLOC;goto failed;}
        count++;
    }
    rc=active(api,again);if(rc)goto failed;
    for(unsigned i=0;i<4;i++)if(again[i]!=values[i]) {rc=A7_FL_PREVIEW_CHANGED;goto failed;}
    for(unsigned i=0;i<4;i++)n.parameter(objects[i],values[i]);
    n.list(objects[4],0);
    static const unsigned ids[]={383,386,389,392};
    for(unsigned i=0;i<4;i++)n.add(objects[4],ids[i],objects[i]);
    /* Original setter adds the SAME style object twice. ParamList owns the
     * resulting list; use its original add/request functions, never free it. */
    n.add(objects[4],383,objects[0]);
    n.request("@M00B",38,objects[4]);
    for(unsigned i=0;i<4;i++)report.active[i]=values[i];
    report.issued++;return finish(1);
failed:
    while(count)n.release(objects[--count]);
    return finish(rc);
}
