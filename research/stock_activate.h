#ifndef STOCK_ACTIVATE_H
#define STOCK_ACTIVATE_H
#include <stdint.h>
#include "stock_layout.h"
#if NMA_PAGE_COUNT < 1 || NMA_PAGE_COUNT > 31 || NMA_PATCH_COUNT != NMA_PAGE_COUNT
#error Unsupported stock activation layout
#endif
#define NMA_PAGE_MASK ((1u << NMA_PAGE_COUNT)-1)
typedef long (*NmaSyscall)(void *,long,long,long,long,long,long,long);
typedef struct {uint32_t size;unsigned char sha[32];} NmaFile;
typedef struct {uint32_t offset,size;unsigned char before[4096],after[4096];} NmaPatch;
typedef struct {
 uint32_t version,view_size;
 unsigned char view_before[32],view_after[32];
 NmaFile required[NMA_REQUIRED_COUNT];
 NmaPatch patches[NMA_PATCH_COUNT];
 unsigned char pages[NMA_PAGE_COUNT][4096];
} NmaBundle;
typedef struct {
 uint32_t magic,version,phase,pid,view_base,other_mappings,cow_mask,written_mask;
 int32_t status,first_error,rollback_ok,readonly_confirmed;
 unsigned char bundle_sha[32];
} NmaReport;
int nma_run(const NmaBundle *,const unsigned char [32],NmaSyscall,void *,int,NmaReport *);
void nma_bundle_sha(const NmaBundle *,unsigned char [32]);
long nma_linux_syscall(void *,long,long,long,long,long,long,long);
#endif
