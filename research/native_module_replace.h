#ifndef NATIVE_MODULE_REPLACE_H
#define NATIVE_MODULE_REPLACE_H
#include <stdint.h>
typedef long (*NMRCall)(void *,long,long,long,long,long,long,long);
typedef int (*NMRIdentity)(void *); /* Verified read-only ILCE-7M3 identity, returns1. */
typedef struct {
    uint32_t version,old_size,new_size,view_size;
    const unsigned char *new_bytes;
    unsigned char old_sha[32],new_sha[32],view_sha[32],new_proof_sha[32];
} NMRBundle;
typedef struct {
    uint32_t magic,version,phase,created,backed_up,published;
    int32_t status,first_error,rollback_ok,readonly_confirmed;
    unsigned char binding[32];
} NMRReport;
/* Only this explicit first upgrade: a7fl.so, .a7fl-r1.new,
 * .a7fl-2478cec2.orig, /setting/A7FLUP1.LOG. Never resumes or deletes journal.
 * write=0 is preflight only; write=1 publishes one new inode. Existing mapped
 * DSO pages are untouched and remain old until a separately requested reboot.
 * No constructors, process control or USB calls are present in this core. */
int nmr_run(const NMRBundle *,const unsigned char expected[32],NMRCall,void *,NMRIdentity,void *,int write,NMRReport *);
void nmr_binding(const NMRBundle *,unsigned char [32]);
long nmr_linux_call(void *,long,long,long,long,long,long,long);
#endif
