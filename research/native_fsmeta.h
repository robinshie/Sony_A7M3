#ifndef NATIVE_FSMETA_H
#define NATIVE_FSMETA_H
#include <stdint.h>
typedef long (*NfmSyscall)(void *,long,long,long,long,long,long,long);
typedef struct {uint32_t offset,size;int32_t result;uint32_t tag;unsigned char bytes[1024];} NfmRaw;
typedef struct {int32_t lstat_result,open_result,fstat_result,close_result;unsigned char lstat64[104],fstat64[104];} NfmStat;
typedef struct {int32_t open_result,read_result,close_result;uint32_t size;unsigned char bytes[16384];} NfmDirectory;
typedef struct {
 uint32_t magic,version,size;int32_t status,first_error;
 uint32_t capacity,geometry_ok,raw_count,mount_size,stat_count,directory_count,reserved[5];
 NfmRaw raw[32];NfmStat stats[8];NfmDirectory directories[2];unsigned char mounts[4096];
} NfmReport;
int nfm_read(NfmReport *,NfmSyscall,void *);
#endif
