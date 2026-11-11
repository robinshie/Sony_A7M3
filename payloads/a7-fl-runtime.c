/* Guarded camera-resident LUT toggle. No constructor, filesystem or save call.
 * This modifies backup RAM and fires native callbacks. A later unrelated global
 * backup save MAY persist that RAM. The caller must not describe this alone as
 * independent or autosave-safe calibration storage.
 */
#include "a7-fl-runtime.h"

static int equal(const uint8_t *a,const uint8_t *b) {
    for(unsigned i=0;i<A7_FL_BYTES;i++) if(a[i]!=b[i]) return 0;
    return 1;
}
static void copy(uint8_t *a,const uint8_t *b) {
    for(unsigned i=0;i<A7_FL_BYTES;i++) a[i]=b[i];
}
uint32_t a7_fl_crc(const uint8_t *bytes,uint32_t n) {
    uint32_t crc=~0u;
    for(uint32_t i=0;i<n;i++) {
        crc^=bytes[i];
        for(unsigned j=0;j<8;j++) crc=(crc>>1)^((0u-(crc&1u))&0xedb88320u);
    }
    return ~crc;
}
static int enter(struct a7_fl_context *c) {
    return __atomic_exchange_n(&c->lock,1u,__ATOMIC_ACQUIRE)==0;
}
static int leave(struct a7_fl_context *c,int result) {
    c->last_error=result;
    __atomic_store_n(&c->lock,0u,__ATOMIC_RELEASE);
    return result;
}
static int layout(struct a7_fl_context *c) {
    return c->api.size(A7_FL_PROPERTY)==(int)A7_FL_BYTES &&
           c->api.attr(A7_FL_PROPERTY)==8;
}
static int read_current(struct a7_fl_context *c) {
    c->read_result=c->api.read(A7_FL_PROPERTY,c->scratch);
    if(c->read_result!=(int)A7_FL_BYTES) return A7_FL_READ;
    if(equal(c->scratch,c->original)) return A7_FL_OFF;
    if(equal(c->scratch,c->candidate)) return A7_FL_ON;
    return A7_FL_FOREIGN;
}
static int table_valid(const uint8_t *original,const uint8_t *candidate) {
    int different=0;
    for(unsigned i=0;i<A7_FL_BYTES;i++) {
        int a=(int)(int8_t)original[i],b=(int)(int8_t)candidate[i];
        if(i>=1215) {if(a!=b) return 0;continue;}
        if(a < -64 || a>63 || b < -64 || b>63) return 0;
        different|=b!=a;
    }
    return different;
}
int a7_fl_init(struct a7_fl_context *c,const struct a7_fl_api *api,
               const uint8_t *original,uint32_t original_crc,
               const uint8_t *candidate,uint32_t candidate_crc) {
    if(!c||!api||!original||!candidate) return A7_FL_ARGUMENT;
    if(!enter(c)) return A7_FL_BUSY;
    /* Never replace tables in a live context, especially while it is enabled. */
    if(c->initialized) return leave(c,A7_FL_ARGUMENT);
    if(!api->size||!api->attr||!api->read||!api->write) return leave(c,A7_FL_API);
    if(a7_fl_crc(original,A7_FL_BYTES)!=original_crc ||
       a7_fl_crc(candidate,A7_FL_BYTES)!=candidate_crc || !table_valid(original,candidate))
        return leave(c,A7_FL_TABLE);
    c->api=*api;copy(c->original,original);copy(c->candidate,candidate);
    c->state=A7_FL_UNKNOWN;
    if(!layout(c)) {c->state=A7_FL_UNKNOWN;return leave(c,A7_FL_LAYOUT);}
    int actual=read_current(c);
    if(actual<0) return leave(c,actual);
    c->state=actual;c->initialized=1;
    return leave(c,A7_FL_OK);
}
int a7_fl_read_status(struct a7_fl_context *c) {
    if(!c) return A7_FL_ARGUMENT;
    if(!enter(c)) return A7_FL_BUSY;
    if(!c->initialized) return leave(c,A7_FL_UNINITIALIZED);
    if(!layout(c)) {c->state=A7_FL_UNKNOWN;return leave(c,A7_FL_LAYOUT);}
    int actual=read_current(c);
    c->state=actual<0?A7_FL_UNKNOWN:actual;
    return leave(c,actual<0?actual:A7_FL_OK);
}
int a7_fl_set(struct a7_fl_context *c,int enabled) {
    if(!c || (enabled!=0&&enabled!=1)) return A7_FL_ARGUMENT;
    if(!enter(c)) return A7_FL_BUSY;
    if(!c->initialized) return leave(c,A7_FL_UNINITIALIZED);
    if(!layout(c)) {c->state=A7_FL_UNKNOWN;return leave(c,A7_FL_LAYOUT);}
    int actual=read_current(c);
    if(actual<0) {c->state=A7_FL_UNKNOWN;return leave(c,actual);}
    if(actual==enabled) {c->state=actual;return leave(c,A7_FL_OK);}
    const uint8_t *target=enabled?c->candidate:c->original;
    c->write_result=c->api.write(3,A7_FL_PROPERTY,target);
    actual=read_current(c);
    if(c->write_result==(int)A7_FL_BYTES && actual==enabled) {
        c->state=enabled;return leave(c,A7_FL_OK);
    }
    int error=c->write_result==(int)A7_FL_BYTES?A7_FL_VERIFY:A7_FL_WRITE;
    /* An error return can follow an accepted write. Restore the known factory
     * table and independently read it; do not trust the acknowledgement alone.
     */
    c->recovery_result=c->api.write(3,A7_FL_PROPERTY,c->original);
    actual=read_current(c);
    if(actual==A7_FL_OFF) {c->state=A7_FL_OFF;return leave(c,error);}
    c->state=A7_FL_FAULT;
    return leave(c,A7_FL_RECOVERY);
}
int a7_fl_replace_candidate(struct a7_fl_context *c,const uint8_t *table,uint32_t crc) {
    if(!c||!table) return A7_FL_ARGUMENT;
    if(!enter(c)) return A7_FL_BUSY;
    if(!c->initialized) return leave(c,A7_FL_UNINITIALIZED);
    if(a7_fl_crc(table,A7_FL_BYTES)!=crc || !table_valid(c->original,table))
        return leave(c,A7_FL_TABLE);
    if(!layout(c)) {c->state=A7_FL_UNKNOWN;return leave(c,A7_FL_LAYOUT);}
    int actual=read_current(c);
    if(actual<0) {c->state=A7_FL_UNKNOWN;return leave(c,actual);}
    if(actual==A7_FL_OFF || equal(table,c->candidate)) {
        copy(c->candidate,table);c->state=actual;return leave(c,A7_FL_OK);
    }
    c->write_result=c->api.write(3,A7_FL_PROPERTY,table);
    c->read_result=c->api.read(A7_FL_PROPERTY,c->scratch);
    if(c->write_result==(int)A7_FL_BYTES && c->read_result==(int)A7_FL_BYTES && equal(c->scratch,table)) {
        copy(c->candidate,table);c->state=A7_FL_ON;return leave(c,A7_FL_OK);
    }
    int error=c->write_result==(int)A7_FL_BYTES?A7_FL_VERIFY:A7_FL_WRITE;
    c->recovery_result=c->api.write(3,A7_FL_PROPERTY,c->original);
    actual=read_current(c);
    if(actual==A7_FL_OFF) {c->state=A7_FL_OFF;return leave(c,error);}
    c->state=A7_FL_FAULT;return leave(c,A7_FL_RECOVERY);
}
