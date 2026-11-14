/* Owned DMM request channel for the pinned 4.04 native ABI. No pixel I/O.
 * A successful Open holds a DMM reference, NOT exclusive DMA ownership. */
#ifndef A7_DMM_CHANNEL_H
#define A7_DMM_CHANNEL_H
#include <stdint.h>
enum a7_dmm_result { A7_DMM_OK=0,A7_DMM_PENDING=1,A7_DMM_ARGUMENT=-1,
    A7_DMM_ALLOC=-2,A7_DMM_SEND=-3,A7_DMM_REPLY=-4,A7_DMM_REMOTE=-5,A7_DMM_STATE=-6 };
struct a7_dmm_native {
    void (*construct)(void *dmm,uint16_t owner);
    void (*destroy)(void *dmm);
    int (*send)(void *channel,void *message,uint16_t bytes,uint32_t reply_queue,uint32_t target);
    int (*receive)(void *channel,void *message,uint16_t bytes,uint32_t reply_queue,uint32_t timeout);
};
struct a7_dmm_channel {
    /* Original DmmCh: vptr, queue, owner, then DataflowInfraCh. 64 bytes bound
     * reserves more than its constructor's 44-byte object; code must be pinned
     * before these callbacks are supplied. Never copy a constructed instance. */
    uint32_t object[16];
    struct a7_dmm_native api;
    uint32_t constructed,pending,held,poisoned,command,request_handle;
    int transport_error,remote_status;
    uint8_t reply[24];
    /* Diagnostic wire bytes, never proof of a successful/matching request. */
    uint8_t observed_reply[24];
};
/* The caller serializes this object and keeps it resident until dispose succeeds.
 * A receive timeout leaves the queue and any in-flight request alive. No blind
 * retry, freeing a queue with a pending reply, or reporting timeout as success.
 * Timeout values use the native receiver's units; this API does not assume ms. */
int a7_dmm_init(struct a7_dmm_channel *,const struct a7_dmm_native *,uint16_t owner);
int a7_dmm_info(struct a7_dmm_channel *,uint16_t handle,uint32_t timeout);
int a7_dmm_open(struct a7_dmm_channel *,uint16_t handle,uint32_t timeout);
int a7_dmm_close(struct a7_dmm_channel *,uint32_t timeout);
int a7_dmm_poll(struct a7_dmm_channel *,uint32_t timeout);
/* Reconcile a retained GetUnitInfo reply only when command and private reply
 * queue match. Info replies do not echo a handle, even on success. This never
 * opens a unit or claims frame ownership. */
int a7_dmm_reconcile_info(struct a7_dmm_channel *);
int a7_dmm_dispose(struct a7_dmm_channel *);
/* Only after a matched, successful Open. Single contiguous extent required.
 * Does not map the address or imply any particular pixel layout. */
int a7_dmm_extent(const struct a7_dmm_channel *,uint32_t *physical,uint32_t *bytes);
#endif
