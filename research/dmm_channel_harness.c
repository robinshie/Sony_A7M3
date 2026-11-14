#include <stdint.h>
#include <stddef.h>
#include "a7-dmm-channel.h"
static unsigned cases,checks,allocations,frees,sends,receives,allocate_failure,send_failure,receive_failure;
static unsigned bad_reply,remote_failure,last_timeout,command,handle,queue=0x123456,original_call;
static unsigned allowed_timeout=7,sleep_calls;
static unsigned frame_case,fail_command,dump_calls;
static void *channel;
static uint8_t sent[24],native_sent[24];
void *memset(void *p,int c,size_t n){uint8_t *d=p;while(n--)*d++=(uint8_t)c;return p;}
void *memcpy(void *p,const void *q,size_t n){uint8_t *d=p;const uint8_t *s=q;while(n--)*d++=*s++;return p;}
static void put(const char *s){volatile uint32_t *u=(void*)0x09000000;while(*s)u[0]=*s++;}
static void number(unsigned n){char b[12];unsigned i=0;do{b[i++]=(char)('0'+n%10);n/=10;}while(n);while(i){char s[2]={b[--i],0};put(s);}}
static void stop(void){register unsigned r0 __asm__("r0")=0x18,r1 __asm__("r1")=0x20026;__asm__ volatile("svc 0xab":"+r"(r0),"+r"(r1)::"memory");while(1){}}
static void check(int ok,const char *s){checks++;if(!ok){put("FAIL ");put(s);put(" case=");number(cases);put("\n");stop();}}
static unsigned u16(const uint8_t *p){return p[0]|((unsigned)p[1]<<8);}
static void p16(uint8_t *p,unsigned v){p[0]=(uint8_t)v;p[1]=(uint8_t)(v>>8);}
static void p32(uint8_t *p,unsigned v){p16(p,v);p16(p+2,v>>16);}
static int print_level(void){return 0;}
static void native_log(unsigned a,unsigned b,unsigned c,unsigned d,unsigned e){(void)a;(void)b;(void)c;(void)d;(void)e;}
static void forbidden_native_call(void){check(0,"unexpected original dependency");}
static int queue_alloc(void *self,uint32_t *id,int mode){
    allocations++;check(mode==1,"original queue lifetime policy");channel=self;*id=allocate_failure?0:queue;return allocate_failure?1:0;
}
static int queue_free(void *self,uint32_t id){frees++;check(self==channel&&id==queue,"free owned queue only");return 0;}
static int queue_send(void *self,void *message,uint16_t n,uint32_t id,uint32_t target){
    check(self==channel&&id==queue&&n==24&&target==0x61003c,"native send ABI");sends++;memcpy(sent,message,24);
    command=u16(sent);handle=u16(sent+2);return send_failure?1:0;
}
static int queue_receive(void *self,void *message,uint16_t n,uint32_t id,uint32_t timeout){
    check(self==channel&&id==queue&&n==24,"native receive ABI");receives++;last_timeout=timeout;
    check(timeout==(original_call?UINT32_MAX:allowed_timeout),"bounded receive timeout");
    if(receive_failure||command==fail_command)return 1;
    uint8_t *p=message;memset(p,0,24);p16(p,(0x8000|command)+(bad_reply==1));p16(p+2,remote_failure?0xffff:0);
    p16(p+4,remote_failure||command!=5?0:handle+(bad_reply==2));p16(p+6,queue+(bad_reply==4));p32(p+8,bad_reply==3?2:1);
    unsigned bytes=frame_case==2?4177920:1048576;
    p32(p+16,frame_case&&command==0x13?bytes:0x10000000);p32(p+20,frame_case?bytes:4096);return 0;
}
#include "native-fixups.h"
static const struct a7_dmm_native api={
    (void*)0x50035ba9,(void*)0x50035b55,queue_send,queue_receive
};
static void reset(void){allocations=frees=sends=receives=allocate_failure=send_failure=receive_failure=bad_reply=remote_failure=last_timeout=original_call=sleep_calls=frame_case=fail_command=dump_calls=0;allowed_timeout=7;cases++;}
static void native_request(unsigned op,uint16_t unit){
    uint32_t obj[16];uint8_t reply[24];memset(obj,0xc7,sizeof obj);api.construct(obj,41);
    for(unsigned i=11;i<16;i++)check(obj[i]==0xc7c7c7c7,"original constructor fits 44 bytes");
    original_call=1;
    if(op==5)check(!((int(*)(void*,void*,uint16_t,uint16_t,uint32_t))0x50035f31)(obj,reply,unit,0,UINT32_MAX),"original Open");
    else check(!((int(*)(void*,void*,uint16_t))(op==6?0x50036039:0x50036235))(obj,reply,unit),"original Close/Info");
    memcpy(native_sent,sent,24);api.destroy(obj);original_call=0;
}
static void compare_requests(void){
    static const uint16_t handles[]={1,0x1234,0x44b2,0xffff};
    for(unsigned q=0;q<3;q++)for(unsigned h=0;h<4;h++)for(unsigned op=0;op<3;op++){
        reset();queue=q==0?0x123456:q==1?0xffff:0x654321;
        unsigned cmd=op==0?0x13:op==1?5:6;native_request(cmd,handles[h]);
        struct a7_dmm_channel c={0};check(!a7_dmm_init(&c,&api,41),"our native constructor");
        int result;
        if(cmd==0x13)result=a7_dmm_info(&c,handles[h],7);
        else if(cmd==5)result=a7_dmm_open(&c,handles[h],7);
        else {check(!a7_dmm_open(&c,handles[h],7),"hold before close");result=a7_dmm_close(&c,7);}
        check(!result,"own request complete");for(unsigned i=0;i<24;i++)check(sent[i]==native_sent[i],"byte-exact original request");
        if(cmd==5){uint32_t address=0,length=0;check(!a7_dmm_extent(&c,&address,&length)&&address==0x10000000&&length==4096,"extent parse");
            check(a7_dmm_dispose(&c)==A7_DMM_STATE,"do not drop open reference");check(!a7_dmm_close(&c,7),"close exact reference");}
        check(!a7_dmm_dispose(&c)&&allocations==frees,"original destructor balances queues");
    }
}
static void faults(void){
    struct a7_dmm_channel c;
    reset();memset(&c,0,sizeof c);allocate_failure=1;
    check(a7_dmm_init(&c,&api,41)==A7_DMM_ALLOC&&!c.constructed&&!sends&&!frees,"allocation failure before send");
    for(unsigned op=0;op<2;op++){
        reset();memset(&c,0,sizeof c);check(!a7_dmm_init(&c,&api,41),"init timeout test");receive_failure=1;
        check((op?a7_dmm_open(&c,123,7):a7_dmm_info(&c,123,7))==A7_DMM_PENDING&&c.pending,"retain pending reply");
        check(a7_dmm_dispose(&c)==A7_DMM_STATE&&a7_dmm_info(&c,124,7)==A7_DMM_STATE&&sends==1&&!frees,"no retry or queue reuse");
        receive_failure=0;check(!a7_dmm_poll(&c,7)&&!c.pending,"late reply on same queue");
        if(op)check(!a7_dmm_close(&c,7),"late Open closed");check(!a7_dmm_dispose(&c),"late completion cleanup");
    }
    reset();memset(&c,0,sizeof c);check(!a7_dmm_init(&c,&api,41),"init ambiguous send");send_failure=1;
    check(a7_dmm_open(&c,123,7)==A7_DMM_SEND&&c.pending&&!receives,"send ambiguity retained");
    check(!a7_dmm_poll(&c,7)&&c.held==123,"ambiguous send later completed");send_failure=0;
    check(!a7_dmm_close(&c,7)&&!a7_dmm_dispose(&c),"ambiguous send balanced");
    for(unsigned bad=1;bad<=4;bad++){
        reset();memset(&c,0,sizeof c);check(!a7_dmm_init(&c,&api,41),"init bad response");bad_reply=bad;
        int result=a7_dmm_open(&c,123,7);
        if(bad!=3)check(result==A7_DMM_REPLY&&c.poisoned&&a7_dmm_dispose(&c)==A7_DMM_STATE&&!frees,"mismatched completion quarantined");
        else {uint32_t a=77,n=88;check(!result&&a7_dmm_extent(&c,&a,&n)==A7_DMM_REPLY&&a==77&&n==88,"scatter extent rejected unchanged");
            bad_reply=0;check(!a7_dmm_close(&c,7)&&!a7_dmm_dispose(&c),"scatter reference closed");}
    }
    reset();memset(&c,0,sizeof c);check(!a7_dmm_init(&c,&api,41),"init remote failure");remote_failure=1;
    check(a7_dmm_open(&c,123,7)==A7_DMM_REMOTE&&!c.held&&!c.pending&&c.remote_status==-1,"remote open failure");
    remote_failure=0;check(!a7_dmm_open(&c,123,7),"retry known failed Open");remote_failure=1;
    check(a7_dmm_close(&c,7)==A7_DMM_REMOTE&&c.held==123,"failed close retains reference");
    remote_failure=0;check(!a7_dmm_close(&c,7)&&!a7_dmm_dispose(&c),"retry known failed Close");
    reset();memset(&c,0,sizeof c);check(!a7_dmm_init(&c,&api,41),"init invalid args");
    check(a7_dmm_open(&c,0,7)==A7_DMM_STATE&&a7_dmm_info(&c,123,UINT32_MAX)==A7_DMM_STATE&&!sends,"no zero handle or unbounded wait");
    check(!a7_dmm_dispose(&c),"dispose idle");
    for(unsigned wrong=0;wrong<3;wrong++){
        reset();memset(&c,0,sizeof c);check(!a7_dmm_init(&c,&api,41),"init retained error");
        c.pending=c.poisoned=1;c.command=0x13;c.request_handle=0x44b2;
        p16(c.observed_reply,0x8013+(wrong==1));p16(c.observed_reply+2,0xfffb);
        p16(c.observed_reply+6,queue+(wrong==2));
        int rc=a7_dmm_reconcile_info(&c);
        if(wrong)check(rc==A7_DMM_REPLY&&c.pending&&c.poisoned&&!frees,"foreign errors remain retained");
        else check(rc==A7_DMM_REMOTE&&c.remote_status==-5&&!c.pending&&!c.poisoned&&
                   !a7_dmm_dispose(&c)&&allocations==frees,"known failed Info releases its queue");
    }
    reset();memset(&c,0,sizeof c);check(!a7_dmm_init(&c,&api,41),"init captured Info success");
    static const uint8_t live_info[24]={0x13,0x80,0,0,0,0,0xb8,0x60,1,0,1,0,1,0,0,0,0,0xc0,0x3f,0,0,0,0,0};
    memcpy(c.observed_reply,live_info,24);p16(c.observed_reply+6,queue);
    c.pending=c.poisoned=1;c.command=0x13;c.request_handle=19393;
    check(!a7_dmm_reconcile_info(&c)&&!c.pending&&!c.held&&!c.poisoned,"Info success has no echoed handle");
    for(unsigned i=0;i<24;i++)check(c.reply[i]==c.observed_reply[i],"complete Info payload retained");
    check(!a7_dmm_dispose(&c)&&allocations==frees,"captured successful Info queue cleanup");
}
#define A7_DMM_OBSERVER_TEST
static int observer_sleep(void){sleep_calls++;return 0;}
#include "dmm_frame_dump.h"
void a7_dmm_frame_dump(struct a7_dmm_dump_result *r,uint32_t physical,uint32_t length){
 check(command==5&&physical==0x10000000&&length==(frame_case==2?4177920u:1048576u),"read follows successful exact Open");
 dump_calls++;r->status=0;r->physical=physical;r->length=r->written=length;r->reads=256;
}
#include "dmm_observer.c"
static void observer_tests(void){
    uint32_t trace[200];uint8_t metadata[60];
    for(unsigned mode=0;mode<5;mode++){
        reset();allowed_timeout=0;memset(trace,0,sizeof trace);memset(metadata,0,sizeof metadata);
        struct a7_dmm_observer *o=(void*)((uint8_t*)trace+A7_DMM_OBSERVER_OFFSET);
        check(!a7_dmm_init(&o->channel,&api,41),"observer independent queue");
        metadata[0]=1;p16(metadata+8,0x1234);p16(metadata+20,1616);p16(metadata+22,1080);
        if(mode==1)metadata[0]=0;if(mode==2)p16(metadata+20,320);
        if(mode==3)receive_failure=1;if(mode==4)remote_failure=1;
        a7yc_dmm_observe(trace,metadata);
        if(mode==1||mode==2)check(!o->attempted&&!sends&&!sleep_calls,"skip unavailable or small entries");
        else{
            check(o->attempted==1&&sends==1&&!frees,"single in-call query");
            for(unsigned i=0;i<60;i++)check(o->metadata[i]==metadata[i],"paired metadata snapshot");
            a7yc_dmm_observe(trace,metadata);check(sends==1,"no repeated requests");
            if(mode==3){check(o->polls==10&&sleep_calls==10&&o->status==A7_DMM_PENDING&&o->channel.pending,"bounded callback wait");
                receive_failure=0;check(!a7_dmm_poll(&o->channel,0),"late callback reply consumed");}
            else check(!o->polls&&!sleep_calls&&o->status==(mode==4?A7_DMM_REMOTE:0),"immediate observer result");
        }
        check(!a7_dmm_dispose(&o->channel)&&allocations==frees,"observer cleanup");
    }
    for(unsigned slow=0;slow<3;slow++){
        reset();frame_case=1;allowed_timeout=0;fail_command=slow==1?5:slow==2?6:0;
        memset(trace,0,sizeof trace);trace[12]=8;memset(metadata,0,sizeof metadata);
        struct a7_dmm_observer *o=(void*)((uint8_t*)trace+A7_DMM_OBSERVER_OFFSET);
        check(!a7_dmm_init(&o->channel,&api,41),"frame observer independent queue");
        metadata[0]=1;p16(metadata+8,0x1234);p16(metadata+20,1616);p16(metadata+22,1080);
        a7yc_dmm_observe(trace,metadata);
        if(!slow)check(o->phase==4&&dump_calls==1&&!o->channel.held&&!o->channel.pending&&sends==3,"Info Open copy Close ordering");
        else {
            check(o->channel.pending&&o->polls==10&&sleep_calls==10&&dump_calls==(slow==2),"late Open never read outside callback");
            fail_command=0;check(!a7_dmm_poll(&o->channel,0),"late completion consumed");
            if(o->channel.held)check(!a7_dmm_close(&o->channel,0),"late Open cleanup closes without reading");
            check(dump_calls==(slow==2),"USB cleanup is not a late frame reader");
        }
        check(!a7_dmm_dispose(&o->channel)&&allocations==frees,"balanced frame observer queue");
    }
    for(unsigned valid=0;valid<2;valid++){
        reset();frame_case=2;allowed_timeout=0;memset(trace,0,sizeof trace);trace[12]=9;memset(metadata,0,sizeof metadata);
        struct a7_dmm_observer *o=(void*)((uint8_t*)trace+A7_DMM_OBSERVER_OFFSET);
        check(!a7_dmm_init(&o->channel,&api,41),"sparse observer queue");
        metadata[0]=1;p16(metadata+8,0x1234);p16(metadata+20,1616);p16(metadata+22,1080);p16(metadata+24,valid?1920:1280);
        a7yc_dmm_observe(trace,metadata);
        check(o->phase==4&&dump_calls==valid&&!o->channel.pending&&!o->channel.held,"sparse requires exact observed geometry");
        check(sends==(valid?3u:1u),"unknown geometry never opened");
        check(!a7_dmm_dispose(&o->channel)&&allocations==frees,"sparse queue cleanup");
    }
}
void guest_main(void){
    for(unsigned i=0;i<sizeof fixups/sizeof *fixups;i++)*(volatile uint32_t*)fixups[i].address=(uint32_t)fixups[i].function+fixups[i].addend;
    compare_requests();faults();observer_tests();put("DMM_CHANNEL_PASSED cases=");number(cases);put(" checks=");number(checks);put("\n");stop();
}
