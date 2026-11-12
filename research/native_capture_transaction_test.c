/* Host-only Backup API fixture for the two CAP properties. */
#include "a7-fl-capture.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static uint8_t factory[2][A7_FL_BYTES],look[2][A7_FL_BYTES],live[2][A7_FL_BYTES];
static const uint8_t *const stock[2]={factory[0],factory[1]};
static const uint8_t *const candidate[2]={look[0],look[1]};
static unsigned writes,fail_at,fail_mode,bad_layout;
static unsigned index_for(uint32_t id) {
    assert(id==0x30005||id==0x30006);
    return id-0x30005;
}
static int cap_size(uint32_t id) {return index_for(id)==1&&bad_layout?1279:1280;}
static int cap_attr(uint32_t id) {(void)index_for(id);return 8;}
static int cap_read(uint32_t id,void *out) {
    memcpy(out,live[index_for(id)],1280);return 1280;
}
static int cap_write(uint16_t mode,uint32_t id,const void *bytes) {
    assert(mode==3);
    unsigned index=index_for(id);
    ++writes;
    if(writes==fail_at&&fail_mode==1)return -1;
    memcpy(live[index],bytes,1280);
    if(writes!=fail_at)return 1280;
    if(fail_mode==3)live[index][1215]^=1;
    return -1;
}
static const struct a7_fl_api api={cap_size,cap_attr,cap_read,cap_write};
static void start(void) {
    memset(factory,0,sizeof factory);
    factory[0][405]=255;factory[1][405]=126;
    memcpy(look,factory,sizeof look);
    look[0][0]=1;look[1][0]=2;look[0][405]=254;look[1][405]=127;
    memcpy(live,factory,sizeof live);
    writes=fail_at=fail_mode=bad_layout=0;
}
int main(void) {
    start();
    assert(a7_fl_capture_check(&api,stock,candidate,0)==0);
    assert(a7_fl_capture_set(&api,stock,candidate,1)==0&&writes==2);
    assert(a7_fl_capture_check(&api,stock,candidate,1)==0);
    assert(a7_fl_capture_set(&api,stock,candidate,1)==0&&writes==2);
    assert(a7_fl_capture_set(&api,stock,candidate,0)==0&&writes==4);
    assert(a7_fl_capture_check(&api,stock,candidate,0)==0);

    start();
    memcpy(live[0],look[0],A7_FL_BYTES);
    assert(a7_fl_capture_check(&api,stock,candidate,-1)==0);
    assert(a7_fl_capture_check(&api,stock,candidate,1)==A7_FL_VERIFY);
    assert(a7_fl_capture_set(&api,stock,candidate,1)==0&&writes==1);

    start();
    bad_layout=1;
    assert(a7_fl_capture_set(&api,stock,candidate,1)==A7_FL_LAYOUT&&writes==0);
    bad_layout=0;
    live[1][1215]=2;
    assert(a7_fl_capture_set(&api,stock,candidate,1)==A7_FL_FOREIGN&&writes==0);

    start();
    look[1][1215]=1;
    assert(a7_fl_capture_set(&api,stock,candidate,1)==A7_FL_TABLE&&writes==0);
    look[1][1215]=0;look[1][0]=30;
    assert(a7_fl_capture_set(&api,stock,candidate,1)==A7_FL_TABLE&&writes==0);
    look[1][0]=2;look[1][405]=0;
    /* Packed level 8 differs by only two, but scaling wraps badly. */
    assert(a7_fl_capture_set(&api,stock,candidate,1)==A7_FL_TABLE&&writes==0);

    for(unsigned mode=1;mode<=2;mode++) {
        start();fail_at=2;fail_mode=mode;
        assert(a7_fl_capture_set(&api,stock,candidate,1)==A7_FL_WRITE);
        assert(a7_fl_capture_check(&api,stock,candidate,0)==0);
        assert(writes==(mode==1?3u:4u));
    }
    start();fail_at=2;fail_mode=3;
    assert(a7_fl_capture_set(&api,stock,candidate,1)==A7_FL_RECOVERY);
    assert(writes==3&&memcmp(live[0],factory[0],1280)==0&&live[1][1215]==1);
    puts("NATIVE_CAPTURE_TRANSACTION_PASSED");
    return 0;
}
