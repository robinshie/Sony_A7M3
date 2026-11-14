#include "dmm_observer.h"
#include <stddef.h>
#ifndef A7_DMM_OBSERVER_TEST
void *memset(void *p,int value,size_t n){uint8_t *d=p;while(n--)*d++=(uint8_t)value;return p;}
static int observer_sleep(void){uint32_t delay[2]={0,20000000};
    register long r7 __asm__("r7")=162,r0 __asm__("r0")=(long)delay,r1 __asm__("r1")=0;
    __asm__ volatile("svc #0":"+r"(r0):"r"(r7),"r"(r1):"memory","cc");return (int)r0;}
#endif
static uint32_t observer_word(const uint8_t *p){return p[0]|((uint32_t)p[1]<<8)|((uint32_t)p[2]<<16)|((uint32_t)p[3]<<24);}
static void observer_copy(uint8_t *d,const uint8_t *s){for(unsigned i=0;i<24;i++)d[i]=s[i];}
static void observer_wait(struct a7_dmm_observer *o){
    while(o->polls<10&&o->channel.pending&&!o->channel.poisoned){
        if(observer_sleep())break;o->polls++;o->status=a7_dmm_poll(&o->channel,0);
    }
}
void a7yc_dmm_observe(void *trace,const uint8_t *metadata){
    struct a7_dmm_observer *o=(void*)((uint8_t*)trace+A7_DMM_OBSERVER_OFFSET);
    if(!o->channel.constructed||o->attempted||!metadata||metadata[0]!=1)return;
    unsigned handle=metadata[8]|((unsigned)metadata[9]<<8);
    unsigned width=metadata[20]|((unsigned)metadata[21]<<8),height=metadata[22]|((unsigned)metadata[23]<<8);
    if(!handle||width<640||height<480)return;
    o->attempted=1;for(unsigned i=0;i<60;i++)o->metadata[i]=metadata[i];
    o->status=a7_dmm_info(&o->channel,(uint16_t)handle,0);
    /* Only one qualifying call is delayed, at most 200ms in nanosleep.
     * No GetUnitInfo retry, unit Open, physical mapping or pixel write. */
    observer_wait(o);o->info_status=o->status;
    if(!o->channel.pending&&!o->channel.poisoned)observer_copy(o->info_reply,o->channel.reply);
    unsigned mode=((uint32_t*)trace)[12];
    if(mode<8||o->status||o->channel.pending||o->channel.poisoned)return;
    /* Info +16 matched the observed native allocation length. Keep all raw
     * replies; require Open's independently returned length to match it. */
    uint32_t expected=observer_word(o->info_reply+16);
    if(metadata[44]!=0||metadata[12]||metadata[13]||metadata[14]||metadata[15]||expected<1024*1024||expected>8*1024*1024){o->status=-20;o->phase=4;return;}
    if(mode==9&&(metadata[24]!=0x80||metadata[25]!=7||expected!=4177920u)){o->status=-22;o->phase=4;return;}
    o->phase=1;o->status=a7_dmm_open(&o->channel,(uint16_t)handle,0);
    observer_wait(o);o->open_status=o->status;
    if(!o->channel.pending&&!o->channel.poisoned)observer_copy(o->open_reply,o->channel.reply);
    if(o->status||o->channel.pending||o->channel.poisoned)return;
    o->phase=2;uint32_t physical=0,length=0;
    o->dump.status=-21;
    if(!a7_dmm_extent(&o->channel,&physical,&length)&&length==expected)
        a7_dmm_frame_dump(&o->dump,physical,length);
    /* The read is only permitted here, while still inside the original call.
     * USB cleanup after a delayed reply must close, never perform this read. */
    o->phase=3;o->status=a7_dmm_close(&o->channel,0);
    observer_wait(o);o->close_status=o->status;
    if(!o->channel.pending&&!o->channel.poisoned){observer_copy(o->close_reply,o->channel.reply);if(!o->status)o->phase=4;}
    /* Queue disposal happens under the trace lock in the USB stop operation. */
}
