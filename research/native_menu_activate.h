#ifndef NATIVE_MENU_ACTIVATE_H
#define NATIVE_MENU_ACTIVATE_H
#include <stdint.h>
typedef long (*NmaSyscall)(void *,long,long,long,long,long,long,long);
typedef struct {uint32_t size;unsigned char sha[32];} NmaFile;
typedef struct {uint32_t offset,size;unsigned char before[80],after[80];} NmaPatch;
typedef struct {
 uint32_t version,view_size;
 unsigned char view_before[32],view_after[32];
 NmaFile required[3]; /* /usr/lib/a7fl.so and the two published locales */
 NmaPatch patches[4]; /* helper A, helper B, MENU branch, still-entry branch */
 unsigned char pages[3][4096]; /* old file pages at188000,20d000,5b9000 */
} NmaBundle;
typedef struct {
 uint32_t magic,version,phase,pid,view_base,other_mappings,cow_mask,written_mask;
 int32_t status,first_error,rollback_ok,readonly_confirmed;
 unsigned char bundle_sha[32];
} NmaReport;
/* mode0 is strictly read-only. mode1 makes three same-byte private COW pages,
 * then writes only the four attested ranges through the kernel filesystem.
 * Mode2 independently restores attested old bytes from a known mixed state,
 * only while all three current mapped pages are still the old version.
 * Mode3 removes activation after a new-loader boot (new mapped pages and full
 * new file required). Mode4 recovers a failed mode3 known-mixed transaction.
 * Both retain unchanged new executable pages until the following cold boot.
 * No raw devices, signal/thread operations, new processes or reboot calls. */
int nma_run(const NmaBundle *,const unsigned char expected[32],NmaSyscall,void *,int mode,NmaReport *);
void nma_bundle_sha(const NmaBundle *,unsigned char [32]);
long nma_linux_syscall(void *,long,long,long,long,long,long,long);
#endif
