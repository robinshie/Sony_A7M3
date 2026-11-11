#ifndef NATIVE_MENU_WBI_H
#define NATIVE_MENU_WBI_H
#include <stdint.h>
typedef long (*NwbSys)(void*,long,long,long,long,long,long,long);
typedef struct {
 uint32_t magic,version,phase;int32_t status,error;
 uint32_t pid,capacity_lo,capacity_hi,mode,header_kind,written,fsync_ok,neighbor_ok,reserved;
 unsigned char preimage_sha[32],data[1024];
} NwbReport;
int nwb_run(NwbSys,void*,unsigned,const unsigned char*,NwbReport*);
#endif
