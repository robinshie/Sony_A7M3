#include "a7-fl-capture.h"

#define CAP_BYTES ((int)A7_FL_BYTES)

static int same(const uint8_t *a,const uint8_t *b,unsigned n) {
    for(unsigned i=0;i<n;i++)if(a[i]!=b[i])return 0;
    return 1;
}
static int raw_signed(unsigned value) {return value<128?(int)value:(int)value-256;}
static int packed(unsigned value,unsigned level) {
    int raw=raw_signed(value);
    if(level<8) {
        raw*=(int)level;
        raw=raw>=0?raw/8:-((-raw+7)/8);
    }
    unsigned code=(unsigned)raw&127;
    return code<64?(int)code:(int)code-128;
}
static int bounded_pair(const uint8_t *stock,const uint8_t *candidate,unsigned table) {
    if(!same(stock+1215,candidate+1215,65)||same(stock,candidate,1215))return 0;
    for(unsigned i=0;i<1215;i++) {
        unsigned a=stock[i],b=candidate[i];
        if(table==0) {
            int x=raw_signed(a),y=raw_signed(b);
            if(x< -64||x>63||y< -64||y>63)return 0;
        } else if(a>=128||b>=128)return 0;
        if(a==b)continue;
        int limit=i<405?8:12;
        for(unsigned level=1;level<=8;level++) {
            int delta=packed(b,level)-packed(a,level);
            if(delta< -limit||delta>limit)return 0;
        }
    }
    return 1;
}
static int arguments(const struct a7_fl_api *api,const uint8_t *const stock[2],
                     const uint8_t *const candidate[2]) {
    if(!api||!stock||!candidate||!stock[0]||!stock[1]||!candidate[0]||!candidate[1])
        return A7_FL_ARGUMENT;
    if(!api->size||!api->attr||!api->read||!api->write)return A7_FL_API;
    if(!bounded_pair(stock[0],candidate[0],0)||!bounded_pair(stock[1],candidate[1],1))
        return A7_FL_TABLE;
    return 0;
}
static uint32_t property(unsigned i) {return A7_FL_PROPERTY+1+i;}
static int read_state(const struct a7_fl_api *api,const uint8_t *const stock[2],
                      const uint8_t *const candidate[2],unsigned i,uint8_t *scratch) {
    uint32_t id=property(i);
    if(api->size(id)!=CAP_BYTES||api->attr(id)!=8)return A7_FL_LAYOUT;
    if(api->read(id,scratch)!=CAP_BYTES)return A7_FL_READ;
    if(same(scratch,stock[i],A7_FL_BYTES))return A7_FL_OFF;
    if(same(scratch,candidate[i],A7_FL_BYTES))return A7_FL_ON;
    return A7_FL_FOREIGN;
}
static int read_pair(const struct a7_fl_api *api,const uint8_t *const stock[2],
                     const uint8_t *const candidate[2],int state[2],uint8_t *scratch) {
    for(unsigned i=0;i<2;i++) {
        state[i]=read_state(api,stock,candidate,i,scratch);
        if(state[i]<0)return state[i];
    }
    return 0;
}
int a7_fl_capture_check(const struct a7_fl_api *api,const uint8_t *const stock[2],
                        const uint8_t *const candidate[2],int expected) {
    if(expected< -1||expected>1)return A7_FL_ARGUMENT;
    int rc=arguments(api,stock,candidate);
    if(rc)return rc;
    uint8_t scratch[A7_FL_BYTES];
    int state[2];
    rc=read_pair(api,stock,candidate,state,scratch);
    if(rc)return rc;
    if(expected>=0&&(state[0]!=expected||state[1]!=expected))return A7_FL_VERIFY;
    return 0;
}
int a7_fl_capture_set(const struct a7_fl_api *api,const uint8_t *const stock[2],
                      const uint8_t *const candidate[2],int enabled) {
    if(enabled!=0&&enabled!=1)return A7_FL_ARGUMENT;
    int rc=arguments(api,stock,candidate);
    if(rc)return rc;
    uint8_t scratch[A7_FL_BYTES];
    int before[2],seen[2];
    rc=read_pair(api,stock,candidate,before,scratch);
    if(rc)return rc;
    unsigned attempted=0;
    const uint8_t *const *target=enabled?candidate:stock;
    for(unsigned i=0;i<2;i++) {
        if(before[i]==enabled)continue;
        rc=read_pair(api,stock,candidate,seen,scratch);
        if(rc)goto failed;
        for(unsigned j=0;j<2;j++) {
            if(seen[j]!=((attempted&(1u<<j))?enabled:before[j])) {
                rc=A7_FL_FOREIGN;goto failed;
            }
        }
        attempted|=1u<<i;
        int written=api->write(3,property(i),target[i]);
        int after=read_state(api,stock,candidate,i,scratch);
        if(written!=CAP_BYTES) {rc=A7_FL_WRITE;goto failed;}
        if(after!=enabled) {rc=A7_FL_VERIFY;goto failed;}
    }
    if(!attempted)return 0;
    rc=read_pair(api,stock,candidate,seen,scratch);
    if(!rc&&seen[0]==enabled&&seen[1]==enabled)return 0;
    if(!rc)rc=A7_FL_VERIFY;
failed:
    if(!attempted)return rc;
    /* The call may have written despite an error acknowledgement. Restore
     * only a verified, recognized target; do not overwrite unrelated data. */
    for(unsigned n=2;n>0;n--) {
        unsigned i=n-1;
        if(!(attempted&(1u<<i)))continue;
        int after=read_state(api,stock,candidate,i,scratch);
        if(after==enabled&&after!=before[i]) {
            (void)api->write(3,property(i),before[i]?candidate[i]:stock[i]);
        }
    }
    if(read_pair(api,stock,candidate,seen,scratch)||seen[0]!=before[0]||seen[1]!=before[1])
        return A7_FL_RECOVERY;
    return rc;
}
