/* Experimental r9: an actual model transition, followed by a timed restoration.
 * Requests use the framework queue directly, avoiding CmnMRUtil's memory-recall
 * bookkeeping. No Creative Style backup property or AV-CAM memory is written.
 * Native TimerManager callbacks are ordinary dispatcher calls, not signals.
 */
#include "a7-fl-preview-cycle.h"
#include "a7-fl-preview-cycle-pins.h"
struct stamp {int32_t sec,nsec;};
struct native_api {
    void *(*allocate)(unsigned);
    void *(*parameter)(void *,int);
    void *(*list)(void *,unsigned);
    void (*add)(void *,unsigned,void *);
    void (*request)(const char *,unsigned,void *);
    void (*release)(void *);
    void *(*timer_add)(void *,struct stamp *,void (*)(void *,struct stamp *,void *),void *);
    int (*timer_remove)(void *,void *);
};
static struct a7_fl_preview_report report;
static struct a7_fl_preview_cycle_report cycle;
static struct {
    uint32_t lock;
    uintptr_t base,obj;
    void *handle,*timer,*record,*restore[5];
    uint32_t expired,repeat;
    int (*readable)(void *,uintptr_t,unsigned);
    void *opaque;
    struct native_api n;
    struct a7_fl_api backup;
    int original[4];
} state;
const struct a7_fl_preview_report *a7_fl_preview_status(void){return &report;}
const struct a7_fl_preview_cycle_report *a7_fl_preview_cycle_status(void){return &cycle;}
static int finish(int rc){report.last_result=rc;__atomic_store_n(&state.lock,0,__ATOMIC_RELEASE);return rc;}
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
static int deadline(struct stamp *t) {
#ifdef A7_FL_PREVIEW_CYCLE_TEST
    extern int cycle_test_clock(struct stamp *);
    int rc=cycle_test_clock(t);
#else
    register long nr __asm__("r7")=263,r0 __asm__("r0")=1,r1 __asm__("r1")=(long)t;
    __asm__ volatile("svc #0":"+r"(r0):"r"(nr),"r"(r1):"memory","cc");
    int rc=(int)r0;
#endif
    if(rc||t->sec<0||t->sec>=0x7ffffffe||t->nsec<0||t->nsec>=1000000000)return 0;
    t->nsec+=300000000;if(t->nsec>=1000000000){t->nsec-=1000000000;t->sec++;}return 1;
}
static void send(void **objects,const int values[4]) {
    static const unsigned ids[]={383,386,389,392};
    for(unsigned i=0;i<4;i++)state.n.parameter(objects[i],values[i]);
    state.n.list(objects[4],0);
    for(unsigned i=0;i<4;i++)state.n.add(objects[4],ids[i],objects[i]);
    state.n.add(objects[4],383,objects[0]);
    state.n.request("@M00B",38,objects[4]);
}
static void restore(void *record,struct stamp *now,void *opaque) {
    (void)now;
    while(__atomic_exchange_n(&state.lock,1,__ATOMIC_ACQUIRE)){}
    if(opaque!=&state||!cycle.pending){finish(A7_FL_PREVIEW_TIMER);return;}
    /* No TimerManager operation is called while admission holds state.lock.
     * If a heavily delayed caller has not queued the temporary command yet,
     * expire the armed timer and let that caller release its raw allocations. */
    if(cycle.pending==1){
        state.expired=1;finish(A7_FL_PREVIEW_TIMER);
        state.n.timer_remove(state.timer,record);return;
    }
    if(cycle.pending!=2||record!=state.record){finish(A7_FL_PREVIEW_TIMER);return;}
    cycle.pending=3;state.repeat=0;
    __atomic_store_n(&state.lock,0,__ATOMIC_RELEASE);
    state.n.timer_remove(state.timer,record);
    int values[4],rc=active(&state.backup,values);
    if(rc)for(unsigned i=0;i<4;i++)values[i]=state.original[i];
    /* Preserve a different style selected by the user during the interval. */
    if(!rc&&values[0]==cycle.temporary_style)
        for(unsigned i=0;i<4;i++)values[i]=state.original[i];
    send(state.restore,values); /* raw storage reserved before temporary command */
    while(__atomic_exchange_n(&state.lock,1,__ATOMIC_ACQUIRE)){}
    for(unsigned i=0;i<4;i++)report.active[i]=values[i];
    state.record=0;cycle.pending=0;cycle.restored++;cycle.restore_result=rc?rc:1;
    unsigned repeat=state.repeat;finish(rc?rc:2);
    if(repeat)a7_fl_preview_request(state.base,&state.backup,state.readable,state.opaque);
}
static int process_id(void) {
#ifdef A7_FL_PREVIEW_CYCLE_TEST
    return 42;
#else
    register long nr __asm__("r7")=20,r0 __asm__("r0");
    __asm__ volatile("svc #0":"=r"(r0):"r"(nr):"memory","cc");return (int)r0;
#endif
}
static int prepare(uintptr_t base,int (*readable)(void*,uintptr_t,unsigned),void *opaque) {
    if(state.handle)return state.base==base&&((int*)state.timer)[9]==process_id()?0:A7_FL_PREVIEW_LIBRARY;
    void *(*open)(const char*,int)=(void*)(base+0x15d958);
    void *(*symbol)(void*,const char*)=(void*)(base+0x15c8dc);
    int (*close)(void*)=(void*)(base+0x15bf38);
#ifdef A7_FL_PREVIEW_CYCLE_TEST
    extern void cycle_test_loader(void *(**)(const char*,int),void *(**)(void*,const char*),int (**)(void*));
    cycle_test_loader(&open,&symbol,&close);
#endif
    void *h=open("/usr/lib/libObj.so",6);if(!h)return A7_FL_PREVIEW_LIBRARY;
    uintptr_t f=(uintptr_t)symbol(h,"_ZN12TimerManager3addEP8timespecPFvP18timeCallBackRecordS1_PvES4_");
    if(f<=0x8641b3u)goto bad;
    uintptr_t obj=f-0x8641b3u;
    if(obj>UINT32_MAX-0x13288c0u||
       (uintptr_t)symbol(h,"timerManager")!=obj+0x13288bc||
       (uintptr_t)symbol(h,"_ZN12TimerManager6removeEP18timeCallBackRecord")!=obj+0x86420d)goto bad;
    for(unsigned i=0;i<sizeof a7_cycle_obj_offsets/sizeof a7_cycle_obj_offsets[0];i++) {
        uintptr_t address=obj+a7_cycle_obj_offsets[i];
        if(readable(opaque,address,16)!=1)goto bad;
        for(unsigned j=0;j<16;j++)if(*(const uint8_t*)(address+j)!=a7_cycle_obj_pins[i][j])goto bad;
    }
    if(readable(opaque,obj+0x13288bc,4)!=1)goto bad;
    void *manager=*(void**)(obj+0x13288bc);
    if(!manager||readable(opaque,(uintptr_t)manager,40)!=1||
       ((int*)manager)[9]!=process_id())goto bad;
    state.n=(struct native_api){(void*)(base+0x15867c),(void*)(base+0x1617cd),
        (void*)(base+0x15d230),(void*)(base+0x15c7b8),(void*)(base+0x159924),
        (void*)(base+0x159c64),(void*)(obj+0x8641b3),(void*)(obj+0x86420d)};
#ifdef A7_FL_PREVIEW_CYCLE_TEST
    extern void cycle_test_bind(struct native_api *);
    cycle_test_bind(&state.n);
#endif
    state.base=base;state.obj=obj;state.timer=manager;state.handle=h;return 0;
bad:
    close(h);return A7_FL_PREVIEW_LIBRARY;
}
int a7_fl_preview_request(uintptr_t base,const struct a7_fl_api *api,
                         int (*readable)(void *,uintptr_t,unsigned),void *opaque) {
    if(__atomic_exchange_n(&state.lock,1,__ATOMIC_ACQUIRE))return A7_FL_PREVIEW_CHANGED;
    report.attempts++;
    if(!base||base>UINT32_MAX-0x1617dcu||!api||!api->size||!api->read||!readable)
        return finish(A7_FL_PREVIEW_ARGUMENT);
    if(cycle.pending){
        if(base!=state.base||api->read!=state.backup.read||api->size!=state.backup.size)return finish(A7_FL_PREVIEW_CHANGED);
        cycle.coalesced++;if(cycle.pending==3)state.repeat=1;return finish(1);
    }
    for(unsigned i=0;i<sizeof a7_cycle_view_offsets/sizeof a7_cycle_view_offsets[0];i++) {
        uintptr_t address=base+a7_cycle_view_offsets[i];
        if(readable(opaque,address,16)!=1)return finish(A7_FL_PREVIEW_PIN);
        for(unsigned j=0;j<16;j++)if(*(const uint8_t*)(address+j)!=a7_cycle_view_pins[i][j])return finish(A7_FL_PREVIEW_PIN);
    }
    int values[4],again[4],rc=active(api,values);if(rc)return finish(rc);
    rc=prepare(base,readable,opaque);if(rc)return finish(rc);
    void *objects[10];unsigned count=0;
    while(count<10){objects[count]=state.n.allocate(20);if(!objects[count]){rc=A7_FL_PREVIEW_ALLOC;goto failed;}count++;}
    rc=active(api,again);if(rc)goto failed;
    for(unsigned i=0;i<4;i++)if(values[i]!=again[i]){rc=A7_FL_PREVIEW_CHANGED;goto failed;}
    struct stamp when;if(!deadline(&when)){rc=A7_FL_PREVIEW_TIMER;goto failed;}
    for(unsigned i=0;i<4;i++)state.original[i]=report.active[i]=values[i];
    for(unsigned i=0;i<5;i++)state.restore[i]=objects[i+5];
    state.backup=*api;state.readable=readable;state.opaque=opaque;
    state.expired=0;cycle.pending=1;
    /* Avoid lock inversion with the native timer dispatcher. */
    __atomic_store_n(&state.lock,0,__ATOMIC_RELEASE);
    void *record=state.n.timer_add(state.timer,&when,restore,&state);
    while(__atomic_exchange_n(&state.lock,1,__ATOMIC_ACQUIRE)){}
    if(!record||state.expired){cycle.pending=0;rc=A7_FL_PREVIEW_TIMER;goto failed;}
    state.record=record;
    /* Arm the guaranteed restoration before the temporary command. If timing,
     * allocation or pin validation fails, no temporary command is sent. */
    cycle.pending=2;cycle.restore_result=0;
    cycle.temporary_style=values[0]==1?7:1;values[0]=cycle.temporary_style;
    send(objects,values);report.issued++;return finish(1);
failed:
    while(count)state.n.release(objects[--count]);
    return finish(rc);
}
