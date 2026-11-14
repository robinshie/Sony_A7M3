#include "a7-dmm-channel.h"
static unsigned u16(const uint8_t *p){return p[0]|((unsigned)p[1]<<8);}
static uint32_t u32(const uint8_t *p){return u16(p)|((uint32_t)u16(p+2)<<16);}
static void put16(uint8_t *p,unsigned v){p[0]=(uint8_t)v;p[1]=(uint8_t)(v>>8);}
static void put32(uint8_t *p,uint32_t v){put16(p,v);put16(p+2,v>>16);}
int a7_dmm_init(struct a7_dmm_channel *c,const struct a7_dmm_native *api,uint16_t owner){
    if(!c||!api||!api->construct||!api->destroy||!api->send||!api->receive||!owner||
       c->constructed||c->pending||c->held||c->poisoned)return A7_DMM_ARGUMENT;
    c->api=*api;c->api.construct(c->object,owner);c->constructed=1;
    if(!c->object[1]){c->api.destroy(c->object);c->constructed=0;return A7_DMM_ALLOC;}
    return 0;
}
static int accept_reply(struct a7_dmm_channel *c,const uint8_t *next){
    int remote=(int16_t)u16(next+2);
    if(u16(next)!=(0x8000u|c->command)||u16(next+6)!=(c->object[1]&65535)||
       (!remote&&c->command==5&&u16(next+4)!=c->request_handle)){
        c->poisoned=1;return A7_DMM_REPLY;
    }
    for(unsigned i=0;i<24;i++)c->reply[i]=next[i];
    c->remote_status=remote;c->pending=0;c->poisoned=0;
    if(c->remote_status)return A7_DMM_REMOTE;
    if(c->command==5)c->held=c->request_handle;
    else if(c->command==6)c->held=0;
    return 0;
}
int a7_dmm_reconcile_info(struct a7_dmm_channel *c){
    if(!c||!c->constructed||!c->pending||!c->poisoned||c->held||c->command!=0x13)return A7_DMM_STATE;
    return accept_reply(c,c->observed_reply);
}
int a7_dmm_poll(struct a7_dmm_channel *c,uint32_t timeout){
    if(!c||!c->constructed||!c->pending||c->poisoned||timeout==UINT32_MAX)return A7_DMM_STATE;
    /* Private response bytes do not escape until transport + message identity
     * pass. A timeout/error is not permission to overwrite or recycle a queue. */
    uint8_t next[24]={0};
    c->transport_error=c->api.receive((uint8_t *)c->object+12,next,24,c->object[1],timeout);
    if(c->transport_error)return A7_DMM_PENDING;
    for(unsigned i=0;i<24;i++)c->observed_reply[i]=next[i];
    return accept_reply(c,next);
}
static int request(struct a7_dmm_channel *c,unsigned command,uint16_t handle,uint32_t timeout){
    if(!c||!c->constructed||c->pending||c->poisoned||!handle||timeout==UINT32_MAX||
       (command==6?c->held!=handle:c->held!=0))return A7_DMM_STATE;
    uint8_t message[24]={0};put16(message,command);put16(message+2,handle);
    /* Exact request body used by DmmCh::{getUnitInfo,open,close}. Open uses
     * flags=0 and memory mask UINT32_MAX, matching the native utility path. */
    if(command==5)put32(message+12,UINT32_MAX);
    put32(message+16,c->object[1]);put16(message+20,c->object[1]);
    c->command=command;c->request_handle=handle;c->remote_status=0;c->pending=1;
    c->transport_error=c->api.send((uint8_t *)c->object+12,message,24,c->object[1],0x61003c);
    if(c->transport_error){
        /* The native API does not establish whether a failing send queued a
         * request. Retain its channel; poll may still consume a late reply. */
        return A7_DMM_SEND;
    }
    return a7_dmm_poll(c,timeout);
}
int a7_dmm_info(struct a7_dmm_channel *c,uint16_t handle,uint32_t timeout){return request(c,0x13,handle,timeout);}
int a7_dmm_open(struct a7_dmm_channel *c,uint16_t handle,uint32_t timeout){return request(c,5,handle,timeout);}
int a7_dmm_close(struct a7_dmm_channel *c,uint32_t timeout){
    if(!c||!c->held||c->held>65535)return A7_DMM_STATE;
    return request(c,6,(uint16_t)c->held,timeout);
}
int a7_dmm_dispose(struct a7_dmm_channel *c){
    if(!c||!c->constructed||c->pending||c->held||c->poisoned)return A7_DMM_STATE;
    c->api.destroy(c->object);c->constructed=0;return 0;
}
int a7_dmm_extent(const struct a7_dmm_channel *c,uint32_t *physical,uint32_t *bytes){
    if(!c||!physical||!bytes||!c->constructed||c->pending||c->poisoned||!c->held||c->command!=5||c->remote_status)return A7_DMM_STATE;
    /* Address +16 and length +20 match the original consumer. +8 is an
     * observed selector, not yet a proven extent-count field; reject values
     * other than the one observed native reply. No pixel layout is inferred. */
    uint32_t address=u32(c->reply+16),length=u32(c->reply+20);
    if(u32(c->reply+8)!=1||!address||!length||length>UINT32_MAX-address)return A7_DMM_REPLY;
    *physical=address;*bytes=length;return 0;
}
